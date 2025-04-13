import os
import pyaudio
import wave
import threading
import pyautogui
import struct
import pygame
import queue
import speech_recognition as sr
from pynput import keyboard
import warnings

# Suppress warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# Simple sound player
def play_beep(file_path):
    threading.Thread(
        target=lambda: (
            pygame.mixer.init(),
            pygame.mixer.music.load(file_path),
            pygame.mixer.music.play(),
        ),
        daemon=True
    ).start()

# Audio configuration
SAMPLE_RATE = 22050
CHUNK_SIZE = 2048
SILENCE_THRESHOLD = 300
SILENCE_DURATION = 0.5

# Global state
is_recording = False
audio = None
transcription_queue = queue.Queue()

# Transcribe audio file to text
def transcribe_audio(audio_path):
    recognizer = sr.Recognizer()
    # Calibrate for ambient noise (if applicable)
    try:
        with sr.AudioFile(audio_path) as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio_data = recognizer.record(source)
    except Exception as e:
        print(f"Error calibrating noise: {e}")
        return ""

    text = ""
    try:
        text = recognizer.recognize_google(audio_data)
        print(f"Transcribed: {text}")
    except (sr.UnknownValueError, sr.RequestError) as e:
        print(f"Transcription error: {e}")
    except Exception as e:
        print(f"Error: {e}")
    
    try:
        os.remove(audio_path)
    except Exception:
        pass
        
    return text.strip()
# Process audio chunks and convert to text
def process_transcriptions():
    while True:
        audio_chunk = transcription_queue.get()
        if audio_chunk is None:
            break
            
        # Save chunk to temporary file
        temp_path = "temp.wav"
        try:
            with wave.open(temp_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(audio.get_sample_size(pyaudio.paInt16))
                wf.setframerate(SAMPLE_RATE)
                wf.writeframes(audio_chunk)
                
            # Convert to text and type it
            text = transcribe_audio(temp_path)
            if text:
                pyautogui.typewrite(text + ' ')
        except Exception as e:
            print(f"Processing error: {e}")
            
        transcription_queue.task_done()

# Record audio from microphone
def record_audio():
    global is_recording, audio
    
    audio = pyaudio.PyAudio()
    frames = []
    silence_counter = 0.0
    chunk_time = CHUNK_SIZE / float(SAMPLE_RATE)
    
    # Set up audio stream
    stream = audio.open(format=pyaudio.paInt16,
                      channels=1,
                      rate=SAMPLE_RATE,
                      input=True,
                      frames_per_buffer=CHUNK_SIZE)
    
    print("Recording started... Press Alt+Ctrl+Shift+R to stop")
    play_beep('blip_no.mp3')
    
    # Main recording loop
    while is_recording:
        try:
            data = stream.read(CHUNK_SIZE)
            frames.append(data)
            
            # Check for silence
            samples = struct.unpack('<' + 'h'*(len(data)//2), data)
            amplitude = max(samples) if samples else 0
            
            if amplitude < SILENCE_THRESHOLD:
                silence_counter += chunk_time
            else:
                silence_counter = 0.0
            
            # Process chunk after silence period
            if silence_counter >= SILENCE_DURATION:
                audio_chunk = b"".join(frames)
                chunk_samples = struct.unpack('<' + 'h'*(len(audio_chunk)//2), audio_chunk)
                if chunk_samples and max(chunk_samples) > SILENCE_THRESHOLD:
                    transcription_queue.put(audio_chunk)
                frames = []
                silence_counter = 0.0
                
        except Exception as e:
            print(f"Recording error: {e}")
    
    # Process any remaining audio
    if frames:
        audio_chunk = b"".join(frames)
        if audio_chunk:
            transcription_queue.put(audio_chunk)
    
    # Clean up audio resources
    stream.stop_stream()
    stream.close()
    audio.terminate()
    
    # Save complete recording
    with wave.open("temp_full.wav", "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(audio.get_sample_size(pyaudio.paInt16))
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(b"".join(frames) if frames else b"")
    
    print("Recording saved to temp_full.wav")
    play_beep('blip_yes.mp3')

# Toggle recording state when hotkey is pressed
def on_hotkey():
    global is_recording
    
    if not is_recording:
        is_recording = True
        threading.Thread(target=record_audio, daemon=True).start()
    else:
        is_recording = False
        print("Stopping recording...")

# Start transcription worker
transcription_thread = threading.Thread(target=process_transcriptions, daemon=True)
transcription_thread.start()

# Register hotkey and wait
with keyboard.GlobalHotKeys({
    '<ctrl>+<alt>+<shift>+r': on_hotkey,
}) as h:
    h.join()
