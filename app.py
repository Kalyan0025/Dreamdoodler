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

st.title("🧠✨ Visual Journal / Data Humanism Bot")
st.caption("Different kinds of life data → Dear Data–style visuals on a Paper.js canvas.")

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
        "No GEMINI_API_KEY found. The app will use a built-in demo visual instead of AI-generated sketches."
    )

# ---------- Sidebar: choose data type + input style ----------

mode_label = st.sidebar.selectbox(
    "What kind of data are you bringing?",
    [
        "Tracked week / routine (numbers over days)",  # Standard A or D
        "Stressful or emotional week (journal)",       # Standard B
        "Dream",                                       # Standard C
        "Attendance / presence over days",             # Standard D
        "Stats / categories & quantities",             # Standard E
    ],
)

# map to compact internal mode key
mode_key_map = {
    "Tracked week / routine (numbers over days)": "week",
    "Stressful or emotional week (journal)": "stress",
    "Dream": "dream",
    "Attendance / presence over days": "attendance",
    "Stats / categories & quantities": "stats",
}
mode = mode_key_map[mode_label]

# decide if this mode usually uses tabular data
default_input_style = "story"
allow_table = mode in {"week", "attendance", "stats"}

if allow_table:
    input_style_label = st.sidebar.radio(
        "How are you giving the data?",
        ["Story / description", "Spreadsheet / table (CSV)"],
        help=(
            "Story = natural language explanation of the data.\n"
            "Spreadsheet = upload a CSV and optionally describe what it represents."
        ),
    )
else:
    input_style_label = "Story / description"

input_style = "story" if input_style_label.startswith("Story") else "table_time_series"

st.sidebar.markdown("### Flow")
st.sidebar.write(
    "1. Pick the kind of data\n"
    "2. Choose story vs table if available\n"
    "3. Type / upload\n"
    "4. Click **Generate Visual** and read yourself on the canvas ✨"
)

# ---------- Main input areas ----------

table_df = None
table_summary_text = None

if input_style == "story":
    # helpful placeholders per mode
    placeholder_by_mode = {
        "week": dedent(
            """\
            Topic: How connected I felt this week.
            Time range: Monday–Sunday (7 days).

            What I tracked:
            - family_calls: number of calls with family (0–5)
            - friend_chats: number of chats with close friends (0–5)
            - work_messages: number of work-related messages that felt stressful (0–10)
            - mood: overall mood that day (1=low, 5=high)

            Data (per day): describe roughly or precisely, your choice.
            Reflection: how did the week feel overall?"""
        ),
        "stress": dedent(
            """\
            Topic: A very stressful week.

            Journal:
            Describe what made it stressful: exams, deadlines, people, lack of sleep...

            Rough sense of how big each thing felt (1–5):
            - Exams: 5
            - Conferences: 3
            - Part-time job: 4
            - Sleep / energy: 2

            Reflection:
            How did your body/mind feel by the end?"""
        ),
        "dream": dedent(
            """\
            Describe the dream in as much detail as you like.
            Example:
            Me and my friend Gomma were flying across space past glowing planets,
            drifting between small worlds, weightless and calm."""
        ),
        "attendance": dedent(
            """\
            Describe the attendance data.
            Example:
            This is one month of my office presence, one row per day,
            with 1 if I went in and 0 if I stayed home."""
        ),
        "stats": dedent(
            """\
            Describe your spreadsheet of stats.
            Example:
            A week of how many hours I spent in different areas of my life:
            Study, Work, Leisure, Chores. Each has sub-activities with total hours."""
        ),
    }

    user_text = st.text_area(
        "Describe your data / week / dream / statistics:",
        height=260,
        placeholder=placeholder_by_mode.get(mode, ""),
    )

else:
    # table / CSV input
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

            # Compact textual summary for Gemini
            max_rows = 40
            max_cols = 10
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

# which of the 5 visual standards should be preferred?
# A: week grid of circles + mood line
# B: stress flower
# C: dream ribbon & planets
# D: attendance calendar
# E: organic stacked columns
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
    "Force demo visual (ignore Gemini)", value=False,
    help="Useful for testing even without an API key or when the model misbehaves."
)

# ---------- Generate button ----------

if st.button("Generate Visual", type="primary"):
    if input_style == "story" and not user_text.strip():
        st.warning("Please write something first.")
    elif input_style == "table_time_series" and table_df is None:
        st.warning("Please upload a CSV file first.")
    else:
        result = None
        error_msg = None

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
                result = None

        if result is None:
            if error_msg:
                st.error("Gemini failed, using a built-in demo visual instead.")
                with st.expander("Error details"):
                    st.code(error_msg, language="text")
            result = build_fallback_result(
                mode=mode,
                user_text=user_text,
                input_style=input_style,
                visual_standard_hint=visual_standard_hint,
            )

        # ---------- Show interpretation ----------
        st.subheader("How the bot interpreted this")
        st.write(result.get("summary", ""))

        schema = result.get("schema", {})
        if schema:
            with st.expander("Structured interpretation (schema)", expanded=False):
                st.json(schema)

        # ---------- Render Paper.js canvas ----------
        paperscript = result.get("paperscript", "").strip()
        if not paperscript:
            st.error("No PaperScript was generated.")
        else:
            template = Path("paper_template.html").read_text(encoding="utf-8")
            html = template.replace("// __PAPERSCRIPT_PLACEHOLDER__", paperscript)
            st.subheader("Visual Canvas")
            components.html(html, height=640, scrolling=False)
