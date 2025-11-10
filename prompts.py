import json
from pathlib import Path
from textwrap import dedent

import google.generativeai as gen

IDENTITY_TEXT = Path("identity.txt").read_text(encoding="utf-8")


def build_prompt(mode: str, user_text: str, input_style: str, table_summary: str | None) -> str:
    """
    Build the full prompt for Gemini, supporting:
    - narrative / reflection input ("story")
    - tabular / time-series CSV input ("table_time_series")
    """

    header = dedent(
        f"""
        {IDENTITY_TEXT}

        Entry mode (semantic focus): {mode}
        Input_style: {input_style}
        """
    )

    if input_style == "story":
        body = dedent(
            f"""
            The user has provided a natural language journal-style entry.

            User journal entry:
            \"\"\"{user_text}\"\"\"
            """
        )
    else:
        # table / time-series
        body = dedent(
            f"""
            The user has provided a tabular or time-series dataset plus a short description.
            Treat this as temporal life data suitable for calendar-like, grid-based Data Humanism visuals.

            User description of the dataset:
            \"\"\"{user_text}\"\"\"

            Tabular dataset summary (in CSV-like text form). Use this as your data, do NOT fabricate extra columns:
            {table_summary or "[no table summary available]"}
            """
        )

    return header + "\n" + body


def call_gemini(mode: str, user_text: str, input_style: str, table_summary: str | None) -> dict:
    """
    Call Gemini and expect a JSON object with:
    { "summary": "...", "schema": {...}, "paperscript": "..." }
    """

    prompt = build_prompt(mode, user_text, input_style, table_summary)

    model = gen.GenerativeModel("gemini-1.5-pro")  # change model name if needed
    response = model.generate_content(
        prompt,
        generation_config={"temperature": 0.7},
    )

    raw_text = response.text.strip()

    # Try to find JSON in the response safely
    if raw_text.startswith("```"):
        # Remove markdown fences (```json ... ```)
        raw_text = raw_text.strip("`")
        raw_text = raw_text.replace("json", "", 1).strip()

    data = json.loads(raw_text)  # will raise if invalid → handled by caller
    return data


# ---------- Fallback demo (no AI needed) ----------

def build_fallback_result(mode: str, user_text: str, input_style: str) -> dict:
    """
    Simple, deterministic fallback visual.
    For now, both story and table inputs use the same orbit-style visual,
    but schema annotates the inputStyle so you can refine later.
    """

    if input_style == "table_time_series":
        kind_phrase = "calendar / routine dataset (fallback visual only)"
    else:
        kind_phrase = "narrative reflection (fallback visual only)"

    summary = (
        f"Demo visual for a {kind_phrase}: "
        "a calm central orb with orbiting memories, used when Gemini is not available or fails."
    )

    schema = {
        "mode": mode,
        "inputStyle": input_style,
        "moodWord": "mixed",
        "moodIntensity": 5,
        "colorHex": "#F6C589",
        "mainPerson": None,
        "highlights": [
            "Fallback highlight 1",
            "Fallback highlight 2",
            "Fallback highlight 3",
        ],
        "rawTextPreview": (user_text or "")[:200],
    }

    # A simple PaperScript: central breathing orb + 3 orbiting dots
    paperscript = dedent(
        """
        // Fallback PaperScript demo

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
            content: 'Your Data as an Orbit',
            fillColor: new Color(1, 1, 1, 0.85),
            fontFamily: 'Helvetica Neue, Arial, sans-serif',
            fontSize: 20
        });

        // Subtitle
        var subtitle = new PointText({
            point: center + new Point(0, baseRadius + 60),
            justification: 'center',
            content: 'Fallback demo visual',
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

        // Handle resize
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
