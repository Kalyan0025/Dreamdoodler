import json
from pathlib import Path
from textwrap import dedent

import google.generativeai as gen

IDENTITY_TEXT = Path("identity.txt").read_text(encoding="utf-8")


def build_prompt(
    mode: str,
    user_text: str,
    input_style: str,
    table_summary: str | None,
    visual_standard_hint: str | None,
) -> str:
    """
    Build the full prompt for Gemini, including:
    - mode:    'week', 'stress', 'dream', 'attendance', 'stats'
    - input_style: 'story' or 'table_time_series'
    - visual_standard_hint: 'A'..'E' as our 5 canonical styles
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
    mode: str,
    user_text: str,
    input_style: str,
    table_summary: str | None,
    visual_standard_hint: str | None,
) -> dict:
    """
    Call Gemini and expect a JSON object:
    { "summary": "...", "schema": {...}, "paperscript": "..." }
    """

    prompt = build_prompt(mode, user_text, input_style, table_summary, visual_standard_hint)

    model = gen.GenerativeModel("gemini-1.5-pro")
    response = model.generate_content(
        prompt,
        generation_config={"temperature": 0.7},
    )

    raw_text = response.text.strip()

    # Some models wrap JSON in ```json ... ```
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        raw_text = raw_text.replace("json", "", 1).strip()

    data = json.loads(raw_text)  # may raise; handled by caller
    return data


# ---------- Fallback demo (no AI needed) ----------

def build_fallback_result(
    mode: str,
    user_text: str,
    input_style: str,
    visual_standard_hint: str | None,
) -> dict:
    """
    Very simple, deterministic fallback.
    Uses a neutral orbit-style visual so that something always renders,
    but the AI styles (A–E) are expected for real runs.
    """

    summary = (
        "Fallback visual only: a calm central orb with three orbiting memories. "
        "This is used when Gemini is not available or fails."
    )

    schema = {
        "mode": mode,
        "inputStyle": input_style,
        "visualStandard": visual_standard_hint or "A",
        "topic": "fallback",
        "moodWord": "mixed",
        "moodIntensity": 5,
        "colorHex": "#F6C589",
        "notes": (user_text or "")[:200],
    }

    paperscript = dedent(
        """
        // Fallback PaperScript demo: central breathing orb with orbiting dots

        var center = view.center;
        var baseRadius = Math.min(view.size.width, view.size.height) * 0.18;

        // Background gradient
        var rect = new Path.Rectangle(view.bounds);
        var topColor = new Color(0.02, 0.03, 0.07);
        var bottomColor = new Color(0.15, 0.15, 0.25);
        rect.fillColor = {
            gradient: {
                stops: [topColor, bottomColor]
            },
            origin: view.bounds.topCenter,
            destination: view.bounds.bottomCenter
        };

        // Central mood orb
        var moodCircle = new Path.Circle({
            center: center,
            radius: baseRadius,
            fillColor: new Color(0.97, 0.80, 0.55, 0.9),
            strokeColor: new Color(1, 1, 1, 0.6),
            strokeWidth: 3
        });

        // Soft halo
        var halo = new Path.Circle({
            center: center,
            radius: baseRadius * 1.5,
            fillColor: new Color(1, 0.9, 0.7, 0.08),
            strokeColor: null
        });

        // Orbits
        var orbits = [];
        var orbitCount = 3;
        for (var i = 0; i < orbitCount; i++) {
            var r = baseRadius * (1.6 + i * 0.35);
            var orbit = new Path.Circle({
                center: center,
                radius: r,
                strokeColor: new Color(1, 1, 1, 0.08),
                strokeWidth: 1
            });
            orbits.push(orbit);
        }

        // Orbiting dots
        var dots = [];
        function makeDot(radius, angleOffset) {
            return {
                radius: radius,
                angle: angleOffset,
                path: new Path.Circle({
                    center: new Point(center.x + radius, center.y),
                    radius: 8,
                    fillColor: new Color(1, 0.96, 0.85, 0.95),
                    strokeColor: new Color(0.3, 0.3, 0.4, 0.6),
                    strokeWidth: 1
                })
            };
        }

        dots.push(makeDot(orbits[0].bounds.width / 2, 0));
        dots.push(makeDot(orbits[1].bounds.width / 2, 120));
        dots.push(makeDot(orbits[2].bounds.width / 2, 240));

        // Title text
        var title = new PointText({
            point: center + new Point(0, -baseRadius - 40),
            justification: 'center',
            content: 'Fallback orbit view',
            fillColor: new Color(1, 1, 1, 0.85),
            fontFamily: 'Helvetica Neue, Arial, sans-serif',
            fontSize: 20
        });

        // Subtitle
        var subtitle = new PointText({
            point: center + new Point(0, baseRadius + 60),
            justification: 'center',
            content: 'Used when AI illustration is unavailable',
            fillColor: new Color(1, 1, 1, 0.6),
            fontFamily: 'Helvetica Neue, Arial, sans-serif',
            fontSize: 14
        });

        // Animation
        function onFrame(event) {
            var t = event.time;

            // Breathing motion
            var scaleFactor = 1 + 0.04 * Math.sin(t * 1.3);
            moodCircle.scale(scaleFactor, center);
            halo.scale(1 + 0.06 * Math.sin(t * 1.1), center);

            // Orbit rotation
            var speeds = [0.6, 0.4, 0.25];
            for (var i = 0; i < dots.length; i++) {
                var d = dots[i];
                d.angle += speeds[i] * 0.5;
                var rad = d.radius;
                var angleRad = d.angle * Math.PI / 180;
                var x = center.x + rad * Math.cos(angleRad);
                var y = center.y + rad * Math.sin(angleRad);
                d.path.position = new Point(x, y);
            }
        }

        function onResize(event) {
            rect.bounds = view.bounds;
            rect.fillColor.origin = view.bounds.topCenter;
            rect.fillColor.destination = view.bounds.bottomCenter;
            center = view.center;
        }
        """
    )

    return {
        "summary": summary,
        "schema": schema,
        "paperscript": paperscript,
    }
