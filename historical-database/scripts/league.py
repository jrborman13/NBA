"""
League configuration — makes the ingest pipeline target NBA or WNBA cleanly.

The two leagues share the SAME stats platform (nba_api endpoints, identical column schemas),
differing only in: host, league_id, season-string format, history start, period length, and the
destination Postgres schema. Select via env LEAGUE=nba|wnba (default nba).
"""

import os

NBA = {
    "league": "nba",
    "league_id": "00",
    "host": "stats.nba.com",
    "referer": "https://www.nba.com/",
    "origin": "https://www.nba.com",
    "schema": None,           # public for now; -> 'nba' after the schema move
    "season_kind": "range",   # 'YYYY-YY', e.g. 2024-25
    "season_start": 2005,     # validated history start for the full tier set
    "season_end": 2025,
    "period_sec": 720,        # 12-min quarters (lineup time-alignment)
    "teams_static": True,     # build teams dim from nba_api.stats.static.teams
    "standings_v3": False,    # LeagueStandings (V1) works for NBA
    "has_tracking": True,     # LeagueDashPtStats / Synergy / PlayerDashPtPass exist
}

WNBA = {
    "league": "wnba",
    "league_id": "10",
    "host": "stats.wnba.com",
    "referer": "https://www.wnba.com/",
    "origin": "https://www.wnba.com",
    "schema": "wnba",
    "season_kind": "year",    # 'YYYY', e.g. 2024 (single summer season)
    "season_start": 1997,     # league founding; probe confirms per-endpoint cut-offs
    "season_end": 2025,
    "period_sec": 600,        # 10-min quarters
    "teams_static": False,    # no WNBA static; build teams dim from team stats
    "standings_v3": True,     # WNBA needs LeagueStandingsV3 (V1 returns empty)
    "has_tracking": False,    # WNBA has no player-tracking / synergy / passing data
}

_LEAGUES = {"nba": NBA, "wnba": WNBA}


def get_league() -> dict:
    name = os.environ.get("LEAGUE", "nba").strip().lower()
    if name not in _LEAGUES:
        raise ValueError(f"LEAGUE must be one of {list(_LEAGUES)}; got {name!r}")
    return _LEAGUES[name]


def season_string(cfg: dict, start_year: int) -> str:
    """Build a season string for the given league. NBA -> '2024-25'; WNBA -> '2024'."""
    if cfg["season_kind"] == "year":
        return str(start_year)
    return f"{start_year}-{str(start_year + 1)[2:]}"
