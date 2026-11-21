# CLOCK-1 report — punches become attendance

Delivered 2026-11-05. Live on payobook, payobook_template, p0clone, rize.

## In plain words (for the owner)

- **Time › Time clocks** is a new tab. Upload a punch file there (or from
  Import › "Time-clock punches"): Excel, CSV, the machine's own `attlog.dat`,
  or the attendance program's daily sheet. You see what the file holds first
  — punches, people, days, any number that matches nobody — then press Add.
- Within seconds the punches become work days: first punch in, last punch
  out, night shifts kept as one day, double taps counted once. They show in
  the Week Grid, the person's week and the weekly timesheet like any other
  hours, and cannot be typed over (fix them with a correction).
- A number that matches nobody waits in "Numbers that match nobody". Type a
  name or badge ID and press Enter; everything that number punched is paired
  at once.
- Days that are closed, waiting for approval, have a correction or a
  hand-typed entry are never changed: the punches wait in "Punches on hold"
  with the reason and a "Fix this day" button.
- Separate fix, already live: the Week Grid and the weekly timesheet now put a
  punch on the day the person actually worked in their own time zone. A
  06:30 start in Vietnam used to show on the day before.

## 1. Commits (branch 19.1, pushed)

| Hash | What |
|---|---|
| 2512ca3e2 | Step 1 — local-day fix (grid read/save, drawer, packet, freeze, correction check) |
| f73696c4d | Step 2 — pb_clock ledger, machines, clock number, settings, `device` source, security |
| e66f3042b | Step 3 — pairing engine + 5-minute job |
| 60713c171 | Step 4 — punch upload mode + Import lens mode cards |
| e0636b905 | Step 5 — Time hub lens registry + Time clocks lens |
| 0c5708cad | Step 6 — Vietnamese (pb_clock 221 entries, 65 new in pb_attendance_flow) |
| e5e99b885 | fix — lens template did not compile (found in the browser) |
| f732c21f8 | pause note (owner pause, lifted) |
| (this) | fix — new-punch highlight; report; ledger; pause note removed |

Versions: pb_clock 19.0.1.0.0 (new), pb_hr_workforce 19.0.4.23.0,
pb_timesheet_approval 19.0.1.1.0, pb_time_hub 19.0.1.4.0,
pb_attendance_flow 19.0.1.3.0.

## 2. Tests 1–18

Iterations ran on a throwaway copy of p0clone (`clk1test`, dropped at the
end, ledger G7); the final run was on **p0clone itself** after deploy:
`-u pb_clock --test-tags /pb_clock` → `0 failed, 0 error(s)` (36 tests).
The full pre-deploy run over all five modules: 175 tests, 6 failing —
weekentry test_06, attendance_flow 04/05/07/13, packet s02 — the **same six
fail on unchanged HEAD** (baseline run, data-dependent approval routes).

| # | Case | Test | Result |
|---|---|---|---|
| 1 | same 10 punches twice → 10 rows; create returns existing row | test_01 (+01b zone, 01c unique clock number, 01d device source) | PASS |
| 2 | 06:30 local 4 Nov → local day 4 Nov in attendance, grid (Wednesday cell, read-only), packet, freeze pairs | test_02 + test_local_day 01–09 | PASS (note: 4 Nov is a Wednesday, the handover said Tuesday) |
| 3 | night shift 26/10 19:18 + 27/10 07:36 = one day 12.3 h; 27/10 19:15 new day | test_03 | PASS |
| 4 | 07:30 → 04:00 next day = 20.5 h | test_04 | PASS |
| 5 | double tap: one paired, two ignored | test_05 | PASS |
| 6 | middle punches: in 07:11 out 20:36, two `middle`, 13.42 h | test_06 | PASS |
| 7 | single punch → open day, `missing_checkout` in the feed | test_07 | PASS |
| 8 | unknown 999 → badge 1; assign → paired, badge 0 | test_08 | PASS |
| 9 | locked day → attendance unchanged, punch held, note names the day | test_09 (pb_close present) | PASS |
| 10 | grid row 08–17 + punches 07:11/20:36 → held "manual entry exists", grid row untouched | test_10 | PASS |
| 11 | year 2000 / future → ignored | test_11 | PASS |
| 12 | run twice + repair → same ids/times/write_date, zero writes | test_12 (+12b late punch updates in place) | PASS |
| 13 | daily sheet with legacy headers + title rows → 5 punches, mitaco_export, 3 days; re-import adds 0 | test_13 | PASS |
| 14 | attlog.dat 4 lines → 4 punches, `<serial>_attlog.dat` names the machine | test_14 | PASS |
| 15 | 20 001 rows → 20 000, truncated; days mode keeps 2 000 | test_15 (+15b table with TST-A/TST-B, nothing paired inline) | PASS |
| 16 | officer cannot write a punch; manager cannot change the number; plain user cannot read; assign by plain user → {error} | test_16 | PASS |
| 17 | brand name in no pb_clock file | test_17 | PASS |
| 18 | built-in lenses unchanged (31 pb_time_hub tests green), registry adds `clocks` after import | test_18 | PASS |

Also: lens facade cases (empty → live, badge count, suggestion by leading
zeros, auto-match, refuse a second number, re-pair/settings/machine rights,
people search with leavers). Learn truth gate: no Time findings (its 7
failures are on pay-run and employee screens, pre-existing).

## 3. Browser validation (rize.payobook.com, open session, Chrome MCP)

Shots in `docs/handovers/clock/shots/`:
`00_compile_error_before_fix` (the bug, fixed in e5e99b885),
`01_import_mode_cards`, `02_lens_empty_state`, `03_import_punch_mode`,
`04_check_card` (20 punches · 4 people · 2 days, TST-A/TST-B flagged),
`05_done_toast` ("20 punches added · 2 numbers not matched · pairing runs in
the background"), `06_lens_unknown_numbers`, `07_badge_this_week` (tab badge
2), `08_auto_match_sentence` (plain "nobody yet" sentence),
`09_keyboard_assign` (↓, Enter, typed a badge ID), `10_after_assign` (badge
1), `11_grid_cell_locked` (9.1 h Mon/Tue, regular hours locked, overtime
editable), `12_person_drawer` (same local days), `13_settings_saved`.

Server side: the job paired 16 punches into 8 days within ~20 s of the
upload (the trigger works). Console: the only errors were the compile error
before the fix; none after. All test data removed afterwards through the
model layer (20 punches, 9 days, the upload machine, the test clock number;
setting back to 2) — logged in `/opt/deploy-notes.md`.

**Not done:** the payobook.com pass (I did not open a session there) and
"Fix this day" end-to-end (no held punch arose in the walk-through; covered by
tests 9/10 server-side only).

## 4. Deploy

| Commit | Module → version | Window (UTC) | EXIT per DB | Jobs before → after | Evidence |
|---|---|---|---|---|---|
| 0c5708cad | +pb_clock 1.0.0, pb_hr_workforce 4.23.0, pb_timesheet_approval 1.1.0, pb_time_hub 1.4.0, pb_attendance_flow 1.3.0 | 02:14:46–02:20:03 | p0clone 0 · template 0 · rize 0 · payobook 0 (errors 0) | 32/29/75/43 → 33/29/76/44 | `/tmp/clock1-run-20261105021444`, backups `/odoo/backups/clock1-run-20261105021444` |
| e5e99b885 | pb_clock (looks) | 02:22 | OK | unchanged | `/tmp/clock1b-run-…` |
| (fix 2) | pb_clock (looks) | 04:00 | OK | unchanged | `/tmp/clock1c-run-…` |

Pairing job id: payobook 148, p0clone 84, rize 84 (switched ON by hand —
the deploy script restores the old job set, G3); payobook_template 84 OFF and
appended to `pb_tenants.template_active_crons`. Tree hashes identical
(script check), `latest_version` matches every manifest on all four. PO gate
OK (pb_clock 258 rows, 0 empty), SCSS gate OK on the box. `ListAgents` is not
available in this session, so no heads-up could be sent; the notes file had
no open START from another session.

## 5. Design bar — self-score 8/10

- **Hero:** the live sentence + pulse dot; the import check card with
  sparkline and unknown chips. Good.
- **States:** empty, loading, error, quiet, live, zero sections greyed,
  truncation banner, nothing-new import. Huge: recent list pages by 200, the
  unknown table caps at 300 rows (no paging yet).
- **Plain language:** every label and toast in plain words, Vietnamese for
  all. Gap: the Week Grid lock sentence for a time-clock day still says
  "Device/kiosk punch — edit on the attendance form" (older string in
  pb_hr_workforce; should point at a correction).
- **Motion:** pulse, rise on the check card, slide-in for arriving punches
  (fixed so only real arrivals slide in).
- **Keyboard + bulk:** ↑/↓/Enter/Esc in the unknown table and typeahead;
  "Assign all suggested", "Match by employee codes", "Re-pair this week".
- Gaps: typeahead avatars render blank on rize; the machine card truncates
  "Files you upload"; the done card repeats the count in title and sentence;
  hero says "Files you upload" as the place of the last punch.

## 6. Deviations

- `pb_hr_workforce/models/hr_attendance.py` already existed; helpers added.
- Converted three more UTC-day sites than listed: the Time hub drawer, the
  correction coherence check, and the packet's unapproved-weeks finder.
- `work_day` uses the person's zone (rule 11), not the machine's; same for
  Sudima.
- Icons `scan` / `pause` / `userX` / `list` / `settings`: the shared registry
  has no fingerprint, radio or pause-circle, and adding them would mean
  upgrading pb_import_kit (wide cascade).
- "Assign now" is on the import's Done card (before the import the numbers
  are not in the ledger yet).
- An unknown machine name in a file becomes a machine (up to 20 per file).
- Tests iterated on a copy of p0clone; final run on p0clone.
- Owner pause 02:25–03:55 UTC; resumed from the pause commit.

## 7. Gotchas

Appended to `CLOCK_LEDGER.md` §3: G2–G8.

## 8. Lessons / tours to update in CLOCK-3

- `pb_time_hub/learn_manifest.py` screen `wftime` — add a Time clocks column
  (and mention the Import mode cards).
- `pb_learn/static/content/learn_content.json`: `sc_wftime`, `wftime`,
  `approveot`, `L21`, `wfclose` (and the `time` / `leave` tutorial nodes),
  anchor `wf-time`.
- `docs/tutorial_poc/author/data.js` scenes on `wftime`.

## 9. Open questions for CLOCK-2

1. **attlog column order.** The handover fixes number, time, status, verify,
   work code; some ZK firmwares put a machine number third. The receiver
   should parse by position per firmware and keep `direction_raw`.
2. Machine time zone changes do not move punches already in the ledger
   (append-only). If a machine was set up in the wrong zone, the fix is a
   re-import, not an edit — the ADMS handshake time sync matters.
3. One open day per person is a platform limit: a second forgotten
   check-out holds the later single-punch day ("an earlier day has no
   check-out yet"). CLOCK-3 alerts should surface it.
4. Dedup key for live push = serial|PIN|time; an upload of the same punch
   has key 'upload'|…, so both land and the double-tap rule folds them. Fine,
   but the lens will show the second as "Double tap".
