# WFSETUP P9 — report: reversible "Disable" / "Enable" for a clock connection

Handover: `WFSETUP_P9_DISABLE_HANDOVER.md`. Built in worktree `gitlocal-worktrees/wfsetup-p9`, pushed to `19.1`:
`7c8321864` (code), `9f553ebb2` (deploy scripts + ledger WS60-WS62; its subject line still says "WS51-WS54" — the
numbers were taken by P7/P8 in the meantime and renumbered while rebasing), `768c6786c` (retry wrapper = the
deployed commit).

## 1. What changed

| Where | What a person sees |
|---|---|
| Clock connection screen (pb_clock 19.0.1.5.0) | **Disable** button (connected PCs, attendance managers only) with the inline confirm "This PC will stop sending clock-ins until you enable it again. Nothing already received is removed, and it does not need to be paired again." Status becomes **Disabled** (between Connected and Access revoked). **Enable** button (no confirm) returns it to Connected. One chatter line each. The Connection health tab shows a grey note with the power icon: "Disabled — This PC is not sending clock-ins. It stays paired, nothing already received is removed, and everything punched meanwhile is sent once you enable it." + Enable. List: disabled / revoked rows greyed, state as a badge. |
| The PC (no change to the Windows program) | While disabled every upload is answered **HTTP 423** "This connection is disabled in Payobook. Ask your Payobook administrator to enable it." (not the 401 revoke answer). The pairing token is kept. |
| Guided setup page (IT) | Pill "Disabled" and a matching sentence; no new pairing code is offered (a code would have silently un-paired the PC). English only, like the rest of that page. |
| Workforce setup step 6 (pb_workforce_setup 19.0.1.6.0) | A disabled PC card: grey chip **Disabled** (power icon), "Disabled on purpose. The PC stays paired and keeps new clock-ins waiting. Once enabled, it sends everything punched meanwhile.", **Enable** for managers (others: "Ask a manager to enable it."). No setup-link button on it. |
| Step 6 / step 7 totals | A disabled clock is neither "sending", "left to finish later" nor "waiting for IT". Confirmed step with only disabled clocks reads "1 clock disabled" / "N clocks disabled"; step 7 shows its amber "No clock is sending clock-ins yet" line. |

Untouched by Disable / Enable: the "Send accepted records to attendance" tick and the processing of records already
received. Rights: the same group as Revoke (`hr_attendance.group_hr_attendance_manager`); the state field stays
read-only (`write` refuses it for everyone but the connector's own methods).

Watch jobs: `cron_watch_clocks` only ever looks at machines that call in (`pb.clock.device` kind `terminal`), never at
a PC connection or its collection group, so a disabled PC raises nothing by construction; pinned by
`test_05_watch_job_quiet_for_a_disabled_pc`.

Translations: vi_VN + id_ID for every new sentence in both modules (pb_clock gets its first `id_ID.po`, holding only
the new P9 sentences; the rest of the connection screen was and stays English in vi/id — pre-existing). Every msgid
checked against `odoo-bin i18n export` (type, name and xml id identical); one fix from that check: the banner text
was split into block elements so it exports as two plain terms instead of one HTML term.

## 2. Step 3 check (the catch-up requirement) — PASSED, so built

`tools/attendance_connector/connector.py` keeps **no read position**: each run re-reads the whole MDB, puts unseen rows
into its local SQLite queue (de-duplicated by row hash) and marks rows acknowledged only after a 200 whose
`acknowledged` equals the batch size. Any refused call (401 / 423 / 5xx) raises before `acknowledge`, so the rows stay
queued. The server de-duplicates again on `(connector, row_hash)`.

Proof with the real program (`pb_clock/tests/test_disable.py::TestDisableHttp.test_02`): its own `sync()` and `post()`
run against the test server (only the MDB read and the HTTPS opener are stood in for). Connected: 2 rows arrive.
Disabled: 2 more rows punched; the upload fails with "HTTP 423", the PC queue holds exactly 2, the server took in
nothing; a second refused run loses nothing. Enabled: the next sync sends 2, queue 0, the server holds exactly the 4
MDB rows (hashes compared), the same MDB again sends 0, and a full re-send after a queue replay is all duplicates.
Result: **no gap, no duplicates.**

## 3. Tests

Local copy of `upd_p6_t_tpl` (+ `-u all`), `--proxy-mode` (WS62):
- Full `pb_clock` + `pb_workforce_setup` suites: **207 tests**; 203 passed first time; 2 were my own test mistakes
  (a test transport stand-in, an expected sort order) — fixed and the P9 set re-run **10 / 10 green**; the other 2
  (`TestAlerts.test_01_silent`, `test_02_no_punches`) fail identically on unchanged `origin/19.1` code (baseline run on a
  separate copy) — date-dependent, not P9.
- New: `pb_clock/tests/test_disable.py` (7: manager disable/enable + token kept + chatter, tick survives, officer
  refused, only from the right state + revoke still works, watch job quiet, 423/401/200, catch-up proof) and
  `pb_workforce_setup/tests/test_p9.py` (3: disabled row + counts + order, Enable from step 6 refused for officer and for
  an administrator without clock rights, step 6/7 texts).
- Static gates (`test_static`: no vendor word, every icon exists, no emoji) green.

Local browser walk (Chrome, attendance manager): Disable button -> confirm text -> Ok -> status Disabled, header shows
Enable, Connection health note; step 6 grey Disabled card -> Enable -> "Sending clock-ins" + toast, focus stays on the
card. Vietnamese and Indonesian: buttons, confirm, status, note, chatter line, step 6 card and button title all
translated. Console: 0 errors, 0 warnings.

## 4. Deploy (NORMAL tier) — LIVE x5

- Waited for P7's DONE (23:10 UTC) and checked P8 had no open START (P8 only wrote a rehearsal NO-GO note).
- Deployed commit `768c6786c` (pushed `19.1`); scripts `p9/` (clones of the P6 ones + `p9_tries.sh` in a
  `systemd-run` unit). START 23:41 UTC; tries 1-3 waited for 15 quiet minutes (someone was working until 23:38);
  try 4 at 23:56: backups x5 right before the stop (`/odoo/backups/wfsetup-p9-20261124T2339Z/`), stop, per-module
  scoped `rsync --delete` with `--exclude=releases/PayobookAttendanceConnector.zip`, `-u pb_clock,pb_workforce_setup`
  one database at a time (payobook_template 23 s, p0clone 18 s, rize 21 s, payobook 23 s, sudima 19 s, 0 ERROR each),
  asset purge + `web.assets.version` x5, start. **Downtime 211 s.** DONE 00:02 UTC.
- Verification (`p9_verify.sh`): both trees = commit; the server-built Windows package zip unchanged (sha); versions
  `pb_clock 19.0.1.5.0` and `pb_workforce_setup 19.0.1.6.0` installed on payobook, payobook_template, p0clone, rize,
  sudima; jobs = prep snapshot x5 (59 / 40 / 49 / 92 / 91 active; on payobook_template the upgrade re-activated the
  four clock jobs 84, 85, 86, 91, switched straight back off by the script); data right before the stop vs after
  identical x5; every clock connection's state, attendance tick and pairing unchanged x5 (sudima: 1, 4-8 connected,
  tick off); compiled code carries P9 x5; 0 ERROR in the upgrade logs and the server log after the restart (log
  rotated at 00:00); sites 200 x5. A Codex deploy (workspace settings) followed at 00:04 — re-checked afterwards: P9
  trees and versions still intact x5, job counts unchanged.
- Live looks: **sudima** (look only; QA login 2501 switched on with a random password and off + rotated again right
  after): step 6 shows the six connections in their real state (5 "Not heard from since 23/24 Nov", 1 "Connected,
  but clock-ins are switched off"; none Disabled); the "Group B · supplied MDB validation" screen shows the new
  **Disable** button next to Revoke (not pressed); console clean. **payobook** (QA login): there is no PC connection
  on the demo database (only the DEMO machine that calls in by itself, which has no Disable), so look only: step 6
  renders, the status list carries Disabled, console clean. Nothing was disabled and no "Send accepted records to
  attendance" tick was changed on any database.

## 5. Unsure / chosen
- The header showed two solid primary buttons when disabled (Guided setup + Enable): Enable made a normal button
  (one primary per bar); the Connection health note carries its own Enable.
- vi "Disabled" = "Tạm ngưng" (paused) — "Đã tắt" was already taken by step 6's "Switched off" (revoked); id
  "Dinonaktifkan" vs "Dimatikan" for the same reason.
- After Enable a PC reads "Not heard from since …" until its next scheduled sync (up to its interval) — truthful, left
  as is.
- The full suite was not re-run after the two test-only fixes and the banner markup split; the P9 tests were re-run
  (10/10) and the final view was upgraded cleanly on the local copy and on all five live databases.

## 6. Left undone / for the owner
- Nothing from the handover. The Disable / Enable buttons were proven end to end locally (manager, en / vi / id);
  live they were only looked at, by design.
- The connection screen's existing text (tabs, other buttons, the guided setup page) is still English in vi / id —
  pre-existing, outside P9.

