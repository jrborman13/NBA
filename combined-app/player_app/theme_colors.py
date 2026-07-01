"""
Theme-aware color palette for the NBA Analytics App.

Detects light vs dark mode via st.get_option('theme.backgroundColor')
and returns appropriate colors for custom HTML/CSS rendering.

Usage:
    from theme_colors import tc
    st.markdown(f'<div style="background:{tc.green_bg};color:{tc.green_text};">Over</div>', ...)
"""

import streamlit as st


def _is_dark_mode() -> bool:
    """Detect if the active Streamlit theme is dark."""
    try:
        bg = st.get_option("theme.backgroundColor") or ""
        if not bg:
            return False
        # Parse hex to check luminance
        bg = bg.lstrip("#")
        if len(bg) == 6:
            r, g, b = int(bg[0:2], 16), int(bg[2:4], 16), int(bg[4:6], 16)
            # Perceived luminance — dark if below ~128
            return (0.299 * r + 0.587 * g + 0.114 * b) < 128
    except Exception:
        pass
    return False


class _ThemeColors:
    """Color palette that adapts to light/dark mode. Access via the `tc` singleton."""

    def __init__(self):
        self._cache_key = None
        self._load()

    def _load(self):
        dark = _is_dark_mode()
        key = "dark" if dark else "light"
        if key == self._cache_key:
            return
        self._cache_key = key

        if dark:
            # ── Dark mode palette ──────────────────────────────────────
            # Greens (over / positive)
            self.green_bg = "rgba(46, 125, 50, 0.35)"
            self.green_text = "#81C784"
            self.green_bg_solid = "#1B3A1E"
            # Reds (under / negative)
            self.red_bg = "rgba(183, 28, 28, 0.35)"
            self.red_text = "#EF9A9A"
            self.red_bg_solid = "#3A1B1B"
            # Neutral / gray
            self.neutral_bg = "rgba(255, 255, 255, 0.08)"
            self.neutral_text = "#B0B0B0"
            # Info / blue
            self.info_bg = "rgba(33, 150, 243, 0.25)"
            self.info_text = "#90CAF9"
            # Warning / yellow-orange
            self.warn_bg = "rgba(255, 193, 7, 0.25)"
            self.warn_text = "#FFE082"
            # Card / container backgrounds
            self.card_bg = "rgba(255, 255, 255, 0.06)"
            self.card_border = "rgba(255, 255, 255, 0.12)"
            # Text
            self.text_primary = "#E0E0E0"
            self.text_secondary = "#9E9E9E"
            self.text_muted = "#757575"
            # Injury status
            self.injury_out = "#EF5350"
            self.injury_doubtful = "#FFA726"
            self.injury_questionable = "#FFEE58"
            self.injury_probable = "#66BB6A"
            self.injury_unknown = "#9E9E9E"
            self.injury_text = "#FFFFFF"
            # Heatmap gradients (for averages table)
            self.heatmap_green = lambda intensity: f"rgba(46, 125, 50, {0.15 + 0.35 * min(intensity, 1.0):.2f})"
            self.heatmap_red = lambda intensity: f"rgba(183, 28, 28, {0.15 + 0.35 * min(intensity, 1.0):.2f})"
            self.heatmap_neutral = "rgba(255, 255, 255, 0.06)"
            # Prop highlight (game logs)
            self.prop_over_bg = "rgba(46, 125, 50, 0.3)"
            self.prop_under_bg = "rgba(183, 28, 28, 0.3)"
            # Lean styling (dataframe)
            self.lean_over_bg = "#1B3A1E"
            self.lean_over_text = "#81C784"
            self.lean_under_bg = "#3A1B1B"
            self.lean_under_text = "#EF9A9A"
            # Image placeholder bg
            self.img_placeholder = "#2A2A2A"
            # Section header bg (e.g. team logos row)
            self.section_bg = "rgba(255, 255, 255, 0.05)"
        else:
            # ── Light mode palette ─────────────────────────────────────
            self.green_bg = "#d4edda"
            self.green_text = "#155724"
            self.green_bg_solid = "#d4edda"
            self.red_bg = "#f8d7da"
            self.red_text = "#721c24"
            self.red_bg_solid = "#f8d7da"
            self.neutral_bg = "rgb(240, 240, 240)"
            self.neutral_text = "#666666"
            self.info_bg = "#e8f4fd"
            self.info_text = "#0c5460"
            self.warn_bg = "#fff3cd"
            self.warn_text = "#856404"
            self.card_bg = "#FFFFFF"
            self.card_border = "#dee2e6"
            self.text_primary = "#262730"
            self.text_secondary = "#555555"
            self.text_muted = "#666666"
            self.injury_out = "#dc3545"
            self.injury_doubtful = "#fd7e14"
            self.injury_questionable = "#ffc107"
            self.injury_probable = "#28a745"
            self.injury_unknown = "#6c757d"
            self.injury_text = "#FFFFFF"
            self.heatmap_green = lambda intensity: f"rgb(200, {int(200 + 55 * min(intensity, 1.0))}, 200)"
            self.heatmap_red = lambda intensity: f"rgb({int(200 + 55 * min(intensity, 1.0))}, 200, 200)"
            self.heatmap_neutral = "rgb(240, 240, 240)"
            self.prop_over_bg = "rgb(200, 235, 200)"
            self.prop_under_bg = "rgb(245, 200, 200)"
            self.lean_over_bg = "#d4edda"
            self.lean_over_text = "#155724"
            self.lean_under_bg = "#f8d7da"
            self.lean_under_text = "#721c24"
            self.img_placeholder = "#f0f0f0"
            self.section_bg = "#e8f4f8"

    def refresh(self):
        """Re-detect theme. Call at the top of each page render if needed."""
        self._cache_key = None
        self._load()

    @property
    def is_dark(self) -> bool:
        self._load()
        return self._cache_key == "dark"


# Singleton — import this in pages
tc = _ThemeColors()
