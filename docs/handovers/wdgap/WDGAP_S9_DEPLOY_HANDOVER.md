# WDGAP Step 9 go-live — merge, go live ×5, verify (S9-A, S9-B, S9-C + follow-ups)

Method: EXACTLY as `WDGAP_S5_DEPLOY_HANDOVER.md` and `WDGAP_S8_DEPLOY_HANDOVER.md` (main
checkout, same directory) and the chain they name; the proven command sequence is in
`WDGAP_S5_DEPLOY_REPORT.md` / `WDGAP_S8_DEPLOY_REPORT.md` on `origin/19.1`. Read those,
`WDGAP_LEDGER.md`, `WDGAP_WAVE_RULES.md`, `WDGAP_S9_HANDOVER.md` ("Step go-live note"),
`WDGAP_S9_FACTS.md` (§5, §6), `WDGAP_OWNER_RULINGS_2026-11-15.md` (P1–P6, C-3, C-5 and
the 2026-11-16 rulings RV1–RV4, VC1, VC2), and the three phase reports on their
branches (deploy notes + follow-up sections are binding): `WDGAP_S9A_REPORT.md`
(`origin/wdgap-s9a` 32dc38b4b; NEW `pb_review_forms`; follow-up RV1),
`WDGAP_S9B_REPORT.md` (`origin/wdgap-s9b` c248734c8; NEW `pb_conduct`,
`pb_people_reports`), `WDGAP_S9C_REPORT.md` (`origin/wdgap-s9c` 68e7ed1f8; NEW
`pb_voice`; follow-up VC1). All non-negotiables of the S5 deploy handover apply
unchanged (five databases only; never abm; ONE addons dir; scoped rsync; `git archive`
from the pushed commit; backups first; deploy notes START/DONE; never over another
deployer's open START — "Codex" and "Claude WORKFLOW-2" also deploy; never roll a module
back: compare server versions before rsync; never leave the service stopped; white-label
"Odoo" rule; no credentials; explicit-path staging; no force-push; never `pb_lifecycle/`
or `pb_pack_*`; commit trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`).
RISKY tier (new security rules around the most private records; four new modules).

## 0. Order

Only one go-live at a time. Step 8 is going live now; a Step 6 go-live and a small
"S5-F" go-live may also be queued. Do your merge and ALL local testing now on branch
`wdgap-s9-merge` from `origin/19.1`; before pushing to `origin 19.1` or touching the
server: no open START by anyone in `/opt/deploy-notes.md` (bounded poll, every 10
minutes, up to 6 hours), then merge the then-current `origin/19.1` in and re-run the
seams that the newly merged code can touch (employee home hooks/tiles, Approvals
inbox, People hub assets). Before stopping the service, check the request log for real
signed-in activity on rize/payobook in the last 15 minutes; if someone is active, wait
(re-check every 10 minutes, up to 90 minutes), then hold and report.

## 1. Merge (order: s9a, s9b, s9c)

- **Squash-merge `wdgap-s9b`** (its WIP commits carry a report-draft line describing
  throwaway local test-login passwords — harmless, database deleted, but it must not
  enter `19.1` history; also delete that line from `WDGAP_S9B_REPORT.md` if it is still
  in the final file).
- Merge-time tasks the builders left for you (the ONE sanctioned `pb_me_portal` edit:
  the tile list + its pinned test; keep minimal; list file/lines):
  a. "My review" tile (RV4) + the home entry S9-A removed — exact change in the S9-A
     report "Follow-up RV1".
  b. "Letters from HR" tile/page entry — exact two-line change in the S9-B report
     (fixes `pb_me_portal` test_01).
  If Step 6 is already on `origin/19.1` its tiles are there too — keep all of them.
- Version raises per the three reports.
Seams (merged tree):
c. Employee home: hooks of all three (and Step 5/6 modules if merged) stack, each calls
   `super()`; "Needs you" rows of review, survey and HR letter appear together; the
   conduct row stays neutral (never "warning"/"disciplinary").
d. Privacy matrix re-run on the MERGED tree, as each role (payroll officer, payroll
   manager, general HR, lifecycle user, un-named administrator, line manager, another
   employee, the employee): conduct case/notes/files/letters/document copies — nothing;
   finished review PDF/answers/comments — only employee, manager, review HR; survey
   answers — no path to a person; people reports — HR only, payroll refused.
e. Documents: a conduct letter copy and a review PDF filed on the same employee — each
   stays under its own rule; other documents unchanged for payroll.
f. Small groups: people reports and survey results hide <5 incl. Excel and subtraction
   across company/department/team.
g. Goals → pay review: a goal year without a form reads exactly as today (golden).
h. PDFs the builders could not print locally: finished review PDF, conduct letter —
   render on the rize rehearsal copy.
Combined local run on `wdgap_s9m_t`; failure set = union of recorded baselines.

## 2. Rehearsal — short

Backups ×5 — **and confirm the nightly backups include each database's file folder
(filestore)**: `pb_voice` keeps answers of an OPEN survey sealed there; report yes/no
and where. Practice install on a `rize` copy (jobs + mail off; `dropdb --force` after):
installs cleanly, nothing created, nothing queued, existing document access for payroll
unchanged except the new closed kinds; no payslip recompute needed (no pay touched) —
do the one-run old-vs-new comparison only if a pay-reading module's files changed.

## 3–5. Live checks, go live, checks on payobook.com

`-u` edited modules, `-i` the four new ones ×5. Look-only on payobook.com: Settings ›
HR › Review forms opens empty; Talent › Conduct tab visible only to named people
(nobody named → nobody sees it; do not name anyone); People › Insights → People reports
opens for HR with small groups "Hidden"; Talent › Voice opens, library offered, no
survey started; My Payobook as a demo employee shows "My review" and no conduct row;
one existing demo payslip PDF and one existing employee document still open. Cheap
open-the-screen checks on the other four sites.

## 6. Report — `WDGAP_S9_DEPLOY_REPORT.md` (commit + push to 19.1)

As S5/S8. Carry forward the open owner questions from S9-B (hidden figures in small
companies; no monthly headcount line; country notes for VN/ID; second sign-off and
appeal step; administrators out until named) in plain words. Final message under 300
words, plain English, screen words only. Usage-limit error mid-deploy: finish the
database you are on, START the service, DONE/FAILED in the deploy notes, PAUSED at the
top of the report.
