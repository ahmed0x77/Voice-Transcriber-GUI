import os
import json
from google import genai
from google.genai import types

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
        contents = [
            types.Content(
            role="user",
            parts=[
                types.Part.from_uri(
                file_uri=uploaded_file.uri,
                mime_type=uploaded_file.mime_type,
                ),
                types.Part.from_text(text="""**Objective:** You are a transcript model. Your task is to transcribe the provided audio file into clean, readable text. You must preserve the original language and native script of all spoken words, and intelligently infer correct terms based on context where pronunciation is ambiguous.

**Instructions for Your Transcription:**

1.  **Transcribe Audio:** Convert the audio content (provided directly with this prompt) to text.
2.  **Remove Disfluencies:** You are to eliminate filler words and self-corrections (e.g., "um," "uh," "like," "you know," "I mean," "sort of").
3.  **Intelligent Error Correction & Clarification:**
    *   You should fix obvious minor slips of the tongue or grammatical errors *only if the speaker's intended meaning is unequivocally clear*. Do not alter the original meaning.
    *   **Contextual Inference for Ambiguous/Technical Terms:** If a specific term (especially a technical term, product name, or proper noun) is slightly mispronounced, slurred, or acoustically unclear, you must leverage the surrounding context to infer and transcribe the most probable correct term.
        *   **Example:** If the audio sounds like "please fix this socketye-oh connection in that Python script," and "socket IO" is a highly plausible and common term in the context of a "Python script," you should transcribe it as "socket IO."
        *   This applies when the audio might be ambiguous but the context provides strong clues to the intended word.
    *   **Constraint:** This inference should only be applied when the contextual evidence is strong and the inferred term significantly improves clarity and accuracy without altering the speaker's core message. You must avoid speculative guessing if context is weak.

4.  **Preserve Original Language & Script (No Translation, No Transliteration to Latin Script):**
    *   You must transcribe all words *exactly* as spoken in their original language, using their native script.
    *   If the audio contains mixed languages (e.g., English and Arabic), you are to transcribe words in their respective languages *and scripts* without translation.
    *   **Crucial Example:** If a speaker says "hello man انت فاكرني", your transcription *must* be "hello man انت فاكرني". It should *NOT* be "hello man enta fakerny" or "hello man you remember me". The Arabic words must remain in Arabic script.
5.  **Formatting:** You should include line breaks as needed for readability (e.g., for new speakers or logical breaks in thought).

**Input:** Audio file (provided directly with this message/prompt).
**Output:** Cleaned, contextually-aware text transcript with original languages and scripts preserved."""),
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

