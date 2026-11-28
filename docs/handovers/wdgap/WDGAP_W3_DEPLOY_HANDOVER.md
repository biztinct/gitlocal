# WDGAP wave 3 go-live — merge, go live ×5, verify (W3-A, W3-B, W3-C code)

Method: EXACTLY as `WDGAP_S5_DEPLOY_HANDOVER.md`, `WDGAP_S8_DEPLOY_HANDOVER.md`,
`WDGAP_S6_DEPLOY_HANDOVER.md`, `WDGAP_S9_DEPLOY_HANDOVER.md` (main checkout, same
directory) and the chain they name; the proven command sequence is in
`WDGAP_S6_DEPLOY_REPORT.md` / `WDGAP_S9_DEPLOY_REPORT.md` on `origin/19.1`. Read those,
`WDGAP_LEDGER.md`, `WDGAP_WAVE_RULES.md`, `WDGAP_OWNER_RULINGS_2026-11-15.md` (the
"Rulings 2026-11-17" blocks: PR1, PR2, CD1, CD4–CD6, IM2, PRV1, PRV2, RN1–RN3, BG1),
and the three phase reports on their branches — deploy notes and follow-up sections are
binding: `WDGAP_W3A_REPORT.md` (`origin/wdgap-w3a`; `pb_people_reports`, `pb_conduct`),
`WDGAP_W3B_REPORT.md` (`origin/wdgap-w3b`; pay review waits, renewal kind + "Follow-up
RN3" payroll treatment, Renew link + read-only check), `WDGAP_W3C_REPORT.md`
(`origin/wdgap-w3c`; IM2 internal-move papers; BG1 bank-copy batches are DATA already
created on live rize/sudima by the builder — not part of this deploy).

All non-negotiables of the S5 deploy handover apply unchanged: databases `payobook`,
`payobook_template`, `p0clone`, `rize`, `sudima` ONLY (never `abm`, `pbf_preview`,
`recruit_connect_20261023`); ONE addons dir `/odoo/odoo-server/addons` on ssh alias
`Payobook19v2`; clean staging; per-module scoped `rsync -a --delete` (NEVER into the
addons root); never deploy vendored standard addons; `git archive` from the pushed
commit; backups ×5 first; hashes + `latest_version` ×5; asset purge +
`web.assets.version` bump; `/opt/deploy-notes.md` START/DONE; never over another
deployer's open START ("Codex", "Claude WORKFLOW-2" also deploy; Codex's 2026-11-16
release — `pb_people`, `pb_employee_vault`, `pb_scheme_map` + one more — is live but
NOT on `origin/19.1`: compare server manifest versions before every rsync and NEVER
roll a module back; if a module you must ship is newer on the server, stop and report);
never leave the service stopped; white-label: the word "Odoo" never in anything an end
user can see; no credentials or test passwords anywhere; never commit `outputs/`,
`SUDIMA/`, `RIZE/`; explicit-path staging, no `git stash`, no force-push; never
`pb_lifecycle/` or `pb_pack_*`; `pb_me_portal` untouched; tenant email off on purpose
on rize/sudima/p0clone (do not raise or fix); demo data add-only; trailer
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; bounded polls only, never
wait silently. RISKY tier (pay review writes wages on a date; renewals feed the Vietnam
pay formula; conduct security rules).

## 1. Merge (branch `wdgap-w3-merge` from `origin/19.1`; order: w3a, w3b, w3c)

- Merge-time fix left by W3-A: the one Step 9 test in `pb_review_forms` that pinned the
  old "Hidden" behaviour — apply the exact change written in the W3-A report; list
  file/lines.
- Version raises per the three reports.
Seams (merged tree):
a. Pay review (W3-B) + "Raise the scale" (S8-D) share the hourly job that writes dated
   rises: both written on their day, once; running the job twice writes nothing more;
   a person with newer pay is left out and listed (PRV2).
b. Pay review with a start date in a paid month → "Re-work those months" opens a draft
   Past-month re-work (`pb_retro`); no back pay created automatically.
c. Renewal (both paths) copies VN contract kind and payroll treatment Permanent only;
   Probation/trial never copied; allowances still carried (S8-D); "Make it permanent"
   still works; new contract links to the old one.
d. IM2: internal hire → no "before you join" papers asked, no emails; outside
   candidate unchanged.
e. Privacy matrix re-run on the MERGED tree as each role (payroll officer, payroll
   manager, general HR, HR manager, lifecycle user, un-named administrator, line
   manager, another employee, the employee, first named person, second named person,
   named person who is the subject): conduct exactly as the W3-A report table; the
   second-sign-off reminder never appears in the general Approvals inbox; people
   reports HR only with nothing hidden; survey results STILL hide groups under 5 incl.
   Excel.
Combined local run on `wdgap_w3m_t`; failure set = union of recorded baselines; drop
your test databases after (touch nobody else's).

## 2. Rehearsal on a `rize` copy (jobs + mail off first; `dropdb --force` after)

Upgrade cleanly; old-vs-new recompute of one recent rize run — identical line for line;
no contract, wage, pay line, payslip or bank row changed by the upgrade (counts +
checksums); existing applied pay reviews untouched; nothing queued to send. Run W3-B's
read-only unlinked-renewals check on all five live databases; write lists to
`/Users/adity/Documents/GitHub/gitlocal/outputs/wdgap-w3-renewal-links-2026-11-17/`
(never committed); report counts only. Any payslip difference → do NOT go live; report.

## 3. Read-only live checks, 4. Go live

As S6. Before stopping the service: no open START; request log shows no real signed-in
activity on rize/payobook in the last 15 minutes (else re-check every 10 minutes, up to
90 minutes, then hold and report). `-u` the edited modules ×5 (no new modules expected;
if a report names one, `-i` it). After: cron counts equal the snapshot (payobook job
156 and the template jobs stay OFF — re-switch off anything the upgrade turned on);
NO bank-copy batch exists on rize or sudima yet (the builder creates them after your
DONE line — you never create or approve one); Compliance › Bank shows nothing waiting
×5 before and after. `wdgap-w3c` also carries "Follow-up: one notice per batch" (one
to-do + at most one email per approver per bank batch) — follow its deploy notes and
add to seam (e): a held batch of N bank changes → 1 to-do per approver, closed when
the batch is decided; a single bank change behaves as before; rulings BG2–BG4.

## 5. Checks on payobook.com (QA login path as in the S6 report; look-only; undo
anything you try)

People › Insights → People reports: no "Hidden" anywhere, month-by-month line and
"Last 12 months" present, Excel downloads; Talent › Conduct still visible only to
named people (name nobody); Pay Review: a demo review with a future start date shows
"Applies on <date>" after Apply and no contract wage changed — then "Take it back";
Contracts → Renew on a demo fixed-term contract shows kind and payroll treatment
ready-filled (cancel); one existing demo payslip PDF opens. Cheap open-the-screen
checks on the other four sites.

## 6. Report — `WDGAP_W3_DEPLOY_REPORT.md` (commit + push to 19.1)

As S6. Final message under 300 words, plain English, screen words only, no code names.
Usage-limit error mid-deploy: finish the database you are on, START the service,
DONE/FAILED in the deploy notes, PAUSED at the top of the report.
