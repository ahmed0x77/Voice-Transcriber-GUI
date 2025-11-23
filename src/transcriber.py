import os
import json
import base64
from openai import OpenAI

SETTINGS_FILE = 'settings.json'

def _load_prompt():
    """Load custom prompt from settings.json (transcri_brain.prompt) if enabled.
    Falls back to a minimal default instruction if not present.
    The user requested a plain Part.from_text(text="...") without extra markdown wrappers.
    """
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            brain = data.get('transcri_brain', {})
            if brain.get('enabled', True):
                prompt = brain.get('prompt', '').strip()
                if prompt:
                    return prompt
    except Exception as e:
        print('Prompt load error:', e)
    # Default minimal instruction (kept concise per request)
    return "Transcribe the audio accurately. Preserve original language/scripts. Remove filler words. Do not translate."

def _load_api_key():
    """Load API key from settings.json"""
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get('openrouter_api_key', '')
    except Exception as e:
        print('API key load error:', e)
    return ''

def _load_model():
    """Load model from settings.json"""
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get('model', 'google/gemini-2.5-flash-lite')
    except Exception as e:
        print('Model load error:', e)
    return 'google/gemini-2.5-flash-lite'

def transcribe_with_gemini(audio_file):
    """Transcribes audio using OpenRouter (OpenAI client) with Gemini model"""
    if audio_file is None:
        return None
    
    try:
        # Initialize the OpenAI client with OpenRouter configuration
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=_load_api_key(),
        )
        
        print("Sending to OpenRouter...")
        
        # Read and encode the audio file
        with open(audio_file, "rb") as f:
            audio_data = base64.b64encode(f.read()).decode("utf-8")
            
        custom_prompt = _load_prompt()
        model_name = _load_model()
        
        # Create the chat completion request
        # Using the model specified in settings
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": custom_prompt
                        },
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": audio_data,
                                "format": "wav"
                            }
                        }
                    ]
                }
            ]
        )
        
        # Extract the text from the response
        transcribed_text = response.choices[0].message.content
        print(transcribed_text)
        return transcribed_text
            
    except Exception as e:
        print(f"Error during transcription: {e}")
        return f"Transcription error: {str(e)}"

