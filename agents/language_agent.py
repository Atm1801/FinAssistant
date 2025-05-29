# agents/language_agent.py
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, List, Dict, Any
from langchain_core.messages import BaseMessage, HumanMessage
import operator
import requests
from config.settings import settings
import json
from fastapi import FastAPI, HTTPException
from datetime import datetime, timedelta
import uvicorn

# Import the new models
from orchestrator.models import LanguageAgentRequest, TickerExtraction

# Initialize LLM
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=settings.GOOGLE_API_KEY, temperature=0.7)

# LangChain structured output for ticker extraction
ticker_extractor_llm = llm.with_structured_output(TickerExtraction)
ticker_extraction_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an expert at extracting stock ticker symbols from text. Extract all relevant stock symbols from the user's query. If no explicit tickers are mentioned, try to infer them based on company names. If no stock-related entities are found, return an empty list. Provide only the ticker symbols, not company names, in the list."),
    ("human", "{question}")
])
ticker_extraction_chain = ticker_extraction_prompt | ticker_extractor_llm

# Define State for Langgraph
class AgentState(TypedDict):
    question: str
    portfolio_data: dict
    extracted_tickers: List[str]
    stock_quotes: Dict[str, Any]
    daily_adjusted_data: Dict[str, Any]
    earnings_surprises: List[dict]
    recent_news: List[Dict[str, Any]]
    retrieved_context: List[str]
    final_brief: str
    error: str

# --- Helper for News API ---
def fetch_financial_news(query: str, api_key: str, num_articles: int = 3) -> List[Dict[str, Any]]:
    """
    Fetches recent financial news articles using NewsAPI.org.
    Prioritizes English articles from the last 7 days.
    """
    if not api_key:
        print("NEWS_API_KEY is not set. Skipping news retrieval.")
        return []

    base_url = "https://newsapi.org/v2/everything"
    from_date = (datetime.now() - timedelta(days=7)).isoformat(timespec='minutes')

    params = {
        "q": query,
        "language": "en",
        "sortBy": "relevancy",
        "from": from_date,
        "apiKey": api_key,
        "pageSize": num_articles
    }

    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()
        articles = data.get("articles", [])
        
        filtered_articles = []
        for article in articles:
            if article.get("title") and article.get("description"):
                filtered_articles.append({
                    "source": article.get("source", {}).get("name", "N/A"),
                    "title": article.get("title"),
                    "description": article.get("description"),
                    "url": article.get("url")
                })
        return filtered_articles
    except requests.exceptions.RequestException as e:
        print(f"Error fetching news from NewsAPI: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error in news fetching: {e}")
        return []

# --- Langgraph Nodes ---

def extract_tickers(state: AgentState):
    """Extracts stock tickers from the user's question using the LLM."""
    print("---EXTRACTING TICKERS---")
    question = state["question"]
    try:
        extraction_result: TickerExtraction = ticker_extraction_chain.invoke({"question": question})
        tickers = extraction_result.tickers
        print(f"Extracted Tickers: {tickers}")
        return {"extracted_tickers": tickers}
    except Exception as e:
        print(f"Error extracting tickers: {e}")
        return {"error": f"Error extracting tickers: {e}"}

def retrieve_data(state: AgentState):
    print("---RETRIEVING DATA---")
    extracted_tickers = state["extracted_tickers"]
    stock_quotes = {}
    daily_adjusted_data = {}
    errors = []

    if not extracted_tickers:
        print("No specific tickers extracted. Proceeding without specific stock data.")
        return state

    for ticker in extracted_tickers:
        try:
            quote_response = requests.get(f"http://localhost:{settings.API_AGENT_PORT}/api/stock_quote/{ticker}")
            quote_response.raise_for_status()
            stock_quotes[ticker] = quote_response.json()
            print(f"Retrieved quote for {ticker}: {stock_quotes[ticker]}")

            daily_response = requests.get(f"http://localhost:{settings.API_AGENT_PORT}/api/daily_adjusted/{ticker}")
            daily_response.raise_for_status()
            daily_adjusted_data[ticker] = daily_response.json()
            print(f"Retrieved daily adjusted data for {ticker}")

        except requests.exceptions.RequestException as e:
            errors.append(f"Could not retrieve data for {ticker}: {e}")
            print(f"Error retrieving data for {ticker}: {e}")
        except HTTPException as e:
            errors.append(f"API Agent error for {ticker}: {e.detail}")
            print(f"API Agent error for {ticker}: {e.detail}")
        except Exception as e:
            errors.append(f"Unexpected error for {ticker}: {e}")
            print(f"Unexpected error for {ticker}: {e}")

    # No hardcoded earnings surprises here
    earnings_surprises = []

    error_message = "\n".join(errors) if errors else ""

    return {
        "stock_quotes": stock_quotes,
        "daily_adjusted_data": daily_adjusted_data,
        "earnings_surprises": earnings_surprises,
        "error": error_message
    }

def retrieve_news(state: AgentState):
    print("---RETRIEVING NEWS---")
    question = state["question"]
    extracted_tickers = state["extracted_tickers"]
    recent_news = []

    news_queries = []
    if extracted_tickers:
        news_queries.extend([f"{ticker} stock news" for ticker in extracted_tickers])
    
    if not news_queries or len(extracted_tickers) < 2:
        news_queries.append(question)

    unique_queries = list(set(news_queries))[:2]

    for q in unique_queries:
        print(f"Fetching news for query: '{q}'")
        articles = fetch_financial_news(q, settings.NEWS_API_KEY)
        recent_news.extend(articles)
    
    seen = set()
    deduped_news = []
    for news_item in recent_news:
        identifier = (news_item.get("title"), news_item.get("url"))
        if identifier not in seen:
            deduped_news.append(news_item)
            seen.add(identifier)

    print(f"Retrieved {len(deduped_news)} news articles.")
    return {"recent_news": deduped_news}

def analyze_data(state: AgentState):
    print("---ANALYZING DATA---")
    question = state["question"]
    portfolio_data = state["portfolio_data"]
    stock_quotes = state["stock_quotes"]
    daily_adjusted_data = state["daily_adjusted_data"]
    earnings_surprises = state["earnings_surprises"]
    recent_news = state["recent_news"]

    analysis_input = {
        "question": question,
        "portfolio_data": portfolio_data,
        "stock_quotes": stock_quotes,
        "daily_adjusted_data": daily_adjusted_data,
        "earnings_surprises": earnings_surprises,
        "recent_news": recent_news, # Pass news to Analysis Agent
    }

    retrieved_context = []
    try:
        analysis_response = requests.post(
            f"http://localhost:{settings.ANALYSIS_AGENT_PORT}/analysis/analyze_brief_data/",
            json=analysis_input
        )
        analysis_response.raise_for_status()
        analysis_result = analysis_response.json()

        retrieved_context.append(f"Analysis insights: {analysis_result.get('summary', 'No specific summary provided.')}")

    except requests.exceptions.RequestException as e:
        print(f"Error contacting analysis agent: {e}")
        retrieved_context.append(f"Error contacting analysis agent: {e}")
    except Exception as e:
        print(f"Unexpected error during analysis: {e}")
        retrieved_context.append(f"Unexpected error during analysis: {e}")


    for ticker, av_wrapped_quote in stock_quotes.items():
        quote = av_wrapped_quote.get("Global Quote", {})
        if quote:
            price_str = quote.get('price', 'N/A')
            change_str = quote.get('change', 'N/A')
            change_percent_str = quote.get('change_percent', 'N/A').replace('%', '')

            try:
                price = float(price_str) if price_str != 'N/A' else 'N/A'
                change = float(change_str) if change_str != 'N/A' else 'N/A'
                change_percent = float(change_percent_str) if change_percent_str != 'N/A' else 'N/A'

                price_fmt = f"{price:.2f}" if isinstance(price, (int, float)) else price
                change_fmt = f"{change:.2f}" if isinstance(change, (int, float)) else change
                change_percent_fmt = f"{change_percent:.2f}%" if isinstance(change_percent, (int, float)) else change_percent

                retrieved_context.append(
                    f"Real-time quote for {ticker}: Price={price_fmt}, Change={change_fmt} ({change_percent_fmt})"
                )
            except ValueError:
                retrieved_context.append(
                    f"Real-time quote for {ticker}: Price={price_str}, Change={change_str} ({quote.get('change_percent', 'N/A')})"
                )
        else:
             retrieved_context.append(f"Real-time quote for {ticker}: Data not fully available.")
    
    if daily_adjusted_data:
        for ticker, av_wrapped_daily_data in daily_adjusted_data.items():
            daily_data = av_wrapped_daily_data.get("Time Series (Daily)", {})
            if daily_data:
                dates = sorted(daily_data.keys())
                if len(dates) >= 2:
                    oldest_date = dates[0]
                    latest_date = dates[-1]
                    
                    oldest_close = daily_data[oldest_date].get('4. close', 'N/A')
                    latest_close = daily_data[latest_date].get('4. close', 'N/A')

                    try:
                        oldest_close_f = float(oldest_close) if oldest_close != 'N/A' else None
                        latest_close_f = float(latest_close) if latest_close != 'N/A' else None

                        if oldest_close_f is not None and latest_close_f is not None and oldest_close_f != 0:
                            price_change_over_period = ((latest_close_f - oldest_close_f) / oldest_close_f) * 100
                            retrieved_context.append(
                                f"Historical trend for {ticker} ({oldest_date} to {latest_date}): "
                                f"Price changed from {oldest_close_f:.2f} to {latest_close_f:.2f} ({price_change_over_period:.2f}%)."
                            )
                        else:
                            retrieved_context.append(f"Historical trend for {ticker}: Data incomplete for trend analysis.")
                    except ValueError:
                        retrieved_context.append(f"Historical trend for {ticker}: Raw data for {oldest_date} close={oldest_close}, {latest_date} close={latest_close}.")
                elif len(dates) == 1:
                    retrieved_context.append(f"Historical data for {ticker} available only for {dates[0]}.")
                else:
                    retrieved_context.append(f"No sufficient historical data for {ticker}.")

    if portfolio_data:
        retrieved_context.append(f"Portfolio initial data: {portfolio_data}")

    return {"retrieved_context": retrieved_context}


def synthesize_narrative(state: AgentState):
    print("---SYNTHESIZING NARRATIVE---")
    question = state["question"]
    portfolio_data = state["portfolio_data"]
    retrieved_context = state["retrieved_context"]
    earnings_surprises = state["earnings_surprises"]
    stock_quotes = state["stock_quotes"]
    daily_adjusted_data = state["daily_adjusted_data"]
    recent_news = state["recent_news"]

    # Create a comprehensive prompt for the LLM
    prompt_template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a helpful and highly detailed financial analyst. Your goal is to generate a comprehensive, insightful, and professional market brief based on the user's query and all available financial data. "
                "**CRITICAL: If 'Portfolio Data' is provided and relevant to the query (e.g., 'how is my portfolio doing?'), thoroughly analyze the individual stock performance within the portfolio and its overall impact. "
                "Explicitly discuss the performance of stocks mentioned in the portfolio and their contribution to the portfolio's recent activity or overall health.**"
                "\n\nSynthesize real-time stock quotes, historical performance, earnings surprises, and recent news to provide a holistic overview. "
                "Highlight key financial metrics, significant changes, emerging trends, and important news developments relevant to the user's question or specific companies mentioned. "
                "Discuss both positive and negative implications where applicable. If no specific tickers were found, discuss general market sentiment or relevant economic trends based on the query if possible, or clearly state the limitations. "
                "Ensure the output is well-structured, easy to understand, and provides actionable insights or a clear summary of the current market landscape pertinent to the query."
                "\n\nUser Question: {question}"
                "\n\nPortfolio Data: {portfolio_data}"
                "\n\nReal-time Stock Quotes: {stock_quotes}"
                "\n\nHistorical Daily Adjusted Data: {daily_adjusted_data}"
                "\n\nEarnings Surprises: {earnings_surprises}"
                "\n\nRecent Financial News: {recent_news}"
                "\n\nFinancial Analysis/Context from Analysis Agent: {retrieved_context}"
            ),
            ("human", "Generate the detailed and comprehensive market brief."),
        ]
    )

    chain = prompt_template | llm | StrOutputParser()
    try:
        brief = chain.invoke({
            "question": question,
            "portfolio_data": portfolio_data,
            "stock_quotes": stock_quotes,
            "daily_adjusted_data": daily_adjusted_data,
            "earnings_surprises": earnings_surprises,
            "recent_news": recent_news,
            "retrieved_context": "\n".join(retrieved_context)
        })
        print(f"DEBUG: Brief generated. Type: {type(brief)}, Length: {len(brief) if isinstance(brief, str) else 'N/A'}")
        print(f"DEBUG: First 200 chars of brief:\n{brief[:200]}")
        return {"final_brief": brief}
    except Exception as e:
        print(f"Error during narrative synthesis: {e}")
        return {"error": f"Error during narrative synthesis: {e}"}


# Define the Langgraph workflow
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("extract_tickers", extract_tickers)
workflow.add_node("retrieve_data", retrieve_data)
workflow.add_node("retrieve_news", retrieve_news)
workflow.add_node("analyze_data", analyze_data)
workflow.add_node("synthesize_narrative", synthesize_narrative)

# Define the graph flow
workflow.set_entry_point("extract_tickers")
workflow.add_edge("extract_tickers", "retrieve_data")
workflow.add_edge("retrieve_data", "retrieve_news")
workflow.add_edge("retrieve_news", "analyze_data")
workflow.add_edge("analyze_data", "synthesize_narrative")
workflow.add_edge("synthesize_narrative", END)

# Compile the graph
app_graph = workflow.compile()

# FastAPI integration for the language agent
lang_app = FastAPI()

@lang_app.post("/language/generate_brief/")
async def generate_brief_endpoint(request: LanguageAgentRequest):
    try:
        initial_state = AgentState(
            question=request.question,
            portfolio_data=request.portfolio_initial_data,
            extracted_tickers=[],
            stock_quotes={},
            daily_adjusted_data={},
            earnings_surprises=[],
            recent_news=[],
            retrieved_context=[],
            final_brief="",
            error=""
        )
        
        result = app_graph.invoke(initial_state)

        if result.get("error"):
            raise HTTPException(status_code=500, detail=result["error"])

        final_brief = result.get("final_brief")
        if not final_brief:
            return {"brief": "Could not generate a comprehensive brief. Please try rephrasing your query or provide more context."}

        return {"brief": final_brief}
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Unhandled error in generate_brief_endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")

if __name__ == "__main__":
    uvicorn.run(lang_app, host="0.0.0.0", port=settings.LANGUAGE_AGENT_PORT)