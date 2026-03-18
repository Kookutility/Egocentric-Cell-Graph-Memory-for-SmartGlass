using UnityEngine;

namespace SmartGlass.Player
{
    /// <summary>
    /// Simple first-person keyboard and mouse controller for indoor navigation tests.
    /// </summary>
    [RequireComponent(typeof(CharacterController))]
    public class PlayerController : MonoBehaviour
    {
        [SerializeField] private Camera playerCamera;
        [SerializeField] private float moveSpeed = 2.5f;
        [SerializeField] private float lookSensitivity = 2.0f;
        [SerializeField] private float gravity = -9.81f;

        private CharacterController characterController;
        private float pitch;
        private Vector3 verticalVelocity;

        public float CurrentYawDeg => transform.eulerAngles.y;

        private void Awake()
        {
            characterController = GetComponent<CharacterController>();
            Cursor.lockState = CursorLockMode.Locked;
        }

        private void Update()
        {
            UpdateLook();
            UpdateMovement();
        }

        private void UpdateLook()
        {
            float mouseX = Input.GetAxis("Mouse X") * lookSensitivity;
            float mouseY = Input.GetAxis("Mouse Y") * lookSensitivity;

            pitch = Mathf.Clamp(pitch - mouseY, -80f, 80f);
            playerCamera.transform.localRotation = Quaternion.Euler(pitch, 0f, 0f);
            transform.Rotate(Vector3.up * mouseX);
        }

        private void UpdateMovement()
        {
            Vector3 input = new Vector3(Input.GetAxis("Horizontal"), 0f, Input.GetAxis("Vertical"));
            Vector3 worldMove = transform.TransformDirection(input.normalized) * moveSpeed;

            if (characterController.isGrounded && verticalVelocity.y < 0f)
            {
                verticalVelocity.y = -2f;
            }

            verticalVelocity.y += gravity * Time.deltaTime;
            Vector3 finalMove = worldMove + verticalVelocity;
            characterController.Move(finalMove * Time.deltaTime);
        }
    }
}
