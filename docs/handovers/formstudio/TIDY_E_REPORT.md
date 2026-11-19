# PAUSED — owner pause, 2026-11-19 (Sydney afternoon)

**Done:** module `pb_employee_form_tidy` built and pushed on `tidy-e` (3 feature
commits + this WIP): form rules (remove 32 / country 40+2), Country of Work label +
top of form + quiet hint, dates show the year, Payroll-ready reads the approved bank
account, Country of Work from pay file / Updates sheets / Mapping lane, "Fill Country
of Work" button with preview, vi/id PO (gate OK, no brand word). Own suite: 23/23
green on `tidy_e_t`. Browser walk done on desktop + phone (screenshots in
`tidy_e_shots/`, console clean apart from pre-existing missing app icons). Phone fix
for the People header row (wrap) added in the WIP commit — re-run the module suite
after resume to confirm.

**Next (on "continue"):**
1. Baseline suites (`tidy_e_bl`, touched modules, without the module) were STOPPED
   mid-run by the pause — re-run baseline, then the same suites with the module
   (`scratchpad/tidy/suite.sh`), compare failure sets (test 10).
2. Golden payslip per country: with module = VN/ID/IN/SG NETPAY 5,000 + WAGE 12,345;
   run the same `golden.py` on the baseline database and compare (test 8, cross-DB).
3. Silent-install check (hash of `hr_employee` before/after `-i`) (test 11).
4. Write the full report (per-box table, verdict changes, before/after counts, deploy
   notes, owner questions), drop `tidy_e_t`, `tidy_e_bl`, `tidy_e_base`.

Local Payroll-ready on the walk data (8 people): before 1 with bank / 7 not ready /
12%; after 2 / 6 / 25% (India person with only the old free-text box drops out;
Vietnam-file and approved-account people count).

Local databases kept for resume: `tidy_e_base`, `tidy_e_t`, `tidy_e_bl` (all local,
DEMO data only). No server touched. No server or test process left running.
