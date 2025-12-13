import nba_api.stats.endpoints
import requests
import json
import pandas as pd
import nba_api

current_season = '2025-26'
season_type = 'Regular Season'
# opponent_id = 1610612760

#ADVANCED DATA LOADING
##SEASON
data_adv_season = nba_api.stats.endpoints.LeagueDashTeamStats(
    league_id_nullable='00',
    # last_n_games=None,
    measure_type_detailed_defense='Advanced',
    pace_adjust='N',
    per_mode_detailed='PerGame',
    season=current_season,
    season_type_all_star=season_type
    ).get_data_frames()[0]

# Add missing ranking columns for Core Stats
data_adv_season['OFF_RATING_RANK'] = data_adv_season['OFF_RATING'].rank(ascending=False, method='first').astype(int)
data_adv_season['DEF_RATING_RANK'] = data_adv_season['DEF_RATING'].rank(ascending=True, method='first').astype(int)
data_adv_season['NET_RATING_RANK'] = data_adv_season['NET_RATING'].rank(ascending=False, method='first').astype(int)
data_adv_season['PACE_RANK'] = data_adv_season['PACE'].rank(ascending=False, method='first').astype(int)
data_adv_season['AST_PCT_RANK'] = data_adv_season['AST_PCT'].rank(ascending=False, method='first').astype(int)
data_adv_season['TM_TOV_PCT_RANK'] = data_adv_season['TM_TOV_PCT'].rank(ascending=True, method='first').astype(int)
data_adv_season['AST_TO_RANK'] = data_adv_season['AST_TO'].rank(ascending=False, method='first').astype(int)
data_adv_season['DREB_PCT_RANK'] = data_adv_season['DREB_PCT'].rank(ascending=False, method='first').astype(int)
data_adv_season['OREB_PCT_RANK'] = data_adv_season['OREB_PCT'].rank(ascending=False, method='first').astype(int)
data_adv_season['REB_PCT_RANK'] = data_adv_season['REB_PCT'].rank(ascending=False, method='first').astype(int)
##LAST 5 GAMES
data_adv_L5 = nba_api.stats.endpoints.LeagueDashTeamStats(
    league_id_nullable='00',
    # last_n_games=None,
    measure_type_detailed_defense='Advanced',
    pace_adjust='N',
    per_mode_detailed='PerGame',
    season=current_season,
    season_type_all_star=season_type,
    last_n_games=5
    ).get_data_frames()[0]

#MISC DATA LOADING
##SEASON
data_misc_season = nba_api.stats.endpoints.LeagueDashTeamStats(
    league_id_nullable='00',
    # last_n_games=None,
    measure_type_detailed_defense='Misc',
    pace_adjust='N',
    per_mode_detailed='PerGame',
    season=current_season,
    season_type_all_star=season_type
    ).get_data_frames()[0]

### ADJUSTMENTS FOR DIFFERENTIALS
#### POINTS IN THE PAINT
data_misc_season['PTS_PAINT_DIFF'] = data_misc_season['PTS_PAINT'] - data_misc_season['OPP_PTS_PAINT']
data_misc_season['PTS_PAINT_DIFF_RANK'] = data_misc_season['PTS_PAINT_DIFF'].rank(ascending=False, method='first')
#### SECOND CHANCE POINTS
data_misc_season['PTS_2ND_CHANCE_DIFF'] = data_misc_season['PTS_2ND_CHANCE'] - data_misc_season['OPP_PTS_2ND_CHANCE']
data_misc_season['PTS_2ND_CHANCE_DIFF_RANK'] = data_misc_season['PTS_2ND_CHANCE_DIFF'].rank(ascending=False, method='first')
#### FASTBREAK POINTS
data_misc_season['PTS_FB_DIFF'] = data_misc_season['PTS_FB'] - data_misc_season['OPP_PTS_FB']
data_misc_season['PTS_FB_DIFF_RANK'] = data_misc_season['PTS_FB_DIFF'].rank(ascending=False, method='first')
#### POINTS OFF TURNOVERS
data_misc_season['PTS_OFF_TOV_DIFF'] = data_misc_season['PTS_OFF_TOV'] - data_misc_season['OPP_PTS_OFF_TOV']
data_misc_season['PTS_OFF_TOV_DIFF_RANK'] = data_misc_season['PTS_OFF_TOV_DIFF'].rank(ascending=False, method='first')

# Add missing ranking columns for misc stats
data_misc_season['PTS_PAINT_RANK'] = data_misc_season['PTS_PAINT'].rank(ascending=False, method='first').astype(int)
data_misc_season['OPP_PTS_PAINT_RANK'] = data_misc_season['OPP_PTS_PAINT'].rank(ascending=True, method='first').astype(int)
data_misc_season['PTS_2ND_CHANCE_RANK'] = data_misc_season['PTS_2ND_CHANCE'].rank(ascending=False, method='first').astype(int)
data_misc_season['OPP_PTS_2ND_CHANCE_RANK'] = data_misc_season['OPP_PTS_2ND_CHANCE'].rank(ascending=True, method='first').astype(int)
data_misc_season['PTS_FB_RANK'] = data_misc_season['PTS_FB'].rank(ascending=False, method='first').astype(int)
data_misc_season['OPP_PTS_FB_RANK'] = data_misc_season['OPP_PTS_FB'].rank(ascending=True, method='first').astype(int)
data_misc_season['PTS_OFF_TOV_RANK'] = data_misc_season['PTS_OFF_TOV'].rank(ascending=False, method='first').astype(int)
data_misc_season['OPP_PTS_OFF_TOV_RANK'] = data_misc_season['OPP_PTS_OFF_TOV'].rank(ascending=True, method='first').astype(int)

##LAST 5 GAMES
data_misc_L5 = nba_api.stats.endpoints.LeagueDashTeamStats(
    league_id_nullable='00',
    # last_n_games=None,
    measure_type_detailed_defense='Misc',
    pace_adjust='N',
    per_mode_detailed='PerGame',
    season=current_season,
    season_type_all_star=season_type,
    last_n_games=5
    ).get_data_frames()[0]

### ADJUSTMENTS FOR DIFFERENTIALS
#### POINTS IN THE PAINT
data_misc_L5['PTS_PAINT_DIFF'] = data_misc_L5['PTS_PAINT'] - data_misc_L5['OPP_PTS_PAINT']
data_misc_L5['PTS_PAINT_DIFF_RANK'] = data_misc_L5['PTS_PAINT_DIFF'].rank(ascending=False, method='first')
#### SECOND CHANCE POINTS
data_misc_L5['PTS_2ND_CHANCE_DIFF'] = data_misc_L5['PTS_2ND_CHANCE'] - data_misc_L5['OPP_PTS_2ND_CHANCE']
data_misc_L5['PTS_2ND_CHANCE_DIFF_RANK'] = data_misc_L5['PTS_2ND_CHANCE_DIFF'].rank(ascending=False, method='first')
#### FASTBREAK POINTS
data_misc_L5['PTS_FB_DIFF'] = data_misc_L5['PTS_FB'] - data_misc_L5['OPP_PTS_FB']
data_misc_L5['PTS_FB_DIFF_RANK'] = data_misc_L5['PTS_FB_DIFF'].rank(ascending=False, method='first')
#### POINTS OFF TURNOVERS
data_misc_L5['PTS_OFF_TOV_DIFF'] = data_misc_L5['PTS_OFF_TOV'] - data_misc_L5['OPP_PTS_OFF_TOV']
data_misc_L5['PTS_OFF_TOV_DIFF_RANK'] = data_misc_L5['PTS_OFF_TOV_DIFF'].rank(ascending=False, method='first')

# Add missing ranking columns for Last 5 games misc stats
data_misc_L5['PTS_PAINT_RANK'] = data_misc_L5['PTS_PAINT'].rank(ascending=False, method='first').astype(int)
data_misc_L5['OPP_PTS_PAINT_RANK'] = data_misc_L5['OPP_PTS_PAINT'].rank(ascending=True, method='first').astype(int)
data_misc_L5['PTS_2ND_CHANCE_RANK'] = data_misc_L5['PTS_2ND_CHANCE'].rank(ascending=False, method='first').astype(int)
data_misc_L5['OPP_PTS_2ND_CHANCE_RANK'] = data_misc_L5['OPP_PTS_2ND_CHANCE'].rank(ascending=True, method='first').astype(int)
data_misc_L5['PTS_FB_RANK'] = data_misc_L5['PTS_FB'].rank(ascending=False, method='first').astype(int)
data_misc_L5['OPP_PTS_FB_RANK'] = data_misc_L5['OPP_PTS_FB'].rank(ascending=True, method='first').astype(int)
data_misc_L5['PTS_OFF_TOV_RANK'] = data_misc_L5['PTS_OFF_TOV'].rank(ascending=False, method='first').astype(int)
data_misc_L5['OPP_PTS_OFF_TOV_RANK'] = data_misc_L5['OPP_PTS_OFF_TOV'].rank(ascending=True, method='first').astype(int)

#LOAD TRADITIONAL DATA
## SEASON
data_trad_season = nba_api.stats.endpoints.LeagueDashTeamStats(
    league_id_nullable='00',
    # last_n_games=None,
    measure_type_detailed_defense='Base',
    pace_adjust='N',
    per_mode_detailed='PerGame',
    season=current_season,
    season_type_all_star=season_type
    ).get_data_frames()[0]

# Add missing ranking columns for traditional stats
data_trad_season['AST_RANK'] = data_trad_season['AST'].rank(ascending=False, method='first').astype(int)
data_trad_season['TOV_RANK'] = data_trad_season['TOV'].rank(ascending=True, method='first').astype(int)
## LAST 5
data_trad_L5 = nba_api.stats.endpoints.LeagueDashTeamStats(
    league_id_nullable='00',
    # last_n_games=None,
    measure_type_detailed_defense='Base',
    pace_adjust='N',
    per_mode_detailed='PerGame',
    season=current_season,
    season_type_all_star=season_type,
    last_n_games=5
    ).get_data_frames()[0]

# Add missing ranking columns for Last 5 games traditional stats
data_trad_L5['AST_RANK'] = data_trad_L5['AST'].rank(ascending=False, method='first').astype(int)
data_trad_L5['TOV_RANK'] = data_trad_L5['TOV'].rank(ascending=True, method='first').astype(int)
## SEASON - STARTERS
data_trad_season_starters = nba_api.stats.endpoints.LeagueDashTeamStats(
    league_id_nullable='00',
    # last_n_games=None,
    measure_type_detailed_defense='Base',
    pace_adjust='N',
    per_mode_detailed='PerGame',
    season=current_season,
    season_type_all_star=season_type,
    starter_bench_nullable='Starters'
    ).get_data_frames()[0]

# Add missing ranking columns for starters
data_trad_season_starters['PTS_RANK'] = data_trad_season_starters['PTS'].rank(ascending=False, method='first').astype(int)
## LAST 5 - STARTERS
data_trad_L5_starters = nba_api.stats.endpoints.LeagueDashTeamStats(
    league_id_nullable='00',
    # last_n_games=None,
    measure_type_detailed_defense='Base',
    pace_adjust='N',
    per_mode_detailed='PerGame',
    season=current_season,
    season_type_all_star=season_type,
    last_n_games=5,
    starter_bench_nullable='Starters'
    ).get_data_frames()[0]

# Add missing ranking columns for Last 5 starters
data_trad_L5_starters['PTS_RANK'] = data_trad_L5_starters['PTS'].rank(ascending=False, method='first').astype(int)
## SEASON - BENCH
data_trad_season_bench = nba_api.stats.endpoints.LeagueDashTeamStats(
    league_id_nullable='00',
    # last_n_games=None,
    measure_type_detailed_defense='Base',
    pace_adjust='N',
    per_mode_detailed='PerGame',
    season=current_season,
    season_type_all_star=season_type,
    starter_bench_nullable='Bench'
    ).get_data_frames()[0]

# Add missing ranking columns for bench
data_trad_season_bench['PTS_RANK'] = data_trad_season_bench['PTS'].rank(ascending=False, method='first').astype(int)
## LAST 5 - BENCH
data_trad_L5_bench = nba_api.stats.endpoints.LeagueDashTeamStats(
    league_id_nullable='00',
    # last_n_games=None,
    measure_type_detailed_defense='Base',
    pace_adjust='N',
    per_mode_detailed='PerGame',
    season=current_season,
    season_type_all_star=season_type,
    last_n_games=5,
    starter_bench_nullable='Bench'
    ).get_data_frames()[0]

# Add missing ranking columns for Last 5 bench
data_trad_L5_bench['PTS_RANK'] = data_trad_L5_bench['PTS'].rank(ascending=False, method='first').astype(int)

#LOAD FOUR FACTORS DATA
##SEASON
data_4F_season = nba_api.stats.endpoints.LeagueDashTeamStats(
    league_id_nullable='00',
    # last_n_games=None,
    measure_type_detailed_defense='Four Factors',
    pace_adjust='N',
    per_mode_detailed='PerGame',
    season=current_season,
    season_type_all_star=season_type
    ).get_data_frames()[0]

# Add missing ranking columns for Four Factors
data_4F_season['OPP_TOV_PCT_RANK'] = data_4F_season['OPP_TOV_PCT'].rank(ascending=True, method='first').astype(int)
## LAST 5 GAMES
data_4F_L5 = nba_api.stats.endpoints.LeagueDashTeamStats(
    league_id_nullable='00',
    # last_n_games=None,
    measure_type_detailed_defense='Four Factors',
    pace_adjust='N',
    per_mode_detailed='PerGame',
    season=current_season,
    season_type_all_star=season_type,
    last_n_games=5
    ).get_data_frames()[0]

# Add missing ranking columns for Last 5 Four Factors
data_4F_L5['OPP_TOV_PCT_RANK'] = data_4F_L5['OPP_TOV_PCT'].rank(ascending=True, method='first').astype(int)

# SHOOTING DATA LOADING
# Team offense shooting stats (use 2024-25 if current season not available)
try:
    team_offense_url = f"https://api.pbpstats.com/get-totals/nba?Season={current_season}&SeasonType={season_type.replace(' ', '+')}&Type=Team"
    team_offense_response = requests.get(team_offense_url)
    team_stats = pd.DataFrame(team_offense_response.json()['multi_row_table_data'])
except:
    team_offense_url = f"https://api.pbpstats.com/get-totals/nba?Season=2024-25&SeasonType={season_type.replace(' ', '+')}&Type=Team"
    team_offense_response = requests.get(team_offense_url)
    team_stats = pd.DataFrame(team_offense_response.json()['multi_row_table_data'])

# Team defense (opponent) shooting stats
try:
    opp_offense_url = f"https://api.pbpstats.com/get-totals/nba?Season={current_season}&SeasonType={season_type.replace(' ', '+')}&Type=Opponent"
    opp_offense_response = requests.get(opp_offense_url)
    opp_team_stats = pd.DataFrame(opp_offense_response.json()['multi_row_table_data'])
except:
    opp_offense_url = f"https://api.pbpstats.com/get-totals/nba?Season=2024-25&SeasonType={season_type.replace(' ', '+')}&Type=Opponent"
    opp_offense_response = requests.get(opp_offense_url)
    opp_team_stats = pd.DataFrame(opp_offense_response.json()['multi_row_table_data'])

# Convert TeamId to int to match NBA API team IDs
team_stats['TeamId'] = team_stats['TeamId'].astype(int)
opp_team_stats['TeamId'] = opp_team_stats['TeamId'].astype(int)

# Calculate per game values and add ranking columns
for df in [team_stats, opp_team_stats]:
    # Total FG (2PT + 3PT)
    df['FGM'] = df['FG2M'] + df['FG3M']
    df['FGA'] = df['FG2A'] + df['FG3A']
    df['FGM_PG'] = round(df['FGM'] / df['GamesPlayed'], 1)
    df['FGA_PG'] = round(df['FGA'] / df['GamesPlayed'], 1)
    df['FG%'] = round(df['FGM'] / df['FGA'], 3)
    # 2PT
    df['FG2M_PG'] = round(df['FG2M'] / df['GamesPlayed'], 1)
    df['FG2A_PG'] = round(df['FG2A'] / df['GamesPlayed'], 1)
    df['2PT%'] = df['Fg2Pct']
    # 3PT
    df['FG3M_PG'] = round(df['FG3M'] / df['GamesPlayed'], 1)
    df['FG3A_PG'] = round(df['FG3A'] / df['GamesPlayed'], 1)
    df['3PT%'] = df['Fg3Pct']
    # FT (calculate FTM from FtPoints which is points from free throws)
    df['FTM'] = df['FtPoints']  # Each FT is 1 point
    df['FTM_PG'] = round(df['FTM'] / df['GamesPlayed'], 1)
    df['FTA_PG'] = round(df['FTA'] / df['GamesPlayed'], 1)
    df['FT%'] = round(df['FTM'] / df['FTA'], 3) if df['FTA'].sum() > 0 else 0

# Add ranking columns for team stats
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

# Add ranking columns for opponent stats (lower is better for defense)
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

# Calculate shooting differentials
shooting_diff_results = team_stats.copy()
for col in ['FGM_PG', 'FGA_PG', 'FG%', 'FG2M_PG', 'FG2A_PG', '2PT%', 'FG3M_PG', 'FG3A_PG', '3PT%', 'FTM_PG', 'FTA_PG', 'FT%']:
    shooting_diff_results[col] = team_stats[col].values - opp_team_stats[col].values

# Add ranking columns for differentials
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

# Add zone shooting stats rankings
for df in [team_stats, opp_team_stats, shooting_diff_results]:
    # Rim shooting
    df['RIM_FREQ_RANK'] = df['AtRimFrequency'].rank(ascending=False, method='first').astype(int)
    df['RIM_FG%_RANK'] = df['AtRimAccuracy'].rank(ascending=False, method='first').astype(int)
    # Short mid-range
    df['SMR_FREQ_RANK'] = df['ShortMidRangeFrequency'].rank(ascending=False, method='first').astype(int)
    df['SMR_FG%_RANK'] = df['ShortMidRangeAccuracy'].rank(ascending=False, method='first').astype(int)
    # Long mid-range
    df['LMR_FREQ_RANK'] = df['LongMidRangeFrequency'].rank(ascending=False, method='first').astype(int)
    df['LMR_FG%_RANK'] = df['LongMidRangeAccuracy'].rank(ascending=False, method='first').astype(int)
    # Corner 3
    df['C3_FREQ_RANK'] = df['Corner3Frequency'].rank(ascending=False, method='first').astype(int)
    df['C3_FG%_RANK'] = df['Corner3Accuracy'].rank(ascending=False, method='first').astype(int)
    # Above the break 3
    df['ATB3_FREQ_RANK'] = df['Arc3Frequency'].rank(ascending=False, method='first').astype(int)
    df['ATB3_FG%_RANK'] = df['Arc3Accuracy'].rank(ascending=False, method='first').astype(int)

#Key base variables
nba_logo = 'https://a.espncdn.com/combiner/i?img=/i/teamlogos/leagues/500/nba.png?w=100&h=100&transparent=true'

#Load in the current NBA standings
standings = nba_api.stats.endpoints.LeagueStandings(league_id='00', season=current_season, season_type='Regular Season').get_data_frames()[0]

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
        
        # Compare date parts only
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

# Default team IDs (will be overridden by UI selection)
# These are placeholders that will be set by the streamlit app
home_id = None
away_id = None
home_logo_link = None
away_logo_link = None
game_title = "Select a matchup"

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
    
    # Pace
    stats['away_team_pace'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_away_id, 'PACE'].values[0]
    stats['away_team_pace_rank'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_away_id, 'PACE_RANK'].values[0]
    stats['l5_away_team_pace'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_away_id, 'PACE'].values[0]
    stats['l5_away_team_pace_rank'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_away_id, 'PACE_RANK'].values[0]
    stats['la_pace'] = round(data_adv_season['PACE'].mean(), 1)
    stats['l5_la_pace'] = round(data_adv_L5['PACE'].mean(), 1)
    stats['home_team_pace'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_home_id, 'PACE'].values[0]
    stats['home_team_pace_rank'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_home_id, 'PACE_RANK'].values[0]
    stats['l5_home_team_pace'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_home_id, 'PACE'].values[0]
    stats['l5_home_team_pace_rank'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_home_id, 'PACE_RANK'].values[0]
    
    # Assists
    stats['away_team_ast'] = data_trad_season.loc[data_trad_season['TEAM_ID'] == selected_away_id, 'AST'].values[0]
    stats['away_team_ast_rank'] = data_trad_season.loc[data_trad_season['TEAM_ID'] == selected_away_id, 'AST_RANK'].values[0]
    stats['l5_away_team_ast'] = data_trad_L5.loc[data_trad_L5['TEAM_ID'] == selected_away_id, 'AST'].values[0]
    stats['l5_away_team_ast_rank'] = data_trad_L5.loc[data_trad_L5['TEAM_ID'] == selected_away_id, 'AST_RANK'].values[0]
    stats['la_ast'] = round(data_trad_season['AST'].mean(), 1)
    stats['l5_la_ast'] = round(data_trad_L5['AST'].mean(), 1)
    stats['home_team_ast'] = data_trad_season.loc[data_trad_season['TEAM_ID'] == selected_home_id, 'AST'].values[0]
    stats['home_team_ast_rank'] = data_trad_season.loc[data_trad_season['TEAM_ID'] == selected_home_id, 'AST_RANK'].values[0]
    stats['l5_home_team_ast'] = data_trad_L5.loc[data_trad_L5['TEAM_ID'] == selected_home_id, 'AST'].values[0]
    stats['l5_home_team_ast_rank'] = data_trad_L5.loc[data_trad_L5['TEAM_ID'] == selected_home_id, 'AST_RANK'].values[0]
    
    # Assist Percentage
    stats['away_team_ast_pct'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_away_id, 'AST_PCT'].values[0]
    stats['away_team_ast_pct_rank'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_away_id, 'AST_PCT_RANK'].values[0]
    stats['l5_away_team_ast_pct'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_away_id, 'AST_PCT'].values[0]
    stats['l5_away_team_ast_pct_rank'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_away_id, 'AST_PCT_RANK'].values[0]
    stats['la_ast_pct'] = round(data_adv_season['AST_PCT'].mean(), 3)
    stats['l5_la_ast_pct'] = round(data_adv_L5['AST_PCT'].mean(), 3)
    stats['home_team_ast_pct'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_home_id, 'AST_PCT'].values[0]
    stats['home_team_ast_pct_rank'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_home_id, 'AST_PCT_RANK'].values[0]
    stats['l5_home_team_ast_pct'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_home_id, 'AST_PCT'].values[0]
    stats['l5_home_team_ast_pct_rank'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_home_id, 'AST_PCT_RANK'].values[0]
    
    # Turnovers
    stats['away_team_tov'] = data_trad_season.loc[data_trad_season['TEAM_ID'] == selected_away_id, 'TOV'].values[0]
    stats['away_team_tov_rank'] = data_trad_season.loc[data_trad_season['TEAM_ID'] == selected_away_id, 'TOV_RANK'].values[0]
    stats['l5_away_team_tov'] = data_trad_L5.loc[data_trad_L5['TEAM_ID'] == selected_away_id, 'TOV'].values[0]
    stats['l5_away_team_tov_rank'] = data_trad_L5.loc[data_trad_L5['TEAM_ID'] == selected_away_id, 'TOV_RANK'].values[0]
    stats['la_tov'] = round(data_trad_season['TOV'].mean(), 1)
    stats['l5_la_tov'] = round(data_trad_L5['TOV'].mean(), 1)
    stats['home_team_tov'] = data_trad_season.loc[data_trad_season['TEAM_ID'] == selected_home_id, 'TOV'].values[0]
    stats['home_team_tov_rank'] = data_trad_season.loc[data_trad_season['TEAM_ID'] == selected_home_id, 'TOV_RANK'].values[0]
    stats['l5_home_team_tov'] = data_trad_L5.loc[data_trad_L5['TEAM_ID'] == selected_home_id, 'TOV'].values[0]
    stats['l5_home_team_tov_rank'] = data_trad_L5.loc[data_trad_L5['TEAM_ID'] == selected_home_id, 'TOV_RANK'].values[0]
    
    # Turnover Percentage
    stats['away_team_tov_pct'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_away_id, 'TM_TOV_PCT'].values[0]
    stats['away_team_tov_pct_rank'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_away_id, 'TM_TOV_PCT_RANK'].values[0]
    stats['l5_away_team_tov_pct'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_away_id, 'TM_TOV_PCT'].values[0]
    stats['l5_away_team_tov_pct_rank'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_away_id, 'TM_TOV_PCT_RANK'].values[0]
    stats['la_tov_pct'] = round(data_adv_season['TM_TOV_PCT'].mean(), 3)
    stats['l5_la_tov_pct'] = round(data_adv_L5['TM_TOV_PCT'].mean(), 3)
    stats['home_team_tov_pct'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_home_id, 'TM_TOV_PCT'].values[0]
    stats['home_team_tov_pct_rank'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_home_id, 'TM_TOV_PCT_RANK'].values[0]
    stats['l5_home_team_tov_pct'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_home_id, 'TM_TOV_PCT'].values[0]
    stats['l5_home_team_tov_pct_rank'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_home_id, 'TM_TOV_PCT_RANK'].values[0]
    
    # Opp. Turnover Percentage
    stats['away_team_opp_tov_pct'] = data_4F_season.loc[data_4F_season['TEAM_ID'] == selected_away_id, 'OPP_TOV_PCT'].values[0]
    stats['away_team_opp_tov_pct_rank'] = data_4F_season.loc[data_4F_season['TEAM_ID'] == selected_away_id, 'OPP_TOV_PCT_RANK'].values[0]
    stats['l5_away_team_opp_tov_pct'] = data_4F_L5.loc[data_4F_L5['TEAM_ID'] == selected_away_id, 'OPP_TOV_PCT'].values[0]
    stats['l5_away_team_opp_tov_pct_rank'] = data_4F_L5.loc[data_4F_L5['TEAM_ID'] == selected_away_id, 'OPP_TOV_PCT_RANK'].values[0]
    stats['la_opp_tov_pct'] = round(data_4F_season['OPP_TOV_PCT'].mean(), 3)
    stats['l5_la_opp_tov_pct'] = round(data_4F_L5['OPP_TOV_PCT'].mean(), 3)
    stats['home_team_opp_tov_pct'] = data_4F_season.loc[data_4F_season['TEAM_ID'] == selected_home_id, 'OPP_TOV_PCT'].values[0]
    stats['home_team_opp_tov_pct_rank'] = data_4F_season.loc[data_4F_season['TEAM_ID'] == selected_home_id, 'OPP_TOV_PCT_RANK'].values[0]
    stats['l5_home_team_opp_tov_pct'] = data_4F_L5.loc[data_4F_L5['TEAM_ID'] == selected_home_id, 'OPP_TOV_PCT'].values[0]
    stats['l5_home_team_opp_tov_pct_rank'] = data_4F_L5.loc[data_4F_L5['TEAM_ID'] == selected_home_id, 'OPP_TOV_PCT_RANK'].values[0]
    
    # AST/TOV Ratio
    stats['away_team_ast_tov'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_away_id, 'AST_TO'].values[0]
    stats['away_team_ast_tov_rank'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_away_id, 'AST_TO_RANK'].values[0]
    stats['l5_away_team_ast_tov'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_away_id, 'AST_TO'].values[0]
    stats['l5_away_team_ast_tov_rank'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_away_id, 'AST_TO_RANK'].values[0]
    stats['la_ast_tov'] = round(data_adv_season['AST_TO'].mean(), 2)
    stats['l5_la_ast_tov'] = round(data_adv_L5['AST_TO'].mean(), 2)
    stats['home_team_ast_tov'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_home_id, 'AST_TO'].values[0]
    stats['home_team_ast_tov_rank'] = data_adv_season.loc[data_adv_season['TEAM_ID'] == selected_home_id, 'AST_TO_RANK'].values[0]
    stats['l5_home_team_ast_tov'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_home_id, 'AST_TO'].values[0]
    stats['l5_home_team_ast_tov_rank'] = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == selected_home_id, 'AST_TO_RANK'].values[0]
    
    # Points off Turnovers - Offense
    stats['away_team_pts_off_tov'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_away_id, 'PTS_OFF_TOV'].values[0]
    stats['away_team_pts_off_tov_rank'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_away_id, 'PTS_OFF_TOV_RANK'].values[0]
    stats['l5_away_team_pts_off_tov'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_away_id, 'PTS_OFF_TOV'].values[0]
    stats['l5_away_team_pts_off_tov_rank'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_away_id, 'PTS_OFF_TOV_RANK'].values[0]
    stats['la_pts_off_tov'] = round(data_misc_season['PTS_OFF_TOV'].mean(), 1)
    stats['l5_la_pts_off_tov'] = round(data_misc_L5['PTS_OFF_TOV'].mean(), 1)
    stats['home_team_pts_off_tov'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_home_id, 'PTS_OFF_TOV'].values[0]
    stats['home_team_pts_off_tov_rank'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_home_id, 'PTS_OFF_TOV_RANK'].values[0]
    stats['l5_home_team_pts_off_tov'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_home_id, 'PTS_OFF_TOV'].values[0]
    stats['l5_home_team_pts_off_tov_rank'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_home_id, 'PTS_OFF_TOV_RANK'].values[0]
    
    # Points off Turnovers - Defense
    stats['away_team_opp_pts_off_tov'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_away_id, 'OPP_PTS_OFF_TOV'].values[0]
    stats['away_team_opp_pts_off_tov_rank'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_away_id, 'OPP_PTS_OFF_TOV_RANK'].values[0]
    stats['l5_away_team_opp_pts_off_tov'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_away_id, 'OPP_PTS_OFF_TOV'].values[0]
    stats['l5_away_team_opp_pts_off_tov_rank'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_away_id, 'OPP_PTS_OFF_TOV_RANK'].values[0]
    stats['la_opp_pts_off_tov'] = round(data_misc_season['OPP_PTS_OFF_TOV'].mean(), 1)
    stats['l5_la_opp_pts_off_tov'] = round(data_misc_L5['OPP_PTS_OFF_TOV'].mean(), 1)
    stats['home_team_opp_pts_off_tov'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_home_id, 'OPP_PTS_OFF_TOV'].values[0]
    stats['home_team_opp_pts_off_tov_rank'] = data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_home_id, 'OPP_PTS_OFF_TOV_RANK'].values[0]
    stats['l5_home_team_opp_pts_off_tov'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_home_id, 'OPP_PTS_OFF_TOV'].values[0]
    stats['l5_home_team_opp_pts_off_tov_rank'] = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_home_id, 'OPP_PTS_OFF_TOV_RANK'].values[0]
    
    # Points off Turnovers - Differential
    stats['away_team_pts_off_tov_diff'] = round(data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_away_id, 'PTS_OFF_TOV_DIFF'].values[0], 1)
    stats['away_team_pts_off_tov_diff_rank'] = int(data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_away_id, 'PTS_OFF_TOV_DIFF_RANK'].values[0])
    stats['l5_away_team_pts_off_tov_diff'] = round(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_away_id, 'PTS_OFF_TOV_DIFF'].values[0], 1)
    stats['l5_away_team_pts_off_tov_diff_rank'] = int(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_away_id, 'PTS_OFF_TOV_DIFF_RANK'].values[0])
    stats['la_pts_off_tov_diff'] = round(data_misc_season['PTS_OFF_TOV_DIFF'].mean(), 1)
    stats['l5_la_pts_off_tov_diff'] = round(data_misc_L5['PTS_OFF_TOV_DIFF'].mean(), 1)
    stats['home_team_pts_off_tov_diff'] = round(data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_home_id, 'PTS_OFF_TOV_DIFF'].values[0], 1)
    stats['home_team_pts_off_tov_diff_rank'] = int(data_misc_season.loc[data_misc_season['TEAM_ID'] == selected_home_id, 'PTS_OFF_TOV_DIFF_RANK'].values[0])
    stats['l5_home_team_pts_off_tov_diff'] = round(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_home_id, 'PTS_OFF_TOV_DIFF'].values[0], 1)
    stats['l5_home_team_pts_off_tov_diff_rank'] = int(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == selected_home_id, 'PTS_OFF_TOV_DIFF_RANK'].values[0])
    
    # Starters Scoring
    stats['away_team_starters_scoring'] = data_trad_season_starters.loc[data_trad_season_starters['TEAM_ID'] == selected_away_id, 'PTS'].values[0]
    stats['away_team_starters_scoring_rank'] = data_trad_season_starters.loc[data_trad_season_starters['TEAM_ID'] == selected_away_id, 'PTS_RANK'].values[0]
    stats['l5_away_team_starters_scoring'] = data_trad_L5_starters.loc[data_trad_L5_starters['TEAM_ID'] == selected_away_id, 'PTS'].values[0]
    stats['l5_away_team_starters_scoring_rank'] = data_trad_L5_starters.loc[data_trad_L5_starters['TEAM_ID'] == selected_away_id, 'PTS_RANK'].values[0]
    stats['la_starters_scoring'] = round(data_trad_season_starters['PTS'].mean(), 1)
    stats['l5_la_starters_scoring'] = round(data_trad_L5_starters['PTS'].mean(), 1)
    stats['home_team_starters_scoring'] = data_trad_season_starters.loc[data_trad_season_starters['TEAM_ID'] == selected_home_id, 'PTS'].values[0]
    stats['home_team_starters_scoring_rank'] = data_trad_season_starters.loc[data_trad_season_starters['TEAM_ID'] == selected_home_id, 'PTS_RANK'].values[0]
    stats['l5_home_team_starters_scoring'] = data_trad_L5_starters.loc[data_trad_L5_starters['TEAM_ID'] == selected_home_id, 'PTS'].values[0]
    stats['l5_home_team_starters_scoring_rank'] = data_trad_L5_starters.loc[data_trad_L5_starters['TEAM_ID'] == selected_home_id, 'PTS_RANK'].values[0]
    
    # Bench Scoring
    stats['away_team_bench_scoring'] = data_trad_season_bench.loc[data_trad_season_bench['TEAM_ID'] == selected_away_id, 'PTS'].values[0]
    stats['away_team_bench_scoring_rank'] = data_trad_season_bench.loc[data_trad_season_bench['TEAM_ID'] == selected_away_id, 'PTS_RANK'].values[0]
    stats['l5_away_team_bench_scoring'] = data_trad_L5_bench.loc[data_trad_L5_bench['TEAM_ID'] == selected_away_id, 'PTS'].values[0]
    stats['l5_away_team_bench_scoring_rank'] = data_trad_L5_bench.loc[data_trad_L5_bench['TEAM_ID'] == selected_away_id, 'PTS_RANK'].values[0]
    stats['la_bench_scoring'] = round(data_trad_season_bench['PTS'].mean(), 1)
    stats['l5_la_bench_scoring'] = round(data_trad_L5_bench['PTS'].mean(), 1)
    stats['home_team_bench_scoring'] = data_trad_season_bench.loc[data_trad_season_bench['TEAM_ID'] == selected_home_id, 'PTS'].values[0]
    stats['home_team_bench_scoring_rank'] = data_trad_season_bench.loc[data_trad_season_bench['TEAM_ID'] == selected_home_id, 'PTS_RANK'].values[0]
    stats['l5_home_team_bench_scoring'] = data_trad_L5_bench.loc[data_trad_L5_bench['TEAM_ID'] == selected_home_id, 'PTS'].values[0]
    stats['l5_home_team_bench_scoring_rank'] = data_trad_L5_bench.loc[data_trad_L5_bench['TEAM_ID'] == selected_home_id, 'PTS_RANK'].values[0]
    
    # ==================== SHOOTING STATS ====================
    # Field Goals Made
    stats['away_team_fgm'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'FGM_PG'].values[0]
    stats['away_team_fgm_rank'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'FGM_RANK'].values[0]
    stats['away_team_opp_fgm'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'FGM_PG'].values[0]
    stats['away_team_opp_fgm_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'FGM_RANK'].values[0]
    stats['away_team_diff_fgm'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'FGM_PG'].values[0], 1)
    stats['away_team_diff_fgm_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'FGM_RANK'].values[0]
    stats['la_fgm'] = round(team_stats['FGM_PG'].mean(), 1)
    stats['home_team_fgm'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'FGM_PG'].values[0]
    stats['home_team_fgm_rank'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'FGM_RANK'].values[0]
    stats['home_team_opp_fgm'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'FGM_PG'].values[0]
    stats['home_team_opp_fgm_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'FGM_RANK'].values[0]
    stats['home_team_diff_fgm'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'FGM_PG'].values[0], 1)
    stats['home_team_diff_fgm_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'FGM_RANK'].values[0]
    
    # Field Goals Attempted
    stats['away_team_fga'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'FGA_PG'].values[0]
    stats['away_team_fga_rank'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'FGA_RANK'].values[0]
    stats['away_team_opp_fga'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'FGA_PG'].values[0]
    stats['away_team_opp_fga_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'FGA_RANK'].values[0]
    stats['away_team_diff_fga'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'FGA_PG'].values[0], 1)
    stats['away_team_diff_fga_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'FGA_RANK'].values[0]
    stats['la_fga'] = round(team_stats['FGA_PG'].mean(), 1)
    stats['home_team_fga'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'FGA_PG'].values[0]
    stats['home_team_fga_rank'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'FGA_RANK'].values[0]
    stats['home_team_opp_fga'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'FGA_PG'].values[0]
    stats['home_team_opp_fga_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'FGA_RANK'].values[0]
    stats['home_team_diff_fga'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'FGA_PG'].values[0], 1)
    stats['home_team_diff_fga_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'FGA_RANK'].values[0]
    
    # Field Goal Percentage
    stats['away_team_fg_pct'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'FG%'].values[0]
    stats['away_team_fg_pct_rank'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'FG%_RANK'].values[0]
    stats['away_team_opp_fg_pct'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'FG%'].values[0]
    stats['away_team_opp_fg_pct_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'FG%_RANK'].values[0]
    stats['away_team_diff_fg_pct'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'FG%'].values[0], 3)
    stats['away_team_diff_fg_pct_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'FG%_RANK'].values[0]
    stats['la_fg_pct'] = round(team_stats['FG%'].mean(), 3)
    stats['home_team_fg_pct'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'FG%'].values[0]
    stats['home_team_fg_pct_rank'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'FG%_RANK'].values[0]
    stats['home_team_opp_fg_pct'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'FG%'].values[0]
    stats['home_team_opp_fg_pct_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'FG%_RANK'].values[0]
    stats['home_team_diff_fg_pct'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'FG%'].values[0], 3)
    stats['home_team_diff_fg_pct_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'FG%_RANK'].values[0]
    
    # 2PT Field Goals Made
    stats['away_team_2pt'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'FG2M_PG'].values[0]
    stats['away_team_2pt_rank'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'FG2M_RANK'].values[0]
    stats['away_team_opp_2pt'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'FG2M_PG'].values[0]
    stats['away_team_opp_2pt_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'FG2M_RANK'].values[0]
    stats['away_team_diff_2pt'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'FG2M_PG'].values[0], 1)
    stats['away_team_diff_2pt_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'FG2M_RANK'].values[0]
    stats['la_2pt'] = round(team_stats['FG2M_PG'].mean(), 1)
    stats['home_team_2pt'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'FG2M_PG'].values[0]
    stats['home_team_2pt_rank'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'FG2M_RANK'].values[0]
    stats['home_team_opp_2pt'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'FG2M_PG'].values[0]
    stats['home_team_opp_2pt_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'FG2M_RANK'].values[0]
    stats['home_team_diff_2pt'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'FG2M_PG'].values[0], 1)
    stats['home_team_diff_2pt_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'FG2M_RANK'].values[0]
    
    # 2PT Field Goals Attempted
    stats['away_team_2pa'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'FG2A_PG'].values[0]
    stats['away_team_2pa_rank'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'FG2A_RANK'].values[0]
    stats['away_team_opp_2pa'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'FG2A_PG'].values[0]
    stats['away_team_opp_2pa_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'FG2A_RANK'].values[0]
    stats['away_team_diff_2pa'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'FG2A_PG'].values[0], 1)
    stats['away_team_diff_2pa_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'FG2A_RANK'].values[0]
    stats['la_2pa'] = round(team_stats['FG2A_PG'].mean(), 1)
    stats['home_team_2pa'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'FG2A_PG'].values[0]
    stats['home_team_2pa_rank'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'FG2A_RANK'].values[0]
    stats['home_team_opp_2pa'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'FG2A_PG'].values[0]
    stats['home_team_opp_2pa_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'FG2A_RANK'].values[0]
    stats['home_team_diff_2pa'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'FG2A_PG'].values[0], 1)
    stats['home_team_diff_2pa_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'FG2A_RANK'].values[0]
    
    # 2PT Field Goal Percentage
    stats['away_team_2pt_pct'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, '2PT%'].values[0]
    stats['away_team_2pt_pct_rank'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, '2PT%_RANK'].values[0]
    stats['away_team_opp_2pt_pct'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, '2PT%'].values[0]
    stats['away_team_opp_2pt_pct_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, '2PT%_RANK'].values[0]
    stats['away_team_diff_2pt_pct'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, '2PT%'].values[0], 3)
    stats['away_team_diff_2pt_pct_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, '2PT%_RANK'].values[0]
    stats['la_2pt_pct'] = round(team_stats['2PT%'].mean(), 3)
    stats['home_team_2pt_pct'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, '2PT%'].values[0]
    stats['home_team_2pt_pct_rank'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, '2PT%_RANK'].values[0]
    stats['home_team_opp_2pt_pct'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, '2PT%'].values[0]
    stats['home_team_opp_2pt_pct_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, '2PT%_RANK'].values[0]
    stats['home_team_diff_2pt_pct'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, '2PT%'].values[0], 3)
    stats['home_team_diff_2pt_pct_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, '2PT%_RANK'].values[0]
    
    # 3PT Field Goals Made
    stats['away_team_3pt'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'FG3M_PG'].values[0]
    stats['away_team_3pt_rank'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'FG3M_RANK'].values[0]
    stats['away_team_opp_3pt'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'FG3M_PG'].values[0]
    stats['away_team_opp_3pt_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'FG3M_RANK'].values[0]
    stats['away_team_diff_3pt'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'FG3M_PG'].values[0], 1)
    stats['away_team_diff_3pt_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'FG3M_RANK'].values[0]
    stats['la_3pt'] = round(team_stats['FG3M_PG'].mean(), 1)
    stats['home_team_3pt'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'FG3M_PG'].values[0]
    stats['home_team_3pt_rank'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'FG3M_RANK'].values[0]
    stats['home_team_opp_3pt'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'FG3M_PG'].values[0]
    stats['home_team_opp_3pt_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'FG3M_RANK'].values[0]
    stats['home_team_diff_3pt'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'FG3M_PG'].values[0], 1)
    stats['home_team_diff_3pt_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'FG3M_RANK'].values[0]
    
    # 3PT Field Goals Attempted
    stats['away_team_3pa'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'FG3A_PG'].values[0]
    stats['away_team_3pa_rank'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'FG3A_RANK'].values[0]
    stats['away_team_opp_3pa'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'FG3A_PG'].values[0]
    stats['away_team_opp_3pa_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'FG3A_RANK'].values[0]
    stats['away_team_diff_3pa'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'FG3A_PG'].values[0], 1)
    stats['away_team_diff_3pa_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'FG3A_RANK'].values[0]
    stats['la_3pa'] = round(team_stats['FG3A_PG'].mean(), 1)
    stats['home_team_3pa'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'FG3A_PG'].values[0]
    stats['home_team_3pa_rank'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'FG3A_RANK'].values[0]
    stats['home_team_opp_3pa'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'FG3A_PG'].values[0]
    stats['home_team_opp_3pa_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'FG3A_RANK'].values[0]
    stats['home_team_diff_3pa'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'FG3A_PG'].values[0], 1)
    stats['home_team_diff_3pa_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'FG3A_RANK'].values[0]
    
    # 3PT Field Goal Percentage
    stats['away_team_3pt_pct'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, '3PT%'].values[0]
    stats['away_team_3pt_pct_rank'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, '3PT%_RANK'].values[0]
    stats['away_team_opp_3pt_pct'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, '3PT%'].values[0]
    stats['away_team_opp_3pt_pct_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, '3PT%_RANK'].values[0]
    stats['away_team_diff_3pt_pct'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, '3PT%'].values[0], 3)
    stats['away_team_diff_3pt_pct_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, '3PT%_RANK'].values[0]
    stats['la_3pt_pct'] = round(team_stats['3PT%'].mean(), 3)
    stats['home_team_3pt_pct'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, '3PT%'].values[0]
    stats['home_team_3pt_pct_rank'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, '3PT%_RANK'].values[0]
    stats['home_team_opp_3pt_pct'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, '3PT%'].values[0]
    stats['home_team_opp_3pt_pct_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, '3PT%_RANK'].values[0]
    stats['home_team_diff_3pt_pct'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, '3PT%'].values[0], 3)
    stats['home_team_diff_3pt_pct_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, '3PT%_RANK'].values[0]
    
    # Free Throws Made
    stats['away_team_ftm'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'FTM_PG'].values[0]
    stats['away_team_ftm_rank'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'FTM_RANK'].values[0]
    stats['away_team_opp_ftm'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'FTM_PG'].values[0]
    stats['away_team_opp_ftm_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'FTM_RANK'].values[0]
    stats['away_team_diff_ftm'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'FTM_PG'].values[0], 1)
    stats['away_team_diff_ftm_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'FTM_RANK'].values[0]
    stats['la_ftm'] = round(team_stats['FTM_PG'].mean(), 1)
    stats['home_team_ftm'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'FTM_PG'].values[0]
    stats['home_team_ftm_rank'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'FTM_RANK'].values[0]
    stats['home_team_opp_ftm'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'FTM_PG'].values[0]
    stats['home_team_opp_ftm_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'FTM_RANK'].values[0]
    stats['home_team_diff_ftm'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'FTM_PG'].values[0], 1)
    stats['home_team_diff_ftm_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'FTM_RANK'].values[0]
    
    # Free Throws Attempted
    stats['away_team_fta'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'FTA_PG'].values[0]
    stats['away_team_fta_rank'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'FTA_RANK'].values[0]
    stats['away_team_opp_fta'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'FTA_PG'].values[0]
    stats['away_team_opp_fta_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'FTA_RANK'].values[0]
    stats['away_team_diff_fta'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'FTA_PG'].values[0], 1)
    stats['away_team_diff_fta_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'FTA_RANK'].values[0]
    stats['la_fta'] = round(team_stats['FTA_PG'].mean(), 1)
    stats['home_team_fta'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'FTA_PG'].values[0]
    stats['home_team_fta_rank'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'FTA_RANK'].values[0]
    stats['home_team_opp_fta'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'FTA_PG'].values[0]
    stats['home_team_opp_fta_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'FTA_RANK'].values[0]
    stats['home_team_diff_fta'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'FTA_PG'].values[0], 1)
    stats['home_team_diff_fta_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'FTA_RANK'].values[0]
    
    # Free Throw Percentage
    stats['away_team_ft_pct'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'FT%'].values[0]
    stats['away_team_ft_pct_rank'] = team_stats.loc[team_stats['TeamId'] == selected_away_id, 'FT%_RANK'].values[0]
    stats['away_team_opp_ft_pct'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'FT%'].values[0]
    stats['away_team_opp_ft_pct_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_away_id, 'FT%_RANK'].values[0]
    stats['away_team_diff_ft_pct'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'FT%'].values[0], 3)
    stats['away_team_diff_ft_pct_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_away_id, 'FT%_RANK'].values[0]
    stats['la_ft_pct'] = round(team_stats['FT%'].mean(), 3)
    stats['home_team_ft_pct'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'FT%'].values[0]
    stats['home_team_ft_pct_rank'] = team_stats.loc[team_stats['TeamId'] == selected_home_id, 'FT%_RANK'].values[0]
    stats['home_team_opp_ft_pct'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'FT%'].values[0]
    stats['home_team_opp_ft_pct_rank'] = opp_team_stats.loc[opp_team_stats['TeamId'] == selected_home_id, 'FT%_RANK'].values[0]
    stats['home_team_diff_ft_pct'] = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'FT%'].values[0], 3)
    stats['home_team_diff_ft_pct_rank'] = shooting_diff_results.loc[shooting_diff_results['TeamId'] == selected_home_id, 'FT%_RANK'].values[0]
    
    # ==================== ZONE SHOOTING STATS ====================
    # Rim Shooting - Frequency
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
    
    # Rim Shooting - Accuracy
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
