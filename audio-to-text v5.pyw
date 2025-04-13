import os
import json
import threading
import tempfile
import time
import wave
import pyaudio
import pyperclip
import pyautogui
import keyboard
import winsound
import pystray
import numpy as np
from PIL import Image
from threading import Event
from google import genai
from google.genai import types
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
stop_event = threading.Event()

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
        
        # Check if the chunk is silence
        if is_silence(data):
            silence_count += 1
            consecutive_silence += 1
            
            # Only append some silence chunks to maintain natural sound
            # Add a bit of silence at the beginning if we haven't started recording voice yet
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
    # play_audio(temp_file, wait=True)  # Play the recorded audio for confirmation
    
    return temp_file

def transcribe_with_gemini(audio_file):
    """Transcribes audio using the Gemini API"""
    if audio_file is None:
        return None
    
    try:
        # Initialize the Gemini API client
        client = genai.Client(
            api_key=os.environ.get("GEMINI_API_KEY"),
        )
        
        print("Sending to Gemini API...")
        
        # Upload the audio file
        uploaded_file = client.files.upload(file=audio_file)
        
        # Define the model and content
        model = "gemini-2.0-flash-lite"
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_uri(
                        file_uri=uploaded_file.uri,
                        mime_type=uploaded_file.mime_type,
                    ),
                    types.Part.from_text(text="""Interpret the provided audio, focusing on context and speaker intent, not just literal words. Act as an editor: remove fillers, repetitions, and self-corrections (e.g., 'um', 'like', 'I mean'). Fix minor errors based on clear intent. Output a clean, concise, and fluent text representing the core intended message."""),
                ],
            ),
        ]
        
        # Configure the response schema
        generate_content_config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "text": types.Schema(
                        type=types.Type.STRING,
                    ),
                },
            ),
        )
        
        # Generate content
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=generate_content_config,
        )
        
        # Parse the response
        try:
            response_json = json.loads(response.text)
            transcribed_text = response_json.get("text", "")
            return transcribed_text
        except json.JSONDecodeError:
            print("Error decoding JSON response")
            return response.text  # Return raw text if JSON parsing fails
            
    except Exception as e:
        print(f"Error during transcription: {e}")
        return f"Transcription error: {str(e)}"

def toggle_recording():
    """Starts or stops audio recording"""
    global recording, stop_event
    
    if not recording:
        # Start recording
        print("Starting recording...")
        play_audio("blip_yes.wav")  # Play start sound
        stop_event.clear()
        recording = True
        threading.Thread(target=process_speech, daemon=True).start()
    else:
        # Stop recording
        print("Stopping recording...")
        play_audio("blip_no.wav")  # Play stop sound
        stop_event.set()
        recording = False

def process_speech():
    """Records audio, transcribes it, and pastes the result"""
    # Record audio until stop_event is set
    audio_file = record_audio()
    
    # Skip transcription if no audio file (silent recording)
    if audio_file is None:
        print("No speech detected, skipping transcription")
        return
    
    # Transcribe the recorded audio
    transcribed_text = transcribe_with_gemini(audio_file)
    
    # Display and paste the result
    if transcribed_text:
        print(f"Transcribed: {transcribed_text}")
        
        # Copy text to clipboard
        pyperclip.copy(transcribed_text + ' ')
        pyautogui.hotkey('ctrl', 'v')  # Paste the text
        print("Text copied to clipboard")
        
        # Delete the temporary audio file
        try:
            os.remove(audio_file)
            print(f"Deleted temporary file: {audio_file}")
        except Exception as e:
            print(f"Error deleting temporary file: {e}")
    else:
        print("No transcription result")

def create_tray_icon():
    """Create a system tray icon with menu options"""
    # Use an existing icon.png file
    icon_image = Image.open("icon.png")
    
    # Define what happens when the app is quitting
    quit_event = Event()
    
    def on_exit(icon, _):
        # Clean up and exit
        print("Exiting application...")
        icon.stop()
        quit_event.set()
        # Make sure recording is stopped
        if recording:
            toggle_recording()
    
    def on_toggle_recording(_):
        # Call the toggle_recording function
        toggle_recording()
    
    # Create the tray icon and menu
    icon = pystray.Icon("speech_to_text")
    icon.icon = icon_image
    icon.title = "Speech to Text (Gemini)"
    icon.menu = pystray.Menu(
        pystray.MenuItem("Start/Stop Recording", on_toggle_recording),
        pystray.MenuItem("Exit", on_exit)
    )
    
    return icon, quit_event

# Check if API key is set
if not os.environ.get("GEMINI_API_KEY"):
    print("WARNING: GEMINI_API_KEY not set in environment variables or .env file")

# Main function
def main():
    # Register the global hotkey
    keyboard.add_hotkey('ctrl+alt+shift+r', toggle_recording)
    print("Press Ctrl+Alt+Shift+R to start/stop recording or use the system tray icon.")
    
    # Create and run the system tray icon
    tray_icon, quit_event = create_tray_icon()
    icon_thread = threading.Thread(target=tray_icon.run)
    icon_thread.daemon = True
    icon_thread.start()
    
    # Wait for the quit event
    quit_event.wait()

if __name__ == "__main__":
    main()