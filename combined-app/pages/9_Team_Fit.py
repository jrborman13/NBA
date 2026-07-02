"""Team Fit (v1) — stylistic player<->team fit from the shared style fingerprint (Path B).

Pick a player; rank all 30 teams by how well the player fits (need_fill + style_match), see WHY,
and view the player+team 2D style embedding. Honest framing: validated to beat baseline,
directional — not statistically decisive.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'player_app'))

import streamlit as st
import pandas as pd

try:
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except Exception:
    HAS_PLOTLY = False

from supabase_config import get_supabase_client
import team_fit as tf

st.set_page_config(layout="wide")
st.title("🧩 Team Fit (v1)")
st.caption("Stylistic player↔team fit from the 28-dim shared style fingerprint (offensive + "
           "defensive play-type mix, shot-zone mix, possession phase rates).")
st.warning("⚠️ **" + tf.HONEST_NOTE + "**")


@st.cache_resource(show_spinner="Loading style fingerprints…")
def load_season(season):
    return tf.SeasonFit(get_supabase_client(), season)


@st.cache_data(ttl=3600)
def get_seasons():
    c = get_supabase_client()
    seen, start = set(), 0
    while True:
        d = c.table("style_fingerprint").select("season").range(start, start + 999).execute().data
        if not d:
            break
        seen.update(r["season"] for r in d)
        if len(d) < 1000:
            break
        start += 1000
    return sorted(seen, reverse=True)


seasons = get_seasons()
if not seasons:
    st.error("No style_fingerprint data found. Run the backfill / nightly refresh first.")
    st.stop()

c1, c2, c3 = st.columns([0.25, 0.45, 0.30])
with c1:
    season = st.selectbox("Season", seasons, index=0)
sf = load_season(season)

players_sorted = sorted(sf.players, key=lambda i: sf.player_name.get(i, str(i)))
with c2:
    pid = st.selectbox("Player", players_sorted,
                       format_func=lambda i: sf.player_name.get(i, str(i)))
with c3:
    w = st.slider("Need-fill weight (w)", 0.0, 1.0, 0.9, 0.1,
                  help="w=1 → pure need-fill (where the lift is); w=0 → pure style-match. Default 0.9.")

ranked = sf.rank_teams(pid, w=w)
if not ranked:
    st.error("Could not score this player (missing fingerprint).")
    st.stop()

left, right = st.columns([0.46, 0.54])

with left:
    st.subheader(f"Best stylistic fits for {sf.player_name.get(pid, pid)}")
    df = pd.DataFrame(ranked)[["team", "blend", "need_fill", "style_match"]]
    df.columns = ["Team", "Fit (blend)", "Need-fill", "Style-match"]
    st.dataframe(
        df, hide_index=True, width="stretch", height=460,
        column_config={col: st.column_config.NumberColumn(format="%.2f", help=tf.SCORE_DEFS[col])
                       for col in ["Fit (blend)", "Need-fill", "Style-match"]},
    )
    st.caption("**Fit (blend):** " + tf.SCORE_DEFS["Fit (blend)"] + "  \n"
               "**Need-fill:** " + tf.SCORE_DEFS["Need-fill"] + "  \n"
               "**Style-match:** " + tf.SCORE_DEFS["Style-match"])

with right:
    top = ranked[0]
    st.subheader(f"Why {sf.player_name.get(pid, pid)} → {top['team']}")
    st.caption(tf.WHY_CAPTION)
    for label, p_pct, t_pct in sf.explain(pid, top["team_id"]):
        st.markdown(f"- **{label}** — you do it a lot (**{p_pct}th** pctile) · team rarely (**{t_pct}th**)")

st.divider()
st.subheader("Style embedding — players + teams in one 2D space")
st.caption("Nearby = similar playstyle. Teams are squares; the selected player is highlighted. "
           "(2D PCA of the standardized fingerprints.)")

if not HAS_PLOTLY:
    st.info("Install plotly to see the embedding.")
else:
    emb = sf.embedding()
    top_team_ids = {r["team_id"] for r in ranked[:3]}
    px_, py_, ptxt = [], [], []
    for (et, eid), (x, y) in emb.items():
        if et == "P" and eid != pid:
            px_.append(x); py_.append(y); ptxt.append(sf.player_name.get(eid, str(eid)))
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=px_, y=py_, mode="markers", name="players",
                             marker=dict(size=5, color="rgba(120,120,120,0.45)"),
                             text=ptxt, hoverinfo="text"))
    tx, ty, ttxt, tcol = [], [], [], []
    for tid in sf.teams:
        if ("T", tid) in emb:
            x, y = emb[("T", tid)]
            tx.append(x); ty.append(y); ttxt.append(sf.team_name.get(tid, str(tid)))
            tcol.append("#FF4B4B" if tid in top_team_ids else "rgba(31,119,180,0.85)")
    fig.add_trace(go.Scatter(x=tx, y=ty, mode="markers+text", name="teams",
                             marker=dict(size=12, color=tcol, symbol="square",
                                         line=dict(width=1, color="white")),
                             text=ttxt, textposition="top center", textfont=dict(size=9),
                             hoverinfo="text"))
    if ("P", pid) in emb:
        x, y = emb[("P", pid)]
        fig.add_trace(go.Scatter(x=[x], y=[y], mode="markers+text", name=sf.player_name.get(pid, "player"),
                                 marker=dict(size=16, color="#2ca02c", symbol="star",
                                             line=dict(width=1, color="white")),
                                 text=[sf.player_name.get(pid, "")], textposition="bottom center",
                                 hoverinfo="text"))
    fig.update_layout(height=560, showlegend=True, xaxis_title="PC1", yaxis_title="PC2",
                      margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig, width="stretch")
    st.caption(f"🔴 your top-3 fits ({', '.join(sf.team_name.get(t, str(t)) for t in top_team_ids)}) · "
               f"⭐ {sf.player_name.get(pid, '')}")
