"""
Tanking detection and minute-adjustment utilities.

Shared between the Predictions Streamlit page (3_Predictions.py) and the
headless batch prediction script (generate_predictions_batch.py).

The Streamlit page wraps _get_standings and _get_game_spread with
@st.cache_data and passes the pre-fetched values in via the standings_df /
spread keyword arguments so this module stays free of Streamlit dependencies.
"""

import os
import requests
import pandas as pd

# Teams that have an incentive to WIN despite a poor record.
# These are never flagged as tanking regardless of record.
PICK_INCENTIVE_WIN_TEAM_IDS: set[int] = {
    1610612740,  # New Orleans Pelicans (no 2026 first-round pick)
}

# Internal sentinel — means "auto-fetch from the API"
_FETCH = object()

# ---------------------------------------------------------------------------
# API helpers (no caching — wrap with @st.cache_data in Streamlit contexts)
# ---------------------------------------------------------------------------

def get_standings(season: str = '2025-26'):
    """Fetch NBA standings. Returns a DataFrame or None on failure."""
    try:
        import nba_api.stats.endpoints as _ep
        return _ep.LeagueStandings(
            season=season, league_id='00', timeout=90
        ).get_data_frames()[0]
    except Exception:
        return None


def get_game_spread(away_abbr: str, home_abbr: str) -> float | None:
    """
    Return the absolute point spread from The Odds API.
    Returns None when the key is missing or the game is not found.
    """
    api_key = os.environ.get('THE_ODDS_API_KEY', '')
    if not api_key:
        return None
    try:
        resp = requests.get(
            'https://api.the-odds-api.com/v4/sports/basketball_nba/odds',
            params={'apiKey': api_key, 'regions': 'us', 'markets': 'spreads',
                    'dateFormat': 'iso', 'oddsFormat': 'american'},
            timeout=10,
        )
        resp.raise_for_status()
        from nba_api.stats.static import teams as _nba_teams
        name_to_abbr = {t['full_name']: t['abbreviation'] for t in _nba_teams.get_teams()}
        nick_to_abbr = {t['nickname']: t['abbreviation'] for t in _nba_teams.get_teams()}

        def _resolve(name):
            return name_to_abbr.get(name) or nick_to_abbr.get(name.split()[-1], name)

        for game in resp.json():
            ga = _resolve(game.get('away_team', ''))
            gh = _resolve(game.get('home_team', ''))
            if {ga, gh} == {away_abbr, home_abbr}:
                away_full = game.get('away_team', '')
                for bm in game.get('bookmakers', []):
                    for market in bm.get('markets', []):
                        if market.get('key') == 'spreads':
                            for outcome in market.get('outcomes', []):
                                if outcome.get('name') == away_full:
                                    return abs(float(outcome['point']))
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Core detection logic
# ---------------------------------------------------------------------------

def games_back_from_play_in(team_id: int, standings_df) -> float:
    """Return how many games back a team is from the 10th conference seed."""
    team_row = standings_df[standings_df['TeamID'] == team_id]
    if len(team_row) == 0:
        return 0.0
    conf = team_row['Conference'].iloc[0]
    conf_df = standings_df[standings_df['Conference'] == conf]
    seed10 = conf_df[conf_df['PlayoffRank'] == 10]
    if len(seed10) == 0:
        return 0.0
    w10 = int(seed10['WINS'].iloc[0])
    l10 = int(seed10['LOSSES'].iloc[0])
    w = int(team_row['WINS'].iloc[0])
    l = int(team_row['LOSSES'].iloc[0])
    return max(0.0, ((w10 - w) + (l - l10)) / 2.0)


def detect_tanking(team_id: int, standings_df) -> str | None:
    """
    Return 'hard', 'soft', or None tanking severity for a team.
    Teams in PICK_INCENTIVE_WIN_TEAM_IDS are never flagged as tanking.
    """
    if team_id in PICK_INCENTIVE_WIN_TEAM_IDS:
        return None
    team_row = standings_df[standings_df['TeamID'] == team_id]
    if len(team_row) == 0:
        return None
    w = int(team_row['WINS'].iloc[0])
    l = int(team_row['LOSSES'].iloc[0])
    games_remaining = 82 - w - l
    if games_remaining <= 0:
        return None
    gb = games_back_from_play_in(team_id, standings_df)
    if gb >= 10 and games_remaining <= 20:
        return 'hard'
    if gb >= 6 and games_remaining <= 20:
        return 'soft'
    return None


# ---------------------------------------------------------------------------
# Adjustment computation
# ---------------------------------------------------------------------------

def compute_tanking_adjustments(
    statlines: list,
    away_team_id: int,
    home_team_id: int,
    away_abbr: str,
    home_abbr: str,
    *,
    standings_df=_FETCH,
    spread=_FETCH,
) -> tuple[dict, dict]:
    """
    Detect tanking context for a matchup and return suggested minute
    adjustments together with display metadata.

    Minute adjustment model
    -----------------------
    Tanking team:
      Stars (≥32 MPG avg)     hard: −6, soft: −4
      Starters (28–32)        hard: −5, soft: −3
      Rotation (22–28)        hard: −3, soft: −2
      Bench (<22)             hard: +5, soft: +3  ← more run for back-end guys

    Playoff-contender facing a tanking team (blowout / garbage-time effect):
      Stars                   hard: −4, soft: −2
      Starters                hard: −3, soft: −1
      Rotation                hard: −2, soft:  0
      Bench                   hard: +3, soft: +1  ← bench runs out the clock

    Both teams tanking: apply tanking deltas at 50% for each team.

    Spread amplifier:
      ≥12 pts → 100%  |  8–11 pts → 75%  |  <8 pts → skip
      No spread available → 75% (conservative default).

    Parameters
    ----------
    statlines : list of dicts, each with:
        player_id, is_away, and _original_season_minutes (or MIN)
    standings_df : DataFrame | _FETCH
        Pre-fetched standings (pass a DataFrame to skip the API call).
        Defaults to auto-fetch.
    spread : float | None | _FETCH
        Known spread value, None = "no spread available" (→ 75% multiplier),
        or _FETCH to auto-fetch from The Odds API.

    Returns
    -------
    (manual_adjustments, tanking_context)
        manual_adjustments : dict  player_id_str → target_minutes
        tanking_context    : dict  display metadata for the UI banner
    """
    if standings_df is _FETCH:
        standings_df = get_standings()
    if standings_df is None:
        return {}, {}

    away_tanking = detect_tanking(away_team_id, standings_df)
    home_tanking = detect_tanking(home_team_id, standings_df)

    if away_tanking is None and home_tanking is None:
        return {}, {}

    both_tanking = (away_tanking is not None) and (home_tanking is not None)

    # Spread amplifier
    if spread is _FETCH:
        spread = get_game_spread(away_abbr, home_abbr)

    if spread is None:
        spread_mult = 0.75
    elif spread >= 12:
        spread_mult = 1.0
    elif spread >= 8:
        spread_mult = 0.75
    else:
        away_gb = games_back_from_play_in(away_team_id, standings_df)
        home_gb = games_back_from_play_in(home_team_id, standings_df)
        return {}, {
            'away_tanking': away_tanking, 'home_tanking': home_tanking,
            'away_games_back': away_gb, 'home_games_back': home_gb,
            'spread': spread, 'spread_mult': 0.0,
            'skipped_competitive': True, 'players_adjusted': 0,
        }

    TANK = {
        'hard': {'star': -6, 'starter': -5, 'rotation': -3, 'bench': +5},
        'soft': {'star': -4, 'starter': -3, 'rotation': -2, 'bench': +3},
    }
    BLOW = {
        'hard': {'star': -4, 'starter': -3, 'rotation': -2, 'bench': +3},
        'soft': {'star': -2, 'starter': -1, 'rotation':  0, 'bench': +1},
    }

    def role_tier(baseline):
        if baseline >= 32:
            return 'star'
        if baseline >= 28:
            return 'starter'
        if baseline >= 22:
            return 'rotation'
        return 'bench'

    manual_adjustments: dict = {}
    for statline in statlines:
        pid = statline.get('player_id')
        if not pid:
            continue
        baseline = statline.get('_original_season_minutes', statline.get('MIN', 0))
        if baseline <= 0:
            continue

        is_away = statline.get('is_away', True)
        my_tank = away_tanking if is_away else home_tanking
        opp_tank = home_tanking if is_away else away_tanking
        tier = role_tier(baseline)

        if both_tanking:
            if my_tank:
                raw = TANK[my_tank][tier] * spread_mult * 0.5
                manual_adjustments[str(pid)] = round(max(8.0, baseline + raw), 1)
        elif my_tank:
            raw = TANK[my_tank][tier] * spread_mult
            manual_adjustments[str(pid)] = round(max(8.0, baseline + raw), 1)
        elif opp_tank:
            raw = BLOW[opp_tank][tier] * spread_mult
            if raw != 0:
                manual_adjustments[str(pid)] = round(max(8.0, baseline + raw), 1)

    away_gb = games_back_from_play_in(away_team_id, standings_df)
    home_gb = games_back_from_play_in(home_team_id, standings_df)
    tanking_context = {
        'away_tanking': away_tanking,
        'home_tanking': home_tanking,
        'away_games_back': away_gb,
        'home_games_back': home_gb,
        'spread': spread,
        'spread_mult': spread_mult,
        'both_tanking': both_tanking,
        'skipped_competitive': False,
        'players_adjusted': len(manual_adjustments),
    }
    return manual_adjustments, tanking_context
