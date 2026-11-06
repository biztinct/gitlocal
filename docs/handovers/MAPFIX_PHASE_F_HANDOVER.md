# MAPFIX Phase F — A filter that hides its wires, a lane that keeps its field, a create that checks

> **OUTCOME (2026-08-23): BUILT, DEPLOYED, VALIDATED.** pb_formula_studio **19.0.1.126.0** live on
> abm · acme · payobook · payobook_template. All ten numbered cases pass. Python 63/63 on abm (5 new
> in `TestMappingCreateGuard`), hoot 60/60 at `/web/tests?filter=mapping_canvas` (12 new). abm left
> exactly as found — `hr_payslip_import_mapping` and `hr_formula_rule` both diff clean before/after
> (MF37's oracle). Ledger updated: MF35's deploy ritual corrected in place, MF36 closed, MF38–MF41
> appended. NOT pushed.
>
> Live numbers on the Bank lane pill: 1 wire drawn, 16 counted, 1 + 16 = 17 = the unfiltered total;
> chips "5 hidden by filter above" + "11 hidden by filter below"; `clear` restores all 17.
> Two items to know about: **MF39** — the reveal bar is now effectively unreachable and was kept
> deliberately; **MF40** — F2's UI path is not reachable in today's product because the served
> catalogue is complete, so the fix is correct and latent (validated by driving `addEmpField` live).


Read `docs/handovers/MAPFIX_LEDGER.md` and `docs/handovers/COLROLES_LEDGER.md` FIRST.
Operationally: CR6 + MF17 (chmod after rsync; verify `latest_version` with `sudo -u postgres psql`),
**MF35** (the ledger's deploy ritual is missing `sudo -u odoo` — `systemd-run` runs as root; fix the
ledger text while you are in there), CR20 (park browser tabs on `about:blank` before stopping the
service), MF12 (assets rebuild on upgrade), MF13/CR22/MF26 (card affordances and layout), **MF37**
(patching `window.fetch` cannot observe Odoo RPCs — the oracle for "did the board write anything"
must be the DATABASE; Phase E lost a mapping to this and had to restore it).

Three items: one owner-reported visual defect, plus the two follow-ups Phase E deliberately left
(MF36), which the owner has now asked to close.

**Note**: since Phase E the branch is PUSHED (`origin/19.1`, through `15071c57`). Commit as usual;
the owner will say when to push again — do not push.

## F1 — Filtered-out wires must not hang off the edges (owner-reported)

**Reproduction**: on the Employee/Contract tab, click a lane pill (e.g. **Bank**). The left column
correctly narrows to Bank Name and its wire renders. But wires belonging to components the filter
removed are still drawn, docking at the top and bottom edges of the canvas as arrows that point at
nothing. The owner: *"these extra arrows hang at the top and/or bottom … no need to show these
hanging arrows as they do not belong to the filtered components."*

**Why it happens (design, not accident)**: CR21 (Phase B) made lane filtering a canvas prop
(`groupFilter`) applied inside `_passes` rather than trimming the item array, precisely so a wire
whose end is filtered **docks** at the column edge instead of counting as `gone`. That docking is
RIGHT for **scrolling** — the "↑ 8 mapped above" affordance tells you a connection exists just off
screen — and WRONG for **filtering**, where the user has explicitly said "show me only these".

**The distinction to implement**: *scrolled out of view* ≠ *filtered out of the set*.
- A wire whose endpoint is merely **scrolled** past keeps today's docking behaviour, unchanged.
- A wire with **either** endpoint excluded by an active filter (lane pill, All/Mapped/Unmapped
  toggle, or the search box, on **either** column) is **not drawn at all**.
- The existing counters stay and become the explanation: the column header's "N wires hidden by this
  filter" with its `clear` link, and the `N hidden by filter above/below` pills. Verify those counts
  now agree exactly with the number of wires actually suppressed — today the count and the drawing
  can disagree, which is the underlying inconsistency. Make one predicate answer both.

Implementation notes: `mapping_canvas.js` — `_passes` (~:95 area, per-side filter state `f.left`/
`f.right`), the geometry builder (`ui.geom`) and `hiddenWires(side)`. Introduce one helper (e.g.
`isFilteredOut(side, id)`) used by the geometry filter AND the counter, so they cannot drift.
Do not regress: wire selection (`w` key walking, `selWire`, `jumpTo`) must skip suppressed wires
rather than selecting an invisible one.

## F2 — A field added mid-session lands in its lane (MF36)

A field brought onto the board from the search box during a session (`mapEmpRight`-style client-side
append) is pushed to the **end** of the right column instead of into its lane, so the lane headers
briefly stop telling the truth. Insert it at its lane position instead — the server already returns
`lane`/`lane_order` on every item (Phase E made that an invariant), so this is an insertion-index
problem, not a data problem. If a session-added field belongs to a lane not currently rendered, render
that lane header too.

## F3 — `employee_mapping_create` applies the catalogue predicate (MF36; owner approved)

The board refuses to OFFER a destination that fails `_ec_is_mappable`, but the create RPC never
re-checks — so a wire can still be made through the search box, a stale board, or a direct RPC.
Close it: apply the same predicate server-side in `employee_mapping_create` before writing, and
refuse with a clear sentence naming the field and why it cannot receive a value. Reuse
`_ec_bad_spec_msg`-style wording; do not invent a second refusal vocabulary.

Two cautions:
- **Do not break existing rows.** Mappings created before this guard may point at fields the
  predicate now refuses; they must keep loading and keep rendering with the Phase-E `warn` note.
  The guard governs CREATE only, never READ. (The owner has already deleted the one live instance —
  payobook mapping 16 → `hr.contract.active`, which had no component at all — so there may be no
  live example left; assert the behaviour with a test rather than looking for one.)
- The bank lane (`b:` specs) does not go through `_ec_is_mappable` at all and must not start to.

## Numbered test cases

1. With a lane filter active, `ui.geom` contains no wire whose either endpoint is filtered out; with
   no filter, geometry is unchanged (count equality against the pre-filter set).
2. A wire whose endpoint is only SCROLLED out still renders and still docks (the "N mapped above"
   behaviour is preserved) — assert distinctly from case 1.
3. "N wires hidden by this filter" equals exactly the number suppressed by case 1, for: a lane pill,
   the Mapped/Unmapped toggle, a search term, and a combination of all three.
4. `clear` restores every wire.
5. `w`-key wire walking and `selWire` never select a suppressed wire.
6. A field added from the search mid-session appears at its lane position with the correct lane
   header, not at the column end (F2).
7. `employee_mapping_create` refuses a target failing `_ec_is_mappable`, with a readable message and
   no row written (F3).
8. `employee_mapping_create` still accepts every `b:` bank spec (F3 caution 2).
9. An existing mapping row pointing at a now-refused field still loads, renders, and carries the
   `warn` note — READ is unaffected (F3 caution 1).
10. Regression: Phase D/E suites green (Python and hoot), both batteries green, board still loads 236
    right items with no console errors, 0 bounding-box overlaps at 1440 and 1024.

## Deploy + live verification

1. Local: JS parse (`.mjs` + `node --check`), XML parse, `npx sass`, `py_compile`, both batteries.
2. Deploy per ledger ritual (with the MF35 `sudo -u odoo` correction) to **abm acme payobook
   payobook_template**; chmod; `sudo -u postgres psql` version check on all four; restart; port bound.
3. Chrome-MCP on **abm** (park other tabs on `about:blank` first): click the **Bank** lane pill and
   screenshot — no hanging arrows top or bottom, counter agrees; then a search filter, same check;
   then `clear` and confirm every wire returns. Screenshot F2's lane insertion.
   **Leave abm exactly as found.** Per MF37 the oracle is the DATABASE: record
   `SELECT id, component_id, target_model_id, target_field_id FROM hr_payslip_import_mapping WHERE
   salary_structure_id = <abm config>` before and after, and diff. Restore anything that moved.
4. Self-review vs spec; ONE feature-scoped commit including ledger + this handover; **do not push**.
5. While in the ledger: correct the deploy ritual to include `sudo -u odoo` (MF35).

## Report back

Per-test results; before/after screenshots for F1 (Bank pill) and F2; the before/after mapping-table
diff for abm proving nothing was written; deviations; MF-numbered gotchas; files touched; manifest
versions; commit hash.
