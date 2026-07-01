"""
Shared player-hexagon fetch + scoring + radar rendering.

Single source of truth for the 6-axis player hexagon so the standalone page (pages/7_Hexagon.py)
and the Players-page tab (pages/2_Players.py) never drift. Reads the deployed Supabase objects:
  - v_player_axis_pctile : 0-100 percentile of each sub-metric (per pool/season)
  - hexagon_weights      : per-sub-metric weights (DB defaults)
  - player_axis_metrics  : raw sub-metric values (for hover/detail)
Axis score = weighted mean of its sub-metric percentiles (null-skipped).
"""
import streamlit as st
import pandas as pd

try:
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

from supabase_config import get_supabase_client

AXES = ["finishing", "shooting", "playmaking", "defending", "rebounding", "gravity"]
AXIS_LABELS = ["Finishing", "Shooting", "Playmaking", "Defending", "Rebounding", "Gravity"]
SEASON_TYPE = "Regular Season"
MIN_SAMPLE = 1500  # on-court offensive possessions below which scores get a noise caveat

# axis -> [(sub_metric column, display label)] — columns match v_player_axis_pctile & hexagon_weights
AXIS_SUBMETRICS = {
    "finishing":  [("rim_rate", "Rim rate"), ("rim_fg_pct_over_league", "Rim FG% over league"), ("team_rim_freq_lift", "Team rim-freq on/off")],
    "shooting":   [("cs_efg", "Catch-&-shoot eFG"), ("pu_efg", "Pull-up eFG"), ("shotmaking_over_exp", "Jump make over expected"), ("spotup_ppp", "Spot-up PPP")],
    "playmaking": [("ast_pct", "AST%"), ("ast_pts_created", "Assist pts created"), ("drive_ast", "Drive assists")],
    "defending":  [("def_rim_stop", "Rim-stop (norm−actual)"), ("def_pm_stop", "FG suppression (−PM)"), ("deflections_per36", "Deflections / 36"), ("contested2_per36", "Contested 2PT / 36"), ("blk_per100", "BLK / 100"), ("stl_per100", "STL / 100")],
    "rebounding": [("oreb_pct", "OREB%"), ("dreb_pct", "DREB%"), ("sc_rate_on_minus_off", "2nd-chance on/off"), ("contested_reb_per36", "Contested reb / 36"), ("reb_chance_pct", "Reb-chance conversion")],
    "gravity":    [("shot_diet_gravity_efg", "Shot-diet gravity"), ("off_rating_lift", "ORtg on/off lift"), ("rim_freq_lift", "Rim-freq on/off lift")],
}


# ---------------------------------------------------------------- data access
@st.cache_resource
def client():
    return get_supabase_client()


@st.cache_data(ttl=1800)
def fetch_pctiles(season, pool):
    c = client()
    if c is None:
        return pd.DataFrame()
    r = (c.table("v_player_axis_pctile").select("*")
         .eq("season", season).eq("season_type", SEASON_TYPE).eq("pool", pool).execute())
    df = pd.DataFrame(r.data)
    return df.set_index("player_id") if not df.empty else df


@st.cache_data(ttl=1800)
def fetch_raw(season):
    c = client()
    if c is None:
        return pd.DataFrame()
    r = (c.table("player_axis_metrics").select("*")
         .eq("season", season).eq("season_type", SEASON_TYPE).execute())
    df = pd.DataFrame(r.data)
    return df.set_index("player_id") if not df.empty else df


@st.cache_data(ttl=3600)
def fetch_default_weights():
    c = client()
    if c is None:
        return {}
    r = c.table("hexagon_weights").select("axis, sub_metric, weight").execute()
    return {(row["axis"], row["sub_metric"]): float(row["weight"]) for row in (r.data or [])}


# ---------------------------------------------------------------- scoring
def compute_scores(prow, weights):
    """axis score = weighted mean of its sub-metric percentiles, skipping nulls"""
    out = {}
    for axis, subs in AXIS_SUBMETRICS.items():
        num = den = 0.0
        for sub, _ in subs:
            p = prow.get(sub) if prow is not None else None
            w = weights.get((axis, sub), 0.0)
            if w and p is not None and not pd.isna(p):
                num += w * float(p)
                den += w
        out[axis] = int(round(num / den)) if den > 0 else 0
    return out


def _f(v, fmt, scale=1.0):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    try:
        return fmt.format(v * scale)
    except Exception:
        return str(v)


def raw_hover(raw_row):
    if raw_row is None:
        return ["" for _ in AXES]
    g = raw_row.get
    return [
        f"Rim rate {_f(g('rim_rate'), '{:.0%}')} · Rim FG% vs lg {_f(g('rim_fg_pct_over_league'), '{:+.1%}')} · team rim-freq on/off {_f(g('team_rim_freq_lift'), '{:+.1%}')}",
        f"C&S eFG {_f(g('cs_efg'), '{:.1%}')} · Pull-up eFG {_f(g('pu_efg'), '{:.1%}')} · Jump make vs exp {_f(g('shotmaking_over_exp'), '{:+.1%}')} · Spot-up PPP {_f(g('spotup_ppp'), '{:.2f}')}",
        f"AST% {_f(g('ast_pct'), '{:.0%}')} · Ast pts created {_f(g('ast_pts_created'), '{:.1f}')} · Drive ast {_f(g('drive_ast'), '{:.1f}')}",
        f"Rim-stop {_f(g('def_rim_stop'), '{:+.1%}')} · FG suppression {_f(g('def_pm_stop'), '{:+.1f}')} · Defl/36 {_f(g('deflections_per36'), '{:.1f}')} · Cont2/36 {_f(g('contested2_per36'), '{:.1f}')}",
        f"OREB% {_f(g('oreb_pct'), '{:.0%}')} · DREB% {_f(g('dreb_pct'), '{:.0%}')} · 2nd-chance on/off {_f(g('sc_rate_on_minus_off'), '{:+.1%}')} · Cont reb/36 {_f(g('contested_reb_per36'), '{:.1f}')}",
        f"Shot-diet gravity {_f(g('shot_diet_gravity_efg'), '{:+.3f}')} · ORtg lift {_f(g('off_rating_lift'), '{:+.1f}')} · rim-freq lift {_f(g('rim_freq_lift'), '{:+.1%}')}",
    ]


def add_trace(fig, scores, raw_row, name, color):
    vals = [scores[a] for a in AXES]
    fig.add_trace(go.Scatterpolar(
        r=vals + [vals[0]],
        theta=AXIS_LABELS + [AXIS_LABELS[0]],
        customdata=raw_hover(raw_row) + [raw_hover(raw_row)[0]],
        fill="toself", name=name, line=dict(color=color, width=2),
        hovertemplate="<b>%{theta}</b>: %{r}<br>%{customdata}<extra>" + name + "</extra>",
    ))


# ---------------------------------------------------------------- one-shot renderer (for the Players tab)
def render_hexagon_tab(season, player_id, player_name=None, pool="all", key_prefix="players"):
    """Render the six-axis hexagon for a single player using the DB default weights. Lean version
    for embedding as a tab: no player selector / no weight editor. Fails clean (st.info) if the
    player has no hexagon row (< 1000 on-court off. possessions that season). Never raises."""
    if not HAS_PLOTLY:
        st.error("This view needs plotly. Install with: pip install plotly")
        return
    if client() is None:
        st.error("Supabase is not configured. Set SUPABASE_URL and SUPABASE_KEY in your .env.")
        return

    try:
        pid = int(player_id)
    except (TypeError, ValueError):
        st.info("No hexagon available for this player.")
        return

    name = player_name or str(pid)
    px_df = fetch_pctiles(season, pool)
    if px_df.empty or pid not in px_df.index:
        st.info(f"🕸️ No hexagon data for **{name}** in {season} — the hexagon needs **≥ 1,000 "
                f"on-court offensive possessions** in the season (bench/low-minute and just-traded "
                f"players may not qualify yet).")
        return

    prow = px_df.loc[pid]
    if isinstance(prow, pd.DataFrame):   # dup-index guard
        prow = prow.iloc[0]
    weights = fetch_default_weights()
    scores = compute_scores(prow.to_dict(), weights)
    raw_df = fetch_raw(season)
    raw = raw_df.loc[pid].to_dict() if (not raw_df.empty and pid in raw_df.index) else None

    fig = go.Figure()
    add_trace(fig, scores, raw, name, "#1f77b4")
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100], tickvals=[20, 40, 60, 80, 100])),
        showlegend=False, height=520, margin=dict(l=60, r=60, t=30, b=30),
    )

    left, right = st.columns([3, 2])
    with left:
        st.plotly_chart(fig, use_container_width=True)
    with right:
        st.markdown(f"#### 🕸️ {name}")
        off_poss = int(prow["off_poss_on"]) if "off_poss_on" in prow and not pd.isna(prow["off_poss_on"]) else 0
        st.caption(f"Pos group **{prow.get('pos_group') or '—'}** · on-court off. possessions "
                   f"**{off_poss:,}** · 0–100 percentile vs all qualified players ({season})")
        if off_poss < MIN_SAMPLE:
            st.warning(f"⚠️ Small sample ({off_poss:,} poss) — scores are noisier than usual.")
        st.dataframe(
            pd.DataFrame({"Axis": AXIS_LABELS, "Score": [scores[a] for a in AXES]}),
            hide_index=True, use_container_width=True,
            column_config={"Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d")},
        )
        if raw:
            with st.expander("Raw sub-metrics"):
                for label, txt in zip(AXIS_LABELS, raw_hover(raw)):
                    st.markdown(f"**{label}** — {txt}")
    st.caption("Full hexagon (position pool, 2-player compare, editable weights) on the **Player Hexagon** page.")
