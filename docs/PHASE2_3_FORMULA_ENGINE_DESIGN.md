# Phase-2 & Phase-3 — Formula Engine Design Document

Companion to `docs/PHASE1_FORMULA_ENGINE_PLAN.md` and the product vision artifact.
Covers Tier-2 (Medium-term) at implementation grade and Tier-3 (Long-term) as design briefs.

**How to use this document.** Tier-2 features F6–F15 are designed to the same standard as Phase 1: locked decisions, data models with field names, file-level work, and — for the two riskiest — task checklists with acceptance criteria and code skeletons (S3, S4). Tier-3 briefs (B1–B9) deliberately stop at architecture + data model + key decision: they depend on Tier-2 code landing first, and file-level plans written against code that doesn't exist yet rot. Each brief states its **design-complete trigger** — the event after which it can be hardened to Phase-1 grade in ~1 session.

## Phase-1 infrastructure this document treats as existing (verified in code)

| Piece | Where | Status |
|---|---|---|
| Dependency graph RPC `get_intelligence` / `get_impact_analysis` | `pb_formula_studio/models/pb_formula_studio.py:286/451` | ✅ landed |
| Grid Studio (`grid_studio.js`, `formula_bar.js`, `cell_autocomplete.js`) | `pb_formula_studio/static/src/js/grid/` | ✅ landed |
| `bulk_update_components` / `translate_formula` | `pb_formula_studio.py:603/639` | ✅ landed |
| Import preview mixin + preview lines + confidence | `pb_hr_payroll_formula/wizards/multisheet_import_preview.py` | ✅ landed |
| `_llm_chat` / `explain_formula_ai` / `ai_review_import` | — | ⬜ pending (Phase-1 Feature 5) |
| Chunked compute pattern `prepare_run`/`compute_batch` | `pb_payrun_wizard/models/pb_payrun_wizard.py:170/211` | ✅ existing, reuse |
| Expected-vs-computed validation with number coercion | `pb_hr_payroll_formula/models/formula_sample_data.py:164–244` | ✅ existing, generalize |

---

# PART A — Tier-2 full designs

## F6 — Shadow Parallel Run (the hero) · ~3 weeks

**What it is.** Import the client's historical Excel payroll *results* (not just formulas), recompute those periods through the engine, compare cell-by-cell, cluster discrepancies by cause, and issue a Migration Confidence certificate.

### Decisions

- **D6.1 — The compare engine is a generalization of `hr.formula.sample.data`, not a new invention.** That model already stores `input_values_json` / `expected_values_json`, evaluates via `_evaluate_rules_with_dependencies`, and compares with numeric coercion (`formula_sample_data.py:164–244`). A shadow run is *N samples × M periods with clustering on top*. Extract the coercion + tolerance comparison into a reusable helper (`pb_hr_payroll_formula/formula_engine/comparison.py`) used by BOTH sample validation and shadow runs — one comparison semantics everywhere.
- **D6.2 — Recompute runs through the chunked-compute pattern**, cloned from `pb_payrun_wizard.prepare_run`/`compute_batch`: the OWL cockpit drives batches of ~50 employee-periods over silent RPC, showing a determinate progress bar. Never one long server call (4,512 employees × 12 months would time out and lock rows).
- **D6.3 — Shadow runs never create `hr.payslip` records.** Results live in shadow models only. The engine is exercised via the same `_evaluate_rules_with_dependencies` path payslips use, but persistence is quarantined — a shadow run must be droppable without a trace.
- **D6.4 — Historical results enter through the existing multisheet reader** (`ExcelConnector.load_workbook_multisheet` + `HeaderDetector`), NOT a new parser. A results workbook is structurally identical to a formula workbook (employees × components); the only new step is mapping result columns → existing component codes, which reuses the import preview's mapping UX.
- **D6.5 — Tolerance is per-component, defaulting per number_format.** Currency components default to ±1 unit (rounding-mode differences), percentages ±0.0001, counts exact. Stored on the shadow run, editable before re-compare (re-compare is pure DB work — no recompute needed).
- **D6.6 — Clustering is deterministic first, AI-narrated second.** Group discrepancies by (component_code, period, sign-of-delta, |delta| bucket). The LLM (via Phase-1 `_llm_chat`) only *names* clusters ("banker's rounding on OT in March") — grouping itself never depends on AI.

### Data model (new file `pb_hr_payroll_formula/models/shadow_run.py`)

```
hr.formula.shadow.run
  name, config_id (m2o hr.formula.config), state: draft/importing/mapping/computing/compared/certified
  period_ids (o2m shadow.period), tolerance_json (Text)
  employees_total, values_total, values_matched, confidence (Float, computed)
  certificate_attachment_id (m2o ir.attachment)

hr.formula.shadow.period            # one per month imported
  run_id, period_label, date_start, date_end, source_sheet_name
  employee_count, status: pending/computed/compared

hr.formula.shadow.line              # one per employee-period
  period_id, employee_ref (Char — the workbook's key), employee_id (m2o, resolved)
  input_values_json, expected_values_json, computed_values_json
  match_state: matched/discrepant/error, discrepancy_count

hr.formula.shadow.discrepancy       # one per mismatched cell, cluster-keyed
  line_id, component_code, expected (Float), computed (Float), delta (Float)
  cluster_key (Char, computed: code|period|sign|bucket), cluster_id (m2o shadow.cluster)

hr.formula.shadow.cluster
  run_id, cluster_key, discrepancy_count, sample_line_ids
  cause_label (Char — AI-suggested or manual), resolution: pending/fixed/accepted/wontfix
  fix_note (Text)
```

### Work plan

| Task | Files | AC |
|---|---|---|
| T6.1 Models + access rules | `models/shadow_run.py`, `security/ir.model.access.csv` | Module upgrades; demo smoke: create/drop a run leaves no orphans |
| T6.2 Extract `comparison.py` helper from sample-data validation; refactor `formula_sample_data.py` to use it | `formula_engine/comparison.py` | Existing sample verdicts unchanged on the VN demo configs (regression: run all samples before/after, identical verdicts) |
| T6.3 Results importer: workbook → periods/lines; column→component mapping step reusing preview-line UX; employee resolution by ref with unmatched report | `wizards/shadow_import_wizard.py` | 12-month VN demo export re-imports with 100% employee match; an alien column lands in "unmapped" not silently dropped |
| T6.4 Chunked recompute + compare: `prepare_shadow(run_id)` → `compute_shadow_batch(payload)` (clone the payrun pattern) calling `_evaluate_rules_with_dependencies` per line, then `comparison.py` per component | `models/shadow_run.py` | 4.5k × 1 month completes with progress bar, no request >30 s; re-running a batch is idempotent |
| T6.5 Clustering + confidence | `models/shadow_run.py` | Seeded discrepancy fixture (change one rate, recompute) produces exactly one cluster covering all affected lines |
| T6.6 Cockpit UI: run list, progress, cluster triage (accept / open in studio / adjust tolerance), drill to line detail | new client action in `pb_formula_studio` or `pb_shadow_run` module, kit-styled | Keyboard-navigable cluster triage; "open in studio" lands on the offending component |
| T6.7 Certificate: QWeb PDF of scope, confidence, cluster resolutions, sign-off names | `report/shadow_certificate.xml` | PDF renders with real run data; immutable snapshot stored as attachment |
| T6.8 AI cause naming (optional rung) | reuse `_llm_chat` | With no key: clusters show raw key; with key: names appear; failure silent |

**Verification fixture (build once in pb_demo):** generate a "historical" workbook by exporting the demo world's computed June payslips to Excel, then (a) import unmodified → expect confidence 100%; (b) perturb one rate in the workbook → expect exactly the affected cells in one cluster. This gives a ground-truth harness for the whole feature.

### S3 — Skeleton: compare + cluster engine (the risky spot)

```python
# pb_hr_payroll_formula/formula_engine/comparison.py
"""Single source of truth for expected-vs-computed comparison.
Extracted from hr.formula.sample.data._compute_validation — keep semantics
IDENTICAL (numeric coercion incl. '1,234.5' strings, blank == missing)."""

def coerce_number(value):
    ...  # moved verbatim from formula_sample_data.py:200 (_coerce_number)

def compare_values(expected: dict, computed: dict, tolerance: dict) -> list:
    """Return [{'code', 'expected', 'computed', 'delta'}] for mismatches only.
    tolerance: {code_or_'*': abs_tolerance}. Missing computed value for an
    expected code IS a mismatch (delta=None) — silence is the enemy."""
    out = []
    for code, exp_raw in expected.items():
        exp = coerce_number(exp_raw)
        if exp is None:
            continue                      # non-numeric expected: skip, don't guess
        comp = coerce_number(computed.get(code))
        tol = tolerance.get(code, tolerance.get('*', 0.5))
        if comp is None or abs(comp - exp) > tol:
            out.append({'code': code, 'expected': exp, 'computed': comp,
                        'delta': None if comp is None else comp - exp})
    return out


# models/shadow_run.py — chunked drive (mirror pb_payrun_wizard.py:170/211)
class ShadowRun(models.Model):
    _name = 'hr.formula.shadow.run'

    @api.model
    def prepare_shadow(self, run_id):
        run = self.browse(run_id)
        line_ids = run.period_ids.mapped('line_ids').filtered(
            lambda l: l.match_state == 'pending').ids
        return {'line_ids': line_ids, 'total': len(line_ids)}

    @api.model
    def compute_shadow_batch(self, payload):
        """One chunk (~50 lines). Idempotent: recomputing a compared line
        just overwrites its result. NEVER creates hr.payslip records (D6.3)."""
        lines = self.env['hr.formula.shadow.line'].browse(payload['line_ids'])
        run = lines[0].period_id.run_id
        tol = json.loads(run.tolerance_json or '{}')
        rules = run.config_id.rule_ids          # fetch once per chunk, not per line
        for line in lines:
            inputs = json.loads(line.input_values_json or '{}')
            computed, _log = line._evaluate_rules_with_dependencies_for(rules, inputs)
            mismatches = comparison.compare_values(
                json.loads(line.expected_values_json or '{}'), computed, tol)
            line.write({...})                    # computed json, match_state, count
            self._write_discrepancies(line, mismatches)
        return {'done': len(lines)}

    def _cluster_key(self, d, period_label):
        sign = '+' if (d['delta'] or 0) >= 0 else '-'
        mag = d['delta'] and min(int(math.log10(abs(d['delta'])) + 1), 9) or 0
        return f"{d['code']}|{period_label}|{sign}|{mag}"   # deterministic, D6.6
```

---

## F7 — Formula version history with token diff · ~1.5 weeks

### Decisions

- **D7.1 — Version capture lives in ONE model-layer funnel, not in the UI.** All formula mutations flow through a small set of `pb.formula.studio` methods (`save_formula:317`, `save_component:400`, `update_component:334`, `bulk_update_components:603`, `add_component:464`) plus the import's rule creation. Add a single `_snapshot_rule(rule, reason)` helper on `hr.formula.rule` and call it from a `write` override on the rule itself **guarded to formula-bearing fields** — so even future callers (imports, shell fixes) are captured. Snapshot BEFORE the write (store the outgoing state).
- **D7.2 — Versions are append-only rows, not chatter.** `mail.thread` tracking produces prose; diffing needs structure. New model `hr.formula.rule.version` with the full field snapshot as JSON + the formula as text. Chatter can be added later *from* this data, never instead of it.
- **D7.3 — Token diff is computed on read, not stored.** Reuse the studio's `_tokenize` (line 108): tokenize old and new formulas, run a standard LCS diff over token streams, render insert/delete/replace runs as chips. Storing diffs would denormalize what a pure function derives.
- **D7.4 — Config snapshots are version sets, not copies.** "Compare config v(activation N) to now" = for each rule, its latest version at each activation timestamp. Activation events (existing lifecycle `cfg_activate`) write a `hr.formula.config.milestone` row (config_id, name, timestamp) — comparisons anchor to milestones.

### Data model (`pb_hr_payroll_formula/models/formula_rule_version.py`)

```
hr.formula.rule.version
  rule_id (m2o, index, ondelete=cascade), config_id (related, store)
  seq (Integer, per-rule monotonic), user_id, create_date
  excel_formula (Text), snapshot_json (Text: name/code/category/type/format flags)
  reason (Selection: edit/bulk/import/fill/restore/lifecycle), note (Char)

hr.formula.config.milestone
  config_id, name (e.g. "Activated v3"), milestone_date, user_id
```

### Work plan

| Task | AC |
|---|---|
| T7.1 Version model + `write` override on `hr.formula.rule` guarded to `{excel_formula, code, name, category_id, column_type, number_format, appears_on_payslip}`; skip no-op writes; batch-safe (one version row per changed rule per write call) | Editing via grid, card, bulk-edit and drag-fill each produce exactly one version row with the correct `reason`; a pure `sequence` write produces none |
| T7.2 `get_rule_history(rule_id)` + `diff_versions(rule_id, seq_a, seq_b)` RPCs; LCS over `_tokenize` output | Diff of `=P*0.10` → `=P*0.12` returns one `replace` run covering only the number token |
| T7.3 Version rail UI on the editor card + grid context action: list, who/when/reason, chip-rendered diff, "Restore" (writes old formula → itself creates a `restore` version) | Restore round-trips; the rail shows the restore as a new entry, history never rewrites |
| T7.4 Milestones on `cfg_activate` + "Compare to activation" view (changed rules only, each with its diff) | Activating, changing 2 rules, comparing → exactly those 2 appear |

### S4 — Skeleton: capture hook + token LCS (the risky spot)

```python
# pb_hr_payroll_formula/models/formula_rule.py  (addition)
VERSIONED_FIELDS = {'excel_formula', 'code', 'name', 'category_id',
                    'column_type', 'number_format', 'appears_on_payslip'}

def write(self, vals):
    tracked = VERSIONED_FIELDS & set(vals)
    if tracked and not self.env.context.get('skip_formula_version'):
        reason = self.env.context.get('formula_version_reason', 'edit')
        Version = self.env['hr.formula.rule.version'].sudo()
        for rule in self:
            # snapshot OUTGOING state; skip no-ops so bulk writes stay clean
            if all(self._fields[f].convert_to_write(rule[f], rule) == vals.get(f)
                   for f in tracked):
                continue
            Version.create({
                'rule_id': rule.id,
                'seq': rule._next_version_seq(),
                'excel_formula': rule.excel_formula or '',
                'snapshot_json': json.dumps(rule._version_snapshot()),
                'reason': reason,
            })
    return super().write(vals)
# Callers set context: save_formula → reason='edit'; bulk_update_components →
# 'bulk'; translate_formula commit → 'fill'; import execute → 'import' (and the
# import's initial create is NOT versioned — version 0 is implicit creation).

# pb_formula_studio/models/pb_formula_studio.py  (addition)
@api.model
def diff_versions(self, rule_id, seq_a, seq_b):
    """Token-level LCS diff, rendered as runs for chip display."""
    va, vb = self._version_formulas(rule_id, seq_a, seq_b)
    A = self._tokenize_text(va)   # thin wrapper over _tokenize's lexer
    B = self._tokenize_text(vb)
    # Standard LCS table over token *values*; emit runs:
    #   {op: 'equal'|'insert'|'delete', tokens: [...]}
    # Merge adjacent delete+insert into 'replace' — reads as "0.10 → 0.12".
    ...
    return {'runs': runs, 'a_label': ..., 'b_label': ...}
```

**Gotcha to encode in tests:** drag-fill commits N formulas in a loop — each target rule must get its own version row, and the whole fill must be one `reason='fill'` batch (assert count == N, not 1 and not 2N).

---

## F8 — Simulate-before-activate · ~1.5 weeks

**What:** any draft change (or whole draft config vs the active one) runs against last period's real inputs for every employee; UI shows a delta distribution, biggest movers, and zero-change count *before* activation.

**Decisions.**
- **D8.1 — Simulation = shadow-run machinery with a different expected-side.** Expected = last period's `formula_computed_values` (already stored as JSON on every payslip by `hr_payslip_formula.py`); computed = re-evaluation with the DRAFT rule set. Reuse `comparison.py` and the chunked drive from F6 — simulation is F6 with `expected_source='last_payrun'`. Build F6 first; F8 becomes ~1 week.
- **D8.2 — Draft evaluation is an overlay, never a write.** `simulate(config_id, overrides)` where `overrides = {rule_id: draft_formula}` evaluates with substituted formulas in memory (the evaluator already takes a rules list — construct dicts/namedtuples, don't write records). This also powers grid scenario columns (F14) and future what-if sliders.
- **D8.3 — Distribution is computed server-side** (histogram buckets + top-N movers + counts), shipped small; the client renders (Chart.js already in the stack via PayAI charts).

**Work:** `simulate_prepare` / `simulate_batch` RPCs on `pb.formula.studio`; results in a transient `hr.formula.simulation` (+lines for movers only — don't persist 4.5k rows of zeros); "Simulate" button on the lifecycle rail; histogram + movers table + "N employees unchanged" banner in a modal surface.
**ACs:** editing one division-scoped allowance shows deltas ONLY for that division's employees; a no-op edit shows 100% unchanged; runtime for 4.5k employees under ~2 min with live progress; abandoning simulation leaves no residue.

## F9 — Payslip Studio v1 · ~2 weeks

**Decisions.**
- **D9.1 — New module `pb_payslip_studio`** (cockpit pattern: client action + kit styling), reading/writing `hr.formula.rule` payslip fields. No new "payslip definition" model in v1 — the rule graph stays the single source of truth (vision: grid and payslip are two lenses).
- **D9.2 — Sections become a first-class model** `hr.payslip.section` (config_id, name EN/VI, sequence, color_key, collapse_when_empty Boolean). `hr.formula.rule` gains `payslip_section_id` (m2o) + `payslip_sequence` (Integer) + `visibility_rule` (Selection: always/when_nonzero/never) — replacing ad-hoc use of `payslip_identifier` for grouping (migration: seed sections from existing distinct `payslip_identifier` values; keep the old field populated for report compatibility until reports are ported).
- **D9.3 — Drag-drop via native HTML5 DnD** inside the OWL canvas (tray ↔ sections, reorder within section). No external DnD lib (CSP + asset weight); the payslip canvas is a list-of-lists, well within native DnD.
- **D9.4 — Preview renders through the real engine**: right pane shows the slip for a chosen sample (reuse `compute_preview`) with visibility rules applied; print preview reuses the QWeb payslip report with a `preview=1` context.

**Work:** section model + rule fields + migration hook; canvas component (tray = rules with `visibility_rule='never'` or no section; sections editable inline; drop updates `payslip_section_id`/`payslip_sequence` via one RPC `move_component_to_section`); sync check — flipping `appears_on_payslip` in the grid moves the chip to/from the tray on next load.
**ACs:** drag round-trip persists and survives reload; VN/EN label toggle affects canvas and print preview identically; a `when_nonzero` component with zero sample value renders greyed in canvas and absent in print preview; empty section with `collapse_when_empty` absent in print preview.

## F10 — Unified Mapping Canvas kit · ~2 weeks

**Decisions.**
- **D10.1 — One OWL component `MappingCanvas` in a new shared kit** (`pb_mapping_kit` or inside `pb_import_kit`), fed by an **adapter contract** — the canvas knows nothing about payroll:
  ```js
  props: {
    leftItems:  [{id, label, sublabel, meta}], rightItems: [...],
    wires:      [{leftId, rightId, state: 'accepted'|'suggested'|'error',
                  confidence, transform}],
    onAccept(wire), onReject(wire), onDraw(leftId, rightId),
    onEditTransform(wire), onTest()   // each adapter implements against its model
  }
  ```
- **D10.2 — Four adapters, shipped in this order:** (1) mid→end cycle (server data already exists from Phase-1 T4.1/T4.2 — suggestions map 1:1 to wires), (2) API field mapping (T4.3's field browser feeds `leftItems`), (3) import column mapping (preview lines), (4) employee→scheme (rules + coverage preview, needs its own rule model — smallest new server surface: `hr.formula.scheme.assignment` with domain-style condition + config_id + preview RPC).
- **D10.3 — Wires are SVG paths in a positioned overlay** recomputed from item DOM positions on scroll/resize (throttled via rAF). Suggested = dashed + confidence badge; error = red + tooltip; transform = badge mid-wire opening a popover.

**ACs:** the same `MappingCanvas` file renders all four surfaces with zero payroll imports in the kit module; keyboard path exists (focus left item → Enter → focus right item → Enter draws a wire); 200-item boards stay smooth (virtualize columns if not).

## F11–F15 — Remaining Tier-2 (design blocks)

**F11 Typed cells (~1 week).** Extend the Phase-1 grid: cell editor chosen by `number_format`/`column_type` — percent editor (display ×100, store fraction), currency (thousands separators display-only), bracket-table cells. Bracket tables are the real content: new model `hr.formula.rate.table` (config_id, name, bracket lines: lower/upper/rate) + converter support for a `BRACKET(table_code, value)` pseudo-function that compiles to nested comparisons via the existing converter pipeline. **Decision:** brackets compile at rule-save time into the stored python_formula — the evaluator stays table-ignorant. AC: a PIT bracket table edited in the bracket editor changes computed tax correctly; the compiled formula survives export/import round-trip.

**F12 Raw-Excel mode (~3 days).** Toggle on card + grid formula bar already edits raw Excel — the card's chip view gains an "edit as text" mode using the same textarea + `validate_formula_live` path the grid uses. Persist preference per user (`ir.config_parameter` per-user or localStorage). AC: both modes write identical `excel_formula`; switching modes mid-edit preserves the buffer.

**F13 Problems rail + lint + rename-refactor (~1.5 weeks).** Server `get_problems(config_id)`: aggregates invalid formulas, cycles (from `get_intelligence`), unused, magic-number lint (numeric literals ≥ threshold occurring ≥2× → "extract a constant"), missing-on-payslip totals. Rename-refactor: `rename_component(rule_id, new_code)` rewrites referencing formulas server-side in one transaction (reuse `_expand_refs` machinery to find references by column letter — codes don't appear in formulas, letters do, so renaming *codes* is metadata-only; renaming *column letters* is forbidden — document this asymmetry in the UI). AC: problems list count matches individually verified issues on a seeded messy config; rename of a code referenced by 5 formulas leaves all 5 evaluating identically.

**F14 Scenario columns (~1 week, after F8).** Grid action "duplicate as scenario" creates an overlay entry (client-state + `hr.formula.scenario` persistence: config_id, name, overrides_json) rendered as a ghost column pair (base | scenario) using F8's overlay evaluation for the value row. Promote = write override into the real rule (versioned, `reason='edit'`); discard = delete row. AC: scenario column edits never touch `hr.formula.rule` until promote; two scenarios on one component render side-by-side.

**F15 Comments & annotations (~1 week).** `mail.thread` on `hr.formula.rule` is the cheap 80%: enable chatter in a side panel on card + grid (message_post with component context), plus an `is_review_note` flag surfacing in the Problems rail until resolved. Defer pinned-to-token anchoring to Tier-3 (needs version-stable anchors; design after F7 usage patterns emerge). AC: a note left in grid shows on the card and in the rail; resolving clears it from the rail, not from history.

---

# PART B — Tier-3 design briefs

Each brief: concept → architecture → key locked decision → dependencies → design-complete trigger.

**B1 Execution replay.** Step through a real payslip's computation. Architecture: the evaluator already produces a computation log; upgrade `_evaluate_rules_with_dependencies` to optionally emit a structured trace `[{col, expr, inputs: {col: val}, result}]` (flag-gated, stored on demand — not on every payrun). Replay UI = grid overlay stepping through trace entries, filling the value row progressively. **Decision: trace is generated on-demand by re-evaluating one payslip's inputs, never persisted at scale.** Depends: grid (✅), F6's overlay habits. Trigger: F8 lands (same overlay evaluation core).

**B2 Scenario sandboxes (branch/merge configs).** Full-config branches vs F14's per-component overrides. Architecture: `copy()` of `hr.formula.config` with `parent_config_id` + `branch_state`; merge = three-way per-rule comparison (base activation milestone from F7, branch, current active) with conflict UI. **Decision: branch at config granularity, merge at rule granularity, F7 milestones are the merge base — no diff3 on text.** Depends: F7 (hard), F8 (simulation gate before merge). Trigger: F7 in production one month (need real version data to validate merge-base logic).

**B3 Release bundles + sign-off + audit narrative.** `hr.formula.release` groups version rows (F7) since the last milestone; reviewer surface = diffs + F8 simulation + test results in one screen; approval writes immutable milestone; narrative auto-drafted via `_llm_chat` from structured release data (deterministic fallback: templated changelog). **Decision: a release is a query over F7 versions, not a new capture path — never a second history.** Depends: F7, F8. Trigger: both in production.

**B4 Legislation packs.** Country starter configs as data modules (`pb_pack_vn_2027`, …): config + rules + rate tables (F11) + sample data with expected values as executable acceptance tests. **Decision: packs are importable data + tests, not code modules — installing = importing a validated config snapshot; AI drafts pack updates as F7-versioned proposals, humans certify against the pack's own test suite.** Depends: F11 rate tables, F7. Trigger: second country onboarded manually (pattern extraction needs two real instances).

**B5 Scheme variants (Figma model).** Master config + variant configs holding only overrides (sparse `hr.formula.variant.override`: variant_id, rule_code, field, value). Resolution merges master + overrides at evaluation-set build time. **Decision: overrides are sparse per-field rows, not config copies — updating master propagates automatically; a variant's grid shows override badges.** Depends: F7 (override provenance), B2 experience. Trigger: first real multi-division client with ≥70% shared rules.

**B6 Bureau cockpit.** Multi-client board: per-config health (Phase-1 score), payrun calendar state, open problems (F13), pending releases (B3). Architecture: read-only aggregation cockpit + template cloning (`copy()` a validated config across companies with employee-mapping wizard). Depends: F13, B3; multi-company audit of `pb_hr_payroll_formula` (company_id discipline) is the real work — schedule a 2-day audit first. Trigger: second paying client on one server.

**B7 Client review portal.** Portal-user read-only view of a config (rendered cards + payslip preview) + commenting (F15 chatter with portal access) + release approval (B3 sign-off from the client side). **Decision: reuse Odoo portal framework (`pb_demo_portal` patterns), not a separate app; share = signed token URL scoped to one config + one release.** Depends: F15, B3. Trigger: B3 lands.

**B8 What-if sliders + cost projection.** Thin UI over F8's overlay simulation: slider varies an input/constant, debounced `simulate_batch` on a sampled employee subset (~200, stratified by division) for instant feel, full run on release. Annualized employer cost = sum of employer-side components × 12 with proration flags. **Decision: interactive mode samples, commit mode is exhaustive — never present sampled numbers as final.** Depends: F8. Trigger: F8 lands.

**B9 Dependency graph as navigation.** Promote the existing flowchart to a full-screen force/hierarchical layout of `get_intelligence` nodes with category filters, critical-path emphasis, click-to-edit. **Decision: layout client-side (elkjs candidate — CSP-safe if vendored into assets), data unchanged from Phase 1.** Depends: nothing hard. Trigger: user demand signal; it's polish until then.

---

# Sequencing & effort (Tier-2)

| Order | Feature | Effort | Hard dependency |
|---|---|---|---|
| 1 | F7 Version history | 1.5 w | — (do first: everything after wants provenance) |
| 2 | F6 Shadow Parallel Run | 3 w | comparison.py extraction |
| 3 | F8 Simulate-before-activate | 1.5 w → ~1 w | F6 machinery |
| 4 | F13 Problems rail + lint + rename | 1.5 w | — |
| 5 | F10 Mapping Canvas kit | 2 w | Phase-1 T4.x server data |
| 6 | F9 Payslip Studio v1 | 2 w | — |
| 7 | F11 Typed cells + rate tables | 1 w | — |
| 8 | F14 Scenario columns | 1 w | F8 |
| 9 | F12 Raw-Excel mode | 3 d | — |
| 10 | F15 Comments | 1 w | — |

~15 dev-weeks for Tier-2. F6+F7 first two slots is deliberate: they are the trust core the sales narrative rests on, and F8/F14/B1/B2/B3 all reuse their machinery.

# Verification strategy (applies to every Tier-2 feature)

1. Ground-truth fixtures in pb_demo (the F6 export-perturb-reimport harness doubles for F7/F8 regression).
2. Every feature ends with the 30.5k-payslip batch recompute — byte-identical `formula_computed_values` proves the engine core untouched.
3. Chrome MCP keyboard-only pass on each new surface (per the accessibility commitment).
4. Version-capture completeness test: after any feature merges, run one edit through every mutation path (card, grid, bulk, fill, import, restore) and assert F7 captured all six.
