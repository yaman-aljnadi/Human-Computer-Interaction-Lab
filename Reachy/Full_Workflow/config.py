import torch

# Connection
REACHY_IP = '192.168.50.241'

# Models
DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"
QWEN_MODEL_ID = "Qwen/Qwen2.5-VL-3B-Instruct"
WHISPER_MODEL_TYPE = "base.en"
PIPER_MODEL_PATH = "piper_audios/ru_RU-irina-medium.onnx"

# Audio Files (Temp files)
TEMP_INPUT_AUDIO = "temp_command.wav"
TEMP_OUTPUT_AUDIO = "reachy_speech.wav"
SYSTEM_AUDIO = "system_speech.wav"