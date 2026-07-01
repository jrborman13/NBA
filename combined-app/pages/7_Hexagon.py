"""
Player Hexagon — 6-axis player profile (Finishing, Shooting, Playmaking,
Defending, Rebounding, Gravity) as 0-100 percentile scores.

Reads the deployed Supabase objects:
  - v_player_axis_pctile : 0-100 percentile of each sub-metric (per pool/season)
  - hexagon_weights      : per-sub-metric weights (the DB defaults)
  - player_axis_metrics  : the raw sub-metric values (for hover/detail)
Axis score = weighted mean of its sub-metric percentiles (null-skipped). Weights are
editable live in the sidebar; v_player_hexagon applies the saved hexagon_weights server-side.
Refreshes nightly via refresh_show_rollups() -> refresh_player_axis_metrics().
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'player_app'))

import streamlit as st
import pandas as pd

try:
    import plotly.graph_objects as go
except ImportError:
    st.error("This page needs plotly. Install with: pip install plotly")
    st.stop()

from supabase_config import get_supabase_client, get_supabase_service_client

st.set_page_config(layout="wide")
st.title("🔷 Player Hexagon")

AXES = ["finishing", "shooting", "playmaking", "defending", "rebounding", "gravity"]
AXIS_LABELS = ["Finishing", "Shooting", "Playmaking", "Defending", "Rebounding", "Gravity"]
SEASON_TYPE = "Regular Season"
MIN_SAMPLE = 1500  # on-court offensive possessions below which scores get a noise caveat

# axis -> [(sub_metric column, display label)] — column names match v_player_axis_pctile & hexagon_weights
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
def _client():
    return get_supabase_client()


@st.cache_resource
def _service_client():
    # service-role key (optional) — needed to write hexagon_weights back as the default
    try:
        return get_supabase_service_client()
    except Exception:
        return None


@st.cache_data(ttl=3600)
def get_seasons():
    seasons, start = set(), 0
    while True:
        r = _client().table("player_axis_metrics").select("season").range(start, start + 999).execute()
        if not r.data:
            break
        seasons.update(row["season"] for row in r.data)
        if len(r.data) < 1000:
            break
        start += 1000
    return sorted(seasons, reverse=True)


@st.cache_data(ttl=3600)
def get_player_names():
    out, start = {}, 0
    while True:
        r = _client().table("players").select("player_id, first_name, last_name").range(start, start + 999).execute()
        if not r.data:
            break
        for row in r.data:
            out[row["player_id"]] = f"{row['first_name']} {row['last_name']}"
        if len(r.data) < 1000:
            break
        start += 1000
    return out


@st.cache_data(ttl=1800)
def get_pctiles(season, pool):
    r = (_client().table("v_player_axis_pctile").select("*")
         .eq("season", season).eq("season_type", SEASON_TYPE).eq("pool", pool).execute())
    df = pd.DataFrame(r.data)
    return df.set_index("player_id") if not df.empty else df


@st.cache_data(ttl=1800)
def get_raw(season):
    r = (_client().table("player_axis_metrics").select("*")
         .eq("season", season).eq("season_type", SEASON_TYPE).execute())
    df = pd.DataFrame(r.data)
    return df.set_index("player_id") if not df.empty else df


@st.cache_data(ttl=3600)
def get_default_weights():
    r = _client().table("hexagon_weights").select("axis, sub_metric, weight").execute()
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


# ---------------------------------------------------------------- controls (in-page)
if _client() is None:
    st.error("Supabase is not configured. Set SUPABASE_URL and SUPABASE_KEY in your .env.")
    st.stop()

seasons = get_seasons()
ctrl = st.columns([2, 4, 1.4])
with ctrl[0]:
    season = st.selectbox("Season", seasons, index=0)
with ctrl[1]:
    pool_label = st.radio("Compare against", ["All qualified players", "Same position"],
                          index=0, horizontal=True)
    pool = "all" if pool_label.startswith("All") else "position"
with ctrl[2]:
    st.markdown("<div style='height:1.7em'></div>", unsafe_allow_html=True)  # align with inputs
    if st.button("🗑️ Clear cache", width="stretch"):
        st.cache_data.clear()
        st.rerun()

px_df = get_pctiles(season, pool)
if px_df.empty:
    st.warning(f"No hexagon data for {season} yet.")
    st.stop()

names = get_player_names()
raw_df = get_raw(season)
px_df = px_df.copy()
px_df["name"] = [names.get(pid, str(pid)) for pid in px_df.index]
px_df = px_df.sort_values("name")
name_list = px_df["name"].tolist()

psel = st.columns(2)
with psel[0]:
    p1 = st.selectbox("Player", name_list,
                      index=name_list.index("Nikola Jokić") if "Nikola Jokić" in name_list else 0)
with psel[1]:
    p2 = st.selectbox("Compare with (optional)", ["— none —"] + name_list, index=0)

# ---------------------------------------------------------------- axis weights (in-page)
with st.expander("⚖️ Axis weights — edit to re-tune the grades (updates live)", expanded=False):
    defaults = get_default_weights()
    canon, rows = [], []
    for axis, subs in AXIS_SUBMETRICS.items():
        for sub, lbl in subs:
            canon.append((axis, sub))
            rows.append({"Axis": axis.title(), "Metric": lbl, "Weight": defaults.get((axis, sub), 1.0)})
    edited = st.data_editor(
        pd.DataFrame(rows), key="hexw", hide_index=True, width="stretch", num_rows="fixed",
        disabled=["Axis", "Metric"],
        column_config={"Weight": st.column_config.NumberColumn("Weight", min_value=0.0, max_value=5.0, step=0.5)},
    )
    weights = {canon[i]: float(edited.iloc[i]["Weight"]) for i in range(len(canon))}

    svc = _service_client()
    wb = st.columns([2, 1, 1])
    with wb[0]:
        confirm = st.checkbox("Confirm overwrite of saved defaults", value=False, key="hexw_confirm")
    with wb[1]:
        save_clicked = st.button("💾 Save as default", width="stretch",
                                 disabled=(svc is None or not confirm))
    with wb[2]:
        if st.button("↺ Reset", width="stretch"):
            st.session_state.pop("hexw", None)
            st.rerun()
    if save_clicked and svc is not None:
        payload = [{"axis": a, "sub_metric": s, "weight": w} for (a, s), w in weights.items()]
        try:
            svc.table("hexagon_weights").upsert(payload, on_conflict="axis,sub_metric").execute()
            get_default_weights.clear()
            st.success("Saved — these are now the defaults (v_player_hexagon updated for all seasons).")
        except Exception as e:
            st.error(f"Save failed: {e}")
    if svc is None:
        st.caption("Set `SUPABASE_SERVICE_KEY` in your .env to enable 'Save as default'.")
    st.caption("Scores are 0–100 percentiles vs the chosen pool, blended by these weights. "
               "Edits are session-only until saved. Defending is a proxy (no tracking-defense feed).")


# ---------------------------------------------------------------- chart
def player_bits(name):
    prow = px_df[px_df["name"] == name].iloc[0]
    pid = prow.name
    scores = compute_scores(prow.to_dict(), weights)
    raw = raw_df.loc[pid].to_dict() if (not raw_df.empty and pid in raw_df.index) else None
    return prow, scores, raw


fig = go.Figure()
prow1, scores1, raw1 = player_bits(p1)
add_trace(fig, scores1, raw1, p1, "#1f77b4")
if p2 != "— none —":
    _, scores2, raw2 = player_bits(p2)
    add_trace(fig, scores2, raw2, p2, "#d62728")

fig.update_layout(
    polar=dict(radialaxis=dict(visible=True, range=[0, 100], tickvals=[20, 40, 60, 80, 100])),
    showlegend=True, height=560, margin=dict(l=60, r=60, t=40, b=40),
)

left, right = st.columns([3, 2])
with left:
    st.plotly_chart(fig, use_container_width=True)
with right:
    st.markdown(f"#### {p1}")
    st.caption(f"Pos group **{prow1.get('pos_group') or '—'}** · on-court off. possessions "
               f"**{int(prow1['off_poss_on']):,}** · pool: **{pool_label.lower()}**")
    if int(prow1["off_poss_on"]) < MIN_SAMPLE:
        st.warning(f"⚠️ Small sample ({int(prow1['off_poss_on']):,} poss) — scores are noisier than usual.")
    st.dataframe(
        pd.DataFrame({"Axis": AXIS_LABELS, "Score": [scores1[a] for a in AXES]}),
        hide_index=True, use_container_width=True,
        column_config={"Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d")},
    )
    if raw1:
        with st.expander("Raw sub-metrics"):
            for label, txt in zip(AXIS_LABELS, raw_hover(raw1)):
                st.markdown(f"**{label}** — {txt}")
