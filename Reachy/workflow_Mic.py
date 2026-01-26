import torch
import cv2
import time
import os
import wave
import threading
import re
import numpy as np
import speech_recognition as sr
import whisper  # OpenAI Whisper

from PIL import Image as PILImage
from pynput import keyboard 

from piper import PiperVoice

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
            
        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        self.model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            "Qwen/Qwen2.5-VL-3B-Instruct",
            torch_dtype=torch.bfloat16,
            device_map="auto",
        )
        self.processor = AutoProcessor.from_pretrained("Qwen/Qwen2.5-VL-3B-Instruct")
        
        self.model_path = "piper_audios/en_US-joe-medium.onnx" 
        print(f"Loading Piper Voice Model: {self.model_path}...")
        try:
            self.voice = PiperVoice.load(self.model_path, use_cuda=torch.cuda.is_available())
        except Exception as e:
            print(f"Failed to load Piper model: {e}")
            raise e

        print("Loading Whisper Model...")
        self.whisper_model = whisper.load_model("base.en") 
        
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        
        self.running = True
        self.is_processing = False  
        self.pending_prompt = None  
        
        self.conversation_mode = False

        print("AI Brain + Voice + Ears Ready.")

    def listen_loop(self):
        """
        Runs in a separate thread. Continuously listens to the mic.
        """
        print("Listening thread started...")
        
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source)
            
            while self.running:
                if self.is_processing:
                    time.sleep(0.5)
                    continue

                try:
                    print("Listening...")
                    audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
                    
                    with open("temp_command.wav", "wb") as f:
                        f.write(audio.get_wav_data())

                    result = self.whisper_model.transcribe("temp_command.wav")
                    text = result["text"].lower().strip()
                    
                    if text:
                        print(f"User said: '{text}'")
                        self.check_keywords(text)

                except sr.WaitTimeoutError:
                    pass 
                except Exception as e:
                    print(f"Error in listener: {e}")

    # Completely refactored keyword checker
    def check_keywords(self, text):
        """
        Router for voice commands. Handles Mode Switching and Specific Actions.
        """

        # Exit Conversation
        if "stop chatting" in text or "stop conversation" in text:
            print(">>> Switching to COMMAND MODE")
            self.conversation_mode = False
            self.pending_prompt = "Say precisely: 'Okay, I am back to command mode.'"
            self.is_processing = True
            return


        if self.conversation_mode:
            print(f">>> Conversational Input: {text}")
            self.pending_prompt = f"You are having a casual conversation. The user said: '{text}'. Reply naturally based on what you see in the image."
            self.is_processing = True
            return

        
        # Enable Conversation
        if "let's chat" in text or "start conversation" in text:
            print("Switching to CONVERSATION MODE")
            self.conversation_mode = True
            self.pending_prompt = "Say precisely: 'I am ready to chat! What is on your mind?'"
            self.is_processing = True

        # Describe Scene
        elif "tell me what you see" in text or "describe" in text:
            print("Trigger: General Description")
            self.pending_prompt = "Use two sentences to tell me what you see. Make it funny."
            self.is_processing = True

        # Find Object
        elif "find" in text and "for me" in text:
            match = re.search(r"find (.*?) for me", text)
            if match:
                object_to_find = match.group(1)
                print(f"Trigger: Finding '{object_to_find}'")
                self.pending_prompt = f"I am looking for {object_to_find}. Tell me if you see it and where it is in the image."
                self.is_processing = True

        elif "look at me" in text or "look forward" in text:
            print("Head Movement")
            self.is_processing = True 
            threading.Thread(target=self.perform_head_reset).start()

    # physical movement
    def perform_head_reset(self):
        """Moves Reachy's head to look forward, then speaks."""
        try:
            print("Moving head...")
            self.reachy.head.look_at(x=1.0, y=0.0, z=0.0, duration=1.0)
            
            self.speak_direct("I am looking forward now.")
        except Exception as e:
            print(f"Head move error: {e}")
        finally:
            self.is_processing = False

    
    def speak_direct(self, text):
        try:
            audio_file = "system_speech.wav"
            with wave.open(audio_file, "wb") as wav_file:
                self.voice.synthesize_wav(text, wav_file)
            self.reachy.audio.upload_audio_file(audio_file)
            self.reachy.audio.play_audio_file(audio_file)
            time.sleep(3) 
            if os.path.exists(audio_file):
                os.remove(audio_file)
        except Exception as e:
            print(f"TTS Error: {e}")

    def run(self):
        print("Live Stream Active. Talk to Reachy!")
        
        listener_thread = threading.Thread(target=self.listen_loop)
        listener_thread.daemon = True 
        listener_thread.start()

        while self.running:
            # OBTAIN IMAGE FROM REACHY'S EYES
            frame, _ = self.reachy.cameras.teleop.get_frame(CameraView.LEFT)

            # Just to check in what mode he is 
            if frame is not None:
                if self.conversation_mode:
                    cv2.putText(frame, "MODE: CHAT", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                else:
                    cv2.putText(frame, "MODE: COMMAND", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

                cv2.imshow("Reachy's Vision", frame)
            
            key = cv2.waitKey(1)
            if key == ord('q'):
                self.running = False

            if self.pending_prompt is not None and frame is not None:
                print("\n[Processing Request...]")
                self.process_and_speak(frame, self.pending_prompt)
                
                self.pending_prompt = None
                self.is_processing = False 
                print("[Ready to listen again]")

        cv2.destroyAllWindows()
        self.reachy.disconnect()

    def process_and_speak(self, frame, text_prompt):
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = PILImage.fromarray(rgb_frame)
        
        messages = [{
            "role": "user",
            "content": [
                {"type": "image", "image": pil_image},
                {"type": "text", "text": text_prompt},
            ],
        }]

        text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
        
        inputs = self.processor(text=[text], images=image_inputs, videos=video_inputs, padding=True, return_tensors="pt").to(self.device)

        generated_ids = self.model.generate(**inputs, max_new_tokens=150)
        generated_ids_trimmed = [out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)]
        output_text = self.processor.batch_decode(generated_ids_trimmed, skip_special_tokens=True)[0]

        print(f"Reachy says: {output_text}")

        try:
            audio_file = "reachy_speech.wav"
            
            with wave.open(audio_file, "wb") as wav_file:
                self.voice.synthesize_wav(output_text, wav_file)

            self.reachy.audio.upload_audio_file(audio_file)
            self.reachy.audio.play_audio_file(audio_file)
            
            # Wait for audio to finish
            time.sleep(10) 
            
            if os.path.exists(audio_file):
                os.remove(audio_file)
                
        except Exception as e:
            print(f"Audio Error: {e}")

if __name__ == '__main__':
    bot = ReachyAIVoiceBot()
    bot.run()