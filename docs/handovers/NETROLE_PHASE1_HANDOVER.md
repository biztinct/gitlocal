# NETROLE Phase 1 — a component's category comes from what NET pay does with it

Program: NETROLE (auto-categorise Earning/Deduction from formula usage).
Phase 1 of ~4. This phase is **engine + ABM repair only**. Read
`docs/FORMULA_ENGINE_CONVENTIONS.md` first (esp. C1, C2, C5, C7, C9, C10).

## Why (the defect this replaces)

`hr.payroll.import.batch._get_default_category`
([payroll_import_batch.py:3498](../../pb_hr_payroll_formula/models/payroll_import_batch.py#L3498))
categorises a component by **substring match on its code**: `'SI' in code → DED`,
`'TAX' in code → DED`. So on ABM (`abm` DB, scheme id 14, 99 rules, ALL with
`category_id = NULL` — verified by SQL 2026-08-27):

- `ACTUBASISALA` (actual basic salary, an **earning**) → DED (contains "SI")
- `TAXABLEINCOM`, `TAXAINCOAFTE` (tax **bases**) → DED (contain "TAX")
- `SALARYFORSI` (SI **base**, ₫1.9bn) → DED
- `SIHIUITOT215` (EMPLOYER 21.5% contribution, ₫408.5m) → DED

Result on the live June run (run id 13): **Deductions ₫5,058,029,390 against
gross ₫1.9bn**. The only real employee deduction is ₫199,500,000.

The truth is already in the scheme: `NETPAY = BP5-CD5+CC5`. Whatever is
subtracted on the way to net pay is a deduction; whatever is added is an
earning; whatever never reaches net pay is information or employer cost.
This phase builds that derivation.

## Verified plumbing facts — do NOT re-derive

- Rule model `hr.formula.rule` in
  [formula_rule.py](../../pb_hr_payroll_formula/models/formula_rule.py):
  `category_id` (m2o `hr.salary.rule.category`, ~line 100), `code`,
  `column_letter`, `column_type` in {input, formula, constant} (~line 115),
  `excel_formula`, `sequence`, `appears_on_payslip`, `salary_rule_id`,
  `config_id`. Helpers you MUST reuse: `_normalize_excel_formula` (strips
  `$`/row numbers, line 444), `_strip_string_literals` (line 451),
  `_compute_dependencies` (line ~1418) — note it expands
  `BRACKET(table, expr)` via `hr.formula.rate.table.expand_brackets(formula, config)`
  BEFORE extracting refs; your parser must do the same.
- **Formulas reference column letters with row numbers** and **ranges**:
  real ABM shapes are `=BP5-CD5+CC5`, `=SUM(AE5:AX5)+BM5`, `=SUM(BS5:BU5)`,
  `=ROUND(U5/AB5*AC5,0)`. A range `AE5:AX5` must expand to every rule of the
  config whose `column_letter` falls in the span (compare by
  `openpyxl.utils.column_index_from_string`; openpyxl is already a manifest dep).
- Payslip lines carry the category **copied at creation**, in TWO producers:
  batch path [payroll_import_batch.py:3440-3470](../../pb_hr_payroll_formula/models/payroll_import_batch.py#L3440)
  (falls back to `_get_default_category`) and batchless path
  [hr_payslip_formula.py:~510-560](../../pb_hr_payroll_formula/models/hr_payslip_formula.py#L510)
  (`_create_payslip_lines_from_formulas`, uses `rule.category_id` only).
  `hr_payslip_line.category_id` is **NOT NULL** in SQL — every payslip-visible
  rule must end up with a category.
- Salary-rule shadow records: `_get_or_create_salary_rule`
  ([payroll_import_batch.py:3540+](../../pb_hr_payroll_formula/models/payroll_import_batch.py#L3540))
  creates/links `hr.salary.rule` per code; ABM's existing salary rules carry the
  WRONG categories (that's where June's line categories came from). A repair
  must update rule, linked salary rule, AND existing lines.
- KPI band: [pb_payruns/models/hr_payslip_run.py:157-181](../../pb_payruns/models/hr_payslip_run.py#L157)
  `_compute_pb_totals` — raw SQL sum by category code over
  `('NET','GROSS','DED','DEDUCTION','COMP','BASIC','ALW')`; net = NET;
  gross = GROSS else BASIC+ALW; deductions = |DED+DEDUCTION+COMP|.
  It already `flush_model`s before reading (don't remove that).
- `hr_salary_rule_category` rows on abm (global, has duplicates): BASIC(1,13),
  ALW(2,14), GROSS(3), DED(4,15), NET(5), COMP(6), TAX(16), OTH(23) + others.
  Match by `code` (any row with the right code satisfies the KPI SQL); pick
  `search([('code','=',X)], limit=1)` deterministically.
- ABM June ground truth (run 13, live): NET total 727,655,630;
  `ACTUTOTAINCO` sums to 927,155,630; `TOTALDEDUCTI` = 199,500,000;
  `SIHIUITOT215` (employer) = 408,500,000; `NETPAY = BP−CD+CC` where
  BP=ACTUTOTAINCO, CD=TOTALDEDUCTI, CC=MARSHINSREFU-or-similar (verify CC's
  code on the server, don't guess). `TOTACOSTTOER = CE+CI+CJ` (references
  NETPAY + employer contributions) — the employer-cost cluster.
- Tests run on `payobook_template` per C10. Test-run script pattern already on
  the server at `/tmp/t_run.sh` (systemd-run, sentinel file, `--test-tags`,
  ports 8199/8198). **Bump the manifest version or `-u` runs 0 tests.**

## Deploy contract (read CLAUDE.md top section — it is a hard rule)

- Everything deploys to `/odoo/odoo-server/addons` (ssh host `Payobook19v2`).
- Fresh staging dir: `sudo rm -rf /tmp/deployN && mkdir -p /tmp/deployN`; rsync
  repo modules there, then per-module
  `sudo rsync -a --delete --chown=odoo:odoo /tmp/deployN/<m>/ /odoo/odoo-server/addons/<m>/`.
  **NEVER `--delete` with the addons root as destination.**
- Upgrade ALL FOUR DBs (`abm`, `payobook`, `acme`, `payobook_template`) via the
  detached-unit pattern (`/tmp/u_run.sh` exists; edit its `-u` list). Verify
  `EXIT[db]=0` for each and `systemctl is-active odoo-server` after.
- No JS/SCSS in this phase → no asset-cache purge needed.

## Build (module: `pb_hr_payroll_formula`, plus one `pb_payruns` change)

### 1. The classifier — new file `pb_hr_payroll_formula/models/formula_net_role.py`

Model extension of `hr.formula.rule` adding stored, **on-demand** fields (no
`@api.depends` on excel_formula — formulas churn; classification runs when
asked, on import, or on repair):

- `net_role` Selection: `earning / deduction / net / employer_cost / info / mixed`
  (no default; empty = never classified).
- `net_role_detail` Boolean — True when another component of the SAME role
  (other than NET itself) references this one sign-preservingly, i.e. this
  value is folded into a subtotal. Details keep their category for payslip
  display but are excluded from run totals (else `TOTALDEDUCTI` +
  `SIHIIUTOT105` double-count).
- `net_role_reason` Char — one human sentence, e.g.
  "Subtracted from NETPAY through TOTALDEDUCTI". White-label: never the word
  "Odoo"; speak in component codes/names the user gave.
- `net_role_confidence` Selection: `certain / likely / review`.

On `hr.formula.config`:

- `classify_net_roles()` → computes and WRITES the four fields on every rule of
  the config; returns a summary dict (counts per role, unresolved list). Pure
  ORM, no UI.
- `suggest_categories()` → returns a JSON-able list
  `[{rule_id, code, name, current_category, suggested_category_code,
  role, detail, reason, confidence, agrees: bool}]` WITHOUT writing categories —
  Phase 2's popup feeds on this.
- `apply_suggested_categories(rule_ids=None)` → writes `category_id` from the
  suggestion (all rules, or the accepted subset), and pushes the same category
  onto each rule's linked `hr.salary.rule` (`salary_rule_id.category_id`).
  Does NOT touch existing payslip lines (repair below is explicit).

### 2. The sign-propagation algorithm (the heart — take care here)

Build per-config graph once:
1. For each formula rule: take `excel_formula`, expand `BRACKET` (same call as
   `_compute_dependencies`), strip string literals, normalise (row numbers
   off), then parse with a small tokenizer/recursive-descent parser over
   `+ - * / ( ) , : % comparisons functions`. Do NOT regex-only this; ranges,
   unary minus and IF need structure. Keep the parser in the new file,
   pure-Python, no new deps.
2. Emit signed edges `ref → this_rule` with sign ∈ {+1, −1, None(unknown)}:
   - additive terms carry their term sign; unary minus flips.
   - `a*b`, `a/b`: refs in numerator factors get the term sign; a negative
     NUMERIC literal factor flips it; refs in denominators or inside
     multiplications of two refs → sign kept but confidence drops to `likely`.
   - `SUM(range)` → each expanded member gets the term sign; `ROUND/MIN/MAX/
     FLOOR/CEILING(x, …)` → first arg propagates, others ignored; `ABS` →
     sign None; `IF(c, a, b)` → refs in `c` are IGNORED (condition, not
     contribution), refs in `a`/`b` propagate with confidence `likely`;
     comparison operands ignored.
   - Codes may appear instead of letters (`_compute_dependencies` handles
     both) — resolve a token first as column_letter, then as code.
3. Identify NET: the rule whose `category_id.code == 'NET'`, else code exactly
   `NET`/`NETPAY`, else name matches (case/space-insensitive) "net pay"/
   "netpay"/"thực lãnh"/"thuc lanh". If none → classification refuses with a
   clear summary error (never guess NET).
4. Propagate from NET backwards: sign(X→NET) = union over all paths of the
   product of edge signs (DFS with memo + cycle guard). Sets: {+} → earning,
   {−} → deduction, {+,−} or any None on every path → `mixed`/`review`.
5. Unreachable from NET: if reachable from a component that itself references
   NET **positively** together with other unreachables (the `TOTACOSTTOER =
   NETPAY + employer parts` pattern: a rule referencing NET with sign +1 whose
   other addends are NET-unreachable) → those addends are `employer_cost`.
   Everything else unreachable → `info`.
6. `net_role_detail`: X is detail iff ∃ Y (Y ≠ NET rule, same role as X) with a
   sign-preserving edge X→Y. On ABM this must make `ACTUBASISALA`,
   `SIHIIUTOT105`, `MONTHLYPIT`, `SALARYFORSI` details and leave
   `ACTUTOTAINCO`, `TOTALDEDUCTI` as the non-detail roll-ups.
7. Category from role: `net → NET`; `deduction → DED`; `employer_cost → COMP`;
   `info → OTH`; `mixed → OTH` (confidence `review`); earnings: `BASIC` when
   the code/name says base salary (contains BASE/BASIC/LUONG CO BAN — token
   match, not raw substring of the whole code: "BASESALARY" yes,
   "ACTUBASISALA" ALSO yes (it IS basic salary) — use ('BASE' in code or
   'BASIC' in code or 'BASISALA' in code)); the top-level earning AGGREGATE
   (non-detail earning whose formula is a pure ± sum, e.g. `ACTUTOTAINCO`)
   → `GROSS`; every other earning → `ALW`.

### 3. Run totals honour detail (module `pb_payruns`)

- New field `hr.payslip.line.component_detail` Boolean (add in
  `pb_hr_payroll_formula`'s payslip-line extension
  [hr_payslip_line.py](../../pb_hr_payroll_formula/models/hr_payslip_line.py),
  where `report_visible`/`component_type` already live). Both line producers
  copy it from `rule.net_role_detail`.
- `_compute_pb_totals` SQL: exclude `component_detail = TRUE` rows from the
  GROSS/BASIC/ALW and DED/DEDUCTION sums (NET stays as-is), and **drop `COMP`
  from the deductions sum** — an employer contribution is employer cost, not a
  deduction from pay. Before dropping COMP, CHECK the `payobook` demo DB:
  `SELECT count(*) FROM hr_payslip_line pl JOIN hr_salary_rule_category c ON
  c.id=pl.category_id WHERE c.code='COMP'` — if the demo's deduction KPIs
  visibly depend on COMP, report it and keep COMP behind
  `component_detail IS NOT TRUE` instead of dropping; state what you chose.
  Old rows have `component_detail` NULL → sums unchanged for every existing
  tenant until classification runs. Migration adds the column only (plain
  field add needs no migration script — just the `-u`).

### 4. The ABM repair (authorised by the owner in this exact session)

After deploy + upgrade of all 4 DBs, against the LIVE `abm` DB via JSON-RPC
(pattern: server-side python probe over `http://127.0.0.1:8069` with Host
header `abm.payobook.com`, login `ash@biztinct.com` / `J5validate!2026` —
working example exists at `/tmp/probe2.py` on the server; do NOT use
odoo-bin shell):

1. `classify_net_roles()` then `apply_suggested_categories()` on config 14.
2. Repair the EXISTING June lines (run 13) + any loose draft slips of config
   14: SQL `UPDATE hr_payslip_line pl SET category_id = r.cat,
   component_detail = r.net_role_detail FROM (rule join) …` matching by
   `pl.code = rule.code` for slips whose `formula_config_id = 14` or whose
   run is 13. Then recompute run totals (write on `slip_ids` or
   `env.add_to_compute` on the four pb_ fields + flush).
3. Verify and REPORT these exact numbers on run 13:
   - `pb_total_net` unchanged: **727,655,630**
   - `pb_total_deductions` ≈ **199,500,000** (TOTALDEDUCTI only; state exact)
   - `pb_total_gross` ≈ **927,155,630 + CC-component total** (state exact and
     name CC's code)
   - gross − deductions = net must hold to the đồng. If it does not, STOP,
     report the discrepancy, and do not tweak numbers to force it.
4. Also verify NO other tenant changed: `payobook` KPI totals for 2 sample
   runs before vs after upgrade must be identical.

### 5. What Phase 1 must NOT do (binding non-goals)

- No UI, no popup, no OWL — Phase 2.
- Do not auto-classify any scheme except ABM's config 14. The classifier is
  invoked, never ambient.
- Do not modify `_get_default_category`'s behaviour for schemes without
  classification (it stays the fallback; you may route the batch line-producer
  through `rule.category_id` first — it already does).
- Do not touch `om_hr_payroll`.
- Never "Odoo" in any user-visible string (help=, error text). Reasons/labels
  speak Payobook or neutral.

## Tests (numbered; new file `pb_hr_payroll_formula/tests/test_net_role_classifier.py`)

Build a scheme in-test mirroring ABM's shape (letters + ranges + IF):
`NET = GROSSAGG − DEDAGG + REFUND`; `GROSSAGG = SUM(range of BASE, ALW1, ALW2)`;
`DEDAGG = SI + PIT`; `SI = ROUND(SIBASE*0.105,0)`; `SIBASE = MIN(BASE, CAP)`;
`ERCOST = NET + ERSI`; `INFOFIELD` unreferenced; one `IF(X>0, A, −B)` rule.

1. BASE → earning/BASIC, detail=True (folded into GROSSAGG).
2. GROSSAGG → earning/GROSS, detail=False; DEDAGG → DED, detail=False.
3. SI, PIT → DED detail=True; SIBASE → detail of a DED (via SI) with role
   deduction, reason mentions the path.
4. REFUND (added positively, not base-ish, not aggregate) → ALW non-detail.
5. ERSI → employer_cost/COMP; ERCOST → employer_cost or info (state which and
   why in the test docstring — it references NET, it must NOT be earning).
6. INFOFIELD → info/OTH.
7. The IF rule with both-sign branches → mixed/review, category OTH.
8. No NET identifiable → classification raises/returns refusal, writes nothing.
9. `suggest_categories()` writes nothing (row-count + values diff proves it).
10. `apply_suggested_categories()` sets rule AND linked salary rule categories.
11. Range expansion: a rule whose letter sits inside `SUM(A:C)` span is an
    edge; one outside is not.
12. Line producers copy `component_detail`; a run's `pb_total_deductions`
    excludes detail rows and COMP (build a tiny run like
    `pb_payruns/tests/test_run_totals.py` does — reuse its fixture idioms).
13. Cycle in formulas (A refs B, B refs A) → no hang, both `review`.
14. Existing behaviour guard: a config with NO classification leaves every
    `component_detail` False/NULL and KPI sums exactly as before (regression
    on `test_run_totals.py` still green).

Run: full suites `TestNetRoleClassifier` + existing
`TestRunTotals,TestStructurelessPayslip,TestRunAdoptsThePeriod,TestGeneratePayslipsDialog`
on `payobook_template`. All green before deploy; then live ABM repair; then the
verification numbers.

## Version bumps

`pb_hr_payroll_formula` → 19.0.1.89.0; `pb_payruns` → 19.0.1.11.0.

## Commits (repo rule: per feature, explicit staging, no push)

1. `feat(formula): a component's category comes from what net pay does with it`
   — classifier + fields + tests.
2. `fix(payrun): run totals count each dong once` — component_detail + KPI SQL
   + its tests.
(ABM data repair is live-data, not a commit; describe it in the report.)

## Report back

- Test counts + EXIT codes (template DB), upgrade EXIT per DB.
- The ABM before/after table (gross/ded/net) + the identity check.
- CC component's real code + how it classified.
- Full list of the 99 ABM rules with role/category/detail/confidence (compact
  table in the report, it goes to the owner).
- Anything where the algorithm punted to `review`, with the formula text.
- Any deviation from this spec, stated as a deviation with the reason.
