"""
ui_theme.py — reusable custom CSS + HTML component helpers for the NBA app.

Purely additive. Nothing here runs unless a page explicitly imports and calls it.
To fully remove the custom look, delete this file and pages/99_UI_Showcase.py —
no existing page is modified, so the app reverts to its current state.

Builds on the existing theme-aware palette in theme_colors.py (the `tc` singleton),
so light/dark mode is respected automatically.

Usage (in any page, which already adds player_app to sys.path):

    from ui_theme import inject_global_css, stat_card, badge, section_header, nav_card

    inject_global_css()                 # once, near the top of the page
    section_header("Tonight's Slate", "6 games", icon="🏀")
    c1, c2, c3 = st.columns(3)
    with c1: stat_card("Edwards PTS", "27.4", delta="+3.1 vs season", delta_good=True)
    with c2: stat_card("Team Pace", "99.8", delta="-1.2", delta_good=False)
    with c3: stat_card("Net Rtg", "+4.6", accent="#236192")
"""

from __future__ import annotations

import html as _html
from typing import Optional

import streamlit as st

try:
    from theme_colors import tc
except Exception as e:  # fail loud — this module is meaningless without the palette
    raise ImportError(
        "ui_theme requires theme_colors.tc. Ensure player_app is on sys.path "
        "(pages already do sys.path.insert(..., '..', 'player_app'))."
    ) from e


# ── Brand accents ──────────────────────────────────────────────────────────
# Default accent tracks the Streamlit primaryColor in .streamlit/config.toml.
PRIMARY = "#FF4B4B"
# Timberwolves (the app's "home" team) — handy presets for accents.
WOLVES_NAVY = "#236192"
WOLVES_GREEN = "#78BE20"
WOLVES_GRAY = "#9EA2A2"


def _esc(s) -> str:
    return _html.escape(str(s))


# ── Global CSS injector ────────────────────────────────────────────────────
def inject_global_css(
    *,
    accent: str = PRIMARY,
    tighten_top_padding: bool = True,
    style_buttons: bool = True,
    style_metrics: bool = True,
    style_tabs: bool = True,
    style_dataframe_header: bool = True,
    hide_default_footer: bool = False,
) -> None:
    """Inject one <style> block of app-wide polish.

    Every effect is opt-in via a flag and scoped to standard Streamlit
    containers, so calling this only *adds* styling. Remove the call (or the
    module) to revert. Safe to call once per page render.
    """
    tc.refresh()  # re-detect light/dark for this render
    parts = []

    if tighten_top_padding:
        parts.append(
            ".block-container{padding-top:2.2rem;padding-bottom:3rem;}"
        )

    # Headings: a touch heavier + tighter, consistent across pages.
    parts.append(
        "h1,h2,h3{font-weight:800!important;letter-spacing:-0.01em;}"
        "h1{font-size:2.05rem!important;}"
    )

    if style_buttons:
        parts.append(
            f"""
            .stButton>button{{
                border-radius:10px;border:1px solid {tc.card_border};
                font-weight:600;transition:all .15s ease;
            }}
            .stButton>button:hover{{
                border-color:{accent};color:{accent};
                transform:translateY(-1px);
                box-shadow:0 2px 8px rgba(0,0,0,0.10);
            }}
            """
        )

    if style_metrics:
        # Turn st.metric into a bordered card.
        parts.append(
            f"""
            div[data-testid="stMetric"]{{
                background:{tc.card_bg};
                border:1px solid {tc.card_border};
                border-radius:12px;padding:14px 16px;
            }}
            div[data-testid="stMetricLabel"] p{{
                font-weight:600;color:{tc.text_secondary};
            }}
            """
        )

    if style_tabs:
        parts.append(
            f"""
            button[data-baseweb="tab"]{{font-weight:600;}}
            div[data-baseweb="tab-highlight"]{{background:{accent}!important;}}
            """
        )

    if style_dataframe_header:
        parts.append(
            f"""
            div[data-testid="stDataFrame"] thead tr th{{
                background:{tc.section_bg}!important;
                font-weight:700!important;
            }}
            """
        )

    if hide_default_footer:
        parts.append("footer{visibility:hidden;}")

    st.markdown("<style>" + "".join(parts) + "</style>", unsafe_allow_html=True)


# ── Components ─────────────────────────────────────────────────────────────
def stat_card(
    label: str,
    value,
    *,
    delta: Optional[str] = None,
    delta_good: Optional[bool] = None,
    icon: Optional[str] = None,
    accent: str = PRIMARY,
    render: bool = True,
) -> str:
    """A branded stat card. Returns the HTML; renders it too unless render=False.

    delta_good=True → green, False → red, None → neutral (used only for `delta`).
    """
    tc.refresh()
    if delta_good is True:
        d_color = tc.green_text
    elif delta_good is False:
        d_color = tc.red_text
    else:
        d_color = tc.text_muted

    icon_html = f'<span style="font-size:1.1rem;margin-right:6px;">{_esc(icon)}</span>' if icon else ""
    delta_html = (
        f'<div style="font-size:.82rem;font-weight:600;color:{d_color};margin-top:4px;">{_esc(delta)}</div>'
        if delta is not None
        else ""
    )
    card = f"""
    <div style="background:{tc.card_bg};border:1px solid {tc.card_border};
                border-left:4px solid {_esc(accent)};border-radius:12px;
                padding:14px 16px;height:100%;">
        <div style="font-size:.8rem;font-weight:600;color:{tc.text_secondary};
                    text-transform:uppercase;letter-spacing:.03em;">{icon_html}{_esc(label)}</div>
        <div style="font-size:1.7rem;font-weight:800;color:{tc.text_primary};
                    line-height:1.15;margin-top:2px;">{_esc(value)}</div>
        {delta_html}
    </div>
    """
    if render:
        st.markdown(card, unsafe_allow_html=True)
    return card


def badge(text: str, kind: str = "neutral", *, render: bool = True) -> str:
    """A small pill. kind ∈ {good, bad, info, warn, neutral}."""
    tc.refresh()
    palette = {
        "good": (tc.green_bg, tc.green_text),
        "bad": (tc.red_bg, tc.red_text),
        "info": (tc.info_bg, tc.info_text),
        "warn": (tc.warn_bg, tc.warn_text),
        "neutral": (tc.neutral_bg, tc.neutral_text),
    }
    bg, fg = palette.get(kind, palette["neutral"])
    pill = (
        f'<span style="display:inline-block;background:{bg};color:{fg};'
        f'font-size:.75rem;font-weight:700;padding:3px 10px;border-radius:999px;'
        f'letter-spacing:.02em;">{_esc(text)}</span>'
    )
    if render:
        st.markdown(pill, unsafe_allow_html=True)
    return pill


def section_header(
    title: str,
    subtitle: Optional[str] = None,
    *,
    icon: Optional[str] = None,
    accent: str = PRIMARY,
    render: bool = True,
) -> str:
    """A section heading with an accent bar and optional subtitle."""
    tc.refresh()
    icon_html = f"{_esc(icon)} " if icon else ""
    sub_html = (
        f'<div style="font-size:.9rem;color:{tc.text_secondary};margin-top:2px;">{_esc(subtitle)}</div>'
        if subtitle
        else ""
    )
    block = f"""
    <div style="border-left:5px solid {_esc(accent)};padding:2px 0 2px 12px;margin:10px 0 14px 0;">
        <div style="font-size:1.35rem;font-weight:800;color:{tc.text_primary};
                    letter-spacing:-0.01em;">{icon_html}{_esc(title)}</div>
        {sub_html}
    </div>
    """
    if render:
        st.markdown(block, unsafe_allow_html=True)
    return block


def nav_card(
    title: str,
    subtitle: str,
    href: str,
    *,
    gradient: str = "linear-gradient(135deg, #1d428a 0%, #c8102e 100%)",
    render: bool = True,
) -> str:
    """A clickable gradient navigation tile (the Home.py pattern, reusable)."""
    card = f"""
    <a href="{_esc(href)}" style="text-decoration:none;">
        <div style="background:{gradient};padding:22px;border-radius:12px;
                    text-align:center;cursor:pointer;transition:transform .15s ease;
                    box-shadow:0 2px 10px rgba(0,0,0,0.12);"
             onmouseover="this.style.transform='translateY(-2px)'"
             onmouseout="this.style.transform='translateY(0)'">
            <h2 style="color:#fff;margin:0;font-weight:800;">{_esc(title)}</h2>
            <p style="color:rgba(255,255,255,0.92);margin:8px 0 0 0;">{_esc(subtitle)}</p>
        </div>
    </a>
    """
    if render:
        st.markdown(card, unsafe_allow_html=True)
    return card
