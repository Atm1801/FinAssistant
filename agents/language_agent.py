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
    retrieved_context: List[str]
    final_brief: str
    error: str

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
        return state # Return current state, potentially with an empty list of tickers

    for ticker in extracted_tickers:
        try:
            # Fetch real-time quote
            quote_response = requests.get(f"http://localhost:{settings.API_AGENT_PORT}/api/stock_quote/{ticker}")
            quote_response.raise_for_status()
            stock_quotes[ticker] = quote_response.json()
            print(f"Retrieved quote for {ticker}: {stock_quotes[ticker]}")

            # Fetch daily adjusted historical data
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

    # For earnings surprises, you'd typically have a separate API call or a lookup
    earnings_surprises = []
    # Simplified dummy data, you'd integrate a real source here
    if "TSM" in extracted_tickers:
        earnings_surprises.append({"ticker": "TSM", "date": "2024-04-18", "surprise_percent": 5.2})
    if "005930.KS" in extracted_tickers: # Samsung Electronics
        earnings_surprises.append({"ticker": "005930.KS", "date": "2024-04-30", "surprise_percent": 7.1})

    error_message = "\n".join(errors) if errors else ""

    return {
        "stock_quotes": stock_quotes,
        "daily_adjusted_data": daily_adjusted_data,
        "earnings_surprises": earnings_surprises,
        "error": error_message
    }

def analyze_data(state: AgentState):
    print("---ANALYZING DATA---")
    question = state["question"]
    portfolio_data = state["portfolio_data"]
    stock_quotes = state["stock_quotes"]
    daily_adjusted_data = state["daily_adjusted_data"]
    earnings_surprises = state["earnings_surprises"]

    analysis_input = {
        "question": question,
        "portfolio_data": portfolio_data,
        "stock_quotes": stock_quotes,
        "daily_adjusted_data": daily_adjusted_data,
        "earnings_surprises": earnings_surprises,
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


    # Add any direct stock quote or historical data that's relevant to the context
    for ticker, av_wrapped_quote in stock_quotes.items(): # Renamed 'quote' for clarity
        quote = av_wrapped_quote.get("Global Quote", {}) # <--- CRITICAL FIX HERE: Unwrap the quote
        if quote: # Ensure 'Global Quote' key exists and is not empty
            # Safely get numeric values, defaulting to N/A or 0 if missing/invalid
            price_str = quote.get('price', 'N/A')
            change_str = quote.get('change', 'N/A')
            change_percent_str = quote.get('change_percent', 'N/A').replace('%', '') # Remove % for float conversion

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
                # If conversion fails, append as raw string
                retrieved_context.append(
                    f"Real-time quote for {ticker}: Price={price_str}, Change={change_str} ({quote.get('change_percent', 'N/A')})"
                )
        else:
             retrieved_context.append(f"Real-time quote for {ticker}: Data not fully available.")


    # Add portfolio data if it exists
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

    # Create a comprehensive prompt for the LLM
    prompt_template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a helpful financial assistant. Based on the user's question, portfolio data, real-time stock quotes, and financial analysis, generate a concise and informative market brief. "
                "Highlight key financial data, changes, and any relevant earnings surprises. "
                "If real-time data or analysis is available, prioritize it. If no specific tickers were found, discuss the market generally based on the query if possible, or state the limitations. "
                "Structure your response clearly and professionally."
                "\n\nUser Question: {question}"
                "\n\nPortfolio Data: {portfolio_data}"
                "\n\nReal-time Stock Quotes: {stock_quotes}"
                "\n\nEarnings Surprises: {earnings_surprises}"
                "\n\nFinancial Analysis/Context: {retrieved_context}"
            ),
            ("human", "Generate the market brief."),
        ]
    )

    chain = prompt_template | llm | StrOutputParser()
    try:
        brief = chain.invoke({
            "question": question,
            "portfolio_data": portfolio_data,
            "stock_quotes": stock_quotes,
            "earnings_surprises": earnings_surprises,
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
workflow.add_node("analyze_data", analyze_data)
workflow.add_node("synthesize_narrative", synthesize_narrative)

# Define the graph flow
workflow.set_entry_point("extract_tickers")
workflow.add_edge("extract_tickers", "retrieve_data")
workflow.add_edge("retrieve_data", "analyze_data")
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
            retrieved_context=[],
            final_brief="",
            error=""
        )
        
        # Invoke the graph
        result = app_graph.invoke(initial_state)

        if result.get("error"):
            # If any node explicitly set an error, raise HTTPException
            raise HTTPException(status_code=500, detail=result["error"])

        # Check if final_brief exists and is not empty, otherwise indicate a problem
        final_brief = result.get("final_brief")
        if not final_brief:
            return {"brief": "Could not generate a comprehensive brief. Please try rephrasing your query or provide more context."}

        return {"brief": final_brief}
    except HTTPException as he:
        # Re-raise FastAPI HTTPExceptions
        raise he
    except Exception as e:
        # Catch any other unexpected errors during the process
        print(f"Unhandled error in generate_brief_endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")

if __name__ == "__main__":
    uvicorn.run(lang_app, host="0.0.0.0", port=settings.LANGUAGE_AGENT_PORT)