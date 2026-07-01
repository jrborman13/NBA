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
import hexagon_viz as hv  # shared fetch + scoring + radar (single source of truth; no drift)

st.set_page_config(layout="wide")
st.title("🔷 Player Hexagon")

# Shared constants + scoring/render from hexagon_viz (this page adds the selector, compare, weights UI)
AXES, AXIS_LABELS, SEASON_TYPE, MIN_SAMPLE, AXIS_SUBMETRICS = (
    hv.AXES, hv.AXIS_LABELS, hv.SEASON_TYPE, hv.MIN_SAMPLE, hv.AXIS_SUBMETRICS)


# ---------------------------------------------------------------- data access
_client = hv.client  # shared cached client


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


# Fetch + scoring + render come from hexagon_viz (shared; keeps this page and the Players-page
# hexagon tab identical). Aliased so the UI code below is unchanged.
get_pctiles = hv.fetch_pctiles          # (season, pool)
get_raw = hv.fetch_raw                  # (season)
get_default_weights = hv.fetch_default_weights
compute_scores = hv.compute_scores
_f = hv._f
raw_hover = hv.raw_hover
add_trace = hv.add_trace


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
