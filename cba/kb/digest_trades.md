# Trades Bucket — Rule Digest (2023 NBA CBA)

Source: `rules_trades.json` (38 rules, `TRADE-001`..`TRADE-038`). Bucket: `trades`.
All citations are to **printed pages**. Paraphrased, not verbatim.

## Source coverage note (important)
The four named source files (VII §8, VII §3, Art. XXIV, Art. XIII) do **not** contain the
core Traded Player Exception (TPE) mechanics or salary-matching percentages. Those live in
**Article VII, Section 6(j)** (Exceptions to the Salary Cap), which was read in full to extract
TRADE-017 through TRADE-030 accurately. Without §6(j) the scope items (TPE creation/use/expiration,
salary matching, aggregation) could not be captured.

## Two scope items not found under their expected names — REVIEW FLAGGED
- **Base Year Compensation (`TRADE-031`)** — the term does **not** appear in VII §3 (Determination
  of Salary) or anywhere in the supplied CBA work files (confirmed via full-text search of
  `cba_full.txt`). The 2023 CBA appears to have eliminated the "Base Year Compensation" label. Its
  functional replacement for over-cap Bird sign-and-trades is the **§6(j)(5) deemed-salary rule**
  (greater of prior salary or 50% of new first-year salary) — captured in `TRADE-025`.
- **Poison pill (`TRADE-038`)** — "poison pill" does **not** appear in any provided file. The
  mechanics usually called "poison pill" derive from §6(j)(5) deemed salary and from Article XI
  offer-sheet structuring (free-agency bucket), neither labeled as such in the 2023 CBA.

## Rule index by sub-area

### Trade definition, cash, timing/restrictions (Article VII §8)
- `TRADE-001` — Definition of a trade (negotiated exchange + trade call; not waivers) — §8(k), p.266
- `TRADE-002` — Cash limit 5.15% of Cap per year, paid/received not netted — §8(a), p.260
- `TRADE-003` — Consent to trade one-year QFA/EQFA contract (implicit no-trade) — §8(b), pp.260-261
- `TRADE-004` — No trade after deadline in a contract's final season — §8(c), p.260
- `TRADE-005` — 30-day restriction: draft rookies & Two-Way signings — §8(d)(i), p.260
- `TRADE-006` — 3-month / Dec 15 restriction: newly signed FAs — §8(d)(ii), pp.260-261
- `TRADE-007` — 3-month / Jan 15 restriction: re-signed Bird FAs >120% on capped team — §8(d)(iii), pp.260-262
- `TRADE-014` — Assignor cannot re-sign player waived by assignee for one year — §8(h), p.265
- `TRADE-015` — Divest preexisting financial arrangements before assignment — §8(i), pp.265-266
- `TRADE-016` — NBA summarizes trade terms to NBPA within one week — §8(j), p.266

### Sign-and-trade & extension/renegotiation trade timing (Article VII §8(e)-(g))
- `TRADE-008` — Sign-and-trade of a Veteran Free Agent (3-4 yrs, conditions) — §8(e)(1), pp.260-261
- `TRADE-009` — Sign-and-trade of an amendment/extension (blackout window, length caps) — §8(e)(2), p.263
- `TRADE-010` — No Exhibit 6 in sign-and-trade contract/extension (physical OK) — §8(e)(3), p.263
- `TRADE-011` — 6-month restriction after large extension/renegotiation (both directions) — §8(f)(i), pp.263-264
- `TRADE-012` — 1-year restriction after Designated Veteran Player Extension/Contract — §8(f)(ii), p.264
- `TRADE-013` — Room calc when trading an extended Rookie Scale Contract — §8(g), pp.264-265

### Traded Player Exception — sizes, creation, use, expiration (Article VII §6(j))
- `TRADE-017` — Standard TPE: 100% + $250K, simultaneous OR non-simul (1-yr window) — §6(j)(1)(i), pp.240-241
- `TRADE-018` — Aggregated Standard TPE: 100% + $250K, simultaneous — §6(j)(1)(ii), pp.240-241
- `TRADE-019` — Transition TPE: 110% + $250K, **2023-24 only** — §6(j)(1)(iii), p.241
- `TRADE-020` — Expanded TPE: greater-of {200%+$250K / 100%+$7.5M-indexed} or 125%+$250K — §6(j)(1)(iv), p.241
- `TRADE-021` — Room Under Cap + $250K acquisition (cannot combine with other TPEs) — §6(j)(1)(v), p.241
- `TRADE-022` — Under-cap team may instead use Transition/Expanded TPE — §6(j)(2), p.242
- `TRADE-027` — No TPE if Disabled Player Exception used for same player — §6(j)(7), p.245
- `TRADE-028` — TPEs do not apply to Two-Way Players — §6(j)(8), p.246
- `TRADE-030` — TPE eligibility & Team Salary inclusion (the §6(n) machinery) — §6(n)(1)-(2), pp.247-248

### Aggregation rules (Article VII §6(j)(3)-(6))
- `TRADE-023` — 2-month no-aggregation for recently acquired players (Dec 16 carve-out) — §6(j)(4)(i), p.242
- `TRADE-024` — Minimum Traded Player limit in 3+-player aggregations — §6(j)(4)(ii), pp.242-243
- `TRADE-025` — Over-cap QFA/EQFA sign-and-trade deemed salary (50% rule) — §6(j)(5), pp.242-243
- `TRADE-026` — Outgoing salary reduced by unprotected Base Comp; Jan 8 protection-deeming — §6(j)(6), pp.243-245
- `TRADE-029` — $250K allowance → $0 above First Apron (apron cross-ref) — §6(j)(3), p.242

### Trade bonuses & no-trade clauses (Article VII §3(b); Article XXIV)
- `TRADE-032` — Trade bonus treated as signing-bonus salary, allocated on trade — VII §3(b), pp.198-201
- `TRADE-033` — Trade bonus: 15% cap, first-trade-only, paid once — XXIV §2(a)(i)-(ii), p.414
- `TRADE-034` — Trade bonus amendment/addition rules — XXIV §2(a)(iii)-(vi), pp.414-416
- `TRADE-035` — General prohibition of no-trade contracts — XXIV §1, p.414
- `TRADE-036` — Permitted no-trade clause for 8/4 veterans — XXIV §2(b), pp.416-417

### Circumvention (Article XIII)
- `TRADE-037` — Anti-circumvention applies to trades/assignments; penalties — XIII §1(a) (penalties §3(a)), pp.339-342

### Flagged absences
- `TRADE-031` — Base Year Compensation not present in the 2023 CBA (REVIEW) — VII §3, pp.198-210
- `TRADE-038` — Poison-pill provision not present under that label (REVIEW) — VII §6(j)(5), pp.242-243

## Apron cross-references (handled primarily in the aprons bucket)
- §8(a) cash limit, §8(e)(1) sign-and-trade, and all §6(j) TPEs are "Subject to Section 2(e)"
  (apron restrictions). Only the base mechanics are captured here.
- `TRADE-029` captures the one concrete base-mechanics apron interaction: the $250,000 trade
  allowance drops to $0 when post-assignment Apron Team Salary exceeds the First Apron Level.

## Key dates referenced
- **30 days** — rookie/Two-Way trade lock (`TRADE-005`)
- **3 months / Dec 15** — newly signed FA trade lock (`TRADE-006`)
- **3 months / Jan 15** — re-signed Bird FA >120% on capped team (`TRADE-007`)
- **Dec 16** — aggregation carve-out trigger (`TRADE-023`)
- **Dec 15 → trade deadline** — Minimum Traded Player aggregation window (`TRADE-024`)
- **Jan 8** — Base Compensation deemed fully protected for outgoing-salary math (`TRADE-026`)
- **6 months** — post-large-extension/renegotiation trade lock (`TRADE-011`)
- **1 year** — post-Designated-Veteran lock (`TRADE-012`); non-simul TPE window (`TRADE-017`);
  assignor re-sign lock (`TRADE-014`)
- **2 months** — no-aggregation window for recently acquired players (`TRADE-023`)
