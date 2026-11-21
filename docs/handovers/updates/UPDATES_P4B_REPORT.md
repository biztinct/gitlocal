# UPDATES — Phase 4b report (HR officers send leave opening balances)

Small follow-up to P4, implemented, tested, deployed and checked on 2026-11-13 (Sydney;
2026-11-12 UTC) by the Opus implementation agent. The agent prompt was the spec (a handover would
have been longer than the diff). Owner decisions D23–D26 are in the ledger.

## R1. What changed

| Module | Version | Where |
|---|---|---|
| `pb_updates` | 19.0.1.7.0 → **19.0.1.7.1** | upgraded on all five (payobook, payobook_template, p0clone, rize, sudima) |

Nothing else. `pb_timeoff`, `pb_lifecycle`, `pb_hiring`, `pb_me_expense` and
`docs/handovers/workflow2` were not edited, staged or deployed. No schema change, no new job.

1. **Who may send** (`_leave_may_set`): an HR officer (`hr.group_hr_user`, constant `SENDER` in
   `updates_leave.py`) or a Time Off administrator. `hr.group_hr_user` is the group P4 meant by "HR
   officers can still check one" (P4 test L12b's officer; the records desk's `_may_read`). Time Off
   officers and administrators hold it too (their groups imply it).
2. **Who may undo** (`_leave_may_undo`, new): Time Off administrators only — unchanged. The Undo
   button (`can_undo`), the Updates undo and the Records screen's undo of a leave update all ask it.
3. **How an officer's balances are written.** P4 writes on approval as the proposer, with the
   proposer's own rights, and refused everything when the proposer was not a Time Off administrator
   ("…no longer has the Time Off administrator role") — so without this change an HR officer's
   approved sheet would have written NOTHING (the P3a class of bug). Now:
   - a Time Off administrator (or the superuser) still writes with their own rights — P4 exactly;
   - an HR officer: the officer's own user runs with superuser rights (`su`) **for the two writes
     of `_write_one` only** — the policy layer's `post_opening_balance` (whose own gate accepts the
     superuser) and one allocation's create + approve. The audit still names the officer
     (`create_uid`, approver on the allocation). Before those writes, per row: the full verdict is
     read again (`_leave_row_check`, as in P4), plus two officer-only rails:
     (a) the person works in one of the officer's companies (else "…works in X, which Y no longer
     works in, so this balance was not set."); (b) **never the officer's own balance** (the native
     Time Off rule that only an administrator approves their own allocation) — refused already on
     the review grid and on Apply: "…cannot set their own leave balance. Ask a Time Off
     administrator or another HR officer to send it."
   - an actor who no longer has the HR officer role at write time: every row "Could not be set",
     "…no longer has the HR officer role, so no balance was set…".
   This is the same capability P4's design uses (Time Off administrator rights over exactly these
   allocations/postings), not wider: no gate, read or other write runs elevated.
4. **Wording, English and Vietnamese** — every sentence that said setting needs the Time Off
   administrator role now says the HR officer role: the Start tile ("Setting them needs the HR
   officer role"), the leave topic line, the Apply step's lock line, Apply's server refusal, and the
   write-time refusal. "Undoing leave balances needs the Time Off administrator role." stays (true).
   Two new sentences (own balance, company). No other screen change.

Commit: `d058dea9a` (feature) · the docs commit carrying this report and the ledger.

## R2. Tests

New `pb_updates/tests/test_updates_p4b.py` on the P4 fixture (its own company, real absence
policy, real allocation flow), 10 cases; P4's `test_L12b` updated (an officer can now send).

| # | Case | Result |
|---|---|---|
| B1 | HR officer (no Time Off right of any kind) sends under "No approval needed": a policy person (12 days, 3 carried, 2 taken → one opening posting through the policy layer, its allocation validated) and a plain person (9 days of a type whose allocations a Time Off officer approves → one validated allocation); both created by the officer; the Time Off screen shows 12 and 9 | PASS |
| B2 | Officer cannot undo: no Undo button, Updates undo and Records undo both refuse ("…Time Off administrator role."); balance untouched; a Time Off administrator then undoes it | PASS |
| B3 | An employee-only (portal) login and a plain manager (internal login, manager of a person): cannot send; nothing created | PASS |
| B4 | A login that can check a sheet but is not an HR officer (records viewer): checks, cannot send ("…needs the HR officer role."), `may_set` false; nothing created | PASS |
| B5 | Officer's own balance: refused on the grid and on Apply (sent past the screen), the other person still goes; a Time Off administrator can set it | PASS |
| B6 | Wording: the old admin-only sentences are gone from the template and the server; no "Odoo" in the touched files | PASS |
| R1 | Real records route: officer's sheet waits with the HR lead (an HR officer without Time Off rights); nothing written before approval; approved → both balances set (policy + plain), created by the officer, Time Off screen 12 / 10 | PASS |
| R2 | Officer loses the HR officer role before approval → every row "Could not be set" with the sentence; nothing written | PASS |
| R3 | Officer moved out of the company before approval → refused ("no longer works in"); nothing written | PASS |
| R4 | A Time Off administrator's sheet on the route: written with their own rights, created by them (P4 unchanged) | PASS |
| L12b | Officer checks and `may_set` is true | PASS |
| Suite | Local isolated tree (G13: `git archive HEAD` + this module), copy of the template shape, `-u pb_records,pb_updates,pb_import_advanced`: **pb_records 134 + pb_updates 244, 0 failed** | PASS |
| Live | p0clone after start (ports 8471/8472): see R4 | PASS |
| .po | `PoFileReader` reads 1,393 rows; all 7 new/changed sentences translated, placeholders identical; 0 "Odoo" in any msgstr; `i18n export -l pot` lists every new sentence | PASS |

## R3. Where an HR officer's sheet goes in with nobody else (census, read only, 2026-11-12 20:48 UTC)

The screen's own question (`leave_outlook`) asked per company in a rolled-back shell on each
database. "HR officers" = active internal logins with the HR officer role but not Time Off
administrator (the people this change gives the power to send).

| Database | Company | Route for a leave sheet | People | HR officers (new senders) | Time Off administrators |
|---|---|---|---|---|---|
| **payobook** | **Payobook Vietnam JSC** (demo world) | **No approval needed — goes in at once** | 4,547 | **187** (mostly demo sign-up logins) | 6 |
| payobook | Your Company / Payobook / Payobook Singapore | waits for Mitchell Admin | 21 / 7 / 0 | 1 | 2 |
| payobook_template | My Company | waits for the platform support login | 1 | 0 | 0 |
| p0clone | My Company | waits for the platform support login | 12 | 0 | 0 |
| **rize** | **Rize Farms** | **No approval needed — goes in at once** | 241 | **5**: debalina, thao, wildan, the demo login `indo@demo`, the platform support login | 1 |
| sudima | Sudima Panels Vietnam | waits for the company's approver | 651 | 1 (the owner's own login) | 1 |

So **an HR officer alone can now set leave balances on payobook's demo world and on rize.** On rize
that includes balances through the absence policy for its 225 people on one, which are permanent
(D26). Every other company needs a second person.

## R4. Deploy evidence

Unit `updates-p4b-20261112T205834Z` under `flock /tmp/payobook-studio-deploy.lock` (free). Tier 2
(normal): no dumps; previous tree kept in `/odoo/backups/updates-p4b-20261112T205834Z/pb_updates.prev`.
START 20:58 / DONE 21:07 UTC in `/opt/deploy-notes.md`. Evidence `/tmp/updates-p4b-20261112T205834Z/`.

- Before: server `pb_updates` tree = HEAD `223263669` (4aa06a4f800e4292). Staged = commit
  `d058dea9a` (e653f679f3d1faf5). Only `pb_updates` copied (scoped rsync).
- `-u pb_updates` on all five: EXIT=0, 0 ERROR/CRITICAL in every upgrade log.
- **Downtime 100 s** (20:58:54 stop → 21:00:34 listening). No test in the stopped window (G19).
- After: server tree hash e653f679f3d1faf5 = repo; `latest_version` 19.0.1.7.1 installed on all five.
- Active scheduled jobs: identical id lists before/after — 50 / 32 / 39 / 82 / 81.
- Assets: signal row + `/web/assets/%` purge + `web.assets.version` bump on all five.
- Users, group memberships (hash), allocations (count + id/state/days hash), leave requests (count +
  id/state hash), policy postings, leave rows from Updates, updates, employees, mail queue:
  **identical before/after on all five**.
- Sites payobook.com, rize, p0clone, sudima 200; one service process; server log since start 0 ERROR.
- **Live p0clone after start (ports 8471/8472): pb_records 134 + pb_updates 244 tests, 0 failed**;
  one ERROR line, the expected "Error processing line" of P5's Y6c (G68).
- No live writes: nothing applied anywhere (the suites are TransactionCase, rolled back). No sign-in
  with a password.

Rollback: scoped `rsync -a --delete pb_updates.prev/ /odoo/odoo-server/addons/pb_updates/`, `-u
pb_updates` on the five, asset signal + purge + version bump, restart. No data to undo.

## R5. Needs an owner decision

1. **rize: HR officers can now set leave balances alone.** rize's route for these sheets is "No
   approval needed", so debalina, thao and wildan — and also the demo login `indo@demo` and the
   platform support login, which hold the HR officer role there — can each set opening balances
   at once, including permanent ones for the 225 people on an absence policy. Keep it, or put a
   second person on rize's records route (that also changes rize's personal-details and pay
   changes from sheets), or take the HR officer role off the two non-staff logins?
2. **payobook.com demo world:** 187 HR-officer logins (demo sign-ups) can now set leave balances for
   the demo people at once. Demo data only; flagging so it is a known choice.
3. **Own balance rule** (added as a safety rail, not asked for): an HR officer cannot set their own
   leave balance from a sheet; a Time Off administrator or another HR officer has to. Keep?
