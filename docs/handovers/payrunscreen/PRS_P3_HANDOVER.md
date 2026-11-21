# PRS P3 — "Kind of run": Regular / Top-up

Read first: `PRS_LEDGER.md` (C1–C13, R1–R7, gotchas) and the Follow-up 1
section of `PRS_P2_REPORT.md` (why R6's top-up half could not be built).

## Owner ruling R8 (2026-11-04) — add to the ledger

A pay run has a **Kind of run**: Regular (default) or Top-up. It is picked when
the run is made and can be changed on the run while it is a draft. "Compared
with" (R5/R6) only pairs runs of the same kind: a top-up compares only with an
approved top-up of the month before. Existing runs stay Regular; NO backfill on
any database (payobook demo included).

## Scope

1. `hr.payslip.run.pb_run_kind` in pb_payruns: `fields.Selection([('regular',
   'Regular'), ('topup', 'Top-up')], string='Kind of run', default='regular',
   required=True, tracking=False)`; help (plain English): "Top-up: an extra run
   that pays a few people something on top of their normal month — a bonus, a
   correction, an award. Top-ups are only compared with other top-ups."
2. Run settings card on the pay run screen: a "Kind of run" row, editable in
   draft only (same rule as the other settings), saved by the form.
3. Header chip on the run screen: show "Top-up" (soft violet chip) when the run
   is one; nothing for Regular.
4. Pay Run board card: a small "Top-up" tag on top-up cards (same chip style the
   board already uses for division). Board quick look: one line "Kind of run:
   Top-up". Nothing for Regular.
5. Pay run wizard (`pb_payrun_wizard`): a "Kind of run" choice on the first step
   (Regular selected; Top-up with the help sentence under it), passed into
   `run_vals` in BOTH create paths (`pb_payrun_wizard.py:1072` in
   `create_and_compute`, `:1220` in `prepare_run`) when the field exists. Keep
   gitlocal-f3's `scheme_preview` 'unchecked' key and hint line exactly as they
   are.
6. `get_run_screen` comparison: add `pb_run_kind` equality to the previous-run
   search (R6 + R8). The "nothing to compare with" sentence names the kind for a
   top-up: "There is no approved top-up for August 2026 on this scheme, so there
   is nothing to compare with yet."
7. Tests: T19 default Regular; T20 top-up compares only with an approved top-up
   of the month before (a Regular approved month is ignored); T21 the wizard
   passes the kind on both paths; T22 board card carries the kind; extend the
   header-button guard test if anything changed in the header (it should not).
8. vi_VN for every new string (C9): "Kind of run" = "Loại kỳ lương", "Regular" =
   "Thường kỳ", "Top-up" = "Bổ sung" (use these unless the .po already
   translates the same English word differently; then match it and say so).

## Safety rail (binding)

Today the wizard's period guard (`_period_runs` → "exists" confirmation →
`force_clean` → `_clean_period`) and `_adopt_loose_slips` treat any run in the
same period + scheme as the same month's run. **Choosing Top-up must never
clean, delete, overwrite or adopt payslips from a Regular run.** Do the
minimum to make that true: when the kind is Top-up, the period guard and the
clean only consider Top-up runs, and loose-slip adoption is skipped. Do not
change Regular behaviour at all. Report exactly what a user now sees when
making a top-up for a month that already has a Regular run, and what still
does not fit a top-up (e.g. the wizard makes a payslip for every eligible
person; picking a few people is NOT in scope) as an owner question.

## Non-goals

No backfill. No new kind beyond the two. No change to approval routes, pay
calculation, delivery or the payslip. No rize record changed.

## Deploy — RISKY tier (a new stored column on a client table)

Everything in C11, plus before the `-u`: `sudo -u postgres pg_dump -Fc <db> >
/odoo/backups/prs-p3-<db>-<UTC stamp>.dump` for each of the four DBs (check
free disk first; report sizes). Modules: pb_payruns, pb_payrun_wizard (bump
both past HEAD; gitlocal-f3 shipped pb_payruns 19.0.3.4.3). Order on each DB:
pb_payruns then pb_payrun_wizard in the same `-u`. Verify `pb_run_kind` is
'regular' on every existing row (`select pb_run_kind, count(*) from
hr_payslip_run group by 1` per DB). Message gitlocal-f3 before the `-u`.

## Browser (payobook.com, QA login; read the console)

B13 a draft run: Kind of run row in Run settings, switch to Top-up, save →
header chip appears; switch back to Regular, save (leave it Regular).
B14 the pay run wizard first step shows the choice (go no further than
reading it; do not make a run).
B15 the board shows no Top-up tag anywhere (no run is a top-up) and nothing
else moved.
B16 rize run 1591 opened only: Regular, no chip, nothing pressed.

## Report back (`PRS_P3_REPORT.md`)

Test results (whole pb_payruns + pb_payrun_wizard suites), deploy evidence
(backups, versions, cron counts, row counts by kind, log grep), B13–B16, the
top-up wizard behaviour + owner questions, ledger rows, commit hash(es). Do not
push.
