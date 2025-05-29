# orchestrator/orchestrator.py
from fastapi import FastAPI, HTTPException
import requests
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from config.settings import settings
import uvicorn
import base64
import io
import json # Ensure json is imported

from orchestrator.models import LanguageAgentRequest # This import is correct

app = FastAPI()

# Redefine UserQuery to accept optional portfolio data and handle audio input
class UserQuery(BaseModel):
    query_text: Optional[str] = None
    audio_file_base64: Optional[str] = None # Base64 encoded audio for STT
    portfolio_data: Dict[str, Any] = Field({}, description="Optional portfolio allocation data from the user.")

@app.post("/orchestrate/generate_brief/")
async def orchestrate_market_brief(query: UserQuery):
    """
    Orchestrates the entire process for generating a market brief.
    Handles both text and voice input, and returns voice output for the conclusion.
    """
    print("---ORCHESTRATOR: Received request to generate brief---")
    
    # Initialize variables for the brief and audio output
    final_brief_text = ""
    conclusion_audio_base64 = None # To store base64 audio of the conclusion

    try:
        # --- 1. Handle Input: Text or Voice Transcription ---
        question_for_language_agent = ""
        if query.audio_file_base64:
            print("---ORCHESTRATOR: Processing voice input for transcription---")
            # Call Voice Agent for Speech-to-Text
            voice_agent_transcribe_url = f"http://localhost:{settings.VOICE_AGENT_PORT}/voice/transcribe/"
            transcribe_payload = {"audio_file_base64": query.audio_file_base64} # Send base64 in JSON
            
            voice_response = requests.post(voice_agent_transcribe_url, json=transcribe_payload)
            voice_response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
            transcribed_data = voice_response.json()
            question_for_language_agent = transcribed_data.get("transcribed_text", "")
            
            if not question_for_language_agent:
                raise HTTPException(status_code=400, detail="Voice input could not be transcribed to text.")
            print(f"---ORCHESTRATOR: Transcribed text: '{question_for_language_agent}'")

        elif query.query_text:
            print("---ORCHESTRATOR: Processing text input---")
            question_for_language_agent = query.query_text
        else:
            raise HTTPException(status_code=400, detail="Either 'query_text' or 'audio_file_base64' must be provided.")

        # --- 2. Call Language Agent for Analysis and Brief Generation ---
        print("---ORCHESTRATOR: Calling Language Agent for brief generation---")
        lang_agent_request_data = LanguageAgentRequest(
            question=question_for_language_agent,
            portfolio_initial_data=query.portfolio_data
        )

        language_response = requests.post(
            f"http://localhost:{settings.LANGUAGE_AGENT_PORT}/language/generate_brief/",
            json=lang_agent_request_data.model_dump()
        )
        language_response.raise_for_status()
        language_agent_output = language_response.json()
        final_brief_text = language_agent_output.get("brief", "")
        # Language Agent might also return audio for conclusion directly
        conclusion_audio_base64 = language_agent_output.get("conclusion_audio_base64")

        if not final_brief_text:
            raise HTTPException(status_code=500, detail="Language Agent did not return a brief.")
        
        print("---ORCHESTRATOR: Successfully received brief from Language Agent---")

        # --- 3. Return Response ---
        response_data = {"brief_text": final_brief_text}
        if conclusion_audio_base64:
            response_data["conclusion_audio_base64"] = conclusion_audio_base64

        return response_data

    except requests.exceptions.RequestException as re:
        print(f"---ORCHESTRATOR ERROR: Service unavailable or error contacting agent: {re}")
        detail = f"Service unavailable or error contacting agent: {re}"
        if re.response is not None:
            try:
                error_json = re.response.json()
                if "detail" in error_json:
                    detail = f"Agent error ({re.response.status_code}): {error_json['detail']}"
            except json.JSONDecodeError:
                detail = f"Agent error ({re.response.status_code}): {re.response.text}"
        raise HTTPException(status_code=re.response.status_code if re.response else 503, detail=detail)
    except HTTPException as he:
        print(f"---ORCHESTRATOR ERROR: HTTP Exception: {he.detail}")
        raise he
    except Exception as e:
        print(f"---ORCHESTRATOR ERROR: Unhandled orchestration error: {e}")
        raise HTTPException(status_code=500, detail=f"Orchestration Error: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=settings.ORCHESTRATOR_PORT)