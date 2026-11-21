# WDGAP S9-B — report: Conduct cases + People reports

Branch `wdgap-s9b` (from `origin/19.1` @ `abc2259b6`). Two NEW modules, no file outside them
edited. Not deployed. Local test database `wdgap_s9b_t` (copy of `upd_p6_t_tpl`), dropped at the end.

## 1. What was built

### 1.1 `pb_conduct` — Conduct cases (owner ruling P3)

- **The case** (`pb.conduct.case`): concern → hearing → decision → letter → closed. A concern has a
  reason (HR-editable list, 7 seeded), what happened, when, and who raised it (free text — the person
  who raised it gets no access). Hearing: date/time, place, who attends, held-on date, minutes (a
  note on the case). "No hearing needed" goes straight to the decision with a reason. Decision: no
  action / verbal / written / final written warning / dismissal, a summary that goes into the letter,
  and "valid until" for warnings (default 6 / 12 / 12 months, HR changes it). Close (with a reason
  before a decision), open again. Earlier cases of the same person are listed in the drawer. Own
  history log (`pb.conduct.event`) — NO chatter, no followers, no email, no to-do.
- **Letters** (`pb.conduct.letter`, own model — NOT `pb.hr.letter`): invitation to a hearing and the
  decision letter, worded from HR-editable templates (`pb.conduct.letter.template`, plain text with
  `${...}` words; only the listed words are accepted), in the employee's language (vi/id seeded via
  `.po`). Draft letters can be edited or deleted; issuing renders the PDF (one record per render),
  files a copy in the employee's documents under the new category **"Private HR letters"**
  (code `pb_conduct`) and makes it readable on My Payobook. An issued letter is frozen. Issuing the
  decision letter closes the case.
- **Country notes** (`pb.conduct.country.note`): per country and step, HR writes what their adviser
  says; shown on the case at that step. **Shipped EMPTY** — every case shows "Check each step with
  your adviser. The law on hearings, warnings and letters differs by country, and these steps are
  general." The seeded letter wording carries the same "starting point — check with your adviser"
  line on its form.
- **Files**: attachments of the case itself (10 MB cap); never filed in the vault.
- **Dismissal → leaving checklist**: a button (probe of `pb.journey.case`, the pb_pip pattern),
  pressed by HR on purpose; the checklist carries no case detail (only "opened by" the HR person).
  Note: opening it runs the leaving module's own steps (e.g. its exit questionnaire email) exactly as
  from a resignation.
- **Board**: Talent › **Conduct** tab (sequence 30, `feature: "lifecycle"`, server probe
  `pb.conduct.can_open`), quiet glance (open, hearings in 7 days, waiting for a decision, letters to
  issue, replies to read, warnings still valid), quiet steps, shared filter panel, drawer with the
  adviser line + country notes, the next move, letters, notes, files, earlier cases and history.
  ⌘K rows 2760/2770. Set up menu (head only): Reasons, Letter wording, Country notes; "Who can see
  conduct cases" opens the Access screen.
- **Employee side** (`/my/letters`, page "Letters from HR"): only ISSUED letters addressed to one of
  the session user's own employee records; "I have read this"; one reply; PDF download. A neutral
  "Needs you" row ("1 letter from HR to read") while unread; an entry under "More" only while the
  person has a letter (C-3: no `pb_me_portal` edit, no proper tile). The words "warning",
  "disciplinary", "conduct" never appear in the page chrome or the home row.
- **Access screen**: groups `pb_conduct.group_conduct_user` ("HR — conduct cases") and
  `group_conduct_head` ("Head of HR — conduct cases"), no implied_ids from or to any HR, lifecycle,
  payroll or administrator group, nobody put in them at install. Abilities `conduct-cases-hr` /
  `conduct-cases-head` and roles "Conduct cases — HR" / "— head of HR" ship as data (noupdate,
  area People), listed only to the heads (and, as for every role, to the access team who give
  roles). Install adds the two roles to the Talent left-menu gate (additive; nobody holds them).

### 1.2 `pb_people_reports` — People reports (owner ruling P6)

- A tab under **People › Insights** (`under: "insights"`, registered straight into the People hub
  registry — no shared file touched), ⌘K row 2780. Five views: Headcount and turnover, Joiners and
  leavers, Why people leave, Age and gender, Length of service; company / department / year
  pickers; Download (Excel).
- **Who**: HR staff only, for the companies in their switcher narrowed by "who sees what"
  (`pb.group.scoped`, companies AND departments). NOT the payroll team: on this build every payroll
  officer holds the HR officer group because the payroll groups imply it, so the gate requires the HR
  group to come from a non-payroll group (an HR person who also does payroll still passes).
- **How figures are counted**: worked out live from employee records and their version history —
  NO stored snapshot, NO job, nothing to backfill. A person in two companies of a group
  (`pb_person_id`) is counted once; a move inside the group is no joiner/leaver for the group and a
  leaver + joiner for each company (said on screen). Start date = joining date, else first contract
  start (people with neither: counted every month, never as joiners — said on screen with a count).
  Archived records with no leaving date are left out (said on screen). Headcount at a month-end =
  people still employed after that day. Turnover = leavers ÷ average of start and end headcount.
  "Paid last month, not this month, no leaving date" cross-check line (a count, payslips read under
  sudo after the HR gate; no money).
- **Periods are fixed calendar years** ("2026 so far" up to the last COMPLETE month, and the four
  years before). Joiners and leavers are shown **by quarter**; the headcount **at the start and the
  end of the year** (plus the average and turnover), not month by month (§4 explains why).
- **Breakdowns** (why they left, age bands, gender, length of service) are offered for a company or
  the group, not for one department (most departments are too small; said on screen).
- **No money**, so nothing can be added across currencies.

## 2. Privacy — the exact rules that close each leak, and the test that proves it

| Leak / risk | Rule (file) | Proof |
|---|---|---|
| Nobody but named people may read a case, its notes, history, letters or set-up | ACL only for the two conduct groups (`pb_conduct/security/ir.model.access.csv`); facade `pb.conduct` re-checks `is_reader` on every call and answers an explained refusal with no data | T01–T08 (each role: no access right on 7 models, `search` refused, board refusal payload is exactly `{allowed, why}`, every facade call refused) |
| FACTS leak 1 — `pb.hr.letter` readable by every lifecycle user | Conduct letters are NOT `pb.hr.letter` rows (own model, own PDF) | T02 + every role: `pb.hr.letter` search for the employee is empty; lifecycle user/manager/admin cannot read `pb.conduct.letter` or its PDF attachment |
| FACTS leak 2 — every HR/payroll officer reads every vault document | GLOBAL rule `rule_vault_conduct_private` on `pb.employee.document`: `['|', ('category_id.code','!=','pb_conduct'), (1,'=',1) if user.pb_conduct_reader else ('employee_id.user_id','=',user.id)]` (`pb_conduct/security/conduct_security.xml`) | T01–T06 (document not in search, `read` refused, its attachment refused), T13 (an un-named HR officer cannot FILE into the category; control: same officer files into an ordinary one), T14 (other categories unchanged for HR and payroll), T15 (Employee 360 drawer lists it for the named person, not for HR/payroll/lifecycle) |
| Case files | Attachments with `res_model = pb.conduct.case` → attachment access follows the case | T01–T08 (`read(['datas'])` refused; listing refused or empty) |
| A named HR person who is the subject of a case | GLOBAL rules "never about yourself" on case, note, history, letter: `['!', ('employee_id.user_id', '=', user.id)]`; `create_case` refuses yourself; people picker leaves you out | T10 (cannot list, open, read history, open a case about self; the head can) |
| Company scope | GLOBAL company rules on all conduct models | T11 |
| Line manager | No group → no access | T04 |
| Employee (portal) | No access right at all; only `/my/letters` (session-resolved, issued + own only) | T08, T30–T33, T50–T52 (HTTP, real portal logins: own finished letters only, no draft/summary/notes/minutes/files/raised-by in the page, other person's letter PDF 404, reply/read on another's letter refused, draft never served) |
| Employee with an internal login | Same: no right on the case; sees only their own finished letter in their documents | T08b |
| Email / chatter | No mail.thread on any conduct model; nothing posted on `hr.employee`; no activity | T40 (no `mail.mail` queued by the whole flow, no message/activity on conduct models, nothing about the case on the person) |
| Payroll team reading people reports | Gate requires HR from a non-payroll group | T80 |
| People reports — small groups and subtraction | `pb_people_reports/models/suppress.py`: rules 1–5 + the AUDIT (exact elimination, bounds, small exact search) — see §4 | T69–T78 (engine), T70 (300 random tables attacked by brute force: no hidden cell has only one possible value), T69 (quarter-style series with the headcount identity), T83–T86, T88–T90 |

**What a tenant administrator sees** (T06): nothing in conduct cases, like everybody not named.
The Tenant administrator role does not include the conduct abilities (it is create-only and was
not widened); because it holds the access team, the administrator can SEE the two conduct roles on
the Access screen and give them — to someone else or themselves — and that grant is recorded like
every other. A **system administrator** (T05) is in the same position: not let in by default (unlike
growth plans). The superuser (code running as the system) bypasses rules by definition.

## 3. Tests

Baseline recorded BEFORE any install, same database: `-u pb_employee_vault,pb_me_portal,pb_people_hub`
tags `/pb_employee_vault,/pb_me_portal,/pb_people_hub`: **133 tests, 5 failed, 2 errors** —
TestMeHomeCards.test_05_grid (E), TestPbMePortal.test_01_profile_change_flow_and_audit (E),
TestMeHomeCards.test_06_font, TestMeHomeSource.test_12_vi_po_parses_and_covers_the_new_words,
TestPeopleHubStatic ×2 (contracts action, lens order), TestPortalOnlyDoors.test_t1_7.

After (same database, same tags, plus the two new modules), `-u` all five:
**195 tests, 7 failed, 2 errors** — the baseline seven, plus:

| Test | Why | Status |
|---|---|---|
| `pb_conduct` TestConductFlow.test_40 | it read "nobody else holds the conduct group" and my own WALK login (seeded on the same database) holds it | test rewritten to check the real risk (the built-in administrator and system account are not put in either group; the module ships no user data) — passes in the final module run below |
| `pb_me_portal` TestMeHomeSource.test_01_registry_covers_every_tile | `pb_me_portal` requires every My Payobook page of our modules to be in ITS tile list; `/my/letters` is not (contract C-3: no `pb_me_portal` edit; the page sits under "More") | **left for the orchestrator's C-3 prep commit**: add `('/my/letters', 'me', 'file-text', 'indigo', {})` to `_TILE_ROWS` and `'/my/letters': {'text': _lt('Letters HR has sent you')}` to `_TILE_WORDS` in `pb_me_portal/models/pb_me_home.py`, plus its vi/id entries. Until then this one test fails at merge. |

Final module run after the last code changes (`-u pb_conduct,pb_people_reports`, tags
`/pb_conduct,/pb_people_reports`): **62 tests, 0 failed, 0 errors**. The suppression engine tests
also run outside the server: T69–T78 pass; extra attacker sweeps (4 × ~2,850 random tables,
outside the suite): 0 leaks.

| # | What | Result |
|---|---|---|
| T01–T06 | HR officer, HR manager, lifecycle user/manager/admin, payroll officer/manager, line manager, system administrator, Tenant administrator: no right on 7 models, board refusal `{allowed, why}` only, every server call refused, case files / letter PDFs / vault copy refused, no `pb.hr.letter` row | pass |
| T07, T08 | another employee (portal), the employee themselves (portal): no ORM access | pass |
| T08b | employee with an internal login: sees only their OWN finished letter in their documents | pass |
| T09 | named HR sees everything of the case | pass |
| T10 | named HR never sees / opens a case about themselves; the head does | pass |
| T11 | company scope | pass |
| T12 | only the head changes reasons / wording / country notes | pass |
| T13–T15 | vault: un-named HR cannot file into the private category (control passes); other categories unchanged; Employee 360 drawer hides it from HR/payroll/lifecycle, shows it to the named | pass |
| T20–T26 | flow concern→hearing→decision→letter, refusals out of order, no-action and reopen, dismissal → neutral leaving checklist, issued letter frozen, template words checked, country notes on the case | pass |
| T30–T33 | employee: own finished letters only (no draft, summary, notes, minutes, files, raised-by), read + one reply, cannot touch another's letter, neutral Needs-you row | pass |
| T40, T41 | silent install (no job, no mail queued, no message/activity, nobody granted, role restricted, Talent gate) ; groups imply nothing upward | pass |
| T50–T53 | HTTP as real portal logins: page, read, reply, PDF; another employee gets 404/refusal; draft PDF 404; un-named HR board call refused over RPC | pass |
| T60, T61 / T95, T96 | no vendor name in any screen file; vi + id `.po` parse, 100% translated, markers present | pass |
| T69–T78 | hiding engine incl. the brute-force attackers | pass |
| T80, T81 | HR only (payroll team refused even though payroll implies HR; HR+payroll passes); only the companies the reader sees | pass |
| T82, T82b | start/end headcount reconciles with the records; every figure is the truth or hidden; no quarter can be worked out from the year totals; the group keeps its totals | pass |
| T83–T86 | small department hidden with its complement; a department / company on its own follows its parent row and vice versa | pass |
| T87 | a move inside the group is no group turnover; a leaver + joiner per company | pass |
| T88, T89 | breakdowns hide small groups, not per department; group − company cannot give another company's hidden figure | pass |
| T90, T91 | the Excel download hides exactly what the screen hides; no money anywhere | pass |

**Browser walk** (local copy, `http://s9b.localhost:8597`, own host name so other builders' sessions
were untouched; console clean on every screen apart from the live-update reconnect logged during my
own server restart):
- as the NAMED head (walk_named): Talent › Conduct board, glance, steps, filters, drawer (adviser
  line, hearing, decision, letters, notes, files, earlier cases, history); new case → plan hearing →
  invitation letter; set-up menu; People › Insights › People reports (all five views; a 50-person
  DEMO company keeps start/end headcount 48/50, joiners 8, leavers 6, turnover 12.2%, two small
  quarters hidden; department table hides Legal (3) and its complement).
- as UN-NAMED HR (walk_hr): no Conduct tab on Talent; the board address shows "Only for the people
  HR names" with no data; RPC refused; People reports open.
- as the EMPLOYEE (walk_emp, portal): home shows "2 letters from HR to read"; `/my/letters` shows
  the two finished letters only; "I have read this" and a reply work; vi and id pages translated.
- Found and fixed in the walk: the invitation printed the hearing time in UTC (03:00 for a 14:00
  hearing) — letters now use the employee's, then the company's, then the issuer's time zone; form
  fields were unstyled — styled; the month-by-month headcount line (§4).
- Not walked: the PDF download (no PDF engine on this Mac — letters issue without a PDF here, logged,
  graceful; the PDF path is covered by the tests and the server has the engine) and the Excel
  download (covered by T90).

## 4. People reports: the hiding rules, and why there is no month-by-month line

Rules (`suppress.py`, all on the server; a hidden cell is `{v: null, h: true}` on screen, in totals
and in the download): (1) 1–4 people hidden, zero shown; (2) a hidden total hides its parts;
(3) a set with hidden parts keeps at least two hidden and they must add up to 5 or more;
(4) a pair whose difference is public (the year's joiners and leavers: end minus start headcount)
hides both sides together; (5) shares and rates follow their sources; (6) **the audit**: the
equations a reader can write (totals = parts, known differences) are solved exactly — elimination,
then bounds ("a hidden cell holds at least one person"), then a small exhaustive search — and any
hidden cell left with a single possible value gets a neighbour hidden too (a part before a total;
never a figure already shown as a tile on another screen). Sets that do not add up exactly (a person
in two companies is counted once in the group) are used for rules 2–3 but kept out of the exact audit.

Cross-screen, both directions: a company or department looked at on its own takes the hiding of its
row in the parent table, AND the parent table takes each row's own hiding (both computed with the
same calls). A company-by-group breakdown (age, gender, reasons, length of service) is suppressed as
ONE table so group − company can never give another company's hidden figure; its totals are the
tiles. Age/gender/leaving breakdowns are offered per company, never per department.

Found while testing and walking (each changed the design):
- (a) Rules alone leaked: a hidden row total rebuilt from the grand total gave away its only
  non-zero cell (found by the attacker test T70). The audit was added.
- (b) Joiners and leavers by month next to a monthly headcount can almost always be pieced together
  (a −5 June change plus "5 leavers this year" pins every other month). Moved to quarters.
- (c) The walk then showed that a month-by-month headcount ON ITS OWN breaks the rule: "49 in
  August, 50 in September" gives a one-person change by subtraction, and the audit hid the year's
  joiners, leavers and turnover to compensate for a 50-person company. The monthly headcount line was
  removed: the screen shows the headcount at the start and the end of the year, joiners and leavers
  by quarter, and the year totals. For the 50-person walk company that keeps headcount, joiners,
  leavers and turnover visible, with two small quarters hidden.
- Periods are fixed calendar years: a sliding "last 12 months" would let two windows be subtracted.
- Residual, said plainly: somebody who writes down this year's figures each month and compares
  them can see month-to-month changes ("2026 so far" grows each month). HR can also read every
  leaver on the employee records directly; the hiding protects the report, not those records.

## 4b. Deviations from the handover / FACTS (on purpose)

- Letters are NOT `pb.hr.letter` rows (FACTS offered this option): closes leak 1 by construction.
- No approval route for the decision and no formal appeal step (FACTS §2.3 precedent, not a scope
  bullet): the named HR person records the decision. Left for later (§7).
- `_workflow_capabilities` NOT declared for the case model: a workflow on a conduct case could send
  messages to people who are not named. Workflow Studio still only lists the model to designers who
  can read it (the named people).
- No settings card in Settings (a "Set up" menu on the board instead).
- People reports: no stored month-end snapshot and no job (worked out live); calendar years only;
  joiners/leavers by quarter; headcount at start and end only; breakdowns per company, not per
  department; no turnover % per department row (it would need the row's start headcount).
- Country notes ship EMPTY (legal wording is an owner item).

## 5. Files outside the new modules

None edited. New: `pb_conduct/**`, `pb_people_reports/**`, this report. Install-time data written
into other modules' tables by the new modules (no file edits): a vault category, two abilities, two
roles, two Talent menu role links, a global rule on `pb.employee.document`.

## 6. Deploy notes (risky tier: new security rules)

- `-i pb_conduct,pb_people_reports` on all five databases; **no existing module needs a version
  raise** (nothing else changed). Depends: pb_conduct → hr, portal, pb_hub, pb_talent_hub,
  pb_import_kit, pb_filter_kit, pb_me_portal, pb_employee_vault, biz_access, pb_vendor_access;
  pb_people_reports → hr, pb_hub, pb_people_hub, pb_insights, pb_group, pb_import_kit, pb_filter_kit
  (probes pb_workseg `pb_person_id`, `date_of_joining`, `hr.payslip`).
- No pay figure changes, no cron, no mail, no demo data. Install grants nobody anything.
- Assets: new backend + frontend files → asset purge + restart.
- Check after install: `ir_module_module.latest_version` 19.0.1.0.0 ×2 per DB; on one DB, an HR
  officer opening Talent sees no Conduct tab; People › Insights › People reports opens.
- Seam: `_pbme_needs_extra` calls `super()`; `PbMePortal.home` override calls `super()` (S9-C and
  Step 6 modules stack the same hooks).

## 7. Questions for the owner (plain words)

1. **Small companies will see "Hidden" a lot.** Under the "nobody under 5" rule, a company with
   few joiners or leavers will often see those numbers hidden, sometimes the turnover too. A
   50-person company keeps its yearly totals; a 15-person one usually will not. Is that the right
   price, or do you want a softer rule for HR (for example "under 3")?
2. **No month-by-month headcount line.** Showing the headcount for every month lets anyone work out
   a one-person change by subtraction, which your rule forbids, so the report shows the headcount at
   the start and end of the year and joiners/leavers by quarter. Keep it that way, or allow the
   monthly line and accept that small monthly changes can be worked out?
3. **Country notes for hearings and warnings start empty.** Should we have Vietnam and Indonesia
   notes written after a legal check, or will each customer's HR write their own?
4. **Sign-off and appeal.** Today the named HR person records the decision. Do you want a second
   signature (for example Head of HR) before a warning or dismissal is final, and a formal "appeal"
   step after the employee replies?
5. **Administrators.** Unlike growth plans, a system or tenant administrator does not see conduct
   cases until they are named (they can name themselves on the Access screen, which is recorded).
   Keep that?

## 8. Left for later

- `/my/letters` proper tile on the employee home (C-3 prep commit — exact change in §3).
- Decision sign-off route and appeal step (Q4).
- Explorer cost-centre column (C-5, not this phase).
- A "people moving between departments" view (moves) — the data is there (versions), not shown.

## 9. Gotchas → ledger

- S9B-1: a method called `_table` on a model silently replaces the model's database table name
  ("expected string … got 'function'" at registry load). Never name a model method `_table`
  (or `_name`, `_order`, `_rec_name` …).
- S9B-2: on this build every payroll officer holds the HR officer group (the payroll groups imply it):
  "HR only" by `has_group('hr.group_hr_user')` includes the whole payroll team. Check the group's
  source (`pb_people_reports` `_can_read`).
- S9B-3: small-group hiding needs an exact AUDIT, not just rules: a hidden row total rebuilt from
  the grand total gave away its only non-zero cell; and two shown headcounts a month apart give a
  one-person change by subtraction. Test hiding with a brute-force attacker (`test_suppress.py`).
- S9B-4: hr.employee `tz` defaults to UTC; letters/time stamps for a person should use their login,
  then the company, then the issuer's zone.
- S9B-5: `pb_me_portal` TestMeHomeSource.test_01 fails for ANY new My Payobook page of a `pb_*`
  module until it is in `_TILE_ROWS` — every phase that adds a page under C-3 trips it at merge.
- S9B-6: an `HttpCase` run can finish its tests and then hang at shutdown; the result line is in the
  log ("0 failed … of N tests") — read it there and stop the process.
