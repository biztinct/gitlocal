# WDGAP IDB1 go-live — merge, go live ×5, verify (general bank payment list)

Method: EXACTLY as `WDGAP_W3_DEPLOY_HANDOVER.md` (main checkout, same directory) and
the chain it names; proven command sequence in `WDGAP_W3_DEPLOY_REPORT.md` on
`origin/19.1`. Read those, `WDGAP_LEDGER.md`, `WDGAP_WAVE_RULES.md`,
`WDGAP_IDB1_HANDOVER.md`, `WDGAP_OWNER_RULINGS_2026-11-15.md` (IDB1–IDB3, BG1–BG4),
and `WDGAP_IDB1_REPORT.md` on `origin/wdgap-idb1` (deploy notes + "Follow-up IDB2" are
binding). All non-negotiables of the W3 deploy handover apply unchanged (five databases
only — `payobook`, `payobook_template`, `p0clone`, `rize`, `sudima`; never `abm`,
`pbf_preview`, `recruit_connect_20261023`; ONE addons dir; scoped rsync, never
`--delete` into the addons root; `git archive` from the pushed commit; backups ×5
first; hashes + `latest_version` ×5; asset purge + `web.assets.version` bump; deploy
notes START/DONE; never over another deployer's open START; never roll back a module
that is newer on the server — Codex has live modules not on `origin/19.1`; activity
check on rize/payobook before stopping the service; never leave it stopped;
white-label "Odoo" rule; no credentials; explicit-path staging; no stash; no
force-push; never `pb_lifecycle/`, `pb_pack_*`, `pb_me_portal`; tenant email off on
purpose; demo data add-only; trailer
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; bounded polls in one
command, never end a turn on "waiting"). RISKY tier (bank account data, pay amounts,
approval gate).

## Differences

1. Merge `wdgap-idb1` into `wdgap-idb1-merge` from `origin/19.1`; combined local run
   on `wdgap_idb1m_t` (IDB1 tests + suites of touched modules = baseline). Seams on
   the merged tree: the Vietnamese bank file byte-identical; its existing approval
   untouched; the payment list refused before its own approval (screen + direct URL)
   and for anyone who cannot download the bank file; nothing in the Approvals inbox
   after upgrade; a bank change waiting for approval (BK2 / the BG1 batches) is never
   used by the list.
2. Rehearsal on a `rize` copy (jobs + mail off; `dropdb --force` after): upgrade
   clean; old-vs-new recompute of one recent rize run identical; no bank, contract or
   payslip row changed; the two WAITING bank-copy batches on the copy untouched. On
   the copy only: produce the payment list for one recent rize run that has Indonesian
   staff, through the approval; report counts only (people, per-currency totals, how
   many "need a check" by reason) — never print account numbers; delete the file.
3. Live: `-u` the modules the report names ×5. After: the waiting bank-copy batches
   on live rize (59) and sudima (358) still waiting with the same counts unless a
   customer approver has acted — report what you see, never approve or refuse; cron
   states equal the snapshot.
4. payobook.com look-only (QA login path as in the W3 report): Pay & deliver on a
   demo run shows "Payment list (any bank)" with the summary and the download
   disabled with its reason; send for approval and approve ONLY if the demo setup
   allows it with demo logins and it is cleanly reversible, else look only; one
   existing bank file and one demo payslip PDF still open. Cheap open-the-screen
   checks on the other four sites.
5. Report `WDGAP_IDB1_DEPLOY_REPORT.md` (commit + push to 19.1). Final message under
   250 words, plain English, screen words only: live or held, downtime, checks,
   rehearsal counts, anything held, owner questions as real-world questions.
