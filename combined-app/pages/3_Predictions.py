import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'player_app'))
import tanking_utils as _tu

import streamlit as st
import player_functions as pf
import team_defensive_stats as tds
import prediction_model as pm
import prediction_features as pf_features
import matchup_stats as ms
import vegas_lines as vl
import prediction_tracker as pt
import parlay_tracker as ptl
import injury_adjustments as inj
import without_player_stats as wps
import backtest as bt
import injury_report as ir
import player_similarity as ps
import pandas as pd
import nba_api.stats.endpoints
from datetime import datetime, date, timedelta
import math
import requests
import prediction_store
from theme_colors import tc


def _resolve_player_id(player_name: str) -> str:
    """Try to resolve a display name to an NBA API numeric player ID."""
    try:
        from nba_api.stats.static import players as _nba_players
        matches = _nba_players.find_players_by_full_name(player_name)
        if matches:
            return str(matches[0]['id'])
    except Exception:
        pass
    return player_name.lower().replace(' ', '_')


def _returning_ids_from_injury_dict(injury_dict):
    """Extract player IDs listed as probable or questionable (i.e. returning, not out)."""
    ids = set()
    for side in ('away', 'home'):
        for item in injury_dict.get(side, []):
            status = (item.get('status') or '').lower()
            if ('probable' in status or 'questionable' in status) and item.get('player_id'):
                ids.add(str(item['player_id']))
    return ids


_PLAY_STAT_LABELS = {
    'PTS': 'Points', 'REB': 'Rebounds', 'AST': 'Assists',
    'STL': 'Steals', 'BLK': 'Blocks', 'TOV': 'Turnovers',
    'FG3M': '3-Pointers Made', 'FTM': 'Free Throws Made',
    'PRA': 'Pts+Reb+Ast', 'RA': 'Reb+Ast', 'MIN': 'Minutes',
}


def _render_leg_with_l5(leg: dict, bulk_logs):
    """Render a play leg as an expander showing Players-page-style averages + game logs."""
    _stat  = leg.get('stat', '')
    _lc    = tc.green_bg if 'Over' in leg.get('lean', '') else tc.red_bg
    _lt    = tc.green_text if 'Over' in leg.get('lean', '') else tc.red_text
    _slbl  = _PLAY_STAT_LABELS.get(_stat, _stat)
    _opp   = leg.get('opponent', '')
    _ostr  = f" vs {_opp}" if _opp else ''
    _pred  = round(float(leg.get('prediction', 0)), 1)
    _line  = round(float(leg.get('line', 0)), 1)
    _edge  = leg.get('edge_pct', 0)

    _exp_label = (
        f"{leg.get('player_name', '')}  ({leg.get('team', '')}{_ostr})"
        f"  ·  {_slbl} {leg.get('lean', '')}"
        f"  ·  Pred {_pred} / Line {_line}"
        f"  ·  {_edge:+.1f}%"
    )

    with st.expander(_exp_label, expanded=False):
        st.markdown(
            f'<div style="background:{_lc};border-radius:6px;padding:8px 14px;margin:4px 0 8px 0;">'
            f'<strong>{leg.get("player_name", "")}</strong>'
            f' <span style="color:{tc.text_secondary};">({leg.get("team", "")}{_ostr})</span>'
            f' &nbsp;·&nbsp; <strong>{_slbl}</strong> {leg.get("lean", "")}'
            f' &nbsp;·&nbsp; Pred <strong>{_pred}</strong> / Line {_line}'
            f' &nbsp;·&nbsp; <span style="color:{_lt};font-weight:600;">{_edge:+.1f}%</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        _pid = str(leg.get('player_id', ''))
        if not _pid or bulk_logs is None or len(bulk_logs) == 0:
            return

        try:
            _plogs = pf_features.get_player_logs_from_bulk(_pid, bulk_logs)
            if len(_plogs) == 0:
                return

            # ── Build averages from raw logs (Players-page style) ───────────
            def _compute_period_stats(df):
                if len(df) == 0:
                    return None
                def _smean(col):
                    return df[col].astype(float).mean() if col in df.columns else 0.0
                fgm  = _smean('FGM');  fg3m = _smean('FG3M')
                fga  = _smean('FGA');  fg3a = _smean('FG3A')
                ftm  = _smean('FTM');  fta  = _smean('FTA')
                pts  = _smean('PTS');  reb  = _smean('REB')
                ast  = _smean('AST');  stl  = _smean('STL')
                blk  = _smean('BLK');  tov  = _smean('TOV')
                mins = _smean('MIN')
                two_pm = fgm - fg3m;   two_pa = fga - fg3a
                pra    = pts + reb + ast
                fp     = pts * 1.0 + reb * 1.2 + ast * 1.5 + stl * 3.0 + blk * 3.0 - tov * 1.0
                return {
                    'MIN': mins, 'PTS': pts, 'REB': reb, 'AST': ast, 'PRA': pra,
                    'STL': stl, 'BLK': blk, 'TOV': tov, 'FP': fp,
                    '2PM': two_pm, '2PA': two_pa, '3PM': fg3m, '3PA': fg3a,
                    'FTM': ftm, 'FTA': fta,
                    '2P%': (two_pm / two_pa * 100) if two_pa > 0 else 0.0,
                    '3P%': (fg3m / fg3a * 100) if fg3a > 0 else 0.0,
                    'FT%': (ftm / fta * 100) if fta > 0 else 0.0,
                }

            _periods = [('L3', _plogs.head(3)), ('L5', _plogs.head(5)),
                        ('L10', _plogs.head(10)), ('Season', _plogs)]
            avg_rows = []
            stats_by_period = {}
            _avg_num_cols = ['MIN', 'PTS', 'REB', 'AST', 'PRA', 'STL', 'BLK', 'TOV', '2PM', '2PA', '3PM', '3PA', 'FTM', 'FTA']
            _pct_cols     = ['2P%', '3P%', 'FT%']

            for _lbl, _df in _periods:
                _s = _compute_period_stats(_df)
                if _s:
                    stats_by_period[_lbl] = _s
                    _r = {'Period': _lbl}
                    for _c in _avg_num_cols:
                        _r[_c] = f"{_s[_c]:.1f}"
                    for _c in _pct_cols:
                        _r[_c] = f"{_s[_c]:.1f}%"
                    avg_rows.append(_r)

            if avg_rows:
                _avg_df = pd.DataFrame(avg_rows)
                _szn_idx = len(_avg_df) - 1
                _szn_row = _avg_df.iloc[_szn_idx]

                def _heatmap_style(row, df_ref, szn_ref):
                    styles = [''] * len(row)
                    for i, col in enumerate(df_ref.columns):
                        if col == 'Period' or '+/-' in col:
                            continue
                        try:
                            if col in _avg_num_cols:
                                cv = float(str(row[col]).replace(',', ''))
                                sv = float(str(szn_ref[col]).replace(',', ''))
                            elif col in _pct_cols:
                                cv = float(str(row[col]).replace('%', ''))
                                sv = float(str(szn_ref[col]).replace('%', ''))
                            else:
                                continue
                            if cv > sv:
                                dp = ((cv - sv) / sv * 100) if sv > 0 else 0
                                styles[i] = f'background-color: {tc.heatmap_green(dp / 20)};'
                            elif cv < sv:
                                dp = ((sv - cv) / sv * 100) if sv > 0 else 0
                                styles[i] = f'background-color: {tc.heatmap_red(dp / 20)};'
                            else:
                                styles[i] = f'background-color: {tc.heatmap_neutral};'
                        except (ValueError, TypeError):
                            pass
                    return styles

                st.markdown("**Averages**")
                _styled_avg = _avg_df.style.apply(_heatmap_style, df_ref=_avg_df, szn_ref=_szn_row, axis=1)
                st.dataframe(_styled_avg, width='stretch', hide_index=True)

            # ── Prepare game logs ──────────────────────────────────────────
            _all_logs = _plogs.copy()

            if 'FGM' in _all_logs.columns and 'FG3M' in _all_logs.columns:
                _all_logs['2PM'] = (_all_logs['FGM'].astype(float) - _all_logs['FG3M'].astype(float)).round(0)
            if 'FGA' in _all_logs.columns and 'FG3A' in _all_logs.columns:
                _all_logs['2PA'] = (_all_logs['FGA'].astype(float) - _all_logs['FG3A'].astype(float)).round(0)
            if all(c in _all_logs.columns for c in ['REB', 'AST']):
                _all_logs['RA'] = (_all_logs['REB'].astype(float) + _all_logs['AST'].astype(float)).round(0)
            if all(c in _all_logs.columns for c in ['PTS', 'REB', 'AST']):
                _all_logs['PRA'] = (_all_logs['PTS'].astype(float) + _all_logs['REB'].astype(float) + _all_logs['AST'].astype(float)).round(1)
            if all(c in _all_logs.columns for c in ['PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV']):
                _all_logs['FP'] = (
                    _all_logs['PTS'].astype(float) * 1.0 +
                    _all_logs['REB'].astype(float) * 1.2 +
                    _all_logs['AST'].astype(float) * 1.5 +
                    _all_logs['STL'].astype(float) * 3.0 +
                    _all_logs['BLK'].astype(float) * 3.0 -
                    _all_logs['TOV'].astype(float) * 1.0
                ).round(1)

            _all_logs = _all_logs.rename(columns={'GAME_DATE': 'Date', 'MATCHUP': 'Matchup', 'WL': 'W/L', 'FG3M': '3PM', 'FG3A': '3PA'})
            _log_ordered = ['Date', 'Matchup', 'W/L', 'MIN', 'PTS', 'REB', 'AST', 'PRA', 'RA', 'STL', 'BLK', 'TOV', 'FP', '2PM', '2PA', '3PM', '3PA', 'FTM', 'FTA']
            _log_cols = [c for c in _log_ordered if c in _all_logs.columns]
            _all_logs = _all_logs[_log_cols].copy()

            if 'Date' in _all_logs.columns:
                _all_logs['Date'] = pd.to_datetime(_all_logs['Date']).dt.strftime('%m/%d')

            _log_num_cols = [c for c in _log_cols if c not in ('Date', 'Matchup', 'W/L')]

            # ── Highlight the prop stat column green/red vs the line ──
            _stat_to_log_col = {'FG3M': '3PM', 'FPTS': 'FP'}
            _prop_col = _stat_to_log_col.get(_stat, _stat)

            def _highlight_prop(row, cols):
                styles = [''] * len(row)
                if _prop_col in cols:
                    idx = list(cols).index(_prop_col)
                    try:
                        val = float(row.iloc[idx])
                        if val > _line:
                            styles[idx] = f'background-color: {tc.prop_over_bg};'
                        elif val < _line:
                            styles[idx] = f'background-color: {tc.prop_under_bg};'
                    except (ValueError, TypeError):
                        pass
                return styles

            _log_int_cols = [c for c in _log_num_cols if c != 'FP']
            _fmt = {c: '{:.0f}' for c in _log_int_cols if c in _all_logs.columns}
            if 'FP' in _all_logs.columns:
                _fmt['FP'] = '{:.1f}'

            # ── Filter vs opponent logs ────────────────────────────────────
            _vs_logs = _all_logs[_all_logs['Matchup'].str.contains(_opp, na=False)] if _opp and 'Matchup' in _all_logs.columns else pd.DataFrame()

            _opp_label = f"vs {_opp}" if _opp else "vs Opp"
            _tab_all, _tab_vs = st.tabs(["All Logs", _opp_label])

            with _tab_all:
                _styled_all = _all_logs.style.apply(_highlight_prop, cols=_all_logs.columns, axis=1).format(_fmt)
                st.dataframe(_styled_all, width='stretch', hide_index=True, height=213)

            with _tab_vs:
                if len(_vs_logs) == 0:
                    st.info(f"No games vs {_opp} this season.")
                else:
                    _styled_vs = _vs_logs.style.apply(_highlight_prop, cols=_vs_logs.columns, axis=1).format(_fmt)
                    st.dataframe(_styled_vs, width='stretch', hide_index=True, height=213)

        except Exception:
            pass


# normalize_team_minutes now lives in combined-app/player_app/minutes_normalization.py
# so scripts/generate_predictions_batch.py applies the identical normalization
# (Prediction Parity Rule). Imported here to keep this page's call sites unchanged.
from minutes_normalization import normalize_team_minutes  # noqa: E402


# ---------------------------------------------------------------------------
# Tanking detection
# ---------------------------------------------------------------------------
# Teams that don't own their current first-round pick have incentive to WIN
# (a worse record benefits the pick recipient, not them).
# Update at the start of each season as pick ownership changes.
# 2025-26: Pelicans conveyed their 2026 first-round pick to OKC.
_PICK_INCENTIVE_WIN_TEAM_IDS = _tu.PICK_INCENTIVE_WIN_TEAM_IDS
_games_back_from_play_in = _tu.games_back_from_play_in
_detect_tanking = _tu.detect_tanking


@st.cache_data(ttl=3600, show_spinner=False)
def _get_standings_for_tanking():
    """Fetch NBA standings for tanking detection (cached 1 hour)."""
    return _tu.get_standings(season=pf_features.CURRENT_SEASON)


@st.cache_data(ttl=1800, show_spinner=False)
def _get_game_spread(away_abbr: str, home_abbr: str):
    """Return the absolute point spread from The Odds API (cached 30 min)."""
    return _tu.get_game_spread(away_abbr, home_abbr)


def compute_tanking_adjustments(
    statlines: list,
    away_team_id: int,
    home_team_id: int,
    away_abbr: str,
    home_abbr: str,
) -> tuple[dict, dict]:
    """
    Detect tanking context and return suggested minute adjustments with metadata.
    Uses Streamlit-cached standings and spread lookups.
    """
    standings_df = _get_standings_for_tanking()
    spread = _get_game_spread(away_abbr, home_abbr)
    return _tu.compute_tanking_adjustments(
        statlines, away_team_id, home_team_id, away_abbr, home_abbr,
        standings_df=standings_df, spread=spread,
    )


st.set_page_config(layout="wide")
st.title("Predictions")

# Add sidebar with cache clear button
with st.sidebar:
    st.markdown("### Cache Management")
    if st.button("🗑️ Clear All Cache", width='stretch'):
        st.cache_data.clear()
        st.success("✅ Cache cleared successfully!")
        st.rerun()
    st.markdown("---")

    # --- Simulation settings ---
    st.markdown("### Ceiling / Floor Method")
    run_simulation = st.checkbox(
        "Monte Carlo simulation",
        value=True,
        help="Run simulations to estimate ceiling/floor. Uncheck for faster predictions using historical percentiles only."
    )

    _sim_kwargs = {'enabled': run_simulation}
    if run_simulation:
        with st.expander("Advanced: Simulation Settings", expanded=False):
            _sim_kwargs['n_iterations'] = st.slider(
                "Iterations", 100, 1000, 500, step=100,
                help="More iterations = more accurate distribution but slower per player (~0.5s per 100 at default settings)."
            )
            _sim_kwargs['ceiling_percentile'] = float(st.slider(
                "Ceiling percentile", 80, 99, 90,
                help="e.g. 90 = the 90th-percentile outcome of the simulations."
            ))
            _sim_kwargs['floor_percentile'] = float(st.slider(
                "Floor percentile", 1, 20, 10,
                help="e.g. 10 = the 10th-percentile outcome of the simulations."
            ))
            st.markdown("**Input variance (per iteration)**")
            _min_std = st.slider(
                "Minutes std (0 = use player history)", 0.0, 8.0, 0.0, step=0.5,
                help="How many minutes to vary each iteration. 0 = automatically uses the player's own historical minute variability."
            )
            _sim_kwargs['minutes_std'] = None if _min_std == 0.0 else _min_std
            _sim_kwargs['opp_def_rtg_noise_std'] = st.slider(
                "Opp DefRtg noise (σ)", 0.0, 8.0, 3.0, step=0.5,
                help="Gaussian noise added to opponent defensive rating each iteration."
            )
            _sim_kwargs['pace_noise_std'] = st.slider(
                "Pace noise (σ)", 0.0, 5.0, 2.0, step=0.5,
                help="Gaussian noise added to opponent pace each iteration."
            )
            _sim_kwargs['usage_noise_std'] = st.slider(
                "Usage rate noise (σ %)", 0.0, 5.0, 2.0, step=0.5,
                help="Gaussian noise added to player usage rate each iteration."
            )

    _simulation_config = pm.SimulationConfig(**_sim_kwargs)
    st.markdown("---")


# Cache players dataframe to avoid repeated API calls
@st.cache_data
def get_cached_players_dataframe():
    """Cache players dataframe from PlayerIndex endpoint"""
    result = pf.get_players_dataframe()
    return result

@st.cache_data
def get_cached_player_list():
    """Cache player list from PlayerIndex endpoint"""
    result = pf.get_player_list()
    return result

@st.cache_data
def get_player_name_map(player_ids_list, players_df):
    """Cache player names using the players dataframe"""
    result = {pid: pf.get_player_name(pid, players_df) for pid in player_ids_list}
    return result

@st.cache_data
def get_cached_player_stats():
    """Get player stats including average minutes for sorting"""
    try:
        import nba_api.stats.endpoints as endpoints
        player_stats = endpoints.LeagueDashPlayerStats(
            season=pf_features.CURRENT_SEASON,
            league_id_nullable='00',
            per_mode_detailed='PerGame',
            season_type_all_star='Regular Season'
        ).get_data_frames()[0]
        # Convert PLAYER_ID to int for consistent key type
        minutes_dict = {}
        for _, row in player_stats.iterrows():
            player_id = int(row['PLAYER_ID'])
            minutes = float(row['MIN']) if pd.notna(row['MIN']) else 0.0
            minutes_dict[player_id] = minutes
        return minutes_dict
    except Exception as e:
        print(f"Error fetching player stats: {e}")
        return {}

# Cache team defensive shooting data
@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_cached_shooting_data():
    """Cache team shooting data from pbpstats API"""
    try:
        team_stats, opp_team_stats = tds.load_shooting_data()
        return team_stats, opp_team_stats, None
    except Exception as e:
        return None, None, str(e)

# Cache player shooting data
@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_cached_player_shooting_data():
    """Cache player shooting data from pbpstats API"""
    try:
        player_stats = tds.load_player_shooting_data()
        return player_stats, None
    except Exception as e:
        return None, str(e)

# Function to fetch matchups for a given date
@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_matchups_for_date(selected_date):
    """Fetch NBA matchups for a given date from the API"""
    try:
        import pytz
        from datetime import datetime
        
        # Get schedule data
        league_schedule = nba_api.stats.endpoints.ScheduleLeagueV2(
            league_id='00',
            season='2025-26'
        ).get_data_frames()[0]
        
        league_schedule['dateGame'] = pd.to_datetime(league_schedule['gameDate'])
        league_schedule['matchup'] = league_schedule['awayTeam_teamTricode'] + ' @ ' + league_schedule['homeTeam_teamTricode']
        
        # Compare date parts only to handle datetime objects with time components
        date_games = league_schedule[
            league_schedule['dateGame'].dt.date == selected_date
        ]
        
        if len(date_games) > 0:
            matchups = []
            for _, row in date_games.iterrows():
                matchup_str = row['matchup']
                away_team = row['awayTeam_teamTricode']
                home_team = row['homeTeam_teamTricode']
                away_team_id = row['awayTeam_teamId']
                home_team_id = row['homeTeam_teamId']
                game_id = str(row.get('gameId', ''))
                
                # Get game time from gameDateTimeEst (has actual tip-off time)
                game_time_str = None
                game_date_raw = row.get('gameDate', '')
                game_dt_est_raw = row.get('gameDateTimeEst', '')

                if pd.notna(game_dt_est_raw) and game_dt_est_raw:
                    try:
                        # gameDateTimeEst is Eastern time but NBA API appends a
                        # misleading 'Z' suffix.  Strip it so pandas doesn't
                        # interpret the value as UTC.
                        est_str = str(game_dt_est_raw).replace('Z', '')
                        game_dt = pd.to_datetime(est_str)
                        if game_dt.hour != 0 or game_dt.minute != 0:
                            # Localize as Eastern (the true timezone of this field)
                            eastern = pytz.timezone('US/Eastern')
                            if game_dt.tzinfo is None:
                                game_dt = eastern.localize(game_dt)
                            else:
                                game_dt = game_dt.astimezone(eastern)

                            # Convert to Central Time
                            central = pytz.timezone('US/Central')
                            game_dt_ct = game_dt.astimezone(central)

                            hour_12 = game_dt_ct.strftime('%I').lstrip('0') or '12'
                            minute_str = f":{game_dt_ct.strftime('%M')}" if game_dt_ct.minute != 0 else ""
                            am_pm = game_dt_ct.strftime('%p')
                            game_time_str = f"{hour_12}{minute_str} {am_pm} CT"
                    except Exception:
                        pass

                matchups.append({
                    'matchup': matchup_str,
                    'away_team': away_team,
                    'home_team': home_team,
                    'away_team_id': away_team_id,
                    'home_team_id': home_team_id,
                    'game_time': game_time_str,
                    'game_date': game_date_raw
                })
            return matchups, None  # Return matchups and error (None)
        else:
            return [], None  # No games on this date
    except Exception as e:
        return [], str(e)  # Return empty list and error message


# Get cached players dataframe and player list
players_df = get_cached_players_dataframe()

# Get cached player stats (including average minutes) for sorting
player_minutes_map = get_cached_player_stats()

# Cached function to fetch injury report for a specific date
@st.cache_data(ttl=1800, show_spinner=False)  # Cache for 30 minutes
def get_cached_injury_report_for_date(selected_date):
    """Fetch and cache injury report for a specific date"""
    try:
        # Always use today's date for injury reports (PDF includes tomorrow's games too)
        injury_df, status_msg = ir.fetch_injuries_for_date(report_date=date.today())
        if injury_df is not None and len(injury_df) > 0:
            return injury_df, status_msg, None
        else:
            return pd.DataFrame(), status_msg, "No injuries found"
    except Exception as e:
        return pd.DataFrame(), "", str(e)

# Validate players_df
if players_df is None or len(players_df) == 0:
    st.error("Failed to load players data. Please clear the cache and restart the app.")
    st.stop()

if 'PERSON_ID' not in players_df.columns:
    st.error(f"Players dataframe has incorrect format. Available columns: {list(players_df.columns)}")
    st.error("Please clear the Streamlit cache (☰ → Settings → Clear cache) and restart the app.")
    st.stop()
player_ids_list = get_cached_player_list()
player_name_map = get_player_name_map(player_ids_list, players_df)

# Matchup filter section
col_date, col_matchup = st.columns([0.3, 0.7])

with col_date:
    # Date selector - default to today
    selected_date = st.date_input(
        "Select Date:",
        value=date.today(),
        key="matchup_date"
    )

with col_matchup:
    # Get matchups for selected date
    matchups, matchup_error = get_matchups_for_date(selected_date)
    
    # Show error if API call failed
    if matchup_error:
        st.warning(f"⚠️ Could not fetch matchups: {matchup_error}")
        matchups = []
    
    # Matchup dropdown
    if matchups:
        # Format matchup options
        matchup_options = ["All Matchups"]
        for m in matchups:
            matchup_options.append(m['matchup'])
        
        selected_matchup_str = st.selectbox(
            "Select Matchup:",
            options=matchup_options,
            key="matchup_selector",
            help="Select a matchup to filter players, or 'All Matchups' to see everyone"
        )
    else:
        selected_matchup_str = "All Players"
        if not matchup_error:  # Only show info if no error (meaning no games on this date)
            st.info("ℹ️ No games scheduled for this date. Showing all players.")

# Fetch injury report for the selected date
# This needs to happen after date selection but before injury section
injury_report_df, injury_report_url, injury_load_error = get_cached_injury_report_for_date(selected_date)

# Clear processed matchups cache when date changes (so injuries get re-processed)
if 'last_injury_date' not in st.session_state or st.session_state.last_injury_date != selected_date:
    st.session_state.last_injury_date = selected_date
    st.session_state.processed_matchups = {}  # Clear cached matchup injury data

# Filter players based on selected matchup
filtered_player_ids_list = player_ids_list.copy()
selected_team_ids = None
matchup_away_team_id = None
matchup_home_team_id = None
matchup_away_team_abbr = None
matchup_home_team_abbr = None

if selected_matchup_str and selected_matchup_str != "All Players" and selected_matchup_str != "All Matchups":
    # Find the selected matchup
    selected_matchup = next((m for m in matchups if m['matchup'] == selected_matchup_str), None)
    
    if selected_matchup:
        # Get team IDs and abbreviations for filtering
        matchup_away_team_id = selected_matchup['away_team_id']
        matchup_home_team_id = selected_matchup['home_team_id']
        matchup_away_team_abbr = selected_matchup['away_team']
        matchup_home_team_abbr = selected_matchup['home_team']
        selected_team_ids = [matchup_away_team_id, matchup_home_team_id]
        
        # Filter players dataframe to only include players from these teams
        if 'TEAM_ID' in players_df.columns:
            # Convert team IDs to match the format in players_df (handle both int and str)
            players_df_team_ids = players_df['TEAM_ID'].astype(int)
            filtered_players_df = players_df[players_df_team_ids.isin(selected_team_ids)].copy()
            
            # Add average minutes column for sorting
            filtered_players_df['AVG_MIN'] = filtered_players_df['PERSON_ID'].apply(
                lambda x: player_minutes_map.get(int(x), 0)
            )
            
            # Sort: Away team first, then Home team; within each team, sort by minutes descending
            away_players = filtered_players_df[filtered_players_df['TEAM_ID'].astype(int) == matchup_away_team_id]
            away_players = away_players.sort_values('AVG_MIN', ascending=False)
            
            home_players = filtered_players_df[filtered_players_df['TEAM_ID'].astype(int) == matchup_home_team_id]
            home_players = home_players.sort_values('AVG_MIN', ascending=False)
            
            # Combine: away team players first, then home team players
            sorted_players_df = pd.concat([away_players, home_players])
            filtered_player_ids_list = sorted_players_df['PERSON_ID'].astype(str).tolist()
            
            # Show info about the matchup
            st.info(f"📊 Showing players from: {selected_matchup['away_team']} @ {selected_matchup['home_team']} (sorted by minutes)")
            


# Fetch injury report for the selected date
injury_report_df, injury_report_url, injury_load_error = get_cached_injury_report_for_date(selected_date)

# Clear processed matchups cache when date changes (so injuries get re-processed)
if 'last_injury_date_predictions' not in st.session_state or st.session_state.last_injury_date_predictions != selected_date:
    st.session_state.last_injury_date_predictions = selected_date
    st.session_state.processed_matchups_predictions = {}  # Clear cached matchup injury data

# ── Page-level tabs ──────────────────────────────────────────────
_pred_tab, _injury_tab = st.tabs(["📊 Predictions", "🏥 Injury Report"])

with _injury_tab:
    st.markdown("### Injury Report for Games")
    st.caption("Latest report (e.g. 6 PM ET) may differ from earlier; use Refresh to fetch now.")

    @st.cache_data(ttl=600, show_spinner="Fetching injury report...")
    def _fetch_injury_tab_data(sel_date):
        _inj_players_df = pf.get_players_dataframe()
        return ir.fetch_injuries_for_date(sel_date, _inj_players_df), _inj_players_df

    if st.button("🔄 Refresh injury report", type="secondary", key="refresh_injury_report_pred"):
        _fetch_injury_tab_data.clear()
        st.rerun()
    st.markdown("")

    def _inj_status_color(status):
        s = (status or '').lower()
        if 'out' in s:          return tc.injury_out
        if 'doubtful' in s:     return tc.injury_doubtful
        if 'questionable' in s: return tc.injury_questionable
        if 'probable' in s:     return tc.injury_probable
        return tc.injury_unknown

    def _inj_sort_key(inj_item):
        s = (inj_item.get('status', '') or '').lower()
        if 'probable' in s:     return 0
        if 'questionable' in s: return 1
        if 'doubtful' in s:     return 2
        if 'out' in s:          return 3
        return 4

    def _render_team_injuries(injuries, team_abbr, team_id_val):
        st.markdown(
            f"""<div style="display:flex; align-items:center; gap:10px; margin-bottom:10px;">
                <img src="https://cdn.nba.com/logos/nba/{team_id_val}/primary/L/logo.svg"
                     style="height:36px; width:auto;">
                <span style="font-size:17px; font-weight:bold;">{team_abbr}</span>
            </div>""",
            unsafe_allow_html=True,
        )
        if injuries:
            for _inj in injuries:
                _status    = _inj.get('status', '')
                _color     = _inj_status_color(_status)
                _name      = ir.format_player_name(_inj.get('player_name', ''))
                _reason    = ir.format_injury_reason(_inj.get('reason', ''))
                _player_id = _inj.get('player_id', '')
                _headshot  = (
                    f"https://cdn.nba.com/headshots/nba/latest/1040x760/{_player_id}.png"
                    if _player_id else ""
                )
                st.markdown(
                    f"""<div style="display:flex; align-items:center; gap:12px;
                                    padding:8px 0; border-bottom:1px solid #eee;">
                        <img src="{_headshot}"
                             style="width:75px; height:55px; object-fit:cover;
                                    border-radius:4px; background-color:{tc.img_placeholder};"
                             onerror="this.style.display='none'">
                        <div style="flex:1;">
                            <span style="font-weight:bold;">{_name}</span>
                            <span style="background-color:{_color}; color:white;
                                         padding:2px 6px; border-radius:3px;
                                         font-size:12px; margin-left:8px;">{_status}</span>
                            <br><span style="font-size:13px; color:#666;">{_reason}</span>
                        </div>
                    </div>""",
                    unsafe_allow_html=True,
                )
        else:
            st.info("No injuries reported")

    try:
        (_inj_tab_df, _inj_tab_status), _inj_tab_players_df = _fetch_injury_tab_data(selected_date)
        if _inj_tab_df is not None and len(_inj_tab_df) > 0:
            st.success(f"✅ {_inj_tab_status}")

            for _inj_matchup in (matchups or []):
                _inj_away = _inj_matchup['away_team']
                _inj_home = _inj_matchup['home_team']
                _inj_away_id = _inj_matchup.get('away_team_id', '')
                _inj_home_id = _inj_matchup.get('home_team_id', '')
                _inj_matchup_str = _inj_matchup['matchup']

                _inj_game_date_raw = _inj_matchup.get('game_date', '')
                _inj_time_label = _inj_matchup_str
                if _inj_game_date_raw:
                    try:
                        import pytz as _pytz_inj
                        _inj_dt = pd.to_datetime(_inj_game_date_raw)
                        if _inj_dt.hour != 0 or _inj_dt.minute != 0:
                            if _inj_dt.tzinfo is None:
                                _inj_dt = _pytz_inj.UTC.localize(_inj_dt)
                            _inj_ct = _inj_dt.astimezone(_pytz_inj.timezone('US/Central'))
                            _inj_h12 = _inj_ct.hour % 12 or 12
                            _inj_ampm = "AM" if _inj_ct.hour < 12 else "PM"
                            _inj_time_label = f"{_inj_matchup_str} | {_inj_h12}:{_inj_ct.minute:02d} {_inj_ampm} CT"
                    except Exception:
                        pass

                st.markdown(f"#### {_inj_time_label}")

                _matchup_injuries = ir.get_injuries_for_matchup(
                    _inj_tab_df, _inj_away, _inj_home, _inj_tab_players_df
                )
                _away_injuries = sorted(_matchup_injuries.get('away', []), key=_inj_sort_key)
                _home_injuries = sorted(_matchup_injuries.get('home', []), key=_inj_sort_key)

                if not _away_injuries and not _home_injuries:
                    st.info(f"No injuries reported for {_inj_matchup_str}")
                else:
                    _inj_c1, _inj_c2 = st.columns(2)
                    with _inj_c1:
                        _render_team_injuries(_away_injuries, _inj_away, _inj_away_id)
                    with _inj_c2:
                        _render_team_injuries(_home_injuries, _inj_home, _inj_home_id)

                st.markdown("---")
        else:
            st.warning(f"⚠️ {_inj_tab_status}")
            st.info("💡 Injury reports are typically available closer to game time. Try again later.")
    except Exception as _inj_err:
        st.error(f"❌ Error fetching injury report: {_inj_err}")
        import traceback
        with st.expander("Error Details"):
            st.code(traceback.format_exc())

with _pred_tab:

    # Check if matchup is selected
    if selected_matchup_str and selected_matchup_str != "All Players" and selected_matchup_str != "All Matchups":
        selected_matchup = next((m for m in matchups if m['matchup'] == selected_matchup_str), None)

        if selected_matchup:
            matchup_away_team_id = selected_matchup['away_team_id']
            matchup_home_team_id = selected_matchup['home_team_id']
            matchup_away_team_abbr = selected_matchup['away_team']
            matchup_home_team_abbr = selected_matchup['home_team']

            # Filter players for this matchup
            if 'TEAM_ID' in players_df.columns:
                selected_team_ids = [matchup_away_team_id, matchup_home_team_id]
                players_df_team_ids = players_df['TEAM_ID'].astype(int)
                filtered_players_df = players_df[players_df_team_ids.isin(selected_team_ids)].copy()
                filtered_player_ids_list = filtered_players_df['PERSON_ID'].astype(str).tolist()
            else:
                filtered_player_ids_list = player_ids_list.copy()

            # Show matchup info
            st.info(f"📊 Generating predictions for: {matchup_away_team_abbr} @ {matchup_home_team_abbr}")

            # === TANKING ALERT BANNER ===
            # Show after predictions are generated (context stored in session state)
            _t_ctx_key = f"{selected_date.strftime('%Y-%m-%d')}_{matchup_away_team_abbr}_{matchup_home_team_abbr}_tanking_ctx"
            _t_ctx = st.session_state.get(_t_ctx_key)
            if _t_ctx and _t_ctx.get('players_adjusted', 0) > 0:
                _severity_label = {'hard': '🔴 Hard', 'soft': '🟡 Soft'}
                _parts = []
                if _t_ctx.get('away_tanking'):
                    _parts.append(
                        f"{matchup_away_team_abbr}: {_severity_label.get(_t_ctx['away_tanking'], '')} tank "
                        f"({_t_ctx['away_games_back']:.1f} GB from play-in)"
                    )
                if _t_ctx.get('home_tanking'):
                    _parts.append(
                        f"{matchup_home_team_abbr}: {_severity_label.get(_t_ctx['home_tanking'], '')} tank "
                        f"({_t_ctx['home_games_back']:.1f} GB from play-in)"
                    )
                _spread_str = f" | Spread: {_t_ctx['spread']:.1f} pts" if _t_ctx.get('spread') else " | Spread: N/A"
                _scale_pct = int(_t_ctx.get('spread_mult', 0.75) * 100)
                _detail = " | ".join(_parts) + _spread_str + f" | Adjustments applied at {_scale_pct}%"
                if _t_ctx.get('both_tanking'):
                    _detail = "Both teams tanking — reduced-intensity game. " + _detail
                st.warning(
                    f"📉 **Tanking Alert** — Minute projections auto-adjusted for {_t_ctx['players_adjusted']} "
                    f"players (stars/starters ↓, bench ↑).\n\n{_detail}"
                )
            elif _t_ctx and _t_ctx.get('skipped_competitive'):
                # Tanking team detected but spread is tight — surface a softer note
                _parts = []
                if _t_ctx.get('away_tanking'):
                    _parts.append(f"{matchup_away_team_abbr} ({_t_ctx['away_games_back']:.1f} GB)")
                if _t_ctx.get('home_tanking'):
                    _parts.append(f"{matchup_home_team_abbr} ({_t_ctx['home_games_back']:.1f} GB)")
                if _parts:
                    _spread_val = _t_ctx.get('spread')
                    _spread_note = f"Spread of {_spread_val:.1f} pts" if _spread_val else "A tight spread"
                    st.info(
                        f"ℹ️ {' and '.join(_parts)} {'are' if len(_parts) > 1 else 'is'} out of play-in contention, "
                        f"but {_spread_note} suggests a competitive game — no minute adjustments applied."
                    )

            # === INJURY REPORT SECTION ===
            st.markdown("---")
            with st.expander("🏥 **Injury Report** - Official NBA injury data", expanded=True):
                st.caption("Players marked OUT/Doubtful are auto-selected below")

                # Use the pre-fetched injury data from initial load
                # Create a matchup-specific key for session state
                matchup_key = f"predictions_{matchup_away_team_abbr}@{matchup_home_team_abbr}"

                # Initialize session state for this matchup if needed
                if 'processed_matchups_predictions' not in st.session_state:
                    st.session_state.processed_matchups_predictions = {}

                # Process injuries for this matchup (only once per matchup)
                if matchup_key not in st.session_state.processed_matchups_predictions:
                    away_out = []
                    home_out = []
                    all_matchup_injuries = {'away': [], 'home': []}
                    questionable_probable = {'away': [], 'home': []}
                    has_injuries = False
                    if injury_report_df is not None:
                        try:
                            df_len = len(injury_report_df)
                            has_injuries = df_len > 0
                        except Exception as e:
                            has_injuries = False
                    if has_injuries:
                        # Get injuries for this specific matchup
                        matchup_injuries = ir.get_injuries_for_matchup(
                            injury_report_df,
                            matchup_away_team_abbr,
                            matchup_home_team_abbr,
                            players_df
                        )

                        # Separate OUT/DOUBTFUL from QUESTIONABLE/PROBABLE
                        away_questionable = []
                        for injury_item in matchup_injuries['away']:
                            status_lower = injury_item['status'].lower() if injury_item['status'] else ''
                            if 'out' in status_lower or 'doubtful' in status_lower:
                                if injury_item['player_id']:
                                    away_out.append(injury_item['player_id'])
                                away_questionable.append(injury_item)
                            elif 'questionable' in status_lower or 'probable' in status_lower:
                                away_questionable.append(injury_item)

                        home_questionable = []
                        for injury_item in matchup_injuries['home']:
                            status_lower = injury_item['status'].lower() if injury_item['status'] else ''
                            if 'out' in status_lower or 'doubtful' in status_lower:
                                if injury_item['player_id']:
                                    home_out.append(injury_item['player_id'])
                                home_questionable.append(injury_item)
                            elif 'questionable' in status_lower or 'probable' in status_lower:
                                home_questionable.append(injury_item)

                        all_matchup_injuries = matchup_injuries
                        questionable_probable = {'away': away_questionable, 'home': home_questionable}

                    # Store processed data for this matchup
                    st.session_state.processed_matchups_predictions[matchup_key] = {
                        'away_out': away_out,
                        'home_out': home_out,
                        'all_matchup_injuries': all_matchup_injuries,
                        'questionable_probable': questionable_probable
                    }

                # Get the processed data for this matchup
                matchup_data = st.session_state.processed_matchups_predictions[matchup_key]
                fetched_away_out = matchup_data['away_out']
                fetched_home_out = matchup_data['home_out']
                all_matchup_injuries = matchup_data['all_matchup_injuries']
                questionable_probable = matchup_data['questionable_probable']

                # Show injury report status
                if injury_report_url:
                    st.info(f"📋 {injury_report_url}")
                elif injury_load_error:
                    st.warning(f"⚠️ Could not load injury report: {injury_load_error}")

                # Show all found injuries for this matchup
                all_injuries_away = all_matchup_injuries.get('away', [])
                all_injuries_home = all_matchup_injuries.get('home', [])

                if all_injuries_away or all_injuries_home:
                    st.success(f"✅ Found {len(all_injuries_away) + len(all_injuries_home)} injuries for this matchup")

                    # Helper function to get status color
                    def get_status_color(status):
                        status_lower = status.lower() if status else ''
                        if 'out' in status_lower:
                            return tc.injury_out
                        elif 'doubtful' in status_lower:
                            return tc.injury_doubtful
                        elif 'questionable' in status_lower:
                            return tc.injury_questionable
                        elif 'probable' in status_lower:
                            return tc.injury_probable
                        else:
                            return tc.injury_unknown

                    # Helper function to get status sort order (Probable first, Out last)
                    def get_status_order(status):
                        status_lower = status.lower() if status else ''
                        if 'probable' in status_lower:
                            return 0
                        elif 'questionable' in status_lower:
                            return 1
                        elif 'doubtful' in status_lower:
                            return 2
                        elif 'out' in status_lower:
                            return 3
                        else:
                            return 4

                    # Two-column layout for injuries
                    col_away, col_home = st.columns(2)

                    with col_away:
                        if all_injuries_away:
                            st.markdown(f"### {matchup_away_team_abbr}")
                            sorted_away = sorted(all_injuries_away, key=lambda x: get_status_order(x.get('status', '')))
                            for injury_item in sorted_away:
                                status = injury_item.get('status', 'Unknown')
                                status_color = get_status_color(status)
                                formatted_name = ir.format_player_name(injury_item['player_name'])
                                formatted_reason = ir.format_injury_reason(injury_item.get('reason', ''))
                                player_id = injury_item.get('player_id', '')
                                headshot_url = f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png" if player_id else ""
                                st.markdown(f"""
                                    <div style="display: flex; align-items: center; gap: 12px; padding: 8px 0; border-bottom: 1px solid #eee;">
                                        <img src="{headshot_url}" style="width: 75px; height: 55px; object-fit: cover; border-radius: 4px; background-color: #f0f0f0;" onerror="this.style.display='none'">
                                        <div style="flex: 1;">
                                            <span style="font-weight: bold;">{formatted_name}</span>
                                            <span style="background-color: {status_color}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 12px; margin-left: 8px;">{status}</span>
                                            <br><span style="font-size: 13px; color: #666;">{formatted_reason}</span>
                                        </div>
                                    </div>
                                """, unsafe_allow_html=True)
                        else:
                            st.markdown(f"### {matchup_away_team_abbr}")
                            st.info("No injuries")

                    with col_home:
                        if all_injuries_home:
                            st.markdown(f"### {matchup_home_team_abbr}")
                            sorted_home = sorted(all_injuries_home, key=lambda x: get_status_order(x.get('status', '')))
                            for injury_item in sorted_home:
                                status = injury_item.get('status', 'Unknown')
                                status_color = get_status_color(status)
                                formatted_name = ir.format_player_name(injury_item['player_name'])
                                formatted_reason = ir.format_injury_reason(injury_item.get('reason', ''))
                                player_id = injury_item.get('player_id', '')
                                headshot_url = f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png" if player_id else ""
                                st.markdown(f"""
                                    <div style="display: flex; align-items: center; gap: 12px; padding: 8px 0; border-bottom: 1px solid #eee;">
                                        <img src="{headshot_url}" style="width: 75px; height: 55px; object-fit: cover; border-radius: 4px; background-color: #f0f0f0;" onerror="this.style.display='none'">
                                        <div style="flex: 1;">
                                            <span style="font-weight: bold;">{formatted_name}</span>
                                            <span style="background-color: {status_color}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 12px; margin-left: 8px;">{status}</span>
                                            <br><span style="font-size: 13px; color: #666;">{formatted_reason}</span>
                                        </div>
                                    </div>
                                """, unsafe_allow_html=True)
                        else:
                            st.markdown(f"### {matchup_home_team_abbr}")
                            st.info("No injuries")
                else:
                    st.info("No injuries reported")

                # Show which players are being auto-selected as OUT
                if fetched_away_out or fetched_home_out:
                    st.caption(f"🔴 Only players marked OUT or Doubtful are auto-selected below")


            st.divider()

            # === SELECT PLAYERS OUT SECTION ===
            # Get players from both teams for the injury selection
            # Filter players by team
            away_team_players_df = players_df[players_df['TEAM_ID'].astype(int) == matchup_away_team_id].copy()
            home_team_players_df = players_df[players_df['TEAM_ID'].astype(int) == matchup_home_team_id].copy()

            # Add minutes for sorting
            away_team_players_df['AVG_MIN'] = away_team_players_df['PERSON_ID'].apply(
                lambda x: player_minutes_map.get(int(x), 0)
            )
            home_team_players_df['AVG_MIN'] = home_team_players_df['PERSON_ID'].apply(
                lambda x: player_minutes_map.get(int(x), 0)
            )

            # Sort by minutes and get top players (likely to matter most)
            away_team_players_df = away_team_players_df.sort_values('AVG_MIN', ascending=False).head(15)
            home_team_players_df = home_team_players_df.sort_values('AVG_MIN', ascending=False).head(15)

            # Get player IDs and create name maps
            away_player_ids = away_team_players_df['PERSON_ID'].astype(str).tolist()
            home_player_ids = home_team_players_df['PERSON_ID'].astype(str).tolist()

            def format_player_with_mins(pid):
                name = player_name_map.get(pid, f"Player {pid}")
                mins = player_minutes_map.get(int(pid), 0)
                return f"{name} ({mins:.1f} mpg)"

            st.markdown("**Select Players Out (adjust manually if needed):**")
            inj_col1, inj_col2 = st.columns(2)

            with inj_col1:
                st.markdown(f"**{matchup_away_team_abbr} Players Out:**")
                # Use fetched data as default if available
                default_away_out = [p for p in fetched_away_out if p in away_player_ids]
                away_players_out = st.multiselect(
                    "Away team injuries",
                    options=away_player_ids,
                    default=default_away_out,
                    format_func=format_player_with_mins,
                    key=f"predictions_away_injuries_{matchup_key}",
                    label_visibility="collapsed"
                )

            with inj_col2:
                st.markdown(f"**{matchup_home_team_abbr} Players Out:**")
                # Use fetched data as default if available
                default_home_out = [p for p in fetched_home_out if p in home_player_ids]
                home_players_out = st.multiselect(
                    "Home team injuries",
                    options=home_player_ids,
                    default=default_home_out,
                    format_func=format_player_with_mins,
                    key=f"predictions_home_injuries_{matchup_key}",
                    label_visibility="collapsed"
                )

            # Store selections in session state for use by Best Value Plays
            predictions_injuries_key = f"predictions_injuries_{matchup_key}"
            st.session_state[predictions_injuries_key] = {
                'away_out': away_players_out,
                'home_out': home_players_out
            }


            # === BEST VALUE PLAYS SECTION ===
            # BEST VALUE PLAYS SECTION
            # ============================================================
            game_date_str_bvp = selected_date.strftime('%Y-%m-%d')
            game_cache_key_bvp = f"{game_date_str_bvp}_{matchup_away_team_abbr}_{matchup_home_team_abbr}"

            # Initialize session state for game-level prediction cache
            if 'predictions_game_cache' not in st.session_state:
                st.session_state.predictions_game_cache = {}

            with st.expander("🎯 **Best Value Plays** - Find edges across the entire game", expanded=True):
                st.caption("Generate predictions for all players and compare against Underdog lines to find the best value plays")

                # Check if we have cached predictions for this game
                cached_game_predictions = st.session_state.predictions_game_cache.get(game_cache_key_bvp)

                # If no cached predictions, check for CSV file from DraftKings Optimizer
                if cached_game_predictions is None:
                    downloads_dir = os.path.expanduser("~/Downloads")
                    csv_file = os.path.join(
                        downloads_dir,
                        f"predicted_statlines_{matchup_away_team_abbr}_vs_{matchup_home_team_abbr}_{game_date_str_bvp}.csv"
                    )

                    if os.path.exists(csv_file):
                        try:
                            # Load CSV file
                            csv_df = pd.read_csv(csv_file)

                            # Convert CSV to predictions format
                            loaded_predictions = {}
                            for _, row in csv_df.iterrows():
                                player_name = row.get('Player', '')
                                team_abbr = row.get('Team', '')

                                # Find player ID by matching name
                                player_match = players_df[
                                    (players_df['PLAYER_FIRST_NAME'] + ' ' + players_df['PLAYER_LAST_NAME'] == player_name) |
                                    (players_df['PLAYER_FIRST_NAME'] + ' ' + players_df['PLAYER_LAST_NAME'].str.replace(' ', '') == player_name)
                                ]

                                if len(player_match) > 0:
                                    player_id = str(player_match['PERSON_ID'].iloc[0])

                                    # Determine if home or away
                                    is_home = team_abbr == matchup_home_team_abbr
                                    opponent_abbr = matchup_home_team_abbr if not is_home else matchup_away_team_abbr

                                    # Create Prediction objects from CSV values
                                    predictions_dict = {}

                                    # Create Prediction objects for each stat
                                    stats_to_load = ['PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'FG3M', 'FTM', 'PRA', 'FPTS']
                                    for stat in stats_to_load:
                                        if stat in row and pd.notna(row[stat]):
                                            value = float(row[stat])
                                            predictions_dict[stat] = pm.Prediction(
                                                stat=stat,
                                                value=value,
                                                confidence='medium',  # Default confidence for loaded predictions
                                                breakdown={},
                                                factors={'source': 'CSV file'}
                                            )

                                    # Add ceiling/floor if available
                                    ceiling_floor = {}
                                    if 'FPTS_Ceiling' in row and pd.notna(row['FPTS_Ceiling']):
                                        ceiling_floor['ceiling'] = float(row['FPTS_Ceiling'])
                                    if 'FPTS_Floor' in row and pd.notna(row['FPTS_Floor']):
                                        ceiling_floor['floor'] = float(row['FPTS_Floor'])
                                    if 'FPTS_Median' in row and pd.notna(row['FPTS_Median']):
                                        ceiling_floor['median'] = float(row['FPTS_Median'])
                                    if 'FPTS_Variance' in row and pd.notna(row['FPTS_Variance']):
                                        ceiling_floor['variance'] = float(row['FPTS_Variance'])
                                    if 'FPTS_StdDev' in row and pd.notna(row['FPTS_StdDev']):
                                        ceiling_floor['std_dev'] = float(row['FPTS_StdDev'])

                                    loaded_predictions[player_id] = {
                                        'predictions': predictions_dict,
                                        'player_name': player_name,
                                        'opponent_abbr': opponent_abbr,
                                        'is_home': is_home,
                                        'team_abbr': team_abbr,
                                        'ceiling_floor': ceiling_floor if ceiling_floor else None
                                    }

                            if len(loaded_predictions) > 0:
                                # Cache the loaded predictions
                                st.session_state.predictions_game_cache[game_cache_key_bvp] = loaded_predictions
                                cached_game_predictions = loaded_predictions
                                st.info(f"📂 Loaded {len(loaded_predictions)} predictions from CSV file")
                        except Exception as e:
                            # If loading fails, just continue without cached predictions
                            st.warning(f"⚠️ Could not load predictions from CSV: {e}")
                            cached_game_predictions = None

                # Initialize session state for API data (GAME-LEVEL CACHE)
                if 'odds_game_cache' not in st.session_state:
                    st.session_state.odds_game_cache = {}
                if 'odds_api_credits' not in st.session_state:
                    st.session_state.odds_api_credits = None

                # Check if we have cached odds for this game
                cached_game_props = st.session_state.odds_game_cache.get(game_cache_key_bvp)

                # === FETCH UNDERDOG LINES SECTION ===
                with st.expander("🎰 **Fetch Underdog Lines** (The Odds API)", expanded=True):
                    st.caption("Fetch live player props from Underdog Fantasy via The Odds API")

                    # Get player count for display
                    if cached_game_props is not None:
                        players_with_props = len(cached_game_props)
                    else:
                        players_with_props = 0

                    # Dry-run preview section
                    col_preview, col_fetch = st.columns([2, 1])

                    with col_preview:
                        if st.button("🔍 Preview Request (Free)", key="preview_odds_request_bvp"):
                            with st.spinner("Checking for available events..."):
                                preview = vl.preview_odds_request(
                                    matchup_home_team_abbr,
                                    matchup_away_team_abbr,
                                    game_date_str_bvp
                                )

                                if preview.get('error'):
                                    st.error(f"❌ {preview['error']}")
                                    if preview.get('events_on_date'):
                                        st.info(f"Events found on {game_date_str_bvp}: {', '.join(preview['events_on_date'])}")
                                else:
                                    st.success(f"✅ Event found: {preview['event_details']['away_team']} @ {preview['event_details']['home_team']}")

                                    with st.container():
                                        st.markdown("**Request Details (Dry Run)**")
                                        st.code(f"""
    Event ID: {preview['event_id']}
    Region: {preview['request_info']['region']}
    Bookmaker: {preview['request_info']['bookmaker']}
    Markets: {', '.join(preview['request_info']['markets_requested'])}
    Estimated Cost: {preview['estimated_cost']}
    """, language=None)

                    with col_fetch:
                        fetch_disabled = cached_game_props is not None
                        if fetch_disabled:
                            fetch_label = f"✅ Game Cached ({players_with_props} players)"
                        else:
                            fetch_label = "📥 Fetch Lines (1 Credit)"

                        if st.button(fetch_label, key="fetch_odds_bvp", disabled=fetch_disabled):
                            with st.spinner("Fetching ALL player props for this game..."):
                                # Fetch ALL props for the game (costs 1 credit)
                                all_props, api_response = vl.fetch_all_props_for_game(
                                    matchup_home_team_abbr,
                                    matchup_away_team_abbr,
                                    game_date_str_bvp
                                )

                                if api_response.success:
                                    # Cache at GAME level
                                    st.session_state.odds_game_cache[game_cache_key_bvp] = all_props
                                    st.session_state.odds_api_credits = api_response.credits_remaining

                                    if all_props:
                                        st.success(f"✅ Cached props for {len(all_props)} players! Switch players freely - no additional credits needed.")
                                    else:
                                        st.warning("⚠️ No props found for this game on Underdog")

                                    st.rerun()
                                else:
                                    # Show detailed error message
                                    error_msg = api_response.error or "Unknown API error"
                                    st.error(f"❌ API Error: {error_msg}")

                                    # Provide helpful guidance for common errors
                                    if "Invalid API key" in error_msg:
                                        st.info("💡 **Troubleshooting:**\n"
                                               "- Verify your API key in The Odds API dashboard\n"
                                               "- If you just upgraded, try regenerating your API key\n"
                                               "- Wait a few minutes for activation after upgrading\n"
                                               "- Ensure there are no extra spaces in the API key")

                                    if api_response.credits_remaining is not None:
                                        st.session_state.odds_api_credits = api_response.credits_remaining

                    # Clear cache button
                    if cached_game_props is not None:
                        if st.button("🔄 Refresh Game Lines", key="refresh_odds_bvp"):
                            del st.session_state.odds_game_cache[game_cache_key_bvp]
                            st.session_state.odds_api_credits = None
                            st.rerun()

                    # Show API credits if available
                    if st.session_state.odds_api_credits is not None:
                        st.caption(f"💳 API Credits Remaining: {st.session_state.odds_api_credits}")

                # Update cached_game_props after potential fetch
                cached_game_props = st.session_state.odds_game_cache.get(game_cache_key_bvp)

                col_gen, col_status = st.columns([1, 2])

                with col_gen:
                    # Only enable generation if we have odds
                    if cached_game_props is None:
                        st.warning("⚠️ Fetch Underdog lines above to enable predictions")
                        gen_disabled = True
                    elif cached_game_predictions is not None:
                        st.success(f"✅ {len(cached_game_predictions)} players predicted")
                        gen_disabled = True
                    else:
                        gen_disabled = False

                    if st.button("🔮 Generate All Predictions", disabled=gen_disabled, key="gen_all_predictions"):
                        # Cache injury data in session state to avoid duplicate calls
                        if 'matchup_injuries_cache' not in st.session_state:
                            st.session_state.matchup_injuries_cache = {}

                        matchup_inj_key = f"{game_cache_key_bvp}_injuries"
                        if matchup_inj_key not in st.session_state.matchup_injuries_cache:
                            if injury_report_df is not None and len(injury_report_df) > 0:
                                matchup_inj = ir.get_injuries_for_matchup(
                                    injury_report_df,
                                    matchup_away_team_abbr,
                                    matchup_home_team_abbr,
                                    players_df
                                )
                                st.session_state.matchup_injuries_cache[matchup_inj_key] = matchup_inj
                            else:
                                st.session_state.matchup_injuries_cache[matchup_inj_key] = {'away': [], 'home': []}
                        else:
                            matchup_inj = st.session_state.matchup_injuries_cache[matchup_inj_key]

                        # Get list of players who are OUT or DOUBTFUL from stored selections
                        predictions_injuries_key = f"predictions_injuries_{matchup_key}"
                        stored_injuries = st.session_state.get(predictions_injuries_key, {'away_out': [], 'home_out': []})
                        out_player_ids = set(stored_injuries.get('away_out', []) + stored_injuries.get('home_out', []))

                        # Filter to players who are not injured (include all players, even low-minute ones)
                        # This allows the model to predict for deep bench players who might enter rotation due to injuries
                        players_to_predict = [
                            pid for pid in filtered_player_ids_list 
                            if pid not in out_player_ids  # Skip players who are OUT or DOUBTFUL
                        ]

                        if out_player_ids:
                            st.info(f"⏭️ Skipping {len(out_player_ids)} players who are Out/Doubtful")

                        # Build required data structures
                        player_names_map = {pid: player_name_map.get(pid, f"Player {pid}") for pid in players_to_predict}
                        player_team_ids_map = {}
                        for pid in players_to_predict:
                            player_row = players_df[players_df['PERSON_ID'].astype(str) == pid]
                            if len(player_row) > 0:
                                player_team_ids_map[pid] = int(player_row['TEAM_ID'].iloc[0])

                        # Store in session state for later use
                        if 'player_team_ids_map_cache' not in st.session_state:
                            st.session_state.player_team_ids_map_cache = {}
                        st.session_state.player_team_ids_map_cache[game_cache_key_bvp] = player_team_ids_map

                        progress_bar = st.progress(0, text="Generating predictions...")

                        def update_progress(current, total, player_name):
                            progress_bar.progress(current / total, text=f"({current}/{total}) {player_name}...")

                        # Generate predictions for all players
                        import time
                        gen_start = time.time()
                        all_predictions = pm.generate_predictions_for_game(
                            player_ids=players_to_predict,
                            player_names=player_names_map,
                            player_team_ids=player_team_ids_map,
                            away_team_id=matchup_away_team_id,
                            home_team_id=matchup_home_team_id,
                            away_team_abbr=matchup_away_team_abbr,
                            home_team_abbr=matchup_home_team_abbr,
                            game_date=game_date_str_bvp,
                            progress_callback=update_progress,
                            simulation_config=_simulation_config,
                        )
                        gen_total_time = time.time() - gen_start

                        progress_bar.empty()

                        # Cache the predictions
                        st.session_state.predictions_game_cache[game_cache_key_bvp] = all_predictions

                        # Log predictions to tracker (CSV fallback; never blocks display)
                        try:
                            records_to_log = []
                            for pid, player_preds in all_predictions.items():
                                p_name = player_names_map.get(pid, f"Player {pid}")
                                is_home_player = player_team_ids_map.get(pid) == matchup_home_team_id
                                opp_abbr = matchup_home_team_abbr if not is_home_player else matchup_away_team_abbr
                                for stat in ['PTS', 'REB', 'AST', 'FG3M', 'FTM']:
                                    if stat not in player_preds:
                                        continue
                                    pred = player_preds[stat]
                                    records_to_log.append(pt.PredictionRecord(
                                        timestamp=pd.Timestamp.now().isoformat(),
                                        player_id=pid,
                                        player_name=p_name,
                                        opponent_abbr=opp_abbr,
                                        game_date=game_date_str_bvp,
                                        stat=stat,
                                        prediction=pred.value,
                                        vegas_line=None,
                                        actual=None,
                                        is_home=is_home_player,
                                        days_rest=2,
                                        confidence=pred.confidence,
                                        season_avg=pred.breakdown.get('season_avg', 0.0),
                                        l5_avg=pred.breakdown.get('L5_avg', 0.0),
                                        l10_avg=0.0,
                                        vs_opponent_avg=pred.breakdown.get('vs_opponent'),
                                        opp_def_rating=0.0,
                                        opp_pace=0.0,
                                        usage_rate=0.0,
                                    ))
                            if records_to_log:
                                pt.log_predictions_batch(records_to_log)
                        except Exception:
                            pass  # Logging failures must never affect prediction display

                        st.success(f"✅ Generated predictions for {len(all_predictions)} players!")
                        st.rerun()

                with col_status:
                    if cached_game_predictions is not None and cached_game_props is not None:
                        st.info(f"📊 Predictions: {len(cached_game_predictions)} players | Lines: {len(cached_game_props)} players")

                    # Refresh button - actually regenerates predictions
                    if cached_game_predictions is not None:
                        if st.button("🔄 Regenerate Predictions", key="refresh_all_predictions"):
                            # Check if game has already started
                            from datetime import datetime
                            import pytz
                            now_utc = datetime.now(pytz.UTC)

                            # Get game datetime from schedule
                            game_datetime = None
                            try:
                                league_schedule = nba_api.stats.endpoints.ScheduleLeagueV2(
                                    league_id='00',
                                    season='2025-26'
                                ).get_data_frames()[0]

                                league_schedule['dateGame'] = pd.to_datetime(league_schedule['gameDate'])
                                game_row = league_schedule[
                                    (league_schedule['dateGame'].dt.date == pd.to_datetime(game_date_str_bvp).date()) &
                                    (league_schedule['awayTeam_teamTricode'] == matchup_away_team_abbr) &
                                    (league_schedule['homeTeam_teamTricode'] == matchup_home_team_abbr)
                                ]

                                if len(game_row) > 0:
                                    game_datetime = pd.to_datetime(game_row.iloc[0]['gameDateTimeUTC'])
                                    if game_datetime.tzinfo is None:
                                        game_datetime = pytz.UTC.localize(game_datetime.to_pydatetime())
                                    else:
                                        game_datetime = game_datetime.to_pydatetime()
                            except:
                                pass

                            # Check if game has already started
                            if game_datetime is not None and game_datetime < now_utc:
                                st.warning(f"⏭️  Game has already started or finished (tip-off: {game_datetime.strftime('%Y-%m-%d %H:%M:%S %Z')}). Cannot regenerate predictions.")
                                st.stop()

                            # Delete CSV file if it exists (so it doesn't get reloaded)
                            downloads_dir = os.path.expanduser("~/Downloads")
                            csv_file = os.path.join(
                                downloads_dir,
                                f"predicted_statlines_{matchup_away_team_abbr}_vs_{matchup_home_team_abbr}_{game_date_str_bvp}.csv"
                            )
                            if os.path.exists(csv_file):
                                try:
                                    os.remove(csv_file)
                                except Exception as e:
                                    st.warning(f"⚠️ Could not delete CSV file: {e}")

                            # Clear cached predictions (including CSV-loaded ones)
                            if game_cache_key_bvp in st.session_state.predictions_game_cache:
                                del st.session_state.predictions_game_cache[game_cache_key_bvp]

                            # Also clear best plays cache if it exists
                            cached_best_plays_key = f"{game_cache_key_bvp}_best_plays"
                            if cached_best_plays_key in st.session_state:
                                del st.session_state[cached_best_plays_key]

                            # Now trigger regeneration by calling the same logic as "Generate All Predictions"
                            # Cache injury data in session state to avoid duplicate calls
                            if 'matchup_injuries_cache' not in st.session_state:
                                st.session_state.matchup_injuries_cache = {}

                            matchup_inj_key = f"{game_cache_key_bvp}_injuries"
                            if matchup_inj_key not in st.session_state.matchup_injuries_cache:
                                if injury_report_df is not None and len(injury_report_df) > 0:
                                    matchup_inj = ir.get_injuries_for_matchup(
                                        injury_report_df,
                                        matchup_away_team_abbr,
                                        matchup_home_team_abbr,
                                        players_df
                                    )
                                    st.session_state.matchup_injuries_cache[matchup_inj_key] = matchup_inj
                                else:
                                    st.session_state.matchup_injuries_cache[matchup_inj_key] = {'away': [], 'home': []}
                            else:
                                matchup_inj = st.session_state.matchup_injuries_cache[matchup_inj_key]

                            # Get list of players who are OUT or DOUBTFUL from stored selections
                            predictions_injuries_key = f"predictions_injuries_{matchup_key}"
                            stored_injuries = st.session_state.get(predictions_injuries_key, {'away_out': [], 'home_out': []})
                            out_player_ids = set(stored_injuries.get('away_out', []) + stored_injuries.get('home_out', []))

                            # Filter to players who are not injured
                            players_to_predict = [
                                pid for pid in filtered_player_ids_list 
                                if pid not in out_player_ids
                            ]

                            if out_player_ids:
                                st.info(f"⏭️ Skipping {len(out_player_ids)} players who are Out/Doubtful")

                            # Build required data structures
                            player_names_map = {pid: player_name_map.get(pid, f"Player {pid}") for pid in players_to_predict}
                            player_team_ids_map = {}
                            for pid in players_to_predict:
                                player_row = players_df[players_df['PERSON_ID'].astype(str) == pid]
                                if len(player_row) > 0:
                                    player_team_ids_map[pid] = int(player_row['TEAM_ID'].iloc[0])

                            # Store in session state for later use
                            if 'player_team_ids_map_cache' not in st.session_state:
                                st.session_state.player_team_ids_map_cache = {}
                            st.session_state.player_team_ids_map_cache[game_cache_key_bvp] = player_team_ids_map

                            progress_bar = st.progress(0, text="Regenerating predictions...")

                            def update_progress(current, total, player_name):
                                progress_bar.progress(current / total, text=f"({current}/{total}) {player_name}...")

                            # Generate predictions for all players
                            import time
                            gen_start = time.time()
                            all_predictions = pm.generate_predictions_for_game(
                                player_ids=players_to_predict,
                                player_names=player_names_map,
                                player_team_ids=player_team_ids_map,
                                away_team_id=matchup_away_team_id,
                                home_team_id=matchup_home_team_id,
                                away_team_abbr=matchup_away_team_abbr,
                                home_team_abbr=matchup_home_team_abbr,
                                game_date=game_date_str_bvp,
                                progress_callback=update_progress,
                                simulation_config=_simulation_config,
                            )
                            gen_total_time = time.time() - gen_start

                            progress_bar.empty()

                            # Cache the predictions
                            st.session_state.predictions_game_cache[game_cache_key_bvp] = all_predictions
                            st.success(f"✅ Regenerated predictions for {len(all_predictions)} players!")
                            st.rerun()

                # If we have both predictions and props, show the best value plays
                if cached_game_predictions is not None and cached_game_props is not None:
                    st.markdown("---")

                    # Filters
                    filter_col1, filter_col2, filter_col3 = st.columns(3)

                    with filter_col1:
                        min_edge = st.slider(
                            "Minimum Edge %",
                            min_value=0,
                            max_value=25,
                            value=5,
                            step=1,
                            key="bvp_min_edge"
                        )

                    with filter_col2:
                        confidence_options = st.multiselect(
                            "Confidence Level",
                            options=['high', 'medium', 'low'],
                            default=['high', 'medium'],
                            key="bvp_confidence"
                        )

                    with filter_col3:
                        stat_options = st.multiselect(
                            "Stats",
                            options=['PTS', 'REB', 'AST', 'PRA', 'RA', 'STL', 'BLK', 'FG3M', 'FTM', 'FPTS'],
                            default=['PTS', 'REB', 'AST', 'PRA', 'RA', 'FG3M', 'FTM', 'FPTS'],
                            key="bvp_stats"
                        )

                    # Calculate injury adjustments for all players in batch predictions (optimized)
                    injury_adjustments_map = {}

                    # Get player_team_ids_map from session state or reconstruct it efficiently
                    cached_team_ids_map = st.session_state.get('player_team_ids_map_cache', {}).get(game_cache_key_bvp)
                    if cached_team_ids_map is None:
                        # Reconstruct from players_df efficiently using a lookup dictionary
                        # Create a fast lookup map: player_id -> team_id
                        players_df_id_str = players_df['PERSON_ID'].astype(str)
                        players_df_team_id = players_df['TEAM_ID'].astype(int)
                        player_team_lookup = dict(zip(players_df_id_str, players_df_team_id))

                        cached_team_ids_map = {}
                        for player_id in cached_game_predictions.keys():
                            player_id_str = str(player_id)
                            if player_id_str in player_team_lookup:
                                cached_team_ids_map[player_id_str] = player_team_lookup[player_id_str]

                        # Cache it for future use
                        if 'player_team_ids_map_cache' not in st.session_state:
                            st.session_state.player_team_ids_map_cache = {}
                        st.session_state.player_team_ids_map_cache[game_cache_key_bvp] = cached_team_ids_map

                    # Get injury data from cache (already fetched earlier)
                    matchup_inj_key = f"{game_cache_key_bvp}_injuries"
                    matchup_inj = st.session_state.get('matchup_injuries_cache', {}).get(matchup_inj_key, {'away': [], 'home': []})

                    # Build lists of out players by team ONCE from stored selections
                    predictions_injuries_key = f"predictions_injuries_{matchup_key}"
                    stored_injuries = st.session_state.get(predictions_injuries_key, {'away_out': [], 'home_out': []})
                    away_out = stored_injuries.get('away_out', [])
                    home_out = stored_injuries.get('home_out', [])
                    out_player_ids = set(away_out + home_out)

                    # Pre-fetch bulk game logs once for "without X" historical stats lookup.
                    # get_bulk_player_game_logs() is @st.cache_data so this is free if already cached.
                    _bulk_logs_for_inj = pf_features.get_bulk_player_game_logs()

                    # Calculate injury adjustments for each player (now with efficient lookup)
                    for player_id, player_data in cached_game_predictions.items():
                        player_id_str = str(player_id)
                        player_team_id = cached_team_ids_map.get(player_id_str)

                        if not player_team_id:
                            continue

                        # Determine teammates_out and opponents_out
                        if int(player_team_id) == matchup_away_team_id:
                            teammates_out = [p for p in away_out if p != player_id_str]
                            opponents_out = home_out
                            opp_team_id = matchup_home_team_id
                        elif int(player_team_id) == matchup_home_team_id:
                            teammates_out = [p for p in home_out if p != player_id_str]
                            opponents_out = away_out
                            opp_team_id = matchup_away_team_id
                        else:
                            continue

                        # Only calculate if there are injuries
                        if teammates_out or opponents_out:
                            # Compute empirical "without X" multipliers from historical game logs.
                            # Returns None when the sample is too small (<3 games) — the function
                            # degrades gracefully to pure role-based adjustment in that case.
                            wp_stats = None
                            if teammates_out and _bulk_logs_for_inj is not None and len(_bulk_logs_for_inj) > 0:
                                try:
                                    wp_stats = wps.get_without_player_stats(
                                        player_id=player_id_str,
                                        absent_player_ids=teammates_out,
                                        bulk_game_logs=_bulk_logs_for_inj,
                                    )
                                except Exception:
                                    wp_stats = None

                            injury_adj = inj.calculate_injury_adjustments(
                                player_id=player_id_str,
                                player_team_id=int(player_team_id),
                                opponent_team_id=opp_team_id,
                                teammates_out=teammates_out,
                                opponents_out=opponents_out,
                                player_minutes_map=player_minutes_map,
                                players_df=players_df,
                                without_player_stats=wp_stats,
                            )
                            if injury_adj.get('factors'):
                                injury_adjustments_map[player_id_str] = injury_adj

                    # Build normalized statlines FIRST (before Value Plays)
                    # This ensures Value Plays use the same normalized/scaled values as Predicted Statlines
                    normalized_statlines_key = f"{game_cache_key_bvp}_normalized_statlines"

                    # Check if we have manually adjusted statlines in session state
                    if normalized_statlines_key in st.session_state:
                        statlines_list = st.session_state[normalized_statlines_key]

                        # Validate cached statlines: check if they sum to 240 per team
                        # If not, re-normalize them (they might be from before the fix)
                        away_total = sum(s['MIN'] for s in statlines_list if s.get('is_away'))
                        home_total = sum(s['MIN'] for s in statlines_list if not s.get('is_away'))
                        away_active = len([s for s in statlines_list if s.get('is_away') and s.get('MIN', 0) > 0.01])
                        home_active = len([s for s in statlines_list if not s.get('is_away') and s.get('MIN', 0) > 0.01])

                        # If totals are wrong or too many players, re-normalize
                        if (abs(away_total - 240.0) > 0.1 or abs(home_total - 240.0) > 0.1 or 
                            away_active > 10 or home_active > 10):
                            # Re-normalize the cached statlines
                            bulk_game_logs = pf_features.get_bulk_player_game_logs()
                            matchup_inj_key = f"{game_cache_key_bvp}_injuries"
                            matchup_inj = st.session_state.get('matchup_injuries_cache', {}).get(matchup_inj_key, {'away': [], 'home': []})
                            out_player_ids_revalidate = set()
                            for injury_item in matchup_inj.get('away', []) + matchup_inj.get('home', []):
                                status_lower = injury_item.get('status', '').lower()
                                if 'out' in status_lower or 'doubtful' in status_lower:
                                    if injury_item.get('player_id'):
                                        out_player_ids_revalidate.add(str(injury_item['player_id']))

                            normalize_team_minutes(
                                statlines_list,
                                target_minutes=240.0,
                                out_player_ids=out_player_ids_revalidate,
                                bulk_game_logs=bulk_game_logs,
                                game_date=game_date_str_bvp,
                                manual_adjustments=None,
                                returning_player_ids=_returning_ids_from_injury_dict(matchup_inj),
                            )
                            # Update cache with re-normalized statlines
                            st.session_state[normalized_statlines_key] = statlines_list
                    else:
                        # Build statlines list with injury-adjusted predictions
                        statlines_list = []
                        for player_id, player_data_dict in cached_game_predictions.items():
                            player_id_str = str(player_id)

                            # Get actual predictions dict (nested under 'predictions' key)
                            predictions_dict = player_data_dict.get('predictions', {})

                            # Get player info - use cached name if available, otherwise look up
                            player_name = player_data_dict.get('player_name')
                            if not player_name:
                                player_row = players_df[players_df['PERSON_ID'].astype(str) == player_id_str]
                                if len(player_row) == 0:
                                    continue
                                player_name = f"{player_row['PLAYER_FIRST_NAME'].iloc[0]} {player_row['PLAYER_LAST_NAME'].iloc[0]}"

                            # Get team info from cached data or lookup
                            team_abbr = player_data_dict.get('team_abbr')
                            if not team_abbr:
                                player_row = players_df[players_df['PERSON_ID'].astype(str) == player_id_str]
                                if len(player_row) == 0:
                                    continue
                                player_team_id = int(player_row['TEAM_ID'].iloc[0])
                                is_away = (player_team_id == matchup_away_team_id)
                                team_abbr = matchup_away_team_abbr if is_away else matchup_home_team_abbr
                            else:
                                # Determine is_away from team_abbr
                                is_away = (team_abbr == matchup_away_team_abbr)

                            # Extract base stat predictions
                            def get_pred_value(stat_key):
                                pred_obj = predictions_dict.get(stat_key)
                                if pred_obj and hasattr(pred_obj, 'value'):
                                    return pred_obj.value
                                return 0.0

                            # Get base predictions (before any injury adjustments)
                            base_pts = get_pred_value('PTS')
                            base_reb = get_pred_value('REB')
                            base_ast = get_pred_value('AST')
                            base_stl = get_pred_value('STL')
                            base_blk = get_pred_value('BLK')
                            base_tov = get_pred_value('TOV')
                            base_fg3m = get_pred_value('FG3M')
                            base_ftm = get_pred_value('FTM')

                            minutes = player_minutes_map.get(int(player_id), 25.0)
                            original_season_minutes = minutes  # Store BEFORE injury adjustments

                            # Store base stats and injury adjustments for proper scaling order
                            # We'll apply injury adjustments AFTER normalization scaling
                            injury_adj_multipliers = None
                            injury_adjusted_minutes = minutes  # Track minutes after injury boost
                            if player_id_str in injury_adjustments_map:
                                injury_adj = injury_adjustments_map[player_id_str]
                                # Store injury multipliers for later application
                                injury_adj_multipliers = {
                                    'PTS': injury_adj.get('PTS', 1.0),
                                    'REB': injury_adj.get('REB', 1.0),
                                    'AST': injury_adj.get('AST', 1.0),
                                    'STL': injury_adj.get('STL', 1.0),
                                    'BLK': injury_adj.get('BLK', 1.0),
                                    'TOV': injury_adj.get('TOV', 1.0) if 'TOV' in injury_adj else 1.0,
                                    'FG3M': injury_adj.get('FG3M', 1.0),
                                    'FTM': injury_adj.get('FTM', 1.0),
                                    'minutes_boost': injury_adj.get('minutes_boost', 0.0)
                                }
                                # Add minutes boost for initial normalization
                                minutes += injury_adj.get('minutes_boost', 0.0)
                                injury_adjusted_minutes = minutes  # Store injury-adjusted minutes

                            # For now, use base stats (injury adjustments will be applied after normalization)
                            pts = base_pts
                            reb = base_reb
                            ast = base_ast
                            stl = base_stl
                            blk = base_blk
                            tov = base_tov
                            fg3m = base_fg3m
                            ftm = base_ftm

                            # Calculate derived stats from base stats
                            pra = pts + reb + ast
                            ra = reb + ast
                            # FPTS using Underdog formula: PTS*1 + REB*1.2 + AST*1.5 + STL*3 + BLK*3 - TOV*1
                            fpts = pts * 1.0 + reb * 1.2 + ast * 1.5 + stl * 3.0 + blk * 3.0 - tov * 1.0

                            statline = {
                                'Player': player_name,
                                'Team': team_abbr,
                                'player_id': player_id_str,
                                'MIN': minutes,
                                '_original_season_minutes': original_season_minutes,  # Store for proper scaling
                                '_injury_adjusted_minutes': injury_adjusted_minutes,  # Store injury-adjusted minutes for scaling baseline
                                '_base_stats': {  # Store base stats before injury adjustments
                                    'PTS': base_pts,
                                    'REB': base_reb,
                                    'AST': base_ast,
                                    'STL': base_stl,
                                    'BLK': base_blk,
                                    'TOV': base_tov,
                                    'FG3M': base_fg3m,
                                    'FTM': base_ftm
                                },
                                '_injury_multipliers': injury_adj_multipliers,  # Store for re-application after normalization
                                'PTS': pts,  # Will be updated during normalization
                                'REB': reb,
                                'AST': ast,
                                'STL': stl,
                                'BLK': blk,
                                'TOV': tov,
                                'FG3M': fg3m,
                                'FTM': ftm,
                                'PRA': pra,
                                'RA': ra,
                                'FPTS': fpts,
                                'is_away': is_away
                            }
                            statlines_list.append(statline)

                        # Store original MIN values BEFORE normalization for comparison
                        # This ensures we can detect when user resets to original vs when normalization matches manual adjustment
                        original_mins_key = f"{game_cache_key_bvp}_original_mins"
                        if original_mins_key not in st.session_state:
                            # Store original MIN values (before any normalization or manual adjustments)
                            st.session_state[original_mins_key] = {statline['player_id']: statline['MIN'] for statline in statlines_list}

                        # Get bulk game logs for recent activity check
                        bulk_game_logs = pf_features.get_bulk_player_game_logs()

                        # Compute tanking adjustments and store for re-normalization
                        tanking_adj_key = f"{game_cache_key_bvp}_tanking_adj"
                        tanking_ctx_key = f"{game_cache_key_bvp}_tanking_ctx"
                        if tanking_adj_key not in st.session_state:
                            _t_adj, _t_ctx = compute_tanking_adjustments(
                                statlines_list,
                                matchup_away_team_id,
                                matchup_home_team_id,
                                matchup_away_team_abbr,
                                matchup_home_team_abbr,
                            )
                            st.session_state[tanking_adj_key] = _t_adj
                            st.session_state[tanking_ctx_key] = _t_ctx

                        tanking_adj = st.session_state.get(tanking_adj_key, {})

                        # Normalize minutes and scale stats using helper function
                        normalize_team_minutes(
                            statlines_list,
                            target_minutes=240.0,
                            out_player_ids=out_player_ids,
                            bulk_game_logs=bulk_game_logs,
                            game_date=game_date_str_bvp,
                            manual_adjustments=tanking_adj if tanking_adj else None,
                            returning_player_ids=_returning_ids_from_injury_dict(all_matchup_injuries),
                        )

                        # Ensure players with 0 minutes have all stats set to 0
                        for statline in statlines_list:
                            if statline.get('MIN', 0) == 0 or statline.get('MIN', 0) < 0.01:
                                statline['PTS'] = 0.0
                                statline['REB'] = 0.0
                                statline['AST'] = 0.0
                                statline['STL'] = 0.0
                                statline['BLK'] = 0.0
                                statline['TOV'] = 0.0
                                statline['FG3M'] = 0.0
                                statline['FTM'] = 0.0
                                statline['PRA'] = 0.0
                                statline['RA'] = 0.0
                                statline['FPTS'] = 0.0


                        # Store in session state
                        st.session_state[normalized_statlines_key] = statlines_list

                    # ── Injury-return estimates callout ──────────────────────────
                    _return_players = [
                        s for s in statlines_list if s.get('_injury_return_estimate')
                    ]
                    if _return_players:
                        _return_lines = []
                        for _rp in _return_players:
                            _rp_missed = _rp.get('_injury_return_games_missed', '?')
                            _rp_base   = _rp.get('_injury_return_baseline', '?')
                            _rp_proj   = round(_rp.get('MIN', 0), 1)
                            _rp_back   = _rp.get('_injury_return_games_back', 0)
                            _rp_role   = _rp.get('_injury_return_role', '?')
                            _rp_pct    = _rp.get('_injury_return_ramp_pct', '?')
                            _game_label = f"game {_rp_back + 1} back" if _rp_back > 0 else "1st game back"
                            _return_lines.append(
                                f"**{_rp['Player']}** ({_rp['Team']}) — missed {_rp_missed} games, "
                                f"{_rp_role} role ({_rp_base} min baseline), "
                                f"{_game_label} at {_rp_pct}% → **{_rp_proj} min**"
                            )
                        st.info(
                            "⚠️ **Returning Player Ramp-Up** — minutes restricted based on "
                            "absence length, role, and games since return. Use Manual Minutes to override.\n\n"
                            + "\n\n".join(f"- {l}" for l in _return_lines)
                        )

                    # Create normalized predictions dict for Value Plays
                    # This ensures Value Plays use the same normalized/scaled values
                    normalized_predictions = {}
                    for statline in statlines_list:
                        player_id_str = statline['player_id']
                        if player_id_str not in normalized_predictions:
                            normalized_predictions[player_id_str] = {
                                'predictions': {},
                                'player_name': statline['Player'],
                                'team_abbr': statline['Team']
                            }

                        # Create Prediction objects with normalized values
                        from prediction_model import Prediction
                        normalized_predictions[player_id_str]['predictions']['PTS'] = Prediction(
                            stat='PTS', value=statline['PTS'], confidence='high',
                            breakdown={'normalized': statline['PTS']}, factors={'source': 'normalized_statline'}
                        )
                        normalized_predictions[player_id_str]['predictions']['REB'] = Prediction(
                            stat='REB', value=statline['REB'], confidence='high',
                            breakdown={'normalized': statline['REB']}, factors={'source': 'normalized_statline'}
                        )
                        normalized_predictions[player_id_str]['predictions']['AST'] = Prediction(
                            stat='AST', value=statline['AST'], confidence='high',
                            breakdown={'normalized': statline['AST']}, factors={'source': 'normalized_statline'}
                        )
                        normalized_predictions[player_id_str]['predictions']['STL'] = Prediction(
                            stat='STL', value=statline['STL'], confidence='high',
                            breakdown={'normalized': statline['STL']}, factors={'source': 'normalized_statline'}
                        )
                        normalized_predictions[player_id_str]['predictions']['BLK'] = Prediction(
                            stat='BLK', value=statline['BLK'], confidence='high',
                            breakdown={'normalized': statline['BLK']}, factors={'source': 'normalized_statline'}
                        )
                        normalized_predictions[player_id_str]['predictions']['TOV'] = Prediction(
                            stat='TOV', value=statline['TOV'], confidence='high',
                            breakdown={'normalized': statline['TOV']}, factors={'source': 'normalized_statline'}
                        )
                        normalized_predictions[player_id_str]['predictions']['FG3M'] = Prediction(
                            stat='FG3M', value=statline['FG3M'], confidence='high',
                            breakdown={'normalized': statline['FG3M']}, factors={'source': 'normalized_statline'}
                        )
                        normalized_predictions[player_id_str]['predictions']['FTM'] = Prediction(
                            stat='FTM', value=statline['FTM'], confidence='high',
                            breakdown={'normalized': statline['FTM']}, factors={'source': 'normalized_statline'}
                        )
                        normalized_predictions[player_id_str]['predictions']['PRA'] = Prediction(
                            stat='PRA', value=statline['PRA'], confidence='high',
                            breakdown={'normalized': statline['PRA']}, factors={'source': 'normalized_statline'}
                        )
                        normalized_predictions[player_id_str]['predictions']['RA'] = Prediction(
                            stat='RA', value=statline['RA'], confidence='high',
                            breakdown={'normalized': statline['RA']}, factors={'source': 'normalized_statline'}
                        )
                        normalized_predictions[player_id_str]['predictions']['FPTS'] = Prediction(
                            stat='FPTS', value=statline['FPTS'], confidence='high',
                            breakdown={'normalized': statline['FPTS']}, factors={'source': 'normalized_statline'}
                        )

                    # Check if we have cached best_plays from manual recalculation
                    cached_best_plays_key = f"{game_cache_key_bvp}_best_plays"
                    if cached_best_plays_key in st.session_state:
                        best_plays = st.session_state[cached_best_plays_key]
                    else:
                        # Find best value plays using NORMALIZED predictions (no additional injury adjustments needed)
                        best_plays = pm.find_best_value_plays(
                            all_predictions=normalized_predictions,
                            all_props=cached_game_props,
                            min_edge_pct=float(min_edge),
                            confidence_filter=confidence_options if confidence_options else ['high', 'medium', 'low'],
                            stat_filter=stat_options if stat_options else ['PTS', 'REB', 'AST', 'PRA'],
                            injury_adjustments_map=None  # Already normalized, no additional adjustments
                        )
                        # Cache for future use
                        st.session_state[cached_best_plays_key] = best_plays

                    # Check for systematic bias
                    if best_plays:
                        over_count = sum(1 for p in best_plays if 'Over' in p['lean'])
                        under_count = sum(1 for p in best_plays if 'Under' in p['lean'])
                        total_count = len(best_plays)

                        if total_count > 0:
                            over_pct = (over_count / total_count) * 100
                            under_pct = (under_count / total_count) * 100
                            avg_edge = sum(p['edge'] for p in best_plays) / total_count

                            # Show bias warning if heavily skewed
                            if over_pct > 80:
                                st.warning(f"⚠️ **Potential Over-Bias**: {over_pct:.1f}% of plays are Over ({over_count}/{total_count}). Average edge: {avg_edge:+.2f}. Model may be systematically over-predicting.")
                            elif under_pct > 80:
                                st.warning(f"⚠️ **Potential Under-Bias**: {under_pct:.1f}% of plays are Under ({under_count}/{total_count}). Average edge: {avg_edge:+.2f}. Model may be systematically under-predicting.")
                            elif abs(avg_edge) > 1.5:
                                st.info(f"ℹ️ **Bias Detected**: Average edge = {avg_edge:+.2f} ({over_count} Over, {under_count} Under). This may indicate systematic prediction bias.")

                    if best_plays:
                        st.markdown(f"### 🏆 Top {min(len(best_plays), 20)} Value Plays")

                        # Sort by absolute edge % descending before taking top 20
                        sorted_plays = sorted(best_plays, key=lambda x: abs(x['edge_pct']), reverse=True)

                        # Create DataFrame for display
                        plays_df = pd.DataFrame(sorted_plays[:20])  # kept for download button

                        _top_sg_df = pd.DataFrame([{
                            'Player':  _p['player_name'],
                            'Team':    _p['team'],
                            'Stat':    _p['stat'],
                            'Pred':    round(_p['prediction'], 1),
                            'Line':    round(float(_p['line']), 1),
                            'Edge':    f"{_p['edge']:+.1f}",
                            'Edge %':  f"{_p['edge_pct']:+.1f}%",
                            'Lean':    _p['lean'],
                            'Conf':    _p['confidence'],
                        } for _p in sorted_plays[:20]])

                        def _sg_lean_style(val):
                            if 'Over' in str(val):  return f'background-color:{tc.lean_over_bg};color:{tc.lean_over_text}'
                            if 'Under' in str(val): return f'background-color:{tc.lean_under_bg};color:{tc.lean_under_text}'
                            return ''

                        st.dataframe(
                            _top_sg_df.style.map(_sg_lean_style, subset=['Lean']),
                            hide_index=True,
                            width='stretch',
                            column_config={
                                'Pred': st.column_config.NumberColumn(format="%.1f"),
                                'Line': st.column_config.NumberColumn(format="%.1f"),
                            },
                        )

                        _bvp_bulk_logs = pf_features.get_bulk_player_game_logs()
                        for _vp in sorted_plays[:20]:
                            _render_leg_with_l5(_vp, _bvp_bulk_logs)

                        # Download button for Value Plays
                        value_plays_csv = plays_df[[
                            'player_name', 'team', 'stat', 'prediction', 'line', 
                            'edge', 'edge_pct', 'lean', 'confidence'
                        ]].copy()
                        value_plays_csv.columns = [
                            'Player', 'Team', 'Stat', 'Pred', 'Line', 
                            'Edge', 'Edge %', 'Lean', 'Conf'
                        ]
                        csv_value_plays = value_plays_csv.to_csv(index=False)
                        st.download_button(
                            label="📥 Download Value Plays CSV",
                            data=csv_value_plays,
                            file_name=f"value_plays_{matchup_away_team_abbr}_vs_{matchup_home_team_abbr}_{game_date_str_bvp}.csv",
                            mime="text/csv",
                            key="download_value_plays"
                        )

                        # Summary stats
                        overs = len([p for p in best_plays if 'Over' in p['lean']])
                        unders = len([p for p in best_plays if 'Under' in p['lean']])
                        st.caption(f"📈 {overs} Over plays | 📉 {unders} Under plays | Total: {len(best_plays)} plays found")

                        # ── 3-LEG PARLAYS ─────────────────────────────────────────
                        st.markdown("---")
                        st.markdown("#### 🎰 Best 3-Leg Parlays")
                        st.caption("Each parlay uses 3 different players. No player appears in more than one parlay. Sorted by combined edge percentage.")

                        from itertools import combinations as _sg_combos

                        _sg_sorted = sorted(best_plays, key=lambda x: abs(x.get('edge_pct', 0)), reverse=True)

                        # Deduplicate (best play per player+stat) and exclude Pushes
                        _sg_seen = {}
                        _sg_deduped = []
                        for _sgp in _sg_sorted:
                            if _sgp.get('lean', '') == 'Push':
                                continue
                            if _sgp.get('prediction', 0) <= 0.1:
                                continue
                            _sgkey = (_sgp['player_id'], _sgp['stat'])
                            if _sgkey not in _sg_seen:
                                _sg_seen[_sgkey] = True
                                _sg_deduped.append(_sgp)

                        _sg_candidates = _sg_deduped[:50]
                        _sg_all_parlays = []
                        for _sgcombo in _sg_combos(_sg_candidates, 3):
                            if len({_p['player_id'] for _p in _sgcombo}) < 3:
                                continue
                            if len({_p['team'] for _p in _sgcombo}) < 2:
                                continue
                            _sgedge = sum(abs(_p['edge_pct']) for _p in _sgcombo)
                            _sg_all_parlays.append((_sgedge, list(_sgcombo)))
                        _sg_all_parlays.sort(key=lambda x: -x[0])

                        # Greedy: pick 5 non-overlapping parlays
                        _sg_best = []
                        _sg_used = set()
                        for _sgte, _sglegs in _sg_all_parlays:
                            _sgpids = {_p['player_id'] for _p in _sglegs}
                            if _sgpids & _sg_used:
                                continue
                            _sg_best.append((_sgte, _sglegs))
                            _sg_used |= _sgpids
                            if len(_sg_best) == 5:
                                break

                        if not _sg_best:
                            st.info("Not enough distinct plays to form 3-leg parlays. Try lowering the minimum edge % or adding more stat types.")
                        else:
                            for _sgrank, (_sgte, _sglegs) in enumerate(_sg_best, 1):
                                _sg_payout = round(ptl.parlay_payout_multiplier(_sglegs), 2)
                                with st.expander(
                                    f"Parlay {_sgrank}  •  Combined Edge: {_sgte:.1f}%  •  Payout: {_sg_payout:.2f}x",
                                    expanded=(_sgrank == 1),
                                ):
                                    for _sgl in _sglegs:
                                        _render_leg_with_l5(_sgl, _bvp_bulk_logs)
                                    # ── Payout override ───────────────────────────
                                    _sg_adj_payout = st.number_input(
                                        "Payout multiplier (edit if you have a boost)",
                                        value=_sg_payout,
                                        min_value=0.0,
                                        step=0.01,
                                        format="%.2f",
                                        key=f"payout_sg_{_sgrank}_{game_cache_key_bvp}",
                                    )
                                    _sg_save_key  = f"save_sg_parlay_{_sgrank}_{game_cache_key_bvp}"
                                    _sg_saved_key = f"sg_parlay_saved_{_sgrank}_{game_cache_key_bvp}"
                                    if st.session_state.get(_sg_saved_key):
                                        st.success("✅ Parlay saved to tracker")
                                    elif st.button("💾 Save Parlay", key=_sg_save_key):
                                        _sgpid = ptl.save_parlay(game_date_str_bvp, _sglegs, payout_override=float(_sg_adj_payout))
                                        if _sgpid:
                                            if game_date_str_bvp >= str(date.today()):
                                                ptl.post_parlay_to_discord(game_date_str_bvp, _sglegs, float(_sg_adj_payout))
                                            st.session_state[_sg_saved_key] = True
                                            st.rerun()
                                        else:
                                            st.error("Failed to save parlay.")

                        # Show all predicted statlines sorted by team and minutes
                        st.markdown("---")
                        st.markdown("### 📊 All Predicted Statlines")

                        # Use normalized statlines from session state (already calculated above)
                        statlines_list = st.session_state.get(normalized_statlines_key, [])

                        # Get original MIN values key (should already be stored before normalization)
                        original_mins_key = f"{game_cache_key_bvp}_original_mins"

                        # Manual Minutes Adjustment Interface
                        with st.expander("⚙️ **Manual Minutes Adjustment**", expanded=False):
                            st.caption("Edit minutes directly in the table (whole numbers). Stats scale proportionally; each team targets 240 total minutes.")

                            # Initialize manual adjustments in session state
                            manual_adjustments_key = f"{game_cache_key_bvp}_manual_minutes"
                            if manual_adjustments_key not in st.session_state:
                                st.session_state[manual_adjustments_key] = {}

                            # Game-specific editor keys so state never bleeds across matchups
                            away_editor_key = f"away_mins_editor_{game_cache_key_bvp}"
                            home_editor_key = f"home_mins_editor_{game_cache_key_bvp}"

                            def _role_label_min(baseline):
                                if baseline >= 32: return "⭐ Star"
                                if baseline >= 28: return "🔑 Starter"
                                if baseline >= 22: return "🔄 Rotation"
                                if baseline >= 15: return "🪑 Bench"
                                return "⬇ Deep"

                            def _build_mins_df(statlines_for_edit):
                                rows = []
                                for s in statlines_for_edit:
                                    pid = s['player_id']
                                    adjusted = st.session_state[manual_adjustments_key].get(pid, s['MIN'])
                                    baseline = s.get('_original_season_minutes', s['MIN'])
                                    rows.append({
                                        'Player': s['Player'],
                                        'Role': _role_label_min(s.get('_role_baseline_min', baseline)),
                                        'Minutes': int(round(adjusted)),
                                        'Season Avg': int(round(baseline)),
                                    })
                                return pd.DataFrame(rows)

                            away_statlines_edit = sorted([s for s in statlines_list if s['is_away']], key=lambda x: -x['MIN'])
                            home_statlines_edit = sorted([s for s in statlines_list if not s['is_away']], key=lambda x: -x['MIN'])

                            adj_col1, adj_col2 = st.columns(2)

                            with adj_col1:
                                st.markdown(f"**{matchup_away_team_abbr}** (Away)")
                                edited_away = st.data_editor(
                                    _build_mins_df(away_statlines_edit),
                                    column_config={
                                        'Player': st.column_config.TextColumn(disabled=True),
                                        'Role': st.column_config.TextColumn(disabled=True, width='small'),
                                        'Minutes': st.column_config.NumberColumn(min_value=0, max_value=48, step=1),
                                        'Season Avg': st.column_config.NumberColumn(disabled=True, width='small'),
                                    },
                                    hide_index=True,
                                    width='stretch',
                                    key=away_editor_key,
                                )
                                away_total = int(edited_away['Minutes'].sum())
                                delta_a = away_total - 240
                                st.caption(f"Total: **{away_total} min** {'⚠️ ' + str(abs(delta_a)) + ' over' if delta_a > 5 else ('⚠️ ' + str(abs(delta_a)) + ' short' if delta_a < -5 else '✅ on target')}")
                                # Sync edits → manual_adjustments_key
                                for i, row in edited_away.iterrows():
                                    pid = away_statlines_edit[i]['player_id']
                                    orig = away_statlines_edit[i].get('_original_season_minutes', away_statlines_edit[i]['MIN'])
                                    new_val = float(int(row['Minutes']))
                                    if abs(new_val - round(orig)) >= 1:
                                        st.session_state[manual_adjustments_key][pid] = new_val
                                    elif pid in st.session_state[manual_adjustments_key]:
                                        del st.session_state[manual_adjustments_key][pid]

                            with adj_col2:
                                st.markdown(f"**{matchup_home_team_abbr}** (Home)")
                                edited_home = st.data_editor(
                                    _build_mins_df(home_statlines_edit),
                                    column_config={
                                        'Player': st.column_config.TextColumn(disabled=True),
                                        'Role': st.column_config.TextColumn(disabled=True, width='small'),
                                        'Minutes': st.column_config.NumberColumn(min_value=0, max_value=48, step=1),
                                        'Season Avg': st.column_config.NumberColumn(disabled=True, width='small'),
                                    },
                                    hide_index=True,
                                    width='stretch',
                                    key=home_editor_key,
                                )
                                home_total = int(edited_home['Minutes'].sum())
                                delta_h = home_total - 240
                                st.caption(f"Total: **{home_total} min** {'⚠️ ' + str(abs(delta_h)) + ' over' if delta_h > 5 else ('⚠️ ' + str(abs(delta_h)) + ' short' if delta_h < -5 else '✅ on target')}")
                                # Sync edits → manual_adjustments_key
                                for i, row in edited_home.iterrows():
                                    pid = home_statlines_edit[i]['player_id']
                                    orig = home_statlines_edit[i].get('_original_season_minutes', home_statlines_edit[i]['MIN'])
                                    new_val = float(int(row['Minutes']))
                                    if abs(new_val - round(orig)) >= 1:
                                        st.session_state[manual_adjustments_key][pid] = new_val
                                    elif pid in st.session_state[manual_adjustments_key]:
                                        del st.session_state[manual_adjustments_key][pid]

                            pending = len(st.session_state[manual_adjustments_key])
                            btn_col, reset_col = st.columns([4, 1])
                            with reset_col:
                                if st.button("↩️ Reset", key="reset_all_mins"):
                                    st.session_state[manual_adjustments_key] = {}
                                    for _ek in (away_editor_key, home_editor_key):
                                        if _ek in st.session_state:
                                            del st.session_state[_ek]
                                    st.rerun()

                            with btn_col:
                                if pending:
                                    st.info(f"ℹ️ {pending} player(s) adjusted — click Recalculate to apply.")

                            # Apply manual adjustments and recalculate button
                            if st.button("🔄 Recalculate Stats & Value Plays", key="recalc_stats", type="primary"):
                                # Clear best_plays cache so it recalculates with new minutes
                                cached_best_plays_key = f"{game_cache_key_bvp}_best_plays"
                                if cached_best_plays_key in st.session_state:
                                    del st.session_state[cached_best_plays_key]

                                # Get cached predictions for regenerating base stats
                                cached_game_predictions_recalc = st.session_state.predictions_game_cache.get(game_cache_key_bvp)

                                # Create a copy of statlines_list to avoid modifying the cached version
                                statlines_list_copy = []
                                for statline in statlines_list:
                                    statline_copy = statline.copy()
                                    player_id_str = statline_copy['player_id']
                                    # Apply manual adjustments if they exist
                                    if player_id_str in st.session_state[manual_adjustments_key]:
                                        # Store the pre-manual-adjustment minutes for scaling
                                        statline_copy['_original_min'] = statline_copy['MIN']
                                        statline_copy['MIN'] = st.session_state[manual_adjustments_key][player_id_str]

                                    # Get new minutes (after manual adjustment)
                                    new_minutes = statline_copy['MIN']

                                    # Check if player needs base stats regenerated (has > 0 minutes but missing/invalid base_stats)
                                    base_stats = statline_copy.get('_base_stats')
                                    needs_base_stats = False
                                    if new_minutes > 0.01:
                                        if not base_stats:
                                            needs_base_stats = True
                                        elif all(v == 0.0 for v in base_stats.values()):
                                            # Base stats exist but are all zeros (player was initially at 0 minutes)
                                            needs_base_stats = True

                                    # Regenerate base stats from cached predictions if needed
                                    if needs_base_stats and cached_game_predictions_recalc:
                                        try:
                                            player_id_int = int(player_id_str)
                                            if player_id_int in cached_game_predictions_recalc:
                                                player_data = cached_game_predictions_recalc[player_id_int]
                                                predictions_dict = player_data.get('predictions', {})

                                                # Extract base predictions using same pattern as initial statline building
                                                def get_pred_value(stat_key):
                                                    pred_obj = predictions_dict.get(stat_key)
                                                    if pred_obj and hasattr(pred_obj, 'value'):
                                                        return pred_obj.value
                                                    return 0.0

                                                # Regenerate base stats from cached predictions
                                                statline_copy['_base_stats'] = {
                                                    'PTS': get_pred_value('PTS'),
                                                    'REB': get_pred_value('REB'),
                                                    'AST': get_pred_value('AST'),
                                                    'STL': get_pred_value('STL'),
                                                    'BLK': get_pred_value('BLK'),
                                                    'TOV': get_pred_value('TOV'),
                                                    'FG3M': get_pred_value('FG3M'),
                                                    'FTM': get_pred_value('FTM')
                                                }

                                                # Also set original season minutes if missing
                                                if '_original_season_minutes' not in statline_copy or statline_copy.get('_original_season_minutes', 0) == 0:
                                                    # Get from player_minutes_map or use new_minutes as fallback
                                                    statline_copy['_original_season_minutes'] = player_minutes_map.get(player_id_int, new_minutes)

                                                # Set injury-adjusted minutes to new_minutes if missing
                                                if '_injury_adjusted_minutes' not in statline_copy:
                                                    statline_copy['_injury_adjusted_minutes'] = new_minutes
                                        except (ValueError, KeyError, AttributeError) as e:
                                            # If regeneration fails, fall back to current stats
                                            if not base_stats:
                                                statline_copy['_base_stats'] = {
                                                    'PTS': statline_copy.get('PTS', 0.0),
                                                    'REB': statline_copy.get('REB', 0.0),
                                                    'AST': statline_copy.get('AST', 0.0),
                                                    'STL': statline_copy.get('STL', 0.0),
                                                    'BLK': statline_copy.get('BLK', 0.0),
                                                    'TOV': statline_copy.get('TOV', 0.0),
                                                    'FG3M': statline_copy.get('FG3M', 0.0),
                                                    'FTM': statline_copy.get('FTM', 0.0)
                                                }

                                    # Ensure _original_season_minutes is preserved
                                    if '_original_season_minutes' not in statline_copy or statline_copy.get('_original_season_minutes', 0) == 0:
                                        # Fallback: use _original_min if available, otherwise current MIN
                                        statline_copy['_original_season_minutes'] = statline_copy.get('_original_min', statline_copy['MIN'])

                                    # Ensure base stats exist (fallback if regeneration didn't happen)
                                    if '_base_stats' not in statline_copy:
                                        # If base stats don't exist, create them from current stats (fallback)
                                        statline_copy['_base_stats'] = {
                                            'PTS': statline_copy.get('PTS', 0.0),
                                            'REB': statline_copy.get('REB', 0.0),
                                            'AST': statline_copy.get('AST', 0.0),
                                            'STL': statline_copy.get('STL', 0.0),
                                            'BLK': statline_copy.get('BLK', 0.0),
                                            'TOV': statline_copy.get('TOV', 0.0),
                                            'FG3M': statline_copy.get('FG3M', 0.0),
                                            'FTM': statline_copy.get('FTM', 0.0)
                                        }
                                    # _injury_multipliers should already be preserved from the copy

                                    # Ensure all required stat fields exist with default values
                                    required_stats = ['PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'FG3M', 'FTM']
                                    for stat in required_stats:
                                        if stat not in statline_copy:
                                            statline_copy[stat] = 0.0

                                    statlines_list_copy.append(statline_copy)

                                # Use the copy for recalculation
                                statlines_list = statlines_list_copy

                                # Get bulk game logs for recent activity check
                                bulk_game_logs = pf_features.get_bulk_player_game_logs()

                                # Get out_player_ids from session state or reconstruct
                                matchup_inj_key = f"{game_cache_key_bvp}_injuries"
                                matchup_inj = st.session_state.get('matchup_injuries_cache', {}).get(matchup_inj_key, {'away': [], 'home': []})
                                out_player_ids_recalc = set()
                                for injury_item in matchup_inj.get('away', []) + matchup_inj.get('home', []):
                                    status_lower = injury_item.get('status', '').lower()
                                    if 'out' in status_lower or 'doubtful' in status_lower:
                                        if injury_item.get('player_id'):
                                            out_player_ids_recalc.add(str(injury_item['player_id']))

                                # Manual adjustments were already applied to statlines_list_copy above (lines 2550-2554)
                                # Now we just need to scale stats for manually adjusted players based on their new minutes
                                manual_adjustments = st.session_state[manual_adjustments_key]
                                for statline in statlines_list:
                                    player_id_str = statline['player_id']
                                    if player_id_str in manual_adjustments:
                                        # Ensure MIN matches manual adjustment exactly (protect from any modifications)
                                        new_minutes = manual_adjustments[player_id_str]
                                        statline['MIN'] = new_minutes  # Force exact value from manual_adjustments dict

                                        # Scale stats for manually adjusted players
                                        old_minutes = statline.get('_original_min', statline.get('MIN', 0))

                                        # If new minutes is 0 or very small, set all stats to 0
                                        if new_minutes <= 0.01:
                                            statline['PTS'] = 0.0
                                            statline['REB'] = 0.0
                                            statline['AST'] = 0.0
                                            statline['STL'] = 0.0
                                            statline['BLK'] = 0.0
                                            statline['TOV'] = 0.0
                                            statline['FG3M'] = 0.0
                                            statline['FTM'] = 0.0
                                            statline['PRA'] = 0.0
                                            statline['RA'] = 0.0
                                            statline['FPTS'] = 0.0
                                        elif old_minutes > 0.01:
                                            # Use base stats if available, otherwise use current stats
                                            base_stats = statline.get('_base_stats', {})
                                            if base_stats and len(base_stats) > 0:
                                                # Scale from base stats
                                                scale_factor = new_minutes / old_minutes
                                                statline['PTS'] = base_stats.get('PTS', 0.0) * scale_factor
                                                statline['REB'] = base_stats.get('REB', 0.0) * scale_factor
                                                statline['AST'] = base_stats.get('AST', 0.0) * scale_factor
                                                statline['STL'] = base_stats.get('STL', 0.0) * scale_factor
                                                statline['BLK'] = base_stats.get('BLK', 0.0) * scale_factor
                                                statline['TOV'] = base_stats.get('TOV', 0.0) * scale_factor
                                                statline['FG3M'] = base_stats.get('FG3M', 0.0) * scale_factor
                                                statline['FTM'] = base_stats.get('FTM', 0.0) * scale_factor
                                            else:
                                                # Fallback to current stats if base stats not available
                                                scale_factor = new_minutes / old_minutes
                                                statline['PTS'] = statline.get('PTS', 0.0) * scale_factor
                                                statline['REB'] = statline.get('REB', 0.0) * scale_factor
                                                statline['AST'] = statline.get('AST', 0.0) * scale_factor
                                                statline['STL'] = statline.get('STL', 0.0) * scale_factor
                                                statline['BLK'] = statline.get('BLK', 0.0) * scale_factor
                                                statline['TOV'] = statline.get('TOV', 0.0) * scale_factor
                                                statline['FG3M'] = statline.get('FG3M', 0.0) * scale_factor
                                                statline['FTM'] = statline.get('FTM', 0.0) * scale_factor

                                            # Recalculate derived stats
                                            statline['PRA'] = statline['PTS'] + statline['REB'] + statline['AST']
                                            statline['RA'] = statline['REB'] + statline['AST']
                                            statline['FPTS'] = (
                                                statline['PTS'] + 
                                                statline['REB'] * 1.2 + 
                                                statline['AST'] * 1.5 + 
                                                statline['STL'] * 3 + 
                                                statline['BLK'] * 3 - 
                                                statline['TOV']
                                            )
                                        else:
                                            # Player was at 0 minutes, but now has non-zero minutes
                                            if new_minutes > 0.01:
                                                base_stats = statline.get('_base_stats', {})
                                                if base_stats and len(base_stats) > 0 and not all(v == 0.0 for v in base_stats.values()):
                                                    # Use base_stats and scale to new_minutes
                                                    # Get scaling baseline (same logic as normalize_team_minutes)
                                                    scaling_baseline = statline.get('_injury_adjusted_minutes')
                                                    if scaling_baseline is None or scaling_baseline <= 0:
                                                        scaling_baseline = statline.get('_original_season_minutes')
                                                    if scaling_baseline is None or scaling_baseline <= 0:
                                                        scaling_baseline = 25.0  # Default baseline

                                                    scale_factor = new_minutes / scaling_baseline
                                                    statline['PTS'] = base_stats.get('PTS', 0.0) * scale_factor
                                                    statline['REB'] = base_stats.get('REB', 0.0) * scale_factor
                                                    statline['AST'] = base_stats.get('AST', 0.0) * scale_factor
                                                    statline['STL'] = base_stats.get('STL', 0.0) * scale_factor
                                                    statline['BLK'] = base_stats.get('BLK', 0.0) * scale_factor
                                                    statline['TOV'] = base_stats.get('TOV', 0.0) * scale_factor
                                                    statline['FG3M'] = base_stats.get('FG3M', 0.0) * scale_factor
                                                    statline['FTM'] = base_stats.get('FTM', 0.0) * scale_factor

                                                    # Recalculate derived stats
                                                    statline['PRA'] = statline['PTS'] + statline['REB'] + statline['AST']
                                                    statline['RA'] = statline['REB'] + statline['AST']
                                                    statline['FPTS'] = (
                                                        statline['PTS'] + 
                                                        statline['REB'] * 1.2 + 
                                                        statline['AST'] * 1.5 + 
                                                        statline['STL'] * 3 + 
                                                        statline['BLK'] * 3 - 
                                                        statline['TOV']
                                                    )
                                                else:
                                                    # No base stats available, set to 0
                                                    statline['PTS'] = 0.0
                                                    statline['REB'] = 0.0
                                                    statline['AST'] = 0.0
                                                    statline['STL'] = 0.0
                                                    statline['BLK'] = 0.0
                                                    statline['TOV'] = 0.0
                                                    statline['FG3M'] = 0.0
                                                    statline['FTM'] = 0.0
                                                    statline['PRA'] = 0.0
                                                    statline['RA'] = 0.0
                                                    statline['FPTS'] = 0.0

                                # Check if manual adjustments sum to 240 for each team
                                # If so, skip normalization entirely and lock all minutes
                                skip_normalization = False
                                if manual_adjustments_key in st.session_state and st.session_state[manual_adjustments_key]:
                                    manual_adjustments_check = st.session_state[manual_adjustments_key]

                                    # Calculate totals for each team using manual adjustments if they exist, otherwise use current MIN
                                    away_total = 0.0
                                    home_total = 0.0
                                    away_manual_count = 0
                                    home_manual_count = 0

                                    for statline in statlines_list:
                                        player_id_str = statline.get('player_id')
                                        # Use manual adjustment if exists, otherwise use current MIN from statline
                                        if player_id_str in manual_adjustments_check:
                                            current_min = manual_adjustments_check[player_id_str]
                                            if statline.get('is_away', False):
                                                away_manual_count += 1
                                            else:
                                                home_manual_count += 1
                                        else:
                                            current_min = statline.get('MIN', 0)

                                        if statline.get('is_away', False):
                                            away_total += current_min
                                        else:
                                            home_total += current_min

                                    # If both teams sum to exactly 240, skip normalization entirely
                                    if abs(away_total - 240.0) < 0.01 and abs(home_total - 240.0) < 0.01:
                                        skip_normalization = True

                                if not skip_normalization:
                                    # Merge tanking adjustments (base) with user's manual adjustments (override)
                                    _tanking_base = st.session_state.get(f"{game_cache_key_bvp}_tanking_adj", {})
                                    _user_adj = st.session_state.get(manual_adjustments_key, {})
                                    _merged_adj = {**_tanking_base, **_user_adj} if (_tanking_base or _user_adj) else None
                                    # Normalize minutes to 240 per team (but protect manual adjustments)
                                    normalize_team_minutes(
                                        statlines_list,
                                        target_minutes=240.0,
                                        out_player_ids=out_player_ids_recalc,
                                        bulk_game_logs=bulk_game_logs,
                                        game_date=game_date_str_bvp,
                                        manual_adjustments=_merged_adj,
                                        returning_player_ids=_returning_ids_from_injury_dict(all_matchup_injuries),
                                    )

                                # Ensure players with 0 minutes have all stats set to 0
                                for statline in statlines_list:
                                    if statline.get('MIN', 0) == 0 or statline.get('MIN', 0) < 0.01:
                                        statline['PTS'] = 0.0
                                        statline['REB'] = 0.0
                                        statline['AST'] = 0.0
                                        statline['STL'] = 0.0
                                        statline['BLK'] = 0.0
                                        statline['TOV'] = 0.0
                                        statline['FG3M'] = 0.0
                                        statline['FTM'] = 0.0
                                        statline['PRA'] = 0.0
                                        statline['RA'] = 0.0
                                        statline['FPTS'] = 0.0

                                # Display normalized minutes summary
                                st.success("✅ Minutes normalized to 240 per team. See normalized minutes below:")

                                # Show normalized minutes breakdown
                                norm_col1, norm_col2 = st.columns(2)

                                with norm_col1:
                                    st.markdown(f"**{matchup_away_team_abbr} Normalized Minutes:**")
                                    away_norm_total = 0.0
                                    away_norm_list = []
                                    for statline in statlines_list:
                                        if statline['is_away']:
                                            away_norm_total += statline['MIN']
                                            away_norm_list.append({
                                                'Player': statline['Player'],
                                                'MIN': statline['MIN']
                                            })
                                    # Sort by minutes descending
                                    away_norm_list.sort(key=lambda x: x['MIN'], reverse=True)
                                    for item in away_norm_list:
                                        st.write(f"{item['Player']}: {item['MIN']:.1f}")
                                    st.metric("Total", f"{away_norm_total:.1f}", delta=f"{away_norm_total - 240:.1f}" if abs(away_norm_total - 240) > 0.01 else None)

                                with norm_col2:
                                    st.markdown(f"**{matchup_home_team_abbr} Normalized Minutes:**")
                                    home_norm_total = 0.0
                                    home_norm_list = []
                                    for statline in statlines_list:
                                        if not statline['is_away']:
                                            home_norm_total += statline['MIN']
                                            home_norm_list.append({
                                                'Player': statline['Player'],
                                                'MIN': statline['MIN']
                                            })
                                    # Sort by minutes descending
                                    home_norm_list.sort(key=lambda x: x['MIN'], reverse=True)
                                    for item in home_norm_list:
                                        st.write(f"{item['Player']}: {item['MIN']:.1f}")
                                    st.metric("Total", f"{home_norm_total:.1f}", delta=f"{home_norm_total - 240:.1f}" if abs(home_norm_total - 240) > 0.01 else None)

                                # Update normalized predictions for Value Plays
                                normalized_predictions = {}
                                for statline in statlines_list:
                                    player_id_str = statline['player_id']
                                    if player_id_str not in normalized_predictions:
                                        normalized_predictions[player_id_str] = {
                                            'predictions': {},
                                            'player_name': statline['Player'],
                                            'team_abbr': statline['Team']
                                        }

                                    from prediction_model import Prediction
                                    normalized_predictions[player_id_str]['predictions']['PTS'] = Prediction(
                                        stat='PTS', value=statline['PTS'], confidence='high',
                                        breakdown={'normalized': statline['PTS']}, factors={'source': 'normalized_statline'}
                                    )
                                    normalized_predictions[player_id_str]['predictions']['REB'] = Prediction(
                                        stat='REB', value=statline['REB'], confidence='high',
                                        breakdown={'normalized': statline['REB']}, factors={'source': 'normalized_statline'}
                                    )
                                    normalized_predictions[player_id_str]['predictions']['AST'] = Prediction(
                                        stat='AST', value=statline['AST'], confidence='high',
                                        breakdown={'normalized': statline['AST']}, factors={'source': 'normalized_statline'}
                                    )
                                    normalized_predictions[player_id_str]['predictions']['STL'] = Prediction(
                                        stat='STL', value=statline['STL'], confidence='high',
                                        breakdown={'normalized': statline['STL']}, factors={'source': 'normalized_statline'}
                                    )
                                    normalized_predictions[player_id_str]['predictions']['BLK'] = Prediction(
                                        stat='BLK', value=statline['BLK'], confidence='high',
                                        breakdown={'normalized': statline['BLK']}, factors={'source': 'normalized_statline'}
                                    )
                                    normalized_predictions[player_id_str]['predictions']['TOV'] = Prediction(
                                        stat='TOV', value=statline['TOV'], confidence='high',
                                        breakdown={'normalized': statline['TOV']}, factors={'source': 'normalized_statline'}
                                    )
                                    normalized_predictions[player_id_str]['predictions']['FG3M'] = Prediction(
                                        stat='FG3M', value=statline['FG3M'], confidence='high',
                                        breakdown={'normalized': statline['FG3M']}, factors={'source': 'normalized_statline'}
                                    )
                                    normalized_predictions[player_id_str]['predictions']['FTM'] = Prediction(
                                        stat='FTM', value=statline['FTM'], confidence='high',
                                        breakdown={'normalized': statline['FTM']}, factors={'source': 'normalized_statline'}
                                    )
                                    normalized_predictions[player_id_str]['predictions']['PRA'] = Prediction(
                                        stat='PRA', value=statline['PRA'], confidence='high',
                                        breakdown={'normalized': statline['PRA']}, factors={'source': 'normalized_statline'}
                                    )
                                    normalized_predictions[player_id_str]['predictions']['RA'] = Prediction(
                                        stat='RA', value=statline['RA'], confidence='high',
                                        breakdown={'normalized': statline['RA']}, factors={'source': 'normalized_statline'}
                                    )
                                    normalized_predictions[player_id_str]['predictions']['FPTS'] = Prediction(
                                        stat='FPTS', value=statline['FPTS'], confidence='high',
                                        breakdown={'normalized': statline['FPTS']}, factors={'source': 'normalized_statline'}
                                    )

                                # Recalculate Value Plays with updated normalized_predictions

                                best_plays = pm.find_best_value_plays(
                                    all_predictions=normalized_predictions,
                                    all_props=cached_game_props,
                                    min_edge_pct=float(min_edge),
                                    confidence_filter=confidence_options if confidence_options else ['high', 'medium', 'low'],
                                    stat_filter=stat_options if stat_options else ['PTS', 'REB', 'AST', 'PRA'],
                                    injury_adjustments_map=None
                                )

                                # CRITICAL: Reapply manual adjustments AFTER normalization to ensure they're preserved
                                # Normalization might have modified manual adjustment values, so restore them
                                manual_adjustments_reapplied = False
                                if manual_adjustments_key in st.session_state and st.session_state[manual_adjustments_key]:
                                    for statline in statlines_list:
                                        player_id_str = statline.get('player_id')
                                        if player_id_str in st.session_state[manual_adjustments_key]:
                                            manual_min = st.session_state[manual_adjustments_key][player_id_str]
                                            old_statline_min = statline.get('MIN', 0)

                                            # Only reapply if different (normalization might have changed it)
                                            if abs(manual_min - old_statline_min) > 0.01:
                                                statline['MIN'] = manual_min  # Force exact manual adjustment value
                                                manual_adjustments_reapplied = True

                                                # Recalculate stats for this player based on new minutes
                                                # Use CURRENT normalized stats and minutes (not base_stats) for accurate scaling
                                                old_minutes = old_statline_min  # Current normalized minutes before manual adjustment
                                                new_minutes = manual_min

                                                if new_minutes > 0.01 and old_minutes > 0.01:
                                                    # Scale from CURRENT normalized stats (which already account for normalization)
                                                    # This ensures stats scale correctly relative to the current normalized state
                                                    scale_factor = new_minutes / old_minutes
                                                    statline['PTS'] = statline.get('PTS', 0.0) * scale_factor
                                                    statline['REB'] = statline.get('REB', 0.0) * scale_factor
                                                    statline['AST'] = statline.get('AST', 0.0) * scale_factor
                                                    statline['STL'] = statline.get('STL', 0.0) * scale_factor
                                                    statline['BLK'] = statline.get('BLK', 0.0) * scale_factor
                                                    statline['TOV'] = statline.get('TOV', 0.0) * scale_factor
                                                    statline['FG3M'] = statline.get('FG3M', 0.0) * scale_factor
                                                    statline['FTM'] = statline.get('FTM', 0.0) * scale_factor

                                                    # Recalculate derived stats
                                                    statline['PRA'] = statline['PTS'] + statline['REB'] + statline['AST']
                                                    statline['RA'] = statline['REB'] + statline['AST']
                                                    statline['FPTS'] = (
                                                        statline['PTS'] + 
                                                        statline['REB'] * 1.2 + 
                                                        statline['AST'] * 1.5 + 
                                                        statline['STL'] * 3 + 
                                                        statline['BLK'] * 3 - 
                                                        statline['TOV']
                                                    )

                                # If manual adjustments were reapplied, rebuild normalized_predictions and recalculate value plays
                                if manual_adjustments_reapplied:
                                    # Rebuild normalized_predictions with updated statlines
                                    normalized_predictions = {}
                                    for statline in statlines_list:
                                        player_id_str = statline['player_id']
                                        if player_id_str not in normalized_predictions:
                                            normalized_predictions[player_id_str] = {
                                                'predictions': {},
                                                'player_name': statline['Player'],
                                                'team_abbr': statline['Team']
                                            }

                                        from prediction_model import Prediction
                                        normalized_predictions[player_id_str]['predictions']['PTS'] = Prediction(
                                            stat='PTS', value=statline['PTS'], confidence='high',
                                            breakdown={'normalized': statline['PTS']}, factors={'source': 'normalized_statline'}
                                        )
                                        normalized_predictions[player_id_str]['predictions']['REB'] = Prediction(
                                            stat='REB', value=statline['REB'], confidence='high',
                                            breakdown={'normalized': statline['REB']}, factors={'source': 'normalized_statline'}
                                        )
                                        normalized_predictions[player_id_str]['predictions']['AST'] = Prediction(
                                            stat='AST', value=statline['AST'], confidence='high',
                                            breakdown={'normalized': statline['AST']}, factors={'source': 'normalized_statline'}
                                        )
                                        normalized_predictions[player_id_str]['predictions']['STL'] = Prediction(
                                            stat='STL', value=statline['STL'], confidence='high',
                                            breakdown={'normalized': statline['STL']}, factors={'source': 'normalized_statline'}
                                        )
                                        normalized_predictions[player_id_str]['predictions']['BLK'] = Prediction(
                                            stat='BLK', value=statline['BLK'], confidence='high',
                                            breakdown={'normalized': statline['BLK']}, factors={'source': 'normalized_statline'}
                                        )
                                        normalized_predictions[player_id_str]['predictions']['TOV'] = Prediction(
                                            stat='TOV', value=statline['TOV'], confidence='high',
                                            breakdown={'normalized': statline['TOV']}, factors={'source': 'normalized_statline'}
                                        )
                                        normalized_predictions[player_id_str]['predictions']['FG3M'] = Prediction(
                                            stat='FG3M', value=statline['FG3M'], confidence='high',
                                            breakdown={'normalized': statline['FG3M']}, factors={'source': 'normalized_statline'}
                                        )
                                        normalized_predictions[player_id_str]['predictions']['FTM'] = Prediction(
                                            stat='FTM', value=statline['FTM'], confidence='high',
                                            breakdown={'normalized': statline['FTM']}, factors={'source': 'normalized_statline'}
                                        )
                                        normalized_predictions[player_id_str]['predictions']['PRA'] = Prediction(
                                            stat='PRA', value=statline['PRA'], confidence='high',
                                            breakdown={'normalized': statline['PRA']}, factors={'source': 'normalized_statline'}
                                        )
                                        normalized_predictions[player_id_str]['predictions']['RA'] = Prediction(
                                            stat='RA', value=statline['RA'], confidence='high',
                                            breakdown={'normalized': statline['RA']}, factors={'source': 'normalized_statline'}
                                        )
                                        normalized_predictions[player_id_str]['predictions']['FPTS'] = Prediction(
                                            stat='FPTS', value=statline['FPTS'], confidence='high',
                                            breakdown={'normalized': statline['FPTS']}, factors={'source': 'normalized_statline'}
                                        )

                                    # Recalculate value plays with updated normalized_predictions
                                    best_plays = pm.find_best_value_plays(
                                        all_predictions=normalized_predictions,
                                        all_props=cached_game_props,
                                        min_edge_pct=float(min_edge),
                                        confidence_filter=confidence_options if confidence_options else ['high', 'medium', 'low'],
                                        stat_filter=stat_options if stat_options else ['PTS', 'REB', 'AST', 'PRA'],
                                        injury_adjustments_map=None
                                    )

                                # Update session state
                                st.session_state[normalized_statlines_key] = statlines_list
                                st.session_state[f"{game_cache_key_bvp}_normalized_predictions"] = normalized_predictions
                                st.session_state[f"{game_cache_key_bvp}_best_plays"] = best_plays

                                st.rerun()

                            # Reset button
                            if st.button("🔄 Reset to Original", key="reset_minutes"):
                                st.session_state[manual_adjustments_key] = {}
                                st.rerun()

                        # Filter out players with 0 minutes before displaying
                        statlines_list_filtered = [s for s in statlines_list if s.get('MIN', 0) > 0.01]

                        # Sort: away team first (minutes descending), then home team (minutes descending)
                        statlines_list_filtered.sort(key=lambda x: (not x['is_away'], -x['MIN']))

                        # Create DataFrame from filtered list
                        statlines_df = pd.DataFrame(statlines_list_filtered)
                        display_statlines_df = statlines_df[['Player', 'Team', 'MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'FG3M', 'FTM', 'PRA', 'FPTS']].copy()

                        # Format numbers
                        for col in ['MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'FG3M', 'FTM', 'PRA', 'FPTS']:
                            display_statlines_df[col] = display_statlines_df[col].apply(lambda x: f"{x:.1f}")

                        st.dataframe(display_statlines_df, width='stretch', hide_index=True)

                        # Download button for Predicted Statlines (also filtered)
                        csv_statlines = statlines_df[['Player', 'Team', 'MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'FG3M', 'FTM', 'PRA', 'FPTS']].copy()
                        csv_statlines_str = csv_statlines.to_csv(index=False)
                        st.download_button(
                            label="📥 Download Predicted Statlines CSV",
                            data=csv_statlines_str,
                            file_name=f"predicted_statlines_{matchup_away_team_abbr}_vs_{matchup_home_team_abbr}_{game_date_str_bvp}.csv",
                            mime="text/csv",
                            key="download_statlines"
                        )

                        # Download button for Manual Adjustments
                        manual_adjustments_key = f"{game_cache_key_bvp}_manual_minutes"
                        if manual_adjustments_key in st.session_state and st.session_state[manual_adjustments_key]:
                            manual_adjustments = st.session_state[manual_adjustments_key]
                            statlines_list_for_export = st.session_state.get(normalized_statlines_key, statlines_list)

                            # Create DataFrame with manual adjustments
                            manual_adjustments_data = []
                            for statline in statlines_list_for_export:
                                player_id_str = statline.get('player_id')
                                player_name = statline.get('Player', 'Unknown')
                                team = statline.get('Team', 'Unknown')
                                original_min = statline.get('_original_min', statline.get('MIN', 0))
                                current_min = statline.get('MIN', 0)

                                if player_id_str in manual_adjustments:
                                    adjusted_min = manual_adjustments[player_id_str]
                                    difference = adjusted_min - original_min
                                else:
                                    adjusted_min = original_min
                                    difference = 0.0

                                manual_adjustments_data.append({
                                    'Player': player_name,
                                    'Team': team,
                                    'Original_Minutes': original_min,
                                    'Manually_Adjusted_Minutes': adjusted_min,
                                    'Difference': difference,
                                    'Current_Projected_Minutes': current_min
                                })

                            if manual_adjustments_data:
                                manual_adjustments_df = pd.DataFrame(manual_adjustments_data)
                                # Sort by team, then by current minutes descending
                                manual_adjustments_df = manual_adjustments_df.sort_values(['Team', 'Current_Projected_Minutes'], ascending=[True, False])

                                csv_manual_adjustments = manual_adjustments_df.to_csv(index=False)
                                st.download_button(
                                    label="📥 Download Manual Minute Adjustments CSV",
                                    data=csv_manual_adjustments,
                                    file_name=f"manual_adjustments_{matchup_away_team_abbr}_vs_{matchup_home_team_abbr}_{game_date_str_bvp}.csv",
                                    mime="text/csv",
                                    key="download_manual_adjustments"
                                )

                        # Debug output for manual adjustments (always visible)
                        if manual_adjustments_key in st.session_state and st.session_state[manual_adjustments_key]:
                            manual_adjustments = st.session_state[manual_adjustments_key]
                            statlines_list_debug = st.session_state.get(normalized_statlines_key, [])
                            cached_game_predictions_debug = st.session_state.predictions_game_cache.get(game_cache_key_bvp)

                            with st.expander("🔍 Debug: Manual Adjustments Details", expanded=False):
                                st.write("### Players with Manual Minute Adjustments")
                                for statline in statlines_list_debug:
                                    player_id_str = statline.get('player_id')
                                    if player_id_str in manual_adjustments:
                                        player_name = statline.get('Player', 'Unknown')
                                        old_min = statline.get('_original_min', statline.get('MIN', 0))
                                        new_min = manual_adjustments[player_id_str]

                                        base_stats = statline.get('_base_stats', {})
                                        scaling_baseline = statline.get('_injury_adjusted_minutes')
                                        if scaling_baseline is None or scaling_baseline <= 0:
                                            scaling_baseline = statline.get('_original_season_minutes')
                                        if scaling_baseline is None or scaling_baseline <= 0:
                                            scaling_baseline = 25.0

                                        st.write(f"**{player_name}** (ID: {player_id_str})")
                                        st.write(f"- Minutes: {old_min:.1f} → {new_min:.1f}")
                                        st.write(f"- Base stats exist: {bool(base_stats and len(base_stats) > 0)}")
                                        if base_stats and len(base_stats) > 0:
                                            st.write(f"- Base stats: PTS={base_stats.get('PTS', 0):.1f}, REB={base_stats.get('REB', 0):.1f}, AST={base_stats.get('AST', 0):.1f}, STL={base_stats.get('STL', 0):.1f}, BLK={base_stats.get('BLK', 0):.1f}, TOV={base_stats.get('TOV', 0):.1f}")
                                        st.write(f"- Scaling baseline: {scaling_baseline:.1f}")
                                        if old_min > 0.01:
                                            st.write(f"- Scale factor: {new_min / old_min:.3f}")
                                        elif base_stats and len(base_stats) > 0 and not all(v == 0.0 for v in base_stats.values()):
                                            st.write(f"- Scale factor (0→nonzero): {new_min / scaling_baseline:.3f}")

                                        # Show current stats
                                        st.write(f"- Current stats: PTS={statline.get('PTS', 0):.1f}, REB={statline.get('REB', 0):.1f}, AST={statline.get('AST', 0):.1f}, STL={statline.get('STL', 0):.1f}, BLK={statline.get('BLK', 0):.1f}, TOV={statline.get('TOV', 0):.1f}, FPTS={statline.get('FPTS', 0):.1f}")

                                        # Check if player exists in cached predictions
                                        player_in_cache = False
                                        if cached_game_predictions_debug:
                                            try:
                                                player_id_int = int(player_id_str)
                                                player_in_cache = player_id_int in cached_game_predictions_debug
                                            except:
                                                pass
                                        st.write(f"- Player in cached predictions: {player_in_cache}")
                                        st.write("---")

                        # Value Plays section after manual adjustments
                        # Only show if manual adjustments exist or predictions have been recalculated
                        if manual_adjustments_key in st.session_state and st.session_state[manual_adjustments_key]:
                            # Reload statlines_list from session state to ensure we have the latest version with manual adjustments applied
                            statlines_list_updated = st.session_state.get(normalized_statlines_key, statlines_list)

                            # Check if we have cached game props and predictions
                            cached_game_props_updated = st.session_state.odds_game_cache.get(game_cache_key_bvp)
                            cached_game_predictions_updated = st.session_state.predictions_game_cache.get(game_cache_key_bvp)

                            if cached_game_props_updated is not None and cached_game_predictions_updated is not None:
                                # Build normalized predictions dict from current statlines (includes manual adjustments)
                                updated_normalized_predictions = {}
                                for statline in statlines_list_updated:
                                    player_id_str = statline['player_id']
                                    # Only include players with minutes > 0
                                    if statline.get('MIN', 0) > 0.01:
                                        if player_id_str not in updated_normalized_predictions:
                                            updated_normalized_predictions[player_id_str] = {
                                                'predictions': {},
                                                'player_name': statline['Player'],
                                                'team_abbr': statline['Team']
                                            }

                                        from prediction_model import Prediction
                                        updated_normalized_predictions[player_id_str]['predictions']['PTS'] = Prediction(
                                            stat='PTS', value=statline['PTS'], confidence='high',
                                            breakdown={'normalized': statline['PTS']}, factors={'source': 'normalized_statline'}
                                        )
                                        updated_normalized_predictions[player_id_str]['predictions']['REB'] = Prediction(
                                            stat='REB', value=statline['REB'], confidence='high',
                                            breakdown={'normalized': statline['REB']}, factors={'source': 'normalized_statline'}
                                        )
                                        updated_normalized_predictions[player_id_str]['predictions']['AST'] = Prediction(
                                            stat='AST', value=statline['AST'], confidence='high',
                                            breakdown={'normalized': statline['AST']}, factors={'source': 'normalized_statline'}
                                        )
                                        updated_normalized_predictions[player_id_str]['predictions']['STL'] = Prediction(
                                            stat='STL', value=statline['STL'], confidence='high',
                                            breakdown={'normalized': statline['STL']}, factors={'source': 'normalized_statline'}
                                        )
                                        updated_normalized_predictions[player_id_str]['predictions']['BLK'] = Prediction(
                                            stat='BLK', value=statline['BLK'], confidence='high',
                                            breakdown={'normalized': statline['BLK']}, factors={'source': 'normalized_statline'}
                                        )
                                        updated_normalized_predictions[player_id_str]['predictions']['TOV'] = Prediction(
                                            stat='TOV', value=statline['TOV'], confidence='high',
                                            breakdown={'normalized': statline['TOV']}, factors={'source': 'normalized_statline'}
                                        )
                                        updated_normalized_predictions[player_id_str]['predictions']['FG3M'] = Prediction(
                                            stat='FG3M', value=statline['FG3M'], confidence='high',
                                            breakdown={'normalized': statline['FG3M']}, factors={'source': 'normalized_statline'}
                                        )
                                        updated_normalized_predictions[player_id_str]['predictions']['FTM'] = Prediction(
                                            stat='FTM', value=statline['FTM'], confidence='high',
                                            breakdown={'normalized': statline['FTM']}, factors={'source': 'normalized_statline'}
                                        )
                                        updated_normalized_predictions[player_id_str]['predictions']['PRA'] = Prediction(
                                            stat='PRA', value=statline['PRA'], confidence='high',
                                            breakdown={'normalized': statline['PRA']}, factors={'source': 'normalized_statline'}
                                        )
                                        updated_normalized_predictions[player_id_str]['predictions']['RA'] = Prediction(
                                            stat='RA', value=statline['RA'], confidence='high',
                                            breakdown={'normalized': statline['RA']}, factors={'source': 'normalized_statline'}
                                        )
                                        updated_normalized_predictions[player_id_str]['predictions']['FPTS'] = Prediction(
                                            stat='FPTS', value=statline['FPTS'], confidence='high',
                                            breakdown={'normalized': statline['FPTS']}, factors={'source': 'normalized_statline'}
                                        )

                                # Get filter values from session state (same as original Value Plays section)
                                min_edge_updated = st.session_state.get('bvp_min_edge', 5)
                                confidence_options_updated = st.session_state.get('bvp_confidence', ['high', 'medium'])
                                stat_options_updated = st.session_state.get('bvp_stats', ['PTS', 'REB', 'AST', 'PRA', 'RA', 'FG3M', 'FTM', 'FPTS'])

                                # Find best value plays using updated predictions
                                updated_best_plays = pm.find_best_value_plays(
                                    all_predictions=updated_normalized_predictions,
                                    all_props=cached_game_props_updated,
                                    min_edge_pct=float(min_edge_updated),
                                    confidence_filter=confidence_options_updated if confidence_options_updated else ['high', 'medium', 'low'],
                                    stat_filter=stat_options_updated if stat_options_updated else ['PTS', 'REB', 'AST', 'PRA'],
                                    injury_adjustments_map=None  # Already normalized, no additional adjustments
                                )

                                # Display updated value plays
                                with st.expander("🎯 **Value Plays (After Manual Adjustments)**", expanded=True):
                                    if updated_best_plays:
                                        st.markdown(f"### 🏆 Top {min(len(updated_best_plays), 20)} Value Plays")

                                        # Sort by absolute edge % descending before taking top 20
                                        sorted_plays = sorted(updated_best_plays, key=lambda x: abs(x['edge_pct']), reverse=True)

                                        # Create DataFrame for display
                                        plays_df = pd.DataFrame(sorted_plays[:20])  # Top 20

                                        # Format the display
                                        display_df = plays_df[[
                                            'player_name', 'team', 'stat', 'prediction', 'line', 
                                            'edge', 'edge_pct', 'lean', 'confidence'
                                        ]].copy()

                                        display_df.columns = [
                                            'Player', 'Team', 'Stat', 'Pred', 'Line', 
                                            'Edge', 'Edge %', 'Lean', 'Conf'
                                        ]

                                        # Map stat codes to display names (for Underdog clarity)
                                        stat_display_names = {
                                            'PTS': 'Points',
                                            'REB': 'Rebounds',
                                            'AST': 'Assists',
                                            'PRA': 'Points + Rebounds + Assists',
                                            'RA': 'Rebounds + Assists',
                                            'STL': 'Steals',
                                            'BLK': 'Blocks',
                                            'FG3M': '3-Pointers Made',
                                            'FTM': 'Free Throws Made',
                                            'FPTS': 'Fantasy Points'
                                        }

                                        # Apply stat name mapping
                                        display_df['Stat'] = display_df['Stat'].map(stat_display_names).fillna(display_df['Stat'])

                                        # Format columns - all numbers formatted to consistent decimal places
                                        display_df['Pred'] = display_df['Pred'].apply(lambda x: f"{x:.1f}")
                                        display_df['Line'] = display_df['Line'].apply(lambda x: f"{x:.1f}")
                                        # Keep edge signed (not absolute) so we can see over/under direction
                                        display_df['Edge'] = display_df['Edge'].apply(lambda x: f"{x:+.1f}")
                                        # Edge % should be absolute for sorting, but we'll display signed
                                        display_df['Edge %'] = display_df['Edge %'].apply(lambda x: f"{abs(x) / 100:.3f}")
                                        display_df['Conf'] = display_df['Conf'].str.capitalize()

                                        # Style function for lean column
                                        def style_lean_updated(row):
                                            styles = [''] * len(row)
                                            lean_idx = display_df.columns.get_loc('Lean')
                                            lean_val = row['Lean']

                                            if 'Strong Over' in lean_val:
                                                styles[lean_idx] = 'background-color: rgba(46, 125, 50, 0.4); font-weight: bold'
                                            elif 'Lean Over' in lean_val:
                                                styles[lean_idx] = 'background-color: rgba(76, 175, 80, 0.3)'
                                            elif 'Strong Under' in lean_val:
                                                styles[lean_idx] = 'background-color: rgba(183, 28, 28, 0.4); font-weight: bold'
                                            elif 'Lean Under' in lean_val:
                                                styles[lean_idx] = 'background-color: rgba(244, 67, 54, 0.3)'

                                            # Also color confidence
                                            conf_idx = display_df.columns.get_loc('Conf')
                                            if row['Conf'] == 'High':
                                                styles[conf_idx] = 'background-color: rgba(33, 150, 243, 0.3)'
                                            elif row['Conf'] == 'Medium':
                                                styles[conf_idx] = 'background-color: rgba(255, 193, 7, 0.3)'

                                            return styles

                                        styled_plays = display_df.style.apply(style_lean_updated, axis=1)
                                        st.dataframe(styled_plays, width='stretch', hide_index=True)

                                        # Download button for Value Plays
                                        value_plays_csv = plays_df[[
                                            'player_name', 'team', 'stat', 'prediction', 'line', 
                                            'edge', 'edge_pct', 'lean', 'confidence'
                                        ]].copy()
                                        value_plays_csv.columns = [
                                            'Player', 'Team', 'Stat', 'Pred', 'Line', 
                                            'Edge', 'Edge %', 'Lean', 'Conf'
                                        ]
                                        csv_value_plays = value_plays_csv.to_csv(index=False)
                                        st.download_button(
                                            label="📥 Download Value Plays CSV (After Adjustments)",
                                            data=csv_value_plays,
                                            file_name=f"value_plays_updated_{matchup_away_team_abbr}_vs_{matchup_home_team_abbr}_{game_date_str_bvp}.csv",
                                            mime="text/csv",
                                            key="download_value_plays_updated"
                                        )

                                        # Summary stats
                                        overs = len([p for p in updated_best_plays if 'Over' in p['lean']])
                                        unders = len([p for p in updated_best_plays if 'Under' in p['lean']])
                                        st.caption(f"📈 {overs} Over plays | 📉 {unders} Under plays | Total: {len(updated_best_plays)} plays found")
                                    else:
                                        st.info("No plays found matching your filters. Try lowering the minimum edge % or expanding filters.")

                        # Calculate team totals
                        st.markdown("---")
                        st.markdown("### 🏀 Predicted Final Score")

                        # Aggregate points by team (use full statlines_list, not filtered, for accurate totals)
                        statlines_df_full = pd.DataFrame(statlines_list)
                        away_total_pts = statlines_df_full[statlines_df_full['is_away'] == True]['PTS'].sum()
                        home_total_pts = statlines_df_full[statlines_df_full['is_away'] == False]['PTS'].sum()
                        total_score = away_total_pts + home_total_pts

                        # Team-level sanity checks
                        # Typical NBA team totals: 100-130 points per game
                        # If predicted total is way outside this range, show warning
                        if away_total_pts > 140 or home_total_pts > 140:
                            st.warning(f"⚠️ **Unusually High Prediction**: Team totals exceed 140 points. This may indicate over-adjustment from injuries or other factors.")
                        elif total_score > 280:
                            st.warning(f"⚠️ **Unusually High Total**: Combined score ({total_score:.1f}) exceeds typical NBA game totals (200-260). Model may be over-predicting.")

                        # Get game lines (spread and total) from The Odds API
                        game_lines_total = None
                        game_lines_spread = None
                        try:
                            # Get events for the date
                            events, error = vl.get_nba_events(game_date_str_bvp)
                            if not error and events:
                                # Find the matching event
                                event = vl.find_event_for_matchup(events, matchup_home_team_abbr, matchup_away_team_abbr)
                                if event:
                                    event_id = event['id']

                                    # Fetch odds for game lines (totals and spreads) - FREE, doesn't cost credits
                                    url = f"{vl.ODDS_API_BASE}/sports/{vl.SPORT}/events/{event_id}/odds"
                                    params = {
                                        'apiKey': vl.ODDS_API_KEY,
                                        'regions': 'us',
                                        'bookmakers': 'draftkings',
                                        'markets': 'totals,spreads',
                                        'oddsFormat': 'american',
                                        'dateFormat': 'iso'
                                    }

                                    response = requests.get(url, params=params, timeout=10)

                                    if response.status_code == 200:
                                        data = response.json()

                                        if 'bookmakers' in data and len(data['bookmakers']) > 0:
                                            bookmaker = data['bookmakers'][0]

                                            if 'markets' in bookmaker:
                                                for market in bookmaker['markets']:
                                                    if market['key'] == 'totals':
                                                        if 'outcomes' in market and len(market['outcomes']) > 0:
                                                            game_lines_total = market['outcomes'][0].get('point', None)
                                                            break

                                                    if market['key'] == 'spreads':
                                                        if 'outcomes' in market:
                                                            for outcome in market['outcomes']:
                                                                # Find the home team spread
                                                                if outcome.get('name') == matchup_home_team_abbr:
                                                                    game_lines_spread = outcome.get('point', None)
                                                                    break
                                                            if game_lines_spread is None and len(market['outcomes']) > 0:
                                                                game_lines_spread = market['outcomes'][0].get('point', None)
                        except Exception as e:
                            # Silently fail - game lines are optional
                            pass

                        # Display predicted score
                        score_col1, score_col2, score_col3 = st.columns(3)

                        with score_col1:
                            st.metric(
                                label=f"{matchup_away_team_abbr} (Away)",
                                value=f"{away_total_pts:.1f}",
                                delta=None
                            )

                        with score_col2:
                            st.metric(
                                label=f"{matchup_home_team_abbr} (Home)",
                                value=f"{home_total_pts:.1f}",
                                delta=None
                            )

                        with score_col3:
                            st.metric(
                                label="Total",
                                value=f"{total_score:.1f}",
                                delta=None
                            )

                        # Compare to Vegas lines
                        if game_lines_total is not None or game_lines_spread is not None:
                            st.markdown("**📊 Comparison to Vegas Lines:**")

                            comparison_lines = []

                            if game_lines_total is not None:
                                total_diff = total_score - game_lines_total
                                total_lean = "Over" if total_diff > 0 else "Under"
                                comparison_lines.append(f"**Total**: Predicted {total_score:.1f} vs Line {game_lines_total:.1f} ({total_diff:+.1f}, **{total_lean}**)")

                            if game_lines_spread is not None:
                                # Spread is from home team perspective
                                # If line is -7.5, that means home team is favored by 7.5 (home needs to win by 7.5+)
                                # If line is +7.5, that means away team is favored by 7.5 (home can lose by up to 7.5)
                                predicted_spread_home_perspective = home_total_pts - away_total_pts

                                # Determine which team is favored and calculate spread from favored team's perspective
                                if game_lines_spread < 0:
                                    # Home is favored (negative line, e.g., -5.5)
                                    favored_team = matchup_home_team_abbr
                                    underdog_team = matchup_away_team_abbr

                                    if predicted_spread_home_perspective >= 0:
                                        # Home won or tied - spread is negative from favored perspective
                                        predicted_spread_from_favored = -predicted_spread_home_perspective
                                    else:
                                        # Home lost (underdog won) - spread is negative from favored perspective
                                        predicted_spread_from_favored = predicted_spread_home_perspective

                                    line_from_favored = game_lines_spread  # Already negative (e.g., -5.5)

                                    # Determine covering team
                                    if predicted_spread_home_perspective >= abs(game_lines_spread):
                                        # Home covers: won by enough
                                        covering_team = favored_team
                                        covering_margin = predicted_spread_home_perspective - abs(game_lines_spread)
                                    else:
                                        # Underdog covers: home didn't win by enough or lost
                                        covering_team = underdog_team
                                        if predicted_spread_home_perspective < 0:
                                            # Home lost - underdog covers by line + margin
                                            covering_margin = abs(game_lines_spread) + abs(predicted_spread_home_perspective)
                                        else:
                                            # Home won but didn't cover
                                            covering_margin = abs(game_lines_spread) - predicted_spread_home_perspective
                                else:
                                    # Away is favored (positive line, e.g., +5.5)
                                    favored_team = matchup_away_team_abbr
                                    underdog_team = matchup_home_team_abbr
                                    predicted_spread_away_perspective = away_total_pts - home_total_pts

                                    if predicted_spread_away_perspective >= 0:
                                        # Away won or tied - spread is negative from favored perspective
                                        predicted_spread_from_favored = -predicted_spread_away_perspective
                                    else:
                                        # Away lost (underdog won) - spread is negative from favored perspective
                                        predicted_spread_from_favored = predicted_spread_away_perspective

                                    line_from_favored = -abs(game_lines_spread)  # Convert to negative (e.g., -5.5)

                                    # Determine covering team
                                    if predicted_spread_away_perspective >= abs(game_lines_spread):
                                        # Away covers: won by enough
                                        covering_team = favored_team
                                        covering_margin = predicted_spread_away_perspective - abs(game_lines_spread)
                                    else:
                                        # Underdog covers: away didn't win by enough or lost
                                        covering_team = underdog_team
                                        if predicted_spread_away_perspective < 0:
                                            # Away lost - underdog covers by line + margin
                                            covering_margin = abs(game_lines_spread) + abs(predicted_spread_away_perspective)
                                        else:
                                            # Away won but didn't cover
                                            covering_margin = abs(game_lines_spread) - predicted_spread_away_perspective

                                # Format: Show predicted spread from winning team's perspective if underdog wins, otherwise from favored team's perspective
                                if covering_team != favored_team and predicted_spread_from_favored < 0:
                                    # Underdog won - show from underdog's perspective
                                    # Underdog was +abs(line), won by abs(margin), so spread is +abs(line) + abs(margin)
                                    underdog_spread = abs(line_from_favored) + abs(predicted_spread_from_favored)
                                    underdog_line = abs(line_from_favored)
                                    comparison_lines.append(f"**Spread**: {covering_team} +{underdog_spread:.1f} vs Line +{underdog_line:.1f} ({covering_team} +{abs(predicted_spread_from_favored):.1f}, **{covering_team} covers**)")
                                else:
                                    # Favored team covers or won - show from favored team's perspective
                                    comparison_lines.append(f"**Spread**: {favored_team} {predicted_spread_from_favored:+.1f} vs Line {line_from_favored:+.1f} ({covering_team} +{covering_margin:.1f}, **{covering_team} covers**)")

                            if comparison_lines:
                                for line in comparison_lines:
                                    st.write(line)
                        else:
                            st.info("ℹ️ Game lines (spread/total) not available. These are fetched from DraftKings via The Odds API.")
                    else:
                        st.info("No plays found matching your filters. Try lowering the minimum edge % or expanding filters.")

                elif cached_game_predictions is None and cached_game_props is not None:
                    st.info("👆 Click 'Generate All Predictions' to find value plays")
                elif cached_game_predictions is not None and cached_game_props is None:
                    st.warning("⚠️ Need to fetch Underdog lines first to compare predictions")


        else:
            st.warning("⚠️ Please select a matchup to generate predictions.")
    else:
        # ================================================================
        # ALL MATCHUPS VIEW — Generate predictions for every game at once,
        # surface best plays and 3-leg parlays across all games.
        # ================================================================
        if not matchups:
            st.info("No games found for the selected date.")
        else:
            from itertools import combinations as _combos
            from prediction_model import Prediction as _Pred

            game_date_str_all = selected_date.strftime('%Y-%m-%d')
            all_games_cache_key = f"all_games_plays_{game_date_str_all}"

            # Ensure caches exist
            if 'predictions_game_cache' not in st.session_state:
                st.session_state.predictions_game_cache = {}
            if 'odds_game_cache' not in st.session_state:
                st.session_state.odds_game_cache = {}

            # Classify which games have props already fetched
            games_with_props = []
            games_without_props = []
            for _m in matchups:
                _gk = f"{game_date_str_all}_{_m['away_team']}_{_m['home_team']}"
                if st.session_state.odds_game_cache.get(_gk):
                    games_with_props.append(_m)
                else:
                    games_without_props.append(_m)

            st.subheader("🏀 All Games — Best Plays & Top Parlays")

            # ── FETCH LINES FOR ALL GAMES ─────────────────────────────────────
            _fetch_row_col, _credits_col = st.columns([3, 1])
            with _fetch_row_col:
                _needs_fetch = [
                    m for m in matchups
                    if not st.session_state.odds_game_cache.get(
                        f"{game_date_str_all}_{m['away_team']}_{m['home_team']}"
                    )
                ]
                if _needs_fetch:
                    _fetch_label = f"📥 Fetch Lines for All Games ({len(_needs_fetch)} of {len(matchups)} remaining)"
                else:
                    _fetch_label = f"✅ All Game Lines Fetched ({len(matchups)} games)"
                if st.button(_fetch_label, key="fetch_all_lines_btn", disabled=not _needs_fetch):
                    _fp = st.progress(0, text="Starting…")
                    for _fi, _fm in enumerate(_needs_fetch):
                        _fa = _fm['away_team']
                        _fh = _fm['home_team']
                        _fk = f"{game_date_str_all}_{_fa}_{_fh}"
                        _fp.progress(
                            _fi / len(_needs_fetch),
                            text=f"Fetching {_fa} @ {_fh} ({_fi + 1}/{len(_needs_fetch)})…",
                        )
                        try:
                            _fprops, _fres = vl.fetch_all_props_for_game(_fh, _fa, game_date_str_all)
                            if _fres.success:
                                st.session_state.odds_game_cache[_fk] = _fprops
                                if _fres.credits_remaining is not None:
                                    st.session_state.odds_api_credits = _fres.credits_remaining
                            else:
                                st.warning(f"⚠️ {_fa} @ {_fh}: {_fres.error or 'API error'}")
                        except Exception as _fe:
                            st.warning(f"⚠️ Could not fetch {_fa} @ {_fh}: {_fe}")
                    _fp.progress(1.0, text="Done!")
                    _fp.empty()
                    st.rerun()
            with _credits_col:
                if st.session_state.get('odds_api_credits') is not None:
                    st.caption(f"💳 {st.session_state.odds_api_credits} credits left")

            # Re-classify after potential fetch
            games_with_props = [
                m for m in matchups
                if st.session_state.odds_game_cache.get(
                    f"{game_date_str_all}_{m['away_team']}_{m['home_team']}"
                )
            ]

            if not games_with_props:
                st.warning("No game lines fetched yet. Click the button above to fetch lines for all games.")
            else:
                _btn_col, _regen_col, _rst_col = st.columns([4, 2, 1])
                with _btn_col:
                    _gen_all = st.button(
                        f"⚡ Generate Predictions for All Games ({len(games_with_props)} with lines)",
                        key="gen_all_games_btn",
                        type="primary",
                    )
                with _regen_col:
                    if st.button("🔄 Regenerate All", key="regen_all_games_btn"):
                        prediction_store.delete_predictions_for_date(game_date_str_all)
                        if all_games_cache_key in st.session_state:
                            del st.session_state[all_games_cache_key]
                        # Clear per-game caches too
                        for _mk in list(st.session_state.get('predictions_game_cache', {}).keys()):
                            if _mk.startswith(game_date_str_all):
                                del st.session_state.predictions_game_cache[_mk]
                        st.rerun()
                with _rst_col:
                    if st.button("↩️ Clear", key="clear_all_games_btn"):
                        if all_games_cache_key in st.session_state:
                            del st.session_state[all_games_cache_key]
                        st.rerun()

                if _gen_all or all_games_cache_key in st.session_state:
                    if _gen_all or all_games_cache_key not in st.session_state:
                        _all_plays = []
                        _total_games_all = len(games_with_props)
                        _prog = st.progress(0, text="Starting…")

                        # Load any cached predictions from Supabase for this date
                        _sb_preds_df = prediction_store.load_predictions_for_date(game_date_str_all)

                        # Pre-fetch bulk game logs once for all normalization calls
                        _bulk_logs_all = pf_features.get_bulk_player_game_logs()

                        for _gi, _mo in enumerate(games_with_props):
                            _away = _mo['away_team']
                            _home = _mo['home_team']
                            _away_id = int(_mo['away_team_id'])
                            _home_id = int(_mo['home_team_id'])
                            _gk = f"{game_date_str_all}_{_away}_{_home}"

                            try:
                                # ── Check Supabase predictions cache for this game ────────
                                _sb_norm_preds_cached = None
                                if _sb_preds_df is not None:
                                    _sb_norm_preds_cached = prediction_store.reconstruct_norm_preds(
                                        _sb_preds_df, _away, _home
                                    )

                                if _sb_norm_preds_cached:
                                    # Cache hit — skip model entirely
                                    _norm_preds = _sb_norm_preds_cached
                                    _min_map = {
                                        pid: float(pdata.get('_proj_min', 0))
                                        for pid, pdata in _norm_preds.items()
                                    }
                                    _prog.progress(
                                        (_gi + 1) / max(_total_games_all, 1),
                                        text=f"Game {_gi + 1}/{_total_games_all}: {_away} @ {_home} — (Supabase cache)",
                                    )
                                else:
                                    # ── 1. Get or generate predictions ──────────────────────
                                    _gpreds = st.session_state.predictions_game_cache.get(_gk)
                                    if _gpreds is None:
                                        _team_ids = [_away_id, _home_id]
                                        if 'TEAM_ID' not in players_df.columns:
                                            continue
                                        _match_df = players_df[players_df['TEAM_ID'].astype(int).isin(_team_ids)]
                                        _pids = _match_df['PERSON_ID'].astype(str).tolist()

                                        # Injuries for this game
                                        if 'matchup_injuries_cache' not in st.session_state:
                                            st.session_state.matchup_injuries_cache = {}
                                        _inj_key = f"{_gk}_injuries"
                                        if _inj_key not in st.session_state.matchup_injuries_cache:
                                            if injury_report_df is not None and len(injury_report_df) > 0:
                                                st.session_state.matchup_injuries_cache[_inj_key] = ir.get_injuries_for_matchup(
                                                    injury_report_df, _away, _home, players_df
                                                )
                                            else:
                                                st.session_state.matchup_injuries_cache[_inj_key] = {'away': [], 'home': []}
                                        _minj = st.session_state.matchup_injuries_cache[_inj_key]
                                        _out_ids = set(
                                            [p.get('player_id') for p in _minj.get('away', []) if 'out' in (p.get('status', '') or '').lower() or 'doubtful' in (p.get('status', '') or '').lower()] +
                                            [p.get('player_id') for p in _minj.get('home', []) if 'out' in (p.get('status', '') or '').lower() or 'doubtful' in (p.get('status', '') or '').lower()]
                                        ) - {None}
                                        _pids = [p for p in _pids if p not in _out_ids]

                                        _pnames = {pid: player_name_map.get(pid, f"Player {pid}") for pid in _pids}
                                        _ptids = {}
                                        for _pid in _pids:
                                            _row = players_df[players_df['PERSON_ID'].astype(str) == _pid]
                                            if len(_row) > 0:
                                                _ptids[_pid] = int(_row['TEAM_ID'].iloc[0])

                                        def _make_all_prog_cb(_gi, _away, _home, _total_games_all):
                                            def _cb(cur, tot, pname):
                                                frac = (_gi + cur / max(tot, 1)) / max(_total_games_all, 1)
                                                _prog.progress(
                                                    min(frac, 1.0),
                                                    text=f"Game {_gi + 1}/{_total_games_all}: {_away} @ {_home} — {pname} ({cur}/{tot})",
                                                )
                                            return _cb

                                        _gpreds = pm.generate_predictions_for_game(
                                            player_ids=_pids,
                                            player_names=_pnames,
                                            player_team_ids=_ptids,
                                            away_team_id=_away_id,
                                            home_team_id=_home_id,
                                            away_team_abbr=_away,
                                            home_team_abbr=_home,
                                            game_date=game_date_str_all,
                                            simulation_config=_simulation_config,
                                            progress_callback=_make_all_prog_cb(_gi, _away, _home, _total_games_all),
                                        )
                                        st.session_state.predictions_game_cache[_gk] = _gpreds
                                    else:
                                        # Already in session-state cache — advance the bar
                                        _prog.progress(
                                            (_gi + 1) / max(_total_games_all, 1),
                                            text=f"Game {_gi + 1}/{_total_games_all}: {_away} @ {_home} — (cached)",
                                        )

                                    if not _gpreds:
                                        continue

                                    # ── 2. Build statlines ───────────────────────────────────
                                    _statlines = []
                                    for _pid, _pdata in _gpreds.items():
                                        _pid_s = str(_pid)
                                        _pname = _pdata.get('player_name', player_name_map.get(_pid_s, ''))
                                        _team = _pdata.get('team_abbr', '')
                                        _is_home_p = _pdata.get('is_home', False)
                                        _mins = player_minutes_map.get(int(_pid) if str(_pid).isdigit() else 0, 25.0)

                                        def _gv(stat):
                                            _preds_d = _pdata.get('predictions', {})
                                            if stat in _preds_d:
                                                _po = _preds_d[stat]
                                                return float(_po.value) if hasattr(_po, 'value') else float(_po)
                                            return 0.0

                                        _pts = _gv('PTS'); _reb = _gv('REB'); _ast = _gv('AST')
                                        _stl = _gv('STL'); _blk = _gv('BLK'); _tov = _gv('TOV')
                                        _fg3 = _gv('FG3M'); _ftm = _gv('FTM')
                                        _statlines.append({
                                            'Player': _pname, 'Team': _team, 'player_id': _pid_s,
                                            'MIN': _mins,
                                            '_original_season_minutes': _mins,
                                            '_injury_adjusted_minutes': _mins,
                                            '_base_stats': {'PTS': _pts, 'REB': _reb, 'AST': _ast, 'STL': _stl, 'BLK': _blk, 'TOV': _tov, 'FG3M': _fg3, 'FTM': _ftm},
                                            '_injury_multipliers': None,
                                            'PTS': _pts, 'REB': _reb, 'AST': _ast,
                                            'STL': _stl, 'BLK': _blk, 'TOV': _tov,
                                            'FG3M': _fg3, 'FTM': _ftm,
                                            'PRA': _pts + _reb + _ast,
                                            'RA': _reb + _ast,
                                            'FPTS': _pts + _reb * 1.2 + _ast * 1.5 + _stl * 3.0 + _blk * 3.0 - _tov,
                                            'is_away': not _is_home_p,
                                        })

                                    # ── 3. Normalize minutes ─────────────────────────────────
                                    _inj_key2 = f"{_gk}_injuries"
                                    _out_norm = set()
                                    if 'matchup_injuries_cache' in st.session_state:
                                        _mi2 = st.session_state.matchup_injuries_cache.get(_inj_key2, {})
                                        _out_norm = set(
                                            [p.get('player_id') for p in _mi2.get('away', []) if 'out' in (p.get('status', '') or '').lower() or 'doubtful' in (p.get('status', '') or '').lower()] +
                                            [p.get('player_id') for p in _mi2.get('home', []) if 'out' in (p.get('status', '') or '').lower() or 'doubtful' in (p.get('status', '') or '').lower()]
                                        ) - {None}
                                    _returning_norm = _returning_ids_from_injury_dict(
                                        st.session_state.matchup_injuries_cache.get(f"{_gk}_injuries", {})
                                    )
                                    normalize_team_minutes(
                                        _statlines,
                                        target_minutes=240.0,
                                        out_player_ids=_out_norm,
                                        bulk_game_logs=_bulk_logs_all,
                                        game_date=game_date_str_all,
                                        returning_player_ids=_returning_norm,
                                    )

                                    # Flag injury-return estimates in progress bar text
                                    _ret_est = [s for s in _statlines if s.get('_injury_return_estimate')]
                                    if _ret_est:
                                        _ret_names = ', '.join(
                                            f"{s['Player']} (~{round(s['MIN'],1)} min)"
                                            for s in _ret_est
                                        )
                                        _prog.progress(
                                            (_gi + 1) / max(_total_games_all, 1),
                                            text=f"Game {_gi + 1}/{_total_games_all}: {_away} @ {_home} — ⚠️ Return estimates: {_ret_names}",
                                        )

                                    # ── Upload normalized statlines to Supabase ───────────
                                    _cf_map = {
                                        str(_pid): _pdata.get('ceiling_floor', {})
                                        for _pid, _pdata in (_gpreds or {}).items()
                                    }
                                    prediction_store.upload_game_predictions(
                                        game_date_str_all, _away, _home, _statlines, _cf_map
                                    )

                                    # ── 4. Build normalized_predictions ──────────────────────
                                    _norm_preds = {}
                                    for _sl in _statlines:
                                        if _sl.get('MIN', 0) <= 0.01:
                                            continue
                                        _pid_s2 = _sl['player_id']
                                        _is_h2 = not _sl['is_away']
                                        _norm_preds[_pid_s2] = {
                                            'predictions': {
                                                _st: _Pred(stat=_st, value=_sl[_st], confidence='high',
                                                           breakdown={'normalized': _sl[_st]},
                                                           factors={'source': 'all_games'})
                                                for _st in ['PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'FG3M', 'FTM', 'PRA', 'RA', 'FPTS']
                                            },
                                            'player_name': _sl['Player'],
                                            'team_abbr': _sl['Team'],
                                            'is_home': _is_h2,
                                            'opponent_abbr': _home if _sl['is_away'] else _away,
                                        }
                                    _min_map = {sl['player_id']: sl['MIN'] for sl in _statlines}

                                # ── 5. Find best plays for this game ─────────────────────
                                _game_props = st.session_state.odds_game_cache.get(_gk)
                                if not _game_props:
                                    continue
                                _plays = pm.find_best_value_plays(
                                    all_predictions=_norm_preds,
                                    all_props=_game_props,
                                    min_edge_pct=5.0,
                                    confidence_filter=['high', 'medium', 'low'],
                                    stat_filter=['PTS', 'REB', 'AST', 'PRA', 'RA', 'STL', 'BLK', 'FG3M'],
                                    injury_adjustments_map=None,
                                )
                                _game_time = _mo.get('game_time', '')
                                for _p in _plays:
                                    _p['game'] = f"{_away} @ {_home}"
                                    _p['game_time'] = _game_time or ''
                                    _p['proj_min'] = round(_min_map.get(_p['player_id'], 0), 1)
                                _all_plays.extend(_plays)

                            except Exception as _e:
                                st.warning(f"Could not process {_away} @ {_home}: {_e}")

                        _prog.progress(1.0, text="Done!")
                        _prog.empty()

                        # Filter out any play where the model's projected value is effectively 0
                        _all_plays = [_p for _p in _all_plays if _p.get('prediction', 0) > 0.1]
                        st.session_state[all_games_cache_key] = _all_plays

                    _all_plays = st.session_state.get(all_games_cache_key, [])
                    _bulk_logs_all = pf_features.get_bulk_player_game_logs()

                    if not _all_plays:
                        st.warning("No plays with sufficient edge found. Try fetching lines for more games.")
                    else:
                        _plays_sorted = sorted(_all_plays, key=lambda x: abs(x.get('edge_pct', 0)), reverse=True)

                        # ── TOP PLAYS TABLE ──────────────────────────────────────────
                        st.markdown(f"#### 🎯 Top Plays Across All Games ({len(_plays_sorted)} total with 5%+ edge)")
                        _top_df = pd.DataFrame([{
                            'Game':    _p.get('game', ''),
                            'Time':    _p.get('game_time', ''),
                            'Player':  _p['player_name'],
                            'Team':    _p['team'],
                            'Min':     _p.get('proj_min', 0),
                            'Stat':    _p['stat'],
                            'Pred':    round(_p['prediction'], 1),
                            'Line':    round(float(_p['line']), 1),
                            'Edge':    f"{_p['edge']:+.1f}",
                            'Edge %':  f"{_p['edge_pct']:+.1f}%",
                            'Lean':    _p['lean'],
                            'Conf':    _p['confidence'],
                        } for _p in _plays_sorted[:25]])

                        def _lean_style(val):
                            if 'Over' in str(val):  return f'background-color:{tc.lean_over_bg};color:{tc.lean_over_text}'
                            if 'Under' in str(val): return f'background-color:{tc.lean_under_bg};color:{tc.lean_under_text}'
                            return ''

                        st.dataframe(
                            _top_df.style.map(_lean_style, subset=['Lean']),
                            hide_index=True,
                            width='stretch',
                            column_config={
                                'Min':  st.column_config.NumberColumn(format="%.1f"),
                                'Pred': st.column_config.NumberColumn(format="%.1f"),
                                'Line': st.column_config.NumberColumn(format="%.1f"),
                            },
                        )

                        # ── TOP 3-LEG PARLAYS ────────────────────────────────────────
                        st.markdown("#### 🎰 Best 3-Leg Parlays")
                        st.caption("Each parlay uses 3 different players. No player appears in more than one parlay. Sorted by combined edge percentage.")

                        # Deduplicate: keep best play per (player, stat); exclude Pushes
                        _seen_ps = {}
                        _deduped = []
                        for _p in _plays_sorted:
                            if _p.get('lean', '') == 'Push':
                                continue
                            _pskey = (_p['player_id'], _p['stat'])
                            if _pskey not in _seen_ps:
                                _seen_ps[_pskey] = True
                                _deduped.append(_p)

                        _candidates = _deduped[:50]
                        _all_parlays = []
                        for _combo in _combos(_candidates, 3):
                            if len({_p['player_id'] for _p in _combo}) < 3:
                                continue
                            if len({_p['team'] for _p in _combo}) < 2:
                                continue
                            _total_edge = sum(abs(_p['edge_pct']) for _p in _combo)
                            _all_parlays.append((_total_edge, list(_combo)))
                        _all_parlays.sort(key=lambda x: -x[0])

                        # Pick top 5 parlays with no player appearing in more than one parlay
                        _best_parlays = []
                        _used_players = set()
                        for _tedge, _legs in _all_parlays:
                            _leg_pids = {_p['player_id'] for _p in _legs}
                            if _leg_pids & _used_players:
                                continue
                            _best_parlays.append((_tedge, _legs))
                            _used_players |= _leg_pids
                            if len(_best_parlays) == 5:
                                break

                        if not _best_parlays:
                            st.info("Not enough distinct players to form 5 non-overlapping 3-leg parlays.")
                        else:
                            for _rank, (_tedge, _legs) in enumerate(_best_parlays, 1):
                                _payout_disp = round(ptl.parlay_payout_multiplier(_legs), 2)
                                with st.expander(
                                    f"Parlay {_rank}  •  Combined Edge: {_tedge:.1f}%  •  Payout: {_payout_disp:.2f}x",
                                    expanded=(_rank == 1),
                                ):
                                    for _leg in _legs:
                                        _render_leg_with_l5(_leg, _bulk_logs_all)
                                    # ── Payout override ───────────────────────────
                                    _adj_payout_all = st.number_input(
                                        "Payout multiplier (edit if you have a boost)",
                                        value=_payout_disp,
                                        min_value=0.0,
                                        step=0.01,
                                        format="%.2f",
                                        key=f"payout_all_{_rank}_{game_date_str_all}",
                                    )
                                    _save_key = f"save_parlay_{_rank}_{game_date_str_all}"
                                    _saved_key = f"parlay_saved_{_rank}_{game_date_str_all}"
                                    if st.session_state.get(_saved_key):
                                        st.success("✅ Parlay saved to tracker")
                                    elif st.button("💾 Save Parlay", key=_save_key):
                                        _pid = ptl.save_parlay(game_date_str_all, _legs, payout_override=float(_adj_payout_all))
                                        if _pid:
                                            if game_date_str_all >= str(date.today()):
                                                ptl.post_parlay_to_discord(game_date_str_all, _legs, float(_adj_payout_all))
                                            st.session_state[_saved_key] = True
                                            st.rerun()
                                        else:
                                            st.error("Failed to save parlay. Check logs.")

    # ================================================================
    # PARLAY TRACKER — always visible at the bottom of the page
    # ================================================================

    # Auto-verify once per session: score any pending parlays whose game date has passed
    _auto_verify_key = f"parlay_auto_verified_{date.today()}"
    if not st.session_state.get(_auto_verify_key):
        _pending_check = ptl.load_parlays(status='pending')
        _today_str = str(date.today())
        _verifiable = [p for p in _pending_check if str(p.get('game_date', '9999'))[:10] < _today_str]
        if _verifiable:
            try:
                _auto_logs = pf_features.get_bulk_player_game_logs()
                ptl.verify_pending_parlays(_auto_logs)
            except Exception:
                pass
        st.session_state[_auto_verify_key] = True

    st.markdown("#### 💰 Track All Parlays")
    with st.expander("📊 Parlay Tracker", expanded=False):
        _all_parlays_db = ptl.load_parlays()
        _pnl = ptl.get_pnl_summary(_all_parlays_db)

        # ── Summary row ──────────────────────────────────────────────
        _m1, _m2, _m3, _m4, _m5 = st.columns(5)
        _m1.metric("Record", f"{_pnl['wins']}–{_pnl['losses']}")
        _m2.metric("Win Rate", f"{_pnl['win_rate']}%")
        _m3.metric("Units Risked", f"{_pnl['units_risked']}")
        _m4.metric("Units Returned", f"{_pnl['units_returned']}")
        _net_color = "normal" if _pnl['net_units'] == 0 else ("inverse" if _pnl['net_units'] < 0 else "normal")
        _m5.metric("Net Units", f"{_pnl['net_units']:+.2f}", delta=f"{_pnl['net_units']:+.2f}", delta_color=_net_color)

        # ── Verify button ────────────────────────────────────────────
        _vc1, _vc2 = st.columns([2, 5])
        with _vc1:
            if st.button("🔍 Verify Pending Parlays", key="verify_parlays_btn"):
                with st.spinner("Fetching box scores and scoring legs…"):
                    try:
                        _logs_for_verify = pf_features.get_bulk_player_game_logs()
                        _vresult = ptl.verify_pending_parlays(_logs_for_verify)
                        st.success(
                            f"✅ Verified {_vresult['verified']} parlay(s). "
                            f"{_vresult['skipped']} skipped (box scores not yet available)."
                        )
                        st.rerun()
                    except Exception as _ve:
                        st.error(f"Verification failed: {_ve}")
        with _vc2:
            if _pnl['pending'] > 0:
                st.caption(f"⏳ {_pnl['pending']} pending parlay(s) awaiting verification")

        st.divider()

        # ── Tabs: Pending / Results ───────────────────────────────────
        _tab_pending, _tab_results = st.tabs(["⏳ Pending", "📋 Results"])

        def _render_parlay_card(p, editable_payout=False):
            _legs = p.get('legs', [])
            _status = p.get('status', 'pending')
            _gdate = p.get('game_date', '')
            _payout = p.get('payout_multiplier', 6.0)
            _logged = str(p.get('logged_at', ''))[:16].replace('T', ' ')
            _status_icon = {'pending': '⏳', 'won': '✅', 'lost': '❌'}.get(_status, '❓')
            _legs_won = p.get('legs_won')
            _legs_total = p.get('legs_total', len(_legs))
            _subtitle = (
                f"Game date: {_gdate}  •  Logged: {_logged}  •  "
                f"Payout: {_payout:.2f}x  •  "
                + (f"Legs: {_legs_won}/{_legs_total}" if _legs_won is not None else f"Legs: {_legs_total}")
            )
            st.caption(f"{_status_icon} {_subtitle}")
            for _leg in _legs:
                _lean = _leg.get('lean', '')
                _result = _leg.get('result', '')
                _actual = _leg.get('actual')
                if _result == 'win':
                    _lc, _lt = tc.green_bg, tc.green_text
                elif _result == 'loss':
                    _lc, _lt = tc.red_bg, tc.red_text
                elif 'Over' in _lean:
                    _lc, _lt = tc.info_bg, tc.info_text
                else:
                    _lc, _lt = tc.warn_bg, tc.warn_text
                _actual_str = f"  •  Actual: <strong>{_actual}</strong>" if _actual is not None else ""
                _result_str = f"  •  <strong>{'WIN' if _result == 'win' else 'LOSS' if _result == 'loss' else ''}</strong>" if _result in ('win', 'loss') else ""
                st.markdown(
                    f'<div style="background:{_lc};border-radius:6px;padding:6px 12px;margin:3px 0;font-size:0.9em;">'
                    f'<strong>{_leg.get("player_name","")}</strong>'
                    f' <span style="color:{tc.text_secondary};">({_leg.get("team","")} vs {_leg.get("opponent","")})</span>'
                    f' &nbsp;·&nbsp; <strong>{_leg.get("stat","")}</strong> {_lean}'
                    f' &nbsp;·&nbsp; Line {_leg.get("line","")} / Pred {round(_leg.get("prediction",0),1)}'
                    f' &nbsp;·&nbsp; <span style="color:{_lt};font-weight:600;">{_leg.get("edge_pct",0):+.1f}%</span>'
                    f'{_actual_str}'
                    f'<span style="color:{_lt};font-weight:700;">{_result_str}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            # ── Payout edit (results only) ────────────────────────────
            _pid = p.get('id', '')
            if editable_payout:
                _ep_col, _ep_btn_col = st.columns([3, 1])
                _ep_new = _ep_col.number_input(
                    "Actual payout (x)",
                    value=float(_payout or 0),
                    min_value=0.0,
                    step=0.01,
                    format="%.2f",
                    key=f"ep_{_pid}",
                )
                if _ep_btn_col.button("💾 Save", key=f"ep_save_{_pid}"):
                    ptl.update_payout(_pid, _ep_new, _status)
                    st.rerun()

            # ── Delete controls ──────────────────────────────────────
            _confirm_key = f"confirm_del_{_pid}"
            if st.session_state.get(_confirm_key):
                st.warning("Delete this play permanently?")
                _dc1, _dc2 = st.columns(2)
                if _dc1.button("✅ Yes, delete", key=f"del_yes_{_pid}"):
                    ptl.delete_parlay(_pid)
                    del st.session_state[_confirm_key]
                    st.rerun()
                if _dc2.button("❌ Cancel", key=f"del_no_{_pid}"):
                    del st.session_state[_confirm_key]
                    st.rerun()
            else:
                if st.button("🗑️ Delete play", key=f"del_{_pid}"):
                    st.session_state[_confirm_key] = True
                    st.rerun()

        with _tab_pending:
            _pending_parlays = [p for p in _all_parlays_db if p.get('status') == 'pending']
            if not _pending_parlays:
                st.info("No pending parlays. Save a parlay from the All Games view above.")
            else:
                for _p in _pending_parlays:
                    with st.container(border=True):
                        _render_parlay_card(_p)

        with _tab_results:
            _resolved = [p for p in _all_parlays_db if p.get('status') in ('won', 'lost')]
            if not _resolved:
                st.info("No resolved parlays yet.")
            else:
                for _p in _resolved:
                    with st.container(border=True):
                        _render_parlay_card(_p, editable_payout=True)

    # ================================================================
    # LOG CUSTOM PLAY — always visible, works without a matchup selected
    # ================================================================

    if 'cp_staged_legs' not in st.session_state:
        st.session_state.cp_staged_legs = []

    _CP_STAT_LABELS = {
        'PTS': 'Points (PTS)', 'REB': 'Rebounds (REB)', 'AST': 'Assists (AST)',
        'PRA': 'Pts+Reb+Ast (PRA)', 'PR': 'Pts+Reb (PR)', 'PA': 'Pts+Ast (PA)',
        'RA': 'Reb+Ast (RA)', 'STL': 'Steals (STL)', 'BLK': 'Blocks (BLK)',
        'TOV': 'Turnovers (TOV)', 'FG3M': '3-Pointers Made (FG3M)',
        'FTM': 'Free Throws Made (FTM)', 'FPTS': 'Fantasy Points (FPTS)',
        'MIN': 'Minutes (MIN)',
    }

    with st.expander("✏️ Log Custom Play", expanded=False):
        _cp_date_str = selected_date.strftime('%Y-%m-%d')

        if 'odds_game_cache' not in st.session_state:
            st.session_state.odds_game_cache = {}

        # ── Staged legs ──────────────────────────────────────────────
        if st.session_state.cp_staged_legs:
            st.markdown(f"**Staged legs ({len(st.session_state.cp_staged_legs)}):**")
            for _cpi, _cpl in enumerate(st.session_state.cp_staged_legs):
                _cpli_col, _cpli_rm = st.columns([9, 1])
                _cpli_icon = '📈' if 'Over' in _cpl['lean'] else '📉'
                _cpli_odds_val = _cpl['over_odds'] if 'Over' in _cpl['lean'] else _cpl['under_odds']
                _cpli_odds_str = f"+{_cpli_odds_val}" if _cpli_odds_val > 0 else str(_cpli_odds_val)
                _cpli_col.markdown(
                    f"{_cpli_icon} **{_cpl['player_name']}** ({_cpl['team']} vs {_cpl['opponent']})  "
                    f"— {_cpl['stat']} **{_cpl['lean']} {_cpl['line']}**  •  Odds: {_cpli_odds_str}  •  _{_cpl['game']}_"
                )
                if _cpli_rm.button("✕", key=f"cp_rm_{_cpi}"):
                    st.session_state.cp_staged_legs.pop(_cpi)
                    st.rerun()
            st.divider()

        # ── Game selector ────────────────────────────────────────────
        if matchups:
            _cp_game_options = [f"{m['away_team']} @ {m['home_team']}" for m in matchups]
        else:
            _cp_game_options = []

        _cp_game_labels = ["-- Select a game --"] + _cp_game_options
        _cp_sel_idx = st.selectbox(
            "Game",
            range(len(_cp_game_labels)),
            format_func=lambda i: _cp_game_labels[i],
            key="cp_game_select",
        )

        if _cp_sel_idx == 0:
            st.caption("Select a game to load available props from Underdog Fantasy.")
        else:
            _cp_match = matchups[_cp_sel_idx - 1]
            _cp_away = _cp_match['away_team']
            _cp_home = _cp_match['home_team']
            _cp_gk = f"{_cp_date_str}_{_cp_away}_{_cp_home}"
            _cp_game_label = f"{_cp_away} @ {_cp_home}"

            # ── Fetch / cache props ──────────────────────────────────
            _cp_props = st.session_state.odds_game_cache.get(_cp_gk)

            # ── Fetch Underdog props (optional, enriches line defaults) ──
            if not _cp_props:
                if st.button("📡 Fetch Underdog Lines (1 credit)", key="cp_fetch_props_btn"):
                    with st.spinner(f"Fetching props for {_cp_game_label}…"):
                        _cp_all_props, _cp_resp = vl.fetch_all_props_for_game(
                            _cp_home, _cp_away, _cp_date_str
                        )
                        if _cp_resp.success and _cp_all_props:
                            st.session_state.odds_game_cache[_cp_gk] = _cp_all_props
                            st.rerun()
                        else:
                            st.error(f"Could not fetch props: {_cp_resp.error or 'No props found'}")

            if _cp_props:
                st.caption(f"✅ Underdog lines loaded for {len(_cp_props)} players")

            # ── Build combined player list: predictions + Underdog ──
            # 1. Players from generated predictions for this game
            _cp_game_players = {}  # name_lower -> {display, team, opponent, player_id}
            for _cp_m in matchups:
                if _cp_m['away_team'] == _cp_away and _cp_m['home_team'] == _cp_home:
                    _cp_norm_key = f"{_cp_date_str}_{_cp_away}_{_cp_home}_normalized_statlines"
                    _cp_statlines = st.session_state.get(_cp_norm_key, [])
                    for _cps in _cp_statlines:
                        _cpn = _cps.get('Player', '')
                        if _cpn and _cps.get('MIN', 0) > 0:
                            _cp_is_away = _cps.get('is_away', False)
                            _cp_game_players[_cpn.lower().strip()] = {
                                'display': _cpn,
                                'team': _cp_away if _cp_is_away else _cp_home,
                                'opponent': _cp_home if _cp_is_away else _cp_away,
                                'player_id': str(_cps.get('player_id', '')),
                            }
                    break

            # 2. Add any Underdog players not already in predictions
            if _cp_props:
                for _cpk in _cp_props:
                    if _cpk not in _cp_game_players:
                        _cp_game_players[_cpk] = {
                            'display': _cpk.title(),
                            'team': _cp_away,  # default; user picks below
                            'opponent': _cp_home,
                            'player_id': _resolve_player_id(_cpk.title()),
                        }

            if not _cp_game_players:
                st.info("Generate predictions for this game first, or fetch Underdog lines above.")
            else:
                # ── Player selector ──────────────────────────────────
                _cp_player_keys = sorted(_cp_game_players.keys())
                _cp_player_labels = ["-- Select a player --"] + [_cp_game_players[k]['display'] for k in _cp_player_keys]
                _cp_player_idx = st.selectbox(
                    "Player",
                    range(len(_cp_player_labels)),
                    format_func=lambda i: _cp_player_labels[i],
                    key="cp_player_select",
                )

                if _cp_player_idx > 0:
                    _cp_player_key = _cp_player_keys[_cp_player_idx - 1]
                    _cp_player_info = _cp_game_players[_cp_player_key]
                    _cp_player_display = _cp_player_info['display']

                    # ── Player's team (key includes player so it resets on change) ──
                    _cp_default_team_idx = 0 if _cp_player_info['team'] == _cp_away else 1
                    _cp_player_team_choice = st.radio(
                        "Player's team",
                        [_cp_away, _cp_home],
                        index=_cp_default_team_idx,
                        horizontal=True,
                        key=f"cp_player_team_{_cp_player_key}",
                    )
                    _cp_player_opp = _cp_home if _cp_player_team_choice == _cp_away else _cp_away

                    # ── Prop / stat selector (all markets always) ────
                    _cp_all_stat_keys = list(_CP_STAT_LABELS.keys())
                    _cp_stat = st.selectbox(
                        "Prop",
                        _cp_all_stat_keys,
                        format_func=lambda s: _CP_STAT_LABELS.get(s, s),
                        key=f"cp_stat_select_{_cp_player_key}",
                    )

                    if _cp_stat:
                        # Pre-fill from Underdog if available
                        _cp_ud_prop = (_cp_props or {}).get(_cp_player_key, {}).get(_cp_stat)
                        _cp_default_line = _cp_ud_prop.line if _cp_ud_prop else 0.5
                        _cp_default_over = _cp_ud_prop.over_odds if _cp_ud_prop else -137
                        _cp_default_under = _cp_ud_prop.under_odds if _cp_ud_prop else -137

                        if _cp_ud_prop:
                            st.caption(f"📊 Underdog line: {_cp_ud_prop.line}")

                        # ── Line (key includes player+stat so it resets on change) ──
                        _cp_line_val = st.number_input(
                            "Line",
                            value=float(_cp_default_line),
                            step=0.5,
                            min_value=0.0,
                            key=f"cp_line_input_{_cp_player_key}_{_cp_stat}",
                        )

                        # ── Direction + Odds (key includes player+stat) ──
                        _cp_direction = st.radio(
                            "Direction",
                            ["Over", "Under"],
                            horizontal=True,
                            key=f"cp_direction_{_cp_player_key}_{_cp_stat}",
                        )
                        _cp_default_odds = _cp_default_over if _cp_direction == "Over" else _cp_default_under
                        _cp_adj_odds = st.number_input(
                            "Odds (edit if you have a boost)",
                            value=int(_cp_default_odds),
                            step=5,
                            key=f"cp_odds_input_{_cp_player_key}_{_cp_stat}_{_cp_direction}",
                        )

                        # ── Add Leg button ────────────────────────────
                        if st.button("➕ Add Leg", key="cp_add_leg_btn"):
                            _cp_final_over  = int(_cp_adj_odds) if _cp_direction == "Over"  else int(_cp_default_over)
                            _cp_final_under = int(_cp_adj_odds) if _cp_direction == "Under" else int(_cp_default_under)
                            st.session_state.cp_staged_legs.append({
                                'player_id':   _cp_player_info.get('player_id') or _resolve_player_id(_cp_player_display),
                                'player_name': _cp_player_display,
                                'team':        _cp_player_team_choice,
                                'opponent':    _cp_player_opp,
                                'stat':        _cp_stat,
                                'line':        _cp_line_val,
                                'lean':        _cp_direction,
                                'prediction':  0,
                                'edge_pct':    0,
                                'over_odds':   _cp_final_over,
                                'under_odds':  _cp_final_under,
                                'game':        _cp_game_label,
                            })
                            st.rerun()

        # ── Save / Clear ─────────────────────────────────────────────
        if st.session_state.cp_staged_legs:
            _cp_payout_preview = round(ptl.parlay_payout_multiplier(st.session_state.cp_staged_legs), 2)
            _cp_payout_override = st.number_input(
                "Payout multiplier (edit if your actual payout differs)",
                value=_cp_payout_preview,
                min_value=0.0,
                step=0.01,
                format="%.2f",
                key="cp_payout_override",
            )
            st.caption(f"{len(st.session_state.cp_staged_legs)} leg(s)  •  Auto-calculated: **{_cp_payout_preview:.2f}x**")
            _cp_s1, _cp_s2 = st.columns(2)
            _cp_teams_in_play = {leg['team'] for leg in st.session_state.cp_staged_legs}
            if len(_cp_teams_in_play) < 2:
                st.warning("⚠️ Parlay must include players from at least 2 different teams.")
            if _cp_s1.button("💾 Save Parlay", key="cp_save_btn", disabled=len(_cp_teams_in_play) < 2):
                _cp_legs_to_save = list(st.session_state.cp_staged_legs)
                _cp_saved_id = ptl.save_parlay(_cp_date_str, _cp_legs_to_save, payout_override=float(_cp_payout_override))
                if _cp_saved_id:
                    if _cp_date_str >= str(date.today()):
                        ptl.post_parlay_to_discord(_cp_date_str, _cp_legs_to_save, float(_cp_payout_override))
                    st.session_state.cp_staged_legs = []
                    st.success("✅ Parlay saved!")
                    st.rerun()
                else:
                    st.error("Failed to save. Check logs.")
            if _cp_s2.button("🗑️ Clear all legs", key="cp_clear_btn"):
                st.session_state.cp_staged_legs = []
                st.rerun()

    # ================================================================
    # LOG PAST PLAY — retroactive entry for any date
    # ================================================================

    _NBA_TEAMS = sorted([
        'ATL','BOS','BKN','CHA','CHI','CLE','DAL','DEN','DET','GSW',
        'HOU','IND','LAC','LAL','MEM','MIA','MIL','MIN','NOP','NYK',
        'OKC','ORL','PHI','PHX','POR','SAC','SAS','TOR','UTA','WAS',
    ])
    _RETRO_STAT_LABELS = {
        'PTS': 'Points (PTS)', 'REB': 'Rebounds (REB)', 'AST': 'Assists (AST)',
        'PRA': 'Pts+Reb+Ast (PRA)', 'PR': 'Pts+Reb (PR)', 'PA': 'Pts+Ast (PA)',
        'RA': 'Reb+Ast (RA)', 'STL': 'Steals (STL)', 'BLK': 'Blocks (BLK)',
        'TOV': 'Turnovers (TOV)', 'FG3M': '3-Pointers Made (FG3M)',
        'FTM': 'Free Throws Made (FTM)', 'FPTS': 'Fantasy Points (FPTS)',
        'MIN': 'Minutes (MIN)',
    }

    if 'rp_staged_legs' not in st.session_state:
        st.session_state.rp_staged_legs = []

    with st.expander("🕐 Log Past Play", expanded=False):
        st.caption("Retroactively log a play you forgot to record. All fields are manual since live lines are no longer available.")

        # ── Date (shared across all legs in this parlay) ─────────────
        _rp_date = st.date_input(
            "Game date",
            value=date.today() - timedelta(days=1),
            max_value=date.today(),
            key="rp_date",
        )
        _rp_date_str = _rp_date.strftime('%Y-%m-%d')

        # ── Staged legs ──────────────────────────────────────────────
        if st.session_state.rp_staged_legs:
            st.markdown(f"**Staged legs ({len(st.session_state.rp_staged_legs)}):**")
            for _rpi, _rpl in enumerate(st.session_state.rp_staged_legs):
                _rpli_col, _rpli_rm = st.columns([9, 1])
                _rpli_icon = '📈' if 'Over' in _rpl['lean'] else '📉'
                _rpli_odds_val = _rpl['over_odds'] if 'Over' in _rpl['lean'] else _rpl['under_odds']
                _rpli_odds_str = f"+{_rpli_odds_val}" if _rpli_odds_val > 0 else str(_rpli_odds_val)
                _rpli_col.markdown(
                    f"{_rpli_icon} **{_rpl['player_name']}** ({_rpl['team']} vs {_rpl['opponent']})  "
                    f"— {_rpl['stat']} **{_rpl['lean']} {_rpl['line']}**  •  Odds: {_rpli_odds_str}  •  _{_rpl['game']}_"
                )
                if _rpli_rm.button("✕", key=f"rp_rm_{_rpi}"):
                    st.session_state.rp_staged_legs.pop(_rpi)
                    st.rerun()
            st.divider()

        # ── Add a leg ────────────────────────────────────────────────
        st.markdown("**Add a leg:**")
        _rp_col_away, _rp_col_vs, _rp_col_home = st.columns([2, 0.4, 2])
        with _rp_col_away:
            _rp_away = st.selectbox("Away team", _NBA_TEAMS, key="rp_away_team")
        with _rp_col_vs:
            st.markdown("<div style='text-align:center;padding-top:32px;'>@</div>", unsafe_allow_html=True)
        with _rp_col_home:
            _rp_home_options = [t for t in _NBA_TEAMS if t != _rp_away]
            _rp_home = st.selectbox("Home team", _rp_home_options, key="rp_home_team")

        _rp_game_label = f"{_rp_away} @ {_rp_home}"

        # ── Player selector (NBA API static list, cached) ────────────
        if 'nba_all_players' not in st.session_state:
            try:
                from nba_api.stats.static import players as _nba_static_players
                _all_active = _nba_static_players.get_active_players()
                st.session_state.nba_all_players = sorted(_all_active, key=lambda p: p['full_name'])
            except Exception:
                st.session_state.nba_all_players = []

        _rp_player_options = st.session_state.nba_all_players
        _rp_player_labels  = ["-- Select a player --"] + [p['full_name'] for p in _rp_player_options]
        _rp_player_idx = st.selectbox(
            "Player",
            range(len(_rp_player_labels)),
            format_func=lambda i: _rp_player_labels[i],
            key="rp_player_select",
        )
        _rp_player_selected = _rp_player_options[_rp_player_idx - 1] if _rp_player_idx > 0 else None

        _rp_player_team_choice = st.radio(
            "Player's team",
            [_rp_away, _rp_home],
            horizontal=True,
            key="rp_player_team",
        )
        _rp_player_opp = _rp_home if _rp_player_team_choice == _rp_away else _rp_away

        _rp_stat = st.selectbox(
            "Prop",
            list(_RETRO_STAT_LABELS.keys()),
            format_func=lambda s: _RETRO_STAT_LABELS[s],
            key="rp_stat",
        )
        _rp_line = st.number_input("Line", value=20.5, step=0.5, min_value=0.0, key="rp_line")

        _rp_direction = st.radio("Direction", ["Over", "Under"], horizontal=True, key="rp_direction")
        _rp_odds = st.number_input("Odds", value=-137, step=5, key="rp_odds")

        if st.button("➕ Add Leg", key="rp_add_leg_btn", disabled=_rp_player_selected is None):
            _rp_over_odds  = int(_rp_odds) if _rp_direction == "Over"  else -137
            _rp_under_odds = int(_rp_odds) if _rp_direction == "Under" else -137
            st.session_state.rp_staged_legs.append({
                'player_id':   str(_rp_player_selected['id']),
                'player_name': _rp_player_selected['full_name'],
                'team':        _rp_player_team_choice,
                'opponent':    _rp_player_opp,
                'stat':        _rp_stat,
                'line':        _rp_line,
                'lean':        _rp_direction,
                'prediction':  0,
                'edge_pct':    0,
                'over_odds':   _rp_over_odds,
                'under_odds':  _rp_under_odds,
                'game':        _rp_game_label,
            })
            st.rerun()

        # ── Save / Clear ─────────────────────────────────────────────
        if st.session_state.rp_staged_legs:
            _rp_payout_preview = round(ptl.parlay_payout_multiplier(st.session_state.rp_staged_legs), 2)
            _rp_payout_override = st.number_input(
                "Payout multiplier (edit if your actual payout differs)",
                value=_rp_payout_preview,
                min_value=0.0,
                step=0.01,
                format="%.2f",
                key="rp_payout_override",
            )
            st.caption(f"{len(st.session_state.rp_staged_legs)} leg(s)  •  Auto-calculated: **{_rp_payout_preview:.2f}x**  •  Game date: **{_rp_date_str}**")
            _rp_teams_in_play = {leg['team'] for leg in st.session_state.rp_staged_legs}
            if len(_rp_teams_in_play) < 2:
                st.warning("⚠️ Parlay must include players from at least 2 different teams.")
            _rp_s1, _rp_s2 = st.columns(2)
            if _rp_s1.button("💾 Save Parlay", key="rp_save_btn", disabled=len(_rp_teams_in_play) < 2):
                _rp_legs_to_save = list(st.session_state.rp_staged_legs)
                _rp_saved_id = ptl.save_parlay(_rp_date_str, _rp_legs_to_save, payout_override=float(_rp_payout_override))
                if _rp_saved_id:
                    st.session_state.rp_staged_legs = []
                    st.success("✅ Past play saved!")
                    st.rerun()
                else:
                    st.error("Failed to save. Check logs.")
            if _rp_s2.button("🗑️ Clear all legs", key="rp_clear_btn"):
                st.session_state.rp_staged_legs = []
                st.rerun()
