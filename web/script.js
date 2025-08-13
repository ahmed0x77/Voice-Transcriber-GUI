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

  // Auto-saving on change for all relevant controls
  [
    toggleComboInput,
    holdKeyInput,
    brainProviderSelect,
    brainPromptTextarea,
    apiKeyInput,
  ].forEach((el) => {
    el.addEventListener("change", saveSettings);
  });

  // Prompt Edit Button
  editPromptBtn.addEventListener("click", () => {
    brainPromptTextarea.focus();
    brainPromptTextarea.select();
  });

  // --- Initial Load ---
  loadSettings();
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