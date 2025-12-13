import streamlit as st
import streamlit_testing_functions as functions
import datetime
from datetime import date

import altair as alt
import pandas as pd

# Clear all caches
# st.cache_data.clear()

st.set_page_config(layout="wide")
st.title("NBA Matchup Data App HA GAYYY")

# Cache matchup data
@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_cached_matchups(selected_date):
    """Get matchups for a given date"""
    return functions.get_matchups_for_date(selected_date)

@st.cache_data
def get_cached_team_list():
    """Get list of all teams"""
    return functions.get_team_list()

# Matchup Selection Section
st.markdown("### Select Matchup")
col_date, col_matchup = st.columns([0.3, 0.7])

with col_date:
    selected_date = st.date_input(
        "Select Date:",
        value=date.today(),
        key="matchup_date"
    )

with col_matchup:
    matchups, matchup_error = get_cached_matchups(selected_date)
    
    if matchup_error:
        st.warning(f"⚠️ Could not fetch matchups: {matchup_error}")
        matchups = []
    
    if matchups:
        matchup_options = [m['matchup'] for m in matchups]
        selected_matchup_str = st.selectbox(
            "Select Matchup:",
            options=matchup_options,
            key="matchup_selector"
        )
        # Get the selected matchup's team IDs
        selected_matchup = next((m for m in matchups if m['matchup'] == selected_matchup_str), None)
        if selected_matchup:
            home_id = selected_matchup['home_team_id']
            away_id = selected_matchup['away_team_id']
            st.success(f"📊 {selected_matchup['away_team_name']} @ {selected_matchup['home_team_name']}")
        else:
            home_id = None
            away_id = None
    else:
        st.info("ℹ️ No games scheduled for this date. Select teams manually below.")
        # Manual team selection
        teams = get_cached_team_list()
        team_names = [t['TEAM_NAME'] for t in teams]
        
        col_away, col_home = st.columns(2)
        with col_away:
            away_team_name = st.selectbox("Away Team:", options=team_names, key="away_team_manual")
            away_team = next((t for t in teams if t['TEAM_NAME'] == away_team_name), None)
            away_id = away_team['TEAM_ID'] if away_team else None
        with col_home:
            home_team_name = st.selectbox("Home Team:", options=team_names, key="home_team_manual")
            home_team = next((t for t in teams if t['TEAM_NAME'] == home_team_name), None)
            home_id = home_team['TEAM_ID'] if home_team else None

# Check if teams are selected
if home_id is None or away_id is None:
    st.warning("⚠️ Please select both teams to view matchup data.")
    st.stop()

# Get matchup stats
@st.cache_data
def get_cached_matchup_stats(home_id, away_id):
    """Cache matchup stats"""
    return functions.get_matchup_stats(home_id, away_id)

stats = get_cached_matchup_stats(home_id, away_id)

# Sidebar for selecting the tab
tab = st.radio("Select Tab", ('Core Stats', 'Shooting', 'Players', 'Lineups'))

stat_font_size = 20
rank_font_size = 16
border = 1
padding = 8
border_radius = 5
title_header_background_color = 'f9f9f9'
body_header_background_color = 'f9f9f9'
body_background_color = 'white'

if tab == 'Core Stats':


    # Create the HTML for the header
    header_html = f"""
    <div style="display: flex; align-items: center; justify-content: space-between; padding: {padding}px; border: 1px solid black; background-color: #{body_header_background_color}; font-family: Arial, sans-serif;">
      <!-- Away Team Logo -->
      <a href="{stats['away_logo_link']}" style="display: inline-block;">
        <img src="{stats['away_logo_link']}" alt="Away Team Logo" style="height: 150px; width: auto;" />
      </a>
    
      <!-- Team Names -->
      <div style="display: flex; flex-direction: column; align-items: center; flex-grow: 1; text-align: center;">
        <span style="font-size: 30px; font-weight: bold;">{stats['game_title']}</span>
      </div>
    
      <!-- Home Team Logo -->
      <a href="{stats['home_logo_link']}" style="display: inline-block;">
        <img src="{stats['home_logo_link']}" alt="Home Team Logo" style="height: 150px; width: auto;" />
    </div>
    <br>
    """
    # Render the HTML in Streamlit
    st.markdown(header_html, unsafe_allow_html=True)

    # Create the HTML table with column spanners
    html_table_2 = f"""
    <table style="width:50%; border: {border}px solid black; border-collapse: collapse; text-align: center">
      <thead>
        <!-- First sticky row -->
        <tr>
          <th style="border: 1px solid black; background-color: #{body_header_background_color}; position: sticky; top: 0; z-index: 3; height: 175px; text-align: bottom; vertical-align: middle; box-shadow: 0px 2px 0px 0px black;"></th>
          <th colspan="2" style="border: 1px solid black; background-color: #{body_header_background_color}; position: sticky; top: 0; z-index: 3; height: 175px; text-align: bottom; vertical-align: bottom; box-shadow: 0px 2px 0px 0px black;">
              <img src="{stats['away_logo_link']}" alt="Away Team Logo" style="height: 100px; width: auto;"/>
          </th>
          <th colspan="1" style="border: 1px solid black; background-color: #{body_header_background_color}; position: sticky; top: 0; z-index: 3; height: 175px; text-align: bottom; vertical-align: bottom; box-shadow: 0px 2px 0px 0px black;">
              <img src="{stats['nba_logo']}" alt="NBA Team Logo" style="height: 100px; width: auto;"/>
          </th>
          <th colspan="2" style="border: 1px solid black; background-color: #{body_header_background_color}; position: sticky; top: 0; z-index: 3; height: 175px; text-align: bottom; vertical-align: bottom; box-shadow: 0px 2px 0px 0px black;">
              <img src="{stats['home_logo_link']}" alt="Home Team Logo" style="height: 100px; width: auto;"/>
          </th>
        </tr>
        <!-- Second sticky row -->
        <tr>
          <th style="border: 1px solid black; position: sticky; top: 175px; z-index: 2; background-color: #{body_header_background_color}; text-align: center; vertical-align: middle; box-shadow: 0px 2px 0px 0px black;">Metric</th>
          <th style="border: 1px solid black; position: sticky; top: 175px; z-index: 2; background-color: #{body_header_background_color}; text-align: center; vertical-align: middle; box-shadow: 0px 2px 0px 0px black;">Season</th>
          <th style="border: 1px solid black; position: sticky; top: 175px; z-index: 2; background-color: #{body_header_background_color}; text-align: center; vertical-align: middle; box-shadow: 0px 2px 0px 0px black;">Last 5</th>
          <th style="border: 1px solid black; position: sticky; top: 175px; z-index: 2; background-color: #{body_header_background_color}; text-align: center; vertical-align: middle; box-shadow: 0px 2px 0px 0px black;">League Average</th>
          <th style="border: 1px solid black; position: sticky; top: 175px; z-index: 2; background-color: #{body_header_background_color}; text-align: center; vertical-align: middle; box-shadow: 0px 2px 0px 0px black;">Season</th>
          <th style="border: 1px solid black; position: sticky; top: 175px; z-index: 2; background-color: #{body_header_background_color}; text-align: center; vertical-align: middle; box-shadow: 0px 2px 0px 0px black;">Last 5</th>
        </tr>
      </thead>
      <tbody>
      <tr>
        <td style="border: {border}px solid black;">Offensive Rating</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_ortg']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_ortg_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_away_team_ortg']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_away_team_ortg_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['la_ortg']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{stats['l5_la_ortg']}</strong></p>
        </td>
         <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_ortg']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_ortg_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_home_team_ortg']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_home_team_ortg_rank']}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Defensive Rating</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_drtg']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_drtg_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_away_team_drtg']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_away_team_drtg_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['la_drtg']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{stats['l5_la_drtg']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_drtg']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_drtg_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_home_team_drtg']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_home_team_drtg_rank']}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Net Rating</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_net']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_net_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_away_team_net']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_away_team_net_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['la_net']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{stats['l5_la_net']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_net']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_net_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_home_team_net']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_home_team_net_rank']}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Offensive Rebound %</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_oreb']*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_oreb_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['l5_away_team_oreb']*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_away_team_oreb_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['la_oreb']*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{round(stats['l5_la_oreb']*100, 3)}%</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_oreb']*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_oreb_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['l5_home_team_oreb']*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_home_team_oreb_rank']}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Defensive Rebound %</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_dreb']*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_dreb_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['l5_away_team_dreb']*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_away_team_dreb_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['la_dreb']*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{round(stats['l5_la_dreb']*100, 3)}%</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_dreb']*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_dreb_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['l5_home_team_dreb']*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_home_team_dreb_rank']}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Rebound %</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_reb']*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_reb_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['l5_away_team_reb']*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_away_team_reb_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['la_reb']*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{round(stats['l5_la_reb']*100, 3)}%</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_reb']*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_reb_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['l5_home_team_reb']*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_home_team_reb_rank']}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Points in the Paint - Offense</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_pitp_off']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_pitp_off_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_away_team_pitp_off']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_away_team_pitp_off_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['la_pitp_off']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{stats['l5_la_pitp_off']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_pitp_off']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_pitp_off_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_home_team_pitp_off']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_home_team_pitp_off_rank']}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Points in the Paint - Defense</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_pitp_def']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_pitp_def_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_away_team_pitp_def']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_away_team_pitp_def_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['la_pitp_def']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{stats['l5_la_pitp_def']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_pitp_def']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_pitp_def_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_home_team_pitp_def']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_home_team_pitp_def_rank']}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Points in the Paint - Differential</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_pitp_diff']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_pitp_diff_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_away_team_pitp_diff']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_away_team_pitp_diff_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['la_pitp_diff']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{stats['l5_la_pitp_diff']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_pitp_diff']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_pitp_diff_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_home_team_pitp_diff']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_home_team_pitp_diff_rank']}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">2nd Chance Points - Offense</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_2c_off']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_2c_off_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_away_team_2c_off']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_away_team_2c_off_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['la_2c_off']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{stats['l5_la_2c_off']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_2c_off']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_2c_off_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_home_team_2c_off']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_home_team_2c_off_rank']}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">2nd Chance Points - Defense</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_2c_def']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_2c_def_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_away_team_2c_def']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_away_team_2c_def_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['la_2c_def']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{stats['l5_la_2c_def']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_2c_def']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_2c_def_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_home_team_2c_def']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_home_team_2c_def_rank']}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">2nd Chance Points - Differential</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_2c_diff']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_2c_diff_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_away_team_2c_diff']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_away_team_2c_diff_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['la_2c_diff']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{stats['l5_la_2c_diff']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_2c_diff']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_2c_diff_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_home_team_2c_diff']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_home_team_2c_diff_rank']}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Fast Break Points - Offense</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_fb_off']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_fb_off_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_away_team_fb_off']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_away_team_fb_off_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['la_fb_off']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{stats['l5_la_fb_off']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_fb_off']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_fb_off_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_home_team_fb_off']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_home_team_fb_off_rank']}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Fast Break Points - Defense</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_fb_def']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_fb_def_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_away_team_fb_def']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_away_team_fb_def_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['la_fb_def']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{stats['l5_la_fb_def']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_fb_def']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_fb_def_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_home_team_fb_def']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_home_team_fb_def_rank']}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Fast Break Points - Differential</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_fb_diff']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_fb_diff_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_away_team_fb_diff']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_away_team_fb_diff_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['la_fb_diff']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{stats['l5_la_fb_diff']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_fb_diff']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_fb_diff_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_home_team_fb_diff']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_home_team_fb_diff_rank']}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Pace</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_pace']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_pace_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_away_team_pace']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_away_team_pace_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['la_pace']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{stats['l5_la_pace']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_pace']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_pace_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_home_team_pace']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_home_team_pace_rank']}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Assists</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_ast']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_ast_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_away_team_ast']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_away_team_ast_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['la_ast']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{stats['l5_la_ast']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_ast']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_ast_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_home_team_ast']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_home_team_ast_rank']}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Assist Percentage</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_ast_pct']*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_ast_pct_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['l5_away_team_ast_pct']*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_away_team_ast_pct_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['la_ast_pct']*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{round(stats['l5_la_ast_pct']*100, 3)}%</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_ast_pct']*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_ast_pct_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['l5_home_team_ast_pct']*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_home_team_ast_pct_rank']}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Turnovers</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_tov']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_tov_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_away_team_tov']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_away_team_tov_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['la_tov']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{stats['l5_la_tov']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_tov']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_tov_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_home_team_tov']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_home_team_tov_rank']}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Turnover Percentage</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_tov_pct']*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_tov_pct_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['l5_away_team_tov_pct']*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_away_team_tov_pct_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['la_tov_pct']*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{round(stats['l5_la_tov_pct']*100, 3)}%</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_tov_pct']*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_tov_pct_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['l5_home_team_tov_pct']*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_home_team_tov_pct_rank']}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Opp. Turnover Percentage</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_opp_tov_pct']*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_opp_tov_pct_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['l5_away_team_opp_tov_pct']*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_away_team_opp_tov_pct_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['la_opp_tov_pct']*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{round(stats['l5_la_opp_tov_pct']*100, 3)}%</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_opp_tov_pct']*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_opp_tov_pct_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['l5_home_team_opp_tov_pct']*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_home_team_opp_tov_pct_rank']}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Assist-to-Turnover Ratio</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_ast_tov']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_ast_tov_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_away_team_ast_tov']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_away_team_ast_tov_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['la_ast_tov']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{stats['l5_la_ast_tov']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_ast_tov']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_ast_tov_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_home_team_ast_tov']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_home_team_ast_tov_rank']}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Points off Turnovers</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_pts_off_tov']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_pts_off_tov_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_away_team_pts_off_tov']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_away_team_pts_off_tov_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['la_pts_off_tov']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{stats['l5_la_pts_off_tov']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_pts_off_tov']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_pts_off_tov_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_home_team_pts_off_tov']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_home_team_pts_off_tov_rank']}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Opp. Points off Turnovers</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_opp_pts_off_tov']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_opp_pts_off_tov_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_away_team_opp_pts_off_tov']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_away_team_opp_pts_off_tov_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['la_opp_pts_off_tov']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{stats['l5_la_opp_pts_off_tov']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_opp_pts_off_tov']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_opp_pts_off_tov_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_home_team_opp_pts_off_tov']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_home_team_opp_pts_off_tov_rank']}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Points off Turnovers - Differential</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_pts_off_tov_diff']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_pts_off_tov_diff_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_away_team_pts_off_tov_diff']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_away_team_pts_off_tov_diff_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['la_pts_off_tov_diff']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{stats['l5_la_pts_off_tov_diff']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_pts_off_tov_diff']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_pts_off_tov_diff_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_home_team_pts_off_tov_diff']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_home_team_pts_off_tov_diff_rank']}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Starters Scoring</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_starters_scoring']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_starters_scoring_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_away_team_starters_scoring']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_away_team_starters_scoring_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['la_starters_scoring']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{stats['l5_la_starters_scoring']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_starters_scoring']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_starters_scoring_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_home_team_starters_scoring']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_home_team_starters_scoring_rank']}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Bench Scoring</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_bench_scoring']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_bench_scoring_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_away_team_bench_scoring']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_away_team_bench_scoring_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['la_bench_scoring']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{stats['l5_la_bench_scoring']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_bench_scoring']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_bench_scoring_rank']}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['l5_home_team_bench_scoring']}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['l5_home_team_bench_scoring_rank']}</strong></p>
        </td>
      </tr>  
      </tbody>
    </table>
    """

    # Render the table in Streamlit
    st.markdown(html_table_2, unsafe_allow_html=True)

elif tab == 'Shooting':

    # Create the HTML for the header
    header_html_shooting = f"""
        <div style="display: flex; align-items: center; justify-content: space-between; padding: {padding}px; border: 1px solid black; background-color: #{body_header_background_color}; font-family: Arial, sans-serif;">
          <!-- Away Team Logo -->
          <a href="{stats['away_logo_link']}" style="display: inline-block;">
            <img src="{stats['away_logo_link']}" alt="Away Team Logo" style="height: 150px; width: auto;" />
          </a>

          <!-- Team Names -->
          <div style="display: flex; flex-direction: column; align-items: center; flex-grow: 1; text-align: center;">
            <span style="font-size: 30px; font-weight: bold;">{stats['game_title']}</span>
          </div>

          <!-- Home Team Logo -->
          <a href="{stats['home_logo_link']}" style="display: inline-block;">
            <img src="{stats['home_logo_link']}" alt="Home Team Logo" style="height: 150px; width: auto;" />
        </div>
        <br>
        """
    # Render the HTML in Streamlit
    st.markdown(header_html_shooting, unsafe_allow_html=True)

    html_table_shooting = f"""
        <table style="width:75%; border: {border}px solid black; border-collapse: collapse; text-align: center">
          <thead>
            <!-- First sticky row -->
                <tr>
                  <th style="border: 1px solid black; background-color: #{body_header_background_color}; position: sticky; top: 0; z-index: 3; height: 175px; text-align: bottom; vertical-align: middle; box-shadow: 0px 2px 0px 0px black;"></th>
                  <th colspan="3" style="border: 1px solid black; background-color: #{body_header_background_color}; position: sticky; top: 0; z-index: 3; height: 175px; text-align: bottom; vertical-align: bottom; box-shadow: 0px 2px 0px 0px black;">
                      <img src="{stats['away_logo_link']}" alt="Away Team Logo" style="height: 100px; width: auto;"/>
                  </th>
                  <th colspan="1" style="border: 1px solid black; background-color: #{body_header_background_color}; position: sticky; top: 0; z-index: 3; height: 175px; text-align: bottom; vertical-align: bottom; box-shadow: 0px 2px 0px 0px black;">
                      <img src="{stats['nba_logo']}" alt="NBA Team Logo" style="height: 100px; width: auto;"/>
                  </th>
                  <th colspan="3" style="border: 1px solid black; background-color: #{body_header_background_color}; position: sticky; top: 0; z-index: 3; height: 175px; text-align: bottom; vertical-align: bottom; box-shadow: 0px 2px 0px 0px black;">
                      <img src="{stats['home_logo_link']}" alt="Home Team Logo" style="height: 100px; width: auto;"/>
                  </th>
                </tr>
                <!-- Second sticky row -->
                <tr>
                  <th style="border: 1px solid black; position: sticky; top: 175px; z-index: 2; background-color: #{body_header_background_color}; text-align: center; vertical-align: middle; box-shadow: 0px 2px 0px 0px black; width: 130px">Metric</th>
                  <th style="border: 1px solid black; position: sticky; top: 175px; z-index: 2; background-color: #{body_header_background_color}; text-align: center; vertical-align: middle; box-shadow: 0px 2px 0px 0px black; width: 100px;">Team</th>
                  <th style="border: 1px solid black; position: sticky; top: 175px; z-index: 2; background-color: #{body_header_background_color}; text-align: center; vertical-align: middle; box-shadow: 0px 2px 0px 0px black; width: 100px">Opponent</th>
                  <th style="border: 1px solid black; position: sticky; top: 175px; z-index: 2; background-color: #{body_header_background_color}; text-align: center; vertical-align: middle; box-shadow: 0px 2px 0px 0px black; width: 100px">Difference</th>
                  <th style="border: 1px solid black; position: sticky; top: 175px; z-index: 2; background-color: #{body_header_background_color}; text-align: center; vertical-align: middle; box-shadow: 0px 2px 0px 0px black; width: 80px">League Average</th>
                  <th style="border: 1px solid black; position: sticky; top: 175px; z-index: 2; background-color: #{body_header_background_color}; text-align: center; vertical-align: middle; box-shadow: 0px 2px 0px 0px black; width: 100px">Team</th>
                  <th style="border: 1px solid black; position: sticky; top: 175px; z-index: 2; background-color: #{body_header_background_color}; text-align: center; vertical-align: middle; box-shadow: 0px 2px 0px 0px black; width: 100px">Opponent</th>
                  <th style="border: 1px solid black; position: sticky; top: 175px; z-index: 2; background-color: #{body_header_background_color}; text-align: center; vertical-align: middle; box-shadow: 0px 2px 0px 0px black; width: 100px">Difference</th>
                </tr>
          </thead>
          <tbody>
            <tr>
                <td style="border: {border}px solid black;">Field Goals Made</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_fgm']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_fgm_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_opp_fgm']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_opp_fgm_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_diff_fgm']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_diff_fgm_rank']}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['la_fgm']}</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_fgm']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_fgm_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_opp_fgm']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_opp_fgm_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_diff_fgm']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_diff_fgm_rank']}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Field Goals Attempted</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_fga']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_fga_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_opp_fga']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_opp_fga_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_diff_fga']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_diff_fga_rank']}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['la_fga']}</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_fga']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_fga_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_opp_fga']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_opp_fga_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_diff_fga']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_diff_fga_rank']}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Field Goal Percentage</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_fg_pct']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_fg_pct_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_opp_fg_pct']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_opp_fg_pct_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_diff_fg_pct']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_diff_fg_pct_rank']}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['la_fg_pct']*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_fg_pct']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_fg_pct_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_opp_fg_pct']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_opp_fg_pct_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_diff_fg_pct']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_diff_fg_pct_rank']}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">2PT Field Goals Made</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_2pt']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_2pt_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_opp_2pt']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_opp_2pt_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_diff_2pt']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_diff_2pt_rank']}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['la_2pt']}</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_2pt']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_2pt_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_opp_2pt']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_opp_2pt_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_diff_2pt']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_diff_2pt_rank']}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">2PT Field Goals Attempted</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_2pa']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_2pa_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_opp_2pa']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_opp_2pa_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_diff_2pa']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_diff_2pa_rank']}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['la_2pa']}</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_2pa']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_2pa_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_opp_2pa']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_opp_2pa_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_diff_2pa']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_diff_2pa_rank']}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">2PT Field Goal Percentage</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_2pt_pct']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_2pt_pct_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_opp_2pt_pct']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_opp_2pt_pct_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_diff_2pt_pct']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_diff_2pt_pct_rank']}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['la_2pt_pct']*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_2pt_pct']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_2pt_pct_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_opp_2pt_pct']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_opp_2pt_pct_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_diff_2pt_pct']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_diff_2pt_pct_rank']}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">3PT Field Goals Made</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_3pt']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_3pt_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_opp_3pt']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_opp_3pt_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_diff_3pt']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_diff_3pt_rank']}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['la_3pt']}</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_3pt']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_3pt_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_opp_3pt']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_opp_3pt_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_diff_3pt']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_diff_3pt_rank']}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">3PT Field Goals Attempted</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_3pa']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_3pa_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_opp_3pa']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_opp_3pa_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_diff_3pa']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_diff_3pa_rank']}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['la_3pa']}</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_3pa']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_3pa_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_opp_3pa']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_opp_3pa_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_diff_3pa']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_diff_3pa_rank']}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">3PT Field Goal Percentage</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_3pt_pct']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_3pt_pct_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_opp_3pt_pct']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_opp_3pt_pct_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_diff_3pt_pct']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_diff_3pt_pct_rank']}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['la_3pt_pct']*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_3pt_pct']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_3pt_pct_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_opp_3pt_pct']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_opp_3pt_pct_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_diff_3pt_pct']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_diff_3pt_pct_rank']}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Free Throws Made</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_ftm']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_ftm_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_opp_ftm']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_opp_ftm_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_diff_ftm']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_diff_ftm_rank']}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['la_ftm']}</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_ftm']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_ftm_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_opp_ftm']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_opp_ftm_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_diff_ftm']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_diff_ftm_rank']}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Free Throws Attempted</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_fta']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_fta_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_opp_fta']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_opp_fta_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['away_team_diff_fta']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_diff_fta_rank']}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['la_fta']}</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_fta']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_fta_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_opp_fta']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_opp_fta_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{stats['home_team_diff_fta']}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_diff_fta_rank']}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Free Throw Percentage</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_ft_pct']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_ft_pct_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_opp_ft_pct']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_opp_ft_pct_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_diff_ft_pct']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_diff_ft_pct_rank']}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['la_ft_pct']*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_ft_pct']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_ft_pct_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_opp_ft_pct']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_opp_ft_pct_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_diff_ft_pct']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_diff_ft_pct_rank']}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Rim Frequency</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_rim_freq']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_rim_freq_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_opp_rim_freq']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_opp_rim_freq_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_diff_rim_freq']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_diff_rim_freq_rank']}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['la_rim_freq']*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_rim_freq']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_rim_freq_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_opp_rim_freq']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_opp_rim_freq_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_diff_rim_freq']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_diff_rim_freq_rank']}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Rim Accuracy</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_rim_acc']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_rim_acc_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_opp_rim_acc']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_opp_rim_acc_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_diff_rim_acc']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_diff_rim_acc_rank']}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['la_rim_acc']*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_rim_acc']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_rim_acc_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_opp_rim_acc']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_opp_rim_acc_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_diff_rim_acc']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_diff_rim_acc_rank']}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Short Mid-Range Frequency</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_smr_freq']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_smr_freq_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_opp_smr_freq']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_opp_smr_freq_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_diff_smr_freq']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_diff_smr_freq_rank']}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['la_smr_freq']*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_smr_freq']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_smr_freq_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_opp_smr_freq']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_opp_smr_freq_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_diff_smr_freq']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_diff_smr_freq_rank']}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Short Mid-Range Accuracy</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_smr_acc']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_smr_acc_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_opp_smr_acc']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_opp_smr_acc_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_diff_smr_acc']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_diff_smr_acc_rank']}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['la_smr_acc']*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_smr_acc']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_smr_acc_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_opp_smr_acc']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_opp_smr_acc_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_diff_smr_acc']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_diff_smr_acc_rank']}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Long Mid-Range Frequency</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_lmr_freq']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_lmr_freq_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_opp_lmr_freq']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_opp_lmr_freq_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_diff_lmr_freq']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_diff_lmr_freq_rank']}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['la_lmr_freq']*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_lmr_freq']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_lmr_freq_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_opp_lmr_freq']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_opp_lmr_freq_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_diff_lmr_freq']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_diff_lmr_freq_rank']}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Long Mid-Range Accuracy</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_lmr_acc']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_lmr_acc_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_opp_lmr_acc']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_opp_lmr_acc_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_diff_lmr_acc']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_diff_lmr_acc_rank']}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['la_lmr_acc']*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_lmr_acc']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_lmr_acc_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_opp_lmr_acc']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_opp_lmr_acc_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_diff_lmr_acc']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_diff_lmr_acc_rank']}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Above the Break 3 Frequency</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_atb3_freq']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_atb3_freq_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_opp_atb3_freq']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_opp_atb3_freq_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_diff_atb3_freq']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_diff_atb3_freq_rank']}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['la_atb3_freq']*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_atb3_freq']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_atb3_freq_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_opp_atb3_freq']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_opp_atb3_freq_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_diff_atb3_freq']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_diff_atb3_freq_rank']}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Above the Break 3 Accuracy</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_atb3_acc']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_atb3_acc_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_opp_atb3_acc']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_opp_atb3_acc_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_diff_atb3_acc']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_diff_atb3_acc_rank']}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['la_atb3_acc']*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_atb3_acc']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_atb3_acc_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_opp_atb3_acc']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_opp_atb3_acc_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_diff_atb3_acc']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_diff_atb3_acc_rank']}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Corner 3 Frequency</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_c3_freq']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_c3_freq_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_opp_c3_freq']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_opp_c3_freq_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_diff_c3_freq']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_diff_c3_freq_rank']}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['la_c3_freq']*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_c3_freq']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_c3_freq_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_opp_c3_freq']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_opp_c3_freq_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_diff_c3_freq']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_diff_c3_freq_rank']}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Corner 3 Accuracy</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_c3_acc']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_c3_acc_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_opp_c3_acc']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_opp_c3_acc_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['away_team_diff_c3_acc']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['away_team_diff_c3_acc_rank']}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['la_c3_acc']*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_c3_acc']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_c3_acc_rank']}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_opp_c3_acc']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_opp_c3_acc_rank']}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(stats['home_team_diff_c3_acc']*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{stats['home_team_diff_c3_acc_rank']}</strong></p>
                </td>
            </tr>
          </tbody>
        </table>
    """

    # Render the table in Streamlit
    st.markdown(html_table_shooting, unsafe_allow_html=True)


elif tab in ('Players', 'Lineups'):
    st.write("Still Under Development")


