# WFPLAN Phase 1 — "The room opens": `pb_decision_room` under People → Plan

Read `docs/handovers/WFPLAN_LEDGER.md` FIRST and fully (rules, credentials, plumbing
facts, gotchas, deploy ritual). This document is the phase; the ledger is the law.

## 0. What you are building, in one paragraph

The approved concept is Codex's "Option 05 · The Decision Room"
(`design_poc/workforce_lab/public/option5.html` — open it in a browser: `cd
design_poc/workforce_lab/public && python3 -m http.server 8767`, then
http://localhost:8767/option5.html; approved screenshot
`docs/handovers/wfplan_shots/option5_approved.jpg`). Phase 1 ships the room itself
inside Payobook: a new module `pb_decision_room` whose canvas becomes what the People
app's **Plan** lens lands on; the seven legacy planning cards move into a fold under
"Classic planning tools". The room is grounded on the company's real roster and pay
(teams, roles, headcount, monthly pay, currency), Vietnam 2026 statutory rules and an
editable assumptions record; the CEO types a yearly revenue target and moves a few
levers; the dark stage, the goals compass, the year lens, the story caption, the
three-card ripple and the saved-plans dock all respond live. Saved plans are stored on
the server for the whole company, not in the browser. Nothing changes payroll.

Phase 2 (not now) adds the detail workspace (work & shifts, why-profit-changed bridge,
people & pay, room to hire), the goal finder with three paths + preview, the stress
panel, export brief, and assumptions editing. Build Phase 1 so those bolt on: the engine
must already compute what they need (see §4), but do not build their UI.

## 1. Scope (deliverables) and binding non-goals

Deliverables:
1. Module `pb_decision_room` (version `19.0.1.0.0`): security groups, two models, one
   facade, one client-action record, OWL cockpit, SCSS, XML templates, tests, i18n stub.
2. `pb_people_hub` change (bump to next patch version): the Plan lens hero slot + the
   "Classic planning tools" fold; sidebar `match_action_tags` gains `pb_decision_room`;
   palette entry for the lens stays as is.
3. `pb_import_kit` change (bump): any new Lucide icons the room needs, added to `IC`.
4. Deployed and verified on `p9clone` (tests green), `payobook`, `abm`,
   `payobook_template`. Chrome-validated on payobook (company 5) and abm.
5. Feature-scoped commits (see ledger rule 5). Ledger updated. Phase report (§9).

Binding non-goals (do NOT build in P1):
- No detail workspace tabs, no goal-finder search, no preview banner, no stress panel
  buttons, no "one small experiment" card, no export, no assumptions editing UI (the
  dialog is read-only), no shift levers (evening/night), no room-to-hire chart.
- No writes to any `hr.*` model, ever. No accounting link. No AI text.
- No edits inside `pb_hr_workforce_planning/`. No new `pb.sidebar.item` (the room lives
  under the existing People rail item).
- No localStorage for plans (UI preferences only: metric, motion, month, fold state).

## 2. Design (the bar, the hero, the copy)

**The bar (owner's words, verbatim): "extreme WOW, intuitive, out-of-this-world
experience, best in class."** Hero moment: the dark indigo stage — one huge animated
profit number, the year drawn as a glowing line over a faint baseline and a ±10 % band,
a month scrubber that plays through the year — and every lever on the left makes it
breathe within one frame. Zero dead-ends: every state below is designed. Plain language
everywhere. Motion with purpose (number tween 350 ms, the ripple travelling across the
three cards, the stage line easing to its new shape). Keyboard: sliders take arrow keys,
number boxes take typing, `Esc` closes dialogs, `⌘Z` undoes.

Layout (clone the concept, adjusted for the hub): the lens canvas is full-bleed inside
the hub (rail 76 px on the left). Inside it: a slim page heading (eyebrow "DECISION
ROOM", h1 "See the year before you commit to it.", sub "Set your goals. Shape your team.
Watch the business respond.", actions Undo / Reset / Save plan), then the two-column
`plan-layout` (control room 282 px sticky left; story column right). Below 1100 px the
control room stacks on top; at 390 px everything is one column and the stage keeps its
big number readable (≥ 40 px).

Copy rules: the concept's sentences are good — keep their tone, drop "Fictional company ·
USD", every "$" and every "240". Replace unicode glyphs with `ic()` icons: ✧ →
`sparkles`, ↗ → `external` (or add `arrowUpRight`), ↶ → `undo`, ◈ → `info`, ▶ → `play`,
❙❙ → add `pause`, ✓ → `check`, ! → `alert`. Add to `pb_import_kit` `IC`: `target`,
`pause`, `arrowUpRight`, `moon`, `sun` (only if missing; check the file first).

Colour: ledger rule 6. The stage is flat `#241F52` (no gradient) with the concept's
dot-texture overlay at 8 % white; plan line `#D7C6FF`, baseline dashed `#8D84AC`, band
fill `rgba(199,184,237,.08)`, goal pace dotted `#F7A6C3`, month marker `#E7DDFF`.
Light cards on `#F4F5FB`. Good = `#2E7D4F`, bad = `#DC2668`, watch = `#D97706`.

Currency: read `res.company.currency_id` (`symbol`, `position`, `decimal_places`). Money
formatter: VND-style (0 decimals) → `₫1.25B` / `₫840M` / `₫12.5M` / `₫950k`; decimal
currencies → `$1.25m` / `$840k` / `$1,250`. Negative → leading `−`. Signed deltas
`+₫1.4B`, `−0.8 pp`, `+24 people`. Never show more than three significant digits on a
tile; full figures live in tooltips.

States (each designed, each with a next step):
- **Not allowed** (no decision group): the lens hero is absent; the classic fold still
  shows for wfp users; a user with neither sees the launcher's existing empty state.
- **Loading**: skeleton of the stage (grey line placeholder, three tiles) for ≤ 1 s;
  the facade must answer in < 800 ms on company 5 (4.5k staff) — cache the baseline
  per company for 10 minutes (`tools.ormcache` keyed on company id + roster signature =
  count of open contracts + max write_date) and expose `refresh` to bypass it.
- **No roster** (0 employees / 0 contracts in the company): the room still opens with an
  empty baseline and a card in the story column: "This company has no people on record
  yet. Add employees and contracts, or type a team below to sketch a plan." with a
  "Sketch a team" composer (name, people, monthly pay) that adds a virtual team to the
  baseline for this browser session only.
- **No revenue target yet**: first visit shows the target field in the control room with
  an amber ring and the stage metric locked to "People cost" until a target is typed;
  a one-line nudge "Type this year's revenue target and profit appears." Persist the
  target into the assumptions record on blur (managers) or into the plan state (users).
- **Facade error**: story column shows "The room could not load the roster. <reason>.
  Try again." with a Retry button; console.warn the error (never swallow).
- **Huge roster**: > 30 teams → teams beyond the 12 largest roll into "Other teams";
  role picker lists roles of the selected team only.
- **Save conflicts**: a plan name already used → "A plan called X exists. Replace it?"
  with Replace / Rename. 20 plans per company max → "20 plans saved. Remove one first."
- **Read-only user** (decision user, not manager): can save/delete own plans; cannot
  delete others' (button absent, not disabled); assumptions dialog says who can change
  them.
- **Dark theme**: the hub renders light; the stage is dark by design. Verify the light
  cards do not invert under the platform's dark mode (`biz_theme` tokens) — if they do,
  scope `.pbim.dr` colours explicitly.

## 3. Module layout (exact)

```
pb_decision_room/
  __manifest__.py            depends: base, hr, mail, pb_hub, pb_import_kit, pb_people_hub
  __init__.py                (om_hr_payroll NOT a dependency: read hr.contract / hr.payslip
  hooks.py                    only when present in self.env)
  security/pb_decision_room_security.xml   groups + company rule
  security/ir.model.access.csv
  models/__init__.py
  models/pb_decision_assumptions.py        pb.decision.assumptions (one per company)
  models/pb_decision_plan.py               pb.decision.plan (saved plans)
  models/pb_decision_room.py               pb.decision.room AbstractModel facade
  views/pb_decision_room_action.xml        ir.actions.client record, tag pb_decision_room
  views/pb_decision_plan_views.xml         admin-only list/form (OFF-MENU fallback)
  views/pb_decision_assumptions_views.xml  admin-only form (OFF-MENU fallback)
  static/src/scss/decision_room.scss
  static/src/js/decision_engine.js         pure functions, no OWL, unit-testable
  static/src/js/decision_format.js         money/pct/signed/esc, currency-aware
  static/src/js/decision_charts.js         canvas horizon + ring + mini bars
  static/src/js/decision_room.js           the OWL cockpit (registry "actions")
  static/src/js/decision_palette.js        Plan hero slot + ⌘K rows (loaded after room)
  static/src/xml/decision_room.xml
  tests/__init__.py, tests/test_decision_room.py, tests/test_static_contract.py
  i18n/pb_decision_room.pot
```

Manifest assets (`web.assets_backend`, this order): scss, decision_format.js,
decision_engine.js, decision_charts.js, decision_room.js, decision_palette.js, xml.

## 4. Server design

### 4.1 Groups (security xml)
- `group_decision_user` "Decision Room: plan" — opens the room, saves and deletes OWN
  plans. `implied_ids`: none. Given automatically to `hr.group_hr_manager` and to
  `pb_hr_workforce_planning.group_wfp_user` via their `implied_ids` (add an
  `<record id="hr.group_hr_manager" model="res.groups">` with
  `implied_ids` 4-link in this module's data — check that the wfp group xmlid resolves;
  if `pb_hr_workforce_planning` is not installed on a DB, guard with a `post_init_hook`
  that links when the group exists, instead of a data record that would fail).
- `group_decision_manager` "Decision Room: assumptions" — everything above plus edit
  assumptions and delete anyone's plan. Implied by `base.group_system`.
- Company rule on `pb.decision.plan` and `pb.decision.assumptions`:
  `['|', ('company_id','=',False), ('company_id','in', company_ids)]`.

### 4.2 `pb.decision.assumptions` (one per company; `company_id` unique via
`models.Constraint`)
Fields (all with plain-English `string`/`help`; VN 2026 defaults from core.js):
`company_id` (required), `revenue_target` (Monetary, yearly; 0 = not set),
`demand_growth_pct` (Float, default 0), `employer_rate_pct` (23.5), `employee_rate_pct`
(10.5), `contribution_cap` (Monetary, 46,800,000 for VND companies else 0 = no cap),
`allowance_pct` (12, non-taxable allowances share), `ot_multiplier` (1.5), `night_uplift_pct`
(30), `work_days` (22), `recruit_cost_months` (1.0), `severance_months` (1.5),
`ramp_first_month_pct` (50), `attrition_pct_year` (Float, default 12; used only when the
user switches attrition on), `bonus_month_index` (Integer 1 = January; 0 = none),
`bonus_months` (Float 1.0 = one month's pay), `other_fixed_monthly` (Monetary, default 0),
`other_pct_revenue` (Float, default 25), `revenue_team_ids` (Many2many hr.department:
teams whose people produce revenue; default = every top-level department whose name does
not match `finance|account|hr|human|admin|legal|it\b|support` case-insensitive),
`pit_ladder` (Json, default the VN ladder from core.js `pitOn`), `note` (Text).
`get_for_company(company)` creates the record on first read (sudo create is acceptable
here — it is a settings row — but READ must not be sudo).

### 4.3 `pb.decision.plan`
`name` (Char, required), `company_id` (required, default current), `user_id` (creator),
`state` (Json — the lever state, exactly the engine's state object), `goals` (Json),
`summary` (Json — `{profit, cost, revenue, coverage, heads, margin}` computed by the
client at save time and stored for the dock table without recomputing server-side),
`is_reference` (Boolean — the plan the company compares against by default; at most one
per company, enforced in `write/create`), `note` (Text), `active`.
`_name_uniq = models.Constraint('unique(company_id, name)', "A plan with this name already exists.")`.
Display name = name. Chatter (`mail.thread`) so a saved plan can be discussed.

### 4.4 Facade `pb.decision.room` (AbstractModel, `@api.model` only)
- `_can_read()` = user in `group_decision_user` or manager or admin; `_can_manage()`.
- `get_room(company_id=None, refresh=False)` → dict:
  ```
  { allowed, can_manage, company: {id, name, currency: {symbol, position, decimals, code}},
    assumptions: {…every field above, plus id},
    baseline: { asof: 'YYYY-MM-DD', headcount, teams: [ {key, name, department_id,
                revenue: bool, heads, pay_month_avg, roles: [ {key, name, job_id, heads,
                pay_month_avg, level: 1..4} ] } ] },
    plans: [ {id, name, user, user_id, mine, is_reference, summary, goals, state, written} ],
    limits: {max_plans: 20} }
  ```
  Baseline builder (one pass, `read_group`/SQL, company-scoped, no sudo):
  1. Roster source: open `hr.contract`s (`state='open'`, company) → employee, wage,
     job, department. **Verify on p9clone first** which of these live on hr.contract
     vs hr.version on this build (ledger §data). If `job_id`/`department_id` are on
     `hr.version`, join through `employee.version_id`/`current_version_id`. Employees
     with no open contract are added with heads=1 and pay = their team's average.
  2. Team = top-level department (walk `parent_id` to the root); no department →
     "Unassigned". Role = job; no job → "Other roles". `level` = 4 if the job name
     matches `chief|director|head|vp`, 3 for `manager|lead|senior`, 2 for
     `specialist|engineer|analyst|officer|executive`, else 1 (used by the engine for
     "a senior hire eats budget faster" and by the role picker order).
  3. `pay_month_avg` = average `wage` of open contracts in that role (0 → fall back to
     the latest `hr.payslip` basic per employee if `'hr.payslip' in self.env`; still 0 →
     team average; still 0 → company average; log a debug line per fallback).
  4. Sort teams by heads desc; beyond 12 teams roll into "Other teams" (roles merged).
  5. Cache 10 min per (company, signature) with `tools.ormcache`; `refresh=True` clears.
- `save_plan(vals)` → id (create or replace when `replace=True`); `delete_plan(id)`
  (own or manager); `set_reference(id)`; `save_assumptions(vals)` (manager only —
  Phase 1 only uses it for `revenue_target` and `demand_growth_pct` from the control room).
- Every independent number in its own `_safe()`; never raise for a metric.

## 5. Engine (`decision_engine.js`) — port, then extend

Port `design_poc/wfplan/src/core.js` `compute()` to accept the server baseline
(`teams[].roles[]` instead of the hard-coded DIVS) and the assumptions record, in the
company currency (no ₫M scaling inside the engine; scale only in the formatter). Keep its
month loop semantics: contributions with cap, allowance share, OT multiplier, night
uplift, bonus month, recruit cost in the arrival month, severance for let-gos, ramp
(first month 50 %), attrition + backfill, seasonality (keep core.js's curve; it is an
assumption listed in the dialog), demand mode ON whenever `revenue_target > 0`.

State object (the ONLY thing a plan stores; keep it flat and JSON-safe):
```
{ target: <yearly revenue or 0>, growth: %, stress: %, raise: %, raiseMonth: 1..12,
  ot: hours/person/month, otFrom: 1..12, attritionOn: bool, backfill: bool,
  bonusMonths: float, productivity: %, absence: %, start: 1..12,
  moves: [ {team: key, role: key|null, n: ±int, month: 1..12} ]  // hires (+) / let-gos (−)
}
```
Defaults: `raise 0, ot = today's average from assumptions (0 if unknown), attritionOn
false, backfill true, productivity 0, absence 8, start = next month, moves []`.

Outputs (`compute(baseline, assumptions, state)` → `{rows[12], year, teams}`): per month
`{name, index, heads, headsByTeam, salary, overtime, premium, bonus, contributions,
recruit, severance, learning, people (=all employer cost), gross, withholding, takehome,
demand, capacity, revenue, coverage, other, profit, margin}`; year sums, `year.coverage`,
`year.unserved`, `year.headcount` (December). Coverage model from core.js demand mode:
`capacity = target_month × (revenueHeads[m]/revenueHeadsBase) × hoursFactor`,
`revenue = min(demand, capacity)`, demand = target spread by seasonality × (1 + growth ×
(m+1)/12) × (1 + stress). Level-aware: a move at level L costs that role's pay; the
"room" helpers (P2) will use it.

Also port (from decision-model.js / living-model.js), adapted to this state shape:
`GOALS` definitions (margin ≥, profit ≥, cost ≤, coverage ≥, heads ≤, overtime ≤) with
currency-aware format; `normalizeGoals`, `evaluate`, `grade`, `series(plan, metric)`
(cumulative for money, monthly for coverage), `stressBand`, `bridge` (steps: revenue,
base salaries, overtime & premiums, bonus, contributions, recruiting & severance,
other costs — must sum exactly to the profit difference; keep the `check`), `changes`,
`describeChange`, `story`. `candidates`/`headroom`/`marginal` may be ported now (pure
functions) but get no UI in P1.

Warnings (from core.js `warnings()`), shown as the story caption's second line when
present: January loss (bonus vs hires), capacity idle, unserved demand, cash low month.

## 6. Cockpit (`decision_room.js` + xml) — what is on screen in P1

Follow `option5.html` section by section; P1 keeps these and drops the rest:
1. **Page heading** + actions: Undo (disabled when nothing to undo; `⌘Z`), Reset to
   baseline, Save plan (opens the name dialog; Replace/Rename flow).
2. **Control room** (sticky): goal invite card ("Find a way to my goals" opens the Set
   goals dialog in P1 — the path finder arrives in P2, say so inside the dialog with one
   quiet line); presets (Grow thoughtfully / Invest in people / Ease overtime — recomputed
   from the real baseline: e.g. "+5 % people in the biggest revenue team from next month";
   "5 % raise from month 1"; "overtime to 0 + productivity 8 %"); **Revenue target**
   money input with growth-by-December slider (the owner's ruling — this is the first
   control); **team picker** (select of teams, "· N today") → lever "Add/remove people"
   (range −20 %…+50 % of the team's heads, integer people; number box beside it) with an
   optional **role** select (default "Typical mix" = pro-rata across the team's roles);
   "New hires arrive in" month select; levers Overtime per person, Salary increase (with
   from-month); folds: "Pay, development & available time" (productivity, absence,
   bonus months, leavers switch + backfill switch), "Contributions & deductions"
   (read-only lines from assumptions + "Who can change these"). Each lever shows the
   comparison tick and "Was X".
3. **Goal compass**: pills for the goals that are on (met/missed, progress track); "Set
   goals" dialog with the six goal cards (on/off + target); default goals: margin ≥ 20 %,
   profit ≥ baseline profit, cost ≤ baseline cost × 1.1, coverage ≥ 97 % (only when a
   target exists).
4. **Outcome stage** (dark): scene name + status dot; Motion on/off; "Show only the
   difference"; metric tabs Profit / People cost / Coverage (coverage tab hidden without a
   target); hero number (tween) + delta pill vs comparison + before/after sentence;
   horizon canvas (band, baseline dashed, dotted goal pace, plan line, month markers,
   month callout, diff-mode bars); legend; timeline (play/pause, range 0..11, month
   stamp); three tiles (People on payroll · month, Workforce cost · month, Demand
   served · month or Take-home · month without a target).
5. **Year lens**: 12 month cards (profit, watch dot when coverage < goal or a warning),
   click selects the month; note line ("March is the lowest-profit month…").
6. **Story caption**: `story()` title + copy; warnings line beneath.
7. **Impact journey**: three cards (Your people: dot grid, 1 dot ≈ N people scaled so
   the grid holds ≤ 200 dots; The work you can deliver: ring; The financial result: paired
   monthly bars) with the ripple animation on change. Clicking a card does nothing in P1
   except a gentle highlight (no detail workspace yet) — tooltip "Detail views arrive in
   the next release".
8. **Scenario dock**: "Compare against" select (Original baseline / reference plan /
   saved plans); "Use this plan as comparison"; table (Plan · People Dec · Workforce cost
   · Demand served · Operating profit · vs comparison · Open / Compare / Remove); footer
   "Saved for everyone at <company> · up to 20 plans · nothing here changes payroll".
9. **Assumptions dialog** (read-only): the assumption sentences, generated from the
   record (e.g. "Employer contributions 23.5 % of pay, capped at ₫46.8M"), plus "Roster
   as of <date>: N people in T teams", and who can change them.
10. **Toast** for saves, comparisons, resets.
11. **"Explore freely. Nothing here changes payroll."** model note, always visible.

Undo: a 40-deep history of `{state, goals, sceneName}`; Redo optional. Reset = state to
defaults, goals kept.

### 6.1 Plan lens hero slot (`pb_people_hub` edit — minimal, test-safe)
- `plan_launcher.js`: add `export const PLAN_HERO = "pb_people_hub_plan_hero";` and, in
  `setup()`, `this.hero = registry.category(PLAN_HERO).getAll()[0] || null;`; template
  renders `<t t-if="hero" t-component="hero.Component" t-props="heroProps"/>` above the
  cards, and the cards move inside `<details class="pbpl-classic" t-att-open="!hero">`
  with summary "Classic planning tools · 7 screens" (when no hero is registered the
  fold is open and the page reads exactly as today). `heroProps` is memoised
  (`{ embedded: true }` is NOT allowed in this file by test — use `{ inPlan: true }`).
  Keep every string the tests look for (ledger §plumbing). The lens `groups` in
  `people_hub.js` becomes `[...PLAN_GATE, ...heroGroups()]` where `heroGroups()` reads
  the registry once in setup — a Decision-Room user without any wfp group must still see
  the Plan lens.
- `pb_people_hub/data/pb_sidebar.xml`: append `pb_decision_room` to `match_action_tags`.
- `decision_palette.js` (in the new module): `registry.category(PLAN_HERO).add(
  "decision_room", { Component: PbDecisionRoom, groups: DECISION_GATE })` and two ⌘K rows
  in the 2300 block: "Decision Room" (→ hub xmlid, lens `plan`) and "Saved plans"
  (→ same, with context `pb_focus: 'plans'`; the room scrolls to the dock when it sees
  `arrival.focus === 'plans'` — declare `wantsArrival`).
- The standalone action record `action_pb_decision_room` (tag `pb_decision_room`) renders
  the same component full-screen with a back chip "People" (`openHub` back pattern,
  `pb_hub/static/src/js/hub_nav.js`), for deep links.

## 7. Tests (numbered; all must pass on p9clone)

Python (`tests/test_decision_room.py`, `post_install`):
- T1 facade refuses gracefully: a user with no decision group gets `allowed: False` and
  empty baseline, no AccessError.
- T2 baseline shape on the demo company: teams ≥ 1, every team has heads > 0 and
  `pay_month_avg > 0`, sum of team heads == active employees in the company (±0), roles
  sum to team heads, ≤ 13 teams (12 + Other).
- T3 baseline is company-scoped: switching `allowed_company_ids` to another company
  changes the counts; no cross-company leak.
- T4 assumptions auto-create once per company; second read returns the same id; unique
  constraint blocks a duplicate.
- T5 save_plan creates, replace=True updates, unique name per company raises the friendly
  message, 21st plan refused with the friendly message.
- T6 delete_plan: user deletes own; user cannot delete another's (AccessError with a
  plain sentence); manager can.
- T7 set_reference keeps at most one reference per company.
- T8 facade timing: `get_room` on company 5 < 800 ms warm, < 3 s cold (assert and log).
- T9 no user-visible string in the module contains "Odoo" (walk xml/js/py/pot).
- T10 groups: `hr.group_hr_manager` implies `group_decision_user`; `base.group_system`
  implies manager.

Static (`tests/test_static_contract.py`): T11 every icon name used in xml/js exists in
`pb_import_kit` `IC`; T12 the action is a record, not a bare tag, and the tag is
registered in decision_room.js; T13 manifest asset order (scss, format, engine, charts,
room, palette, xml) and every file on disk is in the bundle and vice versa; T14 the
`pb_people_hub` tests still pass unchanged (run `/pb_people_hub` tags).

Engine (JS, run with node — `decision_engine.js` must be loadable outside Odoo: wrap the
`@odoo-module` exports so a `node tools/decision_engine_check.mjs` script can import
via a tiny shim, or keep the engine as a plain ES module with no Odoo imports):
- T15 baseline plan (no moves, no raise) reproduces `heads × pay` totals within 0.5 %.
- T16 bridge steps sum to exactly `plan.profit − ref.profit` (1e-6).
- T17 +10 people in a revenue team from month 3 → December heads +10, recruit cost only
  in month 3, ramp halves their capacity in month 3.
- T18 a level-4 hire costs more than a level-1 hire in the same team.
- T19 stressBand lo ≤ plan ≤ hi on revenue in every month.
- T20 coverage never exceeds 100 %; without a target coverage == 1 and revenue == 0.

Browser (Chrome MCP, payobook then abm; record screenshots in
`docs/handovers/wfplan_p1_shots/`):
- B1 People → Plan lands in the room; stage shows the company's real headcount and
  currency; "Classic planning tools" fold closed by default and opens to 7 cards.
- B2 Type a revenue target → profit tab appears, coverage tile appears.
- B3 Move "Add people" → hero number tweens, ripple runs, year cards update, story
  sentence names the team and the number.
- B4 Save plan "Board draft" → appears in dock; reload → still there; second browser
  user (abm login) sees it on abm only (company scoping).
- B5 Compare against the saved plan → "Was X" ticks move; delta pill re-bases.
- B6 Undo ×3, Reset, Motion off, Difference view, play through the year.
- B7 390 px phone: no horizontal scroll, stage number ≥ 40 px, control room stacked.
- B8 Dark mode of the platform: cards readable.
- B9 ⌘K "Decision Room" opens the lens; deep link `/odoo/action-pb_decision_room` shows
  the back chip "People".
- B10 A user with `hr.group_hr_user` only (no manager): lens hidden if they hold no wfp
  group; if they hold wfp_user the fold shows and the hero is present (implied group).

## 8. Build order (so something is demonstrable early)

1. Module skeleton + groups + models + facade + tests T1–T10 on p9clone.
2. Engine port + node checks T15–T20.
3. Cockpit: stage first (hero moment), then control room, then compass/year/story/
   journey, then dock + dialogs. Chrome-validate continuously on p9clone (port 8199 is
   fine for the browser: `http://3.104.113.197:8199/odoo/action-pb_decision_room`, or
   deploy to payobook when stable).
4. Plan lens hero slot in `pb_people_hub` + palette + sidebar match. Run `/pb_people_hub`
   tests.
5. Deploy ritual (ledger) to payobook, abm, payobook_template; verify versions + hashes.
6. Commits per feature; ledger append; phase report.

## 9. Report back (plain-English first, then engineering)

1. Three sentences a CEO understands: what opens under People → Plan now, what it shows
   for the Vietnam company, what it cannot do yet.
2. Test results table T1–T20, B1–B10 (pass/fail with evidence paths).
3. Facade timings on company 5 (cold/warm) and the roster source you verified
   (hr.contract vs hr.version fields) — write that fact into the ledger.
4. Deploy evidence: manifest vs `latest_version` per DB; hash match; screenshots.
5. Deviations from this spec and why; new gotchas appended to the ledger (WF3+).
6. Self-score against the design bar (hero, dead-ends, language, motion, ergonomics),
   with the one thing you would improve first.
7. Commit list (hashes + one line each).
