# PRS P2 — report (the new pay run screen, live)

Phase: P2 of the PAY RUN SCREEN programme. Brief: `PRS_P2_HANDOVER.md`.
Built, tested, deployed and walked 2026-11-04 by an Opus implementation
agent. LIVE on payobook, payobook_template, p0clone, rize (never abm).

Commits on 19.1 (not pushed):

| Commit | What |
|---|---|
| 94a27cc52 | feat — the screen, form arch, payload parts/R4/R5, tests, vi_VN, ledger (19.0.3.4.0) |
| 849d8e02e | fix — route preview ~1 s faster for non-admins; journey counts real checks (19.0.3.4.1) |
| 1e4e5fb52 | fix (looks) — quick-look lines, history "now", one reload after a button |
| 0a3f728a3 | fix (looks) — the screen loads silently under its own skeletons |

## 1. What was built

`pb_payruns/static/src/{js,xml,scss}/payrun_screen.*` — view widget
`pb_payrun_screen` first in the pay run form's sheet, plus a tiny
`pb_payrun_history` widget ("What happened") beside the native Run settings
group. Same URL, same record, same breadcrumbs.

* **Header** — status pill, work dates, scheme, people, "Paid in VND (₫)"
  chips; Downloads; More; ONE primary button with a key cap (Ctrl/⌘ ↵) and a
  "N to check" badge. The title is shown once, in the existing control panel
  breadcrumb line ("title once"); the screen does not repeat it.
* **Banners** — date mismatch (amber, R2), sent back (amber, with "Show who
  needs a look"), rejected (rose, read-only wording), classic layout on
  (slate, "Hide it").
* **Journey**, **money card** (big take-home, bold sentence, three-part bar
  growing in, four legend tiles, "Compared with" chip or the plain "nothing to
  compare with yet"), **checks card** (rows land one by one, then the verdict
  settles; doors as small outline buttons; amber advice rows from the board —
  FILLIN's `fillin` with no button, the attendance "week not closed" with its
  "Open Workforce › Close" door), **who signs it off** (prepared-by seat,
  seats, "Ready to pay", amber R4 note on a fast lane, its own skeleton while
  the route part loads), **pay and deliver** (approved runs; the "now" step
  presses Pay & deliver), **people** (team column with bars, search, three
  tabs, every column sortable incl. status, 100 rows + "Show 100 more",
  footer totals, "Nobody matches … Show everyone").
* **Quick look** side panel (portal to body): name, job · team, flag,
  take-home box, the payslip's own Pay / Deductions / Company pays on top
  lines from `pb_statement_json` (four-figure fallback), Trace + Open full
  payslip; ↑/↓ moves, Esc closes.
* **Bulk bar**: tick + shift-click range; only the verbs the payload allows
  (Recalculate, Payslips PDF, Delete these draft payslips — confirm names the
  count); Esc clears.
* **Keyboard**: `/` search (not while typing), Esc closes the top layer,
  Ctrl/⌘+Enter presses the primary (confirm first). Key handler is in the
  capture phase (PRS-G25) and steps aside when a dialog is open.
* **States**: skeleton loading; failed-load card (reason + Try again + Show
  the classic layout); empty run card with Make payslips; rejected banner;
  route part error row with Try again.
* **Buttons** go through the form's `env.onClickViewButton` (save first,
  reload after); confirms are `ConfirmationDialog` with explicit titles and the
  payload's words. The payload reloads when the record's identity, write_date
  or state changes (proved: one reload per save).
* **Escape hatch**: More › "Show the classic layout" → `body.pb-prs-classic`
  (sessionStorage, this tab only) brings back the native header (11 buttons
  on payobook), the old rail, alerts, KPI band and slip list.
* **Form arch**: `vu-no-hero`; `create="0"` (see §4); old pieces get
  `pb-prs-legacy` (hidden, never deleted); Run settings relabelled (Run name,
  Work dates, Full month in working days, Books it is posted to — via
  `_get_view` because accounting is not a dependency, Reverses an earlier
  run) and moved beside the history widget; "Full month in working days" now
  locked outside draft (it had no rule at all, PRS-G24).
* **Payload** (P1 fixes allowed by the handover): `parts='main'|'route'`
  (item 16); `tone` on every check row; R4 amber fast-lane / no-step row and
  confirm; R5 previous run = same kind (`_pb_kind_key`) for the calendar
  month just before; board amber advice rows with their own doors; More ›
  "Add or remake payslips"; `_pb_overtime_included` reads with one search
  (Submit path too — same payslips, same rules); journey counts only the four
  real checks.

Screenshots (`docs/handovers/payrunscreen/p2_screens/`):

* `B1_draft_payobook_2419.png` — draft, 520 people, hero + checks with amber advice
* `B1_send_confirm.png` — Send for approval confirm (cancelled)
* `B4_approved_payobook_1524.png` — approved run, Pay and deliver
* `B5_quick_look_payobook_2419.png` — quick look with the payslip's lines
* `B5_bulk_bar_payobook_2419.png` — 6 ticked by shift-range, bulk bar
* `B10_phone_people_payobook_1535.png` — 400 px wide, table scrolls in its box
* B3 / B12: no screenshot (see §2).

## 2. Tests

**Python** — whole `pb_payruns` suite on a clean clone of the P1 scratch DB
(pb_approval_config, pb_pay_delivery, pb_source_atlas, pb_payroll_templates,
pb_payslip installed; pb_hr_payroll_formula upgraded for FILLIN's column,
PRS-G22): **155 test classes / 179 methods, 0 failed, 0 errors**, 11 skipped
(all pre-existing: wkhtmltopdf, pb_comp_ben/pb_close absent, OTH category,
plain-user payslip ACL). New/changed: T7 (R5 wording), T14 header-button guard
(C13), T15 composed form (widget first, anchors kept, settings card), T16
`vu-no-hero` + `create="0"`, T17 fast lane amber, T18 June mid-month ≠ July
end-of-month, T18b two months back ≠ last month, parts main+route = whole,
"Add or remake payslips" offered, board advice rows with/without doors and
"All 4 checks pass" through the real entry point. T14 was also checked
against the LIVE composed form on payobook: the same 13 header buttons, every
one offered by the screen (Split as the one conditional entry).

**Browser** (payobook.com, QA login, company 5; console read on every page):

| | Result |
|---|---|
| B1 draft with payslips (2419, 520) | PASS — hero, ticks, verdict; confirm "Send for approval? It goes to 3 people in turn, starting with Demo User…"; Not yet; run still draft |
| B2 empty run | NOT WALKABLE on payobook — the QA account may not create pay runs and the demo world has none (PRS-G30). Walked locally: empty card, Make payslips opens Generate Payslips, closed |
| B3 pending run | NOT WALKABLE — no run is waiting for approval on payobook and none may be submitted for the test. Covered by T5 (live seats, Open the approval / Open in Approvals) |
| B4 done run (1524) | PASS — Pay and deliver steps, primary opens the existing Pay & deliver screen, back |
| B5 people | PASS — search, tabs, team filter, every column sorts, Show 100 more, quick look ↑/↓/Esc, tick + shift-range (6), bulk bar; delete NOT pressed |
| B6 Downloads | PASS — Excel downloaded (520 rows), PDF downloaded (1524), Payroll report opened (it takes ~3½ min to load by itself — pre-existing) |
| B7 More | PASS — Where the numbers come from, What changed, Add or remake payslips (Generate Payslips, cancelled), Delete draft payslips (confirm, Keep them), Reject (confirm, Keep it), Set back to draft (confirm, Keep it approved), Email payslips (confirm, Not now). "Recalculate everyone" NOT pressed: it acts at once with no confirm (P1 design) |
| B8 settings | PASS — working days 22→21 saved, screen reloaded once after the save; put back to 22 (final value 22, run still draft) |
| B9 classic layout | PASS — on/off; native header, rail, KPI band, slip list come back; off clears the tab flag |
| B10 phone width 400 px | PASS — page scroll width 400 = viewport; table scrolls inside its box |
| B11 console | PASS — no errors on any screen; one pre-existing warning (app icon size in the web manifest) |
| B12 rize 1591 | PASS by read-only payload (no rize sign-in available to this agent): mismatch banner text right, ₫ with 0 decimals and no ".00", 63 people, route row AMBER "No sign-off is set for this scheme / Sending it approves it straight away.", Send confirm says the same, compare "no run of the same kind for August 2026"; run unchanged afterwards (state draft, write_date 2026-10-19 02:16:46, 63 payslips). Nothing pressed |

Local smoke (fixture run on a scratch DB) also exercised: real bulk delete
path (stopped by a local permission, not by the screen), real save + reload,
empty run, classic layout, keyboard.

## 3. Deploy evidence

Normal tier via `/odoo/ops/filter_deploy.sh` (flock, backups, cron snapshot
`active` ids, stop, `-u pb_payruns` per DB stopping at the first failure,
cron restore, asset purge + `orm_signaling_assets` row + `web.assets.version`
bump, start, warm). Staged from `git archive HEAD`. gitlocal-f3 messaged
before each `-u`; their go-ahead relayed by Fable; START/DONE lines in
`/opt/deploy-notes.md`.

| Run | Version | Window (UTC) | Result |
|---|---|---|---|
| 1 | 19.0.3.4.0 (94a27cc52) | 23:19:35–23:24:09 | OK, EXIT=0 errors=0 ×4 |
| 2 | 19.0.3.4.1 (849d8e02e) | 23:35:02–23:39:43 | OK, EXIT=0 errors=0 ×4 |
| 3 | looks (1e4e5fb52) | 23:53 | OK, assets purged ×4 |
| 4 | looks (0a3f728a3) | 23:54 | OK, assets purged ×4 |

* `latest_version` = **19.0.3.4.1** on payobook, payobook_template, p0clone,
  rize (manifest 19.0.3.4.1).
* Active scheduled jobs before/after: p0clone 31/31, payobook_template 28/28,
  rize 74/74, payobook 42/42 — same as the last DONE lines.
* Module tree byte-identical repo ↔ server (47 files, `__pycache__`/`.pyc`/
  `.DS_Store` skipped) after each run.
* Server log: 0 `Traceback|CRITICAL| ERROR ` lines since each start.
* Translations: Odoo's `PoFileReader` on the box: 808 rows, 695 reaching a
  screen, no "Odoo" in any msgstr.
* Evidence dirs on the box: `/tmp/prs-p2-run-20261103231935`,
  `/tmp/prs-p2b-run-20261103233502`, `/tmp/prs-p2c-run-20261103235318`,
  `/tmp/prs-p2d-run-20261103235424`; backups `/odoo/backups/prs-p2-run-20261103231935`,
  `/odoo/backups/prs-p2b-run-20261103233502`.
* Which of gitlocal-f3's commits rode along: **12e57634d** (FILLIN P2
  block C — `_run_checks` 'fillin' advisory, pb_payruns 3.3.1), already live
  from their own deploy; shipped again unchanged inside HEAD.

## 4. The breadcrumb "New"

It is core behaviour: the form view's own create button ("New"), shown to
anyone allowed to create pay runs (the QA account is not, so payobook shows
none; rize's admin sees it). On this build a run's name and dates are
read-only on the form (Odoo 19 ignores the old `states=` rule), so a run made
from that button can never be saved — a dead end. Fixed in our view with
`create="0"`; runs are made by Run payroll. Test T16 pins it.

## 5. Learn impact

Nothing points at the pay run FORM. Every Learn anchor, lesson and replica
that mentions a pay run points at the Pay runs board cards ("Submit for
approval on its card in Payroll › Runs") — the board is unchanged. pb_learn
not touched.

## 6. Self-score against the design bar

* Hero moment — **met**: the take-home figure rises, the bar grows in three
  parts, ticks land one by one and the verdict settles.
* Zero dead-ends — **mostly**: every state has words and a next step;
  failed loads offer Try again + classic layout; the dead "New" is gone.
  Not met: "Recalculate everyone" and bulk Recalculate act with no confirm
  (P1's choice, unchanged).
* Plain language — **met** on this screen; two neighbouring windows it opens
  still say "Generate Payslips" / "Input changes" / "This wizard will…"
  (other modules, not touched).
* Motion with purpose, keyboard + bulk — **met**.
* Speed — **not yet best in class** on big runs: a 520-payslip run takes
  ~4 s for the main part and ~4 s more for who-signs-it-off for a non-admin
  (PRS-G28). The screen now stays readable throughout (own skeletons, no
  loading cover), and 3.4.1 took ~1 s off. Rize 1591 (63 people) is fast:
  0.10 s + 0.24 s server time.

Built differently from the mock-up, and why:

* No "Send a reminder" on a pending run — needs new server behaviour
  (non-goal).
* No Excel in the bulk bar — there is no per-selection Excel export; only
  the verbs P1's `bulk` allows are shown.
* No back link / big title inside the screen — the control panel already
  carries "Back to Pay Runs", the breadcrumb and the title (title once).
* Run settings descriptions are help tooltips (?) rather than lines under each
  label — the settings card is the native group, kept native.
* History and Run settings sit side by side only above 1180 px (stacked
  below, as in the mock-up).

## 7. Ledger, decisions, open items

New ledger rows: **C13** (header-button guard), **PRS-G19…G30**.

For Fable / the owner:

1. **Big runs are slow for non-admins** (PRS-G28): the access-studio layer
   (biz_access) runs an uncached permission lookup on every field read of a
   guarded record. It is app-wide (the board has it too). A cache in
   biz_access would fix it everywhere; that is outside this programme.
2. **"Compared with" can pair a top-up with the full month.** Payobook's
   3-person "Retail top-up — Sep 2026" is compared with the 902-person
   "Payroll August 2026" (same scheme, same kind) → "99.7% less take-home".
   And that August run is still a DRAFT, yet the sentence says "902 people
   were paid then". Options: only approved runs count as the comparison, and/or
   a top-up kind of run. Owner decision.
3. **Recalculate has no confirm** (More and bulk bar). It changes figures on
   a draft at once. Add one?
4. **Pay & deliver screen shows "Total net ₫0"** for run 1524 — that
   screen's own figure, seen in passing.
5. Rize 1591 is still a fast lane with the wrong month in its name (R2,
   PRS-G18) — the screen now says both plainly; nothing was changed.

## Follow-up 1 (2026-11-04, Fable's rize review + owner rulings R6, R7)

Commit **cff91d69c**, pb_payruns **19.0.3.4.2**, LIVE on payobook,
payobook_template, p0clone, rize (00:06:33–00:11:10 UTC; EXIT=0 errors=0 ×4;
active jobs 31/28/74/42 unchanged; tree byte-identical, 47 files; log clean;
gitlocal-f3 asked first and said go; START/DONE logged; evidence
`/tmp/prs-p2e-run-20261104000633`, backups `/odoo/backups/prs-p2e-run-20261104000633`).

| Item | Done | Checked live (payobook, 1568 px, QA) |
|---|---|---|
| 1 Width | Sheet is one centred 1320 px column; Run settings row the same width; above 1180 px Downloads / More / the primary stay on the right of the chips row (chips wrap in their own box) | screen 1320 px, 87 / 86 px either side; actions on the chips row |
| 2 Money gap | money / checks grid aligned to the top; each card sizes to its content | money card 353 px vs checks 554 px; 20 px from the compare line to the bar |
| 3 Notes | amber rows are "notes": journey "Checks pass · 1 note" / "· N notes"; verdict keeps "Everything checks out" + "Ready to send for approval, with N notes below." (fast lane: "Ready to send, with N notes below. Nobody signs it off…") | 2419: "Checks pass · 2 notes", "…with 2 notes below."; rize 1591 (read-only): "Checks pass · 3 notes" + the fast-lane sentence |
| R6 approved only | the previous run must be approved; wording "There is no approved run of the same kind for … " | 1524 top-up no longer compares with the draft 902-person August run |
| R6 top-ups | **NOT built — needs a decision.** No existing field or setting tells a top-up apart: payobook's "Retail top-up", "Awards run" and "Retail bonus run" carry the same scheme and the same scheme cycle type (end of month) as the full monthly runs, and no code creates them specially. The only "kind" notion is the scheme's cycle type (regular / mid-month / end of month / final settlement). R6 forbids inventing one, so a top-up would still compare with an APPROVED full month on the same scheme. | — |
| R7 Recalculate asks | More › Recalculate everyone and the bulk bar: "Recalculate N payslips? Their figures may change." / "Recalculate the payslip? Its figures may change.", OK "Recalculate", "Not now", primary (not danger) style | More: "Recalculate 520 payslips?"; bulk (3 ticked): "Recalculate 3 payslips?" — both cancelled |

Tests: T7 / T18 / T18b now approve their earlier runs; new
`test_r6_a_draft_or_pending_month_before_is_not_compared`,
`test_r7_recalculate_everyone_asks_first`,
`test_notes_are_named_in_the_journey_and_the_verdict`; the board-advice test
expects "Checks pass · 2 notes". Suite **158 classes, 0 failed**. No top-up
test (nothing to tell a top-up apart with — see R6 above). vi_VN: 11 new
entries, 7 merged; PoFileReader on the box: 819 rows, clean.

Console: clean on every screen walked (only the existing app-icon size
warning). The logo loader seen in some shots now comes from the Learn helper's
own request (`learn.guide.rpc_guide`, ~11 s), not from this screen.

Screenshots: `p2_screens/F1_wide_draft_payobook_2419.png` (1568 px),
`p2_screens/F1_phone_approved_payobook_1524.png` (400 px; page scroll width
= 400).

Ledger: R6, R7 added.

**Decision needed (owner):** how should a top-up be told apart from a full
month? Options in plain words: (a) a "kind of run" choice when a run is made
(Regular / Top-up), shown on the run and used for "Compared with"; (b) a
top-up is any run whose scheme is not set on the run itself (fragile —
some full months have no scheme set either); (c) leave it: compare with the
approved full month and accept the large percentages on top-ups.
