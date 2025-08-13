import threading
import os
import sys
from typing import Callable, Optional

try:
    import pystray
    from PIL import Image
except Exception as e:  # pragma: no cover
    pystray = None
    Image = None

# Store pystray icon instance without static type annotation (pystray may be missing at import time)
_icon_instance = None  # will hold pystray.Icon instance
_thread: Optional[threading.Thread] = None

_tray_callbacks = {
    'show': None,        # type: Optional[Callable[[], None]]
    'quit': None,        # type: Optional[Callable[[], None]]
    'start_record': None,
    'stop_record': None,
}


def _load_icon(path: str):
    if Image is None:
        return None
    try:
        return Image.open(path)
    except Exception:
        return None


def init_tray(icon_path: str = 'icon.png', **callbacks):
    """Initialize and start the system tray icon in a background thread.

    callbacks: show (show UI), quit (terminate), start_record, stop_record
    """
    global _thread
    for k, v in callbacks.items():
        if k in _tray_callbacks:
            _tray_callbacks[k] = v

    if pystray is None:
        print('pystray not available; tray icon disabled')
        return

    if _thread and _thread.is_alive():
        return

    _thread = threading.Thread(target=_run_tray, args=(icon_path,), daemon=True)
    _thread.start()


def _run_tray(icon_path: str):
    global _icon_instance
    image = _load_icon(icon_path) or _fallback_image()

    menu = pystray.Menu(
        # Default action on click: Show Window
        pystray.MenuItem('Show Window', lambda: _safe_call('show'), default=True),
        pystray.MenuItem('Start Recording', lambda: _safe_call('start_record')),
        pystray.MenuItem('Stop Recording', lambda: _safe_call('stop_record')),
        pystray.MenuItem('Quit', lambda: _safe_call('quit')),
    )
    _icon_instance = pystray.Icon('smart_audio_transcript', image, 'Smart Audio Transcript', menu)
    try:
        _icon_instance.run()
    except Exception as e:
        print('Tray icon failed:', e)


def _fallback_image():
    if Image is None:
        return None
    from PIL import ImageDraw
    img = Image.new('RGB', (64, 64), color=(30, 30, 30))
    d = ImageDraw.Draw(img)
    d.ellipse((16, 16, 48, 48), fill=(255, 90, 60))
    return img


def _safe_call(name: str):
    cb = _tray_callbacks.get(name)
    if cb:
        try:
            cb()
        except Exception as e:
            print(f'Tray callback {name} error:', e)


def notify(message: str):  # Placeholder for future Windows toast integration
    print('[Tray]', message)


def shutdown_tray():
    global _icon_instance
    if _icon_instance:
        try:
            _icon_instance.stop()
        except Exception:
            pass
        _icon_instance = None
