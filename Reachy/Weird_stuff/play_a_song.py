from reachy2_sdk import ReachySDK
import time

REACHY_IP = '192.168.50.241'
AUDIO_FILE = 'End_of_Line.mp3' 

def play_sound():
    print(f"Connecting to Reachy at {REACHY_IP}...")
    sdk = ReachySDK(host=REACHY_IP)

    if not sdk.is_connected():
        print("Could not connect to Reachy.")
        return

    print("Reachy Connected. Uploading and playing audio...")

    sdk.audio.upload_audio_file(AUDIO_FILE)
    sdk.audio.play_audio_file(AUDIO_FILE)
    time.sleep(2)
    
    sdk.disconnect()
    print("Done.")

if __name__ == "__main__":
    play_sound()
