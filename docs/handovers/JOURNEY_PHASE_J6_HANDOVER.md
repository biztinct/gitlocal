# JOURNEY Phase J6 — Three owner-reported defects on the live Transformations board

**Read first:** `docs/handovers/JOURNEY_LEDGER.md` (J1–J5 outcomes, ALL MJ gotchas MJ1–MJ29),
then `MAPFIX_LEDGER.md` standing rules (deploy ritual, MF12/MF17/MF35/MF37/MF41, CR6/CR20).
**White-label absolute: no user-visible string may say "Odoo".** Branch 19.1. One feature-scoped
commit (explicit staging, ledger + this handover included; leave `ABM/ABM Template.xlsx` unstaged
as found). **The branch is now PUSHED through `47a361cb` — commit as usual, do not push; the owner
decides pushes.** abm login: `ash@biztinct.com` / `J5validate!2026`.

This is a MAPFIX-D-style defect round: the owner used the live J4 Transformations board on abm
(config 14, connector 3 "Zoho People (ABM)") and reported three defects, with screenshots. One of
them **destroyed live data that must be repaired first**.

## D0 — REPAIR FIRST: the owner's double-click deleted a live wire on abm

The owner double-clicked the rule→component wire of rule **"Overtime 300% — hours"** (output key
`OTHRS300`) and the board deleted the mapping. Evidence: the board now shows the rule with the
`Unread output` pill and the right lane reads "0 fed by a rule"; its sibling `OTHRS150` is still
wired to component "OT 1.5 Hours" (`OT15HOURS`, note "Already fed by Rule output 'OTHRS150'").

Repair before anything else:
1. Diff abm's `hr_integration_field_mapping` against J5's recorded closing state (59 rows; J4's
   board-wire id list `[37,38,40,41,39,42,33,36]` is in the J4 phase entry). Identify the missing
   row — expect the one with `source_field='OTHRS300'` targeting the "OT 3.0 Hours"-family
   component (symmetric to the OTHRS150→OT15HOURS pair; confirm the component by code/name before
   writing).
2. Recreate it through the ORM with its original business fields (`connector_id`, `endpoint_id`,
   `source_field`, `target_rule_id`, transform config if any — check the sibling wire's shape).
   The id will differ (ORM cannot mint old ids — J3's precedent); record old id → new id.
3. Check whether the component's `source_binding` was cleared by the delete
   (`api_mapping_delete` clears a binding only when it was that wire's — post-J1 line for the
   guard; pre-J1 it was `pb_formula_studio.py:5138-5141`). If cleared, restore
   `('rule', 'OTHRS300')` with `origin='migration'` semantics (use the setter, note the origin
   choice in the report).
4. Screenshot the healed board (rule no longer `Unread output`, component note restored) and
   fingerprint the table. This repair is the ONE intended write of the phase — everything after
   it runs under the usual MF37 empty-diff discipline.

## D1 — Wires misalign when the search filter is active

Owner screenshot (search `OTHRS150`): the three read-edges (dashed, field→rule) originate well
BELOW their cards' right-edge ports — the cards sit at the top of the lane but the curves start
from where the cards would sit UNFILTERED. Additionally the two amber dock chips
("↑ 10 hidden by the search above" / "↑ 25 hidden by the search above") render ON TOP of the
middle and right lane headers — the "TRANSFORMATIONS" title reads "NS" behind the chip.

Fix both on the `TransformFlowBoard`:
- Wire endpoints must be computed from the FILTERED layout's real card rects (the canvas learned
  this as MF38/F1: ask the filter state, then measure what is actually rendered — likely the
  board is deriving Y positions from unfiltered indices or stale rects; find the actual cause and
  say which it was).
- Dock chips must never cover lane headers: reserve a band for them (or offset below the header
  row) at every viewport; prove with the MJ7/MJ12 overlap sweep including the filtered state —
  the sweep evidently did not include "search active with hidden-above chips", so ADD that state
  to the sweep permanently.

**D1 addendum (owner's second screenshot, UNFILTERED board):** the misalignment is not
filter-specific. With no search active and the right column scrolled ("↑ 1 above" / "↓ 6 below"
docks showing), the solid rule→component wires anchor to the WRONG right-lane cards — they sweep
up to "Actual Parking" / "Actual Taxi allowance" (sealed `Calculated` components, "Already fed by
Calculated", which no rule feeds) instead of their true targets or the dock chips. Likely the
same root cause family: wire Ys derived from unscrolled/unfiltered card positions instead of the
rendered rects + the canvas' clamp-to-dock behaviour (CR21/F1 precedent). The owner also reports
double-clicking a SOLID wire misaligns as well. Additionally, the floating **`× Remove` pill
renders mid-wire** — directly implicated in D3's accidental delete: a double-click's second click
lands on the verb. Whatever D3 does with the verb, it must not sit where a click/double-click on
the wire naturally lands.

## D2 — Double-click on a read (dashed) wire should centre both ends

Parity with the shared canvas: double-clicking a wire elsewhere centres/aligns both endpoints
(`centreBoth` family). On the transform board's dashed read edges, double-click currently does
nothing (or worse — see D3). Make double-click on ANY transform-board wire centre both ends,
clearing the filter with the existing "clear the filter and show me" behaviour if an end is
hidden (reuse the canvas' vocabulary; do not invent a second reveal mechanism).

## D3 — Double-click must NEVER delete; deletion gets an explicit verb + Undo

The owner's double-click on the live rule→component wire DELETED it. Whatever the mechanism
(inspect the board's wire hit handlers — most likely the armed-cut or click-twice path landing as
two clicks), the required behaviour is:

- **Double-click is never destructive** — on any wire it does D2's centre-both. Single-click
  selects. Deletion happens ONLY through an explicit, labelled verb (the wire's existing Remove
  affordance / keyboard Delete on a selected wire is acceptable if it is unmistakably explicit).
- **Every wire deletion on the transform board AND the API board gets an Undo**: before calling
  `api_mapping_delete`, snapshot the row's full business spec (including transform config and
  whether the target's binding pointed at this wire); after deletion, show a toast
  "Wire removed — Undo" (house toast pattern); Undo recreates via `api_mapping_create` (+
  transform re-apply + binding restore) and re-reads the board. Undo lives as ONE helper shared
  by both boards' delete paths — not two copies. The recreated row's id may differ; the toast
  disappearing ends the undo window (no queue, no history stack — this is a safety net, not an
  undo system; note that scope decision in the report).
- Excel/employee-board deletes are OUT of scope this round; if the shared helper makes them
  nearly free, note it as a follow-up rather than doing it.

## D4 — Creating a rule→component mapping by mouse is effectively impossible

Owner report (third screenshot): clicking the middle-column rule card opens the Rule Composer —
correct per J4 — but the owner then **cannot select the rule's output and map it to a scheme
component at all**. J4's own validation drew wires via "arm-output → click-component", so either
the arming affordance regressed or it is so subtle the owner cannot find it (both count as the
defect: an affordance a user cannot discover does not exist — MF26's lesson).

Required behaviour:
- The rule card's **output side carries an unmistakable draw affordance** — the output-key
  chip/port styled and labelled as the thing you click to wire (hover cursor, tooltip
  "Wire this output to a component…"). Clicking it ARMS the output: the board shows the canvas'
  armed banner ("Click a component to connect · Esc to cancel"), right-lane cards light as
  targets, and clicking one creates the wire through `api_mapping_create` (J3's conflict dialog
  firing when applicable). Escape disarms (existing ladder).
- The armed-affordance click must NOT be swallowed by the card's open-composer click (event
  isolation), and opening the composer must remain available and obvious (card body/title).
- A keyboard path exists: focus the output affordance, Enter arms, focus a target, Enter wires
  (MF33 guard intact).
- If investigation shows the J4 arming path still works but was undiscoverable, say so in the
  report and fix the discoverability anyway; if it regressed, name the commit/cause.

Additional numbered test cases:
13. Mouse-only creation: starting from a cold board, wire an unread output to an unfed component
    using only clicks (screenshot each step); delete + Undo restores; diff clean.
14. Clicking the card body still opens the composer; arming the output does NOT open the
    composer; Escape disarms; the armed banner shows and clears correctly at 1440 and 1024.

## Safety rails

- After D0's repair, the standard MF37 discipline: fingerprint
  `hr_integration_field_mapping`, `hr_api_transformation_rule`, `hr_formula_rule` (config 14
  `source_binding*`) before/after all remaining live probes; every test probe that deletes a wire
  must UNDO it (which conveniently tests the feature) and end with the diff clean against the
  post-repair state.
- NEVER `action_process`; no live external pulls. MJ2 warm server; MJ6 version bump after late
  asset edits; MJ13 `innerWidth`; MJ23 probe waits sized to round-trips.
- Take suite baselines yourself (MJ11/MJ14/MJ20): post-J5 ledger says Python 373 with the 3
  pre-existing reds, hoot 98. Screenshots to `.journey-shots/J6/`.

## Numbered test cases (abm; all pass before commit)

1. D0 repair: `hr_integration_field_mapping` back to 59 rows; the OTHRS300 wire live; the rule's
   `Unread output` pill gone on both the Transformations tab and the Journey; binding state
   verified and reported; before/after fingerprints in the report.
2. Search `OTHRS150`: every visible wire's endpoints terminate ON the visible cards' ports at
   1440 and 1024 (bounding-box assertion on endpoint-to-port distance, not eyeballing).
3. The hidden-above/below dock chips overlap NOTHING (lane headers included) in any filter state
   — the MJ7/MJ12 sweep now includes the filtered-with-chips state and passes 0 overlaps.
4. Double-click a dashed read wire → both ends centre (filter cleared via the existing reveal
   vocabulary if needed); nothing is written (diff clean).
5. Double-click the live rule→component wire → centres both ends; the row still exists (diff
   clean). Repeat 10 rapid double-clicks: still exists.
6. Explicit Remove verb deletes; the Undo toast appears; clicking Undo restores the wire
   (business-field-identical row, board re-read, unread pill cycles correctly); final diff vs
   post-repair state clean.
7. Same delete+Undo behaviour on the `System fields → Scheme` board (shared helper, one
   implementation — grep-proof).
8. Letting the toast expire leaves the wire deleted (then restore via the verb + re-wire for
   cleanup; end-state diff clean).
9. Keyboard: Delete on a selected wire (if that path exists) routes through the same
   explicit-verb + Undo path; Enter/double-click never deletes (MF33 family).
10. Suites: self-taken baselines, finish at-or-above, 0 new failures; new hoot tests cover
    "dblclick never calls the delete RPC" and the undo snapshot helper (translation-free, MJ3).
11. Grep gates: no user-visible "Odoo"; new strings translated.
12. Deploy per MAPFIX ritual over abm acme payobook payobook_template; `latest_version` verified
    in psql on all four.

## Report back

The D0 repair record (missing row identified, old→new id, binding state, fingerprints) · what
D1's actual root cause was · per-case results (1–12) · suite tallies · screenshots index ·
deviations with reasoning · new MJ gotchas appended to `JOURNEY_LEDGER.md` (+ a J6 phase-status
entry; STATUS header stays COMPLETE with a defect-round note) · the single commit hash. Do not
push.
