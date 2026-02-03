import torch
from PIL import Image as PILImage
from transformers import AutoModelForCausalLM, AutoTokenizer, Qwen2_5_VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info
import re
import config

class Brain:
    def __init__(self):
        self.device = config.DEVICE
        
        # (VLM) Part
        print("Loading Eyes (VLM)...")
        self.vlm = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            config.QWEN_MODEL_ID,
            torch_dtype=torch.bfloat16,
            device_map="auto",
        )
        self.vlm_processor = AutoProcessor.from_pretrained(config.QWEN_MODEL_ID)

        # (LLM) part
        print("Loading Mind (LLM)...")
        self.llm = AutoModelForCausalLM.from_pretrained(
            config.LLM_MODEL_ID,
            torch_dtype=torch.bfloat16,
            device_map="auto"
        )
        self.llm_tokenizer = AutoTokenizer.from_pretrained(config.LLM_MODEL_ID)
        
        print("Brain Ready.")

    def see(self, cv2_frame, specific_prompt=None):
        rgb_frame = cv2_frame[:, :, ::-1]
        pil_image = PILImage.fromarray(rgb_frame)

        if specific_prompt:
            prompt = f"Answer this question based on the image: {specific_prompt}"
        else:
            prompt = "Describe everything you see in this image in detail."
        
        messages = [{
            "role": "user",
            "content": [
                {"type": "image", "image": pil_image},
                {"type": "text", "text": prompt},
            ],
        }]

        text = self.vlm_processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
        
        inputs = self.vlm_processor(
            text=[text], 
            images=image_inputs, 
            videos=video_inputs, 
            padding=True, 
            return_tensors="pt"
        ).to(self.device)

        generated_ids = self.vlm.generate(**inputs, max_new_tokens=100)
        generated_ids_trimmed = [out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)]
        
        raw_description = self.vlm_processor.batch_decode(generated_ids_trimmed, skip_special_tokens=True)[0]
        return raw_description

    def think(self, user_text, visual_context=None):
        # 1. Construct System Prompt with Emotion Instructions
        system_prompt = (
            "You are Reachy, a helpful robot assistant. "
            "You have emotions. When you reply, start your sentence with an emotion tag like [HAPPY], [SAD], [EXCITED], [CONFUSED], or [NEUTRAL]. "
            "Example: '[HAPPY] I would love to help you with that!' "
            "Example: '[SAD] I am sorry, I cannot do that.' "
        )
        
        if visual_context:
            system_prompt += f"A VLM has seen this: '{visual_context}'. Answer based on this. DON'T MENTION THE VLM."

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text}
        ]

        text = self.llm_tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        model_inputs = self.llm_tokenizer([text], return_tensors="pt").to(self.device)

        generated_ids = self.llm.generate(model_inputs.input_ids, max_new_tokens=100)
        generated_ids = [output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)]

        raw_response = self.llm_tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
        
        # 2. Parse Emotion Tag
        emotion = "neutral" # Default
        clean_text = raw_response

        # Regex to find [TAG] at the start
        match = re.match(r"\[(HAPPY|SAD|EXCITED|NEUTRAL|CONFUSED|ANGRY)\]\s*(.*)", raw_response, re.IGNORECASE | re.DOTALL)
        
        if match:
            emotion = match.group(1).lower()
            clean_text = match.group(2)
            print(f"[Brain] Detected Emotion: {emotion}")
        else:
            print("[Brain] No emotion tag detected, defaulting to neutral.")

        return clean_text, emotion