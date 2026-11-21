# Mapping design implementation — 16 October 2026

The approved Connection desk is implemented in the payroll application. The design review HTML remains a separate prototype.

## What changed

- **Connections** is the default. Searchable component rows show every configured source with a numbered priority. A detail panel separates Sources, Storage, and Use in payroll.
- **Source order** opens a scheme-wide review before Save. Only the lane order changes; disabled lanes stay disabled and the pay-period fallback stays last. Preview values and historical run provenance are separate facts. Zero and False remain supplied values.
- **Text and amount components** remain first-class choices. New components stay drafts until Save. Storage promotion retains existing source connections and uses the existing type-clash checks. Value type and pay role remain separate settings.
- **Component links** narrow the appropriate side of the specialist mapping board. System and spreadsheet boards focus the destination; employee/contract mappings focus the component on the source side. Searches can be cleared normally.
- **Transformations** use four navigable steps: Data, Filter, Calculate, Name & connect. Show all steps retains the experienced-user workflow. The proof rail distinguishes received rows, illustrations, missing data, and preview errors. An unverified fallback is not presented as a verified result.
- **Save & connect** is optional and available only with existing mapping-edit permissions. The destination and replacement effect are reviewed explicitly. Rule saving and connection creation share one transaction, including rollback on failure. Spreadsheet and record fallbacks remain.
- **Journey** stays last among the three primary tabs and remains the full holistic view. Trace this component mounts the same Journey component with its existing component filter.

## Arrow preservation

The implementation does not change `journey_board.js`, `journey_board.xml`, `journey.scss`, or `mapping_geometry.js`. The same payload direction drives the same renderer. One-way links have one arrowhead; two-way links have a second head. Curves still leave and arrive horizontally at the measured card/row anchors. Folded cards, bundles, hover/pin tracing, scroll docking, and lane visibility remain in that renderer.

## Existing capabilities retained

Tools retains system-field mappings, spreadsheet mappings, employee and contract read/write mappings, workforce assignment, cycle carryover, and component treatment. Their existing suggestion review, confidence threshold, vendor templates, saved templates, file replacement/download/import handoff, field catalogues, conflict decisions, reconciliation, grouping, and advanced canvas remain reachable.

The existing transformation composer retains vendor and general recipes, natural-language drafting, nested rows, all/any conditions, operators, sum/count/average/minimum/maximum, units, additive fields, formulas, run operands, date calculations, advanced read-only rules, provenance, and unsaved-draft handling. The execution engine is reused.

## Verification and deployment

Runtime source commit: `f673edeffea3cdb1e8fc6b8cd533cfe36a62324a` (the complete commit is recorded in the deployment receipt). Feature implementation began at `ac8a4993a`; subsequent fixes include `d581f3f10`, `4c5cb5f6f`, `ba85f2fef`, and `0bbe1b971`.

The latest combined custom-module state was deployed to Payobook19v2: **p0clone, payobook, rize, payobook_template, and abm**. All 149 custom modules / 4,813 files match the deployment manifest. Installed versions are `pb_formula_studio` 19.0.1.201.26 and `pb_integrations` 19.0.1.14.6.

Each database passed **69 selected server tests: 345 total, zero failures or errors**. These include read-only projection, disabled-source handling, precedence preview/save, stale reviews after source/component changes, role and component-target access, draft validation, source retention, atomic rule binding, rollback, unnamed transient previews, and the existing Studio/value-type/run-operand regressions.

The local browser-component checks passed 43 render/interaction assertions, plus 14 direction/alignment assertions. Nine OWL templates compiled with the application's own compiler. Chrome then verified the deployed behavior: searchable components; zero and leading-zero identifier display; before/after priority review and Save; text and amount draft creation; cancellation; selection after refresh; explicit pay-role Save; component-focused system mapping; recipe search; four-step and all-steps editing; a preview before naming; the visibly preselected destination; Save & connect with fallbacks retained; the contained component trace; and the retained specialist tools.

At 390 pixels, the new component dialog measures 370 pixels wide with visible Cancel and Save controls and no horizontal document overflow. The viewport and navigation layout were restored after testing. The full Vietnam Journey renders 69 wires, including 10 with reverse arrowheads, and the original source/geometry files remain byte-identical to the prior runtime commit. Final Chrome checks reported no console errors.

Only the audit-created fictional scheme and connector were removed. All five databases match the original business snapshots for employee/contract counts, wages, configuration/rule data, payslips, stored pay values, and queued mail. All pre-existing scheduled jobs remain present with their original activation flags; no inactive job was enabled. Test PNG files were not saved, and no product images or user-provided screenshots were deleted.

The final database backups, source manifest, test logs, deployment receipt, and cleanup receipt are retained privately under `/odoo/backups/mapping-desk-responsive-20261016`. Earlier backup receipts are retained as well. The application service is active.
