# FILTER wave 1 — report (People lifecycle boards)

Builder: Opus (w1), worktree branch `worktree-agent-a4b7dfba4bca6380d`
(rebased onto `19.1` @ `d857c857b`, kit 1.2.0). Not pushed, not merged. Nothing touched on
the live addons, the live databases or `/opt/deploy-notes.md`.

## Summary

| Screen | Module | Result |
|---|---|---|
| Contracts | `pb_contracts` 19.0.1.10.0 | PASS (T1–T22 on the preview, console clean) |
| Journeys | `pb_lifecycle` 19.0.1.6.0 | PASS (T1–T22 on the preview, console clean) |
| Awards | `pb_comp_ben` 19.0.1.6.0 | PASS (T1–T22 on the preview, console clean) |
| Growth plans | `pb_pip` 19.0.1.4.0 | PASS (T1–T22 on the preview, console clean) |
| New joiners | `pb_onboarding` 19.0.1.3.0 | PASS (T1–T22 on the preview, console clean) |

Modules touched (live deploy sync + `-u` list, all get a NEW dependency on
`pb_filter_kit`, so every database where they are installed needs the `-u`):
`pb_contracts, pb_lifecycle, pb_comp_ben, pb_pip, pb_onboarding, pb_learn`.

`pb_learn` is bumped to 19.0.20.7.0 once for the wave (replica + anchors);
19.1 meanwhile reached 19.0.20.6.5 (wave 4), so 20.7.0 is still the highest.
**Needs `pb_filter_kit` 19.0.1.2.0** (already in 19.1): Growth plans and New
joiners use the `next_7` preset and an explicit preset list; Awards and
Growth plans use `label_sudo`. Deploy the kit in the same batch.
Other waves bump it too: at merge time take the highest version and keep
every wave's `screens.js` / `anchors.json` hunks.

## 1. Per screen

Sections that hide themselves on the payobook copy (one value or none, kit
rule; they reappear on databases with more variety): Contracts — Trial period
ends; Journeys — Status, Company; Awards — none; Growth plans — Asked by,
Check-in rhythm, Company; New joiners — Where they are, Status, Running late
(every joiner on the copy is "settling in" with late steps; the strip still
shows the three steps).

### 1.1 Contracts (`pb_contracts`, model `pb.contracts`, screen key `contracts`)
- Sections (11): **pinned** Contract status (choice in the board's own words:
  Draft / Running / Expired / Cancelled — the stock label of a draft is "New"), Pay structure
  (`struct_id`), Contract ends (`date_end`, future presets); then Where it is
  (choice: Draft / Running / Ending within 30 days / Ended), Started
  (`date_start`), Department (`employee_id.department_id`), Job position,
  Contract category (`type_id`), Monthly wage (money), Trial period ends,
  Company.
- Views: All contracts · Running · Ending within 30 days · Draft · Started this month.
- Sorts: Newest start first (default), Earliest end date first, Oldest start
  first, Person A to Z, Highest wage first. Page size 60.
- Removed: search box, start-date chips + custom range, structure chips
  (keyed on NAME), the "Showing … / Show all" line, client `filtered` /
  `_inDate` / `stepOf`, the 240 cap. `get_board` keeps the numbers line and
  `step_counts` (Learn's `get_board` refs) without rows.
- Kept: 4-step strip (counts from the server for the panel's state, step
  press = `kit.toggleFilters({step:[key]})`), drawer soft registry,
  `?contract=` deep link, `HubBackChip`.
- "Running" keeps the old server meaning: open and NOT ending within 30
  days, including open contracts whose end date is already behind them —
  so every running contract sits at exactly one step (the handover's
  "no end date or end date > 30 days" would have dropped those from every
  step).
- Learn: `ct-filters` (reserved) moved onto the kit toolbar; replica
  `contracts()` draws view tabs + Filters + search; anchor text updated.

### 1.2 Journeys (`pb_lifecycle`, model `pb.journeys`, screen key `journeys`)
- Sections (12): **pinned** Journey type, Status, Department; then Where it
  is (start / under way / nothing left to do — `task_ids any`), Running late
  (`task_ids any [open, due < today]`), Key date, Checklist used, Started
  by, Done (%) (number), Opened on, Job position, Company.
- Views: All journeys · Running now · Steps overdue · Not started · Nothing left to do.
- Sorts: Latest key date (default), Earliest key date, Opened most recently,
  Least done first, Person A to Z. Page size 60.
- Removed: search, type chips, state chips, "Running late" chip, the
  "Showing …" line, client `visibleRows`, the 400 cap, `type_counts`.
  `get_board` keeps access, numbers, types and checklists (start dialog).
- Refusal: `pbf_layout` returns `refused` without lifecycle access.
- Refresh after a drawer action now re-reads in place (it used to blank
  the whole screen, which would have remounted the panel).
- Learn: nothing in Learn describes this screen — `grep -c journeys.xml
  pb_learn/static/src/anchors.json` = 0; no lesson has `"screen":
  "journeys"`; no `journeys()` replica.

### 1.3 Awards (`pb_comp_ben`, model `pb.incentives`, screen key `awards`)
- Sections (12): **pinned** Where it is (draft / waiting / agreed / in a
  pay run / paid / not approved), Kind, Pay it in (`period_month`); then Who
  it is for and Department (both `label_sudo`), Pay run, Amount (money), Approval, Where it has
  got to, Where it came from, Asked by, Letter on file.
- Views: All awards · Waiting for approval · Agreed, not in a run · In a pay run · Paid this month.
- Sorts: Pay month newest (default), Pay month oldest, Largest amount,
  Raised most recently. Page size 60.
- Removed: search, kind chips, "Showing …" line, client filtering, the 400
  cap. The numbers line was counted from the 400 loaded rows; it is now
  `search_count` over every award (the "not approved" figure too).
- Every figure now filters (two new: "agreed, not in a run" and "paid this
  month" press `where` + pay month = this month, as they count).
- Search: a person (name or code, resolved under sudo for the same R56
  reason `_person()` reads the employee as the system) or a reason.
- Refusal: `pbf_layout` returns `_refusal()['why']` under the same rule.
- Learn: new reserved anchor `aw-filters`; replica `awards()` draws the
  strip. `aw-steps`, `aw-table`, `aw-put` unchanged.

### 1.4 Growth plans (`pb_pip`, model `pb.pip`, screen key `growth`)
- Sections (14): **pinned** Stage, HR owner, Plan ends; then Drifting or at
  risk (`domain_method`; values "Needs attention" / "On track or closed"),
  Department (`label_sudo`), Asked by, Plan template, Plan starts,
  Check-in rhythm, Seen by the person, Outcome, Past its end date, Company.
- Views: **Open plans** (start view) · Closed plans · Waiting on a decision ·
  Ending within 7 days · Not yet seen.
- Sorts: Ending soonest (default), Started most recently, Asked most
  recently. Page size 60.
- The Open/Closed toggle button is gone (two views). The step strip hides
  when only closed stages are listed (W1-T4).
- "Ending within 7 days" = open stages + the kit 1.2.0 `next_7` preset (a
  range frozen when the views were built was used until kit 1.2.0 landed).
- "Drifting or at risk": non-stored (R2) — reached through `domain_method`
  (`_risk_ids`, computed once per request into `cr.cache`), so the figure
  still filters. The card badge stays.
- Removed: search, stage chips, owner chips (by NAME), "Needs somebody
  today", `_facet`, the 300 cap. Numbers counted over every open plan.
- Learn: new reserved anchor `gw-filters`; replica `growth()` draws Open
  plans / Closed plans + Filters + search.

### 1.5 New joiners (`pb_onboarding`, model `pb.onboarding`, screen key `joiners`)
- Sections (12): **pinned** First day (presets next 7 / next 30 days, this
  week, this month, last month, last 90 days, no first day yet), Where they are (ready / settling /
  done), Department; then Buddy (main buddy, help says stand-ins are not
  counted), HR partner, Country, Checklist used, Status, Started by,
  Manager, Running late (`task_ids any`), How they say it is going
  (`domain_method` over `pb.newhire.pulse`).
- Views: All new joiners · Joining this week · Still without a buddy · Steps overdue · Started, checklist open.
- Sorts: Latest first day (default), Earliest first day, Least done first,
  Person A to Z. Page size 60.
- Removed: search, month / department / country chips, "Needs something",
  `_facet`, `_d`, the 300 cap. Numbers counted over every joiner on the
  board; "Still without a buddy" now counts the main buddy only, so pressing
  it lists exactly what it counts.
- Learn: new reserved anchor `nj-filters`; replica `joiners()` draws the strip.

## 2. Test matrix

Preview `pbf_preview` (copy of payobook, kit 1.1.1 at test time), held
02:05–02:48 UTC by w1; Claude-in-Chrome on http://localhost:8170, sign-in
from the preview's throwaway login. P = pass, n.a. = not applicable.

| Test | Contracts | Journeys | Awards | Growth plans | New joiners |
|---|---|---|---|---|---|
| T1 open, counts, first tab lit, no console errors | P | P | P | P (start view "Open plans") | P |
| T2 tick → chip, N of total, own count stays, others recount | P | P | P | P | P |
| T3 OR within a section | P (9+4,516) | P (11+10) | P | P | P |
| T4 AND across sections | P (4,525 → 17) | P (21 → 2) | P | P | P |
| T5 Only | P | P | P | P | P |
| T6 find a value, Enter ticks first, Escape clears | P ("vietnam") | P ("facil") | P ("spot") | P ("evaluat") | P ("quality") |
| T7 find nonsense → "Nothing matches" | P | P | P | P | P |
| T8 preset chip / Pick dates range chip | P | P | P | P | P |
| T9 number minimum, separators | P (₫20M or more, 20,000,000) | P (Done ≥ 10 %) | P (₫3M or more) | n.a. (no number section) | n.a. |
| T10 chip opens its section (panel scrolls, page does not), × removes, Clear all | P | P | P | P | P |
| T11 search, "/" focuses, Escape clears | P | P | P | P | P |
| T12 every sort changes the first row | P (5 sorts) | P (5) | P (4) | P (3) | P (4) |
| T13 paging "Show 60 more" | P (60 → 120 of 4,534) | n.a. (22 rows) | n.a. (13) | n.a. (6) | n.a. (11) |
| T14 save private view, rename, share toast, delete with confirmation | P | P | P | P | P |
| T15 every built-in view applies its filters and lights its tab | P | P | P | P | P |
| T16 figure presses the panel, again → back | P | P | P | P | P |
| T17 hide filters, badge, reload keeps hidden + filters | P | P | P | P | P |
| T18 copied link restores filters + search | P | P | P | P | P |
| T19 bulk / export on the filtered set | n.a. (none) | n.a. | n.a. (queue dialog is server-driven, never read the list) | n.a. | n.a. |
| T20 empty for a filter → "Show all"; empty for a search names the term | P | P | P | P | P |
| T21 phone drawer | partial (see note) | partial | partial | partial | partial |
| T22 Vietnamese labels, views, sorts | P | P | P | P | P |
| Wave test | W1-T1 P | W1-T2 P (19 = 19) | W1-T3 P | W1-T4 P | W1-T5 P (7 rows, 0 with a buddy) |

- **T21 note:** `resize_window` did not change this browser's viewport (it
  stayed 1,920 px, cf. F23), so the narrow drawer was checked with the class
  fallback the test list allows: with `pbf--narrow` the panel becomes a fixed
  330 px drawer at the left edge over the list. The scrim only appears when the
  kit itself detects a narrow window, which could not be produced here.
- **W1-T3:** proved on the preview copy from a shell with a user outside the
  awards groups: `pbf_layout` returns the board's refusal sentence,
  `get_awards_page` returns no rows, and the screen's own lock message shows
  (the kit makes no further calls). Growth plans refuses the same way.
- Also checked: every built-in view's count equals the rows its page returns
  (all five screens, from a shell); each card / row still opens its drawer or
  dialog (contract drawer not re-tested, journey / plan / joiner drawers and
  the New award dialog yes); an awards-only reader (no HR rights) sees person
  and department names, rows and search (after `label_sudo`).
- Timings on the preview (4,534 contracts): layout 0.16 s, counts 0.10 s,
  page 0.12 s on Contracts; every other screen under 0.2 s per call.
- After kit 1.2.0 landed (during my hold-out) I re-ran the server probe
  against kit 1.2.0 with the final code: all views still equal their pages,
  the new presets count correctly. The two tabs that now use `next_7`
  ("Ending within 7 days", "Joining this week") were not re-clicked in a
  browser — please include them in the post-deploy smoke.
- Clean-up: both test views deleted (0 left), `pbf:*` keys cleared from
  local and session storage, preview session signed out, tab closed.

Screenshots (Claude-in-Chrome, 0.6 scale): Contracts
`/var/folders/tl/jk1lq25507v_yj3394mz25x00000gp/T/claude-chrome-screenshots-7vHXhr/screenshot-1793413766182-5.jpg`,
Journeys `…/screenshot-1793414034014-6.jpg`, Awards `…/screenshot-1793414175744-7.jpg`,
Growth plans `…/screenshot-1793414346631-8.jpg`, New joiners `…/screenshot-1793414489284-9.jpg`.

## 3. Deploy evidence

Builders do not deploy (wave contract §D). Preview rehearsal:
- `pbf_preview.sh upgrade pb_filter_kit,pb_contracts,pb_lifecycle,pb_comp_ben,pb_pip,pb_onboarding,pb_learn`
  → `EXIT=0 errors=0`; latest_version on the copy: pb_contracts 19.0.1.10.0,
  pb_lifecycle 19.0.1.6.0, pb_comp_ben 19.0.1.6.0, pb_pip 19.0.1.4.0,
  pb_onboarding 19.0.1.3.0, pb_learn 19.0.20.7.0, pb_filter_kit 19.0.1.1.1.
  The only upgrade WARNINGs are old duplicate field labels.
- Second `upgrade pb_lifecycle,pb_pip` (to load the stored option-label
  translations, F27) → `EXIT=0 errors=0`.
- Preview server log: no ERROR / CRITICAL line during the hold.
- PO gate (ledger §5) passed on the box for all five `vi_VN.po`; no old
  translation lost (polib comparison: 0 lost, 0 changed per module).
- No live deploy (builders do not deploy); no cron snapshot needed.

## 4. Kit gaps and design debts

Kit gaps (not changed — for the coordinator):
1. (Answered by kit 1.2.0 `always`, not adopted in W1.) **A section the screen must count on every refresh even while folded.**
   Every W1 screen has a step strip that is a filter section ("Where it is",
   "Stage"); `kit.counts` only holds open sections, so each screen's page
   call recounts that one section server-side (`_pbf_step_counts`). A
   `alwaysCount: true` section flag (or `kit.counts` for a named key on
   every refresh) would remove the duplicate and the strip would update in
   the same round trip as the panel.
2. (Answered by kit 1.2.0, ADOPTED in W1.) **No "next 7 days" / "this week" date preset**, and one preset set per
   section (past OR future). Growth plans "Ending within 7 days" and New
   joiners "Joining this week" are custom ranges baked into the built-in
   view; a tab kept in the browser tab's memory over midnight shows as
   "changed". New joiners' First day needs both past and future presets.
3. (Ledger F29.) **`searchPlaceholder="'…'"` is never translated** (a literal inside an
   expression is not extracted). W1 screens pass a `_t` getter; the
   reference (`pb_people`) still ships an English-only placeholder.
4. (Resolved by W2, ledger F13.) The anchor lint now accepts `coach="'x'"`;
   the W1 templates also name the anchor in an XML comment beside the
   layout, which is harmless.

Design debts:
- Card-level "drifting" (Growth plans) and "pulse red" (New joiners) remain
  Python facts reached through `domain_method`; fine at today's sizes
  (open plans and joiners are tens), would need a stored field past ~1,000.
- Department / person sections on Awards and Growth plans go through
  `employee_id.*`; a reader without HR rights on employees may see those
  two sections hide themselves (kit degrades per section). Search is safe
  (resolved under sudo).
- Journeys "Steps overdue" figure counts overdue STEPS (101) while pressing
  it lists the JOURNEYS with an overdue step (19); same on New joiners (65 vs
  11). That was already so before W1; a sentence under the figure, or
  counting journeys, would remove the surprise.
- The step strips still count server-side in each page call
  (`_pbf_step_counts`, with the late / risk flags the kit cannot give);
  `always: ['step']` (kit 1.2.0) could replace the plain-count halves.
- Awards: kind "Training reimbursement" (added by another module) shows a
  blank kind chip in the table — the board's own label map does not know it
  (pre-existing).
- "Clear all" keeps the previous tab lit with its "changed" dot (kit
  behaviour since 1.0); pressing a figure no longer does (kit 1.1.1).
- New joiners: a case without `anchor_date` falls into "Getting ready"
  (the old screen fell back to `_joining_date()`); Country no longer falls
  back to the company's country.

## 5. Self-score against the design bar

Scale 1–5 against the bar (hero moment / zero dead-ends / plain language /
motion with purpose / keyboard + bulk ergonomics).

| Screen | Hero | Dead-ends | Language | Motion | Keyboard / bulk | Note |
|---|---|---|---|---|---|---|
| Contracts | 4 | 5 | 5 | 4 | 4 | 4,534 contracts paged; strip, figures, tabs and panel agree |
| Journeys | 4 | 5 | 5 | 4 | 4 | refresh no longer blanks the screen |
| Awards | 4 | 5 | 5 | 4 | 3 | table is cramped beside the open panel (names wrap) |
| Growth plans | 4 | 5 | 5 | 4 | 4 | Open/Closed toggle became tabs; risk filter survives |
| New joiners | 4 | 5 | 5 | 4 | 4 | future first days now one click |

Hero = the panel + strip combination is the kit's; the screens add no new
hero of their own (non-goal). Every state is designed: loading skeleton,
nothing-yet, empty-for-filter, empty-for-search (names the term), load
failure with Try again, paging; refusals show the board's own sentence.

## 6. Commits

On `worktree-agent-a4b7dfba4bca6380d`, on top of `19.1` @ `d857c857b`:

| Hash | Screen |
|---|---|
| `eb03c4ecb` | Contracts (pb_contracts + pb_learn bump/replica/anchor) |
| `276d180e4` | Journeys (pb_lifecycle) |
| `6e2a909d9` | Awards (pb_comp_ben + pb_learn replica/anchor) |
| `9882d9087` | Growth plans (pb_pip + pb_learn replica/anchor) |
| `802b6e2f9` | New joiners (pb_onboarding + pb_learn replica/anchor) |
| (this commit) | report + ledger F26–F30 |

Each screen commit carries its own Vietnamese and the test-pass fixes
(folded in). Nothing is left uncommitted. Not pushed, not merged. If `19.1`
moves again before the merge, the only expected conflict is the
`pb_learn/__manifest__.py` version line (take the highest).

## 7. New gotchas

Appended to `FILTER_LEDGER.md` §4: **F26** hold race between two waiters
(check the holder file names you), **F27** stored option labels need `-u` to
show their Vietnamese (and were missing in two modules), **F28** use a
`choice` when a stock label contradicts the board's words, **F29** literal
`searchPlaceholder` is never translated, **F30** Chrome tool blocks
`key=value`-looking results.
