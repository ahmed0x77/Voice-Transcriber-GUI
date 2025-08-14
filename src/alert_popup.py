"""Popup alerts (Windows-first) for missing or invalid Gemini API key.

Uses native Windows MessageBox (thread-safe enough for simple notifications) for reliability.
Falls back to a temporary Tk messagebox if native call fails and we're on main thread.
"""
from __future__ import annotations

import threading

def _win_messagebox(title: str, message: str, flags: int) -> bool:
    """Attempt to show a Windows native message box.

    flags example: 0x00000040 (MB_ICONWARNING) | 0x00001000 (MB_SYSTEMMODAL)
    Returns True if shown, False if it failed (e.g., non-Windows platform).
    """
    try:
        import ctypes  # noqa
        ctypes.windll.user32.MessageBoxW(0, message, title, flags)
        return True
    except Exception:
        return False

def _tk_fallback(kind: str, title: str, message: str):
    import threading as _th
    if _th.current_thread() is not _th.main_thread():
        # Avoid creating Tk in a worker thread.
        return
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk(); root.withdraw()
        if kind == 'warn':
            messagebox.showwarning(title, message)
        else:
            messagebox.showerror(title, message)
        try:
            root.destroy()
        except Exception:
            pass
    except Exception:
        pass

def show_missing_api_key_popup():
    msg = (
        "Gemini API key is not set.\n\n"
        "How to fix:\n"
        "1. Open the app window -> API Keys tab.\n"
        "2. Paste your Gemini API key (it auto-saves).\n"
        "OR create a .env file with: GEMINI_API_KEY=your_key_here"
    )
    if not _win_messagebox("API Key Required", msg, 0x00000040 | 0x00001000):  # Warning + System modal
        _tk_fallback('warn', "API Key Required", msg)

def show_invalid_api_key_popup(error_text: str | None = None):
    msg_lines = [
        "Gemini API request failed.",
        "\nWhat to do:",
        "1. Verify the Gemini API key is correct and active.",
        "2. Check your internet connection.",
        "3. If newly created, wait a minute and retry.",
        "4. Update the key in the API Keys tab or your .env file.",
    ]
    if error_text:
        msg_lines.append("\nRaw error: " + error_text.strip())
    msg = "\n".join(msg_lines)
    if not _win_messagebox("Gemini Error", msg, 0x00000010 | 0x00001000):  # Error icon + System modal
        _tk_fallback('error', "Gemini Error", msg)
