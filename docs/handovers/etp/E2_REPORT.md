# ETP E2 — Business trips on My Payobook — implementation report (Opus)

Handover: `E2_HANDOVER.md`. Ledger: `ETP_LEDGER.md`. Not committed, not deployed.
Clone: `p1clone`, port 8098, staged from a clean `/tmp/deployE2` (`pb_me_trip` + `pb_me_portal` 19.0.3.4.0 from the repo;
`pb_business_trip` and `pb_ask_hr` were hash-checked identical to the server copies and NOT staged). Final runs
2026-10-16 00:19–00:22 (full) and 00:23–00:24 (module, after the last test was added) server time.
`pb_me_portal`, `pb_business_trip`, the trip bridges, `pb_me_expense` and `pb_me_project_time` were not edited.

## 1. Files added (all new; no existing file changed)

| File | What |
|---|---|
| `pb_me_trip/__manifest__.py` | "Employee Self-Service Portal — business trips", summary "Ask for a trip and follow its approval, from My Payobook", depends `pb_me_portal, pb_business_trip`, auto_install, Hidden/Tools, 19.0.1.0.0, frontend assets only. |
| `pb_me_trip/models/me_trip.py` | Facade `pb.me.trip` (AbstractModel): guards `_own_emp` / `_own` / `get_trip` (employee.user_id == uid), `policy_for`, `policy_map` (the live card's facts), `preview` (pure arithmetic = the record's computes), `new_trip` / `update_trip` / `add_line` / `remove_line` with the D1 whitelist, `send` (friendly overlap check, then stock `action_submit`), `withdraw` (`action_cancel`, three states only), `reopen` (`action_reset_to_draft`), `status` (label/tone/bucket, route stepper or fixed ladder, refusal/return reason + who, blocked reason, `can`, attendance sentence, leave overlap), `card`, `lines`, `own_trips`, `next_trip`, `waiting_on_me`, `copy_values`, `route_preview`. |
| `pb_me_trip/models/pb_me_home.py` | Home hooks: needs-you rows `trip_refused` ("1 trip request refused — fix and resend") and `trip_returned`; My requests source `trip` with the exact D7 states/tones and title "Trip · Đà Nẵng · 12–14 Nov"; extra card "Your next trip" only when an authorised trip is under way or starts within 14 days. |
| `pb_me_trip/controllers/portal.py` | `PbMeTripPortal(PbMePortal)`: all routes of the handover + `trip_count` counter; ownership guard → facade → savepoint → `?done=` redirect or the same page with the reason; styled 404 for another person's trip on GET and POST; no-JS `refresh` / `add_line` / `remove_line:<n>` re-render paths; `/my/trips/new?copy=<id>` ("Ask again with these details"). |
| `pb_me_trip/views/portal_templates.xml` | Breadcrumbs, home tile, own icon set (`trip_icon`, E12), pill, toast, error line, the trip card (live + static), stepper, board, cost row, form, trip page, 404, home "Your next trip" card. |
| `pb_me_trip/static/src/scss/me_trip.scss` | `.pbtr-*` layer on the pbme kit; phone layout; reduced-motion block. |
| `pb_me_trip/static/src/interactions/trip_form.js` | Live card (no words in JS), Major-city switch visibility, add/remove rows, Enter adds a row, Ctrl/Cmd+Enter sends, Enter never sends by accident, double-submit lock, `done` cleaned from the address bar, arrow/j/k on the board. |
| `pb_me_trip/i18n/vi_VN.po` | 187 entries built from the clone's own export (`odoo-bin i18n export`), three rules each. |
| `pb_me_trip/tests/test_me_trip.py`, `test_po_gate.py`, `__init__.py` | E2.1–E2.9, E2.11 (+ D7 hooks, blocked route, inbox withdrawal). |

## 2. Test results

Final full run (`-u pb_me_trip,pb_me_portal,pb_business_trip --test-tags /pb_me_trip,/pb_me_portal,/pb_business_trip`):
```
odoo.tests.stats: pb_business_trip: 15 tests 16.73s 2022 queries
odoo.tests.stats: pb_me_portal: 125 tests 98.73s 33744 queries
odoo.tests.stats: pb_me_trip: 26 tests 32.31s 11769 queries
odoo.tests.result: 1 failed, 9 error(s) of 126 tests when loading database 'p1clone'
ERROR x8: TestBusinessTrip.test_01/02/03/04/05/06/07/12            <- clone data, not E2 (below)
FAIL:     TestMeHome.test_02_tile_meta_default_and_hidden          <- pb_me_portal pre-work pin (below)
ERROR:    TestPbMePortal.test_01_profile_change_flow_and_audit     <- known M19
```
Module re-run after the last test was added (`-u pb_me_trip --test-tags /pb_me_trip`):
`pb_me_trip: 27 tests … odoo.tests.result: 0 failed, 0 error(s) of 21 tests`, `EXIT=0`. No warning from pb_me_trip.

**The 8 `pb_business_trip` errors are not caused by E2.** They all fail at "No step is waiting for a decision on this
one." The stock tests date their trips 11–13 Aug 2026; on p1clone the trip route's Finance approver and HR lead
responsibilities (rows 2 and 5, platform.recovery) start on 2026-09-15, and the engine only accepts a holder whose dates
cover the request date (`biz_approval_workflow/models/responsibility.py:116` `_covers(on_date)`; the trip's request date is
`date_from`). So every stock test request is blocked before its first step opens. Reproduced in a rolled-back shell on
p1clone: request `blocked`, "Nobody holds "Finance approver" for My Company yet." The failing path (`action_submit` →
engine) never touches pb_me_trip (it inherits no trip method). These tests were written for the fixed ladder and fail on
any database whose trip route is live with holders seeded after August.

**`TestMeHome.test_02` is pb_me_portal's own pin**: 19.0.3.4.0 added `/my/expenses` to the Me group
(`pb_me_home.py:107`) but `tests/test_me_home.py:68-70` still pins the Me order without it. One-line test fix, listed in §6.

| # | Test(s) | Result |
|---|---|---|
| E2.1 | `test_e2_1_preview_equals_the_record` | pass. `preview` days 3 / rate / allowance / lines / estimated / advance = the record's `duration_days`, `per_diem_total`, `estimated_total`; the card's formatted money = `fmt_money` of the record. |
| E2.2 | `test_e2_2_new_trip_as_an_employee_login` | pass. Employee login creates: own employee, employee's company, `BT/2026/…`, `create_uid` = the login, 2 lines (empty row dropped), `state` draft despite `state='approved'`, forged `employee_id`/`manager_id`/`name`/`per_diem_rate`/`company_id` ignored; end before start → "The trip cannot end before it starts. Check the two dates.", no trip; missing purpose/city/country and a line without an amount refused with plain words; another person's employee → AccessError. |
| E2.3 | `test_e2_3_policy_for_and_the_card_words` | pass. VN + tier1 = `policy_vn_tier1` 200,000; VN = `policy_vn_other` 150,000 (payroll); Antarctica = `_match` fallback (none on p1clone → rate 0, channel none, company currency), tier ignored where no tier-1 exists; a FR `expense` policy → card says "Claimed as an expense after the trip" and not "Paid with your salary", VN trip the reverse; `policy_map` carries the same answers. |
| E2.4 | `test_e2_4_send_route_authorised`, `_4b_refuse_fix_and_resend`, `_4c_fixed_ladder_without_a_route`, `_4d_a_blocked_route_says_so` | pass. Draft shows "who will be asked"; send → `submitted`, ONE request, `submitter_uid` = employee login, seats manager / finance / HR lead; steps named from the route + the manager's name, "Waiting approval"; manager → `manager_approved` ("With finance"), finance → `finance_approved` ("With HR"), HR lead → `approved`, "Authorised" + the attendance sentence, all steps done. Refuse with reason → `refused`, "Refused — your turn", reason + who, stopped on the manager step; edit refused → UserError; reopen → draft; edit; send → attempt 2 pending. No route → fixed-ladder names with the manager's name. Blocked route → "Nobody to approve yet", block reason, take back works. |
| E2.5 | `test_e2_5_overlaps` | pass. Second trip over the same days → refused naming "Đà Nẵng" and "9–11 Mar", stays draft. Approved leave over the days → send succeeds, `status()['leave_overlap']` = the leave type, and stock's chatter note is still posted. |
| E2.6 | `test_e2_6_take_back`, `_6b_withdrawn_in_the_inbox_is_shown_truthfully` | pass. Withdraw from submitted → `cancelled`, request `cancelled` (not pending), "Taken back"; second withdraw refused; edit of a submitted trip refused; withdraw of an authorised trip → "…Ask HR to cancel it.", stays approved. Inbox withdrawal (`engine.cancel`) leaves the trip submitted → page says "Taken back from Approvals" and offers Fix and resend. |
| E2.7 | `test_e2_7_ownership`, `test_e2_7_routes_are_404_for_another_persons_trip` | pass. Facade: status/card None, lines [], `get_trip` empty, every write AccessError, nothing changed, not in the list; employee login has no ACL on trips and no portal ACL row exists. Routes: GET page/edit 404 styled (no destination leaked), POST send/withdraw/reopen/edit/line add/line remove 404, nothing written; unknown id 404. |
| E2.8 | `test_e2_8_flow_for_an_employee_login`, `_8b_flow_for_a_full_account`, `_8c_home_tile_in_time`, `_8d_line_routes_and_errors` | pass, both kinds of login. Empty state words → form fields drawn → no-script "Add a line" redraws with 2 rows and writes nothing → bad dates re-render with the reason, nothing created → POST send (forged employee/state ignored) → `/my/trips/<id>?done=sent`, the record's three amounts, stepper with the current step, "Waiting approval", toast, the manager's name, "Paid with your salary" → board card `is-wait` → `trip_count` 0 → My requests `wait` row → refuse → page reason + "Fix and resend", `trip_count` 1, My requests `act`, `/my` "1 trip request refused — fix and resend", no next-trip card → reopen → edit form → resend → attempt 2 → take back → "Ask again with these details" → a trip in 6 days: no card while waiting, card "Your next trip … in 6 days" on `/my` once authorised, authorised page with the attendance sentence and "Ask HR to cancel an authorised trip", board hero. Tile sits in Time. Line add/remove routes, negative amount refused, overlap on `/send` shown on the trip page. |
| E2.9 | inside E2.8 | pass. `pb.expense.claim` absent on p1clone → no "Claim receipts for this trip", no `/my/expenses/new` link (the test asserts the link instead when the model exists). |
| E2.10 | the run above | pb_me_trip green; pb_me_portal 125 green except M19 and the pre-work pin; pb_business_trip errors are clone data (above). |
| E2.11 | `TestTripPoGate` (4 tests) + server parse gate | pass. Server `PoFileReader`: 206 rows. Every entry: module line, occurrence, `odoo-python` for code, msgstr, no vendor name; every page word has a VI line for its own view; every `_()`/`_lt()` literal has one. Live: `/vi/my/trips/<id>` and `/vi/my/trips/new` fully Vietnamese (route step names from the engine's own file: "Quản lý của họ", "Người duyệt tài chính", "Trưởng nhân sự"). |
| D7 | `test_e2_d7_home_hooks` | pass. My requests row/label/tone/url/title; needs-you row; extra card absent at zero, absent while waiting, present (in 6 days) once authorised, the nearest within 14 days wins. |
| E2.12 | browser walk | done, below. |

### E2.12 — browser walk (clone, staged code, port 8098 local-only, tunnelled)
Own headless Chrome over DevTools (the Chrome MCP browser was not used, ledger T26). Temporary logins on p1clone:
`e2.ui.employee@example.com` (employee login, portal), `e2.ui.manager@example.com` (their manager, internal),
`e2.ui.finance@example.com` and `e2.ui.hrlead@example.com` (seated as the trip route's Finance approver / HR lead for the
walk; the clone's own rows 2 and 5 were deactivated and are now reactivated, mine archived). All four logins are
**archived with scrambled passwords**; the UI server is stopped and the tunnel closed.

Employee: `/my` → Business trips tile in Time → `/my/trips` empty state → New: country Vietnam (the Major-city switch
appears), Đà Nẵng, dates, purpose, a Lodging line, **Enter added the next line with focus in its amount**, a Transport
line, Add a line + remove (row animates out), advance; the card rewrote at every step (allowance 150,000 ₫ × 3 =
450,000 ₫; Major city on → 200,000 ₫ × 3; estimated 3,400,000 ₫; advance 2,000,000 ₫; all five section numbers turned
solid); phone 390 px with no sideways scroll; **Ctrl+Enter sent it** → trip page: toast, "Waiting approval", stepper
Sent in ✓ → Their manager (Long E2 Manager, pulsing) → Finance approver → HR lead → Approved, "Waiting for Long E2 Manager
(Their manager). You can take it back until it is authorised.", address bar cleaned; take back (two-step "Yes, take it
back") → "Taken back"; My requests shows both rows.
Manager in the backend **Approvals inbox** (`/bizapp/action-993`): the card "Trip · Thu E2 Walk · Đà Nẵng · Your turn" →
drawer → **Turn down** with "Please go the week after: the client team is away that week." → trip refused.
Employee: `/my` top line "Your trip request was refused. Fix it and send it again." + needs-you row; trip page "Refused by
Long E2 Manager." with the reason quoted, stopped on Their manager (phone too) → **Fix and resend** → form prefilled, toast,
dates moved a week (card: 29–31 Oct) → sent → "Waiting approval".
Manager, then finance, then HR lead each pressed **Approve** in their own inbox → trip `approved`.
Employee: "Authorised. Have a good trip. Your attendance is marked automatically for every trip day.", all steps done,
"Ask HR to cancel an authorised trip", no receipts link (expenses module absent); `/my` shows the **Your next trip** card
("Đà Nẵng, Vietnam · in 13 days · 29–31 Oct · 3 days · Attendance is marked automatically"); board strip "0 waiting on you ·
0 with someone · next trip in 13 days" + the dark hero card; arrow key moved between cards; Vietnamese pages; styled 404.
Console: nothing from these pages. Seen and not ours: the website logo 500 (clone filestore, every page, known since T2) and
pb_learn's "translations have not been loaded" warning in the backend (known).
Defects the walk found and fixed: the script's date range read "25–Nov 27" in English (now built from the day and month
parts like the server's "25–27 Nov"); the "·" before "3 days" was lost when the hidden placeholder sat between the two
spans. A JS/SCSS change needed the clone's `/web/assets/%` attachments purged and the UI server restarted (CLAUDE.md step 6).
The route was not blocked on the walk (the near-term dates are covered by the holders), so the blocked state is covered by
`test_e2_4d` rather than a screenshot.
Screenshots (42): scratchpad `e2walk/shots/` (not versioned) — `01`–`11` employee (desktop/phone, the `-blocked` files are
the first trip, not actually blocked), `20`–`23` inbox, `30`–`35` refusal/fix/resend/VI, `40`–`44` authorised/home/board.

## 3. Design self-score
- **Hero moment — the trip card writes itself.** Two columns (questions left, sticky card right; one column on a phone,
  card before the buttons): every keystroke rewrites destination, dates, "3 days", the allowance sum ("150,000 ₫ × 3 =
  450,000 ₫ · Paid with your salary"), other costs, the estimated total and the advance (amber row), and each changed
  value glows once; the plane badge straightens while you type. After sending, the same card (bigger) is the trip page's
  header with the pill, and under it the approval stepper with the live names, the waiting step pulsing softly.
- **Zero dead-ends.** Empty board, empty filter, every refusal (dates, purpose, city, country, amounts, overlap naming the
  other trip, edit after sending, take back an authorised trip → Ask HR), refused / sent back (reason + who + Fix and
  resend), blocked route (sentence + Ask HR + take back), inbox withdrawal (said truthfully, Fix and resend), taken back
  (Ask again with these details, prefilled), leave overlap (quiet line, never a block), authorised (attendance sentence,
  Ask HR to cancel), styled 404. Every page works without the script.
- **Plain words** throughout; no product or vendor name in a new string. **Motion with purpose**: value glow, row in/out,
  pill pop on change, toast, step pulse, card lift; all off under reduced motion.
- **Keyboard**: Ctrl/Cmd+Enter sends, Enter in a line adds the next, Enter elsewhere never sends, double-submit lock,
  arrow/j/k on the board, real radios/checkbox for chips and the switch.
- Self-score **8.5/10**. Short of 10: no city autocomplete (a free text field with the country first); the inbox
  decision is not reflected live (the page updates on reload); on a phone the card sits below the questions rather than in
  a sticky mini-bar.

## 4. Learn impact
Grepped `learn_content.json`, `anchors.json`, `engine/screens.js`, `engine/fixture.js`: the only trip mentions are the
backend Time hub's "Trips" tab and the approval-route fixture; no lesson describes the employee home's tiles or `/my`
trips. **Nothing in Learn is affected.**

## 5. Decisions the handover did not make + proposed ledger rows
1. **Bucket for a draft on the board is "Waiting on you"** (it is not sent yet); My requests keeps D7's quiet `off`.
2. **Status words beyond the stock states**: "Sent back — your turn" (draft whose latest request was returned), "Nobody to
   approve yet" (request blocked), "Taken back from Approvals" (inbox withdrawal). The pill reads the request on top of the
   trip state only when that request is the story of the current state (an old finished request is ignored).
3. **Fix and resend also from an inbox withdrawal** while the trip still says `submitted` (stock's reset allows it); not
   from `manager_approved`/`finance_approved` (stock refuses) — there the page offers take back + "Ask again with these
   details".
4. **Friendly overlap check before stock's guard**, naming the other trip's destination and dates; stock's guard stays the
   backstop. The handover's "reason naming the dates" is met by both.
5. **Route step names in Vietnamese come from the engine's own .po** (`code_translations` of `biz_approval_workflow`), not
   repeated in this module's file, as the handover allows.
6. **City and country are both required** (the card needs both; the country decides the policy).
7. **Lines are replaced as a whole on edit**; their date is the trip's first day (never from the request).
8. **"Ask again with these details"** (`/my/trips/new?copy=<id>`) on a taken-back or refused trip — a small addition for
   zero dead-ends; it prefills the form and writes nothing.
9. **Needs-you also has a "sent back" row** (amber) next to the spec's "refused" row (rose); the home tile's count is both.
10. **The home card also shows a trip already under way** ("under way, until 14 Nov"), still only for authorised trips.

Proposed ledger rows:

| # | Gotcha / fact | How to apply |
|---|---|---|
| E14 | A route seat is a READ only (`trip_rule_seat`). When a seated person decides, the shim writes the trip's new status AS THAT PERSON (`chain_shim.py:474` `_approval_advance` → `_chain_engine_write`); a holder without a write-capable trip group (payroll manager / HR manager / attendance officer) gets "could not follow its own route": the decision stands, the trip stays one state behind. | Seat Finance approver / HR lead with people in those groups (the default seed does); tests give fixtures the real groups. Shim-side fix listed in §6. |
| E15 | The engine accepts a responsibility holder only when its dates cover the REQUEST date (`responsibility.py:116`), and a trip's request date is its `date_from`. On p1clone the holders start 2026-09-15, so stock `pb_business_trip` tests (August 2026 trips) all block. | Known clone/data errors for `TestBusinessTrip.test_01–07, 12`; do not chase in a phase run. |
| E16 | `pb_me_portal` 19.0.3.4.0's `TestMeHome.test_02_tile_meta_default_and_hidden` pins the Me order without `/my/expenses`. | Fix the pin in pb_me_portal (one line). |
| E17 | QWeb term grouping merges an empty inline `<span/>` with the next inline text (the switch's knob span swallowed its label into one term with indentation). | Put label text in its own block (`div`) next to purely decorative spans. |
| E18 | `Intl.DateTimeFormat` puts the month first in en-US; compacting "12–14" from its output gives "12–Nov 14". | Build "d MMM" from `formatToParts` to mirror babel's `d MMM`. |

## 6. Shared-module changes I believe are needed (listed, not done)
1. **pb_me_portal** `tests/test_me_home.py:68-70`: add `'/my/expenses'` to the pinned Me order (19.0.3.4.0 pre-work).
2. **biz_approval_workflow** `chain_shim.py` `_approval_advance` / `_approval_apply` / `_approval_reject`: write the
   consumer's status with `sudo()` (the engine has already checked the seat), so a correctly seated decider without a trip
   write group cannot leave the trip a state behind (E14). Not needed for E2 to work with the default seeds.
3. **biz_approval_workflow** (ledger E8, still open): mirror an inbox withdrawal on the record (`_approval_withdraw` in the
   shim). E2 shows the case truthfully meanwhile.
4. **Before deploy (data, not code)**: on p1clone the trip route's holders exist but start 2026-09-15 — fine for new trips;
   worth checking on payobook that Finance approver and HR lead are held by real people (on p1clone both are the platform
   recovery account).

## 7. Self-review
**Scope**
- Module, manifest, auto-install, frontend assets only: done.
- Routes (list + filter, new GET/POST send|save, page, edit GET/POST draft only, send, withdraw, reopen, line add, line
  remove), guard → sudo → savepoint → redirect / re-render with reason: done (+ `copy`, no-JS re-render actions).
- Facade methods `own_trips, policy_for, preview, new_trip, update_trip, send, withdraw, reopen, status, next_trip`: done
  (status adds `key`, `bucket`, `current`, `block_reason`, `leave_overlap`).
- D1 whitelist and re-stated guards; D2 policy + tier-1 switch + channel words; D3 send via `action_submit`, route names /
  ladder names, blocked sentence + Ask HR when installed; D4 take back + request withdrawn (tested) + inbox withdrawal
  shown truthfully; D5 no receipts on lines, claim link only with `pb.expense.claim`; D6 record computes = card (tested),
  attendance sentence; D7 tile, needs-you, My requests source, next-trip card quiet at zero; D8 no backend change: done.
- Design bar (hero card, stepper, quiet board, empty state words, keyboard): done; deviations in §3.
- Translations (three rules, export-built, parse gate, per-view coverage): done. Learn: checked, nothing affected.
- Tests E2.1–E2.12: done; only pre-existing clone failures outside the module remain (§2).

**Non-goals**: no receipts on lines, no itinerary/booking, no multi-destination, no editing after sending (take back →
edit → resend), no cancelling an authorised trip, no edits to pb_business_trip / bridges / pb_me_portal, no new fields on
stock models, no sidebar item, no HR-side pages, no portal ACL rows: all respected.

**Safety rails**: every sudo write sits behind the route's `_ess_own_employees` guard AND the facade's uid guard; the trip
id is re-checked on every route; whitelist enforced (forged fields tested); `action_cancel` only from the three waiting
states; every refusal re-renders with the reason (tested for create, edit, send, line add); no 500 seen in the walk.

**Side effects on the clone only**: p1clone has pb_me_trip 19.0.1.0.0 installed and pb_me_portal 19.0.3.4.0 upgraded,
`web.base.url` = `http://localhost:8098`, the `/web/assets/%` attachments regenerated, trips BT/2026/0120 (taken back) and
BT/2026/0121 (authorised, 29–31 Oct) for the archived walk employee, two archived temporary responsibility rows
(3555, 3556; the clone's own rows 2 and 5 active again). Live service, port 8069 and every live database untouched.
