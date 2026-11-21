# WDGAP QF4 — Goal scores into the pay review; benefits start and end by themselves

Read first: `WDGAP_LEDGER.md` (binding conventions, decisions), then `WDGAP_QF4_FACTS.md`
(verified plumbing, file:line — do not re-derive), then
`docs/handovers/updates/UPDATES_LEDGER.md` G94–G99 (worktree, test loader).

You are the implementer AND the tester/reviewer of this phase. You do NOT deploy.

## 1. Scope

### A. Goal scores flow into the pay review
A1. **On the pay review's scores step: "Read scores from Goals"** next to "Paste scores" /
    "Read scores in" (`pb_pay/static/src/xml/pay_review.xml:219-229`). It opens a drawer
    cloned from the paste drawer: pick the goals year (default: the most recent closed
    year for the company that ended on or before the review's effective date; open years
    are offered and marked "not closed yet"), then a preview — how many people have a
    score, how many will change, how many have none, and the mapping table — then
    "Use these scores". Writes `pb.pay.rating` rows with a NEW source
    `('goals', 'Read from Goals')` through the existing `_write_many`, then re-applies
    guidance exactly as the paste flow does. Shown only when Goals is installed.
A2. **At goals year close, each closed sheet's score is stamped on the employee** as the
    latest performance score (`hr.employee.pb_performance_rating`), so the NEXT pay review
    opens already filled in. Clone the writer precedent `pb_pip/models/pip_case.py:857`
    (clamp, `str()` for a selection, both field names when both exist, chatter line).
A3. **Mapping** (one function, used by A1 and A2, unit-tested): goal sheet score is a
    Float 0–5. `levels` = the review's `rating_scale` for A1, 5 for A2.
    `rating = max(1, min(levels, round_half_up(score / 5 * levels)))`.
    A sheet that is not `scored` is skipped (never written as 1). For closed sheets read
    the frozen figure (`frozen_json`), not the live compute.
A4. The old cycle-form button `action_close` (`pb_goals/views/goal_views.xml:76`,
    `cycle.py:156`) skips the real close. Route it through `close_cycle` (or remove the
    button if the form is unreachable from Payobook's menus — say which in the report).

### B. Benefits
B1. **A plan can cover people by itself.** New field on `pb.benefit.plan`:
    "Who is covered automatically" = `Nobody (HR adds people)` (default) /
    `Everyone, from the day they join` / `Everyone, once the trial period is passed`.
    A person qualifies when they are in the plan's company and, if the plan has a country,
    their country matches (use the same employee-country resolution the leave screens use
    if it is importable without a new dependency; otherwise the employee's company
    country — state which in the report).
B2. **Joiners are enrolled** when they become an employee:
    - hiring: a new `leg()` in `pb.hiring.offer.action_confirm_joined`
      (`pb_hiring/models/offer_closure.py:70`, beside `_ensure_package`; pb_hiring already
      depends on pb_comp_ben);
    - any other source: `pb.journey.case.action_open` for onboarding cases (pb_comp_ben
      depends on pb_lifecycle — check how the case knows it is an onboarding case and that
      it carries an employee; never raise from the hook);
    - trial period passed: inside `pb_probation` `_verdict_pass` / `_on_verdict`, with the
      probe pattern `if 'pb.benefit.plan' in self.env:` inside try/except + log (pb_probation
      must NOT gain a dependency on pb_comp_ben).
    All three call ONE method `pb.benefit.plan._enrol_who_qualifies(employee, moment)`
    (`moment` in `join|probation`). It never creates a second active enrolment for the
    same plan and person; start date = joining date / day the trial was passed.
    Enrolments it creates carry `started_by = 'auto'` (new selection `manual|auto`,
    default `manual`) and show a quiet chip "Started automatically".
B3. **"Cover everyone who qualifies now"** button on a plan whose setting is not Nobody:
    preview ("38 people qualify, 31 are already covered, 7 will be added"), then confirm.
    This is how existing staff and imported people get in. Requires `group_comp_head`.
B4. **Leavers' cover ends by itself.** When a resignation is approved
    (`pb_offboarding` `_on_resignation_approved(case)`, FACTS "Last day") — probe pattern
    again, pb_offboarding must NOT depend on pb_comp_ben — every active enrolment of the
    person gets `end_date = last working day` and `end_reason = 'leaving'` (new field;
    values `manual|leaving`). The enrolment stays "Covered" until that day; a daily job in
    pb_comp_ben moves enrolments whose `end_date` has passed to "Ended". If the last day
    changes, the stamped date follows; if the exit is withdrawn/cancelled, clear the date
    ONLY on rows with `end_reason = 'leaving'`. Also cover the non-resignation exits: when
    `hr.employee.departure_date` is written or the employee is archived (pb_comp_ben can
    extend `hr.employee.write` — keep it cheap: act only when one of those two keys is in
    `vals`). Rows HR ended by hand are never touched.
B5. **HR can see it coming**: the benefits list shows "Ends 30 Nov 2026 · leaving" on such
    rows, and the exit board's HR desk note gains one line "Benefits: 2 plans end on
    30 Nov" IF that is a one-line addition to an existing text builder in pb_offboarding
    via the probe pattern; if it needs a new desk or a board change, do not do it — report.
B6. **A way in that is not only the ⌘K palette**: register Benefits as a lens beside the
    existing pay hub lenses (`PAY_LENSES` in `pb_comp_ben/static/src/js/comp_ben_palette.js:43-60`)
    if the precedent in that file extends cleanly; keep the ⌘K entry. Test it INSIDE the
    hub (hub-lens no-scroll trap). If it does not extend cleanly, report instead of forcing it.

## 2. Binding non-goals

- No new module (no bridge module install). Cross-module links use the probe pattern
  (`'model' in env`, `name in Model._fields`) in the module that owns the event.
- No benefit costs, payroll deductions, nominees/dependant rules, insurer files, waiting
  periods in days, or eligibility by grade/department — later steps.
- No new exit clearance desk (FACTS "Gotchas for adding a Benefits desk").
- No approval process for benefits. Do not edit `pb_approval_config` /
  `biz_approval_workflow`.
- Do not change how the pay review computes rises, the guidance grid, or any rating that
  was typed/pasted unless the user presses "Use these scores" after the preview.
- Do not touch `pb_pack_*` (ledger D2). Do not touch demo generators.

## 3. Safety rails

R1. Access: A1 uses the review facade's `_require_write()` + `_editable()` exactly like
    `paste_ratings` (`pb_pay_reviews.py:651-667`). Reading goal scores happens with
    `sudo()` AFTER that check and is limited to the review's own lines' employees — a pay
    reviewer must not get a general window into Goals. B3 requires `group_comp_head`.
    `action_end` has no access check today (FACTS) — leave its behaviour, but the new
    automatic paths run `sudo()` only inside the hooks.
R2. Hooks never raise into the host flow (confirm joined, case open, verdict, resignation
    approval, employee write): try/except, log with `_logger.exception`, continue.
R3. Idempotent: running any hook twice creates nothing twice and moves no date twice.
R4. A2 writes the employee field with `sudo()` like the precedent, only for sheets being
    closed in this run, and posts one chatter line per person in plain words. Reopening a
    year does NOT roll the score back — say so in the close preview text if cheap.
R5. Multi-company: a plan only ever enrols employees of its own company; the daily job
    runs across companies as superuser but writes only state.
R6. Daily job: one `ir.cron` in pb_comp_ben data, `noupdate="1"`, sensible off-peak time,
    no mail. (Deploy note: cron snapshot before/after per ledger.)
R7. White-label, plain words, Lucide icons, quiet chips. Every new string in the module's
    `.po` files that exist (pb_comp_ben: `vi_VN.po` only; check pb_pay, pb_goals,
    pb_probation, pb_offboarding, pb_hiring) — PO parse gate.
R8. Version-bump every module touched.

## 4. Architecture — exact seams

- `pb_pay/models/pb_pay_rating.py`: `SOURCES` += goals; `read_from_goals(review_id,
  cycle_id=None, dry_run=True)` returning the same dict shape as `paste(..., dry_run)`
  plus `years` (id, name, closed) and `mapping`; probe `'pb.goal.set' in self.env`.
  `pb_pay/models/pb_pay_reviews.py`: facade `goal_scores(review_id, cycle_id, dry_run)`;
  the review payload gains `has_goals` (Bool).
  `pb_pay/static/src/js/pay_review.js:701-750` + `pay_review.xml:219-229, 608-645`: the
  button + drawer (clone the paste drawer; no new `markup()` per redraw).
- `pb_goals/models/scoring.py` or a new `pb_goals/models/pay_score.py`: the mapping
  function + `_stamp_performance_score()` called from `_close_for_year()` after `super()`
  (`close.py:243` path). `pb_goals/models/cycle.py:156` + `goal_views.xml:76`: A4.
- `pb_comp_ben/models/benefit.py`: fields, `_enrol_who_qualifies`, `cover_everyone_preview`
  / `cover_everyone`, `_stamp_leaving(employee, last_day)`, `_clear_leaving(employee)`,
  `_cron_end_due()`; `hr.employee` extension for departure/archive.
  `pb_comp_ben/data/`: cron. Views: plan form field, list chips, button.
  `pb_comp_ben/static/src/js/comp_ben_palette.js`: lens (B6).
- `pb_hiring/models/offer_closure.py`: the leg. `pb_probation/models/probation_review.py`:
  probe call. `pb_offboarding/models/resignation.py` (+ where the last day changes or the
  exit is withdrawn): probe calls.

## 5. Numbered test cases (T = Odoo test; write and run)

Tests in each module's `tests/test_wdgap_qf4.py`, tagged to run alone. Tests that need two
modules live in the module that depends on both, or `skipTest` when the other is absent.

1. T Mapping: (score, levels) → rating for 0.0, 0.4, 2.5, 3.0, 4.49, 4.5, 5.0 at levels
   3/4/5; unscored → skipped.
2. T `read_from_goals` dry run writes nothing and reports read/changed/missing counts;
   commit writes `source='goals'` rows; guidance re-applied (a line's suggested rise
   changes as it would after a paste).
3. T A user with pay-review write rights but no Goals rights can use it and gets scores
   only for people on the review; a user without `_require_write` is refused; a
   non-editable review is refused.
4. T Default year = latest closed year ending on/before the effective date; an open year
   can be chosen and is flagged.
5. T Year close stamps `pb_performance_rating` for scored sheets only; a review created
   afterwards seeds those ratings (`_seed_ratings`). Old `action_close` path no longer
   bypasses the close.
6. T Plan "from the day they join": onboarding case open → one enrolment, `started_by=auto`,
   start = joining date; second call → still one.
7. T Hiring `action_confirm_joined` enrols (skip if fixtures are too heavy — then cover by
   calling the leg directly and say so).
8. T Plan "once the trial period is passed": not enrolled at join; enrolled at verdict pass.
9. T Country filter: a plan for another country does not enrol; another company's plan
   does not enrol.
10. T "Cover everyone who qualifies now": preview counts right; confirm adds only the
    missing; refused without `group_comp_head`.
11. T Resignation approved → `end_date` = last working day, `end_reason='leaving'`, still
    "Covered"; cron after that date → "Ended"; cron before → unchanged.
12. T Last day changed → date follows; exit withdrawn → date cleared on leaving rows only;
    a row HR ended by hand untouched throughout.
13. T Employee archived / `departure_date` written without a resignation → same stamping.
14. T Every hook swallows an injected failure (patch `_enrol_who_qualifies` to raise) and
    the host action still completes.
15. T Full existing suites green for every module touched (`-u` each; ledger G35).
16. Browser (local copy; Claude in Chrome per G99): pay review → Read scores from Goals →
    preview → use; plan form → set automatic cover → Cover everyone → list shows chips;
    Benefits lens inside the hub scrolls; console clean.
17. Static gates: py_compile, XML well-formed, PO parse gate, grep the diff for "Odoo" in
    user-visible strings (none).

## 6. Working rules

- NEW git worktree branched from `origin/19.1`, branch `wdgap-qf4`. Local test recipe:
  latest UPDATES reports (`docs/handovers/updates/UPDATES_P5E_REPORT.md`,
  `UPDATES_P6_REPORT.md`) and ledger rows G12, G19, G35, G97.
- Feature-scoped commits (A and B separately), explicit paths; push `wdgap-qf4`. Do NOT
  merge into 19.1. Do NOT deploy.
- Commit messages end with: `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`
- Usage-limit error → one WIP commit, "Where I stopped" in the report, end with PAUSED.

## 7. Report back — `docs/handovers/wdgap/WDGAP_QF4_REPORT.md` (commit it)

1. What was built per scope item; files; version bumps.
2. Test table (each numbered case → pass/fail, command, counts) + full-suite counts.
3. Self-review against §2 and §3, item by item.
4. Decisions you had to take (B1 country resolution, A4, B5, B6) and anything not done.
5. Owner questions as plain real-world questions (e.g. "When the goals year is closed and
   somebody already has a score from a trial-period review, the goals score replaces it.
   Is that what you want?").
6. Deploy notes: modules to `-u`, tier (new stored fields + a new scheduled job → normal;
   say if you think risky), cron added (name), asset purge (yes).
7. New gotchas → rows in `WDGAP_LEDGER.md`.

Final message to the orchestrator: under 250 words — branch, last commit, test counts,
failures or deviations, owner questions.
