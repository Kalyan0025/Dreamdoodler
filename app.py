import os
from pathlib import Path
from textwrap import dedent

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as gen

from prompts import call_gemini, build_fallback_result


st.set_page_config(page_title="Visual Journal Bot", layout="wide")

st.title("🧠✨ Visual Journal / Data Humanism Bot")
st.caption("Different kinds of life data → Dear Data–style visuals on a Paper.js canvas.")

# ---------- Gemini config ----------
api_key = None
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
else:
    api_key = os.getenv("GEMINI_API_KEY")

if api_key:
    gen.configure(api_key=api_key)
    st.sidebar.success("Gemini API key loaded ✅")
else:
    st.sidebar.error("No GEMINI_API_KEY found ❌ — app will use fallback visuals only.")


# ---------- Sidebar: data type & input style ----------

mode_label = st.sidebar.selectbox(
    "What kind of data are you bringing?",
    [
        "Tracked week / routine (numbers over days)",  # Standard A or D
        "Stressful or emotional week (journal)",       # Standard B
        "Dream",                                       # Standard C
        "Attendance / presence over days",             # Standard D
        "Time stats / categories",                     # Standard E
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

if mode in ["week", "stress", "dream"]:
    input_style = st.sidebar.radio(
        "How will you share it?",
        ["story"],
        index=0,
        help="These are meant to be written like mini journal entries.",
    )
else:
    input_style = st.sidebar.radio(
        "How will you share it?",
        ["story", "table_time_series"],
        index=0,
        help="For attendance / stats, you can either describe it in words or upload a CSV.",
    )

st.sidebar.markdown("---")

st.markdown(
    "#### How to use this\n"
    "1. Pick the kind of data\n"
    "2. Choose story vs table if available\n"
    "3. Type / upload\n"
    "4. Click **Generate Visual** and read yourself on the canvas ✨"
)

# ---------- Inputs ----------

table_df = None
table_summary_text = None

if input_style == "story":
    placeholder_by_mode = {
        "week": dedent(
            """\
            Topic: Your week of connections.

            For each day, roughly describe:
            - Any calls, chats, or messages (with whom?)
            - Any in-person time (with whom?)
            - Any quiet / alone moments

            Then a short reflection on how the week felt overall."""
        ),
        "stress": dedent(
            """\
            Topic: A very stressful week.

            Journal:
            Describe what made it stressful: exams, deadlines, people, lack of sleep...

            Rough sense of how big each thing felt (1–5):
            - Exams: 5
            - Work / part-time job: 4
            - Sleep / energy: 2

            Reflection:
            How did your body/mind feel by the end?"""
        ),
        "dream": dedent(
            """\
            Describe the dream in as much detail as you like.
            Example:
            Me and my friend were flying across space past glowing planets,
            drifting between small worlds, weightless and calm."""
        ),
        "attendance": dedent(
            """\
            Describe the attendance data.
            Example:
            This is one month of my office presence. I want to see a visual of days I showed up vs days I worked from home."""
        ),
        "stats": dedent(
            """\
            Describe what your time stats represent.
            Example:
            How many hours I spent last week on study, work, rest, friendships, etc."""
        ),
    }

    user_text = st.text_area(
        "Journal / description",
        height=260,
        placeholder=placeholder_by_mode.get(mode, "Describe your data / week / dream in your own words."),
    )
else:
    st.markdown("#### Upload a CSV")

    help_text = {
        "week": "e.g. one row per day with columns like date, family_calls, friend_chats, work_messages, mood_score.",
        "attendance": "e.g. one row per day with columns date, weekday, attended (0/1).",
        "stats": "e.g. one row per sub-activity with columns category, subcategory, hours.",
    }.get(mode, "One row per record, numeric or categorical columns are all okay.")

    data_file = st.file_uploader(help_text, type=["csv"])

    user_text = st.text_area(
        "In words, what does this table represent in your life?",
        height=150,
        placeholder="Write a short explanation so the visual can be human and readable.",
    )

    if data_file is not None:
        try:
            table_df = pd.read_csv(data_file)
        except Exception:
            st.error("Could not read the CSV. Make sure it is a valid UTF-8 CSV file.")
            table_df = None

        if table_df is not None:
            st.markdown("##### Preview of your data")
            st.dataframe(table_df.head(25))

            max_rows = 40
            max_cols = 10
            df_small = table_df.iloc[:max_rows, :max_cols]
            table_summary_text = df_small.to_csv(index=False)
        else:
            table_summary_text = None
    else:
        table_summary_text = None

# ---------- Choose visual standard hint (A–E) ----------

if mode == "week" and input_style == "story":
    visual_standard_hint = "A"
elif mode == "stress":
    visual_standard_hint = "B"
elif mode == "dream":
    visual_standard_hint = "C"
elif mode == "attendance":
    visual_standard_hint = "D"
elif mode == "week" and input_style == "table_time_series":
    visual_standard_hint = "D"
elif mode == "stats":
    visual_standard_hint = "E"
else:
    visual_standard_hint = "A"

use_demo = st.checkbox(
    "Force demo visual (ignore Gemini)",
    value=False,
    help="Useful for testing even without an API key or when the model misbehaves.",
)

st.sidebar.markdown("### Debug")
st.sidebar.write(f"Mode: `{mode}`  •  Input style: `{input_style}`  •  Hint: `{visual_standard_hint}`")


# ---------- Generate ----------

if st.button("Generate Visual", type="primary"):
    if input_style == "story" and not (user_text or "").strip():
        st.warning("Please write something first.")
    elif input_style == "table_time_series" and table_df is None:
        st.warning("Please upload a CSV file first.")
    else:
        result = None
        error_msg = None
        error_reason = None

        if api_key and not use_demo:
            try:
                result = call_gemini(
                    mode=mode,
                    user_text=user_text,
                    input_style=input_style,
                    table_summary=table_summary_text,
                    visual_standard_hint=visual_standard_hint,
                )
            except Exception as e:
                error_msg = str(e)
                error_reason = "Gemini call or JSON parsing failed."
                result = None
        else:
            if not api_key:
                error_reason = "No GEMINI_API_KEY configured."
            elif use_demo:
                error_reason = "Demo mode forced (checkbox checked)."

        if result is None:
            st.error("Using fallback visual instead of AI illustration.")
            if error_reason:
                st.write(f"**Reason:** {error_reason}")
            if error_msg:
                with st.expander("Error details from Gemini / JSON parsing"):
                    st.code(error_msg, language="text")

            result = build_fallback_result(
                mode=mode,
                user_text=user_text,
                input_style=input_style,
                visual_standard_hint=visual_standard_hint,
            )

        st.subheader("How the bot interpreted this")
        st.write(result.get("summary", ""))

        schema = result.get("schema", {})
        if schema:
            with st.expander("Structured interpretation (schema)", expanded=False):
                st.json(schema)

        paperscript = (result.get("paperscript") or "").strip()
        if not paperscript:
            st.error("No PaperScript was generated in the result.")
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
