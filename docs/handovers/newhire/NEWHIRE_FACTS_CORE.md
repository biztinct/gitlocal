# NEWHIRE — core plumbing facts (do not re-derive)

Gathered 2026-11-25 on worktree `gitlocal-worktrees/newhire` (branch `newhire`, from `origin/19.1` @ `36dd3afcf`).
Every path is repo-relative. "DOES NOT EXIST" means grepped for and absent on this branch.
Target design: `docs/design/new-hire-studio-poc.html` (STEPS at :398-405; views vWho :428, vRole :452, vPay :478,
vSched :503, vDocs :518, vWelcome :551, vCheck :568; right panel renderPv :597; findings drawer :620).
Engineering doc: technical names are fine here. Every user-visible string the build adds must still obey the
white-label rule (no "Odoo") and the plain-words rule.

---

## A. The flow being replaced

### A.1 Doors into it
| Door | Where | What it sends |
|---|---|---|
| People › Employees "Add employee" | button `pb_people/static/src/xml/people.xml:26` → `addEmployee()` `pb_people/static/src/js/people.js:323-325` | `doAction({type:'ir.actions.client', tag:'pb_onboard_wizard', name:'Add employee'})`, no params |
| Org chart "A new starter" / "Fill this role › A new starter" | `pb_orgchart/static/src/js/orgchart_edit.js:353-372` (`openNewStarter`) | same tag, `params.prefill = {fill_job_id, parent_id, parent_name, department_id, department_name, job_id, job_title}`; guards with `registry.category("actions").contains("pb_onboard_wizard")` |
| Home dashboard card "Add your first employee" | `pb_dashboard/static/src/js/pb_dashboard.js:65-71` | opens the Employees screen (`ACT_EMPLOYEES`), not the wizard |
| Server action record | `pb_people_advanced/views/wizard_actions.xml:3-6` `action_pb_onboard_wizard` (name "Add Employee", tag `pb_onboard_wizard`) | — |

### A.2 Client action `pb_onboard_wizard`
- File `pb_people_advanced/static/src/js/onboard_wizard.js`; class `OnboardWizard`, template `pb_people_advanced.OnboardWizard`
  (`static/src/xml/onboard_wizard.xml`, root `.pbim.emp.pplw-root`, card `.pplw-card`); registered :127.
- Steps `["Person","Role","Contract"]` (:9). Form keys (:19-29): `name, work_email, work_phone, country_id, department_id, job_id,
  job_title, parent_id, fill_job_id, with_contract(true), struct_id, structure_type_id, wage, date_start, date_end,
  resource_calendar_id, activate(true), bank_name, account_number, account_holder` (+ `pb_scale_pin_reason` added by pb_pay_scales).
- Loads `pb.people.onboard.wizard.get_defaults()` (:41); prefill from `props.action.params.prefill` (:34-60).
- Submit: `orm.call(MODEL,'create_employee',[form])` (:107-128). A pending answer (`res.pending`) is NOT an error.
- Currency shown = company symbol (`get cur()` :74 ← `pb.people.refs._refs()['currency']` = `company.currency_id.symbol`,
  `pb_people_advanced/models/people_wizards.py:38`). This is the "wrong currency sign" finding.
- `biz_theme/static/src/js/required_fields.js:8` lists `.pplw-card` as a validation scope (cosmetic coupling).

### A.3 Backend `pb.people.onboard.wizard` (AbstractModel) — `pb_people_advanced/models/people_wizards.py`
- `get_defaults()` :47-59 → `pb.people.refs._refs()` (:23-40: `structures, structure_types, calendars, default_calendar,
  default_struct, currency, today`) + `departments, jobs, countries` (limit 200/200/300) + `banks` (`_pb_bank_choices` :80-94,
  from `pb.bank.registry`) + `bank_check` (`_pb_bank_door_ready` :75-77).
- **`create_employee(vals) -> dict`** :183-289. Contract:
  1. `require_hr(env)` (:184; `newhire_approval.py:43-51`: superuser or `hr.group_hr_user`/`hr.group_hr_manager`, else AccessError).
  2. `name` required → `{'error': 'A name is required.'}`.
  3. **Maker-checker branch** (:190-232) when `NEWHIRE_WRITE` not in context and `pb.newhire.proposal` exists:
     bank problem is checked now (`_pb_bank_problem` :109-123, 6–19 digits) and bank keys stripped if bad;
     `pb.newhire.proposal.propose('employee', "Add %s to the payroll", payload={'values': vals}, facts={wage:{value,unit=company
     currency}, has_bank:{value,unit}, contract_type:{value=str(structure_type_id)}}, amount=wage).answer()`.
     Not applied → `dict(answer, employee_id=0, employee_name, contract_id=0, error=None[, bank={state:'later'|'not_sent'}])`.
     Applied (fast lane) → `dict(answer['result'], reference=answer['reference'])`.
  4. **Approved write** (`NEWHIRE_WRITE` set): `hr.employee.create` with ONLY `name, job_id, department_id, country_id, job_title,
     parent_id, work_email, work_phone` (:233-252). `country_id` is NATIONALITY (`hr/models/hr_version.py:60-61`
     "Nationality (Country)"). **Not written: `payroll_country`, `date_of_joining`, `pb_attendance_category`, `pb_clock_code`,
     `resource_calendar_id`, `tz`, `work_location_id`, `private_email`, `trial_date_end`.**
  5. Bank: `_pb_send_bank(emp, bank, env.user)` :130-169 → `pb.bank.change.request._pb_hold_new_hire(emp, {x_account_number,
     x_bank_name, x_account_name}, proposer)` (`pb_bank_ocr/models/pb_bank_import_hold.py:158-175`) inside a savepoint;
     outcome `{'state': 'sent'|'check'|'not_sent'|'later', 'message', 'reference'}`; a non-sent outcome is posted on the employee
     chatter (`_pb_bank_note` :172-180).
  6. Contract if `vals['with_contract']` (:266-278) → `pb.people.contract.wizard.create_contract({employee_id, wage, date_start,
     date_end, struct_id, structure_type_id, resource_calendar_id, activate})`.
  7. Returns `{'employee_id','employee_name','contract_id','error'(contract error),'applied':True[, 'bank']}` (:285-289).
- **`pb.people.contract.wizard.create_contract(vals) -> dict`** :503-590. `require_hr`; same proposal pattern with kind
  `'contract'`, `target=emp`, `subject_uids=emp.user_id.ids` (:509-533). Approved write builds `cvals` (:534-568):
  `employee_id, name ("<emp> - <date_start>"), wage(float), date_start (default today), [date_end], [struct_id],
  [structure_type_id], resource_calendar_id (vals or company calendar — ALWAYS set), [vietnam_contract_type],
  [pb_payroll_contract_type], [pb_renewed_from_id]`; `hr.contract.create(cvals)`; `state='open'` only if `vals['activate']`
  (:571-572). **Not written: `payroll_country` (so currency = company's, see C.3), `trial_date_end`, `contract_type_id`,
  `type_id` (om_hr_payroll required, defaults to first `hr.contract.type`, `om_hr_payroll/models/hr_contract.py:72-74`),
  pay lines for a NEW contract** (lines are only carried on renewal, `_carry_renewal_lines` :441-501).
  Returns `{'contract_id','name','employee_id','error':None,'applied':True}`.

### A.4 Maker-checker `pb.newhire.proposal` — `pb_people_advanced/models/newhire_approval.py`
- Model :54-70: `_inherit=['biz.approval.proposal.mixin']`, process key `'newhire'` (:34), prefix `NEW`, gate groups
  `('hr.group_hr_user','hr.group_hr_manager')` (:37), kinds `employee|contract`, fact specs `wage`(decimal) `has_bank`(bool)
  `contract_type`(char).
- Fields (mixin, `biz_approval_workflow/models/proposal.py:113-157`): `name, kind, title_text, payload_json, snapshot_json,
  facts_json, scope_json, subject_json, amount(Monetary), currency_id (company), scope_label, note, target_model, target_id,
  company_id, user_id (asked by), state, applied, applied_at, block_note, result_json, seat_user_ids`.
- States (`proposal.py:51-57`): `draft` Being prepared · `pending` Waiting for approval · `applied` Carried out ·
  `returned` Sent back · `rejected` Turned down.
- `propose(kind, title, payload, snapshot=None, facts=None, scope_keys=None, scope_label='', target=None, company=None,
  note='', subject_uids=None, amount=0.0)` `proposal.py:256-296` → sudo create + `biz.approval.engine.submit(record)`.
  **No route for the company → `submit` raises UserError** (`biz_approval_workflow/models/engine.py:855-858`).
  Fast lane ("No approval needed") applies inside the same call.
- `answer()` `proposal.py:298-326` → `{ok, proposal_id, reference, kind, state, applied, pending, request_id, with_whom,
  route, block_note, message, notes, result}`.
- **Payload stored and replayed**: `payload={'values': <the whole form dict>}` as JSON (`_plain`-normalised). On approval
  `_apply_employee` (:114-132) strips the bank keys, calls `create_employee(values)` under `NEWHIRE_WRITE`, then sends the bank
  details as the ORIGINAL proposer (`self.user_id`). `_apply_contract` (:134-141) replays `create_contract`.
  Snapshot is empty (create has no "before"), so `_proposal_moved` never blocks.
  **The full account number sits in `payload_json`** (readable by HR + seat holders); only the drawer row masks it (:97-102).
- Who approves: seeded route = one step, role `hr_lead` filled from `hr.group_hr_manager` (`_approval_seed_default` :145-154;
  seeded on company create :157-168 and `post_init_hook`). The last approver must hold a gate group (rail 5,
  `proposal.py:551-574`) and performs the write as themselves.
- Where the approver sees it: the one approvals inbox, client action `pb_approval_inbox`
  (`pb_approval_config/static/src/js/inbox.js:962`); the drawer table = `_approval_detail` (`proposal.py:468-493`) fed by
  `_proposal_rows` (:90-111: Name, Job title, Work email/phone, Monthly pay, Starts, Ends, Bank, Account holder, •••• last 4,
  Job, Team, Country, Person, Salary structure, Kind of contract, Working hours, "And a contract straight away",
  "Contract starts in force"). Record rules `pb_people_advanced/security/newhire_approval_rules.xml` (seat or asker; HR by company).
- Reject → `state='rejected'`, nothing created (`proposal.py:514-516`). Return → `state='returned'` (:510-512). Payload is
  readonly: **edit-and-resend DOES NOT EXIST**; the maker can withdraw (`biz.approval.engine.cancel(request, reason)`,
  `engine.py:1464-1490`, submitter or admin) and propose again. The POC line "You can come back and change anything before it is
  approved" needs cancel + re-propose.
- Test helper for a fast lane: `biz.approval.seed.set_no_approval_needed(company, process_key)` (`seed_helper.py:320`).

### A.5 Everything else that calls or patches it (must not break)
| Who | Where | Contract it relies on |
|---|---|---|
| pb_pay_scales — server | `pb_pay_scales/models/joiners.py:36-83` (`PbContractWizardScales`): `get_defaults` adds `scale_hint`; `create_contract` fills an EMPTY wage from `pb.pay.scales.resolve(job, company, date_start, employee)` and calls `place_new_contract(contract, reason, source='hire', note)` after an applied create. `:85-97` (`PbOnboardWizardScales`): reads `vals['pb_scale_pin_reason']` and passes it via context `pb_scale_pin_reason`. | the replacement must still go through `create_contract` and keep `pb_scale_pin_reason` / `pb_scale_pin_note` in the values |
| pb_pay_scales — JS | `pb_pay_scales/static/src/js/joiner_hint.js:79-127` patches `OnboardWizard.prototype` (`setup`, `onField` on `job_id`/`date_start`, `next`) and calls `pb.pay.scales.joiner_suggest`; template ext `pb_pay_scales/static/src/xml/joiner_hint.xml:41` | if the tag is re-pointed these patches go dead silently; the studio must call `joiner_suggest` itself (G.2) |
| pb_orgchart | `pb_orgchart/models/onboard_fill.py:20-38` wraps `create_employee`: when `fill_job_id == job_id` and not pending, `hr.job.no_of_recruitment -= 1` (runs again on approval replay) | keep `fill_job_id` in the payload; accept the `params.prefill` keys of A.1 |
| pb_updates joiners sheet | `pb_updates/models/updates_joiners.py:820-850` calls `create_employee(dict(j['vals']))` with `NEWHIRE_WRITE: False`; `PbNewHireProposalUpdates` (:152-178) extends `_approval_apply/_reject/_return` of the proposal; `pb.updates.joiner.proposal_id` (:123) | the server method and the proposal model must stay; signature of `create_employee(vals)` unchanged |
| pb_form_studio_contracts | `pb_form_studio_contracts/models/contract_wizard.py:61-78` — after `create_contract`, carries custom fields on RENEWAL only | unaffected by a new create path that calls `create_contract` |
| pb_contract_lifecycle | Extend / Make permanent go through `create_contract(renew_from=…)` (docstring `pb_form_studio_contracts/models/contract_wizard.py:5-9`) | do not change `create_contract` behaviour for renewals |
| pb_hiring "Confirm they joined" | `pb_hiring/models/offer_closure.py:70-137`: `_ensure_employee` (:160-219, applicant vals, no wizard), `_ensure_contract` (:252-301, raw ORM, **deliberately bypasses the wizard and the newhire proposal**), `_ensure_case` (:430-458) | the POC's "Confirm they joined opens this same screen" is a NEW behaviour; today Hiring never touches the wizard |
| Lessons | `pb_people/learn_manifest.py:190`, `pb_learn/static/src/anchors.json:590` (describes "three-step onboarding wizard"), `pb_learn/static/src/engine/screens.js:593-641` (Employees replica), `pb_learn/static/content/learn_content.json` (4 hits) | standing rule: a screen change updates the lessons in the same work |

Existing tests: `pb_people_advanced/tests/test_fs16_newhire_bank.py` (tests 01–09: bank waits for second person, via approval,
bad number, no bank, contract fact, defaults bank list); `pb_pay_scales/tests/test_wdgap_s8a_scales.py:268,331,348`
(empty wage → scale, onboard passes reason, joiner sheet); `pb_pay_scales/tests/test_wdgap_w3_merge_seams.py:197`;
`pb_orgchart/tests/test_orgchart_p3.py:387,465` (future starter, new starter fills the role); `pb_updates/tests/test_updates_p3b.py`
(21 tests, :148 patches the wizard class); `pb_approval_config/tests/test_p7_matrix.py:120`;
`pb_contract_lifecycle/tests/test_wdgap_s8d_renewal.py:121`, `pb_contract_rules/tests/test_wdgap_w3b_renewals.py:81`
(contract wizard renewals). No JS tests.

---

## B. The studio shell to clone — `pb_workforce_setup`

### B.1 Manifest `pb_workforce_setup/__manifest__.py`
- `depends` (:54-61): `pb_workforce_workspace, pb_wf_kit, pb_import_kit, pb_hub, pb_timeoff, pb_attendance_policy`.
- `data`: `security/ir.model.access.csv`, `security/undo_rules.xml`, `views/setup_action.xml`.
- `assets` `web.assets_backend` (:67-84): scss `setup_studio.scss`; js `setup_util, step_shifts, step_weeks, setup_drawer,
  step_people, step_rules, step_holidays, step_clocks, step_live, preview_panel, setup_studio, takeover`; xml `setup_studio.xml`
  (ONE template file holding every `t-name`).
- Version `19.0.1.4.1`. i18n: `i18n/vi_VN.po`, `i18n/id_ID.po`, `i18n/pb_workforce_setup.pot`.

### B.2 File map
| Layer | Files |
|---|---|
| Facade | `models/setup.py` (`pb.workforce.setup` AbstractModel: gates :57-75, `load(employee_id)` :151-175, shifts/weeks CRUD, `find_people`, `person_week`); extended by `models/people.py` (step 3 + bulk + undo), `models/rules.py` (step 4 + `pay_example`), `models/holidays.py`, `models/clocks.py`, `models/golive.py`, `models/days.py`, `models/roster.py` |
| Stored | `models/undo.py` (`pb.workforce.setup.undo` TransientModel: `user_id, company_id, kind, payload(Json), summary`), `models/company.py` (4 setup-state fields), `models/employee.py` (create hook, H.2) |
| JS | `setup_studio.js` (root), `setup_util.js` (helpers), `setup_drawer.js`, `preview_panel.js`, `step_*.js` (one OWL component per step), `takeover.js` |
| Tests | `tests/test_setup.py, test_people.py, test_rules.py, test_golive.py, test_p5a.py, test_p5c.py, test_static.py` (tag `wfsetup`, `post_install -at_install`) |

### B.3 How it is registered and opened
- `views/setup_action.xml:5-8` `ir.actions.client` `action_setup_studio`, tag `pb_workforce_setup_studio`.
- `registry.category("actions").add("pb_workforce_setup_studio", SetupStudio)` `setup_studio.js:465`.
- Tag starts with `pb_` so the Payobook sidebar stays (`setup_studio.js:7-8`).
- Current step in the URL: `initialStep()` :176-191 reads `router.current.step` when `cur.action` matches the action id/xmlid,
  else `context.pb_wfs_step`; `props.updateActionState({step})` in `setup()` AND on change (:149-151, :309; ledger WS4).
- Old doors are taken over from the NEW module with `registry…add(…, {force: true})` / `patch`, never by editing the owners
  (`takeover.js:1-25`, `openStudio(action, step)` :49-54). Same pattern fits re-pointing `pb_onboard_wizard`.

### B.4 Layout pieces (reuse vs copy)
| Piece | Implementation | Verdict |
|---|---|---|
| 3 columns | `.pbws-work { grid-template-columns: 232px minmax(0,1fr) 320px; gap: 20px }` scss :124-125; `<nav class="pbws-steps">` xml :67, `<main class="pbws-stage">` :80, `<aside class="pbws-card pbws-pv">` :109; steps rail sticky `top:72px` :131; preview sticky :767; breakpoints 1180 (2 cols) / 820 (1 col) / 600 :848-905 | copy + rename prefix |
| Top bar + progress | xml :10-37 (`HubBackChip back tone='light'` from `@pb_hub/js/hub_nav`), `progressLine/progressStyle/doneCount` js :449-457 | copy; HubBackChip/hubBack reusable as-is |
| Step status | server `load()['steps'] = [{key, state:'done'|'todo'|'warn', text}]` (`setup.py:166`, `_steps`), rendered by `stepClass/status` js :446-461 | copy pattern (status from server) |
| Step API object | `this.api = {addGuard, go, refresh, toast, setBar, onConfirm, …}` js :99-145; leave guards `go()` :297-314 | copy |
| Load/refresh | one `load()` + sequence-guarded `refresh()` js :201-246 | copy |
| Bottom nav | `.pbws-nav` xml :88-107: Back = previous step title; one solid button = `current.next` / step bar / confirm | copy |
| Drawer 480 px | `SetupDrawer` `setup_drawer.js` (props `title, subtitle, onClose, slots`; Esc + scrim close, Tab trap, focuses panel), template xml :879; scss `.pbws-scrim` :424 | copy (it is not exported from a shared kit; `pb_wf_kit` WfDrawer is 320 px) |
| Toast + Undo | `toast(msg, {kind, undo, ms})` js :324-339, 8 s, centred over stage (`stageCentre`), template xml :115-124, scss :746-764; Undo = server row `pb.workforce.setup.undo` + `undo(undo_id)` (`people.py:777`) | copy the toast; undo rows are wfsetup-specific |
| Sticky bulk bar | `.pbws-bulk` xml :539-548, scss :411-421 | not needed for single hire (copy if "Many at once" ever lands here) |
| Icons | `icon(name,size)` cache over `ic()` from `@pb_import_kit/js/import_icons` (`setup_util.js:17-23`; new markup per call re-inserts DOM) | reuse pattern, own cache |
| SCSS tokens | `.pbim.pbws { --pbws-ink, -muted, -faint #94A0B4, -line, -line2 #EEF0F6, -canvas, -card, -p, -p-h, -p-soft, -p-light, -p-dark, -ok, -ok-soft, -warn #B45309, -warn-soft #FDF1DD, -err, -err-soft, -r 14px, -shadow, -display 'Manrope' }` mapped onto `--pbim-*` with fallbacks, scss :16-38 | copy with a new prefix (WS1: `pbws-` is taken; grep a free one, e.g. `pbnh-`) |

### B.5 The wfsetup "live pay example" is NOT a payslip
`pb.workforce.setup.pay_example(employee_id, in_minutes, out_minutes, rules=None, day_kind='weekday')` `rules.py:780-790` →
`_pay_example` :800-948: picks a REAL employee's first shift day this week, builds bands/breaks/night windows from the screen's
unsaved rules and calls `calculate(...)` from `odoo.addons.pb_attendance_policy.engine` (import `rules.py:42`). Output = hours
(late minutes, worked/normal/overtime/night hours, rate %). Writes nothing. **It never touches the formula engine or money** —
nothing to reuse for the first-payslip example except the shape (server returns `{error, fix}` naming the step that fixes it,
`_example_error` :793-798).

### B.6 WFSETUP ledger gotchas that will bite a sibling studio (`docs/handovers/wfsetup/WFSETUP_LEDGER.md`)
- WS1 CSS prefix must be grep-checked free; `pbws-` is taken.
- WS2 A user without company read gets AccessError on `env.company.name`; read the company with sudo after the gate.
- WS3 `upd_p6_t_tpl` needs one `-u all` before tests; it lacks some modules.
- WS4 Call `updateActionState({step})` in `setup()` too, or a reload loses `?step=`.
- WS5 Local server serves the old bundle after a static edit; purge `/web/assets/%` and restart.
- WS6 Chrome MCP drag sends only end points; windows stop at 500 px (use `emulate`).
- WS9 Any roster write by a non-HR user trips the HR-only `pb_attendance_policy_id` read; pass `pb_policy_id` or read with sudo.
- WS10 Escape never reaches a window `keydown` listener; listen with `{capture: true}`.
- WS11 Sass `min()/max()` with mixed units kills the whole backend bundle; write `unquote("min(…)")`.
- WS12 Undo toast lasts 8 s: Apply + Undo in one script call; keep screenshots inline.
- WS13 Never `display:flex` on a `td`; `table-layout: fixed` + `colgroup`.
- WS14 A drawer must focus its dialog element, not the first option.
- WS15 "Has a working week" = member row covering today; a future start counts as "No working week yet" (a new hire starting next month WILL show this).
- WS16 Public-holiday rows: `calendar_id` = company calendar, create far out then write UTC bounds (`pb.holidays._create_row`).
- WS17 Global `[type=text] {display:block;width:100%}`: inline inputs need `display:inline-block`.
- WS18 Half-typed number box reports `""`; never write NaN/empty back into reactive state (wage box!).
- WS20 Overtime rate rows are picked by NATIONALITY (`hr.employee.country_id`), not country of work.
- WS22 `_t()` has no `%%` escape.
- WS24 Never set studio state from a step's `onWillStart` (endless RPC loop); use `onMounted`.
- WS25 `pb.holidays.add/…` gate on `env.user`; sudo does not help.
- WS28 Bulk writes on tracked fields need `tracking_disable=True, mail_notrack=True`.
- WS32 `odoo-bin i18n export -c <conf> -d <db> -o <file>.pot <module>`; resync `.po` from the new `.pot`.
- WS34 One-letter weekday msgids cannot be translated; use luxon `toFormat("ccccc")`.
- WS36 A `git archive` baseline needs `pb_import_kit` beside it (static icon test).
- WS37 In one test transaction `write_date` never moves.
- WS39 The export only sees a LITERAL `_t("…")` first argument.
- WS40 `_t` import must be exactly `import { _t } from "@web/core/l10n/translation";` (double quotes, nothing after `;`).
- WS42 Numbers: use `formatFloat` (web) / `formatLang` (server), never `toLocaleString()`; switch walk users' language via the menu.
- WS43 On sudima uid 2 is not an administrator; tests needing one create one.
- WS45 A template-flagged DB copy on the live box must be served by a separate `odoo-bin` through a tunnel.
- WS46 A table can keep showing a value after Undo until reload — refresh after Undo.

---

## C. Country of work, pay scheme, currency

### C.1 Fields
- `hr.employee.payroll_country` Selection `pb_hr_payroll_base/models/hr_payroll_structure_base.py:266-272` (VN, ID, IN, SG, MY),
  `selection_add` TH, KH, PH `pb_hr_payroll_formula/models/employee_work_timezone.py:70-71`; relabelled "Country of Work"
  `pb_employee_form_tidy/models/hr_employee.py:28-31`. Plain stored field, no compute.
- `hr.contract.payroll_country` Selection `hr_payroll_structure_base.py:279-285` — **VN, ID, IN, SG, MY only** (writing TH/KH/PH
  raises). No compute; only `_onchange_struct_id` (:339-343) sets it from `struct_id.payroll_country_code`.
- `hr.employee.country_id` = nationality (`hr/models/hr_version.py:60-61`, on the version record, `groups=hr.group_hr_user`).
- Writers of employee `payroll_country`: "Fill Country of Work" wizard (`pb_employee_form_tidy/models/country_of_work_fill.py:277`,
  HR manager; order: paying scheme's `country_code` → company country), pay-data import creating a person
  (`pb_hr_payroll_formula/models/payroll_import_batch.py:1813-1815`: `vals['payroll_country'] = formula_config.country_code` —
  the precedent to copy), connected-system staging (`pb_hr_payroll_base/models/zoho_staging_base.py:95-158`). The Add-employee
  path writes NEITHER employee nor contract `payroll_country`.
- Side effect of employee `payroll_country` at create: `employee_work_timezone.py:108-127` sets `tz` from it
  (`COUNTRY_TIMEZONES` :7-10) and clones the company calendar into that time zone (`_pb_in_work_timezone` :32-58,
  copies the calendar's closures). Contract create then copies the employee calendar only if `resource_calendar_id` is not in
  vals (:130-140) — **`create_contract` always passes one (A.3), overriding the time-zone calendar**.

### C.2 Who else reads "country" (they do NOT agree)
| Reader | Ladder | Where |
|---|---|---|
| Time-off kinds / leave earning | leave policy country → `payroll_country` → company country | `pb_timeoff/models/pb_timeoff.py:109-116` |
| Trial-period policy | work address country → **nationality** → company | `pb_probation/models/probation_policy.py:88-99` |
| Fixed-term contract rule | same as trial (work address → nationality → company) | `pb_contract_rules/models/contract_rule.py:81-93` |
| Overtime rates | nationality | WS20 |
| Scheme map | department only; no country at all | C.4 |
So setting `payroll_country` alone does not move the trial period or fixed-term rule: they follow `address_id.country_id`
(work address) first. The studio must set the work address (or accept nationality) to make step 2's "What this decides" true.

### C.3 Contract currency
`hr.contract.currency_id` is a non-stored compute `_compute_contract_payroll_currency` `hr_payroll_structure_base.py:291-303`:
`{'VN':'VND','ID':'IDR','IN':'INR','SG':'SGD','MY':'MYR'}[contract.payroll_country]` else company currency. The base field
was `related='company_id.currency_id'` (`hr_contract/models/hr_contract.py:68`). Because `create_contract` never sets
`payroll_country`, **a contract made today is denominated in the company currency** (and `wage` Monetary rounds to that
currency's decimals — comment :287-290). The new path must pass `payroll_country` in the contract values.
Scheme currency: `hr.formula.config.currency_id` stored compute from `country_code` (`formula_config.py:134-139, 896-903`);
`scheme_currency()` → `{id, name, symbol, position, decimals}` (:905-925); `currency_by_country()` → `{code: {...}}` pure read (:927+).

### C.4 `pb.scheme.map` (AbstractModel, `pb_scheme_map/models/pb_scheme_map.py`)
- Ladder `RUNGS = ('segment','department','division','rule','only','none')` (:66; doc :19-41):
  1 confirmed `pb.work.segment` naming a scheme (needs a person) · 2 department map, deepest team first (via `parent_path`) ·
  3 the team's `pb.division` · 4 `hr.formula.scheme.assignment.domain` evaluated on the employee (needs a record) ·
  5 the company's ONLY active scheme (`_only_scheme(company_id, cycle_type)` :254-270, `limit=2`, must be exactly one) · 6 none.
- `resolve(employee, cycle_type='any', on_date=None) -> {config_id, config_name, rung, via}` :274-287;
  `resolve_many(employee_ids, …)` :339-457. Team comes from the open contract's `department_id`, else `hr_version.department_id`
  via raw SQL (`_departments_for` :102-143) — needs `flush_all()` after writes in the same transaction.
- **Country is not a rung.** The map never filters by `payroll_country`.
- Stored answer on the person: `hr.employee.pb_paid_by_id`, `pb_paid_by_advance_id`, `pb_paid_by_rung`, `pb_paid_by_stale`
  (default True) `pb_scheme_map/models/hr_employee.py:47-60`, recomputed nightly / when stale. All readonly.
- **Hypothetical person (team + company, no record): the nearest API is `pb.updates.desk._department_schemes(dept_ids)`**
  `pb_updates/models/updates_joiners.py:219-265` → `{dept_id: {'ids': {config_id}, 'names': {config_id: name}}}` for every cycle
  type (rungs 2, 3, 5 only). It lives in pb_updates (wrong home) and returns a SET, not the one main-run answer.
  **Recommended seam:** factor a pure `pb.scheme.map.resolve_for_team(department_id, company_id, cycle_type='any', on_date=None)
  -> {config_id, config_name, rung, via}` out of `resolve_many`'s rungs 2/3/5 (the loop body :383-453 already works on
  `chain`/`company_id` only), make `_department_schemes` call it, and add a country check on top in the studio: if the
  answer's `country_code` ≠ the chosen country, say so; if there is no answer, list active schemes of the company with that
  `country_code` (a NEW rule — there is no "by country" rung today).
- `hr.formula.config.schemes_for_employee(employee)` / `component_scope_for_employee(employee) -> {known, schemes:[{id, name,
  country_code, country_name, currency, currency_symbol, role}], codes}` `pb_hr_payroll_formula/models/scheme_component_scope.py:65-195` — record only.

### C.5 Scheme models
- `hr.formula.config` (`pb_hr_payroll_formula/models/formula_config.py`): `name` :48, `code` :54, `cycle_type` :74-79
  (regular/mid_cycle/end_cycle/full_final), `use_proration/proration_basis/proration_component_ids/proration_rounding` :80-101,
  `country_code` Selection required :116-125 (VN ID IN SG MY TH KH PH), `country_id` stored compute :127-132,
  `currency_id` stored compute :134-139, `company_id` required :183-188, `rule_ids` :198, `state` :529-535
  (draft/testing/validated/active/archived; only `active` pays).
- `hr.formula.scheme.assignment` (base `pb_hr_payroll_formula/models/formula_scheme_assignment.py:13-23`: `config_id, department_id
  ("Segment"), domain, sequence, active`; `pb_scheme_map/models/formula_scheme_assignment.py:73-97` adds `division_id,
  cycle_type, company_id, source, confidence, note, date_from, date_to`).
- **Per-person scheme override ("Use a different scheme" in POC vPay :484) DOES NOT EXIST.** The only person-level ways are a
  work segment (`pb.work.segment`, rung 1) or an assignment row with an employee `domain` (rung 4). Choosing another scheme for
  one hire = writing one of those, or a decision to drop the picker.

---

## D. Contract

- Two contract stores exist on this build: core Odoo 19 `hr.version` (`hr/models/hr_version.py`: `contract_date_start` :145,
  `contract_date_end` :146-148, `trial_date_end` :149-150 (hr_manager), `wage` :167, `contract_type_id` :174, all on the
  employee's version) and the ported `hr.contract` (`hr_contract/models/hr_contract.py:19`, payroll's model, read by payslips,
  the scheme map SQL and fill-in). **`create_contract` writes `hr.contract` only** (A.3); nothing syncs it to `hr.version`.
- `hr.contract` fields used: `date_start` (required, default today) :32, `date_end` :33-34, `trial_date_end` :35-36, `wage`
  (Monetary, required) :41, `state` draft/open/close/cancel :43-49, `resource_calendar_id` :37-40, `structure_type_id` :26,
  `contract_type_id` :56, `job_id/department_id/company_id` computed from the employee at create (`_compute_employee_contract`
  :94-101). Overlap constraint `_check_current_contract` :116+ (one non-draft contract at a time). om_hr_payroll adds
  `type_id` "Employee Category" required (`om_hr_payroll/models/hr_contract.py:72-74`), `advantages_ids` :75-77, `struct_id`.
- **Permanent vs fixed term:** no single field. Fixed term = `date_end` set and not a trial agreement
  (`pb.contract.rule._is_fixed` `pb_contract_rules/models/contract_rule.py:117-127`). Vietnam only: `vietnam_contract_type`
  (`indefinite|definite|seasonal|probation`, default `indefinite`) `pb_hr_payroll_vietnam/models/hr_contract_vietnam.py:18-23`
  and `pb_payroll_contract_type` (permanent/probation, pb_employee_vault). Employment kind lives on `hr.version.employee_type`
  (+`intern`) `pb_contract_lifecycle/models/hr_typing.py:59-69`.
- Fixed-term limits per country: `pb.contract.rule` (`contract_rule.py:31-66`: `country_id, company_id, max_in_row,
  max_months_each, max_months_total, gap_days`), `rule_for(employee)` :95-111, `check_extension(contract, months)` :194.
- **Trial period policy:** `pb.probation.policy` `pb_probation/models/probation_policy.py:26-63` (`country_id, duration_months,
  evaluation_lead_days, feedback_window_days, extension_grace_days, default_extension_months, company_id, active, sequence`).
  `policy_for(employee)` :102-117 (country ladder C.2, first match, falls back to the country-less row); `settings_for(employee)
  -> {policy_id, policy_name, duration_months, …}` :120-160; `trial_end_for(employee, joined_on=None)` :163-184 =
  `add_months(start, months)` (same day N months later, clamped — `probation_common.py:206`; NOT minus one day as the POC
  `trialEnd()` :379 draws). Seeded: VN 2, IN 3, SG 3, ID 3, default 2 months (`data/probation_policy_data.xml:19-76`).
  All take an employee RECORD; for a hypothetical, call `policy_for`'s search directly with the chosen country (small refactor:
  `policy_for_country(country_id, company_id)`).
- Applied at creation? **Not by Add employee.** It is applied when an ONBOARDING journey case opens:
  `pb.journey.case.action_open` → `setup_probation` → `_set_trial_end` (`pb_probation/models/journey_case_ext.py:24-108`)
  writes `emp.pb_set_trial_end(end)` (`pb_probation/models/hr_employee.py:157-180`) = **`hr.employee.trial_date_end`
  (the VERSION field), not `hr.contract.trial_date_end`**, and only when empty and a country policy exists. Hiring opens that
  case (`offer_closure.py:430-458` → `pb.zoho.pipeline._open_case(employee, 'onboarding', anchor, company)` +
  `_after_onboard(case, {...})`, `pb_zoho_bridge/models/zoho_pipeline.py:555,657`). Add employee opens no case.
- Country rule forbidding a trial on a fixed-term contract: **DOES NOT EXIST** (no field on `pb.probation.policy`, nothing in
  `pb_contract_rules`). The POC's "Fixed-term contracts in Indonesia cannot have one" needs a new policy flag.

---

## E. FILLIN — the scheme's usual answers (`pb_hr_payroll_formula/models/contract_fill_in.py`)

- Where the usual answer lives: `hr.formula.rule.default_value` (Float, `formula_rule.py:559`) on the scheme's rule, with words
  in `value_labels` (`'0=No;1=Yes'`, parsed by `parse_value_labels` :60-86). Rule flags: `is_contract_component` (:674),
  `is_text_component` (:788), `value_kind` (:808).
- Trigger: `hr.contract.create` → `_pb_fill_in_defaults()` unless context `pb_skip_fill_in` (:432-437); also when "Paid by"
  becomes known (`pb_scheme_map/models/hr_employee.py:191-210`).
- `_pb_fill_one(contract)` :496-548: `flush_all()`; schemes = `_pb_fill_schemes(employee)` (:477-494, via
  `component_scope_for_employee`, ACTIVE only); for each scheme the rules
  `is_contract_component and not is_text_component and value_kind in NUMERIC_FILL_KINDS and code and |default_value|>1e-9`
  sorted `(sequence, id)` (:516-522); skips any code already on the contract (`have` :512-513, "first scheme wins; never
  overwritten"); creates `hr.contract.advantage {contract_id, advantage_template_id (template_for_rule :293-317), amount,
  pb_fill:'auto'}` with sudo + `pb_fill_in_write` context, and logs `hr.contract.advantage.change` `'auto_default'`.
  "No" = absence of a line (zero defaults are never filled).
- Marks: `hr.contract.advantage.pb_fill` ('auto'), `pb_checked_by`, `pb_checked_at` (:326-331); any later write of
  `amount/text_value` without `pb_fill_in_write` clears the mark (:333-347). Review: `pb_fillin_unchecked()` :551-554,
  `pb_fillin_check(line_ids)` :582.
- **Preview for a scheme without a contract: DOES NOT EXIST as a method.** Nearest seam = the rule filter at :516-522 — factor it
  into `hr.formula.config._pb_usual_answer_rules()` (returns the rules) and have `_pb_fill_one` call it. For display per rule:
  `name`, `code`, `default_value`, `value_label_control()` ('toggle' for yes/no, :209-220), `value_label_options()` :189-193,
  `value_to_text(amount)` :168-180, `value_word_choices()` :222-229 — all on `hr.formula.rule`, record-free.
- **Overrides at creation:** the fill skips codes already present, so pass the person's choices as lines IN the create:
  `hr.contract.create({..., 'advantages_ids': [(0, 0, {'advantage_template_id': tmpl.id, 'amount': x})]})` — lines that exist
  before `_pb_fill_in_defaults` runs are never touched and carry no `pb_fill` mark (correct: a person chose them). "Off" for a
  yes/no = a line with `amount 0.0` (blocks the auto line). Caveats: (1) an HR officer has READ-ONLY access to
  `hr.contract.advantage` (comment :507-508) → the lines must be written with sudo behind `require_hr`; (2)
  `create_contract` builds `cvals` from a fixed key list and drops anything else → it needs a new `lines`/`components` key for
  a NEW contract (today only renewals carry lines); (3) the payload of the proposal must carry those lines so the approved replay
  writes them.

---

## F. First-payslip example — candidates and verdict

| Candidate | Inputs | Needs real records | Writes | Fit |
|---|---|---|---|---|
| F8 simulation `hr.formula.simulation` (`pb_hr_payroll_formula/models/formula_simulation.py:110+`, facade `pb_formula_studio.simulate_prepare/batch/result/drop` `pb_formula_studio/models/pb_formula_studio.py:4629-4660`) | a scheme + its LAST PAY RUN's stored `formula_input_values` | yes (past payslips) | transient sim row | No — population delta tool |
| What-if sliders `whatif_*` (`pb_formula_studio.py:4665-4713`) | same overlay sim | yes | transient | No |
| Overlay evaluator `_evaluate_config_overlay(config, input_values, overrides, value_overrides)` (`formula_simulation.py:43-105`, module function) | an input dict | config only | none | Kernel only |
| Read-only sample evaluator `hr.formula.sample.data.new({'config_id': id})._evaluate_rules_with_dependencies(inputs, readonly=True, errors=errors)` (`formula_sample_data.py:595-640` → `formula_program.run_sample(steps, inputs, errors)` `formula_program.py:133-180`; precedent `pb_formula_studio.preview_from_payslip` :2271-2360) | an input dict | config only (`.new()` record) | none | **Best evaluation kernel** |
| Hiring offer cost `pb.hiring.offer.action_calculate_employer_cost` (`pb_hiring/models/offer_cost.py:71-128`) + profile `pb.hiring.cost.profile` (:13-44: `company_id, country_id, config_id, gross_input_id, employer_rule_ids, defaults_json, effective_from/to`) | monthly gross into ONE named input + approved defaults JSON for every other input (missing input = refusal) | the profile row | writes the result HTML on the offer | Closest "hypothetical person" precedent; employer cost only, no proration, strict, needs a profile per country |
| Real payslip `compute_sheet()` (`hr_payslip_formula.py:1068-1110` → `_pb_compute_sheet_with_formulas` :167-238) | employee + contract + payslip | yes | payslip fields + lines; **non-application path calls `rules._compute_dependencies()` and `rule.evaluate()` which WRITE on the shared scheme rules** (:262-263, :287-288) | Truthful but heavy |

How inputs are really built (`hr.payslip._get_formula_input_values(config, provenance=None)` `hr_payslip_formula.py:614+`):
input rules only; lanes per `config._source_kind_rank()`; `BASIC/WAGE/BASE` codes read `contract.wage` (hard-coded map :736-740);
mapped employee/contract fields via `hr.payslip.import.mapping` (`destination_type='field'`, :704-713); contract components via
`hr.payroll.import.batch._contract_component_values(contract, config)`; `WD_*`/`HOURS_*` from `worked_days_line_ids` (:752-763);
connected-system feeds; `history.*` running totals; else `rule.default_value`. Rebuilding that for a hypothetical without records
would be a second resolver (forbidden: "no parallel engine").

Totals: the one rule is `hr.payslip.line.pb_pay_totals()` → `{gross, deductions, net, employer_cost}`
(`om_hr_payroll/models/pay_bands.py:57-117`; `hr.payslip.pb_pay_totals()/pb_net_amount()` :195-204), reading line
`pay_role` (rule `net_role` `formula_net_role.py:602-614`), `component_detail`, `category_id`. It works on lines, so either real
lines or `hr.payslip.line.new({...})` in-memory lines.

Proration of a mid-month start: **no engine-wide joiner proration.** `config.use_proration` (formula_config.py:80) only prorates
mid-period CONTRACT VALUE CHANGES of listed components (`payroll_import_batch._apply_proration` :2563-2680, import path); the
application path refuses it (`application_payroll_source.py:767-768`). Worked days come from
`om_hr_payroll` `get_worked_day_lines(contracts, date_from, date_to)` (`om_hr_payroll/models/hr_payslip.py:416+`), which uses the
payslip period and is **not clamped to the contract start** (:423-424). So a joiner's first month is prorated only if the scheme's
formulas use day counts that come from attendance/period inputs or a hand-entered input (blueprint helpers `PAIDDAYS/STDDAYS/
PAIDCALD`, `pb_blueprint/models/recipe_schema.py:99-115`). Per scheme, not guaranteed.

**Verdict — feasible, with one design:**
1. Server method on the new facade, e.g. `first_payslip_example(draft) -> {ok, month, period:{from,to}, days:{worked, of},
   lines:[{name, amount, band}], gross, deductions, net, currency, scheme, notes[], error, fix}`.
2. Inside `with cr.savepoint(): … raise _Rollback()` (precedent `pb_blueprint/models/blueprint_components.py:45` class
   `_Rollback`, `bp_recipe_preview` :753-776, `raise _Rollback()` :766), context `tracking_disable=True, mail_notrack=True, mail_create_nolog=True,
   pb_skip_fill_in=False`, sudo behind `require_hr`: create `hr.employee` (department, job, company, `payroll_country`),
   `hr.contract` (state `open`, wage, start, `payroll_country`, the usual-answer lines/overrides — fill-in runs for real),
   `hr.payslip` (draft, `date_from`=start-of-month, `date_to`=end-of-month, `contract_id`, `formula_config_id`=resolved scheme,
   `calculation_method='formula'`), worked days via `onchange_employee_id(date_from, date_to, emp.id, contract.id)['value']`
   (`hr_payslip.py:698`) — clamp the day counts to the start date yourself and SAY so on screen.
3. `inputs = slip._get_formula_input_values(config)` (read path), evaluate with the read-only sample kernel (never
   `compute_sheet`, to avoid rule writes/locks), turn the results into `hr.payslip.line.new(...)` per payslip-visible rule and
   call `.pb_pay_totals()`. Copy plain dicts out BEFORE the rollback; then `env.invalidate_all()`.
4. Debounce on the client (wage typing) and sequence-guard replies like `setup_studio.js:229-246`.
Risks to test, not assume: (a) ~17 `hr.employee`, 9 `hr.contract`, 8 `hr.payslip` create overrides run every call
(`pb_tenancy/models/hr_employee.py:37-39` **refuses at the seat limit** → example fails on a full plan; calendar clone takes an
advisory lock `employee_work_timezone.py:41`; scheme-map stale SQL; attendance-policy join); (b) mail tracking precommit data for
rolled-back ids — keep the no-tracking context or the request can fail at commit; (c) PostgreSQL sequences are not rolled
back (none found on these creates in pb_*; om_hr_payroll consumes `salary.slip` only in its own `compute_sheet` :400 — do not
call it); (d) cost unknown — `formula_program.py:8-9` records 8.77 s/person on a 409-rule scheme BEFORE compilation; measure per call and debounce; (e) a scheme whose inputs come from a pay
data file or connected system shows defaults — the panel must say "example, from the scheme's usual values".
Cheaper fallback if (a) bites: the offer-cost pattern (pure dict in, `run_sample`, no records) with a per-country profile —
honest but needs set-up per scheme.

---

## G. Pay bands and pay scales

- "Place a new hire" = palette entry `pay_place_hire` (`pb_pay/static/src/js/pay_palette.js:80-88`) → action
  `pb_pay.action_pb_pay_place` (`pb_pay/views/pb_pay_action.xml:25-29`, tag `pb_pay`, `pb_tab='bands', pb_focus='place'`).
- Server `pb.pay.bands.place_hire(job_id=None, level=0, experience_pct=50)` `pb_pay/models/pb_pay_bands.py:1134-1240` →
  `{ok, job, job_id, people, median(+labels), market_label, experience_pct, levels[], band: _band_dict(...) | None, offer,
  offer_label, sentence, dots}`. `_band_dict` (:428-450) gives `min, mid, max` + labels, `currency_id, currency_code, country_code,
  level, family`. Band = FIRST `pb.pay.band.job` link of the job (:1151-1153), optional same-family `level`; **no country or
  date filter** (`pb.pay.band.country_code` exists, `pb_pay/models/pb_pay_band.py:77-78`; `bands_on(on_date, company)` :190-203
  is not used here). Currency = the band's.
- Gate: `READ_GROUPS = (pb_pay.group_pay_manager, pb_pay.group_pay_viewer, pb_group.group_group_admin, hr.group_hr_manager)`
  (`pb_pay_bands.py:48-53`) — **a plain HR officer gets AccessError**; the studio must catch it and hide the band.
- Pay scales: `pb.pay.scales.resolve(job, company=None, day=None, employee=None) -> {found, why, grade, scale, version, step,
  amount, sentence, steps}` (`pb_pay_scales/models/resolver.py:99-151`; with no employee only the scale's own country/company is
  checked); screen wrapper `joiner_suggest(employee_id=0, job_id=0, date_start=None, company_id=0, wage=None)`
  (`pb_pay_scales/models/screen.py:807-834`, HR user or scales reader; adds `reasons, show_why, grade, scale, typed_step,
  typed_off`). Empty wage is filled server-side in `create_contract` (A.5) and the contract is placed by
  `place_new_contract(contract, reason, source, note)` (`resolver.py:166-196`).

---

## H. Schedule and time

- Give ONE employee a working week from a date: `pb.workforce.setup.assign_week(employee_ids, week_id, date_from, start_week=0,
  mode='replace') -> {moved, kept, already, undo_id, summary}` (`pb_workforce_setup/models/people.py:364-407`; preview
  `assign_week_preview` :338-361). Writes `pb.shift.pattern.member {pattern_id, team_id, employee_id, date_from, date_to=False}`
  (+ a rotation team when needed). **Gate `_gate_edit` = attendance manager** (`setup.py:62-75`) — an HR officer is refused; the
  new-hire apply must create the member row itself (sudo behind the HR gate) or require that role.
  Team default: `pb.shift.pattern.department_id` (`pb_shift_patterns/models/shift_pattern.py:56-59`) — a "usual week for this
  team" is a search on it (no existing helper). Slots: `pb.shift.pattern.slot` (:142-160).
- Late and overtime rule group: `hr.employee.pb_attendance_category` Selection `worker|manager`, and `pb_attendance_policy_id`
  (`pb_attendance_policy/models/policy.py:179-180`, both `groups='hr.group_hr_user'`). On employee create, if the company has
  exactly ONE active policy, the person is pointed at it and gets `worker` when no category was passed
  (`pb_workforce_setup/models/employee.py:14-42`). Passing `pb_attendance_category` in create vals is respected. Bulk setter
  `set_late_rule(employee_ids, group)` `people.py:726` (attendance manager).
- Clock: `hr.employee.pb_clock_code` Char "Clock number", unique per company (constraint), `groups='hr.group_hr_user'`
  (`pb_clock/models/hr_employee.py:11-31`). Punch matching ladder: `pb_clock_code` → `barcode` → `identification_id`
  (`pb_clock/models/clock_pairing.py:230-253`). Assign + pair backlog: `pb.clock.lens.assign_code(code, employee_id)`
  (`clock_lens.py:590-622`, attendance officer). **"Next free clock number" DOES NOT EXIST**; fingerprint enrolment has no field.
- Leave earning (`pb_leave_setup/models/earning.py`): service start = `date_of_joining` then `first_contract_date` (`_service_start`
  :114-121; never the contract start). `hr.employee.date_of_joining` is defined in `pb_hr_payroll_formula/models/hr_employee.py:31`
  and **is not written by Add employee**. `first_contract_date` is a stored compute from `hr.contract` dates
  (`hr_contract/models/hr_employee.py:24,58-61`). Monthly share `_month_share` :151-180 (per-year/12 × worked share of the month);
  yearly `_year_share` :182-207.
- Per-country annual entitlement for display: `hr.leave.type.pb_ls_days_per_year` (`pb_leave_setup/models/leave_type.py:30`)
  where `pb_ls_earning != 'none'` (:23), country by `pb.timeoff._type_country(lt)` = `(lt.pb_policy_country_id or lt.country_id).code`
  (`pb_timeoff/models/pb_timeoff.py:102-107`); ready-made kinds carry `pb_ls_starter_key` like `VN.annual` (:56-59). Extra days for
  service `pb_ls_step_ids`. A Rize-style leave policy on the person (`pb_leave_policy_id`, `pb_timeoff/models/rize_policy.py`)
  overrides — readable, not required.
- Public holidays: `resource.calendar.leaves` with no resource on the COMPANY's working calendar (`pb.holidays`,
  `pb_timeoff/models/pb_holidays.py:1-25`, `_column` :178 reads `company.resource_calendar_id`). **Per-country holiday calendars
  DO NOT EXIST**; a person gets the closures of their own calendar (company calendar, or its time-zone clone, C.1). In a company
  paying in two countries everybody shares one holiday list. The POC's "Follows the country of work, not the nationality" is
  only true for one-country companies.

---

## I. Security, i18n, tests

- Groups: `require_hr` = `hr.group_hr_user` | `hr.group_hr_manager` | superuser (`newhire_approval.py:37,43-51`). People hub
  Employees gate `EMPLOYEE_GATE = [pb_records.group_records_viewer, base.group_system, hr.group_hr_user,
  pb_demo.group_payobook_demo]` (`pb_people_hub/static/src/js/people_hub.js:67-72`); contracts `CONTRACT_GATE` :75-80 —
  so a records viewer or demo user SEES the Add employee button but `create_employee` refuses them. Bands need
  `hr.group_hr_manager`+ (G); assign-week needs attendance manager (H); fill-in check needs contract/payroll manager
  (`contract_fill_in.py:52-55`). Sensitive employee fields used here are HR-only (`country_id`, `pb_attendance_*`,
  `pb_clock_code`, `trial_date_end` = hr_manager).
- Record rules that matter: newhire proposal seat/HR rules (A.4); bank change requests (pb_bank_ocr); undo rows own-only
  (`pb_workforce_setup/security/undo_rules.xml`).
- Palette/rail gating: entries are `palette.add(id, {id, label, sublabel, icon, groups, requires, action: {xmlid, lens}})`
  (`pb_people_hub/static/src/js/people_hub_palette.js:42-66`); "the door is an XMLID, not a tag" (:16-25). A new full-screen
  studio needs its own `ir.actions.client` xmlid and should be opened by xmlid.
- Languages shipped by the shell: `vi_VN.po`, `id_ID.po` + `.pot` (`pb_workforce_setup/i18n/`). `pb_people_advanced/i18n` has
  `vi_VN.po, id_ID.po`; `pb_people/i18n` only `vi_VN.po`. PO loading rules: memory note "PO translation loading rules" (three
  markers per entry: `#. module:`, `#. odoo-python|odoo-javascript`, `#: code:addons/<m>/<path>:0`; `.pot` filters the `.po`);
  repo references `docs/handovers/wdgap/WDGAP_LEDGER.md:95-96` → `docs/handovers/updates/UPDATES_LEDGER.md` and the LOOK ledger.
- Test conventions: `@tagged('post_install', '-at_install', '<programme tag>')`, `TransactionCase`, users via `new_test_user`
  (`pb_workforce_setup/tests/test_people.py:18-50`); static gates file (`tests/test_static.py`: no "Odoo" in visible text, every
  icon exists, no emoji, right tag). Commands used by wfsetup (private conf in scratch, addons path = official addons + the
  worktree, DB = copy of `upd_p6_t_tpl` + one `-u all`, WS3): baseline `-i <module> --test-enable --test-tags /<module>,/<deps…>`
  on a `git archive HEAD` snapshot, then `-u <modules> --test-tags …` on the worktree (`WFSETUP_P2_REPORT.md:20-23`,
  `WFSETUP_P5A_REPORT.md:20-24`). Plus a Chrome walk B1..Bn with console check (standing rule).

---

## Open questions / risks for the architect
1. **Scheme by country.** The map knows teams, not countries. Decide: team decides scheme and the country is checked against
   it (recommended), or a new "by country" rung. And drop or build the per-person "Use a different scheme" picker (no seam today).
2. **Country of work must be written in four places to be true**: employee `payroll_country`, contract `payroll_country`
   (currency!), the work address (trial period + fixed-term rule read address → nationality), and the time zone/calendar.
   Contract `payroll_country` lacks TH/KH/PH.
3. **Two trial-end fields** (`hr.version.trial_date_end` read by probation, `hr.contract.trial_date_end` on the payroll
   contract). Pick one to write at hire (recommend the employee/version field via `pb_set_trial_end`, as probation does).
4. **First-payslip example** = savepoint + rollback over real records (F). Confirm the owner accepts "example from the
   scheme's usual values" wording and that a seat-limit tenant shows no example.
5. **Approval payload is frozen**: "change it before approval" = withdraw + resend. And the full account number is stored in
   the proposal JSON — move bank details out of the payload or accept it.
6. **Keep or replace `create_employee`**: four callers + three patchers depend on it (A.5). Recommended: the studio calls a NEW
   facade that builds one payload and ends in the SAME `pb.newhire.proposal` (kind `employee`), whose `_apply_employee` is
   extended to do the extra writes (payroll_country, lines, week, late rule, clock number, trial end, case). The old tag is
   re-pointed with `force` from the new module.
7. **Role gaps**: an HR officer cannot read pay bands, assign a working week, or write contract component lines. The approved
   apply runs as the approver — the gate list (`_proposal_gate_groups`) may need widening or sudo writes behind `require_hr`.
8. **Hiring path**: "From Hiring" / "Confirm they joined opens this screen" changes a working path that today deliberately
   skips the newhire proposal (`offer_closure.py:252-275`). Owner decision.
9. **Joining checklist + trial end from Add employee** means opening an onboarding case through `pb.zoho.pipeline._open_case`
   (lives in `pb_zoho_bridge`) — check module dependency weight, and that `pb_probation` is installed on all four DBs.
10. **Holidays per country and "next free clock number" do not exist**; either build them or soften the POC sentences.

---

## Corrections and additions found in P1 (2026-11-25)
- §A.4 "the maker can withdraw (`engine.cancel`)": true, but the mixin has no `_approval_withdraw`, so the PROPOSAL stays
  `pending` after its request is cancelled. `pb_new_hire` (`create_ext.py`, `PbNewHireProposalNH._approval_withdraw`) moves a
  studio proposal to `draft`; other new-hire proposals keep the old behaviour (ledger NH14).
- §A.4 / §C.3: the request's amount is shown in `_approval_context()['currency_id']`, i.e. the company currency, whatever the
  hire's country (ledger NH15). Studio proposals now pass the contract currency.
- §C.4 `resolve_for_team` now exists (`pb_scheme_map/models/pb_scheme_map.py`, after `resolve_many`), built from three shared
  rung helpers `_rung_department/_rung_division/_rung_only` that `resolve_many` also calls. `_department_schemes` in pb_updates
  was NOT switched to it (not in the P1 handover's §2.2 list; it returns a set over every cycle type).
- §D `policy_for_country(country, company)` now exists in `pb_probation/models/probation_policy.py`; `policy_for` calls it.
- §E `_pb_usual_answer_rules()` lives on `hr.formula.config` in `contract_fill_in.py` (class `HrFormulaConfigUsualAnswers`,
  not `formula_config.py`); `_pb_fill_one` calls it.
- §I the recipe DB `upd_p6_t_tpl` has no active scheme and a US/USD company; it lacks `pb_pay_scales` and `pb_contract_rules`
  (ledger NH16).
- MRO on the local DB after install (top first): `pb.people.onboard.wizard` pb_new_hire → pb_pay_scales → pb_orgchart →
  pb_people_advanced; `pb.people.contract.wizard` pb_new_hire → pb_pay_scales → pb_people_advanced. The studio path is written to
  work in either order (extras ride in the context key `pb_nh_hire`, read by the `hr.employee` / `hr.contract` create overrides).

## Corrections and additions found in P2 (2026-11-25)
- §H `assign_week` has no post-gate helper to reuse: `_assign_plan` (which also refuses a past date and, for a
  multi-week rotation, may need a NEW team) plus inline creation. `save_pattern` replaces a whole pattern. Both gate on
  `has_group`, which sudo does not bypass (ledger NH23). The studio's week leg creates the one
  `pb.shift.pattern.member {pattern, Team A (lowest sequence), employee, date_from = first day}` row with sudo; the
  model's `_check_member` judges overlaps. The day strip reads `_pb_slot_map` + `_pb_cycle_index` for Team A's offset,
  as `pb.workforce.setup.people()` does.
- §H the employee's leave country is `pb_policy_country_id`; `country_id` on a leave type follows the company (NH22).
- §H public holidays: `pb.holidays._column(company, first, last, today)` returns `{rows:[{date, days, name…}], next}`.
- `hr.contract.type` on this build: `name, code, sequence, country_id, is_payroll_enabled, payroll_schedule,
  wage_calculation` (no kind field). `hr.contract` has BOTH `type_id` ("Employee Category", om_hr_payroll, the one the
  contract panel shows) and `contract_type_id` ("Contract Type", hr_contract); the studio writes `type_id`.
- `pb.people._pay_symbol` read only "Paid by" (refreshed overnight), not the contract: fixed in P2 (NH29).
