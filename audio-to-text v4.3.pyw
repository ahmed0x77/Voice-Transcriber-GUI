while True:
    try:
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
        import pystray
        from PIL import Image
        from threading import Event

        # Global state variables
        listening = False
        stop_event = threading.Event()
        overlay_window = None

        # Initialize your Vosk model (update the path to the model directory as needed)
        #https://alphacephei.com/vosk/models
        model_path = "vosk-model-en-us-0.22-lgraph"  # for FAST louding use "vosk-model-small-en-us-0.15"
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
                
                # Set initial position near mouse
                x, y = pyautogui.position()
                
                # Simple approach: If mouse Y position is less than 150 pixels from top,
                # place the window below the cursor, otherwise place it above
                if y < 150:
                    # Mouse is near top of screen - place window BELOW cursor
                    window_y = y + 80  # 80 pixels below the cursor
                else:
                    # Mouse is not near top - place window ABOVE cursor
                    window_y = y - self.window_height - 80  # 80 pixels above the cursor
                
                self.geometry(f"{self.window_width}x{self.window_height}+{x - self.window_width // 2}+{window_y}")
                
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

    # ...existing code...
        def enhance_voice(data):
            """
            Applies a simple gain boost to the audio data to make it louder.
            """
            try:
                # Convert audio bytes to numpy array
                arr = np.frombuffer(data, dtype=np.int16)

                # If data is empty, return the original data
                if len(arr) == 0:
                    return data

                # Convert to float32 for processing (range -1.0 to 1.0)
                float_arr = arr.astype(np.float32) / 32768.0

                # --- Simple Gain Boost ---
                gain_factor = 1.8  # Adjust this value (e.g., 1.5 = 50% louder, 2.0 = 100% louder)
                enhanced = float_arr * gain_factor
                # --- End Simple Gain Boost ---

                # Clip the audio to prevent distortion if it exceeds the valid range
                enhanced = np.clip(enhanced, -0.99, 0.99)

                # Convert back to int16
                result = (enhanced * 32767).astype(np.int16)

                return result.tobytes()
            except Exception as e:
                # Print error and return original data if enhancement fails
                print(f"Audio enhancement error: {e}")
                return data
    # ...existing code...

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
                # Make sure recognition is stopped
                if listening:
                    toggle_recognition()
                # Close any open windows
                if overlay_window:
                    try:
                        overlay_window.destroy()
                    except:
                        pass
            
            def on_toggle_recognition(_):
                # Call the toggle_recognition function
                toggle_recognition()
            
            # Create the tray icon and menu
            icon = pystray.Icon("voice_recognition")
            icon.icon = icon_image
            icon.title = "Voice Recognition"
            icon.menu = pystray.Menu(
                pystray.MenuItem("Start/Stop Recognition", on_toggle_recognition),
                pystray.MenuItem("Exit", on_exit)
            )
            
            return icon, quit_event

        # Register the global hotkey: Ctrl+Alt+Shift+R toggles recognition
        keyboard.add_hotkey('ctrl+alt+shift+r', toggle_recognition)
        print("Press Ctrl+Alt+Shift+R to start/stop speech recognition or use the system tray icon.")

        # Create and run the system tray icon
        tray_icon, quit_event = create_tray_icon()
        icon_thread = threading.Thread(target=tray_icon.run)
        icon_thread.daemon = True
        icon_thread.start()

        # Wait for the quit signal instead of keyboard.wait('esc')
        quit_event.wait()




    except Exception as e:
        print(f"Error: {e}")
        continue  # Restart the loop to re-import modules and reset state
