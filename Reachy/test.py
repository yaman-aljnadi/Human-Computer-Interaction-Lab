import cv2
import time
from reachy2_sdk import ReachySDK

# 1. Connect to your Reachy 2 robot
# Replace 'reachy.local' with your robot's actual IP address if necessary
reachy = ReachySDK(host='reachy.local') 

# 2. Check connected cameras
print(f"Available cameras: {reachy.cameras}")

# 3. Stream from the left camera (teleop_left)
print("Starting camera stream... Press 'q' to quit.")

while True:
    # Retrieve the latest frame from the left camera
    # You can also use reachy.cameras.teleop_right for the right eye
    frame = reachy.cameras.teleop_left.last_frame
    
    if frame is not None:
        cv2.imshow('Reachy 2 Left Eye', frame)
    
    # Break loop on 'q' press
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# 4. Cleanup
cv2.destroyAllWindows()
reachy.disconnect()