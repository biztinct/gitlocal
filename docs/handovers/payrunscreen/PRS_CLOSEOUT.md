# PAY RUN SCREEN (PRS) — closeout, 2026-11-04

The single pay run screen (`hr.payslip.run` form) was redesigned from the
owner-approved mock-up (`docs/design/payrun-screen-prototype.html`,
https://claude.ai/artifact/FQ8Gdp8PAKEfij7brmm892) and is live on payobook,
payobook_template, p0clone and rize (never abm).

## What shipped

| Phase | What | Versions | Commits |
|---|---|---|---|
| P1 | `pb.payruns.get_run_screen` payload; `_pb_slip_totals` (one per-payslip money source) | (shipped inside 19.0.3.3.1 by gitlocal-f3) | 6eb39d6a3 |
| P2 | OWL view widget in the form: one primary, journey, money + checks, who signs it off / pay and deliver, people + quick look + bulk, history, run settings card, classic-layout escape hatch, header-button guard (C13) | pb_payruns 19.0.3.4.1 | 94a27cc52, 849d8e02e, 1e4e5fb52, 0a3f728a3, 824ad2802 |
| P2 F1 | full width, money-card gap, "Checks pass · N notes", R6 approved-only compare, R7 recalculate asks first | pb_payruns 19.0.3.4.2 | cff91d69c, 4c6445512 |
| P3 | "Kind of run" Regular / Top-up (R8): settings row, chip, board tag, wizard choice, same-kind compare; top-up never clears a regular run | pb_payruns 19.0.3.5.0, pb_payrun_wizard 19.0.1.40.0, pb_demo 19.0.1.13.1 | 768b9435b, 5fc176661 |
| P3 F1 | R9 regular never clears a top-up; R11 payobook runs 1524/1525/1526 marked Top-up | pb_payrun_wizard 19.0.1.41.0, pb_demo 19.0.1.13.2 | 8d773a537, e440940a4 |

Backups: `/odoo/backups/prs-p3-run-20261104003651/`, `/odoo/backups/prs-p3f-run-20261104025022/`.
Owner rulings R1–R11 and gotchas PRS-G1… are in `PRS_LEDGER.md`.

## Open items (owner / later)

1. Rize run 1591 "Rize Vietnam Payroll · October 2026" covers 1–30 Sep and its
   scheme has no sign-off (Send approves it at once). Owner: ask Rize first;
   nothing changed. The screen warns about both.
2. Big runs are slow for non-admins (~4 s + ~4 s for 520 people): the access
   layer checks every field read uncached; app-wide, belongs to the access
   module.
3. Top-ups still pay everyone's full month (R10: leave for now). Options on
   record: a "pick the people" step, or pay chosen items only.
4. Pay & deliver shows "Total net ₫0" for payobook run 1524 — not investigated.
5. Payroll report (opened from the screen) took ~3½ min to load — its own
   slowness, not the screen's.
6. Loose payslips (belonging to no run) are still adopted by a new Regular run,
   as before.
