# Lifecycle enhancements — September 2026

The production screens extend Payobook's existing Hiring, Probation and Public Holidays modules. They use the existing shared component tokens, indigo actions, navy navigation and solid neutral surfaces.

## Hiring

- Lifecycle → Hiring presents the role journey, a four-step manpower request, a focused role workspace and the next approval action.
- Requests capture country, department, reason, reporting manager, seniority, role description or JD file, three interviewer/focus pairs, optional assignment, budget currency and a distinct target closing date.
- Fifteen canonical candidate stages coexist with historical stages. Assignment is optional. Offer and Joined require the existing background-check and signed-offer/employee flows.
- Company story and five candidate email templates are configurable under Hiring tools. Generic tenants default to the company name; the `rize` database seeds the supplied Rize copy. Existing content is not overwritten on upgrade.
- Job applications capture profile, work authorization, relocation, a 150–250-word motivation and a private validated resume. First-touch and application-touch attribution are captured from the server session, including UTM fields and sanitized source URLs.
- Referrals require candidate consent, relationship disclosure, candidate contact/profile/resume and the panel declaration. The referrer cannot join that candidate's interview panel.
- Existing interview scheduling, calendar invitations, feedback, BGV, document collection, offer approvals, signed-copy recording and joining automation remain connected to the role workspace.

## Probation

- The journey shows peer selection, perspectives, manager conversation, HR/leadership review and outcome.
- Default peer policy is 3–4; HR can configure limits. New feedback uses the SOP's six 1–4 agreement questions, interaction frequency, three strengths and three improvements. Existing feedback keeps its historical questionnaire.
- Peer agreement and manager expectations are separate scales. Peer averages do not overwrite the existing five-point performance rating.
- A completed manager conversation and manager ratings are required before recommendation. Every probation outcome waits for HR review; leadership/regional roles also require the named executive reviewer. Request-changes returns the assessment to the manager.
- Extensions require an improvement plan and record a one-month plan review date. An outcome does not automatically terminate employment.
- Existing policy triggers, reminders, one permitted feedback extension, training gates, check-ins and archived letters continue to apply.

## Holidays

- Monthly calendar, entity comparison, durable import review and leave-policy reference share one workspace.
- Imports retain source/version, distinguish public/company holidays and collective leave, flag conflicts, and require reconciliation before publication to the actual working calendar.
- Published versions preserve their evidence and cannot be edited or deleted through ordinary access. Publication is serialized and cannot be repeated.
- The supplied Rize 2026 country sheets are available as review input. Indonesia's June 1 and Vietnam's November 24 discrepancies are explicit review items. No source dates or entitlements are automatically applied.
- The supplied 15-category leave matrix is seeded as an HR-reviewable reference in Rize; it does not change allocations.

## Tenant setup

1. Configure recruitment branding, company story and manpower approver. Rize's Dhruv approver is selected only when exactly one matching internal user exists; otherwise set the approver explicitly.
2. Maintain country hiring rules and approval routes. Email delivery continues to respect the existing Hiring switches and outgoing mail configuration.
3. Set the HR and executive probation reviewers on the relevant policy. Automatic review opening continues to respect the existing automation switch.
4. Review holiday source rows and leave references with HR before publication.

Google Calendar synchronization and external e-signature execution require a configured provider connection. This release retains working calendar invitations and the signed-document workflow; it does not claim an unconfigured Google/Zoho Sign/DocuSign connection is active.

## Migration and verification

Upgrade/install `pb_hiring` 19.0.1.3.0, `pb_probation` 19.0.1.3.0 and `pb_timeoff` 19.0.1.5.0 in every current application database. Preserve template cron suspension. Clear backend assets after upgrade. Do not replace the server's standard Odoo addons with older vendored repository copies.

Regression and Chrome workflow checks are performed on an isolated restored tenant with external mail disabled. Verify module versions, content hashes, branded screens and service health after deploying the latest combined repository state. Remove the temporary test database, filestore and all test screenshots afterward.

## Removable demo examples

Payobook and Rize are authorized to retain examples. Run the existing shell script with `PB_DEMO_ACTION=lifecycle-load` to add `DEMO Lifecycle journeys`, or `PB_DEMO_ACTION=lifecycle-remove` to remove its exact registered records. The CLI defaults to the operating company with the most employees; set `PB_DEMO_COMPANY_ID` to select a specific company for both load and removal. Repeated loads do not duplicate records, and the existing five-person demo world is preserved. The separate register is also visible under demo settings.

Examples include two hiring roles, three candidates, a manager evaluation and a draft holiday review. All new named business records begin with `DEMO`. Careers jobs remain unpublished and the holiday draft does not change working days. No real recipients are emailed by the loader. ABM and the template receive code only.

The dedicated removal action also tracks the outcome letter and any calendar entries produced from these exact demonstration records. A renamed calendar entry blocks removal for review. Records created independently during later demonstrations should be registered through the existing demo-register workflow.
