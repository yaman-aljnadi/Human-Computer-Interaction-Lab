import torch
from PIL import Image as PILImage
from transformers import AutoModelForCausalLM, AutoTokenizer
from openai import OpenAI
import json
import config

class Brain:
    def __init__(self):
        self.device = config.DEVICE
        
        # --- VLM SETUP (Moondream) ---
        print(f"[Brain] Loading Eyes ({config.QWEN_MODEL_ID})...")
        self.vlm = AutoModelForCausalLM.from_pretrained(
            config.QWEN_MODEL_ID, 
            trust_remote_code=True,
            torch_dtype=torch.float16,
            device_map={"": self.device}
        )
        self.vlm_tokenizer = AutoTokenizer.from_pretrained(config.QWEN_MODEL_ID)
        
        # --- LLM SETUP ---
        print(f"[Brain] Loading Mind ({config.OPENAI_LLM_MODEL})...")
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)
        
        self.history = []
        self.max_history = 20 

        # Define the tools (Capabilities) the LLM has
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "see_environment",
                    "description": "Use this tool ONLY when the user asks to look at something, describe the scene, or identify objects visually.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "focus": {
                                "type": "string",
                                "description": "What specific object to look for. If general, use 'describe the scene'."
                            }
                        },
                        "required": ["focus"],
                    },
                }
            }
        ]

        self.system_prompt = (
            "You are Reachy, a helpful humanoid robot assistant. "
            "Keep answers short, unless user asks for a detailed answer."
            # "Start sentences with emotion tags: [HAPPY], [NEUTRAL], [CONFUSED], [EXCITED]. "
            "If the user shows you something or ask you for visuals, ALWAYS use the 'see_environment' tool."
            "Keep your responses as close to human interaction as possible and don't make it feel robotic, like try to avoid phrases that will make you sound like a robot"
        )

    def _run_vlm(self, image_frame, prompt_focus):
        """Internal helper to run Moondream without clearing cache aggressively."""
        try:
            rgb_frame = image_frame[:, :, ::-1]
            pil_image = PILImage.fromarray(rgb_frame)
            
            # Moondream specific prompt wrapper
            enc_image = self.vlm.encode_image(pil_image)
            answer = self.vlm.answer_question(enc_image, prompt_focus, self.vlm_tokenizer)
            return answer
        except Exception as e:
            print(f"VLM Error: {e}")
            return "Error: Camera malfunction."

    def think(self, user_text, get_frame_callback):
        """
        Main logic loop.
        get_frame_callback: A function passed from main.py that returns the current CV2 frame.
        """
        # 1. Update History
        self.history.append({"role": "user", "content": user_text})
        if len(self.history) > self.max_history * 2:
            self.history = self.history[-self.max_history * 2:]

        messages = [{"role": "system", "content": self.system_prompt}] + self.history

        # 2. First API Call (Does the LLM want to talk or see?)
        try:
            response = self.client.chat.completions.create(
                model=config.OPENAI_LLM_MODEL,
                messages=messages,
                tools=self.tools,
                tool_choice="auto", 
                temperature=0.7
            )
            
            response_message = response.choices[0].message

            # 3. Check for Tool Calls (The "Visual" Trigger)
            tool_calls = response_message.tool_calls
            
            if tool_calls:
                print(f"[Brain] Logic decided to SEE. invoking VLM...")
                
                # Append the LLM's "intent to call tool" to history (Required by OpenAI API)
                messages.append(response_message) 

                for tool_call in tool_calls:
                    if tool_call.function.name == "see_environment":
                        # 1. Parse arguments (what is it looking for?)
                        args = json.loads(tool_call.function.arguments)
                        focus_prompt = args.get("focus", "Describe the scene")
                        
                        # 2. GET IMAGE NOW (Fresh capture)
                        frame = get_frame_callback()
                        
                        if frame is not None:
                            # 3. RUN VLM
                            visual_description = self._run_vlm(frame, focus_prompt)
                            print(f"[VLM Result] {visual_description}")
                        else:
                            visual_description = "Error: I could not access my camera."

                        # 4. Feed result back to LLM
                        messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": "see_environment",
                            "content": visual_description,
                        })

                # 5. Second API Call (Synthesize the Answer)
                final_response = self.client.chat.completions.create(
                    model=config.OPENAI_LLM_MODEL,
                    messages=messages
                )
                answer_text = final_response.choices[0].message.content

            else:
                # Normal text conversation
                answer_text = response_message.content

            # 6. Save and Return
            self.history.append({"role": "assistant", "content": answer_text})
            return self._parse_emotion(answer_text)

        except Exception as e:
            print(f"[Brain Error] {e}")
            return "I am having a headache.", "sad"

    def _parse_emotion(self, text):
        import re
        emotion = "neutral"
        clean_text = text
        match = re.match(r"\[(HAPPY|SAD|EXCITED|NEUTRAL|CONFUSED|ANGRY)\]\s*(.*)", text, re.IGNORECASE | re.DOTALL)
        if match:
            emotion = match.group(1).lower()
            clean_text = match.group(2).strip()
        return clean_text, emotion