using SmartGlass.Network;
using TMPro;
using UnityEngine;

namespace SmartGlass.Debugging
{
    /// <summary>
    /// Displays graph summary and runtime state for live debugging.
    /// </summary>
    public class DebugGraphView : MonoBehaviour
    {
        [SerializeField] private PythonBridge pythonBridge;
        [SerializeField] private TextMeshProUGUI graphSummaryText;

        private void Awake()
        {
            pythonBridge.OnResultReceived += HandleResult;
        }

        private void HandleResult(PythonBridge.ResultPacket result)
        {
            string summary = result.graph_summary != null ? $"Cells: {result.graph_summary.num_cells}, Edges: {result.graph_summary.num_edges}" : "Graph summary unavailable";
            graphSummaryText.text = $"FSM: {result.fsm_state}\n{summary}";
        }
    }
}
