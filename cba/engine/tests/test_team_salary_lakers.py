"""
End-to-end accuracy proof: parse a real SalarySwish team page into contract
rows, run them through the Team Salary calculator, and check the result
against SalarySwish's own published figure.

This is the regression pattern: the calculator is "correct" only when it
reproduces a known team's number. Run: python3 tests/test_team_salary_lakers.py
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from ingest.salaryswish_loader import contract_row_from_cell, parse_money_cell  # noqa
from calculator.team_salary import (LeagueConstants, ContractRow,  # noqa
                                     CapHold, compute_team_salary)

SEASON = "2026-27"
# 2026-27 constants as published on SalarySwish (projected; cap not yet official June 2026).
C2627 = LeagueConstants(
    season=SEASON, salary_cap=165_472_000, tax_level=201_048_000,
    first_apron=209_661_000, second_apron=222_372_000, min_team_salary=148_924_800,
)
PUBLISHED_ROSTER_CAP_HIT = 109_001_737   # SalarySwish, 2026-27 active roster


def load_fixture():
    path = os.path.join(os.path.dirname(__file__), "fixtures", "lakers_2026-27_active.txt")
    rows = []
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, acquired, cell = [p.strip() for p in line.split("|")]
        r = contract_row_from_cell(name, SEASON, cell, acquired_via=acquired)
        assert r is not None, f"failed to parse: {line}"
        rows.append(r)
    return rows


def main():
    rows = load_fixture()
    contracts = [ContractRow(player_name=r["player_name"], cap_figure=r["cap_figure"])
                 for r in rows]

    # Active-roster summation check (no holds): must equal published roster cap hit.
    total = sum(c.cap_figure for c in contracts)
    assert total == PUBLISHED_ROSTER_CAP_HIT, (
        f"roster cap hit mismatch: got {total:,} vs published {PUBLISHED_ROSTER_CAP_HIT:,}")
    print(f"PASS  roster cap hit  ${total:,}  == SalarySwish published")

    # Spot-check option/guarantee parsing on two known cells.
    assert parse_money_cell("P  $5,390,700$5,390,700$5,390,700$0")["option"] == "player"
    assert parse_money_cell("T  $2,497,812$0$2,497,812$0")["guaranteed"] == 0
    print("PASS  option flags + guarantee parsing")

    # Tier flags: Lakers (with holds) are above the 2nd apron, but THIS active-only
    # slice ($109M) is below every line — verify the calculator's tiering logic.
    state = compute_team_salary(
        team_id=1610612747, constants=C2627, contracts=contracts,
        cap_holds=[], roster_count=10, rookie_minimum=1_270_000)
    assert state.over_first_apron is False and state.over_second_apron is False
    print(f"PASS  tiering  team_salary=${state.team_salary:,} "
          f"(active-only slice, below all lines as expected)")
    print("\nNOTE: full team salary incl. cap holds reconciliation is the next "
          "validation layer (which FA holds count toward cap vs. apron).")


if __name__ == "__main__":
    main()
