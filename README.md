# Reachy 2: AI Interaction & VR Teleoperation Workflows

This repository contains the complete control architecture for the **Reachy 2 Humanoid Robot**. It integrates state-of-the-art AI models (LLMs, VLMs, and Speech Recognition) to provide two distinct operational modes: **Autonomous Interaction** and **VR Teleoperation Companion**.

## 📂 Repository Structure

The project is organized into modular workflows and testing sandboxes:

### 1. Reachy Core Logic (`/Reachy`)
This is the main production code, split into two independent workflows:

* **`Full_Workflow_No_Tele/` (Autonomous Mode)**
    * **Description:** The complete standalone experience. Reachy manages its own movements, tracks faces using MediaPipe, performs gestures (waving, dancing), and converses with users.
    * **Key Files:**
        * `main.py`: The entry point for the autonomous control loop.
        * `movement.py`: Handles inverse kinematics, dancing, and gestures.
        * `tracker.py`: Real-time face tracking logic.
        * `brain.py`: The cognitive core (connects LLM and VLM).

* **`Full_Workflow_Tele/` (VR Companion Mode)**
    * **Description:** A "Brain-Only" mode designed to run alongside VR teleoperation software. It **disables all motor commands** to prevent conflicts with the human pilot, turning Reachy into a smart voice/vision assistant that "rides along" with the VR operator.
    * **Key Files:**
        * `main_vr.py`: The passive control loop (Listen -> Think -> Speak).
        * `reachy_interface.py`: A safety-locked interface that prevents accidental motor stiffness.

* **Resources**
    * `piper_audios/`: ONNX models for local text-to-speech generation.
    * `songs/`: Audio files for the robot's entertainment modules.

### 2. Research & ROS (`/Realtime_ROS`)
Scripts for interacting directly with the robot's ROS middleware, primarily for grabbing raw camera frames or sensor data outside the standard SDK.
* Includes scripts for real-time inference with **Florence-2** and **Qwen** models.

### 3. Sandbox & Testing (`/SandBox`)
Experimental scripts and Jupyter notebooks for unit testing:
* **`General_Testing/`**: Notebooks for ROS bag extraction and vision model benchmarks.
* **`Reachy_Related/`**: Safety tests (`No_Go_Position.txt`), audio recording, and movement calibration.

---

## 🚀 AI Stack & Technologies

| Component | Technology | Description |
| :--- | :--- | :--- |
| **Brain (LLM)** | **OpenAI GPT-4o** | Handles conversation logic, personality, and tool usage. |
| **Vision (VLM)** | **Moondream2 / Qwen** | Allows Reachy to "see" and describe its environment. |
| **Ears (ASR)** | **OpenAI Whisper** | High-accuracy speech-to-text transcription. |
| **Voice (TTS)** | **OpenAI TTS / Piper** | Generates Reachy's voice (Streaming or Local). |
| **Tracking** | **MediaPipe / OpenCV** | Face detection and head tracking (Autonomous mode only). |

---

## 🛠️ Setup & Usage

### Prerequisites
* Python 3.10+
* Reachy 2 SDK
* `ffmpeg` (for audio processing)

### Environment Variables
Create a `.env` file in the workflow folder you are using (`Full_Workflow_No_Tele` or `Full_Workflow_Tele`) with the following:

```env
OPENAI_API_KEY=your_api_key_here
REACHY_IP=192.168.50.241 (or your robot's IP)