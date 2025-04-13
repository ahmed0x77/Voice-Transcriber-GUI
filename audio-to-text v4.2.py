import json
import threading
import keyboard  # Global hotkey listener
import pyaudio
import pyautogui
import tkinter as tk
from vosk import Model, KaldiRecognizer
import time
import numpy as np
import winsound  # Add this import for playing audio

# Global state variables
listening = False
stop_event = threading.Event()
recognition_thread = None
overlay_window = None
position_update_thread = None

# Initialize your Vosk model (update the path to the model directory as needed)
#https://alphacephei.com/vosk/models
model_path = "vosk-model-en-us-0.22"  # for FAST louding use "vosk-model-small-en-us-0.15"
print(f"Loading Vosk model might take a while...")
model = Model(model_path)

class TransparentOverlay(tk.Tk):
    def __init__(self):
        super().__init__()
        
        # Configure window properties
        self.attributes("-topmost", True)  # Always on top
        self.attributes("-alpha", 0.7)     # Semi-transparent
        self.overrideredirect(True)        # No window decorations
        
        # Set window dimensions
        self.window_width = 600
        self.window_height = 80
        self.offset_y = 80  # Distance above the mouse cursor
        
        # Set initial position near mouse
        x, y = pyautogui.position()
        self.geometry(f"{self.window_width}x{self.window_height}+{x - self.window_width // 2}+{y - self.window_height - self.offset_y}")
        
        # Set background color
        self.configure(bg='black')
        
        # Create text widget with scrolling capability
        self.text_widget = tk.Text(
            self,
            font=("Arial", 14),
            fg="white",
            bg="black",
            wrap=tk.WORD,
            height=3,
            border=0,
            padx=10,
            pady=5
        )
        # Make text widget read-only
        self.text_widget.config(state=tk.DISABLED)
        self.text_widget.pack(expand=True, fill=tk.BOTH)
        
        # Initialize with default text
        self.update_text("Ready for speech...")
    
    def update_text(self, text):
        # Enable editing, clear, insert new text, then disable editing
        self.text_widget.config(state=tk.NORMAL)
        self.text_widget.delete(1.0, tk.END)
        self.text_widget.insert(tk.END, text)
        self.text_widget.config(state=tk.DISABLED)
        
        # Scroll to the end to show latest text
        self.text_widget.see(tk.END)
        self.update()
    
    def close(self):
        self.destroy()

def enhance_voice(data):
    try:
        # Convert audio bytes to numpy array
        arr = np.frombuffer(data, dtype=np.int16)
        
        # If data is empty, return the original data
        if len(arr) == 0:
            return data
        
        # Convert to float32 for processing
        float_arr = arr.astype(np.float32) / 32768.0
        
        # Calculate RMS (root mean square) for volume level
        rms = np.sqrt(np.mean(float_arr ** 2))
        
        # Static variables for adaptive thresholds (using function attributes)
        if not hasattr(enhance_voice, "noise_floor"):
            enhance_voice.noise_floor = 0.005  # Initial estimate, will adapt
            enhance_voice.noise_history = [0.005] * 10  # Keep history of noise levels
            enhance_voice.speech_detected = False
            enhance_voice.attack = 0.1  # Fast attack for noise gate
            enhance_voice.release = 0.2  # Slower release for smoother transitions
            enhance_voice.gain_smoothing = 0.0  # Current smoothed gain
        
        # Update noise floor estimate (when audio level is low)
        if rms < enhance_voice.noise_floor * 1.5:
            enhance_voice.noise_history.pop(0)  # Remove oldest value
            enhance_voice.noise_history.append(rms)  # Add new value
            enhance_voice.noise_floor = np.mean(enhance_voice.noise_history) * 1.2  # Slight headroom
        
        # Detect if this is speech (well above noise floor)
        is_speech = rms > enhance_voice.noise_floor * 3.0
        
        # Adaptive gain based on input level
        target_gain = 0.0
        if is_speech:
            # Compression curve: more gain for quieter speech, less for louder
            if rms < 0.02:  # Very quiet speech
                target_gain = 5.0  # More aggressive boost
            elif rms < 0.05:  # Moderate speech
                target_gain = 3.0  # Medium boost
            else:  # Loud speech
                target_gain = 1.5  # Lighter boost
            
            # Noise gate with smooth transition
            if not enhance_voice.speech_detected:
                # Attack - gradually increase gain
                enhance_voice.gain_smoothing = enhance_voice.gain_smoothing * (1 - enhance_voice.attack) + target_gain * enhance_voice.attack
            else:
                # Normal operation
                enhance_voice.gain_smoothing = enhance_voice.gain_smoothing * 0.7 + target_gain * 0.3
            
            enhance_voice.speech_detected = True
            
        else:
            # Release - gradually decrease gain when speech ends
            if enhance_voice.speech_detected:
                enhance_voice.gain_smoothing = enhance_voice.gain_smoothing * (1 - enhance_voice.release)
                if enhance_voice.gain_smoothing < 0.1:
                    enhance_voice.speech_detected = False
            else:
                enhance_voice.gain_smoothing = 0.0
        
        # Apply the calculated gain
        enhanced = float_arr * (1.0 + enhance_voice.gain_smoothing)
        
        # Simple noise reduction by slight attenuation below threshold
        mask = np.abs(enhanced) < enhance_voice.noise_floor * 2
        enhanced[mask] *= 0.5  # Reduce noise by 50%
        
        # Clip to prevent distortion
        enhanced = np.clip(enhanced, -0.99, 0.99)
        
        # Convert back to int16
        result = (enhanced * 32767).astype(np.int16)
        
        print(f"Level: {rms:.4f} | Noise: {enhance_voice.noise_floor:.4f} | Gain: {enhance_voice.gain_smoothing:.1f}", end="\r")
        
        return result.tobytes()
    except Exception as e:
        print(f"Audio enhancement error: {e}")
        return data  # If anything fails, return original data
import pyperclip
def run_vosk():
    """
    Listens to the microphone and outputs both partial and final results.
    """
    global overlay_window
    
    recognizer = KaldiRecognizer(model, 16000)
    recognizer.SetWords(True)  # Enable word-level details if needed

    # Start PyAudio stream
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16,
                    channels=1,
                    rate=16000,
                    input=True,
                    frames_per_buffer=8000)
    stream.start_stream()
    print("Listening... (speak now)")
    
    # Create overlay window to show partial results
    overlay_window = TransparentOverlay()
    overlay_window.update_text("Listening... (speak now)")
    
    while not stop_event.is_set():
        try:
            # Read data from the microphone and enhance it
            data = stream.read(4000, exception_on_overflow=False)
            data = enhance_voice(data) # ((OPTIONAL)): Enhance audio data
            if len(data) == 0:
                continue

            # Process the enhanced audio frame
            if recognizer.AcceptWaveform(data):
                # Final result available
                final_result = json.loads(recognizer.Result())
                if "text" in final_result and final_result["text"]:
                    final_text = final_result["text"]
                    print("Final:", final_text)
                    
                    # Update overlay with "typing..." message
                    overlay_window.update_text(f"Typing: {final_text}")
                    
                    # Type the text (with a space at the end)
                    pyperclip.copy(final_text + ' ')
                    pyautogui.hotkey('ctrl', 'v')

                    
                    # Reset overlay
                    overlay_window.update_text("Listening...")
            else:
                # Partial (interim) result available
                partial_result = json.loads(recognizer.PartialResult())
                partial_text = partial_result.get("partial", "")
                if partial_text:
                    # Update overlay with partial text
                    overlay_window.update_text(partial_text)
                    # Print partial results to console
                    print("\rPartial: " + partial_text, end="", flush=True)
                    
        except Exception as e:
            print(f"Error: {e}")
    
    print("\nRecognition stopped.")
    
    # Clean up resources
    if overlay_window:
        overlay_window.close()
    stream.stop_stream()
    stream.close()
    p.terminate()

def play_audio(file_path, wait=False):
    """THIS ONLY SUPPORTS .WAV FILES"""  # only .wav
    if not file_path.endswith('.wav'):
        raise Exception('Only .wav files are supported')
    if wait:
        winsound.PlaySound(file_path, winsound.SND_FILENAME)
    else:
        winsound.PlaySound(file_path, winsound.SND_FILENAME | winsound.SND_ASYNC)

def toggle_recognition():
    """
    Toggles speech recognition on/off using a global hotkey.
    """
    global listening, recognition_thread, stop_event, overlay_window

    if not listening:
        print("Starting recognition...")
        play_audio("blip_yes.wav")  # Play start sound
        stop_event.clear()
        recognition_thread = threading.Thread(target=run_vosk, daemon=True)
        recognition_thread.start()
        listening = True
    else:
        print("Stopping recognition...")
        play_audio("blip_no.wav")  # Play stop sound
        stop_event.set()
        # Wait for thread to finish cleanup
        recognition_thread.join(timeout=1.0)
        listening = False

# Register the global hotkey: Ctrl+Alt+Shift+R toggles recognition
keyboard.add_hotkey('ctrl+alt+shift+r', toggle_recognition)
print("Press Ctrl+Alt+Shift+R to start/stop speech recognition. Press Esc to exit.")
keyboard.wait('esc')

# Make sure to clean up any remaining windows on exit
if overlay_window:
    try:
        overlay_window.destroy()
    except:
        pass

