import json
import os
from pathlib import Path
from textwrap import dedent

import google.generativeai as gen

# Load identity
IDENTITY_TEXT = Path("identity.txt").read_text(encoding="utf-8")

# Configure key
API_KEY = os.getenv("GEMINI_API_KEY")
if API_KEY:
    gen.configure(api_key=API_KEY)


def has_gemini_key() -> bool:
    return bool(API_KEY)


def build_prompt(mode, user_text, input_style, table_summary, visual_standard_hint):
    table_block = table_summary.strip() if table_summary else "[none]"

    return dedent(f"""
    {IDENTITY_TEXT}

    mode: {mode}
    inputStyle: {input_style}
    visualStandardHint: {visual_standard_hint}

    userText: \"\"\"{user_text}\"\"\"

    tableSummary: \"\"\"{table_block}\"\"\"

    REQUIRED JSON FORMAT:
    {{
      "summary": "...",
      "schema": {{
          "mode": "...",
          "visualStandard": "...",
          "dimensions": {{
              "days": [
                  {{
                    "name": "Mon",
                    "connection_score": 0.1,
                    "events": [
                       {{
                         "type": "friends|family|focus|alone|rush",
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

    ONLY return a JSON object. No backticks.
    """).strip()


def _strip_fences(text: str) -> str:
    """Remove ```json fences."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```")[1].strip()
    return t


def call_gemini(mode, user_text, input_style, table_summary, visual_standard_hint):
    if not API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set")

    prompt = build_prompt(mode, user_text, input_style, table_summary, visual_standard_hint)

        model = gen.GenerativeModel("gemini-pro")

    response = model.generate_content(prompt)
    raw = response.text or ""
    raw = _strip_fences(raw)

    # Isolate { ... }
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1:
        raw = raw[start:end+1]

    data = json.loads(raw)

    # Guarantee keys exist
    if "schema" not in data:
        raise ValueError("schema missing from model output")

    if "paperscript" not in data:
        data["paperscript"] = ""

    return data


# ------------------ FALLBACK ------------------

def build_fallback_result(mode, user_text, input_style, visual_standard_hint):
    """A simple fallback schema that always renders."""
    schema = {
        "mode": mode,
        "inputStyle": input_style,
        "visualStandard": visual_standard_hint,
        "dimensions": {
            "days": [
                {
                    "name": "Mon",
                    "connection_score": 0.1,
                    "events": [
                        {"type": "rush", "time_slot": "morning", "size": 12, "intensity": 3},
                        {"type": "focus", "time_slot": "afternoon", "size": 10, "intensity": 1}
                    ]
                },
                {
                    "name": "Tue",
                    "connection_score": 0.5,
                    "events": [
                        {"type": "family", "time_slot": "evening", "size": 18, "intensity": 3}
                    ]
                },
                {
                    "name": "Wed",
                    "connection_score": 0.7,
                    "events": [
                        {"type": "focus", "time_slot": "afternoon", "size": 18, "intensity": 4},
                        {"type": "friends", "time_slot": "afternoon", "size": 14, "intensity": 2}
                    ]
                }
            ]
        }
    }

    return {
        "summary": "Fallback Dear-Data schema (Gemini failed).",
        "schema": schema,
        "paperscript": ""
    }
