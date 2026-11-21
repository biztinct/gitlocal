# HOME — premium Home dashboard (program doc)

Owner brief (2026-10-12): "design this home dashboard as a premium dashboard with mini charts … absolutely premium
with user delight and exceptional user friendliness". Prototype **approved as-is** on 2026-10-12; build mode =
phased (Fable designs, Opus builds in-session, Fable deploys and walks).

Design page: https://claude.ai/artifact/6XeVJQr4AARBDoARVS3FgR — file copy `docs/design/home-dashboard-prototype.html`
(**the build target; what it shows is what ships**). Ledger: `HOME_LEDGER.md` (rules H-R1…R8 + rows).

## What Home becomes (one screen, top to bottom)
1. **Top line** — greeting + date + company (small), "Prototype" pill removed in the build, "Updated hh:mm", the
   existing ⌘K ask pill (pb_hub palette) — no new ask surface.
2. **Hero (light-tint card)** — eyebrow "October 2026 payroll"; h1 = the state in words ("8 days to payday · 1 pay
   run needs your approval"); one plain sentence with inline links; 5-node journey (Set up · Prepare · Approve · Pay ·
   Deliver payslips) with done/now/wait/todo tones; ONE solid button that names the act; right card "October so far"
   = prepared-of-expected with a progress bar, net so far, run count, cut-off, and a 12-month net sparkline.
3. **Needs you** line — every open action as a chip (amber waiting on someone / rose problem); nothing at zero; tail
   link "All N approvals".
4. **Payroll, month by month** (2/3 width) — 12 columns = the month picker (click, ← →, Esc); segmented Net pay /
   Gross pay / Deductions / Employer cost / People; hover tooltip with full figures; in-progress month = hollow
   column at the latest completed month's height with the prepared share filled; "Latest" / "Tet" / "In progress"
   small labels. Under it: the month's facts line (runs, approved, delivered, "All runs balance"), four figures each
   with its own sparkline and a neutral delta (People paid, Net pay, Average net per person, Total cost to the
   company), and ONE stacked bar Net | Deductions | Employer cost with a Gross bracket + legend.
5. **October, step by step** (1/3) — the 5 steps with who/when; **Coming up** — cut-off, interviews, payday,
   contracts ending, next public holiday.
6. **Row of three cards** — People this month (joined / leaving, out today split, 7-day strip, red line for people
   with no active contract), October pay runs (each run: monogram, state badge, progress bar, net; a rose/amber note
   that names the problem AND the next step), Hiring (counts + a note).
7. **Closing row** — Keep learning (next best lesson + streak), Pay schemes (quiet line; never a ring at 100 %).

Empty / small-tenant states: the activation checklist stays exactly as today (tests pin it) and replaces sections
2–7 when `activation.show`; a month with no runs shows the column at zero with "No pay run" in the tooltip; a chip
with 0 is not rendered; a card whose source module is absent is not rendered (the row re-flows).

## Verified plumbing (do not re-derive; refs checked 2026-10-12)
- **Home today**: `pb_dashboard` = one AbstractModel `pb.dashboard`, one RPC `get_dashboard_data(period)`
  (`pb_dashboard/models/pb_dashboard.py:218-431`), one OWL component `PbDashboard` (`static/src/js/pb_dashboard.js:120-626`)
  mounted standalone (action tag `pb_dashboard`) AND as the `pulse` lens of pb_home_hub with `embedded: true`
  (`pb_home_hub/static/src/js/home_hub.js:50,128-135`). The hub also calls `pb.pay.hub.get_period_state` for its
  tracker chip (`pb_payhub/models/pb_pay_hub.py:135-158`). Depends only on `web, om_hr_payroll, pb_hr_payroll_base`
  (`__manifest__.py`); every other model is read through `optional()` (`pb_dashboard.py:227-244`), AST-checked by
  `tests/test_activation.py:196-228` (test_04/test_05 — note test_05 greps the substring `pb_import`, which would also
  catch `pb_import_kit`: H5).
- **Money rail**: `_period_kpis` sums `pl.code='GROSS'` + categories INSCO/COMP over `hr_payslip_line`
  (`pb_dashboard.py:184-215`) — breaches the one-pay-band rule and costs 2.1 s per month. The stored run roll-ups are
  free and correct: `hr.payslip.run.pb_employee_count / pb_total_net (indexed) / pb_total_gross / pb_total_deductions /
  pb_total_employer_cost / pb_balance_ok / pb_balance_gap / pb_unsourced_count / pb_currency_id / pb_division /
  pb_division_label` (`pb_payruns/models/hr_payslip_run.py:218-276`, computed by `_compute_pb_totals` with the
  pay_role CASE at `316-458`). `hr_payslip_line` is 1.7 GB on payobook: any planner scan costs ~12.5 s (`pb_dashboard.py:92-102`).
- **Three "current month" definitions** exist: dashboard = newest month with payslips (`_payroll_months`,
  `pb_dashboard.py:89-121`); `pb.pay.hub._period` = the CURRENT calendar month with stage 1–5 from the least-advanced
  overlapping run (`pb_payhub/models/pb_pay_hub.py:40-52, 60-158`; runs scoped by their payslips' companies, PA4);
  pb_payruns keys a run's month on `date_end` (`pb_payruns/models/pb_payruns.py:42-208`). Home uses the hub's month
  for the hero/steps and `date_end` months for the chart.
- **Run states** on this build: `draft / approval_pending / done / cancel` (`pb_payruns/models/hr_payslip_run.py:51-65`);
  payslip states `draft / verify / level1 / level2 / done / cancel` (`om_hr_payroll/models/hr_payslip.py:53-60`).
  `hr.payslip.run` has **no `company_id`** — scope through payslips (`pb_insights/models/pb_insights.py:155-174`).
- **Waiting on me**: `hr.payslip.run._pb_runs_awaiting(uid)` → ids of runs with an open seat held by me on an active
  step (`pb_payruns/models/hr_payslip_run.py:520-536`). Approvals inbox: `pb.approval.inbox.list_requests(tab='mine')`
  → `counts{mine, all, returned, done}` + cards with `process, area, title, amount, submitted_by/at, due_at, late`
  (`pb_approval_config/models/inbox_facade.py:178-230, 239-255, 314-388`); `_counts` = one bounded search + 3 counts.
- **Calendar**: `pb.payroll.calendar` (pb_comp_ben) rows per month: `month` (1st), `cutoff_date` ("Changes close"),
  `pay_date` ("People are paid"), `company_id`, `country_id`, `state` (`pb_comp_ben/models/payroll_calendar.py:36-66`).
  Next public holiday: `pb.holidays.next_one()` (`pb_timeoff/models/pb_holidays.py:454-465`, ungated, own company).
- **Leave**: `pb.timeoff._kpis` pattern — validated `hr.leave` covering today, pending = state in confirm/validate1,
  7-day counts from one bounded search (`pb_timeoff/models/pb_timeoff.py:103-163`). Delivery batches:
  `pb.payslip.delivery.batch` state `done` per run (`pb_payhub/models/pb_pay_hub.py:88-102`).
- **People**: `hr.employee.first_contract_date` (stored, from hr_contract) → joiners (`pb_people/models/pb_people.py:21-30`);
  contracts ending = `hr.contract` state open + `date_end` in window (`pb_contracts/models/pb_contracts.py:57-108`).
- **Hiring**: `pb.hiring._can_read()` gate (`pb_hiring/models/pb_hiring.py:79`); `get_board` is per-requisition heavy
  (`146-205`) — Home reads counts directly (`pb.hiring.requisition.state`, `pb.hiring.interview.feedback_late`
  `pb_hiring/models/pb_hiring.py:380,405`).
- **Learn**: `learn.runtime.next_best()` / `streak()` (`pb_learn/models/learn_runtime.py:483-536, 553-585`).
- **Schemes**: `hr.formula.config` (company_id at `formula_config.py:183`, `rule_count`, `state`, `validation_status`
  passed/failed/pending at `1043-1050`, `test_result_ids`), read inside `safe()` today (`pb_dashboard.py:337-350`).
- **Charts in this codebase are hand-drawn SVG** — sparkline precedent `pb_explorer/static/src/xml/explorer.xml:584-589`
  + `explorer.js:1170-1180`; ring `pb_tenancy/static/src/js/plan_usage.js:56-60`. Chart.js exists only as the lazy
  `web.chartjs_lib` bundle and is NOT used here.
- **Design system**: tokens and the newest owner-approved look = the Pay Runs board (`pb_payruns/static/src/scss/payruns.scss:5-22`
  tokens; hero `67-107`; cards `180-262`). Lucide = `import { ic } from "@pb_import_kit/js/import_icons"` (`pb_import_kit/static/src/js/import_icons.js:338-348`,
  unknown names fall back SILENTLY to a tick). Quiet-board rules: `docs/handovers/QUIET_BOARD_ROLLOUT.md:10-34`.
  Inter is never loaded by any backend asset (`biz_theme/static/src/scss/biz_variables.scss:76-77`) — the build
  renders in the system font unless H6 is taken up.
- **Learn anchors** on the current template: `data-coach="dash-hero|dash-runpayroll|dash-period|dash-kpis|dash-formula"`
  (`pb_dashboard/static/src/xml/pb_dashboard.xml:8,24,71,90,195`; used by pb_learn tours — `docs/tutorial_poc/author/data.js:3553-3578`).

## Phases
| Phase | Scope | Builder | Verify |
|---|---|---|---|
| **P1 Server data** | `pb.dashboard.get_home_data()` — the whole payload (period, needs-you, 12 months from stored run totals, runs, steps, upcoming, people, hiring, learn, schemes), every foreign read through `optional()`, no `hr_payslip_line` read, timing per section; tests 1–11. | Opus | tests on the server clone |
| **P2 Front end** | New `PbDashboard` template/JS/SCSS from the prototype: hero, needs-you, chart-as-picker + month panel, steps, coming up; embedded + standalone; keyboard; Lucide via the kit; Learn anchors kept; EN strings via `_t`. | Opus | source tests + Fable's browser walk after deploy |
| **P3 Cards, polish, VI** | People / October pay runs / Hiring / Keep learning / Pay schemes cards; empty states; VI `.po`; delete the old KPI code + tests pinned to it; version bumps; Learn lesson text for Home updated (pb_learn content + anchors). | Opus | tests + Fable walk |
| Deploy | After P2 (server + front end together) and after P3, payobook first (PENDING.md for the others), by Fable. | Fable | Chrome walk on payobook.com with the QA login; `timing_ms` read on payobook scale |

## Owner decisions
- OD1 (2026-10-12): prototype approved as-is. OD2: phased build (Fable designs, Opus builds). Open: none yet.
