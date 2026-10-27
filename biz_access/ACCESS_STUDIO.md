# Access Studio

Option 1 is integrated into the existing Access board. Its Screens, full menu,
See it as, people passports, role builder, delegation, exports and history remain.
Module-local doors share the central catalogue; they do not copy roles.

## Data and governance

- `pb.role.profile` remains a role. `pb.access.profile` packages role references.
- Profiles have an owner, review date, revisions, clone/compare/retire flows and
  optional approved department assignment rules.
- Profile definitions, bulk assignments, policy changes and temporary extra
  grants require an independent current owner. Requests contain immutable
  snapshots; changed roles, profiles or memberships invalidate stale approvals.
- Scoped owners have an explicit role ceiling. Central owners manage ownership.
  Cross-company assignments and shared definitions require central ownership.
- Profile membership, independent roles, temporary grants and loans remain
  distinct sources. Removing one does not remove another source's permissions.
- Reviews run on a 90-day cadence. Expiry uses server calendar dates and a
  one-minute scheduled reconciliation. A job outage delays group reconciliation;
  operators must monitor the expiry cron alongside existing delegation expiry.
- Employee department moves remove automatic profile sources and mark retained
  manual assignments for review. Archiving an employee removes Studio sources;
  account deactivation and independent grants remain the offboarding workflow's
  responsibility. An explicitly revoked assignment is not silently restored.
- Audit events and submitted snapshots cannot be edited or deleted through ORM.

## Enforcement

The explicit resource catalogue covers candidates, hiring requests, offers,
interviews, employees, contracts, payslips and pay runs, where installed.
Other modules retain existing application ability controls and can use profiles.
Only reviewed, installed field/resource adapters are exposed; arbitrary models,
Python expressions and client-provided record domains are not accepted.

Policies restrict the application's native ACLs and record rules. They do not
create native permission groups or grant access beyond the role's abilities.
Policies from independent sources combine; an unrestricted native/direct grant
can retain broader access and is identified by Explain access. Company rules
remain an intersection. Own scope uses the adapter's stated owner; Team means
the employee reporting hierarchy, including the user.

CRUD scopes, AND/OR department/stage conditions, editing stages, field read/edit,
creation inputs, exports, attachment downloads, archive, owner reassignment and
workflow finalisation are checked server-side. Approvals still need native
workflow authority and permission to edit the workflow state. Native safeguards
against approving one's own work are retained.

Field permissions must match the record scope of the same source. Explicitly
protected scalar values stay guarded in elevated application facades, including
cached field access. Native superuser jobs remain trusted. Masked fields expose
no raw value through ordinary reads; reasoned reveal checks the signed-in user,
one record, native field groups and the matching source, then records an audit
receipt without retaining the revealed value.

No existing role or person's access is changed merely by upgrading. There is no
fictional production seed data, automatic profile assignment migration or
activation of new record restrictions. New profiles and policies take effect
only through the reviewed workflows.
