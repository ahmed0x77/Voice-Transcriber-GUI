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
import numpy as np
import time
import audioop

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
SILENCE_THRESHOLD = 150  # Lower threshold to catch softer speech
SILENCE_DURATION = 0.2
VOLUME_BOOST = 1.5  # Amplification factor

# New settings for voice enhancement
DYNAMIC_ENERGY_ADJUSTMENT = True
NOISE_REDUCTION = True

# Global state
is_recording = False
audio = None
transcription_queue = queue.Queue()

# Enhance audio by boosting volume and reducing noise
def enhance_audio(audio_data):
    # Convert bytes to numpy array for processing
    data_np = np.frombuffer(audio_data, dtype=np.int16)
    
    # Calculate current RMS volume
    rms = audioop.rms(audio_data, 2)
    
    # Only apply boost if volume is low
    if rms < 2000:
        # Boost volume - careful with clipping
        boost_factor = min(VOLUME_BOOST, 32767.0 / (max(abs(data_np)) + 1))
        data_np = (data_np * boost_factor).astype(np.int16)
    
    # If needed, we could add more sophisticated noise reduction here
    
    # Convert back to bytes
    return data_np.tobytes()

# Transcribe audio file to text
def transcribe_audio(audio_path):
    recognizer = sr.Recognizer()
    text = ""
    
    try:
        with sr.AudioFile(audio_path) as source:
            # Adjust recognition sensitivity
            if DYNAMIC_ENERGY_ADJUSTMENT:
                recognizer.dynamic_energy_threshold = True
                recognizer.energy_threshold = 300  # Start with a lower threshold
                recognizer.dynamic_energy_adjustment_ratio = 1.5
            
            # Reduce the pause threshold to detect end of speech faster
            recognizer.pause_threshold = 0.6
            recognizer.phrase_threshold = 0.3
            
            audio_data = recognizer.record(source)
        
        # Use a more accurate recognition engine if available
        # Can try different services based on accuracy needs
        text = recognizer.recognize_google(audio_data)
        print(f"Transcribed: {text}")
    except (sr.UnknownValueError, sr.RequestError) as e:
        print(f"Transcription error: {e}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Clean up temp file
    try:
        os.remove(audio_path)
    except:
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
                wf.writeframes(enhance_audio(audio_chunk))
                
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
            data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            
            # Apply real-time enhancement
            if VOLUME_BOOST != 1.0:
                data = enhance_audio(data)
                
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
    
    time.sleep(0.3)  # Allow final frames to be processed
    
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
