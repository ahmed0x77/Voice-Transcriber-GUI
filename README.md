# 🎤 Smart Audio Transcript

> **Turn your voice into text with AI-powered transcription**

A modern, feature-rich speech-to-text application that combines the power of Google's Gemini AI with a beautiful web interface and floating recording controls. Perfect for content creators, developers, students, and anyone who needs fast, accurate transcription.

![Screenshot of Smart Audio Transcript](SCREENSHOT_PLACEHOLDER.png)

## ✨ Features

### 🎯 **Smart Recording**
- **One-click recording** with customizable hotkeys
- **Pause & resume** without losing your audio
- **Multiple microphones** support with easy device switching

### 🤖 **AI-Powered Transcription**
- **Google Gemini AI** for accurate, context-aware transcription
- **Multi-language support** - 120+ Supported Languages
- **Customizable AI prompts** for specialized use cases

### 🖥️ **Modern Interface**
- **Beautiful UI** with dark theme and responsive design
- **Floating recording overlay** that stays on top while you work
- **System tray integration** for background operation
- **Real-time status** and audio feedback

### ⚡ **Productivity Features**
- **Auto-paste** transcribed text directly to your active application
- **auto-save in cliboard** it automatically saves the transcribed text to clipboard
- **Background operation** - keeps running in system tray

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Get Your API Key
- Get a free [Google Gemini API key](https://makersuite.google.com/app/apikey)

### 3. Run the App
```bash
python main.py
```

### 4. Add Your API Key (in the app)
1) In the left sidebar, click `API Keys`  
2) Paste your key into the `Gemini API Key` field  
3) The key is saved automatically (you can change it anytime)

Tip: Alternatively, you can create a `.env` file with `GEMINI_API_KEY=your_key`.


## 🎮 How It Works

1. **Start Recording** - press `Ctrl+Shift+Space` to start/stop recording
2. **Speak Naturally** - The floating overlay shows recording status
3. **AI Processing** - Gemini AI transcribes with context awareness
4. **Auto-Paste** - Text appears in your active application and is saved to clipboard

## 🛠️ Configuration

### Hotkeys
- **Toggle Mode**: Press once to start/stop (default: `Ctrl+Shift+Space`)
- **Hold Mode**: Hold to record, release to stop (default: `Ctrl`)

### Audio Settings
- **Silence Threshold**: Adjust sensitivity for your environment
- **Microphone Selection**: Choose your preferred input device
- **Ambient Calibration**: Automatic noise floor detection

### AI Customization
- **Custom Prompts**: Tailor transcription for your specific needs
- **Language Preservation**: Maintains original scripts and accents



## 🏗️ Architecture

Smart Audio Transcript uses a modern hybrid architecture:

- **🌐 Web Interface** (Eel) - Settings and configuration
- **🎯 Native Overlay** (CustomTkinter) - Floating recording controls  
- **🗂️ System Tray** (pystray) - Background management
- **🎤 Core Engine** (Python) - Audio processing & AI integration

This gives you the best of both worlds: a modern web UI for settings and responsive native controls for recording.



## 🤝 Contributing

We welcome contributions! Here's how you can help:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

---

**Made with ❤️ for the open source community**

*Transform your voice into text with the power of AI*
