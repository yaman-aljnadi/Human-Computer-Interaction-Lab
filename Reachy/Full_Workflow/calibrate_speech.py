import time
import wave
import contextlib
import os
import config
from speaking import Voice
from reachy_interface import ReachyRobot

def get_wav_duration(filename):
    # obtain the wav file duration 
    if not os.path.exists(filename):
        return 0
    with contextlib.closing(wave.open(filename, 'r')) as f:
        frames = f.getnframes()
        rate = f.getframerate()
        return frames / float(rate)

def run_calibration():
    # Initialize connection
    print("Initializing components...")
    voice = Voice()
    robot = ReachyRobot()
    
    samples = [
        "Hello.",
        "I am Reachy, your robotic assistant.",
        "This is a much longer sentence. I am speaking for a longer time to verify that my new timing calculation works perfectly for paragraphs."
    ]

    print("\n--- Starting Audio Calibration ---")
    
    for i, text in enumerate(samples):
        print(f"\n Test {i+1}: '{text[:30]}...'")
        
        # Generating Audio files in order to do testing and finding out how long 
        voice.synthesize(text, config.TEMP_OUTPUT_AUDIO)
        
        # Calculate EXACT duration 
        duration = get_wav_duration(config.TEMP_OUTPUT_AUDIO)
        print(f" -> File Duration: {duration:.2f} seconds")
        
        # Play it on Reachy
        # We pass wait=False because we want to control the sleep ourselves
        robot.play_audio(config.TEMP_OUTPUT_AUDIO, wait=False)
        
        # Sleep for the exact duration + small buffer (0.5s) for network latency
        print(f" -> Sleeping for {duration + 0.5:.2f}s...")
        time.sleep(duration + 0.5)
        print(" -> Done.")

    print("\nCalibration Complete. If the speech didn't cut off, the logic is valid.")
    robot.disconnect()

if __name__ == "__main__":
    run_calibration()