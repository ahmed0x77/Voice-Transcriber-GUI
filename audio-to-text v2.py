import whisper
import pyaudio
import wave
import os
import warnings
from pynput import keyboard
import threading
import time
import pyautogui
import pygame

def playsound(file_path):
    # Initialize the mixer module in pygame
    pygame.mixer.init()
    
    # Load the MP3 file
    pygame.mixer.music.load(file_path)
    
    # Play the MP3 file
    pygame.mixer.music.play()
    
    # Wait until the music finishes playing
    while pygame.mixer.music.get_busy():
        continue

# Suppress specific warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning, module="whisper")




import torch
model_size="small"
if torch.cuda.is_available():
    device = "cuda"
else:
    device = "cpu"

model = whisper.load_model(model_size, device=device)
def transcribe_audio(audio_path):
    print(f"Transcribing audio from: {audio_path}")
    result = model.transcribe(audio_path, language="en")
    result = result.get("text", "")
    result = result.replace('Bifone', 'python')
    result = result.replace('bifund', 'python')
    os.remove(audio_path)
    
    return result.strip()

import queue
import threading

transcription_queue = queue.Queue()

def transcribe_worker():
    while True:
        audio_chunk = transcription_queue.get()
        if audio_chunk is None:
            break
        with wave.open("temp.wav", "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(audio.get_sample_size(pyaudio.paInt16))
            wf.setframerate(22050)
            wf.writeframes(audio_chunk)
        pyautogui.typewrite(transcribe_audio("temp.wav") + ' ')
        transcription_queue.task_done()

transcription_queue = queue.Queue()
transcription_thread = threading.Thread(target=transcribe_worker, daemon=True)
transcription_thread.start()


def get_audio_duration(audio_path):
    with wave.open(audio_path, "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        duration = frames / float(rate)
    return duration



# Global variables
is_recording = False
stream = None
audio = None
frames = []


import struct

def record_audio(output_file, sample_rate=22050, chunk_size=4096, silence_threshold=500, silence_duration_sec=1.0):
    global is_recording, stream, audio, frames

    audio = pyaudio.PyAudio()
    frames = []
    silence_counter = 0.0
    chunk_time = chunk_size / float(sample_rate)

    stream = audio.open(format=pyaudio.paInt16,
                        channels=1,
                        rate=sample_rate,
                        input=True,
                        frames_per_buffer=chunk_size)

    print("Recording started... Press Alt+Ctrl+D to stop")
    playsound('blip_no.mp3')

    while is_recording:
        data = stream.read(chunk_size)
        frames.append(data)

        samples = struct.unpack('<' + 'h'*(len(data)//2), data)
        amplitude = max(samples) if samples else 0

        if amplitude < silence_threshold:
            silence_counter += chunk_time
        else:
            silence_counter = 0.0

        if silence_counter >= silence_duration_sec:
            audio_chunk = b"".join(frames)
            chunk_samples = struct.unpack('<' + 'h'*(len(audio_chunk)//2), audio_chunk)
            if chunk_samples and max(chunk_samples) > silence_threshold:
                transcription_queue.put(audio_chunk)
            frames = []
            silence_counter = 0.0

    # After stopping, check if there are remaining frames to transcribe
    if frames:
        audio_chunk = b"".join(frames)
        chunk_samples = struct.unpack('<' + 'h'*(len(audio_chunk)//2), audio_chunk)
        if chunk_samples and max(chunk_samples) > silence_threshold:
            transcription_queue.put(audio_chunk)

    stream.stop_stream()
    stream.close()
    audio.terminate()

    # Optionally save the full recording
    with wave.open(output_file, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(audio.get_sample_size(pyaudio.paInt16))
        wf.setframerate(sample_rate)
        wf.writeframes(b"".join(frames))

    print("Recording saved to", output_file)
    playsound('blip_yes.mp3')




def on_hotkey():
    global is_recording
    
    if not is_recording:
        is_recording = True
        threading.Thread(target=lambda: record_audio("temp.wav")).start()
    else:
        is_recording = False
        print("Stopping recording...")

# Setup the hotkey
with keyboard.GlobalHotKeys({
    '<ctrl>+<alt>+<shift>+r': on_hotkey,
}) as h:
    h.join()











