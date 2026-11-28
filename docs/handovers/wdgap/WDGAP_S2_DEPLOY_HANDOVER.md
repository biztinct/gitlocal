# WDGAP Step 2 go-live — merge, go live ×5, verify (S2-A, S2-C, S2-D, S2-B1, S2-B2)

Method: EXACTLY as `WDGAP_W3_DEPLOY_HANDOVER.md` and `WDGAP_IDB1_DEPLOY_HANDOVER.md`
(main checkout, same directory) and the chain they name; proven command sequence in
`WDGAP_W3_DEPLOY_REPORT.md` / `WDGAP_IDB1_DEPLOY_REPORT.md` / `WDGAP_IDB1F_REPORT.md`
on `origin/19.1`. Read those, `WDGAP_WAVE_RULES.md`, `WDGAP_S2_HANDOVER.md` (incl. the
WAVE 2 block + file ownership), `WDGAP_S2_FACTS.md`,
`WDGAP_OWNER_RULINGS_2026-11-15.md` (G1–G4, TD1–TD3, BL1–BL4, FG1, YE1–YE3), and the
five phase reports — their deploy notes, merge-time tasks and Follow-up sections are
binding: `WDGAP_S2A_REPORT.md` (`origin/wdgap-s2a`), `WDGAP_S2C_REPORT.md`
(`origin/wdgap-s2c`), `WDGAP_S2D_REPORT.md` (`origin/wdgap-s2d`),
`WDGAP_S2B1_REPORT.md` (`origin/wdgap-s2b1`), `WDGAP_S2B2_REPORT.md`
(`origin/wdgap-s2b2`). The ledger to keep is the one on `wdgap-s2a` plus each
branch's added rows.

All non-negotiables of the W3 deploy handover apply unchanged: databases `payobook`,
`payobook_template`, `p0clone`, `rize`, `sudima` ONLY (never `abm`, `pbf_preview`,
`recruit_connect_20261023`); ONE addons dir `/odoo/odoo-server/addons` on ssh alias
`Payobook19v2`; clean staging; per-module scoped `rsync -a --delete` (NEVER into the
addons root); never deploy vendored standard addons; `git archive` from the pushed
commit; backups ×5 first; hashes + `latest_version` ×5; asset purge +
`web.assets.version` bump; `/opt/deploy-notes.md` START/DONE; never over another
deployer's open START ("Codex", "Claude WORKFLOW-2"); compare server manifest versions
before every rsync and NEVER roll a module back (Codex's 2026-11-16 release is live but
not on `origin/19.1` — if a module you must ship is newer on the server, stop and
report); before stopping the service: no real signed-in activity on rize/payobook in
the last 15 minutes (re-check every 10 minutes, up to 90, then hold and report); never
leave the service stopped; white-label: the word "Odoo" never in anything an end user
can see (UI, files, file names, PDF text + metadata); no credentials or test passwords
anywhere; never print real account or tax numbers (last 4 only); never commit
`outputs/`, `SUDIMA/`, `RIZE/`; explicit-path staging, no `git stash`, no force-push;
never `pb_lifecycle/` or `pb_pack_*`; tenant email off on purpose on
rize/sudima/p0clone (do not raise or fix); demo data add-only; trailer
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; bounded polls in one
command, never end a turn on "waiting". RISKY tier (reads pay figures, bank files,
approval gates, employee-visible tax documents, access change on Filings).

## 0. Before anything

`git fetch`; confirm each of the five branches carries its Follow-up section(s)
(S2-A "Follow-up FG1"; S2-C "Follow-up BL1" + "Follow-up BL4"; S2-D "Follow-up TD1–TD3" + "Follow-up
ESI"; S2-B1 "Follow-up YE1–YE3"; S2-B2 "Follow-up"). If one is missing, STOP and say
which — do not merge a branch whose builder is still working.

## 1. Merge (branch `wdgap-s2-merge` from `origin/19.1`; order: s2a, s2b1, s2b2, s2c, s2d)

Merge-time tasks (apply every one the reports list; list file/lines in your report):
a. `pb_hub` palette Filings gate constant → the FG1 three-group list (S2-A task 1 as
   rewritten by its FG1 follow-up).
b. `pb_form_lines`: manifest data list + `models/__init__.py` (union of both wave-2
   branches), ONE version raise (19.0.1.1.0); any shared-file diffs S2-B2 listed.
c. Identity/field probes: put `pb_me_tax`'s real field names (table in the S2-D
   report: PTKP status, India PAN/regime/PF/ESI, Singapore fields) into the monthly
   reader's `_pb_identity_id`, S2-B1's `_pb_identity_in/_sg`, and S2-B2's member-number
   probe lists. Test: with `pb_me_tax` installed and a number on file, the person is IN
   each file; without it, left out with the reason.
d. `pb_me_portal`: ONLY the pinned "Me" tile-list test line(s) that S2-D and S2-B1
   name (Tax details, Tax certificates) — exact change from their reports; no other
   edit to that module.
e. Gate agreement (FG1): Tax returns, Year-end, Fund files, Form lines, prepare,
   download all use the shared gate — payroll officer/manager OR "Government reports"
   holders; "Accepted by the authority" and "Release to employees" payroll manager
   only. No restated group list left behind (grep).
f. Optional link: Tax details page (pb_me_tax) → "Tax certificates" (pb_me_tax_cert)
   only if both reports offer a hook for it; else skip and note.
Seams on the merged tree (all must hold; combined run on `wdgap_s2m_t`, failure set =
union of recorded baselines; drop your databases after):
1. Vietnamese bank file and "Payment list (any bank)" byte-identical (golden); a bank
   layout file is refused before approval, leaves out other-name accounts (BL1), keeps
   close names flagged (BL3); BL4 company setting default = left out, "Pay by file"
   = in + flagged + counted; the employee "in another person's name" notice shows to
   HR only, "Mark as seen" hides it and records who/when; install writes no employee
   row.
2. Vietnam social-insurance reports byte-identical while nothing is mapped.
3. Silent install on a database copy: nothing mapped, filed, released, asked or
   mailed; no new scheduled job; nothing new in the Approvals inbox; no home-page
   reminder for a person whose tax number is on file.
4. Three payslips recomputed identical; no payslip, contract, employee or bank row
   changed by install/upgrade (counts + checksums) — TD3 writes a contract only on an
   HR approval.
5. Access matrix as each role (payroll officer, payroll manager, "Government reports"
   holder only, HR without payroll, line manager, the employee, another employee,
   portal): Filings family per (e); a certificate only to its own employee after
   release; tax-detail requests and proofs HR only; screen AND direct URL.
6. End to end on the local copy: map lines → prepare an Indonesian monthly return →
   approve → download; a year-end filing → release → the employee downloads own
   certificate → take back → gone; YE1 ticked person gets none.
7. vi/id PO gate; grep: no "Odoo" in any user-visible string, file made, file name or
   PDF metadata.

## 2. Rehearsal on a `rize` copy (jobs + mail off first; `dropdb --force` after)

Upgrade/install clean; seam 3 and 4 on real data (old-vs-new recompute of one recent
rize run identical line for line — report honestly if no Vietnam payslip can be
recomputed, as in wave 3); the two WAITING bank-copy batches on the copy untouched.
On the copy only, read-only against real pay: make a mapping with Suggest for rize's
Indonesian scheme and one other country that has finished payslips, run the monthly
return's check step for one recent month, and compare totals with the payslips by
hand — report counts and totals only (people, totals per currency, how many left out
by reason, how many identity numbers missing), never names or numbers; delete every
file made. Count per LIVE database, read-only: who gains the Filings lens under FG1
(nobody should lose it); people with no tax number who will see the TD1 reminder; and
how each customer scheme names the registered-dependants figure (S2-D's deploy check).
Write any lists to `/Users/adity/Documents/GitHub/gitlocal/outputs/wdgap-s2-golive-2026-11-18/`
(never committed). Any payslip difference or a seam failure → do NOT go live; report.

## 3. Go live

As W3/IDB1. `-i` the new modules the reports name (`pb_form_lines`, `pb_me_tax`,
`pb_me_tax_cert`, any other) and `-u` the edited ones ×5, in dependency order. After:
silent-install proof ×5 (seam 3 queries); cron counts equal the snapshot (payobook job
156 and the template jobs stay OFF — re-switch off anything the upgrade turned on);
waiting bank-copy batches on rize (59) and sudima (358) still waiting with the same
counts unless a customer approver has acted — report what you see, never approve or
refuse.

## 4. Checks on payobook.com (QA login path as in the W3 report; undo what you try)

Compliance › Filings shows Tax returns / Year-end / Fund files for the demo company's
country and the Form lines door; Form lines → Suggest shows proposals (do not save
unless cleanly reversible — if you save a demo mapping, keep it: demo data is
add-only, name nothing "RIZE"); Pay & deliver → Payment list shows the "Bank layout"
choice and the left-out summary; Settings › Payroll › Bank layouts opens with the
"check with your bank" note; My Payobook shows "Tax details" (numbers masked) and
"Tax certificates" (empty state); one existing bank file and one demo payslip PDF
still open; console clean. Cheap open-the-screen checks on the other four sites.

## 5. Report — `WDGAP_S2_DEPLOY_REPORT.md` (commit + push to 19.1)

As W3. Include the INFERRED list gathered from the five reports in one table (form /
layout, what is not confirmed, what would confirm it). Final message under 300 words,
plain simple English, screen words only, no code names: live or held, downtime,
checks, rehearsal counts, anything held, owner questions as real-world questions.
Usage-limit error mid-deploy: finish the database you are on, START the service,
DONE/FAILED in the deploy notes, PAUSED at the top of the report.
