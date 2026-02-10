from reachy2_sdk import ReachySDK
import time

reachy = ReachySDK(host='192.168.50.241') 

reachy.r_arm.turn_off()

print("--- Reachy is now in Compliant Mode ---")
print("Move the arm to the positions you want to record.")
print("The code will print the joint angles in a format you can copy-paste.")
print("Press Ctrl+C to stop.\n")

try:
    while True:
        s_pitch = reachy.r_arm.shoulder.pitch.present_position
        s_roll  = reachy.r_arm.shoulder.roll.present_position
        e_yaw   = reachy.r_arm.elbow.yaw.present_position
        e_pitch = reachy.r_arm.elbow.pitch.present_position

        print(f"{{ 'r_arm.shoulder.pitch': {s_pitch:.1f}, "
              f"'r_arm.shoulder.roll': {s_roll:.1f}, "
              f"'r_arm.elbow.yaw': {e_yaw:.1f}, "
              f"'r_arm.elbow.pitch': {e_pitch:.1f} }}")

        time.sleep(0.5)

except KeyboardInterrupt:
    print("\n--- Monitoring Stopped by User ---")