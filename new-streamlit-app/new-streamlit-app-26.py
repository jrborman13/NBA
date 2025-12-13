import pandas as pd
import altair as alt
import streamlit as st
import nba_api.stats.endpoints
from datetime import datetime

st.set_page_config(layout="wide")
st.title("NBA Matchup Data App")



# Load data
data = pd.read_csv('/Users/jackborman/Desktop/PycharmProjects/NBA/new-streamlit-app/files/synergy_data.csv', index_col=0)

# Calculate ranks for each PLAY_TYPE and TYPE_GROUPING combination
def calculate_ranks(df):
    """Calculate ranks based on TYPE_GROUPING: higher PPP better for Offensive, lower PPP better for Defensive.
    Also calculate frequency ranks: higher POSS_PCT is better for both Offensive and Defensive."""
    ranked_data = []
    
    for (play_type, type_grouping), group in df.groupby(['PLAY_TYPE', 'TYPE_GROUPING']):
        group = group.copy()
        
        if type_grouping == 'Offensive':
            # Higher PPP is better - rank in descending order
            group['Rank'] = group['PPP'].rank(method='min', ascending=False).astype(int)
        elif type_grouping == 'Defensive':
            # Lower PPP is better - rank in ascending order
            group['Rank'] = group['PPP'].rank(method='min', ascending=True).astype(int)
        else:
            # Default to ascending if unknown type
            group['Rank'] = group['PPP'].rank(method='min', ascending=True).astype(int)
        
        # Frequency rank: Higher POSS_PCT is better for both Offensive and Defensive (rank 1 = highest)
        group['Frequency_Rank'] = group['POSS_PCT'].rank(method='min', ascending=False).astype(int)
        
        ranked_data.append(group)
    
    return pd.concat(ranked_data, ignore_index=True)

# Calculate ranks
data_ranked = calculate_ranks(data)

# Function to fetch today's matchups
@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_todays_matchups():
    """Fetch today's NBA matchups from the API"""
    try:
        league_schedule = nba_api.stats.endpoints.ScheduleLeagueV2(
            league_id='00',
            season='2025-26'
        ).get_data_frames()[0]
        
        league_schedule['dateGame'] = pd.to_datetime(league_schedule['gameDate'])
        league_schedule['matchup'] = league_schedule['awayTeam_teamTricode'] + ' @ ' + league_schedule['homeTeam_teamTricode']
        
        # Compare date parts only to handle datetime objects with time components
        todays_games = league_schedule[
            league_schedule['dateGame'].dt.date == datetime.now().date()
        ]
        
        if len(todays_games) > 0:
            matchups = []
            for _, row in todays_games.iterrows():
                matchup_str = row['matchup']
                away_team = row['awayTeam_teamTricode']
                home_team = row['homeTeam_teamTricode']
                matchups.append({
                    'matchup': matchup_str,
                    'away_team': away_team,
                    'home_team': home_team
                })
            return matchups, None  # Return matchups and error (None)
        else:
            return [], None  # No games today
    except Exception as e:
        return [], str(e)  # Return empty list and error message

# Main content - Consolidated table view
st.subheader("Consolidated Table: All Teams by Play Type and Type Grouping")

# Matchup filter section
st.markdown("### Matchup Filter")

# Get today's matchups
todays_matchups, matchup_error = get_todays_matchups()

# Show error if API call failed
if matchup_error:
    st.warning(f"⚠️ Could not fetch today's matchups: {matchup_error}. Using 'All Teams' mode.")

# Filter mode selection
if todays_matchups:
    filter_mode = st.radio(
        "Filter Mode:",
        ["Today's Matchups", "All Teams"],
        horizontal=True
    )
else:
    filter_mode = "All Teams"
    if not matchup_error:  # Only show info if no error (meaning no games today)
        st.info("ℹ️ No games scheduled for today. Use 'All Teams' mode to select teams manually.")

selected_team_abbrevs = None

if filter_mode == "Today's Matchups" and todays_matchups:
    # Create dropdown for today's matchups
    matchup_options = [m['matchup'] for m in todays_matchups]
    selected_matchup_str = st.selectbox(
        "Select Today's Matchup:",
        options=matchup_options,
        help="Select a matchup from today's scheduled games"
    )
    
    # Extract team abbreviations from selected matchup
    if selected_matchup_str:
        selected_matchup = next(m for m in todays_matchups if m['matchup'] == selected_matchup_str)
        selected_team_abbrevs = [selected_matchup['away_team'], selected_matchup['home_team']]
        # st.info(f"📊 Analyzing matchup: {selected_matchup_str}")

else:
    # Get unique teams for the matchup filter
    available_teams = sorted(data_ranked[['TEAM_ABBREVIATION', 'TEAM_NAME']].drop_duplicates().values.tolist())
    team_options = {f"{team[0]} - {team[1]}": team[0] for team in available_teams}

    # Multiselect for teams
    selected_team_labels = st.multiselect(
        "Select Teams to Compare (leave empty to show all teams):",
        options=list(team_options.keys()),
        default=[],
        help="Select specific teams to compare in the matchup. This will filter both offensive and defensive tables."
    )

    # Extract team abbreviations from selected labels
    selected_team_abbrevs = [team_options[label] for label in selected_team_labels] if selected_team_labels else None

# Apply team filter if teams are selected
matchup_filtered_data = data_ranked.copy()
if selected_team_abbrevs:
    matchup_filtered_data = matchup_filtered_data[matchup_filtered_data['TEAM_ABBREVIATION'].isin(selected_team_abbrevs)]

# Check if exactly 2 teams are selected for matchup comparison
if selected_team_abbrevs and len(selected_team_abbrevs) == 2:
    team1_abbrev = selected_team_abbrevs[0]
    team2_abbrev = selected_team_abbrevs[1]
    
    # Get team names from data
    team1_data = data_ranked[data_ranked['TEAM_ABBREVIATION'] == team1_abbrev]
    team2_data = data_ranked[data_ranked['TEAM_ABBREVIATION'] == team2_abbrev]
    
    if len(team1_data) > 0:
        team1_name = team1_data['TEAM_NAME'].iloc[0]
    else:
        team1_name = team1_abbrev
        
    if len(team2_data) > 0:
        team2_name = team2_data['TEAM_NAME'].iloc[0]
    else:
        team2_name = team2_abbrev
    
    if filter_mode == "Today's Matchups":
        st.info(f"📊 Comparing today's matchup: {team1_abbrev} @ {team2_abbrev}")
    else:
        st.info(f"📊 Comparing matchup: {team1_abbrev} vs {team2_abbrev}")
    
    # Get offensive and defensive data for both teams (including frequency data)
    # Use shortened column names: OFF->O, DEF->D, RANK->RK
    team1_off = data_ranked[
        (data_ranked['TEAM_ABBREVIATION'] == team1_abbrev) & 
        (data_ranked['TYPE_GROUPING'] == 'Offensive')
    ][['PLAY_TYPE', 'TEAM_ABBREVIATION', 'PPP', 'Rank', 'POSS_PCT', 'Frequency_Rank']].copy()
    team1_off.columns = ['PLAY_TYPE', 'O_TEAM', 'O_PPP', 'O_RK', 'O_FREQ', 'O_FREQ_RK']
    
    team2_def = data_ranked[
        (data_ranked['TEAM_ABBREVIATION'] == team2_abbrev) & 
        (data_ranked['TYPE_GROUPING'] == 'Defensive')
    ][['PLAY_TYPE', 'TEAM_ABBREVIATION', 'PPP', 'Rank', 'POSS_PCT', 'Frequency_Rank']].copy()
    team2_def.columns = ['PLAY_TYPE', 'D_TEAM', 'D_PPP', 'D_RK', 'D_FREQ', 'D_FREQ_RK']
    
    team1_def = data_ranked[
        (data_ranked['TEAM_ABBREVIATION'] == team1_abbrev) & 
        (data_ranked['TYPE_GROUPING'] == 'Defensive')
    ][['PLAY_TYPE', 'TEAM_ABBREVIATION', 'PPP', 'Rank', 'POSS_PCT', 'Frequency_Rank']].copy()
    team1_def.columns = ['PLAY_TYPE', 'D_TEAM', 'D_PPP', 'D_RK', 'D_FREQ', 'D_FREQ_RK']
    
    team2_off = data_ranked[
        (data_ranked['TEAM_ABBREVIATION'] == team2_abbrev) & 
        (data_ranked['TYPE_GROUPING'] == 'Offensive')
    ][['PLAY_TYPE', 'TEAM_ABBREVIATION', 'PPP', 'Rank', 'POSS_PCT', 'Frequency_Rank']].copy()
    team2_off.columns = ['PLAY_TYPE', 'O_TEAM', 'O_PPP', 'O_RK', 'O_FREQ', 'O_FREQ_RK']
    
    # Create matchup tables
    matchup_left = team1_off.merge(team2_def, on='PLAY_TYPE', how='inner')
    matchup_right = team2_off.merge(team1_def, on='PLAY_TYPE', how='inner')
    
    # Add difference column based on rank (D_RK - O_RK)
    # Positive = offense advantage (lower rank is better, so if D_RK > O_RK, offense is better)
    # Negative = defense advantage (if D_RK < O_RK, defense is better)
    matchup_left['ADVANTAGE'] = matchup_left['D_RK'] - matchup_left['O_RK']
    matchup_right['ADVANTAGE'] = matchup_right['D_RK'] - matchup_right['O_RK']
    
    # Reorder columns: PLAY_TYPE, ADVANTAGE, then offense columns, then defense columns
    matchup_left = matchup_left[['PLAY_TYPE', 'ADVANTAGE', 'O_TEAM', 'O_PPP', 'O_RK', 'O_FREQ', 'O_FREQ_RK', 'D_TEAM', 'D_PPP', 'D_RK', 'D_FREQ', 'D_FREQ_RK']]
    matchup_right = matchup_right[['PLAY_TYPE', 'ADVANTAGE', 'O_TEAM', 'O_PPP', 'O_RK', 'O_FREQ', 'O_FREQ_RK', 'D_TEAM', 'D_PPP', 'D_RK', 'D_FREQ', 'D_FREQ_RK']]
    
    # Sort by PLAY_TYPE
    matchup_left = matchup_left.sort_values('PLAY_TYPE')
    matchup_right = matchup_right.sort_values('PLAY_TYPE')
    
    # Function to apply conditional formatting based on rank difference
    def highlight_matchup_advantage(row):
        """Apply background color based on rank difference"""
        advantage = row['ADVANTAGE']
        # Threshold of 10 rank positions for "significant" difference
        threshold = 10
        
        if advantage > threshold:
            # Significant offensive advantage (DEF_RANK much higher than OFF_RANK) - light green
            return ['background-color: #d4edda'] * len(row)
        elif advantage < -threshold:
            # Significant defensive advantage (DEF_RANK much lower than OFF_RANK) - light red
            return ['background-color: #f8d7da'] * len(row)
        else:
            # Close matchup (within ±10 ranks) - light yellow
            return ['background-color: #fff3cd'] * len(row)
    
    # Create two columns
    col_left, col_right = st.columns(2)
    
    # Left column - Team 1 Offense vs Team 2 Defense
    with col_left:
        st.markdown(f"### {team1_abbrev} Offense vs {team2_abbrev} Defense")
        if len(matchup_left) > 0:
            # Apply conditional formatting
            styled_left = matchup_left.style.apply(highlight_matchup_advantage, axis=1).format({
                'O_PPP': '{:.3f}', 
                'D_PPP': '{:.3f}',
                'O_FREQ': '{:.3f}',
                'D_FREQ': '{:.3f}',
                'ADVANTAGE': '{:.0f}'
            })
            
            st.dataframe(
                styled_left,
                use_container_width=True,
                hide_index=True
            )
            
            # Legend
            st.caption("🟢 Green = OFF Adv. (>10 rank difference) | 🔴 Red = DEF Adv. (<-10 rank difference) | 🟡 Yellow = Close Matchup (±10 ranks)")
            
            # Download button (without ADVANTAGE column for cleaner CSV)
            csv_left = matchup_left.drop('ADVANTAGE', axis=1).to_csv(index=False)
            st.download_button(
                label=f"Download {team1_abbrev} Off vs {team2_abbrev} Def",
                data=csv_left,
                file_name=f"{team1_abbrev}_off_vs_{team2_abbrev}_def.csv",
                mime="text/csv",
                key="download_matchup_left"
            )
        else:
            st.info("No matchup data available.")
    
    # Right column - Team 2 Offense vs Team 1 Defense
    with col_right:
        st.markdown(f"### {team2_abbrev} Offense vs {team1_abbrev} Defense")
        if len(matchup_right) > 0:
            # Apply conditional formatting
            styled_right = matchup_right.style.apply(highlight_matchup_advantage, axis=1).format({
                'O_PPP': '{:.3f}', 
                'D_PPP': '{:.3f}',
                'O_FREQ': '{:.3f}',
                'D_FREQ': '{:.3f}',
                'ADVANTAGE': '{:.0f}'
            })
            
            st.dataframe(
                styled_right,
                use_container_width=True,
                hide_index=True
            )
            
            # Legend
            st.caption("🟢 Green = OFF Adv. (>10 rank difference) | 🔴 Red = DEF Adv. (<-10 rank difference) | 🟡 Yellow = Close Matchup (±10 ranks)")
            
            # Download button (without ADVANTAGE column for cleaner CSV)
            csv_right = matchup_right.drop('ADVANTAGE', axis=1).to_csv(index=False)
            st.download_button(
                label=f"Download {team2_abbrev} Off vs {team1_abbrev} Def",
                data=csv_right,
                file_name=f"{team2_abbrev}_off_vs_{team1_abbrev}_def.csv",
                mime="text/csv",
                key="download_matchup_right"
            )
        else:
            st.info("No matchup data available.")

else:
    # Regular view - show offensive and defensive tables
    # Prepare consolidated data columns (without TYPE_GROUPING since we'll split by it)
    # Include Frequency (POSS_PCT) and Frequency_Rank
    consolidated_cols = ['TEAM_ABBREVIATION', 'TEAM_NAME', 'PLAY_TYPE', 'PPP', 'Rank', 'POSS_PCT', 'Frequency_Rank']
    
    # Split data into offensive and defensive
    offensive_data = matchup_filtered_data[matchup_filtered_data['TYPE_GROUPING'] == 'Offensive'].copy()
    defensive_data = matchup_filtered_data[matchup_filtered_data['TYPE_GROUPING'] == 'Defensive'].copy()
    
    # Sort both datasets
    offensive_data = offensive_data.sort_values(['PLAY_TYPE', 'Rank'])
    defensive_data = defensive_data.sort_values(['PLAY_TYPE', 'Rank'])
    
    # Create two columns
    col_left, col_right = st.columns(2)
    
    # Left column - Offensive data
    with col_left:
        st.markdown("### Offensive Data")
        if len(offensive_data) > 0:
            offensive_display = offensive_data[consolidated_cols].copy()
            # Rename POSS_PCT to Frequency for display
            offensive_display = offensive_display.rename(columns={'POSS_PCT': 'Frequency', 'Frequency_Rank': 'Freq_Rank'})
            st.dataframe(
                offensive_display.style.format({
                    'PPP': '{:.3f}',
                    'Frequency': '{:.3f}'
                }).background_gradient(
                    subset=['Rank'], 
                    cmap='RdYlGn_r'  # Reversed for offensive (higher is better)
                ).background_gradient(
                    subset=['Freq_Rank'],
                    cmap='RdYlGn_r'  # Higher frequency is better
                ),
                use_container_width=True,
                hide_index=True
            )
            
            # Download button for offensive data
            csv_offensive = offensive_display.to_csv(index=False)
            st.download_button(
                label="Download Offensive Data as CSV",
                data=csv_offensive,
                file_name="nba_offensive_ppp_rankings.csv",
                mime="text/csv",
                key="download_offensive"
            )
        else:
            st.info("No offensive data available.")
    
    # Right column - Defensive data
    with col_right:
        st.markdown("### Defensive Data")
        if len(defensive_data) > 0:
            defensive_display = defensive_data[consolidated_cols].copy()
            # Rename POSS_PCT to Frequency for display
            defensive_display = defensive_display.rename(columns={'POSS_PCT': 'Frequency', 'Frequency_Rank': 'Freq_Rank'})
            st.dataframe(
                defensive_display.style.format({
                    'PPP': '{:.3f}',
                    'Frequency': '{:.3f}'
                }).background_gradient(
                    subset=['Rank'], 
                    cmap='RdYlGn'  # Normal for defensive (lower is better)
                ).background_gradient(
                    subset=['Freq_Rank'],
                    cmap='RdYlGn_r'  # Higher frequency is better
                ),
                use_container_width=True,
                hide_index=True
            )
            
            # Download button for defensive data
            csv_defensive = defensive_display.to_csv(index=False)
            st.download_button(
                label="Download Defensive Data as CSV",
                data=csv_defensive,
                file_name="nba_defensive_ppp_rankings.csv",
                mime="text/csv",
                key="download_defensive"
            )
        else:
            st.info("No defensive data available.")