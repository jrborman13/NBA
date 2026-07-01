# Roster Rules Digest — 2023 NBA CBA

Bucket: `roster_rules`. Extracted from Article XLI (NBA G League), Article II (Uniform Player Contract), and Article VII §4 (Determination of Team Salary). Page citations are to **printed** pages.

**Counts:** 20 roster rules. Review-flagged: `ROSTER-016`.

---

## G League assignment / recall (Article XLI)

- **ROSTER-001** — NBAGL Work Assignment eligibility. A Team may assign a non-Two-Way player from its Active or Inactive List to its NBAGL team if the player has 0–2 Years of Service; with >2 Years of Service the player **and** the Players Association must consent in writing. The assigned player is placed on the NBA Inactive List. (XLI §1(a), p.550)
- **ROSTER-002** — No numeric limit on the number of NBAGL Work Assignments; assignments may not be used for discipline/retaliation; NBA may set reasonable assignment/recall rules. (XLI §1(b)–(c), p.550)
- **ROSTER-003** — Written notice to player, NBA, and Players Association required to assign or recall; player must report within **48 hours**. Failure to report (without reasonable excuse) is finable/suspendable and prejudicial conduct. (XLI §2(a)–(b), pp.550–551)
- **ROSTER-004** — A suspended player on an NBAGL Work Assignment must stay on the NBA **Inactive List** for the suspension and may not play NBA or NBAGL games; Team may recall at its option. (XLI §4(e)(iv), p.554)
- **ROSTER-005** — A suspended **Two-Way Player** may be kept on the Active, Inactive, or Two-Way List; but if he was on the Active List when the conduct occurred and the NBA imposed the suspension, he stays on the Active List — unless the suspension exceeds **5 games**, in which case he must move to the Two-Way List after the 5th game. (XLI §4(e)(v), p.555)

## 10-Day Contracts (Article II §9)

- **ROSTER-006** — Available from **January 5**; term = longer of 10 days or 3 Team games; Minimum Player Salary; may not extend to/past the Team's last Regular Season game. (II §9(a)–(b),(d), pp.48–49)
- **ROSTER-007** — Same player: max **2** 10-Day Contracts per Season. Concurrent cap by combined Active+Inactive List size (excl. Two-Way): 12→0, 13→1, 14→2, 15→3. Early termination blocks a new contract before the original stated term ends. (II §9(c),(g), pp.48–49)
- **ROSTER-008** — Hardship 10-Day Contracts may be signed any time in the Season; shortened to days remaining if they'd reach the last Regular Season game. (II §9(e), p.49)

## Two-Way Contracts (Article II §11)

- **ROSTER-009** — Max **3** Two-Way Players on a roster at any time. (II §11(b)(i), p.52)
- **ROSTER-010** — A Two-Way Player may be on the Active List for max **50 games** per Regular Season (prorated by days remaining if signed mid-season; minimum 1). (II §11(b)(ii), p.52)
- **ROSTER-011** — Max **90 Under-Fifteen Games** per Regular Season per Two-Way Player on the Active List. "Under-Fifteen Game" = Regular Season game with <15 players on Standard NBA Contracts. (II §11(b)(iii), pp.52–53)
- **ROSTER-012** — Eligibility: no signing after **March 4**; player must have **<4 Years of Service** throughout the Contract (narrow 1-year exception at exactly 4 YOS); max **3 Salary Cap Years** under a Two-Way Contract with the same Team. (II §11(e), p.54)
- **ROSTER-013** — Term max **2 Seasons**; no Option Year or Early Termination Option. (II §11(d), p.54; reinforced by II §2(b), p.15)
- **ROSTER-014** — Standard NBA Contract Conversion Option: Team may convert a Two-Way Contract to a Standard NBA Contract (Minimum Player Salary, remaining term) from July 1 through just before the Team's last Regular Season game of the Salary Cap Year; separately, a negotiated Standard NBA Contract (no Exhibit 10) voids the Two-Way Contract; the contracting Team is the only Team that may sign the player to a standard deal during the term. (II §11(f)–(g), pp.54–56)
- **ROSTER-016** ⚑ — Two-Way Player Conversion Option: every Exhibit 10 Contract gives the Team an option to convert to a Two-Way Contract before the first day of the Regular Season, subject to the Two-Way roster limit (Art. X §4(d), referenced but not in source files). (II §11(h), pp.56–58)

## Team Salary interactions (Article VII §4) & related contract forms (Article II §3)

- **ROSTER-015** — Two-Way Player Salaries are **excluded from Team Salary**; no Room or Exception needed to sign/acquire/convert a Two-Way player. (VII §4(j), p.225)
- **ROSTER-017** — Incomplete-roster charge: July 1 through the day before the Regular Season, a Team with **<12** counted players in Team Salary has Team Salary increased by (12 − count) × rookie (0 YOS) Minimum Annual Salary. Counted players: contracted players in Team Salary, free agents in Team Salary, Offer Sheet players, unsigned First Round Picks. (VII §4(f) + §4(a)(5), pp.216, 220–221)
- **ROSTER-018** — Non-Guaranteed Training Camp Contract (Exhibit 9): requires **≥14** players already signed (excl. Two-Way/training-camp) at signing; max **6** such contracts per Team at once. (II §3(r), pp.20–21)
- **ROSTER-019** — Exhibit 10 Contracts: max **6** per Team at once; each must be 1 Season at Minimum Player Salary (only the Exhibit 10 Bonus permitted; protection only via Conversion Protection Amount). (II §3(s), pp.22–23)
- **ROSTER-020** — A Two-Way Player who **completes** a Two-Way Contract has a Free Agent Amount equal to the 0-YOS Standard-Contract Minimum Annual Salary. (VII §4(d)(7), p.218)

---

## Notes on bucket overlap

Several rules straddle buckets and are cross-referenced in their `notes`:
- **Salary side** (salary_cap / contracts): Two-Way salary formula and protection amounts (II §11(a),(c)), Exhibit 10 Bonus amounts, suspension salary reductions (XLI §4(e)), and the cap-hold mechanics of ROSTER-015/-017/-020 — captured here only for their roster/transaction effect.
- **Free agency**: ROSTER-020 (post-Two-Way Free Agent Amount).

## Review flag

- **ROSTER-016** — relies on Article X §4(d) for the Two-Way Player roster limit cross-reference, which is **not present in the provided source files**. The cross-reference is inferred from context (the 3-Two-Way-Player limit in ROSTER-009) and should be verified against Article X.
