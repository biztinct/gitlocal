# Formula Studio redesign and repairs — deployment verified

The deployed workspace has a readable Table and component inspector, a smaller
Grid, explicit sample and actual-payslip preview, and one review queue. The audit
remediation map is in `docs/handovers/STUDIO_EXPERIENCE_2026_10_16.md`.

Runtime commits, in order:

- `826bdf8eb`: workspace, typed formatting, draft creation, scoped analysis.
- `037ec5235`: tool action context, effective defaults, selected outcomes.
- `09a1cad4e`: component context for Grid saves and Undo.
- `412b75eaa`: neutral folded groups, actual-payslip entry, review queue and mobile layout.

The latest combined runtime tree was deployed, including all 149 existing custom
addons. All 4,807 source files were verified against both the repository and the
server. Vendored Odoo standard addons were excluded. Existing unrelated local
work was preserved.

| Database | Studio version | Engine version | Full regression checks | Final Studio checks | Active jobs before → after |
|---|---|---|---:|---:|---:|
| payobook | 19.0.1.201.19 | 19.0.1.148.12 | 72 passed | 32 passed | 37 → 37 |
| rize | 19.0.1.201.19 | 19.0.1.148.12 | 72 passed | 32 passed | 69 → 69 |
| p0clone | 19.0.1.201.19 | 19.0.1.148.12 | 72 passed | 32 passed | 26 → 26 |
| payobook_template | 19.0.1.201.19 | 19.0.1.148.12 | 72 passed | 32 passed | 0 → 0 |
| abm | 19.0.1.201.19 | 19.0.1.148.12 | 72 passed | 32 passed | 0 → 0 |

Every job's activation flag matched by ID, not merely by count. Temporary database
triggers prevented upgrades from activating inactive jobs and forced any new job
inactive. The triggers were removed after verification. Payroll inputs and stored
results, component formulas and types, contract-wage fingerprints, employee and
payslip counts, and outgoing-mail queue snapshots remained unchanged by deployment.

The Odoo service is active. Asset bundles were invalidated on all five databases.
`tools/deploy_status.py` reports nothing pending. Rollback backups and complete
receipts are under `/odoo/backups/studio-experience-ui-20261016/`; the full engine
and Studio regression receipt is under
`/odoo/backups/studio-experience-final-20261016/`.

Chrome checks on Rize covered search, grouping, all 81 Grid columns, column
selection, three Grid rows, Add draft validation and cancellation, Compare's named
net-pay outcome, What-if's one-run employee scope and cancellation, payslip
readiness, legislation applicability, and the review workflow. All 115 dependency
edge paths contain geometry. A 390 × 844 viewport retained readable scheme names,
controls and preview values. No JavaScript runtime errors were observed.

A temporary draft scheme with fictional samples verified component creation,
formula recalculation, Undo, value-type persistence, zero-preserving identifiers,
quantities, rates, and buffered edits during fast sample switches. That scheme and
its five components and two samples were removed. The isolated test database was
also removed. Test screenshots were kept in memory; no screenshot or PNG files
were written. Product assets were preserved.

Additional checks passed: 14 native formatter assertions, 10 merged OWL templates,
and Odoo's translation reader over the 2,468-entry Vietnamese catalogue.

Value-type corrections remain explicit, reviewed configuration changes. The new
Review value types panel preserves manual choices, starts suggestions unchecked,
and does not change a scheme on read. Existing pay runs are not recomputed or
rewritten by this repair. This is deliberate because a value's type affects how
future payroll inputs are interpreted.

Machine-readable results: `2026-10-16-formula-studio-experience.json`.
