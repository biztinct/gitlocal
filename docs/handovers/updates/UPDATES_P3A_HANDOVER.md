# UPDATES — Phase 3a handover: approval split by type, bank second check, month-only pay file, old import retired

Read first: `UPDATES_LEDGER.md` (all of it), `UPDATES_P2C_REPORT.md` §R9 (this phase's
research — do not re-derive it, do re-grep line numbers), `UPDATES_P2D_REPORT.md` §R9 and
its deviations. Visual reference: `docs/design/updates-desk-prototype.html`.

**Design mandate (owner, verbatim): "extreme WOW, intuitive, out-of-this-world experience,
best in class".** Indigo design system (`#5A4BB0`), white cards, Lucide icons, never emoji.

**White-label rule:** the word "Odoo" never appears in any user-visible string (labels,
tooltips, toasts, errors, `string=`, `help=`, selection labels, menu/action names, exported
text, `.po` msgstr). Technical identifiers stay. **Plain words on screen.**

First job: add to the ledger owner decision **D12** (below) and split the phase map's P3
row into P3a (this) and P3b (new joiners from a sheet, drafts, "what changed since the last
pay run" line).

## 1. Owner decisions that bind this phase — do not re-ask

- **D3** Approval split by type: person details apply at once; pay changes go to approval;
  bank details always need a second person.
- **D1** The pay run's pay data file is month-only; lasting changes come through Updates.
- **D12 (2026-11-11)** A person who has only an employee self-service (portal) login CAN be
  named as somebody's manager or coach. They are recorded as the manager; **their login is
  not changed** and they get no extra screens. Nothing fails.

## 2. Scope

1. **Three lanes for one file** (D3): personal details · pay and contract · bank details —
   each its own change, own approval behaviour, own line on every screen.
2. **Bank second check**: a bank-details change is never carried out on the say-so of the
   person who proposed it alone.
3. **D12**: naming a portal-login person as manager/coach works, from Updates and from the
   Records screen.
4. **D1**: every door through which a person uploads a pay data file for a pay run is
   month-only; the lasting-write code paths stay for the connected-system lane only.
5. **The old employee import is retired** from every screen, and its typed-code execution
   is removed.
6. **Demo pay runs pick up one-offs** (P2d report, owner item 1): the demo shortcut on
   `payobook` reads Updates one-offs like a normal run, without pressing Recalculate.

Versions: bump every module you change (patch or minor as fits); `pb_records` and
`pb_updates` minor.

## 3. Binding non-goals and safety rails

- **No lane ever becomes weaker than today.** A company whose records route today sends
  everything to approval keeps approval on pay and bank. The only relaxation is the one
  the owner chose: the personal-details lane applies at once (see §4.2 for the exact rule
  and its switch).
- **All-or-none per lane**, same `_write_plan`, same moved-since check, same undo. No second
  write engine.
- **Bank lane fails closed.** If no second person can be found, the change waits and says
  why; it is never carried out by its proposer, never auto-approved, never skipped — also
  for companies set to "No approval needed", for scheduled changes on their day, and for
  "Start now".
- **Do not change the approval engine's behaviour for any other process** (hiring, leave,
  pay run, workflow tasks…). Any engine change must be opt-in per process and proven
  inert for the others (test F12). The engine's "carried out" wording for scheduled
  changes (G29) is NOT in scope.
- **D1 must not break**: the connected-system lane (`integration_cron.py:531`,
  intentionally lasting), `pb_payroll_templates`' "Keep for future payrolls" (already
  routed through the desk), or any existing pay-run suite. The month's payslips must
  compute byte-identically for a file that was already uploaded one-time (test F16).
- **Retiring ≠ deleting data.** Remove menus, tiles, buttons and the unsafe code path; do
  not drop models or tables that hold rows on any of the five databases (check first);
  never delete demo data.
- No new joiners from a sheet, no drafts, no "what changed" line (P3b). No timesheets (P4).
- Never apply anything on `rize` or `sudima`; do not touch sudima's two waiting changes.
- Do not touch `pb_lifecycle`, `pb_hiring`, `pb_me_expense`, `pb_timeoff`,
  `docs/handovers/workflow2`.

## 4. Design

### 4.1 Lanes

`pb.updates.desk` already splits one file into several `pb.records.apply` rows under one
batch (P2c: by start date and by `hold_scope`). Add the lane as a second splitting axis and
store it on the apply: `lane` Selection `details` / `pay` / `bank` (empty on applies made
before this phase and on Records-screen applies that are not split — see below).

| Lane | Columns |
|---|---|
| `bank` | every `b:` card |
| `pay` | every `c:` card; every `contract`-group field; and any `employee`-group field the desk already treats as pay (`_plan_touches` / `SALARY_TOKENS`) |
| `details` | the rest of the `employee` group |

Fix on the way: `SALARY_TOKENS` matches "Payment method" as pay by a word match (P2c §R9.1).
Replace the guess for lane purposes with an explicit list of field names reviewed against
`_master_fields()`; put the list in the report. Keep `touches_salary` as it is for existing
routes unless a test proves it wrong.

The Records screen (grid edits and its own import) also splits by lane when a proposal
mixes lanes — the bank rule must not be avoidable by using the other door. One proposal
there becomes up to three applies; its toast and History list them. Unmixed proposals
behave exactly as today (test F11).

### 4.2 What each lane does

- **details** — applies at once, no approval, WHEN the company's records route is the
  shipped default or "No approval needed". If the company has deliberately configured its
  own records route (anything other than the default definition — detect by comparing with
  `_records_definition`, report how), details keep following that route: an owner's
  explicit set-up is never overridden. A per-company switch
  "Personal details from a sheet apply without approval" (default ON) on the same
  set-up surface where the records route is edited lets a company turn it off.
- **pay** — the records route, exactly as today (process key unchanged).
- **bank** — its own process key through `_approval_process_key_for` (precedent
  `payroll_import_approval.py:58-69`), default definition = ONE step, "a second person":
  the Finance role when the company has one held by somebody other than the proposer,
  else any Records manager other than the proposer; `independent`. Strict rule, enforced
  in the adapter (not by a general engine change): the user who decides may not be the
  apply's proposer (`create_uid`) — refuse with "Bank details need a second person. You
  proposed this change, so somebody else has to approve it." If the engine has no
  per-process hook where an adapter can veto a decision, add the smallest opt-in hook
  (`_approval_may_decide(request, user)` returning a sentence or None), called only when
  the adapter defines it. "No approval needed" for records does NOT apply to the bank key:
  seed the bank definition on install/upgrade for every company (idempotent, `noupdate`
  semantics: never overwrite a definition somebody edited).
  If nobody else can decide: the request stays waiting and the Updates row says "Waiting
  for a second person. Nobody else in <company> can approve bank details yet — add one in
  Access."
- Start dates (P2c): unchanged per lane — bank and details are never "dated" unless
  `hold_scope='all'`, in which case they are scheduled like the rest but the bank lane
  still needs its second person BEFORE it is scheduled.
- CLEAR on bank stays refused (P2b). One-offs (P2d) are their own kind of sheet and are
  not laned.

### 4.3 D12 — manager with a self-service login

P2c report R10.1: setting such a person as manager fails inside the write because of a
login-tier clash (a manager role is granted on write). Find the exact write that grants
the role (start from the traceback in `outputs/updates-p2c/` or reproduce locally with a
portal-login employee as `parent_id`), and make the manager/coach assignment NOT touch the
named person's login or groups when that login is portal-tier: record the reporting line
only. Do not weaken the guard that stops a portal login receiving staff groups — skip the
grant, do not bypass the check. Same result from Updates, the Records screen and the
employee form. Report which module carried the grant and whether anything else (org chart,
My Team, approvals "manager" step) assumed the manager has a staff login; an approval step
that resolves to such a manager must fall back the way the engine already does for a
manager with no login at all.

### 4.4 D1 — pay data file month-only

Force `one_time=True` and both auto-create flags off, server-side, on the doors a person
uses to upload a pay file for a run: the Import screen's "Load Pay Data"
(`pb_import/models/pb_import.py:47-48`) and `pb_payrun_wizard` without
`pb_payroll_templates` (front-end default "update", `payrun_wizard.js:51`) — and any
other door your grep finds (`one_time` / `auto_create_employees` writers). Remove the
"update records" choice from those screens; where it was, one quiet line: "This file is
used for this pay run only. To change employee, contract or bank records, use
People › Updates." with a link. A row for a person who does not exist is a plain
"needs attention" row ("Nobody matches this row. Add the employee first."), never a new
employee. Leave the batch model's lasting-write code in place (the connected-system lane
uses it) but make the server refuse `one_time=False` unless the call comes from that lane
(context key set only in `integration_cron`), so no client can switch it back on.

### 4.5 Old employee import

`employee.import.wizard` (`pb_hr_payroll_base/wizards/employee_import_wizard.py`) and its
doors (`pb_hr_payroll_base.action_employee_import_wizard` on the country payroll
dashboards; the Import screen's "Import Employees" tile →
`pb_import_advanced.action_pb_employee_wizard`): remove every menu, tile and button;
point the Import screen tile to People › Updates instead (label "Update employees from a
sheet"); delete the `exec()` of typed code (`:509-516`) outright; leave the wizard model
loadable but unreachable if removing it would orphan stored rows or views on any of the
five databases, otherwise remove it cleanly (report which). `pb_hr_payroll_base` is a base
module: upgrading it re-activates dependents' scheduled jobs (memory note
`cron-snapshot-boolean-trap`) — snapshot and restore precisely, or avoid upgrading it by
making the change from a module that depends on it. Lessons/tours that mention the old
import must be updated in the same work (memory note `lessons-follow-screen-changes`).

### 4.6 Demo pay runs and one-offs

P2d deviation 1: payobook's demo pay runs use a demo shortcut that reads no inputs. Make
that shortcut pass through P2d's reader (`pb.updates.oneoff._for_slip` and the shared
merge) so an approved one-off lands without "Recalculate". Demo module only; no change to
real compute paths; existing demo runs' figures must not change (all 47 balance — memory
note `demo-world-payroll-figures-fixed`).

### 4.7 Screens (`pb_updates`, `pb_records`)

- **Review**: column headers carry a small lane tag (user-round `details`, banknote `pay`,
  landmark `bank` — Lucide) and the three lanes get a legend strip with counts.
- **Apply step**: one card per lane present in the file, each saying in plain words what
  will happen: "Personal details · 42 values · change now" / "Pay and contract · 12
  values · go to <who> for approval" (the real route's names, as today) / "Bank details ·
  3 values · need a second person: <names>" (or the nobody-else sentence, in amber). The
  primary button states the outcome ("Apply 42 and send 15 for approval").
- **Done / Past updates / Coming up**: a batch shows its lanes as separate lines with
  their own state; cancel and undo act per lane as well as for the whole batch.
- **Approvals inbox**: a bank request reads "Bank details for N people" with old → new
  masked except the last 4 characters of an account number, and the proposer cannot
  approve it (button disabled with the sentence; server refuses regardless).
- **Records screen**: toast and History show the split when a proposal was mixed.
- Vietnamese for every new string (G2, G6).

## 5. Tests (numbered)

| # | Case | Expect |
|---|---|---|
| F1 | File with details + pay + bank columns, default route | three applies under one batch; details applied; pay follows the records route; bank waiting for a second person |
| F2 | Company with "No approval needed" for records | details and pay applied at once; bank still waits |
| F3 | Company with its own configured records route | details follow that route (not applied at once); switch off/on behaves as §4.2 |
| F4 | Proposer tries to approve their own bank change (UI path and direct RPC) | refused with the sentence; nothing written |
| F5 | A second person approves | written; audit names both |
| F6 | Nobody else can approve | stays waiting; the nobody-else sentence; never written |
| F7 | Bank lane with a future date and `hold_scope='all'`; "Start now" by the proposer | second person first; never written on the proposer's action alone |
| F8 | Undo / cancel per lane and for the whole batch | each lane restored / cancelled independently |
| F9 | Lane field list | every Master-records field is in exactly one lane; "Payment method" where the report says |
| F10 | Records screen mixed proposal (grid, and its import) | split into lanes; bank needs a second person |
| F11 | Records screen unmixed proposal; Updates file with one lane | identical to before (capture before, compare after) |
| F12 | Another process's approval (pick two: leave, pay run) with the new hook present | byte-identical decisions and log lines |
| F13 | Bank definition seeding | present once per company after upgrade; an edited one is not overwritten on re-upgrade |
| F14 | D12: portal-login person as manager from Updates, Records screen, employee form | recorded; the person's groups and login tier unchanged; no error; an approval "manager" step falls back |
| F15 | D1: each upload door with a client forcing `one_time=False` / auto-create on | server forces month-only; unknown person = needs attention; no employee, contract, bank or pay-item line written |
| F16 | D1: a one-time file through each door, before vs after | identical payslips |
| F17 | Connected-system lane | still writes lasting values |
| F18 | Old import: every former door; the `exec` path | unreachable / gone; Import tile opens Updates |
| F19 | Demo run with an approved one-off; the existing demo runs | lands without Recalculate; existing figures unchanged |
| F20 | Full suites of every module touched + `pb_records`, `pb_updates`; review speed 4,575 × 73 | green (same pre-existing failures only, listed); ≤ 25 s |
| F21 | `.po` parse gate; "Odoo" scan of new and touched strings | clean |

## 6. Browser validation, deploy, report

- Browser (local copy, console read at every step, the people's company — G22): the
  three-lane flow end to end with two different users (proposer and second person), the
  proposer's disabled approve, the nobody-else state, Records screen mixed proposal, a
  portal-login manager, each pay-file door showing month-only, the Import screen tile.
  Screenshots to `outputs/updates-p3a/` (never committed).
- **Tier 3** on all five (`payobook`, `payobook_template`, `p0clone`, `rize`, `sudima`;
  never `abm`, `pbf_preview`, `recruit_connect_20261023`): deploy-notes START/DONE + the
  flock (wait if the other session holds it); `pg_dump` of all five first; rollback note
  written before deploying; scoped per-module rsync, only modules you changed, never the
  repo's copies of standard addons; cron snapshot before/after with the id→active list
  (expect no new job; restore anything a base-module upgrade re-activated); asset purge;
  **no tests in the stopped window** (G19); hashes and versions on all five; suites on
  live `p0clone` after start on free ports.
- Before deploying, list for each of the five databases: the records route in force per
  company, whether a Finance role holder exists, and therefore what each lane will do
  there from tomorrow — put the table in the report (the owner will be told in plain
  words). If on `rize` or `sudima` the bank lane would have nobody able to approve, say so
  prominently; do not create users or roles there.
- Live check on `payobook`, server-side: QA user proposes a three-lane change for DEMO
  people → details applied → QA cannot approve the bank lane → a second existing internal
  demo user (not the owner's admin account) approves it, or, if none qualifies, the bank
  lane is cancelled and that is reported → everything undone/cancelled and proven
  restored; a month-only pay file door check on a database copy with jobs and mail
  switched off (memory note `copy-db-runs-live-crons`), dropped afterwards. Look-only in
  the browser on `payobook`. Never sign in to a live site with a password; the QA password
  stays only in the memory note.
- Commit per feature with explicit paths, credential scan, push `origin 19.1`.
- Report `UPDATES_P3A_REPORT.md`: F1–F21 with output; the lane field list; the per-database
  "what each lane does" table; the engine hook (if added) and proof it is inert elsewhere;
  where the manager role grant lived; every pay-file door found; what happened to the old
  import's model; deploy evidence ×5; deviations; new gotchas; ledger updated. For P3b,
  from the code with file:line: (1) the smallest safe way to create an employee + first
  contract from a sheet row by reusing `pb.people.onboard.wizard.create_employee`
  (new-hire approval included), and what a "Pay scheme" column would have to set given
  the scheme map resolves by team; (2) where a half-finished Updates file could be parked
  server-side (existing attachment/batch fields) for a "draft" that survives closing the
  browser; (3) what the pay-run preparation would query to list "changes since the last
  finished pay run" per person (Records audit rows, one-offs, scheduled changes).
