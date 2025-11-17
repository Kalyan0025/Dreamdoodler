import json
import os
from pathlib import Path
from textwrap import dedent
import re

import google.generativeai as gen

# ---------- CONFIG / IDENTITY ----------

IDENTITY_TEXT = Path("identity.txt").read_text(encoding="utf-8")

API_KEY = os.getenv("GEMINI_API_KEY")
if API_KEY:
    gen.configure(api_key=API_KEY)


def has_gemini_key() -> bool:
    """Return True if a Gemini API key is configured."""
    return bool(API_KEY)


# ---------- LOCAL SCHEMA BUILDERS ----------

_DAY_MAP = [
    ("Mon", "monday"),
    ("Tue", "tuesday"),
    ("Wed", "wednesday"),
    ("Thu", "thursday"),
    ("Fri", "friday"),
    ("Sat", "saturday"),
    ("Sun", "sunday"),
]


def _extract_sentences(text: str) -> list[str]:
    if not text:
        return []
    parts = re.split(r"[.\n]+", text)
    return [p.strip() for p in parts if p.strip()]


def _clamp(value, lo, hi):
    return max(lo, min(hi, value))


def _build_week_day_features(text: str) -> list[dict]:
    """
    Turn free-form weekly journal text into per-day features that can be
    used both for the Week Wave (A) and Stress Storm (B).
    """
    text = text or ""
    sentences = _extract_sentences(text)
    # map abbr -> combined sentence text
    day_sentences = {abbr: "" for abbr, _ in _DAY_MAP}

    for sent in sentences:
        low = sent.lower()
        for abbr, full in _DAY_MAP:
            if full in low or abbr.lower() in low:
                day_sentences[abbr] = (day_sentences[abbr] + " " + sent).strip()

    # simple keyword lists
    positive_words = [
        "calm",
        "friends",
        "brunch",
        "coffee",
        "good",
        "great",
        "fun",
        "nice",
        "happy",
        "relaxed",
        "celebrat",
        "walk",
        "connected",
        "well",
    ]
    negative_words = [
        "anxious",
        "anxiety",
        "stress",
        "stressed",
        "rushed",
        "lonely",
        "alone",
        "tired",
        "exhausted",
        "overwhelmed",
        "worried",
        "sad",
    ]
    focus_words = [
        "deep work",
        "library",
        "study",
        "studied",
        "studying",
        "project",
        "assignment",
        "quiet",
        "focus",
    ]
    exercise_words = [
        "run",
        "ran",
        "running",
        "walk",
        "walked",
        "jog",
        "gym",
        "workout",
        "km",
    ]
    social_words = [
        "friends",
        "brunch",
        "coffee",
        "call",
        "parents",
        "team",
        "group",
        "meeting",
    ]

    features: list[dict] = []

    for abbr, full in _DAY_MAP:
        sent = day_sentences[abbr]
        low = sent.lower()

        # defaults
        mood = 3.0
        energy = 2.0
        conn = 0.3
        stress = 2.0

        if sent:
            for w in positive_words:
                if w in low:
                    mood += 0.5
                    conn += 0.1
                    stress -= 0.3
            for w in negative_words:
                if w in low:
                    mood -= 0.6
                    conn -= 0.05
                    stress += 0.6
            for w in focus_words:
                if w in low:
                    energy += 0.6
            for w in exercise_words:
                if w in low:
                    energy += 0.7
            for w in social_words:
                if w in low:
                    conn += 0.15

            # parse "X km" if present
            km_match = re.search(r"(\d+)\s*km", low)
            if km_match:
                km = float(km_match.group(1))
                energy += km / 10.0

        mood = _clamp(round(mood), 1, 5)
        energy = _clamp(round(energy), 1, 4)
        conn = _clamp(conn, 0.0, 1.0)
        stress = _clamp(round(stress), 1, 5)

        # label: small human note
        if sent:
            words = sent.strip()[:80].split()
            label = " ".join(words[:6])
        else:
            label = ""

        features.append(
            {
                "name": abbr,
                "mood": int(mood),
                "energy": int(energy),
                "connection_score": float(conn),
                "stress": int(stress),
                "label": label,
            }
        )

    return features


def _build_dimensions(mode: str, user_text: str, table_summary: str | None, visual_standard_hint: str) -> dict:
    """
    Build a 'dimensions' dict purely from local heuristics.
    It does NOT depend on the LLM.
    """
    if mode in ("week", "stress"):
        days = _build_week_day_features(user_text)
        if mode == "week":
            return {"days": days}
        else:
            # stress timeline derived from same features
            return {
                "timeline": [
                    {"label": d["name"], "stress": d["stress"], "note": d["label"]}
                    for d in days
                ]
            }

    if mode == "dream":
        # naive: treat whole text as 3 dream clusters
        text = (user_text or "").strip()
        if not text:
            clusters = []
        else:
            words = [w for w in re.split(r"\W+", text) if w]
            step = max(1, len(words) // 3)
            chunks = [
                " ".join(words[i : i + step])
                for i in range(0, len(words), step)
            ][:3]
            clusters = []
            for i, chunk in enumerate(chunks):
                clusters.append(
                    {
                        "symbol": f"scene {i+1}",
                        "intensity": 2 + (i % 3),
                        "note": chunk[:80],
                    }
                )
        return {"clusters": clusters}

    if mode == "attendance":
        # simple 5x7 grid; mildly "driven" by text length
        base_rows = ["Week 1", "Week 2", "Week 3", "Week 4", "Week 5"]
        total_on = max(1, min(35, len(user_text or "") // 40))
        rows = []
        idx = 0
        for r_label in base_rows:
            vals = []
            for _ in range(7):
                vals.append(1 if idx < total_on else 0)
                idx += 1
            rows.append({"label": r_label, "values": vals})
        return {"rows": rows}

    # stats / generic numeric
    if table_summary:
        # try to create categories from first CSV column header
        import csv
        from io import StringIO

        f = StringIO(table_summary)
        reader = csv.reader(f)
        rows = list(reader)
        if len(rows) >= 2:
            header = rows[0]
            col_name = header[0] or "A"
            categories = []
            for i, row in enumerate(rows[1:6], start=1):
                try:
                    v = float(row[1])
                except Exception:
                    v = float(i)
                categories.append({"name": row[0] or f"{col_name}{i}", "value": v})
            return {"categories": categories}

    # generic fallback
    return {
        "categories": [
            {"name": "A", "value": 1.0},
            {"name": "B", "value": 2.0},
            {"name": "C", "value": 3.0},
        ]
    }


def _build_base_schema(
    mode: str,
    input_style: str,
    visual_standard_hint: str,
    dimensions: dict,
    notes: str,
    mood_word: str = "curious",
    mood_intensity: int = 3,
) -> dict:
    return {
        "mode": mode,
        "inputStyle": input_style,
        "visualStandard": visual_standard_hint,
        "dimensions": dimensions,
        "moodWord": mood_word,
        "moodIntensity": int(mood_intensity),
        "colorHex": "#f6c589",
        "notes": (notes or "")[:280],
    }


# ---------- SMALL HELPER TO ASK GEMINI FOR SUMMARY ----------

def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        parts = t.split("```")
        if len(parts) >= 2:
            t = parts[1].strip()
    return t


def _llm_summarise(mode: str, user_text: str) -> dict | None:
    """
    Ask Gemini only for a small JSON with summary + mood.
    If anything fails, return None.
    """
    if not API_KEY:
        return None

    prompt = dedent(
        f"""
        {IDENTITY_TEXT}

        You are helping a person visualise their personal data / journal
        in a Dear Data style. First, you only need to summarise their entry.

        mode: {mode}

        Journal or description:
        \"\"\"{user_text}\"\"\"

        Respond with ONLY valid JSON, no backticks, in this format:
        {{
          "summary": "2-3 sentence warm, human summary of what this week or data felt like.",
          "moodWord": "one lowercase word like calm, anxious, hopeful, overwhelmed, peaceful",
          "moodIntensity": 1-5
        }}
        """
    ).strip()

    try:
        model = gen.GenerativeModel("gemini-2.5-flash")
        resp = model.generate_content(prompt)
        raw = (resp.text or "").strip()
        raw = _strip_fences(raw)
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            raw = raw[start : end + 1]
        data = json.loads(raw)
        return data
    except Exception:
        return None


# ---------- PUBLIC API ----------

def call_gemini(mode, user_text, input_style, table_summary, visual_standard_hint):
    """
    Main entry: use Gemini for summary + mood, use local heuristics for schema.
    """
    if not API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set")

    summary_payload = _llm_summarise(mode, user_text)
    if not summary_payload:
        raise RuntimeError("Gemini summary failed")

    summary = summary_payload.get("summary") or "No summary from model."
    mood_word = summary_payload.get("moodWord") or "curious"
    mood_intensity = int(summary_payload.get("moodIntensity") or 3)

    dimensions = _build_dimensions(mode, user_text, table_summary, visual_standard_hint)
    schema = _build_base_schema(
        mode=mode,
        input_style=input_style,
        visual_standard_hint=visual_standard_hint,
        dimensions=dimensions,
        notes=user_text,
        mood_word=mood_word,
        mood_intensity=mood_intensity,
    )

    return {
        "summary": summary,
        "schema": schema,
        "paperscript": "",
    }


def build_fallback_result(mode, user_text, input_style, visual_standard_hint):
    """
    Used when Gemini call fails or no key is present.
    """
    dimensions = _build_dimensions(mode, user_text, None, visual_standard_hint)
    schema = _build_base_schema(
        mode=mode,
        input_style=input_style,
        visual_standard_hint=visual_standard_hint,
        dimensions=dimensions,
        notes=user_text,
    )

    return {
        "summary": "LLM unavailable — using deterministic interpretation.",
        "schema": schema,
        "paperscript": "",
    }
