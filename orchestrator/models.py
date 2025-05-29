from pydantic import BaseModel,Field
from typing import Dict, Any, List, Optional

class LanguageAgentRequest(BaseModel):
    question: str
    portfolio_initial_data: Dict[str, Any] = Field({}, description="Initial portfolio allocation data (optional).") # Default to empty dict

class TickerExtraction(BaseModel):
    """Extracted stock tickers from a user query."""
    tickers: List[str] = Field(..., description="List of extracted stock ticker symbols.") # List of stock ticker symbols (e.g., ["AAPL", "GOOGL"])