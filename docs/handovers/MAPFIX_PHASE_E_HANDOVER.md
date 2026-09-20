# MAPFIX Phase E — Selection values: see all of them, and see them at all

> **BUILT AND LIVE (2026-08-23) — pb_formula_studio 19.0.1.124.0 on abm · acme · payobook ·
> payobook_template.** Outcome against this spec, so the next reader does not have to diff it:
>
> * **E2's verdict**: `hr.employee.employee_type` fails `_ec_is_mappable` on the **`store`** clause,
>   not `readonly`. Odoo 19 delegates hr.employee to `hr.version` (`_inherits`), so it is a RELATED,
>   non-stored, perfectly writable field (MF30). The handover's option 1(a) was right about the
>   shape — the predicate was too strict — and wrong about which clause. Fixed at the predicate.
>   Catalogue **193 → 236** (hr.employee 133→173, hr.contract 56→59, bank 4); **nothing was lost**.
> * The card the owner photographed was in fact `hr.employee.org_employee_type` (om_hr_payroll, a
>   **Char** also labelled "Employee Type", wired as mapping 52) — which correctly has no values.
>   The real `employee_type` was absent entirely, which is the same defect seen from the other side:
>   the six-value selection could not be reached at all. Both now read correctly.
> * **No live mapping on abm targets a non-mappable field**, so E2(3)'s `warn` card has no live
>   instance; it is asserted by `test_03`, which wires `active` (deny-listed but writable). It
>   DOES have one on **payobook** — mapping 16 → `hr.contract.active` — which now renders warned.
> * **A defect this spec did not anticipate** was found live and fixed: Enter on the new note ALSO
>   reached the board's own `case "Enter"` and wired a column (MF33). The `⋮` trigger had the same
>   latent bug since Phase D.
> * Test results, payload delta and screenshots are in the Phase E report; gotchas MF30–MF37 are in
>   `MAPFIX_LEDGER.md`.


Read `docs/handovers/MAPFIX_LEDGER.md` and `docs/handovers/COLROLES_LEDGER.md` FIRST. Operationally:
CR6 + MF17 (chmod after rsync; verify `latest_version` with `sudo -u postgres psql`), CR20 (park
browser tabs on `about:blank` before stopping the service), MF12 (assets rebuild on upgrade),
MF13/CR22/MF26 (affordances that reserve width wreck these cards — this phase adds another one, so
measure it).

Two defects reported by the owner against the live Phase-D board on abm, with screenshots.

## E1 — A truncated value list must be openable

**Reproduction**: the `Status` card (hr.contract) reads `4 values — New, Running, Expired, …`. The
full list exists only in the `title` tooltip, which is slow, un-selectable, cut off by the viewport,
and invisible on touch.

Phase D deliberately caps the inline text (`_EC_SEL_INLINE_MAX = 4`, `_EC_SEL_INLINE_CHARS = 44`,
`_ec_selection_note` ~:5250-5294) — that cap is correct and stays. What is missing is a way to open
the rest.

**Build**: make the note itself the affordance when it is truncated. Clicking it opens a small
popover listing **every** permitted value, one per line, showing the label and — where they differ —
the **stored code**, because the code is what the spreadsheet must literally contain
(`_coerce_mapped_value` validates against the keys and stores `None` on a miss).

Requirements:
- **Reuse the Phase-D popover** built for the `⋮` card menu (`mapping_canvas.js`/`.xml`, the
  measured-after-render placement from MF27 — a popover cannot be placed from an estimated height).
  Do not write a second popover implementation.
- Opening it must NOT wire anything: the note lives inside a card whose `t-on-click` calls
  `clickRight(it.id)` — stop propagation, or the act of reading the values maps the column.
  **Test this explicitly**; it is the obvious way to ship a bug.
- Keyboard reachable, `aria-expanded`, Escape closes and returns focus — matching the `⋮` menu's
  behaviour. Escape here must not also disarm a component (Phase D's D2 precedence: innermost
  dismissable first).
- Long lists scroll inside the popover; the popover never forces the card or column to grow, and it
  must not reserve layout width when closed (MF13).
- Only truncated notes are clickable; a note already showing every value stays inert text (no
  affordance that does nothing).
- Values are already in the payload's `title` — reuse or extend that rather than adding an RPC; if
  you extend `_ec_selection_note` to also emit a structured `values: [{key, label}]`, keep the
  payload increase modest (the board carries 24 selection cards; measure the delta and report it).

## E2 — Some selection cards show no values at all

**Reproduction**: `Employee Type` (hr.employee, wired) shows label + model and NO values, while
`Vietnam Contract Type` (hr.contract, unwired) on the same screen lists its four. The owner proved
via the form tooltip that `hr.employee.employee_type` IS a selection with six values
(employee/worker/student/trainee/contractor/freelance).

**Root cause (diagnosed — verify, then fix):** there are TWO places that build a right-hand card and
they disagree.
- The catalogue path `_ec_right_items` (~:5388-5406) filters every field through
  `_ec_is_mappable(model, fname)` and passes a per-model `notes` dict.
- The keep-a-wired-field-visible path inside `employee_mapping_data` (~:5549-5554) does **not**:
```python
if rid not in present:
    fld = self.env['ir.model.fields'].sudo().search([...], limit=1)
    if fld:
        right.append(self._ec_field_item(fld))     # no lane, no lane_order, no notes
```
`_ec_field_item` falls back to `self._ec_notes_for(fld.model)` when `notes is None`, but
**`_ec_notes_for` itself gates on `_ec_is_mappable`** (~:5333-5335). So any wired field that fails
the mappability predicate is rendered as a card whose note lookup misses — a card with no values —
while an identical unwired field is simply absent from the board.

**What to do:**
1. **Determine the truth about `hr.employee.employee_type` on this build**: does it fail
   `_ec_is_mappable`, and on which clause (`store`, `readonly`, `_EC_TTYPES`, deny-list)? Report the
   answer explicitly — it decides the rest.
   - If it fails on `readonly` while actually being writable (a plausible `ir.model.fields` vs
     registry drift — note the domain at :5389-5390 reads `ir.model.fields.readonly` while
     `_ec_is_mappable` reads `field.readonly`; they can disagree), then the predicate is too strict
     and the fix is to the predicate — which will also reveal other legitimately-mappable fields.
     Report how many cards the catalogue gains, per model, so the change is visible.
   - If it is genuinely not mappable, then it must not be offered at all — and the existing wire to
     it is a mapping that cannot work, so surface that rather than hide it (see 3).
2. **One construction site.** Make the wired-append path go through the same predicate and the same
   note-building as the catalogue path. The invariant to establish, and to assert in a test: *every
   card rendered on the right carries the same metadata it would have if it had come from the
   catalogue* — lane, lane_order and note included. Today the appended card also gets no lane, which
   is why such cards land in the fallback group by accident rather than by decision.
3. **A wire to a non-mappable field must not be silent.** If a mapping exists whose target the
   catalogue would refuse, keep the card visible (losing it would hide a live mapping) but mark it —
   a `warn`-toned note saying the destination cannot be written and the mapping should be re-pointed.
   Reuse the existing `tone: 'warn'` note styling from `_ec_m2o_note`.
4. Check the same drift in `ec_model_fields` (~:5604-5626) and `ec_search_fields` (~:5596-5602) —
   they already share the predicate, but confirm rather than assume.

## Numbered test cases

1. `_ec_notes_for('hr.employee')` contains `employee_type` (post-fix), with all six values.
2. Every item returned by `employee_mapping_data(...)['right']` has a `lane`, a `lane_order`, and —
   for selection/many2one fields — a note. Assert over the whole live-shaped board, not a sample.
   This is the E2 invariant.
3. A wired mapping whose target fails the catalogue predicate still renders, carries a `warn` note,
   and is not silently dropped.
4. Catalogue counts per model before/after the predicate fix (record both; a large jump needs an
   explanation in the report, a zero jump means the diagnosis was wrong — say so).
5. Clicking a truncated note opens the popover and **does not create a mapping** (assert wire count
   unchanged and no RPC to `employee_mapping_create`).
6. The popover lists every value with label and stored code; scrolls when long; Escape closes it and
   does not disarm an armed component; focus returns to the trigger.
7. A non-truncated note is not clickable and exposes no button semantics.
8. Card name and code remain fully legible with the new affordance present — 0 bounding-box overlaps
   across all cards at 1440 and 1024 (the Phase-D measurement, re-run).
9. Payload delta for the 193-card board with structured values included — report ms and KB against
   Phase D's 132 ms / 69 KB.
10. Both regression batteries green; existing Phase-B/C/D suites still green (21 Python, 41 hoot).

## Deploy + live verification

1. Local: JS parse (`.mjs` + `node --check`), XML parse, `npx sass`, `py_compile`, both batteries.
2. Deploy per ledger ritual to **abm acme payobook payobook_template**; chmod; `sudo -u postgres
   psql` version check on all four; restart; port bound. Bump touched manifests.
3. Chrome-MCP on **abm** (park other tabs on `about:blank` first):
   - screenshot the `Status` card, click its note, screenshot the open popover showing all 4 values
     with codes;
   - screenshot `Employee Type` now showing its six values (the owner's exact defect);
   - re-run the overlap measurement and report the number.
   - **Leave abm exactly as found** — record and restore anything wired/unwired, as Phases B and D did.
4. Self-review vs spec; ONE feature-scoped commit including ledger + this handover; no push.

## Report back

The `_ec_is_mappable` verdict for `employee_type` and which clause decided it; catalogue counts
before/after per model; per-test results; payload delta; screenshots; what was changed and restored
on abm; deviations; MF-numbered gotchas; files touched; manifest versions; commit hash.
