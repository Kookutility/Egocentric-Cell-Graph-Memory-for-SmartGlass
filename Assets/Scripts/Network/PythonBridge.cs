using System;
using System.Collections.Concurrent;
using System.Collections;
using System.Net.Http;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using SmartGlass.Sensor;
using UnityEngine;

namespace SmartGlass.Network
{
    /// <summary>
    /// Manages HTTP session control and WebSocket runtime streaming to the Python server.
    /// </summary>
    public class PythonBridge : MonoBehaviour
    {
        [Serializable]
        public class FramePacket
        {
            public string session_id;
            public int frame_id;
            public float timestamp;
            public float yaw_deg;
            public int step_count;
            public string jpg_b64;
        }

        [Serializable]
        public class GraphSummary
        {
            public int num_cells;
            public int num_edges;
        }

        [Serializable]
        public class ResultPacket
        {
            public int frame_id;
            public string fsm_state;
            public int cell_id;
            public string cell_type;
            public string event_name;
            public string instruction;
            public float confidence;
            public GraphSummary graph_summary;
            public string rawJson;
        }

        [SerializeField] private string httpBaseUrl = "http://127.0.0.1:8000";
        [SerializeField] private string wsUrl = "ws://127.0.0.1:8000/ws/runtime";
        [SerializeField] private string sessionId = "demo_001";
        [SerializeField] private ImuSimulator imuSimulator;
        [SerializeField] private SensorCapture sensorCapture;

        private readonly ConcurrentQueue<string> outgoingFrames = new ConcurrentQueue<string>();
        private readonly ConcurrentQueue<ResultPacket> incomingResults = new ConcurrentQueue<ResultPacket>();
        private readonly HttpClient httpClient = new HttpClient();
        private ClientWebSocket webSocket;
        private CancellationTokenSource cancellationSource;
        private int frameId;
        private int sentFrameCount;
        private int droppedFrameCount;
        private float averageLatencyMs;
        private bool sessionActive;

        public bool IsConnected => webSocket != null && webSocket.State == WebSocketState.Open;
        public string ConnectionState => IsConnected ? "Connected" : sessionActive ? "Connecting" : "Idle";
        public int SentFrameCount => sentFrameCount;
        public int DroppedFrameCount => droppedFrameCount;
        public float AverageLatencyMs => averageLatencyMs;
        public event Action<ResultPacket> OnResultReceived;

        private void Awake()
        {
            if (sensorCapture != null)
            {
                sensorCapture.OnFrameEncoded += QueueFrame;
            }
        }

        private void Update()
        {
            while (incomingResults.TryDequeue(out ResultPacket result))
            {
                OnResultReceived?.Invoke(result);
            }
        }

        public async void StartSession()
        {
            if (sessionActive) return;
            sessionActive = true;
            cancellationSource = new CancellationTokenSource();
            await PostJsonAsync("/session/start", "{\"session_id\":\"" + sessionId + "\"}");
            await ConnectWebSocketAsync(cancellationSource.Token);
            _ = Task.Run(() => SendLoopAsync(cancellationSource.Token));
            _ = Task.Run(() => ReceiveLoopAsync(cancellationSource.Token));
        }

        public async void ResetSession()
        {
            await PostJsonAsync("/session/reset", "{}");
            frameId = 0;
        }

        public async void StopSession()
        {
            sessionActive = false;
            cancellationSource?.Cancel();
            if (webSocket != null)
            {
                await webSocket.CloseAsync(WebSocketCloseStatus.NormalClosure, "Stopping", CancellationToken.None);
            }
            await PostJsonAsync("/session/stop", "{}");
        }

        public async void TriggerBacktracking()
        {
            await PostJsonAsync("/session/backtrack", "{}");
        }

        private async Task PostJsonAsync(string path, string json)
        {
            using var content = new StringContent(json, Encoding.UTF8, "application/json");
            await httpClient.PostAsync(httpBaseUrl + path, content);
        }

        private async Task ConnectWebSocketAsync(CancellationToken token)
        {
            webSocket = new ClientWebSocket();
            await webSocket.ConnectAsync(new Uri(wsUrl), token);
        }

        private void QueueFrame(byte[] jpgBytes)
        {
            if (!sessionActive)
            {
                return;
            }
            frameId += 1;
            var packet = new FramePacket
            {
                session_id = sessionId,
                frame_id = frameId,
                timestamp = Time.time,
                yaw_deg = imuSimulator != null ? imuSimulator.SmoothedYawDeg : 0f,
                step_count = frameId,
                jpg_b64 = Convert.ToBase64String(jpgBytes)
            };
            string json = JsonUtility.ToJson(packet);
            if (outgoingFrames.Count > 2)
            {
                droppedFrameCount += 1;
                return;
            }
            outgoingFrames.Enqueue(json);
        }

        private async Task SendLoopAsync(CancellationToken token)
        {
            while (!token.IsCancellationRequested)
            {
                if (!IsConnected)
                {
                    await Task.Delay(250, token);
                    continue;
                }
                if (!outgoingFrames.TryDequeue(out string json))
                {
                    await Task.Delay(5, token);
                    continue;
                }
                var start = Time.realtimeSinceStartup;
                ArraySegment<byte> bytes = new ArraySegment<byte>(Encoding.UTF8.GetBytes(json));
                await webSocket.SendAsync(bytes, WebSocketMessageType.Text, true, token);
                sentFrameCount += 1;
                averageLatencyMs = Mathf.Lerp(averageLatencyMs, (Time.realtimeSinceStartup - start) * 1000f, 0.1f);
            }
        }

        private async Task ReceiveLoopAsync(CancellationToken token)
        {
            byte[] buffer = new byte[32768];
            while (!token.IsCancellationRequested && IsConnected)
            {
                var segment = new ArraySegment<byte>(buffer);
                WebSocketReceiveResult result = await webSocket.ReceiveAsync(segment, token);
                string json = Encoding.UTF8.GetString(buffer, 0, result.Count);
                string normalizedJson = json.Replace("\"event\"", "\"event_name\"");
                ResultPacket packet = JsonUtility.FromJson<ResultPacket>(normalizedJson);
                packet.rawJson = json;
                incomingResults.Enqueue(packet);
            }
        }
    }
}
