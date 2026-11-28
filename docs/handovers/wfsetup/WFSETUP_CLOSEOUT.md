# WFSETUP — closeout (2026-11-26)

Programme: replace the Codex "Set up Workforce" screen with a guided 7-step **Workforce setup** studio, then carry
clock hours from Sudima's time clocks into pay from 1 December 2026. Phased build P1–P10c, each phase a handover +
report in this folder. Ledger of gotchas: `WFSETUP_LEDGER.md` (WS1–WS79). Owner rulings: `WFSETUP_OWNER_RULINGS.md`
(R1–R17). Deferred streams: `WFSETUP_BACKLOG.md`.

## 1. What is live (all five: payobook, payobook_template, p0clone, rize, sudima; never abm)

| Phase | What | Live |
|---|---|---|
| P1–P5a | `pb_workforce_setup` studio: Shifts, Working weeks, Who works what, Late and overtime rules, Holidays, Time clocks, Check and go live; publish in slices; pay-rate resolution fix (`pb_hr_workforce`); Workforce tabs trimmed (`pb_workforce_workspace`) | sudima + payobook 24 Nov (P5b, 551 s down) |
| P6 | Honest clock states in step 6/7, Undo redraw after bulk actions | 25 Nov, 109 s |
| P7 | Studio installed on rize, payobook_template, p0clone | 25 Nov, 89 s |
| P8 | Clock-ins → attendance rehearsal: **NO-GO** (90.3 % match; legacy attendance blocks rules) → rulings R8–R16 | rehearsal only |
| P9 | Clock connection Disable / Enable (reversible, catch-up proven) | 25 Nov, 211 s |
| P10b | Scheme "Hours from the clocks from" date; paid days / OT / premium from the rules engine; readiness refusal list; recompute stamp; leading-zero clock matching (99.5 %); extra-hours On/Off in step 4 | 25 Nov, 619 s |
| P10c | "From the clocks" labels in the pay data template and component source card | 25 Nov, 755 s |

Final versions: `pb_hr_payroll_formula` 19.0.1.173.0, `pb_formula_studio` 19.0.1.216.0, `pb_clock` 19.0.1.6.0,
`pb_attendance_policy` 19.0.1.1.0, `pb_payrun_wizard` 19.0.1.48.0, `pb_workforce_setup` 19.0.1.7.0,
`pb_blueprint` 19.0.1.11.9 (later peer releases may have moved shared modules on).

Live sudima configuration done by us (owner-instructed, each undoable on screen): VN 2027 public holidays (10 days; none
in Dec 2026); built-in extra hours count OFF (step 4, "Switch it on again"); scheme 7844 maps paid days, OT and premium
hours from the clocks from 2026-12-01 + 7 information-only clock inputs (scheme still **draft**).
payobook.com keeps the classic Workforce menu (owner, do not re-ask).

## 2. Never done by us on live (customer's presses)
Confirm rules, publish a roster, switch clock-ins on, approve overtime, activate the scheme or contracts, run a pay run.

## 3. Sudima December checklist (full text in `WFSETUP_P10B_REPORT.md` §7)
1. Decide how overtime above the legal limit is paid (B1) — 40 % of approved OT in the rehearsal month.
2. Confirm OT limits (4 h/day, 40 h/month, 200 h/year; 300 h if special sector).
3. Mark each time-off type paid/unpaid (an unmarked type stops the run).
4. Put everyone on their real working week (step 3).
5. Confirm the late and overtime rules (step 4).
6. Publish the 1–31 Dec roster incl. Sunday shifts (step 7).
7. Sudima IT: get the five office PCs reading again (silent since 23 Nov), then switch clock-ins on (step 6); connector 1
   (owner's test PC) stays off.
8. During December: time off entered, one-punch days fixed, every OT entry decided.
9. Scheme "Propose for approval"; 650 contracts to Running.
10. Early January: run December pay; pay data file leaves clock columns and Sunday hours empty.
11. Before February: check Tết 2027 / National Day notice against step 5.

## 4. Open items
- **B1** overtime above the legal limit — separate stream, design only when the owner asks.
- **B2** 25 unmatched clock numbers (304 records) — Sudima to identify.
- **B3** Sudima job-board password unreadable.
- **B4** payobook_template has 40 active jobs.
- **B7 / R17** worked public holiday: 300 % until Sudima HR answers whether daily-paid workers get the day's pay on top
  (400 %); settle before 1 Jan 2027. Scheme 7844 has no holiday formula — the multiplier lives in the clock hours.
- P10c notes: "Set to read" says "No source" beside the clock chip; the Full view shows the source section twice;
  a peer's new clock option "Late working days (for allowance rules)" lacks vi/id text (theirs).

## 5. Server housekeeping done in this programme
- 2026-11-25: 308 pre-deploy backup entries in `/odoo/backups` dated before 22 Nov deleted (owner: "older than 3 days");
  server 89 % → 62 %.
- Weekly prune (owner ruling 2026-11-25, replaces the rize exemption for UPDATE backups only):
  `ops/deploy_backup_prune.py` → `/odoo/ops/`, `/etc/cron.d/payobook-deploy-backup-prune` Mon 16:40 UTC, deletes
  `/odoo/backups` entries older than 3 days for every database, keeps the newest 5, skips symlinks / in-use paths / a
  held deploy lock. Nightly backups (`/odoo/nightly-backups`, 7 days; rize 30) and `/odoo/archives` untouched. Rule
  appended to `/odoo/ops/AGENTS.md`.
