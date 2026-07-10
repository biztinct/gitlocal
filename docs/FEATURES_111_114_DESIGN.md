# Features 111–114 — Implementation Design

Companion to the vision (`FORMULA_ENGINE_VISION.html`, WOW table rows 111–114) and the phase docs in this folder. Same convention: locked decisions → data model → numbered tasks with acceptance criteria → code skeletons for the risky spots. All file:line references verified against the repo on 2026-07-10.

Scope decisions from product owner:
- **111** — column letters are permanent; drag changes display only. Never rewrite formulas on reorder.
- **112** — read-only grid + filters + variance-vs-previous-run toggle + drill-to-payslip. No inline editing in v1.
- **113** — fully maintained legislation packs (not skeletons): rates + legislation refs + certification tests, versioned.
- **114** — all four vendors ship as mapping templates + auth scaffolding; live fetch is verified end-to-end against the demo connector only.

---

# 111 — Category-grouping columns (and the reorder-safety fix)

## The problem underneath the feature

`column_letter` is a stored computed field **derived from `sequence`** (`pb_hr_payroll_formula/models/formula_rule.py:393-449`). Reorder methods already exist — `move_column_left()`, `move_column_right()`, `reorder_to_position()` (`formula_rule.py:1209-1274`) — and they shift sequences, which recomputes letters. The companion `_update_formula_references_after_reorder()` (`formula_rule.py:1270-1274`) is a **pass-through that rewrites nothing**. Consequence: reordering today silently re-points every letter-based formula reference at a different component. Feature 111 therefore has two jobs: make grouping/reordering possible in the grid, and make it *impossible* for any reorder to change computation.

## Decisions

- **D111.1 — Letters become permanent identities, using the existing `forced_column_letter` mechanism.** `forced_column_letter` (`formula_rule.py:165-168`) already overrides the computed letter and is excluded from position calculation (`450-454`) — it's how constants get ZA/ZB today. We freeze *every* rule: a migration writes `forced_column_letter = column_letter` for all existing rules, and every creation path assigns the next free letter as forced at birth. From then on `sequence` is pure display order and `_compute_column_letter` can never move a letter.
- **D111.2 — Reorder APIs keep their names, lose their teeth.** `move_column_left/right` and `reorder_to_position` continue to exist (other code may call them) but now only rewrite `sequence`. Delete `_update_formula_references_after_reorder` entirely — with frozen letters there is nothing to update, and keeping a do-nothing safety valve invites someone to rely on it. Add a hard server guard: after any reorder, assert letters unchanged (cheap: compare sorted (id, letter) pairs) — raise, don't log, if violated.
- **D111.3 — "Next free letter" is max, not fill-the-gap.** New components take `max(existing letter) + 1` (skip the ZA+ constants range). Never reuse a deleted component's letter within a config: a stale formula referencing the old letter must stay *visibly broken* (validation error) rather than silently bind to a new component. This matches the user's observed current behavior (increment from last used) and makes it a guarantee.
- **D111.4 — Grouping is a display sort, not a structure.** "Group by category" = one batched write of `sequence` values ordered by `(category_id.sequence, current sequence)` — stable, so manual order within a category survives. Header drag = HTML5 DnD calling `reorder_to_position`. A thin color band strip under the header row shows category runs; a boundary renders where adjacent columns differ in category.
- **D111.5 — Letter badge is always visible in the header** (already true: `grid_studio.xml:23-36` shows letter + code). Out-of-alphabetical display is by design; the badge is the identity anchor. No "renumber" tool in v1 (explicitly rejected in scoping).

## Tasks

| # | Task | Files | Acceptance criteria |
|---|---|---|---|
| T111.1 | Freeze migration + creation paths (S7) | `pb_hr_payroll_formula/migrations/<ver>/post-freeze_letters.py` (or `post_init_hook` on version bump); `pb_formula_studio.py::add_component` (~464); import execute path in `multisheet_import_wizard.py` (letters are already explicit there — set them as forced); `_seed_template` | After upgrade: every rule has `forced_column_letter` set and `column_letter == forced_column_letter`; creating a component in the studio assigns max+1; deleting T then adding a component yields the next letter after the old max, never T again |
| T111.2 | Guarded reorder | `formula_rule.py`: rewrite the three reorder methods to sequence-only + `_assert_letters_frozen(config)` guard; delete `_update_formula_references_after_reorder` | Reorder any column on the VN demo config → every `excel_formula` byte-identical (SQL compare before/after), `compute_preview` values identical; the guard raises if a test deliberately unsets a forced letter first |
| T111.3 | Header drag in grid | `grid/grid_studio.js` + `grid_studio.xml`: `draggable="true"` on header cells, dragover insertion indicator, drop → `reorder_to_position` RPC → parent refresh | Drag GROSS between two other columns → order persists after reload; focus/selection survive (id-keyed); values row unchanged; no OWL key warnings |
| T111.4 | Group-by-category action + band strip | Toolbar button → new RPC `group_columns_by_category(config_id)` (batch sequence write, stable sort); band strip row in `grid_studio.xml` + `grid.scss` (reuse category color tokens from the outline) | One click groups all columns; within-category manual order preserved (stable); band boundaries match category changes; a second click is a no-op |
| T111.5 | Category-aware insertion | `add_component`: default `sequence` = end of the component's category run (if grouped), else end of grid | Adding a Deduction while grouped lands at the end of the Deduction band, not the far right |

## S7 — Skeleton: freeze migration + guarded reorder

```python
# pb_hr_payroll_formula/migrations/19.0.X/post-freeze_letters.py
def migrate(cr, version):
    """Letters become permanent identities (D111.1).
    Materialize today's computed letters as forced letters — after this,
    sequence changes can never move a letter again."""
    cr.execute("""
        UPDATE hr_formula_rule
           SET forced_column_letter = column_letter
         WHERE (forced_column_letter IS NULL OR forced_column_letter = '')
           AND column_letter IS NOT NULL AND column_letter != ''
    """)

# pb_hr_payroll_formula/models/formula_rule.py  (replacements)
def _next_free_letter(self, config):
    """max+1, never reuse (D111.3). Skip the ZA+ constants namespace."""
    used = [self._letter_num(r.column_letter) for r in config.rule_ids
            if r.column_letter and not r.column_letter.startswith('Z')]
    return self._num_letter((max(used) if used else 0) + 1)

def _assert_letters_frozen(self, config, before):
    after = {r.id: r.column_letter for r in config.rule_ids}
    if before != after:
        raise UserError(_(
            "Column letters changed during reorder — aborted to protect "
            "formulas. This is a bug; please report it."))

def reorder_to_position(self, new_sequence):
    """Display-only reorder (D111.2). Letters are frozen; only sequence moves."""
    self.ensure_one()
    config = self.config_id
    before = {r.id: r.column_letter for r in config.rule_ids}
    # ... existing sequence shift logic, unchanged ...
    self._assert_letters_frozen(config, before)
    return True
# move_column_left / move_column_right: same pattern (guard wraps the write).
# _update_formula_references_after_reorder: DELETED — do not reintroduce.

# pb_formula_studio/models/pb_formula_studio.py
@api.model
def group_columns_by_category(self, config_id):
    config = self.env['hr.formula.config'].browse(config_id)
    before = {r.id: r.column_letter for r in config.rule_ids}
    ordered = config.rule_ids.sorted(
        key=lambda r: (r.category_id.sequence if r.category_id else 999,
                       r.sequence))                      # stable (D111.4)
    for i, rule in enumerate(ordered):
        if rule.sequence != (i + 1) * 10:
            rule.with_context(skip_formula_version=True).sequence = (i + 1) * 10
    self.env['hr.formula.rule']._assert_letters_frozen(config, before)
    return self.get_studio_data(config_id)
```

**Gotcha for the implementer:** `_compute_column_letter` depends on `sequence` — after freezing, verify the compute simply returns the forced letter for every rule and that no *other* `@api.depends('sequence')` compute re-derives anything letter-shaped (search the file). Also grep for any code that *parses* `column_letter` positionally (the evaluator's `column_map` at `formula_rule.py:498-919` keys by letter — fine, it's identity-based).

---

# 112 — Post-calculation results grid (new module `pb_payrun_results`)

## What it is

Pick a pay run → every employee's computed components in one Excel-style read-only grid — frozen employee column, category color bands, totals row, division/department/search filters, variance-vs-previous-run heat toggle, drill to payslip, one-click .xlsx of the full filtered set.

## Decisions

- **D112.1 — New module `pb_payrun_results`**, standard cockpit pattern (`registry.category("actions").add`, action XML, `pb.sidebar.item` under the Pay Runs section — copy the wiring from `pb_govt_reports`). Server model `pb.payrun.results` (AbstractModel, RPC-only, like `pb.formula.studio`).
- **D112.2 — Data source is `formula_computed_values` JSON** on each slip (`hr_payslip_formula.py:45-60`) — one JSON parse per row, zero joins to `hr.payslip.line`. Columns come from the run's config rules filtered to `appears_on_payslip OR report_visible`, ordered by display `sequence` (which after 111 is the user's curated order — the grid inherits grouping for free). v1 supports formula-calculated slips only; a run with none shows an explicit empty-state, not a blank grid.
- **D112.3 — Server-side pagination and filtering** (100 rows/page): 4,512 employees × ~60 columns must never land in one payload. Totals row is computed over the FULL filtered set server-side (not the page). Export likewise ignores pagination.
- **D112.4 — Variance pairing is by employee + cycle type.** Previous slip = latest earlier slip of the same employee with the same `formula_config_id.cycle_type` (mid compares to mid, end to end). Deltas computed server-side and shipped alongside values only when the toggle is on (`?with_variance=1`) — half the payload otherwise. Client renders heat tint (reuse the amber/cyan dep-tint palette from `grid.scss`: amber = decreased, cyan = increased; intensity bucketed by |delta| percentile, not absolute value).
- **D112.5 — Drill actions:** row click → `action.doAction` to the payslip form; cell click → popover showing the component's name, formula, and explanation via `explain_formula_ai` when available, deterministic `_explain` otherwise (both on `pb.formula.studio` — reuse, don't duplicate).
- **D112.6 — Export copies the proven blob pattern** (`export_test_template`, `pb_formula_studio.py:3798-3827` server / `formula_studio.js:2222-2233` client): openpyxl workbook → base64 in the RPC response → client `atob` → Blob → `<a download>`. Header row colored per category, employee column frozen (`freeze_panes="B2"`), totals row bold, number formats from each rule's `number_format`. No ir.attachment, no controller route.
- **D112.7 — CSS: reuse `.pbfs-grid2`** sticky-pane machinery (`pb_formula_studio/static/src/scss/grid.scss`) under a new `.pbr-` namespace rather than `.pbim-table` — the results grid is the same frozen-panes problem the Grid Studio already solved.

## RPC contract

```
pb.payrun.results.get_grid(run_id, filters={division, department_id, search, with_variance, page})
→ {run: {id, name, period, state, config_name},
   runs: [{id, name}],                      # switcher dropdown
   columns: [{code, name, category, color, number_format}],
   rows: [{slip_id, employee_id, employee_name, employee_code, department,
           values: {CODE: num}, deltas: {CODE: num} | null}],
   totals: {CODE: num}, page, page_count, row_count,
   prev_run_label: str | null, empty_reason: str | null}

pb.payrun.results.export_grid(run_id, filters)   # full set, no pagination
→ {ok, file_b64, mimetype, filename}
```

## Tasks

| # | Task | AC |
|---|---|---|
| T112.1 | Module scaffold: manifest (depends `pb_hr_payroll_formula`, `pb_sidebar`, `pb_import_kit`), action XML, sidebar item, empty cockpit renders | Cockpit opens from sidebar; run switcher lists formula runs newest-first |
| T112.2 | `get_grid` RPC: columns from config rules, rows from slip JSON, filters, pagination, totals over full set | Spot-check 3 employees × 3 components against payslip "Formula Computed JSON" tab — exact match; totals equal the sum over all pages; search "Nguyễn" filters server-side |
| T112.3 | Grid UI: `.pbr-grid` frozen employee column + header (CSS sticky), category color bands (shared tokens with 111's band strip), pagination bar, filter row | 4.5k-employee run: page loads < 3 s, scroll stays smooth; keyboard: arrows move row focus, Enter opens payslip |
| T112.4 | Variance toggle + pairing (S8) | For an employee with a hand-computed month-over-month OT change, delta matches exactly; first-ever run shows "no previous run" state, not zeros; mid-cycle run never pairs against an end-cycle slip |
| T112.5 | Drill: row → payslip form; cell → explanation popover | Popover shows formula + explanation for the clicked component; works with AI disabled (deterministic text) |
| T112.6 | xlsx export (S8) | Exported file opens in Excel: all filtered rows (not one page), frozen first column, category-colored headers, totals row, VN currency formats; 4.5k rows export < 30 s |
| T112.7 | pb_coach tour step + empty states | Non-formula run and empty-filter cases show explanatory empty states |

## S8 — Skeleton: grid RPC + variance pairing + xlsx export

```python
# pb_payrun_results/models/payrun_results.py
class PayrunResults(models.AbstractModel):
    _name = 'pb.payrun.results'
    _description = 'Pay Run Results Grid'

    PAGE = 100

    @api.model
    def get_grid(self, run_id, filters=None):
        f = filters or {}
        run = self.env['hr.payslip.run'].browse(run_id)
        slips = run.slip_ids.filtered(lambda s: s.formula_computed_values)
        if not slips:
            return {'empty_reason': _('This run has no formula-calculated payslips.'), ...}
        config = slips[0].formula_config_id
        cols = [{'code': r.code, 'name': r.name, 'category': ...,
                 'color': ..., 'number_format': r.number_format}
                for r in config.rule_ids.sorted('sequence')
                if r.appears_on_payslip or r.report_visible]
        codes = [c['code'] for c in cols]

        slips = self._apply_filters(slips, f)            # division/dept/search
        # totals over the FULL filtered set (D112.3) — one pass, before slicing
        totals = dict.fromkeys(codes, 0.0)
        parsed = {}                                       # slip_id -> values dict
        for s in slips:
            v = json.loads(s.formula_computed_values or '{}')
            parsed[s.id] = v
            for c in codes:
                totals[c] += float(v.get(c) or 0.0)

        page = max(1, int(f.get('page') or 1))
        page_slips = slips.sorted(key=lambda s: s.employee_id.name)[
            (page - 1) * self.PAGE: page * self.PAGE]

        deltas_by_slip = (self._pair_variance(page_slips, codes, parsed)
                          if f.get('with_variance') else {})
        rows = [{'slip_id': s.id, 'employee_id': s.employee_id.id,
                 'employee_name': s.employee_id.name,
                 'department': s.employee_id.department_id.name or '',
                 'values': {c: parsed[s.id].get(c) for c in codes},
                 'deltas': deltas_by_slip.get(s.id)} for s in page_slips]
        return {'columns': cols, 'rows': rows, 'totals': totals,
                'page': page, 'page_count': -(-len(slips) // self.PAGE),
                'row_count': len(slips), ...}

    def _pair_variance(self, slips, codes, parsed):
        """Previous slip = latest earlier slip, same employee, SAME cycle_type
        (D112.4). One batched search for the whole page, not per slip."""
        cycle = slips[0].formula_config_id.cycle_type
        prev = self.env['hr.payslip'].search([
            ('employee_id', 'in', slips.mapped('employee_id').ids),
            ('date_to', '<', min(slips.mapped('date_from'))),
            ('formula_config_id.cycle_type', '=', cycle),
            ('formula_computed_values', '!=', False)],
            order='employee_id, date_to desc')
        latest_prev = {}                                  # employee_id -> slip (first seen = latest)
        for p in prev:
            latest_prev.setdefault(p.employee_id.id, p)
        out = {}
        for s in slips:
            p = latest_prev.get(s.employee_id.id)
            if not p:
                continue
            pv = json.loads(p.formula_computed_values or '{}')
            cv = parsed[s.id]
            out[s.id] = {c: float(cv.get(c) or 0) - float(pv.get(c) or 0)
                         for c in codes}
        return out

    @api.model
    def export_grid(self, run_id, filters=None):
        """Full filtered set. Mirror export_test_template's return shape
        (pb_formula_studio.py:3798) so the client can reuse the blob pattern."""
        import openpyxl
        from openpyxl.styles import Font, PatternFill
        from openpyxl.utils import get_column_letter
        data = self._full_rows(run_id, filters)          # same pipeline, no slice
        wb = openpyxl.Workbook(); ws = wb.active
        ws.title = data['run']['name'][:31]
        ws.freeze_panes = 'B2'                            # D112.6
        # header: employee + category-colored component columns
        ws.cell(1, 1, _('Employee')).font = Font(bold=True)
        for j, col in enumerate(data['columns'], start=2):
            c = ws.cell(1, j, f"{col['name']} ({col['code']})")
            c.font = Font(bold=True)
            c.fill = PatternFill('solid', fgColor=col['xlsx_color'])
        for i, row in enumerate(data['rows'], start=2):
            ws.cell(i, 1, row['employee_name'])
            for j, col in enumerate(data['columns'], start=2):
                cell = ws.cell(i, j, row['values'].get(col['code']))
                cell.number_format = col['excel_number_format']  # from rule.number_format
        # totals row bold, widths, ...
        buf = io.BytesIO(); wb.save(buf)
        return {'ok': True, 'file_b64': base64.b64encode(buf.getvalue()).decode(),
                'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'filename': f"payrun_results_{data['run']['name']}.xlsx"}
```

Client download handler: copy `exportTestTemplate` (`formula_studio.js:2222-2233`) verbatim into the cockpit.

---

# 113 — Country payroll templates as maintained legislation packs

## Decisions

- **D113.1 — Grow the existing template seam, don't replace it.** `wizard_templates()` / `_seed_template()` / `create_config()` (`pb_formula_studio.py:4332-4361`) stay the API the studio wizard calls; they are refactored to read from a new model instead of the hardcoded `VN_STANDARD` tuple list (which becomes the first record, migrated as `vn_standard` — zero behavior change for existing users).
- **D113.2 — Pack registry model, packs as data modules.**
  ```
  hr.formula.config.template
    code (unique per version: 'vn_standard_2026'), country_code, name, description
    version (Char '2026.1'), effective_date, state: draft/certified/superseded
    components_json      # [{code, name, type, category, excel_formula, constant_value,
                          #   appears_on_payslip, number_format, legislation_ref}]
    rate_tables_json     # [{code, name, brackets: [{lower, upper, rate}], legislation_ref}]
    sample_tests_json    # [{name, inputs: {..}, expected: {..}}]  — the certification suite
    legislation_refs_json # [{ref, title, url, effective_date}]
    supersedes_id (m2o self)
  ```
  Each country ships as a data-only module `pb_pack_vn`, `pb_pack_sg`, … containing one or more template records. Rate tables flatten into bracket formulas at seed time until F11 (typed rate tables) lands — the JSON format is F11-ready so packs don't need rewriting.
- **D113.3 — Certification gate at install.** Each pack module's `post_init_hook` creates a throwaway config from its template, runs every sample test through `_evaluate_rules_with_dependencies` (the validated path — never `evaluate_all`, per the converter contract), asserts all pass, then deletes the config. A failing test **blocks install**. This is what "maintained" means mechanically: the pack proves itself on every install and every update.
- **D113.4 — Converter contract is enforced at the registry.** A constraint on `hr.formula.config.template` validates every component code in `components_json`: underscore-free AND no code is a substring of another (the Excel→Python converter mangles violators to 0 — hard rule). Better to fail at pack authoring than at client payroll.
- **D113.5 — Updates are new versions, not edits.** A rate change ships as a new template record (`version='2027.1'`, `supersedes_id` set); the old one flips to `superseded`. Applying an update to a *live* config: v1 = a diff report (component-by-component: changed formulas/rates with legislation refs) the consultant applies manually; once F7 version history lands, upgrade to one-click apply as versioned proposals. Never silent auto-update of a live payroll.
- **D113.6 — Content pipeline + rollout.** Mine the legacy country modules' salary-rule XML (`pb_hr_payroll_vietnam/data/`, `.._indonesia/data/enhanced_salary_rules_data.xml`, `.._india/data/hr_salary_rule_data.xml`, …) for component lists and formulas — they are `hr.salary.rule` records, so mining = translating rule logic to excel formulas, not copy-paste. Rollout: **infrastructure + VN + SG first** (VN content exists and is demo-validated; SG CPF is precisely specified), then ID → MY → TH → IN → JP. Each pack needs a country reviewer sign-off before `state='certified'`.

## Tasks

| # | Task | AC |
|---|---|---|
| T113.1 | Registry model + code-contract constraint + access rules | Creating a template with codes `TAX` and `TAXRATE` (substring) is rejected with a clear message; underscore code rejected |
| T113.2 | Refactor `wizard_templates`/`_seed_template` to read the registry; migrate `VN_STANDARD` to a record | Studio wizard shows the same two entries as today; create-from-template produces an identical config to pre-refactor (regression compare) |
| T113.3 | Seeding v2: categories, rate-table flattening, sample-test import (tests land as `hr.formula.sample.data` on the new config), forced letters per 111 | Config created from a pack has components grouped by category, letters frozen, and its sample tests visible in the Test workbench — all green |
| T113.4 | Certification `post_init_hook` harness (shared helper in `pb_hr_payroll_formula`) | Deliberately corrupting one expected value in a dev copy of the VN pack blocks install with the failing test named |
| T113.5 | `pb_pack_vn`: full VN pack (PIT brackets, SI/HI/UI caps, family deductions, OT multipliers) with legislation refs + ≥ 10 sample tests incl. bracket boundaries | Installs green; a config created from it computes the demo world's known-good PIT values |
| T113.6 | `pb_pack_sg`: CPF (age-banded rates, OW/AW ceilings), SDL, SHG funds + tests | Installs green; CPF sample tests cover at least 3 age bands and the ceiling |
| T113.7 | Country picker UX in the studio wizard (flag, description, effective date, legislation ref links) + "what's inside" preview before create | Picking SG shows the component list + rates before committing; created config is immediately testable |
| T113.8 | Update-diff report: `compare_template_versions(a, b)` → rendered diff (component added/removed/changed with refs) | VN 2026.1 → dev 2027.1 with one rate change produces a one-line diff naming the rate and its legislation ref |

**Ongoing commitment (flag to product owner):** "fully maintained" means someone owns rate watch per country. The mechanical side is covered (versions, certification, diff reports); the editorial side needs an owner per country and a review cadence — recommend piggybacking on M4 Compliance Watch when it lands, manual quarterly review until then.

---

# 114 — Ready-made HR/API connector mapping templates

## Decisions

- **D114.1 — Templates are data, applied on demand.** New model:
  ```
  hr.integration.mapping.template
    connector_type (zoho/workday/sap/oracle), source_path (Char),
    target_code (Char — canonical input code: BASIC, DEPENDENTS, WDAYS, OTHOURS…),
    transformation_type, default_value, is_required (Bool), note (Char)
  ```
  shipped as XML data in `pb_hr_payroll_formula/data/mapping_templates_<vendor>.xml`, with the four vendors' standard payload paths (Zoho People REST field names, Workday RaaS report fields, SAP SuccessFactors OData properties, Oracle HCM REST resources). ~15–25 rows per vendor covering identity, compensation, dependents, attendance.
- **D114.2 — Seeding matches by canonical code, degrades visibly.** `action_apply_mapping_template()` on the connector: for each template row, find the connector's config input rule whose `code == target_code` → create `hr.integration.field.mapping`. No match → still create the mapping row but flagged `state='suggested'` (new Selection field on the mapping: `active_state: active/suggested/ignored`) so nothing silently disappears; the mapping list shows suggested rows amber with a "pick target rule" dropdown (the Phase-1 `source_field_autocomplete` widget already handles the source side).
- **D114.3 — Onboarding is a 4-step wizard, not a form.** `hr.integration.onboarding.wizard`: (1) pick vendor (cards with logos + per-vendor auth guide text) → (2) auth (existing credential fields per `auth_type`; "Test connection" reuses `test_connection()`) → (3) mappings (auto-applied template + suggested-row resolution + **batch test** via Phase-1 `test_mappings_batch` against a fetched or stored sample employee) → (4) activate. Every step is skippable/resumable — the wizard writes to the real connector record as it goes.
- **D114.4 — End-to-end truth is the demo connector** (user decision). The four vendor templates are validated structurally (paths documented against vendor API docs, cited in each row's `note`), but live fetch is CI-verified only against `demo_connector.py`. Each vendor card in step 1 shows an honest badge: "Field template — verified against API docs vX" vs the demo's "Live-tested".
- **D114.5 — No new auth machinery.** OAuth2/api_key/basic/bearer fields and refresh flow already exist (`integration_connector.py:77-82, 336-349`); 114 adds only per-vendor *guide text* (which console to open, which scopes to grant) as `help_html` on the template-set records.

## Tasks

| # | Task | AC |
|---|---|---|
| T114.1 | Template model + `active_state` on field mapping + access rules | Suggested mappings render amber in the mapping list and are excluded from sync until resolved |
| T114.2 | Vendor template data: Zoho, Workday, SAP SF, Oracle (each row cites its API doc section in `note`) | Each vendor has ≥ 15 rows spanning identity/compensation/dependents/attendance; every `target_code` passes the converter contract check |
| T114.3 | `action_apply_mapping_template` + re-apply semantics (idempotent: existing active mappings never overwritten; missing ones added) | Applying twice creates no duplicates; a config with BASIC+DEPENDENTS inputs gets those active, the rest suggested |
| T114.4 | Onboarding wizard (4 steps, kit-styled) | Full flow on the demo connector: pick demo → test connection green → mappings seeded → batch test shows raw→transformed per mapping → activate; a deliberately broken nested path shows an explicit error row |
| T114.5 | Vendor cards + honesty badges + auth guides | Zoho card shows the OAuth console steps; badge wording matches D114.4 |
| T114.6 | pb_coach tour: "Connect your HR system" | Tour walks the demo connector end-to-end |

---

# Sequencing & effort

| Order | Feature | Effort | Why |
|---|---|---|---|
| 1 | **111** | ~1 week | Smallest, fixes a live data-integrity trap, and 112/113 both benefit (112 inherits curated column order; 113 seeds frozen letters) |
| 2 | **112** | ~1.5 weeks | Self-contained new module; highest daily-use value |
| 3 | **114** | ~1.5 weeks | Server-light, mostly data + wizard; independent |
| 4 | **113 infra + VN + SG** | ~2.5 weeks | Registry + certification harness + two real packs; remaining countries are content work (~2–4 days each) on the finished infra |

# Verification (pb_demo VN world + Chrome MCP)

1. **111**: SQL-snapshot all `excel_formula` + run `compute_preview` before/after a drag storm (10 random reorders + group-by-category) — both byte-identical. Keyboard-only drag alternative (bulk-select + "move to position" fallback) works.
2. **112**: 3-way value check (grid cell = payslip JSON tab = xlsx cell) on 3 employees; totals vs run total; variance vs a hand-computed OT delta; 4.5k-row export opens in Excel.
3. **113**: fresh DB → install `pb_pack_vn` → create config → all sample tests green → compute a demo employee and compare to known-good PIT; corrupt-pack negative test blocks install.
4. **114**: onboarding wizard end-to-end on the demo connector; template apply idempotency; suggested-row resolution flow; broken-path batch test shows the error, not 0.

---
---

# PART II — Content appendices (added 2026-07-10, after F111 shipped)

Part I gives the mechanics; these appendices give the **data** — the part a coding model would otherwise have to invent. Statutory numbers below were re-verified against 2026 sources on 2026-07-10; every number still carries an effective date and a VERIFY note because legislation moves. The certification gate (T113.4) is what makes an error here survivable: a wrong rate fails its own sample tests.

## A0 — Design amendment: reconcile 113 with the shipped B4 legislation packs

B4 shipped (`hr.formula.legislation.pack` — country-scoped, versioned **value-only** bundles applied to *existing* configs, F7-versioned, milestone-sealed). Feature 113 as drafted also said "packs," which would create two things with one name. Amendment to D113.2/D113.6:

- **113 is renamed "Country Starter Templates"** (model stays `hr.formula.config.template`). A template carries **structure**: components, formulas, categories, payslip sections, sample tests.
- **Statutory values have ONE source of truth: the B4 legislation pack.** A template's `components_json` may tag a constant with `"legislation_code": "DEDUCTSELF"`; at create-config time the seeder resolves those values from the country's **current published** `hr.formula.legislation.pack` (highest version, state=published, effective_date ≤ today). The template never hardcodes a rate that a pack owns.
- Consequence: a rate change is shipped ONCE (a new B4 pack version) and serves both existing configs (B4 apply/rollout) and future configs (template seeding). The template's own version only bumps on *structural* change.
- Sample tests in a template pin the pack version they were computed against (`"pack_version": "2026.1"` in `sample_tests_json`); the certification harness loads that exact pack version so tests stay reproducible even after newer packs publish.
- New task **T113.2b**: extend the VN B4 seed data (`data/legislation_pack_data.xml`) with any statutory codes the VN template needs that the shipped 10-item pack lacks (e.g. ER-side rates already exist; add OT multipliers ONLY if modeled as constants). SG needs a new B4 pack `sg_statutory_2026` (A2 below) — B4's model is country-generic, nothing to build, just data.

## A1 — `pb_pack_vn` content specification (Vietnam)

**⚠ 2026 is a transition year for VN PIT — the template must ship BOTH schedules as effective-dated table versions:**

- **Deductions (in force since 2026-01-01, Resolution 110/2025/UBTVQH15):** personal 15,500,000 ₫/month (was 11,000,000), per-dependent 6,200,000 ₫/month (was 4,400,000). The shipped B4 pack "Vietnam Personal-Relief Increase v2026" already carries exactly these — the template references it, per A0.
- **PIT schedule:** the classic **7-bracket** table (5/10/15/20/25/30/35% at thresholds 5/10/18/32/52/80M) is what the demo world computes today; the **Amended PIT Law 2025 introduces a 5-bracket** table (5/15/25/30/35%, top band above 100M/month) with salary-income provisions applying from the 2026 tax year. **VERIFY before certification** which schedule the client's 2026 filings use (implementation dates were staged: law text effective 2026-07-01, salary provisions from 2026-01-01). Ship both as `hr.formula.rate.table` versions with `effective_date`; the template defaults to the one matching its `effective_date` field. Do NOT hand-compute expected test values — generate them through F11's `compile_excel` harness, then cross-check ≥3 against an official calculator, then freeze into `sample_tests_json`.

**Statutory values (via B4 pack, baseline = the shipped "Vietnam Statutory Parameters" pack, confirmed against demo configs):**

| Code | Meaning | Value | Note |
|---|---|---|---|
| DEDUCTSELF / DEDUCTDEP | Personal / dependent relief | 15.5M / 6.2M | 2026 pack (Resolution 110/2025) |
| EESI / EEHI / EEUI | Employee SI/HI/UI | 8% / 1.5% / 1% | unchanged 2026 |
| ERSI / ERHI / ERUI | Employer SI/HI/UI | 17.5% / 3% / 1% | employer side; verify ERSI split incl. occupational fund |
| CAPLO / CAPHI | SI-HI cap / UI cap bases | 46.8M / 99.2M | 20× reference level / 20× regional minimum — re-verify July 2026 (reference-level revisions were pending) |

**Component structure (mine the live demo config — it IS the validated VN structure):** inputs (BASIC, DEPS, working-day inputs, OT hours by type, bonuses/allowance inputs) → earnings (position/responsibility/meal/transport/phone allowances, OT 150/200/300%, 13th-month handling) → pre-tax (GROSS, SI base with cap, EE contributions) → tax (TAXABLE = GROSS − EE contributions − reliefs; PIT via `BRACKET(PITVN, TAXABLE)`) → employer side (ER contributions, total cost) → NET. Respect the converter contract on every code. Payslip sections per F9 (`hr.payslip.config` records in the template, bilingual labels EN/VI).

**Certification test matrix (≥12 cases, expected values harness-generated per above):** zero income; income below first bracket; each bracket boundary ±1,000 ₫ for whichever schedule is active (5-bracket ⇒ 6 boundary cases); SI cap boundary (income at/above CAPLO); 0/1/3 dependents; OT-heavy month; and one full known-good demo employee reproduced end-to-end.

## A2 — `pb_pack_sg` content specification (Singapore)

**CPF (effective 2026-01-01):** OW ceiling **S$8,000/month** (raised from 7,400); AW ceiling = **102,000 − total OW subject to CPF** that year. Age-banded total rates 2026: **≤55: 37%** (20% EE + 17% ER); **55–60: 34%**; **60–65: 25%**; **65–70: 16.5%**; **>70: 13.5%**. ⚠ The EE/ER split inside the 55–60, 60–65 and >70 bands changed with the 2026 senior-worker step-up — **VERIFY the exact splits against the CPF Board's published 2026 table before freezing** (only the ≤55 split of 20/17 is long-stable). Age-band transitions apply from the first day of the month AFTER crossing 55/60/65/70. Model: one `hr.formula.rate.table`-like structure per side won't fit age banding — implement as an AGE input (or derived from birthdate) + nested-IF band formulas generated by the template, with band rates as B4 pack constants (`CPFEE55`, `CPFER55`, `CPFEE60`, … per band) so a future rate change is a pack update, not a formula edit.
**SDL:** 0.25% of monthly remuneration, min S$2, cap S$11.25 (i.e. capped at S$4,500 wage). **SHG funds** (employee-side, community-based: CDAC/ECF/MBMF/SINDA, wage-banded flat amounts): ship the four band tables with a per-employee FUND selector input; **VERIFY current band tables** — they change rarely but are easy to get stale.
**Structure:** inputs (BASIC, AGE or DOB-derived band, bonus/AW inputs, FUND selector) → OW capping → CPF EE/ER by band → AW ceiling tracking (needs a YTD-OW input in v1 — document this honestly as a limitation: true AW-ceiling tracking is cross-period) → SDL → SHG → NET + employer cost.
**Certification matrix (≥10):** the doc's own AC (≥3 age bands) plus: wage exactly at 8,000; above ceiling; band transition month (birthday month vs next month); AW below/above the remaining ceiling; SDL min and cap; one SHG per fund.

## A3 — Feature 114 vendor template datasets

Rules for all four datasets: rows are **seeds, not gospel** — the safety net is D114.2 (unmatched → `suggested`, never dropped) + the batch test against the tenant's real stored payload. Every row's `note` cites the vendor doc area; badge wording per D114.4 ("Field template — verify against your tenant"). Canonical target codes: `EMPID, FULLNAME, EMAIL, DEPT, JOBTITLE, JOINDATE, BASIC, ALLOWFIX, BONUS, DEPS, WDAYS, OTHOURS, LEAVEDAYS, BANKACC, TAXID`. Transform defaults to `direct` unless noted.

**Zoho People** (REST v2, `/api/forms/P_EmployeeView/records` + payroll form; field labels follow the tenant's form customization — the batch test resolves drift):
`EmployeeID→EMPID (required)`, `FirstName + LastName→FULLNAME (concat transform)`, `EmailID→EMAIL`, `Department→DEPT`, `Designation→JOBTITLE`, `Dateofjoining→JOINDATE (date)`, `Salary→BASIC`, `Other_Allowance→ALLOWFIX`, `No_of_Dependents→DEPS`, `Total_working_days→WDAYS`, `Overtime_hours→OTHOURS`, `LeaveTaken→LEAVEDAYS`, `Bank_Account_No→BANKACC`, `PAN_or_TaxID→TAXID`. (14 rows; attendance rows may also come via the Attendance API — note on row.)

**Workday** (RaaS custom report or `Get_Workers` SOAP→JSON; paths assume a flattened RaaS report — the recommended integration shape):
`Employee_ID→EMPID (required)`, `Legal_Name→FULLNAME`, `primaryWorkEmail→EMAIL`, `Supervisory_Organization→DEPT`, `Business_Title→JOBTITLE`, `Hire_Date→JOINDATE`, `Total_Base_Pay_Annualized→BASIC (÷12 transform, note: verify frequency)`, `Allowance_Plan_Amount→ALLOWFIX`, `Bonus_Plan_Amount→BONUS`, `Dependents_Count→DEPS`, `Scheduled_Weekly_Hours→WDAYS (transform: ×52÷12÷8, note: derive working days — verify against tenant convention)`, `Bank_Account_Number→BANKACC`, `National_ID→TAXID`. (13 rows.)

**SAP SuccessFactors** (OData v2: `PerPerson`/`EmpEmployment`/`EmpCompensation`/`EmpPayCompRecurring`):
`userId→EMPID (required)`, `personalInfoNav/firstName + lastName→FULLNAME (concat)`, `emailNav/emailAddress→EMAIL`, `departmentNav/name→DEPT`, `jobInfoNav/jobTitle→JOBTITLE`, `startDate→JOINDATE (SF /Date()/ epoch transform — note explicitly: SF dates are epoch-wrapped)`, `empPayCompRecurringNav[payComponent=BASE]/paycompvalue→BASIC`, `[payComponent=ALLOW]/paycompvalue→ALLOWFIX`, `[payComponent=BONUS]/paycompvalue→BONUS`, `personRelationshipNav count→DEPS (count transform)`, `standardHours→WDAYS (derive, verify)`, `paymentInfoNav/accountNumber→BANKACC`, `nationalIdNav/nationalId→TAXID`. (13 rows; pay-component codes BASE/ALLOW/BONUS are tenant-configured — flag as the #1 thing the batch test will catch.)

**Oracle HCM Cloud** (REST `hcmRestApi/resources/11.13.18.05/workers` + `salaries`):
`PersonNumber→EMPID (required)`, `names[PrimaryFlag]/DisplayName→FULLNAME`, `emails[Primary]/EmailAddress→EMAIL`, `workRelationships/assignments/DepartmentName→DEPT`, `assignments/JobName→JOBTITLE`, `workRelationships/StartDate→JOINDATE`, `salaries/SalaryAmount→BASIC (note: check SalaryBasis for frequency)`, `salaries/AnnualizedSalary→(alt BASIC, suggested-only row)`, `dependents count→DEPS (count)`, `assignments/StandardWorkingHours→WDAYS (derive, verify)`, `personBankAccounts/AccountNumber→BANKACC`, `nationalIdentifiers/NationalIdentifierNumber→TAXID`. (12 rows.)

**T114.2 amendment:** ship these rows exactly as specified, each with its doc citation in `note`; rows marked "verify/derive" get `is_required=False` and a `suggested`-by-default flag so they never silently feed wrong numbers — promotion to active happens in the wizard's batch-test step where the real payload is visible.

## A4 — Verdict on remaining design sufficiency

- **112**: build from Part I as-is (S8 + live cockpit precedents). No additions needed.
- **114**: Part I mechanics + A3 datasets = complete.
- **113**: Part I mechanics + A0 reconciliation + A1/A2 content = complete, with the explicit rule that **expected test values are harness-generated and cross-checked, never hand-typed**, and every ⚠ VERIFY item is resolved before a pack flips to `certified`.
