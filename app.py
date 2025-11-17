import os
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as gen  # needed so Streamlit Cloud has it imported

from prompts import call_gemini, build_fallback_result, has_gemini_key
from dear_data_renderer import render_week_standard_a, render_single_mood_tile


st.set_page_config(page_title="Visual Journal Bot", layout="wide")

st.title("🧠✨ Visual Journal / Data Humanism Bot")
st.caption("Different kinds of life data → Dear Data–style visuals on a Paper.js canvas.")


# ---------- API key status ----------
if has_gemini_key():
    st.sidebar.success("Gemini API key loaded ✔")
else:
    st.sidebar.error("No GEMINI_API_KEY found — app will use fallback visuals.")


# ---------- Sidebar: mode selection ----------
mode_label = st.sidebar.selectbox(
    "What kind of life data are you bringing?",
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


def _looks_like_single_moment(text: str) -> bool:
    """
    Heuristic: if the user text is very short and has no obvious
    temporal phrases, treat it as a single emotional moment instead
    of a whole-week timeline.
    """
    if not text:
        return False

    words = text.strip().split()
    if len(words) < 15:
        # check if there are any time-related words
        time_markers = [
            "yesterday",
            "today",
            "tomorrow",
            "morning",
            "evening",
            "night",
            "then",
            "after",
            "before",
            "later",
            "earlier",
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        ]
        lower = text.lower()
        if not any(tok in lower for tok in time_markers):
            return True
    return False


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

use_demo = st.sidebar.checkbox("Force fallback visual (ignore Gemini)", value=False)

# ---------- Instructions ----------
st.markdown(
    "#### How to use this\n"
    "1. Pick the kind of data\n"
    "2. If available, choose story vs table\n"
    "3. Type or upload\n"
    "4. Click **Generate Visual** to see your canvas ✨"
)

st.subheader("Journal / description")

table_summary_text = None

if input_style == "story":
    user_text = st.text_area(
        "Write here:",
        height=260,
        placeholder="Describe your week / stress / dream / attendance / stats in your own words…",
    )
else:
    user_text = st.text_area(
        "Describe what this table represents in your life:",
        height=160,
        placeholder="Short description so the visual can stay human (e.g., 'two weeks of office attendance').",
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
        # Decide an "API mode" — for stress we split between timeline vs single moment
        if mode == "stress" and _looks_like_single_moment(user_text or ""):
            api_mode = "stress_single"
        else:
            api_mode = mode

        # 1. get LLM output or fallback
        if use_demo or not has_gemini_key():
            result = build_fallback_result(api_mode, user_text, input_style, visual_standard_hint)
        else:
            try:
                result = call_gemini(
                    mode=api_mode,
                    user_text=user_text,
                    input_style=input_style,
                    table_summary=table_summary_text,
                    visual_standard_hint=visual_standard_hint,
                )
            except Exception as e:
                st.error("Gemini call / JSON parse failed → using fallback.")
                st.code(str(e))
                result = build_fallback_result(api_mode, user_text, input_style, visual_standard_hint)

        # 2. Show summary + schema
        st.subheader("How the bot interpreted this")
        st.write(result.get("summary", ""))

        schema = result.get("schema", {})
        if schema:
            with st.expander("Structured schema (for Dear Data rendering)", expanded=False):
                st.json(schema)

        # 3. Decide which PaperScript to use
        schema_mode = schema.get("mode") or api_mode

        paperscript: str = ""

        try:
            if schema_mode == "week":
                # Dear Data week postcard renderer
                paperscript = render_week_standard_a(schema)
            elif schema_mode == "stress_single":
                # Single mood tile for things like "hi, I'm sad"
                paperscript = render_single_mood_tile(schema)
            else:
                # Fallback: let model provide its own PaperScript, if any
                paperscript = (result.get("paperscript") or "").strip()
        except Exception as e:
            st.error("Renderer failed, falling back to any model-provided PaperScript.")
            st.code(str(e))
            paperscript = (result.get("paperscript") or "").strip()

        # 4. Actually embed into the Paper.js HTML shell
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
                st.subheader("Visual Canvas")
                components.html(html, height=640, scrolling=False)
