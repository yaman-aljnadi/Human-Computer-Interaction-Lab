import torch
import cv2
import time
import os
from gtts import gTTS
from PIL import Image as PILImage
from pynput import keyboard # <-- NEW IMPORT

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
        print("AI Brain Ready.")

        # --- NEW: Setup state variables for the keyboard listener ---
        self.running = True
        self.capture_requested = False

    # --- NEW: Keyboard listener functions ---
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
        
        # --- NEW: Start the background keyboard listener ---
        listener = keyboard.Listener(on_press=self.on_press)
        listener.start()

        while self.running:
            # 1. OBTAIN IMAGE FROM REACHY'S EYES
            frame, _ = self.reachy.cameras.teleop.get_frame(CameraView.LEFT)

            if frame is not None:
                cv2.imshow("Reachy's Vision", frame)
            
            # We still need waitKey(1) just to keep the video window refreshing
            cv2.waitKey(1) 

            # --- NEW: Check if 'c' was pressed globally ---
            if self.capture_requested:
                print("\n[Processing image...]")
                self.process_and_speak(frame)
                self.capture_requested = False # Reset flag

        # Cleanup after loop ends
        listener.stop()

    def process_and_speak(self, frame):
        # 2. PROCESS IMAGE USING VLM
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = PILImage.fromarray(rgb_frame)
        
        messages = [{
            "role": "user",
            "content": [
                {"type": "image", "image": pil_image},
                {"type": "text", "text": "Use two sentences to tell me what you see in front of you as if you are a friendly robot. Also try to make it sound funny and throw some jokes in there."},
            ],
        }]

        text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
        
        inputs = self.processor(text=[text], images=image_inputs, videos=video_inputs, padding=True, return_tensors="pt").to(self.device)

        generated_ids = self.model.generate(**inputs, max_new_tokens=60)
        generated_ids_trimmed = [out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)]
        output_text = self.processor.batch_decode(generated_ids_trimmed, skip_special_tokens=True)[0]

        print(f"Reachy says: {output_text}")

        try:
            audio_file = "reachy_speech.mp3"
            tts = gTTS(text=output_text, lang='en', tld='co.uk')
            tts.save(audio_file)
            self.reachy.audio.upload_audio_file(audio_file)
            self.reachy.audio.play_audio_file(audio_file)
            time.sleep(3) 
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