# Access and Delegation design review — revision 3

Open `../access-delegation-poc.html` in a browser. The self-contained document
contains three interactive concepts, a review of the existing product,
first-party research links, a feature-preservation checklist, a comparison and
recommendation. It has no external dependencies or production API calls.

- **01 Access Studio (recommended):** a module-specific workspace with scoped
  roles, reusable profiles, CRUD scopes, record rules, form fields, Screens,
  delegation and revision history.
- **02 Guided Setup:** choose a profile, refine source-role policy, preview the
  form and full menu, then review a local profile assignment.
- **03 People Passport:** explain a person's assigned profile, source roles,
  additional grants, menu and effective record/field access.

Hiring, People and Payroll use one central catalogue within each concept.
Global Settings groups that catalogue by module. The Hiring access owner can
manage only Hiring; a platform-owner demo mode exposes the other workspaces.
Shared roles remain references controlled by their owning module.

An **account type** is Staff/Employee/External. An **access profile** packages
existing roles. A **role** carries policies; profiles do not duplicate those
policies. The existing `pb.role.profile` technical model remains a role.

Screens preserves the entire 12-item menu map, role/profile/person previews,
visible/locked/hidden states, submenu ordering and visibility, and the path
from submenu to form and resource. The preservation checklist distinguishes
interactive examples from production features to retain (advanced role gates,
audiences, orphan warnings, drag/keyboard ordering and revision restoration).
Menu layout does not grant or revoke backend data access.

All identities, records and policies are fictional. Each concept has independent
in-memory state and resets on reload. Only a design preference uses local
storage and can be downloaded; it does not approve production implementation.

The simplified policy evaluator covers per-action scope, mandatory Company A,
AND/OR record conditions, field read/write and separate creation inputs.
It is not the Odoo authorization engine. Fields/rules/simulator demonstrate the
first resource in each module. Detailed menu mappings include illustrative
adapters. Real persistence, enforcement, notifications, automatic expiry,
masking and migrations are outside this artifact.

## Editing and publishing

Edit `app.js` and `studio.js`, and edit the static content/CSS directly in the HTML, then run:

```sh
python3 docs/design/access-delegation-poc/build.py
node --check docs/design/access-delegation-poc/app.js
node --check docs/design/access-delegation-poc/studio.js
```

After committing the preview sources and hosting files, re-check the latest
branch/worktree and run:

```sh
python3 docs/design/access-delegation-poc/deploy.py
```

The script rejects uncommitted preview source or deployment bytes and a stale
JavaScript bundle. It publishes the complete preview from the latest committed
combined branch state. Exclude unrelated concurrent-session work from commits.

## Scope

The only deployment target is the existing isolated static review environment:
`https://payobook.com/preview/access-delegation/`, served by nginx on
`Payobook19v2`. Deployment preserves existing configuration, backs up the
previous preview, validates nginx and reloads it. It does not deploy Odoo source
or alter databases, roles or permissions. No upgrade or migration is in scope
for `payobook`, `payobook_template`, `p0clone` or `rize`. Retired ABM is untouched.

See `verification.md` for deployed Chrome checks. Screenshots are viewed in
memory; no test PNGs are retained.


## Revision 3 — expanded Option 1

Studio adds People & assignments and Requests & reviews. Role actions,
record rules and form fields are nested inside the role editor. Screens,
Profiles, Delegation and History remain directly accessible.

Interactive demonstrations include reviewed bulk profile assignment,
published effective-access explanations with a profile-removal simulation,
request/approval/rejection with self-approval protection, impact previews,
combined payroll conflicts, published role versions and restore-as-draft,
profile ownership/clone/compare/retirement, periodic profile reviews,
business-action and workflow-stage previews, masking/reasoned reveal and
manual join/move/leave event simulation.

The fixed snapshot date is 2 November 2026. Dates are evaluated at date
precision in the new assignment demonstration; no background expiration job
runs. Extra roles remain independent when a profile is removed. Suspended
sample people have no effective grants. Only Studio uses these expanded
member workflows; Options 2 and 3 retain their independently reset examples.

The role/menu editing preview can show draft policy. Studio's people
explanation uses published snapshots. Policy expansion, record-rule changes
and added profile references go to an independent demo approval. Existing
sample profile assignments use preapproved packages. All real identities,
grant ceilings, business-specific prerequisites and multi-company rules
need authoritative server evaluation in a production implementation.
