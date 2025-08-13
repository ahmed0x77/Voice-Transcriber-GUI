document.addEventListener("DOMContentLoaded", () => {
  // API Key input field
  const apiKeyInput = document.getElementById("apiKeyInput");
  // --- Element Selectors ---
  const views = {
    general: document.getElementById("view-general"),
    "api-keys": document.getElementById("view-api-keys"),
  };
  const navButtons = document.querySelectorAll(".nav-list button");

  // Settings Controls
  const shortcutModeTabs = document.getElementById("shortcutModeTabs");
  const toggleKeyRow = document.getElementById("toggleKeyRow");
  const holdKeyRow = document.getElementById("holdKeyRow");
  const toggleComboInput = document.getElementById("toggleComboInput");
  const holdKeyInput = document.getElementById("holdKeyInput");

  const brainProviderSelect = document.getElementById("brainProvider");
  const brainPromptTextarea = document.getElementById("brainPrompt");
  const editPromptBtn = document.getElementById("editPromptBtn");
  const savePromptBtn = document.getElementById("savePromptBtn");
  const cancelPromptBtn = document.getElementById("cancelPromptBtn");
  const audioDeviceSelect = document.getElementById("audioDeviceSelect");
  const silenceThresholdInput = document.getElementById("silenceThresholdInput");
  const calibrateBtn = document.getElementById("calibrateBtn");

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
      brainProviderSelect.value = settings.transcri_brain.provider || "Gemini";
      brainPromptTextarea.value = settings.transcri_brain.prompt || "";
    }
    // Gemini API Key
    apiKeyInput.value = settings.gemini_api_key || "";
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
      speech_provider: currentSettings.speech_provider, // Preserved from load
      transcri_brain: {
        enabled: true, // Always enabled as per previous request
        provider: brainProviderSelect.value,
        prompt: brainPromptTextarea.value,
      },
      gemini_api_key: apiKeyInput.value.trim(),
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
    brainProviderSelect,
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