import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # API Keys
    ALPHA_VANTAGE_API_KEY: str = os.getenv("ALPHA_VANTAGE_API_KEY", "34OCFR8ZF9UVYG7R")
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "AIzaSyDD8-zVBGKoERFYdDNoYDG4B2NSqQmQE0E") # For Gemini
    NEWS_API_KEY: str = os.getenv("NEWS_API_KEY", "5aa3c526ae244c24bf6e27638073eb44") # Example key, replace with actual

    # FastAPI Ports
    API_AGENT_PORT: int = 8001
    SCRAPING_AGENT_PORT: int = 8002
    RETRIEVER_AGENT_PORT: int = 8003
    ANALYSIS_AGENT_PORT: int = 8004
    LANGUAGE_AGENT_PORT: int = 8005
    VOICE_AGENT_PORT: int = 8006
    ORCHESTRATOR_PORT: int = 8000

    # Paths
    VECTOR_DB_PATH: str = "data/faiss_index"
    SEC_FILINGS_CACHE_PATH: str = "data/sec_filings_cache"

    # RAG settings
    RETRIEVAL_TOP_K: int = 5
    RETRIEVAL_CONFIDENCE_THRESHOLD: float = 0.6 # Example threshold

settings = Settings()