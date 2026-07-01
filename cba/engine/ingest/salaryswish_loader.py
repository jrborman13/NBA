"""
SalarySwish -> contract / cap_hold loader.

SalarySwish team pages are SERVER-RENDERED, so they parse cleanly from the
fetched HTML/markdown (unlike Spotrac). This module turns a team page into
rows for the `contract` and `cap_hold` tables in db/001_schema.sql, and also
exposes the page's published totals so the calculator can be validated
against them (SalarySwish computes Team Salary / apron room itself).

Page data model (per the column toggles on the page):
    a salary cell stacks four values  ->  CAP HIT | GUARANTEED | BASE | LIKELY
    an optional leading flag           ->  P = player option, T = team option

NOTE ON TERMS OF USE: SalarySwish has a Terms of Use and runs on ads. Fetch
politely (cache locally, rate-limit, personal use) and confirm bulk pulling
is permitted before scheduling a multi-team crawl.
"""
from __future__ import annotations
import re

OPTION_FLAG = {"P": "player", "T": "team", "E": "eto"}


def parse_money_cell(cell: str) -> dict | None:
    """Parse one stacked salary cell into its components.

    >>> parse_money_cell("$2,296,271$1,258,873$2,296,271$0")
    {'cap_hit': 2296271, 'guaranteed': 1258873, 'base': 2296271, 'likely': 0, 'option': 'none'}
    >>> parse_money_cell("P  $14,898,786$14,898,786$14,898,786$0")['option']
    'player'
    >>> parse_money_cell("Bird UFA") is None
    True
    """
    cell = cell.strip()
    option = "none"
    m = re.match(r"^([PTE])\b", cell)
    if m:
        option = OPTION_FLAG[m.group(1)]
        cell = cell[m.end():]
    nums = [int(x.replace(",", "")) for x in re.findall(r"\$([\d,]+)", cell)]
    if not nums:
        return None
    keys = ["cap_hit", "guaranteed", "base", "likely"]
    out = dict(zip(keys, nums))
    out["option"] = option
    return out


def contract_row_from_cell(player_name: str, season: str, cell: str,
                           contract_type: str = "standard",
                           acquired_via: str | None = None) -> dict | None:
    """Build a `contract` table row from a parsed salary cell."""
    parsed = parse_money_cell(cell)
    if parsed is None:
        return None
    return {
        "player_name": player_name,
        "season": season,
        "cap_figure": parsed["cap_hit"],          # the value that counts toward Team Salary
        "base_salary": parsed["base"],
        "likely_bonuses": parsed["likely"],
        "guaranteed_amount": parsed["guaranteed"],
        "guarantee_status": ("guaranteed" if parsed["guaranteed"] >= parsed["cap_hit"]
                             else "partial" if parsed["guaranteed"] > 0 else "non_guaranteed"),
        "option_type": parsed["option"],
        "is_option_year": parsed["option"] != "none",
        "contract_type": contract_type,
        "acquired_via": acquired_via,
        "source": "salaryswish",
    }


# Published-total labels on the page -> our keys (for calculator validation).
TOTAL_LABELS = {
    "ROSTER CAP HIT": "roster_cap_hit",
    "INCOMPLETE ROSTER CHARGE": "incomplete_roster_charge",
    "HOLDS": "holds",
    "TEAM SALARY": "team_salary",
    "DEAD CAP HIT": "dead_cap",
}


def parse_published_totals(markdown: str, season_index: int = 0) -> dict:
    """Pull the page's own computed totals for the given season column.

    Used as the regression oracle: our calculator must reproduce these.
    `season_index` 0 = first/displayed season column.
    """
    out = {}
    for label, key in TOTAL_LABELS.items():
        m = re.search(rf"{re.escape(label)}\s*\|([^\n]+)", markdown)
        if not m:
            continue
        cells = re.findall(r"\$([\d,]+)|(-)", m.group(1))
        vals = [int(a.replace(",", "")) if a else None for a, b in cells]
        if season_index < len(vals):
            out[key] = vals[season_index]
    return out
