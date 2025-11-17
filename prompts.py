import json
import os
import re
import math
import csv
from io import StringIO
from pathlib import Path
from textwrap import dedent

import google.generativeai as gen

IDENTITY_TEXT = Path("identity.txt").read_text(encoding="utf-8")

API_KEY = os.getenv("GEMINI_API_KEY")
if API_KEY:
    gen.configure(api_key=API_KEY)


def has_gemini_key() -> bool:
    return bool(API_KEY)


# ============================================================
# PROMPT BUILDING
# ============================================================

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
    We only ask Gemini for a human summary.
    Schema/dimensions are built locally so visuals stay consistent and
    tied to the actual input instead of fragile model output.
    """
    header = _base_header(
        mode=mode,
        input_style=input_style,
        visual_standard_hint=visual_standard_hint,
        user_text=user_text,
        table_summary=table_summary,
    )

    schema_template = """
    REQUIRED FORMAT:
    {
      "summary": "1–3 sentences summarising what the user wrote: key events, emotions, stress levels, dream scenes or time-use categories.",
      "schema": {},
      "paperscript": ""
    }

    RULES:
    - Only return ONE JSON object.
    - Do NOT wrap it in markdown or ``` fences.
    - "schema" MUST be an object (can be empty – it will be ignored).
    - Never include commentary outside the JSON.
    """

    return "\n\n".join([header, schema_template]).strip()


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        parts = t.split("```")
        if len(parts) >= 2:
            t = parts[1].strip()
    return t


# ============================================================
# LOCAL DIMENSION BUILDERS (HYBRID MODEL)
# ============================================================

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _build_week_dimensions(text: str) -> dict:
    """
    Build a 7-day structure for 'week' mode.
    Tries to read segments like 'Mon: ...', 'Tue: ...'.
    If not present, falls back to a generic pattern, but still
    uses the overall tone of the text to modulate mood/energy.
    """
    text = text or ""
    lower = text.lower()

    base_days = []
    for d in DAY_NAMES:
        base_days.append(
            {
                "name": d,
                "mood": 3,
                "energy": 3,
                "connection_score": 0.3,
                "label": "",
            }
        )

    # quick overall tone
    if any(w in lower for w in ["exhausted", "tired", "burnout", "overwhelmed"]):
        base_mood = 2
        base_energy = 2
    elif any(w in lower for w in ["happy", "joy", "excited", "grateful"]):
        base_mood = 4
        base_energy = 4
    else:
        base_mood = 3
        base_energy = 3

    # connection cues
    def _conn_score(seg: str) -> float:
        seg_l = seg.lower()
        score = 0.1
        if any(w in seg_l for w in ["friend", "friends", "group", "team"]):
            score += 0.4
        if any(w in seg_l for w in ["call", "phone", "parents", "family"]):
            score += 0.3
        if any(w in seg_l for w in ["walk", "coffee", "brunch", "dinner"]):
            score += 0.2
        return max(0.0, min(1.0, score))

    # per-day parsing
    for i, day in enumerate(DAY_NAMES):
        key = f"{day.lower()}:"
        idx = lower.find(key)
        if idx == -1:
            # try "mon -", "mon –"
            for sep in [f"{day.lower()} -", f"{day.lower()} –"]:
                idx2 = lower.find(sep)
                if idx2 != -1:
                    key = sep
                    idx = idx2
                    break

        if idx == -1:
            # no explicit segment, use overall tone
            base_days[i]["mood"] = base_mood
            base_days[i]["energy"] = base_energy
            base_days[i]["connection_score"] = 0.3
            continue

        # slice from this key up to next day marker or end
        start = idx + len(key)
        slice_text = lower[start:]
        end_idx = len(slice_text)
        for other in DAY_NAMES:
            if other == day:
                continue
            marker = other.lower() + ":"
            j = slice_text.find(marker)
            if j != -1 and j < end_idx:
                end_idx = j
        segment = text[start : start + end_idx].strip()

        # mood heuristic
        seg_l = segment.lower()
        mood = base_mood
        if any(w in seg_l for w in ["sad", "down", "lonely", "anxious", "worried"]):
            mood = 2
        if any(w in seg_l for w in ["great", "amazing", "fun", "good", "calm"]):
            mood = 4
        if any(w in seg_l for w in ["panic", "awful", "terrible"]):
            mood = 1

        # energy heuristic
        energy = base_energy
        if any(w in seg_l for w in ["rushed", "busy", "deadline", "presentation"]):
            energy = min(5, energy + 1)
        if any(w in seg_l for w in ["slow", "lazy", "rest", "sleep"]):
            energy = max(1, energy - 1)

        base_days[i]["mood"] = int(max(1, min(5, mood)))
        base_days[i]["energy"] = int(max(1, min(5, energy)))
        base_days[i]["connection_score"] = _conn_score(segment)
        base_days[i]["label"] = segment[:80] if segment else ""

    return {"days": base_days}


def _build_stress_points(text: str) -> dict:
    """
    Turn a stressful journal into 4–8 timeline points for Stress visuals.
    """
    text = (text or "").strip()
    if not text:
        return {
            "timeline": [
                {
                    "label": "quiet",
                    "position": 0.0,
                    "stress": 2,
                    "emotion": "calm",
                    "body_note": "",
                },
                {
                    "label": "peak",
                    "position": 0.6,
                    "stress": 8,
                    "emotion": "anxious",
                    "body_note": "tight chest",
                },
                {
                    "label": "after",
                    "position": 1.0,
                    "stress": 4,
                    "emotion": "tired",
                    "body_note": "",
                },
            ]
        }

    raw_segments = re.split(r"[.!?]+", text)
    segments = [s.strip() for s in raw_segments if s.strip()]
    if not segments:
        segments = [text]

    max_points = 8
    if len(segments) > max_points:
        step = math.ceil(len(segments) / max_points)
        segments = segments[::step]

    n = len(segments)
    points = []

    for i, seg in enumerate(segments):
        seg_l = seg.lower()

        stress = 3
        if any(w in seg_l for w in ["exam", "deadline", "project", "quiz"]):
            stress += 2
        if any(w in seg_l for w in ["no sleep", "insomnia", "tired", "exhausted"]):
            stress += 2
        if any(w in seg_l for w in ["fight", "argument", "conflict"]):
            stress += 2
        if any(w in seg_l for w in ["walk", "rest", "breathe", "break", "meditate"]):
            stress -= 1

        stress = max(1, min(10, stress))

        if "calm" in seg_l or "better" in seg_l or "okay" in seg_l:
            emotion = "relieved"
        elif any(w in seg_l for w in ["angry", "irritated", "mad"]):
            emotion = "angry"
        elif any(w in seg_l for w in ["scared", "afraid", "nervous"]):
            emotion = "afraid"
        elif stress >= 7:
            emotion = "anxious"
        else:
            emotion = "tense"

        body_note = ""
        if any(w in seg_l for w in ["headache", "migraine"]):
            body_note = "headache"
        elif any(w in seg_l for w in ["chest", "tight"]):
            body_note = "tight chest"
        elif any(w in seg_l for w in ["stomach", "nausea"]):
            body_note = "stomach knot"

        label_words = seg.split()
        label = " ".join(label_words[:3]) if label_words else f"moment {i+1}"

        position = i / max(1, n - 1)

        points.append(
            {
                "label": label,
                "position": float(position),
                "stress": int(stress),
                "emotion": emotion,
                "body_note": body_note,
            }
        )

    return {"timeline": points}


def _build_dream_clusters(text: str) -> dict:
    """
    Break a dream into 3–5 scenes: used by dream renderer.
    """
    text = (text or "").strip()
    if not text:
        return {"scenes": []}

    raw_segments = re.split(r"[.!?\n]+", text)
    segments = [s.strip() for s in raw_segments if s.strip()]
    if not segments:
        segments = [text]

    target = 4
    if len(segments) <= target:
        scenes = segments
    else:
        step = math.ceil(len(segments) / target)
        scenes = segments[::step][:target]

    clusters = []
    for i, seg in enumerate(scenes):
        seg_l = seg.lower()

        if any(w in seg_l for w in ["calm", "peace", "quiet", "soft"]):
            emotion = "peaceful"
            base_intensity = 3
            color = "#4b8fe2"
        elif any(w in seg_l for w in ["fear", "scared", "dark", "chase", "monster"]):
            emotion = "afraid"
            base_intensity = 8
            color = "#e34b4b"
        elif any(w in seg_l for w in ["excited", "bright", "glow", "flying"]):
            emotion = "excited"
            base_intensity = 7
            color = "#f5b14a"
        else:
            emotion = "curious"
            base_intensity = 5
            color = "#9b6ae3"

        has_guide = any(
            w in seg_l
            for w in [
                "friend",
                "guide",
                "teacher",
                "someone",
                "he ",
                "she ",
                "they ",
                "you ",
            ]
        )

        intensity = max(1, min(10, base_intensity))
        orbit = 1 + (i % 4)

        clusters.append(
            {
                "id": i + 1,
                "label": seg[:40] or f"scene {i+1}",
                "emotion": emotion,
                "intensity": int(intensity),
                "colorHint": color,
                "orbit": int(orbit),
                "hasGuide": bool(has_guide),
            }
        )

    return {"scenes": clusters}


def _default_single_mood(user_text: str) -> dict:
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


def _build_stats_dimensions(table_summary: str | None) -> dict:
    """
    Tries to read simple 2-column CSV-style summary: name, value.
    Falls back to A/B/C bars.
    """
    if table_summary:
        try:
            f = StringIO(table_summary)
            reader = csv.reader(f)
            rows = list(reader)
            if len(rows) >= 2:
                header = rows[0]
                col_name = header[0] or "Item"
                cats = []
                for i, row in enumerate(rows[1:6], start=1):
                    if len(row) < 2:
                        continue
                    name = row[0] or f"{col_name}{i}"
                    try:
                        v = float(row[1])
                    except Exception:
                        v = float(i)
                    cats.append({"name": name, "value": v})
                if cats:
                    return {"categories": cats}
        except Exception:
            pass

    return {
        "categories": [
            {"name": "A", "value": 1.0},
            {"name": "B", "value": 2.0},
            {"name": "C", "value": 3.0},
        ]
    }


def _build_attendance_dimensions(text: str) -> dict:
    """
    Simple presence grid: based on text length we light up some cells.
    """
    text = text or ""
    total_on = max(1, min(35, len(text) // 40))
    rows_out = []
    idx = 0
    for label in ["Week 1", "Week 2", "Week 3", "Week 4", "Week 5"]:
        vals = []
        for _ in range(7):
            vals.append(1 if idx < total_on else 0)
            idx += 1
        rows_out.append({"label": label, "values": vals[:7]})
    return {"rows": rows_out}


def _build_dimensions(mode, user_text, table_summary, visual_standard_hint) -> dict:
    """
    Central place: from (mode, text, table) → dimensions dict.
    This is what your Dear-Data renderers consume.
    """
    text = (user_text or "").strip()

    if mode == "week":
        return _build_week_dimensions(text)

    if mode == "stress":
        return _build_stress_points(text)

    if mode == "dream":
        return _build_dream_clusters(text)

    if mode == "stress_single":
        return _default_single_mood(text)

    if mode == "stats":
        return _build_stats_dimensions(table_summary)

    if mode == "attendance":
        return _build_attendance_dimensions(text)

    # generic single mood tile when nothing else matches
    return _default_single_mood(text)


# ============================================================
# GEMINI CALL + HYBRID SCHEMA
# ============================================================

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

    try:
        data = json.loads(raw)
    except Exception:
        # If JSON is broken, fall back to local interpretation entirely
        return build_fallback_result(mode, user_text, input_style, visual_standard_hint, table_summary)

    summary = data.get("summary") or "No summary from model; using local interpretation."

    # Local schema ALWAYS wins (hybrid model)
    dimensions = _build_dimensions(mode, user_text, table_summary, visual_standard_hint)

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


# ============================================================
# FALLBACK (NO GEMINI / ERROR)
# ============================================================

def build_fallback_result(
    mode,
    user_text,
    input_style,
    visual_standard_hint,
    table_summary=None,
):
    """
    Used when GEMINI_API_KEY is missing or the call fails.
    Still builds a meaningful schema from the text.
    """
    dimensions = _build_dimensions(mode, user_text, table_summary, visual_standard_hint)

    summary = {
        "week": "Fallback Dear-Data week schema (no Gemini).",
        "stress": "Fallback stress timeline schema (no Gemini).",
        "dream": "Fallback dream scenes schema (no Gemini).",
        "stress_single": "Fallback single-mood schema (no Gemini).",
        "stats": "Fallback stats schema (no Gemini).",
        "attendance": "Fallback attendance presence schema (no Gemini).",
    }.get(mode, "Fallback generic schema (no Gemini).")

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
