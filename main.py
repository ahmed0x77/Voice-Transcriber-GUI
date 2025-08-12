import os
from ui import RecorderApp
from recorder import app

# Check if API key is set
if not os.environ.get("GEMINI_API_KEY"):
    print("WARNING: GEMINI_API_KEY not set in environment variables or .env file")

if __name__ == "__main__":
    # Start CustomTkinter app
    app_instance = RecorderApp()
    # Set the global app reference in recorder module
    import recorder
    recorder.app = app_instance
    app_instance.mainloop()

