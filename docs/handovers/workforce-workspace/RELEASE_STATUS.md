# Workforce workspace — deployed 24 November 2026

The approved design is live on Sudima: grouped navigation for daily work, guided initial setup, and a factory/workplace overview. Existing editors, approvals and calculation engines remain authoritative.

## Release

- Implementation: `73726dec8`.
- Settings integration: `ba442cd77`.
- Final deployed combined code: `87ff2e4434ab582f12c9398f426dddfadcf5d7df`, including the completed DOCSTUDIO W2 and Sudima joining-date changes.
- SSH target: `Payobook19v2`; addons directory: `/odoo/odoo-server/addons`.
- Installed `pb_workforce_workspace` 19.0.1.0.0 on `payobook`, `payobook_template`, `p0clone`, `rize`, and `sudima`.
- Enabled only Sudima, through the live guided setup UI. Other companies retain their previous navigation.
- All 208 combined custom-module trees and installed versions verified. Existing generated Windows connector ZIP deliberately retained. Standard server addons and retired ABM untouched.
- The initial install and final return-navigation correction were deployed separately (154 and 178 seconds of service downtime). Both completed successfully; all four active hostnames returned HTTP 200.

## Verification

- Nine server tests passed on the isolated Sudima copy: company scope, permissions, administrator-only adoption, allowed catalog names, search/pagination, readiness without activation, and workplace filtering.
- Deployed catalog reads and CSS/JS asset compilation passed on all five databases (eight catalogs on Sudima, seven elsewhere; attendance calculation remains optional).
- Live Chrome: enabled adoption, factory overview, shift editor, Back to list, policy edit/cancel and unsaved-change protection, recurring pattern preview, roster board/review, people, overtime definitions, calendars, connector details, attendance/hours, overtime approvals, and Settings return path passed.
- Pattern preview reported 4,645 potential new drafts and 7,739 existing entries; no draft creation or publication was performed.
- Settings > HR > Calculation policies opens the same premium editor. Back to list and Back to Settings were both exercised after the correction.
- Mobile: 390px viewport and document width, usable 603px canvas, collapsed approval dock. No browser console errors.
- UI creation was tested only on the isolated database: a 07:30–16:30 shift with a one-hour break computed eight hours.
- Temporary live QA user 2501 disabled and password rotated. Isolated service, database, filestore and credential files removed. No test screenshot files were saved; inline JPEG inspection only. Concurrent-session and user-provided images preserved.

## Where users go

| Task | Menu |
| --- | --- |
| Initial setup | Settings > HR > Workforce setup > Set up Workforce, or Workforce > Guided setup |
| Daily factory view | Workforce > Overview > Factory overview |
| Shift definitions | Workforce > Shifts & patterns > Shift library |
| Repeating work/rest days | Workforce > Shifts & patterns > Recurring patterns |
| Roster | Workforce > Roster > Roster board / Review roster |
| Employee assignments | Workforce > People > People & assignments |
| Calculation, overtime and calendars | Workforce > Rules & calendars |
| Actual hours and approvals | Workforce > Timesheets > Attendance & hours / Overtime approvals |
| PC connectors and received data | Workforce > Connections > Data connectors; open a connector > Received records |

## Sudima data still requiring review

This UI release is not payroll readiness approval. The attendance calculation policy remains draft (zero active), and all 12,384 roster rows remain draft. Worker lateness of 1–9 minutes remains unconfirmed. No extra-bonus logic was implemented.

The latest live employee count is 678 after the other session's profile additions; all 678 have no workplace assigned, so the overview honestly displays “Workplace not assigned”. Guided setup also reports 27 people without an attendance policy. The client can maintain these assignments in the UI.

## Evidence and backups

- Initial release: `/tmp/workforce-workspace-20261124/receipt.json`.
- Final release: `/tmp/workforce-workspace-20261124-final/receipt.json`.
- Database verification: `/tmp/workforce-workspace-20261124-final/verification.json`.
- Browser verification/data safeguards: `/tmp/workforce-workspace-20261124-final/ui-verification.json`.
- Final nonproduction backups: `/odoo/backups/workforce-workspace-20261124T101650Z/` (seven-day retention, preserve latest usable).
- Final Rize backup: `/odoo/archives/rize-workforce-workspace-20261124T101650Z/` (permanent).
- Exact pre-deployment scheduled-job states restored on all five databases.
