from reachy2_sdk import ReachySDK
import time

# Connect to Reachy 2
reachy = ReachySDK(host='192.168.50.213')

# Put BOTH arms into compliant mode
reachy.r_arm.turn_off()
reachy.l_arm.turn_off()

print("--- Reachy is now in Compliant Mode ---")
print("Move BOTH arms to the positions you want to record.")
print("The code will print the joint angles for both arms.")
print("Press Ctrl+C to stop.\n")

try:
    while True:

        # =========================
        # RIGHT ARM
        # =========================
        r_s_pitch = reachy.r_arm.shoulder.pitch.present_position
        r_s_roll  = reachy.r_arm.shoulder.roll.present_position
        r_e_yaw   = reachy.r_arm.elbow.yaw.present_position
        r_e_pitch = reachy.r_arm.elbow.pitch.present_position

        # =========================
        # LEFT ARM
        # =========================
        l_s_pitch = reachy.l_arm.shoulder.pitch.present_position
        l_s_roll  = reachy.l_arm.shoulder.roll.present_position
        l_e_yaw   = reachy.l_arm.elbow.yaw.present_position
        l_e_pitch = reachy.l_arm.elbow.pitch.present_position

        # Print everything as one snapshot
        print(
            "{ "
            f"'r_arm.shoulder.pitch': {r_s_pitch:.1f}, "
            f"'r_arm.shoulder.roll': {r_s_roll:.1f}, "
            f"'r_arm.elbow.yaw': {r_e_yaw:.1f}, "
            f"'r_arm.elbow.pitch': {r_e_pitch:.1f}, "
            f"'l_arm.shoulder.pitch': {l_s_pitch:.1f}, "
            f"'l_arm.shoulder.roll': {l_s_roll:.1f}, "
            f"'l_arm.elbow.yaw': {l_e_yaw:.1f}, "
            f"'l_arm.elbow.pitch': {l_e_pitch:.1f}"
            " }"
        )

        time.sleep(0.5)

except KeyboardInterrupt:
    print("\n--- Monitoring Stopped by User ---")