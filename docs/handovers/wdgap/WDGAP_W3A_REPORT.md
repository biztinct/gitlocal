# WDGAP W3-A — report: People reports for HR without hiding (PR1), month-by-month line (PR2), second sign-off on conduct decisions (CD1)

Branch `wdgap-w3a` from `origin/19.1` @ `19fd98032`. Commits: `34ed6c9d0` (PR1 + PR2),
`a0dbd8a2b` (CD1), then this report. Two LIVE modules changed, nothing else edited
(one out-of-lane test fixture is described in §6, NOT edited). Not deployed. Local test database
`wdgap_w3a_t` (copy of `upd_p6_t_tpl`, 40 behind modules upgraded), dropped at the end.

## 1. What changed

### 1.1 PR1 — People reports: HR sees everything (`pb_people_reports` 19.0.1.0.0 → **19.0.1.1.0**)

- **The hiding is gone, cleanly.** `models/suppress.py` (the hiding engine and its exact audit) and
  `tests/test_suppress.py` are DELETED; `models/__init__.py`, `tests/__init__.py` updated. No switch
  was kept (a switch would have kept the whole engine alive). Every figure is now a plain number on
  screen, in the totals and in the download: the `{v, h}` cells, the "Hidden" chip, "This group is
  too small", "fewer than 5", the rule line under the pickers and the download's "Hidden (small
  group)" are all removed (template, JS, SCSS, Python, `.po`).
- **Access unchanged.** `_can_read` (HR from a non-payroll group, for the companies the reader sees,
  narrowed by "who sees what") is byte-identical. Proven again in T80 (payroll officer, line manager,
  portal employee, internal employee login: refused; HR+payroll person: allowed).
- **Finer breakdowns restored** (they were coarsened only for the hiding rule):
  - Why people leave, Age and gender, Length of service **per department** again
    (`_cat_rows`, people_reports.py:551 — counts straight from the chosen scope's measure).
  - The company/department table gets **headcount at the start** and **turnover %** per row
    (`_breakdown` :379, `_group_table` :493).
  - "Last 12 months" is offered beside the calendar years (`_periods` :215, `_params` :170; the S9-B
    report §4 says it was dropped only because two sliding windows could be subtracted).
  - The data notes and the payroll cross-check say real counts instead of "fewer than 5".
- Kept: no money figures (T91); nothing ever added across currencies (no money at all); surveys
  (`pb_voice`) untouched — `git diff origin/19.1 -- pb_voice` is empty.

### 1.2 PR2 — month-by-month headcount line (`pb_people_reports`, same version)

- `_months` (:460): for every month of the period, headcount at the month end, joiners, leavers and
  the change; quarters group the months (their joiners/leavers totals, the headcount at their last
  month, the change). A "last 12 months" period shows the cut quarters it spans (e.g. "Q4 2025" with
  Nov–Dec only).
- Screen (Headcount and turnover): a **line of the headcount at each month end** (one series, brand
  indigo, 2px line, 8px points, crosshair + tooltip on hover; the line starts at the headcount the day
  before the period) and the **Month by month** table with quarter total rows. Joiners and leavers view:
  the same table. Excel: the same month rows with bold quarter rows, then the company/department table
  with start, end, joiners, leavers, turnover.
- Layout fix found in the walk: the report's cards shrank to the lens height and clipped the month
  table — `.pbpr > * { flex-shrink: 0 }`.

### 1.3 CD1 — second sign-off on conduct decisions (`pb_conduct` 19.0.1.0.0 → **19.0.1.1.0**)

**Which decisions need it** (`SIGNOFF_OUTCOMES`, conduct_common.py:46): every decision whose letter
tells the employee of a consequence — **verbal warning, written warning, final written warning,
dismissal**. "No action" (letter "No further action") needs none and is issued directly, as before.

**States** (a new step `signoff`, "Second sign-off", between Letter and Closed; `signoff_state` on the
case):

| From | Action (who) | To |
|---|---|---|
| Decision | Record the decision (any named person) | Letter — decision recorded, draft letter prepared, `signoff_required` set |
| Letter | Ask for the second sign-off (any named person) | Second sign-off (`waiting`); the draft letter is frozen |
| Second sign-off | Confirm and issue the letter (a valid second person) | the letter is issued (PDF, filed, the employee can read it) and the case closes — `confirmed` |
| Second sign-off | Send it back, with a reason (a valid second person) | Letter (`sent_back`, reason shown to the first person; wording editable; ask again) |
| Second sign-off | Take it back (anyone named who cannot sign it) | Letter (blank sign-off) |
| Letter | Change the decision (any named person, while no decision letter is issued) | Decision (draft letter removed, decision text kept to start from) |
| Letter, unconfirmed | Close the case, with a reason | Closed — the unconfirmed decision is dropped (no warning on record without two people), logged |

**Who can be the second person** (`_signers`, conduct_case.py:267): a person NAMED for conduct cases
(either conduct group) who works in the case's company — never the person who recorded the decision,
never the person who asked for the sign-off, never the employee the case is about (named or not; a
named subject also cannot see the case at all — the existing "never about yourself" rule). The
system account is not a signer. If nobody qualifies, the drawer says so and links to the Access screen
(`_signoff_blocker` :283): with one named person in the company — "A second person named for conduct
cases is needed to confirm this decision. Only one person is named for this company now: name a
second one on the Access screen."

**Rails**: `action_issue` refuses a decision letter that needs a sign-off and has none
(conduct_letter.py:153 — the only way to issue it is `action_confirm_signoff`); title/body edits and
deletion are refused while the case waits (`_check_not_waiting` :145); closing from the waiting step
is refused; the leaving checklist for a dismissal opens only after the sign-off (`action_start_exit`).
**Cases decided before this change stay as they are**: `signoff_required` is a new column, False on
every existing case, so their letters still issue directly — no migration, no backfill (T109).

**"Needs you" for the second person, inside `pb_conduct`**:
- Conduct board: glance figure "waiting for your sign-off" (rose only when non-zero), step "Second
  sign-off" with its flag, a "Waiting on you" filter and a "Waiting for your sign-off" view, and the row
  says "Your sign-off is needed". The Letter step now says "1 to send for a second sign-off" instead of
  "1 letter to issue" for an unconfirmed warning.
- My Payobook home (`_pbme_conduct_signoff`, pb_me_home.py:40): a named person with a decision waiting
  for THEIR sign-off gets one row "1 item waits for your sign-off — Open it in HR to confirm or send it
  back", which opens the Conduct board. Never the case, the person, or the words conduct / warning /
  dismissal / hearing (T113). Nobody un-named ever gets it (T108, T115).
- **Not the general Approvals inbox, on purpose**: that inbox is shown to approvers who are not named
  for conduct cases, and a row's title and details would tell them a case exists and whom it is about.
  T114 proves no approval request or event is ever created for a conduct case.

**Nothing is emailed** (T114: no mail queued, no message, no to-do through ask / send back / ask
again / confirm). Employee wording unchanged and neutral.

### 1.4 Files

`pb_people_reports`: `__manifest__.py`, `models/__init__.py`, `models/people_reports.py` (rewritten
around the plain figures), `models/suppress.py` (deleted), `static/src/js/people_reports.js`,
`static/src/xml/people_reports.xml`, `static/src/scss/people_reports.scss`, `tests/__init__.py`,
`tests/test_people_reports.py` (rewritten for PR1/PR2), `tests/test_reports_static.py` (+T97),
`tests/test_suppress.py` (deleted), `i18n/*.po|pot`.

`pb_conduct`: `__manifest__.py`, `models/conduct_common.py`, `models/conduct_case.py`,
`models/conduct_letter.py`, `models/pb_conduct.py`, `models/pb_me_home.py`,
`static/src/js/conduct_board.js`, `static/src/xml/conduct_board.xml`,
`static/src/scss/conduct_board.scss`, `tests/__init__.py`, `tests/common.py` (+ a second named person;
the fixture's written warning now goes through ask + confirm), `tests/test_conduct_flow.py` (T23:
leaving checklist waits for the sign-off), `tests/test_conduct_privacy.py` (T08b via sign-off),
`tests/test_conduct_portal.py` (+T54), `tests/test_conduct_signoff.py` (new, T100–T115),
`i18n/*.po|pot`.

## 2. Tests

**Baseline, recorded BEFORE any edit** (same database, `-u pb_conduct,pb_people_reports,
pb_employee_vault,pb_me_portal,pb_people_hub,pb_review_forms`, tags `/pb_conduct,/pb_people_reports,
/pb_employee_vault,/pb_me_portal,/pb_people_hub,wdgap_s9m`): **200 tests, 6 failed, 2 errors** —
TestMeHomeCards.test_05_grid (E), TestPbMePortal.test_01_profile_change_flow_and_audit (E),
TestMeHomeCards.test_06_font, TestMeHomeSource.test_01_registry_covers_every_tile,
TestMeHomeSource.test_12_vi_po_parses_and_covers_the_new_words, TestPeopleHubStatic ×2 (contracts
action, lens order), TestPortalOnlyDoors.test_t1_7. (Per module: pb_conduct 36, pb_people_reports 26,
pb_employee_vault 13, pb_me_portal 93, pb_people_hub 27, seams 5.)

**After** (same command, same database): **207 tests** (pb_conduct 54, pb_people_reports 20 — the 6
hiding-engine tests deleted with the engine —, pb_employee_vault 13, pb_me_portal 93, pb_people_hub
27; the 5 seam tests do not start, see below). Failure set = **the baseline eight, plus**:
- `TestS9MergeSeams` setUpClass in `pb_review_forms` (expected) — its fixture issues a
  written-warning letter directly, which CD1 now refuses ("This decision needs a second sign-off
  first"). That file is outside this phase's lane: the exact fix is in §6; with it applied locally
  (then reverted, not committed) the seam suite passes **5/5, 0 failed**.
- `TestConductSignoff.test_110` failed once in that run because it counted "warnings still valid" as
  an absolute number and my browser-walk warning (committed on the same local database) made it 2;
  the test now compares before/after closing. Final module run after that fix (`-u pb_conduct,
  pb_people_reports`, tags `/pb_conduct,/pb_people_reports`): **74 tests, 0 failed, 0 errors**.

### 2.1 Numbered tests (new or changed) — all pass

| # | What | Result |
|---|---|---|
| T80 | HR only: payroll officer, line manager, portal employee, internal employee login refused (no data, `{allowed, why}`, report and Excel raise); HR + payroll passes | pass |
| T81 | only the companies the reader already sees | pass |
| T82 | tiles = independent count of the records (start, end, joiners 9, leavers 6, turnover formula); group: the mover is no leaver | pass |
| T82b | PR2: every month's headcount, joiners, leavers = an independent count; months add up to the tiles; one company: each month = previous + joiners − leavers | pass |
| T82c | quarters group the months exactly (sums; quarter headcount = its last month) | pass |
| T83 | PR1: a 3-person department is shown with its real figures (start 2, end 3, 1 joiner, 0% turnover); rows add up to the total = tiles | pass |
| T84 | the small department on its own: real figures, month line correct | pass |
| T85 / T86 | a department / company on its own equals its row in the parent table (start, end, joiners, leavers) | pass |
| T87 | a move inside the group is no group turnover; a leaver + joiner per company; the group's August line shows 0/0 | pass |
| T88 | breakdowns per department again: gender 2 men / 1 woman, ages, leaving reasons (5 resigned), length of service; percentages add to 100 | pass |
| T89 | the group's gender breakdown = the sum of its companies | pass |
| T90 | the download = the screen (every month row, quarter row, department row, gender row); no "Hidden", no vendor name | pass |
| T91 / T92 | no money words; silent install (no job, mail template, group, rule) | pass |
| T93 | "Last 12 months": offered; 12 months ending with the last complete month, each = independent count; unknown period falls back | pass |
| T94 | nothing hidden anywhere (5 views × group / company / small department) | pass |
| T95 / T96 / T97 | no vendor name on screen; vi + id parse, ≥95% translated, markers; no hiding words or engine left, new words in both `.po` | pass |
| T100 | which decisions need the sign-off: verbal / written / final / dismissal yes (letter refused through the board AND the model); "No action" issues directly | pass |
| T101 | until confirmed the employee sees nothing: no PDF, no document, not in their letters, home row counts only the earlier letters | pass |
| T102 | waiting: letter frozen (edit, delete, issue refused); the first person cannot confirm, send back or close; the second person sees the buttons | pass |
| T102b | decided by one named person, sent by another: neither may sign; a third (the head) confirms; board counts "to send" vs "to issue" | pass |
| T103 | confirm: letter issued, filed, case closed, employee sees it, history lines; no second confirm | pass |
| T104 | send back needs a reason; returns to the first person with the reason; wording edited; ask again; confirm issues the new wording | pass |
| T105 | only ONE named person in a company: plain message naming the Access screen, before and after asking; nobody (not even the system) can confirm; naming a second person unblocks it | pass |
| T106 | a named person who IS the case subject: cannot see, count or sign it; no home row; another named person can | pass |
| T107 | the employee is never a signer, even when named; a portal employee has no right at all | pass |
| T108 | general HR, HR manager, lifecycle, payroll, line manager, un-named administrator, tenant administrator, another employee, the employee (portal), an internal-login employee: cannot ask, confirm, send back or take back (board AND model), get no home row | pass |
| T109 | a case decided before this change (no flag) still issues its letter directly | pass |
| T110 | closing without the sign-off needs a reason and drops the decision (no live warning), reopen goes to Concern | pass |
| T111 | change the decision (draft removed, text kept); refused once the decision letter is issued, even reopened | pass |
| T112 | take it back: letter editable again | pass |
| T113 | needs-you: board figure + filter + view for the second person only; one neutral home row that opens the board; gone after confirm | pass |
| T114 | not in the Approvals inbox (no request/event for a conduct case); no mail, message or to-do | pass |
| T115 | the privacy matrix with the new steps (§3) | pass |
| T20–T26, T30–T33, T40–T41, T01–T15 | the S9-B suite, fixture now going through the sign-off (T23: the leaving checklist waits for it; T08b via sign-off) | pass |
| T50–T53 | HTTP as real portal logins (unchanged) | pass |
| T54 | HTTP as the portal employee: a decision waiting for the sign-off is not on `/my/letters`, its PDF is 404, a reply is refused; after the second person confirms, it is there (summary of the case never) | pass |

### 2.2 Static gates
`py_compile` of every changed Python file: ok. XML parse of both templates: ok. `node --check` of both
JS files: ok. PO gate (`PoFileReader` in T61/T96/T97): both modules, vi + id, parse, 100% translated,
`odoo-python` / `odoo-javascript` markers; the new/changed `.po` entries were merged text-level (old
entries byte-identical; 12 obsolete hiding entries removed from each people-reports file, 1 changed
sentence in conduct). Vendor word on added user-visible lines: 0 (the only hit is the technical
fallback address `/odoo/action-…` used when the `/bizapp` re-route module is absent — never shown as
text; every live database has `/bizapp`). Product name in `biz_*`: no `biz_*` file touched.

## 3. Privacy matrix (S9-B matrix re-run with the new steps)

Against a case **waiting for the second sign-off** and one **sent back** (T115, T106, T108, T113, T54):

| Role | Sees the case / its new sign-off fields | Can ask / confirm / send back / take back | Home "Needs you" row | Sees the held letter |
|---|---|---|---|---|
| General HR officer / HR manager | no (no access right; board refuses with `{allowed, why}`) | no | no | no |
| Lifecycle user/manager/admin | no | no | no | no |
| Payroll officer/manager | no | no | no | no |
| Line manager | no | no | no | no |
| Another employee (portal) | no | no | no | no |
| Un-named system administrator / tenant administrator | no (CD3 unchanged) | no | no | no |
| The employee (portal, and with an internal login) | no ORM access; only issued letters on `/my/letters` | no | only "letter from HR to read" once issued | **no** until confirmed (page, PDF 404, reply refused) |
| First named person (recorded the decision / asked) | yes, incl. the send-back reason | ask, take back, change decision; **cannot** confirm or send back | no | yes (it is their draft) |
| Second named person | yes | **confirm** or send back | yes, neutral | yes |
| Named person who IS the case subject | **no** (never about yourself) | no | no (not counted) | only once issued, as the employee |

People reports (T80, T81): HR yes (own companies only); payroll officer, line manager, employees no.

## 4. Browser walk (local copy, own host names `w3a.localhost`, `w3a2.localhost`, `w3a3.localhost`
on port 8633 — other builders' sessions untouched; console clean on every screen)

- **HR (first named person)**, People › Insights › People reports: tiles; the headcount line with its
  tooltip ("Jun 2026 — Headcount 7, Joiners 0 · Leavers 1"); Month by month with quarter rows; By
  department with a 1-person and a 4-person department shown in full (start, end, joiners, leavers,
  turnover 25%); Age and gender for ONE department (2 women, 1 man, 1 not recorded); "Last 12 months"
  (Nov 2025 – Oct 2026, cut quarters Q4 2025 / Q4 2026); the download built (8 KB). Found and fixed:
  the cards shrank and clipped the month table (flex-shrink), and the chart was too tall on a wide
  screen (drawing box widened).
- **Conduct, first named person**: a written warning recorded → drawer shows the amber "Second
  sign-off" block, the draft marked "Draft, waits for the second sign-off", buttons Ask / Change the
  decision / Close; Ask → step "Second sign-off", block "Sent by … A second person … confirms it",
  only "Take it back" offered. Found and fixed: the Letter step said "1 letter to issue" for an
  unconfirmed warning — it now says "1 to send for a second sign-off".
- **Second named person**: My Payobook home shows "1 item waits for your sign-off — Open it in HR to
  confirm or send it back" (top line "Something waits for your sign-off."); the row opens the Conduct
  board: glance "1 waiting for your sign-off", row "Your sign-off is needed"; drawer "This decision
  waits for your sign-off…", Confirm and issue → "Confirmed by DEMO Sean Second on …", case Closed,
  letter Issued.
- **The employee (portal)**: home "1 letter from HR to read" (neutral); `/my/letters` shows the
  finished letter only — the case summary is not on the page.
- Not walked on screen: the one-named-person message (T105 covers it, incl. the Access-screen link's
  words) and the PDF (no PDF engine on this Mac; covered by tests and the S9 rehearsal).

## 5. Deviations (on purpose)

- PR1 and PR2 are ONE commit: both rewrite the same functions of `people_reports.py` and the same
  template (the month line replaced the hiding-driven quarter view), so an honest PR1-only state
  would have been a throw-away intermediate. CD1 is its own commit.

- No "show / hide small groups" switch was kept: the default (show everything) needs none, and
  keeping a switch would keep the whole hiding engine and its tests alive.
- Turnover per department row was added (it was left out only because the hiding could not show the
  row's start headcount).
- The second sign-off issues the letter itself (confirm = finish the letter), so nobody can change the
  wording after the second person read it. "Take it back" and "Change the decision" were added so a
  waiting or sent-back decision is never stuck (e.g. with only one named person).
- Closing a case whose warning/dismissal was never confirmed drops that decision (logged) instead of
  leaving an unconfirmed warning on record.
- The second person's "Needs you" is on the Conduct board AND on their My Payobook home (only if they
  have an employee record); nothing in the general Approvals inbox (§1.3).

## 6. Out-of-lane item (NOT edited — for the merge)

`pb_review_forms/tests/test_wdgap_s9_merge_seams.py` (the Step 9 seam test) builds its fixture by
issuing a written-warning letter directly (line 97 `F.issue_letter(cls.letter.id)`), which CD1 now
refuses, so its setUpClass errors after this branch merges. Exact fix (verified locally: 5/5 pass,
then reverted):

```python
# after cls.conduct_named = user('cn', [...]) (line 69-70):
        # W3-A (ruling CD1): a second named person gives the second sign-off
        cls.conduct_second = user('cn2', ['base.group_user', 'pb_conduct.group_conduct_user'])
# replace line 97 `F.issue_letter(cls.letter.id)` with:
        F.move(cid, 'ask_signoff')
        env['pb.conduct'].with_user(cls.conduct_second).with_context(
            allowed_company_ids=cls.company.ids).move(cid, 'confirm_signoff')
```
No `pb_review_forms` version raise is needed (test file only).

## 7. Deploy notes (normal tier + a new column)

- `-u pb_people_reports,pb_conduct` on all five databases (payobook, payobook_template, p0clone, rize,
  sudima). New stored columns on `pb_conduct_case` (seven `signoff_*` fields, all empty on existing
  rows — existing cases keep the old behaviour by design). New selection value `signoff` on the case
  step. No data migration, no job, no mail, no new group/rule, no pay figure touched.
- New/changed backend assets in both modules → asset purge + restart + `web.assets.version` bump.
- Check after: `latest_version` 19.0.1.1.0 ×2 per database; People › Insights › People reports shows
  no "Hidden" and a "Month by month" card (the S9 deploy counted 252 hidden cells on rize; after this
  upgrade there are none by construction).
- Merge with the seam-test fix of §6 at the same time.
- The orchestrator may want to confirm on the live sites that nobody is named for conduct cases yet
  (S9 deploy: nobody named) — then the "only one named person" message will show as soon as HR names
  the first person and records a warning.

## 8. Questions for the owner (plain words)

1. **Who may give the second sign-off?** Today it is any OTHER person named for conduct cases in that
   company (not the one who recorded the decision or asked, never the employee). Should it instead
   always be the "Head of HR — conduct cases"?
2. **Closing a case before the second sign-off** drops the warning (it never counts). Is that right,
   or should such a case keep the decision on record as "not confirmed"?
3. **Small companies with one HR person**: they cannot finish a warning until they name a second
   person on the Access screen. Is that acceptable, or should an outside adviser login be suggested
   in the message?

## 9. Left for later

- A "people moving between departments" view (unchanged from S9-B).
- Explorer cost-centre column (C-5, not this phase).

## 10. Gotchas → ledger

- W3A-1: a hub lens laid out as a flex column shrinks its cards to the lens height; a card with
  `overflow-x: auto` then clips its own content (the month table was cut after 3 rows). Give the
  lens's direct children `flex-shrink: 0`.
- W3A-2: the code-term extractor misread a tuple of pairs `(('reasons', _('…')), ('genders', _('…')))`
  and exported the bare keys ("genders", "ages", "service_rows") as translatable terms. Build such
  label maps as a dict, one `_()` per line.
- W3A-3: a sentence built in a template around `<t t-esc>` names ("Sent by <name>, <date>. A second
  person…") exports as fragments that cannot be reordered in Vietnamese/Indonesian; build the whole
  sentence on the server with named placeholders.
- W3A-4: a worktree guard refuses shell lines combining `cd`/variables/`git` with the repo path —
  `git rm`, `git diff`, `git checkout` each as a plain one-line command from the worktree root.
