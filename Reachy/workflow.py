import torch
import cv2
import time
import os
import wave
from PIL import Image as PILImage
from pynput import keyboard 

# Piper Import
from piper import PiperVoice

# Qwen Imports
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info

# Reachy 2 Imports
from reachy2_sdk import ReachySDK
from reachy2_sdk.media.camera import CameraView

class ReachyAIVoiceBot:
    def __init__(self, reachy_ip='192.168.50.241'):
        print("Connecting to Reachy...")
        self.reachy = ReachySDK(host=reachy_ip)
        
        if not self.reachy.is_connected():
            raise ConnectionError("Could not connect to Reachy 2.")
            
        print("Loading Qwen 2.5 Vision Model...")
        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"

        self.model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            "Qwen/Qwen2.5-VL-3B-Instruct",
            torch_dtype=torch.bfloat16,
            device_map="auto",
        )
        self.processor = AutoProcessor.from_pretrained("Qwen/Qwen2.5-VL-3B-Instruct")
        
        # --- NEW: Load Piper Voice Model ---
        # Update this to match your specific .onnx file name
        self.model_path = "piper_audios/en_US-joe-medium.onnx" 
        print(f"Loading Piper Voice Model: {self.model_path}...")
        try:
            self.voice = PiperVoice.load(self.model_path, use_cuda=torch.cuda.is_available())
            print("Piper Voice loaded successfully!")
        except Exception as e:
            print(f"Failed to load Piper model: {e}")
            raise e

        print("AI Brain + Voice Ready.")

        self.running = True
        self.capture_requested = False

    def on_press(self, key):
        try:
            if hasattr(key, 'char'):
                if key.char == 'c':
                    self.capture_requested = True
                elif key.char == 'q':
                    self.running = False
        except AttributeError:
            pass

    def run(self):
        print("Live Stream Active. Press 'c' to ask Reachy what it sees. Press 'q' to quit.")
        
        listener = keyboard.Listener(on_press=self.on_press)
        listener.start()

        while self.running:
            # OBTAIN IMAGE FROM REACHY'S EYES
            frame, _ = self.reachy.cameras.teleop.get_frame(CameraView.LEFT)

            if frame is not None:
                cv2.imshow("Reachy's Vision", frame)
            
            cv2.waitKey(1) 

            if self.capture_requested:
                print("\n[Processing image...]")
                self.process_and_speak(frame)
                self.capture_requested = False

        listener.stop()

    def process_and_speak(self, frame):
        # 2. PROCESS IMAGE USING VLM
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = PILImage.fromarray(rgb_frame)
        
        messages = [{
            "role": "user",
            "content": [
                {"type": "image", "image": pil_image},
                {"type": "text", "text": "Use two sentences to tell me what you see in front of you. Also try to make it sound funny and throw some jokes in there."},
            ],
        }]

        text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
        
        inputs = self.processor(text=[text], images=image_inputs, videos=video_inputs, padding=True, return_tensors="pt").to(self.device)

        generated_ids = self.model.generate(**inputs, max_new_tokens=300)
        generated_ids_trimmed = [out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)]
        output_text = self.processor.batch_decode(generated_ids_trimmed, skip_special_tokens=True)[0]

        print(f"Reachy says: {output_text}")

        try:
            audio_file = "reachy_speech.wav"
            
            with wave.open(audio_file, "wb") as wav_file:
                self.voice.synthesize_wav(output_text, wav_file)

            # Upload to Reachy and play
            self.reachy.audio.upload_audio_file(audio_file)
            self.reachy.audio.play_audio_file(audio_file)
            

            time.sleep(6) 
            os.remove(audio_file)
        except Exception as e:
            print(f"Audio Error: {e}")

    def shutdown(self):
        cv2.destroyAllWindows()
        self.reachy.disconnect()

if __name__ == '__main__':
    bot = ReachyAIVoiceBot()
    try:
        bot.run()
    finally:
        bot.shutdown()