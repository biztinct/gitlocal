# JOURNEY Phase J7 — Two owner-reported legibility defects on the shared mapping board

**Read first:** `docs/handovers/JOURNEY_LEDGER.md` (J1–J6 outcomes, ALL MJ gotchas MJ1–MJ35),
then `MAPFIX_LEDGER.md` standing rules (deploy ritual, MF12/MF13/MF17/MF26/MF35/MF37/MF41,
CR6/CR20/CR21/CR22). **White-label absolute: no user-visible string may say "Odoo".** Branch 19.1.
One feature-scoped commit (explicit staging, ledger + this handover; leave `ABM/ABM Template.xlsx`
unstaged). **`d975e98d` (J6) is committed but NOT pushed — commit as usual, do not push.**
abm login: `ash@biztinct.com` / `J5validate!2026`. Current: `pb_formula_studio` **19.0.1.149.0**.
Baselines to take yourself (MJ11/MJ14/MJ20): post-J6 Python **420** with the same three
pre-existing reds, hoot **113**.

Both defects are on the **shared two-lane `MappingCanvas`** (owner screenshots: the
`System fields → Scheme` board on abm, config 14, filtered by `bank`, right column filtered to
Unmapped/Suggested) — i.e. they affect all five two-lane adapters, and D2 also affects the J4
transform board. J6's fixes were scoped to `TransformFlowBoard`; this is the same *family* of
defect one board over. Fix them in the shared component so both boards inherit it.

## D1 — The dock chip covers the first card in the column

Owner screenshot: the amber pill **"↑ 11 hidden by filter above"** renders ON TOP of the top-most
right-column card — "Employee Bank Ac… EMPLOYEE RECORD / EMPBANKACCOA" is legible only from its
second line down; the card's name row is behind the chip. Same class of defect J6 fixed on the
transform board (its deviation 4), now on the shared canvas.

Requirements:
- A dock chip must never occlude a card, at any viewport, in any filter/scroll state, in EITHER
  column, for BOTH the above and below variants. Reserve a band (offset the scroll content when a
  chip is present, or float the chip clear of the card band) — pick the approach that keeps wire
  geometry honest and say which you chose and why.
- **The chip must remain clickable and must keep its CR21/F1 behaviour** (`clickDock` finds
  suppressed wires; `jumpTo` clears the filter) — J6's MJ39-family lesson: do not delete
  live-tested behaviour while re-placing it.
- **Wire endpoints must stay correct after the re-placement.** If you offset content, the band
  edges that wires clamp to move with it — J6's MJ30 (a 49.75px coordinate-space offset painted
  every wire wrong for four phases) is exactly this hazard. Re-run J6's wire-measurement harness
  and report `maxErr` at 1440 and 1024 in the affected states.
- **Why the sweep missed it (investigate and fix the sweep):** MJ7 taught the sweep to skip pairs
  that do not share a layer, because "a dropdown is SUPPOSED to cover the chips beneath it". A
  dock chip is almost certainly being classified as that kind of intentional overlay. It is not —
  it is in-flow furniture that must never cover content. Make the sweep test dock chips against
  cards **permanently**, in both columns, and state what the misclassification was.

## D2 — Component and field names are truncated with no way to read them

Owner screenshot: right-column cards read "Enroll for Insu…", "Employee Bank Ac…",
"Phone Allowa…"; on the transform board earlier, "OT Night shift weeken…". The owner's ask,
verbatim: *"Find out a way to display full name of the component."*

Requirements:
- **The full name must be readable without leaving the board.** Preferred: let the name **wrap to
  up to two lines** (cards grow), keeping code/badges/ports laid out correctly; anything still
  too long ellipsises on the second line AND carries the complete name in a title/tooltip. If you
  judge wrapping unsafe, an always-available hover/focus tooltip plus a widened name column is an
  acceptable alternative — justify the choice with measurements, not preference.
- Applies to **both columns** and to the **transform board's** cards (shared card chrome).
- **Hard constraints from prior scars — read them before you touch card layout:**
  - MF13/MF26: `.mc-item-label > span` has `min-width: 0`; any affordance sharing the name's line
    reserves width even at `opacity: 0` and crushed the label to ONE CHARACTER. Constant-width
    trigger, out of the flow, or it breaks again.
  - MF27: popovers/tooltips must be measured then placed, never positioned from an estimate.
  - MJ34: an affordance nobody can find does not exist — if the answer is a tooltip, it must be
    discoverable (cursor/affordance), not a hidden `title=`.
- **Variable card heights are the risk.** Wrapping changes rects, so: wire anchoring, dock
  aggregation (`aggregateDocks`), `clampY`, scroll-into-view (`centreBoth`/`jumpTo`), keyboard
  walking and the geometry kernel's assumptions must all still hold. Prove with the wire harness
  (`maxErr 0`) and by exercising a card whose name wraps at both viewports.
- Sample values, chips/badges and the source pills must not be pushed off the card; the card's
  hit area and port position must remain stable while the pointer is over it.

## Safety rails

- MF37 oracle on abm: fingerprint `hr_integration_field_mapping`, `hr_payslip_import_mapping`,
  `hr_formula_rule` (config 14 `source_binding*`) before/after; **this phase should write
  NOTHING** — it is presentation only. Any probe that does write must Undo (J6's toast) and the
  final diff must be clean against the post-J6 baseline (abm: 41 mapping rows,
  `478c051b85e20e4d0e1c832376d3e0ed`).
- NEVER `action_process`; no live external pulls. MJ2 warm server before believing red hoot; MJ6
  version bump after late asset edits; MJ13 `innerWidth` assertion; MJ12 SVG-aware sweeps (with
  D1's dock-chip correction); MJ23 probe waits sized to round-trips.
- Screenshots to `.journey-shots/J7/`.

## Numbered test cases (abm; all pass before commit)

1. Reproduce first: capture the defect at 1440 with the owner's exact state
   (`System fields → Scheme`, left search `bank`, right filter `Suggested`/`Unmapped`) — the
   "before" shot goes in the index.
2. Dock chip vs cards: 0 occlusion in both columns, above AND below variants, at 1440 and 1024,
   across ≥4 filter/scroll states — asserted by the corrected sweep, not by eye.
3. The chip still works: click "N hidden above" → jumps/clears filter per CR21/F1; suppressed
   wires still counted and reachable.
4. Wire integrity after re-placement: `maxErr` reported at 1440 and 1024 in the D1 states; docked
   wires still fade/lose their arrowhead (J6 deviation 3).
5. Full names: the four owner-cited cards ("Enroll for Insurance", "Employee Bank Account",
   "Phone Allowance", and a transform-board long name) are fully readable on the board; the
   longest name in abm's 99-column catalogue is readable or explicitly ellipsised WITH a
   discoverable full-name affordance.
6. Card integrity: no label crushed to one character in any state (MF13 regression assertion);
   badges, code, sample and port all present and positioned; 0 overlaps over the full sweep at
   1440 and 1024.
7. Wrapping cards do not break geometry: with at least one wrapped card in each column, wires
   anchor with `maxErr 0`, `centreBoth` still centres, keyboard walking still lands correctly.
8. The transform board inherits the name fix (same card chrome) and keeps J6's alignment
   (`maxErr 0`).
9. Suites: self-taken baselines, finish at-or-above with new tests on top, 0 new failures; hoot
   additions translation-free (MJ3) and covering the dock-chip placement rule + the name-overflow
   rule as pure/DOM facts.
10. Grep gates: no user-visible "Odoo"; any new string translated.
11. MF37: final diffs clean (ideally untouched — this phase writes nothing).
12. Deploy per MAPFIX ritual over abm acme payobook payobook_template; `latest_version` verified
    in psql on all four.

## Report back

D1's root cause + which placement strategy you chose and why · the sweep misclassification you
fixed · D2's chosen approach with the measurements that justified it · per-case results (1–12) ·
`maxErr` numbers · suite tallies vs self-taken baselines · MF37 diffs · screenshots index
(before + after) · deviations with reasoning · new MJ gotchas appended to `JOURNEY_LEDGER.md`
(+ a J7 phase entry; STATUS stays COMPLETE with the defect-round note extended) · the single
commit hash. Do not push.
