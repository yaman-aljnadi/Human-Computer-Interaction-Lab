from reachy2_sdk import ReachySDK
from reachy2_sdk.media.camera import CameraView
import cv2
import time

IP = '192.168.50.241'  # Your Reachy IP

print(f"Connecting to {IP}...")
reachy = ReachySDK(host=IP)

if reachy.cameras.teleop is None:
    print("CRITICAL ERROR: The robot does not see a camera connected.")
    print("Action: Restart the robot hardware (Power cycle).")
else:
    print("Camera detected! Streaming test...")
    
    while True:
        # Try to grab frame
        result = reachy.cameras.teleop.get_frame(CameraView.RIGHT)
        
        if result is not None:
            frame, _ = result
            cv2.imshow("Test Stream", frame)
            print("Frame received.", end='\r')
        else:
            print("Frame dropped (None received).")

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()