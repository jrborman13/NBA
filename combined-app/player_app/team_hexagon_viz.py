"""
Shared team-hexagon fetch + scoring + radar rendering.

Single source of truth for the six phase-of-play spokes (Rim, Perimeter, Transition, Second
Chance, Bonus, Rebounding) shown as overlaid OFFENSE (solid) / DEFENSE (dashed) shapes, both
oriented OUTWARD = GOOD. Used by the standalone page (pages/8_Team_Hexagon.py) and the Teams-page
matchup tab (pages/1_Teams.py) so the two never drift.

Reads the deployed Supabase objects (SUPABASE_DERIVED_OBJECTS.md §8):
  - v_team_axis_pctile  : 0-100 percentile of each sub-metric, per season/season_type/side pool
  - team_axis_weights   : per-(axis, sub_metric) weights, applied to both sides
  - v_team_axis_metrics : raw sub-metric values (for hover/detail)
"""
import streamlit as st
import pandas as pd

try:
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

from supabase_config import get_supabase_client

SEASON_TYPE = "Regular Season"
WOLVES_ID = 1610612750  # home team — sorts first, marked 🐺

AXES = ["rim", "perimeter", "transition", "second_chance", "bonus", "rebounding"]
AXIS_LABELS = ["Rim", "Perimeter", "Transition", "Second Chance", "Bonus", "Rebounding"]

# axis -> [(sub_metric, display label)] — sub_metric names match v_team_axis_pctile & team_axis_weights
AXIS_SUBMETRICS = {
    "rim":           [("pct", "Rim FG% (allowed)"), ("freq", "Rim rate")],
    "perimeter":     [("pct", "3P% (allowed)"), ("freq", "3PA rate")],
    "transition":    [("ppp", "Transition PPP"), ("rate", "Transition rate")],
    "second_chance": [("ppp", "2nd-chance PPP"), ("rate", "2nd-chance rate")],
    "bonus":         [("rate", "Bonus rate"), ("rtg", "Bonus rating")],
    "rebounding":    [("reb_pct", "OREB% / DREB%")],
}


# ---------------------------------------------------------------- data access
@st.cache_resource
def client():
    return get_supabase_client()


@st.cache_data(ttl=1800)
def fetch_pctiles(season):
    """long: one row per team × side × axis × sub_metric, with pctile (0-100)."""
    c = client()
    if c is None:
        return pd.DataFrame()
    out, start = [], 0
    while True:
        r = (c.table("v_team_axis_pctile").select("*")
             .eq("season", season).eq("season_type", SEASON_TYPE).range(start, start + 999).execute())
        if not r.data:
            break
        out.extend(r.data)
        if len(r.data) < 1000:
            break
        start += 1000
    return pd.DataFrame(out)


@st.cache_data(ttl=1800)
def fetch_raw(season):
    """wide: one row per team with o_*/d_* raw sub-metrics (for hover)."""
    c = client()
    if c is None:
        return pd.DataFrame()
    r = (c.table("v_team_axis_metrics").select("*")
         .eq("season", season).eq("season_type", SEASON_TYPE).execute())
    df = pd.DataFrame(r.data)
    return df.set_index("team_id") if not df.empty else df


@st.cache_data(ttl=3600)
def fetch_default_weights():
    c = client()
    if c is None:
        return {}
    r = c.table("team_axis_weights").select("axis, sub_metric, weight").execute()
    return {(row["axis"], row["sub_metric"]): float(row["weight"]) for row in (r.data or [])}


# ---------------------------------------------------------------- scoring
def compute_scores(pdf, team_id, side, weights):
    """axis score = weighted mean of its sub-metric percentiles for one team+side."""
    sub = pdf[(pdf["team_id"] == team_id) & (pdf["side"] == side)]
    look = {(row["axis"], row["sub_metric"]): row["pctile"] for _, row in sub.iterrows()}
    out = {}
    for axis, subs in AXIS_SUBMETRICS.items():
        num = den = 0.0
        for sm, _ in subs:
            p = look.get((axis, sm))
            w = weights.get((axis, sm), 0.0)
            if w and p is not None and not pd.isna(p):
                num += w * float(p)
                den += w
        out[axis] = int(round(num / den)) if den > 0 else 0
    return out


def _f(v, fmt, scale=1.0):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    try:
        return fmt.format(float(v) * scale)
    except Exception:
        return str(v)


def raw_hover(raw_row, side):
    """per-axis raw-value strings for the given side (o_* or d_* columns)."""
    if raw_row is None:
        return ["" for _ in AXES]
    g = raw_row.get
    if side == "off":
        return [
            f"Rim rate {_f(g('o_rim_freq'), '{:.1f}%')} · Rim FG% {_f(g('o_rim_pct'), '{:.1f}%')}",
            f"3PA rate {_f(g('o_3_freq'), '{:.1f}%')} · 3P% {_f(g('o_3pct'), '{:.1f}%')}",
            f"Transition PPP {_f(g('o_trans_ppp'), '{:.2f}')} · rate {_f(g('o_trans_rate'), '{:.1%}')}",
            f"2nd-chance PPP {_f(g('o_2nd_ppp'), '{:.2f}')} · rate {_f(g('o_2nd_rate'), '{:.1%}')}",
            f"Bonus rate {_f(g('o_bonus_rate'), '{:.1%}')} · bonus ORtg {_f(g('o_bonus_ortg'), '{:.1f}')}",
            f"OREB% {_f(g('o_oreb_pct'), '{:.1%}')}",
        ]
    return [
        f"Opp rim rate {_f(g('d_rim_freq'), '{:.1f}%')} · opp rim FG% {_f(g('d_rim_pct'), '{:.1f}%')}",
        f"Opp 3PA rate {_f(g('d_3_freq'), '{:.1f}%')} · opp 3P% {_f(g('d_3pct'), '{:.1f}%')}",
        f"Transition PPP allowed {_f(g('d_trans_ppp'), '{:.2f}')} · rate {_f(g('d_trans_rate'), '{:.1%}')}",
        f"2nd-chance PPP allowed {_f(g('d_2nd_ppp'), '{:.2f}')} · rate {_f(g('d_2nd_rate'), '{:.1%}')}",
        f"Bonus rate allowed {_f(g('d_bonus_rate'), '{:.1%}')} · bonus DRtg {_f(g('d_bonus_drtg'), '{:.1f}')}",
        f"DREB% {_f(g('d_dreb_pct'), '{:.1%}')}",
    ]


def _hex_to_rgba(hex_color, alpha):
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def add_trace(fig, scores, raw_row, label, color, side):
    vals = [scores[a] for a in AXES]
    is_off = side == "off"
    fig.add_trace(go.Scatterpolar(
        r=vals + [vals[0]],
        theta=AXIS_LABELS + [AXIS_LABELS[0]],
        customdata=raw_hover(raw_row, side) + [raw_hover(raw_row, side)[0]],
        name=label,
        fill="toself" if is_off else "none",
        fillcolor=_hex_to_rgba(color, 0.12) if is_off else None,
        line=dict(color=color, width=2, dash="solid" if is_off else "dash"),
        hovertemplate="<b>%{theta}</b>: %{r}<br>%{customdata}<extra>" + label + "</extra>",
    ))


# ---------------------------------------------------------------- one-shot renderer (Teams-page tab)
def render_team_hexagon(season, team_ids, sides=("off", "def"), key_prefix="teams"):
    """Overlay 1-2 teams' offense/defense hexagons for `season`, using the DB default weights.
    Reuses the caller's already-selected team ids — no selector. Fails clean (st.info) if the
    season has no hexagon data or none of the given teams are present. Never raises."""
    if not HAS_PLOTLY:
        st.error("This view needs plotly. Install with: pip install plotly")
        return
    if client() is None:
        st.error("Supabase is not configured. Set SUPABASE_URL and SUPABASE_KEY in your .env.")
        return

    pdf = fetch_pctiles(season)
    if pdf.empty:
        st.info(f"⬡ No team hexagon data for {season} yet.")
        return

    team_names = pdf[["team_id", "team_name"]].drop_duplicates().set_index("team_id")["team_name"].to_dict()
    ids = []
    for t in team_ids:
        try:
            t = int(t)
        except (TypeError, ValueError):
            continue
        if t in team_names and t not in ids:
            ids.append(t)
    if not ids:
        st.info("⬡ No team hexagon available for this matchup yet "
                "(the season's team-hexagon data may not be loaded).")
        return

    raw_df = fetch_raw(season)
    weights = fetch_default_weights()
    colors = ["#1f77b4", "#d62728"]

    def team_bits(team_id):
        raw = raw_df.loc[team_id].to_dict() if (not raw_df.empty and team_id in raw_df.index) else None
        return {s: compute_scores(pdf, team_id, s, weights) for s in ("off", "def")}, raw

    bits = {t: team_bits(t) for t in ids}

    fig = go.Figure()
    for t, color in zip(ids, colors):
        scores, raw = bits[t]
        for side in sides:
            add_trace(fig, scores[side], raw,
                      f"{team_names[t]} {'OFF' if side == 'off' else 'DEF'}", color, side)
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100], tickvals=[20, 40, 60, 80, 100])),
        showlegend=True, height=560, margin=dict(l=60, r=60, t=40, b=40),
    )

    left, right = st.columns([3, 2])
    with left:
        st.plotly_chart(fig, use_container_width=True)
    with right:
        st.caption("Solid = offense, dashed = defense. **Outward = good** on both sides "
                   f"(0–100 percentile vs the 30 teams, {season}).")
        cols = {"Spoke": AXIS_LABELS}
        for t in ids:
            s = bits[t][0]
            cols[f"{team_names[t]} O"] = [s["off"][a] for a in AXES]
            cols[f"{team_names[t]} D"] = [s["def"][a] for a in AXES]
        st.dataframe(
            pd.DataFrame(cols), hide_index=True, use_container_width=True,
            column_config={c: st.column_config.ProgressColumn(c, min_value=0, max_value=100, format="%d")
                           for c in cols if c != "Spoke"},
        )

    # matchup edges (only when both teams are present)
    if len(ids) == 2:
        a, b = ids
        sa, sb = bits[a][0], bits[b][0]
        st.markdown("##### 🆚 Matchup edges")
        st.caption("Each team's offense vs the other's defense on the shared spokes "
                   "(0–100, outward = good). Positive favors the attacking team.")
        edge_rows = []
        for ax, lbl in zip(AXES, AXIS_LABELS):
            edge_rows.append({
                "Spoke": lbl,
                f"{team_names[a]} ATK": sa["off"][ax], f"{team_names[b]} D": sb["def"][ax],
                f"→ {team_names[a]} edge": sa["off"][ax] - sb["def"][ax],
                f"{team_names[b]} ATK": sb["off"][ax], f"{team_names[a]} D": sa["def"][ax],
                f"→ {team_names[b]} edge": sb["off"][ax] - sa["def"][ax],
            })
        st.dataframe(pd.DataFrame(edge_rows), hide_index=True, use_container_width=True)

    st.caption("Full team hexagon (season/side controls, any-two-team compare, editable weights) "
               "on the **Team Hexagon** page.")
