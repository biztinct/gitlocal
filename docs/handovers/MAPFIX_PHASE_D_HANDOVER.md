# MAPFIX Phase D — Mapping canvas: two crashes, three usability defects

Read `docs/handovers/MAPFIX_LEDGER.md` and `docs/handovers/COLROLES_LEDGER.md` FIRST (standing rules;
CR6 chmod + `sudo -u postgres` psql verification per MF17, CR20 park tabs on `about:blank`, MF12
assets rebuild on upgrade not mtime, MF13/CR22 hover affordances that reserve width wreck card
layout — **this phase is largely about that class of bug**).

All five defects were reported by the owner against the LIVE Phase-B board on abm with screenshots.
Two have exact root causes already diagnosed — do not re-derive, verify and fix.

## D1 — CRASH: `'int' object has no attribute 'startswith'` (highest priority)

**Reproduction**: on the Employee/Contract tab, click a component's "Send to a field instead…" verb,
type into the right-hand search, press **Enter** → red dialog, `RPC_ERROR ... builtins.AttributeError`.

**Root cause (verified)**: `ui.focusId` is a SINGLE value shared by both columns
(`mapping_canvas.js` — `onKeydown`, the `case "Enter"` branch ~:1047-1050):
```js
case "Enter":
    ev.preventDefault();
    if (this.ui.focusSide === "left") this.clickLeft(this.ui.focusId);
    else this.clickRight(this.ui.focusId);
    break;
```
The arrow-key branch above it resolves through the focused side's list (`list.findIndex(... focusId)`,
falling back to index 0), but **Enter uses `focusId` raw**. With `focusSide === "right"` while
`focusId` still holds a LEFT id — a `hr.formula.rule` id, an **integer** — `clickRight(123)` sends
`target_spec: 123`. Server-side `employee_mapping_create` (`pb_formula_studio.py` ~:5480) does
`spec = target_spec or ''` — which catches falsy but NOT wrong type, so `123 or ''` is `123` — then
`spec.startswith('b:')` raises.

**Fix, both ends (defence in depth):**
1. **Client**: Enter must act on the item actually focused in the current side's list, i.e. resolve
   `list[idx]` (the same list/idx the arrow keys use) and pass `list[idx].id`; if the resolved item
   is absent, do nothing. Consider also keeping focus per side (`focusLeftId`/`focusRightId`) — if
   you do, migrate every reader; if that is too wide, the resolve-through-list fix alone is
   sufficient and smaller. Justify your choice.
2. **Server**: `employee_mapping_create` coerces defensively — `spec = str(target_spec or '')` — and
   returns a clean `{'ok': False, 'msg': …}` for an unrecognised spec shape instead of raising.
   Audit the sibling RPCs in that family (`employee_mapping_delete`, the suggest/accept paths, and
   the `f:`/`b:` parsing at ~:5503 and ~:5996) for the same raw-`.startswith` assumption.
3. Add a test asserting `employee_mapping_create(config, ctx, rule_id, 123)` returns `ok: False` and
   does not raise.

## D2 — Escape does not clear the armed component

**Reproduction**: arm a component (its card highlights; the banner reads "Click a target component
to connect · Esc to cancel"), press Escape → the highlight stays.

**Root cause (verified)**: Escape inside a column search input is handled first
(`mapping_canvas.js` ~:392):
```js
if (ev.key === "Escape") { ev.stopPropagation(); this.clearSearch(side); }
```
`stopPropagation` means it never reaches the canvas handler whose `case "Escape"` clears
`ui.armedLeft` (~:1052). "Send to a field instead…" focuses that very search box, so in the exact
flow the banner promises Esc will cancel, Esc cannot.

**Fix**: Escape must always disarm, wherever focus is. Suggested precedence: if a component is armed
→ disarm (and clear any in-flight wire preview + the banner); else if the search box has text →
clear the search; else close/deselect as today. Ensure the wire-preview branch (`selWire`, ~:1018)
and the transform editor still cancel correctly. Also make the on-screen banner's "Esc to cancel"
literally true from every focus location — test with focus in the search, on a card, and on the
canvas background.

## D3 — Hover verbs cover the field name

**Reproduction**: hovering a component card shows three pills ("Send to a field instead…",
"Make amount", "Detach component") that **overlay the card's name and code** (owner screenshots 1
and 3). MF13 already moved `.mc-item-acts` to absolute positioning to stop it collapsing card names
at `opacity:0`; that fixed the collapse but the visible state now obscures the content.

**Fix** — this is a design task, not a nudge; the owner asked for "great user experience in
visibility and utility". Constraints: cards are narrow (~300px), three verbs is too many to sit
inline, and the verbs must remain discoverable (a hidden-until-hover-only affordance already proved
fragile twice). Options to weigh — pick ONE and justify:
- a single compact "⋯" trigger on the card opening a small popover menu with the three verbs (keeps
  the card readable at all times; one hover target instead of three);
- a right-side action rail that appears in the card's gutter, outside the text box;
- verbs relocated to a details/inspector strip shown for the selected card only.
Requirements regardless of choice: the card's **name and code stay fully legible at every moment**;
the affordance is reachable by keyboard and has accessible labels; it does not reserve layout width
when hidden (MF13); it does not depend on hover alone (touch/keyboard reachable); and it survives
the narrowest supported canvas width. Re-use the studio's existing menu/popover idiom and design
tokens (indigo family, Lucide-style inline SVG, no emoji) — do not invent a new component if one
exists. **Screenshot before and after at the same viewport width.**

## D4 — Selection fields must show their allowed values

Right-column cards for `ttype == 'selection'` currently show only the label and model, so the user
cannot tell whether their spreadsheet's values will fit. Show the permitted values on the card:
inline when few (e.g. ≤4 short values, comma-joined and truncated with a title/tooltip carrying the
full list), otherwise a count with the full list on hover/expand ("6 values — Married, Single, …").
Read them from the field's selection definition on the model (`self.env[model]._fields[name].selection`,
resolving callables safely; fall back to `ir.model.fields.selection_ids` if that fails) and pass
them through `_ec_field_item`. Labels must be translated user-facing labels, not the technical keys —
but ALSO show the key where it differs, because the import matches on the stored value
(`_coerce_mapped_value` validates against allowed keys and stores `None` on a miss — so a user
seeing only "Married" cannot know the file must say `married`). Keep the payload small: this is
computed for up to 193 cards, so build the selection map once per model per call, not per field.

## D5 — Many2one: make the auto-create behaviour visible (mostly verification)

`_coerce_mapped_value` (`pb_hr_payroll_formula/models/payroll_import_batch.py:1126-1166`) ALREADY
resolves an m2o by name and **creates the record when missing** — but only when the comodel has a
real `name` field; when its identity field is something else (e.g. `res.partner.bank`, whose
`_rec_name` is the account number) it deliberately refuses and logs, storing nothing.

**Do not change that behaviour** — it is correct and deliberate (MAPFIX B1 comment in situ). What is
missing is that the user cannot see it before wiring. Surface it on the right-hand card for m2o
fields: a short note such as "Creates the department if it doesn't exist" for creatable comodels,
and a distinct caution for non-creatable ones ("Must already exist — won't be created"). Derive
creatability with the same rule the batch uses (`'name' in target._fields`) so the UI and the
engine can never disagree; if you find yourself duplicating that predicate, extract it into one
helper the batch also calls.

Add a test asserting: (a) mapping `department_id` to a column with an unseen name creates one
department and links it; (b) a comodel without `name` does not create and the column is skipped with
the value left unset; (c) the UI flag matches the engine's behaviour for both.

## Numbered test cases

1. `employee_mapping_create` with an int `target_spec` → `{'ok': False}`, no traceback.
2. Enter in the right search box after arming a component wires to the focused RIGHT item (or does
   nothing) — never sends a left id. Regression for D1.
3. Enter with focus on the left column still arms/acts as before.
4. Escape disarms from: the search input, a focused card, and the canvas background. Banner clears.
5. Escape with no arm still clears search text (old behaviour preserved).
6. Card name + code fully visible while the action affordance is shown, at the narrowest supported
   width — asserted from live DOM (bounding boxes do not overlap) plus screenshots.
7. Action verbs reachable by keyboard; each has an accessible name.
8. A selection field's card lists its values (or a count + full list on hover); a non-selection card
   is unchanged; payload build is O(models) not O(fields) — assert no N+1 by timing or by counting
   queries on the 193-field abm board.
9. m2o card shows the creates/must-exist note correctly for `department_id` (creatable) and for a
   non-creatable comodel.
10. m2o auto-create end-to-end per D5 (a)(b)(c).
11. Full board still loads with 193 right items and no console errors; both regression batteries
    green (`excel_semantics_battery`, `import_resolution_battery`).

## Deploy + live verification

1. Local: JS parse (`.mjs` copy + `node --check`), XML parse, `npx sass` compile, `py_compile`,
   batteries.
2. Deploy per ledger ritual to **abm acme payobook payobook_template** — chmod, sentinel,
   `sudo -u postgres psql` `latest_version` check on all four (MF17), restart, port bound. Bump both
   touched manifests.
3. Chrome-MCP on **abm** (park other tabs on `about:blank` first — CR20), reproducing the owner's
   exact flow: open the mapping canvas → Employee/Contract tab → a component's action verbs →
   "Send to a field instead…" → type `status` → **press Enter** → assert NO error dialog and correct
   behaviour. Then press Escape and assert the highlight and banner clear. Screenshot each.
   **Leave abm exactly as found** — record and restore anything you change (Phase B's report is the
   model for this).
4. Self-review diff vs spec; ONE feature-scoped commit including ledger + this handover; no push.

## Report back

Per-test results; before/after screenshots for D3 at the same viewport; which D1 client fix you
chose and why; which D3 design you chose and why; the selection-values payload cost on the 193-field
board; what was changed and restored on abm; deviations; MF-numbered gotchas appended; files
touched; manifest versions; commit hash.

---

## Outcome (filled in on delivery, 2026-08-23)

**DONE and live on abm · acme · payobook · payobook_template.**
pb_formula_studio **19.0.1.121.0** · pb_hr_payroll_formula **19.0.1.72.0** (`latest_version`
verified per DB with `sudo -u postgres psql` — MF17).

Decisions the spec left open:

* **D1, client**: the *resolve-through-the-list* fix, not split per-side focus. Splitting
  `focusId` into `focusLeftId`/`focusRightId` would touch the template, both `onWillUpdateProps`
  branches and every reader of `ui.focusId` to remove a mismatch that cannot survive one line of
  resolution anyway. It resolves **strictly** (no index-0 fallback, unlike the arrow keys): moving a
  focus ring is harmless, drawing a wire because nothing was focused is not. `_relocateFocus` —
  called when a search applies — is what keeps "type, then Enter" working: it puts a *visible* focus
  on the top hit, so the card Enter acts on is the card the reader can see.
* **D3**: option 1 of the three offered — **one compact `⋮` trigger + an anchored popover menu**.
  Chosen because it is the only one that can be *proved*: a single FIXED-width (22px) button in the
  flow means the label's width is deterministic, the text ellipsises instead of collapsing, and no
  bounding box ever overlaps another (MF26). A gutter rail would have re-created the variable-width
  problem the moment a fourth verb appeared, and an inspector strip hides the verbs behind a
  selection the reader has not made yet. The trigger is visible at rest (dimmed) — hover-only has
  failed twice — and the menu rows carry a sentence per verb, which three pills on a 300px card
  never had room for.
* **D5**: engine untouched, as instructed. The predicate was extracted to
  `payroll_import_batch.m2o_creates_missing()` / `m2o_resolution_key()` and the batch now calls it
  too, so the card's promise and the import's behaviour are the same line of code.

Numbered cases 1-11: all pass — 9 new Python tests (`pb_formula_studio/tests/test_mapping_defects.py`)
plus the 12 Phase-B ones = **21/21 on abm**, and **41/41 hoot** at
`/web/tests?filter=mapping_canvas` (15 new). Live on abm: the owner's exact flow now completes
("Designation now goes to Marital Status instead of the contract."), Escape disarms from all three
focus locations, 0/19 cards overlap at 1440 **and** at 1024, and the whole-board RPC costs
**132 ms / 69 KB** for 193 cards with 56 notes.

Everything touched on abm was restored: 10 mappings with the original ids
(`1,2,30,31,32,33,35,36,37,38`) and rule 662 `DESIGNATION` back to
`is_contract_component=True, is_text_component=True, column_role='contract', source='auto'`.

New gotchas: **MF24-MF29** in `MAPFIX_LEDGER.md`.
Screenshots: `.mapfix-d-shots/` (before/after at 1440, plus 1024).
