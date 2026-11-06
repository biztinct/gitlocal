# FILTER wave 4 — HR services (Ask HR, Assets, Praise, Vendors, Approvals inbox)

Read first: `FILTER_LEDGER.md`, `FILTER_WAVE_COMMON.md`, INVENTORY.md §13–§17.
Wave id `w4`, stage `/tmp/pbf_stage_w4`, preview holder `w4`.
Report: `docs/handovers/filter/FILTER_W4_REPORT.md`.

### 1. Vendors — `pb_vendor_access` (§16) — start here, it is the easiest
- `_pbf_model='pb.vendor'`, screen `vendors`, base = company.
- PIN `type` (`vendor_type`), PIN `agreement` (`agreement_state`, none "No
  agreement yet"), PIN `owner` (`responsible_user_id`); `department`,
  `country`, `next_end` (`next_end_date`, future), `mine` (choice
  `responsible_user_id = uid`), `company`.
- Views: All · Coming up for renewal · Already run out · Nothing recorded · I look after.
- Search: the folded Python search existed for "Bùi"; override
  `_pbf_search_domain` to OR the plain `ilike` with an unaccented match if
  the DB has `unaccent` (check `select * from pg_extension`), else note the regression.
- The headline sentence now reads `kit.matched`.

### 2. Praise — `pb_rnr` (§15)
- `_pbf_model='pb.rnr.nomination'`, screen `praise`, base = company.
- PIN `step` (choice grouping `state`), PIN `value` (`value_id`), PIN
  `nominee`; `outcome`, `nominator`, `department` (`nominee_id.department_id`),
  `cycle`, `written` (`submitted_at`), `decided` (`decided_at`), `winner`
  (choice `is_winner`), `public` (choice), `amount` (money).
- Views: Waiting on a manager · Waiting on HR · Not this time · Given money this quarter · Quarter winners.
- `this_month`/`awarded_qtd` glance figures → `toggleFilters` with the
  matching sections.

### 3. Assets register — `pb_assets` (§14)
- `_pbf_model='pb.asset'`, screen `assets`, base = company. The Requests
  segment stays as it is.
- PIN `status` (`state`; label per kind is a display concern: show the
  generic state label and put the kind-specific wording in the card), PIN
  `kind`, PIN `category`; `country`, `holder` (`current_employee_id`),
  `department` (`current_employee_id.department_id`), `warranty`
  (`warranty_end`, future presets), `bought` (`purchase_date`), `arrived`
  (`delivery_date`), `cost` (money), `reused` (choice), `company`.
- Views: Spare physical · Out with people · Under repair · Warranty ending in 60 days (next_90 if no 60) · Switched-off accounts.
- Bulk bar: "pick all visible" picks the kit's page; `bulk_set_state` gets
  ids from the page (R6). Add "Select everything matching (N)" through one
  server call that takes `filters`/`search` and returns ids (cap 2,000 with
  a plain-English note when capped).

### 4. Ask HR (Home lens) — `pb_ask_hr` (§13)
- `_pbf_model='pb.ask.hr.ticket'`, screen `askhr`, base = the record rules
  already split employee/HR: no base domain beyond what `get_board` applied.
- PIN `step` (`state`), PIN `category`, PIN `owner` (`user_id`, none
  "Nobody has it yet"); `mine` (choice `user_id = uid`), `asker`,
  `department`, `asked` (`create_date`), `answered`, `closed`, `closed_by`,
  `company`. `late`/`waiting_days` stay glance figures (R2) unless one query
  answers "new and older than 2 working days" — try `domain_method`.
- Views: Nobody has it yet · Mine · Answered this week · New, waiting · Closed (lifts the 60 cap).
- The step strip stays the primary control: counts from the kit, press =
  `toggleFilters`. Bulk take/hand/close act on shown cards (R6).
- Embedded lens: the Home hub owns the title (W17); `PbFilterLayout` has no
  title. Drop the per-user localStorage filter memory (the kit remembers).
- Learn: replica `askhr` strip; anchors `ah-*` unchanged; add `coach="'ah-filters'"`.

### 5. Approvals inbox — `pb_approval_config` (§17) — the hard one, do it last
- `_pbf_model='biz.approval.request'`, screen `approvals`. The Mine / My
  team / Everyone scope swaps the searching model (user vs sudo): keep the
  scope row as the screen's own control ABOVE the panel and pass it as
  `ctx: {scope}`; `_pbf_records()` returns the same model/sudo the facade's
  `_scoped` picks for that scope; `_pbf_base_domain` = the scope's domain.
  Changing scope → `kit.reconfigure({ctx:{scope}})`.
- The four tabs become the first four built-in views (same wording: the 42
  lessons and PayAI doors use it). PIN `pile` (choice grouping `state`), PIN
  `area` (`process_id.area`), PIN `due` (`due_at`: today / late presets —
  add `overdue` = `due_at < now` as a choice if presets cannot express it);
  `process`, `company`, `submitted`, `sent_by`, `amount` (number; never
  summed), `currency`, `my_turn` (choice via `domain_method` =
  `seat_ids.acting_user_id = uid` AND `_is_mine`, one query).
- Views: My turn today · Late · Sent back to me · Finished this month · Pay area waiting.
- Arrival/`locate_request` → `initial` filters + scope; external doors by
  tag keep working (test from Records Desk's door).
- Cursor paging exists server-side: use it for the page (`list_requests`
  already takes a cursor); page size 60.
- Learn: 42 lessons on `approvals`, replica `approvals`; anchors `ai-*`
  unchanged; `coach="'pbam-filters'"` on the layout + declare it.

## Wave-specific tests
- W4-T1 Vendors: search "bui" finds "Bùi …" (or the report says it does not and why).
- W4-T2 Assets: tick a status, "Select everything matching", run a bulk
  state change on the preview → only matching assets change.
- W4-T3 Ask HR as a plain employee user (preview): counts show only their tickets.
- W4-T4 Approvals: scope Mine → My team → Everyone; counts change; a door
  from Records Desk lands on the right request with the panel pre-set.

## Report back
`FILTER_W4_REPORT.md` per `FILTER_WAVE_COMMON.md §E`.
