# agents/analysis_agent.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List
from config.settings import settings
import uvicorn
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import json # Ensure json is imported for json.dumps

analysis_app = FastAPI()

# Initialize LLM for analysis (can be the same or different model)
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=settings.GOOGLE_API_KEY, temperature=0.5)

# Pydantic model for the incoming data from Language Agent
class AnalysisInput(BaseModel):
    question: str
    portfolio_data: Dict[str, Any]
    stock_quotes: Dict[str, Any]
    daily_adjusted_data: Dict[str, Any]
    earnings_surprises: List[Dict[str, Any]]

@analysis_app.post("/analysis/analyze_brief_data/")
async def analyze_brief_data_endpoint(data: AnalysisInput):
    """
    Analyzes the collected data and generates insights.
    """
    try:
        # Construct the detailed input for the LLM as a single string
        # This string will be passed as a single variable to the prompt template
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
            analysis_context_str += "Historical Daily Adjusted Data (latest for each ticker):\n"
            for ticker, av_wrapped_daily_data in data.daily_adjusted_data.items():
                daily_data = av_wrapped_daily_data.get("Time Series (Daily)", {})
                if daily_data:
                    latest_date = sorted(daily_data.keys(), reverse=True)[0] if daily_data else "N/A"
                    if latest_date != "N/A":
                        latest_day_data = daily_data[latest_date]
                        analysis_context_str += (
                            f"  {ticker} (as of {latest_date}): "
                            f"Close={latest_day_data.get('4. close', 'N/A')}, "
                            f"Volume={latest_day_data.get('5. volume', 'N/A')}\n"
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

        # LLM prompt for analysis - Define 'context_data' as a variable
        prompt_template = ChatPromptTemplate.from_messages([
            ("system",
             "You are a financial analysis expert. Analyze the provided financial data and user query to extract key insights, trends, and implications. "
             "Focus on answering what the user needs to know about their query, especially regarding specific stocks, market movements, or portfolio impacts. "
             "Summarize the most important information concisely. If any data points are missing or indicate issues, mention them. "
             "Return a clear, narrative summary of your analysis."
             "\n\n--- Data for Analysis ---\n{context_data}"), # <--- Use placeholder here
            ("human", "Provide a comprehensive analysis based on the data above.")
        ])

        chain = prompt_template | llm | StrOutputParser()
        # Pass the constructed string as the 'context_data' variable
        analysis_summary = chain.invoke({"context_data": analysis_context_str}) # <--- Pass the variable here

        return {"summary": analysis_summary}

    except Exception as e:
        print(f"Error caught in analysis_brief_data_endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Error during analysis: {e}")

if __name__ == "__main__":
    uvicorn.run(analysis_app, host="0.0.0.0", port=settings.ANALYSIS_AGENT_PORT)