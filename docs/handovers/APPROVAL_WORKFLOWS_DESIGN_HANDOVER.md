# Approval workflows: one place to configure, the right people every time

**Design handover · 12 September 2026 · implementation has not started**

Owner brief: a premium, novice-friendly configuration experience for multiple approval processes, with central management and different hierarchies for different payroll schemes and divisions. This document is the implementation contract; the companion [visual design PDF](../../output/pdf/approval-workflows-design.pdf) supplies annotated screen compositions. Neither artifact is a working product.

Repository baseline inspected: `44e165cbd1b61d50b16c9e9a557077e7dab89b88`. This is a local source review, not a verification of installed modules or live database behavior. Re-read current code before implementation because other sessions are active. All new model names, methods, routes and capabilities below are proposals unless explicitly described as existing.

## 1. Product decision

Build **Approval workflows**, a central configuration workspace beside the existing Approvals inbox. Its core interaction is a readable, vertical sequence of people and decisions. A novice answers four questions:

1. **What needs approval?** Choose Payroll, Timesheets, Scheme changes, or another supported process.
2. **Where should this apply?** Choose the company, optionally a division or payroll scheme.
3. **Who checks it?** Add people or organizational roles in order, with an obvious “Everyone must approve” option.
4. **Does it work?** Try an example, resolve setup issues, and review the impact before publishing.

The differentiator is **“Try an example.”** The designer shows the actual route, resolved people, deadlines and reasons for this employee or payroll scope. A permanently visible sentence explains the configuration. There is no requirement to understand a flowchart, write a condition expression, or know an internal permission group.

Central management does not mean identical approvals everywhere. Shared workflows define steps; scoped role assignments supply each division's people. A scheme can inherit the applicable default, use another shared workflow, or have its own centrally visible variation. A single scheme spanning several divisions can therefore use the same workflow structure with different people.

### Three different approvals, one configuration experience

| Business question | Workflow type | What completion permits |
|---|---|---|
| Are these scheme changes ready to use? | Scheme changes | Seal/activate the reviewed scheme revision after technical checks |
| Are these payroll results correct? | Payroll run | Mark the reviewed run approved; downstream payment controls still apply |
| May this payment be released? | Bank payment release | Record internal authorization for the exact payment package; bank confirmation remains separate |

Timesheets, leave, overtime, employee changes and other objects use the same engine through their own adapters. Approval of one object never implicitly approves a different object.

### Confirmed owner decisions

The owner confirmed these choices during this design session:

- Shared updates **automatically apply to future submissions, with an impact preview**. Existing requests retain their version. Explicit version pinning is an optional advanced design capability, not the default.
- Payroll self-approval has **configurable exceptions with a required audit reason**. Independent review remains the preset; the configured exception can permit an otherwise eligible maker/submitter to approve. It is a first-release capability, not deferred work. See §7.2 for exact limits and audit behavior.
- First-release timesheets means **attendance and payroll hours, including imported timesheets**. Project timesheets remain a separate future adapter. Verify the live source before building; do not confuse the attendance grid with a durable submitted sheet.

## 2. Evidence and existing system reconciliation

### 2.1 Workbook source

Source: [Zoho Payroll Vietnam Final Configuration and Data Setup Pack COMPLETED.xlsx](../../RIZE/VIETNAM/Zoho_Payroll_Vietnam_Final_Configuration_and_Data_Setup_Pack_COMPLETED.xlsx), **Approval Matrix**, `A1:K14`. Read directly from the workbook's stored cell values. The workbook was not changed.

`A3` says roles are proposed and named approvers, delegates, limits and SLAs need completion before activation. `J5:J14` says “Ready” on all ten rows. These are source assertions, not proof that user accounts, delegates, deadlines or bank mandates are configured in this application. Import as proposed setup, then resolve and validate.

| Row / workflow | Maker → reviewer → final role (source) | Named people / backup (source) | Limit; timing; evidence (source) | Interpretation for the design |
|---|---|---|---|---|
| 5 · Employee master changes | HR Ops → HR Reviewer → HR Lead | Nithya (HR Manager); Monica (Finance Manager) | None; 1 working day; import report + change evidence | Change request with before/after evidence; confirm the unnamed reviewer separately |
| 6 · Salary/contract changes | HR Ops → HR Reviewer → HR + Finance | Nithya (HR) + Monica (Finance); Nguyen Thi Phuong Thao | None (unified); 1 working day; approved letter/contract | Propose HR and Finance as two required seats in one final step; confirm “+” semantics |
| 7 · Timesheet and leave | Employee/Manager → Line Manager → HR | Nithya (HR Manager); respective Line Manager | None; by Day 15 cut-off; approved timesheet | Split Timesheets and Leave into distinct adapters; dynamic manager, then HR; listed backup may conflict with the prior reviewer |
| 8 · Overtime | Employee/Manager → Line Manager → Functional Manager | Nithya (HR) + Monica (Finance); respective Line Manager | ≤200 h/person/year; by Day 15; approved hours and reason | Named people differ from final role wording; require clarification. Treat annual hours as a validation/control input, not a money threshold |
| 9 · Incentive/bonus | Functional Owner → HR/Payroll → Functional Manager + Finance | Nithya (HR) + Monica (Finance); Nguyen Thi Phuong Thao | None; by Day 15; scheme result and approval | Separate reviewer and joint final step; confirm functional manager identity |
| 10 · Draft payroll run | Payroll Preparer → HR Reviewer → HR Lead | Nithya (HR Manager); Monica (Finance Manager) | None; 1 working day; control report + variance | HR approval of results; Finance authorization is a later process in this matrix, not automatically another row-10 step |
| 11 · Funding and payroll journal | Payroll/Finance → Finance Reviewer → Finance Controller | Monica (Finance Manager); Nithya (HR Manager) | None; 1 working day; funding tie-out + JE | Separate funding and journal capabilities if different objects; one approval package only if both artifacts can be frozen together |
| 12 · Bank file creation | Payroll/Finance Maker → Bank Checker → Authorized Signatory | Nithya + Monica + Thao (joint); joint authorizers | None; on/before penultimate working day; bank control total | Draft proposes all three distinct people; identities and checker role need confirmation; do not infer backup seats from “joint authorizers” |
| 13 · Bank payment release | Bank Maker → Bank Checker → Authorized Signatory | Nithya + Monica + Thao (joint); per bank mandate | Per bank mandate; on/before penultimate working day; bank release confirmation | Mandate is unresolved structured input; internal approval cannot claim funds were released |
| 14 · Reopen / off-cycle payroll | Payroll Preparer → HR + Finance Review → Country/Finance Approver | Nithya + Monica (joint); Nguyen Thi Phuong Thao | None; case-by-case; exception approval and audit reason | Separate reopen authorization from the subsequent run approval; off-cycle uses an explicit run-kind binding |

Rules for interpreting this source:

- Stage 1–10 are **ten business processes**, not ten sequential approval steps on every pay run.
- The matrix does not identify which role every named person fills. Preserve raw text, propose mappings, and request owner validation in the setup review.
- “None” means no threshold condition was specified, not approval bypass. “Per bank mandate” and “Case-by-case” are unresolved configuration, not executable rules.
- “Thao” is not automatically linked to Nguyen Thi Phuong Thao. Offer the possible match and require an explicit account selection.
- “1 working day” does not say whether the allowance is per step or for the whole request. Propose a **whole-request target** for imported rows, requiring confirmation; each step may have its own response target.
- The 200-hour value is a workbook control, not a legal conclusion. This design does not change existing overtime caps, bonus-hour treatment or statutory calculations. Confirm the business/control policy before enabling it.
- Source controls and drafts belong only to the intended company. Never seed named people or Vietnam policies into all tenants.

### 2.2 Verified local integration points

| Existing location | Observed behavior | Required reconciliation |
|---|---|---|
| `pb_blueprint/static/src/js/blueprint_steps.js` | Current order is Start, Pay rules, **Connect (3 of 6)**, Outputs, Test, Finish | Keep the six-step journey; embed approvals in Connect |
| `pb_blueprint/static/src/xml/connect.xml`, `static/src/js/step_connect.js`, `models/blueprint_connect.py` | Approvals card is informational; says custom rules per configuration will arrive later; `_connect_guard` refuses setup/skip of approvals | Replace with real binding summary and builder entry; remove the informational-only server guard for approvals |
| `pb_blueprint/models/blueprint.py::optional_status` | Forces `approvals.status = info` | Migrate/coerce old JSON; derive workflow readiness rather than trusting a saved “done” flag |
| `pb_blueprint/models/blueprint_finish.py::_finish_optional`, `bp_finish`; `static/src/js/finish_text.js`, `connect_text.js`; `static/src/xml/steps.xml` | Finish reports approvals as informational; hides its change link; finishing setup does not activate real payroll | Show actual coverage and a working return link. Preserve finish-as-draft; readiness becomes mandatory when activating/submitting |
| `pb_payruns/models/hr_payslip_run.py` | Fixed `PB_TIER`, draft → optional level0 → level1 → level2 → done; protected state actions; run/slip cascades; send back and guarded undo | Existing legacy path must remain usable. New requests need dynamic request steps and a deliberate compatibility adapter |
| `pb_payruns/models/res_config_settings.py` | `pb_payruns.officer_review` is a per-database setting, default on | Capture into a legacy baseline per company during migration; retire the editable switch only after its submissions migrate |
| `pb_payrun_wizard/models/pb_payrun_wizard.py::submit_for_approval` | Existing entry point for run submission | Route through one server resolver; callers must not pick a workflow ID |
| `pb_approval/models/pb_approval.py`, `static/src/xml/approval.xml`; `pb_payruns/models/pb_payruns.py` | Payroll cockpit and board assume Officer/HR/Finance lanes | Make status and next approver data dynamic; preserve legacy lane rendering for legacy records |
| `biz_approval_chain/models/biz_approval_mixin.py`, `biz_approval_log.py` | Generic but code-defined transitions; append-only transition log; used by several modules | Add a versioned configurable engine beside the existing contract. Do not globally reinterpret all mixin users |
| `pb_hr_payroll_formula/models/formula_config.py::action_activate` | Technical error checks then activation/milestone | For migrated schemes require approval of the exact activation candidate; block direct writes and alternate activation paths too |
| `pb_formula_studio/models/pb_formula_studio.py::release_approve`, `rollback_apply`, branch merge callers; `pb_hr_payroll_formula/models/formula_release.py` | Editor-gated release sign-off creates a sealed milestone and `hr.formula.release` | Introduce a pending change proposal; seal the approved candidate only once, without recreating formula history |
| `pb_hr_payroll_formula/models/formula_review.py`; `pb_formula_studio/controllers/review.py` | Public token review can record a typed-name client acknowledgment | Preserve as external acknowledgment. It does not satisfy an authenticated internal approver seat |
| `pb_scheme_map/models/formula_scheme_assignment.py` | Existing `hr.formula.scheme.assignment` extends with division and cycle type; schemes can cover more than one segment | Reuse scheme assignments for applicability; do not create a competing employee-to-scheme map |
| `pb_group/models/pb_division.py` | `pb.division` crosses company boundaries; dated department links; `division_for` uses closest ancestor attachment | Reuse dated division resolution. Every approval binding also has a company boundary |
| `biz_access/models/pb_role_profile.py`, `pb_role_ability.py`; `pb_group/models/pb_group_visibility.py` | Existing role/ability and scope concepts | Integrate eligibility and visibility; organizational seat assignment is not a permission grant |
| `pb_hr_workforce/models/attendance_weekentry.py`, `attendance_timecard.py` | Grid/timecard facades; grid approval action shown is for overtime requests | Payroll timesheet approval needs a durable employee-period submission snapshot; do not attach approvals to a transient grid |
| `hr_timesheet_sheet/models/hr_timesheet_sheet.py` | Separate `hr_timesheet.sheet` business object and confirm/done/refuse actions | Optional project-timesheet adapter in a custom module; inspect installed server version, do not modify/deploy this vendored core copy |
| `pb_hr_workforce/models/overtime_request.py`, `pb_timeoff/models/pb_timeoff.py` | Overtime has guarded workflow fields and payroll-hour splitting; leave uses its own installed actions | Separate adapters; preserve payroll calculations and leave entitlement side effects |
| `pb_pay_delivery/models/bank_export_wizard.py`; payment actions in `pb_payruns` | Post-approval bank export/payment paths already exist | Inventory export, regenerate, download and paid-state paths before adding payment authorization |
| `pb_audit/models/pb_audit_console.py` | Consolidates existing approval logs and other audit sources | Extend source integration with request/decision IDs; do not create an unconnected second audit experience |

## 3. Scope and vocabulary

### Initial usable release

Ship the central workspace, sequential and joint steps, scoped people, delegation, evidence, versioned publication, routing preview, payroll run adapter, payroll-timesheet adapter, and the scheme's Connect integration. Complete the scheme-change adapter in the same programme before claiming scheme approval itself is configurable. The catalogue may show future types as **Not connected yet**, with no Publish action.

Other matrix processes follow through adapters: project timesheets/leave/overtime; master/salary/incentive changes; funding/journal; bank file/release; reopen and off-cycle controls. The roadmap in §14 makes these explicit deliverables, not simulated ready features.

### User vocabulary

| UI term | Meaning |
|---|---|
| Workflow | A named reusable set of approval steps |
| Applies to | Company, optional division/scheme, and kind of transaction |
| Step | A review or decision that must finish before the next step starts |
| Role in this division | A responsibility such as HR lead whose people are resolved in context |
| Everyone must approve | Each required seat must be satisfied by a distinct eligible person |
| One person can approve | Any one eligible member of the selected seat/pool may decide |
| Backup | Eligible replacement for a specific seat, with explicit activation conditions |
| Using company/division default | Inherited binding, with its source visible |
| Custom for this scheme | A centrally managed variant with its own lifecycle |
| Try an example | Read-only simulation using the same resolver as submission |
| Publish | Make a workflow revision available to future submissions from an effective time |
| Ready to use | Complete configuration and supported adapter, with current coverage checks passing |

Do not expose “DAG,” “quorum,” “domain,” “res.users,” “level1” or “rule priority” to ordinary users. Keep an expert inspection view for authorized support.

## 4. Information architecture and navigation

- **Approvals** remains the place to act on requests. Add **Workflows** for users with configuration capability; retain an obvious **My approvals** tab. Reuse the existing sidebar/hub placement rather than adding a second competing Approvals entry.
- Workflow workspace tabs: **Workflows · People & backups · History**. Default is Workflows, filtered by the existing active company context. Division scope must use the existing context facilities where embedded.
- The PDF uses simplified surrounding navigation, with Workflows indented beneath Approvals. In implementation use the actual hub/tab placement and current sidebar contract; do not reproduce the illustrative rail as a new global menu.
- Existing scheme Settings: **Approval workflows**. Blueprint **Connect → Approvals** opens the same detail/binding component with company and scheme fixed.
- Group/division detail offers **Approval responsibilities**, opening a filtered People & backups view. It does not invent another hierarchy editor.
- Every workflow row, scope chip, person and affected-scheme count is a working door with a return path. Unsaved changes are retained in a server draft or require an explicit leave decision.

## 5. Premium interaction and visual specification

### 5.1 Visual direction

Calm, confident and precise. Use Payobook's actual `pb_import_kit` tokens: indigo primary `#5A4BB0`, ink `#1B1733`, muted `#64748B`, page `#F5F6FA`, white surfaces, borders `#E2E8F0`, soft indigo `#EDEAF8`. Green, amber and rose carry status only. No gradients on chrome. Use existing typography, Lucide `ic()` registry, drawers and shared kit components. Mockup fonts approximate the installed product font; implementation inherits the application font.

- Desktop: 32 px page padding, 24 px between major areas, 16 px internal gaps, 14 px card corners. Header 28–32 px, step titles 16–18 px, body 14 px, secondary labels at least 12 px. Avoid a giant decorative hero.
- Builder: approximately 2/3 route editor, 1/3 sticky example preview. A thin neutral vertical connector creates the reading order; the step's people and decision rule carry emphasis.
- One dominant action per surface: **Create workflow**, **Continue**, **Try example**, or **Publish**, depending on state. Secondary actions are quiet, visibly labeled buttons.
- Use stable layout while loading, restrained 120–180 ms transitions, visible keyboard focus and reduced-motion support. Never use color alone for status.
- At <1100 px, put the preview below the editor or behind a labeled “Example route” disclosure with a result summary always visible. At 390 px, single-column cards and full-height drawers; action rows wrap. Do not shrink desktop text to fit.
- Translation: literal `_t()`/`_()` strings; English and Vietnamese QA; allow text expansion. Dates, currency and durations follow locale. Long person and scheme names wrap without ellipsis hiding identity.

### 5.2 Screen A — workflow library

Title **Approval workflows**, subtitle **The right checks, for every team.** Primary **Create workflow**. Quiet switch **Workflows / My approvals** where the hub permits it.

Show actionable setup summary only when there are issues: “2 workflows need people before they can be used.” A row opens the filtered issues. No invented health scores or decorative KPI grid.

Each row contains name, process, scope, readable route, status, and usage. Example: **Vietnam payroll review** · Payroll · Vietnam company default · HR reviewer → HR lead · Published · Used by 3 schemes. A custom row explicitly says **Custom for Retail monthly**. The route text is generated from the persisted revision, not maintained separately.

Search name/person; filters Process, Division, Status. Empty state: “Start with an approval flow you already know.” Offer **Payroll review**, **Manager then HR**, **Joint sign-off**, **Start blank**. Presets explain their steps and remain drafts until completed.

### 5.3 Screen B — create workflow

Four small progress labels: **Purpose → People → Timing & checks → Review**. Autosave to Draft with “Saved” / “Saving…” / “Couldn’t save · Retry” states. There is no auto-publication.

Purpose contains name, process, “Applies to” scope selector and optional run kind. Defaults derive from entry context. Choosing a scheme shows its divisions from the existing scheme map. Do not assume selecting a scheme selects a single division.

Offer **Use an existing workflow** before creating a duplicate. A similar workflow suggestion uses exact type/scope/step matching and is dismissible; it must not require an AI service.

### 5.4 Screen C — people and approval sequence

At top, the sentence: **“After submission, the line manager reviews. Then HR gives final approval.”** Editing a step changes this sentence immediately.

Each step card: number, human title, who approves, decision mode, backup summary, and Edit / Move up / Move down / Remove. Dragging may be optional, never the only ordering method. Maker is displayed as **Submitted by**, outside the decision sequence.

Person picker has three categories: **A person**, **A role in this company/division**, **Their manager**. Show the selected role plus resolved names for the current example. If unresolved, say “No HR lead assigned for Retail in Vietnam” with **Choose a person** / **Open responsibilities**. Never silently substitute all HR users.

Advanced disclosure contains conditional step and distinct-person policy. Payroll also exposes **Self-approval exceptions** with a plain summary, scoped eligible roles/people and mandatory reason. Joint step uses clear checkboxes/seats and **Everyone must approve**. Example: “Nithya and Monica must both approve.” A pool uses “One of these people.” Initial release supports any-one and all-required; arbitrary N-of-M and arbitrary graph branching are later capabilities.

Add step offers **Review**, **Final approval** and **Notify people**. Notifications are visibly outside the approval sequence and never counted as required approvals. A conditional step reads **“Only when overtime is included”**, with an Always/Only when selector and a typed field/operator/value form. No expression editor for business users.

### 5.5 Screen D — timing, evidence and backups

Use a small set of grouped questions, not a large technical form:

- **When is this due?** No target / Within working time / Payroll calendar deadline / Choose date on each request.
- **If someone is away?** Name seat-specific backup; temporary delegation dates live under People & backups. Missing backup is a warning unless mandated; a missing required primary is blocking.
- **What must be attached?** Check named evidence requirements, stage at which required, and acceptable document kind. Evidence may be an immutable generated control report.
- **If it is late?** Reminder then notify the workflow owner. Reassign to an approved backup only when explicitly configured. Never auto-approve.

An example displays the **absolute local due date and timezone**. “Day 15” is incomplete until the payroll calendar, local time and non-working-day rule are chosen. “Penultimate working day” requires month/calendar anchor. Keep country-specific examples inside that company's setup.

### 5.6 Screen E — try an example / fix gaps

Right-hand preview, also available full width: employee or run selection, division, scheme, run kind and submission date. Server derives facts from a real record. For hypothetical samples, visibly label editable facts **Example data**. No actions or notifications are sent.

Show: **“Retail monthly → Retail exception → workflow v2”**, then sequential cards with actual people, backups, due times, evidence and conditions. **Why this route?** expands selection precedence and why other candidate bindings lost.

Use three result levels: **Ready for this example**, **Needs attention** (non-blocking), **Cannot submit**. A blocked result names the problem, object and fix. Example: “The line manager is also the submitter. Choose an independent backup for this step.” Include a separate whole-scope coverage run so one good example cannot masquerade as full validation.

The example panel differentiates **No rule applies**, **Person missing**, **Permission missing**, **Conflicting rules**, **Unsupported record type** and **Required evidence missing**. “Fix setup” deep-links to the offending field; preserve the draft and preview context.

### 5.7 Screen F — payroll scheme integration

Connect remains **step 3 of 6**. The Approvals card expands into:

1. **Payroll run approval** — effective workflow and a compact people path, plus **Change**.
2. **Scheme change approval** — separately labeled workflow for activating/releasing changes, plus **Change**.
3. **Related approvals** — links to payroll timesheets and payment authorization; explicit prerequisite status, not editable duplicate definitions.

“Change” opens three radio choices:

- **Use the default for each division** — recommended initial choice; displays every distinct effective route, not just the first.
- **Use a shared workflow** — choose a compatible published workflow. Role holders still resolve for each division.
- **Customize for this scheme** — start from the effective workflow; create a new centrally visible variant only when changes are saved. Label exactly what differs and which division/run kinds it covers.

Within a scheme, **Add an exception for a division** allows a different shared workflow or variant for that division. Default and exception precedence must be shown in the preview. If someone chooses Customize on a scheme already spanning different workflows, first choose which route to start from; do not merge silently.

Always show provenance: **Inherited from Vietnam / Retail**, **Shared with 3 schemes**, or **Custom for this scheme**. Editing a shared workflow says **“This changes future requests for 3 schemes”** before publication; **Customize instead** is available without losing edits.

Finish may retain an incomplete draft, with the exact issue listed in Decisions still open. It must not activate a scheme or submit a payroll run with unresolved approval coverage. Technical validation, completing setup, workflow readiness, and business approval are four distinct statuses.

### 5.8 Screen G — review and publish

Review shows **What changes**, **Who is affected**, **When it starts**, and **Requests already in progress**. Example: “Add Finance after HR for Retail monthly. Applies to new submissions from 1 October, 09:00 Asia/Ho_Chi_Minh. 12 requests already in progress keep their current route.” All counts are real and permission-filtered.

Before Publish, run whole-scope validation. Blocking issues have direct fixes. Ordinary warnings require acknowledgment with named consequences; no blanket “I understand everything.” Compare the previous published revision and the final draft in human terms, including removed checks and changed permissions.

Publish rechecks draft revision and the scope fingerprint. Concurrent change returns “This workflow changed while you were reviewing it. Review the latest version.” Publication must not secretly adopt a different draft.

Success: **“Workflow published. Future submissions will use this version from [time].”** Links **View workflow** and **Return to scheme**. No confetti in payroll configuration.

### 5.9 Screen H — request and mobile review

Inbox shows My turn / All visible / Returned, with workflow type, scope, due date and next person. Avoid fixed named lanes that cannot represent custom workflows. Filters preserve company and division visibility. Amounts are grouped by currency, never summed across currencies.

Request drawer shows read-only submitted facts, evidence, clear current step, completed decisions, and remaining people. Joint step says **“1 of 2 approvals received · Waiting for Monica.”** Actions: **Approve**, **Send back**, and secondary **Reject request**. Send back/reject requires a reason and shows the consequence before submission.

At 390 px, identity and current action come first; evidence and history are disclosures. Sticky footer does not cover content or the on-screen keyboard. Loading and permission loss disable actions with an inline reason. Batch approval requires explicit selection and per-request results; omit it from the first release if independent evidence review cannot be preserved.

## 6. Workflow, binding and responsibility model

Keep these concepts separate:

1. **Definition**: reusable identity, owner, process type and immutable published versions.
2. **Binding**: where a definition/version applies; company, scheme, division and run kind.
3. **Responsibility**: who occupies a business seat for a company/division and effective dates.
4. **Request**: the exact object revision, selected binding/version and resolved approval route at submission.

Changing a division's HR lead need not create new workflow definitions. Changing the approval order requires a new workflow revision. A custom variant is a full independent definition with parent provenance; it does not inherit hidden field patches when its parent changes. Offer a reviewable **Compare with original** / **Adopt changes** operation later.

### 6.1 Deterministic selection

Always start with the record's company; never use the currently selected UI company as the authoritative business scope. Cross-company divisions do not erase this boundary. A binding belongs to one company. Group administrators may apply a template to several companies through a reviewed batch operation that creates separate bindings.

For each homogeneous approval scope, select the first matching rank:

| Rank | Binding scope |
|---|---|
| 1 | Exact scheme + exact division |
| 2 | Exact scheme, any division |
| 3 | Exact division, no scheme |
| 4 | Company default, no division/scheme |

Within a rank, an exact run-kind binding wins over **Any kind**. Match process type exactly. Choose only effective bindings and eligible published revisions; compare timestamps in UTC with UI-local conversion. Do not use amount/employee conditions to pick among competing definitions in v1; conditions include or omit steps inside the selected definition.

If no binding matches, refuse submission with an actionable setup error. If two bindings tie, publication should already have blocked the overlap; at runtime fail closed and list the conflict to an authorized workflow owner. Never pick the newest ID or smallest sequence arbitrarily.

Explicit blocked/paused binding at the winning rank is a **stop**, not permission to fall back to a broader workflow. Inherit mode creates no shadow “empty override”; it resolves the lower-scope default. Pinning references a published revision explicitly and appears in impact previews.

### 6.2 Examples

| Record facts | Available bindings | Expected route |
|---|---|---|
| Vietnam, Retail, Retail monthly, end-cycle | Company default; Retail default | Retail default |
| Same record | Above + Retail monthly shared binding | Scheme shared binding |
| Same record | Above + Retail monthly/Retail exception | Exact scheme/division exception |
| Same scheme, Operations division | Retail exception + scheme shared | Scheme shared with Operations role holders |
| Retail monthly, off-cycle | Scheme any-kind + scheme off-cycle | Scheme off-cycle |
| Singapore, Retail division | Only Vietnam/Retail binding exists | No match; never cross company |
| Same-rank overlapping end-cycle bindings | Two effective matches | Setup conflict; cannot submit |

### 6.3 Mixed payroll runs

A run can contain payslips from multiple schemes and divisions. Do not read `slip_ids[:1]` to choose a workflow. In v1, **prevent mixed approval scopes on submission** and offer **Split into review groups** before approval. Each group must have one company, currency, scheme, division and run kind, plus one resolved workflow. Each resulting pay run follows the existing per-run/slip finalization contract. Validate the split conserves every payslip exactly once and reconciles totals; use draft-only splitting and an explicit review action.

If operational requirements demand a single parent run, a later adapter may maintain child approval packages and complete the parent only after every required child succeeds. That is a separate supported capability and must not be improvised by grouping only the UI. Preview must reveal mixed scope even when two divisions currently happen to have the same approver names.

An employee with multiple employment/scheme segments in a period may need more than one payroll-timesheet scope. Determine allocation from the existing payroll assignment resolver and record effective dates, not from the employee's current department alone. Unresolved allocation is a setup issue.

### 6.4 Time semantics

- `submitted_at`: when the request is frozen and its workflow revision is selected.
- `scope_date`: business date used by the adapter for dated employment/division/scheme assignments. Payroll uses the approved calculation context/segment dates; timesheets use dates covered by the submitted hours.
- `effective_from`: earliest submission timestamp eligible for a workflow revision/binding.
- `due_at`: frozen UTC deadline, with original calendar/timezone metadata.

If the adapter cannot provide unambiguous scope facts, it must refuse submission. Moving an employee or department after submission does not silently reroute an existing request.

## 7. People, independence and delegation

### 7.1 Approver selection: recommended hybrid

**Choose a responsibility or reporting relationship by default; resolve it to authenticated users. Keep direct user selection for fixed signatories and specific exceptions.** This is a product recommendation informed by established enterprise patterns, not a claim that one universal method suits every process.

Microsoft's sequential approval documentation retrieves the employee's manager and uses the manager's mail address for the approval. SAP's recipient assignment documentation distinguishes direct users from roles/team functions and specifies one-recipient versus all-recipient completion. These support the hybrid approach; Payobook's scope, snapshot and exception rules here are our design decisions. Sources: [Microsoft: Set up sequential approvals](https://learn.microsoft.com/en-us/power-automate/set-up-sequential-approvals), [SAP: Configuring recipient assignment](https://help.sap.com/docs/SAP_S4HANA_CLOUD/a630d57fc5004c6383e7a81efee7a8bb/1500e4821dcc4cfe8bb6c89688843055.html), accessed 12 September 2026.

| Picker option | Best fit | Example shown to a novice | Maintained in |
|---|---|---|---|
| **Their manager** | Individual attendance/payroll-hour requests | “Line manager of the employee on this timesheet → [resolved name]” | Existing employee reporting relationship |
| **A role in this division/company** | HR, Finance, functional approvals across schemes | “Finance approver · Vietnam / Retail → Monica” | Central People & backups responsibility assignments |
| **Specific people** | Named signatories, small fixed teams, temporary needs | “Nithya + Monica + Thao · Everyone must approve” | This version's named seats; replace via a new version/reassignment |
| **One of a team** | An interchangeable review desk | “Any eligible member of Vietnam Payroll Review” | Scoped approved responsibility pool, intersected with permissions |

Show the first three options as cards in the picker; **One of a team** is a role/pool option, not another required concept on the initial screen. For a payroll batch, recommend scoped business roles because a batch can contain many employees/managers. If a manager step is explicitly chosen, split the approval scope by resolved manager or explain that the run must be split; never use the preparer's manager as a substitute.

Picker details: search by display name and existing business identifier; show avatar/initials, full name, job/role, company/division and account availability. Respect directory visibility. Do not auto-link employees without accounts, choose by job-title text, invite users or grant permissions merely by selecting them. A role is an organizational responsibility, not a raw permission group or an AI guess. Restrict selectable roles to an approved catalogue and show a direct repair path for missing assignments.

Responsibility resolution is deterministic: exact company+division assignment first; explicitly configured company responsibility fallback second. A division-required role with no assignment blocks unless its definition explicitly permits company fallback. Show fallback provenance. Overlapping single-holder assignments block; an intentional pool is separately typed and displays any/all semantics. If scheme-specific people are needed without a different sequence, permit a reviewed scheme-specific seat assignment at higher specificity, shown as “For this scheme”; do not clone the whole workflow merely to change its HR lead. Add optional scheme scope to the responsibility record, with precedence scheme+division → scheme → division → company and the same explicit fallback policy. Source `pb.role.profile` supplies eligibility where appropriate; it does not by itself establish a person's scoped business responsibility.

Updating a role holder affects **new requests**. In-flight requests retain their assigned people until an authorized, logged reassignment or applicable delegation takes effect. Always show the human resolution and why: **“HR lead for Vietnam / Retail → Nithya.”**

Resolvers supported initially: selected authenticated user; employee line manager; department manager; named responsibility in record company/division; bounded group of eligible people. Resolve line manager from the employee being reviewed, not the submitter who uploaded a batch.

Eligibility = selected/resolved responsibility **and** active identity **and** allowed company/division/object capability. Configuring a person never grants access to payroll data. The picker shows “Needs permission” as an issue and offers a link to the existing access-management experience for an authorized admin.

Freeze principals/seats and initial resolved candidates at submission; recheck access, active account and segregation of duties at every decision. Do not change people dynamically just because a role assignment changed. A request owner with reassignment capability may choose an eligible replacement with a recorded reason. An unavailable person never results in approval by default.

For payroll/scheme/bank workflows, the default independent-person policy excludes the submitter and the recorded business maker from required decisions. Also exclude the underlying subject for their individual timesheet. For a payroll batch containing an approver's own payslip, isolate that payslip/scope for another approver unless an explicitly scoped subject-interest exception permits it. Preview explains conflicts before submission. Define the maker set from the submitted transaction/change authors, not merely `create_uid` or every historic editor. Payroll maker/submitter exceptions below are owner-requested; they do not automatically waive subject-interest conflicts, bank mandates or scheme-change governance.

### 7.2 Payroll self-approval exceptions (confirmed requirement)

The payroll policy offers **Require independent approval** (default) and **Allow selected self-approval exceptions**. Enabling the latter requires the publisher to choose the affected steps, company/division/scheme/run kind, eligible people or scoped responsibilities, conflict kinds (maker and/or submitter), any expiry/limit, and a policy-change reason. Default limits may be absent if explicitly configured; do not invent a monetary cap. An optional **May approve a run containing their own payslip** is a separately named conflict waiver and is off by default.

At a matching decision, replace the usual button with **Approve with exception**. Show “You prepared/submitted this payroll” and require a nonempty transaction-specific reason. Confirm the exact step and affected scope. Record actual actor, conflict type, policy/version, scoped grant, reason, timestamp and source revision in an immutable exception event linked to the decision. Show an **Exception used** badge in the request trail and an audit filter/report; include exception usage in notifications to the configured workflow owner. Ordinary non-conflicting approvals do not demand an exception reason.

The workflow editor presents scope, actor and reason settings as one form; the separate grant record described below is an implementation detail. Selecting an eligible exception never requires the novice to understand two security objects.

An exception waives only the selected independence conflict. It never grants record access, adds someone to the assigned route, auto-approves a step, suppresses evidence, bypasses thresholds, or lets one person count as two required members of a joint approval. It cannot waive a bank mandate. Repeated-person-across-steps permission is a separate explicit setting: if enabled for payroll, require an exception reason at each repeated decision; if disabled, send to a different eligible person. Both settings are clearly listed in publication impact.

Preview shows **“Can approve with a reason under [exception policy]”** rather than “Cannot submit” for a valid scoped conflict waiver. At runtime recheck that scope/eligibility and expiry still permit the exception; expired/revoked grants block and offer reassignment. Store the published exception policy on the request, while an independently revocable grant controls current permission to use it. Revocation can remove permission, never silently add new permission to an old request. Authorization to manage exception grants is separate from permission to edit payroll results. No implicit global administrator bypass.

Each joint step contains required seats. One natural person cannot fill two required seats, including by delegation. Default distinct-person policy also prevents one reviewer from satisfying successive required reviews on the same request; payroll may explicitly allow the audited repeated-person exception above. An insufficient number of eligible people after applicable exceptions is blocking; never silently collapse steps.

Backups are seat-specific. A delegation has principal, delegate, scope, start/end, authority and reason; no delegation chains or self-delegation. Resolve and record an applicable delegation when a step activates. If it changes mid-step, use an explicit, logged reassignment. Reassignment does not erase a previous completed valid decision. Reject cycles and conflicts, including one backup proposed for both required joint seats.

The workbook's “respective Line Manager” backup may already have completed the preceding step, so it must be reviewed. “Per bank mandate” cannot supply an executable backup identity. No email-only or typed-name signature satisfies an internal decision.

## 8. Versioning, publication and governance

Definition lifecycle: Draft → Published (possibly scheduled) → Superseded / Archived. A published revision is immutable. Editing creates a new draft with expected revision. Rollback publishes a new revision equivalent to a previous one, preserving history.

Binding changes are versioned/effective-dated too. Workflow, binding, roles, delegation and calendar changes appear in History, with who/when/why and affected scope. Archive prevents new use, while existing requests remain visible and completable under their pinned version. Pause blocks new submissions and retains queued requests; it must explain how to resume.

Publication validation includes schema correctness, nonempty applicable approval path, unsupported conditions, effective-date overlaps, role coverage, eligibility, independence, delegation conflicts, evidence definitions and calendar resolution. Run scope analysis over every covered segment, not only a sampled employee. Conditions also need boundary scenarios; coverage is a current result, not a guarantee about future employees. Revalidate at submission.

Capabilities: view configuration, edit scoped drafts, publish scoped revisions, bind scoped schemes, maintain scoped responsibilities, reassign pending steps, decide assigned requests, inspect audit. Separate publication power from approval power. Workflow admins do not become payroll approvers.

Policy changes require authorized publisher and an audit reason/impact review; a second administrator sign-off is an optional later governance mode. If added, use a protected company-level governance policy that cannot approve its own replacement or be overridden by the scheme being governed. Similarly, scheme-change workflows are managed independently from formula editors: a proposal cannot remove its own approval requirement.

## 9. Runtime semantics and invariants

### Request states

`draft → pending → approved`, with `pending → returned | rejected | cancelled | blocked`. Returned requests may be edited and resubmitted as a new attempt. Blocked preserves the underlying active step and completed decisions; repair returns to pending. Rejected/cancelled requests remain in history. Cancellation is an explicit permissioned action, not generic write access.

Steps progress sequentially. A joint step opens its seats together, and completes only when all required independent seats approve. In any-one mode, the first valid decision closes the seat. Concurrent approve/reject operations are serialized under a request lock; the losing caller receives the current result, not an overwritten history.

The same user pressing Approve twice must produce one decision. Require idempotency keys and expected request/step revision. Unique constraints complement transactional locking. A notification retry never repeats a business transition.

### Frozen facts and evidence

At submission, freeze object revision/hash, company/scope, amounts/currency/hours, relevant formula/release IDs, attachments/report checksums, evaluated conditions, route, selected binding/version and principals. Evidence added later must be explicitly allowed by the step and appended with provenance; replacing decision-relevant evidence invalidates the attempt.

Decision-relevant changes after submission invalidate authorization: return/revise and create a new attempt. The initial safe rule is to restart required approvals after a material change, not guess which completed signatures survive. Keep prior decisions and a before/after explanation. Trivial comments do not invalidate.

Default Send back is **Return to preparer**, cancels pending tasks, and makes material edits possible through the adapter. Keep legacy one-stage send-back/finished-run undo for legacy requests only. New undo/reopen needs a scoped authorization process and must be blocked after external payment/delivery/accounting facts make reversal unsafe. Never equate Undo with reversing bank funds.

### Conditions and timing

Allowlisted facts have explicit type and unit: Boolean overtime included, decimal payroll net total in a named currency, variance %, integer employee count, hours per person/year, run kind. v1 supports a flat All/Any condition group per step, with equality/in/range/comparison operators. No arbitrary Python/SQL/domain execution. Reject unsupported operators, missing facts and currency mismatch. If a condition skips all required approvals, fail validation; no implicit straight-through approval.

Working-time targets use an explicitly selected calendar. Whole-request and per-step deadlines are separate; the displayed effective step deadline is the earlier applicable one. Past deadline at submission produces an overdue request and escalation unless the process explicitly has a hard business cut-off, in which case submission is blocked. Calendar changes do not silently alter existing due dates. A deadline adjustment requires reason/history.

Notification schedules are idempotent, retryable jobs. Persist outbox rows in the same transaction as the event; delivery happens after commit. Do not put wages or bank details in email subject/notification snippets. Deep links recheck authentication and authorization.

### Side effects

Approval records authorize; adapters execute domain transitions. Finalization must verify every required decision and exact source revision again under lock. Same-database writes must be atomic; failures leave a retriable state without partially approved/published domain records. External effects use an idempotent outbox and report “Authorization complete · action pending/failed” separately.

Payroll approval does not itself transfer funds. Bank file creation pins bytes/hash, beneficiary set, bank-account revision, currency and control total. Regeneration or bank-detail changes require new authorization. Bank release completion requires external confirmation or a clearly labeled manually recorded confirmation with evidence; internal approvals alone cannot set “Paid.”

## 10. Proposed technical architecture

### 10.1 Modules and ownership

- Extend `biz_approval_chain` with the generic versioned engine, preserving its existing mixin API for unmigrated objects. If a separate `biz_approval_workflow` module is cleaner, it must depend on the old log/kit and be the only new runtime engine. Decide once in foundation work.
- New `pb_approval_config` owns Payobook configuration UI, facades and scoped responsibilities; depends on the shared engine and existing kit/access interfaces.
- Domain integration modules own payroll/scheme/time/payment adapters. Avoid importing payroll into the generic engine. Registry exposes only installed and supported adapter capabilities.
- Extend `pb_approval` to consume normalized request summaries; the legacy facade remains until its records have drained.
- Reuse one `ApprovalWorkflowSummary`, `ApprovalWorkflowEditor`, `ApprovalRoutePreview` and `ApprovalReadiness` across hub, scheme Settings and Blueprint.

### 10.2 Proposed persistent records

| Model | Essential fields / rules |
|---|---|
| `biz.approval.workflow` | company owner, name, type, owner user, active; stable identity |
| `biz.approval.workflow.version` | workflow, revision, schema version, immutable step/condition/evidence snapshot, status, published_by/at, effective_from; unique workflow+revision |
| `biz.approval.binding` | company, type, scheme/division optional, run kind, workflow, follow/pin, pinned version, effective interval, pause, revision; reject ties/overlaps transactionally |
| `biz.approval.responsibility` | company, optional division/scheme, named business seat, single/pool mode, explicit fallback policy, effective interval, authorized user(s), reference to existing access role if applicable |
| `biz.approval.exception.grant` | scoped eligible people/responsibilities, conflict kinds, expiry/revocation, authority/reason, policy linkage; separate from object edit permissions |
| `biz.approval.delegation` | principal, delegate, seat/scope, effective interval, authority, reason; no cycles |
| `biz.approval.request` | adapter type and constrained source reference, source attempt/revision/hash, company/scope snapshot, maker/subject set, binding/version, state, current step, deadlines, lock revision |
| `biz.approval.request.step` | request, stable step key, sequence, evaluated inclusion, mode, status, due_at, completion_at |
| `biz.approval.request.seat` | step, seat key, principal/candidate snapshot, activated delegate, status; unique seat identity |
| `biz.approval.decision` | request/step/seat, actual actor, acting-for, action, reason, timestamp, source hash, idempotency key; immutable |
| `biz.approval.evidence` | source attachment/report reference, checksum, revision, who supplied it, requirement key; ACL follows request and document |
| `biz.approval.event` or compatible existing log extension | append-only lifecycle/assignment/decision provenance; links existing `biz.approval.step.log` and audit console |
| `biz.approval.outbox` | event, delivery/action type, recipient/reference, unique dedupe key, retry state; restricted access |
| `pb.payroll.timesheet.submission` (if no installed durable equivalent exists) | employee/employment, period, company/scheme/division, attendance/import source rows and snapshot, attempt, request; uniqueness prevents duplicate overlapping authorized hours |
| `pb.scheme.change.proposal` | config, candidate milestone/version boundary, change kind (activate/release/rollback), request, applied state; does not duplicate formula-version history |

Use Odoo 19-compatible `models.Constraint` patterns observed in the repository, not ignored legacy `_sql_constraints`. Scope custom record rules by company and permitted division/subject. Constrain generic model references to the adapter registry; never accept arbitrary model/method names from the client. Audit/evidence data is not deleted by ordinary archive or source deletion; preserve tombstones/provenance according to existing retention policy.

### 10.3 Adapter contract

Each adapter implements equivalents of:

1. `get_submission_context(record)` — scope, facts with units, maker/subjects, immutable source revision and evidence; caller access enforced.
2. `validate_submission(record, context)` — domain readiness and mixed-scope checks.
3. `freeze_submission(record, attempt)` — snapshot/lock decision-relevant fields.
4. `serialize_for_actor(request, actor)` — permitted facts and evidence, no scope leak.
5. `apply_outcome(request, outcome)` — atomic/idempotent guarded domain transition against frozen facts.
6. `return_for_revision(request, reason)` — controlled edit path and invalidation policy.
7. `capabilities()` — supported facts, evidence, deadline anchors, scopes and actions.

Resolver and adapter code are server authoritative. UI is a projection, not an authorization layer.

Persistence detail for configuration implementers: normalized editable draft steps/seats/conditions may live as child records, while publication compiles one validated immutable version snapshot. Treat the published snapshot as the runtime source of truth and the draft as editable authoring state. Store stable step/seat keys across revisions for meaningful comparisons; copy changes into a new version, never update an existing published step through a shared relation. Define a versioned serializer and validate all imported drafts through the same schema.

### 10.4 Facade and payload contract

Proposed configuration RPCs: `list_workflows(filters, cursor)`, `get_workflow(id)`, `save_draft(id, expected_revision, draft)`, `preview_route(draft_id, example)`, `validate_coverage(draft_id)`, `publication_preview(draft_id)`, `publish(draft_id, expected_revision, impact_fingerprint, effective_from)`, `get_scheme_approvals(config_id)`, `set_scheme_binding(config_id, expected_revision, selection)`.

Proposed runtime RPCs: `list_requests(filters, cursor)`, `get_request(id)`, `submit(adapter_key, record_id, expected_source_revision, idempotency_key)`, `decide(request_id, step_key, action, reason, expected_revision, idempotency_key)`, `reassign(request_id, seat_key, person_id, reason, expected_revision)`.

Every method checks object access and scope first, including list/search/count/preview endpoints. Example API response (illustrative names/IDs, not source configuration):

```json
{
  "status": "blocked",
  "draft_revision": 7,
  "selection": {"source": "scheme_division", "binding_id": 41, "workflow_version": 2},
  "summary": "Line manager review, then HR approval",
  "steps": [
    {"key": "manager_review", "label": "Line manager review", "included": true,
     "mode": "any", "people": [], "due_at": null},
    {"key": "hr_approval", "label": "HR approval", "included": true,
     "mode": "all", "people": [{"id": 52, "label": "Example HR lead"}], "due_at": null}
  ],
  "issues": [{"code": "missing_manager", "severity": "blocking",
              "message": "Choose a line manager for this employee.",
              "field_path": "steps.manager_review.people", "fix": "open_employee_manager"}],
  "side_effects": false
}
```

Validation errors use stable codes and translatable messages. Return conflicts without overwriting other sessions. Paginate list endpoints; bulk-resolve hierarchy/role coverage to avoid per-person query explosions. Target a normal first screen under 2 seconds and a single-record preview under 1 second on the deployed reference tenant; measure and report actual results rather than claiming these targets are achieved.

## 11. Payroll and scheme compatibility: explicit migration choices

### Payroll state projection

Do not fit arbitrary dynamic steps into `level0/level1/level2`. Introduce a separate managed-approval flag/request relation and a new non-final run state such as `approval_pending` in the custom adapter. Add supported `ondelete` behavior and migration. Dynamic labels come from request steps.

Legacy records retain existing state keys and methods. Managed submissions enter `approval_pending`; payslips remain in a non-final state consistent with current confirmation behavior. Only the managed adapter's finalizer can make run/slips `done`. Inventory and update every consumer that filters pending states: cockpit, wizard, analytics, exports, payslip delivery, undo/reset and legacy native buttons. Intermediate legacy methods must reject direct advancement on managed records. Test individual payslip approval routes as well as run routes so a child record cannot bypass the parent workflow.

Reuse the domain side-effect bodies through private guarded helpers where possible; do not replay the fixed public approval actions as if an arbitrary new actor belonged to all three old permission groups. Do not implement a global `sudo()` bypass to make it work. Preserve existing accounting hooks and compensation inclusion rules.

### Scheme change approval

Current formula edits and `release_approve` do not constitute a pending multi-person approval flow. For managed schemes, create an immutable **change proposal** containing the exact candidate versions before requesting decisions. Editors may prepare a later candidate but must not mutate the submitted one. Activation/release applies only that candidate after technical checks and final approval.

Do not let editing an active formula silently alter production calculations while approval is pending. Use the existing branch/version/milestone infrastructure to stage candidate changes; ensure payroll reads the last activated/approved revision. Audit direct writes/imports, branch merge, rollback and activation paths. If the current evaluator cannot resolve a sealed effective revision, implementing that boundary is a prerequisite for claiming scheme-change approval, not an optional polish item.

Scheme Settings shows its two separate workflow bindings. However, permission to edit a scheme is not permission to alter its own scheme-change governance. Future governance updates apply only after independently authorized publication. Existing `hr.formula.release` remains the record of completed release sealing. Client review acknowledgment stays attached as separate evidence.

### Payroll timesheets

The initial packet is an employee/employment/period submission of the exact imported or attendance-derived payroll hours. It records source rows, versions, type of hours and corrections. Manager/HR decisions approve that packet. Later changes require a new attempt, and payroll preparation references only approved packet revisions where the company enables this prerequisite.

Do not duplicate hour calculations or change leave/OT rules. Define the read adapter from the tenant's actual feed. Historical records with no provenance are marked legacy/unverified, not backfilled as “approved.” Project timesheets use their own process type/adapter because their approved analytical hours may have a different business meaning.

## 12. Migration and rollout safeguards

1. Read installed versions, current databases, company structure, active workflows, officer parameter, pending run counts by state, existing user capabilities, payroll-timesheet sources and downstream integrations. Produce an inventory with no mutations.
2. Introduce schema and feature flags per company/process. Keep all old requests on their old path. No blanket migration of every `biz.approval.chain.mixin` consumer.
3. Create a **Legacy payroll chain** baseline reflecting the officer setting, with provenance and actual groups. This baseline may expose gaps against the new independence policy; report them. Do not pretend importing the baseline makes it publishable as a new managed workflow.
4. Import the workbook matrix as source-linked drafts only in the intended company. Matching people is a reviewed step, not fuzzy auto-assignment. Preserve “Ready” as source metadata alongside application readiness.
5. Shadow-preview new routing against representative records and all current covered scopes. Show differences from legacy behavior and fix identities, ambiguity and capabilities.
6. Activate new submissions by company/process with an explicit effective time. Display coexistence of legacy requests and managed requests in the inbox. Keep pending legacy Officer-tier runs visible even if new workflows omit that step.
7. After legacy submissions are disabled, make the old officer setting read-only with a link to Approval workflows. Retain its read path for legacy records. Do not maintain two editable policy controls for the same new submission.
8. Rollback stops new managed submissions or restores a previous published policy. It does not rewrite approved decisions or downgrade paid runs. Keep the new runtime available until its active requests drain; database restore is a separate operational recovery choice.

## 13. Acceptance criteria and test matrix

### Novice UX success criteria

- A person unfamiliar with the product can configure Manager → HR, assign one division, successfully preview, and publish without help or internal vocabulary. Moderated target: under five minutes after accounts and hierarchy already exist; measure with representative users.
- A scheme owner can explain whether a workflow is inherited, shared or custom from its summary card without opening an expert screen.
- A person can identify who will approve, what they see, and why a route was selected. A missing manager has a direct repair path.
- No successful simulation, import “Ready” cell, completed wizard, or published definition alone claims every future request is approvable.
- Every visible action works; unsupported types are visibly unavailable. UI behavior is consistent at 1440, 1024 and 390 px and in English/Vietnamese.

### Required automated and deployed checks

| ID | Scenario | Expected result |
|---|---|---|
| A01 | Company/division/scheme/exact exception precedence | Deterministic route as §6 |
| A02 | Equal-rank overlapping effective bindings, including concurrent publish | One publication fails; no ambiguous runtime route |
| A03 | Cross-company division | No policy/people/data bleed |
| A04 | Exact run-kind vs Any kind | Exact wins within rank; boundaries tested |
| A05 | Paused winning binding | Submission blocked, no fallback bypass |
| A06 | No applicable policy / unsupported adapter | Actionable failure; no state change |
| A07 | Shared update, pinned scheme, scheduled version | New eligible submissions change; pins and old requests remain fixed |
| A08 | Archive/rollback | Old requests remain auditable/completable; new use follows explicit policy |
| A09 | Missing/deactivated manager, hierarchy cycle, ambiguous role holder | Block or require explicit repair; no “all HR” fallback |
| A10 | Maker=self, manager=self, approver's own payslip | Independence conflict before decision; split/reassign path |
| A11 | Joint Nithya/Monica seats | Both independent decisions required; duplicate click does not count twice |
| A12 | Same delegate across two seats / delegation cycle / expired grant | Refused; no collapsed quorum |
| A13 | Reassignment and permission revocation during request | Current access rechecked; logged reassignment; no hidden rerouting |
| A14 | Concurrent approve/reject/finalize | Serialized outcome, truthful loser response, one finalization |
| A15 | RPC state write/context forgery, create-in-approved-state | Server refuses on request, run and relevant child objects |
| A16 | Evidence replaced / source changed after submission | Prior authorization cannot finalize new facts |
| A17 | Return, edit, resubmit | New attempt, correct recalculation, prior audit preserved |
| A18 | Conditional boundary and missing units/currency/facts | Correct inclusion; bad/missing facts block; no empty approval route |
| A19 | Working day/holiday/timezone/Day 15/penultimate day | Exact due timestamp; past deadlines/cut-offs behave as §9 |
| A20 | Failed notification and retry | Decision commits once; eventual delivery without duplication |
| A21 | Bank file regeneration/account change/payment retry | Authorization invalidated where needed; no false Paid status |
| A22 | Mixed schemes/divisions/currencies in a run | Preview detects; submission blocked until reviewed split; payslips/totals conserved |
| A23 | Legacy Officer off/on and requests already at level0 | Old behavior preserved; no stranded or hidden requests |
| A24 | Managed finalization and direct legacy/child entry points | No bypass; run/slip/accounting/compensation side effects correct |
| A25 | Formula release/activation/import/rollback/branch merge | Exact candidate approved; active payroll cannot consume unapproved edits |
| A26 | Public review token signoff | Records acknowledgment only; does not fulfill internal decision |
| A27 | Blueprint old JSON and open setup drafts | Coercion works; Connect/Finish agree; draft can finish without activating |
| A28 | Scheme-specific edit and shared edit | Scope shown correctly; shared impact reviewed; custom does not mutate parent |
| A29 | Attendance/import change after timesheet approval | New packet attempt required; downstream payroll prerequisite enforced |
| A30 | Payroll vs project timesheet | Separate type and side effects; no double counting hours |
| A31 | Unauthorized list/count/preview/evidence/deep-link | No sensitive data or existence leak |
| A32 | Concurrent draft/binding update | Explicit conflict, no lost edit |
| A33 | Coverage scan vs one passing example | Whole-scope missing-person issue remains blocking |
| A34 | Cron/finalizer failure mid-transition | Atomic local state or explicit retriable external action; no partial success |
| A35 | Role changes after preview before publication/submission | Fingerprint/revalidation catches stale eligibility |
| A36 | Workbook rows 5–14 | Traceable drafts; unresolved source text remains unresolved; no automatic activation |
| A37 | Authorized payroll maker/submitter exception | Only configured actor/scope/step eligible; nonempty reason required and exception event visible |
| A38 | Exception absent, expired/revoked, wrong scope or missing reason | Approval refused; no bypass via RPC or client context |
| A39 | Exception actor in a joint step | One decision counts for one seat; another person still required |
| A40 | Same person at successive steps with explicit exception | Allowed only when configured; reason and conflict recorded at every affected decision |
| A41 | Responsibility hierarchy and company fallback | Specificity/explicit fallback respected; conflicting holders blocked; new requests resolve changed holders |

Chrome end-to-end paths after implementation: novice create→preview→publish; Connect inherit→customize→return→Finish; different divisions produce different approvers; two distinct authenticated users complete a joint step; unauthorized user cannot act via UI or RPC; missing manager→repair→preview; send back→revise→resubmit; pending request remains on old version after publication; mobile/VI; legacy request drain; payroll finalization and exact scheme proposal approval. Use deliberate test users and generated records, not real payment release.

## 14. Implementation work packages

| Package | Deliverable | Exit gate |
|---|---|---|
| W0 · Inventory and contract | Installed-state inventory, adapter source selection, current entry-point map, final owner choices | No unresolved model/source assumption hidden in implementation; approved design defaults recorded |
| W1 · Engine foundation | Versioned definitions, bindings, scoped responsibility adapter, resolver, immutable requests/decisions, locks, audit, timing/outbox, configurable audited payroll exceptions | A01–A20, A31–A35, A37–A41 at model level; legacy mixin regressions pass |
| W2 · Configuration experience | Library, four-step builder, example/coverage preview, people/backups, publish impact, reusable components | Novice journey works in Chrome with persisted drafts and real server validation |
| W3 · Payroll and Blueprint | Run adapter, dynamic inbox, compatibility state projection, Connect/Settings/Finish binding | A22–A24, A27–A28; whole payroll path including child bypass protection passes |
| W4 · Timesheets and scheme changes | Verified payroll-hour packet adapter; exact scheme candidate proposal, activation/release integration | A25–A26, A29–A30; payroll does not read unapproved hours/changes when prerequisites enabled |
| W5 · Matrix extensions | Leave/OT/project sheets, employee/salary/incentive changes, funding/journal, bank file/release, reopen/off-cycle | Each type has a real adapter, source mapping and tests; unsupported types stay unpublishable |
| W6 · Migration and polish | Tenant-specific drafts, controlled activation, legacy drain, translations, accessibility, performance | All applicable acceptance cases pass deployed; operational evidence complete |

W1–W4 form the first core release; W5 is the remaining source-matrix programme, not optional if the owner expects all ten matrix processes. Do not claim “all workflows implemented” after only payroll. Break packages into reviewable commits with tests. Read existing programme conventions and avoid module dependency cycles.

### Deployment completion contract for the implementing session

This session delivers documentation only. It does not deploy a product change or modify databases.

For every later code/configuration change, follow the owner's completion policy: commit relevant changes excluding concurrent work; recheck latest branch and working tree; deploy the latest combined relevant repository state to every in-scope environment/database; test the deployed version with Chrome for user-facing changes; report commit, target names and results; remove every PNG/screenshot created by that test run while preserving existing assets and other-session files.

Local `CLAUDE.md` identifies `/odoo/odoo-server/addons` as the single live addon destination and `payobook`, `abm`, `acme`, `payobook_template` as the database set at the time it was written. **Reverify targets and installed module scope before deployment**, because this design session has not connected to the server. Never deploy old vendored standard Odoo addons over server core. Never use a destructive delete against the entire addons root. Verify custom module content/version parity, upgrades and asset refresh where needed. If a required target/credential/test path is unknown, ask rather than silently skipping deployment.

## 15. Open business inputs and recommendation log

These do not prevent completing the design; they prevent falsely activating an unverified production policy.

| Input | Recommendation / required decision |
|---|---|
| Shared update adoption | Owner confirmed automatic application to future submissions with impact preview |
| Self-approval and repeated people | Owner confirmed configurable payroll self-approval exceptions with audit reason; exact defaults/limits in §7.2 |
| Timesheet scope | Owner confirmed attendance/payroll hours including imports; verify actual live feed at W0 |
| Meaning of “+” / “joint” | Propose all listed people for explicit joint rows; confirm role-to-person mapping and mandate |
| Unnamed reviewers / “Thao” identity | Match authenticated accounts explicitly; never infer from abbreviated names |
| Calendar anchors and SLA scope | Confirm company working calendar/timezone, cut-off hour, non-working-day rule, request vs step allowance |
| Annual overtime control | Preserve workbook value as proposed control; do not override current cap/bonus behavior without policy decision |
| Approval visibility | Use existing permissions/scopes; confirm restricted payroll-view capability for reviewers if needed |
| Mixed payroll groups | Split before submission in v1; confirm whether a parent batch is operationally required |
| Scheme change candidate model | Enforce last-approved revision for live calculations; verify evaluator/branch infrastructure before implementation |

## 16. Ready-to-use prompt for the next session

> Implement the Approval workflows programme described in `docs/handovers/APPROVAL_WORKFLOWS_DESIGN_HANDOVER.md`, using `output/pdf/approval-workflows-design.pdf` as the visual companion. Read both before coding. Start with W0 and verify the current repository and live module versions; the design baseline is historical. Preserve concurrent work.
>
> Build one reusable configuration experience and one authoritative versioned resolver. Reconcile Blueprint Connect (step 3 of 6), scheme Settings, formula activation/release and the legacy payroll tier engine. Distinguish payroll run approval, scheme-change approval and bank authorization. Use the hybrid role/manager/person picker, scoped roles and explicit scheme/division exceptions, with immutable requests, distinct-person joint approvals and working previews. Owner decisions: automatic shared updates for future submissions with impact preview; configurable payroll self-approval exceptions with audit reason; attendance/payroll hours including imported timesheets first. Do not treat the workbook's Ready labels as configured identities. Do not invent an existing durable payroll-timesheet model; verify the source.
>
> Complete each authorized implementation package with meaningful tests, focused commits, deployed checks on all verified in-scope databases and Chrome UI verification. Recheck the latest combined state before deployment. Remove only screenshots/PNGs generated by your testing. Report remaining packages explicitly; never call a configuration-only facade a working approval feature.

## 17. Design verification record

- All ten matrix rows and their timing/evidence/identity ambiguities were transcribed and reconciled against source cells.
- Blueprint step order, informational guard/status, payroll tier parameter, division model, formula release and public acknowledgment paths were checked in local source.
- The PDF contains static vector screen designs with illustrative data; no live user, workflow, account assignment, payment or database was created.
- The Markdown contract is authoritative for behavior. Screen counts, names other than workbook examples, and dates are illustrative and must be replaced by live derived values.
- Artifact layout, PDF text and local links are checked before delivery. Runtime, deployed and Chrome product tests are not applicable to this documentation-only delivery; they remain required for implementation.
- Final artifact QA: ten PDF pages rendered and visually inspected; source references and local links checked; 41 unique acceptance scenarios enumerated. Owner responses are incorporated in the policy, visual screens and next-session prompt. Temporary rendered PNGs are removed before completion.
