# WDGAP Step 6 go-live — merge, go live ×5, verify (S6-A, S6-B, S6-C + follow-ups)

Method: EXACTLY as `WDGAP_S5_DEPLOY_HANDOVER.md` and `WDGAP_S8_DEPLOY_HANDOVER.md` (main
checkout, same directory) and the chain they name; the proven command sequence is in
`WDGAP_S5_DEPLOY_REPORT.md` / `WDGAP_S8_DEPLOY_REPORT.md` on `origin/19.1`. Read those,
`WDGAP_LEDGER.md`, `WDGAP_WAVE_RULES.md`, `WDGAP_S6_HANDOVER.md` ("Step go-live note"),
`WDGAP_S6_FACTS.md` (§8 "unavoidable shared surfaces", §9),
`WDGAP_OWNER_RULINGS_2026-11-15.md` (E1–E6, C-1..C-4 and the 2026-11-16 rulings BK1,
BK2, CT1, PV1, ME1, EC1–EC3, TA1, PA1, IM1), and the three phase reports on their
branches — each has deploy notes and follow-up sections you must follow:
`WDGAP_S6A_REPORT.md` (`origin/wdgap-s6a`; NEW `pb_me_details`, `pb_me_letters`,
`pb_me_privacy`; edits `pb_bank_ocr`, `pb_records`; follow-ups BK1, BK2),
`WDGAP_S6B_REPORT.md` (`origin/wdgap-s6b`; NEW `pb_hiring_internal`, `pb_me_payai`;
follow-ups PA1, IM1), `WDGAP_S6C_REPORT.md` (`origin/wdgap-s6c`; NEW
`pb_expense_payroll`, `pb_trip_advance`, `pb_expense_allowance`; follow-up TA1). All
non-negotiables of the S5 deploy handover apply unchanged (five databases only; never
abm; ONE addons dir; scoped rsync; `git archive` from the pushed commit; backups first;
deploy notes START/DONE; never over another deployer's open START — "Codex" and "Claude
WORKFLOW-2" also deploy and Codex shipped `pb_people`/`pb_employee_vault`/`pb_scheme_map`
on 2026-11-16: never roll a module back, compare server versions before rsync; never
leave the service stopped; white-label "Odoo" rule; no credentials; explicit-path
staging; no force-push; never `pb_lifecycle/` or `pb_pack_*`; commit trailer
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`). RISKY tier (bank details,
pay lines, AI, new security rules; eight new modules). Only differences are below.

## 0. Order

Step 8 must be LIVE first (WDGAP S8 DONE line in `/opt/deploy-notes.md` and its merge
on `origin/19.1`). If it is not, do merge + local testing now and poll (bounded) before
pushing or touching the server. A follow-up go-live "S5-F" may also be queued — only
one go-live at a time; whoever has the open START goes first.

## 1. Merge (branch `wdgap-s6-merge` from `origin/19.1`; order: s6a, s6c, s6b)

Version raises per the three reports. Merge-time tasks the builders left for you (the
only edits you make outside merging; keep each minimal, test it, list file/lines):
a. ME1 — "My details" and "Certificates" tiles move from "More" to "Me" on My Payobook
   (the S6-A report names the `pb_me_portal` test that pins the tile list; this is the
   ONE sanctioned `pb_me_portal` edit: the tile row + its test).
b. BK2 gap — the Run-payroll wizard's result screen shows "N bank changes are waiting
   for approval" after a pay data file load (S6-A report "Follow-up BK2" names the spot).
Seams (merged tree):
c. FACTS §8 "unavoidable shared surfaces" — every row; employee home hooks of all S6
   modules stack (each calls `super()`), with Step 5's late-minutes page if present.
d. C-1: S6-B internal hire → opens S8-B Change job prefilled (real model now on 19.1),
   no second employee record; IM1: no "before you join" emails for the internal hire.
e. C-2: a role under S8-C "Pause hiring" is hidden from internal roles.
f. One payslip carrying a claim line (S6-C), a trip-advance recovery, a back-pay line
   (W2-D2) and Step 5 time inputs: computes once, recompute never doubles, totals read
   correctly; with none of them → byte-identical (golden).
g. Bank: approved change from each path (My Payobook, bank-document check, Updates
   sheet, HR bank screen, pay data file import, old Vietnam import, connected-system
   refresh) lands in BOTH stores only on approval; approver ≠ requester.
h. Approvals inbox shows the new process keys (bank, certificates, trip advance
   settlement …) seeded once per company; nothing waiting after install.
i. PayAI: off by default ×5 after install; with no AI account configured HR sees "not
   set up yet", employees see nothing; no outside call is made by install or tests.
j. PDFs the builders could not print locally: employment certificate, salary
   certificate — render on the rize rehearsal copy (wkhtmltopdf is on the server).
Combined local run on `wdgap_s6m_t`; failure set = union of recorded baselines.

## 2. Rehearsal — short

Backups ×5. Practice install/upgrade on a `rize` copy (jobs + mail off first;
`dropdb --force` after): old-vs-new recompute of one recent rize run — identical line
for line; no bank store, family, contract or payslip row changed by install (counts +
checksums of the bank fields before/after); nothing queued to send.

## 3. Read-only live checks BEFORE go-live — includes an OWNER GATE

As S5/S8, plus:
- **Bank-store check (S6-A's read-only method) on all five databases**: list of
  employees whose two bank records disagree. Write the result to a file OUTSIDE the
  repo (`/Users/adity/Documents/GitHub/gitlocal/outputs/wdgap-s6-bank-check-<date>/`,
  never committed; one small CSV per database: employee, company, record A, record B —
  mask account numbers to the last 4 digits in anything you print to me).
- Report the COUNTS per database in your message. **If rize or sudima has ANY
  disagreement, do everything else up to but not including the go-live, then HOLD and
  report: the owner must see the list first** (nothing is rewritten by the go-live, but
  the owner asked to see it before). If only demo databases disagree, proceed and
  report the counts.
- Nightly backups include each database's file folder (filestore)? Report yes/no.

## 4. Go live, 5. Checks on payobook.com (QA login path as in the S5 report; demo data
add-only; look-only where it would email a real person)

`-u` edited modules, `-i` the eight new ones ×5. Then: My Payobook as a demo employee —
"My details" and "Certificates" under "Me"; an employment certificate downloads as a
PDF (demo person); privacy notice: nobody asked (no notice published); internal roles
page opens (empty or demo); HR: People › Family tab, People › Privacy board, Compliance
› Bank shows nothing waiting; Home › Policies opens, PayAI for employees OFF; company
setting "Approved claims are paid" = by finance ×5; one existing demo payslip PDF still
opens. Cheap open-the-screen checks on the other four sites.

## 6. Report — `WDGAP_S6_DEPLOY_REPORT.md` (commit + push to 19.1)

As S5/S8, plus the bank-check counts and where the lists are. Carry forward open owner
questions in plain words. Final message under 300 words, plain English, screen words
only. Usage-limit error mid-deploy: finish the database you are on, START the service,
DONE/FAILED in the deploy notes, PAUSED at the top of the report.
