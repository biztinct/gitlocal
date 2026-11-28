# Mapping design lab

The current review is **revised Direction A** in `index.html`: a Connection desk with ranked multi-source mappings, a dedicated holistic Journey, and an improved transformation-creation flow. It is a design prototype, not a production implementation.

The original three self-contained alternatives are preserved in `explorations.html`:

- **A — Connection desk:** complete connections in paired rows, with Route / Storage / Use in payroll details. Recommended daily workspace.
- **B — Focused journey:** one component's route, with a grouped whole-scheme overview.
- **C — Guided review:** an issue queue with evidence, choices, before/after preview, and local application.

The revised review answers the user's priority/Journey/transformation questions and contains an **18-area capability-preservation check**. The archived alternatives retain the initial 12 findings and comparison. Both documents open without dependencies. The private hosted review copy is managed by Sites project `appgprj_6ad1b2d84d888191b2ac3be354913d0d`.

## Scope and behavior

All examples are fictional. The revised prototype starts with twelve components and three review decisions. The archived alternatives start with nine components and four decisions. These do not describe the live customer's configuration. No employee data or screenshots are included.

The revised desk, Transformations, and Journey share in-memory state. Navigation preserves that state; reload/reset restores it. The archived alternative chooser remembers a preferred design in browser local storage. A local preference is not approval or a backend save.

Working interactions include component selection, search/filter, multi-source tags, simulated fallback, scheme-wide priority impact preview, lane gates, component tracing, holistic Journey highlighting/focus/collapse, text/amount creation, record destinations, treatment, direct system-field conversion, rules, suggestions, reference reconciliation, templates, viewer mode, and one-step Undo. The rule builder demonstrates filters, aggregation, units, formula cases, missing data, defaults/errors, and save/bind while preserving fallbacks.

Import, pay-run creation, real payroll calculation, actual permissions, connector discovery and full server rule execution remain outside the prototype. The source-resolution examples are explicitly local simulations of the documented engine behavior. Specialist date/Python/assignment/cycle/canvas tools are retained in the proposed architecture, rather than replaced by reduced mock controls. No connector calls, background jobs, mail, or payroll database writes exist.

Important examples:

- Uniform allowance has system / spreadsheet / contract sources. Its file-supplied zero wins over the contract amount; blank falls through. `False` remains a value. Scheme priority is not a row-only display order.
- Journey is the final primary navigation item and opens the holistic view. Trace is a separate focused dialog; a component-opened Journey announces focus and provides Show whole Journey.
- Create approved overtime hours: 4 rows, 2 matches, 5 hours. Save and connect adds a Rule source while retaining the spreadsheet fallback. Unverified/no-data is not displayed as proven zero; an explicitly unverified rule can be saved unconnected.
- Shift note → Storage → Make text component reuses the component and adds contract storage, preserving the file source. + Component → Amount creates a named component only after save.
- Standard working days → Use in payroll → Edit treatment → Days changes `22 ₫` to `22 days`. Text cannot become an amount silently; non-money cannot directly add to net pay; identifier `00017` keeps its leading zeros.

## Validation

The author ran **63 revised interaction/invariant checks** in jsdom, plus Chrome UI verification. The initial alternatives passed 52 checks. Deployment and final browser verification are recorded separately in `rollout.md`.

This change is a design artifact only. It does not modify or deploy the production Odoo modules, and has no database migration in scope. The deployment target is the isolated private design-review Site. Existing production job activation flags are untouched.
