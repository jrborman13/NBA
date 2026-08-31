"""Period arithmetic in build_pbp_lineups, per league AND per era (SITE-78).

The WNBA played two 20-minute halves from 1997 to 2005. The builder encoded every
WNBA season as 10-minute quarters, which made `elapsed()` go negative — 26,887 of
123,465 stored half-era stint rows (21.8%) have a negative elapsed second.

Two distinct bugs, and fixing only the first leaves the second:

  1. the period LENGTH  — 600s where the clock counts down from PT20M
  2. the regulation CUTOFF — `p <= 4` treats half-era periods 3 and 4 as
     regulation, but in a two-half game those are OVERTIME (127 games)

These are pure arithmetic; no database. The negative-elapsed counts that motivated
them are measured in the SITE-78 ticket, not here.
"""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "historical-database" / "scripts"))

bpl = pytest.importorskip("build_pbp_lineups")


@pytest.fixture
def era():
    """Set the module globals the way main() does, and always restore the NBA defaults."""
    saved = (bpl.REG_SEC, bpl.REG_PERIODS)

    def _set(reg_sec, reg_periods):
        bpl.REG_SEC, bpl.REG_PERIODS = reg_sec, reg_periods

    yield _set
    bpl.REG_SEC, bpl.REG_PERIODS = saved


def test_nba_defaults_are_12_minute_quarters():
    """The module defaults are the NBA's. This pins that the SITE-78 fix did not move them:
    the old code hardcoded `p <= 4`, so REG_PERIODS=4 must reproduce it exactly."""
    assert (bpl.REG_SEC, bpl.REG_PERIODS) == (720, 4)
    assert bpl.period_len(4) == 720, "period 4 is regulation in the NBA"
    assert bpl.period_len(5) == 300, "period 5 is overtime"


def test_wnba_modern_era_is_10_minute_quarters(era):
    era(600, 4)
    assert [bpl.period_len(p) for p in (1, 2, 3, 4)] == [600] * 4
    assert bpl.period_len(5) == 300
    assert bpl.period_bounds(4) == (1800, 2400), "a 40-minute game"


def test_wnba_half_era_is_two_20_minute_halves(era):
    """1997-2005. This is the length half of the bug."""
    era(1200, 2)
    assert bpl.period_len(1) == 1200
    assert bpl.period_len(2) == 1200
    assert bpl.period_bounds(2) == (1200, 2400), "regulation still ends at 2400s"


def test_wnba_half_era_period_3_is_overtime_not_regulation(era):
    """The cutoff half of the bug, and the half that fixing REG_SEC alone leaves behind.

    Under the old `p <= 4` test, period 3 of a two-half game was called regulation and
    given a full period length. It is a 5-minute overtime.
    """
    era(1200, 2)
    assert bpl.period_len(3) == 300, "period 3 is OT when regulation is two halves"
    assert bpl.period_len(4) == 300, "so is period 4 — a double overtime"
    assert bpl.period_bounds(3) == (2400, 2700)
    assert bpl.period_bounds(4) == (2700, 3000), "double-OT game runs 3000s"


def test_elapsed_is_non_negative_across_a_half_era_period(era):
    """The symptom the ticket is named for.

    `elapsed()` is `start + (period_len - remaining)`. With a 600s period length and a
    clock counting down from 20:00, that is 600 - 1184 = -584. Walk the real clock range
    and assert nothing goes negative.
    """
    era(1200, 2)
    for minute in range(21):
        clk = f"PT{minute:02d}M00.00S"
        for period in (1, 2):
            assert bpl.elapsed(period, clk) >= 0, f"period {period} at {clk}"
    assert bpl.elapsed(1, "PT20M00.00S") == 0, "tip-off is elapsed 0"
    assert bpl.elapsed(2, "PT00M00.00S") == 2400, "end of regulation"


# ---------------------------------------------------------------------------
# The era BOUNDARY itself.
#
# The tests above set REG_SEC/REG_PERIODS explicitly, so they prove period_len's
# arithmetic and nothing about which era a given season selects. Verified 2026-08-30:
# breaking the boundary (`<= 2005` -> `<= 1900`) left all five of them green. That is
# why period_shape() was extracted from main() — the boundary is the load-bearing
# decision, and it needs an assertion that can fail.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("season,expected", [
    ("1997", (1200, 2)),   # first WNBA season, two 20-minute halves
    ("2005", (1200, 2)),   # last half-era season
    ("2006", (600, 4)),    # first quarter-era season
    ("2026", (600, 4)),
])
def test_wnba_period_shape_by_season(season, expected):
    assert bpl.period_shape("wnba", season) == expected


def test_wnba_era_boundary_is_between_2005_and_2006():
    """Pin the boundary itself, not just seasons either side of it."""
    assert bpl.period_shape("wnba", "2005") != bpl.period_shape("wnba", "2006")
    assert bpl.period_shape("wnba", "2005")[1] == 2, "2005 regulation is two halves"
    assert bpl.period_shape("wnba", "2006")[1] == 4, "2006 regulation is four quarters"


def test_nba_period_shape_ignores_the_wnba_era_rule():
    """NBA seasons are "2025-26" and would raise if parsed as an int. They must not be."""
    assert bpl.period_shape("nba", "2025-26") == (720, 4)
    assert bpl.period_shape("nba", "1999-00") == (720, 4), "no WNBA era rule leaks across"
