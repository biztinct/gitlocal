# TIDY-E go-live — merge, go live ×5, verify (employee Full details clean-up)

Method: EXACTLY as `docs/handovers/wdgap/WDGAP_S2_DEPLOY_HANDOVER.md` (MAIN checkout)
and the chain it names; proven command sequence in `WDGAP_S2_DEPLOY_REPORT.md` /
`WDGAP_S2F_REPORT.md` on `origin/19.1`. ALL non-negotiables of that handover apply
unchanged (five databases only — `payobook`, `payobook_template`, `p0clone`, `rize`,
`sudima`; never `abm`, `pbf_preview`, `recruit_connect_20261023`; ONE addons dir;
scoped rsync, never `--delete` into the addons root; `git archive` from the pushed
commit; backups ×5 first; hashes + `latest_version` ×5; asset purge +
`web.assets.version` bump; `/opt/deploy-notes.md` START/DONE; never over another
deployer's open START; compare server manifest versions before every rsync and never
roll a module back; 15 quiet minutes on rize/payobook before stopping the service;
never leave it stopped; white-label "Odoo" rule; no credentials; never print employee
data — counts only; explicit-path staging; no stash; no force-push; tenant email off
on purpose; demo data add-only; trailer `Co-Authored-By: Claude Opus 5.5
<noreply@anthropic.com>`; bounded polls, never end a turn on "waiting"). NORMAL tier
with a pay-adjacent figure (Payroll-ready) and one data action (Country of Work).

Read: `FORMSTUDIO_LEDGER.md` (R11–R13), `FIELD_TIDY_HANDOVER.md`,
`FIELD_AUDIT_FACTS.md` (same folder), and `TIDY_E_REPORT.md` on `origin/tidy-e` — its
deploy notes and merge-time tasks are binding. If that report still starts with
PAUSED or lacks test results, STOP and say so.

1. Merge `tidy-e` into `tidy-e-merge` from `origin/19.1`; local run of its numbered
   tests + touched suites = baseline. Do NOT merge any `fs-*` branch.
2. Rehearsal on a `rize` copy (jobs + mail off; `dropdb --force` after): install /
   upgrade clean; no employee, contract, payslip or bank row changed by the upgrade
   (counts + checksums); one recent rize payslip per country recomputed identical;
   on the copy, as HR in a browser (or via the same view-rendering call), one
   employee each of Vietnam, Indonesia, India, Singapore: only general boxes + own
   country's boxes; the 31 removed boxes absent; save the form → no hidden value
   changed. Payroll-ready before/after counts on the copy. Press the on-screen "Fill
   empty Country of Work from pay set-up" action on the copy: record the preview.
3. Go live ×5 (`-i pb_employee_form_tidy`, `-u` whatever the report names). After:
   cron counts equal the snapshot; nothing mailed; Sudima's waiting bank batch
   untouched.
4. Country of Work (owner rulings R12/R13): on EACH live database press the SAME
   on-screen action (through the UI or by calling exactly the method the button
   calls, as a real HR-manager user — not a private script): record the preview
   (per country, undecided + why), confirm, record what was filled. Only empties are
   filled. Expected: rize almost nothing (2 logins with no contract stay empty);
   sudima → Vietnam; payobook demo → by pay set-up. If the preview on any database
   looks wrong (e.g. most people undecided, or a country that customer does not
   have), do NOT confirm on that database — report.
5. Checks on rize.payobook.com are look-only and need care (a customer is testing):
   do not sign in as a customer user; verify by read-only queries + the view-render
   call. Browser checks on payobook.com (QA login path as in the S2 report): one
   employee per country — boxes by country, Date of Joining with the year, "Country
   of Work" label; People list "Payroll-ready" figure and "Bank details" filter;
   Mapping offers "Country of Work"; console clean.
6. Report `docs/handovers/formstudio/TIDY_E_DEPLOY_REPORT.md` (commit + push to
   19.1): before/after Payroll-ready per database; Country of Work filled per
   database and country; who is still empty and why (counts). Final message under
   250 words, plain simple English, screen words only.
