# Formula Studio experience repair — 16 October 2026

The October audit found a crowded workspace and several controls whose visible
result did not match their label. The implementation introduces a Table workspace
with a component inspector, keeps Grid and Cards, and consolidates advanced tools
under the existing searchable Tools menu. Existing editors, permissions, approval
routes, fixed column letters, virtualization, and recent loading improvements remain
in use.

| Audit gap | Implemented treatment |
|---|---|
| Units and formatting | Shared frontend formatter honors value kind; typed Test, Replay and Payslip values; identifiers retain leading zeroes. Review value types proposes corrections without changing a configuration on read or overriding manual choices. |
| Health score contradicts issues | Workspace and Health show the same actionable error/warning summary. Text comparisons no longer trigger a numeric-reference error. Blank formulas are reported. |
| Unsafe unused-component advice | Review use replaces the delete shortcut; wording requires checking mapping and reports. |
| Incorrect Compare / What-if headline | Scheme net-pay designation replaces last-column guessing. Named monetary outcome can be selected explicitly; a missing designation requires a choice. |
| What-if combines historical runs | Explicit pay-run scope; one payslip per employee; correct population/sampling metadata. No assumed annualization. |
| Blank or numeric-only Test inputs | Letter-keyed imported inputs display correctly, value types choose input controls, text identifiers survive saving. Pending edits are captured per sample and serialized. |
| Grouping does not appear to work | Visible grouping by component type or Treatment group. Grouping changes only the view, never permanent sequence or column letters. |
| Show everything leaves columns hidden | Show all columns overrides both scheme hiding and the payroll lens for this view; a column manager and reset are available. |
| Add immediately saves a blank rule | Unsaved draft with name/type/value type and formula validation; Cancel creates no record. Server also rejects blank creation. |
| Empty active payslip layout | Readiness message; preview net is the designated computed component, independent of layout placement. |
| Redundant Grid rows | Category, Type and Status rows removed; type is in the header, errors remain contextual. Keyboard row model matches rendered rows. |
| Chaotic toolbar | Build / Validate / Compare / Health navigation; Table / Grid / Cards subviews; searchable Tools and Review changes. One lifecycle control. |
| Sample button silently cycles / does nothing | Labeled sample picker, disabled empty state, existing real-person picker retained. |
| Unreadable all-node map | Open centered on selected component at readable zoom; component picker centers and highlights its connections. Overview Fit remains available. |
| Progress, navigation and accessibility | What-if explicit run, progress, Cancel, failure feedback. Build view and selected component remembered per scheme. Close labels; draft dialogs trap focus and support Escape. |
| Legislation falsely says all aligned | Distinguish applicable configurations aligned from none applicable/checked. |
| Coverage implies complete correctness | Explain formula assertion coverage and scenario limits; existing boundary scenario generation retained. |

Classification corrections are intentionally reviewable. Applying a proposed value
type can change how future payroll inputs are interpreted; the screen explicitly
requires recomputation and validation before relying on changed stored results.
No existing pay run is recomputed by the repair or by opening the new workspace.

Validation: 14 native Node formatter checks; merged-template OWL compilation;
68 selected Odoo regression cases passed on an isolated copy of p0clone, with all
cron jobs and mail servers disabled and guarded against reactivation. Deployment
receipts and end-to-end Chrome checks are recorded in the deployment closeout.
