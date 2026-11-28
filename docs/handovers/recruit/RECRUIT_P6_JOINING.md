# RECRUIT — Phase 6: from signed to joined — Post-offer, the week before, "Confirm they joined", the numbers

Delivers register lines **G-42 (upload half), G-44, G-52, G-53, G-54, G-55, G-56, G-57,
G-58**: a signed offer no longer creates the employee; the person stays a candidate in
Post-offer with an expected joining date and a recruiter-run "Before they join" list
(buddy nomination by the manager, laptop preferences from the candidate, meet-the-team
chats); one email a week before to recruiter + hiring manager + HR with three answers;
"Confirm they joined" creates the employee, contract, login and hands to HR onboarding;
"Did not join" is an offer drop with a reason; several signed documents per country;
Hiring numbers get market / department / recruiter filters, the offered → accepted →
signed → joined funnel with drops, a pipeline-ageing report, a leadership view and an
Excel export per report.

Read first, in order: `docs/handovers/recruit/RECRUIT_LEDGER.md` (all rows incl.
P1–P5), the **P1–P5 phase reports** (shapes: `_act_journey_stage`, `get_candidate`,
`request_state`, `_offer_block_reason`, `_sender`, `parts_for`, `videocall_url`,
`_ensure_event` helper), the blueprint sections "From offer to joined" and "The
candidate drawer", the register lines, then this file. Facts verified 2026-09-30 on the
working copy; re-locate moved lines by name. Rulings R8 and RC-D5 apply.

---

## 0. Scope and binding non-goals

**In scope (P6):** `pb_hiring` **19.0.2.5.0** with a migration.
1. **Split signed from joined**: `action_record_signed` moves the candidate to
   `post_offer`, sets `expected_join_date` (from `start_date`) and creates NOTHING else.
   New offer states `joined` ("They have joined", replaces the meaning of today's
   `closed`) and `dropped` ("Did not join"). `action_close` becomes **Confirm they
   joined** (`action_confirm_joined(joined_on)`): all of today's legs, anchored on the
   actual date; the candidate moves to `joined` (hired stage); `date_closed` = hire date.
   **Did not join** (`action_did_not_join(reason_id, note)`): offer `dropped`, candidate
   `offer_drop_out` with the reason, headcount not filled, HM + Talent lead told.
2. **Before they join** (`pb.hiring.prejoin` items on the offer): buddy nomination (email
   to the manager with a token page to name one or more buddies), laptop preferences
   (candidate token page), meet-the-team chats (recruiter picks people + time → calendar
   entry + `.ics` mails, reusing the interview event helper), free to-dos; each with
   owner, due (relative to the expected date), state; shown in the drawer's Post-offer
   Next box and a "Before they join" section, with one button per item. On join, the
   buddy lands on the employee (`buddy_id`) and ticks the onboarding "Choose their buddy"
   step; laptop preferences land on the asset request / laptop step note.
3. **The week before**: daily leg → one email 7 days before `expected_join_date` to the
   recruiter, the reporting manager and the HR-lead holders, with three buttons on a
   token page: "Still on", "Date changed" (date + reason), "Did not join" (reason); plus
   "Change the joining date" sheet on the drawer (reason, notify HM + HR); every change
   in the timeline.
4. **Signed documents per country**: `pb.hiring.offer.document` (kind: offer letter /
   employment agreement / probation letter / other; label; attachment; signed on; who);
   migration turns today's single `signed_attachment_id` into one row; "Add a signed
   document"; all filed to the vault on join under the right category; the drawer lists
   them with the country's expected set (VN: offer + probation letter later; IN/ID: offer
   + employment agreement) as a checklist hint (not a gate).
5. **Hiring numbers**: filters department / country (market) / recruiter + date range;
   funnel offered → accepted → signed → joined with declined / did-not-join and reasons,
   per market; pipeline ageing (candidates in open stages by days since last move, by
   stage and recruiter, "stalled" ≥ 14 days highlighted); leadership view (fill rate =
   filled ÷ agreed roles, open headcount by country, source mix, delay split, time to
   fill trend); Excel export per section ("Download this report") plus the whole
   workbook. Analytics screens keep their tiles (quiet-board rule).
6. Home/board: Post-offer cards show "Joining Mon 3 Nov · 9 days" and the item count;
   the Joined column gains the sentence + the "Confirm they joined" button in the drawer;
   the requisition's `filled_count` counts `joined` offers.
7. Tests, deploy (three DBs, never abm), Chrome validation, report.

**Binding non-goals:** HR onboarding after joining (exists: `pb_onboarding` template,
30/60/90 check-ins, pulses — do not change beyond ticking the buddy step and passing the
laptop note); probation (`pb_probation`); generated offer letters / DocuSign (deferred,
R3); email language versions (P8 — but the candidate-facing laptop page and its email
use `pb_lang` like P2's pages); the agency portal (P7); a candidate-side upload of the
signed copy (owner item; recruiters upload).

---

## 1. Verified plumbing facts (do not re-derive)

### 1.1 Closure today (`pb_hiring/models/offer_closure.py`)
- `action_close` :61-105: returns True if already `closed` :64; any state other than
  `signed` → UserError :66-72. Legs in order: `_ensure_employee` :110-171 (outside a
  savepoint, raises :74-79; reuses `employee_id` or finds by `applicant_ids`; creates a
  partner :134-143; vals from `applicant._get_employee_create_vals()`
  `hr_recruitment/models/hr_applicant.py:1025-1049` + company, work_email, job_title,
  `parent_id` = reporting manager :145-158; copies attachments :163-168; **no country,
  no portal user here**), `_mark_applicant_hired` (override `journey.py:429-435` →
  stage `joined`; base :176-197), `_ensure_contract` :202-261 (switch `create_contract`
  default 1 `hiring_common.py:92`; reuses an `hr.contract`; creates with `wage` from
  `_basic_line` :263-276, `date_start` = `start_date` or today; stays draft),
  `_ensure_package` :281-334 (`pb.employee.comp` draft, `effective_date=start_date`),
  `_ensure_login` :339-362 (`pb.zoho.pipeline._auto_create_login(employee, company,
  summary)` `pb_zoho_bridge/models/zoho_pipeline.py:586-624`, portal user, gated
  `pb_zoho_bridge.auto_create_logins`), `_ensure_case` :367-394 (`_open_case(employee,
  'onboarding', start_date, company)` `zoho_pipeline.py:555-583` → `_after_onboard(case,
  {'name','date_of_joining','source':'pb_hiring','_raw':{}})`; `pb_onboarding`'s
  `zoho_pipeline_ext.py:26-35` runs `case.setup_onboarding()`; pb_hiring does NOT depend
  on pb_onboarding), `_file_signed_copy` :399-438 (`pb.employee.document`, category
  `pb_employee_vault.cat_other`, "Signed offer <ref>", idempotent on name), state
  `closed` + `closed_on` :94-99, `requisition._on_filled` (`requisition_a3.py:85-113`;
  `filled_count` = offers in `closed` :59-66 → `action_mark_filled` + mail),
  `_tell_them_they_joined` :443-472 (switch `closure_mail`; `mail_template_offer_closed`
  to manager user email, manager work_email, `recruiter_manager_id.email` via `_mail`
  `offer.py:644-659`). Idempotency by stored links (docstring :32-35; test
  `test_offer.py:501-510`). **No reopen/undo of a closure.**
- Offer states `hiring_common.py:252-263`: draft, submitted, manager_ok, hr_ok, sent,
  accepted, declined, signed, closed ("They have joined"), refused; `OFFER_LIVE`
  :266-267. `action_send_to_candidate` `offer.py:602-642`; `record_decision` :717-737
  (once; `_tell_recruiter_the_answer` :739-766 — **a declined offer moves nothing**, the
  candidate keeps their stage, `test_offer.py:414-424`); `action_record_signed` :771-815
  (from accepted or sent; mandatory attachment 5 MB + MIME; overwrites the single
  `signed_attachment_id` :158-160; sets `signed_on`, `signed_by_id`, `state='signed'`,
  `candidate_decision='accepted'`). `start_date` required :122, in the approval revision
  stamp (`offer_approval.py:46,105`); `_check_start` :254-261 blocks past dates only in
  draft/submitted; `_act_offer_set` changes `start_date` in any state
  (`pb_hiring_a3.py:524-537`); facade `_act_record_signed` :617, `_act_close_offer`
  :636-646; board button only in `signed` (`hiring_board.xml:1219-1220`,
  `hiring_board.js:1360-1361`). Token page `/hiring/o/<token>` :174-222 (accept/decline
  once, one comment, download letter; no upload). `page_facts` `offer.py:687-715`.
- Stages (working copy `journey.py:20-38`): `post_offer` seq 110 family open, `joined`
  the only `hired_stage` (:215; `test_stages_p1.py:44`); `ALWAYS_ON` incl. post_offer +
  joined :45; nothing moves a candidate to `post_offer` today; `draft_for` moves to
  `offer` (:421-427). Board: manual moves to `joined` refused (`board_p1.py:274-277`,
  `test_journey.py:29-38`); `post_offer` Next prompt "Offer accepted. Joined is set from
  the offer when they start." :802-808; staleness chip skips offer/post_offer :519-523.
  `date_closed` "Hire Date" `hr_applicant.py:90` (compute :598-604 on `hired_stage`).
- Refuse reasons `hr_recruitment/data/hr_recruitment_data.xml:72-101` (refuse_reason_1,
  _2, _5, _6, _7, _8); `_pb_reject` `hr_applicant_ext.py:123-139`; journey override
  `journey.py:357-363`; `_act_reject` `pb_hiring.py:853-862`; drawer lists ≤30 reasons
  (`pb_hiring.py:498-502`); moving back clears the reason (`board_p1.py:296-298`);
  `offer_drop_out` seq 170 (`journey.py:37`, meaning :86), free-text reason only
  (`pb_stage_reason` `journey.py:306`, written :289-290).

### 1.2 Onboarding hand-off (`pb_onboarding`, `pb_lifecycle`)
- Template "New joiner — the full welcome" `pb_onboarding/data/journey_template_data.xml:34-157`
  (old P0 template deactivated :26-32), steps: 10 Choose their buddy (manager, case_open
  +0, `buddy_invite`, escalates 3 d), 20 Laptop and equipment (it, doj −12,
  `asset_laptop`), 30 Tool access (it, doj −5), 40 Tell us about you (candidate, doj −1,
  form), 50 Welcome card (hr, doj +0, `poster`), 60 Day-one introduction (hr, doj +0,
  `day1_ics`), 70 Send their sign-in details (hr, doj +0, `credentials`), 80 Finish your
  own details (employee, doj +3), 90 Welcome session (hr, doj +7).
- **A journey cannot start before the employee exists**: `pb.journey.case.employee_id`
  required (`pb_lifecycle/models/journey_case.py:54-56`); tasks related
  (`journey_task.py:35-37`); no applicant field anywhere; `pb.asset.request`,
  `pb.employee.checkin`, `pb.newhire.pulse`, `pb.buddy.nomination` all need an employee.
  `_open_case` picks the template via `pick_for(case_type, employee.country_id,
  company.id)` (`journey_template.py:67`), `source='zoho'` hard-coded; `action_open`
  → `_generate_tasks` (`journey_case.py:263-321`), assignees `_resolve_assignee`
  :218-260 (manager = `employee.parent_id.user_id`; candidate = token; hr/it/finance/admin
  = config-parameter user or the lifecycle manager group :25-30; hrbp/buddy probed
  :35-38); `doj` = anchor_date → `first_contract_date` → earliest contract → today
  :157-186. `buddy_id`, `hrbp_user_id`, `buddy_temp_*`, `onboarding_case_id`,
  `_pb_join_date` (`pb_onboarding/models/hr_employee.py:49-58`, :134-156).
  `setup_onboarding` `journey_case_ext.py:75-95` (HRBP, check-ins d30/60/90 :30,
  orientation, pulses 7/30/60 `onboarding_common.py:50-52`, asset requests with
  `needed_by` = laptop step due). Buddy: `_auto_buddy_invite` `journey_ext.py:308-326`
  (mails `mail_template_buddy_nominate` `pb_onboarding/data/mail_template_data.xml:122-146`
  to the manager's work_email; step stays open; **the manager has no token page** — the
  choice is backend `pb.onboarding.buddy_choose` `pb_onboarding.py:227` →
  `pb.buddy.nomination.choose` :258-291 (sets `buddy_id`, `_schedule_connects`,
  `_tell_them`, `_tick_step`)). Buddy catch-ups = `pb.employee.checkin` kind `buddy`
  every 14 days ×6 (`buddy_nomination.py:311-341`), not calendar events.
- Token pages `pb_lifecycle/controllers/token_pages.py`: `/journey/t/<token>` :79-86 +
  `/submit` :88-109 (`_task_for_token` `journey_task.py:98-115`; form answers
  `payload_json` via `action_done`; question types text/rating/choice :179-209);
  `/journey/f/<token>` :112-153; pulses `pb_onboarding/controllers/pulse_pages.py:33,43`.
  `build_ics(summary, dt_start, dt_end=None, organizer=None, attendees=None,
  description='', location='', uid=None)` `pb_lifecycle/models/ics.py:48-88` (bytes,
  naive UTC, default 1 h); used by `_auto_day1_ics` `journey_ext.py:181-237`.
- Contract models: `hr.contract` (vendored `hr_contract` 19.0.1.0.0, `date_start`
  `hr_contract/models/hr_contract.py:32`; `first_contract_date` `hr_employee.py:24,58-61`)
  AND `hr.version` (`contract_date_start` `hr/models/hr_version.py:145`); closure, demo
  seeds (`pb_demo_seed/seeds/people.py:356-365`) and lifecycle use `hr.contract`.
  `pb.employee.comp` (`pb_comp_ben/models/employee_comp.py:33-49`).
- Join-date helpers: `pb_onboarding/models/hr_employee.py:134` `_pb_join_date`;
  `pb_people/models/pb_people.py:21`; `pb_lifecycle/models/letter.py:163`. **No
  expected/confirmed joining-date field exists** beyond `offer.start_date` /
  `case.anchor_date`.
- Vault `pb.employee.document` (`pb_employee_vault/models/employee_document.py:52-77`;
  no API, callers `create()` as sudo; categories `cat_labor_contract`, `cat_id_document`,
  `cat_certificate`, `cat_health_check`, `cat_work_permit`, `cat_other`). Letter
  templates `pb.letter.template` (`letter.py:57-77`, no country field; offer template
  matched by country name `ilike` `offer.py:342-364`); shipped `letter_template_offer_generic`
  :28 / `_vietnam` :68; contract-lifecycle letters `pb_contract_lifecycle/data/letter_template_data.xml:27-67`;
  probation letters `pb_lifecycle/data/letter_template_data.xml:39`,
  `pb_probation/data/letter_template_data.xml:26,61`. **No "employment agreement"
  template exists.**
- Crons: `cron_hiring_daily` → `run_now` `hiring_automation.py:50-70` (legs
  `_nudge_adverts`, `_nudge_open_roles`, `_chase_late_feedback`, `_chase_documents`,
  `_document_deadlines`, `_move_covers`); `leg(env, label, fn)` `hiring_common.py:335-349`;
  multi-address mail = loop `send_mail(..., email_values={'email_to': addr})`
  (`offer.py:644-659`, `offer_closure.py:457-468`). Lifecycle reminders
  `pb_lifecycle/models/lifecycle_reminders.py:50-148`. **No cron fires N days before a
  joining date.**
- Analytics `pb_hiring/models/analytics.py`: `get_board` :124-196 (`SCAN_LIMIT=2000`
  :46 on requisitions :119 and `_sources` :336; `DEFAULT_DAYS=90` :41, `_window` :94-109;
  cohort = requisitions with `opened_on` in window + `company_id in env.companies`
  :111-119 — **company is the only filter**); tiles requests / filled / fill_median /
  fill_mean :227-236 / offer_median :239-260 / offers + acceptance `_offer_acceptance`
  :263-281 (accepted ÷ (accepted+declined)); sections stages :284-320 (stage log),
  sources :323-353, delays (reschedules), no_shows, agency; `export_xlsx` :417-503
  (sheets Summary / Time in stage / Where they came from / Interviews moved / Nobody came
  / Agency or our own; base64). `hiring_numbers.js` :1-172 (ranges 30/90/180/365 +
  custom; `get_board(from,to)`, `export_xlsx` data URL; action `pb_hiring_numbers`
  :172, `action_pb_hiring_numbers` `offer_views.xml:586-589`); `hiring_numbers.xml`
  header :43-52, ranges :64-75, empty :87, tiles :105, sections :123-216; Insights lens
  `hiring_palette.js:82-96`; ⌘K `hiring_analytics` seq 3570 :255-266. Stage log fields
  `stage_log.py:30-47`, `note_move` :56-73.
- Demo: joiners "DEMO Nguyen Van An" (552) / "DEMO Tran Thi Binh" (553) with offers
  106/107 CLOSED, employees 19613/19614, contracts, packages, checklists, logins
  `demo.a3.an@` / `demo.a3.binh@example.com` on requisition 798; offer 108 mid-approval
  (`RIZE_LEDGER.md:1642-1659`) — leave them as they are (migration maps `closed` →
  `joined`). `pb.demo.seed.register(records, label, last)` (`demo_seed.py:237`),
  `register_ids` :209; `PROTECTED_MODELS` :55-59 (employees/contracts not protected).
- Tests `test_offer.py`: `OfferCase` :44-118 (`_offer` :92-107, `_complete_documents`
  :109-118), `_agreed` :370-373, `TestTheClosure` :442-557 (`_signed` :444-453 → hr_ok,
  documents, send, accepted, `action_record_signed` with a PDF; tests :455-557),
  `TestTheNumbers` :731-758; **no stubs of the zoho hooks** — the real
  `_auto_create_login` / `_open_case` / `_after_onboard` run in tests.

---

## 2. Architecture

### 2.1 Offer states and the two moments
- States: draft, submitted, manager_ok, hr_ok, sent, accepted, declined, signed,
  **joined** ("They have joined"), **dropped** ("Did not join"), refused. Migration:
  `closed` → `joined` everywhere (states, `OFFER_LIVE`, `filled_count`, analytics,
  board, tests); keep a read-only alias so old code paths comparing to `'closed'` fail
  loudly in tests rather than silently (grep them all).
- New fields on the offer: `expected_join_date` (Date; set = `start_date` at signing;
  editable via the sheet with `join_date_reason` + history in chatter), `joined_on`
  (Date), `join_status` (Selection: pending / confirmed / changed / dropped),
  `week_before_sent_at`, `week_before_token`, `document_ids`, `prejoin_ids`,
  `buddy_employee_ids`, `laptop_prefs_json`, `laptop_token`, `buddy_token`.
- `action_record_signed`: as today (attachment → becomes the first
  `pb.hiring.offer.document` kind `offer_letter`), then `expected_join_date`,
  `join_status='pending'`, candidate → `post_offer` (with `just_moved`), create the
  default pre-join items (§2.2), post the timeline line, mail HM + Talent lead
  ("<name> signed; joining on <date>"). No employee, contract, login, case, vault.
- `action_confirm_joined(joined_on=None)` (from `signed` only; `joined_on` default =
  `expected_join_date`, may be earlier/later): today's legs 1–10 with anchor `joined_on`
  (contract `date_start` = `joined_on`; package `effective_date` = `joined_on`; case
  anchor = `joined_on`); after `_ensure_case`: copy `buddy_employee_ids[0]` → `employee.buddy_id`
  and tick the case's "Choose their buddy" step (find by `automation_key='buddy_invite'`
  → `action_done` / `_tick_step` — verify the API; if `pb_onboarding` is not installed on
  the DB, skip with a note), put `laptop_prefs_json` (rendered as text) into the laptop
  step's notes and the asset request's note if one exists; file every
  `pb.hiring.offer.document` to the vault (offer_letter → `cat_other` "Signed offer",
  employment_agreement / probation_letter → `cat_labor_contract`, other → `cat_other`);
  offer `joined`, `joined_on`, `join_status='confirmed'`; candidate → `joined`;
  `_on_filled`; the "they joined" mails. Confirmation dialog on screen: "Confirm that
  <name> started on <date>? This creates their employee record, contract and sign-in."
- `action_did_not_join(reason_id, note)` (from `signed`): offer `dropped`,
  `join_status='dropped'`, candidate → `offer_drop_out` with `pb_stage_reason` = reason
  name + note and `refuse_reason_id` = the seeded reason "Accepted the offer but did not
  join" (new `hr.applicant.refuse.reason` row in pb_hiring data), cancel pending pre-join
  items and chats (archive their events), mail HM + Talent lead + HR lead holders,
  timeline. Also add a seeded reason "Declined the offer" used by `record_decision`
  declined → move the candidate to `offer_drop_out` (today a declined offer moves
  nothing — fix; keep the candidate active? No: closed stage → inactive like other
  outcomes; leaving the stage reactivates as today).

### 2.2 Before they join (`pb.hiring.prejoin`)
- Fields: `offer_id`, `sequence`, `kind` (Selection: buddy / laptop / chat / todo),
  `title`, `owner` (Selection: recruiter / manager / candidate / hr), `due_offset_days`
  (relative to `expected_join_date`, negative = before), `due_date` (computed stored,
  recomputed when the expected date changes), `state` (open / done / skipped),
  `done_on`, `note`, `token` (for manager/candidate pages), `event_id` (chats),
  `people_employee_ids` (chats), `reminded_at`. Default items created at signing (from
  a small company-level list `pb.hiring.prejoin.template`, seeded: "Ask <manager> to
  name a buddy" (manager, −10), "Ask <name> for laptop preferences" (candidate, −10),
  "Set up a meet-the-team chat" (recruiter, −5), "Send the first-day details" (recruiter,
  −2)); the Talent lead edits the list in Hiring set-up → "Before they join" card.
- Actions: buddy → `mail_template_prejoin_buddy` to the manager with `/hiring/b/<token>`
  (page: the new joiner's name, role, start date; pick one or more buddies from a
  searchable list of the company's employees; a line why; submit → `buddy_employee_ids`,
  item done, recruiter told); laptop → `mail_template_prejoin_laptop` to the candidate
  (in `pb_lang`) with `/hiring/l/<token>` (page: laptop type (Mac / Windows / no
  preference), keyboard layout, screen size, accessories, anything else; submit →
  `laptop_prefs_json`, item done, recruiter told); chat → a sheet (people from the team
  + the manager, date/time, 30 min default, video or in person) → a calendar entry via the
  interview `_ensure_event`-style helper (extract a shared `_make_event(title, start,
  minutes, partners, description, location, organiser)` in `hiring_common` or the
  interview model; P5's Google Meet path applies when the organiser is connected) +
  `.ics` mails to the candidate and the people; item done when the chat time passes;
  todo → tick. Reminders: daily leg mails the owner when an item is due tomorrow and
  still open (recruiter to-do for candidate/manager items overdue by 2 days).
- Drawer (Post-offer): Next box "Joining Mon 3 Nov · 9 days · 2 of 4 things done ·
  <next open item as the button>"; "Before they join" section listing items with owner,
  due, state, per-item button; "Change the joining date"; "Confirm they joined" /
  "Did not join" buttons (Confirm is primary from 3 days before the date; both always
  available). Card chip: "Joining in 9 days" (amber when an item is overdue).

### 2.3 The week before
- Daily leg `_week_before_join`: offers `signed` with `expected_join_date == today + 7`
  (calendar days; also catch a date set later inside the window: send when
  `week_before_sent_at` is empty and the date is ≤ 7 days away and > today) → one mail
  `mail_template_join_week` (from `_sender`) to recruiter, reporting manager (user email
  or work_email), HR-lead holders; body: "<name> joins on <date> as <title>. Still on? ·
  The date changed · They will not join" → `/hiring/w/<token>` page with the three
  buttons (Still on → `join_status` stays, note "confirmed by <who>"; Date changed →
  date + reason → `expected_join_date` updated, items' due dates shift, HM + HR told;
  Did not join → reason → `action_did_not_join`). Everything to the timeline.

### 2.4 Hiring numbers
- `get_board(date_from, date_to, department_id=None, country_id=None, recruiter_id=None)`
  and `get_funnel(...)` → `{offered, accepted, signed, joined, declined, dropped,
  by_market:[{country, offered, accepted, joined, drops}], reasons:[{reason, n}]}`;
  `get_ageing(...)` → rows (candidate, role, stage, days since last move, recruiter),
  stalled threshold param `pb_hiring.stalled_days` (14); `get_leadership(...)` → fill
  rate, open headcount by country, source mix, delay split, time-to-fill by month.
  Export: `export_xlsx(kind='all'|'funnel'|'ageing'|'leadership'|<section>)`.
- UI: filter bar (department / country / recruiter / range) above the tiles; new
  sections Funnel (a horizontal funnel with the drop reasons list), Ageing (table with
  stalled rows highlighted, click → the candidate), Leadership (four tiles + a 12-month
  time-to-fill bar chart drawn with plain SVG on tokens, no library); "Download this
  report" per section + "Download everything".

---

## 3. Design (build to the blueprint)

Design bar verbatim (ledger): **"exceptional premium, extreme WOW, a novice can work
without training"**. Hero moment for P6: the Post-offer card's countdown and the
"Before they join" list ticking itself as the manager and the candidate answer from
their emails; and the funnel where a drop shows its reason on hover. Zero dead-ends:
"Confirm they joined" says what it creates; "Did not join" asks the reason and says
who is told; a token that is used says so and offers the recruiter's email. Plain words
("Joining in 9 days", "Still on?", "They will not join"). Candidate-facing pages and
mails in `pb_lang` (vi_VN + id_ID `.po` entries); the manager page English. Light and
dark; the ageing and funnel readable in both.

---

## 4. Rules (plain English on screen)
- Signing an offer keeps the person a candidate; nothing about them exists in the
  employee list until you confirm they started.
- The joining date is the recruiter's to change until the person starts; every change
  is recorded and the hiring manager and HR are told.
- A week before the date, everyone involved gets one email with three answers.
- "Did not join" counts as an offer drop with its reason, so the numbers stay honest.
- The buddy the manager names becomes the buddy on day one; laptop preferences reach the
  people who prepare the laptop.

---

## 5. Numbered test cases
1. Migration: `closed` offers → `joined`; `filled_count` unchanged; demo joiners intact.
2. Signing moves the candidate to `post_offer`, sets the expected date, creates the
   default pre-join items with correct due dates, creates NO employee/contract/login/
   case/vault rows, mails HM + Talent lead.
3. Confirm joined (default date / earlier / later): all legs run with the chosen anchor;
   candidate `joined`, `date_closed` set; buddy copied + step ticked when pb_onboarding is
   installed (skip cleanly when not); laptop note reaches the step/asset request; every
   document filed with the right category; idempotent on a second call; `_on_filled`.
4. Did not join: offer `dropped`, candidate `offer_drop_out` with the seeded reason,
   items cancelled, chats archived, mails sent; headcount not filled; the role stays open.
5. Declined offer now moves the candidate to `offer_drop_out` with "Declined the offer".
6. Change the joining date: items' due dates shift; timeline + mails; the week-before
   mail re-arms when the new date is > 7 days away.
7. Week-before leg: fires once at 7 days (and once for a date set inside the window);
   the token page's three answers do what they say; a used token says so.
8. Buddy page: names two buddies; item done; recruiter told; on join → `buddy_id` = the
   first, both in the case note. Laptop page: saves prefs in `pb_lang`; item done.
9. Chat: event + `.ics` mails; the event uses the shared helper; Google path when the
   organiser is connected (mocked); item done after the time passes.
10. Documents: several per offer; kinds; the drawer's country hint; migration of the old
    single attachment.
11. Numbers: filters narrow every metric; funnel counts and reasons; ageing rows and
    stalled flag; leadership fill rate and headcount by country; each export kind returns
    a workbook with the expected sheet(s).
12. Existing tests pass (rewrite closure tests to the two-moment flow).
Browser (payobook.com, light + dark; the candidate laptop page at 360 px):
13. Sign a demo offer → Post-offer card with countdown → drawer list → send the buddy
    email → open the link logged out → name a buddy → the item ticks.
14. Laptop email → page → submit → item ticks; the recruiter sees the answers.
15. Set up a chat → `.ics` mail; the event on the recruiter's calendar.
16. Change the date → chip and due dates update; mails queued.
17. Week-before page (force the date) → "Date changed" flow.
18. Confirm they joined → employee exists with buddy; contract dated; the welcome
    checklist open; the card in Joined; the role filled when headcount reached.
19. Did not join on another demo offer → Offer drop with reason; funnel shows it.
20. Hiring numbers: filters, funnel hover, ageing click-through, leadership chart, both
    downloads.
21. No console errors; no red style bar.

## 6. Deploy and verify
Tier **risky** (state migration on offers; closure rewrite). Backups ×3; rehearse on a
clone of payobook (it holds the closed demo offers); then payobook, rize, template;
asset purge etc.; hash + versions; one Chrome walk; cheap checks elsewhere. Demo
(payobook): one signed offer in Post-offer with items, one dropped, registered. Commits
per feature; no push. Ledger rows; phase log.

## 7. Report back
P1 §7 format; tests 1–21; self-score; deviations; ledger rows + shapes for P7/P8
(`join_status`, `pb.hiring.prejoin`, `get_funnel`, `export_xlsx(kind)`, the shared event
helper, the join-week token route); owner items (whether candidates may upload their own
signed copy; the country document sets; the stalled-days threshold; who the HR
recipients of the week-before mail should be per company); demo table.
