# ETP — conventions & gotcha ledger

Every handover in this program references this file. Add a row whenever a new gotcha is hit. Program doc:
`ETP_PROGRAM.md`. TIERS rules T-R1…T-R12 and ledger rows T1–T37 (`../tiers/TIERS_LEDGER.md`) bind here too.

## Standing rules (bind every phase)
- **E-R1 One feature, one auto-install glue module; pb_me_portal is read-only for phase agents.** `pb_me_expense`,
  `pb_me_trip`, `pb_me_project_time` each depend on `pb_me_portal` plus their backend module. The home tiles,
  words and glyphs already exist in pb_me_portal 19.0.3.4.0. A phase that believes it must edit pb_me_portal (or
  any other shared module) stops and lists the change in its report instead.
- **E-R2 A portal seam is `sudo()` after an explicit ownership guard** (T-R11): the guard is "the record's
  employee is one of `_ess_own_employees()`"; `employee_id` is never read from the request; no `base.group_portal`
  ACL row or rule, ever. `sudo()` keeps `env.user`, so `create_uid`, the engine's submitter and the message author
  stay the employee.
- **E-R3 Under sudo the stock guards are off — the module re-states every guard it relies on.** Ownership, state
  ("only a draft may be edited"), company (`company_id` = the employee's company, never `env.company`), and a
  **whitelist of accepted fields** (`state` / `approval_state` / `manager_id` are never taken from the request).
- **E-R4 Every decision goes through the one approval engine** (biz_approval_workflow): claims and trips show their
  route step ("With your manager", "With finance"), the refusal reason, and a blocked route as a plain sentence
  with a next step ("Nobody is set up to approve this yet — Ask HR"). A request never hangs silently.
- **E-R5 Uploads**: bounded read (`read(MAX + 1)`), mimetype allowlist `image/jpeg, image/png, image/webp,
  application/pdf`, 10 MB cap, the attachment bound to its record only after the record exists (savepoint; unlink
  the attachment on failure). The form carries `enctype="multipart/form-data"` and `accept="image/*,.pdf"` with
  `capture="environment"` on the camera button only.
- **E-R6 Everything an employee login sees carries a token** (T14/T20): receipt images and downloads use
  `access_token`; an HttpCase as the share user proves each one is 200.
- **E-R7 Tests run on the ASSIGNED clone and port only** (`ETP_PROGRAM.md` table) — never on p0clone when you were
  given p1clone, never the live service, never a `-u` on a live database. Stage into your own `/tmp/deployEx`.
- **E-R8 Every page works without JavaScript** (plain form POSTs); JS enhances (autosave, live preview, keyboard).
  Server facts travel in `data-*` attributes; the interaction class pattern is `pb_ess_workforce/static/src/interactions/clock.js`.
- **E-R9 PO entries need three lines** (`#. module:`, `#. odoo-python` / `#. odoo-javascript`, an occurrence) and
  a non-empty `msgstr` with no vendor name; run the parse gate (T3A_HANDOVER §3) on every `.po` you write.
- **E-R10 The design bar is binding** (owner, verbatim): "extreme WOW, intuitive, out-of-this-world experience,
  best in class." Hero moment named in the report; zero dead-ends; plain words; motion with purpose; keyboard +
  bulk ergonomics where rows are involved; measured against the best consumer/SaaS tool in the category (Expensify
  / Rydoo for receipts, TravelPerk for trips, Harvest / Toggl / Clockify for the week grid), never against stock.
  Look = MEHOME's (`pbme-*` classes, pbim tokens, Inter, Lucide SVG; no emoji, no gradients, no Font Awesome, no
  stock portal tables).
- **E-R11 Fable deploys.** An agent never starts, stops or upgrades the live service and never writes to a live
  database. Browser walks run against the staged clone instance over a tunnel (T3B_REPORT §T3b.12) with a
  temporary employee login that is archived afterwards.
- **E-R12 Lessons follow screen changes**: grep Learn (`pb_learn/static/content/learn_content.json`,
  `pb_learn/static/src/anchors.json`, `pb_learn/static/src/engine/{screens,fixture}.js`) for the home and `/my`;
  update words if a lesson describes them; never write a new lesson; report.
- **E-R13 Never the vendor's name in a user-visible string** (T-R4); plain English everywhere a person reads.

## Ledger
| # | Date | Gotcha / fact | How to apply |
|---|---|---|---|
| E1 | 2026-10-16 | Stock `hr.expense` in 19: no `hr.expense.sheet`; `state` is computed from a STORED `approval_state` (`submitted/approved/refused`, `hr_expense/models/hr_expense.py:122-143`, server copy) plus the move; `action_submit` (`:1125-1139`) auto-approves when the employee has neither `manager_id` nor `expense_manager_id` (`_can_be_autovalidated` `:1141-1144`). On payobook 12 of 20 portal-login employees would be auto-approved. | E1 never calls `action_submit` from the portal; the claim writes `approval_state='submitted'` under sudo and the shared engine decides (`_do_approve` / `_do_refuse(reason)`, `:1440-1473`). |
| E2 | 2026-10-16 | The engine's adapter mixin declares a computed `approval_state` (`biz_approval_workflow/models/adapter.py:39-41`); stock `hr.expense` has a stored one with other values. Mixing the adapter straight into `hr.expense` would corrupt the expense state machine. | The approval carrier is a NEW model `pb.expense.claim` (1..N expenses) wired with `register_chain` exactly like `pb_training/models/claim_approval.py`; `hr.expense` is never given the mixin. |
| E3 | 2026-10-16 | No approval route exists for expenses (0 processes, 0 requests); trips have process key `trip` with a default route laid by `pb_business_trip/models/pb_business_trip_approval.py:94-109` + `post_init_hook` (`__init__.py:11-13`) and a migration script. | E1 adds process key `expense` with the same default route shape (Their manager → Finance approver) laid by its post_init_hook for every company, cloned from the trip module. |
| E4 | 2026-10-16 | Receipts on an expense: `attachment_ids` (One2many on `ir.attachment`, `res_model='hr.expense'`), `message_main_attachment_id` from `mail.thread.main.attachment`; `create_expense_from_attachments` (`:1234-1267`) shows the shape: create, write `res_model/res_id` on the attachment, `_message_set_main_attachment_id(att, force=True)`. `action_get_attachment_view` / `attachment_number` do not exist in 19. | Clone that shape. Duplicate-receipt detection reads `message_main_attachment_checksum` — setting the main attachment keeps it working. |
| E5 | 2026-10-16 | Expense categories = `product.product` with `can_be_expensed` (7 on payobook: Meals FOOD, Travel & Accommodation TRANS & ACC, Mileage MIL, Gifts GIFT, Communication COMM, Expenses EXP_GEN, Travel Expense from pb_trip_expense_bridge), all `company_id` NULL. Only Mileage has a cost (company 1), where stock computes quantity × price. | The category picker lists `can_be_expensed` products whose company is empty or the employee's; Mileage (a product with `standard_price`) is left out of this release (non-goal). |
| E6 | 2026-10-16 | `pb.business.trip` under sudo skips `_approval_can`, the rate/approved write locks (`pb_business_trip.py:292-313`), the line locks (`:401-427`) and the `state` guard in `biz_approval_mixin.py:106-123`; `action_cancel`/`action_reset_to_draft` have no permission check at all. | E2 re-states: owner check before every sudo call; edits only in `draft`; cancel only from `submitted/manager_approved/finance_approved` (approved → "Ask HR"); field whitelist; `employee_id`/`company_id` set explicitly. |
| E7 | 2026-10-16 | The trip onchange never passes a city tier, so a Vietnam destination always matches the 150k "Other cities" policy (`pb_trip_policy.py:41-65` `_match`). Policies live only on destination + company, never on the employee. | E2's form asks "Major city (Hanoi / HCMC)?" only when a tier-1 policy exists for the country and passes the tier to `_match`. |
| E8 | 2026-10-16 | Trips: `_guard_trip_overlap` (`:256-270`) refuses a trip overlapping the same employee's submitted/approved trips; `_leave_overlap_warning` only posts a chatter note. `action_cancel` on an APPROVED trip deletes draft expenses and is refused when one is already submitted (`pb_trip_expense_bridge.py:118-133`). Withdrawing from the inbox (`engine.cancel`) is not mirrored on the trip (no `_approval_withdraw` in the shim). | Portal: overlap message is shown as the reason; approved trips cannot be cancelled from the portal; the trip page reads the request state, not only `state`, so an inbox withdrawal shows truthfully. |
| E9 | 2026-10-16 | Timesheet lines: `hr_timesheet/models/hr_timesheet.py` (server copy) — `create()` `:214-357` derives company/accounts from the project, `name` empty → `'/'` (`:262-263`), needs an active employee; `_check_can_write` `:202-208`; `project_timesheet_holidays` blocks writing/deleting leave-generated lines (`models/account_analytic.py:31-59`) and creating on the leave task. CE 19 has no `validated` field. Portal users have NO active ACL/rule on `account.analytic.line` (stock portal rows ship inactive); `base.group_user` has none either. | E3 reads and writes under sudo after the ownership guard; leave lines render read-only; the picker excludes `company.leave_timesheet_task_id`; weekly lock/approval is a non-goal. |
| E10 | 2026-10-16 | Pickable projects for an employee mirror the stock internal-user rule: `allow_timesheets`, not a template, active, `company_id` in (empty, employee's company), `privacy_visibility in ('employees','portal')` or the employee's partner follows it. Every company but Payobook Singapore has an "Internal" project (Training / Meeting / Time Off tasks). Projects 1–6 on payobook are stock demo data with no company. | E3's facade re-states that rule in Python (sudo search + filter), never a new rule. |
| E11 | 2026-10-16 | `biz_week_grid` (the backend week grid) loads only in `web.assets_backend`; the portal bundles are lean by rule. | E3 writes its own grid in QWeb + SCSS + one interaction (borrow the `--bwg-*` look, not the code). |
| E12 | 2026-10-16 | Portal vocabulary: inner pages use `.pbme-btn--primary/--ghost`, status pills `.pbme-pill--act/--wait/--no` (`me_portal.scss:243-258`); the HOME uses `.pbme-btn--pri/--out` and `.pbme-badge--<tone>` is an icon tile there, not a pill. Icons: `pb_me_portal.ess_icon` with `t-value="'name'"` (W87); any glyph a module needs beyond the registry it draws in its OWN icon template (`pb_ess_workforce.work_icon` precedent). | Use the inner-page vocabulary on pages, the home vocabulary inside home cards; never add a branch to `ess_icon`. |
| E13 | 2026-10-16 | `createdb -T p0clone` fails while the live job runner holds sessions on it (T18). | Clones are made with `pg_dump -Fc p0clone \| pg_restore -d <db>` plus a filestore copy (`/odoo/.local/share/Odoo/filestore/<db>`). p1clone/p2clone exist (2026-10-16). |
| E14 | 2026-10-16 | A route seat is a READ only (`trip_rule_seat`). When a seated person decides, the shim writes the trip's new status AS THAT PERSON (`chain_shim.py:474` `_approval_advance` → `_chain_engine_write`); a holder without a write-capable trip group gets "could not follow its own route": the decision stands, the trip stays one state behind. (E2 report) | Seat Finance approver / HR lead with people in those groups (the default seed does); test fixtures get the real groups. Shim-side fix (`sudo()` on the consumer write) listed in E2_REPORT §6, not done. |
| E15 | 2026-10-16 | The engine accepts a responsibility holder only when its dates cover the REQUEST date (`responsibility.py:116`); a trip's request date is `date_from`. On the clones the holders start 2026-09-15, so stock `pb_business_trip` tests (August 2026 trips) block: `TestBusinessTrip.test_01–07, 12`. | Known clone/data errors; do not chase in a phase run. On payobook every seat is held by the admin login from 2026-09-15. |
| E16 | 2026-10-16 | pb_me_portal 19.0.3.4.0's `TestMeHome.test_02` pinned the Me order without `/my/expenses`. | Fixed by Fable in the E2 commit (the pin now lists Expenses last). |
| E17 | 2026-10-16 | QWeb term grouping merges an empty inline `<span/>` with the next inline text (a switch's knob span swallowed its label into one translatable term with indentation). | Put label text in its own block element next to purely decorative spans. |
| E18 | 2026-10-16 | `Intl.DateTimeFormat` puts the month first in en-US; compacting "12–14" from its output gives "12–Nov 14". | Build "d MMM" from `formatToParts` to mirror babel's `d MMM`. |
