# Artifact and source map

All relative links resolve from this file in either the repository or the extracted review bundle. The bundle preserves those paths. Current behavior is defined by implementation commit `f68945ecc39b2845f00f09a77e3fa2941ffe640c`; the POC records earlier exploration. The bundle manifest lists every included file and hash.

## Review documents

| Artifact | Purpose |
| --- | --- |
| [START_HERE.md](START_HERE.md) | Reading order, scope, version, source authority and access instructions. |
| [SECOND_OPINION_PROMPT.md](SECOND_OPINION_PROMPT.md) | Copy into a session with access to the same workspace; uses absolute paths and requires no attachment. |
| [DESIGN_REVIEW.md](DESIGN_REVIEW.md) | Requirements, views, user journeys, architecture, service ownership, security and execution semantics. |
| [DECISIONS_AND_GAPS.md](DECISIONS_AND_GAPS.md) | Alternatives, evolution, prototype/current comparison and questions that need independent judgment. |
| [VERIFICATION.md](VERIFICATION.md) | Recorded tests, release chronology, limits and safe review walkthrough. |
| [Release summary](evidence/RELEASE_SUMMARY.json) | Sanitized copy of permanent release evidence, explicitly labelled as historical verification. |
| [Backend test results](evidence/BACKEND_TEST_RESULTS.txt) | Recorded output of the 42-test deployed backend suite. |

## Interactive design artifacts

| Artifact | How to use it |
| --- | --- |
| [Workflow Studio POC HTML](../../workflow-studio-poc.html) | Open directly in a browser. Self-contained, fictional data and browser-local persistence. Explore Journey/Flowchart/People, forms, rehearsal, review and Design notes. |
| [Approval Matrix POC HTML](../../approval-matrix-poc.html) | Open with its sibling [asset folder](../../approval-matrix-poc/). Compare route configuration, people/backups, scope and safeguards with Studio's orchestration role. |
| [Current workbench HTML](../../../../pb_lifecycle/static/workflow/index.html) | Application entry, not an offline prototype. Needs Odoo authentication, wrapper and RPC backend. |
| [POC README](../README.txt) | Original interaction contract, test commands and milestone notes. Contains historical statements superseded by the current brief. |
| [Implementation narrative](../IMPLEMENTATION.txt) | Chronological record of actual implementation, native automation, templates, filters, Across, record stages and setup. |
| [Paused handover](../PAUSED-HANDOVER.txt) | Historical checkpoint only. Work resumed; not the final delivery status. |

The original conversation's screenshots are not independent repository artifacts. Their issues are recorded in [the decision table](DECISIONS_AND_GAPS.md): intimidating typography, missing multi-field collection, Review text overlap, native template form, wrong return destination, missing native stages and confusion between stages and sections. Test screenshots were removed under repository policy; the pack does not recreate them.

## POC design, interaction and research source

| Files | Design elements |
| --- | --- |
| [shell.html](../shell.html), [style.css](../style.css), [ui.js](../ui.js) | Product shell, type/spacing/color/motion, icons and shared UI helpers. |
| [model.js](../model.js), [app.js](../app.js) | Shared definition, fictional execution/rehearsal, views, editor navigation, review and local history. |
| [forms-model.js](../forms-model.js), [forms-ui.js](../forms-ui.js) | Typed collection, form editing, conditional fields and participant experience. |
| [integration-model.js](../integration-model.js) | Approval integration and no-double-up sample rules. |
| [modules-model.js](../modules-model.js), [modules-ui.js](../modules-ui.js) | Hiring/sample native-stage and shared-settings workspace; prototype boundaries. |
| [flow-model.js](../flow-model.js), [flow-ui.js](../flow-ui.js) | Semantic card movement, valid destinations, grouping and graph layout. |
| [research.js](../research.js) | Benchmark evidence, recommendation, implementation roadmap and UI blueprint embedded in Design notes. |
| [build.py](../build.py) | Embeds source, styles and font into the standalone POC HTML. |
| [Inter font](../InterVariable.woff2), [font licence](../Inter-OFL.txt) | Offline typography and redistribution terms. |
| [test-model.cjs](../test-model.cjs), [test-flow.cjs](../test-flow.cjs), [test-forms.cjs](../test-forms.cjs), [test-modules.cjs](../test-modules.cjs) | POC-only semantics tests. They do not test the production runtime. |
| [test-ui.cjs](../test-ui.cjs), [test-ux.cjs](../test-ux.cjs), [test-flow-ui.cjs](../test-flow-ui.cjs), [test-forms-ui.cjs](../test-forms-ui.cjs), [test-modules-ui.cjs](../test-modules-ui.cjs) | POC browser/UX checks. Environment and cleanup requirements are in the README. |
| [deploy.py](../deploy.py), [verify-live.py](../verify-live.py), [nginx-location.conf](../nginx-location.conf) | Historical POC preview deployment/verification, not the application release procedure. Read only during a design review. |

## Current frontend

| Source | Responsibilities |
| --- | --- |
| [app.js](../../../../pb_lifecycle/static/workflow/app.js) | Library, builder, inspector, review, run/task views and state. |
| [actions.js](../../../../pb_lifecycle/static/workflow/actions.js) | UI actions, draft changes, navigation and server calls. |
| [graph.js](../../../../pb_lifecycle/static/workflow/graph.js) | Shared graph rendering, layout, Across, semantic move targets and progress cards. |
| [forms.js](../../../../pb_lifecycle/static/workflow/forms.js) | Form builder, preview and participant task UI. |
| [conditions.js](../../../../pb_lifecycle/static/workflow/conditions.js) | Typed condition editor and field/operator/value choices. |
| [templates.js](../../../../pb_lifecycle/static/workflow/templates.js) | Premium shared-email composer and preview. |
| [record-context.js](../../../../pb_lifecycle/static/workflow/record-context.js) | Native stages, setup from a record and shared-stage editing surface. |
| [style.css](../../../../pb_lifecycle/static/workflow/style.css), [icons.js](../../../../pb_lifecycle/static/workflow/icons.js) | Current visual system, responsive styles, status cues and icons. |
| [OWL wrapper](../../../../pb_lifecycle/static/src/js/workflow_studio.js), [record controls](../../../../pb_lifecycle/static/src/xml/workflow_record.xml) | Authenticated iframe, origin return, record form hooks and action entry points. |
| [Client action/menu XML](../../../../pb_lifecycle/views/workflow_action.xml), [manifest](../../../../pb_lifecycle/__manifest__.py) | Application registration, assets, dependencies and module version. |

## Backend architecture and contracts

| Source | Questions it answers |
| --- | --- |
| [workflow_definition.py](../../../../pb_lifecycle/models/workflow_definition.py) | What graphs/forms/rules are valid? How do typed comparisons, native-domain compilation and preview work? |
| [workflow_models.py](../../../../pb_lifecycle/models/workflow_models.py) | What is persisted? What runtime mutations are protected? How do native activity and approval models connect? |
| [workflow_studio.py](../../../../pb_lifecycle/models/workflow_studio.py) | What are the facade APIs, model selection, draft/publication/activation, event capture, assignments, worker, module actions and task/form operations? |
| [workflow_progress.py](../../../../pb_lifecycle/models/workflow_progress.py) | What can a viewer see? How are existing approval attempts projected? How do submission access, return and retries work? |
| [workflow_configuration.py](../../../../pb_lifecycle/models/workflow_configuration.py) | What metadata powers filters, native stages/fields and template editing? How are preview and shared-resource permissions checked? |
| [workflow_record_context.py](../../../../pb_lifecycle/models/workflow_record_context.py) | How are native stages discovered, Hiring stage edits guarded, record setup resolved and record-only scope enforced? |
| [Workflow security](../../../../pb_lifecycle/security/workflow_security.xml), [model ACLs](../../../../pb_lifecycle/security/workflow/ir.model.access.csv), [abilities](../../../../pb_lifecycle/data/workflow_abilities.xml) | Viewer, Designer, Publisher, record rules and role integration. Read facade checks too. |
| [Workflow cron](../../../../pb_lifecycle/data/workflow_cron.xml) | Configured periodic worker. |
| [Backend tests](../../../../pb_lifecycle/tests/test_workflow_studio.py) | Concrete assertions and uncovered behavior; 42 tests at this baseline. |

## Existing services to compare for overlap and reuse

The bundle includes tracked source for `pb_lifecycle`, `biz_approval_workflow`, `pb_approval_config`, `biz_access`, `pb_hiring`, `pb_me_expense` and `pb_filter_kit`, plus the selected navigation files below. This is integration context, not a claim these modules were all created or changed by Workflow Studio.

| Existing owner | Start here |
| --- | --- |
| Approval execution and business application | [engine.py](../../../../biz_approval_workflow/models/engine.py), [adapter.py](../../../../biz_approval_workflow/models/adapter.py), [chain_shim.py](../../../../biz_approval_workflow/models/chain_shim.py), [request.py](../../../../biz_approval_workflow/models/request.py), [process.py](../../../../biz_approval_workflow/models/process.py) |
| Approval scope, people, delegation and delivery | [binding.py](../../../../biz_approval_workflow/models/binding.py), [responsibility.py](../../../../biz_approval_workflow/models/responsibility.py), [delegation.py](../../../../biz_approval_workflow/models/delegation.py), [outbox.py](../../../../biz_approval_workflow/models/outbox.py), [event.py](../../../../biz_approval_workflow/models/event.py) |
| Approval Matrix UI and service | [matrix_facade.py](../../../../pb_approval_config/models/matrix_facade.py), [inbox_facade.py](../../../../pb_approval_config/models/inbox_facade.py), [matrix_room.js](../../../../pb_approval_config/static/src/js/matrix_room.js), [builder.js](../../../../pb_approval_config/static/src/js/builder.js), [scheme_panel.js](../../../../pb_approval_config/static/src/js/scheme_panel.js), [people_tab.js](../../../../pb_approval_config/static/src/js/people_tab.js) |
| Access and delegation | [pb_access_delegation.py](../../../../biz_access/models/pb_access_delegation.py), [pb_role_ability.py](../../../../biz_access/models/pb_role_ability.py), [pb_role_profile.py](../../../../biz_access/models/pb_role_profile.py), [role_assignments.py](../../../../biz_access/models/role_assignments.py), [role_editor.py](../../../../biz_access/models/role_editor.py) |
| Existing Lifecycle runtime and participant pages | [journey_template.py](../../../../pb_lifecycle/models/journey_template.py), [journey_case.py](../../../../pb_lifecycle/models/journey_case.py), [journey_task.py](../../../../pb_lifecycle/models/journey_task.py), [pb_journeys.py](../../../../pb_lifecycle/models/pb_journeys.py), [token_pages.py](../../../../pb_lifecycle/controllers/token_pages.py) |
| Hiring stages, existing automations and forms | [journey.py](../../../../pb_hiring/models/journey.py), [board_p1.py](../../../../pb_hiring/models/board_p1.py), [automation_p8.py](../../../../pb_hiring/models/automation_p8.py), [hooks_p8.py](../../../../pb_hiring/models/hooks_p8.py), [forms_p2.py](../../../../pb_hiring/models/forms_p2.py) |
| Hiring candidate communication | [comms_p8.py](../../../../pb_hiring/models/comms_p8.py); distinct company/key templates and sender from ordinary `mail.template`. |
| Actual Expense states and transitions | [expense_claim.py](../../../../pb_me_expense/models/expense_claim.py), [expense_claim_views.xml](../../../../pb_me_expense/views/expense_claim_views.xml) |
| Existing reusable filtering | [filter_view.py](../../../../pb_filter_kit/models/filter_view.py), [filter_mixin.py](../../../../pb_filter_kit/models/filter_mixin.py), [filter_components.js](../../../../pb_filter_kit/static/src/js/filter_components.js), [filter_kit.js](../../../../pb_filter_kit/static/src/js/filter_kit.js) |
| Shared navigation and settings return | [hub_nav.js](../../../../pb_hub/static/src/js/hub_nav.js), [settings_hub.js](../../../../pb_settings/static/src/js/settings_hub.js) |

## Adjacent approval design documentation

- [Approval workflows design handover](../../../handovers/APPROVAL_WORKFLOWS_DESIGN_HANDOVER.md): initial business/process inventory and design context.
- [Approval Matrix design](../../../handovers/APPROVAL_MATRIX_DESIGN.md): Matrix ownership and product design.
- [Approval Matrix ledger](../../../handovers/APPROVAL_MATRIX_LEDGER.md): decisions, implementation phases and evidence pointers.
- [Approval Matrix closeout](../../../handovers/APPROVAL_MATRIX_CLOSEOUT.md): historical delivery and limitations.
- Phased handovers: [P1](../../../handovers/APPROVAL_MATRIX_P1_HANDOVER.md), [P2](../../../handovers/APPROVAL_MATRIX_P2_HANDOVER.md), [P3](../../../handovers/APPROVAL_MATRIX_P3_HANDOVER.md), [P4](../../../handovers/APPROVAL_MATRIX_P4_HANDOVER.md), [P5](../../../handovers/APPROVAL_MATRIX_P5_HANDOVER.md), [P6](../../../handovers/APPROVAL_MATRIX_P6_HANDOVER.md), [P7](../../../handovers/APPROVAL_MATRIX_P7_HANDOVER.md).

These are preserved historical documents. Their deployment targets, screenshots and old completion status are not current operating instructions. In particular, ABM is retired. Some historical links require the full repository; they are not all bundled dependencies.

## Release and test tooling

[prepare_release.py](../../../../tools/workflow_studio/prepare_release.py), [deploy_release.py](../../../../tools/workflow_studio/deploy_release.py), [run_suite.py](../../../../tools/workflow_studio/run_suite.py), [sync_test.py](../../../../tools/workflow_studio/sync_test.py), [chrome_test.cjs](../../../../tools/workflow_studio/chrome_test.cjs), [ui_fixture.py](../../../../tools/workflow_studio/ui_fixture.py), [cleanup_ui_fixture.py](../../../../tools/workflow_studio/cleanup_ui_fixture.py).

These scripts document past release/test mechanics. Some contain release-specific stages, baseline refs and installation assumptions. They are not safe one-command onboarding instructions for a reviewer. [Verification](VERIFICATION.md) gives the review boundary and recorded results.

## Primary references retained from the design research

These links explain the patterns considered; they were not newly revalidated for this documentation pass. The original [research source](../research.js) contains the fuller comparison and source attribution. “Leader” is the design shortlist's judgment, not an independently verified ranking.

| Product | Pattern considered | Retained reference |
| --- | --- | --- |
| ServiceNow | Stage playbooks and alternative process views | [Create a process definition](https://www.servicenow.com/docs/r/build-workflows/workflow-studio/create-process-definition.html) |
| Kissflow | Human work, forms, parallelism and participant permissions | [Making a process workflow](https://kfdocs.kissflow.com/help/docs/build/processes/workflow-design/making-a-process-workflow) |
| Pega Blueprint | Guided drafting and completeness | [Blueprint expectations](https://academy.pega.com/topic/blueprint-delivered-and-hands-expectations/v1) |
| Workato | Typed data tokens and mapping | [Data pills and mapping](https://docs.workato.com/en/recipes/data-pills-and-mapping) |
| Camunda | Diagram validation and explicit process semantics | [Fix diagram problems](https://docs.camunda.io/docs/8.8/components/modeler/web-modeler/fix-problems-in-your-diagram/) |
| Power Automate | Contextual configuration and dynamic data | [Cloud flow designer](https://learn.microsoft.com/en-us/power-automate/flows-designer) |
| Tines | Groups, change control and operational clarity | [Change control](https://www.tines.com/stories/docs/stories/change-control/) |
| Make | Named routing, fallback and subflows | [Router](https://help.make.com/router) |
| Zapier | Human-in-the-loop pauses | [Request approval](https://help.zapier.com/hc/en-us/articles/38731463206029-Request-approval-to-keep-your-workflow-running-with-Human-in-the-Loop) |
| Salesforce Flow | Layout, versioning and tests | [Meet Flow Builder](https://trailhead.salesforce.com/content/learn/modules/flow-basics/meet-flow-builder) |
| Appian | Analyst/designer process configuration | [Process model object](https://docs.appian.com/suite/help/26.3/process-model-object.html) |
| Nintex | Reusable action groups and in-designer testing | [Designer canvas](https://help.nintex.com/en-us/nwc/content/designer/DesignerCanvas.htm) |
| Retool | Block data and execution debugging | [Workflows](https://retool.com/build-enterprise-apps/workflows) |

Native Odoo references: [Community automation source](https://github.com/odoo/odoo/blob/19.0/addons/base_automation/models/base_automation.py), [mail templates](https://github.com/odoo/odoo/blob/19.0/addons/mail/models/mail_template.py), [mail rendering](https://github.com/odoo/odoo/blob/19.0/addons/mail/models/mail_render_mixin.py), and [automation interaction documentation](https://www.odoo.com/documentation/19.0/applications/studio/automated_actions.html). The last describes Studio UI as well as concepts; it does not imply an Enterprise Studio dependency in this Community application. The server's own stock Odoo checkout remains the deployment authority for native addons.
