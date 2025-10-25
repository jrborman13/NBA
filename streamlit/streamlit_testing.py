import streamlit as st
import streamlit_testing_functions as functions

import altair as alt
import pandas as pd
import streamlit as st

# Clear all caches
st.cache_data.clear()

# import plotly.graph_objects as go
# import matplotlib.pyplot as plt
#
# # Create a DataFrame for plotting
# data = pd.DataFrame({
#     'x': range(10),
#     'y1': [i * 1.5 for i in range(10)],
#     'y2': [i * 2.5 for i in range(10)],
#     'y3': [i * 3.5 for i in range(10)]
# })
#
# # Create individual line charts
# chart1 = alt.Chart(data).mark_line().encode(x='x', y='y1', tooltip=['x', 'y1'])
# chart2 = alt.Chart(data).mark_line().encode(x='x', y='y2', tooltip=['x', 'y2'])
# chart3 = alt.Chart(data).mark_line().encode(x='x', y='y3', tooltip=['x', 'y3'])
#
# # Create individual line plots
# fig1 = go.Figure(go.Scatter(x=[1, 2, 3], y=[4, 5, 6], mode='lines', name='Line 1'))
# fig2 = go.Figure(go.Scatter(x=[1, 2, 3], y=[6, 5, 4], mode='lines', name='Line 2'))
# fig3 = go.Figure(go.Scatter(x=[1, 2, 3], y=[4, 6, 5], mode='lines', name='Line 3'))
#
# # Create subplots
# fig, axes = plt.subplots(1, 3, figsize=(15, 5))
# axes[0].plot([1, 2, 3], [4, 5, 6])
# axes[0].set_title("Line 1")
# axes[1].plot([1, 2, 3], [6, 5, 4])
# axes[1].set_title("Line 2")
# axes[2].plot([1, 2, 3], [4, 6, 5])
# axes[2].set_title("Line 3")


st.set_page_config(layout="wide")
st.title("NBA Matchup Data App")
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

# # Layout charts in Streamlit
# col1, col2, col3 = st.columns(3)
# col1.altair_chart(chart1, use_container_width=True)
# col2.altair_chart(chart2, use_container_width=True)
# col3.altair_chart(chart3, use_container_width=True)
#
# # Layout charts in Streamlit
# col1, col2, col3 = st.columns(3)
# col1.plotly_chart(fig1, use_container_width=True)
# col2.plotly_chart(fig2, use_container_width=True)
# col3.plotly_chart(fig3, use_container_width=True)
#
# # Render in Streamlit
# st.pyplot(fig)


    # Create the HTML for the header
    header_html = f"""
    <div style="display: flex; align-items: center; justify-content: space-between; padding: {padding}px; border: 1px solid black; background-color: #{body_header_background_color}; font-family: Arial, sans-serif;">
      <!-- Away Team Logo -->
      <a href="{functions.away_logo_link}" style="display: inline-block;">
        <img src="{functions.away_logo_link}" alt="Away Team Logo" style="height: 150px; width: auto;" />
      </a>
    
      <!-- Team Names -->
      <div style="display: flex; flex-direction: column; align-items: center; flex-grow: 1; text-align: center;">
        <span style="font-size: 30px; font-weight: bold;">{functions.game_title}</span>
      </div>
    
      <!-- Home Team Logo -->
      <a href="{functions.home_logo_link}" style="display: inline-block;">
        <img src="{functions.home_logo_link}" alt="Home Team Logo" style="height: 150px; width: auto;" />
    </div>
    <br>
    """
    # Render the HTML in Streamlit
    st.markdown(header_html, unsafe_allow_html=True)

    # # Define variables for the away and home team logos and league average data
    # league_average = "50%"  # Example value for league average
    #
    # # Function to calculate background color based on rank (1 = green, 30 = red)
    # def get_color(rank):
    #     # Normalize rank into two halves: 1 to 15 and 15 to 30
    #     if rank <= 15:
    #         # Green (1) to White (15)
    #         normalized = (rank - 1) / 14  # Map 1 -> 0, 15 -> 1
    #         red = int(255 * normalized)
    #         green = 255
    #         blue = int(255 * normalized)
    #     else:
    #         # White (15) to Red (30)
    #         normalized = (rank - 15) / 15  # Map 15 -> 0, 30 -> 1
    #         red = 255
    #         green = int(255 * (1 - normalized))
    #         blue = int(255 * (1 - normalized))
    #     return f"rgb({red}, {green}, {blue})"  # Return RGB color
    #
    # # Define example metrics with ranks
    # metrics = [
    #     {"metric": "Offense", "rank_away": 5, "rank_home": 25},
    #     {"metric": "Defense", "rank_away": 10, "rank_home": 20},
    # ]
    #
    # # Generate table rows dynamically
    # rows = ""
    # for data in metrics:
    #     away_color = get_color(data["rank_away"])
    #     home_color = get_color(data["rank_home"])
    #     rows += f"""
    #     <tr>
    #         <td style="border: 1px solid black; padding: {padding}px; text-align: left; font-family: 'IBM Plex Sans', sans-serif;">{data['metric']}</td>
    #         <td style="border: 1px solid black; background-color: {away_color}; font-family: 'IBM Plex Sans', sans-serif;">{data['rank_away']}</td>
    #         <td style="border: 1px solid black; background-color: {away_color}; font-family: 'IBM Plex Sans', sans-serif;">Data {data['rank_away']}</td>
    #         <td style="border: 1px solid black; text-align: center; font-family: 'IBM Plex Sans', sans-serif;">{league_average}</td>
    #         <td style="border: 1px solid black; background-color: {home_color}; font-family: 'IBM Plex Sans', sans-serif;">{data['rank_home']}</td>
    #         <td style="border: 1px solid black; background-color: {home_color}; font-family: 'IBM Plex Sans', sans-serif;">Data {data['rank_home']}</td>
    #     </tr>
    #     """
    #
    # # Create the full HTML table
    # html_table = f"""
    # <!DOCTYPE html>
    # <html>
    # <head>
    # <style>
    #     table {{
    #         width: 100%;
    #         border-collapse: collapse;
    #         text-align: center;
    #         font-family: IBM Plex Sans, sans-serif;
    #     }}
    #     th, td {{
    #         border: 1px solid black;
    #         padding: {padding}px;
    #         font-family: IBM Plex Sans, sans-serif;
    #     }}
    #     th {{
    #         background-color: #{body_header_background_color};
    #         font-family: IBM Plex Sans, sans-serif;
    #     }}
    # </style>
    # </head>
    # <body>
    # <table>
    #   <tr>
    #     <th style="border: 1px solid black;">Metric</th>
    #     <th colspan="2" style="border: 1px solid black;">
    #         <img src="{functions.away_logo_link}" alt="Away Team Logo" style="height: 50px; width: auto;"/>
    #     </th>
    #     <th style="border: 1px solid black;">League Average</th>
    #     <th colspan="2" style="border: 1px solid black;">
    #         <img src="{functions.home_logo_link}" alt="Home Team Logo" style="height: 50px; width: auto;"/>
    #     </th>
    #   </tr>
    #   <tr>
    #     <th>Metric</th>
    #     <th>Rank</th>
    #     <th>Col 1</th>
    #     <th>Avg</th>
    #     <th>Rank</th>
    #     <th>Col 2</th>
    #   </tr>
    #   {rows}
    # </table>
    # </body>
    # </html>
    # """
    #
    # # Render the HTML table in Streamlit using st.components.v1.html
    # st.components.v1.html(html_table, height=250)

    # Create the HTML table with column spanners
    html_table_2 = f"""
    <table style="width:50%; border: {border}px solid black; border-collapse: collapse; text-align: center">
      <thead>
        <!-- First sticky row -->
        <tr>
          <th style="border: 1px solid black; background-color: #{body_header_background_color}; position: sticky; top: 0; z-index: 3; height: 175px; text-align: bottom; vertical-align: middle; box-shadow: 0px 2px 0px 0px black;"></th>
          <th colspan="2" style="border: 1px solid black; background-color: #{body_header_background_color}; position: sticky; top: 0; z-index: 3; height: 175px; text-align: bottom; vertical-align: bottom; box-shadow: 0px 2px 0px 0px black;">
              <img src="{functions.away_logo_link}" alt="Away Team Logo" style="height: 100px; width: auto;"/>
          </th>
          <th colspan="1" style="border: 1px solid black; background-color: #{body_header_background_color}; position: sticky; top: 0; z-index: 3; height: 175px; text-align: bottom; vertical-align: bottom; box-shadow: 0px 2px 0px 0px black;">
              <img src="{functions.nba_logo}" alt="NBA Team Logo" style="height: 100px; width: auto;"/>
          </th>
          <th colspan="2" style="border: 1px solid black; background-color: #{body_header_background_color}; position: sticky; top: 0; z-index: 3; height: 175px; text-align: bottom; vertical-align: bottom; box-shadow: 0px 2px 0px 0px black;">
              <img src="{functions.home_logo_link}" alt="Home Team Logo" style="height: 100px; width: auto;"/>
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
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_ortg}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_ortg_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_ortg}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_ortg_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_ortg}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_ortg}</strong></p>
        </td>
         <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_ortg}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_ortg_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_ortg}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_ortg_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Defensive Rating</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_drtg}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_drtg_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_drtg}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_drtg_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_drtg}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_drtg}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_drtg}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_drtg_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_drtg}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_drtg_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Net Rating</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_net}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_net_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_net}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_net_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_net}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_net}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_net}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_net_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_net}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_net_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Offensive Rebound %</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_oreb*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_oreb_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.l5_away_team_oreb*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_oreb_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_oreb*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{round(functions.l5_la_oreb*100, 3)}%</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_oreb*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_oreb_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.l5_home_team_oreb*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_oreb_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Defensive Rebound %</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_dreb*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_dreb_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.l5_away_team_dreb*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_dreb_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_dreb*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{round(functions.l5_la_dreb*100, 3)}%</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_dreb*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_dreb_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.l5_home_team_dreb*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_dreb_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Rebound %</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_reb*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_reb_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.l5_away_team_reb*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_reb_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_reb*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{round(functions.l5_la_reb*100, 3)}%</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_reb*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_reb_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.l5_home_team_reb*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_reb_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Points in the Paint - Offense</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_pitp_off}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_pitp_off_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_pitp_off}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_pitp_off_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_pitp_off}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_pitp_off}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_pitp_off}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_pitp_off_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_pitp_off}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_pitp_off_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Points in the Paint - Defense</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_pitp_def}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_pitp_def_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_pitp_def}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_pitp_def_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_pitp_def}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_pitp_def}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_pitp_def}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_pitp_def_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_pitp_def}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_pitp_def_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Points in the Paint - Differential</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_pitp_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_pitp_diff_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_pitp_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_pitp_diff_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_pitp_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_pitp_diff}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_pitp_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_pitp_diff_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_pitp_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_pitp_diff_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">2nd Chance Points - Offense</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_2c_off}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_2c_off_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_2c_off}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_2c_off_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_2c_off}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_2c_off}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_2c_off}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_2c_off_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_2c_off}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_2c_off_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">2nd Chance Points - Defense</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_2c_def}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_2c_def_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_2c_def}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_2c_def_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_2c_def}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_2c_def}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_2c_def}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_2c_def_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_2c_def}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_2c_def_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">2nd Chance Points - Differential</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_2c_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_2c_diff_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_2c_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_2c_diff_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_2c_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_2c_diff}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_2c_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_2c_diff_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_2c_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_2c_diff_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Fast Break Points - Offense</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_fb_off}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_fb_off_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_fb_off}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_fb_off_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_fb_off}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_fb_off}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_fb_off}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_fb_off_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_fb_off}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_fb_off_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Fast Break Points - Defense</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_fb_def}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_fb_def_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_fb_def}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_fb_def_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_fb_def}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_fb_def}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_fb_def}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_fb_def_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_fb_def}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_fb_def_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Fast Break Points - Differential</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_fb_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_fb_diff_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_fb_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_fb_diff_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_fb_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_fb_diff}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_fb_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_fb_diff_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_fb_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_fb_diff_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Pace</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_pace}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_pace_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_pace}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_pace_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_pace}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_pace}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_pace}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_pace_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_pace}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_pace_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Assists</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_ast}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_ast_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_ast}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_ast_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_ast}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_ast}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_ast}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_ast_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_ast}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_ast_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Assist Percentage</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_ast_pct*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_ast_pct_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.l5_away_team_ast_pct*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_ast_pct_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_ast_pct*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{round(functions.l5_la_ast_pct*100, 3)}%</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_ast_pct*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_ast_pct_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.l5_home_team_ast_pct*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_ast_pct_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Turnovers</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_tov_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_tov_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_tov}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_tov_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_tov_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Turnover Percentage</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_tov_pct*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_tov_pct_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.l5_away_team_tov_pct*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_tov_pct_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_tov_pct*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{round(functions.l5_la_tov_pct*100, 3)}%</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_tov_pct*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_tov_pct_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.l5_home_team_tov_pct*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_tov_pct_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Opp. Turnover Percentage</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_opp_tov_pct*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_tov_pct_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.l5_away_team_opp_tov_pct*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_opp_tov_pct_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_opp_tov_pct*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{round(functions.l5_la_opp_tov_pct*100, 3)}%</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_opp_tov_pct*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_tov_pct_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.l5_home_team_opp_tov_pct*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_opp_tov_pct_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Assist-to-Turnover Ratio</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_ast_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_ast_tov_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_ast_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_ast_tov_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_ast_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_ast_tov}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_ast_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_ast_tov_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_ast_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_ast_tov_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Points off Turnovers</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_pts_off_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_pts_off_tov_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_pts_off_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_pts_off_tov_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_pts_off_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_pts_off_tov}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_pts_off_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_pts_off_tov_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_pts_off_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_pts_off_tov_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Opp. Points off Turnovers</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_opp_pts_off_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_pts_off_tov_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_opp_pts_off_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_opp_pts_off_tov_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_opp_pts_off_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_opp_pts_off_tov}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_opp_pts_off_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_pts_off_tov_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_opp_pts_off_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_opp_pts_off_tov_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Points off Turnovers - Differential</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_pts_off_tov_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_pts_off_tov_diff_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_pts_off_tov_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_pts_off_tov_diff_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_pts_off_tov_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_pts_off_tov_diff}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_pts_off_tov_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_pts_off_tov_diff_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_pts_off_tov_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_pts_off_tov_diff_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Starters Scoring</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_starters_scoring}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_starters_scoring_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_starters_scoring}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_starters_scoring_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_starters_scoring}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_starters_scoring}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_starters_scoring}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_starters_scoring_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_starters_scoring}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_starters_scoring_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Bench Scoring</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_bench_scoring}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_bench_scoring_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_bench_scoring}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_bench_scoring_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_bench_scoring}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_bench_scoring}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_bench_scoring}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_bench_scoring_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_bench_scoring}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_bench_scoring_rank}</strong></p>
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
          <a href="{functions.away_logo_link}" style="display: inline-block;">
            <img src="{functions.away_logo_link}" alt="Away Team Logo" style="height: 150px; width: auto;" />
          </a>

          <!-- Team Names -->
          <div style="display: flex; flex-direction: column; align-items: center; flex-grow: 1; text-align: center;">
            <span style="font-size: 30px; font-weight: bold;">{functions.game_title}</span>
          </div>

          <!-- Home Team Logo -->
          <a href="{functions.home_logo_link}" style="display: inline-block;">
            <img src="{functions.home_logo_link}" alt="Home Team Logo" style="height: 150px; width: auto;" />
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
                      <img src="{functions.away_logo_link}" alt="Away Team Logo" style="height: 100px; width: auto;"/>
                  </th>
                  <th colspan="1" style="border: 1px solid black; background-color: #{body_header_background_color}; position: sticky; top: 0; z-index: 3; height: 175px; text-align: bottom; vertical-align: bottom; box-shadow: 0px 2px 0px 0px black;">
                      <img src="{functions.nba_logo}" alt="NBA Team Logo" style="height: 100px; width: auto;"/>
                  </th>
                  <th colspan="3" style="border: 1px solid black; background-color: #{body_header_background_color}; position: sticky; top: 0; z-index: 3; height: 175px; text-align: bottom; vertical-align: bottom; box-shadow: 0px 2px 0px 0px black;">
                      <img src="{functions.home_logo_link}" alt="Home Team Logo" style="height: 100px; width: auto;"/>
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
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_fgm}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_fgm_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_opp_fgm}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_fgm_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_diff_fgm}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_fgm_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_fgm}</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_fgm}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_fgm_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_opp_fgm}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_fgm_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_diff_fgm}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_fgm_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Field Goals Attempted</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_fga}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_fga_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_opp_fga}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_fga_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_diff_fga}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_fga_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_fga}</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_fga}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_fga_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_opp_fga}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_fga_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_diff_fga}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_fga_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Field Goal Percentage</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_fg_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_fg_pct_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_opp_fg_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_fg_pct_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_diff_fg_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_fg_pct_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_fg_pct*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_fg_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_fg_pct_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_opp_fg_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_fg_pct_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_diff_fg_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_fg_pct_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">2PT Field Goals Made</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_2pt}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_2pt_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_opp_2pt}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_2pt_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_diff_2pt}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_2pt_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_2pt}</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_2pt}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_2pt_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_opp_2pt}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_2pt_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_diff_2pt}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_2pt_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">2PT Field Goals Attempted</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_2pa}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_2pa_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_opp_2pa}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_2pa_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_diff_2pa}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_2pa_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_2pa}</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_2pa}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_2pa_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_opp_2pa}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_2pa_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_diff_2pa}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_2pa_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">2PT Field Goal Percentage</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_2pt_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_2pt_pct_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_opp_2pt_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_2pt_pct_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_diff_2pt_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_2pt_pct_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_2pt_pct*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_2pt_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_2pt_pct_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_opp_2pt_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_2pt_pct_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_diff_2pt_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_2pt_pct_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">3PT Field Goals Made</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_3pt}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_3pt_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_opp_3pt}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_3pt_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_diff_3pt}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_3pt_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_3pt}</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_3pt}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_3pt_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_opp_3pt}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_3pt_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_diff_3pt}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_3pt_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">3PT Field Goals Attempted</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_3pa}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_3pa_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_opp_3pa}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_3pa_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_diff_3pa}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_3pa_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_3pa}</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_3pa}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_3pa_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_opp_3pa}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_3pa_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_diff_3pa}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_3pa_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">3PT Field Goal Percentage</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_3pt_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_3pt_pct_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_opp_3pt_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_3pt_pct_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_diff_3pt_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_3pt_pct_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_3pt_pct*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_3pt_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_3pt_pct_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_opp_3pt_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_3pt_pct_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_diff_3pt_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_3pt_pct_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Free Throws Made</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_ftm}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_ftm_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_opp_ftm}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_ftm_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_diff_ftm}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_ftm_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_ftm}</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_ftm}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_ftm_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_opp_ftm}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_ftm_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_diff_ftm}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_ftm_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Free Throws Attempted</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_fta}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_fta_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_opp_fta}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_fta_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_diff_fta}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_fta_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_fta}</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_fta}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_fta_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_opp_fta}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_fta_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_diff_fta}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_fta_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Free Throw Percentage</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_ft_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_ft_pct_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_opp_ft_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_ft_pct_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_diff_ft_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_ft_pct_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_ft_pct*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_ft_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_ft_pct_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_opp_ft_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_ft_pct_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_diff_ft_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_ft_pct_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Rim Frequency</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_rim_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_rim_freq_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_opp_rim_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_rim_freq_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_diff_rim_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_rim_freq_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_rim_freq*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_rim_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_rim_freq_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_opp_rim_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_rim_freq_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_diff_rim_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_rim_freq_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Rim Accuracy</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_rim_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_rim_acc_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_opp_rim_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_rim_acc_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_diff_rim_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_rim_acc_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_rim_acc*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_rim_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_rim_acc_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_opp_rim_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_rim_acc_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_diff_rim_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_rim_acc_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Short Mid-Range Frequency</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_smr_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_smr_freq_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_opp_smr_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_smr_freq_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_diff_smr_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_smr_freq_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_smr_freq*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_smr_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_smr_freq_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_opp_smr_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_smr_freq_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_diff_smr_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_smr_freq_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Short Mid-Range Accuracy</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_smr_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_smr_acc_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_opp_smr_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_smr_acc_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_diff_smr_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_smr_acc_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_smr_acc*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_smr_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_smr_acc_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_opp_smr_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_smr_acc_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_diff_smr_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_smr_acc_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Long Mid-Range Frequency</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_lmr_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_lmr_freq_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_opp_lmr_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_lmr_freq_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_diff_lmr_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_lmr_freq_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_lmr_freq*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_lmr_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_lmr_freq_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_opp_lmr_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_lmr_freq_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_diff_lmr_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_lmr_freq_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Long Mid-Range Accuracy</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_lmr_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_lmr_acc_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_opp_lmr_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_lmr_acc_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_diff_lmr_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_lmr_acc_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_lmr_acc*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_lmr_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_lmr_acc_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_opp_lmr_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_lmr_acc_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_diff_lmr_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_lmr_acc_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Above the Break 3 Frequency</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_atb3_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_atb3_freq_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_opp_atb3_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_atb3_freq_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_diff_atb3_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_atb3_freq_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_atb3_freq*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_atb3_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_atb3_freq_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_opp_atb3_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_atb3_freq_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_diff_atb3_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_atb3_freq_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Above the Break 3 Accuracy</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_atb3_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_atb3_acc_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_opp_atb3_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_atb3_acc_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_diff_atb3_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_atb3_acc_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_atb3_acc*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_atb3_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_atb3_acc_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_opp_atb3_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_atb3_acc_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_diff_atb3_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_atb3_acc_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Corner 3 Frequency</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_c3_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_c3_freq_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_opp_c3_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_c3_freq_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_diff_c3_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_c3_freq_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_c3_freq*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_c3_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_c3_freq_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_opp_c3_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_c3_freq_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_diff_c3_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_c3_freq_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Corner 3 Accuracy</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_c3_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_c3_acc_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_opp_c3_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_c3_acc_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_diff_c3_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_c3_acc_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_c3_acc*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_c3_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_c3_acc_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_opp_c3_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_c3_acc_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_diff_c3_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_c3_acc_rank}</strong></p>
                </td>
            </tr>
          </tbody>
        </table>
    """

    # Render the table in Streamlit
    st.markdown(html_table_shooting, unsafe_allow_html=True)


elif tab in ('Players', 'Lineups'):
    st.write("Still Under Development")

