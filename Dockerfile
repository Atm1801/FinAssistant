# Use a Python base image
FROM python:3.10-slim-buster

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project
COPY . .

# Expose ports for Streamlit and FastAPI services
EXPOSE 8501 # Streamlit default port
EXPOSE 8000 # Orchestrator
EXPOSE 8001 # API Agent
EXPOSE 8002 # Scraping Agent
EXPOSE 8003 # Retriever Agent
EXPOSE 8004 # Analysis Agent
EXPOSE 8005 # Language Agent
EXPOSE 8006 # Voice Agent


# Command to run all FastAPI services and Streamlit
# This is a simplified approach for demonstration.
# In production, use a process manager like supervisord or separate containers.
CMD sh -c "uvicorn agents.api_agent:app --host 0.0.0.0 --port 8001 & \
           uvicorn agents.scraping_agent:app --host 0.0.0.0 --port 8002 & \
           uvicorn agents.retriever_agent:app --host 0.0.0.0 --port 8003 & \
           uvicorn agents.analysis_agent:app --host 0.0.0.0 --port 8004 & \
           uvicorn agents.language_agent:lang_app --host 0.0.0.0 --port 8005 & \
           uvicorn agents.voice_agent:app --host 0.0.0.0 --port 8006 & \
           uvicorn orchestrator.orchestrator:app --host 0.0.0.0 --port 8000 & \
           streamlit run streamlit_app/app.py --server.port 8501 --server.enableCORS false --server.enableXsrfProtection false"