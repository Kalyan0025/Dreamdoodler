import os
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as gen

from prompts import call_gemini, build_fallback_result

# ---------- Streamlit + Gemini config ----------

st.set_page_config(page_title="Visual Journal Bot", layout="wide")

st.title("🧠✨ Visual Journal Bot")
st.caption("Type a reflection → see it as a visual on the canvas.")

# Configure Gemini using Streamlit secrets (for Streamlit Cloud) or env var
api_key = None
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
else:
    api_key = os.getenv("GEMINI_API_KEY")

if api_key:
    gen.configure(api_key=api_key)
else:
    st.warning(
        "No GEMINI_API_KEY found. The app will use a built-in demo visual instead of AI-generated code."
    )

# ---------- Sidebar: mode selection ----------

mode_label = st.sidebar.selectbox(
    "What are you journaling?",
    ["Week reflection", "Dream", "Self-portrait"],
)

mode_key = {
    "Week reflection": "week",
    "Dream": "dream",
    "Self-portrait": "self",
}[mode_label]

st.sidebar.markdown("### How to use")
st.sidebar.write(
    "1. Choose a mode\n"
    "2. Write your journal entry\n"
    "3. Click **Generate Visual**\n"
    "4. Watch the canvas update 👀"
)

# ---------- Main input ----------

default_placeholder = {
    "week": "This week felt calm but meaningful. I finished my project and reconnected with an old friend.",
    "dream": "I was walking across floating islands in the night sky, with glass trees glowing softly.",
    "self": "I am a quiet observer who loves drawing, late-night walks, and listening to stories.",
}[mode_key]

user_text = st.text_area(
    "Write your journal entry:",
    height=200,
    placeholder=default_placeholder,
)

use_demo = st.checkbox(
    "Force demo visual (ignore Gemini for now)",
    value=False,
    help="Useful for testing even when the API key is missing or the model is flaky.",
)

# ---------- Generate button ----------

if st.button("Generate Visual", type="primary"):
    if not user_text.strip():
        st.warning("Please write something first.")
    else:
        # Try Gemini if available and not forcing demo
        result = None
        error_msg = None

        if api_key and not use_demo:
            try:
                result = call_gemini(mode_key, user_text)
            except Exception as e:
                error_msg = str(e)
                result = None

        # Fallback if Gemini failed or demo requested
        if result is None:
            if error_msg:
                st.error("Gemini failed, using a built-in demo visual instead.")
                st.code(error_msg, language="text")
            result = build_fallback_result(mode_key, user_text)

        # ---------- Show interpretation ----------
        st.subheader("How the bot interpreted this")
        st.write(result.get("summary", ""))

        schema = result.get("schema", {})
        if schema:
            with st.expander("Structured journal data (schema)", expanded=False):
                st.json(schema)

        # ---------- Render canvas ----------
        paperscript = result.get("paperscript", "").strip()
        if not paperscript:
            st.error("No PaperScript was generated.")
        else:
            template = Path("paper_template.html").read_text(encoding="utf-8")
            html = template.replace("// __PAPERSCRIPT_PLACEHOLDER__", paperscript)

            st.subheader("Visual Journal Canvas")
            components.html(html, height=620, scrolling=False)
