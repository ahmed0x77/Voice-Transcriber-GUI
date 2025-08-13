import os
import threading
import keyboard
import customtkinter as ctk


class RecordingOverlay(ctk.CTkToplevel):
    """Floating pill-style overlay while recording, styled like the provided design.

    Layout:
    [ dark pill ]  ┌────────────────────────────────────────────────────────────┐
                   │  [■  0:04]  |   ↻    ⏸/▶    🗑                             │
                   └────────────────────────────────────────────────────────────┘
    - Clicking the left status pill (red square + timer) stops/finalizes.
    - ↻ mapped to finalize as well (acts as stop in this app).
    - ⏸/▶ toggles pause.
    - 🗑 cancels the recording.
    """

    def __init__(self, master, on_pause_toggle, on_stop, on_cancel):
        super().__init__(master)

        # Window chrome
        self.withdraw()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        try:
            self.attributes("-alpha", 0.97)
        except Exception:
            pass

        # --- Transparent corners fix (Windows) ---
        # We give the toplevel a unique background color and set it as a transparent color key
        # so only the rounded container frame is visible (no black square corners).
        # This avoids the black corners you observed around the pill overlay.
        self._transparent_color = "#010101"  # Rarely used near-black distinct color
        try:
            # Tk 8.6+ on Windows supports -transparentcolor; wrap in try for cross‑platform safety.
            self.configure(fg_color=self._transparent_color)
            self.attributes("-transparentcolor", self._transparent_color)
        except Exception:
            # Fallback: keep a dark background (will show square on platforms lacking support)
            self.configure(fg_color="#000000")

        # Callbacks
        self.on_pause_toggle = on_pause_toggle
        self.on_stop = on_stop
        self.on_cancel = on_cancel

        # State
        self.is_paused = False
        self._seconds_elapsed = 0
        self._timer_job_id = None
        # Root background already set (possibly transparent). Inner rounded frame is the visible pill.
        self.container = ctk.CTkFrame(self, fg_color="#1b1b1b", corner_radius=28)
        self.container.pack(fill="both", expand=True)
        self.container.pack_propagate(False)

        # Inner layout - pack left to right
        # Left status pill (red indicator + timer)
        self.status_pill = ctk.CTkFrame(self.container, fg_color="#2a2a2a", corner_radius=16)
        self.status_pill.pack(side="left", padx=(12, 8), pady=12)
        self.status_pill.pack_propagate(False)
        self.status_pill.configure(width=170, height=40)

        # Recording icon: orange circle + white square (stop symbol)
        self.rec_indicator = ctk.CTkFrame(
            self.status_pill,
            width=36,
            height=36,
            corner_radius=18,
            fg_color="#ff6a45"
        )
        self.rec_indicator.pack(side="left", padx=(12, 10), pady=2)
        self.rec_indicator.pack_propagate(False)
        self.rec_inner_stop = ctk.CTkFrame(
            self.rec_indicator,
            width=16,
            height=16,
            corner_radius=4,
            fg_color="white"
        )
        self.rec_inner_stop.place(relx=0.5, rely=0.5, anchor="center")

        self.timer_label = ctk.CTkLabel(self.status_pill, text="0:00", text_color="white", font=("Segoe UI", 18, "bold"))
        self.timer_label.pack(side="left", padx=(0, 14))

        # Clicking the status pill finalizes/stop
        for widget in (self.status_pill, self.rec_indicator, self.timer_label):
            widget.bind("<Button-1>", lambda _e: self.on_stop())

        # Vertical divider
        self.divider = ctk.CTkFrame(self.container, width=2, height=36, fg_color="#2a2a2a")
        self.divider.pack(side="left", padx=6, pady=14)

        # Icon button helper
        def make_icon(text: str, command):
            return ctk.CTkButton(
                self.container,
                text=text,
                width=40,
                height=40,
                corner_radius=20,
                fg_color="transparent",
                hover_color="#2a2a2a",
                text_color="white",
                font=("Segoe UI Symbol", 20, "bold"),
                command=command,
            )

        # Icons: restart (actual restart logic), pause/resume, delete
        self.restart_button = make_icon("↻", lambda: self.master.restart_recording())
        self.restart_button.pack(side="left", padx=4, pady=10)

        self.pause_button = make_icon("⏸", self.on_pause_toggle)
        self.pause_button.pack(side="left", padx=4, pady=10)

        self.delete_button = make_icon("🗑", self.on_cancel)
        self.delete_button.pack(side="left", padx=(4, 12), pady=10)

        # Drag to move from anywhere on the container
        self._offset_x = 0
        self._offset_y = 0
        for drag_widget in (self.container, self.status_pill, self.divider):
            drag_widget.bind("<Button-1>", self._start_move)
            drag_widget.bind("<B1-Motion>", self._on_move)

        # Place and start timer
        self.bind("<Destroy>", self._on_destroy)
        self.after(10, self._place_initial)
        self._schedule_tick()

    # Window placement: bottom-center, nice width/height for the pill
    def _place_initial(self):
        try:
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
            width, height = 460, 64
            x = int((screen_w - width) / 2)
            y = int(screen_h - height - 96)
            self.geometry(f"{width}x{height}+{x}+{y}")
        finally:
            self.deiconify()

    # Dragging helpers
    def _start_move(self, event):
        self._offset_x = event.x
        self._offset_y = event.y

    def _on_move(self, event):
        x = self.winfo_pointerx() - self._offset_x
        y = self.winfo_pointery() - self._offset_y
        self.geometry(f"+{x}+{y}")

    # Timer
    def _schedule_tick(self):
        self._timer_job_id = self.after(1000, self._tick)

    def _tick(self):
        try:
            if self.winfo_exists() and not self.is_paused:
                self._seconds_elapsed += 1
                minutes = self._seconds_elapsed // 60
                seconds = self._seconds_elapsed % 60
                self.timer_label.configure(text=f"{minutes}:{seconds:02d}")
        finally:
            # Continue ticking unless destroyed
            if self.winfo_exists():
                self._schedule_tick()

    def _on_destroy(self, _event=None):
        if self._timer_job_id is not None:
            try:
                self.after_cancel(self._timer_job_id)
            except Exception:
                pass
            self._timer_job_id = None

    # External control from the app
    def set_paused(self, is_paused: bool):
        self.is_paused = is_paused
        try:
            if self.winfo_exists():
                self.pause_button.configure(text="▶" if is_paused else "⏸")
                # Dim the circle color when paused
                self.rec_indicator.configure(fg_color="#ffa089" if is_paused else "#ff6a45")
        except Exception:
            pass

    def reset_timer(self):
        """Reset the overlay timer display to 0:00."""
        self._seconds_elapsed = 0
        try:
            if self.winfo_exists():
                self.timer_label.configure(text="0:00")
        except Exception:
            pass


class RecorderApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.title("Voice to Text (Gemini)")
        try:
            if os.path.exists("icon.ico"):
                self.iconbitmap("icon.ico")
        except Exception:
            pass

        self.geometry("520x360")
        self.minsize(520, 360)

        # State / vars
        self.auto_paste_var = ctk.BooleanVar(value=True)
        self.status_var = ctk.StringVar(value="Idle")
        self.overlay = None
        self._recording_thread = None  # track active recording thread

        # Header
        header = ctk.CTkLabel(self, text="Speech to Text", font=("Segoe UI", 20, "bold"))
        header.pack(pady=(16, 8))

        # Status
        self.status_label = ctk.CTkLabel(self, textvariable=self.status_var)
        self.status_label.pack()

        # Controls
        controls = ctk.CTkFrame(self)
        controls.pack(fill="x", padx=16, pady=12)
        self.record_button = ctk.CTkButton(controls, text="Start Recording", height=36, command=self.start_recording)
        self.record_button.pack(side="left", padx=(12, 8), pady=12)
        self.pause_button = ctk.CTkButton(controls, text="Pause", height=36, state="disabled", command=self.toggle_pause)
        self.pause_button.pack(side="left", padx=8, pady=12)
        self.stop_button = ctk.CTkButton(controls, text="Stop", height=36, state="disabled", command=self.stop_recording)
        self.stop_button.pack(side="left", padx=8, pady=12)
        self.auto_paste_switch = ctk.CTkSwitch(controls, text="Auto paste result", variable=self.auto_paste_var)
        self.auto_paste_switch.pack(side="right", padx=12)

        # Transcript box
        self.transcript_box = ctk.CTkTextbox(self, wrap="word")
        self.transcript_box.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.transcript_box.insert("end", "Transcriptions will appear here. Press 'Start Recording' or use Ctrl+Alt+Shift+R.")
        self.transcript_box.configure(state="disabled")

        # Hotkey
        try:
            keyboard.add_hotkey('ctrl+alt+shift+r', self.toggle_recording)
        except Exception:
            pass

        # API key notice
        if not os.environ.get("GEMINI_API_KEY"):
            self.status_var.set("Warning: GEMINI_API_KEY is not set")

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # --- Helpers ---
    def _set_recording_ui(self, is_recording: bool):
        self.record_button.configure(state="disabled" if is_recording else "normal",
                                     text="Recording..." if is_recording else "Start Recording")
        self.pause_button.configure(state="normal" if is_recording else "disabled")
        self.stop_button.configure(state="normal" if is_recording else "disabled")
        self.status_var.set("Recording" if is_recording else "Idle")

    def _ensure_overlay(self):
        if self.overlay is None or not self.overlay.winfo_exists():
            self.overlay = RecordingOverlay(self, self.toggle_pause, self.stop_recording, self.cancel_recording)
        return self.overlay

    def _safe_destroy_overlay(self):
        if self.overlay is not None:
            try:
                if self.overlay.winfo_exists():
                    self.after(0, self._destroy_overlay_safe)
            except Exception:
                self.overlay = None

    def _destroy_overlay_safe(self):
        if self.overlay is not None:
            try:
                if self.overlay.winfo_exists():
                    self.overlay.destroy()
            except Exception:
                pass
            finally:
                self.overlay = None

    # --- Actions ---
    def start_recording(self):
        import recorder
        if recorder.recording:
            return
        try:
            recorder.play_audio("audio/start.wav")
        except Exception:
            pass
        recorder.stop_event.clear()
        recorder.pause_event.clear()
        recorder.cancelled = False
        recorder.recording = True
        recorder.set_paused(False)
        self._set_recording_ui(True)
        self._ensure_overlay()
        t = threading.Thread(target=recorder.process_speech, daemon=True)
        self._recording_thread = t
        t.start()

    def stop_recording(self):
        import recorder
        if not recorder.recording:
            return
        try:
            recorder.play_audio("audio/stop.wav")
        except Exception:
            pass
        recorder.stop_event.set()
        recorder.recording = False
        self._set_recording_ui(False)
        self._safe_destroy_overlay()

    def cancel_recording(self):
        import recorder
        if not recorder.recording:
            return
        try:
            recorder.play_audio("audio/cancel.wav")
        except Exception:
            pass
        recorder.cancelled = True
        recorder.stop_event.set()
        recorder.recording = False
        self._set_recording_ui(False)
        self._safe_destroy_overlay()
        self.status_var.set("Recording cancelled")

    def toggle_pause(self):
        import recorder
        current = recorder.pause_event.is_set()
        recorder.set_paused(not current)
        try:
            if self.overlay and self.overlay.winfo_exists():
                self.overlay.set_paused(recorder.pause_event.is_set())
        except Exception:
            pass
        self.pause_button.configure(text="Resume" if recorder.pause_event.is_set() else "Pause")
        self.status_var.set("Paused" if recorder.pause_event.is_set() else "Recording")
        try:
            recorder.play_audio("audio/pause.wav")
        except Exception:
            pass

    def restart_recording(self):
        """Reset timer & discard current audio without transcribing, then start fresh.
        Avoids duplicate recording threads by waiting for old thread to finish."""
        import recorder
        old_thread = self._recording_thread
        if recorder.recording:
            recorder.cancelled = True
            recorder.stop_event.set()
            recorder.recording = False
            try:
                recorder.play_audio("audio/stop.wav")
            except Exception:
                pass
        ov = self._ensure_overlay()
        try:
            if ov and ov.winfo_exists():
                ov.reset_timer()
                ov.set_paused(False)
        except Exception:
            pass

        def _wait_then_start():
            if old_thread is not None and old_thread.is_alive():
                self.after(50, _wait_then_start)
                return
            recorder.stop_event.clear()
            recorder.pause_event.clear()
            recorder.cancelled = False
            recorder.recording = True
            recorder.set_paused(False)
            self._set_recording_ui(True)
            try:
                recorder.play_audio("audio/start.wav")
            except Exception:
                pass
            new_t = threading.Thread(target=recorder.process_speech, daemon=True)
            self._recording_thread = new_t
            new_t.start()

        _wait_then_start()

    def toggle_recording(self):
        import recorder
        if not recorder.get_recording_state():
            self.after(0, self.start_recording)
        else:
            self.after(0, self.stop_recording)

    def on_transcription_done(self, text: str):
        if self.auto_paste_var.get():
            import pyautogui
            pyautogui.hotkey('ctrl', 'v')

        self.transcript_box.configure(state="normal")
        self.transcript_box.delete("1.0", "end")
        self.transcript_box.insert("end", text)
        self.transcript_box.configure(state="disabled")
        try:
            import recorder
            recorder.play_audio("audio/done.wav")
        except Exception:
            pass

    def on_recording_completed(self):
        self._set_recording_ui(False)
        self._safe_destroy_overlay()

    def on_close(self):
        import recorder
        recorder.stop_event.set()
        try:
            self.destroy()
        except Exception:
            os._exit(0)
