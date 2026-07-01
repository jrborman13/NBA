"""
Team Hexagon — 6 phase-of-play spokes (Rim, Perimeter, Transition, Second Chance,
Bonus, Rebounding), shown as overlaid OFFENSE (solid) and DEFENSE (dashed) shapes.
Both sides are oriented so OUTWARD = GOOD (defense percentiles are inverted in the
warehouse), so a complete team fills the hexagon.

Reads the deployed Supabase objects (SUPABASE_DERIVED_OBJECTS.md §8):
  - v_team_axis_pctile  : 0-100 percentile of each sub-metric, per season/season_type/side pool
  - team_axis_weights   : per-(axis, sub_metric) weights, applied to both sides
  - v_team_axis_metrics : raw sub-metric values (for hover/detail)
Axis score = weighted mean of its sub-metric percentiles. Weights are editable live;
v_team_hexagon applies the saved team_axis_weights server-side. All views read live (no cron).

Player on/off axes (Gravity, Playmaking) have no team analog and are intentionally absent;
offense-vs-defense is the dimension that replaces them.
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
st.title("⬡ Team Hexagon")

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
def _client():
    return get_supabase_client()


@st.cache_resource
def _service_client():
    try:
        return get_supabase_service_client()
    except Exception:
        return None


@st.cache_data(ttl=3600)
def get_seasons():
    seasons, start = set(), 0
    while True:
        r = (_client().table("v_team_hexagon").select("season")
             .eq("season_type", SEASON_TYPE).range(start, start + 999).execute())
        if not r.data:
            break
        seasons.update(row["season"] for row in r.data)
        if len(r.data) < 1000:
            break
        start += 1000
    return sorted(seasons, reverse=True)


@st.cache_data(ttl=1800)
def get_pctiles(season):
    """long: one row per team × side × axis × sub_metric, with pctile (0-100)."""
    out, start = [], 0
    while True:
        r = (_client().table("v_team_axis_pctile").select("*")
             .eq("season", season).eq("season_type", SEASON_TYPE).range(start, start + 999).execute())
        if not r.data:
            break
        out.extend(r.data)
        if len(r.data) < 1000:
            break
        start += 1000
    return pd.DataFrame(out)


@st.cache_data(ttl=1800)
def get_raw(season):
    """wide: one row per team with o_*/d_* raw sub-metrics (for hover)."""
    r = (_client().table("v_team_axis_metrics").select("*")
         .eq("season", season).eq("season_type", SEASON_TYPE).execute())
    df = pd.DataFrame(r.data)
    return df.set_index("team_id") if not df.empty else df


@st.cache_data(ttl=3600)
def get_default_weights():
    r = _client().table("team_axis_weights").select("axis, sub_metric, weight").execute()
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


# ---------------------------------------------------------------- controls
if _client() is None:
    st.error("Supabase is not configured. Set SUPABASE_URL and SUPABASE_KEY in your .env.")
    st.stop()

seasons = get_seasons()
if not seasons:
    st.warning("No team hexagon data found yet.")
    st.stop()

ctrl = st.columns([2, 4, 1.4])
with ctrl[0]:
    season = st.selectbox("Season", seasons, index=0)
with ctrl[1]:
    sides_label = st.radio("Show", ["Offense + Defense", "Offense only", "Defense only"],
                           index=0, horizontal=True)
with ctrl[2]:
    st.markdown("<div style='height:1.7em'></div>", unsafe_allow_html=True)
    if st.button("🗑️ Clear cache", width="stretch"):
        st.cache_data.clear()
        st.rerun()

sides = {"Offense + Defense": ["off", "def"], "Offense only": ["off"], "Defense only": ["def"]}[sides_label]

pdf = get_pctiles(season)
if pdf.empty:
    st.warning(f"No hexagon data for {season} yet.")
    st.stop()
raw_df = get_raw(season)

# team list — Wolves first (🐺), then alphabetical
team_names = pdf[["team_id", "team_name"]].drop_duplicates().set_index("team_id")["team_name"].to_dict()
others = sorted([t for t in team_names if t != WOLVES_ID], key=lambda t: team_names[t])
ordered = ([WOLVES_ID] if WOLVES_ID in team_names else []) + others
label_of = {t: (("🐺 " if t == WOLVES_ID else "") + team_names[t]) for t in ordered}
labels = [label_of[t] for t in ordered]
id_of = {label_of[t]: t for t in ordered}

tsel = st.columns(2)
with tsel[0]:
    t1_label = st.selectbox("Team", labels, index=0)
with tsel[1]:
    t2_label = st.selectbox("Compare with (optional)", ["— none —"] + labels, index=0)
t1 = id_of[t1_label]
t2 = id_of.get(t2_label)

# ---------------------------------------------------------------- weights editor
with st.expander("⚖️ Axis weights — edit to re-tune the grades (updates live)", expanded=False):
    defaults = get_default_weights()
    canon, rows = [], []
    for axis, subs in AXIS_SUBMETRICS.items():
        for sm, lbl in subs:
            canon.append((axis, sm))
            rows.append({"Axis": axis.replace("_", " ").title(), "Metric": lbl,
                         "Weight": defaults.get((axis, sm), 1.0)})
    edited = st.data_editor(
        pd.DataFrame(rows), key="teamhexw", hide_index=True, width="stretch", num_rows="fixed",
        disabled=["Axis", "Metric"],
        column_config={"Weight": st.column_config.NumberColumn("Weight", min_value=0.0, max_value=5.0, step=0.5)},
    )
    weights = {canon[i]: float(edited.iloc[i]["Weight"]) for i in range(len(canon))}

    svc = _service_client()
    wb = st.columns([2, 1, 1])
    with wb[0]:
        confirm = st.checkbox("Confirm overwrite of saved defaults", value=False, key="teamhexw_confirm")
    with wb[1]:
        save_clicked = st.button("💾 Save as default", width="stretch", disabled=(svc is None or not confirm))
    with wb[2]:
        if st.button("↺ Reset", width="stretch"):
            st.session_state.pop("teamhexw", None)
            st.rerun()
    if save_clicked and svc is not None:
        payload = [{"axis": a, "sub_metric": s, "weight": w} for (a, s), w in weights.items()]
        try:
            svc.table("team_axis_weights").upsert(payload, on_conflict="axis,sub_metric").execute()
            get_default_weights.clear()
            st.success("Saved — these are now the defaults (v_team_hexagon updated for all seasons).")
        except Exception as e:
            st.error(f"Save failed: {e}")
    if svc is None:
        st.caption("Set `SUPABASE_SERVICE_KEY` in your .env to enable 'Save as default'.")
    st.caption("Scores are 0–100 percentiles vs the 30 teams that season (Regular Season pool), "
               "blended by these weights. Both shapes point outward = good (defense is inverted). "
               "Weights apply to offense and defense alike.")


# ---------------------------------------------------------------- chart
def team_bits(team_id):
    raw = raw_df.loc[team_id].to_dict() if (not raw_df.empty and team_id in raw_df.index) else None
    return {side: compute_scores(pdf, team_id, side, weights) for side in ("off", "def")}, raw


fig = go.Figure()
scores1, raw1 = team_bits(t1)
for side in sides:
    add_trace(fig, scores1[side], raw1, f"{team_names[t1]} {'OFF' if side == 'off' else 'DEF'}",
              "#1f77b4", side)
if t2 is not None:
    scores2, raw2 = team_bits(t2)
    for side in sides:
        add_trace(fig, scores2[side], raw2, f"{team_names[t2]} {'OFF' if side == 'off' else 'DEF'}",
                  "#d62728", side)

fig.update_layout(
    polar=dict(radialaxis=dict(visible=True, range=[0, 100], tickvals=[20, 40, 60, 80, 100])),
    showlegend=True, height=580, margin=dict(l=60, r=60, t=40, b=40),
)

left, right = st.columns([3, 2])
with left:
    st.plotly_chart(fig, use_container_width=True)
with right:
    st.markdown(f"#### {team_names[t1]}")
    st.caption("Solid = offense, dashed = defense. Outward = good on both.")
    st.dataframe(
        pd.DataFrame({"Spoke": AXIS_LABELS,
                      "Off": [scores1["off"][a] for a in AXES],
                      "Def": [scores1["def"][a] for a in AXES]}),
        hide_index=True, use_container_width=True,
        column_config={
            "Off": st.column_config.ProgressColumn("Off", min_value=0, max_value=100, format="%d"),
            "Def": st.column_config.ProgressColumn("Def", min_value=0, max_value=100, format="%d"),
        },
    )

# ---------------------------------------------------------------- matchup edges
if t2 is not None:
    st.markdown("##### 🆚 Matchup edges")
    st.caption(f"Where each team's offense out-rates the other's defense (both 0–100, outward = good). "
               f"Positive favors the attacking team.")
    scores2, _ = team_bits(t2)
    edge_rows = []
    for a, lbl in zip(AXES, AXIS_LABELS):
        a_off, b_def = scores1["off"][a], scores2["def"][a]
        b_off, a_def = scores2["off"][a], scores1["def"][a]
        edge_rows.append({
            "Spoke": lbl,
            f"{team_names[t1]} ATK": a_off, f"{team_names[t2]} D": b_def,
            f"→ {team_names[t1]} edge": a_off - b_def,
            f"{team_names[t2]} ATK": b_off, f"{team_names[t1]} D": a_def,
            f"→ {team_names[t2]} edge": b_off - a_def,
        })
    st.dataframe(pd.DataFrame(edge_rows), hide_index=True, use_container_width=True)

st.caption("Spokes: Rim & Perimeter (rate × accuracy from shot_event), Transition / Second chance / "
           "Bonus (possession engine), Rebounding (OREB%/DREB%). Player on/off axes (Gravity, "
           "Playmaking) have no team analog and are intentionally absent.")
