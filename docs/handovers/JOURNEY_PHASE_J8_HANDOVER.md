# JOURNEY Phase J8 — The contract component becomes a visible destination (+ a clipped arrowhead)

**Read first:** `docs/handovers/JOURNEY_LEDGER.md` (J1–J7 outcomes, ALL MJ gotchas MJ1–MJ40),
then `MAPFIX_LEDGER.md` standing rules (deploy ritual, MF11/MF13/MF26/MF37/MF41, CR6/CR18/CR20/
CR21/CR22). **White-label absolute: no user-visible string may say "Odoo"** — not in a label, a
note, a toast, a tooltip, an empty state or a `.po` msgstr. Technical identifiers are untouched.
Branch `19.1`. ONE feature-scoped commit (explicit staging; include the ledger + this handover;
leave `ABM/ABM Template.xlsx` unstaged as found). **`d975e98d` (J6) and `619c92c7` (J7) are
committed but NOT pushed — commit as usual, do not push.**
abm login: `ash@biztinct.com` / `J5validate!2026`. Current: `pb_formula_studio` **19.0.1.151.0**.
Baselines to take yourself (MJ11/MJ14/MJ20): post-J7 Python **436** with the same three
pre-existing reds, hoot **119**.

---

## What the owner asked, and why this phase exists

The owner opened the `Employee & contract ⇆` board looking for where to send **Gas Allowance**,
which they want kept on the contract as a component, and could not find it in the right column.
They asked whether the reason was that the one2many rows "are not created yet".

The diagnosis, already given to the owner and **not to be re-derived**:

- The right column is generated from `ir.model.fields` of `hr.employee` + `hr.contract`, narrowed
  to scalar types by `_EC_TTYPES` — `pb_formula_studio.py:7425`. one2many/many2many are excluded
  *deliberately* ("a spreadsheet cell is not a set of records", the comment at `:7423`). A
  contract component is not a field of the contract at all: it is a row of
  `hr.contract.advantage` pointing at an `hr.contract.advantage.template`, matched by CODE.
  It could therefore never appear there, created or not.
- Gas Allowance **already has** that destination. `is_contract_component = True` on the rule IS
  the wiring; the left card's `Contract component` badge (`:7972-7978`) is the only place the
  board says so.
- Creation timing (verified): the TEMPLATE is created lazily by the first processed import —
  `_get_or_create_advantage_template`, `pb_hr_payroll_formula/models/payroll_import_batch.py:3747`
  (searched by `code`, created if absent, and an existing template's `value_type` is **never**
  flipped, `:3763-3770`). The per-contract LINE is created by `_sync_contract_components`,
  `:3818`, called at step 3 of processing, `:1290`. Separately, once a template exists,
  `hr.contract.create` seeds one EMPTY line per template on every new contract (CR18,
  `om_hr_payroll/models/hr_contract.py:111-113`) — which is why "has lines" proves nothing and
  `_ec_component_history` (`pb_formula_studio.py:8326`) counts only lines with a value in them.
- **abm today: 20 rules flagged `is_contract_component`, 0 templates, 0 lines** (Gas Allowance is
  rule 675 `GASALLOWANCE`; also `PHONEALLOW` 676, `MEALALLOW` 677). Nothing has been processed
  there — `action_process` has been kept off live databases throughout this programme and stays
  off in this one.

So the defect is not a missing mechanism. **It is that the board's single most-used destination
is invisible on the board** — you have to already know what a badge means to know where a value
lands. That is exactly what this surface exists to prevent.

## Scope

**D1 — a `Contract components` lane in the right column, wirable, honest about its state.**
**D2 — the left-column arrowhead is clipped.**

**Binding non-goals.** Do not touch the resolver ladder or its order (J-D5). Do not change what
`_sync_contract_components` writes or when. Do not create advantage templates or lines from this
board — the import remains the only thing that creates them, and the UI's job is to SAY so. Do not
run `action_process` anywhere. No live external API pulls. Do not widen `_EC_TTYPES` — the fix is
a synthetic lane, not a relaxed field predicate. Do not build a second promotion path: the RPCs
below already exist and are live-tested.

---

## D1 — the lane

### Shape

A new lane keyed `contract_component`, placed **between `contract_terms` and `bank`** in
`_EC_LANES` (`:7480-7509`), heading **"Contract components"** (`_ec_lane_label`, `:7572`). It
carries exactly **two synthetic cards**, built the way `_bank_lane_items` builds its four
(`:7545-7569`) and spliced the way `_ec_right_column` splices them (`:7916-7930`):

| id | label | what it says |
|---|---|---|
| `c:amount` | Contract component — amount | Kept on the contract under this column's own code, as a number the pay calculation reads back. |
| `c:text` | Contract component — text | Kept on the contract as text — a grade, a shift code, a note. |

The `c:` prefix follows the `b:` precedent exactly: `employee_mapping_create` tells the id kinds
apart by inspection (`:8258` for `b:`, `:8273` for `f:`), and `_ec_spec` (`:8214`) already
coerces whatever the browser sent to a string. Add the `c:` branch **before** the `f:` parse, and
make an unknown `c:` suffix a refusal via `_ec_bad_spec_msg` (`:8230`), never a traceback.

Two cards rather than one because the value TYPE is a real fork in the model
(`is_text_component`, `hr.contract.advantage.template.value_type`), and choosing it at wire time
is the difference between the board expressing the decision and hiding it.

### Wiring is the existing promotion, reused

`c:amount` → `employee_mapping_make_component(rule_id, 'amount')` (`:8379`).
`c:text` → the same with `'text'`. Both already: refuse a non-`input` column with a sentence
(`:8396`), unlink any existing field/bank mapping row so the column keeps exactly ONE destination
(`:8402-8404`), and set the role per CR-A2 (`:8409`). **Route through them; do not reimplement.**

Wiring *away* — from a component card to a field or a bank card — already demotes, keeps the
history and returns the sentence to show: `_ec_demote_component` (`:8346`). That is the inverse
and it needs no change; the wire simply moves.

### The wires have no mapping row — synthesise them

There is no `hr.payslip.import.mapping` row behind a contract component; the boolean on the rule
is the fact. So `employee_mapping_data` (`:8056`) must emit, for every left card with
`is_contract_component` or `is_text_component`, a wire to `c:amount` / `c:text` alongside the
`em<id>` mapping wires it already builds at `:8067-8074`. Requirements:

- a distinct id namespace (e.g. `cc<rule.id>`) and `kind` — so no client path can hand a rule id
  to `employee_mapping_delete` (`:8460`), which browses `hr.payslip.import.mapping` and would
  unlink a stranger's row;
- **`state: 'accepted'`** and the **⇆ two-way treatment**: these rows genuinely run both ways —
  the import writes the contract, and the pay run reads the component back
  (`payroll_import_batch.py:2870-2886`, resolved source `contract_component`; a flagged rule with
  no line falls back to `0.0` as `contract_component_default`, `:3374-3376`). Give the card the
  same direction sentence J3 gave field wires (`_ec_direction`, `:8119`) — worded for a
  component, not copied verbatim;
- the wire's Remove verb routes to `employee_mapping_detach_component` (`:8424`), which **refuses
  when contracts already carry values** and returns the sentence naming the door that is open
  (`:8450-8454`). Show that refusal; do not swallow it and do not invent a force path;
- Undo (J6's snapshot toast, `api_mapping_restore` family) must cover a successful detach — the
  snapshot is just the two booleans plus `column_role`/`column_role_source`. Re-promote through
  the same RPC. One shared helper, not a second copy (J6's grep-proof rule).

### The card must answer "does this exist yet?"

This is the owner's actual question and the reason the lane earns its place. Each card carries a
live state line, from **at most two queries per board load**:

- **nothing created yet** → "Created on the first import — nothing on any contract yet."
- **live** → "N contracts carry a value." (count lines with a value in them, the
  `_ec_component_history` predicate at `:8340-8343` — never a bare line count, CR18.)

Aggregate over the config's own component codes, in ONE `search` on templates and ONE
`read_group`/`search_count` on lines. **Measure `employee_mapping_data`'s round-trip before and
after and report both**; a regression over ~50ms on abm is a fail — put the counts behind the
same cheapness bar the rest of the board holds to.

### Traps that will bite, stated so you do not have to find them

1. **The promoted card can vanish under the user's own hand.** `make_component('amount')` sets
   `column_role = 'payroll'` (`:8409`), and `_ec_left_items` hides payroll-role cards unless the
   payroll chip is on (`:7960-7961`). Wire Gas Allowance to `c:amount` with that chip off and the
   card disappears the instant it succeeds — which reads as "the board ate my column". Required:
   after a promotion the card stays visible and its new wire is on screen. Reveal it the way the
   board already reveals things (the CR21/F1 clear-the-filter vocabulary), and say what happened;
   do not invent a second reveal mechanism.
2. **Many wires, one card.** abm has 20 flagged rules and can only grow. Twenty curves converging
   on one port is a knot, not a diagram. Distribute the arrival points down the card's edge (a
   comb), or state and implement another rule — **your choice, justified with a measurement at
   1440 and 1024 with the payroll chip ON**. Whatever you choose, the endpoints must obey the
   existing clamp/dock machinery (`clampY`, `aggregateDocks`) rather than a parallel one.
3. **Text↔amount is not freely reversible once data exists.** An existing template's `value_type`
   is never flipped (`payroll_import_batch.py:3763-3770`) — it only logs a warning, server-side,
   where no user will ever see it. If a template already exists for that code with the OTHER
   type, the board must say so at wire time, in the caution tone, instead of accepting a wire
   whose promise the import will quietly decline.
4. Every new card goes through the same construction invariant `_ec_field_item` carries
   (`:7811-7823`): a card rendered on the right has the metadata it would have had from the
   catalogue. The two synthetic cards are not fields — give them the equivalent, and make
   `test_02`'s whole-board assertion pass with them present.
5. `_ec_wire_right_id` (`:8025`) maps a persisted mapping to a right-card id. Component wires do
   not go through it; make sure nothing assumes every wire in the payload does.
6. `_ec_unresolved` (`:8491`) already treats a contract component as resolved (`:8479`) — check
   the counts and the "N unresolved" copy still read correctly once components are visibly wired,
   and that the role-count chips (`_ec_role_counts`, `:8157`) do not double-count.

---

## D2 — the left-column arrowhead is clipped

Owner screenshot (`Employee & contract ⇆`, 21 columns, left column scrolled): the ◀ heads
arriving at SHUI Participation / TU Participation / Department are cut — only part of each
triangle is painted.

Verified facts, do not re-derive:

- The wire's source x is **the first visible CARD's right edge**, not the column's:
  `mapping_canvas.js:326` sets `edge = r.right - rb.left` from a card rect, and `:426` sets
  `sx = L.edge + 4`.
- The bidi back-head is a hand-placed triangle spanning `sx` → `sx + HEAD` with `HEAD = 11`,
  `HEAD_H = 6` (`mapping_geometry.js:23-25`, `:58-60`).
- `.mc-col-body` has `padding: 4px 14px 20px` and `overflow-y: auto`
  (`mapping.scss:148`) — so ~14px of padding plus a scrollbar gutter sit to the right of a card,
  and the head is drawn INTO that band.
- `.mc-wires` is `z-index: 1`; `.mc-cols` is `z-index: 2` (`mapping.scss:54`, `:89`). The SVG is
  **behind** the columns. Anything opaque in that band paints over the head.

That is the hypothesis, not the finding — **measure it and report which of the two it actually is**
(occluded by the column layer, or clipped by `.mc-board`'s `overflow: clip` at `:47-51`), then fix
it at the cause. Constraints: the fix must not move `sx` in a way that shifts wire geometry
(MJ30 — a 49.75px coordinate-space slip painted every wire wrong for four phases, and MJ12's SVG
exclusion is why no sweep saw it); re-run J6's wire-measurement harness and report `maxErr` at
1440 and 1024. Applies to **both** columns and both heads, at every scroll and filter state, and
to the transform board if it shares the cause.

**And make the sweep catch this class.** J7 rebuilt `tools/mapping_overlap_sweep.js` with a named
closed list of user-openable layers (MJ38) but SVG is still outside it (MJ12). An arrowhead is
content. Add a permanent assertion that no wire head is occluded or clipped, in either column —
say what you added and why it could not have fired before.

---

## Safety rails

- MF37 oracle on abm: fingerprint `hr_integration_field_mapping`, `hr_payslip_import_mapping`,
  and `hr_formula_rule` (`is_contract_component`, `is_text_component`, `column_role`,
  `column_role_source` for config 14) before and after. This phase's live probes DO write — every
  promotion/detach in a test must be reversed, and the closing diff must be clean against the
  post-J7 baseline. **Record abm's 20 flagged rule ids before you start**, and prove those exact
  20 are the flagged set at the end.
- `hr_contract_advantage_template` and `hr_contract_advantage` must both still be **0 rows on abm**
  when you finish. If either is non-zero, something created contract data from a mapping board and
  that is a defect of this phase, not a side effect.
- NEVER `action_process`. No live external pulls. MJ2 warm the server before believing a red hoot
  run; MJ6 bump the version after late asset edits; MJ13 assert `innerWidth`; MJ23 size probe
  waits to round-trips; MJ39 include coordinates in any signature that decides re-placement.
- Screenshots to `.journey-shots/J8/`.

## Numbered test cases (abm; all pass before commit)

1. Reproduce first: the owner's state (`Employee & contract ⇆`, Gas Allowance visible with the
   payroll chip on) — "before" shot showing no contract-component destination, and a shot of the
   clipped left arrowheads.
2. The lane renders between Contract terms and Bank account, in both columns' orders, with both
   cards, at 1440 and 1024; group headers still emit once per consecutive run (`_ec_place_in_lane`
   precedent, MAPFIX E2).
3. abm's 20 flagged rules each draw a component wire to the right card matching their type; the
   left badge and the wire agree for all 20 (assert programmatically, not by eye).
4. Wire Gas Allowance to `c:amount` by mouse from a cold board: the promotion succeeds, the card
   **stays visible**, its wire is on screen, and the toast says what happened. Reverse it and
   diff clean.
5. Detach through the wire's Remove verb: Undo restores the exact prior state (both booleans +
   role + role source). Letting the toast expire leaves it detached; re-promote to clean up.
6. Detach refusal: with a template and a filled line present (**build this in a scratch database,
   never on abm**), the refusal sentence shows and nothing is written.
7. Type-conflict caution: a code whose template already exists as the other type is refused or
   warned at wire time — again in a scratch database — and the sentence names what will actually
   happen.
8. The card state line is right in both states: "created on the first import" on abm (0 templates)
   and "N contracts carry a value" in the scratch database. Report the measured
   `employee_mapping_data` round-trip before and after.
9. Density: 20 wires into one card at 1440 and 1024 — the rule you chose holds, 0 overlaps over
   the full corrected sweep, docks still aggregate correctly.
10. D2: no wire head clipped or occluded in either column, at 1440 and 1024, across ≥4
    scroll/filter states, asserted by the extended sweep; `maxErr` reported at both viewports and
    unchanged from J7's zero.
11. Two-way: component wires carry the ⇆ treatment and a direction sentence that is true for a
    component (import writes it, pay run reads it back); the transform board and the Journey view
    still agree with the board about which columns are components.
12. Suites: self-taken baselines, finish at or above with new tests on top, 0 new failures. New
    hoot tests cover the lane splice, the `c:` spec parse, the never-vanishing card, and the
    arrowhead assertion as pure/DOM facts, translation-free (MJ3).
13. Grep gates: no user-visible "Odoo" anywhere added; every new string translated.
14. MF37: closing diffs clean; the two advantage tables still 0 rows on abm.
15. Deploy per the MAPFIX ritual over `abm acme payobook payobook_template`; `latest_version`
    verified in psql on all four; service up at the end.

## Report back

D1's shape as built (and any deviation from the two-card design, with reasoning) · which of the
two D2 causes it actually was · the density rule you chose and its measurements · the sweep
assertion you added and why it could not have fired before · per-case results (1–15) · `maxErr`
numbers · the `employee_mapping_data` timing before/after · suite tallies against your own
baselines · MF37 diffs including the two advantage-table counts · screenshots index (before +
after) · new MJ gotchas appended to `JOURNEY_LEDGER.md` (+ a J8 phase entry; STATUS stays COMPLETE
with the defect-round note extended to J8) · the single commit hash. **Do not push.**
