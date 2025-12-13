import streamlit as st
import streamlit_testing_functions as functions
import pandas as pd
import numpy as np

st.set_page_config(layout="wide")
st.title("NBA Matchup Data App")

# Matchup selector
st.markdown("### Select Matchup")

# Get today's matchups
todays_matchups = functions.get_todays_matchups()

if todays_matchups:
    # Create matchup options for dropdown
    matchup_options = []
    for matchup in todays_matchups:
        matchup_str = f"{matchup['away_team_name']} @ {matchup['home_team_name']}"
        if matchup['is_wolves_game']:
            matchup_str += " 🐺"
        matchup_options.append(matchup_str)
    
    # Default to first option (Wolves game if available, otherwise first by time)
    default_idx = 0
    
    selected_matchup_str = st.selectbox(
        "Choose Today's Matchup:",
        options=matchup_options,
        index=default_idx,
        help="Select a matchup from today's scheduled games. Timberwolves games are marked with 🐺"
    )
    
    # Find the selected matchup
    selected_matchup = todays_matchups[matchup_options.index(selected_matchup_str)]
    
    # Store in session state to track changes
    matchup_changed = ('selected_matchup' not in st.session_state or 
                      st.session_state.get('selected_matchup', {}).get('game_id') != selected_matchup.get('game_id'))
    
    if matchup_changed:
        st.session_state['selected_matchup'] = selected_matchup
        # Store override in session state
        st.session_state['matchup_override'] = selected_matchup
    
    # Update matchup variables without reloading (all team stats are already calculated)
    # This avoids unnecessary API calls and timeout errors
    if 'matchup_override' in st.session_state:
        # Set override and update matchup variables
        functions.set_matchup_override(st.session_state['matchup_override'])
        # Update matchup (this updates away_id, home_id, logos, etc.)
        # All team stats are already calculated, so we just need to change which teams we're displaying
        functions.update_selected_matchup(st.session_state['matchup_override'])
else:
    st.info("ℹ️ No games scheduled for today.")
    # Use default matchup from functions module
    selected_matchup = None
    if 'selected_matchup' in st.session_state:
        del st.session_state['selected_matchup']

# Sidebar for selecting the tab
tab = st.radio("Select Tab", ('Core Stats', 'Shooting', 'Players', 'Lineups'), horizontal=True)

if tab == 'Core Stats':
    # Header with team logos and game title
    col_header1, col_header2, col_header3 = st.columns([1, 2, 1])
    
    with col_header1:
        st.image(functions.away_logo_link, width=150)
        st.caption("Away")
    
    with col_header2:
        st.markdown(f"<h2 style='text-align: center;'>{functions.game_title}</h2>", unsafe_allow_html=True)
    
    with col_header3:
        st.image(functions.home_logo_link, width=150)
        st.caption("Home")
    
    # Time period selector
    time_period = st.radio("Time Period", ("Season", "Last 5"), horizontal=True, key="time_period")
    
    # Helper function to get stat value based on time period
    def get_stat(season_val, l5_val):
        return season_val if time_period == "Season" else l5_val
    
    # Helper function to get rank value based on time period
    def get_rank(season_rank, l5_rank):
        return season_rank if time_period == "Season" else l5_rank
    
    # Helper function to get league average based on time period
    def get_la(season_la, l5_la):
        return season_la if time_period == "Season" else l5_la
    
    # Helper function to determine advantage color based on rank difference
    # For offensive metrics: lower rank (higher stat) is better
    # For defensive metrics: lower rank (lower stat) is better
    def get_advantage_color(off_rank, def_rank, is_offensive=True):
        """Determine color based on rank difference"""
        if off_rank is None or def_rank is None:
            return "#ffffff"
        
        rank_diff = def_rank - off_rank if is_offensive else off_rank - def_rank
        threshold = 10
        
        if rank_diff > threshold:
            return "#d4edda"  # Light green - advantage
        elif rank_diff < -threshold:
            return "#f8d7da"  # Light red - disadvantage
        else:
            return "#fff3cd"  # Light yellow - neutral
    
    # Create two columns for matchup comparison
    col_left, col_right = st.columns(2)
    
    # LEFT COLUMN: Away Offense vs Home Defense
    with col_left:
        st.markdown("### 🏀 Away Offense vs Home Defense")
        
        # Build matchup data
        matchup_rows_left = []
        
        # Offensive Rating vs Defensive Rating
        away_ortg = get_stat(functions.away_team_ortg, functions.l5_away_team_ortg)
        away_ortg_rk = get_rank(functions.away_team_ortg_rank, functions.l5_away_team_ortg_rank)
        home_drtg = get_stat(functions.home_team_drtg, functions.l5_home_team_drtg)
        home_drtg_rk = get_rank(functions.home_team_drtg_rank, functions.l5_home_team_drtg_rank)
        la_ortg = get_la(functions.la_ortg, functions.l5_la_ortg)
        matchup_rows_left.append({
            'Metric': 'Offensive Rating',
            'League Avg': f"{la_ortg:.1f}",
            'Away Off': f"{away_ortg:.1f}",
            'Off Rank': away_ortg_rk,
            'Home Def': f"{home_drtg:.1f}",
            'Def Rank': home_drtg_rk,
            'Rank Diff': home_drtg_rk - away_ortg_rk,
            'Color': get_advantage_color(away_ortg_rk, home_drtg_rk, is_offensive=True)
        })
        
        # Offensive Rebound % vs Defensive Rebound %
        away_oreb = get_stat(functions.away_team_oreb, functions.l5_away_team_oreb)
        away_oreb_rk = get_rank(functions.away_team_oreb_rank, functions.l5_away_team_oreb_rank)
        home_dreb = get_stat(functions.home_team_dreb, functions.l5_home_team_dreb)
        home_dreb_rk = get_rank(functions.home_team_dreb_rank, functions.l5_home_team_dreb_rank)
        la_oreb = get_la(functions.la_oreb, functions.l5_la_oreb)
        matchup_rows_left.append({
            'Metric': 'Offensive Rebound %',
            'League Avg': f"{round(la_oreb*100, 3)}%",
            'Away Off': f"{round(away_oreb*100, 3)}%",
            'Off Rank': away_oreb_rk,
            'Home Def': f"{round(home_dreb*100, 3)}%",
            'Def Rank': home_dreb_rk,
            'Rank Diff': home_dreb_rk - away_oreb_rk,
            'Color': get_advantage_color(away_oreb_rk, home_dreb_rk, is_offensive=True)
        })
        
        # Points in Paint - Offense vs Defense
        away_pitp_off = get_stat(functions.away_team_pitp_off, functions.l5_away_team_pitp_off)
        away_pitp_off_rk = get_rank(functions.away_team_pitp_off_rank, functions.l5_away_team_pitp_off_rank)
        home_pitp_def = get_stat(functions.home_team_pitp_def, functions.l5_home_team_pitp_def)
        home_pitp_def_rk = get_rank(functions.home_team_pitp_def_rank, functions.l5_home_team_pitp_def_rank)
        la_pitp_off = get_la(functions.la_pitp_off, functions.l5_la_pitp_off)
        matchup_rows_left.append({
            'Metric': 'Points in Paint',
            'League Avg': f"{la_pitp_off:.1f}",
            'Away Off': f"{away_pitp_off:.1f}",
            'Off Rank': away_pitp_off_rk,
            'Home Def': f"{home_pitp_def:.1f}",
            'Def Rank': home_pitp_def_rk,
            'Rank Diff': home_pitp_def_rk - away_pitp_off_rk,
            'Color': get_advantage_color(away_pitp_off_rk, home_pitp_def_rk, is_offensive=True)
        })
        
        # 2nd Chance Points - Offense vs Defense
        away_2c_off = get_stat(functions.away_team_2c_off, functions.l5_away_team_2c_off)
        away_2c_off_rk = get_rank(functions.away_team_2c_off_rank, functions.l5_away_team_2c_off_rank)
        home_2c_def = get_stat(functions.home_team_2c_def, functions.l5_home_team_2c_def)
        home_2c_def_rk = get_rank(functions.home_team_2c_def_rank, functions.l5_home_team_2c_def_rank)
        la_2c_off = get_la(functions.la_2c_off, functions.l5_la_2c_off)
        matchup_rows_left.append({
            'Metric': '2nd Chance Points',
            'League Avg': f"{la_2c_off:.1f}",
            'Away Off': f"{away_2c_off:.1f}",
            'Off Rank': away_2c_off_rk,
            'Home Def': f"{home_2c_def:.1f}",
            'Def Rank': home_2c_def_rk,
            'Rank Diff': home_2c_def_rk - away_2c_off_rk,
            'Color': get_advantage_color(away_2c_off_rk, home_2c_def_rk, is_offensive=True)
        })
        
        # Fast Break Points - Offense vs Defense
        away_fb_off = get_stat(functions.away_team_fb_off, functions.l5_away_team_fb_off)
        away_fb_off_rk = get_rank(functions.away_team_fb_off_rank, functions.l5_away_team_fb_off_rank)
        home_fb_def = get_stat(functions.home_team_fb_def, functions.l5_home_team_fb_def)
        home_fb_def_rk = get_rank(functions.home_team_fb_def_rank, functions.l5_home_team_fb_def_rank)
        la_fb_off = get_la(functions.la_fb_off, functions.l5_la_fb_off)
        matchup_rows_left.append({
            'Metric': 'Fast Break Points',
            'League Avg': f"{la_fb_off:.1f}",
            'Away Off': f"{away_fb_off:.1f}",
            'Off Rank': away_fb_off_rk,
            'Home Def': f"{home_fb_def:.1f}",
            'Def Rank': home_fb_def_rk,
            'Rank Diff': home_fb_def_rk - away_fb_off_rk,
            'Color': get_advantage_color(away_fb_off_rk, home_fb_def_rk, is_offensive=True)
        })
        
        # Assists
        away_ast = get_stat(functions.away_team_ast, functions.l5_away_team_ast)
        away_ast_rk = get_rank(functions.away_team_ast_rank, functions.l5_away_team_ast_rank)
        la_ast = get_la(functions.la_ast, functions.l5_la_ast)
        matchup_rows_left.append({
            'Metric': 'Assists',
            'League Avg': f"{la_ast:.1f}",
            'Away Off': f"{away_ast:.1f}",
            'Off Rank': away_ast_rk,
            'Home Def': '—',
            'Def Rank': '—',
            'Rank Diff': None,
            'Color': "#ffffff"
        })
        
        # Assist Percentage
        away_ast_pct = get_stat(functions.away_team_ast_pct, functions.l5_away_team_ast_pct)
        away_ast_pct_rk = get_rank(functions.away_team_ast_pct_rank, functions.l5_away_team_ast_pct_rank)
        la_ast_pct = get_la(functions.la_ast_pct, functions.l5_la_ast_pct)
        matchup_rows_left.append({
            'Metric': 'Assist %',
            'League Avg': f"{round(la_ast_pct*100, 3)}%",
            'Away Off': f"{round(away_ast_pct*100, 3)}%",
            'Off Rank': away_ast_pct_rk,
            'Home Def': '—',
            'Def Rank': '—',
            'Rank Diff': None,
            'Color': "#ffffff"
        })
        
        # Turnovers (lower is better for offense)
        away_tov = get_stat(functions.away_team_tov, functions.l5_away_team_tov)
        away_tov_rk = get_rank(functions.away_team_tov_rank, functions.l5_away_team_tov_rank)
        la_tov = get_la(functions.la_tov, functions.l5_la_tov)
        matchup_rows_left.append({
            'Metric': 'Turnovers',
            'League Avg': f"{la_tov:.1f}",
            'Away Off': f"{away_tov:.1f}",
            'Off Rank': away_tov_rk,
            'Home Def': '—',
            'Def Rank': '—',
            'Rank Diff': None,
            'Color': "#ffffff"
        })
        
        # Turnover Percentage
        away_tov_pct = get_stat(functions.away_team_tov_pct, functions.l5_away_team_tov_pct)
        away_tov_pct_rk = get_rank(functions.away_team_tov_pct_rank, functions.l5_away_team_tov_pct_rank)
        la_tov_pct = get_la(functions.la_tov_pct, functions.l5_la_tov_pct)
        matchup_rows_left.append({
            'Metric': 'TOV %',
            'League Avg': f"{round(la_tov_pct*100, 3)}%",
            'Away Off': f"{round(away_tov_pct*100, 3)}%",
            'Off Rank': away_tov_pct_rk,
            'Home Def': '—',
            'Def Rank': '—',
            'Rank Diff': None,
            'Color': "#ffffff"
        })
        
        # Points off Turnovers - Away Offense vs Home Defense
        away_pts_off_tov = get_stat(functions.away_team_pts_off_tov, functions.l5_away_team_pts_off_tov)
        away_pts_off_tov_rk = get_rank(functions.away_team_pts_off_tov_rank, functions.l5_away_team_pts_off_tov_rank)
        home_opp_pts_off_tov = get_stat(functions.home_team_opp_pts_off_tov, functions.l5_home_team_opp_pts_off_tov)
        home_opp_pts_off_tov_rk = get_rank(functions.home_team_opp_pts_off_tov_rank, functions.l5_home_team_opp_pts_off_tov_rank)
        la_pts_off_tov = get_la(functions.la_pts_off_tov, functions.l5_la_pts_off_tov)
        matchup_rows_left.append({
            'Metric': 'TOV% and Points off TOV',
            'League Avg': f"{la_pts_off_tov:.1f}",
            'Away Off': f"{away_pts_off_tov:.1f}",
            'Off Rank': away_pts_off_tov_rk,
            'Home Def': f"{home_opp_pts_off_tov:.1f}",
            'Def Rank': home_opp_pts_off_tov_rk,
            'Rank Diff': home_opp_pts_off_tov_rk - away_pts_off_tov_rk,
            'Color': get_advantage_color(away_pts_off_tov_rk, home_opp_pts_off_tov_rk, is_offensive=True)
        })
        
        # Assist-to-Turnover Ratio
        away_ast_tov = get_stat(functions.away_team_ast_tov, functions.l5_away_team_ast_tov)
        away_ast_tov_rk = get_rank(functions.away_team_ast_tov_rank, functions.l5_away_team_ast_tov_rank)
        la_ast_tov = get_la(functions.la_ast_tov, functions.l5_la_ast_tov)
        matchup_rows_left.append({
            'Metric': 'AST/TOV Ratio',
            'League Avg': f"{la_ast_tov:.2f}",
            'Away Off': f"{away_ast_tov:.2f}",
            'Off Rank': away_ast_tov_rk,
            'Home Def': '—',
            'Def Rank': '—',
            'Rank Diff': None,
            'Color': "#ffffff"
        })
        
        # Starters Scoring
        away_starters = get_stat(functions.away_team_starters_scoring, functions.l5_away_team_starters_scoring)
        away_starters_rk = get_rank(functions.away_team_starters_scoring_rank, functions.l5_away_team_starters_scoring_rank)
        la_starters = get_la(functions.la_starters_scoring, functions.l5_la_starters_scoring)
        matchup_rows_left.append({
            'Metric': 'Starters Scoring',
            'League Avg': f"{la_starters:.1f}",
            'Away Off': f"{away_starters:.1f}",
            'Off Rank': away_starters_rk,
            'Home Def': '—',
            'Def Rank': '—',
            'Rank Diff': None,
            'Color': "#ffffff"
        })
        
        # Bench Scoring
        away_bench = get_stat(functions.away_team_bench_scoring, functions.l5_away_team_bench_scoring)
        away_bench_rk = get_rank(functions.away_team_bench_scoring_rank, functions.l5_away_team_bench_scoring_rank)
        la_bench = get_la(functions.la_bench_scoring, functions.l5_la_bench_scoring)
        matchup_rows_left.append({
            'Metric': 'Bench Scoring',
            'League Avg': f"{la_bench:.1f}",
            'Away Off': f"{away_bench:.1f}",
            'Off Rank': away_bench_rk,
            'Home Def': '—',
            'Def Rank': '—',
            'Rank Diff': None,
            'Color': "#ffffff"
        })
        
        # Create DataFrame
        df_left = pd.DataFrame(matchup_rows_left)
        
        # Separate rows with and without Rank Diff
        df_left_with_diff = df_left[df_left['Rank Diff'].notna()].copy().reset_index(drop=True)
        df_left_without_diff = df_left[df_left['Rank Diff'].isna()].copy()
        
        # Format Rank Diff as integer
        if len(df_left_with_diff) > 0:
            df_left_with_diff['Rank Diff'] = df_left_with_diff['Rank Diff'].astype(int)
        
        # Display table with renamed columns (only rows with Rank Diff)
        if len(df_left_with_diff) > 0:
            display_df_left = df_left_with_diff[['Metric', 'League Avg', 'Away Off', 'Off Rank', 'Home Def', 'Def Rank', 'Rank Diff']].copy()
            display_df_left.columns = ['Metric', 'League Avg', 'Away Off', 'Off RK', 'Home Def', 'Def RK', 'Rank Diff']
            
            def highlight_matchup_left_display(row):
                # Use the row index directly since we reset the index
                color = df_left_with_diff.iloc[row.name]['Color']
                return [f"background-color: {color}"] * len(row)
            
            st.dataframe(
                display_df_left.style.apply(highlight_matchup_left_display, axis=1),
                use_container_width=True,
                hide_index=True
            )
        
        # Store rows without Rank Diff for later display in overall metrics section
        st.session_state['left_no_diff'] = df_left_without_diff
    
    # RIGHT COLUMN: Away Defense vs Home Offense
    with col_right:
        st.markdown("### 🛡️ Away Defense vs Home Offense")
        
        # Build matchup data
        matchup_rows_right = []
        
        # Defensive Rating vs Offensive Rating
        home_ortg = get_stat(functions.home_team_ortg, functions.l5_home_team_ortg)
        home_ortg_rk = get_rank(functions.home_team_ortg_rank, functions.l5_home_team_ortg_rank)
        away_drtg = get_stat(functions.away_team_drtg, functions.l5_away_team_drtg)
        away_drtg_rk = get_rank(functions.away_team_drtg_rank, functions.l5_away_team_drtg_rank)
        la_drtg = get_la(functions.la_drtg, functions.l5_la_drtg)
        matchup_rows_right.append({
            'Metric': 'Defensive Rating',
            'League Avg': f"{la_drtg:.1f}",
            'Home Off': f"{home_ortg:.1f}",
            'Off Rank': home_ortg_rk,
            'Away Def': f"{away_drtg:.1f}",
            'Def Rank': away_drtg_rk,
            'Rank Diff': away_drtg_rk - home_ortg_rk,  # Lower defensive rank is better
            'Color': get_advantage_color(home_ortg_rk, away_drtg_rk, is_offensive=False)
        })
        
        # Defensive Rebound % vs Offensive Rebound %
        home_oreb = get_stat(functions.home_team_oreb, functions.l5_home_team_oreb)
        home_oreb_rk = get_rank(functions.home_team_oreb_rank, functions.l5_home_team_oreb_rank)
        away_dreb = get_stat(functions.away_team_dreb, functions.l5_away_team_dreb)
        away_dreb_rk = get_rank(functions.away_team_dreb_rank, functions.l5_away_team_dreb_rank)
        la_dreb = get_la(functions.la_dreb, functions.l5_la_dreb)
        matchup_rows_right.append({
            'Metric': 'Defensive Rebound %',
            'League Avg': f"{round(la_dreb*100, 3)}%",
            'Home Off': f"{round(home_oreb*100, 3)}%",
            'Off Rank': home_oreb_rk,
            'Away Def': f"{round(away_dreb*100, 3)}%",
            'Def Rank': away_dreb_rk,
            'Rank Diff': home_oreb_rk - away_dreb_rk,  # Higher defensive rebound % is better
            'Color': get_advantage_color(home_oreb_rk, away_dreb_rk, is_offensive=False)
        })
        
        # Points in Paint - Defense vs Offense
        home_pitp_off = get_stat(functions.home_team_pitp_off, functions.l5_home_team_pitp_off)
        home_pitp_off_rk = get_rank(functions.home_team_pitp_off_rank, functions.l5_home_team_pitp_off_rank)
        away_pitp_def = get_stat(functions.away_team_pitp_def, functions.l5_away_team_pitp_def)
        away_pitp_def_rk = get_rank(functions.away_team_pitp_def_rank, functions.l5_away_team_pitp_def_rank)
        la_pitp_def = get_la(functions.la_pitp_def, functions.l5_la_pitp_def)
        matchup_rows_right.append({
            'Metric': 'Points in Paint',
            'League Avg': f"{la_pitp_def:.1f}",
            'Home Off': f"{home_pitp_off:.1f}",
            'Off Rank': home_pitp_off_rk,
            'Away Def': f"{away_pitp_def:.1f}",
            'Def Rank': away_pitp_def_rk,
            'Rank Diff': home_pitp_off_rk - away_pitp_def_rk,  # Lower points allowed is better
            'Color': get_advantage_color(home_pitp_off_rk, away_pitp_def_rk, is_offensive=False)
        })
        
        # 2nd Chance Points - Defense vs Offense
        home_2c_off = get_stat(functions.home_team_2c_off, functions.l5_home_team_2c_off)
        home_2c_off_rk = get_rank(functions.home_team_2c_off_rank, functions.l5_home_team_2c_off_rank)
        away_2c_def = get_stat(functions.away_team_2c_def, functions.l5_away_team_2c_def)
        away_2c_def_rk = get_rank(functions.away_team_2c_def_rank, functions.l5_away_team_2c_def_rank)
        la_2c_def = get_la(functions.la_2c_def, functions.l5_la_2c_def)
        matchup_rows_right.append({
            'Metric': '2nd Chance Points',
            'League Avg': f"{la_2c_def:.1f}",
            'Home Off': f"{home_2c_off:.1f}",
            'Off Rank': home_2c_off_rk,
            'Away Def': f"{away_2c_def:.1f}",
            'Def Rank': away_2c_def_rk,
            'Rank Diff': home_2c_off_rk - away_2c_def_rk,
            'Color': get_advantage_color(home_2c_off_rk, away_2c_def_rk, is_offensive=False)
        })
        
        # Fast Break Points - Defense vs Offense
        home_fb_off = get_stat(functions.home_team_fb_off, functions.l5_home_team_fb_off)
        home_fb_off_rk = get_rank(functions.home_team_fb_off_rank, functions.l5_home_team_fb_off_rank)
        away_fb_def = get_stat(functions.away_team_fb_def, functions.l5_away_team_fb_def)
        away_fb_def_rk = get_rank(functions.away_team_fb_def_rank, functions.l5_away_team_fb_def_rank)
        la_fb_def = get_la(functions.la_fb_def, functions.l5_la_fb_def)
        matchup_rows_right.append({
            'Metric': 'Fast Break Points',
            'League Avg': f"{la_fb_def:.1f}",
            'Home Off': f"{home_fb_off:.1f}",
            'Off Rank': home_fb_off_rk,
            'Away Def': f"{away_fb_def:.1f}",
            'Def Rank': away_fb_def_rk,
            'Rank Diff': home_fb_off_rk - away_fb_def_rk,
            'Color': get_advantage_color(home_fb_off_rk, away_fb_def_rk, is_offensive=False)
        })
        
        # Opponent Turnover Percentage
        away_opp_tov_pct = get_stat(functions.away_team_opp_tov_pct, functions.l5_away_team_opp_tov_pct)
        away_opp_tov_pct_rk = get_rank(functions.away_team_opp_tov_pct_rank, functions.l5_away_team_opp_tov_pct_rank)
        la_opp_tov_pct = get_la(functions.la_opp_tov_pct, functions.l5_la_opp_tov_pct)
        matchup_rows_right.append({
            'Metric': 'Opp. TOV %',
            'League Avg': f"{round(la_opp_tov_pct*100, 3)}%",
            'Home Off': '—',
            'Off Rank': '—',
            'Away Def': f"{round(away_opp_tov_pct*100, 3)}%",
            'Def Rank': away_opp_tov_pct_rk,
            'Rank Diff': None,
            'Color': "#ffffff"
        })
        
        # Points off Turnovers - Away Defense vs Home Offense (reversed)
        away_opp_pts_off_tov = get_stat(functions.away_team_opp_pts_off_tov, functions.l5_away_team_opp_pts_off_tov)
        away_opp_pts_off_tov_rk = get_rank(functions.away_team_opp_pts_off_tov_rank, functions.l5_away_team_opp_pts_off_tov_rank)
        home_pts_off_tov = get_stat(functions.home_team_pts_off_tov, functions.l5_home_team_pts_off_tov)
        home_pts_off_tov_rk = get_rank(functions.home_team_pts_off_tov_rank, functions.l5_home_team_pts_off_tov_rank)
        la_opp_pts_off_tov = get_la(functions.la_opp_pts_off_tov, functions.l5_la_opp_pts_off_tov)
        matchup_rows_right.append({
            'Metric': 'TOV% and Points off TOV',
            'League Avg': f"{la_opp_pts_off_tov:.1f}",
            'Home Off': f"{home_pts_off_tov:.1f}",
            'Off Rank': home_pts_off_tov_rk,
            'Away Def': f"{away_opp_pts_off_tov:.1f}",
            'Def Rank': away_opp_pts_off_tov_rk,
            'Rank Diff': away_opp_pts_off_tov_rk - home_pts_off_tov_rk,
            'Color': get_advantage_color(home_pts_off_tov_rk, away_opp_pts_off_tov_rk, is_offensive=False)
        })
        
        # Create DataFrame
        df_right = pd.DataFrame(matchup_rows_right)
        
        # Separate rows with and without Rank Diff
        df_right_with_diff = df_right[df_right['Rank Diff'].notna()].copy().reset_index(drop=True)
        df_right_without_diff = df_right[df_right['Rank Diff'].isna()].copy()
        
        # Format Rank Diff as integer
        if len(df_right_with_diff) > 0:
            df_right_with_diff['Rank Diff'] = df_right_with_diff['Rank Diff'].astype(int)
        
        # Display table with renamed columns (only rows with Rank Diff)
        if len(df_right_with_diff) > 0:
            display_df_right = df_right_with_diff[['Metric', 'League Avg', 'Home Off', 'Off Rank', 'Away Def', 'Def Rank', 'Rank Diff']].copy()
            display_df_right.columns = ['Metric', 'League Avg', 'Home Off', 'Off RK', 'Away Def', 'Def RK', 'Rank Diff']
            
            def highlight_matchup_right_display(row):
                # Use the row index directly since we reset the index
                color = df_right_with_diff.iloc[row.name]['Color']
                return [f"background-color: {color}"] * len(row)
            
            st.dataframe(
                display_df_right.style.apply(highlight_matchup_right_display, axis=1),
                use_container_width=True,
                hide_index=True
            )
        
        # Store rows without Rank Diff for later display in overall metrics section
        st.session_state['right_no_diff'] = df_right_without_diff
    
    # Legend
    st.caption("🟢 Green = Advantage (>10 rank diff) | 🔴 Red = Disadvantage (<-10 rank diff) | 🟡 Yellow = Neutral (±10 ranks)")
    
    # Additional metrics section (Net Rating, Pace, Rebound %, etc.)
    st.markdown("---")
    st.markdown("### Overall Team Metrics")
    
    col_net1, col_net2, col_net3, col_net4 = st.columns(4)
    
    with col_net1:
        st.metric(
            "Away Net Rating",
            f"{get_stat(functions.away_team_net, functions.l5_away_team_net):.1f}",
            delta=f"Rank: {get_rank(functions.away_team_net_rank, functions.l5_away_team_net_rank)}"
        )
    
    with col_net2:
        st.metric(
            "Home Net Rating",
            f"{get_stat(functions.home_team_net, functions.l5_home_team_net):.1f}",
            delta=f"Rank: {get_rank(functions.home_team_net_rank, functions.l5_home_team_net_rank)}"
        )
    
    with col_net3:
        st.metric(
            "Pace",
            f"{get_stat(functions.away_team_pace, functions.l5_away_team_pace):.1f}",
            delta=f"Rank: {get_rank(functions.away_team_pace_rank, functions.l5_away_team_pace_rank)}"
        )
    
    with col_net4:
        st.metric(
            "Rebound %",
            f"{round(get_stat(functions.away_team_reb, functions.l5_away_team_reb)*100, 3)}%",
            delta=f"Rank: {get_rank(functions.away_team_reb_rank, functions.l5_away_team_reb_rank)}"
        )
    
    # Display rows without Rank Diff from both tables
    if 'left_no_diff' in st.session_state and len(st.session_state['left_no_diff']) > 0:
        st.markdown("#### Additional Metrics (Away Offense)")
        df_left_no_diff = st.session_state['left_no_diff'][['Metric', 'League Avg', 'Away Off', 'Off Rank']].copy()
        df_left_no_diff.columns = ['Metric', 'League Avg', 'Away Off', 'Off RK']
        st.dataframe(df_left_no_diff, use_container_width=True, hide_index=True)
    
    if 'right_no_diff' in st.session_state and len(st.session_state['right_no_diff']) > 0:
        st.markdown("#### Additional Metrics (Away Defense)")
        df_right_no_diff = st.session_state['right_no_diff'][['Metric', 'League Avg', 'Away Def', 'Def Rank']].copy()
        df_right_no_diff.columns = ['Metric', 'League Avg', 'Away Def', 'Def RK']
        st.dataframe(df_right_no_diff, use_container_width=True, hide_index=True)

elif tab == 'Shooting':
    # Keep existing shooting tab structure
    st.write("Shooting tab - keeping existing structure for now")

elif tab in ('Players', 'Lineups'):
    st.write("Still Under Development")

