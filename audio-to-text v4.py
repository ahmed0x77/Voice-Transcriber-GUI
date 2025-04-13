import json
import threading
import keyboard  # Global hotkey listener
import pyaudio
import pyautogui
import tkinter as tk
from vosk import Model, KaldiRecognizer

# Global state variables
listening = False
stop_event = threading.Event()
recognition_thread = None
overlay_window = None

# Initialize your Vosk model (update the path to the model directory as needed)
#https://alphacephei.com/vosk/models
model_path = "vosk-model-small-en-us-0.15"  # e.g., "vosk-model-small-en-us-0.15"
model = Model(model_path)

class TransparentOverlay(tk.Tk):
    def __init__(self):
        super().__init__()
        
        # Configure window properties
        self.attributes("-topmost", True)  # Always on top
        self.attributes("-alpha", 0.7)     # Semi-transparent
        self.overrideredirect(True)        # No window decorations
        
        # Calculate position (bottom of screen)
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        window_width = screen_width * 0.8
        window_height = 100
        x_position = (screen_width - window_width) / 2
        y_position = screen_height - window_height - 100
        
        # Set window size and position
        self.geometry(f"{int(window_width)}x{int(window_height)}+{int(x_position)}+{int(y_position)}")
        
        # Set background color
        self.configure(bg='black')
        
        # Add text display
        self.text = tk.Label(
            self, 
            text="Ready for speech...", 
            font=("Arial", 16),
            fg="white", 
            bg="black",
            wraplength=window_width - 20
        )
        self.text.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)
    
    def update_text(self, text):
        self.text.config(text=text)
        self.update()
    
    def close(self):
        self.destroy()

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
            # Read data from the microphone
            data = stream.read(4000, exception_on_overflow=False)
            if len(data) == 0:
                continue

            # Process the audio frame
            if recognizer.AcceptWaveform(data):
                # Final result available
                final_result = json.loads(recognizer.Result())
                if "text" in final_result and final_result["text"]:
                    final_text = final_result["text"]
                    print("Final:", final_text)
                    
                    # Update overlay with "typing..." message
                    overlay_window.update_text(f"Typing: {final_text}")
                    
                    # Type the text (with a space at the end)
                    pyautogui.typewrite(final_text + ' ')
                    
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

def toggle_recognition():
    """
    Toggles speech recognition on/off using a global hotkey.
    """
    global listening, recognition_thread, stop_event, overlay_window

    if not listening:
        print("Starting recognition...")
        stop_event.clear()
        recognition_thread = threading.Thread(target=run_vosk, daemon=True)
        recognition_thread.start()
        listening = True
    else:
        print("Stopping recognition...")
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

