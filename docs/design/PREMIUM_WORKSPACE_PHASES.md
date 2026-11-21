# Premium employee and contract workspaces

## Delivery 1: restore the presentation, prove native field editing

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
remain responsible for onchanges, validation, access, writes and audit. Fields
not shown remain hidden dependencies so the original onchange graph is intact.
No field removed by the source form or its permissions is recreated.

Only the six named fields move into the new editor in this delivery. There is
no claim that all native fields have been migrated. Before each next delivery,
inventory its native fields/actions and map them to a premium destination.

## Incremental acceptance

1. Review the actual Job & organisation appearance in drawer and expanded mode.
2. Prove contract approval-controlled fields in an isolated database before
   expanding the contract editor. A proposed pay change must not bypass approval.
3. Move personal/contact and remaining job fields using the proven section
   projection, then documents/resume, then payroll and country-specific groups.
4. Include published custom fields and Form builder rules in each section's
   coverage audit; do not introduce duplicate writable sources.
5. Keep Full details until every applicable field, special widget and action has
   a tested destination. Each delivery is separately committed and deployed.

## Required acceptance checks for delivery 1

- Profile and Terms default; no duplicate record header, native toolbar or tabs.
- Related selectors, native job onchange, saved values and cancellation.
- Draft survives Expand; closing or switching tabs protects unsaved changes.
- Full details remains a separate native form; builder Back returns to the panel.
- Native field attributes and dependencies unchanged; ordinary full form unchanged.
- Existing access, approval, Form builder and document regressions remain green.
- Live Chrome smoke without saving production employee or pay changes.
