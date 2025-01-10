
import nba_api.stats.endpoints
import requests
import json
import pandas as pd
import nba_api

current_season = '2024-25'


#ADVANCED DATA LOADING
##SEASON
data_adv_season = nba_api.stats.endpoints.LeagueDashTeamStats(
    # last_n_games=None,
    measure_type_detailed_defense='Advanced',
    pace_adjust='N',
    per_mode_detailed='PerGame',
    season=current_season,
    season_type_all_star='Regular Season'
    ).get_data_frames()[0]
##LAST 5 GAMES
data_adv_L5 = nba_api.stats.endpoints.LeagueDashTeamStats(
    # last_n_games=None,
    measure_type_detailed_defense='Advanced',
    pace_adjust='N',
    per_mode_detailed='PerGame',
    season=current_season,
    season_type_all_star='Regular Season',
    last_n_games=5
    ).get_data_frames()[0]

#MISC DATA LOADING
##SEASON
data_misc_season = nba_api.stats.endpoints.LeagueDashTeamStats(
    # last_n_games=None,
    measure_type_detailed_defense='Misc',
    pace_adjust='N',
    per_mode_detailed='PerGame',
    season='2024-25',
    season_type_all_star='Regular Season'
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
    season='2024-25',
    season_type_all_star='Regular Season',
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
    season='2024-25',
    season_type_all_star='Regular Season'
    ).get_data_frames()[0]
## LAST 5
data_trad_L5 = nba_api.stats.endpoints.LeagueDashTeamStats(
    # last_n_games=None,
    measure_type_detailed_defense='Base',
    pace_adjust='N',
    per_mode_detailed='PerGame',
    season='2024-25',
    season_type_all_star='Regular Season',
    last_n_games=5
    ).get_data_frames()[0]
## SEASON - STARTERS
data_trad_season_starters = nba_api.stats.endpoints.LeagueDashTeamStats(
    # last_n_games=None,
    measure_type_detailed_defense='Base',
    pace_adjust='N',
    per_mode_detailed='PerGame',
    season='2024-25',
    season_type_all_star='Regular Season',
    starter_bench_nullable='Starters'
    ).get_data_frames()[0]
## LAST 5 - STARTERS
data_trad_L5_starters = nba_api.stats.endpoints.LeagueDashTeamStats(
    # last_n_games=None,
    measure_type_detailed_defense='Base',
    pace_adjust='N',
    per_mode_detailed='PerGame',
    season='2024-25',
    season_type_all_star='Regular Season',
    last_n_games=5,
    starter_bench_nullable='Starters'
    ).get_data_frames()[0]
## SEASON - BENCH
data_trad_season_bench = nba_api.stats.endpoints.LeagueDashTeamStats(
    # last_n_games=None,
    measure_type_detailed_defense='Base',
    pace_adjust='N',
    per_mode_detailed='PerGame',
    season='2024-25',
    season_type_all_star='Regular Season',
    starter_bench_nullable='Bench'
    ).get_data_frames()[0]
## LAST 5 - BENCH
data_trad_L5_bench = nba_api.stats.endpoints.LeagueDashTeamStats(
    # last_n_games=None,
    measure_type_detailed_defense='Base',
    pace_adjust='N',
    per_mode_detailed='PerGame',
    season='2024-25',
    season_type_all_star='Regular Season',
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
    season='2024-25',
    season_type_all_star='Regular Season'
    ).get_data_frames()[0]
## LAST 5 GAMES
data_4F_L5 = nba_api.stats.endpoints.LeagueDashTeamStats(
    # last_n_games=None,
    measure_type_detailed_defense='Four Factors',
    pace_adjust='N',
    per_mode_detailed='PerGame',
    season='2024-25',
    season_type_all_star='Regular Season',
    last_n_games=5
    ).get_data_frames()[0]

#Key base variables
wolves_id = data_adv_season.loc[data_adv_season['TEAM_NAME'] == 'Minnesota Timberwolves', 'TEAM_ID'].values[0]
logo_link = f'https://cdn.nba.com/logos/nba/{wolves_id}/primary/L/logo.svg'
timberwolves = 'Minnesota Timberwolves'
nba_logo = 'https://a.espncdn.com/combiner/i?img=/i/teamlogos/leagues/500/nba.png?w=100&h=100&transparent=true'

#Load in the current NBA standings
standings = nba_api.stats.endpoints.LeagueStandings(league_id='00', season='2024-25', season_type='Regular Season').get_data_frames()[0]

#Import today's games
from nba_api.live.nba.endpoints import scoreboard
games = scoreboard.ScoreBoard()
games_json = json.loads(games.get_json())
todays_games = games_json['scoreboard']['games']

#Search for the Wolves game
target_key = 'gameCode'
partial_match = 'MIN'

for index, dictionary in enumerate(todays_games):
    if target_key in dictionary and partial_match in dictionary[target_key]:
        target_index = index
    # else:
    #     target_index = 0

if todays_games[target_index]['homeTeam']['teamId'] == wolves_id:
    game_id = todays_games[target_index]['gameId']
    home_or_away = 'Home'
    home_id = wolves_id
    home_logo_link = f'https://cdn.nba.com/logos/nba/{home_id}/primary/L/logo.svg'
    away_id = todays_games[target_index]['awayTeam']['teamId']
    away_logo_link = f'https://cdn.nba.com/logos/nba/{away_id}/primary/L/logo.svg'
    opponent_name = data_adv_season.loc[data_adv_season['TEAM_ID'] == away_id, 'TEAM_NAME'].values[0]
    game_title = f'{opponent_name} at Minnesota Timberwolves'
else:
    game_id = todays_games[target_index]['gameId']
    home_or_away = 'Away'
    away_id = wolves_id
    away_logo_link = f'https://cdn.nba.com/logos/nba/{away_id}/primary/L/logo.svg'
    home_id = todays_games[target_index]['homeTeam']['teamId']
    home_logo_link = f'https://cdn.nba.com/logos/nba/{home_id}/primary/L/logo.svg'
    opponent_name = data_adv_season.loc[data_adv_season['TEAM_ID'] == home_id, 'TEAM_NAME'].values[0]
    game_title = f'Minnesota Timberwolves at {opponent_name}'

print(game_title, todays_games)

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
print(la_tov_pct)
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