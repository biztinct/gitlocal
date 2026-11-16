# WDGAP S9 — plumbing facts: performance and listening

Step 9 of the study's build order ("Performance and listening"). This is a read-only code survey, done on 2026-11-15 against `origin/19.1` @ `7f0fa3aad` (the W2 deploy report). **The plumbing below is verified, so do not re-derive it.** Spot-check a line before you rely on it. Paths are relative to the repo root.

**In scope:**
1. a review form builder for yearly appraisals;
2. disciplinary cases;
3. engagement surveys, with results by team that are safe for small groups, and action plans;
4. people reports: turnover, hires against leavers, age, gender, length of service.

**Out of scope:**
- The e-learning player and on-the-job sign-off (owner, 2026-11-15, `WDGAP_DEFERRED.md` row 6).
- Form Studio and customers' own fields (deferred row 7). The review form builder must not grow into a general form builder.

**Binding for every builder:**
- The ledger conventions (`WDGAP_LEDGER.md`).
- White-label: the word "Odoo" never appears in anything a user sees or receives. "Payobook" never appears in a generic `biz_*` module (ledger QFM-1).
- Plain words and Lucide icons.
- vi and id `.po` entries for every new user-visible string.

---

## 0. Shared plumbing every S9 phase uses

| What | Where | Note |
|---|---|---|
| Talent hub lens registry | `pb_talent_hub/static/src/js/talent_hub.js:42` `TALENT_LENSES` | The rail today: Goals (`pb_goals/static/src/js/goals_palette.js:82`), Growth (`pb_pip/static/src/js/pip_palette.js:55`), Praise (`pb_rnr/static/src/js/rnr_palette.js:64`), Insights (`goals_palette.js:161`, lens `goal_numbers`). A new module adds its own tab from its own JS, so no shared file is touched. |
| People hub lens registry | `PEOPLE_LENSES` (doc at `pb_people_hub/static/src/js/people_hub.js:85`). Insights lens at `:131`, gated by `EMPLOYEE_GATE` (`:67`: records viewer, system, `hr.group_hr_user`, demo) | A lens declared with `under: "insights"` becomes a TAB inside People › Insights (`pb_hub/static/src/js/hub_shell.js:96`, `:333`; `subLenses` in `pb_insights/static/src/js/module_insights.js:30`). |
| Insights destinations table | `pb_insights_hub/static/src/js/insights_hub.js:105` `INSIGHT_DESTINATIONS` (a closed table); `registerModuleInsight` at `:114` | Do NOT add a key there: it is a shared file. Register straight into `pb_people_hub_lens` with `under: "insights"`, which gives the same result. |
| ⌘K palette | `registry.category("pb_hub_palette")`. Rows carry `groups`, `probe: {model, method}` and `requires` (precedent `pip_palette.js:69–110`) | `probe` means the server decides whether the door opens (`pb.pip.can_open`, `pb_pip/models/pb_pip.py:109`). |
| Product switches | `pb_hub/static/src/js/hub_features.js` (fails open) | Use `feature: "lifecycle"`, as Growth plans does. No new key is needed. |
| Settings card | `pb_settings/static/src/js/settings_hub.js:271` `SETTINGS_CATEGORIES`; groups at `:286` (use group `"hr"`) | Precedent `pb_hr_comm/static/src/js/comm_palette.js:103`. Each phase registers its OWN category key, so there is no collision. |
| Filter kit / quiet board | `pb_filter_kit` (used by pb_pip, pb_probation, pb_ask_hr). QuietGlance/QuietSteps live in `pb_import_kit` (memory `quiet-board-pattern`) | Analytics screens keep tiles. Work boards are quiet (grey at zero). Reference look: Growth plans (`pb_pip`) and Contracts (memory `lifecycle-colour-pass`). |
| My Payobook home card | `pb_me_portal/models/pb_me_home.py:328` `_pbme_extra_cards` (savepoint wrapper at `:314`) | Precedent: `pb_loans/models/pb_me_home.py:107` with template `pb_loans.pbme_card_loans`. The root class is `.pbme-home`, not `.pbme` (ledger PRB-W5). |
| My Payobook "Needs you" row | `pb_me_portal/models/pb_me_home.py:721` `_pbme_needs_extra(emp, put)` | Precedent `pb_me_team/models/pb_me_home.py:25`. |
| My Payobook page | Inherit `PbMePortal` (`pb_me_portal/controllers/portal.py:52`). The employee comes from the session only (`_ess_employee`, `:55`) | Precedent `pb_loans/controllers/portal.py:19`. Browser-walk every new portal page: under PRB-W5, a `t-att-*` `%` format broke a whole page. |
| My Payobook tiles | ONLY urls listed in `TILES` (`_TILE_ROWS` at `pb_me_home.py:94`, `_TILE_WORDS` at `:153`, used at `:309`). A stock `portal.portal_docs_entry` with an unknown url lands in "More" with a plain file icon (`TILE_DEFAULT`, `:209`) | A proper tile means editing pb_me_portal, which is the self-service team's file. See §6. |
| Approval engine | `biz.approval.chain.mixin` + `register_chain(...)`. Precedent: `pb_loans/models/loan_approval.py:24` (no `date_field`, ledger PRB-W1), process data at `pb_loans/data/approval_process.xml:7`. Verdict-style decision: `pb_probation/models/verdict_approval.py:174` `propose_verdict` | Context and detail are read under sudo (ledger W2B-2). |
| Approvals inbox, for work that is not an approval | Add-only seam: `pb_approval_config/models/inbox_extra.py:33` `_extra_items`, `:38` `_extra_counts` | WF2 tasks use it (`pb_lifecycle/models/workflow_inbox.py:17`). The inbox drawer only opens the kinds it was built for, so a new kind needs JS in pb_approval_config. S9 does not use this seam (see §3). |
| Access screen wording | `pb.role.ability` (`biz_access/models/pb_role_ability.py:42`), shipped as DATA by the module itself with `noupdate="1"`. Precedent: `pb_lifecycle/data/workflow_abilities.xml:3`. WF2 G80: once a role holds an ability, an upgrade that rewrites it fails | This avoids editing `pb_vendor_access/hooks.py` (`ROLE_ABILITY_GROUPS`, `:426`). |
| Workflow Studio | Lists every model that has a `company_id` and that the designer can read (`pb_lifecycle/models/workflow_studio.py:97–105`). A module declares itself, duck-typed, with `_workflow_capabilities()` (`:111`; precedent `pb_timeoff/models/workflow_contract.py:18`) | Declare it in the new module's own file. Raw survey answers must have no ACL, so Studio never offers them. |
| Who-sees-what (group) | `pb.group.scoped` in `pb_group/models/pb_group_visibility.py:440`; `_visible_companies` at `:444`, `_visible_departments` at `:459` | pb_explorer inherits it (`pb_explorer/models/pb_explorer.py`, class `PbExplorer`). |
| One person in two companies | `hr.employee.pb_person_id` (`pb_workseg/models/hr_employee.py:16`). The Explorer counts `COALESCE(NULLIF(person_id,0), employee_id)` (`pb_explorer.py:920`) | People reports must count a person once at group level. |
| Letters engine (a WF2-owned module) | `pb.letter.template` (`pb_lifecycle/models/letter.py:57`), `pb.hr.letter` (`:85`), `action_generate` (`:171`), `_make_pdf` (`:193`), `_file_in_vault` (`:220`). Letter types in `pb_lifecycle/models/lifecycle_common.py:71`. PDF in `pb_lifecycle/report/hr_letter_report.xml:8` | Use it only through `_inherit` / `selection_add` from a new module. PDF: render ONE record per call, because wkhtmltopdf on the server is unpatched (LEARNING LN33). |
| Translations | Modules with both vi and id files: pb_goals, pb_probation, pb_me_portal, pb_me_team, pb_offboarding, pb_loans, pb_lifecycle, pb_employee_vault. vi only: pb_pip, pb_ask_hr, pb_insights, pb_people_hub, pb_talent_hub, pb_hr_comm, pb_rnr | New modules ship `vi_VN.po` + `id_ID.po` (+ `.pot`), with three markers per entry and the parse gate (ledger convention 3; PRD-3: one-line msgids). |

---

## 1. Review form builder for yearly appraisals

### 1.1 What exists today

**Goal year:** `pb.goal.cycle` (`pb_goals/models/cycle.py:35`).
- It holds the dates and the half-way date.
- Review rules are added in `pb_goals/models/review.py:218`:
  - `mid_year_min_months` (`:220`);
  - `year_end_min_months` (`:226`);
  - `checkin_day` (`:232`);
  - `band_ids` (`:238`).
- States are at `goals_common.py:121`.

**Goal sheet:** `pb.goal.set` (`goal_set.py:42`). States are at `goals_common.py:140`.
- The manager is the employee's `parent_id` only (see the study row "second manager").
- Weights must total 100 (`WEIGHT_TOTAL`, `goals_common.py:276`).
- Score: key results are marked 0–5 (`SCORES`, `:246`), averaged per goal, then weighted per sheet (`scoring.py:165`).
- Self-rating scale: `RATINGS` (`:264`).

**Review:** `pb.goal.review` (`review.py:51`).
- Kinds are FIXED to `mid_year` / `year_end` (`REVIEW_KINDS`, `goals_common.py:195`).
- One review per sheet per kind (`review.py:55`). States are planned / done (`goals_common.py:201`).
- Content:
  - `manager_note`, required on write-up (`action_review_done` at `review.py:128`, refusal at `:142`);
  - `employee_note`;
  - `score_at_review`, frozen at write-up (`:96`).
- Only the manager or the goals HR lead may write it up (`_may_write_up`, `:121`).
- The manager gets one reminder (`_nudge`, `:175`).
- Which reviews apply is stamped once per sheet, and the employee gets a sentence explaining it (`_stamp_applicability` at `:313`, `_applicability_sentence` at `:365`).
- Score words come from the bands, `pb.goal.band` (`:445`).

**Who fills what:**
- The manager writes up in the backend Goals board: `pb.goals.write_up_review` (`pb_goals/models/pb_goals_year.py:230`), called from `goals_board.js:723`, drawer `pb_goals.GoalsDrawerYear` (`goals_year.xml:192`).
- The employee can only add "what I want said" before the write-up, through `/my/goals/review/<id>/say` (`pb_goals/controllers/portal.py:245` → `pb.my.goals.say_on_review`, `pb_my_goals_year.py:174`).
- Line managers keep the backend. Under TIERS, anyone with reports keeps a full account.

**Visibility:**
- The person and their manager can read review rows (`security/pb_goals_rules_b2.xml:85`).
- So can the employee's own login on its own (`:96`) and the goals HR groups (`:107`).
- Groups: Goals administrator / HR lead for goals / Head of goals (`security/pb_goals_security.xml:44/52/60`).

**Other fixed question sets.** These are precedents, not builders:
- probation colleague questions: `PEER_QUESTIONS` in `pb_probation/models/probation_common.py:83`, a list of `{key, type, label}`;
- lifecycle feedback by link: `pb.feedback.request` (`pb_lifecycle/models/feedback.py:31`), kinds at `:20`, with a fixed `questions_json`;
- growth-plan evaluation: `EVAL_QUESTIONS` (`pb_pip/models/pip_common.py`).

The only question editor HR can change is Learning's question bank, built on the standard survey question (`pb_training/models/question_bank.py:33`).

**Link to pay (QF4, live).** There is one seam: `pb.goal.set._pay_score()` (`pb_goals/models/pay_score.py:98`). A closed sheet uses its frozen copy (`:106`). The score goes through `pay_rating()` (`:43`).
- The pay review's "Read scores from Goals" reads it (`pb_pay/models/pb_pay_rating.py:265`; the call `sheet._pay_score()` is at about `:318`).
- Year close stamps it onto `pb_performance_rating` (`pay_score.py:116/130`). That field is owned by pb_pay (`pb_pay_rating.py:432`).
- pb_pip and pb_probation write the same field by probe (`pb_pip/models/pip_case.py:857`).

**No PDF of a review.** There is no `ir.actions.report` in pb_goals, pb_pip or pb_probation.

**Competencies:** none. Possible seeds:
- company values, `pb.company.value` (`pb_rnr/models/company_value.py:21`);
- `hr_skills`, installed wherever Learning is (`pb_training/__manifest__.py` depends on `hr_skills`).

### 1.2 What is missing
- An HR-built form per goal year, with sections for goals, competencies or values rated on the same 1–5 words, HR's own questions, and an overall section.
- The employee's self-review, done before the manager's.
- Manager answers per question.
- Section weights that produce an overall result.
- A "hide scores from the employee until …" option.
- Employee buttons "I have read this" and "I want to talk about it". In the study, the second one opens Ask HR.
- A PDF filed in the employee's documents.
- The overall result going into the pay review.

### 1.3 Precedent to clone
- **Build into the EXISTING review rows.** Do not make a second review object. A form attaches to the goal year; answers attach to `pb.goal.review`. The fixed mid-year and year-end moments stay.
- **Question schema:** the `PEER_QUESTIONS` shape (`{key, type: rating|text|choice, label}`). Rating words come from `RATINGS`/`SCORES`, so the employee's words and the manager's words match (comment at `goals_common.py:241`).
- **Builder screen:** a guided wizard in Settings (category group `hr`), with "Preview as the employee". The Announcements preview is the precedent (`pb_hr_comm`).
- **Acknowledgement:** `action_acknowledge` (`pb_pip/models/pip_case.py:584`) and `/my/growth/ack` (`pb_pip/controllers/portal.py:208`).
- **PDF and filing:** copy the shape of `pb.hr.letter._make_pdf` / `_file_in_vault` (one record per render), using the review's own `ir.actions.report`. Do not create `pb.hr.letter` rows: that model is owned by WF2 and every lifecycle user can read it (§2.4).
- **Pay:** in the new module, override `pb.goal.set._pay_score()` to return the overall result when the year has a form, and freeze the overall into the frozen copy at close. The pay review and the close stamp then both follow it, with NO change to pb_pay.
- **Frontend:**
  - an OWL `patch()` of `PbGoalsBoard`;
  - a `t-inherit` of `pb_goals.GoalsDrawerYear`;
  - a QWeb xpath on the pb_goals portal templates (`views/portal_templates_b2.xml`);
  - the controller class `PbGoalsPortal` (`pb_goals/controllers/portal.py:39`). It inherits `CustomerPortal`, not `PbMePortal`.

### 1.4 Risks
- **Privacy.** Once the manager's per-question scores are stored on a record the employee can read, `rule_review_portal` (`rules_b2.xml:96`) lets the employee read them. "Hide until" must therefore be a field-level `groups=` or a separate model, not a portal filter (ledger PRC-W1).
- **The write-up needs a note.** `action_review_done` requires `manager_note`. A form must still produce one, or let the overall comment fill it; otherwise the write-up is refused.
- **Pay suggestions change.** Changing what `_pay_score()` returns changes the pay-review suggestions for any year that has a form (owner question Q2). Years without a form must return exactly today's value; prove it with a golden test.
- **QF4-W4.** `action_close` is an xpath anchor (`goal_year_views.xml:446`). Never remove buttons in inherited views; hide them instead.
- **Stale Apps text (user-visible).** `pb_goals/__manifest__.py:68–69` still says "any link to pay … not here", which has been untrue since QF4. Fix it in this phase; pb_goals is S9-A's to touch.
- **PDF.** wkhtmltopdf on the server is unpatched, so render one document per call.

### 1.5 Modules a builder edits
- New: `pb_review_forms` (all new files).
- May touch: `pb_goals` (the manifest description line and a version bump only, if needed).
- Read only: pb_pay (no edit), pb_rnr (probe), pb_employee_vault (filing, no edit).

---

## 2. Disciplinary cases

### 2.1 What exists today

**Nothing disciplinary exists** in any `pb_*` model. A grep for "disciplin" finds only comments and one vault note (`pb_me_portal/models/employee_document_ext.py:6`).

**The closest record is the growth plan,** `pb.pip.case` (`pb_pip/models/pip_case.py:70`):
- seven stops (docstring at `:3–28`);
- nothing is written to the person until the plan starts;
- every write goes to the chatter;
- acknowledgement at `:584` and verdict at `:779`;
- letter: `_prepare_letter` at `:1073`;
- exit hand-off: `action_start_exit` at `:895` opens or reuses the leaving checklist.

**Growth plans have their own access ladder, granted by name.** This is the precedent to clone.
- Groups: HR — growth plans (`pb_pip/security/pb_pip_security.xml:39`) and Head (`:47`). There are no `implied_ids` from any lifecycle group (doc at `:4–22`).
- The person who asked sees only their own request, through a computed user field (rule at `:128`, field at `pb_pip/models/res_users_ext.py:43`).
- On borrowed lifecycle models, rules come in pairs: one "everything" rule and one narrow rule (`:157–222`).
- Access-screen roles are `growth-plans-hr` and `growth-plans-head` (`pb_vendor_access/hooks.py:449`).

**Employee side of growth plans:**
- the page `/my/growth` (`pb_pip/controllers/portal.py:132`);
- acknowledgement at `:208`;
- letter download, after proving the plan is theirs, at `:237`.

**Ask HR** is `pb.ask.hr.ticket` (`pb_ask_hr/models/ticket.py:71`).
- Its categories are fixed (`:37`) and there is no confidential flag.
- Every `hr.group_hr_user` reads every ticket (`security/pb_ask_hr_security.xml:29`).
- It is not a safe home for grievances or cases.

**Letters** are `pb.hr.letter`.
- The types are at `lifecycle_common.py:71`, and none of them is a warning.
- The body is a template with `${placeholders}` (`letter.py:38`).
- It makes a PDF and files it in the vault (`:171–255`), and sends through approval (`:257`).
- Only the `pip` type has the markup-placeholder hatch (`pb_pip/models/letter_ext.py`).

**Documents vault:** `pb.employee.document` (`pb_employee_vault/models/employee_document.py:52`), with categories at `:37`. There is no restricted flag. The only category flag is `ess_uploadable` (`pb_me_portal/models/employee_document_ext.py:17`).

**Employee timeline.** It lists approval history only for a FIXED list of models (`_APPROVAL_SOURCES` at `pb_employee_vault/models/employee_timeline.py:22`, used at `:135`). A new case model is not shown there unless someone adds it, which is a good default.

**Leaving:** `pb.resignation` (`pb_offboarding/models/resignation.py:54`).
- Reason: `departure_reason_id` (`:111`).
- An HR-only "Sorry to lose them" flag (`:120`).
- It stamps the employee record (`_stamp_employee_record`, `:437`).

### 2.2 What is missing
- A case record that runs from concern, through investigation or meeting and a hearing with minutes, to decision, letter, and appeal or close.
- A reasons list.
- Kinds of outcome: verbal warning, written warning, final warning, dismissal. Country words go in the pack notes.
- A "valid until" date on warnings.
- A history on the person.
- Restricted letters and documents.
- The employee's own copy and their reply.
- An optional hand-off from dismissal to the leaving checklist.

### 2.3 Precedent to clone
Clone growth plans end to end:
- **Access:**
  - its own ladder, with no implied lifecycle groups;
  - a computed user flag that the rules read (`res_users_ext.py:43`; domain pattern at `pb_pip_security.xml:136`);
  - a facade that re-checks access on every call.
- **Chatter:** only on its own record. Never post on `hr.employee`; far more people can read the person record.
- **Employee page:** acknowledgement, plus a letter download only after proving the case is theirs.
- **Talent lens:** with a `probe` (`pip_palette.js:55–66`).
- **Exit:** through `setup_offboarding()`. Copy `pip_case.py:895`, and probe for pb_offboarding.
- **Decision:** through the approval engine (`register_chain`, no `date_field`).
- **Letter types:** add them with `selection_add` on `pb.letter.template.letter_type`. New keys only: under WF2 G58, never relabel an existing key.
- **Access wording:** `pb.role.ability` data inside the module.

### 2.4 Risks — privacy (the main design issue)
1. **Letters leak to lifecycle staff.**
   - `pb.hr.letter` has an "everything" rule for every lifecycle user, manager and admin (`pb_pip_security.xml:210`), plus company rules (`pb_lifecycle/security/pb_lifecycle_security.xml:102–110`).
   - A warning letter stored as a `pb.hr.letter` is therefore readable by the whole lifecycle team.
   - **Fix:** the new module adds a GLOBAL rule (ANDed) on `pb.hr.letter` that limits discipline letter types to its own readers, using the computed user flag. Or it renders its own PDF from the template body without creating a `pb.hr.letter` row.
2. **The vault leaks to payroll staff.**
   - Every payroll officer and HR officer reads EVERY document (`pb_employee_vault/security/pb_employee_vault_security.xml:30`; ACL in `ir.model.access.csv:6–10`).
   - **Fix:** a category of its own (a data record), plus a GLOBAL rule on `pb.employee.document` that hides that category from everyone who is not a reader.
   - The Employee 360 drawer reads documents WITHOUT sudo (`pb_employee_vault/models/pb_people_360.py:78`), so the rule holds there too.
3. **The employee sees every one of their own documents on My Payobook.**
   - `/my/documents` reads under sudo (`pb_me_portal/controllers/portal.py:345`), so a filed warning letter WILL show to the person. That is usually right.
   - Hearing minutes and investigation notes must NEVER be filed in the vault.
4. **Approvers see the request detail in the Approvals inbox.** Keep `_approval_detail` to the outcome and the reason category, with no notes.
5. **Workflow Studio offers the case model to any designer who can read it** (`workflow_studio.py:103`). That is fine, because reading needs the discipline group. Declare `_workflow_capabilities`.
6. **Legal steps differ by country.** These are [U], not verified here:
   - Vietnam: a hearing with the employee and the union representative, written minutes, time limits, and warnings that lapse after a period.
   - Indonesia: warning letters SP1–SP3, each valid for up to 6 months.

   Ship generic steps plus country notes that HR can edit. The legal check is an owner item, not code.

### 2.5 Modules a builder edits
- New: `pb_conduct` (all new files). It depends on pb_lifecycle, pb_employee_vault, biz_approval_workflow, pb_talent_hub, pb_me_portal, pb_filter_kit, pb_import_kit and biz_access.
- No edits to pb_lifecycle, pb_employee_vault, pb_pip, pb_ask_hr or pb_offboarding (pb_offboarding is probed only).

---

## 3. Engagement surveys (results by team, small-group safe, action plans)

### 3.1 What exists today

**Anonymous shift rating:** `pb.shift.pulse` (`pb_ess_workforce/models/shift_pulse.py:76`). This is the privacy contract to clone:
- no employee link at all (docstring at `:4–48`);
- the row is written with `with_user(SUPERUSER_ID)`, not `sudo()` (`:160`). With sudo, `create_uid` would be the person;
- one rating per person per day, enforced by a salted hash plus a UNIQUE constraint (`_pulse_hash` at `:122`, constraint at `:98`). The salt sits in a system-only parameter;
- a server floor, `PULSE_FLOOR = 5` (`:65`). Below it the server returns NO figures (`get_pulse_tile`, `:219`);
- a 7-day window (`:69`).

**Gap:** HR managers and attendance officers can read the raw rows (date, department, comment) through the ACL (`pb_ess_workforce/security/ir.model.access.csv:2–3`). The floor protects only the tile.

**Other existing feedback, all named on purpose:**
- **New-joiner checks:** `pb.newhire.pulse` (`pb_onboarding/models/newhire_pulse.py`; see `:3–14`). Answered through an emailed token.
- **Exit questionnaire:** `EXIT_QUESTIONS` (`pb_offboarding/models/journey_case_ext.py`), one per leaver.

**Token pages for people with no login:** `/journey/f/<token>` (`pb_lifecycle/controllers/token_pages.py:139`) and `pb.feedback.request._token_url` (`feedback.py:89`). A per-person token identifies the person unless the answer row never stores it.

**The standard `survey` addon IS installed** wherever Learning is: `pb_training/__manifest__.py:76–77` depends on `survey` and `website_slides_survey`. Learning L0–L7 is live on all databases; sudima was cloned from the template. I did not check this on the server.

The standard survey tool does not fit anonymous engagement surveys:
- each answer stores the signed-in person's `partner_id` and `email` (`~/odoo19/odoo/addons/survey/models/survey_user_input.py:47–48`, filled in `survey_survey.py:563–571`);
- the results page `/survey/results/<survey>` (`controllers/main.py:731`) shows every answer to survey officers, with no minimum group;
- access is either "anyone with the link" or "invited" only (`survey_survey.py:92`);
- pb_training already overrides `survey.question` for EVERY question (`pb_training/models/question_bank.py:33`, write guard at `:142`). A module built on the survey tool would inherit Learning's library rules.

**Recommendation: a small model of our own,** copying the shift-pulse contract.

**Audience pickers to reuse:**
- announcements: `AUDIENCE_KINDS` (`pb_hr_comm/models/comm_common.py:133`; field at `pb_hr_comm/models/post.py:101`);
- required-training rules (`pb_training/models/requirement.py`).

**People with no email: "worker logins".** Employee (portal) logins are made in bulk; people sign in with their employee code, and first passwords are printed once (`biz_access/models/account_workers.py:7`, `create_worker_logins` at `:136`).

Tenant email is OFF on rize, sudima and p0clone, by the owner's choice (ledger convention 9). Invitations must work without email, through the Needs you row and the home card.

**Manager area on My Payobook:** `/my/team` (`pb_me_team/controllers/portal.py:37`).
- The page is built by `_team_page` (`:44`) with template `pb_me_team.portal_my_team` (`pb_me_team/views/portal_templates.xml:98`).
- Each section is isolated by `_pbmt_safe` (`:76`).
- Rize teams average 5.2 people, with a maximum of 16. None of the 40 rize managers has a login yet (memory `myteam-program`).

**Today board team pulse tile** (`pb_today`): this is the leave/time area and is not touched.

### 3.2 What is missing
- **Setting up:**
  - survey rounds: who, when, which questions, and reminders;
  - a question library in en/vi/id, with company values from Praise (`pb.company.value`) as an option;
  - HR's own questions (scale, choice, text);
  - eNPS.
- **Answering:** on My Payobook.
- **Results:**
  - participation %;
  - results by group (department, company, tenure band);
  - a configurable floor, applied on the server to EVERY number and comment;
  - protection against subtracting two overlapping groups;
  - a manager "Team voice" view.
- **Acting:** action plans linked to the results.

### 3.3 Precedent to clone
- **Answer storage:** copy `shift_pulse.py` exactly:
  - no employee field;
  - `with_user(SUPERUSER_ID)`;
  - a salted hash for "has answered this round", plus UNIQUE;
  - the salt in a system parameter.

  The answer stores only the group keys AS OF the round (company, department, tenure band, and so on), never the person.

  Give the raw answer model no ACL row for any user group. Only the results facade reads it, under sudo and behind its own gate. As a result, Workflow Studio never lists it and HR lists cannot show it.
- **Participation:** a count of hashes per group only. Nobody ever sees a per-person "has answered".
- **Results facade:** "below the floor, nothing" (the shape of `get_pulse_tile`, `:219`), for numbers AND comments. Add secondary suppression: if a parent group and all but one of its children are shown, hide one more.
- **Doors:**
  - a Talent lens "Voice" (own JS), a ⌘K row and a Settings card;
  - a My Payobook page, home card and Needs you row (hooks in §0);
  - a manager card added by QWeb xpath on `pb_me_team.portal_my_team`. Inherit it; do not edit it.
- **Action plans:** a small list of our own (owner, due date, which theme it came from), shown on the results page. The owner is told through their Needs you row and a standard to-do activity.

  Do NOT use WF2 workflow tasks: they live in `pb_lifecycle`, which WF2 owns, and they are tied to workflow runs. Do not use the inbox seam either: its drawer cannot open a new kind without pb_approval_config JS.
- **Optional invitation as an announcement:** probe `pb.hr.comm.post`. No dependency is needed.

### 3.4 Risks — privacy first
- **`sudo()` stamps `create_uid`.** This is the shift-pulse lesson and the single most likely leak.
- **Time stamps identify people.** `create_date`, plus a department, plus a small team gives a name. Use the floor and "latest round" grouping only, with no per-day breakdown.
- **Free-text comments identify people** through writing style and details:
  - show comments only above the floor, and to HR only by default (owner Q4);
  - PayAI comment summaries are a later item.
- **A floor of 5 hides most single-manager teams,** because teams are about 5 people. The owner must know this before choosing (Q4).
- **Tenure and age bands multiply small cells.** Offer only department and company groupings in the first build. Add tenure band only where every cell passes the floor.
- **A system administrator can always work out who answered** (salt plus the employee table), as the shift-pulse docstring says. Say so in the help text; do not promise "nobody can ever know".
- **Staff with no login.** Kiosk answering belongs on the clock-in screen (pb_clock, the leave/time team's module). It is not in S9 (Q5).

### 3.5 Modules a builder edits
- New: `pb_voice` (all new files).
  - Depends on pb_me_portal, pb_me_team (template inherit), pb_talent_hub, pb_settings, pb_import_kit, pb_filter_kit and biz_access.
  - Probes pb_rnr and pb_hr_comm.
- No edits to pb_ess_workforce, pb_onboarding, pb_training, survey, pb_me_portal or pb_me_team.

---

## 4. People reports (turnover, hires against leavers, age, gender, length of service)

### 4.1 What exists today

**Explorer (`pb_explorer`).** Its facts are PAYROLL only:
- `pb.fact.run` (`pb_explorer/models/pb_fact.py:49`);
- `pb.fact.line` (`:138`): run × component;
- `pb.fact.emp` (`:187`): run × employee × component type, with department and job as of the period end, via `_ASOF_JOIN` on `hr_version` (`pb_fact_builder.py:56`).

What it can show:
- **Measures:** `_MEASURES` (`pb_explorer.py:67`). "People" is a distinct person count (`:87`).
- **Dimensions:** `_DIMENSIONS` (`:119`). There is no gender, age, tenure or location.
- **Lenses:** `_LENSES` (`:316`), including "Workforce Movement" (`:325`).
- **Movement:** joiners and leavers between two runs, in `_waterfall` (`:2496`).

How it works:
- **Gate:** the payroll analytics groups (`_GATE_GROUPS` at `:46`, `_require`).
- **Scope:** company scope plus who-sees-what, in `_co_ids` (`pb.group.scoped`).
- **Financial-year start:** `_fy_start_month` (`:1410`). The group setting is `pb_group/models/pb_group.py:71`, with `fiscal_year_start` at `:135`.
- **Builder job:** `cron_build` (`pb_fact_builder.py:846`).

**Workforce insights** (`pb_workforce_insights/models/pb_workforce_insights.py`):
- headcount by month (`_headcount`, `:190`);
- joiners and leavers between the last two months, on a PAYROLL basis (movement at `:206–231`);
- its docstring says HR leaving dates were not kept up to date (`:193–195`);
- it uses the same payroll gate (`:43`).

**Module insights, area "people"** (`pb_insights/models/module_insights.py:63`):
- it counts active records, running contracts, and first contracts started;
- these are today's status only, and former employees are excluded (`:73`);
- its rule is "a snapshot never invents a historical series from today's status" (`:61`);
- the gate for "people" is system, `hr.group_hr_user`, records viewer, and demo (`_allowed`, `:201`);
- it is drawn as People › Insights (`people_hub.js:131`).

**Source fields (Odoo 19):**
- **On the version record** (`~/odoo19/odoo/addons/hr/models/hr_version.py`):
  - gender is `sex` (`:81`, HR-only);
  - `departure_date` (`:148`) and `departure_reason_id` (`:145`), both HR-only;
  - `date_version` (`:64`), `department_id` (`:127`), `job_id` (`:130`) and `contract_date_start` (`:156`).
- **On the employee record:**
  - `birthday` (`hr_employee.py:134`, HR-only);
  - joining date `date_of_joining` (`pb_hr_payroll_formula/models/hr_employee.py:31`).

  The precedent order for a start date is joining date, then first contract, then contract start (`hr_payslip_formula.py:1375`; see the PR2 facts).
- **Leaving reason categories:** the standard `hr.departure.reason` (resigned / fired / retired), set by Offboarding (`resignation.py:111`, stamped at `:437`).
- **Archived leavers** need `active_test=False`.

**Nothing computes** turnover rate, the voluntary/involuntary split, age bands, tenure bands or gender mix anywhere. A grep for "diversity" and "tenure band" finds nothing.

### 4.2 Figures: available now vs new facts needed

| Figure | Today | Needs |
|---|---|---|
| Paid headcount by month, payroll basis | yes (Explorer People, Workforce insights) | — |
| Joiners / leavers between two pay runs | yes, payroll basis only | — |
| Headcount including people not on payroll, month by month | no (today-only snapshot) | month-end people snapshot |
| Hires vs leavers per month, HR basis | no | snapshot events (joined / left) |
| Turnover % (leavers ÷ average headcount), voluntary vs not | no | snapshot + leaving reason kind |
| Leavers by department / tenure band / reason | no | snapshot |
| Age bands, gender mix, length-of-service bands | no | snapshot (bands only, never raw birthdays in the report) |
| Moves (department/job changes) | no | snapshot diff month to month (from `hr.version`) |

### 4.3 Precedent to clone

**A new small fact table:** one row per person per month-end.
- Each row holds: company, person key, department, job, location, gender, age band, tenure band, employee type, that month's events (joined / left / moved), and the leaving reason kind.
- A monthly job fills it, and a BACKFILL fills the past from `hr.version` history plus leaving dates. The as-of logic is the same as `_ASOF_JOIN`.
- It follows the same doctrine as the Explorer facts:
  - only its builder writes it;
  - reads never write;
  - numbers reconcile: the snapshot count at a month-end equals the active records that day.

**The board:**
- its own read-only facade: gate first, then sudo; company scope via `pb.group.scoped`; each person counted once via `pb_person_id`;
- drawn as a tab under People › Insights (`under: "insights"`);
- analytics look (tiles allowed), with an Excel download like QF2;
- five starting views: Headcount & turnover, Hires vs leavers, Why people leave, Age & gender, Length of service.

**Floor:** every cell under 5 people shows as hidden, with the matching secondary suppression. Same rule as §3.

**Group rules:** a move between two companies of one group is a move at group level, but a leaver plus a joiner at company level. Say which one on screen.

### 4.4 Risks
- **HR-only fields.** Gender, birthday and leaving reasons are HR-only. A payroll-analytics audience must not get them through a new door (Q6). Adding new measures to the Explorer (`pb_explorer.py:67/119/316`) would put them behind the PAYROLL gate, so that is not part of this step.
- **Data quality.** Rize has leavers still marked active and joiners only half set up (memory `rize-vn-headcount-gaps`). HR-basis turnover will under-count until that is fixed. Show a "paid last month, not this month" cross-check line beside it.
- **Backfill size.** Rize and payobook have many versions × months. Cap and chunk the work like `cron_build`, and report what is still pending; never show it as zero.

### 4.5 Modules a builder edits
- New: `pb_people_reports` (all new files).
  - Depends on pb_people_hub, pb_insights, pb_group, pb_import_kit and hr.
  - Probes pb_workseg and pb_offboarding.
- No edits to pb_explorer, pb_insights, pb_insights_hub or pb_workforce_insights.

---

## 5. Proposed split — three builders at the same time

| Phase | Builds | Owns (may edit) | Size |
|---|---|---|---|
| **S9-A Review forms** | §1: a form builder per goal year, self-review on My Payobook, manager answers in the Goals drawer, section weights that give an overall result, the hide-until option, acknowledgement, a PDF filed in documents, and the overall result into pay (via `_pay_score`) | new `pb_review_forms/**`; `pb_goals/__manifest__.py` (description lines 68–69 + version) only if needed | L |
| **S9-B Conduct + People reports** | §2 disciplinary cases (`pb_conduct`) and §4 people reports (`pb_people_reports`). These are two independent new modules for one builder, or two builders if there is capacity; they share no file | new `pb_conduct/**`, new `pb_people_reports/**` | M + M |
| **S9-C Employee voice** | §3: survey rounds, a library in en/vi/id, answering on My Payobook, anonymity and the floor, results by group, a manager card on /my/team, and action plans | new `pb_voice/**` | L |

**Working apart:**
- No S9 phase edits a file that another S9 phase owns.
- Each phase registers its own:
  - Talent or People lens and ⌘K rows;
  - Settings category key (`reviews`, `conduct`, `voice`, `people_reports`);
  - abilities, as data;
  - `.po` files.
- Each phase keeps its own scratch folder (ledger QF3-1).

**Deploy:** one deploy agent ships all three. The new modules are installed with `-i` on all five databases. Use the risky tier, because of the new security rules.

---

## 6. Collision list (files outside the new modules)

| File / area | Owner | S9 use | Plan |
|---|---|---|---|
| `pb_lifecycle/**`: workbench `static/workflow/*.js`, `static/src/js/workflow_studio.js`, `controllers/`, `i18n/vi_VN.po`, `i18n/id_ID.po`, `.pot`, `__manifest__.py` | WORKFLOW-2 P6b (building now: the Studio editor in vi/id) | S9-B uses `pb.hr.letter` / `pb.letter.template` through `_inherit` + `selection_add`, and adds global rules from its own module | **Never edit any file under `pb_lifecycle/`.** |
| `pb_me_portal/models/pb_me_home.py` `_TILE_ROWS` (`:94`) / `_TILE_WORDS` (`:153`), plus the pb_me_portal `.po` | self-service team | proper tiles for `/my/conduct` (B) and `/my/voice` (C) | Optional. Without it, the pages show in "More" with a plain icon. If wanted, it is one 2-row change, made by the self-service builder or by the S9 deploy agent at merge. |
| `pb_me_portal` hooks `_pbme_extra_cards` (`:328`), `_pbme_needs_extra` (`:721`), `PbMePortal` (`controllers/portal.py:52`) | self-service team | B and C inherit them | No edit. Ask the self-service team not to rename these hooks. |
| `pb_me_team/views/portal_templates.xml:98` `portal_my_team` | self-service team | C inherits it by xpath for the "Team voice" card | No edit. Agree a stable anchor: if that template's structure changes, C's xpath breaks. |
| `pb_goals/**` | S9-A | A | Only S9-A. |
| `pb_pay` (pay review, `pb_pay_rating.py:265`) | job-changes / pay scales team | A changes only what `pb.goal.set._pay_score()` returns | No pb_pay edit. Tell that team the read path stays `sheet._pay_score()`. |
| `pb_contracts`, `pb_workforce*`, `pb_contract_lifecycle` | job-changes team | people reports read moves from `hr.version` | No edit, read only. If they add a "change job" event record, people reports can read it later. |
| `pb_timeoff`, `pb_clock`, `pb_schedule`, `pb_attendance_flow`, `pb_ess_workforce`, `pb_today` | leave/time team | none (a kiosk survey is not in S9) | No edit. |
| `pb_vendor_access/hooks.py` (role bundles at `:426`) | shared | avoided: abilities ship as data | No edit. |
| `pb_insights_hub/static/src/js/insights_hub.js:105` | shared | avoided: register under People › Insights directly | No edit. |
| `pb_employee_vault`, `pb_ask_hr`, `pb_pip`, `pb_offboarding`, `pb_explorer` | — | read, inherit or probe only | No edit. |

---

## 7. Owner questions (plain words; recommended option first)

**Q1. When a manager does the end-of-year review, what should the review form hold?**
- (Recommended) One form per goal year for the whole company. It holds the goals score, a few skills or company values rated from "Well below" to "Well above", and up to about eight questions HR writes. The employee gives their own view first, then the manager, then an overall comment. Easy to run; every team is reviewed the same way.
- The same parts, but HR can make a different form for each department or job. Fits a mixed workforce; more set-up, and results are harder to compare across teams.
- Keep today's review (goals score and a written note) and only add the employee's own view. Quickest; HR still cannot add its own questions.

**Q2. Once a year has a review form, which result should the pay review start from?**
- (Recommended) The overall review result: goals and the other parts, mixed by the shares HR sets on the form (for example 70% goals, 30% skills). Pay follows the whole review.
- The goals score only, as today. The other parts are for the conversation only.
- HR chooses for each goal year.

**Q3. Who may see disciplinary cases (concerns, hearing notes, decisions, warning letters)?**
- (Recommended) Only the people HR names by hand on the Access screen, as with growth plans today. The employee sees only their own finished letters on My Payobook and can reply; they never see the notes. Their line manager sees nothing unless named.
- Everyone in the HR team.
- The named HR people, plus each employee's line manager for cases about their own team.

**Q4. How private should engagement survey answers be?**
- (Recommended) Fully anonymous: nobody, not even HR, can see who answered what. Results appear only for groups of 5 people or more. Written comments appear only for groups of 5 or more, and only to HR. Because teams average about 5 people, many managers will see their department's results rather than their own team's.
- Anonymous, but results appear from 3 people. More managers see their own team; it becomes easier to guess who said what.
- Confidential: HR can see each person's answers; managers see only groups of 5 or more. HR can follow up a worrying answer; people may answer less honestly.

**Q5. How do staff with no My Payobook login answer a survey?**
- (Recommended) Only on My Payobook. Staff without email get a login made in bulk, with printed sign-in slips; this already exists on the Access screen. Answers stay anonymous.
- Also on a shared tablet at the site, where a person types their employee code. Reaches everyone, but it belongs on the clock-in screen another team is building, so it would come later.
- Paper forms that HR types in. Reaches everyone now; HR handles the papers, so the answers are not anonymous to HR.

**Q6. Who should see the people reports (turnover, joiners against leavers, age, gender, length of service)?**
- (Recommended) HR staff, for the companies they can already see. Any group smaller than 5 people shows as hidden.
- Also the payroll team who use the Explorer today.
- Also line managers, for their own team only (small teams will mostly show as hidden).

**Defaults taken without asking.** State these in the step report:
- Discipline steps are generic, with country notes HR can edit. The legal check per country is an owner item.
- Survey action plans are a simple list of our own, not workflow tasks.
- People reports are their own tab under People › Insights, not new Explorer measures.
- Turnover counts the leaving dates on the employee record, with a "paid last month, not this month" cross-check.
- Surveys are a small module of our own, not the standard survey tool.

---

## 8. New gotchas for the ledger (S9-F rows)

| # | Gotcha |
|---|---|
| S9-F1 | Every lifecycle user, manager and admin can read `pb.hr.letter` (`pb_pip/security/pb_pip_security.xml:210`). A sensitive letter type needs a GLOBAL rule from its own module, or no `pb.hr.letter` row at all. |
| S9-F2 | The documents vault lets every payroll officer and HR officer read every document (`pb_employee_vault/security/pb_employee_vault_security.xml:30`). `/my/documents` shows the employee every one of their own documents, under sudo (`pb_me_portal/controllers/portal.py:345`). To restrict documents, put a global rule on a category, and never file notes there. |
| S9-F3 | The shift rating's floor protects only the tile: HR managers and attendance officers read the raw rows through the ACL (`pb_ess_workforce/security/ir.model.access.csv:2–3`). Raw anonymous answers get NO ACL row for any user group. |
| S9-F4 | The standard survey tool stores the signed-in person's contact and email on each answer (`survey/models/survey_user_input.py:47–48`). Its results page has no minimum group (`survey/controllers/main.py:731`). Learning overrides every `survey.question` (`pb_training/models/question_bank.py:33`, `:142`). |
| S9-F5 | Odoo 19 field locations: gender is `sex` on `hr.version` (`hr/models/hr_version.py:81`); the leaving date and reason are version fields too (`:145/:148`); `birthday` is on the employee (`hr_employee.py:134`). All are HR-only. Read them through the ORM or `hr_version` explicitly. Archived leavers need `active_test=False`. |
| S9-F6 | My Payobook home tiles come only from pb_me_portal's `TILES` (`pb_me_home.py:309`). Any other url becomes a plain "More" tile. |
| S9-F7 | `INSIGHT_DESTINATIONS` (`pb_insights_hub/static/src/js/insights_hub.js:105`) is a closed table. A new Insights tab registers straight into the hub's lens registry with `under: "insights"`. |
| S9-F8 | `pb_goals/__manifest__.py:68–69` (Apps list text, which users can see) still says the module has no link to pay. That has been untrue since QF4. |
| S9-F9 | Workflow Studio offers every model with a `company_id` that the designer may read (`pb_lifecycle/models/workflow_studio.py:97–105`). A new sensitive model is safe only if its ACL is narrow. |
