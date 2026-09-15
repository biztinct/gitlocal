# RIZE Wave 2 — handover to the next session

**What this is.** The RIZE programme (2026-08-31 → 09-02) built the ten coloured
tabs of `RIZE/HRMS Proposal - Must Have.xlsx` into Payobook as twelve modules.
Five tabs were left out on purpose — they were uncoloured, which the owner had
ruled "Zoho keeps these". On 2026-09-15 the owner reversed that: **Hiring &
Recruitment, Goal Setting, HR Comm, Leave & Attendance and LnD are now to be
built in Payobook, the same way and to the same design as the first wave.**

This document is the bridge. Part A is what the first wave learned, distilled
so it need not be re-learned. Part B is what has CHANGED in the product since,
which the old notes do not know. Part C is the verified map of what already
exists for each of the five tabs and the build decision for each. Part D is
the phase plan. Part E is the prompts to paste into the new session.

Read order for the new session: this file → `RIZE_LEDGER.md` (sections 1–7,
then R1–R130) → `RIZE_CLOSEOUT.md` → `APPROVAL_MATRIX_CLOSEOUT.md` §1.

---

## Part A — What the first wave learned (distilled from R1–R130)

These are the patterns, not the individual gotchas. The ledger has the
gotchas; append new ones there as **R131+** — one ledger for the whole RIZE
stream, never a second file.

### A1. The shape of a RIZE module (all twelve are identical in skeleton)

- **One OWL client-action cockpit per surface** ("board"): an `AbstractModel`
  facade (`pb.<thing>`) whose every RPC is wrapped in `_safe()`, scoped to
  `env.companies`, row-capped, returning ids not records (R43). The JS is a
  `pbim`-kit component; icons come from the single `ic()` registry in
  `pb_import_kit` — the set is CLOSED, an unknown name renders a plain circle
  with no error (R-icons). Rail icons are the kebab `ICONS` map in
  `pb_sidebar`, also closed and test-enforced.
- **Records open natively, skinned.** Drill-downs from a board go to ordinary
  form views under the `vu-form` engine (Option B — skin, don't rebuild). Two
  rules a form MUST carry: every hand-built `act_window` dict includes
  `'views': [[False, 'form']]` (R125 — without it the client throws and the
  user sees the generic error dialog), and every `nolabel="1"` field directly
  inside a `<group>` carries `colspan="2"` (R128 — or it renders one label
  wide).
- **Lenses, not menus.** A module joins a hub through a soft registry:
  `LIFECYCLE_LENSES`, `PEOPLE_LENSES`, `PAY_LENSES`, `HOME_LENSES`,
  `INSIGHTS_LENSES`, `SETTINGS_CATEGORIES`. The registry is the seam; a
  module that is not installed simply contributes nothing. Registration is
  test-enforced per the ledger's "Platform contract" section.
- **⌘K rows in a numbered block per module** (`hub_palette_entries.js`).
- **Portal pages for the employee** under `/my/<thing>` (pb_me_portal
  route/security contract), token pages for outsiders (`/journey/t|f/<token>`
  pattern), never a backend login for a candidate or a peer reviewer.
- **Letters through the letter engine** (`pb.letter.template` →
  `pb.hr.letter` → PDF in the vault), never a bespoke QWeb report — and never
  `sudo()` on a report (R89 leaks companies).
- **Automation as registered handler keys**, e.g.
  `pb.journey.task._automation_handlers()` returns
  `{'credentials': '_auto_credentials', 'day1_ics': ..., }` — a later module
  ADDS a key; nobody edits a Selection (pb_onboarding/models/journey_ext.py:70).
- **Hooks never raise** (`_after_onboard`, `_after_offboard`, every cron): log
  and continue. Reminders are idempotent (re-run = no second mail, R30).
- **Config switches are `ir.config_parameter` keys** with a documented
  default, and the mail-sending ones ship OFF where a real address is needed
  (finance, HR alert). The closeout lists every switch; a new module adds its
  own to that table.

### A2. What the money rules taught

- Anything that reaches a payslip goes through ONE door: `pb.oneoff.feed`
  (`preview_for_run` → `queue_for_run` → `mark_paid_for_run`), gated on the
  target run being draft/officer AND its scheme carrying an `INCENTV` input
  component (R72). Awards flip to Paid on final approval
  (`action_payslip_run_level2_done`, R70). Nothing else writes pay lines.
- Budget canon is `wfp.budget.actual` (D2). Do not create a second budget
  table for a requisition's "budget status" — read that one.
- `hr.version` holds job_title/department in Odoo 19; write employees ONLY
  through the ORM (R14). Reading `hr.employee` drags ~40 group-gated fields —
  read narrow (R56).

### A3. What deploying taught

- The ritual is in the ledger ("Deploy ritual") and it is exact: clean
  staging dir → scoped `--delete` per module (NEVER into `addons/` itself) →
  detached `systemd-run` install → poll `.done` → `EXIT=` line may be missing
  (R15) — grep the real log → asset purge for any JS/SCSS
  (`DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'`) → restart →
  verify in Chrome. A `-u` re-validates every dependent module's XML; a
  `<group string=…>` in a search view (R129) or an Odoo-16 `<report>` tag
  anywhere downstream fails the whole batch with the real error only in
  `/var/log/odoo/odoo-server.log`.
- Python-only change = rsync + restart, no `-u`. View/data/security change =
  `-u`. Post-init hooks run on INSTALL only — a route, a cron `nextcall`, a
  seed for an existing DB needs a MIGRATION too (AM70, and the
  `post-resign_approval.py` pattern).
- A restart clears server-side caches that a SQL data fix does not
  (R124: the generated user-form arch kept the old privilege names until
  restart).
- "Files deployed + restarted" is not verification. Re-run the exact probe
  that proved the bug. The generic error dialog hides the cause: attach an
  `unhandledrejection` listener BEFORE clicking to read it (R125).

### A4. What testing on a live demo box taught

- Test actors are `rize.p<phase>.<role>@example.com`, company 5 "Payobook
  Vietnam JSC", passwords `RizeP<n>!2026`, all documented in the closeout.
  Data created during a phase is NOT cleaned up (D9 — payobook is a demo DB),
  but is RENAMED so it reads as demo, never deleted (TIDY rule 15).
- Group memberships granted to a test user for a test are REVERTED to the
  exact pre-test set, verified against a snapshot (R123). Never test with the
  owner's login.
- Every phase ends with light + dark screenshots of every new screen (R20:
  dark mode on NATIVE list views is a known product-wide gap — not yours to
  fix, note it and move on).
- Mail sends within the second (R47) — assert on `mail.mail` rows, not on a
  delay.

### A5. What working autonomously taught

- Sleep/watchdog interruptions kill agents mid-run. Commit every finished
  slice (commit-per-feature); an agent resumed via `SendMessage` recovers from
  `git status`/`git log`/the server, never from memory. A `TaskStop`'d agent
  cannot be resumed — spawn a completion agent that VERIFIES first.
- Each phase report feeds the next handover: palette block used, registry
  names, API signatures, new R-numbers, test accounts created. The ledger's
  "Phase plan & status" table is updated by the phase, not by the reviewer.
- Owner rulings get a D-number and go in the ledger the moment they are
  given. Pending decisions go in the closeout, not in a chat message.

### A6. Standing rules (verbatim into every phase prompt)

- **White-label:** the word "Odoo" never appears in anything a user can see —
  labels, help, placeholders, empty states, errors, menus, reports, emails,
  `.po` msgstr. Technical identifiers untouched. `biz_debrand`,
  `biz_deroute` (`/bizapp`), `biz_mail_debrand` carry the global seams.
- **Plain English on screen:** words people say out loud ("Who deserves it",
  "Give this to somebody"), never model vocabulary. The description sentence
  is the hero of every catalogue row (R33).
- **Design mandate:** extreme-WOW, intuitive, best-in-class bar — hero
  moment, zero dead ends, purposeful motion, bulk ergonomics; Lucide not
  emoji; Chrome-MCP validated in light AND dark. No gradients, no emoji,
  locked palette (`payobook-design-system`).
- **One addons directory** (`/odoo/odoo-server/addons`), every DB upgraded,
  version diff not a hand list (AM145).

---

## Part B — What changed since the first wave (the old notes do not know this)

| Fact | Then (2026-09-02) | Now (2026-09-15) | Consequence |
|---|---|---|---|
| Sign-offs | each module rolled its own `biz_approval_chain` | **One engine (`biz_approval_workflow`) under one Approval Matrix (`pb_approval_config`)** — 42 published routes per company, one inbox on Home; every RIZE module was retrofitted (`pb_rnr/models/nomination_approval.py` is the newest and the one to clone) | **Every new sign-off is an adapter + a seeded route + a migration.** No new chain, no new approval UI. See B1. |
| ⌘K palette | next free block 3300 | blocks up to **3450** are taken (`pb_approval_config`, `pb_pay`, `pb_workseg`) | **Next free block is 3500.** |
| Validator login | `igc1.validator` / `RizeP0!2026` (uid 2065) | **uid 2065 is deactivated** | New session has no test admin. See B2. |
| Admin password | `Rize#Payobook2026` | **changed by the owner, unknown** | See B2. |
| Databases | `payobook` only | `payobook` (master, 5 companies), `payobook_template`, `abm` (retired), **`rize` (customer tenant, 98 pb modules incl. all RIZE)**, `p9clone`, `rztest` | Owner ruling: **build and test on `payobook`**; roll-out to `rize` is the tenant-sync rule, a separate step. |
| Unpushed commits | 56 | **1,519** on `19.1` vs `origin/19.1` | Not yours; just do not be surprised. Push is an owner decision. |
| E-Learning | not installed | **`website_slides` installed** (+ `website`, `website_hr_recruitment`, `gamification`, `hr_skills`, `hr_recruitment_skills`) | See C5. |
| Recruitment | ruled ABSENT | **`hr_recruitment` installed** (jobs, applicants, stages, sources, talent pool, job platforms, calendar) | See C1. |
| Surveys | — | **`survey`, `website_slides_survey`, `hr_recruitment_survey` NOT installed** | Question bank / scored tests / certification need `survey`. Owner-authorised install in Phase E1. |
| Home | — | `pb_home_hub` "the queue that needs you" + `pb_today` triage board + the approval inbox | "HR daily task list" in the Goals sheet = Home. Tasks surface there via `HOME_LENSES` or as approval requests — there is no separate task-list model to build. |

### B1. The approval adapter recipe (verified in `pb_rnr/models/nomination_approval.py`)

```python
from odoo.addons.biz_approval_workflow.models.seed_helper import (
    manager_step, register_chain, role_step, route)
register_chain(<PROCESS_KEY>, model='pb.<thing>', ...)          # catalogue row
class PbThingApproval(models.Model):
    _inherit = 'pb.<thing>'
    _approval_process_key = <PROCESS_KEY>
    def _chain_title(self): ...          # what the approver sees
    def _chain_facts(self): ...          # the facts a route is chosen on
    def _chain_fact_specs(self): ...     # unit = a real unit, never a type (AM25)
    def _chain_revision_values(self): ...# what is frozen — must not include write_date (AM32)
    def _approval_detail(self, request): # optional drawer shape (AM49)
    def _approval_seed_default(self, company):
        return route(manager_step(_('Their manager')), role_step('hr_lead', _('HR lead')))
```
Plus `migrations/<ver>/post-<thing>_approval.py` calling the module's
`seed_all(env)` (clone `pb_offboarding/migrations/19.0.1.1.0/post-resign_approval.py`).
Rules that bit: facts a route is chosen ON are read under `sudo()` — the
maker may not be allowed to open the scheme (AM40); "their manager" for a
person without a login reads `employee_id.parent_id.user_id` directly (AM50);
a catalogue row must name a STORED model that can hold the request (AM45);
the adapter module depends on `biz_approval_workflow` only, never on
`pb_approval_config` (AM52). Escalation "after N days" is the engine's
delegation/escalation, configured on the route — not a bespoke cron.

### B2. Credentials — an owner input the new session must ask for on day one

The new session cannot log in. The owner must EITHER give the current
`ash@biztinct.com` password (used only to reset a validator, never to test
with), OR authorise re-activating uid 2065:
`UPDATE res_users SET active=true WHERE id=2065;` (password still
`RizeP0!2026`; deactivate again at close). Prompt 1 asks for this.

---

## Part C — The five tabs: what exists, what to build, and why

Owner rulings taken 2026-09-15 (record as **D10–D13** in the ledger):
- **D10** Mixed approach: EXTEND Leave & Attendance; BUILD Hiring, Goals, HR
  Comm and Training fresh in the RIZE style.
- **D11** Build and test on `payobook`.
- **D12** Outside services (LinkedIn posting, e-signature, Google Calendar,
  Slack) stay OFF — email only, ICS attachments, screens built ready to
  connect. Same as D3.
- **D13** Field attendance = location + selfie, no face matching, no
  biometric storage.
- **D14 (designer's call, owner delegated):** Training REUSES the installed
  E-Learning content engine plus Surveys; Hiring KEEPS the standard applicant
  store underneath a bespoke requisition-to-offer layer. Rationale below.

### C1. Hiring & Recruitment → new module `pb_hiring` (3 phases)

**Exists (installed):** `hr.job`, `hr.applicant` (stages with `hired_stage`,
`kanban_state`, refuse reasons, CV attachments), `hr.recruitment.source`,
**`hr.talent.pool`** (= the sheet's resume bank), `hr.job.platform` (= posting
targets), `calendar.event` inherit (= interview meeting), public `/jobs` page
(`website_hr_recruitment`). `hr_recruitment_survey` (interview scorecards) NOT
installed.

**Exists (ours):** `pb.employee.comp` pay packages (= the offer's salary
file), the letter engine (= offer letter, country templates), the journey
engine + `_after_onboard` (= hire → onboarding case, verify the exact opener
in `pb_zoho_bridge/models/zoho_pipeline.py:627` and `pb_onboarding`'s
extension of it), `wfp.budget.actual` (= budget status), `pb.access.delegation`
(NOT reused for recruiter cover — too heavy; see below).

**Decision:** keep the standard applicant/job/talent-pool tables as the
STORE (reliable, already debranded at menu level, feeds `/jobs`), and build
everything the sheet actually asks for as a bespoke layer with RIZE-style
cockpits. The standard pipeline kanban is skinned (vu-form), not rebuilt.

**Build:**
- `pb.hiring.requisition` (MR): raised only by function heads (group), fields
  per the form (role type, location, budget status read from
  `wfp.budget.actual` with over-budget alert, JD requirements, interview steps,
  reporting manager, timeline, remarks); approval route via matrix
  (manager → HR → finance if over budget); on approval: `hr.job` created or
  linked, recruiter + recruiter's manager notified by country rule, referral
  opens automatically unless "sensitive replacement" flag.
- JD: `pb.hiring.jd` versioned text on the requisition, approval route,
  stored to the vault (letter engine attachment pattern).
- Referral: `/my/refer` portal form → `hr.applicant` with source "Referral",
  tracker on the board.
- Job posting: platform rows on `hr.job.platform`; "Publish" produces the
  ready-to-send pack (email to platform contact + the public `/jobs` page);
  LinkedIn API off (D12).
- Screening: applicant tags shortlisted / rejected / future-fit / fit-for-
  other-role (dropdown → move to another job); resume bank = talent pool,
  HR-only record rule.
- Interview loop: `pb.hiring.interview` (round, panel, slot) → `calendar.event`
  + ICS mails to candidate/panel/recruiter; 24h and 30-min reminder cron
  (idempotent); reschedule requires reason + internal/external tag; no-show
  mandatory log; **feedback form via token page** (`/hiring/f/<token>`, the
  peer-feedback pattern) with a 24-working-hour timer and urgent reminder;
  next-round / rejection mail from editable templates; debrief notes +
  decision on the final round.
- BGV: `pb.hiring.bgv` checklist + document upload, blocks offer drafting.
- Offer: document request mail with 2-day deadline + reminders → candidate
  upload via token page; offer prep = salary proposal on `pb.employee.comp`
  (proposed lines) → hiring-manager review (route) → offer letter via the
  letter engine (country template) → candidate review token page → "signed"
  recorded manually (e-sign off, D12) → position closed, hiring manager +
  recruiter manager notified → `hr.applicant` moved to hired stage → the SAME
  onboarding path a Zoho arrival takes.
- Recruiter cover: `cover_user_id` + window on the requisition, manager
  approval (route), audit in chatter — lighter than `pb.access.delegation`
  because nothing about groups changes.
- Analytics lens (Insights hub): time to fill / to offer / in stage, offer
  acceptance, source effectiveness, delay split internal/external; XLSX via
  the export canon.
- Agency: `agency_vendor_id` → `pb.vendor` (P11) on the requisition, hiring
  manager notified, vendor performance counted on the vendor card.

**Surfaces:** Lifecycle hub → **Hiring** lens, seq **10** (before New joiners
at 20 — hiring precedes joining); board = requisitions × stage with the
pipeline drawer; `/my/refer`, `/my/hiring` (hiring manager's own
requisitions); token pages for candidates/panels. Palette block **3500**.

### C2. Goal Setting → new module `pb_goals` (2 phases)

**Exists:** nothing for goals (`hr_appraisal` is uninstallable on this
version). Reusable: journey automation keys (Day-1 trigger), the
check-in/reminder pattern (`pb_probation` 1:1 + `pb_pip` check-ins), the
approval matrix, `pb_home_hub` for "HR daily task list", XLSX export canon,
editable mail templates pattern (`pb_pay_delivery`).

**Build:**
- `pb.goal.cycle` (FY, mid-year date, org cycle), `pb.goal` (employee, title,
  description, timeline, weightage, self-rating, state draft → submitted →
  manager-approved → HR-locked → closed/archived; lock timestamp + who),
  `pb.goal.kr` (key result, progress %, history rows), `pb.goal.checkin`
  (monthly, auto-scheduled, must be marked complete), `pb.goal.change`
  (formal change request after lock; route manager + HR).
- Trigger: register `goals_kickoff` in the onboarding automation handlers
  (Day-1 step done → cycle opened, employee gets 2 weeks, reminders).
- Approval: ONE route employee → manager (weightage) → HR lock, through the
  matrix; escalation on SLA via the route's escalation, logs in the request.
- Mid-year / joining-month logic: applicability computed from joining date vs
  cycle (Nov joiner with Mar FY end → pro-rated, explained by mail).
- Scoring: weightage × KR score → aggregate; year-end archive.
- Reports lens (Insights): progress, completion %, missed check-ins, manager
  compliance, year-end scores; XLSX.
- Home lens: "Goals waiting on you" (pending approvals, overdue check-ins).
- Visibility: employee own, manager team, HR all (record rules).

**Surfaces:** People hub → **Goals** lens seq **70** (after Praise at 60);
`/my/goals` portal (create, progress, check-in); manager view on the board.
Palette block **3600**.

### C3. HR Comm → new module `pb_hr_comm` (1 phase)

**Exists:** `pb_rnr/models/celebration.py` (anniversary engine, `anniv_mail`
switch OFF) — extend it with birthdays rather than duplicate; `pb_rnr_wall`
(recognition wall on Home) — announcements can post there; the mail
template + `publish_notify` bulk pattern (`pb_pay_delivery`).

**Build:** `pb.hr.comm.post` (date/time, one-off or recurring, company/
country, audience, subject, body, template/poster attachment, responsible HR,
state scheduled → sent), the communication calendar (month view lens),
"responsible notified 2 days prior" + edit window rule (edits allowed until
T-2 days by the responsible; after that HR head), scheduled send cron
(email; Slack off, D12), per-country HR responsibility (matrix responsibility
`hr_lead` scoped by company), head-HR full visibility, birthdays +
anniversaries switched on with a personalised card mail (the "poster" = the
email card, D7).

**Surfaces:** People hub → **Announcements** lens seq **80**; a Home lens
"Coming up" (next 7 days); Settings category "Announcements" for templates.
Palette block **3700**.

### C4. Leave & Attendance → EXTEND `pb_timeoff` + `pb_driver_checkin` (1 phase)

**Exists (verified):** `pb_timeoff` Leave Command Center over `hr.leave`
(approval queue through the matrix adapter `hr_leave_approval.py`, month
heatmap, balance board, apply-on-behalf, officer gate); `pb_attendance_flow`
(missing punches, late rules, corrections with approval); `pb_driver_checkin`
GPS PWA with **`pb_selfie_attachment_id` already on `hr.attendance`** and a
manager live map; `pb_today` triage board ("who is in, who is late, where the
field is"); `hr_holidays` leave types/allocations/carry-over.

**Gaps against the sheet (all confirmed absent in `pb_timeoff.py`):**
country holiday calendar for everybody; HR escalation when a manager sits on
a request > 2 days; carry-forward alert 6 months before a double balance;
backdated-request alert; sick-leave exception path; "cannot edit past
leaves"; field-staff (agronomist) eligibility for the check-in PWA.

**Build (inside the existing modules, new files only where possible):**
- Holiday calendar lens: public holidays per company/country from
  `resource.calendar.leaves`, shown to every employee (`/my/holidays` +
  a lens on Workforce), with the year's list per country side by side.
- Escalation: the leave route's escalation step at 2 days → HR lead (matrix,
  not a cron); backdated request → alert to HR at submit; sick leave type
  flag allowing backdating + optional certificate upload; past-leave edit
  refused with a friendly error.
- Carry-forward watch: cron 6 months before the cut-off flags employees whose
  balance would double; mail + activity; idempotent.
- Field staff: generalise the driver PWA's eligibility from "driver" to a
  configurable group (`pb_driver_checkin.field_groups`), rename the surface
  copy to "Field check-in" (drivers remain a case of it); status visible on
  `pb_today` and to the team; leave overlaps drawn on the check-in board.

**Surfaces:** Workforce mission already owns Leave/Attendance/Today —
add lenses there; `/my/holidays`. Palette block **3800**.

### C5. LnD → new module `pb_training` over E-Learning + Surveys (3 phases)

**Exists (verified):** `website_slides` — courses (`slide.channel`), content
(`slide.slide` types video / document / article / image / quiz, upload or
Google-Drive), per-person completion (`slide.slide.partner.completed`),
in-lesson quiz (`slide.question` / `slide.answer`), tags, karma. **NOT
installed:** `survey` (question bank, scored tests, attempts, time limit,
certificates) and `website_slides_survey` (certification slide type).
**Ours:** `pb_probation`'s `pb.training.track` / `pb.training.item` /
`pb.training.status` with `_check_training_gate()` at
`probation_review.py:833` and `settle_training(status_id, done, score)` at
`pb_probation.py:395` — a small course tracker that the probation verdict
already gates on. `pb_learn` is PRODUCT training (how to run payroll) —
unrelated, leave it alone.

**Decision (D14):** rebuilding a video player, progress tracking, a quiz
engine, a question bank and certification is months for a worse result. Use
E-Learning as the content engine and Surveys as the test engine; build the
Payobook layer on top; **the learner never sees the public `/slides` site** —
every learner surface is ours under `/my/training`, and the public E-Learning
and survey routes are gated to internal users and debranded.

**Build:**
- E1 (gate phase): install `survey` + `website_slides_survey` (owner
  authorised); re-skin the learner flow — `/my/training` (my courses, due
  dates, progress, "take the test" only after every item is complete,
  score shown immediately, certificate download); the test itself runs on
  the survey page under the portal theme with the debrand seams verified
  (white-label sweep of `website_slides` + `survey` user-facing strings is
  part of E1). **Stop for an owner look at the learner flow before E2.**
- E2: `pb.training.assignment` (course × person/group × due date × reason:
  day-one mandatory, probation-linked, compliance recurring, ad hoc, manager/
  leadership), question bank = survey question library, reminders +
  escalation to manager/HR (idempotent cron), delay reason required from the
  employee (sick / emergency / other, approved by manager), recurring
  compliance schedules, **probation link: `pb.training.item` becomes a thin
  view over an assignment so `_check_training_gate()` keeps working
  unchanged** (adapter, no data migration of history — old rows stay).
- E3: training budget — `pb.training.claim` (invoice + certificate upload,
  HR validation route, reimbursement → `pb.oneoff.feed` queue as an award-
  type line, D-money rule); analytics lens (completion ratio, performance
  ratio, overdue, date range, weekly/monthly pack by mail); certificates in
  the vault.

**Surfaces:** the **Learn** mission on the rail currently holds `pb_learn`
(product lessons). Training joins Learn as its first lens **"My training"
(employees) / "Training" (HR)** — do not create a second rail item. HR admin
of courses stays on the skinned E-Learning backend. Palette block **3900**.

---

## Part D — Phase plan

Each row = one Opus implementation cycle with its own handover
(`RIZE_W2_P<x>_<NAME>.md`), numbered tests, deploy, report. Sequential (one
live server). Order is by owner value and by what each unblocks; the owner
may re-order.

| # | Module | Scope | Depends on |
|---|---|---|---|
| A1 | `pb_hiring` | requisition + budget check + approval + JD + referral + posting-ready + Hiring lens + `/my/refer` | — |
| A2 | `pb_hiring` | interview loop (schedule/ICS/reminders/reschedule/no-show), panel feedback token page + 24h timer, next-round/reject mails, debrief | A1 |
| A3 | `pb_hiring` | BGV, document request, offer via pay package + letter, candidate review page, closure → onboarding, recruiter cover, agency tag, analytics lens | A2 |
| E1 | `pb_training` | install survey; learner flow `/my/training` re-skinned; white-label sweep; **owner checkpoint** | — |
| E2 | `pb_training` | assignments (mandatory/probation/compliance/ad hoc), reminders + escalation, delay reasons, probation gate adapter | E1 |
| E3 | `pb_training` | budget claims → feed, analytics + mail pack, certificates | E2 |
| B1 | `pb_goals` | cycles, goals, KRs, Day-1 trigger, submit → manager → HR lock route, `/my/goals`, People lens | — |
| B2 | `pb_goals` | monthly check-ins, mid-year/joining logic, change requests, scoring, reports lens, Home lens | B1 |
| D1 | `pb_timeoff` + `pb_driver_checkin` | holiday calendar, 2-day escalation, carry-forward watch, backdated/sick rules, field check-in generalisation | — |
| C1 | `pb_hr_comm` | calendar, posts, T-2 rule, scheduled mail, birthdays on the celebration engine, lenses | — |

Ten cycles. Palette: A 3500, B 3600, C 3700, D 3800, E 3900. Lens seqs as
in Part C. Ledger entries continue at **R131**; rulings at **D10**.

Owner checkpoints (the only stops): E1 learner flow; anything that would
install or uninstall a module on the live DB (E1's `survey` install is
pre-authorised by this document once the owner confirms Prompt 1).

---

## Part E — Prompts for the new session

Paste **Prompt 1** as the first message. It makes the new session produce the
owner-facing blueprint first (as RIZE did), then run the phases. Prompt 2 is
the per-phase launch text the new session's designer uses for each Opus agent.
Prompt 3 is the resume text for an interrupted agent.

### Prompt 1 — kickoff (paste as the first message of the new session)

```
We are continuing the RIZE HRMS programme into Wave 2. Read, in this order,
before doing anything:
  1. docs/handovers/RIZE_W2_HANDOVER.md   (this wave: learnings, what changed, decisions, phase plan)
  2. docs/handovers/RIZE_LEDGER.md        (conventions, deploy ritual, R1–R130, D1–D9)
  3. docs/handovers/RIZE_CLOSEOUT.md      (what is live, logins, switches)
  4. docs/handovers/APPROVAL_MATRIX_CLOSEOUT.md §1 and the adapter recipe in the W2 handover Part B1

Scope: the five uncoloured tabs of RIZE/HRMS Proposal - Must Have.xlsx —
Hiring & Recruitment, Goal Setting, HR Comm, Leave & Attendance, LnD — are now
to be built in Payobook. Rulings D10–D14 in the W2 handover are decided; do
not re-ask them. Record them in RIZE_LEDGER.md as D10–D14 first.

Model of work: the phased methodology in my global CLAUDE.md — you (Fable)
design each phase as a handover file docs/handovers/RIZE_W2_P<x>_<NAME>.md,
launch an Opus 5 subagent in THIS session with it, read its report, update the
ledger, launch the next. No Fable code review. Run A1→A2→A3→E1→(stop for my
look at the learner flow)→E2→E3→B1→B2→D1→C1 back-to-back without asking me,
except at the E1 checkpoint and before any module install/uninstall on the
live database.

Step 0 (before any phase): produce docs/design/rize-w2-blueprint.html —
same design system as docs/design/rize-hrms-blueprint.html (same tokens,
fonts, light+dark) — with, per tab: the requirement rows from the sheet, what
exists today, what gets built, where it appears on screen, the approval
routes, the switches. Show it to me. I will approve or trim; then start A1.

Credentials: I will give you EITHER the current ash@biztinct.com password
(use it only to re-activate a validator, never to test with) OR permission to
run  UPDATE res_users SET active=true WHERE id=2065;  on payobook so that
igc1.validator / RizeP0!2026 works again. Ask me for one of these now, before
Step 0, and deactivate the validator again at the end.

Standing rules, every phase, verbatim in every handover: white-label (never
"Odoo" in anything a user sees); plain English on screen and in every
message to me; the design mandate (extreme-WOW, Lucide, light+dark validated
in Chrome); commit per feature; build and test on the payobook database only;
test data stays but is named as demo; group grants reverted after tests;
every sign-off is an Approval Matrix adapter, never a new chain; every
hand-built window action carries 'views'; every nolabel field in a group
carries colspan="2"; ⌘K blocks 3500/3600/3700/3800/3900 per the plan; ledger
entries from R131; the same RIZE test actors and companies.

When everything is live: write docs/handovers/RIZE_W2_CLOSEOUT.md in the
shape of RIZE_CLOSEOUT.md, update docs/design/rize-closeout.html (or a W2
page) for me, and list the decisions that are mine.
```

### Prompt 2 — per-phase launch (the designer pastes this into each Opus agent, filling the blanks)

```
You are implementing RIZE Wave 2 phase <A1|…> of the Payobook product.
Read FIRST, in order: docs/handovers/RIZE_LEDGER.md (all of it — binding
rules, deploy ritual, R1–R<latest>, D1–D<latest>), then
docs/handovers/RIZE_W2_HANDOVER.md Parts A, B and C<n>, then your phase
handover docs/handovers/RIZE_W2_P<x>_<NAME>.md. Do not re-derive anything the
handover marks "verified". Clone the precedents it names (file:line).

Deliver: the module(s) as specified; every numbered test case run and its
result recorded; deployed to the payobook database with the exact ritual
(clean staging → scoped rsync per module → detached install → real log
checked → asset purge if JS/SCSS → restart → Chrome-MCP verification in light
AND dark, screenshots); a feature-scoped commit after each verified slice
(explicit file staging, engineering-language message ending with the
attribution line in force); the ledger's "Phase plan & status" row updated;
new gotchas appended as R<next>; a report back covering: commits, per-test
results, deploy EXIT, deviations from the handover and why, palette rows
used, registry names, API signatures other phases will call, test accounts
created, switches added with their defaults, anything the owner must decide.

Hard rules: white-label — the word "Odoo" never in a user-visible string;
plain-English labels; the design mandate (Lucide icons only, no emoji, no
gradients, locked palette, hero moment, zero dead ends); every sign-off is a
biz_approval_workflow adapter with a seeded route AND a migration, never a
new chain; hand-built act_window dicts carry 'views'; nolabel fields in a
<group> carry colspan="2"; search-view <group> has no string/expand; mails
asserted on mail.mail rows; hooks and crons never raise; reminders
idempotent; sudo only where the handover says; no --delete into
/odoo/odoo-server/addons/ itself; never deploy the repo's copies of standard
addons; test as the RIZE test actors, never as the owner; revert every group
you grant, verified against a snapshot; test data stays, named as demo.

If the session is interrupted, on resume recover state from git status,
git log and the server (ir_module_module, the log) — never from memory —
and continue from the last committed slice.
```

### Prompt 3 — resuming an interrupted agent (SendMessage to the same agent id)

```
You were interrupted mid-phase. Do not trust your memory of where you were.
Recover from disk: git status, git log --oneline -15, the module tree, and on
the server: ir_module_module state/version for your module(s), the tail of
/var/log/odoo/odoo-server.log, and whether the service is up (if a deploy was
in flight, verify the server is serving before anything else). Then continue
from the last committed, verified slice. Commit every finished slice from
here on and poll long waits with short repeated until-loops.
```

---

## Appendix — verified facts for the phase designer (do not re-derive)

- Approval adapter canon: `pb_rnr/models/nomination_approval.py` (register_chain +
  `_approval_process_key` + `_chain_*` + `_approval_seed_default`);
  migration pattern `pb_offboarding/migrations/19.0.1.1.0/post-resign_approval.py`.
- Onboarding automation keys: `pb_onboarding/models/journey_ext.py:70`
  `_automation_handlers()`; key list documented at
  `pb_onboarding/models/onboarding_common.py:15`.
- Zoho → onboarding hook: `pb_zoho_bridge/models/zoho_pipeline.py:627 _after_onboard(case, rec)`,
  extended in `pb_onboarding/models/zoho_pipeline_ext.py:26`.
- Buddy opener signature (pattern for "open X for employee"):
  `pb_onboarding/models/buddy_nomination.py:230 open_for(employee_id, case_id=None)`.
- Probation training gate: `pb_probation/models/probation_review.py:833 _check_training_gate`,
  `pb_probation/models/pb_probation.py:395 settle_training(status_id, done=True, score=None)`,
  models in `pb_probation/models/training.py` (track :39, item :139, status :164).
- Journey task hooks: `pb_lifecycle/models/journey_task.py:130 action_done(payload=None)`;
  case task generation `journey_case.py:278 _generate_tasks` (R31: a new step
  column needs `_generate_tasks()` extended).
- Letters: `pb.letter.template` / `pb.hr.letter` in `pb_lifecycle/models/letter.py`
  (:56, :84); letter approval adapter `letter_approval.py:50`.
- Comp: `pb.employee.comp` + `pb.employee.comp.line` (pay package),
  `pb.incentive`, `pb.oneoff.feed`, `pb.payroll.calendar` — `pb_comp_ben/models/`.
- Leave cockpit facade: `pb_timeoff/models/pb_timeoff.py` (`get_board`,
  `act`, `apply_on_behalf`, `_balances`); adapter
  `pb_timeoff/models/hr_leave_approval.py:51` (mixin form of the recipe).
- Field check-in selfie: `pb_driver_checkin/models/hr_attendance.py:16 pb_selfie_attachment_id`.
- Recruitment store: `hr_recruitment/models/hr_applicant.py` (`kanban_state`
  :108, hired-stage logic :599), `hr_recruitment_stage.py:25 hired_stage`,
  `hr_talent_pool.py:8`, `hr_job_platform.py:8`, `calendar.py:8`.
- E-Learning: `website_slides/models/slide_slide.py` (types :88–92,
  `action_mark_completed` :830), `slide_question.py:9/:63`,
  `slide_slide_partner.py:17 completed`.
- Celebration engine: `pb_rnr/models/celebration.py`; wall `pb_rnr_wall.py`.
- Home/today: `pb_home_hub` (queue), `pb_today` (triage), inbox facade
  `pb_approval_config/models/inbox_facade.py`.
- Live DB facts (2026-09-15): companies 1 Your Company, 2 Payobook, 5 Payobook
  Vietnam JSC, 6 Payobook Singapore, 7 SG Company; uid 2 = owner (password
  unknown); uid 2065 validator INACTIVE; ess1.demo (1984) active; `survey`,
  `website_slides_survey`, `hr_recruitment_survey` NOT installed;
  `hr_appraisal` uninstallable.
- Palette blocks taken up to 3450 (`pb_approval_config`, `pb_pay`, `pb_workseg`).
