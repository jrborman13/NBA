"""
Parlay Tracker Module
Log saved parlays to Supabase, verify results against actual box scores,
and track unit P&L over time.
"""

import json
import os
import uuid
import logging
import requests as _requests
from datetime import datetime, date
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

FALLBACK_FILE = "parlay_log.json"


# ─── Supabase helpers ─────────────────────────────────────────────────────────

def _get_client():
    try:
        from supabase_config import get_supabase_client, is_supabase_configured
        if is_supabase_configured():
            return get_supabase_client()
    except Exception:
        pass
    return None


# ─── Payout helpers ───────────────────────────────────────────────────────────

def american_to_decimal(american_odds: int) -> float:
    """Convert American odds to decimal multiplier (includes stake return)."""
    if american_odds < 0:
        return round(100 / abs(american_odds) + 1, 4)
    return round(american_odds / 100 + 1, 4)


def parlay_payout_multiplier(legs: List[Dict]) -> float:
    """
    Calculate parlay payout multiplier by stacking each leg's decimal odds.
    Uses over_odds if lean is Over, under_odds if Under. Falls back to -110.
    Returns profit multiplier (e.g. 5.95 means win 5.95 units on 1 unit risked).
    """
    multiplier = 1.0
    for leg in legs:
        if 'Over' in leg.get('lean', ''):
            american = leg.get('over_odds', -110)
        else:
            american = leg.get('under_odds', -110)
        multiplier *= american_to_decimal(int(american))
    # Subtract stake to get profit multiplier
    return round(multiplier - 1.0, 4)


# ─── Save parlay ──────────────────────────────────────────────────────────────

def save_parlay(game_date: str, legs: List[Dict], payout_override: Optional[float] = None) -> Optional[str]:
    """
    Save a parlay to Supabase (or local JSON fallback).
    Returns the parlay_id (uuid string) on success, None on failure.
    payout_override: if provided, stores this value instead of the auto-calculated multiplier.
    """
    parlay_id = str(uuid.uuid4())
    payout_mult = payout_override if payout_override is not None else parlay_payout_multiplier(legs)

    # Strip keys we don't need to persist (keeps row size small)
    clean_legs = [
        {k: v for k, v in leg.items()
         if k in ('player_id', 'player_name', 'team', 'opponent', 'stat',
                  'line', 'lean', 'prediction', 'edge_pct',
                  'over_odds', 'under_odds', 'game')}
        for leg in legs
    ]

    record = {
        'id': parlay_id,
        'game_date': game_date,
        'logged_at': datetime.utcnow().isoformat(),
        'legs': clean_legs,
        'status': 'pending',
        'units_risked': 1.0,
        'payout_multiplier': payout_mult,
        'legs_won': None,
        'legs_total': len(clean_legs),
        'units_returned': None,
        'verified_at': None,
    }

    client = _get_client()
    if client:
        try:
            row = {**record, 'legs': json.dumps(clean_legs)}
            client.table('parlay_log').insert(row).execute()
            return parlay_id
        except Exception as e:
            logger.warning(f"Supabase insert failed, falling back to JSON: {e}")

    # Fallback: local JSON file
    try:
        existing = _load_fallback()
        existing.append(record)
        with open(FALLBACK_FILE, 'w') as f:
            json.dump(existing, f, indent=2, default=str)
        return parlay_id
    except OSError as e:
        logger.warning(f"Fallback JSON write failed: {e}")
        return None


# ─── Load parlays ─────────────────────────────────────────────────────────────

def load_parlays(status: Optional[str] = None, limit: int = 200) -> List[Dict]:
    """
    Load parlays from Supabase (or local JSON fallback).
    Optionally filter by status: 'pending', 'won', 'lost'.
    """
    client = _get_client()
    if client:
        try:
            q = (client.table('parlay_log')
                 .select('*')
                 .order('logged_at', desc=True)
                 .limit(limit))
            if status:
                q = q.eq('status', status)
            resp = q.execute()
            rows = resp.data or []
            for row in rows:
                if isinstance(row.get('legs'), str):
                    try:
                        row['legs'] = json.loads(row['legs'])
                    except Exception:
                        pass
            return rows
        except Exception as e:
            logger.warning(f"Supabase load failed, falling back to JSON: {e}")

    rows = _load_fallback()
    if status:
        rows = [r for r in rows if r.get('status') == status]
    return sorted(rows, key=lambda x: x.get('logged_at', ''), reverse=True)[:limit]


def _load_fallback() -> List[Dict]:
    try:
        with open(FALLBACK_FILE, 'r') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return []


def update_payout(parlay_id: str, new_payout: float, status: str) -> None:
    """Override the stored payout multiplier and recalculate units_returned."""
    units_returned = round(new_payout, 4) if status == 'won' else 0.0
    _update_parlay(parlay_id, {
        'payout_multiplier': round(new_payout, 4),
        'units_returned': units_returned,
    })


def delete_parlay(parlay_id: str) -> bool:
    """Delete a parlay record by ID. Returns True on success."""
    client = _get_client()
    if client:
        try:
            client.table('parlay_log').delete().eq('id', parlay_id).execute()
            return True
        except Exception as e:
            logger.warning(f"Supabase delete failed, falling back to JSON: {e}")

    try:
        rows = _load_fallback()
        rows = [r for r in rows if r.get('id') != parlay_id]
        with open(FALLBACK_FILE, 'w') as f:
            json.dump(rows, f, indent=2, default=str)
        return True
    except OSError as e:
        logger.warning(f"Fallback JSON delete failed: {e}")
        return False


def _update_parlay(parlay_id: str, updates: Dict):
    """Update a parlay record in Supabase or the fallback JSON."""
    client = _get_client()
    if client:
        try:
            row_updates = {**updates}
            if 'legs' in row_updates:
                row_updates['legs'] = json.dumps(row_updates['legs'])
            client.table('parlay_log').update(row_updates).eq('id', parlay_id).execute()
            return
        except Exception as e:
            logger.warning(f"Supabase update failed, falling back to JSON: {e}")

    try:
        rows = _load_fallback()
        for row in rows:
            if row.get('id') == parlay_id:
                row.update(updates)
        with open(FALLBACK_FILE, 'w') as f:
            json.dump(rows, f, indent=2, default=str)
    except OSError as e:
        logger.warning(f"Fallback JSON update failed: {e}")


# ─── Verification ─────────────────────────────────────────────────────────────

def _get_actual_stat(player_id: str, game_date: str, stat: str, game_logs_df) -> Optional[float]:
    """Look up a player's actual box-score stat from bulk_game_logs DataFrame."""
    if game_logs_df is None or len(game_logs_df) == 0:
        return None

    mask = (
        (game_logs_df['PLAYER_ID'].astype(str) == str(player_id)) &
        (game_logs_df['GAME_DATE'].astype(str).str[:10] == str(game_date)[:10])
    )
    rows = game_logs_df[mask]
    if len(rows) == 0:
        return None
    row = rows.iloc[0]

    def _col(name: str) -> float:
        return float(row[name]) if name in row.index and row[name] is not None else 0.0

    if stat == 'PRA':
        return _col('PTS') + _col('REB') + _col('AST')
    if stat == 'RA':
        return _col('REB') + _col('AST')
    if stat in row.index:
        return float(row[stat]) if row[stat] is not None else None
    return None


def verify_pending_parlays(game_logs_df) -> Dict[str, Any]:
    """
    Score all pending parlays whose game_date is before today.
    Marks each leg with actual value + result, updates status and units_returned.
    Returns a summary dict.
    """
    today = str(date.today())
    pending = [p for p in load_parlays(status='pending')
               if str(p.get('game_date', '9999-99-99'))[:10] < today]

    verified_count = 0
    skipped_count = 0

    for parlay in pending:
        legs = parlay.get('legs', [])
        legs_won = 0
        all_found = True

        for leg in legs:
            actual = _get_actual_stat(
                leg['player_id'], parlay['game_date'], leg['stat'], game_logs_df
            )
            if actual is None:
                all_found = False
                leg['result'] = 'unknown'
                continue

            line = float(leg.get('line', 0))
            lean = leg.get('lean', '')
            leg['actual'] = round(actual, 1)
            if 'Over' in lean:
                leg['result'] = 'win' if actual > line else 'loss'
            else:
                leg['result'] = 'win' if actual < line else 'loss'

            if leg['result'] == 'win':
                legs_won += 1

        if not all_found:
            skipped_count += 1
            continue

        won = (legs_won == len(legs))
        payout_mult = float(parlay.get('payout_multiplier', 6.0))
        units_returned = round(payout_mult, 4) if won else 0.0

        _update_parlay(parlay['id'], {
            'status': 'won' if won else 'lost',
            'legs_won': legs_won,
            'units_returned': units_returned,
            'verified_at': datetime.utcnow().isoformat(),
            'legs': legs,
        })
        verified_count += 1

    return {
        'verified': verified_count,
        'skipped': skipped_count,
        'total_pending': len(pending),
    }


# ─── P&L summary ──────────────────────────────────────────────────────────────

def get_pnl_summary(parlays: List[Dict]) -> Dict[str, Any]:
    """Compute overall unit P&L from a list of parlay records."""
    resolved = [p for p in parlays if p.get('status') in ('won', 'lost')]
    pending  = [p for p in parlays if p.get('status') == 'pending']

    total_risked   = sum(float(p.get('units_risked', 1.0)) for p in resolved)
    total_returned = sum(float(p.get('units_returned', 0) or 0) for p in resolved)
    net_units      = round(total_returned - total_risked, 2)

    wins  = sum(1 for p in resolved if p.get('status') == 'won')
    losses = sum(1 for p in resolved if p.get('status') == 'lost')

    return {
        'total': len(resolved),
        'wins': wins,
        'losses': losses,
        'win_rate': round(wins / len(resolved) * 100, 1) if resolved else 0.0,
        'units_risked': round(total_risked, 2),
        'units_returned': round(total_returned, 2),
        'net_units': net_units,
        'pending': len(pending),
    }


# ─── Discord notification ─────────────────────────────────────────────────────

def _get_webhook_url() -> str:
    """Read webhook URL from Streamlit secrets, env var, or fallback."""
    try:
        import streamlit as st
        url = st.secrets.get('DISCORD_WEBHOOK_URL') or st.secrets.get('secrets', {}).get('DISCORD_WEBHOOK_URL', '')
        if url:
            return url
    except Exception:
        pass
    return os.environ.get('DISCORD_WEBHOOK_URL', '')


def post_parlay_to_discord(game_date: str, legs: List[Dict], payout_mult: float) -> bool:
    """
    Post a saved parlay to Discord as a rich embed.
    Returns True on success, False on failure.
    """
    webhook_url = _get_webhook_url()
    if not webhook_url:
        logger.warning("DISCORD_WEBHOOK_URL not configured — skipping Discord post.")
        return False

    # Colour: green if majority overs, red if majority unders, purple if mixed
    over_count  = sum(1 for l in legs if 'Over'  in l.get('lean', ''))
    under_count = sum(1 for l in legs if 'Under' in l.get('lean', ''))
    if over_count > under_count:
        color = 0x2ecc71   # green
    elif under_count > over_count:
        color = 0xe74c3c   # red
    else:
        color = 0x9b59b6   # purple

    combined_edge = round(sum(abs(l.get('edge_pct', 0)) for l in legs), 1)

    fields = []
    for i, leg in enumerate(legs, 1):
        lean  = leg.get('lean', '')
        icon  = '📈' if 'Over' in lean else '📉'
        game  = leg.get('game', '')
        game_str = f" — {game}" if game else ''
        fields.append({
            'name': f"Leg {i}  {icon}  {leg.get('player_name', '')} ({leg.get('team', '')}){game_str}",
            'value': (
                f"**{leg.get('stat', '')}** {lean}  "
                f"Line **{round(float(leg.get('line', 0)), 1)}**  •  "
                f"Pred **{round(float(leg.get('prediction', 0)), 1)}**  •  "
                f"Edge **{leg.get('edge_pct', 0):+.1f}%**"
            ),
            'inline': False,
        })

    embed = {
        'title': '🎰 Parlay Saved',
        'color': color,
        'fields': fields,
        'footer': {
            'text': f"Game Date: {game_date}  •  Payout: {payout_mult:.2f}x  •  Combined Edge: {combined_edge:.1f}%"
        },
        'timestamp': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.000Z'),
    }

    try:
        resp = _requests.post(webhook_url, json={'embeds': [embed]}, timeout=5)
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.warning(f"Discord post failed: {e}")
        return False
