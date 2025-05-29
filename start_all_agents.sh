#!/bin/bash

# Start the Orchestrator
echo "Starting Orchestrator Agent..."
uvicorn orchestrator.orchestrator:app --host 0.0.0.0 --port 8000 --reload &
ORCHESTRATOR_PID=$!
echo "Orchestrator Agent started with PID: $ORCHESTRATOR_PID"

# Start the API Agent
echo "Starting API Agent..."
uvicorn agents.api_agent:api_app --host 0.0.0.0 --port 8001 --reload &
API_PID=$!
echo "API Agent started with PID: $API_PID"

# Start the Scraping Agent (if it runs standalone)
echo "Starting Scraping Agent..."
uvicorn agents.scraping_agent:app --host 0.0.0.0 --port 8002 --reload &
SCRAPING_PID=$!
echo "Scraping Agent started with PID: $SCRAPING_PID"

# Start the Retriever Agent (if it runs standalone)
echo "Starting Retriever Agent..."
uvicorn agents.retriever_agent:app --host 0.0.0.0 --port 8003 --reload &
RETRIEVER_PID=$!
echo "Retriever Agent started with PID: $RETRIEVER_PID"

# Start the Analysis Agent
echo "Starting Analysis Agent..."
uvicorn agents.analysis_agent:analysis_app --host 0.0.0.0 --port 8004 --reload &
ANALYSIS_PID=$!
echo "Analysis Agent started with PID: $ANALYSIS_PID"

# Start the Language Agent
echo "Starting Language Agent..."
uvicorn agents.language_agent:lang_app --host 0.0.0.0 --port 8005 --reload &
LANGUAGE_PID=$!
echo "Language Agent started with PID: $LANGUAGE_PID"

# Start the Voice Agent
echo "Starting Voice Agent..."
uvicorn agents.voice_agent:voice_app --host 0.0.0.0 --port 8006 --reload &
VOICE_PID=$!
echo "Voice Agent started with PID: $VOICE_PID"

# Wait for agents to spin up
echo "Giving agents a moment to initialize..."
sleep 5

# Start the Streamlit application in the foreground
echo "Starting Streamlit App..."
streamlit run streamlit_app/app.py --server.port 8501 --server.address 0.0.0.0

wait