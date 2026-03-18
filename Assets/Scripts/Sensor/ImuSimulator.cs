using System.Collections.Generic;
using UnityEngine;

namespace SmartGlass.Sensor
{
    /// <summary>
    /// Computes smoothed yaw and turn accumulation from the player or camera heading.
    /// </summary>
    public class ImuSimulator : MonoBehaviour
    {
        [SerializeField] private Transform yawSource;
        [SerializeField] private int smoothWindow = 7;

        private readonly Queue<float> yawHistory = new Queue<float>();
        private float yawSum;
        private float? lastSmoothedYaw;
        private float accumulatedTurn;

        public float CurrentYawDeg { get; private set; }
        public float SmoothedYawDeg { get; private set; }
        public float YawDeltaDeg { get; private set; }
        public float AccumulatedTurnDeg => accumulatedTurn;

        private void Update()
        {
            Transform source = yawSource != null ? yawSource : transform;
            CurrentYawDeg = source.eulerAngles.y;

            yawHistory.Enqueue(CurrentYawDeg);
            yawSum += CurrentYawDeg;
            while (yawHistory.Count > smoothWindow)
            {
                yawSum -= yawHistory.Dequeue();
            }

            SmoothedYawDeg = yawSum / Mathf.Max(1, yawHistory.Count);
            YawDeltaDeg = lastSmoothedYaw.HasValue ? Mathf.DeltaAngle(lastSmoothedYaw.Value, SmoothedYawDeg) : 0f;
            accumulatedTurn += YawDeltaDeg;
            lastSmoothedYaw = SmoothedYawDeg;
        }

        public void ResetAccumulatedTurn()
        {
            accumulatedTurn = 0f;
        }
    }
}
