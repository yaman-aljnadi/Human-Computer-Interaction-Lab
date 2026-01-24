import torch
import cv2
import time
import numpy as np
from PIL import Image as PILImage

# Qwen Imports
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info

# Reachy 2 Imports
from reachy2_sdk import ReachySDK
from reachy2_sdk.media.camera import CameraView

print(f"PyTorch Version: {torch.__version__}")
print(f"CUDA Available: {torch.cuda.is_available()}")

class ReachyQwenViewer:
    def __init__(self, reachy_ip='192.168.50.241'): # Change IP if needed
        print("Connecting to Reachy...")
        self.reachy = ReachySDK(host=reachy_ip)
        
        # Ensure cameras are initialized
        if not self.reachy.is_connected():
            raise ConnectionError("Could not connect to Reachy 2.")
            
        print("Loading Qwen Model... (This may take a moment)")
        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"

        try:
            self.model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                "Qwen/Qwen2.5-VL-3B-Instruct",
                torch_dtype=torch.bfloat16,
                attn_implementation="flash_attention_2",
                device_map="auto",
            )
            self.processor = AutoProcessor.from_pretrained("Qwen/Qwen2.5-VL-3B-Instruct", use_fast=False)
            print('Model Loaded Successfully.')
        except Exception as e:
            print(f"Failed to load model: {e}")
            raise e

    def run_vision_loop(self):
        print("Starting Vision Loop... Press 'q' in the window to exit, or 'c' to capture and ask Qwen.")
        
        while True:
            # 1. Get the latest frame from the Left Teleop Camera
            # The SDK returns (frame, timestamp)
            frame, _ = self.reachy.cameras.teleop.get_frame(CameraView.LEFT)

            if frame is None:
                print("Warning: Received empty frame")
                time.sleep(0.1)
                continue

            # 2. Display the live feed
            cv2.imshow("Reachy 2 Left Eye", frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                print("Quitting viewer...")
                break
            elif key == ord('c'):
                print("Capturing frame for Qwen...")
                self.process_with_qwen(frame)

    def process_with_qwen(self, frame):
        try:
            # Reachy SDK returns BGR frames, just like OpenCV
            # We convert to RGB for PIL and the AI model
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = PILImage.fromarray(rgb_frame)
            
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image", 
                            "image": pil_image, 
                        },
                        {"type": "text", "text": "Can you tell me what you see? And return everything in a list format"},
                    ],
                }
            ]

            text = self.processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            
            image_inputs, video_inputs = process_vision_info(messages)
            
            inputs = self.processor(
                text=[text],
                images=image_inputs,
                videos=video_inputs,
                padding=True,
                return_tensors="pt",
            )
            
            inputs = inputs.to(self.device)

            generated_ids = self.model.generate(**inputs, max_new_tokens=128)
            
            generated_ids_trimmed = [
                out_ids[len(in_ids) :] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
            ]
            
            output_text = self.processor.batch_decode(
                generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
            )[0]

            print(f"\n[Qwen (Reachy's Perspective)]: {output_text}\n")

        except Exception as e:
            print(f'Error Details: {e}')

    def shutdown(self):
        cv2.destroyAllWindows()
        self.reachy.disconnect()

if __name__ == '__main__':
    viewer = ReachyQwenViewer()
    try:
        viewer.run_vision_loop()
    except KeyboardInterrupt:
        pass
    finally:
        viewer.shutdown()