document.addEventListener("DOMContentLoaded", () => {
  // API Key input field
  const apiKeyInput = document.getElementById("apiKeyInput");
  // --- Element Selectors ---
  const views = {
    general: document.getElementById("view-general"),
    "api-keys": document.getElementById("view-api-keys"),
    history: document.getElementById("view-history"),
  };
  const navButtons = document.querySelectorAll(".nav-list button");

  // Settings Controls
  const shortcutModeTabs = document.getElementById("shortcutModeTabs");
  const toggleKeyRow = document.getElementById("toggleKeyRow");
  const holdKeyRow = document.getElementById("holdKeyRow");
  const toggleComboInput = document.getElementById("toggleComboInput");
  const holdKeyInput = document.getElementById("holdKeyInput");

  const modelSelect = document.getElementById("modelSelect");
  const brainPromptTextarea = document.getElementById("brainPrompt");
  const editPromptBtn = document.getElementById("editPromptBtn");
  const savePromptBtn = document.getElementById("savePromptBtn");
  const cancelPromptBtn = document.getElementById("cancelPromptBtn");
  const audioDeviceSelect = document.getElementById("audioDeviceSelect");
  const silenceThresholdInput = document.getElementById("silenceThresholdInput");
  const calibrateBtn = document.getElementById("calibrateBtn");
  const historyList = document.getElementById("history-list");

  // --- Functions ---

  /**
   * Updates the UI to reflect the provided settings object.
   * @param {object} settings The settings object from Python.
   */
  const applySettingsToUI = (settings) => {
    // Shortcut Controls
    const mode = settings.shortcut_mode || "toggle";
    shortcutModeTabs.querySelectorAll("button").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.mode === mode);
    });
    toggleKeyRow.classList.toggle("hidden", mode !== "toggle");
    holdKeyRow.classList.toggle("hidden", mode !== "hold");
    toggleComboInput.value = settings.shortcut_key_toggle || "";
    holdKeyInput.value = settings.shortcut_key_hold || "";

    // Transcri Brain
    if (settings.transcri_brain) {
      brainPromptTextarea.value = settings.transcri_brain.prompt || "";
    }
    // Model
    modelSelect.value = settings.model || "google/gemini-2.5-flash-lite";
    
    // OpenRouter API Key
    apiKeyInput.value = settings.openrouter_api_key || "";
    // Mic
    silenceThresholdInput.value = settings.silence_threshold ?? 50;
    // Audio device will be populated by loadAudioDevices()
  };

  /**
   * Reads all values from the UI, constructs a settings object,
   * and sends it to the Python backend.
   */
  const saveSettings = async () => {
    const activeModeBtn = shortcutModeTabs.querySelector("button.active");
    const mode = activeModeBtn ? activeModeBtn.dataset.mode : "toggle";

    const payload = {
      shortcut_mode: mode,
      shortcut_key_toggle: toggleComboInput.value.trim(),
      shortcut_key_hold: holdKeyInput.value.trim(),
      silence_threshold: Number(silenceThresholdInput.value) || 50,
      audio_device_index: audioDeviceSelect.value === "" ? null : Number(audioDeviceSelect.value),
      // We still need to send the other settings
      model: modelSelect.value,
      transcri_brain: {
        enabled: true, // Always enabled as per previous request
        prompt: brainPromptTextarea.value,
      },
      openrouter_api_key: apiKeyInput.value.trim(),
    };

    try {
      // Update global settings object before sending
      currentSettings = { ...currentSettings, ...payload };
      await eel.update_settings(payload)();
      console.log("Settings saved successfully.");
    } catch (err) {
      console.error("Failed to save settings:", err);
    }
  };

  /**
   * Loads settings from the Python backend.
   */
  let currentSettings = {};
  const loadSettings = async () => {
    try {
      const settings = await eel.get_settings()();
      currentSettings = settings; // Store initial settings
      applySettingsToUI(settings);
    } catch (err) {
      console.error("Failed to load settings:", err);
    }
  };

  // --- Event Listeners ---

  // Navigation
  navButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      navButtons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const viewToShow = btn.dataset.view;
      Object.entries(views).forEach(([key, element]) => {
        element.classList.toggle("hidden", key !== viewToShow);
      });
      
      // Load history when switching to history view
      if (viewToShow === "history") {
        loadHistory();
      }
    });
  });

  // Shortcut Mode Tabs
  shortcutModeTabs.addEventListener("click", (e) => {
    const btn = e.target.closest("button");
    if (!btn) return;

    const mode = btn.dataset.mode;
    shortcutModeTabs.querySelectorAll("button").forEach((b) => {
      b.classList.toggle("active", b === btn);
    });
    toggleKeyRow.classList.toggle("hidden", mode !== "toggle");
    holdKeyRow.classList.toggle("hidden", mode !== "hold");
    saveSettings(); // Save immediately on mode change
  });

  // Auto-saving on change for all relevant controls (except prompt which has manual save)
  [
    toggleComboInput,
    holdKeyInput,
    modelSelect,
    apiKeyInput,
    silenceThresholdInput,
    audioDeviceSelect,
  ].forEach((el) => {
    el.addEventListener("change", saveSettings);
  });

  // Prompt Edit/Save/Cancel functionality
  let originalPromptValue = "";
  
  editPromptBtn.addEventListener("click", () => {
    // Store original value for cancel
    originalPromptValue = brainPromptTextarea.value;
    
    // Enable editing
    brainPromptTextarea.readOnly = false;
    brainPromptTextarea.focus();
    
    // Show save/cancel buttons, hide edit button
    editPromptBtn.classList.add("hidden");
    savePromptBtn.classList.remove("hidden");
    cancelPromptBtn.classList.remove("hidden");
  });
  
  savePromptBtn.addEventListener("click", async () => {
    // Disable editing
    brainPromptTextarea.readOnly = true;
    
    // Hide save/cancel buttons, show edit button
    editPromptBtn.classList.remove("hidden");
    savePromptBtn.classList.add("hidden");
    cancelPromptBtn.classList.add("hidden");
    
    // Save the settings
    await saveSettings();
  });
  
  cancelPromptBtn.addEventListener("click", () => {
    // Restore original value
    brainPromptTextarea.value = originalPromptValue;
    
    // Disable editing
    brainPromptTextarea.readOnly = true;
    
    // Hide save/cancel buttons, show edit button
    editPromptBtn.classList.remove("hidden");
    savePromptBtn.classList.add("hidden");
    cancelPromptBtn.classList.add("hidden");
  });

  // --- Initial Load ---
  loadSettings();

  // Load audio devices
  const loadAudioDevices = async () => {
    try {
      const res = await eel.get_audio_devices()();
      if (res && res.ok && res.devices) {
        // Clear existing options except "Default microphone"
        while (audioDeviceSelect.children.length > 1) {
          audioDeviceSelect.removeChild(audioDeviceSelect.lastChild);
        }
        // Add device options
        res.devices.forEach(device => {
          const option = document.createElement('option');
          option.value = device.index;
          option.textContent = device.name;
          audioDeviceSelect.appendChild(option);
        });
        // Set selected device from settings
        const deviceIndex = currentSettings.audio_device_index;
        if (deviceIndex !== null && deviceIndex !== undefined) {
          audioDeviceSelect.value = deviceIndex;
        } else {
          audioDeviceSelect.value = ""; // Default microphone
        }
      }
    } catch (err) {
      console.error("Failed to load audio devices:", err);
    }
  };

  loadAudioDevices();

  // Calibrate handler
  calibrateBtn.addEventListener("click", async () => {
    calibrateBtn.disabled = true;
    const oldText = calibrateBtn.textContent;
    calibrateBtn.textContent = "Calibrating...";
    try {
      const res = await eel.calibrate_silence_threshold(2.5)();
      if (res && res.ok) {
        const thr = Math.round(res.threshold);
        silenceThresholdInput.value = thr;
        currentSettings.silence_threshold = thr;
        await eel.set_silence_threshold(thr)();
      } else {
        console.error("Calibration failed", res && res.error);
      }
    } catch (err) {
      console.error("Calibration error", err);
    } finally {
      calibrateBtn.textContent = oldText;
      calibrateBtn.disabled = false;
    }
  });

  // --- History Functions ---
  let currentlyPlayingButton = null;

  const loadHistory = async () => {
    try {
      historyList.innerHTML = "<p style='color: var(--text-secondary); padding: 20px;'>Loading...</p>";
      const history = await eel.get_history()();
      renderHistory(history);
    } catch (err) {
      console.error("Failed to load history:", err);
      historyList.innerHTML = "<p style='color: #ff4d4d; padding: 20px;'>Failed to load history.</p>";
    }
  };

  const renderHistory = (history) => {
    historyList.innerHTML = "";
    if (!history || history.length === 0) {
      historyList.innerHTML = "<p style='color: var(--text-secondary); padding: 20px;'>No recordings yet.</p>";
      return;
    }

    history.forEach((item) => {
      const el = document.createElement("div");
      el.className = "history-item";
      
      const date = new Date(item.timestamp).toLocaleString();
      const hasTranscript = item.transcript && item.transcript.trim().length > 0;
      
      el.innerHTML = `
        <div class="history-header">
          <span>${date}</span>
          <span>${item.filename}</span>
        </div>
        <div class="history-transcript">${hasTranscript ? item.transcript : "<em>No transcript</em>"}</div>
        <div class="history-actions">
          <button class="play-btn" data-filename="${item.filename}">▶ Play</button>
          <button class="copy-btn" ${!hasTranscript ? 'style="display:none"' : ''}>📄 Copy Text</button>
          <button class="reprocess-btn">🔄 Reprocess</button>
          <button class="delete-btn">🗑 Delete</button>
        </div>
      `;

      // Play/Stop button
      const playBtn = el.querySelector(".play-btn");
      playBtn.addEventListener("click", async () => {
        const isPlaying = playBtn.textContent.startsWith("⏹");
        
        if (isPlaying) {
          // Stop current playback
          await eel.stop_audio()();
          playBtn.textContent = "▶ Play";
          playBtn.dataset.playing = "false";
          currentlyPlayingButton = null;
        } else {
          // Stop any other playing audio first
          if (currentlyPlayingButton && currentlyPlayingButton !== playBtn) {
            await eel.stop_audio()();
            currentlyPlayingButton.textContent = "▶ Play";
            currentlyPlayingButton.dataset.playing = "false";
          }
          
          // Start playback
          const started = await eel.play_history_item(item.filename)();
          if (started) {
            playBtn.textContent = "⏹ Stop";
            playBtn.dataset.playing = "true";
            currentlyPlayingButton = playBtn;
            
            // Auto-reset button after playback (estimate based on file duration)
            // For now, we'll check periodically if audio is still playing
            const checkPlayback = setInterval(async () => {
              const stillPlaying = await eel.is_audio_playing()();
              if (!stillPlaying && playBtn.dataset.playing === "true") {
                playBtn.textContent = "▶ Play";
                playBtn.dataset.playing = "false";
                currentlyPlayingButton = null;
                clearInterval(checkPlayback);
              }
            }, 500);
            
            // Safety timeout (max 10 minutes)
            setTimeout(() => {
              clearInterval(checkPlayback);
              if (playBtn.dataset.playing === "true") {
                playBtn.textContent = "▶ Play";
                playBtn.dataset.playing = "false";
                currentlyPlayingButton = null;
              }
            }, 600000);
          }
        }
      });

      // Copy button
      if (hasTranscript) {
        el.querySelector(".copy-btn").addEventListener("click", async () => {
          try {
            await navigator.clipboard.writeText(item.transcript || "");
            const btn = el.querySelector(".copy-btn");
            const originalText = btn.textContent;
            btn.textContent = "✓ Copied!";
            setTimeout(() => {
              btn.textContent = originalText;
            }, 2000);
          } catch (err) {
            console.error("Failed to copy:", err);
          }
        });
      }

      // Reprocess button (always visible)
      el.querySelector(".reprocess-btn").addEventListener("click", async (e) => {
        const btn = e.target;
        const confirmMsg = hasTranscript 
          ? "Re-transcribe this recording? This will replace the existing transcript."
          : "Transcribe this recording?";
        
        if (!confirm(confirmMsg)) return;
        
        btn.disabled = true;
        const originalText = btn.textContent;
        btn.textContent = "⏳ Processing...";
        try {
          const newHistory = await eel.transcribe_history_item(item.filename)();
          if (newHistory) {
            renderHistory(newHistory);
          } else {
            btn.textContent = "❌ Error";
            setTimeout(() => {
              btn.textContent = originalText;
              btn.disabled = false;
            }, 2000);
          }
        } catch (err) {
          console.error(err);
          btn.textContent = "❌ Error";
          setTimeout(() => {
            btn.textContent = originalText;
            btn.disabled = false;
          }, 2000);
        }
      });

      // Delete button
      el.querySelector(".delete-btn").addEventListener("click", async () => {
        if (confirm(`Delete this recording?\n\n${item.filename}`)) {
          try {
            const newHistory = await eel.delete_history_item(item.filename)();
            renderHistory(newHistory);
          } catch (err) {
            console.error("Failed to delete:", err);
          }
        }
      });

      historyList.appendChild(el);
    });
  };
});

// ---------------- Eel <-> Python callback handlers -----------------
// Expose functions so Python can call eel.transcriptionResult(text) and eel.recordingCompleted()
// without causing AttributeError. These can later be enhanced to update UI elements.

function transcriptionResult(text) {
  console.log("Transcription result received:", text);
  // TODO: Display in UI (e.g., add a transcript panel)
}
eel.expose(transcriptionResult);

function recordingCompleted() {
  console.log("Recording completed (Python callback).");
  // Future: re-enable record button, show notification, etc.
}
eel.expose(recordingCompleted);