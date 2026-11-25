# NEWHIRE — ledger (standing rules, architect decisions, gotchas)

Binding on every phase. Read before the phase handover. Add a gotcha (`NHnn`) the moment you hit one; never renumber.

Programme: replace People › Employees "Add employee" (3-step window) with the **New Hire Studio**, a guided 7-step screen.
Design of record: `docs/design/new-hire-studio-poc.html` (open it in a browser and click through — layout, wording, spacing,
colour, motion). Facts (do not re-derive): `NEWHIRE_FACTS_CORE.md`, `NEWHIRE_FACTS_ONBOARD.md`.
Owner approved the design and the phased build on 2026-11-25.

## 0. Standing rules

1. **Worktree only**: `/Users/adity/Documents/GitHub/gitlocal-worktrees/newhire` (branch `newhire`). Never edit or stage from
   `/Users/adity/Documents/GitHub/gitlocal`. Other sessions (Codex, other Claude sessions) ship People modules — keep edits to
   modules we do not own to the smallest pure refactor the handover names, and report every such file.
2. **White-label**: the word "Odoo" never appears in anything a user can see or receive (labels, tooltips, toasts, errors,
   menu/action names, field `string=`/`help=`, emails, `.po` msgstr, manifest `name`/`summary`). Technical identifiers
   (`from odoo import`, model/xml ids, comments, these docs) keep the real name. Use "Payobook" or a neutral word.
3. **Plain words on screen**: use the words in the POC ("pay scheme", "Country of work", "trial period", "working week",
   "take-home"). No model names, codes or internal vocabulary in any user-visible string. One sentence per `_t()`/`_()`.
4. **Design bar (owner's words, verbatim): "extreme WOW, intuitive, out-of-this-world experience, best in class."** Every
   phase must state and satisfy: a **hero moment** (named in the handover); **zero dead-ends** (every state — empty, loading,
   error, partial, huge — is designed; every failure names its reason and its next step); **plain language over code
   vocabulary**; **motion with purpose** (enter/exit, progress, state change — never decorative jitter); **keyboard
   ergonomics** (Tab order, Enter to continue, Esc closes drawers); measured against the best consumer/SaaS tool in the
   category, not against the stock framework. Lucide icons via the import kit, never emoji. The phase report scores itself
   against this bar.
5. **No parallel engines**: never re-implement scheme resolution, the fill-in, pay totals, trial-period maths or approval.
   Call the existing code; where the handover asks for a factor-out, the old caller must call the new function too.
6. **Backend needs a screen twin**: anything the build can do server-side must be doable by the user on screen.
7. **Tests**: `@tagged('post_install', '-at_install', 'newhire')`, `TransactionCase`, users via `new_test_user`. A static
   gate file (clone `pb_workforce_setup/tests/test_static.py`): no "Odoo" in visible text, every icon exists, no emoji.
   Local run recipe: FACTS_CORE §I (wfsetup recipe: private conf in the scratch dir, DB copy of `upd_p6_t_tpl` + one `-u all`).
   Also run the suites of every module you touched and the existing tests listed in FACTS_CORE §A.5.
8. **Browser proof is mandatory** before calling a screen done: local server, Chrome MCP walk, console read
   (errors only), at 1440 and 400 px wide. A hidden Chrome tab renders blank — check `document.visibilityState` first.
9. **Translations**: every string translatable from day one (`_t("literal")` with the exact import
   `import { _t } from "@web/core/l10n/translation";`, `_()` in Python). `.po` files arrive in P5 (vi_VN, id_ID).
10. **Commits**: one feature-scoped commit per coherent piece, explicit paths only (never `git add .`/`-A`), message =
    problem → fix → key decisions, ending with `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`. The repo is
    PUBLIC: no passwords, keys, client names or client data in any commit. Builders commit; the main loop pushes.
11. **No deploy and no server writes unless the phase handover says so.** Never touch any database named `abm`.
12. **Lessons follow screens**: FACTS_CORE §A.5 lists the Learn anchors/replicas that describe the old window. They are
    updated in P5 with the takeover going live; a phase that changes what a lesson describes says so in its report.
13. **Usage limit**: on a 429 / "session limit", finish the current step, make one WIP commit with explicit paths, write a
    "Where I stopped" section in the phase report, end with PAUSED.

## 1. Architect decisions (made — do not reopen without a report)

- **D1 Module**: new module `pb_new_hire`, CSS prefix `pbnh-` (grep first; if taken use `pbnj-` and record it). Client
  action tag `pb_new_hire_studio`, xmlid `pb_new_hire.action_new_hire_studio`, name "Add employee".
- **D2 One create path, same approval**: the studio builds ONE values dict and proposes through the existing
  `pb.newhire.proposal` (kind `employee`). On approval the existing `_apply_employee` replays
  `pb.people.onboard.wizard.create_employee(values)`; `pb_new_hire` extends `create_employee` / `create_contract` by
  inheritance so the NEW optional keys are honoured. Signatures unchanged; every old caller (Updates joiners sheet, org chart,
  pay scales) keeps working with the old keys.
- **D3 Team decides the pay scheme; the country is checked against it.** New pure function
  `pb.scheme.map.resolve_for_team(...)` (factor-out, FACTS_CORE §C.4). No per-person "use a different scheme" picker (no seam
  exists); when the team's scheme and the chosen country disagree the screen says so and names the fix.
- **D4 Country of work is written where it matters**: employee `payroll_country`, contract `payroll_country` (currency),
  and the trial period is computed from the CHOSEN country (`policy_for_country`), not from the address ladder. Nationality
  (`country_id`) is its own optional field that defaults to the country of work.
- **D5 Trial end** is written on the employee (`pb_set_trial_end`, the field the trial-period board reads), with the
  product's own maths (`add_months(start, months)`, no minus one day). HR can switch it off for this person.
- **D6 Usual answers** are previewed from the scheme (`_pb_usual_answer_rules`, factor-out) and the person's choices are
  written as contract lines so the automatic fill-in leaves them alone.
- **D7 After sending**: the payload is frozen. The screen offers "Withdraw and change" (engine cancel + back to the form
  with everything still filled in), never "edit in place".
- **D8 Welcome link = the standard sign-up invitation** landing on the existing My Payobook pages (FACTS_ONBOARD §B). The
  person sets a password once. No token link ever collects bank details, ID numbers or papers.
- **D9 First-payslip example** = savepoint + rollback over real records (FACTS_CORE §F), built in P4 by the architect or
  under tight rails. Until then the panel says what will appear there.
- **D10 Install scope while building**: `pb_new_hire` is installed on `payobook` only until the closeout phase; the takeover
  of the old door lives inside `pb_new_hire`, so databases without it keep the old window.

## 2. Where the POC is not true to the product (build the truth, keep the feel)

| POC says | Truth | Build |
|---|---|---|
| Welcome link "with no password" | Signed invitation, password set once (D8) | wording changed in P3 |
| "Use a different scheme" picker | no per-person override exists (D3) | show "Paid by" read-only + mismatch help |
| Trial ends one day before N months | product uses same day N months later (D5) | product maths |
| "Fixed-term contracts in Indonesia cannot have one" | no such rule exists | a per-person switch instead |
| Holidays "follow the country of work" | one holiday list per company calendar | say "your company's holiday list" |
| "Gets the next free clock number, 0232" | no such feature | a plain clock-number box (P2) |
| "Change anything before it is approved" | payload frozen (D7) | Withdraw and change |
| Numbers typed in Hiring "come across" | Hiring holds files only | P4: files come across; numbers are asked |
| First payslip always prorated | no engine-wide joiner proration | P4: show what the scheme really does, say so |

## 3. Gotchas

- **NH1** `hr.employee.country_id` is NATIONALITY. Country of work is `payroll_country` (Selection; contract accepts only
  VN/ID/IN/SG/MY — writing TH/KH/PH on a contract raises). FACTS_CORE §C.1.
- **NH2** `create_contract` always passes `resource_calendar_id`, overriding the time-zone calendar the employee create
  cloned from `payroll_country`. FACTS_CORE §C.1.
- **NH3** Contract `wage` is Monetary and rounds to the contract currency at write time; the currency follows the contract's
  `payroll_country`. Set the country before (or re-write the wage after) or a SGD wage is rounded to VND decimals. §C.3.
- **NH4** The scheme map reads departments with raw SQL: `flush_all()` after writes in the same transaction. §C.4.
- **NH5** Two trial-end fields; the board reads the employee/version one. §D.
- **NH6** HR officers have read-only access to `hr.contract.advantage`, are refused by pay bands (`AccessError`) and by
  `assign_week`. Write behind `require_hr` with sudo; catch and hide for reads. §E, §G, §H.
- **NH7** `pb_tenancy` refuses `hr.employee.create` at the seat limit — including inside a savepoint preview. §F.
- **NH8** The approval payload is stored as JSON and replayed later by ANOTHER user (the approver): every value must be
  JSON-plain (ids, strings, numbers), never recordsets or dates objects; re-validate on replay (a team or job may be gone).
- **NH9** No approval route for the company → `propose` raises a UserError. Design that state.
- **NH10** Sibling-studio gotchas from WFSETUP apply as written: WS1, WS2, WS4, WS5, WS10, WS11, WS14, WS17, WS18, WS22,
  WS24, WS28, WS39, WS40, WS42 (FACTS_CORE §B.6).
- **NH11** (P1) An OWL template cannot call JS globals: `String(x)`, `Number(x)`, `Math.*` compile to `ctx.String` and crash the
  step on render ("ctx.String is not a function"). Put the comparison in a component method (`isJob(j)`).
- **NH12** (P1) Python: `0 in (None, '', False)` is **True** (`0 == False`). A "turned off" usual answer (amount 0) was dropped
  by a membership test. Test emptiness with identity (`value is None or value is False or value == ''`).
- **NH13** (P1) `hr.department.complete_name` is not stored: `search(order='complete_name')` raises. Order by name, sort in Python.
- **NH14** (P1) The approval engine calls `record._approval_withdraw` only if the model has it; the proposal mixin does not, so a
  withdrawn `pb.newhire.proposal` stayed "Waiting for approval" forever. `pb_new_hire` adds the hook for studio payloads only
  (state → `draft`).
- **NH15** (P1) The approval request's money is `_approval_context()['currency_id']` (company currency by default): a
  Singapore hire showed "5,200.50 VND" in the inbox. `pb_new_hire` overrides `_approval_context` for studio payloads with the
  contract currency; the mixin and the proposal's own currency field are unchanged.
- **NH16** (P1) `upd_p6_t_tpl` (the wfsetup recipe DB) has no active scheme, one team, a US/USD company and lacks `pb_pay_scales`
  and `pb_contract_rules`. Install those two and seed a walk world (script in the P1 report, §2.3) before any browser walk.
- **NH17** (P1) Chrome DevTools MCP can be held by another session ("browser is already running for … chrome-profile"). Use the
  Claude-in-Chrome tools instead. Its window cannot go below ~578 px: prove 400 px by narrowing `.pbnh` to 340 px (400 minus
  the 60 px sidebar) — the viewport is already under the 600 px breakpoint. Type-ahead on a native `<select>` cannot be driven
  on macOS (keys go to the native popup): use `form_input` for selects in a keyboard walk.
- **NH18** (P1) Screens we do not own still read the company currency: People › Employees shows a studio hire's IDR wage as
  "₫9.0M", and the contract panel's "Employee category" is the first `hr.contract.type` ("Vietnam Permanent Monthly") for an
  Indonesian hire (`create_contract` never sets `type_id`, FACTS §A.3). Not fixed in P1 — open questions in the P1 report.
- **NH19** (P2) `pb.zoho.pipeline._open_case` picks the joining checklist by the employee's NATIONALITY (`country_id`), not
  the Country of Work. The studio previews with the same country (nationality, defaulting to the country of work), so a
  hire whose nationality differs gets that country's checklist — say so if a country-specific checklist ever surprises.
- **NH20** (P2) A contract letter prints the pay, and `pb_doc_contracts` only lets a **payroll manager** make it
  (`pb.contracts._cd_unmask_wage`, checked in `pb_doc_contracts/models/doc_studio.py:_pbdc_pay`, which overrides the
  pb_doc_studio branch). An HR manager without it gets "This contract shows pay…". Step 6 switches the letter off up
  front in the fast lane and warns in the approval route. Locally there is no wkhtmltopdf, so a real save fails with
  "The PDF could not be made right now" outside test mode (tests render HTML).
- **NH21** (P2) Opening a joining checklist fills an EMPTY trial end from the policy (`pb_probation` `_set_trial_end`),
  so a trial period HR switched off came back. `pb_new_hire` overrides `pb.journey.case._set_trial_end` behind the
  context key `pb_nh_no_trial_employee_id` (that one employee only).
- **NH22** (P2) `hr.leave.type.country_id` follows the company; the leave's country is `pb_policy_country_id`
  (`pb.timeoff._type_country` reads that first). Seed leave types with `pb_policy_country_id`.
- **NH23** (P2) `assign_week` / `save_pattern`, `create_worker_logins`, `pb.onboarding.buddy_choose` and the New joiners
  board all gate on `user.has_group(...)`, which **sudo does not bypass**. The legs write the product's own row shapes
  with sudo (week member, buddy nomination as Hiring's `_hand_over_buddy` does) or ask for the right
  (`create_worker_logins` only when the applier manages access; otherwise a failed leg pointing at Access).
- **NH24** (P2) No employee code is made at creation. `_pb_sign_in_code` is barcode → clock number → identification
  number, so the studio's "Employee number" sign-in is the clock number typed in step 4. A worker's first-password slip
  can only be printed at creation (Access › Logins for workers); afterwards only "Set a new password" exists.
- **NH25** (P2) `pb_probation.auto_trigger` defaults to OFF: "the trial review opens" is only true when it is on. The
  timeline shows "Trial period ends" (HR opens the review) otherwise.
- **NH26** (P2) Steps due "when the journey opens" are dated with `fields.Date.today()` (server, UTC): in Sydney the
  buddy step of a checklist opened before 11:00 is dated yesterday and shows "1 overdue" on New joiners. Product
  behaviour, not ours; the preview uses the same date so they match (W9).
- **NH27** (P2) OWL: a child component that reads state through ANOTHER component's reactive (`api.someGetter` →
  `studio.nh`) does not re-render when it changes. Shared answers are plain functions taking the caller's own `nh`
  (`weekNameOf`, `siteNameOf`, `ownMissingOf` in studio_util.js).
- **NH28** (P2) OWL: never await a dialog inside `onWillStart` — the component is not mounted, so the dialog never shows
  and the screen hangs. Decide in `load()`, ask in `onMounted` (the org-chart "Carry on?" question).
- **NH29** (P2) "Paid by" (`pb_paid_by_id`) is refreshed overnight and empty for a person added today; screens that
  need the money of a new hire must read the contract (`pb_people._pay_symbol` now does).
- **NH30** (P2) The New joiners board needs a Lifecycle role; HR managers without it see a lock card. The done card
  shows "See new joiners" only when `pb.onboarding._can_read()`. Lifecycle users also see only some cases (record
  rules), so a hire added by someone else may not be on their board.
- **NH31** (P2) A server started with `--test-enable` (even with no tests) shuts down after "post tests". Don't use it
  to get HTML reports on a walk server.
- **NH32** (P3a) The contract letter's pay gate is NOT opened by sudo: `pb_doc_contracts._pbdc_pay` asks
  `pb.contracts._cd_unmask_wage()` (`has_group`, NH23) and then reads the wage with `env(su=False)`. The studio's letter leg
  opens it with the context key `pb_nh_letter_contract_id`, read by a `_cd_unmask_wage` override in `pb_new_hire` — for that
  one call only.
- **NH33** (P3a) SCSS: a modifier class with the same specificity loses to a base rule written LATER in the file
  (`.pbnh-scrim` is defined after the step 5 block) — the drawer kept the dialog's 16 px padding. Use
  `.pbnh-scrim.pbnh-scrim--side`.
- **NH34** (P3a) Focus after an OWL state change: `requestAnimationFrame` can run before OWL patches the DOM (the opened form
  was still `inert`, focus stayed on the button). Wait ~60 ms (`StepDocs.later`) or focus in `onPatched`.
- **NH35** (P3a) Unstored computed answers (`hr.employee.pb_bank_on_record`) stay cached inside one transaction after the
  fields they read change; `pb.new.hire.ask.refresh()` invalidates the employee before reading.
- **NH36** (P3a) `pb.people.vault_upload_batch` checks the base64 length (14 MB) before the decoded size: a 10.0–10.5 MB file
  gets "Choose a non-empty file up to 10 MB.", not "Each file must be 10 MB or smaller." The studio mirrors that order.
- **NH37** (P3a) `/my/tax` offers tax kinds by the PAY SCHEME's country (`_pbtx_country`), not the Country of Work: when the
  team's scheme is of another country (D3 mismatch), a tax ask url may be refused on that page.
- **NH38** (P3a) A company row of `pb.new.hire.paper` without its own label shows the usual row's label
  (`display_label`), else the category name. Vault category names are English product words ("ID Document",
  "Degree / Certificate"): rows that print them have no seeded label (SG/VN/IN/MY certificate).
- **NH39** (P3a) Locally, `odoo-bin --test-enable --stop-after-init` hangs after "post-tests" ("Hit CTRL-C again"); and
  post_install tests run only for the modules being `-u`'d (a `-u pb_new_hire` run with `/pb_people_advanced` tags ran none
  of its tests). Use the scratch `runt.sh` pattern: `-u` every module whose tests you want, kill after "post-tests".
- **NH40** (P3a) Files of a waiting hire are private `ir.attachment` rows of its proposal listed in
  `pb.newhire.proposal.pb_nh_files` (never in the payload); the fast lane applies inside `propose`, so `send` passes them by
  the context key `pb_nh_files` for that one call. `_approval_withdraw/_reject/_return` and the apply drop them.
- **NH41** (P3b) `pb.me.home._pbme_needs_extra` is ONE chain inside one savepoint: a sibling that raises (several read the
  session's own employee and raise for anyone else, e.g. `pb_me_project_time`, `pb_ess_workforce`) loses every row put
  AFTER it. Put your row first (before `super()`), guarded; a row already `put` survives because `put` fills the
  caller's dict. Test the home as the person (`with_user(emp.user_id)`), never as admin.
- **NH42** (P3b) `mail.template.send_mail` copies `body_html` into the `mail.message` of the `mail.mail` (`_inherits`) and,
  with the template's model/res_id, that message shows on the record's chatter (only `user_notification` is hidden). A
  mail that carries a sign-up link is sent with `email_values={'model': False, 'res_id': False, 'auto_delete': True}`:
  on nobody's chatter, deleted once sent. (The bridge's own credentials template does leave its link on the chatter.)
- **NH43** (P3b) The signup link is stateless (signed payload): every link minted stays valid until its own expiry
  (`auth_signup.signup.validity.hours`, 144 h by default) or the first sign-in. "Send again" / "Copy" do not revoke
  older links. Setting the password through the link also makes the stock `auth_signup` send its own
  "account created" email (force-sent) — a stock message on every invitation, not ours.
- **NH44** (P3b) Locally the asset bundle is not rebuilt when a file changes: restart with the `/web/assets/%`
  attachments deleted (scratch `restart4.sh`) before judging a JS/SCSS change in the browser.
- **NH45** (P3b) Narrow-width proof in Claude-in-Chrome: `resize_window` may not apply (window stays 1920 CSS px), the
  backend refuses to load in an iframe and popups are blocked. `/my` pages CAN be framed (390 px iframe = a real
  phone viewport). For the studio, set `.pbnh` to 340 px AND copy the stylesheet's own `max-width` media rules into a
  plain `<style>` (CSSOM read) so the breakpoints apply; measure `scrollWidth`.
- **NH46** (P3b) `navigator.clipboard.writeText` can stay pending forever in an automation tab without focus (no
  reject): race it with a timeout and fall back to a select-the-text field (`studio_util.copyText`).
- **NH47** (P3b) The New joiners drawer (`.obb-scrim`, z-index 1400) sits above the notification layer: a toast
  raised from inside the drawer is hidden. Say the answer inside the drawer too. Its `pbim-badge` capitalises every
  word (`text-transform`); sentence-case badges need `text-transform: none`.
- **NH48** (P3b) An activity assigned to another user (the HR note 3 days before day one) makes the stock
  "<summary> assigned to you" notification email — product behaviour on every activity.
- **NH49** (P3b) Tests run on whatever database the runner is given (often a walk DB): never assume there is no active
  mail server (switch them ALL off when testing "no email"), no other joiner with open asks (judge one person's mail /
  activity, not a job's totals), no other queued mail (scan only rows made by the test) or no published privacy notice
  (the `/my` gate redirects every page test; patch `pb.privacy.consent._pb_pending` except in the test of the gate).
- **NH50** (P4) `cr.savepoint()` (flush=True) RUNS the caller's pending precommit hooks on entry (mail tracking of earlier
  writes) and its rollback calls `cr.clear()`, dropping every precommit hook registered so far. Postcommit hooks survive.
  In a test that counts rows around a savepoint, `self.env.cr.flush()` first, or the fixtures' tracking "appears".
- **NH51** (P4) Some side effects are NOT undone by a savepoint rollback: creating an employee whose manager signs in makes
  the stock `hr_holidays` create write `res.groups`, which signals `registry.clear_cache('stable')` to every worker. The
  payslip example leaves the manager out (it changes nothing on a payslip). Assert `registry.cache_invalidated` is empty.
- **NH52** (P4) The formula kernel swallows every formula exception and answers 0.0 (`formula_program._evaluate`), like the
  real payslip; `errors=` is almost never filled. A broken formula shows as a 0 line, not as an error.
- **NH53** (P4) Inside one transaction `write_date` does not move (NOW() is the transaction's time): a cache keyed on rule
  write dates misses a change made in the same transaction (tests). Hash the rules' content too.
- **NH54** (P4) `pg_advisory_xact_lock` (the calendar copy in `_pb_in_work_timezone`) is held to the END of the transaction,
  not the savepoint: two previews in one company serialise. Try the lock first (`pg_try_advisory_xact_lock`) and answer busy.
- **NH55** (P4) One screen can fire two examples back to back (bring-across, then the contract category picked by itself):
  the second meets the first's lock. The client runs ONE example request at a time and re-sends when the draft moved on.
- **NH56** (P4) The vault's `ID Document` category requires an expiry date; Hiring never asks for one. The hiring leg holds
  that paper (amber, "needs a valid-until date") instead of inventing a date; the file stays on the offer.
- **NH57** (P4) HR approvers cannot create `pb.bank.change.request` through `pb.bank.ocr.create_from_upload`. The hiring leg
  creates it AS the hire's sender with sudo (FS-16's `_pb_hold_new_hire` precedent: the creator counts as a preparer, so
  the second approval is truly someone else's).
- **NH58** (P4) Hiring's `action_confirm_joined` would make a work-email login and open a checklist whatever the studio
  chose; its legs swallow every failure (`hiring_common.leg`, warning log only) — check results on the records, not on a
  return value.
- **NH59** (P4) Every "Confirm they joined" in Hiring funnels into `PbHiringBoard.p6OpenConfirm`; patch that one method.
  `user.hasGroup` is async: read it in `onWillStart` of the patched `setup`.
- **NH60** (P4) Locally `pb.hiring.offer.action_send_to_candidate` fails without wkhtmltopdf (the letter PDF). Walk seeds
  write `state='signed'`, `join_status='pending'` directly (scratch `seed_hiring_p4.py`); tests try the real flow first.

- **NH61** (P5a) Chrome's own page translation rewrites a Vietnamese / Indonesian screen back into English in the automation
  browser (mixed lines like "AI LÀM GÌ" give it away; `<font>` nodes appear). Right after every reload set
  `document.documentElement.setAttribute('translate','no')` and check `document.querySelectorAll('font').length === 0`
  before reading any wording.
- **NH62** (P5a) After a `.po` change the browser keeps the old screen wording: web translations are cached in the IndexedDB
  database `localization` (and per server process). Restart the server AND `indexedDB.deleteDatabase('localization')`
  before judging a translation fix; the server's `/web/webclient/translations` answer is the truth.
- **NH63** (P5a) On the walk DB a shell write of `res.users.lang` did not show in the session; the top-bar language switch
  (EN / ID / VI) is what changes the user's language — use it in walks. Learn has its own content switch (Tiếng Việt).
- **NH64** (P5a) `with_user(u)` does not put the user's language in the context: `_()` then guesses it from the uid while
  translated FIELDS read the context's (none = English), so a test mixes both. Call like the browser does:
  `.with_user(u).with_context(lang=u.lang)`.
- **NH65** (P5a) A test class attribute named `id` (e.g. `cls.id = {...}`) shadows `TestCase.id()`: the runner dies in
  `result.stopTest` with "'dict' object is not callable" and reports 0 tests. Never name a fixture `id`.
- **NH66** (P5a) The local disk filled up (466 GB, ~0 free) during DB copies: every tool stops (the shell cannot create its
  output file, Write cannot write, Postgres refuses connections). Each walk/test DB copy costs ~0.5 GB (DB + filestore);
  keep ≥ 3 GB free before parallel suites, drop superseded copies, and use a slim "before" snapshot (only the modules a
  phase changes, placed FIRST in `addons_path`) instead of a full `git archive` (1.1 GB).
- **NH67** (P5a) The recipe base `upd_p6_t_tpl` has an inactive admin and inconsistent modules (`pb_govt_reports` not
  loaded): a server on a copy times out (`virtual real time limit`). For "a database without pb_new_hire" walks, uninstall
  the module on a copy of `nh3_base` (`button_immediate_uninstall`) instead.
- **NH68** (P5a) `mail.template.body_html` exports as ONE msgid (the whole HTML, `translate=True`), not one per text node:
  its translation must keep every tag, attribute and `t-out` byte-identical (the P5a checker compares the tag lists).
- **NH69** (P5a) The Learn generator's guard rule reads a click step's KEY, ANCHOR and English TITLE: a `guard: false`
  step whose title has a write verb ("Open Add employee") is refused ("…whose name says it add"). Title it by what the
  learner does ("Find where new people start").
- **NH70** (P5a) Learn content is English + Vietnamese only (bilingual leaves). An Indonesian user sees English lesson text
  with other modules' Indonesian words mixed in through the global screen translation table (a pre-existing odd id_ID
  msgstr shows in the "Your turn" box). Walk lessons in en and vi.
- **NH71** (P5a) An upgrade loads a `.po`'s model terms into `noupdate` rows when that language key is missing (the
  non-overwrite merge `noupdate || update || stored`): the shipped paper labels got vi/id on a plain `-u`; a label someone
  already wrote in that language is never overwritten. Proven on the walk DB (`label->>'vi_VN'`).
- **NH72** (P5a) The website layout titles a `/my` page with the TEMPLATE's own name ("Welcome (new joiner)") unless the
  controller passes `additional_title` — and template names are never translated. Pass a `_()` title.
