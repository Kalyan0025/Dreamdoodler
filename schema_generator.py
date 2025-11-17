###############################################################
# schema_generator.py — Core Dear-Data Schema Construction
# FINAL FULLY REPLACABLE VERSION
###############################################################

import re
import csv
import math
from statistics import mean


DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


################################################################
# 1. HIGH-LEVEL ENTRY POINT
################################################################

def generate_schema(raw_text: str, csv_text: str, llm_meta: dict, forced_mode: str):
    """
    Main deterministic schema builder.
    Takes:
      - raw_text from user
      - optional CSV
      - llm_meta (summary, imagery, color_keywords, etc.)
      - forced_mode (may be "auto")

    Returns schema dict:
    {
        "mode": "week|stress|dream|attendance|stats",
        "visualStandard": "A|B|C|D|E",
        "dimensions": {...},
        "llm": llm_meta
    }
    """

    # 1) Decide mode (auto-detect or forced)
    if forced_mode != "auto":
        mode = forced_mode
    else:
        mode = auto_detect_mode(raw_text, csv_text, llm_meta)

    # 2) Map mode to visual standard
    visual_map = {
        "week": "A",
        "stress": "B",
        "dream": "C",
        "attendance": "D",
        "stats": "E",
    }
    visual_standard = visual_map.get(mode, "A")

    # 3) Build dimensions based on detected mode
    if mode == "week":
        dims = build_week_dimensions(raw_text, llm_meta)
    elif mode == "stress":
        dims = build_stress_dimensions(raw_text, llm_meta)
    elif mode == "dream":
        dims = build_dream_dimensions(raw_text, llm_meta)
    elif mode == "attendance":
        dims = build_attendance_dimensions(csv_text, raw_text)
    else:
        dims = build_stats_dimensions(csv_text, raw_text)

    # 4) Final schema
    return {
        "mode": mode,
        "visualStandard": visual_standard,
        "dimensions": dims,
        "llm": llm_meta,
        "raw_text": raw_text[:500],
    }


################################################################
# 2. MODE AUTO-DETECTION LOGIC
################################################################

def auto_detect_mode(text: str, csv_text: str, llm: dict) -> str:

    # If CSV present, strongly lean toward attendance/stats
    if csv_text:
        # Heuristic: if first column looks like dates or days → attendance
        sample = csv_text.lower()
        if "present" in sample or "absent" in sample or "attend" in sample:
            return "attendance"

        # If numerical grid → stats
        if re.search(r"\d", sample):
            return "stats"

    # LLM might suggest story type
    jt = llm.get("journal_type", "").lower()
    if jt in ["week", "stress", "dream", "attendance", "stats"]:
        return jt

    # heuristic rules
    t = text.lower()

    # Dream-like patterns
    if any(w in t for w in ["dream", "night", "floating", "strange", "vision"]):
        return "dream"

    # Emotional patterns
    if any(w in t for w in ["anxious", "stress", "tired", "burnout", "worry"]):
        return "stress"

    # Week patterns
    if any(day.lower() in t for day in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]):
        return "week"

    # Stats fallback
    return "week"


################################################################
# 3. WEEK DIMENSIONS (VISUAL STANDARD A)
################################################################

def build_week_dimensions(text: str, llm: dict):
    """
    Produces:
    {
       "days": [
          {
             "name": "Mon",
             "connection_score": float,
             "energy": int,
             "mood": int,
             "label": "string"
          }, ...
       ]
    }
    """

    # 1) Initialize 7 days
    days = []
    for d in DAY_NAMES:
        days.append({
            "name": d,
            "connection_score": 0.0,
            "energy": 2,
            "mood": 3,
            "label": ""
        })

    # 2) Split by day names if user used them
    lower = text.lower()
    for i, d in enumerate(DAY_NAMES):
        label = find_day_segment(lower, d.lower())
        if label:
            # Extract connection score via naive heuristics
            conn = extract_connection_score(label)
            days[i]["connection_score"] = conn

            # Extract energy (activity words)
            days[i]["energy"] = extract_energy(label)

            # Extract mood from LLM cues
            days[i]["mood"] = estimate_mood(llm, label)

            days[i]["label"] = label.strip()[:90]

    return {"days": days}


def find_day_segment(text, day):
    """
    Extract segment after occurrence of "mon:", "tue-" etc.
    """
    patterns = [
        day + ":",
        day + " -",
        day + " –",
        day + " —",
        day + " —",
        day + " ",
    ]
    for p in patterns:
        if p in text:
            part = text.split(p, 1)[1]
            # Cut until next day
            for d in DAY_NAMES:
                marker = d.lower()
                if marker in part:
                    part = part.split(marker, 1)[0]
            return part.strip()
    return None


def extract_connection_score(segment: str) -> float:
    """Count mentions of friends/social/work calls etc."""
    score = 0
    low = segment.lower()
    for kw in ["friend", "call", "meet", "group", "talk"]:
        score += low.count(kw)
    return min(1.0, score / 4)


def extract_energy(segment: str) -> int:
    """Rough numeric intensity."""
    low = segment.lower()
    energy = 1
    if "run" in low or "workout" in low or "gym" in low:
        energy += 2
    if "walk" in low:
        energy += 1
    if "tired" in low:
        energy -= 1
    return max(1, min(5, energy))


def estimate_mood(llm, segment):
    """Combine LLM's emotion + local textual keywords."""
    base = 3

    # LLM cues
    emo = " ".join(llm.get("emotion_keywords", []))
    if "stress" in emo or "anxious" in emo:
        base -= 1
    if "calm" in emo or "joy" in emo:
        base += 1

    # Text cues
    low = segment.lower()
    if "stress" in low or "sad" in low:
        base -= 1
    if "happy" in low or "fun" in low:
        base += 1

    return max(1, min(5, base))


################################################################
# 4. STRESS DIMENSIONS (VISUAL STANDARD B)
################################################################

def build_stress_dimensions(text: str, llm: dict):
    """
    Returns stress timeline with spikes.
    {
      "timeline": [
         { "index":0, "stress":0-5, "label":"..." }
      ]
    }
    """
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    timeline = []

    for i, line in enumerate(lines):
        stress = extract_stress_score(line, llm)
        timeline.append({
            "index": i,
            "stress": stress,
            "label": line[:120]
        })

    return {"timeline": timeline}


def extract_stress_score(line, llm):
    base = 2

    emo = " ".join(llm.get("emotion_keywords", []))
    if "stress" in emo or "anxiety" in emo:
        base += 1

    low = line.lower()
    for kw in ["stress", "panic", "tired", "angry", "overwhelmed"]:
        if kw in low:
            base += 1

    return max(0, min(5, base))


################################################################
# 5. DREAM DIMENSIONS (VISUAL STANDARD C)
################################################################

def build_dream_dimensions(text: str, llm: dict):
    """
    Builds dream clusters:
    {
       "clusters":[
         { "symbol":"stars", "intensity":3 },
         { "symbol":"waves", "intensity":2 }
       ]
    }
    """
    clusters = []
    imagery = llm.get("imagery", [])

    for img in imagery:
        clusters.append({
            "symbol": img,
            "intensity": min(5, 1 + len(img) % 4)
        })

    # fallback: use general words in text
    if not clusters:
        words = re.findall(r"[a-zA-Z]+", text.lower())
        uniq = list(set(words))[:5]
        for u in uniq:
            clusters.append({
                "symbol": u,
                "intensity": (len(u) % 5) + 1
            })

    return {"clusters": clusters}


################################################################
# 6. ATTENDANCE DIMENSIONS (VISUAL STANDARD D)
################################################################

def build_attendance_dimensions(csv_text: str, raw_text: str):
    """
    Converts CSV presence data into grid:
    {
      "rows": [
         { "label":"Name", "values":[1,0,1,...] }
      ]
    }
    """
    rows = []

    if not csv_text:
        # fallback simple structure
        return {
            "rows": [
                {"label": "Row1", "values": [1,0,1,1,0,1,0]},
                {"label": "Row2", "values": [0,1,1,0,1,1,1]},
            ]
        }

    # Parse CSV into structured grid
    csv_lines = csv_text.strip().split("\n")
    reader = csv.reader(csv_lines)
    for i, row in enumerate(reader):
        label = row[0] if row else f"Row{i+1}"
        vals = []
        for cell in row[1:]:
            if cell.strip().lower() in ["1","true","yes","present","p"]:
                vals.append(1)
            else:
                vals.append(0)
        rows.append({"label": label, "values": vals[:14]})

    return {"rows": rows}


################################################################
# 7. STATS DIMENSIONS (VISUAL STANDARD E)
################################################################

def build_stats_dimensions(csv_text: str, raw_text: str):
    """
    {
       "categories":[
          {"name":"A","value":20},
          {"name":"B","value":12}
       ]
    }
    """
    if not csv_text:
        return {
            "categories":[
                {"name":"A", "value": 5},
                {"name":"B", "value": 9},
                {"name":"C", "value": 12},
            ]
        }

    csv_lines = csv_text.strip().split("\n")
    reader = csv.reader(csv_lines)
    header = None
    categories = []

    for i, row in enumerate(reader):
        if i == 0:
            header = row
            continue

        if len(row) >= 2:
            name = row[0]
            try:
                val = float(row[1])
            except:
                continue
            categories.append({"name": name, "value": val})

    if not categories:
        categories = [{"name":"Item", "value":5}]

    return {"categories": categories}
