from pydantic import BaseModel
from typing import Dict, Any, List, Optional

class LanguageAgentRequest(BaseModel):
    question: str
    portfolio_initial_data: Dict[str, Any] = {} # Default to empty dict

class TickerExtraction(BaseModel):
    """Extracted stock tickers from a user query."""
    tickers: List[str] = [] # List of stock ticker symbols (e.g., ["AAPL", "GOOGL"])