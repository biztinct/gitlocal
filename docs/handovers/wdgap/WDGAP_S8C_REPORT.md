# WDGAP S8-C — Organisation (`pb_org_structure`, `pb_plan_hiring`) — report

Branch `wdgap-s8c` (from `origin/19.1` @ `abc2259b6`). Two NEW modules, both
`19.0.1.0.0`, install with `-i`. **No existing file is edited** (`git diff origin/19.1`
outside the two modules and this report is empty). Nothing here changes a payslip
figure, a wage or a pay line.

## 1. What was built, per item

### 1.1 Job page with levels (`pb_org_structure`)
- `pb.job.level`: a named ladder (name translatable, order, "what it means", optional
  company — empty = every company). Unique name per company; cannot be deleted or
  archived while a job uses it.
- `hr.job.pb_level_id` (+ on the backend job form). The job page in People › Jobs shows
  people in the job, people to hire, pay band and family (read from Pay by a probe —
  `'pb.pay.band.job' in env`, no dependency, no money shown), level, description
  ("What the job is", stored in the core `description`), the job's open requests, and
  the role's pause switch.
- Levels are names only. **Not done on purpose:** the level is not copied into the
  employee's free-text "Job level" (`hr.employee.pb_job_level`) or the request's
  `pb_role_level` — the first is read by pay formulas (application-data schemes), so a
  bulk copy could change pay. Owner question Q1.

### 1.2 Cost centres as a proper list (never rewriting history)
- `pb.cost.centre` (code, name, company, notes, active). Unique code per company
  (ignoring case/spaces). Multi-company record rules.
- THE ONE WRITTEN VALUE stays `hr.contract.costcenter` (text) — drawer, employee panel,
  renewals (`CARRIED_FIELDS`), connected system, Updates and formulas keep working
  untouched. `hr.contract.pb_cost_centre_id` is a **stored compute of the text** (the
  list entry of the contract's company whose code, else name, equals the text). The
  list never writes onto a contract. A code that contracts carry cannot be changed or
  deleted ("add a new cost centre and move people from a date").
- "On contracts, but not on the list" + **Add them to the list** — creates entries from
  the texts already typed; writes **no** contract (test T3 checks every contract's
  `write_date`).
- **Move people to a cost centre, from a date** (`pb.cost.centre.move`): a whole team
  (and teams under it) or chosen people; today or later only (a past date is refused
  with "Payslips already made keep the cost centre they were paid under."), at most
  12 months ahead, at most 2,000 people at once; preview first ("People who move to X
  from D: N. Already there: M."); dated today = made at once; later = waits and a
  quiet daily job (`cron_pb_cost_centre_moves`, safe on an empty database, one failing
  move never stops the others, sends nothing) makes it on the day. A newer change
  replaces a waiting one for the same contract. History list with Cancel.
- **History guard, on every writer of the text:** `hr.payslip.line.costcenter` is a
  stored related copy of the contract's text (om_hr_payroll), so any edit used to
  rewrite the cost centre on that contract's PAST payslips. `hr.contract.write` now
  runs the write inside `env.protecting(...)` for the lines of payslips that are no
  longer a draft (`state not in draft/verify`) or whose period ended before the change
  date (the move's date, else today). Those lines keep the cost centre they were paid
  under; drafts for now follow the contract as before. **This changes the behaviour of
  the existing writers too** (contract drawer, Updates/Records, connected-system sync):
  a correction of a cost centre no longer reaches finished payslips. That is the
  "never rewrite history" rule applied everywhere; flagged for the deploy agent (§5).
- Each team's usual cost centre (`hr.department.pb_cost_centre_id`): filled in only on
  NEW contracts in that team that have none (a typed one wins). Nobody already there
  changes.
- **Not done (by design):** no override of `pb.records.desk._master_fields` — the
  existing "Cost centre" text field in Updates already writes the one value, and the
  history guard covers it. The seam row in the FACTS table is honoured by not touching
  it. Explorer column: left for later (C-5).

### 1.3 Pause hiring (J6 + C-2)
- Switches with reason, who, when: `res.company.pb_hiring_pause`,
  `hr.department.pb_hiring_pause` (covers the team and every team under it — stored
  recursive `hr.department.pb_hiring_paused`), `hr.job.pb_hiring_pause_self`.
- **C-2:** `hr.job.pb_hiring_paused` — stored boolean = role switch OR team (or a team
  above) OR company. Nothing about the role, its request, advert or candidates is
  rewritten while paused, so **restarting restores everything** by itself.
- **Stops** (plain sentence "Hiring is paused for <where>: <reason>"):
  new hiring request on every path (`pb.hiring.requisition.create`: board, recruiter
  opening a role, the plan, imports), sending one in (`_request_send_in`), opening a role
  (`_open_for_candidates`), advertising (`pb.hiring.posting.publish_for`), the careers
  page list (`hr.job._search_get_detail` adds `pb_hiring_paused = False`) and its
  application form + job-board eligibility (`pb_hiring_accepts_applications`), a new
  open role on the org chart (`pb.orgchart._do_add_open_role` → "error" answer).
- **Carries on with a warning:** candidates, interviews, agreed requests and offers.
  The Hiring board's role card gets a "Hiring paused" chip, the role page an amber
  banner ("People already in progress carry on, and offers can still be sent."), and
  the offer panel "Hiring is paused. This offer can still be sent." `_offer_block_reason`
  is untouched (test T7).
- Who may pause/restart: talent lead (`pb_hiring.group_hiring_manager`), HR managers,
  administrators. A reason is required. The change is posted on the team's/role's
  chatter.
- Screens: People › Jobs › Hiring pause (companies, teams with "paused with <team>",
  roles paused one by one) and the job page. **Not built:** the switch on the org
  chart team panel (the org chart has no team panel to patch; left for later).
- **Not done:** a role state "On hold" by `selection_add` — not needed, because the
  boolean is computed and nothing is rewritten; S6-B reads the boolean per C-2.

### 1.4 "Would rehire" mark
- `hr.employee.pb_rehire` yes / no / not sure + note + by + on, all
  `groups='hr.group_hr_user'` (PRC-W1: the employee's own login cannot read it — test T8).
  On the employee form (HR settings tab, "If they leave").
- Asked in the Exits drawer (t-inherit of `pb_offboarding.PbExitsBoard` + patch), for
  anybody on the Exits board including "Last day has passed": shown and saved only for
  people who may change exits (`pb.exits._can_write`) AND hold an HR group; a lifecycle
  reader without write sees nothing and is refused.
- Hiring board candidate card: a quiet chip "Worked here 2022–2024 · would rehire: Yes"
  (amber only for "No") when the candidate's email or phone (last 9 digits) matches a
  former (archived) employee of the reader's companies — **HR only**; a talent lead
  without an HR group, line managers and agencies never see it. Never a block.

### 1.5 Approved Decision Room plan → draft hiring requests (`pb_plan_hiring`)
- On an APPROVED plan the dock row gets **Hiring requests** and "N of M hires have a
  request". The dialog lists the plan's hires from its frozen levers
  (`state.moves`): moves with the same team, role and month are one line (people
  added). Each line: how many · role · team · month (wanted by = 1st of that month in
  the approval year; a month already past at approval is next year's).
- Ticked lines become **DRAFT** requests (`request_state = writing`, never sent in),
  created AS THE PERSON (`_require_raise` applies), with title (the job's name, or typed
  for "other roles"/whole-team lines), team (the job's own team when it sits under the
  plan's team), job, company, currency, headcount, wanted-by date and "From the approved
  plan …" in the remarks.
- **No duplicates on re-run:** `pb.hiring.requisition.(pb_plan_id, pb_plan_line_key)`
  is UNIQUE (SQL), and a line holding a request in any state is never made again.
- **Link both ways:** plan → `pb_requisition_ids`, the dialog links each line to its
  request (opens the Hiring board on that role); request → `pb_plan_id` on its form
  (shown to Decision Room users) and "From the approved plan: <name>" on the role page.
- Not made (said on the line): leavers ("People leaving are not handled here"), the
  "Other teams" bucket (choose the team on the Hiring board), a team where hiring is
  paused (probe of `pb_hiring_paused`, no dependency on `pb_org_structure`).

### 1.6 Doors
- People hub lens **Jobs** (sequence 58, `ORG_GATE`: HR officer, HR manager, talent
  lead, system; `wantsArrival` so ⌘K rows can open a part). Four parts on a quiet step
  row: Jobs (filter panel), Levels, Cost centres, Hiring pause.
- ⌘K: 4500 Jobs, 4510 Cost centres (opens that part), 4520 Pause hiring (opens that
  part). Client action `pb_org_structure.action_pb_org_jobs` (tag `pb_org_jobs`).

## 2. Hard dependencies (the handover's question)

| Module | Depends on | Why it cannot be a probe |
|---|---|---|
| `pb_org_structure` | `pb_hiring` | overrides `pb.hiring.requisition`, `pb.hiring.posting`, `pb.hiring`, `hr.job.pb_hiring_accepts_applications`, and its templates are extended (t-inherit needs the asset loaded first) |
| `pb_org_structure` | `pb_orgchart` | overrides `pb.orgchart._do_add_open_role` (Python `_inherit` needs the model) |
| `pb_org_structure` | `pb_offboarding` | overrides `pb.exits` and patches `PbExitsBoard` (JS import) |
| `pb_org_structure` | — `pb_decision_room`, `pb_vendor_access`, `pb_pay` | **not** dependencies (pay band read by probe) |
| `pb_plan_hiring` | `pb_decision_room`, `pb_hiring` | it is the glue between the two (FACTS §7 default) |
| `pb_plan_hiring` | — `pb_org_structure` | not a dependency (pause read by probe) |

Every one of these is installed on all five databases under the tenant module-sync rule
(the local template has them all). **Deploy agent: confirm `pb_hiring`, `pb_orgchart`,
`pb_offboarding`, `pb_decision_room` are installed on p0clone and sudima before
`-i`**; otherwise the install would pull them in.

## 3. Tests

Local, one database `wdgap_s8c_t` = copy of `upd_p6_t_tpl` brought to the branch
(33 modules behind HEAD `-u`), then `-i pb_org_structure,pb_plan_hiring`. Dropped at the
end with its filestore.

### 3.1 New tests — `/pb_org_structure,/pb_plan_hiring`: 16 tests, 0 failed, 0 errors

| # | Case | Result |
|---|---|---|
| T1 | silent install: no level, no cost centre, no linked contract, nothing paused; the daily job exists and has nothing to do (0); Jobs head answers zeros; one lens (seq 58), three palette rows (4500–4520) | PASS |
| T1b | no "Odoo" in any user-visible string (templates, `_t`, `_()`, `string=`/`help=`) | PASS |
| T2 | levels: add, order, move up, duplicate name refused, archive refused while used; job page saves level + description (paragraphs); HR officer reads but cannot change; outside HR sees nothing; filter "No level yet" | PASS |
| T3 | list kept in step: code any case, name ignoring spaces; "add them to the list" writes no contract (write dates unchanged); typing the text links; code in use cannot change; in-use entry cannot be deleted; duplicate code refused | PASS |
| T4 | **history**: direct write of the text → finished payslip line keeps "OLD", a past-month draft keeps "OLD", this month's draft follows; move dated today via the screen → contract text = code, finished line unchanged; amounts and wage unchanged; past date refused | PASS |
| T4b | later date waits (job makes 0), a newer change replaces the waiting one, on the day the job makes it once (old text kept on the move), a second run makes nothing | PASS |
| T5 | team's usual cost centre: only new contracts with none; existing and typed ones untouched | PASS |
| T6 | multi-company: another company's code never links, is not listed, cannot be moved to | PASS |
| T7 | team pause: reason required; team and sub-team paused, other team not; C-2 boolean on the job; new request refused with the reason; other team still works; existing request: send-in, open and advert refused; offer rule unchanged; board row carries the warning; restart restores, new request works, the old request untouched | PASS |
| T7b | rights (HR officer / plain user refused); role pause only that role, request on that job refused; company pause covers every team (shown as "paused with …"), refused with the reason; restart | PASS |
| T7c | careers page: list domain carries the pause filter; application form refused while paused, open again after; org chart "add open role" answers an error with the reason and creates no job | PASS |
| T8 | would-rehire: HR manager sees and sets it in the Exits drawer; an HR officer who may only read exits sees nothing and is refused; the employee's own login cannot read the field; archived leaver applies again → HR sees "Worked here … · would rehire: Yes", the talent lead (no HR group) does not | PASS |
| T9 | plan lines: moves merged per team/role/month (2+1 = 3), the job's own team, wanted-by next March / this December, leavers and the bucket not makeable; dock "0 of 3" | PASS |
| T10 | drafts once: missing title refused; two made (writing, headcount 3, team, date, job, remarks); second press makes 0; SQL unique refuses a copy; role row names the plan; deep link carries `pb_role_id`; dock "2 of 3" | PASS |
| T11 | rights and states: a planner who cannot raise requests sees lines, press refused; outside the room refused; a draft plan has no lines and makes nothing | PASS |
| T11b | paused team: line says so with the reason, makes nothing; restart → makeable | PASS |

### 3.2 Existing suites (no file of these modules is edited; run because the new modules extend them)

Baseline first, on the same copy BEFORE the new modules existed:
`-u pb_hiring,pb_orgchart,pb_offboarding,pb_decision_room` with
`/pb_hiring,/pb_orgchart,/pb_offboarding,/pb_decision_room` → **692 tests, 11 failed, 2 errors**.

After, with both new modules installed (same four suites + the two new ones):
**708 tests, 11 failed, 2 errors — the failure set is IDENTICAL to the baseline**
(`diff base.fails after.fails` empty; 708 = 692 + the 16 new tests):

| Pre-existing (same before and after) |
|---|
| ERROR `TestRecruitPrivacy.test_02b_unsharing_regenerates_the_file_tokens`, `test_08_the_resume_bank` |
| FAIL `TestClientReview.test_hiring_only_cannot_read_access_directory` |
| FAIL `TestDecisionRoomFacade.test_t22_only_the_planning_lead_changes_the_assumptions`, `test_t2_the_baseline_is_this_companys_own_roster` |
| FAIL `TestDecisionRoomStaticContract.test_t14_the_people_hub_edit_kept_every_promise_that_module_makes` |
| FAIL `TestRecruitInterviewsP5.test_07b_without_google_nothing_changes` |
| FAIL `TestRecruitJoining.test_11_the_numbers_filters_funnel_ageing_leadership_and_exports` |
| FAIL `TestRecruitPrivacy.test_02_the_manager_sees_the_card_and_a_sentence_until_shared` |
| FAIL `TestRecruitPrivacyFiles.test_02_tokenised_cv_link` |
| FAIL `TestRecruitStages.test_13_set_up_has_six_cards_and_none_is_a_dead_end` |
| FAIL `TestRegistersP9.test_08_the_hub_names_the_two_registers_between_overview_and_interviews` |
| FAIL `TestTheCover.test_t7_who_is_asked_to_agree_it_is_said_out_loud` |

`/pb_hub,/pb_people_hub` (the lens and palette registries the new modules plug into),
with the new modules installed: 79 tests, 3 failed —
`TestHubKitStaticGates.test_the_kit_stacks_nothing_above_twenty` (reads pb_hub's own
SCSS: a `z-index: 30`), `TestPeopleHubStatic.test_the_contracts_action_opens_the_board_with_a_way_back`
(reads the contracts action's context, set by pb_contract_lifecycle) and
`test_the_lens_order_matches_the_mockup` (reads only `people_hub.js`'s own config list).
None of the three reads a file or record of the new modules; **a run on a copy without
them was not made** (one database at a time) — the go-live agent's combined run should
confirm they are pre-existing. pb_hub's cross-module palette/lens gate tests
(`test_palette_lens_gates`, which walk every module's JS) all PASS with the new rows.

Final re-run of the new suites after the walk fixes (on the walk copy, which now holds
DEMO walk data): 15 of 16 pass; T1 (silent install) fails there only because the walk
data paused two roles — it passed on the clean copy (runs `t3` and `after` above).

### 3.3 Static gates
- PO parse gate (`PoFileReader`) on all six i18n files: parse clean; vi/id: 195 code
  terms reaching a screen + 105 model terms (`pb_org_structure`), 30 + 13
  (`pb_plan_hiring`). Every msgid translated in both languages; each entry carries
  `#. module:`, the `odoo-python`/`odoo-javascript` marker and a `code:addons/…:0`
  occurrence (exported with `odoo-bin i18n export`, then filled). The `.pot` ships too.
- Sentences translated whole (PRD-3): counts and names go through `_t("… %s …")`
  helpers, not text around `t-esc`.
- No emoji, no gradients, Lucide icons from the shared registry; no JS global in a
  template expression.

### 3.4 Browser walk
Local copy seeded with DEMO people (scratch `seed_walk.py`: 4 teams, 6 jobs, 8 people
with typed cost centres, an exit checklist, an approved plan, one request), server with
`--max-cron-threads=0`, Claude in Chrome at 614 px wide (the window cannot be resized —
QF2-G7 — so the phone layout was walked; wide layouts are plain CSS grids). Everything
inside its hub. Console clean at the end (one error found and fixed, below).

- People › **Jobs**: step row (Jobs / Levels / Cost centres with the amber "Contracts
  not on the list" flag / Hiring pause), filter panel with views and counts, list rows.
  Levels: added "Associate" and "Senior", ordered. Job page (DEMO Sales associate): set
  level Senior + description, saved; paused hiring for the role with a reason → amber
  sentence on the page, "Restart hiring for this role".
- Cost centres: "On contracts, but not on the list" (CC-SALES and cc-sales counted as
  one), **Add them to the list** → "Added to the list: 3. No contract was changed.";
  Move people: Head office, team DEMO Operations, today → preview "People who move to
  Head office from …: 3." → moved; changes list shows before → after.
- Hiring pause: paused DEMO Sales with a reason → DEMO North shows "Paused with DEMO
  Sales"; the role paused one by one is listed with Restart.
- Hiring board: role card chip "Hiring paused"; role page header chip; Details tab
  banner with the reason; **Publish** → refused with "Hiring is paused for this role:
  Store budget review until March". (The role page's own "Next: Publish" card still
  offers the button — pb_hiring's card; the press is refused with the sentence. Left as
  is: hiding it means editing pb_hiring's card logic.)
- Exits drawer (DEMO Khanh Ho): "Would we hire them again?" Yes / No / Not sure + note;
  Yes saved, "Seen by HR only. Administrator · date".
- Decision Room: approved plan row shows "Hiring requests" and "0 of 2 hires have a
  request"; the dialog lists the Sales line as paused (with the team's reason), the
  Operations "Other roles" line asks for a title, the leaver line under "Not handled
  here"; made one draft ("Draft hiring requests made: 1. Nothing has been sent in."), the
  line now links "HR-… · DEMO Forklift driver · Being written"; the link opens the Hiring
  board on that role, whose Details tab says "From the approved plan: DEMO Plan 2027".

Fixed during the walk: the step row did nothing (QuietSteps calls `qStepPick` without
`this` inside a `t-call` — bound with `t-set`); "1 roles"-style plurals reworded as
"Label: N"; numbers in the phone layout carried no label (added "People", "To hire",
"Contracts", "Teams", "Waiting" for narrow screens); the job description lost its
paragraphs on a second save (now one paragraph per line both ways); a change made for a
contract with no cost centre showed the new one as "before" (now "—").

## 4. Contracts other phases rely on

- **C-2 (S6-B):** `hr.job.pb_hiring_paused` — stored Boolean, indexed; True when the
  role, its team (or a team above it) or its company is paused. Probe:
  `'pb_hiring_paused' in env['hr.job']._fields`. Also available:
  `hr.job.pb_hiring_pause_sentence()` → '' or the translated sentence, and
  `hr.department.pb_hiring_paused` (stored, recursive).
- `pb.hiring.requisition.pb_plan_id` / `pb_plan_line_key` (unique pair).
- `hr.contract.pb_cost_centre_id` (stored compute of the text, read-only) and
  `pb.job.level` / `hr.job.pb_level_id` — for the people-reports team's later Explorer
  column (C-5).
- Context key `pb_cost_centre_change_date` on `hr.contract.write`: the date a
  cost-centre change takes effect (history guard). Without it: today.
- Shared seams: `pb.records.desk._master_fields` NOT overridden;
  `pb.contract.review._build_new_contract` NOT overridden (the text is already
  carried); `hr.contract` new field `pb_cost_centre_id` (S8-A uses other names).
  `pb.hiring._row` is extended by both new modules (each adds its own keys only).

## 5. Deploy notes (for the step's go-live agent)

- Install order: `-i pb_org_structure` then `-i pb_plan_hiring` (or together) on
  payobook, payobook_template, p0clone, rize, sudima; asset purge after.
- Tier: **normal for `pb_plan_hiring`; risky for `pb_org_structure`** — it adds a stored
  compute on `hr.contract` (computed on install for every contract: all empty, the list
  is empty) and it **changes how every cost-centre edit treats finished payslips**
  (they keep their cost centre). No payslip figure changes; a recompute rehearsal is
  not needed for figures, but count before/after on a copy:
  `select count(*), count(distinct costcenter) from hr_payslip_line` and a sample of
  done payslips' line `costcenter` must be identical after install.
- Counts to measure on copies of rize and payobook (FACTS §12.2; no live access in this
  phase):
  - contracts with a typed cost centre: `select company_id, costcenter, count(*) from hr_contract where coalesce(trim(costcenter),'') <> '' and state in ('open','draft') group by 1,2 order by 3 desc;`
  - contracts whose job differs from the employee's job: `select count(*) from hr_contract c join hr_employee e on e.id = c.employee_id join hr_version v on v.id = e.version_id where c.state = 'open' and coalesce(c.job_id,0) <> coalesce(v.job_id,0);`
- Silent install: no data rows, one daily job that does nothing until somebody dates a
  change, no email anywhere, nothing paused.
- The new modules touch no pay calculation: no rize rehearsal is needed for S8-C on its
  own (S8-A/B need one).

## 6. Owner questions (plain words)

- **Q1. Job level on people's records.** The job page now has a level (for example
  "Senior"). People's records also have a typed "Job level" box, and some pay set-ups
  read that box. Should setting a job's level also fill the box for everybody in that
  job? *Recommended: no, keep them separate for now* — filling it could change pay where
  a pay set-up reads it; HR can still type it per person.
- **Q2. Old cost-centre corrections.** From now on, changing a person's cost centre never
  changes payslips already finished — they keep the cost centre they were paid under.
  Before, a correction also rewrote old payslips. Is that what you want? *Recommended:
  yes* (finished payslips are history). If you sometimes need to correct a typo on past
  payslips, that would be a separate, deliberate tool.
- **Q3. Pause switch on the org chart.** You can pause hiring for a company, a team or a
  role on People › Jobs. Do you also want the switch on the org chart? *Recommended:
  later*, Jobs covers it.

## 7. Left for later

- Explorer cost-centre / job-level column (C-5, people-reports team): reads
  `hr.contract.pb_cost_centre_id` and `hr.job.pb_level_id`.
- Stamping the cost centre on a payslip line at compute time instead of the related
  store (an `om_hr_payroll` edit — FACTS §6.1): the history guard makes it safe for
  now; the proper fix is out of S8 scope.
- Pause switch on the org chart; a "paused" mark on org-chart open roles.
- Job advert already sent to an external job board is not withdrawn by a pause (the
  careers page and new adverts stop; existing external postings stay until the board
  next reads them).
- A job's level shown in the employee side panel; level as a route condition in
  approvals.
- Decision Room "other teams" bucket lines: pick a team in the dialog.
- Candidate match also by national ID (via `pb.person`).

## 8. Gotchas → ledger rows

- **S8C-1** A contract created with `company_id` in its values gets NO `department_id`
  (nor job/schedule): `hr_contract._compute_employee_contract` computes all four
  together and the ORM protects every field of a compute method when one of them is in
  the create values. Read `contract.department_id or contract.employee_id.department_id`.
- **S8C-2** `hr.department.complete_name` is not stored on this build: `order='complete_name'`
  raises "Cannot convert … to SQL". Sort in Python by `display_name`.
- **S8C-3** `hr.payslip.line.costcenter` is a stored related of the contract's text; to
  keep history, wrap the contract write in `env.protecting([line_field], history_lines)`
  — protected records are removed from the recompute marking (`models.py` `modified`).
- **S8C-4** `pb.exits.get_exit` (base) reads `employee.country_id`, which needs an HR
  group: a lifecycle user without `hr.group_hr_user` gets an AccessError on the whole
  drawer (pre-existing, not changed).
- **S8C-5** OWL template expressions cannot use `Number(...)` (OWL's allowed globals
  are only `Math`, `RegExp`, `Array`, `Object`, `Date`, `console`, `window`) — use a getter.
- **S8C-7** `pb_import_kit.QuietSteps` calls `qStepPick(st.key)` from inside a
  `t-call`: a component METHOD named `qStepPick` is called without `this` ("Cannot read
  properties of undefined (reading 'state')"). Bind it in the call:
  `<t t-set="qStepPick" t-value="(key) => this.qStepPick(key)"/>`.
- **S8C-8** Parallel builders' local walks share cookies on `127.0.0.1` across ports (the
  session was logged out by another builder's server: "Logged into database
  'wdgap_w2d2_t', but dbfilter rejects it"). Walk on `http://<phase>.localhost:<port>`
  (Chrome resolves `*.localhost` to loopback with its own cookie jar).
- **S8C-6** A test that expects a SQL unique violation logs `odoo.sql_db: bad query` at
  ERROR; wrap it in `mute_logger('odoo.sql_db')` so a "no ERROR in the log" gate stays clean.
