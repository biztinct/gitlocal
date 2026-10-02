# ACCESS P7 — The three packaging faults (a fresh database must install)

Read FIRST: `docs/handovers/ACCESS_CLOSEOUT.md` debt **D3**, and `ACCESS_PROGRAM.md`'s ledger
(A1-F6 bind — especially **F6: never run `odoo-bin --test-enable` without `--http-port`**, it
stole port 8069 and served 500s to the live site for 14 minutes).

Owner approved 2026-09-02: fix all three. The goal is concrete and testable: **`-i base,<the
Payobook set>` on an EMPTY database must complete**, because that is what reusing `biz_access`
in the owner's other application requires.

Design bar (verbatim, binding): **extreme WOW, intuitive, out-of-this-world, best in class**.
White-label rule: "Odoo" never in a user-visible string; plain English in anything a user reads.

## The three faults — verified locations (do not re-derive)

### Fault 1 — `hr_contract` real data points at a demo-only record
`hr_contract/__manifest__.py`: `data` includes `data/hr_contract_data.xml`; `demo` is
`data/hr_contract_demo.xml`. Something in the always-loaded data file (or another always-loaded
file in that module) resolves only when demo data is present. **Find the exact offending
`ref=`/`eval` by installing `hr_contract` on an empty DB WITHOUT `--without-demo=False`
semantics confusion — i.e. reproduce it first, capture the real error, then fix.** Report the
precise file:line.
Fix direction: move the offending record into the demo file, or make the always-loaded data
self-sufficient (create what it needs, or drop the reference). Never make real data depend on
demo data — that is the actual rule being broken.

### Fault 2 — `om_hr_payroll` uses `report_xlsx` without declaring it
- `om_hr_payroll/models/hr_payslip.py:1762` — `_inherit = ['report.report_xlsx.abstract']`
  (and a commented import at :25).
- `om_hr_payroll/__manifest__.py` depends = `['mail','hr_contract','hr_holidays','web_notify','account']`
  — **no `report_xlsx`**.
- ⚠ **AND A LIVE INCONSISTENCY TO FIX**: `report_xlsx` is PRESENT in this repo, marked
  `installed` in the `payobook` database, but **ABSENT from `/odoo/odoo-server/addons` on the
  server**. Establish what is actually true (is the model loading? is the payslip spreadsheet
  report broken on live right now? check the model exists in the registry and try the report),
  then make disk, database and manifest agree. If the module belongs on the server, deploy it
  per the CLAUDE.md contract; if it does not, the dependency must be removed and the inheriting
  class made conditional instead. **Decide on evidence and say which you chose and why.**

### Fault 3 — `om_hr_payroll` ↔ `pb_hr_flow` dependency loop
`om_hr_payroll/views/hr_contract_views.xml:14` — the root Payroll `menuitem` sets
`action="pb_hr_flow.action_hr_flow_wizard"`, but `pb_hr_flow/__manifest__.py` depends on
`om_hr_payroll`. A base module referencing a downstream module's action = unresolvable on a
fresh install. (Note line 8: an `action_internal_user_portal` version is commented out — the
module's own action.)
Fix direction (recommended): make `om_hr_payroll`'s menuitem **self-sufficient** (its own action,
or no action), and have **`pb_hr_flow` re-point that same menu to its wizard** from its own data
file. Live behaviour is preserved exactly where pb_hr_flow is installed, and the cycle is gone.
Note the native menus are CSS-hidden on this product (the rail is the real navigation), so the
user-visible risk is low — but do not change what an installed system does.

## Binding NON-goals

- Do NOT redesign menus, the rail, or navigation. Do NOT touch the Access home.
- Do NOT "fix" other modules' unrelated install failures beyond these three — if a fourth
  blocker appears on the empty-DB run, REPORT it with its error; only fix it if it is a
  one-line sibling of these three, and say so.
- No new features. No Cybrosys resurrection (it is gone). Do not push.

## Numbered test cases

1. **Reproduce first**: on a scratch database, capture the exact failing error for each of the
   three faults BEFORE fixing (paste the real messages in your report).
2. Empty-DB install of `hr_contract` alone succeeds (fault 1 closed).
3. Empty-DB install of `om_hr_payroll` alone succeeds (faults 2+3 closed).
4. **The headline test**: a brand-new empty database installs the Payobook set end to end
   (at minimum: `om_hr_payroll, pb_hr_payroll_base, pb_hr_payroll_formula, pb_sidebar,
   pb_settings, pb_hub, biz_theme, biz_access`) and boots. Screenshot the running Access home
   on that fresh database (this is the reuse proof the owner asked for).
5. `biz_access` alone on an empty DB still installs (P6's proof must not regress).
6. Live regression: `payobook` and `abm` upgrade cleanly with the changed modules; the payslip
   spreadsheet report works (or is proven to have already been broken — say which); the Payroll
   menu still opens what it opened before on payobook.
7. Full suites green on payobook (compare failure COUNT against the closeout's known set —
   pb_learn template drift is pre-existing).
8. Copy audit on anything user-visible you touched.

## Deploy + verify

Repo CLAUDE.md contract is authoritative (single addons dir; per-module scoped
`rsync --delete`; **NEVER** `--delete` with the addons root as destination). Upgrade the
affected DBs; asset ritual (purge + bump `web.assets.version`) only if assets changed.
⚠ **F6: any `odoo-bin` run must pass `--http-port` to a free port (or `--no-http`)** — never
let a test/shell run take 8069. Drop every scratch/clone database promptly (ledger A8).

## Report back

1. The exact file:line and real error message for each of the three faults, before and after.
2. The `report_xlsx` decision (deploy it vs remove the dependency) with the evidence behind it,
   and whether the payslip spreadsheet report was already broken on live.
3. The fresh-database install proof: module list, exit code, and the Access home screenshot.
4. Any fourth blocker found (reported, not silently fixed).
5. Live regression evidence + deploy verification per DB.
6. Commits (feature-scoped, module files only, Claude co-author line, **not pushed**).
