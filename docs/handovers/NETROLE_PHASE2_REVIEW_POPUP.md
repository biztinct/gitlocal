# NETROLE Phase 2 — the import ends with a category conversation, not a guess

Program: NETROLE. Phase 2 of 4 — runs AFTER Phase 1 (the classifier) is merged.
Modules: `pb_formula_studio` (the UI), `pb_hr_payroll_formula` (the chain-in).
Read `docs/FORMULA_ENGINE_CONVENTIONS.md` C1, C2, C3, C7, C10, C11 and
CLAUDE.md's deploy contract. Design mandate applies: WOW, Lucide icons (no
emoji), locked Payobook palette, Chrome-MCP validation.

## What the owner asked for (verbatim intent)

At the moment an Excel with formulas is imported to create a payroll scheme,
the system should decide Earning vs Deduction from each component's usage in
the net-pay formula — and where the user's own colour/band coding already
implied a category, show a pop-up with OUR suggestions and the reason, and let
the user accept via checkboxes. "Very intuitive and user friendly wow."

## Phase 1 gives you the brain — verify its real API from code

Phase 1 (committed before you start; read
`pb_hr_payroll_formula/models/formula_net_role.py` and its tests as the source
of truth — if it deviates from this doc, the CODE wins):
- `config.classify_net_roles()` — computes/stores `net_role`,
  `net_role_detail`, `net_role_reason`, `net_role_confidence` per rule.
- `config.suggest_categories()` — read-only suggestion list
  `{rule_id, code, name, current_category, suggested_category_code, role,
  detail, reason, confidence, agrees}`.
- `config.apply_suggested_categories(rule_ids=None)` — writes rule +
  linked salary-rule categories for the accepted subset.

## Verified plumbing — do NOT re-derive

- The import finish line: `_import_completion_action(created_rules, msg_parts)`
  in [formula_import_wizard.py:~290-308](../../pb_hr_payroll_formula/wizards/formula_import_wizard.py#L290)
  — returns a `display_notification` whose `params['next']` already chains a
  follow-up action (`config_id.studio_people_mapping_action(created_rules)` —
  clone that config-level-method precedent). BOTH single-sheet import paths
  funnel through it; check whether the multisheet wizard
  ([multisheet_import_wizard.py](../../pb_hr_payroll_formula/wizards/multisheet_import_wizard.py))
  has its own finish line and hook it the same way if so.
- The user's own colour/band signal lives on the rule as `component_type`
  (Char — the merged band above the column, e.g. "Deductions", "Allowances";
  [formula_rule.py:129](../../pb_hr_payroll_formula/models/formula_rule.py#L129)).
  "Colour coding agrees/disagrees" = compare a normalised `component_type`
  (contains deduction/khấu trừ → DED; allowance/phụ cấp → ALW; earning/thu
  nhập → earning-side) against the classifier's suggestion.
- Studio toolbar: add a "Review categories" command to the `commandLanes`
  getter at [formula_studio.js:1180](../../pb_formula_studio/static/src/js/formula_studio.js#L1180)
  (standing memory rule: new tools go in that getter). Rich tooltips pattern
  is already there.
- Asset-cache purge is mandatory after JS/SCSS/XML changes (C2), per DB.

## Build

### The review surface (OWL, `pb_formula_studio`)

A client-action dialog/takeover `pb_category_review` opened with
`{config_id, next_action?}`:
- Header: scheme name, one sentence — "We read your NETPAY formula. Here is
  what each component does to net pay." A small legend of the role colours
  (reuse net_role earning/deduction tints; same hues Phase 4 will use).
- Body: grouped list — Earnings / Deductions / Employer cost / Information /
  Needs review — each row: checkbox (checked by default when
  `confidence == 'certain'` OR the suggestion agrees with the user's own band;
  UNchecked when it would OVERRIDE a category a person already set and
  disagrees), component name + code chip, current → suggested category as two
  chips with an arrow, and the reason sentence ("Subtracted from NETPAY
  through TOTALDEDUCTI"). Confidence shown as a subtle badge; `review` rows
  get an amber left rail and sit in their own group at top.
- A "colour coding" ribbon on rows where the user's band disagrees with the
  math: "Your sheet's band says Allowances — the formula says Deduction",
  with the formula-derived one suggested but the row UNchecked (their explicit
  coding is not silently overridden; the math must win only by their click).
- Footer: "Apply N selected" (primary) / "Skip for now" (secondary). Apply
  calls `apply_suggested_categories(selected_rule_ids)`; then, if a
  `next_action` was passed (the people-mapping chain), dispatch it; else
  close back to the studio. Both buttons work with 0 selected (= skip).
- Empty/degenerate states: no NET identifiable → the dialog explains it in
  one sentence and offers "Pick the net component" (a simple select over the
  scheme's formula rules that sets it and re-runs `classify_net_roles`);
  nothing to suggest (all agree) → a green "Everything already matches the
  formula" state with a close button.

### The chain-in (`pb_hr_payroll_formula`)

- After any Excel scheme import creates formula rules:
  run `classify_net_roles()` (guarded — a classification failure must NEVER
  fail the import; C7 says log it), and if there is ≥1 suggestion that
  changes anything or any `review` row, set
  `params['next']` to the review action, passing the previously-chained
  people-mapping action through so it still happens after (the review dialog
  dispatches it on close). When classification finds nothing to say, the old
  chain is byte-identical.
- Also a config-level server action + studio command so the review can be
  reopened any time ("Review categories" in `commandLanes`).

### Non-goals

- No changes to the classifier's math (Phase 1 owns it; file issues in the
  report instead of editing it, unless a P1 bug blocks you — then fix
  minimally and flag it as a deviation).
- No auto-apply anywhere. The popup is the only writer, and only of checked
  rows. ABM is already repaired (Phase 1) — do not touch live categories.
- No payslip/KPI changes.

## Tests (`pb_formula_studio/tests/test_category_review.py` + wizard-side)

1. Import a colour-banded in-test workbook → the completion action chains the
   review (`params['next']` tag + config in context); a workbook whose scheme
   yields no suggestions chains the OLD action unchanged.
2. Classification failure during import (force NET-less scheme) → import still
   succeeds, notification still returned, review offers the pick-NET path.
3. Server payload for the dialog: agrees/disagrees flags correct for a rule
   whose `component_type` band contradicts the formula sign.
4. `apply` with a subset writes exactly that subset (rule + salary rule),
   others untouched.
5. Default-check policy: certain+agrees → checked; disagrees-with-user-band →
   unchecked (assert on the payload flags the client uses).
6. Existing import-wizard tests still green.

Run on `payobook_template`; bump `pb_formula_studio` + `pb_hr_payroll_formula`
manifests; deploy per contract; upgrade 4 DBs; purge assets per DB; restart.
Validate live on ABM with Chrome MCP: open the studio on scheme 14, run
"Review categories" (it is already classified — expect the all-agree state or
real suggestions), screenshot the dialog; also do one REAL colour-coded import
on `payobook_template` or a scratch scheme on payobook (delete it after) and
screenshot the chained popup. Restart the Chrome MCP server if it is down
(standing approval); JSON-RPC fallback only if it truly cannot run, stated.

## Commits

1. `feat(formula): classify a scheme's components the moment they are imported`
2. `feat(studio): the category review — accept the formula's answer by checkbox`
Explicit staging, no push.

## Report back

Screenshots (dialog states), test counts + EXITs, per-DB upgrade EXITs, the
exact default-check matrix you shipped, deviations.
