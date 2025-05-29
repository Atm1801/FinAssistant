# streamlit_app.py
import streamlit as st
import requests
import json

st.set_page_config(layout="wide")

# Backend API endpoints (replace with your actual orchestrator URL if different)
ORCHESTRATOR_URL = "http://localhost:8000"

st.title("📈 AI-Powered Financial Market Brief Generator")

st.markdown("""
Welcome to your AI Financial Analyst! Ask a question about the market, specific stocks, or your portfolio, and I'll generate a comprehensive brief for you.
""")

# User input for the question
user_question = st.text_area(
    "What financial insights are you looking for today? (e.g., 'Analyze MSFT and GOOGL performance today and recent news.', 'What's the current market sentiment?', 'How did NVDA perform historically?')",
    height=100,
    key="user_question_input"
)

# User input for portfolio data (optional)
st.subheader("Optional: Your Portfolio Initial Data")
st.markdown("Provide initial allocation data to get a personalized analysis. (e.g., `{\"MSFT\": 0.3, \"GOOGL\": 0.2, \"Other\": 0.5}`)")
portfolio_input_str = st.text_area(
    "Enter your portfolio data as a JSON object (or leave empty):",
    value="{}", # <-- Changed default value to an empty JSON object
    height=100,
    key="portfolio_input"
)

portfolio_data = {}
if portfolio_input_str:
    try:
        portfolio_data = json.loads(portfolio_input_str)
    except json.JSONDecodeError:
        st.error("Invalid JSON format for portfolio data. Please enter a valid JSON object.")
        portfolio_data = None # Indicate invalid data

if st.button("Generate Market Brief", type="primary"):
    if not user_question:
        st.warning("Please enter a question to get a market brief.")
    elif portfolio_data is not None:
        with st.spinner("Generating your market brief... This may take a moment as AI analyzes current data and news."):
            try:
                # Prepare the request payload
                payload = {
                    "question": user_question,
                    "portfolio_initial_data": portfolio_data
                }
                headers = {"Content-Type": "application/json"}

                # Send request to the Orchestrator
                response = requests.post(f"{ORCHESTRATOR_URL}/orchestrate/generate_brief/", json=payload, headers=headers)
                response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
                
                brief_data = response.json()
                st.subheader("📊 Your Market Brief:")
                st.markdown(brief_data.get("brief", "No brief could be generated at this time. Please check your inputs or try again later."))

            except requests.exceptions.ConnectionError:
                st.error("Could not connect to the backend API. Please ensure all agents and the orchestrator are running.")
            except requests.exceptions.HTTPError as e:
                st.error(f"Error from API: {e}. Detail: {e.response.json().get('detail', 'No additional detail.')}")
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")
    else:
        st.info("Please correct the portfolio data JSON format before generating the brief.")

st.markdown("---")