# WDGAP QF4 — report: goal scores into the pay review; benefits start and end by themselves

Branch `wdgap-qf4` (from `origin/19.1` @ 1065e98bf). Built, tested and self-reviewed by the
implementation agent. NOT merged, NOT deployed.

## 1. What was built

### A. Goal scores into the pay review

| Item | What | Files |
|---|---|---|
| A1 | "Read scores from Goals" button on the review's tools row (only where Goals is installed: payload `has_goals`), drawer cloned from the paste drawer: goals-year picker (open years labelled "· not closed yet" plus a note), sentence, three counts (have a score / will change / have none), the mapping table, the people with no score, then "Use these scores". Writes `pb.pay.rating` rows with new source `('goals', 'Read from Goals')` through `_write_many`, then `review.apply_guidance_to()` exactly as `paste` does. | `pb_pay/models/pb_pay_rating.py` (`SOURCES`, `_goal_years`, `read_from_goals`, `_goals_sentence`), `pb_pay/models/pb_pay_reviews.py` (facade `goal_scores`, `has_goals`), `pb_pay/static/src/js/pay_review.js`, `pb_pay/static/src/xml/pay_review.xml`, `pb_pay/static/src/scss/pay.scss` |
| A2 | At year close every sheet closed in that run whose frozen score exists is stamped on the employee as `pb_performance_rating` (and `wfp_performance_rating` where present), clamp + `str()` for a selection, `sudo()`, one chatter line on the employee ("Their latest performance score is now 4 out of 5, from the goals year FY2025."). Hooked on `pb.goal.set._close_for_year()` after `super()`, only when the sheet went from not-closed to closed, inside its own savepoint (a failure never stops the close). The close preview gains one sentence: "Each score also becomes the person's latest performance score, which the next pay review starts from. Reopening the year does not take that back." | `pb_goals/models/pay_score.py` (new), `pb_goals/models/close.py` |
| A3 | ONE mapping: `pay_rating(score, levels)` = `max(1, min(levels, round_half_up(score/5*levels)))` in Decimal; `None` for unscored (skipped, never 1). Closed sheets read `frozen_json`'s score; open sheets the live score only when `scored`. The drawer's table is produced by running the rule over every 2-decimal score, so it cannot disagree with it. pb_pay reaches it through `env['pb.goal.set']._pay_rating_for` (probe, no dependency). | `pb_goals/models/pay_score.py` |
| A4 | The cycle form IS reachable (⌘K palette "Goal years" → `pb_goals.action_pb_goal_cycle`), so the old button was ROUTED, not removed: `action_close` now calls `close_cycle(id, with_gaps=False)` (HR-lead check, refuses while unscored, freezes, files, stamps). The old "Close it" button is hidden (`invisible="1"`), because "Score it and close the year" beside it is the same press; the button stays in the view as the anchor `view_pb_goal_cycle_form_b2` hangs off. | `pb_goals/models/cycle.py`, `pb_goals/views/goal_views.xml` |

### B. Benefits

| Item | What | Files |
|---|---|---|
| B1 | `pb.benefit.plan.auto_cover` "Who is covered automatically": Nobody (HR adds people) [default] / Everyone, from the day they join / Everyone, once the trial period is passed. Radio on the plan form. Qualifies = active employee of the plan's company (a plan with no company enrols nobody), and the plan's country when it has one. | `pb_comp_ben/models/benefit.py`, `views/comp_ben_views.xml` |
| B2 | ONE method `pb.benefit.plan._enrol_who_qualifies(employee, moment, on_date=None)`; never a second active enrollment per plan+person; `started_by='auto'` (new selection `manual`/`auto`, labels "Added by HR" / "Started automatically", quiet grey chip in both lists). Called from: hiring "Confirm they joined" (new leg `_ensure_benefits`, start = `_anchor_date()` = the day they started); every onboarding checklist that opens (`pb_comp_ben` override of `pb.journey.case.action_open`, `case_type == 'onboarding'`, start = `case._joining_date()`); a passed trial (`pb_probation` `_verdict_pass` → `_start_benefits_after_trial`, probe `'pb.benefit.plan' in env`, start = today). | `pb_comp_ben/models/benefit_auto.py` (new), `pb_hiring/models/offer_closure.py`, `pb_probation/models/probation_review.py` |
| B3 | "Cover everyone who qualifies now" button on the plan form header (only `group_comp_head`, hidden while the plan covers Nobody) → small preview window "5 people qualify, 2 are already covered, 3 will be added." → "Add them". Server methods `cover_everyone_preview()` / `cover_everyone()` both refuse anyone without `group_comp_head`. Start date = today, or the person's first day if that is still ahead. New transient model `pb.benefit.cover.wizard` (access: head of pay only). | `benefit.py`, `benefit_auto.py`, `views/comp_ben_views.xml`, `security/ir.model.access.csv` |
| B4 | New `end_reason` (`manual` "Set by HR" / `leaving` "Leaving"). `_stamp_leaving(employee, last_day)` writes `end_date = last day`, `end_reason='leaving'` on every still-covered row that has no end date or was stamped "leaving" before — a row HR ended, or an end date HR typed, is never touched. `_clear_leaving(employee, only_day=None)` takes the stamp off "leaving" rows only (narrowed to one exit's day when given). Callers: resignation approved (`pb_offboarding` `_on_resignation_approved` → `_benefits_follow_last_day`, probe); the agreed/requested last day written on an approved resignation (`pb.resignation.write`); resignation withdrawn (`action_withdraw` → `_benefits_call_off`); leaving checklist cancelled (`pb_offboarding` `pb.journey.case.action_cancel`, offboarding only, clears rows stamped with the checklist's key date); `hr.employee.write` with `departure_date` (set → stamp/follow, emptied → clear; Odoo's unarchive empties it) or `active=False` (archived without a date → today). Daily job "Benefits: end cover after the last day" (`noupdate`, 17:30 UTC, writes `state='ended'` only, no mail) moves rows whose `end_date` is before today to Ended. | `benefit.py`, `benefit_auto.py`, `data/ir_cron.xml`, `pb_offboarding/models/resignation.py`, `pb_offboarding/models/journey_case_ext.py` |
| B5 | List chip "Ends 30 Nov 2026 · leaving" (computed `end_note`, amber badge, plain "Ends 30 Nov 2026" when HR set the date) on the plan's "People on it" list and the "Who is covered" list. The exit board's HR-desk line was NOT added — see §4. | `benefit.py`, `views/comp_ben_views.xml` |
| B6 | NOT done — see §4. The ⌘K entry is unchanged. | — |

### Version bumps

| Module | Before | After |
|---|---|---|
| pb_goals | 19.0.1.4.0 | 19.0.1.5.0 |
| pb_pay | 19.0.3.7.0 | 19.0.3.8.0 |
| pb_comp_ben | 19.0.1.7.0 | 19.0.1.8.0 |
| pb_hiring | 19.0.2.23.7 | 19.0.2.23.8 |
| pb_probation | 19.0.1.5.0 | 19.0.1.6.0 |
| pb_offboarding | 19.0.1.5.0 | 19.0.1.6.0 |

Translations: 3 new strings in `pb_goals` (vi + id), 24 in `pb_pay` (vi + `.pot`), 28 in `pb_comp_ben`
(vi; the module has no id file). Entries were taken from `odoo-bin i18n export` of the upgraded
database, so each carries `#. module:`, the `odoo-python`/`odoo-javascript` marker and a
`code:addons/...:0` occurrence. pb_hiring / pb_probation / pb_offboarding gained no user-visible
string (their new text is log lines only).

## 2. Tests

Local: copy of `upd_p3c_t_tpl` upgraded with `pb_updates` (template was behind HEAD, see ledger
W1), then copies of that (`qf4_t1`, `qf4_full`). Isolated worktree tree, own ports 8931/8932.
Afterwards all scratch databases were dropped (disk space) except `qf4_walk`, the seeded browser
copy (local only; its admin login was re-activated for the walk) — drop it when no longer needed.

Command (QF4 only): `odoo-bin -c qf4.conf -d qf4_t1 -u pb_goals,pb_pay,pb_comp_ben,pb_hiring,pb_probation,pb_offboarding --test-enable --test-tags wdgap_qf4 --stop-after-init`
→ **40 tests, 0 failed, 0 errors**. The run logs 6 ERROR lines; all six are the injected
`RuntimeError('injected')` of test 14 being swallowed and logged by the hooks, as designed.

| # | Case | Where | Result |
|---|---|---|---|
| 1 | Mapping 0.0/0.4/2.5/3.0/4.49/4.5/5.0 at 3/4/5 levels; unscored → None; table covers 0–5 once | `pb_goals/tests/test_wdgap_qf4.py` TestQf4Mapping (3) | PASS |
| 2 | Dry run writes nothing, counts read/changed/missing; use writes `source='goals'`; guidance re-applied (`guidance_pct == grid.pct_for(3, …)`); label "Read from Goals" | `pb_pay/tests/test_wdgap_qf4.py` test_02 (2) | PASS |
| 3 | Pay manager with no Goals rights can use it, only review people read (a person added after the worksheet is ignored); viewer refused (AccessError); decided review refused; another company's year refused | test_03 (4) | PASS |
| 4 | Default = latest closed year ending on/before the effective date (not the later closed one, not the older one); open year offered, labelled "not closed yet", choosable, flagged; payload `has_goals` | test_04 (2) | PASS |
| 5 | Close stamps scored sheets only (unscored keeps its old value), chatter line; reopen does not roll back; closed sheet reads the frozen figure; preview sentence; old `action_close` refuses while unscored and then does the real close (freeze + stamp); a review made after the close seeds 5 / `synced` | pb_goals TestQf4Close (5) + pb_pay test_05 (1) | PASS |
| 6 | Join plan: checklist opens → one auto row from the joining date; second call → still one; "Nobody" plan untouched; trial plan not at join | pb_comp_ben TestQf4Join (3) | PASS |
| 7 | Real `action_confirm_joined` on RECRUIT P6's signed-offer fixture → one row (the hiring leg and the checklist do not double), start = `joined_on`, trial plan untouched, leg again → still one | `pb_hiring/tests/test_wdgap_qf4.py` (1) | PASS |
| 8 | Trial plan: not at join, one row at `_verdict_pass()`, second pass → still one | `pb_probation/tests/test_wdgap_qf4.py` (1) | PASS (driven through `_verdict_pass()`, the method the hook sits in; `action_verdict('pass')` needs the colleague-feedback fixture) |
| 9 | Plan for Indonesia / another company's plan do not enrol a VN-company joiner; VN plan does; a person whose payroll country is ID gets the ID plan, not the VN one | TestQf4Join test_09 | PASS |
| 10 | Preview 1 covered / n−1 added; confirm adds only the missing; second press 0; wizard preview + confirm; pay-team user refused on preview, confirm and button | TestQf4CoverEveryone (3) | PASS |
| 11 | Approval → end date = agreed last day, "leaving", still Covered; job before → unchanged; last day moved to yesterday → follows → job → Ended; job shipped with the right code | pb_offboarding test_11 + pb_comp_ben test_11 (2) | PASS |
| 12 | Last day moved → both rows follow; HR types its own date on one → kept when the checklist is cancelled, the other cleared; withdrawn resignation clears what it stamped; approval twice moves nothing; hand-ended row untouched throughout | pb_offboarding test_12 (3) | PASS |
| 13 | Archive → today/"leaving"; departure date → follows; unarchive → cleared; HR-typed end date kept; stamp twice → 0 | pb_comp_ben TestQf4Leaving (3) | PASS |
| 14 | Injected failure: checklist open, employee write, confirm joined, verdict pass, resignation approval all complete | 5 tests across 4 modules | PASS |
| 15 | Full suites, `-u` all six, `--test-tags /pb_goals,/pb_pay,/pb_comp_ben,/pb_hiring,/pb_probation,/pb_offboarding` | see below | PASS — no new failure |
| 16 | Browser, local copy `qf4_walk` at 127.0.0.1:8941 (Claude in Chrome, own tab, closed after): pay review → "Read scores from Goals" → year list "DEMO FY2026 · not closed yet", "DEMO FY2025" → preview "3 people have a goals score, 3 of them will change and 1 have none" with counts and the 4-row table → open year shows "Nobody on this review…" + not-closed note and no use button → closed year → "Use these scores" → toast "3 scores read from Goals.", worksheet scores 4/3/2, guidance re-applied. Plan form → "Everyone, from the day they join" → save → "Cover everyone who qualifies now" → "5 people qualify, 2 are already covered, 3 will be added." → "Add them" → toast, rows show "STARTED AUTOMATICALLY"; the leaver shows "ENDS 30 NOV 2026 · LEAVING". Console: 0 errors. Lens check: n/a (B6 not built). Two fixes made from the walk: the count badges were title-cased by the shared badge style (now plain), the chip column was too narrow (now 230px). | PASS |
| 17 | `py_compile` all changed/new Python; XML parse of every changed XML; PO parse gate (`PoFileReader`) over all ten `.po` of the six modules: 0 failures, 0 vendor name in any msgstr; diff grep for the vendor name in user-visible strings: none | PASS |

### Full suites (test 15)

`qf4_full` (copy of the upgraded base): **906 tests — 10 failed, 3 errors; none caused by QF4.**
pb_goals 197, pb_comp_ben 20, pb_offboarding 12, pb_probation 11: all green. pb_pay 136, pb_hiring 530:

| Failure | Cause | Evidence |
|---|---|---|
| pb_pay `test_t4c_the_catalogue_covers_the_whole_exported_template` | 46 old `pb_pay.pot` terms with no Vietnamese | the same 46 on `origin/19.1`; all 24 QF4 terms are translated |
| pb_pay `test_t11_the_product_never_says_the_wrong_name_to_a_user` | `pb_pay.pot` header said "Project-Id-Version: Odoo Server 19.0" | same header on `origin/19.1`; FIXED in this branch (header now "Payobook 19.0"); re-run: passes |
| pb_hiring `TestArrangingOne.test_t2_the_step_moves_the_candidate…` | `psycopg2.errors.DiskFull` during the run (the Mac had ~5 GB free) | re-run of the whole class on `qf4_t1`: 28 tests (with pb_pay's static contract) 0 failed |
| pb_hiring 10 others: `TestClientReview.test_hiring_only_cannot_read_access_directory`, `TestRecruitInterviewsP5.test_07b`, `TestRecruitJoining.test_11`, `TestRecruitPrivacy.test_02/02b/08`, `TestRecruitPrivacyFiles.test_02`, `TestRecruitStages.test_13`, `TestRegistersP9.test_08`, `TestTheCover.test_t7` | pre-existing (hub order, privacy tokens, setup cards, Google, approval title) | every one also fails on an unchanged `origin/19.1` tree run of `/pb_hiring` (that baseline run: 7 failed, 63 errors of 528, the extra errors are its own environment) |

## 3. Self-review against the handover

§2 non-goals
- No new module; cross-module links are probes in the module that owns the event (pb_probation and pb_offboarding gained NO dependency; pb_pay/pb_goals none on each other). ✔
- No costs, deductions, nominee rules, insurer files, waiting periods, grade/department rules. ✔
- No new clearance desk. ✔  No approval process; `pb_approval_config` / `biz_approval_workflow` untouched. ✔
- Pay review: rise maths, guidance grid and typed/pasted ratings change only after "Use these scores" (the dry run writes nothing — test 2). Note: like "Paste scores", "Use these scores" re-applies the guidance to every row, which resets proposals typed by hand on the worksheet — this is the paste precedent the handover asked to copy. ✔
- `pb_pack_*` and demo generators untouched. ✔

§3 rails
- R1 ✔ facade checks `_require_write()` + `_editable()` first; Goals read with `sudo()` after, only for the review's own lines' employees and only years of the review's companies (a year id from elsewhere is refused). B3 `group_comp_head` enforced server-side. `action_end` unchanged.
- R2 ✔ every hook in its own savepoint + `_logger.exception` (hiring uses its `leg()`, which logs a warning with the trace — the module's precedent).
- R3 ✔ idempotence tested for enrol, stamp, approval, cover-everyone.
- R4 ✔ `sudo()` write, only sheets closed in this run, one chatter line per person; preview says reopening does not take it back.
- R5 ✔ plan enrols only its own company's employees; the job runs as the cron user (superuser) and writes `state` only.
- R6 ✔ one `ir.cron`, `noupdate="1"`, 17:30 UTC (04:30 Sydney, 00:30 Vietnam; clear of the 19:30 UTC backups), no mail.
- R7 ✔ plain words, no vendor name, Lucide icon (`award`) from the shared `ic()` set, quiet grey "Started automatically" chip; translations added and parse-gated.
- R8 ✔ six bumps.

## 4. Decisions taken, and what was not done

- **B1 country**: the leave screens' resolution (`pb.timeoff._emp_country`: absence policy's country → payroll country → company country) is in `pb_timeoff`, which pb_comp_ben does not depend on, so it is not importable. It was CLONED with field probes (`pb_leave_policy_id`, `payroll_country`, else company), so the answer is the same as the leave screens' wherever those fields exist, and the company's country otherwise.
- **A4**: routed through `close_cycle` (the form is reachable from ⌘K "Goal years"); the duplicate old button hidden.
- **B5 exit-board line — NOT done.** The board's HR desk carries the desk's own stored note (`pb.exit.clearance.note`, what HR typed when signing off) and the board does not print that note anywhere; there is no existing text builder to add one line to. Adding it means a board change → reported instead, per the handover. The benefits list chip is done.
- **B6 Benefits lens — NOT done.** `PAY_LENSES` entries must be an OWL `Component`; the Benefits screen is a plain list/form window and there is no list-in-a-lens precedent (the closest, `LedgerCockpit`, needs a server descriptor model and the filter kit). Doing it means building a new Benefits board. ⌘K entry unchanged.
- **Trial-plan joiners with no trial**: a "once the trial period is passed" plan enrols at the pass; a person who never has a trial period is picked up by "Cover everyone who qualifies now" (it counts "Not applicable" and an empty/elapsed trial date as passed), not automatically at join. Owner question below.
- **Cancel after approval**: an approved resignation cannot be withdrawn on screen ("talk to HR and they will cancel both"). The two ways HR "cancels both" are covered: cancelling the leaving checklist clears the rows stamped with its key date, and emptying the departure date on the employee clears all "leaving" rows.
- **Clash**: when an employee record already carries a different departure date, the resignation leaves the record alone (existing rule) but benefits follow the resignation's agreed day.
- `pb_comp_ben` overrides `pb.journey.case.action_open` itself (it already depends on pb_lifecycle), so hiring, the connected-system pipeline and a checklist HR opens by hand all reach the same method; the hiring leg makes the hiring path not depend on whether a checklist template exists.
- Commit attribution: the session's own attribution line (Opus 5.5) was used rather than the handover's "Fable 5.2", because this phase's code was written by the Opus agent.

## 5. Owner questions

1. When a goals year is closed, each person's goals score becomes their "latest performance score". If somebody already has a score from a trial-period review or an improvement plan, the goals score replaces it. Is that what you want?
2. A plan set to "Everyone, once the trial period is passed" only adds people at the moment a trial is passed. People hired with no trial period are not added by themselves — HR adds them with "Cover everyone who qualifies now". Should people with no trial period be added on their first day instead?
3. The daily job also ends cover for any OLD benefit rows that already have a "Covered until" date in the past but still say "Covered". On the first night after this goes live those rows will switch to "Ended". Is that right, or should we check the numbers per customer first?
4. Benefits is still reached only through the ⌘K search (and the employee's own page). Giving it a tab in Payroll means building a small Benefits board (plans and who is on them). Do you want that as a next step?
5. The exit board could show "Benefits: 2 plans end on 30 Nov" on each leaver. That needs a small change to the board itself. Do you want it?

## 6. Deploy notes

- Modules to `-u` (all five customers, never abm): `pb_goals`, `pb_pay`, `pb_comp_ben`, `pb_hiring`, `pb_probation`, `pb_offboarding`. Where `pb_comp_ben` is absent the probes make the other modules skip benefits silently.
- Tier: **normal** — new stored fields (`auto_cover`, `started_by`, `end_reason` with defaults, a new selection value on `pb.pay.rating.source`), a new transient model and a new scheduled job. No stored-data rewrite at upgrade. Before the first night run, count `pb_benefit_enrollment` rows with `state='active' AND end_date < today` per database (owner question 3) — those are the rows the job will move to Ended.
- New job: **"Benefits: end cover after the last day"** (`pb_comp_ben.cron_benefit_end_due`), daily 17:30 UTC. Cron snapshot before/after per ledger (pb_hiring/pb_pay are not base modules, but six modules are upgraded together).
- Asset purge: **yes** (pay review JS/XML/SCSS changed) — `DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'` per database, then restart.
- PO parse gate on the box after rsync (pb_pay `.pot` changed too).

## 7. New gotchas → ledger

W1–W5 added to `WDGAP_LEDGER.md` (template behind HEAD needs `pb_updates`; unarchive empties `departure_date`; shared badge title-cases; the cycle-form button is an xpath anchor; local disk nearly full).
