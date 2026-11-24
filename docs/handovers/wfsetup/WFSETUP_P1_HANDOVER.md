# WFSETUP P1 — screen shell + Shifts + Working weeks

Read first, in this order: `WFSETUP_LEDGER.md` (standing rules — binding), `WFSETUP_FACTS.md` (verified plumbing — **do not
re-derive**; sections 0, A, B, H, J, K matter for this phase), then open `docs/design/workforce-setup-prototype.html` in a
browser and click through steps 1 and 2. The prototype is the design of record: layout, wording, spacing, colours, motion.

Work ONLY in this worktree: `/Users/adity/Documents/GitHub/gitlocal-worktrees/wfsetup` (branch `wfsetup`). Never edit the
shared checkout `/Users/adity/Documents/GitHub/gitlocal`. No deploy, no server access in this phase.

## 1. Scope

A new module **`pb_workforce_setup`** (19.0.1.0.0) containing:
1. The **Setup Studio** client action: top bar with progress, 7-step rail on the left, working area in the centre, the
   "See it on a real person" panel on the right (prototype `.top`, `.steps`, `.stage`, `.pv`).
2. **Step 1 Shifts** — fully working against `hr.shift.template`.
3. **Step 2 Working weeks** — fully working against `pb.shift.pattern` (+ slot / team).
4. Steps 3–7: the rail entries with REAL status text where this phase can compute it (step 3 count), and a designed
   "This step arrives next" panel in the centre for 3–7 (one calm card, the step's question as the heading, no fake controls).
5. The right panel in P1: person picker + that person's week strip + per-day shift times. The sliders and the dark result box
   arrive in P3 — in P1 show the week strip and, under it, the line "Pay example appears here once the late and overtime
   rules are set up." Empty state exactly as the prototype ("… has no working week yet").

### Binding non-goals (do NOT do these)
- Do not touch `pb_workforce_workspace`, its Settings card, the Mission tabs or any other module's files. Takeover is P5.
  The new screen is reached in this phase only by its own action (`/bizapp/action-pb_workforce_setup.action_setup_studio`).
- No bulk people actions (P2), no rules (P3), no holidays/clocks/publish (P4), no .po files (P5) — but every user-visible
  string must already be translatable (`_t(...)` in JS, plain text nodes in templates, `_()` in Python), one sentence per line.
- No new stored fields on existing models. No changes to `hr.shift.template` / `pb.shift.pattern` Python.
- No dependency on `pb_attendance_policy` or `hr_shift`.
- No new calculation logic.

## 2. Plumbing decisions (made — follow them)

**Module**: `pb_workforce_setup/` at the repo root. `depends`: `pb_workforce_workspace` (brings pb_mission, pb_shift_patterns,
pb_clock, pb_settings), `pb_wf_kit`, `pb_import_kit`, `pb_hub`, `pb_timeoff`. Verify each is a real module and that none
creates a dependency cycle; report if `pb_timeoff` cannot be depended on. Manifest `name`/`summary` must not say "Odoo".
`views/setup_action.xml`: `ir.actions.client` id `action_setup_studio`, name "Workforce setup", tag `pb_workforce_setup_studio`
(new tag — do NOT reuse `pb_workforce_setup`). Assets in `web.assets_backend`. CSS prefix **`pbws-`** (grep the repo first; if
taken pick `pbwz-` and note it in the ledger). Root element also carries `.pbim` so kit tokens/buttons apply.

**Server facade** `pb.workforce.setup` (AbstractModel, `models/setup.py`). Clone the gate style of
`pb_workforce_workspace/models/workspace.py:39` and `pb_shift_patterns/models/patterns_board.py:42-67`.
- `_gate_read()`: `hr_attendance.group_hr_attendance_officer` or `base.group_system`, else AccessError("Attendance access is required.").
- `_gate_edit()`: `hr_attendance.group_hr_attendance_manager` or `base.group_system`, else AccessError with the plain sentence
  "Only an attendance manager can change the workforce setup."
- Every domain is scoped to **`self.env.company` only** (facts K2: no company record rules on shifts/roster). Shared shifts
  (`company_id = False`) are listed and usable but shown with a small "Shared" chip and are read-only here.
- `load()` → `{can_edit, company:{id,name}, today, features:{rules: 'pb.attendance.policy' in env}, steps:[…7], shifts:[…], weeks:[…]}`.
  `steps[i] = {key, state:'done'|'warn'|'todo', text}`. Keys: `shifts, weeks, people, rules, holidays, clocks, live`.
  P1 rules: shifts done when ≥1 usable shift else warn "Add your first shift"; weeks done when ≥1 else warn; people warn
  "N people have no working week" / done "All N people have a working week" where a person HAS a week when an active
  `pb.shift.pattern.member` row in an active pattern of this company covers today (`date_from` empty or ≤ today, `date_to`
  empty or ≥ today), counted over active employees of the company (sudo read AFTER the gate, facts K3/K24); rules, holidays,
  clocks, live → `todo` with text "Coming next" in P1 (later phases replace them).
- Shifts
  - row shape: `{id, name, code, start:'HH:MM', end:'HH:MM', break_minutes:int, color:<name>, overnight:bool, paid_minutes:int, shared:bool, used_weeks:int, used_roster:bool}`.
  - `save_shift(vals, shift_id=False)` — vals `{name, start, end, break_minutes, color}`. Sets `is_overnight = end <= start`
    (facts A: it is a manual tick and `_check_hours` refuses otherwise). On create: `company_id = env.company`; `code`
    generated (uppercase initials of the name, max 4 chars, then `-2`, `-3`… until no shift of this company or shared has it —
    facts A: uniqueness is NOT enforced by the DB, so check it yourself); `shift_type` derived once (start < 12:00 morning,
    < 18:00 afternoon, else night) and never changed afterwards. Plain UserErrors for: empty name; start == end
    ("A shift needs a start and an end that differ."); break ≥ shift length ("The break is longer than the shift.");
    break < 0. Returns the row.
  - `copy_shift(shift_id)` → new row named "<name> (copy)", new code.
  - `remove_shift(shift_id)` → if used by any `pb.shift.pattern.slot` (any company the user can see): UserError "This shift is
    used in N working week(s). Take it out of them first." Else if referenced by `hr.shift.planning` or (when installed)
    `pb.attendance.policy.shift`: archive (`active=False`) and return `{archived: True}`. Else unlink → `{archived: False}`.
  - Colour: the model stores an integer palette index (facts A). Find how `pb_schedule` turns that index into a CSS colour and
    choose the 6 indices closest to the prototype's indigo / teal / amber / blue / rose / green; keep ONE mapping table
    (Python constant mirrored in JS via `load()` payload — do not duplicate the table in two files). Unknown stored indices
    render as indigo and are preserved on save unless the user picks a colour.
- Working weeks (a "working week" = `pb.shift.pattern`)
  - row shape: `{id, name, editable:bool, weeks:[[shift_id|false ×7], …], people:int, minutes_per_week:[…], cycle_days, reason:str|false}`.
    `editable` is True only when `cycle_days % 7 == 0` AND `start_date` is a Monday. Otherwise `weeks` is still produced for
    display where possible, `editable False`, `reason` = "This rotation does not follow whole weeks." and the card shows a
    quiet "Open the rotation editor" button → existing patterns board (`pb_mission.action_pb_workforce` with context
    `pb_shell_lens: 'patterns'`). Never a dead end.
    Mapping (facts B.1): `weeks[w][d]` ⇔ slot `day_index = 7*w + d`.
  - `save_week(vals, week_id=False)` — vals `{name, weeks}`. **Do NOT call `save_pattern`** (it replaces teams and members
    whole — facts B.2). Write with the ORM behind `_gate_edit()`: name, `cycle_days = 7*len(weeks)`, slots upserted by
    `day_index`, slots with `day_index >= cycle_days` deleted; teams and members untouched (ids must survive). Create:
    `start_date` = Monday of the current week, `company_id = env.company`, one team "Team A" offset 0, `cycle_days` as above.
    1 ≤ weeks ≤ 8 (56-day limit). Shift must be usable in this company (same rule as `patterns_board.py` save_pattern's
    template check). Catch the model's ValidationError when shrinking under a team offset and re-raise as "A team in this
    working week starts in a later week. Move that team first in the rotation editor."
  - `remove_week(week_id)` — refuse when it has current/future members ("N people work this week. Move them to another week
    first."), else archive via the existing `archive_pattern` semantics.
- `find_people(query='', limit=20)` and `person_week(employee_id)` for the right panel: `person_week` returns
  `{id, name, department, week_name|false, days:[{label, shift_id|false, start, end} ×7]}` for the CURRENT week using the real
  cycle index formula (`shift_pattern.py:114-118` — call `_pb_cycle_index`, do not re-implement it), honouring team offset and
  member dates. Default person = first employee (by name) who has a week, else first employee.

**Client** (`static/src/js/…`, `static/src/xml/…`, `static/src/scss/setup_studio.scss`):
- `setup_studio.js` root (`registry.category('actions').add('pb_workforce_setup_studio', …)`), child components
  `StepShifts`, `StepWeeks`, `StepSoon`, `PreviewPanel`. Imports exactly as spelled in facts §0/§H
  (`@pb_import_kit/js/import_icons` `ic`, `@pb_hub/js/hub_nav` `HubBackChip, hubBack` with `tone="light"`).
- Icons: only names listed as present in facts H; cache markup once (facts K6); an unknown name silently renders a tick (K7) —
  the static test below guards it. Missing `arrowLeft`: use a rotated `arrowRight` or text.
- Port the prototype's CSS under `.pbws-…` 1:1 (same paddings, radii, type sizes), replacing its `:root` colour tokens with the
  kit's `pbim` tokens where an equivalent exists and keeping the literal value where not. No gradients, no emoji.
- Saving model (decided):
  - Shifts: editing happens in place in the expanded row on a local draft; the bar, the times and the paid-hours summary
    update on every keystroke (prototype behaviour). The row button reads **Save** when the draft differs (primary) and
    **Done** when it does not; a quiet **Cancel** restores. Leaving the step or opening another row with unsaved changes
    saves first; a refused save keeps the row open with the server's sentence shown inline under the fields (not only a toast).
  - Working weeks: paint by click or drag (pointer events as in the prototype) and keyboard (Enter/Space on a focused day);
    each working week autosaves 600 ms after the last change, with a small "Saving…" → "Saved" marker in its header; on a
    refused save restore the last saved state and show the sentence. Name saves on blur/Enter.
  - After any save, refresh the step statuses and the right panel (one `load()`-style refresh, sequence-guarded against
    out-of-order replies — precedent `workspace.js` `seq`).
- Read-only users (officer): everything visible, every control that changes data hidden or disabled, and one line under the
  heading: "You can look, but only an attendance manager can change this."
- States to design and build: loading skeleton; load error with "Try again"; no shifts yet (the four starter buttons become
  the centre of the card with the sentence "Start with one of these, then adjust the times."); no working weeks yet;
  no shifts when entering step 2 ("Add a shift first" → button to step 1); 30+ shifts (list scrolls inside the page, no
  layout break); long names (ellipsis, full name in `title`).
- Responsive: same breakpoints as the prototype (≤1180 px the right panel drops under the centre; ≤820 px the rail becomes a
  horizontal strip). The Payobook sidebar must stay visible (tag starts with `pb_` — facts H).
- URL: remember the current step in the action's state so a browser refresh returns to the same step.

## 3. Design bar (verbatim, binding)
"extreme WOW, intuitive, out-of-this-world experience, best in class." Hero moment for this phase: the 24-hour shift bar that
reshapes as you type, and painting a week by dragging. Zero dead-ends (every state above designed, every refusal names its
reason and next step), plain language over code vocabulary, motion with purpose (bar transitions, drawer/row expand — respect
`prefers-reduced-motion`), keyboard + bulk ergonomics. Lucide icons only, never emoji. One solid primary button per bar.
White-label: the word "Odoo" must not appear in any user-visible string. Screen words: "shift", "working week", "day off",
"unpaid break" — never template, pattern, slot, cycle, policy, code names of fields.

## 4. Numbered test cases

Python (`tests/test_setup.py`, `@tagged('post_install','-at_install','wfsetup')`; fixtures cloned from
`pb_workforce_workspace/tests/test_workspace.py`: manager, officer, basic user, two companies; obey facts K4/K5):
1. `load()` — basic internal user AccessError; officer `can_edit False`; manager `can_edit True`; payload has 7 steps in order.
2. `save_shift` create 22:00→06:00 break 30 → `is_overnight True`, `break_duration 0.5`, company = env.company, code set.
3. Two shifts with the same initials get different codes; a shared shift's code is also avoided.
4. `save_shift` refusals: empty name, start == end, break ≥ length — each a UserError with the sentences above.
5. Officer calling `save_shift` / `copy_shift` / `remove_shift` / `save_week` / `remove_week` → AccessError.
6. Editing 08:00–17:00 to 20:00–04:00 flips `is_overnight` to True and back to False when edited to 08:00–17:00.
7. `remove_shift`: unused → deleted; used in a working week → UserError naming the count; used only by a roster row → archived.
8. `copy_shift` → "(copy)", new code, same times/break/colour.
9. `weeks()` shape: 7-day Monday pattern → 1×7; 14-day → 2×7; a 5-day cycle or a non-Monday start → `editable False` with reason.
10. `save_week` create → Monday start, `cycle_days 7`, one team offset 0, slots match the grid, off days have no template.
11. `save_week` edit on a pattern with 2 teams and 3 members → team ids and member ids unchanged; changed cells only.
12. Shrink 2 weeks → 1: slots with `day_index ≥ 7` gone; with a team offset 7 → the plain refusal, nothing changed.
13. `save_week` with a shift of another company → refused; more than 8 weeks → refused.
14. `remove_week` with a current member → refused with the count; with only past members (`date_to` < today) → archived.
15. Company isolation: company B's shifts/weeks never appear for A; a user with both companies allowed sees only `env.company`.
16. Step-3 status count: member with `date_to` yesterday and member with `date_from` tomorrow both count as "no working week".
17. `person_week`: team offset 7 on a 14-day rotation shows week 2's shifts; a member past their `date_to` shows no week.
18. Static (`tests/test_static.py`, clone `pb_shift_patterns/tests/test_static.py`): no "Odoo" in any user-visible string of
    the module; every `ic('…')` name used exists in `pb_import_kit/static/src/js/import_icons.js`; no emoji characters in
    js/xml/scss.

Also run and report the existing suites of the modules you depend on that this could affect: `/pb_workforce_workspace`,
`/pb_shift_patterns` (facts J.1 for commands, tags and known flaky baselines). Baseline first, then with the new module.

Browser walk (Chrome tools; local server on a copy of `upd_p6_t_tpl`, port block 8190–8199, host `wfs1.localhost`,
`--max-cron-threads=0`; facts J.1 for the traps; disk is 98 % full — ONE small DB, drop it and its filestore when done):
B1 open the action as a manager: rail, progress, both steps, right panel render; console clean.
B2 edit a shift's end time: bar and summary change while typing; Save; refresh the browser → still there, same step.
B3 create from each starter; overnight starter draws two segments and says "ends next day".
B4 copy, then remove the copy; try removing a shift used in a week → the sentence, no crash.
B5 paint by click, by drag across 5 days, and by keyboard; "Saved" appears; refresh → persisted.
B6 add a rotation week, paint nights, remove the last week.
B7 new working week from empty; rename; remove.
B8 right panel: pick a person with a week → strip matches step 2; person without → empty state and its button.
B9 sign in as an officer: read-only line, no edit controls, no errors.
B10 widths 1440, 1100, 800, 400: no horizontal page scroll, nothing clipped. Screenshot each step at 1440 next to the
    prototype and list every visual difference you could not close.

## 5. Report back (`docs/handovers/wfsetup/WFSETUP_P1_REPORT.md`, committed)
- Result per numbered test and per walk item (pass/fail, with output for failures); suite totals before/after.
- Deviations from this handover and why. Anything in the facts doc that turned out wrong (with file:line).
- Self-review against §3: score each bullet, name the weakest point honestly.
- New gotchas → append to the ledger's gotcha section (WS1…).
- The colour index mapping you chose and how you derived it.
- Commits (feature-scoped, explicit paths, no client folders, no credentials). Commit messages end with:
  `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`
- If you hit a usage/session limit: one WIP commit, a "Where I stopped" section, end your reply with PAUSED.
