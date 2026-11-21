# UPDATES — Phase 6 report (a client's admin manages approvals for their own company: D21-D22)

Implemented, tested, deployed and checked by the Opus implementation agent on 2026-11-12 against
`UPDATES_P6_HANDOVER.md` and `UPDATES_LEDGER.md`. Numbering: D21 and D22 were free in the ledger
(P4 uses D16-D19, P5 uses D20), so the handover's numbers are kept.

R0 below was written BEFORE the deploy, as the handover asks.

## R0. Rollback note (written before anything ran)

**What the deploy changes.** Code of two modules on all five databases (`payobook`,
`payobook_template`, `p0clone`, `rize`, `sudima`), and ONE stored change per database made by the
module upgrade itself: the Tenant administrator role (`pb_vendor_access.role_tenant_administrator`)
gains the ability "Approval routes — publish" through the role service, which (a) gives that
permission to every person the role is assigned to, (b) bumps the role's revision and writes a
History row (`pb.role.change`, reason "Owner decision 12 November 2026: a client's own
administrator chooses who approves what in their company (approvals set-up)."), and (c) replaces
the role's sentence (it still reads exactly as shipped on 2026-10-01 on all five) with the same
sentence plus "who approves what", English and Vietnamese. Dry run on all five live databases
(rolled back): the only login that gains anything is **hr@sudima.local on sudima** (R6).

**Code.** Previous trees kept as `/odoo/backups/updates-p6-<TS>/{pb_approval_config,pb_vendor_access}.prev`.
Restore = per-module scoped `rsync -a --delete <m>.prev/ /odoo/odoo-server/addons/<m>/`, then the
data undo below, then restart (the old code has no migration that would undo the widening).
Five dumps `/odoo/backups/updates-p6-<TS>/<db>.pre-updates-p6.dump` are taken before the service
stops; a full restore is `pg_restore` of the database's dump.

**Data undo (the widening), per database, service stopped, `odoo-bin shell -d <db>`.** Rehearsed
on the local walk copy (`upd_p6_walk`): the admin lost the permission, History row written.

```python
from odoo.addons.pb_vendor_access.hooks import (
    TENANT_ADMIN_DESCRIPTION, TENANT_ADMIN_DESCRIPTION_20261001, TENANT_ADMIN_XMLID)
from odoo.addons.pb_vendor_access.catalogue_vi import VI
role = env.ref(TENANT_ADMIN_XMLID).sudo()
ab = env['pb.role.ability'].by_keys(['approvals-publish'])
vals = {'ability_ids': [(3, a.id) for a in ab]}
env.cr.execute("SELECT description->>'en_US' FROM pb_role_profile WHERE id=%s", [role.id])
if (env.cr.fetchone()[0] or '').strip() == TENANT_ADMIN_DESCRIPTION.strip():
    vals['description'] = TENANT_ADMIN_DESCRIPTION_20261001
role.with_context(lang='en_US', pb_access_reason='Undo UPDATES P6').write(vals)
if 'description' in vals and env['res.lang'].sudo().search_count([('code', '=', 'vi_VN')]):
    role.update_field_translations('description', {'vi_VN': VI[TENANT_ADMIN_DESCRIPTION_20261001]})
env.cr.commit()
```

(Undoing on the old code needs the two constants; with the old tree in place, paste the two
sentences from this commit's `hooks.py` instead.) No route, responsibility, user or group outside
the role service's own reconcile is written by this phase. Nothing is published, no job added.

---

## R1. What shipped

| Module | Version | Where | What |
|---|---|---|---|
| `pb_vendor_access` | 19.0.1.16.2 → **19.0.1.17.0** | upgraded on all five | Tenant administrator gains "Approval routes — publish" (`TENANT_ADMIN_ABILITIES`, `TENANT_ADMIN_ADDED_20261112`); migration `19.0.1.17.0/post-migrate.py` widens the existing role through the role service; new role sentence + Vietnamese |
| `pb_approval_config` | 19.0.1.7.0 → **19.0.1.8.0** | upgraded on all five | the rails (`models/setup_rails.py` + facade/import checks); the inbox "way out" link; three buttons aligned with the engine; People & backups support-seat line; picker CSS fix; tests `tests/test_p6_*.py`; Vietnamese for 16 new sentences, `.pot` refreshed from `odoo-bin i18n export` |

Commit `f030318ce` (code). Docs commit carries this report and the ledger.

## R2. The gates found (find first)

| Gate | Where | Before P6 |
|---|---|---|
| Server facade of the Approval Matrix | `pb.approval.matrix._require_config` (`models/matrix_facade.py`) | system admin, `group_approval_admin` or `group_approval_config` |
| Publish | `pb.approval.matrix._can_publish`, `biz.approval.engine._require_publish` | `group_approval_publish` (or admin/system) |
| Settings card + ⌘K rows | `static/src/js/palette.js` `APPROVAL_CONFIG_GATE` | config / publish / admin / system groups |
| Settings left-menu entry | `pb_vendor_access.SCREEN_GATES['pb_settings.item_settings']` | `access-team` ability (the Tenant administrator already has it) |
| Client action record | `views/actions.xml` | no group (the server gate is the boundary) |
| Access rights | `biz_approval_workflow/security/ir.model.access.csv` | the config tier may WRITE/CREATE the process catalogue (`biz.approval.process`) and the responsibility catalogue (`biz.approval.role`) — the engine's own definitions |
| Record rules | `biz_approval_workflow_rules.xml` | company rules on every model; config users read every request of their companies |
| Spreadsheet door | `pb.approval.matrix.import` | config gate only; `run`/`proposed_people` took any company id; `resolve_person` took any user, no audit line |
| Tenant administrator role | `pb_vendor_access/hooks.py` | 23 abilities, none of them approvals set-up (on rize/sudima/template/p0clone 21: some modules absent) |

Census before (read-only, rolled back): the role reaches no approvals set-up anywhere; who could open
the screen = system administrators only (payobook ash, look.p4, qa.test; template/p0clone the support
login; rize ash + support login; sudima ash + support login). Finding: an access manager could
ALREADY give anybody, themselves included, the catalogue roles "Approval routes — publish" or
"Approvals administrator" in Access (two clicks, History row) — so D22 was reachable before, without
any of the rails below.

**What was granted, exactly:** one ability, `approvals-publish` (group
`biz_approval_workflow.group_approval_publish`, implying `group_approval_config` and
`group_approval_user`), added to the Tenant administrator role through the Access catalogue's role
service. Not "Approvals administrator" (cover for others, moving a waiting step, withdrawing any
request). No stock group; the role's closure still reaches neither `base.group_system` nor
`base.group_erp_manager` (test `test_still_no_administrator_permission_in_its_closure`).

## R3. The rails (each on the screen's facade AND on the models, for a direct call)

`pb_approval_config/models/setup_rails.py`; "the platform's own people" = the code under sudo, the
superuser, a system administrator or an ERP administrator. Everybody else who sets approvals up —
a tenant admin — meets:

1. **The engine's catalogue is not set-up.** `biz.approval.process` and `biz.approval.role`
   refuse create / write / delete ("What a kind of request is, and the list of responsibilities,
   are part of the product…"). Routes, bindings and who holds a seat stay editable.
2. **The platform's own row and seat.** Process `tenant` ("Suspend, delete or change plan") and
   responsibility `platform_owner` are hidden from the grid, People & backups and the builder's
   role list, and refused on every set-up call (create/open/save/publish a route, bind, bulk
   "No approval needed", seat, empty a seat, scheme panel) and on the models (workflow, version,
   binding, responsibility create/write; `biz.approval.engine.publish` refuses before its checks).
   "Support access" and "Role grants" stay the client's (support access is the customer's decision
   by design, `pb_tenancy/models/support_approval.py`).
3. **The platform support login is nobody's to name.** Never offered in the people picker; refused
   as holder, backup, group member, cover, or a person named on a route (only ADDING it is refused:
   a route that already names it can be opened and the name removed); where it already holds a seat
   the cell says "Platform support · Not one of your people — choose someone who works here" with no
   account id; the trail and hand-over lists show it as "Platform support", no picture link.
4. **People & backups:** a backup or group member must have an active staff login in the company
   (before, any id was accepted). Spreadsheet resolve: same rails + an audit line.
5. **Cross-database:** structural (one database per client); no set-up call takes a database name
   (test M3e scans the source); another company of the same database is refused ("You cannot see
   that company").

No approval decision path changed: who is asked, who may decide and what is written are untouched
(`pb_records` was not edited). The three inbox buttons below are display only.

## R4. Tests M1-M8

New: `pb_approval_config/tests/test_p6_tenant_admin.py` (4 classes, 13 cases; a tenant admin built
from the role's permissions and nothing else) and `test_p6_bank_rails.py` (11 cases on the P3a/P3c
fixture; skipped where Updates is not installed). Local isolated tree (G13).

| # | Case | Result |
|---|---|---|
| M1 | tenant admin: grid opens (`can_publish`), a route started, edited, published (`published_by` = them); Finance holder + backup set, then only the backup changed — the trail line says "backup: Hugo HR" with before/after in the payload; History tab shows it under their name (`test_M1_*`) | PASS |
| M2 | a plain HR + payroll manager and a portal login: grid and seat calls refused exactly as before ("…setting them up is somebody else's job…") | PASS |
| M3 | a: process/responsibility catalogue write/create/delete refused by direct call (the support login still can). b: platform row/seat hidden + refused on 9 screen calls and 5 direct calls incl. engine publish. c: support login not offered, refused as holder/backup/cover/route person (screen and direct), masked where it sits. d: Access still refuses any role reaching the system permission; no ability carries it. e: another company refused; a person from another company refused as holder or backup; no database door. f: spreadsheet resolve refuses the support login and a portal login, writes an audit line | PASS |
| M4 | the tenant admin edits the bank route through the screen's own calls: (a) "No approval needed" (bulk switch) → request "approved", nothing written, "Try again" still writes nothing, no dead buttons (P3a F5b); (b) only the proposer named, independence off → waits "add a person to the bank details route", proposer never seated, may-decide and write refusals hold (F4, D14); (c) proposer + demo login named (support login cannot even be named) → nobody seated, blocked; (d) Finance given to the proposer → a records manager stands in, proposer refused even when moved onto the seat (F5c/F4); (e) support and demo logins moved onto a seat → "This login cannot approve" (K2/K4); (f) a real second person on the admin's route still writes (D13, no over-blocking); (g) dated change on a fast route is not even scheduled (F7) | PASS |
| M5 | "Nobody else…": tenant admin sees "Give someone a role in Access" (Access, people lens) + "Name a Finance approver" (Matrix, People & backups, Finance); names one, presses "Try again now it is set up", that person approves → account written. Proposer without the right: no links, "Only your administrator can add someone… Ask them to add one — they can then try this again from here." Named-route twin: "Add a person to the bank details route" (the request's own workflow), proposer gets the sentence. A request stuck for another reason, or not stuck: nothing | PASS |
| M6 | locally, `-u pb_vendor_access,pb_approval_config,biz_approval_workflow,biz_access,pb_records,pb_updates,pb_import_advanced,pb_tenants`: **1,169 tests**, 6 failures, **all pre-existing or environment** — 4 in `pb_approval_config` (colour contract on an old `#F8F9FC`; Vietnamese completeness of 71 old strings; other modules' Phase-7 Vietnamese; a placeholder in `pb_comp_ben`) fail identically on unchanged HEAD; 2 `pb_tenants` t8 need a local golden-template database. On a copy of the live template's shape (G55): 475 tests, the same 4 + one `test_inbox_facade` u10 error that also fails on unchanged HEAD with that shape. P6's own 24: green on both. pb_records 134, pb_updates 180, pb_vendor_access 105, biz_access 297, biz_approval_workflow 89: green. Live p0clone: R7 | PASS (no new failure) |
| M7 | who gains the screen, per database | R6 |
| M8 | `.po` parse gate (`PoFileReader`): vi_VN 931 entries, `.pot` 930, 0 "Odoo" in any msgstr; the 16 new msgids taken from the exporter's own template; `test_M8_no_vendor_name`; manual scan of every new sentence | PASS |

## R5. Browser walk (local copy, console read at every step)

Local database `upd_p6_walk` (copy of the upgraded test database, jobs off), company "P6 Walk Co":
the tenant admin (role assigned through the role service) proposed a bank change for DEMO Dee
Walker; nobody else could approve it. Screenshots in `outputs/updates-p6/` (01-08):

1. Approvals › All I can see › the stuck request: under "This cannot move." two buttons, solid
   "Give someone a role in Access" and quiet "Name a Finance approver" (01).
2. "Name a Finance approver" → Approval Matrix, People & backups, the Finance picker open (02 —
   found a pre-existing defect: the search box grew into a giant ring; fixed in this phase, 07).
3. Fiona Finance named (03) → back to Approvals → "Try again now it is set up" → "Waiting for
   Fiona Finance" (04).
4. Signed in as Fiona: "Your turn", Approve → "Recorded. Thank you." (05); the account number was
   written (database check). Fiona has no "Workflows" button.
5. HR manager without the role, the Matrix by direct link: "The Approval Matrix could not be opened
   — …setting them up is somebody else's job. Ask whoever looks after approvals." (06).
6. Tenant admin: Settings › Workflows shows Approval Matrix + Approvals inbox (08); no
   "Platform owner" row, no "Suspend, delete" row.

Console: 0 errors at every step. Gotcha met: two local servers on `localhost` share one cookie
across ports — another session's tab on `localhost:8795` signed my tab out; the walk moved to
`127.0.0.1` (G77).

Live, look-only, payobook.com with the browser's existing session (a system administrator): the
Matrix and the inbox render, console 0 errors (09); nothing edited.

## R6. Who can open approvals set-up, per database (M7)

Before the deploy: dry run of the widening on each live database inside a rolled-back shell (the
exact role-service call the migration makes). After: read-only census. Before = after except where
marked.

| Database | Tenant administrator assigned to | Can open approvals set-up BEFORE | AFTER | Gained |
|---|---|---|---|---|
| payobook | nobody | ash@biztinct.com, look.p4@payobook.com, qa.test@payobook.com (all system administrators) | same | **nobody** |
| payobook_template | nobody | the platform support login | same | **nobody** (new clients' admins get it at creation through the role) |
| p0clone | nobody | the platform support login | same | **nobody** |
| rize | ash@biztinct.com | ash@biztinct.com, the platform support login | same | **nobody** (ash is a system administrator already) |
| sudima | hr@sudima.local | ash@biztinct.com, the platform support login | + **hr@sudima.local** | **hr@sudima.local** — Sudima's own admin (the only Tenant administrator there, and one of its two access managers) |

No login that is not a client's intended admin gained anything. payobook's 186 demo-role sign-ups
and `demo.hr@example.com` (an access manager there) do not hold the role.

## R7. Deploy evidence

Unit `updates-p6-20261112T105928Z` under `flock /tmp/payobook-studio-deploy.lock` (free, no other
deploy open); START 10:59 / DONE 11:13 UTC in `/opt/deploy-notes.md`. Evidence
`/tmp/updates-p6-20261112T105928Z/` and `/tmp/p6_ev/` on the server. Tier 3.

- Before: both server trees byte-identical to the pre-phase commit (`pb_approval_config`
  9f88ae20e8b82755, `pb_vendor_access` c7cd5f1482a7e4da) — the whole diff shipped was this phase's.
  Clean staging folder; per-module scoped rsync; no standard addon touched.
- Five dumps first `/odoo/backups/updates-p6-20261112T105928Z/`: payobook 79,098,196 B,
  payobook_template 27,827,438, p0clone 28,161,884, rize 41,545,667, sudima 27,776,706; plus the two
  previous trees.
- `-u pb_vendor_access,pb_approval_config` ×5: EXIT=0, **0 ERROR/CRITICAL** in every upgrade log;
  migration line on each: "Tenant administrator gained approvals-publish … sentence updated"
  (reached: rize ash@biztinct.com, sudima hr@sudima.local, others nobody).
- **Downtime 260 s** (11:00:38–11:04:58 UTC). No test in the stopped window (G19).
- Active scheduled jobs: id lists identical before/after — 50 / 32 / 39 / 82 / 81; nothing
  re-activated, nothing lost.
- Assets: signal row + purge + `web.assets.version` bump on all five.
- Users (count/active), approval responsibilities, route versions (id/status/fingerprint), bindings
  and the mail queue: **identical before/after on all five** — no route edited.
- Tree hashes repo = server: `pb_approval_config` 977bc265fa7ebaa2, `pb_vendor_access`
  f7eb56d224e6bc13. `latest_version` 19.0.1.8.0 / 19.0.1.17.0 on all five.
- Sites after start: payobook.com, rize, p0clone, sudima 200. Server log since start: 0 ERROR.
- **Live p0clone suites after start (ports 8471/8472):** `/pb_approval_config,/pb_vendor_access,
  /pb_records,/pb_updates` — 475 tests, **P6 24/24**, pb_records 134, pb_updates 180,
  pb_vendor_access 105 green; 5 in `pb_approval_config` fail — the same 5 that fail on the pre-P6
  code with the template's shape (R4 M6). 0 ERROR lines outside test results.
- Role History on each database: revision 2 "Owner decision 12 November 2026: …" (+ the people it
  reached) and revision 3 "Role updated by administration" (the Vietnamese sentence write, G76).

## R8. What the audit records (scope item 3)

Every set-up change by a tenant admin leaves a line in the approvals trail (`biz.approval.event`,
append-only; `create()` stamps who and when; Settings › Approval Matrix › History):

| Change | Line | Also kept |
|---|---|---|
| start a route | "X started "name" as a draft" | the draft version |
| publish a route | "X published "name" version N" (+ reason, confirmed warnings) | every version is immutable; `published_by`, `published_at`, reason on the version; the old one "Replaced" |
| holder / backup / group of a seat | "X made Y the Finance approver for Co" — **new: "· backup: Z" / "· no backup" when the backup changed**; payload before/after holder, backup, group | the responsibility row |
| empty a seat | "X left "role" for Co with nobody in it" | row archived, not deleted |
| cover (hand-over) | "A is covering for B" | the hand-over row |
| a place's route (scheme panel) | "X put <place> on "route"" / "…back on the route the rest of the company uses" | binding |
| many to "No approval needed" / undo | "X set N processes to "No approval needed": …" with the undo note | old route ended, not deleted |
| name from a spreadsheet | **new**: "X made Y the role for Co (holder/backup, from the spreadsheet)" | |

Not in this trail: draft saves (a draft is not in force; versioned by `draft_revision`); Updates'
"personal details from a sheet apply at once" switch (`pb_updates`, now also reachable by a tenant
admin — R10 item 3). The role widening itself is in the role's History (R7).

## R9. Deviations from the handover, and why

1. **The "Nobody else" link lives in the approvals inbox only.** The sentence also shows on the
   Updates Apply step, which is `pb_updates` — Phase 4's module, off limits. The server side is
   reusable (`pb.approval.inbox._second_person_fix(request)`); wiring the Apply step is a few lines
   in `pb_updates` once Phase 4 is done.
2. **"Name a Finance approver" is offered beside "add one in Access".** The sentence names Access;
   with D22 the most direct fix is the Finance seat (a Finance approver needs no HR rights, P3a
   F5d). Both are shown only to someone who can use them.
3. **Three inbox buttons now follow the engine's own rules** (Withdraw, Try again on an
   approved-but-failed request, Move it to somebody else): they showed for anyone who sets
   approvals up, but the engine refuses them unless approvals administrator / sender / route owner
   (G79). Display only; nobody loses a power they had.
4. **Backups and group members must work in the company** (People & backups, for non-platform
   people). Before, any id was accepted.
5. **The people picker's search box** grew into a giant ring in the drawer (pre-existing, met in the
   walk) — fixed (`approval_matrix.scss`).
6. **`.pot` refreshed** from the exporter (it was stale by ~70 entries; the 4 pre-existing
   Vietnamese/colour test failures are unchanged by it).
7. **The migration uses the role service**, not the 1.10.0 grant loop (roles are assignments now,
   G76).

## R10. New gotchas (ledger G75-G79, fact U45)

Numbering: Phase 4 was adding U37-U38 and G60-G64 to the ledger at the same time, so this phase's rows are U45 and G75-G79 (no overlap).

The config tier can write the engine catalogue; roles are assignments (dry-run the role write
live, rolled back); localhost cookies collide across ports; facade writes run under sudo (rails on
two layers); inbox buttons out of step with the engine.

## R11. Needs an owner decision / owner action

1. **sudima:** hr@sudima.local can now change Sudima's approval routes — including who approves
   bank details, which D21 keeps as it is today. Nothing was changed there; if Sudima should not
   touch it yet, say so (the role can be taken off hr@sudima.local in Access).
2. **rize:** ash already had the screen; no Rize person holds the Tenant administrator role. If
   debalina (or another Rize person) should set approvals up, give them the role in Access.
3. **Also unlocked for every tenant admin** (part of "approvals set-up"): the Updates switch
   "personal details from a sheet apply without approval", reading every approval request in their
   company, and "Try again now it is set up" on stuck requests. Say if any of these should stay
   with you.
4. **Five pre-existing test failures in `pb_approval_config`** (old colour, ~70 untranslated
   Vietnamese strings, other modules' Vietnamese, one inbox test on the template's shape) — not
   caused here; a tidy-up job.
5. **Updates Apply step link** (R9.1) — schedule after Phase 4.
