"""
Player Similarity Module
Calculates similarity scores between NBA players based on comprehensive stat profiles.
Used for:
1. Displaying similar players on player profiles
2. Adjusting predictions based on similar players' performance vs. opponents
"""

import pandas as pd
import numpy as np
import streamlit as st
from typing import Dict, List, Tuple, Optional
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.metrics.pairwise import cosine_similarity
import nba_api.stats.endpoints as endpoints

# Current season configuration
CURRENT_SEASON = "2025-26"
SEASON_TYPE = "Regular Season"

# Minimum games/minutes thresholds
MIN_GAMES = 5
MIN_MINUTES = 10.0


# =============================================================================
# DATA FETCHING FUNCTIONS
# =============================================================================

@st.cache_data(ttl=3600, show_spinner=False)
def get_all_player_base_stats(season: str = CURRENT_SEASON) -> pd.DataFrame:
    """
    Fetch base per-game stats for all players.
    
    Returns DataFrame with:
    - Basic stats: PTS, REB, AST, STL, BLK, TOV, MIN, GP
    - Shooting: FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT
    """
    try:
        stats = endpoints.LeagueDashPlayerStats(
            season=season,
            per_mode_detailed='PerGame',
            season_type_all_star=SEASON_TYPE
        ).get_data_frames()[0]
        return stats
    except Exception as e:
        print(f"Error fetching base stats: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def get_all_player_misc_stats(season: str = CURRENT_SEASON) -> pd.DataFrame:
    """
    Fetch misc stats (paint scoring, fast break, 2nd chance) for all players.
    """
    try:
        stats = endpoints.LeagueDashPlayerStats(
            measure_type_detailed_defense='Misc',
            per_mode_detailed='PerGame',
            season=season,
            season_type_all_star=SEASON_TYPE
        ).get_data_frames()[0]
        return stats
    except Exception as e:
        print(f"Error fetching misc stats: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def get_all_player_drives_stats(season: str = CURRENT_SEASON) -> pd.DataFrame:
    """
    Fetch drives tracking data for all players.
    """
    try:
        stats = endpoints.LeagueDashPtStats(
            season=season,
            per_mode_simple='PerGame',
            pt_measure_type='Drives',
            player_or_team='Player'
        ).get_data_frames()[0]
        return stats
    except Exception as e:
        print(f"Error fetching drives stats: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def get_all_player_advanced_stats(season: str = CURRENT_SEASON) -> pd.DataFrame:
    """
    Fetch advanced stats (usage rate, etc.) for all players.
    """
    try:
        stats = endpoints.LeagueDashPlayerStats(
            measure_type_detailed_defense='Advanced',
            per_mode_detailed='PerGame',
            season=season,
            season_type_all_star=SEASON_TYPE
        ).get_data_frames()[0]
        return stats
    except Exception as e:
        print(f"Error fetching advanced stats: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def get_player_shooting_zones(season: str = CURRENT_SEASON) -> pd.DataFrame:
    """
    Fetch zone shooting data from pbpstats.
    """
    import requests
    try:
        season_type_url = SEASON_TYPE.replace(' ', '+')
        url = f"https://api.pbpstats.com/get-totals/nba?Season={season}&SeasonType={season_type_url}&Type=Player"
        response = requests.get(url)
        if response.status_code == 200:
            df = pd.DataFrame(response.json()['multi_row_table_data'])
            df['PLAYER_ID'] = df['EntityId'].astype(int)
            return df
        return pd.DataFrame()
    except Exception as e:
        print(f"Error fetching shooting zones: {e}")
        return pd.DataFrame()


# =============================================================================
# SIMILARITY FEATURE BUILDING
# =============================================================================

@st.cache_data(ttl=3600, show_spinner="Building player profiles...")
def build_similarity_features(season: str = CURRENT_SEASON) -> Tuple[pd.DataFrame, List[str]]:
    """
    Build comprehensive feature matrix for player similarity.
    
    Returns:
        Tuple of (feature_df, feature_columns)
        - feature_df: DataFrame with PLAYER_ID, PLAYER_NAME and all features
        - feature_columns: List of column names used for similarity
    """
    # Fetch all data sources
    base_stats = get_all_player_base_stats(season)
    misc_stats = get_all_player_misc_stats(season)
    drives_stats = get_all_player_drives_stats(season)
    advanced_stats = get_all_player_advanced_stats(season)
    shooting_zones = get_player_shooting_zones(season)
    
    if base_stats.empty:
        return pd.DataFrame(), []
    
    # Start with base stats - include TEAM_ID for full team name lookup
    base_cols = ['PLAYER_ID', 'PLAYER_NAME', 'TEAM_ABBREVIATION', 'TEAM_ID', 'GP', 'MIN']
    # Add TEAM_NAME if available (some endpoints have it, some don't)
    if 'TEAM_NAME' in base_stats.columns:
        base_cols.append('TEAM_NAME')
    features = base_stats[[c for c in base_cols if c in base_stats.columns]].copy()
    
    # Filter by minimum games and minutes
    features = features[
        (features['GP'] >= MIN_GAMES) & 
        (features['MIN'] >= MIN_MINUTES)
    ].copy()
    
    if len(features) == 0:
        return pd.DataFrame(), []
    
    # -------------------------------------------------------------------------
    # 1. Basic Per-Game Stats
    # -------------------------------------------------------------------------
    basic_cols = ['PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'MIN']
    for col in basic_cols:
        if col in base_stats.columns:
            features = features.merge(
                base_stats[['PLAYER_ID', col]],
                on='PLAYER_ID',
                how='left',
                suffixes=('', '_dup')
            )
    
    # -------------------------------------------------------------------------
    # 2. Shooting Stats
    # -------------------------------------------------------------------------
    shooting_cols = ['FGM', 'FGA', 'FG_PCT', 'FG3M', 'FG3A', 'FG3_PCT', 'FTM', 'FTA', 'FT_PCT']
    for col in shooting_cols:
        if col in base_stats.columns:
            features = features.merge(
                base_stats[['PLAYER_ID', col]],
                on='PLAYER_ID',
                how='left',
                suffixes=('', '_dup')
            )
    
    # Calculate shooting rates/distribution
    features['FG3A_RATE'] = features['FG3A'] / features['FGA'].replace(0, np.nan)
    features['FTA_RATE'] = features['FTA'] / features['FGA'].replace(0, np.nan)
    
    # -------------------------------------------------------------------------
    # 3. Misc Stats (Paint, Fast Break, 2nd Chance)
    # -------------------------------------------------------------------------
    if not misc_stats.empty:
        misc_cols = ['PTS_PAINT', 'PTS_FB', 'PTS_2ND_CHANCE', 'PTS_OFF_TOV']
        for col in misc_cols:
            if col in misc_stats.columns:
                features = features.merge(
                    misc_stats[['PLAYER_ID', col]],
                    on='PLAYER_ID',
                    how='left',
                    suffixes=('', '_dup')
                )
        
        # Calculate paint scoring rate
        features['PAINT_PTS_RATE'] = features['PTS_PAINT'] / features['PTS'].replace(0, np.nan)
    
    # -------------------------------------------------------------------------
    # 4. Drives Stats
    # -------------------------------------------------------------------------
    if not drives_stats.empty:
        drives_cols = ['DRIVES', 'DRIVE_FG_PCT', 'DRIVE_PTS', 'DRIVE_AST', 'DRIVE_TOV']
        for col in drives_cols:
            if col in drives_stats.columns:
                features = features.merge(
                    drives_stats[['PLAYER_ID', col]],
                    on='PLAYER_ID',
                    how='left',
                    suffixes=('', '_dup')
                )
    
    # -------------------------------------------------------------------------
    # 5. Advanced Stats (Usage Rate)
    # -------------------------------------------------------------------------
    if not advanced_stats.empty:
        if 'USG_PCT' in advanced_stats.columns:
            features = features.merge(
                advanced_stats[['PLAYER_ID', 'USG_PCT']],
                on='PLAYER_ID',
                how='left',
                suffixes=('', '_dup')
            )
    
    # -------------------------------------------------------------------------
    # 6. Zone Shooting (from pbpstats)
    # -------------------------------------------------------------------------
    if not shooting_zones.empty:
        zone_cols = [
            ('AtRimAccuracy', 'RIM_ACC'),
            ('AtRimFrequency', 'RIM_FREQ'),
            ('ShortMidRangeAccuracy', 'SMR_ACC'),
            ('ShortMidRangeFrequency', 'SMR_FREQ'),
            ('LongMidRangeAccuracy', 'LMR_ACC'),
            ('LongMidRangeFrequency', 'LMR_FREQ'),
            ('Corner3Accuracy', 'C3_ACC'),
            ('Corner3Frequency', 'C3_FREQ'),
            ('Arc3Accuracy', 'ATB3_ACC'),
            ('Arc3Frequency', 'ATB3_FREQ'),
        ]
        
        for orig_col, new_col in zone_cols:
            if orig_col in shooting_zones.columns:
                zone_data = shooting_zones[['PLAYER_ID', orig_col]].copy()
                zone_data = zone_data.rename(columns={orig_col: new_col})
                features = features.merge(
                    zone_data,
                    on='PLAYER_ID',
                    how='left',
                    suffixes=('', '_dup')
                )
    
    # -------------------------------------------------------------------------
    # Clean up and define feature columns
    # -------------------------------------------------------------------------
    
    # Remove any duplicate columns
    features = features.loc[:, ~features.columns.str.endswith('_dup')]
    
    # Fill NaN values with 0 for numeric columns
    numeric_cols = features.select_dtypes(include=[np.number]).columns
    features[numeric_cols] = features[numeric_cols].fillna(0)
    
    # Define which columns to use for similarity calculation
    feature_columns = [
        # Basic stats (weighted heavily)
        'PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'MIN',
        # Shooting volume
        'FGM', 'FGA', 'FG3M', 'FG3A', 'FTM', 'FTA',
        # Shooting efficiency
        'FG_PCT', 'FG3_PCT', 'FT_PCT',
        # Shooting profile
        'FG3A_RATE', 'FTA_RATE',
    ]
    
    # Add optional columns if they exist
    optional_cols = [
        # Misc stats
        'PTS_PAINT', 'PTS_FB', 'PTS_2ND_CHANCE', 'PAINT_PTS_RATE',
        # Drives
        'DRIVES', 'DRIVE_FG_PCT', 'DRIVE_PTS', 'DRIVE_AST',
        # Advanced
        'USG_PCT',
        # Zone shooting
        'RIM_ACC', 'RIM_FREQ', 'SMR_ACC', 'SMR_FREQ',
        'LMR_ACC', 'LMR_FREQ', 'C3_ACC', 'C3_FREQ',
        'ATB3_ACC', 'ATB3_FREQ',
    ]
    
    for col in optional_cols:
        if col in features.columns:
            feature_columns.append(col)
    
    # Filter to only columns that exist
    feature_columns = [col for col in feature_columns if col in features.columns]
    
    return features, feature_columns


# =============================================================================
# SIMILARITY CALCULATION
# =============================================================================

def calculate_similarity_matrix(
    features_df: pd.DataFrame,
    feature_columns: List[str],
    position_filter: bool = False,
    minutes_tier_filter: bool = True
) -> pd.DataFrame:
    """
    Calculate pairwise similarity between all players.
    
    Args:
        features_df: DataFrame with player features
        feature_columns: List of columns to use for similarity
        position_filter: If True, only compare within same position group
        minutes_tier_filter: If True, weight by minutes similarity
    
    Returns:
        DataFrame with similarity scores (player pairs)
    """
    if features_df.empty or not feature_columns:
        return pd.DataFrame()
    
    # Extract feature matrix
    X = features_df[feature_columns].values
    
    # Standardize features (z-score normalization)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Calculate cosine similarity
    similarity_matrix = cosine_similarity(X_scaled)
    
    # Convert to DataFrame
    player_ids = features_df['PLAYER_ID'].values
    similarity_df = pd.DataFrame(
        similarity_matrix,
        index=player_ids,
        columns=player_ids
    )
    
    return similarity_df


@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_similarity_matrix(season: str = CURRENT_SEASON) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Cache the similarity matrix calculation.
    Returns both the features_df and similarity_df to avoid recalculating.
    """
    features_df, feature_columns = build_similarity_features(season)
    if features_df.empty:
        return pd.DataFrame(), pd.DataFrame()
    
    similarity_df = calculate_similarity_matrix(features_df, feature_columns)
    return features_df, similarity_df


@st.cache_data(ttl=3600, show_spinner=False)
def get_similar_players(
    player_id: int,
    n: int = 5,
    season: str = CURRENT_SEASON,
    min_similarity: float = 0.0,
    exclude_same_team: bool = False
) -> List[Dict]:
    """
    Get the N most similar players to a given player.
    
    Args:
        player_id: NBA API player ID
        n: Number of similar players to return
        season: NBA season
        min_similarity: Minimum similarity threshold
        exclude_same_team: If True, exclude teammates
    
    Returns:
        List of dicts with player info and similarity scores
    """
    # Use cached similarity matrix (much faster for batch operations)
    features_df, similarity_df = get_cached_similarity_matrix(season)
    
    if features_df.empty or similarity_df.empty or player_id not in features_df['PLAYER_ID'].values:
        return []
    
    if player_id not in similarity_df.index:
        return []
    
    # Get player's row
    player_similarities = similarity_df.loc[player_id]
    
    # Get player's team for exclusion
    player_row = features_df[features_df['PLAYER_ID'] == player_id].iloc[0]
    player_team = player_row['TEAM_ABBREVIATION']
    
    # Build results
    # Convert min_similarity from percentage (0-100) to decimal (0-1)
    min_similarity_decimal = min_similarity / 100.0
    
    results = []
    for other_id, similarity in player_similarities.items():
        if other_id == player_id:
            continue  # Skip self
        
        if similarity < min_similarity_decimal:
            continue
        
        other_row = features_df[features_df['PLAYER_ID'] == other_id]
        if len(other_row) == 0:
            continue
        
        other_row = other_row.iloc[0]
        
        # Optionally exclude teammates
        if exclude_same_team and other_row['TEAM_ABBREVIATION'] == player_team:
            continue
        
        # Get team name (use full name if available, otherwise use abbreviation)
        team_abbr = other_row['TEAM_ABBREVIATION']
        team_name = other_row.get('TEAM_NAME', team_abbr) if 'TEAM_NAME' in other_row else team_abbr
        
        results.append({
            'player_id': int(other_id),
            'player_name': other_row['PLAYER_NAME'],
            'team_abbr': team_abbr,
            'team_name': team_name,
            'similarity': round(similarity * 100, 1),  # Convert to percentage
            'ppg': round(other_row.get('PTS', 0), 1),
            'rpg': round(other_row.get('REB', 0), 1),
            'apg': round(other_row.get('AST', 0), 1),
            'mpg': round(other_row.get('MIN', 0), 1),
            # Handle NaN values for shooting percentages
            'fg_pct': round(other_row['FG_PCT'] * 100, 1) if pd.notna(other_row.get('FG_PCT')) else 0.0,
            'fg3_pct': round(other_row['FG3_PCT'] * 100, 1) if pd.notna(other_row.get('FG3_PCT')) else 0.0,
            'ft_pct': round(other_row['FT_PCT'] * 100, 1) if pd.notna(other_row.get('FT_PCT')) else 0.0,
        })
    
    # Sort by similarity and return top N
    results.sort(key=lambda x: x['similarity'], reverse=True)
    return results[:n]


def get_similarity_breakdown(
    player_id: int,
    compare_player_id: int,
    season: str = CURRENT_SEASON
) -> Dict:
    """
    Get detailed breakdown of similarity between two players.
    Shows which stats are most similar/different.
    
    Returns:
        Dict with category-level similarity scores and key differences
    """
    features_df, feature_columns = build_similarity_features(season)
    
    if features_df.empty:
        return {}
    
    player_row = features_df[features_df['PLAYER_ID'] == player_id]
    compare_row = features_df[features_df['PLAYER_ID'] == compare_player_id]
    
    if len(player_row) == 0 or len(compare_row) == 0:
        return {}
    
    player_row = player_row.iloc[0]
    compare_row = compare_row.iloc[0]
    
    # Calculate per-stat differences
    differences = {}
    for col in feature_columns:
        if col in player_row and col in compare_row:
            player_val = player_row[col]
            compare_val = compare_row[col]
            
            # Handle zero division
            if player_val != 0:
                pct_diff = abs(compare_val - player_val) / abs(player_val) * 100
            else:
                pct_diff = 100 if compare_val != 0 else 0
            
            differences[col] = {
                'player_value': round(player_val, 2),
                'compare_value': round(compare_val, 2),
                'abs_diff': round(abs(compare_val - player_val), 2),
                'pct_diff': round(pct_diff, 1)
            }
    
    # Group by category
    categories = {
        'Scoring': ['PTS', 'FGM', 'FG_PCT', 'FG3M', 'FG3_PCT', 'FTM', 'FT_PCT'],
        'Playmaking': ['AST', 'TOV', 'DRIVE_AST'],
        'Rebounding': ['REB'],
        'Defense': ['STL', 'BLK'],
        'Shot Profile': ['FG3A_RATE', 'FTA_RATE', 'RIM_FREQ', 'C3_FREQ', 'ATB3_FREQ'],
        'Paint Scoring': ['PTS_PAINT', 'PAINT_PTS_RATE', 'DRIVES', 'DRIVE_PTS'],
    }
    
    category_similarities = {}
    for cat_name, cols in categories.items():
        cat_diffs = [differences[c]['pct_diff'] for c in cols if c in differences]
        if cat_diffs:
            # Lower avg difference = higher similarity
            avg_diff = np.mean(cat_diffs)
            similarity = max(0, 100 - avg_diff)
            category_similarities[cat_name] = round(similarity, 1)
    
    # Find biggest similarities and differences
    sorted_diffs = sorted(differences.items(), key=lambda x: x[1]['pct_diff'])
    
    return {
        'overall_similarity': get_similar_players(player_id, n=100, season=season),  # Will filter for this player
        'category_similarities': category_similarities,
        'most_similar_stats': sorted_diffs[:5],  # Top 5 most similar
        'biggest_differences': sorted_diffs[-5:][::-1],  # Top 5 biggest differences
        'all_differences': differences
    }


# =============================================================================
# PREDICTION INTEGRATION - Similar Players vs Defense
# =============================================================================

def get_similar_players_vs_opponent(
    player_id: int,
    opponent_team_id: int,
    game_logs_df: pd.DataFrame,
    opponent_abbr: str = None,
    season: str = CURRENT_SEASON,
    n_similar: int = 10,
    min_games_vs_opponent: int = 1
) -> Dict:
    """
    Get how similar players performed against a specific opponent.
    Used to adjust predictions based on similar player performance.
    
    Args:
        player_id: Target player ID
        opponent_team_id: Opponent team ID
        game_logs_df: DataFrame with all player game logs
        season: NBA season
        n_similar: Number of similar players to consider
        min_games_vs_opponent: Minimum games vs opponent to include
    
    Returns:
        Dict with weighted performance data and adjustment factors
    """
    # Get similar players
    similar_players = get_similar_players(
        player_id, 
        n=n_similar, 
        season=season,
        min_similarity=50.0,  # At least 50% similar
        exclude_same_team=True  # Don't include teammates
    )
    
    if not similar_players:
        return {
            'pts_adjustment_factor': 1.0,
            'reb_adjustment_factor': 1.0,
            'ast_adjustment_factor': 1.0,
            'confidence': 'low',
            'sample_size': 0,
            'similar_player_data': []
        }
    
    # Get opponent abbreviation if not provided (need to look up from team_id)
    if opponent_abbr is None:
        # Try to get from game_logs_df if available
        opponent_rows = game_logs_df[game_logs_df['TEAM_ID'] == opponent_team_id]
        if len(opponent_rows) > 0 and 'MATCHUP' in opponent_rows.columns:
            # Extract from MATCHUP field
            matchup_str = opponent_rows['MATCHUP'].iloc[0]
            # MATCHUP format: "MIN vs. LAL" or "MIN @ LAL"
            if 'vs.' in matchup_str:
                parts = matchup_str.split('vs.')
                opponent_abbr = parts[1].strip() if len(parts) > 1 else None
            elif '@' in matchup_str:
                parts = matchup_str.split('@')
                opponent_abbr = parts[1].strip() if len(parts) > 1 else None
    
    if opponent_abbr is None:
        return {
            'pts_adjustment_factor': 1.0,
            'reb_adjustment_factor': 1.0,
            'ast_adjustment_factor': 1.0,
            'confidence': 'low',
            'sample_size': 0,
            'similar_player_data': []
        }
    
    results = []
    total_weight = 0
    weighted_pts_diff = 0
    weighted_reb_diff = 0
    weighted_ast_diff = 0
    
    for sim_player in similar_players:
        sim_id = sim_player['player_id']
        similarity = sim_player['similarity'] / 100  # Convert back to 0-1
        sim_team_abbr = sim_player.get('team_abbr', '')
        
        # Exclude similar players who play for the opponent team
        if sim_team_abbr.upper() == opponent_abbr.upper():
            continue
        
        # Get this player's games vs opponent
        # MATCHUP format: "MIN vs. LAL" or "MIN @ LAL"
        sim_player_all_games = game_logs_df[game_logs_df['PLAYER_ID'] == sim_id]
        
        # Filter for games vs specific opponent
        sim_player_games = sim_player_all_games[
            sim_player_all_games['MATCHUP'].str.contains(opponent_abbr, na=False, case=False)
        ]
        
        if len(sim_player_games) < min_games_vs_opponent:
            continue
        
        # Get season averages
        season_pts = sim_player['ppg']
        season_reb = sim_player['rpg']
        season_ast = sim_player['apg']
        season_min = sim_player.get('mpg', 0)  # Get minutes per game
        
        # Get performance vs opponent
        games_pts = sim_player_games['PTS'].astype(float).mean() if len(sim_player_games) > 0 and 'PTS' in sim_player_games.columns else season_pts
        games_reb = sim_player_games['REB'].astype(float).mean() if len(sim_player_games) > 0 and 'REB' in sim_player_games.columns else season_reb
        games_ast = sim_player_games['AST'].astype(float).mean() if len(sim_player_games) > 0 and 'AST' in sim_player_games.columns else season_ast
        games_min = sim_player_games['MIN'].astype(float).mean() if len(sim_player_games) > 0 and 'MIN' in sim_player_games.columns else season_min
        
        # Skip or heavily downweight low-minute players (< 10 MPG season avg)
        # They often have high per-minute rates but low total production, which skews adjustments
        minutes_weight = 1.0
        if season_min < 10:
            # Heavily downweight players averaging < 10 MPG
            minutes_weight = 0.2
        elif season_min < 15:
            # Moderate downweight for 10-15 MPG players
            minutes_weight = 0.5
        elif season_min < 20:
            # Slight downweight for 15-20 MPG players
            minutes_weight = 0.75
        
        # Calculate differentials (vs opponent compared to season avg)
        if season_pts > 0:
            pts_diff = (games_pts - season_pts) / season_pts
        else:
            pts_diff = 0
        
        if season_reb > 0:
            reb_diff = (games_reb - season_reb) / season_reb
        else:
            reb_diff = 0
        
        if season_ast > 0:
            ast_diff = (games_ast - season_ast) / season_ast
        else:
            ast_diff = 0
        
        # Weight by similarity, sample size, AND minutes played
        # Low-minute players get much less weight
        weight = similarity * len(sim_player_games) * minutes_weight
        total_weight += weight
        weighted_pts_diff += pts_diff * weight
        weighted_reb_diff += reb_diff * weight
        weighted_ast_diff += ast_diff * weight
        
        results.append({
            'player_name': sim_player['player_name'],
            'similarity': sim_player['similarity'],
            'games_vs_opp': len(sim_player_games),
            'pts_vs_opp': round(games_pts, 1),
            'season_pts': season_pts,
            'pts_diff': round(pts_diff * 100, 1),
            'season_min': season_min,  # Store for confidence calculation
        })
    
    # Calculate final adjustments
    if total_weight > 0:
        avg_pts_diff = weighted_pts_diff / total_weight
        avg_reb_diff = weighted_reb_diff / total_weight
        avg_ast_diff = weighted_ast_diff / total_weight
    else:
        avg_pts_diff = 0
        avg_reb_diff = 0
        avg_ast_diff = 0
    
    # Cap extreme adjustments to prevent unrealistic predictions
    # Limit to ±30% adjustment (prevents outliers from dominating)
    avg_pts_diff = max(-0.30, min(0.30, avg_pts_diff))
    avg_reb_diff = max(-0.30, min(0.30, avg_reb_diff))
    avg_ast_diff = max(-0.30, min(0.30, avg_ast_diff))
    
    # Determine confidence
    # Lower confidence if most similar players are low-minute players
    avg_minutes = np.mean([r.get('season_min', 0) for r in results]) if results else 0
    if len(results) >= 5 and total_weight > 3 and avg_minutes >= 15:
        confidence = 'high'
    elif len(results) >= 3 and avg_minutes >= 10:
        confidence = 'medium'
    else:
        confidence = 'low'
    
    return {
        'pts_adjustment_factor': 1.0 + avg_pts_diff,
        'reb_adjustment_factor': 1.0 + avg_reb_diff,
        'ast_adjustment_factor': 1.0 + avg_ast_diff,
        'confidence': confidence,
        'sample_size': len(results),
        'total_games_analyzed': sum(r['games_vs_opp'] for r in results),
        'similar_player_data': results
    }


# =============================================================================
# DISPLAY HELPERS
# =============================================================================

def format_similar_players_for_display(similar_players: List[Dict]) -> pd.DataFrame:
    """
    Format similar players list for Streamlit display.
    """
    if not similar_players:
        return pd.DataFrame()
    
    display_data = []
    for i, player in enumerate(similar_players, 1):
        display_data.append({
            'Rank': i,
            'Player': player['player_name'],
            'Team': player['team'],
            'Similarity': f"{player['similarity']}%",
            'PPG': player['ppg'],
            'RPG': player['rpg'],
            'APG': player['apg'],
            'MPG': player['mpg'],
        })
    
    return pd.DataFrame(display_data)


def get_similarity_traits(
    player_id: int,
    similar_player_id: int,
    features_df: pd.DataFrame,
    feature_columns: List[str]
) -> List[str]:
    """
    Get human-readable traits that make two players similar.
    """
    if features_df.empty:
        return []
    
    player_row = features_df[features_df['PLAYER_ID'] == player_id]
    sim_row = features_df[features_df['PLAYER_ID'] == similar_player_id]
    
    if len(player_row) == 0 or len(sim_row) == 0:
        return []
    
    player_row = player_row.iloc[0]
    sim_row = sim_row.iloc[0]
    
    traits = []
    
    # Check scoring similarity
    pts_diff = abs(player_row.get('PTS', 0) - sim_row.get('PTS', 0))
    if pts_diff < 3:
        traits.append("Similar scoring volume")
    
    # Check 3PT rate similarity
    fg3_rate_diff = abs(player_row.get('FG3A_RATE', 0) - sim_row.get('FG3A_RATE', 0))
    if fg3_rate_diff < 0.1:
        traits.append("Similar 3PT shooting profile")
    
    # Check paint scoring
    paint_diff = abs(player_row.get('PTS_PAINT', 0) - sim_row.get('PTS_PAINT', 0))
    if paint_diff < 3:
        traits.append("Similar paint scoring")
    
    # Check playmaking
    ast_diff = abs(player_row.get('AST', 0) - sim_row.get('AST', 0))
    if ast_diff < 2:
        traits.append("Similar playmaking")
    
    # Check rim finishing
    rim_acc_diff = abs(player_row.get('RIM_ACC', 0) - sim_row.get('RIM_ACC', 0))
    if rim_acc_diff < 0.05:
        traits.append("Similar rim finishing")
    
    # Check drives
    drives_diff = abs(player_row.get('DRIVES', 0) - sim_row.get('DRIVES', 0))
    if drives_diff < 2:
        traits.append("Similar driving style")
    
    return traits[:3]  # Return top 3 traits

