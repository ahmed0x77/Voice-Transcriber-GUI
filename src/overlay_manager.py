"""CustomTkinter recording overlay manager used alongside the Eel web UI.

Retains the original floating pill overlay while primary UI is in browser.
"""
import threading
import customtkinter as ctk

USE_OVERLAY = True

_root = None
_overlay = None
_thread = None

_callbacks = {
    'pause_toggle': None,
    'stop': None,
    'cancel': None,
    'restart': None,
}

class RecordingOverlay(ctk.CTkToplevel):
    def __init__(self, master, on_pause_toggle, on_stop, on_cancel, on_restart):
        super().__init__(master)

        # Window setup
        self.withdraw()
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        try:
            self.attributes('-alpha', 0.97)
        except Exception:
            pass

        # Transparency (rounded pill)
        self._transparent_color = '#010101'
        try:
            self.configure(fg_color=self._transparent_color)
            self.attributes('-transparentcolor', self._transparent_color)
        except Exception:
            self.configure(fg_color='#000000')

        # Callbacks
        self.on_pause_toggle = on_pause_toggle
        self.on_stop = on_stop
        self.on_cancel = on_cancel
        self.on_restart = on_restart

        # State
        self.is_paused = False
        self._seconds_elapsed = 0
        self._timer_job_id = None

        # Container
        self.container = ctk.CTkFrame(self, fg_color='#1b1b1b', corner_radius=28, border_width=2, border_color='#2E2E2E')
        self.container.pack(fill='both', expand=True)
        self.container.pack_propagate(False)

        # Status pill (indicator + timer)
        self.status_pill = ctk.CTkFrame(self.container, fg_color='#2a2a2a', corner_radius=16)
        self.status_pill.pack(side='left', padx=(12, 8), pady=12)
        self.status_pill.pack_propagate(False)
        self.status_pill.configure(width=170, height=40)

        self.rec_indicator = ctk.CTkFrame(self.status_pill, width=36, height=36, corner_radius=18, fg_color='#ff6a45')
        self.rec_indicator.pack(side='left', padx=(12, 10), pady=2)
        self.rec_indicator.pack_propagate(False)
        self.rec_inner_stop = ctk.CTkFrame(self.rec_indicator, width=16, height=16, corner_radius=4, fg_color='white')
        self.rec_inner_stop.place(relx=0.5, rely=0.5, anchor='center')

        self.timer_label = ctk.CTkLabel(self.status_pill, text='0:00', text_color='white', font=('Segoe UI', 18, 'bold'))
        self.timer_label.pack(side='left', padx=(0, 14))
        for w in (self.status_pill, self.rec_indicator, self.timer_label, self.rec_inner_stop):
            w.bind('<Button-1>', lambda _e: self.on_stop())
            w.configure(cursor='hand2')

        # Divider
        self.divider = ctk.CTkFrame(self.container, width=2, height=36, fg_color='#2a2a2a')
        self.divider.pack(side='left', padx=6, pady=14)

        # Icon button factory
        def make_icon(text, command):
            return ctk.CTkButton(
                self.container,
                text=text,
                width=40,
                height=40,
                corner_radius=20,
                fg_color='transparent',
                hover_color='#2a2a2a',
                text_color='white',
                font=('Segoe UI Symbol', 20, 'bold'),
                command=command,
            )

        # Buttons
        self.restart_button = make_icon('↻', self.on_restart)
        self.restart_button.pack(side='left', padx=4, pady=10)
        self.pause_button = make_icon('⏸', self.on_pause_toggle)
        self.pause_button.pack(side='left', padx=4, pady=10)
        self.delete_button = make_icon('🗑', self.on_cancel)
        self.delete_button.pack(side='left', padx=(4, 12), pady=10)

        # Dragging
        self._offset_x = 0
        self._offset_y = 0
        for drag_widget in (self.container, self.status_pill, self.divider):
            drag_widget.bind('<Button-1>', self._start_move)
            drag_widget.bind('<B1-Motion>', self._on_move)

        # Lifecycle
        self.bind('<Destroy>', self._on_destroy)
        self.after(10, self._place_initial)
        self._schedule_tick()

    def _place_initial(self):
        try:
            sw = self.winfo_screenwidth(); sh = self.winfo_screenheight()
            width, height = 460, 64
            x = int((sw - width) / 2); y = int(sh - height - 96)
            self.geometry(f"{width}x{height}+{x}+{y}")
        finally:
            self.deiconify()

    def _start_move(self, event):
        self._offset_x = event.x; self._offset_y = event.y

    def _on_move(self, event):
        x = self.winfo_pointerx() - self._offset_x
        y = self.winfo_pointery() - self._offset_y
        self.geometry(f"+{x}+{y}")

    def _schedule_tick(self):
        self._timer_job_id = self.after(1000, self._tick)

    def _tick(self):
        try:
            if self.winfo_exists() and not self.is_paused:
                self._seconds_elapsed += 1
                m = self._seconds_elapsed // 60; s = self._seconds_elapsed % 60
                self.timer_label.configure(text=f"{m}:{s:02d}")
        finally:
            if self.winfo_exists():
                self._schedule_tick()

    def _on_destroy(self, _):
        if self._timer_job_id:
            try: self.after_cancel(self._timer_job_id)
            except Exception: pass
            self._timer_job_id = None

    def set_paused(self, value: bool):
        self.is_paused = value
        try:
            self.pause_button.configure(text='▶' if value else '⏸')
            self.rec_indicator.configure(fg_color='#ffa089' if value else '#ff6a45')
        except Exception:
            pass

    def reset(self):
        self._seconds_elapsed = 0
        try: self.timer_label.configure(text='0:00')
        except Exception: pass


def _tk_thread():
    global _root
    ctk.set_appearance_mode('System')
    _root = ctk.CTk()
    _root.withdraw()
    _root.protocol('WM_DELETE_WINDOW', lambda: None)
    _root.mainloop()


def init_overlay(pause_toggle_cb, stop_cb, cancel_cb, restart_cb):
    if not USE_OVERLAY:
        return
    global _thread
    _callbacks['pause_toggle'] = pause_toggle_cb
    _callbacks['stop'] = stop_cb
    _callbacks['cancel'] = cancel_cb
    _callbacks['restart'] = restart_cb
    if _thread is None or not _thread.is_alive():
        _thread = threading.Thread(target=_tk_thread, daemon=True)
        _thread.start()


def show_overlay():
    if not USE_OVERLAY:
        return
    def _create():
        global _overlay
        if _overlay is None or not _overlay.winfo_exists():
            _overlay = RecordingOverlay(
                _root,
                on_pause_toggle=_callbacks['pause_toggle'],
                on_stop=_callbacks['stop'],
                on_cancel=_callbacks['cancel'],
                on_restart=_callbacks['restart'],
            )
        else:
            _overlay.reset(); _overlay.set_paused(False); _overlay.deiconify()
    if _root:
        _root.after(0, _create)


def set_paused_overlay(value: bool):
    if not USE_OVERLAY or _root is None:
        return
    def _p():
        if _overlay and _overlay.winfo_exists():
            _overlay.set_paused(value)
    _root.after(0, _p)


def destroy_overlay():
    if not USE_OVERLAY or _root is None:
        return
    def _d():
        global _overlay
        if _overlay and _overlay.winfo_exists():
            try: _overlay.destroy()
            except Exception: pass
        _overlay = None
    _root.after(0, _d)
