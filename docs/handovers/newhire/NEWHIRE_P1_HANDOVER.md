# NEWHIRE P1 — the studio, the three required steps, check and send

Read first, in this order: `NEWHIRE_LEDGER.md` (binding), `NEWHIRE_FACTS_CORE.md` (verified plumbing — **do not re-derive**;
§A, §B, §C, §D, §E, §G, §I matter here), then open `docs/design/new-hire-studio-poc.html` in a browser and click through
steps 1, 2, 3 and 7 and the right-hand panel. The POC is the design of record for layout, wording, spacing, colour and
motion, except where ledger §2 says the POC is not true to the product.

Work ONLY in `/Users/adity/Documents/GitHub/gitlocal-worktrees/newhire` (branch `newhire`). No deploy, no server access.

**Hero moment of this phase**: pick a team and watch "What this decides" light up — pay scheme, currency, trial period —
while the right-hand record assembles itself and the wage box switches to the right currency. Nothing is chosen twice.

## 1. Scope

A new module **`pb_new_hire`** (19.0.1.0.0):
1. The **New Hire Studio** client action: top bar (crumb People › Employees › Add employee, progress, "Skip to the end"),
   7-step rail grouped Required / Optional, with defaults / Finish, the stage, and the right panel "The record so far"
   (POC `.top`, `.steps`, `.stage`, `.pv`).
2. **Step 1 Who is joining**, **Step 2 Role and place**, **Step 3 Contract and pay**, **Step 7 Check and add** — fully
   working, ending in the existing new-hire approval.
3. Steps 4–6: real rail entries (state `todo`, text "Arrives next") and, in the stage, ONE calm card with the step's
   question as heading and one sentence saying what will be set here and that today the team defaults apply. No fake controls.
   They do not block sending.
4. Right panel in P1: avatar ring + name + role, the facts list, **Payroll-ready** (two honest lines), **Paid by** card
   (scheme name, currency, the one-line reason), and where the payslip box will be a quiet line "A first-payslip example
   appears here in a later release." No fake numbers. "Who does what" bar is P3.
5. **Takeover of the old door** from inside `pb_new_hire` (clone `pb_workforce_setup/static/src/js/takeover.js`): the tag
   `pb_onboard_wizard` is re-registered with `{force: true}` to a tiny component that opens the studio, forwarding
   `params.prefill` (org chart keys, FACTS §A.1). `pb_people`'s button therefore opens the studio wherever `pb_new_hire`
   is installed and the old window everywhere else. Do not edit `pb_people`, `pb_orgchart` or `pb_people_advanced` JS.
6. Parity with what the old window did through patches: the pay-scale hint and pin reason (`joiner_suggest`, FACTS §G.2,
   §A.5) and the optional bank block is NOT in P1's screen (bank moves to step 5 in P3) — see non-goals.

### Binding non-goals
- No schedule/clock/leave (P2), no welcome step, sign-in, buddy, equipment, letter, custom fields, joining checklist (P2).
- No details/papers/bank on this screen, no welcome link (P3). The Payroll-ready panel therefore says
  "Bank account: add it from the employee's side panel after approval" in P1.
- No "From Hiring" and no "Many at once" tiles (P4); step 1 has no source tiles in P1 — just the form.
- No first-payslip example (P4). No `.po` files (P5). No Learn changes (P5).
- No per-person scheme picker (D3). No new approval process, states or inbox work.
- Do not change `create_employee` / `create_contract` behaviour for callers that do not send the new keys.

## 2. Plumbing decisions (made — follow them)

### 2.1 Module
`pb_new_hire/` at the repo root. `depends`: `pb_people_advanced`, `pb_hub`, `pb_import_kit`, `pb_scheme_map`,
`pb_probation`, `pb_employee_form_tidy`. Everything else is feature-detected (`'pb.pay.bands' in self.env`,
`'pb.pay.scales' in self.env`). Verify each dependency is real and creates no cycle; verify all six are installed
on every live database per FACTS_ONBOARD §M's matrix and report any that is not. `views/studio_action.xml`:
`ir.actions.client` `action_new_hire_studio`, name "Add employee", tag `pb_new_hire_studio`. Assets in
`web.assets_backend`. Root element `.pbim.pbnh`; tokens copied from `.pbim.pbws` with the new prefix (FACTS §B.4).
One XML template file, one SCSS file, JS split: `studio_util.js`, `step_who.js`, `step_role.js`, `step_pay.js`,
`step_soon.js` (the calm card for 4–6), `step_check.js`, `record_panel.js`, `new_hire_studio.js`, `takeover.js`.

### 2.2 Small factor-outs in modules we do not own (pure refactors, each with a test in its home module)
1. `pb_scheme_map/models/pb_scheme_map.py`: `resolve_for_team(department_id, company_id, cycle_type='any', on_date=None)
   -> {config_id, config_name, rung, via}` built from the body of `resolve_many`'s rungs department / division / only
   (FACTS §C.4). `resolve_many` must call it for those rungs so there is one implementation; results for existing
   employees must be byte-identical (run `pb_scheme_map`'s suite). If the body cannot be shared without behaviour risk,
   STOP that refactor, implement `resolve_for_team` beside it reusing the same private helpers, and say so in the report.
2. `pb_probation/models/probation_policy.py`: `policy_for_country(country, company)` returning the policy record
   (first match, then the country-less row — same search `policy_for` does after its ladder); `policy_for` calls it.
3. `pb_hr_payroll_formula/models/contract_fill_in.py` + `formula_config.py`: `hr.formula.config._pb_usual_answer_rules()`
   returning the rules the fill-in would use (the filter at `contract_fill_in.py:516-522`, same sort); `_pb_fill_one` calls it.

### 2.3 Server facade `pb.new.hire` (AbstractModel, `models/studio.py`)
Gate: `require_hr(env)` from `pb_people_advanced` on every public method (same AccessError sentence as today). Read the
company with sudo after the gate (WS2). Everything is scoped to `self.env.company`.

- `load(prefill=None) -> {can_send, company:{id,name,country_code}, today, countries:[{code,name}], teams:[{id,name,
  manager_id,manager_name}], jobs:[{id,name,department_id|false}], managers: via find_people, sites:[{id,name}],
  nationalities:[{id,name,code}], approval:{needs:bool, with_whom:str|false, problem:str|false}, features:{bands, scales},
  draft:{…defaults…}}`.
  - `countries` = the employee `payroll_country` selection values ∩ the contract's (NH1), labels from the selection.
    Default country = the country of the team's scheme, else the company's country when it is in the list.
  - `approval`: tell the screen BEFORE the last step whether a second person approves, and who
    (use the approval engine's own route lookup for process `newhire` — find the read method the inbox/config screen uses;
    do not re-implement). No route → `problem` = "New hires cannot be sent yet: nobody is set to approve them. Ask an
    administrator to set this in Approvals." and the Send button is disabled with that sentence beside it (NH9).
  - `prefill` keys from the org chart are accepted and returned inside `draft`.
- `team_defaults(department_id) -> {manager_id, manager_name, site_id|false, country_code|false, scheme:{…}|false}` —
  manager = the department's manager; site = the most common `work_location_id` among the team's active people (false when
  none); country = the team scheme's `country_code`.
- `decides(department_id, country_code, date_start, contract_kind) -> {scheme:{id,name,country_code,match:bool,rung,why},
  currency:{name,symbol,position,decimals}, trial:{months, ends:'YYYY-MM-DD', policy_name}|false, problem:str|false,
  fix:str|false}`.
  - scheme via `resolve_for_team`; `why` is a plain sentence: department rung → "Because <team> is paid by this scheme.";
    division → "Because <team>'s division is paid by this scheme."; only → "It is the only pay scheme in <company>.";
    none → scheme false, `problem` "No pay scheme pays <team> yet.", `fix` "You can still add the person. Set who pays this
    team in Mapping before the first pay run."
  - mismatch (`scheme.country_code != country_code`) → `match False`, `problem` "<team> is paid by <scheme>, a <country A>
    scheme, but you chose <country B> as the country of work.", `fix` "Choose <country A>, or pick the team that <country
    B> people belong to." Sending is allowed (HR may know better) but step 2 shows the amber hint and step 7 lists it.
  - currency = `currency_by_country()[country_code]` (FACTS §C.3); it drives the wage box symbol and formatting.
  - trial via `policy_for_country` + `add_months(start, months)` (import the product's helper, D5). No policy → false and
    the screen says "No trial period rule for <country>."
- `usual_answers(config_id) -> [{code, name, control:'toggle'|'choice'|'number', value, text, options:[{value,label}]}]`
  from `_pb_usual_answer_rules()` + the rule's own record-free label helpers (FACTS §E). Empty list → the card says
  "This pay scheme has no usual answers to check." (designed state, not a blank card).
- `pay_hint(job_id, date_start, wage) -> {band:{min,mid,max,min_label,max_label,currency_code}|false, band_note:str|false,
  scale:{…joiner_suggest reply…}|false}`. Bands: call `pb.pay.bands.place_hire(job_id=…)` inside try/except AccessError →
  `band False` silently (NH6). If the band's currency differs from the chosen country's currency → `band False`,
  `band_note` "The pay band for this job is in <X>, so it is not shown against a wage in <Y>." Scales: call
  `joiner_suggest` exactly as `joiner_hint.js` does today and render its `sentence`/reasons; an empty wage with a scale
  found shows "Leave empty to use <amount> from the pay scale" and the pin-reason choice the old window showed
  (read `pb_pay_scales/static/src/xml/joiner_hint.xml` for wording and the `pb_scale_pin_reason` values).
- `find_people(query='', limit=20)` for the manager picker (name, job, team).
- `check_person(name, work_email) -> {same_name:[{id,name,job,team}], email_taken:bool}` — active employees of the company
  with the same normalised name (case/space-insensitive); powers the "already an employee" amber hint. Never blocks.
- `send(draft) -> answer` — validates, builds the values dict (§2.4) and proposes. Validation errors come back as
  `{ok: False, step:'who'|'role'|'pay', field, message}` (plain sentence, the screen jumps to that field) — never a raw
  traceback for a user mistake. Proposing: replicate the maker branch of `create_employee` (FACTS §A.3 step 3) HERE so the
  facts carry the right unit: `pb.newhire.proposal.propose('employee', "Add %s to the payroll", payload={'values': vals},
  facts={wage:{value, unit=<contract currency name>}, has_bank:{value False}, contract_type:{value}}, amount=wage).answer()`.
  Keep `amount` semantics exactly as today (a number; the proposal's own currency field is the company's — do not change
  the mixin). If the answer is applied (fast lane) return its result merged with `applied True`. Return shape =
  the proposal `answer()` dict + `employee_id`, `employee_name`.
- `withdraw(proposal_id, reason='') -> {ok, message}` — only the asker, only while `pending`; calls the engine's cancel
  (FACTS §A.4). The client keeps the draft in memory and returns to step 7 with everything filled in (D7).

### 2.4 The values dict and the extended create (D2)
Old keys keep their meaning. New optional keys, all JSON-plain (NH8):
`pb_nh` (True — marks a studio hire), `payroll_country` (code), `country_id` (nationality id, optional),
`date_of_joining` (= first day), `private_email`, `private_phone`, `parent_id`, `work_location_id`,
`trial_date_end` ('YYYY-MM-DD' or False for "no trial"), `contract_kind` ('permanent'|'fixed'), `usual` (list of
`{code, amount}` — ONLY the answers the user changed from the scheme's usual value, plus toggles switched off as
`amount 0`), `pb_scale_pin_reason`/`pb_scale_pin_note`, `fill_job_id` (org chart). `with_contract` is always True from the
studio, `activate` True, `date_start` = first day, `date_end` only when fixed term, `struct_id`/`structure_type_id` NOT sent.

`models/create_ext.py` in `pb_new_hire`:
- `class PbOnboardWizardNewHire(models.AbstractModel): _inherit = 'pb.people.onboard.wizard'` — override
  `create_employee(vals)`: call `super()`; when the result is an applied create (`employee_id` truthy, not pending) and
  `vals.get('pb_nh')`, do the extra employee writes in ONE `write` (sudo, `tracking_disable`): `payroll_country`,
  `date_of_joining`, `private_email`, `private_phone`, `work_location_id` (each only when present AND the field exists on
  the model — check `_fields`), then the trial end via `emp.pb_set_trial_end(date)` when a date was sent (D5; when False
  was sent write nothing). Re-validate on replay (NH8): a team/job/site that no longer exists is dropped with a chatter
  note "… was removed before approval", never a crash.
  Order problem to solve and report: `super().create_employee` creates the contract BEFORE these writes, and the contract
  must get the country at creation (NH3). So pass the contract keys through to `create_contract` — see next bullet — and
  make sure the EMPLOYEE's `payroll_country` is set before the contract is created (the time-zone calendar clone, NH2,
  happens at employee create). If `super()` cannot be made to do that by adding `payroll_country` to what it passes to
  `hr.employee.create`, then for `pb_nh` values do the employee create yourself with the full vals and call
  `create_contract` yourself, reusing the parent's bank and return-shape code paths — but keep ONE code path for
  non-`pb_nh` callers (plain `super()`). State which you did and why.
- `class PbContractWizardNewHire(models.AbstractModel): _inherit = 'pb.people.contract.wizard'` — override
  `create_contract(vals)`: when `vals.get('pb_nh')` and this is the approved write: create with fill-in deferred
  (`with_context(pb_skip_fill_in=True)` through `super()`), then on the new contract (sudo, behind the gate already passed):
  write `payroll_country` then re-write `wage` (NH3); do NOT overwrite the employee's time-zone calendar — if the employee
  has its own calendar after create, write that calendar on the contract (NH2); create one `hr.contract.advantage` line per
  `usual` entry (template via `template_for_rule`, FACTS §E; `amount 0` lines included — they block the auto line); then call
  `contract._pb_fill_in_defaults()` so the rest of the usual answers are filled and marked `auto` as normal; `flush_all()`
  before anything reads the scheme map (NH4). The pay-scales override (FACTS §A.5) must still run: check the MRO order of
  the three inheriting classes with a test that an empty wage is still filled from the scale through the studio path.
- `class PbNewHireProposalNH(models.Model): _inherit = 'pb.newhire.proposal'` — extend `_proposal_rows` so the approver's
  drawer shows, for `pb_nh` payloads: "Country of work", "Paid by", "First day", "Trial period ends", "Kind of contract",
  monthly pay formatted in the CONTRACT currency (`formatLang` with that currency), manager, work site, and one row per
  changed usual answer ("<name>: <text>"). Hide "Salary structure" for `pb_nh` payloads. Keep every existing row for old
  payloads.

### 2.5 Client
Clone the shell mechanics of `pb_workforce_setup/static/src/js/setup_studio.js` (FACTS §B.3–B.4): one `load()`,
sequence-guarded refreshes, the `api` object passed to steps, `updateActionState({step})` in `setup()` and on change (WS4),
leave guards, toast, drawer (copy `SetupDrawer`, focus the dialog — WS14), Escape with `{capture:true}` (WS10),
`HubBackChip`. Differences from wfsetup:
- **State lives in the client** as one reactive `draft` until Send (nothing is saved server-side before that). Step status
  is computed on the client from the draft with the POC's rules (`STEPS[].st`), because there is no server record yet.
  Survive an accidental reload: mirror the draft to `sessionStorage` (key per company + user, try/catch, cleared on Send
  success and on "Add another person"); never store anything there after Send. A leave guard asks "Leave without adding
  <name>?" (in-page dialog, not `confirm()`) only when the draft has a name.
- **Step 1** fields: Full name* , First day* (date, default today), Work email, Personal email or phone (one box → the
  facade splits it: contains "@" → `private_email`, else `private_phone`). Hints: duplicate person (amber, from
  `check_person`, debounced 400 ms, sequence-guarded) and the "A work email is not needed" hint with the P2-true wording
  "People without one can still be given a sign-in later from Access."
- **Step 2**: Team*, Job* (jobs of the team first, then the rest; free typing of a new job title goes to `job_title`
  only when no job is picked — keep today's `job_id` + `job_title` pair), Country of work*, Manager (search), Work site,
  Nationality (collapsed under "More", default = country of work). Picking a team calls `team_defaults` and fills manager /
  site / country ONLY where the user has not typed their own value; each auto-filled field carries the teal "Suggested from
  the team" line and loses it when edited. "What this decides" tiles from `decides()`: Pay scheme, Currency, Trial period
  (three tiles in P1 — Holidays / Papers / Contract letter tiles arrive with their phases; do not show tiles that are not
  true yet). Tiles animate from dashed-empty to filled (150–250 ms, respects reduced motion). Mismatch → amber hint with
  the `fix` sentence.
- **Step 3**: "Paid by" card (read-only, with `why`); wage box with the currency symbol from `decides().currency`, thousands
  separators while typing using the currency's decimals (WS18: never write NaN/"" into state; WS42: `formatFloat`), band
  track + chip when `pay_hint.band`, scale sentence when `pay_hint.scale`; Contract segmented control Permanent / Fixed
  term (+ Ends date, required and after the first day when fixed); Trial period row with a switch (on by default when a
  policy exists; off → "No trial period for <first name>"); "The scheme's usual answers" card from `usual_answers` with a
  teal "Usual answer" chip that turns into a purple "Changed for <first name>" chip when edited, and a per-row "Back to
  usual" link. Changing the first day in step 1 or 3 is the same field.
- **Step 7**: the check list (rows with Change buttons that jump to the step and focus the first field), the amber rows for
  problems (`decides.problem`, no scheme, duplicate name), "When you press the button" list reflecting `load().approval`
  truthfully (with a second person: "<who> gets the hire to approve…"; fast lane: "<name> is added straight away."), and
  the Send button: "Send for approval" / "Add <first name>" accordingly. While sending: button shows progress, is disabled,
  double-submit impossible.
- **After Send**: pending → the done card ("<name> is with <with_whom> for approval", reference, "Withdraw and change",
  "Add another person", "Back to Employees"); applied → "<name> is added" with "Open <first name>'s record" (open the
  employee side panel the Employees screen uses — find how `pb_people` opens it and do the same) + "Add another person".
  Server refusal → stay on step 7, the reason in a red hint with the next step; never a lost draft.
- **Keyboard**: Enter in a single-line field moves to the next field, Cmd/Ctrl+Enter = the step's primary button, Esc
  closes the drawer/dialog, focus lands on the step heading after a step change (screen-reader friendly).
- **States to design** (ledger rule 4): loading skeleton for the shell; `load()` failure card with Retry; no teams yet
  ("Add a team first" + button to the Teams screen); no approval route (NH9); user without the HR role (the facade's
  AccessError sentence on a full-page card with "Back to Employees"); 400 px width (rail becomes the horizontal strip).

## 3. Safety rails
- Nothing is written before Send. `send` does exactly one `propose`. The approved write runs as the approver through the
  existing replay (NH8) — test it with a second user.
- A failure in any of the extra writes after the employee exists must not leave a half-made hire silently: wrap the
  extension steps so that a failure rolls the whole approved apply back (let the exception propagate — the engine reports it
  on the request) rather than swallowing it. Only "the thing was deleted meanwhile" is downgraded to a chatter note.
- No sudo before the gate. No user-supplied field names reach `write` (whitelist in §2.4).

## 4. Tests (`pb_new_hire/tests/`, tag `newhire`) — number them in the report
T1 `resolve_for_team` equals `resolve` for an employee of that team on department / division / only / none fixtures.
T2 `policy_for_country` = `policy_for` for an employee whose ladder yields that country; `policy_for` unchanged.
T3 `_pb_usual_answer_rules` returns exactly the rules `_pb_fill_one` fills (compare codes on a fixture scheme).
T4 `decides`: match, mismatch (problem + fix text), no scheme, no policy; currency per country; trial end = add_months.
T5 `send` with a fast lane: employee has `payroll_country`, `date_of_joining`, private contact, manager, site, nationality
   default; trial end on the employee; contract `open`, `payroll_country` set, `currency_id` = the country's, wage NOT
   rounded to the company currency (company VND, hire in SG with wage 5200.50).
T6 `send` with a second person: nothing created while pending; approver (second user) approves → same assertions as T5;
   reject → nothing created.
T7 Usual answers: one toggled off and one amount changed → those lines exist without the `auto` mark, the untouched ones are
   filled with the `auto` mark, no duplicate codes.
T8 Old callers unchanged: `create_employee` without `pb_nh` behaves exactly as before (run `test_fs16_newhire_bank`, and
   the pay-scales, org chart, updates suites named in FACTS §A.5).
T9 Pay scale through the studio: empty wage → filled from the scale, contract placed, pin reason honoured.
T10 Org chart prefill: `fill_job_id == job_id` lowers the to-hire count once on approval, not on send.
T11 Validation: missing name / first day / team / job / country / wage, fixed term without end, end before start →
    `{ok False, step, field, message}`; non-HR user → AccessError; no approval route → `load().approval.problem`.
T12 `withdraw`: asker only, pending only; after withdraw a second `send` works.
T13 Replay hardening: team deleted between send and approve → hire still created, chatter note, no crash.
T14 `_proposal_rows` for a `pb_nh` payload shows the new rows and the wage in the contract currency.
T15 Static gates (no "Odoo", icons exist, no emoji, `_t` import form).
Browser walk (local server), each with a console-error read: B1 open from People › Employees "Add employee" (takeover);
B2 full happy path to "is with … for approval"; B3 approve as the second user in the approvals inbox, see the drawer rows,
then the new person in Employees with the right currency on the wage; B4 mismatch country hint; B5 team with no scheme;
B6 duplicate name hint; B7 Withdraw and change → resend; B8 reload mid-way keeps the draft and the step; B9 org chart
"A new starter" prefill; B10 400 px width; B11 a user without the HR role; B12 keyboard-only run of steps 1–3.

## 5. Report back — `docs/handovers/newhire/NEWHIRE_P1_REPORT.md`
1. What was built (file list) and every file touched outside `pb_new_hire` with the reason.
2. Test results T1–T15 and B1–B12 (pass/fail, with the failing output), plus the suites of touched modules.
3. Self-review against this handover: every deviation, with the reason. Which option you took in §2.4's order problem.
4. Design bar score (ledger rule 4), honest, with screenshots saved under the scratch dir (not committed).
5. New gotchas added to the ledger (NH11+).
6. Open questions for the architect; anything in P2–P4 that P1's structure makes harder.
7. Commits made (hashes). Do not push.
