# NEWHIRE P5b — merge to 19.1 and go live (report)

Release engineer, 25 Nov 2026 (UTC). Handover `NEWHIRE_P5B_DEPLOY_HANDOVER.md`. Engineering receipt: real technical
names on purpose. No credentials, client names or client data in this file.

**Result: GO. Merged and pushed to `19.1` (`a2a44544c`, the deployed commit), LIVE on all five databases, 515 s of
downtime (07:58:06–08:06:41 UTC).** `pb_new_hire` 19.0.1.5.0 is installed on **payobook only** (D10); `pb_learn`
19.0.20.9.0 and `pb_people` 19.0.1.3.6 are upgraded on all five; the Python-only factor-outs in
`pb_hr_payroll_formula`, `pb_probation`, `pb_scheme_map` run everywhere since the restart. Every database exit 0,
0 ERROR. Nothing failed, nothing restored. abm and `_test_sudima_policy_20261119` untouched.

## 1. Timeline (UTC, 25 Nov 2026)

| Time | Step |
|---|---|
| 07:06 | `/opt/deploy-notes.md` read: every START closed (last WFSETUP P10b data DONE 05:59, storage NOTE 06:00); no lock file |
| ~07:08 | Scope 1 fix committed `ddb704299` (step 2 rail line names only what is missing) + static gate S6; 8/8 static + catalogue tests |
| ~07:09 | `git merge origin/19.1` into `newhire` → `9c202a8b2`. Upstream moved by docs only since the P5a merge (2 commits, 4 doc files) |
| 07:09–07:18 | `pb_new_hire` full suite on the merged code (`nh8_m`): **131 / 131**, 0 failed, 0 errors (P5a 130 + S6) |
| ~07:18 | Deploy scripts `c502339ae` (`docs/handovers/newhire/p5b/`, clones of wfsetup p5b/p10b); fresh worktree from `origin/19.1` (`17df93241`), `git merge --no-ff newhire` → `a2a44544c`; tree = `newhire` byte for byte; secret scan (only made-up fixture passwords in tests); pushed `17df93241..a2a44544c` |
| 07:19–07:23 | Prep (`nh_prep.sh`): staged = commit; server copies of the five shared modules = `origin/19.1` (hashes identical, none newer); PO gate; 128-module dependency closure installed on all five; dumps ×5 read back; file-folder hard links; counts + job snapshots |
| 07:23–07:37 | Rehearsals on hidden template copies `nh_rh_payobook`, `nh_rh_rize` (§3) — passed |
| 07:37–07:49 | `pb_new_hire` suite on the payobook copy (real data) + environment re-run (§3.2) — green |
| ~07:40–07:46 | rize copy browser walk (old window, wages per currency); copy dropped 07:46:20 |
| ~07:50–07:55 | payobook copy browser walk (L1–L4, L8, L9) |
| 07:55 | START line; quiet since 07:40:36 on rize/payobook/sudima (first try); lock taken |
| 07:55–07:58 | Go-live dumps ×5 + counts; notes re-read (no HOLD, no open START) |
| 07:58:06 | Service stopped; per-module scoped rsync; addons = staged |
| 07:58–08:05 | Upgrades one database at a time (§4) |
| 08:06:41 | Service up; five sites warmed 200; DONE line 08:06; lock removed |
| 08:08–08:13 | Verification (§5), live L4 hire on payobook, L5/L10 server checks, L7 on the copy; NOTE line 08:13; payobook copy dropped 08:12:39 |

Backups `/odoo/backups/newhire-20261125T0719Z/` (prep dumps, go-live dumps, file-folder hard links,
`previous-trees.tgz`). Evidence `/tmp/newhire-p5b-20261125T0719Z/` on the server.

| Database | Prep dump | Go-live dump (right before the stop) |
|---|---|---|
| payobook | 84,399,581 B | 84,402,723 B |
| payobook_template | 32,029,575 B | 32,031,669 B |
| p0clone | 32,569,587 B | 32,572,083 B |
| rize | 45,048,545 B | 45,051,977 B |
| sudima | 36,218,892 B | 36,221,555 B |

## 2. What shipped (checked against `git diff origin/19.1...newhire`, not only the P5a table)

| Module | Version | Where | How |
|---|---|---|---|
| `pb_new_hire` | — → 19.0.1.5.0 | files ×5, installed on **payobook** | `-i` on payobook only |
| `pb_learn` | 19.0.20.8.10 → 19.0.20.9.0 | all five | `-u` |
| `pb_people` | 19.0.1.3.5 → 19.0.1.3.6 | all five | `-u` |
| `pb_hr_payroll_formula`, `pb_probation`, `pb_scheme_map` | unchanged (19.0.1.170.0, 19.0.1.6.0, 19.0.2.5.6) | all five | files + restart (methods only, no fields — checked in the diff) |

## 3. Rehearsals (hidden template copies; jobs, mail servers and incoming mail OFF first; staged code first in a separate addons path)

| Copy | Command | Result |
|---|---|---|
| `nh_rh_payobook` (4,582 people) | `-i pb_new_hire -u pb_learn,pb_people` | exit 0, **102 s**, 0 ERROR, 0 Traceback (1,232 WARNING lines = the usual framework noise: computed-field consistency, view accessibility hints, duplicate labels — same kinds as earlier deploys) |
| | data | identical except what the install must add: 6 new **empty** employee columns (`nh_*`; checksum of every other employee value = before, 0 people with a value in them), +1 mail template, +4 record rules, 14 paper rows |
| | jobs | upgrade cascade re-activated 6 (all off on the copy); no new job row |
| `nh_rh_rize` (313 people) | `-u pb_learn,pb_people` | exit 0, **75 s**, 0 ERROR; `pb_new_hire` stays uninstalled |
| | data | identical except +4 messages = change notes on 2 scheduled jobs and 2 server actions (technical records; earlier deploys showed the same) |
| | browser (tunnel, throwaway HR login made on the copy, dropped with it) | People › Employees › **Add employee opens the old three-step window** (Person / Role / Contract); closed without saving; Employees list shows each contract's own money (rupiah, rupee, dong and Singapore dollar rows; one monthly total per currency, never added together); console clean |

### 3.2 Suites on the payobook copy (real data)
`-u pb_new_hire,pb_people --test-tags /pb_new_hire,/pb_people:TestPeoplePaySymbol`: 133 tests, **125 passed**, 4
errors + 4 failures, all environmental — proven by a re-run with only the environment fixed
(`nh_rh_tests2.sh`): **15 / 15 passed** in the four classes involved.
- 4 errors (`test_d11`, `test_s2`, `test_t7`, `test_t8`): the static tests read sibling modules next to
  `pb_new_hire`; the staging dir holds only the six shipped trees (as WFSETUP WS36).
- 4 failures (`TestWelcomePage` v05, v05b, v06, v08b — the only tests that make web requests): the live conf's
  `dbfilter = ^%d$` finds no database for host 127.0.0.1, so the test server answered 404. Empty dbfilter → pass.

## 4. Go-live

Order payobook_template → p0clone → sudima → rize → payobook; staged = commit `a2a44544c`.

| Database | Command | Exit / time / ERROR | Versions after | Jobs active before → after |
|---|---|---|---|---|
| payobook_template | `-u pb_learn,pb_people` | 0 / 77 s / 0 | learn 19.0.20.9.0, people 19.0.1.3.6, new hire uninstalled | 40 → 40 (job 45 re-activated by the cascade, switched back off) |
| p0clone | same | 0 / 78 s / 0 | same | 49 → 49 |
| sudima | same | 0 / 74 s / 0 | same | 91 → 91 |
| rize | same | 0 / 79 s / 0 | same | 92 → 92 |
| payobook | `-i pb_new_hire -u pb_learn,pb_people` | 0 / 93 s / 0 | + pb_new_hire 19.0.1.5.0 | 59 → 59 |

Asset purge + `orm_signaling_assets` + `web.assets.version = newhire-p5b-20261125T0719Z` on each database.
**Downtime 515 s.**

## 5. Verification

| Check | Result |
|---|---|
| Trees | all 6 server trees = commit `a2a44544c` (hash of sorted file md5s, skipping `__pycache__`, `*.pyc`, `.DS_Store`) |
| Versions | manifest = `latest_version` (normalised) for all six modules on all five; `pb_new_hire` installed on **payobook** only; `tools/deploy_status.py`: "Nothing pending" ×5 |
| Jobs vs prep snapshot | identical ×5 (payobook 112/59, template 100/40, p0clone 100/49, rize 100/92, sudima 100/91); payobook job 156 off |
| Studio reminder job | **none exists**: `pb_new_hire` creates no scheduled job; its reminders ride on `pb_lifecycle`'s lifecycle reminders job, which is **off on payobook** (id 105, unchanged) — nothing to switch off |
| Data right before the stop vs after | payobook_template, p0clone, sudima identical; payobook = the 6 new empty employee columns (every other value identical, re-checked live), +1 mail template, +4 record rules, the module's rows; rize +4 technical change notes — exactly as rehearsed |
| Compiled code | payobook: studio + takeover + step 2 sentence + Learn replica in the bundle; other four: old window registered, no studio; Learn replica ×5 |
| Server log since the stop | 0 ERROR / CRITICAL, 0 Traceback, 0 asset errors; upgrade logs 0 ERROR; one service process |
| Sites | five × 200; payobook `/my/welcome` and the studio action answer (sign-in redirect when signed out) |
| Rehearsal copies | both dropped, file folders gone, rehearsal service stopped, throwaway logins gone with the copies |

## 6. L1–L10

**Where the browser checks ran.** The automation browser was signed in to payobook.com as the owner's own admin
account. Standing rule: never test as the owner; and this release engineer may not type the QA password into a public
site. So the browser walks ran on the **payobook rehearsal copy** (same code as live, a copy of live data taken
07:20, throwaway logins made on the copy) through a local tunnel, and the live side was proven with server checks
and one real send through the studio's own server call as the QA login. **Ask the owner for a two-minute look on
payobook.com** (People › Employees › Add employee).

| # | Check | Result |
|---|---|---|
| L1 | Add employee opens the seven-step screen | **pass** (copy): People › Employees › Add employee → the studio, "0 of 7 steps done"; live bundle carries the studio + takeover |
| L2 | steps 1–3, Indonesian and Vietnamese team | **partly**: payobook has **no Indonesian team** (all its pay schemes are Vietnamese; the Singapore company has no scheme). Vietnamese team (Retail / Stores - Central): scheme "Payobook Retail — End-Month Payroll", VND ₫, 2-month trial, Vietnamese letter, Citizen ID; payslip example ₫12,000,000 basic → ₫16,530,000 gross with the scheme's allowances and insurance. Same team with Country of work = Indonesia: IDR Rp, 3-month trial, Indonesian letter, KTP, and the mismatch warning "…a Vietnam scheme, but you chose Indonesia…" with a **Use Vietnam** fix. Step 2 rail line read "Team and job needed" while the country was filled (scope 1 fix) |
| L3 | steps 5 and 6 render | **pass** (copy): step 5 "Who fills in the rest?" (personal details, emergency contact, tax code…, Ask / I have it / Not needed); step 6 sign-in, checklist (11 steps), buddy, 10 equipment chips, letter |
| L4 | send one DEMO hire and approve it | **pass**, no approval needed: payobook's demo company has **no approval step for new hires** ("Nobody needs to approve new hires here"), so the person is added at once. Copy (browser): "DEMO NH Rehearsal Indo is added", reference NEW00098. **Live (server call as the QA login): "DEMO NH P5b Live Check"** — employee in Stores - Central / Sales Associate, Vietnam, trial end 1 Feb 2027; running contract ₫12,000,000 in **VND**; joining checklist open (New joiners row); 7 asks; 1 equipment request; **contract letter PDF produced** (`application/pdf`, 34,008 B) — the PDF tool works on the server; no mail queued. Welcome page: route live; this hire has no sign-in (none chosen), so no link was sent |
| L5 | document reader configured? | **payobook: yes** (one active document-reader setting, used by all four companies through the lookup's fallback) → bank paper defaults to "came across / read". **payobook_template, p0clone, rize, sudima: no** (only a switched-off assistant setting) |
| L6 | Hiring › "Confirm they joined" opens the studio | **not testable on payobook**: no signed offer is waiting ("No signed offers are waiting" in step 1). Nothing seeded on live |
| L7 | Learn lesson "Add your first employee" plays | **pass** (copy): Employees and contracts › Try → practice company → "Step 1 of 6 · Find where new people start … a guided screen of seven steps"; console clean. Full 6-step walk was done locally in P5a (W4) |
| L8 | org chart "add a person here" | **pass** (copy): the org chart's exact door (`pb_onboard_wizard` with team + manager prefill) opens the studio; step 2 shows team Stores - Central, the manager, country suggested, job empty |
| L9 | Vietnamese user sees Vietnamese | **pass** (copy): studio fully Vietnamese ("Thêm nhân viên · Đã xong 0/7 bước · Ai sắp vào làm?…"). **vi_VN and id_ID are active on all five databases** |
| L10 | rize: old window; wage column per contract currency | **pass**: copy browser (old three-step window; Rp / ₹ / ₫ / S$ per row, totals kept apart); live server check: four separate totals (Rp, ₫, ₹, S$), each row carries its own contract's sign; live bundle: old window registered, no studio. Nothing created on rize |

## 7. Rollback plan (written before the stop; not needed)

| Failure | What happens |
|---|---|
| An upgrade/install exits non-zero, or a version check fails, inside the window | `nh_golive.sh` stops the sequence, removes the six shipped trees, untars `previous-trees.tgz` (pb_new_hire stays absent), drops and restores the failed database and every database already upgraded in this run from the go-live dumps, purges assets, starts the service. FAILED line in the deploy notes. Reported before anything else. |
| Service will not start after a clean run | Read the log first. Code-only cause: previous trees back (`tar -C /odoo/odoo-server/addons -xzf previous-trees.tgz`, `rm -rf pb_new_hire`), start. Restore a database only if the site stays down. |
| A problem found after go-live (site up) | Report first; decide per failure. Files from `previous-trees.tgz`; data from `golive-<db>.dump` ONLY if data changed and the owner agrees. payobook only: `pb_new_hire` can be uninstalled (its own rows only; the old window comes back). |

## 8. Deviations / choices

1. **Three shared modules not `-u`'d**: the handover listed `pb_scheme_map`, `pb_probation`, `pb_hr_payroll_formula`
   among "manifest version changed"; the diff and the P5a table say no bump and methods only, so they shipped as
   files and loaded with the restart. Upgrading them would only have added cascade time.
2. **Browser walks on the payobook copy, live L4 by server call** (§6 note). Live L1/L3/L6–L9 not clicked on
   payobook.com.
3. **L2 Indonesian team** does not exist on payobook; the Indonesian path was shown as the country mismatch case.
4. **L4 "approve"**: payobook has no approval route for new hires (fast lane), so there was nothing to approve.
5. **L6** not testable (no signed offer on payobook); nothing seeded.
6. Suites ran on the server copy with 8 environmental failures, proven green with the environment fixed (§3.2).
7. Extra scripts beyond the precedent: `nh_rh_tests2.sh` (environment re-run), `nh_rh_users_pb.py` (two throwaway
   logins on the payobook copy), `nh_live_hire.py` (live L4). The rize copy's throwaway login needed contract and
   payroll roles and a restart of the copy's server to see contracts (its rights were cached) — copy only.

## 9. Left behind

- Live payobook: one demo hire **"DEMO NH P5b Live Check"** (employee, contract, checklist, asks, 1 equipment request,
  contract letter). Demo data, kept on purpose.
- Backups `/odoo/backups/newhire-20261125T0719Z/` and evidence `/tmp/newhire-p5b-20261125T0719Z/`. Rehearsal copies,
  their file folders, the rehearsal service and every throwaway login: removed.
- Local: worktree `gitlocal-worktrees/nh-release` (branch `nh-release-p5b` = `19.1` + this report) can be removed.

## 10. Open items / questions

1. **Owner look on payobook.com** (two minutes): People › Employees › Add employee; then decide when the other four
   databases get the studio (PENDING row added; rollout = `-i pb_new_hire` per database, risky tier).
2. payobook has **no Indonesian team** and **no approval step for new hires**, so the Indonesian path and the
   "second person approves" path cannot be demonstrated there. Add an Indonesian demo team/scheme and a demo approval
   route if the owner wants to show them.
3. The approval engine's answer after a direct add reads "Add somebody to the payroll — done." (seen in the server
   answer, not on the studio's done screen, which names the person). Pre-existing engine wording; check where it shows.
4. Another session (DOCSTUDIO PDFFIX) opened a START at 08:07 that upgrades `pb_hr_payroll_formula` to 19.0.1.171.0 and
   switches the PDF engine; its line says it carries the NEWHIRE factor-out. After it, re-check one contract letter
   from the studio on payobook.
5. Carried from P5a §7: joining-checklist step names untranslated; Learn has no Indonesian.

## 11. New gotchas
NH73–NH77 in the ledger.
