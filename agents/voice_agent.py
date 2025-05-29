from fastapi import FastAPI, UploadFile, File, HTTPException
from pydub import AudioSegment
from pydub.playback import play # For local testing of TTS
import speech_recognition as sr
from gtts import gTTS
import io
import uvicorn
from config.settings import settings
import requests # For calling the language agent
import os

app = FastAPI()

@app.post("/voice/stt/")
async def speech_to_text(audio_file: UploadFile = File(...)):
    """Converts spoken audio to text."""
    try:
        # Save the uploaded audio to a temporary file
        temp_audio_path = "temp_audio.wav"
        with open(temp_audio_path, "wb") as f:
            f.write(await audio_file.read())

        recognizer = sr.Recognizer()
        with sr.AudioFile(temp_audio_path) as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data) # Using Google Web Speech API
        os.remove(temp_audio_path)
        return {"text": text}
    except sr.UnknownValueError:
        raise HTTPException(status_code=400, detail="Could not understand audio")
    except sr.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Could not request results from STT service; {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"STT Error: {e}")

@app.post("/voice/tts/")
async def text_to_speech(text: str):
    """Converts text to spoken audio (MP3)."""
    try:
        tts = gTTS(text=text, lang='en')
        audio_bytes_io = io.BytesIO()
        tts.write_to_fp(audio_bytes_io)
        audio_bytes_io.seek(0)
        # In a real app, you'd stream this or return a file response.
        # For this example, we'll return it as bytes.
        return {"audio_bytes": audio_bytes_io.getvalue()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS Error: {e}")

@app.post("/voice/process_brief/")
async def process_voice_brief(audio_file: UploadFile = File(...)):
    """
    End-to-end processing: STT -> Language Agent -> TTS.
    This is the core of the voice interaction for the brief.
    """
    try:
        # 1. STT
        stt_response = await speech_to_text(audio_file)
        user_question = stt_response["text"]
        print(f"User Question (STT): {user_question}")

        # 2. Call Language Agent
        # For simplicity, sending a dummy portfolio data; in a real app, this would be dynamic
        language_response = requests.post(
            f"http://localhost:{settings.LANGUAGE_AGENT_PORT}/language/generate_brief/",
            json={"question": user_question, "portfolio_initial_data": {"asia_tech_allocation_yesterday": 0.18, "current_asia_tech_allocation": 0.22}}
        )
        language_response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        brief_text = language_response.json().get("brief")
        print(f"Generated Brief: {brief_text}")

        # 3. TTS
        tts_response = await text_to_speech(brief_text)
        audio_output_bytes = tts_response["audio_bytes"]

        return {"brief_text": brief_text, "audio_brief_bytes": audio_output_bytes}

    except HTTPException as he:
        raise he # Re-raise FastAPI HTTPExceptions
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Voice Brief Processing Error: {e}")

if __name__ == "__main__":
    # To run this agent: uvicorn agents.voice_agent:app --host 0.0.0.0 --port 8006 --reload
    uvicorn.run(app, host="0.0.0.0", port=settings.VOICE_AGENT_PORT)