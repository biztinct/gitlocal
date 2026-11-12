# UPDATES — Phase 3c handover: who may approve bank details (owner decisions D13–D15)

Small set-up phase. Read first: `UPDATES_LEDGER.md`, `UPDATES_P3A_REPORT.md` §R7 (what each
lane does per database), §R8 (the engine seams) and §R15.

First job: add D13–D15 to the ledger and a P3c row to the phase map.

**White-label rule:** the word "Odoo" never appears in any user-visible string. Plain words
on screen. Lucide icons, never emoji.

## 1. Owner decisions (2026-11-12) — do not re-ask

- **D13** A bank-details change needs ONE second person (never the proposer). Already what
  P3a ships; no change.
- **D14** On `rize`, only Rize's real people approve bank details: **debalina, thao,
  wildan** stay; the demo login `indo@demo` and the platform support login
  (`platform.recovery@payobook.com`) must NOT be able to approve a bank change there.
  Nothing else about those two logins changes.
- **D15** For a NEW client created from the template, the client's own admin login is the
  bank approver; Payobook's support login is not an approver of a client's bank details.
  If the admin proposes a bank change themselves, the existing "nobody else … add one in
  Access" sentence applies.

## 2. Scope

1. **A general rule, in code** (`pb_records` bank adapter from P3a): the platform support
   login and demo logins are never SEATED on the bank route and can never decide a bank
   request — the same way P3a already never seats employee-only logins (P3a deviation 10).
   Identify "platform support login" the way the tenant platform already identifies its
   protected recovery login (memory note `tenant-admin-protected-login`; grep `pb_tenants`
   / the recovery user's xmlid or flag — do not match on an email string if a flag or
   xmlid exists). Identify "demo login" only if the build already has a reliable marker
   (e.g. the `@demo` logins created by the demo generator carry one); if there is no
   reliable marker, do NOT invent a guess — handle `indo@demo` on rize by set-up (item 2)
   and report.
2. **rize set-up (D14)** — the one change to rize's stored set-up this programme makes, by
   explicit owner decision: make sure the people who can be seated for bank approvals at
   rize are exactly debalina, thao and wildan (plus ash, who is skipped when ash is the
   proposer). Find WHY `indo@demo` and the support login qualify today (Finance
   responsibility holder / backup / Records manager group) and remove only that
   qualification FOR THE BANK ROUTE. Prefer the narrowest lever: if item 1's rule already
   excludes both, change nothing stored on rize. If a stored change is still needed,
   change the bank route's seat/definition for rize's companies — do not remove a group or
   responsibility that the login uses for anything else, and do not touch
   `rize-approvals-independence-off` (owner decision). Snapshot before, show after, write
   the exact undo statements in the report.
3. **New clients (D15)**: where a tenant is created from the template (`pb_tenants`
   provisioning — find the step that creates the tenant admin), make the tenant admin the
   holder of whatever the bank route seats first (the Finance responsibility for the
   tenant's company, if that is the lever P3a's default definition reads), and make sure
   the support login holds no bank-approver seat in a newly created tenant. On
   `payobook_template` itself the stored state may stay as it is if item 1's rule already
   stops the support login approving; say which. Existing tenants (`rize`, `sudima`) are
   not re-provisioned: for `sudima`, only REPORT who can approve bank details after item
   1's rule (if the answer is "nobody", say so prominently — the owner will be asked).
4. **Access screen wording**: wherever a company's bank approver is shown or the
   "nobody else" sentence appears, the fix must be reachable — confirm the sentence's
   "add one in Access" path really leads to a place where a tenant admin can give a
   person the right to approve bank details; if it does not, add the smallest
   link/affordance and report.

## 3. Non-goals and rails

- No change to any other approval process or to the engine's behaviour elsewhere (re-run
  P3a's F12 inertness test).
- The bank lane still fails closed in every path (re-run F4–F7).
- Do not create, delete, archive or re-password any user on any database. Do not change
  anybody's groups except as item 2 strictly needs, and prefer not at all.
- Never touch `abm`; never apply an Updates change on `rize`/`sudima` (the D14 set-up
  change is the only stored change there, and only if needed).
- Do not touch `pb_lifecycle`, `pb_hiring`, `pb_me_expense`, `pb_timeoff`,
  `docs/handovers/workflow2`. `pb_tenants` is not deployed to tenant databases (memory note
  `tenant-module-sync-rule`) — respect that.

## 4. Tests

| # | Case | Expect |
|---|---|---|
| K1 | Support login is the only Finance holder; somebody proposes a bank change | not seated; waits with the "nobody else" sentence |
| K2 | Support login tries to decide a bank request by direct call | refused |
| K3 | Support login in any OTHER process's route | unchanged (inert) |
| K4 | Demo-marked login (only if a reliable marker exists) | never seated for bank |
| K5 | New tenant provisioned in a test | tenant admin is the bank approver; support login is not |
| K6 | P3a F4–F7, F12, F13 | still pass; full `pb_records` + `pb_updates` suites green |
| K7 | "Odoo" scan + `.po` gate for any new string | clean |

## 5. Deploy and verify

Tier 2 for code on all five (`payobook`, `payobook_template`, `p0clone`, `rize`,
`sudima`), plus the rize set-up change if needed (back up `rize` first with `pg_dump`;
write the undo statements before running it). Deploy-notes START/DONE + flock; scoped
per-module rsync; cron snapshot before/after; no tests in the stopped window (G19); hashes
and versions ×5. After deploy, for EVERY company on all five databases, compute (read-only,
server-side) "if X proposes a bank change, who is asked?" for each person able to propose,
and put the table in the report. On rize the answer must contain only debalina, thao,
wildan and ash. Commit with explicit paths, credential scan, push `origin 19.1`.

## 6. Report — `UPDATES_P3C_REPORT.md`

K1–K7; how the support login and demo logins are recognised; what (if anything) was
changed on rize, with before/after and undo statements; the provisioning change; the
per-database "who is asked" table; sudima's answer; deviations; new gotchas.
