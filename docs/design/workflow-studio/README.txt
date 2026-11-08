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
