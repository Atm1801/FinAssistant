import streamlit as st
import requests
import json
import base64
from io import BytesIO

# Import mic_recorder
from streamlit_mic_recorder import mic_recorder

st.set_page_config(layout="wide")

# Backend API endpoints
ORCHESTRATOR_URL = "http://localhost:8000" # Ensure this matches your orchestrator's running port

st.title("📈 AI-Powered Financial Market Brief Generator")

st.markdown("""
Welcome to your AI Financial Analyst! Ask a question about the market, specific stocks, or your portfolio.
I'll generate a comprehensive brief, and can even read out the conclusion for you!
""")

# Input Method Selection
input_method = st.radio(
    "Choose your input method:",
    ("Text Input", "Voice Input"),
    key="input_method_radio"
)

user_question = ""
audio_file_base64 = None # This will hold the base64 encoded audio if voice input is used

if input_method == "Text Input":
    user_question = st.text_area(
        "What financial insights are you looking for today? (e.g., 'Analyze MSFT and GOOGL performance today and recent news.', 'What's the current market sentiment?', 'How did NVDA perform historically?')",
        height=100,
        key="user_question_text_input"
    )
else: # Voice Input selected
    st.write("How would you like to provide your voice query?")
    voice_input_option = st.radio(
        "Choose voice input option:",
        ("Record from Microphone", "Upload Audio File"),
        key="voice_input_option_radio"
    )

    if voice_input_option == "Record from Microphone":
        st.info("Click the microphone to record your question. Click again to stop.")
        audio = mic_recorder(
            start_prompt="Start recording",
            stop_prompt="Stop recording",
            key="voice_input_recorder"
        )
        if audio:
            st.audio(audio['bytes']) # Play back recorded audio for user confirmation
            audio_file_base64 = base64.b64encode(audio['bytes']).decode('utf-8')
            st.success("Audio recorded and ready for processing!")
        else:
            st.info("No audio recorded yet.")
    else: # Upload Audio File
        st.info("Upload an audio file (WAV or MP3 recommended).")
        uploaded_audio_file = st.file_uploader("Upload your audio file:", type=["wav", "mp3", "ogg"], key="audio_uploader")
        if uploaded_audio_file:
            audio_bytes = uploaded_audio_file.read()
            st.audio(audio_bytes) # Play back uploaded audio for user confirmation
            audio_file_base64 = base64.b64encode(audio_bytes).decode('utf-8')
            st.success("Audio file uploaded and ready for processing!")
        else:
            st.info("Please upload an audio file.")

# --- Optional Portfolio Input ---
st.subheader("Optional: Your Portfolio Initial Data")
st.markdown("Provide initial allocation data to get a personalized analysis. (e.g., `{\"MSFT\": 0.3, \"GOOGL\": 0.2, \"Other\": 0.5}`)")
portfolio_input_str = st.text_area(
    "Enter your portfolio data as a JSON object (or leave empty):",
    value="{}",
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

# --- Generate Brief Button ---
if st.button("Generate Market Brief", type="primary"):
    # Input validation
    if (input_method == "Text Input" and not user_question.strip()) or \
       (input_method == "Voice Input" and not audio_file_base64):
        st.warning("Please provide a query (text or voice) to generate a market brief.")
    elif portfolio_data is None:
        st.info("Please correct the portfolio data JSON format before generating the brief.")
    else:
        with st.spinner("Generating your market brief... This may take a moment as AI analyzes current data and news."):
            try:
                # Prepare the request payload
                payload = {
                    "query_text": user_question if input_method == "Text Input" else None,
                    "audio_file_base64": audio_file_base64 if input_method == "Voice Input" else None,
                    "portfolio_data": portfolio_data
                }
                headers = {"Content-Type": "application/json"}

                # Send request to the Orchestrator
                response = requests.post(f"{ORCHESTRATOR_URL}/orchestrate/generate_brief/", json=payload, headers=headers)
                response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)

                brief_data = response.json()
                final_brief_text = brief_data.get("brief_text")
                conclusion_audio_base64 = brief_data.get("conclusion_audio_base64")

                st.subheader("📊 Your Market Brief:")
                if final_brief_text:
                    st.markdown(final_brief_text)
                else:
                    st.markdown("No brief could be generated at this time. Please check your inputs or try again later.")

                if conclusion_audio_base64:
                    st.subheader("🔊 Listen to the Conclusion:")
                    try:
                        audio_bytes = base64.b64decode(conclusion_audio_base64)
                        st.audio(BytesIO(audio_bytes), format="audio/mpeg", start_time=0)
                    except Exception as audio_err:
                        st.error(f"Could not play conclusion audio: {audio_err}")
                else:
                    st.info("No audio conclusion available for this brief.")

            except requests.exceptions.ConnectionError:
                st.error("Could not connect to the backend API. Please ensure all agents and the orchestrator are running.")
            except requests.exceptions.HTTPError as e:
                error_detail = e.response.json().get('detail', 'No additional detail.') if e.response else str(e)
                st.error(f"Error from API: {e}. Detail: {error_detail}")
                st.info("Please check the console/terminal where your agents are running for more specific error messages.")
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")
    # This 'else' block was previously misplaced, it should be part of the outer 'if'
    # It seems it was duplicated or incorrectly indented.
    # The portfolio_data check is handled at the start of the 'if st.button' block now.

# Footer
st.markdown("---")