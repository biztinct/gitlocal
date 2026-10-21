# NAV program — closeout (2026-10-21)

Menu and submenu redesign of Payobook. Designed by Fable from the 19 October review; built by Opus in six phases; all live on
`payobook`, `payobook_template`, `p0clone`, `rize`. Design of record: `docs/design/payobook-navigation-review-20261019.html`
sections 12–13. Rules and gotchas: `docs/handovers/NAV_LEDGER.md`.

| Phase | What shipped | Modules (version) | Report | Live (AEDT) |
|---|---|---|---|---|
| P1 | One submenu standard: 72 px sticky icon rail, label under icon, keyboard, phone strip; Workforce rail aligned | pb_hub 1.12.0, pb_mission 1.12.0 | NAV_P1_REPORT.md | 2026-10-20 23:10 |
| P2 | Eleven-entry menu: Payroll (was Pay Run), Hiring / Expenses / Talent areas, People takes Joiners · Probation · Exits · Contracts, Lifecycle hub = redirector, Ask HR on Home, Settings in 7 groups, search keywords for old words, role gates, Learn and Access updated | 30 modules + new pb_expenses_hub, pb_talent_hub (NAV_P2A_REPORT.md §1) | NAV_P2A/P2B_REPORT.md | 2026-10-21 08:25 |
| P3a | Hiring APPLICANTS (pipeline across jobs) and OFFERS (register with papers, checks, joining) + Overview tiles; two old bugs fixed | pb_hiring 2.10.0, pb_learn 20.5.13 | NAV_P3A_REPORT.md | 2026-10-21 10:47 |
| P3b | Readiness checklist with owners on run cards, started-weeks attendance advice, "Changes close in N days · People are paid on D" from the payroll calendar | pb_payruns 3.1.0, pb_learn 20.5.14 | NAV_P3B_REPORT.md | 2026-10-21 11:47 |
| P3c | Home › TEAM for managers (direct reports only; no money, no growth plans); inbox area arrival that never overrides a request focus | pb_home_hub 1.4.0, pb_approval_config 1.6.6, pb_probation 1.4.1, pb_goals 1.2.1, pb_learn 20.5.15 | NAV_P3C_REPORT.md | 2026-10-21 13:21 |
| P3d | Home › ASK HR as a Payobook board (counts, steps, filters, Take it / Hand to, empty states); fixed a live 403 on "Ask a new question" | pb_ask_hr 1.2.0, pb_learn 20.5.16 | NAV_P3D_REPORT.md | 2026-10-21 14:50 |

## Owner decisions recorded
- 2026-10-20: Pay Run → Payroll; Ask HR becomes a Home item; Learn stays visible; inside-screen audit before any build.
- 2026-10-21: run cards show both calendar dates (reverses the 11 Oct "no pay-day words" ruling, now that the calendar exists); P3 = all four screens.
- 2026-10-21 14:15 (via LEARNING L0, LD2/LD3): employee Training becomes its own GROW root "Learning"; Talent = GOALS · GROWTH · PRAISE; the Learn entry is renamed "Help". Supersedes §12.4 on those points.

## Left open (not defects)
- Vietnamese: lane titles Draft / Waiting for approval / Done on the Pay Run board are still English in VI (pre-dates NAV).
- The Hiring hub's inner tab bar can show a tab other than the rail item (logged P2).
- The offers register table scrolls sideways under ~1,500 px.
- Phone-width behaviour of P3 screens was checked in harnesses, not on a device.
- `pb_payhub` module display name still "Payobook Pay Run Hub" (not user-visible).
- §13 "Later" rows: skills matrix, policy library, obligations calendar, spend dashboard, scheduled reports, org chart on ORG.

## Deploy practice established
Shared lock + `/opt/deploy-notes.md` START/DONE (R14) with ChatGPT and the other Claude sessions; stage from `git archive HEAD`; cron snapshot per DB; bundle warm-up after restart; never reload translations with overwrite; Learn `.po` byte-identical and "gõ DUYỆT" = 1 on every pb_learn deploy.
