# SCHEMECTX — closeout

Opened and built 2026-09-19. Three owner findings on `rize.payobook.com`, three
Opus phases plus one small follow-up, all in one session. Live on all six
databases (`payobook`, `abm`, `payobook_template`, `rize`, `rztest`, `p9clone`).
Nothing pushed.

Read order for anyone picking this up: this file → `SCHEMECTX_LEDGER.md`
(rules + gotchas SC1…) → the three `SCHEMECTX_PHASE_n_REPORT.md`.

## What it delivered

| # | Owner's finding | What is true now |
|---|---|---|
| 1 | A scheme with country India paid in dong | The scheme's currency follows its country even when that currency is inactive (INR, IDR…) — never activated (rule 9). Stored rows healed by migration (`rize` 3939 VND→INR, `payobook` 577 VND→IDR). Pay run wizard, pay run, payslip statement, results, Explorer facts, contract drawer and pay run ledgers read the scheme's money first, the company's second. The journey's Country field says "Pays in ₹ INR" live. Symbol is always prefixed (SC3). |
| 2 | Every contract carried every scheme's components | The catalogue stays a flat list keyed by code; the SCHEME's rules decide scope (`hr.formula.config.component_scope_for_employee`, `pb_hr_payroll_formula/models/scheme_component_scope.py`). Drawer: scope strip (scheme · country), the scheme's components incl. virtual rows for codes with no stored line, valued strangers in a folded "Other values on this contract", empty strangers hidden, an unassigned empty state with a door to "Who is paid by what". The all-templates fan-out in `om_hr_payroll` `HrContract.create` is gone. Comp card scoped. Explorer country derives from the scheme; pay run results carry the scheme's country; AI insights group/filter by scheme and country and never sum two currencies. |
| 3 | Studio Settings was the old look | Settings opens the `pb_blueprint` journey in **edit mode** (`bp_adopt` → `mode=edit`), any scheme, Active included. Every `_CFG_FIELDS` member has a home (company stays the read-only chip). Locks: country once payslips exist; pay logic once not-draft or paid (BLUEPRINT ledger rule 8a) — and `bp_component_save` finally has that gate in create mode too. The old panel is removed; Set to draft / Retire / Simulate / Regenerate / Import from Excel moved into the studio; Intelligence became the "Health" tab. |

Pay neutrality was measured in Phases 1 and 2 on real data: 230 payslip lines,
before vs after, diff empty.

## Owner rulings — do not re-litigate

* Every Settings field lives in the journey; the old panel is retired.
* Out-of-scheme contract lines are hidden; a line holding a value is NEVER
  deleted or silently hidden.
* Clean-up of EMPTY out-of-scheme lines: **`rize` only** — done 2026-09-19,
  140 lines, 0 holding a value; dump `/odoo/backups/schemectx-p3/rize.dump`,
  undo file `/var/tmp/schemectx_cleanup_rize_20260919.csv`
  (`tools/schemectx_cleanup_contract_lines.py --restore`). `payobook` (117,058
  empty lines — its six sector schemes declare no contract components) and
  `p9clone` (7) deliberately left alone: the screens already hide them.
* The journey opens for Active schemes, with the locks above.
* Accepted deviations: scope = declared contract components PLUS any other rule
  of that scheme whose code the catalogue already carries (SC8); source lanes
  reorder by button + arrow key, not drag; the wizard takes the currency's
  symbol, not its position (SC3); the "no exchange rate" hint only shows for a
  company that actually consolidates (SC7).

## State of `rize` worth knowing

Engineering (7 people) is attached to **Rize India Payroll** (attached by the
owner on 2026-09-19, not by a builder). 96 people have no scheme yet and see the
unassigned state. `rize` has one company, no PayAI model configured, and no
fact rows carrying a scheme — so Explorer-by-scheme/country and the insights
question could not be SHOWN there; they are pinned by tests (Phase 2 `test_14`,
`test_15*`).

## Open

1. Push — the branch is ~40 commits ahead of `origin/19.1`.
2. PayAI on `rize`: no model configured, and its screen still uses emoji.
3. The hoot runner cannot execute on the server; JS assertions were run in node
   and the mounted halves clicked live (Phase 3 report §3).
4. Pre-existing reds on `rztest` are data-dependent (SC6) — baseline against a
   clean worktree before blaming a change.
5. A virtual-row save was not clicked on live data (would write a demo line for
   no reason); pinned by Phase 2 `test_05`.
