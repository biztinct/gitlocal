# Decisions, alternatives and open questions

This is a reconstruction from the retained POC, implementation notes, source and commit history. It records the user's requirements and the resulting design; it is not a verbatim transcript or an independent endorsement. Baseline: `f68945ecc39b2845f00f09a77e3fa2941ffe640c`, 10 November 2026. Read [the brief](DESIGN_REVIEW.md) for current behavior and [the source map](ARTIFACT_MAP.md) to verify it.

## How the design developed

| User request or observed problem | Design response | Current boundary |
| --- | --- | --- |
| A graphical workflow configurator for all business processes; at least three options | Journey, Flowchart and People views over one definition; Journey recommended as default | These became complementary views rather than three separate products. |
| Broader inspiration than Darwinbox, Zoho and n8n | Thirteen additional benchmark references and pattern comparisons in the POC | Desk research and design judgment, not an independently measured product ranking. |
| Less intimidating; larger fonts; the POC must resemble the end product | Readable type, short labels, contextual inspector, quieter borders, common blocks first, reduced-motion support | Current workbench follows this direction but is not a pixel-identical copy of the older POC. |
| Collect multiple fields, dropdowns and booleans | Multi-field task builder, preview and dedicated participant screen with save/resume | New Studio forms coexist with existing Hiring and Lifecycle forms. |
| Avoid duplication with Approval Matrix, delegation and access | Reference Matrix; reuse native approval requests, people resolution and application of approved effects | Studio does not provide a competing approver-chain editor. Broader semantic duplication detection is incomplete. |
| Reuse Odoo 19 Community automation | Install/use `base_automation` as the event-capture layer; keep premium controls | Durable runs, forms, joins and user-facing progress are additional application services. |
| Reuse Hiring settings, stages and email templates | Contextual module links, guarded actions and shared-resource editing where supported | Hiring candidate templates and ordinary `mail.template` remain distinct existing services. |
| Support entirely new processes and later-installed modules | Standalone workflow requests and a supported model picker | No automatic creation of business models or implementation of every module action. |
| Protect existing processes | Inactive drafts, explicit activation, immutable published versions, permission checks | Concurrent active workflows can still overlap semantically. Creation alone does not replace existing flows. |
| Show the exact position of a record visually | Read-only graph for actual runs and native approval attempts, multiple current parallel leaves | Native record stages are current context, not fabricated historical completion. |
| Drag blocks to change the flow | Semantic insertion/move targets, validation, Undo/Redo and keyboard/touch alternatives | Structured graph; arbitrary cycles/edges are not supported. |
| Review text collided and wrapped badly | Review markup/alignment and mobile navigation fixes | Full accessibility and localization certification remains open. |
| Create template opened a native Odoo form; Back returned to the wrong place | Premium shared-template composer, preview, contextual origin/selection/view restoration | Edits are to a shared mutable template, so later sends can change across workflows. |
| Filters should work on tasks and parallel paths too | Typed condition builder across start, optional blocks, branches, parallel eligibility and waits | Initiator roles, current source values and frozen eligibility need clear explanations. |
| Horizontal journey should snake across rows | Across builder view with alternating direction and parallel lanes | Runtime progress stays in Flowchart; deep nested groups open there. |
| Expense stages were absent from View workflow; editor stages were confusing | Native stage strip/context plus renaming editor groupings to Sections | Separate concepts remain necessary; whether the UI explains them sufficiently needs usability review. |
| Workflow editors should add/edit flows from any record/module | Supported native form entry, existing-flow list, module-wide or record-only inactive draft | Readable company-scoped business models; custom module screens need their own entry integration. |

## Alternatives considered and the current recommendation

**One workspace with contextual depth.** A canvas-first design makes branches visible but can intimidate ordinary users. A journey-first design is easier for linear work but can hide conditional complexity. A responsibility view helps with handoffs but is insufficient for execution order. The recommendation combines these views over the same graph, with Journey as the entry point. Across adds compactness at the cost of directional complexity. Review whether four views are now too many.

**Reuse existing services through a premium surface.** Rebuilding settings, permissions, stages and templates would create competing sources of truth. Sending users to every native form preserves ownership but fragments the experience. The chosen hybrid edits selected shared resources in a premium contextual UI, reuses module services underneath, and links to specialist settings with return context. A reviewer should challenge inconsistent coverage and decide where shared components are preferable to more custom screens.

**Separate sections from native stages.** Making a workflow group automatically set a record status looks simple but can bypass approval, accounting or Hiring side effects. Keeping sections as visual groups and using explicit guarded module actions preserves business semantics. The cost is a second concept users must understand. A possible next design is a stage-led view that groups work beneath the native stage it watches or changes, while still making the underlying operation explicit. That view is a proposal, not shipped.

**Native event capture plus durable coordination.** Stock automation supplies useful create/change/date triggers and domains. Long-running human work, immutable versions, conditional joins, task forms and visual run state need further coordination. The implementation adds `pb.workflow.*`. The initial POC instead recommended extending existing `pb.journey.*` first. The reviewer must assess whether the implemented separation is justified by generalized graph execution, or whether it creates avoidable task, form, runtime and monitoring duplication.

**Record-specific workflows use ordinary filters.** A record-only draft is just `id = selected record`, which keeps one execution system and makes scope inspectable. It also permits many one-off workflows and does not override module-wide flows. Alternatives include a centrally governed exception model, reusable process templates, or forbidding record-only automatic activation. None should be assumed approved simply because a record-only editor exists.

**Published versions pin definitions, not every dependency.** This avoids silently rewriting running graphs and still respects current rights and shared module settings. It does not guarantee reproducibility of later email body content, source values or role membership. Review whether templates/actions need separately versioned references, impact previews or explicit adoption policies.

## Prototype versus implementation

“POC” means the browser-local artifact. “Current” means the source at the baseline commit. A successful prototype interaction is not evidence of a production service.

| Capability | POC | Current application |
| --- | --- | --- |
| Journey, Flowchart, People | Interactive | Implemented over one persisted definition. |
| Across / wrapping rows | Not the authoritative reference | Implemented later in the builder. |
| Reordering, groups, Undo, insertion targets | Interactive, sample validation | Persisted draft changes with backend validation; existing versions unchanged. |
| Detailed simulated rehearsal, participant decisions, timers, injected failures | Rich local simulation | Try it out offers a more limited preview; actual human work uses runs/tasks. Do not equate preview with complete runtime simulation. |
| Decision tables with overlap checks | Interactive sample | Full POC decision-table designer not shipped. Typed conditions are shipped. |
| Typed data-token exploration and source jump | Rich sample UI | Supported field/answer selection in applicable controls; not every POC token affordance. |
| Forms | Many fields, local reusable versions; file metadata only | Server validation, real private uploads, persisted task answers; no full independent form-template library. |
| Approval checks | Fictional Matrix routes and role examples | Existing native Matrix and approval service. |
| Hiring shared settings and multilingual candidate templates | Browser-local sample editing | Native settings remain their owners; premium `mail.template` composer is not a universal Hiring-template replacement. |
| Native stage creation | Explicitly proposed, not performed | Not a generic capability; guarded existing Hiring-stage rename is implemented. |
| Saved groups | Browser-local version library and copied components | Published group snapshots copied into a graph; no propagated upgrades. |
| Version comparison / regression examples / JSON export | Rich local history and demonstrations | Immutable server versions and activity; not full parity with the POC's comparison/testing suite. |
| AI workflow drafting | Proposal | No AI generation service implemented by this feature. |
| External apps and webhooks | Conceptual/advanced possibilities | No arbitrary integration builder; use explicit registered adapters. |
| Roles and delegation | Fictional access/cover examples | Real ACLs and native approval ownership; not a new access-delegation engine. |
| Existing-record progress | Sample simulation | Real permission-filtered runtime/native-approval graph plus current native stage context. |

## Issues the second opinion should actively investigate

The following are review targets, not a claim that each is a confirmed defect.

| Area | Current evidence or concern | What the reviewer should decide |
| --- | --- | --- |
| Additional runtime | `pb.workflow.run/step` exists beside Lifecycle case/task and Hiring journeys | Retain separation, consolidate shared services, or converge runtimes? Compare migration and operational costs. |
| Forms and filters | New workbench editors coexist with Hiring forms and `pb_filter_kit` | Is there a reusable schema/component boundary that avoids parallel implementations? |
| Stage meaning | Native state, approval route, section and step state are separate | Can ordinary users predict which operation changes a record? Would native-stage grouping help? |
| Stage discovery | Statusbar/field conventions, with specific Hiring handling | Which modules need explicit capability adapters rather than metadata inference? |
| Shared-stage editing | Only guarded Hiring rename is inline; fixed statuses cannot be changed | Is the limitation explained at the point of action? Define a safe create/edit contract before promising generic stage creation. |
| Model coverage | Company-scoped readable models; hooks on native forms | Enumerate excluded models and bespoke screens, then prioritize missing entry points. |
| Duplicate side effects | Some template/native-rule/Matrix checks, no complete effect inventory | Design event + scope + effect ownership across Studio, built-in hooks and delayed jobs. |
| Record-only proliferation | Same model may have module-wide and many record-only flows | Define discoverability, precedence expectations, expiry and activation governance. |
| Shared mutable resources | Template contents and native settings are not frozen by run version | Are historical reproducibility, impact previews and audit detail adequate? |
| Filter timing | Live new conditions, snapshot legacy branches, frozen parallel eligibility, live waits | Make semantics predictable and verify parity with native domains and preview. |
| Role filters | Initiator's current groups | Is the role subject sufficiently explicit? Assignee/subject-person roles would need distinct selectors and access rules. |
| Parallel work | Eligible paths + all/first joins; side-effect restrictions | Review cancellation, losing branches, failures, retries and reconciliation with native services. |
| Failure handling | Savepoints, persistent native references, bounded worker, retry | Prove intended idempotency and explain partial irreversible work; do not advertise universal exactly-once execution. |
| Draft validation | `save_draft` classifies some errors using message fragments | Inspect the older `stage order` fragment against newer `section order` text. Prefer structured error codes if this makes the draft gate brittle. Publication still validates the full graph. |
| Component reuse | Plain JavaScript iframe workbench and its own CSS/components | Assess OWL/shared design-system reuse, focus preservation, keyboard access, translation and maintenance. |
| First-time usability | Four views, many capabilities and multiple status concepts | Test with ordinary process owners, not only implementers; reduce default choices if needed. |
| Operational scale | Periodic bounded scans, no enterprise-scale performance evidence | Identify workload targets and test queues, long-lived runs, locks, retention and observability. |
| Audit and participant access | Separate Studio logs and internal task UI | Evaluate integration with the existing audit console, inboxes, external participant pages and record navigation. |

## Research rationale and limits

The [retained benchmark source](../research.js) records ServiceNow, Kissflow, Pega Blueprint, Workato, Camunda, Microsoft Power Automate, Tines, Make, Zapier, Salesforce Flow, Appian, Nintex and Retool, alongside the initial Darwinbox/Zoho/n8n inspiration. The [artifact map](ARTIFACT_MAP.md) includes the relevant primary links.

The adopted patterns are progressive disclosure, contextual configuration, human-work forms, typed data choices, named paths, explicit joins, reusable groups, validation, versioned changes and visual progress. The shortlist is a design reference set, not a proven “best applications” league table. No new competitive benchmark or hands-on vendor evaluation was performed for this documentation pack. Claims in old research should be rechecked before using them for procurement or market comparisons.

## Suggested next review priorities

1. Resolve the ownership/runtime questions before adding more block types.
2. Test the Stages/Sections/approval explanation with real process owners using Expense and a second module.
3. Define an explicit module capability contract for stage management and business effects.
4. Strengthen overlap detection and explain what multiple matching workflows will do.
5. Choose where forms, filters, templates, task surfaces and audit can share components and services.
6. Add scenario-driven verification for failure recovery, multi-company access, shared-resource changes and larger workloads.

These are recommendations for the independent review to challenge, not authorization to change the application during that review.
