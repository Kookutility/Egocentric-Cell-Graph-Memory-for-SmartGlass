using System;
using System.Collections;
using UnityEngine;
using UnityEngine.Rendering;

namespace SmartGlass.Sensor
{
    /// <summary>
    /// Captures camera frames to JPG with AsyncGPUReadback for streaming to Python.
    /// </summary>
    public class SensorCapture : MonoBehaviour
    {
        [SerializeField] private Camera captureCamera;
        [SerializeField] private int width = 640;
        [SerializeField] private int height = 360;
        [SerializeField] private int captureFps = 5;
        [SerializeField, Range(40, 95)] private int jpgQuality = 75;

        private RenderTexture renderTexture;
        private Texture2D stagingTexture;
        private bool capturePending;

        public int CaptureWidth => width;
        public int CaptureHeight => height;
        public int CaptureFps => captureFps;
        public event Action<byte[]> OnFrameEncoded;

        private void Start()
        {
            renderTexture = new RenderTexture(width, height, 24, RenderTextureFormat.ARGB32);
            stagingTexture = new Texture2D(width, height, TextureFormat.RGB24, false);
            captureCamera.targetTexture = renderTexture;
            StartCoroutine(CaptureLoop());
        }

        private IEnumerator CaptureLoop()
        {
            var wait = new WaitForSeconds(1f / Mathf.Max(1, captureFps));
            while (enabled)
            {
                if (!capturePending)
                {
                    RequestCapture();
                }
                yield return wait;
            }
        }

        private void RequestCapture()
        {
            capturePending = true;
            captureCamera.Render();
            AsyncGPUReadback.Request(renderTexture, 0, TextureFormat.RGB24, OnReadbackCompleted);
        }

        private void OnReadbackCompleted(AsyncGPUReadbackRequest request)
        {
            capturePending = false;
            if (request.hasError)
            {
                Debug.LogWarning("SensorCapture GPU readback failed.");
                return;
            }

            stagingTexture.LoadRawTextureData(request.GetData<byte>());
            stagingTexture.Apply();
            byte[] jpgBytes = stagingTexture.EncodeToJPG(jpgQuality);
            OnFrameEncoded?.Invoke(jpgBytes);
        }

        private void OnDestroy()
        {
            if (captureCamera != null)
            {
                captureCamera.targetTexture = null;
            }
            if (renderTexture != null)
            {
                renderTexture.Release();
            }
        }
    }
}
