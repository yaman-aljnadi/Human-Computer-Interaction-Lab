import torch
from PIL import Image as PILImage
from transformers import AutoModelForCausalLM, AutoTokenizer, Qwen2_5_VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info
import config

class Brain:
    def __init__(self):
        self.device = config.DEVICE
        
        # 1. Load the Eyes (VLM)
        print("Loading Eyes (VLM)...")
        self.vlm = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            config.QWEN_MODEL_ID,
            torch_dtype=torch.bfloat16,
            device_map="auto", # Be careful with VRAM here
        )
        self.vlm_processor = AutoProcessor.from_pretrained(config.QWEN_MODEL_ID)

        # 2. Load the Mind (LLM)
        print("Loading Mind (LLM)...")
        self.llm = AutoModelForCausalLM.from_pretrained(
            config.LLM_MODEL_ID,
            torch_dtype=torch.bfloat16,
            device_map="auto"
        )
        self.llm_tokenizer = AutoTokenizer.from_pretrained(config.LLM_MODEL_ID)
        
        print("Brain Ready.")

    def see(self, cv2_frame):
        """
        VLM TASK: strictly describes the image. No personality.
        """
        rgb_frame = cv2_frame[:, :, ::-1]
        pil_image = PILImage.fromarray(rgb_frame)

        # We ask the VLM a purely descriptive question
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
        """
        LLM TASK: Takes user text + optional visual context and generates the final answer.
        """
        
        system_prompt = "You are Reachy, a helpful robot assistant. "
        
        if visual_context:
            system_prompt += f"You have just looked at the world. Your visual system reports: '{visual_context}'. "
            system_prompt += "Answer the user's question based on this visual information."
        else:
            system_prompt += "Chat naturally with the user."

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text}
        ]

        text = self.llm_tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        model_inputs = self.llm_tokenizer([text], return_tensors="pt").to(self.device)

        generated_ids = self.llm.generate(model_inputs.input_ids, max_new_tokens=100)
        generated_ids = [output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)]

        response = self.llm_tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
        return response