# GROUP Phase 6a — "Pay, part one": Pay Bands and Fairness

Read `docs/handovers/GROUP_LEDGER.md` FIRST and fully (rules, rulings G1–G9 — **G9** is
this phase's charter — plumbing "Legacy module", gotchas GR1–GR38; GR38: the kit has no
dark palette, so report "dark" only as platform chrome; GR24/WF15: temporary validators),
then the P1–P5 phase-log entries, then Part G of `docs/design/group-blueprint.html`
(Pay Bands and Fairness screens, "Where the old pieces went", "What is kept from the old
data") and Part A "Planning and pay reviews", then the legacy inventory in
`docs/design/one-group-many-payrolls.html` (Question 1 table + engineer fold).

## 0. What you are building, in one paragraph

The first half of the **Pay** area, rebuilt from first principles rather than ported
(owner ruling G9): a new module `pb_pay` with a **Pay** lens on the People hub carrying
two tabs now (Bands, Fairness) and two more in 6b (Review, Changes). **Pay Bands** are
salary ranges per country and currency, per job family and level, with history; every
open contract gets a band and a position in it, computed and kept current; the screen
draws each band as a range with every person as a dot, lights up outliers when you drag a
band's edge, surfaces health cards you never had to look for (below band, above band,
compression, inversion, spread), and offers "Place a new hire". **Fairness** computes,
from what payroll actually paid, the pay gap by gender, level and division, the spread
within the same job, and the people paid least for the same work, with a plain sentence
per number and a one-page statement to print. The old Pay Grades migrate into bands and
the old band figures on contracts are recomputed; the old module stays installed until 6b.

## 1. Scope and binding non-goals

Deliverables:
1. `pb_pay` 19.0.1.0.0: models (`pb.pay.family`, `pb.pay.band`, `pb.pay.band.job`,
   `pb.pay.position`), fairness facade, the Pay lens (People hub, key `pay`, seq 45) with
   Bands and Fairness tabs, band import/export, place-a-new-hire, the printed fairness
   statement, ⌘K rows 3400–3420, migration from `wfp.pay.grade` + contract `grade_id`,
   tests, `vi_VN.po`.
2. `pb_contracts` bump: the contract screens read band + position from `pb.pay.position`
   (where they read `wfp.pay.grade`/`compa_ratio` today, `pb_contract_360.py:50`).
3. Deployed p9clone → payobook → abm → payobook_template; Chrome walks; commits; ledger;
   report.

Non-goals (do NOT build):
- No Pay Review, guidance grid, approvals, apply-to-contract, letters, Pay changes (6b).
- No uninstall of `pb_hr_workforce_planning`, no `pb_budget` re-home (6b). Do not edit
  the legacy module.
- No writes to `hr.contract.wage`. No accounting. No stored converted amounts.
- No new `pb.sidebar.item`.

## 2. Design (the bar, the hero, the copy)

**The bar (owner's words, verbatim): "extreme WOW, intuitive, out-of-this-world
experience, best in class."** Hero: **the band picture.** Each band is a horizontal range
on a shared money axis; every person in it is a dot placed by their pay; drag the band's
left or right edge and the dots that fall outside light up rose with a running "₫184M a
year to bring 7 people back in"; release to save, undo to put it back. Hover a dot: name,
job, pay, position ("62% through the band"). Second hero: **one honest number per
question** on Fairness — "Women in Bread earn 3.6% less than men in the same jobs" with
the population it was measured on, the method in one sentence, and "show me the people"
for those allowed. Benchmarks: Pave, Ravio, Figures, Lattice.

Copy: "Pay bands", "Band", "Job family", "Level", "Position in band", "Below band" /
"Above band", "Compression" (explained: "newer people paid more than long-serving people
in the same job"), "Inversion" ("a manager paid less than someone who reports to them"),
"Spread", "Place a new hire", "Fairness", "Pay gap", "Same job, different pay". Never
"compa-ratio", "range penetration", "grade" on screen. Zero dead-ends (§8). Keyboard:
band edges nudge with arrows; dots are focusable; Esc closes drawers (WF4).

## 3. Server design

### 3.1 Models
- `pb.pay.family`: `name`, `code`, `sequence`, `active` (job families: Operations, Sales,
  Engineering…; a bootstrap suggests families from `hr.job` names).
- `pb.pay.band`: `name` (computed "<family> L<level> · <country>"), `family_id`,
  `level` (1–12), `country_code` (Selection as the engine's), `currency_id` (from
  country, editable), `min_amount`, `mid_amount`, `max_amount` (Monetary, monthly),
  `date_from` (required), `date_to`, `company_ids` (optional restriction), `active`,
  `note`; `mail.thread` tracking on the three amounts. Constraints: min ≤ mid ≤ max; no
  two active bands for the same (family, level, country) overlapping in time.
- `pb.pay.band.job`: `band_id`, `job_id` (`hr.job`), `company_id` (related), unique per
  job per date range (a job belongs to one band at a time).
- `pb.pay.position` (stored, one row per open contract): `employee_id`, `contract_id`,
  `person_id` (`pb.person`), `company_id`, `job_id`, `band_id`, `wage`, `currency_id`,
  `position_pct` = (wage − min)/(max − min) × 100 (may be < 0 or > 100),
  `compa` = wage/mid, `state` Selection below|in|above|no_band, `as_of`. Recomputed by
  a nightly cron, on band/job-link/contract writes, and by a "Recompute" button; one SQL
  pass for 4.5k contracts (< 2 s).
- `hr.contract` gets related read-only fields `pb_band_id`, `pb_position_pct`,
  `pb_band_state` (from the position row) — the fields `pb_contracts` will read.

### 3.2 Facade `pb.pay.bands`
`get_board(company_ids, family, country)` → bands with their people dots (id, name, job,
wage, position; capped at 400 dots per band, "and N more"), health cards (below, above,
compression, inversion, spread) with counts and the top rows, families, countries;
`move_edge(band_id, side, amount, dry_run)` → cost to bring outliers in + the outliers;
`place_hire(job_id, level, experience_pct)` → band, median of current people, dots,
suggested offer (mid, nudged ±10% by the experience slider), the sentence;
`import_bands(file)` with a preview (family, level, country, min/mid/max per row; errors
per row), `export_bands()`; `suggest_families()`.
Definitions (state them in the UI's "How this is measured" fold): compression = a person
with < 12 months tenure paid above the median of people with ≥ 36 months in the same job
and company; inversion = a manager (`hr.employee.parent_id` chain) paid less than a direct
report in the same currency; spread = max/min within a band per company.

### 3.3 Facade `pb.pay.fairness`
Inputs: the last closed main-run month from `pb.fact.emp` (basis gross or basic, pick
basic pay; if facts are absent for a company use open contract wages and say so) joined
to `hr.version` for `sex` (Odoo 19 field name), level (from the band), division (from
facts `division_id`), job. Outputs per scope (group/company/division): `gap_gender`
(median-based, per job level, weighted; "not enough people" below 5 per side),
`gap_by_level[]`, `gap_by_division[]`, `same_job_spread[]` (job, min, median, max, people),
`lowest_for_same_work[]` (people ≥ 15% under the job median; names only for allowed
readers, else counts), a plain sentence per number, and `method` sentences. Never
stored. `print_statement(scope)` → self-contained HTML like the decision brief.
Currency: within one company only; cross-company comparisons only when the currency is
the same or in group mode through `pb.fx` with the P3 badge and refusal.

### 3.4 Migration (post-migrate, idempotent)
`wfp.pay.grade` → `pb.pay.band` (family "Migrated", level = `grade_level`, country from
`country_code`, min/mid/max from range fields, `date_from` = today, note "migrated from
Pay Grades"); `hr.contract.grade_id` → `pb.pay.band.job` links per job where consistent,
else a note listing the conflicts; positions recomputed. Legacy records untouched.

### 3.5 Security
`pb_pay.group_pay_viewer` (implied by `hr.group_hr_manager`): boards without names on
Fairness ("show me the people" hidden); `pb_pay.group_pay_manager` (implied by
`base.group_system`): everything, edits bands, sees names. Company rules on band jobs and
positions.

## 4. Client design
- Pay lens (`pb_pay/static/src/js/pay_hub.js`, registered into `PEOPLE_LENSES` seq 45
  with `groups` = the two groups): a small tab strip Bands · Fairness (Review · Changes
  greyed with "coming next" in 6a).
- **Bands tab**: filters (country, family, company); the band picture (SVG on a shared
  axis in the chosen currency; bands stacked by family/level; dots with jitter; hover
  card; drag handles on edges with the running cost; keyboard nudge); health cards row
  (each opens a drawer listing people with a "Fix in a review" note pointing to 6b);
  "Place a new hire" drawer (job → level → experience slider → suggested offer → copy);
  Import/Export buttons (import preview drawer).
- **Fairness tab**: scope chip (group/company/division, reusing P4's picker component if
  exportable, else a simple select); the headline sentence; cards: gap by gender, by
  level, by division; same-job spread table; lowest-for-same-work list (names gated);
  "How this is measured" fold; "Print the statement" button.
- Contract screens (`pb_contracts`): the band chip and position bar replace the legacy
  grade fields.
- ⌘K: 3400 "Pay bands", 3410 "Fairness", 3420 "Place a new hire".

## 5. Tests (p9clone; numbered)
- T1 band constraints (min ≤ mid ≤ max; overlap per family/level/country refused with the
  sentence); a job in one band at a time.
- T2 positions: one row per open contract; `position_pct`/`compa`/`state` correct on a
  fixture; recompute in one pass < 2 s for company 5; cron and triggers.
- T3 health cards: compression, inversion, spread on fixtures with known answers.
- T4 `move_edge` dry-run cost equals Σ(new edge − wage) over outliers; nothing written on
  dry run; written on commit; undo restores.
- T5 `place_hire` returns band, median, suggested offer within [min, max]; a job without a
  band explains.
- T6 import preview flags bad rows and imports good ones; export round-trips.
- T7 fairness: gender gap median-based per level; "not enough people" below 5; same-job
  spread; lowest-for-same-work threshold; names hidden for viewers; method sentences
  present; nothing stored.
- T8 cross-company fairness refuses mixed currencies without group mode; group mode uses
  `pb.fx` and reports unknown rates.
- T9 migration: `wfp.pay.grade` rows become bands; contract links carried where
  consistent; legacy untouched (`git diff --quiet -- pb_hr_workforce_planning`).
- T10 `pb_contracts` reads the new fields; the legacy fields are no longer referenced by
  it (grep test).
- T11 no "Odoo"; static contract; palette 3400–3420; lens registered seq 45 with a palette
  row; `vi_VN.po` complete for new strings.
- T12 earlier suites green (same p9clone drift set).
Browser (payobook + abm via temporary validators; 1440 + 390; Vietnamese user;
`docs/handovers/group_p6a_shots/`):
- B1 Pay lens → Bands: picture with dots for company 5 (families suggested from jobs,
  bands created from the migrated grades or by import); hover; drag an edge → rose dots +
  cost → release → undo.
- B2 Health cards: open each drawer; counts match the tab.
- B3 Place a new hire: Assembly operator L2 → suggested offer; copy.
- B4 Import a small spreadsheet with one bad row → preview → import.
- B5 Fairness on company 5: headline sentence, three cards, spread table, lowest list
  (names as manager, counts as viewer), print statement.
- B6 Contract 360 shows the band chip and position bar.
- B7 abm: bands empty state with the import/suggest path; fairness with its 153 people.
- B8 390 px; ⌘K rows; B9 Vietnamese user.

## 6. Build order
1. Models + positions + migration + T1–T2, T9 on p9clone.
2. Bands facade + health + place-hire + import + T3–T6.
3. Fairness facade + statement + T7–T8.
4. Lens + two tabs + contracts bump + T10–T12; Chrome walks.
5. Deploy ritual (backups) to all DBs; verify; commits; ledger (GR39+); report.

## 7. Report back (plain-English first)
1. Three sentences: what a band is on screen, what the health cards found on the Vietnam
   company, what Fairness said.
2. T1–T12 / B1–B9 table with evidence; position recompute timing.
3. Deploy evidence per DB; migration counts (grades → bands, links carried/conflicts).
4. Deviations; new gotchas; phase log updated.
5. Self-score against the bar and the one thing to improve first.
6. Commit list.

## 8. States (zero dead-ends)
No bands yet (teach + "Suggest families from your jobs" + import) · a job with no band
(dot in an "Unbanded" lane + link) · a band with nobody in it (range drawn, "no one yet") ·
mixed currencies in one view (per-currency lanes; group mode via the chip) · fewer than 5
people on a side (gap says "not enough people to compare fairly") · no facts for a company
(fairness from contracts; sentence) · viewer without names · import with errors · drag
beyond another band (allowed, warned) · Vietnamese user.
