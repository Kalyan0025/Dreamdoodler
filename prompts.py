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
    """
    Build the instruction for Gemini.

    IMPORTANT:
    - Each mode has its own schema (week, stress, dream, attendance, stats).
    - This is what lets the renderer draw something *meaningful*, not generic.
    """

    header = _base_header(
        mode=mode,
        input_style=input_style,
        visual_standard_hint=visual_standard_hint,
        user_text=user_text,
        table_summary=table_summary,
    )

    # ------- MODE: WEEK / ROUTINE --------
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
                  "mood": 1-5,             // 1 = very low, 5 = very high
                  "energy": 1-5,           // 1 = exhausted, 5 = buzzing
                  "connection_score": 0.0-1.0,
                  "label": "short 3–6 word note for the day (e.g. 'calm call with parents')"
                }}
              ]
            }}
          }},
          "paperscript": ""
        }}

        RULES:
        - Always output EXACTLY 7 items in dimensions.days in order Mon..Sun.
        - mood and energy must be integers 1–5.
        - connection_score is 0.0–1.0 (floating point).
        - label should be human and short, like a diary caption.
        - ALWAYS return strictly valid JSON (no comments in the real output).
        """

    # ------- MODE: STRESS / EMOTIONAL WEEK --------
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
                  "label": "short name like 'morning commute' or 'presentation'",
                  "position": 0.0-1.0,      // 0 = start of the week, 1 = end
                  "stress": 1-10,           // 1 = very calm, 10 = overwhelming stress
                  "emotion": "one word emotion like anxious, angry, tense, relieved",
                  "body_note": "optional physical note like 'tight chest', 'headache'"
                }}
              ]
            }}
          }},
          "paperscript": ""
        }}

        RULES:
        - Use between 4 and 12 timeline points.
        - Keep position in ascending order.
        - Use stress to reflect intensity described by the user.
        - ALWAYS return strictly valid JSON.
        """

    # ------- MODE: DREAM --------
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
                  "label": "short human name for this scene (e.g. 'Red island', 'Blue planet of peace')",
                  "emotion": "primary emotion like excited, afraid, peaceful, hopeful, confused",
                  "intensity": 1-10,           // 1 = very faint, 10 = overwhelming
                  "colorHint": "#rrggbb",      // hex colour matching the emotion
                  "orbit": 1-4,                // 1 = close to centre, 4 = far out
                  "hasGuide": true or false    // true if a guide / recurring figure is present
                }}
              ]
            }}
          }},
          "paperscript": ""
        }}

        RULES:
        - Use between 3 and 7 scenes.
        - Preserve the ORDER of the dream from beginning to end.
        - intensity must reflect how strong the feeling was in the text.
        - orbit should loosely match the feeling: calmer = inner, big dramatic = outer.
        - If a guide or recurring figure is present in a scene, set hasGuide = true.
        - ALWAYS return strictly valid JSON (no comments in the real output).
        """

    # ------- MODE: ATTENDANCE / PRESENCE --------
    elif mode == "attendance":
        schema_template = f"""
        REQUIRED FORMAT:
        {{
          "summary": "one-paragraph story of presence/absence over the period",
          "schema": {{
            "mode": "attendance",
            "visualStandard": "{visual_standard_hint}",
            "dimensions": {{
              "days": [
                {{
                  "name": "Mon|Tue|Wed|Thu|Fri|Sat|Sun or a date label",
                  "present": true or false,
                  "half_day": true or false,
                  "reason": "optional short note like 'sick', 'travel', 'class', 'office'",
                  "importance": 1-5   // how important it felt to the user
                }}
              ]
            }}
          }},
          "paperscript": ""
        }}

        RULES:
        - Use 5–21 days depending on the text.
        - If the user mentions many weeks, compress into representative days.
        - ALWAYS return strictly valid JSON.
        """

    # ------- MODE: GENERIC TIME / CATEGORY STATS --------
    else:  # mode == "stats" or anything else
        schema_template = f"""
        REQUIRED FORMAT:
        {{
          "summary": "one-paragraph overview of how time or attention is split across categories",
          "schema": {{
            "mode": "stats",
            "visualStandard": "{visual_standard_hint}",
            "dimensions": {{
              "categories": [
                {{
                  "name": "category label like 'work', 'study', 'friends', 'scrolling'",
                  "hours": 0.0-168.0,
                  "emotional_tone": "positive|neutral|negative",
                  "note": "short human description (e.g. 'deep focus', 'doomscrolling')"
                }}
              ]
            }}
          }},
          "paperscript": ""
        }}

        RULES:
        - Use between 3 and 12 categories.
        - hours is any numeric allocation that fits the story (it does not need to sum to a fixed total).
        - ALWAYS return strictly valid JSON.
        """

    # Combine header + mode-specific template
    return "\n\n".join([header, schema_template]).strip()


def _strip_fences(text: str) -> str:
    """
    Remove ```json fences if the model adds them anyway.
    """
    t = text.strip()
    if t.startswith("```"):
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

    # This is the model you already tested successfully.
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


# ---------- FALLBACKS (USED WHEN GEMINI FAILS OR NO KEY) ----------


def _default_week_dimensions():
    """Simple, hand-coded Dear-Data week – used if Gemini fails."""
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
    """Fallback dream scenes if Gemini is unavailable."""
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


def build_fallback_result(mode, user_text, input_style, visual_standard_hint):
    """
    Used when Gemini call fails or no key is present.
    Always returns a valid summary + schema + (empty) paperscript.
    """
    if mode == "week":
        dimensions = _default_week_dimensions()
        summary = "Fallback Dear-Data week schema (Gemini failed or no key)."
    elif mode == "dream":
        dimensions = _default_dream_scenes()
        summary = "Fallback dream journey schema (Gemini failed or no key)."
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
