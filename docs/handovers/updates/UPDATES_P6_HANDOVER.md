# UPDATES — Phase 6 handover: a client's admin manages approvals for their own company

Runs in parallel with Phase 4 (which works in `pb_updates`). **Do not edit `pb_updates`,
`pb_records/models/*` logic, or any file Phase 4 is touching**; this phase lives in the
approvals and access modules. Ledger edits: append-only, re-read the file immediately
before editing, and `git pull --rebase`-safe (commit only your explicit paths).

Read first: `UPDATES_LEDGER.md`; `UPDATES_P3C_REPORT.md` (who is asked for bank changes,
the "named approvers are never widened" rule, the "add one in Access" sentence);
`UPDATES_P3A_REPORT.md` §R8. Memory notes (in
`/Users/adity/.claude/projects/-Users-adity-Documents-GitHub-gitlocal/memory/`):
`approval-matrix-program`, `access-program`, `access-desk`, `tenant-admin-protected-login`,
`access-preview-palette-gates`, `tab-gate-probe-fix`, `rize-approvals-independence-off`.

**White-label rule:** the word "Odoo" never appears in any user-visible string. Plain
words on screen. Lucide icons, never emoji. **Design mandate (owner, verbatim): "extreme
WOW, intuitive, out-of-this-world experience, best in class".**

## 1. Owner decisions (2026-11-12) — do not re-ask

- **D21** Sudima's bank approvals stay as they are for now (the owner's login and
  Sudima's HR login approve each other's). Change nothing on `sudima`.
- **D22** A client's own admin (the Tenant administrator role) can open approvals set-up
  for their own company and choose who approves what — bank details, pay changes and the
  rest. They cannot see other clients.

## 2. Scope

1. The Tenant administrator role can open and use the approvals set-up screen (the
   Approval Matrix and what it needs: routes, steps, responsibilities/role holders,
   backups) for the companies of their own database.
2. The "Nobody else in <company> can approve bank details yet — add one in Access"
   sentence (and its Approval-Matrix twin from P3c) carries a link that takes a tenant
   admin straight to the place where they can add that person.
3. An audit line for every approvals set-up change made by a tenant admin (who, when,
   what changed) — reuse the matrix's existing versioning/audit if it already records
   this; report what it records.

## 3. Rails (binding)

- **Find first, then grant narrowly.** Establish exactly which groups/ACLs/record rules/
  menu and client-action gates the Approval Matrix and its RPC methods check today, and
  which the Tenant administrator role has. Grant through the existing Access catalogue
  mechanism (the way roles receive capabilities with an audit row), not by adding
  `base.group_system` or any broader stock group to the role.
- **A tenant admin must not be able to weaken code-enforced rails**: the bank second
  person (proposer can never approve; support and demo logins never seated; bank lane
  fails closed) is enforced in the adapter and must stay true whatever a route says —
  re-run P3a F4–F7 and P3c K1–K4 with a route edited by a tenant admin to "No approval
  needed" and to "proposer approves".
- **A tenant admin must not be able to**: grant themselves or anyone the platform/support
  capabilities; see or edit the protected support login; change another database (already
  structural: one database per client — confirm no cross-database surface is reachable
  from the screen); edit the approval ENGINE's definitions of process types (only routes
  and who holds a seat).
- **Owner decisions stay put**: `rize-approvals-independence-off` and rize's bank route
  from P3c are stored set-up; this phase does not alter them (a rize tenant admin could
  later — that is the point of D22).
- No behaviour change for any approval decision path. No new approval process.
- Change nothing stored on `rize` or `sudima` beyond what a module upgrade itself does
  (the role gaining the capability). If the role's capability is stored per database and
  needs a data step, do it identically on all five through the module upgrade, and list
  exactly which users gain the screen on each database BEFORE deploying — if any login
  that is not a client's intended admin would gain it, stop and report.
- Do not touch `pb_lifecycle`, `pb_hiring`, `pb_me_expense`, `pb_timeoff`,
  `docs/handovers/workflow2`, `pb_updates`. `pb_tenants` is not deployed to tenants.

## 4. Tests

| # | Case | Expect |
|---|---|---|
| M1 | Tenant admin opens approvals set-up, edits a route, changes a role holder and a backup | allowed; saved; audit line |
| M2 | A plain HR/payroll manager, an employee-only login | still refused exactly as today |
| M3 | Tenant admin tries each forbidden thing in §3 (direct RPC as well as the screen) | refused |
| M4 | Bank route edited by a tenant admin to weaken it; then P3a F4–F7, P3c K1–K4 | code rails still hold |
| M5 | The "nobody else" link as tenant admin / as someone without the right | lands on the right place / link hidden or leads to a plain "ask your administrator" sentence |
| M6 | Every other approvals suite + `pb_records` + `pb_updates` suites | green |
| M7 | Who gains the screen, per database | exactly the intended tenant admins (table in the report) |
| M8 | `.po` parse gate; "Odoo" scan of new strings | clean |

## 5. Browser validation, deploy, report

- Browser (local copy, console read at every step): as a tenant admin — open the screen,
  add a bank approver, see a waiting bank change become approvable by that person; as a
  manager without the role — no access. Screenshots to `outputs/updates-p6/`.
- Tier 3 on all five (`payobook`, `payobook_template`, `p0clone`, `rize`, `sudima`; never
  `abm`, `pbf_preview`, `recruit_connect_20261023`): deploy-notes START/DONE + flock (Phase
  4 uses the same lock — wait, never overlap); `pg_dump` ×5; rollback note first; scoped
  rsync of only your modules; cron snapshot with the id→active list and precise restore
  (an access/base-module upgrade re-activates dependents' jobs — memory note
  `cron-snapshot-boolean-trap`); asset purge if JS changed; no tests in the stopped window
  (G19); hashes and versions ×5; suites on live `p0clone` after start on free ports.
  Before your dry-run rsync, re-check that you are not shipping Phase 4's half-done files:
  deploy only modules whose diff against the server is entirely yours.
- Live check: read-only — per database, list who can now open approvals set-up; on
  `payobook`, look-only in the browser with the existing session. No route is edited on
  any live database.
- Commit with explicit paths, credential scan, push `origin 19.1`.
- Report `UPDATES_P6_REPORT.md`: M1–M8; the gates found and exactly what was granted; the
  per-database table of who gains the screen; what the audit records; deploy evidence ×5;
  deviations; new gotchas; ledger (D21, D22, phase map row).
