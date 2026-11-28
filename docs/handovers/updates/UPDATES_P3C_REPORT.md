# UPDATES — Phase 3c report (who may approve bank details: owner decisions D13-D15)

Implemented, tested, deployed and checked live on 2026-11-12 by the Opus implementation agent
(commits `995f676c2` code rule, `25d674476` provisioning, `a9a0b691d` test fixtures, plus the docs
commit carrying this report and the ledger) against `UPDATES_P3C_HANDOVER.md` and `UPDATES_LEDGER.md`.

R0 below was written BEFORE the deploy and BEFORE the rize set-up change, as the handover asks.

## R0. Rollback note and the exact undo statements (written before anything ran)

**Code (all five databases).** Previous module trees kept on the server in
`/odoo/backups/updates-p3c-<TS>/{pb_records,pb_updates,pb_tenants}.prev`. Restore = per-module
scoped `rsync -a --delete <m>.prev/ /odoo/odoo-server/addons/<m>/`, `-u pb_records` on the five
databases (`-u pb_records,pb_tenants` on payobook), restart. No schema change, no new job, no
stored data written by the upgrade itself. Five dumps `/odoo/backups/updates-p3c-<TS>/<db>.pre-updates-p3c.dump`
taken before the service stops.

**The rize set-up change (D14), the only stored change of this phase.** Read-only dry run on
live rize (2026-11-12, `d14_route.py MODE=dry`): company Rize Farms (id 1), bank-details route
workflow **17504**, binding 17504, published version **17562** (revision 1, "Finance approver ·
whole company"), no waiting bank-details request, no open draft, revisions [1]. The change
publishes revision **2** of workflow 17504 through the approval engine (as the platform support
login, the 2026-09-18 precedent), the same definition with its one step's "who" set to
`{"mode": "people", "user_ids": [2, 653, 656, 939], "all": false}` (ash@biztinct.com,
debalina@rize.farm, thao@rize.farm, wildan@rize.farm; any one of them; the proposer is always
left out by the code). Revision 1 becomes "Replaced" and is kept. Nothing else on rize is
written: no user, group, responsibility, or other route.

Undo — puts revision 1 back in use (rehearsed on a clone of the template, R4):

```sql
-- on rize, as the odoo database user
BEGIN;
UPDATE biz_approval_workflow_version SET status = 'superseded'
 WHERE workflow_id = 17504 AND revision = 2 AND status = 'published';
UPDATE biz_approval_workflow_version SET status = 'published'
 WHERE id = 17562 AND workflow_id = 17504 AND status = 'superseded';
COMMIT;
```

(The "route in use" is worked out from the version status on every request — nothing is cached,
so no restart is needed.) Any bank-details request sent in while revision 2 was in use keeps
revision 2's people (requests carry their version); cancel it first if that matters. Full
restore of the database instead: `pg_restore` of `rize.pre-updates-p3c.dump`.

**Provisioning (pb_tenants, payobook only).** Only affects tenants created after the deploy; no
tenant is created by this phase.

---

## R1. What shipped

| Module | Version | Where | What |
|---|---|---|---|
| `pb_records` | 19.0.1.10.0 → **19.0.1.10.1** | upgraded on all five | the code rule (R3); two new sentences + Vietnamese |
| `pb_tenants` | 19.0.2.5.0 → **19.0.2.5.1** | upgraded on payobook only (the only database it is installed on; never on a tenant) | provisioning makes the client admin the bank approver (R5) |
| `pb_updates` | 19.0.1.5.0 (unchanged) | files only | tests K1-K4, K7 (`tests/test_updates_p3c.py`) |

Plus one stored change on rize (R4) and the "who is asked" census (R6).

## R2. Tests K1-K7

New: `pb_updates/tests/test_updates_p3c.py` (3 classes, 15 cases, P3a's company-of-its-own
fixture; the support login is a staff login with system administrator, HR manager and payroll
manager rights, named by the `pb_tenancy.recovery_login` setting) and
`pb_tenants/tests/test_p3c_bank_approver.py` (4 cases).

| # | Case | Result |
|---|---|---|
| K1 | `test_K1_support_login_alone_is_never_seated` — a company where the support login is the only Finance holder and the only other records manager: the Apply step says "Nobody else in P3C Lone Co can approve bank details yet — add one in Access."; sent: the request is **blocked** with that sentence, the support login holds no seat, nothing written. `K1b` — the support login NAMED on a bank route next to a real person: only the real person is seated. `K1c` — the support login as the Finance holder's backup (holder = proposer): left out, a records manager stands in. `K1d` — with no setting on the database the default name `platform.recovery@payobook.com` is recognised | PASS |
| K2 | `test_K2_support_login_cannot_decide_by_direct_call` — direct `decide` with no seat: refused "This login cannot approve bank details. One of the company's own people has to approve them."; the seat moved onto the support login by an approvals admin: same refusal; the inbox's own Approve path: same; nothing written. `K2b` (fail closed) — the decide check bypassed so the support login's yes IS recorded: the request is approved but **nothing is written** ("Bank details need a second person…") — that yes never counts. `K2c` — the proposer still gets P3a's own sentence first | PASS |
| K3 | `TestUpdatesP3cOtherProcessesInert` — "Other request" (the engine's reference adapter) through a route that NAMES the support login and through an HR-lead route the support login holds, each run with the new seams and with them bypassed (P3a's F12 harness): the support login is seated and decides; state, seats, decisions, steps and event lines identical | PASS |
| K4 | `test_K4_demo_role_login_is_never_seated` — a login with the demo role (`pb_demo.group_payobook_demo`) holding Finance: not seated, a records manager stands in; moved onto the seat: refused by name. `K4b` — a login merely NAMED like a demo one (`p3c.finance@demo`, no demo role) is an ordinary person (no guessing) | PASS |
| K5 | `pb_tenants` `TestP3cTenantBankApprover` — the template's shape (Finance held by the support login, also as backup): after `_seat_bank_approver` the client admin holds Finance, the support login is off the seat; if the support login proposes, the admin is asked; if the admin proposes, nobody (the D15 sentence). `K5b` no Finance seat → one is made for the admin; `K5c` a real person already holding Finance is left alone (warned); `K5d` `_step_admin` calls it after the rails. **Rehearsal on a clone of the LIVE golden template** (P3b's pre-deploy dump, upgraded to this code, local): the real `_step_admin` → "owner@k5client.example approves bank details for My Company; the platform support login does not."; Finance before = platform.recovery, after = the admin; Apply step as the support login: "Need a second person: K5 Owner"; as the admin: "Waiting for a second person. Nobody else in My Company can approve bank details yet — add one in Access." | PASS |
| K6 | P3a F4-F7, F12, F13 and every older case: locally, isolated tree (G13), `-i pb_tenants -u pb_records,pb_updates`: pb_records 134, pb_updates 180, pb_tenants 20 → 1 failure, F18 = the known local artefact (passes with `pb_import_advanced` upgraded in the same run, G59). Locally on a copy of the LIVE template's shape (Finance = support login): pb_records 134 + pb_updates 180 → **260/260, 0 failed**. **Live p0clone after start (ports 8471/8472): first run 3 failures + 2 errors, all test fixtures (R7); after the fixture fix: 260/260, 0 ERROR lines** | PASS |
| K7 | No "Odoo" in any new sentence (`test_K7_no_vendor_name` + source scan); `.po`: built against `odoo-bin i18n export -l pot` — both new msgids found by the extractor and translated in `pb_records/i18n/vi_VN.po`, which `PoFileReader` reads (365 entries); 0 "Odoo" in any msgstr. The provisioning log lines (platform cockpit only) carry no vendor name | PASS |

## R3. How the support login and demo logins are recognised

One question in one place: `pb.records.apply._bank_excluded(user)` →
`'self_service'` (portal login, P3a), `'support'`, `'demo'` or `''`.

- **Platform support login.** There is no xmlid and no flag on that account: provisioning
  (`pb_tenants._ensure_break_glass`) creates it by login, and the platform names it in every
  tenant database with the setting `pb_tenancy.recovery_login` (the way `biz_access`'s
  `recovery_login()` already hides it from Access screens). The rule reads that setting and the
  platform's own `pb_tenants.break_glass_login`, and always includes the default
  `platform.recovery@payobook.com` (the setting is absent on payobook, the template and
  p0clone). Census: recognised on all five (only rize and sudima carry the setting).
- **Demo logins.** The build has one reliable marker: the demo role
  `pb_demo.group_payobook_demo` ("Payobook Demo User", given by the demo sign-up and the demo
  world, described as "cannot approve"). It exists only where `pb_demo` is installed —
  **payobook only** (186 active logins carry it; none of them was a bank approver before, so
  nothing changed for anyone there). There is **no** marker for rize's `indo@demo` ("Indonesia
  Finance", made by hand on 2026-10-19; `pb_demo` is never on a tenant) — so, as the handover
  says, nothing was guessed from the login name (test K4b) and rize was set up instead (R4).
- **Where the rule bites:** (1) seats — whoever the route or the Finance seat names, and the
  fallback (Finance, then records managers), never includes them; (2) `decide` — an approve by
  them is refused by name; (3) the write — a yes from them never counts as the second person
  (fail closed, K2b). All three only for a bank proposal the P3a rule binds (`_bank_rule_applies`),
  so sudima's pre-lane waiting change RD00185 keeps exactly its old rules (G46).
- **A route that names its approvers** (rize after R4) is never widened to Finance or the
  records managers: if nobody named (other than the proposer) can be asked, the request waits
  with "Waiting for a second person. Nobody else named to approve bank details in <company> can
  approve this yet — add a person to the bank details route in Settings › Approval Matrix."

## R4. rize — the stored change (D14)

**Why `indo@demo` and the support login qualified.** rize's bank route (P3a) asks the Finance
holder — ash — and, when ash proposes, any "records manager" (HR manager, payroll manager or
system administrator in the company). `indo@demo` (id 936) and `platform.recovery@payobook.com`
(id 300) both hold the **payroll manager** permission (the support login also system
administrator); debalina (653), thao (656) and wildan (939) hold it too; komal (938) does not.
After the code rule (R3) the support login was out, but `indo@demo` was still asked
(census before the change: ash proposes → debalina, **indo@demo**, thao, wildan). Their
permissions are used for everything else they do, so none was touched.

**The lever:** the bank route of Rize Farms now names its approvers. Published through the
approval engine at 08:05:14 UTC as revision 2 of workflow 17504 (publisher: the platform support
login, as the 2026-09-18 precedent; reason: "Owner decision 2026-11-12 (UPDATES D14)…"), after a
fresh backup `/odoo/backups/updates-p3c-20261112T075430Z/rize.pre-d14.dump` (41.5 MB) and a
read-only dry run. Nothing else on rize was written: users, group memberships and
responsibilities identical before/after (hashes, R8); the independence-off routes untouched.

| | Before | After |
|---|---|---|
| version in use | 17562, revision 1 — "Finance approver · whole company" | **17563, revision 2** — "Ash Sohani + Debalina De + Nguyen Thi Phuong Thao + Wildan · any one" |
| revision 1 | in use | "Replaced", kept |
| step "who" | `{"mode": "role", "role": "finance", "scope": "company"}` | `{"mode": "people", "user_ids": [2, 653, 656, 939], "all": false}` |
| ash proposes → asked | debalina, **indo@demo**, thao, wildan | **debalina, thao, wildan** |
| debalina / thao / wildan proposes → asked | ash | ash + the other two |
| indo@demo or the support login proposes → asked | ash | ash, debalina, thao, wildan |
| waiting bank changes | 0 | 0 |

**Undo** (exact statements, written in R0 before the change; rehearsed on a template clone):

```sql
BEGIN;
UPDATE biz_approval_workflow_version SET status = 'superseded'
 WHERE workflow_id = 17504 AND revision = 2 AND status = 'published';
UPDATE biz_approval_workflow_version SET status = 'published'
 WHERE id = 17562 AND workflow_id = 17504 AND status = 'superseded';
COMMIT;
```

## R5. New clients (D15) — the provisioning change

`pb_tenants` `_step_admin` (the step that turns the template's archived administrator into the
client's admin) now calls `_seat_bank_approver(env, admin, say)` right after the
tenant-administrator rails: for every company in the new database, the company-wide Finance
responsibility (the seat P3a's shipped bank route asks first) is given to the client admin when
it is held by the platform support login or nobody (made if missing), and the support login is
taken off its backup and pool. A real person already holding Finance is left alone and the log
says so. Inside a savepoint; a failure is logged, never stops provisioning. The cockpit's log
reads "<admin login> approves bank details for <company>; the platform support login does not."

- Proven on a clone of the live golden template (K5): the real admin step, then the Apply step
  as each login.
- **payobook_template itself is left as it is** (Finance still held by the support login): the
  code rule already means the support login is never asked there, and every new clone is
  re-seated by the step above.
- Note: Finance is one responsibility, so in a new tenant the admin is also the Finance person
  for any other route that asks Finance (pay-run sign-off, payment release…). In the template
  those were the support login too; the client's own admin is the sensible holder.
- Existing tenants (rize, sudima) are not re-provisioned.

## R6. "If X proposes a bank change, who is asked?" — every company, all five databases

Read-only census after the deploy and the rize change (`census.py`, server-side, rolled back):
for each company, every active staff login that can send one in (can read employee records and
change employee or contract records), the Apply step's own answer. "Anyone else" = who would be
asked for a proposer who holds no seat.

| Database · company | If this person proposes | Who is asked |
|---|---|---|
| **rize · Rize Farms** | ash@biztinct.com | debalina@rize.farm, thao@rize.farm, wildan@rize.farm |
| | debalina@rize.farm | ash, thao, wildan |
| | thao@rize.farm | ash, debalina, wildan |
| | wildan@rize.farm | ash, debalina, thao |
| | indo@demo; platform support login | ash, debalina, thao, wildan |
| | (komal@rize.farm cannot send one in) | — |
| **sudima · Sudima Panels Vietnam** | hr@sudima.local | ash@biztinct.com (the owner's own login on sudima, made 2026-11-05) |
| | ash@biztinct.com | hr@sudima.local |
| | anyone else | hr@sudima.local or ash@biztinct.com |
| **payobook_template · My Company** | nobody can send one in (the only staff login is the support login, which has no right to change employee records) | anyone else: **nobody** — "Nobody else in My Company can approve bank details yet — add one in Access." (by design; new clients are re-seated, R5) |
| **p0clone · My Company** | same as the template | **nobody** (same sentence) |
| **payobook · Your Company, Payobook, Payobook Singapore Pte Ltd** | ash@biztinct.com ("Mitchell Admin" there) | look.p4@payobook.com, qa.test@payobook.com |
| | look.p4@payobook.com or qa.test@payobook.com | ash@biztinct.com |
| **payobook · Payobook Vietnam JSC** (demo world) | any of 192 logins (ash, demo@payobook.com, the sign-up and demo logins…) | the `payobook` login (backup of the self-service Finance holder) |
| | the `payobook` login | 78avanda@gmail.com, demo.hr@example.com, look.p4@payobook.com, ash@biztinct.com, qa.test@payobook.com, tuan.quach@example.com |
| **payobook · SG Company** | archived company | — |

Logins left out by the rule: rize and sudima the support login; payobook the 186 demo-role
logins (none had been an approver); template/p0clone the support login.

**Sudima's answer (handover §2.3):** not "nobody". hr@sudima.local and ash@biztinct.com each
approve the other's bank changes. Note that ash@biztinct.com is the owner's own login, not one
of Sudima's people (owner item 1).

## R7. Deploy evidence and the live suite

Unit `updates-p3c-20261112T075430Z` under `flock /tmp/payobook-studio-deploy.lock`;
START 07:54 UTC in `/opt/deploy-notes.md`. Evidence `/tmp/updates-p3c-20261112T075430Z/` and
`/tmp/p3c_ev/` on the server.

- Before: the three server trees byte-identical to the pre-phase commit `5cbb6f31b`
  (pb_records b50cbf158387a7ad, pb_updates 8936cd5cc3465122, pb_tenants 7d8826f1bbe3091b).
- Five dumps first: `/odoo/backups/updates-p3c-20261112T075430Z/` — payobook 80,534,939 B,
  payobook_template 27,815,651, p0clone 28,149,411, rize 41,596,822, sudima 27,992,017; plus
  the three previous trees; plus `rize.pre-d14.dump` (41,532,194 B, 08:05, right before R4).
- `-u pb_records` ×5 (`pb_records,pb_tenants` on payobook): EXIT=0, **0 ERROR/CRITICAL** in
  every upgrade log.
- **Downtime 99 s** (07:56:06–07:57:45 UTC). No test in the stopped window (G19).
- Active scheduled jobs: identical id lists before/after — 50 / 32 / 39 / 82 / 81; nothing
  re-activated, nothing lost.
- Assets: signal row + purge + `web.assets.version` bump on all five.
- Sites after start: payobook.com, rize, p0clone, sudima 200. Server log since start: 0 ERROR.
- Users (count/active), every group membership (hash), every approval responsibility (hash),
  mail queue: **identical before/after on all five**. payobook pay-run totals hash
  `ecc1827c…` before = after.
- Tree hashes repo = server: pb_records adfe91a4cad8bd71, pb_updates d761dd442c11902c,
  pb_tenants a2451714995de151 (before the test-only fix below; after it pb_records
  a51de96203138e9e, pb_updates 2b8bbb6b8a3671b4).

| Check | payobook | payobook_template | p0clone | rize | sudima |
|---|---|---|---|---|---|
| `pb_records` latest_version | 19.0.1.10.1 | 19.0.1.10.1 | 19.0.1.10.1 | 19.0.1.10.1 | 19.0.1.10.1 |
| `pb_updates` | 19.0.1.5.0 | 19.0.1.5.0 | 19.0.1.5.0 | 19.0.1.5.0 | 19.0.1.5.0 |
| `pb_tenants` | 19.0.2.5.1 | not installed | not installed | not installed | not installed |
| active jobs before → after | 50 → 50 | 32 → 32 | 39 → 39 | 82 → 82 | 81 → 81 |

**Live p0clone suites after start, first run: 244 of 247, 3 failures + 2 errors — all in tests,
none in the product.** p0clone's only Finance holder is the platform support login. Three older
pb_records fixtures (`test_records_r2_desk` 05a/05b, `test_records_r3_roundtrip` 07, the P2a
look-ups fixture) WRITE bank details by having "whoever holds the seat" approve — that was the
support login, which is now (correctly) never seated, so no seat existed. Local test databases
hide this (Finance = administrator; G55). Fix: `bank_second.ensure_second_person` gives the
fixture company a Finance holder of its own first. And K1d created a login p0clone already has
(now reused). Re-run locally on a copy of the live template's shape, then the test files only
were synced to the server (no restart: the running service never loads tests).
Commit `a9a0b691d`; synced at 08:13 UTC under the lock with its own START/DONE lines (tree
hashes pb_records a51de96203138e9e, pb_updates 2b8bbb6b8a3671b4 = repo). **Second run on live
p0clone: 260 of 260, 0 failed, 0 ERROR lines** (08:18 UTC). Afterwards: sites 200, server log
0 ERROR since start, active jobs still 50 / 32 / 39 / 82 / 81. DONE line 08:18 UTC.

## R8. Item 4 — does "add one in Access" lead somewhere a tenant admin can act?

**Yes, for the sentence as it stands; no affordance was added.** The sentence appears only when
the bank route asks Finance and nobody other than the proposer (and the excluded logins) holds
it or is a records manager. A records manager IS a second person (P3a). In Access, a person
who manages access (the tenant admin) can give anybody a role carrying the payroll-manager or
HR-manager permission — on every tenant five such roles exist ("Payroll manager", "Payroll
approver — final", "Payroll administrator", "HR records administration", "Tenant
administrator"; census on rize, sudima and the provisioned template clone). From that moment
the person is asked (P3a F5c; K1c). Who manages access today: rize — ash and the support
login; sudima — ash and hr@sudima.local; a new tenant — its admin.

What a tenant admin can NOT reach: the **Approval Matrix** (Settings › Approval Matrix, where
the Finance responsibility and the bank route itself are set). The Tenant administrator role
does not include "approvals set-up"; on rize and sudima only ash and the support login can open
it (G57). That matters for the second sentence, which only rize can show (its route names
people): adding a person to rize's bank route needs ash. Owner item 3.

## R9. Deviations from the handover, and why

1. **A route that names its approvers is never widened** (not asked for). Without it, rize's
   guarantee would hold only while one named person besides the proposer is available; with
   all of them away the P3a fallback would ask the records managers — `indo@demo` among them.
   New sentence for that case (R3), Vietnamese included.
2. **Support login recognised by its login, read from the platform's setting** — there is no
   xmlid or flag on the account (G54). The handover allowed this when no flag exists.
3. **Demo marker = the demo role**, which exists on payobook only; `indo@demo` is handled by
   rize's route (as the handover prescribes when there is no reliable marker).
4. **rize's route published as the platform support login** (the 2026-09-18 precedent for
   changes made on the owner's behalf). The route's history shows "Platform support (recovery
   account)" as publisher with the reason. That login still cannot approve a bank change.
5. **The write-time rail also ignores an excluded login's yes** (K2b) — belt and braces, so a
   future path that skips `decide` cannot let it count.
6. **Three older pb_records test fixtures changed** (R7) — they now bring their own Finance
   holder; assertions unchanged.
7. **pb_updates shipped files-only** (tests only, version unchanged).
8. **In a new tenant the admin holds Finance for every route that asks Finance**, not only bank
   details (one responsibility; R5).

## R10. New gotchas (ledger G54-G59)

Support login has no xmlid or flag (named by a setting); local test databases hide fixtures
that rely on the support login holding Finance (always also run on a copy of the live
template's shape); a plain login with no seat cannot even read a bank request (AccessError
before the decide check); Tenant administrator cannot open the Approval Matrix; `odoo-bin
shell` logs into the server log unless `--logfile` is given; F18's local artefact.

## R11. Needs an owner decision / owner action

1. **sudima:** hr@sudima.local's bank changes are approved by **ash@biztinct.com — your own
   login**, not one of Sudima's people (and hr@sudima.local approves yours). If a Sudima person
   should approve, give them a payroll-manager role in Access (or the Finance responsibility).
2. **payobook_template and p0clone:** nobody can approve a bank change there ("Nobody else in My
   Company…"). Expected for the template (new clients are fixed at creation); p0clone is an
   internal copy — say if it needs an approver.
3. **rize — a new Rize approver later** has to be added to the bank route by ash (Approval
   Matrix); a tenant admin cannot open that screen today (R8). Say if the Tenant administrator
   role should include "approvals set-up".
4. **indo@demo on rize** keeps its payroll-manager rights for everything else (D14: nothing else
   changes); it can still SEND a bank change, which goes to ash, debalina, thao or wildan.
5. Unchanged from P3a §R15: payobook demo world's bank approver is the `payobook` login (the
   Finance holder there is a self-service login); bank approvals need one person, not two (D13
   confirms that).
