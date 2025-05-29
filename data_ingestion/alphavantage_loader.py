import requests
from config.settings import settings

class AlphaVantageLoader:
    def __init__(self):
        self.api_key = settings.ALPHA_VANTAGE_API_KEY
        self.base_url = "https://www.alphavantage.co/query"

    def get_quote_endpoint(self, symbol: str) -> dict:
        """Retrieves real-time quote for a given stock symbol."""
        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": symbol,
            "apikey": self.api_key
        }
        response = requests.get(self.base_url, params=params)
        response.raise_for_status()
        return response.json()

    def get_daily_adjusted(self, symbol: str) -> dict:
        """Retrieves daily adjusted historical data."""
        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": symbol,
            "outputsize": "compact", # "full" for all available data
            "apikey": self.api_key
        }
        response = requests.get(self.base_url, params=params)
        response.raise_for_status()
        return response.json()

# Example Usage:
if __name__ == "__main__":
    loader = AlphaVantageLoader()
    # print(loader.get_quote_endpoint("AAPL"))
    # print(loader.get_daily_adjusted("MSFT"))