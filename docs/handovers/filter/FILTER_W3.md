# FILTER wave 3 — Hiring (roles, interviews, applicants, offers)

Read first: `FILTER_LEDGER.md`, `FILTER_WAVE_COMMON.md`, INVENTORY.md §9–§12.
Wave id `w3`, stage `/tmp/pbf_stage_w3`, preview holder `w3`.
Report: `docs/handovers/filter/FILTER_W3_REPORT.md`.

All four live in `pb_hiring`, two components (`hiring_board.js` for Roles +
Interviews, `hiring_registers_p9.js` for Applicants + Offers). One facade
model `pb.hiring` already exists: give it the mixin with `ctx: {kind}`
(ledger §3a): `kind in ('roles','interviews','applicants','offers')` picks
`_pbf_model`, spec, views and `_pbf_screen()='hiring:<kind>'`. Each tab
owns ONE kit (`useFilterKit` per tab component, or one kit per tab in the
host with `reconfigure` on tab switch — pick the simpler; the Roles tab is
the heaviest Learn screen, so keep its DOM anchors).

### 1. Roles (§9) — `pb.hiring.requisition`, screen `hiring:roles`
- PIN `step` (choice cloning `stageOf`), PIN `status` (`state`), PIN
  `department`; `country`, `recruiter`, `request` (`request_state`),
  `budget` (`budget_status`), `role_type`, `manager`
  (`reporting_manager_id`), `wanted_by`, `opened`, `headcount` (number),
  `has_candidates` (choice `applicant_ids != False`).
- Views: Open roles · Over budget · Nobody asked yet · Filled · Opened this quarter.
- `waiting`/`waiting_mine`/`mine` stay glance figures (per-reader Python,
  R2) unless a `domain_method` over the cover scope answers in < 300 ms —
  try it, report the timing, decide.
- The same RPC used to return `interviews`: the Interviews tab now loads its
  own page (below); keep `get_board` returning what the Overview tiles need.
- Learn: 105 lesson hits on screen `hiring`; replica `hiring` redraws the
  filter strip; anchors `hi-*` unchanged; add `coach="'hi-filters'"`.

### 2. Interviews (§10) — `pb.hiring.interview`, screen `hiring:interviews`
- Base = company + the 42-day window OR feedback pending (as `_interview_rows`).
- PIN `when` (`start`, past+future presets + custom), PIN `state`, PIN
  `role` (`requisition_id`); `kind`, `mode`, `recruiter`, `job`, `round`
  (number), `opinions` (choice: late = `feedback_ids any [state=pending,
  due < now]`; waiting = pending any).
- Views: Today · This week · Opinions late · Called off recently.
- "Send the reminders due now" stays in the toolbar slot.

### 3. Applicants register (§11) — `hr.applicant`, screen `hiring:applicants`
- Base = roles the reader may see (`_p9_roles`) → `job_id in jobs` and the
  `active_test=False` context the current search uses; counts and pages
  under the same sudo + privacy mask the register applies today
  (`_pbf_records()` override) — never wider.
- PIN `family` (choice from `FAMILY_DOMAINS`), PIN `role`
  (`pb_requisition_id`), PIN `recruiter` (`pb_requisition_id.recruiter_id`);
  `stage` (`stage_id`), `screen` (`pb_screen`), `applied` (`create_date`),
  `moved` (`date_last_stage_update`), `source` (`source_id`), `hold`
  (`pb_hold_until`), `authorisation`, flags `waiting_mine` / `late` /
  `iv_week` / `duplicate` as choices with `domain_method` if they can be
  computed in one query each (time them); otherwise keep them as
  post-filter chips in the toolbar slot and say so.
- Views: In play · Waiting on me · Opinions late · Interview this week · Possible duplicates.
- Kanban: columns stay per stage; cards = the kit's page (page size 120 for
  a board, "Show more" appends); column counts from the kit's `stage`
  section counts (R1). Drag + bulk move act on the shown cards (R6).
- `openRegister(tab, {flag, step})` doors → `initial` / `kit.setFilters`.
  Migrate the localStorage memory (`APPS_DEFAULT`) by dropping it: the kit
  remembers per tab.
- Learn: anchors `hi-applicants`, `hi-applicants-board` stay on their
  wrappers; none quoted in lessons.

### 4. Offers register (§12) — `pb.hiring.offer`, screen `hiring:offers`
- PIN `step` (choice grouping `state` per `OFFER_STEPS`), PIN `state`, PIN
  `role`; `recruiter`, `start` (`start_date`), `sent` (`sent_on`),
  `decision` (`candidate_decision`), `manager`, `joined` (`joined_on`),
  `docs` (choice overdue), `check` (`bgv_id.state`), `monthly`
  (number, only when `show_money`: hide the section otherwise — build the
  spec conditionally).
- Views: With the candidate · Joining in 30 days · Documents overdue · Joined this month · Turned down.
- Overview tiles read `_p9_offer_rows`: keep them in sync by having the tile
  counts come from `pbf_counts` (R4/R1).
- `waiting_mine` = `_chain_my_seat()` → `domain_method` if one query; else glance.

## Wave-specific tests
- W3-T1 Roles: a reader limited by cover scope sees the same roles in the
  panel counts as in the list (create a limited user on the preview).
- W3-T2 Applicants: drag a card between columns after filtering; the card
  moves and counts update; bulk move acts only on shown cards.
- W3-T3 Offers: tile "Documents overdue" on the Overview equals the view count.
- W3-T4 Tab switch Roles → Interviews → Applicants → Offers keeps each
  tab's own filters (reconfigure or per-tab kits) with no console errors.

## Report back
`FILTER_W3_REPORT.md` per `FILTER_WAVE_COMMON.md §E`.
