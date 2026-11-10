# WORKFLOW-2 programme — conventions and gotcha ledger

Started 11 November 2026. Builds on the shipped Workflow Studio (`pb_lifecycle`, baseline `f68945ecc`, 19.0.1.9.0). Design source: `docs/design/workflow-studio/review/SECOND_OPINION_REVIEW.md` (findings F1–F21, §9 addendum and the three "owner rulings" blocks at the end) and the clickable prototype `docs/design/workflow-studio/review/second-opinion-poc.html`. Every phase handover references this file. Add a row to §4 whenever a new gotcha is hit.

## 1. Owner rulings (binding)

| # | Ruling |
|---|---|
| R1 | **Add to the shipped design, never replace it.** Journey, Across, Flowchart, People, Build / Try it out / Review / Activity, the left step list, saved groups, module actions, reference steps and the existing Flowchart canvas (dotted canvas, curved connectors, "+" insert points, smooth drag) all stay. "By stage" is an additional view. |
| R2 | **No double-ups; Studio is the one central point.** Existing modules keep ownership of their own stages, approvals, messages, reminders and automations. Studio must (a) show what a module already does, in place, (b) never perform an effect a module already performs, (c) never write a module's status field, (d) never define an approval route, (e) warn before a designer adds a step that repeats an existing effect. A phase that adds an effect type must add its double-up check in the same phase. |
| R2a | **Reuse first, and ask the owner when an overlap is found** (owner, 11 Nov, citing Approval Matrix as the model example: Studio reuses it and adds no approval feature of its own). If a phase finds an existing feature that does the same job as something Studio has or is about to get (inbox, reminders, forms, conditions, messages, automations, checklists, stage settings), the builder does not build a second one and does not silently pick: it reports the overlap under "Overlaps found" in the phase report with the options, and the main loop asks the owner. |
| R3 | **Workflows run at system level, the native way.** No per-workflow execution user, no new service user. Who may build is controlled by the shipped groups (View progress / Designer / Publisher), assigned through Access. |
| R4 | **Users add their own stages without programming** (review §9): a workflow stage layer anchored to the module's own status; "Just a heading" stages keep today's Sections. |
| R5 | Ordinary employees (portal logins) and people with no login take part in workflow tasks. |
| R6 | Joiner and leaver checklists are to be expressible in Studio eventually. Do not migrate running journey cases. |
| R7 | White-label: the word "Odoo" (and "OdooBot") never appears in a user-visible string. Technical identifiers are untouched. |
| R8 | Plain English on every label, toast and error: words a process owner uses, no model or field names. |
| R9 | Design bar (verbatim, owner 2026-08-29): **"extreme WOW, intuitive, out-of-this-world experience, best in class."** Lucide SVG icons, never emoji. Brand indigo `#5A4BB0`, one solid primary button per bar. Every state designed (empty, loading, error, partial, huge). |

## 1a. Reuse decisions (owner, via question cards; inventory = `EXISTING_BEHAVIOUR_INVENTORY.md` Part 3)

| # | Overlap | Decision (11 Nov) |
|---|---|---|
| D1 | Workflow "My tasks" vs Approvals inbox | **Workflow tasks and forms go into the Approvals inbox** (one list, with a filter). The separate "My tasks" list is retired once they are there. |
| D2 | Late work | **Reuse the approval engine's reminder → escalation → backup** (and People & backups cover) for workflow tasks. No second reminder system. |
| D3 | Hiring Automations | **Hiring keeps its own.** Studio shows them as "already happens" and warns/refuses a repeat. Nothing is moved. |
| D4 | Form builders | **Studio's form builder is the general one** for workflows and, later, joiner/leaver checklists. Hiring's public application forms stay as they are. |
| D5 | Approvers told twice (pay change, overtime, contract extension, resignation, goals, time off, probation) | **Only the approval engine tells approvers when a route is live.** Each area's older duplicate message is switched off in that case. Work outside Studio; schedule as its own phase (P2b). |
| D6 | Requester told twice or never | **Fix the gaps, one owner per message.** Each area owns the one message to the requester; missing ones are added (e.g. expense claim approved / paid) and must reach employee-home (portal) logins. Same phase as D5. |
| D7 | New joiner preparation split between Hiring "Before they join" and the joining checklist | **Split by date.** Hiring's list owns everything before the start date (buddy, laptop preferences, meet-the-team). The joining checklist owns day one onward (day-one invite, raising the laptop request from the answer already given). The buddy chosen in Hiring is carried over, never asked twice. Work in Hiring/onboarding, same phase as D5/D6. |
| D8 | In-app notices, letters, one-step sign-offs, self-running checklist steps | **Reuse all four**: notice step → announcement; letter step → letters library (its sending approval stays); one-step sign-offs stay in "Other request"; self-running checklist steps shown as "already happens" with a warning before a repeat. |
| D9 | Databases | **`sudima` joins the deploy set for this programme** (owner, 11 Nov: "update sudima only"); it is a live client site (80 active jobs) whose `pb_lifecycle` was at 19.0.1.6.0. Back it up first. **`pbf_preview` and `recruit_connect_20261023` are never touched**: both are 2.1 GB copies of `payobook` with jobs and mail off, left over from earlier work. Deleting them is the owner's call. |

## 2. Phases

| Phase | Scope | Handover | Status |
|---|---|---|---|
| P0 | Inventory of what every module already does (stages, approvals, messages, automations) | brief in agent prompt → `EXISTING_BEHAVIOUR_INVENTORY.md` | done 11 Nov (uncommitted; 17 overlaps listed) |
| P1 | Backend unblock: system-level execution, approval step follows instead of forcing, coexistence, one timing rule, error codes | `WF2_P1_HANDOVER.md` → `WF2_P1_REPORT.md` | done (see report) |
| P2 | Module contract (stages, transitions, existing effects, subject person) for Expense, Leave, Hiring + workflow stage layer + "already happens" data and double-up warnings + sudima brought up to date | `WF2_P2_HANDOVER.md` | running |
| P2b | Message clean-up in the areas themselves (D5 approvers told once, D6 requester gaps incl. employee-home logins, D7 new-joiner split by date) — after P4 | — | — |
| P3 | Screens on the existing workbench: "When…" sentence, By stage view, Stages screen, stage headers and "already happens" rows on every view incl. the canvas, new step types, lateness choices, touch drag | — | — |
| P4 | Progress on the record, one "My work" list, portal employees and token links, where time goes | — | — |
| P5 | Vietnamese and Indonesian, schedule trigger, consolidation, closeout | — | — |

## 3. Standing engineering conventions

- Branch `19.1`. One commit per feature, explicit paths only (`git add <file>…`, never `.`/`-A`), no `__pycache__`. Builders commit; the main loop pushes. Scan for credentials before any push; the repo is public.
- Other sessions (including a ChatGPT deployer) work this repo and server. Never touch files outside the phase scope. Never rewrite shared history.
- Bump `pb_lifecycle/__manifest__.py` version every phase that ships.
- Deploy contract is in the repo `CLAUDE.md` (one addons dir, per-module scoped rsync, four databases `payobook`, `payobook_template`, `p0clone`, `rize`, never `abm`). Before any deploy: `ssh Payobook19v2 cat /opt/deploy-notes.md`; if another START has no DONE, stop and report. Append START and DONE/FAILED lines (`sudo tee -a`), name `Claude WORKFLOW-2`. Take `flock /tmp/payobook-studio-deploy.lock`. Snapshot active cron ids per database before and after; a `-u` must not change them (compare counts, never grep booleans).
- Use `~/pb_upgrade.sh <db> <module>` on the server for upgrades (detached, writes `/tmp/pbu.log` + `/tmp/pbu.done`). Never `pkill -f odoo-bin`. Never `systemctl daemon-reload`. Warm each site with one curl after a restart.
- Do not run `odoo-bin shell` while the service is running. Stop the service first, confirm no `odoo-bin` process, then start.
- Never copy a database on the live server without first switching off its jobs and mail servers (a copy gets its jobs run by the live service within a minute).
- Tests: `pb_lifecycle/tests/test_workflow_studio.py`, run with `tools/workflow_studio/run_suite.py` through `odoo-bin shell` (rolls back). `setUpClass` already holds existing live runs inside the test transaction.
- Browser validation on payobook.com with the QA login is mandatory for any screen change (credentials are in the main loop's memory, never in the repo).
- After JS/CSS changes: per database `INSERT INTO orm_signaling_assets DEFAULT VALUES` then `DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'`. The workbench under `static/workflow/` is served as static files inside an iframe with a `v=` query in `static/src/js/workflow_studio.js:18`; bump that value when workbench files change.

## 4. Gotchas

| # | Date | Gotcha |
|---|---|---|
| G1 | 11 Nov | `sudo()` keeps the calling user's uid. Module code that checks `self.env.user.has_group(...)` therefore sees whoever happened to trigger `_advance` (a participant, the cron user). For deterministic system execution use the superuser environment, not `sudo()`. |
| G2 | 11 Nov | `save_draft` classified validation errors by English text fragments; one fragment was stale. Use the error `code`, never the text. |
| G3 | 11 Nov | Overlap detection that reads only `base.automation` misses Hiring rules (`pb.hiring.automation.rule`), approval-engine outbox messages and Lifecycle reminders. The module contract (P2) is the source of truth for "already happens". |
| G4 | 11 Nov | `biz.approval.engine.submit(record)` keeps the record's own environment (`_as_record` does not rebind it). To send something in as a person, pass `record.with_user(person)` and call the engine from that environment; a superuser record turns the engine's `check_access('write')` into a no-op and records the system as submitter. |
| G5 | 11 Nov | The adapter field `approval_request_id` is "latest attempt for this res_model/res_id" with no company or process term. Worker-side code looks requests up itself with explicit `company_id` and `process_id` terms (`WorkflowStep._follow`). |
| G6 | 11 Nov | Since P1 the worker re-scans "needs attention" runs that still have a waiting step, every minute. Anything that raises inside that loop must fail the one step (per-step savepoint) and log once, or run history grows a row per minute. `_cron_workflows` guards both. |
| G7 | 11 Nov | `execution_user_id` is still referenced by record rules `workflow_run_participant` and `workflow_log_participant` (`security/workflow_security.xml`). The phase that drops the columns must remove those terms first, or the upgrade fails on the rule domains. |
| G8 | 11 Nov | Review's "Existing automation to review" lists every active `base.automation` on the model, including the rule Studio generated for another workflow ("Workflow Studio · …"), so that workflow appears twice on Review (also under "Also active for these records"). |
| G9 | 11 Nov | `/tmp/payobook-studio-deploy.lock` is root-owned 0644: open it read-only for flock (`exec 9</tmp/…lock; flock -n 9`); `exec 9>` fails with "Permission denied". `~/pb_upgrade.sh` runs `-u` with HTTP and cron threads on; P1 ran `odoo-bin … --no-http --max-cron-threads=0` directly, as `tools/workflow_studio/deploy_release.py` does. |
| G10 | 11 Nov | The framework's own refusal text for an unreadable record names the technical model ("You are not allowed to access 'Applicant' (hr.applicant) records."). It reaches designers as a step error when a task's assignee cannot read the record (T4). R8 gap, untouched in P1. |
