"""
Prediction Store
Upload and retrieve per-player normalized stat predictions from Supabase.
Used as a cross-page cache so the model only runs once per day.
"""

import logging
import pandas as pd
from typing import Dict, List, Optional, Any
from datetime import date

logger = logging.getLogger(__name__)


# ─── Supabase helpers ────────────────────────────────────────────────────────

def _get_client():
    try:
        from supabase_config import get_supabase_client, is_supabase_configured
        if is_supabase_configured():
            return get_supabase_client()
    except Exception:
        pass
    return None


def _get_write_client():
    """Client for INSERT/UPDATE/DELETE on player_predictions.

    supabase_config builds its client from SUPABASE_KEY, which is the publishable
    (anon) key. Migration `enable_rls_public_readonly_anon` (2026-08-04) turned on
    RLS with a SELECT-only anon policy so the website could read safely — which
    also means anon writes now fail with 42501. Every write here has silently
    returned False since that date; the season had already ended, so nobody saw it.

    Writes therefore need the service-role key, matching what
    historical-database/scripts/supabase_io.py already does. Falls back to the
    read client so behaviour is unchanged where no service key is configured.
    """
    import os
    url = os.environ.get('SUPABASE_URL')
    service_key = os.environ.get('SUPABASE_SERVICE_KEY')
    if url and service_key:
        try:
            from supabase import create_client
            return create_client(url, service_key)
        except Exception as e:
            logger.warning(f"service-role client unavailable, falling back to read client: {e}")
    return _get_client()


TABLE = 'player_predictions'


# ─── Public API ──────────────────────────────────────────────────────────────

def delete_predictions_for_date(game_date: str) -> bool:
    """Delete all cached predictions for a given date from Supabase."""
    client = _get_write_client()
    if not client:
        return False
    try:
        client.table(TABLE).delete().eq('game_date', game_date).execute()
        logger.info(f"Deleted predictions for {game_date}")
        return True
    except Exception as e:
        logger.warning(f"delete_predictions_for_date failed: {e}")
        return False


def predictions_exist_for_date(game_date: str) -> bool:
    """Return True if at least one prediction row exists for this date."""
    client = _get_client()
    if not client:
        return False
    try:
        resp = (client.table(TABLE)
                .select('player_id')
                .eq('game_date', game_date)
                .limit(1)
                .execute())
        return bool(resp.data)
    except Exception as e:
        logger.warning(f"predictions_exist_for_date failed: {e}")
        return False


def upload_game_predictions(
    game_date: str,
    away: str,
    home: str,
    statlines: List[Dict],
    ceiling_floor_map: Optional[Dict[str, Dict]] = None,
) -> bool:
    """
    Upsert normalized statlines for one game into Supabase.

    Args:
        game_date:         YYYY-MM-DD
        away / home:       team tricodes
        statlines:         list of statline dicts (post-normalize_team_minutes)
        ceiling_floor_map: optional dict of player_id -> {ceiling, floor, median, std_dev}
    """
    client = _get_write_client()
    if not client:
        return False

    cf_map = ceiling_floor_map or {}
    game_label = f"{away} @ {home}"
    rows = []

    for sl in statlines:
        pid = str(sl.get('player_id', ''))
        if not pid:
            continue
        proj_min = float(sl.get('MIN', 0))
        if proj_min <= 0.01:
            continue

        cf = cf_map.get(pid, {})
        pts  = round(float(sl.get('PTS',  0)), 2)
        reb  = round(float(sl.get('REB',  0)), 2)
        ast  = round(float(sl.get('AST',  0)), 2)
        stl  = round(float(sl.get('STL',  0)), 2)
        blk  = round(float(sl.get('BLK',  0)), 2)
        tov  = round(float(sl.get('TOV',  0)), 2)
        fg3m = round(float(sl.get('FG3M', 0)), 2)
        ftm  = round(float(sl.get('FTM',  0)), 2)
        pra  = round(float(sl.get('PRA',  pts + reb + ast)), 2)
        ra   = round(float(sl.get('RA',   reb + ast)), 2)
        fpts_val = round(float(sl.get('FPTS', pts + reb * 1.2 + ast * 1.5 + stl * 3.0 + blk * 3.0 - tov)), 2)

        rows.append({
            'game_date':    game_date,
            'player_id':    pid,
            'player_name':  sl.get('Player', sl.get('player_name', '')),
            'team':         sl.get('Team',   sl.get('team', '')),
            'opponent':     home if sl.get('is_away') else away,
            'game':         game_label,
            'is_home':      not sl.get('is_away', True),
            'proj_min':     round(proj_min, 1),
            'pts':          pts,
            'reb':          reb,
            'ast':          ast,
            'stl':          stl,
            'blk':          blk,
            'tov':          tov,
            'fg3m':         fg3m,
            'ftm':          ftm,
            'pra':          pra,
            'ra':           ra,
            'fpts':         fpts_val,
            'fpts_ceiling': round(float(cf.get('ceiling', fpts_val * 1.3)), 2),
            'fpts_floor':   round(float(cf.get('floor',   fpts_val * 0.7)), 2),
            'fpts_median':  round(float(cf.get('median',  fpts_val)),        2),
            'fpts_stddev':  round(float(cf.get('std_dev', 0)),               2),
        })

    if not rows:
        return False

    try:
        # Upsert in batches of 100
        for i in range(0, len(rows), 100):
            client.table(TABLE).upsert(
                rows[i:i + 100],
                on_conflict='game_date,player_id',
            ).execute()
        logger.info(f"Uploaded {len(rows)} predictions for {game_label} on {game_date}")
        return True
    except Exception as e:
        logger.warning(f"upload_game_predictions failed for {game_label}: {e}")
        return False


def load_predictions_for_date(game_date: str) -> Optional[pd.DataFrame]:
    """
    Load all predictions for a date from Supabase.
    Returns a DataFrame or None if unavailable.
    """
    client = _get_client()
    if not client:
        return None
    try:
        resp = (client.table(TABLE)
                .select('*')
                .eq('game_date', game_date)
                .execute())
        if not resp.data:
            return None
        return pd.DataFrame(resp.data)
    except Exception as e:
        logger.warning(f"load_predictions_for_date failed: {e}")
        return None


def reconstruct_norm_preds(df: pd.DataFrame, away: str, home: str) -> Dict[str, Any]:
    """
    Reconstruct the _norm_preds dict expected by find_best_value_plays()
    for a single game, from the loaded DataFrame.

    Returns dict keyed by player_id with the same shape as the in-memory dict
    built in 3_Predictions.py step 4.
    """
    from types import SimpleNamespace

    game_label = f"{away} @ {home}"
    game_df = df[df['game'] == game_label]
    norm_preds = {}

    for _, row in game_df.iterrows():
        pid = str(row['player_id'])
        stats = {
            'PTS':  float(row.get('pts',  0) or 0),
            'REB':  float(row.get('reb',  0) or 0),
            'AST':  float(row.get('ast',  0) or 0),
            'STL':  float(row.get('stl',  0) or 0),
            'BLK':  float(row.get('blk',  0) or 0),
            'TOV':  float(row.get('tov',  0) or 0),
            'FG3M': float(row.get('fg3m', 0) or 0),
            'FTM':  float(row.get('ftm',  0) or 0),
            'PRA':  float(row.get('pra',  0) or 0),
            'RA':   float(row.get('ra',   0) or 0),
            'FPTS': float(row.get('fpts', 0) or 0),
        }
        norm_preds[pid] = {
            'predictions': {
                stat: SimpleNamespace(value=val, confidence='high',
                                      breakdown={'supabase': val}, factors={})
                for stat, val in stats.items()
            },
            'player_name':   str(row.get('player_name', '')),
            'team_abbr':     str(row.get('team', '')),
            'is_home':       bool(row.get('is_home', False)),
            'opponent_abbr': str(row.get('opponent', '')),
            '_proj_min':     float(row.get('proj_min', 0) or 0),
        }

    return norm_preds


def reconstruct_csv_df(df: pd.DataFrame, away: str, home: str) -> pd.DataFrame:
    """
    Reconstruct the CSV DataFrame format expected by the DraftKings Optimizer
    (same shape as predicted_statlines_{away}_vs_{home}_{date}.csv).
    """
    game_label = f"{away} @ {home}"
    game_df = df[df['game'] == game_label].copy()
    if game_df.empty:
        return pd.DataFrame()

    out = pd.DataFrame({
        'Player':        game_df['player_name'].values,
        'Team':          game_df['team'].values,
        'MIN':           game_df['proj_min'].fillna(0).values,
        'PTS':           game_df['pts'].fillna(0).values,
        'REB':           game_df['reb'].fillna(0).values,
        'AST':           game_df['ast'].fillna(0).values,
        'STL':           game_df['stl'].fillna(0).values,
        'BLK':           game_df['blk'].fillna(0).values,
        'TOV':           game_df['tov'].fillna(0).values,
        'FG3M':          game_df['fg3m'].fillna(0).values,
        'FTM':           game_df['ftm'].fillna(0).values,
        'PRA':           game_df['pra'].fillna(0).values,
        'FPTS':          game_df['fpts'].fillna(0).values,
        'FPTS_Ceiling':  game_df['fpts_ceiling'].fillna(0).values,
        'FPTS_Floor':    game_df['fpts_floor'].fillna(0).values,
        'FPTS_Median':   game_df['fpts_median'].fillna(0).values,
        'FPTS_Variance': (game_df['fpts_stddev'].fillna(0) ** 2).values,
        'FPTS_StdDev':   game_df['fpts_stddev'].fillna(0).values,
    })
    return out
