import nba_api.stats.endpoints
import requests
import json
import pandas as pd
import nba_api
import altair as alt
import streamlit as st

current_season = '2025-26'
game_logs_ex = nba_api.stats.endpoints.PlayerGameLogs(
    season_nullable=current_season,
).get_data_frames()[0]


ant = game_logs_ex.loc[game_logs_ex['PLAYER_NAME'] == 'Anthony Edwards'].sort_values(by='GAME_DATE')

ant = ant.assign(game_num=range(1, len(ant) + 1))

# Calculate 5-game moving average
ant['PTS_MA'] = ant['PTS'].rolling(window=5, min_periods=1).mean()

# Create the base chart for actual points
pts_chart = alt.Chart(ant).mark_line(color='#f76517').encode(
    x='game_num:Q',
    y='PTS:Q',
    tooltip=['game_num', 'PTS']
).properties(
    title="Points per Game with 5-Game Moving Average",
    width=600,
    height = 500
)

# Create the moving average line
ma_chart = alt.Chart(ant).mark_line(color='#175aaa', ).encode(
    x='game_num:Q',
    y='PTS_MA:Q',
    tooltip=['game_num', 'PTS_MA']
)

# Combine both charts
final_chart = pts_chart + ma_chart

ant_id = '1630162'
headshot = f'https://cdn.nba.com/headshots/nba/latest/1040x760/{ant_id}.png'
