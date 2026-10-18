# Vietnam information-only Contract Text components

The owner approved adding all 22 previously excluded, non-calculated VN sheet
headings to **Rize Vietnam Payroll HC Oct 2026**, Draft configuration **4639**,
code `RIZE_VIETNAM_HC_202610`. This includes the four Indonesia-labelled headings.
The changes are confined to the **rize** database; shared application code is
verified/deployed across all existing Payobook19v2 application databases.

| VN columns | Component labels |
| --- | --- |
| N–O | Blood Type; Religion |
| AS–AV | NPWP Number (Tax Number)-Indo; Family Card Number-Indo; BPJS Keternagakerjaan Number-Indo; BPJS Kesehatan Number-Indo |
| AX–AZ | Background Check Completed; Background Check/Ref Check status; Background Check/Ref Check Links |
| BA–BC | Signed Offer Letter; NDA/Employment Agreement; Personal Document Link |
| CI–CK | IT Asset type; IT Asset number; Software access given |
| CL–CO | Last Appraisal Date; Performance Rating; Promotion Date (if any); PIP History (if any) |
| CT–CV | University/School; Major; Education Level |

Each component preserves the spreadsheet label and binds to its exact
`VN|<heading>` key. It is an input of value kind **text**, stored as a
**Contract Text** component, column role **contract**, report group
**Employee information**, pay role **information only**, not required, and hidden
from payslips. Dates and identifiers deliberately remain text under the owner's
instruction. No new Employee or Contract SQL columns are introduced. Actual
values, when separately reviewed/imported, use the existing contract-component
line model. This change does not import any source employee values.

The scoped migration appends components without renumbering any existing
immutable component letter or changing any formula. It retains the owner's
current source priority, native mappings, all 11 recurring placeholders, all
17 monthly bindings, separate registered-tax-dependent setting and native
dependent-count transformation. Draft state, roster and payroll assignments
remain unchanged. The original workbook/sample metadata is preserved; the
18 calculated/generated source columns remain hidden.

New fields are selected in the **Employee records** layout lane. They appear in
the fully protected third sheet of the monthly download and in the separate
Employee/Contract records workbook. Existing Time/Monthly adjustments selections
and record-field order are preserved. Downloaded values come from current saved
records, so new contract-text values are initially blank.

`tools/add_rize_vietnam_hr_context.py` defaults to a rollback dry run, refuses any
database other than `rize`, checks the expected Draft/code and verifies existing
rows instead of overwriting them on rerun. Full hashes of Employee, Contract,
contract advantage, payslip and run rows prove that business values do not
change. The non-personal definition and its read-only extractor also include the
22 fields so a future new configuration keeps these mappings.

## Preparation checks

The production rollback dry run passed: **22 source wires**, **22 Contract Text
destinations**, **138 components / 115 inputs**, **30 of 30 payroll scenarios**,
zero configuration errors, and both actual workbook generators containing every
new heading. Monthly Time/adjustment selections remain **4 / 13**. The Records
lane grows **75 → 97** fields (plus pinned Employee Name); the review download
still contains **63 existing Employee records out of 70 approved source people**.
All existing rule/source/native-mapping snapshots and business-row hashes match.

Deployment and Chrome results are recorded below after live verification.
