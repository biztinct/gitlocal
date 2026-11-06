# Approval Matrix — design note (POC stage)

**12 September 2026 · POC for owner review · no product code changed**

Companion to the clickable POC at `docs/design/approval-matrix-poc.html` (multi-file: `docs/design/approval-matrix-poc/`). The 12 Sep handover `APPROVAL_WORKFLOWS_DESIGN_HANDOVER.md` remains the behaviour contract for the engine (selection rules, invariants, acceptance cases); this note widens its scope to the whole product and records the decisions taken with the owner.

## 1. What the product does today (verified in code)

- Five separate approval engines, none configurable by a user: the shared chain mixin (11 request types, transitions hard-coded per type); the pay run chain (Officer → HR → Finance, one on/off setting); the comp-cycle step model (data-driven, no permission checks); formula release sign-off (one person; client "signature" is a typed name on a public link); plain state writes.
- Three inboxes that do not see each other: the Home Approvals lens (pay runs only), the Workforce team lens (4 types), per-form buttons.
- No gate at all on: bank file generation, mark as paid, journals, Records Desk bulk writes (incl. file uploads), budget uploads, exchange rates, role grants, support access, tenant suspension, scheme activation, statutory rate tables, full & final, retro adjustments, closing/reopening a payroll month, unlocking a locked day.
- No submit/approve on the weekly attendance grid at all.
- Access hand-overs move approval power silently; the audit console sees only the chain log.
- The New configuration journey (Connect, 3 of 6) says custom approval rules are "coming in a later release" and refuses to open the card.

## 2. Product decision

**Approval Matrix**: one place (Settings → Approval Matrix, also reachable from the Approvals inbox) listing every process that can need sign-off, each with a readable, versioned workflow. One engine underneath, one inbox on top, one adapter per business object.

| Layer | Answers | Example |
|---|---|---|
| Process catalogue | what can need approval | Pay run, Bank file, Pay change, Weekly timesheet, Scheme change, Role grant |
| Workflow (versioned) | how it is checked | HR lead reviews, then Finance approves; from ₫600m add the Country director |
| Responsibilities | who fills a seat, where | HR lead for Vietnam / Retail = Nithya, backup Monica |
| Binding | where a workflow applies | company default → division → scheme → scheme + division; run kind |

## 3. Catalogue

Seven areas: Pay · Money out · Pay data · People · Time · Setup & rules · Platform. Forty processes in the POC; each row is Published, Draft, Needs people, or Not connected yet. A row is Published only when the workflow is published **and** the feature is wired to the engine. Money-out rows carry a recommendation (two people) that the publisher confirms; it is advice, never a lock.

## 4. What a workflow designer can do

1. Steps: Review · Final approval · Joint approval (everyone, distinct people) · Any one of a team · Notify only · Only when… (conditions on typed facts).
2. Who: Their manager · Manager's manager · A role in this scope · Specific people · One of a team. Roles resolve to names with provenance.
3. Route by amount (or hours, headcount, % change) as a first-class ladder, in the run's own currency.
4. Scope layering with per-division and per-scheme exceptions; most specific wins; ties refused at publish.
5. Safeguards: independent approver (default, can be switched off per workflow), self-approval exceptions with mandatory reason, repeated-person rule, required evidence, calendar-based due dates, remind → escalate → optional reassign. A late request is never approved by the system on its own.
6. "No approval needed" lane for **any** process (owner decision 12 Sep: allowed everywhere, a one-person company must work), always shown as a card and on the Matrix row, every use logged. Removing the last step switches to it automatically so the state is never hidden.
7. Backups per seat and time-boxed hand-overs that show "covering for" on every card.
8. Try an example + Check whole coverage; every issue names its fix.
9. Publish with impact: what changes, who is affected, when it starts; in-flight requests keep their version.
10. Import of the setup workbook's Approval Matrix tab as drafts for one company; names remain proposals until an account is chosen.

## 5. Reconciliation with existing features

| Existing place | After |
|---|---|
| New configuration → Connect → Approvals card | Real card: Pay run approval (Inherited / Shared / Custom + Change) and Scheme change approval; Finish shows real coverage |
| Scheme Settings | Approval workflows panel, same component |
| Pay run chain | Replaced outright (no payroll is live). Fixed tiers become an editable preset; the on/off setting is removed |
| Home Approvals lens + Workforce team lens + form buttons | One inbox: My turn / All I can see / Returned / Done; team lens becomes a filter; every request type ships a default workflow equal to today's route |
| Scheme activate / release / rollback / merge | Change proposal (a branch) → approval → apply |
| Comp-cycle step model | Superseded by the engine |
| Access hand-overs | Approval delegation explicit and visible |
| Audit console | Reads engine events (requests, decisions, exceptions, hand-overs, reassignments) |

## 6. Owner decisions recorded

- Build style after go-ahead: phased, Fable designs / Opus builds in-session.
- Fast lane: allowed for every process (owner: "it could be a one-man company").
- No hard minimums anywhere: the system warns and offers options (two people for money out, independence rule, coverage gaps) and the publisher confirms each warning; it never restricts. Confirmations are recorded with the publish.
- No payroll is live: replace, do not run old and new side by side.

## 7. Open for the owner when reviewing the POC

1. Where it lives: Settings → Approval Matrix + Workflows tab in the inbox (recommended) vs. a rail entry.
2. Amount tiers as a first-class control (recommended) vs. conditions only.
3. Which processes ship "Not connected yet" in release one (POC marks: Government filings, Connected-system mappings, Tenant plan changes).

## 8. Build order after go-ahead

Engine + audit → Matrix UI + one inbox → pay run + New configuration reconciliation → timesheets + scheme change → money out + pay data → the rest of the catalogue → Vietnamese + polish. Engineering facts (modules, seams, dependency order, files to touch) are in the approved plan and will be carried into each phase handover.
