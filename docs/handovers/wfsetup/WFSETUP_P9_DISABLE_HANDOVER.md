# WFSETUP P9 — a reversible "Disable" / "Enable" for a clock connection (pb_clock + studio step 6)

Owner request 2026-11-25 (connector screen, Sudima "Group B · supplied MDB validation"): "I want you to provide that
switch called disable on the screen." Today the only way to stop a PC is "Revoke installation access", which wipes the
pairing (re-pair needed). The owner wants an everyday on/off. Its records are real production punches; it stays NOT
sent to attendance until the owner ticks "Send accepted records to attendance" themselves — do not change that tick.

## Verified facts (do not re-derive)
- `pb_clock` 19.0.1.4.3, installed on all five databases. Last commits on it: 306bf23ac, 50e01ff41, a108a6dcf.
- `pb_clock/models/clock_connector.py:44` `state` selection new / connected / revoked, readonly, tracked.
  `action_revoke` :111-118 clears token/pairing/invitation hashes and posts "Installation access revoked. Stored
  records remain available." `_manager()` = manager check; `_setup_lock()` row lock.
- `pb_clock/controllers/connector.py:52-53`: every PC call is refused with 401 "Installation access revoked" unless
  `state == 'connected'` and the token matches.
- Form header `pb_clock/views/clock_connector.xml:8` (buttons: Guided setup / invite IT, Replace / manually pair PC,
  Download Windows package, Received records, Revoke installation access; statusbar `state`).
- Windows program: `tools/attendance_connector/connector.py` (scheduled task "Payobook Attendance Connector", every
  `interval_minutes`). Find how it keeps its read position (it reads the Mitaco MDB) and what it does on a refused call.
- Studio step 6: `pb_workforce_setup/models/clocks.py` (states Sending / Connected but switched off / Not heard from,
  ledger WS49) and its OWL step; `pb_clock` health chips in `pb_clock/static/setup/setup.js:53`, `clock_lens.js:435`;
  the clock watch jobs `cron_watch_clocks` / `cron_recheck_clocks` (they may raise "silent" alerts).

## Behaviour (decided)
1. New state value **`disabled` — "Disabled"** in the selection (statusbar shows it between Connected and Access
   revoked). The pairing (token) is KEPT.
2. Header: **"Disable"** (visible when connected; managers only) and **"Enable"** (visible when disabled; managers
   only). Inline confirm text for Disable: "This PC will stop sending clock-ins until you enable it again. Nothing
   already received is removed, and it does not need to be paired again." Enable needs no confirm. Chatter line on
   each. Enable returns to `connected`.
3. PC calls while disabled are refused with a distinct answer (HTTP 423, message "This connection is disabled in
   Payobook. Ask your Payobook administrator to enable it.") — NOT the revoke text. Requirement: after Enable, the PC
   catches up everything punched while disabled, with no gap and no duplicates. Verify in `connector.py` that a refused
   upload does not advance the PC's read position. If it does advance, STOP and report before building — do not
   change the Windows program in this phase.
4. While disabled: the clock watch jobs do not alert on it; the connection-health tab and studio step 6 show
   **"Disabled"** (grey, Lucide `power-off`) with "Enable" for managers. A disabled connection does not count as
   "sending" or as "needs attention" in step 6/7 checks.
5. "Send accepted records to attendance" is untouched by Disable/Enable. Processing of records ALREADY received is
   unaffected (stays governed by that tick).
6. Settings/rights: same group as Revoke (`hr_attendance.group_hr_attendance_manager`).
7. Do not disable any real connection on any live database. Do not touch Sudima's ticks.

## Rules (binding)
White-label: the word "Odoo" never in a user-visible string (labels, help, errors, msgstr). Design bar verbatim:
"extreme WOW, intuitive, out-of-this-world experience, best in class"; Lucide via `ic()`, no emoji. vi_VN + id_ID
for every new sentence in both modules (three loading rules; parse gate; WS40 import spelling). Commit messages end
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. No credentials, no client folders in commits.

## Tests
1. disable/enable by a manager; refused for an officer; token kept; chatter lines.
2. Controller: disabled → 423 with the new message; revoked → still 401 revoke text; connected → accepted.
3. Catch-up proof: simulate (or run `connector.py` against a local server with a small fake MDB/CSV fixture if the
   test kit allows) an upload refused while disabled, then Enable → the same rows arrive, no duplicates.
4. Watch jobs skip disabled; step 6 payload shows `disabled`; step 6/7 checks treat it as neither sending nor failing.
5. Full `pb_clock` and `pb_workforce_setup` suites green (note pre-existing failures: pb_clock HTTPS tests locally).
Browser: the Disable button, its confirm, statusbar, Enable; step 6 "Disabled"; vi + id; console clean.

## Deploy (NORMAL tier; adds one selection value, no new columns unless you need one)
Sequence after the peer agents: WFSETUP P7 (installing pb_workforce_setup on rize/payobook_template/p0clone) must have
its DONE line in `/opt/deploy-notes.md` first; WFSETUP P8 (Sudima clock-ins) may be draining records on sudima — do
not stop the service while P8 has an open START; wait. Then the usual contract: backups ×5, staging clean, per-module
scoped rsync of `pb_clock` and `pb_workforce_setup`, `-u pb_clock,pb_workforce_setup` on all five (pb_workforce_setup
where installed), asset purge + `web.assets.version`, hashes, versions, crons unchanged, HTTP 200 ×5, START/DONE.
Never abm. Live look: payobook (QA login) Disable then Enable a demo connection if one exists (else look only);
sudima look only — the six connections show their real state, nothing disabled.
Report `WFSETUP_P9_REPORT.md` committed + pushed to 19.1 (rebase on peers' pushes).
