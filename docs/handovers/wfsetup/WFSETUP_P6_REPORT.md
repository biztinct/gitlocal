# WFSETUP P6 — honest clocks, one undo path, small deploy (report)

Implementation + deploy agent, 24 Nov 2026 (UTC; 25 Nov morning Sydney). Handover `WFSETUP_P6_HANDOVER.md`.
Engineering receipt: real technical names on purpose. No credentials in this file.

**Result: LIVE on sudima + payobook, 109 s of downtime (21:14:18–21:16:07 UTC).** `pb_workforce_setup`
19.0.1.4.1 → **19.0.1.5.0** on exactly those two; absent on payobook_template, p0clone, rize. Commits on `19.1`:
`ae4c71b37` (code), `e093c763e` (deploy scripts = the deployed commit). Nothing switched on, confirmed or
published on any live database. abm untouched.

## 1. What changed

| Fix | What the screen does now |
|---|---|
| 1. Step 6 "Time clocks" | Each PC clock reads **Sending clock-ins** / **Connected, but clock-ins are switched off** / **Not heard from since <time or date>** (plus the existing Waiting for IT / Needs attention / Switched off). "Heard from recently" is pb_clock's own rule: a PC after `max(60, 3 × interval)` min (the connector page's "Contact overdue"), a machine after 180 s (the Time clocks screen's chip) — ledger WS49. The step is green only with ≥ 1 sending clock or the manager's existing confirmation (`pb_wfs_clocks_ok`); only-connected clocks show amber "Clock-ins switched off". Attendance managers get **Switch clock-ins on** on a connected PC whose switch is off, behind an inline confirm panel (Esc / "Not now" closes it, focus returns to the button); it writes `publish_punches` through the connector's own `write` as the caller (no sudo) via the new facade method `clock_switch_on`. Others see "Ask a manager to switch clock-ins on." A silent PC whose switch is also off says so in one extra line. Chips wrap inside the card. |
| 2. Step 7 + finish card | "Clock-ins now turn into paid hours using your rules." only when a clock is heard from; otherwise the finish card shows "No clock is sending clock-ins yet — paid hours will start once one is." with **See step 6**, and the checklist shows the amber (never blocking) line "No clock is sending clock-ins yet. Paid hours start once one is. You can go live without it." `live_check` and `go_live_finish` carry `clocks_sending`. |
| 3. Undo | ONE undo path: every toast Undo (step 3's three bulk actions, step 5's holiday add / remove) is a `{method, args, kind}` that the studio runs with its own services (`onToastUndo`), then reloads the step on screen (`registerReload`) and the studio data (rail, person panel) **before** it shows "Undone…". |

Translations: 20 new msgids (+ 2 field labels the P5c `.pot` had missed), vi_VN + id_ID, `.pot` re-exported (781
msgids), PO gate on the server 806 rows each, 0 empty, 0 vendor word. No new stored field, no data change.

## 2. Decisions I made where the handover did not match the code (please read)

1. **The send switch is NOT what turns clock-ins into paid hours under the step 4 rules** (ledger WS47). The
   rules read a PC's received records directly (`pb.clock.connector.event` state `ready/posted/duplicate`,
   `pb_attendance_policy/models/policy.py:298-302`), and with the switch off the records are kept as `ready`. The
   switch turns them into clock-in rows on the attendance side (and legacy pairing for people not on active
   rules), and switching it on **replays every record already received** (sudima: 71,063). P5b's "0 attendance
   because the switch is off" (WS44) was wrong — the real reason was that no record is newer than 23 Nov (the PCs
   read databases the terminals no longer feed). So I kept the handover's shape (three states, the switch, green
   rule) but made every sentence true:
   - the "switched off" card says the clock-ins are kept and the rules read them once confirmed, and only appear
     in attendance after switching on;
   - the confirm sentence says "…will start arriving in attendance, **including the ones it has already sent**,
     and will be turned into paid hours by the rules in step 4";
   - step 7 / the finish card decide on "a clock is heard from" (switch on or off), not on the switch, and the
     no-clock line says "paid hours will start once one is" instead of "once one is switched on in step 6".
2. "Not heard from" threshold: pb_clock has two health chips; I used the connector page's for PCs and the Time
   clocks screen's for machines (they are the only ones). It is much stricter than the old 24 h: a 15-minute PC
   reads "Not heard from since 14:05" an hour after its last call.
3. Undo (WS46): the plain path (apply → Undo) already redrew the table on a small local company; I could not
   reproduce the exact P5b symptom. The reproducible fault was an Undo pressed after leaving step 3 and coming back
   within 8 s: the old step's `orm` refused ("Component is destroyed") and **nothing was undone** (WS48). Fixed in
   the common path for every undo, as the handover asked.
4. Step 7's amber clock line shows even when the manager confirmed step 6 "without a clock" while nothing sends —
   it is true and never blocks.
5. Commit trailer: `Claude Opus 5.5` (the model that did the work) instead of the handover's `Claude Fable 5.2`.

## 3. Tests

| Run | Result |
|---|---|
| Local DB `wfs6` (copy of `upd_p6_t_tpl` + `-u all`, WS3), `-i/-u pb_workforce_setup,pb_workforce_workspace` + both test tags, final code | **0 failed, 0 errors of 106**: `pb_workforce_setup` 94 (89 before + 5 new `test_p6`), `pb_workforce_workspace` 12 |
| §3.1 three states / green rule (`TestP6Clocks.test_01-03`) | pass (sending / held / silent / slow PC; machine 60 s vs 10 min; officer sees no switch; green with one sending, with confirmation; not green with only connected-off) |
| §3.2 switch (`test_04`) | pass: officer refused (studio gate), Settings admin without clock rights refused (connector's own rule), other company "no longer there", manager writes only that connector, `write_uid` = manager |
| §3.3 finish + checklist variants (`test_05`) | pass: amber not blocking, `clocks_sending` False/True on `live_check` and `go_live_finish`, held-but-heard counts as sending |
| §3.4 static | every msgid has vi + id (product PO reader), placeholders equal, three loading markers, no vendor word |
| `test_golive` 07 / 16 | updated for the new thresholds; `clock_switch_on` added to the officer-refused list |

Browser (local, port 8197, `--max-cron-threads=0`, "Walk Six Co": 60 people, 3 PCs; manager / officer / vi / id
logins): **B1** three states render, chips wrap — pass. **B2** confirm panel; real Esc key closes it; focus back on
"Switch clock-ins on" (after a fix, WS50); Switch on → 0.8 s, chip "Sending clock-ins", rail "2 clocks sending",
database: only that connector, written by the manager — pass. **B3** finish card both variants ("No clock is
sending… See step 6" → opens step 6; and "Clock-ins now turn into paid hours…") — pass. **B4** late rule → Undo
redraws in place; leave step 3, come back, Undo → works (before: "Component is destroyed"); Give a working week →
Undo: rows, head chip and rail back (8 → 10 without a week); holidays "Add them all" → Undo — pass. **B5**
Vietnamese and Indonesian cards, confirm, intro, rail, step 7 amber line — pass. Officer: no buttons, "Ask a
manager…" — pass. Console: clean (one 500 for the website logo image on the local login page: the copied DB has an
empty file folder; not this code). Scratch DB dropped afterwards.

## 4. Deploy (tier NORMAL)

| Time (UTC) | Step |
|---|---|
| 21:09 | Pushed `def1e000a..e093c763e` to `19.1` (fast-forward; `origin/19.1` had not moved). Staging tar from the pushed commit; scripts `docs/handovers/wfsetup/p6/` (trimmed clones of `p5b/`) |
| 21:09–21:11 | Prep: staged = commit; live tree 19.0.1.4.1; previous tree saved; PO gate; job snapshots ×5; dumps sudima 37.7 MB, payobook 84.3 MB |
| 21:12 | Notes re-read (last entries all closed, no HOLD, no lock); START line; lock taken |
| 21:12 | Quiet check: no signed-in activity on rize/payobook/sudima since 20:57 |
| 21:12–21:14 | Fresh dumps right before the stop (sudima 37,715,597 B, payobook 84,318,779 B) |
| 21:14:18 | Service stopped; scoped rsync of `pb_workforce_setup` only; addons = staged |
| 21:14–21:15 | `-u pb_workforce_setup`: sudima exit 0 / 22 s / 0 ERROR; payobook exit 0 / 20 s / 0 ERROR; asset purge + `orm_signaling_assets` + `web.assets.version = wfsetup-p6-20261124T2110Z` on both |
| 21:16:07 | Service up; five sites 200; DONE line; lock removed; NOTE line 21:20 |

Backups `/odoo/backups/wfsetup-p6-20261124T2110Z/`; evidence `/tmp/wfsetup-p6-20261124T2110Z/`.

| Database | pb_workforce_setup | Jobs active (prep → now) |
|---|---|---|
| payobook | 19.0.1.5.0 | 59 → 59 |
| sudima | 19.0.1.5.0 | 91 → 91 |
| payobook_template | not installed | 40 → 40 |
| p0clone | not installed | 48 → 48 |
| rize | not installed | 91 → 91 |

Verification: tree = commit; data right before the stop vs after identical on both; clock send switches unchanged
(sudima 6 × off, payobook has no PC clock); server log after start 0 ERROR (2 cron errors on payobook_template in
the stop second: "connection closed" — the stop, not this code); compiled code has the setup screen and the switch
on both; HTTP 200 × 5.

## 5. Live look

- **payobook.com, QA login** (company Payobook Vietnam JSC): step 6 shows its one clock (a machine) "Waiting for
  IT" — there is no PC there, so the three new states cannot show on payobook. Step 7: clock line amber "No clock is
  sending clock-ins yet…". Step 3: 4,553 people in 2.0 s; ticked 3, Worker → "Apply to 3" (2.1 s) → **Undo → the
  three rows back to "Not set" in 2.0 s, no reload**; database: all three empty again. Console clean.
- **sudima, look-only** (QA login 2501 on with a random password for the walk, off again with another random
  password, file removed): step 6 shows six PCs — five "Not heard from since Mon 23 / Tue 24 Nov" with "Clock-ins
  are also switched off for this clock", one "Connected, but clock-ins are switched off" (heard 7 min before);
  rail "Clock-ins switched off"; bar "Continue, finish 6 clocks later". Step 7: clock line amber "6 clocks still
  need setting up. You can go live without them." (one PC is heard from, so not the "no clock sending" line);
  rules still the blocking item. Nothing pressed. Console clean. Afterwards: 6 × switch off, 0 active rule sets,
  0 published roster rows.

## 6. What the owner should know (plain)

1. On Sudima, switching clock-ins on is **not needed for pay** under the new late and overtime rules, and
   pressing it would push about 71,000 old records into attendance at once. The real problem is that no clock
   record newer than Monday 23 Nov has arrived: five of six office PCs have gone quiet and the sixth reads a file
   the clock machines are no longer copied into.
2. The "switch" decision is still the customer's; the screen now says exactly what it does.

## 7. Left undone / for later

- `pb_workforce_setup` on rize / payobook_template / p0clone: unchanged row in `docs/deploy/PENDING.md`.
- The finish-card bundle probe (`'clocks_sending' in js`) read False because templates are not in the scanned
  JS text; the browser walk is the proof that the finish card works.
- WS43 / WS36 test data assumptions remain (not touched).
