# Verification, releases and review procedure

This document reports recorded implementation evidence. Preparing this review pack did not rerun the application's production release, activate workflows or change business records. The documentation pass validates its artifact links, package contents and source/POC consistency separately.

## Baseline and deployment scope

| Item | Recorded value |
| --- | --- |
| Implementation baseline | `f68945ecc39b2845f00f09a77e3fa2941ffe640c` |
| Native-stage/setup feature commit | `801378629a60ba8eb4fcde6f9ffa125fabc9a81a` |
| Branch | `19.1` |
| Module | `pb_lifecycle`, `19.0.1.9.0` |
| Server | SSH alias `Payobook19v2` |
| Custom addon deployment destination | `/odoo/odoo-server/addons`; preserve stock addons from the server checkout |
| Active databases verified | `payobook`, `payobook_template`, `p0clone`, `rize` |
| Combined custom source | 159 module trees verified, with installed versions checked in all four databases |
| Permanent evidence archive | `/odoo/archives/rize-workflow-stages-polish-20261110T001328Z/release-evidence` |

Rize is production. ABM and `abm.payobook.com` remain retired; do not recreate or deploy there. Production Rize backups and permanent retirement/final archives do not expire automatically. Nonproduction retention is seven days while preserving the latest usable backup. These operating constraints supersede historic scopes in older approval handovers.

The portable [release summary](evidence/RELEASE_SUMMARY.json) records the relevant verification without embedding database contents, temporary credentials or operational workflow-count details. It is derived from the permanent release evidence, not a new audit of current server state. Later deployments by other sessions may supersede this baseline.

## Recorded backend verification

The deployed transactional backend suite passed **42 tests, zero failures, zero errors**. The [recorded log](evidence/BACKEND_TEST_RESULTS.txt) contains the test names and result; [test_workflow_studio.py](../../../../pb_lifecycle/tests/test_workflow_studio.py) contains the assertions.

Coverage includes:

- Standalone processes, typed/required/conditional form answers and invalid payloads.
- Idempotent start versus deliberate repeat, draft conflicts, immutable pinned versions, explicit publication/activation.
- Native created/changed hooks, watched fields, before/after domains and pause isolation.
- Branches, eligible parallel joins, no-match continuation, persistent waits and timeout.
- Live new conditions versus legacy snapshot rules, nested roles and forward-answer validation.
- Required native Matrix, no-approval native fast path, frozen submission answers and return-for-changes.
- Native email queue/retry reference and native task/activity ownership.
- Progress versus design permissions, source access recheck, company boundaries and runtime mutation guards.
- Shared template preview/editing concurrency.
- Record setup, record-only filter enforcement, actual statusbar values without implied history, and guarded shared Hiring rename.

These tests establish specific behavior under their fixtures and assertions. They do not prove every supported model's complete business cycle, every provider delivery scenario, load capacity or all race conditions.

## Recorded Chrome checks

The latest deployed Chrome check passed with no page errors. It verified:

1. A real expense record's current native status appears above its actual approval route.
2. A Designer can create an inactive draft scoped to that record.
3. **Wait for this** uses the real stage field/value; fixed statuses cannot be renamed.
4. Sections remain separate from record stages; Designer does not gain publication rights.
5. The premium Hiring shared-stage rename editor opens and explains shared impact. Chrome canceled the change; the backend transactional test separately exercised actual rename and concurrency/permission checks.
6. A second module can open setup and create a draft from a record without an existing run.
7. The mobile stage dialog/navigation fits the viewport.

Metadata/setup checks covered Expense (`pb.expense.claim`), Hiring (`hr.applicant`), Employee (`hr.employee`), Leave (`hr.leave`) and Pay (`hr.payslip`) across all four active databases. Employee correctly had no native stage field. These were metadata checks, not full end-to-end Expense, Hiring, employee, leave and payroll lifecycles.

Earlier recorded implementation notes describe the 25-test initial runtime release and the expanded 38-test premium configuration release. Their Chrome checks included standalone task/form completion, native expense progress, shared email preview/edit without sending, exact origin return, module-settings return, Across rearrangement/Undo, task/path filters and responsive layouts. The latest 42-test log and summary are bundled; older summaries are in [IMPLEMENTATION.txt](../IMPLEMENTATION.txt), not represented as freshly rerun evidence.

## Cleanup and preservation

The latest recorded UI test removed five draft workflows, one temporary user and two contacts. It created no runs, sent no mail, and left the existing expense record and native stages unchanged. Four test PNG files were removed; the recorded remaining test-PNG count was zero.

No examples were automatically activated by the release. Existing workflow activation/version choices and cron settings were preserved. Publication remains separate from activation. This is not a guarantee that a future user-created workflow cannot overlap with existing functionality.

This documentation task creates no screenshots and includes no screenshot files in the portable bundle. Existing product assets and user-provided images remain untouched.

## Relevant commit history

| Commit | Work recorded |
| --- | --- |
| `fc9343ea5` | Initial interactive three-view POC. |
| `8795d6e90` | Broader benchmark research and richer interactive rehearsals. |
| `87c5cc467` | Readable, progressively disclosed product UI. |
| `0268b8d18` | Multi-field collection and existing approval-service reuse. |
| `0e05caf30` | Native/shared Hiring settings and workflow-group exploration in the POC. |
| `874f18ac3` | Simpler flow UI and semantic block reordering. |
| `7246c1fd5` | Historical pause checkpoint and progress-view requirements. |
| `5fee668b2` | Shared production Studio, forms, native automation and actual record progress. |
| `14a593ba1` | Deployment-note format normalization. |
| `3724b71f5` | Consistent relative-path ordering in release verification. |
| `6a3e866df` | Review text alignment and narrow-screen navigation fixes. |
| `2830bd9eb` | Premium templates, shared filter controls and Across journeys. |
| `a7e4e4ffb` | Checksum release copies for reproducible archive timestamps. |
| `801378629` | Native record stages, Sections distinction and record-level workflow setup. |
| `f68945ecc` | Mobile fit, available module-action choices and native-approval status wording. |

The documentation commit is later than the baseline. It does not change the feature version. The ZIP manifest identifies the source baseline and the documentation commit separately.

## Operational lessons relevant to confidence

One earlier release copy used archive-preserved timestamps. A same-size file could be missed by timestamp/size comparison. The hash check caught the mismatch before database upgrade; the copy was restored and the tool changed to checksum-based copying for forward and rollback operations. This is why the evidence records complete tree verification, not only a successful copy command.

A prior test-clone strategy allowed the main Odoo server to see a clone owned by its ordinary database role; module upgrade could reactivate cron. The clone was removed after checking that no mail had been sent. Future test isolation must prevent the main service from connecting, use an isolated database role where appropriate, and neutralize jobs after upgrades as well as before them. The later 42-test preflight used rollback-only transactional testing with existing workflow activity held/disabled inside the test transaction.

Do not run the retained release/test scripts blindly. Some contain historical release paths, refs or initial-install assumptions. A new execution requires checking their current inputs, active scope, backups and isolation. A second-opinion design review does not require that execution.

## Safe review walkthrough

Use the POC offline to understand interaction ideas. Its data and writes are fictional. Explore the ordinary Journey first, then Flowchart moves, People, collection forms, conditional paths and Design notes. Compare its behavior against the current-feature table; do not mark a current feature complete solely because its POC works.

For the current UI, use an authorized nonproduction account and read existing examples where available. Open a saved Expense record, inspect **View workflow**, compare the native stage strip with the approval route, and inspect **Set up workflow**. Compare a Hiring record and a module without a stage field. Examine the composer, conditions and Across view from an existing permitted draft without saving shared resources. Do not publish, activate, rename shared stages or send messages as part of a read-only review.

If a reviewer needs to verify mutation paths, they should first define a separate test plan and authorized isolated fixtures. This prompt does not grant production write access. Avoid raw database modifications and generic status writes that bypass module services.

When running authorized screenshot-based tests later, track the exact files created and remove those screenshots afterward. Never blanket-delete PNGs, `/tmp`, customer workbooks or unknown files.

## What remains unproven

The evidence does not certify formal WCAG conformance, full translations, arbitrary native-stage creation, universal module-action coverage, exhaustive duplicate-effect detection, exactly-once external delivery, production-scale throughput, full mobile task coverage, or public/token participant access for new Studio forms. Existing source permissions, role changes, shared templates and native module settings remain live dependencies even for a pinned run.

The independent review should state which findings come from code, which come from observed UI, which are architectural opinions and which need new tests. A missing test is a gap in evidence, not automatically a confirmed defect.
