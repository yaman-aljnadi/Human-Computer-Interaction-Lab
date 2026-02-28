import asyncio
import base64
import json
import pyaudio
import cv2
import audioop 
from openai import AsyncOpenAI
import config

class RealtimeBrain:
    def __init__(self, get_frame_callback, condition="embodied"):
        self.get_frame_callback = get_frame_callback
        self.client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        
        self.audio_format = pyaudio.paInt16
        self.channels = 1
        
        # Record at Windows native rate, downsample to OpenAI rate
        self.native_rate = 48000 
        self.openai_rate = 24000 
        self.chunk = 2048 
        
        self.pyaudio_instance = pyaudio.PyAudio()
        self.mic_stream = None
        self.speaker_stream = None
        self.is_connected = False

        self.audio_out_queue = asyncio.Queue()

        prompt_file = "prompts/embodied_prompt.txt" if condition == "embodied" else "prompts/copilot_prompt.txt"

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
                
                # Instantly resample 48kHz to 24kHz for OpenAI
                data_24k, audio_state = audioop.ratecv(
                    data, 2, self.channels, self.native_rate, self.openai_rate, audio_state
                )
                
                audio_b64 = base64.b64encode(data_24k).decode("utf-8")
                await connection.input_audio_buffer.append(audio=audio_b64)
                await asyncio.sleep(0.001)
        except asyncio.CancelledError:
            pass
        finally:
            if self.mic_stream:
                self.mic_stream.stop_stream()
                self.mic_stream.close()

    async def start_session(self):
        self.is_connected = True
        
        try:
            # Speakers usually handle 24kHz fine, but if it sounds glitchy, we can resample this later too
            self.speaker_stream = self.pyaudio_instance.open(
                format=self.audio_format, channels=self.channels,
                rate=self.openai_rate, output=True 
            )
        except Exception as e:
            print(f"[Audio Task ERROR] Speaker failed to open: {e}")

        async with self.client.realtime.connect(model=config.OPENAI_REALTIME_MODEL) as conn:
            print("[Realtime] Connected!")
            
            await conn.session.update(session={
                "type": "realtime",
                "instructions": self.system_prompt,
                "audio": {
                    "input": {
                        "format": {
                            "type": "audio/pcm",
                            "rate": self.openai_rate, 
                        },
                        "transcription": {"model": "whisper-1"},
                        "turn_detection": {
                            "type": "server_vad",
                            "interrupt_response": True, 
                        },
                    },
                    "output": {
                        "format": {
                            "type": "audio/pcm",
                            "rate": self.openai_rate,
                        },
                        "voice": config.ROBOT_VOICE,
                    }
                },
                "tools": [{
                    "type": "function",
                    "name": "see_environment",
                    "description": "Look at the user's environment to see what is in front of you.",
                    "parameters": {"type": "object", "properties": {"focus": {"type": "string"}}}
                }],
                "tool_choice": "auto"
            })

            # --- MODIFICATION START ---
            # Start both the microphone input task and the new audio output task
            asyncio.create_task(self._audio_input_task(conn))
            asyncio.create_task(self._audio_output_task()) 
            # --- MODIFICATION END ---

            async for event in conn:
                if event.type == "input_audio_buffer.speech_started":
                    print("\n[OpenAI] Detected you are speaking. Interrupted!")
                    
                    # --- MODIFICATION START ---
                    # 1. Clear the pending audio queue instantly when the user speaks
                    while not self.audio_out_queue.empty():
                        try:
                            self.audio_out_queue.get_nowait()
                        except asyncio.QueueEmpty:
                            break
                    # --- MODIFICATION END ---
                    
                elif event.type == "input_audio_buffer.speech_stopped":
                    print("[OpenAI] Speech stopped. Processing...")
                    
                elif event.type == "conversation.item.input_audio_transcription.completed":
                    print(f"[You] {event.transcript}")
                    
                # UPDATED: Handle both beta and GA transcript event names
                elif event.type in ("response.audio_transcript.done", "response.output_audio_transcript.done"):
                    print(f"[Reachy] {event.transcript}")
                    
                elif event.type == "error":
                    err = getattr(event, "error", None)
                    msg = getattr(err, "message", str(err) if err else "unknown error")
                    print(f"[OpenAI ERROR] {msg}")

                # UPDATED: Handle both beta and GA audio delta event names
                elif event.type in ("response.audio.delta", "response.output_audio.delta"):
                    if self.speaker_stream:
                        audio_bytes = base64.b64decode(event.delta)
                        # --- MODIFICATION START ---
                        # Put audio into the queue instead of blocking the main event loop
                        self.audio_out_queue.put_nowait(audio_bytes)
                        # --- MODIFICATION END ---
                
                elif event.type == "response.function_call_arguments.done":
                    if getattr(event, "name", "") == "see_environment":
                        print("\n[Realtime] Tool triggered: Looking around...")
                        
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
                                        {
                                            "type": "input_image",
                                            "image_url": f"data:image/jpeg;base64,{b64_im}",
                                        },
                                    ],
                                }
                            )
                            print("[Realtime] Image sent to OpenAI.")
                        else:
                            print("[Realtime] Camera failed. Sending error message.")
                            await conn.conversation.item.create(
                                item={
                                    "type": "message",
                                    "role": "user",
                                    "content": [{"type": "input_text", "text": "Camera malfunctioned. Tell the user you cannot see."}],
                                }
                            )

                        await conn.response.create(
                            response={
                                "instructions": "Answer concisely in speech about what you just saw.",
                            }
                        )

    def stop(self):
        self.is_connected = False
        if self.speaker_stream:
            self.speaker_stream.stop_stream()
            self.speaker_stream.close()
        self.pyaudio_instance.terminate()


    async def _audio_output_task(self):
            """Pulls audio from the queue and plays it without blocking the main loop."""
            while self.is_connected:
                try:
                    # Wait for audio chunks from the server
                    audio_bytes = await self.audio_out_queue.get()
                    if audio_bytes and self.speaker_stream:
                        # Run the blocking PyAudio write in a separate thread
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(None, self.speaker_stream.write, audio_bytes)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    print(f"[Audio Output Error] {e}")