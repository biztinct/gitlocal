# FILTER wave 1 — People lifecycle boards (the straightforward five)

Read first, in this order: `FILTER_LEDGER.md` (all of it), `FILTER_WAVE_COMMON.md`,
then INVENTORY.md §1, §4, §5, §7, §8 (the verified plumbing with file:line —
do not re-derive it). Reference implementation: `pb_people`.

Wave id `w1`. Stage dir `/tmp/pbf_stage_w1`. Preview holder name `w1`.
Report file: `docs/handovers/filter/FILTER_W1_REPORT.md`.

## Screens (build in this order)

### 1. Contracts — `pb_contracts` (INVENTORY §1)
- Facade `pb.contracts` inherits the mixin; `_pbf_model='hr.contract'`,
  `_pbf_screen='contracts'`, base domain = the board's company domain.
- Sections (keys/paths from §1): PIN `status` (`state`, selection), PIN
  `structure` (`struct_id`), PIN `ends` (`date_end`, presets future); then
  `step` (choice cloning `step_dom` — draft / running / ending within 30 days /
  ended), `starts` (`date_start`, past), `department`
  (`employee_id.department_id`), `job`, `category` (`type_id`), `wage`
  (money), `trial` (`trial_date_end`, future), `company`.
- Views: All · Running · Ending within 30 days · Draft · Started this month.
- The 4-step strip stays as `QuietSteps`, but its counts come from the kit
  (`kit.counts.step.values`), and pressing a step = `kit.toggleFilters({step:[key]})`
  (ruling R1). The `"open"` double-step case: `running` = state open and
  (no end date or end date > 30 days); `ending` = state open and end date
  within 30 days — write both as domains, no client re-check.
- Remove: search/date/structure chip rows; `filtered`/`_inDate`; the 240 cap.
  New `get_contracts_page(filters, search, sort, offset, limit=60)`.
  Keep `get_board` for the numbers + step counts if the hub reads it
  (R4), minus its 240 rows.
- Keep: `pb_contracts_drawer` soft registry, `?contract=` deep link,
  `HubBackChip`, "showing" line now from the kit (`kit.matched`).
- Learn: anchor `ct-filters` (reserved) → goes on `<PbFilterLayout coach="'ct-filters'">`;
  replica `contracts()` in `screens.js` redraws the filter strip like the
  Employees one (view tabs + Filters + search chips); update
  `anchors.json` desc. Lessons that quote `ct-roster`/`ct-kpis` are unaffected.

### 2. Journeys — `pb_lifecycle` (INVENTORY §7)
- `_pbf_model='pb.journey.case'`, screen `journeys`, base = draft/active/on_hold + company.
- PIN `type` (`case_type`), PIN `status` (`state`), PIN `department`
  (`employee_id.department_id`); `key_date` (`anchor_date`), `checklist`
  (`template_id`), `source`, `progress` (number, unit none), `opened`
  (`date_opened`), `job`, `company`, `late` (choice, literal domain
  `[('task_ids','any',[('state','in',OPEN_TASK_STATES),('due_date','<',today)])]`),
  `step` (choice: start / running / wrap, as §7).
- Views: All · Running now · Steps overdue · Not started · Nothing left to do.
- `templates`/`types` keep shipping in the head payload for the start dialog.
- Learn: none (verify with the grep in the report).

### 3. Awards — `pb_comp_ben` (INVENTORY §8)
- `_pbf_model='pb.incentive'`, screen `awards`, base = company or no company (`:83`).
- PIN `where` (choice cloning `stepOf` incl. refused), PIN `kind`, PIN `month`
  (`period_month`, past presets + custom); `person`, `department`, `run`,
  `amount` (money), `approval` (`state`), `fulfilment`, `source`, `asked_by`,
  `letter` (choice `letter_id` set / not).
- Views: All · Waiting for approval · Agreed, not in a run · In a pay run · Paid this month.
- The refusal payload (`_refusal`): override `pbf_layout` to return
  `{'refused': …}` under the same condition (ledger §3a).
- Learn: replica `awards()` — the filter strip; anchors unchanged.

### 4. Growth plans — `pb_pip` (INVENTORY §4)
- `_pbf_model='pb.pip.case'`, screen `growth`, base = company.
- The Open/Closed toggle becomes two built-in views (Open plans is the first
  = default; Closed plans). PIN `stage` (`state`), PIN `owner`
  (`hr_owner_user_id`), PIN `ends` (`end_date`); `department`, `asked_by`,
  `template`, `starts`, `rhythm`, `seen` (choice on `employee_ack`),
  `outcome` (`verdict`), `overdue` (choice: `end_date < today` and active).
- Views: Open plans · Closed plans · Waiting on a decision · Ending within 7 days
  (`ends` custom range today..today+7 — use preset `next_30` if the kit has
  no 7-day preset and say so) · Not yet seen.
- `drifting` stays a card badge (non-stored compute, R2) — note as debt.
- `_can_read` refusal → `pbf_layout` override as in Awards.
- Learn: replica `growth()`.

### 5. New joiners — `pb_onboarding` (INVENTORY §5)
- `_pbf_model='pb.journey.case'`, screen `joiners`, base = onboarding +
  states + the 120-day floor (`:85`) + company.
- PIN `first_day` (`anchor_date`, both past and future matter: use presets
  `past` and add the custom range), PIN `step` (choice ready / settling /
  done as §5), PIN `department`; `buddy` (`employee_id.buddy_id`, none "No
  buddy yet"), `hrbp`, `country`, `checklist`, `status`, `source`, `manager`,
  `overdue` (choice via `task_ids any`).
- Views: All · Joining this week · Still without a buddy · Steps overdue · Started, checklist open.
- Stand-in buddies (`buddy_temp_id`): the `buddy` section counts the main
  buddy only; say so in the section `help`.
- Learn: replica `joiners()`.

## Wave-specific tests (on top of §C)
- W1-T1 Contracts: press step "Ending soon" → chip "Where it is · Ending within
  30 days" and the step lights; press again → everyone.
- W1-T2 Journeys: "Steps overdue" view count equals a manual
  `search_count` of the `any` domain on the preview (`odoo-bin shell`).
- W1-T3 Awards: a user who is refused by `_refusal` gets the screen's refusal
  and no panel errors in the console (use the preview admin and temporarily
  remove the group in the preview DB, or prove it from shell).
- W1-T4 Growth plans: switch Open → Closed view; the step strip hides in
  Closed as before.
- W1-T5 New joiners: "Still without a buddy" lists only people with no buddy.

## Report back
`FILTER_W1_REPORT.md` per `FILTER_WAVE_COMMON.md §E`. Commit per screen in
your worktree branch; do not merge or push.
