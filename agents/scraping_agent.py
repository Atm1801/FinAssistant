from fastapi import FastAPI, HTTPException
from data_ingestion.sec_filings_scraper import SECFilingsScraper
from config.settings import settings
import uvicorn

app = FastAPI()
sec_scraper = SECFilingsScraper()

@app.get("/scrape/earnings_report/{ticker}")
async def scrape_earnings_report(ticker: str):
    try:
        report_text = sec_scraper.get_recent_earnings_report_text(ticker)
        if report_text:
            return {"ticker": ticker, "earnings_report_text": report_text}
        else:
            raise HTTPException(status_code=404, detail=f"No earnings report found for {ticker}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # To run this agent: uvicorn agents.scraping_agent:app --host 0.0.0.0 --port 8002 --reload
    uvicorn.run(app, host="0.0.0.0", port=settings.SCRAPING_AGENT_PORT)