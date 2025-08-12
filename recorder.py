import os
import json
import threading
import tempfile
import time
import wave
import pyaudio
import pyperclip
import pyautogui
import numpy as np
import winsound
from dotenv import load_dotenv

# Load API key from .env file
load_dotenv()

# Audio settings
AUDIO_FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
TEMP_DIRECTORY = tempfile.gettempdir()

# Silence detection settings
SILENCE_THRESHOLD = 50  # Amplitude threshold for silence detection
MIN_VOICE_PERCENTAGE = 0.05  # Minimum percentage of non-silent chunks to consider as valid speech

# Global variables
recording = False
paused = False
cancelled = False
stop_event = threading.Event()
pause_event = threading.Event()
app = None  # Will hold the UI app instance

def play_audio(file_path, wait=False):
    """Plays WAV file for audio feedback"""
    if not file_path.endswith('.wav'):
        raise Exception('Only .wav files are supported')
    if wait:
        winsound.PlaySound(file_path, winsound.SND_FILENAME)
    else:
        winsound.PlaySound(file_path, winsound.SND_FILENAME | winsound.SND_ASYNC)

def is_silence(data):
    """Determine if an audio chunk is silence based on amplitude threshold"""
    # Convert bytes to numpy array
    audio_array = np.frombuffer(data, dtype=np.int16)
    # Calculate the average absolute amplitude
    amplitude = np.abs(audio_array).mean()
    print("amplitude:", amplitude)  # Debugging line to check amplitude
    return amplitude < SILENCE_THRESHOLD

def record_audio():
    """Records audio from microphone until stop_event is set, filtering out silence"""
    # Create a temporary file for the recording
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    temp_file = os.path.join(TEMP_DIRECTORY, f"recording_{timestamp}.wav")
    
    # Initialize PyAudio
    p = pyaudio.PyAudio()
    
    # Open audio stream
    stream = p.open(
        format=AUDIO_FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK
    )
    
    print("Recording started...")
    frames = []
    silence_count = 0
    voice_count = 0
    consecutive_silence = 0
    recording_voice = False
    
    # Record audio in chunks until stop_event is set
    while not stop_event.is_set():
        data = stream.read(CHUNK, exception_on_overflow=False)

        # If paused, drain audio but do not process/append
        if pause_event.is_set():
            continue

        # Check if the chunk is silence
        if is_silence(data):
            silence_count += 1
            consecutive_silence += 1

            # Only append some silence chunks to maintain natural sound
            if recording_voice and consecutive_silence <= 8:  # Keep ~0.5 second of trailing silence
                frames.append(data)
        else:
            voice_count += 1
            consecutive_silence = 0
            recording_voice = True
            frames.append(data)
    
    # Stop and close the stream
    stream.stop_stream()
    stream.close()
    p.terminate()
    
    # Get voice percentage to determine if there's actual speech
    total_chunks = silence_count + voice_count
    voice_percentage = voice_count / total_chunks if total_chunks > 0 else 0
    
    print(f"Voice detected in {voice_percentage:.1%} of the recording")
    
    # If there's not enough voice, return None
    if voice_percentage < MIN_VOICE_PERCENTAGE:
        print("Not enough speech detected. Skipping transcription.")
        return None
    
    # Save the recorded audio to the temporary file
    with wave.open(temp_file, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(AUDIO_FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
    
    print(f"Recording saved to {temp_file}")
    file_size = os.path.getsize(temp_file)
    print(f"File size: {file_size / (1024 * 1024):.2f} MB")
    
    return temp_file

def set_paused(value: bool):
    global paused
    paused = bool(value)
    if paused:
        pause_event.set()
    else:
        pause_event.clear()

def get_recording_state() -> bool:
    return globals().get("recording", False)

def process_speech():
    """Records audio, transcribes it, and pastes the result"""
    from transcriber import transcribe_with_gemini
    
    # Record audio until stop_event is set
    audio_file = record_audio()
    
    # Check if recording was cancelled
    if cancelled:
        print("Recording was cancelled, skipping transcription")
        return
    
    # Skip transcription if no audio file (silent recording)
    if audio_file is None:
        print("No speech detected, skipping transcription")
        return
    
    # Transcribe the recorded audio
    transcribed_text = transcribe_with_gemini(audio_file)

    # Display and paste the result
    if transcribed_text:
        print(f"Transcribed: {transcribed_text}")

        # Notify UI and clipboard/paste
        def _finish_in_ui():
            if app is not None:
                app.on_transcription_done(transcribed_text)
        try:
            # Copy text to clipboard
            pyperclip.copy(transcribed_text + ' ')
        except Exception:
            pass
        finally:
            if app is not None:
                app.after(0, _finish_in_ui)

        # Delete the temporary audio file
        try:
            os.remove(audio_file)
            print(f"Deleted temporary file: {audio_file}")
        except Exception as e:
            print(f"Error deleting temporary file: {e}")
    else:
        print("No transcription result")

    # Ensure UI state resets after processing
    if app is not None:
        app.after(0, app.on_recording_completed)

