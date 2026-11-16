# WDGAP S6-B — Apply and ask — report

> **PAUSED** (owner pause, 2026-11-16, during the PA1 / IM1 follow-up).
> Done and committed as WIP: IM1 (no "Before they join" list for internal moves, one note +
> "Joining your team" for the new manager) and PA1 (question log without any person,
> `_log_access = False`; separate coded daily counter `pb.policy.quota`; HR list "Could not
> answer" first + Excel; numbers only under 5 people), tests IM1-1/2 and PA1-1…7, vi/id PO
> files refilled (PO gate passes locally). Versions bumped to 19.0.1.1.0.
> **Exact next step on resume:** test database `wdgap_s6b_t` is kept (both modules installed,
> clean dump at `scratchpad/s6b/clean.dump`). Run
> `bash scratchpad/s6b/go.sh f1 -u pb_hiring_internal,pb_me_payai --test-enable --test-tags /pb_hiring_internal,/pb_me_payai`
> and fix any failure (the run was stopped at test 54 of ~70, no failure reported yet); then the
> neighbour run `/pb_hiring,/pb_me_portal,/pb_ask_hr` (compare with §4.2), a short walk of
> Home › Policies questions list and `/my/jobs/moves`, write report sections "Follow-up PA1"
> and "Follow-up IM1", commit, push, drop `wdgap_s6b_t`.

**Status: DONE** (2026-11-16). Branch `wdgap-s6b` (from `origin/19.1` @ `abc2259b6`). Two NEW
modules, no existing file edited. Built, tested (64 new tests, 0 failed; neighbour suites equal
to baseline), browser-walked and self-reviewed by the S6-B builder. Not deployed. Test database
dropped. C-1 / C-2 checked against `origin/wdgap-s8b` (S8-B report §2) and `origin/wdgap-s8c`
(`hr.job.pb_hiring_paused`, `hr.department.pb_hiring_paused`) — read only, not merged.

| Module | Version | What it is |
|---|---|---|
| `pb_hiring_internal` | 19.0.1.0.0 | Item 4: staff apply for internal roles (E4, C-1, C-2) |
| `pb_me_payai` | 19.0.1.0.0 | Item 5: PayAI for employees, company policies only (E5) |

## 1. What was built

### 1.1 `pb_hiring_internal` — Jobs inside the company

- **Who can apply, per role** — new field `pb.hiring.requisition.pb_staff_posting`
  (`outside` "Outside candidates only" = default and today's behaviour / `both` "Staff and
  outside candidates" / `staff` "Staff only"). On the role form (beside "Open to referrals")
  and on the new Hiring hub tab **Staff moves**.
  - Staff-only roles never reach the careers page: `hr.job.pb_hiring_accepts_applications`
    answers no, `pb.hiring.posting.publish_for` refuses with a sentence, and choosing "Staff
    only" on a role already published takes it off (`website_published` false, note on the role).
- **Which roles an employee sees** (`_pbhi_roles_for` / `_pbhi_open_for_staff`): open, open to
  staff, not confidential, not a quiet replacement, the employee's own company, and **not
  paused (C-2)** — `'pb_hiring_paused' in hr.job._fields` probed, read under sudo; absent field
  = not paused. Re-checked at the moment of applying.
- **Employee pages** (portal routes, session-resolved employee, sudo after the checks):
  `/my/jobs` (open roles + "Your applications"), `/my/jobs/<id>` (advert, apply form, status,
  withdraw), POST `/my/jobs/<id>/apply`, POST `/my/jobs/<id>/withdraw`, `/my/jobs/moves`
  (manager page). Tile "Jobs inside the company" in Growth, drawn only when the count is above
  zero (a role open to staff, or an own application) — so nothing shows after install.
- **Applying** (`hr.applicant._pbhi_apply`): ONE standard `hr.applicant` on the real role with
  stock `employee_id` = the person, `pb_internal` = True, source "Internal" (looked up by name),
  its own contact (so a recruiter's edit never renames the person's real contact), optional
  note (2,000 chars) and CV (PDF/Word ≤ 5 MB). One open application per role.
- **What the employee sees**: plain states only — Received / Being considered / Offer being
  prepared / Offer accepted / Moving to this role / Not this time / Withdrawn. Never a stage
  name. My requests row ("Internal role") lists ONLY staff applications (an outside hire's old
  candidate row also points at their employee and is excluded). Withdraw allowed before the
  Offer stage and while no live offer exists; it moves the application to "Drop-out".
- **E4 — the current manager is told only when an offer is near.** "Near" = the application
  enters stage `offer`, `post_offer` or `joined`, or an offer is drafted (`draft_for`).
  Until then the manager is not a follower (removed at apply if any rule subscribed them), gets
  no note, activity or approval, and nothing on their pages mentions it. At that moment, once:
  `pb_manager_told_on` / `pb_manager_told_id` stamped on the application; ONE in-app note in the
  manager's inbox (`message_notify` on the mover's employee record, only for internal users whose
  notifications go to the inbox — never an email of its own); a "Needs you" line on the
  manager's home ("<name> may move to another role", 21 days after being told) linking to
  `/my/jobs/moves` (works for portal managers too). If the manager is on the role's hiring
  team (reporting manager, who asked for it, recruiter, recruiter's manager, interview owner,
  or holds the Recruiter group) the employee is told before applying: "Your manager is on the
  hiring team for this role, so they will see your application."
- **C-1 — an internal hire ends in a job change, never a second person.** For an offer whose
  candidate is internal, "Confirm they joined" (`action_confirm_joined`) runs NONE of the
  new-joiner legs: no employee, contract, pay package, benefits, login or joining checklist
  (each `_ensure_*` is also guarded one by one). It links the offer to the existing employee,
  marks the candidate hired, files the signed letter, fills the role, sets "Job change to do",
  then: when `'pb.job.change' in env` (and it has `pb_start_for_employee`) it returns that
  action and the board opens it (`board_patch.js` patches `p6Act` to `doAction` the returned
  `pb_open_action`); otherwise the board says "Job change to do: change their job on their
  employee record." The Staff moves tab has "Start the job change" / the same calm note.
- **"Fits another role"** copies keep `employee_id` and `pb_internal` (`copy_data`), so a
  second role can never hire a second employee.
- **Retention clean-up** already protects any candidate with an employee record
  (`_pb_retention_protected` → 'hired'); tested.
- **Hiring hub › Staff moves** (lens via the `pb_hiring_hub_lens` registry, hiring-team group +
  probe `pb.hiring.internal.can_open`): counts, Applications (person, now → role, state,
  "Manager told d MMM" / "Manager not told yet", job change button), Who can apply (segmented
  control per open role; locked for confidential and quiet replacements; "Hiring paused: hidden
  from staff" flag). The candidate drawer gets a "Works here" line (job · manager told or not).

### 1.2 `pb_me_payai` — Company policies on My Payobook (E5)

- **HR side**: Home › **Policies** lens (Home hub registry, `hr.group_hr_user` + probe): status
  ("PayAI for employees" on/off, AI account "Set up" / "Not set up yet", questions today and
  this month), switch on/off and daily limits (HR manager or administrator only), upload
  (PDF with text / .docx / .txt / .md ≤ 10 MB; read into sections at headings; a scan says
  "No words found" and cannot be published), publish toggle, remove. The switch and limits are
  also on the existing Settings page beside PayAI's other switches ("PayAI for employees").
- **Employee side**: `/my/ask-policy` — question box, the published policy titles, a privacy
  card; the answer card names the policy and section ("From the policy"), "Answers come from
  the policy text. If something matters, check with HR." and "Ask HR instead". When it cannot
  answer (not in the files, AI account failed, daily limit): a plain sentence and "Ask HR, with
  my question" — a small form that POSTS the question to `/my/ask-policy/ask-hr` (never in a
  web address, so it is not kept in browser history or server logs), which draws Ask HR's own
  new-question form with subject and details filled in (pb_ask_hr's own form helper; its route
  is not changed; nothing is sent for them until they press Send).
  Tile "Company policies" in People, drawn only when the person is offered it at all.
- **Readiness** (`pb.policy.answer._ready_for`): company switch on (default OFF everywhere) AND
  the company's own AI account (`payroll.ai.config`, its own "Policy answers for employees" row
  first — new purpose via `selection_add` — else its own PayAI row; never another company's,
  never a document-reading engine, a keyed provider needs a key) AND a published policy with
  words for the person's department (empty = everyone). Otherwise the employee sees nothing and
  the page redirects home.
- **Answering** (`ask`): local keyword search (accent-folded, stop words out, ≥ 2 shared words,
  heading bonus, top 3 sections). No match → "not found" WITHOUT calling the AI account. Limits
  checked (per person / per company per day, only calls that reached the AI account count).
  Then ONE call through `_send` (the only egress point) with a fixed instruction text, the
  matching excerpts and the scrubbed question; reply must be JSON with the excerpts used or
  `NO_ANSWER`. Names put back locally (`restore_names`) for the person who asked.
- **Privacy** — what leaves: the fixed instruction (no company, no person), the matching
  policy sections, and the question after the company's full employee names (+ the asker's
  own name parts and login name) are replaced by placeholders and `generic_scrub` takes out
  emails, phones, long numbers and amounts. Never the employee's name, login, email, id,
  department, job or any record. The question's words are NOT stored: `pb.policy.question`
  keeps who/when/outcome/which policy (for limits and counts); HR sees counts only (the log is
  readable by administrators only).
- **No personal figures, no general knowledge**: nothing in the module reads a payslip, leave,
  contract or the back-office PayAI engine/data queries (tested by guard + source scan); the
  instruction forbids outside knowledge and guessing.

## 2. Files edited outside the new modules

**None.** Every extension is by inheritance from the two new modules:
`pb.hiring.requisition`, `pb.hiring.posting`, `hr.job`, `hr.applicant`, `pb.hiring.offer`,
`pb.hiring` (facade: `_act_confirm_joined`, `get_candidate`), `pb.me.home` (tile registry
`TILES.setdefault`, `_pbme_needs_extra`, `_my_requests_sources`, `_my_requests_rows`), the
portal controllers (subclasses of `PbMePortal` / `PbAskHrPortal` adding their own routes and
calling `_ask_hr_render_new`), QWeb `inherit_id` (portal home, breadcrumbs), OWL `t-inherit` of
`pb_hiring.P1Overlays`, `patch(PbHiringBoard.prototype)`, the Hiring and Home hub lens
registries, `payroll.ai.config.purpose` `selection_add`, `res.config.settings` view inherit.
`pb_me_portal`, `pb_hiring`, `pb_ask_hr`, `pb_payroll_ai_insights`, `pb_lifecycle`,
`pb_explorer`, `pb_pack_*` untouched.

## 3. Contracts (what other phases rely on / what I pass)

- **C-1 — vals passed to `pb.job.change.pb_start_for_employee(employee_id, vals)`** (keys taken
  from the S8-B draft's `START_KEYS`, falsy values left out): `job_id`, `job_title`,
  `department_id`, `parent_id` (offer's reporting manager, else the role's), `company_id` (the
  role's company), `effective_date` (joined-on / expected join / start date), `wage` (the
  offer's basic monthly earning line, when there is one), `reason` ("Moved to <role> through an
  internal application."), `reason_kind` = `'transfer'` (HR can change it on the screen),
  `source` = `'internal_hire'`, `source_ref` = the offer reference. All are keys the S8-B
  report §2 accepts.
  A refusal or non-dict answer leaves "Job change to do" and never undoes the move.
- **C-2** — reads `hr.job.pb_hiring_paused` by probe only; no dependency on S8-C.
- **C-3** — no `pb_me_portal` edit; existing glyphs only (`briefcase`, `file-text`, `users`,
  `shield`, …); PayAI's "sparkles" is drawn inline in this module's own template.
- **C-4** — `pb_ess_workforce` not used (owner chose no personal figures).
- Fields others may read: `hr.applicant.pb_internal`, `pb_manager_told_on`,
  `pb_manager_told_id`, `pb_job_change_state` (`to_do` / `opened`),
  `pb.hiring.requisition.pb_staff_posting`; `res.company.pb_policy_ai_on`,
  `pb_policy_ai_person_day`, `pb_policy_ai_company_day`; model `pb.policy.question` (the AI-use
  count Step 10 wants).

## 4. Tests

Local database `wdgap_s6b_t` (copy of `upd_p6_t_tpl`, the 33 modules behind the worktree
`-u`'d; vi + id installed), dropped at the end. AI calls are never real: `_send` (the one egress
point) is replaced in every test; the AI account row is a local provider kind needing no key.

### 4.1 New suites — 64 tests, 0 failed (FRESH install `-i` on the restored clean copy)

`pb_hiring_internal` (39 + 4 static):

| # | Case | Result |
|---|---|---|
| B1 | Every role "Outside candidates only" after install (silent) | PASS |
| B2 / B2b | Staff see only open, staff-open, non-confidential, non-quiet roles of their company; never another company's (apply refused) | PASS |
| B3 | C-2 without the field: nothing hidden | PASS |
| B3b | C-2 with the field on: role hidden and apply refused | PASS |
| B3c | C-2 for a role with no job record: the team's pause answer | PASS |
| B4 | Apply = one candidate with `employee_id`, source Internal, own contact; NO new employee | PASS |
| B5 | Second application to the same role refused | PASS |
| B6 | **E4 before the offer**: through Shortlist/Discussion 1/2 the manager gets no note, activity or approval, is not a follower, cannot read the candidate, is refused Staff moves, has no "Needs you" row | PASS |
| B7 | **E4 at the offer**: told once (inbox note names person + role, not the note text), `pb_manager_told_on` set, "Needs you" row; a later stage does not tell again | PASS |
| B7b | A drafted offer counts as "offer near" | PASS |
| B8 | Manager on the role's hiring team detected (reporting manager / recruiter) | PASS |
| B9 | Withdraw before the offer; refused from the Offer stage | PASS |
| B10 / B10b | Employee words, never stage names; My requests shows only staff applications | PASS |
| B11 | "Fits another role" copy keeps the person and the flag | PASS |
| B12 | Staff-only: off the careers page, careers apply refused, Publish refused | PASS |
| B13 | Retention clean-up never takes a staff application | PASS |
| B14 | Staff moves: hiring team only; posting change by recruiter; bad value refused | PASS |
| B20 | `/my/jobs` and role pages as a **portal user**; hidden roles 404 | PASS |
| B21 / B21b | Apply over HTTP with CV; a forged `employee_id` ignored; twice / wrong file / closed role refused | PASS |
| B22 | Status words over HTTP; withdraw over HTTP | PASS |
| B23 | **E4 manager pages** `/my`, `/my/jobs/moves`, `/my/requests`, `/my/team`, `/my/team/approvals`, `/my/hiring` show nothing before the offer | PASS |
| B24 | After the offer: manager home "may move", moves page lists it | PASS |
| B25 | Home tile count 2 → 0 when nothing is open to staff | PASS |
| B26 | Heads-up when the manager is on the hiring team | PASS |
| B27 | Another employee cannot see or withdraw someone's application | PASS |
| B30 / B30b | **C-1 without `pb.job.change`**: no employee, contract, login or checklist made; offer linked to the existing person; "Job change to do" on board + Staff moves | PASS |
| B31 | **C-1 with the flow** (stand-in): opened once with the S8-B keys (incl. `reason_kind='transfer'`), board returns `pb_open_action`, state "opened", nothing created | PASS |
| B32 | Change job refusing never undoes the move | PASS |
| B33 | An OUTSIDE candidate still joins exactly as before (new employee) | PASS |
| B40–B43 | White-label scan; no cron/mail template/automation; PO gate; every page word has vi + id | PASS |

`pb_me_payai` (28 + 5 static):

| # | Case | Result |
|---|---|---|
| P1 | Off by default on a new company | PASS |
| P2 | No AI account: HR "not set up", employee `not_ready`, no call | PASS |
| P3 | Another company's AI account never borrowed | PASS |
| P4 | Document-reading engine / keyed provider without key not used; own PayAI row used | PASS |
| P5 | File read into sections at headings; search finds the right section, nothing for unrelated words | PASS |
| P6 | Answered, names policy + section; log row without the question's words | PASS |
| P7 | Not in the files: no call; model `NO_ANSWER` → not found | PASS |
| P8 | **Egress**: exact messages carry only role/content; no name, given name, manager name, email, phone, login, job, department or company; placeholders present; question + excerpt present | PASS |
| P9 | Daily limits per person and per company, no call once reached | PASS |
| P10 | AI account failure → calm "could not answer" | PASS |
| P11 | **No personal figures**: payslip / leave / allocation / contract / PayAI chat never searched; no back-office engine in the source | PASS |
| P12 | Department audience | PASS |
| P13 / P13b | Desk gates (plain user / portal refused; HR uploads; only HR manager switches + limits); scan without words cannot be published | PASS |
| P14 | Company rule on policy files | PASS |
| P15 | The answer door over RPC answers only for the caller's own record | PASS |
| P20 | Switched off: tile count 0, page redirects, nothing asked | PASS |
| P21 | Portal user asks and reads the answer + source | PASS |
| P22 | Not found → "Ask HR, with my question" posts (never in the address) and opens Ask HR's form filled in; no ticket until sent | PASS |
| P23 | Ask HR's own form unchanged | PASS |
| P24 | Limit sentence on the page, no call | PASS |
| P40–P44 | White-label; silent install; PO gate; every page word vi + id; nothing switched on after install | PASS |

### 4.2 Existing suites (no file of theirs edited) — failure sets equal to baseline

| Suite | Baseline (same DB, without the new modules) | With the new modules installed |
|---|---|---|
| `pb_hiring` (530 tests) | 8 failed + 2 errors: TestClientReview.test_hiring_only_cannot_read_access_directory, TestRecruitInterviewsP5.test_07b, TestRecruitJoining.test_11, TestRecruitPrivacy.test_02 / 02b / 08, TestRecruitPrivacyFiles.test_02, TestRecruitStages.test_13, TestRegistersP9.test_08, TestTheCover.test_t7 | **identical 10** |
| `pb_me_portal` + `pb_ask_hr` (170) | 8: TestMeHomeCards.test_05_grid / test_06_font, TestMeHomeSource.test_01_registry_covers_every_tile / test_12_vi_po, TestPbMePortal.test_01, TestPortalOnlyDoors.test_t1_7, TestAskHrBoardP3d.test_12 / test_13 | **7** — the same minus TestMeHomeSource.test_01 (it passed with the modules installed; no new failure) |

All baseline failures read their own module's source files, a hard-coded old version, the
`/bizapp` route, or the approval engine — none is in a path these modules touch.

### 4.3 Browser walk (local copy, `http://127.0.0.1:8496`, 500 px wide = phone width)

- Employee (PORTAL login): home shows "Jobs inside the company" (Growth) and "Company policies"
  (People); `/my/jobs` lists the two staff roles, hides the outside-only one; role page → Apply
  with a note → "Received" card + Withdraw; `/my/ask-policy` → answer "3 days of paid wedding
  leave" with source chip "DEMO Staff handbook · 2. Wedding leave"; a dog question → "could not
  find" + "Ask HR, with my question" → Ask HR form filled in (address without the question).
- **What reached the (local stand-in) AI service**, captured on the wire: fixed instruction +
  two handbook sections + "Question: Hi, I am [person-1], phone [phone]. How many days of
  wedding leave do I get?" — name and phone out.
- HR/admin: Home › Policies (inside the Home hub, beside Ask HR): status on / AI account set up /
  3 asked · 1 answered · 2 not in the policies; file list published. Hiring › Staff moves (inside
  the Hiring hub): counts, application "Manager not told yet", Who can apply segmented control →
  "Saved. Staff and outside candidates".
- Manager (staff login, no hiring rights) after the application reached Offer: "Needs you" →
  "DEMO Walk Mai may move to another role · An offer is near…"; `/my/jobs/moves` lists it;
  `/vi/my/jobs/moves` fully Vietnamese.
- Console: no errors on any page walked.

Static gates: Python compiles, XML parses, no "Odoo" in any XML/PO/user string of both modules.

## 5. Deviations and decisions made without asking

- **"Offer near" = the Offer stage or later, or a drafted offer** (FACTS Q4/E4 wording "when an
  offer is about to be made"; pb_hiring's stage `offer` means "The person we want").
- **Manager on the role's hiring team**: E4 cannot hide an application from somebody who runs
  that role's hiring, so the employee is told before they apply (role page heads-up).
- **How the manager is told**: in-app only (inbox note for staff who use the inbox + a "Needs
  you" line and `/my/jobs/moves` for everyone). No email of its own (tenant email is off on
  purpose on three databases).
- **Internal moves skip pb_hiring's "joined" automations** (`hooks_p8` `_fire('joined')`) and the
  "Before they join" emails still run as for any signed offer — see owner question 3.
- **PayAI search is keyword-based**, no vector store (FACTS §6.6 "simple keyword/section search
  first"). A scanned PDF has no words and cannot be published.
- **The question's words are not stored** (privacy). HR sees counts, not questions — owner
  question 2.
- Policy answers reuse the company's existing PayAI account when it has no separate
  "Policy answers for employees" row (owner: "uses the database's existing AI account").

## 6. Deploy notes (for the step's deploy agent)

- Tier: **risky** (new modules, access, AI egress). Install order: `pb_hiring_internal`,
  `pb_me_payai` (each `-i` on every database; both need `pb_hiring` / `pb_ask_hr` /
  `pb_payroll_ai_insights` / `pb_home_hub` installed — they are on all five today).
- Silent: no cron, no mail template, no data rows; every role stays "Outside candidates only";
  PayAI for employees is off on every company; both tiles hidden.
- After install: asset purge (`/web/assets/%`) + restart (new frontend and backend assets).
- Nothing touches pay. No data migration.
- Seam at merge with S6-A/S6-C: all three add `pb.me.home` overrides and portal routes; every
  override here calls `super()` and appends; helper names are prefixed `_pbhi_` / `_pbpa_`.
- With S8-B merged: B31 will start passing through the REAL `pb.job.change`; re-run
  `/pb_hiring_internal` after the merge and check the prefill lands in its screen.

## 7. Owner questions (plain words)

1. **Should a manager ever be able to see that someone in their team applied earlier than the
   offer?** Today: no, unless the manager is on that role's hiring team (then the employee is
   warned before applying). Nothing to decide unless you want a change.
2. **Should HR see the questions people ask PayAI?** Today the words are not kept; HR sees only
   how many questions were asked, answered, and not found. Keeping the words would help HR fix
   gaps in the policies, but people may type private things into the box.
3. **When someone moves inside the company, should the "Before they join" emails (laptop, buddy,
   first chat) still go to them?** Today they still go, as for any signed offer. Turning them off
   for internal moves is a small follow-up.

## 8. Left for later

- A count of internal moves on the Hiring numbers (the "Internal" source already makes it
  countable; no report built).
- PayAI: smarter search (synonyms, Vietnamese/Indonesian word forms), and asking in a follow-up
  conversation (today each question stands alone).
- A dedicated `pb_me_portal` glyph for PayAI on the home tile (C-3 prep commit), if wanted.
- The browser tab title of the new employee pages is the English page name for every language
  (same as Ask HR's pages today).
- The walk was at phone width (500 px, the browser window available); desktop width of the
  employee pages was not seen (CSS has a two-column layout from 860 px).
- Seam test with the REAL `pb.job.change` (S8-B) after both are merged: B31 uses a stand-in.

## 9. Gotchas → ledger rows

- **S6B-1**: On Odoo 19 an employee's own `department_id` is read through `hr.version`; a test
  that blocks `hr.version` reads to prove "no personal records" breaks the person's own
  department lookup. Guard payslip / leave / contract models, not `hr.version`.
- **S6B-2**: A stand-in for a provider in a test must be a plain function on the class
  (`patch.object(cls, '_send', new=lambda self, *a: …)`), not a callable object: an object is
  not bound and receives the wrong arguments.
- **S6B-3**: `hr.applicant` with no `partner_id` but an `email_from` FINDS an existing contact by
  email (stock `_inverse_partner_email`) — for an employee that is their real work contact, and
  later edits of the candidate rename it. Give an internal application its own contact.
- **S6B-5**: Odoo 19's test loader does NOT collect `test_*` methods a TestCase inherits from a
  plain mixin class (`class Gates: …` + `class TestX(Gates, TransactionCase)`): they silently
  never ran. Put the methods on the TestCase itself, and check the "Starting …" lines.
- **S6B-6**: A session restart kills runs started with the Bash tool's background mode (exit
  137). Long suites: `nohup bash script &` + `disown` from a scratch script, then poll a file.
- **S6B-7**: The browser walk caught the PayAI → Ask HR hand-off putting the employee's question
  in the web address (history, server logs). Any "carry text to another page" goes in a POST body.
- **S6B-4**: Local `-u` of 33 behind modules on the 150 MB template took 40 minutes with
  seven other builders on the Mac; dump the upgraded copy once (`pg_dump -Fc`, 18 MB) instead of
  re-upgrading.
