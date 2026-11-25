# NEWHIRE P2 — report (Schedule and time off, Welcome and first day)

Built on worktree `gitlocal-worktrees/newhire` (branch `newhire`), 2026-11-25. Not pushed, nothing deployed, no server access.

## 1. What was built

`pb_new_hire` 19.0.1.0.0 → **19.0.1.1.0**. New dependencies (all installed on the five live databases, FACTS_ONBOARD §M3):
`pb_onboarding, pb_zoho_bridge, pb_assets, pb_doc_contracts, pb_form_studio_people, biz_access, pb_clock`. No cycle (nothing
depends on `pb_new_hire`). Working weeks (`pb.shift.pattern`), late rules (`pb.attendance.policy`), leave setup
(`pb_ls_*` fields) and the Workforce setup studio are feature-detected, never depended on.

| Layer | Files |
|---|---|
| Facade (steps 3/4/6) | `models/studio_welcome.py` (new, `_inherit pb.new.hire`): `contract_categories`, `schedule_options`, `check_clock`, `welcome_options` (+ timeline), `find_buddies`, `_letter_info` (also the step-2 tile via `decides`), `_validate_welcome`, `_values_welcome` |
| Welcome legs | `models/welcome_legs.py` (new): `pb.new.hire.legs.run` — clock → week → own_fields → login → case → buddy → equipment → letter, each in its own savepoint; `pb.journey.case._set_trial_end` override (NH21) |
| Core path | `models/create_ext.py`: late rule on the one employee create; `type_id` on the one contract create; legs called after the core, `result['legs']` + `legs_summary`; approver rows; `models/studio.py`: P2 draft keys, letter tile, `features.joiners` |
| Client | `step_sched.js`, `step_welcome.js` (new); `new_hire_studio.js` (P2_KEYS table, refreshes, "Carry on?" dialog, statuses), `step_check.js`, `step_pay.js` (category), `step_role.js` (letter tile), `record_panel.js` (working week), `step_soon.js` (now step 5 only), `studio_util.js` (shared answers), xml, scss |
| Tests | `tests/test_welcome.py` (W1–W16 + extras, 28 tests) |

**Files touched outside `pb_new_hire`** (fix 6a, nothing else):

| File | Why |
|---|---|
| `pb_people/models/pb_people.py` | `_pay_symbol(e, cache, contract=None)`: a contract that carries its own Country of Work answers with its own currency; `_wage_totals` passes each contract. Contracts without a Country of Work keep the old scheme/company answer. |
| `pb_people/__manifest__.py` | 19.0.1.3.5 → 19.0.1.3.6 |
| `pb_people/tests/__init__.py`, `pb_people/tests/test_pay_symbol.py` | new (W12) — pb_people had no tests folder |

Docs: this report; ledger NH19–NH31; P2 correction sections at the end of both fact sheets.

### 1.1 Mails and activities triggered at apply (safety rail 3)
Measured by W16 (fast lane, every leg on: email sign-in, checklist, buddy, 2 equipment chips, letter):
- **Mails: 1** — "Meet your buddy, <buddy>" to the joiner's work email, from `pb.buddy.nomination.choose` (`_tell_them`,
  behind `pb_onboarding.buddy_mail`). Hiring's `_hand_over_buddy` sends the same mails today. The buddy's own mail
  goes when the buddy has a work email. **No sign-in mail at apply** (`_auto_create_login` uses `no_reset_password`;
  the invitation is the checklist's day-one `credentials` step). No password/credential mail ever.
- **Activities: 0.**
- Chatter notes (no mail): the case's "Journey started", HR partner / check-in / equipment notes (pb_onboarding), the
  trial-end note (pb_probation, P1), and one sentence per failed leg on the employee.

### 1.2 Printing a worker's sign-in slip after creation
**Not possible.** Access › Logins for workers prints slips only from the answer of `create_worker_logins` ("the passwords
are not shown again"). For an existing login the only path is Access › the person › **Set a new password** (make one,
copy it, tell them in person; it sets "must choose a new password"). So the studio's employee-number leg drops the first
password at once and its success line says "set the first password in Access". Gap for the owner: a "print a new slip"
button on Set a new password would close it.

## 2. Results

### 2.1 Numbered tests (`-u pb_new_hire --test-tags /pb_new_hire`, local DB `nh1_base`)
**52 / 52 pass** (24 from P1 + 28 P2). W12 in pb_people: **2 / 2 pass**.

| # | Test | Result |
|---|---|---|
| W1 | `schedule_options`: team default flagged and first, day strip Mon–Fri 08:30–17:30, 40 h, field week Mon–Sat; leave row by country (SG yes, VN no); holiday count ≥ 2 + next; no patterns → `weeks False` + the sentence; `check_clock` taken/free/empty | pass |
| W2 | late rule `manager` rides the create; clock written; clock taken meanwhile → hire created without it, failed leg "Clock number … was taken by … meanwhile.", chatter sentence | pass |
| W3 | week: one member row, office week, Team A, from the first day; week archived before approval → failed leg "Set it from Workforce." | pass (no module-absent branch exists, see §3.2) |
| W4 | own fields: country filter (VN-only not asked for SG), link field `supported False`, required missing → `{ok False, step 'welcome', field 'own-x_pbfs_demo_req'}`, values written once on approval (unsupported + other-country dropped), refusal at apply → failed leg quoting the label; approver row shows "Medium" | pass (Form builder `fields_for`/`write_values` patched — no DDL in a test) |
| W5 | email: portal login linked (`pb_portal_user_id` = `user_id`, share), no mail at apply; employee number (approver manages access): login = clock number, `pb_portal_user_id` set, no first-password pattern in payload, result, answer, employee or proposal chatter; without the access right → failed leg pointing to Logins for workers; none → no user | pass |
| W6 | one onboarding case, template picked, anchor = first day, 5 tasks; re-running the legs opens no second case; checklist switched off → no case, no requests | pass |
| W7 | buddy chosen → `buddy_id`, buddy step done; none → step pending, owned by the manager's login | pass |
| W8 | chips laptop + ID card → 2 draft requests, no second laptop, linked to the laptop task, `needed_by` = first day; no chips → laptop request cancelled, task skipped "Not needed for …" | pass |
| W9 | every timeline step date == the real task due date; check-ins present; no laptop chip → no laptop line; "none" sign-in → "no sign-in yet" | pass |
| W10 | SG → general wording + "No letter wording for Singapore yet"; VN → own wording; saved as an employee document (payroll manager); failure → failed leg with the engine's sentence; no pay right in the fast lane → toggle off with the reason, letter not tried | pass |
| W11 | categories: SG permanent / fixed suggested by country + kind word, hourly never; MY none; chosen `type_id` written; not sent → the suggestion written (not "first row") | pass |
| W12 | pb_people: IDR contract row/KPI write Rp; contract without a country keeps the company sign | pass |
| W13 | P1 trial end survives the checklist opening; trial switched off stays off after the checklist opens | pass |
| W14 | approver rows: Working week, Late and overtime rule, Clock number, Sign-in, Joining checklist, Buddy, Equipment, Contract letter, Contract category, own field | pass |
| W15 | static gates (no vendor name, icons, no emoji, `_t` form, tags) + P1's 24 | pass |
| W16 | mails/activities at apply (§1.1); all legs ok; summary starts "Ready: " | pass |

### 2.2 Suites of touched modules
Walk DB `nh1_base`, `-u pb_new_hire,pb_people,pb_people_advanced,pb_onboarding,pb_probation` with those tags:
pb_people_advanced 8, pb_onboarding 9, pb_probation 11 — **28 / 28 pass** (the modules whose code the legs call or
override: the create path, the checklist set-up, `_set_trial_end`). pb_people 2/2.

That run also showed every studio send refused on the walk DB: the walk seed's own **required** "Shuttle route" applies
to every hire in the database, which is the rule working (W4). The P1/P2 test base now switches tenant-required own
fields off inside its transaction; re-run on the same DB: **pb_new_hire 52 + pb_people 2 = 54 / 54 pass**.
Not re-run in P2: pb_updates / pb_orgchart / pb_pay_scales / pb_approval_config (no file of theirs changed; the create
path keeps P1's old-caller behaviour, T8 still passes).

### 2.3 Browser walk (local server, Claude-in-Chrome, 1440 px; console read)
Walk world: `nh1_base` (P1 seed) + `-i pb_shift_patterns,pb_attendance_policy,pb_leave_setup,pb_workforce_setup` + the P2
seed (scratch `walk_seed_p2.py`, not committed: Office week for Finance, Field week for Indonesia Operation, a late-rule
set, Indonesia annual leave 12 days, 3 holidays, Budi with a login, two buddies with tenure and one too new, clock numbers,
own fields Shuttle route (required), Uniform size (choice), Locker number (Indonesia only), the HR lead with payroll
manager + Lifecycle user). A copy of the P1 walk DB was kept as `nh1_p1`.

| # | Walk | Result |
|---|---|---|
| C1 | step 4 defaults: Field week "Same as the rest of the team", strip Mon–Sat 07:30, 48 h, leave row, "3 days off in the next 12 months · Next: New Year"; change to Office week → strip re-drawn (keyed, `pbnh-land` with 30 ms stagger), 40 h, rail + record panel follow | pass (record panel lag found and fixed, NH27) |
| C2 | clock 0231 → red "Clock number 0231 already belongs to Abdul Rohman…", rail amber "Clock number taken"; 0288 → "is free" | pass |
| C3 | timeline re-flows: laptop chip off → line becomes "Requests: ID card, Email account, System login"; "Not yet" → "Nothing to send: Dewi has no sign-in yet" + "Finish your own details" moves to the fallback owner; buddy chosen → "Buddy: Adika Nadhif · Chosen now…"; first day 7 → 14 Dec → every date moves a week | pass |
| C4 | required Shuttle route empty → rail amber "1 of your own fields is needed", check row "Shuttle route is needed" with Change, Add disabled; Change jumps and focuses the field; typing it turns the rail green | pass |
| C5 | approval route: Rina Kartika sent (with Dewi Lestari), drawer shows every new row (week, late rule, clock, sign-in, checklist, buddy, equipment, letter, category, Shuttle route); approved as the HR lead → New joiners board shows Rina (Step 1 of 3); DB: Field week member from 7 Dec, clock 0301, login linked, 11 tasks dated as previewed, 4 draft equipment requests, Shuttle route on the record, category "Indonesia Permanent Monthly", IDR | pass except the letter: **failed leg "The PDF could not be made right now"** — no wkhtmltopdf on this Mac (NH20); W10 proves the save in test mode |
| C6 | fast lane, clock number given away meanwhile: done card green "Ready: working week Office week, 3 of your own fields, sign-in for …, joining checklist (11 steps), buddy Adika Nadhif, 3 equipment requests" + amber "The clock number could not be set: Clock number 0288 was taken by Rizky Maulana meanwhile. Type another one on the employee record."; Open record / See new joiners / Add another person | pass |
| C7 | no working weeks → "No working weeks are set up yet, so the new person follows the company's usual working hours." (no setup link: the maker is not an attendance officer); no checklist → "No joining checklist is set up" + timeline = first day (+ trial end) only, rail "No checklist"; no own fields → the card is not shown | pass |
| C8 | kept unsent "Siti Rahma" + org chart "fill Accountant" → "Carry on with Siti Rahma?" with "Carry on" focused (Esc = carry on); "Start Accountant" → Finance / Accountant prefilled, name box focused | pass |
| C9 | People › Employees: Rina "Rp11.0M", KPI "Rp29.0M · ₫24.0M · S$5K Monthly wage" | pass |
| C10 | window at its 500 px minimum + studio root 340 px: one column, step strip scrolls sideways (as P1), sign-in modes wrap, chips wrap, timeline 74 px date column; `scrollWidth` = 340 | pass (hint layout fixed for phones after this walk) |
| C11 | console (errors only) over a full keyboard pass (name → Ctrl+Enter → job → wage → week select focused by Tab → buddy combobox type + Enter → own field → Ctrl+Enter twice = sent → Withdraw and change → toast): **no errors**; server log: no error from our code (one pre-existing pb_me_portal warning at login) | pass |

**W: 16/16 groups pass (52 + 2 tests). C: 11/11 pass**, C5 with the local-only PDF caveat.

## 3. Self-review against the handover — deviations

1. **Week leg (§2.3)**: there is no post-gate helper inside `assign_week` (only `_assign_plan` + inline creation), and
   both writers gate on `has_group`, which sudo does not bypass (NH23); `save_pattern` would rewrite the whole pattern.
   The leg creates the single `pb.shift.pattern.member` row both writers create, on **Team A** (lowest sequence, the
   rest of the team's rotation), with sudo; the model's constraint judges. So **W3 has no "module-absent" branch** —
   the leg is the same with or without Workforce setup.
2. **Late rule** is not a leg: `pb_attendance_category` rides on the one employee create (P1 hook) — allowed by §2.3.
3. **Buddy leg** calls `pb.buddy.nomination.open_for(...).choose(...)` (what `buddy_choose` wraps, as Hiring does)
   instead of `pb.onboarding.buddy_choose`, whose lifecycle-manager gate HR approvers do not hold. A refusal is a failed
   leg (the manager is then asked by the checklist), not Hiring's silent direct write.
4. **Employee-number sign-in**: `create_worker_logins` is called only when the applier manages access; otherwise a
   failed leg points to Access › Logins for workers (which prints the slip). In the fast lane step 6 shows the mode
   disabled with that reason. The mode is available only once a clock number is typed (NH24).
5. **Letter** availability also depends on the pay right (NH20): off with the reason in the fast lane, a warning
   line in the approval route. "pay_blocked/missing" from the preview are not checked separately: `contract_document_save`
   refuses with the same sentence when pay is hidden, and a missing field prints blank by design.
6. **Equipment `None`**: "not chosen" stays today's default (laptop only) when step 6 is never opened; opening step 6
   sets the chips to the usual ones, so what is shown is what is asked. Non-laptop requests are linked to the laptop
   task; the task is skipped only when no equipment at all is chosen.
7. **No checklist template** → no case is opened (an empty case would put the person on New joiners with nothing to do).
8. **Timeline owners** use `pb.journey.case._resolve_assignee` on an in-memory case; an owner nobody can be found for is
   shown as "you" / "whoever approves the hire" (the case creator, `_generate_tasks`' fallback). Synthesized rows: First
   day, the check-ins (30/60/90) with the one-tap questions folded in (7/30/60), and "Trial period ends" — "review
   opens" only when `pb_probation.auto_trigger` is on (NH25).
9. **Contract category**: when the screen sends none, the server writes the suggestion (if any) — so old callers / a
   skipped select never fall back to "first row" silently.
10. **One draft-key table**: the client declares P2 keys once (`P2_KEYS`: blank + send); the server list `DRAFT_KEYS`
    stays a second list (another language). P1's keys were not migrated into the table (risk for no gain).
11. **Done card for the approver**: legs are stored in the proposal result and failed legs are posted on the employee;
    the Approvals inbox (another module) was not changed to show them.
12. **"See new joiners"** shows only when the user may open the board (NH30) and the checklist leg succeeded.
13. Extra facade method `find_buddies`; `schedule_options` takes a 4th argument `first_name` (for the "no weeks" sentence).

## 4. Design bar (ledger rule 4), scored honestly

- **Hero moment — 9/10.** The timeline is real (the checklist that will be picked, dated by its own anchors), re-flows on
  first day / manager / sign-in / buddy / chips, rows re-enter with a 30 ms stagger, "Straight away" in teal first, the
  first day as the anchor dot. Missing: a FLIP move animation (rows re-enter rather than slide).
- **Zero dead-ends — 9/10.** Every unavailable choice is shown with its reason and a jump (work email, clock number,
  access right, pay right, refused buddy with the rule's words); no weeks / no checklist / no own fields designed; every
  failed leg names reason + where to fix. Gap: the worker first-password slip after creation (§1.2).
- **Plain language — 9/10.** Screen words only; one owner phrase ("whoever approves the hire") is long.
- **Motion — 8/10.** Strip landing, chip press, timeline stagger, legs rise; all off under reduced motion.
- **Keyboard — 8/10.** Ctrl+Enter through every step, Tab lands in step 4's first control, buddy combobox with arrows /
  Enter / Esc, chips are buttons (Space/Enter), Esc = "Carry on" in the org-chart question.
- **Versus BambooHR / HiBob onboarding** — the dated "who does what" before pressing anything is on par; the welcome link
  (P3) and the first payslip (P4) are the missing halves.

## 5. New gotchas
NH19–NH31 in the ledger: checklist by nationality; letter needs the pay right (and wkhtmltopdf locally); checklist refills a
switched-off trial; leave country field; `has_group` gates ignore sudo; no employee code / slip only at creation; review
trigger off by default; case-open steps dated in UTC; OWL cross-component reactivity; no dialogs in `onWillStart`;
"Paid by" is overnight; New joiners needs a Lifecycle role; `--test-enable` server stops.

## 6. Open questions for the architect / owner
1. **Worker sign-in slip after creation** (§1.2): add "print a new slip" to Access › Set a new password? (owner)
2. **Letter and pay right**: should approving a new hire imply the right to print its contract letter (it already decides
   the pay), or stay payroll-manager only? Today an HR-lead approver without it gets an amber leg.
3. **Equipment requests linked to the laptop task**: fulfilling the phone ticks "Laptop and equipment". Keep, or add a
   generic equipment step to the checklist template (template change = out of P2 scope)?
4. **Lifecycle role for HR**: HR managers cannot open New joiners; should HR managers get the Lifecycle user role?
5. **Checklist by nationality** (NH19): should `_open_case` read the Country of Work instead? (pb_zoho_bridge change)
6. Inbox display of the legs for the approver (another module) — wanted?

## 7. Commits (not pushed)
- `dbaaca7ac` NEWHIRE P2: handover
- `f2b75a39f` pb_people: write a wage in its contract's money (NEWHIRE P2 fix a)
- `fc4211dde` NEWHIRE P2: server side of steps 4 and 6 and the welcome legs
- `a94906293` NEWHIRE P2: steps 4 and 6 on screen, and what follows on step 7
- walk fixes commit and this docs commit (see `git log`)

Local leftovers (not in git): DB `nh1_base` (P2 walk world, approval route ON for DEMO Farms), DB `nh1_p1` (copy before
P2), scratch `walk_seed_p2.py`, `route.py` (switch fast lane / route), `check.py`.
