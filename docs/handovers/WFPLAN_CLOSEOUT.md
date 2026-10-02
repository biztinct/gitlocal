# The Decision Room — Closeout (2026-09-07)

The Decision Room is finished and live. It is the screen where you set this year's
revenue target, move a handful of levers — people, pay, hours, shifts, when the new
people arrive — and watch headcount, workforce cost, the work you can deliver and
operating profit answer, month by month, on your own roster and your own pay.

Three phases, three implementation cycles, everything deployed to the master database
and to the tenant, browser-checked at desk size and on a phone, in light and in dark,
in English and in Vietnamese.

**Nothing in this room changes payroll.** It reads the roster and it saves plans. That
sentence is on the screen, in those words, and there is no code path from the room to an
employee, a contract, a payslip or a pay run.

---

# PART ONE — FOR THE OWNER

## 1. What is live, and where you find it

**People → Plan.** The Plan tab in the People app used to open a grid of seven old
planning screens. It now opens the Decision Room. The seven old screens are still there,
folded away under "Classic planning tools" at the bottom, and they open exactly what they
opened before.
*Screenshot: `wfplan_p3_shots/B34_payobook_1440_light.png`*

**Home → Decision Room.** The room now has a second door on your home page, in the same
strip as Pulse, Approvals and Wall. Same screen, one press from where your day starts.
*Screenshot: `wfplan_p3_shots/B30a_home_hub_decision_room_lens.png`*

**On a phone.** Open it on a 390-pixel screen and the dark stage fills the first view:
the big profit number, the year drawn as a line, the month strip. One bar sits at the
bottom of the screen — "Shape your plan" — and a thumb pulls up a sheet with every lever
in it. The headline number is repeated at the top of that sheet, so you can see what a
lever is doing while your thumb is still on it. This is the version for the taxi on the
way to a board meeting.
*Screenshots: `wfplan_p3_shots/B25a_phone390_stage_first.png`,
`B25b_phone390_sheet_open.png`, `B25c_phone390_sheet_hero_moves.png`*

**In Vietnamese.** A person whose Payobook is set to Vietnamese sees the whole room in
Vietnamese — every heading, every sentence, every warning, the printed brief, and money
in the words Vietnamese finance actually uses: ₫2.200 tỷ, ₫840 triệu, ₫12,5 triệu.
*Screenshots: `wfplan_p3_shots/B29a_vietnamese_1440.png`, `B29b_vietnamese_bridge_tab.png`*

**By search and by link.** Press ⌘K anywhere and type "Decision Room" (or "Saved plans",
which opens the room already scrolled to your saved plans). The room also has its own
address, `payobook.com/odoo/action-pb_decision_room`, which you can bookmark.

## 2. How to use it in five minutes

1. **Open it.** People → Plan, or Home → Decision Room.
2. **Type what you plan to earn this year** in the first box on the left. Type it the way
   you say it — `2,200 B`, `2.2 t`, or the whole number. Profit appears the moment it is
   there.
3. **Say what a good year looks like.** Press "Set goals". Switch on the ones that matter
   — margin, profit, cost, work delivered, team size, overtime — and put a number on each.
   Every figure on the page then keeps score against them.
4. **Move a lever.** Pick a team, add or remove people, choose the month they arrive. Or
   move the salary increase, the overtime, the evening and night shares. The big number,
   the line, the twelve month cards and the sentence underneath all move together.
5. **Ask the room for a way.** Inside the goals dialog, press "Find paths to these goals".
   It offers up to three calculated directions — build the team, develop the team, or a
   blend — each with its profit, what it changes, and what it protects. If they all come
   back to the plan you already have, it says so in one honest card rather than pretending.
6. **Try one before you keep it.** "Try this direction" repaints the whole room in
   preview, with an amber banner. "Keep this direction" makes it yours; "Back to my plan"
   puts everything back exactly as it was.
7. **Look closer.** The three cards under the stage open a workspace with four tabs:
   are there enough people on the right shifts, why profit is different, where a year of
   pay actually goes, and how many more people you could take before a goal breaks.
8. **Give it a reality check.** "And if demand surprises us?" swings demand ten per cent
   either way and tells you what happens.
9. **Save it.** "Save plan", give it a name. It is saved on the server for everyone at
   your company — not in your browser — up to twenty plans. Use "Compare against" to
   measure any plan against any other.
10. **Print it.** "Export the decision brief" opens one self-contained page in a new tab:
    the goals, the outcome, the reason for every difference, the twelve months and every
    assumption behind them. Use your browser's Print command to save it as a PDF.

Two shortcuts worth knowing: **⌘Z** undoes the last change (forty deep), and **⌘S** opens
the Save box. The whole room can be driven from the keyboard alone — Tab to a card, Enter
to open it, arrow keys across the tabs and along every slider, Shift+arrow to move a
slider ten steps at a time, Space to play the year, Esc to close anything.

## 3. What the numbers are built from

**Your people.** The room counts everybody active in the company you are looking at.
Each person's team and role come from their contract when the contract names them, and
from their employee record when it does not — one rule that answers both your databases.
Their pay is the monthly salary on their open contract. The room reads totals only: how
many people in a team, what a role costs on average. It never sends a person's name or
salary anywhere.

**How fresh it is.** The roster is re-read at most every ten minutes. Open "See the
assumptions" and the top line says how many people it counted and the clock time it read
them — "4,533 people · roster read at 14:02" — with a **Refresh** button beside it that
reads the roster again and leaves your plan exactly where it is.

**What is a record and what is an assumption.** The people, the teams, the roles and the
pay are records — they come from your database. Everything else is an assumption, and
every one of them is on the "See the assumptions" screen in a plain sentence:
contribution rates and the cap, the allowance share, the overtime multiplier and working
days, evening and night premiums, how the year's work splits across the three shifts,
what recruiting and ending a role cost, how productive a new person is in their first
month, the yearly bonus, costs that are not people, the shape of the year, and the
income-tax ladder. Your HR or finance lead can change any of them; everyone else sees
them and is told who to ask. Every change is recorded on the assumptions record with who
changed what.

**What it deliberately leaves out.** Individual people, the timing of working capital,
whether a roster is legal, and tax filings. It is a planning sketch, not a payroll
calculation and not a promise about the future.

## 4. Decisions still open — your call

**a) Retire the "Classic planning tools" fold?**
Today the seven old planning screens still fold open at the bottom of the Plan tab.
- *Keep them:* nothing changes; anybody who relied on them still has them.
- *Hide the fold:* the Plan tab becomes only the Decision Room — cleaner, and one less
  thing to explain. Half a day of work. Reversible.
- *Remove them altogether:* this is bigger than it looks. Your **Budget** screen is built
  on one of the old planning module's tables (`wfp.budget.actual`), so that module cannot
  simply be uninstalled — Budget would have to be moved onto its own table first. Call it
  two to three days, and it is not reversible without a restore. **Recommendation: hide
  the fold now, decide about removing later.**

**b) Push the code?**
Everything is committed on the `19.1` branch on the build machine and nothing has been
pushed to the shared repository — that has been true since the Workforce programme. There
are now **19 unpushed commits on this branch** — 14 from earlier work and 5 from this
phase. Pushing costs nothing and loses nothing; not pushing means one machine holds the
only copy.
**Recommendation: push.**

**c) The AB Mauri administrator password.**
The password recorded for the AB Mauri tenant does not work, and has not since Phase 1.
Every check on that tenant has been done with temporary users that are created, used and
switched off again. Resetting your own password is your decision, not ours, so it has not
been touched. Until it is reset, nobody can log into AB Mauri as the administrator.

**d) The demo plan and the demo target on Payobook Vietnam JSC.**
A saved plan called **"Board draft"** and a revenue target of **₫2,200B** were entered
during Phase 1's checks and are still there. They are harmless and they make the room
look alive for a demonstration. Say the word and either goes.

**e) Planning on or off, per customer.**
The Decision Room is governed by the same switch as the Plan tab — "people_plan" in your
tenant settings. Switch it off for a customer and both doors disappear together; switch
it on and both come back. It is on by default.

## 5. Temporary logins — all switched off

Every temporary user created across the three phases has been switched off again. None of
them can log in. They are listed here so nothing is a surprise later.

| Database | Login | What it was for | State now |
|---|---|---|---|
| payobook | `wfplan.vi@payobook.com` (4405) | the Vietnamese walk-through | archived |
| payobook | `wfplan.reader3@payobook.com` (4406) | the "can see it / cannot see it" check | archived |
| abm | `wfplan.validator@payobook.com` (246) | manager checks on the tenant | archived |
| abm | `wfplan.reader@payobook.com` (247) | read-only checks on the tenant | archived |
| abm | `wfplan.vi3@payobook.com` (248) | the Vietnamese walk-through on the tenant | archived |
| p9clone | `wfplan.p3@payobook.com` (3816) | the feature-switch check on the rehearsal copy | archived |

Your own password was never changed, on either database.

---

# PART TWO — FOR ENGINEERS

## 6. What shipped, per database

| Module | Version | p9clone | payobook | abm | payobook_template |
|---|---|---|---|---|---|
| `pb_decision_room` | 19.0.3.0.0 | ✓ | ✓ | ✓ | ✓ |
| `pb_hub` | 19.0.1.8.0 | ✓ | ✓ | ✓ | ✓ |
| `pb_import_kit` | 19.0.1.12.0 | ✓ | ✓ | ✓ | ✓ |
| `pb_people_hub` | 19.0.1.4.0 (unchanged in P3) | ✓ | ✓ | ✓ | ✓ |
| `pb_home_hub` | 19.0.1.0.0 (new dependency, already installed) | ✓ | ✓ | ✓ | ✓ |

Module trees verified byte-identical between the working copy and
`/odoo/odoo-server/addons` (sha256 over each tree, `__pycache__`, `*.pyc` and `.DS_Store`
excluded). `ir_module_module.latest_version` verified per database.
`pb_decision_room/i18n/vi_VN.po` loaded on all four (`field_description->>'vi_VN'` on
`pb.decision.assumptions.revenue_target` reads "Mục tiêu doanh thu cả năm").
`pg_dump -Fc` backups taken before the production upgrade:
`/tmp/wf_p3_payobook.dump` (52 MB), `/tmp/wf_p3_abm.dump` (16 MB),
`/tmp/wf_p3_payobook_template.dump` (11 MB).

## 7. Tests

- **97 server tests green** on p9clone (`--test-tags /pb_decision_room,/pb_people_hub,
  /pb_hub,/pb_import_kit`): 44 `pb_decision_room`, 34 `pb_hub`, 37 `pb_people_hub`.
- **70 engine checks green** under `node tools/decision_engine_check.mjs` — no database,
  no browser: it loads `decision_engine.js`, `decision_format.js` and
  `decision_charts.js` off disk exactly as they ship.
- Browser walks B1–B36 across the three phases, on payobook (company 5, 4,533 people) and
  on abm (company 1, 153 people), at 1440 px and 390 px, light and dark, English and
  Vietnamese. Phase 3 evidence: `docs/handovers/wfplan_p3_shots/`.

Timings on company 5: facade `get_room` **78 ms cold, 7 ms warm**; the goal finder
**151 ms** over 46 combinations; the headroom scan **< 25 ms**.

## 8. Seams added, and what they are for

| Seam | Where | Why |
|---|---|---|
| `pb_people_hub_plan_hero` registry | `pb_people_hub/static/src/js/plan_launcher.js` | the Plan lens renders whatever is registered here above the legacy cards; the dependency runs hub → room, so the hub cannot import the room back |
| `pb_home_hub_lens` entry `decide` | `pb_decision_room/static/src/js/decision_palette.js` | the Home door, gated by the same groups and the same feature switch |
| `FEATURE_BY_LENS` `pb_home_hub#decide` | `pb_hub/static/src/js/hub_features.js` | one switch, both doors — a tenant without planning cannot find the room on Home either |
| palette `focus` forwarding | `pb_hub/static/src/js/hub_palette_service.js` (P1) | lets a ⌘K row be more specific than its lens ("Saved plans" scrolls to the dock) |
| `useTranslator(fn)` | `decision_engine.js`, `decision_format.js` | those two files may not import anything (the node checks load them raw), so the platform's `_t` is injected instead — see WF23 |

## 9. Commits (this phase)

Feature-scoped, explicit paths, on `19.1`, **not pushed**.

| Hash | What |
|---|---|
| `ec1d7d20` | `chevronUp` in the shared icon registry, for the phone's sheet bar; `pb_import_kit` 19.0.1.12.0 |
| `97560b5b` | the Home hub lens, gated by the same groups and the same feature switch; `pb_hub` 19.0.1.8.0 |
| `201c93c3` | the phone, the keyboard, the motion, the scaled experiment, the roster refresh and the Vietnamese-aware formatter; `pb_decision_room` 19.0.3.0.0 |
| `20845108` | the Vietnamese catalogue — 686 terms, `.pot` refreshed |
| `db61b064` | this closeout, the P3 phase log, gotchas WF23–WF29 and the browser evidence |

## 10. What Phase 4 could be

- **Shift rosters from the real schedule.** Today the three shift shares are a pool of
  hours, not a roster. `hr.attendance` and the working-schedule records could supply the
  real split, and the tab could say "this is what you actually ran last quarter".
- **Actuals against plan.** Once a pay run closes, the month it covers has a real
  workforce cost. Drawing that on the same line as the plan turns the room from a sketch
  into a tracker, and is the single most valuable thing left.
- **More than one year.** Everything in the engine is a twelve-month loop. A three-year
  view is a bigger change to the charts than to the arithmetic.
- **The phone's canvas.** The hub's own rails take about 116 px of a 390 px screen. A
  full-bleed lens on a phone would give the stage a third more room; that is a `pb_hub`
  change and would improve every cockpit, not just this one.

## 11. Where to read next

- `docs/handovers/WFPLAN_LEDGER.md` — the programme law: rules, credentials, verified
  plumbing facts and gotchas WF1–WF29.
- `docs/handovers/WFPLAN_P1_DECISION_ROOM.md`, `WFPLAN_P2_LOOK_CLOSER.md`,
  `WFPLAN_P3_WOW_AND_CLOSE.md` — the three phase specifications.
- `docs/handovers/wfplan_p1_shots/`, `wfplan_p2_shots/`, `wfplan_p3_shots/` — the
  browser evidence.
