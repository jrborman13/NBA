import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'streamlit'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'new-streamlit-app', 'player-app'))

import streamlit as st
import pandas as pd
import datetime
from datetime import date
from PIL import Image, ImageDraw, ImageFont
import io
import nba_api.stats.endpoints
import requests
import vegas_lines as vl
import streamlit_testing_functions as functions
import injury_report as ir

st.set_page_config(layout="wide")
st.title("📱 Social Media Image Generator")

# Function to fetch matchups for a given date
@st.cache_data(ttl=3600)
def get_matchups_for_date(selected_date):
    """Fetch NBA matchups for a given date from the API"""
    try:
        league_schedule = nba_api.stats.endpoints.ScheduleLeagueV2(
            league_id='00',
            season='2025-26'
        ).get_data_frames()[0]
        
        # Convert game date column to datetime
        league_schedule['dateGame'] = pd.to_datetime(league_schedule['gameDate'])
        
        # Compare date parts only to handle datetime objects with time components
        date_games = league_schedule[
            league_schedule['dateGame'].dt.date == selected_date
        ]
        
        matchups = []
        for _, row in date_games.iterrows():
            matchup = {
                'away_team': row.get('awayTeam_teamTricode', ''),
                'home_team': row.get('homeTeam_teamTricode', ''),
                'away_team_id': row.get('awayTeam_teamId', ''),
                'home_team_id': row.get('homeTeam_teamId', ''),
                'game_date': selected_date.strftime('%Y-%m-%d'),
                'game_id': row.get('gameId', '')
            }
            matchups.append(matchup)
        
        return matchups
    except Exception as e:
        st.error(f"Error fetching schedule: {str(e)}")
        return []

# Date selector
selected_date = st.date_input(
    "Select Game Date",
    value=date.today(),
    key="social_date"
)

# Get matchups
matchups = get_matchups_for_date(selected_date)

if not matchups:
    st.warning("No games found for this date.")
    st.stop()

# Matchup selector
matchup_options = [f"{m['away_team']} @ {m['home_team']}" for m in matchups]
selected_matchup_str = st.selectbox("Select Matchup", matchup_options)

# Get selected matchup
selected_matchup = None
for m in matchups:
    if f"{m['away_team']} @ {m['home_team']}" == selected_matchup_str:
        selected_matchup = m
        break

if not selected_matchup:
    st.stop()

# Get team data for the matchup
@st.cache_data(ttl=3600)
def get_team_stats(team_id, season='2025-26'):
    """Get team stats for display"""
    try:
        team_stats = nba_api.stats.endpoints.TeamDashboardByGeneralSplits(
            team_id=team_id,
            season=season,
            season_type_all_star='Regular Season'
        )
        df = team_stats.get_data_frames()[0]
        if len(df) > 0:
            return {
                'ORTG': df['OFF_RATING'].iloc[0] if 'OFF_RATING' in df.columns else 0,
                'DRTG': df['DEF_RATING'].iloc[0] if 'DEF_RATING' in df.columns else 0,
                'NET_RTG': df['NET_RATING'].iloc[0] if 'NET_RATING' in df.columns else 0,
                'PACE': df['PACE'].iloc[0] if 'PACE' in df.columns else 0,
                'FG_PCT': df['FG_PCT'].iloc[0] * 100 if 'FG_PCT' in df.columns else 0,
                'FG3_PCT': df['FG3_PCT'].iloc[0] * 100 if 'FG3_PCT' in df.columns else 0,
            }
    except:
        pass
    return {}

away_stats = get_team_stats(selected_matchup['away_team_id'])
home_stats = get_team_stats(selected_matchup['home_team_id'])

# Function to get game lines (total and spread) from DraftKings via The Odds API
@st.cache_data(ttl=1800)  # Cache for 30 minutes
def get_game_lines(away_team, home_team, game_date):
    """Get total and spread from DraftKings via The Odds API"""
    try:
        # Get events for the date
        events, error = vl.get_nba_events(game_date)
        if error or not events:
            return None, None, error
        
        # Find the matching event
        event = vl.find_event_for_matchup(events, home_team, away_team)
        if not event:
            return None, None, "Event not found"
        
        event_id = event['id']
        
        # Fetch odds for game lines (totals and spreads)
        # Use 'totals' and 'spreads' markets (these are FREE - game lines don't cost credits)
        url = f"{vl.ODDS_API_BASE}/sports/{vl.SPORT}/events/{event_id}/odds"
        params = {
            'apiKey': vl.ODDS_API_KEY,
            'regions': 'us',  # Use 'us' for game lines (DraftKings)
            'bookmakers': 'draftkings',
            'markets': 'totals,spreads',
            'oddsFormat': 'american',
            'dateFormat': 'iso'
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            total = None
            spread = None
            
            if 'bookmakers' in data and len(data['bookmakers']) > 0:
                bookmaker = data['bookmakers'][0]
                
                # Extract totals
                if 'markets' in bookmaker:
                    for market in bookmaker['markets']:
                        if market['key'] == 'totals':
                            if 'outcomes' in market and len(market['outcomes']) > 0:
                                total = market['outcomes'][0].get('point', None)
                                break
                        
                        if market['key'] == 'spreads':
                            if 'outcomes' in market:
                                # Find the home team spread
                                for outcome in market['outcomes']:
                                    if outcome.get('name', '').upper() == home_team.upper():
                                        spread = outcome.get('point', None)
                                        break
                                if spread is None and len(market['outcomes']) > 0:
                                    # Fallback to first outcome
                                    spread = market['outcomes'][0].get('point', None)
            
            return total, spread, None
        else:
            return None, None, f"API error: {response.status_code}"
            
    except Exception as e:
        return None, None, str(e)

# Get game lines
total, spread, lines_error = get_game_lines(
    selected_matchup['away_team'],
    selected_matchup['home_team'],
    selected_matchup['game_date']
)

if lines_error:
    st.info(f"⚠️ Could not fetch betting lines: {lines_error}")

# Generate matchup summary data
@st.cache_data(ttl=1800)
def load_summary_data():
    players_df = functions.get_players_dataframe()
    game_logs_df = functions.get_all_player_game_logs()
    return players_df, game_logs_df

summary_players_df, summary_game_logs_df = load_summary_data()

# Fetch injury report for the date
@st.cache_data(ttl=600, show_spinner=False)
def fetch_summary_injuries():
    return ir.fetch_injuries_for_date()

summary_injury_df, _ = fetch_summary_injuries()

# Get injuries for matchup
summary_away_injuries = []
summary_home_injuries = []
if summary_injury_df is not None and len(summary_injury_df) > 0:
    matchup_injuries = ir.get_injuries_for_matchup(
        summary_injury_df,
        selected_matchup['away_team'],
        selected_matchup['home_team'],
        summary_players_df
    )
    summary_away_injuries = matchup_injuries.get('away', [])
    summary_home_injuries = matchup_injuries.get('home', [])

# Generate matchup summary
matchup_summary = functions.generate_matchup_summary(
    away_id=selected_matchup['away_team_id'],
    home_id=selected_matchup['home_team_id'],
    away_name=selected_matchup.get('away_team_name', selected_matchup['away_team']),
    home_name=selected_matchup.get('home_team_name', selected_matchup['home_team']),
    away_abbr=selected_matchup['away_team'],
    home_abbr=selected_matchup['home_team'],
    players_df=summary_players_df,
    game_logs_df=summary_game_logs_df,
    away_injuries=summary_away_injuries,
    home_injuries=summary_home_injuries
)

# Image generation function
def generate_matchup_image(away_team, home_team, away_stats, home_stats, game_date, 
                           matchup_summary, total=None, spread=None):
    """Generate a Twitter-friendly matchup image styled like the Matchup Summary"""
    # Taller image to fit matchup summary content
    width, height = 1200, 1400
    img = Image.new('RGB', (width, height), color='#0a0a0a')
    draw = ImageDraw.Draw(img)
    
    try:
        title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 56)
        section_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 32)
        header_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
        text_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 18)
        small_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
    except:
        title_font = ImageFont.load_default()
        section_font = ImageFont.load_default()
        header_font = ImageFont.load_default()
        text_font = ImageFont.load_default()
        small_font = ImageFont.load_default()
    
    white = '#FFFFFF'
    gray = '#888888'
    accent = '#1DA1F2'
    
    y_pos = 40
    
    # Title
    title = f"{away_team} @ {home_team}"
    title_bbox = draw.textbbox((0, 0), title, font=title_font)
    title_width = title_bbox[2] - title_bbox[0]
    draw.text(((width - title_width) // 2, y_pos), title, fill=white, font=title_font)
    y_pos += 70
    
    # Date
    date_str = datetime.datetime.strptime(game_date, '%Y-%m-%d').strftime('%B %d, %Y')
    date_bbox = draw.textbbox((0, 0), date_str, font=small_font)
    date_width = date_bbox[2] - date_bbox[0]
    draw.text(((width - date_width) // 2, y_pos), date_str, fill=gray, font=small_font)
    y_pos += 40
    
    # Betting lines
    if total is not None or spread is not None:
        lines_parts = []
        if spread is not None:
            lines_parts.append(f"{home_team} {spread:+.1f}")
        if total is not None:
            lines_parts.append(f"O/U {total:.1f}")
        if lines_parts:
            lines_text = " | ".join(lines_parts)
            lines_bbox = draw.textbbox((0, 0), lines_text, font=text_font)
            lines_width = lines_bbox[2] - lines_bbox[0]
            draw.text(((width - lines_width) // 2, y_pos), lines_text, fill=accent, font=text_font)
            y_pos += 35
    
    y_pos += 20
    
    # Column positions
    x_left = 50
    x_right = width // 2 + 25
    
    # === BIGGEST MISMATCHES ===
    draw.text((x_left, y_pos), "🔥 Biggest Stat Mismatches", fill=white, font=section_font)
    y_pos += 45
    
    mismatches = matchup_summary.get('mismatches', [])
    away_advantages = [m for m in mismatches if m['team_with_advantage'] == away_team][:5]
    home_advantages = [m for m in mismatches if m['team_with_advantage'] == home_team][:5]
    
    # Left column - Away advantages
    draw.text((x_left, y_pos), f"{away_team} Advantages", fill=white, font=header_font)
    y_temp = y_pos + 30
    for m in away_advantages:
        arrow = "🟢" if m['rank_diff'] >= 15 else "🟡" if m['rank_diff'] >= 10 else "⚪"
        text = f"{arrow} {m['stat_name']}: #{m['off_rank']} vs #{m['def_rank']} (+{m['rank_diff']})"
        draw.text((x_left, y_temp), text, fill=white, font=text_font)
        y_temp += 25
    
    # Right column - Home advantages
    draw.text((x_right, y_pos), f"{home_team} Advantages", fill=white, font=header_font)
    y_temp = y_pos + 30
    for m in home_advantages:
        arrow = "🟢" if m['rank_diff'] >= 15 else "🟡" if m['rank_diff'] >= 10 else "⚪"
        text = f"{arrow} {m['stat_name']}: #{m['off_rank']} vs #{m['def_rank']} (+{m['rank_diff']})"
        draw.text((x_right, y_temp), text, fill=white, font=text_font)
        y_temp += 25
    
    y_pos = max(y_pos + 30 + len(away_advantages) * 25, y_pos + 30 + len(home_advantages) * 25) + 30
    
    # === HOT PLAYERS ===
    draw.text((x_left, y_pos), "📈 Hot Players (20%+ Above Season Avg)", fill=white, font=section_font)
    y_pos += 45
    
    hot_players = matchup_summary.get('hot_players', {})
    away_hot = hot_players.get('away', [])[:3]
    home_hot = hot_players.get('home', [])[:3]
    
    # Left column
    draw.text((x_left, y_pos), away_team, fill=white, font=header_font)
    y_temp = y_pos + 30
    for p in away_hot:
        hot_stat = p['hot_stats'][0]
        pct = int(hot_stat['pct_change'] * 100)
        text = f"🔥 {p['player_name']}: {hot_stat['l5']:.1f} {hot_stat['stat']} (+{pct}%)"
        draw.text((x_left, y_temp), text, fill=white, font=text_font)
        y_temp += 25
    
    # Right column
    draw.text((x_right, y_pos), home_team, fill=white, font=header_font)
    y_temp = y_pos + 30
    for p in home_hot:
        hot_stat = p['hot_stats'][0]
        pct = int(hot_stat['pct_change'] * 100)
        text = f"🔥 {p['player_name']}: {hot_stat['l5']:.1f} {hot_stat['stat']} (+{pct}%)"
        draw.text((x_right, y_temp), text, fill=white, font=text_font)
        y_temp += 25
    
    y_pos = max(y_pos + 30 + len(away_hot) * 25, y_pos + 30 + len(home_hot) * 25) + 30
    
    # === KEY INJURIES ===
    draw.text((x_left, y_pos), "🏥 Key Injuries", fill=white, font=section_font)
    y_pos += 45
    
    key_injuries = matchup_summary.get('key_injuries', {})
    away_inj = key_injuries.get('away', [])[:3]
    home_inj = key_injuries.get('home', [])[:3]
    
    def get_status_badge(status):
        status_lower = status.lower() if status else ''
        if 'out' in status_lower:
            return "🔴"
        elif 'doubtful' in status_lower:
            return "🟠"
        elif 'questionable' in status_lower:
            return "🟡"
        else:
            return "⚪"
    
    # Left column
    draw.text((x_left, y_pos), away_team, fill=white, font=header_font)
    y_temp = y_pos + 30
    for inj in away_inj:
        badge = get_status_badge(inj.get('status', ''))
        player_name = ir.format_player_name(inj.get('player_name', 'Unknown'))
        status = inj.get('status', 'Unknown')
        text = f"{badge} {player_name} ({status})"
        draw.text((x_left, y_temp), text, fill=white, font=text_font)
        y_temp += 25
    
    # Right column
    draw.text((x_right, y_pos), home_team, fill=white, font=header_font)
    y_temp = y_pos + 30
    for inj in home_inj:
        badge = get_status_badge(inj.get('status', ''))
        player_name = ir.format_player_name(inj.get('player_name', 'Unknown'))
        status = inj.get('status', 'Unknown')
        text = f"{badge} {player_name} ({status})"
        draw.text((x_right, y_temp), text, fill=white, font=text_font)
        y_temp += 25
    
    # Footer
    footer_text = "NBA Matchup Breakdown"
    footer_bbox = draw.textbbox((0, 0), footer_text, font=small_font)
    footer_width = footer_bbox[2] - footer_bbox[0]
    draw.text(((width - footer_width) // 2, height - 40), footer_text, fill=gray, font=small_font)
    
    return img

# Generate image
if st.button("Generate Image", type="primary"):
    with st.spinner("Generating matchup image..."):
        img = generate_matchup_image(
            selected_matchup['away_team'],
            selected_matchup['home_team'],
            away_stats,
            home_stats,
            selected_matchup['game_date'],
            matchup_summary,
            total=total,
            spread=spread
        )
        
        # Display preview
        st.image(img, caption=f"{selected_matchup['away_team']} @ {selected_matchup['home_team']} - {selected_matchup['game_date']}")
        
        # Convert to bytes for download
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        
        # Download button
        st.download_button(
            label="Download Image",
            data=img_buffer,
            file_name=f"{selected_matchup['away_team']}_{selected_matchup['home_team']}_{selected_matchup['game_date']}.png",
            mime="image/png"
        )

