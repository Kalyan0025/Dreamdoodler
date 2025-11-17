import os
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as gen  # ensure dependency is loaded on Streamlit Cloud

from prompts import call_gemini, build_fallback_result, has_gemini_key
from dear_data_renderer import (
    render_week_wave_A,
    render_stress_storm_B,
    render_dream_planets_C,
    render_attendance_grid_D,
    render_stats_handdrawn_E,
)


st.set_page_config(page_title="Visual Journal Bot", layout="wide")

st.title("🧠✨ Visual Journal / Data Humanism Bot")
st.caption("Any life data → Dear Data–style human visuals on a Paper.js canvas.")


# ---------- API key status ----------
if has_gemini_key():
    st.sidebar.success("Gemini API key loaded ✔")
else:
    st.sidebar.error("No GEMINI_API_KEY found — app will use local Dear-Data logic only.")


# ---------- Sidebar: mode selection ----------
mode_label = st.sidebar.selectbox(
    "What kind of data are you bringing?",
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

# input style
if mode in ["week", "stress", "dream"]:
    input_style = "story"
else:
    input_style = st.sidebar.radio("How will you share it?", ["story", "table_time_series"])

# visual hint -> standard A–E
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

use_demo = st.sidebar.checkbox("Force local visual (ignore Gemini)", value=False)

# ---------- Instructions ----------
st.markdown(
    "#### How to use this\n"
    "1. Pick the kind of data\n"
    "2. If available, choose story vs table\n"
    "3. Type or upload\n"
    "4. Click **Generate Visual** to see your Dear-Data canvas ✨"
)

st.subheader("Describe your week / dream / stress / attendance / stats")
st.caption("Write freely in your own words.")

table_summary_text = None

if input_style == "story":
    user_text = st.text_area(
        "Write here:",
        height=260,
        placeholder="Describe your week / stress / dream / attendance / stats in your own words…",
    )
else:
    user_text = st.text_area(
        "What does this table represent in your life?",
        height=140,
        placeholder="Short human description (e.g., 'three months of office attendance').",
    )
    upload = st.file_uploader("Upload CSV", type=["csv"])
    if upload is not None:
        try:
            df = pd.read_csv(upload)
            st.markdown("##### Data preview")
            st.dataframe(df.head(25))
            df_small = df.iloc[:40, :10]
            table_summary_text = df_small.to_csv(index=False)
        except Exception as e:
            st.error("Could not read the CSV file.")
            st.code(str(e))
            table_summary_text = None


# ---------- Generate ----------
if st.button("Generate Visual", type="primary"):
    if input_style == "story" and not (user_text or "").strip():
        st.warning("Please write something first.")
    elif input_style == "table_time_series" and table_summary_text is None:
        st.warning("Please upload a CSV file or check that it loaded correctly.")
    else:
        # 1. get LLM summary + local schema or full local fallback
        if use_demo or not has_gemini_key():
            st.info("Gemini unavailable or bypassed — using deterministic Dear-Data interpretation.")
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
                st.error("Gemini failed — continuing with local interpretation.")
                st.code(str(e))
                result = build_fallback_result(mode, user_text, input_style, visual_standard_hint)

        # 2. Show summary + schema
        st.subheader("How the bot interpreted this")
        st.write(result.get("summary", ""))

        schema = result.get("schema", {}) or {}
        if schema:
            with st.expander("Schema (internal representation)", expanded=False):
                st.json(schema)

        # 3. Choose renderer based on schema.mode
        schema_mode = schema.get("mode") or mode

        paperscript: str
        try:
            if schema_mode == "week":
                paperscript = render_week_wave_A(schema)
            elif schema_mode == "stress":
                paperscript = render_stress_storm_B(schema)
            elif schema_mode == "dream":
                paperscript = render_dream_planets_C(schema)
            elif schema_mode == "attendance":
                paperscript = render_attendance_grid_D(schema)
            else:
                paperscript = render_stats_handdrawn_E(schema)
        except Exception as e:
            st.error("Dear-Data renderer crashed — showing raw PaperScript from Gemini (if any).")
            st.code(str(e))
            paperscript = (result.get("paperscript") or "").strip()

        # 4. Embed into Paper.js HTML shell
        if not paperscript:
            st.error("No PaperScript available to draw anything.")
        else:
            try:
                template = Path("paper_template.html").read_text(encoding="utf-8")
            except Exception as e:
                st.error("Could not read paper_template.html")
                st.code(str(e))
            else:
                html = template.replace("// __PAPERSCRIPT_PLACEHOLDER__", paperscript)
                st.subheader("🎨 Visual Canvas (Dear Data Rendering)")
                components.html(html, height=640, scrolling=False)
