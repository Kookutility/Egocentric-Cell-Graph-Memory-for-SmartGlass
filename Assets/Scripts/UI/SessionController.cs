using SmartGlass.Network;
using UnityEngine;

namespace SmartGlass.UI
{
    /// <summary>
    /// Button-friendly session controller for Python runtime commands.
    /// </summary>
    public class SessionController : MonoBehaviour
    {
        [SerializeField] private PythonBridge pythonBridge;

        public void StartSession()
        {
            pythonBridge.StartSession();
        }

        public void ResetSession()
        {
            pythonBridge.ResetSession();
        }

        public void StopSession()
        {
            pythonBridge.StopSession();
        }

        public void TriggerBacktracking()
        {
            pythonBridge.TriggerBacktracking();
        }
    }
}
