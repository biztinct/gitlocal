# Unified Workforce workspace

## Scope

An optional company-level presentation layer in `pb_workforce_workspace`. Installation leaves `res.company.pb_workforce_workspace_enabled` false. An administrator changes it from Settings → Workforce setup → Set up Workforce. It changes navigation, not calculation or payroll configuration.

Daily navigation:

- Overview → Factory overview / Today
- Roster → Roster board / Review roster
- Shifts & patterns → Shift library / Recurring patterns
- People → People & assignments
- Rules & calendars → Attendance policies / Overtime definitions / Overtime ceilings / Working calendars / Holidays (when installed)
- Timesheets → Attendance & hours / Overtime approvals / Close & send to payroll
- Connections → Data connectors
- More → existing time-off, approvals, field and insights lenses, subject to role permissions
- Guided setup → six review steps with live counts and direct access to the same records

## Reuse and safeguards

The existing schedule board, pattern editor, time hub, overtime desk, approval inbox and close workflow remain the operating screens. New libraries open the existing record forms in the shared premium record host. New records use the original form dialog. Model validation, permissions, approval workflows and audit records remain authoritative. No parallel calculation or write API is introduced.

The presentation facade has a fixed catalog allowlist, checks attendance access and each model's read ACL, applies the current company domain even when several companies are allowed, and returns only field metadata allowed to that user. Catalog pages are limited to 40 records. The company preference is administrator-only. Other companies keep existing navigation until they adopt it.

Attendance policy is an optional capability; this module does not depend on or install the calculation engine in other tenants. Missing optional capabilities are reported rather than counted as complete.

Patterns display weekdays relative to the actual cycle anchor, shift times and rest days. The unified flow requires a preview before creating drafts and preserves the existing engine's conflict handling. It never publishes inferred schedules automatically. Existing standalone patterns retain their behavior.

The factory overview groups by employee workplace, not terminal IP or machine name. Drill-down passes a workplace filter to roster/people catalogs and the selected week to roster review. Company-wide setup counts are separate from that week's workplace counts. No inferred assignment is written on read.

## Sudima at rehearsal

- 651 employee records have no workplace assignment, so the overview honestly shows “Workplace not assigned”. Employee assignment is available through People & assignments.
- Attendance policy remains draft; there are no active policies.
- 12,384 draft roster rows remain unpublished.
- Worker lateness of 1–9 minutes remains unconfirmed.
- No payroll, bonus, device, connector credential or deduction setting is activated or changed by this release.

## Verification

Nine database tests cover tenant isolation, optional adoption, model allowlisting, officer read-only access, administrator-only adoption, search/pagination, workplace scope and non-mutating readiness reads. Browser checks on a separate Sudima database copy cover grouped navigation, catalogs, original policy fields, shift creation, unsaved edit protection, recurring pattern preview and responsive layout. Final live deployment evidence is recorded separately after release.
