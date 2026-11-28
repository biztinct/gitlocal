# WFSETUP P3 — Step 4 "Late and overtime rules" + the real live pay example + automatic holiday / rest-day marking

Read first: `WFSETUP_LEDGER.md`, `WFSETUP_OWNER_RULINGS.md` (**R4–R7 decide this phase**), `WFSETUP_FACTS.md` sections D, E,
F (first two bullets), K (**do not re-derive**), the P1 and P2 reports, then step 4 and the right-hand panel of
`docs/design/workforce-setup-prototype.html`. Where the prototype and the rulings differ, **the rulings win** (see §2.6).

Worktree `/Users/adity/Documents/GitHub/gitlocal-worktrees/wfsetup`, branch `wfsetup`. No deploy, no server access.

This phase touches how paid hours are derived. Treat every write path as pay-critical: tests first, no shortcuts, and stop
and report rather than guess when the facts doc and the code disagree.

## 1. Scope
1. Step 4 screen: the rules as editable sentences (prototype `.rule` / `.sent`), backed by the real rule set.
2. The right panel's sliders + dark result box, computed by the **real engine** on the server, including unsaved edits.
3. "Confirm these rules" = real activation, for everyone in the company.
4. Automatic holiday / rest-day marking of roster shifts (ruling R7).
5. Rail status for step 4.

### Binding non-goals
- No second calculation engine and no JavaScript re-implementation of the maths. The only maths is `pb_attendance_policy/engine.py:calculate`.
- No change to `engine.py`. No change to `pb.attendance.policy` semantics (active rule sets stay immutable — facts D.1).
- No approval switch (R6). No "after N paid hours a day" rule (R5).
- `pb.attendance.rule` grace minutes and `pb_time_pay` (facts D.7) are not touched.
- Overtime ceilings (`pb.ot.ceiling`) are not part of this step.

## 2. Plumbing decisions (made)

### 2.1 "The rules" = one rule set per company, managed by the studio
`pb.workforce.setup._rules_record()`: the company's ACTIVE `pb.attendance.policy` if one exists, else its newest DRAFT, else none.
- No rule set yet → `rules()` returns sensible defaults (below) with `state:'new'`; the first save creates a draft
  (`tz` = company calendar tz → user tz → UTC; name "<Company> attendance rules").
- Draft → edits write straight to it (autosave 600 ms after the last change, "Saving… / Saved" marker, as P1's weeks).
- Active → the step is read-only with the line "These rules are in use." and one button **Change the rules**; that makes a
  revision (`policy.copy()` → draft, facts D.1) and the screen edits the draft; the active one keeps calculating meanwhile.
  A banner says "You are editing a new version. The current rules stay in use until you confirm."; **Discard changes** deletes the draft.
- More than one active policy in the company, or employees pointing at different policies → do not guess: the step shows
  "This company uses more than one set of rules. Open the advanced rules screen." with a button to the existing policy
  action, and is otherwise read-only. (Test it.)

### 2.2 Payload and mapping
`rules()` → `{state:'new'|'draft'|'active'|'revision'|'advanced', can_edit, late:{worker:[{from,to,hours}],manager:[…]},
shifts:[{shift_id,name,start,end,break_start:'HH:MM',break_minutes,overtime_from:'HH:MM',in_weeks:bool}], rates:{normal,rest_day,holiday,night}
(percent ints), night:{on,from,to}, clock:{before,after}, people:{total,with_rules,worker,manager}, problems:[sentence]}`.
- **Late lines** (facts D.1: bands are `[minimum, maximum)` minutes, must start at 0, be contiguous, last one open-ended, all
  confirmed to activate). The screen shows inclusive whole minutes from 1: line `{from:1,to:9}` ⇔ band `[1,10)`. The server
  always maintains a hidden first band `[0, first.from)` with 0 hours and makes the last line open-ended ("30 minutes late or
  more"). `save_rules` receives the lines and REBUILDS the bands of that group in one write (sorted, gap-free by
  construction: each line's `to` = next line's `from − 1`; the client enforces it while typing, the server re-validates and
  refuses with "The late lines must follow on from each other with no gap."). `hours` 0–24 in steps of 0.25.
- **Per-shift lines** (R5; facts D.1 `pb.attendance.policy.shift`): one line per active shift of the company, those used in a
  working week first: "<Shift> 07:30–16:30 · unpaid break starts at [11:30] · overtime starts at [16:30]".
  `break_start_offset` / `normal_end_offset` are elapsed hours from the shift start — convert to and from clock times across
  midnight for overnight shifts. `break_hours` is kept equal to the shift's own break (step 1); a shift edit in step 1
  re-syncs it when the rule set is a draft. Defaults when a shift has no line yet: break in the middle of the shift,
  overtime from the shift's end. Lines are created for every shift used in a working week; `_check_rule` refusals
  (facts D.1) are surfaced as "Overtime must start after the shift starts and no later than it ends." etc.
- **Rates** (facts E.1): three numbers — normal overtime (`weekday`), rest day (`weekend`), public holiday (`holiday`) — plus
  night extra (`night`: 30 % ⇔ multiplier 1.3). Read the row the runtime would pick for this company and its country
  (`overtime_request.py:93-107`). FIRST write a test that pins the facts-doc suspicion that a GLOBAL row can beat a specific
  one because of `order … desc` with NULLs first. If it is real, fix the resolution in `pb_hr_workforce` so the most specific
  row wins (company+country > company > country > global), with a test in that module, and bump its version — this is the one
  allowed edit outside our module. On save: if the picked row belongs to this company, write it; otherwise create a
  company-specific row (country = company country) so other companies in the database are never changed. Minimum 100 %.
- **Night**: `night_premium`, `night_start`, `night_end` on the rule set. **Clock window**: `capture_before/after`, 0–6 h.
- **Approval**: a fixed sentence, no control: "Overtime always needs a manager's approval before it is paid."

### 2.3 Confirm = activate for everyone
`confirm_rules()` (edit gate; one transaction; savepoint):
1. Mark every band of both groups confirmed (pressing Confirm IS the confirmation).
2. `action_activate()` on the draft; translate each precondition failure (facts D.1 `:68-84`) into one plain sentence in
   `problems` rather than a traceback, e.g. "Managers have no late lines yet."
3. If this was a revision: retire the previously active rule set.
4. Point every active employee of the company at the active rule set and give people with no group the group Worker
   (sudo after the gate — facts K24). 
5. Future, not-yet-calculated roster rows of those people (`date >= today`, no generated attendance, calculation status
   empty) get `pb_policy_id` = the active rule set (facts D.2 / open risk 1: rows created before a person had rules carry
   none and are ignored by the calculation job). Verify which context token, if any, guards `pb_policy_id` and use the
   module's own path; never write calculated fields.
Returns `{people, rows_updated, retired}` → toast "Rules confirmed for 678 people."
Also: new employees created later in a company with exactly one active rule set get it and group Worker automatically
(`hr.employee.create` override in our module; test it does nothing when there are zero or several active rule sets).

### 2.4 Live pay example (the hero)
`pay_example(employee_id, in_minutes, out_minutes, rules=None, day_kind='weekday')` — read gate, **writes nothing**:
- the person's first working day this week (from P1's `person_week`), its shift, the person's group;
- follow the chain in facts D.3 steps 1–7 exactly, using `Grid._pb_shift_window` / `_pb_shift_tzname`;
- `rules` (optional) = the screen's current unsaved values, used INSTEAD of stored ones (late lines → band dicts with
  `confirmed: True`; this shift's break/overtime times; night settings). Stored draft bands are also passed as confirmed —
  a hypothetical must not fail on "not confirmed".
- punches = shift start + `in_minutes`, shift end + `out_minutes`.
Returns the engine's numbers plus ready sentence parts: `{clock_in, clock_out, late_minutes, taken_off_hours, worked_hours,
normal_hours, overtime_hours, night_hours, rate_percent, group, shift_name, day_label, error:sentence|false}`.
Client: sliders call it throttled (leading + trailing, 120 ms), drop out-of-order replies, and keep the last good result on
screen while a new one loads (no flicker — ledger gotcha on `t-out`/markup). A small three-way choice above the sliders:
**Normal day · Rest day · Public holiday** (feeds `day_kind`, shows the matching rate). Remember: the real engine does not pay
early arrival (facts D.6) — the "Clocks in" slider label must say "10 min early (not counted)".
Engine `error` values are mapped to plain sentences; never show the raw key.

### 2.5 Automatic holiday / rest-day marking (R7)
New stored Boolean on `hr.shift.planning` in OUR module: `pb_day_kind_manual` ("Day type set by hand", default False).
- On create, when `pb_day_kind` is not given: compute it — `holiday` when the shift's local start date is a public holiday /
  company day off for that person (reuse `pb.shift.pattern.engine._pb_holiday_map` — facts B.3 — do not re-implement);
  else `weekend` (the "rest day" kind) when the person's working week has that day OFF (cycle index via `_pb_cycle_index`,
  honouring team offset and member dates), or, for a person with no working week, when their working calendar has no hours
  that weekday; else `weekday`.
- When a user sets `pb_day_kind` explicitly (form or any write carrying the key without our context flag) → `pb_day_kind_manual = True`
  and it is never recomputed.
- `pb.workforce.setup.remark_days(date_from=None)` — recomputes every NOT-manual, not-yet-calculated row from today on for the
  company; returns `{checked, changed:{holiday:n, rest_day:n, normal:n}}`. Called automatically after `confirm_rules`, after a
  holiday is added/removed (P4 wires that), and exposed on screen in this step as a quiet link "Re-check holiday and rest-day
  shifts" with the result in a toast (owner rule: whatever the backend does must be doable on screen).
- Bulk creates (pattern engine makes thousands of rows) must stay fast: compute per batch with one holiday-map call and one
  membership read, not per row. Test with 3,000 rows.

### 2.6 Where the prototype is overruled
| Prototype | Build |
|---|---|
| "After 8 paid hours in a day…" | one line per shift with a clock time (R5) |
| approval switch | fixed sentence (R6) |
| one rest-day % and one holiday % shown only as text | same numbers, and the example can be switched to rest day / holiday |
| "Between 1 and 9" lines editable freely | `to` of a line drives the next line's `from`; last line is "N minutes late or more" |

## 3. Design bar (verbatim, binding)
"extreme WOW, intuitive, out-of-this-world experience, best in class." Hero moment: change a number in a sentence and the
dark box on the right re-works a real person's paid hours before you lift your finger. Zero dead-ends (every engine refusal
has a sentence and a fix), plain language, motion with purpose, keyboard ergonomics (Tab walks the highlighted numbers in
reading order; arrow keys step them). Lucide via `ic()`, never emoji. One solid primary per bar. No "Odoo" in any
user-visible string. Screen words: "rules", "late", "overtime", "rest day", "public holiday", "night work" — never policy,
band, category, offset, capture, pairing, multiplier, day kind.

## 4. Numbered test cases
Python (`tests/test_rules.py`, tags `post_install, -at_install, wfsetup`):
1. `rules()` with no rule set → defaults, `state 'new'`, nothing created. First `save_rules` creates one draft.
2. Late lines `[1–9: 0, 10–29: 0.5, 30+: 1]` → bands `[0,1) 0`, `[1,10) 0`, `[10,30) 0.5`, `[30,∞) 1`; round-trip returns the same lines.
3. Gap or overlap in submitted lines → the refusal sentence, nothing saved.
4. Per-shift line: day shift 07:30–16:30, break 11:30, overtime 16:30 → offsets 4.0 / 9.0; overnight 19:30–04:30, break
   23:30, overtime 04:30 → 4.0 / 9.0; overtime time outside the shift → refusal sentence.
5. Changing a shift's break in step 1 re-syncs `break_hours` on a draft rule set and never touches an active one.
6. Rate resolution pin test (global vs specific); after the fix the specific row wins; saving rates never changes a row of
   another company or a shared global row.
7. `confirm_rules`: all bands confirmed, state active, all active employees pointed at it, groupless → Worker, future
   uncalculated roster rows get `pb_policy_id`, past/calculated rows untouched.
8. Confirm with managers missing lines → `problems` sentence, still draft, nothing else changed (transaction rolled back).
9. Revision flow: Change the rules → draft copy; edits do not affect the active one; Confirm → new active, old retired,
   employees and future rows re-pointed; Discard → draft gone, active untouched.
10. Two active rule sets → `state 'advanced'`, every write method refuses with the sentence.
11. Officer: `rules()` and `pay_example()` allowed; `save_rules` / `confirm_rules` / `remark_days` AccessError.
12. `pay_example` equals a direct `engine.calculate` call built by hand for: on time; 12 min late worker vs manager; 45 min
    late; leaves 60 min after overtime start; leaves early; overnight shift with night extra on; rest day; public holiday.
13. `pay_example` with unsaved `rules` differing from stored → uses the unsaved ones; writes nothing (row counts and max
    write_date on policy, band, shift-rule, roster, attendance tables unchanged).
14. `pay_example` for a person with no working week / no group / shift without a line → `error` sentence, no exception.
15. Auto marking on create: public holiday → holiday; one-off on the person's day off → rest day; normal → normal; explicit
    value in vals → kept and `pb_day_kind_manual True`.
16. Manual edit later → flag set; `remark_days` skips it; a non-manual row flips when a holiday is added then `remark_days` runs.
17. `remark_days` never touches rows with generated attendance or calculation status.
18. 3,000-row batch create stays under an agreed budget (report the number) and query count does not grow per row.
19. New employee in a company with one active rule set gets it + Worker; with none or two → untouched.
20. Existing suites: `/pb_attendance_policy` (8 + standalone engine 11), `/pb_hr_workforce`, `/pb_shift_patterns`, `/pb_schedule`,
    `/pb_workforce_workspace`, all earlier wfsetup tests — baseline first, then after.

Browser walk:
B1 change "10 → 15" in a late line: next line's start follows; "Saved"; the right box changes with a 12-minute-late example.
B2 Workers / Managers switch; add a line; remove a line.
B3 per-shift overtime time: move it 30 minutes earlier → example shows more overtime.
B4 night switch on with an overnight shift person → night hours appear.
B5 Normal day / Rest day / Public holiday choice changes rate and result.
B6 sliders: smooth, no flicker, "early (not counted)" wording.
B7 Confirm with a deliberate gap in managers → the sentence; fix; Confirm → toast with the people count; step turns green.
B8 Change the rules → banner; edit; Discard; again → Confirm → still green.
B9 "Re-check holiday and rest-day shifts" → toast with counts.
B10 officer read-only; widths 1440 / 1100 / 800 / 400; console clean. Screenshot beside the prototype; list open differences.

## 5. Report back (`WFSETUP_P3_REPORT.md`, committed)
As P1 §5, plus: the result of the rate-resolution pin test and exactly what you changed in `pb_hr_workforce` (if anything);
which guard protects `pb_policy_id` on roster rows; the measured batch-create numbers; a short "what a payroll person
should double-check" list for the deploy phase. On a usage limit: WIP commit, "Where I stopped", end with PAUSED.
