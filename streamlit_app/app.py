import streamlit as st
import requests
import base64
import json
import io
import numpy as np # For audio playback workaround on Streamlit
import soundfile as sf
import pydub

# Assume orchestrator is running on 8000
ORCHESTRATOR_URL = "http://localhost:8000/orchestrate/market_brief/"

st.set_page_config(layout="wide", page_title="Finance Assistant")

st.title("🗣️ AI Finance Assistant: Morning Market Brief")

st.markdown("""
Welcome to your AI Finance Assistant! Ask about your risk exposure in Asia tech stocks and any earnings surprises.
""")

# Input method selection
input_method = st.radio("Choose Input Method:", ("Text Input", "Voice Input"))

brief_text = ""
audio_brief_bytes = None

if input_method == "Text Input":
    user_question = st.text_area(
        "Enter your question:",
        "What’s our risk exposure in Asia tech stocks today, and highlight any earnings surprises?"
    )
    if st.button("Get Market Brief (Text)"):
        if user_question:
            with st.spinner("Generating brief..."):
                try:
                    response = requests.post(
                        ORCHESTRATOR_URL,
                        json={"query_text": user_question}
                    )
                    response.raise_for_status()
                    brief_data = response.json()
                    brief_text = brief_data.get("brief_text", "No brief generated.")
                    if brief_data.get("audio_brief_base64"):
                        audio_brief_bytes = base64.b64decode(brief_data["audio_brief_base64"])
                except requests.exceptions.ConnectionError:
                    st.error("Could not connect to the orchestrator. Please ensure all FastAPI services are running.")
                except requests.exceptions.HTTPError as e:
                    st.error(f"HTTP Error: {e.response.status_code} - {e.response.text}")
                except Exception as e:
                    st.error(f"An error occurred: {e}")
        else:
            st.warning("Please enter a question.")

elif input_method == "Voice Input":
    audio_file = st.file_uploader("Upload your audio question (WAV format recommended):", type=["wav", "mp3"])

    if st.button("Get Market Brief (Voice)"):
        if audio_file:
            with st.spinner("Processing voice input and generating brief..."):
                try:
                    # Convert audio to base64
                    audio_bytes = audio_file.read()
                    audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')

                    response = requests.post(
                        ORCHESTRATOR_URL,
                        json={"audio_file_base64": audio_base64}
                    )
                    response.raise_for_status()
                    brief_data = response.json()
                    brief_text = brief_data.get("brief_text", "No brief generated.")
                    if brief_data.get("audio_brief_base64"):
                        audio_brief_bytes = base64.b64decode(brief_data["audio_brief_base64"])

                except requests.exceptions.ConnectionError:
                    st.error("Could not connect to the orchestrator. Please ensure all FastAPI services are running.")
                except requests.exceptions.HTTPError as e:
                    st.error(f"HTTP Error: {e.response.status_code} - {e.response.text}")
                except Exception as e:
                    st.error(f"An error occurred: {e}")
        else:
            st.warning("Please upload an audio file.")

if brief_text:
    st.subheader("Market Brief:")
    st.write(brief_text)

    if audio_brief_bytes:
        st.subheader("Listen to the Brief:")
        st.audio(audio_brief_bytes, format='audio/mpeg') # gTTS produces MP3