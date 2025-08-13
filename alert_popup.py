"""Centralized Tkinter-based popup alerts for the application.

Two primary alerts required by user:
1. Missing API key when user attempts to start recording the first time.
2. Invalid / failing Gemini API key after a transcription attempt.

These popups are lightweight and independent from the main (eel) UI / overlay.
They create (or reuse) a hidden Tk root so they can be called safely from any thread.
"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox

_root = None
_root_lock = threading.Lock()

def _get_root():
    global _root
    if _root and _root.winfo_exists():
        return _root
    with _root_lock:
        if _root and _root.winfo_exists():
            return _root
        _root = tk.Tk()
        _root.withdraw()  # Keep root hidden
        _root.title("Smart Audio Transcript")
    return _root

def _show_async(func, *args, **kwargs):
    """Ensure popup executes in Tk main thread; create a temporary loop if needed."""
    root = _get_root()
    try:
        # If called from a non-main thread, schedule via after
        root.after(0, lambda: func(*args, **kwargs))
    except Exception:
        pass

def show_missing_api_key_popup():
    """Show instructions when user tries to record without setting an API key."""
    instructions = (
        "Gemini API key is not set.\n\n"
        "To fix: Open the app window -> 'API Keys' tab -> paste your Gemini API key and it will auto-save.\n"
        "Alternatively, create a .env file with: GEMINI_API_KEY=your_key_here"
    )
    _show_async(messagebox.showwarning, "API Key Required", instructions)

def show_invalid_api_key_popup(error_text: str | None = None):
    """Show error when API key fails during transcription."""
    body = [
        "Gemini API request failed.",
        "\nWhat to do:",
        "1. Re-check that your Gemini API key is correct and active.",
        "2. Ensure you have network connectivity.",
        "3. If recently created, wait a minute and retry.",
        "4. Update the key in the 'API Keys' tab or .env file.",
    ]
    if error_text:
        body.append("\nRaw error: " + error_text.strip())
    _show_async(messagebox.showerror, "Gemini Error", "\n".join(body))
