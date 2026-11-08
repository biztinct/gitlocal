Payobook Workflow Studio — interactive design POC v2

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
