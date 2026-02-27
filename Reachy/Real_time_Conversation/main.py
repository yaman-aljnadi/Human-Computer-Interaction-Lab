import asyncio
import base64
import json
import pyaudio
import cv2
import audioop
import os
from openai import AsyncOpenAI

# --- Configuration ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") 
OPENAI_REALTIME_MODEL = "gpt-realtime-2025-08-28"
VOICE = "alloy"

class RealtimeAIAssistant:
    def __init__(self):
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY environment variable not set.")
            
        self.client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        
        # Audio Configuration
        self.audio_format = pyaudio.paInt16
        self.channels = 1
        self.native_rate = 48000  # Standard mic recording rate
        self.openai_rate = 24000  # Required rate for OpenAI Realtime API
        self.chunk = 2048 
        
        self.pyaudio_instance = pyaudio.PyAudio()
        self.mic_stream = None
        self.speaker_stream = None
        self.is_connected = False

        self.system_prompt = (
            "You are a helpful AI assistant. Keep answers short. "
            "If the user asks you to look at something, ALWAYS use the 'see_environment' tool."
        )

    def get_webcam_frame(self):
        """Standalone replacement for the robot camera using standard webcam."""
        cap = cv2.VideoCapture(0)
        ret, frame = cap.read()
        cap.release()
        if ret:
            return frame
        return None

    async def _audio_input_task(self, connection):
        print(f"[Audio Task] Opening mic at {self.native_rate}Hz...")
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
            self.speaker_stream = self.pyaudio_instance.open(
                format=self.audio_format, channels=self.channels,
                rate=self.openai_rate, output=True 
            )
        except Exception as e:
             print(f"[Audio Task ERROR] Speaker failed to open: {e}")

        async with self.client.realtime.connect(model=OPENAI_REALTIME_MODEL) as conn:
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
                        "voice": VOICE,
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

            asyncio.create_task(self._audio_input_task(conn))

            async for event in conn:
                if event.type == "input_audio_buffer.speech_started":
                    print("\n[OpenAI] Detected you are speaking...")
                    
                elif event.type == "input_audio_buffer.speech_stopped":
                    print("[OpenAI] Speech stopped. Processing...")
                    
                elif event.type == "conversation.item.input_audio_transcription.completed":
                    print(f"[You] {event.transcript}")
                    
                elif event.type in ("response.audio_transcript.done", "response.output_audio_transcript.done"):
                    print(f"[AI] {event.transcript}")
                    
                elif event.type == "error":
                    err = getattr(event, "error", None)
                    msg = getattr(err, "message", str(err) if err else "unknown error")
                    print(f"[OpenAI ERROR] {msg}")

                elif event.type in ("response.audio.delta", "response.output_audio.delta"):
                    if self.speaker_stream:
                        audio_bytes = base64.b64decode(event.delta)
                        self.speaker_stream.write(audio_bytes)
                
                elif event.type == "response.function_call_arguments.done":
                    if getattr(event, "name", "") == "see_environment":
                        print("\n[Realtime] Tool triggered: Looking around...")
                        
                        frame = self.get_webcam_frame()
                        
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

async def main():
    print("Starting Standalone Realtime AI...")
    ai = RealtimeAIAssistant()
    try:
        await ai.start_session()
    except KeyboardInterrupt:
        print("\nStopping...")
        ai.stop()

if __name__ == "__main__":
    asyncio.run(main())