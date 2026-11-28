# BLUEPRINT Phase B4 — Connect: source mapping, payslip layout, approvals

Read `docs/handovers/BLUEPRINT_LEDGER.md` FULLY (rulings BP-R8, R9, R11; gotchas through B3),
the three phase reports (B1–B3), and `BLUEPRINT_PLAN.md` §"Step 3 · Connect" and §"Reuse".
B1–B3 code is the base.

## 1. Goal (plain English)

Step 3 becomes the place where a person connects the configuration to the outside: where the
pay inputs come from, what the payslip looks like, and how approvals work. Two of the three are
doors into tools that already exist (the mapping screen and the payslip designer), opened **on
this draft**, returning **to this journey**, and reporting back a plain status line ("12 of 19
inputs have a source", "31 of 38 components placed · 7 in the tray"). The third is an honest
information card. Each task can be skipped and revisited; skipping never weakens anything.

## 2. Scope — in
- Connect step UI: three task cards with status pills, coverage lines, primary door, Skip for
  now, "Skip the rest & review outputs", the company/configuration identity strip.
- `bp_readiness(config_id)` RPC (mapping coverage across the three lanes + payslip placement)
  and the status semantics (`optional_status_json`): `not_started | in_progress | configured |
  skipped | needs_review`, with `needs_review` set automatically when components change after a
  task was configured.
- Mapping Studio round-trip (`pb_config`, `pb_mode`, `pb_back`); Payslip Studio round-trip via
  a new Formula Studio arrival key `pbfs_open_payslip` + auto-return on close when `pb_back` is
  present (a minimal, registry-probed seam in `formula_studio.js`).
- Approvals info card (owner decision: information only).
- Tests, deploy ×4, Chrome validation, commits, gotchas, report.

## 3. Scope — binding non-goals
- No approval-matrix model, no change to `pb_payruns`/`biz_approval_chain` (later program).
- No new mapping editor, no new payslip editor, no copying of either studio's code (BP-R8).
- No bilingual label editing UI beyond what Payslip Studio already offers (BP-R9).
- No outputs table / tests (B5), no VI (B6).

## 4. Design (bar: "extreme WOW, intuitive, out-of-this-world experience, best in class")

### 4.1 Connect step
Eyebrow "03 / CONNECT WHAT YOU NEED", H1 **"Connect what you need. Continue when ready."**,
lead "These tasks belong to this company and configuration. Set them up here, or skip
individually and come back through the configuration's Settings later."
Identity strip (white card, two chips): Company · Configuration (name + code) — so a person
always sees which draft the doors open on.

Three **task cards** in a row (stack at ≤1100px), each: Lucide icon in a `#EDEAF8` tile
(`arrow-left-right` / `layout-list` / `check-check`), title, status pill, two-line explanation,
a **coverage line** (live, from `bp_readiness`), primary button, "Skip for now" ghost link, and
a muted "Manage later: Settings → <name> · same configuration".

- **Source mapping** — "Connect a payroll system, spreadsheets or employee records to the
  inputs of this configuration." Coverage: "12 of 19 inputs have a source · 4 from the connected
  system · 6 from spreadsheets · 2 from employee records" (only the non-zero lanes named; zero
  inputs → "This configuration has no inputs to map yet"). Primary **Open source mapping** →
  `openHub(action, {tag:"pb_mapping_studio", context:{pb_config: cid, pb_mode:"journey"},
  back:{label:"New configuration", tag:"pb_blueprint", context:{config_id: cid, step:"connect"}}})`
  — by TAG (BP14). Guard: `registry.category("actions").contains("pb_mapping_studio")`, else the
  card explains the mapping screen is not installed (no button).
- **Payslip layout** — "Place the components on the payslip, name the sections, choose which
  values people see." Coverage: "31 of 38 components placed · 7 in the tray · 4 sections"
  (rules with `appears_on_payslip` and a `payslip_identifier` = placed; `appears_on_payslip` and
  no section = tray; sections = `hr.payslip.config` bound to the config). Primary **Open payslip
  designer** → `doAction({type:"ir.actions.client", tag:"pb_formula_studio", params:{config_id: cid,
  pbfs_open_payslip: true}}, {additionalContext:{pb_back:{label:"New configuration", tag:"pb_blueprint",
  context:{config_id: cid, step:"connect"}}}})`.
- **Approvals** — pill "Already in place" (teal), text: "Pay runs already follow Officer → HR →
  Finance approval. Custom approval rules per configuration are coming in a later release." No
  button, no skip. A small "How approvals work today" link opens a kit modal with three lines
  describing the existing chain in plain words (read the labels from `pb_payruns` if it exposes
  them; otherwise the three tier names).

Status pills: **Not started** (grey) · **In progress** (purple, "you opened it but nothing is
connected yet" — set when the door was opened and the coverage is still zero) · **Done**
(green — set when coverage > 0 on return, or the person presses "Mark as done" which appears
once coverage > 0) · **Skipped** (amber outline, with "Undo" turning it back) · **Needs another
look** (rose outline: a formerly Done task whose inputs/components changed since — the card
says what changed: "3 components were added since you mapped: OTWD, OTWE, OTHO").
Footer: Back · **Continue to outputs →**; plus **Skip the rest & review outputs** (ghost) which
marks every Not-started task Skipped (never touches Done/In progress) and continues.
Returning from a studio lands on this step with the returned card briefly highlighted (purple
ring fading over 1.2 s) and its coverage line freshly loaded.

### 4.2 Zero dead-ends
studio not installed → explanation, no button · draft finished/active → doors still work but the
skip links disappear · Mapping Studio swaps an invalid config (`defaults.fell_back` includes
`config`) → the journey warns before opening if `mapping_pickers` reports the draft is not
selectable, with the reason · Payslip Studio has no samples → it already handles that; the
coverage line still works · a person skips everything → Continue works; Finish (B6) will list the
skipped tasks · a returning arrival with a stale revision → reload prompt.

## 5. Server
- `bp_readiness(config_id)` → `{ok, mapping:{inputs, mapped, by_lane:{api, excel, records, cycle},
  unmapped:[{code,name}], changed_since:[codes]}, payslip:{total, placed, tray, sections, removed_placed:[codes],
  changed_since:[codes]}, status:{mapping, payslip, approvals:'info'}, revision}`.
  Inputs = `rule_ids.filtered(column_type=='input')`; mapped = union of
  `hr.integration.field.mapping` (`target_rule_id in inputs`, active), `hr.payslip.import.mapping`
  (`salary_structure_id = config`, `component_id in inputs`), `hr.payroll.cycle.component.mapping`
  (`end_cycle_config_id = config`, target component in inputs) — reuse the pattern at
  `pb_formula_studio.py:7104-7110`. Verify each model's exact field names before coding (ledger
  §Mapping lanes) and state them in the report.
- Status bookkeeping in `optional_status_json`: `{mapping:{status, opened_at, done_at, snapshot:[input
  codes at done]}, payslip:{status, …, snapshot:[placed codes]}, approvals:{status:'info'}}`.
  `needs_review` = status was `configured` and the current input/component set ≠ snapshot; the
  diff is `changed_since`. RPCs: `bp_task_open(config_id, task)` (stamps `opened_at`, sets
  in_progress if not_started), `bp_task_set(config_id, task, status)` (configured|skipped|not_started;
  configured requires coverage > 0 server-side), `bp_skip_rest(config_id)`.
- Return door: when the journey is opened with `params.step == "connect"` it lands on the step
  and calls `bp_readiness`. Mapping Studio already honours `pb_back` (`HubBackChip`).

## 6. Formula Studio seam (minimal, registry-probed, listed in the report)
In `formula_studio.js` arrival block (after `pbfs_open_people_mapping`): read `pbfs_open_payslip`
from params or context → after `load(cfgId)`, `await this.openPayslip()`. In `closePayslip()`:
if the action carried `pb_back` (use `hubBack(this.props)`) **and** the arrival had
`pbfs_open_payslip`, navigate back through the same door the chip uses (call the chip's logic,
do not re-implement: expose a tiny `goBack(back, actionService)` helper from `pb_hub/hub_nav.js`
if one is not exported yet, or render the chip and click-equivalent it) so closing the designer
returns to the journey automatically. The old behaviour (close → stay in the grid) remains when
no `pb_back` is present.

## 7. Tests
1. `bp_readiness` counts: seed Complete, create one API mapping, one record mapping, one cycle
   mapping to inputs → `mapped 3`, by-lane correct; a mapping to a formula rule is ignored.
2. Payslip placement: move two rules into a section via `move_component` → placed 2, tray N−2,
   sections 1; delete the section → back to tray.
3. Status machine: not_started → opened → in_progress; coverage > 0 + set configured → Done;
   add an input via B2 RPC → needs_review with `changed_since == [code]`; skip → skipped;
   skip_rest touches only not_started.
4. `bp_task_set(configured)` with zero coverage → refused with a plain reason.
5. Source-assertion tests (pattern `test_one_mapping_home.py`): the Connect step opens both
   studios BY TAG with `pb_back` carrying `config_id` + `step:"connect"`; `pbfs_open_payslip` is
   read from params OR context; the studio's `closePayslip` returns only when `pb_back` exists.
6. White-label + vocabulary gate over the new files; the approvals text has no tier names that
   are not on screen elsewhere.

## 8. Deploy + acceptance (bump `pb_blueprint` 19.0.1.3.0, `pb_formula_studio` +1)
1. Connect step renders three cards with identity strip; statuses Not started; coverage lines
   with real numbers on a Complete draft.
2. Open source mapping → Mapping Studio on the draft (header FROM/TO names the draft), Journey
   tab, back chip "New configuration"; wire one spreadsheet column (or an employee field) to an
   input; back chip → journey at Connect, card highlighted, coverage 1 of N, status In progress →
   "Mark as done" → Done.
3. Add a component on the Components tab → back to Connect → mapping card "Needs another look"
   naming the new input; open + return → Done again after re-mark.
4. Open payslip designer → Formula Studio opens WITH the designer overlay already open on the
   draft; move a component into a section; close the designer → **journey again** at Connect;
   coverage "1 placed"; status In progress → mark done.
5. Remove a placed component on the Components tab → payslip card "Needs another look" listing it.
6. Skip for now on mapping → Skipped pill + Undo; Skip the rest & review outputs → only
   Not-started tasks flip; Continue lands on Outputs (thin panel from B1).
7. Approvals card: pill, text, "How approvals work today" modal; no button.
8. Uninstall-guard: hide the mapping door when `pb_mapping_studio` is absent from the registry
   (simulate by deleting the registry entry in the console) → explanation, no dead button.
9. Refresh on Connect → same statuses; other-company draft → refusal (B1 behaviour intact).
10. 390 px: cards stack; doors reachable; back chip visible in both studios.
11. abm: the same round-trips on a fresh draft; all four DBs on the new versions; gates green.

## 8b. Addendum after the B3 report (binding)
- **Baseline live on all four DBs**: `pb_blueprint 19.0.1.2.0`, `pb_hr_payroll_formula 19.0.1.124.0`,
  `pb_pay_delivery 19.0.1.2.0` (B3 added a `pb_back` chip there — the same idiom your studios
  already honour). Server files now: `blueprint.py, blueprint_studio.py, blueprint_components.py,
  blueprint_tax.py, blueprint_calendar.py, payday.py, recipe_*.py, essentials_recipes.py,
  workbook_vocabulary.py, formula_*_ext.py`. Put B4's server code in a new `blueprint_connect.py`
  (`_inherit = 'pb.blueprint.studio'`), reusing `_guard`, `_plain`, `_revision_guard`.
  Client: add `step_connect.js` + `xml/connect.xml`; `step_thin.js` must no longer be used for
  `connect` (only `outputs`/`test` remain thin until B5).
- **Fix BP36 in this phase**: four hoot tests in `static/tests/blueprint_steps.test.js` throw
  "translations have not been loaded" when they stringify a `_t()` label. Resolve by asserting on
  keys/structure rather than translated words, or by mocking the translation service the way
  hoot's own web tests do (`@web/../tests/web_test_helpers` — check for `patchTranslations` or
  similar). All hoot tests must be green in the report (state the count).
- **Demo estate**: three demo configurations now live on payobook ("Vietnam · Monthly payroll
  (guided setup)", "… — setup in progress", "Vietnam · Complete (guided setup demo)" — 111
  components, finished). Use the last one for Connect walkthroughs where a rich configuration
  helps; never delete or rename them; discard your own drafts through the product path.
- **Gotchas BP29–BP36** are in the ledger (incl. the white-label gate now scanning RPC payloads —
  keep it green for `bp_readiness` and the approvals modal text; `pb_back` on the Pay & Deliver
  cockpit; the compiler's `inherit` semantics). Read before coding.
- Owner questions from B3 (§13 of its report) are logged for closeout — do not act on them.

## 9. Report (`docs/handovers/BLUEPRINT_PHASE_B4_REPORT.md`)
Results 1–11; exact mapping-model field names used per lane; the `optional_status_json` shape;
the studio seam lines (before → after); how auto-return on designer close is wired; gotchas;
self-score; deferred items with reasons.
