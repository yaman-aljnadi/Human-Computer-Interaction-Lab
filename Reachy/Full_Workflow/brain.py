import torch
from PIL import Image as PILImage
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info
import config

class Brain:
    def __init__(self):
        print("Loading Qwen VLM Brain...")
        self.model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            config.QWEN_MODEL_ID,
            torch_dtype=torch.bfloat16,
            device_map="auto",
        )
        self.processor = AutoProcessor.from_pretrained(config.QWEN_MODEL_ID)
        self.device = config.DEVICE
        print("Brain Ready.")

    def think(self, cv2_frame, text_prompt):
        """Takes a CV2 frame and a prompt, returns a text response."""
        # Convert CV2 BGR to RGB for PIL
        rgb_frame = cv2_frame[:, :, ::-1] # Faster than cvtColor
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
        
        inputs = self.processor(
            text=[text], 
            images=image_inputs, 
            videos=video_inputs, 
            padding=True, 
            return_tensors="pt"
        ).to(self.device)

        generated_ids = self.model.generate(**inputs, max_new_tokens=150)
        generated_ids_trimmed = [out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)]
        
        return self.processor.batch_decode(generated_ids_trimmed, skip_special_tokens=True)[0]