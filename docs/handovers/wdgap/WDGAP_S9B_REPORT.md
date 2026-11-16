# WDGAP S9-B — report: Conduct cases + People reports

> **PAUSED (owner pause, 2026-11-16).** State: both modules built; last full runs —
> `/pb_conduct` 36/36 pass (`both6`), `/pb_people_reports` facade tests 14/14 pass (`rep10`),
> engine tests pass outside the server; PO files built (0 missing) and parse. Test database
> `wdgap_s9b_t` KEPT, walk data seeded (logins `walk_named` head-named, `walk_hr` un-named HR,
> `walk_emp` portal; passwords `walk-<login>`, local copy only). Local server stopped.
> **Exact next step:** (1) re-run `export_pot.sh` + `build_po.sh` (scratch `s9b/`) in case strings
> moved, then one full run `run_tests.sh final pb_conduct,pb_people_reports
> /pb_conduct,/pb_people_reports`; (2) after-change run of the neighbour suites
> `run_tests.sh after pb_employee_vault,pb_me_portal,pb_people_hub
> /pb_employee_vault,/pb_me_portal,/pb_people_hub` and compare with the baseline set in §3;
> (3) browser walk on `http://s9b.localhost:8597` (NOT 127.0.0.1 — other builders' cookies):
> start with `walk_start.sh` minus the seed line (data already seeded), sign in with
> `/web/session/authenticate`; walk Talent › Conduct as walk_named, as walk_hr (no tab / refusal),
> People › Insights › People reports, and `/my/letters` as walk_emp; console clean. The first
> screenshot attempt timed out (renderer busy while assets built) — wait for the bundle first.
> Note: no wkhtmltopdf locally, so letters issue without a PDF/vault copy here (logged, graceful);
> tests cover the PDF path in test mode. (4) Fill RESULTS/DEVIATIONS/OWNER placeholders below,
> commit with a feature message, push, drop `wdgap_s9b_t` + its filestore.

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
  years before). Joiners and leavers are shown **by quarter**, headcount by month (§4 explains why).
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

RESULTS_PLACEHOLDER

## 4. People reports: the hiding rules, and why joiners/leavers are by quarter

Rules (`suppress.py`, all on the server; a hidden cell is `{v: null, h: true}` on screen, in totals
and in the download): (1) 1–4 people hidden, zero shown; (2) a hidden total hides its parts;
(3) a set with hidden parts keeps at least two hidden and they must add up to 5 or more;
(4) a pair whose difference is public (joiners and leavers of one quarter: the headcount change)
hides both sides together; (5) shares and rates follow their sources; (6) **the audit**: the
equations a reader can write (totals = parts, known differences) are solved exactly — elimination,
then bounds ("a hidden cell holds at least one person"), then a small exhaustive search — and any
hidden cell left with a single possible value gets a neighbour hidden too (a part before a total).
Cross-screen: a company or department looked at on its own takes the hiding of its row in the parent
table (computed with the same calls), and a company-by-group breakdown is suppressed as one table so
group − company can never give another company's hidden figure.

Found while testing (the attacker test): (a) rules alone leaked — a hidden row total rebuilt from
the grand total gave away its only non-zero cell; the audit was added. (b) With headcount shown for
EVERY month, joiners and leavers by month can almost always be pieced together (a −5 June headcount
change plus "5 leavers this year" pins every other month); the audit then hid nearly everything for
a small company. So joiners/leavers are by quarter, headcount by month, and periods are fixed
calendar years (a sliding "last 12 months" would let two windows be subtracted).

DEVIATIONS_PLACEHOLDER

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

OWNER_PLACEHOLDER
