# Voice to Text (Gemini) - Modular Version

A speech-to-text application with a modern CustomTkinter UI and Gemini AI transcription.

## Project Structure

The project is now organized into three main modules:

### 📁 `recorder.py`

- **Audio recording logic** and core functionality
- Silence detection and filtering
- Audio file management
- Global state management (recording, pause, cancel)
- Audio playback functions

### 📁 `transcriber.py`

- **LLM/Gemini transcription logic**
- API integration with Google Gemini
- Audio file processing and transcription
- Response parsing and error handling

### 📁 `ui.py`

- **CustomTkinter UI and overlay**
- Main application window
- Floating recording overlay with controls
- User interface state management
- Audio feedback integration

### 📁 `main.py`

- **Application entry point**
- Ties all modules together
- Starts the CustomTkinter application

## Features

- 🎤 **Audio Recording**: High-quality microphone recording with silence filtering
- ⏸️ **Pause/Resume**: Temporarily pause recording without losing audio
- 🛑 **Stop**: Complete recording and process for transcription
- ❌ **Cancel**: Discard recording without processing
- 🎵 **Audio Feedback**: Custom sound effects for all actions
- ⌨️ **Hotkey Support**: `Ctrl+Alt+Shift+R` to start/stop recording
- 📋 **Auto-paste**: Option to automatically paste transcribed text
- 🌐 **Multi-language**: Supports mixed languages with native scripts

## Setup

1. **Install Dependencies**:

   ```bash
   pip install customtkinter pyaudio pyperclip pyautogui keyboard numpy google-genai python-dotenv
   ```

2. **Set API Key**: Create a `.env` file with your Gemini API key:

   ```
   GEMINI_API_KEY=your_api_key_here
   ```

3. **Audio Files**: Ensure the `audio/` folder contains:
   - `start.wav` - Recording start sound
   - `pause.wav` - Pause/resume sound
   - `stop.wav` - Stop recording sound
   - `cancel.wav` - Cancel recording sound
   - `done.wav` - Transcription complete sound

## Usage

Run the application:

```bash
python main.py
```

### Controls

- **Start Recording**: Click the button or press `Ctrl+Alt+Shift+R`
- **Pause/Resume**: Click the pause button in the overlay
- **Stop**: Click the stop button to process the audio
- **Cancel**: Click the ✕ button to discard the recording

### Overlay

The floating overlay appears when recording and provides:

- Visual recording indicator with pulsing animation
- Pause/Resume button
- Stop button (processes audio)
- Cancel button (discards audio)
- Draggable positioning

## File Organization Benefits

- **Maintainability**: Each module has a single responsibility
- **Reusability**: Components can be used independently
- **Testing**: Easier to test individual components
- **Development**: Multiple developers can work on different modules
- **Debugging**: Clearer separation of concerns

## Dependencies

- `customtkinter`: Modern UI framework
- `pyaudio`: Audio recording and playback
- `pyperclip`: Clipboard operations
- `pyautogui`: Auto-paste functionality
- `keyboard`: Global hotkey support
- `numpy`: Audio processing
- `google-genai`: Gemini AI API
- `python-dotenv`: Environment variable management
