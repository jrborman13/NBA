# Manifest — NBA CBA (July 2023) Transaction Rules Knowledge Base

Source document: `NBA CBA - 2023 version.pdf` (676 PDF sheets). All page citations use the CBA's **printed page numbers**; to open one in a PDF viewer add **24** (printed page _N_ = PDF sheet _N_+24). See `00_structure_map.md` for the rationale.

## Files produced (in `cba/kb/`)

| File | Contents |
|---|---|
| `00_structure_map.md` | Article- and section-level table of contents with printed page ranges, the full Exhibit list, the page-number convention, the bucket→source map, and the list of Articles judged irrelevant to transaction-checking. |
| `01_defined_terms.json` | Glossary: 148 defined/operative terms a transaction rule could depend on, each paraphrased with an Article/Section/page citation. |
| `02_crossref.json` | Cross-reference index: rule→related-rules, rule→defined-terms, the reverse term→rules index, plus `unresolved_term_references` (term strings not in the glossary) and `dangling_rule_references` (empty). |
| `rules_free_agency.json` | 39 rules — UFA/RFA, qualifying offers, required tenders, offer sheets, moratorium, Bird/Early Bird/Non-Bird rights, right of first refusal. |
| `rules_trades.json` | 38 rules — salary matching, simultaneous vs non-simultaneous trades, Traded Player Exception, aggregation, deemed-salary (the 2023 successor to Base Year Compensation), no-trade clauses, trade bonuses, timing/eligibility. |
| `rules_salary_cap.json` | 40 rules — how the Cap / Minimum Team Salary / Tax Level / Apron Levels are set, what counts as Salary, cap holds, incomplete-roster charges. |
| `rules_aprons_and_hard_caps.json` | 25 rules — first- and second-apron transaction restrictions and hard-cap triggers. |
| `rules_exceptions.json` | 29 rules — every cap exception (Bird/Early Bird/Non-Bird, the three MLEs, Bi-annual, Disabled Player, Minimum, Rookie, Traded Player, Second Round Pick, Reinstatement) with amounts, mechanics, and eligibility. |
| `rules_contracts.json` | 43 rules — max/min salaries, rookie scale, allowable raises, options, veteran and rookie-scale extensions, contract lengths, Exhibit-10/9 and 10-day mechanics, signing eligibility. |
| `rules_roster_rules.json` | 20 rules — roster size, two-way contracts, 10-day contracts, G League assignment/recall, minimum-roster interaction with the incomplete-roster charge. |
| `digest_<bucket>.md` (×7) | Human-readable, skimmable summary of each bucket's rules with citations, for spot-checking against the source. |

## Rule counts by bucket

| Bucket | Rules |
|---|---|
| contracts | 43 |
| salary_cap | 40 |
| free_agency | 39 |
| trades | 38 |
| exceptions | 29 |
| aprons_and_hard_caps | 25 |
| roster_rules | 20 |
| **Total** | **234** |

Glossary: **148** defined terms. `rules_other.json` was **not** created — every candidate rule mapped cleanly to a standard bucket.

## Rules flagged `review_flag: true` (7) — please verify these

- **CONTRACT-008** — Minimum-salary figures in Exhibit C are labeled "Baseline." The actual minimum each Salary Cap Year is that baseline escalated per the Agreement, so the literal exhibit numbers are not the live amounts.
- **CONTRACT-026** — Same "Baseline" caveat for the Exhibit B Rookie Salary Scale: live scale = baseline escalated each year.
- **CAP-033** — Bundles several smaller Article VII §3 salary-treatment/exclusion sub-rules (loans 3(c), one-year minimums 3(f), insurance 3(g), averaging) into one object; verify none needs to be split out.
- **CAP-040** — Bundles several Article VII §4 Team-Salary exclusion subsections (expansion, assigned players, summer contracts, two-way, Exhibit 10, second-round) into one object; verify the bundling.
- **ROSTER-016** — The referenced two-way roster limit lives in Article X §4(d), which was outside this rule's source slice; the cross-reference was inferred from context and should be confirmed.
- **TRADE-031** — "Base Year Compensation" does not appear in the 2023 CBA text; the 2023 agreement appears to have dropped the label. The functional analogue is the §6(j)(5) deemed-/reduced-salary (≈50%) rule, captured separately. Confirm you want a BYC-named rule at all.
- **TRADE-038** — "Poison pill" likewise does not appear as a defined term; the offer-sheet salary-averaging mechanic in Article XI is its practical equivalent. Confirm whether a distinct poison-pill rule is needed.

## Articles / Exhibits NOT mined for rules (and why)

Mined for rules: Articles **I** (glossary), **II, VII, VIII, IX, XI, XII, XIII, XXIV, XLI**, and Exhibits **B, C** (scale amounts). Article **X** was consulted only for cross-referenced eligibility/roster limits.

Not mined (no transaction-eligibility content): Articles **III–VI** (player expenses, benefits, military duty, conduct), **XIV–XXIII/XXIII** procedural and welfare articles, **XV–XXII** (certifications, playing conditions, travel, union security, scheduling, all-star, health), **XXV** (deferred compensation — treated as cap-accounting already covered by VII §5; flag if you want it broken out), **XXVI–XXXII** (team rules, set-off, media, miscellaneous, no-strike, grievance/system arbitration), **XXXIII** (anti-drug), **XXXIV–XL, XLII** (recognition through expansion/other). Exhibits **A** (UPC form — the contract the rules operate on), **D, E, F, G*, H*, I-series, J-series** were not mined as rule sources (*Exhibits G/H are the offer-sheet and first-refusal forms; their mechanics are captured as free-agency rules). See `00_structure_map.md` for the complete list and please confirm the exclusions.

## Ambiguities and judgment calls

1. **Page-number basis.** Citations use the document's printed page numbers (what the TOC and external CBA references use), not the raw PDF sheet index. Offset is +24. Documented in `00_structure_map.md`.
2. **2023 terminology changes.** The 2023 CBA dropped the explicit "Base Year Compensation" and "poison pill" labels of prior CBAs. Rules that prior-CBA knowledge would expect under those names are captured under their 2023 mechanics and flagged (TRADE-031, TRADE-038) rather than invented.
3. **Traded Player Exception location.** The core TPE salary-matching/aggregation mechanics live in Article VII **§6(j)** (Exceptions), not §8 (Trade Rules). They are represented in both the `exceptions` and `trades` buckets and linked via `02_crossref.json`; this intentional overlap reflects the CBA's own structure.
4. **Apron vs. exceptions overlap.** Several rules (e.g., which exceptions a team above an apron may use, and which exception use triggers a hard cap) appear in both `exceptions` and `aprons_and_hard_caps`; the aprons bucket holds the restriction/trigger framing, the exceptions bucket holds the amount/mechanics. They are cross-linked.
5. **Bundled sub-rules.** CAP-033 and CAP-040 each consolidate several closely-related statutory subsections; flagged so you can decide whether to split them.
6. **Unresolved term references.** `02_crossref.json` lists 37 `depends_on_terms` strings (52 references) that do not match a glossary entry even after case/plural/alias normalization. All are generic phrases ("signing bonus", "death"), award names used in max-salary criteria ("All-NBA", "NBA MVP", "Defensive Player of the Year"), Exhibit-form names ("Exhibit 1", "Exhibit 9"), or out-of-scope accounting/arbitration terms ("Audit Report", "System Arbitrator", "Shortfall Amount"). These were deliberately left out of the transaction glossary; they are candidates for later addition if needed.

## Verification performed

- All 9 JSON files parse; all 234 rule objects carry the full 14-field schema with non-empty `citation.pages`.
- No duplicate `rule_id`s; **0** dangling `related_rule_ids` after repairing one (FA-023 had pointed at a non-existent `EXC-VFA`; repointed to EXC-002/003/004).
- Every rule's cited page was checked to fall within its cited Article's printed-page range — all consistent (the only two "out-of-range" hits were correct Exhibit B/C citations).
- A keyword-overlap scan against the source text on each cited page caught citation drift in the exceptions tail; **EXC-025** (Second Round Pick), **EXC-026** (Reinstatement), and **EXC-027** (Non-Aggregation) were corrected to their verified pages (246, 247, 247).
