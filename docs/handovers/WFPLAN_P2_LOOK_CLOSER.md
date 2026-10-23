# WFPLAN Phase 2 — "Look closer": the detail layer, the goal finder, stress, the brief

Read `docs/handovers/WFPLAN_LEDGER.md` FIRST and fully (rules, credentials, plumbing,
gotchas WF1–WF15, deploy ritual), then `docs/handovers/WFPLAN_P1_DECISION_ROOM.md` for
what Phase 1 built and why. Phase 1 is COMPLETE and live (`pb_decision_room` 19.0.1.0.0
on p9clone, payobook, abm, payobook_template). This phase extends it in place.

## 0. What you are building, in one paragraph

Phase 1 opened the room: the dark stage, the levers, goals, the year strip, the story and
the three-card ripple. Phase 2 makes the three cards OPEN — a detail workspace under the
ripple with four tabs (Work & shifts, Why profit changed, People & pay, Room to hire) —
and adds the parts of the approved concept that answer "so what should I do?": the goal
finder that offers three calculated paths you can try before you keep, the demand
reality-check (softer / as planned / stronger), the "one small experiment" nudge, a
printable decision brief, and the assumptions panel that a manager can edit. It also
fixes the one thing Phase 1 named as its weakest point: the revenue target box, which
must read and accept "2,200 B" like the goal boxes do. Everything stays read-only towards
payroll.

Reference for every screen in this phase: `design_poc/workforce_lab/public/option5.html`
(serve with `python3 -m http.server 8767` inside that folder; READ ONLY, never edit) and
the approved screenshot `docs/handovers/wfplan_shots/option5_approved.jpg`. Concept code
to port: `option5.js` (renderDetail/renderShifts/renderBridge/renderPeople/renderRoom/
drawDemand/findPaths/beginPreview/finishPreview/exportBrief/renderStress),
`decision-model.js` (candidates/headroom), `living-model.js` (marginal/stressOutcome/
bridge). Phase 1 already ported `bridge`, `marginal`, `headroom`, `candidates`,
`stressBand` into `pb_decision_room/static/src/js/decision_engine.js` (lines ~479–843) —
use them; adjust signatures only if a test below needs it.

## 1. Scope and binding non-goals

Deliverables:
1. `pb_decision_room` 19.0.2.0.0: engine additions (shifts), facade additions, cockpit
   additions (§4–§8), SCSS, templates, tests T21–T42, browser walks B11–B24.
2. Deployed and verified on p9clone (tests), payobook, abm, payobook_template.
3. Feature-scoped commits; ledger appended (WF16+); phase log updated; report (§10).

Non-goals (do NOT build):
- No home tile, no Vietnamese translations, no phone-specific redesign beyond keeping
  every new surface usable at 390 px (that is Phase 3).
- No PDF engine work: the brief is an HTML page with a print stylesheet; "Save as PDF" is
  the browser's print dialog. No `ir.actions.report`.
- No AI text, no accounting link, no writes to `hr.*`, no edits to
  `pb_hr_workforce_planning/`, no localStorage for anything but UI preferences.
- Do not retire or hide the "Classic planning tools" fold (owner decision, Phase 3).

## 2. Design (the bar, the hero of this phase, the copy)

**The bar (owner's words, verbatim): "extreme WOW, intuitive, out-of-this-world
experience, best in class."** Hero of this phase: **the goal finder** — the CEO ticks the
goals that matter, presses "Find paths to these goals", and three cards appear (Build
the team / Develop the team / Blend the two) each with a profit number, the moves it
makes and a "Try this direction" button; trying one repaints the entire room in preview
mode with an amber banner "Trying a possibility — Keep this direction / Back to my plan".
Second hero: the profit bridge — a waterfall from "today" to "your plan" whose steps sum
exactly. Zero dead-ends (every state in §9). Plain language: every step in the bridge
has a one-line reason; every tab has a one-sentence heading that says what question it
answers. Motion: tabs slide, the bridge bars grow from the running level, the preview
banner enters from the top, the stress buttons cross-fade the stage. Keyboard: tabs are
arrow-navigable (`role="tablist"`), Escape closes dialogs (WF4: capture-phase), `⌘Z`
undoes a kept path.

Copy: keep the concept's headings ("Enough people. In the right places.", "Every
difference has a reason.", "A whole team. A clear money story.", "How much room do we
have?", "And if demand surprises us?", "What would make this a great plan?") — they are
already plain. Replace "operators" with the selected team's name; replace every "$",
"240", "USD", "fictional" with real values or nothing. Icons via `ic()` only (add to
`pb_import_kit` `IC` if missing: `sun`, `sunset`, `moon`, `printer`, `flask`, `route`,
`gitBranch`, `sliders`; check first). No gradients; the existing `dr-*` tokens.

Layout: the detail workspace is a white card directly under the impact journey, full
story-column width, tabs across the top (`.dr-tabs`), one panel visible. Clicking an
impact card selects its tab and scrolls the workspace into view. The stress panel sits
under the workspace; the scenario dock stays last. The "one small experiment" card sits
at the bottom of the control room (above the model note). The goal finder lives inside
the existing goals dialog (Phase 1's `goalsOpen`), below the goal cards.

## 3. Engine additions (`decision_engine.js`)

### 3.1 Shifts
New assumptions fields (§4.1) give shift demand shares and premiums. New state keys
`evening` and `night` (% of revenue-earning heads on those shifts; day = rest), defaulted
from the assumptions' `shift_evening_pct` / `shift_night_pct`. `normalizeState` clamps
evening 0–50, night 0–40, evening+night ≤ 80.

In `compute()`, for each month when a target exists: split revenue-earning capacity
hours across the three shifts by share; split demand by the assumptions' demand shares
(`demand_day_pct` etc.); `served[s] = min(available[s], demand[s])`; revenue =
Σ served × revenue-per-hour (the same calibration Phase 1 uses for coverage — capacity
today serves the target fully at the assumed shares; document the formula in a comment);
`row.shifts = [{key:'day'|'evening'|'night', heads, available, demand, served}]`.
Premium cost: evening heads × pay × `evening_uplift_pct`, night heads × pay ×
`night_uplift_pct` (night already exists in Phase 1 — do not double count: move the
Phase 1 night premium onto the shift split). Without a target: shifts still split heads
and cost premiums, but demand/served are null and the tab says so.

`balanceShifts(baseline, assumptions, state)` → the evening/night shares that match
demand shares (the "Match shifts to demand" button).

### 3.2 Helpers the UI needs (pure, tested)
- `bridge(plan, ref)` — already exists; add `steps[].reason` (one plain sentence each)
  and keep `check === true`.
- `payStory(plan, state, assumptions)` → `{gross, withholding, takehome, contributions,
  recruit, severance, premiums, overtime, total}` for the People & pay tab.
- `teamsInDecember(plan, ref)` → `[{key, name, heads, refHeads, payMonth}]`.
- `headroom(...)` → `{points:[{add, profit, met, failed}], intervals:[[lo,hi]], enabled}`
  for a team (and optional role); cap the scan at +50 % of the team or 200 people,
  whichever is smaller; must finish < 150 ms on company 5 (memoise `compute` inputs;
  if slower, step by 2 or 5 people and say so in the tab's footnote).
- `candidates(...)` → three lanes `{lane:'hire'|'develop'|'balanced', state, result,
  met, failed, checks, change}` over a bounded grid: people in the largest revenue team
  {0, +2 %, +5 %, +10 %, +15 %} of its heads (rounded), overtime {0, 8, 16, current},
  productivity {0, 5, 10, current}, raise {current}, plus the current state; rank by
  fewest failed goals, then normalised shortfall, then lower cost, then fewer changes.
  Must return in < 400 ms on company 5 (it is ≤ 5×4×4 = 80 computes; if a compute is
  > 5 ms, profile and fix before adding the UI).
- `stressOutcome(...)` → the sentence for the stress panel (uses `stressBand`).
- `briefModel(...)` → the plain data the brief renders (goals table, one sentence,
  annual outcome table, bridge, decisions that differ, full inputs, month by month,
  assumptions sentences).

## 4. Server additions

### 4.1 `pb.decision.assumptions` new fields
`shift_evening_pct` (Float, default 25), `shift_night_pct` (15), `evening_uplift_pct`
(Float, default 0 — help: "Extra pay for evening shifts, on top of base pay"),
`demand_day_pct` (60), `demand_evening_pct` (25), `demand_night_pct` (15; the three must
sum to 100 — `@api.constrains` with a plain sentence), `productivity_cost_per_point`
(Monetary per person per month, default 0 — replaces Phase 1's hard-coded `learning = 0`;
0 keeps the P1 behaviour). Add `mail.thread` with `tracking=True` on every number so the
chatter on the record shows who changed what (the room's dialog links to it for managers).
Migration: `migrations/19.0.2.0.0/post-migrate.py` is NOT needed (defaults fill on
upgrade) — but assert in T21 that an upgraded record reads the defaults.

### 4.2 Facade `pb.decision.room`
- `get_room` returns the new assumption fields and `assumptions_form` = the list of
  editable fields with `{key, label, help, kind: 'money'|'pct'|'months'|'int'|'teams'|
  'ladder', step, min, max}` so the dialog is generated, not hand-written twice.
- `save_assumptions(vals)` (manager only; exists) now accepts every field above, validates
  ranges server-side with plain sentences, and returns the fresh assumptions dict + a new
  roster signature so the client recomputes. Writing clears the baseline cache for that
  company (WF11 dict).
- `render_brief(payload)` → HTML string: server-side QWeb template
  `pb_decision_room.brief` rendered with `briefModel` data the CLIENT computed (the
  server does not recompute; it lays out and stamps company name, user, date, currency).
  The page is self-contained (inline CSS, print stylesheet, `@page` margins, no
  external assets), opens in a new tab via a `data:`-free route: add a controller
  `/decision-room/brief/<token>` that serves an HTML kept in `ir.attachment`? — NO, keep
  it simpler: the facade returns the HTML, the client opens `window.open()` and writes
  the document (`document.write` of a same-origin blank window is fine here). The brief
  ends with "Explore freely. Nothing in payroll, hiring or contracts is changed by this
  document." and names the plan, the comparison, and every assumption.

## 5. Cockpit: the detail workspace (`decision_room.js` + xml + scss)

Tabs (`state.detail`, default `coverage` when a target exists, else `people`):
1. **Work & shifts** — heading "Enough people. In the right places." + "Find the gap
   before adding more cost." Button "Match shifts to demand" (applies `balanceShifts`
   with a toast naming the new shares). Demand picture: canvas (`decision_charts.js`
   `drawDemand`) with three lines — Work arriving (rose, dashed), Potential capacity
   (teal, dashed), Work delivered (primary) — in hours, month markers, selected-month
   rule; legend; footnote. Three shift tiles (Day / Evening / Night with `sun` /
   `sunset` / `moon`): heads on that shift, time band + premium text, a capacity track
   (served %, comparison marker, "N h served"), status line ("Demand fully covered" /
   "N hours of demand unserved" / "spare capacity here"). Two levers under them: Evening
   share, Night share (same lever component as Phase 1, with comparison tick). Without
   a target: the picture and tiles show heads and premiums only, and one line says "Type
   a revenue target to see demand against capacity."
2. **Why profit changed** — heading "Every difference has a reason." Waterfall canvas
   (`drawBridge`): start bar = comparison, one bar per step (green up / rose down),
   end bar = your plan, dotted connectors, value labels above bars, two-line category
   labels, y-axis in compact money; legend list below with each step's value and reason.
   Footnote: "This bridge reconciles the difference. It does not claim each input acts
   alone."
3. **People & pay** — heading "A whole team. A clear money story." Left: "Who is on the
   team in December" — one row per team (plan bar solid, comparison bar faint, heads,
   delta, monthly pay). Right: "Where a year of pay goes" — money strip (take-home vs
   deductions), rows for gross, deductions, take-home, then the employer box
   (contributions, overtime & premiums, recruiting & severance, total workforce cost).
   Footnote: "Deductions are shown once, inside gross pay. They never add to business
   cost."
4. **Room to hire** — heading "How much room do we have?" + "Explore additional hires
   while holding every other input fixed." Team select (+ role select, default typical
   mix). Result card: "12–18 additional people in Production" or "No additional hiring
   meets every goal." or "Choose a goal to see your room to hire." Canvas
   (`drawRoom`): profit vs +N people, teal segments where every goal is met, rose dots
   where not, x labels "+0 / +N/2 / +N people". "Try N more" buttons (up to four, from
   the interval edges) → preview. Footnote names what stays fixed and the step size.

Impact cards: clicking selects the tab (`data-focus`), highlights the card
(`.selected`), scrolls the workspace into view (respect motion off). Remove the Phase 1
"Detail views arrive in the next release" tooltip.

## 6. Cockpit: goal finder, preview, stress, experiment, assumptions, target box

- **Goal finder** (inside the goals dialog): note "Your current demand, pay, shifts and
  hiring month stay in place."; button "Find paths to these goals" (disabled with a
  toast when no goal is on; validates every on-goal box in range). While searching: the
  button reads "Exploring the possibilities…" (≥ 40 ms yield so the label paints).
  Result: "Checked N combinations." + three `path-option` cards (eyebrow HIRING & HOURS
  / SKILLS & HOURS / MOST FLEXIBLE; title; status "Meets every selected goal" or "N
  goals still missed"; profit; delta vs your plan; spec rows: people to add (team),
  productivity, overtime, workforce cost, margin, demand served; one sentence; "Try this
  direction"). If every lane equals the current plan: one card "Your plan already meets
  these goals. Room to think bigger." with a "Raise a goal" hint. Method fold: "What the
  search changes — and what it protects" in plain words.
- **Preview** (`state.preview`): trying a path or a "Try N more" closes the dialog,
  snapshots `{state, goals, sceneName, historyLength}`, applies the candidate state with
  sceneName "<lane> · preview", repaints, scrolls to the compass, and shows the amber
  banner: eyebrow TRYING A POSSIBILITY, title, copy "+₫X annual profit vs your previous
  plan. M/N goals met. Your previous plan is kept until you choose.", buttons "Back to
  my plan" and "Keep this direction". Save/Export are disabled during preview (tooltip
  says why). Opening a saved plan during preview is refused with a toast. Keep → history
  gets the pre-preview state (so `⌘Z` returns); Back → everything restored.
- **Stress panel** (under the workspace): eyebrow "GIVE THE PLAN A REALITY CHECK", h2
  "And if demand surprises us?", three buttons −10 % Softer demand / As planned Your
  forecast / +10 % Stronger demand (`state.stress`, recorded in history); outcome
  sentence from `stressOutcome`. The stage band legend reads "Demand stress range".
  Hidden without a target (one line: "Type a revenue target to stress-test the plan.").
- **One small experiment** (control room, above the model note): eyebrow, title
  "Five more people in <largest revenue team> would add ₫X of profit." / "…would cost
  ₫X of profit.", copy (coverage + cost), button "Preview 5 more people" → preview.
  Team follows the control room's selected team.
- **Assumptions dialog** (existing, now editable for managers): generated from
  `assumptions_form`; grouped "Revenue & demand", "Pay & contributions", "Hiring &
  leaving", "Shifts & hours", "Other costs"; each field shows its plain help; money
  fields use the compact money input (below); "Teams that earn revenue" as toggle chips
  over the baseline teams; Save → `save_assumptions` → recompute → toast "Assumptions
  saved for <company>. Every plan now uses them." Non-managers see values, no inputs,
  and "Changed by <name> on <date>" from the chatter + "Ask <manager group name> to
  change these." Link "Open the change history" (managers) opens the record form.
- **Compact money input** (`decision_format.js` `parseCompact` + a small OWL component
  `DrMoneyInput`): displays `₫2,200B`, accepts "2200000000000", "2,200 B", "2.2 t",
  "2200b", "1.5m"; suffixes k/m/b/t (case-insensitive) and the currency symbol
  ignored; commits on blur/Enter; arrow keys step by the visible unit; invalid text
  keeps the old value and shakes once. Use it for the revenue target (control room),
  every money goal, and money assumptions. Retire the "type in billions" boxes.
- **Export the decision brief** (dock footer): computes `briefModel`, calls
  `render_brief`, opens the new tab, toast "Decision brief opened in a new tab — use
  Print to save it as PDF." Disabled during preview.

## 7. Tests (numbered; all must pass on p9clone)

Server (`tests/test_decision_room.py`, `post_install`):
- T21 upgraded assumptions carry the new defaults (25/15/0; 60/25/15; 0) and the demand
  shares constraint refuses 60/25/20 with a plain sentence.
- T22 `save_assumptions` is manager-only; a plan-tier user gets an AccessError whose
  message names who can change them; a manager's write appears in the chatter with the
  old and new value; the baseline cache is cleared (a subsequent `get_room` reflects a
  changed `revenue_team_ids`).
- T23 `get_room().assumptions_form` lists every editable field exactly once with a
  label, help and kind; no key is missing from the model and none is extra.
- T24 `render_brief` returns self-contained HTML (no `<script src`, no `<link`, no
  external URL), contains the company name, the plan name, "Nothing in payroll", every
  goal row and every assumption sentence passed in, and never the word "Odoo".
- T25 `render_brief` escapes user text (a plan named `<b>x</b>` is shown literally).
- T26 T9 still holds over the whole module incl. the brief template and `.pot`.
- T27 the `pb_people_hub` suite still passes.

Engine (`node tools/decision_engine_check.mjs`, extend):
- T28 shift split conserves heads: day+evening+night == revenue heads every month; with
  the default shares nothing changes vs Phase 1 totals except the evening premium at 0.
- T29 `balanceShifts` returns shares equal to the demand shares (rounded) and served
  hours ≥ before in every shift.
- T30 bridge with shifts still sums exactly; every step has a non-empty reason.
- T31 `payStory` identities: gross − withholding == takehome; total == people cost.
- T32 `headroom` on a 400-person team finishes < 150 ms and its intervals are exactly
  the runs of `met` points.
- T33 `candidates` returns three lanes, ranked as specified, in < 400 ms on the
  company-5 baseline (use the fixture exported by T8's timing run — write the baseline
  JSON into `tools/fixtures/company5_baseline.json` from the facade on p9clone, without
  person names).
- T34 with unreachable goals every lane reports `met === false` and lists `failed`.
- T35 `parseCompact("2,200 B") === 2.2e12`, `"1.5m"` → 1.5e6, `"₫950k"` → 950000,
  `"abc"` → null; round-trip with `format.compact`.
- T36 `briefModel` contains the twelve month rows and the decisions that differ.

Browser (Chrome MCP, payobook + abm, 1440 and 390, light and dark; screenshots into
`docs/handovers/wfplan_p2_shots/`):
- B11 Click "The work you can deliver" card → Work & shifts tab opens and scrolls into
  view; three tiles show heads; "Match shifts to demand" changes the shares and toasts.
- B12 Evening share lever → tiles, demand picture and stage all move; comparison tick
  visible.
- B13 Why profit changed → waterfall bars sum to the delta pill's number; legend reasons
  readable; two-line labels do not overlap at 1440 or 390.
- B14 People & pay → team rows match the stage's December headcount; money strip
  percentages add to 100.
- B15 Room to hire → pick a team → interval sentence + chart; "Try N more" → preview
  banner; Keep → dock "on canvas" row updates; ⌘Z returns.
- B16 Goals dialog → Find paths → three cards in < 1 s; Try "Blend the two" → preview;
  Back to my plan → previous numbers return exactly.
- B17 With goals nobody can meet (margin ≥ 95 %) → cards say what is missed; nothing
  crashes.
- B18 Stress −10 % / +10 % → stage, tiles, story and sentence change; band legend text.
- B19 One small experiment → Preview 5 more → banner; Keep.
- B20 Assumptions as manager: change employer rate to 24 → Save → stage cost moves;
  chatter shows the change; as plan-tier user: read-only view with the "ask" sentence.
- B21 Revenue target box: type "2,200 B" → shows ₫2,200B and profit recomputes; type
  "abc" → shake, value kept; arrow up steps by 1 B.
- B22 Export brief → new tab, self-contained, print preview has no cut-off tables; the
  brief names plan, comparison, goals, bridge, months, assumptions.
- B23 390 px: tabs scroll horizontally without page overflow; tiles stack; bridge
  scrolls inside its own container (WF6 rule); preview banner wraps.
- B24 Dark mode: workspace, banner, dialog cards readable.

## 8. Build order

1. Assumptions fields + facade form/brief + T21–T27 on p9clone.
2. Engine: shifts, helpers, fixture, node checks T28–T36.
3. Money input + target box (small, visible win) → then workspace tabs 2, 3, 1, 4.
4. Goal finder + preview + stress + experiment.
5. Assumptions dialog (editable) + brief.
6. Chrome walks, deploy ritual (bump to 19.0.2.0.0; `-u pb_decision_room` on each DB;
   backup first), version/hash verification, commits, ledger, report.

## 9. States to design (zero dead-ends)
No target (tabs 1, 4 and stress degrade with one sentence each) · goals all off (room
tab and finder explain) · unreachable goals · preview active (save/export/open disabled
with reasons) · headroom scan hits the cap (footnote says the range scanned) ·
`render_brief` failure (toast with reason + retry) · pop-up blocked (toast: "Your browser
blocked the new tab. Allow pop-ups for Payobook and try again.") · manager vs user on
assumptions · a team with 0 revenue heads selected in Room to hire ("This team does not
earn revenue in this model; adding people here changes cost only.") · demand shares that
do not sum to 100 (inline sentence, Save disabled).

## 10. Report back (plain-English first, then engineering)
1. Three sentences a CEO understands: what the three cards open, what "find a path"
   does, what a printed brief contains.
2. Results table T21–T36, B11–B24 with evidence paths. Timings: `candidates` and
   `headroom` on company 5.
3. Deploy evidence per DB (version, hash), backups taken.
4. Deviations and why; new gotchas WF16+ appended; ledger phase log updated.
5. Self-score against the bar and the one thing to improve first.
6. Commit list.
