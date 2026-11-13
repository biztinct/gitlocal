# Independent review prompt — Payobook Workflow Studio

Copy the prompt below into another session with access to the same local workspace. Every local artifact reference uses its full absolute filesystem path. No attachment or ZIP is needed. These paths require filesystem access to this computer; they are not public URLs.

---

I want an independent, critical second opinion on the design and implementation of **Payobook Workflow Studio**, a graphical business-process configurator for our application on **Odoo 19 Community**. Please read the artifacts and relevant source before recommending changes. You do not need the earlier conversation; the context and reading order are below.

This is a review request, not permission to implement, deploy, activate workflows, modify business records, rename shared stages, grant access or send messages. Do not merely endorse the existing recommendation. Distinguish confirmed behavior, defects, usability risks, architectural tradeoffs, prototype-only ideas and missing evidence.

## Access and baseline

Read the artifacts directly from `/Users/adity/Documents/GitHub/gitlocal`. I will not attach files. Use your filesystem tools to open the absolute paths below, then follow the source map for additional implementation files. If this workspace is inaccessible, report that specific access limitation; do not claim to have read the files or require an attachment as the default workflow.

Review implementation commit `f68945ecc39b2845f00f09a77e3fa2941ffe640c`, branch `19.1`, `pb_lifecycle` version `19.0.1.9.0`, as documented on 10 November 2026. If the repository has later changes, identify them and distinguish them from this baseline. Source is authoritative for actual behavior; the POC is earlier interaction exploration.

## What we are trying to achieve

We want business users to build and understand workflows visually across **all supported business modules**, including new processes and later-added modules. Hiring was an integration example, not the scope of the product. Expense, payroll, leave, onboarding/offboarding and other processes matter too.

The experience should feel premium, modern, readable, friendly and intuitive: plain words, clear alignment, larger fonts, restrained borders, helpful animation, and details only when needed. We do not want a technical Odoo form or an overwhelming automation canvas as the everyday interface. The POC should inform the real end product, not be an attractive but disconnected demo.

Users should be able to add and rearrange steps, multi-field forms, tasks, people, emails, waits, conditions, different paths, parallel work and supported module actions. Dragging a card must change actual execution order, with valid destinations and Undo. A compact horizontal journey should wrap at the right edge, continue right-to-left on the next row, and keep the flow understandable.

The most important constraint is **no unnecessary duplication**. We already have Approval Matrix, people/backups, access and delegation, native stages/statuses, module settings, email templates, tasks, Hiring journeys/forms/automations and existing Lifecycle services. Reuse their authority and capabilities through a smooth experience. Separate specialist screens are acceptable when they are the better design, provided the user returns to the exact originating workflow and step.

Existing processes must keep working. New definitions start as drafts; publication/activation and impact should be clear. A permitted user opening a record should see its actual current workflow position in a flowchart. Designers should find existing workflows or set up a new one from a record/module. The distinction between editing a process and changing an individual record must be obvious.

## Read these artifacts first

1. Start here: `/Users/adity/Documents/GitHub/gitlocal/docs/design/workflow-studio/review/START_HERE.md` — scope, reading order, authority and stale-document warnings.
2. Design and implementation brief: `/Users/adity/Documents/GitHub/gitlocal/docs/design/workflow-studio/review/DESIGN_REVIEW.md` — complete current design, journeys, diagrams, models, permissions and semantics.
3. Decisions and gaps: `/Users/adity/Documents/GitHub/gitlocal/docs/design/workflow-studio/review/DECISIONS_AND_GAPS.md` — requirements history, alternatives and prototype/current comparison. Challenge its conclusions.
4. Artifact/source map: `/Users/adity/Documents/GitHub/gitlocal/docs/design/workflow-studio/review/ARTIFACT_MAP.md` — all major design elements and implementation paths, plus adjacent services and research references.
5. Verification: `/Users/adity/Documents/GitHub/gitlocal/docs/design/workflow-studio/review/VERIFICATION.md`, release summary: `/Users/adity/Documents/GitHub/gitlocal/docs/design/workflow-studio/review/evidence/RELEASE_SUMMARY.json` and 42-test log: `/Users/adity/Documents/GitHub/gitlocal/docs/design/workflow-studio/review/evidence/BACKEND_TEST_RESULTS.txt` — recorded evidence and limits, not newly rerun checks.
6. Original Workflow Studio HTML POC: `/Users/adity/Documents/GitHub/gitlocal/docs/design/workflow-studio-poc.html` — open offline with fictional data. Explore the three original views, multi-field collection, branches, rehearsal, review and Design notes.
7. Approval Matrix HTML POC: `/Users/adity/Documents/GitHub/gitlocal/docs/design/approval-matrix-poc.html`, Matrix design: `/Users/adity/Documents/GitHub/gitlocal/docs/handovers/APPROVAL_MATRIX_DESIGN.md`, approval design handover: `/Users/adity/Documents/GitHub/gitlocal/docs/handovers/APPROVAL_WORKFLOWS_DESIGN_HANDOVER.md`, Matrix ledger: `/Users/adity/Documents/GitHub/gitlocal/docs/handovers/APPROVAL_MATRIX_LEDGER.md` and closeout: `/Users/adity/Documents/GitHub/gitlocal/docs/handovers/APPROVAL_MATRIX_CLOSEOUT.md` — understand what Studio must complement and reuse.
8. Implementation narrative: `/Users/adity/Documents/GitHub/gitlocal/docs/design/workflow-studio/IMPLEMENTATION.txt`, original README: `/Users/adity/Documents/GitHub/gitlocal/docs/design/workflow-studio/README.txt` and benchmark/design source: `/Users/adity/Documents/GitHub/gitlocal/docs/design/workflow-studio/research.js` — historical rationale. Later dated implementation notes supersede earlier POC claims.

The POC is useful but is **not the latest deployed UI**. It contains richer simulated rehearsal, decision tables, sample multilingual Hiring templates and other ideas that have not all shipped. Its initial statement that `base_automation` was uninstalled is obsolete. Its “workflow stages” are now called **Sections**. The paused handover is historical. Older approval documents mention retired environments; they are not current deployment instructions.

The current HTML: `/Users/adity/Documents/GitHub/gitlocal/pb_lifecycle/static/workflow/index.html` requires the authenticated Odoo application and backend, so do not assess it by opening it as a standalone file. If authorized access is available, use Settings → Workflows → Workflow Studio, or a supported saved record's **View workflow** / **Set up workflow**. The public [preview](https://payobook.com/preview/workflow-studio/) is the historical POC. Do not assume access to private application URLs or fetch customer records to perform this review.

## Current design in brief

The original three alternatives became **Journey**, **Flowchart** and **People** views of one graph, with Journey the recommended default. **Across** was added later for wrapping rows. The main tabs are Build, Try it out, Review and Activity. A contextual inspector handles step settings; advanced options are progressively disclosed.

Collect information supports many typed fields in one task: text, number, date, dropdown, multiple choice, Yes/No, file, lookup, repeatable description/amount rows and sections, with conditional visibility and required validation. The designer edits/preview forms; the participant uses a full-screen task with save/resume. Native `mail.activity` is reused, linked to the workflow run. New Studio participant forms require an internal login; older token participant pages are separate.

Approval Matrix owns approval routes, people, backups, safeguards and applying the approved business effect. Studio references/submits/adopts the existing request rather than defining a second approval chain. Access rights stay in existing access services. Ordinary emails use shared `mail.template` and the native queue, with a premium composer and preview. Hiring candidate messages use their own existing service, not a duplicate generic sender.

Community `base_automation` handles record create/change/date event capture. Application-owned server actions capture durable events; a bounded periodic worker advances persistent runs. Enterprise Studio is not required. The implementation adds `pb.workflow`, version, event, run, step and log models beside existing `pb.journey.*` services. The earlier POC recommended extending Lifecycle first, so this additional runtime is a deliberate area for scrutiny.

Published graph versions are immutable, activation is separate, and existing runs stay pinned. Current permissions, source values for newer conditions, shared templates and module settings remain live dependencies. Saved groups insert snapshot copies rather than live governed references. A new standalone process uses run/form data; it does not create arbitrary Odoo models or fields.

**Record stages are not workflow sections.** For Expense, Draft / Waiting approval / Approved / Paid are native module values. Manager and Finance approval checks occur within the applicable approval status. Sections such as Prepare / Do the work / Finish group Studio steps; finishing a section does not move a record. Current progress displays the real native stage above the actual graph/approval route without inventing stage history.

Stages opens the native catalogue/context; Sections edits grouping. Filters and “Wait for this” use real native fields. Stage movement requires a module-owned operation. Inline shared-stage editing currently supports guarded Hiring rename through its existing service. Fixed statuses and arbitrary new native Hiring stages are not freely editable. A module's stage keys have business semantics and cannot safely be treated as labels alone.

Designers can open record setup, see existing same-module/company workflows and create an inactive draft for matching module records or only that record. Record-only is an ordinary ID filter; it does not suppress other workflows. The model picker supports readable persistent business models with company scope, not every technical/shared object. Native form entry points are generic; bespoke module screens are not automatically all integrated.

Typed nested filters cover start scope, before-change conditions, optional steps, branch/parallel paths and waits. New conditions generally use live source values; legacy simple branches retain snapshot behavior. Parallel eligibility is evaluated once. Role filters refer to the **initiator's current access groups**, not automatically the assignee or approval role. Required Matrix steps cannot be bypassed by a filter. The graph is structured, not unrestricted cyclic BPMN.

## Inspect source, not only this description

Start with definition/validation: `/Users/adity/Documents/GitHub/gitlocal/pb_lifecycle/models/workflow_definition.py`, models: `/Users/adity/Documents/GitHub/gitlocal/pb_lifecycle/models/workflow_models.py`, facade/worker: `/Users/adity/Documents/GitHub/gitlocal/pb_lifecycle/models/workflow_studio.py`, progress/security projection: `/Users/adity/Documents/GitHub/gitlocal/pb_lifecycle/models/workflow_progress.py`, configuration/templates: `/Users/adity/Documents/GitHub/gitlocal/pb_lifecycle/models/workflow_configuration.py`, record stages/setup: `/Users/adity/Documents/GitHub/gitlocal/pb_lifecycle/models/workflow_record_context.py` and backend tests: `/Users/adity/Documents/GitHub/gitlocal/pb_lifecycle/tests/test_workflow_studio.py`.

For UI, inspect app.js: `/Users/adity/Documents/GitHub/gitlocal/pb_lifecycle/static/workflow/app.js`, graph.js: `/Users/adity/Documents/GitHub/gitlocal/pb_lifecycle/static/workflow/graph.js`, forms.js: `/Users/adity/Documents/GitHub/gitlocal/pb_lifecycle/static/workflow/forms.js`, conditions.js: `/Users/adity/Documents/GitHub/gitlocal/pb_lifecycle/static/workflow/conditions.js`, templates.js: `/Users/adity/Documents/GitHub/gitlocal/pb_lifecycle/static/workflow/templates.js`, record-context.js: `/Users/adity/Documents/GitHub/gitlocal/pb_lifecycle/static/workflow/record-context.js`, CSS: `/Users/adity/Documents/GitHub/gitlocal/pb_lifecycle/static/workflow/style.css` and OWL wrapper/navigation: `/Users/adity/Documents/GitHub/gitlocal/pb_lifecycle/static/src/js/workflow_studio.js`. The workbench is predominantly plain JavaScript within an iframe; assess component reuse, accessibility and maintainability rather than assuming it uses all existing premium components.

Use the integration source map: `/Users/adity/Documents/GitHub/gitlocal/docs/design/workflow-studio/review/ARTIFACT_MAP.md` to compare existing Lifecycle cases/tasks, Hiring forms/automations, `pb_filter_kit`, Approval Matrix, `biz_approval_workflow`, `biz_access`, Expense states and shared navigation. These are the strongest places to find avoidable duplication.

## Questions I need you to answer

1. **Product and usability:** Is the default experience understandable to an ordinary process owner? Are four views helpful or excessive? Where can language, fields, navigation, forms, stage controls and progressive disclosure be simplified? Check keyboard/touch alternatives, zoom, mobile, error recovery and motion.
2. **Stages and progress:** Does the current distinction between record stages, sections, approval checks and step states solve the user's confusion? Propose a better experience if needed. Explain exactly how viewing, adding/editing stages, waiting for a stage and moving a record should work, using Expense and Hiring examples.
3. **Reuse and ownership:** Does this complement existing services or create second sources of truth? Assess the additional `pb.workflow.*` runtime, form builders, filter builders, inbox/task surfaces, shared templates, audit and module settings. State what to keep, reuse, consolidate or remove, with pros and cons.
4. **Native Odoo capabilities:** Are Community automation triggers, watched fields, before/after domains, activities, mail and business actions used appropriately? What useful capability is missing? Recommend premium controls, not raw technical forms or unrestricted Python/field writes.
5. **Workflow correctness:** Review semantic dragging, branches/fallback, filtered parallel work, joins, waits/timeouts, skipped paths, failures, retries, return-for-changes, duplicate starts and cancellation. Evaluate live versus snapshot data, shared-resource changes, idempotency and domain/preview/runtime consistency.
6. **Cross-module design:** Can this scale to Expense, Pay, Leave, employee journeys and future modules? What adapters or capability contracts are needed? Is record-only scope a good idea, and how should coexistence, precedence, discovery, expiry and governance work?
7. **Permissions and existing behavior:** Do design, publish, progress, participation and module-configuration rights remain separate? Check source access, company isolation, execution identity, template preview, attachments and shared-stage editing. Can any step bypass native approval or protected business effects?
8. **No double-ups:** Are current overlap checks enough? How should Studio reveal that a native hook, delayed job, template or another workflow already performs the same effect? Do not assume matching template IDs are a complete semantic conflict check.
9. **Architecture and maintenance:** Is the orchestration/runtime split justified? Should shared OWL components, schemas or services replace portions of the iframe workbench? Assess upgradeability, localization, audit, observability, retention and performance evidence.
10. **Benchmark-inspired improvements:** The retained shortlist includes ServiceNow, Kissflow, Pega, Workato, Camunda, Power Automate, Tines, Make, Zapier, Salesforce Flow, Appian, Nintex and Retool. Which patterns actually help this product? If you make fresh vendor/capability claims, verify current primary sources. Prefer a few valuable changes over adding every feature.

## Deliver the review in this form

- A clear recommendation: keep the direction, make targeted changes, or reconsider a larger architectural choice, with reasons and confidence.
- A prioritized findings table: severity/priority, affected journey or component, evidence with file/method or observed UI, impact, proposed change and verification needed. Separate confirmed defects from risks and missing tests.
- An ownership/reuse map stating which service owns each concern and where duplicate configuration or execution may occur.
- A revised interaction proposal for native stages + sections + record progress, including an Expense example and a different module. Use a simple diagram or wireframe if it improves clarity.
- A current/prototype/proposed capability matrix, including exclusions behind “all modules” and “new process.”
- A short implementation sequence with tradeoffs, compatibility/migration considerations and acceptance criteria. Prioritize the changes; do not just produce a feature wishlist.
- A test plan addressing the actual gaps. The recorded 42 backend tests, Chrome cases and five-model/four-database metadata checks are useful evidence but are not exhaustive all-module business-cycle, accessibility or scale tests.
- Any essential unanswered questions, after checking the supplied artifacts. If access is missing, identify precisely what you could not verify rather than inventing behavior.

Be candid. The goal is a simpler, coherent product with one understandable experience and clear ownership underneath, not to defend the current implementation or add complexity for its own sake.
