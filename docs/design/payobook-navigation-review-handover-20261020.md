# Payobook navigation design handover for independent review

Prepared on 20 October 2026. Design baseline reviewed on 19 October 2026. Status: proposed and awaiting the owner’s implementation decision.

This handover explains the proposed navigation, its business reasoning, the screens it requires, and the limits of the supporting evidence. Another model can review the design from this file alone. Repository access and the original HTML help with technical verification and visual review, but are not prerequisites for understanding the proposal.

The recommendation is to reorganize Payobook around clear business domains, reuse its working transaction and approval systems, and add selected operational views. The original Word proposal provides useful business coverage; its individual statuses, fields, metrics and buttons should not all become menu entries.

## 1 How to use this handover

Attach this file to the reviewing model and give it the prompt below. Optionally attach `payobook-navigation-review-20261019.html` to show the icons, interactive menu explorer and dashboard compositions. The HTML is a design prototype, not a connected application.

The contents have four purposes:

- Sections 2–6 establish the problem, evidence, decisions and interaction model.
- Section 7 specifies every proposed menu destination, including its purpose and implementation treatment.
- Sections 8–11 explain the build packages, dashboards, data boundaries and example user journeys.
- Sections 12–16 identify unresolved decisions, technical verification points, rollout constraints and the expected review output.

### Ready to copy review prompt

```text
Act as an independent senior HRIS and payroll product architect reviewing the attached Payobook design handover.

The owner wants your critical assessment before deciding whether to implement it. Review the design; do not implement, deploy, change permissions or modify application/database records.

Read the evidence classifications carefully. Live observations are a dated snapshot. Source-code support does not establish installation, configuration or correctness across every database. A proposed feature or unresolved assumption is not a verified current capability.

Assess whether the navigation is easy to understand for employees, managers, HR, recruiters, payroll and finance. Challenge the domain boundaries, menu depth, terminology, role perspectives, duplicate destinations, dashboard usefulness, and the proposed first release. Check that new screens reuse existing records and that genuine new processes or integrations are identified honestly.

Pay particular attention to payroll readiness, effective-dated employment changes, expense payment reconciliation, confidentiality, multi-company scope, and the separation of employee training from product help. Review the later manufacturing, mentoring, succession, corporate-card and booking scope without assuming those capabilities already exist.

Use the destination references, D decision IDs, A work-package IDs and J journey IDs when making findings. Do not approve a choice simply because another model proposed it. Preserve useful existing capabilities and propose alternatives only when they solve a concrete user or control problem.

Return:
1. A verdict: adopt, adopt with changes, or redesign, with the main reasons.
2. Ranked findings with severity, exact reference, user/control impact, recommended change and evidence still needed.
3. A revised menu only where you recommend a change, explaining the tradeoff.
4. A first-release scope separated into navigation work, views over existing records, genuinely new workflows/data, and external integrations.
5. Acceptance criteria and the owner decisions needed before implementation.

If you lack code or live access, state which conclusions are architecture judgments and which technical claims require verification. Do not invent test results, installed modules, vendor capabilities or implementation estimates.
```

## 2 Product context and the problem to solve

Payobook is an Odoo 19 based HR and payroll application. Its repository contains custom modules for people, employment contracts, payroll, recruitment, workforce time, approvals, lifecycle journeys, expenses, learning, goals, compliance and integrations. The demo site is `https://payobook.com`; the backend uses `/bizapp` and employee self-service uses `/my`.

The owner supplied `RIZE/Payobook Menu-Sub Menu-.docx`, a broad HR administrator capability map. It covers recruitment, employee lifecycle, workforce operations, travel, expenses, payroll, performance, learning, HR services, analytics, governance and system administration. It also proposes manufacturing productivity and longer-term talent programmes.

The immediate problem is findability and ownership. Several substantial capabilities already exist but are grouped in places that may not match the user’s working day. For example, Hiring is inside Lifecycle, Trips is inside Workforce, and Learn combines product tutorials with employee training. The proposal also mixes durable destinations with record statuses and individual actions.

The owner requested an assessment and an HTML proposal before deciding on implementation. No application implementation has been authorized by that design request. This handover preserves that proposed design for independent review; it does not record owner approval.

### Recommendation in one page

1. Use an expandable primary menu with one submenu level. Complex workspaces can then have local tabs, boards, calendars and filters.
2. Use ten business entry points: Home, People, Hiring, Talent and learning, Workforce, Payroll, Travel and expenses, HR services, Insights and Governance. Put Settings and Help in utility positions.
3. Give Hiring a direct entry. Put joining, changing and leaving under People → Lifecycle. Keep employee training and performance together in Talent and learning.
4. Keep a distinct personal workspace, using the current employee portal. Add a coherent manager view rather than granting a manager the administrator’s full menu.
5. Reuse employee, contract, application, claim, payroll and approval records. Add aggregate lists and dashboard compositions where existing records are hard to work across.
6. Retain one approval engine and one shared Inbox. A domain’s approvals shortcut is a filtered entry into that Inbox. Ordinary HR questions remain conversations.
7. Make readiness and payment states evidence-based. An attendance evidence lock, an approved pay run, a published payslip and a confirmed payment are different facts.
8. Keep manufacturing analytics, corporate-card/booking integrations and general career/succession/mentoring programmes out of the initial rollout until their data and workflow requirements are agreed.

The complete reference has 12 entry points including the two utilities and 66 submenu destinations. This is broader at the primary level than the current administrator rail, which has ten entries including Settings. The intended benefit comes from clearer ownership and role filtering, not from claiming that fewer primary entries are always better.

### Proposed menu at a glance

The labels below show the complete reference, including Later scope. The working application should show only enabled, delivered and permitted destinations.

```text
Home
  - My day [Extend]
  - Inbox [Extend]
  - Announcements [Reuse]

People
  - Employee directory [Reuse]
  - Organization [Extend]
  - Contracts and compensation [Reuse]
  - Lifecycle [Extend]
  - Documents and assets [Extend]
  - Workforce planning [Reuse]

Hiring
  - Hiring overview [Extend]
  - Requisitions and jobs [Extend]
  - Applications [New]
  - Candidates and talent pool [Extend]
  - Interviews [Reuse]
  - Offers and joining [New]

Talent and learning
  - Talent overview [New]
  - Goals and reviews [Reuse]
  - Development and growth plans [Extend]
  - Courses and assignments [Reuse]
  - Skills and certifications [New]
  - Recognition and engagement [Extend]
  - Career paths and succession [Later]

Workforce
  - Today and coverage [Reuse]
  - Schedules and shifts [Reuse]
  - Attendance [Reuse]
  - Project timesheets [Extend]
  - Time off and holidays [Reuse]
  - Overtime [Reuse]
  - Period close and handover [Extend]
  - Field workforce [Reuse]
  - Production labour deployment [Later]

Payroll
  - Payroll overview [Extend]
  - Current run [Reuse]
  - Pay runs [Reuse]
  - Payroll inputs [Reuse]
  - Results and payslips [Reuse]
  - Adjustments and settlements [Reuse]
  - Payments and delivery [Extend]
  - Payroll calendar [Reuse]
  - Variable pay and awards [Reuse]

Travel and expenses
  - Spend overview [New]
  - Trips [Reuse]
  - Expense claims [Extend]
  - Reimbursements [New]
  - Allocation and spend reports [Extend]
  - Travel bookings and cards [Later]

HR services
  - HR request board [Reuse]
  - Service reports [New]

Insights
  - Dashboards [Extend]
  - Reports and explorer [Extend]
  - Scheduled reports [Later]
  - Manufacturing analytics [Later]

Governance
  - Compliance workbench [Extend]
  - Filings and statutory reports [Reuse]
  - Policy library [New]
  - Audit trail and controls [Reuse]
  - Workforce safeguards [Reuse]

Settings [utility]
  - Organization and masters [Extend]
  - Users and access [Reuse]
  - Payroll configuration [Reuse]
  - HR and operations configuration [Extend]
  - Workflows and notifications [Reuse]
  - Integrations and data [Reuse]
  - System and localization [Reuse]

Help and product guides [utility]
  - Guides and tutorials [Reuse]
  - Product support and releases [Extend]

```

Section 7 defines the purpose, local views, icon and source foundation of each entry.

## 3 What is known and what is proposed

### Evidence classifications

| Classification | Meaning | What it does not establish |
| --- | --- | --- |
| Observed in the demo | The prior review opened the signed-in demo navigation and relevant hub tabs on 19 October 2026. | Every role, tenant or database has the same menu, configuration or working end-to-end flow. |
| Supported by source | Relevant models, views, registries or workflow code were inspected. | The module is installed, correctly configured and fully tested in a particular database. |
| Proposed design | A recommended grouping, screen, control, interaction or acceptance requirement. | The capability already exists or has been approved for implementation. |
| Unverified | The review did not establish a complete implementation of a capability. | The capability is definitely absent from every module or database. |

The handover transcribes the design baseline; it does not perform a fresh live audit on 20 October. Facts about current deployment must be rechecked if they affect implementation.

### Destination treatment labels

| Label | Meaning |
| --- | --- |
| Reuse | Keep an existing screen or workflow and make it easier to reach. Verify the specific proposed detail before implementation. |
| Extend | Improve or compose an existing surface. This may still require new queries, adapters, fields or workflow controls. |
| New | Create a new view or a genuine new process. A new view can use existing models and does not necessarily require a new transaction table. |
| Later | Excluded from the proposed launch menu; requires a separate scope decision. |

The 66 destinations contain **31 Reuse, 22 Extend, 8 New and 5 Later** classifications. These count navigation destinations, not engineering tasks or effort. There are 12 work packages in section 8; one package may affect several destinations. A treatment label also does not specify the rollout phase.

### Vocabulary used in the design

| Term | Meaning in this proposal |
| --- | --- |
| Domain | A durable business area such as Hiring or Payroll. |
| Destination | A submenu entry that opens an object list, workbench, dashboard or other stable workspace. |
| Local view | A tab, board, calendar, grouping or saved filter inside a destination. |
| Record action | Create, Submit, Approve, Publish, Export or another permitted operation on the relevant record or population. |
| Operational dashboard | A view of current exceptions, owners and next actions. |
| Analytical dashboard | Historical analysis with defined measures, populations and comparison periods. |
| Person and employment | A human identity and that person’s entity-specific employment/contract relationships; these must not be conflated. |
| Product learning | Guidance on using Payobook. It belongs in Help. |
| Employee learning | Job training, assignments, tests and qualifications. It belongs in Talent and learning. |

## 4 Current navigation observed in the demo

This is the dated baseline against which the design was proposed.

| Current primary entry | Observed hub tabs or views | Proposed treatment |
| --- | --- | --- |
| Home | Pulse, Approvals, Wall, Announce | Keep role home and shared Inbox; consolidate announcement reading. |
| Pay Run | Run, Runs, Payslips, Results, Import, Deliver, Adjust, Settle, Calendar, Awards | Rename the domain Payroll; group related destinations and preserve existing tools. |
| People | Employees, Records, Pay, Where they work, Assets, Praise, Goals, Announce, Plan | Keep employee operations here; move talent and announcements to their clearer owners. |
| Ask HR | Kanban/list with New, With HR, Answered, Closed | HR services for operators; Ask HR remains the employee-facing label. |
| Lifecycle | Journeys, Hiring, New joiners, Exits, Probation, Growth plans, Contracts | Expose Hiring directly; People owns employment lifecycle; Talent owns restricted growth cases. |
| Workforce | Today, Schedule, Time, Time Off, Overtime, Trips, Approvals, Close, Holidays, Field | Keep time and coverage; move travel; reuse Inbox and close tools. |
| Insights | Pulse, Explorer, Workforce, Payroll Report, Budget, Hiring, Training, Goals | Organize existing analytical views into Dashboards and Reports. |
| Compliance | Filings, Bank, Young workers, Audit | Governance owns oversight; Payroll reaches bank verification during payment readiness. |
| Learn | Lessons, Training, Team, Settings | Separate product guides from employee training. |
| Settings | Payroll engines/defaults, organization/tenant tools, integration, access, approvals, hiring, support/about and other administration | Group by domain and privilege. Keep platform/demo operations out of normal company administration. |

The employee portal already exposes personal pay and payslips, profile changes, documents/assets, time, leave, overtime, project time, trips, expenses, goals, training, recognition, requests and Ask HR. The proposed personal workspace is a clearer presentation of those capabilities, not a new employee database.

The current Records Desk remains a governed bulk-data workbench. The proposal retains an authorized toolbar/search entry from People and Payroll inputs rather than creating another employee directory.

## 5 Design decisions and the reasons behind them

Each decision is proposed and open to challenge. The reviewer should distinguish a different preference from a concrete findability, workflow or control problem.

| ID | Proposed decision | Reason | Tradeoff to evaluate |
| --- | --- | --- | --- |
| D01 | Ten business entry points plus Settings and Help utilities; filter by role and enabled feature. | Exposes independent working domains while avoiding the full administrator map for every user. | The complete rail grows to 12 entries. Test scanability, scrolling and which roles need each domain. |
| D02 | Two sidebar levels, with local tabs for complex workspaces. | Keeps locations stable while statuses and process steps remain close to the records. | Lifecycle and other complex work may become less immediate. Search, pins and role landing pages must compensate. |
| D03 | Give Hiring its own primary entry. | Recruitment is a distinct working day and has users who do not perform general employee lifecycle administration. | Adds a root entry; the existing Hiring implementation must be reached without creating a second hiring product. |
| D04 | Put Lifecycle inside People. | Joining, probation, employment changes and exits concern the employment relationship. | Frequent HR operators may value the current direct Lifecycle entry. Validate with task tests. |
| D05 | Combine performance and employee training under Talent and learning; move product tutorials to Help. | Separates learning for the job from learning to use Payobook. | The combined talent domain is broad; training administrators and managers need focused perspectives. |
| D06 | Combine Travel and expenses. | Trip authorization, advances, receipts, claims and reimbursement form a connected spend journey. | Some organizations have distinct travel and finance owners. Preserve their permissions and transaction states. |
| D07 | Keep one shared Inbox, with filtered domain shortcuts. | Avoids duplicated approval queues and contradictory decisions. | Checklist tasks and approval requests are different objects; adapters must preserve their semantics. |
| D08 | Keep one employee profile and canonical source records. | Personal, employment, document and pay views should not become separate copies of the employee. | Aggregate lists and cross-domain drilldowns must keep identity, access and source ownership clear. |
| D09 | Separate operational action views from historical analytics. | A payroll blocker queue and a payroll cost trend answer different questions. | Domain overview and Insights charts can still duplicate measures if they use separate definitions. |
| D10 | Put policy oversight and audit in Governance; keep rule editing in Settings. | Reviewing controls differs from configuring how a calculation or approval works. | Users may not understand the boundary; contextual links must reach the same canonical definition. |
| D11 | Put bank verification in Payroll payment readiness, with oversight links from Governance. | It is most actionable when preparing payment. | Retain independent verification permissions and audit ownership. |
| D12 | Use statuses as filters and actions as buttons. | Draft, Approved, Create and Export do not need independent global locations. | A high-volume specialized queue may merit a saved destination if user testing proves the need. |
| D13 | Defer capabilities that require a new product/data contract. | A menu item alone cannot deliver manufacturing analytics, card matching or succession. | Hidden future scope must not obscure a real contractual customer requirement. |
| D14 | Preserve old links, source controls and server authorization during cutover. | Navigation improvement should not alter transaction outcomes or invalidate bookmarks. | Route compatibility and active-menu ownership require explicit migration work. |

The icon vocabulary is the existing shared Lucide-style line icon set. Icons support text labels; they do not replace them. Section 7 gives the prototype’s exact icon keys for consistent review. Those keys are design references, not newly installed assets.

## 6 Navigation behavior and role perspectives

### Interaction rules

- Primary domain selection exposes its submenu. Selecting a submenu opens the associated workspace and makes its location clear.
- Use a domain landing view only when it helps that role. The selected role’s frequent work should not be buried behind a generic company dashboard.
- Local tabs hold coherent views of a domain’s records. Statuses normally use filters, board columns or saved queues.
- Preserve list search, filters, sort, scroll position and back context after opening a record and returning.
- Carry relevant company, location, country, pay group, period, currency and timezone context. Show the scope visibly when it changes the meaning of results.
- Search, pins and contextual links use the same destination catalogue and access logic as the menu. They supplement visible navigation.
- Retain old action routes and aliases. Prototype keys in section 7 are references, not finalized production routes or Odoo XMLIDs.
- A disabled/uninstalled feature has no live destination. An enabled feature with no records has a useful empty state. An unavailable source shows an error/unavailable state, not a misleading zero.
- Keep visible keyboard focus, selected-page indication, semantic controls, text labels and mobile reflow. The implementation target is WCAG 2.2 AA, subject to actual accessibility verification.

### Global controls

Me / My team / Administration workspace switch; persistent Inbox shortcut; search; notifications; company scope; profile. These controls do not imply additional business modules or grant privileges.

### Recommended role starts

| Perspective | Start and principal work | Boundary |
| --- | --- | --- |
| Employee | My home; own pay, time, trips/claims, goals/training, profile/documents and requests. | Reuse `/my` ownership checks. No administrator menu or broader records by default. |
| Manager | My team and Inbox; coverage, own hiring requests, assigned lifecycle tasks, reviews and required learning. | Team relationship alone does not authorize compensation, confidential coaching or formal case access. |
| HR operations | HR home; People, lifecycle, hiring, workforce, HR cases and talent. | Payroll amounts and restricted case details require separate permissions. |
| Recruiter | Hiring overview; assigned requisitions, applications, interviews and offers. | No general employee/payroll access. Candidate visibility and retention remain governed. |
| Payroll operations | Payroll overview; pay groups, inputs, runs, results, delivery and statutory outputs. | Preparing, approving, paying and reopening are different capabilities. Scoped people/contract reads are separately authorized. |
| Finance | Spend overview or authorized payroll work; liabilities, advances, payments and reconciliation. | Financial duties do not confer general HR access or all payroll editing rights. |
| Configuration administrator | Settings categories relevant to the administrator’s domain and scope. | Ordinary operational roles do not automatically receive configuration privilege. Platform tenant operations remain separate from company administration. |

The HTML role selector illustrates this idea; it is not a complete access matrix. In particular, its simplified role filtering must not be copied as the production authorization system. Final permissions must be mapped to existing groups, record/field rules, company/team scope and feature entitlements.

### Personal workspace reference

| Destination | Purpose |
| --- | --- |
| My home | Summary, notices and actions needing me. |
| Profile and documents | Personal changes, documents and employee assets. |
| My pay | Payslips, pay explanation, tax sheet and pay package. |
| My time | Schedule, attendance, leave, overtime and project time. |
| Trips and expenses | Own trip requests and expense claims. |
| Goals and learning | Own goals, training, recognition and assigned development. |
| My requests | Submitted requests, statuses and replies. |
| Ask HR | Ask a question and follow the HR conversation. |

## 7 Complete destination specification

The following 66 entries preserve the menu design and treatment classifications in the HTML baseline. The `domain.destination` reference lets a reviewer identify a finding precisely. `Inside` names local views or filters; it does not add another global menu layer. `Foundation` is source evidence or an explicit dependency, not an installation guarantee. `Treatment` records the proposed implementation judgment.

Later entries are shown for completeness and must remain hidden until separately scoped and delivered. A New/Extend entry scheduled for a later release also needs a working earlier destination or must remain hidden; a treatment label is not permission to ship an empty placeholder.

### Home

Domain reference: `home`. Icon key: `home`. A role-specific start with the work that needs attention.

#### My day

Reference: `home.today`.

- **Treatment:** Extend. **Screen:** Dashboard. **Icon:** `activity`.
- **Purpose:** Show the next actions for the signed-in role, with the correct entity and period.
- **Inside:** Needs attention; Upcoming deadlines; Recent work; Pinned shortcuts.
- **Foundation:** pb_home_hub, pb_dashboard, pb_me_portal.
- **Design:** Extend existing Home; add an HR view and a manager composition. Keep the payroll start for payroll staff.

#### Inbox

Reference: `home.inbox`.

- **Treatment:** Extend. **Screen:** Shared work queue. **Icon:** `inbox`.
- **Purpose:** Bring tasks and approvals into one entry point; decisions still use the existing approval engine.
- **Inside:** My turn; Assigned tasks; Submitted by me; History.
- **Foundation:** pb_approval_config, biz_approval_workflow; lifecycle task adapters.
- **Design:** Reuse the current approvals inbox. Add links or adapters for checklist tasks; do not rebuild approvals or silently merge unlike task states.

#### Announcements

Reference: `home.notices`.

- **Treatment:** Reuse. **Screen:** Feed and calendar. **Icon:** `megaphone`.
- **Purpose:** Read company notices and the existing social wall.
- **Inside:** Announcements; Wall; Calendar.
- **Foundation:** pb_hr_comm, existing Wall lens.
- **Design:** One reader destination. Authorized authors get Compose and Manage actions; retire the duplicate People Announce entry.

### People

Domain reference: `people`. Icon key: `users`. The people record, employment operations and long-range staffing.

#### Employee directory

Reference: `people.directory`.

- **Treatment:** Reuse. **Screen:** List and employee profile. **Icon:** `users`.
- **Purpose:** Find a person and open their complete employee record.
- **Inside:** Active / inactive filters; Profile; Employment; Pay and benefits; Documents; Emergency contacts.
- **Foundation:** pb_people, pb_employee_vault, pb_contracts.
- **Design:** Keep one employee identity. Employee profile tabs hold personal and bank details; do not turn each field category into a global menu.

#### Organization

Reference: `people.org`.

- **Treatment:** Extend. **Screen:** Organization view. **Icon:** `gitBranch`.
- **Purpose:** Browse teams, reporting lines, departments and locations.
- **Inside:** Org chart; Departments; Locations; Reporting relationships.
- **Foundation:** hr, hr_org_chart_overview, pb_workseg; portal org chart.
- **Design:** Promote a clear organization view. Edit controlled masters in Settings; this is the operational read view.

#### Contracts and compensation

Reference: `people.contracts`.

- **Treatment:** Reuse. **Screen:** Register and workbench. **Icon:** `scrollText`.
- **Purpose:** Manage contract terms, renewals, packages and approved compensation changes.
- **Inside:** Contracts; Expiry and renewal; Pay packages; Pay reviews; Pay changes.
- **Foundation:** pb_contracts, pb_contract_lifecycle, pb_pay, pb_comp_ben.
- **Design:** Reuse current contract and Pay screens, with explicit links from each employee. Pay changes already include promotions; avoid a second salary engine.

#### Lifecycle

Reference: `people.lifecycle`.

- **Treatment:** Extend. **Screen:** Case workspace. **Icon:** `refresh`.
- **Purpose:** Track joining, probation, employment changes and leaving with owners and due dates.
- **Inside:** Overview; Onboarding; Probation; Employment changes; Exits; Letters.
- **Foundation:** pb_lifecycle, pb_onboarding, pb_probation, pb_offboarding; new changes extension.
- **Design:** Move Lifecycle under People. Reuse existing journeys and specialist boards. Add effective-dated non-pay employment changes only where current proposals do not cover them.

#### Documents and assets

Reference: `people.documents`.

- **Treatment:** Extend. **Screen:** Operational registers. **Icon:** `fileCheck`.
- **Purpose:** Find missing or expiring evidence and outstanding employee assets across the organization.
- **Inside:** Document exceptions; Expiring documents; Asset allocation; Returns and clearance.
- **Foundation:** pb_employee_vault, pb_assets.
- **Design:** Build aggregate list views over existing records, keeping originals on the employee. Certification ownership remains in Talent and learning.

#### Workforce planning

Reference: `people.planning`.

- **Treatment:** Reuse. **Screen:** Planning workbench. **Icon:** `trendingUp`.
- **Purpose:** Plan future headcount and employment costs.
- **Inside:** Headcount scenarios; Staffing gaps; Budget; Forecast versus actual.
- **Foundation:** pb_people_hub Plan, pb_decision_room, pb_hr_workforce_planning.
- **Design:** Retain the existing planning product. Daily roster changes stay in Workforce; strategic planning lives here.

### Hiring

Domain reference: `hiring`. Icon key: `userPlus`. A direct place for recruitment teams, with the existing hiring board underneath.

#### Hiring overview

Reference: `hiring.hiring-home`.

- **Treatment:** Extend. **Screen:** Operational dashboard. **Icon:** `layoutGrid`.
- **Purpose:** See vacancies, overdue feedback and candidates awaiting the next step.
- **Inside:** Open roles; Feedback overdue; Offers awaiting action; Joining soon.
- **Foundation:** pb_hiring board and analytics.
- **Design:** Expose the existing board directly. Use operational counts; trend reports link to Insights rather than create a parallel metric engine.

#### Requisitions and jobs

Reference: `hiring.requisitions`.

- **Treatment:** Extend. **Screen:** List and board. **Icon:** `briefcase`.
- **Purpose:** Request headcount and manage roles and advertisements as related records.
- **Inside:** Requisitions; Jobs; Publishing; Budget and approval status.
- **Foundation:** pb.hiring.requisition, hr.job, existing requisition and JD screens.
- **Design:** Keep requisitions and jobs distinct but linked. Create is a button; Draft, Approved and Closed are filters.

#### Applications

Reference: `hiring.applications`.

- **Treatment:** New. **Screen:** Cross-role list and pipeline. **Icon:** `columns`.
- **Purpose:** Work through applications across jobs without opening every role drawer.
- **Inside:** Pipeline; List; Stage and owner filters; Candidate detail.
- **Foundation:** hr.applicant, pb_hiring existing screening and privacy controls.
- **Design:** New aggregate screen over existing applications. Preserve candidate-versus-application identity and the current stage transitions.

#### Candidates and talent pool

Reference: `hiring.candidates`.

- **Treatment:** Extend. **Screen:** Searchable register. **Icon:** `bookOpen`.
- **Purpose:** Search reusable candidate profiles while preserving application history by role.
- **Inside:** Resume bank; Talent pool; Skills and source filters.
- **Foundation:** pb_hiring Resume bank and privacy_p4.
- **Design:** Reuse the resume bank. Add a clear application history relationship; verify consent, visibility and retention before broadening search.

#### Interviews

Reference: `hiring.interviews`.

- **Treatment:** Reuse. **Screen:** Calendar and queue. **Icon:** `calendarClock`.
- **Purpose:** Schedule interviews, gather panel feedback and follow up late responses.
- **Inside:** Calendar; My interviews; Feedback due; Interview detail.
- **Foundation:** pb_hiring interview board, panel feedback, Google integration.
- **Design:** Promote the current Interviews tab and its role detail; no separate menu for each interview outcome.

#### Offers and joining

Reference: `hiring.offers`.

- **Treatment:** New. **Screen:** Offer register. **Icon:** `send`.
- **Purpose:** Track offers and readiness to hand a selected candidate to onboarding.
- **Inside:** Offer status filters; Documents; Checks; Joining dates; Handover.
- **Foundation:** pb.hiring.offer, docreq, bgv, joining_p6, pb_onboarding.
- **Design:** New aggregate register using existing offer forms and controls. Pre-joining belongs here; employee onboarding begins after an explicit handover.

### Talent and learning

Domain reference: `talent`. Icon key: `graduationCap`. Performance, employee training and capability development.

#### Talent overview

Reference: `talent.talent-home`.

- **Treatment:** New. **Screen:** Operational dashboard. **Icon:** `layoutGrid`.
- **Purpose:** Find overdue reviews, incomplete required learning and capability risks.
- **Inside:** Reviews due; Required training; Certification exceptions; Development actions.
- **Foundation:** pb_goals analytics, pb_training analytics, vault; new summary composition.
- **Design:** New composite landing page. Reuse source metrics; access to aggregate data must not expose confidential cases.

#### Goals and reviews

Reference: `talent.goals`.

- **Treatment:** Reuse. **Screen:** Goal and review workbench. **Icon:** `target`.
- **Purpose:** Run goal cycles and assessments using the existing goals product.
- **Inside:** Goals; Check-ins; Reviews; Scores; Cycle administration.
- **Foundation:** pb_goals.
- **Design:** Move out of the People tab strip. Do not create separate global menus for each assessment step.

#### Development and growth plans

Reference: `talent.development`.

- **Treatment:** Extend. **Screen:** Case workbench. **Icon:** `trendingUp`.
- **Purpose:** Support development and existing restricted performance-improvement cases.
- **Inside:** Development actions; Growth plans; Coaching within a case.
- **Foundation:** pb_pip, pb.employee.checkin; broader development model unverified.
- **Design:** Move the current restricted growth board here. A PIP coaching note is not a general mentoring platform; keep ordinary development distinct from formal cases.

#### Courses and assignments

Reference: `talent.training`.

- **Treatment:** Reuse. **Screen:** Learning administration. **Icon:** `bookOpen`.
- **Purpose:** Manage job training, enrollments, completion, tests and learning claims.
- **Inside:** Course library; Assignments; Tests; Training claims; Recurring requirements.
- **Foundation:** pb_training, website_slides, survey.
- **Design:** Reuse Training. Product-use tutorials move to Help; employee learning remains here.

#### Skills and certifications

Reference: `talent.skills`.

- **Treatment:** New. **Screen:** Skills matrix and evidence register. **Icon:** `idCard`.
- **Purpose:** Compare required skills with assessed proficiency and valid evidence.
- **Inside:** Skills matrix; Qualifications; Certificates; Expiry; Gap filters.
- **Foundation:** hr_skills where installed, pb_employee_vault, pb_training; required-skill extension.
- **Design:** New aggregate matrix plus requirement/assessment forms where missing. Do not duplicate certificates. Employee profile shows the same records.

#### Recognition and engagement

Reference: `talent.recognition`.

- **Treatment:** Extend. **Screen:** Recognition and survey workspace. **Icon:** `star`.
- **Purpose:** Recognize colleagues and review engagement at an appropriate aggregate level.
- **Inside:** Recognition; Surveys; Feedback trends.
- **Foundation:** pb_rnr, existing Praise / Wall; survey coverage to verify.
- **Design:** Consolidate existing recognition. Treat company survey administration and anonymity thresholds as explicit requirements, not assumed features.

#### Career paths and succession

Reference: `talent.careers`.

- **Treatment:** Later. **Screen:** Programme and readiness workbench. **Icon:** `route`.
- **Purpose:** Develop career frameworks and succession plans once ownership and assessment rules exist.
- **Inside:** Career paths; Mentoring programmes; Critical roles; Successors; Readiness.
- **Foundation:** No complete general career / mentoring / succession workflow verified.
- **Design:** Later: define job architecture and restricted audiences before building. Do not relabel existing PIP cases as succession planning.

### Workforce

Domain reference: `workforce`. Icon key: `clock`. Daily time, coverage and validated time inputs.

#### Today and coverage

Reference: `workforce.workforce-today`.

- **Treatment:** Reuse. **Screen:** Operational dashboard. **Icon:** `activity`.
- **Purpose:** Resolve absence, lateness, coverage gaps and field exceptions.
- **Inside:** Present / absent filters; Late arrivals; Coverage; Exception drilldown.
- **Foundation:** pb_today, pb_mission.
- **Design:** Reuse Today. Show data freshness and distinguish missing punches from confirmed absence.

#### Schedules and shifts

Reference: `workforce.schedule`.

- **Treatment:** Reuse. **Screen:** Calendar and roster. **Icon:** `calendar`.
- **Purpose:** Plan shifts, rotate teams and publish assignments.
- **Inside:** Week roster; Shift templates; Rotations; Coverage.
- **Foundation:** pb_schedule, hr_shift.
- **Design:** Keep Create shift, Copy week and Publish as actions. Do not add a Night shifts menu; use a shift type filter.

#### Attendance

Reference: `workforce.attendance`.

- **Treatment:** Reuse. **Screen:** Grid and timeline. **Icon:** `clock`.
- **Purpose:** Review punches, correct attendance and validate source imports.
- **Inside:** Timeline; Weekly entry; Corrections; Device exceptions.
- **Foundation:** pb_time_hub, pb_attendance_flow, pb_hr_workforce.
- **Design:** Relabel Time to Attendance in navigation. Keep attendance time separate from project timesheets.

#### Project timesheets

Reference: `workforce.project-time`.

- **Treatment:** Extend. **Screen:** Timesheet list and approvals. **Icon:** `table`.
- **Purpose:** Capture project effort and submit timesheets for review.
- **Inside:** By week; By project; Awaiting approval; Approved hours.
- **Foundation:** pb_me_project_time, hr_timesheet_sheet, pb_timesheet_approval.
- **Design:** Add a visible operational door for enabled tenants. Payroll treatment must follow explicit mapping; do not substitute project hours for attendance.

#### Time off and holidays

Reference: `workforce.timeoff`.

- **Treatment:** Reuse. **Screen:** Leave workspace. **Icon:** `umbrella`.
- **Purpose:** Manage requests, balances, public holidays and absence planning.
- **Inside:** Requests; Balances; Calendar; Holidays; Carry forward.
- **Foundation:** pb_timeoff, hr_holidays_public.
- **Design:** Combine adjacent calendar tasks. Approval badges deep-link to the same Inbox with a time-off filter.

#### Overtime

Reference: `workforce.overtime`.

- **Treatment:** Reuse. **Screen:** Request and hours register. **Icon:** `zap`.
- **Purpose:** Approve overtime and review payable hours against the relevant rules.
- **Inside:** Requests; Approved hours; Limits and exceptions; Payroll handover.
- **Foundation:** pb_hr_workforce Overtime Desk, ohrms_overtime.
- **Design:** Reuse the current overtime desk. Requested, worked, approved and payable hours are distinct measures.

#### Period close and handover

Reference: `workforce.close`.

- **Treatment:** Extend. **Screen:** Close workbench. **Icon:** `lock`.
- **Purpose:** Review evidence, resolve exceptions and hand authorized time inputs to payroll.
- **Inside:** Exceptions; Attendance close; Overtime validation; Reopen history; Handover.
- **Foundation:** pb_close, pb_workforce_payroll_bridge.
- **Design:** Extend the current close view with explicit handover evidence. A workforce evidence lock is not proof that payroll inputs are financially frozen.

#### Field workforce

Reference: `workforce.field`.

- **Treatment:** Reuse. **Screen:** Map and assignments. **Icon:** `mapPin`.
- **Purpose:** Review field check-ins and assignments when the feature is enabled.
- **Inside:** Check-ins; Map; Assignments; Exceptions.
- **Foundation:** pb_driver_checkin, pb_mission Field.
- **Design:** Keep this optional, permission-scoped and separate from a production-output claim.

#### Production labour deployment

Reference: `workforce.deployment`.

- **Treatment:** Later. **Screen:** Planning board and assignment form. **Icon:** `layers`.
- **Purpose:** Assign qualified people to production lines against verified requirements.
- **Inside:** Line requirements; Skill eligibility; Allocations; Reassignments.
- **Foundation:** Would extend roster, skills and work segments; ERP/MES adapter required.
- **Design:** Later phase: define site, line, operation, interval, minimum skill and required headcount first. A normal shift assignment is not this capability.

### Payroll

Domain reference: `payroll`. Icon key: `banknote`. Run payroll with a clear period, evidence trail and controlled delivery.

#### Payroll overview

Reference: `payroll.payroll-overview`.

- **Treatment:** Extend. **Screen:** Readiness dashboard. **Icon:** `gauge`.
- **Purpose:** Show what is blocking the next run and who must resolve it.
- **Inside:** Readiness; Deadlines; Assigned blockers; Run progress.
- **Foundation:** pb_payhub, pb_dashboard; source-specific readiness adapters.
- **Design:** Extend existing hub and tracker. Add a scoped readiness view; calculate each blocker from its owning subsystem.

#### Current run

Reference: `payroll.current-run`.

- **Treatment:** Reuse. **Screen:** Guided process. **Icon:** `play`.
- **Purpose:** Prepare, calculate, validate and submit a run for approval.
- **Inside:** Scope; Inputs; Calculation; Validation; Approval.
- **Foundation:** pb_payrun_wizard, pb_payruns, existing approval engine.
- **Design:** Retain the existing wizard and board. Current means selected entity, pay group, period and run type, not one global month.

#### Pay runs

Reference: `payroll.runs`.

- **Treatment:** Reuse. **Screen:** Board and list. **Icon:** `calendar`.
- **Purpose:** Find current and historical runs, including adjustments and test runs.
- **Inside:** Board / list; History; Status and period filters.
- **Foundation:** pb_payruns, hr.payslip.run.
- **Design:** Rename Runs to Pay runs. Keep draft test runs distinguishable from approved payroll.

#### Payroll inputs

Reference: `payroll.inputs`.

- **Treatment:** Reuse. **Screen:** Import and validation workbench. **Icon:** `download`.
- **Purpose:** Import and reconcile variable inputs with explicit provenance.
- **Inside:** Upload; Mapping; Validation; Changes; Approved inputs.
- **Foundation:** pb_import, pb_import_wizard, pb_formula_studio, pb_records.
- **Design:** Expose the existing import journey. Mapping is a configuration link, not another copy inside Payroll.

#### Results and payslips

Reference: `payroll.results`.

- **Treatment:** Reuse. **Screen:** Results grid and publication. **Icon:** `receipt`.
- **Purpose:** Explain payroll totals, compare variances and publish authorized payslips.
- **Inside:** Results; Variance; Payslip preview; Publication history.
- **Foundation:** pb_payrun_results, pb_payslip_review, pb_payslip.
- **Design:** Keep gross, deductions, tax and net as columns or breakdowns. Publication status and payment status remain separate.

#### Adjustments and settlements

Reference: `payroll.adjustments`.

- **Treatment:** Reuse. **Screen:** Special run workbench. **Icon:** `percent`.
- **Purpose:** Process retro pay, proration and final settlements with traceable source cases.
- **Inside:** Retroactive pay; Proration; Final settlement.
- **Foundation:** pb_payhub Adjust / Settle, pb_hr_fullandfinal.
- **Design:** Group less frequent run variants. Link exits to their one settlement; no second settlement form in Lifecycle.

#### Payments and delivery

Reference: `payroll.payments`.

- **Treatment:** Extend. **Screen:** Delivery and reconciliation view. **Icon:** `landmark`.
- **Purpose:** Verify bank readiness, produce files and reconcile payment outcomes.
- **Inside:** Bank readiness; Payment files; Payslip delivery; Accounting export; Reconciliation.
- **Foundation:** pb_pay_delivery, pb_bank_ocr, existing accounting outputs.
- **Design:** Move the bank verification door here; Governance can link to it. File generation never means bank acceptance or employee payment.

#### Payroll calendar

Reference: `payroll.calendar`.

- **Treatment:** Reuse. **Screen:** Calendar. **Icon:** `calendarClock`.
- **Purpose:** Track deadlines, reminders and pay dates.
- **Inside:** Calendar; Upcoming deadlines; Reminder history.
- **Foundation:** pb_comp_ben payroll_calendar.
- **Design:** Reuse Calendar, scoped by company and pay group.

#### Variable pay and awards

Reference: `payroll.variable-pay`.

- **Treatment:** Reuse. **Screen:** Input register. **Icon:** `coins`.
- **Purpose:** Queue approved incentives and monetary awards into the correct pay run.
- **Inside:** Awards; Bonuses; Approved / queued / paid filters.
- **Foundation:** pb_comp_ben incentives, pb_training claims bridge.
- **Design:** Rename Awards to clarify monetary intent. Recognition in Talent can create a linked award only through the approved path.

### Travel and expenses

Domain reference: `spend`. Icon key: `wallet`. One operations home for travel authorization and employee spend.

#### Spend overview

Reference: `spend.spend-home`.

- **Treatment:** New. **Screen:** Operational dashboard. **Icon:** `layoutGrid`.
- **Purpose:** Find pending claims, unpaid reimbursements and outstanding trip advances.
- **Inside:** Awaiting action; Approved unpaid; Advance aging; Policy exceptions.
- **Foundation:** pb.business.trip, pb.expense.claim, hr.expense, accounting status.
- **Design:** New composition over existing transactions. Show amounts by currency and distinguish advance, claim, payable and paid.

#### Trips

Reference: `spend.trips`.

- **Treatment:** Reuse. **Screen:** Board and trip detail. **Icon:** `plane`.
- **Purpose:** Authorize business travel, record costs and link claims to the trip.
- **Inside:** Requests; Upcoming / current / past filters; Trip detail; Advance.
- **Foundation:** pb_business_trip, pb_me_trip, pb_trip_expense_bridge.
- **Design:** Move existing Trips out of Workforce. Destination, purpose and estimated cost stay on the form; itinerary documents stay in the trip.

#### Expense claims

Reference: `spend.claims`.

- **Treatment:** Extend. **Screen:** Claims register. **Icon:** `receipt`.
- **Purpose:** Validate receipts and route claims to the right approvers.
- **Inside:** Claims; Receipts; Exception filters; Approval trail.
- **Foundation:** pb_me_expense pb.expense.claim, hr.expense.
- **Design:** Provide an admin claims workbench over existing backend forms. Employee submission continues to use the current self-service claim form.

#### Reimbursements

Reference: `spend.reimbursements`.

- **Treatment:** New. **Screen:** Aging and reconciliation list. **Icon:** `banknote`.
- **Purpose:** Track approved claims until accounting confirms payment.
- **Inside:** Approved unpaid; Part-paid exceptions; Paid; Reconciliation.
- **Foundation:** pb.expense.claim paid synchronization, hr.expense, accounting.
- **Design:** New finance view, not a second payment ledger. Display payment evidence and prevent payroll reimbursement and AP payment for the same claim.

#### Allocation and spend reports

Reference: `spend.allocation`.

- **Treatment:** Extend. **Screen:** Allocation view and reports. **Icon:** `gitMerge`.
- **Purpose:** Analyze expenses by controlled accounting dimensions.
- **Inside:** Department; Cost centre; Project / client; Billable status.
- **Foundation:** hr.expense analytic distribution; project and client links to verify.
- **Design:** Reuse analytic distribution where available. Add governed project/client selectors only after confirming target masters and posting semantics.

#### Travel bookings and cards

Reference: `spend.booking`.

- **Treatment:** Later. **Screen:** External integrations. **Icon:** `link`.
- **Purpose:** Connect booking references and corporate-card transactions when a provider is selected.
- **Inside:** Booking references; Card feed; Receipt matching; Reconciliation.
- **Foundation:** No production-ready booking or card workflow verified in this review.
- **Design:** Later and separately scoped. Prefer provider integrations; do not build an airline/hotel booking engine or a card issuer.

### HR services

Domain reference: `services`. Icon key: `inbox`. The HR team’s case queue and service quality.

#### HR request board

Reference: `services.requests`.

- **Treatment:** Reuse. **Screen:** Kanban and list. **Icon:** `inbox`.
- **Purpose:** Respond to employee questions and follow each conversation to closure.
- **Inside:** New; With HR; Answered; Closed; Owner and category filters.
- **Foundation:** pb_ask_hr.
- **Design:** Rename the admin entry HR services, retain Ask HR for employees. Current states are board columns, not nested menus.

#### Service reports

Reference: `services.service-reports`.

- **Treatment:** New. **Screen:** Queue dashboard. **Icon:** `chartColumn`.
- **Purpose:** Track queue age, ownership, first response and resolution without losing case context.
- **Inside:** Open aging; Unassigned; First response; Resolution trends.
- **Foundation:** pb.ask.hr.ticket timestamps and messages; metric definitions required.
- **Design:** New report view. If SLA promises are added, define working calendars, pause rules and first-response timestamp; answered_on alone is not a full SLA engine.

### Insights

Domain reference: `insights`. Icon key: `chartColumn`. Historical analysis, saved reports and trusted metric definitions.

#### Dashboards

Reference: `insights.dashboards`.

- **Treatment:** Extend. **Screen:** Analytics catalogue. **Icon:** `layoutGrid`.
- **Purpose:** Choose workforce, payroll, budget, hiring, goals and learning analysis.
- **Inside:** Workforce; Payroll; Budget; Hiring; Learning; Talent.
- **Foundation:** pb_insights_hub, pb_insights, pb_workforce_insights, existing domain analytics.
- **Design:** Reuse current analysis. Separate operational action queues from historical dashboards; do not rebuild a chart for every submenu.

#### Reports and explorer

Reference: `insights.reports`.

- **Treatment:** Extend. **Screen:** Report catalogue and explorer. **Icon:** `table`.
- **Purpose:** Find standard and saved reports, with secure export.
- **Inside:** Standard reports; Saved views; Explorer; Export.
- **Foundation:** pb_explorer, payroll report and domain reports.
- **Design:** Add a clear catalogue over current report actions. Exports are actions and retain row/field permissions.

#### Scheduled reports

Reference: `insights.scheduled`.

- **Treatment:** Later. **Screen:** Delivery administration. **Icon:** `calendarClock`.
- **Purpose:** Schedule verified reports for authorized recipients.
- **Inside:** Schedules; Recipients; Delivery history.
- **Foundation:** Training packs have schedules; generalized scheduler not verified.
- **Design:** Later general service: reuse existing training packs; add recipient authorization, data scope, failure handling and owner review before broad distribution.

#### Manufacturing analytics

Reference: `insights.manufacturing`.

- **Treatment:** Later. **Screen:** Verified operational analytics. **Icon:** `gauge`.
- **Purpose:** Analyze labour efficiency and labour cost per unit using production evidence.
- **Inside:** Good units; Earned hours; Actual labour hours; Cost per unit; Comparisons.
- **Foundation:** Requires ERP/MES output, standards, quality, downtime and assignment data.
- **Design:** Later integration project. Attendance and payroll alone cannot produce a defensible production-efficiency metric; never derive automatic salary deductions from it.

### Governance

Domain reference: `governance`. Icon key: `shieldCheck`. Obligations, policy evidence and the audit trail.

#### Compliance workbench

Reference: `governance.compliance`.

- **Treatment:** Extend. **Screen:** Obligations register and calendar. **Icon:** `calendarClock`.
- **Purpose:** Know which obligation is due, who owns it and what evidence closes it.
- **Inside:** Upcoming; Overdue; Filed; Jurisdiction and frequency filters.
- **Foundation:** pb_govt_reports, pb_filing.flow; extend obligation metadata.
- **Design:** Extend filings with obligation ownership, due dates and evidence. Monthly / quarterly / annual are frequency filters; country configuration stays in Settings.

#### Filings and statutory reports

Reference: `governance.filings`.

- **Treatment:** Reuse. **Screen:** Filing workflow. **Icon:** `fileCheck`.
- **Purpose:** Generate and review supported jurisdiction reports and track the actual filing evidence.
- **Inside:** Tax; Labour and insurance; Review; Filing evidence; History.
- **Foundation:** pb_govt_reports, pb_hr_govt, configured country packs.
- **Design:** Reuse supported reports. Generated, approved, submitted and accepted are different statuses; do not imply regulator submission without a verified connector or evidence.

#### Policy library

Reference: `governance.policies`.

- **Treatment:** New. **Screen:** Versioned document register. **Icon:** `bookOpen`.
- **Purpose:** Publish approved policies and record required acknowledgements.
- **Inside:** Current policies; Versions; Acknowledgement coverage; Review due.
- **Foundation:** New general policy/version/acknowledgement model; existing documents and approval engine reused.
- **Design:** A policy file is not a configuration rule. Add owner, version, audience, effective date, review date and acknowledgement records; linked rules remain in Settings.

#### Audit trail and controls

Reference: `governance.audit`.

- **Treatment:** Reuse. **Screen:** Audit workbench. **Icon:** `scrollText`.
- **Purpose:** Investigate decisions, changes, access and control exceptions.
- **Inside:** Record changes; Payroll audit; Approval history; Control exceptions.
- **Foundation:** pb_audit, biz_approval_workflow, biz_access.
- **Design:** Reuse Audit. Keep policy oversight here and workflow editing in Settings. Trace decisions to source records and actor/time.

#### Workforce safeguards

Reference: `governance.safeguards`.

- **Treatment:** Reuse. **Screen:** Exception view. **Icon:** `shield`.
- **Purpose:** Review the existing young-worker and related workforce controls.
- **Inside:** Young-worker exceptions; Source evidence; Resolution.
- **Foundation:** pb_young_worker; relevant Workforce rule views.
- **Design:** Reuse the specialist guard. Workforce gets contextual alerts; this is the oversight entry.

### Settings

Domain reference: `settings`. Icon key: `settings`. Configuration offered only to authorized domain administrators.

#### Organization and masters

Reference: `settings.organization-settings`.

- **Treatment:** Extend. **Screen:** Configuration catalogue. **Icon:** `building`.
- **Purpose:** Maintain companies, locations, departments, jobs and allocation dimensions.
- **Inside:** Companies; Countries; Locations; Departments; Jobs; Cost centres; Projects / clients.
- **Foundation:** pb_settings, pb_group, existing HR and analytic masters.
- **Design:** One owner per master. Tenant/hosting administration remains limited to platform staff; ordinary company admins should not see it.

#### Users and access

Reference: `settings.access`.

- **Treatment:** Reuse. **Screen:** Access administration. **Icon:** `key`.
- **Purpose:** Manage roles, scope, delegates and access reviews.
- **Inside:** Users; Roles; Scope; Delegation; Access history.
- **Foundation:** biz_access, current Access and delegation.
- **Design:** Use current authorization. The proposed role preview is an illustration, never a replacement for server permissions.

#### Payroll configuration

Reference: `settings.payroll-settings`.

- **Treatment:** Reuse. **Screen:** Configuration workbench. **Icon:** `calculator`.
- **Purpose:** Manage components, formulas, mappings, country rules and payment formats.
- **Inside:** Templates; Components; Formula Studio; Mapping; Statutory rules; Payment setup.
- **Foundation:** pb_formula_studio, pb_structures, pb_statutory, pb_payroll_templates.
- **Design:** Keep existing calculation and mapping products. Hide engineering and unsupported country settings from routine payroll operators.

#### HR and operations configuration

Reference: `settings.domain-settings`.

- **Treatment:** Extend. **Screen:** Configuration catalogue. **Icon:** `sliders`.
- **Purpose:** Find domain-owned policies and reference settings without duplicating their data.
- **Inside:** Workforce; Hiring; Talent and learning; Travel and expenses; HR services.
- **Foundation:** Existing settings registries, trip policy and expense categories.
- **Design:** Regroup links by domain. Spending limits, leave rules and categories are settings or form fields, never parallel operational screens.

#### Workflows and notifications

Reference: `settings.workflows`.

- **Treatment:** Reuse. **Screen:** Approval and routing configuration. **Icon:** `workflow`.
- **Purpose:** Configure approval paths, delegation rules and notifications.
- **Inside:** Approval workflows; Business rules; Escalations; Templates; History.
- **Foundation:** pb_approval_config, biz_approval_workflow, current Settings Approvals.
- **Design:** Reuse one workflow engine. Governance provides oversight links to these same definitions.

#### Integrations and data

Reference: `settings.integrations`.

- **Treatment:** Reuse. **Screen:** Connector workbench. **Icon:** `plug`.
- **Purpose:** Operate imports, ERP connections, attendance devices and integration diagnostics.
- **Inside:** Connectors; Mappings; Import history; Errors; API configuration.
- **Foundation:** pb_integrations, pb_import_advanced, current connectors.
- **Design:** Reuse integration tools. Logs must show failures and reprocessing without exposing credentials.

#### System and localization

Reference: `settings.system`.

- **Treatment:** Reuse. **Screen:** System configuration. **Icon:** `globe`.
- **Purpose:** Control allowed language, currency, calendars, branding and system preferences.
- **Inside:** Localization; Calendars; Branding; System activity.
- **Foundation:** pb_settings and standard settings.
- **Design:** Respect tenancy scope and admin boundaries; keep product metadata and platform support controls in their authorized lanes.

### Help and product guides

Domain reference: `help`. Icon key: `helpCircle`. How to use Payobook, separate from job training.

#### Guides and tutorials

Reference: `help.guides`.

- **Treatment:** Reuse. **Screen:** Help library. **Icon:** `bookOpen`.
- **Purpose:** Find current Payobook lessons, tutorials and contextual guidance.
- **Inside:** Getting started; Module guides; Tutorials; FAQs; Troubleshooting.
- **Foundation:** pb_learn Lessons and helper.
- **Design:** Move product lessons here while keeping old Learn links and learning progress intact.

#### Product support and releases

Reference: `help.support`.

- **Treatment:** Extend. **Screen:** Support links. **Icon:** `helpCircle`.
- **Purpose:** Find the support route and understand changes to Payobook.
- **Inside:** Contact support; Release notes; About Payobook.
- **Foundation:** Current About Payobook and support entry points.
- **Design:** Expose available support and release information. This is product support; employee HR questions go to Ask HR.

## 8 Build packages and screen requirements

These packages reproduce the proposed delivery split. They describe outcomes and reuse boundaries, not estimated effort or an approved implementation backlog. Exact fields, schemas, API contracts and permission groups still require a fit check against installed modules.

| ID | Proposed phase | Deliverable | Reuse and new work | Acceptance evidence |
| --- | --- | --- | --- | --- |
| A1 | First | Navigation shell and destination catalogue | Extend `pb_sidebar` and shared hubs for child destinations, consistent labels, stable routes and search aliases. No new business transaction model. | Old routes resolve; correct selection after a deep link; keyboard and narrow-screen navigation work. |
| A2 | First | Role homes and My team | Adapt Home for HR/payroll; add a manager composition over existing team tasks, coverage, reviews and learning. Extend Inbox adapters where required. | Counts reconcile to permitted source rows. Missing permission/source failure does not produce a false zero. |
| A3 | First | Applications and Offers registers | New cross-job list/pipeline views over existing `hr.applicant` and `pb.hiring.offer`; retain forms, transitions and approvals. Make jobs/requisitions/resume bank directly discoverable. | Find offers waiting on the reviewer across assigned jobs, open one, and return to the preserved list without exposing unrelated candidates. |
| A4 | First | Payroll readiness | Extend the pay hub and add a combined readiness read. Reuse input validation, approvals, contract/payment prerequisites, run checks and workforce handover evidence. | Each blocker identifies its source and owner. Stale/failed checks cannot show Ready. Workforce locking and financial input finalization remain distinct. |
| A5 | Next | Spend operations | New spend dashboard and reimbursement aging/reconciliation; extend admin claims and allocation. Reuse trips, claims, receipts and accounting records; retain employee submission forms. | Approved-unpaid reconciles by currency. Exporting a file does not mark a claim paid. Prevent payroll and AP from reimbursing the same source twice. |
| A6 | Next | Employment changes where current processes have gaps | Add an effective-dated non-pay request/register only for fields/processes not already covered. Reuse existing pay-change, contract-extension and governed record proposals. | Retain before/after values, effective date, approval and application outcome. Cross-company moves use the correct employment/contract process. |
| A7 | Next | Document exceptions and skills evidence | Aggregate existing vault/assets records; create a skills/qualification matrix. Add requirements/assessment/validity only where existing models do not suffice. | One certificate is referenced in employee and skills views. Distinguish self-declared, assessed, verified and expired evidence. |
| A8 | Next | Talent overview and development | New composition over goals and training metrics; reuse reviews and restricted growth cases. Define ordinary development separately before extending it. | Overdue counts reconcile. Confidential case details do not leak through broad search, summaries or exports. |
| A9 | Next | Policy library | New general policy/version/publication/acknowledgement workflow if the fit check confirms the gap. Reuse documents and approvals. | Identify effective and historic versions, owner, audience and acknowledgement coverage. Publishing a document does not change computational rules. |
| A10 | Next | Compliance obligations | Extend existing filings with applicability, ownership, recurrence, deadlines and evidence. Verify each country’s supported outputs. | Generated, reviewed, submitted and accepted are separate facts. Obligation completion requires the appropriate evidence. |
| A11 | Next | HR service reporting | New queue-age/ownership/response/resolution report over existing tickets. Add first-response/SLA fields only for an agreed service policy. | Define reopened cases, working calendars and pauses. `answered_on` alone is not treated as a complete first-response or SLA engine. |
| A12 | Later | Manufacturing, talent programmes and financial feeds | Separately scope production labour allocation/output analytics, general mentoring/career/succession, advanced job-learning paths, booking/card feeds and generalized report scheduling. | Each has an owner, source data, integration contract, permissions and an end-to-end acceptance path before a menu becomes live. |

### Forms and records to retain

Employee and contract detail; pay-change proposal; requisition and job; application and interview; offer and pre-joining checks; trip request; receipt and expense claim; goals and reviews; training assignment/test; HR question; filing proposal; approval configuration.

A create action or a different status does not justify a second form. Aggregate Applications and Offers views must open the current detail/transition flow instead of creating parallel records.

### Conceptual requirements for genuine process gaps

This table elaborates the baseline for review; these are proposed requirements, not verified existing schemas or finalized Odoo model names.

| Capability | Minimum information the design needs | Reuse constraint and unresolved choice |
| --- | --- | --- |
| Non-pay employment change | Person/employment, fields affected, before/after values, effective date, reason, approver, status, applied result and failure/conflict outcome. | First establish whether current contract/records proposals handle the required fields and future dates. Do not duplicate effective-dated pay changes. Decide cancellation, correction and overlapping-change rules. |
| Skill requirement and assessment | Controlled skill/qualification, role/site requirement, required proficiency, assessed proficiency, assessor, assessment date, evidence reference and validity where applicable. | Reuse installed skills models and vault certificates. Decide who can assert/verify evidence and how changes to requirements affect an employee’s apparent gap. |
| Policy version and acknowledgement | Policy identity, owner, version, approval, publication/effective date, review date, audience and acknowledgement evidence. | Reuse document storage. Policies are not executable payroll/leave rules. Decide audience snapshot, supersession and whether a new version requires another acknowledgement. |
| Compliance obligation | Company/jurisdiction, applicability, frequency, due date, owner, source rule/reference, status and evidence linked to filing records. | Reuse filing workflow. Decide how applicability and deadline changes are reviewed and who verifies the jurisdiction-specific configuration. |
| Expense allocation and settlement evidence | Controlled accounting dimensions, eligible payment route, payable amount, linked posting/payment references and reconciliation status. | Underlying expense/accounting records remain canonical. Decide handling of partial payment, rejected payment, reversals, advances and payroll versus AP routing. |
| Combined readiness result | Scope, source check, result, severity, owner, last-checked time and drilldown reference; any finalization evidence required by the agreed run process. | Read from owning domains. Do not create an independent green/red state that can disagree with source approvals or silently freeze transactions. |

## 9 Dashboard specifications

### Shared dashboard contract

Every operational tile should make the following understandable: what population is counted, the time/entity scope, the definition, last refresh/check, whether it blocks the process, who owns resolution, and the exact source list to open.

- Separate a confirmed zero from no data, no access, an unavailable source or stale evidence.
- Keep blockers and advisory findings distinct. The applicable rules determine whether an item blocks a specific operation.
- Distinguish people, employment records and payslips; a payslip count is not automatically headcount.
- Distinguish actuals and forecasts, requested/worked/approved/payable overtime, approved and paid, and publication and payment.
- Show currency buckets or a specified reporting currency with an exchange-rate date/method. Do not silently sum currencies.
- Operational and analytical views should share measure definitions and source populations.
- Counts, drilldowns and exports obey the same authorization rules. An aggregate must not reveal restricted case information.

### Proposed compositions

| Dashboard | Question answered | Main measures and source population | Treatment |
| --- | --- | --- | --- |
| HR home | What needs HR’s attention? | Joiners not ready, probation decisions due, exit tasks overdue, missing/expiring evidence; source cases/tasks within the selected horizon. | Extend Home/lifecycle summaries. |
| My team | What needs this manager? | Awaiting my decision, coverage gaps, reviews due, required learning overdue; authorized team/assignment scope. | New composition using existing records. |
| Payroll readiness | Can this selected run progress? | Input errors, outstanding approvals, configured contract/payment prerequisites, material variance exceptions; company + pay group + period + run type. | Extend pay hub plus combined readiness read. |
| Spend operations | What money is still owed or unresolved? | Approved-unpaid claims, outstanding advances, policy exceptions, oldest unresolved claims; reconcile claims to expense/accounting records. | New dashboard and finance list. |
| Hiring overview | Where is recruitment stuck? | Roles needing action, feedback overdue, offers awaiting action, joining readiness; source recruitment events. | Promote existing board/analytics. Define time-to-fill separately from time-to-hire. |
| Talent overview | Which capability work needs attention? | Reviews due, learning overdue, qualification gaps with explicit denominators and evidence status. | New composition over goals/training/skills. |
| Governance workbench | Which obligations or controls are at risk? | Due/overdue applicable obligations, missing filing evidence, policy reviews due; owned company/jurisdiction records. | Extend filing workbench. Missing data is not proof of compliance. |
| Manufacturing | Why did output, efficiency or unit labour cost change? | Verified good units, earned hours, actual labour hours, attributable labour cost; matched production boundary and effective standards. | Later, after source integration and reconciliation. |

The HTML includes three illustrative compositions: Payroll readiness, HR home and Spend operations. Their numbers and sample check timestamps are invented examples, not observations of actual employees, liabilities or payroll results. Those illustrative numbers are not requirements.

### Manufacturing data prerequisite

The design cannot infer production productivity from attendance and payroll alone. Minimum proposed inputs are site, line/operation, product/work order, assignment intervals, verified good/rejected/reworked output, actual labour hours, effective standard time, downtime reason and source identifiers. Define treatment of shared labour, subcontractors, overtime, rework and product mix.

Proposed formulas to agree with the production owner:

- Earned standard hours = sum of verified good quantity multiplied by the applicable standard hours per unit.
- Labour efficiency = earned standard hours divided by actual labour hours within the same scope.
- Labour cost per good unit = attributable labour cost divided by verified good units.

Missing, zero-denominator or incomparable inputs must be handled explicitly. These are proposed analytical definitions. They are not evidence that the current application supplies those inputs, and must not automatically create salary deductions or individual employment decisions.

## 10 Data ownership and control boundaries

### Canonical owners

| Information | Canonical owner in the proposed architecture | Required relationship |
| --- | --- | --- |
| Person, employment and contract | People and existing employee/contract models | Maintain identity separately from company-specific employment and terms. Effective dates identify the applicable record. |
| Requisition, job, candidate, application and offer | Existing Hiring records | A candidate can have multiple applications; a requisition and a job are related but distinct. Link accepted offer/pre-joining to onboarding explicitly. |
| Attendance and approved overtime | Workforce | Preserve source approvals and handover evidence. Backdated corrections take a controlled reopen/adjustment path. |
| Monetary awards and variable inputs | Existing approved incentive/input records | Recognition is not payment. Link an eligible approved amount to the correct run and prevent duplicate inclusion. |
| Claim, receipt, posting and payment | Existing claim/expense/accounting records | Approval, posting and payment remain distinct. Preserve the source link if payroll is the reimbursement route. |
| Payroll results and payslips | Existing calculation engine and payroll run | Retain input/calculation version and approval history. Authorized reopening must not silently rewrite a completed outcome. |
| Filing completion | Existing filing record plus evidence | A generated file or approved proposal does not establish submission or acceptance. |
| Qualifications and certificates | Skill assessment with shared document evidence | Reuse the same evidence from employee, training and eligibility views. |
| Policy publication | Versioned policy record linked to current configuration where relevant | A document describes policy; computational rules and their approval remain in their existing systems. |
| Production output | Verified ERP/MES or controlled production source | Payobook links employment/time/cost. It must not create a second uncontrolled production ledger. |

### Payroll handover sequence

```text
People and contracts
  -> validated time, overtime and eligible variable inputs
  -> source approvals and agreed input-finalization evidence
  -> calculation and variance review
  -> authorized payroll approval
  -> payslip publication, payment reconciliation and statutory evidence
```

This is a target workflow, not a statement that every transition is already enforced by the current build.

The prior source review found an important distinction in `pb_close/models/wf_lock.py`: workforce locks protect attendance/related evidence, while payroll money is driven through other input pathways. Therefore “attendance closed” must not be equated with “all financial payroll inputs are finalized.” Review the actual run/finalization rules before deciding what the readiness dashboard can assert.

### Authorization

Menu visibility is presentation, not a security boundary. Server authorization must cover direct record reads, list reads, counts, search, exports, drilldowns, decisions and mutations. Reuse company/team scope, roles, field/record restrictions and feature entitlements.

Salary, candidate data, formal performance cases and confidential coaching need independent access. A generic manager relationship, an Inbox assignment or a dashboard tile must not grant access to the rest of a restricted record.

## 11 User journeys for review and acceptance

The journeys below make the proposed behavior concrete. They are acceptance scenarios for a future implementation; they are not reported tests of deployed behavior.

### J01 Recruiter finds an offer awaiting action

1. Start in Hiring overview and open Hiring → Offers and joining.
2. Filter to authorized offers awaiting the recruiter’s action across assigned jobs.
3. Open an offer using its existing detail/approval flow, inspect joining checks and complete an allowed action.
4. Return to the same filtered list and see the resulting status.

Acceptance: one underlying offer record, correct candidate/application/job links, current approvals preserved, and no unrelated candidate or compensation data exposed. Rejected/declined/accepted states do not need separate global menus. References: D03, A3, `hiring.offers`.

### J02 HR tracks a joiner and probation decision

1. HR home shows a joiner not ready or a probation decision due.
2. Drill into People → Lifecycle, already filtered to the relevant cases/tasks.
3. Open the existing onboarding/probation record, identify the owner and complete permitted work.
4. The source list, case and Home summary agree after refresh.

Acceptance: checklist evidence, document checks and employment records remain linked. Managers see only assigned/permitted work. References: D04, A2, `people.lifecycle`.

### J03 HR requests an employment change

1. From the employee or Lifecycle workspace, choose the relevant change process.
2. Reuse existing pay/contract proposal flows when they cover the change. For an uncovered non-pay change, capture before/after values, reason and effective date.
3. Route to authorized approval and apply on the agreed effective date/process boundary.
4. Retain an audit of approval, application and any conflict or failure.

Acceptance: no bypass through a duplicate form, no unintended rewriting of historical pay, and no simple company-field edit used to stand in for a cross-company employment transfer. Cancellation, overlap and retroactive correction need agreed rules. References: A6, `people.contracts`, `people.lifecycle`.

### J04 Payroll resolves a blocking input

1. Select company, pay group, period and run type in Payroll.
2. Payroll overview identifies an unresolved source check, its owner and freshness.
3. Open the exact filtered source records and resolve the issue through the existing control path.
4. Refresh readiness; show Ready only when applicable current checks support it. Continue calculation/review/approval through the existing run tools.

Acceptance: zero, unavailable and stale are distinct; an attendance evidence lock alone does not prove financial input finalization. References: A4, `payroll.payroll-overview`, `payroll.inputs`.

### J05 Finance follows an expense to payment

1. An employee submits receipts/claim through existing self-service. A permitted trip link can supply context.
2. The claim follows the existing manager/finance approval route.
3. Finance opens Travel and expenses → Reimbursements to inspect approved-unpaid claims and reconciliation evidence.
4. Accounting or the authorized payroll reimbursement route confirms the outcome; the claim reflects the appropriate evidence.

Acceptance: file generation is not payment confirmation; partial/failed/reversed payments have explicit treatment; the same source cannot be paid by both payroll and AP. Advances remain identifiable and must not be added to related claims as if they were independent expense totals. References: D06, A5, `spend.reimbursements`.

### J06 Manager and employee use different perspectives

1. Manager starts in My team with assigned decisions and team coverage/learning work.
2. Employee starts in My home and opens personal pay, leave, claim or training work.
3. Both see the same relevant source request status within their respective permissions.

Acceptance: a manager’s role does not automatically reveal salary or confidential coaching; an employee cannot reach another person’s data by changing a direct URL. References: A2, section 6.

### J07 HR manages certification evidence

1. A skill/certificate requirement identifies an employee gap or an upcoming expiry.
2. Open the matrix/register and then the underlying assessment or vault evidence.
3. Verify or renew evidence through the permitted process.
4. Employee profile, training and matrix views reference the same evidence and agreed validity.

Acceptance: certification dates are recorded rather than invented; a passed training test is not automatically every role’s qualification. References: A7, `talent.skills`, `people.documents`.

### J08 Compliance owner completes an obligation

1. Governance shows an applicable obligation with owner and due date.
2. Open the existing filing workflow, generate/review the supported output and retain the required evidence.
3. Record submission/acceptance only when supported by the actual process/evidence.

Acceptance: frequency is a view of obligations, not three separate monthly/quarterly/annual systems; generated is not accepted. References: A10, `governance.compliance`, `governance.filings`.

### J09 A user arrives through an old bookmark

1. Open a current standalone action, tutorial link or saved record URL after the menu cutover.
2. Reach the surviving workspace/record with the correct domain selected and an understandable back path.
3. Check a denied role’s access through the same route.

Acceptance: no blank destination, “unnamed” breadcrumb or competing selected menu; compatibility does not widen access. References: D14, A1.

## 12 Decisions the independent review should challenge

The following issues remain open. Listing them does not change the baseline recommendation; it makes its tradeoffs explicit.

| Priority | Question | Alternatives or evidence that would resolve it |
| --- | --- | --- |
| High | Is the 12-entry complete rail too broad? | Test the ten business domains plus utilities against a smaller role-first hub arrangement. Evaluate actual task frequency, scanability and mobile behavior rather than a fixed menu-count rule. |
| High | Should Lifecycle remain a primary entry for HR? | Compare People → Lifecycle with a role-specific direct entry or pin. Test joining, probation and exit tasks with HR operators. |
| High | Is the proposed first release too ambitious? | A1–A4 includes new hiring lists, role compositions and readiness aggregation. Consider a navigation-only cutover followed by new views if it reduces delivery risk. |
| High | What opens when a future dashboard has not been built? | The full map lists New/Extend views that are scheduled after the first release. Specify a working existing landing or hide the destination; do not publish empty placeholders. |
| High | Does non-pay change management already exist sufficiently? | Inspect current contract, pay, Records and proposal models for fields, future dates, approvals, conflicts and application outcomes before approving A6. |
| High | What can payroll readiness legitimately assert? | Inspect calculation inputs, source approvals, snapshots/finalization, reopening and off-cycle runs. Define blocker rules per process and payment method. |
| High | Is the expense payment/reconciliation contract complete? | Walk claims, posting, advances, partial payment, reversals, payroll routing and AP routing with finance. Confirm where the payment truth is stored. |
| High | How should ordinary development and restricted growth/PIP cases be presented? | A common domain need not mean a common list, data model or audience. Consider separate permitted destinations or a clearly differentiated workspace. |
| Medium | Does HR services justify its own root with two destinations? | Compare a dedicated case-team entry with People → HR services and personal Ask HR. Use operator volume and ownership. |
| Medium | Are combined Results and payslips, and Payments and delivery, sufficiently clear? | Check whether payroll review, publication and finance delivery users can reach their frequent work without confusing states or permissions. |
| Medium | Are Contracts and compensation too broad alongside employee profile? | Validate the difference between a person’s detail and an aggregate operational workbench. Keep one canonical record and clear contextual links. |
| Medium | Are organization, location/work-segment and production-allocation concepts distinct enough? | Define organization hierarchy, work location, employing entity, charged entity, shift assignment and production-line allocation. Do not use one view to imply another process exists. |
| Medium | Will Talent and learning be manageable for each operator? | Validate training administration, review cycles, skills evidence and recognition with their actual owners. Broader engagement surveys remain a fit-check item. |
| Medium | Are Governance and Settings labels understandable? | Tree-test “find an overdue filing,” “publish a policy,” and “change an approval rule.” Consider clearer labels if users consistently choose the wrong owner. |
| Medium | How should specialist analytics be reached by recruiters/training roles? | The prototype’s simplified role filter is incomplete. Ensure authorized domain specialists can reach their own analytics without receiving broad company/payroll analytics. |
| Medium | Is deferred functionality a real customer requirement? | Reconcile manufacturing, career/succession, mentoring, advanced learning paths and card/booking requirements with customer contracts and priorities. Do not defer a required workflow merely to simplify a menu project. |

Do not treat “not verified” as proof of absence, or the existence of a similarly named module as proof of full coverage. Installation/version checks and role-based workflow walkthroughs resolve those questions.

## 13 Technical verification points for a reviewer with repository access

### Architecture fit

- `pb_sidebar` currently supplies section/item navigation and route/model matching. The proposed child level needs a supported parent/destination relationship or a derived catalogue; relabeling XML records alone is insufficient.
- `pb_hub` and the domain hubs provide shared navigation and registry extension points. Reuse them while moving visible ownership; avoid circular module dependencies.
- Keep stable action/lens/focus identities. The names and composite keys in this handover are review references, not a final routing specification.
- Existing model/tag matches can be broad. Employee/contract detail opened from several domains needs explicit source/back context rather than competing active-menu claims.
- A destination registry should consistently supply label, icon, order, target, visibility/feature check, search aliases and contextual navigation. This is a proposed contract; its precise representation remains to be designed.
- Preserve configuration shortcuts to the one authoritative setting. Organization browsing is operational; editing the controlled master belongs to authorized administration.
- Navigation cutover should not alter payroll calculations, approvals or master values. Genuine new process/data migrations require separate, repeatable migration logic.

### Useful source locations from the prior review

Paths are relative to the repository root. They are starting points for verification, not an exhaustive dependency graph.

| Question | Source locations |
| --- | --- |
| Rail records, access and active location | `pb_sidebar/models/pb_sidebar.py`; `pb_sidebar/data/pb_sidebar_data.xml`; `pb_sidebar/static/src/js/pb_sidebar.js`; `pb_tenancy/models/pb_sidebar.py`; `biz_access/` |
| Shared hub navigation | `pb_hub/static/src/js/`; `pb_home_hub/static/src/js/home_hub.js`; `pb_people_hub/static/src/js/people_hub.js` |
| Hiring’s current placement and specialized access | `pb_hiring/static/src/js/hiring_palette.js`; `pb_hiring/models/sidebar_door.py`; `pb_lifecycle/static/src/js/lifecycle_hub.js` |
| Current hiring transaction foundation | `pb_hiring/models/requisition.py`; `pb_hiring/models/offer.py`; `pb_hiring/models/interview.py`; `pb_hiring/models/hr_applicant_ext.py`; other hiring joining/privacy/approval extensions |
| Workforce and close semantics | `pb_mission/static/src/js/pb_mission.js`; `pb_time_hub/`; `pb_close/models/wf_lock.py`; `pb_workforce_payroll_bridge/` |
| Payroll hub and configuration | `pb_payhub/static/src/js/pay_hub.js`; `pb_payrun_wizard/`; `pb_settings/static/src/js/settings_hub.js`; `pb_formula_studio/` |
| Existing pay and governed record changes | `pb_pay/models/pb_pay_change.py`; `pb_contracts/models/pb_contract_360.py`; `pb_contract_lifecycle/`; `pb_records/models/records_approval.py`; `pb_records/models/pb_records_change.py` |
| Shared approval inbox and engine | `pb_approval_config/`; `biz_approval_workflow/`; `pb_home_hub/static/src/js/home_hub.js` |
| Travel and claim/payment state | `pb_business_trip/models/pb_business_trip.py`; `pb_me_expense/models/expense_claim.py`; `pb_me_expense/models/hr_expense.py`; `pb_trip_expense_bridge/`; `hr_expense/` |
| Learning and evidence | `pb_training/models/assignment.py`; `pb_training/models/certificate.py`; `pb_training/models/schedule.py`; `pb_employee_vault/models/employee_document.py`; `pb_learn/` |
| Goals and restricted case coaching | `pb_goals/`; `pb_pip/models/pip_case.py`; `pb_pip/models/pb_pip.py` |
| HR cases, filings and audit | `pb_ask_hr/models/ticket.py`; `pb_govt_reports/models/pb_filing_flow.py`; `pb_audit/` |
| Employee personal workspace | `pb_me_portal/views/portal_templates.xml`; `pb_me_portal/models/pb_me_home.py`; `pb_ess_workforce/`; personal domain extensions |
| Existing icon vocabulary | `pb_import_kit/static/src/js/import_icons.js` |

The original report’s source observations establish a foundation, not completeness. The highest-value verification is to follow actual data and permission checks through the proposed journeys rather than infer behavior from module names.

## 14 Proposed phasing and release criteria

### Baseline phasing

- First release: A1–A4, covering the navigation/destination catalogue, role homes/team composition, cross-job Applications/Offers views and payroll readiness.
- Next release: A5–A11, covering spend, uncovered employment changes, evidence/skills, talent summary, policies, obligations and service reporting.
- Separate scope: A12, covering manufacturing, advanced talent/learning programmes and external financial/booking feeds.

The owner has not approved this sequence. The reviewer should decide whether the first release should be smaller. Existing destinations can move before every new view exists, provided each live menu still reaches a useful permitted screen. Phase and feature availability must be explicitly mapped before rollout.

### Required release evidence after approval

| Area | Evidence required |
| --- | --- |
| Findability | Role-based tree tests and task walkthroughs for offers, probation, missing inputs, payslips and approved-unpaid claims. |
| Chrome user journeys | Landing → menu → preserved filtered list → detail → permitted action → return. Cover desktop, narrow mobile and English/Vietnamese labels. |
| Authorization | Allowed/denied users, direct URLs, row counts, exports and company/team/field boundaries. Hidden menus alone are insufficient. |
| Payroll regression | Representative runs retain intended populations, inputs, amounts and approval history after navigation changes. Cover multiple pay groups, off-cycle/test runs, stale readiness and reopened inputs. |
| Reconciliation | Dashboard/source-row agreement, claim/accounting payment agreement, filing evidence, and no duplicate source inputs. |
| Compatibility | Existing action links, search aliases, tutorial links and employee routes remain meaningful. |
| Recovery | Feature/navigation rollback restores usable navigation without reversing legitimate business transactions. New data migrations have their own safe recovery plan. |

These are tests to run on an eventual deployed implementation. The original HTML review’s desktop/mobile/interaction checks validate only that review document, not the application design or business controls.

### Repository and environment constraints

These constraints were supplied by the owner and read from `AGENTS.md` for this handover on 20 October 2026. Re-read the then-current instructions before any separately authorized implementation. This section provides context; it does not authorize deployment during review.

- Commit only relevant changes and preserve unrelated or concurrent-session work.
- Before deployment, re-check the latest branch and deploy the latest combined repository state to all active environments/databases in scope.
- SSH target: `Payobook19v2`. The only deployment addons directory is `/odoo/odoo-server/addons`; preserve standard addons from the server’s own checkout.
- Active databases: `payobook`, `payobook_template`, `p0clone`, `rize`. Upgrade custom modules only where already installed; verify combined custom-module content and installed versions across all four.
- `rize` is production. Its backups are exempt from automatic deletion. Nonproduction backups have seven-day retention while preserving the latest usable backup; permanent retirement/final archives do not expire automatically.
- ABM is retired. Do not deploy, recreate, upgrade or provision `abm` or `abm.payobook.com` without an explicit owner request. Preserve `/odoo/archives/abm-20261020` and the retired hostname response.
- Test the deployed implementation, including Chrome end to end when behavior is user-facing; report commit, deployment targets and results.
- Remove only PNGs/screenshots generated by the current testing. Preserve product assets, user images and unrelated files.
- Preserve active processes, live addon targets, customer workbooks and unknown temporary files. Never blanket-delete `/tmp`.
- Ask for genuinely missing targets, credentials or required test paths.

## 15 Source provenance and limits

### Design baseline

- Original visual report: [Payobook navigation review](payobook-navigation-review-20261019.html).
- Report commit: `d43553eac`, titled `Document Payobook navigation and screen architecture review`.
- Report SHA-256 at handover preparation: `d18e7f2dce6267886d6c23c00e6ba87c4b11ebc159b6b7cf1cca93e7fd9d8eb5`.
- Original owner proposal: [Payobook Menu Sub Menu Word document](<../../RIZE/Payobook Menu-Sub Menu-.docx>).
- Original repository branch: `19.1`. The source review was a point-in-time assessment; the branch can advance through other sessions.
- Current operating constraints: [AGENTS.md](../../AGENTS.md).

Section 7 is transcribed from the HTML’s embedded architecture data, retaining all 66 destination references, labels, icons, local-view lists, source/dependency notes and treatment explanations. The surrounding handover organizes that design for review. Conceptual process requirements, acceptance journeys and open questions are review elaborations; they do not silently amend the baseline menu or assert implemented behavior.

### Scope of the original assessment

The prior review inspected the demo administrator navigation and existing employee portal session, read the supplied Word proposal and examined relevant repository modules. It did not sign in as every persona, test every business workflow, verify every installed database/module version or conduct a complete security or jurisdictional compliance audit.

The Word document was text-only in the inspected OOXML: 658 paragraphs, no embedded images/tables, and no tracked changes or comments found. Its capability coverage informed the design; its pagination did not determine the architecture.

No payroll records, candidate data, employee identifiers or access tokens are required for this handover. The reviewer can assess the architecture without receiving customer datasets or credentials.

### Market patterns used as inspiration

These references were consulted for the original assessment on 19 October 2026. They support general patterns; they are not feature-parity certifications or claims that a vendor’s whole menu should be copied.

- [Workday Concept Hubs](https://doc.workday.com/admin-guide/en-us/manage-workday/tenant-configuration/navigation/concept--hubs.html): topic/job-function workspaces combining overview, tasks and reports.
- [Rippling platform](https://www.rippling.com/platform): shared reporting, workflows, permissions and approval services across domains.
- [BambooHR Employee Self Service](https://www.bamboohr.com/resources/hr-glossary/employee-self-service): permitted personal actions with manager oversight.
- [Nielsen Norman Group Flat versus Deep Website Hierarchies](https://www.nngroup.com/articles/flat-vs-deep-hierarchy/): tradeoffs between breadth, depth and understandable grouping.
- [W3C WCAG 2.2](https://www.w3.org/TR/WCAG22/): accessibility requirements for navigation and interaction. The design has not been certified conformant.

## 16 Expected independent review output

A useful review changes a decision or reduces uncertainty. It should identify the affected user and exact proposed destination/process rather than offer only general aesthetic advice.

Use this structure:

```text
Verdict
Adopt / adopt with changes / redesign
Main reasons and material conditions

Ranked findings
F01 | Critical/High/Medium/Low | D/A/J/destination reference
Observation or design concern
Affected user and consequence
Recommended change and tradeoff
Evidence or owner decision still needed

Revised architecture
Only changed branches, with reasons
Existing routes/records that must remain canonical

First-release scope
Navigation and labels
Views over existing records
New business workflows or data
External integrations and deferred work
Dependencies and explicit exclusions

Validation and decisions
Acceptance criteria
Claims requiring code/live verification
Owner choices needed before implementation
```

The reviewer should challenge the baseline where warranted, retain evidence-backed reuse, and identify a smaller implementation path if it can achieve the owner’s objective with less risk. The next step remains an owner decision on the reviewed design and scope.
