# WDGAP Step 8 go-live — merge, go live ×5, verify (S8-A, S8-B, S8-C)

Method: EXACTLY as `WDGAP_S5_DEPLOY_HANDOVER.md` (main checkout, same directory) and the
chain it names (`WDGAP_W2B_DEPLOY_HANDOVER.md`, `WDGAP_W2B_DEPLOY_REPORT.md`,
`WDGAP_LEDGER.md`, `WDGAP_WAVE_RULES.md`). Read those, `WDGAP_S8_HANDOVER.md` ("Step
go-live note"), `WDGAP_S8_FACTS.md` (§9 "Shared seams inside S8", §10),
`WDGAP_OWNER_RULINGS_2026-11-15.md` (J1–J6, C-1, C-2, and the 2026-11-16 rulings SC2,
CC1, JL1), and the three phase reports on their branches — each has deploy notes you
must follow: `WDGAP_S8A_REPORT.md` (`origin/wdgap-s8a` ba1f6adbe; NEW `pb_pay_scales`,
`pb_pay_package`; edits `pb_pay`, `pb_contracts`), `WDGAP_S8B_REPORT.md`
(`origin/wdgap-s8b`; NEW `pb_job_change`, `pb_contract_rules`, `pb_agency_staff`),
`WDGAP_S8C_REPORT.md` (`origin/wdgap-s8c` 7b4f07159; NEW `pb_org_structure`,
`pb_plan_hiring`). All non-negotiables of the S5 deploy handover apply unchanged
(five databases only; never abm; ONE addons dir; scoped rsync; `git archive` from the
pushed commit; backups first; deploy notes START/DONE; never over another deployer's
open START; never leave the service stopped; white-label "Odoo" rule; no credentials;
explicit-path staging; no force-push; never `pb_lifecycle/` or `pb_pack_*`; commit
trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`). RISKY tier (wage
and pay lines; seven new modules). Only the differences are written here.

## 0. ORDER WITH THE STEP 5 GO-LIVE (binding)

Another agent ("WDGAP S5") is merging and taking Step 5 + back-pay lines live right
now. Do your merge and ALL local testing in parallel on branch `wdgap-s8-merge` from
`origin/19.1`, but do NOT push to `origin 19.1` and do NOT touch the live server until
BOTH are true: (a) `/opt/deploy-notes.md` shows the WDGAP S5 DONE line, and (b)
`origin/19.1` contains the Step 5 merge. Poll with a bounded loop (every 10 minutes, up
to 6 hours; report if still not there). Then merge the new `origin/19.1` into your
branch, re-run the seam tests below that the Step 5 code can touch (contracts, pay
tab, Mission/People hub assets, `pb_retro` deep-link from Change job) and the suites of
modules both steps edited, and continue. If the S5 line is FAILED/held, stop before
go-live and report.

## 1. Merge (order: s8a, s8b, s8c)

Version raises the builders left for you: every edited existing module per the three
reports. Seams (merged tree):
a. FACTS §9 "Shared seams inside S8" table — every row.
b. S8-B Change job with a pay change on a contract that is on an S8-A scale → the
   contract shows Pinned/Drifted correctly afterwards; nothing writes a payslip.
c. S8-B past-dated pay change → button opens a draft Past-month re-work (`pb_retro`,
   live); with the Step 5 merge in, sending that re-work for payment still works.
d. S8-C cost-centre history guard (owner ruling CC1: finished payslips keep the cost
   centre they were paid under) + S8-B transfer that changes department/cost centre:
   past payslip lines unchanged, drafts follow.
e. S8-C pause hiring + S8-C plan → draft hiring requests: a paused team's plan rows are
   refused with the plain reason, nothing half-created.
f. Agency staff "+N" beside headcount and S8-C People › Jobs tab and S8-A Scales tab
   load in one assets bundle; browser smoke at desktop AND phone width (S8-C could only
   check phone width), console clean.
g. Hub and People hub suites: S8-C saw 3 failures it could not baseline — run them on
   `origin/19.1` WITHOUT the new modules first to establish the baseline; any failure
   caused by the new modules is a blocker to fix or report.
Combined local run on one database `wdgap_s8m_t`; failure set = union of baselines.
Other builders are on this Mac: own port, own browser address, never touch their
databases. Never wait silently — bounded polls.

## 2. Rehearsal — short

Backups ×5. Practice install/upgrade on a `rize` copy (jobs + mail off first;
`dropdb --force` after); old-vs-new recompute of one recent rize run — identical line
for line; confirm no contract, wage, pay line or payslip row changed by install
(counts + sums before/after), and no scale/package/job-change/agency rows created.
Also measure on the rize and payobook copies (read-only) the renewal count query from
the S8-B report (how many people are at or over the Vietnam/Indonesia fixed-term
limits) — report the numbers; change nothing.

## 3. Read-only live checks

As S5, plus: `pb_hiring`, `pb_orgchart`, `pb_offboarding`, `pb_decision_room` and the
Vendors module (`pb_vendor_access`, needed by `pb_agency_staff`) installed on each of
the five. A module whose dependency is missing on a database is NOT installed there
(no force-install of the dependency) — report it.

## 4. Go live, 5. Checks on payobook.com (QA login; demo data add-only)

`-u` edited modules, `-i` the seven new ones ×5. Then look-only: People › Pay → Scales
tab opens empty; a demo contract drawer shows "Build from a total" (open, do not
apply); People → Change job opens prefilled for a demo person (cancel); People › Jobs
shows levels, cost centres, pause switch (do not pause); agency staff list empty;
Exits drawer shows "Would rehire" for HR; one existing demo payslip PDF still opens.
Cheap open-the-screen checks on the other four sites.

## 6. Report — `WDGAP_S8_DEPLOY_REPORT.md` (commit + push to 19.1)

As S5. Carry forward the owner questions from the three reports in plain words
(notably S8-B: extended contracts lose the old contract's allowances; Pay › Changes
writes a raise at once whatever start date it shows; adviser to confirm the VN/ID
limits). Final message under 300 words, plain English, screen words only. Usage-limit
error mid-deploy: finish the database you are on, START the service, DONE/FAILED in the
deploy notes, PAUSED at the top of the report.
