###############################################################
# renderer_selector.py — chooses the correct visual renderer
# FINAL FULLY REPLACABLE VERSION
###############################################################

from dear_data_renderer import (
    render_week_wave_A,
    render_stress_storm_B,
    render_dream_planets_C,
    render_attendance_grid_D,
    render_stats_handdrawn_E,
)


def select_renderer(schema: dict) -> str:
    """
    Based on schema["mode"] and schema["visualStandard"],
    routes to the appropriate PaperScript generator.
    """

    mode = schema.get("mode", "").lower()
    vs = schema.get("visualStandard", "").upper()

    # Defensive fallback
    if not mode:
        mode = "week"
    if not vs:
        vs = "A"

    # --- Week Renderer (A) ---
    if mode == "week" or vs == "A":
        return render_week_wave_A(schema)

    # --- Stress Renderer (B) ---
    if mode == "stress" or vs == "B":
        return render_stress_storm_B(schema)

    # --- Dream Renderer (C) ---
    if mode == "dream" or vs == "C":
        return render_dream_planets_C(schema)

    # --- Attendance Renderer (D) ---
    if mode == "attendance" or vs == "D":
        return render_attendance_grid_D(schema)

    # --- Stats Renderer (E) ---
    if mode == "stats" or vs == "E":
        return render_stats_handdrawn_E(schema)

    # Fallback - use week renderer
    return render_week_wave_A(schema)
