"""
99_UI_Showcase.py — live preview of the ui_theme.py components.

Purely additive demo page. Delete this file + player_app/ui_theme.py to fully
revert the app to its current state (no other file is touched). Sorts last in
the sidebar (99_) so it stays out of the way.

Run: cd combined-app && streamlit run Home.py  →  open "UI Showcase" in the sidebar.
"""

import os
import sys

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "player_app"))

from ui_theme import (  # noqa: E402
    inject_global_css,
    stat_card,
    badge,
    section_header,
    nav_card,
    WOLVES_NAVY,
    WOLVES_GREEN,
)

st.set_page_config(page_title="UI Showcase", page_icon="🎨", layout="wide")

# One call = app-wide polish. Toggle it to compare against stock Streamlit.
apply = st.toggle("Apply custom theme", value=True, help="Off = stock Streamlit look")
if apply:
    inject_global_css(accent=WOLVES_NAVY)

st.title("🎨 UI Showcase")
st.caption("Everything here is drawn by player_app/ui_theme.py. Nothing else in the app is modified.")

# ── Stat cards ─────────────────────────────────────────────────────────────
section_header("Stat cards", "st.metric alternative with brand accents", icon="📊", accent=WOLVES_NAVY)
c1, c2, c3, c4 = st.columns(4)
with c1:
    stat_card("Edwards PTS", "27.4", delta="+3.1 vs season", delta_good=True, icon="🐺", accent=WOLVES_NAVY)
with c2:
    stat_card("Team Pace", "99.8", delta="-1.2 vs L10", delta_good=False, accent=WOLVES_GREEN)
with c3:
    stat_card("Net Rtg", "+4.6", delta="4th in NBA", delta_good=True)
with c4:
    stat_card("Opp DRtg", "112.3", delta="neutral matchup", accent=WOLVES_NAVY)

# ── Badges ─────────────────────────────────────────────────────────────────
section_header("Badges", "Status pills for injuries, leans, tags", icon="🏷️", accent=WOLVES_NAVY)
b1, b2, b3, b4, b5 = st.columns(5)
with b1:
    badge("OVER LEAN", "good")
with b2:
    badge("UNDER LEAN", "bad")
with b3:
    badge("QUESTIONABLE", "warn")
with b4:
    badge("VALUE PLAY", "info")
with b5:
    badge("NO EDGE", "neutral")

# ── Nav cards ──────────────────────────────────────────────────────────────
section_header("Navigation tiles", "Reusable version of the Home page cards", icon="🧭", accent=WOLVES_NAVY)
n1, n2 = st.columns(2)
with n1:
    nav_card("Teams", "Matchup & Team Analytics", "/Teams")
with n2:
    nav_card(
        "Predictions",
        "Stats, props & FPTS",
        "/Predictions",
        gradient=f"linear-gradient(135deg, {WOLVES_NAVY} 0%, {WOLVES_GREEN} 100%)",
    )

# ── Native widgets, restyled ───────────────────────────────────────────────
section_header("Native widgets, restyled", "Buttons, metrics, tabs get global polish", icon="✨", accent=WOLVES_NAVY)
st.button("Refresh predictions")
m1, m2, m3 = st.columns(3)
m1.metric("Wins", "41", "+3")
m2.metric("Losses", "24", "-1")
m3.metric("Streak", "W4")
t1, t2 = st.tabs(["📈 Trends", "🏥 Injuries"])
t1.write("Tab styling inherits the accent color on the active indicator.")
t2.write("Toggle the theme switch at the top to see the before/after.")
