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

# axis -> [(sub_metric column, display label)] — columns match v_player_axis_pctile & hexagon_weights.
# ⚠️ KEEP IN SYNC WITH hexagon_weights: this list IS the set of sub-metrics the app blends
# (compute_scores) and shows (raw_hover). Whenever the hexagon stats change (a sub-metric added /
# dropped / re-weighted via the weight backtest), add or remove it here AND in RAW_FMT below, or the
# Players-page hexagon tab will silently drift from the DB's v_player_hexagon. Zero-weight sub-metrics
# are kept here on purpose so they stay editable in the weights editor (they contribute 0 to the score).
AXIS_SUBMETRICS = {
    "finishing":  [("rim_rate", "Rim rate"), ("rim_fg_pct_over_league", "Rim FG% over league"), ("team_rim_freq_lift", "Team rim-freq on/off (w0)")],
    "shooting":   [("cs_efg", "Catch-&-shoot eFG"), ("pu_efg", "Pull-up eFG"), ("shotmaking_over_exp", "Jump make over expected"), ("atb3_att_pg", "Above-break-3 att/g"), ("spotup_ppp", "Spot-up PPP (w0)")],
    "playmaking": [("ast_pts_created", "Assist pts created"), ("ast_pct", "AST% (w0)"), ("drive_ast", "Drive assists (w0)")],
    "defending":  [("def_rim_stop", "Rim-stop (norm−actual)"), ("def_pm_stop", "FG suppression (−PM)"), ("deflections_per36", "Deflections / 36"), ("contested2_per36", "Contested 2PT / 36"), ("blk_per100", "BLK / 100"), ("stl_per100", "STL / 100"), ("drtg_swing", "DRtg on/off swing")],
    "rebounding": [("oreb_pct", "OREB%"), ("dreb_pct", "DREB%"), ("sc_rate_on_minus_off", "2nd-chance on/off"), ("contested_reb_per36", "Contested reb / 36"), ("reb_chance_pct", "Reb-chance conversion")],
    # Gravity switched to NBA tracking data from 2025-26. The _fb entries carry the
    # pre-2025-26 location proxies for players the tracking feed does not cover
    # (145 of 379 in 2025-26); they are NULL for covered players, so a player scores
    # on one formula or the other, never a mix. Splits are (w0) breakdown only.
    "gravity":    [("tracking_gravity", "NBA tracking gravity"), ("off_rating_lift", "ORtg on/off lift"),
                   ("shot_diet_gravity_efg", "Shot-diet gravity"), ("rim_freq_lift", "Rim-freq on/off lift"),
                   ("shot_diet_gravity_efg_fb", "Shot-diet gravity (untracked fallback)"),
                   ("rim_freq_lift_fb", "Rim-freq on/off lift (untracked fallback)"),
                   ("grav_onball_perim", "On-ball perimeter gravity (w0)"),
                   ("grav_offball_perim", "Off-ball perimeter gravity (w0)"),
                   ("grav_onball_int", "On-ball interior gravity (w0)"),
                   ("grav_offball_int", "Off-ball interior gravity (w0)")],
}

# Per-sub-metric display format (value scale, format string) for the "Raw sub-metrics" expander.
# ⚠️ Add an entry here for every new sub-metric added to AXIS_SUBMETRICS (falls back to 2-dp otherwise).
RAW_FMT = {
    "rim_rate": "{:.0%}", "rim_fg_pct_over_league": "{:+.1%}", "team_rim_freq_lift": "{:+.1%}",
    "cs_efg": "{:.1%}", "pu_efg": "{:.1%}", "shotmaking_over_exp": "{:+.1%}", "atb3_att_pg": "{:.1f}", "spotup_ppp": "{:.2f}",
    "ast_pts_created": "{:.1f}", "ast_pct": "{:.0%}", "drive_ast": "{:.1f}",
    "def_rim_stop": "{:+.1%}", "def_pm_stop": "{:+.1f}", "deflections_per36": "{:.1f}", "contested2_per36": "{:.1f}",
    "blk_per100": "{:.1f}", "stl_per100": "{:.1f}", "drtg_swing": "{:+.1f}",
    "oreb_pct": "{:.0%}", "dreb_pct": "{:.0%}", "sc_rate_on_minus_off": "{:+.1%}", "contested_reb_per36": "{:.1f}", "reb_chance_pct": "{:.0%}",
    "shot_diet_gravity_efg": "{:+.3f}", "off_rating_lift": "{:+.1f}", "rim_freq_lift": "{:+.1%}",
    "tracking_gravity": "{:+.2f}", "shot_diet_gravity_efg_fb": "{:+.3f}", "rim_freq_lift_fb": "{:+.1%}",
    "grav_onball_perim": "{:+.2f}", "grav_offball_perim": "{:+.2f}",
    "grav_onball_int": "{:+.2f}", "grav_offball_int": "{:+.2f}",
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
def fetch_default_weights(season: str = None):
    """Effective weights for `season`.

    hexagon_weights is season-scoped: a row applies from its `season_from`
    onward, and the most specific applicable row wins — the same resolution
    v_player_hexagon does in SQL. Gravity switched to NBA tracking data from
    2025-26, so a flat (axis, sub_metric) dict would pick a row at random and
    silently drift from the DB.

    season=None means "latest", i.e. every row applies.
    """
    c = client()
    if c is None:
        return {}
    r = c.table("hexagon_weights").select("axis, sub_metric, weight, season_from").execute()
    best = {}
    for row in (r.data or []):
        sf = row.get("season_from") or "0000-00"
        if season is not None and sf > season:
            continue                      # not yet in effect for this season
        key = (row["axis"], row["sub_metric"])
        prev = best.get(key)
        if prev is None or sf > prev[0]:
            best[key] = (sf, float(row["weight"]))
    return {k: v[1] for k, v in best.items()}


@st.cache_data(ttl=3600)
def fetch_weight_scopes(season: str = None):
    """(axis, sub_metric) -> the season_from of the row currently in effect.

    The weights editor writes back to the scope it is showing: editing while a
    2025-26 season is selected updates the 2025-26 gravity rows, editing an older
    season updates the '0000-00' defaults. Without this the editor would silently
    rewrite history while appearing to change the current season.
    """
    c = client()
    if c is None:
        return {}
    r = c.table("hexagon_weights").select("axis, sub_metric, season_from").execute()
    best = {}
    for row in (r.data or []):
        sf = row.get("season_from") or "0000-00"
        if season is not None and sf > season:
            continue
        key = (row["axis"], row["sub_metric"])
        if key not in best or sf > best[key]:
            best[key] = sf
    return best


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
    """One "· "-joined line per axis listing every sub-metric in AXIS_SUBMETRICS with its raw value.
    Data-driven from AXIS_SUBMETRICS + RAW_FMT so it always shows the complete, current set — add a
    sub-metric to those two dicts and it appears here automatically (no hand-editing this function)."""
    if raw_row is None:
        return ["" for _ in AXES]
    g = raw_row.get
    out = []
    for axis in AXES:
        parts = [f"{label} {_f(g(sub), RAW_FMT.get(sub, '{:.2f}'))}" for sub, label in AXIS_SUBMETRICS[axis]]
        out.append(" · ".join(parts))
    return out


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
    weights = fetch_default_weights(season)
    scores = compute_scores(prow.to_dict(), weights)
    raw_df = fetch_raw(season)
    raw = raw_df.loc[pid].to_dict() if (not raw_df.empty and pid in raw_df.index) else None

    fig = go.Figure()
    add_trace(fig, scores, raw, name, "#FF4B4B")  # theme primaryColor
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100], tickvals=[20, 40, 60, 80, 100])),
        showlegend=False, height=520, margin=dict(l=70, r=70, t=50, b=50),
    )

    st.markdown(f"### 🕸️ {name} — Player Hexagon · {season}")
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
