# FS-5 — Reach everywhere (`pb_form_studio_reach`) — report

**PAUSED (owner pause, 2026-11-19).**
Done: branch `fs-5` from `origin/fs-1`; local DB `fs_5_t` (copy of `upd_p6_t_tpl`, brought up to the branch,
`pb_form_studio_reach` installs cleanly, no errors); code written for items 1 (pay formulas: catalogue +
values + formula delete blocker + "Use in pay formulas" untick guard), 2 (Records master fields, hidden-card
drop in every desk mode, Country of Work blank cell + refusal), 3 (Mapping "Company details" lane + hidden
fields not mappable), 4 (My details see-only card, 'Everyone' fields only, picked by setting), 6 (biz_access
hook `_studio_extra_fields` — listing + enforcement, manual fields only; biz_access 19.0.1.14.0), 7 (timeline:
custom fields watched, files "File attached", hidden fields' changes filtered from employee Timeline and
contract History).
Next: tests (numbered cases, test hosts registered in test code only by patching `_pbfs_hosts`; patch
`_pbfs_busy` in tests — see gotcha below), PO files vi/id + gate, item 8 Learn lesson, item 5 Explorer
written up as NOT DONE (reasons below), baseline runs of touched suites, browser walk, full report.

## Notes gathered so far (for the full report)
- Explorer (item 5) — not forced: `_DIMENSIONS` is a module constant read in 12 places (spec parser,
  schema, drill, export…); line facts (`pb_fact_line`) carry no `employee_id`, so money measures cannot be
  split by a person's field without a fact rebuild. Only the people-count measures could take it.
- Engine gotcha (merge task for `pb_form_studio`): `_pbfs_busy` check 1 joins `pg_locks` to `pg_class` on
  oid without `l.database = current DB`. Local databases copied from one template share table oids, so a
  payslip write in ANOTHER database can refuse "A pay run is being worked out". Fix: add
  `AND l.database = (SELECT oid FROM pg_database WHERE datname = current_database())`.
- Merge-time: nothing reaches anything until FS-2 (`hr.employee`) and FS-3 (`hr.contract`) hosts are
  registered; all surfaces key on `fields_for(model, …)`, which returns [] for an unregistered model.
