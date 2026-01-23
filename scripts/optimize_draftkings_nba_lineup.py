#!/usr/bin/env python3
"""
NBA DraftKings Lineup Optimizer
Optimizes NBA DraftKings lineups using FPTS predictions and salary constraints.
"""

import pandas as pd
import numpy as np
from pulp import LpMaximize, LpProblem, LpVariable, lpSum
import os
import sys
import argparse
from datetime import datetime
from typing import Optional, Tuple, List, Dict

# Try to import fuzzywuzzy, but make it optional
try:
    from fuzzywuzzy import fuzz
    FUZZYWUZZY_AVAILABLE = True
except ImportError:
    FUZZYWUZZY_AVAILABLE = False
    print("Warning: fuzzywuzzy not installed. Fuzzy name matching will be disabled.")
    print("Install with: pip install fuzzywuzzy python-Levenshtein")


def normalize_player_name(name: str) -> str:
    """
    Normalize player name for matching.
    
    Args:
        name: Player name string
        
    Returns:
        Normalized name (lowercase, stripped, handles suffixes)
    """
    if pd.isna(name) or name == '':
        return ''
    
    name = str(name).strip()
    # Convert to lowercase
    name = name.lower()
    # Remove common suffixes (Jr., Sr., III, etc.) for better matching
    suffixes = [' jr.', ' sr.', ' ii', ' iii', ' iv', ' jr', ' sr']
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)].strip()
    
    return name


def load_draftables(csv_path: str) -> pd.DataFrame:
    """
    Load DraftKings draftables CSV.
    
    Args:
        csv_path: Path to draftables CSV file
        
    Returns:
        DataFrame with columns: displayName, salary, position
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Draftables CSV not found: {csv_path}")
    
    df = pd.read_csv(csv_path)
    
    # Check for required columns
    required_cols = ['displayName', 'salary', 'position']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns in draftables CSV: {missing_cols}")
    
    # Normalize displayName
    df['displayName_normalized'] = df['displayName'].apply(normalize_player_name)
    
    # Ensure salary is numeric
    df['salary'] = pd.to_numeric(df['salary'], errors='coerce')
    
    # Remove rows with missing critical data
    df = df[df['displayName'].notna() & (df['displayName'] != '')]
    df = df[df['salary'].notna() & (df['salary'] > 0)]
    df = df[df['position'].notna() & (df['position'] != '')]
    
    print(f"Loaded {len(df)} draftable players from {csv_path}")
    return df


def load_predictions(csv_path: str) -> pd.DataFrame:
    """
    Load predictions CSV from Predictions page export.
    
    Args:
        csv_path: Path to predictions CSV file
        
    Returns:
        DataFrame with columns: Player, FPTS, Team (and others)
    """
    if not os.path.exists(csv_path):
        error_msg = f"Predictions CSV not found: {csv_path}\n\n"
        error_msg += "To get the predictions CSV:\n"
        error_msg += "1. Go to the Predictions page in your Streamlit app\n"
        error_msg += "2. Select a game/matchup and generate predictions\n"
        error_msg += "3. Scroll down to 'All Predicted Statlines' section\n"
        error_msg += "4. Click the '📥 Download Predicted Statlines CSV' button\n"
        error_msg += "5. Save the file and use its path with --predictions argument\n\n"
        error_msg += "The CSV should contain columns: Player, Team, FPTS (and other stats)"
        raise FileNotFoundError(error_msg)
    
    df = pd.read_csv(csv_path)
    
    # Check for required columns
    if 'Player' not in df.columns:
        available_cols = ', '.join(df.columns.tolist())
        raise ValueError(
            f"Missing 'Player' column in predictions CSV.\n"
            f"Available columns: {available_cols}\n"
            f"Please export from Predictions page using 'Download Predicted Statlines CSV' button."
        )
    if 'FPTS' not in df.columns:
        available_cols = ', '.join(df.columns.tolist())
        raise ValueError(
            f"Missing 'FPTS' column in predictions CSV.\n"
            f"Available columns: {available_cols}\n"
            f"Please export from Predictions page using 'Download Predicted Statlines CSV' button."
        )
    
    # Normalize Player name
    df['Player_normalized'] = df['Player'].apply(normalize_player_name)
    
    # Ensure FPTS is numeric
    df['FPTS'] = pd.to_numeric(df['FPTS'], errors='coerce')
    
    # Remove rows with missing critical data
    df = df[df['Player'].notna() & (df['Player'] != '')]
    df = df[df['FPTS'].notna()]
    
    print(f"Loaded {len(df)} player predictions from {csv_path}")
    return df


def match_players_fuzzy(draftables_df: pd.DataFrame, predictions_df: pd.DataFrame, 
                        threshold: int = 85) -> dict:
    """
    Match players using fuzzy matching.
    
    Args:
        draftables_df: DataFrame with draftables (must have displayName_normalized)
        predictions_df: DataFrame with predictions (must have Player_normalized)
        threshold: Minimum similarity score (0-100) for a match
        
    Returns:
        Dictionary mapping draftable index to prediction index
    """
    if not FUZZYWUZZY_AVAILABLE:
        return {}
    
    matches = {}
    draftables_names = draftables_df['displayName_normalized'].tolist()
    predictions_names = predictions_df['Player_normalized'].tolist()
    
    for draft_idx, draft_name in enumerate(draftables_names):
        if not draft_name:
            continue
        
        best_match_idx = None
        best_score = 0
        
        for pred_idx, pred_name in enumerate(predictions_names):
            if not pred_name:
                continue
            
            # Use ratio for overall similarity
            score = fuzz.ratio(draft_name, pred_name)
            if score > best_score:
                best_score = score
                best_match_idx = pred_idx
        
        if best_score >= threshold:
            matches[draft_idx] = best_match_idx
    
    return matches


def merge_draftables_with_predictions(draftables_df: pd.DataFrame, 
                                     predictions_df: pd.DataFrame) -> pd.DataFrame:
    """
    Merge draftables and predictions data.
    
    Args:
        draftables_df: DataFrame with draftables
        predictions_df: DataFrame with predictions
        
    Returns:
        Merged DataFrame with matched players
    """
    merged_data = []
    matched_draft_indices = set()
    matched_pred_indices = set()
    
    # First pass: exact name matching
    for draft_idx, draft_row in draftables_df.iterrows():
        draft_name_norm = draft_row['displayName_normalized']
        
        # Try exact match first
        exact_matches = predictions_df[
            predictions_df['Player_normalized'] == draft_name_norm
        ]
        
        if len(exact_matches) > 0:
            pred_row = exact_matches.iloc[0]
            merged_dict = {
                'Player': draft_row['displayName'],
                'displayName': draft_row['displayName'],
                'salary': draft_row['salary'],
                'position': draft_row['position'],
                'FPTS': pred_row['FPTS'],
                'Team': pred_row.get('Team', ''),
                'match_type': 'exact'
            }
            # Add tip time and opponent if available
            if 'Tip_Time' in pred_row:
                merged_dict['Tip_Time'] = pred_row['Tip_Time']
            if 'Opponent' in pred_row:
                merged_dict['Opponent'] = pred_row['Opponent']
            elif 'Opponent_Team' in pred_row:
                merged_dict['Opponent'] = pred_row['Opponent_Team']
            merged_data.append(merged_dict)
            matched_draft_indices.add(draft_idx)
            matched_pred_indices.add(pred_row.name)
    
    # Second pass: fuzzy matching for unmatched players
    if FUZZYWUZZY_AVAILABLE:
        unmatched_draft = draftables_df[~draftables_df.index.isin(matched_draft_indices)].copy()
        unmatched_pred = predictions_df[~predictions_df.index.isin(matched_pred_indices)].copy()
        
        if len(unmatched_draft) > 0 and len(unmatched_pred) > 0:
            # Ensure normalized columns exist
            if 'displayName_normalized' not in unmatched_draft.columns:
                unmatched_draft['displayName_normalized'] = unmatched_draft['displayName'].apply(normalize_player_name)
            if 'Player_normalized' not in unmatched_pred.columns:
                unmatched_pred['Player_normalized'] = unmatched_pred['Player'].apply(normalize_player_name)
            
            # Reset index to ensure positional indices match enumerate() results
            unmatched_draft_reset = unmatched_draft.reset_index(drop=True)
            unmatched_pred_reset = unmatched_pred.reset_index(drop=True)
            
            fuzzy_matches = match_players_fuzzy(unmatched_draft_reset, unmatched_pred_reset, threshold=85)
            
            # Get actual indices from original filtered dataframes (before reset)
            draft_actual_indices = unmatched_draft.index.tolist()
            pred_actual_indices = unmatched_pred.index.tolist()
            
            for draft_pos_idx, pred_pos_idx in fuzzy_matches.items():
                # Map positional indices back to actual dataframe indices
                if draft_pos_idx < len(draft_actual_indices) and pred_pos_idx < len(pred_actual_indices):
                    draft_idx = draft_actual_indices[draft_pos_idx]
                    pred_idx = pred_actual_indices[pred_pos_idx]
                    
                    draft_row = draftables_df.loc[draft_idx]
                    pred_row = predictions_df.loc[pred_idx]
                    
                    merged_dict = {
                        'Player': draft_row['displayName'],
                        'displayName': draft_row['displayName'],
                        'salary': draft_row['salary'],
                        'position': draft_row['position'],
                        'FPTS': pred_row['FPTS'],
                        'Team': pred_row.get('Team', ''),
                        'match_type': 'fuzzy'
                    }
                    # Add tip time and opponent if available
                    if 'Tip_Time' in pred_row:
                        merged_dict['Tip_Time'] = pred_row['Tip_Time']
                    if 'Opponent' in pred_row:
                        merged_dict['Opponent'] = pred_row['Opponent']
                    elif 'Opponent_Team' in pred_row:
                        merged_dict['Opponent'] = pred_row['Opponent_Team']
                    merged_data.append(merged_dict)
                    matched_draft_indices.add(draft_idx)
                    matched_pred_indices.add(pred_idx)
    
    # Third pass: include draftables without predictions (set FPTS to 0)
    unmatched_draft = draftables_df[~draftables_df.index.isin(matched_draft_indices)]
    for draft_idx, draft_row in unmatched_draft.iterrows():
        merged_data.append({
            'Player': draft_row['displayName'],
            'displayName': draft_row['displayName'],
            'salary': draft_row['salary'],
            'position': draft_row['position'],
            'FPTS': 0.0,
            'Team': '',
            'match_type': 'no_prediction'
        })
    
    merged_df = pd.DataFrame(merged_data)
    
    # Print matching statistics
    exact_count = len(merged_df[merged_df['match_type'] == 'exact'])
    fuzzy_count = len(merged_df[merged_df['match_type'] == 'fuzzy'])
    no_pred_count = len(merged_df[merged_df['match_type'] == 'no_prediction'])
    
    print(f"\nMatching Statistics:")
    print(f"  Exact matches: {exact_count}")
    print(f"  Fuzzy matches: {fuzzy_count}")
    print(f"  No prediction: {no_pred_count}")
    print(f"  Total players: {len(merged_df)}")
    
    return merged_df


def add_position_flags(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add boolean flags for position eligibility.
    
    Args:
        df: DataFrame with 'position' column
        
    Returns:
        DataFrame with added position flag columns
    """
    df = df.copy()
    
    # Parse position string and add flags
    # Positions can be like "PG", "SG", "PG/SG", "SF/PF", "PF/C", "C"
    position_str = df['position'].astype(str).str.upper()
    
    df['is_pg'] = position_str.str.contains('PG', na=False)
    df['is_sg'] = position_str.str.contains('SG', na=False)
    df['is_sf'] = position_str.str.contains('SF', na=False)
    df['is_pf'] = position_str.str.contains('PF', na=False)
    df['is_c'] = position_str.str.contains('C', na=False) & ~position_str.str.contains('PF/C', na=False)
    # Handle PF/C separately - they can play C
    df['is_c'] = df['is_c'] | position_str.str.contains('PF/C', na=False)
    
    # G slot: can be PG or SG
    df['is_g'] = df['is_pg'] | df['is_sg']
    
    # F slot: can be SF or PF
    df['is_f'] = df['is_sf'] | df['is_pf']
    
    # UTIL slot: any position
    df['is_util'] = True
    
    return df


def optimize_lineup(df: pd.DataFrame, max_salary: int = 50000) -> pd.DataFrame:
    """
    Optimize lineup using PuLP.
    
    Args:
        df: DataFrame with Player, salary, FPTS, and position flags
        max_salary: Maximum total salary (default 50000)
        
    Returns:
        DataFrame with selected players
    """
    # Check for duplicate Player names
    if df['Player'].duplicated().any():
        print(f"Warning: Found {df['Player'].duplicated().sum()} duplicate player names. Keeping first occurrence.")
        df = df.drop_duplicates(subset=['Player'], keep='first').reset_index(drop=True)
    
    # Ensure index is unique
    df = df.reset_index(drop=True)
    
    # Set up the optimization problem
    prob = LpProblem("Optimize_NBA_Lineup", LpMaximize)
    
    # Define binary variables for each player (1 = selected, 0 = not selected)
    players = df["Player"].tolist()
    vars = LpVariable.dicts("Select", players, cat="Binary")
    
    # Create a lookup dictionary for faster access
    player_data = df.set_index('Player').to_dict('index')
    
    # Objective: maximize total FPTS
    prob += lpSum([vars[name] * player_data[name]["FPTS"] for name in players])
    
    # Constraint: select exactly 8 players
    prob += lpSum([vars[name] for name in players]) == 8
    
    # Constraint: total salary <= max_salary
    prob += lpSum([vars[name] * player_data[name]["salary"] for name in players]) <= max_salary
    
    # Position constraints: at least 1 of each required position
    prob += lpSum([vars[name] for name in players if player_data[name]["is_pg"]]) >= 1  # At least 1 PG
    prob += lpSum([vars[name] for name in players if player_data[name]["is_sg"]]) >= 1  # At least 1 SG
    prob += lpSum([vars[name] for name in players if player_data[name]["is_sf"]]) >= 1  # At least 1 SF
    prob += lpSum([vars[name] for name in players if player_data[name]["is_pf"]]) >= 1  # At least 1 PF
    prob += lpSum([vars[name] for name in players if player_data[name]["is_c"]]) >= 1   # At least 1 C
    
    # Critical: Need at least 3 players who can play G (PG or SG) because we need:
    # - 1 for PG slot
    # - 1 for SG slot  
    # - 1 for G slot
    prob += lpSum([vars[name] for name in players if player_data[name]["is_g"]]) >= 3  # At least 3 G-eligible (for PG, SG, and G slots)
    
    # Critical: Need at least 3 players who can play F (SF or PF) because we need:
    # - 1 for SF slot
    # - 1 for PF slot
    # - 1 for F slot
    prob += lpSum([vars[name] for name in players if player_data[name]["is_f"]]) >= 3  # At least 3 F-eligible (for SF, PF, and F slots)
    
    # UTIL can be any position, so at least 1 is already guaranteed by the 8-player constraint
    # But we explicitly require at least 1 UTIL-eligible (any position)
    prob += lpSum([vars[name] for name in players if player_data[name]["is_util"]]) >= 1  # At least 1 UTIL (any)
    
    # Solve the problem
    print("\nSolving optimization problem...")
    prob.solve()
    
    # Check solution status
    if prob.status != 1:  # 1 = Optimal
        if prob.status == -1:
            raise ValueError("Optimization failed: No feasible solution found. Check position constraints and salary cap.")
        elif prob.status == 0:
            raise ValueError("Optimization failed: Solution not found. Problem may be infeasible.")
        else:
            raise ValueError(f"Optimization failed with status: {prob.status}")
    
    # Create a list to store selected players
    selected_players = []
    
    # Get the selected players and their data
    for name in players:
        if vars[name].value() == 1:
            player_info = player_data[name]
            selected_players.append({
                'Player': name,
                'Position': player_info['position'],
                'Salary': player_info['salary'],
                'FPTS': player_info['FPTS'],
                'Team': player_info.get('Team', '')
            })
    
    # Create dataframe from selected players
    selected_df = pd.DataFrame(selected_players)
    
    if len(selected_df) == 0:
        raise ValueError("No players selected. Optimization may have failed.")
    
    # Rename 'Position' to 'position' for add_position_flags function
    selected_df = selected_df.rename(columns={'Position': 'position'})
    
    # Add position flags back to selected_df for slot assignment
    selected_df = add_position_flags(selected_df)
    
    # Assign position slots to each player
    selected_df = assign_position_slots(selected_df)
    
    # Rename 'position' back to 'Position' for consistency
    selected_df = selected_df.rename(columns={'position': 'Position'})
    
    # Sort by slot order: PG, SG, SF, PF, C, G, F, UTIL
    slot_order = {'PG': 1, 'SG': 2, 'SF': 3, 'PF': 4, 'C': 5, 'G': 6, 'F': 7, 'UTIL': 8}
    selected_df['slot_order'] = selected_df['Slot'].map(slot_order)
    # Sort by slot order first, then by salary (descending) within each slot
    selected_df = selected_df.sort_values(['slot_order', 'Salary'], ascending=[True, False]).reset_index(drop=True)
    selected_df = selected_df.drop('slot_order', axis=1)
    
    return selected_df


def optimize_multiple_lineups(df: pd.DataFrame, max_salary: int = 50000, num_lineups: int = 5, 
                              max_overlap: int = 3) -> List[pd.DataFrame]:
    """
    Generate multiple unique lineups with different optimization strategies.
    
    Args:
        df: DataFrame with Player, salary, FPTS, and position flags
        max_salary: Maximum total salary (default 50000)
        num_lineups: Number of lineups to generate (default 5)
        max_overlap: Maximum number of overlapping players between lineups (default 3)
        
    Returns:
        List of DataFrames, each containing an optimized lineup
    """
    lineups = []
    selected_players_sets = []  # Track selected players to ensure uniqueness
    player_exposure_count = {}  # Track how many times each player has been selected across all lineups
    
    # Check for duplicate Player names
    if df['Player'].duplicated().any():
        df = df.drop_duplicates(subset=['Player'], keep='first').reset_index(drop=True)
    
    df = df.reset_index(drop=True)
    
    # Initialize exposure counts for all players
    for player_name in df['Player'].tolist():
        player_exposure_count[player_name] = 0
    
    # Check if ceiling/floor columns exist
    has_ceiling = 'FPTS_Ceiling' in df.columns or 'ceiling_FPTS' in df.columns or 'FPTS_Ceiling' in df.columns
    ceiling_col = None
    if 'FPTS_Ceiling' in df.columns:
        ceiling_col = 'FPTS_Ceiling'
    elif 'ceiling_FPTS' in df.columns:
        ceiling_col = 'ceiling_FPTS'
    
    # If no ceiling column, create default values based on FPTS
    if not has_ceiling and 'FPTS' in df.columns:
        df['FPTS_Ceiling'] = df['FPTS'] * 1.3
        df['FPTS_Floor'] = df['FPTS'] * 0.7
        ceiling_col = 'FPTS_Ceiling'
        has_ceiling = True
    
    # Strategy definitions
    strategies = [
        {
            'name': 'Max FPTS',
            'objective': 'fpts',
            'weight': 1.0
        },
        {
            'name': 'Max Value',
            'objective': 'value',
            'weight': 1.0
        },
        {
            'name': 'Max Ceiling',
            'objective': 'ceiling',
            'weight': 1.0,
            'requires_ceiling': True
        },
        {
            'name': 'Balanced',
            'objective': 'balanced',
            'weight': 1.0
        },
        {
            'name': 'Punt Strategy',
            'objective': 'punt',
            'weight': 1.0,
            'requires_ceiling': True
        }
    ]
    
    for strategy_idx, strategy in enumerate(strategies[:num_lineups]):
        # Skip ceiling-based strategies if ceiling data not available
        if strategy.get('requires_ceiling') and not has_ceiling:
            # Fall back to value strategy
            strategy = {'name': 'Max Value', 'objective': 'value', 'weight': 1.0}
        
        try:
            # Set up optimization problem
            prob = LpProblem(f"Optimize_NBA_Lineup_{strategy['name']}", LpMaximize)
            
            players = df["Player"].tolist()
            vars = LpVariable.dicts("Select", players, cat="Binary")
            player_data = df.set_index('Player').to_dict('index')
            
            # Objective function based on strategy
            if strategy['objective'] == 'fpts':
                # Maximize total FPTS
                prob += lpSum([vars[name] * player_data[name]["FPTS"] for name in players])
            elif strategy['objective'] == 'value':
                # Maximize FPTS per dollar (value)
                # Scale by 1000 to make numbers reasonable
                prob += lpSum([vars[name] * (player_data[name]["FPTS"] / max(player_data[name]["salary"], 1) * 1000) 
                              for name in players])
            elif strategy['objective'] == 'ceiling' and ceiling_col:
                # Maximize ceiling FPTS
                prob += lpSum([vars[name] * player_data[name].get(ceiling_col, player_data[name]["FPTS"]) 
                              for name in players])
            elif strategy['objective'] == 'balanced':
                # Weighted combination: 60% FPTS, 40% value
                prob += lpSum([vars[name] * (
                    0.6 * player_data[name]["FPTS"] + 
                    0.4 * (player_data[name]["FPTS"] / max(player_data[name]["salary"], 1) * 1000)
                ) for name in players])
            elif strategy['objective'] == 'punt' and ceiling_col:
                # Maximize ceiling with constraint on average salary
                prob += lpSum([vars[name] * player_data[name].get(ceiling_col, player_data[name]["FPTS"]) 
                              for name in players])
            else:
                # Default to FPTS
                prob += lpSum([vars[name] * player_data[name]["FPTS"] for name in players])
            
            # Standard constraints
            prob += lpSum([vars[name] for name in players]) == 8
            prob += lpSum([vars[name] * player_data[name]["salary"] for name in players]) <= max_salary
            
            # Position constraints
            prob += lpSum([vars[name] for name in players if player_data[name]["is_pg"]]) >= 1
            prob += lpSum([vars[name] for name in players if player_data[name]["is_sg"]]) >= 1
            prob += lpSum([vars[name] for name in players if player_data[name]["is_sf"]]) >= 1
            prob += lpSum([vars[name] for name in players if player_data[name]["is_pf"]]) >= 1
            prob += lpSum([vars[name] for name in players if player_data[name]["is_c"]]) >= 1
            prob += lpSum([vars[name] for name in players if player_data[name]["is_g"]]) >= 3
            prob += lpSum([vars[name] for name in players if player_data[name]["is_f"]]) >= 3
            prob += lpSum([vars[name] for name in players if player_data[name]["is_util"]]) >= 1
            
            # Punt strategy: enforce salary tier structure
            # 2-3 high salary stars (>= $8,000), 2-3 low salary role players (<= $6,000), 2-3 mid-tier (between $6,000 and $8,000)
            if strategy['objective'] == 'punt':
                # High salary players (stars) >= $8,000
                high_salary_players = [name for name in players if player_data[name]["salary"] >= 8000]
                prob += lpSum([vars[name] for name in high_salary_players]) >= 2
                prob += lpSum([vars[name] for name in high_salary_players]) <= 3
                
                # Low salary players (role players) <= $6,000
                low_salary_players = [name for name in players if player_data[name]["salary"] <= 6000]
                prob += lpSum([vars[name] for name in low_salary_players]) >= 2
                prob += lpSum([vars[name] for name in low_salary_players]) <= 3
                
                # Mid-tier players (between $6,000 and $8,000)
                mid_salary_players = [name for name in players if 6000 < player_data[name]["salary"] < 8000]
                prob += lpSum([vars[name] for name in mid_salary_players]) >= 2
                prob += lpSum([vars[name] for name in mid_salary_players]) <= 3
            
            # Uniqueness constraints: ensure this lineup differs from previous ones
            for prev_lineup_idx, prev_selected in enumerate(selected_players_sets):
                # Constraint: at most max_overlap players can overlap
                prob += lpSum([vars[name] for name in prev_selected]) <= max_overlap
            
            # Player exposure constraint: no player can appear in more than 3 lineups total
            max_exposure = 3
            for player_name in players:
                current_exposure = player_exposure_count.get(player_name, 0)
                if current_exposure >= max_exposure:
                    # Player has already reached max exposure, exclude from this lineup
                    prob += vars[player_name] == 0
            
            # Solve
            prob.solve()
            
            if prob.status != 1:
                # If infeasible, try without uniqueness constraints (but keep exposure constraints)
                if len(selected_players_sets) > 0:
                    # Remove uniqueness constraints and retry
                    prob = LpProblem(f"Optimize_NBA_Lineup_{strategy['name']}_retry", LpMaximize)
                    vars = LpVariable.dicts("Select", players, cat="Binary")
                    
                    if strategy['objective'] == 'fpts':
                        prob += lpSum([vars[name] * player_data[name]["FPTS"] for name in players])
                    elif strategy['objective'] == 'value':
                        prob += lpSum([vars[name] * (player_data[name]["FPTS"] / max(player_data[name]["salary"], 1) * 1000) 
                                      for name in players])
                    elif strategy['objective'] == 'ceiling' and ceiling_col:
                        prob += lpSum([vars[name] * player_data[name].get(ceiling_col, player_data[name]["FPTS"]) 
                                      for name in players])
                    elif strategy['objective'] == 'balanced':
                        prob += lpSum([vars[name] * (
                            0.6 * player_data[name]["FPTS"] + 
                            0.4 * (player_data[name]["FPTS"] / max(player_data[name]["salary"], 1) * 1000)
                        ) for name in players])
                    elif strategy['objective'] == 'punt' and ceiling_col:
                        prob += lpSum([vars[name] * player_data[name].get(ceiling_col, player_data[name]["FPTS"]) 
                                      for name in players])
                    
                    prob += lpSum([vars[name] for name in players]) == 8
                    prob += lpSum([vars[name] * player_data[name]["salary"] for name in players]) <= max_salary
                    prob += lpSum([vars[name] for name in players if player_data[name]["is_pg"]]) >= 1
                    prob += lpSum([vars[name] for name in players if player_data[name]["is_sg"]]) >= 1
                    prob += lpSum([vars[name] for name in players if player_data[name]["is_sf"]]) >= 1
                    prob += lpSum([vars[name] for name in players if player_data[name]["is_pf"]]) >= 1
                    prob += lpSum([vars[name] for name in players if player_data[name]["is_c"]]) >= 1
                    prob += lpSum([vars[name] for name in players if player_data[name]["is_g"]]) >= 3
                    prob += lpSum([vars[name] for name in players if player_data[name]["is_f"]]) >= 3
                    prob += lpSum([vars[name] for name in players if player_data[name]["is_util"]]) >= 1
                    
                    # Punt strategy: enforce salary tier structure
                    if strategy['objective'] == 'punt':
                        # High salary players (stars) >= $8,000
                        high_salary_players = [name for name in players if player_data[name]["salary"] >= 8000]
                        prob += lpSum([vars[name] for name in high_salary_players]) >= 2
                        prob += lpSum([vars[name] for name in high_salary_players]) <= 3
                        
                        # Low salary players (role players) <= $6,000
                        low_salary_players = [name for name in players if player_data[name]["salary"] <= 6000]
                        prob += lpSum([vars[name] for name in low_salary_players]) >= 2
                        prob += lpSum([vars[name] for name in low_salary_players]) <= 3
                        
                        # Mid-tier players (between $6,000 and $8,000)
                        mid_salary_players = [name for name in players if 6000 < player_data[name]["salary"] < 8000]
                        prob += lpSum([vars[name] for name in mid_salary_players]) >= 2
                        prob += lpSum([vars[name] for name in mid_salary_players]) <= 3
                    
                    # Player exposure constraint: no player can appear in more than 3 lineups total
                    max_exposure = 3
                    for player_name in players:
                        current_exposure = player_exposure_count.get(player_name, 0)
                        if current_exposure >= max_exposure:
                            # Player has already reached max exposure, exclude from this lineup
                            prob += vars[player_name] == 0
                    
                    prob.solve()
            
            if prob.status != 1:
                print(f"Warning: Strategy '{strategy['name']}' failed to find solution")
                continue
            
            # Extract selected players
            selected_players = []
            selected_player_set = set()
            for name in players:
                if vars[name].value() == 1:
                    player_info = player_data[name]
                    player_dict = {
                        'Player': name,
                        'Position': player_info['position'],
                        'Salary': player_info['salary'],
                        'FPTS': player_info['FPTS'],
                        'Team': player_info.get('Team', '')
                    }
                    # Add tip time and opponent if available
                    if 'Tip_Time' in player_info:
                        player_dict['Tip_Time'] = player_info['Tip_Time']
                    if 'Opponent' in player_info:
                        player_dict['Opponent'] = player_info['Opponent']
                    elif 'Opponent_Team' in player_info:
                        player_dict['Opponent'] = player_info['Opponent_Team']
                    selected_players.append(player_dict)
                    selected_player_set.add(name)
            
            if len(selected_players) == 0:
                continue
            
            selected_df = pd.DataFrame(selected_players)
            selected_df = selected_df.rename(columns={'Position': 'position'})
            selected_df = add_position_flags(selected_df)
            selected_df = assign_position_slots(selected_df)
            selected_df = selected_df.rename(columns={'position': 'Position'})
            
            # Sort by slot order
            slot_order = {'PG': 1, 'SG': 2, 'SF': 3, 'PF': 4, 'C': 5, 'G': 6, 'F': 7, 'UTIL': 8}
            selected_df['slot_order'] = selected_df['Slot'].map(slot_order)
            selected_df = selected_df.sort_values('slot_order', ascending=True).reset_index(drop=True)
            selected_df = selected_df.drop('slot_order', axis=1)
            
            lineups.append(selected_df)
            selected_players_sets.append(selected_player_set)
            
            # Update player exposure counts
            for player_name in selected_player_set:
                player_exposure_count[player_name] = player_exposure_count.get(player_name, 0) + 1
            
        except Exception as e:
            print(f"Error generating lineup with strategy '{strategy['name']}': {e}")
            import traceback
            traceback.print_exc()
            continue
    
    return lineups


def calculate_boom_score(row: pd.Series) -> float:
    """
    Calculate boom score for a player.
    Higher score = higher boom potential.
    
    Formula:
    boom_score = (
        (ceiling_FPTS - median_FPTS) * 0.4 +  # Ceiling upside
        (median_FPTS / salary * 1000) * 0.2 +  # Value component
        (variance_factor) * 0.2 +  # High variance = boom potential
        (matchup_factor) * 0.2     # Favorable matchup (simplified - assume neutral for now)
    )
    
    Args:
        row: Series with player data including FPTS, FPTS_Ceiling, FPTS_Floor, salary, etc.
        
    Returns:
        Boom score (higher = more boom potential)
    """
    median_fpts = row.get('FPTS', row.get('FPTS_Median', 0))
    ceiling_fpts = row.get('FPTS_Ceiling', median_fpts * 1.3)
    floor_fpts = row.get('FPTS_Floor', median_fpts * 0.7)
    salary = row.get('salary', row.get('Salary', 10000))
    variance = row.get('FPTS_Variance', 0.0)
    std_dev = row.get('FPTS_StdDev', 0.0)
    
    # Ceiling upside component
    ceiling_upside = max(ceiling_fpts - median_fpts, 0) * 0.4
    
    # Value component (FPTS per dollar)
    if salary > 0:
        value_component = (median_fpts / salary * 1000) * 0.2
    else:
        value_component = 0
    
    # Variance factor (higher variance = more boom potential)
    # Normalize variance (assume typical range 0-200)
    variance_factor = min(std_dev / 10.0, 2.0) * 0.2  # Cap at 2.0 for normalization
    
    # Matchup factor (simplified - assume neutral for now, could be enhanced)
    matchup_factor = 0.1  # Neutral baseline
    
    boom_score = ceiling_upside + value_component + variance_factor + matchup_factor
    
    return round(boom_score, 2)


def calculate_bust_score(row: pd.Series) -> float:
    """
    Calculate bust score for a player.
    Higher score = higher bust risk.
    
    Formula:
    bust_score = (
        (median_FPTS - floor_FPTS) * 0.3 +  # Floor downside
        (salary / median_FPTS) * 0.3 +       # Salary risk
        (consistency_factor) * 0.2 +         # Low variance = less bust risk (inverted)
        (matchup_factor) * 0.2                # Unfavorable matchup (simplified)
    )
    
    Args:
        row: Series with player data including FPTS, FPTS_Ceiling, FPTS_Floor, salary, etc.
        
    Returns:
        Bust score (higher = more bust risk)
    """
    median_fpts = row.get('FPTS', row.get('FPTS_Median', 0))
    ceiling_fpts = row.get('FPTS_Ceiling', median_fpts * 1.3)
    floor_fpts = row.get('FPTS_Floor', median_fpts * 0.7)
    salary = row.get('salary', row.get('Salary', 10000))
    variance = row.get('FPTS_Variance', 0.0)
    std_dev = row.get('FPTS_StdDev', 0.0)
    
    # Floor downside component
    floor_downside = max(median_fpts - floor_fpts, 0) * 0.3
    
    # Salary risk component (higher salary relative to FPTS = higher risk)
    if median_fpts > 0:
        salary_risk = (salary / median_fpts) * 0.3
    else:
        salary_risk = 10.0 * 0.3  # High risk if no FPTS
    
    # Consistency factor (low variance = less bust risk, so invert)
    # Lower std_dev = lower bust risk, so we subtract from max
    consistency_factor = max(0, (2.0 - min(std_dev / 10.0, 2.0))) * 0.2
    
    # Matchup factor (simplified - assume neutral for now)
    matchup_factor = 0.1  # Neutral baseline
    
    bust_score = floor_downside + salary_risk + consistency_factor + matchup_factor
    
    return round(bust_score, 2)


def calculate_boom_bust_probabilities(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate boom and bust scores/probabilities for all players.
    
    Args:
        df: DataFrame with player predictions including FPTS, FPTS_Ceiling, FPTS_Floor, salary
        
    Returns:
        DataFrame with added Boom_Score and Bust_Score columns
    """
    df = df.copy()
    
    # Calculate boom scores
    df['Boom_Score'] = df.apply(calculate_boom_score, axis=1)
    
    # Calculate bust scores
    df['Bust_Score'] = df.apply(calculate_bust_score, axis=1)
    
    # Calculate probabilities (normalize scores to 0-100 range)
    # For boom: higher score = higher probability
    max_boom = df['Boom_Score'].max() if len(df) > 0 else 1
    min_boom = df['Boom_Score'].min() if len(df) > 0 else 0
    boom_range = max_boom - min_boom if max_boom > min_boom else 1
    df['Boom_Probability'] = ((df['Boom_Score'] - min_boom) / boom_range * 100).round(1)
    
    # For bust: higher score = higher probability
    max_bust = df['Bust_Score'].max() if len(df) > 0 else 1
    min_bust = df['Bust_Score'].min() if len(df) > 0 else 0
    bust_range = max_bust - min_bust if max_bust > min_bust else 1
    df['Bust_Probability'] = ((df['Bust_Score'] - min_bust) / bust_range * 100).round(1)
    
    return df


def assign_position_slots(selected_df: pd.DataFrame) -> pd.DataFrame:
    """
    Assign each player to a specific DraftKings position slot.
    
    DraftKings NBA lineup requires exactly 8 players:
    - PG (at least 1)
    - SG (at least 1)
    - SF (at least 1)
    - PF (at least 1)
    - C (at least 1)
    - G (at least 1, can be PG or SG)
    - F (at least 1, can be SF or PF)
    - UTIL (at least 1, can be any position)
    
    Args:
        selected_df: DataFrame with selected players and position flags
        
    Returns:
        DataFrame with 'Slot' column added (exactly 8 slots filled)
    """
    df = selected_df.copy()
    
    if len(df) != 8:
        raise ValueError(f"Expected exactly 8 players, but got {len(df)}")
    
    df['Slot'] = None
    df['assigned'] = False
    
    # Identify players who can play multiple positions
    # For PG/SG: prefer assigning single-position players to PG/SG slots, save multi-position for G
    df['is_pg_only'] = df['is_pg'] & ~df['is_sg']
    df['is_sg_only'] = df['is_sg'] & ~df['is_pg']
    df['is_pg_sg'] = df['is_pg'] & df['is_sg']  # Can play both
    
    df['is_sf_only'] = df['is_sf'] & ~df['is_pf']
    df['is_pf_only'] = df['is_pf'] & ~df['is_sf']
    df['is_sf_pf'] = df['is_sf'] & df['is_pf']  # Can play both
    
    # Strategy: Fill PG and SG first, prioritizing single-position players
    # This leaves multi-position PG/SG players available for the G slot
    
    # Fill PG slot - prefer PG-only players, but can use PG/SG if needed
    eligible_pg = df[(df['is_pg'] == True) & (df['assigned'] == False)]
    if len(eligible_pg) > 0:
        # Prefer PG-only players first
        pg_only = eligible_pg[eligible_pg['is_pg_only'] == True]
        if len(pg_only) > 0:
            idx = pg_only.sort_values('FPTS', ascending=False).index[0]
        else:
            idx = eligible_pg.sort_values('FPTS', ascending=False).index[0]
        df.loc[idx, 'Slot'] = 'PG'
        df.loc[idx, 'assigned'] = True
    
    # Fill SG slot - prefer SG-only players, but can use PG/SG if needed
    eligible_sg = df[(df['is_sg'] == True) & (df['assigned'] == False)]
    if len(eligible_sg) > 0:
        # Prefer SG-only players first
        sg_only = eligible_sg[eligible_sg['is_sg_only'] == True]
        if len(sg_only) > 0:
            idx = sg_only.sort_values('FPTS', ascending=False).index[0]
        else:
            idx = eligible_sg.sort_values('FPTS', ascending=False).index[0]
        df.loc[idx, 'Slot'] = 'SG'
        df.loc[idx, 'assigned'] = True
    
    # Fill SF slot - prefer SF-only players
    eligible_sf = df[(df['is_sf'] == True) & (df['assigned'] == False)]
    if len(eligible_sf) > 0:
        sf_only = eligible_sf[eligible_sf['is_sf_only'] == True]
        if len(sf_only) > 0:
            idx = sf_only.sort_values('FPTS', ascending=False).index[0]
        else:
            idx = eligible_sf.sort_values('FPTS', ascending=False).index[0]
        df.loc[idx, 'Slot'] = 'SF'
        df.loc[idx, 'assigned'] = True
    
    # Fill PF slot - prefer PF-only players
    eligible_pf = df[(df['is_pf'] == True) & (df['assigned'] == False)]
    if len(eligible_pf) > 0:
        pf_only = eligible_pf[eligible_pf['is_pf_only'] == True]
        if len(pf_only) > 0:
            idx = pf_only.sort_values('FPTS', ascending=False).index[0]
        else:
            idx = eligible_pf.sort_values('FPTS', ascending=False).index[0]
        df.loc[idx, 'Slot'] = 'PF'
        df.loc[idx, 'assigned'] = True
    
    # Fill C slot
    eligible_c = df[(df['is_c'] == True) & (df['assigned'] == False)]
    if len(eligible_c) > 0:
        idx = eligible_c.sort_values('FPTS', ascending=False).index[0]
        df.loc[idx, 'Slot'] = 'C'
        df.loc[idx, 'assigned'] = True
    
    # Fill G slot (must be PG or SG) - should have at least one available
    eligible_g = df[(df['is_g'] == True) & (df['assigned'] == False)]
    if len(eligible_g) == 0:
        # This shouldn't happen if optimizer worked correctly, but handle it
        raise ValueError("No eligible player found for G slot. Optimizer may have selected invalid lineup.")
    idx = eligible_g.sort_values('FPTS', ascending=False).index[0]
    df.loc[idx, 'Slot'] = 'G'
    df.loc[idx, 'assigned'] = True
    
    # Fill F slot (must be SF or PF) - should have at least one available
    eligible_f = df[(df['is_f'] == True) & (df['assigned'] == False)]
    if len(eligible_f) == 0:
        raise ValueError("No eligible player found for F slot. Optimizer may have selected invalid lineup.")
    idx = eligible_f.sort_values('FPTS', ascending=False).index[0]
    df.loc[idx, 'Slot'] = 'F'
    df.loc[idx, 'assigned'] = True
    
    # Fill UTIL slot (any remaining player - should be exactly 1)
    unassigned = df[df['assigned'] == False]
    if len(unassigned) != 1:
        raise ValueError(f"Expected exactly 1 unassigned player for UTIL slot, but found {len(unassigned)}")
    idx = unassigned.index[0]
    df.loc[idx, 'Slot'] = 'UTIL'
    df.loc[idx, 'assigned'] = True
    
    # Verify all 8 players are assigned
    unassigned_count = (df['assigned'] == False).sum()
    if unassigned_count > 0:
        raise ValueError(f"{unassigned_count} player(s) not assigned to a slot. Lineup is invalid.")
    
    # Verify all 8 slots are filled
    slots_filled = df['Slot'].value_counts()
    required_slots = ['PG', 'SG', 'SF', 'PF', 'C', 'G', 'F', 'UTIL']
    missing_slots = [slot for slot in required_slots if slot not in slots_filled.index]
    if missing_slots:
        raise ValueError(f"Missing required slots: {missing_slots}. Lineup is invalid.")
    
    # Remove helper columns
    df = df.drop(['assigned', 'is_pg_only', 'is_sg_only', 'is_pg_sg', 'is_sf_only', 'is_pf_only', 'is_sf_pf'], axis=1, errors='ignore')
    
    return df


def format_lineup_output(selected_df: pd.DataFrame) -> pd.DataFrame:
    """
    Format optimized lineup for display/saving.
    
    Args:
        selected_df: DataFrame with selected players and Slot assignments (already sorted by Slot)
        
    Returns:
        Formatted DataFrame with totals row at the end, maintaining Slot order: PG, SG, SF, PF, C, G, F, UTIL
    """
    formatted_df = selected_df.copy()
    
    # Ensure rows are in correct slot order: PG, SG, SF, PF, C, G, F, UTIL
    slot_order = {'PG': 1, 'SG': 2, 'SF': 3, 'PF': 4, 'C': 5, 'G': 6, 'F': 7, 'UTIL': 8}
    formatted_df['_slot_order'] = formatted_df['Slot'].map(slot_order)
    formatted_df = formatted_df.sort_values('_slot_order', ascending=True).reset_index(drop=True)
    formatted_df = formatted_df.drop('_slot_order', axis=1)
    
    # Reorder columns: Slot, Player, Position, Team, Salary, FPTS
    column_order = ['Slot', 'Player', 'Position', 'Team', 'Salary', 'FPTS']
    # Only include columns that exist
    column_order = [col for col in column_order if col in formatted_df.columns]
    # Add any remaining columns
    remaining_cols = [col for col in formatted_df.columns if col not in column_order]
    formatted_df = formatted_df[column_order + remaining_cols]
    
    # Calculate totals
    total_salary = formatted_df['Salary'].sum()
    total_fpts = formatted_df['FPTS'].sum()
    
    # Add totals row
    totals_dict = {
        'Player': 'TOTAL',
        'Salary': total_salary,
        'FPTS': total_fpts
    }
    # Add empty values for other columns
    for col in formatted_df.columns:
        if col not in totals_dict:
            totals_dict[col] = ''
    
    totals_row = pd.DataFrame([totals_dict])
    
    formatted_df = pd.concat([formatted_df, totals_row], ignore_index=True)
    
    return formatted_df


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(
        description='Optimize NBA DraftKings lineup using FPTS predictions',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python optimize_draftkings_nba_lineup.py \\
      --draftables ~/Downloads/draftkings_draftables_140610.csv \\
      --predictions ~/Downloads/predictions_export.csv
  
  # With custom salary cap and output file
  python optimize_draftkings_nba_lineup.py \\
      --draftables draftables.csv \\
      --predictions predictions.csv \\
      --max-salary 50000 \\
      --output my_lineup.csv
        """
    )
    parser.add_argument(
        '--draftables',
        type=str,
        required=True,
        help='Path to draftables CSV file (from fetch_draftkings_draftables.py). Required columns: displayName, salary, position'
    )
    parser.add_argument(
        '--predictions',
        type=str,
        required=True,
        help='Path to predictions CSV file (exported from Predictions page). Required columns: Player, FPTS, Team. Export from Predictions page using "Download Predicted Statlines CSV" button.'
    )
    parser.add_argument(
        '--max-salary',
        type=int,
        default=50000,
        help='Maximum total salary (default: 50000)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output CSV file path (default: optimized_lineup_TIMESTAMP.csv)'
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("NBA DraftKings Lineup Optimizer")
    print("=" * 60)
    
    try:
        # Load data
        print("\nLoading data...")
        draftables_df = load_draftables(args.draftables)
        predictions_df = load_predictions(args.predictions)
        
        # Merge datasets
        print("\nMerging draftables with predictions...")
        merged_df = merge_draftables_with_predictions(draftables_df, predictions_df)
        
        if len(merged_df) == 0:
            raise ValueError("No players found after merging datasets")
        
        # Add position flags
        print("\nAdding position eligibility flags...")
        merged_df = add_position_flags(merged_df)
        
        # Check if we have enough players with predictions
        players_with_preds = merged_df[merged_df['FPTS'] > 0]
        print(f"\nPlayers with predictions: {len(players_with_preds)}")
        
        if len(players_with_preds) < 8:
            print(f"Warning: Only {len(players_with_preds)} players have predictions. May not be able to fill lineup.")
        
        # Optimize lineup
        selected_df = optimize_lineup(merged_df, max_salary=args.max_salary)
        
        # Format output
        formatted_df = format_lineup_output(selected_df)
        
        # Display results
        print("\n" + "=" * 60)
        print("OPTIMIZED LINEUP")
        print("=" * 60)
        print(formatted_df.to_string(index=False))
        
        # Calculate and display summary
        total_salary = selected_df['Salary'].sum()
        total_fpts = selected_df['FPTS'].sum()
        salary_remaining = args.max_salary - total_salary
        
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Total Salary: ${total_salary:,} / ${args.max_salary:,}")
        print(f"Salary Remaining: ${salary_remaining:,}")
        print(f"Total FPTS: {total_fpts:.2f}")
        print(f"Average FPTS per Player: {total_fpts / len(selected_df):.2f}")
        
        # Save to CSV
        if args.output:
            output_path = args.output
        else:
            downloads_dir = os.path.expanduser("~/Downloads")
            os.makedirs(downloads_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(downloads_dir, f"optimized_lineup_{timestamp}.csv")
        
        formatted_df.to_csv(output_path, index=False)
        print(f"\n✓ Lineup saved to: {output_path}")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
