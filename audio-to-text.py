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
    return result

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
def record_audio(output_file, sample_rate=22050, chunk_size=2048):
    """
    Records audio from the microphone and saves it to a file.
    """
    global is_recording, stream, audio, frames
    
    audio = pyaudio.PyAudio()
    frames = []
    
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
    
    # Save the recording
    stream.stop_stream()
    stream.close()
    audio.terminate()
    
    # Save the audio to a file
    with wave.open(output_file, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(audio.get_sample_size(pyaudio.paInt16))
        wf.setframerate(sample_rate)
        wf.writeframes(b"".join(frames))
    
    print("Recording saved to", output_file)
    playsound('blip_yes.mp3')
    if os.path.exists(output_file):
        audio_duration = get_audio_duration(output_file)
        print(f"Audio duration: {audio_duration:.2f} seconds")

        transcription = transcribe_audio(output_file)
        pyautogui.write(transcription)



def on_hotkey():
    global is_recording
    
    if not is_recording:
        is_recording = True
        threading.Thread(target=lambda: record_audio("output.wav")).start()
    else:
        is_recording = False
        print("Stopping recording...")

# Setup the hotkey
with keyboard.GlobalHotKeys({
    '<ctrl>+<alt>+<shift>+r': on_hotkey,
}) as h:
    h.join()











