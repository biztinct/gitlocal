# NEWHIRE P1 — report (the studio, the three required steps, check and send)

Built on worktree `gitlocal-worktrees/newhire` (branch `newhire`), 2026-11-25. Not pushed, nothing deployed, no server access.

## 1. What was built

New module **`pb_new_hire`** 19.0.1.0.0 (prefix `pbnh-`, grep-checked free):

| Layer | Files |
|---|---|
| Manifest / action | `__manifest__.py` (depends `pb_people_advanced, pb_hub, pb_import_kit, pb_scheme_map, pb_probation, pb_employee_form_tidy`), `views/studio_action.xml` (`action_new_hire_studio`, name "Add employee", tag `pb_new_hire_studio`, path `add-employee`) |
| Facade | `models/studio.py` — `pb.new.hire`: `load, team_defaults, decides, usual_answers, pay_hint, find_people, check_person, send, withdraw` |
| Create path | `models/create_ext.py` — `create_employee` / `create_contract` extensions, `hr.employee` / `hr.contract` create hooks, `pb.newhire.proposal` rows, request currency and withdraw hook |
| Client | `static/src/js/studio_util.js, step_who.js, step_role.js, step_pay.js, step_soon.js, step_check.js, record_panel.js, new_hire_studio.js, takeover.js`; one template file `static/src/xml/new_hire_studio.xml`; one SCSS file `static/src/scss/new_hire_studio.scss` |
| Tests | `tests/test_new_hire.py` (T1–T14 + extras), `tests/test_static.py` (T15) — tag `newhire` |

**Files touched outside `pb_new_hire`** (the three pure refactors of handover §2.2, nothing else):

| File | Why |
|---|---|
| `pb_scheme_map/models/pb_scheme_map.py` | rungs 2/3/5 moved into `_rung_department/_rung_division/_rung_only`; `resolve_many` calls them; new `resolve_for_team(department_id, company_id, cycle_type, on_date)` uses the same three. The body could be shared without behaviour risk (rung 4 still sits between 3 and 5 in `resolve_many`). |
| `pb_probation/models/probation_policy.py` | new `policy_for_country(country, company)`; `policy_for` calls it (same two searches, same order, incl. the "no country → first policy" quirk). |
| `pb_hr_payroll_formula/models/contract_fill_in.py` | new `hr.formula.config._pb_usual_answer_rules()` (on the existing `HrFormulaConfigUsualAnswers` class in this file, not in `formula_config.py`); `_pb_fill_one` calls it. |

Docs: `NEWHIRE_LEDGER.md` (NH11–NH18 added), `NEWHIRE_FACTS_CORE.md` (corrections section at the end), this report.
No `pb_people`, `pb_orgchart` or `pb_people_advanced` file was edited (JS or Python).

Dependency check (handover §2.1): the six dependencies form no cycle (pb_new_hire depends on them; nothing depends on
pb_new_hire). Per FACTS_ONBOARD §M3 `pb_people_advanced, pb_scheme_map, pb_probation, pb_employee_form_tidy` are installed on
all five live databases; `pb_hub` and `pb_import_kit` are not rows in that matrix but are dependencies of modules that are
(e.g. `pb_probation`, `pb_scheme_map`), so they are installed everywhere too.

## 2. Results

### 2.1 Numbered tests (`-u pb_new_hire --test-tags /pb_new_hire`, local DB `nh1_base`)

**24 / 24 pass** (19 server + 5 static).

| # | Test | Result |
|---|---|---|
| T1 | `resolve_for_team` == `resolve(employee)` on department, division, none-or-only fixtures, plus a one-scheme company (only rung) | pass |
| T2 | `policy_for_country` == `policy_for`; fallback identical for a country with no row | pass |
| T3 | `_pb_usual_answer_rules` codes == codes the fill-in marks `auto` on a fresh contract (zero default excluded) | pass |
| T4 | `decides`: match (why sentence), mismatch (exact problem + fix sentences), no scheme, no policy ("No trial period rule for Malaysia."), currency per country, trial = `add_months` (2026-12-07 → 2027-03-07); countries = VN ID IN SG MY only (NH1) | pass |
| T5 | fast lane, company VND, SG hire 5,200.50: employee Country of Work / joining date / private email / manager / site / nationality default; trial end on the employee; contract open, SG, SGD, wage 5200.50 (not rounded), contract calendar = employee's | pass |
| T6 | second person: nothing while pending, `with_whom` = approver, approve → same as T5; reject → nothing | pass |
| T7 | usual answers: toggle off (line 0, no mark), amount changed (no mark), untouched (marked `auto`), unknown code ignored, no duplicates | pass |
| T8 | old `create_employee` without `pb_nh`: no Country of Work, contract in company currency (+ old suites, §2.2) | pass |
| T9 | empty wage through the studio with pay scales installed: filled from the scale, contract placed, pin reason `offer` reaches `place_new_contract` (scale `resolve`/`place_new_contract` patched in the test — no real scale fixture) | pass |
| T10 | org chart `fill_job_id`: unchanged on send, lowered once on approval | pass |
| T11 | validation: name, first day, team, job, country, unknown country, wage missing, wage not a number, fixed term without end, end before start → `{ok False, step, field, message}`; nothing written; non-HR `load`/`send` → AccessError; no route → `load().approval.problem` and `send` refuses | pass |
| T11b | approval info: `needs`, `with_whom` = holder of HR lead; fast lane → `needs False` | pass |
| T12 | withdraw: not by another user, request cancelled, proposal no longer pending, second withdraw refused, a new send then approve works | pass |
| T13 | team deleted between send and approve → hire created without team, typed job title kept, chatter "was removed before approval" | pass |
| T14 | `_proposal_rows` for a studio payload (Country of work, Paid by, First day, Trial period ends, Kind of contract, Manager, Work site, wage in SGD, "Changed to No", no Salary structure); request amount in SGD; old payload keeps old rows | pass |
| T15 | static: no vendor name, every icon exists, no emoji, `_t` import form + literal first argument, action tags | pass |
| extra | `check_person` (case/space-insensitive, email taken), `team_defaults`, fixed term + trial switched off | pass |

### 2.2 Suites of touched modules and FACTS §A.5

Run 1 — walk DB `nh1_base`, `-u` of every touched module + FACTS §A.5 modules, tags `/pb_scheme_map, /pb_probation,
/pb_hr_payroll_formula:TestFillInP1, /pb_people_advanced, /pb_pay_scales, /pb_orgchart, /pb_updates, /pb_approval_config,
/pb_contract_lifecycle, /pb_contract_rules, /pb_new_hire`: **650 tests, 6 failed, 2 errors** — pb_scheme_map 43, pb_probation 17,
pb_hr_payroll_formula (fill-in) 19, pb_people_advanced 10, pb_pay_scales 53, pb_orgchart 99, pb_updates 296,
pb_approval_config 194, pb_contract_lifecycle 14, pb_contract_rules 23, pb_new_hire 30 (24 run).

Every not-ok was then run on a **fresh** copy of `upd_p6_t_tpl` (`nh2_base`, `-u all` + pay scales + contract rules), first
with the pre-P1 code (`git archive 36dd3afcf`), then with the P1 code (+ `-i pb_new_hire`):

| Test | Run 1 (walk DB) | Fresh DB, old code | Fresh DB, P1 code | Verdict |
|---|---|---|---|---|
| pb_people_advanced `test_02_through_the_new_hire_approval` | fail | **fail** | fail | pre-existing (template DB route state) |
| pb_people_advanced `test_03b_bad_number_on_the_approval_route…` | error | pass | **pass** | walk DB only: I had set new hires to "No approval needed" on the main company for the fast-lane walk |
| pb_approval_config `test_u10_an_arranged_exception…` | error | **error** | error | pre-existing (AccessError in pb_bank_ocr's notice reading a user) |
| pb_approval_config `test_the_look_invents_no_colour…` | fail | **fail** | fail | pre-existing static check |
| pb_approval_config `test_u13 / test_z06d / test_z06e` (Vietnamese) | fail | **fail** | fail | pre-existing translation checks |
| pb_pay_scales `test_r02_real_cost_per_currency` | fail | **fail** | fail | pre-existing |

Fresh DB, P1 code: the same 7 not-ok as the old code and nothing else (89 tests incl. pb_new_hire 24/24). **No regression
from P1.** None of these modules' files was edited in P1.

### 2.3 Browser walk (local server, Claude-in-Chrome, 1440 px; console read after each)

Walk world: `nh1_base` = copy of `upd_p6_t_tpl` + `-u all` + `-i pb_pay_scales,pb_contract_rules` (NH16), then a seed run
through `odoo-bin shell` (company DEMO Farms VND/VN; four active schemes ID/SG/VN/IN mapped to four teams, a fifth team
unmapped; usual answers on the Indonesia and Singapore schemes; two sites; managers; an IDR pay band on Junior Agronomist;
users maker (HR manager), lead (HR manager, holds "HR lead"), viewer (records viewer, no HR)). The seed script stays in the
scratch area (it sets local test passwords; not committed).

| # | Walk | Result |
|---|---|---|
| B1 | People › Employees › Add employee opens the studio (URL `…/pb_onboard_wizard` → `…/add-employee`), name box focused | pass |
| B2 | Sari Wulandari, Indonesia Operation, Junior Agronomist: tiles fill (Indonesia monthly staff / IDR / 3 months to 7 Mar 2027), manager + site + country suggested, band "Inside the pay band", one usual answer switched off ("Changed for Sari"), Skip to the end, Send → "Sari Wulandari is with Dewi Lestari for approval", reference NEW00049 | pass |
| B3 | as the HR lead: Approvals inbox card, drawer rows (Country of work, Paid by, Team, Job, Manager, Work site, Nationality, Kind of contract, Trial period ends, Monthly pay "Rp 9,000,000.00", "BPJS Kesehatan covered: Changed to No"), Approve. DB: employee ID / Asia/Jakarta calendar, contract open IDR 9,000,000, lines: BPJS Kes 0 (no mark), others `auto`. People › Employees shows the person with a running contract **but the list writes the wage "₫9.0M"** (pb_people formats every wage in the company currency — NH18, not our screen). The inbox amount showed "9,000,000 VND" — fixed after this walk (NH15, T14). | pass, with the Employees-list caveat |
| B4 | Finance + India: Pay scheme tile amber, exact mismatch sentence + fix, "Use Singapore" puts the country back | pass |
| B5 | Human Resources (no map): "No pay scheme yet", "No pay scheme pays Human Resources yet." + "You can still add the person…" in the stage and the record panel | pass |
| B6 | "abdul rohman" (existing "Abdul Rohman"): amber "is already an employee (Junior Agronomist, Indonesia Operation)" | pass |
| B7 | Withdraw and change → draft intact on step 7, toast; Change on the pay row focuses the wage box; new wage; Ctrl+Enter sends again; first proposal is `draft`, second applied after approval | pass |
| B8 | reload on `?step=role` keeps the step and the draft; reload of an org-chart draft keeps it and shows "Your unsent hire was kept…" with Start again | pass |
| B9 | Org chart › Accountant open role › Fill this role › A new starter › Open the form: team Finance, job Accountant, manager Tan Wei Ling, Singapore suggested, back chip "Back to Org chart"; added in the fast lane → to-hire count 1 → 0 | pass |
| B10 | phone layout: the window cannot go below 578 px (NH17), so the studio root was narrowed to 340 px (400 minus the 60 px sidebar): horizontal step strip, one column, tiles stacked, no element wider than the page | pass (emulated) |
| B11 | records viewer presses Add employee: full-page card "Adding people is for HR" with the server's own sentence and Back to Employees (which works); no error dialog | pass |
| B12 | keyboard: type name, Enter moves to the next box, Enter on the last box = Next, heading focused on the new step, Tab into the team box, Ctrl+Enter = the step's button, Escape closes the leave dialog ("Stay here" focused). Native selects were set with `form_input` (macOS type-ahead cannot be driven by the tool, NH17) | pass |
| extra | leave guard: sidebar Home with a named draft → "Leave without adding Lim Jia Hui?"; fast lane "Lim Jia Hui is added" → Open Lim's record opens the employee side panel (SG, SGD 5,200.50 in the DB, Asia/Singapore) | pass |

Console: one real error during the walk — `ctx.String is not a function` in step 2 (NH11), fixed before continuing; one
`ConnectionLostError` on the bus while the local server restarted. Otherwise clean.

Screenshots: inline in the session; the hero (step 2) and step 3 were also saved to the session scratch folder `shots/` (not committed).

## 3. Self-review against the handover — deviations

1. **§2.4 order problem — neither of the two options as written.** Option 1 (super passes `payroll_country` to
   `hr.employee.create`) needs an edit in `pb_people_advanced`; option 2 (create the employee ourselves for `pb_nh`) skips
   any override that sits below us in the MRO (pay scales, org chart). Taken instead: `super()` is always called, with the
   studio's extras in a context key; whitelisted `hr.employee.create` and `hr.contract.create` hooks put Country of Work,
   joining date, private contact and site on the ONE employee create (name-matched), and Country of Work + the employee's
   calendar on the ONE contract create (employee-matched). One code path for every caller; works in any MRO order.
2. **Contract currency is set at create, not "write payroll_country then re-write wage".** Same outcome (T5: 5,200.50 SGD),
   no rounding window at all, and independent of where pay scales sits in the MRO.
3. **Extra payload keys** (JSON-plain): `pb_nh_scheme_id` (which scheme the changed answers belong to) and `pb_nh_names`
   (names for the approver rows and for the "removed before approval" notes); `usual` items also carry `name`/`text`.
4. **Vietnam contract kind**: a VN studio hire sends `vn_kind` `definite`/`indefinite` from the Permanent / Fixed-term choice
   (the old window always left the default "indefinite", wrong for a fixed term).
5. **`pay_hint` takes a 4th argument `country_code`** — the band-currency check needs the chosen country's money.
6. **`decides` returns `trial_none`** (the "No trial period rule for <country>." sentence) besides `trial`.
7. **`pb_updates._department_schemes` was not switched to `resolve_for_team`** (not in §2.2; it returns a set over all cycle
   types).
8. **Approval request currency**: `_approval_context` overridden for studio payloads so the inbox shows the contract money (the
   mixin and the proposal's own currency field are untouched, as asked).
9. **`_approval_withdraw`** added on `pb.newhire.proposal` for studio payloads only (proposal → `draft`), otherwise a withdrawn
   hire stays "Waiting for approval" (NH14).
10. **No drawer component** was copied: nothing in P1 needs a drawer; the leave question is a small in-page dialog
    (Esc closes, safe answer focused).
11. **Personal email or phone** hint says "Kept on the record as their own contact." — the POC's welcome-link line is not true
    until P3.
12. **Steps 4–6 sentences** say "your company's usual working hours and holiday list" (true today) instead of "team defaults".
13. Withdrawn/unsent draft: a new org-chart prefill replaces a kept draft without asking (the org chart sent a fresh request).

## 4. Design bar (ledger rule 4), scored honestly

- **Hero moment — 9/10.** Picking a team fills manager, site and country with teal "Suggested from the team" lines, the three
  tiles land from dashed to teal, the record panel's Paid by card and trial line update, the wage box switches to the
  country's symbol. Mismatch turns the scheme tile amber with a one-click fix.
- **Zero dead-ends — 8/10.** Designed: loading skeleton, load failure + Try again, no HR role, no team ("Add a team first"),
  no route (Send disabled with the sentence), no scheme, mismatch, duplicate name, email taken, server refusal (red hint +
  Fix it), withdraw. Not designed yet: a seat-limit refusal reads as the server's sentence only.
- **Plain language — 9/10.** All screen words from the POC or the facade; no codes. Wage figures follow the currency's own
  decimals ("Rp 8,500,000.00") — correct but heavier than the POC's whole numbers.
- **Motion with purpose — 8/10.** Step enter rise, tile landing, chips fade, done tick pop, ring; all off under reduced motion.
- **Keyboard — 8/10.** Enter chain, Ctrl+Enter, Esc, heading focus, combobox manager picker with arrows; native selects rely
  on the browser's own type-ahead.
- **Versus the best in class (Rippling's "role decides everything")** — the decide-once feel is there; the first-payslip
  example (P4) is the missing half of the wow.

## 5. New gotchas

NH11–NH18 in the ledger (template JS globals, falsy zero, unstored `complete_name`, missing withdraw hook, request currency,
the recipe DB, the browser tools, other screens still in company money).

## 6. Open questions for the architect / what P2–P4 inherit

1. **People › Employees list and KPI write every wage in the company currency** (`₫9.0M` for an IDR contract) — a pb_people
   fix (FACTS §A.2's "wrong currency sign" finding lives on there). Owner/architect: which phase owns it?
2. **Contract "Employee category" (`type_id`)** defaults to the first `hr.contract.type` ("Vietnam Permanent Monthly") for any
   country — `create_contract` never sets it (FACTS §A.3). Should the studio pick a category by country (P2?)
3. **A kept draft is replaced by a new org-chart prefill without asking.** Acceptable, or ask "Carry on with Sari, or start
   Lim?"
4. **Leaving through the browser's own address bar / tab close** keeps the draft (sessionStorage) but does not ask; only
   in-app navigation asks. Fine for P1?
5. P2 structure: steps 4–6 are a single `StepSoon` component keyed by step; P2/P3 replace it per step. The draft and
   `sendDraft` are flat; new keys need adding in three places (`blankDraft`, `sendDraft`, server `DRAFT_KEYS`/`_values`).
6. P4 (first payslip): `decides()` and `usual_answers()` already give the scheme and the person's overrides the example needs.

## 7. Commits (not pushed)

- `c97f73ead` NEWHIRE: design of record, ledger, fact sheets and P1 handover
- `ac5c20c9b` NEWHIRE P1: team-only scheme lookup, trial policy by country, usual-answer rules
- `b33710f0c` NEWHIRE P1: pb_new_hire server side (studio facade, one create path)
- `feb4a15b7` NEWHIRE P1: the New Hire Studio screen and the Add employee takeover
- (this report + ledger NH11–NH18 + fact corrections — the docs commit after these)

Local leftovers (not in git): DB `nh1_base` (walk world, kept for P2's walk; passwords only in the scratch seed script),
screenshots `p1-step2-hero.jpg`, `p1-step3-pay.jpg` in the session scratch folder `shots/`. `nh2_base` (baseline) dropped.
