# agents/api_agent.py
from fastapi import FastAPI, HTTPException
from config.settings import settings # Still needed for ports
import requests
import uvicorn
from datetime import datetime, date # Import date as well
import json # For printing debug, if needed

import yfinance as yf # NEW IMPORT

# Initialize FastAPI app
api_app = FastAPI()

def get_yfinance_quote(symbol: str) -> dict:
    """Fetches real-time quote for a given stock symbol using yfinance."""
    try:
        ticker = yf.Ticker(symbol)
        # Using fast_info for quick real-time data
        # Note: 'fast_info' might not contain all fields of 'info'
        # 'info' makes another network call. For a quick snapshot, fast_info is often enough.
        # If more details are needed, use ticker.info
        quote_data = ticker.fast_info # Use fast_info for potentially faster response
        
        if not quote_data:
             # Fallback to ticker.info if fast_info is empty
            quote_data = ticker.info 
        
        if not quote_data or 'lastPrice' not in quote_data: # Check for a key that indicates valid data
            raise HTTPException(status_code=404, detail=f"No real-time quote data found for {symbol}.")

        # Normalize yfinance output to match (or be similar to) AlphaVantage's Global Quote structure
        # This reduces changes needed in the Language Agent
        normalized_quote = {
            "symbol": quote_data.get('symbol', symbol),
            "open": quote_data.get('open', 'N/A'),
            "high": quote_data.get('dayHigh', 'N/A'),
            "low": quote_data.get('dayLow', 'N/A'),
            "price": quote_data.get('lastPrice', 'N/A'), # Or 'currentPrice' or 'regularMarketPrice'
            "volume": quote_data.get('volume', 'N/A'),
            "latest_trading_day": date.today().isoformat(), # yfinance doesn't provide this directly in fast_info
            "previous_close": quote_data.get('previousClose', 'N/A'),
            # yfinance often gives change/change percent directly in fast_info/info
            # If not, you can calculate:
            "change": round(float(quote_data.get('lastPrice', 0)) - float(quote_data.get('previousClose', 0)), 2) if isinstance(quote_data.get('lastPrice'), (int, float)) and isinstance(quote_data.get('previousClose'), (int, float)) else 'N/A',
            "change_percent": f"{(float(quote_data.get('lastPrice', 0)) - float(quote_data.get('previousClose', 0))) / float(quote_data.get('previousClose', 1)) * 100:.2f}%" if isinstance(quote_data.get('lastPrice'), (int, float)) and isinstance(quote_data.get('previousClose'), (int, float)) and quote_data.get('previousClose') != 0 else 'N/A'
        }
        return {"Global Quote": normalized_quote} # Wrap in "Global Quote" to match previous structure

    except yf.TickerError as e:
        raise HTTPException(status_code=404, detail=f"Invalid stock symbol {symbol}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching quote for {symbol}: {e}")

def get_yfinance_daily_adjusted(symbol: str, period: str = "6mo") -> dict:
    """Fetches daily adjusted historical data for a given stock symbol using yfinance.
    
    Args:
        symbol (str): The stock ticker symbol.
        period (str): Valid periods: "1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max".
                      "6mo" by default to get a good range for analysis.
    """
    try:
        ticker = yf.Ticker(symbol)
        # We need to explicitly fetch history for adjusted close
        hist = ticker.history(period=period, interval="1d", actions=False, auto_adjust=True)
        
        if hist.empty:
            raise HTTPException(status_code=404, detail=f"No historical data found for {symbol} for period {period}.")

        # Convert DataFrame to a dictionary matching AlphaVantage's "Time Series (Daily)" structure
        # Keys will be dates, values will be dictionaries of OHLCV
        time_series_data = {}
        for index, row in hist.iterrows():
            date_str = index.strftime('%Y-%m-%d')
            time_series_data[date_str] = {
                "1. open": f"{row['Open']:.4f}",
                "2. high": f"{row['High']:.4f}",
                "3. low": f"{row['Low']:.4f}",
                "4. close": f"{row['Close']:.4f}", # This is the adjusted close
                "5. volume": f"{int(row['Volume'])}"
                # AlphaVantage also has 'adjusted close' and 'dividend amount' and 'split coefficient'
                # We can add '6. adjusted close' if needed, which is same as '4. close' here due to auto_adjust=True
            }
        
        # Sort by date in ascending order (AlphaVantage usually provides latest first, so reverse to match)
        # Or you can reverse it when you return if the consuming agent expects latest first.
        # For simplicity, let's keep it in the order yfinance gives, which is oldest first.
        # LangChain LLM will process the entire context.

        # AlphaVantage returns latest date first, so reverse the dictionary for consistent consumption
        # Or simply, the LLM will be given all data and should infer.
        # For this specific case, let's reverse to match AV behavior if needed by LLM directly.
        # No, let's keep it simple. The LLM can handle unordered context.
        # Re-creating a dict to maintain key order if needed for specific use cases.
        ordered_time_series = dict(sorted(time_series_data.items(), reverse=True))


        return {"Time Series (Daily)": ordered_time_series} # Wrap in "Time Series (Daily)" to match previous structure

    except yf.TickerError as e:
        raise HTTPException(status_code=404, detail=f"Invalid stock symbol {symbol}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching historical data for {symbol}: {e}")


@api_app.get("/api/stock_quote/{symbol}")
async def get_stock_quote_endpoint(symbol: str):
    """Endpoint to get real-time stock quote using yfinance."""
    return get_yfinance_quote(symbol)

@api_app.get("/api/daily_adjusted/{symbol}")
async def get_daily_adjusted_endpoint(symbol: str):
    """Endpoint to get daily adjusted historical data using yfinance."""
    # We can pass the period if we want to expose it in the API, or keep it fixed
    return get_yfinance_daily_adjusted(symbol, period="6mo") # Default to 6 months of data

if __name__ == "__main__":
    uvicorn.run(api_app, host="0.0.0.0", port=settings.API_AGENT_PORT)