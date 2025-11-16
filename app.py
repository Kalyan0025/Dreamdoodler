import os
from pathlib import Path
from textwrap import dedent

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as gen

from prompts import call_gemini, build_fallback_result


st.set_page_config(page_title="Visual Journal Bot", layout="wide")

# ---------- API KEY ----------
api_key = None
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
else:
    api_key = os.getenv("GEMINI_API_KEY")

if api_key:
    gen.configure(api_key=api_key)
    st.sidebar.success("Gemini API key loaded ✔")
else:
    st.sidebar.error("No GEMINI_API_KEY found — demo mode only")


# ---------- SIDEBAR ----------
mode_label = st.sidebar.selectbox(
    "What kind of data?",
    [
        "Tracked week / routine (numbers over days)",
        "Stressful or emotional week (journal)",
        "Dream",
        "Attendance / presence over days",
        "Time stats / categories",
    ],
)

mode_map = {
    "Tracked week / routine (numbers over days)": "week",
    "Stressful or emotional week (journal)": "stress",
    "Dream": "dream",
    "Attendance / presence over days": "attendance",
    "Time stats / categories": "stats",
}
mode = mode_map[mode_label]

# Input style logic
if mode in ["week", "stress", "dream"]:
    input_style = "story"
else:
    input_style = st.sidebar.radio("How will you share it?", ["story", "table_time_series"])

# Visual hint (your existing logic)
if mode == "week":
    visual_standard_hint = "A"
elif mode == "stress":
    visual_standard_hint = "B"
elif mode == "dream":
    visual_standard_hint = "C"
elif mode == "attendance":
    visual_standard_hint = "D"
else:
    visual_standard_hint = "E"

use_demo = st.sidebar.checkbox("Force demo visual")


# ---------- INPUT AREA ----------
st.subheader("Journal / Description")

if input_style == "story":
    user_text = st.text_area("Write here:", height=240, placeholder="Write your story...")
    table_summary_text = ""
else:
    user_text = st.text_area("Describe the table:", height=120)
    upload = st.file_uploader("Upload CSV", type=["csv"])
    table_summary_text = None

    if upload:
        try:
            df = pd.read_csv(upload)
            st.write(df.head())
            df_small = df.iloc[:40, :10]
            table_summary_text = df_small.to_csv(index=False)
        except:
            st.error("Could not read CSV.")
            table_summary_text = None


# ---------- GENERATE ----------
if st.button("Generate Visual"):
    if use_demo or not api_key:
        result = build_fallback_result(mode, user_text, input_style, visual_standard_hint)
    else:
        try:
            result = call_gemini(
                mode=mode,
                user_text=user_text,
                input_style=input_style,
                table_summary=table_summary_text,
                visual_standard_hint=visual_standard_hint,
            )
        except Exception as e:
            st.error("Gemini / JSON error → fallback used.")
            st.code(str(e))
            result = build_fallback_result(mode, user_text, input_style, visual_standard_hint)

    st.subheader("Summary")
    st.write(result["summary"])

    st.subheader("Schema")
    st.json(result["schema"])

    paperscript = result["paperscript"]

    # ---------- CANVAS ----------
    template = Path("paper_template.html").read_text(encoding="utf-8")
    final_html = template.replace("// __PAPERSCRIPT_PLACEHOLDER__", paperscript)

    st.subheader("Canvas")
    components.html(final_html, height=650, scrolling=False)
