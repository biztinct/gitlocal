# RIZE P3 — pb_onboarding: the new-joiner experience

Read FIRST: `docs/handovers/RIZE_LEDGER.md` + the phase log entries for P0/P1/P2 (model
APIs, registry names, after-hooks — where THIS file and the P0–P2 reports disagree, the
reports + actual code win; reconcile by reading the code). Design doc:
`docs/design/rize-hrms-blueprint.html` §03 + §17 (wow: journey timeline, new-hire pulse,
living org chart — ALL THREE are in scope this phase).

## Scope

ONE new module `pb_onboarding` (depends: pb_lifecycle, pb_zoho_bridge, pb_assets,
pb_me_portal):
1. Buddy programme — nomination, eligibility validation, notifications, recurring
   connects, red flags, temporary buddy.
2. HRBP — assignment rules, auto-assign on arrival, HRBP card everywhere.
3. The full RIZE onboarding journey template (supersedes P0's skeleton seed): laptop via
   pb.asset.request, tool access, pre-joining intro form, welcome poster email, day-1
   manager intro with ICS attachment, credentials release (calls P1 `send_credentials`),
   data completion with escalation, orientation batch, 30-60-90 HRBP check-ins.
4. Auto-executing steps: journey steps of kind email/letter fire themselves on their due
   date (small inherit on the P0 reminder cron or task model).
5. Orientation batches (weekly/bi-weekly setting) with auto-bucketing by joining date.
6. **"New joiners" lens** on the Lifecycle hub (via P0's soft registry).
7. Portal: `/my/journey` (the WOW visual timeline + HRBP card + team + tasks),
   `/my/buddy` (buddy space), `/my/orgchart` (living org chart), and the new-hire pulse
   (day 7/30/60 one-tap check).

### Binding NON-goals
- No probation logic (P5 — the 30-60-90 check-ins are created here but probation verdicts
  are P5). No offboarding (P4). No recognition (P8).
- No Slack, no external calendar API — ICS attachments only (ruling D3).
- Do not rebuild what P0 built — extend via inherit/registry only.

## Verified plumbing facts (do NOT re-derive)
- P0 journey engine: `pb.journey.template/.step/.case/.task`, `pb.employee.checkin`,
  `pb.feedback.request`, letter engine, reminder cron, token routes `/journey/t|f/<token>`.
  Read `pb_lifecycle/models/` for exact method names; P0's `_resolve_assignee` probes
  employee fields for hrbp/buddy rules — MATCH THE FIELD NAMES IT PROBES (see P0 code);
  if it probes none, extend `_resolve_assignee` via `_inherit` instead.
- P1: `pb.zoho.pipeline` with `_after_onboard(case, rec)` hook (override here to trigger
  buddy-nomination email + HRBP assign); `send_credentials(employee)`; portal users are
  auto-created on arrival (D6).
- P2: `pb.asset.request` exists with `journey_task_id`; offboarding auto-task append
  pattern in its inherit of `pb.journey.case.action_open()` — clone that inherit shape for
  onboarding-specific augmentation (per-case task injection).
- Joining date: prefer `first_contract_date` fallback pattern
  (`pb_people/models/pb_people.py:22-30`); Zoho arrivals may have no contract → the case
  `anchor_date` from P1 IS the DOJ. Use case.anchor_date consistently.
- Buddy eligibility inputs: tenure = today - join date >= 6 months; full-time = standard
  `hr.employee.employee_type` not in ('contractor','intern') when set (field exists but is
  largely unused — treat unset as full-time, warn); "out of probation": until P5 ships a
  probation_state, use `contract.trial_date_end < today OR unset` (read
  trial via the employee's current contract; `pb_contracts/models/pb_contract_360.py:76`
  confirms the field). Same-location = `work_location_id` or company match → soft warning
  only.
- Pulse pattern (anonymous floor, salted hash): `pb_ess_workforce/models/shift_pulse.py` —
  the NEW-HIRE pulse is NOT anonymous (HR needs to follow up) so do NOT clone the
  anonymity machinery; it's a simple per-employee record. Clone only the one-tap portal UX.
- Bulk mail: publish_notify pattern (`pb_ess_workforce/models/publish_notify.py:23-53`) —
  config gate + cap + honest counts — use for the welcome poster team email.
- Portal canon: pb_me_portal controllers/security; `_prepare_home_portal_values` hook for
  `/my` counters. Frontend assets only.
- Org chart data: `hr.employee.parent_id` / `child_ids`; keep it server-rendered + light
  JS (no backend OWL in portal); cap depth/breadth (e.g. 500 nodes) and scope to the
  employee's company.
- ICS helper: P0 shipped `build_ics(...)` — use it; day-1 intro email attaches the .ics.

## Architecture

### Employee extensions (`models/hr_employee.py`)
- `pb_hrbp_user_id` m2o res.users (tracked, HR-gated write) — OR the exact name P0 probes.
- `pb_buddy_id` m2o hr.employee (tracked) + `pb_buddy_temp_id` (active temp cover).
- `pb_onboarding_case_id` computed (latest onboarding case).
- Completeness: `pb_profile_complete_pct` computed non-stored (photo `image_1920`,
  private address fields, emergency contact fields, birthday, `sex` — check which private
  fields exist on this build's hr.employee before listing).

### Models
**`pb.hrbp.rule`** — sequence, country_id optional, department_id optional,
hrbp_user_id required, active, company_id. `assign_for(employee)` first-match; action
"Backfill HRBP" (server action) for existing staff.

**`pb.buddy.nomination`** — case_id, employee_id (new hire), manager_user_id,
candidate_ids m2m hr.employee, chosen_id, state sent/chosen/confirmed, token (manager
nominates via a simple backend dialog — manager is an internal/portal user; use a
backend-lite page or the cockpit; token page optional), eligibility_report_json (per
candidate: pass/warn reasons). On confirm → write employee.pb_buddy_id + auto-emails to
buddy & new hire + schedule recurring buddy connects (`pb.employee.checkin` kind buddy,
cadence config param default every 2 weeks × 3 months).

**`pb.orientation.batch`** — batch_date, state upcoming/done, attendee_ids m2m,
company_id, notes. Config params: `pb_onboarding.orientation_freq` ('weekly'|'biweekly',
default biweekly), `pb_onboarding.orientation_weekday` (default 1=Tue). Auto-bucketing:
when an onboarding case opens (hook) attach the employee to the next batch on/after DOJ
(create the batch if missing).

**`pb.newhire.pulse`** — employee_id, day_mark Selection('7','30','60'), token,
score Selection 1-5 (one-tap), comment Char optional, state sent/answered, sent_at,
answered_at, company_id. Created+emailed by cron at DOJ+7/30/60 (idempotent); red scores
(1-2) flag the case (chatter + red_flag on a checkin or case field per P0's shape).
Token page `/journey/p/<token>` — five big tap targets, thank-you page, expired page.

**Welcome poster**: journey step (form kind) "Tell us about you" pre-DOJ (token form,
questions seeded: nickname, hometown, 3 fun facts, hobbies, photo optional (skip file
upload if the token page doesn't support it — text only is fine)); on DOJ an auto step
renders a designed HTML card (inline CSS, brand palette, no external assets) and emails it
to the new hire's department members (publish_notify pattern, cap, gate config param
`pb_onboarding.poster_mail` default '1' — keep '0' during tests).

### Journey template + auto-steps
- Seed the FULL "RIZE onboarding" `pb.journey.template` (replace/deactivate P0's skeleton
  via data, don't delete): buddy nomination [manager, case_open+0], laptop request [it,
  doj−12, links a pb.asset.request via a small glue action], tool access [it, doj−5],
  intro form [candidate, doj−1, form+token], welcome poster [auto email, doj+0],
  day-1 intro [auto email w/ ICS to manager+hire, doj+0], credentials [auto: calls P1
  send_credentials, doj+0], data completion [employee, doj+3, escalates], orientation
  [hr, doj+7 info task], (30-60-90 check-ins are created directly on case open, not steps).
- Auto-execution: inherit the P0 cron (or task model) so due tasks whose step_kind is
  'email'/'letter'/marked-auto run `action_auto()`: send the template/letter, mark done,
  log. Idempotent, per-record try/except. Credentials step = a specific auto handler
  (match by a `automation_key` Char on the step — add via inherit — values:
  'credentials','poster','day1_ics'; extensible for later phases).
- On onboarding case open (inherit like P2 did): assign HRBP if empty, create the 30-60-90
  checkins (owner = HRBP user), enrol in orientation batch, create the pulse schedule.

### New joiners lens (Lifecycle hub, soft registry)
Facade `pb.onboarding` get_board(): rows = active onboarding cases {employee, DOJ,
days_to/since, progress, buddy (name/none chip), HRBP, orientation batch, pulse status
(last score dot), data completeness %, red flags}; kpis (joining this week, missing buddy,
overdue tasks, red pulses); facets (country, department, month). Row → the P0 case detail
(reuse — link via hub lens switch to Journeys with focus, or embed the case drawer; pick
the cheaper one that stays seamless). Buddy nomination dialog launchable per row (manager
or HR): candidate list with eligibility chips (green pass / amber warn + reason).

### Portal pages (frontend)
- `/my/journey` — THE wow page: hero with progress ring + days-until/since-joining;
  vertical timeline of my case's tasks (done ✓ / current highlighted / upcoming), each
  actionable when assigned to me; HRBP + buddy cards (photo, contact); my team strip
  (manager + peers avatars); links to my pending forms. Empty state for staff with no
  case: friendly "no active journey".
- `/my/buddy` — for buddies: my buddy assignments, connect log (mark done + notes +
  red-flag toggle), next connect date, "hand over temporarily" (picks temp buddy,
  window) which emails HR. For the new hire: shows their buddy card + connect history.
- `/my/orgchart` — living org chart: server-rendered tree centred on me (up to CEO path,
  my siblings, my reports), search box (name → recentre), click any node to recentre;
  light JS only, no backend assets; cap + company scope. Linked from /my/journey team
  strip.
- `/my` home: counters card "My journey" (open tasks) via `_prepare_home_portal_values`.
- Security: own-record rules for case/task read where needed (P0 may already ship the
  task rule — check), org chart reads via controller sudo scoped to company with field
  whitelist (name, job, department, parent, image), NEVER wage anything.

## Safety rails
- Poster/pulse/buddy emails all behind config params, default OFF ('0') until tests pass,
  then set poster '1', pulse '1' as final step, and SAY SO in the report.
- Use @example.com test employees for mail-flow tests (P1's pattern); demo employees for
  read-only board tests. Clean up test records.
- Don't edit pb_lifecycle/pb_zoho_bridge/pb_assets source EXCEPT documented additive
  `_inherit` extensions inside pb_onboarding.
- Deploy `-i pb_onboarding` (+`-u pb_lifecycle` ONLY if you had to touch it — prefer not).

## Numbered test cases
T1. Deploy clean; registry loads.
T2. Simulate a Zoho arrival (P1 webhook or wizard) with DOJ ~10 days out → onboarding case
    opens with the FULL template; HRBP auto-assigned per rule; 30-60-90 checkins exist
    owned by HRBP; employee lands in the right orientation batch; laptop request created
    (needed_by = DOJ−12..−10) linked to its journey task.
T3. Buddy nomination: as the manager (or HR), open the dialog → candidates show
    eligibility chips (verify one ineligible: <6 months tenure shows red with reason);
    choose one → employee.buddy set, buddy connects scheduled, 2 mails queued (buddy +
    hire) — inspect mail.mail, don't send to real people.
T4. Temp buddy: set a temp cover → connects reassigned for the window; HR notified.
T5. Intro-form token page: fill as the candidate (logged out) → answers stored; poster
    auto-step on DOJ renders the card (force-run the auto step) → mail queued to the
    department ONLY (cap respected); with poster param '0' → skipped with honest log.
T6. Day-1 auto step → email with a valid .ics attachment (opens in a calendar app —
    validate the ICS text: DTSTART/DTEND/ORGANIZER/ATTENDEE present).
T7. Credentials auto step → exactly one invite mail queued for the portal user (P1 path);
    running twice doesn't double-send.
T8. Data completion: employee with missing photo/address shows completeness <100% on the
    lens; the escalation path (past escalation_days) queues the HR escalation mail.
T9. Pulse: force day-7 pulse → mail queued with token link; tap score 2 on the token page
    → recorded, case red-flagged, lens shows the red dot; day-30 cron run is idempotent.
T10. `/my/journey` as a test portal user: timeline renders (done/current/upcoming), HRBP +
    buddy cards show, team strip present; SCREENSHOTS light+dark (portal pages follow the
    site theme — verify legibility in both).
T11. `/my/buddy` as the buddy's login: connect log + mark-done + red flag work; new hire
    sees buddy card.
T12. `/my/orgchart`: renders centred on the user, search recentres, click-through works,
    caps respected; another company's people absent.
T13. New joiners lens on Lifecycle hub: board correct (buddy/HRBP/pulse/completeness
    columns), facets work, ⌘K entries navigate.
T14. White-label grep zero; plain English; no emoji anywhere (Lucide only).
T15. Regressions: P0 Journeys lens + P2 Assets lens still load; an offboarding case still
    auto-appends asset tasks.
T16. Tidy up; enable poster+pulse params; report final param states.

## Deliverables / report back
Commits, per-test results, deploy EXIT, deviations, ledger gotchas appended, the
`automation_key` values registered (P4/P5/P7 will add more), exact employee field names
used for HRBP/buddy (P5 needs them), portal route list, and screenshots referenced.
