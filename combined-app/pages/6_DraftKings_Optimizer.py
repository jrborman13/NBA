import sys
import os
from pathlib import Path

# Add paths for imports
project_root = Path(__file__).parent.parent  # combined-app/
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'scripts'))
sys.path.insert(0, str(project_root / 'player_app'))

# Load .env from repo root (NBA/.env) so API keys are available
try:
    from dotenv import load_dotenv
    _env_path = project_root.parent / '.env'
    load_dotenv(dotenv_path=_env_path, override=False)
except ImportError:
    pass

import streamlit as st
import pandas as pd
from datetime import date, datetime
import pytz
import glob
import tempfile
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

# Import DraftKings functions
from fetch_draftkings_draftables import fetch_direct, fetch_via_zenrows, extract_player_data, fetch_draftgroup_info
from optimize_lineups_by_wave import get_matchups_with_times, group_games_by_wave, optimize_lineups_by_wave, combine_predictions_for_waves, optimize_combined_waves
from generate_predictions_batch import generate_predictions_for_date, get_matchups_for_date
from optimize_draftkings_nba_lineup import load_draftables, format_lineup_output, calculate_boom_bust_probabilities, merge_draftables_with_predictions, add_position_flags

# Import prediction functions
import player_functions as pf
import prediction_model as pm
import injury_report as ir
import prediction_features as pred_feat
import prediction_store
from theme_colors import tc

st.set_page_config(
    page_title="DraftKings Optimizer",
    page_icon="🎯",
    layout="wide"
)

st.title("🎯 DraftKings Lineup Optimizer")

# Initialize session state
if 'draftables_df' not in st.session_state:
    st.session_state.draftables_df = None
if 'draftgroup_id' not in st.session_state:
    st.session_state.draftgroup_id = None
if 'optimized_lineups' not in st.session_state:
    st.session_state.optimized_lineups = {}
if 'dk_games' not in st.session_state:
    st.session_state.dk_games = []  # list of game dicts from draftGroup.games
if 'stack_recommendation' not in st.session_state:
    st.session_state.stack_recommendation = None
if 'stack_llm_reason' not in st.session_state:
    st.session_state.stack_llm_reason = None
if 'merged_df' not in st.session_state:
    st.session_state.merged_df = None

# Sidebar settings
with st.sidebar:
    st.header("⚙️ Settings")
    
    # Draftgroup ID input
    draftgroup_id_input = st.text_input(
        "DraftKings Draftgroup ID",
        value=str(st.session_state.draftgroup_id) if st.session_state.draftgroup_id else "",
        help="Enter the DraftKings draftgroup ID (e.g., 140610)"
    )
    
    # Date picker
    selected_date = st.date_input(
        "Game Date",
        value=date.today(),
        help="Select the date for the games you want to optimize"
    )
    
    # Max salary
    max_salary = st.number_input(
        "Max Salary",
        min_value=40000,
        max_value=60000,
        value=50000,
        step=1000,
        help="Maximum total salary for the lineup"
    )
    
    # Include injured players toggle
    include_injured = st.checkbox(
        "Include Injured Players",
        value=False,
        help="Include players marked as OUT or DOUBTFUL in predictions"
    )
    
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
                help="More iterations = more accurate distribution but slower per player."
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
                help="0 = automatically uses the player's own historical minute variability."
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

    # Contest type selector
    contest_type = st.radio(
        "Contest Type",
        ["GPP (Tournament)", "Cash (H2H / 50-50)"],
        index=0,
        help="GPP: maximize upside/differentiation. Cash: maximize floor/consistency.",
    )
    contest_type_key = 'gpp' if contest_type.startswith('GPP') else 'cash'

    st.markdown("---")

    # Clear cache button
    if st.button("🗑️ Clear Cache", width='stretch'):
        st.cache_data.clear()
        st.session_state.draftables_df = None
        st.session_state.draftgroup_id = None
        st.session_state.optimized_lineups = {}
        st.session_state.dk_games = []
        st.session_state.stack_recommendation = None
        st.session_state.stack_llm_reason = None
        st.session_state.merged_df = None
        st.success("Cache cleared!")
        st.rerun()

# Main content area
# Section 1: Draftables
st.header("📋 DraftKings Draftables")

if draftgroup_id_input:
    try:
        draftgroup_id = int(draftgroup_id_input)
            
        # Check if we need to fetch new draftables
        if (st.session_state.draftgroup_id != draftgroup_id or 
            st.session_state.draftables_df is None):
            
            if st.button("🔍 Fetch Draftables", type="primary", width='stretch'):
                try:
                    with st.spinner("Fetching draftables from DraftKings API..."):
                        # Try direct fetch first
                        data = fetch_direct(draftgroup_id)
                    
                        # If direct fails, try ZenRows fallback
                        if data is None:
                            st.info("Direct fetch failed, trying ZenRows proxy...")
                            data = fetch_via_zenrows(draftgroup_id)
                        
                        if data is None:
                            st.error("❌ Failed to fetch draftables from both direct API and ZenRows proxy.")
                            st.info("💡 Tips: Check that the draftgroup ID is correct and try again. If the issue persists, ensure ZENROWS_API_KEY is set if using the proxy.")
                        elif 'draftables' not in data:
                            st.error(f"❌ Response does not contain 'draftables' array.")
                            st.code(f"Response keys: {list(data.keys())}")
                        else:
                            draftables = data['draftables']
                            if not isinstance(draftables, list):
                                st.error(f"❌ Draftables is not a list (type: {type(draftables)})")
                            elif len(draftables) == 0:
                                st.error("❌ Draftables array is empty")
                            else:
                                try:
                                    # Extract and process
                                    df = extract_player_data(draftables)
                                    
                                    # Validate required columns
                                    required_cols = ['displayName', 'salary', 'position']
                                    missing_cols = [col for col in required_cols if col not in df.columns]
                                    if missing_cols:
                                        st.error(f"❌ Missing required columns: {missing_cols}")
                                    else:
                                        # Remove duplicates
                                        original_count = len(df)
                                        df = df.drop_duplicates(subset=['displayName'], keep='first')
                                        duplicates_removed = original_count - len(df)
                                        
                                        # Validate salary data
                                        if df['salary'].isna().any():
                                            st.warning(f"⚠️ Warning: {df['salary'].isna().sum()} player(s) have missing salary data")
                                        
                                        # Store in session state
                                        st.session_state.draftables_df = df
                                        st.session_state.draftgroup_id = draftgroup_id

                                        # Fetch draftgroup info for game tip-off times
                                        draftgroup_info = fetch_draftgroup_info(draftgroup_id)
                                        if draftgroup_info and 'games' in draftgroup_info:
                                            st.session_state.dk_games = draftgroup_info['games']
                                        else:
                                            st.session_state.dk_games = []

                                        st.success(f"✅ Loaded {len(df)} players (removed {duplicates_removed} duplicates)")
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Error processing draftables data: {e}")
                                    import traceback
                                    st.code(traceback.format_exc())
                except Exception as e:
                    st.error(f"❌ Unexpected error fetching draftables: {e}")
                    import traceback
                    st.code(traceback.format_exc())
        else:
            # Show current draftables info - full width
            df = st.session_state.draftables_df
            st.success(f"✅ Draftables loaded: {len(df)} players")

            # Salary range and position distribution
            if 'salary' in df.columns:
                st.metric("Salary Range", f"${df['salary'].min():,.0f} - ${df['salary'].max():,.0f}")

            # Position distribution - compact display with larger font
            if 'position' in df.columns:
                st.markdown("### Position Distribution")
                position_counts = df['position'].value_counts().head(10)
                pos_text = " | ".join([f"{pos}: {count}" for pos, count in position_counts.items()])
                st.markdown(f"**{pos_text}**")

            # Game tip-off times from draftgroup info
            if st.session_state.dk_games:
                st.markdown("### Tip-Off Times")
                _ct_tz = pytz.timezone('US/Central')
                _game_rows = []
                for g in st.session_state.dk_games:
                    start_utc = g.get('startDate', '')
                    desc = g.get('description', '')
                    try:
                        dt_utc = datetime.fromisoformat(start_utc.replace('Z', '+00:00'))
                        dt_ct = dt_utc.astimezone(_ct_tz)
                        tip_str = dt_ct.strftime('%-I:%M %p CT')
                    except Exception:
                        tip_str = start_utc
                    _game_rows.append({'Matchup': desc, 'Tip-Off (CT)': tip_str})
                st.dataframe(pd.DataFrame(_game_rows), hide_index=True, width='stretch')
            
    except ValueError:
        st.warning("⚠️ Please enter a valid draftgroup ID (numbers only)")
else:
    st.info("👆 Enter a DraftKings draftgroup ID above to fetch draftables")

# Section 2: Schedule and Wave Selection
st.markdown("---")
st.header("📅 Schedule & Tip-Off Waves")

# Initialize variables
matchups = []
waves = {}
selected_waves = []
selected_matchups = []
existing_predictions = {}
team_fpts_scalars = {}
stack_team = None
stack_count = 2

# Get matchups for selected date
@st.cache_data(ttl=3600)
def get_cached_matchups(selected_date):
    return get_matchups_with_times(selected_date)

if st.session_state.draftables_df is None:
    st.warning("⚠️ Please fetch draftables first before selecting games")
else:
    matchups = get_cached_matchups(selected_date)
    
    if len(matchups) == 0:
        st.info(f"ℹ️ No games scheduled for {selected_date.strftime('%Y-%m-%d')}")
    else:
        ct_tz = pytz.timezone('US/Central')

        # Build set of wave times from DK games (if available) to restrict the slate
        dk_wave_times = set()
        if st.session_state.dk_games:
            for g in st.session_state.dk_games:
                start_utc = g.get('startDate', '')
                try:
                    dt_utc = datetime.fromisoformat(start_utc.replace('Z', '+00:00'))
                    dt_ct = dt_utc.astimezone(ct_tz)
                    hour_12 = dt_ct.hour % 12 or 12
                    am_pm = "AM" if dt_ct.hour < 12 else "PM"
                    dk_wave_times.add(f"{hour_12}:{dt_ct.minute:02d} {am_pm} CT")
                except Exception:
                    pass

        # Group NBA API matchups by tip-off wave, restricted to DK slate times
        waves_dict = defaultdict(list)
        for matchup in matchups:
            game_datetime = matchup['game_datetime']
            game_time_ct = game_datetime.astimezone(ct_tz)
            hour_12 = game_time_ct.hour % 12 or 12
            am_pm = "AM" if game_time_ct.hour < 12 else "PM"
            wave_time_str = f"{hour_12}:{game_time_ct.minute:02d} {am_pm} CT"
            # Only include this game if it falls in a DK slate wave (or no DK data available)
            if not dk_wave_times or wave_time_str in dk_wave_times:
                waves_dict[wave_time_str].append(matchup)

        waves = dict(waves_dict)

        # Display waves and allow selection
        st.subheader("Select Tip-Off Waves")

        wave_options = sorted(waves.keys())
        if dk_wave_times and not wave_options:
            st.warning("⚠️ No NBA schedule matches found for the DK slate tip-off times. Check the selected date.")
        selected_waves = st.multiselect(
            "Tip-Off Times",
            options=wave_options,
            default=wave_options,  # Select all by default
            help="Select which tip-off waves to optimize lineups for"
        )
        selected_matchups = [m for wt in selected_waves for m in waves.get(wt, [])]

        # Show games for selected waves
        if selected_waves:
            st.markdown("**Games in selected waves:**")
            for wave_time in sorted(selected_waves):
                games_in_wave = waves[wave_time]
                with st.expander(f"{wave_time} ({len(games_in_wave)} game(s))"):
                    for matchup in games_in_wave:
                        st.text(f"  • {matchup['matchup']}")
        else:
            st.warning("⚠️ Please select at least one tip-off wave")

        # Implied totals expander (only when waves are selected)
        LEAGUE_AVG_SCORE = 113.0
        team_fpts_scalars = {}
        if selected_waves:
            @st.cache_data(ttl=1800, show_spinner=False)
            def fetch_odds_totals(utc_date_prefixes: tuple):
                """Fetch per-team implied totals from The Odds API using totals + spreads markets.
                Formula: away_implied = (total - away_spread) / 2
                         home_implied = (total + away_spread) / 2
                Returns ({abbr: implied_total}, status_str).
                """
                import requests
                api_key = os.environ.get('THE_ODDS_API_KEY', '')
                if not api_key:
                    return {}, "THE_ODDS_API_KEY not set"
                url = "https://api.the-odds-api.com/v4/sports/basketball_nba/odds"
                params = {
                    'apiKey': api_key,
                    'regions': 'us',
                    'markets': 'totals,spreads',
                    'dateFormat': 'iso',
                    'oddsFormat': 'american',
                }
                try:
                    resp = requests.get(url, params=params, timeout=10)
                    resp.raise_for_status()
                    games = resp.json()
                except Exception as e:
                    return {}, f"Odds API error: {e}"

                from nba_api.stats.static import teams as nba_teams
                name_to_abbr = {t['full_name']: t['abbreviation'] for t in nba_teams.get_teams()}
                nick_to_abbr = {t['nickname']: t['abbreviation'] for t in nba_teams.get_teams()}

                def resolve_abbr(full_name):
                    if full_name in name_to_abbr:
                        return name_to_abbr[full_name]
                    return nick_to_abbr.get(full_name.split()[-1], full_name)

                implied = {}
                for game in games:
                    commence = game.get('commence_time', '')
                    if utc_date_prefixes and not any(commence.startswith(d) for d in utc_date_prefixes):
                        continue
                    away_name = game.get('away_team', '')
                    away_abbr = resolve_abbr(away_name)
                    home_abbr = resolve_abbr(game.get('home_team', ''))

                    total = None
                    away_spread = None
                    for bm in game.get('bookmakers', []):
                        for market in bm.get('markets', []):
                            if market.get('key') == 'totals' and total is None:
                                for outcome in market.get('outcomes', []):
                                    if outcome.get('name') == 'Over':
                                        total = float(outcome['point'])
                                        break
                            if market.get('key') == 'spreads' and away_spread is None:
                                for outcome in market.get('outcomes', []):
                                    if outcome.get('name') == away_name:
                                        away_spread = float(outcome['point'])
                                        break
                        if total is not None and away_spread is not None:
                            break

                    if total is not None:
                        if away_spread is not None:
                            implied[away_abbr] = (total - away_spread) / 2
                            implied[home_abbr] = (total + away_spread) / 2
                        else:
                            # No spread available — fall back to symmetric split
                            implied[away_abbr] = total / 2
                            implied[home_abbr] = total / 2

                return implied, f"Loaded {len(implied) // 2} game total(s)"

            # Build UTC date prefixes from DK games' startDate values (most reliable source).
            # DK startDates are UTC — late ET games fall on the next UTC day, so we can't
            # just use the local selected_date string.
            from datetime import timedelta
            if st.session_state.dk_games:
                _utc_prefixes = tuple(sorted({
                    g['startDate'][:10]
                    for g in st.session_state.dk_games
                    if g.get('startDate')
                }))
            else:
                # Fallback: cover selected_date and next UTC day (handles ET→UTC overflow)
                _d = selected_date.strftime('%Y-%m-%d')
                _d1 = (selected_date + timedelta(days=1)).strftime('%Y-%m-%d')
                _utc_prefixes = (_d, _d1)

            with st.expander("📈 Implied Totals (optional)", expanded=False):
                st.caption("Auto-fetched from The Odds API. Edit any value to override. Leave at 113.0 to skip scaling.")
                odds_col1, odds_col2 = st.columns([3, 1])
                with odds_col2:
                    refresh_odds = st.button("🔄 Refresh Odds", key="refresh_odds")
                if refresh_odds:
                    fetch_odds_totals.clear()

                fetched_totals, odds_status = fetch_odds_totals(_utc_prefixes)
                with odds_col1:
                    if fetched_totals:
                        st.caption(f"✅ {odds_status}")
                    else:
                        st.caption(f"⚠️ {odds_status} — enter totals manually below.")

                for wave_time in sorted(selected_waves):
                    for matchup in waves.get(wave_time, []):
                        away = matchup['away_team']
                        home = matchup['home_team']
                        col1, col2 = st.columns(2)
                        with col1:
                            away_impl = st.number_input(
                                away, min_value=80.0, max_value=160.0,
                                value=float(fetched_totals.get(away, LEAGUE_AVG_SCORE)),
                                step=0.5, key=f"impl_{away}_{wave_time}"
                            )
                        with col2:
                            home_impl = st.number_input(
                                home, min_value=80.0, max_value=160.0,
                                value=float(fetched_totals.get(home, LEAGUE_AVG_SCORE)),
                                step=0.5, key=f"impl_{home}_{wave_time}"
                            )
                        if away_impl != LEAGUE_AVG_SCORE:
                            team_fpts_scalars[away] = away_impl / LEAGUE_AVG_SCORE
                        if home_impl != LEAGUE_AVG_SCORE:
                            team_fpts_scalars[home] = home_impl / LEAGUE_AVG_SCORE

# Section 3: Predictions
st.markdown("---")
st.header("📊 Predictions")

# Use a session-scoped temp directory — no CSV files ever land in ~/Downloads
if '_dk_temp_dir' not in st.session_state or not os.path.isdir(st.session_state.get('_dk_temp_dir', '')):
    st.session_state._dk_temp_dir = tempfile.mkdtemp(prefix='dk_optimizer_')
downloads_dir = st.session_state._dk_temp_dir
game_date_str = selected_date.strftime('%Y-%m-%d')

if st.session_state.draftables_df is None or len(matchups) == 0:
    st.info("ℹ️ Fetch draftables and select a date with games to continue")
else:
    # Check for existing prediction files
    pattern = os.path.join(downloads_dir, f"predicted_statlines_*_{game_date_str}.csv")
    existing_prediction_files = glob.glob(pattern)
    
    # Map matchups to prediction files (only for selected wave games)
    existing_predictions = {}
    for matchup in selected_matchups:
        prediction_file = os.path.join(
            downloads_dir,
            f"predicted_statlines_{matchup['away_team']}_vs_{matchup['home_team']}_{game_date_str}.csv"
        )
        if os.path.exists(prediction_file):
            existing_predictions[matchup['matchup']] = prediction_file

    # Restore missing prediction CSVs from Supabase cache
    _sb_df = prediction_store.load_predictions_for_date(game_date_str)
    if _sb_df is not None:
        for _sm in selected_matchups:
            _smk = _sm['matchup']
            if _smk not in existing_predictions:
                _saw = _sm['away_team']
                _shm = _sm['home_team']
                _sb_csv = prediction_store.reconstruct_csv_df(_sb_df, _saw, _shm)
                if not _sb_csv.empty:
                    _sb_csv_path = os.path.join(
                        downloads_dir,
                        f"predicted_statlines_{_saw}_vs_{_shm}_{game_date_str}.csv"
                    )
                    _sb_csv.to_csv(_sb_csv_path, index=False)
                    existing_predictions[_smk] = _sb_csv_path

    # Cached injury/player data in shared scope so we can clear injury cache from both tabs
    @st.cache_data(ttl=1800, show_spinner="Loading player data...")
    def load_injury_player_data():
        return pf.get_players_dataframe()

    @st.cache_data(ttl=600, show_spinner="Fetching injury report...")
    def fetch_injury_data(selected_date):
        players_df = load_injury_player_data()
        return ir.fetch_injuries_for_date(selected_date, players_df)

    @st.cache_data(ttl=1800, show_spinner=False)
    def get_hot_cold_for_team(team_id: int, current_player_ids: frozenset = frozenset(), threshold_pct: float = 0.20, min_l5_games: int = 3):
        """
        Compute hot/cold players for a team from bulk game logs.
        Hot  = L5 avg >= threshold_pct above season avg in PTS, REB, or AST
        Cold = L5 avg <= threshold_pct below season avg in PTS, REB, or AST
        Returns: (hot_players, cold_players) — each a sorted list of dicts.
        """
        try:
            bulk_logs = pred_feat.get_bulk_player_game_logs()
        except Exception:
            return [], []

        if len(bulk_logs) == 0 or 'TEAM_ID' not in bulk_logs.columns:
            return [], []

        team_logs = bulk_logs[bulk_logs['TEAM_ID'].astype(int) == int(team_id)].copy()
        if len(team_logs) == 0:
            return [], []

        name_col = 'PLAYER_NAME' if 'PLAYER_NAME' in team_logs.columns else None
        if name_col is None:
            return [], []

        # Season averages
        season = team_logs.groupby('PLAYER_ID').agg(
            GP=('GAME_ID', 'count'),
            PTS=('PTS', 'mean'),
            REB=('REB', 'mean'),
            AST=('AST', 'mean'),
            Player=(name_col, 'first'),
        )

        # L5 averages
        sorted_logs = team_logs.sort_values('GAME_DATE', ascending=False)
        l5 = sorted_logs.groupby('PLAYER_ID').head(5).groupby('PLAYER_ID').agg(
            L5_GP=('GAME_ID', 'count'),
            L5_PTS=('PTS', 'mean'),
            L5_REB=('REB', 'mean'),
            L5_AST=('AST', 'mean'),
        )

        merged = season.join(l5, how='inner')
        merged = merged[merged['L5_GP'] >= min_l5_games]
        if current_player_ids:
            merged = merged[merged.index.astype(str).isin(current_player_ids)]

        hot_players, cold_players = [], []
        for player_id, row in merged.iterrows():
            if row['PTS'] < 3:
                continue
            hot_stats, cold_stats = [], []
            for stat, l5_col in [('PTS', 'L5_PTS'), ('REB', 'L5_REB'), ('AST', 'L5_AST')]:
                sv, lv = row[stat], row[l5_col]
                if sv > 0.5:
                    pct = (lv - sv) / sv
                    if pct >= threshold_pct:
                        hot_stats.append({'stat': stat, 'season': round(sv, 1), 'l5': round(lv, 1), 'pct': pct})
                    elif pct <= -threshold_pct and sv >= 8.0:
                        cold_stats.append({'stat': stat, 'season': round(sv, 1), 'l5': round(lv, 1), 'pct': pct})
            name = row.get('Player', f'Player {player_id}')
            if hot_stats:
                hot_players.append({'player': name, 'hot_stats': sorted(hot_stats, key=lambda x: -x['pct']), 'best_pct': max(s['pct'] for s in hot_stats)})
            if cold_stats:
                cold_players.append({'player': name, 'cold_stats': sorted(cold_stats, key=lambda x: x['pct']), 'worst_pct': min(s['pct'] for s in cold_stats)})

        hot_players.sort(key=lambda x: -x['best_pct'])
        cold_players.sort(key=lambda x: x['worst_pct'])
        return hot_players, cold_players

    @st.cache_data(ttl=1800, show_spinner=False)
    def get_rotation_players(team_id: int, current_player_ids: frozenset = frozenset(), min_minutes: float = 12.0, min_games: int = 5):
        """
        Return a team's rotation players (min >= min_minutes, gp >= min_games)
        sorted by season minutes descending. Used for minute-opportunity analysis.
        """
        try:
            bulk_logs = pred_feat.get_bulk_player_game_logs()
        except Exception:
            return []

        if len(bulk_logs) == 0 or 'TEAM_ID' not in bulk_logs.columns:
            return []

        team_logs = bulk_logs[bulk_logs['TEAM_ID'].astype(int) == int(team_id)].copy()
        if len(team_logs) == 0:
            return []

        name_col = 'PLAYER_NAME' if 'PLAYER_NAME' in team_logs.columns else None
        if name_col is None:
            return []

        season = team_logs.groupby('PLAYER_ID').agg(
            GP=('GAME_ID', 'count'),
            MIN=('MIN', 'mean'),
            PTS=('PTS', 'mean'),
            Player=(name_col, 'first'),
        )
        sorted_logs = team_logs.sort_values('GAME_DATE', ascending=False)
        l5 = sorted_logs.groupby('PLAYER_ID').head(5).groupby('PLAYER_ID').agg(
            L5_MIN=('MIN', 'mean'),
        )

        merged = season.join(l5, how='left')
        merged = merged[(merged['GP'] >= min_games) & (merged['MIN'] >= min_minutes)]
        if current_player_ids:
            merged = merged[merged.index.astype(str).isin(current_player_ids)]
        merged = merged.sort_values('MIN', ascending=False)

        return [
            {
                'player': row['Player'],
                'player_id': str(idx),
                'min_avg': round(row['MIN'], 1),
                'l5_min': round(row.get('L5_MIN', row['MIN']), 1),
                'pts_avg': round(row['PTS'], 1),
                'gp': int(row['GP']),
            }
            for idx, row in merged.iterrows()
        ]

    @st.cache_data(ttl=1800, show_spinner=False)
    def get_role_changes_for_team(team_id: int, current_player_ids: frozenset = frozenset(), threshold_pct: float = 0.20, min_l5_games: int = 3, min_season_min: float = 8.0):
        """
        Detect players with meaningful minute changes vs their season average.
        Emerging = L5 MIN avg >= threshold_pct above season MIN avg
        Declining = L5 MIN avg <= threshold_pct below season MIN avg
        Only considers players averaging >= min_season_min minutes/game.
        """
        try:
            bulk_logs = pred_feat.get_bulk_player_game_logs()
        except Exception:
            return [], []

        if len(bulk_logs) == 0 or 'TEAM_ID' not in bulk_logs.columns:
            return [], []

        team_logs = bulk_logs[bulk_logs['TEAM_ID'].astype(int) == int(team_id)].copy()
        if len(team_logs) == 0 or 'MIN' not in team_logs.columns:
            return [], []

        name_col = 'PLAYER_NAME' if 'PLAYER_NAME' in team_logs.columns else None
        if name_col is None:
            return [], []

        season = team_logs.groupby('PLAYER_ID').agg(
            GP=('GAME_ID', 'count'),
            MIN=('MIN', 'mean'),
            PTS=('PTS', 'mean'),
            Player=(name_col, 'first'),
        )

        sorted_logs = team_logs.sort_values('GAME_DATE', ascending=False)
        l5 = sorted_logs.groupby('PLAYER_ID').head(5).groupby('PLAYER_ID').agg(
            L5_GP=('GAME_ID', 'count'),
            L5_MIN=('MIN', 'mean'),
            L5_PTS=('PTS', 'mean'),
        )

        merged = season.join(l5, how='inner')
        merged = merged[
            (merged['L5_GP'] >= min_l5_games) &
            (merged['MIN'] >= min_season_min)
        ]
        if current_player_ids:
            merged = merged[merged.index.astype(str).isin(current_player_ids)]

        emerging, declining = [], []
        for _, row in merged.iterrows():
            szn_min = row['MIN']
            l5_min = row['L5_MIN']
            if szn_min <= 0:
                continue
            pct = (l5_min - szn_min) / szn_min
            entry = {
                'player': row['Player'],
                'min_szn': round(szn_min, 1),
                'min_l5': round(l5_min, 1),
                'pts_szn': round(row['PTS'], 1),
                'pts_l5': round(row['L5_PTS'], 1),
                'pct': pct,
            }
            if pct >= threshold_pct:
                emerging.append(entry)
            elif pct <= -threshold_pct:
                declining.append(entry)

        emerging.sort(key=lambda x: -x['pct'])
        declining.sort(key=lambda x: x['pct'])
        return emerging, declining

    # Create tabs for Predictions, Injury Report, and Hot/Cold
    pred_tab, injury_tab, hot_cold_tab = st.tabs(["📊 Predictions", "🏥 Injury Report", "🔥 Hot & Cold"])
    
    with pred_tab:
        # Show prediction status
        col1, col2 = st.columns([2, 1])
        
        with col1:
            if len(existing_predictions) == len(selected_matchups):
                st.success(f"✅ Predictions available for all {len(selected_matchups)} game(s)")
            elif len(existing_predictions) > 0:
                st.warning(f"⚠️ Predictions available for {len(existing_predictions)}/{len(selected_matchups)} game(s)")
            else:
                st.info(f"ℹ️ No predictions found. Will generate for {len(selected_matchups)} game(s)")

        with col2:
            # Show generate button if predictions are missing
            if len(existing_predictions) < len(selected_matchups):
                if st.button("🔄 Generate Predictions", type="primary", width='stretch'):
                    try:
                        _progress_bar = st.progress(0, text="Starting prediction generation…")

                        def _gen_progress(game_idx, total_games, player_cur, player_tot, player_name, matchup_str):
                            frac = (game_idx - 1 + player_cur / max(player_tot, 1)) / max(total_games, 1)
                            _progress_bar.progress(
                                min(frac, 1.0),
                                text=f"Game {game_idx}/{total_games} — ({player_cur}/{player_tot}) {player_name} ({matchup_str})"
                            )

                        exclude_injured = not include_injured
                        output_files = generate_predictions_for_date(
                            selected_date,
                            output_dir=downloads_dir,
                            exclude_injured=exclude_injured,
                            optimize_lineups=False,
                            simulation_config=_simulation_config,
                            progress_callback=_gen_progress,
                        )
                        _progress_bar.empty()

                        if len(output_files) > 0:
                            # Upload newly generated predictions to Supabase
                            for _of in output_files:
                                try:
                                    _fn = os.path.basename(_of)
                                    _parts = _fn.replace('predicted_statlines_', '').replace(f'_{game_date_str}.csv', '').split('_vs_')
                                    if len(_parts) == 2:
                                        _aw, _hm = _parts
                                        _csv_df = pd.read_csv(_of)
                                        if 'player_id' in _csv_df.columns:
                                            _sls = _csv_df.to_dict('records')
                                            prediction_store.upload_game_predictions(game_date_str, _aw, _hm, _sls)
                                except Exception:
                                    pass
                            st.success(f"✅ Generated {len(output_files)} prediction file(s)")
                            st.rerun()
                        else:
                            st.error("❌ No prediction files were generated. Check the console for errors.")
                    except Exception as e:
                        st.error(f"❌ Error generating predictions: {e}")
                        import traceback
                        with st.expander("Error Details"):
                            st.code(traceback.format_exc())
                        st.info("💡 Tips: Ensure you have internet connectivity and that the NBA API is accessible.")
            
            # Always show regenerate button (even when predictions exist)
            st.caption("Uses the latest injury report and refreshes the injury tab after run.")
            if st.button("🔄 Regenerate All Predictions", type="secondary", width='stretch'):
                try:
                    # Clear injury cache so regeneration uses fresh injuries
                    fetch_injury_data.clear()
                    # Delete existing prediction files first (but only for games that haven't started)
                    from datetime import datetime
                    now_utc = datetime.now(pytz.UTC)
                    deleted_count = 0
                    skipped_started_count = 0

                    for matchup in matchups:
                        game_datetime = matchup.get('game_datetime')

                        if game_datetime is not None:
                            if isinstance(game_datetime, pd.Timestamp):
                                if game_datetime.tzinfo is None:
                                    game_datetime = pytz.UTC.localize(game_datetime.to_pydatetime())
                                else:
                                    game_datetime = game_datetime.to_pydatetime()

                            if game_datetime < now_utc:
                                skipped_started_count += 1
                                continue

                        prediction_file = os.path.join(
                            downloads_dir,
                            f"predicted_statlines_{matchup['away_team']}_vs_{matchup['home_team']}_{game_date_str}.csv"
                        )
                        if os.path.exists(prediction_file):
                            try:
                                os.remove(prediction_file)
                                deleted_count += 1
                            except Exception as e:
                                st.warning(f"⚠️ Could not delete {prediction_file}: {e}")

                    if deleted_count > 0:
                        st.info(f"🗑️ Deleted {deleted_count} existing prediction file(s)")
                    if skipped_started_count > 0:
                        st.info(f"⏭️  Skipped {skipped_started_count} game(s) that have already started or finished")

                    _progress_bar = st.progress(0, text="Starting prediction generation…")

                    def _regen_progress(game_idx, total_games, player_cur, player_tot, player_name, matchup_str):
                        frac = (game_idx - 1 + player_cur / max(player_tot, 1)) / max(total_games, 1)
                        _progress_bar.progress(
                            min(frac, 1.0),
                            text=f"Game {game_idx}/{total_games} — ({player_cur}/{player_tot}) {player_name} ({matchup_str})"
                        )

                    exclude_injured = not include_injured
                    output_files = generate_predictions_for_date(
                        selected_date,
                        output_dir=downloads_dir,
                        exclude_injured=exclude_injured,
                        optimize_lineups=False,
                        simulation_config=_simulation_config,
                        progress_callback=_regen_progress,
                    )
                    _progress_bar.empty()

                    if len(output_files) > 0:
                        # Upload regenerated predictions to Supabase
                        for _of in output_files:
                            try:
                                _fn = os.path.basename(_of)
                                _parts = _fn.replace('predicted_statlines_', '').replace(f'_{game_date_str}.csv', '').split('_vs_')
                                if len(_parts) == 2:
                                    _aw, _hm = _parts
                                    _csv_df = pd.read_csv(_of)
                                    if 'player_id' in _csv_df.columns:
                                        _sls = _csv_df.to_dict('records')
                                        prediction_store.upload_game_predictions(game_date_str, _aw, _hm, _sls)
                            except Exception:
                                pass
                        st.success(f"✅ Regenerated {len(output_files)} prediction file(s)")
                        st.rerun()
                    else:
                        st.error("❌ No prediction files were generated. Check the console for errors.")
                except Exception as e:
                    st.error(f"❌ Error regenerating predictions: {e}")
                    import traceback
                    with st.expander("Error Details"):
                        st.code(traceback.format_exc())
                    st.info("💡 Tips: Ensure you have internet connectivity and that the NBA API is accessible.")
    
    with injury_tab:
        st.markdown("### Injury Report for Games")
        st.caption("Latest report (e.g. 6 PM ET) may differ from earlier; use Refresh to fetch now.")
        if st.button("🔄 Refresh injury report", type="secondary", key="refresh_injury_report"):
            fetch_injury_data.clear()
            st.rerun()
        st.markdown("")  # spacing

        def _inj_status_color(status):
            s = (status or '').lower()
            if 'out' in s:          return tc.injury_out
            if 'doubtful' in s:     return tc.injury_doubtful
            if 'questionable' in s: return tc.injury_questionable
            if 'probable' in s:     return tc.injury_probable
            return tc.injury_unknown

        def _inj_sort_key(inj):
            s = (inj.get('status', '') or '').lower()
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
                for inj in injuries:
                    status    = inj.get('status', '')
                    color     = _inj_status_color(status)
                    name      = ir.format_player_name(inj.get('player_name', ''))
                    reason    = ir.format_injury_reason(inj.get('reason', ''))
                    player_id = inj.get('player_id', '')
                    headshot  = (
                        f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png"
                        if player_id else ""
                    )
                    st.markdown(
                        f"""<div style="display:flex; align-items:center; gap:12px;
                                        padding:8px 0; border-bottom:1px solid #eee;">
                            <img src="{headshot}"
                                 style="width:75px; height:55px; object-fit:cover;
                                        border-radius:4px; background-color:{tc.img_placeholder};"
                                 onerror="this.style.display='none'">
                            <div style="flex:1;">
                                <span style="font-weight:bold;">{name}</span>
                                <span style="background-color:{color}; color:white;
                                             padding:2px 6px; border-radius:3px;
                                             font-size:12px; margin-left:8px;">{status}</span>
                                <br><span style="font-size:13px; color:#666;">{reason}</span>
                            </div>
                        </div>""",
                        unsafe_allow_html=True,
                    )
            else:
                st.info("No injuries reported")

        try:
            players_df_injury = load_injury_player_data()
            injury_df, injury_status = fetch_injury_data(selected_date)
            if injury_df is not None and len(injury_df) > 0:
                st.success(f"✅ {injury_status}")

                for matchup in selected_matchups:
                    away_team    = matchup['away_team']
                    home_team    = matchup['home_team']
                    away_team_id = matchup.get('away_team_id', '')
                    home_team_id = matchup.get('home_team_id', '')
                    matchup_str  = matchup['matchup']

                    game_datetime = matchup.get('game_datetime')
                    if game_datetime:
                        ct_tz = pytz.timezone('US/Central')
                        if game_datetime.tzinfo is None:
                            game_datetime = pytz.UTC.localize(game_datetime)
                        game_time_ct = game_datetime.astimezone(ct_tz)
                        hour_12 = game_time_ct.hour % 12 or 12
                        am_pm = "AM" if game_time_ct.hour < 12 else "PM"
                        tip_time_str = f"{hour_12}:{game_time_ct.minute:02d} {am_pm} CT"
                        matchup_with_time = f"{matchup_str} | {tip_time_str}"
                    else:
                        matchup_with_time = matchup_str

                    st.markdown(f"#### {matchup_with_time}")

                    matchup_injuries = ir.get_injuries_for_matchup(
                        injury_df, away_team, home_team, players_df_injury
                    )
                    away_injuries = sorted(matchup_injuries.get('away', []), key=_inj_sort_key)
                    home_injuries = sorted(matchup_injuries.get('home', []), key=_inj_sort_key)

                    if not away_injuries and not home_injuries:
                        st.info(f"No injuries reported for {matchup_str}")
                    else:
                        inj_col1, inj_col2 = st.columns(2)
                        with inj_col1:
                            _render_team_injuries(away_injuries, away_team, away_team_id)
                        with inj_col2:
                            _render_team_injuries(home_injuries, home_team, home_team_id)

                    st.markdown("---")
            else:
                st.warning(f"⚠️ {injury_status}")
                st.info("💡 Injury reports are typically available closer to game time. Try again later.")
        except Exception as e:
            st.error(f"❌ Error fetching injury report: {e}")
            import traceback
            with st.expander("Error Details"):
                st.code(traceback.format_exc())

    with hot_cold_tab:
        st.markdown("### Hot & Cold Players")
        st.caption("Hot = L5 avg ≥ 20% above season avg | Cold = L5 avg ≥ 20% below season avg (PTS, REB, or AST) | Emerging/Declining = ≥20% change in minutes")

        # Position compatibility groups for minute-opportunity matching
        POSITION_COMPAT = {
            'G':   {'G', 'PG', 'SG', 'G-F'},
            'PG':  {'PG', 'G', 'SG', 'G-F'},
            'SG':  {'SG', 'G', 'PG', 'G-F'},
            'G-F': {'G-F', 'G', 'F', 'SG', 'SF'},
            'F':   {'F', 'SF', 'PF', 'F-C', 'G-F'},
            'SF':  {'SF', 'F', 'PF', 'G-F'},
            'PF':  {'PF', 'F', 'SF', 'F-C', 'C'},
            'F-C': {'F-C', 'F', 'PF', 'C'},
            'C':   {'C', 'C-F', 'F-C', 'PF'},
            'C-F': {'C-F', 'C', 'F-C', 'PF'},
        }

        try:
            # Reuse injury data for minute-opportunity section
            players_df_hc = load_injury_player_data()
            injury_df_hc, _ = fetch_injury_data(selected_date)

            # Build PERSON_ID → POSITION map from PlayerIndex (already loaded)
            pos_map = {}
            if players_df_hc is not None and len(players_df_hc) > 0:
                if 'PERSON_ID' in players_df_hc.columns and 'POSITION' in players_df_hc.columns:
                    pos_map = {
                        str(row['PERSON_ID']): str(row['POSITION'])
                        for _, row in players_df_hc[['PERSON_ID', 'POSITION']].dropna().iterrows()
                    }

            def current_roster_ids(team_id: int) -> frozenset:
                """Return frozenset of current PERSON_IDs for a team from PlayerIndex."""
                if players_df_hc is None or len(players_df_hc) == 0:
                    return frozenset()
                tid_col = next((c for c in ('TEAM_ID', 'TeamID') if c in players_df_hc.columns), None)
                pid_col = next((c for c in ('PERSON_ID', 'PlayerID') if c in players_df_hc.columns), None)
                if tid_col is None or pid_col is None:
                    return frozenset()
                return frozenset(
                    players_df_hc[players_df_hc[tid_col].astype(int) == int(team_id)][pid_col].astype(str).tolist()
                )

            for matchup in selected_matchups:
                away_team = matchup['away_team']
                home_team = matchup['home_team']
                away_team_id = matchup['away_team_id']
                home_team_id = matchup['home_team_id']
                matchup_str = matchup['matchup']

                # Tip time label (reuse same formatting as injury tab)
                game_datetime = matchup.get('game_datetime')
                if game_datetime:
                    ct_tz = pytz.timezone('US/Central')
                    if game_datetime.tzinfo is None:
                        game_datetime = pytz.UTC.localize(game_datetime)
                    game_time_ct = game_datetime.astimezone(ct_tz)
                    hour_12 = game_time_ct.hour % 12 or 12
                    am_pm = "AM" if game_time_ct.hour < 12 else "PM"
                    tip_label = f"{matchup_str} | {hour_12}:{game_time_ct.minute:02d} {am_pm} CT"
                else:
                    tip_label = matchup_str

                st.markdown(f"#### {tip_label}")

                # --- Hot & Cold ---
                with st.spinner(f"Loading hot/cold data for {matchup_str}..."):
                    away_hot, away_cold = get_hot_cold_for_team(away_team_id, current_roster_ids(away_team_id))
                    home_hot, home_cold = get_hot_cold_for_team(home_team_id, current_roster_ids(home_team_id))

                def build_player_table(players, stat_key, pct_key):
                    rows = []
                    for p in players:
                        row = {'Player': p['player']}
                        for s in p[stat_key]:
                            arrow = '▲' if s['pct'] > 0 else '▼'
                            row[s['stat']] = f"{s['l5']} ({arrow}{abs(s['pct'])*100:.0f}% vs {s['season']} szn)"
                        row['Best Δ'] = f"{p[pct_key]*100:+.0f}%"
                        rows.append(row)
                    return pd.DataFrame(rows) if rows else None

                hc_col1, hc_col2 = st.columns(2)

                with hc_col1:
                    st.markdown(f"**{away_team}**")
                    if away_hot:
                        st.markdown("🔥 **Hot Players**")
                        df = build_player_table(away_hot, 'hot_stats', 'best_pct')
                        if df is not None:
                            st.dataframe(df, width='stretch', hide_index=True)
                    else:
                        st.caption("No hot players (≥20% above season avg)")

                    if away_cold:
                        st.markdown("🥶 **Cold Players**")
                        df = build_player_table(away_cold, 'cold_stats', 'worst_pct')
                        if df is not None:
                            st.dataframe(df, width='stretch', hide_index=True)
                    else:
                        st.caption("No cold players (≥20% below season avg)")

                with hc_col2:
                    st.markdown(f"**{home_team}**")
                    if home_hot:
                        st.markdown("🔥 **Hot Players**")
                        df = build_player_table(home_hot, 'hot_stats', 'best_pct')
                        if df is not None:
                            st.dataframe(df, width='stretch', hide_index=True)
                    else:
                        st.caption("No hot players (≥20% above season avg)")

                    if home_cold:
                        st.markdown("🥶 **Cold Players**")
                        df = build_player_table(home_cold, 'cold_stats', 'worst_pct')
                        if df is not None:
                            st.dataframe(df, width='stretch', hide_index=True)
                    else:
                        st.caption("No cold players (≥20% below season avg)")

                # --- Emerging / Declining Roles ---
                with st.spinner(f"Loading role change data for {matchup_str}..."):
                    away_emerging, away_declining = get_role_changes_for_team(away_team_id, current_roster_ids(away_team_id))
                    home_emerging, home_declining = get_role_changes_for_team(home_team_id, current_roster_ids(home_team_id))

                if away_emerging or away_declining or home_emerging or home_declining:
                    rc_col1, rc_col2 = st.columns(2)

                    def build_role_table(players):
                        rows = [
                            {
                                'Player': p['player'],
                                'MIN/g (szn)': p['min_szn'],
                                'MIN/g (L5)': p['min_l5'],
                                'Δ%': f"{p['pct']*100:+.0f}%",
                            }
                            for p in players
                        ]
                        return pd.DataFrame(rows) if rows else None

                    with rc_col1:
                        st.markdown(f"**{away_team}**")
                        if away_emerging:
                            st.markdown("📈 **Emerging Roles**")
                            df = build_role_table(away_emerging)
                            if df is not None:
                                st.dataframe(df, width='stretch', hide_index=True)
                        else:
                            st.caption("No emerging role players (≥20% more minutes)")

                        if away_declining:
                            st.markdown("📉 **Declining Roles**")
                            df = build_role_table(away_declining)
                            if df is not None:
                                st.dataframe(df, width='stretch', hide_index=True)
                        else:
                            st.caption("No declining role players (≥20% fewer minutes)")

                    with rc_col2:
                        st.markdown(f"**{home_team}**")
                        if home_emerging:
                            st.markdown("📈 **Emerging Roles**")
                            df = build_role_table(home_emerging)
                            if df is not None:
                                st.dataframe(df, width='stretch', hide_index=True)
                        else:
                            st.caption("No emerging role players (≥20% more minutes)")

                        if home_declining:
                            st.markdown("📉 **Declining Roles**")
                            df = build_role_table(home_declining)
                            if df is not None:
                                st.dataframe(df, width='stretch', hide_index=True)
                        else:
                            st.caption("No declining role players (≥20% fewer minutes)")

                # --- Minute Opportunities ---
                if injury_df_hc is not None and len(injury_df_hc) > 0:
                    matchup_injuries_hc = ir.get_injuries_for_matchup(
                        injury_df_hc, away_team, home_team, players_df_hc
                    )
                    concern_statuses = {'out', 'doubtful', 'questionable'}

                    def format_name(n):
                        if n and ',' in n:
                            parts = n.split(',', 1)
                            return f"{parts[1].strip()} {parts[0].strip()}"
                        return n or 'Unknown'

                    # Collect impacted teams
                    teams_with_injuries = {}
                    for side, team_abbr, team_id in [
                        ('away', away_team, away_team_id),
                        ('home', home_team, home_team_id),
                    ]:
                        side_injuries = [
                            inj for inj in matchup_injuries_hc.get(side, [])
                            if inj.get('status', '').lower() in concern_statuses
                        ]
                        if side_injuries:
                            teams_with_injuries[team_abbr] = {
                                'team_id': team_id,
                                'injuries': side_injuries,
                            }

                    if teams_with_injuries:
                        st.markdown("**📈 Minute Opportunities**")
                        st.caption("Top 2-3 healthy rotation players (≥15 min/g L5) most likely to absorb minutes for each Q/D/Out player.")
                        for team_abbr, info in teams_with_injuries.items():
                            st.markdown(f"**{team_abbr}**")

                            # Get full roster (low thresholds to catch bench players)
                            all_rotation = get_rotation_players(info['team_id'], current_roster_ids(info['team_id']), min_minutes=0, min_games=3)
                            rotation_by_name = {r['player'].lower(): r for r in all_rotation}

                            # Exclusion sets: ID-based (reliable) + name-based (fallback)
                            all_injured_ids = {
                                str(inj['player_id'])
                                for inj in info['injuries']
                                if inj.get('player_id')
                            }
                            all_injured_names = {
                                format_name(inj['player_name']).lower()
                                for inj in info['injuries']
                            }

                            # Healthy rotation (L5 min ≥ 15 min/g), enriched with position
                            healthy = [
                                dict(r, position=pos_map.get(r.get('player_id', ''), ''))
                                for r in all_rotation
                                if r.get('player_id') not in all_injured_ids
                                and r['player'].lower() not in all_injured_names
                                and r['l5_min'] >= 15.0
                            ]
                            healthy.sort(key=lambda x: -x['l5_min'])

                            for inj in info['injuries']:
                                inj_name = format_name(inj['player_name'])
                                status = inj.get('status', '?').capitalize()
                                inj_id = str(inj.get('player_id', ''))
                                inj_pos = pos_map.get(inj_id, '')
                                inj_data = rotation_by_name.get(inj_name.lower())
                                # Skip injured players who weren't playing meaningful minutes
                                if inj_data is None or inj_data['l5_min'] < 15.0:
                                    continue
                                min_str = f" — {inj_data['min_avg']} min/g" if inj_data else ""
                                pos_str = f" ({inj_pos})" if inj_pos else ""
                                st.markdown(f"*{inj_name}{pos_str} ({status}){min_str}*")

                                # Filter to position-compatible healthy players
                                compat = POSITION_COMPAT.get(inj_pos, set())
                                if compat:
                                    candidates = [r for r in healthy if r['position'] in compat]
                                else:
                                    candidates = healthy  # no position data — show by minutes

                                top_candidates = candidates[:3]
                                if top_candidates:
                                    cand_df = pd.DataFrame([{
                                        'Player': r['player'],
                                        'Pos': r['position'],
                                        'MIN/g (szn)': r['min_avg'],
                                        'MIN/g (L5)': r['l5_min'],
                                        'PTS/g': r['pts_avg'],
                                    } for r in top_candidates])
                                    st.dataframe(cand_df, width='stretch', hide_index=True)
                                else:
                                    st.caption("No position-compatible rotation data available.")

                st.markdown("---")

        except Exception as e:
            st.error(f"❌ Error loading hot/cold data: {e}")
            import traceback
            with st.expander("Error Details"):
                st.code(traceback.format_exc())

# Section 4: Boom/Bust Analysis
st.markdown("---")
st.header("📊 Boom/Bust Analysis")

if (st.session_state.draftables_df is None or 
    len(matchups) == 0 or 
    len(existing_predictions) == 0):
    st.info("ℹ️ Fetch draftables, select games, and ensure predictions are available to view boom/bust analysis")
else:
    # Combine predictions from selected waves
    if selected_waves:
        try:
            combined_predictions_df, team_abbreviations = combine_predictions_for_waves(
                matchups, selected_waves, downloads_dir, selected_date
            )
            
            if len(combined_predictions_df) > 0:
                # Merge with draftables to get salaries
                draftables_df = st.session_state.draftables_df.copy()
                
                # Ensure normalized columns exist (required by merge_draftables_with_predictions)
                if 'displayName_normalized' not in draftables_df.columns:
                    from optimize_draftkings_nba_lineup import normalize_player_name
                    draftables_df['displayName_normalized'] = draftables_df['displayName'].apply(normalize_player_name)
                
                # Ensure predictions have normalized column
                if 'Player_normalized' not in combined_predictions_df.columns:
                    from optimize_draftkings_nba_lineup import normalize_player_name
                    combined_predictions_df['Player_normalized'] = combined_predictions_df['Player'].apply(normalize_player_name)
                
                merged_df = merge_draftables_with_predictions(draftables_df, combined_predictions_df)

                # Store merged_df for stack recommendation (Section 6.5)
                st.session_state.merged_df = merged_df.copy()

                # Filter to selected teams
                if 'Team' in merged_df.columns:
                    merged_df = merged_df[merged_df['Team'].isin(team_abbreviations)].copy()
                
                if len(merged_df) > 0:
                    # Calculate boom/bust scores
                    merged_df = calculate_boom_bust_probabilities(merged_df)
                    
                    # Create two columns for boom and bust tables
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.subheader("🚀 Boom Candidates")
                        
                        # Filter boom candidates
                        boom_df = merged_df.copy()
                        
                        # Filters
                        boom_min_salary = st.slider(
                            "Min Salary",
                            min_value=3000,
                            max_value=10000,
                            value=3000,
                            step=500,
                            key="boom_min_salary"
                        )
                        boom_max_salary = st.slider(
                            "Max Salary",
                            min_value=3000,
                            max_value=13000,
                            value=13000,
                            step=500,
                            key="boom_max_salary"
                        )
                        boom_max_score = float(boom_df['Boom_Score'].max()) if len(boom_df) > 0 and 'Boom_Score' in boom_df.columns else 10.0
                        boom_min_score = st.slider(
                            "Min Boom Score",
                            min_value=0.0,
                            max_value=boom_max_score,
                            value=0.0,
                            step=0.5,
                            key="boom_min_score"
                        )
                        
                        # Apply filters
                        if 'Boom_Score' in boom_df.columns:
                            boom_df = boom_df[
                                (boom_df['salary'] >= boom_min_salary) &
                                (boom_df['salary'] <= boom_max_salary) &
                                (boom_df['Boom_Score'] >= boom_min_score)
                            ].copy()
                            
                            # Sort by boom score descending
                            boom_df = boom_df.sort_values('Boom_Score', ascending=False)
                        else:
                            boom_df = boom_df[
                                (boom_df['salary'] >= boom_min_salary) &
                                (boom_df['salary'] <= boom_max_salary)
                            ].copy()
                        
                        # Select columns to display
                        display_cols = ['Player', 'Team', 'salary', 'FPTS', 'FPTS_Ceiling', 'Boom_Score', 'Boom_Probability']
                        available_cols = [col for col in display_cols if col in boom_df.columns]
                        boom_display = boom_df[available_cols].copy()
                        
                        # Rename columns for display
                        rename_map = {}
                        if 'salary' in boom_display.columns:
                            rename_map['salary'] = 'Salary'
                        if 'FPTS_Ceiling' in boom_display.columns:
                            rename_map['FPTS_Ceiling'] = 'Ceiling FPTS'
                        if rename_map:
                            boom_display = boom_display.rename(columns=rename_map)
                        
                        # Format numbers
                        if 'Salary' in boom_display.columns:
                            boom_display['Salary'] = boom_display['Salary'].apply(lambda x: f"${x:,.0f}")
                        if 'FPTS' in boom_display.columns:
                            boom_display['FPTS'] = boom_display['FPTS'].apply(lambda x: f"{x:.1f}")
                        if 'Ceiling FPTS' in boom_display.columns:
                            boom_display['Ceiling FPTS'] = boom_display['Ceiling FPTS'].apply(lambda x: f"{x:.1f}")
                        if 'Boom_Score' in boom_display.columns:
                            boom_display['Boom_Score'] = boom_display['Boom_Score'].apply(lambda x: f"{x:.2f}")
                        if 'Boom_Probability' in boom_display.columns:
                            boom_display['Boom_Probability'] = boom_display['Boom_Probability'].apply(lambda x: f"{x:.1f}%")
                        
                        # Highlight top boom candidates
                        if len(boom_display) > 0:
                            st.dataframe(boom_display.head(20), width='stretch', hide_index=True)
                            st.caption(f"Showing top {min(20, len(boom_display))} boom candidates")
                        else:
                            st.info("No players match the boom filters")
                    
                    with col2:
                        st.subheader("💥 Bust Candidates")
                        
                        # Filter bust candidates
                        bust_df = merged_df.copy()
                        
                        # Filters
                        bust_min_salary = st.slider(
                            "Min Salary",
                            min_value=3000,
                            max_value=10000,
                            value=3000,
                            step=500,
                            key="bust_min_salary"
                        )
                        bust_max_salary = st.slider(
                            "Max Salary",
                            min_value=3000,
                            max_value=13000,
                            value=13000,
                            step=500,
                            key="bust_max_salary"
                        )
                        bust_max_score = float(bust_df['Bust_Score'].max()) if len(bust_df) > 0 and 'Bust_Score' in bust_df.columns else 10.0
                        bust_min_score = st.slider(
                            "Min Bust Score",
                            min_value=0.0,
                            max_value=bust_max_score,
                            value=0.0,
                            step=0.5,
                            key="bust_min_score"
                        )
                        
                        # Apply filters
                        if 'Bust_Score' in bust_df.columns:
                            bust_df = bust_df[
                                (bust_df['salary'] >= bust_min_salary) &
                                (bust_df['salary'] <= bust_max_salary) &
                                (bust_df['Bust_Score'] >= bust_min_score)
                            ].copy()
                            
                            # Sort by bust score descending
                            bust_df = bust_df.sort_values('Bust_Score', ascending=False)
                        else:
                            bust_df = bust_df[
                                (bust_df['salary'] >= bust_min_salary) &
                                (bust_df['salary'] <= bust_max_salary)
                            ].copy()
                        
                        # Select columns to display
                        display_cols = ['Player', 'Team', 'salary', 'FPTS', 'FPTS_Floor', 'Bust_Score', 'Bust_Probability']
                        available_cols = [col for col in display_cols if col in bust_df.columns]
                        bust_display = bust_df[available_cols].copy()
                        
                        # Rename columns for display
                        rename_map = {}
                        if 'salary' in bust_display.columns:
                            rename_map['salary'] = 'Salary'
                        if 'FPTS_Floor' in bust_display.columns:
                            rename_map['FPTS_Floor'] = 'Floor FPTS'
                        if rename_map:
                            bust_display = bust_display.rename(columns=rename_map)
                        
                        # Format numbers
                        if 'Salary' in bust_display.columns:
                            bust_display['Salary'] = bust_display['Salary'].apply(lambda x: f"${x:,.0f}")
                        if 'FPTS' in bust_display.columns:
                            bust_display['FPTS'] = bust_display['FPTS'].apply(lambda x: f"{x:.1f}")
                        if 'Floor FPTS' in bust_display.columns:
                            bust_display['Floor FPTS'] = bust_display['Floor FPTS'].apply(lambda x: f"{x:.1f}")
                        if 'Bust_Score' in bust_display.columns:
                            bust_display['Bust_Score'] = bust_display['Bust_Score'].apply(lambda x: f"{x:.2f}")
                        if 'Bust_Probability' in bust_display.columns:
                            bust_display['Bust_Probability'] = bust_display['Bust_Probability'].apply(lambda x: f"{x:.1f}%")
                        
                        # Display bust candidates
                        if len(bust_display) > 0:
                            st.dataframe(bust_display.head(20), width='stretch', hide_index=True)
                            st.caption(f"Showing top {min(20, len(bust_display))} bust candidates")
                        else:
                            st.info("No players match the bust filters")
            else:
                st.info("ℹ️ No predictions available for selected waves")
        except Exception as e:
            st.error(f"❌ Error calculating boom/bust analysis: {e}")
            import traceback
            with st.expander("Error Details"):
                st.code(traceback.format_exc())

# Section 4.5: Top Injuries
st.markdown("---")
st.header("🏥 Top Injuries Tonight")
st.caption("Stars and key starters who are OUT or DOUBTFUL — and value players who may benefit.")

if st.session_state.draftables_df is None or len(matchups) == 0:
    st.info("ℹ️ Load draftables to see injury impact analysis.")
else:
    try:
        @st.cache_data(ttl=600, show_spinner=False)
        def _top_inj_load_players():
            return pf.get_players_dataframe()

        @st.cache_data(ttl=600, show_spinner=False)
        def _top_inj_fetch_report(date_str: str):
            pdf = _top_inj_load_players()
            return ir.fetch_injuries_for_date(date_str, pdf)

        @st.cache_data(ttl=3600, show_spinner=False)
        def _top_inj_avg_minutes():
            try:
                logs = pred_feat.get_bulk_player_game_logs()
                if logs is None or logs.empty or 'MIN' not in logs.columns:
                    return {}
                return logs.groupby('PLAYER_ID')['MIN'].mean().round(1).to_dict()
            except Exception:
                return {}

        with st.spinner("Loading injury impact data…"):
            top_inj_df, _ = _top_inj_fetch_report(game_date_str)
            avg_min_map    = _top_inj_avg_minutes()
            top_inj_pdf    = _top_inj_load_players()

        if top_inj_df is None or len(top_inj_df) == 0:
            st.info("No injury report available. Try refreshing the Injury Report tab.")
        else:
            # Collect injuries from every selected matchup, tagging with abbreviation + team_id
            IMPACTFUL_STATUSES = {'out', 'doubtful'}
            all_tonight_injuries = []
            for _m in selected_matchups:
                _away, _home = _m['away_team'], _m['home_team']
                _away_id, _home_id = _m.get('away_team_id', ''), _m.get('home_team_id', '')
                _minj = ir.get_injuries_for_matchup(top_inj_df, _away, _home, top_inj_pdf)
                for _inj in _minj.get('away', []):
                    all_tonight_injuries.append({**_inj, 'team_abbr': _away, 'team_id': _away_id})
                for _inj in _minj.get('home', []):
                    all_tonight_injuries.append({**_inj, 'team_abbr': _home, 'team_id': _home_id})

            # Filter to OUT/DOUBTFUL and attach MPG; keep only ≥22 MPG players
            key_injured = []
            for _inj in all_tonight_injuries:
                _status = (_inj.get('status', '') or '').lower().strip()
                if not any(s in _status for s in IMPACTFUL_STATUSES):
                    continue
                _pid = _inj.get('player_id')
                _mpg = avg_min_map.get(int(_pid), 0.0) if _pid and str(_pid).isdigit() else 0.0
                if _mpg >= 22:
                    key_injured.append({**_inj, 'avg_mpg': round(_mpg, 1)})

            key_injured.sort(key=lambda x: -x['avg_mpg'])

            if not key_injured:
                st.success("✅ No stars or starters are OUT or DOUBTFUL tonight.")
            else:
                def _role_badge(mpg):
                    if mpg >= 32: return "⭐ Star"
                    if mpg >= 26: return "🔑 Starter"
                    return "🔄 Rotation"

                def _status_color(status):
                    return tc.injury_out if 'out' in (status or '').lower() else tc.injury_doubtful

                def _value_beneficiaries(team_abbr, min_sal=3000, max_sal=4500):
                    """Return top value DK plays on the same team from merged_df."""
                    src = st.session_state.merged_df
                    if src is None or 'Team' not in src.columns:
                        return []
                    # Exclude players who are currently OUT
                    _out_names = {
                        ir.format_player_name(_i.get('player_name', '')).lower()
                        for _i in all_tonight_injuries
                        if 'out' in (_i.get('status', '') or '').lower()
                    }
                    team_df = src[
                        (src['Team'] == team_abbr) &
                        (src['salary'] >= min_sal) &
                        (src['salary'] <= max_sal)
                    ].copy()
                    _name_col = 'Player' if 'Player' in team_df.columns else 'displayName'
                    team_df = team_df[~team_df[_name_col].str.lower().isin(_out_names)]
                    sort_col = 'FPTS' if 'FPTS' in team_df.columns else 'salary'
                    team_df = team_df.sort_values(sort_col, ascending=False).head(4)
                    results = []
                    for _, vr in team_df.iterrows():
                        results.append({
                            'name': vr.get('Player', vr.get('displayName', '')),
                            'pos':  vr.get('position', ''),
                            'sal':  int(vr.get('salary', 0)),
                            'fpts': vr.get('FPTS', None),
                        })
                    return results

                has_predictions = st.session_state.merged_df is not None

                for _inj in key_injured:
                    _pname   = ir.format_player_name(_inj.get('player_name', ''))
                    _pid     = _inj.get('player_id', '')
                    _status  = _inj.get('status', '')
                    _reason  = ir.format_injury_reason(_inj.get('reason', ''))
                    _team    = _inj.get('team_abbr', '')
                    _team_id = _inj.get('team_id', '')
                    _mpg     = _inj['avg_mpg']
                    _role    = _role_badge(_mpg)
                    _color   = _status_color(_status)
                    _head    = f"https://cdn.nba.com/headshots/nba/latest/1040x760/{_pid}.png" if _pid else ""
                    _logo    = f"https://cdn.nba.com/logos/nba/{_team_id}/primary/L/logo.svg" if _team_id else ""

                    _mid_vals  = _value_beneficiaries(_team, min_sal=4500, max_sal=6000)
                    _vals      = _value_beneficiaries(_team, min_sal=3000, max_sal=4500)

                    def _build_chips(players, bg, border, text_color):
                        return ''.join(
                            f'<span style="display:inline-flex;align-items:center;gap:4px;'
                            f'background:{bg};border:1px solid {border};border-radius:4px;'
                            f'padding:3px 8px;margin:2px;font-size:12px;">'
                            f'<strong>{v["name"]}</strong>&nbsp;{v["pos"]}&nbsp;'
                            f'<span style="color:{text_color};">&#36;{v["sal"]:,}'
                            f'{"" if v["fpts"] is None else " · {:.1f} FPTS".format(v["fpts"])}'
                            f'</span></span>'
                            for v in players
                        )

                    # Build mid-range chips HTML ($4.5k–$6k, yellow)
                    if _mid_vals:
                        _mid_html = (
                            f'<div style="margin-top:8px;">'
                            f'<span style="font-size:11px;color:#555;font-weight:600;">'
                            f'⬆️ Mid-Range Beneficiaries (&#36;4.5k–&#36;6k)</span><br>'
                            f'{_build_chips(_mid_vals, tc.warn_bg, tc.warn_text, tc.warn_text)}</div>'
                        )
                    else:
                        _mid_html = ''

                    # Build value chips HTML ($3k–$4.5k, green)
                    if _vals:
                        _val_html = (
                            f'<div style="margin-top:8px;">'
                            f'<span style="font-size:11px;color:#555;font-weight:600;">'
                            f'💰 Value Beneficiaries (&#36;3k–&#36;4.5k)</span><br>'
                            f'{_build_chips(_vals, tc.green_bg, tc.green_text, tc.green_text)}</div>'
                        )
                    elif not has_predictions:
                        _val_html = (
                            '<div style="margin-top:6px;font-size:11px;color:#888;">'
                            'Load predictions to see value beneficiaries.</div>'
                        )
                    else:
                        _val_html = (
                            '<div style="margin-top:6px;font-size:11px;color:#888;">'
                            'No &#36;3k–&#36;4.5k teammates on this slate.</div>'
                        )

                    _reason_part = (
                        f'<div style="font-size:12px;color:#888;margin-top:2px;">{_reason}</div>'
                        if _reason else ''
                    )
                    _logo_part = (
                        f'<img src="{_logo}" style="height:24px;vertical-align:middle;'
                        f'margin-left:4px;" onerror="this.style.display=\'none\'">'
                        if _logo else ''
                    )

                    _card_html = (
                        f'<div style="border:1px solid {tc.card_border};border-radius:10px;'
                        f'padding:14px;margin-bottom:10px;background:{tc.card_bg};'
                        f'border-left:4px solid {_color};">'
                        f'<div style="display:flex;align-items:center;gap:14px;">'
                        f'<img src="{_head}" style="width:140px;height:105px;object-fit:cover;'
                        f'border-radius:8px;background:{tc.neutral_bg};flex-shrink:0;"'
                        f' onerror="this.style.display=\'none\'">'
                        f'<div style="flex:1;min-width:0;">'
                        f'<div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">'
                        f'<strong style="font-size:15px;">{_pname}</strong>'
                        f'<span style="background:{_color};color:white;padding:2px 8px;'
                        f'border-radius:4px;font-size:12px;font-weight:600;">{_status}</span>'
                        f'<span style="background:{tc.img_placeholder};color:{tc.text_primary};padding:2px 8px;'
                        f'border-radius:4px;font-size:12px;">{_role} · {_mpg:.0f} MPG</span>'
                        f'{_logo_part}'
                        f'</div>'
                        f'{_reason_part}'
                        f'{_mid_html}'
                        f'{_val_html}'
                        f'</div>'
                        f'</div>'
                        f'</div>'
                    )
                    st.markdown(_card_html, unsafe_allow_html=True)

    except Exception as _e:
        st.warning(f"Could not load Top Injuries section: {_e}")

# Section 5: Lock Players
st.markdown("---")
st.header("🔒 Lock Players")

locked_player_names = []
optimization_blocked = False

if st.session_state.draftables_df is not None:
    df_lock = st.session_state.draftables_df
    player_options = [
        f"{row['displayName']} ({row['position']}, ${int(row['salary']):,})"
        for _, row in df_lock.sort_values('salary', ascending=False).iterrows()
    ]

    locked_selections = st.multiselect(
        "Select players to lock into every lineup (max 5):",
        options=player_options,
        max_selections=5,
        help="These players will be included in all optimized lineups. Salary validation enforced."
    )

    locked_player_names = [s.split(' (')[0] for s in locked_selections]

    if locked_player_names:
        locked_salary = df_lock[df_lock['displayName'].isin(locked_player_names)]['salary'].sum()
        remaining_budget = max_salary - locked_salary
        remaining_slots = 8 - len(locked_player_names)
        min_needed = remaining_slots * 3500

        col1, col2, col3 = st.columns(3)
        col1.metric("Locked Salary", f"${int(locked_salary):,}")
        col2.metric("Remaining Budget", f"${int(remaining_budget):,}")
        col3.metric("Min Needed for Remaining", f"${int(min_needed):,}")

        if remaining_budget < min_needed:
            st.error(
                f"Not enough budget remaining. Locked players use ${int(locked_salary):,}, "
                f"leaving ${int(remaining_budget):,} for {remaining_slots} spots — "
                f"need at least ${int(min_needed):,} (${3500:,}/player avg minimum)."
            )
            optimization_blocked = True
        else:
            st.success(f"{len(locked_player_names)} player(s) locked. Budget check passed.")
else:
    st.info("ℹ️ Load draftables above to enable player locking.")

# Section 6: Exclude Players
st.markdown("---")
st.header("🚫 Exclude Players")

excluded_player_names = []

if st.session_state.draftables_df is not None:
    df_excl = st.session_state.draftables_df
    excl_options = [
        f"{row['displayName']} ({row['position']}, ${int(row['salary']):,})"
        for _, row in df_excl.sort_values('salary', ascending=False).iterrows()
    ]

    excluded_selections = st.multiselect(
        "Select players to exclude from all lineups:",
        options=excl_options,
        help="These players will never appear in any optimized lineup."
    )

    excluded_player_names = [s.split(' (')[0] for s in excluded_selections]

    if excluded_player_names:
        st.success(f"{len(excluded_player_names)} player(s) excluded from optimization.")
else:
    st.info("ℹ️ Load draftables above to enable player exclusion.")

# Section 6.5: Stack Settings
st.markdown("---")
st.header("📌 Stack Settings")

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_team_def_ratings():
    """Returns {team_abbr: def_rtg} from LeagueDashTeamStats Advanced."""
    try:
        from nba_api.stats.endpoints import LeagueDashTeamStats
        from nba_api.stats.library.http import NBAStatsHTTP as NBAHTTP
        df = LeagueDashTeamStats(
            measure_type_detailed_defense='Advanced',
            season='2025-26',
            per_mode_simple='PerGame',
            timeout=90,
        ).get_data_frames()[0]
        return {row['TEAM_ABBREVIATION']: float(row['DEF_RATING']) for _, row in df.iterrows()}
    except Exception:
        return {}


@st.cache_data(ttl=21600, show_spinner=False)
def fetch_pbpstats_opp_zones():
    """Returns {team_abbr: {AtRimAccuracy, Arc3Accuracy}} — what each team *allows*."""
    import requests as _req
    try:
        from nba_api.stats.static import teams as _nba_teams
        id_to_abbr = {str(t['id']): t['abbreviation'] for t in _nba_teams.get_teams()}
        resp = _req.get(
            'https://api.pbpstats.com/get-totals/nba',
            params={'Season': '2025-26', 'SeasonType': 'Regular Season', 'Type': 'Opponent'},
            timeout=15,
        )
        rows = resp.json().get('multi_row_table_data', [])
        result = {}
        for row in rows:
            abbr = id_to_abbr.get(str(row.get('TeamId', '')), '')
            if abbr:
                result[abbr] = {
                    'AtRimAccuracy': float(row.get('AtRimAccuracy', 0.60)),
                    'Arc3Accuracy':  float(row.get('Arc3Accuracy', 0.36)),
                }
        return result
    except Exception:
        return {}


def compute_team_stack_scores(merged_df, team_fpts_scalars, contest_type,
                               team_to_opponent=None, opp_def_ratings=None, opp_zone_stats=None):
    """Compute composite stack score per team. Returns list of dicts sorted by score desc."""
    if merged_df is None or len(merged_df) == 0:
        return []

    # GPP: ceiling + implied matter most; Cash: proj FPTS + efficiency matter most
    # Both now include opponent defensive signals (defrtg + zone vulnerability)
    if contest_type == 'cash':
        weights = {
            'implied': 0.20, 'fpts_proj': 0.22, 'ceiling': 0.05,
            'efficiency': 0.18, 'depth': 0.08,
            'opp_def_rtg': 0.13, 'opp_zone_vuln': 0.14,
        }
    else:
        weights = {
            'implied': 0.25, 'fpts_proj': 0.15, 'ceiling': 0.25,
            'efficiency': 0.05, 'depth': 0.05,
            'opp_def_rtg': 0.12, 'opp_zone_vuln': 0.13,
        }

    LEAGUE_AVG = 113.0
    team_groups = []
    for team, grp in merged_df.groupby('Team'):
        eligible = grp[grp['FPTS'] > 0] if 'FPTS' in grp.columns else grp
        if len(eligible) < 2:
            continue
        sum_fpts = eligible['FPTS'].sum() if 'FPTS' in eligible.columns else 0.0
        sum_ceil = eligible['FPTS_Ceiling'].sum() if 'FPTS_Ceiling' in eligible.columns else sum_fpts
        sum_sal  = eligible['salary'].sum() if 'salary' in eligible.columns else 1
        depth    = int((eligible['FPTS'] >= 20).sum()) if 'FPTS' in eligible.columns else 0
        implied  = team_fpts_scalars.get(team, 1.0) * LEAGUE_AVG

        opp = (team_to_opponent or {}).get(team, '')
        opp_dr = (opp_def_ratings or {}).get(opp)
        opp_z  = (opp_zone_stats or {}).get(opp, {})

        team_groups.append({
            'team': team, 'sum_fpts': sum_fpts, 'sum_ceil': sum_ceil,
            'sum_sal': sum_sal, 'depth': depth, 'implied': implied,
            'opp': opp,
            'opp_defrtg':  opp_dr,
            'opp_atrim':   opp_z.get('AtRimAccuracy'),
            'opp_arc3':    opp_z.get('Arc3Accuracy'),
        })

    if not team_groups:
        return []

    # --- Normalize offensive sub-scores ---
    max_fpts  = max(t['sum_fpts'] for t in team_groups) or 1
    max_ceil  = max(t['sum_ceil'] for t in team_groups) or 1
    max_depth = max(t['depth'] for t in team_groups) or 1
    max_impl  = max(t['implied'] for t in team_groups) or 1
    max_eff   = max(t['sum_fpts'] / (t['sum_sal'] / 1000) for t in team_groups if t['sum_sal'] > 0) or 1

    # --- Normalize defensive sub-scores across slate opponents ---
    _drs    = [t['opp_defrtg'] for t in team_groups if t['opp_defrtg'] is not None]
    _atrims = [t['opp_atrim']  for t in team_groups if t['opp_atrim']  is not None]
    _arc3s  = [t['opp_arc3']   for t in team_groups if t['opp_arc3']   is not None]

    dr_min, dr_max     = (min(_drs),    max(_drs))    if len(_drs) > 1    else (None, None)
    atrim_min, atrim_max = (min(_atrims), max(_atrims)) if len(_atrims) > 1 else (None, None)
    arc3_min, arc3_max   = (min(_arc3s),  max(_arc3s))  if len(_arc3s) > 1  else (None, None)

    def _norm(val, lo, hi):
        """Normalize val in [lo, hi] → [0, 1]. Returns 0.5 if range is zero or val is None."""
        if val is None or lo is None or hi == lo:
            return 0.5
        return (val - lo) / (hi - lo)

    results = []
    for t in team_groups:
        eff = t['sum_fpts'] / (t['sum_sal'] / 1000) if t['sum_sal'] > 0 else 0

        # Higher opponent DefRtg = softer defense = better for offense
        opp_def_sub = _norm(t['opp_defrtg'], dr_min, dr_max)

        # Higher AtRimAccuracy + Arc3Accuracy *allowed* = worse defense = better for us
        atrim_sub = _norm(t['opp_atrim'], atrim_min, atrim_max)
        arc3_sub  = _norm(t['opp_arc3'],  arc3_min,  arc3_max)
        zone_sub  = 0.6 * atrim_sub + 0.4 * arc3_sub

        sub = {
            'implied':      t['implied'] / max_impl,
            'fpts_proj':    t['sum_fpts'] / max_fpts,
            'ceiling':      t['sum_ceil'] / max_ceil,
            'efficiency':   eff / max_eff,
            'depth':        t['depth'] / max_depth,
            'opp_def_rtg':  opp_def_sub,
            'opp_zone_vuln': zone_sub,
        }
        score = sum(weights[k] * v for k, v in sub.items()) * 100
        results.append({
            'team':       t['team'],
            'score':      round(score, 1),
            'implied':    round(t['implied'], 1),
            'proj_fpts':  round(t['sum_fpts'], 1),
            'ceiling':    round(t['sum_ceil'], 1),
            'depth':      t['depth'],
            'opp':        t['opp'],
            'opp_defrtg': round(t['opp_defrtg'], 1) if t['opp_defrtg'] is not None else None,
            'opp_atrim':  round(t['opp_atrim'] * 100, 1) if t['opp_atrim'] is not None else None,
            'opp_arc3':   round(t['opp_arc3'] * 100, 1) if t['opp_arc3'] is not None else None,
        })

    results.sort(key=lambda x: -x['score'])
    return results


all_game_teams = sorted(
    {m['away_team'] for m in matchups} | {m['home_team'] for m in matchups}
)

# Build opponent lookup from slate matchups
_team_to_opponent = {}
for _m in matchups:
    _team_to_opponent[_m['away_team']] = _m['home_team']
    _team_to_opponent[_m['home_team']] = _m['away_team']

if not all_game_teams:
    st.info("ℹ️ Load draftables and select a date with games to configure stacking.")
else:
    # --- AI Recommendation ---
    merged_for_stack = st.session_state.get('merged_df')

    if merged_for_stack is None or len(merged_for_stack) == 0:
        st.info("ℹ️ Generate predictions first to enable AI team recommendation")
    else:
        if st.button("🔍 Analyze Teams", type="secondary"):
            with st.spinner("Fetching defensive data…"):
                _def_ratings  = fetch_team_def_ratings()
                _zone_stats   = fetch_pbpstats_opp_zones()
            rec = compute_team_stack_scores(
                merged_for_stack, team_fpts_scalars, contest_type_key,
                team_to_opponent=_team_to_opponent,
                opp_def_ratings=_def_ratings,
                opp_zone_stats=_zone_stats,
            )
            st.session_state.stack_recommendation = rec
            st.session_state.stack_llm_reason = None  # reset LLM reason on re-analyze

    rec = st.session_state.get('stack_recommendation')
    if rec:
        top = rec[0]
        _opp_line = ''
        if top.get('opp'):
            _parts = [f"vs {top['opp']}"]
            if top.get('opp_defrtg') is not None:
                _parts.append(f"DefRtg {top['opp_defrtg']}")
            if top.get('opp_atrim') is not None:
                _parts.append(f"AtRim allowed {top['opp_atrim']}%")
            if top.get('opp_arc3') is not None:
                _parts.append(f"Arc3 allowed {top['opp_arc3']}%")
            _opp_line = ' &nbsp;|&nbsp; '.join(_parts)
        st.markdown(
            f"""<div style="border:2px solid #FF4B4B; border-radius:8px; padding:12px; margin-bottom:8px;">
<b>⭐ {top['team']} &nbsp; Score: {top['score']:.0f}/100</b><br>
Implied: {top['implied']} &nbsp;|&nbsp; Proj FPTS: {top['proj_fpts']} &nbsp;|&nbsp; Ceiling: {top['ceiling']} &nbsp;|&nbsp; Depth: {top['depth']} options<br>
<span style="font-size:0.9em; color:#888;">{_opp_line}</span>
</div>""",
            unsafe_allow_html=True,
        )
        if len(rec) > 1:
            others = ', '.join(f"{r['team']} ({r['score']:.0f})" for r in rec[1:3])
            st.caption(f"Also consider: {others}")

        # LLM expander (only if ANTHROPIC_API_KEY is set)
        anthropic_key = os.environ.get('ANTHROPIC_API_KEY', '')
        if anthropic_key:
            with st.expander("▶ Ask Claude why"):
                cached_reason = st.session_state.get('stack_llm_reason')
                if cached_reason:
                    st.info(cached_reason)
                else:
                    if st.button("Ask Claude", key="ask_claude_stack"):
                        try:
                            import anthropic as _anthropic_sdk
                            table_lines = []
                            for r in rec[:6]:
                                line = (
                                    f"{r['team']}: score={r['score']:.0f}, implied={r['implied']}, "
                                    f"proj_fpts={r['proj_fpts']:.0f}, ceiling={r['ceiling']:.0f}, depth={r['depth']}"
                                )
                                if r.get('opp'):
                                    line += f", opp={r['opp']}"
                                if r.get('opp_defrtg') is not None:
                                    line += f", opp_defrtg={r['opp_defrtg']}"
                                if r.get('opp_atrim') is not None:
                                    line += f", opp_atrim_allowed={r['opp_atrim']}%"
                                if r.get('opp_arc3') is not None:
                                    line += f", opp_arc3_allowed={r['opp_arc3']}%"
                                table_lines.append(line)
                            prompt = (
                                f"Slate: {game_date_str}, Contest: {contest_type_key}\n"
                                f"Teams ranked by stack score (includes opponent defensive rating and zone vulnerability):\n"
                                + "\n".join(table_lines) + "\n"
                                f"Recommend the top team to stack in DraftKings NBA {contest_type_key}. "
                                f"2-3 sentences max. Be specific about why this team over others, "
                                f"referencing matchup quality where relevant."
                            )
                            client = _anthropic_sdk.Anthropic(api_key=anthropic_key)
                            msg = client.messages.create(
                                model='claude-haiku-4-5-20251001',
                                max_tokens=150,
                                messages=[{'role': 'user', 'content': prompt}],
                            )
                            reason = msg.content[0].text
                            st.session_state.stack_llm_reason = reason
                            st.info(reason)
                        except Exception as _e:
                            st.error(f"Claude API error: {_e}")

    # --- Override selectbox (defaults to recommended team) ---
    rec_team = rec[0]['team'] if rec else None
    stack_team_options = ['None'] + all_game_teams
    default_idx = 0
    if rec_team and rec_team in stack_team_options:
        default_idx = stack_team_options.index(rec_team)

    stack_team_option = st.selectbox(
        "Stack Team (optional)",
        options=stack_team_options,
        index=default_idx,
        help="Defaults to AI-recommended team when predictions are loaded. Override freely.",
    )
    if stack_team_option != 'None':
        stack_team = stack_team_option
        stack_count = st.slider("Players to stack", min_value=2, max_value=4, value=2)
        st.caption(f"All lineups will include at least {stack_count} players from {stack_team}.")
    else:
        stack_team = None
        stack_count = 2

# Section 7: Optimization
st.markdown("---")
st.header("⚡ Lineup Optimization")

if (st.session_state.draftables_df is None or
    len(matchups) == 0 or
    len(existing_predictions) == 0 or
    not selected_waves):
    st.info("ℹ️ Please ensure draftables are loaded, games are selected, predictions are available, and at least one wave is selected")
elif optimization_blocked:
    st.warning("Resolve the locked player salary issue above before optimizing.")
else:
    if st.button("🚀 Optimize Lineups", type="primary", width='stretch'):
        if not selected_waves:
            st.error("❌ Please select at least one tip-off wave")
        else:
            try:
                # Prepare draftables path (save to temp location for optimizer)
                draftables_path = os.path.join(downloads_dir, f"draftkings_draftables_{st.session_state.draftgroup_id}.csv")
                
                # Save draftables if not already saved
                if not os.path.exists(draftables_path):
                    try:
                        st.session_state.draftables_df.to_csv(draftables_path, index=False)
                    except Exception as e:
                        st.error(f"❌ Failed to save draftables file: {e}")
                        st.stop()
                
                # Validate draftables file exists
                if not os.path.exists(draftables_path):
                    st.error(f"❌ Draftables file not found: {draftables_path}")
                    st.stop()
                
                # Optimize combined waves (all selected waves together)
                with st.spinner("Optimizing 5 unique lineups using players from all selected waves..."):
                    try:
                        # Use combined wave optimization
                        optimized_lineups = optimize_combined_waves(
                            selected_date,
                            draftables_path,
                            selected_wave_times=selected_waves,
                            predictions_dir=downloads_dir,
                            output_dir=downloads_dir,
                            max_salary=max_salary,
                            locked_players=locked_player_names if locked_player_names else None,
                            excluded_players=excluded_player_names if excluded_player_names else None,
                            team_fpts_scalars=team_fpts_scalars if team_fpts_scalars else None,
                            contest_type=contest_type_key,
                            stack_team=stack_team,
                            stack_count=stack_count,
                        )

                        if len(optimized_lineups) > 0:
                            # Store results with strategy names (order matches contest type)
                            if contest_type_key == 'cash':
                                strategy_names = ['Max FPTS', 'Balanced', 'Max Value', 'Max FPTS (safe)', 'Balanced (safe)']
                            else:
                                strategy_names = ['Max Ceiling', 'Punt Strategy', 'Balanced', 'Max FPTS', 'Max Value']
                            st.session_state.optimized_lineups = {}
                            for idx, lineup_df in enumerate(optimized_lineups):
                                strategy_name = strategy_names[idx] if idx < len(strategy_names) else f"Lineup {idx + 1}"
                                st.session_state.optimized_lineups[strategy_name] = {
                                    'dataframe': lineup_df,
                                    'file_path': None  # Generated in memory
                                }
                            
                            st.success(f"✅ Successfully optimized {len(optimized_lineups)} unique lineup(s) using players from {len(selected_waves)} wave(s)")
                            st.rerun()
                        else:
                            st.error("❌ No optimized lineups generated. Check console for errors.")
                    except ValueError as e:
                        error_msg = str(e)
                        if "infeasible" in error_msg.lower() or "no feasible solution" in error_msg.lower():
                            st.error("❌ No feasible lineup found. Check salary cap and position constraints.")
                        else:
                            st.error(f"❌ Optimization error: {error_msg}")
                    except Exception as e:
                        st.error(f"❌ Unexpected error during optimization: {e}")
                        import traceback
                        with st.expander("Error Details"):
                            st.code(traceback.format_exc())
            except Exception as e:
                st.error(f"❌ Unexpected error during optimization: {e}")
                import traceback
                with st.expander("Error Details"):
                    st.code(traceback.format_exc())

# Section 8: Results Display
if len(st.session_state.optimized_lineups) > 0:
    st.markdown("---")
    st.header("📈 Optimized Lineups")
    
    # Create tabs for each lineup strategy
    lineup_keys = list(st.session_state.optimized_lineups.keys())
    strategy_tabs = st.tabs(lineup_keys)
    
    for tab_idx, (strategy_name, result) in enumerate(st.session_state.optimized_lineups.items()):
        with strategy_tabs[tab_idx]:
            lineup_df = result['dataframe']
            
            # Strategy descriptions
            strategy_descriptions = {
                'Max FPTS': 'Maximizes total fantasy points (FPTS) without considering salary efficiency.',
                'Max Value': 'Maximizes FPTS per dollar spent, prioritizing players with the best value.',
                'Max Ceiling': 'Maximizes ceiling FPTS potential, targeting players with high upside.',
                'Balanced': 'Balanced approach combining FPTS (60%) and value (40%) for a well-rounded lineup.',
                'Punt Strategy': 'Uses 3+ high-salary stars (≥$8K), 4+ low-salary punts (<$5K), and ≤1 mid-tier player for maximum ceiling upside.',
                'Max FPTS (safe)': 'Maximizes total FPTS with exposure constraints to ensure lineup variety — ideal for cash game diversification.',
                'Balanced (safe)': 'Balanced FPTS/value strategy with exposure constraints for consistent cash game floors.',
            }
            
            # Display strategy description
            description = strategy_descriptions.get(strategy_name, 'Optimized lineup using selected strategy.')
            st.info(f"💡 **Strategy:** {description}")
            
            # Calculate totals
            if 'Salary' in lineup_df.columns and 'FPTS' in lineup_df.columns:
                # Exclude totals row for calculation
                player_rows = lineup_df[lineup_df['Player'] != 'TOTAL']
                total_salary = player_rows['Salary'].sum()
                total_fpts = player_rows['FPTS'].sum()
                salary_remaining = max_salary - total_salary
                total_ceiling = player_rows['FPTS_Ceiling'].sum() if 'FPTS_Ceiling' in player_rows.columns else None
                total_floor = player_rows['FPTS_Floor'].sum() if 'FPTS_Floor' in player_rows.columns else None

                # Display metrics
                col1, col2, col3, col4, col5 = st.columns(5)
                with col1:
                    st.metric("Total Salary", f"${total_salary:,}")
                with col2:
                    st.metric("Salary Remaining", f"${salary_remaining:,}")
                with col3:
                    st.metric("Total FPTS", f"{total_fpts:.2f}")
                with col4:
                    st.metric("Total High FPTS", f"{total_ceiling:.2f}" if total_ceiling is not None else "—")
                with col5:
                    st.metric("Total Low FPTS", f"{total_floor:.2f}" if total_floor is not None else "—")
            
            # Display lineup table
            st.markdown(f"### {strategy_name} Lineup")
            
            # Format display dataframe (exclude totals row for display, show separately)
            display_df = lineup_df[lineup_df['Player'] != 'TOTAL'].copy()
            
            # Reorder columns to show Slot, Player, Position, Team, Tip_Time, Opponent, Salary, FPTS
            column_order = ['Slot', 'Player', 'Position', 'Team']
            if 'Tip_Time' in display_df.columns:
                column_order.append('Tip_Time')
            if 'Opponent' in display_df.columns:
                column_order.append('Opponent')
            column_order.extend(['Salary', 'FPTS'])
            if 'FPTS_Ceiling' in display_df.columns:
                column_order.append('FPTS_Ceiling')
            if 'FPTS_Floor' in display_df.columns:
                column_order.append('FPTS_Floor')

            # Only include columns that exist
            display_cols = [col for col in column_order if col in display_df.columns]
            display_df = display_df[display_cols]

            # Format numbers
            if 'Salary' in display_df.columns:
                display_df['Salary'] = display_df['Salary'].apply(lambda x: f"${x:,.0f}" if pd.notna(x) else "$0")
            if 'FPTS' in display_df.columns:
                display_df['FPTS'] = display_df['FPTS'].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "0.00")
            if 'FPTS_Ceiling' in display_df.columns:
                display_df['FPTS_Ceiling'] = display_df['FPTS_Ceiling'].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "—")
            if 'FPTS_Floor' in display_df.columns:
                display_df['FPTS_Floor'] = display_df['FPTS_Floor'].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "—")
            display_df = display_df.rename(columns={'FPTS_Ceiling': 'High FPTS', 'FPTS_Floor': 'Low FPTS'})
            
            st.dataframe(display_df, width='stretch', hide_index=True)
            
            # Download button
            csv_data = lineup_df.to_csv(index=False)
            strategy_safe = strategy_name.replace(' ', '_').replace('/', '_')
            st.download_button(
                label=f"📥 Download {strategy_name} Lineup CSV",
                data=csv_data,
                file_name=f"optimized_lineup_{strategy_safe}_{selected_date.strftime('%Y%m%d')}.csv",
                mime="text/csv",
                key=f"download_{strategy_safe}_{tab_idx}"
            )
