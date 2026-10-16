# Mapping design lab

Three interactive, self-contained HTML concepts for reviewing a mapping redesign before implementation:

- **A — Connection desk:** complete connections in paired rows, with Route / Storage / Use in payroll details. Recommended daily workspace.
- **B — Focused journey:** one component's route, with a grouped whole-scheme overview.
- **C — Guided review:** an issue queue with evidence, choices, before/after preview, and local application.

`index.html` also contains 12 design findings, tradeoffs, a capability-preservation matrix, the recommendation, and implementation acceptance criteria. It opens without dependencies. The private hosted review copy is managed by Sites project `appgprj_6ad1b2d84d888191b2ac3be354913d0d`.

## Scope and behavior

All examples are fictional. There are initially nine components and four review decisions. They do not describe the live customer's configuration. No employee data or screenshots are included.

The three views share in-memory demo state. Navigation preserves that state; reload/reset restores it. Only the preferred design is remembered in browser local storage. Marking a preference is not approval or a backend save.

Working interactions include component selection, search/filter, text and amount creation, compatible destination selection, source replacement preview, type/treatment changes, transform examples, suggestion acceptance, templates, and one-step Undo. Secondary tools demonstrate their proposed homes. Import, pay-run creation, real calculation, server permissions, discovery and source precedence are explicitly outside the prototype. No connector calls, background jobs, mail, or payroll database writes exist.

Important examples:

- Nationality → Storage → Make text component reuses the selected scheme component and adds local contract storage.
- + Component → Amount creates a named numeric component only after save, then visibly asks for a source.
- Standard working days → Use in payroll → Edit treatment → Days changes `22 ₫` to `22 days`.
- Text cannot silently become an amount; non-money values cannot directly add to net pay.
- Employee code `00017` stays an identifier with its leading zeros.
- Calculated salary explains why it has no incoming mapping.
- Guided review previews a decision before applying it.

## Validation

The author ran 52 interaction/invariant checks in jsdom, plus Chrome end-to-end checks and responsive layout checks. Deployment and final browser verification are recorded separately in `rollout.md`.

This change is a design artifact only. It does not modify or deploy the production Odoo modules, and has no database migration in scope. The deployment target is the isolated private design-review Site. Existing production job activation flags are untouched.
