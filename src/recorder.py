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
CHUNK = 512  # Smaller chunk for lower latency capture (was 1024)
TEMP_DIRECTORY = tempfile.gettempdir()
SELECTED_DEVICE_INDEX = None  # None means use default device

# Silence detection settings
SILENCE_THRESHOLD = 50  # Amplitude threshold for silence detection (can be updated at runtime)
MIN_VOICE_PERCENTAGE = 0.05  # Minimum percentage of non-silent chunks to consider as valid speech

# Global variables
recording = False
paused = False
cancelled = False
stop_event = threading.Event()
pause_event = threading.Event()
app = None  # Legacy reference (tkinter app); kept for backward compatibility
active_session_id = None  # identifies the most recent recording session

# Callback hooks for new (Eel) UI
on_transcription_done_callback = None
on_recording_completed_callback = None

def set_callbacks(on_transcription_done=None, on_recording_completed=None):
    """Register UI callbacks (used by Eel web UI).

    Args:
        on_transcription_done: function(text:str)
        on_recording_completed: function()
    """
    global on_transcription_done_callback, on_recording_completed_callback
    if on_transcription_done is not None:
        on_transcription_done_callback = on_transcription_done
    if on_recording_completed is not None:
        on_recording_completed_callback = on_recording_completed

def play_audio(file_path, wait=False):
    """Plays WAV file for audio feedback"""
    if not file_path.endswith('.wav'):
        raise Exception('Only .wav files are supported')
    # Resolve relative path robustly (works when launched from different CWD or frozen exe)
    if not os.path.isabs(file_path) and not os.path.exists(file_path):
        candidate = os.path.join(os.path.dirname(__file__), file_path)
        if os.path.exists(candidate):
            file_path = candidate
        else:
            # Allow shorthand like 'audio/done.wav' vs full path
            audio_dir_candidate = os.path.join(os.path.dirname(__file__), 'audio', os.path.basename(file_path))
            if os.path.exists(audio_dir_candidate):
                file_path = audio_dir_candidate
    if wait:
        winsound.PlaySound(file_path, winsound.SND_FILENAME)
    else:
        winsound.PlaySound(file_path, winsound.SND_FILENAME | winsound.SND_ASYNC)

def set_silence_threshold(value):
    """Update the global silence threshold used by is_silence().

    Args:
        value: numeric threshold (will be coerced to int, min 1)
    """
    global SILENCE_THRESHOLD
    try:
        v = int(float(value))
        if v < 1:
            v = 1
        SILENCE_THRESHOLD = v
        print(f"Silence threshold set to {SILENCE_THRESHOLD}")
    except Exception as _e:
        pass

def get_audio_devices():
    """Get list of available audio input devices.

    Returns:
        list of dicts with keys: index, name, max_inputs
    """
    devices = []
    try:
        p = pyaudio.PyAudio()
        for i in range(p.get_device_count()):
            try:
                info = p.get_device_info_by_index(i)
                if info.get('maxInputChannels', 0) > 0:  # Has input capability
                    devices.append({
                        'index': i,
                        'name': info.get('name', f'Device {i}'),
                        'max_inputs': info.get('maxInputChannels', 0)
                    })
            except Exception:
                continue
        p.terminate()
    except Exception:
        pass
    return devices

def set_audio_device(device_index):
    """Set the audio input device to use for recording.

    Args:
        device_index: int device index, or None for default
    """
    global SELECTED_DEVICE_INDEX
    if device_index is None:
        SELECTED_DEVICE_INDEX = None
    else:
        try:
            device_index = int(device_index)
            # Validate device exists
            devices = get_audio_devices()
            if any(d['index'] == device_index for d in devices):
                SELECTED_DEVICE_INDEX = device_index
            else:
                print(f"Invalid device index: {device_index}")
        except Exception:
            print(f"Invalid device index: {device_index}")

def is_silence(data):
    """Determine if an audio chunk is silence based on amplitude threshold"""
    # Convert bytes to numpy array
    audio_array = np.frombuffer(data, dtype=np.int16)
    # Calculate the average absolute amplitude
    amplitude = np.abs(audio_array).mean()
    print("amplitude:", amplitude)  # Debugging line to check amplitude
    return amplitude < SILENCE_THRESHOLD

def calibrate_noise_floor(duration_sec: float = 2.0) -> dict:
    """Sample ambient audio to estimate noise floor and propose a silence threshold.

    Args:
        duration_sec: seconds to listen for ambient noise (user should stay silent)

    Returns:
        dict with keys: ambient_mean, ambient_p95, threshold
    """
    if duration_sec is None or duration_sec <= 0:
        duration_sec = 2.0

    # Initialize PyAudio
    p = pyaudio.PyAudio()
    stream = p.open(
        format=AUDIO_FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        input_device_index=SELECTED_DEVICE_INDEX,
        frames_per_buffer=CHUNK
    )
    try:
        num_chunks = int(max(1, RATE / CHUNK * duration_sec))
        amplitudes = []
        for _ in range(num_chunks):
            data = stream.read(CHUNK, exception_on_overflow=False)
            audio_array = np.frombuffer(data, dtype=np.int16)
            amp = float(np.abs(audio_array).mean())
            amplitudes.append(amp)

        if amplitudes:
            ambient_mean = float(np.mean(amplitudes))
            ambient_p95 = float(np.percentile(amplitudes, 95))
        else:
            ambient_mean = 0.0
            ambient_p95 = 0.0

        # Heuristic: pick a safe threshold above noise floor but not too high
        # Use the larger of (p95 * 1.4) and (mean * 2.0), with a lower bound
        proposed = max(ambient_p95 * 1.4, ambient_mean * 2.0, 30.0)
        proposed = float(round(proposed))

        return {
            "ambient_mean": ambient_mean,
            "ambient_p95": ambient_p95,
            "threshold": proposed,
        }
    finally:
        try:
            stream.stop_stream()
        except Exception:
            pass
        try:
            stream.close()
        except Exception:
            pass
        p.terminate()

def record_audio(session_id):
    """Records audio from microphone until stop_event is set, filtering out silence.

    Returns (filepath_or_None, aborted_bool, duration_seconds)
    aborted_bool True means recording became stale/cancelled and should be ignored silently.
    duration_seconds is the actual recording duration in seconds.
    """
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
        input_device_index=SELECTED_DEVICE_INDEX,
        frames_per_buffer=CHUNK
    )
    
    print("Recording started...")
    start_time = time.time()
    frames = []
    pre_roll = []  # capture a small pre-roll so speech right after start sound isn't lost
    MAX_PRE_ROLL_FRAMES = int(RATE / CHUNK * 0.6)  # ~600ms
    silence_count = 0
    voice_count = 0
    consecutive_silence = 0
    recording_voice = False
    
    # Record audio in chunks until stop_event is set
    aborted = False
    while not stop_event.is_set():
        # If session became stale or cancelled, abort immediately (no save, no stats)
        if cancelled or session_id != active_session_id:
            aborted = True
            break
        data = stream.read(CHUNK, exception_on_overflow=False)

        # Accumulate pre-roll until user begins speaking; maintain sliding window
        if len(pre_roll) < MAX_PRE_ROLL_FRAMES:
            pre_roll.append(data)
        else:
            pre_roll.pop(0); pre_roll.append(data)

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
            # On first detected voice append pre-roll to avoid clipping beginning
            if not recording_voice and pre_roll:
                frames.extend(pre_roll)
                pre_roll.clear()
            frames.append(data)
    
    # Stop and close the stream
    stream.stop_stream()
    stream.close()
    p.terminate()
    
    # Calculate recording duration
    duration_seconds = time.time() - start_time
    
    # Handle abort
    if aborted:
        # Clean up stream, return without saving
        return None, True, duration_seconds

    # Get voice percentage to determine if there's actual speech
    total_chunks = silence_count + voice_count
    voice_percentage = voice_count / total_chunks if total_chunks > 0 else 0

    print(f"Voice detected in {voice_percentage:.1%} of the recording")

    # If there's not enough voice, return None
    if voice_percentage < MIN_VOICE_PERCENTAGE:
        print("Not enough speech detected. Skipping transcription.")
        return None, False, duration_seconds

    # Save the recorded audio to the temporary file
    with wave.open(temp_file, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(AUDIO_FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))

    print(f"Recording saved to {temp_file}")
    file_size = os.path.getsize(temp_file)
    print(f"File size: {file_size / (1024 * 1024):.2f} MB")

    return temp_file, False, duration_seconds

def set_paused(value: bool):
    global paused
    paused = bool(value)
    if paused:
        pause_event.set()
    else:
        pause_event.clear()

def get_recording_state() -> bool:
    return globals().get("recording", False)

def process_speech(session_id=None):
    """Records audio, transcribes it, and pastes the result.

    session_id: identifier captured at start; if it no longer matches active_session_id
                when transcription is about to happen, the audio is discarded (stale).
    """
    global active_session_id
    if session_id is None:
        session_id = active_session_id
    from .transcriber import transcribe_with_gemini
    
    # Record audio until stop_event is set
    audio_file, aborted, duration = record_audio(session_id)
    
    # If aborted early (stale/cancelled) skip everything silently
    if aborted:
        return

    # Check if recording was cancelled OR session became stale due to restart after capture finished
    if cancelled or session_id != active_session_id:
        print("Recording was cancelled or stale (post-capture), skipping transcription")
        return
    
    # Check if recording was too short (likely accidental)
    MIN_RECORDING_DURATION = 0.6  # seconds
    if duration < MIN_RECORDING_DURATION:
        print(f"Recording too short ({duration:.2f}s), likely accidental. Skipping transcription.")
        if audio_file:
            try:
                os.remove(audio_file)
            except Exception:
                pass
        return
    
    # Skip transcription if no audio file (silent recording)
    if audio_file is None:
        print("No speech detected, skipping transcription")
        return
    
    # Transcribe the recorded audio
    transcribed_text = transcribe_with_gemini(audio_file)

    # Detect likely API key / auth errors and inform user via popup (non-fatal)
    try:
        if isinstance(transcribed_text, str) and transcribed_text.lower().startswith("transcription error"):
            lowered = transcribed_text.lower()
            if any(k in lowered for k in ["api key", "unauthorized", "invalid", "permission", "403", "401", "forbidden"]):
                try:
                    from .alert_popup import show_invalid_api_key_popup
                    show_invalid_api_key_popup(transcribed_text)
                except Exception:
                    pass
    except Exception:
        pass

    # Discard if session became stale after transcription latency
    if session_id != active_session_id:
        print("Stale recording (post-transcribe) discarded")
        try:
            if audio_file:
                os.remove(audio_file)
        except Exception:
            pass
        return

    # Display and paste the result (still current)
    if transcribed_text:
        print(f"Transcribed: {transcribed_text}")
        # Notify UI callback directly (Eel) or via tkinter if legacy app exists
        if on_transcription_done_callback is not None:
            try:
                on_transcription_done_callback(transcribed_text)
            except Exception as _e:
                print("UI callback (transcription done) error:", _e)
        elif app is not None:
            try:
                app.after(0, app.on_transcription_done, transcribed_text)
            except Exception:
                pass

        # Delete the temporary audio file
        try:
            os.remove(audio_file)
            print(f"Deleted temporary file: {audio_file}")
        except Exception as e:
            print(f"Error deleting temporary file: {e}")
    else:
        print("No transcription result")

    # Ensure UI state resets after processing
    # Notify completion
    if on_recording_completed_callback is not None:
        try:
            on_recording_completed_callback()
        except Exception as _e:
            print("UI callback (recording completed) error:", _e)
    elif app is not None:
        try:
            app.after(0, app.on_recording_completed)
        except Exception:
            pass

