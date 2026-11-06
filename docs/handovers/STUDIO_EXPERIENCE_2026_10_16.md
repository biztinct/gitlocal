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
| Chaotic toolbar | Build / Validate / Compare / Health navigation; Cards / Table / Grid subviews; searchable Tools and Review changes. One lifecycle control. |
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

Chrome follow-up repairs: compact controls against the live theme's full-width
input defaults; retain Table on entry from the configuration board; mark effective
sample inputs as Default; show the deterministic explanation in the inspector;
require an explicit value type for new components; leave proposed type corrections
unchecked and suppress boolean suggestions supported only by numeric zero/one
samples. Tool callbacks and timer-owning actions are bound to the component
instance so graph geometry and cancellation tokens survive OWL render contexts.
The graph's connection paths were found empty in the first deployed browser pass;
the final pass must verify non-empty path geometry and visible connections.

What-if now distinguishes a changed selected outcome from any changed intermediate
output. Scope includes employees excluded for missing inputs and extra payslips
ignored when choosing the latest one per employee. Added four regression cases
for default inputs, sparse-value classification, constant validation, and unchanged
headline outcomes; all 11 audit-specific cases pass before final rollout.

The Chrome write pass used a temporary, draft-only scheme with fictional sample
values. It verified explicit component creation, 00017/00018 identifier preservation,
21 unprefixed days, 10.5% rates, sample switching, a formula edit from 2,100 to 4,200,
Undo back to 2,100, persistent value-type changes, and fast Test sample switching
without moving an edit to the wrong sample. The temporary scheme was removed.
Real-scheme Test inputs now display 21 standard days with a Default marker.
Graph path geometry was verified non-empty after the action-context repair.

Final UI polish removes arbitrary sums from collapsed visual groups (they can mix
units or count the same pay twice), exposes the existing real-payslip picker from
the Table toolbar, keeps failing sample checks visible in the single review queue,
and adjusts the narrow layout so component names and preview values remain readable.


The follow-up runtime commit `b660d31e6` (Studio `19.0.1.201.20`) moves Cards to the
first tab and scopes the inspector's Open mapping door to the selected component.
Journey uses the component ID rather than a name search, includes connected source
rows, and excludes other components sharing those sources. Calculated/fixed rows
remain visible without invented mapping wires. Show all restores the full board;
changing scheme/tab clears the scope. All five databases passed 32 Studio checks
and retained every cron flag. Chrome verified India PF, Vietnam Standard working
days, connecting geometry, tab order, Show all, and return navigation. See the
follow-up section of the deployment closeout for exact targets and backup location.
