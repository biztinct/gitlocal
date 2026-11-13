# RUNSRC — closeout

**Complete 2026-09-18.** Four Opus phases, one session, all live on six
databases. Read this first; the ledger (`RUNSRC_LEDGER.md`, RS1–RS27) carries
the gotchas and the four handovers carry the designs.

## What the owner asked for

1. *"During mapping components it is showing A, B, C etc components for Rize
   Vietnam Payroll configuration — why is that, can you fix it."*
2. *"Do I have to map the primary column e.g. Employee code in spreadsheet
   mapping as well as other mappings like Employee and Contract etc, and also
   API if that is also enabled?"*
3. *"How to map fields like Start and End date of payslip, Standard working
   days etc from the payrun wizard when it runs, and also make that editable in
   wizard (e.g. standard working days so user can change that to account for
   holidays). Can you show mapping for that as well and use these payrun wizard
   fields in transformation for something which payroll might require."*

## What shipped

| Phase | Commit | What |
|---|---|---|
| A | `cca703489` | One card per real spreadsheet column; no invented 85% suggestions |
| B | `81369ce7d` | The run answers six things about its own period; standard working days editable on the run, the load and the guided wizard |
| C | `20c93d231` | "From this pay run" lane on the mapping board — a wire anybody can draw; the source vocabulary unified |
| D | `d89d39bfa` | The run's numbers inside Transformations, in all three authoring lanes; an unpaid-leave rule; Vietnamese |

**9 commits unpushed on branch 19.1.** Nothing has been pushed.

Deployed and verified 2026-09-18 on `payobook`, `abm`, `payobook_template`,
`rize`, `rztest`, `p9clone` — `pb_hr_payroll_formula 19.0.1.140.0`,
`pb_formula_studio 19.0.1.195.0`, `pb_contracts 19.0.1.6.0`,
`pb_integrations 19.0.1.14.0`, `pb_blueprint 19.0.1.9.6`. Module trees
byte-identical repo↔server. payobook.com and rize.payobook.com both 200.

### The answer to question 2, for the record

The identity column is mapped **once**, in **Employee & contract**, and only
when its heading is not one the built-in list already recognises
(`employee_code`, `employee code`, `emp_code`, `emp code`, `emp. code`,
`empcode`, …). The Spreadsheet → Scheme board feeds **pay values only** —
declaring the identity column there is optional and changes nothing. The API
path uses its own recognised-key list plus the same one mapping override.
Identity is deliberately never resolved by column letter. Ledger §1.6.

## Numbers

* Mapping board, live Rize Vietnam board: **18 cards → 9**, **10 suggestion
  wires → 1**, **9 bogus 85% matches → 0**.
* Pay neutrality, measured three times independently: Phase A 39 payslips /
  697 lines byte-identical; Phase B 230 lines, 0 moved; Phase C 85 real
  payslips across five databases, byte-identical. **No pay value moved
  anywhere as a result of this programme.**
* Standard working days: August 2026 = 21 (the 1st is a Saturday),
  September 2026 = 22. Zoho's own `expectedWorkingDays` independently agrees
  with 21 for August.
* Tests: A 12/12, B 16/16 (25 incl. inherited), C 16/16, D 14/14. Suites
  +24 new tests, 0 regressions.

## The safety property that made this deployable

Every phase was **pay-neutral until a person acts**. The run sits last in the
source order, below the contract component: it fills a blank and never
overrides a stated source. A scheme whose file carries a "Standard working
days" column keeps reading the file even after somebody draws the pay-run
wire. Nothing changed on any customer's numbers on deploy day.

## Owner decisions taken during the programme

* **Standard working days defaults to the Mon–Fri count of the period** — not a
  holiday-calendar subtraction (only as good as a list nobody maintains), not a
  per-scheme constant. Adjusted by hand on the run.
* **A transformation must never read a different standard-working-days number
  than the payslip beside it.** It resolves run → load → default, and the
  tester states which it used and why.
* **`DATE_COMPARE_TO` was NOT widened** — the six run values are numbers, not
  dates, and the guided lane is the worst place to put a type lie.
* **The pay run got a sixth contract-drawer bucket** ("From this pay run",
  amber) rather than being squeezed into one of the five existing sentences,
  each of which would have sent a reader somewhere wrong.

## Open items — nothing later catches these

1. **`pb_integrations.TestLedgers.test_the_ledgers_never_sudo` is RED and has
   been since SOURCING S5 (`4f3c317e8`).** `pb_integrations/models/pb_integrations.py`
   has seven `sudo(` calls; the test asserts none. Untouched by this programme.
   **Somebody must decide** whether the sudos are right and the test is stale,
   or the reverse. Until then that module's suite is not green.
2. **~40 untranslated strings in the contract drawer's JS, plus 1 in
   `pb_blueprint`.** Pre-existing; `contract_360.js` dialogs, toasts and the
   terminate flow are still English on a Vietnamese screen.
3. **Three stray tracked files in `pb_hr_payroll_formula/i18n/`** —
   `vi_VNnew`, `vi_VNnew2.po`, `vi_VNorig`, left from a September translation
   session. Odoo ignores them (the basename is not a language code) but
   `vi_VNnew2.po` parses as 2,010 rows and will mislead the next translation
   audit. Safe to delete; not deleted, because removing tracked files is the
   owner's call.
4. **The contract-drawer chip was never photographed.** Proven by two tests on
   all six databases, but no component on `rize` or `rztest` has the pay run as
   its *only* source, and manufacturing one meant mutating a customer clone.
5. **No whole-module test run of `pb_hr_payroll_formula`** — RS10: its 540
   tests OOM-kill the 1.9 GB box, which is serving live tenants. 26 classes
   (360 tests) were run, chosen for blast radius.
6. **The push decision.** 9 commits sit local on 19.1.

## The two things this programme should be remembered for

**RS13 — the source vocabulary lived in four places, not one.** The server
knew "Pay period"; three JavaScript files each kept a private copy, and two of
them rendered *nothing at all* for a kind they did not recognise. Found by
opening a browser one minute after 31 green server-side tests. A green suite is
not a done screen, and any new source kind must be added in all four homes.

**RS12 — two agents deploying to one box will collide.** Phases A and B ran
concurrently; one's files sat ahead of two databases' schema for part of the
window and its deploy stopped the live service for minutes. Both recovered, but
Phase A's closing warning about `abm` and `payobook_template` was already stale
when written — and was only caught because the live box was checked rather than
believed. **Phases that share a server run one at a time.**
