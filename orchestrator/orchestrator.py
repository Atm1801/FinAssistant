from fastapi import FastAPI, HTTPException
import requests
from pydantic import BaseModel
from config.settings import settings
import uvicorn
import base64
import io

from orchestrator.models import LanguageAgentRequest # <--- NEW IMPORT

app = FastAPI()

class UserQuery(BaseModel):
    query_text: str = None
    audio_file_base64: str = None # Base64 encoded audio

@app.post("/orchestrate/market_brief/")
async def orchestrate_market_brief(query: UserQuery):
    """
    Orchestrates the entire process for generating a market brief.
    Handles both text and voice input.
    """
    try:
        brief_text = ""
        audio_brief_bytes = None

        if query.audio_file_base64:
            # Handle voice input
            audio_bytes = base64.b64decode(query.audio_file_base64)
            audio_file_io = io.BytesIO(audio_bytes)
            audio_file_io.name = "input.wav"

            files = {'audio_file': (audio_file_io.name, audio_file_io, 'audio/wav')}
            voice_response = requests.post(
                f"http://localhost:{settings.VOICE_AGENT_PORT}/voice/process_brief/",
                files=files
            )
            voice_response.raise_for_status()
            voice_data = voice_response.json()
            brief_text = voice_data.get("brief_text")
            audio_brief_bytes = base64.b64decode(voice_data.get("audio_brief_base64"))

        elif query.query_text:
            # Handle text input
            # Create an instance of the Pydantic model for the request body
            lang_agent_request_data = LanguageAgentRequest(
                question=query.query_text,
                portfolio_initial_data={
                    "asia_tech_allocation_yesterday": 0.18,
                    "current_asia_tech_allocation": 0.22
                }
            )

            language_response = requests.post(
                f"http://localhost:{settings.LANGUAGE_AGENT_PORT}/language/generate_brief/",
                json=lang_agent_request_data.model_dump() # <--- Use .model_dump() to convert Pydantic model to dict
            )
            language_response.raise_for_status()
            brief_text = language_response.json().get("brief")
        else:
            raise HTTPException(status_code=400, detail="Either 'query_text' or 'audio_file_base64' must be provided.")

        response = {"brief_text": brief_text}
        if audio_brief_bytes:
            response["audio_brief_base64"] = base64.b64encode(audio_brief_bytes).decode('utf-8')

        return response

    except requests.exceptions.RequestException as re:
        raise HTTPException(status_code=503, detail=f"Service unavailable or error contacting agent: {re}")
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Orchestration Error: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=settings.ORCHESTRATOR_PORT)