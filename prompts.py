#############################################
# prompts.py — Gemini Summary + Semantic Layer
# FINAL FULLY REPLACABLE VERSION
#############################################

import os
import json
from pathlib import Path
from textwrap import dedent
import google.generativeai as gen


# -----------------------------------------------------------
# LOAD IDENTITY (your personality + data humanism persona)
# -----------------------------------------------------------
IDENTITY_TEXT = Path("identity.txt").read_text(encoding="utf-8")

API_KEY = os.getenv("GEMINI_API_KEY")
if API_KEY:
    gen.configure(api_key=API_KEY)


def has_gemini_key() -> bool:
    return bool(API_KEY)


# -----------------------------------------------------------
# PROMPT BUILDER
# -----------------------------------------------------------
def build_prompt(user_text: str, table_csv: str, selected_mode: str):
    """
    Build the LLM instruction for semantic interpretation ONLY.
    The LLM is NOT responsible for schema creation or PaperScript.
    """

    table_block = table_csv.strip() if table_csv else "[no_table]"

    return dedent(f"""
        {IDENTITY_TEXT}

        ------------------------------------------------------------
        YOU ARE A DATA HUMANISM INTERPRETATION ENGINE (DEAR DATA STYLE)
        ------------------------------------------------------------

        Your job:
         - Interpret the user's text as a meaningful human narrative.
         - Detect emotion, mood, tone, energy, rhythms, and story arcs.
         - Identify what KIND of journal entry this is (week / stress / dream / attendance / stats).
         - Extract keywords for color theory, symbols, imagery, textures.
         - DO NOT create schema.
         - DO NOT create PaperScript.
         - DO NOT format visuals.
         - ONLY give interpretation, not drawing.

        ------------------------------------------------------------
        INPUT
        ------------------------------------------------------------

        user_text:
        \"\"\"{user_text}\"\"\"

        table_csv (optional):
        \"\"\"{table_block}\"\"\"

        user_selected_mode (may be 'auto'):
        {selected_mode}

        ------------------------------------------------------------
        OUTPUT FORMAT (STRICT JSON)
        ------------------------------------------------------------

        {{
          "summary": "1-paragraph natural-language interpretation",
          "journal_type": "week | stress | dream | attendance | stats",
          "emotion_keywords": ["calm", "stress", "joy", "tired"],
          "color_keywords": ["sage green", "deep blue", "blush pink"],
          "imagery": ["waves", "clouds", "floating circles"],       
          "energy_score": 0-5,
          "story_intensity": 0-5,
          "symbol_hints": ["leaves", "stars", "dots", "spirals"]
        }}

        * The JSON MUST be valid.
        * DO NOT add ANY text before or after the JSON.
        * DO NOT wrap with backticks.
    """).strip()


# -----------------------------------------------------------
# INTERNAL HELPER: strip accidental ```json fences
# -----------------------------------------------------------
def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        parts = t.split("```")
        if len(parts) >= 2:
            return parts[1].strip()
    return t


# -----------------------------------------------------------
# GEMINI CALL (SUMMARY ONLY)
# -----------------------------------------------------------
def call_gemini(user_text: str, table_csv: str, selected_mode: str):
    """
    Calls Gemini 2.5 Flash to extract:
      - summary
      - emotion / color / imagery cues
      - story type hint
    """

    if not API_KEY:
        raise RuntimeError("Missing GEMINI_API_KEY")

    prompt = build_prompt(
        user_text=user_text,
        table_csv=table_csv,
        selected_mode=selected_mode,
    )

    # Gemini model that works reliably
    model = gen.GenerativeModel("gemini-2.5-flash")

    response = model.generate_content(prompt)
    raw = (response.text or "").strip()
    raw = _strip_fences(raw)

    # Extract first {...} block
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1:
        raw = raw[start: end+1]

    try:
        data = json.loads(raw)
    except Exception as e:
        raise ValueError(f"Gemini returned invalid JSON: {e}\nRaw: {raw}")

    required_fields = [
        "summary",
        "journal_type",
        "emotion_keywords",
        "color_keywords",
        "imagery",
        "energy_score",
        "story_intensity",
        "symbol_hints",
    ]

    for f in required_fields:
        if f not in data:
            raise ValueError(f"Missing field '{f}' in Gemini output")

    return data
