import json
import os
import re
from pathlib import Path
from textwrap import dedent

import google.generativeai as gen

# Load identity instructions
IDENTITY_TEXT = Path("identity.txt").read_text(encoding="utf-8")

# Configure Gemini API key
API_KEY = os.getenv("GEMINI_API_KEY")
if API_KEY:
    gen.configure(api_key=API_KEY)


def build_prompt(mode, user_text, input_style, table_summary, visual_standard_hint):
    """
    EXACT workflow you already use — only cleaned.
    """
    table_block = table_summary.strip() if table_summary else "[none]"

    return dedent(f"""
    {IDENTITY_TEXT}

    mode: {mode}
    inputStyle: {input_style}
    visualStandardHint: {visual_standard_hint or "A"}

    userText: \"\"\"{user_text}\"\"\"

    tableSummary: \"\"\"{table_block}\"\"\"

    Respond ONLY with a single JSON object.
    No backticks.
    No extra text.
    """)


def _strip_fences(text: str) -> str:
    """Strip ```json fences Gemini sometimes adds."""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()


def call_gemini(mode, user_text, input_style, table_summary, visual_standard_hint):
    if not API_KEY:
        raise RuntimeError("No GEMINI_API_KEY set.")

    prompt = build_prompt(
        mode, user_text, input_style, table_summary, visual_standard_hint
    )

    model = gen.GenerativeModel("gemini-1.5-pro")

    response = model.generate_content(
        prompt,
        generation_config={"temperature": 0.6},
    )

    raw = (response.text or "").strip()
    raw = _strip_fences(raw)

    # Extract {...} in case noise appears
    if not raw.startswith("{"):
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1:
            raw = raw[start: end + 1]

    data = json.loads(raw)

    if "summary" not in data or "schema" not in data or "paperscript" not in data:
        raise ValueError("JSON missing required keys.")

    return data


# ------------ FALLBACK VISUAL ------------
DEMO_PAPERSCRIPT = """
var bg = new Path.Rectangle(view.bounds);
bg.fillColor = '#0c0f1a';

var center = view.center;
var bubbles = [];

for (var i = 0; i < 35; i++) {
    var p = new Point(
        view.bounds.left + Math.random()*view.bounds.width,
        view.bounds.top + Math.random()*view.bounds.height
    );
    var c = new Path.Circle(p, 10 + Math.random()*20);
    c.fillColor = new Color(Math.random(), Math.random()*0.3, Math.random()*0.2, 0.7);
    c.data.vx = (Math.random()-0.5)*0.5;
    c.data.vy = (Math.random()-0.5)*0.5;
    bubbles.push(c);
}

function onFrame(event){
    for (var i=0; i<bubbles.length; i++){
        var c = bubbles[i];
        c.position.x += c.data.vx;
        c.position.y += c.data.vy;

        if(c.position.x < -40) c.position.x = view.bounds.right + 40;
        if(c.position.x > view.bounds.right + 40) c.position.x = -40;
        if(c.position.y < -40) c.position.y = view.bounds.bottom + 40;
        if(c.position.y > view.bounds.bottom + 40) c.position.y = -40;

        var s = 1 + Math.sin(event.time*2 + i) * 0.002;
        c.scale(s);
    }
}
"""


def build_fallback_result(mode, user_text, input_style, visual_standard_hint):
    """Fallback so you ALWAYS see something."""
    return {
        "summary": "Fallback visual—soft drifting bubbles.",
        "schema": {
            "mode": mode,
            "inputStyle": input_style,
            "visualStandard": visual_standard_hint,
            "topic": "fallback",
            "moodWord": "calm",
            "moodIntensity": 4,
            "colorHex": "#7ba2ff",
            "notes": user_text[:200],
        },
        "paperscript": DEMO_PAPERSCRIPT,
    }
