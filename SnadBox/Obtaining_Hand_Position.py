from reachy2_sdk import ReachySDK
import time

reachy = ReachySDK(host='192.168.50.241') 

# TURN OFF torque to make arms compliant (movable by hand)
reachy.turn_off() 

print("--- Reachy is now in Compliant Mode ---")
print("You can move the arm manually. Press Ctrl+C to stop.\n")

try:
    while True:
        pose_matrix = reachy.r_arm.forward_kinematics()

        x_pos = pose_matrix[0, 3]
        y_pos = pose_matrix[1, 3]
        z_pos = pose_matrix[2, 3]

        print(f"X: {x_pos:.3f} | Y: {y_pos:.3f} | Z: {z_pos:.3f} ")
        

        time.sleep(1)

except KeyboardInterrupt:
    print("\n--- Monitoring Stopped by User ---")



