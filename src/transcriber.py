import os
import json
from google import genai
from google.genai import types

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

def transcribe_with_gemini(audio_file):
    """Transcribes audio using the Gemini API"""
    if audio_file is None:
        return None
    
    try:
        # Initialize the Gemini API client
        client = genai.Client(
            api_key=os.environ.get("GEMINI_API_KEY"),
        )
        
        print("Sending to Gemini API...")
        
        # Upload the audio file
        uploaded_file = client.files.upload(file=audio_file)
        
        # Define the model and content
        model = "gemini-2.0-flash"
        custom_prompt = _load_prompt()
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_uri(
                        file_uri=uploaded_file.uri,
                        mime_type=uploaded_file.mime_type,
                    ),
                    types.Part.from_text(text=custom_prompt),
                ],
            ),
        ]
        
        # Configure the response schema
        generate_content_config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "text": types.Schema(
                        type=types.Type.STRING,
                    ),
                },
            ),
        )
        
        # Generate content
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=generate_content_config,
        )
        
        # Parse the response
        print(response.text)  # Debugging line to check the response")
        try:
            response_json = json.loads(response.text)
            transcribed_text = response_json.get("text", "")
            return transcribed_text
        except json.JSONDecodeError:
            print("Error decoding JSON response")
            return response.text  # Return raw text if JSON parsing fails
            
    except Exception as e:
        print(f"Error during transcription: {e}")
        return f"Transcription error: {str(e)}"

