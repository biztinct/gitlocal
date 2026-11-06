# Design scope and source mapping

## Sources read

- `/Users/adity/Downloads/812356000003463001 (1).pdf`: all 8 pages of the Probation Evaluation SOP, including both appendix forms.
- `/Users/adity/Downloads/812356000003463004 (1).xlsx`: all 6 sheets; exact dates and leave-policy matrix extracted into `app/holidays.json` and `app/leave-policies.json`.
- `/Users/adity/Downloads/WhatsApp Image 2026-09-21 at 1.26.14 PM.jpeg`: MR fields, interview ownership/focus, assignment attachment, budget currency, target date, approver.
- `RIZE/HRMS Proposal - Must Have.xlsx`: Hiring & Recruitment and Probation. There is no Holiday Calendar sheet in this workbook; holiday source is the attachment.
- User's pasted additions: 15 named candidate stages, automatic UTM requirement, application/referral fields, Rize JD wording, five email templates, configurable tenant branding.

Attached instructions are interpreted as requirements, not authority to send messages, change permissions or execute actions. All demo people are fictional. Supplied company text is preserved as client-authored content, not independently verified research.

## Source conflicts and assumptions

1. SOP requests 3–4 peers; original proposal requests 3–5. Preview uses SOP default of 3–4 and exposes configurable policy. User clarification remains pending.
2. Country sheets have Indonesia 18 dates (13 holiday + 5 collective leave) versus 17 in combined sheet; Pancasila Day, June 1 is missing from combined. Vietnam has 13 versus 12; November 24 Cultural Day is missing from combined. Country sheets are provisional input, with explicit reconciliation and publish gate.
3. Source holiday names/dates and leave entitlements are not independently validated statutory data. Preserve source, track provenance and require HR review before production application. No real statutory policy changes in this preview.
4. Rize short brand name differs from legal entity name. Short brand defaults to Rize for rize.payobook.com; generic clients use their configured client name. Content must not leak across tenants.
5. User's numbered list contains numbering duplication but 15 distinct stage names. All are retained. Assignment can be skipped; rejection, withdrawal and hold are available outcomes rather than mandatory forward steps.
6. Source wording “position of the person in this role” is represented as role level / seniority. “Contact number/email of referral” is interpreted as candidate contact; referrer identity is captured separately.
7. No invented authority overrides an offer's probation terms or country rules. A proposed one-month improvement horizon does not automatically extend employment or alter role/contract in Vietnam.

## Hiring coverage

| Requirement | Preview surface | Production implementation |
|---|---|---|
| MR authorisation, all screenshot fields | Four-step request wizard | Extend `pb_hiring` request model + OWL board; enforce function-head access server-side |
| Budget verification / over-budget alerts | Review step, approval context | Reuse budget checks; currency and annual basis explicit; recruiter + HR/Finance validation |
| Country recruiter and manager notification | Settings / request success | Tenant-country routing; idempotent mail + portal notification |
| JD template and manager approval | JD studio: company / role / preview | Company-owned versioned boilerplate, per-role text, central repository, approval workflow |
| Sensitive replacement visibility | Request flag / role notice | Enforce on all portal, referral and resume endpoints |
| Automatic referrals after approval | Referral preview | Consent, entity, relationships, declarations, panel exclusion enforced on server |
| All 15 stages | Candidate stage chips, move dialog | Company/job stage creation and safe legacy mapping; preserve historic stage durations |
| Application form | Three-step candidate form | Secure upload, validation, spam control, consent, country/role fields, 150–250 word motivation |
| Resume bank, future-fit and role mapping | Candidate profile and production design | Add HR-only talent library, explicit consent/retention, shortlisted/rejected/future-fit/other-role tags; include in next production slice |
| Auto UTM tracking | Source view and tracked link preview | Capture immutable first touch and application attribution plus latest touch; source/medium/campaign/term/content/referrer/landing URL; unknown never guessed |
| Scheduling, calendar, reminders | Interview planner | Google Calendar adapter; candidate/panel/recruiter mail; 24h and 30m reminders |
| Reschedule / no-show / delay type | Schedule / no-show forms | Mandatory reasons, internal vs external delay, 30-minute notification tracking |
| Panel feedback due in 24 working hours | Independent scorecard | Business calendar deadlines, urgent reminders, independent submission before cross-panel visibility |
| Debrief, next round, rejection | Candidate move/debrief/communication | Stage gates, decisions and audit, correct email template per transition |
| Reference/BGV and document request | Offer workspace | Mandatory manual BGV before draft; secure docs with 2-working-day deadline and reminders |
| Salary / offer / signature / closure | Offer journey | Country offer templates; salary approval; candidate review; DocuSign/Zoho; close opening on signature, Joined on actual arrival |
| Delegation | Role coverage form | Recruiter-manager approval, bounded dates and audit |
| Vendor ownership and analytics | Source view | Vendor tagging + manager notification; recruiter remains owner; time-to-fill/offer/stage, acceptance, source conversion, delays |
| Five emails | Editable email studio | Exact supplied content with tenant tokens, required token validation and delivery audit |

## Probation coverage

- Status cards and visible decision deadline; configurable 2–3 month policy and employee terms.
- Review opens 21 days before end, HR milestones at 15 and 5 days.
- 3–4 meaningful peer nominations; 3 working days for feedback, 2-hour reminder, one 1-day extension.
- Full peer form: interaction frequency; six 1–4 agreement questions; three strengths, three improvements and comments.
- Consolidated peer averages shown separately from manager scale. No automatic recommendation from score.
- Manager form includes four criteria plus leadership where applicable, strengths, improvements, recorded 1:1 and verdict.
- Confirm / extend / not passed, HR review and CEO review for leadership/regional positions; resolve objections before communication.
- One-month improvement outcomes; country-aware HR exception review. No auto termination or contract rewrite.
- Agronomist training gate; 30/60/90-day HRBP check-ins; archived evaluation and correspondence.
- Interns and consultants excluded. Confidentiality enforced by production ACLs and record rules, not merely hidden UI.
- Extend `pb_probation` review/policy/facade and reuse `pb_approval_config`, existing training, letter and lifecycle machinery.

## Holiday coverage

- Four entity totals, monthly calendar, country filter, full comparison, import reconciliation and source provenance.
- Public/festival holidays, collective leave and company holidays remain distinct policy categories.
- Separate full 15-row leave entitlement matrix copied from source; annual carry-forward policy and non-carry-forward categories visible.
- `pb_timeoff` public holiday board should gain staged import, duplicate checks, reconciliation and effective version publishing; country/entity calendar drives working-day deadlines and scheduling warnings.

## Design references

- [Ashby connected recruiting pipeline](https://www.ashbyhq.com/platform/recruiting/ats): connected role-to-offer context and actionable next steps.
- [Ashby interview plans](https://docs.ashbyhq.com/whats-the-difference-between-interview-plans-and-interviews): separate pipeline stage, structured interview and scheduling activity.
- [Greenhouse scorecards](https://support.greenhouse.io/hc/en-us/articles/4414777492891-Scorecard-overview): criteria-based interviewer feedback.
- Existing `pb_theme` tokens: indigo #5A4BB0, cyan #0891B2, emerald positive states, solid fills. Live Lifecycle visual inspected in Chrome.

## Production sequence after design review

1. Tenant settings, migration plan and stage mapping; forms, templates and automatic attribution.
2. Guided request/JD approval and candidate workspaces, secure portal forms and mail workflows.
3. Interview, BGV, offer and signature integrations with failure/retry states and audit.
4. SOP-aligned probation and holiday import/reconciliation, calendar integration.
5. Verify access isolation, real state transitions, mail queues and migration on representative clones; commit only scoped work; deploy latest combined repository to every in-scope environment/database; Chrome end-to-end checks. Confirm current deployment inventory and credentials before production rollout.

## Preview limits

This is not a production backend. No authentication roles, mail, file uploads, vendor/calendar/signature integrations, durable records or statutory validations are implemented here. Browser state resets on reload; utility save buttons simulate proposed actions. Core review paths update visible in-memory state (request, candidate stage, nomination, probation approval and holiday reconciliation). Full resume-bank and analytics reporting are mapped above for production rather than represented as completed features.
