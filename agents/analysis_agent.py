# agents/analysis_agent.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List
from config.settings import settings
import uvicorn
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import json

analysis_app = FastAPI()

llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=settings.GOOGLE_API_KEY, temperature=0.5)

# Pydantic model for the incoming data from Language Agent
class AnalysisInput(BaseModel):
    question: str
    portfolio_data: Dict[str, Any]
    stock_quotes: Dict[str, Any]
    daily_adjusted_data: Dict[str, Any]
    earnings_surprises: List[Dict[str, Any]]
    recent_news: List[Dict[str, Any]]

@analysis_app.post("/analysis/analyze_brief_data/")
async def analyze_brief_data_endpoint(data: AnalysisInput):
    """
    Analyzes the collected data and generates insights.
    """
    try:
        # Construct a detailed input for the LLM based on available data
        analysis_context_str = "User Question: " + data.question + "\n\n"

        if data.portfolio_data:
            analysis_context_str += f"Portfolio Initial Data: {json.dumps(data.portfolio_data, indent=2)}\n\n"

        if data.stock_quotes:
            analysis_context_str += "Real-time Stock Quotes:\n"
            for ticker, av_wrapped_quote in data.stock_quotes.items():
                quote = av_wrapped_quote.get("Global Quote", {})
                if quote:
                    analysis_context_str += (
                        f"  {ticker}: Price={quote.get('price', 'N/A')}, "
                        f"Change={quote.get('change', 'N/A')} ({quote.get('change_percent', 'N/A')}), "
                        f"Open={quote.get('open', 'N/A')}, High={quote.get('high', 'N/A')}, Low={quote.get('low', 'N/A')}\n"
                    )
            analysis_context_str += "\n"

        if data.daily_adjusted_data:
            analysis_context_str += "Historical Daily Adjusted Data:\n"
            for ticker, av_wrapped_daily_data in data.daily_adjusted_data.items():
                daily_data = av_wrapped_daily_data.get("Time Series (Daily)", {})
                if daily_data:
                    sorted_dates = sorted(daily_data.keys(), reverse=True)
                    analysis_context_str += f"  {ticker} (latest 5 days):\n"
                    for i in range(min(5, len(sorted_dates))):
                        date_str = sorted_dates[i]
                        day_data = daily_data[date_str]
                        analysis_context_str += (
                            f"    {date_str}: Close={day_data.get('4. close', 'N/A')}, "
                            f"Volume={day_data.get('5. volume', 'N/A')}\n"
                        )
            analysis_context_str += "\n"

        if data.earnings_surprises:
            analysis_context_str += "Earnings Surprises:\n"
            for surprise in data.earnings_surprises:
                analysis_context_str += (
                    f"  {surprise.get('ticker', 'N/A')} on {surprise.get('date', 'N/A')}: "
                    f"Surprise Percent={surprise.get('surprise_percent', 'N/A')}%\n"
                )
            analysis_context_str += "\n"
        
        if data.recent_news:
            analysis_context_str += "Recent Financial News:\n"
            for i, news_item in enumerate(data.recent_news):
                analysis_context_str += (
                    f"  Article {i+1} from {news_item.get('source', 'N/A')}:\n"
                    f"    Title: {news_item.get('title', 'N/A')}\n"
                    f"    Description: {news_item.get('description', 'N/A')}\n\n"
                )
            analysis_context_str += "\n"

        # LLM prompt for analysis - Significantly enhanced for portfolio analysis
        prompt_template = ChatPromptTemplate.from_messages([
            ("system",
             "You are a highly skilled financial analyst. Your primary goal is to analyze the provided financial data "
             "(real-time quotes, historical trends, earnings, and recent news) in the context of the user's query. "
             "**CRITICAL: If 'Portfolio Initial Data' is provided, you MUST analyze the performance of each stock within that portfolio "
             "relative to its allocation, and assess the portfolio's overall health or recent activity. "
             "Relate individual stock performance and news to their impact on the portfolio where relevant.**"
             "\n\nFocus on connecting different data points to provide a comprehensive view. For historical data, identify significant price movements or volume changes. "
             "For news, explain its potential impact on relevant companies or the broader market, considering sentiment and direct effects. "
             "Identify opportunities or risks where applicable. "
             "If any data points are missing or indicate issues, mention them. "
             "Return a clear, narrative summary of your analysis, providing actionable insights or a detailed market overview that is directly relevant to the user's question."
             "\n\n--- Data for Analysis ---\n{context_data}"),
            ("human", "Provide a comprehensive analysis based on the data above.")
        ])

        chain = prompt_template | llm | StrOutputParser()
        analysis_summary = chain.invoke({"context_data": analysis_context_str})

        return {"summary": analysis_summary}

    except Exception as e:
        print(f"Error caught in analysis_brief_data_endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Error during analysis: {e}")

if __name__ == "__main__":
    uvicorn.run(analysis_app, host="0.0.0.0", port=settings.ANALYSIS_AGENT_PORT)