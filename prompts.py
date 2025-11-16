import json
from pathlib import Path
from textwrap import dedent

import google.generativeai as gen

# Load the system / identity instructions
IDENTITY_TEXT = Path("identity.txt").read_text(encoding="utf-8")


def build_prompt(
    mode,
    user_text,
    input_style,
    table_summary,
    visual_standard_hint,
):
    """
    Build the full prompt for Gemini.

    mode: 'week', 'stress', 'dream', 'attendance', 'stats'
    input_style: 'story' or 'table_time_series'
    visual_standard_hint: 'A'..'E'
    """

    header = dedent(
        f"""
        {IDENTITY_TEXT}

        mode: {mode}
        inputStyle: {input_style}
        visualStandardHint: {visual_standard_hint or "A"}
        """
    )

    if input_style == "story":
        body = dedent(
            f"""
            The user has provided a natural language description or journal-like entry.

            User text:
            \"\"\"{user_text}\"\"\"
            """
        )
    else:
        body = dedent(
            f"""
            The user has provided a tabular dataset (e.g., from a spreadsheet) plus a short description.

            User description of the dataset:
            \"\"\"{user_text}\"\"\"

            Tabular dataset summary (in CSV-like text). Use this as your data; do NOT invent extra rows:
            {table_summary or "[no table summary available]"}
            """
        )

    return header + "\n" + body


def call_gemini(
    mode,
    user_text,
    input_style,
    table_summary,
    visual_standard_hint,
):
    """
    Call Gemini and expect a JSON object:

    {
      "summary": "...",
      "schema": {...},
      "paperscript": "..."
    }
    """

    prompt = build_prompt(
        mode,
        user_text,
        input_style,
        table_summary,
        visual_standard_hint,
    )

    # IMPORTANT: use a model that actually exists
    # for the public Gemini API.
    model = gen.GenerativeModel("gemini-1.5-pro")

    response = model.generate_content(
        prompt,
        generation_config={"temperature": 0.7},
    )

    raw_text = (response.text or "").strip()

    # Some models wrap JSON in ```json ... ```
    if raw_text.startswith("```"):
        # strip leading and trailing fences
        raw_text = raw_text.strip("`")
        # sometimes starts with "json"
        if raw_text.lower().startswith("json"):
            raw_text = raw_text[4:].lstrip()

    # If there is extra chatter, grab the first {...} block
    if not raw_text.strip().startswith("{"):
        first = raw_text.find("{")
        last = raw_text.rfind("}")
        if first != -1 and last != -1 and last > first:
            raw_text = raw_text[first : last + 1]

    data = json.loads(raw_text)

    # basic sanity check
    if "summary" not in data or "schema" not in data or "paperscript" not in data:
        raise ValueError(
            "Model JSON missing one of: 'summary', 'schema', 'paperscript'. "
            f"Got keys: {list(data.keys())}"
        )

    return data


def build_fallback_result(
    mode,
    user_text,
    input_style,
    visual_standard_hint,
):
    """
    Very simple, deterministic fallback visual.

    Used whenever:
    - No API key is configured,
    - User forces demo mode,
    - Gemini call or JSON parsing fails.
    """

    summary = (
        "Fallback visual: drifting circles that stand in for your week, dream, or stats."
    )

    schema = {
        "mode": mode,
        "inputStyle": input_style,
        "visualStandard": visual_standard_hint or "A",
        "topic": "fallback",
        "moodWord": "mixed",
        "moodIntensity": 5,
        "colorHex": "#F6C589",
        "notes": (user_text or "")[:220],
    }

    # Keep this simple + safe so it never breaks Paper.js
    paperscript = dedent(
        """
        // Fallback PaperScript demo: drifting colored circles

        var center = view.center;
        var size = view.size;

        var circles = [];
        var count = 40;

        function randomColor() {
            var colors = [
                '#f2d0a7',
                '#f28f79',
                '#c8553d',
                '#6b2737',
                '#0b3954'
            ];
            return colors[Math.floor(Math.random() * colors.length)];
        }

        // Background
        var bg = new Path.Rectangle(view.bounds);
        bg.fillColor = new Color(0.03, 0.04, 0.08, 1);

        for (var i = 0; i < count; i++) {
            var pos = new Point(
                view.bounds.left + Math.random() * view.bounds.width,
                view.bounds.top + Math.random() * view.bounds.height
            );
            var r = 10 + Math.random() * 25;
            var c = new Path.Circle(pos, r);
            c.fillColor = randomColor();
            c.opacity = 0.8;
            c.data.drift = new Point(
                (Math.random() - 0.5) * 0.6,
                (Math.random() - 0.5) * 0.6
            );
            circles.push(c);
        }

        function onFrame(event) {
            for (var i = 0; i < circles.length; i++) {
                var c = circles[i];
                c.position += c.data.drift;

                // wrap around
                if (c.position.x < view.bounds.left - 50) c.position.x = view.bounds.right + 50;
                if (c.position.x > view.bounds.right + 50) c.position.x = view.bounds.left - 50;
                if (c.position.y < view.bounds.top - 50) c.position.y = view.bounds.bottom + 50;
                if (c.position.y > view.bounds.bottom + 50) c.position.y = view.bounds.top - 50;

                // subtle breathing
                var s = 1 + Math.sin(event.time * 1.5 + i) * 0.002;
                c.scale(s);
            }
        }
        """
    )

    return {
        "summary": summary,
        "schema": schema,
        "paperscript": paperscript,
    }
