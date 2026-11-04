# PRS P3 report — "Kind of run": Regular / Top-up

Phase: P3 of the PAY RUN SCREEN programme. Brief: `PRS_P3_HANDOVER.md`.
Owner ruling R8 added to `PRS_LEDGER.md`; new traps PRS-G31..G33.

Commit **768b9435b** (feature) on 19.1, not pushed. LIVE on payobook,
payobook_template, p0clone, rize 2026-11-04 00:36:51–00:41:36 UTC.

## 1. What was built

| # | Item | Where |
|---|---|---|
| 1 | `hr.payslip.run.pb_run_kind` — Selection Regular (default) / Top-up, `string='Kind of run'`, required, `tracking=False`, the handover's help sentence. Write guard: a change outside draft is refused ("The kind of run can only be changed while the pay run is a draft."); writing the same value is allowed. | `pb_payruns/models/hr_payslip_run.py` |
| 2 | Run settings row "Kind of run" (radio, horizontal), `readonly="state != 'draft'"`, saved by the form; the screen reloads after the save as for every other setting. | `pb_payruns/views/hr_payslip_run_form_enhance.xml` |
| 3 | Header chip "Top-up" (soft violet, `+` icon, tooltip "An extra run on top of the normal month. It is only compared with other top-ups."); nothing for Regular. Payload key `header.kind` (`None` for Regular). | `pb_payruns.py get_run_screen`, `payrun_screen.xml/.scss` |
| 4 | Board card: violet "TOP-UP" tag beside the period (same tag slot as "refund"); quick look line "Kind of run: Top-up"; nothing for Regular. Card payload key `kind`. The kanban view (`action-1167`, the board the Payroll menu opens) carries the same tag in its division-tag style. | `_board_cards`, `payruns.xml/.scss`, `hr_payslip_run_kanban.xml` |
| 5 | Wizard first step: "Kind of run" two-segment choice under the dates (Regular selected), the help sentence under it, the Scope panel shows "Kind of run · Top-up" when picked, plus one honest note when Top-up is picked (see §4). Sent as `run_kind`; written on BOTH create paths (`prepare_run`, `create_and_compute`) only where the field exists. gitlocal-f3's `scheme_preview` `unchecked` key and hint line untouched. | `pb_payrun_wizard` |
| 6 | "Compared with": previous-run search adds `pb_run_kind` equality. Top-up with nothing to compare: "There is no approved top-up for August 2026 on this scheme, so there is nothing to compare with yet." Regular wording unchanged. | `_screen_previous_run`, `_screen_compare_none` |
| 7 | Tests T19–T22 + T15 extended (below). | |
| 8 | vi_VN for every new string (§5). | |

Safety rail (binding) — built:
* Base wizard: with `run_kind='topup'`, `_period_runs(..., kind='topup')`
  returns top-ups only, so the "already exists" question, Clean and Run
  (`_clean_period` is handed exactly that set) and `plan_preview` never see a
  Regular run. `_adopt_loose_slips` returns nothing for a top-up run;
  `plan_preview` reports `adopt: 0`. The "exists" sentence for a top-up names
  top-ups and says the month's regular run is not touched.
* **pb_demo** (payobook.com only) overrides `prepare_run` and
  `create_and_compute` for demo divisions WITHOUT calling super — its own guard
  and clean would have cleared the division's regular demo run. Mirrored: the
  clear set is filtered to top-ups when Top-up is picked, and the run gets its
  kind (PRS-G31). Version 19.0.1.13.1.
* Regular behaviour is unchanged (pinned by a test): a Regular run still sees
  every run of the month, top-ups included, and still adopts loose payslips.

Not changed: approval routes (still chosen by the scheme map's cycle type),
pay calculation, delivery, payslips. No backfill: the column was created with
its default, so every existing row reads Regular.

## 2. Tests

Scratch DB `am_prs_p3` (clone of `am_prs_p2c`), `-u pb_payruns,pb_payrun_wizard
--test-tags /pb_payruns,/pb_payrun_wizard`: **241 tests, 0 failed, 0 errors**
(both whole suites). The only ERROR log lines are the spreadsheet step's
deliberate bad-file tests.

* T19 `test_t19_a_run_is_regular_unless_someone_says_top_up` — default Regular,
  no chip; Top-up shows the chip; on an approved run the same value saves,
  a change is refused.
* T20 `test_t20_a_top_up_compares_only_with_last_months_top_up` — August's
  approved Regular is ignored by a September top-up (top-up sentence);
  August's approved top-up IS the comparison (+25%); September Regular still
  compares with August Regular.
* T21 `pb_payrun_wizard/tests/test_run_kind.py` (9 tests) — kind written by
  `prepare_run` and `create_and_compute`; no key / unknown value = Regular;
  a top-up does not meet the month's Regular run; Top-up + force_clean on both
  paths never clears it; a top-up adopts no loose payslip (and plan preview
  says 0); a second top-up asks, names only the top-up, and Clean and Run
  clears only it; Regular behaviour unchanged; first step offers the choice.
* T22 `test_t22_the_board_card_carries_the_kind`.
* T15 extended: the composed form has exactly one `pb_run_kind` inside Run
  settings, `readonly="state != 'draft'"`. Header-button guard (T14)
  unchanged — the header was not touched.
* Local asset compile of `web.assets_backend` (shell): CSS + JS build, new
  classes present, no style error.

## 3. Deploy evidence (RISKY tier)

* gitlocal-f3 messaged before the `-u`; their "go" (nothing in flight) relayed
  by Fable. `/opt/deploy-notes.md` read before START; START 00:36, DONE 00:42
  lines written. flock + `/odoo/ops/filter_deploy.sh full`, staged from
  `git archive HEAD` (768b9435b). Live trees of all four modules were checked
  byte-identical to the previous HEAD before staging.
* PO gate (PoFileReader on the box, staged files): pb_payruns 830 rows,
  pb_payrun_wizard 121, pb_demo 166 — clean; every new msgid read back.
* Backups (pg_dump -Fc, taken by the script under the lock, before stop),
  `/odoo/backups/prs-p3-run-20261104003651/`: p0clone 26.7 MB,
  payobook_template 26.5 MB, rize 41.7 MB, payobook 78.1 MB. 23 GB free.
* `-u pb_payruns,pb_payrun_wizard,pb_demo` per DB: EXIT=0 errors=0 ×4
  (p0clone, payobook_template, rize, payobook). pb_learn synced, no `-u`
  (JS only, version unchanged).
* Active jobs before/after: 31 / 28 / 74 / 42 — unchanged.
* Versions: pb_payruns 19.0.3.5.0 and pb_payrun_wizard 19.0.1.40.0 on all 4;
  pb_demo 19.0.1.13.1 on payobook (not installed elsewhere); pb_learn
  19.0.20.8.5 on all 4 = manifest.
* Trees byte-identical to the stage (script hash check, result OK).
* Assets: purge + `orm_signaling_assets` row + `web.assets.version` bump per DB
  (script). Sites warmed 200.
* Rows by kind: payobook regular 53, p0clone regular 10, rize regular 10,
  payobook_template no runs. No NULL, no Top-up.
* Server log since the restart: no ERROR / CRITICAL / Traceback.
* Evidence `/tmp/prs-p3-run-20261104003651` on the box.

## 4. Browser (payobook.com, QA login, console read on every screen)

| | Result |
|---|---|
| B13 draft run 2419 | PASS — Run settings shows "Kind of run" Regular ● / Top-up ○. Picked Top-up, saved: "Top-up" chip appeared after "Draft", compare line became "There is no approved top-up for September 2026 on this scheme…". Picked Regular, saved: chip gone, compare line back to the regular sentence. Final DB value `regular`, state draft. Screenshot `p3_screens/B13_topup_chip_payobook_2419.png` (settings card while Top-up). |
| B14 wizard first step | PASS — "Kind of run" under the dates, Regular selected, help sentence under it. Picking Top-up (screen state only) shows the note and "Kind of run · Top-up" in Scope; set back to Regular. Compute NOT pressed, no run made. `p3_screens/B14_wizard_kind_topup_picked_payobook.png`. |
| B15 board | PASS — Pay Runs kanban (53 cards): 0 "Top-up" tags, division tags as before; the card board (19 cards this month): 0 top-up tags, quick look opens with no kind line. `p3_screens/B15_board_no_topup_payobook.png`. |
| B16 rize run 1591 | PASS by read-only payload (no rize sign-in for this agent, as in P2): Regular, `header.kind` None, card kind regular, compare "no approved run of the same kind for August 2026". Unchanged afterwards: draft, write_date 2026-10-19 02:16:46, 63 payslips. Nothing pressed. |
| Console | Clean on every screen; only the existing app-icon size warning. |

Note: on a 520-payslip run the chip takes the screen's normal reload time
(~4–8 s, PRS-G28) to change after Save.

## 5. Translations (vi_VN)

"Kind of run" = **"Loại đợt lương"** — pb_payruns already translated it that
way (the approval route's kind label), so the handover's "Loại kỳ lương" was
NOT used (C9: match the existing word; PRS-G33). "Regular" = "Thường kỳ",
"Top-up" = "Bổ sung". pb_payruns: 6 new entries + the field reference added
to "Kind of run"; pb_payrun_wizard: 8 new entries. No `.pot` files exist for
these modules. No user string says the platform's name.

## 6. Learn (C8)

The Learn practice replica of the Run payroll Period panel now shows "Kind of
run: Regular" (EN + VI) — `pb_learn/static/src/engine/screens.js`. No lesson
text or anchor changed; no new coach anchor was added (PRS-G32).

## 7. Deviations from the handover

1. pb_demo changed (19.0.1.13.1) — not in the handover's module list, but the
   safety rail is false on payobook.com without it (PRS-G31).
2. pb_learn replica row (C8) shipped with the same deploy, no `-u`.
3. Backups were written by the deploy script as
   `/odoo/backups/prs-p3-run-20261104003651/<db>.dump` (same `pg_dump -Fc`,
   taken under the lock right before the stop) rather than
   `/odoo/backups/prs-p3-<db>-<stamp>.dump`.
4. "Kind of run" Vietnamese = "Loại đợt lương" (existing), not "Loại kỳ lương".
5. Added (not asked): a server-side guard on changing the kind after draft,
   the kanban card tag, and the one-line Top-up note on the wizard.

## 8. What a user sees making a top-up for a month that has a Regular run

1. Run payroll → pick the scheme → "Kind of run: Top-up". The note says the
   top-up still makes a payslip for everyone the scheme covers.
2. Compute payslips: NO "this month's payroll already exists" question (the
   Regular run is not looked at), nothing is cleared, no loose payslip is
   taken. A new draft run is made, marked Top-up, and a payslip is calculated
   for EVERY eligible person with the scheme's normal monthly formulas — i.e.
   a second full month, not a bonus.
3. If a top-up for that month already exists: "This month's <scheme> top-up
   already exists. It is <name>. Would you like to clear it and run this
   top-up again? The month's regular run, and anything belonging to another
   payroll scheme, are not touched." Clean and Run clears only top-ups (and
   only drafts — approved / pending ones are refused as before).
4. On the run: "Top-up" chip, "Compared with" only an approved top-up of the
   month before.

## 9. Owner questions

1. **A top-up pays everyone a full month today.** Making one through Run
   payroll calculates every eligible person's whole month again. To make it a
   real top-up you would delete the people it is not for on the run before
   sending it (the people table's bulk delete), and their amounts are still a
   full month's pay. Options: (a) leave it — top-ups are made by hand / by an
   import, and the kind is only for comparing; (b) a "pick the people" step
   for top-ups (the wizard already has "Run for just a few people…" on schemes
   with an employment-status component — it could be shown for every top-up);
   (c) a top-up that pays only chosen components (bonus, correction) — needs
   a scheme decision.
2. **A Regular run still clashes with a top-up of the same month.** Making the
   regular month AFTER a top-up still asks "this month's payroll already
   exists — clear it?", naming the top-up, and Clean and Run would clear the
   top-up (if it is a draft). The handover said not to change Regular. Should
   a Regular run ignore top-ups the same way?
3. Payobook's existing "Retail top-up", "Awards run" and "Retail bonus run"
   are Regular (no backfill). Mark them Top-up on the run while they are
   drafts? Approved ones cannot be changed (the kind is locked after draft) —
   say if those should be allowed once, by us.

## 10. Commits

* 768b9435b feat(payruns): "Kind of run" — Regular / Top-up … (PRS P3, R8)
* this report + screenshots (docs commit after it)

Not pushed.

## 11. Score against the design bar (C6)

The choice is one obvious control in the place it is made, with the reason in
one sentence under it; the run says what it is at a glance and nothing for
the normal case (quiet board pattern). Honest about the gap: the wizard tells
a person picking Top-up that it still pays everyone. What keeps it from
"best in class": a top-up should start from "who and how much" (question 1).
