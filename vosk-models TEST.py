import json
import time
import wave
import pyaudio
import os
import threading
from vosk import Model, KaldiRecognizer
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)

# Paths to the models - Ensure these paths are correct relative to the script or absolute paths
model_paths = {
    "vosk-model-en-us-0.22-lgraph": "vosk-model-en-us-0.22-lgraph",
    "vosk-model-small-en-us-0.15": "vosk-model-small-en-us-0.15",
    "vosk-model-en-us-0.22": "vosk-model-en-us-0.22"
}

# Audio recording settings
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 24000
CHUNK = 1024
TEMP_AUDIO_FILE = "temp_audio.wav"

# Global flag and container for recording
stop_recording = False
frames = []

# Preloaded models
models = {}

# Colors for each model
model_colors = [
    Fore.RED,
    Fore.GREEN,
    Fore.BLUE
]

def preload_models():
    """
    Preloads all Vosk models into memory.
    """
    global models
    print("Preloading models...")
    for model_name, model_path in model_paths.items():
        try:
            print(f"Loading model: {model_name} from {model_path}")
            start_time = time.time()
            models[model_name] = Model(model_path)
            print(f"Model {model_name} loaded.")
        except Exception as e:
            print(f"Error loading model {model_name}: {e}")
    print("All models preloaded.\n")

def recording_thread(stream):
    global stop_recording, frames
    print("Recording started. Speak now...")
    while not stop_recording:
        try:
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)
        except Exception as e:
            print(f"\nError reading audio chunk: {e}")
    print("Recording thread stopping...")

def record_audio():
    """
    Records audio in a background thread until the user presses Enter.
    """
    global stop_recording, frames
    frames = []
    stop_recording = False

    audio = pyaudio.PyAudio()
    try:
        stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                            input=True, frames_per_buffer=CHUNK)
    except Exception as e:
        print(f"Error opening audio stream: {e}")
        audio.terminate()
        return None

    thread = threading.Thread(target=recording_thread, args=(stream,))
    thread.start()

    # Wait for user to press Enter to stop recording
    input("Press Enter to stop recording...\n")
    stop_recording = True
    thread.join()

    try:
        stream.stop_stream()
        stream.close()
    except Exception as e:
        print(f"Error stopping/closing stream: {e}")
    audio.terminate()

    if not frames:
        print("No audio frames recorded.")
        return None

    # Save the recorded audio to a WAV file
    try:
        with wave.open(TEMP_AUDIO_FILE, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(audio.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b"".join(frames))
        print(f"Audio saved to {TEMP_AUDIO_FILE}, size: {os.path.getsize(TEMP_AUDIO_FILE)} bytes.")
    except Exception as e:
        print(f"Error saving WAV file: {e}")
        return None

    return TEMP_AUDIO_FILE

def transcribe_with_model(model_name, audio_file_path):
    """
    Transcribes the given audio file using the specified preloaded Vosk model.
    """
    try:
        model = models.get(model_name)
        if not model:
            return f"[Error: Model {model_name} not loaded]"

        wf = wave.open(audio_file_path, "rb")
        if wf.getnchannels() != CHANNELS or wf.getsampwidth() != pyaudio.get_sample_size(FORMAT) or wf.getframerate() != RATE:
            print("Warning: Audio file does not match expected properties.")
        recognizer = KaldiRecognizer(model, wf.getframerate())
        recognizer.SetWords(True)

        results = []
        while True:
            data = wf.readframes(4000)
            if not data:
                break
            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                results.append(result.get("text", ""))
        final_result = json.loads(recognizer.FinalResult())
        results.append(final_result.get("text", ""))
        wf.close()
        return " ".join(results).strip() or "[No speech detected]"
    except Exception as e:
        return f"[Transcription error: {e}]"

if __name__ == "__main__":
    preload_models()  # Preload all models before starting the loop

    while True:
        print()
        print()
        print()
        input("Press Enter to start recording...")
        audio_file_path = record_audio()
        if not audio_file_path or not os.path.exists(audio_file_path) or os.path.getsize(audio_file_path) <= 44:
            print("Recording failed or the file is empty.")
        else:
            print(f"\nComparing models using audio file: {audio_file_path}")
            for idx, (model_name, model_path) in enumerate(models.items()):
                transcription = transcribe_with_model(model_name, audio_file_path)
                print(f"{model_colors[idx % len(model_colors)]}--- {model_name} ---")
                print(f"{model_colors[idx % len(model_colors)]}Transcription: {transcription}")
        print("\nPress Enter to record again or Ctrl+C to exit.")