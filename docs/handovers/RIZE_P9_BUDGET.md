# RIZE P9 — pb_budget: budgets on the existing engine

Read FIRST: `docs/handovers/RIZE_LEDGER.md` (especially ruling D2) + phase-log P0–P8.
Design doc: `docs/design/rize-hrms-blueprint.html` §11 + §17 (wow: budget heat view).

## Scope
ONE new module `pb_budget` (depends: pb_hr_workforce_planning, pb_explorer, pb_import_kit):
1. Extend the CANONICAL budget object `wfp.budget.actual` (ruling D2) — no fifth budget
   model: budget_type (manpower / HR-ops / admin), upload lane, currency + manual rate.
2. Auto-actuals: monthly payroll actuals posted from the Explorer fact tables.
3. Scoped visibility: function heads / country HR / finance.
4. **Budget lens** on the Insights hub — budget vs actual + the WOW heat view.
5. Exports (XLSX + PDF).
6. Promote the presentation-currency helpers OUT of pb_demo (D2 second half).

### Binding NON-goals
- Do NOT build a new budget model; do NOT touch wfp.compensation.cycle /
  pb.workforce.demand.plan / hr.formula.budget / pb.schedule.budget beyond leaving them be.
- No payroll-side changes; actuals are READ from facts.

## Verified plumbing facts (do NOT re-derive)
- Canonical object: `wfp.budget.actual`
  (`pb_hr_workforce_planning/models/budget_tracking.py:12-54`) — department × month,
  forecast vs actual headcount + cost, variance. READ it fully; extend via `_inherit`
  (new fields live in pb_budget).
- Explorer facts: `pb.fact.run/.line/.emp` (`pb_explorer/models/pb_fact.py:50,109,150`);
  `pb_fact.py:128` names `code` as the anticipated budget join key; shipped lenses incl.
  `cost` (dept×month) at `pb_explorer/models/pb_explorer.py:145-179`. The actuals writer
  aggregates fact lines per department×month (which codes count as cost: follow what the
  existing `cost` lens counts — mirror its filter exactly, don't invent).
- Explorer has a build cron (`pb_explorer/views/pb_explorer_action.xml:14`) — run actuals
  AFTER facts refresh: either chain off the same cron via inherit or schedule later with
  an idempotent stamp.
- Presentation currency: `pb_demo/models/res_company.py:16-40`
  (`presentation_currency_id`, `convert_to_presentation`) — MOVE the capability: implement
  the same fields/helpers in pb_budget (or a tiny `pb_currency` inside pb_budget),
  keep pb_demo working by making its version defer if already defined (check field
  existence — cleanest: pb_budget defines nothing conflicting but USES pb_demo's if
  present, else defines its own. Since pb_demo IS installed on payobook, simplest safe
  move: depend on nothing, probe `presentation_currency_id` in `res.company._fields`,
  use it when present, else fall back to company currency + manual rate. Document the
  chosen approach — the ledger ruling wants the capability out of demo eventually; a
  full relocation would mean editing pb_demo: acceptable ONLY as an additive shim, no
  behaviour change for demo).
- Manual FX (requirement): per budget line `manual_rate` overrides the automatic
  conversion when set.
- Insights hub: find its lens mechanism (`pb_insights_hub`) — same drill as P7 did for
  pb_payhub; ONE minimal additive integration, documented. Palette 2900s.
- Scoping: "function" = top-level department (blueprint equivalence). Function heads:
  config-free — a `head_user_id` on the budget row? NO: use `hr.department.manager_id`
  (the department head's user) for function-head visibility; country HR = company scoping
  (allowed companies); finance = new group. Record rules on wfp.budget.actual must NOT
  break pb_hr_workforce_planning's own screens — scope NEW rules to the NEW group set
  (additive rules only widen/narrow for the new groups; existing wfp groups keep their
  behaviour).
- XLSX canon: `pb_hr_workforce_planning/wizards/export_wizard.py`; QWeb PDF canon per
  ledger.

## Architecture

### wfp.budget.actual extension (`models/budget_ext.py`, _inherit)
- `pb_budget_type` Selection `[('manpower','Manpower'),('hr_ops','HR operations'),
  ('admin','Admin')]` default manpower.
- `pb_currency_id` (default company currency), `pb_manual_rate` Float (0 = auto),
  `pb_report_amount_*` computed (budget/actual/variance in reporting currency).
- `pb_source` Selection `[('upload','Uploaded'),('auto','Auto actuals'),('manual','Manual')]`.
- Guard: pb_budget's rows are just rows of the same model — the lens filters nothing by
  module; existing wfp screens keep working (verify in tests).

### Upload lane
Wizard `pb.budget.upload.wizard`: download a template XLSX (function/department, month
columns for the FY, amount, type, currency) + upload filled → preview (rows to
create/update, unknown departments flagged, NEVER auto-create departments) → apply.
Idempotent: same file twice → updates, not duplicates (match dept×month×type).

### Auto-actuals
`pb.budget.actuals` service: for each month with facts, per department: actual cost =
mirror of the Explorer cost-lens aggregation; write onto matching manpower budget rows
(create actual-only rows for departments with spend but no budget — flagged "unbudgeted");
HR-ops/admin actuals stay manual/upload (payroll facts don't know them). Cron after the
Explorer build (idempotent month stamp). "Refresh actuals now" button on the lens.

### Expense entries (HR-ops/admin actuals)
Minimal `pb.budget.expense`: date, department_id optional, type (hr_ops/admin), vendor
Char (free text now; P11 may link later), amount + currency, note, attachment, company_id
— rolls into the actuals of its month×type. Simple native list+form + lens add-dialog.

### Visibility
- Groups: `group_budget_viewer` (sees per own scoping), `group_budget_manager`
  (upload/edit; implied viewer), `group_budget_finance` (read-all-in-allowed-companies,
  restricted screens per requirement).
- Record rules (NEW, additive, applied to the new groups only):
  viewer → rows of departments whose top-level parent's `manager_id.user_id` = user (the
  function head) OR rows they created; finance/manager → company-scoped all.
- The lens facade enforces the same scoping server-side.

### Budget lens (Insights hub, palette 2900s) — with the WOW heat view
Facade `pb.budget` get_board(fy, type): matrix departments × months {budget, actual,
variance, unbudgeted flags}; kpis (FY budget, spent, remaining, burn %, functions over
pace); toggles: type (manpower/HR-ops/admin), currency (local/reporting).
Views inside the lens:
- **Heat view (the wow)**: functions as tiles coloured by burn-vs-pace (calm sea-to-amber
  -to-rose scale from kit tokens; colour-blind safe — pair colour with a % label), tile
  click → that function's month bars + its expense/actual drill rows. One glance = who's
  burning fast. CSS transitions, reduced-motion respected.
- **Table view**: the matrix with variance chips; row expand → months.
- Export buttons: XLSX (matrix) + PDF (summary per function, month bars, variance
  narrative lines in plain English: "Marketing is 12% ahead of budget pace").
- "Upload budget", "Add expense", "Refresh actuals" actions per group.

## Safety rails
- NEVER modify existing wfp rows' meaning: new fields default so old rows read as
  manpower/auto with no behaviour change; wfp module's own tests/screens must stay green.
- Actuals writer only writes rows it owns (pb_source='auto') — never overwrites uploaded
  budget figures (budget vs actual are separate columns on the model anyway — verify
  which columns the model uses for each and document).
- FX: reporting conversions computed, never stored destructively; manual rate is
  row-local.
- Deploy `-i pb_budget -u pb_hr_workforce_planning` (inherit fields) — wfp is versioned;
  bump nothing in it (fields live in pb_budget's inherit, `-u` needed only if you add
  data/views into wfp — DON'T; keep all files inside pb_budget, then only `-i pb_budget`
  + `-u` nothing. Confirm inherit-only field addition installs cleanly with plain -i).
- Use demo world data for actuals validation (its formula runs have categorised lines).

## Numbered test cases
T1. Deploy clean; wfp screens (compensation cycles, budget tracking) unchanged.
T2. Template download → fill 2 functions × 3 months (manpower) + 1 HR-ops row → upload
    preview correct (1 unknown dept flagged) → apply; re-upload same file → updates not
    dupes.
T3. Refresh actuals (demo facts) → department actuals match the Explorer cost lens for
    the same month (spot-check one number EXACTLY); unbudgeted dept flagged.
T4. Expense: add an admin expense → month's admin actuals include it.
T5. Heat view: tiles coloured by burn-vs-pace, labels present, click-through drill works;
    reduced-motion honoured; light+dark screenshots (this is the wow — make it
    screenshot-proud).
T6. Currency: budget row in VND with manual rate → reporting figures use the manual
    rate; without → automatic conversion (or company-currency fallback, per the probe
    decision) — show both.
T7. Scoping: function-head test user (manager of dept A) sees ONLY dept A tree in lens +
    rules (probe another dept row by id → denied); finance group sees all; a plain user
    sees nothing.
T8. Exports: XLSX matrix opens; PDF renders with plain-English variance lines.
T9. Idempotent cron: run actuals twice → no dupes; month stamp honoured.
T10. White-label grep zero; plain English everywhere.
T11. Regressions: Insights hub Explorer lens fine; P0–P8 lenses load.
T12. Clean up test rows; report the exact columns used for budget vs actual and the
    Explorer-mirror filter, for the owner report.

## Deliverables / report back
Commits, per-test results, deploy EXIT, deviations, gotchas, the scoping model as built,
presentation-currency approach chosen (probe vs shim), lens integration mechanism on
Insights hub, palette ids.
