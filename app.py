#############################################
# app.py — Visual Journal / Data Humanism Bot
# FINAL FULLY REPLACABLE VERSION
#############################################

import os
from pathlib import Path
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# Internal modules
from prompts import call_gemini, has_gemini_key
from schema_generator import generate_schema
from renderer_selector import select_renderer


# ---------------- STREAMLIT BASE CONFIG ----------------
st.set_page_config(
    page_title="Visual Journal Bot",
    layout="wide",
)

st.title("🧠✨ Visual Journal / Data Humanism Bot")
st.caption("Any life data → Dear Data–style human visuals with Paper.js.")


# ---------------- API KEY STATUS ----------------
if has_gemini_key():
    st.sidebar.success("Gemini API key loaded ✔")
else:
    st.sidebar.error("No GEMINI_API_KEY found — using LLM summary only, visuals still work ✔")


# ---------------- MODE SELECTION ----------------
st.sidebar.markdown("### What kind of data are you sharing?")

mode_label = st.sidebar.selectbox(
    "Choose input type:",
    [
        "Auto Detect",
        "Tracked Week / Routine",
        "Stressful or Emotional Week",
        "Dream / Memory",
        "Attendance / Presence (CSV)",
        "Numeric Stats / Time Categories (CSV)",
    ],
)

MODE_MAP = {
    "Tracked Week / Routine": "week",
    "Stressful or Emotional Week": "stress",
    "Dream / Memory": "dream",
    "Attendance / Presence (CSV)": "attendance",
    "Numeric Stats / Time Categories (CSV)": "stats",
}

if mode_label == "Auto Detect":
    mode = "auto"
else:
    mode = MODE_MAP[mode_label]


# ---------------- USER INPUT ----------------
st.subheader("Describe your week / dream / stress / attendance / stats")
st.write("Write freely in your own words.")

user_text = st.text_area(
    "Write here:",
    height=220,
    placeholder="Describe your week, stress, dream, or stats…",
)

upload = None
table_summary = None

if mode in ["attendance", "stats", "auto"]:
    st.markdown("#### (optional) Upload CSV for attendance or numeric stats")
    upload = st.file_uploader("Upload CSV", type=["csv"])
    if upload:
        try:
            df = pd.read_csv(upload)
            st.markdown("##### Data preview")
            st.dataframe(df.head(30))

            # Keep a trimmed version to feed the LLM
            df_small = df.iloc[:40, :10]
            table_summary = df_small.to_csv(index=False)

        except Exception as e:
            st.error("Could not read the CSV file.")
            st.code(str(e))
            table_summary = None


# ---------------- GENERATE VISUAL ----------------
if st.button("✨ Generate Visual", type="primary"):

    if not (user_text or "").strip() and not upload:
        st.warning("Please write something or upload a CSV.")
        st.stop()

    # 1. LLM SUMMARY (semantic meaning only)
    try:
        llm_result = call_gemini(
            user_text=user_text,
            table_csv=table_summary,
            selected_mode=mode,
        )
        st.success("LLM summary generated ✔")
    except Exception as e:
        st.error("Gemini failed — continuing with local interpretation.")
        st.code(str(e))
        llm_result = {
            "summary": "LLM unavailable — using deterministic interpretation.",
            "mood_keywords": ["calm"],
            "color_keywords": ["blue"],
            "imagery": [],
            "journal_type": "auto",
        }

    st.subheader("How the bot interpreted this")
    st.write(llm_result.get("summary", ""))

    # 2. SCHEMA GENERATION (core human logic)
    schema = generate_schema(
        raw_text=user_text,
        csv_text=table_summary,
        llm_meta=llm_result,
        forced_mode=mode,
    )

    with st.expander("Schema (internal representation)", expanded=False):
        st.json(schema)

    # 3. SELECT RENDERER → PAPER.JS SCRIPT
    paperscript = select_renderer(schema)

    # 4. INSERT INTO TEMPLATE
    try:
        template = Path("paper_template.html").read_text(encoding="utf-8")
    except Exception as e:
        st.error("Could not load paper_template.html")
        st.code(str(e))
        st.stop()

    final_html = template.replace("// __PAPERSCRIPT_PLACEHOLDER__", paperscript)

    # 5. DISPLAY CANVAS
    st.subheader("🎨 Visual Canvas (Dear Data Rendering)")
    components.html(final_html, height=760, scrolling=False)
