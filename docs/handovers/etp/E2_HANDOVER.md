# ETP E2 — Business trips on My Payobook (handover for Opus)

Read first: `ETP_PROGRAM.md`, `ETP_LEDGER.md` (rules E-R1…E-R13, rows E6–E8 are yours), then the TIERS precedents
`../tiers/T3A_HANDOVER.md` + `T3A_REPORT.md` (pb_ask_hr: a glue module with a portal form, a My requests source, a
needs-you row, VI) and `../tiers/T3B_REPORT.md` §T3b.12 (clone run + tunnelled browser walk). Repo `CLAUDE.md`
applies. You do not deploy; Fable does. Plain words in every string a person can see. **Your clone is `p1clone`,
port 8098, staging `/tmp/deployE2`** (E-R7; set `web.base.url` on p1clone to `http://localhost:8098` before the
walk). Two sibling builds run at the same time on p0clone/p2clone — never touch their staging dirs, databases or
modules (`pb_me_expense`, `pb_me_project_time`) and never edit `pb_me_portal` (E-R1).

## What E2 is, in the owner's words
"Business trips … on the portal … premium and intuitive." After E2 every employee can **ask for a business trip
from My Payobook**, watch it move through its approvals, take it back before it is authorised, fix and resend a
refused one, and know what the trip pays (allowance, advance) and that attendance is automatic while away.

## Design (binding, E-R10)
Measured against TravelPerk / Navan's request flow. **Hero moment: the trip card writes itself.** The new-trip page
is a two-column desktop layout (one column stacked on a phone): on the left the questions in plain words — Where
(city + country, country first so the policy matches; a "Major city" toggle only when ledger E7 applies), When
(two dates; the number of days updates live: "3 days"), Why (purpose, one textarea), What it will cost (optional
estimate lines: category chips Lodging / Transport / Meals / Other, amount, note — add rows inline, remove with
one tap), Cash advance (optional amount with "Leave blank if you do not need money up front"). On the right a
**live trip card** that rewrites as you type: "Đà Nẵng, Vietnam · 12–14 Nov · 3 days · Allowance ₫150,000 × 3 =
₫450,000, paid with your salary · Advance ₫2,000,000 · Estimated ₫3,400,000". After sending, the same card is the
trip page's header and under it the **approval stepper** (Sent in → Their manager → Finance approver → HR lead →
Approved, the live names from the route; the current step pulses softly; a refusal shows the reason in the
person's words with "Fix and resend"). The list page `/my/trips` is a quiet board: strip ("1 waiting · next trip
in 6 days"), chips All / Waiting on you / With someone / Done, trip cards (destination, dates, days, status pill),
the next upcoming authorised trip first as a full-width card ("Your next trip · Đà Nẵng · in 6 days · attendance is
marked automatically"). Empty state: "No trips yet. When you need to travel for work, ask here and your manager
sees it at once." Zero dead-ends: overlap with another trip → the reason names the other trip; leave overlap →
a quiet warning line, not a block (ledger E8); approved trips cannot be cancelled here → "Ask HR to cancel an
authorised trip" with the link. Keyboard: Cmd/Ctrl+Enter sends; Enter in an estimate row adds the next row.

## Decisions already taken (do not re-open)
- **D1 No new model.** The portal creates and drives stock `pb.business.trip` and `pb.business.trip.line`
  under sudo after the ownership guard (E-R2), with these re-stated guards (ledger E6): the trip's `employee_id` is
  one of `_ess_own_employees()`; edits (fields and lines) only in `draft`; **send** only from `draft`; **take back**
  (`action_cancel`) only from `submitted / manager_approved / finance_approved`; **fix and resend** only from
  `refused` (`action_reset_to_draft` → edit → `action_submit`); `approved` and `cancelled` are read-only on the
  portal. Field whitelist on create/write: `destination_city, destination_country_id, date_from, date_to, purpose,
  policy_id, per_diem_rate, advance_amount, notes` + lines `(date, category_id, description, amount)`;
  `employee_id` = the session employee, `company_id` = the employee's company, `currency_id` = the policy's or the
  company's; `state`, `manager_id`, `name` never from the request.
- **D2 Policy**: `self.env['pb.trip.policy'].sudo()._match(country, company, tier)` — read its real signature at
  `pb_business_trip/models/pb_trip_policy.py:41-65`; the "Major city" toggle appears only when a tier-1 policy
  exists for that country + company (or global); the matched policy's rate and `per_diem_channel` feed the live card
  ("paid with your salary" for `payroll`, "claimed as an expense after the trip" for `expense`). The person never
  edits the rate (it is the policy's; stock locks it after draft anyway).
- **D3 Send** = `trip.sudo().action_submit()` — the shim takes over when the company has an active `trip` route
  (`_engine_managed`, `chain_shim.py:211-233`), else the fixed ladder runs; both work under sudo because `sudo()`
  keeps the uid (the submitter stays the employee). The portal shows the route steps from the request when one
  exists (`trip.approval_request_id` / its steps and seats — read how `approval_widget_json`
  (`pb_business_trip.py:117-130`) and the shim's stepper (`chain_shim.py:765-776`) name them) and the fixed-ladder
  names otherwise; a `blocked` request → "Nobody is set up to approve this yet. HR can fix the route." + Ask HR link
  when `'pb.ask.hr.ticket' in self.env`.
- **D4 Take back** = `trip.sudo().action_cancel()` (the shim withdraws the open request through the state write,
  `chain_shim.py:666-708`); verify in a test that the request is no longer `pending` afterwards. An inbox
  withdrawal that left the trip `submitted` (ledger E8 gap) is shown truthfully: the portal reads the request state
  first ("Taken back from Approvals") and offers "Fix and resend" only when the trip's own state allows it.
- **D5 Lines**: estimate lines are `pb.business.trip.line` rows; the portal never uploads receipts to lines (the
  bridge only turns receipted lines into expenses at approval time, which is a staff workflow). After the trip the
  person claims receipts through Expenses (E1's "Which trip" picker — nothing to build here; if `pb_me_expense` is
  installed on the clone, the trip page links "Claim receipts for this trip" → `/my/expenses/new?trip=<id>` and
  E1 reads `trip` — **only when `'pb.expense.claim' in self.env`**; otherwise the link is not drawn).
- **D6 What the trip pays**: `per_diem_total`, `estimated_total`, `advance_amount`, `duration_days` are the
  record's own computes — the live card's numbers must equal them after save (a test asserts it). Attendance
  sentence on an approved trip: "Your attendance is marked automatically for every trip day." (ledger E6 §6).
- **D7 Home**: tile `/my/trips` (registry has it — draw it with `portal_docs_entry` guarded `t-if="pbme_home"`,
  `placeholder_count` = trips waiting on the person); needs-you row (`act`: "1 trip request refused — fix and
  resend"); My requests source (`key='trip'`, model `pb.business.trip`, `date_field='date_from'`, states
  `draft→('Draft','off')`, `submitted→('Waiting approval','wait')`, `manager_approved→('With finance','wait')`,
  `finance_approved→('With HR','wait')`, `approved→('Authorised','ok')`, `refused→('Refused — your turn','act')`,
  `cancelled→('Taken back','off')`; title "Trip · Đà Nẵng · 12–14 Nov"); an extra home card `_pbme_extra_cards`
  ONLY when an authorised trip starts within 14 days ("Your next trip" card; nothing otherwise — quiet at zero).
- **D8 No backend change.** `pb_business_trip` is not edited; no ACL/rule rows (E-R2); nothing on the rail (T27).

## Scope (binding)
Module `pb_me_trip`: name "Employee Self-Service Portal — business trips", summary "Ask for a trip and follow its
approval, from My Payobook", depends `['pb_me_portal', 'pb_business_trip']`, `auto_install: True`, category
Hidden/Tools, version `19.0.1.0.0`, assets `web.assets_frontend` only (scss + `static/src/interactions/trip_form.js`:
live card, days count, estimate rows add/remove, Cmd+Enter; the no-JS path is the plain form with an "Add a line"
POST that re-renders).
Routes (`controllers/portal.py`, class extending `PbMePortal`): `GET /my/trips` (`?filter=`), `GET|POST /my/trips/new`
(`action=send|save`), `GET /my/trips/<int:id>`, `GET|POST /my/trips/<id>/edit` (draft only), `POST /my/trips/<id>/send`,
`POST /my/trips/<id>/withdraw`, `POST /my/trips/<id>/reopen` (refused → draft), `POST /my/trips/<id>/line/add`,
`POST /my/trips/<id>/line/<int:line>/remove`. Every POST: ownership guard → sudo → savepoint → redirect `?done=` /
re-render with the reason (`UserError` / `ValidationError` text shown as-is: they are already plain).
Facade `pb.me.trip` (AbstractModel): `own_trips(emp, bucket)`, `policy_for(emp, country_id, tier)`, `preview(values)`
(days, allowance, totals — pure, no write; the JS mirrors it), `new_trip(emp, values, lines)`, `update_trip(trip,
values, lines)`, `send(trip)`, `withdraw(trip)`, `reopen(trip)`, `status(trip)` → `{state, label, tone, steps:[{name,
state}], reason, can:{edit, send, withdraw, reopen}, attendance_sentence}`, `next_trip(emp)`.
Translations `i18n/vi_VN.po` (E-R9; the route step names "Their manager" / "Finance approver" / "HR lead" are
engine strings — translate them in YOUR .po with their real occurrence only if the engine's own .po lacks them;
otherwise leave them). Learn: E-R12.

## Tests (numbered; clone run E-R7; fixtures as T3a; the route: p1clone has company 5's active `trip` route —
assert on whichever companies your fixtures use, laying a route with the module's own `route()` helper if the test
company has none, as `pb_business_trip/tests/test_trip.py` and the shim's tests do)
- **E2.1** `preview` arithmetic = the record's computes after `new_trip` (days, per-diem total, estimated total).
- **E2.2** `new_trip` as `share_emp`: `employee_id` = their employee, `company_id`, `name` = `BT/…`, `create_uid` =
  the share user, lines created; `state` in values is ignored; a `date_to < date_from` → the plain reason, no trip.
- **E2.3** `policy_for`: Vietnam + tier1 → the 200k policy, Vietnam without tier → 150k, a country with no policy →
  the global one (or none) — and the live card words follow `per_diem_channel`.
- **E2.4** `send` → `submitted`; with a route: one `biz.approval.request`, submitter = the share user, steps named;
  decide as the manager → `manager_approved`, as finance → `finance_approved`, as HR lead → `approved`,
  `status()` says "Authorised" + the attendance sentence; refuse with a reason → `refused`, `status().reason` =
  the reason; `reopen` → draft; edit; `send` → attempt 2.
- **E2.5** overlap: a second trip over the same days → `send` refused with the reason naming the dates; a leave over
  the dates → `send` succeeds and `status()` carries the quiet warning (or the chatter note — assert what stock does).
- **E2.6** `withdraw` from `submitted` → `cancelled`, the request not `pending`; from `approved` → refused with the
  Ask HR sentence; `update_trip` on a `submitted` trip → refused.
- **E2.7** ownership: `plain`'s trip → `share_emp` cannot read it through the facade, `GET /my/trips/<id>` 404
  (styled), POSTs 404, never a write.
- **E2.8** HttpCase as `share_emp` AND `plain` (T-R6): list empty-state → new (country select, dates, purpose,
  estimate row) → POST `action=send` → redirect to the trip page `?done=sent` with the card numbers, the stepper and
  the pill; list card; home tile count; `/my/requests` row `wait` then `act` after refusal; the "Your next trip"
  card appears on `/my` only once a trip is approved and starts within 14 days.
- **E2.9** the D5 link: with `pb_me_expense` absent on p1clone the "Claim receipts" link is not drawn (assert).
- **E2.10** Existing suites green: `-i pb_me_trip -u pb_me_portal,pb_business_trip --test-tags
  /pb_me_trip,/pb_me_portal,/pb_business_trip`. Known clone artefacts: T31/T35, M19.
- **E2.11** PO gate; every word has a VI line for its own view.
- **E2.12** Browser walk on the staged clone (port 8098 tunnelled; temporary employee login archived after): phone
  390 px and desktop: new trip, watch the card rewrite, send, stepper; approve as the manager in the backend inbox
  (or refuse → reason → fix and resend); console clean; screenshots named.

## Non-goals (do not do)
- No receipts on trip lines, no itinerary/booking, no multi-destination, no editing after sending (take back →
  edit → resend), no cancelling an authorised trip, no edits to `pb_business_trip` / the bridges / `pb_me_portal`,
  no new fields on stock models, no sidebar item, no HR-side pages.

## Safety rails
- Every sudo write sits after the ownership guard; the trip id in the URL is re-checked; field whitelist (D1).
- `action_cancel` is reachable from the portal only in the three pre-authorisation states.
- A failure on any POST re-renders with the reason — never a traceback, never a bare 500.

## Report back (write `docs/handovers/etp/E2_REPORT.md`)
1. Files changed/added. 2. E2.1–E2.12 results with the clone log's summary lines and the browser walk. 3. Design
self-score (hero moment named). 4. Learn impact. 5. Decisions + proposed ledger rows. 6. Shared-module changes you
believe are needed (listed, not done). 7. Self-review per Scope and Non-goal item.
