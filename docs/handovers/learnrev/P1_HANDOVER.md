# LEARNREV P1 — the content engine: help read from the product (handover for Opus)

Program: `docs/handovers/learnrev/LEARNREV_PROGRAM.md` (standing rules verbatim there). Ledger:
`LEARNREV_LEDGER.md` (LR-R1…R7, LR1–LR10). Design page: `docs/design/learn_revamp/LEARN_REVAMP_DESIGN.html`
("The content engine" section is the spec's intent; this document is the spec).

Work in the git worktree you are given (branch `learnrev-p1`), never in the main tree. **No deploy in this phase.**
Tests run on a clone of payobook on the server. Fable merges and deploys after P0 lands.

## 0. Design bar (verbatim, binding)
"Extreme WOW, intuitive, out-of-this-world experience, best in class." P1 has no UI; its hero moment is the Guide
JSON for Component treatment: complete enough, in English AND Vietnamese, that a panel can draw six field cards
(what it is · choices · how it is filled · used by · if you change it), the "You are here" path, the live "Right now"
list and the doors to the lesson and walkthrough, with NOTHING hand-written except one sentence of purpose per
field. Zero dead ends: every guide call returns a usable answer or a named reason ("no manifest for this screen
yet", "no scheme selected"). Plain screen words in every authored sentence. Never the word "Odoo" in any string a
user can see. Score the report against this bar.

## 1. Scope
- **S1 Manifest registry.** A screen manifest is a Python dict that lives NEXT TO THE SCREEN, in the owning module,
  in a file named `learn_manifest.py` (e.g. `pb_formula_studio/learn_manifest.py` for `treatment` and `mapping`).
  `pb_learn` discovers them by importing `odoo.addons.<module>.learn_manifest` for every installed module that has
  one (no dependency inversion: product modules never import pb_learn). Schema in §3.
- **S2 `learn.guide`** AbstractModel in `pb_learn/models/learn_guide.py` (clone the shape of `learn.helper` /
  `learn.intent`: AbstractModel, no ACL, `@api.model` methods, runs as the asking user, **never sudo** — grep test).
  `guide(screen_key, args=None)` returns the Guide JSON (§4) in the user's language; `rpc_guide` is its public
  wrapper. Facts come from `fields_get()` at call time (labels, help, selection labels — translated by the ORM), from
  the manifest (readers, how filled, consequences), from learn content (station, scenarios, glossary, hub names) and
  from the product's own place data (hub tab labels).
- **S3 Truth gate** test (`pb_learn/tests/test_guide_truth.py`, §6 T1): every manifest claim is checked against the
  code. A wrong field name, a choice that does not exist, a reader file that does not mention the field, a column
  header that is not in the screen's template, a missing Vietnamese sentence — each fails the build.
- **S4 Right-now providers** for `treatment` and `payruns` (§5): server methods, declared in the manifest, that read
  the screen's own state and return numbered things to do, each with the action a panel can wire.
- **S5 Manifests for 8 screens:** `treatment`, `mapping` (Connections tab), `runpayroll`, `payruns`, `payslips`,
  `approvals`, `dashboard`, `formula`. Deliver `treatment` end-to-end FIRST (manifest, guide, gate, provider, tests,
  VI), then the other seven. Where a cockpit's columns are not model fields (most are `_t` literals — ledger LR8),
  declare them as `derived` entries (§3) so the gate can still check the header text against the template.
- **S6 Vietnamese gaps closed in the product .po files** (ledger LR9): `pb_hr_payroll_formula/i18n/vi_VN.po` gets
  msgstr for `value_kind` (label, help, 9 choices), `payroll_signal` (label, help, 2 choices), `value_kind_source`,
  `net_role_source` and `component_type_source` (labels + choices), `imported_component_type` help, `net_role_detail`
  help. `pb_formula_studio/i18n/vi_VN.po` gets "Report group", "Run signal". Follow the PO rules used by ONECHAT OC4
  (`#. module:` + `#:` lines, parse gate). Product fix in the same commit: `_value_kind_options`
  (`pb_hr_payroll_formula/models/formula_config.py:2364-2375`) reads raw `field.selection` (English) while `pay_roles`
  and `signals` use `field._description_selection(self.env)` (:2464-2470) — make value kinds use
  `_description_selection` too so the board's Value type dropdown is translated.
- **S7 Lesson/anchor lint for the 8 screens** (truth gate part): the manifest lists `retired_labels` (for
  treatment: "Group", "Subtotal", "Tells the run"); the gate fails if `docs/tutorial_poc/author/data.js` lesson steps,
  scenario steps or `pb_learn/static/src/anchors.json` registry text for that screen contain one. **Fix the hits in
  this phase** (text only, EN+VI, then `gen_learn_data.py` → `git checkout pb_learn/i18n/vi_VN.po` afterwards — LR-R
  rule in the program doc; verify with `--check`). Known hit: anchors.json `tr-table` says "Group, Pay role,
  Subtotal, Tells the run, Value type" (LR10).

## 2. Binding non-goals
- No UI, no panel, no changes to the Coach drawer, Journey page, router (`learn_helper.py`), intents, scenario
  engine or PayAI. No new DB tables, no stored fields (content never lives in the DB — LEARNOS rule). No sudo. No
  deploy. Do not touch files P0 is changing (`ai_insight_chat.js`, `coach.js openLesson`, `learn_palette.js`,
  `component_treatment.js` LANE_LABELS, `resolve.py`, `formula_net_role.py` reasons) — if a P1 need overlaps, write it
  in the report instead.

## 3. Manifest schema (one dict per screen key; keys are learn screen keys from `learn_content.json`)
```python
# <module>/learn_manifest.py  —  MANIFESTS = {"<screen_key>": {...}}
"treatment": {
  "model": "hr.formula.rule",                      # model whose fields the rows show (None for KPI-only screens)
  "purpose": {"en": "...", "vi": "..."},           # ONE sentence; the only hand-written screen text here
  "path": {"tag": "pb_mapping_studio", "lens": "treatment"},   # resolved to labels + open action by learn.guide
  "before": [{"screen": "formula", "why": {"en": "...", "vi": "..."}}],   # how people get here
  "after":  [{"screen": "runpayroll", "why": {"en": "Recompute the run so the figures add up", "vi": "..."}}],
  "fields": [
    {"key": "pay_role", "field": "net_role",         # model field → label/help/choices from fields_get()
     "column": {"en": "Pay role", "vi": "Vai trò lương"},   # header AS SHOWN; gate checks it against the template
     "source_field": "net_role_source",             # marker that says who filled it (auto/user)
     "filled_by": {"en": "...", "vi": "..."},       # one sentence (how it gets filled)
     "choices_when": {"earning": {"en": "...", "vi": "..."}},   # optional per-choice guidance; keys ⊂ selection
     "used_by": [ {"label": {"en": "Pay run totals", "vi": "..."},
                   "ref": "pb_payruns/models/hr_payslip_run.py:_pb_bucket_sql",   # file:symbol, gate-checked
                   "via": "hr.payslip.line.pay_role"} ],                            # optional copied-field path
     "if_changed": {"en": "...", "vi": "..."},
     "anchor": "tr-table"},                         # data-coach anchor on the real screen (gate: exists)
    {"key": "lane", "derived": True, "column": {"en": "Comes from", "vi": "..."},
     "from": "pb_hr_payroll_formula/models/formula_config.py:_value_kind_lane",   # gate: file+symbol exist
     "values": {"calculated": {"en": "Calculated by a formula", "vi": "..."}, "feed": ..., ...},
     "how": {"en": "...", "vi": "..."}, "if_changed": {"en": "Read-only here; change it in Mapping › Connections.", "vi": "..."}},
  ],
  "actions": [ {"label": {"en": "Re-classify from the formulas", "vi": "..."},
                "method": "hr.formula.config.reclassify_from_formulas",   # gate: model + method exist
                "effect": {"en": "...", "vi": "..."}, "writes": True} ],
  "right_now": "hr.formula.config.learn_right_now",   # §5; None allowed
  "station": "treatment", "tasks": ["sc_treatment"], "terms": ["payRole", "subtotal", "valueType", "componentTreatment"],
  "retired_labels": ["Group", "Subtotal", "Tells the run"],
}
```
Rules: every authored text has BOTH `en` and `vi` (gate). Labels, help and choice labels are NEVER authored here —
they come from `fields_get()`; if a product label is wrong, fix it in the product field (`string=`/`help=`) and its
.po. `column` must equal (whitespace-normalised, case-sensitive) a string in the screen's template or a `_t()` in its
JS (gate reads the files as text; list the template/JS paths under `"templates": [...]` in the manifest).

## 4. Guide JSON (what `learn.guide.guide("treatment", {"config_id": 42})` returns)
```json
{"screen": {"key": "treatment", "name": "Component treatment", "purpose": "...",
            "path": [{"label": "Mapping", "open": {"xmlid": "pb_formula_studio.action_pb_mapping_studio"}},
                     {"label": "Component treatment", "open": {"xmlid": "...", "lens": "treatment", "lens_key": "pb_mode"}}],
            "before": [{"screen": "formula", "name": "Formula Engine", "why": "..."}], "after": [...]},
 "right_now": {"ok": true, "items": [ {"key": "needs_answer", "count": 3, "severity": "warn",
                 "text": "3 rows still need your answer on Pay role: Loan Installment, KPI Bonus, Incentive.",
                 "action": {"kind": "filter", "value": "review"}}, ... ]},
 "fields": [ {"key": "pay_role", "column": "Pay role", "label": "Net Pay Role", "help": "What the net pay formula does…",
              "choices": [{"value": "earning", "label": "Added to net pay", "when": "..."}, ...],
              "filled_by": "...", "source_values": [{"value": "auto", "label": "Worked out from the formulas"}, ...],
              "used_by": [{"label": "Pay run totals", "via": "hr.payslip.line.pay_role"}, ...],
              "if_changed": "...", "anchor": "tr-table"}, ... ],
 "actions": [...], "doors": {"station": "treatment", "lesson": "L9", "tasks": [{"key": "sc_treatment", "name": "...", "modes": ["watch","try"]}],
              "terms": [{"key": "payRole", "term": "pay role", "definition": "..."}]},
 "lang": "vi_VN", "missing": []}
```
`missing` lists what could not be resolved (e.g. `"right_now: no scheme selected"`) — a reason, never an exception.
Strings arrive in the user's language; `used_by.label` and all authored texts pick `vi` when `lang` starts with `vi`.
Path labels: hub name from `learn_content.json hubs[<tag>].name` + tab name from `hubs[<tag>].tabs[<lens>].name`
(precedent `pb_learn/static/src/engine/places.js:127-138 placeLabel`); the open action from
`hubs[<tag>].xmlid` + `lens_key` (precedent `places.js:213-236 openScreen`). LR7: `hub_mapping.tabs` lacks `desk`
(Connections) — add it in `data.js:8189-8232` (EN+VI) and regenerate (then restore pb_learn's vi_VN.po).

## 5. Right-now providers
A provider is `@api.model def learn_right_now(self, args)` on the screen's server model, returning
`[{"key","count","severity":"warn|info|ok","text":{"en","vi"},"action":{...}}]`, ordered by what to do first. It
runs as the user (the model's own access checks apply; `value_kind_board` already raises AccessError for non-officers
at `formula_config.py:2336-2344` — reuse that check, and turn an AccessError into `missing: ["right_now: no access"]`).
- **treatment** (`hr.formula.config.learn_right_now(args={"config_id"})`): (1) `needs_answer` = rows with
  `not net_role or net_role_confidence == 'review'` (`formula_config.py:2435-2436`, the board's `review_count`
  :2473) — name up to 3 components; action `{"kind":"filter","value":"review"}` (the board's chip filter,
  `component_treatment.js:130-146`); (2) `type_conflict` = `role_conflict_count` (:2474), action filter `conflict`;
  (3) `drift` = `drift_count` (:2475), action filter `drift`; (4) `recompute` = runs of this scheme computed BEFORE
  the scheme's last treatment change: there is no stale marker (LR10) — use `max(rule.write_date)` over the config's
  rules vs each run's `max(payslip.write_date)` for runs in `draft`/`approval_pending` whose payslips use this
  config; list up to 3 runs with action `{"kind":"open","xmlid":"pb_payhub.action_pb_pay_hub","lens":"runs"}`;
  (5) when nothing is pending: one `ok` item "Nothing needs you here. Save is enabled only when you change a row."
  Unsaved changes are client state (`component_treatment.js:68,148-150`); the panel adds them in P2.
- **payruns** (`pb.payruns.learn_right_now(args={})`): from the same data `get_board_data` builds
  (`pb_payruns/models/pb_payruns.py:42`, per-run `balance_ok/balance_gap/unsourced/awaiting_me/next_action`):
  (1) runs awaiting ME (`awaiting_me`) with action open the run; (2) runs whose figures do not add up
  (`not balance_ok`) → "open Component treatment for <scheme>"; (3) runs with unsourced components → Mapping ›
  Connections; (4) draft runs with a `next_action`; (5) `ok` item when the board is quiet.

## 6. Tests (numbered; all green before the report)
- **T1 truth gate** (`pb_learn/tests/test_guide_truth.py`): for every discovered manifest: model exists; each
  `field`/`source_field` in `fields_get`; `choices_when` keys ⊂ selection values; `used_by.ref` file exists and its
  text contains the symbol AND (the field name OR the `via` tail); `derived.from` file+symbol exist; every `column`
  appears in one of the manifest's `templates` files (whitespace-normalised); `anchor` exists in
  `pb_learn/static/src/anchors.json` (product block) or in the template as `data-coach="..."`; every authored text has
  non-empty `en` and `vi`; no "Odoo" (any case) in any authored text or any `fields_get` string the guide emits;
  `actions.method` resolves (`hasattr(self.env[model], name)`); `station`/`tasks`/`terms` keys exist in
  `learn_content.json`; `retired_labels` absent from that screen's lesson/scenario/anchor texts (data.js + anchors.json).
- **T2 guide treatment EN/VI**: with a fixture config holding ≥4 rules (one `review`, one hours-with-earning
  conflict), `guide("treatment", {"config_id"})` in `en_US` and `vi_VN`: 6 fields; `pay_role.choices` has 6 entries
  with Vietnamese labels under `vi_VN` ("Cộng vào thực nhận" for `earning`); `value_kind.choices` has 9 entries with
  Vietnamese labels (proves S6); `path` labels "Mapping" / "Component treatment"; `doors.station == "treatment"`.
- **T3 right_now treatment**: same fixture → items `needs_answer` (count 1, names the rule), `type_conflict`
  (count 1); after setting the roles, `ok` item only. A run computed before a later rule write → `recompute` names it.
- **T4 right_now payruns**: a draft run that does not balance → item 2 present with the scheme name.
- **T5 no sudo**: `learn_guide.py` and every `learn_manifest.py` contain no `sudo(`.
- **T6 board options translated**: `value_kind_board` under `vi_VN` returns `options` with Vietnamese labels.
- **T7 missing manifest**: `guide("hub_home")` returns `missing: ["no manifest for this screen yet"]` and the
  station/door data it can still give, no exception.
- Existing suites: `pb_learn` (all), `pb_formula_studio:studio_experience`, `pb_hr_payroll_formula:
  TestNetRoleClassifier,TestValueKinds`, `gen_learn_data.py --check` + `check_contract.py`. List every failure with
  its cause (known: the 6 pre-existing contract failures from the approval-route commit).

## 7. Precedents to clone (verified 2026-10-17)
- AbstractModel without ACL: `pb_learn/models/learn_helper.py` (and `learn_intent.py`); content access:
  `pb_learn/models/learn_content.py:48,95-106,199`.
- Field cards built from metadata: Records Desk `pb_records/models/pb_records_desk.py:243-365 _cards` (label from
  `field_description`, `ttype`, `selection`, `hint`).
- Translated selection labels: `field._description_selection(self.env)` (`formula_config.py:2464-2470`;
  `pb_formula_studio/models/pb_formula_studio.py:10290-10298`).
- Place → label/open: `pb_learn/static/src/engine/places.js:61-74,127-138,213-236`; hub tab lists live in each hub's
  JS (`pb_payhub/static/src/js/pay_hub.js:84-165`, `pb_home_hub/static/src/js/home_hub.js:118-147`,
  `pb_formula_studio/static/src/js/mapping/mapping_studio.js:104-154 MODES`); the authored mirror is
  `learn_content.json hubs` (from `data.js` `hub_*` entries, emitted by `gen_learn_data.py:1053-1081`).
- Component treatment data: `hr.formula.config.value_kind_board` (`formula_config.py:2383-2476`); board key →
  field map is the write path `set_component_setup` (:2583-2652): `kind→value_kind`, `pay_role→net_role`,
  `rollup→net_role_detail`, `signal→payroll_signal`, `group→component_type` (+ `*_source`). The board's own
  explainer `pb_formula_studio/static/src/xml/component_treatment.xml:94-104` and column tooltips `:107-115` are the
  seed for `filled_by` / `if_changed` sentences (LR-R5); leave the template untouched in P1 (P2 replaces the expander).
- Readers of `net_role` (for `used_by`, already verified — cite these): `pb_hr_payroll_formula/models/
  hr_payslip_formula.py:972,976` (stamp onto payslip lines), `payroll_import_batch.py:3933,3935`,
  `pb_payruns/models/hr_payslip_run.py:317-350,383-458`, `pb_dashboard/models/home_data.py:263-280`,
  `pb_payslip/models/hr_payslip.py:121-150`, `pb_explorer/models/pb_fact_builder.py:171-218`,
  `pb_hr_fullandfinal/models/full_and_final.py:225-299,362-386`, `pb_decision_room/models/pb_decision_exact.py:324-333`,
  `pb_workseg/models/pb_work_segment.py:609-625`, `pb_payslip_review/models/review_flags.py:72-78`,
  `pb_source_atlas/models/pb_source_atlas.py:227-258`, `pb_pay_delivery/models/bank_export_wizard.py:70-79` (net
  line via `pb_net_line`). For the other seven screens, find readers with the same grep (field → copied field →
  readers) and cite file:symbol; never guess.
- Odoo-shell/JSON-RPC caveats for any server-side check: `docs/FORMULA_ENGINE_CONVENTIONS.md:42-60`.

## 8. Commits, report
Worktree branch `learnrev-p1`. Feature commits: (1) engine + treatment manifest + gate + VI gaps + product fix,
(2) right-now providers, (3) the other seven manifests, (4) lesson/anchor lint fixes + regenerated content. Explicit
paths, never `-A`; `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. No manifest version bumps yet (Fable
bumps at merge). `P1_REPORT.md`: per scope item what shipped (files), T1–T7 results, the FULL guide JSON for
`treatment` in EN and in VI pasted as the hero, the list of `used_by` entries per screen, design-bar score, anything
not done and why, new LR rows added to the ledger.
