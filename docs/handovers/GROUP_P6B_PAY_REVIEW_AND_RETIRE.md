# GROUP Phase 6b — "Pay, part two": Pay Review, Pay changes, the migrations, and the old module retired

Read `docs/handovers/GROUP_LEDGER.md` FIRST and fully (rules, rulings G1–G9 — **G7** and
**G9** are this phase's charter — plumbing "Legacy module" (what depends on it), gotchas
GR1–GR45), then the P6a phase-log entry and `pb_pay` as built (`pb.pay.band`,
`pb.pay.position`, the Pay lens with its greyed Review/Changes tabs, the fairness facade),
then Part G of `docs/design/group-blueprint.html` (Pay Review, Pay changes, "Where the old
pieces went", "What is kept from the old data"), then the legacy inventory in
`docs/design/one-group-many-payrolls.html` (Question 1 + engineer fold: the seven screens,
the two external writes, `wfp.budget.actual` and pb_budget's seven writer sites).

## 0. What you are building, in one paragraph

The second half of **Pay**, and the end of the old planning module. **Pay Review** runs a
pay review in one screen: it opens with a suggested raise already filled in for every
person from a **guidance grid** (performance across, position in band down), the budget
meter already showing what that costs, and the fairness check already run; managers adjust
in a worksheet or by dragging dots in a **calibration** view; limits explain themselves on
the row; the review cascades through manager → HR → finance → CEO on the platform's
approval chain with real tasks on Home; **apply** previews every contract that will change,
writes the new pay, queues it for the next pay run, prints each person's letter through
the existing letter engine, and keeps a one-click undo for 24 hours; the employee sees
"Your pay, explained" in the portal. **Pay changes** handles a promotion or correction
outside a review through the same guidance, limits, approvals and letter. Then the
**migrations** move every old record into the new world (merit matrices → guidance grids,
compensation cycles → read-only past reviews, performance ratings → a "legacy" rating
snapshot, the budget table → `pb.budget.line` with row-count parity), the People hub's Plan
lens is un-hooked from the old groups and its classic fold removed, and
`pb_hr_workforce_planning` is **uninstalled** on every database behind a pre-flight gate
that refuses if any parity check fails.

## 1. Scope and binding non-goals

Deliverables:
1. `pb_pay` 19.0.2.0.0: `pb.pay.guidance` (+ cells), `pb.pay.rating`, `pb.pay.review`
   (+ lines, limits), `pb.pay.change`, `pb.pay.apply` (undo records), review facade,
   calibration, live fairness, cascade on `biz.approval.chain.mixin`, apply + undo,
   letters, portal page, Review and Changes tabs un-greyed, ⌘K rows 3430–3450, tests,
   `vi_VN.po`.
2. `pb_budget` bump: `pb.budget.line` replaces `wfp.budget.actual` (fields per
   `budget_ext.py:64-127`), all seven writers and every reader/rule/view repointed,
   migration with row-count parity, dependency on the legacy module removed.
3. `pb_people_hub` bump: `PLAN_GATE` → `pb_decision_room.group_decision_user/manager`,
   `PLAN_CARDS` and the classic fold removed, dependency removed, tests rewritten (the
   directory-walk test and the seven-card tests retired).
4. `pb_lifecycle` bump only if a letter type or placeholder is missing.
5. Uninstall `pb_hr_workforce_planning` on p9clone → payobook → abm → payobook_template
   after the gate (§3.8), with `pg_dump` before each and a post-uninstall smoke walk.
6. Chrome walks; commits; ledger; report.

Non-goals (do NOT build):
- No performance-review product: ratings are entered, pasted, or synced per review
  (a `pb.pay.rating` row per person per review), not managed as a workflow.
- No accounting. No stored converted amounts. No new `pb.sidebar.item`.
- Apply writes `hr.contract.wage` (this IS the one intended write, with preview, approval
  and undo); nothing else in `hr.*` is written.
- No email sending of letters in this phase beyond what `pb.hr.letter.action_send`
  already does; generating and filing them is the requirement.

## 2. Design (the bar, the hero, the copy)

**The bar (owner's words, verbatim): "extreme WOW, intuitive, out-of-this-world
experience, best in class."** Hero: **guidance first, then judgement.** A new review for
"Retail scheme · 2027" opens already filled: 902 rows each with a suggested raise, the
budget meter at "₫12.4B of ₫15B", the fairness line "this review narrows the gap in Bread
from 3.6% to 3.2%", and three rose chips where a suggestion breaks a limit. Select a
block, type "+1", and the rows, the meter and the fairness line move together. Second
hero: **calibration** — every person a dot, rating across, proposed raise up; drag a dot
and the row, the meter and the sentence follow; outliers ring in rose. Third: **apply,
safely** — a preview of every contract that will change, in local currency with the date;
Apply; a green strip "Applied to 902 contracts · undo until 14:02 tomorrow"; letters
filed; the pay run sees the new pay. Benchmarks: Lattice, Pave, Carta, Workday; our edge:
payroll-native apply. Copy: "Review", "Guidance", "Proposal", "Budget", "Limits", "Send
for approval", "Approve", "Apply", "Undo", "Letters", "Your pay, explained", "Pay change".
Never "cycle", "matrix", "compa", "guardrail", "recommendation" on screen. Zero dead-ends
(§8). Keyboard: worksheet is a grid (arrows, Enter to edit, Shift+arrows to select a
block, Ctrl/Cmd+V paste), Esc closes drawers (WF4).

## 3. Server design

### 3.1 Guidance grid — `pb.pay.guidance` + `pb.pay.guidance.cell`
Grid: `name`, `country_code`, `company_ids`, `rating_scale` (Selection 3|4|5 levels with
labels), `band_bands` (position-in-band bands: `<0`, `0–33`, `34–66`, `67–100`, `>100`),
`active`, `note`; cells: `rating`, `position_band`, `pct`. `suggest(review)` → per line
the cell's pct (unrated → the middle rating with a chip "unrated"; no band → the middle
band with a chip). Migration: each `wfp.merit.matrix` → one grid (rows from cells'
compa ranges → position bands; performance placeholder → rating levels; pct copied),
name prefixed "Migrated".

### 3.2 Ratings — `pb.pay.rating`
`review_id`, `person_id` (Integer, like `pb.pay.position`), `employee_id`, `rating`
(Integer 1..scale), `source` Selection entered|pasted|synced|legacy, `note`; unique per
review+employee. Paste: a text area accepting "name or employee code, rating" rows with a
preview; sync: if `pb_zoho_bridge` exposes a rating field, map it (optional). Migration:
`hr.employee.wfp_performance_rating` values → a "Legacy ratings" pseudo-review snapshot
(`review_id` False, `source='legacy'`) so nothing is lost when the column drops.

### 3.3 Review — `pb.pay.review` (inherits `biz.approval.chain.mixin`, `mail.thread`)
`name`, `scope_kind/ref/label` (reuse P4's scope contract: company | division | scheme),
`company_ids`, `currency_id` (the review's; per-line currency may differ in a group
review), `year`, `effective_date`, `budget_amount`, `guidance_id`, `rating_scale`,
`limit_ids` (→ `pb.pay.review.limit`: `kind` max_raise_pct | band_ceiling |
division_budget | min_rating | max_raise_amount; `value`; `enforcement` warn|block;
`division_id` optional), `line_ids`, computed: `allocated_amount`, `remaining_amount`,
`people`, `lines_blocked`, `fairness_before/after` (Json from the P6a fairness facade on the
review's population with proposals applied), `state` (mixin-driven: draft → proposed →
hr_review → finance → approved → applied → closed, plus refused), `decision_plan_id`
(optional `pb.decision.plan` it was born from), `applied_at/by`, `undo_until`.
Lines — `pb.pay.review.line`: `review_id`, `employee_id`, `person_id`, `contract_id`,
`manager_id`, `department_id`, `job_id`, `band_id`, `position_pct`, `rating`,
`current_wage`, `currency_id`, `guidance_pct`, `proposal_pct`, `proposal_amount`,
`new_wage` (computed either way), `annual_cost_delta`, `chips` (Json: limit breaches,
unrated, no band, inversion created), `manager_note`, `state` open|submitted|returned,
`returned_note`. Every write recomputes chips and the review's meters; fairness recompute
is debounced server-side (a `_fairness_dirty` flag + recompute on read).
Cascade: the mixin's states are the review's; `_approval_can` per step reads
`pb_pay.group_pay_manager` (HR), `pb_pay.group_pay_finance`, `pb_pay.group_pay_ceo`
(new groups; CEO implied by `base.group_system`); managers act only on their own lines
(`manager_id` = the employee's manager chain); each transition schedules a
`mail.activity` for the next step's group members and shows on the Decision Room's Home
strip (reuse P4's "awaiting" chip mechanism, extended to reviews). Return-to-manager per
line with a note.

### 3.4 Calibration + bulk
Facade `pb.pay.review.calibration(review_id)` → dots (line id, rating, proposal_pct,
position_pct, cost) + outliers (proposal > mean + 2σ within the same rating, or a
limit breach); `set_proposals(review_id, [{line_id, pct|amount}])` bulk with one
recompute; `apply_guidance(line_ids)`; `spread_remaining(line_ids, by='rating')`;
`paste(review_id, text)` → preview → commit.

### 3.5 Apply and undo — `pb.pay.apply`
`preview(review_id)` → contracts that change (employee, contract, old, new, currency,
date, letter type); `apply(review_id)`: for each line, write `hr.contract.wage = new_wage`
(one write per contract, `effective_date` recorded on the apply record; if the company
pays from a pay-data file lane, also flag the line "the next pay file must carry this
figure" — read `hr.formula.config.source_priority` to decide), create an apply record
`pb.pay.apply` (review, line, contract, old_wage, new_wage, applied_at, undo_until =
+24 h, state applied|undone), generate a `pb.hr.letter` per line from a "Pay review"
template (create the template in data if missing, with placeholders old/new/effective
date/percentage), file it via the letter engine, and set the line/state; `undo(review_id)`
within the window restores every `old_wage`, marks apply records undone, and voids the
letters (state); after the window the button is absent and the sentence says why.
Positions (`pb.pay.position`) recompute after apply. Payslips already computed are never
touched.

### 3.6 Pay changes — `pb.pay.change`
`employee_id`, `person_id`, `contract_id`, `kind` promotion|correction|market|other,
`new_job_id` (optional), `current_wage`, `new_wage`, `pct`, `effective_date`, `reason`,
`band_id`/`position_before/after`, `chips` (limits from the company's default review
limits, kept on `pb.pay.settings` per company), cascade on the same mixin (manager →
HR → finance for > threshold), `apply`/`undo` via `pb.pay.apply`, letter. A change made
while a review is open for that person is refused with the sentence.

### 3.7 Portal — "Your pay, explained"
`pb_pay/controllers/portal.py` on the `pb_me_portal` kit: `/my/pay` shows the person's
current pay, band position sentence (if bands exist), the last applied review/change
(old → new, %, date, the letter link), and a plain paragraph explaining what changed and
why (the review's or change's reason). Nothing about other people. Off when the company's
`pb.pay.settings.portal_enabled` is False (default True).

### 3.8 Migrations and the uninstall gate
Migrations (idempotent, in `pb_pay/migrations/19.0.2.0.0/post-migrate.py` and
`pb_budget/migrations/<next>/post-migrate.py`):
1. `wfp.merit.matrix` → `pb.pay.guidance` (count parity).
2. `wfp.compensation.cycle` + recommendations + approval steps → `pb.pay.review`
   (state `closed`, `is_legacy=True`, read-only) + lines + a trail entry per old step
   (count parity per model).
3. `hr.employee.wfp_performance_rating` → `pb.pay.rating` legacy rows (count of non-null).
4. `wfp.budget.actual` → `pb.budget.line` (every column in `budget_ext.py:64-127`;
   `scenario_id` dropped; row-count and sum-of-`actual_cost` parity), then every
   pb_budget reader/writer/rule/view repointed; `pb_budget` tests green.
5. `wfp.budget.guardrail` → `pb.pay.review.limit` templates on `pb.pay.settings`.
6. `wfp.pay.grade` already handled in 6a; `hr.contract.grade_id` values noted in
   `pb.pay.position.note` where a band link could not be made.
Gate (`pb.pay.retire.preflight()`), run on each DB before uninstall; refuses with a
plain list if any fails: every migration parity holds; no module other than the legacy one
references `wfp.` models (grep of installed modules' Python/XML via `ir.model.data` +
a filesystem grep on the server); `pb_budget` and `pb_people_hub` no longer depend on it
(manifests); the Plan lens gate resolves to the Decision Room groups; `pb_contracts`
reads `pb_pay` fields; a `pg_dump` for the DB exists and is newer than the last write.
Uninstall: `odoo-bin -d <db> --stop-after-init` with a small script calling
`env['ir.module.module'].search([('name','=','pb_hr_workforce_planning')]).button_immediate_uninstall()`
(or `-u` a tiny helper) — rehearse on p9clone, then production. Post-uninstall smoke:
People → Plan opens the room; Budget screen numbers identical to the pre-uninstall
screenshot; Contract 360 opens; Explorer loads; no `wfp` table remains; no traceback in
the log.

### 3.9 Security
`pb_pay.group_pay_finance`, `pb_pay.group_pay_ceo` (new); managers are implicit via the
manager chain; viewers see their own team's rows only; record rules on lines by
`manager_id` chain for non-HR.

## 4. Client design
- **Review tab**: list of reviews (cards: scope, year, meter, state, next step); "New
  review" drawer (scope via P4's picker if now exportable, else select; budget; guidance;
  limits; ratings step: enter/paste/sync); the review screen: header (meter, fairness
  line, state timeline with nudge), toolbar (Guidance, +%, Spread remaining, Paste,
  Calibration, Filters: my team / unrated / blocked / below band), the worksheet grid,
  "What blocks approval" panel, Send / Approve / Return / Apply / Undo by role; versions
  and trail drawer.
- **Calibration view**: scatter with draggable dots; a side list of outliers; the same
  header.
- **Changes tab**: list + "New pay change" drawer with the live band/guidance/limits;
  approve/apply/undo.
- **Portal**: `/my/pay` page on the kit.
- Home: the P4 "awaiting" strip now also counts reviews and changes for the user's step.
- ⌘K: 3430 "Pay review", 3440 "New pay change", 3450 "Awaiting my approval".
- Plan lens (`pb_people_hub`): gate = Decision Room groups; hero only; fold removed.

## 5. Tests (p9clone; numbered)
- T1 guidance: suggest per cell; unrated/no-band chips; migration from a fixture matrix
  with count parity.
- T2 ratings: unique per review+employee; paste preview + commit; legacy migration count.
- T3 review meters: allocated/remaining/people; chips for each limit kind; block vs warn;
  fairness before/after recomputed on read when dirty.
- T4 cascade: manager submits own lines only; HR/finance/CEO transitions per group;
  refuse returns with note; activities created; trail complete (`get_approval_trail`).
- T5 calibration payload + `set_proposals` bulk recompute in one pass; `spread_remaining`
  respects the budget; outliers rule.
- T6 apply: preview equals the lines; apply writes each `hr.contract.wage`, creates apply
  records with `undo_until`, generates and files letters, recomputes positions; undo within
  the window restores every wage and voids letters; after the window undo refused with the
  sentence; computed payslips untouched (assert on a fixture payslip).
- T7 pay change: chips from settings; refused while a review is open; cascade; apply/undo.
- T8 portal `/my/pay` renders for an employee user; nothing about others; off switch.
- T9 `pb_budget`: migration parity (rows, Σ actual_cost); all pb_budget tests green on
  `pb.budget.line`; no `wfp.` reference left (grep test).
- T10 `pb_people_hub`: Plan lens gated by Decision Room groups; no `wfp` reference; its
  suite green as rewritten.
- T11 preflight gate: passes on p9clone after migrations; fails (with the list) when a
  parity is broken on purpose in a fixture.
- T12 no "Odoo"; static contract; palette 3430–3450; `vi_VN.po` complete for new strings.
- T13 uninstall rehearsal on p9clone: gate passes → uninstall → smoke checks (Plan lens,
  Budget numbers, Contract 360, Explorer, no `wfp_` tables, no tracebacks) → earlier suites
  green.
Browser (payobook + abm via temporary validators; 1440 + 390; Vietnamese user;
`docs/handovers/group_p6b_shots/`):
- B1 New review for the Retail scheme → opens pre-filled (guidance, meter, fairness line,
  chips) → select a block → +1% → everything moves.
- B2 Calibration: drag a dot; outlier ring; row follows.
- B3 Limits: a blocked row's chip and the panel; fix it.
- B4 Cascade on p9clone with three validator roles: submit → HR → finance → CEO; Home
  strip counts; return a line with a note.
- B5 Apply on p9clone (never on payobook/abm): preview → apply → letters filed → contract
  wage changed → undo → restored. On payobook show the preview only.
- B6 Pay change: promotion drawer → approve → apply on p9clone; refusal while a review is
  open.
- B7 Portal `/my/pay` for an employee on p9clone.
- B8 Budget screen before/after the re-home on payobook: identical numbers.
- B9 People → Plan after the uninstall: room opens, no fold; Contract 360; Explorer.
- B10 abm: review on 153 people; uninstall smoke; 390 px; Vietnamese user.

## 6. Build order
1. Guidance + ratings + review models + limits + facade + T1–T3.
2. Cascade + calibration + bulk + T4–T5.
3. Apply/undo + letters + portal + pay changes + T6–T8.
4. Migrations + `pb_budget` re-home + `pb_people_hub` un-hook + preflight + T9–T12.
5. Uninstall rehearsal on p9clone + T13; Chrome walks on p9clone/payobook/abm.
6. Deploy ritual (backups), production uninstall behind the gate, smoke walks, verify,
   commits, ledger (GR46+), report.

## 7. Report back (plain-English first)
1. Three sentences: what a review looks like when it opens, what apply does, what is gone.
2. T1–T13 / B1–B10 table with evidence; migration parity numbers per DB; the preflight
   output per DB; timings (review open for 902 people, apply for 902).
3. Deploy + uninstall evidence per DB (versions, hashes, `wfp_` tables gone, smoke).
4. Deviations; new gotchas; phase log updated.
5. Self-score against the bar and the one thing to improve first.
6. Commit list.

## 8. States (zero dead-ends)
No guidance grid (review opens with 0% and a "Set guidance" prompt) · no ratings (all
"unrated" chips + paste prompt) · no bands (guidance by rating only; sentence) · budget
exceeded (meter red, Send disabled with the reason) · a line with no contract (skipped,
listed) · a person in two companies (line per employment, currency each) · a review in a
mixed-currency scope (meter in group currency via `pb.fx`, badge, refusal if unknown) ·
apply when a pay run is open for the month (allowed, warned: "June's run is open; new pay
applies from July unless you recompute") · undo after the window · a letter template
missing (created from data) · portal off · preflight failure (the list; nothing
uninstalled) · Vietnamese user.
