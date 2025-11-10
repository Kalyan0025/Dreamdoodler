import os
from pathlib import Path
from textwrap import dedent

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as gen

from prompts import call_gemini, build_fallback_result

# ---------- Streamlit + Gemini config ----------

st.set_page_config(page_title="Visual Journal Bot", layout="wide")

st.title("🧠✨ Visual Journal Bot")
st.caption("Data Humanism engine — text or tables in, living visuals out on the canvas.")

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

# ---------- Sidebar: high-level choices ----------

mode_label = st.sidebar.selectbox(
    "What are you exploring?",
    ["Week / routine", "Dream", "Self / identity"],
)

mode_key = {
    "Week / routine": "week",
    "Dream": "dream",
    "Self / identity": "self",
}[mode_label]

input_style_label = st.sidebar.radio(
    "How are you giving the data?",
    ["Story / reflection", "Table / time series (CSV)"],
    help=(
        "Story = natural language journal entry.\n"
        "Table = CSV with repeated records (e.g., days, tasks, moods). "
        "The bot will treat this as temporal data and use calendar-style visuals."
    ),
)

input_style_key = "story" if input_style_label.startswith("Story") else "table_time_series"

st.sidebar.markdown("### Flow")
st.sidebar.write(
    "1. Pick a mode\n"
    "2. Choose story vs table\n"
    "3. Enter text / upload CSV\n"
    "4. Generate the visual\n"
    "5. Read yourself on the canvas ✨"
)

# ---------- Main input areas ----------

table_df = None
table_summary_text = None

if input_style_key == "story":
    default_placeholder = {
        "week": "This week felt slow but warm. I worked a lot, took two days fully off, and spent time with my sister.",
        "dream": "I was walking across floating islands in the night sky, with glass trees glowing softly.",
        "self": "I am a quiet observer who loves drawing, late-night walks, and listening to stories.",
    }[mode_key]

    user_text = st.text_area(
        "Write your reflection / dream / self-description:",
        height=220,
        placeholder=default_placeholder,
    )

else:
    st.markdown("#### Upload a CSV (routines / time series)")
    data_file = st.file_uploader(
        "Upload a CSV with one row per day / event / record.",
        type=["csv"],
        help="Example: a month of days with columns like date, weekday, hours_worked, stress, mode.",
    )

    user_text = st.text_area(
        "Describe what this dataset represents in your life (this is important for Data Humanism):",
        height=150,
        placeholder="e.g., This is my work log for last month: hours, mode (office/remote/off), and a quick stress rating.",
    )

    if data_file is not None:
        try:
            table_df = pd.read_csv(data_file)
        except Exception:
            st.error("Could not read the CSV. Make sure it is a valid UTF-8 CSV file.")
            table_df = None

        if table_df is not None:
            st.markdown("##### Preview of your data")
            st.dataframe(table_df.head(20))

            # Build a compact textual summary to send to Gemini
            max_rows = 30
            max_cols = 8
            small = table_df.iloc[:max_rows, :max_cols]
            preview_csv = small.to_csv(index=False)

            column_info = [
                {"name": col, "dtype": str(table_df[col].dtype)}
                for col in table_df.columns
            ]

            table_summary_text = dedent(
                f"""
                Dataset summary:
                - Shape: {table_df.shape[0]} rows × {table_df.shape[1]} columns
                - Columns (name, dtype): {column_info[:12]}
                - Preview (first {min(max_rows, len(table_df))} rows, up to {max_cols} columns) as CSV:
                {preview_csv}
                """
            )

use_demo = st.checkbox(
    "Force demo visual (ignore Gemini for now)",
    value=False,
    help="Useful for testing even when the API key is missing or the model is flaky.",
)

# ---------- Generate button ----------

if st.button("Generate Visual", type="primary"):
    if input_style_key == "story" and not user_text.strip():
        st.warning("Please write something first.")
    elif input_style_key == "table_time_series" and table_df is None:
        st.warning("Please upload a CSV file first.")
    else:
        # Try Gemini if available and not forcing demo
        result = None
        error_msg = None

        if api_key and not use_demo:
            try:
                result = call_gemini(
                    mode=mode_key,
                    user_text=user_text,
                    input_style=input_style_key,
                    table_summary=table_summary_text,
                )
            except Exception as e:
                error_msg = str(e)
                result = None

        # Fallback if Gemini failed or demo requested
        if result is None:
            if error_msg:
                st.error("Gemini failed, using a built-in demo visual instead.")
                with st.expander("Error details"):
                    st.code(error_msg, language="text")
            result = build_fallback_result(
                mode=mode_key,
                user_text=user_text,
                input_style=input_style_key,
            )

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
