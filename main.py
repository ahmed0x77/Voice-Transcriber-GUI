"""Eel-based application entry point (replaces CustomTkinter UI)."""
import os
import os
import threading
import json
import eel
import pyautogui
import pyperclip
from dotenv import load_dotenv
import recorder
import keyboard
from overlay_manager import init_overlay, show_overlay, set_paused_overlay, destroy_overlay
from tray import init_tray, shutdown_tray

load_dotenv()

WEB_DIR = 'web'
SETTINGS_FILE = 'settings.json'

# ---------------- Settings Management -----------------
_settings_lock = threading.Lock()
settings = {
    "shortcut_mode": "toggle",           # toggle | hold
    "shortcut_key_toggle": "ctrl+alt+shift+r",  # combination for toggle mode
    "shortcut_key_hold": "ctrl",         # single key for hold mode
    "auto_paste": True,
    "silence_threshold": 50,
    "gemini_api_key": "",
    "speech_provider": "Gemini",         # future: Groq, etc.
    "transcri_brain": {
        "enabled": True,
        "provider": "Gemini",
        "prompt": """**Objective:** You are a transcript model. Your task is to transcribe the provided audio file into clean, readable text. You must preserve the original language and native script of all spoken words, and intelligently infer correct terms based on context where pronunciation is ambiguous.

**Instructions for Your Transcription:**

1.  **Transcribe Audio:** Convert the audio content (provided directly with this prompt) to text.
2.  **Remove Disfluencies:** You are to eliminate filler words and self-corrections (e.g., "um," "uh," "like," "you know," "I mean," "sort of").
3.  **Intelligent Error Correction & Clarification:**
    *   You should fix obvious minor slips of the tongue or grammatical errors *only if the speaker's intended meaning is unequivocally clear*. Do not alter the original meaning.
    *   **Contextual Inference for Ambiguous/Technical Terms:** If a specific term (especially a technical term, product name, or proper noun) is slightly mispronounced, slurred, or acoustically unclear, you must leverage the surrounding context to infer and transcribe the most probable correct term.
        *   **Example:** If the audio sounds like "please fix this socketye-oh connection in that Python script," and "socket IO" is a highly plausible and common term in the context of a "Python script," you should transcribe it as "socket IO."
        *   This applies when the audio might be ambiguous but the context provides strong clues to the intended word.
    *   **Constraint:** This inference should only be applied when the contextual evidence is strong and the inferred term significantly improves clarity and accuracy without altering the speaker's core message. You must avoid speculative guessing if context is weak.

4.  **Preserve Original Language & Script (No Translation, No Transliteration to Latin Script):**
    *   You must transcribe all words *exactly* as spoken in their original language, using their native script.
    *   If the audio contains mixed languages (e.g., English and Arabic), you are to transcribe words in their respective languages *and scripts* without translation.
    *   **Crucial Example:** If a speaker says "hello man انت فاكرني", your transcription *must* be "hello man انت فاكرني". It should *NOT* be "hello man enta fakerny" or "hello man you remember me". The Arabic words must remain in Arabic script.
5.  **Formatting:** You should include line breaks as needed for readability (e.g., for new speakers or logical breaks in thought).

**Input:** Audio file (provided directly with this message/prompt).
**Output:** Cleaned, contextually-aware text transcript with original languages and scripts preserved."""}
}

_hold_registered_key = None
_toggle_registered_combo = None

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            with _settings_lock:
                settings.update(data)
        except Exception as e:
            print('Failed to load settings:', e)

def save_settings():
    try:
        with _settings_lock:
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print('Failed to save settings:', e)


def _unregister_hotkeys():
    global _hold_registered_key, _toggle_registered_combo
    try:
        keyboard.unhook_all()
    except Exception:
        pass
    _hold_registered_key = None
    _toggle_registered_combo = None


def _register_hotkeys():
    """Apply current settings to global hotkey registrations."""
    _unregister_hotkeys()
    mode = settings.get('shortcut_mode', 'toggle')
    if mode == 'toggle':
        combo = settings.get('shortcut_key_toggle', 'ctrl+alt+shift+r')
        try:
            keyboard.add_hotkey(combo, lambda: (start_recording() if not recorder.recording else stop_recording()))
            global _toggle_registered_combo
            _toggle_registered_combo = combo
            print('Registered toggle hotkey:', combo)
        except Exception as e:
            print('Failed to register toggle hotkey:', e)
    else:  # hold
        key = settings.get('shortcut_key_hold', 'ctrl')
        def _on_press():
            if not recorder.recording:
                start_recording()
        def _on_release():
            if recorder.recording:
                stop_recording()
        try:
            keyboard.on_press_key(key, lambda _e: _on_press())
            keyboard.on_release_key(key, lambda _e: _on_release())
            global _hold_registered_key
            _hold_registered_key = key
            print('Registered hold key:', key)
        except Exception as e:
            print('Failed to register hold key:', e)

# ---------------- Core Recording Actions -----------------

@eel.expose
def start_recording():
    if recorder.recording:
        return {"status": "already_recording"}
    recorder.stop_event.clear()
    recorder.pause_event.clear()
    recorder.cancelled = False
    recorder.recording = True
    recorder.set_paused(False)
    # Bump session id so older threads become stale
    import time
    recorder.active_session_id = time.time_ns()
    # Start capture thread BEFORE playing start sound to avoid missing early speech
    threading.Thread(target=recorder.process_speech, kwargs={'session_id': recorder.active_session_id}, daemon=True).start()
    try:
        recorder.play_audio("audio/start.wav")
    except Exception as e:
        print("Audio feedback (start) failed:", e)
    show_overlay()
    return {"status": "started"}

@eel.expose
def stop_recording():
    if not recorder.recording:
        return {"status": "not_recording"}
    recorder.stop_event.set()
    recorder.recording = False
    try:
        recorder.play_audio("audio/stop.wav")
    except Exception as e:
        print("Audio feedback (stop) failed:", e)
    destroy_overlay()
    return {"status": "stopping"}

@eel.expose
def cancel_recording():
    if not recorder.recording:
        return {"status": "not_recording"}
    recorder.cancelled = True
    recorder.stop_event.set()
    recorder.recording = False
    try:
        recorder.play_audio("audio/cancel.wav")
    except Exception as e:
        print("Audio feedback (cancel) failed:", e)
    destroy_overlay()
    return {"status": "cancelled"}

@eel.expose
def restart_recording():
    """Discard current recording (no transcription) and immediately start a fresh capture."""
    if not recorder.recording:
        # If not already recording just start
        return start_recording()
    # Mark current as cancelled so process_speech skips transcription
    recorder.cancelled = True
    recorder.stop_event.set()
    recorder.recording = False
    try:
        recorder.play_audio("audio/stop.wav")
    except Exception:
        pass
    # Start new one
    return start_recording()

@eel.expose
def toggle_pause():
    current = recorder.pause_event.is_set()
    recorder.set_paused(not current)
    set_paused_overlay(recorder.pause_event.is_set())
    try:
        recorder.play_audio("audio/pause.wav")
    except Exception as e:
        print("Audio feedback (pause) failed:", e)
    return {"paused": recorder.pause_event.is_set()}

@eel.expose
def get_state():
    return {
        "recording": recorder.recording,
        "paused": recorder.pause_event.is_set(),
    }

def _on_transcription_done(text: str):
    # Eel (web) UI transcription completion handler.
    # Note: A similarly named method exists in ui.RecorderApp for the legacy Tk UI.
    # They are separate on purpose: this one updates the browser via eel, the other updates Tk widgets.
    # If you fully migrated to Eel, you can delete ui.py and remove app fallback logic in recorder.py.
    # Optional post-processing placeholder (transcri_brain) could be applied here using settings['transcri_brain']
    auto_paste = settings.get('auto_paste', True)
    if auto_paste:
        try:
            pyperclip.copy(text + ' ')
            pyautogui.hotkey('ctrl', 'v')
        except Exception:
            pass
    eel.transcriptionResult(text)
    try:
        recorder.play_audio("audio/done.wav")
    except Exception as e:
        print("Audio feedback (done) failed:", e)

def _on_recording_completed():
    eel.recordingCompleted()

recorder.set_callbacks(
    on_transcription_done=_on_transcription_done,
    on_recording_completed=_on_recording_completed,
)

# ---------------- Eel Exposed Settings APIs -----------------
@eel.expose
def get_settings():
    with _settings_lock:
        return settings

@eel.expose
def update_settings(new_values: dict):
    changed_keys = []
    with _settings_lock:
        for k, v in new_values.items():
            if k in settings:
                if isinstance(settings[k], dict) and isinstance(v, dict):
                    settings[k].update(v)
                else:
                    settings[k] = v
                changed_keys.append(k)
    save_settings()
    # Apply runtime effects
    if 'silence_threshold' in new_values:
        try:
            recorder.set_silence_threshold(new_values.get('silence_threshold'))
        except Exception:
            pass
    if any(k.startswith('shortcut_') or k == 'shortcut_mode' for k in changed_keys):
        _register_hotkeys()
    return {"updated": changed_keys}

@eel.expose
def set_silence_threshold(value):
    """Directly set silence threshold and persist to settings."""
    try:
        recorder.set_silence_threshold(value)
        with _settings_lock:
            settings['silence_threshold'] = int(float(value))
        save_settings()
        return {"ok": True, "silence_threshold": settings['silence_threshold']}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@eel.expose
def calibrate_silence_threshold(duration_sec: float = 2.0):
    """Listen to ambient noise and compute a suggested silence threshold.

    Returns result dict with ambient stats and chosen threshold; applies and persists it.
    """
    try:
        result = recorder.calibrate_noise_floor(duration_sec)
        threshold = int(float(result.get('threshold', 50)))
        recorder.set_silence_threshold(threshold)
        with _settings_lock:
            settings['silence_threshold'] = threshold
        save_settings()
        return {"ok": True, **result}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def main():
    # Always load persisted settings first
    load_settings()
    # Apply silence threshold to recorder
    try:
        recorder.set_silence_threshold(settings.get('silence_threshold', 50))
    except Exception:
        pass
    if not os.environ.get("GEMINI_API_KEY"):
        print("WARNING: GEMINI_API_KEY not set in environment variables or .env file")
        # Load user settings (including optional API key)
        load_settings()
        # Apply stored API key if provided, else fall back to environment
        api_key = settings.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY")
        if api_key:
            os.environ["GEMINI_API_KEY"] = api_key
        else:
            print("WARNING: GEMINI_API_KEY not set; please enter it in API Keys view")
    eel.init(WEB_DIR)
    init_overlay(
        pause_toggle_cb=lambda: toggle_pause(),
        stop_cb=lambda: stop_recording(),
        cancel_cb=lambda: cancel_recording(),
        restart_cb=lambda: restart_recording(),
    )
    _register_hotkeys()

    # System tray integration: run eel in non-blocking mode
    def _on_closed(_path, _pages):
        # Intercept window close -> just hide window; keep app alive in tray
        print('Main window closed (hidden to tray).')
        # There is no direct hide in eel; front-end window will close, user can re-open from tray
        return False  # prevent eel from shutting down server

    # Launch eel (non-blocking)
    eel.start('index.html', size=(980, 640), port=0, block=False, close_callback=_on_closed)

    # Tray callbacks
    def show_ui():
        try:
            eel.show('index.html')  # may not exist; alternative is spawning browser again
        except Exception:
            # Fallback: relaunch a new window using eel.start in a thread (simpler: open in default browser)
            try:
                import webbrowser
                webbrowser.open_new(f'http://localhost:{eel._websocket.port}')  # internal port
            except Exception:
                pass

    def quit_app():
        print('Quitting application from tray...')
        shutdown_tray()
        os._exit(0)

    def tray_start_record():
        start_recording()

    def tray_stop_record():
        stop_recording()

    init_tray(
        icon_path='icon.png',
        show=show_ui,
        quit=quit_app,
        start_record=tray_start_record,
        stop_record=tray_stop_record,
    )

    print('Application running in background (tray). Close the window or use tray menu to quit.')
    # Keep main thread alive
    try:
        while True:
            eel.sleep(1.0)
    except KeyboardInterrupt:
        quit_app()

if __name__ == '__main__':
    main()

