# WDGAP QF4 — plumbing facts: goal scores into the pay review; benefits on join and leave

Verified by a read-only code survey on 2026-11-14 (branch 19.1). Do not re-derive; spot-check a line before relying on it.

# Implementation handover: verified plumbing for Feature A (goal scores into pay review) and Feature B (benefits on join and leave)

All paths below are under `/Users/adity/Documents/GitHub/gitlocal/`.

## Feature A: goal scores into the pay review

**Correction to the brief:** the model is `pb.pay.rating`, not `pb.performance.rating` (`pb_pay/models/pb_pay_rating.py:44`).

### pb_goals: how the year score is computed and stored
- **Key result score:** `pb.goal.kr.score` is a Selection from `'0'` to `'5'` (`goals_common.py:246`, where 0 means "Not done"). `score_value` is the same value as a Float (`scoring.py:58-74`).
- **Goal score:** `pb.goal.score` is the plain average of its key results, as a Float 0–5 with 2 decimals. It stays empty unless every key result is scored (`scoring.py:95-115`).
- **Sheet score:** `pb.goal.set.score` is a stored Float 0–5, worked out as Σ(weight × score) ÷ total weight (`scoring.py:169, 205-225`). The same compute fills `scored` (Bool), `score_band` and `score_tone`. Bands come from `pb.goal.band` (`review.py:445`).
- **One sheet per person per year:** constraint `unique(employee_id, cycle_id)` (`goal_set.py`, near line 64).
- **The year (`pb.goal.cycle`):** fields `name`, `company_id`, `date_start`, `date_end`. There is no integer year field. States are `draft` / `open` / `closed` (`goals_common.py:121`).
- **Sheet states:** `draft`, `submitted`, `manager_ok`, `locked`, `returned`, `refused`, `closed` (`goals_common.py:140`).
- **Year close:**
  - `pb.goal.cycle.preview_close(cycle_id)` (`close.py:62`) and `close_cycle(cycle_id, with_gaps=False)` (`close.py:134`).
  - `close_cycle` requires `pb_goals.group_goals_manager` ("HR lead for goals"), then calls `_do_close(gaps)` (`close.py:156`).
  - `_do_close` runs `pb.goal.set._close_for_year()` per sheet, each in its own `leg()` savepoint (`close.py:243`). That method writes `state='closed'`, `closed_at` and `frozen_json` (from `_freeze()`, `scoring.py:333`) and archives the goals.
  - Reopen: `action_reopen_cycle` (`close.py:212`).
- **Close UI:**
  - Main path: the "Close the year" button in `pb_goals/static/src/xml/goals_board.xml:81` calls `askClose()` / `doClose()` in `static/src/js/goals_board.js:856-895`. These go through the `pb.goals` facade, `pb_goals_year.py:306-311`.
  - Also a form button `action_close_cycle` (`views/goal_year_views.xml:447`).
- **Gotcha:** the older cycle form button `action_close` (`goal_views.xml:76`, method `cycle.py:156`) just writes `state='closed'`. It skips `_do_close`, the freeze and any hook. The best place to hook is `pb.goal.set._close_for_year()` after `super()`, and you should either remove that old button or route it through `close_cycle`.

### pb_pay: the rating model
- **Fields:** `review_id` (cascade), `employee_id` (required), `person_id` (Int), `company_id`, `rating` (Integer, required), `source`, `note`.
- **SOURCES** (`pb_pay_rating.py:32`), exactly: `[('entered','Typed in'), ('pasted','Pasted from a spreadsheet'), ('synced','Read from the connected system'), ('legacy','Carried over')]`.
- **Uniqueness:** `unique(review_id, employee_id)` (`:61`). Legacy rows have `review_id` NULL.
- **No date or period field.** A rating belongs to the review, and the review carries `year` (Integer) and `effective_date` (`pb_pay_review.py:356-361`).
- **Scale:** 1 to `review.rating_scale`. That is related to `pb.pay.guidance.rating_scale`, Selection `'3'`/`'4'`/`'5'`, default `'4'` (`pb_pay_guidance.py:60, 145`). `paste` and `set_one` enforce the range.
- **"Latest score":** there is no query for it. It is the single field `hr.employee.pb_performance_rating`, a Selection `'1'`–`'5'` (`pb_pay_rating.py:302`), shared with `pb_demo` on purpose.

### pb_pay: how a review opens already filled in
1. `pb.pay.reviews.create_review` (`pb_pay_reviews.py:427`) calls `review.build_lines()` (`pb_pay_review.py:602`).
2. That calls `_seed_ratings()` (`:641`). It copies `pb_performance_rating` once per line into rows with source `'synced'`, via `pb.pay.rating._write_many(review, rows, source)` (`pb_pay_rating.py:157`).
3. Then `apply_guidance_to()` (`:794`) reads `_ratings_by_employee()` (`:816`) and calls `grid.pct_for(rating, position_pct, has_band)` (`pb_pay_guidance.py:208`).
   - A rating above the scale is clamped to the top level.
   - A rating below 1 is treated as `middle_rating()`.
   - Cells are keyed by (rating, position band); default seeds are in `SEED` (`:75`).
- Single pay changes read `pb_performance_rating` directly (`pb_pay_change.py:209`).

### pb_pay: flows to clone
- **Facade:** `paste_ratings`, `set_rating` and `sync_ratings` in `pb_pay_reviews.py:651-667`. Each checks `_require_write()` and `_editable()`.
- **Model side:** `paste(review_id, text, dry_run)` (`:67`) and `sync_from_connected_system(review_id)` (`:193`). The sync looks for the field `pb_performance_rating`, then `wfp_performance_rating`, and returns a `{'read', 'sentence'}` dict.
- **UI:** the "Paste scores" / "Read scores in" buttons are in `pb_pay/static/src/xml/pay_review.xml:219-229`, with the paste drawer at `:608-645`. Handlers are `openPaste`, `checkPaste`, `commitPaste` and `syncRatings` in `static/src/js/pay_review.js:701-750`. `REVIEWS = "pb.pay.reviews"` (`:47`).

### Dependencies and bridges
- Neither pb_pay nor pb_goals depends on the other, and no module depends on either.
- pb_goals 19.0.1.4.0 depends on `pb_onboarding`, `pb_hub` and others. pb_pay 19.0.3.7.0 depends on `pb_lifecycle`, `om_hr_payroll` and others.
- **Bridge precedent:** `pb_training_growth/__manifest__.py` has `depends: ['pb_pip', 'pb_training']` and `auto_install: True` (comment ":39-42 THE BRIDGE RULE").
- Other auto-install bridges: `pb_me_expense`, `pb_me_trip`, `pb_training_payai`.
- **Gotcha:** `pb_trip_payroll_bridge` is `auto_install: False`, so it is not a precedent for the auto-install pattern.
- **Probe-instead-of-depend pattern:** check `if name in env['hr.employee']._fields`, as in `pb_pay_rating.py:205`.
- **Which databases have both:** the only install list I found is `docs/handovers/vifix/tools/data/installed_payobook.txt`. It lists pb_goals, pb_pay, pb_comp_ben, pb_offboarding, pb_onboarding, pb_probation, pb_hiring and pb_pip together. Its date is unknown.

### Existing writers (precedent)
- **pb_pip:** `pip_case.py:857` `_write_performance_rating()`, called from `action_verdict` (`:825`). It clamps with `max(1, min(5, int(...)))`, writes `str(value)` when the field is a selection, uses `emp.sudo().write(values)` on both field names when both exist, and posts to the chatter.
- **pb_probation:** the same pattern at `probation_review.py:927`, using `round(self.avg_rating)`, called from `_verdict_pass` (`:868`). `review_journey.py:165` skips the write for "sop_" peer forms.
- **pb_training_growth writes no rating.**
- **Gotchas:**
  - Nobody writes `pb.pay.rating` outside pb_pay. Writers only set the employee field, and an existing review never re-reads it (it is seeded once, at `build_lines`).
  - The goal score is a Float that can be 0. You need to round, clamp to 1..levels and skip 0, otherwise `_seed_ratings` drops it (`if value`).

## Feature B: benefits on join and leave

### pb_comp_ben (19.0.1.7.0)
- **Depends:** `pb_lifecycle`, `pb_payhub`, `pb_payruns`, `om_hr_payroll` and others. **Not** onboarding, offboarding or probation. i18n: `vi_VN.po` only, no `id`.
- **`pb.benefit.plan`** (`models/benefit.py:25`):
  - Fields: `name` (translatable), `kind` (`BENEFIT_KINDS` from `comp_common.py`), `provider_name`, `provider_url`, `country_id`, `coverage_html`, `active`, `company_id`, `enrollment_ids`, `enrolled_count`.
  - **No eligibility fields and no cost fields.**
- **`pb.benefit.enrollment`** (`:58`):
  - Fields: `plan_id`, `employee_id`, `member_ref`, `start_date` (defaults to today), `end_date`, `dependants_json`, `state` (`active` = "Covered", `ended` = "Ended"), `company_id`.
  - No uniqueness constraint.
  - `action_end()` (`:114`) sets `state='ended'` and `end_date` (keeps an existing one, else today). It has no access check.
  - `active_for_employee(employee_id)` (`:121`).
- **How the screen is reached:** only through the ⌘K palette entry `cb_benefits` → `pb_comp_ben.action_pb_benefit_plan` (`static/src/js/comp_ben_palette.js:99-107`, gated on `group_comp_user` / `group_comp_head`, `requires: "pb_comp_ben_incentives"`), plus the employee portal cards (`controllers/portal.py:196`, `views/portal_templates.xml:178`).
  - There are **no menuitems**, and `action_pb_benefit_enrollment` (`comp_ben_views.xml:433`) is referenced nowhere.
  - The pay hub lenses (`PAY_LENSES`: `paycal`, `awards`) are the hub-tab precedent (`comp_ben_palette.js:43-60`). Nothing for benefits is registered in pb_hub, pb_people_hub or pb_settings.
- **Access:**
  - `ir.model.access.csv:13-18`: staff read; `group_comp_user` read/write/create; `group_comp_head` full access.
  - Record rules (`security/pb_comp_ben_security.xml`): company rule `:93`, pay team sees everything `:127`, "my own" `:186`.
- **Approvals:** process keys are `'awards'` (`incentive_approval.py:24`) and `'month'` (`month_approval.py:25`). Nothing for benefits.

### Joiner event
- **"Confirm they joined" is in pb_hiring, not pb_onboarding or pb_lifecycle:** `pb.hiring.offer.action_confirm_joined(joined_on=None)` (`pb_hiring/models/offer_closure.py:70`).
  - It runs a sequence of `leg()` calls, including `_ensure_package`, which creates a `pb.employee.comp` (`:328`). That is a direct pb_comp_ben precedent.
  - pb_hiring (19.0.2.23.7) **already depends on pb_comp_ben**.
  - Post-hook: `hooks_p8.py:186` fires the `'joined'` automation rule after `super()`.
- **Joiners from any source:**
  - `pb.zoho.pipeline._open_case` (`pb_zoho_bridge/models/zoho_pipeline.py:555`) calls `case.action_open()`, then the empty hook `_after_onboard(case, rec)` (`:657`). Overrides must never raise.
  - pb_onboarding overrides `pb.journey.case.action_open` (`pb_onboarding/models/journey_case_ext.py:61`), filtered to `case_type=='onboarding'`, then runs `setup_onboarding()` (`:75`). This is a per-piece try/except list to extend.
  - The base method is in pb_lifecycle (`journey_case.py:263`), which pb_comp_ben already depends on.
- **Step registry:** `pb.journey.task._automation_handlers()` (`pb_onboarding/models/journey_ext.py:69`). Precedents: `pb_goals/models/journey_ext.py:46` plus its step data `pb_goals/data/journey_step.xml:31-41` (`automation_key` `goals_kickoff`).
- **Probation passed:** `pb.probation.review.action_verdict` (`probation_review.py:782`) → `_verdict_pass` (`:862`) → `employee._pb_set_probation_state('passed')` (`hr_employee.py:134`), then the empty hook `_on_verdict(verdict)` (`:1068`, must never raise). The HR-gated path converges on the same method through `super()` (`review_journey.py:259`).

### Leaver event (pb_offboarding 19.0.1.5.0)
- **Depends:** `pb_onboarding`, `pb_zoho_bridge`, `pb_assets`, `pb_hr_fullandfinal` and others, not pb_comp_ben. i18n: vi and id.
- **`pb.exit.clearance`** (`models/exit_clearance.py:31`): `unique(case_id, dept)`.
  - Desks are defined **in code, not seeded data**: `CLEARANCE_DEPTS` it/hr/finance/admin, `CLEARANCE_ORDER` and `CLEARANCE_STATES` pending/cleared/na (`offboarding_common.py:15-29`), plus `P_DEPT_USER` (`:98`).
  - Rows are created by `ensure_for_case(case)`, which loops over `CLEARANCE_ORDER` (`:76`).
  - Marked done with `action_clear(note)` (`:126`), `action_not_needed` (`:150`) or `action_reopen` (`:175`), all guarded by `_can_clear()`. Facade: `pb.exits.clear_clearance` (`pb_exits.py:707`).
  - Rows are created through `setup_offboarding()` (`journey_case_ext.py:96`), reached from `action_open` (`:83`), `_after_offboard` (`zoho_pipeline_ext.py:30`) and resignation approval.
- **Gate in front of the last payment:** `hr.full.final.settlement._pb_blocker_list` (`full_final_guard.py:64`) reads `pb.exit.clearance.pending_for(employee_id)` (`exit_clearance.py:192`). `action_pb_close` is at `:162`.
- **Gotchas for adding a "Benefits" desk:**
  - The `dept` selection needs `selection_add` with `ondelete`.
  - `CLEARANCE_ORDER` is imported by value, so `ensure_for_case` and the board row would also need overriding.
  - The board uses `CLEARANCE_DEPT_LABEL[d]` over `CLEARANCE_ORDER` (`pb_exits.py:201-209`), so an extra desk would hold the settlement but not appear on the board.
  - The step text in `data/journey_template_data.xml:103` says "all four".
- **Last day:** `pb.resignation.approved_lwd` / `requested_lwd` (`resignation.py:85-92`). On approval, `_after_approval_transition` (`:360`) → `_stamp_employee_record` writes `hr.employee.departure_date` (`:404`, never over a different date) → `_ensure_case` sets the case `anchor_date` (`:461`). Then the empty hook `_on_resignation_approved(case)` (`:624`).

### Tests folders
pb_goals, pb_pay, pb_comp_ben, pb_offboarding, pb_onboarding, pb_probation and pb_training_growth all have a `tests/` folder.