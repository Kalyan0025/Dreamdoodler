import json
import os
from pathlib import Path
from textwrap import dedent

import google.generativeai as gen

IDENTITY_TEXT = Path("identity.txt").read_text(encoding="utf-8")

API_KEY = os.getenv("GEMINI_API_KEY")
if API_KEY:
    gen.configure(api_key=API_KEY)


def has_gemini_key() -> bool:
    return bool(API_KEY)


def _base_header(mode, input_style, visual_standard_hint, user_text, table_summary) -> str:
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
        Respond with ONLY a single JSON object, no explanations.
        """
    ).strip()


def build_prompt(mode, user_text, input_style, table_summary, visual_standard_hint):
    header = _base_header(
        mode=mode,
        input_style=input_style,
        visual_standard_hint=visual_standard_hint,
        user_text=user_text,
        table_summary=table_summary,
    )

    if mode == "week":
        schema_template = f"""
        REQUIRED FORMAT:
        {{
          "summary": "one-paragraph natural language summary of the week (feelings, energy, connection)",
          "schema": {{
            "mode": "week",
            "visualStandard": "{visual_standard_hint}",
            "dimensions": {{
              "days": [
                {{
                  "name": "Mon|Tue|Wed|Thu|Fri|Sat|Sun",
                  "mood": 1-5,
                  "energy": 1-5,
                  "connection_score": 0.0-1.0,
                  "label": "short 3–6 word note (e.g. 'calm call with parents')"
                }}
              ]
            }}
          }},
          "paperscript": ""
        }}

        RULES:
        - Always output EXACTLY 7 items in dimensions.days in order Mon..Sun.
        - mood and energy must be integers 1–5.
        - connection_score is 0.0–1.0.
        - label should be human, short diary-like.
        - ALWAYS return strictly valid JSON.
        """

    elif mode == "stress":
        schema_template = f"""
        REQUIRED FORMAT:
        {{
          "summary": "one-paragraph overview of how stress rose and fell over time",
          "schema": {{
            "mode": "stress",
            "visualStandard": "{visual_standard_hint}",
            "dimensions": {{
              "timeline": [
                {{
                  "label": "short name like 'presentation' or 'commute'",
                  "position": 0.0-1.0,
                  "stress": 1-10,
                  "emotion": "one word emotion like anxious, tense, relieved",
                  "body_note": "optional physical note like 'tight chest'"
                }}
              ]
            }}
          }},
          "paperscript": ""
        }}

        RULES:
        - Use between 4 and 12 timeline points.
        - Keep position in ascending order.
        - Use stress to reflect intensity in the text.
        - ALWAYS return strictly valid JSON.
        """

    elif mode == "stress_single":
        schema_template = f"""
        REQUIRED FORMAT:
        {{
          "summary": "one sentence describing the current emotional state",
          "schema": {{
            "mode": "stress_single",
            "visualStandard": "{visual_standard_hint}",
            "dimensions": {{
              "mood": {{
                "label": "one or two words like 'sad', 'anxious', 'calm'",
                "intensity": 1-10,
                "energy": 1-5,
                "body_note": "optional physical note like 'heavy chest'"
              }}
            }}
          }},
          "paperscript": ""
        }}

        RULES:
        - Base intensity on how strong the emotion feels in the text.
        - If there is no physical description, body_note can be empty.
        - ALWAYS return strictly valid JSON.
        """

    elif mode == "dream":
        schema_template = f"""
        REQUIRED FORMAT:
        {{
          "summary": "one short paragraph summarising the dream journey and emotions",
          "schema": {{
            "mode": "dream",
            "visualStandard": "{visual_standard_hint}",
            "dimensions": {{
              "scenes": [
                {{
                  "id": 1,
                  "label": "short human name like 'Red island', 'Blue planet of peace'",
                  "emotion": "excited|afraid|peaceful|hopeful|confused|sad|joyful",
                  "intensity": 1-10,
                  "colorHint": "#rrggbb",
                  "orbit": 1-4,
                  "hasGuide": true or false
                }}
              ]
            }}
          }},
          "paperscript": ""
        }}

        RULES:
        - Use between 3 and 7 scenes.
        - Preserve the ORDER of the dream from start to end.
        - intensity reflects how strong the feeling was in each part.
        - If a guide/recurring figure is present in a scene, set hasGuide=true.
        - ALWAYS return strictly valid JSON.
        """

    else:
        # attendance / stats or any other mode – simple generic note
        schema_template = f"""
        REQUIRED FORMAT:
        {{
          "summary": "one-paragraph overview of the key patterns in the text",
          "schema": {{
            "mode": "{mode}",
            "visualStandard": "{visual_standard_hint}",
            "dimensions": {{
              "note": "short distilled description of the main structure in the data"
            }}
          }},
          "paperscript": ""
        }}

        RULES:
        - Keep it compact and human.
        - ALWAYS return strictly valid JSON.
        """

    return "\n\n".join([header, schema_template]).strip()


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        parts = t.split("```")
        if len(parts) >= 2:
            t = parts[1].strip()
    return t


def call_gemini(mode, user_text, input_style, table_summary, visual_standard_hint):
    if not API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set")

    prompt = build_prompt(mode, user_text, input_style, table_summary, visual_standard_hint)

    model = gen.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt)
    raw = (response.text or "").strip()
    raw = _strip_fences(raw)

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        raw = raw[start : end + 1]

    data = json.loads(raw)

    if "summary" not in data or "schema" not in data:
        raise ValueError("Model JSON missing 'summary' or 'schema'")

    if "paperscript" not in data:
        data["paperscript"] = ""

    return data


def _default_week_dimensions():
    return {
        "days": [
            {
                "name": "Mon",
                "mood": 2,
                "energy": 2,
                "connection_score": 0.2,
                "label": "rushed day",
            },
            {
                "name": "Tue",
                "mood": 4,
                "energy": 3,
                "connection_score": 0.7,
                "label": "calm call with parents",
            },
            {
                "name": "Wed",
                "mood": 2,
                "energy": 3,
                "connection_score": 0.3,
                "label": "anxious presentation",
            },
            {
                "name": "Thu",
                "mood": 3,
                "energy": 3,
                "connection_score": 0.4,
                "label": "quiet solo work",
            },
            {
                "name": "Fri",
                "mood": 4,
                "energy": 4,
                "connection_score": 0.8,
                "label": "good group project",
            },
            {
                "name": "Sat",
                "mood": 4,
                "energy": 4,
                "connection_score": 0.5,
                "label": "deep work + walk",
            },
            {
                "name": "Sun",
                "mood": 5,
                "energy": 3,
                "connection_score": 0.9,
                "label": "brunch + journaling",
            },
        ]
    }


def _default_dream_scenes():
    return {
        "scenes": [
            {
                "id": 1,
                "label": "Cold void with a guide",
                "emotion": "calm",
                "intensity": 2,
                "colorHint": "#727b9a",
                "orbit": 1,
                "hasGuide": True,
            },
            {
                "id": 2,
                "label": "Glowing red island",
                "emotion": "excited",
                "intensity": 9,
                "colorHint": "#e35b4f",
                "orbit": 3,
                "hasGuide": True,
            },
            {
                "id": 3,
                "label": "Blue planet of peace",
                "emotion": "peaceful",
                "intensity": 7,
                "colorHint": "#4a7fd0",
                "orbit": 4,
                "hasGuide": True,
            },
            {
                "id": 4,
                "label": "Descent back with hope",
                "emotion": "hopeful",
                "intensity": 6,
                "colorHint": "#f3c16b",
                "orbit": 2,
                "hasGuide": True,
            },
        ]
    }


def _default_single_mood(user_text: str):
    txt = (user_text or "").lower()
    if "sad" in txt:
        label = "sad"
        intensity = 7
    elif "anxious" in txt or "anxiety" in txt:
        label = "anxious"
        intensity = 8
    elif "happy" in txt or "joy" in txt:
        label = "happy"
        intensity = 7
    else:
        label = "mixed"
        intensity = 5

    return {
        "mood": {
            "label": label,
            "intensity": intensity,
            "energy": 2,
            "body_note": "",
        }
    }


def build_fallback_result(mode, user_text, input_style, visual_standard_hint):
    if mode == "week":
        dimensions = _default_week_dimensions()
        summary = "Fallback Dear-Data week schema (Gemini failed or no key)."
    elif mode == "dream":
        dimensions = _default_dream_scenes()
        summary = "Fallback dream journey schema (Gemini failed or no key)."
    elif mode == "stress_single":
        dimensions = _default_single_mood(user_text or "")
        summary = "Fallback single-mood schema (Gemini failed or no key)."
    else:
        dimensions = {"note": (user_text or "")[:200]}
        summary = "Fallback generic schema (Gemini failed or no key)."

    schema = {
        "mode": mode,
        "inputStyle": input_style,
        "visualStandard": visual_standard_hint,
        "dimensions": dimensions,
        "notes": (user_text or "")[:220],
    }

    return {
        "summary": summary,
        "schema": schema,
        "paperscript": "",
    }
