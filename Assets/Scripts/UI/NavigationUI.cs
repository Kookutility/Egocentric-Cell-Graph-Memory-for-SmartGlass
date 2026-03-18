using SmartGlass.Network;
using TMPro;
using UnityEngine;

namespace SmartGlass.UI
{
    /// <summary>
    /// Updates the main smart-glass runtime labels from the latest Python result packet.
    /// </summary>
    public class NavigationUI : MonoBehaviour
    {
        [SerializeField] private PythonBridge pythonBridge;
        [SerializeField] private TextMeshProUGUI instructionText;
        [SerializeField] private TextMeshProUGUI cellIdText;
        [SerializeField] private TextMeshProUGUI cellTypeText;
        [SerializeField] private TextMeshProUGUI eventText;
        [SerializeField] private TextMeshProUGUI statusText;
        [SerializeField] private TextMeshProUGUI metricsText;

        private void Awake()
        {
            pythonBridge.OnResultReceived += HandleResult;
        }

        private void Update()
        {
            statusText.text = $"Status: {pythonBridge.ConnectionState}";
            metricsText.text = $"Sent: {pythonBridge.SentFrameCount} / Dropped: {pythonBridge.DroppedFrameCount} / RTT≈ {pythonBridge.AverageLatencyMs:F1} ms";
        }

        private void HandleResult(PythonBridge.ResultPacket result)
        {
            instructionText.text = "Instruction: " + result.instruction;
            cellIdText.text = "Cell ID: " + result.cell_id;
            cellTypeText.text = "Cell Type: " + result.cell_type;
            eventText.text = $"Event: {result.event_name} / Confidence: {result.confidence:F2}";
        }
    }
}
