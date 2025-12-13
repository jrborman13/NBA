import streamlit as st
import player_functions as pf
import pandas as pd
import nba_api.stats.endpoints
from datetime import datetime, date

st.set_page_config(layout="wide")
st.title("NBA Player Data")

# Cache players dataframe to avoid repeated API calls
@st.cache_data
def get_cached_players_dataframe():
    """Cache players dataframe from PlayerIndex endpoint"""
    return pf.get_players_dataframe()

@st.cache_data
def get_cached_player_list():
    """Cache player list from PlayerIndex endpoint"""
    return pf.get_player_list()

@st.cache_data
def get_player_name_map(player_ids_list, players_df):
    """Cache player names using the players dataframe"""
    return {pid: pf.get_player_name(pid, players_df) for pid in player_ids_list}

# Function to fetch matchups for a given date
@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_matchups_for_date(selected_date):
    """Fetch NBA matchups for a given date from the API"""
    try:
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
                matchups.append({
                    'matchup': matchup_str,
                    'away_team': away_team,
                    'home_team': home_team,
                    'away_team_id': away_team_id,
                    'home_team_id': home_team_id
                })
            return matchups, None  # Return matchups and error (None)
        else:
            return [], None  # No games on this date
    except Exception as e:
        return [], str(e)  # Return empty list and error message

# Get cached players dataframe and player list
players_df = get_cached_players_dataframe()

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
        matchup_options = ["All Matchups"] + [m['matchup'] for m in matchups]
        selected_matchup_str = st.selectbox(
            "Select Matchup:",
            options=matchup_options,
            key="matchup_selector",
            help="Select a matchup to filter players, or 'All Players' to see everyone"
        )
    else:
        selected_matchup_str = "All Players"
        if not matchup_error:  # Only show info if no error (meaning no games on this date)
            st.info("ℹ️ No games scheduled for this date. Showing all players.")

# Filter players based on selected matchup
filtered_player_ids_list = player_ids_list.copy()
selected_team_ids = None

if selected_matchup_str and selected_matchup_str != "All Players":
    # Find the selected matchup
    selected_matchup = next((m for m in matchups if m['matchup'] == selected_matchup_str), None)
    
    if selected_matchup:
        # Get team IDs for filtering
        away_team_id = selected_matchup['away_team_id']
        home_team_id = selected_matchup['home_team_id']
        selected_team_ids = [away_team_id, home_team_id]
        
        # Filter players dataframe to only include players from these teams
        if 'TEAM_ID' in players_df.columns:
            # Convert team IDs to match the format in players_df (handle both int and str)
            players_df_team_ids = players_df['TEAM_ID'].astype(int)
            filtered_players_df = players_df[players_df_team_ids.isin(selected_team_ids)]
            filtered_player_ids_list = filtered_players_df['PERSON_ID'].astype(str).tolist()
            
            # Show info about the matchup
            st.info(f"📊 Showing players from: {selected_matchup['away_team']} @ {selected_matchup['home_team']}")
        else:
            # If TEAM_ID column doesn't exist, try to filter by team abbreviation
            st.warning("⚠️ Could not filter by team ID. Showing all players.")
            filtered_player_ids_list = player_ids_list.copy()

# Set Anthony Edwards (ID: 1630162) as default selected player
default_player_id = '1630162'
default_index = 0
if default_player_id in filtered_player_ids_list:
    default_index = filtered_player_ids_list.index(default_player_id)
elif len(filtered_player_ids_list) > 0:
    # If default player not in filtered list, use first available
    default_index = 0

# Check if there are any players to show
if len(filtered_player_ids_list) == 0:
    st.warning("⚠️ No players found for the selected matchup. Please select a different matchup or date.")
    st.stop()

selected_player_id = st.selectbox(
    "Select Player",
    options=filtered_player_ids_list,
    format_func=lambda x: player_name_map.get(x, f"Player {x}"),
    index=default_index,
    key="player_selector"
)

# Cache player data to avoid repeated API calls
# Version 2: Added PRA and PRA percentile support
@st.cache_data
def get_cached_player_data(player_id, players_df, _cache_version=2):
    """Cache player data to avoid repeated API calls"""
    return pf.get_player_data(player_id, players_df)

# Get player data for selected player (uses PlayerIndex data, no CommonPlayerInfo API call needed)
player_data = get_cached_player_data(selected_player_id, players_df)

with st.container(border=False):
    col1, col2, col3 = st.columns([0.2, 0.2, 0.6], border=1, vertical_alignment='top')
    with col1:
        # st.image(pf.headshot,
        #          width=225)
        st.markdown(f"""
                    <div style="position: relative; display: inline-block; width: 100%; max-width: 230px;">
                        <img src="{player_data['headshot']}" style="width: 100%; height: auto; max-width: 230px; max-height: 175px; object-fit: cover;">
                        <img src="{player_data['logo']}" style="position: absolute; top: -5px; right: -10px; width: 30%; height: auto; max-width: 80px; max-height: 60px; object-fit: contain;">
                    </div>
                """, unsafe_allow_html=True)
    with col2:

        st.subheader(
            f"{player_data['player_info_name']}",
            anchor=False
        )
        # st.badge(
        #     f"**{player_data['player_info_team']} #{player_data['player_info_number']}**",
        #     color='blue'
        # )
        st.markdown(f"""
            <div style="display: inline-block; background-color: {player_data['team_color']}; color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.875em; font-weight: bold; margin: 0.25rem 0 0.75rem 0;">
                {player_data['player_info_team']} #{player_data['player_info_number']}
            </div>
        """, unsafe_allow_html=True)

        st.write(
            f"**{player_data['player_info_position']}**"
        )
        st.write(
            f"Height: **{player_data['player_info_height']}** | Weight: **{player_data['player_info_weight']} pounds**"
        )

    with col3:
        st.subheader(
            'Season Stats',
            anchor=False
        )
        col5, col6, col7, col8, col9, col10 = st.columns([0.16, 0.16, 0.16, 0.16, 0.16, 0.16], border=0)
        with col5:
            pts_percentile = player_data.get('pts_percentile')
            pts_percentile_str = pf.format_percentile(pts_percentile)
            st.metric(
                label='Points',
                value=player_data['player_pts_pg'],
                delta=f"{pts_percentile_str} %ile" if pts_percentile is not None else None
            )
        with col6:
            reb_percentile = player_data.get('reb_percentile')
            reb_percentile_str = pf.format_percentile(reb_percentile)
            st.metric(
                label='Rebounds',
                value=player_data['player_reb_pg'],
                delta=f"{reb_percentile_str} %ile" if reb_percentile is not None else None
            )
        with col7:
            ast_percentile = player_data.get('ast_percentile')
            ast_percentile_str = pf.format_percentile(ast_percentile)
            st.metric(
                label='Assists',
                value=player_data['player_ast_pg'],
                delta=f"{ast_percentile_str} %ile" if ast_percentile is not None else None
            )
        with col8:
            # Calculate PRA if not in cached data (for backward compatibility)
            if 'player_pra_pg' in player_data:
                player_pra_pg = player_data['player_pra_pg']
            else:
                # Fallback: calculate from existing stats
                player_pra_pg = player_data.get('player_pts_pg', 0.0) + player_data.get('player_reb_pg', 0.0) + player_data.get('player_ast_pg', 0.0)
            
            # Get PRA percentile (should always be available in new cached data)
            pra_percentile = player_data.get('pra_percentile')
            pra_percentile_str = pf.format_percentile(pra_percentile) if pra_percentile is not None else None
            st.metric(
                label='PRA',
                value=f"{player_pra_pg:.1f}",
                delta=f"{pra_percentile_str} %ile" if pra_percentile_str is not None else None
            )
        with col9:
            stl_percentile = player_data.get('stl_percentile')
            stl_percentile_str = pf.format_percentile(stl_percentile)
            st.metric(
                label='Steals',
                value=player_data['player_stl_pg'],
                delta=f"{stl_percentile_str} %ile" if stl_percentile is not None else None
            )
        with col10:
            blk_percentile = player_data.get('blk_percentile')
            blk_percentile_str = pf.format_percentile(blk_percentile)
            st.metric(
                label='Blocks',
                value=player_data['player_blk_pg'],
                delta=f"{blk_percentile_str} %ile" if blk_percentile is not None else None
            )

# with st.container(height=1000, border=True):
#     st.altair_chart(player_data['final_chart'], use_container_width=False)

# Create tabs for Current Season and YoY Data
tab1, tab2 = st.tabs(["Current Season", "YoY Data"])

with tab1:
    # Display averages table with heatmap
    if player_data.get('averages_df') is not None and len(player_data['averages_df']) > 0:
        st.subheader("Averages")
        show_comparison = st.toggle("Show +/- vs Season", value=False, key="show_comparison")
    
        # Create heatmap styling
        averages_df = player_data['averages_df'].copy()
        
        # Ensure all numeric columns are formatted to 1 decimal place
        numeric_cols_to_format = ['MIN', 'PTS', 'REB', 'AST', 'PRA', 'STL', 'BLK', 'TOV', '2PM', '2PA', '3PM', '3PA', 'FTM', 'FTA']
        for col in numeric_cols_to_format:
            if col in averages_df.columns:
                averages_df[col] = averages_df[col].apply(lambda x: f"{float(x):.1f}" if pd.notna(x) and str(x) != '' else x)
        
        # Get season row for comparison (last row)
        season_row_idx = len(averages_df) - 1
        season_row = averages_df.iloc[season_row_idx]
        
        # Function to apply heatmap colors
        def style_heatmap(row):
            styles = [''] * len(row)
            
            # Skip Period column (first column) and percentage columns
            numeric_cols = ['MIN', 'PTS', 'REB', 'AST', 'PRA', 'STL', 'BLK', 'TOV', '2PM', '2PA', '3PM', '3PA', 'FTM', 'FTA']
            pct_cols = ['2P%', '3P%', 'FT%']
            
            for i, col in enumerate(averages_df.columns):
                if col == 'Period':
                    continue
                
                if col in numeric_cols:
                    try:
                        # Handle string values that might be formatted
                        current_val_str = str(row[col]).replace(',', '')
                        season_val_str = str(season_row[col]).replace(',', '')
                        current_val = float(current_val_str)
                        season_val = float(season_val_str)
                        
                        if current_val > season_val:
                            # Green gradient - better than season
                            diff_pct = ((current_val - season_val) / season_val * 100) if season_val > 0 else 0
                            intensity = min(diff_pct / 20, 1.0)  # Cap at 20% difference for max intensity
                            green_intensity = int(200 + (55 * intensity))
                            styles[i] = f'background-color: rgb(200, {green_intensity}, 200);'
                        elif current_val < season_val:
                            # Red gradient - worse than season
                            diff_pct = ((season_val - current_val) / season_val * 100) if season_val > 0 else 0
                            intensity = min(diff_pct / 20, 1.0)
                            red_intensity = int(200 + (55 * intensity))
                            styles[i] = f'background-color: rgb({red_intensity}, 200, 200);'
                        else:
                            # Gray - same as season
                            styles[i] = 'background-color: rgb(240, 240, 240);'
                    except (ValueError, TypeError):
                        pass
                elif col in pct_cols:
                    try:
                        # Extract percentage value
                        current_str = str(row[col]).replace('%', '')
                        season_str = str(season_row[col]).replace('%', '')
                        current_val = float(current_str)
                        season_val = float(season_str)
                        
                        if current_val > season_val:
                            diff_pct = ((current_val - season_val) / season_val * 100) if season_val > 0 else 0
                            intensity = min(diff_pct / 20, 1.0)
                            green_intensity = int(200 + (55 * intensity))
                            styles[i] = f'background-color: rgb(200, {green_intensity}, 200);'
                        elif current_val < season_val:
                            diff_pct = ((season_val - current_val) / season_val * 100) if season_val > 0 else 0
                            intensity = min(diff_pct / 20, 1.0)
                            red_intensity = int(200 + (55 * intensity))
                            styles[i] = f'background-color: rgb({red_intensity}, 200, 200);'
                        else:
                            styles[i] = 'background-color: rgb(240, 240, 240);'
                    except (ValueError, TypeError):
                        pass
            
            return styles
        
        # Add comparison columns if toggle is on
        if show_comparison:
            # Get season row values
            season_row = averages_df.iloc[-1]
            
            # Create comparison dataframe
            comparison_df = averages_df.copy()
            
            # Add +/- columns for numeric stats
            numeric_cols = ['MIN', 'PTS', 'REB', 'AST', 'PRA', 'STL', 'BLK', 'TOV', '2PM', '2PA', '3PM', '3PA', 'FTM', 'FTA']
            pct_cols = ['2P%', '3P%', 'FT%']
            
            # Insert comparison columns after each stat
            new_cols = ['Period']
            for col in averages_df.columns[1:]:  # Skip Period column
                new_cols.append(col)
                if col in numeric_cols:
                    # Add +/- column (already rounded to 1 decimal)
                    comparison_df[f'{col} +/-'] = comparison_df.apply(
                        lambda row: f"{round(float(str(row[col]).replace(',', '')) - float(str(season_row[col]).replace(',', '')), 1):+.1f}" if row.name != season_row_idx else '—',
                        axis=1
                    )
                    new_cols.append(f'{col} +/-')
                elif col in pct_cols:
                    # Add +/- column for percentages
                    comparison_df[f'{col} +/-'] = comparison_df.apply(
                        lambda row: f"{round(float(str(row[col]).replace('%', '')) - float(str(season_row[col]).replace('%', '')), 1):+.1f}%" if row.name != season_row_idx else '—',
                        axis=1
                    )
                    new_cols.append(f'{col} +/-')
            
            # Reorder columns
            comparison_df = comparison_df[new_cols]
            # Update heatmap function to handle comparison columns
            def style_heatmap_with_comparison(row):
                styles = [''] * len(row)
                for i, col in enumerate(comparison_df.columns):
                    if col == 'Period' or '+/-' in col:
                        continue
                    if col in numeric_cols:
                        try:
                            # Handle string values that might be formatted
                            current_val_str = str(row[col]).replace(',', '')
                            season_val_str = str(season_row[col]).replace(',', '')
                            current_val = float(current_val_str)
                            season_val = float(season_val_str)
                            if current_val > season_val:
                                diff_pct = ((current_val - season_val) / season_val * 100) if season_val > 0 else 0
                                intensity = min(diff_pct / 20, 1.0)
                                green_intensity = int(200 + (55 * intensity))
                                styles[i] = f'background-color: rgb(200, {green_intensity}, 200);'
                            elif current_val < season_val:
                                diff_pct = ((season_val - current_val) / season_val * 100) if season_val > 0 else 0
                                intensity = min(diff_pct / 20, 1.0)
                                red_intensity = int(200 + (55 * intensity))
                                styles[i] = f'background-color: rgb({red_intensity}, 200, 200);'
                            else:
                                styles[i] = 'background-color: rgb(240, 240, 240);'
                        except (ValueError, TypeError):
                            pass
                    elif col in pct_cols:
                        try:
                            current_str = str(row[col]).replace('%', '')
                            season_str = str(season_row[col]).replace('%', '')
                            current_val = float(current_str)
                            season_val = float(season_str)
                            if current_val > season_val:
                                diff_pct = ((current_val - season_val) / season_val * 100) if season_val > 0 else 0
                                intensity = min(diff_pct / 20, 1.0)
                                green_intensity = int(200 + (55 * intensity))
                                styles[i] = f'background-color: rgb(200, {green_intensity}, 200);'
                            elif current_val < season_val:
                                diff_pct = ((season_val - current_val) / season_val * 100) if season_val > 0 else 0
                                intensity = min(diff_pct / 20, 1.0)
                                red_intensity = int(200 + (55 * intensity))
                                styles[i] = f'background-color: rgb({red_intensity}, 200, 200);'
                            else:
                                styles[i] = 'background-color: rgb(240, 240, 240);'
                        except (ValueError, TypeError):
                            pass
                return styles
            styled_df = comparison_df.style.apply(style_heatmap_with_comparison, axis=1)
        else:
            styled_df = averages_df.style.apply(style_heatmap, axis=1)
        
        st.dataframe(styled_df, use_container_width=True, hide_index=True)

        # Display recent game logs table
        if player_data.get('recent_games_df') is not None and len(player_data['recent_games_df']) > 0:
            st.subheader("Recent Game Logs (Last 10 Games)")
            show_game_comparison = st.toggle("Show vs Season Avg", value=False, key="show_game_comparison")
            
            # Get season averages for comparison
            if show_game_comparison and player_data.get('averages_df') is not None:
                season_avg = player_data['averages_df'].iloc[-1]  # Last row is season
                
                game_logs_df = player_data['recent_games_df'].copy()
                
                # Add comparison columns
                numeric_cols = ['MIN', 'PTS', 'REB', 'AST', 'PRA', 'STL', 'BLK', 'TOV', '2PM', '2PA', '3PM', '3PA', 'FTM', 'FTA']
                pct_cols = ['2P%', '3P%', 'FT%']
                
                # Create new columns list with comparison columns
                new_cols = []
                for col in game_logs_df.columns:
                    new_cols.append(col)
                    if col in numeric_cols:
                        # Add vs Avg column
                        try:
                            season_val = float(season_avg[col])
                            game_logs_df[f'{col} vs Avg'] = game_logs_df[col].apply(
                                lambda x: f"{round(float(x) - season_val, 1):+.1f}" if pd.notna(x) else ''
                            )
                            new_cols.append(f'{col} vs Avg')
                        except (ValueError, KeyError):
                            pass
                    elif col in pct_cols:
                        # Add vs Avg column for percentages
                        try:
                            season_str = str(season_avg[col]).replace('%', '')
                            season_val = float(season_str)
                            game_logs_df[f'{col} vs Avg'] = game_logs_df[col].apply(
                                lambda x: f"{round(float(str(x).replace('%', '')) - season_val, 1):+.1f}%" if pd.notna(x) else ''
                            )
                            new_cols.append(f'{col} vs Avg')
                        except (ValueError, KeyError):
                            pass
                
                game_logs_df = game_logs_df[new_cols]
                st.dataframe(game_logs_df, use_container_width=True, hide_index=True)
            else:
                st.dataframe(
                    player_data['recent_games_df'],
                    use_container_width=True,
                    hide_index=True
                )
        else:
            st.info("No game logs available for this player.")

with tab2:
    # YoY Data tab
    st.subheader("Historical Season Stats")
    
    # Get YoY data for all seasons
    @st.cache_data
    def get_cached_yoy_data(player_id, players_df):
        """Cache YoY player data to avoid repeated API calls"""
        return pf.get_player_yoy_data(player_id, players_df)
    
    yoy_data = get_cached_yoy_data(selected_player_id, players_df)
    
    if yoy_data and yoy_data.get('averages_df') is not None and len(yoy_data['averages_df']) > 0:
        show_yoy_comparison = st.toggle("Show +/- vs Current Season", value=False, key="show_yoy_comparison")
        
        # Create heatmap styling for YoY data
        yoy_averages_df = yoy_data['averages_df'].copy()
        
        # Ensure all numeric columns are formatted to 1 decimal place
        numeric_cols_to_format = ['MIN', 'PTS', 'REB', 'AST', 'PRA', 'STL', 'BLK', 'TOV', '2PM', '2PA', '3PM', '3PA', 'FTM', 'FTA']
        for col in numeric_cols_to_format:
            if col in yoy_averages_df.columns:
                yoy_averages_df[col] = yoy_averages_df[col].apply(lambda x: f"{float(x):.1f}" if pd.notna(x) and str(x) != '' else x)
        
        # Heatmap comparing each season to current season
        def style_yoy_heatmap(row):
            styles = [''] * len(row)
            
            if not show_yoy_comparison or player_data.get('averages_df') is None:
                return styles
            
            current_season_avg = player_data['averages_df'].iloc[-1]  # Last row is current season
            numeric_cols = ['MIN', 'PTS', 'REB', 'AST', 'PRA', 'STL', 'BLK', 'TOV', '2PM', '2PA', '3PM', '3PA', 'FTM', 'FTA']
            pct_cols = ['2P%', '3P%', 'FT%']
            
            for i, col in enumerate(yoy_averages_df.columns):
                if col == 'Period' or '+/-' in col:
                    continue
                
                if col in numeric_cols:
                    try:
                        current_val_str = str(row[col]).replace(',', '')
                        current_season_val_str = str(current_season_avg[col]).replace(',', '')
                        current_val = float(current_val_str)
                        current_season_val = float(current_season_val_str)
                        
                        if current_val > current_season_val:
                            diff_pct = ((current_val - current_season_val) / current_season_val * 100) if current_season_val > 0 else 0
                            intensity = min(diff_pct / 20, 1.0)
                            green_intensity = int(200 + (55 * intensity))
                            styles[i] = f'background-color: rgb(200, {green_intensity}, 200);'
                        elif current_val < current_season_val:
                            diff_pct = ((current_season_val - current_val) / current_season_val * 100) if current_season_val > 0 else 0
                            intensity = min(diff_pct / 20, 1.0)
                            red_intensity = int(200 + (55 * intensity))
                            styles[i] = f'background-color: rgb({red_intensity}, 200, 200);'
                        else:
                            styles[i] = 'background-color: rgb(240, 240, 240);'
                    except (ValueError, TypeError, KeyError):
                        pass
                elif col in pct_cols:
                    try:
                        current_str = str(row[col]).replace('%', '')
                        current_season_str = str(current_season_avg[col]).replace('%', '')
                        current_val = float(current_str)
                        current_season_val = float(current_season_str)
                        
                        if current_val > current_season_val:
                            diff_pct = ((current_val - current_season_val) / current_season_val * 100) if current_season_val > 0 else 0
                            intensity = min(diff_pct / 20, 1.0)
                            green_intensity = int(200 + (55 * intensity))
                            styles[i] = f'background-color: rgb(200, {green_intensity}, 200);'
                        elif current_val < current_season_val:
                            diff_pct = ((current_season_val - current_val) / current_season_val * 100) if current_season_val > 0 else 0
                            intensity = min(diff_pct / 20, 1.0)
                            red_intensity = int(200 + (55 * intensity))
                            styles[i] = f'background-color: rgb({red_intensity}, 200, 200);'
                        else:
                            styles[i] = 'background-color: rgb(240, 240, 240);'
                    except (ValueError, TypeError, KeyError):
                        pass
            
            return styles
        
        # Add comparison columns if toggle is on
        if show_yoy_comparison:
            # Get current season averages for comparison
            if player_data.get('averages_df') is not None:
                current_season_avg = player_data['averages_df'].iloc[-1]  # Last row is current season
                
                # Create comparison dataframe
                yoy_comparison_df = yoy_averages_df.copy()
                
                numeric_cols = ['MIN', 'PTS', 'REB', 'AST', 'PRA', 'STL', 'BLK', 'TOV', '2PM', '2PA', '3PM', '3PA', 'FTM', 'FTA']
                pct_cols = ['2P%', '3P%', 'FT%']
                
                # Insert comparison columns after each stat
                new_cols = ['Period']
                for col in yoy_averages_df.columns[1:]:  # Skip Period column
                    new_cols.append(col)
                    if col in numeric_cols:
                        # Add +/- column comparing to current season
                        try:
                            yoy_comparison_df[f'{col} +/-'] = yoy_comparison_df.apply(
                                lambda row: f"{round(float(str(row[col]).replace(',', '')) - float(str(current_season_avg[col]).replace(',', '')), 1):+.1f}" if pd.notna(row[col]) and str(row[col]) != '' else '—',
                                axis=1
                            )
                            new_cols.append(f'{col} +/-')
                        except (KeyError, ValueError):
                            pass
                    elif col in pct_cols:
                        # Add +/- column for percentages
                        try:
                            yoy_comparison_df[f'{col} +/-'] = yoy_comparison_df.apply(
                                lambda row: f"{round(float(str(row[col]).replace('%', '')) - float(str(current_season_avg[col]).replace('%', '')), 1):+.1f}%" if pd.notna(row[col]) and str(row[col]) != '' else '—',
                                axis=1
                            )
                            new_cols.append(f'{col} +/-')
                        except (KeyError, ValueError):
                            pass
                
                # Reorder columns
                yoy_comparison_df = yoy_comparison_df[new_cols]
                styled_yoy_df = yoy_comparison_df.style.apply(style_yoy_heatmap, axis=1)
            else:
                styled_yoy_df = yoy_averages_df.style.apply(style_yoy_heatmap, axis=1)
        else:
            styled_yoy_df = yoy_averages_df.style.apply(style_yoy_heatmap, axis=1)
        
        st.dataframe(styled_yoy_df, use_container_width=True, hide_index=True)
    else:
        st.info("No historical season stats available for this player.")