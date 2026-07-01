"""
Regression test for the Hexagon page season dropdown.

Bug (2026-06-28): `get_seasons()` in combined-app/pages/7_Hexagon.py fetched every row of
`player_axis_metrics` in a single request and deduped client-side. Supabase/PostgREST caps a
single response at 1000 rows, and rows come back ordered by season ascending, so once the
historical backfill pushed the table past 1000 rows the dropdown only ever showed the THREE
OLDEST seasons (2013-14, 2014-15, 2015-16) — the current season (2025-26) disappeared.

WHY THIS MATTERS: the page is unusable for current-season analysis if the newest season can't be
selected. The fix is to paginate in 1000-row chunks (the same pattern `get_player_names()` already
uses in the same file). These tests encode that intent:

  * test_get_seasons_paginates  — guards the FIX stays in the code (fails on the single-request
    version, passes once get_seasons paginates). Runs with no network.
  * test_all_backfilled_seasons_visible — live check that the paginated access pattern actually
    surfaces every backfilled season incl. the current one. Skips if creds/network unavailable.
"""
import os
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PAGE = REPO / "combined-app" / "pages" / "7_Hexagon.py"

# Seasons that must be selectable: 2013-14 .. 2025-26 (the backfilled range).
EXPECTED_SEASONS = {f"{y}-{str(y + 1)[2:]}" for y in range(2013, 2026)}


def _get_seasons_source() -> str:
    """Return the source of the get_seasons() function from the Hexagon page."""
    src = PAGE.read_text()
    m = re.search(r"def get_seasons\(\):.*?(?=\n@|\ndef |\Z)", src, re.S)
    assert m, "get_seasons() not found in 7_Hexagon.py"
    return m.group(0)


def test_get_seasons_paginates():
    """get_seasons must page beyond the 1000-row cap, not rely on a single .execute()."""
    body = _get_seasons_source()
    assert ".range(" in body, (
        "get_seasons() does not paginate — a single .select(...).execute() is capped at 1000 rows "
        "and will hide the newest seasons. Page in 1000-row chunks like get_player_names()."
    )


def _anon_client():
    sys.path.insert(0, str(REPO / "combined-app" / "player_app"))
    try:
        from supabase_config import get_supabase_client
    except Exception as e:  # pragma: no cover
        pytest.skip(f"supabase client unavailable: {e}")
    c = get_supabase_client()
    if c is None:
        pytest.skip("Supabase not configured (SUPABASE_URL / SUPABASE_KEY missing)")
    return c


def _paginated_seasons(client) -> set:
    seen, start = set(), 0
    while True:
        data = client.table("player_axis_metrics").select("season").range(start, start + 999).execute().data
        if not data:
            break
        seen.update(r["season"] for r in data)
        if len(data) < 1000:
            break
        start += 1000
    return seen


@pytest.mark.skipif(os.getenv("SKIP_DB_TESTS") == "1", reason="DB tests disabled")
def test_all_backfilled_seasons_visible():
    """Paginated access must expose all backfilled seasons, incl. the current one."""
    client = _anon_client()
    seasons = _paginated_seasons(client)
    missing = EXPECTED_SEASONS - seasons
    assert not missing, f"paginated season list is missing {sorted(missing)}"
    assert "2025-26" in seasons, "current season 2025-26 not selectable"
