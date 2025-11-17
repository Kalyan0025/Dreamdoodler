# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from textwrap import dedent


def _safe_get_dimensions(schema: dict) -> dict:
    return schema.get("dimensions") or {}


# ============================================================
# RENDERER A - WEEK RHYTHM WAVE (DEAR DATA STYLE)
# ============================================================

def render_week_wave_A(schema: dict) -> str:
    """
    Dear Data–style week postcard:
    - pastel paper background
    - hand-drawn grid
    - wavy backbone for the week
    - scribbly mood clouds and activity dots
    """
    dims = _safe_get_dimensions(schema)
    days = dims.get("days") or []

    # normalise to 7 days, with defaults
    fallback_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    normalized = []
    for i, name in enumerate(fallback_names):
        base = {
            "name": name,
            "mood": 3,
            "energy": 2,
            "connection_score": 0.4,
            "label": ""
        }
        if i < len(days):
            d = days[i] or {}
            for k in base.keys():
                base[k] = d.get(k, base[k])
        normalized.append(base)

    js_days = json.dumps(normalized)

    template = """
    // Week Postcard – Dear Data style (Standard A)

    var dayData = __DAY_DATA__;

    function lerp(a, b, t) { return a + (b - a) * t; }

    function lerpColor(c1, c2, t) {
        return new Color(
            lerp(c1.red,   c2.red,   t),
            lerp(c1.green, c2.green, t),
            lerp(c1.blue,  c2.blue,  t)
        );
    }

    var moodCold  = new Color(0.46, 0.68, 0.94);
    var moodMid   = new Color(0.96, 0.82, 0.50);
    var moodWarm  = new Color(0.94, 0.48, 0.64);

    function colorForMood(mood) {
        var t = (mood - 1) / 4.0;
        if (t < 0.5) {
            return lerpColor(moodCold, moodMid, t / 0.5);
        } else {
            return lerpColor(moodMid, moodWarm, (t - 0.5) / 0.5);
        }
    }

    function jitter(pt, amt) {
        return pt.add(new Point(
            (Math.random() - 0.5) * amt,
            (Math.random() - 0.5) * amt
        ));
    }

    var bounds = view.bounds;
    var margin = 52;
    var inner  = bounds.expand(-margin);

    // Paper background
    var bg = new Path.Rectangle(bounds);
    bg.fillColor = new Color(0.99, 0.97, 0.94);

    var sheet = new Path.Rectangle(inner.expand(20));
    sheet.fillColor   = new Color(1.0, 0.995, 0.985, 0.96);
    sheet.strokeColor = new Color(0.86, 0.84, 0.80);
    sheet.strokeWidth = 1.5;

    // Subtle grid, slightly wobbly
    var gridSize = 24;
    for (var gx = inner.left; gx <= inner.right; gx += gridSize) {
        var off = (Math.random() - 0.5) * 3;
        var line = new Path.Line(
            new Point(gx + off, inner.top),
            new Point(gx + off, inner.bottom)
        );
        line.strokeColor = new Color(0.94, 0.94, 0.92, 0.6);
        line.strokeWidth = 0.5;
    }
    for (var gy = inner.top; gy <= inner.bottom; gy += gridSize) {
        var off2 = (Math.random() - 0.5) * 3;
        var line2 = new Path.Line(
            new Point(inner.left, gy + off2),
            new Point(inner.right, gy + off2)
        );
        line2.strokeColor = new Color(0.96, 0.96, 0.94, 0.6);
        line2.strokeWidth = 0.5;
    }

    // Title
    var title = new PointText(new Point(inner.left, inner.top - 22));
    title.content = "A Week in Feelings & Energy";
    title.justification = 'left';
    title.fillColor = new Color(0.28, 0.30, 0.34);
    title.fontSize = 18;

    var count = dayData.length;
    var leftX = inner.left + 40;
    var rightX = inner.right - 40;
    var stepX = (count > 1) ? (rightX - leftX) / (count - 1) : 0;

    var midY   = inner.center.y;
    var amp    = inner.height * 0.22;
    var baseY  = midY + inner.height * 0.12;

    // Collect base points for the main wave
    var controlPoints = [];
    for (var i = 0; i < count; i++) {
        var d = dayData[i];
        var mood = d.mood || 3;
        var x = leftX + stepX * i;
        var t = (mood - 1) / 4.0;
        var y = baseY - (t * amp);
        controlPoints.push(new Point(x, y));
    }

    // Draw the "bundle" of waves (multiple slightly different strokes)
    var bundleGroup = new Group();
    for (var b = 0; b < 14; b++) {
        var path = new Path();
        for (var i = 0; i < controlPoints.length; i++) {
            var base = controlPoints[i];
            var p = jitter(base, 9);
            path.add(p);
        }
        path.smooth();
        path.strokeWidth = 6;
        path.strokeCap = 'round';
        path.strokeColor = new Color(0.90, 0.46, 0.64, 0.16);
        bundleGroup.addChild(path);
    }

    // One crisper line on top
    var mainWave = new Path();
    for (var i2 = 0; i2 < controlPoints.length; i2++) {
        mainWave.add(controlPoints[i2]);
    }
    mainWave.smooth();
    mainWave.strokeWidth = 3.2;
    mainWave.strokeCap = 'round';
    mainWave.strokeColor = new Color(0.90, 0.42, 0.64, 0.9);

    // Baseline (neutral)
    var baseLine = new Path.Line(
        new Point(inner.left, baseY),
        new Point(inner.right, baseY)
    );
    baseLine.strokeColor = new Color(0.88, 0.84, 0.80, 0.9);
    baseLine.strokeWidth = 1.1;

    // Per-day scribbles & bubbles
    var labelBandY = inner.bottom - 42;

    for (var i3 = 0; i3 < count; i3++) {
        var dDay = dayData[i3];
        var name = dDay.name || "";
        var mood = dDay.mood || 3;
        var energy = dDay.energy || 2;
        var conn = dDay.connection_score || 0.0;
        var label = dDay.label || "";

        var x = leftX + stepX * i3;
        var basePt = controlPoints[i3];
        var color = colorForMood(mood);

        // Scribble cloud behind the bubble
        var scribble = new Path();
        var cloudPts = 22;
        var rBase = 18 + energy * 3;
        for (var s = 0; s < cloudPts; s++) {
            var ang = (Math.PI * 2 * s) / cloudPts;
            var rr = rBase + (Math.random() * 12 - 6);
            var p = basePt.add(new Point(
                Math.cos(ang) * rr,
                Math.sin(ang) * rr
            ));
            p = jitter(p, 2.5);
            if (s === 0) scribble.add(p);
            else scribble.lineTo(p);
        }
        scribble.closed = true;
        scribble.strokeColor = new Color(0.65, 0.60, 0.66, 0.7);
        scribble.strokeWidth = 0.7;
        scribble.fillColor = new Color(color.red, color.green, color.blue, 0.16);

        // Mood bubble
        var bubbleR = 10 + energy * 2.6;
        var bubble = new Path.Circle(jitter(basePt, 2), bubbleR);
        bubble.fillColor = color;
        bubble.strokeColor = new Color(0.26, 0.28, 0.34, 0.85);
        bubble.strokeWidth = 1.1;

        // Little ticks around bubble (intensity of day)
        var tickCount = 5 + energy * 3;
        var tickRadius = bubbleR + 4;
        for (var t2 = 0; t2 < tickCount; t2++) {
            var ang2 = (Math.PI * 2 * t2) / tickCount;
            var innerPt = basePt.add(new Point(
                Math.cos(ang2) * (bubbleR - 1),
                Math.sin(ang2) * (bubbleR - 1)
            ));
            var outerPt = basePt.add(new Point(
                Math.cos(ang2) * tickRadius,
                Math.sin(ang2) * tickRadius
            ));
            innerPt = jitter(innerPt, 1);
            outerPt = jitter(outerPt, 1);
            var tick = new Path.Line(innerPt, outerPt);
            tick.strokeColor = new Color(0.24, 0.25, 0.30, 0.7);
            tick.strokeWidth = 0.8;
        }

        // Leaf for strong connection
        if (conn >= 0.55) {
            var leafBase = basePt.add(new Point(0, -bubbleR - 12));
            leafBase = jitter(leafBase, 2);

            var stem = new Path.Line(
                leafBase.add(new Point(0, 6)),
                leafBase
            );
            stem.strokeColor = new Color(0.30, 0.50, 0.36);
            stem.strokeWidth = 1.0;

            var leaf = new Path();
            leaf.add(leafBase);
            leaf.add(leafBase.add(new Point(-6, -5)));
            leaf.add(leafBase.add(new Point(0, -8)));
            leaf.add(leafBase.add(new Point(6, -5)));
            leaf.closed = true;
            leaf.fillColor = new Color(0.60, 0.80, 0.52);
            leaf.strokeColor = new Color(0.32, 0.52, 0.40);
            leaf.strokeWidth = 0.8;
        }

        // Tiny activity dots (encode energy)
        var dotCount = 4 + energy * 3;
        for (var a = 0; a < dotCount; a++) {
            var angle = Math.random() * Math.PI * 2;
            var dist = bubbleR + 10 + Math.random() * 18;
            var ptDot = basePt.add(new Point(
                Math.cos(angle) * dist,
                Math.sin(angle) * dist
            ));
            ptDot = jitter(ptDot, 2);
            var dot = new Path.Circle(ptDot, Math.random() * 1.8 + 0.6);
            dot.fillColor = new Color(color.red, color.green, color.blue, 0.55);
        }

        // Day name
        var dayLabel = new PointText(new Point(x, labelBandY + 6));
        dayLabel.justification = 'center';
        dayLabel.content = name;
        dayLabel.fillColor = new Color(0.32, 0.34, 0.40);
        dayLabel.fontSize = 11;

        // Short note underneath (from schema label)
        var noteY = labelBandY + 20;
        var note = new PointText(new Point(x, noteY));
        note.justification = 'center';
        note.content = label;
        note.fillColor = new Color(0.55, 0.55, 0.58, 0.85);
        note.fontSize = 8;
    }

    // Legend (top-right)
    var legendOrigin = new Point(inner.right - 170, inner.top + 24);

    var legendTitle = new PointText(legendOrigin);
    legendTitle.justification = 'left';
    legendTitle.content = "Legend";
    legendTitle.fillColor = new Color(0.30, 0.32, 0.38);
    legendTitle.fontSize = 10;

    var legendBubble = new Path.Circle(legendOrigin.add(new Point(10, 18)), 5);
    legendBubble.fillColor = colorForMood(4);
    legendBubble.strokeColor = new Color(0.26, 0.28, 0.34);
    legendBubble.strokeWidth = 0.8;
    var legendBubbleText = new PointText(legendOrigin.add(new Point(26, 21)));
    legendBubbleText.justification = 'left';
    legendBubbleText.content = "Mood bubble (color & size)";
    legendBubbleText.fillColor = new Color(0.32, 0.34, 0.40);
    legendBubbleText.fontSize = 8;

    var legendDots = new Path.Circle(legendOrigin.add(new Point(10, 34)), 2);
    legendDots.fillColor = new Color(0.70, 0.70, 0.75);
    var legendDotsText = new PointText(legendOrigin.add(new Point(26, 37)));
    legendDotsText.justification = 'left';
    legendDotsText.content = "Activity dots (energy / km)";
    legendDotsText.fillColor = new Color(0.32, 0.34, 0.40);
    legendDotsText.fontSize = 8;

    var legendLeaf = new Path();
    legendLeaf.add(legendOrigin.add(new Point(6, 48)));
    legendLeaf.add(legendOrigin.add(new Point(10, 42)));
    legendLeaf.add(legendOrigin.add(new Point(14, 48)));
    legendLeaf.closed = true;
    legendLeaf.fillColor = new Color(0.60, 0.80, 0.52);
    legendLeaf.strokeColor = new Color(0.32, 0.52, 0.40);
    legendLeaf.strokeWidth = 0.8;
    var legendLeafText = new PointText(legendOrigin.add(new Point(26, 49)));
    legendLeafText.justification = 'left';
    legendLeafText.content = "Leaf = strong connection / good day";
    legendLeafText.fillColor = new Color(0.32, 0.34, 0.40);
    legendLeafText.fontSize = 8;

    function onFrame(event) {
        var t = event.time;
        for (var b = 0; b < bundleGroup.children.length; b++) {
            var path = bundleGroup.children[b];
            for (var s = 0; s < path.segments.length; s++) {
                var base = controlPoints[s];
                var phase = (b * 0.4) + (s * 0.2);
                var offsetY = Math.sin(t * 0.5 + phase) * 1.8;
                var offsetX = Math.cos(t * 0.3 + phase) * 0.8;
                path.segments[s].point = base.add(new Point(offsetX, offsetY));
            }
            path.smooth();
        }
    }
    """

    return dedent(template).replace("__DAY_DATA__", js_days)



# ============================================================
# RENDERER B - STRESS STORM
# ============================================================

def render_stress_storm_B(schema: dict) -> str:
    dims = _safe_get_dimensions(schema)
    timeline = dims.get("timeline") or []
    js_timeline = json.dumps(timeline)

    template = """
    // Stress Storm - Visual Standard B

    var timeline = __TIMELINE__;

    var bounds = view.bounds;
    var margin = 60;
    var inner = bounds.expand(-margin);

    var bg = new Path.Rectangle(bounds);
    bg.fillColor = new Color(0.98, 0.96, 0.95);

    var sheet = new Path.Rectangle(inner.expand(20));
    sheet.fillColor = new Color(1,1,1,0.96);
    sheet.strokeColor = new Color(0.85,0.8,0.78);
    sheet.strokeWidth = 1.5;

    var title = new PointText(new Point(inner.left, inner.top - 24));
    title.justification = 'left';
    title.content = "Stress Storm Timeline";
    title.fillColor = new Color(0.2,0.22,0.3);
    title.fontSize = 18;

    var count = timeline.length;
    if (count === 0) {
        var msg = new PointText(inner.center);
        msg.justification = 'center';
        msg.content = "No stress data to draw (timeline empty)";
        msg.fillColor = new Color(0.4,0.4,0.4);
        msg.fontSize = 14;
    } else {
        var leftX = inner.left + 40;
        var rightX = inner.right - 40;
        var stepX = (count > 1) ? (rightX - leftX) / (count - 1) : 0;

        var bottomY = inner.bottom - 60;
        var topY    = inner.top + 60;

        var stormPath = new Path();
        stormPath.strokeColor = new Color(0.45, 0.2, 0.35);
        stormPath.strokeWidth = 2.5;

        var scribbleGroup = new Group();

        for (var i = 0; i < count; i++) {
            var t = timeline[i];
            var stress = t.stress || 0;
            var label = t.label || "";

            var x = leftX + stepX * i;
            var norm = Math.min(1, Math.max(0, stress / 5.0));
            var y = bottomY - norm * (bottomY - topY);

            var pt = new Point(x + (Math.random()-0.5)*8,
                               y + (Math.random()-0.5)*10);
            stormPath.add(pt);

            if (stress >= 3) {
                var cloud = new Path();
                var cloudPoints = 14;
                var baseR = 16 + stress * 3;
                for (var c = 0; c < cloudPoints; c++) {
                    var ang = (Math.PI * 2 * c) / cloudPoints;
                    var rr = baseR + (Math.random()*8-4);
                    var cp = pt.add(new Point(Math.cos(ang)*rr, Math.sin(ang)*rr));
                    if (c === 0) cloud.add(cp);
                    else cloud.lineTo(cp);
                }
                cloud.closed = true;
                cloud.fillColor = new Color(0.85,0.78,0.86,0.4);
                cloud.strokeColor = new Color(0.45,0.32,0.55,0.8);
                cloud.strokeWidth = 1;
                scribbleGroup.addChild(cloud);
            }

            if (i % 2 === 0) {
                var lp = new Point(x, bottomY + 30);
                var txt = new PointText(lp);
                txt.justification = 'center';
                txt.content = label;
                txt.fillColor = new Color(0.35,0.35,0.38);
                txt.fontSize = 8;
            }
        }

        stormPath.smooth();

        var baseLine = new Path.Line(
            new Point(leftX-20, bottomY),
            new Point(rightX+20, bottomY)
        );
        baseLine.strokeColor = new Color(0.85,0.8,0.78);
        baseLine.strokeWidth = 1;

        function onFrame(event) {
            var t = event.time;
            scribbleGroup.rotate(0.03, inner.center);
            for (var i = 0; i < stormPath.segments.length; i++) {
                var seg = stormPath.segments[i];
                seg.point.y += Math.sin(t*0.8 + i*0.7) * 0.4;
            }
            stormPath.smooth();
        }
    }
    """

    return dedent(template).replace("__TIMELINE__", js_timeline)


# ============================================================
# RENDERER C - DREAM PLANETS
# ============================================================

def render_dream_planets_C(schema: dict) -> str:
    dims = _safe_get_dimensions(schema)
    clusters = dims.get("clusters") or []
    js_clusters = json.dumps(clusters)

    template = """
    // Dream Planets - Visual Standard C

    var clusters = __CLUSTERS__;

    var bounds = view.bounds;
    var margin = 60;
    var inner = bounds.expand(-margin);

    var bg = new Path.Rectangle(bounds);
    bg.fillColor = new Color(0.05, 0.07, 0.12);

    var glow = new Path.Rectangle(inner.expand(10));
    glow.fillColor = new Color(0.16, 0.14, 0.24, 0.96);
    glow.strokeColor = new Color(0.5,0.45,0.7,0.4);
    glow.strokeWidth = 1.2;

    var title = new PointText(new Point(inner.left, inner.top - 20));
    title.justification = 'left';
    title.content = "Dream Map - Planets of the Night";
    title.fillColor = new Color(0.92,0.9,0.98);
    title.fontSize = 18;

    if (clusters.length === 0) {
        var msg = new PointText(inner.center);
        msg.justification = 'center';
        msg.content = "No dream symbols detected.";
        msg.fillColor = new Color(0.86,0.84,0.92);
        msg.fontSize = 14;
    } else {
        var center = inner.center;
        var baseRadius = Math.min(inner.width, inner.height) * 0.12;

        var planets = [];
        for (var i = 0; i < clusters.length; i++) {
            var cl = clusters[i];
            var intensity = cl.intensity || 2;
            var symbol = cl.symbol || "dream";

            var angle = (Math.PI * 2 * i) / clusters.length;
            var ring = baseRadius + intensity * 18;
            var px = center.x + Math.cos(angle) * ring;
            var py = center.y + Math.sin(angle) * ring;

            var planetR = 14 + intensity * 4;
            var planet = new Path.Circle(new Point(px, py), planetR);
            planet.fillColor = new Color(
                0.4 + Math.random()*0.25,
                0.3 + Math.random()*0.25,
                0.6 + Math.random()*0.25,
                0.9
            );
            planet.strokeColor = new Color(0.95,0.9,0.99,0.8);
            planet.strokeWidth = 1.2;

            var orbit = new Path.Circle(center, ring);
            orbit.strokeColor = new Color(0.5,0.48,0.78,0.2);
            orbit.strokeWidth = 1;
            orbit.dashArray = [4,8];

            var txt = new PointText(new Point(px, py + planetR + 14));
            txt.justification = 'center';
            txt.content = symbol;
            txt.fillColor = new Color(0.95,0.94,0.98);
            txt.fontSize = 9;

            planets.push(planet);
        }

        var stars = new Group();
        for (var s = 0; s < 90; s++) {
            var sx = inner.left + Math.random()*inner.width;
            var sy = inner.top + Math.random()*inner.height;
            var star = new Path.Circle(new Point(sx, sy), Math.random()*1.4+0.3);
            star.fillColor = new Color(0.98,0.96,0.9, Math.random()*0.8+0.2);
            stars.addChild(star);
        }

        function onFrame(event) {
            var t = event.time;
            stars.rotate(0.01, center);
            for (var i = 0; i < planets.length; i++) {
                var p = planets[i];
                p.position.x += Math.sin(t*0.4 + i)*0.3;
                p.position.y += Math.cos(t*0.3 + i)*0.3;
            }
        }
    }
    """

    return dedent(template).replace("__CLUSTERS__", js_clusters)


# ============================================================
# RENDERER D - ATTENDANCE GRID
# ============================================================

def render_attendance_grid_D(schema: dict) -> str:
    dims = _safe_get_dimensions(schema)
    rows = dims.get("rows") or []
    js_rows = json.dumps(rows)

    template = """
    // Attendance Human Grid - Visual Standard D

    var rows = __ROWS__;

    var bounds = view.bounds;
    var margin = 60;
    var inner = bounds.expand(-margin);

    var bg = new Path.Rectangle(bounds);
    bg.fillColor = new Color(0.99,0.97,0.94);

    var sheet = new Path.Rectangle(inner.expand(10));
    sheet.fillColor = new Color(1,1,1,0.98);
    sheet.strokeColor = new Color(0.86,0.84,0.82);
    sheet.strokeWidth = 1.5;

    var title = new PointText(new Point(inner.left, inner.top - 24));
    title.justification = 'left';
    title.content = "Attendance Grid";
    title.fillColor = new Color(0.26,0.28,0.33);
    title.fontSize = 18;

    var maxCols = 0;
    for (var i=0; i<rows.length; i++) {
        var vals = rows[i].values || [];
        if (vals.length > maxCols) maxCols = vals.length;
    }

    if (rows.length === 0 || maxCols === 0) {
        var msg = new PointText(inner.center);
        msg.justification = 'center';
        msg.content = "No attendance data.";
        msg.fillColor = new Color(0.35,0.36,0.4);
        msg.fontSize = 14;
    } else {
        var top = inner.top + 40;
        var left = inner.left + 120;
        var bottom = inner.bottom - 40;
        var right = inner.right - 40;

        var rowH = (bottom - top) / rows.length;
        var colW = (right - left) / maxCols;

        for (var r = 0; r <= rows.length; r++) {
            var y = top + rowH * r + (Math.random()-0.5)*3;
            var line = new Path.Line(
                new Point(left-10, y),
                new Point(right+10, y)
            );
            line.strokeColor = new Color(0.9,0.9,0.9);
            line.strokeWidth = 1;
        }

        for (var c = 0; c <= maxCols; c++) {
            var x = left + colW * c + (Math.random()-0.5)*3;
            var line2 = new Path.Line(
                new Point(x, top-10),
                new Point(x, bottom+10)
            );
            line2.strokeColor = new Color(0.9,0.9,0.9);
            line2.strokeWidth = 1;
        }

        for (var i=0; i<rows.length; i++) {
            var row = rows[i];
            var vals = row.values || [];
            var rowLabel = row.label || ("Row " + (i+1));

            var ly = top + rowH * i + rowH*0.5;
            var lpt = new Point(inner.left + 20, ly+4);
            var txt = new PointText(lpt);
            txt.justification = 'left';
            txt.content = rowLabel;
            txt.fillColor = new Color(0.35,0.36,0.42);
            txt.fontSize = 10;

            for (var j=0; j<maxCols; j++) {
                var val = (j < vals.length) ? vals[j] : 0;
                var cx = left + colW * j + colW*0.5 + (Math.random()-0.5)*4;
                var cy = top + rowH * i + rowH*0.5 + (Math.random()-0.5)*3;

                var rect = new Path.Rectangle(
                    new Point(cx - colW*0.35, cy - rowH*0.35),
                    new Size(colW*0.7, rowH*0.7)
                );
                rect.strokeColor = new Color(0.8,0.8,0.8,0.9);
                rect.strokeWidth = 0.8;

                if (val === 1) {
                    rect.fillColor = new Color(0.47,0.74,0.48,0.75);
                    var chk = new Path();
                    chk.add(new Point(cx - colW*0.15, cy));
                    chk.add(new Point(cx - colW*0.04, cy + rowH*0.12));
                    chk.add(new Point(cx + colW*0.16, cy - rowH*0.16));
                    chk.strokeColor = new Color(0.15,0.35,0.18);
                    chk.strokeWidth = 1.3;
                } else {
                    rect.fillColor = new Color(0.98,0.97,0.95,0.4);
                    var dot = new Path.Circle(new Point(cx, cy), 2);
                    dot.fillColor = new Color(0.8,0.78,0.75,0.7);
                }
            }
        }
    }
    """

    return dedent(template).replace("__ROWS__", js_rows)


# ============================================================
# RENDERER E - STATS HAND-DRAWN BARS
# ============================================================

def render_stats_handdrawn_E(schema: dict) -> str:
    dims = _safe_get_dimensions(schema)
    categories = dims.get("categories") or []
    js_cats = json.dumps(categories)

    template = """
    // Stats Hand-Drawn Bars - Visual Standard E

    var categories = __CATS__;

    var bounds = view.bounds;
    var margin = 60;
    var inner = bounds.expand(-margin);

    var bg = new Path.Rectangle(bounds);
    bg.fillColor = new Color(0.99,0.97,0.94);

    var sheet = new Path.Rectangle(inner.expand(10));
    sheet.fillColor = new Color(1,1,1,0.98);
    sheet.strokeColor = new Color(0.86,0.84,0.82);
    sheet.strokeWidth = 1.5;

    var title = new PointText(new Point(inner.left, inner.top - 24));
    title.justification = 'left';
    title.content = "Hand-Drawn Stats";
    title.fillColor = new Color(0.26,0.28,0.33);
    title.fontSize = 18;

    if (categories.length === 0) {
        var msg = new PointText(inner.center);
        msg.justification = 'center';
        msg.content = "No numeric data.";
        msg.fillColor = new Color(0.4,0.4,0.4);
        msg.fontSize = 14;
    } else {
        var maxVal = 0;
        for (var i=0; i<categories.length; i++) {
            var v = categories[i].value || 0;
            if (v > maxVal) maxVal = v;
        }
        if (maxVal <= 0) maxVal = 1;

        var left = inner.left + 80;
        var right = inner.right - 40;
        var bottom = inner.bottom - 40;
        var top = inner.top + 40;

        var count = categories.length;
        var barW = (right - left) / Math.max(1, count);

        for (var g=0; g<=5; g++) {
            var gy = bottom - (bottom - top) * (g/5);
            gy += (Math.random()-0.5)*2;
            var gl = new Path.Line(
                new Point(left-20, gy),
                new Point(right+10, gy)
            );
            gl.strokeColor = new Color(0.9,0.9,0.9);
            gl.strokeWidth = 0.8;
        }

        for (var i=0; i<categories.length; i++) {
            var cat = categories[i];
            var v = cat.value || 0;
            var name = cat.name || ("C"+(i+1));

            var xCenter = left + barW*(i+0.5);
            var norm = v / maxVal;
            var h = (bottom - top) * norm;

            var x0 = xCenter - barW*0.3 + (Math.random()-0.5)*4;
            var y0 = bottom + (Math.random()-0.5)*4;

            var bar = new Path.Rectangle(
                new Point(x0, y0 - h),
                new Size(barW*0.6, h)
            );
            bar.fillColor = new Color(0.6+Math.random()*0.2,
                                      0.68+Math.random()*0.1,
                                      0.82+Math.random()*0.1,
                                      0.9);
            bar.strokeColor = new Color(0.32,0.36,0.46,0.8);
            bar.strokeWidth = 1.2;

            var s = new Path();
            var steps = 6;
            for (var k=0; k<steps; k++) {
                var px = x0 + barW*0.6*(k/(steps-1));
                var py = y0 - h + (Math.random()-0.5)*6;
                if (k==0) s.add(new Point(px,py));
                else s.lineTo(new Point(px,py));
            }
            s.strokeColor = new Color(0.26,0.3,0.38,0.7);
            s.strokeWidth = 0.8;

            var lp = new Point(xCenter, bottom + 20);
            var txt = new PointText(lp);
            txt.justification = 'center';
            txt.content = name + " (" + v.toFixed(1) + ")";
            txt.fillColor = new Color(0.3,0.32,0.38);
            txt.fontSize = 9;
        }
    }
    """

    return dedent(template).replace("__CATS__", js_cats)
