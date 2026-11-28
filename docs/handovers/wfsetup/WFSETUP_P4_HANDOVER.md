# WFSETUP P4 — Step 5 Holidays, Step 6 Time clocks, Step 7 Check and go live

Read first: `WFSETUP_LEDGER.md`, `WFSETUP_OWNER_RULINGS.md`, `WFSETUP_FACTS.md` sections B.3, B.5, F, G, K (**do not
re-derive**), the P1–P3 reports, then steps 5, 6 and 7 of `docs/design/workforce-setup-prototype.html`.
Worktree `/Users/adity/Documents/GitHub/gitlocal-worktrees/wfsetup`, branch `wfsetup`. No deploy, no server access.

Live facts read from the Sudima database on 2026-11-25 (read-only; use them to shape tests and seed data, do not connect):
- 678 active people, 27 without rules; 3 working weeks, all 7-day, Monday start, one team each (511 / 4 / 2 people).
- 12,384 roster rows, ALL draft, ALL carrying a working-week mark, a rule set and the "suggested" flag, 19 Nov–16 Dec 2026.
- 6 clock connectors, all connected, last heard 23–24 Nov. No future public holidays stored at all.
- `pb_attendance_policy` installed only on sudima; `pb_timeoff`, `pb_clock`, `pb_shift_patterns` installed on all five.

## 1. Scope
1. **Holidays** — a year of small month calendars (prototype `.months`): public holidays, company days off, weekly rest days
   shaded; click a day to add/remove a company day off; a list of the year's days off; one-click suggested public holidays
   for the company's country; Confirm.
2. **Time clocks** — one card per clock with honest health; "Copy setup link for IT"; add a clock; people with no clock
   number; the "no machine at a site?" options that really exist; Confirm.
3. **Check and go live** — checklist with Fix buttons; first-week roster preview; "Publish N weeks" that makes the roster,
   marks holiday/rest days and publishes, with visible progress; the "Workforce is live" finish.
4. Every rail status real; the top progress counts real steps.

### Binding non-goals
- No change to `pb_timeoff`, `pb_clock`, `pb_shift_patterns`, `pb_schedule`, `pb_ess_workforce` code.
- Do not use `publish_shifts` / `publish_shifts_notified` as they are (no company filter — facts B.5).
- No new holiday storage: rows stay `resource.calendar.leaves` through `pb.holidays` (`_create_row` — facts F; never create
  rows directly).
- No clock protocol work, no device pairing wizard changes.
- Not in this phase: Settings takeover, trimming the Workforce tabs, translations (P5).

## 2. Plumbing decisions (made)

**Per-company setup state** — new stored fields on `res.company` in our module (admin/manager-written only through the
facade): `pb_wfs_holidays_year` (Integer, last confirmed year), `pb_wfs_clocks_ok` (Boolean), `pb_wfs_live_on` (Date first
published through the studio), `pb_wfs_live_to` (Date the roster is published up to). Version → 19.0.1.3.0.

### 2.1 Holidays
- `holidays(year=None)` (read gate) → `{year, years:[…], can_edit, has_calendar, days:[{id, date, date_to, name, kind:'public'|'company'|'collective'}],
  rest_weekdays:[0-6…], working_days:int, suggestions:{country, year, count, missing:[{date,name}]}|false, confirmed:bool}` — built
  from `pb.holidays.year()` for `env.company` only. `rest_weekdays` = weekdays that are off in the company's most-used
  working week (shading only). `working_days` = days of the year that are neither rest weekday nor day off.
- Writes go through OUR edit gate (attendance manager), then the existing `pb.holidays` methods with sudo **after** the gate
  and an explicit `company_id == env.company` check — facts F: the underlying write gate does not include attendance
  managers; this is a deliberate, owner-accepted widening limited to the studio. Test that an officer is still refused.
  - `add_day_off(date, name=None, kind='company')`, `remove_day_off(row_id)` (a public holiday asks inline "Remove New Year
    for everyone?" first), `add_suggested(year)` (all-or-nothing via `add_many`).
  - Find out which kind `pb.holidays.add` stores and make company days off land as kind `company`; report how.
- Suggestions: `pb_workforce_setup/data/holiday_suggestions.json`, keyed by country code and year. Ship **VN 2027**:
  1 Jan New Year; 5–9 Feb Tet (Lunar New Year is 6 Feb 2027); 16 Apr Hung Kings Day (10th day of the 3rd lunar month);
  30 Apr Reunification Day; 1 May Labour Day; 2 Sep National Day. Verify the two lunar dates independently (compute the
  lunar calendar or cross-check two sources available offline; if you cannot verify, keep them and say so in the report).
  Also read `pb_timeoff/data/holiday_reference.json` (2026 rows by country) as suggestions for 2026. The card says:
  "Vietnam public holidays for 2027 · 10 days · Add them all" and, under it, "Tet and Hung Kings follow the lunar calendar,
  and the extra National Day holiday is announced each year. Check the government notice before you confirm."
  No list for the country/year → no card (never an empty promise).
- Company has no working calendar (facts F) → the step shows "Choose the company's normal working calendar first." with a
  button to the existing calendars screen; calendar grid still renders read-only.
- After every add/remove call P3's `remark_days()` and say what changed in the toast ("Added. 3 planned shifts are now paid
  as public holiday."). Undo in the toast.
- **Confirm** → `confirm_holidays(year)`; status done "N days off in <year>"; in October–December also nudge once, quietly:
  "Next year's holidays are not set yet" with a jump to next year.

### 2.2 Time clocks
- `clocks()` (read gate) → `{can_edit, clocks:[{kind:'pc'|'machine', id, name, where, state:'ok'|'quiet'|'waiting'|'attention'|'off',
  last_heard, today:int, pending:int, problem:sentence|false, invite_until}], no_number:int, options:[…], confirmed}` from
  `pb.clock.connector` (facts G `_setup_status`) and `pb.clock.device` (via the existing lens API), company-scoped.
  `ok` = heard from in the last 24 h and no error; `quiet` = connected but silent > 24 h ("Quiet since Mon 23 Nov");
  `waiting` = awaiting setup; `attention` = has an error (map `last_error` to one plain sentence, never raw text with paths
  or codes); `off` = revoked. Timestamps shown in the user's timezone as "2 hours ago" / a date.
- `clock_invite(connector_id)` (edit gate) → calls the model's own `_new_invitation` (keep its manager check and row lock —
  facts G) and returns the token + expiry; the client builds `location.origin + '/clock-bridge/setup#' + token` exactly as
  `pb_clock/static/setup/setup.js:132-137` does. When a still-valid invitation exists the card first asks inline:
  "This replaces the link you sent before. Make a new one?" Copy uses `navigator.clipboard` with a select-the-text fallback.
  The toast says "Setup link copied. It works for 5 days." — never claims it was sent.
- `clock_add(name, where)` (edit gate) → creates a connector with the model's required fields (tz from the company calendar);
  then shows its card with the copy-link action. "Clock details" on any card → the model's existing `action_setup`.
- `no_number` = active people with neither a clock number nor a badge number (facts G); chip "N people have no clock number"
  → jumps to step 3 with a new quick filter "No clock number" (add that filter to step 3; row data already has `number`).
- "No machine at a site?" — offer ONLY options that exist in this build. Check each: phone clock-in for employees
  (`pb_me_*` / `pb_clock` employee clock), file import (Time hub "Import" tab), hours typed by a supervisor (Week grid).
  Each is a real link; drop any you cannot open. Report which survived.
- **Confirm** → `pb_wfs_clocks_ok`. Label "Clocks are fine. Confirm", or "Continue, finish N clock(s) later" when some are
  waiting/quiet/attention (still confirms; rail shows "N to finish later").

### 2.3 Check and go live
- `live_check(weeks=4)` (read gate; preview part needs the maker gate, so for officers return the checklist only) →
  `{steps:[{key,title,ok,text,blocking}], weeks, window:{from,to}, plan:{people, new_shifts, already_planned, skipped:{reason:n}},
  sample:[{name, days:[{label,start|false,shift_id}]} ≤6], live:{on,to}|false, can_publish, publish_label}`.
  - `plan` from the existing engine preview (`pb.shift.patterns.preview` for all active working weeks of the company — facts
    B.2/B.3; writes nothing). Start = today (engine snaps to Monday and skips past days). 1 ≤ weeks ≤ 12.
  - Blocking: no shift; no working week; nobody has a working week; rules not confirmed. Not blocking (amber, with Fix):
    people without a working week ("Publish for the 96 who are ready"), holidays not confirmed, clocks not confirmed.
- Publishing runs **one week per call** so the screen can show progress and nothing times out on 12,000+ rows:
  `go_live_start(weeks)` → `{run_id, weeks:[{from,to}]}` (edit gate; re-checks blockers; calls `make_drafts` for the whole
  window once; then `remark_days()`); `go_live_week(run_id, index)` → publishes that week's DRAFT rows **of `env.company`
  only** by calling the records' own `action_publish()` (so the acknowledgement override in `pb_ess_workforce` runs — facts
  B.5) in chunks, then the same notification step the Schedule uses if it can be called on a recordset (read
  `pb_ess_workforce/models/publish_notify.py:72-92`; if it only works by window, call its internals on our company-filtered
  records; tenant mail may be off — report "no channel" counts truthfully, never as an error);
  `go_live_finish(run_id)` → writes `pb_wfs_live_on` (first time) and `pb_wfs_live_to`, returns totals.
  A failed week leaves earlier weeks published and says exactly where it stopped, with **Carry on** to retry that week.
  Re-running is safe: already-published rows are skipped; the engine keeps hand-edited rows (facts B.3).
- Before the first call: an inline confirm panel (not a browser dialog) with the real numbers: "4 weeks · 652 people ·
  15,648 shifts. People see their shifts in My Payobook straight away. Published shifts cannot be un-published in one go."
- After: the finish card (prototype `.done-hero`): "Workforce is live." + totals + **Open the roster** (Mission roster lens)
  and a quiet **Publish more weeks**. Returning later, step 7 shows "Roster published up to <date>" and, within 7 days of
  that date, an amber "The roster runs out on <date>" with the publish control.

### 2.4 Statuses (final)
shifts / weeks / people as built; rules from P3; holidays: done when `pb_wfs_holidays_year` ≥ this year, else todo
"Check and confirm"; clocks: done when confirmed ("All connected" / "N to finish later"), warn when not confirmed and a
clock is waiting/attention, else todo; live: done "Roster published up to <date>", warn when it runs out within 7 days,
else todo "Last step".

## 3. Design bar (verbatim, binding)
"extreme WOW, intuitive, out-of-this-world experience, best in class." Hero moment: pressing Publish and watching the weeks
tick over to the green "Workforce is live." Zero dead-ends (every blocker has a Fix button that lands on the exact step),
plain language, motion with purpose (progress, the finish tick — respect reduced motion), keyboard ergonomics (calendar days
reachable by arrow keys, Enter toggles). Lucide via `ic()`, never emoji. One solid primary per bar. No "Odoo" in any
user-visible string. Screen words: "public holiday", "company day off", "rest day", "clock", "setup link", "publish",
"roster" — never leave, resource calendar, connector, token, invitation hash, draft rows, pattern, engine.

## 4. Numbered test cases
Python (`tests/test_golive.py`, tags `post_install, -at_install, wfsetup`):
1. `holidays()` shape for a company with and without a working calendar; only `env.company` rows; `working_days` arithmetic
   pinned for a fixed year and a Mon–Sat working week.
2. `add_day_off` as an attendance manager WITHOUT time-off rights → row exists, kind company, on the company calendar;
   officer → AccessError; other company's id → refused.
3. `remove_day_off` removes only that row; removing a row of another company refused.
4. `add_suggested(2027)` for a VN company → 10 dated rows, all-or-nothing (a duplicate makes the whole call refuse with a
   sentence), second call reports nothing to add; a company whose country has no list → `suggestions False`.
5. Adding a holiday on a day with a planned, uncalculated shift → `remark_days` flips it to holiday; removing flips it back;
   a hand-set shift never flips.
6. `confirm_holidays` sets the year; status text; officer refused.
7. `clocks()` states: ok / quiet (>24 h) / waiting / attention / off, with fixed "now"; error text never leaks raw `last_error`.
8. `clock_invite` returns a token, sets expiry, invalidates the earlier one (old hash no longer matches); officer refused;
   connector of another company refused.
9. `clock_add` creates a company-scoped connector in state "awaiting setup"; `no_number` count correct.
10. `live_check` blockers: each of the four blocking conditions alone → `can_publish False` with its sentence; non-blocking
    ones leave it True with the "for the N who are ready" label.
11. `live_check` writes nothing (row counts / max write_date on roster, pattern, company tables unchanged).
12. `go_live_start` + `go_live_week` × N + `go_live_finish` on 3 working weeks / 40 people / 4 weeks → every wanted day is
    published exactly once, all rows belong to `env.company`, company fields set, holiday/rest-day marks applied.
13. A second company with drafts in the same window is untouched (state still draft).
14. Re-run publishes nothing new; a hand-edited draft is kept and published as edited; a one-off shift from P2 is published
    and its day is not refilled.
15. Failure injection in week 2 (monkeypatch) → week 1 stays published, run reports where it stopped, retry completes.
16. Officer refused on every write; rules not confirmed → `go_live_start` refuses with the sentence.
17. Scale: 700 people × 4 weeks (≈16,800 rows) — report wall time per week call; no per-row queries in the publish loop.
18. All earlier wfsetup tests and the suites `/pb_timeoff`, `/pb_clock`, `/pb_shift_patterns`, `/pb_ess_workforce`,
    `/pb_attendance_policy`, `/pb_workforce_workspace` — baseline first, then after (known flaky baselines in facts J.1).

Browser walk:
B1 holidays year renders; click a day → company day off appears in the list and the toast offers Undo.
B2 "Add them all" for VN 2027 → 10 days; card disappears; the note about lunar dates is visible.
B3 remove a public holiday → inline question; arrow keys + Enter on the calendar.
B4 clocks: each state card; copy setup link (toast wording, link format in the clipboard); replace-link question.
B5 add a clock; "N people have no clock number" → step 3 filtered.
B6 go-live with a blocker → Fix button lands on the right step; come back, it is green.
B7 publish 4 weeks: confirm panel numbers match the plan; progress week by week; finish card; "Open the roster" shows them published.
B8 return to step 7 → "Roster published up to …"; Publish more weeks adds only the new ones.
B9 officer: all three steps read-only.
B10 all seven steps green → top progress "7 of 7"; widths 1440 / 1100 / 800 / 400; console clean. Screenshots beside the prototype.

## 5. Report back (`WFSETUP_P4_REPORT.md`, committed)
As P1 §5, plus: how the lunar dates were verified; which "no machine" options survived; measured publish timings; the exact
notification behaviour when mail is off. On a usage limit: WIP commit, "Where I stopped", end with PAUSED.
