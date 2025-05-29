# agents/voice_agent.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from config.settings import settings
import uvicorn
import speech_recognition as sr
from gtts import gTTS
import io
import base64
from pydub import AudioSegment

voice_app = FastAPI()

# --- Pydantic Models for Request/Response ---
class TranscribeRequest(BaseModel):
    audio_file_base64: str # Base64 encoded audio data

class TranscribeResponse(BaseModel):
    transcribed_text: str

class SynthesizeSpeechRequest(BaseModel):
    text: str

class SynthesizeSpeechResponse(BaseModel):
    audio_file_base64: str

# --- Speech-to-Text Endpoint ---
@voice_app.post("/voice/transcribe/", response_model=TranscribeResponse)
async def transcribe_audio(request: TranscribeRequest):
    """
    Transcribes base64 encoded audio data to text.
    Expects audio_file_base64 in the request body.
    """
    print("---VOICE AGENT: Receiving audio for transcription---")
    try:
        audio_bytes = base64.b64decode(request.audio_file_base64)
        audio_file_io = io.BytesIO(audio_bytes)
        
        # Pydub can usually infer format, but if issues persist, ensure frontend sends a common format like WAV or MP3
        # For 'webm' from some web recorders, you might need: audio = AudioSegment.from_file(audio_file_io, format="webm")
        audio = AudioSegment.from_file(audio_file_io)

        # Convert to WAV in-memory for SpeechRecognition, as it often prefers WAV
        wav_file_io = io.BytesIO()
        audio.export(wav_file_io, format="wav")
        wav_file_io.seek(0) # Rewind to the beginning for SpeechRecognition to read

        r = sr.Recognizer()
        with sr.AudioFile(wav_file_io) as source:
            audio_data = r.record(source)
        
        # Using Google Web Speech API for transcription (requires internet connection)
        transcribed_text = r.recognize_google(audio_data)
        
        print(f"---VOICE AGENT: Transcribed: '{transcribed_text}'")
        return {"transcribed_text": transcribed_text}

    except sr.UnknownValueError:
        print("---VOICE AGENT: Google Speech Recognition could not understand audio")
        raise HTTPException(status_code=400, detail="Speech Recognition could not understand audio. Please speak clearly.")
    except sr.RequestError as e:
        print(f"---VOICE AGENT: Could not request results from Google Speech Recognition service; {e}")
        raise HTTPException(status_code=500, detail=f"Speech Recognition service error: {e}. Check your internet connection.")
    except Exception as e:
        print(f"---VOICE AGENT: Error during transcription: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}")

# --- Text-to-Speech Endpoint ---
@voice_app.post("/voice/synthesize_speech/", response_model=SynthesizeSpeechResponse)
async def synthesize_speech(request: SynthesizeSpeechRequest):
    """
    Synthesizes text to speech and returns base64 encoded audio.
    """
    print(f"---VOICE AGENT: Synthesizing speech for text: '{request.text[:50]}...'")
    try:
        tts = gTTS(text=request.text, lang='en', slow=False)
        audio_fp = io.BytesIO()
        tts.save(audio_fp)
        audio_fp.seek(0) # Rewind the buffer to read its content
        
        audio_base64 = base64.b64encode(audio_fp.read()).decode('utf-8')
        
        print(f"---VOICE AGENT: Speech synthesis complete for '{request.text[:50]}...'")
        return {"audio_file_base64": audio_base64}
    except Exception as e:
        print(f"---VOICE AGENT: Error during speech synthesis: {e}")
        raise HTTPException(status_code=500, detail=f"Speech synthesis failed: {e}")

if __name__ == "__main__":
    uvicorn.run(voice_app, host="0.0.0.0", port=settings.VOICE_AGENT_PORT)