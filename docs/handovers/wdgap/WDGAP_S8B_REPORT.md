# WDGAP S8-B — A person's working life: report

## PAUSED (owner pause, 2026-11-15)

**Where I stopped.** All three new modules are written as a first full draft
(models, security, data, screens, patches, tests) and committed as WIP. They
have NOT yet been installed or tested. The baseline run of the inherited
suites was stopped part-way by the pause (it had finished pb_contract_lifecycle,
pb_employee_vault, biz_audit_trail, pb_lifecycle, pb_orgchart, pb_pay and was
inside pb_records), so it must be run again from the start.

**Exact next step on resume** (local database `wdgap_s8b_t` is kept, at the
worktree tree + `pb_retro`, with none of the three new modules installed):

1. Re-run the baseline BEFORE installing anything:
   `bash scratchpad/s8b/suite.sh baseline "/pb_contract_lifecycle,/pb_employee_vault,/pb_scheme_map,/pb_vendor_access,/pb_records,/pb_orgchart,/pb_pay,/biz_audit_trail,/pb_lifecycle,/pb_people_hub"`
   (scratch folder `/private/tmp/claude-502/-Users-adity-Documents-GitHub-gitlocal/684f830c-6ed1-451c-a2de-0875eedd2479/scratchpad/s8b/`).
2. `bash scratchpad/s8b/install.sh first -i` — installs `pb_job_change`,
   `pb_contract_rules`, `pb_agency_staff` and runs their tests (JC1–JC14,
   CR1–CR9, AG1–AG8); fix what fails.
3. Re-run the same baseline suites with the modules installed; failure set
   must equal step 1.
4. `bash scratchpad/s8b/export.sh` → write `i18n/vi_VN.po` + `id_ID.po` for
   all three modules; PO parse gate.
5. Browser walk (People hub, employee side panel, org chart, contract
   decisions, Vendors; console clean); measure renewal pay-line loss on the
   local copy; finish this report (sections below); commit; push.

## Built so far (draft, untested)

| Module | What |
|---|---|
| `pb_job_change` 19.0.1.0.0 | `pb.job.change` (+ lines) on the approval engine, process key `jobchange` (manager when they have a login → HR lead → Finance only above the guidance); all values written together on the start date (person + running contract, wage with `pb.pay.apply` row, pay lines with dated change rows, wage change row when the scheme has a BASIC/WAGE/BASE input); future dates held "Scheduled" and written by a quiet hourly job; moved-since check; 24-hour take back; letters by `selection_add` (promotion / transfer / job change); one event on the timeline; "Paid by" before/after (read-only scheme-map override); paid-month banner with a door to a new draft Past-month re-work (probe, runtime lookup, no back-pay input); C-1 `pb_start_for_employee`; board + guided flow screen; side-panel button + chip; org chart button; ⌘K 4460–4461 |
| `pb_contract_rules` 19.0.1.0.0 | `pb.contract.rule` (VN + ID rows with sources, "to confirm with an adviser"); chain counter (renewal link or short break; trial agreements excluded; earlier contracts typed on the person); red warning + "Make it permanent" on Extend; never blocks; extension route fact `past_fixed_term_rule`; drawer line; Updates catalogue fields; ⌘K 4465 |
| `pb_agency_staff` 19.0.1.0.0 | `pb.agency.worker` (not an employee: no employee, contract, login or payslip link); People lens "Agency staff" (59); "+N agency staff" beside the headcount; quiet board + filter kit + drawer with papers; Vendors drawer lists them for HR; ⌘K 4470 |

No existing file was edited.
