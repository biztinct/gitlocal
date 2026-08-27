# NETROLE Phase 4 — the Source Atlas: every number's journey, on one screen

Program: NETROLE. Phase 4 of 4. New module `pb_source_atlas`.
Read `docs/FORMULA_ENGINE_CONVENTIONS.md` C1, C2, C7, C8, C10, C11 and
CLAUDE.md's deploy contract first. This is a flagship WOW surface — the design
mandate applies in full: Lucide/SVG icons (never emoji), the locked Payobook
palette (white + rail hero, no gradients), Chrome-MCP validation of edge cases.

## What the owner asked for (their words, distilled)

"An out-of-the-world, intuitive way to explore ALL the sources feeding payroll
— Integration feeds / Excel / Payobook record fields / contract components —
on screen, plus Excel downloads of each feed / excel / record data used in the
calculation, for all employees a payroll was calculated from."

## The data is ALREADY there — do NOT invent a second lineage

The SOURCING programme made every computed payslip carry its own provenance:

- `hr.payslip.formula_input_values` — JSON `{code: value}` per slip.
- `hr.payslip.formula_input_sources` — JSON `{code: {src, key, via}}` per slip,
  written by both compute paths
  ([hr_payslip_formula.py:128-131](../../pb_hr_payroll_formula/models/hr_payslip_formula.py#L128)
  and the batch path). Vocabulary (fixed, 8 sources × vias) in
  [input_provenance.py](../../pb_hr_payroll_formula/models/input_provenance.py):
  `excel, feed, rule, contract_component, employee_field, calculated,
  constant, none`.
- Raw material per lane:
  - feeds → `hr.api.data.store` rows (`connector_id`, `data_type`,
    `employee_external_id`, `employee_id`, `period_from/to`, `state`,
    `get_mappable_data()`).
  - excel → `hr.payroll.import.line.raw_data_json` / `get_raw_data()`
    ([payroll_import_line.py:31,143](../../pb_hr_payroll_formula/models/payroll_import_line.py#L31));
    the line links slip + batch; batch links run (`payslip_run_id`).
  - record fields / contract components → provenance `key` names the field or
    component; read live off employee/contract.
  - formula chain → `hr.formula.rule` dependencies (Phase 1's parser/graph is
    in `formula_net_role.py` — REUSE its graph builder for the journey view;
    do not write a third formula parser).
- Precedent cockpit to clone for structure (client action, orm.call, lens
  switcher, SQL-backed aggregates, per C8 never ORM-iterate 100k lines):
  `pb_explorer` — action XML
  [pb_explorer/views/pb_explorer_action.xml](../../pb_explorer/views/pb_explorer_action.xml),
  registration `registry.category("actions").add(...)` at
  [explorer.js:499](../../pb_explorer/static/src/js/explorer.js#L499).
  Kit styling: `pb_import_kit` (`@pb_import_kit/js/...` import gotcha — the
  asset path prefix matters, see memory of Import redesign).
- XLSX: `xlsxwriter` is installed and used by
  [om_hr_payroll/models/hr_payslip.py:1261](../../om_hr_payroll/models/hr_payslip.py#L1261)
  (`action_download_payslip_xlsx` returns an attachment-download action —
  clone that mechanism, not a controller).

## The experience (design intent — you own the pixels, honour the system)

One client action, `pb_source_atlas`, opened from a "Where the numbers come
from" button on the pay-run form (inherit `om_hr_payroll.hr_payslip_run_form`,
priority above pb_payruns' 30) and a matching entry on the Pay Runs board card
(small, secondary). Context: the run.

Three connected views, one state:

1. **Lanes** (landing): one card per source lane — Connected system,
   Spreadsheet, Payobook records, Contract components, Scheme constants,
   Fallbacks/none. Each card: Lucide icon, component count, employee coverage
   bar (how many of the run's employees got ≥1 value from this lane), the
   lane's total ₫ contribution where meaningful, and a Download XLSX button.
   A lane with zero use renders muted, not hidden — absence is information.
2. **Grid**: employees × components matrix, cells tinted by source lane
   (the locked palette's tints; legend fixed top-right). Column headers group
   by the component's category band. Virtualised/windowed rows (the demo DB
   has 900-employee runs; render ≤ ~40 rows in DOM, search + jump). Click any
   cell → the Journey flyout.
3. **Journey** (the wow): right-side flyout for one employee × component:
   value at top, then the chain drawn as a vertical flow — source row (the
   actual feed key/excel header + raw value + when it was pulled/imported) →
   transformation rule if any (via='rule') → the component → every formula hop
   to NETPAY (from the Phase-1 graph, each hop showing code, formula snippet,
   sign badge + / −). Sign badges reuse net_role colours (earning/deduction).
   Each hop is clickable → re-anchors the journey on that component.

Downloads (server-side xlsxwriter, one method per lane + "everything"):
- Feeds lane: the `hr.api.data.store` rows the run's period/connector actually
  used (mappable keys as columns).
- Spreadsheet lane: the batch's raw rows re-materialised (one sheet per batch).
- Records lane: employee × the record fields/contract components referenced.
- Matrix: employees × components with a second sheet "Sources" holding the
  per-cell lane string. Filenames: `<run name> — <lane>.xlsx`.

Empty states matter: a run with no computed slips explains itself and offers
the Run Payroll action; a slip with no provenance (pre-SOURCING history) shows
"computed before source tracking existed" rather than blanks.

## Server design

New module `pb_source_atlas` (depends: `web`, `om_hr_payroll`,
`pb_hr_payroll_formula`, `pb_payruns`, `pb_import_kit`). AbstractModel
`pb.source.atlas` with `@api.model` endpoints:
- `get_run_atlas(run_id)` → lanes summary + component list (code, name,
  category, net_role, lane histogram). ONE pass over slips' JSON blobs
  (json.loads per slip, 152–900 slips is fine; do NOT per-cell RPC).
- `get_grid(run_id, offset, limit, search)` → windowed rows
  `{employee, cells: [{code, value, lane}]}`.
- `get_journey(run_id, slip_id, code)` → the chain described above.
- `download_lane(run_id, lane)` → attachment action (xlsxwriter).
Access: payroll officer group and up (mirror the group the pay-run form
already requires); sudo() nothing user-scoped without a reason.

## Non-goals

- No writes to any payroll data — the Atlas is strictly read-only (enforce:
  no endpoint mutates; test proves by row counts).
- No new lineage capture — if provenance is missing, say so, don't recompute.
- Not a general BI tool: one run at a time, no cross-run charts (pb_explorer
  owns analytics).
- Do not touch pb_explorer.

## Tests (`pb_source_atlas/tests/test_atlas.py`) — numbered

1. Atlas over a run whose slips carry provenance JSON: lanes count correctly
   per the vocabulary (fixture writes formula_input_sources directly).
2. Grid windowing: offset/limit honoured; search narrows by employee name.
3. Journey for an excel-sourced value includes the raw header key and at least
   one formula hop ending at the NET rule (build the mini-scheme like Phase 1's
   tests do).
4. Journey for a `none`-sourced value says fallback, no invented hops.
5. Pre-SOURCING slip (empty JSON) → explicit "no provenance" flag, no crash.
6. Each download returns an `ir.actions.act_url`/attachment action and the
   workbook opens (openpyxl round-trip in test) with the expected sheet names.
7. Read-only proof: row counts of payslip/line/store/batch tables identical
   before and after every endpoint.
8. A user without the officer group is refused.

## Delivery

Deploy + install (`-i pb_source_atlas`) on all four DBs, asset purge per DB,
restart. Validate on live ABM run 13 (152 slips with real provenance from the
June run): screenshot Lanes, Grid, one Journey (a NETPAY cell and one
attendance-fed component like ACTUWORKHOUR), and one download opened. Chrome
MCP has standing approval; if the server is down, restart it per memory —
only fall back to JSON-RPC evidence if it truly cannot run, and say so.

Version: new module `19.0.1.0.0`. Commits per feature (server core / UI /
downloads acceptable as one if built together — keep it to ≤2 commits),
explicit staging, no push.

## Report back

Lane counts + coverage on ABM run 13 (real numbers), screenshots, test counts
+ EXITs, per-DB install EXITs, any provenance vocabulary values found in the
wild that the handover didn't list, deviations.
