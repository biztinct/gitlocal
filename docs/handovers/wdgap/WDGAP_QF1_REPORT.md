# WDGAP QF1 — report: approve several at once; PayAI's daily alerts on Home

Branch `wdgap-qf1` (from `origin/19.1` at `1065e98bf`). Built, tested and self-reviewed in
its own worktree. **Not merged, not deployed.**

## 1. What was built

### A. "Approve selected" in the one Approvals inbox
- **Which kinds may be approved together** — new field on the approval catalogue row
  `biz.approval.process.bulk_ok` ("Can be approved several at once"), with a constraint that
  refuses it on any `money` process (plain sentence). Defaults are set ONCE (see §4).
- **Every card says whether it can be ticked** — `_card()` gains `can_bulk`, `bulk_why`
  (short plain reason, the tooltip on a greyed box) and `lock_revision`. The answer is
  `_can_bulk(request)`: my turn, waiting and not stuck, kind allows it, not a money kind,
  and I am not too close to it under the route's independence safeguard (`_conflict_kind`).
- **Server verb** `pb.approval.inbox.decide_many(request_ids, revisions=None)` — approve only,
  max 50 ids (plain refusal above), ids de-duplicated. Per id, in its own savepoint: re-asks
  `_can_bulk`, then calls the SAME `biz.approval.engine.decide` the drawer's Approve uses, as
  the current user, `exception_grant_id=None`, with `expected_lock_revision` = the revision the
  card showed and idempotency key `bulk-<uid>-<request>-<step>-<revision>`. A request left
  `approved` with a `block_reason` counts as not done (approval stands, as `act()` did).
  Returns `{results:[{id, ok, title, error}], done, failed}`; clears the per-request "my turn"
  cache before returning.
- **Screen** (`inbox.js/.xml/.scss`): a tick-box column in front of every card when any card
  is my turn; a box on each of MY cards (greyed with its reason when it cannot go with
  others; no box on other people's cards); "Select all on this page that I can approve (n)"
  with the note "Send back and turn down stay one at a time: each needs its own reason.";
  sticky tray "3 of 4 selected · Approve selected · Clear"; in-page confirm "Approve 3
  requests?" with the count per kind ("3 Leave") and Cancel / Approve 3; toast "3 approved.";
  a calm results panel listing each request that could not be approved with the engine's own
  sentence (those stay ticked). The box never opens the drawer. Keyboard: cards are focusable;
  Space ticks the focused card, Enter opens it; Escape (capture phase, never swallowed) closes
  the confirm, then the results panel, then clears the selection — only when no drawer is open.

### B. PayAI's daily alerts on Home
- `payroll.ai.pulse` gains `company_id` (indexed), `dedupe_key`, `direction`, `ack_level`,
  `ack_severity`; a global record rule "PayAI alerts: own companies only"
  (`company_id = False or in company_ids` — old rows stay where they were).
- The daily job runs the four detectors ONCE PER COMPANY that has people, each reading that
  company's payslips / people / leave only (`hr.payslip.company_id`, `hr.employee.company_id`,
  `hr.leave.employee_company_id`; overtime's department lookup also limited to the company),
  each detector in its own savepoint. Thresholds unchanged.
- One open alert per thing: key `<company>:<kind>[.<joined|left>]:<department|none>`. Still
  true → the open alert's figures, title and date are refreshed (no new row). Gone → the
  alert is resolved on that run (only for detectors that ran cleanly). "Got it" stores how bad
  it was; the alert comes back only when it is 5 points worse (percent for cost/overtime,
  count for people/leave) or its severity rises.
- `home_alerts(limit=3)` — the reader Home uses: open, not acknowledged, `company_id in
  env.companies`, never an old row without company, most severe first then newest (sorted in
  Python), only `{id, category, severity, direction, pct, value, baseline, department, since}`
  — no title, no summary, no `details` (names). Nothing for a reader who cannot open payslips.
- Home: section `payai_noticed` in `get_home_data()` read only through
  `optional('payroll.ai.pulse', …)` (registered in `HOME_MODELS`, `TOP_KEYS`, timing `payai`).
  `None` when PayAI is absent, the reader cannot open payslips/alerts, or nothing is open. Each
  alert carries `door` (a key) only when every action that door needs exists.
- Card "PayAI noticed" in the row of cards: a dot (grey for information, amber, rose), the
  sentence built in the browser from a word table (translated), "First noticed 14 Nov", a quiet
  "Look closer" and "Got it" (removes the line at once). The row icon is made once in `setup()`.

### Files and versions
| Module | Version | Files |
|---|---|---|
| `biz_approval_workflow` | 19.0.1.7.1 → **19.0.1.8.0** | `models/process.py`, `migrations/19.0.1.8.0/post-bulk_ok_defaults.py`, `i18n/vi_VN.po`, `i18n/id_ID.po` |
| `pb_approval_config` | 19.0.1.8.0 → **19.0.1.9.0** | `models/inbox_facade.py`, `static/src/js/inbox.js`, `static/src/xml/inbox.xml`, `static/src/scss/inbox.scss`, `i18n/vi_VN.po`, `i18n/pb_approval_config.pot` (fresh export), `tests/test_wdgap_qf1_bulk.py` |
| `pb_payroll_ai_insights` | 19.0.3.12.4 → **19.0.3.13.0** | `models/payroll_ai_pulse.py`, `security/payroll_ai_security.xml`, `i18n/vi_VN.po`, `tests/test_wdgap_qf1_pulse.py` |
| `pb_dashboard` | 19.0.2.2.8 → **19.0.2.3.0** | `models/home_data.py`, `static/src/js/pb_dashboard.js`, `static/src/xml/pb_dashboard.xml`, `static/src/scss/pb_dashboard.scss`, `i18n/vi_VN.po`, `i18n/pb_dashboard.pot` (fresh export), `tests/test_wdgap_qf1_home.py`, `tests/test_home_data.py` + `tests/test_activation.py` (new key / model registered) |

## 2. Tests

Local runtime, isolated tree (this worktree first after the platform addons), copy of
`upd_p6_t_tpl`, `-u biz_approval_workflow,pb_approval_config,pb_payroll_ai_insights,pb_dashboard,pb_timeoff,pb_hr_workforce,pb_clock` (G35, G97).

| # | Case | Result |
|---|---|---|
| 1 | `_card()` can_bulk true for my-turn; false + reason for not my turn, stuck, money, kind one-at-a-time, I sent it in under independence | PASS (`test_01`) |
| 2 | `bulk_ok` refused on a money process (write and create); default never lands on money | PASS (`test_02`) |
| 3 | Defaults match A3 (11 kinds on; payrun, bankfile, release, records, resign, verdict, newhire, contract, paychange, bankchange, scheme, roles, expense, hiring_request, hiring_offer and every money kind off); marker set; a customer turning leave OFF survives a second seeding AND a re-run of the migration; a kind born later gets its default | PASS (`test_03`); upgrade log: "several-at-once switched on for [correction, goal_change, goal_set, hr_comm_post, leave, letters, overtime, recognition, timesheet, training_request, trip]" |
| 4 | 3 bulk vs 3 single decides: same state, step statuses and seats; decisions by the presser, no exception, idempotency key set | PASS (`test_04`) |
| 5 | Mixed batch (eligible, money, already decided, someone else's) → 1 ok, 3 failed with plain reasons, nothing else changed | PASS (`test_05`) |
| 6 | A row "someone else is deciding" (NOWAIT path simulated: a real failed statement inside the transaction + the engine's sentence) fails alone; the other two approved | PASS (`test_06`) |
| 7 | Same call twice (with and without revisions) approves nothing new; same id three times decided once; a card changed since it was read is refused | PASS (`test_07`, `test_07b`) |
| 8 | 52 ids refused; wrong argument refused; a person with no seat and the submitter get failures only, no decision | PASS (`test_08`) |
| 9 | "My turn" recount in the same request is fresh | PASS (`test_09`) |
| 10 | Existing suites — see below | see below |
| 11 | Two companies, cost jump in one (real payslips with lines) → one alert with that company; the other company's reader sees nothing (Home and search); no payslip right → nothing | PASS (`test_11`) |
| 12 | Detector twice → one open alert; figures updated; "Got it" hides it; +3 points stays hidden, +5 points comes back; severity rise brings it back under 5 points; condition gone → resolved; old rows untouched | PASS (`test_12`, `test_12b`) |
| 13 | Home order critical > warning > info, max 3, exact keys only, no names, old/resolved/acknowledged rows never returned | PASS (`test_13`) |
| 14 | Home payload: card with an open alert (door key present), `None` when nothing open, `None` without payslip right, `None` without PayAI (simulated `optional`), a broken PayAI never blanks Home; JS word table ⇄ server kinds; doors ⇄ server xmlids; no new dependency on PayAI or `pb_learn`; no icon made inside the row loop | PASS (`test_14a`–`14g`) |
| 15 | Browser walk, local copy, INSIDE the Home hub (Claude in Chrome, G99) | PASS — see §2.2 |
| 16 | Static gates: py_compile (10 files), XML parse (3), PO gate, diff grep for the vendor name | PASS — see §2.3 |

QF1's own: **21 tests, 0 failed** (pb_approval_config 10, pb_payroll_ai_insights 4, pb_dashboard 7).

### 2.1 Full suites (case 10, 14)
Full suites of `biz_approval_workflow`, `pb_approval_config` (incl. `test_static_contract`,
`test_vietnamese`), `pb_payroll_ai_insights`, `pb_dashboard` (incl. `test_home_data`,
`test_home_front`, `test_home_cards`, `test_activation`), and the two adapters `pb_timeoff`
and `pb_hr_workforce`, all `-u` (G35): **558 tests, 5 failed, 11 errors — every one
pre-existing / environment, none in QF1 code.** Baseline: the same suites with the four QF1
modules taken from `origin/19.1` (materialised outside the repo and placed first in the
addons path), same template: 541 tests, 3 failed, 13 errors — the same failures.

| Failing test | QF1 tree | `origin/19.1` | Cause |
|---|---|---|---|
| `pb_timeoff` 8 (`test_leave_rules` ×6, `test_timeoff` 03/05) | error | error | the template's `admin` is archived: "Your account is no longer in use" (W4) |
| `pb_hr_workforce` `test_weekentry.test_06` | error | error | "the week of 20 Jul … is with the approver" — pay-close freeze in the template data |
| `pb_approval_config` `test_inbox_facade.u10_an_arranged_exception…` | error | error | known on the template shape (UPDATES P6 M6) |
| `pb_approval_config` colour contract | fail | error* | `inbox.scss:74 #F8F9FC`, an old line (UPDATES P6 M6); QF1 adds no colour |
| `pb_approval_config` `test_u13_…whole_exported_template` | fail | fail | 70 old English strings (P6 M6 counted 71; one has since left the template). Every QF1 string is translated |
| `pb_approval_config` `TestP7Vietnamese` z06d / z06e | fail | (z06c fails first*) | other modules' Phase-7 Vietnamese and a placeholder in `pb_comp_ben` (P6 M6) |
| `pb_payroll_ai_insights` `test_egress.test_04e` | fail | fail | the voice consent sentence is no longer in the catalogue (the consent card was removed by owner ruling 2026-10-15) |

\* In the baseline run those source tests read sibling folders by relative path and the
baseline copy lives outside the repo, so a few of them stop one step earlier (two icon checks
error there too). In the QF1 tree they run normally.

Per module (QF1 tree): biz_approval_workflow 89, pb_approval_config 184, pb_payroll_ai_insights
152, pb_dashboard 86, pb_timeoff 123, pb_hr_workforce 54.

### 2.2 Browser walk (local `qf1_a`, port 8591, jobs off)
Fixture (local, disposable): 4 leave requests waiting on the walker's "Their manager" seat
(DEMO people), one "Other request" moved onto a money process, four PayAI alerts.
- **Approvals lens (Home › INBOX):** money card shows a greyed box, tooltip "Money leaves the
  company with this one, so it is approved on its own."; the 4 leave cards have boxes; "Select
  all on this page that I can approve (4)". Ticked two with the mouse and one with Space on the
  focused card — the drawer never opened. Tray "3 of 4 selected"; confirm "Approve 3
  requests? · 3 Leave"; Approve 3 → toast "3 approved.", My turn 5 → 2, the three leaves are
  `validate` in the database with keys `bulk-2-<id>-mgr-1`. Then a request changed behind the
  screen (lock revision bumped) → results panel "1 request could not be approved · … This
  request changed while you were looking at it. Reload to see the latest." and it stayed
  ticked. Escape closed the panel, a second Escape cleared the selection.
- **Pulse lens:** card "PayAI noticed · 3 things worth a look": "Overtime in Administration is
  up 32%" (rose), "12 leave requests approved in 7 days" (amber), "Pay cost is up 14% on the
  last three months" (amber); the information-level one waits as 4th. "Got it" removed the
  overtime line at once (database: acknowledged, level 32, critical). "Look closer" on cost
  opened Insights › Explorer with "Back to Home"; on leave it opened Workforce › Time off.
  With everything put away the card is not drawn (People / Pay runs / Hiring only).
- **Console:** no errors on either lens. Two 500s on the LOGIN page only (the website logo
  and favicon images: the local copy has no filestore) — environment, unrelated.
- **Phone width (390 px, headless Chrome on the same local server):** Home — card 300 px,
  no sideways scroll; Inbox — card columns `22px 260px` (box + story; icon put away as
  before), tray 330 px, no sideways scroll.
- Screenshots were taken locally (local data, not committed). The phone check is a
  headless-Chrome script kept outside the repo (`qf1_phone.cjs` in the session scratchpad);
  the window of the shared browser could not be resized and the devtools profile was held by
  another session (G99).
- Not exercised in the browser: the overtime and people doors (the overtime line was put away
  first). Both are covered by `test_14f` (the screen opens exactly the actions the server
  checked) and by the same `door()` helper the cost and leave doors used.

### 2.3 Static gates
- `py_compile` on every changed/added Python file: OK. XML parse of `inbox.xml`,
  `pb_dashboard.xml`, `payroll_ai_security.xml`: OK.
- PO gate (`polib`): vi_VN — pb_approval_config 883 rows (+29), pb_dashboard 282 (+20; and the
  stale "balances" entry, no longer in the code, removed so the template test stays exact),
  biz_approval_workflow 243 (+5: the 3 new + "Company"/"Other" that were missing), id_ID 17
  (+3), pb_payroll_ai_insights 280 (+8). 0 placeholder mismatches, 0 vendor name in any
  msgstr, no new duplicate (the one duplicate in pb_approval_config/biz_approval_workflow is
  pre-existing). Both `.pot` files are fresh exports with "Payobook 19.0" in the header.
- Diff grep for the vendor name in added lines (excluding imports and technical markers): none.

## 3. Self-review

| Rail / non-goal | How it holds |
|---|---|
| R1 never more than a single approve | `decide_many` calls `biz.approval.engine.decide` (the drawer's call) as `self.env.user`, no `sudo()` anywhere near it, `exception_grant_id=None`; eligibility re-asked server-side; test 8 (no seat, submitter) |
| R2 one bad row | per-id `cr.savepoint()`; UserError/AccessError/ValidationError → that row's sentence; anything else → plain sentence + log line; test 6 |
| R3 idempotent per row | key `bulk-uid-request-step-revision` + expected revision = the card's; test 7 |
| R4 static contract | classes `pbam-…` only (`pbam-req--sel`, no `is-sel`); kit tokens only; no `self.env.company` in the facade; Escape in capture phase without preventDefault |
| R5 alerts never cross companies | record rule + explicit `company_id in env.companies` + per-company detectors; test 11; `details` never returned (test 13) |
| R6 Home never fails | `section()` savepoint + `optional()`; AccessError → hidden; test 14e (a raising reader) |
| R7 translations | §2.3 |
| R8 versions | §1 table |
| No bulk refuse/send back, no money, no exception | approve only; money refused twice (constraint and `_can_bulk`); exception never passed |
| No engine logic change | `biz_approval_workflow` only gained the field, constraint, create default, seeder, migration |
| No setting screen for `bulk_ok` | none added (follow-up, §5) |
| Retired `act()` / `get_team_data` | untouched |
| PayAI: no new detector, thresholds, provider calls, PDF, menu, cron switch | none added; an updated alert keeps its stored summary, so persistent alerts now cause FEWER summary calls than before (one per alert, not one per day) |
| Old alert rows | not rewritten; never on Home |
| No new dependency | manifests unchanged; test 14g |
| Forbidden modules | `pb_timeoff`, `pb_ess_workforce`, `pb_me_team`, `pb_explorer`, `biz_access`, `pb_pack_*` untouched |
| White-label / plain words | every new string checked; no vendor name |

**Deviations (deliberate, small):**
1. `decide_many(request_ids, revisions=None)` takes an optional map of the revisions the cards
   showed. Without it a second press could approve the NEXT step of a request whose next step is
   also mine; with it the second press is refused ("changed while you were looking"). The screen
   always sends it.
2. The headcount detector raises two different things (joined / left) under one category, so
   their key carries `.joined` / `.left` — otherwise one would overwrite the other.
3. `_can_bulk` also says "This is no longer waiting for a decision." for finished requests (a
   clearer reason than "not your turn" for a request decided in another tab).
5. Commit attribution line: the session's environment prescribes `Co-Authored-By: Claude Opus 5.5`
   (the implementer), so that line is used instead of the handover's Fable line.
4. The pb_dashboard `vi_VN.po` lost one stale entry ("balances") that the code no longer uses;
   the fresh `.pot` no longer has it and the template test compares both ways.

## 4. Decisions taken
- **A3 defaults applied once:** (a) the 19.0.1.8.0 post-migration calls
  `_seed_bulk_defaults()`, which switches on the 11 kinds only where `bulk_ok` is still off and
  the kind is not money, and sets the marker parameter `biz_approval_workflow.bulk_ok_seeded`;
  a second call does nothing; (b) a catalogue row CREATED later (a module installed afterwards,
  or a fresh database) gets the default in `create()` unless the data names `bulk_ok` or it is
  money. Nothing re-asserts it on upgrade, so a customer's choice survives.
- **Doors found:** cost → Insights hub, Explorer lens (`pb_insights_hub.action_pb_insights_hub`
  + `pb_explorer.action_pb_explorer` must exist); overtime → People hub, Workforce insights
  lens (`pb_people_hub.action_pb_people_hub` + `pb_workforce_insights.action_pb_workforce_insights`);
  headcount → People hub; leave → Workforce › Time off (`pb_mission.action_pb_workforce` lens
  `timeoff` + `pb_timeoff.action_pb_timeoff`), the Leave Command Center.
- "Got it" threshold for counts (people, leave): 5 more of them.

## 5. Owner questions
1. **Which kinds of request should managers be allowed to approve several at once?** Today:
   leave, overtime, timesheets, attendance corrections, business trips, training requests,
   setting goals, changing goals, recognition, notices to staff, and letters. Everything about
   pay, money going out, pay data, set-up, leavers, probation verdicts, new hires, contracts,
   pay and bank changes and hiring is approved one at a time. There is no screen to change this
   yet — do you want one in the Approvals set-up room?
2. **Should a brand-new company see "PayAI noticed" before its first pay run?** Home shows the
   "Get your first payroll out" checklist instead of the row of cards until a pay run exists,
   so the PayAI card (like People, Pay runs and Hiring) appears only after that.
3. **Is 50 the right most-at-once?** One press approves at most 50 requests.

## 6. Deploy notes
- Modules to `-u` on all five (`payobook`, `payobook_template`, `p0clone`, `rize`, `sudima`):
  `biz_approval_workflow,pb_approval_config,pb_payroll_ai_insights,pb_dashboard`.
- **Tier: normal** (new stored fields, one one-time data migration that only switches a new
  flag on, a new record rule, a changed daily job). Not a pay calculation. The record rule is
  read-narrowing on PayAI alerts only; treat as normal, but read the cron note below.
- **Daily job touched:** "PayAI Pulse" (`pb_payroll_ai_insights.ir_cron_payai_pulse_detection`,
  `model.run_anomaly_detection()`). First run after deploy creates company-stamped alerts;
  older rows (no company) are left alone and never shown on Home.
- Asset purge: **yes** (JS/SCSS changed in two modules) — and the browser cache keeps the old
  stylesheet under the same address (gotcha W1 below): bump `web.assets.version` as usual.
- Verify on each database: `ir_module_module.latest_version` = the four versions above;
  `select key from biz_approval_process where bulk_ok` = the 11 kinds present there;
  `ir_config_parameter biz_approval_workflow.bulk_ok_seeded` = 1.

## 7. New gotchas (ledger rows W1–W5)
See `WDGAP_LEDGER.md`.
