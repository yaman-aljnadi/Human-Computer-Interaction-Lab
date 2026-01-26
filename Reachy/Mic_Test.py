import os
import time
import json
import numpy as np
import sounddevice as sd
import soundfile as sf
import requests
from dotenv import load_dotenv
from openai import OpenAI
import whisper



# auto pick device indices with sounddevice
# Setting to None uses system default devices
INPUT_DEVICE_INDEX = None   # System default microphone
OUTPUT_DEVICE_INDEX = None  # System default speakers

# Print what devices will be used
if INPUT_DEVICE_INDEX is None and OUTPUT_DEVICE_INDEX is None:
    default_in, default_out = sd.default.device
    print(f"[INFO] Using system default audio devices:")
    print(f"  Input: {sd.query_devices(default_in)['name']}")
    print(f"  Output: {sd.query_devices(default_out)['name']}")
elif INPUT_DEVICE_INDEX is not None and OUTPUT_DEVICE_INDEX is not None:
    print(f"[INFO] Using specified audio devices:")
    print(f"  Input: {sd.query_devices(INPUT_DEVICE_INDEX)['name']}")
    print(f"  Output: {sd.query_devices(OUTPUT_DEVICE_INDEX)['name']}")
else:
    if INPUT_DEVICE_INDEX is not None:
        print(f"[INFO] Using specified input device:")
        print(f"  Input: {sd.query_devices(INPUT_DEVICE_INDEX)['name']}")
    if OUTPUT_DEVICE_INDEX is not None:
        print(f"[INFO] Using specified output device:")
        print(f"  Output: {sd.query_devices(OUTPUT_DEVICE_INDEX)['name']}")

# MANUAL DEVICE INDEX SETTING


# Audio devices listed below:
# 0 = MacBook Air Microphone (input)
# 1 = MacBook Air Speakers (output)
# INPUT_DEVICE_INDEX = 11 # pulse  # Change as needed
# OUTPUT_DEVICE_INDEX = 11

# AUDIO SETTINGS
SAMPLE_RATE = 16000          # Whisper-friendly
CHANNELS = 1                 # mic input channel
RECORD_SECONDS = 5.0         # length of each capture window
CYCLE_SECONDS = 4.0          # how often to run a new cycle (>= RECORD_SECONDS)

WHISPER_MODEL_NAME = "base"  # Whisper base model
OLLAMA_MODEL = "mistral"     # Mistral model
OLLAMA_URL = "http://localhost:11434/api/generate"

TTS_MODEL = "gpt-4o-mini-tts"
TTS_VOICE = "alloy"
TTS_SR_HINT = 24000          # typical output SR for OpenAI TTS wav

# LOAD ENV + OPENAI CLIENT

env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=env_path)

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY not found. Ensure .env is next to this script.")

openai_client = OpenAI(api_key=api_key)

# LOAD WHISPER
print("[INFO] Loading Whisper...")
whisper_model = whisper.load_model(WHISPER_MODEL_NAME)
print(f"[INFO] Whisper loaded: {WHISPER_MODEL_NAME}")

# AUDIO SETUP
sd.default.device = (INPUT_DEVICE_INDEX, OUTPUT_DEVICE_INDEX)
sd.default.samplerate = SAMPLE_RATE

# SYSTEM PROMPT (YOUR REQUEST)
SYSTEM_PROMPT = """
You are the conversational brain for a robot voice pipeline used in a Human–Robot Interaction project.

Context:
- The user speaks into a microphone.
- Whisper transcribes the speech to text.
- You (the LLM) generate a helpful, spoken response.
- A text-to-speech system will read your response aloud to the user.

Behavior rules:
- Keep responses concise (1–4 sentenceunless the user asks for detail.
- Speak naturally, like a friendly robot assistant.
- If the transcription seems incomplete or unclear, ask a short follow-up question.
- Do not mention internal tool names (Whisper, Ollama, OpenAI TTS, ROS).
- If the user says “stop”, “quit”, or “exit”, respond with a short goodbye.

Topic focus:
- You are a Data Science Master's student at the University of Michigan Tech.
"""

# Keep conversation history (last K turns)
conversation_memory = []  # list of {"role": "...", "content": "..."}
MAX_TURNS_TO_KEEP = 10

def add_to_memory(role: str, content: str):
    conversation_memory.append({"role": role, "content": content})
    # Trim memory to last MAX_TURNS_TO_KEEP user+assistant pairs (approx)
    if len(conversation_memory) > 2 * MAX_TURNS_TO_KEEP + 1:
        # keep system + most recent
        del conversation_memory[:2]

# TIMER-BASED LISTENING
def record_audio(seconds: float = RECORD_SECONDS) -> np.ndarray:
    print(f"\nListening for {seconds:.1f}s...")
    audio = sd.rec(
        int(seconds * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="float32",
        blocking=True
    )
    audio = np.squeeze(audio).astype(np.float32)
    print(" Done.")
    return audio

# def record_audio(seconds: float = RECORD_SECONDS) -> np.ndarray:
#     # a test using a recorded mp3 file instead of live audio 
#     print(f"\n[TEST MODE] Loading test audio from 'hellothere.mp3'...")
#     audio, sr = sf.read("hellothere.mp3")
    
#     # Convert stereo to mono if needed
#     if audio.ndim > 1:
#         audio = np.mean(audio, axis=1)
    
#     # Resample if needed
#     if sr != SAMPLE_RATE:
#         print(f" Resampling from {sr} Hz to {SAMPLE_RATE} Hz...")
#         import librosa
#         audio = librosa.resample(audio, orig_sr=sr, target_sr=SAMPLE_RATE)
    
#     audio = audio.astype(np.float32)
#     print(" Done.")
#     return audio

# TRANSCRIBE (ENGLISH ONLY)
def transcribe(audio: np.ndarray) -> str:
    print(" Transcribing...")
    result = whisper_model.transcribe(
        audio,
        language="en",
        task="transcribe",
        fp16=False
    )
    text = (result.get("text") or "").strip()
    print("You said:", text)
    return text

# OLLAMA (MISTRARESPONSE
def llm_response(user_msg: str, model: str = OLLAMA_MODEL) -> str:
    # Build a single prompt string (Ollama /api/generate expects plain prompt)
    # We inject SYSTEM_PROMPT at the top so the model "knows what we're doing".
    lines = []
    lines.append("SYSTEM:\n" + SYSTEM_PROMPT.strip() + "\n")

    # Add recent history
    for item in conversation_memory[-2 * MAX_TURNS_TO_KEEP:]:
        if item["role"] == "user":
            lines.append(f"User: {item['content']}")
        elif item["role"] == "assistant":
            lines.append(f"Assistant: {item['content']}")

    # Add current user message
    lines.append(f"User: {user_msg}")
    lines.append("Assistant:")

    prompt = "\n".join(lines)

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }

    r = requests.post(OLLAMA_URL, json=payload, timeout=120)
    r.raise_for_status()
    reply = r.json().get("response", "").strip()
    return reply

# OPENAI TTS SPEAK
def speak_openai_tts(text: str, out_wav: str = "tts_output.wav"):
    if not text:
        return

    print("Speaking:", text)

    response = openai_client.audio.speech.create(
        model=TTS_MODEL,
        voice=TTS_VOICE,
        input=text
    )

    with open(out_wav, "wb") as f:
        f.write(response.read())

    audio, sr = sf.read(out_wav)
    sd.play(audio, sr)
    sd.wait()

# MAIN LOOP (TIMER)
def main():
    print("\nREADY — Timer-based voice pipeline is running.")
    print(f"Cycle every {CYCLE_SECONDS}s, recording {RECORD_SECONDS}s each cycle.\n")

    # optional: seed memory with a “hello” from assistant so it has a starting style
    # add_to_memory("assistant", "Hello! I’m ready. What would you like to do?")

    while True:
        cycle_start = time.time()

        audio = record_audio(RECORD_SECONDS)
        text = transcribe(audio)

        if not text:
            print("[INFO] Empty transcription. Skipping.")
        else:
            lower = text.lower().strip()
            if lower in ["exit", "quit", "stop"]:
                goodbye = "Shutting down. Goodbye."
                speak_openai_tts(goodbye)
                break

            add_to_memory("user", text)

            try:
                reply = llm_response(text)
            except Exception as e:
                reply = "I had trouble reaching the language model. Please check that your local LLM is running."
                print("[ERROR] LLM call failed:", e)

            if not reply:
                reply = "I’m not sure I caught that. Could you repeat it?"

            add_to_memory("assistant", reply)
            print("Assistant:", reply)
            speak_openai_tts(reply)

        # Timer pacing: wait until next cycle
        elapsed = time.time() - cycle_start
        remaining = CYCLE_SECONDS - elapsed
        if remaining > 0:
            time.sleep(remaining)

if __name__ == "__main__":
    main()