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


def build_prompt(mode, user_text, input_style, table_summary, visual_standard_hint):
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

        The user has provided:
        userText: \"\"\"{user_text}\"\"\"

        tableSummary: \"\"\"{table_block}\"\"\"

        For mode="week" you MUST populate schema.dimensions.days as:
          "dimensions": {{
            "days": [
              {{
                "name": "Mon",
                "connection_score": 0.0-1.0,
                "events": [
                  {{
                    "type": "family|friends|focus|alone|rush",
                    "time_slot": "morning|afternoon|evening",
                    "size": 8-24,
                    "intensity": 1-5
                  }}
                ]
              }},
              ...
            ]
          }}

        Respond with ONLY a single JSON object:
          {{
            "summary": "...",
            "schema": {{ ... }},
            "paperscript": "..."      // optional, backend may ignore
          }}

        Do NOT wrap the JSON in backticks.
        """
    )


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines)
    return t.strip()


def call_gemini(mode, user_text, input_style, table_summary, visual_standard_hint):
    if not API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set")

    prompt = build_prompt(mode, user_text, input_style, table_summary, visual_standard_hint)
    model = gen.GenerativeModel("gemini-1.5-pro")

    response = model.generate_content(prompt, generation_config={"temperature": 0.6})
    raw = (response.text or "").strip()
    raw = _strip_fences(raw)

    # try to isolate the first {...}
    if not raw.lstrip().startswith("{"):
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            raw = raw[start : end + 1]

    data = json.loads(raw)

    if "summary" not in data or "schema" not in data:
        raise ValueError("Model JSON missing 'summary' or 'schema' keys")

    # paperscript is optional now
    if "paperscript" not in data:
        data["paperscript"] = ""

    return data


# ---------- Fallback visuals ----------

DEMO_BUBBLES_PAPERSCRIPT = """\
var center = view.center;
var rect = new Path.Rectangle(view.bounds);
rect.fillColor = new Color(0.04, 0.05, 0.09, 1);

var bubbles = [];
for (var i = 0; i < 30; i++) {
    var p = new Point(
        view.bounds.left + Math.random()*view.bounds.width,
        view.bounds.top + Math.random()*view.bounds.height
    );
    var r = 10 + Math.random()*20;
    var c = new Path.Circle(p, r);
    c.fillColor = new Color(Math.random()*0.6, Math.random()*0.4, Math.random(), 0.8);
    c.data.dx = (Math.random()-0.5)*0.4;
    c.data.dy = (Math.random()-0.5)*0.4;
    bubbles.push(c);
}

function onFrame(event){
    for (var i = 0; i < bubbles.length; i++){
        var b = bubbles[i];
        b.position.x += b.data.dx;
        b.position.y += b.data.dy;
        if (b.position.x < view.bounds.left-40) b.position.x = view.bounds.right+40;
        if (b.position.x > view.bounds.right+40) b.position.x = view.bounds.left-40;
        if (b.position.y < view.bounds.top-40) b.position.y = view.bounds.bottom+40;
        if (b.position.y > view.bounds.bottom+40) b.position.y = view.bounds.top-40;
    }
}
"""


def _default_week_dimensions():
    # A hand-coded example week; used whenever Gemini fails.
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
    Fallback when Gemini is unavailable or fails.
    Always returns a schema + some PaperScript.
    """
    summary = "Fallback visual: an abstract view of your data."

    if mode == "week":
        dimensions = _default_week_dimensions()
    else:
        dimensions = {"note": (user_text or "")[:200]}

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
        "summary": summary,
        "schema": schema,
        "paperscript": DEMO_BUBBLES_PAPERSCRIPT,
    }
