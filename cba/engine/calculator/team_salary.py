"""
Team Salary calculator — the foundation of the CBA compliance engine.

It implements the `salary_cap` rule bucket (cba/kb/rules_salary_cap.json):
sum of cap figures + cap holds + the Incomplete Roster Charge, then the
team's tier vs. cap / tax / first apron / second apron.

Design notes
------------
* Pure function core (`compute_team_salary`) takes plain inputs so it is
  trivially unit-testable against known team salaries — that is the
  primary accuracy check (see cba/engine/tests).
* Thresholds are NOT hard-coded. They come from `league_constants` for the
  season, so the engine stays correct across cap years.
* Rule references in comments (e.g. CAP-040) point at the source rule in
  cba/kb so every line of logic is traceable back to the CBA.

This is a deliberate skeleton: TODO hooks mark the parts that need the
exact statutory thresholds wired in from the rule objects.
"""
from __future__ import annotations
from dataclasses import dataclass, field


# --- input/output shapes -------------------------------------------------
@dataclass
class LeagueConstants:
    season: str
    salary_cap: int
    tax_level: int
    first_apron: int | None
    second_apron: int | None
    min_team_salary: int | None
    # exception amounts available for reference by other engine modules
    nontax_mle: int | None = None
    tax_mle: int | None = None
    room_mle: int | None = None
    biannual: int | None = None


@dataclass
class ContractRow:
    player_name: str
    cap_figure: int                 # amount that counts toward Team Salary
    contract_type: str = "standard" # standard|rookie_scale|two_way|10_day|rest_of_season|minimum|exhibit10
    unlikely_bonuses: int = 0       # excluded from Team Salary; tracked for apron context


@dataclass
class CapHold:
    hold_type: str                  # free_agent|rookie_hold|exception|incomplete_roster
    amount: int
    player_name: str | None = None


@dataclass
class TeamSalaryState:
    team_id: int
    season: str
    team_salary: int
    cap_room: int                   # positive = room under cap; negative = over
    over_tax: bool
    over_first_apron: bool
    over_second_apron: bool
    hard_cap_level: str = "none"    # set by transaction logic, not by this calc
    detail: dict = field(default_factory=dict)


# --- constants that should ultimately be read FROM the rule objects ------
# Standard NBA roster minimum used for the Incomplete Roster Charge.
# TODO: confirm exact count/threshold against rules_salary_cap.json (CAP-040
# family) and roster_rules; surfaced here so it is reviewable, not buried.
MIN_ROSTER_FOR_CHARGE = 14
# Contract types that do NOT count toward Team Salary.
NON_COUNTING_TYPES = {"two_way"}  # two-way salaries are excluded (see EXC-024 note / roster_rules)


def compute_team_salary(
    team_id: int,
    constants: LeagueConstants,
    contracts: list[ContractRow],
    cap_holds: list[CapHold],
    roster_count: int,
    rookie_minimum: int,
) -> TeamSalaryState:
    """Compute Team Salary and tier flags for one team-season.

    `rookie_minimum` is the season's 0-YOS Minimum Annual Salary, used for the
    Incomplete Roster Charge; pass it from min_salary_scale for the season.
    """
    # 1. Sum counting contracts (CAP-: what counts as Salary / Team Salary).
    contract_total = sum(
        c.cap_figure for c in contracts if c.contract_type not in NON_COUNTING_TYPES
    )

    # 2. Add cap holds: Free Agent Amounts, rookie holds, held exceptions
    #    (CAP- Determination of Team Salary, §4). Incomplete-roster charge is
    #    computed below rather than trusted from input.
    hold_total = sum(h.amount for h in cap_holds if h.hold_type != "incomplete_roster")

    # 3. Incomplete Roster Charge (CAP-040 family): empty spots below the
    #    minimum are each charged the rookie minimum, raising Team Salary
    #    toward the floor for cap-room purposes.
    empty_spots = max(0, MIN_ROSTER_FOR_CHARGE - roster_count)
    incomplete_roster_charge = empty_spots * rookie_minimum

    team_salary = contract_total + hold_total + incomplete_roster_charge

    cap_room = constants.salary_cap - team_salary
    return TeamSalaryState(
        team_id=team_id,
        season=constants.season,
        team_salary=team_salary,
        cap_room=cap_room,
        over_tax=team_salary > constants.tax_level,
        over_first_apron=(constants.first_apron is not None
                          and team_salary > constants.first_apron),
        over_second_apron=(constants.second_apron is not None
                           and team_salary > constants.second_apron),
        detail={
            "contract_total": contract_total,
            "hold_total": hold_total,
            "incomplete_roster_charge": incomplete_roster_charge,
            "empty_spots": empty_spots,
        },
    )


if __name__ == "__main__":
    # Smoke test with illustrative numbers (NOT a real roster).
    c25 = LeagueConstants(
        season="2025-26", salary_cap=154_647_000, tax_level=187_895_000,
        first_apron=195_945_000, second_apron=207_824_000, min_team_salary=139_182_000,
    )
    state = compute_team_salary(
        team_id=1610612750,
        constants=c25,
        contracts=[ContractRow("Player A", 50_000_000),
                   ContractRow("Player B", 30_000_000),
                   ContractRow("Two-Way C", 600_000, contract_type="two_way")],
        cap_holds=[CapHold("free_agent", 12_000_000, "FA D")],
        roster_count=12,
        rookie_minimum=1_200_000,
    )
    print(state)
