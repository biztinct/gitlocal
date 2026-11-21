# PDR P3 — two small follow-ups from the P2 report (owner rulings 2026-11-05)

Read `PDR_LEDGER.md` §0 (binding rules) and `PDR_P2_REPORT.md` first.

## F1 — HR Responsible is no longer required on the full contract form

Owner ruling: "Stop requiring it" — every company, every database.

* The requirement is view-only: the server's standard
  `hr_contract/views/hr_contract_views.xml:169`
  `<field name="hr_responsible_id" required="1"/>` (view
  `hr_contract.hr_contract_view_form`). The field itself has no `required=`
  (`hr_contract/models/hr_contract.py:76`). Verify both on the SERVER's copy
  (the repo's `hr_contract/` is an older vendored snapshot — never deploy it).
* Fix in a custom module that already inherits the contract form (prefer
  `pb_contracts`; else `pb_hr_payroll_formula`'s
  `view_hr_contract_form_typed_components`): an inherited view setting
  `required` to `0` on `hr_responsible_id`. Do not hide the field.
* grep all custom modules for any other place that demands it (python
  constraints, `required` in other inherited views, the contract panel's save /
  New contract dialog, approval rules that route to it) and report each; change
  only what blocks a save.
* Test: a contract with no HR Responsible saves from the full form (unit test
  via `Form()` on the inherited view, plus a browser check on a throwaway copy
  or on a demo contract on payobook — never a real rize contract).

## F2 — the pay package never counts a yes/no or worded answer as pay

Owner ruling: fix now. Bug: `pb_comp_ben/models/employee_comp.py:257-272`
(`_lines_from_contract`) turns every non-zero contract component into an
`earning` line, so BPJS TK covered = 1 → earning 1, Tax allowance mode = 2 →
earning 2.

* Find the scheme rule for each component exactly as the contract panel does
  (`pb_contracts/models/pb_contract_360.py`, the rule lookup used by
  `_cd_value_view`). Skip the line when that rule has words (`value_labels`
  parse non-empty) or its `value_kind` is not money (`integer`, `quantity`,
  `rate`, `identifier`, `text`, `date`). No rule found → today's behaviour.
* Existing packages are not rebuilt automatically. Report how many existing
  package lines (per DB) came from such components and their state; do not
  change them (owner decides).
* Tests: flag component skipped; money component kept; component with no
  matching rule kept; the "carries no wage and no components" message still
  fires only when nothing is left.

## Deploy / report

Normal-risk ritual, all four DBs, `/opt/deploy-notes.md` START/DONE, coordinate
with parallel sessions (never ship another session's undeployed commit for the
same module — check `git log <live>..HEAD -- <module>`). Bump versions.
Report `PDR_P3_REPORT.md` (tests, F1 grep table, F2 counts per DB, commits,
versions); append gotchas to the ledger.
