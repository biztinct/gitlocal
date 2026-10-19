# Payroll workbook access

Thao's monthly download failed because standard employee/contract columns used
an in-memory import mapping without elevated metadata access. Reading its
`ir.model.fields` destination failed for payroll staff. Transaction tests had
hidden this behind an administrator-warmed field cache. Synthetic mappings now
use the same metadata access as persisted mappings; user roles are unchanged.

Monthly uploads also required the original downloader to upload the workbook.
Authorized payroll staff with Records export permission can now review another
colleague's download for the same company and configuration. Current population,
identity, layout, source and period checks still apply. A fresh review belongs
to the uploader. Review and applied tokens remain owner-only, as do separate
Employee records imports. No direct access to the receipt storage models or
technical Fields model is granted.

Both reported paths were reproduced: the new cold-cache download and shared
monthly review tests produced two errors on the old code. All 142 selected
template and mapping regressions passed on the staged fix. Four new tests also
cover confirmation ownership, non-payroll callers, cross-company and wrong
configuration references, and isolation of records/review/applied receipts.

Deployment and final verification results follow after rollout.
