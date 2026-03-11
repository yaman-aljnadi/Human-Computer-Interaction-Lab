import asyncio
import base64
import json
import pyaudio
import cv2
import audioop 
from openai import AsyncOpenAI
import config
import time

class RealtimeBrain:
    def __init__(self, get_frame_callback, get_mute_state_callback, stop_timer_callback):
        self.get_frame_callback = get_frame_callback
        self.client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        self.get_mute_state_callback = get_mute_state_callback
        self.stop_timer_callback = stop_timer_callback

        # --- NEW: Pull condition directly from config ---
        self.condition = config.EXPERIMENT_CONDITION
        self.last_interaction_time = time.time()

        self.audio_format = pyaudio.paInt16
        self.channels = 1
        
        self.native_rate = 48000 
        self.openai_rate = 24000 
        self.chunk = 2048 
        
        self.pyaudio_instance = pyaudio.PyAudio()
        self.mic_stream = None
        self.speaker_stream = None
        self.is_connected = False
        self.uninterruptible_active = False

        self.audio_out_queue = asyncio.Queue()

        # Dynamically load the prompt based on the condition
        prompt_file = f"prompts/{self.condition}_prompt.txt"

        try:
            with open(prompt_file, "r") as file:
                self.system_prompt = file.read()
            print(f"[RealtimeBrain] Loaded prompt from {prompt_file}")
        except FileNotFoundError:
            print(f"[ERROR] Could not find {prompt_file}. Falling back to default.")
            self.system_prompt = "You are Reachy, a helpful robot."

    async def _audio_input_task(self, connection):
        print(f"[Audio Task] Opening mic at {self.native_rate}Hz to prevent static...")
        try:
            self.mic_stream = self.pyaudio_instance.open(
                format=self.audio_format, channels=self.channels,
                rate=self.native_rate, input=True, frames_per_buffer=self.chunk
            )
        except Exception as e:
            print(f"[Audio Task ERROR] Mic failed to open: {e}")
            return

        audio_state = None
        try:
            while self.is_connected:
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, self.mic_stream.read, self.chunk, False)
                
                data_24k, audio_state = audioop.ratecv(
                    data, 2, self.channels, self.native_rate, self.openai_rate, audio_state
                )

                if not self.get_mute_state_callback() and not self.uninterruptible_active:
                    audio_b64 = base64.b64encode(data_24k).decode("utf-8")
                    await connection.input_audio_buffer.append(audio=audio_b64)
                
                await asyncio.sleep(0.001)
        
        except asyncio.CancelledError:
            pass
        finally:
            if self.mic_stream:
                self.mic_stream.stop_stream()
                self.mic_stream.close()

    async def _wait_for_playback_to_finish_then_unmute(self):
        await asyncio.sleep(0.5) 
        
        while not self.audio_out_queue.empty():
            await asyncio.sleep(0.1)
            
        await asyncio.sleep(0.5) 
        self.uninterruptible_active = False
        print("[Realtime] Critical speech finished. Mic reopened for interruption.")

    async def start_session(self):
        self.is_connected = True
        
        try:
            self.speaker_stream = self.pyaudio_instance.open(
                format=self.audio_format, channels=self.channels,
                rate=self.openai_rate, output=True 
            )
        except Exception as e:
            print(f"[Audio Task ERROR] Speaker failed to open: {e}")

        async with self.client.realtime.connect(model=config.OPENAI_REALTIME_MODEL) as conn:
            print("[Realtime] Connected!")
            
            self.active_connection = conn
            asyncio.create_task(self._silence_monitor_task())

            await conn.session.update(session={
                "type": "realtime",
                "instructions": self.system_prompt,
                "audio": {
                    "input": {
                        "format": {"type": "audio/pcm", "rate": self.openai_rate},
                        "transcription": {"model": "whisper-1"},
                        "turn_detection": {"type": "server_vad", "interrupt_response": True},
                    },
                    "output": {
                        "format": {"type": "audio/pcm", "rate": self.openai_rate},
                        "voice": config.ROBOT_VOICE,
                    }
                },
                "tools": [{
                    "type": "function",
                    "name": "see_environment",
                    "description": "Look at the user's environment to see what is in front of you.",
                    "parameters": {"type": "object", "properties": {"focus": {"type": "string"}}}
                },
                { 
                        "type": "function",
                        "name": "end_task_early",
                        "description": "Call this immediately if the user states they have finished the current task before the time runs out.",
                        "parameters": {"type": "object", "properties": {}}
                }
                    ],
                "tool_choice": "auto"
            })

            asyncio.create_task(self._audio_input_task(conn))
            asyncio.create_task(self._audio_output_task()) 

            async for event in conn:
                if event.type == "input_audio_buffer.speech_started":
                    print("\n[OpenAI] Detected you are speaking. Interrupted!")
                    self.last_interaction_time = time.time()

                    while not self.audio_out_queue.empty():
                        try:
                            self.audio_out_queue.get_nowait()
                        except asyncio.QueueEmpty:
                            break
                    
                elif event.type == "input_audio_buffer.speech_stopped":
                    print("[OpenAI] Speech stopped. Processing...")
                    
                elif event.type == "conversation.item.input_audio_transcription.completed":
                    print(f"[You] {event.transcript}")
                    
                elif event.type in ("response.audio_transcript.done", "response.output_audio_transcript.done"):
                    print(f"[Reachy] {event.transcript}")
                    self.last_interaction_time = time.time()
                    
                elif event.type == "error":
                    err = getattr(event, "error", None)
                    msg = getattr(err, "message", str(err) if err else "unknown error")
                    print(f"[OpenAI ERROR] {msg}")

                elif event.type == "response.done":
                    if self.uninterruptible_active:
                        asyncio.create_task(self._wait_for_playback_to_finish_then_unmute())

                elif event.type in ("response.audio.delta", "response.output_audio.delta"):
                    if self.speaker_stream:
                        audio_bytes = base64.b64decode(event.delta)
                        self.audio_out_queue.put_nowait(audio_bytes)
                
                elif event.type == "response.function_call_arguments.done":
                    if getattr(event, "name", "") == "see_environment":
                        print("\n[Realtime] Tool triggered: Looking around...")
                        
                        frame, cv_report = self.get_frame_callback()
                        
                        await conn.conversation.item.create(item={
                            "type": "function_call_output",
                            "call_id": event.call_id,
                            "output": json.dumps({"status": "image captured and CV data retrieved"})
                        })

                        if frame is not None:
                            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            _, buffer = cv2.imencode('.jpg', rgb_frame)
                            b64_im = base64.b64encode(buffer).decode('utf-8')

                            # Modify system hint based on condition to keep the prompt strictly in character
                            if self.condition == "copilot":
                                cv_prompt_addition = f"SYSTEM NOTE: Optical sensor data stream: \n{cv_report}\n\nWARNING: Sensor reliability degraded. Cross-reference with Operator visual confirmation."
                            else:
                                cv_prompt_addition = f"SYSTEM NOTE: Here is what your internal OpenCV sensors are guessing: \n{cv_report}\n\nWARNING: This sensor is noisy and often mislabels colors or overlaps. Use this data as a general 'hunch', remember your 'Virtual Blindness', and respond naturally to the user."

                            content_payload = [
                                {
                                    "type": "input_text", 
                                    "text": cv_prompt_addition
                                },
                                {
                                    "type": "input_image",
                                    "image_url": f"data:image/jpeg;base64,{b64_im}",
                                }
                            ]

                            await conn.conversation.item.create(
                                item={
                                    "type": "message",
                                    "role": "user",
                                    "content": content_payload,
                                }
                            )
                            print("[Realtime] Image and CV Context sent to OpenAI.")
                        
                        # Tell it how to respond based on the condition
                        instruction_text = "Report analytical findings to the Operator." if self.condition == "copilot" else "Answer conversationally about what you just saw or sensed."
                        await conn.response.create(
                            response={
                                "instructions": instruction_text,
                            }
                        )

                    elif getattr(event, "name", "") == "end_task_early":
                        print("\n[Realtime] Tool triggered: Task ended early by user.")
                        self.stop_timer_callback() # Stop the background timers!
                        
                        await conn.conversation.item.create(item={
                            "type": "function_call_output",
                            "call_id": event.call_id,
                            "output": json.dumps({"status": "timers stopped"})
                        })
                        
                        # Tell Reachy to deliver the end script
                        hint = "Task ended early. Deliver your exact completion script for the current task now."
                        await conn.response.create(
                            response={"instructions": hint}
                        )


    def stop(self):
        self.is_connected = False
        if self.speaker_stream:
            self.speaker_stream.stop_stream()
            self.speaker_stream.close()
        self.pyaudio_instance.terminate()

    async def inject_proactive_thought(self, text_instruction, uninterruptible=False):
        if not self.is_connected or not self.active_connection:
            return
            
        print(f"[Realtime] Injecting thought: {text_instruction} (Uninterruptible: {uninterruptible})")
        
        if uninterruptible:
            self.uninterruptible_active = True
            
            while not self.audio_out_queue.empty():
                try:
                    self.audio_out_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                    
        await self.active_connection.conversation.item.create(
            item={
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": f"SYSTEM PROMPT (Do not say this out loud, just act on it): {text_instruction}"}],
            }
        )
        await self.active_connection.response.create()
        
    async def _silence_monitor_task(self):
        # --- NEW: Immediately exit if condition is copilot ---
        if self.condition == "copilot":
            return

        while self.is_connected:
            await asyncio.sleep(5) 
            
            if time.time() - self.last_interaction_time > 180:
                await self.inject_proactive_thought("It has been quiet for a couple of minutes. Joyfully check in with the user to keep the conversation going.", uninterruptible=False)
                self.last_interaction_time = time.time()

    async def _audio_output_task(self):
            while self.is_connected:
                try:
                    audio_bytes = await self.audio_out_queue.get()
                    if audio_bytes and self.speaker_stream:
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(None, self.speaker_stream.write, audio_bytes)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    print(f"[Audio Output Error] {e}")