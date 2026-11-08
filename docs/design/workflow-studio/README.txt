Payobook Workflow Studio — interactive design POC — stages and shared module settings revision

Deliverable: ../workflow-studio-poc.html (self-contained; also works offline).
Hosted preview: https://payobook.com/preview/workflow-studio/

Recommendation: Journey-first design with three interchangeable views of one
structured definition: Journey, connected Canvas, Responsibility Blueprint.
Design -> Rehearse -> Review -> Monitor is the main lifecycle.

Research & recommendation contains 13 expanded product benchmarks, the original
Darwinbox/Zoho/n8n references, evidence links, architecture, feature status and a
staged implementation plan. Product evidence and design judgement are distinct.

Working browser interactions:
- Drag/click to add, reorder, configure and remove steps; undo/redo; edit phases.
- Multi-step named conditional routes, fallback, nesting and explicit joins.
- Independent parallel tasks with all/first-completed join semantics.
- Human approvals, rejection, bounded send-back/resubmission, required inputs.
- Role-specific participant previews and sample access/cover/independence checks.
- Typed record and guaranteed earlier-step output tokens, preview and source jump.
- Decision tables with amount ranges, department, fallback and overlap detection.
- Browser-local versioned group library, independent pinned component copies.
- Guided rehearsal with rule/assignment/action traces, simulated timers and retry.
- Definition readiness, draft/snapshot diff, eight regression cases plus saved
  examples, immutable local snapshots, restore, JSON export and local run history.
- Six fictional templates: expense, leave, onboarding, hiring, offboarding, payroll.

Limits: no Odoo writes, production publication, emails, AI calls, customer records
or network integration calls. All access examples are fictional. Parallel runs
are simulated, not a durable server runtime. Stage labels do not create native
model states. JSON is a design schema, not an import for the current approval
engine. AI drafting, shared component governance, durable orchestration, live
adapters and production monitoring are proposals with implementation requirements.
Original v1 localStorage is retained; drafts/snapshots are copied to v2 on first
load. Export important browser-local work before clearing browser data.

Sources: model.js (definition and runtime), research.js (sourced rationale),
app.js (UI), style.css, shell.html. Build embeds them into one standalone HTML.

Build: python3 docs/design/workflow-studio/build.py
Semantics: node docs/design/workflow-studio/test-model.cjs
Chrome E2E: node docs/design/workflow-studio/test-ui.cjs
  Default local URL is localhost:8843/workflow-studio-poc.html.
  PLAYWRIGHT_MODULE may point to the installed Playwright package.
  WORKFLOW_TEST_URL selects a deployed URL.
  WORKFLOW_SCREENSHOT_DIR optionally saves JPEGs for visual review; remove all
  screenshots created by this test run after verification.
Live combined audit: python3 docs/design/workflow-studio/verify-live.py
Deploy committed preview: python3 docs/design/workflow-studio/deploy.py

Deployment only updates the standalone nginx preview route on payobook.com.
It verifies committed source/build consistency and the latest combined custom
module content and installed versions across payobook, payobook_template,
p0clone and rize. Unchanged modules/databases need no upgrade. Standard server
addons, retired ABM, customer assets and concurrent-session work are preserved.

Product UI revision — implementation reference

This POC is the visual and interaction specification for the end-product UI.
The live implementation should reuse its design tokens, components, type scale,
icons, spacing and disclosure patterns. Connect real adapters and data underneath
this interface when implementing the orchestration services. Keep implementation
notes in Design notes; they are not part of the primary end-user workflow.

Product contract:
- Inter variable font embedded offline with its SIL Open Font License.
- 16 px step titles, 14-16 px form text, 12-13 px supporting metadata.
- Neutral work surface, restrained borders, purposeful action colours and
  selected-step emphasis; primary controls at least 44 px high.
- Six everyday actions first; advanced actions under More possibilities/search.
- Open the step inspector on selection. Preserve field focus, scroll context
  and expanded advanced sections while editing. Escape returns to the step.
- Grouped paths are summarised until expanded. One model across Journey,
  Flowchart and People. Focus view hides side panels.
- Build / Try it out / Review / Activity are the product navigation.
- 150 ms feedback and 220 ms panel transitions, with reduced-motion support.
- Desktop inline configuration, tablet/mobile drawers, independently scrolling
  work areas. Mobile fields retain 16 px text.
- UI blueprint in Design notes records the same contract and benchmark sources.

Product UX checks: node docs/design/workflow-studio/test-ux.cjs
Uses the same PLAYWRIGHT_MODULE, WORKFLOW_TEST_URL and WORKFLOW_SCREENSHOT_DIR
settings as test-ui.cjs. Checks type sizes, key contrast pairs, keyboard focus,
progressive disclosure, laptop/mobile layouts and reduced motion.


Multi-field forms and no-double-ups revision (8 November 2026)

Default example: Expense reimbursement (connected). Also try Pay run and Full
and final settlement. Workflows -> building-pattern playground retains all
previous examples and browser drafts; these are explicitly not Matrix config.

Try: Collect expense details -> Edit form -> add/reorder/configure fields ->
Preview form -> Use this form. Try it out opens the dedicated participant screen.
Save draft retains a resumable task across browser reloads. Submit validates
all visible fields, stores typed answers, then invokes a sample Matrix route.
Return for changes reopens collection and restarts the approval decisions.

Forms support short/long text, dropdown, multiple choice, Yes/No, number, date,
email, sample record lookup, attachment metadata, repeatable description/amount
rows and section headings. Required rules, conditional visibility, minimum
number values, read-only existing-record prefills, reordering, keyboard
alternatives, reusable local versions and immutable run snapshots are working.
File bytes are NOT uploaded or persisted: only names/size/type are simulated.

One approval owner: connected examples reference a sample Approval Matrix route.
Scope/people/backups/safeguards stay in Matrix; local approver chains, approval
policy tables, a second Matrix step, bypass filters and duplicate status writes
are rejected. Approval application runs once; additional email is off by default.
No-approval still uses the engine to apply/log, not a bypass of that engine.

Broader recommendation: extend pb_lifecycle templates/cases/tasks/questions and
participant pages; reuse existing task/inbox surfaces, ApprovalSchemePanel,
biz_access permissions, distinct approval cover/access delegation, outbox,
mail.template/mail.activity, ir.cron, pb_audit.console, pb_filter_kit and
ir.attachment / employee vault. Generalise lifecycle to other business domains
only through explicit adapters. Workflow-only questions do not automatically
create model fields or approval facts. Before activation, inventory live event,
action, scope and recipient overlaps; select one executor per effect.

Odoo capability audit: Community base_automation exists in the server checkout,
but is uninstalled in payobook, payobook_template, p0clone and rize. mail,
biz_approval_workflow and pb_approval_config are installed in all four. Native
server actions and ir.cron are useful execution primitives; the Enterprise
Studio UI is not available. No live automation/module/schema is changed here.

Design notes -> No double-ups / top-bar How it fits records evidence, service
ownership, native Odoo reuse, completed prototype behaviours and remaining
implementation work. Architecture, feature status and roadmap agree with it.

Additional checks:
  node docs/design/workflow-studio/test-forms.cjs
  node docs/design/workflow-studio/test-forms-ui.cjs
The latter uses the same Chrome/environment settings as the existing UI checks.
Source additions: forms-model.js, integration-model.js, forms-ui.js.


Stages and shared module settings revision (9 November 2026)

Try Workflows -> Hiring · candidate journey -> Stages / Messages & settings.
One shared contextual workspace is recommended, with mature module components
and execution owners underneath. Design notes -> Stages & module settings
compares rebuilding all settings, navigating existing screens, and this hybrid.

Working POC features:
- Create, describe, reorder and remove workflow-only stage groups; preserve
  membership and validate approval dependencies when moving groups.
- Link native Hiring stages and edit a shared sample name/meaning. Both workflow
  and Hiring settings entry points resolve the same browser-local source.
- Native Hiring stage creation is a labelled proposal: current pb_key choices
  are fixed. Production requires extending keys/families, presets, guards,
  visibility and event handling. No live native stages are created by this POC.
- Show existing stage-entry behaviour before users add another action. Reuse the
  existing rule and sender; choosing an owned message adds a reference only.
- Shared company email editor with actual Hiring-style tokens, candidate preview,
  English/Vietnamese/Bahasa tabs, English fallback, validation and impact scope.
- Global email switch, existing sample rule toggle, source-labelled settings and
  specialist navigation boundary with return context. Sample source edits persist
  locally; no live Hiring records are fetched or changed.
- Rehearsal uses a guarded stage move, one existing phone invitation, typed
  candidate follow-up, Matrix offer approval, and an offer-preparation task.
  Offer approval is not offer sending. Joined is protected by its native action.

Preserved source semantics and implementation boundaries:
- pb_hiring owns pipeline stages, role-specific stage choices/presets, candidate
  visibility, event automations, queued work and candidate delivery. Reuse its
  existing facades; do not add competing base_automation or native template_id
  email triggers for events Hiring already dispatches.
- Candidate emails are mutable pb.hiring.message.template company/key records.
  Future sends use shared edits; they are not pinned to workflow versions.
  Internal mail.template remains distinct with its existing administrator editor.
- Hiring application form starters are copied per role. Reuse/extract the richer
  existing typed form editor; workflow collection is for additional information.
  Application-form and role-policy controls in this HTML are ownership previews,
  not a replacement editor. Specialist calendars/integrations retain their screen.
- This POC freezes fictional source records per rehearsal for repeatable examples.
  Live permissions, shared audit, cross-tab/server concurrency, component extraction
  and adapters remain production implementation work.
- Duplicate-check demos cover this sample catalogue. Production needs a complete
  event/action/scope/recipient inventory, including built-ins and delayed jobs.

Code evidence: pb_hiring/models/journey.py, board_p1.py, comms_p8.py,
automation_p8.py, hooks_p8.py, forms_p2.py; existing Hiring setup/form JS panels.
Source additions: modules-model.js, modules-ui.js.
Additional checks:
  node docs/design/workflow-studio/test-modules.cjs
  node docs/design/workflow-studio/test-modules-ui.cjs
The Chrome suite uses the same URL, Playwright and screenshot settings above.
