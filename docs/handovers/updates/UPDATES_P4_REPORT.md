# UPDATES — Phase 4 report (leave opening balances sheet, attendance tile)

Implemented, tested, deployed and checked on 2026-11-12 by the Opus implementation agent,
against `UPDATES_P4_HANDOVER.md` and `UPDATES_LEDGER.md`. Owner decisions D16–D19 are in the
ledger under their own numbers (they were free).

R0 below was written BEFORE the deploy, as the handover asks.

## R0. Rollback note (written before deploying)

- **Files:** the previous `pb_updates` tree (19.0.1.5.0, git `a45b6e42f`) is kept on the server in
  `/odoo/backups/updates-p4-<TS>/pb_updates.prev`. Restore = scoped
  `rsync -a --delete pb_updates.prev/ /odoo/odoo-server/addons/pb_updates/`, `-u pb_updates` on the
  five databases, asset signal + purge + version bump, restart.
- **Data:** five dumps `/odoo/backups/updates-p4-<TS>/<db>.pre-updates-p4.dump`, taken before the
  service stops.
- **What a files-only rollback leaves behind:** one new table `pb_updates_leave_line`, two new
  columns (`pb_updates_batch.leave_date`; `hr_leave_allocation.pb_updates_leave_line_id`), one
  record rule, selection value `leave` on the batch/layout kind. An old registry ignores them.
- **Balances already set from a sheet stay set** after a rollback: they are ordinary approved
  time-off allocations (and, for people on an absence policy, policy postings). Only the Updates
  screens for them go away. A leave update still **waiting for approval** must be withdrawn
  (Updates home → Withdraw) before a files-only rollback: the old code would try to write its
  empty plan as a records change on approval (nothing would be written).
- **No new scheduled job.** Nothing to switch off. `pb_timeoff` is not touched by this deploy.

---

## R1. What shipped

| Module | Version | Where | What |
|---|---|---|---|
| `pb_updates` | 19.0.1.5.0 → **19.0.1.6.0** | upgraded on all five | the third kind of sheet "Leave opening balances", the store `pb.updates.leave.line`, its approval adapter, the attendance tile; new dependency `hr_holidays` (installed everywhere) |

Nothing else changed. `pb_timeoff` is reached by soft checks only (`'pb.leave.policy.edition' in env`,
`'pb_leave_policy_id' in fields`) and only its public `post_opening_balance` is called; it is
installed on all five databases (19.0.1.10.0) but is not a dependency. No file in `pb_timeoff`,
`pb_lifecycle`, `pb_hiring`, `pb_me_expense` or `docs/handovers/workflow2` was edited, staged or
deployed.

Commits: `c729509f6` (the feature) · the docs commit carrying this report, the handover and the
ledger.

## R2. Tests L1–L14

New file `pb_updates/tests/test_updates_p4.py` — 23 cases in two classes (`TestUpdatesP4` with
"No approval needed", `TestUpdatesP4Route` with a real HR-lead route), a company of its own in Ho
Chi Minh City, today frozen at 12 Nov 2026, balances as at 1 Nov 2026, a real absence policy
(pb_timeoff edition, rules, published, three people assigned and confirmed full time, one not
confirmed), seven leave types (two policy annual types, whole-day / half-day / hour types,
another company's type, a Singapore type). Everything is sent by a Time Off administrator through
the screens' own server calls (`review` → `apply`) and written by the real policy layer and the
real allocation flow.

| # | Case | Result |
|---|---|---|
| L1 | `test_L1_policy_layer_three_people_two_types` — 3 policy people × 2 annual types, with carried and taken: 6 postings of kind "opening" through `post_opening_balance` (days / carried / taken / cutover / review reference "Updates: “DEMO P4 balances” (RD…)"), each with an approved allocation 1 Nov → 31 Dec marked with its row; the Time Off screen's own balance (`pb.timeoff._balances`) shows the days. `L1b` — not-confirmed full time, a non-annual type for a policy person, carried above the policy's cap (8), carried for a person on no policy (greyed "not used"), a date before the policy starts: each refused with its sentence | PASS |
| L2 | `test_L2_no_policy_one_validated_allocation` — whole days and half days: one approved allocation per cell, from 1 Nov 2026, no end date, `pb_updates_leave_line_id` set, note "Opening balance as at 1 Nov 2026, set from Updates…"; no policy posting; Time Off screen shows the days. The "Time Off officer approves" type is approved by the flow (`action_approve`) | PASS |
| L3 | `test_L3_never_a_second_opening_balance` — again for a set balance: "…already has an opening balance of 12 days for P4 Plain days. Undo that update first."; an allocation already covering the date: "…already has P4 Plain days days from 1 Jan 2026; an opening balance cannot be added on top."; a policy balance: "…set through the absence policy on 1 Nov 2026. It cannot be replaced."; sent past the screen straight to `apply`: refused by the server too; allocation count unchanged | PASS |
| L4 | `test_L4_same_value_is_same_not_sent` — exactly the balance already set: `same`, not in the changes | PASS |
| L5 | `test_L5_units_and_limits` — 12.5 on a whole-day type refused ("…whole number of days, like 12."); 12.5 on half days accepted, 12.25 refused; 7.5 hours accepted (allocation = 7.5 / hours per day, shows 7.5 hours); 2,920 hours (365 × 8) accepted, 2,921 and 366 days refused ("more than a year of leave"); −2 refused; 0 refused ("A balance of 0 sets nothing"); "abc" refused; 7.125 hours refused (two decimals) | PASS |
| L6 | `test_L6_type_not_offered` — another company's type and a Singapore type are not even places a column can go; sent past the screen: refused ("…is not offered in P4 Leave Co, where … works." / "…is for employees in another country.") | PASS |
| L7 | `TestUpdatesP4Route`: `test_L7_approve` (waiting with "DEMO P4 HR Lead", nothing written before approval, the approval drawer titled "Leave opening balances", approved → all rows set, the allocation created by the PROPOSER), `test_L7_send_back_turn_down_cancel` (rows returned / rejected / cancelled with the request; allocation count unchanged), `test_L7_outlook_names_the_approver`; "No approval needed" = every other case | PASS |
| L8 | `test_L8_changed_between_review_and_approval` — an allocation given on the Time Off screen while the update waits: on approval that row is "Could not be set" with "…cannot be added on top", the other rows are set; Past updates says "Set, 1 could not be set" and names the person, leave type and reason | PASS |
| L9 | `test_L9_undo` — untouched balances taken off (allocation refused, Time Off balance back to 0); a balance with a day asked for against it stays ("DEMO P4 Plain B has already taken or asked for 1 day of P4 Plain days against this balance, so it stays."), the rest proceeds; a policy-layer update: no Undo button, `undo` answers "…permanent and stay"; after an undo the same balance can be set again; the Records screen's Undo of that change applies the same rules | PASS |
| L10 | `test_L10_leave_rows_untouched` (and inside L9) — leave requests (ids and states), accrual plans, accrual allocations, annual/carry postings and January-rollover rows: identical before and after a send and an undo | PASS |
| L11 | `test_L11_drafts_history_readme_layouts` — a leave draft saved, listed ("Leave balances as at 1 Nov 2026"), opened with its date, never a past update; applying it turns the draft into the update; Past updates row (kind, state, counts, date, Undo); the remembered layout is kind "leave" with a `leave:` fingerprint and is never offered to a lasting sheet; a second draft discarded. `L11b` — the downloaded sheet: headings "· days available" / "· carried from last year" / "· already taken this year", the Read me (blank = leave alone, once per person and leave type, what carried/taken mean, permanent for policy people), a set balance pre-filled; read back as our sheet (`from_sheet`, the date from the hidden sheet) and sent straight back: 0 changes, `same` | PASS |
| L12 | `test_L12_attendance_tile` — attendance officer: shown, opens `pb_mission.action_pb_workforce` with Time › Import; no right: hidden; module absent (patched): hidden. `L12b` — an HR officer can check a sheet but not send it ("…needs the Time Off administrator role"). `L12c` — a future date, a date more than a year back, no date: refused | PASS |
| L13 | Existing kinds: locally, isolated tree (G13: HEAD snapshot + this module), `-u pb_records,pb_updates,pb_import_advanced`, on a copy of the live template's shape: **pb_records 134 + pb_updates 203 tests, 0 failed** (twice). Live `p0clone` after start: R5. Speed: R3 | PASS |
| L14 | `.po`: built from `odoo-bin i18n export -l pot` (G2/G6); 207 new entries appended (only appended — the file's existing entries are byte-identical), `PoFileReader` reads 1,108 rows, 960 reach a screen, placeholders identical in every new msgstr, 0 "Odoo" in any msgstr; `test_L14_no_vendor_name_in_new_strings` scans the new files; the sheet's file name asserted. Four model names of other modules that the export lists (as in P3a/P3b) are left untranslated | PASS |

## R3. Timings

Fresh read-only copy of live payobook (4,575 people), local, uid 2, cold / warm:

| Step | Pre-phase code (HEAD 1.5.0) | This phase | Target |
|---|---|---|---|
| Lasting sheet, 73 columns | 16.2 s / 11.9 s | 18.9 s / 12.0 s | — |
| Read the columns | 5.2 s / 4.6 s | 5.5 s / 4.8 s | — |
| **Review 4,575 × 73** | 12.4 s / 13.1 s | **14.1 s / 13.3 s** | ≤ 25 s ✔ |
| Answer | 0 changes, 60,075 same, 1,499 unmatched | identical | — |
| Leave sheet, whole roster, 7 leave types | — | 2.4 s (live payobook 3.8 s) | — |
| Leave read columns / review, whole roster | — | 0.4 s / 3.0 s (live 4.2 s) | — |
| Updates home (whole) | — | 1.5 s | — |

## R4. Browser walk (local copy of live payobook) and screenshots

My own local server on a fresh copy of live payobook (port 8795, jobs and mail off), company
Payobook Vietnam JSC (G22), console read at every step. Screenshots in `outputs/updates-p4/` (not
committed). Local-only set-up said here: a published absence policy "Walk policy VN" for company 5
with "Demo Annual Leave" bound as its annual type and three people on it; six people given codes
WALKP1–3 / WALKN1–3; a records route with an HR-lead step (the `payobook` login) so a second person
approves; local passwords for `qa.test@payobook.com` (proposer) and `payobook` (approver) — on the
local copy only.

1. `01-home-leave-tile` — Updates home: fourth tile "Leave opening balances"; the hero says so.
2. `02-start-leave-kind` — Start: three kinds (leave chosen), the quiet "Attendance and timesheets"
   tile, "Balances as at", the leave types offered to these people (in use first: "Demo Annual
   Leave · Whole days · 7 balances today · Absence policy"), the absence-policy note.
3. `03-match-leave-columns` — "Goes to" grouped Days available / Carried from last year / Already
   taken this year; "Leave balance" / "Kept with the balance" kinds; the date note. (Continued from
   a draft: "Leave balances as at 1 Nov 2026 · Stopped at: Match columns".)
4. `04-review-grid-refusals` — "This sheet sets 7 opening balances for 6 people, as at 1 Nov 2026.
   4 cells need your attention."; the strip "6 people · 7 balances · 54 days in total · 3 people on
   an absence policy"; per-column totals; refusals: carried 9 above the cap of 8, Paid Time Off for
   a policy person, 12.5 on a whole-day type, −2.
5. `05-fix-whole-days`, `06-fixed-totals` — the fix row's sentence, 12 typed, totals update.
6. `07-apply-card-undo-line` — "Leave opening balances as at 1 Nov 2026 · 8 balances for 6 people",
   66 days in total, 3 through the absence policy, "Go to Payobook for approval", and BEFORE
   applying "What undo can do. 5 balances can be undone later… 3 balances for people on an absence
   policy are permanent once set."; button "Send 8 balances for approval".
7. `08-done-sent-for-approval`, `09-home-waiting-for-approval` — "8 balances for 6 people are
   waiting with Payobook. Nothing is set until they approve."; Past updates row with Withdraw.
8. `10-second-person-approval-drawer` — as the approver, Approvals: the request "Leave opening
   balances as at … · 8 balances" with every person, leave type and balance ("14 days · 0 carried,
   3 taken"); Approve.
9. `11-timeoff-screen-shows-balance` — the Time Off screen: Bùi Mỹ Chi Paid Time Off 12/12, Extra
   Time Off 2.5/2.5. Server check: 8 rows set, 3 through the policy (postings 1–3, 1 Nov → 31 Dec),
   5 allocations (from 1 Nov, no end), every allocation created by the proposer, 0 mails, 0
   messages, approval to-dos closed.
10. `12-undo-dialog`, `13-undo-result-partly` — after a two-day request against one balance: "4
    balances were taken off. 1 stays: Bùi Kim Anh has already taken or asked for 2 days of Paid Time
    Off against this balance, so it stays. 3 balances set through the absence policy are permanent
    and stay."; row "Partly undone".
11. `14-start-lasting-unchanged-attendance-tile`, `15-attendance-tile-opens-import` — lasting-change
    Start unchanged; the tile opens Workforce › Time › Import ("Attendance days").
12. `16-live-payobook-leave-start` — live payobook.com, look only, an existing session: the leave
    Start screen; console clean.

Found and fixed on the walk: a template loop variable named `lt` blanked the whole screen (G60);
"Lasting changes" stayed highlighted next to the leave kind; the send button counted carried/taken
as balances ("Send 11" → "Send 8"); "Goes to" offered all 31 stock leave types (now only those for
the countries the people work in, G61); dates read "11/01/2026" in some sentences (now "1 Nov
2026" everywhere).

## R5. Deploy evidence (five databases)

Unit `updates-p4-20261112T111502Z` under `flock /tmp/payobook-studio-deploy.lock` — it waited for
UPDATES P6 and WORKFLOW-2 P5c (both deploying at the same time) and got the lock at 11:21 UTC.
START 11:21 / DONE 11:40 UTC in `/opt/deploy-notes.md`. Evidence `/tmp/updates-p4-20261112T111502Z/`.

- Before: the server's `pb_updates` tree = pre-phase commit `a45b6e42f` (2b8bbb6b8a3671b4); staged
  tree = repo `c729509f6` (f6b79563672fdc1d). Only `pb_updates` copied; no standard addon, no other
  module; `pb_timeoff` untouched.
- **Backups (tier 3), before the stop**: `/odoo/backups/updates-p4-20261112T111502Z/` — payobook
  79,101,379 B, payobook_template 27,843,489, p0clone 28,186,280, rize 41,544,710, sudima
  27,786,066 (`*.pre-updates-p4.dump`), plus `pb_updates.prev`. Nightly backups untouched.
- `-u pb_updates` on all five: EXIT=0, **0 ERROR/CRITICAL** in every upgrade log.
- **Downtime 132 s** (11:22:35–11:24:47). **No test in the stopped window** (G19).
- Active scheduled jobs: identical id lists before/after — 50 / 32 / 39 / 82 / 81; nothing
  re-activated, nothing lost, no new job.
- Assets: signal row + `/web/assets/%` purge + `web.assets.version` bump on all five.
- Users (count/active), leave requests (count + id/state hash), allocations (count + id/state/days
  hash), policy postings, employees, mail queue: **identical before/after on all five**; payobook
  pay-run totals hash identical.
- Sites after start: payobook.com, rize, p0clone, sudima 200. Server log since start: 0 ERROR.
- **Live p0clone after start (ports 8471/8472): pb_records 134 + pb_updates 203 tests, 0 failed,
  0 ERROR lines.**
- rize, for the record: the WORKFLOW-2 session made one owner-approved access change on rize at
  11:24 UTC, during this window (new role "See everyone's approvals" for debalina@rize.farm: +2
  groups on that user, +1 role assignment, +1 delegation, +1 access request, +1 approval request,
  +1 outbox row). That is theirs, logged in `/opt/deploy-notes.md`; this deploy did not cause or
  touch it (my census counted users, leave and allocations only, which it does not change).

| Check | payobook | payobook_template | p0clone | rize | sudima |
|---|---|---|---|---|---|
| `pb_updates` latest_version | 19.0.1.6.0 | 19.0.1.6.0 | 19.0.1.6.0 | 19.0.1.6.0 | 19.0.1.6.0 |
| table `pb_updates_leave_line` / allocation column / rule | yes | yes | yes | yes | yes |
| upgrade log ERROR | 0 | 0 | 0 | 0 | 0 |
| active jobs before → after | 50 → 50 | 32 → 32 | 39 → 39 | 82 → 82 | 81 → 81 |
| leave balances from Updates after the checks | 0 | 0 | 0 | 0 | 0 |

## R6. Who uses the leave policy layer (census, read only, 2026-11-12)

| Database | Absence policy editions | People on one | Leave types it governs |
|---|---|---|---|
| **rize** (Rize Farms) | 4 published, all from 1 Nov 2026: VN, ID, IN, SG (carry cap 8; ID 6) | 225 of 241 active, all confirmed full time | annual: Rize VN/IN/SG · Annual / privilege (whole days), ID Annual Leaves (half days) |
| payobook | none | 0 | — |
| payobook_template | none | 0 | — |
| p0clone | none | 0 | — |
| sudima | none | 0 | — |

So on rize an opening balance from a sheet goes through the absence policy for those 225 people
(annual leave only, as at 1 Nov 2026 or later, permanent once set); the other 16 rize people, and
everybody on the other four databases, get one approved allocation per balance.

## R7. What undo can and cannot do

- **Can**: take back a balance this sheet set **outside** an absence policy, when nothing has been
  taken **or asked for** against it — the allocation is refused (kept as a refused record, so the
  history stays; it no longer counts on the Time Off screen). The rest of the update proceeds; each
  balance that stays is named with the reason.
- **Cannot**: (1) a balance set **through an absence policy** — the policy layer keeps postings
  permanently and offers no reversal; the Apply step says so before sending, the Past-updates row
  shows no Undo for it; (2) a balance with leave taken or requested against it (cancel the request
  first, then undo); (3) anything the sheet did not create — leave requests, accruals, carry-over,
  the January rollover are never touched.
- After an undo the same person and leave type can be given a balance again (a fresh one).

## R8. Live checks

1. **Live payobook, server-side as the QA user, read only, rolled back** (`odoo-bin shell`, logfile
   in the evidence folder): home lists 7 leave types offered to company 5 people, attendance tile
   available; the leave sheet for the whole roster (4,547 people, 7 columns) in 3.8 s; read back as
   our sheet and sent straight back: **0 changes** (3,049 rows matched, 1,498 namesake rows
   unmatched, as in P2d); a leave draft saved, listed, discarded; counts of leave requests,
   allocations, updates, leave rows, approval proposals and mails identical; transaction rolled back
   — **nothing written**.
2. **Throwaway copy `p4copy_payobook`** (restored on the server from a fresh dump WITHOUT scheduled
   jobs and mail servers — no window for the live workers, G-note copy-db-runs-live-crons — dropped
   with `--force` at 11:36, dump deleted): as the QA user, 3 balances for 2 DEMO people (DEMO
   Recruiter: Paid Time Off 12, Extra Time Off 2.5; DEMO Nguyen Van An: Paid Time Off 7) — approved at
   once (company 5's route is "No approval needed"), written as the QA user from 1 Nov 2026; the Time
   Off screen showed 12 / 2.5 / 7; the same sheet again: "same"; Undo: "3 balances were taken off.";
   leave requests, accruals, postings and mails identical before/after.
3. Browser look-only on payobook.com (R4 item 12). sudima and rize: not opened in the browser;
   nothing applied there.

## R9. Deviations from the handover, and why

1. **Who may send a leave sheet: a Time Off administrator** (`hr_holidays.group_hr_holidays_manager`).
   That is the right the policy layer itself demands (`_manager`) and that may approve any
   allocation; HR officers can still check a sheet and see what it would do. Undo needs the same
   right.
2. **Written as the proposer** (not the approver), with their rights — the precedent of the bank
   lane (`_writer_desk`): the approver may be an HR lead without Time Off rights.
3. **People on an absence policy: annual leave only.** The policy layer's opening balance only takes
   its annual leave types (day or half-day). A non-annual leave type for a policy person is refused
   with a sentence, not written as a plain allocation beside the policy; a leave type governed by a
   policy is refused for a person not on it.
4. **Whole-day leave types refuse decimals** (handover rule "accept what the unit allows"). rize's
   policy annual types for VN/IN/SG are whole-day types, so a balance like 12.5 there is refused —
   owner item R11.1.
5. **0 is refused** ("A balance of 0 sets nothing"): a 0 policy posting would record nothing usable
   and still block that year for good.
6. **A plain balance has no end date** (the allocation form's default); a policy balance ends 31 Dec
   (the layer's own rule). Undo refuses the allocation rather than deleting it.
7. **Quiet writes**: no tracking messages, no chatter line, approval to-dos closed without email —
   225 people at once would otherwise get notifications.
8. **Start screen: a leave-type picker** (in use first), and "Goes to" lists only leave types for
   the countries the people work in (G61) — 31 stock types are "with a balance" on payobook.
9. **The attendance tile opens Workforce › Time › Import** (the current home of the attendance file
   importer; the retired standalone action still exists but is no longer on the rail), gated by the
   Time lens's own group (attendance officer). Also a fourth tile on the Updates home for the leave
   kind.
10. **Carried / taken without a balance in the same row** are refused ("Fill in … as well"), since
    the policy layer records them only with a balance.

New ledger entries: D16–D19 (owner), U37–U39, G60–G64.

## R10. New gotchas (ledger G60–G64)

OWL reads `lt`/`gt`/`lte`/`gte` as operators (a loop variable `lt` blanked the screen); leave type
countries are computed from the company and the stock types are global with a country; the policy
layer returns an existing posting silently and has no reversal; done activities stay as archived
rows; sync the snapshot tree and purge assets after every screen edit.

## R11. Needs an owner decision

1. **rize and whole-day leave types.** rize's annual leave for Vietnam, India and Singapore is taken
   in whole days, so an opening balance like 12.5 days is refused ("…must be a whole number of days").
   If rize's carried-over balances have halves, either the leave types should allow half days, or
   balances are rounded before sending. Which?
2. **Who may set balances.** Today only a Time Off administrator can send a leave sheet or undo one.
   Should HR officers be able to send (the approval route still decides)?
3. **Plain balances never expire.** A balance for someone not on an absence policy runs from the date
   with no end date (as the Time Off screen's own form does). Should it end on 31 December instead?
4. **Policy balances are permanent.** For the 225 rize people on an absence policy, a wrong opening
   balance can only be corrected on the policy's own screens, not undone from Updates.
5. **Year-to-date figures** (D19): design only, not started.
