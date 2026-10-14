# MEHOME — conventions & gotcha ledger

Every handover in this program references this file. Add a row whenever a new gotcha is hit.
Program doc: `MEHOME_PROGRAM.md`. Design page: https://claude.ai/artifact/TXHSsQZQXJBJyzGpLR5pyF
(file copy `docs/design/my-payobook-home-poc.html`, tab "Bento").

## Standing rules (bind every phase)
- **M-R1 Design bar verbatim (binding).** "Extreme WOW, intuitive, out-of-this-world experience, best in class."
  Hero moment = the person's own money and week on screen before any click. Zero dead-ends: every card has an
  empty state that names what will appear and where to go. Motion with purpose only (count-up, ring fill, hover
  lift), all under `prefers-reduced-motion`. Lucide inline SVG only, never emoji, never Font Awesome. Locked
  indigo `#5A4BB0` family through the `--pbim-*` tokens, no gradients (the leave ring is a `conic-gradient` of
  two flat colours — that is a chart, allowed), one solid primary per card.
- **M-R2 The other modules stay untouched.** pb_me_portal owns the page: one `portal.portal_docs_entry`
  override + a URL-keyed registry + one Interaction. Never edit pb_ess_workforce, pb_pay, pb_goals, pb_training,
  pb_hiring, pb_onboarding, pb_offboarding, pb_assets, pb_comp_ben, pb_pip, pb_rnr, pb_timeoff, om_hr_payroll
  for this program. A wrong word on a tile is fixed in the registry (title/text override), not at the source.
- **M-R3 No new hard dependency.** `pb_me_portal.depends` stays as today. Every optional model is read through
  `'model.name' in self.env` and a stored field through `'<field>' in Model._fields`, inside one `optional()`
  helper that logs at debug on AccessError and warning (with trace) on anything else, and returns `None`.
  Absent ⇒ the section is `None` ⇒ the template does not draw the card. A source test lists every optional model.
- **M-R4 Own data only, resolved from the session.** Everything hangs off `_ess_employee()`; no route or payload
  ever accepts an employee id (safety rail 3). Reads of the OWN record may sudo (the route boundary is the gate),
  as the existing pages do.
- **M-R5 The server owns facts, the template owns words.** The payload carries keys, numbers, dates and existing
  names; every sentence lives in QWeb with `_()`-translatable text and has a Vietnamese line in `vi_VN.po`
  (memory `po-translation-loading-rules`: `#. module:`, `#. odoo-python`/`odoo-javascript`, `#: code:` lines).
- **M-R6 Quiet-board colour rule.** Grey at zero; amber = waiting on the person; rose = late/expired; green = a
  good outcome (net pay figure, approved). A delta is neutral. Never a ring at 100 %. "Needs you" order is fixed:
  shifts to confirm → expired document → document expiring → timesheet days missing → overtime waiting →
  training overdue → training due soon → goals to set → profile request (waiting / approved this week).
- **M-R7 Plain English, screen words, never the vendor's name.** Words come from the tiles that exist today
  ("My Leave", "My Schedule", "Payslip PDF"); money with the monetary widget; "Next pay · Friday 31 October";
  no internal names (no "allocation", "ack", "PIT" — say "tax").
- **M-R8 Lucide rule W87/W23 (from `ess_icon`).** Pass icon names with `t-value="'name'"`, never as a t-set
  body (branding wraps bodies in `data-oe-*` markup and every comparison fails silently). Nothing — not even a
  comment — may sit between a `t-elif` and its `t-else`.
- **M-R9 Browser proof.** No phase reports a screen as working without a Chrome walk of `/my` as an employee
  (ess1.demo on payobook after deploy; on the clone, a seeded employee user) AND a clean console. Desktop and a
  412 px viewport.

## Tile table (2026-10-14; all `customize_show`, all xpath `inside .o_portal_docs`, none with `icon`)
| Prio | Module · template | Title | URL | Render guard | counter |
|---|---|---|---|---|---|
| 20 | pb_me_portal `portal_my_home_ess` | Profile | /my/profile | — | profile_request_count |
| 20 | " | Documents | /my/documents | — | document_count |
| 20 | " | Tax Sheet | /my/taxsheet | — | — |
| 22 | pb_ess_workforce `portal_my_home_work` | My Schedule | /my/work/schedule | — | work_shift_count |
| 22 | " | My Timesheet | /my/work/timesheet | — | — |
| 22 | " | My Leave | /my/work/leave | — | work_leave_count |
| 22 | " | My Overtime | /my/work/overtime | — | work_overtime_count |
| 24 | pb_assets `portal_my_home_assets` | My Things | /my/assets | — | asset_count |
| 24 | pb_pay `portal_my_home_pay` | Your pay, explained | /my/pay | — | pay_change_count |
| 26 | pb_onboarding `portal_my_home_onboarding` | My Journey | /my/journey | — | journey_task_count |
| 26 | " | My Buddy | /my/buddy | — | buddy_count |
| 26 | " | Who's Who | /my/orgchart | — | — |
| 27 | pb_offboarding `portal_my_home_offboarding` | My Resignation | /my/resignation | — | resignation_count |
| 29 | pb_pip `portal_my_home_growth` | My Growth Plan | /my/growth | `has_growth_plan` | growth_count |
| 30 | om_hr_payroll `portal_my_home_payslip` | Payslips (no text, NO config_card) | /my/payslips | counter only | payslip_count |
| 31 | pb_comp_ben `portal_my_home_compensation` | My Pay Package | /my/compensation | `has_pay_package` | compensation_count |
| 32 | pb_rnr `portal_my_home_recognition` | Recognition | /my/recognition | `has_recognition` | recognition_count |
| 42 | pb_hiring `portal_my_home_hiring` | Refer someone | /my/refer | — | refer_count |
| 43 | pb_hiring `portal_my_home_hiring_mine` | My hiring | /my/hiring | — | hiring_count |
| 44 | pb_training `portal_my_home_training` | My training | /my/training | — | training_count |
| 45 | pb_training `portal_my_home_training_team` | My team's training | /my/training/team | — (no manager check) | training_team_count |
| 46 | pb_training `portal_my_home_training_claims` | My training allowance | /my/training/claims | — | training_claims_count |
| 46 | pb_goals `portal_my_home_goals` | My goals | /my/goals | — | goals_count |
| 47 | pb_timeoff `portal_my_home_holidays` | Public holidays (text = `pb_holidays_next` or a default) | /my/holidays | — | pb_holidays_count |
| stock | portal `portal_my_home` | Addresses / Connection & Security | /my/addresses, /my/security | config_card | — |
| stock | account / project / hr_timesheet | Your Invoices (always shown by account JS), Our Invoices, Projects, Tasks, Timesheets | /my/invoices…, /my/projects, /my/tasks, /my/timesheets | counter | — |

## Ledger
| # | Date | Gotcha / fact | How to apply |
|---|---|---|---|
| M1 | 2026-10-14 | Counters are filled AFTER render by `PortalHomeCounters` (`/my/counters`); at render every counter is unset. | Card numbers are computed eagerly in `_prepare_portal_layout_values` (one `get_home_data` call, only when `/my` is the route — check `request.httprequest.path == '/my'`); tiles keep the stock lazy counters. |
| M2 | 2026-10-14 | `portal_docs_entry`'s picture variable is `icon` (a static URL), not `image`; the `<img>` sits in `div.o_portal_icon` which `portal_docs_entry_layout` turns `d-block`. | The override replaces `div.o_portal_icon` with an inline Lucide badge; it never sets `icon` itself. |
| M3 | 2026-10-14 | `get_my_leave()` balances are allocated − taken over ALL validated rows, with no date filter. | Caption says "of N allocated", never "this year". |
| M4 | 2026-10-14 | `pb.employee.document.expiry_state` is a non-stored compute (90-day "soon"); it cannot be searched. | Count expiring docs with a domain on `expiry_date` (`<= today + 90 d` and `>= today`; `< today` = expired), own employee only. |
| M5 | 2026-10-14 | Every optional source module (pb_ess_workforce, pb_timeoff, pb_comp_ben, pb_goals, pb_training, pb_pip, pb_pay, pb_pay_delivery) DEPENDS ON pb_me_portal. | pb_me_portal can never import them; soft reads by model name only (M-R3). |
| M6 | 2026-10-14 | `Payslips` tile (om_hr_payroll) has no text and no `config_card`: it is `d-none` until the counter reveals it. | Registry marks `/my/payslips` as `hidden` (the Pay card is its door); the counter RPC still fires, harmless. |
| M7 | 2026-10-14 | `editable` is a reserved website render-context key; a template var of that name is shadowed. | Never name a payload key `editable`. |
| M8 | 2026-10-14 | All `CustomerPortal` subclasses merge into one Python class. | Every new helper/route method is prefixed `_pbme_`. |
| M9 | 2026-10-14 | The next pay date is company-level (`pb.payroll.calendar`), not per employee; the blueprint pay-day rule is officer-gated. | Show the calendar date when present; never guess from `schedule_pay`. |
| M10 | 2026-10-14 | `my_details=True` (set inside `portal_my_home`) is what adds the "My account" h3 and the `col-lg-4` contact column. | Override the `t-set` to `not pbme_home` so an employee's page is full width and has no side column; non-employees keep it. |
| M11 | 2026-10-14 | Custom tiles are injected AFTER `.o_portal_doc_spinner`, outside every `o_portal_category` div. | The Interaction moves `.o_portal_index_card` nodes by `data-pbme-group`; the spinner is hidden by CSS on `.pbme-home`. |
