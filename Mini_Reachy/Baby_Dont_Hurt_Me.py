"""Play a song while Reachy Mini performs a simple head-wobble dance.

Before running, make sure the active Conda environment can import librosa.
"""

import time
from pathlib import Path

import librosa
import numpy as np
from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose


BEAT_DURATION = 0.4  # Seconds for each left/right pose


def dance_to_music(audio_file_path: str) -> None:
    audio_path = Path(audio_file_path)
    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio file not found: {audio_path.resolve()}")

    print("Connecting to Reachy Mini...")

    # Force the remote media backend so streamed audio is sent to Reachy Mini's
    # speaker instead of being routed through the computer's local audio device.
    with ReachyMini(media_backend="webrtc", log_level="INFO") as mini:
        playback_started = False
        robot_moved = False

        try:
            # The SDK expects audio samples at the output device's sample rate.
            output_sr = mini.media.get_output_audio_samplerate()
            if output_sr <= 0:
                raise RuntimeError(
                    f"Invalid output sample rate reported by Reachy Mini: {output_sr}"
                )

            print(f"Loading {audio_path} at {output_sr} Hz...")
            # librosa resamples the MP3 directly to Reachy's output sample rate.
            samples, sr = librosa.load(
                str(audio_path), sr=output_sr, mono=False, dtype=np.float32
            )

            # Reachy Mini expects shape (number_of_samples, channels).
            if samples.ndim == 1:
                samples = samples[:, np.newaxis]  # Mono: (samples, 1)
            else:
                samples = samples.T  # librosa stereo: (channels, samples)

            samples = np.ascontiguousarray(samples, dtype=np.float32)
            if samples.shape[0] == 0:
                raise RuntimeError("The audio file contains no samples.")

            song_duration = samples.shape[0] / sr
            print(f"Song duration: {song_duration:.1f} seconds")

            print("Centering head...")
            mini.goto_target(
                head=create_head_pose(x=0, y=0, z=0, roll=0, pitch=0, yaw=0, mm=True),
                duration=1.0,
                method="ease_in_out",
            )
            robot_moved = True

            mini.media.start_playing()
            playback_started = True
            time.sleep(0.1)  # Give the playback pipeline a moment to start.
            mini.media.push_audio_sample(samples)

            print("Dancing!")
            start_time = time.monotonic()

            while time.monotonic() - start_time < song_duration:
                # Wobble left. goto_target already waits for the movement duration,
                # so do not add another sleep here.
                mini.goto_target(
                    head=create_head_pose(
                        y=-25, roll=np.deg2rad(-25), mm=True
                    ),
                    body_yaw=np.deg2rad(-10),
                    antennas=np.deg2rad([30, -10]),
                    duration=BEAT_DURATION,
                    method="ease_in_out",
                )

                if time.monotonic() - start_time >= song_duration:
                    break

                # Wobble right.
                mini.goto_target(
                    head=create_head_pose(
                        y=25, roll=np.deg2rad(25), mm=True
                    ),
                    body_yaw=np.deg2rad(10),
                    antennas=np.deg2rad([-10, 30]),
                    duration=BEAT_DURATION,
                    method="ease_in_out",
                )

            print("Song finished. Stopping audio and resetting the robot.")

        finally:
            if playback_started:
                mini.media.stop_playing()

            if robot_moved:
                mini.goto_target(
                    head=create_head_pose(
                        x=0, y=0, z=0, roll=0, pitch=0, yaw=0, mm=True
                    ),
                    body_yaw=0.0,
                    antennas=np.deg2rad([0, 0]),
                    duration=1.0,
                    method="minjerk",
                )


if __name__ == "__main__":
    dance_to_music("What_Is_Love.mp3")