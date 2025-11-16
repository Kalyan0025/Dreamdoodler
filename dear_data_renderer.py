from __future__ import annotations

import json
from textwrap import dedent

# canonical order
DAY_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _normalize_week_days(dimensions: dict) -> list[dict]:
    """
    Return a list of 7 day dicts with: name, connection_score, events[].
    Fills missing days with empty defaults.
    """
    days = dimensions.get("days") or []

    name_map = {}
    for d in days:
        name = d.get("name") or d.get("label")
        if not name:
            continue
        key = str(name).strip()[:3].title()
        name_map[key] = {
            "name": key,
            "connection_score": float(d.get("connection_score", 0.0)),
            "events": d.get("events") or [],
        }

    normalized = []
    for name in DAY_ORDER:
        d = name_map.get(name)
        if d is None:
            d = {"name": name, "connection_score": 0.0, "events": []}
        normalized.append(d)
    return normalized


def render_week_standard_a(schema: dict) -> str:
    """
    Render a Dear Data–style week visual (Standard A) as PaperScript,
    using schema["dimensions"]["days"] if available.
    """
    dimensions = schema.get("dimensions") or {}
    days = _normalize_week_days(dimensions)

    # embed as JS literal
    js_days = json.dumps(days)

    return dedent(
        f"""
        // Dear Data – Week standard A renderer (from schema)
        var dayData = {js_days};

        var bounds = view.bounds;
        var center = view.center;

        // background
        var bg = new Path.Rectangle(bounds.expand(40));
        bg.fillColor = new Color(0.04, 0.05, 0.09, 1);

        var card = new Path.Rectangle(bounds.expand(-24), new Size(28, 28));
        card.strokeColor = new Color(0.18, 0.2, 0.3, 1);
        card.strokeWidth = 2;
        card.fillColor = new Color(0.05, 0.06, 0.11, 1);

        var cols = dayData.length;
        var leftPad = bounds.left + 120;
        var rightPad = bounds.right - 40;
        var usableWidth = rightPad - leftPad;
        var colStep = (cols > 1) ? usableWidth / (cols - 1) : 0;

        var topArea = bounds.top + 120;
        var bottomArea = bounds.bottom - 120;
        var verticalRange = bottomArea - topArea;

        function yForSlot(slotIndex) {{
            // 0 = morning, 1 = afternoon, 2 = evening
            return topArea + verticalRange * (slotIndex / 2.0);
        }}

        function colorFor(type) {{
            if (type === 'family')  return '#f6c35b';
            if (type === 'friends') return '#f28f9b';
            if (type === 'focus')   return '#6fa6ff';
            if (type === 'alone')   return '#f6f3ea';
            if (type === 'rush')    return '#ff6b5a';
            return '#cccccc';
        }}

        // stems + labels + glyphs
        for (var i = 0; i < dayData.length; i++) {{
            var x = leftPad + colStep * i;
            var day = dayData[i];

            var stem = new Path.Line(
                new Point(x, topArea - 30),
                new Point(x, bottomArea + 20)
            );
            stem.strokeColor = new Color(0.3, 0.32, 0.42, 0.6);
            stem.dashArray = [3, 6];

            var label = new PointText(new Point(x, bottomArea + 40));
            label.content = day.name || '';
            label.fontSize = 12;
            label.justification = 'center';
            label.fillColor = new Color(0.8, 0.84, 0.93, 0.95);

            var events = day.events || [];
            for (var j = 0; j < events.length; j++) {{
                var ev = events[j] || {{}};
                var timeSlot = ev.time_slot || ev.timeSlot || 'afternoon';
                var slotIndex = (timeSlot === 'morning') ? 0 :
                                (timeSlot === 'evening') ? 2 : 1;
                var y = yForSlot(slotIndex);

                var jitterX = (Math.random() - 0.5) * 8;
                var jitterY = (Math.random() - 0.5) * 4;

                var centerPt = new Point(x + jitterX, y + jitterY);
                var radius = ev.size || 12;
                var intensity = Math.max(1, ev.intensity || 1);
                var col = colorFor(ev.type || 'other');

                var circle = new Path.Circle(centerPt, radius);
                circle.fillColor = col;
                circle.opacity = (ev.type === 'alone') ? 0.85 : 0.95;

                var angleStep = 360 / intensity;
                var tickRadius = radius + 4;

                for (var k = 0; k < intensity; k++) {{
                    var a = (angleStep * k) - 90;
                    var rad = a * Math.PI / 180;

                    var outer = centerPt + new Point(
                        tickRadius * Math.cos(rad),
                        tickRadius * Math.sin(rad)
                    );
                    var inner = centerPt + new Point(
                        (radius - 2) * Math.cos(rad),
                        (radius - 2) * Math.sin(rad)
                    );

                    var t = new Path.Line(inner, outer);
                    t.strokeColor = (ev.type === 'alone') ? '#d6d1c6' : '#1d2639';
                    t.strokeWidth = 1;
                }}
            }}
        }}

        // connection ribbon
        var ribbon = new Path();
        var baseRibbonPoints = [];
        for (var i = 0; i < dayData.length; i++) {{
            var x = leftPad + colStep * i;
            var score = dayData[i].connection_score || 0;
            var baseY = bottomArea + 10;
            var p = new Point(x, baseY - score * 40);
            ribbon.add(p);
            baseRibbonPoints.push(p.clone());

            var node = new Path.Circle(p, 3);
            node.fillColor = '#f28f9b';
        }}
        ribbon.strokeColor = '#f28f9b';
        ribbon.strokeWidth = 2.5;
        ribbon.smooth();

        var title = new PointText(new Point(bounds.left + 40, topArea - 30));
        title.content = "A Week of Connection & Quiet Focus";
        title.fontSize = 16;
        title.justification = 'left';
        title.fillColor = new Color(0.93, 0.94, 0.98, 0.96);

        function onFrame(event) {{
            for (var i = 0; i < ribbon.segments.length; i++) {{
                var base = baseRibbonPoints[i];
                ribbon.segments[i].point.y = base.y + Math.sin(event.time * 1 + i) * 2;
            }}
            ribbon.smooth();
        }}
        """
    )
