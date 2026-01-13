import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'streamlit'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'new-streamlit-app', 'player-app'))

import streamlit as st
import streamlit_testing_functions as functions
import nba_api.stats.endpoints as endpoints
import pandas as pd
from datetime import date

st.set_page_config(layout="wide")
st.title("🏀 Passing Analytics")

# Add sidebar with cache clear button
with st.sidebar:
    st.markdown("### Cache Management")
    if st.button("🗑️ Clear All Cache", width='stretch'):
        st.cache_data.clear()
        st.success("✅ Cache cleared successfully!")
        st.rerun()
    st.markdown("---")  # Separator

# Cache function to get all teams
@st.cache_data(ttl=3600)
def get_all_teams():
    """Get all NBA teams"""
    try:
        team_stats = endpoints.LeagueDashTeamStats(
            league_id_nullable='00',
            season='2025-26',
            season_type_all_star='Regular Season'
        ).get_data_frames()[0]
        
        # Create team options with name and ID
        teams = []
        for _, row in team_stats.iterrows():
            teams.append({
                'id': row['TEAM_ID'],
                'name': row['TEAM_NAME'],
                'abbr': row.get('TEAM_ABBREVIATION', '')
            })
        
        # Sort by team name
        teams.sort(key=lambda x: x['name'])
        return teams
    except Exception as e:
        st.error(f"Error fetching teams: {str(e)}")
        return []

# Cache function to get team roster
@st.cache_data(ttl=1800)
def get_team_roster(team_id):
    """Get roster for a specific team"""
    try:
        players_df = functions.get_players_dataframe()
        if players_df is None or len(players_df) == 0:
            return []
        
        # Filter players by team
        team_players = players_df[players_df['TEAM_ID'].astype(int) == team_id].copy()
        
        if len(team_players) == 0:
            return []
        
        # Create player options
        players = []
        for _, row in team_players.iterrows():
            player_name = f"{row.get('PLAYER_FIRST_NAME', '')} {row.get('PLAYER_LAST_NAME', '')}".strip()
            player_id = row['PERSON_ID']
            players.append({
                'id': int(player_id),
                'name': player_name
            })
        
        # Sort by name
        players.sort(key=lambda x: x['name'])
        return players
    except Exception as e:
        st.error(f"Error fetching roster: {str(e)}")
        return []

# Cache function to get passing data
@st.cache_data(ttl=1800)
def get_player_passing_data(player_id, team_id, season='2025-26', season_type='Regular Season', per_mode_simple='PerGame'):
    """Get passing data for a specific player"""
    try:
        passing_data = endpoints.PlayerDashPtPass(
            season=season,
            season_type_all_star=season_type,
            per_mode_simple=per_mode_simple,
            player_id=str(player_id),
            team_id=str(team_id)
        ).get_data_frames()[0]
        
        return passing_data
    except Exception as e:
        st.error(f"Error fetching passing data: {str(e)}")
        return pd.DataFrame()

# Helper function to convert receiver name to FIRST LAST format
def format_receiver_name(receiver_id, roster):
    """Convert receiver ID to FIRST LAST name format"""
    for player in roster:
        if player['id'] == receiver_id:
            return player['name']  # Already in FIRST LAST format from get_team_roster
    return None

# Helper function to convert passer name to FIRST LAST format
def format_passer_name(passer_id, roster):
    """Convert passer ID to FIRST LAST name format"""
    for player in roster:
        if player['id'] == passer_id:
            return player['name']  # Already in FIRST LAST format from get_team_roster
    return None

# Cache function to get all passing data for a team (for receiver view)
@st.cache_data(ttl=1800)
def get_all_team_passing_data(team_id, roster, season='2025-26', season_type='Regular Season', per_mode_simple='PerGame'):
    """Get passing data for all players on a team"""
    all_passing_data = []
    
    for player in roster:
        try:
            passing_data = endpoints.PlayerDashPtPass(
                season=season,
                season_type_all_star=season_type,
                per_mode_simple=per_mode_simple,
                player_id=str(player['id']),
                team_id=str(team_id)
            ).get_data_frames()[0]
            
            # Add passer ID to each row
            passing_data['PASSER_ID'] = player['id']
            passing_data['PASSER_NAME'] = player['name']
            all_passing_data.append(passing_data)
        except Exception as e:
            # Skip players with no passing data
            continue
    
    if not all_passing_data:
        return pd.DataFrame()
    
    return pd.concat(all_passing_data, ignore_index=True)

# Team Selection
st.markdown("### Select Team")
teams = get_all_teams()

if not teams:
    st.warning("⚠️ Unable to load teams. Please try again later.")
    st.stop()

# Create team options for dropdown
team_options = {team['name']: team for team in teams}
selected_team_str = st.selectbox(
    "Choose Team:",
    options=list(team_options.keys()),
    index=0,
    key="passing_team_select"
)

selected_team = team_options[selected_team_str]
selected_team_id = selected_team['id']
selected_team_name = selected_team['name']

st.markdown("---")

# Get roster for selected team
roster = get_team_roster(selected_team_id)

if not roster:
    st.warning(f"⚠️ No roster data available for {selected_team_name}.")
    st.stop()

# View Mode Selection
st.markdown("### View Mode")
view_mode = st.radio(
    "Select view:",
    options=["Passer → Receiver", "Receiver ← All Passers"],
    index=0,
    key="view_mode",
    horizontal=True,
    help="'Passer → Receiver' shows passes from a specific player. 'Receiver ← All Passers' shows all players who pass to a specific receiver."
)

st.markdown("---")

# Player Selection
st.markdown("### Select Players")

if view_mode == "Passer → Receiver":
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Passer**")
        passer_options = {player['name']: player for player in roster}
        selected_passer_name = st.selectbox(
            "Player making passes:",
            options=list(passer_options.keys()),
            index=0,
            key="passer_select"
        )
        selected_passer = passer_options[selected_passer_name]
    
    with col2:
        st.markdown("**Receiver**")
        receiver_options = {player['name']: player for player in roster}
        selected_receiver_name = st.selectbox(
            "Player receiving passes:",
            options=list(receiver_options.keys()),
            index=0,
            key="receiver_select"
        )
        selected_receiver = receiver_options[selected_receiver_name]
else:  # Receiver ← All Passers
    st.markdown("**Receiver**")
    receiver_options = {player['name']: player for player in roster}
    selected_receiver_name = st.selectbox(
        "Player receiving passes:",
        options=list(receiver_options.keys()),
        index=0,
        key="receiver_select_all"
    )
    selected_receiver = receiver_options[selected_receiver_name]
    selected_passer = None  # Not needed for this view
    selected_passer_name = None

st.markdown("---")

# Per Mode Toggle
st.markdown("### Stats Mode")
per_mode = st.radio(
    "Select stats mode:",
    options=["Per Game", "Totals"],
    index=0,
    key="per_mode_toggle",
    horizontal=True,
    help="'Per Game' shows averages per game. 'Totals' shows cumulative totals."
)

per_mode_simple = "PerGame" if per_mode == "Per Game" else "Totals"

st.markdown("---")

# Get passing data
if view_mode == "Passer → Receiver":
    if selected_passer['id'] == selected_receiver['id']:
        st.info("ℹ️ Please select two different players.")
        st.stop()
    
    st.markdown(f"### Passing Data: {selected_passer_name} → {selected_receiver_name}")
    
    passing_df = get_player_passing_data(
        selected_passer['id'],
        selected_team_id,
        per_mode_simple=per_mode_simple
    )
    
    if passing_df is None or len(passing_df) == 0:
        st.warning(f"⚠️ No passing data available for {selected_passer_name}.")
        st.stop()
    
    # Get available pass types
    if 'PASS_TYPE' in passing_df.columns and len(passing_df['PASS_TYPE'].unique()) > 0:
        available_pass_types = ['All'] + sorted([pt for pt in passing_df['PASS_TYPE'].unique().tolist() if pd.notna(pt)])
    else:
        available_pass_types = ['All']
    
    # Pass type filter (only show if there are multiple pass types)
    if len(available_pass_types) > 1:
        selected_pass_type = st.selectbox(
            "Pass Type:",
            options=available_pass_types,
            index=0,
            key="pass_type_filter",
            help="Filter by pass type. 'All' includes all pass types."
        )
        
        # Filter by pass type if not "All"
        if selected_pass_type != 'All':
            passing_df = passing_df[passing_df['PASS_TYPE'] == selected_pass_type].copy()
    
    # Filter to show only the selected receiver
    receiver_passes = passing_df[
        passing_df['PASS_TEAMMATE_PLAYER_ID'] == selected_receiver['id']
    ]
    
    if len(receiver_passes) == 0:
        st.info(f"ℹ️ {selected_passer_name} has not recorded any passes to {selected_receiver_name} this season.")
    else:
        # Display key metrics
        row = receiver_passes.iloc[0]
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Pass Frequency %", f"{row.get('FREQUENCY', 0):.1%}", 
                     help="Percentage of passer's total passes that go to this receiver")
        
        with col2:
            fg_pct = row.get('FG_PCT', 0)
            if pd.notna(fg_pct):
                st.metric("FG% When Receiving", f"{fg_pct:.1%}")
            else:
                st.metric("FG% When Receiving", "N/A")
        
        with col3:
            ast = row.get('AST', 0)
            st.metric("Assists Per Game", f"{ast:.2f}")
        
        with col4:
            fgm = row.get('FGM', 0)
            fga = row.get('FGA', 0)
            st.metric("FGM / FGA", f"{fgm:.1f} / {fga:.1f}")
        
        st.markdown("---")
        
        # Detailed stats table
        st.markdown("#### Detailed Statistics")
        
        # Prepare display dataframe
        display_cols = [
            'PASS_TEAMMATE_PLAYER_ID', 'FREQUENCY', 'AST', 'FGM', 'FGA', 'FG_PCT',
            'FG2M', 'FG2A', 'FG2_PCT', 'FG3M', 'FG3A', 'FG3_PCT'
        ]
        
        display_df = receiver_passes[[col for col in display_cols if col in receiver_passes.columns]].copy()
        
        # Convert receiver IDs to FIRST LAST names
        if 'PASS_TEAMMATE_PLAYER_ID' in display_df.columns:
            display_df['Receiver'] = display_df['PASS_TEAMMATE_PLAYER_ID'].apply(
                lambda x: format_receiver_name(int(x), roster) or f"Player {x}"
            )
            display_df = display_df.drop(columns=['PASS_TEAMMATE_PLAYER_ID'])
        
        # Format percentages
        if 'FG_PCT' in display_df.columns:
            display_df['FG_PCT'] = display_df['FG_PCT'].apply(lambda x: f"{x:.1%}" if pd.notna(x) else "N/A")
        if 'FG2_PCT' in display_df.columns:
            display_df['FG2_PCT'] = display_df['FG2_PCT'].apply(lambda x: f"{x:.1%}" if pd.notna(x) else "N/A")
        if 'FG3_PCT' in display_df.columns:
            display_df['FG3_PCT'] = display_df['FG3_PCT'].apply(lambda x: f"{x:.1%}" if pd.notna(x) else "N/A")
        
        # Format frequency as percentage
        if 'FREQUENCY' in display_df.columns:
            display_df['FREQUENCY'] = display_df['FREQUENCY'].apply(lambda x: f"{x:.1%}" if pd.notna(x) else "N/A")
        
        # Reorder columns to put Receiver first
        cols = ['Receiver'] + [col for col in display_df.columns if col != 'Receiver']
        display_df = display_df[cols]
        
        # Rename columns for display
        display_df.columns = [
            'Receiver', 'Pass Frequency %', 'AST', 'FGM', 'FGA', 'FG%',
            '2PM', '2PA', '2P%', '3PM', '3PA', '3P%'
        ]
        
        st.dataframe(
            display_df,
            hide_index=True,
            width='stretch'
        )
        
        # Show all passing relationships for the passer
        st.markdown("---")
        st.markdown(f"#### All Passing Relationships: {selected_passer_name}")
        
        # Sort by frequency descending
        all_passes = passing_df.sort_values('FREQUENCY', ascending=False).copy()
        
        # Format for display
        all_display_cols = [
            'PASS_TEAMMATE_PLAYER_ID', 'FREQUENCY', 'AST', 'FGM', 'FGA', 'FG_PCT'
        ]
        
        all_display_df = all_passes[[col for col in all_display_cols if col in all_passes.columns]].copy()
        
        # Convert receiver IDs to FIRST LAST names
        if 'PASS_TEAMMATE_PLAYER_ID' in all_display_df.columns:
            all_display_df['Receiver'] = all_display_df['PASS_TEAMMATE_PLAYER_ID'].apply(
                lambda x: format_receiver_name(int(x), roster) or f"Player {x}"
            )
            all_display_df = all_display_df.drop(columns=['PASS_TEAMMATE_PLAYER_ID'])
        
        # Format percentages
        if 'FG_PCT' in all_display_df.columns:
            all_display_df['FG_PCT'] = all_display_df['FG_PCT'].apply(lambda x: f"{x:.1%}" if pd.notna(x) else "N/A")
        
        # Format frequency as percentage
        if 'FREQUENCY' in all_display_df.columns:
            all_display_df['FREQUENCY'] = all_display_df['FREQUENCY'].apply(lambda x: f"{x:.1%}" if pd.notna(x) else "N/A")
        
        # Reorder columns to put Receiver first
        cols = ['Receiver'] + [col for col in all_display_df.columns if col != 'Receiver']
        all_display_df = all_display_df[cols]
        
        # Rename columns
        all_display_df.columns = [
            'Receiver', 'Pass Frequency %', 'Assists', 'FGM', 'FGA', 'FG%'
        ]
        
        st.dataframe(
            all_display_df,
            hide_index=True,
            width='stretch'
        )

else:  # Receiver ← All Passers view
    st.markdown(f"### All Players Passing to: {selected_receiver_name}")
    
    # Get passing data for all players on the team
    all_team_passing = get_all_team_passing_data(
        selected_team_id,
        roster,
        per_mode_simple=per_mode_simple
    )
    
    if all_team_passing is None or len(all_team_passing) == 0:
        st.warning(f"⚠️ No passing data available for {selected_team_name}.")
        st.stop()
    
    # Filter to find all passes to the selected receiver
    passes_to_receiver = all_team_passing[
        all_team_passing['PASS_TEAMMATE_PLAYER_ID'] == selected_receiver['id']
    ].copy()
    
    if len(passes_to_receiver) == 0:
        st.info(f"ℹ️ No players have recorded passes to {selected_receiver_name} this season.")
        st.stop()
    
    # Get available pass types
    if 'PASS_TYPE' in passes_to_receiver.columns and len(passes_to_receiver['PASS_TYPE'].unique()) > 0:
        available_pass_types = ['All'] + sorted([pt for pt in passes_to_receiver['PASS_TYPE'].unique().tolist() if pd.notna(pt)])
    else:
        available_pass_types = ['All']
    
    # Pass type filter (only show if there are multiple pass types)
    if len(available_pass_types) > 1:
        selected_pass_type = st.selectbox(
            "Pass Type:",
            options=available_pass_types,
            index=0,
            key="pass_type_filter_receiver",
            help="Filter by pass type. 'All' includes all pass types."
        )
        
        # Filter by pass type if not "All"
        if selected_pass_type != 'All':
            passes_to_receiver = passes_to_receiver[passes_to_receiver['PASS_TYPE'] == selected_pass_type].copy()
    
    # Sort by frequency descending
    passes_to_receiver = passes_to_receiver.sort_values('FREQUENCY', ascending=False).copy()
    
    # Display summary metrics
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    total_fgm = passes_to_receiver['FGM'].sum()
    total_fga = passes_to_receiver['FGA'].sum()
    total_fg_pct = (total_fgm / total_fga * 100) if total_fga > 0 else 0
    
    total_fg2m = passes_to_receiver['FG2M'].sum()
    total_fg2a = passes_to_receiver['FG2A'].sum()
    total_fg2_pct = (total_fg2m / total_fg2a * 100) if total_fg2a > 0 else 0
    
    total_fg3m = passes_to_receiver['FG3M'].sum()
    total_fg3a = passes_to_receiver['FG3A'].sum()
    total_fg3_pct = (total_fg3m / total_fg3a * 100) if total_fg3a > 0 else 0
    
    with col1:
        st.metric("FGM / FGA", f"{total_fgm:.1f} / {total_fga:.1f}")
    
    with col2:
        st.metric("FG%", f"{total_fg_pct:.1f}%")
    
    with col3:
        st.metric("2PM / 2PA", f"{total_fg2m:.1f} / {total_fg2a:.1f}")
    
    with col4:
        st.metric("2PT%", f"{total_fg2_pct:.1f}%")
    
    with col5:
        st.metric("3PM / 3PA", f"{total_fg3m:.1f} / {total_fg3a:.1f}")
    
    with col6:
        st.metric("3PT%", f"{total_fg3_pct:.1f}%")
    
    st.markdown("---")
    
    # Display all passers
    st.markdown(f"#### All Passers to {selected_receiver_name}")
    
    # Prepare display dataframe
    display_cols = [
        'PASSER_NAME', 'FREQUENCY', 'FGM', 'FGA', 'FG_PCT',
        'FG2M', 'FG2A', 'FG2_PCT', 'FG3M', 'FG3A', 'FG3_PCT'
    ]
    
    display_df = passes_to_receiver[[col for col in display_cols if col in passes_to_receiver.columns]].copy()
    
    # Format individual columns
    if 'FGM' in display_df.columns:
        display_df['FGM'] = display_df['FGM'].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "0.0")
    if 'FGA' in display_df.columns:
        display_df['FGA'] = display_df['FGA'].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "0.0")
    if 'FG2M' in display_df.columns:
        display_df['2PM'] = display_df['FG2M'].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "0.0")
    if 'FG2A' in display_df.columns:
        display_df['2PA'] = display_df['FG2A'].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "0.0")
    if 'FG3M' in display_df.columns:
        display_df['3PM'] = display_df['FG3M'].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "0.0")
    if 'FG3A' in display_df.columns:
        display_df['3PA'] = display_df['FG3A'].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "0.0")
    
    # Format percentages
    if 'FG_PCT' in display_df.columns:
        display_df['FG%'] = display_df['FG_PCT'].apply(lambda x: f"{x:.1%}" if pd.notna(x) else "N/A")
    if 'FG2_PCT' in display_df.columns:
        display_df['2PT%'] = display_df['FG2_PCT'].apply(lambda x: f"{x:.1%}" if pd.notna(x) else "N/A")
    if 'FG3_PCT' in display_df.columns:
        display_df['3PT%'] = display_df['FG3_PCT'].apply(lambda x: f"{x:.1%}" if pd.notna(x) else "N/A")
    
    # Format frequency as percentage
    if 'FREQUENCY' in display_df.columns:
        display_df['Pass Frequency %'] = display_df['FREQUENCY'].apply(lambda x: f"{x:.1%}" if pd.notna(x) else "N/A")
    
    # Select and reorder columns
    display_df = display_df[['PASSER_NAME', 'Pass Frequency %', 'FGM', 'FGA', 'FG%', '2PM', '2PA', '2PT%', '3PM', '3PA', '3PT%']].copy()
    
    # Rename columns
    display_df.columns = [
        'Passer', 'Pass Frequency %', 'FGM', 'FGA', 'FG%', '2PM', '2PA', '2PT%', '3PM', '3PA', '3PT%'
    ]
    
    st.dataframe(
        display_df,
        hide_index=True,
        width='stretch'
    )

