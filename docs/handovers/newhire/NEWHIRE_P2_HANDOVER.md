# NEWHIRE P2 — Schedule and time off, Welcome and first day

Read first: `NEWHIRE_LEDGER.md` (binding, incl. NH11–NH18), `NEWHIRE_P1_REPORT.md` (§3 deviations and §6 — the structure you
inherit), `NEWHIRE_FACTS_CORE.md` §H (schedule), `NEWHIRE_FACTS_ONBOARD.md` §F (joining checklist), §G (sign-ins),
§H (equipment), §I (letters), §J (custom fields). **Do not re-derive.** Then open the POC and click steps 4 and 6.

Work ONLY in `/Users/adity/Documents/GitHub/gitlocal-worktrees/newhire` (branch `newhire`). No deploy, no server access.
The walk database `nh1_base` and its seed script (P1 report §2.3) are yours to reuse and extend.

**Hero moment of this phase**: step 6's "What happens, and when" — a dated timeline built from the real joining checklist
that re-flows the instant the first day, the manager, the sign-in choice or an equipment chip changes. HR sees the whole
first fortnight before pressing a single button.

## 1. Scope

1. **Step 4 Schedule and time off** replaces `StepSoon` for `sched`.
2. **Step 6 Welcome and first day** replaces `StepSoon` for `welcome`.
3. On approval the hire now also gets: working week, late-rule group, clock number, sign-in, buddy, equipment requests,
   contract letter, the tenant's own fields, and **the joining checklist opened** (which is what puts the person on the
   New joiners board).
4. Step 2 "What this decides" gains the tile **Contract letter** (the template language that will be used, or "No letter
   wording for <country> yet").
5. Step 7 gains the rows for steps 4 and 6 and the "When you press the button" list becomes true to the choices.
6. Three carried-over fixes from P1's open questions:
   a. **People › Employees writes every wage in the company currency** (NH18): fix in `pb_people` at the source — the
      list row, the side figure and the "Monthly wage" KPI must use the contract's currency (the KPI already groups by
      currency on screen: find how and feed it the contract currency). Smallest edit, with a test in `pb_people`'s suite.
   b. **Contract "Employee category" (`type_id`)**: for a studio hire choose it by country + kind instead of "first row".
      Add `contract_categories(country_code, contract_kind) -> [{id, name, suggested:bool}]` on the facade: suggested =
      the best match by the category's own country/kind fields if the model has them, else by name containing the country
      name and the kind word; no confident match → none suggested. Step 3 shows a "Contract category" select ONLY when
      the company has more than one category; preselect the suggestion; required when shown. Send `type_id` in the values;
      `create_contract` ext writes it. Report exactly which fields `hr.contract.type` has on this build.
   c. **A kept draft vs a new org-chart prefill**: ask in an in-page dialog "Carry on with <name>, or start <new role>?"
      (two buttons, safe default = carry on) instead of replacing silently.

### Binding non-goals
- No details / papers / bank / welcome link / asked-items tracker (P3). The sign-in choice here only decides how the
  sign-in is created; the "finish your details" link is P3.
- No "From Hiring" (P4), no payslip example (P4), no `.po` (P5), no Learn (P5).
- Do not depend on `pb_workforce_setup` (installed on 2 of 5 databases) — feature-detect.
- Do not change the joining checklist template, its steps, mails or the scheduled job.
- No new scheduled jobs. No new approval process.

## 2. Plumbing decisions (made — follow them)

### 2.1 Dependencies
Add to `pb_new_hire` `depends` (all installed on all five live databases, FACTS_ONBOARD §M3): `pb_onboarding`,
`pb_zoho_bridge`, `pb_assets`, `pb_doc_contracts`, `pb_form_studio_people`, `biz_access`, `pb_clock`. Feature-detect with
`in self.env`: `pb.shift.pattern` (working weeks), `pb.workforce.setup`, `pb.attendance.policy`, leave-setup fields.
Verify no dependency cycle; bump to 19.0.1.1.0.

### 2.2 The rule for everything this phase writes on approval
The person and the contract are the core (P1: a failure there rolls the approval back). **Everything in this phase is a
"welcome leg"**: each leg runs AFTER the core, in its own savepoint, in the fixed order below. A leg that fails does not
undo the hire: it posts one plain sentence on the employee's chatter ("The working week could not be set: <reason>. Set
it from Workforce.") and is returned in `result['legs'] = [{key, ok, message}]` so the done card (fast lane) and the
approver's result can show it. This is the same contract Hiring's "Confirm they joined" uses (FACTS_ONBOARD §K1.4).
Implement the legs in `models/welcome_legs.py` as one small method each, called from the P1 `create_employee` extension
when `pb_nh` and applied. All leg inputs ride in the values dict (JSON-plain, NH8) and are re-validated on replay.

Order: `late_rule` → `clock` → `week` → `own_fields` → `login` → `case` (joining checklist) → `buddy` → `equipment` →
`letter`. (`case` must come after login so the day-one "sign-in details" step finds a login; buddy and equipment need the case.)

New values keys: `pb_attendance_category` ('worker'|'manager'), `pb_clock_code`, `week_id`, `own_fields` ({x_name: value}),
`login_mode` ('email'|'code'|'none'), `open_case` (bool, default True), `buddy_id`, `equipment` (list of category ids;
`None` = not chosen → today's default behaviour), `letter` (bool), `type_id`.

### 2.3 Step 4 — server
- `schedule_options(department_id, country_code, date_start) -> {weeks:[{id, name, days:[{label, on:bool, start, end}×7],
  hours_per_week, team_default:bool}]|false, weeks_reason, late_groups: bool (policy feature present), clock: bool,
  leave:[{name, days_per_year}], holidays:{count_next_12_months:int, next:{name,date}|false}}`.
  - Weeks = active `pb.shift.pattern` of the company; `team_default` = the pattern whose `department_id` is the team
    (FACTS_CORE §H). Day strip for week 1 of the cycle — reuse the pattern's own slot reading (the method
    `pb.workforce.setup.person_week`/`_week_row` uses, or `pb_shift_patterns`' board row) rather than re-deriving
    `day_index`. Feature absent or no patterns → `weeks False` + `weeks_reason` "No working weeks are set up yet, so
    <first name> follows the company's usual working hours." (and, when `pb.workforce.setup` is installed and the user may
    open it, a quiet "Set up working weeks" link).
  - Leave: `hr.leave.type` rows that earn (`pb_ls_earning != 'none'`) for the country via `pb.timeoff._type_country`
    (FACTS_CORE §H), `pb_ls_days_per_year`. Display only. None → the row is not shown.
  - Holidays: count of the company calendar's public-holiday rows in the next 12 months (read how `pb.holidays` lists
    them). Wording: "Your company's holiday list applies: N days off in the next 12 months." (ledger §2 — never "follows
    the country of work"). Zero → "No public holidays are loaded for your company yet."
- `check_clock(code) -> {ok, message}` — unique per company (the model's own constraint is the judge at write time; this
  is the friendly pre-check).
- Legs: `late_rule` writes `pb_attendance_category` (field-exists check; pass it on the employee create through the P1
  create hook if simpler — then it is not a leg, say which); `clock` writes `pb_clock_code` (duplicate at replay time →
  leg fails with "Clock number <code> was taken by <name> meanwhile."); `week` creates the member row from the first day
  using the SAME internal helper `assign_week` uses after its gate (find it in `pb_workforce_setup/models/people.py`;
  when that module is absent, create the `pb.shift.pattern.member` row exactly as `pb_shift_patterns`' own board method
  does — call that method with sudo behind our HR gate rather than writing fields by hand; NH6).

### 2.4 Step 6 — server
- `welcome_options(draft) -> {login:{modes:[{key, label, sub, available:bool, why_not}], default}, buddies: via
  find_people, equipment:[{id, name, icon, usual:bool}], letter:{available:bool, language, name}|{available False,
  reason}, own_fields:[{name, label, help, kind, required, options, supported:bool}], case:{available:bool, template_name},
  timeline:[{when:'YYYY-MM-DD', title, who, sub, kind:'before'|'day'|'after', past:bool}]}`.
  - **Sign-in modes** (FACTS_ONBOARD §G): `email` — available when a work email is typed ("An invitation goes to <email>
    on the first day."), created by `pb.zoho.pipeline._auto_create_login(employee, company, summary)`, sent on day one by
    the checklist's own step; without a work email → not available, `why_not` "Add a work email in step 1, or use the
    employee number." `code` — `pb.access.create_worker_logins([emp_id])` THEN write `pb_portal_user_id` (§G note);
    available when the person will have an employee code at creation (find how `_pb_sign_in_code` gets it; if a code is
    only assigned later, say so and mark unavailable with the reason). The first password must never be stored in the
    payload or the chatter: after approval HR prints the slip from Access › Logins for workers — verify that screen can
    show/print the slip for an already-created login; if it cannot, the leg's message says exactly where the password is
    obtained, and you report the gap. `none`. Default = `email` if available, else `code` if available, else `none`.
  - **Equipment** = active `pb.asset.category` rows; `usual` = `auto_assign_at_joining`. The chips start on the usual
    ones. Leg: after the case is open, for every chosen category make sure ONE open `pb.asset.request` exists for the
    person (the checklist's own `_raise_asset_requests` already made the laptop one — do not duplicate; match by
    employee + category), created the same way and in the same state the laptop request is created today, `needed_by` =
    first day, linked to the laptop/equipment task when there is one. Laptop chip OFF → the laptop request the case
    raised is cancelled and its task skipped with the note "Not needed for <name>." (use the task's own `action_skip`).
  - **Letter**: `pb.contracts.contract_document_available`-style check for a hypothetical is not possible — decide
    availability from the templates (`pb.letter.template`, `letter_type='employment_contract'`, country swap rule in
    FACTS_ONBOARD §I: country template if one exists, else the generic English one). Tile + toggle sentence: "In
    <language>, filled from step 3 and saved to <first name>'s documents for signing on paper." Leg: `contract_document_save(contract_id)`;
    a `{ok: False}` answer or `pay_blocked`/`missing` is a failed leg with that answer's own sentence.
  - **Own fields** (Form builder): `fields_for('hr.employee', 'all')` filtered to the chosen country (`countries` empty or
    contains it). Supported input kinds: text, long text, whole/decimal number, date, yes/no, single choice. Anything else
    (links to other records, files, multi-choice…) is listed read-only as "Fill this on <first name>'s record after
    approval." **Required supported fields are required in the studio** (step 6's rail text becomes amber "N of your own
    fields are needed" and Send is blocked with a jump-to-field), because `write_values` enforces `is_required`. Leg:
    `write_values('hr.employee', emp_id, vals)`; `{ok False}` → failed leg quoting the field labels.
  - **Joining checklist**: `pb.journey.template.pick_for('onboarding', country, company)`; none → `case.available False`
    and the timeline shows only the first day with "No joining checklist is set up." Leg `case`:
    `pb.zoho.pipeline._open_case(employee, 'onboarding', first_day, company)` then `_after_onboard(case, {...})` exactly
    as `pb_hiring/models/offer_closure.py:430-458` does (read it; pass the same shape). The P1 trial-end write stays —
    confirm `setup_probation` leaves an already-set date alone (FACTS_CORE §D says "only when empty") with a test.
  - **Buddy**: `buddy_id` chosen → leg calls `pb.onboarding.buddy_choose(employee_id, candidate_id, case_id)` (it writes,
    plans catch-ups and ticks the step). Empty → nothing: the checklist's first step asks the manager.
  - **Timeline**: one entry per step of the picked template: `when` = first day + `offset_days` for `doj` anchors, today
    for `case_open`; `who` from the step's `assignee_rule` as words ("Manager: <manager name>", "IT", "HR", "<first
    name>", "Buddy"); steps with `automation_key` say "Sends itself". Plus synthesized entries that are TRUE: "First day"
    (kind `day`), "Trial period review" at trial end minus the policy's `evaluation_lead_days` (when a trial is set), and
    the 7/30/60-day check-ins if `_plan_pulses` will plan them (read `CHECKIN_PLAN`/pulse marks; do not invent). `past`
    = date ≤ today → rendered "Straight away". This is display arithmetic over the template's own fields — it must not
    duplicate `_generate_tasks`; add test W9 proving the preview dates equal the real task due dates after apply.
    Equipment chips and the sign-in mode change the entries (no laptop chip → no laptop line; `none` → the sign-in line
    reads "No sign-in yet").
  - `open_case` False (HR switches "Start the joining checklist" off) → buddy/equipment controls collapse with "These
    need the joining checklist." and the timeline shows the first day only.

### 2.5 Client
- `step_sched.js`, `step_welcome.js` replace `StepSoon` for their keys (keep `StepSoon` for `docs`). Add the new keys in
  the three places P1 report §6.5 names; write ONE helper so a key is declared once (refactor `blankDraft`/`sendDraft`/
  server `DRAFT_KEYS` to a single table if that is cheap; otherwise leave and say so).
- Step 4 layout per POC `vSched`: working-week select with the teal "Same as the rest of the team" line + 7-day strip that
  animates on change; late-rule segmented control (only when the feature is present); clock row = a switch "Clocks in at
  <site>" + a clock-number box (optional; live `check_clock`, debounced) — NOT the POC's "next free number" sentence;
  leave row; holiday row.
- Step 6 layout per POC `vWelcome`: sign-in row (segmented, unavailable modes shown disabled with `why_not` as the
  sub-line — never hidden); buddy row (search picker, "Manager chooses" default); equipment chips; letter switch; "Your
  own fields" card (designed empty state when the tenant has none: the card is not shown at all); the timeline card
  (enter animation per row, 30 ms stagger, reduced-motion safe; "Straight away" rows first).
- Rail status: `sched` done text = week name or "Company's usual hours"; `welcome` done text = "Checklist ready" /
  "No checklist" ; both stay optional unless required own fields are empty.
- Step 7: rows for schedule and welcome with Change; the "When you press the button" list reads from the same
  `welcome_options().timeline` head (next 3 things) so it cannot drift.
- Done card (applied): show the legs — green ticks collapsed into one line when all ok ("Sign-in, checklist, 2 equipment
  requests and the contract letter are ready."), each failed leg as an amber row with its message. Pending: unchanged.
  Add the button "See new joiners" (opens the New joiners board action — find its xmlid in `pb_onboarding`).
- The approver's drawer (`_proposal_rows`) gains: Working week, Clock number, Sign-in, Buddy, Equipment, Contract letter,
  Joining checklist, and one row per own field.

## 3. Safety rails
- Legs never run before the core commit path succeeds, never run for non-`pb_nh` callers, and never raise out of their
  savepoint (except programming errors in tests — make failures visible with a test-only context flag).
- No password, token or sign-up link is ever written to the payload, the chatter, the result dict or a log line.
- Mail: opening the case and creating a login must not send any email at apply time that today's Hiring path does not send.
  List every mail/activity the apply now triggers in the report.
- Everything behind `require_hr`; sudo only inside legs for the documented role gaps (NH6), never for reads shown to the user
  that the user's role may not see (buddy/people search stays in the user's own rights).

## 4. Tests (tag `newhire`) — W1…
W1 `schedule_options` with/without patterns, team default flagged, leave rows by country, holiday count.
W2 legs late rule + clock: written; duplicate clock at replay → failed leg, hire still created, chatter sentence.
W3 leg week: member row from the first day in the right pattern/team; module-absent path covered by patching the feature check.
W4 own fields: definitions filtered by country; required-missing blocks `send` with `{ok False, step:'welcome', field}`;
   values written on approval; unsupported kinds reported `supported False`.
W5 login `email`: portal login linked (`pb_portal_user_id` + `user_id`), no mail at apply; `code`: login = employee
   code, `pb_portal_user_id` set, no password anywhere in payload/chatter/result; `none`: no user.
W6 case: one onboarding case, anchor = first day, tasks generated; second apply (idempotent replay) opens no second case.
W7 buddy chosen → `buddy_id` set, buddy step ticked; empty → step open for the manager.
W8 equipment: usual chips → one request per category, no duplicate laptop request; laptop off → request cancelled, task
   skipped; `open_case False` → no requests.
W9 timeline preview dates == real task due dates after apply (same first day, same template).
W10 letter: country template picked (VN/ID), generic fallback, saved as an employee document; failure → failed leg.
W11 `contract_categories` suggestion + `type_id` written; one category → not asked.
W12 `pb_people` list/KPI currency fix (in `pb_people`'s own tests).
W13 trial end set by P1 survives the case opening.
W14 approver rows for the new keys. W15 static gates still pass; P1's 24 tests still pass.
Browser walk (extend the seed: two working weeks, an attendance policy, asset categories, a joining template, 3 own
fields incl. one required and one country-limited): C1 step 4 defaults + change week (strip animates); C2 clock number
taken → friendly message; C3 step 6 timeline re-flows on first-day change, laptop chip, sign-in mode; C4 required own
field blocks Send and jumps to it; C5 full send → approve as second user → New joiners board shows the person, tasks
dated as previewed, equipment requests exist, letter in documents, own fields on the record, sign-in created;
C6 fast lane done card with one deliberately failed leg (amber row); C7 no patterns / no template / no own fields states;
C8 org-chart prefill vs kept draft dialog; C9 Employees list shows the IDR wage as Rp; C10 340 px root width; C11 console clean.

## 5. Report back — `NEWHIRE_P2_REPORT.md`
Same seven sections as P1 (built + files outside `pb_new_hire` · W/C results · deviations · design-bar score · new
gotchas NH19+ · open questions · commits). Add: the list of mails/activities triggered at apply (rail 3), and what you
found about printing a worker sign-in slip after creation. Commit feature-scoped with explicit paths. Do not push.
