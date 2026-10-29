# Access Studio

Option 1 is integrated into the existing Access board. Its Screens, full menu,
See it as, people passports, role builder, delegation, exports and history remain.
Module-local doors share the central catalogue; they do not copy roles.
Hiring, People and Payroll use their standard inner hub rail. The duplicate
global-sidebar child links are retired, including any copies with the same
Studio action. Settings remains the central administration entry.

Roles & permissions uses one searchable role list, an actions/records matrix,
record rules and form-field controls. The abilities editor's menu drawing is a
read-only preview of that role. People & assignments shows the combined person
passport; Screens is explicitly labeled as shared menu administration.

## Unified people navigation (30 October 2026)

People & assignments opens the existing passport layout directly in both Settings
and module hubs. A single selected person anchors the directory, profile details,
explanation drawer and full menu preview. The old `studio_people` route remains
an alias. Selecting a different filter does not silently change the open person.

| Existing capability | Unified location |
| --- | --- |
| Name/login search; module, company and due-review filters | People directory |
| Original cross-company staff/employee directory | Central-owner “All companies · full directory” filter |
| Add a person; invitations | Directory header, using the existing account workflow |
| Select visible; bulk Assign profile | Directory; up to 100 internal company users per request |
| Assign profile; expiry; independent review | Primary passport action and existing review dialog |
| Profile name, owner/department origin, expiry and review date | Profile assignments beside the menu |
| Review assignment; retain or remove | Each assignment's existing reasoned review dialog |
| Temporary grant, expiry and revoke | Profile assignments; original revoke flow |
| Request access | Selected-person action; self request in an empty directory |
| Explain access; resource/action/record/field checks; remove-profiles simulation | Passport action and existing drawer |
| Reasoned sensitive-field reveal | Existing explanation drawer for the signed-in user |
| See their full menu | Opens the same person's passport, keeping the People tab selected |
| Expandable menu and granular screens | Existing passport miniature and its screen-access reads |
| Give a role; copy roles; take back; end hand-over | Existing passport controls and dialogs |
| Employee/staff account type | Existing passport switch with the same safeguards |
| Their history; equivalent permissions; role-source details | Existing passport details, with equivalent permissions below roles |
| Menu order, visibility toggles, gates and who sees an entry | Screens, labeled “Screen administration · shared menu” |
| Person-to-menu administration and return | “Manage screen visibility” and “Back to [person]'s access” |
| See it as; exports; requests/reviews; delegation; audit | Existing header and workspace tabs |

No assignment, policy or permission is changed by this rearrangement. Central
owners retain full passports. Scoped owners can inspect local assignment details
for company users without gaining the central full-account passport capability.
Owner choices and periodic reviews remain independent of people-directory filters.
The selected person's assignment read is independent of the directory's search
and 200-person limit. Employee logins remain ineligible for staff profiles.

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

No existing role or person's access is changed merely by upgrading. New profiles
and policies normally take effect through reviewed workflows.

The explicitly owner-authorized 28 October traceability setup is provided by
`tools/setup_traceability_access.py`, separate from module upgrades. It defaults
to rollback and requires the maintenance account and an explicit apply flag.
It creates reusable packages, publishes explicit native starting policies for
the supported hiring/payroll/HR capabilities, and adopts only the named existing
matrix accounts. It cannot add native privileges, preserves independent grants,
keeps portal users on native portal scopes and does not create logins. Rize only
adopts the already-existing Komal training account; no demo users are copied.
The maintenance events identify owner authorization rather than impersonating
an independent application approver. Revoked assignments and edited profiles
are never silently replaced by a later rerun.

The native starting policies preserve existing company/ownership/sharing rules
and do not invent Team/Own restrictions from the POC's illustrative data. Owners
can then review narrower scopes or field restrictions in the live matrix.
