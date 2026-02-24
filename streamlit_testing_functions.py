import nba_api.stats.endpoints
import requests
import json
import pandas as pd
import nba_api
import streamlit as st

# ---- NBA API Header Fix (Python 3.13 TLS compatibility) ----
# Must be set before any API calls are made
from nba_api.library.http import NBAHTTP
NBAHTTP.headers = {
    "Host": "stats.nba.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "Connection": "keep-alive",
}
# ------------------------------------------------------------

current_season = '2025-26'
season_type = 'Regular Season'

nba_logo = 'https://a.espncdn.com/combiner/i?img=/i/teamlogos/leagues/500/nba.png?w=100&h=100&transparent=true'

# Default team IDs (will be overridden by UI selection)
home_id = None
away_id = None
home_logo_link = None
away_logo_link = None
game_title = "Select a matchup"

# ============================================================
# CACHED DATA LOADING FUNCTIONS
# All NBA API calls are wrapped here so they only run once
# per session (or once per TTL period), not on every page load.
# ============================================================

@st.cache_data(ttl=3600, show_spinner=False)
def load_adv_season():
    df = nba_api.stats.endpoints.LeagueDashTeamStats(
        league_id_nullable='00',
        measure_type_detailed_defense='Advanced',
        pace_adjust='N',
        per_mode_detailed='PerGame',
        season=current_season,
        season_type_all_star=season_type
    ).get_data_frames()[0]
    df['OFF_RATING_RANK'] = df['OFF_RATING'].rank(ascending=False, method='first').astype(int)
    df['DEF_RATING_RANK'] = df['DEF_RATING'].rank(ascending=True, method='first').astype(int)
    df['NET_RATING_RANK'] = df['NET_RATING'].rank(ascending=False, method='first').astype(int)
    df['PACE_RANK'] = df['PACE'].rank(ascending=False, method='first').astype(int)
    df['AST_PCT_RANK'] = df['AST_PCT'].rank(ascending=False, method='first').astype(int)
    df['TM_TOV_PCT_RANK'] = df['TM_TOV_PCT'].rank(ascending=True, method='first').astype(int)
    df['AST_TO_RANK'] = df['AST_TO'].rank(ascending=False, method='first').astype(int)
    df['DREB_PCT_RANK'] = df['DREB_PCT'].rank(ascending=False, method='first').astype(int)
    df['OREB_PCT_RANK'] = df['OREB_PCT'].rank(ascending=False, method='first').astype(int)
    df['REB_PCT_RANK'] = df['REB_PCT'].rank(ascending=False, method='first').astype(int)
    return df

@st.cache_data(ttl=3600, show_spinner=False)
def load_adv_L5():
    return nba_api.stats.endpoints.LeagueDashTeamStats(
        league_id_nullable='00',
        measure_type_detailed_defense='Advanced',
        pace_adjust='N',
        per_mode_detailed='PerGame',
        season=current_season,
        season_type_all_star=season_type,
        last_n_games=5
    ).get_data_frames()[0]

@st.cache_data(ttl=3600, show_spinner=False)
def load_misc_season():
    df = nba_api.stats.endpoints.LeagueDashTeamStats(
        league_id_nullable='00',
        measure_type_detailed_defense='Misc',
        pace_adjust='N',
        per_mode_detailed='PerGame',
        season=current_season,
        season_type_all_star=season_type
    ).get_data_frames()[0]
    df['PTS_PAINT_DIFF'] = df['PTS_PAINT'] - df['OPP_PTS_PAINT']
    df['PTS_PAINT_DIFF_RANK'] = df['PTS_PAINT_DIFF'].rank(ascending=False, method='first')
    df['PTS_2ND_CHANCE_DIFF'] = df['PTS_2ND_CHANCE'] - df['OPP_PTS_2ND_CHANCE']
    df['PTS_2ND_CHANCE_DIFF_RANK'] = df['PTS_2ND_CHANCE_DIFF'].rank(ascending=False, method='first')
    df['PTS_FB_DIFF'] = df['PTS_FB'] - df['OPP_PTS_FB']
    df['PTS_FB_DIFF_RANK'] = df['PTS_FB_DIFF'].rank(ascending=False, method='first')
    df['PTS_OFF_TOV_DIFF'] = df['PTS_OFF_TOV'] - df['OPP_PTS_OFF_TOV']
    df['PTS_OFF_TOV_DIFF_RANK'] = df['PTS_OFF_TOV_DIFF'].rank(ascending=False, method='first')
    df['PTS_PAINT_RANK'] = df['PTS_PAINT'].rank(ascending=False, method='first').astype(int)
    df['OPP_PTS_PAINT_RANK'] = df['OPP_PTS_PAINT'].rank(ascending=True, method='first').astype(int)
    df['PTS_2ND_CHANCE_RANK'] = df['PTS_2ND_CHANCE'].rank(ascending=False, method='first').astype(int)
    df['OPP_PTS_2ND_CHANCE_RANK'] = df['OPP_PTS_2ND_CHANCE'].rank(ascending=True, method='first').astype(int)
    df['PTS_FB_RANK'] = df['PTS_FB'].rank(ascending=False, method='first').astype(int)
    df['OPP_PTS_FB_RANK'] = df['OPP_PTS_FB'].rank(ascending=True, method='first').astype(int)
    df['PTS_OFF_TOV_RANK'] = df['PTS_OFF_TOV'].rank(ascending=False, method='first').astype(int)
    df['OPP_PTS_OFF_TOV_RANK'] = df['OPP_PTS_OFF_TOV'].rank(ascending=True, method='first').astype(int)
    return df

@st.cache_data(ttl=3600, show_spinner=False)
def load_misc_L5():
    df = nba_api.stats.endpoints.LeagueDashTeamStats(
        league_id_nullable='00',
        measure_type_detailed_defense='Misc',
        pace_adjust='N',
        per_mode_detailed='PerGame',
        season=current_season,
        season_type_all_star=season_type,
        last_n_games=5
    ).get_data_frames()[0]
    df['PTS_PAINT_DIFF'] = df['PTS_PAINT'] - df['OPP_PTS_PAINT']
    df['PTS_PAINT_DIFF_RANK'] = df['PTS_PAINT_DIFF'].rank(ascending=False, method='first')
    df['PTS_2ND_CHANCE_DIFF'] = df['PTS_2ND_CHANCE'] - df['OPP_PTS_2ND_CHANCE']
    df['PTS_2ND_CHANCE_DIFF_RANK'] = df['PTS_2ND_CHANCE_DIFF'].rank(ascending=False, method='first')
    df['PTS_FB_DIFF'] = df['PTS_FB'] - df['OPP_PTS_FB']
    df['PTS_FB_DIFF_RANK'] = df['PTS_FB_DIFF'].rank(ascending=False, method='first')
    df['PTS_OFF_TOV_DIFF'] = df['PTS_OFF_TOV'] - df['OPP_PTS_OFF_TOV']
    df['PTS_OFF_TOV_DIFF_RANK'] = df['PTS_OFF_TOV_DIFF'].rank(ascending=False, method='first')
    df['PTS_PAINT_RANK'] = df['PTS_PAINT'].rank(ascending=False, method='first').astype(int)
    df['OPP_PTS_PAINT_RANK'] = df['OPP_PTS_PAINT'].rank(ascending=True, method='first').astype(int)
    df['PTS_2ND_CHANCE_RANK'] = df['PTS_2ND_CHANCE'].rank(ascending=False, method='first').astype(int)
    df['OPP_PTS_2ND_CHANCE_RANK'] = df['OPP_PTS_2ND_CHANCE'].rank(ascending=True, method='first').astype(int)
    df['PTS_FB_RANK'] = df['PTS_FB'].rank(ascending=False, method='first').astype(int)
    df['OPP_PTS_FB_RANK'] = df['OPP_PTS_FB'].rank(ascending=True, method='first').astype(int)
    df['PTS_OFF_TOV_RANK'] = df['PTS_OFF_TOV'].rank(ascending=False, method='first').astype(int)
    df['OPP_PTS_OFF_TOV_RANK'] = df['OPP_PTS_OFF_TOV'].rank(ascending=True, method='first').astype(int)
    return df

@st.cache_data(ttl=3600, show_spinner=False)
def load_trad_season():
    df = nba_api.stats.endpoints.LeagueDashTeamStats(
        league_id_nullable='00',
        measure_type_detailed_defense='Base',
        pace_adjust='N',
        per_mode_detailed='PerGame',
        season=current_season,
        season_type_all_star=season_type
    ).get_data_frames()[0]
    df['AST_RANK'] = df['AST'].rank(ascending=False, method='first').astype(int)
    df['TOV_RANK'] = df['TOV'].rank(ascending=True, method='first').astype(int)
    return df

@st.cache_data(ttl=3600, show_spinner=False)
def load_trad_L5():
    df = nba_api.stats.endpoints.LeagueDashTeamStats(
        league_id_nullable='00',
        measure_type_detailed_defense='Base',
        pace_adjust='N',
        per_mode_detailed='PerGame',
        season=current_season,
        season_type_all_star=season_type,
        last_n_games=5
    ).get_data_frames()[0]
    df['AST_RANK'] = df['AST'].rank(ascending=False, method='first').astype(int)
    df['TOV_RANK'] = df['TOV'].rank(ascending=True, method='first').astype(int)
    return df

@st.cache_data(ttl=3600, show_spinner=False)
def load_trad_season_starters():
    df = nba_api.stats.endpoints.LeagueDashTeamStats(
        league_id_nullable='00',
        measure_type_detailed_defense='Base',
        pace_adjust='N',
        per_mode_detailed='PerGame',
        season=current_season,
        season_type_all_star=season_type,
        starter_bench_nullable='Starters'
    ).get_data_frames()[0]
    df['PTS_RANK'] = df['PTS'].rank(ascending=False, method='first').astype(int)
    return df

@st.cache_data(ttl=3600, show_spinner=False)
def load_trad_L5_starters():
    df = nba_api.stats.endpoints.LeagueDashTeamStats(
        league_id_nullable='00',
        measure_type_detailed_defense='Base',
        pace_adjust='N',
        per_mode_detailed='PerGame',
        season=current_season,
        season_type_all_star=season_type,
        last_n_games=5,
        starter_bench_nullable='Starters'
    ).get_data_frames()[0]
    df['PTS_RANK'] = df['PTS'].rank(ascending=False, method='first').astype(int)
    return df

@st.cache_data(ttl=3600, show_spinner=False)
def load_trad_season_bench():
    df = nba_api.stats.endpoints.LeagueDashTeamStats(
        league_id_nullable='00',
        measure_type_detailed_defense='Base',
        pace_adjust='N',
        per_mode_detailed='PerGame',
        season=current_season,
        season_type_all_star=season_type,
        starter_bench_nullable='Bench'
    ).get_data_frames()[0]
    df['PTS_RANK'] = df['PTS'].rank(ascending=False, method='first').astype(int)
    return df

@st.cache_data(ttl=3600, show_spinner=False)
def load_trad_L5_bench():
    df = nba_api.stats.endpoints.LeagueDashTeamStats(
        league_id_nullable='00',
        measure_type_detailed_defense='Base',
        pace_adjust='N',
        per_mode_detailed='PerGame',
        season=current_season,
        season_type_all_star=season_type,
        last_n_games=5,
        starter_bench_nullable='Bench'
    ).get_data_frames()[0]
    df['PTS_RANK'] = df['PTS'].rank(ascending=False, method='first').astype(int)
    return df

@st.cache_data(ttl=3600, show_spinner=False)
def load_4F_season():
    df = nba_api.stats.endpoints.LeagueDashTeamStats(
        league_id_nullable='00',
        measure_type_detailed_defense='Four Factors',
        pace_adjust='N',
        per_mode_detailed='PerGame',
        season=current_season,
        season_type_all_star=season_type
    ).get_data_frames()[0]
    df['OPP_TOV_PCT_RANK'] = df['OPP_TOV_PCT'].rank(ascending=True, method='first').astype(int)
    return df

@st.cache_data(ttl=3600, show_spinner=False)
def load_4F_L5():
    df = nba_api.stats.endpoints.LeagueDashTeamStats(
        league_id_nullable='00',
        measure_type_detailed_defense='Four Factors',
        pace_adjust='N',
        per_mode_detailed='PerGame',
        season=current_season,
        season_type_all_star=season_type,
        last_n_games=5
    ).get_data_frames()[0]
    df['OPP_TOV_PCT_RANK'] = df['OPP_TOV_PCT'].rank(ascending=True, method='first').astype(int)
    return df

@st.cache_data(ttl=3600, show_spinner=False)
def load_standings():
    return nba_api.stats.endpoints.LeagueStandings(
        league_id='00',
        season=current_season,
        season_type='Regular Season'
    ).get_data_frames()[0]

@st.cache_data(ttl=3600, show_spinner=False)
def load_shooting_data():
    """Load team offense, defense, and differential shooting data from pbpstats."""
    try:
        team_offense_url = f"https://api.pbpstats.com/get-totals/nba?Season={current_season}&SeasonType={season_type.replace(' ', '+')}&Type=Team"
        team_stats = pd.DataFrame(requests.get(team_offense_url).json()['multi_row_table_data'])
    except:
        team_offense_url = f"https://api.pbpstats.com/get-totals/nba?Season=2024-25&SeasonType={season_type.replace(' ', '+')}&Type=Team"
        team_stats = pd.DataFrame(requests.get(team_offense_url).json()['multi_row_table_data'])

    try:
        opp_offense_url = f"https://api.pbpstats.com/get-totals/nba?Season={current_season}&SeasonType={season_type.replace(' ', '+')}&Type=Opponent"
        opp_team_stats = pd.DataFrame(requests.get(opp_offense_url).json()['multi_row_table_data'])
    except:
        opp_offense_url = f"https://api.pbpstats.com/get-totals/nba?Season=2024-25&SeasonType={season_type.replace(' ', '+')}&Type=Opponent"
        opp_team_stats = pd.DataFrame(requests.get(opp_offense_url).json()['multi_row_table_data'])

    team_stats['TeamId'] = team_stats['TeamId'].astype(int)
    opp_team_stats['TeamId'] = opp_team_stats['TeamId'].astype(int)

    for df in [team_stats, opp_team_stats]:
        df['FGM'] = df['FG2M'] + df['FG3M']
        df['FGA'] = df['FG2A'] + df['FG3A']
        df['FGM_PG'] = round(df['FGM'] / df['GamesPlayed'], 1)
        df['FGA_PG'] = round(df['FGA'] / df['GamesPlayed'], 1)
        df['FG%'] = round(df['FGM'] / df['FGA'], 3)
        df['FG2M_PG'] = round(df['FG2M'] / df['GamesPlayed'], 1)
        df['FG2A_PG'] = round(df['FG2A'] / df['GamesPlayed'], 1)
        df['2PT%'] = df['Fg2Pct']
        df['FG3M_PG'] = round(df['FG3M'] / df['GamesPlayed'], 1)
        df['FG3A_PG'] = round(df['FG3A'] / df['GamesPlayed'], 1)
        df['3PT%'] = df['Fg3Pct']
        df['FTM'] = df['FtPoints']
        df['FTM_PG'] = round(df['FTM'] / df['GamesPlayed'], 1)
        df['FTA_PG'] = round(df['FTA'] / df['GamesPlayed'], 1)
        df['FT%'] = round(df['FTM'] / df['FTA'], 3) if df['FTA'].sum() > 0 else 0

    team_stats['FGM_RANK'] = team_stats['FGM_PG'].rank(ascending=False, method='first').astype(int)
    team_stats['FGA_RANK'] = team_stats['FGA_PG'].rank(ascending=False, method='first').astype(int)
    team_stats['FG%_RANK'] = team_stats['FG%'].rank(ascending=False, method='first').astype(int)
    team_stats['FG2M_RANK'] = team_stats['FG2M_PG'].rank(ascending=False, method='first').astype(int)
    team_stats['FG2A_RANK'] = team_stats['FG2A_PG'].rank(ascending=False, method='first').astype(int)
    team_stats['2PT%_RANK'] = team_stats['2PT%'].rank(ascending=False, method='first').astype(int)
    team_stats['FG3M_RANK'] = team_stats['FG3M_PG'].rank(ascending=False, method='first').astype(int)
    team_stats['FG3A_RANK'] = team_stats['FG3A_PG'].rank(ascending=False, method='first').astype(int)
    team_stats['3PT%_RANK'] = team_stats['3PT%'].rank(ascending=False, method='first').astype(int)
    team_stats['FTM_RANK'] = team_stats['FTM_PG'].rank(ascending=False, method='first').astype(int)
    team_stats['FTA_RANK'] = team_stats['FTA_PG'].rank(ascending=False, method='first').astype(int)
    team_stats['FT%_RANK'] = team_stats['FT%'].rank(ascending=False, method='first').astype(int)

    opp_team_stats['FGM_RANK'] = opp_team_stats['FGM_PG'].rank(ascending=True, method='first').astype(int)
    opp_team_stats['FGA_RANK'] = opp_team_stats['FGA_PG'].rank(ascending=True, method='first').astype(int)
    opp_team_stats['FG%_RANK'] = opp_team_stats['FG%'].rank(ascending=True, method='first').astype(int)
    opp_team_stats['FG2M_RANK'] = opp_team_stats['FG2M_PG'].rank(ascending=True, method='first').astype(int)
    opp_team_stats['FG2A_RANK'] = opp_team_stats['FG2A_PG'].rank(ascending=True, method='first').astype(int)
    opp_team_stats['2PT%_RANK'] = opp_team_stats['2PT%'].rank(ascending=True, method='first').astype(int)
    opp_team_stats['FG3M_RANK'] = opp_team_stats['FG3M_PG'].rank(ascending=True, method='first').astype(int)
    opp_team_stats['FG3A_RANK'] = opp_team_stats['FG3A_PG'].rank(ascending=True, method='first').astype(int)
    opp_team_stats['3PT%_RANK'] = opp_team_stats['3PT%'].rank(ascending=True, method='first').astype(int)
    opp_team_stats['FTM_RANK'] = opp_team_stats['FTM_PG'].rank(ascending=True, method='first').astype(int)
    opp_team_stats['FTA_RANK'] = opp_team_stats['FTA_PG'].rank(ascending=True, method='first').astype(int)
    opp_team_stats['FT%_RANK'] = opp_team_stats['FT%'].rank(ascending=True, method='first').astype(int)

    shooting_diff_results = team_stats.copy()
    for col in ['FGM_PG', 'FGA_PG', 'FG%', 'FG2M_PG', 'FG2A_PG', '2PT%', 'FG3M_PG', 'FG3A_PG', '3PT%', 'FTM_PG', 'FTA_PG', 'FT%']:
        shooting_diff_results[col] = team_stats[col].values - opp_team_stats[col].values

    shooting_diff_results['FGM_RANK'] = shooting_diff_results['FGM_PG'].rank(ascending=False, method='first').astype(int)
    shooting_diff_results['FGA_RANK'] = shooting_diff_results['FGA_PG'].rank(ascending=False, method='first').astype(int)
    shooting_diff_results['FG%_RANK'] = shooting_diff_results['FG%'].rank(ascending=False, method='first').astype(int)
    shooting_diff_results['FG2M_RANK'] = shooting_diff_results['FG2M_PG'].rank(ascending=False, method='first').astype(int)
    shooting_diff_results['FG2A_RANK'] = shooting_diff_results['FG2A_PG'].rank(ascending=False, method='first').astype(int)
    shooting_diff_results['2PT%_RANK'] = shooting_diff_results['2PT%'].rank(ascending=False, method='first').astype(int)
    shooting_diff_results['FG3M_RANK'] = shooting_diff_results['FG3M_PG'].rank(ascending=False, method='first').astype(int)
    shooting_diff_results['FG3A_RANK'] = shooting_diff_results['FG3A_PG'].rank(ascending=False, method='first').astype(int)
    shooting_diff_results['3PT%_RANK'] = shooting_diff_results['3PT%'].rank(ascending=False, method='first').astype(int)
    shooting_diff_results['FTM_RANK'] = shooting_diff_results['FTM_PG'].rank(ascending=False, method='first').astype(int)
    shooting_diff_results['FTA_RANK'] = shooting_diff_results['FTA_PG'].rank(ascending=False, method='first').astype(int)
    shooting_diff_results['FT%_RANK'] = shooting_diff_results['FT%'].rank(ascending=False, method='first').astype(int)

    for df in [team_stats, opp_team_stats, shooting_diff_results]:
        df['RIM_FREQ_RANK'] = df['AtRimFrequency'].rank(ascending=False, method='first').astype(int)
        df['RIM_FG%_RANK'] = df['AtRimAccuracy'].rank(ascending=False, method='first').astype(int)
        df['SMR_FREQ_RANK'] = df['ShortMidRangeFrequency'].rank(ascending=False, method='first').astype(int)
        df['SMR_FG%_RANK'] = df['ShortMidRangeAccuracy'].rank(ascending=False, method='first').astype(int)
        df['LMR_FREQ_RANK'] = df['LongMidRangeFrequency'].rank(ascending=False, method='first').astype(int)
        df['LMR_FG%_RANK'] = df['LongMidRangeAccuracy'].rank(ascending=False, method='first').astype(int)
        df['C3_FREQ_RANK'] = df['Corner3Frequency'].rank(ascending=False, method='first').astype(int)
        df['C3_FG%_RANK'] = df['Corner3Accuracy'].rank(ascending=False, method='first').astype(int)
        df['ATB3_FREQ_RANK'] = df['Arc3Frequency'].rank(ascending=False, method='first').astype(int)
        df['ATB3_FG%_RANK'] = df['Arc3Accuracy'].rank(ascending=False, method='first').astype(int)

    return team_stats, opp_team_stats, shooting_diff_results


# ============================================================
# LAZY-LOADED MODULE-LEVEL VARIABLES
# These preserve the original variable names so the rest of
# your code (get_matchup_stats, etc.) works without any changes.
# Data is only fetched on first access, then cached by Streamlit.
# ============================================================

def _get_data():
    """Internal helper to load all data and return as a dict."""
    return {
        'adv_season': load_adv_season(),
        'adv_L5': load_adv_L5(),
        'misc_season': load_misc_season(),
        'misc_L5': load_misc_L5(),
        'trad_season': load_trad_season(),
        'trad_L5': load_trad_L5(),
        'trad_season_starters': load_trad_season_starters(),
        'trad_L5_starters': load_trad_L5_starters(),
        'trad_season_bench': load_trad_season_bench(),
        'trad_L5_bench': load_trad_L5_bench(),
        '4F_season': load_4F_season(),
        '4F_L5': load_4F_L5(),
        'standings': load_standings(),
        'shooting': load_shooting_data(),
    }

# Expose original variable names by calling cached loaders
# This means the rest of this file and any callers don't need to change
data_adv_season = load_adv_season()
data_adv_L5 = load_adv_L5()
data_misc_season = load_misc_season()
data_misc_L5 = load_misc_L5()
data_trad_season = load_trad_season()
data_trad_L5 = load_trad_L5()
data_trad_season_starters = load_trad_season_starters()
data_trad_L5_starters = load_trad_L5_starters()
data_trad_season_bench = load_trad_season_bench()
data_trad_L5_bench = load_trad_L5_bench()
data_4F_season = load_4F_season()
data_4F_L5 = load_4F_L5()
standings = load_standings()
team_stats, opp_team_stats, shooting_diff_results = load_shooting_data()


# ============================================================
# HELPER FUNCTIONS (unchanged from original)
# ============================================================

# Helper function to get matchups for a given date
def get_matchups_for_date(selected_date):
    """Fetch NBA matchups for a given date from the API"""
    try:
        league_schedule = nba_api.stats.endpoints.ScheduleLeagueV2(
            league_id='00',
            season=current_season
        ).get_data_frames()[0]

        league_schedule['dateGame'] = pd.to_datetime(league_schedule['gameDate'])
        league_schedule['matchup'] = league_schedule['awayTeam_teamTricode'] + ' @ ' + league_schedule['homeTeam_teamTricode']

        date_games = league_schedule[
            league_schedule['dateGame'].dt.date == selected_date
        ]

        if len(date_games) > 0:
            matchups = []
            for _, row in date_games.iterrows():
                matchup_str = row['matchup']
                away_team_name = data_adv_season.loc[data_adv_season['TEAM_ID'] == row['awayTeam_teamId'], 'TEAM_NAME'].values
                home_team_name = data_adv_season.loc[data_adv_season['TEAM_ID'] == row['homeTeam_teamId'], 'TEAM_NAME'].values

                matchups.append({
                    'matchup': matchup_str,
                    'away_team': row['awayTeam_teamTricode'],
                    'home_team': row['homeTeam_teamTricode'],
                    'away_team_id': row['awayTeam_teamId'],
                    'home_team_id': row['homeTeam_teamId'],
                    'away_team_name': away_team_name[0] if len(away_team_name) > 0 else row['awayTeam_teamTricode'],
                    'home_team_name': home_team_name[0] if len(home_team_name) > 0 else row['homeTeam_teamTricode']
                })
            return matchups, None
        else:
            return [], None
    except Exception as e:
        return [], str(e)


# Helper function to get team list for manual selection
def get_team_list():
    """Return list of all teams for dropdown selection"""
    teams = data_adv_season[['TEAM_ID', 'TEAM_NAME', 'TEAM_ABBREVIATION']].sort_values('TEAM_NAME')
    return teams.to_dict('records')


# ============================================================
# MATCHUP OVERRIDE HELPERS
# (preserving any existing set/update functions your pages use)
# ============================================================
_matchup_override = None
_selected_matchup = None

def set_matchup_override(matchup):
    global _matchup_override
    _matchup_override = matchup

def update_selected_matchup(matchup):
    global _selected_matchup
    _selected_matchup = matchup

def get_players_dataframe():
    """Stub - implement or import as needed"""
    raise NotImplementedError("get_players_dataframe must be implemented")

def get_all_player_game_logs():
    """Stub - implement or import as needed"""
    raise NotImplementedError("get_all_player_game_logs must be implemented")


def get_matchup_stats(selected_home_id, selected_away_id):
    """
    Calculate all matchup stats for given home and away team IDs.
    Returns a dictionary with all stats needed for display.
    """
    stats = {}

    # Team logos
    stats['home_id'] = selected_home_id
    stats['away_id'] = selected_away_id
    stats['home_logo_link'] = f'https://cdn.nba.com/logos/nba/{selected_home_id}/primary/L/logo.svg'
    stats['away_logo_link'] = f'https://cdn.nba.com/logos/nba/{selected_away_id}/primary/L/logo.svg'
    stats['nba_logo'] = nba_logo

    # Get team names for game title
    home_team_name = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_home_id, 'TEAM_NAME'].values
    away_team_name = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_away_id, 'TEAM_NAME'].values
    home_name = home_team_name[0] if len(home_team_name) > 0 else 'Home Team'
    away_name = away_team_name[0] if len(away_team_name) > 0 else 'Away Team'
    stats['game_title'] = f'{away_name} at {home_name}'

    # Record and Seed
    stats['away_team_record'] = standings.loc[standings['TeamID'] == selected_away_id, 'Record'].values[0] if len(standings.loc[standings['TeamID'] == selected_away_id]) > 0 else 'N/A'
    stats['away_team_seed'] = standings.loc[standings['TeamID'] == selected_away_id, 'PlayoffRank'].values[0] if len(standings.loc[standings['TeamID'] == selected_away_id]) > 0 else 'N/A'
    stats['home_team_record'] = standings.loc[standings['TeamID'] == selected_home_id, 'Record'].values[0] if len(standings.loc[standings['TeamID'] == selected_home_id]) > 0 else 'N/A'
    stats['home_team_seed'] = standings.loc[standings['TeamID'] == selected_home_id, 'PlayoffRank'].values[0] if len(standings.loc[standings['TeamID'] == selected_home_id]) > 0 else 'N/A'

    # Offensive Ratings
    stats['away_team_ortg'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_away_id, 'OFF_RATING'].values[0]
    stats['away_team_ortg_rank'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_away_id, 'OFF_RATING_RANK'].values[0]
    stats['l5_away_team_ortg'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_away_id, 'OFF_RATING'].values[0]
    stats['l5_away_team_ortg_rank'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_away_id, 'OFF_RATING_RANK'].values[0]
    stats['la_ortg'] = round(data_adv_season['OFF_RATING'].mean(), 1)
    stats['l5_la_ortg'] = round(data_adv_L5['OFF_RATING'].mean(), 1)
    stats['home_team_ortg'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_home_id, 'OFF_RATING'].values[0]
    stats['home_team_ortg_rank'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_home_id, 'OFF_RATING_RANK'].values[0]
    stats['l5_home_team_ortg'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_home_id, 'OFF_RATING'].values[0]
    stats['l5_home_team_ortg_rank'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_home_id, 'OFF_RATING_RANK'].values[0]

    # Defensive Ratings
    stats['away_team_drtg'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_away_id, 'DEF_RATING'].values[0]
    stats['away_team_drtg_rank'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_away_id, 'DEF_RATING_RANK'].values[0]
    stats['l5_away_team_drtg'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_away_id, 'DEF_RATING'].values[0]
    stats['l5_away_team_drtg_rank'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_away_id, 'DEF_RATING_RANK'].values[0]
    stats['la_drtg'] = round(data_adv_season['DEF_RATING'].mean(), 1)
    stats['l5_la_drtg'] = round(data_adv_L5['DEF_RATING'].mean(), 1)
    stats['home_team_drtg'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_home_id, 'DEF_RATING'].values[0]
    stats['home_team_drtg_rank'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_home_id, 'DEF_RATING_RANK'].values[0]
    stats['l5_home_team_drtg'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_home_id, 'DEF_RATING'].values[0]
    stats['l5_home_team_drtg_rank'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_home_id, 'DEF_RATING_RANK'].values[0]

    # Net Ratings
    stats['away_team_net'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_away_id, 'NET_RATING'].values[0]
    stats['away_team_net_rank'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_away_id, 'NET_RATING_RANK'].values[0]
    stats['l5_away_team_net'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_away_id, 'NET_RATING'].values[0]
    stats['l5_away_team_net_rank'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_away_id, 'NET_RATING_RANK'].values[0]
    stats['la_net'] = 0
    stats['l5_la_net'] = 0
    stats['home_team_net'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_home_id, 'NET_RATING'].values[0]
    stats['home_team_net_rank'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_home_id, 'NET_RATING_RANK'].values[0]
    stats['l5_home_team_net'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_home_id, 'NET_RATING'].values[0]
    stats['l5_home_team_net_rank'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_home_id, 'NET_RATING_RANK'].values[0]

    # DREB%
    stats['away_team_dreb'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_away_id, 'DREB_PCT'].values[0]
    stats['away_team_dreb_rank'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_away_id, 'DREB_PCT_RANK'].values[0]
    stats['l5_away_team_dreb'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_away_id, 'DREB_PCT'].values[0]
    stats['l5_away_team_dreb_rank'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_away_id, 'DREB_PCT_RANK'].values[0]
    stats['la_dreb'] = round(data_adv_season['DREB_PCT'].mean(), 3)
    stats['l5_la_dreb'] = round(data_adv_L5['DREB_PCT'].mean(), 3)
    stats['home_team_dreb'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_home_id, 'DREB_PCT'].values[0]
    stats['home_team_dreb_rank'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_home_id, 'DREB_PCT_RANK'].values[0]
    stats['l5_home_team_dreb'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_home_id, 'DREB_PCT'].values[0]
    stats['l5_home_team_dreb_rank'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_home_id, 'DREB_PCT_RANK'].values[0]

    # OREB%
    stats['away_team_oreb'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_away_id, 'OREB_PCT'].values[0]
    stats['away_team_oreb_rank'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_away_id, 'OREB_PCT_RANK'].values[0]
    stats['l5_away_team_oreb'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_away_id, 'OREB_PCT'].values[0]
    stats['l5_away_team_oreb_rank'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_away_id, 'OREB_PCT_RANK'].values[0]
    stats['la_oreb'] = round(data_adv_season['OREB_PCT'].mean(), 3)
    stats['l5_la_oreb'] = round(data_adv_L5['OREB_PCT'].mean(), 3)
    stats['home_team_oreb'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_home_id, 'OREB_PCT'].values[0]
    stats['home_team_oreb_rank'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_home_id, 'OREB_PCT_RANK'].values[0]
    stats['l5_home_team_oreb'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_home_id, 'OREB_PCT'].values[0]
    stats['l5_home_team_oreb_rank'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_home_id, 'OREB_PCT_RANK'].values[0]

    # REB%
    stats['away_team_reb'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_away_id, 'REB_PCT'].values[0]
    stats['away_team_reb_rank'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_away_id, 'REB_PCT_RANK'].values[0]
    stats['l5_away_team_reb'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_away_id, 'REB_PCT'].values[0]
    stats['l5_away_team_reb_rank'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_away_id, 'REB_PCT_RANK'].values[0]
    stats['la_reb'] = round(data_adv_season['REB_PCT'].mean(), 3)
    stats['l5_la_reb'] = round(data_adv_L5['REB_PCT'].mean(), 3)
    stats['home_team_reb'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_home_id, 'REB_PCT'].values[0]
    stats['home_team_reb_rank'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_home_id, 'REB_PCT_RANK'].values[0]
    stats['l5_home_team_reb'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_home_id, 'REB_PCT'].values[0]
    stats['l5_home_team_reb_rank'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_home_id, 'REB_PCT_RANK'].values[0]

    # Points in the Paint - Offense
    stats['away_team_pitp_off'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_away_id, 'PTS_PAINT'].values[0]
    stats['away_team_pitp_off_rank'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_away_id, 'PTS_PAINT_RANK'].values[0]
    stats['l5_away_team_pitp_off'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_away_id, 'PTS_PAINT'].values[0]
    stats['l5_away_team_pitp_off_rank'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_away_id, 'PTS_PAINT_RANK'].values[0]
    stats['la_pitp_off'] = round(data_misc_season['PTS_PAINT'].mean(), 1)
    stats['l5_la_pitp_off'] = round(data_misc_L5['PTS_PAINT'].mean(), 1)
    stats['home_team_pitp_off'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_home_id, 'PTS_PAINT'].values[0]
    stats['home_team_pitp_off_rank'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_home_id, 'PTS_PAINT_RANK'].values[0]
    stats['l5_home_team_pitp_off'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_home_id, 'PTS_PAINT'].values[0]
    stats['l5_home_team_pitp_off_rank'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_home_id, 'PTS_PAINT_RANK'].values[0]

    # Points in the Paint - Defense
    stats['away_team_pitp_def'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_away_id, 'OPP_PTS_PAINT'].values[0]
    stats['away_team_pitp_def_rank'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_away_id, 'OPP_PTS_PAINT_RANK'].values[0]
    stats['l5_away_team_pitp_def'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_away_id, 'OPP_PTS_PAINT'].values[0]
    stats['l5_away_team_pitp_def_rank'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_away_id, 'OPP_PTS_PAINT_RANK'].values[0]
    stats['la_pitp_def'] = round(data_misc_season['OPP_PTS_PAINT'].mean(), 1)
    stats['l5_la_pitp_def'] = round(data_misc_L5['OPP_PTS_PAINT'].mean(), 1)
    stats['home_team_pitp_def'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_home_id, 'OPP_PTS_PAINT'].values[0]
    stats['home_team_pitp_def_rank'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_home_id, 'OPP_PTS_PAINT_RANK'].values[0]
    stats['l5_home_team_pitp_def'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_home_id, 'OPP_PTS_PAINT'].values[0]
    stats['l5_home_team_pitp_def_rank'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_home_id, 'OPP_PTS_PAINT_RANK'].values[0]

    # Points in the Paint - Differential
    stats['away_team_pitp_diff'] = round(data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_away_id, 'PTS_PAINT_DIFF'].values[0], 1)
    stats['away_team_pitp_diff_rank'] = int(data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_away_id, 'PTS_PAINT_DIFF_RANK'].values[0])
    stats['l5_away_team_pitp_diff'] = round(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_away_id, 'PTS_PAINT_DIFF'].values[0], 1)
    stats['l5_away_team_pitp_diff_rank'] = int(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_away_id, 'PTS_PAINT_DIFF_RANK'].values[0])
    stats['la_pitp_diff'] = round(data_misc_season['PTS_PAINT_DIFF'].mean(), 1)
    stats['l5_la_pitp_diff'] = round(data_misc_L5['PTS_PAINT_DIFF'].mean(), 1)
    stats['home_team_pitp_diff'] = round(data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_home_id, 'PTS_PAINT_DIFF'].values[0], 1)
    stats['home_team_pitp_diff_rank'] = int(data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_home_id, 'PTS_PAINT_DIFF_RANK'].values[0])
    stats['l5_home_team_pitp_diff'] = round(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_home_id, 'PTS_PAINT_DIFF'].values[0], 1)
    stats['l5_home_team_pitp_diff_rank'] = int(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_home_id, 'PTS_PAINT_DIFF_RANK'].values[0])

    # 2nd Chance Points - Offense
    stats['away_team_2c_off'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_away_id, 'PTS_2ND_CHANCE'].values[0]
    stats['away_team_2c_off_rank'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_away_id, 'PTS_2ND_CHANCE_RANK'].values[0]
    stats['l5_away_team_2c_off'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_away_id, 'PTS_2ND_CHANCE'].values[0]
    stats['l5_away_team_2c_off_rank'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_away_id, 'PTS_2ND_CHANCE_RANK'].values[0]
    stats['la_2c_off'] = round(data_misc_season['PTS_2ND_CHANCE'].mean(), 1)
    stats['l5_la_2c_off'] = round(data_misc_L5['PTS_2ND_CHANCE'].mean(), 1)
    stats['home_team_2c_off'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_home_id, 'PTS_2ND_CHANCE'].values[0]
    stats['home_team_2c_off_rank'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_home_id, 'PTS_2ND_CHANCE_RANK'].values[0]
    stats['l5_home_team_2c_off'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_home_id, 'PTS_2ND_CHANCE'].values[0]
    stats['l5_home_team_2c_off_rank'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_home_id, 'PTS_2ND_CHANCE_RANK'].values[0]

    # 2nd Chance Points - Defense
    stats['away_team_2c_def'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_away_id, 'OPP_PTS_2ND_CHANCE'].values[0]
    stats['away_team_2c_def_rank'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_away_id, 'OPP_PTS_2ND_CHANCE_RANK'].values[0]
    stats['l5_away_team_2c_def'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_away_id, 'OPP_PTS_2ND_CHANCE'].values[0]
    stats['l5_away_team_2c_def_rank'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_away_id, 'OPP_PTS_2ND_CHANCE_RANK'].values[0]
    stats['la_2c_def'] = round(data_misc_season['OPP_PTS_2ND_CHANCE'].mean(), 1)
    stats['l5_la_2c_def'] = round(data_misc_L5['OPP_PTS_2ND_CHANCE'].mean(), 1)
    stats['home_team_2c_def'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_home_id, 'OPP_PTS_2ND_CHANCE'].values[0]
    stats['home_team_2c_def_rank'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_home_id, 'OPP_PTS_2ND_CHANCE_RANK'].values[0]
    stats['l5_home_team_2c_def'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_home_id, 'OPP_PTS_2ND_CHANCE'].values[0]
    stats['l5_home_team_2c_def_rank'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_home_id, 'OPP_PTS_2ND_CHANCE_RANK'].values[0]

    # 2nd Chance Points - Differential
    stats['away_team_2c_diff'] = round(data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_away_id, 'PTS_2ND_CHANCE_DIFF'].values[0], 1)
    stats['away_team_2c_diff_rank'] = int(data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_away_id, 'PTS_2ND_CHANCE_DIFF_RANK'].values[0])
    stats['l5_away_team_2c_diff'] = round(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_away_id, 'PTS_2ND_CHANCE_DIFF'].values[0], 1)
    stats['l5_away_team_2c_diff_rank'] = int(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_away_id, 'PTS_2ND_CHANCE_DIFF_RANK'].values[0])
    stats['la_2c_diff'] = round(data_misc_season['PTS_2ND_CHANCE_DIFF'].mean(), 1)
    stats['l5_la_2c_diff'] = round(data_misc_L5['PTS_2ND_CHANCE_DIFF'].mean(), 1)
    stats['home_team_2c_diff'] = round(data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_home_id, 'PTS_2ND_CHANCE_DIFF'].values[0], 1)
    stats['home_team_2c_diff_rank'] = int(data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_home_id, 'PTS_2ND_CHANCE_DIFF_RANK'].values[0])
    stats['l5_home_team_2c_diff'] = round(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_home_id, 'PTS_2ND_CHANCE_DIFF'].values[0], 1)
    stats['l5_home_team_2c_diff_rank'] = int(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_home_id, 'PTS_2ND_CHANCE_DIFF_RANK'].values[0])

    # Fast Break Points - Offense
    stats['away_team_fb_off'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_away_id, 'PTS_FB'].values[0]
    stats['away_team_fb_off_rank'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_away_id, 'PTS_FB_RANK'].values[0]
    stats['l5_away_team_fb_off'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_away_id, 'PTS_FB'].values[0]
    stats['l5_away_team_fb_off_rank'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_away_id, 'PTS_FB_RANK'].values[0]
    stats['la_fb_off'] = round(data_misc_season['PTS_FB'].mean(), 1)
    stats['l5_la_fb_off'] = round(data_misc_L5['PTS_FB'].mean(), 1)
    stats['home_team_fb_off'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_home_id, 'PTS_FB'].values[0]
    stats['home_team_fb_off_rank'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_home_id, 'PTS_FB_RANK'].values[0]
    stats['l5_home_team_fb_off'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_home_id, 'PTS_FB'].values[0]
    stats['l5_home_team_fb_off_rank'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_home_id, 'PTS_FB_RANK'].values[0]

    # Fast Break Points - Defense
    stats['away_team_fb_def'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_away_id, 'OPP_PTS_FB'].values[0]
    stats['away_team_fb_def_rank'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_away_id, 'OPP_PTS_FB_RANK'].values[0]
    stats['l5_away_team_fb_def'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_away_id, 'OPP_PTS_FB'].values[0]
    stats['l5_away_team_fb_def_rank'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_away_id, 'OPP_PTS_FB_RANK'].values[0]
    stats['la_fb_def'] = round(data_misc_season['OPP_PTS_FB'].mean(), 1)
    stats['l5_la_fb_def'] = round(data_misc_L5['OPP_PTS_FB'].mean(), 1)
    stats['home_team_fb_def'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_home_id, 'OPP_PTS_FB'].values[0]
    stats['home_team_fb_def_rank'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_home_id, 'OPP_PTS_FB_RANK'].values[0]
    stats['l5_home_team_fb_def'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_home_id, 'OPP_PTS_FB'].values[0]
    stats['l5_home_team_fb_def_rank'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_home_id, 'OPP_PTS_FB_RANK'].values[0]

    # Fast Break Points - Differential
    stats['away_team_fb_diff'] = round(data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_away_id, 'PTS_FB_DIFF'].values[0], 1)
    stats['away_team_fb_diff_rank'] = int(data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_away_id, 'PTS_FB_DIFF_RANK'].values[0])
    stats['l5_away_team_fb_diff'] = round(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_away_id, 'PTS_FB_DIFF'].values[0], 1)
    stats['l5_away_team_fb_diff_rank'] = int(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_away_id, 'PTS_FB_DIFF_RANK'].values[0])
    stats['la_fb_diff'] = round(data_misc_season['PTS_FB_DIFF'].mean(), 1)
    stats['l5_la_fb_diff'] = round(data_misc_L5['PTS_FB_DIFF'].mean(), 1)
    stats['home_team_fb_diff'] = round(data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_home_id, 'PTS_FB_DIFF'].values[0], 1)
    stats['home_team_fb_diff_rank'] = int(data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_home_id, 'PTS_FB_DIFF_RANK'].values[0])
    stats['l5_home_team_fb_diff'] = round(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_home_id, 'PTS_FB_DIFF'].values[0], 1)
    stats['l5_home_team_fb_diff_rank'] = int(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_home_id, 'PTS_FB_DIFF_RANK'].values[0])

    # Points Off Turnovers - Offense
    stats['away_team_pot_off'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_away_id, 'PTS_OFF_TOV'].values[0]
    stats['away_team_pot_off_rank'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_away_id, 'PTS_OFF_TOV_RANK'].values[0]
    stats['l5_away_team_pot_off'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_away_id, 'PTS_OFF_TOV'].values[0]
    stats['l5_away_team_pot_off_rank'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_away_id, 'PTS_OFF_TOV_RANK'].values[0]
    stats['la_pot_off'] = round(data_misc_season['PTS_OFF_TOV'].mean(), 1)
    stats['l5_la_pot_off'] = round(data_misc_L5['PTS_OFF_TOV'].mean(), 1)
    stats['home_team_pot_off'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_home_id, 'PTS_OFF_TOV'].values[0]
    stats['home_team_pot_off_rank'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_home_id, 'PTS_OFF_TOV_RANK'].values[0]
    stats['l5_home_team_pot_off'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_home_id, 'PTS_OFF_TOV'].values[0]
    stats['l5_home_team_pot_off_rank'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_home_id, 'PTS_OFF_TOV_RANK'].values[0]

    # Points Off Turnovers - Defense
    stats['away_team_pot_def'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_away_id, 'OPP_PTS_OFF_TOV'].values[0]
    stats['away_team_pot_def_rank'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_away_id, 'OPP_PTS_OFF_TOV_RANK'].values[0]
    stats['l5_away_team_pot_def'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_away_id, 'OPP_PTS_OFF_TOV'].values[0]
    stats['l5_away_team_pot_def_rank'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_away_id, 'OPP_PTS_OFF_TOV_RANK'].values[0]
    stats['la_pot_def'] = round(data_misc_season['OPP_PTS_OFF_TOV'].mean(), 1)
    stats['l5_la_pot_def'] = round(data_misc_L5['OPP_PTS_OFF_TOV'].mean(), 1)
    stats['home_team_pot_def'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_home_id, 'OPP_PTS_OFF_TOV'].values[0]
    stats['home_team_pot_def_rank'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_home_id, 'OPP_PTS_OFF_TOV_RANK'].values[0]
    stats['l5_home_team_pot_def'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_home_id, 'OPP_PTS_OFF_TOV'].values[0]
    stats['l5_home_team_pot_def_rank'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_home_id, 'OPP_PTS_OFF_TOV_RANK'].values[0]

    # Points Off Turnovers - Differential
    stats['away_team_pot_diff'] = round(data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_away_id, 'PTS_OFF_TOV_DIFF'].values[0], 1)
    stats['away_team_pot_diff_rank'] = int(data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_away_id, 'PTS_OFF_TOV_DIFF_RANK'].values[0])
    stats['l5_away_team_pot_diff'] = round(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_away_id, 'PTS_OFF_TOV_DIFF'].values[0], 1)
    stats['l5_away_team_pot_diff_rank'] = int(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_away_id, 'PTS_OFF_TOV_DIFF_RANK'].values[0])
    stats['la_pot_diff'] = round(data_misc_season['PTS_OFF_TOV_DIFF'].mean(), 1)
    stats['l5_la_pot_diff'] = round(data_misc_L5['PTS_OFF_TOV_DIFF'].mean(), 1)
    stats['home_team_pot_diff'] = round(data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_home_id, 'PTS_OFF_TOV_DIFF'].values[0], 1)
    stats['home_team_pot_diff_rank'] = int(data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_home_id, 'PTS_OFF_TOV_DIFF_RANK'].values[0])
    stats['l5_home_team_pot_diff'] = round(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_home_id, 'PTS_OFF_TOV_DIFF'].values[0], 1)
    stats['l5_home_team_pot_diff_rank'] = int(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_home_id, 'PTS_OFF_TOV_DIFF_RANK'].values[0])

    # Shooting stats (zone-based from pbpstats)
    # Rim - Frequency
    stats['away_team_rim_freq'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'AtRimFrequency'].values[0]
    stats['away_team_rim_freq_rank'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'RIM_FREQ_RANK'].values[0]
    stats['away_team_opp_rim_freq'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'AtRimFrequency'].values[0]
    stats['away_team_opp_rim_freq_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'RIM_FREQ_RANK'].values[0]
    stats['away_team_diff_rim_freq'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'AtRimFrequency'].values[0], 3)
    stats['away_team_diff_rim_freq_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'RIM_FREQ_RANK'].values[0]
    stats['la_rim_freq'] = round(team_stats['AtRimFrequency'].mean(), 3)
    stats['home_team_rim_freq'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'AtRimFrequency'].values[0]
    stats['home_team_rim_freq_rank'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'RIM_FREQ_RANK'].values[0]
    stats['home_team_opp_rim_freq'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'AtRimFrequency'].values[0]
    stats['home_team_opp_rim_freq_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'RIM_FREQ_RANK'].values[0]
    stats['home_team_diff_rim_freq'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'AtRimFrequency'].values[0], 3)
    stats['home_team_diff_rim_freq_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'RIM_FREQ_RANK'].values[0]

    # Rim - Accuracy
    stats['away_team_rim_acc'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'AtRimAccuracy'].values[0]
    stats['away_team_rim_acc_rank'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'RIM_FG%_RANK'].values[0]
    stats['away_team_opp_rim_acc'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'AtRimAccuracy'].values[0]
    stats['away_team_opp_rim_acc_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'RIM_FG%_RANK'].values[0]
    stats['away_team_diff_rim_acc'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'AtRimAccuracy'].values[0], 3)
    stats['away_team_diff_rim_acc_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'RIM_FG%_RANK'].values[0]
    stats['la_rim_acc'] = round(team_stats['AtRimAccuracy'].mean(), 3)
    stats['home_team_rim_acc'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'AtRimAccuracy'].values[0]
    stats['home_team_rim_acc_rank'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'RIM_FG%_RANK'].values[0]
    stats['home_team_opp_rim_acc'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'AtRimAccuracy'].values[0]
    stats['home_team_opp_rim_acc_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'RIM_FG%_RANK'].values[0]
    stats['home_team_diff_rim_acc'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'AtRimAccuracy'].values[0], 3)
    stats['home_team_diff_rim_acc_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'RIM_FG%_RANK'].values[0]

    # Short Mid-Range - Frequency
    stats['away_team_smr_freq'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'ShortMidRangeFrequency'].values[0]
    stats['away_team_smr_freq_rank'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'SMR_FREQ_RANK'].values[0]
    stats['away_team_opp_smr_freq'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'ShortMidRangeFrequency'].values[0]
    stats['away_team_opp_smr_freq_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'SMR_FREQ_RANK'].values[0]
    stats['away_team_diff_smr_freq'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'ShortMidRangeFrequency'].values[0], 3)
    stats['away_team_diff_smr_freq_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'SMR_FREQ_RANK'].values[0]
    stats['la_smr_freq'] = round(team_stats['ShortMidRangeFrequency'].mean(), 3)
    stats['home_team_smr_freq'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'ShortMidRangeFrequency'].values[0]
    stats['home_team_smr_freq_rank'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'SMR_FREQ_RANK'].values[0]
    stats['home_team_opp_smr_freq'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'ShortMidRangeFrequency'].values[0]
    stats['home_team_opp_smr_freq_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'SMR_FREQ_RANK'].values[0]
    stats['home_team_diff_smr_freq'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'ShortMidRangeFrequency'].values[0], 3)
    stats['home_team_diff_smr_freq_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'SMR_FREQ_RANK'].values[0]

    # Short Mid-Range - Accuracy
    stats['away_team_smr_acc'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'ShortMidRangeAccuracy'].values[0]
    stats['away_team_smr_acc_rank'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'SMR_FG%_RANK'].values[0]
    stats['away_team_opp_smr_acc'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'ShortMidRangeAccuracy'].values[0]
    stats['away_team_opp_smr_acc_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'SMR_FG%_RANK'].values[0]
    stats['away_team_diff_smr_acc'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'ShortMidRangeAccuracy'].values[0], 3)
    stats['away_team_diff_smr_acc_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'SMR_FG%_RANK'].values[0]
    stats['la_smr_acc'] = round(team_stats['ShortMidRangeAccuracy'].mean(), 3)
    stats['home_team_smr_acc'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'ShortMidRangeAccuracy'].values[0]
    stats['home_team_smr_acc_rank'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'SMR_FG%_RANK'].values[0]
    stats['home_team_opp_smr_acc'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'ShortMidRangeAccuracy'].values[0]
    stats['home_team_opp_smr_acc_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'SMR_FG%_RANK'].values[0]
    stats['home_team_diff_smr_acc'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'ShortMidRangeAccuracy'].values[0], 3)
    stats['home_team_diff_smr_acc_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'SMR_FG%_RANK'].values[0]

    # Long Mid-Range - Frequency
    stats['away_team_lmr_freq'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'LongMidRangeFrequency'].values[0]
    stats['away_team_lmr_freq_rank'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'LMR_FREQ_RANK'].values[0]
    stats['away_team_opp_lmr_freq'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'LongMidRangeFrequency'].values[0]
    stats['away_team_opp_lmr_freq_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'LMR_FREQ_RANK'].values[0]
    stats['away_team_diff_lmr_freq'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'LongMidRangeFrequency'].values[0], 3)
    stats['away_team_diff_lmr_freq_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'LMR_FREQ_RANK'].values[0]
    stats['la_lmr_freq'] = round(team_stats['LongMidRangeFrequency'].mean(), 3)
    stats['home_team_lmr_freq'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'LongMidRangeFrequency'].values[0]
    stats['home_team_lmr_freq_rank'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'LMR_FREQ_RANK'].values[0]
    stats['home_team_opp_lmr_freq'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'LongMidRangeFrequency'].values[0]
    stats['home_team_opp_lmr_freq_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'LMR_FREQ_RANK'].values[0]
    stats['home_team_diff_lmr_freq'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'LongMidRangeFrequency'].values[0], 3)
    stats['home_team_diff_lmr_freq_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'LMR_FREQ_RANK'].values[0]

    # Long Mid-Range - Accuracy
    stats['away_team_lmr_acc'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'LongMidRangeAccuracy'].values[0]
    stats['away_team_lmr_acc_rank'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'LMR_FG%_RANK'].values[0]
    stats['away_team_opp_lmr_acc'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'LongMidRangeAccuracy'].values[0]
    stats['away_team_opp_lmr_acc_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'LMR_FG%_RANK'].values[0]
    stats['away_team_diff_lmr_acc'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'LongMidRangeAccuracy'].values[0], 3)
    stats['away_team_diff_lmr_acc_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'LMR_FG%_RANK'].values[0]
    stats['la_lmr_acc'] = round(team_stats['LongMidRangeAccuracy'].mean(), 3)
    stats['home_team_lmr_acc'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'LongMidRangeAccuracy'].values[0]
    stats['home_team_lmr_acc_rank'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'LMR_FG%_RANK'].values[0]
    stats['home_team_opp_lmr_acc'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'LongMidRangeAccuracy'].values[0]
    stats['home_team_opp_lmr_acc_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'LMR_FG%_RANK'].values[0]
    stats['home_team_diff_lmr_acc'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'LongMidRangeAccuracy'].values[0], 3)
    stats['home_team_diff_lmr_acc_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'LMR_FG%_RANK'].values[0]

    # Corner 3 - Frequency
    stats['away_team_c3_freq'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'Corner3Frequency'].values[0]
    stats['away_team_c3_freq_rank'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'C3_FREQ_RANK'].values[0]
    stats['away_team_opp_c3_freq'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'Corner3Frequency'].values[0]
    stats['away_team_opp_c3_freq_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'C3_FREQ_RANK'].values[0]
    stats['away_team_diff_c3_freq'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'Corner3Frequency'].values[0], 3)
    stats['away_team_diff_c3_freq_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'C3_FREQ_RANK'].values[0]
    stats['la_c3_freq'] = round(team_stats['Corner3Frequency'].mean(), 3)
    stats['home_team_c3_freq'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'Corner3Frequency'].values[0]
    stats['home_team_c3_freq_rank'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'C3_FREQ_RANK'].values[0]
    stats['home_team_opp_c3_freq'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'Corner3Frequency'].values[0]
    stats['home_team_opp_c3_freq_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'C3_FREQ_RANK'].values[0]
    stats['home_team_diff_c3_freq'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'Corner3Frequency'].values[0], 3)
    stats['home_team_diff_c3_freq_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'C3_FREQ_RANK'].values[0]

    # Corner 3 - Accuracy
    stats['away_team_c3_acc'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'Corner3Accuracy'].values[0]
    stats['away_team_c3_acc_rank'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'C3_FG%_RANK'].values[0]
    stats['away_team_opp_c3_acc'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'Corner3Accuracy'].values[0]
    stats['away_team_opp_c3_acc_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'C3_FG%_RANK'].values[0]
    stats['away_team_diff_c3_acc'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'Corner3Accuracy'].values[0], 3)
    stats['away_team_diff_c3_acc_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'C3_FG%_RANK'].values[0]
    stats['la_c3_acc'] = round(team_stats['Corner3Accuracy'].mean(), 3)
    stats['home_team_c3_acc'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'Corner3Accuracy'].values[0]
    stats['home_team_c3_acc_rank'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'C3_FG%_RANK'].values[0]
    stats['home_team_opp_c3_acc'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'Corner3Accuracy'].values[0]
    stats['home_team_opp_c3_acc_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'C3_FG%_RANK'].values[0]
    stats['home_team_diff_c3_acc'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'Corner3Accuracy'].values[0], 3)
    stats['home_team_diff_c3_acc_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'C3_FG%_RANK'].values[0]

    # Above the Break 3 - Frequency
    stats['away_team_atb3_freq'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'Arc3Frequency'].values[0]
    stats['away_team_atb3_freq_rank'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'ATB3_FREQ_RANK'].values[0]
    stats['away_team_opp_atb3_freq'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'Arc3Frequency'].values[0]
    stats['away_team_opp_atb3_freq_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'ATB3_FREQ_RANK'].values[0]
    stats['away_team_diff_atb3_freq'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'Arc3Frequency'].values[0], 3)
    stats['away_team_diff_atb3_freq_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'ATB3_FREQ_RANK'].values[0]
    stats['la_atb3_freq'] = round(team_stats['Arc3Frequency'].mean(), 3)
    stats['home_team_atb3_freq'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'Arc3Frequency'].values[0]
    stats['home_team_atb3_freq_rank'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'ATB3_FREQ_RANK'].values[0]
    stats['home_team_opp_atb3_freq'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'Arc3Frequency'].values[0]
    stats['home_team_opp_atb3_freq_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'ATB3_FREQ_RANK'].values[0]
    stats['home_team_diff_atb3_freq'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'Arc3Frequency'].values[0], 3)
    stats['home_team_diff_atb3_freq_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'ATB3_FREQ_RANK'].values[0]

    # Above the Break 3 - Accuracy
    stats['away_team_atb3_acc'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'Arc3Accuracy'].values[0]
    stats['away_team_atb3_acc_rank'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'ATB3_FG%_RANK'].values[0]
    stats['away_team_opp_atb3_acc'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'Arc3Accuracy'].values[0]
    stats['away_team_opp_atb3_acc_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'ATB3_FG%_RANK'].values[0]
    stats['away_team_diff_atb3_acc'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'Arc3Accuracy'].values[0], 3)
    stats['away_team_diff_atb3_acc_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'ATB3_FG%_RANK'].values[0]
    stats['la_atb3_acc'] = round(team_stats['Arc3Accuracy'].mean(), 3)
    stats['home_team_atb3_acc'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'Arc3Accuracy'].values[0]
    stats['home_team_atb3_acc_rank'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'ATB3_FG%_RANK'].values[0]
    stats['home_team_opp_atb3_acc'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'Arc3Accuracy'].values[0]
    stats['home_team_opp_atb3_acc_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'ATB3_FG%_RANK'].values[0]
    stats['home_team_diff_atb3_acc'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'Arc3Accuracy'].values[0], 3)
    stats['home_team_diff_atb3_acc_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'ATB3_FG%_RANK'].values[0]

    return stats