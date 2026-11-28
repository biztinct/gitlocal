# NEWHIRE P6 — checklist + equipment names in vi/id, then the studio on the other four sites

Owner rulings 2026-11-25 (evening): (1) switch the new Add employee screen on for rize, sudima, p0clone and
payobook_template NOW; (2) translate the joining checklist's step names and the equipment names into Vietnamese and
Indonesian (lessons stay en + vi); (3) leave the payobook demo data as it is.

Read first: `NEWHIRE_LEDGER.md`, `NEWHIRE_P5A_REPORT.md` §1.1, §3, §7 (where the English leftovers come from),
`NEWHIRE_P5B_REPORT.md` (the release you repeat — scripts in the repo from commit c502339ae are reusable),
`NEWHIRE_P5B_DEPLOY_HANDOVER.md` (every rail there binds this phase too), `NEWHIRE_FACTS_ONBOARD.md` §F, §H, §M.

## Part 1 — translations (build + test locally, in a fresh worktree from origin/19.1)
- Find every record a Vietnamese/Indonesian user reads in English on studio step 6, the joining checklist, the New
  joiners board and equipment requests: checklist template + step names/descriptions (`pb_lifecycle` / `pb_onboarding`
  seeded data), equipment type/category names (`pb_assets`). List them in the report with their module and xmlid.
- Add `vi_VN.po` / `id_ID.po` entries in the OWNING module (PO loading rules; parse gate; reuse the product's existing
  terms). LOOK rule — a translation fix is TWO fixes: the `.po` AND the values already stored: fields must be
  translatable; data is `noupdate` on live, so ship a migration (or post-init/upgrade hook) that writes the vi/id
  translations onto EXISTING seeded records **only where the stored English still equals the shipped English** (a
  tenant's renamed step is never overwritten), and never touches tenant-created rows. Idempotent.
- Making a field translatable changes its storage: check the column conversion is safe on a copy with real volume
  (rehearsal), and that no SQL/JS in the repo reads the column raw.
- Tests: vi and id readers see translated names; renamed step untouched; second run changes nothing; en unchanged.
  Bump each touched module's version. Walk locally in vi and id (step 6, checklist, New joiners, equipment).
- White-label: no "Odoo" in any msgid/msgstr. No client data in the repo.

## Part 2 — release (ONE window)
- Merge to 19.1, push; stage from `git archive` of the pushed commit.
- `-u` the translated modules on ALL FIVE; `-i pb_new_hire` on **rize, sudima, p0clone, payobook_template** (it is
  already on payobook — `-u` there only if its version changed). Order: payobook_template → p0clone → sudima → rize →
  payobook.
- Full risky-tier ritual exactly as P5b: deploy notes (wait on any open START/HOLD — another session was retrying a
  payroll/PDF release this evening), flock, quiet check, job-count snapshot, backups ×5 twice, rehearsals on hidden
  copies of **rize AND sudima** (jobs + mail servers off at once; `dropdb --force` after), rollback plan written before
  the stop. Any rehearsal error → stop, deploy nothing, report.
- Tenant specifics: outgoing mail is off on rize/sudima/p0clone on purpose — not a fault; confirm the studio then
  offers "Copy the welcome link" and sends nothing. rize and sudima are client sites: **create nothing on them** — no
  test hire. Look only. payobook_template: any job an install/upgrade switches on goes off again unless it must run for
  new tenants (then add it to `pb_tenants.template_active_crons` and say so). Seat limits / approval routes on tenants
  are theirs — do not change.
- Never touch `abm` or `_test_sudima_policy_20261119`.

## Verify
Hashes, versions ×5, job counts, log 0 ERROR, five sites 200. Browser on the hidden copies (as P5b) + server-side on
live: on rize and sudima Add employee opens the seven-step screen; teams resolve to their pay schemes and currencies
(rize: an Indonesian and a Vietnamese team); the payslip example renders for one team per country (it leaves no trace —
prove counts before/after on live); step 5 shows the country's papers; From Hiring tile; a Vietnamese and an Indonesian
user read the checklist steps and equipment names in their language; contract letter PDF still produced on payobook
after the other session's PDF change (one letter for the existing DEMO person). Update `docs/deploy/PENDING.md` (remove
the waiting row) and `NEWHIRE_CLOSEOUT.md` §1–§2.

## Report back — `NEWHIRE_P6_REPORT.md`, committed + pushed on 19.1
Final message: short plain summary — live or not per site, downtime, what was seen, anything failed/left behind.
