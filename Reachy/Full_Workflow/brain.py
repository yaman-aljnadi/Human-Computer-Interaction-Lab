import torch
from PIL import Image as PILImage
from transformers import AutoModelForCausalLM, AutoTokenizer
# from qwen_vl_utils import process_vision_info
import re
import config
import gc


class Brain:
    def __init__(self):
        self.device = config.DEVICE
        
        # --- (VLM) Part: MOONDREAM SETUP ---
        print(f"Loading Eyes (VLM: {config.QWEN_MODEL_ID})...")
        # Moondream runs as a standard AutoModelForCausalLM but needs trust_remote_code=True
        self.vlm = AutoModelForCausalLM.from_pretrained(
            config.QWEN_MODEL_ID, 
            trust_remote_code=True,
            torch_dtype=torch.float16, # Moondream prefers float16
            device_map={"": self.device} # Explicit device map helps Moondream
        )
        self.vlm_tokenizer = AutoTokenizer.from_pretrained(config.QWEN_MODEL_ID)
        
        # --- (LLM) Part: QWEN SETUP ---
        print(f"Loading Mind (LLM: {config.LLM_MODEL_ID})...")
        self.llm = AutoModelForCausalLM.from_pretrained(
            config.LLM_MODEL_ID,
            torch_dtype=torch.bfloat16,
            device_map="auto"
        )
        self.llm_tokenizer = AutoTokenizer.from_pretrained(config.LLM_MODEL_ID)


        print("Brain Ready.")

    def see(self, cv2_frame, specific_prompt=None):
        torch.cuda.empty_cache()
        gc.collect()

        rgb_frame = cv2_frame[:, :, ::-1]
        pil_image = PILImage.fromarray(rgb_frame)

        if specific_prompt:
            prompt = f"Answer this question based on the image: {specific_prompt}"
        else:
            prompt = "Describe everything you see in this image in detail."
        
        try:
            # 1. Encode the image using Moondream's custom method
            enc_image = self.vlm.encode_image(pil_image)
            
            # 2. Ask the question
            # Moondream has a helper method .answer_question()
            answer = self.vlm.answer_question(enc_image, prompt, self.vlm_tokenizer)
            
            return answer

        except Exception as e:
            print(f"VLM Error: {e}")
            return "I couldn't see anything clearly."

    def think(self, user_text, visual_context=None):
        # 1. Construct System Prompt with Emotion Instructions
        system_prompt = (
            "Your name is Reachy and you are a humanoid robot assistant. "
            "Keep your answers short limited to 2 sentences and make them sound funny"
            "Don't repeat the previos prompts or mention them again, just give a direct answer."
            # "You have emotions. When you reply, start your sentence with an emotion tag like [HAPPY], [SAD], [EXCITED], [CONFUSED], or [NEUTRAL]. "
            # "Example: '[HAPPY] I would love to help you with that!' "
            # "Example: '[SAD] I am sorry, I cannot do that.' "
        )
        
        if visual_context:
            system_prompt += f"A VLM has seen this: '{visual_context}'. Answer based on this. DON'T SAY THE WORD VLM in your response."

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text}
        ]

        text = self.llm_tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        model_inputs = self.llm_tokenizer([text], return_tensors="pt").to(self.device)

        generated_ids = self.llm.generate(model_inputs.input_ids, max_new_tokens=70)
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