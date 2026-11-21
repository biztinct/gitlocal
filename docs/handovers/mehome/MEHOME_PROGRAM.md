# MEHOME — the employee home page (program doc)

Owner brief (2026-10-14): "/my is very archaic … some have icons and some have not. It is a hero page for
employees and will form the impression of the portal. It has to be WOW and leave a lasting impression … best in
class." Three directions were shown; the owner chose **Option 2 "Bento"** with the "Needs you" list from Option 1.
Build mode = phased (Fable designs, Opus builds in-session, Fable deploys to payobook and walks).

Design page: https://claude.ai/artifact/TXHSsQZQXJBJyzGpLR5pyF — file copy `docs/design/my-payobook-home-poc.html`
(**the build target is the "Bento" tab; what it shows is what ships**, at desktop and at the Phone toggle).
Ledger: `MEHOME_LEDGER.md` (rules M-R1…R9 + rows). Module: `pb_me_portal` (owner of `/my`).

## What the page becomes (one screen, top to bottom)
1. **Top line** — eyebrow "My <brand> · Wednesday 14 October" (brand read as `ess_hero` does, never a literal);
   h1 "Evening, <first name>." (time-of-day word from the user's timezone); ONE plain sentence built from facts
   (next pay in N days · N shifts waiting for your OK · a document needs renewing); a "who" pill on the right
   (avatar, name, job title · company). The stock "My account" heading, the breadcrumb bar and the right-hand
   contact column are gone for anyone with an employee record.
2. **Bento grid** (12 columns, 14 px gap; stacks to one column on a phone):
   - **Pay** (5 cols, 3 rows, light-tint card): label "Last pay · <Month>", the net figure large, a neutral delta
     line against the previous slip ("+₫1,200,000 on August", no colour unless the owner later asks), six bars for
     the last six paid months (current solid indigo, others white with indigo border, month labels under), footer
     "Next pay · <Weekday D Month>" when the pay calendar knows it, buttons "Explain my pay" (outline, only when
     `/my/pay` exists) and "Payslip PDF" (solid). Empty state: "No payslips yet · Your first payslip appears here
     once payroll runs" with a quiet link to Payslips.
   - **Leave** (3 cols, 2 rows): a ring with "<n> days left" inside, caption "of <allocated> allocated · <n> days
     booked" (never "this year" — balances are not year-bound, M3), outline button "Request time off". Hidden when
     the workforce module is absent; empty state when no allocation ("No leave allocated yet").
   - **This week** (4 cols, 2 rows): seven day cells Mon–Sun (today outlined; a shift shows its hours; a shift
     waiting for confirmation is amber; a day off is grey "off"; approved leave reads "leave"), footer "<h> h
     scheduled · <h> h worked so far" + solid "Confirm shifts" when any wait, else outline "Open schedule".
     Hidden when the workforce module is absent.
   - **Needs you** (4 cols): up to five rows, each `icon · bold what · grey detail · chevron`, in a fixed order
     (M-R6). Nothing waiting → one grey line "Nothing needs you right now" (never an empty card).
   - **Me strip** (7 cols): Profile · Documents ("1 expiring soon" when so) · Tax Sheet · My Things · My Pay
     Package — compact rows with coloured Lucide badges. These ARE the modules' own tiles, moved here (M-R2).
3. **Sections below** — "Time", "Growth", "People", "More" (stock Addresses / Sign-in & security / anything
   unknown), each a two-to-four column list of icon rows (title + one-line text). Payslips has no tile (the Pay
   card is its door). A section with no tiles is not drawn.
4. **Phone** (≤ 700 px): hero stacks, the bento becomes one column in the order Pay → Needs you → This week →
   Leave → Me strip; day cells shrink; buttons stay full-width tappable.

Who sees it: anyone whose user is linked to an employee record (`_ess_employee()` finds one). Anyone else
(customer, agency, supplier portal) keeps the stock page exactly as today. Employee-only people additionally keep
today's rule that invoice / project / task / timesheet tiles are hidden; for an employee who is ALSO a manager or
admin those stock tiles land in "More".

## Verified plumbing (do not re-derive; refs checked 2026-10-14)
- **Stock page** (Odoo 19, stock addons outside the repo at `/Users/adity/odoo19/odoo/addons` locally and
  `/odoo/odoo-server/addons` on the server): `/my` = `CustomerPortal.home()` →
  `portal.portal_my_home` (`portal/views/portal_templates.xml:204-235`): `t-set my_details=True`, then
  `div.o_portal_my_home > div.o_portal_docs.row` holding the category divs (`#portal_common_category` with the
  stock Addresses + Connection & Security tiles, `config_card=True`) and a `.o_portal_doc_spinner`. Every custom
  tile is xpath'd `inside` `.o_portal_docs`, so it lands AFTER the spinner as a direct child of the row.
  `my_details=True` makes `portal_layout` (`:144-180`) render the "My account" h3, the `col-lg-8` body and a
  `col-lg-4` `portal.side_content` (avatar, address, "Edit information" → `/my/account`), and hides breadcrumbs.
- **Tile template** `portal.portal_docs_entry` (`:237-258`): inputs `title, text, url, icon, config_card,
  placeholder_count, count, show_count, bg_color`. The picture is the **`icon`** variable (a static URL in an
  `<img>` inside `div.o_portal_icon.d-none`; the inheriting `portal_docs_entry_layout` turns it `d-block`). A
  tile without `config_card` is `d-none` until the counters script reveals it.
- **Counters are lazy**: `home()` calls `_prepare_home_portal_values([])` — no counter has a value at render.
  The interaction `PortalHomeCounters` (`portal/static/src/interactions/portal_home_counters.js`, selector
  `.o_portal_my_home`) collects `[data-placeholder_count]`, calls `/my/counters` (≤ 3 RPCs), writes the number,
  removes `d-none` from the closest `.o_portal_index_card` when the value is not 0, then removes the spinner. It
  keeps element references, so moving a tile in the DOM does not break it. Anything a card needs at render time
  must be set eagerly in `_prepare_portal_layout_values` or a `home()` override (precedent
  `pb_goals/controllers/portal.py:122-137`).
- **Custom tiles today** (22 of them, every one `customize_show`, none with `icon`): the full table with
  priorities, urls, guards and counters is in `MEHOME_LEDGER.md` §Tile table. Only three are guarded at render:
  `has_pay_package` (pb_comp_ben), `has_growth_plan` (pb_pip), `has_recognition` (pb_rnr). `Payslips`
  (om_hr_payroll, prio 30, `/my/payslips`) has NO `text` and NO `config_card`.
- **pb_me_portal today**: hero injected `before` `.o_portal_docs` with a hard-coded "My Payobook" eyebrow
  (`views/portal_templates.xml:19-32`); `.pbme-employee` class on the page when `pbme_employee_only`
  (`controllers/portal.py:50-59`, `models/ess_landing.py:36-57`); CSS hides invoice/project/task/timesheet tiles
  by `href` prefix (`static/src/scss/me_portal.scss:187-192`). Frontend bundle = `pb_import_kit` tokens +
  `me_portal.scss` (`__manifest__.py:55-60`); `ess_icon` = inline Lucide QWeb (`portal_templates.xml:76-87`,
  rules W87/W23 in its comment); `ess_hero` reads the brand (`:106-119`). Version `19.0.1.4.2`.
- **Employee**: `_ess_employee()` (`controllers/portal.py:28-37`): sudo search by `user_id`, current company
  first. Every `CustomerPortal` subclass merges into one class — helper names must be module-prefixed.
  `editable` is a reserved render-context name (`portal.py:88-90`).
- **Net pay**: `_ess_net(slip)` = `slip.line_ids.pb_net_line().total` or None (`portal.py:39-48`;
  `om_hr_payroll/models/pay_bands.py:168-189`, the one-pay-band rule). Slip states `draft/verify/level1/level2/
  done/cancel`; the portal list shows `done` + `cancel`, the tax sheet `done` only. Paid stamp `pb_paid_on`
  exists only when `pb_pay_delivery` is installed (`pb_pay_delivery/models/payment_release.py:320-339`; read it
  with `'pb_paid_on' in Slip._fields`). PDF door: `slip.get_portal_url(report_type='pdf', download=True)`.
- **Next pay day**: the only stored date is `pb.payroll.calendar.pay_date` (pb_comp_ben,
  `models/payroll_calendar.py:36-63`: `month`, `cutoff_date`, `pay_date`, `company_id` (empty = shared),
  `state upcoming/closed`; read ACL for `base.group_user`). Readers to clone: `pb_dashboard/models/home_data.py:
  443-451` and `:1186-1204`. pb_comp_ben depends on pb_me_portal, so read it through `'pb.payroll.calendar' in
  self.env` (precedent `pb_learn/models/learn_path.py:160-186`). Nothing gives a per-employee pay day.
- **Leave**: `pb.ess.workforce.get_my_leave()` (`pb_ess_workforce/models/ess_workforce.py:384-465`): rows per
  leave type with `allocated`, `taken`, `balance`, `low`; `pending` = requests in confirm/validate1. NOT
  year-bound. Door `/my/work/leave`.
- **Shifts**: `get_my_schedule(week_start)` (`ess_workforce.py:108-217`): two weeks from Monday, per week
  `days[]`, `acked`, `total`, `hours_label`, `pending`; top-level `pending`. Confirm = `ack_state`
  pending/acked (`models/shift_planning_ack.py:72-79`). Counter `work_shift_count` = `get_my_counters()
  ['shift_pending']` (`:553-580`, returns zeros when no employee). Door `/my/work/schedule`.
- **Timesheet**: `get_my_week(week_start)` (`ess_workforce.py:284-319`) → `pb.time.hub._person_week`
  (`pb_time_hub/models/time_hub.py:265-376`): per day `sched`, `actual`, `flags` (`missing` = planned shift, no
  attendance, day ≤ today), week totals `{sched, actual, entered, delta}`. Door `/my/work/timesheet`.
- **Overtime**: `get_my_overtime()` (`ess_workforce.py:510-550`) → `pending` count. Door `/my/work/overtime`.
- **Documents**: `pb.employee.document` (`pb_employee_vault/models/employee_document.py:52-97`): `expiry_date`
  (stored, indexed), `verified`, `expiry_state` (NOT stored: none/valid/soon(90 d)/expired — never in a domain).
  Hard dependency. Door `/my/documents`.
- **Profile requests**: states `draft/hr_review/approved/refused` (`models/pb_profile_change_request.py:87-91`).
- **Holidays**: `pb_holidays_next` is already set eagerly by pb_timeoff (`controllers/portal.py:45-71`) from
  `pb.holidays.next_one()` (`models/pb_holidays.py:453-465`, `{date, name, label, days_away}`).
- **Training / goals (optional facades)**: `pb.my.training.home()` → `overdue`, `due_soon` (`pb_training/models/
  pb_my_training_due.py:113-139`); `pb.my.goals.home_count()` (`pb_goals/models/pb_my_goals.py:111-122`).
- **Brand**: `ir.config_parameter biz_debrand.brand_name` → `company.name` → "My workspace" (`ess_hero`).
- **Greeting**: no Python helper exists; `pb_dashboard` has a JS one (cut-offs 12 and 18) — same cut-offs.
- **Learn**: no lesson, tour, anchor or practice replica points at `/my` (grep of `pb_learn` anchors/content/
  screens and `docs/tutorial_poc` on 2026-10-14: one sentence in a Home lesson mentions "My Payobook" as a
  landing, nothing describes the page). State this in every report.
- **Bench**: no local Odoo. Tests run on the server clone `p0clone` with a fresh stage dir (H35), detached run
  (H30 — read the `odoo.tests.result` line), admin OFF on the clone after any walk (H44). `p0clone` holds 6
  people and some payroll (H42) but no workforce rows — tests seed their own.

## Decisions (made 2026-10-14; raise only if a fact below turns out wrong)
- D1 The page is server-rendered QWeb + one small frontend Interaction (grouping, count-up). No OWL on the portal.
- D2 The other 15 modules are NOT edited. One override of `portal.portal_docs_entry` in pb_me_portal reads a
  registry keyed by URL (group, Lucide icon, colour, title/text overrides, "no tile" flag) and the Interaction
  moves tiles into their section. Unknown URL → "More" + a default icon.
- D3 Every live number is read softly (`'<model>' in self.env`, `'<field>' in Model._fields`); an absent source
  hides its card. pb_me_portal gains NO new dependency.
- D4 Money through the existing monetary widget; counts/dates as facts; words in the template (`_()`), VI in
  `i18n/vi_VN.po`.
- D5 "Next pay" shows only when the pay calendar has an upcoming row for the company (or shared); the sentence and
  the Pay footer degrade silently when it does not.
