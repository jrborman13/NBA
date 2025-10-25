import nba_api.stats.endpoints
import requests
import json
import pandas as pd
import nba_api

current_season = '2025-26'
season_type = 'Regular Season'
opponent_id = 1610612760

#ADVANCED DATA LOADING
##SEASON
data_adv_season = nba_api.stats.endpoints.LeagueDashTeamStats(
    # last_n_games=None,
    measure_type_detailed_defense='Advanced',
    pace_adjust='N',
    per_mode_detailed='PerGame',
    season=current_season,
    season_type_all_star=season_type
    ).get_data_frames()[0]
##LAST 5 GAMES
data_adv_L5 = nba_api.stats.endpoints.LeagueDashTeamStats(
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

##LAST 5 GAMES
data_misc_L5 = nba_api.stats.endpoints.LeagueDashTeamStats(
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

#LOAD TRADITIONAL DATA
## SEASON
data_trad_season = nba_api.stats.endpoints.LeagueDashTeamStats(
    # last_n_games=None,
    measure_type_detailed_defense='Base',
    pace_adjust='N',
    per_mode_detailed='PerGame',
    season=current_season,
    season_type_all_star=season_type
    ).get_data_frames()[0]
## LAST 5
data_trad_L5 = nba_api.stats.endpoints.LeagueDashTeamStats(
    # last_n_games=None,
    measure_type_detailed_defense='Base',
    pace_adjust='N',
    per_mode_detailed='PerGame',
    season=current_season,
    season_type_all_star=season_type,
    last_n_games=5
    ).get_data_frames()[0]
## SEASON - STARTERS
data_trad_season_starters = nba_api.stats.endpoints.LeagueDashTeamStats(
    # last_n_games=None,
    measure_type_detailed_defense='Base',
    pace_adjust='N',
    per_mode_detailed='PerGame',
    season=current_season,
    season_type_all_star=season_type,
    starter_bench_nullable='Starters'
    ).get_data_frames()[0]
## LAST 5 - STARTERS
data_trad_L5_starters = nba_api.stats.endpoints.LeagueDashTeamStats(
    # last_n_games=None,
    measure_type_detailed_defense='Base',
    pace_adjust='N',
    per_mode_detailed='PerGame',
    season=current_season,
    season_type_all_star=season_type,
    last_n_games=5,
    starter_bench_nullable='Starters'
    ).get_data_frames()[0]
## SEASON - BENCH
data_trad_season_bench = nba_api.stats.endpoints.LeagueDashTeamStats(
    # last_n_games=None,
    measure_type_detailed_defense='Base',
    pace_adjust='N',
    per_mode_detailed='PerGame',
    season=current_season,
    season_type_all_star=season_type,
    starter_bench_nullable='Bench'
    ).get_data_frames()[0]
## LAST 5 - BENCH
data_trad_L5_bench = nba_api.stats.endpoints.LeagueDashTeamStats(
    # last_n_games=None,
    measure_type_detailed_defense='Base',
    pace_adjust='N',
    per_mode_detailed='PerGame',
    season=current_season,
    season_type_all_star=season_type,
    last_n_games=5,
    starter_bench_nullable='Bench'
    ).get_data_frames()[0]

#LOAD FOUR FACTORS DATA
##SEASON
data_4F_season = nba_api.stats.endpoints.LeagueDashTeamStats(
    # last_n_games=None,
    measure_type_detailed_defense='Four Factors',
    pace_adjust='N',
    per_mode_detailed='PerGame',
    season=current_season,
    season_type_all_star=season_type
    ).get_data_frames()[0]
## LAST 5 GAMES
data_4F_L5 = nba_api.stats.endpoints.LeagueDashTeamStats(
    # last_n_games=None,
    measure_type_detailed_defense='Four Factors',
    pace_adjust='N',
    per_mode_detailed='PerGame',
    season=current_season,
    season_type_all_star=season_type,
    last_n_games=5
    ).get_data_frames()[0]

#Key base variables
wolves_id = data_adv_season.loc[data_adv_season['TEAM_NAME'] == 'Minnesota Timberwolves', 'TEAM_ID'].values[0]
# wolves_id = '1610612750'
logo_link = f'https://cdn.nba.com/logos/nba/{wolves_id}/primary/L/logo.svg'
timberwolves = 'Minnesota Timberwolves'
nba_logo = 'https://a.espncdn.com/combiner/i?img=/i/teamlogos/leagues/500/nba.png?w=100&h=100&transparent=true'

#Load in the current NBA standings
standings = nba_api.stats.endpoints.LeagueStandings(league_id='00', season=current_season, season_type='Regular Season').get_data_frames()[0]

#Import today's games
from nba_api.live.nba.endpoints import scoreboard
games = scoreboard.ScoreBoard()
games_json = json.loads(games.get_json())
todays_games = games_json['scoreboard']['games']

#Search for the Wolves game
target_key = 'gameCode'
partial_match = 'MIN'

target_index = None  # Initialize to None

for index, dictionary in enumerate(todays_games):
    if target_key in dictionary and partial_match in dictionary[target_key]:
        target_index = index
        break  # Stop after finding first match

print(target_index)
print(todays_games[target_index])

try:
    if todays_games[target_index]['homeTeam']['teamId'] == wolves_id:
        game_id = todays_games[target_index]['gameId']
        home_or_away = 'Home'
        home_id = wolves_id
        home_logo_link = f'https://cdn.nba.com/logos/nba/{home_id}/primary/L/logo.svg'
        # away_id = todays_games[target_index]['awayTeam']['teamId']
        away_id = opponent_id
        away_logo_link = f'https://cdn.nba.com/logos/nba/{away_id}/primary/L/logo.svg'
        opponent_name = data_adv_season.loc[data_adv_season['TEAM_ID'] == away_id, 'TEAM_NAME'].values[0]
        game_title = f'{opponent_name} at Minnesota Timberwolves'
    else:
        game_id = todays_games[target_index]['gameId']
        home_or_away = 'Away'
        away_id = wolves_id
        away_logo_link = f'https://cdn.nba.com/logos/nba/{away_id}/primary/L/logo.svg'
        # home_id = todays_games[target_index]['homeTeam']['teamId']
        home_id = opponent_id
        home_logo_link = f'https://cdn.nba.com/logos/nba/{home_id}/primary/L/logo.svg'
        opponent_name = data_adv_season.loc[data_adv_season['TEAM_ID'] == home_id, 'TEAM_NAME'].values[0]
        game_title = f'Minnesota Timberwolves at {opponent_name}'
except:
    home_or_away = 'Away'
    away_id = wolves_id
    away_logo_link = f'https://cdn.nba.com/logos/nba/{away_id}/primary/L/logo.svg'
    # home_id = todays_games[target_index]['homeTeam']['teamId']
    home_id = opponent_id
    home_logo_link = f'https://cdn.nba.com/logos/nba/{home_id}/primary/L/logo.svg'
    opponent_name = data_adv_season.loc[data_adv_season['TEAM_ID'] == home_id, 'TEAM_NAME'].values[0]
    game_title = f'Minnesota Timberwolves at {opponent_name}'

# print(game_title, todays_games)

#Record and Seed
## Away Team
away_team_record = standings.loc[standings['TeamID'] == away_id, 'Record'].values[0]
away_team_seed = standings.loc[standings['TeamID'] == away_id, 'PlayoffRank'].values[0]
away_team_division_seed = standings.loc[standings['TeamID'] == away_id, 'DivisionRank'].values[0]
## Home Team
home_team_record = standings.loc[standings['TeamID'] == home_id, 'Record'].values[0]
home_team_seed = standings.loc[standings['TeamID'] == home_id, 'PlayoffRank'].values[0]
home_team_division_seed = standings.loc[standings['TeamID'] == home_id, 'DivisionRank'].values[0]

#Offensive Ratings
## Away Team
away_team_ortg = data_adv_season.loc[data_adv_season['TEAM_ID'] == away_id, 'OFF_RATING'].values[0]
away_team_ortg_rank = data_adv_season.loc[data_adv_season['TEAM_ID'] == away_id, 'OFF_RATING_RANK'].values[0]
l5_away_team_ortg = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == away_id, 'OFF_RATING'].values[0]
l5_away_team_ortg_rank = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == away_id, 'OFF_RATING_RANK'].values[0]
##League Average
la_ortg = round(data_adv_season['OFF_RATING'].mean(), 1)
l5_la_ortg = round(data_adv_L5['OFF_RATING'].mean(), 1)
## Home Team
home_team_ortg = data_adv_season.loc[data_adv_season['TEAM_ID'] == home_id, 'OFF_RATING'].values[0]
home_team_ortg_rank = data_adv_season.loc[data_adv_season['TEAM_ID'] == home_id, 'OFF_RATING_RANK'].values[0]
l5_home_team_ortg = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == home_id, 'OFF_RATING'].values[0]
l5_home_team_ortg_rank = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == home_id, 'OFF_RATING_RANK'].values[0]

#Defensive Ratings
## Away Team
away_team_drtg = data_adv_season.loc[data_adv_season['TEAM_ID'] == away_id, 'DEF_RATING'].values[0]
away_team_drtg_rank = data_adv_season.loc[data_adv_season['TEAM_ID'] == away_id, 'DEF_RATING_RANK'].values[0]
l5_away_team_drtg = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == away_id, 'DEF_RATING'].values[0]
l5_away_team_drtg_rank = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == away_id, 'DEF_RATING_RANK'].values[0]
##League Average
la_drtg = round(data_adv_season['DEF_RATING'].mean(), 1)
l5_la_drtg = round(data_adv_L5['DEF_RATING'].mean(), 1)
## Home Team
home_team_drtg = data_adv_season.loc[data_adv_season['TEAM_ID'] == home_id, 'DEF_RATING'].values[0]
home_team_drtg_rank = data_adv_season.loc[data_adv_season['TEAM_ID'] == home_id, 'DEF_RATING_RANK'].values[0]
l5_home_team_drtg = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == home_id, 'DEF_RATING'].values[0]
l5_home_team_drtg_rank = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == home_id, 'DEF_RATING_RANK'].values[0]

#Net Ratings
## Away Team
away_team_net = data_adv_season.loc[data_adv_season['TEAM_ID'] == away_id, 'NET_RATING'].values[0]
away_team_net_rank = data_adv_season.loc[data_adv_season['TEAM_ID'] == away_id, 'NET_RATING_RANK'].values[0]
l5_away_team_net = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == away_id, 'NET_RATING'].values[0]
l5_away_team_net_rank = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == away_id, 'NET_RATING_RANK'].values[0]
##League Average
la_net = 0
l5_la_net = 0
## Home Team
home_team_net = data_adv_season.loc[data_adv_season['TEAM_ID'] == home_id, 'NET_RATING'].values[0]
home_team_net_rank = data_adv_season.loc[data_adv_season['TEAM_ID'] == home_id, 'NET_RATING_RANK'].values[0]
l5_home_team_net = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == home_id, 'NET_RATING'].values[0]
l5_home_team_net_rank = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == home_id, 'NET_RATING_RANK'].values[0]

#REBOUND PERCENTAGES

#DREB%
## Away Team
away_team_dreb = data_adv_season.loc[data_adv_season['TEAM_ID'] == away_id, 'DREB_PCT'].values[0]
away_team_dreb_rank = data_adv_season.loc[data_adv_season['TEAM_ID'] == away_id, 'DREB_PCT_RANK'].values[0]
l5_away_team_dreb = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == away_id, 'DREB_PCT'].values[0]
l5_away_team_dreb_rank = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == away_id, 'DREB_PCT_RANK'].values[0]
## League Average
la_dreb = round(data_adv_season['DREB_PCT'].mean(), 3)
l5_la_dreb = round(data_adv_L5['DREB_PCT'].mean(), 3)
## Home Team
home_team_dreb = data_adv_season.loc[data_adv_season['TEAM_ID'] == home_id, 'DREB_PCT'].values[0]
home_team_dreb_rank = data_adv_season.loc[data_adv_season['TEAM_ID'] == home_id, 'DREB_PCT_RANK'].values[0]
l5_home_team_dreb = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == home_id, 'DREB_PCT'].values[0]
l5_home_team_dreb_rank = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == home_id, 'DREB_PCT_RANK'].values[0]

#OREB%
## Away Team
away_team_oreb = data_adv_season.loc[data_adv_season['TEAM_ID'] == away_id, 'OREB_PCT'].values[0]
away_team_oreb_rank = data_adv_season.loc[data_adv_season['TEAM_ID'] == away_id, 'OREB_PCT_RANK'].values[0]
l5_away_team_oreb = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == away_id, 'OREB_PCT'].values[0]
l5_away_team_oreb_rank = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == away_id, 'OREB_PCT_RANK'].values[0]
## League Average
la_oreb = round(data_adv_season['OREB_PCT'].mean(), 3)
l5_la_oreb = round(data_adv_L5['OREB_PCT'].mean(), 3)
## Home Team
home_team_oreb = data_adv_season.loc[data_adv_season['TEAM_ID'] == home_id, 'OREB_PCT'].values[0]
home_team_oreb_rank = data_adv_season.loc[data_adv_season['TEAM_ID'] == home_id, 'OREB_PCT_RANK'].values[0]
l5_home_team_oreb = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == home_id, 'OREB_PCT'].values[0]
l5_home_team_oreb_rank = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == home_id, 'OREB_PCT_RANK'].values[0]

#REB%
## Away Team
away_team_reb = data_adv_season.loc[data_adv_season['TEAM_ID'] == away_id, 'REB_PCT'].values[0]
away_team_reb_rank = data_adv_season.loc[data_adv_season['TEAM_ID'] == away_id, 'REB_PCT_RANK'].values[0]
l5_away_team_reb = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == away_id, 'REB_PCT'].values[0]
l5_away_team_reb_rank = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == away_id, 'REB_PCT_RANK'].values[0]
## League Average
la_reb = round(data_adv_season['REB_PCT'].mean(), 3)
l5_la_reb = round(data_adv_L5['REB_PCT'].mean(), 3)
## Home Team
home_team_reb = data_adv_season.loc[data_adv_season['TEAM_ID'] == home_id, 'REB_PCT'].values[0]
home_team_reb_rank = data_adv_season.loc[data_adv_season['TEAM_ID'] == home_id, 'REB_PCT_RANK'].values[0]
l5_home_team_reb = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == home_id, 'REB_PCT'].values[0]
l5_home_team_reb_rank = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == home_id, 'REB_PCT_RANK'].values[0]

#POINTS IN THE PAINT

#OFFENSE
## Away Team
away_team_pitp_off = data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'PTS_PAINT'].values[0]
away_team_pitp_off_rank = data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'PTS_PAINT_RANK'].values[0]
l5_away_team_pitp_off = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'PTS_PAINT'].values[0]
l5_away_team_pitp_off_rank = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'PTS_PAINT_RANK'].values[0]
## League Average
la_pitp_off = round(data_misc_season['PTS_PAINT'].mean(), 1)
l5_la_pitp_off = round(data_misc_L5['PTS_PAINT'].mean(), 1)
## Home Team
home_team_pitp_off = data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'PTS_PAINT'].values[0]
home_team_pitp_off_rank = data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'PTS_PAINT_RANK'].values[0]
l5_home_team_pitp_off = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'PTS_PAINT'].values[0]
l5_home_team_pitp_off_rank = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'PTS_PAINT_RANK'].values[0]

#DEFENSE
## Away Team
away_team_pitp_def = data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'OPP_PTS_PAINT'].values[0]
away_team_pitp_def_rank = data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'OPP_PTS_PAINT_RANK'].values[0]
l5_away_team_pitp_def = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'OPP_PTS_PAINT'].values[0]
l5_away_team_pitp_def_rank = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'OPP_PTS_PAINT_RANK'].values[0]
## League Average
la_pitp_def = round(data_misc_season['OPP_PTS_PAINT'].mean(), 1)
l5_la_pitp_def = round(data_misc_L5['OPP_PTS_PAINT'].mean(), 1)
## Home Team
home_team_pitp_def = data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'OPP_PTS_PAINT'].values[0]
home_team_pitp_def_rank = data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'OPP_PTS_PAINT_RANK'].values[0]
l5_home_team_pitp_def = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'OPP_PTS_PAINT'].values[0]
l5_home_team_pitp_def_rank = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'OPP_PTS_PAINT_RANK'].values[0]

#DIFFERENCE
## Away Team
away_team_pitp_diff = round(data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'PTS_PAINT_DIFF'].values[0], 1)
away_team_pitp_diff_rank = int(data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'PTS_PAINT_DIFF_RANK'].values[0])
l5_away_team_pitp_diff = round(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'PTS_PAINT_DIFF'].values[0], 1)
l5_away_team_pitp_diff_rank = int(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'PTS_PAINT_DIFF_RANK'].values[0])
## League Average
la_pitp_diff = round(data_misc_season['PTS_PAINT_DIFF'].mean(), 1)
l5_la_pitp_diff = round(data_misc_L5['PTS_PAINT_DIFF'].mean(), 1)
## Home Team
home_team_pitp_diff = round(data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'PTS_PAINT_DIFF'].values[0], 1)
home_team_pitp_diff_rank = int(data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'PTS_PAINT_DIFF_RANK'].values[0])
l5_home_team_pitp_diff = round(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'PTS_PAINT_DIFF'].values[0], 1)
l5_home_team_pitp_diff_rank = int(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'PTS_PAINT_DIFF_RANK'].values[0])

#2ND CHANCE POINTS

#OFFENSE
## Away Team
away_team_2c_off = data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'PTS_2ND_CHANCE'].values[0]
away_team_2c_off_rank = data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'PTS_2ND_CHANCE_RANK'].values[0]
l5_away_team_2c_off = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'PTS_2ND_CHANCE'].values[0]
l5_away_team_2c_off_rank = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'PTS_2ND_CHANCE_RANK'].values[0]
##League Average
la_2c_off = round(data_misc_season['PTS_2ND_CHANCE'].mean(), 1)
l5_la_2c_off = round(data_misc_L5['PTS_2ND_CHANCE'].mean(), 1)
## Home Team
home_team_2c_off = data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'PTS_2ND_CHANCE'].values[0]
home_team_2c_off_rank = data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'PTS_2ND_CHANCE_RANK'].values[0]
l5_home_team_2c_off = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'PTS_2ND_CHANCE'].values[0]
l5_home_team_2c_off_rank = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'PTS_2ND_CHANCE_RANK'].values[0]

#DEFENSE
## Away Team
away_team_2c_def = data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'OPP_PTS_2ND_CHANCE'].values[0]
away_team_2c_def_rank = data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'OPP_PTS_2ND_CHANCE_RANK'].values[0]
l5_away_team_2c_def = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'OPP_PTS_2ND_CHANCE'].values[0]
l5_away_team_2c_def_rank = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'OPP_PTS_2ND_CHANCE_RANK'].values[0]
##League Average
la_2c_def = round(data_misc_season['OPP_PTS_2ND_CHANCE'].mean(), 1)
l5_la_2c_def = round(data_misc_L5['OPP_PTS_2ND_CHANCE'].mean(), 1)
## Home Team
home_team_2c_def = data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'OPP_PTS_2ND_CHANCE'].values[0]
home_team_2c_def_rank = data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'OPP_PTS_2ND_CHANCE_RANK'].values[0]
l5_home_team_2c_def = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'OPP_PTS_2ND_CHANCE'].values[0]
l5_home_team_2c_def_rank = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'OPP_PTS_2ND_CHANCE_RANK'].values[0]

#DIFFERENCE
## Away Team
away_team_2c_diff = round(data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'PTS_2ND_CHANCE_DIFF'].values[0], 1)
away_team_2c_diff_rank = int(data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'PTS_2ND_CHANCE_DIFF_RANK'].values[0])
l5_away_team_2c_diff = round(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'PTS_2ND_CHANCE_DIFF'].values[0], 1)
l5_away_team_2c_diff_rank = int(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'PTS_2ND_CHANCE_DIFF_RANK'].values[0])
## League Average
la_2c_diff = round(data_misc_season['PTS_2ND_CHANCE_DIFF'].mean(), 1)
l5_la_2c_diff = round(data_misc_L5['PTS_2ND_CHANCE_DIFF'].mean(), 1)
## Home Team
home_team_2c_diff = round(data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'PTS_2ND_CHANCE_DIFF'].values[0], 1)
home_team_2c_diff_rank = int(data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'PTS_2ND_CHANCE_DIFF_RANK'].values[0])
l5_home_team_2c_diff = round(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'PTS_2ND_CHANCE_DIFF'].values[0], 1)
l5_home_team_2c_diff_rank = int(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'PTS_2ND_CHANCE_DIFF_RANK'].values[0])

#FAST BREAK POINTS

#OFFENSE
## Away Team
away_team_fb_off = data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'PTS_FB'].values[0]
away_team_fb_off_rank = data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'PTS_FB_RANK'].values[0]
l5_away_team_fb_off = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'PTS_FB'].values[0]
l5_away_team_fb_off_rank = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'PTS_FB_RANK'].values[0]
##League Average
la_fb_off = round(data_misc_season['PTS_FB'].mean(), 1)
l5_la_fb_off = round(data_misc_L5['PTS_FB'].mean(), 1)
## Home Team
home_team_fb_off = data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'PTS_FB'].values[0]
home_team_fb_off_rank = data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'PTS_FB_RANK'].values[0]
l5_home_team_fb_off = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'PTS_FB'].values[0]
l5_home_team_fb_off_rank = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'PTS_FB_RANK'].values[0]

#DEFENSE
## Away Team
away_team_fb_def = data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'OPP_PTS_FB'].values[0]
away_team_fb_def_rank = data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'OPP_PTS_FB_RANK'].values[0]
l5_away_team_fb_def = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'OPP_PTS_FB'].values[0]
l5_away_team_fb_def_rank = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'OPP_PTS_FB_RANK'].values[0]
##League Average
la_fb_def = round(data_misc_season['OPP_PTS_FB'].mean(), 1)
l5_la_fb_def = round(data_misc_L5['OPP_PTS_FB'].mean(), 1)
## Home Team
home_team_fb_def = data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'OPP_PTS_FB'].values[0]
home_team_fb_def_rank = data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'OPP_PTS_FB_RANK'].values[0]
l5_home_team_fb_def = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'OPP_PTS_FB'].values[0]
l5_home_team_fb_def_rank = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'OPP_PTS_FB_RANK'].values[0]

#DIFFERENCE
## Away Team
away_team_fb_diff = round(data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'PTS_FB_DIFF'].values[0], 1)
away_team_fb_diff_rank = int(data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'PTS_FB_DIFF_RANK'].values[0])
l5_away_team_fb_diff = round(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'PTS_FB_DIFF'].values[0], 1)
l5_away_team_fb_diff_rank = int(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'PTS_FB_DIFF_RANK'].values[0])
## League Average
la_fb_diff = round(data_misc_season['PTS_FB_DIFF'].mean(), 1)
l5_la_fb_diff = round(data_misc_L5['PTS_FB_DIFF'].mean(), 1)
## Home Team
home_team_fb_diff = round(data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'PTS_FB_DIFF'].values[0], 1)
home_team_fb_diff_rank = int(data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'PTS_FB_DIFF_RANK'].values[0])
l5_home_team_fb_diff = round(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'PTS_FB_DIFF'].values[0], 1)
l5_home_team_fb_diff_rank = int(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'PTS_FB_DIFF_RANK'].values[0])

#PLAYMAKING STATS

#PACE
## Away Team
away_team_pace = data_adv_season.loc[data_adv_season['TEAM_ID'] == away_id, 'PACE'].values[0]
away_team_pace_rank = data_adv_season.loc[data_adv_season['TEAM_ID'] == away_id, 'PACE_RANK'].values[0]
l5_away_team_pace = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == away_id, 'PACE'].values[0]
l5_away_team_pace_rank = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == away_id, 'PACE_RANK'].values[0]

## League Average
la_pace = round(data_adv_season['PACE'].mean(), 1)
l5_la_pace = round(data_adv_L5['PACE'].mean(), 1)

## Home Team
home_team_pace = data_adv_season.loc[data_adv_season['TEAM_ID'] == home_id, 'PACE'].values[0]
home_team_pace_rank = data_adv_season.loc[data_adv_season['TEAM_ID'] == home_id, 'PACE_RANK'].values[0]
l5_home_team_pace = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == home_id, 'PACE'].values[0]
l5_home_team_pace_rank = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == home_id, 'PACE_RANK'].values[0]

#ASSISTS
## Away Team
away_team_ast = data_trad_season.loc[data_trad_season['TEAM_ID'] == away_id, 'AST'].values[0]
away_team_ast_rank = data_trad_season.loc[data_trad_season['TEAM_ID'] == away_id, 'AST_RANK'].values[0]
l5_away_team_ast = data_trad_L5.loc[data_trad_L5['TEAM_ID'] == away_id, 'AST'].values[0]
l5_away_team_ast_rank = data_trad_L5.loc[data_trad_L5['TEAM_ID'] == away_id, 'AST_RANK'].values[0]

## League Average
la_ast = round(data_trad_season['AST'].mean(), 1)
l5_la_ast = round(data_trad_L5['AST'].mean(), 1)

## Home Team
home_team_ast = data_trad_season.loc[data_trad_season['TEAM_ID'] == home_id, 'AST'].values[0]
home_team_ast_rank = data_trad_season.loc[data_trad_season['TEAM_ID'] == home_id, 'AST_RANK'].values[0]
l5_home_team_ast = data_trad_L5.loc[data_trad_L5['TEAM_ID'] == home_id, 'AST'].values[0]
l5_home_team_ast_rank = data_trad_L5.loc[data_trad_L5['TEAM_ID'] == home_id, 'AST_RANK'].values[0]

#ASSIST PERCENTAGE
## Away Team
away_team_ast_pct = data_adv_season.loc[data_adv_season['TEAM_ID'] == away_id, 'AST_PCT'].values[0]
away_team_ast_pct_rank = data_adv_season.loc[data_trad_season['TEAM_ID'] == away_id, 'AST_PCT_RANK'].values[0]
l5_away_team_ast_pct = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == away_id, 'AST_PCT'].values[0]
l5_away_team_ast_pct_rank = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == away_id, 'AST_PCT_RANK'].values[0]

## League Average
la_ast_pct = round(data_adv_season['AST_PCT'].mean(), 3)
l5_la_ast_pct = round(data_adv_L5['AST_PCT'].mean(), 3)

## Home Team
home_team_ast_pct = data_adv_season.loc[data_adv_season['TEAM_ID'] == home_id, 'AST_PCT'].values[0]
home_team_ast_pct_rank = data_adv_season.loc[data_adv_season['TEAM_ID'] == home_id, 'AST_PCT_RANK'].values[0]
l5_home_team_ast_pct = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == home_id, 'AST_PCT'].values[0]
l5_home_team_ast_pct_rank = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == home_id, 'AST_PCT_RANK'].values[0]

#TURNOVERS
## Away Team
away_team_tov = data_trad_season.loc[data_trad_season['TEAM_ID'] == away_id, 'TOV'].values[0]
away_team_tov_rank = data_trad_season.loc[data_trad_season['TEAM_ID'] == away_id, 'TOV_RANK'].values[0]
l5_away_team_tov = data_trad_L5.loc[data_trad_L5['TEAM_ID'] == away_id, 'TOV'].values[0]
l5_away_team_tov_rank = data_trad_L5.loc[data_trad_L5['TEAM_ID'] == away_id, 'TOV_RANK'].values[0]

## League Average
la_tov = round(data_trad_season['TOV'].mean(), 1)
l5_la_tov = round(data_trad_L5['TOV'].mean(), 1)

## Home Team
home_team_tov = data_trad_season.loc[data_trad_season['TEAM_ID'] == home_id, 'TOV'].values[0]
home_team_tov_rank = data_trad_season.loc[data_trad_season['TEAM_ID'] == home_id, 'TOV_RANK'].values[0]
l5_home_team_tov = data_trad_L5.loc[data_trad_L5['TEAM_ID'] == home_id, 'TOV'].values[0]
l5_home_team_tov_rank = data_trad_L5.loc[data_trad_L5['TEAM_ID'] == home_id, 'TOV_RANK'].values[0]

#TURNOVER PERCENTAGE
## Away Team
away_team_tov_pct = data_adv_season.loc[data_adv_season['TEAM_ID'] == away_id, 'TM_TOV_PCT'].values[0]
away_team_tov_pct_rank = data_adv_season.loc[data_trad_season['TEAM_ID'] == away_id, 'TM_TOV_PCT_RANK'].values[0]
l5_away_team_tov_pct = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == away_id, 'TM_TOV_PCT'].values[0]
l5_away_team_tov_pct_rank = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == away_id, 'TM_TOV_PCT_RANK'].values[0]

## League Average
la_tov_pct = round(data_adv_season['TM_TOV_PCT'].mean(), 3)
# print(la_tov_pct)
l5_la_tov_pct = round(data_adv_L5['TM_TOV_PCT'].mean(), 3)

## Home Team
home_team_tov_pct = data_adv_season.loc[data_adv_season['TEAM_ID'] == home_id, 'TM_TOV_PCT'].values[0]
home_team_tov_pct_rank = data_adv_season.loc[data_adv_season['TEAM_ID'] == home_id, 'TM_TOV_PCT_RANK'].values[0]
l5_home_team_tov_pct = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == home_id, 'TM_TOV_PCT'].values[0]
l5_home_team_tov_pct_rank = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == home_id, 'TM_TOV_PCT_RANK'].values[0]

#OPP. TURNOVER PERCENTAGE
## Away Team
away_team_opp_tov_pct = data_4F_season.loc[data_4F_season['TEAM_ID'] == away_id, 'OPP_TOV_PCT'].values[0]
away_team_opp_tov_pct_rank = data_4F_season.loc[data_trad_season['TEAM_ID'] == away_id, 'OPP_TOV_PCT_RANK'].values[0]
l5_away_team_opp_tov_pct = data_4F_L5.loc[data_4F_L5['TEAM_ID'] == away_id, 'OPP_TOV_PCT'].values[0]
l5_away_team_opp_tov_pct_rank = data_4F_L5.loc[data_4F_L5['TEAM_ID'] == away_id, 'OPP_TOV_PCT_RANK'].values[0]

## League Average
la_opp_tov_pct = round(data_4F_season['OPP_TOV_PCT'].mean(), 3)
l5_la_opp_tov_pct = round(data_4F_L5['OPP_TOV_PCT'].mean(), 3)

## Home Team
home_team_opp_tov_pct = data_4F_season.loc[data_4F_season['TEAM_ID'] == home_id, 'OPP_TOV_PCT'].values[0]
home_team_opp_tov_pct_rank = data_4F_season.loc[data_4F_season['TEAM_ID'] == home_id, 'OPP_TOV_PCT_RANK'].values[0]
l5_home_team_opp_tov_pct = data_4F_L5.loc[data_4F_L5['TEAM_ID'] == home_id, 'OPP_TOV_PCT'].values[0]
l5_home_team_opp_tov_pct_rank = data_4F_L5.loc[data_4F_L5['TEAM_ID'] == home_id, 'OPP_TOV_PCT_RANK'].values[0]

#AST/TOV RATIO
## Away Team
away_team_ast_tov = data_adv_season.loc[data_adv_season['TEAM_ID'] == away_id, 'AST_TO'].values[0]
away_team_ast_tov_rank = data_adv_season.loc[data_trad_season['TEAM_ID'] == away_id, 'AST_TO_RANK'].values[0]
l5_away_team_ast_tov = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == away_id, 'AST_TO'].values[0]
l5_away_team_ast_tov_rank = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == away_id, 'AST_TO_RANK'].values[0]

## League Average
la_ast_tov = round(data_adv_season['AST_TO'].mean(), 2)
l5_la_ast_tov = round(data_adv_L5['AST_TO'].mean(), 2)

## Home Team
home_team_ast_tov = data_adv_season.loc[data_adv_season['TEAM_ID'] == home_id, 'AST_TO'].values[0]
home_team_ast_tov_rank = data_adv_season.loc[data_adv_season['TEAM_ID'] == home_id, 'AST_TO_RANK'].values[0]
l5_home_team_ast_tov = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == home_id, 'AST_TO'].values[0]
l5_home_team_ast_tov_rank = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == home_id, 'AST_TO_RANK'].values[0]

#POINTS OFF TURNOVERS

#OFFENSE
## Away Team
away_team_pts_off_tov = data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'PTS_OFF_TOV'].values[0]
away_team_pts_off_tov_rank = data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'PTS_OFF_TOV_RANK'].values[0]
l5_away_team_pts_off_tov = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'PTS_OFF_TOV'].values[0]
l5_away_team_pts_off_tov_rank = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'PTS_OFF_TOV_RANK'].values[0]
##League Average
la_pts_off_tov = round(data_misc_season['PTS_OFF_TOV'].mean(), 1)
l5_la_pts_off_tov = round(data_misc_L5['PTS_OFF_TOV'].mean(), 1)
## Home Team
home_team_pts_off_tov = data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'PTS_OFF_TOV'].values[0]
home_team_pts_off_tov_rank = data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'PTS_OFF_TOV_RANK'].values[0]
l5_home_team_pts_off_tov = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'PTS_OFF_TOV'].values[0]
l5_home_team_pts_off_tov_rank = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'PTS_OFF_TOV_RANK'].values[0]

#DEFENSE
## Away Team
away_team_opp_pts_off_tov = data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'OPP_PTS_OFF_TOV'].values[0]
away_team_opp_pts_off_tov_rank = data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'OPP_PTS_OFF_TOV_RANK'].values[0]
l5_away_team_opp_pts_off_tov = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'OPP_PTS_OFF_TOV'].values[0]
l5_away_team_opp_pts_off_tov_rank = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'OPP_PTS_OFF_TOV_RANK'].values[0]
##League Average
la_opp_pts_off_tov = round(data_misc_season['OPP_PTS_OFF_TOV'].mean(), 1)
l5_la_opp_pts_off_tov = round(data_misc_L5['OPP_PTS_OFF_TOV'].mean(), 1)
## Home Team
home_team_opp_pts_off_tov = data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'OPP_PTS_OFF_TOV'].values[0]
home_team_opp_pts_off_tov_rank = data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'OPP_PTS_OFF_TOV_RANK'].values[0]
l5_home_team_opp_pts_off_tov = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'OPP_PTS_OFF_TOV'].values[0]
l5_home_team_opp_pts_off_tov_rank = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'OPP_PTS_OFF_TOV_RANK'].values[0]

#DIFFERENCE
## Away Team
away_team_pts_off_tov_diff = round(data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'PTS_OFF_TOV_DIFF'].values[0], 1)
away_team_pts_off_tov_diff_rank = int(data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'PTS_OFF_TOV_DIFF_RANK'].values[0])
l5_away_team_pts_off_tov_diff = round(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'PTS_OFF_TOV_DIFF'].values[0], 1)
l5_away_team_pts_off_tov_diff_rank = int(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'PTS_OFF_TOV_DIFF_RANK'].values[0])
## League Average
la_pts_off_tov_diff = round(data_misc_season['PTS_OFF_TOV_DIFF'].mean(), 1)
l5_la_pts_off_tov_diff = round(data_misc_L5['PTS_OFF_TOV_DIFF'].mean(), 1)
## Home Team
home_team_pts_off_tov_diff = round(data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'PTS_OFF_TOV_DIFF'].values[0], 1)
home_team_pts_off_tov_diff_rank = int(data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'PTS_OFF_TOV_DIFF_RANK'].values[0])
l5_home_team_pts_off_tov_diff = round(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'PTS_OFF_TOV_DIFF'].values[0], 1)
l5_home_team_pts_off_tov_diff_rank = int(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'PTS_OFF_TOV_DIFF_RANK'].values[0])

#STARTERS AND BENCH SCORING

## STARTERS
### Away Team
away_team_starters_scoring = data_trad_season_starters.loc[data_trad_season_starters['TEAM_ID'] == away_id, 'PTS'].values[0]
away_team_starters_scoring_rank = data_trad_season_starters.loc[data_trad_season_starters['TEAM_ID'] == away_id, 'PTS_RANK'].values[0]
l5_away_team_starters_scoring = data_trad_L5_starters.loc[data_trad_L5_starters['TEAM_ID'] == away_id, 'PTS'].values[0]
l5_away_team_starters_scoring_rank = data_trad_L5_starters.loc[data_trad_L5_starters['TEAM_ID'] == away_id, 'PTS_RANK'].values[0]

### League Average
la_starters_scoring = round(data_trad_season_starters['PTS'].mean(), 1)
l5_la_starters_scoring = round(data_trad_L5_starters['PTS'].mean(), 1)

### Home Team
home_team_starters_scoring = data_trad_season_starters.loc[data_trad_season_starters['TEAM_ID'] == home_id, 'PTS'].values[0]
home_team_starters_scoring_rank = data_trad_season_starters.loc[data_trad_season_starters['TEAM_ID'] == home_id, 'PTS_RANK'].values[0]
l5_home_team_starters_scoring = data_trad_L5_starters.loc[data_trad_L5_starters['TEAM_ID'] == home_id, 'PTS'].values[0]
l5_home_team_starters_scoring_rank = data_trad_L5_starters.loc[data_trad_L5_starters['TEAM_ID'] == home_id, 'PTS_RANK'].values[0]

## BENCH
### Away Team
away_team_bench_scoring = data_trad_season_bench.loc[data_trad_season_bench['TEAM_ID'] == away_id, 'PTS'].values[0]
away_team_bench_scoring_rank = data_trad_season_bench.loc[data_trad_season_bench['TEAM_ID'] == away_id, 'PTS_RANK'].values[0]
l5_away_team_bench_scoring = data_trad_L5_bench.loc[data_trad_L5_bench['TEAM_ID'] == away_id, 'PTS'].values[0]
l5_away_team_bench_scoring_rank = data_trad_L5_bench.loc[data_trad_L5_bench['TEAM_ID'] == away_id, 'PTS_RANK'].values[0]

### League Average
la_bench_scoring = round(data_trad_season_bench['PTS'].mean(), 1)
l5_la_bench_scoring = round(data_trad_L5_bench['PTS'].mean(), 1)

### Home Team
home_team_bench_scoring = data_trad_season_bench.loc[data_trad_season_bench['TEAM_ID'] == home_id, 'PTS'].values[0]
home_team_bench_scoring_rank = data_trad_season_bench.loc[data_trad_season_bench['TEAM_ID'] == home_id, 'PTS_RANK'].values[0]
l5_home_team_bench_scoring = data_trad_L5_bench.loc[data_trad_L5_bench['TEAM_ID'] == home_id, 'PTS'].values[0]
l5_home_team_bench_scoring_rank = data_trad_L5_bench.loc[data_trad_L5_bench['TEAM_ID'] == home_id, 'PTS_RANK'].values[0]

pbp_totals_url = "https://api.pbpstats.com/get-totals/nba"
pbp_totals_params = {
    "Season": current_season,
    "SeasonType": season_type,
    "Type": "Team" # Use Opponent for opponent stats
}
pbp_totals_response = requests.get(pbp_totals_url, params=pbp_totals_params)
pbp_totals_response_json = pbp_totals_response.json()
league_stats_dict = pbp_totals_response_json["single_row_table_data"]
team_stats_dict = pbp_totals_response_json["multi_row_table_data"]

pbp_opp_totals_url = "https://api.pbpstats.com/get-totals/nba"
pbp_opp_totals_params = {
    "Season": current_season,
    "SeasonType": season_type,
    "Type": "Opponent" # Use Opponent for opponent stats
}
pbp_opp_totals_response = requests.get(pbp_opp_totals_url, params=pbp_opp_totals_params)
pbp_opp_totals_response_json = pbp_opp_totals_response.json()
opp_league_stats_dict = pbp_opp_totals_response_json["single_row_table_data"]
opp_team_stats_dict = pbp_opp_totals_response_json["multi_row_table_data"]

team_stats = pd.DataFrame(team_stats_dict)
opp_team_stats = pd.DataFrame(opp_team_stats_dict)

# PRE-WORK FOR SHOOTING STATS -- TEAM
## MAKE TEAM ID A NUMBER
## ALL RANKS SHOULD BE ASCENDING=FALSE
team_stats['TeamId'] = team_stats['TeamId'].astype(int)
## FG%
team_stats['FGM'] = team_stats['FG2M'] + team_stats['FG3M']
team_stats['FGA'] = team_stats['FG2A'] + team_stats['FG3A']
team_stats['FGM_PG'] = round((team_stats['FG2M'] + team_stats['FG3M'])/team_stats['GamesPlayed'], 1)
team_stats['FGM_RANK'] = team_stats['FGM_PG'].rank(ascending=False, method='first').astype(int)
team_stats['FGA_PG'] = round((team_stats['FG2A'] + team_stats['FG3A'])/team_stats['GamesPlayed'], 1)
team_stats['FGA_RANK'] = team_stats['FGA_PG'].rank(ascending=False, method='first').astype(int)
team_stats['FG%'] = round(team_stats['FGM']/team_stats['FGA'], 3)
team_stats['FG%_RANK'] = team_stats['FG%'].rank(ascending=False, method='first').astype(int)

## 2PT%
team_stats['FG2M_PG'] = round(team_stats['FG2M']/team_stats['GamesPlayed'], 1)
team_stats['FG2M_RANK'] = team_stats['FG2M_PG'].rank(ascending=False, method='first').astype(int)
team_stats['FG2A_PG'] = round(team_stats['FG2A']/team_stats['GamesPlayed'], 1)
team_stats['FG2A_RANK'] = team_stats['FG2A_PG'].rank(ascending=False, method='first').astype(int)
team_stats['2PT%'] = round(team_stats['FG2M']/team_stats['FG2A'], 3)
team_stats['2PT%_RANK'] = team_stats['Fg2Pct'].rank(ascending=False, method='first').astype(int)
team_stats['2PT_RATE'] = round(team_stats['FG2A']/team_stats['FGA'], 3)
team_stats['2PT_RATE_RANK'] = team_stats['2PT_RATE'].rank(ascending=False, method='first').astype(int)

## 3PT%
team_stats['FG3M_PG'] = round(team_stats['FG3M']/team_stats['GamesPlayed'], 1)
team_stats['FG3M_RANK'] = team_stats['FG3M_PG'].rank(ascending=False, method='first').astype(int)
team_stats['FG3A_PG'] = round(team_stats['FG3A']/team_stats['GamesPlayed'], 1)
team_stats['FG3A_RANK'] = team_stats['FG3A_PG'].rank(ascending=False, method='first').astype(int)
team_stats['3PT%'] = round(team_stats['FG3M']/team_stats['FG3A'], 3)
team_stats['3PT%_RANK'] = team_stats['Fg3Pct'].rank(ascending=False, method='first').astype(int)
team_stats['3PT_RATE'] = round(team_stats['FG3A']/team_stats['FGA'], 3)
team_stats['3PT_RATE_RANK'] = team_stats['3PT_RATE'].rank(ascending=False, method='first').astype(int)

## FT%
team_stats['FTM'] = team_stats['FtPoints']
team_stats['FTM_PG'] = round(team_stats['FTM']/team_stats['GamesPlayed'], 1)
team_stats['FTM_RANK'] = team_stats['FTM_PG'].rank(ascending=False, method='first').astype(int)
team_stats['FTA_PG'] = round(team_stats['FTA']/team_stats['GamesPlayed'], 1)
team_stats['FTA_RANK'] = team_stats['FTA_PG'].rank(ascending=False, method='first').astype(int)
team_stats['FT%'] = round(team_stats['FTM']/team_stats['FTA'], 3)
team_stats['FT%_RANK'] = team_stats['FT%'].rank(ascending=False, method='first').astype(int)
team_stats['FT_RATE'] = round(team_stats['FTA']/team_stats['FGA'], 3)
team_stats['FT_RATE_RANK'] = team_stats['FT_RATE'].rank(ascending=False, method='first').astype(int)

## RIM
team_stats['RIM_FREQ_RANK'] = team_stats['AtRimFrequency'].fillna(0).rank(ascending=False, method='first').astype(int)
team_stats['RIM_FG%_RANK'] = team_stats['AtRimAccuracy'].fillna(0).rank(ascending=False, method='first').astype(int)

## SMR
team_stats['SMR_FREQ_RANK'] = team_stats['ShortMidRangeFrequency'].fillna(0).rank(ascending=False, method='first').astype(int)
team_stats['SMR_FG%_RANK'] = team_stats['ShortMidRangeAccuracy'].fillna(0).rank(ascending=False, method='first').astype(int)

## LMR
team_stats['LMR_FREQ_RANK'] = team_stats['LongMidRangeFrequency'].fillna(0).rank(ascending=False, method='first').astype(int)
team_stats['LMR_FG%_RANK'] = team_stats['LongMidRangeAccuracy'].fillna(0).rank(ascending=False, method='first').astype(int)

## C3
team_stats['C3_FREQ_RANK'] = team_stats['Corner3Frequency'].fillna(0).rank(ascending=False, method='first').astype(int)
team_stats['C3_FG%_RANK'] = team_stats['Corner3Accuracy'].fillna(0).rank(ascending=False, method='first').astype(int)

## ATB3
team_stats['ATB3_FREQ_RANK'] = team_stats['Arc3Frequency'].fillna(0).rank(ascending=False, method='first').astype(int)
team_stats['ATB3_FG%_RANK'] = team_stats['Arc3Accuracy'].fillna(0).rank(ascending=False, method='first').astype(int)


# PRE-WORK FOR SHOOTING STATS -- OPPONENT
## MAKE TEAM ID A NUMBER
## ALL RANKS SHOULD BE ASCENDING=TRUE
opp_team_stats['TeamId'] = opp_team_stats['TeamId'].astype(int)
## FG%
opp_team_stats['FGM'] = opp_team_stats['FG2M'] + opp_team_stats['FG3M']
opp_team_stats['FGA'] = opp_team_stats['FG2A'] + opp_team_stats['FG3A']
opp_team_stats['FGM_PG'] = round((opp_team_stats['FG2M'] + opp_team_stats['FG3M'])/opp_team_stats['GamesPlayed'], 1)
opp_team_stats['FGM_RANK'] = opp_team_stats['FGM_PG'].rank(ascending=True, method='first').astype(int)
opp_team_stats['FGA_PG'] = round((opp_team_stats['FG2A'] + opp_team_stats['FG3A'])/opp_team_stats['GamesPlayed'], 1)
opp_team_stats['FGA_RANK'] = opp_team_stats['FGA_PG'].rank(ascending=True, method='first').astype(int)
opp_team_stats['FG%'] = round(opp_team_stats['FGM']/opp_team_stats['FGA'], 3)
opp_team_stats['FG%_RANK'] = opp_team_stats['FG%'].rank(ascending=True, method='first').astype(int)

## 2PT%
opp_team_stats['FG2M_PG'] = round(opp_team_stats['FG2M']/opp_team_stats['GamesPlayed'], 1)
opp_team_stats['FG2M_RANK'] = opp_team_stats['FG2M_PG'].rank(ascending=True, method='first').astype(int)
opp_team_stats['FG2A_PG'] = round(opp_team_stats['FG2A']/opp_team_stats['GamesPlayed'], 1)
opp_team_stats['FG2A_RANK'] = opp_team_stats['FG2A_PG'].rank(ascending=True, method='first').astype(int)
opp_team_stats['2PT%'] = round(opp_team_stats['FG2M']/opp_team_stats['FG2A'], 3)
opp_team_stats['2PT%_RANK'] = opp_team_stats['Fg2Pct'].rank(ascending=True, method='first').astype(int)
opp_team_stats['2PT_RATE'] = round(opp_team_stats['FG2A']/opp_team_stats['FGA'], 3)
opp_team_stats['2PT_RATE_RANK'] = opp_team_stats['2PT_RATE'].rank(ascending=True, method='first').astype(int)

## 3PT%
opp_team_stats['FG3M_PG'] = round(opp_team_stats['FG3M']/opp_team_stats['GamesPlayed'], 1)
opp_team_stats['FG3M_RANK'] = opp_team_stats['FG3M_PG'].rank(ascending=True, method='first').astype(int)
opp_team_stats['FG3A_PG'] = round(opp_team_stats['FG3A']/opp_team_stats['GamesPlayed'], 1)
opp_team_stats['FG3A_RANK'] = opp_team_stats['FG3A_PG'].rank(ascending=True, method='first').astype(int)
opp_team_stats['3PT%'] = round(opp_team_stats['FG3M']/opp_team_stats['FG3A'], 3)
opp_team_stats['3PT%_RANK'] = opp_team_stats['Fg3Pct'].rank(ascending=True, method='first').astype(int)
opp_team_stats['3PT_RATE'] = round(opp_team_stats['FG3A']/opp_team_stats['FGA'], 3)
opp_team_stats['3PT_RATE_RANK'] = opp_team_stats['3PT_RATE'].rank(ascending=True, method='first').astype(int)

## FT%
opp_team_stats['FTM'] = opp_team_stats['FtPoints']
opp_team_stats['FTM_PG'] = round(opp_team_stats['FTM']/opp_team_stats['GamesPlayed'], 1)
opp_team_stats['FTM_RANK'] = opp_team_stats['FTM_PG'].rank(ascending=True, method='first').astype(int)
opp_team_stats['FTA_PG'] = round(opp_team_stats['FTA']/opp_team_stats['GamesPlayed'], 1)
opp_team_stats['FTA_RANK'] = opp_team_stats['FTA_PG'].rank(ascending=True, method='first').astype(int)
opp_team_stats['FT%'] = round(opp_team_stats['FTM']/opp_team_stats['FTA'], 3)
opp_team_stats['FT%_RANK'] = opp_team_stats['FT%'].rank(ascending=True, method='first').astype(int)
opp_team_stats['FT_RATE'] = round(opp_team_stats['FTA']/opp_team_stats['FGA'], 3)
opp_team_stats['FT_RATE_RANK'] = opp_team_stats['FT_RATE'].rank(ascending=True, method='first').astype(int)

## RIM
opp_team_stats['RIM_FREQ_RANK'] = opp_team_stats['AtRimFrequency'].fillna(0).rank(ascending=True, method='first').astype(int)
opp_team_stats['RIM_FG%_RANK'] = opp_team_stats['AtRimAccuracy'].fillna(0).rank(ascending=True, method='first').astype(int)

## SMR
opp_team_stats['SMR_FREQ_RANK'] = opp_team_stats['ShortMidRangeFrequency'].fillna(0).rank(ascending=True, method='first').astype(int)
opp_team_stats['SMR_FG%_RANK'] = opp_team_stats['ShortMidRangeAccuracy'].fillna(0).rank(ascending=True, method='first').astype(int)

## LMR
opp_team_stats['LMR_FREQ_RANK'] = opp_team_stats['LongMidRangeFrequency'].fillna(0).rank(ascending=True, method='first').astype(int)
opp_team_stats['LMR_FG%_RANK'] = opp_team_stats['LongMidRangeAccuracy'].fillna(0).rank(ascending=True, method='first').astype(int)

## C3
opp_team_stats['C3_FREQ_RANK'] = opp_team_stats['Corner3Frequency'].fillna(0).rank(ascending=True, method='first').astype(int)
opp_team_stats['C3_FG%_RANK'] = opp_team_stats['Corner3Accuracy'].fillna(0).rank(ascending=True, method='first').astype(int)

## ATB3
opp_team_stats['ATB3_FREQ_RANK'] = opp_team_stats['Arc3Frequency'].fillna(0).rank(ascending=True, method='first').astype(int)
opp_team_stats['ATB3_FG%_RANK'] = opp_team_stats['Arc3Accuracy'].fillna(0).rank(ascending=True, method='first').astype(int)

# PRE-WORK FOR SHOOTING STATS -- DIFFERENTIAL
## MAKE TEAM ID A NUMBER
## ALL RANKS SHOULD BE ASCENDING=TRUE

#Get a list of all team abbreviations
pbp_team_list = team_stats.sort_values('Name', ascending=True)['Name'].tolist()

shooting_columns_to_extract = ['TeamId', 'Name',
                               'FGM_PG', 'FGA_PG', 'FG%',
                               'FG2M_PG', 'FG2A_PG', '2PT%',
                               'FG3M_PG', 'FG3A_PG', '3PT%',
                               'FTM_PG', 'FTA_PG', 'FT%',
                               'AtRimFrequency', 'AtRimAccuracy',
                               'ShortMidRangeFrequency', 'ShortMidRangeAccuracy',
                               'LongMidRangeFrequency', 'LongMidRangeAccuracy',
                               'Corner3Frequency', 'Corner3Accuracy',
                               'Arc3Frequency', 'Arc3Accuracy'
                               ]

# Ensure data is reset and aligned
team_stats_diff = team_stats[shooting_columns_to_extract].reset_index(drop=True)
opp_team_stats_diff = opp_team_stats[shooting_columns_to_extract].reset_index(drop=True)

team_stats_col_num = team_stats_diff.shape[1]
shooting_team_stats_diff = pd.DataFrame()

def create_shooting_diff(team):
    func_df = pd.DataFrame()  # Initialize once per function call

    if team not in team_stats_diff['Name'].values:  # Prevent KeyError
        print(f"Warning: {team} not found in team_stats_diff")
        return pd.DataFrame()  # Return empty DF if team is missing

    for col_counter in range(team_stats_col_num):
        column_name = shooting_columns_to_extract[col_counter]

        # Ensure the column exists
        if column_name not in team_stats_diff.columns or column_name not in opp_team_stats_diff.columns:
            print(f"Warning: {column_name} not found in columns")
            continue  # Skip missing columns

        # Get team and opponent stats safely
        team_stat_values = team_stats_diff.loc[team_stats_diff['Name'] == team, column_name].values
        opp_stat_values = opp_team_stats_diff.loc[opp_team_stats_diff['Name'] == team, column_name].values

        if len(team_stat_values) == 0 or len(opp_stat_values) == 0:
            print(f"Warning: Missing data for team {team} in column {column_name}")
            continue  # Skip if data is missing

        team_stat = team_stat_values[0]
        opp_stat = opp_stat_values[0]

        # Compute final stat difference
        if col_counter > 1:
            final_stat = team_stat - opp_stat
            func_df[column_name] = [final_stat]  # Store as list for DataFrame consistency
        else:
            func_df[column_name] = [team_stat]  # Store team_stat as list

    return func_df  # Return full row, not an empty DataFrame

# Apply function across teams
shooting_diff_results = pd.concat([create_shooting_diff(team) for team in pbp_team_list], ignore_index=True)

#SHOOTING DIFFERENTIAL RANKS
shooting_diff_results['FGM_RANK'] = shooting_diff_results['FGA_PG'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['FGA_RANK'] = shooting_diff_results['FGA_PG'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['FG%_RANK'] = shooting_diff_results['FG%'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['FG2M_RANK'] = shooting_diff_results['FG2M_PG'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['FG2A_RANK'] = shooting_diff_results['FG2A_PG'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['2PT%_RANK'] = shooting_diff_results['2PT%'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['FG3M_RANK'] = shooting_diff_results['FG3M_PG'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['FG3A_RANK'] = shooting_diff_results['FG3A_PG'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['3PT%_RANK'] = shooting_diff_results['3PT%'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['FTM_RANK'] = shooting_diff_results['FTM_PG'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['FTA_RANK'] = shooting_diff_results['FTA_PG'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['FT%_RANK'] = shooting_diff_results['FT%'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['RIM_FREQ_RANK'] = shooting_diff_results['AtRimFrequency'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['RIM_FG%_RANK'] = shooting_diff_results['AtRimAccuracy'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['SMR_FREQ_RANK'] = shooting_diff_results['ShortMidRangeFrequency'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['SMR_FG%_RANK'] = shooting_diff_results['ShortMidRangeAccuracy'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['LMR_FREQ_RANK'] = shooting_diff_results['LongMidRangeFrequency'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['LMR_FG%_RANK'] = shooting_diff_results['LongMidRangeAccuracy'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['C3_FREQ_RANK'] = shooting_diff_results['Corner3Frequency'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['C3_FG%_RANK'] = shooting_diff_results['Corner3Accuracy'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['ATB3_FREQ_RANK'] = shooting_diff_results['Arc3Frequency'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['ATB3_FG%_RANK'] = shooting_diff_results['Arc3Accuracy'].fillna(0).rank(ascending=False, method='first').astype(int)
## HOME TEAM SHOOTING STATS

# Overall Field Goals
# home_team_bench_scoring = data_trad_season_bench.loc[data_trad_season_bench['TEAM_ID'] == home_id, 'PTS'].values[0]
## FGM
home_team_fgm = team_stats.loc[team_stats['TeamId'] == home_id, 'FGM_PG'].values[0]
home_team_fgm_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'FGM_RANK'].values[0]
home_team_opp_fgm = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FGM_PG'].values[0]
home_team_opp_fgm_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FGM_RANK'].values[0]
home_team_diff_fgm = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FGM_PG'].values[0], 1)
home_team_diff_fgm_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FGM_RANK'].values[0]
## FGA
home_team_fga = team_stats.loc[team_stats['TeamId'] == home_id, 'FGA_PG'].values[0]
home_team_fga_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'FGA_RANK'].values[0]
home_team_opp_fga = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FGA_PG'].values[0]
home_team_opp_fga_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FGA_RANK'].values[0]
home_team_diff_fga = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FGA_PG'].values[0], 1)
home_team_diff_fga_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FGA_RANK'].values[0]
## FG%
home_team_fg_pct = team_stats.loc[team_stats['TeamId'] == home_id, 'FG%'].values[0]
home_team_fg_pct_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'FG%_RANK'].values[0]
home_team_opp_fg_pct = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FG%'].values[0]
home_team_opp_fg_pct_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FG%_RANK'].values[0]
home_team_diff_fg_pct = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FG%'].values[0]
home_team_diff_fg_pct_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FG%_RANK'].values[0]
# Overall 2-Point Shooting
## 2PT
home_team_2pt = team_stats.loc[team_stats['TeamId'] == home_id, 'FG2M_PG'].values[0]
home_team_2pt_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'FG2M_RANK'].values[0]
home_team_opp_2pt = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FG2M_PG'].values[0]
home_team_opp_2pt_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FG2M_RANK'].values[0]
home_team_diff_2pt = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FG2M_PG'].values[0], 1)
home_team_diff_2pt_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FG2M_RANK'].values[0]
## 2PA
home_team_2pa = team_stats.loc[team_stats['TeamId'] == home_id, 'FG2A_PG'].values[0]
home_team_2pa_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'FG2A_RANK'].values[0]
home_team_opp_2pa = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FG2A_PG'].values[0]
home_team_opp_2pa_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FG2A_RANK'].values[0]
home_team_diff_2pa = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FG2A_PG'].values[0], 1)
home_team_diff_2pa_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FG2A_RANK'].values[0]
## 2PT%
home_team_2pt_pct = team_stats.loc[team_stats['TeamId'] == home_id, '2PT%'].values[0]
home_team_2pt_pct_rank = team_stats.loc[team_stats['TeamId'] == home_id, '2PT%_RANK'].values[0]
home_team_opp_2pt_pct = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, '2PT%'].values[0]
home_team_opp_2pt_pct_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, '2PT%_RANK'].values[0]
home_team_diff_2pt_pct = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, '2PT%'].values[0]
home_team_diff_2pt_pct_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, '2PT%_RANK'].values[0]
# Overall 3-Point Shooting
## 3PT
home_team_3pt = team_stats.loc[team_stats['TeamId'] == home_id, 'FG3M_PG'].values[0]
home_team_3pt_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'FG3M_RANK'].values[0]
home_team_opp_3pt = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FG3M_PG'].values[0]
home_team_opp_3pt_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FG3M_RANK'].values[0]
home_team_diff_3pt = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FG3M_PG'].values[0], 1)
home_team_diff_3pt_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FG3M_RANK'].values[0]
## 3PA
home_team_3pa = team_stats.loc[team_stats['TeamId'] == home_id, 'FG3A_PG'].values[0]
home_team_3pa_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'FG3A_RANK'].values[0]
home_team_opp_3pa = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FG3A_PG'].values[0]
home_team_opp_3pa_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FG3A_RANK'].values[0]
home_team_diff_3pa = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FG3A_PG'].values[0], 1)
home_team_diff_3pa_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FG3A_RANK'].values[0]
## 3PT%
home_team_3pt_pct = team_stats.loc[team_stats['TeamId'] == home_id, '3PT%'].values[0]
home_team_3pt_pct_rank = team_stats.loc[team_stats['TeamId'] == home_id, '3PT%_RANK'].values[0]
home_team_opp_3pt_pct = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, '3PT%'].values[0]
home_team_opp_3pt_pct_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, '3PT%_RANK'].values[0]
home_team_diff_3pt_pct = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, '3PT%'].values[0]
home_team_diff_3pt_pct_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, '3PT%_RANK'].values[0]
# Overall Free Throw Shooting
## FTM
home_team_ftm = team_stats.loc[team_stats['TeamId'] == home_id, 'FTM_PG'].values[0]
home_team_ftm_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'FTM_RANK'].values[0]
home_team_opp_ftm = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FTM_PG'].values[0]
home_team_opp_ftm_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FTM_RANK'].values[0]
home_team_diff_ftm = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FTM_PG'].values[0], 1)
home_team_diff_ftm_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FTM_RANK'].values[0]
## FTA
home_team_fta = team_stats.loc[team_stats['TeamId'] == home_id, 'FTA_PG'].values[0]
home_team_fta_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'FTA_RANK'].values[0]
home_team_opp_fta = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FTA_PG'].values[0]
home_team_opp_fta_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FTA_RANK'].values[0]
home_team_diff_fta = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FTA_PG'].values[0], 1)
home_team_diff_fta_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FTA_RANK'].values[0]
## FT%
home_team_ft_pct = team_stats.loc[team_stats['TeamId'] == home_id, 'FT%'].values[0]
home_team_ft_pct_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'FT%_RANK'].values[0]
home_team_opp_ft_pct = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FT%'].values[0]
home_team_opp_ft_pct_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FT%_RANK'].values[0]
home_team_diff_ft_pct = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FT%'].values[0]
home_team_diff_ft_pct_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FT%_RANK'].values[0]
# RIM
## Rim Frequency
home_team_rim_freq = team_stats.loc[team_stats['TeamId'] == home_id, 'AtRimFrequency'].values[0]
home_team_rim_freq_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'RIM_FREQ_RANK'].values[0]
home_team_opp_rim_freq = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'AtRimFrequency'].values[0]
home_team_opp_rim_freq_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'RIM_FREQ_RANK'].values[0]
home_team_diff_rim_freq = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'AtRimFrequency'].values[0]
home_team_diff_rim_freq_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'RIM_FREQ_RANK'].values[0]
## Rim Accuracy
home_team_rim_acc = team_stats.loc[team_stats['TeamId'] == home_id, 'AtRimAccuracy'].values[0]
home_team_rim_acc_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'RIM_FG%_RANK'].values[0]
home_team_opp_rim_acc = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'AtRimAccuracy'].values[0]
home_team_opp_rim_acc_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'RIM_FG%_RANK'].values[0]
home_team_diff_rim_acc = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'AtRimAccuracy'].values[0]
home_team_diff_rim_acc_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'RIM_FG%_RANK'].values[0]

# Short Mid-Range Shooting
## SMR Frequency
home_team_smr_freq = team_stats.loc[team_stats['TeamId'] == home_id, 'ShortMidRangeFrequency'].values[0]
home_team_smr_freq_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'SMR_FREQ_RANK'].values[0]
home_team_opp_smr_freq = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'ShortMidRangeFrequency'].values[0]
home_team_opp_smr_freq_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'SMR_FREQ_RANK'].values[0]
home_team_diff_smr_freq = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'ShortMidRangeFrequency'].values[0]
home_team_diff_smr_freq_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'SMR_FREQ_RANK'].values[0]
## SMR Accuracy
home_team_smr_acc = team_stats.loc[team_stats['TeamId'] == home_id, 'ShortMidRangeAccuracy'].values[0]
home_team_smr_acc_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'SMR_FG%_RANK'].values[0]
home_team_opp_smr_acc = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'ShortMidRangeAccuracy'].values[0]
home_team_opp_smr_acc_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'SMR_FG%_RANK'].values[0]
home_team_diff_smr_acc = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'ShortMidRangeAccuracy'].values[0]
home_team_diff_smr_acc_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'SMR_FG%_RANK'].values[0]

# Long Mid-Range Shooting
## LMR Frequency
home_team_lmr_freq = team_stats.loc[team_stats['TeamId'] == home_id, 'LongMidRangeFrequency'].values[0]
home_team_lmr_freq_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'LMR_FREQ_RANK'].values[0]
home_team_opp_lmr_freq = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'LongMidRangeFrequency'].values[0]
home_team_opp_lmr_freq_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'LMR_FREQ_RANK'].values[0]
home_team_diff_lmr_freq = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'LongMidRangeFrequency'].values[0]
home_team_diff_lmr_freq_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'LMR_FREQ_RANK'].values[0]
## LMR Accuracy
home_team_lmr_acc = team_stats.loc[team_stats['TeamId'] == home_id, 'LongMidRangeAccuracy'].values[0]
home_team_lmr_acc_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'LMR_FG%_RANK'].values[0]
home_team_opp_lmr_acc = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'LongMidRangeAccuracy'].values[0]
home_team_opp_lmr_acc_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'LMR_FG%_RANK'].values[0]
home_team_diff_lmr_acc = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'LongMidRangeAccuracy'].values[0]
home_team_diff_lmr_acc_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'LMR_FG%_RANK'].values[0]
# Corner 3-Point Shooting
## C3 Frequency
home_team_c3_freq = team_stats.loc[team_stats['TeamId'] == home_id, 'Corner3Frequency'].values[0]
home_team_c3_freq_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'C3_FREQ_RANK'].values[0]
home_team_opp_c3_freq = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'Corner3Frequency'].values[0]
home_team_opp_c3_freq_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'C3_FREQ_RANK'].values[0]
home_team_diff_c3_freq = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'Corner3Frequency'].values[0]
home_team_diff_c3_freq_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'C3_FREQ_RANK'].values[0]
## C3 Accuracy
home_team_c3_acc = team_stats.loc[team_stats['TeamId'] == home_id, 'Corner3Accuracy'].values[0]
home_team_c3_acc_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'C3_FG%_RANK'].values[0]
home_team_opp_c3_acc = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'Corner3Accuracy'].values[0]
home_team_opp_c3_acc_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'C3_FG%_RANK'].values[0]
home_team_diff_c3_acc = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'Corner3Accuracy'].values[0]
home_team_diff_c3_acc_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'C3_FG%_RANK'].values[0]
# Above the Break 3-Point Shooting
## ATB3 Frequency
home_team_atb3_freq = team_stats.loc[team_stats['TeamId'] == home_id, 'Arc3Frequency'].values[0]
home_team_atb3_freq_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'ATB3_FREQ_RANK'].values[0]
home_team_opp_atb3_freq = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'Arc3Frequency'].values[0]
home_team_opp_atb3_freq_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'ATB3_FREQ_RANK'].values[0]
home_team_diff_atb3_freq = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'Arc3Frequency'].values[0]
home_team_diff_atb3_freq_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'ATB3_FREQ_RANK'].values[0]
## ATB3 Accuracy
home_team_atb3_acc = team_stats.loc[team_stats['TeamId'] == home_id, 'Arc3Accuracy'].values[0]
home_team_atb3_acc_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'ATB3_FG%_RANK'].values[0]
home_team_opp_atb3_acc = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'Arc3Accuracy'].values[0]
home_team_opp_atb3_acc_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'ATB3_FG%_RANK'].values[0]
home_team_diff_atb3_acc = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'Arc3Accuracy'].values[0]
home_team_diff_atb3_acc_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'ATB3_FG%_RANK'].values[0]

## AWAY TEAM SHOOTING STATS

# Overall Field Goals
# away_team_bench_scoring = data_trad_season_bench.loc[data_trad_season_bench['TEAM_ID'] == away_id, 'PTS'].values[0]
## FGM
away_team_fgm = team_stats.loc[team_stats['TeamId'] == away_id, 'FGM_PG'].values[0]
away_team_fgm_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'FGM_RANK'].values[0]
away_team_opp_fgm = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FGM_PG'].values[0]
away_team_opp_fgm_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FGM_RANK'].values[0]
away_team_diff_fgm = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FGM_PG'].values[0], 1)
away_team_diff_fgm_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FGM_RANK'].values[0]
## FGA
away_team_fga = team_stats.loc[team_stats['TeamId'] == away_id, 'FGA_PG'].values[0]
away_team_fga_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'FGA_RANK'].values[0]
away_team_opp_fga = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FGA_PG'].values[0]
away_team_opp_fga_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FGA_RANK'].values[0]
away_team_diff_fga = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FGA_PG'].values[0], 1)
away_team_diff_fga_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FGA_RANK'].values[0]
## FG%
away_team_fg_pct = team_stats.loc[team_stats['TeamId'] == away_id, 'FG%'].values[0]
away_team_fg_pct_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'FG%_RANK'].values[0]
away_team_opp_fg_pct = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FG%'].values[0]
away_team_opp_fg_pct_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FG%_RANK'].values[0]
away_team_diff_fg_pct = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FG%'].values[0]
away_team_diff_fg_pct_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FG%_RANK'].values[0]
# Overall 2-Point Shooting
## 2PT
away_team_2pt = team_stats.loc[team_stats['TeamId'] == away_id, 'FG2M_PG'].values[0]
away_team_2pt_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'FG2M_RANK'].values[0]
away_team_opp_2pt = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FG2M_PG'].values[0]
away_team_opp_2pt_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FG2M_RANK'].values[0]
away_team_diff_2pt = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FG2M_PG'].values[0], 1)
away_team_diff_2pt_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FG2M_RANK'].values[0]
## 2PA
away_team_2pa = team_stats.loc[team_stats['TeamId'] == away_id, 'FG2A_PG'].values[0]
away_team_2pa_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'FG2A_RANK'].values[0]
away_team_opp_2pa = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FG2A_PG'].values[0]
away_team_opp_2pa_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FG2A_RANK'].values[0]
away_team_diff_2pa = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FG2A_PG'].values[0], 1)
away_team_diff_2pa_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FG2A_RANK'].values[0]
## 2PT%
away_team_2pt_pct = team_stats.loc[team_stats['TeamId'] == away_id, '2PT%'].values[0]
away_team_2pt_pct_rank = team_stats.loc[team_stats['TeamId'] == away_id, '2PT%_RANK'].values[0]
away_team_opp_2pt_pct = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, '2PT%'].values[0]
away_team_opp_2pt_pct_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, '2PT%_RANK'].values[0]
away_team_diff_2pt_pct = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, '2PT%'].values[0]
away_team_diff_2pt_pct_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, '2PT%_RANK'].values[0]
# Overall 3-Point Shooting
## 3PT
away_team_3pt = team_stats.loc[team_stats['TeamId'] == away_id, 'FG3M_PG'].values[0]
away_team_3pt_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'FG3M_RANK'].values[0]
away_team_opp_3pt = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FG3M_PG'].values[0]
away_team_opp_3pt_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FG3M_RANK'].values[0]
away_team_diff_3pt = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FG3M_PG'].values[0], 1)
away_team_diff_3pt_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FG3M_RANK'].values[0]
## 3PA
away_team_3pa = team_stats.loc[team_stats['TeamId'] == away_id, 'FG3A_PG'].values[0]
away_team_3pa_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'FG3A_RANK'].values[0]
away_team_opp_3pa = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FG3A_PG'].values[0]
away_team_opp_3pa_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FG3A_RANK'].values[0]
away_team_diff_3pa = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FG3A_PG'].values[0], 1)
away_team_diff_3pa_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FG3A_RANK'].values[0]
## 3PT%
away_team_3pt_pct = team_stats.loc[team_stats['TeamId'] == away_id, '3PT%'].values[0]
away_team_3pt_pct_rank = team_stats.loc[team_stats['TeamId'] == away_id, '3PT%_RANK'].values[0]
away_team_opp_3pt_pct = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, '3PT%'].values[0]
away_team_opp_3pt_pct_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, '3PT%_RANK'].values[0]
away_team_diff_3pt_pct = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, '3PT%'].values[0]
away_team_diff_3pt_pct_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, '3PT%_RANK'].values[0]
# Overall Free Throw Shooting
## FTM
away_team_ftm = team_stats.loc[team_stats['TeamId'] == away_id, 'FTM_PG'].values[0]
away_team_ftm_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'FTM_RANK'].values[0]
away_team_opp_ftm = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FTM_PG'].values[0]
away_team_opp_ftm_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FTM_RANK'].values[0]
away_team_diff_ftm = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FTM_PG'].values[0], 1)
away_team_diff_ftm_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FTM_RANK'].values[0]
## FTA
away_team_fta = team_stats.loc[team_stats['TeamId'] == away_id, 'FTA_PG'].values[0]
away_team_fta_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'FTA_RANK'].values[0]
away_team_opp_fta = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FTA_PG'].values[0]
away_team_opp_fta_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FTA_RANK'].values[0]
away_team_diff_fta = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FTA_PG'].values[0], 1)
away_team_diff_fta_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FTA_RANK'].values[0]
## FT%
away_team_ft_pct = team_stats.loc[team_stats['TeamId'] == away_id, 'FT%'].values[0]
away_team_ft_pct_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'FT%_RANK'].values[0]
away_team_opp_ft_pct = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FT%'].values[0]
away_team_opp_ft_pct_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FT%_RANK'].values[0]
away_team_diff_ft_pct = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FT%'].values[0]
away_team_diff_ft_pct_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FT%_RANK'].values[0]
# RIM
## Rim Frequency
away_team_rim_freq = team_stats.loc[team_stats['TeamId'] == away_id, 'AtRimFrequency'].values[0]
away_team_rim_freq_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'RIM_FREQ_RANK'].values[0]
away_team_opp_rim_freq = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'AtRimFrequency'].values[0]
away_team_opp_rim_freq_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'RIM_FREQ_RANK'].values[0]
away_team_diff_rim_freq = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'AtRimFrequency'].values[0]
away_team_diff_rim_freq_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'RIM_FREQ_RANK'].values[0]
## Rim Accuracy
away_team_rim_acc = team_stats.loc[team_stats['TeamId'] == away_id, 'AtRimAccuracy'].values[0]
away_team_rim_acc_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'RIM_FG%_RANK'].values[0]
away_team_opp_rim_acc = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'AtRimAccuracy'].values[0]
away_team_opp_rim_acc_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'RIM_FG%_RANK'].values[0]
away_team_diff_rim_acc = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'AtRimAccuracy'].values[0]
away_team_diff_rim_acc_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'RIM_FG%_RANK'].values[0]

# Short Mid-Range Shooting
## SMR Frequency
away_team_smr_freq = team_stats.loc[team_stats['TeamId'] == away_id, 'ShortMidRangeFrequency'].values[0]
away_team_smr_freq_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'SMR_FREQ_RANK'].values[0]
away_team_opp_smr_freq = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'ShortMidRangeFrequency'].values[0]
away_team_opp_smr_freq_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'SMR_FREQ_RANK'].values[0]
away_team_diff_smr_freq = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'ShortMidRangeFrequency'].values[0]
away_team_diff_smr_freq_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'SMR_FREQ_RANK'].values[0]
## SMR Accuracy
away_team_smr_acc = team_stats.loc[team_stats['TeamId'] == away_id, 'ShortMidRangeAccuracy'].values[0]
away_team_smr_acc_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'SMR_FG%_RANK'].values[0]
away_team_opp_smr_acc = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'ShortMidRangeAccuracy'].values[0]
away_team_opp_smr_acc_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'SMR_FG%_RANK'].values[0]
away_team_diff_smr_acc = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'ShortMidRangeAccuracy'].values[0]
away_team_diff_smr_acc_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'SMR_FG%_RANK'].values[0]

# Long Mid-Range Shooting
## LMR Frequency
away_team_lmr_freq = team_stats.loc[team_stats['TeamId'] == away_id, 'LongMidRangeFrequency'].values[0]
away_team_lmr_freq_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'LMR_FREQ_RANK'].values[0]
away_team_opp_lmr_freq = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'LongMidRangeFrequency'].values[0]
away_team_opp_lmr_freq_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'LMR_FREQ_RANK'].values[0]
away_team_diff_lmr_freq = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'LongMidRangeFrequency'].values[0]
away_team_diff_lmr_freq_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'LMR_FREQ_RANK'].values[0]
## LMR Accuracy
away_team_lmr_acc = team_stats.loc[team_stats['TeamId'] == away_id, 'LongMidRangeAccuracy'].values[0]
away_team_lmr_acc_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'LMR_FG%_RANK'].values[0]
away_team_opp_lmr_acc = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'LongMidRangeAccuracy'].values[0]
away_team_opp_lmr_acc_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'LMR_FG%_RANK'].values[0]
away_team_diff_lmr_acc = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'LongMidRangeAccuracy'].values[0]
away_team_diff_lmr_acc_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'LMR_FG%_RANK'].values[0]
# Corner 3-Point Shooting
## C3 Frequency
away_team_c3_freq = team_stats.loc[team_stats['TeamId'] == away_id, 'Corner3Frequency'].values[0]
away_team_c3_freq_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'C3_FREQ_RANK'].values[0]
away_team_opp_c3_freq = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'Corner3Frequency'].values[0]
away_team_opp_c3_freq_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'C3_FREQ_RANK'].values[0]
away_team_diff_c3_freq = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'Corner3Frequency'].values[0]
away_team_diff_c3_freq_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'C3_FREQ_RANK'].values[0]
## C3 Accuracy
away_team_c3_acc = team_stats.loc[team_stats['TeamId'] == away_id, 'Corner3Accuracy'].values[0]
away_team_c3_acc_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'C3_FG%_RANK'].values[0]
away_team_opp_c3_acc = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'Corner3Accuracy'].values[0]
away_team_opp_c3_acc_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'C3_FG%_RANK'].values[0]
away_team_diff_c3_acc = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'Corner3Accuracy'].values[0]
away_team_diff_c3_acc_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'C3_FG%_RANK'].values[0]
# Above the Break 3-Point Shooting
## ATB3 Frequency
away_team_atb3_freq = team_stats.loc[team_stats['TeamId'] == away_id, 'Arc3Frequency'].values[0]
away_team_atb3_freq_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'ATB3_FREQ_RANK'].values[0]
away_team_opp_atb3_freq = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'Arc3Frequency'].values[0]
away_team_opp_atb3_freq_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'ATB3_FREQ_RANK'].values[0]
away_team_diff_atb3_freq = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'Arc3Frequency'].values[0]
away_team_diff_atb3_freq_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'ATB3_FREQ_RANK'].values[0]
## ATB3 Accuracy
away_team_atb3_acc = team_stats.loc[team_stats['TeamId'] == away_id, 'Arc3Accuracy'].values[0]
away_team_atb3_acc_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'ATB3_FG%_RANK'].values[0]
away_team_opp_atb3_acc = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'Arc3Accuracy'].values[0]
away_team_opp_atb3_acc_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'ATB3_FG%_RANK'].values[0]
away_team_diff_atb3_acc = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'Arc3Accuracy'].values[0]
away_team_diff_atb3_acc_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'ATB3_FG%_RANK'].values[0]

## LEAGUE AVERAGE SHOOTING STATS

la_fgm = round(team_stats_diff['FGM_PG'].mean(), 1)
la_fga = round(team_stats_diff['FGA_PG'].mean(), 1)
la_fg_pct = round(team_stats_diff['FG%'].mean(), 3)

la_2pt = round(team_stats_diff['FG2M_PG'].mean(), 1)
la_2pa = round(team_stats_diff['FG2A_PG'].mean(), 1)
la_2pt_pct = round(team_stats_diff['2PT%'].mean(), 3)

la_3pt = round(team_stats_diff['FG3M_PG'].mean(), 1)
la_3pa = round(team_stats_diff['FG3A_PG'].mean(), 1)
la_3pt_pct = round(team_stats_diff['3PT%'].mean(), 3)

la_ftm = round(team_stats_diff['FTM_PG'].mean(), 1)
la_fta = round(team_stats_diff['FTA_PG'].mean(), 1)
la_ft_pct = round(team_stats_diff['FT%'].mean(), 3)

la_rim_freq = round(team_stats_diff['AtRimFrequency'].mean(), 3)
la_rim_acc = round(team_stats_diff['AtRimAccuracy'].mean(), 3)

la_smr_freq = round(team_stats_diff['ShortMidRangeFrequency'].mean(), 3)
la_smr_acc = round(team_stats_diff['ShortMidRangeAccuracy'].mean(), 3)

la_lmr_freq = round(team_stats_diff['LongMidRangeFrequency'].mean(), 3)
la_lmr_acc = round(team_stats_diff['LongMidRangeAccuracy'].mean(), 3)

la_atb3_freq = round(team_stats_diff['Arc3Frequency'].mean(), 3)
la_atb3_acc = round(team_stats_diff['Arc3Accuracy'].mean(), 3)

la_c3_freq = round(team_stats_diff['Corner3Frequency'].mean(), 3)
la_c3_acc = round(team_stats_diff['Corner3Accuracy'].mean(), 3)
