"""
Injury Impact Analysis
======================
Streamlit app that analyses the ripple effects when any NBA player misses games:
  • Teammates who earn more minutes / improved stats
  • Team on/off rating differentials
  • Best-performing 5-man lineups that don't include the absent player

Run from the project root:
    streamlit run analysis/injuries/app.py
"""

import sys
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — must happen before any nba_api import so the header patch lands
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / 'combined-app' / 'player_app'))
sys.path.insert(0, str(_PROJECT_ROOT / 'streamlit'))

# Patch NBA API headers to avoid 403s from stats.nba.com
from nba_api.library.http import NBAHTTP
NBAHTTP.headers = {
    "Host": "stats.nba.com",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "Connection": "keep-alive",
}

import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import nba_api.stats.endpoints as endpoints
from nba_api.stats.static import teams as _nba_teams_static

import player_functions as pf
import prediction_features as pf_feat
import team_onoff as toff

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Injury Impact Analysis",
    page_icon="🏥",
    layout="wide",
)

CURRENT_SEASON = "2025-26"

# ---------------------------------------------------------------------------
# Static data helpers
# ---------------------------------------------------------------------------

@st.cache_data(ttl=86400, show_spinner=False)
def _all_nba_teams() -> list[dict]:
    """Return all 30 NBA teams sorted by full name."""
    return sorted(_nba_teams_static.get_teams(), key=lambda t: t['full_name'])


@st.cache_data(ttl=3600, show_spinner=False)
def _players_df() -> pd.DataFrame:
    return pf.get_players_dataframe()


@st.cache_data(ttl=3600, show_spinner=False)
def _bulk_player_logs() -> pd.DataFrame:
    return pf_feat.get_bulk_player_game_logs(season=CURRENT_SEASON)


@st.cache_data(ttl=3600, show_spinner=False)
def _bulk_team_logs() -> pd.DataFrame:
    return pf_feat.get_bulk_team_game_logs(season=CURRENT_SEASON)


@st.cache_data(ttl=3600, show_spinner=False)
def _team_onoff(team_id: int) -> pd.DataFrame:
    """Fetch and process on/off data for a team."""
    return toff.get_team_onoff_formatted(
        team_id, season=CURRENT_SEASON, players_df=_players_df()
    )


@st.cache_data(ttl=3600, show_spinner=False)
def _lineup_data(team_id: int, measure: str) -> pd.DataFrame:
    """Fetch LeagueDashLineups for a team (measure = 'Base' or 'Advanced')."""
    try:
        return endpoints.LeagueDashLineups(
            season=CURRENT_SEASON,
            season_type_all_star='Regular Season',
            measure_type_detailed_defense=measure,
            per_mode_detailed='PerGame',
            group_quantity=5,
            team_id_nullable=team_id,
            timeout=90,
        ).get_data_frames()[0]
    except Exception as e:
        st.warning(f"Could not fetch {measure} lineup data: {e}")
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# Headshot URL
# ---------------------------------------------------------------------------

def _headshot_url(player_id) -> str:
    return f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png"


def _team_logo_url(team_id) -> str:
    return f"https://cdn.nba.com/logos/nba/{team_id}/primary/L/logo.svg"


# ---------------------------------------------------------------------------
# Conditional-formatting helpers  (same style as 1_Teams.py)
# ---------------------------------------------------------------------------

def _rank_color(value: float, min_val: float, max_val: float,
                higher_is_better: bool = True) -> str:
    """Return an rgba CSS string on a green–yellow–red gradient."""
    if pd.isna(value) or max_val == min_val:
        return ""
    normalized = (value - min_val) / (max_val - min_val)
    if not higher_is_better:
        normalized = 1.0 - normalized
    # green ← → red
    if normalized >= 0.5:
        t = (normalized - 0.5) * 2        # 0 → 1
        r, g, b = int(255 * t), 200, 0
    else:
        t = normalized * 2                # 0 → 1
        r, g, b = 255, int(200 * t), 0
    return f"rgba({r}, {g}, {b}, 0.30)"


def _delta_style(df: pd.DataFrame, higher_is_better_cols: list[str],
                 lower_is_better_cols: list[str]):
    """Apply per-cell green/red background styling to delta columns."""
    styles = pd.DataFrame("", index=df.index, columns=df.columns)

    for col in higher_is_better_cols:
        if col not in df.columns:
            continue
        mn, mx = df[col].min(), df[col].max()
        for idx in df.index:
            v = df.at[idx, col]
            if pd.notna(v):
                styles.at[idx, col] = f"background-color: {_rank_color(v, mn, mx, True)}"

    for col in lower_is_better_cols:
        if col not in df.columns:
            continue
        mn, mx = df[col].min(), df[col].max()
        for idx in df.index:
            v = df.at[idx, col]
            if pd.notna(v):
                styles.at[idx, col] = f"background-color: {_rank_color(v, mn, mx, False)}"

    return styles


def _style_delta_row(row, pos_cols, neg_cols):
    """Row-based styler used with df.style.apply(axis=1)."""
    styles = [""] * len(row)
    for i, col in enumerate(row.index):
        val = row[col]
        if not isinstance(val, (int, float)) or pd.isna(val):
            continue
        if col in pos_cols:
            if val > 0:
                styles[i] = "background-color: rgba(0,180,80,0.28)"
            elif val < 0:
                styles[i] = "background-color: rgba(220,50,50,0.28)"
        elif col in neg_cols:
            if val < 0:
                styles[i] = "background-color: rgba(0,180,80,0.28)"
            elif val > 0:
                styles[i] = "background-color: rgba(220,50,50,0.28)"
    return styles


# ---------------------------------------------------------------------------
# Core analysis functions
# ---------------------------------------------------------------------------

def get_current_roster_player_ids(
    team_id: int,
    player_logs: pd.DataFrame,
    team_logs: pd.DataFrame,
    recent_n: int = 15,
) -> set:
    """
    Return player IDs who appeared in at least 1 of the team's most recent N games.
    Filters out traded / waived players who no longer suit up for this team.
    """
    tgl = team_logs[team_logs['TEAM_ID'] == team_id].copy()
    if tgl.empty:
        return set()
    if 'GAME_DATE' in tgl.columns:
        tgl = tgl.sort_values('GAME_DATE', ascending=False)
    recent_ids = set(tgl['GAME_ID'].astype(str).head(recent_n))
    recent_plog = player_logs[
        (player_logs['TEAM_ID'] == team_id) &
        (player_logs['GAME_ID'].astype(str).isin(recent_ids))
    ]
    return set(recent_plog['PLAYER_ID'].unique())


def get_team_roster(team_id: int, players_df: pd.DataFrame,
                    active_player_ids: set | None = None) -> pd.DataFrame:
    """Return roster sorted by AVG_MIN desc, filtered to currently active players."""
    roster = players_df[players_df['TEAM_ID'].astype(int) == team_id].copy()
    if active_player_ids is not None:
        active_ints = {int(p) for p in active_player_ids}
        roster = roster[roster['PERSON_ID'].astype(int).isin(active_ints)]
    if 'AVG_MIN' in roster.columns:
        roster = roster.sort_values('AVG_MIN', ascending=False)
    return roster


def get_missed_game_ids(player_id: int, team_id: int,
                        player_logs: pd.DataFrame,
                        team_logs: pd.DataFrame) -> tuple[set, set]:
    """
    Return (played_game_ids, missed_game_ids) for the player on THIS team this season.
    Filters by TEAM_ID so games played for previous teams are excluded.
    """
    player_games = set(
        player_logs[
            (player_logs['PLAYER_ID'] == player_id) &
            (player_logs['TEAM_ID'] == team_id)
        ]['GAME_ID'].astype(str)
    )
    team_games = set(
        team_logs[team_logs['TEAM_ID'] == team_id]['GAME_ID'].astype(str)
    )
    missed = team_games - player_games
    return player_games, missed


def compute_teammate_impact(
    player_id: int,
    team_id: int,
    player_logs: pd.DataFrame,
    team_logs: pd.DataFrame,
    active_player_ids: set | None = None,
) -> pd.DataFrame:
    """
    For each teammate, compute average stats in games WITH vs WITHOUT the player.
    Returns a DataFrame of deltas sorted by MIN delta descending.
    """
    played_ids, missed_ids = get_missed_game_ids(
        player_id, team_id, player_logs, team_logs
    )
    if len(missed_ids) < 2:
        return pd.DataFrame()

    STAT_COLS = ['MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV',
                 'FGM', 'FGA', 'FG3M', 'FG3A', 'FTM', 'FTA']

    team_player_logs = player_logs[
        (player_logs['TEAM_ID'] == team_id) &
        (player_logs['PLAYER_ID'] != player_id)
    ].copy()

    # Restrict to currently-active players (exclude departed / traded players)
    if active_player_ids is not None:
        active_ints = {int(p) for p in active_player_ids}
        team_player_logs = team_player_logs[
            team_player_logs['PLAYER_ID'].astype(int).isin(active_ints)
        ]

    rows = []
    for pid, grp in team_player_logs.groupby('PLAYER_ID'):
        grp_str = grp.copy()
        grp_str['GAME_ID'] = grp_str['GAME_ID'].astype(str)

        with_player = grp_str[grp_str['GAME_ID'].isin(played_ids)]
        without_player = grp_str[grp_str['GAME_ID'].isin(missed_ids)]

        if len(with_player) < 3 or len(without_player) < 2:
            continue

        avail_cols = [c for c in STAT_COLS if c in grp_str.columns]
        avg_with = with_player[avail_cols].mean()
        avg_without = without_player[avail_cols].mean()
        delta = avg_without - avg_with

        row = {'PLAYER_ID': pid,
               'GP_WITH': len(with_player),
               'GP_WITHOUT': len(without_player)}
        for c in avail_cols:
            row[f'{c}_WITH']    = round(float(avg_with[c]), 2)
            row[f'{c}_WITHOUT'] = round(float(avg_without[c]), 2)
            row[f'{c}_DELTA']   = round(float(delta[c]), 2)
        rows.append(row)

    if not rows:
        return pd.DataFrame()

    result = pd.DataFrame(rows)
    # Add FG% columns if possible
    for pfx in ('WITH', 'WITHOUT'):
        fgm, fga = f'FGM_{pfx}', f'FGA_{pfx}'
        if fgm in result.columns and fga in result.columns:
            result[f'FG_PCT_{pfx}'] = (
                result[fgm] / result[fga].replace(0, np.nan)
            ).round(3)
    if 'FG_PCT_WITH' in result.columns and 'FG_PCT_WITHOUT' in result.columns:
        result['FG_PCT_DELTA'] = (
            result['FG_PCT_WITHOUT'] - result['FG_PCT_WITH']
        ).round(3)

    # Add FG3% columns
    for pfx in ('WITH', 'WITHOUT'):
        fg3m, fg3a = f'FG3M_{pfx}', f'FG3A_{pfx}'
        if fg3m in result.columns and fg3a in result.columns:
            result[f'FG3_PCT_{pfx}'] = (
                result[fg3m] / result[fg3a].replace(0, np.nan)
            ).round(3)
    if 'FG3_PCT_WITH' in result.columns and 'FG3_PCT_WITHOUT' in result.columns:
        result['FG3_PCT_DELTA'] = (
            result['FG3_PCT_WITHOUT'] - result['FG3_PCT_WITH']
        ).round(3)

    # Add FG2% columns: (FGM − FG3M) / (FGA − FG3A)
    for pfx in ('WITH', 'WITHOUT'):
        fgm, fga = f'FGM_{pfx}', f'FGA_{pfx}'
        fg3m, fg3a = f'FG3M_{pfx}', f'FG3A_{pfx}'
        if all(c in result.columns for c in [fgm, fga, fg3m, fg3a]):
            fg2m = result[fgm] - result[fg3m]
            fg2a = result[fga] - result[fg3a]
            result[f'FG2_PCT_{pfx}'] = (fg2m / fg2a.replace(0, np.nan)).round(3)
    if 'FG2_PCT_WITH' in result.columns and 'FG2_PCT_WITHOUT' in result.columns:
        result['FG2_PCT_DELTA'] = (
            result['FG2_PCT_WITHOUT'] - result['FG2_PCT_WITH']
        ).round(3)

    result = result.sort_values('MIN_DELTA', ascending=False)
    return result


def filter_lineups_without_player(lineups_df: pd.DataFrame,
                                  last_name: str,
                                  first_initial: str) -> pd.DataFrame:
    """Remove any lineup that contains the given player."""
    if lineups_df.empty:
        return lineups_df
    desc_col = next(
        (c for c in ('GROUP_NAME', 'DESCRIPTION', 'GROUP_ID') if c in lineups_df.columns),
        None
    )
    if desc_col is None:
        return lineups_df
    pattern = last_name.lower()
    mask = ~lineups_df[desc_col].str.lower().str.contains(pattern, na=False)
    return lineups_df[mask].copy()


# ---------------------------------------------------------------------------
# Altair charts
# ---------------------------------------------------------------------------

def _stat_gainers_bar(
    impact_df: pd.DataFrame,
    players_df: pd.DataFrame,
    stat_col: str,
    label: str,
    min_mpg_without: float = 10.0,
    min_players: int = 7,
    max_players: int = 12,
) -> alt.Chart | None:
    """
    Bar chart showing top gainers for a single stat.
    Only includes players averaging > min_mpg_without MPG when the selected player is out.
    Always shows at least min_players bars (relaxes MPG filter if needed to reach that count).
    """
    if stat_col not in impact_df.columns or 'MIN_WITHOUT' not in impact_df.columns:
        return None

    pinfo = players_df[['PERSON_ID', 'PLAYER_FIRST_NAME', 'PLAYER_LAST_NAME']].copy()
    pinfo['PERSON_ID'] = pinfo['PERSON_ID'].astype(str)

    cols = ['PLAYER_ID', stat_col, 'MIN_WITHOUT']
    bar_df = impact_df[[c for c in cols if c in impact_df.columns]].copy()
    bar_df['PLAYER_ID'] = bar_df['PLAYER_ID'].astype(str)
    bar_df = bar_df.merge(pinfo, left_on='PLAYER_ID', right_on='PERSON_ID', how='left')
    bar_df['Name'] = bar_df['PLAYER_FIRST_NAME'].str[0] + '. ' + bar_df['PLAYER_LAST_NAME']
    bar_df = bar_df.dropna(subset=[stat_col])

    # Apply MPG filter; relax it if fewer than min_players would be shown
    filtered = bar_df[bar_df['MIN_WITHOUT'] > min_mpg_without]
    if len(filtered) < min_players:
        filtered = bar_df   # show all if strict filter yields too few

    filtered = filtered.sort_values(stat_col, ascending=False).head(max_players)
    if filtered.empty:
        return None

    chart_height = max(220, len(filtered) * 36)
    bar = (
        alt.Chart(filtered)
        .mark_bar()
        .encode(
            x=alt.X(f'{stat_col}:Q', title=f'{label} Δ (w/o − w/)'),
            y=alt.Y('Name:N', sort='-x', title=''),
            color=alt.condition(
                alt.datum[stat_col] > 0,
                alt.value('#2ecc71'),
                alt.value('#e74c3c'),
            ),
            tooltip=['Name', stat_col, 'MIN_WITHOUT'],
        )
        .properties(height=chart_height, title=f'{label} Gainers When Player is Out (>10 MPG)')
    )
    return bar


def _minutes_trend_chart(player_id: int, teammate_ids: list,
                         player_logs: pd.DataFrame,
                         player_name: str) -> alt.Chart | None:
    """Line chart: teammate minutes over the season, shading the missed-games window."""
    records = []
    for pid in teammate_ids[:5]:   # top 5 only to keep chart readable
        p_logs = player_logs[player_logs['PLAYER_ID'] == pid].copy()
        if p_logs.empty:
            continue
        p_logs = p_logs.sort_values('GAME_DATE')
        p_logs['game_num'] = range(1, len(p_logs) + 1)
        pname_row = p_logs.iloc[0]
        pname = str(pname_row.get('PLAYER_NAME', pid))
        for _, row in p_logs.iterrows():
            records.append({
                'Player': pname,
                'Game': row['game_num'],
                'MIN': float(row['MIN']) if pd.notna(row['MIN']) else 0,
            })
    if not records:
        return None
    df = pd.DataFrame(records)
    chart = (
        alt.Chart(df)
        .mark_line(point=True)
        .encode(
            x=alt.X('Game:Q', title='Game #'),
            y=alt.Y('MIN:Q', title='Minutes'),
            color=alt.Color('Player:N'),
            tooltip=['Player', 'Game', 'MIN'],
        )
        .properties(height=300, title=f"Teammate Minutes Over Season")
        .interactive()
    )
    return chart


def _onoff_bar_chart(onoff_df: pd.DataFrame, selected_player_id: int) -> alt.Chart | None:
    """Horizontal bar chart: NET_RTG_DIFF for all teammates, highlighting selected player."""
    needed = ['PLAYER_ID', 'PLAYER_NAME', 'NET_RTG_DIFF']
    missing = [c for c in needed if c not in onoff_df.columns]
    # Try to find alternative column names
    col_map = {}
    for need in missing:
        for col in onoff_df.columns:
            if need.replace('_', '').lower() in col.replace('_', '').lower():
                col_map[need] = col
                break

    df = onoff_df.copy()
    for need, found in col_map.items():
        df[need] = df[found]

    needed2 = [c for c in needed if c in df.columns]
    if 'NET_RTG_DIFF' not in df.columns:
        return None

    df = df.dropna(subset=['NET_RTG_DIFF']).copy()
    if df.empty:
        return None

    name_col = next((c for c in ('PLAYER_NAME', 'PLAYER_FIRST_NAME') if c in df.columns), None)
    if name_col is None:
        return None

    # Build display name
    if 'PLAYER_FIRST_NAME' in df.columns and 'PLAYER_LAST_NAME' in df.columns:
        df['Display'] = df['PLAYER_FIRST_NAME'].str[0] + '. ' + df['PLAYER_LAST_NAME']
    else:
        df['Display'] = df[name_col]

    # PLAYER_ID may be absent (format_onoff_display_data strips it).
    # Fall back to VS_PLAYER_ID (raw NBA API column) if present.
    id_col = next(
        (c for c in ('PLAYER_ID', 'VS_PLAYER_ID', 'PLAYER_ID_INT') if c in df.columns),
        None,
    )
    df['is_selected'] = (
        df[id_col].astype(str) == str(selected_player_id)
        if id_col is not None
        else False
    )
    df = df.sort_values('NET_RTG_DIFF', ascending=False).head(15)
    df['_color'] = df.apply(
        lambda r: '#FF4B4B' if r['is_selected']
        else ('#2ecc71' if r['NET_RTG_DIFF'] > 0 else '#e74c3c'), axis=1
    )

    chart = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X('NET_RTG_DIFF:Q', title='Net Rating Differential (On − Off)'),
            y=alt.Y('Display:N', sort='-x', title=''),
            color=alt.Color('_color:N', scale=None, legend=None),
            tooltip=['Display', 'NET_RTG_DIFF'],
        )
        .properties(height=400, title='Net Rating Differential by Player (On − Off)')
    )
    return chart


def _delta_scatter(impact_df: pd.DataFrame, x_col: str, y_col: str,
                   x_label: str, y_label: str,
                   players_df: pd.DataFrame) -> alt.Chart | None:
    """Scatter: any two delta columns, labelled by player name."""
    if x_col not in impact_df.columns or y_col not in impact_df.columns:
        return None
    df = impact_df[[x_col, y_col, 'PLAYER_ID']].dropna().copy()
    if df.empty:
        return None

    # Merge player names + headshot URLs
    name_df = players_df[['PERSON_ID', 'PLAYER_FIRST_NAME', 'PLAYER_LAST_NAME']].copy()
    name_df['PERSON_ID'] = name_df['PERSON_ID'].astype(str)
    df['PLAYER_ID'] = df['PLAYER_ID'].astype(str)
    df = df.merge(name_df, left_on='PLAYER_ID', right_on='PERSON_ID', how='left')
    df['Name'] = df['PLAYER_FIRST_NAME'].str[0] + '. ' + df['PLAYER_LAST_NAME']
    df['headshot_url'] = df['PLAYER_ID'].apply(
        lambda pid: f"https://cdn.nba.com/headshots/nba/latest/1040x760/{pid}.png"
    )

    scatter = (
        alt.Chart(df)
        .mark_image(width=38, height=28)
        .encode(
            x=alt.X(x_col, title=x_label),
            y=alt.Y(y_col, title=y_label),
            url='headshot_url:N',
            tooltip=['Name', x_col, y_col],
        )
        .properties(height=320, title=f'{x_label} vs {y_label} (Δ Without Player)')
        .interactive()
    )
    rule_h = alt.Chart(pd.DataFrame({'y': [0]})).mark_rule(strokeDash=[4, 4], color='#888').encode(y='y:Q')
    rule_v = alt.Chart(pd.DataFrame({'x': [0]})).mark_rule(strokeDash=[4, 4], color='#888').encode(x='x:Q')
    return scatter + rule_h + rule_v


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

def _player_header(player_row: pd.Series, team_row: dict,
                   games_played: int, games_missed: int):
    pid = int(player_row['PERSON_ID'])
    first = player_row.get('PLAYER_FIRST_NAME', '')
    last = player_row.get('PLAYER_LAST_NAME', '')
    full_name = f"{first} {last}".strip()
    position = player_row.get('POSITION', '')
    jersey = player_row.get('JERSEY_NUMBER', '')

    headshot = _headshot_url(pid)
    team_logo = _team_logo_url(team_row['id'])

    col_img, col_info, col_logo = st.columns([1, 4, 1])
    with col_img:
        st.markdown(
            f"""
            <div style="text-align:center;">
              <img src="{headshot}"
                   style="width:180px; height:135px; object-fit:cover;
                          border-radius:10px; border:2px solid #ddd;"
                   onerror="this.style.display='none'">
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_info:
        st.markdown(f"## {full_name}")
        st.markdown(
            f"**{team_row['full_name']}** &nbsp;|&nbsp; "
            f"#{jersey} &nbsp;|&nbsp; {position}",
            unsafe_allow_html=True,
        )
        gp_color = '#2ecc71' if games_missed > 0 else '#888'
        missed_label = (
            f'<span style="color:{gp_color};font-weight:bold;">'
            f'{games_missed} games missed</span>'
        )
        st.markdown(
            f"{games_played} games played this season &nbsp;|&nbsp; {missed_label}",
            unsafe_allow_html=True,
        )
    with col_logo:
        st.markdown(
            f"""
            <div style="text-align:center;">
              <img src="{team_logo}"
                   style="width:60px; height:60px; object-fit:contain;"
                   onerror="this.style.display='none'">
            </div>
            """,
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Display sections
# ---------------------------------------------------------------------------

def _display_teammate_impact(impact_df: pd.DataFrame, players_df: pd.DataFrame):
    if impact_df.empty:
        st.info("Not enough games missed to compute teammate impact (need ≥ 2 games out).")
        return

    # Merge player info
    pinfo = players_df[['PERSON_ID', 'PLAYER_FIRST_NAME', 'PLAYER_LAST_NAME']].copy()
    pinfo['PERSON_ID'] = pinfo['PERSON_ID'].astype(str)
    df = impact_df.copy()
    df['PLAYER_ID'] = df['PLAYER_ID'].astype(str)
    df = df.merge(pinfo, left_on='PLAYER_ID', right_on='PERSON_ID', how='left')
    df['HEADSHOT'] = df['PLAYER_ID'].apply(_headshot_url)
    df['Player'] = df['PLAYER_FIRST_NAME'].str[0] + '. ' + df['PLAYER_LAST_NAME']

    # --- Summary cards: top 5 minute gainers ---
    st.markdown("#### Biggest Minute Gainers")
    top5 = df.head(5)
    cols = st.columns(5)
    for i, (_, row) in enumerate(top5.iterrows()):
        with cols[i]:
            def _cl(v): return '#2ecc71' if v > 0 else ('#e74c3c' if v < 0 else '#888')
            def _sg(v): return '+' if v > 0 else ''

            min_d = row.get('MIN_DELTA', 0) or 0
            pts_d = row.get('PTS_DELTA', 0) or 0
            reb_d = row.get('REB_DELTA', 0) or 0
            ast_d = row.get('AST_DELTA', 0) or 0

            fg_w   = row.get('FG_PCT_WITH',  np.nan)
            fg_wo  = row.get('FG_PCT_WITHOUT', np.nan)
            fg2_w  = row.get('FG2_PCT_WITH',  np.nan)
            fg2_wo = row.get('FG2_PCT_WITHOUT', np.nan)
            fg3_w  = row.get('FG3_PCT_WITH',  np.nan)
            fg3_wo = row.get('FG3_PCT_WITHOUT', np.nan)

            def _pct(w, wo):
                if pd.isna(w) or pd.isna(wo):
                    return '—'
                return f'{w:.1%} → {wo:.1%}'

            st.markdown(
                f"""
                <div style="border:1px solid #ddd; border-radius:10px;
                            padding:10px; text-align:center; background:#fafafa;">
                  <img src="{row['HEADSHOT']}"
                       style="width:70px; height:52px; object-fit:cover;
                              border-radius:6px;"
                       onerror="this.style.display='none'"><br>
                  <strong style="font-size:0.88em;">{row['Player']}</strong><br>
                  <span style="font-size:1.15em; color:{_cl(min_d)}; font-weight:bold;">
                    {_sg(min_d)}{min_d:.1f} MIN
                  </span><br>
                  <span style="color:#555; font-size:0.78em;">
                    {row.get('MIN_WITH', 0):.1f} → {row.get('MIN_WITHOUT', 0):.1f} min
                  </span><br>
                  <span style="color:{_cl(pts_d)}; font-size:0.83em;">PTS: {_sg(pts_d)}{pts_d:.1f}</span>
                  <span style="color:{_cl(reb_d)}; font-size:0.83em;"> · REB: {_sg(reb_d)}{reb_d:.1f}</span><br>
                  <span style="color:{_cl(ast_d)}; font-size:0.83em;">AST: {_sg(ast_d)}{ast_d:.1f}</span><br>
                  <span style="color:#555; font-size:0.76em;">FG: {_pct(fg_w, fg_wo)}</span><br>
                  <span style="color:#555; font-size:0.76em;">2P: {_pct(fg2_w, fg2_wo)}</span><br>
                  <span style="color:#555; font-size:0.76em;">3P: {_pct(fg3_w, fg3_wo)}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("---")
    st.markdown("#### Full Teammate Impact Table")

    # Build display table
    display_cols_base = ['Player', 'GP_WITH', 'GP_WITHOUT',
                         'MIN_WITH', 'MIN_WITHOUT', 'MIN_DELTA',
                         'PTS_WITH', 'PTS_WITHOUT', 'PTS_DELTA',
                         'REB_WITH', 'REB_WITHOUT', 'REB_DELTA',
                         'AST_WITH', 'AST_WITHOUT', 'AST_DELTA',
                         'FG_PCT_WITH', 'FG_PCT_WITHOUT', 'FG_PCT_DELTA']
    display_cols = [c for c in display_cols_base if c in df.columns]
    display_cols = ['HEADSHOT'] + display_cols
    tbl = df[display_cols].copy()

    delta_pos_cols = ['MIN_DELTA', 'PTS_DELTA', 'REB_DELTA', 'AST_DELTA', 'FG_PCT_DELTA']
    delta_neg_cols: list = []

    def _row_style(row):
        return _style_delta_row(row, delta_pos_cols, delta_neg_cols)

    styled = (
        tbl.style
        .apply(_row_style, axis=1)
        .format({
            'MIN_WITH': '{:.1f}', 'MIN_WITHOUT': '{:.1f}', 'MIN_DELTA': '{:+.1f}',
            'PTS_WITH': '{:.1f}', 'PTS_WITHOUT': '{:.1f}', 'PTS_DELTA': '{:+.1f}',
            'REB_WITH': '{:.1f}', 'REB_WITHOUT': '{:.1f}', 'REB_DELTA': '{:+.1f}',
            'AST_WITH': '{:.1f}', 'AST_WITHOUT': '{:.1f}', 'AST_DELTA': '{:+.1f}',
            'FG_PCT_WITH': '{:.3f}', 'FG_PCT_WITHOUT': '{:.3f}', 'FG_PCT_DELTA': '{:+.3f}',
        }, na_rep='—')
    )

    col_cfg = {
        'HEADSHOT': st.column_config.ImageColumn('', width=50),
        'Player': st.column_config.TextColumn('Player', width=130),
        'GP_WITH': st.column_config.NumberColumn('GP w/', width=60),
        'GP_WITHOUT': st.column_config.NumberColumn('GP w/o', width=65),
        'MIN_WITH': st.column_config.NumberColumn('MIN w/', width=75),
        'MIN_WITHOUT': st.column_config.NumberColumn('MIN w/o', width=80),
        'MIN_DELTA': st.column_config.NumberColumn('MIN Δ', width=70),
        'PTS_WITH': st.column_config.NumberColumn('PTS w/', width=75),
        'PTS_WITHOUT': st.column_config.NumberColumn('PTS w/o', width=80),
        'PTS_DELTA': st.column_config.NumberColumn('PTS Δ', width=70),
        'REB_WITH': st.column_config.NumberColumn('REB w/', width=75),
        'REB_WITHOUT': st.column_config.NumberColumn('REB w/o', width=80),
        'REB_DELTA': st.column_config.NumberColumn('REB Δ', width=70),
        'AST_WITH': st.column_config.NumberColumn('AST w/', width=75),
        'AST_WITHOUT': st.column_config.NumberColumn('AST w/o', width=80),
        'AST_DELTA': st.column_config.NumberColumn('AST Δ', width=70),
        'FG_PCT_WITH': st.column_config.NumberColumn('FG% w/', width=80, format='%.3f'),
        'FG_PCT_WITHOUT': st.column_config.NumberColumn('FG% w/o', width=80, format='%.3f'),
        'FG_PCT_DELTA': st.column_config.NumberColumn('FG% Δ', width=75, format='%.3f'),
    }

    st.dataframe(styled, hide_index=True, use_container_width=True, column_config=col_cfg)

    # Scatter chart: MIN vs PTS delta
    st.markdown("#### Minutes vs Points Delta")
    scatter = _delta_scatter(impact_df, 'MIN_DELTA', 'PTS_DELTA',
                             'MIN Δ', 'PTS Δ', players_df)
    if scatter:
        st.altair_chart(scatter, width='stretch')


def _display_onoff(onoff_df: pd.DataFrame, selected_player_id: int,
                   selected_player_name: str):
    if onoff_df is None or onoff_df.empty:
        st.info("On/off data not available for this team.")
        return

    # Bar chart
    chart = _onoff_bar_chart(onoff_df, selected_player_id)
    if chart:
        st.altair_chart(chart, width='stretch')

    # Highlight selected player row
    st.markdown("#### On/Off Ratings Table")
    df = onoff_df.copy()

    # Normalise column names for display
    rename = {}
    for col in df.columns:
        cu = col.upper()
        if 'FIRST' in cu and 'NAME' in cu:
            rename[col] = 'First'
        elif 'LAST' in cu and 'NAME' in cu:
            rename[col] = 'Last'
    if rename:
        df = df.rename(columns=rename)
    if 'First' in df.columns and 'Last' in df.columns:
        df.insert(0, 'Player', df['First'].str[0] + '. ' + df['Last'])
        df.drop(columns=['First', 'Last'], inplace=True, errors='ignore')

    # Add headshots
    if 'PLAYER_ID' in df.columns:
        df.insert(0, 'HEADSHOT', df['PLAYER_ID'].astype(str).apply(_headshot_url))

    # Identify delta columns
    diff_cols = [c for c in df.columns if '_DIFF' in c.upper() or 'DIFF' in c]
    pos_good = [c for c in diff_cols if 'NET' in c.upper() or 'OFF_RT' in c.upper() or 'PLUS' in c.upper()]
    neg_good = [c for c in diff_cols if 'DEF_RT' in c.upper()]

    def _onoff_row_style(row):
        return _style_delta_row(row, pos_good, neg_good)

    # Select display columns
    keep = ['HEADSHOT', 'Player'] if 'Player' in df.columns else ['HEADSHOT']
    keep += [c for c in df.columns if any(k in c.upper() for k in
             ('NET_RTG', 'OFF_RTG', 'DEF_RTG', 'PLUS_MINUS', 'MIN')) and c not in keep]
    display_df = df[[c for c in keep if c in df.columns]].copy()

    # Highlight selected player
    if 'PLAYER_ID' in df.columns:
        is_selected = df['PLAYER_ID'].astype(str) == str(selected_player_id)
        row_bg = is_selected.map(
            lambda x: 'background-color: rgba(255,75,75,0.15)' if x else ''
        )

        def _combined_style(row):
            base = _onoff_row_style(row)
            idx = row.name
            if idx in df.index and is_selected.iloc[
                df.index.get_loc(idx) if hasattr(df.index, 'get_loc') else idx
            ]:
                return ['background-color: rgba(255,75,75,0.15)'] * len(row)
            return base
    else:
        _combined_style = _onoff_row_style

    col_cfg = {}
    if 'HEADSHOT' in display_df.columns:
        col_cfg['HEADSHOT'] = st.column_config.ImageColumn('', width=50)
    if 'Player' in display_df.columns:
        col_cfg['Player'] = st.column_config.TextColumn('Player', width=140)

    fmt = {}
    for col in display_df.columns:
        if col in ('HEADSHOT', 'Player', 'PLAYER_ID'):
            continue
        if 'MIN' in col.upper():
            fmt[col] = '{:.1f}'
        elif any(k in col.upper() for k in ('RTG', 'PLUS')):
            fmt[col] = '{:+.1f}'

    styled = display_df.style.apply(_onoff_row_style, axis=1).format(fmt, na_rep='—')
    st.dataframe(styled, hide_index=True, use_container_width=True, column_config=col_cfg)

    # Callout for selected player's specific on/off line
    if 'PLAYER_ID' in df.columns:
        player_row = df[df['PLAYER_ID'].astype(str) == str(selected_player_id)]
        if not player_row.empty:
            pr = player_row.iloc[0]
            net_col = next((c for c in df.columns if 'NET_RTG_DIFF' in c.upper() or ('NET' in c.upper() and 'DIFF' in c.upper())), None)
            off_col = next((c for c in df.columns if 'OFF_RTG_DIFF' in c.upper()), None)
            def_col = next((c for c in df.columns if 'DEF_RTG_DIFF' in c.upper()), None)

            if net_col or off_col or def_col:
                st.markdown(f"#### {selected_player_name}'s On/Off Impact")
                m1, m2, m3 = st.columns(3)
                if net_col and pd.notna(pr.get(net_col)):
                    v = pr[net_col]
                    color = '#2ecc71' if v > 0 else '#e74c3c'
                    m1.markdown(
                        f"<div style='text-align:center'>"
                        f"<div style='font-size:0.8em;color:#888'>Net Rating Δ</div>"
                        f"<div style='font-size:1.6em;font-weight:bold;color:{color}'>{v:+.1f}</div>"
                        f"</div>", unsafe_allow_html=True)
                if off_col and pd.notna(pr.get(off_col)):
                    v = pr[off_col]
                    color = '#2ecc71' if v > 0 else '#e74c3c'
                    m2.markdown(
                        f"<div style='text-align:center'>"
                        f"<div style='font-size:0.8em;color:#888'>Offensive Rtg Δ</div>"
                        f"<div style='font-size:1.6em;font-weight:bold;color:{color}'>{v:+.1f}</div>"
                        f"</div>", unsafe_allow_html=True)
                if def_col and pd.notna(pr.get(def_col)):
                    v = pr[def_col]
                    color = '#2ecc71' if v < 0 else '#e74c3c'   # lower DefRtg = better
                    m3.markdown(
                        f"<div style='text-align:center'>"
                        f"<div style='font-size:0.8em;color:#888'>Defensive Rtg Δ</div>"
                        f"<div style='font-size:1.6em;font-weight:bold;color:{color}'>{v:+.1f}</div>"
                        f"</div>", unsafe_allow_html=True)


def _display_lineups(base_df: pd.DataFrame, adv_df: pd.DataFrame,
                     last_name: str, first_initial: str):
    base_filtered = filter_lineups_without_player(base_df, last_name, first_initial)
    adv_filtered  = filter_lineups_without_player(adv_df,  last_name, first_initial)

    if base_filtered.empty and adv_filtered.empty:
        st.info("No lineup data available.")
        return

    name_col = next(
        (c for c in ('GROUP_NAME', 'DESCRIPTION') if c in base_filtered.columns),
        None
    )

    st.markdown("#### Traditional Stats — Lineups Without This Player")
    if not base_filtered.empty:
        trad_keep = [c for c in
                     [name_col, 'GP', 'W', 'L', 'W_PCT', 'MIN',
                      'PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV',
                      'FGM', 'FGA', 'FG_PCT', 'FG3_PCT', 'FT_PCT', 'PLUS_MINUS']
                     if c in base_filtered.columns]
        trad_df = base_filtered[trad_keep].sort_values('MIN', ascending=False).head(20)

        pos_good_trad = ['W_PCT', 'PTS', 'REB', 'AST', 'STL', 'BLK',
                         'FG_PCT', 'FG3_PCT', 'FT_PCT', 'PLUS_MINUS']
        neg_good_trad = ['TOV']

        def _trad_style(row):
            return _style_delta_row(row, pos_good_trad, neg_good_trad)

        fmt_trad = {}
        for c in trad_df.columns:
            if c in ('W_PCT', 'FG_PCT', 'FG3_PCT', 'FT_PCT'):
                fmt_trad[c] = '{:.3f}'
            elif c == 'PLUS_MINUS':
                fmt_trad[c] = '{:+.1f}'
            elif c not in (name_col, 'GP', 'W', 'L'):
                fmt_trad[c] = '{:.1f}'

        col_cfg_trad = {}
        if name_col:
            col_cfg_trad[name_col] = st.column_config.TextColumn('Lineup', width=340)
        col_cfg_trad['GP']   = st.column_config.NumberColumn('GP',    width=50)
        col_cfg_trad['MIN']  = st.column_config.NumberColumn('MIN',   width=65, format='%.1f')
        col_cfg_trad['PTS']  = st.column_config.NumberColumn('PTS',   width=65, format='%.1f')
        col_cfg_trad['PLUS_MINUS'] = st.column_config.NumberColumn('+/-', width=65)

        styled_trad = trad_df.style.apply(_trad_style, axis=1).format(fmt_trad, na_rep='—')
        st.dataframe(styled_trad, hide_index=True, use_container_width=True,
                     column_config=col_cfg_trad)
    else:
        st.info("No traditional lineup data.")

    st.markdown("#### Advanced Stats — Lineups Without This Player")
    if not adv_filtered.empty:
        adv_keep = [c for c in
                    [name_col, 'GP', 'MIN',
                     'OFF_RATING', 'DEF_RATING', 'NET_RATING',
                     'EFG_PCT', 'TS_PCT', 'AST_PCT', 'AST_TO',
                     'OREB_PCT', 'DREB_PCT', 'TM_TOV_PCT', 'PACE', 'PIE']
                    if c in adv_filtered.columns]
        adv_tbl = adv_filtered[adv_keep].sort_values('MIN', ascending=False).head(20)

        pos_good_adv = ['OFF_RATING', 'NET_RATING', 'EFG_PCT', 'TS_PCT',
                        'AST_PCT', 'AST_TO', 'OREB_PCT', 'DREB_PCT', 'PIE']
        neg_good_adv = ['DEF_RATING', 'TM_TOV_PCT']

        def _adv_style(row):
            return _style_delta_row(row, pos_good_adv, neg_good_adv)

        fmt_adv = {}
        for c in adv_tbl.columns:
            if c in ('EFG_PCT', 'TS_PCT', 'AST_PCT', 'OREB_PCT', 'DREB_PCT', 'TM_TOV_PCT'):
                fmt_adv[c] = '{:.3f}'
            elif c == 'AST_TO':
                fmt_adv[c] = '{:.2f}'
            elif c not in (name_col, 'GP'):
                fmt_adv[c] = '{:.1f}'

        col_cfg_adv = {}
        if name_col:
            col_cfg_adv[name_col] = st.column_config.TextColumn('Lineup', width=340)
        col_cfg_adv['NET_RATING'] = st.column_config.NumberColumn('NET RTG', width=80, format='%.1f')
        col_cfg_adv['OFF_RATING'] = st.column_config.NumberColumn('OFF RTG', width=80, format='%.1f')
        col_cfg_adv['DEF_RATING'] = st.column_config.NumberColumn('DEF RTG', width=80, format='%.1f')
        col_cfg_adv['PACE']       = st.column_config.NumberColumn('PACE',    width=70, format='%.1f')

        styled_adv = adv_tbl.style.apply(_adv_style, axis=1).format(fmt_adv, na_rep='—')
        st.dataframe(styled_adv, hide_index=True, use_container_width=True,
                     column_config=col_cfg_adv)

        # Net Rating bar chart for top lineups
        if 'NET_RATING' in adv_tbl.columns and name_col in adv_tbl.columns:
            chart_df = adv_tbl[[name_col, 'NET_RATING', 'MIN']].dropna().head(12)
            bar = (
                alt.Chart(chart_df)
                .mark_bar()
                .encode(
                    x=alt.X('NET_RATING:Q', title='Net Rating'),
                    y=alt.Y(f'{name_col}:N', sort='-x', title=''),
                    color=alt.condition(
                        alt.datum.NET_RATING >= 0,
                        alt.value('#2ecc71'),
                        alt.value('#e74c3c'),
                    ),
                    tooltip=[name_col, 'NET_RATING', 'MIN'],
                )
                .properties(height=320, title='Net Rating — Top Lineups Without Player')
            )
            st.altair_chart(bar, width='stretch')
    else:
        st.info("No advanced lineup data.")


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------

def main():
    st.markdown(
        "<h1 style='margin-bottom:0'>🏥 Injury Impact Analysis</h1>"
        "<p style='color:#888; margin-top:4px'>Who benefits when a player misses games?</p>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    all_teams = _all_nba_teams()

    # Load season logs early (cached — no API penalty after first load).
    # Needed before the sidebar so we can filter to the current roster.
    with st.spinner("Loading season data…"):
        player_logs = _bulk_player_logs()
        team_logs   = _bulk_team_logs()

    if player_logs.empty or team_logs.empty:
        st.error("Could not load game log data.")
        return

    # ---- Sidebar ----
    with st.sidebar:
        st.markdown("### Select Team & Player")

        team_names = [t['full_name'] for t in all_teams]
        # Default to Timberwolves
        default_team_idx = next(
            (i for i, t in enumerate(all_teams) if t['id'] == 1610612750), 0
        )
        selected_team_name = st.selectbox("Team", team_names, index=default_team_idx)
        team_row = next(t for t in all_teams if t['full_name'] == selected_team_name)
        team_id = team_row['id']

        players_df = _players_df()
        # Filter to players who actually appeared in the team's last 15 games
        active_player_ids = get_current_roster_player_ids(team_id, player_logs, team_logs)
        roster = get_team_roster(team_id, players_df, active_player_ids)

        if roster.empty:
            st.warning("Could not load roster for this team.")
            return

        player_options = []
        for _, row in roster.iterrows():
            first = row.get('PLAYER_FIRST_NAME', '')
            last  = row.get('PLAYER_LAST_NAME', '')
            player_options.append(f"{first} {last}".strip())

        selected_player_name = st.selectbox("Player", player_options)

        st.markdown("---")
        st.caption(f"Season: {CURRENT_SEASON}")
        if st.button("🗑️ Clear Cache"):
            st.cache_data.clear()
            st.rerun()

    # ---- Resolve selected player ----
    player_row = None
    for _, row in roster.iterrows():
        fn = row.get('PLAYER_FIRST_NAME', '')
        ln = row.get('PLAYER_LAST_NAME', '')
        if f"{fn} {ln}".strip() == selected_player_name:
            player_row = row
            break

    if player_row is None:
        st.error("Player not found.")
        return

    player_id = int(player_row['PERSON_ID'])
    first_name = player_row.get('PLAYER_FIRST_NAME', '')
    last_name  = player_row.get('PLAYER_LAST_NAME', '')
    first_initial = first_name[0] if first_name else ''

    played_ids, missed_ids = get_missed_game_ids(
        player_id, team_id, player_logs, team_logs
    )

    # ---- Header ----
    _player_header(player_row, team_row, len(played_ids), len(missed_ids))
    st.markdown("---")

    # ---- Tabs ----
    tab1, tab2, tab3, tab4 = st.tabs([
        "👥 Teammate Impact",
        "📊 On/Off Splits",
        "📋 Lineups Without",
        "📈 Charts",
    ])

    # ----  Tab 1: Teammate impact ----
    with tab1:
        st.markdown(
            f"### When **{selected_player_name}** misses games, who steps up?"
        )
        if len(missed_ids) < 2:
            st.info(
                f"{selected_player_name} has missed fewer than 2 games this season. "
                "No meaningful comparison available yet."
            )
        else:
            with st.spinner("Computing teammate stats…"):
                impact_df = compute_teammate_impact(
                    player_id, team_id, player_logs, team_logs,
                    active_player_ids=active_player_ids,
                )
            _display_teammate_impact(impact_df, players_df)

    # ---- Tab 2: On/Off ----
    with tab2:
        st.markdown(f"### Team On/Off Ratings — {selected_player_name} highlighted")
        with st.spinner("Loading on/off data…"):
            onoff_df = _team_onoff(team_id)
        _display_onoff(onoff_df, player_id, selected_player_name)

    # ---- Tab 3: Lineups ----
    with tab3:
        st.markdown(
            f"### Best 5-Man Lineups That Don't Include **{selected_player_name}**"
        )
        with st.spinner("Loading lineup data…"):
            base_df = _lineup_data(team_id, 'Base')
            adv_df  = _lineup_data(team_id, 'Advanced')
        _display_lineups(base_df, adv_df, last_name, first_initial)

    # ---- Tab 4: Charts ----
    with tab4:
        st.markdown(f"### Teammate Stats — With vs Without **{selected_player_name}**")
        if len(missed_ids) < 2:
            st.info("Insufficient missed games for chart analysis.")
        else:
            with st.spinner("Building charts…"):
                impact_df = compute_teammate_impact(
                    player_id, team_id, player_logs, team_logs,
                    active_player_ids=active_player_ids,
                )
            if impact_df.empty:
                st.info("No chart data available.")
            else:
                c1, c2 = st.columns(2)
                with c1:
                    sc1 = _delta_scatter(impact_df, 'MIN_DELTA', 'PTS_DELTA',
                                        'MIN Δ', 'PTS Δ', players_df)
                    if sc1:
                        st.altair_chart(sc1, width='stretch')
                with c2:
                    sc2 = _delta_scatter(impact_df, 'MIN_DELTA', 'AST_DELTA',
                                        'MIN Δ', 'AST Δ', players_df)
                    if sc2:
                        st.altair_chart(sc2, width='stretch')

                c3, c4 = st.columns(2)
                with c3:
                    sc3 = _delta_scatter(impact_df, 'MIN_DELTA', 'REB_DELTA',
                                        'MIN Δ', 'REB Δ', players_df)
                    if sc3:
                        st.altair_chart(sc3, width='stretch')
                with c4:
                    sc4 = _delta_scatter(impact_df, 'PTS_DELTA', 'FG_PCT_DELTA',
                                        'PTS Δ', 'FG% Δ', players_df)
                    if sc4:
                        st.altair_chart(sc4, width='stretch')

                # Bar chart: top MIN gainers
                if 'MIN_DELTA' in impact_df.columns and 'PLAYER_ID' in impact_df.columns:
                    pinfo = players_df[['PERSON_ID', 'PLAYER_FIRST_NAME', 'PLAYER_LAST_NAME']].copy()
                    pinfo['PERSON_ID'] = pinfo['PERSON_ID'].astype(str)
                    bar_df = impact_df.copy()
                    bar_df['PLAYER_ID'] = bar_df['PLAYER_ID'].astype(str)
                    bar_df = bar_df.merge(pinfo, left_on='PLAYER_ID', right_on='PERSON_ID', how='left')
                    bar_df['Name'] = bar_df['PLAYER_FIRST_NAME'].str[0] + '. ' + bar_df['PLAYER_LAST_NAME']
                    bar_df = bar_df.dropna(subset=['MIN_DELTA']).sort_values('MIN_DELTA', ascending=False).head(10)

                    bar = (
                        alt.Chart(bar_df)
                        .mark_bar()
                        .encode(
                            x=alt.X('MIN_DELTA:Q', title='Minutes Delta (w/o − w/)'),
                            y=alt.Y('Name:N', sort='-x', title=''),
                            color=alt.condition(
                                alt.datum.MIN_DELTA > 0,
                                alt.value('#2ecc71'),
                                alt.value('#e74c3c'),
                            ),
                            tooltip=['Name', 'MIN_DELTA', 'PTS_DELTA'],
                        )
                        .properties(
                            height=320,
                            title=f'Minute Gainers When {selected_player_name} is Out',
                        )
                    )
                    st.altair_chart(bar, width='stretch')

                # --- Additional stat gainers (2x2 grid) ---
                st.markdown("#### Stat Gainers")
                ga1, ga2 = st.columns(2)
                with ga1:
                    pts_bar = _stat_gainers_bar(impact_df, players_df, 'PTS_DELTA', 'Points')
                    if pts_bar:
                        st.altair_chart(pts_bar, width='stretch')
                with ga2:
                    reb_bar = _stat_gainers_bar(impact_df, players_df, 'REB_DELTA', 'Rebounds')
                    if reb_bar:
                        st.altair_chart(reb_bar, width='stretch')

                ga3, ga4 = st.columns(2)
                with ga3:
                    ast_bar = _stat_gainers_bar(impact_df, players_df, 'AST_DELTA', 'Assists')
                    if ast_bar:
                        st.altair_chart(ast_bar, width='stretch')
                with ga4:
                    fga_bar = _stat_gainers_bar(impact_df, players_df, 'FGA_DELTA', 'FG Attempts')
                    if fga_bar:
                        st.altair_chart(fga_bar, width='stretch')


if __name__ == '__main__':
    main()
