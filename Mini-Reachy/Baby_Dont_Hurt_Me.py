import time
import numpy as np
import librosa  # Great for loading and resampling audio
from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose

def dance_to_music(audio_file_path):
    print(f"Loading {audio_file_path}...")
    
    # 1. Load the song and force it to 16kHz (the sample rate Reachy expects)
    # librosa loads audio as float32 by default, which is perfect.
    samples, sr = librosa.load(audio_file_path, sr=16000, mono=False)
    
    # Reshape the array to (samples, channels) as expected by the SDK
    if samples.ndim > 1:
        samples = samples.T  # Stereo
    else:
        samples = samples.reshape(-1, 1)  # Mono

    # 2. Initialize Reachy (Note: media_backend="default" is required for audio!)
    with ReachyMini(media_backend="default") as mini:
        print("Ready to rock. Centering head...")
        
        # Center the robot before the beat drops
        mini.goto_target(
            head=create_head_pose(x=0, y=0, z=0, roll=0, pitch=0, yaw=0, mm=True),
            duration=1.0, method="ease_in_out"
        )
        time.sleep(1.0)
        
        # 3. Setup Audio
        mini.media.start_playing()
        
        # Calculate exactly how long the song is in seconds using the SDK formula
        sample_rate = mini.media.get_output_audio_samplerate()
        song_duration = len(samples) / sample_rate
        print(f"Song duration calculated: {song_duration:.2f} seconds.")

        # 4. Play the music! (This runs in the background)
        mini.media.push_audio_sample(samples)
        
        # 5. Start the dance loop
        BEAT_DURATION = 0.4 
        start_time = time.time()
        
        # Keep dancing as long as the elapsed time is less than the song duration
        while (time.time() - start_time) < song_duration:
            
            # --- WOBBLE LEFT ---
            mini.goto_target(
                head=create_head_pose(y=-25, roll=np.deg2rad(-25), mm=True),
                body_yaw=np.deg2rad(-10),
                antennas=np.deg2rad([30, -10]),
                duration=BEAT_DURATION,
                method="ease_in_out"
            )
            time.sleep(BEAT_DURATION)
            
            # Quick check: If the song ended during the left wobble, break out of the loop!
            if (time.time() - start_time) >= song_duration:
                break
            
            # --- WOBBLE RIGHT ---
            mini.goto_target(
                head=create_head_pose(y=25, roll=np.deg2rad(25), mm=True),
                body_yaw=np.deg2rad(10),
                antennas=np.deg2rad([-10, 30]),
                duration=BEAT_DURATION,
                method="ease_in_out"
            )
            time.sleep(BEAT_DURATION)

        # 6. Cleanup after the song is over
        print("Song finished! Stopping audio and resetting.")
        mini.media.stop_playing()
        
        mini.goto_target(
            head=create_head_pose(x=0, y=0, z=0, roll=0, pitch=0, yaw=0, mm=True),
            body_yaw=0.0,
            antennas=np.deg2rad([0, 0]),
            duration=1.0,
            method="minjerk"
        )

if __name__ == "__main__":
    # Point this to where your audio file is saved!
    dance_to_music("What_Is_Love.mp3")