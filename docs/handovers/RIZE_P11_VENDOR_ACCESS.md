# RIZE P11 — pb_vendor_access: vendors on a leash, access in plain language

Read FIRST: `docs/handovers/RIZE_LEDGER.md` (rule 8: `pb.vendor.*` namespace ONLY —
`vendor_license_core` is the product's own licensing, untouchable) + phase-log P0–P10.
Design doc: `docs/design/rize-hrms-blueprint.html` §09.

## Scope
ONE new module `pb_vendor_access` (depends: pb_lifecycle (reminder/letters patterns),
pb_employee_vault (attachment pattern), pb_import_kit):
1. `pb.vendor` register — type, contacts, department, responsible owner, agreements with
   expiry/renewal alerts, attachments.
2. `pb.access.delegation` — temporary/permanent role hand-over with auto-revert,
   notifications, and history reports.
3. `pb.role.profile` — the readable roles board (who holds what, by department), built ON
   the existing permission groups (a presentation + assignment layer, not a new ACL system).
4. **Vendors** + **Access & delegation** panels in the Settings hub.
5. Optional link-up: `vendor_id` on `pb.asset` (P2 left `supplier_note`) — add the m2o
   here via inherit.

### Binding NON-goals
- No supplier invoicing/purchasing. No new permission primitives — delegation moves
  EXISTING group memberships. Never touch `vendor_license_core`. No contractor-agency
  billing (out of blueprint scope).

## Verified plumbing facts (do NOT re-derive)
- NOTHING vendor-shaped exists (all "vendor" hits are API-connector vocabulary or the
  licensing module). res.partner is used only for payment counterparties — pb.vendor is
  a STANDALONE model (no res.partner inherit; keeps white-label + scope tight).
- Reminder cron canon (vault) per ledger; letters engine P0 if a renewal letter is wanted
  (optional).
- Groups reality: Odoo 19 `res.groups` has no category_id; membership via user.group_ids;
  `all_group_ids` for checks. The role board reads groups of OUR stack (pb_* + payroll
  base ladder) — curate an explicit allowlist of group xmlids with plain-English labels
  (a data model, editable), NOT a dump of every system group.
- Delegation mechanics: adding/removing `res.users.group_ids` — reversible, auditable.
  Store the exact groups moved; auto-revert cron restores precisely (only what's still
  present — a group revoked meanwhile isn't re-added; log honestly).
- Settings hub: find its panel/lens mechanism (`pb_settings` — read how existing panels
  register; P0's report may note it). Palette 3100s.
- XLSX export canon per ledger.

## Architecture

### Models
**`pb.vendor`** — mail.thread. name, vendor_type Selection
`[('recruitment','Recruitment'),('learning','Learning & training'),
('assessment','Assessments & tests'),('benefits','Benefits & insurance'),
('it','IT & software'),('services','Services'),('committee','Committee / statutory'),
('other','Other')]`, contact_name, contact_email, contact_phone, department_id,
responsible_user_id required, country_id, active, notes, agreement_ids, company_id.
**`pb.vendor.agreement`** — vendor_id, name, date_start, date_end, renewal_date
(default = end − 30), value Monetary optional + currency, attachment_ids (ir.attachment
m2m), state Selection running/expiring/expired/renewed computed from dates, note.
Alerts (vault-pattern cron): renewal_date within horizon → responsible + HR mail +
activity (idempotent); expired without renewal → escalation. Renew action: new agreement
row prefilled, old marked renewed.

**`pb.role.profile`** — the curated catalogue: name (plain English, e.g. "Payroll
approver — final"), group_id (res.groups m2o), description ("what this lets someone
do"), area Selection `[('payroll','Payroll'),('people','People'),('lifecycle','Lifecycle'),
('money','Money & budgets'),('system','System')]`, sequence, active. Seeded for the main
stack groups (payroll ladder, lifecycle, assets, budget, PIP — gather the xmlids from the
phase reports; PIP profiles visible only to PIP heads).
Assignment surface reads/writes user membership THROUGH these profiles.

**`pb.access.delegation`** — mail.thread. delegator_user_id, delegate_user_id,
profile_ids m2m (what's being handed), kind Selection temporary/permanent, date_start
(default today), date_end (required when temporary), reason, state Selection
`[('draft','Draft'),('active','Active'),('expired','Ended'),('revoked','Revoked')]`,
applied_group_ids m2m res.groups (exact groups ADDED to the delegate — snapshot),
company_id.
`action_activate()`: adds the profile groups the DELEGATOR actually holds (never more —
you cannot delegate what you don't have; friendly error listing the gap), records
applied_group_ids, mails delegate + HR. Temporary: daily cron auto-reverts at date_end
(removes exactly applied_group_ids still present), state expired, mails both.
`action_revoke()` manual anytime. Permanent: applies and closes (state active→ a
'handed over' terminal? keep active until revoked). History NEVER deleted.

### Settings hub panels (palette 3100s)
- **Vendors panel** (facade `pb.vendors`): board {vendor, type chip, responsible,
  department, agreements: next end date + state chip, value}; kpis (active vendors,
  expiring in 60 days, expired unrenewed); facets (type, department, state); drawer:
  vendor card + agreements timeline + renew action + attachments; "Add vendor" dialog.
  Visibility: HR (lifecycle managers) + each vendor's responsible person (record rule
  `['|',('responsible_user_id','=',user.id), <manager clause>]`).
- **Access & delegation panel** (facade `pb.access`): two tabs —
  Roles board: matrix of profiles × holders (avatars), per-profile holder list, "grant/
  remove" through a confirm dialog (writes membership, chatter on the delegation-log
  model? keep an audit: every grant/remove through this board creates a
  `pb.access.delegation` record kind permanent with reason, so ONE audit trail);
  Delegations: list of active/past delegations {who → whom, profiles, window, state},
  "Delegate my access" dialog (any internal user can delegate what they hold; approval:
  none needed per requirement — notifications suffice; HR can revoke).
  Reports: XLSX export of role assignments + delegation history.
- Gating: panels visible to lifecycle managers/admins (+ responsible persons for their
  vendor rows); "Delegate my access" reachable via ⌘K for any internal user.

## Safety rails
- NEVER add anyone to admin/system groups via profiles — the catalogue seed EXCLUDES
  base.group_system / base.group_erp_manager and the facade hard-refuses profiles
  pointing at them (belt and braces).
- Delegation applies groups the delegator holds — enforced server-side.
- Auto-revert cron idempotent + honest logs; test date manipulation allowed.
- All mails to @example.com test users during tests.
- Deploy `-i pb_vendor_access` (+`-u pb_assets` if the vendor_id inherit needs it —
  inherit lives in pb_vendor_access, so plain -i should do; confirm).

## Numbered test cases
T1. Deploy clean.
T2. Vendors: add 2 vendors (one recruitment w/ agreement ending in 20 days, one IT
    running long) → board chips right; expiring kpi = 1; drawer timeline + attachment
    upload work; light+dark screenshots.
T3. Alert cron: expiring agreement → responsible mail + ONE activity (rerun idempotent);
    renew action → new row prefilled, old marked renewed, alerts stop.
T4. Record rule: a test user set as responsible for vendor A sees ONLY vendor A;
    lifecycle manager sees all; plain user nothing.
T5. Roles board: profiles seeded with plain-English names; matrix shows real holders
    (spot-check against a known user's groups); grant a profile to a test user via the
    board → membership real (probe user.all_group_ids), audit delegation record created;
    remove → reverted + audited.
T6. Guard: attempting to seed/point a profile at the system-admin group → refused.
T7. Delegation: test user A (holding assets-manager) delegates to B temporary 2 days →
    B gains exactly those groups, both mails queued; A cannot delegate a profile they
    lack (friendly error).
T8. Auto-revert: move date_end to yesterday, run cron → B's groups reverted (exactly
    applied ones), state expired, mails; rerun → idempotent.
T9. Manual revoke works mid-window.
T10. Exports: role-assignment XLSX + delegation-history XLSX open and read sanely.
T11. Asset link: pb.asset now shows vendor_id; set it on a test asset; P2 board fine.
T12. White-label grep zero; plain English ("what this lets someone do" copy present).
T13. Regressions: Settings hub existing panels fine; P0–P10 lenses load; a payroll run
    approval untouched by any group changes made (use test users only!).
T14. Clean up test users' memberships + records; report what remains.

## Deliverables / report back
Commits, per-test results, deploy EXIT, deviations, gotchas, the seeded profile
catalogue (owner report needs the plain-English list), Settings-hub integration
mechanism, palette ids.
