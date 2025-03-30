# Virtual Surround with Head Tracking

## Overview
This program emulates multi-channel virtual audio devices, recognized by Linux just like physical devices. When combined with head tracking, it delivers an immersive experience where, even with headphones on, you can perceive the direction of sound regardless of head position—unless you completely turn away from the camera.

### Available Surround Modes:
1. **Stereo** (2 audio channels)  
2. **LCR – Left Center Right** (3 audio channels)  
3. **LCR + Rear** (5 audio channels)  

---

## How to run this project

### 1 Requirements:

#### Linux:
Before running this project:

- Make sure you have **Python 3** installed.

- Check if **PulseAudio** or **PipeWire** is running on your system:

  ```bash
  pactl info
  ```

- Install **PortAudio** library (for audio handling):
  
  ```bash
  sudo apt update
  sudo apt install portaudio19-dev
  ```

- Install **required libraries**:

  ```bash
  pip install -r requirements.txt
  ```

### 2 Running:

- Run main.py:
  
  ```bash
  python3 main.py
  ```

---

## User Interface
The application window is divided into two sections:

![Image](https://github.com/user-attachments/assets/b202f906-d625-4cfb-9cae-3e4894fb764d)

### 1. Compass
- Displays the current state of all audio sources, including their position relative to the listener and volume levels.
- A pointer in the center indicates the current direction you are facing.
- The outer ring provides information about the camera's position relative to the central speaker.
- Clicking on a speaker icon will play sound from that direction and reveal its settings on the right panel.

### 2. Settings
- Allows quick calibration of the camera position.
- Provides a selection of available output audio devices (defaulting to the system's default audio device). It is crucial to select **headphones** not speakers.
- Enables switching between surround modes.
- Displays specific speaker settings when selected on the compass.
- Includes an option to edit speakers in **mirror mode** or **free mode**.
- Features a reset button to clear settings.

---

## State Saving, File Editing, and Troubleshooting
The program saves its entire state in a file named **Virtual_Surround_settings.json**, located in the same directory as the program. **Manual editing is not recommended** as it may cause unexpected behavior.

### Exception: Audio Device Issues
If the program fails to play sound despite selecting the correct audio device, manual editing may be required:
- Locate the `media.name` field in the settings file, which defaults to **"Playback Stream"**.
- Use **pavucontrol** (PulseAudio/ PipeWire control utility) to find the correct audio stream:
  1. Launch **Virtual Surround**.
  2. Open **pavucontrol** and go to the **Playback** tab.
  3. Find the program listed as **Python** (this application is seen as a couple of audio sources it is important to select the one that tries to play the sound but nothing can be heard).
  4. Copy the text after the colon (`:`), ignoring any trailing "na".
- If sound still does not play, you may need to manually change the default device for the stream in **pavucontrol** and set `media.name` to an empty string (`""`).

---

## Camera Calibration
The program allows calibration of the camera’s position relative to the direction considered "front," meaning where the central front speaker will be perceived.
- The calibration screen will highlight the **optimal camera position in green**.
- The best setup is placing the camera **near your primary monitor**, where you most frequently look.
- Non-optimal placements are possible but may cause tracking issues if you look away too often.

---

## Best Practices for Experiencing Spatial Audio
To achieve true multi-channel surround sound (beyond two channels), the application must support multi-channel audio output.

### Browser Compatibility:
- **Google Chrome & YouTube** only support stereo (2-channel) audio.
- If using LCR or LCR+Rear modes, behavior depends on the active Linux audio server:

#### 1. **PulseAudio**
- By default, **forces** audio playback on all available speakers.
- Stereo content will be **distributed across all speakers** in LCR+Rear mode, which reduces spatial accuracy (front and rear sound identical).
- **Recommended modes for stereo sources:** Stereo or LCR.

#### 2. **PipeWire**
- **Plays stereo audio only through "Front Left" and "Front Right" speakers** in LCR and LCR+Rear modes.
- This prevents rear speakers from duplicating stereo sound, preserving the spatial effect for multi-channel applications.
- **Recommended mode:** LCR+Rear (since stereo sources won't interfere with multi-channel ones).

---

## System Compatibility
The program is currently fully compatible with Linux, supporting both PulseAudio and PipeWire with pulse modules. The application has been tested on: Ubuntu 22.04.5 LTS and Ubuntu 24.04.2 LTS.


