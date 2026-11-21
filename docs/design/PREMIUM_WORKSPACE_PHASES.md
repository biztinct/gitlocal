# Premium employee and contract workspaces

## Delivery 1 (previous release): restore the presentation, prove native field editing

Employee opens on the original Profile. Personal, Pay & tax, Company details,
Documents and Timeline remain. Contract opens on its original Terms. Full
details opens the separate complete form; Expand changes the premium panel's
width only. No legacy page is embedded in either panel.

Job & organisation contains two premium cards, with Edit, Save and Cancel:

| Premium card | Native employee fields | Delivery |
| --- | --- | --- |
| Role & organisation | department_id, job_id, job_title | Editable in delivery 1 |
| Reporting & workplace | parent_id, work_location_id, address_id | Editable in delivery 1 |
| Remaining job groups | Job level, division, grade, employee type, performance; coach, buddy, HR partner, login; hours, leave policy, work contacts and badge; key dates | Existing premium summary retained; edit through Full details |
| Personal | Identity, IDs, contacts, family and education | Existing premium summary retained; migrate in a later delivery |
| Pay & tax | Pay setup, approved bank, tax and country-specific facts | Existing protected premium summary retained; migrate with approval tests |
| Company details | Published custom fields | Existing editable Form builder grid retained |
| Documents | Shared categories, attachments and expiry metadata | Existing shared document component retained |
| Resume | Experience, skills, certifications, CV | Full details until migrated |
| Employee system actions | User creation, plans, history and other native buttons | Full details until individually mapped |
| Contract | Terms, components, history, custom fields | Original premium presentation restored; existing editors retained; remaining native fields accessible through Full details |

The Job form projects the server-processed native form into a new layout. It
retains installed field attributes, domains, contexts, widgets, required and
readonly rules, translated labels and ancestor visibility. It does not add a
write facade: native FormController/relational model and hr.employee.web_save
remain responsible for onchanges, validation, access, writes and audit. Only fields referenced by the section and its domains remain hidden dependencies;
unrelated payroll collections are not loaded. Native onchanges for the section
continue through the existing relational model.
No field removed by the source form or its permissions is recreated.

Only the six named fields move into the new editor in this delivery. There is
no claim that all native fields have been migrated. Before each next delivery,
inventory its native fields/actions and map them to a premium destination.

## Delivery 2: native controls throughout the premium workspace

The shared projector now supports scalar fields and selected complex native
widgets. Only the active section mounts its native controller. Its stable
registration preserves a draft while the drawer expands, and navigation checks
the same controller before leaving. No legacy page shell is embedded.

| Section | Premium destination |
| --- | --- |
| Job | Organisation, reporting, locations, contacts, schedule, weekdays, dates, approvers, eligibility, departure, notes and organisation chart |
| Personal | Identity, contact/address, dependent country/state selectors, identity papers and work permit file, family, emergency contacts and education |
| Pay & tax | Existing approved-bank and payroll summaries plus native pay settings, applicable country tax/insurance fields, dependent records and tax requests |
| Résumé | Existing native experience, skills and certification widgets, badges and résumé file actions |
| Documents | Shared document categories with expiry metadata, plus native ID card and driving licence file controls |
| Settings | Native user link, attendance PIN, tags, photo and properties |
| Contract Terms / Components | Existing premium editors and approval route retained |
| Contract Agreement details | Native reference/employee/type, salary structure type, signed terms, payroll facts, exemption evidence and notes |

The original Profile and contract Terms remain the entry screens. Read values
use the same dark semibold typography. Drawer cards use two columns, phones one;
expanded cards use the available width for four field columns. Complex grids
keep their native interaction and horizontal scrolling where necessary.

Form builder lists the projected native controls alongside summary values.
Published visibility/labels and country rules continue through the processed
native view. An unreadable one-to-many or many-to-many collection is omitted
for that role so it cannot block other permitted fields. No access rights are
added and server-side access checks remain authoritative.

Approval-controlled bank changes still use the bank workflow, and contract
money-related changes still use the proposal/apply route. A saved proposal
must not change current terms before approval. System actions such as creating
a login, launch plans, historical versions and smart-button reports retain
Full details as their explicit destination; this delivery does not reproduce
the entire native administration toolbar.

## Acceptance

- Profile and Terms default; no duplicate record header, native toolbar or tabs.
- Native save, cancellation, related selectors, onchanges, dates and file controls.
- Draft survives Expand; closing or switching tabs protects unsaved changes.
- Personal and Job work for HR without requiring payroll collection access.
- Contract protected changes remain pending until the existing approval applies.
- Builder Back restores the originating record/tab/width; inventory matches controls.
- Documents use the same categories as Full details; legacy file fields remain available.
- Inbox clearing a selected status keeps the Where it is filter available.
- Published leave rules remain immutable; Duplicate edition creates a draft.
- Normal full forms are unchanged and remain available for unmapped system actions.
- Live Chrome smoke does not save production employee or pay changes.
