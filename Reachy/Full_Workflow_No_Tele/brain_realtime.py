import asyncio
import base64
import json
import wave
import pyaudio
import audioop
import time
import cv2
from openai import AsyncOpenAI
import config

class RealtimeBrainNonTeleop:
    def __init__(self, get_frame_callback, get_mute_state_callback, on_speech_ready_callback, on_dance_command_callback=None):
        self.get_frame_callback = get_frame_callback
        self.get_mute_state_callback = get_mute_state_callback
        self.on_speech_ready_callback = on_speech_ready_callback
        self.on_dance_command_callback = on_dance_command_callback
        
        self.client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        
        self.audio_format = pyaudio.paInt16
        self.channels = 1
        self.native_rate = 48000
        self.openai_rate = 24000
        self.chunk = 2048
        
        self.pyaudio_instance = pyaudio.PyAudio()
        self.mic_stream = None
        self.is_connected = False
        
        # Buffer to hold incoming audio chunks from OpenAI
        self.audio_response_buffer = bytearray()
        
        # --- UPDATE: Dynamic System Prompt based on Condition ---
        if config.EXPERIMENT_CONDITION == "crowd":
            self.system_prompt = (
                "You are Reachy, an enthusiastic, highly charismatic humanoid robot presenting to a large live audience. "
                "Keep your energy high, be incredibly cheerful, and feel free to throw in some lighthearted, family-friendly jokes or witty remarks. "
                "Your answers should be engaging but brief enough to keep the crowd entertained without rambling. "
                "If the user shows you something or asks you for visuals, ALWAYS use the 'see_environment' tool. "
                "If the audience asks you to dance, show a move, or perform, you MUST immediately call the 'perform_dance' tool. NEVER describe yourself dancing in text. "
                "Never act like a boring AI—you are a star performer on stage!"
            )
        else:
            # Load the corresponding text file to give Reachy context about the tasks
            prompt_file = f"prompts/{config.EXPERIMENT_CONDITION}_prompt.txt"
            try:
                with open(prompt_file, "r") as file:
                    base_prompt = file.read()
            except FileNotFoundError:
                print(f"[Warning] Could not find {prompt_file}. Falling back to default.")
                base_prompt = "You are Reachy."
            
            # Add the specific instruction for the Pre-Task face-to-face phase
            self.system_prompt = (
                f"{base_prompt}\n\n"
                "CRITICAL SYSTEM NOTE: You are currently in the PRE-TASK PHASE. "
                "The user is standing in front of you and is NOT wearing the VR headset yet. "
                "Do NOT start any tasks. Just chat with them socially and get to know them. "
                "If they ask about the tasks, you can use the knowledge above to answer briefly, but otherwise keep it casual."
            )

    async def _audio_input_task(self, connection):
        """Continuously streams local microphone to OpenAI."""
        try:
            self.mic_stream = self.pyaudio_instance.open(
                format=self.audio_format, channels=self.channels,
                rate=self.native_rate, input=True, frames_per_buffer=self.chunk
            )
        except Exception as e:
            print(f"[Mic Error] {e}")
            return

        audio_state = None
        try:
            while self.is_connected:
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, self.mic_stream.read, self.chunk, False)
                
                # Resample 48kHz mic to 24kHz for OpenAI
                data_24k, audio_state = audioop.ratecv(
                    data, 2, self.channels, self.native_rate, self.openai_rate, audio_state
                )
                
                # Only send audio if the user hasn't muted the robot via the UI
                if not self.get_mute_state_callback():
                    audio_b64 = base64.b64encode(data_24k).decode("utf-8")
                    await connection.input_audio_buffer.append(audio=audio_b64)
                    
                await asyncio.sleep(0.001)
        except asyncio.CancelledError:
            pass
        finally:
            if self.mic_stream:
                self.mic_stream.stop_stream()
                self.mic_stream.close()

    def _save_buffer_to_wav(self, filename=config.TEMP_OUTPUT_AUDIO):
        """Wraps the accumulated PCM16 bytes into a proper WAV file."""
        if len(self.audio_response_buffer) == 0:
            return False
            
        with wave.open(filename, 'wb') as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(self.pyaudio_instance.get_sample_size(self.audio_format))
            wav_file.setframerate(self.openai_rate)
            wav_file.writeframes(self.audio_response_buffer)
        
        self.audio_response_buffer.clear() 
        return True

    async def start_session(self):
        self.is_connected = True
        
        async with self.client.realtime.connect(model=config.OPENAI_REALTIME_MODEL) as conn:
            print("[Brain] Connected to Realtime API!")
            
            await conn.session.update(session={
                "type": "realtime",
                "instructions": self.system_prompt,
                "audio": {
                    "input": {
                        "format": {"type": "audio/pcm", "rate": self.openai_rate},
                        "transcription": {"model": "whisper-1"},
                        "turn_detection": {
                            "type": "server_vad", 
                            "interrupt_response": False,
                            # We can also add these if it's still too sensitive:
                            # "threshold": 0.6,
                            # "silence_duration_ms": 600
                        },
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
                        "name": "perform_dance",
                        "description": "Trigger this tool IMMEDIATELY when the user or audience asks you to dance, show a move, or perform.",
                        "parameters": {"type": "object", "properties": {}}
                    }
                ],
                "tool_choice": "auto"
            })

            intro_text = ""
            if config.EXPERIMENT_CONDITION == "embodied":
                intro_text = "Briefly introduce yourself to the user standing in front of you. Tell them you are Reachy, their AI partner for today, and you're excited to work with them. Ask them how they are doing."
            elif config.EXPERIMENT_CONDITION == "copilot":
                intro_text = "Briefly introduce yourself to the user standing in front of you. Tell them you are the AI Copilot who will be assisting them during the VR tasks today. Ask them how they are doing."
            elif config.EXPERIMENT_CONDITION == "crowd":
                intro_text = "Give a very quick, energetic welcome to the crowd!"
            
            if intro_text:
                await conn.conversation.item.create(
                    item={
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": f"SYSTEM PROMPT (Do not say this out loud, just act on it): {intro_text}"}]
                    }
                )
                await conn.response.create()

            asyncio.create_task(self._audio_input_task(conn))

            async for event in conn:
                if event.type == "input_audio_buffer.speech_started":
                    print("\n[Brain] Mic picked up audio...")
                    
                elif event.type == "input_audio_buffer.speech_stopped":
                    print("[Brain] Speech stopped. Generating response...")

                elif event.type == "conversation.item.input_audio_transcription.completed":
                    print(f"[User] {event.transcript}")
                
                    
                # Catch BOTH variations of the transcript event
                elif event.type in ("response.audio_transcript.done", "response.output_audio_transcript.done"):
                    print(f"[Reachy] {event.transcript}")
                    
                # Catch BOTH variations of the audio chunk event
                elif event.type in ("response.audio.delta", "response.output_audio.delta"):
                    # Append incoming chunks to memory
                    audio_bytes = base64.b64decode(event.delta)
                    self.audio_response_buffer.extend(audio_bytes)
                    
                # Catch ANY event that signifies the response is finished
                elif event.type in ("response.audio.done", "response.output_audio.done", "response.done"):
                    # Model finished talking. Save and play!
                    if len(self.audio_response_buffer) > 0:
                        success = self._save_buffer_to_wav(config.TEMP_OUTPUT_AUDIO)
                        if success:
                            self.on_speech_ready_callback(config.TEMP_OUTPUT_AUDIO)
                            
                # Catch errors so they don't fail silently
                elif event.type == "error":
                    err = getattr(event, "error", None)
                    msg = getattr(err, "message", str(err) if err else "unknown error")
                    print(f"[OpenAI ERROR] {msg}")

                elif event.type == "response.function_call_arguments.done":
                    
                    if getattr(event, "name", "") == "see_environment":
                        print("\n[Brain] Tool triggered: Looking around...")
                        
                        frame = self.get_frame_callback()
                        
                        await conn.conversation.item.create(item={
                            "type": "function_call_output",
                            "call_id": event.call_id,
                            "output": json.dumps({"status": "image captured"})
                        })

                        if frame is not None:
                            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            _, buffer = cv2.imencode('.jpg', rgb_frame)
                            b64_im = base64.b64encode(buffer).decode('utf-8')

                            await conn.conversation.item.create(
                                item={
                                    "type": "message",
                                    "role": "user",
                                    "content": [
                                        {"type": "input_text", "text": "Describe what you see in this image to the user."},
                                        {"type": "input_image", "image_url": f"data:image/jpeg;base64,{b64_im}"}
                                    ],
                                }
                            )
                        
                        await conn.response.create()

                    # --- FIXED INDENTATION HERE ---
                    elif getattr(event, "name", "") == "perform_dance":
                        print("\n[Brain] Tool triggered: Performing dance...")
                        
                        # Acknowledge the tool success to OpenAI so it doesn't freeze
                        await conn.conversation.item.create(item={
                            "type": "function_call_output",
                            "call_id": event.call_id,
                            "output": json.dumps({"status": "music playing and dance started"})
                        })

                        # Force the LLM to give a quick hype line before the music starts
                        await conn.response.create(
                            response={"instructions": "Give a very quick, one-sentence hype line introducing your Tron dance routine to the crowd!"}
                        )

                        # Trigger the callback to main.py to start the music!
                        if hasattr(self, 'on_dance_command_callback') and self.on_dance_command_callback:
                            self.on_dance_command_callback()

    def stop(self):
        self.is_connected = False
        self.pyaudio_instance.terminate()