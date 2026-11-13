# RECRUIT — Phase 1: the role board, Rize's stages, the non-blocking rule

Owner approved the gap register (`docs/design/rize-recruit-gap.html`) and the
experience blueprint (`docs/design/rize-hiring-experience.html`) on 2026-09-30 and
mandated the phased workflow. This phase builds the part Anita asked for first:
**"I need the pipelines configured first. I need the jobs configured first."**
It delivers register lines **G-03, G-04, G-05, G-06, G-07, G-09, G-10 (shell), G-11,
G-24, G-25, G-34, G-49** — the drag-and-drop board per role, Rize's stage set with
per-role visibility and department + country presets, every gate removed except the
offer rule, the Talent lead rename, the stock Recruitment menus hidden, the candidate
drawer with a Next box and a timeline, and the Hiring set-up door with its Stages card
live.

Read first, in order: `docs/handovers/recruit/RECRUIT_LEDGER.md` (all of it — it
inherits the RIZE ledger's rules, ritual and gotchas), `docs/design/rize-hiring-experience.html`
(open it in a browser; the board mock is the target), the register lines named above,
then this file. Everything marked **verified** below was checked on 2026-09-30 against
the repo — do not re-derive it.

---

## 0. Scope and binding non-goals

**In scope (P1):**
1. `pb_hiring` **19.0.2.0.0** (a major bump: the stage set changes) with a migration.
2. Rize's stage set as the product default (RC-D2): rename, reorder, add `shortlist`
   and `post_offer`, keep `reference` as hidden-by-default, retire the six stock stages
   idempotently (RC5), clear the stock acknowledgement template (RC9).
3. A one-line **meaning** per stage (shown on hover on the column name; editable by the
   Talent lead).
4. **Per-role visible stages** (`pb_visible_stage_ids` on the role) + **presets** by
   department × country (`pb.hiring.stage.preset`) + the Stages card in the new
   **Hiring set-up** screen (list with inline rename, drag reorder, meaning; the preset
   matrix; "Preview as a board").
5. **The role board**: open a role → columns = its visible stages, cards = candidates,
   `useSortable` drag between columns and onto the Closed rail, multi-select with a
   floating bar, Undo toast, per-role quiet numbers line, column captions, empty-column
   sentences, first-visit hints, keyboard.
6. **The candidate drawer** over the board: hero, Next box, timeline (stage log + emails
   + notes + interviews + first look), interviews & opinions summary, documents, quick
   actions (Advance / Move to / Email / Not this time / Open the full record).
7. **Gates removed** (RC-D5): stage-move rules in `journey.py:78-90` and
   `_act_journey_stage` (reason optional, on-hold date optional, `offer` and `post_offer`
   allowed), `action_mark_done` no longer refuses while opinions are pending (prompt
   instead), the "select in the debrief before drafting an offer" rule stays for now (P3
   owns offer gating; do not touch `offer.py` beyond what §4.6 says).
8. **Who moves** (RC-D1): only `_can_recruit` users may move; a line manager gets the
   board read-only with notes.
9. **Talent lead rename** (RC-D2): group name, Access catalogue row + Vietnamese, the
   words on screen. `pb_vendor_access` **19.0.1.11.0** with a migration (RC12).
10. **Hiring home** restyled to the blueprint (role cards with the mini funnel in stage
    order, the Next sentence, "Open a role" / "Ask a manager" buttons — the latter two
    are P3 features: in P1 "Open a role" opens the existing raise wizard, "Ask a manager"
    is NOT shown yet).
11. Stock Recruitment menus hidden (RC15). ⌘K rows in the **4000** block.
12. Demo data on `payobook` only: two Talent lead / line-manager logins and ~28 demo
    candidates spread across the stages of the open demo roles so the board reads like
    the blueprint mock (RC-D7). Registered with `pb.demo.seed`.
13. Tests (numbered in §5), deploy to **payobook, rize (INSTALL), payobook_template**
    (RC-D4), Chrome validation light + dark on payobook.com, phase report.

**Binding non-goals (later phases own these — do not start them):** the application
form builder and languages (P2); roles without requests, "Ask a manager", budget flag,
JD sharing, the explicit offer rule (P3); Share-with control, money masking, private
recruiter notes, Resume bank tab, consent/retention (P4); scorecard templates, Calendly
rule, Google Calendar (P5); Post-offer countdown, joining confirmation, pre-joining tasks
(P6); channels, agency portal (P7); email languages, automations list (P8). Do not
rebuild the Interviews tab (only the `mark_done` gate changes). Do not touch
`hiring_numbers.*`. Do not add a rail item. Do not modify `vendor_license_core`.

---

## 1. Verified plumbing facts (do not re-derive)

### 1.1 The board today (`pb_hiring/static/src/js/hiring_board.js`, 1293 lines; `static/src/xml/hiring_board.xml`, 1597 lines; `static/src/scss/hiring.scss`, 1127 lines)
- Component `PbHiringBoard` (js:98), template `pb_hiring.PbHiringBoard` (xml:29), registry
  tag `pb_hiring_board` (js:1293). Icons via `import { ic } from "@pb_import_kit/js/import_icons"`
  (js:35), wrapped as `this.ic(n,s)` (js:201), used as `<t t-out="ic('mail',13)"/>`.
- `load()` (js:224-268) calls `orm.call("pb.hiring","get_board",[])` then
  `journey_options` → `state.journey` (stages `[{id,key,name,outcome}]`, `message_fields`,
  `managers`, `users`, `countries`, `currencies`, `company_sections`).
- Every write: `act(verb, payload)` → `orm.call("pb.hiring","act",[verb,payload])`
  (js:528-545); an `ir.actions.act_window` result is `doAction`ed; `note` shows a toast;
  `refresh()` (js:270) reloads unless `reload:false`.
- Drawer: `openDrawer(id)` (js:501-513) → `orm.call("pb.hiring","get_requisition",[id])`;
  sections `candidates` (xml:878-935), `request` (:743), `jd` (:800), `offer` (:498).
- Move stage today: `startStageMove(cd)` (js:587) → inline `<select>` dialog (xml:1595,
  `offer`/`joined` disabled) → `saveStageMove` → `act("journey_stage", {applicant_id,
  key, reason, update_date})`.
- Email candidate: `startMessage(cd)` (js:589), `previewMessage` (js:593 →
  `act("message_preview")`), `sendMessage` (js:597 → `act("message_send")`).
- Journey chips: `JOURNEY_STAGES` (js:40-45) keys request/publish/recruit/joined;
  `stageOf(r)` (js:328-335); `get stages` (js:337-350); `glance` (js:396-411, 10 items
  from `kpis`); `nextStep(r)` (js:425-467); `chooseJourney` (js:586); `filtered`
  (js:279-315). These are ROLE-level and stay (RC2).
- Interviews tab (xml:324-452) reads `state.interviews` from `get_board`; actions
  `reschedule`, `no_show`, `mark_done`, `debrief`, `open_interview`, `run_reminders`.
- Inline dialogs are state-driven scrims: raise (xml:1009), writingJd (1036), moving
  (1071), scheduling (1114), rescheduling (1193), noShowing (1245), debriefing (1284),
  rejecting (1324), noting (1363), overriding (1400), lineForm (1431), letter (1485),
  signing (1518), coverForm (1552).
- **RC1**: `togglePanel` defined twice (js:801 and js:1006) — fix while you are there.
- Styles: `.pbhr` root at scss:44, drawer :339, `.pbhr-glance`/`.pbhr-gl` :977-1005,
  `.pbhr-steps4`/`.pbhr-st` :1008-1068, `.pbhr-stage-chip` :938. Tokens used are the
  kit's `--pbim-*` (`pb_import_kit/static/src/scss/import_tokens.scss:8-50`): `--pbim-primary`
  #5A4BB0, `--pbim-primary-hover` #4A3D96, `--pbim-primary-dark` #241F52, `--pbim-soft`
  #EDEAF8, `--pbim-ink` #1B1733, `--pbim-muted` #64748B, `--pbim-line` #E2E8F0,
  `--pbim-line-2` #F1F5F9, `--pbim-surface` #fff, `--pbim-bg` #F5F6FA, `--pbim-green`
  #2E7D4F / `-soft` #E3F2E9, `--pbim-amber` #D97706 / `-soft` #FEF3C7, `--pbim-rose`
  #DC2668 / `-soft` #FCE7EF, `--pbim-cyan` #2563EB, `--pbim-ring` rgba(90,75,176,.18),
  radii `--pbim-r` 14px / `-sm` 10px / `-lg` 18px, shadows `--pbim-sh`, `--pbim-sh-lg`.
  Root class `pbim pbim-page pbhr`. Font Inter (kit). Dark mode: the kit has no dark
  palette product-wide (wave-2 finding) — design your dark tokens under
  `.pbhr` for the new surfaces and keep them legible; do not attempt a kit-wide dark theme.
- Assets (`__manifest__.py`): `web.assets_backend` = hiring.scss, hiring_numbers.scss,
  hiring_board.js, hiring_numbers.js, hiring_palette.js, hiring_board.xml,
  hiring_numbers.xml; `web.assets_frontend` = portal_hiring.scss. Version 19.0.1.3.5.

### 1.2 Server facade (`pb_hiring/models/pb_hiring.py`, AbstractModel `pb.hiring` :52; A3 overrides in `pb_hiring_a3.py`)
- Permission: `_can_read` :79 (any hiring group or `requisition._can_raise(user)`; cover
  users via `pb_hiring_a3.py:45`), `can_open` :86, `_can_write` :94 (manager|admin),
  `_can_admin` :99, `_can_recruit` :103 (user|manager|admin; A3 :59 adds cover),
  `_require_recruit` :125 (A3 :79), `_require_write` :134.
- `get_board(limit=None)` :146 (A3 :118): keys `allowed, can_write, can_recruit,
  can_admin, can_raise, kpis, rows, departments, countries, recruiters, states, role_types,
  budget_states, screen_tags, rule_count, total, capped, interviews, interview_states,
  modes, step_kinds, no_show_reasons, delay_kinds, decisions, recommendations` + A3
  `offer_rows, agencies, covering, offer_states, bgv_results, offer_kinds, offer_periods`.
  `BOARD_LIMIT = 300` :41. Empty shape `_empty_board` :208.
- Row `_row` :229-296: `id, name, title, role_type, department(_id), country(_id),
  location, headcount, state, state_label, waiting, waiting_mine, budget_*, currency,
  recruiter(_id, _avatar), requested_by, jd_state, jd_count, published, referral_open,
  referrals, candidates, pipeline [{id,name,count}] (from _pipeline :320), days_open,
  target_start_date, rank`; `journey.py:304` adds `target_close_date`.
- `get_requisition(id)` :440 (A3 :201): `_row` keys + `steps, panel_people, jds,
  postings, referrals, candidates_list, other_jobs, refuse_reasons` (+ A3 `agency*,
  filled_count, offer_out_count, letter_templates, cover, journey, offers`).
  Candidate shape `_candidates` :518-560: `id, name, email, stage, stage_seq, source,
  screen, screen_label, status, active, interviews, next_interview, rounds, selected`
  — **no `stage_id` / `pb_key`** (RC3).
- `act(verb, payload)` :588 dispatches to `_act_<verb>` (:602-903, `journey.py:309-421`,
  `pb_hiring_a3.py:446+`). `_act_journey_stage` `journey.py:365-385`: `check_access('write')`
  + `_require_recruit`; needs a `pb_key`; REFUSES `offer`/`joined`; requires `reason` for
  OUTCOMES and `update_date` for `on_hold`; writes `stage_id, pb_stage_reason,
  pb_hold_until`; `message_post`; returns `{id, note}`.
- Interview row `_interview_row` :361-407 has `bucket` ∈ today/week/later/past/late/awaiting.

### 1.3 Stages (`pb_hiring/models/journey.py`)
- `STAGES` :11-20 (sequence = (index+1)*10): `screening` 10 "Screening", `panel_review`
  20 "Panel Review", `phone` 30 "Recruiter Phone Call", `assignment` 40, `discussion_1`
  50, `discussion_2` 60, `discussion_3` 70, `reference` 80 "Reference Check", `offer` 90
  "Offer Stage", `joined` 100, `cv_reject` 110, `interview_reject` 120, `drop_out` 130,
  `on_hold` 140, `offer_drop_out` 150. `OUTCOMES` :21.
- `hr.recruitment.stage.pb_key` Selection :53. `_ensure_journey_stages` :56-61 (fold =
  outcome; `hired_stage` = joined) called by `seed_journey` :424 from
  `data/journey_seed.xml`.
- `hr.applicant.write` :78-90 (the gates to remove), `create` :93 (defaults to
  `screening`), `_pb_next_stage` :100 (skips `assignment` unless `pb_assignment`),
  `_pb_shortlist` :114 (→ `panel_review`), `_pb_reject` :122 (→ `cv_reject` /
  `interview_reject`). Stage-log hook `hr_applicant_ext.py:54-85` (reads old stage, calls
  `pb.hiring.stage.log.note_move` inside a savepoint). `pb.hiring.stage.log` fields
  `stage_log.py:26-73`: `applicant_id, job_id, requisition_id, from_stage_id,
  to_stage_id, at, by_user_id, company_id`; `note_move` :58.
- First look: `hr_applicant_ext.py:30-49` `pb_screen` Selection (Shortlisted / Not this
  time / Worth keeping in touch with / Better suited to another role), `pb_screen_on`,
  `pb_screen_by`, `pb_other_job_id`; the talent-pool add at :141-153.
- `pb.hiring.step` `requisition.py:51-83` (`stage_id` optional m2o); `_act_create`
  `journey.py:330-339` links Discussion steps to `discussion_1..3`.
- Stock `hr.recruitment.stage` (`hr_recruitment/models/hr_recruitment_stage.py`):
  `job_ids` m2m :15, `template_id` :19, `fold` :22, `hired_stage` :25,
  `rotting_threshold_days` :27, `legend_*` :29-36, **no `active`** (RC5). Stock seed
  stages: New, Qualification, First Interview, Second Interview, Contract Proposal,
  Contract Signed (`hr_recruitment/data/hr_recruitment_data.xml:44-66`; "New" carries the
  acknowledgement template :44-46).
- Stock `hr.applicant`: `stage_id` computed/stored with `group_expand` :78-82;
  `date_last_stage_update` :92; `write` :650-671 maintains last-stage bookkeeping (RC10);
  `_track_template` :875-889.

### 1.4 Hub, lenses, palette, access
- `pb_hiring/static/src/js/hiring_palette.js`: Lifecycle lens "hiring" :50-63 (icon
  `userPlus`, `Component: PbHiringBoard`, `groups: LIFECYCLE_GATE + 3 hiring groups`,
  `probe {model:"pb.hiring", method:"can_open"}`, sequence 10); Insights lens :80-94;
  `SETTINGS_CATEGORIES` :119-150 (sequence 40); palette entry `hiring_board` :155-165
  (`requires:"pb_hiring_board"`, `action {xmlid:"pb_lifecycle.action_pb_lifecycle_hub",
  lens:"hiring"}`, sequence 3500).
- Lens schema `pb_hub/static/src/js/hub_shell.js:67-88`; gates `hub_gates.js:35-60`;
  palette entry schema `hub_palette_entries.js:5-18`; Lifecycle hub config
  `pb_lifecycle/static/src/js/lifecycle_hub.js:51-94`.
- Groups `pb_hiring/security/pb_hiring_security.xml`: `group_hiring_user` "Recruiter"
  :40-46 (implies `hr_recruitment.group_hr_recruitment_user`), `group_hiring_manager`
  "Hiring manager" :48-54 (implies user + `hr_recruitment.group_hr_recruitment_manager`),
  `group_hiring_admin` "Head of hiring" :56-65; privilege :34. pb_hiring has NO record
  rule on `hr.applicant`; stock rules (`hr_recruitment/security/hr_recruitment_security.xml`
  :49-67) let interviewers see applicants they are named on and recruitment users see all.
  pb rules come in own/all pairs (requisition :225/:232, stage_log :199/:206, interview
  :153/:160).
- Access catalogue `pb_vendor_access/hooks.py` rows :142 `hiring-recruiter`, :147
  `hiring-manager`, :151 `hiring-head`; group map :431-433; `ensure_catalogue` :955;
  migration pattern `pb_vendor_access/migrations/19.0.1.10.0/post-migrate.py`
  (`migrate(cr, version)` guarded by `table_exists(cr,'pb_role_profile')`);
  `catalogue_vi.py` is a `VI` dict keyed by the exact English label (:32, e.g.
  `"Recruiter": "Chuyên viên tuyển dụng"` :72), applied by `apply_catalogue_vi` :303.
  Current manifest 19.0.1.10.0.
- Quiet-board kit: `pb_import_kit/static/src/xml/quiet_board.xml` (`QuietGlance` with
  `qGlance`/`qGlanceOn`; `QuietSteps` with `qSteps`/`qStepsLabel`/`qStepPick`; docs in
  lines 1-23), styles `quiet_board.scss`; call-site example
  `pb_onboarding/static/src/xml/onboarding_board.xml:69-82` (RC6).
- Drag: `web/static/src/core/utils/sortable_owl.js:13` `useSortable`; stock usage
  `web/static/src/views/kanban/kanban_renderer.js:100-141` (RC8).

### 1.5 Tests, demo, migrations
- Tests `pb_hiring/tests/`: `test_hiring.py` (64, `HiringCase` :39 with
  `_requisition(**extra)` :61), `test_interviews.py` (64, `InterviewCase` :38),
  `test_offer.py` (72, `OfferCase` :44), `test_journey.py` (6). 206 total, tagged
  `post_install`; run `--test-tags /pb_hiring`.
- Migrations exist at `pb_hiring/migrations/19.0.1.0.0/post-hiring_approval.py` and
  `19.0.1.2.0/post-offer_approval.py` (`def migrate(cr, version)`).
- Demo seed code `pb_demo_seed/seeds/lifecycle.py:31-62` makes 2 requisitions, 1 job,
  3 applicants. Live payobook has ~10 requests, 7 jobs, 7 candidates, 9 interviews, 3
  offers (from the wave-2 closeout). Recruiter login `demo.recruiter@example.com` /
  `RizeW2!2026` (uid 4446). `pb.demo.seed.register(records, label, last=False)`.

---

## 2. Architecture

### 2.1 Data
- **Stages** (`journey.py`): replace `STAGES` with the Rize default set, keys kept where
  they exist so nothing else breaks:

  | key | name | seq | family | default visible |
  |---|---|---|---|---|
  | `screening` | Applications received | 10 | open | always |
  | `shortlist` (NEW) | Shortlist | 20 | open | always |
  | `panel_review` | Hiring manager review | 30 | open | preset |
  | `phone` | Recruiter review | 40 | open | preset |
  | `assignment` | Assignment | 50 | open | preset |
  | `discussion_1` | Discussion 1 | 60 | open | preset |
  | `discussion_2` | Discussion 2 | 70 | open | preset |
  | `discussion_3` | Discussion 3 | 80 | open | preset |
  | `reference` | Reference check | 90 | open | hidden by default |
  | `offer` | Offer | 100 | open | always |
  | `post_offer` (NEW) | Post-offer | 110 | open | always |
  | `joined` | Joined | 120 | done | always (not a drop target) |
  | `cv_reject` | CV reject | 130 | closed | always |
  | `interview_reject` | Interview reject | 140 | closed | always |
  | `drop_out` | Drop-out | 150 | closed | always |
  | `on_hold` | On hold | 160 | closed | always |
  | `offer_drop_out` | Offer drop | 170 | closed | always |

  Add `pb_family` Selection (open/done/closed) computed from the key, `pb_meaning`
  (Char, the hover sentence; seed the sentences from the blueprint's vocabulary sheet),
  `pb_always_on` Boolean. Add `_stage(key)` helper (RC4). `_ensure_journey_stages`
  becomes idempotent on NAME and SEQUENCE too (renames existing rows by key) — that is
  the migration for existing DBs — and also runs `_retire_stock_stages()`: for each stock
  stage xmlid (`hr_recruitment.stage_job0..5`; verify the ids in
  `hr_recruitment_data.xml`), move its applicants (New→screening, Qualification→shortlist,
  First Interview→discussion_1, Second Interview→discussion_2, Contract Proposal→offer,
  Contract Signed→joined) with context `just_moved` so no template fires, clear
  `template_id`, then `unlink()` (RC5). Rename `_pb_shortlist` to target `shortlist`.
- **Presets**: new model `pb.hiring.stage.preset` (`name`, `company_id`,
  `department_id` optional, `country_id` optional, `stage_ids` m2m, `sequence`, `active`);
  match order: department+country → department → country → the company's "Standard"
  preset (seeded: standard = all open stages except `reference` and `discussion_3`).
  Seed one "Standard" per company in the seed hook (idempotent).
- **Role**: `pb.hiring.requisition.pb_visible_stage_ids` m2m, filled on create from the
  matching preset (never stored empty: fall back to Standard, then all). Outcome/done
  stages and `screening`/`shortlist`/`offer`/`post_offer` are ALWAYS shown regardless
  (`pb_always_on`). A candidate sitting in a stage the role hides still shows — the column
  appears with a "hidden for this role" caption until it is empty (zero dead-ends).
- **Switch**: `ir.config_parameter` `pb_hiring.line_managers_move` (default `0`, RC-D1).
- **Group rename**: `group_hiring_manager` name → "Talent lead" (the xmlid stays).

### 2.2 Server API (all on `pb.hiring`, called via `act` or directly)
- `get_requisition` gains per candidate: `stage_id`, `stage_key`, `family`,
  `applied_on`, `days_in_stage`, `source_label`, `waiting` (short sentence or ''),
  `next_interview_at`, `opinions` `{in, total, late}`, `has_cv`, `shared` (P4 fills; '' now),
  `edge` ∈ '' | 'green' | 'amber' | 'rose'. Plus `stages` for THIS role:
  `[{id,key,name,family,meaning,visible,count,avg_days}]` (avg days from the stage log),
  `closed_counts`, `role_glance` (per-role quiet numbers: people in play, waiting on you,
  interviews this week, opinions late, offers out — same `{key,n,label,tone,run}` shape).
- `_act_journey_stage(payload)`: `{applicant_ids: [..], key, reason?, hold_until?,
  send_email?}` — bulk-capable, no gates (see §4.1), returns `{moved:[{id, from_key}],
  note}` so the client can Undo by calling it back with the from keys (an undo move is
  logged as a normal move with a note "undone").
- `_act_role_stages(payload)`: `{requisition_id, stage_ids}` (Talent lead / Head only —
  `_require_write`).
- `_act_stage_meaning({stage_id, meaning})`, `_act_stage_rename({stage_id, name})`,
  `_act_stage_reorder({ids})` — `_require_write`.
- `_act_preset_save({id?, name, department_id, country_id, stage_ids})`,
  `_act_preset_delete({id})`.
- `get_setup()` → `{stages:[...], presets:[...], departments, countries, can_edit,
  cards:[{key,title,status,action}]}` for the set-up screen (cards: stages (live),
  forms → today's "Recruitment identity" settings form, scorecards → the scoring-lines
  list, emails → "Candidate emails", automations → the switches settings form,
  people → the Access home if `pb_vendor_access` action resolves; each card's `action`
  is an act_window dict WITH `views` (RC13) or an `ir.actions.client`).
- `get_timeline(applicant_id)` → `[{at, kind, text, by}]` merged from the stage log,
  `mail.message` (emails and notes on the applicant, subject/first line only), first look,
  interviews (arranged / done / no-show), offers (sent/answered/signed), sorted desc.
- `_act_first_look` (existing screening) targets: Shortlist → `shortlist`; CV reject →
  `cv_reject`; Future-fit → talent pool + `cv_reject`; Fit for other role → copy to the
  other role's `screening` + `cv_reject` here (blueprint table). Labels on screen become
  "Shortlist", "CV reject", "Future-fit", "Fit for other role"; the stored Selection
  values stay.

### 2.3 Client
- One client action (`pb_hiring_board`), two views in `state.view`: `home` (roles) and
  `role` (the role page with tabs Board / Interviews / Details / Activity). Use the
  action's `context`/`params` to deep-link (`{roleId}`) and push it with
  `this.env.services.router` if straightforward; otherwise keep it in state and support
  browser Back via a `popstate` listener. The existing drawer sections become the
  **Details** tab (request / jd / offer / adverts / referrals) — same markup, moved.
  Interviews tab = the existing interviews list filtered to this role (the home
  Interviews tab stays as is).
- Board: `useSortable({ref: boardRef, elements: ".pbhr-card", groups: ".pbhr-col",
  connectGroups: true, onDrop({element, group}) })` → `act("journey_stage",
  {applicant_ids:[id], key})`. The Closed rail is a group whose drop opens the outcome
  popover (which outcome, optional reason, "send the not-this-time email" tick →
  `send_email`). `joined` is not a group (its column shows the sentence "Joined is set
  when you confirm the person started, from their offer."). Line managers and anyone
  without `can_recruit` get no sortable and no checkboxes; hovering a card shows "Only
  recruiters and the talent lead move candidates".
- Cards: name, "Applied N days ago · Source", ≤2 chips, coloured edge, hover quick
  actions (Advance → next visible stage, Not this time → `interview_reject` or
  `cv_reject` by family, Open). Checkbox on hover / shift-click range; floating bar
  (`N selected · Move to ▾ · Send an email · Not this time · Clear`). Keyboard: arrows,
  Enter, M (move menu), E (email), Esc.
- Undo toast: 5 s, calls `journey_stage` back with the returned `from_key`s.
- Quiet numbers on the role page: reuse the kit `QuietGlance` template (RC6) with
  `role_glance`; the home keeps its existing glance markup.
- Column header: name, count pill, "~N days here", hover tooltip = meaning; Talent lead
  sees "+ Show a hidden stage" ghost column at the end (opens a checklist of hidden stages
  → `role_stages`).
- Empty column sentence per stage (from `pb_meaning`); empty board sentence: "Nobody
  has applied yet. Publish the role or add a candidate."; loading = 3 skeleton cards per
  column; >30 cards per column → "Show 40 more".
- First-visit hints: `localStorage` key `pbhr.hints.v1`, three hints, each dismissable,
  never shown again; wrapped in try/catch.
- Drawer: slide-over 520px over the board (board dimmed, arrows move to next card);
  hero (name, role, stage, applied, source, location), Next box (server `next` sentence +
  optional button), scorecards summary (existing feedback rows: who / score / decision),
  timeline (`get_timeline`), documents (attachments with preview link), actions.
- Hiring set-up: new client action `pb_hiring_setup` (same module), registered as a
  Settings category entry (replace/extend `SETTINGS_CATEGORIES` :119-150) and as a
  button "Set up hiring" on the home for `can_write` users, ⌘K row 4000. Stages card:
  list (inline rename on click, drag reorder with `useSortable`, meaning editable,
  "used by N roles"), presets matrix (rows = presets, columns = optional stages, click a
  cell to toggle; "Add a preset" picks department + country), "Preview as a board"
  renders sample columns. Other five cards: status sentence + Go (to the existing
  screens; never a dead end).

---

## 3. Design (build to the blueprint — this is the deliverable)

The design bar, verbatim from the ledger: **"exceptional premium, extreme WOW, a
novice can work without training"** — a named hero moment, zero dead-ends,
plain-language over code vocabulary, motion with purpose, keyboard + bulk ergonomics,
measured against the best SaaS tool in the category.

- **Hero moment:** dragging a card. The target column lights up as the card crosses it,
  the card lifts with `--pbim-sh-lg` and a 1.5° tilt, settles in 150 ms, the count pills
  tick, and the toast names what happened and what fired ("Dang Thi Mai moved to
  Recruiter review · Undo"). Nothing else on the page animates while that happens.
- Follow the blueprint's board mock for layout, chips, edges, closed rail, selection bar,
  toast, and the drawer mock for the drawer. Follow the "Rules that bind every screen"
  section for motion, undo-not-confirm, states, first visit, keyboard, plain words, light
  and dark.
- Words on screen come from the blueprint's vocabulary sheet. "Not this time" for
  reject; "Waiting on Minh" not "pending approval"; "Agreed" not "validated".
- Every new user-visible string: `_t()` in JS with `%s`, plain text in XML, and a
  Vietnamese entry in `pb_hiring/i18n/vi_VN.po` with the three comment lines.
- Lucide only via `ic()`; add missing icons to `IC` in the kit (grip, columns, undo,
  eyeOff, lock, sparkles as needed) — that file is deployed with the kit.
- Dark: define `.pbhr` dark tokens under `@media (prefers-color-scheme: dark)` AND
  `[data-theme="dark"]` for the new surfaces; check both in Chrome.

---

## 4. The rules of this phase (plain English on screen)

### 4.1 Moving
- Any card to any open or closed column, in any direction, by anyone with
  `can_recruit`. No reason required; the outcome popover offers one. `on_hold` offers a
  "look again on" date; empty is fine.
- Moving into `offer` or `post_offer` is allowed and does nothing else (the offer flow
  itself is P3). Moving into `joined` by drag is not offered; the column explains.
- Moving a candidate who has an interview without an outcome shows, in the toast, "Log
  how the interview went?" as a link — the move already happened.
- `action_mark_done` on an interview no longer refuses when opinions are missing; the
  interview shows "N opinions still to come" and the chase keeps running.
- `write` on `hr.applicant` keeps only the touch-field protection; the offer/joined
  rules go. The stage-log hook keeps logging every move (including bulk and undo).
- The line-manager switch OFF: a `_can_raise`-only user calling `journey_stage` gets a
  clear `AccessError` "Only recruiters and the talent lead move candidates."

### 4.2 Stages and presets
- Renaming a stage renames it everywhere at once (it is the record's name). Reordering
  changes `sequence`. Meaning is one sentence, max 160 chars.
- A role's visible set is edited from the board ("Show a hidden stage") or the Details
  tab; presets only affect NEW roles (say so on the matrix: "Presets fill in new roles;
  existing roles keep their own columns").
- Deleting a preset that roles were created from does nothing to those roles.

### 4.3 Who sees what (this phase)
- Recruiter / Talent lead / Head of hiring: everything as today.
- A line manager (`_can_raise` only): the home shows their roles; the board is read-only
  (no sortable, no checkboxes, no quick actions except Open and Note); the drawer shows
  the same sections minus money (P4 hardens this; in P1 simply do not render
  `salary_expected`/`salary_proposed` for non-`can_recruit` users).

### 4.4 Stock surfaces
- Stock Recruitment menus hidden by `active=False` data records (RC15). The stock
  applicant form stays reachable from the drawer's "Open the full record" for
  recruiters (VU-skinned as today).

---

## 5. Numbered test cases (record each result in the report)

Python tests (`pb_hiring/tests/test_board_p1.py`, `test_stages_p1.py`; extend the
existing helpers; tag `post_install`):
1. Seed on a fresh DB creates the 17 stages with the names/sequences of §2.1, `pb_family`
   right, meanings non-empty, and NO stock stage rows remain.
2. Running the seed twice changes nothing (idempotent); renaming a stage then re-seeding
   keeps the rename? — NO: the seed sets Rize names ONLY when the row is CREATED or still
   carries the OLD wave-2 name; a client rename survives an upgrade. Test both.
3. Stock stage retirement moves applicants per the map, fires no email, and unlinks.
4. A new role gets `pb_visible_stage_ids` from department+country preset, else department,
   else country, else Standard; never empty.
5. `get_requisition` returns `stages` with counts that add up to `candidates` (+ closed
   counts), each candidate with `stage_key` and `family`.
6. `journey_stage` moves one and many; no reason needed for `cv_reject`; `on_hold` with
   no date OK; `offer` and `post_offer` allowed; `joined` refused with the explaining
   message; returns `from_key`s; undo call restores and logs.
7. A `_can_raise`-only user cannot move (AccessError text as §4.1); with the switch ON
   they can, on their own roles only.
8. `write` on `hr.applicant` no longer raises for `offer`/`joined` targets; touch-field
   protection still raises.
9. `action_mark_done` with pending opinions succeeds and the feedback chase still runs.
10. `get_timeline` merges stage log, first look, an email, a note, an interview, in
    descending order with plain-English texts.
11. First look → Shortlist lands in `shortlist`; Future-fit lands in `cv_reject` AND the
    pool; Fit for other role creates the copy in the other role's `screening`.
12. Presets: save/delete; `_require_write` enforced; the matrix payload round-trips.
13. `get_setup` returns six cards, each with a resolvable action carrying `views`.
14. Group `group_hiring_manager` reads "Talent lead"; Access catalogue row label + Vietnamese
    updated; `ensure_catalogue` migration is idempotent.
15. Stock menus are inactive after install/upgrade.
16. Existing 206 tests still pass (fix the ones that asserted the old gates/names).

Browser (payobook.com, Chrome MCP, light AND dark, console read each time):
17. Recruiter: home → open the busiest demo role → board shows its visible columns in
    order with counts, captions, meanings on hover; closed rail counts.
18. Drag a card to another column: highlight, lift, settle, toast with Undo; Undo puts it
    back; both moves in the timeline.
19. Drag onto Closed: popover; choose CV reject with no reason; card in the rail; count up.
20. Tick three cards → floating bar → Move to → all three moved; Undo restores all three.
21. Keyboard: arrows, Enter opens the drawer, Esc closes, M opens the move menu.
22. Drawer: Next box sentence matches the state (a late opinion shows "Remind"), timeline
    ordered, documents open, arrows move to the next card without closing.
23. Talent lead: "+ Show a hidden stage" adds Discussion 3 to a role; the column appears
    empty with its meaning sentence.
24. Hiring set-up → Stages: rename inline (board reflects it), drag reorder, edit a
    meaning; presets matrix toggle; "Preview as a board"; the other five cards open the
    right screens.
25. Line manager login: home shows only their roles; board read-only; hover message.
26. First visit hints appear once; dismissed; not again after reload.
27. Empty role (no candidates): the empty-board sentence and the buttons it names work.
28. A role with a candidate in a hidden stage: the column shows with the caption.
29. Stock Recruitment menus absent from the app switcher/menus.
30. Dark mode: all of 17–24 legible; no white flashes.
31. No console errors on any screen; no red style bar.

---

## 6. Deploy and verify

Tier = **risky** (migration rewrites stored stage data; new module install on two DBs;
security rename). Follow the RIZE ledger ritual with these specifics:
1. Backups first: `payobook`, `rize`, `payobook_template` into
   `/odoo/backups/2026-09-30-recruit-p1/`.
2. Rehearse on a clone of `rize` (`createdb -T rize rize_p1_rehearsal` with the service
   stopped; install there; drop it after).
3. `payobook`: `-u pb_hiring,pb_vendor_access` (+ `pb_import_kit` if icons were added).
4. `rize`: check `ir_module_module` for every module in `pb_hiring`'s `depends`; install
   what is missing (allowed: any pb_*/biz_* except pb_tenants, pb_demo, pb_demo_portal,
   pb_website); then `-i pb_hiring -u pb_vendor_access`.
5. `payobook_template`: same as rize (install if missing, else upgrade).
6. Per DB: asset purge + `web.assets.version` bump + `orm_signaling_assets` row (RC14).
7. Verify: hash each touched module tree repo vs server; `latest_version` per DB matches
   the manifests (19.0.2.0.0 / 19.0.1.11.0); one Chrome walk on payobook.com (tests
   17–31); on rize and the template, the cheap checks (files identical, version, the
   Lifecycle → Hiring tab opens for an admin with no console error).
8. Demo data (payobook only): the two logins + ~28 candidates, registered with
   `pb.demo.seed` (label "RECRUIT P1 board candidates"); NOT on rize/template.
9. Commits per feature (explicit staging), e.g. stages+migration / presets+setup / board /
   drawer / rename+menus / demo+tests / docs. Do not push.

---

## 7. Report back

Keep it under two pages, plain English, in this order:
1. What is live and where (three DBs, versions), the commits.
2. Test results 1–31 with any deviation and why.
3. A self-score against the design bar (hero moment, dead-ends, words, motion,
   keyboard/bulk, dark) with one honest sentence each.
4. Deviations from this handover and the reason (e.g. `useSortable` limitations).
5. New ledger rows you appended (RC16+), and anything the next phase must know (API
   names you left behind: the `journey_stage` payload, `get_setup`, `get_timeline`,
   `role_glance` shape).
6. Owner items: anything that needs the owner's word (e.g. a stage name, a preset).
7. Demo records table (label, model, count) and the two new logins.
