import json
import os
from pathlib import Path
from textwrap import dedent

import google.generativeai as gen

# ---------- CONFIG / IDENTITY ----------

IDENTITY_TEXT = Path("identity.txt").read_text(encoding="utf-8")

API_KEY = os.getenv("GEMINI_API_KEY")
if API_KEY:
    gen.configure(api_key=API_KEY)


def has_gemini_key() -> bool:
    """Return True if a Gemini API key is configured."""
    return bool(API_KEY)


# ---------- PROMPT BUILDING ----------

def build_prompt(mode, user_text, input_style, table_summary, visual_standard_hint):
    """
    Build the instruction for Gemini.
    We keep it simple: ask for summary + schema, no PaperScript is required.
    """
    table_block = table_summary.strip() if table_summary else "[none]"

    return dedent(
        f"""
        {IDENTITY_TEXT}

        -------------------------
        CURRENT REQUEST
        -------------------------

        mode: {mode}
        inputStyle: {input_style}
        visualStandardHint: {visual_standard_hint}

        userText: \"\"\"{user_text}\"\"\"

        tableSummary: \"\"\"{table_block}\"\"\"

        You are a data humanism assistant inspired by Dear Data.
        Respond with ONLY a single JSON object.

        REQUIRED FORMAT:
        {{
          "summary": "one-paragraph natural language summary of this data",
          "schema": {{
             "mode": "{mode}",
             "visualStandard": "{visual_standard_hint}",
             "dimensions": {{
                "days": [
                  {{
                    "name": "Mon",
                    "connection_score": 0.0,
                    "events": [
                      {{
                        "type": "family|friends|focus|alone|rush",
                        "time_slot": "morning|afternoon|evening",
                        "size": 8-24,
                        "intensity": 1-5
                      }}
                    ]
                  }}
                ]
             }}
          }},
          "paperscript": ""
        }}

        DO NOT wrap the JSON in backticks.
        DO NOT add any text before or after the JSON.
        """
    ).strip()


def _strip_fences(text: str) -> str:
    """
    Remove ```json fences if the model adds them anyway.
    """
    t = text.strip()
    if t.startswith("```"):
        # crude but safe
        parts = t.split("```")
        if len(parts) >= 2:
            t = parts[1].strip()
    return t


# ---------- GEMINI CALL ----------

def call_gemini(mode, user_text, input_style, table_summary, visual_standard_hint):
    """
    Call Gemini and parse the JSON response.
    Raises on error so the caller can fall back.
    """
    if not API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set")

    prompt = build_prompt(mode, user_text, input_style, table_summary, visual_standard_hint)

    # IMPORTANT: this is the model that worked in your gemini_test.py
    model = gen.GenerativeModel("gemini-2.5-flash")

    response = model.generate_content(prompt)
    raw = (response.text or "").strip()
    raw = _strip_fences(raw)

    # Try to isolate the first {...} block
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        raw = raw[start : end + 1]

    data = json.loads(raw)

    if "summary" not in data or "schema" not in data:
        raise ValueError("Model JSON missing 'summary' or 'schema'")

    # paperscript is optional; backend may override with Dear Data renderer
    if "paperscript" not in data:
        data["paperscript"] = ""

    return data


# ---------- FALLBACK (USED WHEN GEMINI FAILS) ----------

def _default_week_dimensions():
    """
    A simple, hand-coded Dear Data style week – used if Gemini fails.
    """
    return {
        "days": [
            {
                "name": "Mon",
                "connection_score": 0.1,
                "events": [
                    {"type": "rush", "time_slot": "morning", "size": 12, "intensity": 3},
                    {"type": "focus", "time_slot": "afternoon", "size": 10, "intensity": 1},
                ],
            },
            {
                "name": "Tue",
                "connection_score": 0.5,
                "events": [
                    {"type": "family", "time_slot": "evening", "size": 18, "intensity": 3},
                ],
            },
            {
                "name": "Wed",
                "connection_score": 0.7,
                "events": [
                    {"type": "focus", "time_slot": "afternoon", "size": 18, "intensity": 4},
                    {"type": "friends", "time_slot": "afternoon", "size": 14, "intensity": 2},
                ],
            },
            {
                "name": "Thu",
                "connection_score": 0.6,
                "events": [
                    {"type": "friends", "time_slot": "afternoon", "size": 14, "intensity": 2},
                ],
            },
            {
                "name": "Fri",
                "connection_score": 0.9,
                "events": [
                    {"type": "focus", "time_slot": "afternoon", "size": 14, "intensity": 2},
                    {"type": "friends", "time_slot": "evening", "size": 18, "intensity": 3},
                ],
            },
            {
                "name": "Sat",
                "connection_score": 0.2,
                "events": [
                    {"type": "focus", "time_slot": "afternoon", "size": 20, "intensity": 4},
                    {"type": "alone", "time_slot": "evening", "size": 14, "intensity": 3},
                ],
            },
            {
                "name": "Sun",
                "connection_score": 0.8,
                "events": [
                    {"type": "friends", "time_slot": "afternoon", "size": 18, "intensity": 3},
                    {"type": "alone", "time_slot": "evening", "size": 16, "intensity": 2},
                ],
            },
        ]
    }


def build_fallback_result(mode, user_text, input_style, visual_standard_hint):
    """
    Used when Gemini call fails or no key is present.
    Always returns a valid summary + schema + (empty) paperscript.
    """
    if mode == "week":
        dimensions = _default_week_dimensions()
    else:
        dimensions = {
            "note": (user_text or "")[:200]
        }

    schema = {
        "mode": mode,
        "inputStyle": input_style,
        "visualStandard": visual_standard_hint,
        "dimensions": dimensions,
        "moodWord": "curious",
        "moodIntensity": 5,
        "colorHex": "#f6c589",
        "notes": (user_text or "")[:220],
    }

    return {
        "summary": "Fallback Dear-Data schema (Gemini failed or no key).",
        "schema": schema,
        "paperscript": "",
    }
