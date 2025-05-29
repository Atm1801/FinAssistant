from fastapi import FastAPI, HTTPException
from config.settings import settings
import requests
import uvicorn
from datetime import datetime
import json

# Initialize FastAPI app
api_app = FastAPI()

class AlphaVantageLoader:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://www.alphavantage.co/query"

    def get_quote_endpoint(self, symbol: str) -> dict: # Added symbol parameter
        """Fetches real-time quote for a given stock symbol."""
        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": symbol, # Use the dynamic symbol
            "apikey": self.api_key
        }
        try:
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()

            print(f"\n--- AlphaVantage Raw Response for {symbol} ---")
            print(json.dumps(data, indent=2)) # Print the full response
            print("-------------------------------------------\n")

            if "Global Quote" in data and data["Global Quote"]:
                quote = data["Global Quote"]
                return {
                    "symbol": quote.get("01. symbol"),
                    "open": float(quote.get("02. open")),
                    "high": float(quote.get("03. high")),
                    "low": float(quote.get("04. low")),
                    "price": float(quote.get("05. price")),
                    "volume": int(quote.get("06. volume")),
                    "latest_trading_day": quote.get("07. latest trading day"),
                    "previous_close": float(quote.get("08. previous close")),
                    "change": float(quote.get("09. change")),
                    "change_percent": quote.get("10. change percent")
                }
            elif "Error Message" in data:
                raise HTTPException(status_code=404, detail=f"AlphaVantage Error: {data['Error Message']}")
            else:
                raise HTTPException(status_code=500, detail="Unexpected AlphaVantage API response for Global Quote.")
        except requests.exceptions.RequestException as e:
            raise HTTPException(status_code=503, detail=f"Error contacting AlphaVantage API: {e}")

    def get_daily_adjusted(self, symbol: str) -> dict: # Added symbol parameter
        """Fetches daily adjusted historical data for a given stock symbol."""
        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": symbol, # Use the dynamic symbol
            "apikey": self.api_key,
            "outputsize": "compact" # "compact" for last 100 days, "full" for 20+ years
        }
        try:
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()

            print(f"\n--- AlphaVantage Raw Response for {symbol} ---")
            print(json.dumps(data, indent=2)) # Print the full response
            print("-------------------------------------------\n")


            if "Time Series (Daily)" in data:
                return data["Time Series (Daily)"]
            elif "Error Message" in data:
                 raise HTTPException(status_code=404, detail=f"AlphaVantage Error: {data['Error Message']}")
            else:
                raise HTTPException(status_code=500, detail="Unexpected AlphaVantage API response for Daily Adjusted.")
        except requests.exceptions.RequestException as e:
            raise HTTPException(status_code=503, detail=f"Error contacting AlphaVantage API: {e}")

# Initialize AlphaVantage loader with API key from settings
av_loader = AlphaVantageLoader(settings.ALPHA_VANTAGE_API_KEY)

@api_app.get("/api/stock_quote/{symbol}") # Path parameter for symbol
async def get_stock_quote_endpoint(symbol: str): # Accept symbol
    """Endpoint to get real-time stock quote."""
    return av_loader.get_quote_endpoint(symbol)

@api_app.get("/api/daily_adjusted/{symbol}") # Path parameter for symbol
async def get_daily_adjusted_endpoint(symbol: str): # Accept symbol
    """Endpoint to get daily adjusted historical data."""
    return av_loader.get_daily_adjusted(symbol)

if __name__ == "__main__":
    uvicorn.run(api_app, host="0.0.0.0", port=settings.API_AGENT_PORT)