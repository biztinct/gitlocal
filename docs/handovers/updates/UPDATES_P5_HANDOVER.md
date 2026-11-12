# UPDATES — Phase 5 handover: year-to-date figures (small version)

Start only after Phase 4 is live. Read first: `UPDATES_LEDGER.md` (all of it),
`UPDATES_P4_REPORT.md` and `UPDATES_P2D_REPORT.md` (the "new kind of sheet + store +
approval" pattern, and the two pay-run input seams), `UPDATES_P3B_REPORT.md` §R9 item 3.

**Design mandate (owner, verbatim): "extreme WOW, intuitive, out-of-this-world experience,
best in class".** Indigo design system (`#5A4BB0`), white cards, Lucide icons, never emoji.

**White-label rule:** the word "Odoo" never appears in any user-visible string. Technical
identifiers stay. **Plain words on screen**: "year-to-date figures", "before Payobook",
"paid in Payobook", "tax year".

First job: add to the ledger owner decision **D20** and the facts of §3 under the next free
numbers.

## 1. Owner decision D20 (2026-11-12) — do not re-ask

Year-to-date pay figures, **small version**: a fourth kind of sheet in Updates to load
approved opening figures (what a person was paid and taxed this tax year BEFORE the client
started on Payobook) for many people at once; they show on the employee's own tax summary
and are made ready for Rize Indonesia's December tax step so the five figures need not be
typed by hand. **No tax calculation is changed.** Upgrading any country's tax formula to
use year-to-date figures every month is NOT approved.

## 2. Scope

1. Store + sheet: "Year-to-date figures before Payobook" — same four steps, drafts,
   history, approval on the pay route, undo.
2. A per-person **year-to-date view**: before Payobook + paid in Payobook = total, per
   figure, with a download.
3. The employee's own tax summary includes the opening figures.
4. Delivery to a pay run **only** as designed in §4.4 — guarded, opt-in per pay scheme,
   and inert everywhere it is not switched on.

## 3. Verified facts (read-only study 2026-11-12; re-grep line numbers)

- No shipped tax formula in any country reads earlier payslips; every month is standalone.
  A formula cannot look anything up (fixed evaluation scope, `formula_program.py:99-117`,
  `formula_rule.py:2373-2386`; `env`/`search` refused, `excel_semantics.py:289-295`): a
  year-to-date figure can only arrive as an INPUT value.
- Existing year-to-date source: `history.ytd.<CODE>`
  (`pb_hr_payroll_formula/models/application_domain_sources.py:187-193,290-291`;
  `_application_history_value` `:476-518`): sums `formula_computed_values[CODE]` of DONE
  payslips of the same scheme from the later of 1 January and the joining date, needs an
  unbroken run of payslips, reports `posted_history_or_opening_balances_missing` when none
  (`:492-493`). Application-data runs only. **Silent zero**: joining date falls back to the
  contract start (`:481`); if `date_of_joining` is blank and the contract starts at
  go-live it answers a confident `0.0 zero_confirmed` (`:485-486`). No Python test covers it.
- Blueprint convention for a manual year-to-date input: `<CODE>YTD`
  (`pb_blueprint/models/recipe_compiler.py:443-446`, `recipe_schema.py:117-124,182`).
- Rize's Indonesia scheme does its final-period reconciliation from MANUAL inputs: BB
  (final-period flag), BC (taxable gross January to last month), BD (employee JHT+JP to
  date), BE (job-expense months), BF (PPh 21 already withheld), plus IDYTDREVIEW
  (`tools/prepare_rize_sg_id_master.py:134-136,150,193-196`,
  `tools/verify_rize_sg_id_payroll.py:60-67`) — from tool scripts, NOT verified on the live
  tenant. Verify read-only on `rize` before designing the mapping (§4.4).
- Tax year is hard-coded calendar year (`application_domain_sources.py:480`,
  `payroll_preparation.py:313`, `pb_me_portal/controllers/portal.py:471`). India's
  April–March is not modelled — out of scope; the sheet's tax year is the calendar year.
- Employee tax summary: `pb_me_portal/controllers/portal.py:450-495` (done payslips, year
  of the latest slip, codes from config, default `GROSS,SIEMP,HIEMP,UIEMP,PIT`,
  `models/hr_payslip_ess.py:16-43`).
- An "opening payslip" was rejected: it would be counted by the bank file, pay totals,
  analytics, contribution reports and previous-run comparisons. Use a separate store.
- The two input seams every non-application run passes through are already overridden by
  `pb_updates/models/updates_payrun.py` (P2d). Application-data runs certify their inputs
  (P2d report: not coverable without changing that certification).

## 4. Design

### 4.1 Store (`pb_updates`)

`pb.updates.ytd.line`: employee, company, `tax_year` (int), `figure` (key from the
catalogue below), amount (≥ 0; months as a whole number 0–12), `covers_to` (Date: the last
day the figures cover — the day before the client's first Payobook pay period), batch,
state (`waiting` / `set` / `replaced` / `undone`), evidence note (free text from the
sheet's optional "Source" column). Constraint (G1 style): one `set` row per employee +
tax year + figure. Access through model methods only; company record rule. The batch is
approved on the pay route (clone P2d/P4).

Figure catalogue (fixed keys, translated labels): gross pay · taxable pay · income tax
withheld · employee social contributions · employer social contributions · months
counted. A company may add more figures by naming a pay item of one of its schemes as a
figure (set-up on the Updates home, tenant admin or payroll manager): the figure's key is
then the pay item's code, so "paid in Payobook" can be summed for it.

Replacing: a later approved sheet replaces a `set` row (old → new shown in review); CLEAR
removes it; both refused once the figure has been USED by a finished pay run (§4.4), with
"… was used in pay run <name>. It can no longer be changed here."

### 4.2 The sheet

Start: fourth choice "Year-to-date figures before Payobook" with tax year (this year
default; last year allowed) and "Figures cover up to" date (required; inside that tax
year). Download: people × the company's figures, existing values pre-filled, "Read me"
explaining what "before Payobook" means and that nothing here changes how tax is
calculated. Match / Review / Apply / Done / drafts / Past updates as other kinds; cell
checks: not a number, negative, months not 0–12, person's joining date after "covers to"
(amber note: "joined after this date — are you sure?", allowed), already used in a pay
run (refused). Totals per figure.

### 4.3 The view and the tax summary

- Updates home → "Year-to-date figures" → a per-person table for a tax year: for each
  figure, **Before Payobook** (the stored line) + **Paid in Payobook** (sum over the
  person's DONE payslips in that tax year: for catalogue figures use the same codes the
  employee tax summary uses for the company, for pay-item figures the item's own code via
  `formula_computed_values`/lines — one grouped query, no per-person search) = **Total**.
  Gaps are shown, not hidden: a person with payslips missing between "covers to" and the
  latest slip gets an amber "months missing" chip. Download as a sheet (one row per
  person, three columns per figure).
- Employee tax summary (`pb_me_portal`): add the opening figures to the year's totals for
  the matching codes with one extra visible row "Before Payobook (up to <date>)". If
  `pb_me_portal` is being edited by another session or the change is larger than a small
  override from `pb_updates`, report instead of forcing it.

### 4.4 Delivery to a pay run — guarded

Nothing is delivered unless a payroll manager has, for a pay scheme, mapped an INPUT pay
item to a year-to-date figure on a small set-up screen ("This pay item receives: Total
taxable pay so far this year" / "Before Payobook only" / "months counted"…). No mapping →
the engine never sees these figures (test Y9: byte-identical runs on every mode).

With a mapping, for a non-application run, the P2d seams supply the mapped item's value =
the chosen basis (opening only, or opening + paid in Payobook up to the day before the
slip's period) — ONLY when no other source supplies that item; if the pay data file (or
the month's workbook) carries a number for it, D11's rule applies unchanged: stop and
ask, both amounts shown. The value and its two parts are recorded in the slip's input
sources. A figure used by a slip that becomes DONE is marked used (locks §4.1 changes);
released if that slip is cancelled/deleted.

Application-data runs: do not change their certification. Offer instead, on the
year-to-date view, **"Download for the pay run"**: a sheet with exactly the mapped input
items as columns and the computed values per person, ready to be loaded the way that run
already takes those inputs. Also fix nothing in `_application_history_value` — but DO
report the silent-zero case as a finding with a proposed fix and a failing test sketch.

Rize (read-only on the server): confirm the six Indonesia input items above exist on the
live scheme, how December's run will take them (which run mode Rize's real runs use), and
write in the report the exact mapping an administrator should set and which of the two
delivery routes applies. **Do not set the mapping, load figures or change anything on
`rize`.**

## 5. Non-goals and rails

- No tax formula, bracket table, country pack or scheme rule is changed. No new source
  key in the application-data catalogue. No "opening payslip".
- A run with no mapping, or no stored figures for its people, is byte-identical to before
  on every mode (capture before, compare after).
- Never touch `rize`/`sudima` data. Do not edit `pb_timeoff`, `pb_lifecycle`, `pb_hiring`,
  `pb_me_expense`, `docs/handovers/workflow2`.
- Everything shipped earlier keeps behaving as today.

## 6. Tests

| # | Case | Expect |
|---|---|---|
| Y1 | Sheet → review → approve → stored; replace; CLEAR; undo | as designed |
| Y2 | Bad cells (not a number, negative, months 13, covers-to outside the year) | refused with sentences |
| Y3 | Approval: approve / send back / turn down / cancel | rows follow the batch |
| Y4 | View: opening + paid = total for catalogue and pay-item figures; missing months chip | correct against hand-computed fixtures |
| Y5 | Employee tax summary | totals include opening; extra row shown; unchanged for people without opening figures |
| Y6 | Mapping set, no-file / pay-file / template run | mapped item receives the value once; sources record both parts |
| Y7 | File also carries the item with a different number | stop and ask (D11); equal → once |
| Y8 | Figure used by a finished slip → change refused; slip cancelled → released | as stated |
| Y9 | No mapping, or mapping but no figures: every run mode | byte-identical to before |
| Y10 | Application-data run with a mapping | nothing delivered; "Download for the pay run" gives the right values |
| Y11 | Earlier kinds (lasting changes, one-offs, new joiners, leave) | suites green; review 4,575 × 73 ≤ 25 s |
| Y12 | `.po` parse gate; "Odoo" scan | clean |

## 7. Browser validation, deploy, report

- Browser (local copy, console read at every step): the sheet end to end, the view and its
  download, the mapping set-up, a run receiving a mapped figure, the clash stop, the
  employee tax summary. Screenshots to `outputs/updates-p5/`.
- **Tier 3** on all five (`payobook`, `payobook_template`, `p0clone`, `rize`, `sudima`;
  never `abm`, `pbf_preview`, `recruit_connect_20261023`): deploy-notes START/DONE + flock;
  `pg_dump` ×5 first; rollback note before deploying; scoped rsync of only the modules you
  changed; cron snapshot with the id→active list; asset purge; no tests in the stopped
  window (G19); hashes and versions ×5; suites on live `p0clone` after start on free ports.
- Live check: writes only on a throwaway copy of `payobook` (jobs and mail servers off
  first, dropped afterwards). On live `payobook`, server-side as the QA user: download,
  review an unchanged sheet, save and discard a draft — nothing written. Look-only in the
  browser. Never sign in to a live site with a password.
- Commit per feature with explicit paths, credential scan, push `origin 19.1`.
- Report `UPDATES_P5_REPORT.md`: Y1–Y12 with output; the Rize Indonesia findings and the
  exact steps an administrator takes for December (plain enough to hand to the owner);
  the silent-zero finding; what was done for the employee tax summary; deploy evidence ×5;
  deviations; new gotchas; ledger updated.
