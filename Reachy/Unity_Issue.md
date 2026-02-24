# Reachy2Teleoperation Unity Setup & Troubleshooting Guide

This guide documents the common compilation and runtime errors encountered when setting up the [Reachy2Teleoperation](https://github.com/pollen-robotics/Reachy2Teleoperation) project in Unity, specifically regarding missing VR dependencies and GStreamer WebRTC DLL failures.

---

## 1. Missing `Sigtrap` Namespace Error

**Symptom:**
When opening the project in Unity, the console throws the following compilation error:
`error CS0246: The type or namespace name 'Sigtrap' could not be found`

**The Cause:**
The project relies on an open-source VR comfort plugin called **VR Tunnelling Pro** (by Sigtrap Games). If you downloaded the project via the GitHub "Download ZIP" button, GitHub strips out submodules, leaving this dependency completely missing.

**The Fix:**
Delete your current project folder and re-download it via the command line using Git to ensure all submodules are pulled correctly:

1. Open your terminal or command prompt.
2. Run the following command:
`git clone --recurse-submodules -b master https://github.com/pollen-robotics/Reachy2Teleoperation.git`
3. Open the newly cloned folder in Unity.

---

## 2. GStreamer DLL "Unknown Architecture" & High Ping

**Symptoms:**
* High latency (60ms+ compared to the official executable's 3ms).
* Missing Reachy inputs.
* Console errors including:
  * `DllNotFoundException: UnityGStreamerPlugin assembly`
  * `Failed to load ... expected x64 architecture, but was Unknown architecture.`

**The Cause (Part 1 - Environment Variables):**
Unity cannot locate the underlying GStreamer software installed on Windows. The plugin is just a bridge; it needs the actual MSVC 64-bit GStreamer binaries to function.

**The Fix (Part 1):**
1. Install the **MSVC 64-bit** (Complete Installation) version of GStreamer for Windows.
2. Open Windows Environment Variables.
3. Edit the system `Path` variable and add these two entries at the **very top** of the list (above any FFMPEG or MinGW paths to prevent conflicts):
   * `C:\gstreamer\1.0\msvc_x86_64\bin`
   * `C:\gstreamer\1.0\msvc_x86_64\lib\gstreamer-1.0`
4. Completely close Unity and **Quit Unity Hub** from the Windows System Tray to ensure the new PATH variables are loaded on the next launch.

**The Cause (Part 2 - The Git LFS Trap):**
If the architecture error persists after fixing the PATH, your `UnityGStreamerPlugin.dll` file is corrupted. Because the DLL is hosted using Git LFS (Large File Storage), Unity's package manager often fails to download the actual 52KB compiled binary. Instead, it downloads a 1KB text "pointer" file. Unity tries to read this text file as a DLL, fails to find 64-bit machine code, and throws the "Unknown architecture" error.

---

## 3. The `EntryPointNotFoundException` Version Mismatch

**Symptom:**
After replacing the fake 1KB DLL with a real one downloaded from GitHub, you receive this error:
`EntryPointNotFoundException: RegisterChannelCommandOpenCallback`

**The Cause:**
You downloaded the newest DLL from the `main` branch, but your Unity project is locked to an older, specific commit hash (e.g., `c3fb39ef1dbd90189b5a1e0c7c648204008e8b8a`). The C# scripts in your older project version are trying to call function names that were changed in the newer DLL version.

**The Fix:**
You must manually download the raw compiled DLL from the exact historical commit your project is locked to, and embed the package locally so Unity stops trying to overwrite it.

### Step-by-Step Ultimate GStreamer Fix:

**Step 1: Find Your Locked Commit Hash**
1. Navigate to your project directory: `Reachy2Teleoperation/Packages/`
2. Open `packages-lock.json` in a text editor.
3. Search for `"com.pollenrobotics.gstreamerwebrtc"`.
4. Copy the long string of letters and numbers next to `"hash"` or `"revision"` (e.g., `c3fb39ef1dbd90189b5a1e0c7c648204008e8b8a`).

**Step 2: Construct the Raw LFS Download Link**
To bypass GitHub's web interface and force the LFS server to hand you the real compiled binary from that specific point in time, construct a URL using this formula:
`https://github.com/[Organization]/[Repo]/raw/[Commit-Hash]/[File-Path]`

*Example for Reachy:*
`https://github.com/pollen-robotics/GstreamerWebRTCUnityPlugin/raw/c3fb39ef1dbd90189b5a1e0c7c648204008e8b8a/UnityProject/Packages/com.pollenrobotics.gstreamerwebrtc/Runtime/Plugins/x86_64/UnityGStreamerPlugin.dll`

Paste your constructed link into a browser and download the actual ~52KB `.dll` file.

**Step 3: Embed the Package Locally**
1. Close Unity and Unity Hub.
2. Navigate to Unity's temporary cache: `Reachy2Teleoperation/Library/PackageCache/`
3. Copy the folder named `com.pollenrobotics.gstreamerwebrtc@[random-letters]`.
4. Paste it into your local packages directory: `Reachy2Teleoperation/Packages/`
5. Rename the pasted folder to exactly: `com.pollenrobotics.gstreamerwebrtc` (remove the `@` and everything after it).

**Step 4: Replace the Fake DLL**
1. Inside your newly embedded package, navigate to: `Packages/com.pollenrobotics.gstreamerwebrtc/Runtime/Plugins/x86_64/`
2. Delete the 1KB `UnityGStreamerPlugin.dll` text file.
3. Move your manually downloaded 52KB DLL into this folder.

When you reopen Unity, the package manager will prioritize your local embedded folder. It will load the correct, version-matched 64-bit DLL, properly connect to your local GStreamer installation, and the WebRTC data channels will finally initialize.