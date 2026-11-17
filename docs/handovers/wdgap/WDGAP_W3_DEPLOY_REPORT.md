# WDGAP wave 3 — deploy report (merge W3-A, W3-B, W3-C; live ×5; verify)

Merge-deploy-verify agent, 2026-11-17 (UTC). Handover `WDGAP_W3_DEPLOY_HANDOVER.md` (method of the
S5/S6/S8/S9 deploy handovers).

**Result: merged, pushed to `19.1` at `201feacda` (fast-forward from `3276686c7`, no force), LIVE on
all five databases** (payobook, payobook_template, p0clone, rize, sudima). Eight modules upgraded ×5;
`pb_review_forms` tree copied (test file only). **356 s down** (21:24:54–21:30:50 UTC). Deploy notes
START 21:09, DONE 21:39 UTC. abm, pbf_preview, recruit_connect untouched; Codex's modules (pb_people,
pb_employee_vault, pb_scheme_map, pb_tenants, pb_approval_config, pb_hr_payroll_vietnam) untouched.
Nothing held back. **No bank-copy batch exists on rize or sudima** — the W3-C builder may now create
them (ruling BG4: after this DONE line).

## 1. Merge

Branch `wdgap-w3-merge` from `origin/19.1` @ `3276686c7` (which already carried Codex's 11-17 commits),
`--no-ff` in the order `wdgap-w3a` (8fbb8e9be), `wdgap-w3b` (c3595a58a), `wdgap-w3c` (e8286b25e):
**no conflict**. Then `201feacda`: the one merge-time edit + seam tests.

**Merge-time edit (W3-A report §6, exactly as written)** —
`pb_review_forms/tests/test_wdgap_s9_merge_seams.py`: after `cls.conduct_named` (line 69–70) a second
named person `cls.conduct_second = user('cn2', ['base.group_user', 'pb_conduct.group_conduct_user'])`
(lines 71–72); line 97 `F.issue_letter(cls.letter.id)` replaced by `F.move(cid, 'ask_signoff')` + the
second person's `move(cid, 'confirm_signoff')` (lines 100–102). (The handover called it the test that
"pinned the old Hidden behaviour"; the seam file has no Hidden assertion — the failing part was the
directly issued warning letter, which CD1 now refuses.) No version raise (test file only).

**New seam tests** `pb_pay_scales/tests/test_wdgap_w3_merge_seams.py` (tag `wdgap_w3m`), test file only,
`pb_pay_scales` is upgraded anyway.

Versions after the merge (all raised by the builders): pb_people_reports 19.0.1.0.0 → 19.0.1.1.0,
pb_conduct 19.0.1.0.0 → 19.0.1.1.0, pb_pay_scales 19.0.1.1.0 → 19.0.1.2.0, pb_people_advanced
19.0.1.1.3 → 19.0.1.1.5, pb_contract_lifecycle 19.0.1.3.3 → 19.0.1.3.5, pb_contract_rules 19.0.1.0.1 →
19.0.1.0.2, pb_hiring_internal 19.0.1.1.0 → 19.0.1.2.0, pb_bank_ocr 19.0.1.4.0 → 19.0.1.5.0;
pb_review_forms 19.0.1.0.1 (unchanged). No new module.

### 1.1 Static gates (merged diff vs `3276686c7`, 80 files)
py_compile 48: 0 failures. XML 4: 0. `node --check` 4 JS: ok. PO parse (`PoFileReader`) 14 `.po/.pot`:
0 failures, 0 msgstr naming the vendor. Vendor word on added lines: only technical (`.po` markers,
imports, docs, `@odoo-module`) and pb_conduct's `/odoo` route fallback when `/bizapp` is absent (never
shown as text; every live site has `/bizapp`). No credentials in the merged diff (scanned).

### 1.2 Seams — all pass

| # | Seam | Proof (merged tree) |
|---|---|---|
| a | Pay Review (W3-B) + "Raise the scale" (S8-D) share the hourly job | **M1** (new): a scale rise and a review due the same day: nothing before the day; on the day the rise writes A and C, the review writes B; C (in both) is **left out of the review and listed** ("changed since", PRV2) — never overwritten; one dated record per written rise (B = "From the pay review"); a second run writes nothing (SQL spy). Plus W3-B V1–V8 and S8-D R01–R12 (pb_pay_scales 43 tests, 0 failed). |
| b | Start date in a paid month → "Re-work those months" → draft Past-month re-work, no back pay | W3-B V5 on the merged tree with `pb_retro` installed (not skipped): pass |
| c | Renewal copies kind + treatment Permanent only, never Probation; pay lines still carried; Make it permanent works; link | **M2** (new): ONE renewal of a Vietnam fixed-term, Permanent contract with two pay lines — on the Contracts "Renew" path AND the decision board's extension — carries Fixed-term, Permanent, both pay lines and the link; old contract untouched; Make it permanent → open-ended, lines carried, treatment not copied, linked. Plus W3-B N1–N6, T1–T4 and S8-D X1–X6: pass |
| d | IM2: internal hire not asked for papers, no emails; outsider unchanged | W3-C IM2-1 … IM2-6 (pb_hiring_internal 53 tests, all pass) |
| e | Privacy matrix as every role (payroll officer, payroll manager, general HR, HR manager, lifecycle user, un-named administrator, line manager, another employee, the employee, first named, second named, named person who is the subject) | W3-A T106–T115, T54 (HTTP as the portal employee), T80/T81/T94 (people reports: HR only, nothing hidden) and the Step 9 seams M1–M3 (re-run with the fix): pass. Second sign-off never in the general Approvals inbox (T114: no approval request, event, mail or to-do). **Surveys still hide groups under 5, Excel included**: pb_voice 47 tests pass. |
| e+ | One notice per bank batch (W3-C follow-up, BG2–BG4) | W3-C N1–N9 in pb_bank_ocr (55 tests; only the 4 recorded baseline errors): a held batch of N → 1 to-do per approver, done when decided; a single bank change as before |

### 1.3 Combined local runs (Mac, ONE database `wdgap_w3m_t` = copy of `upd_p6_t_tpl`, port 8977)

Base: `-u` the 44 modules behind the tree, `-i` pb_retro, pb_pay_scales, pb_pay_package, pb_job_change,
pb_contract_rules, pb_review_forms, pb_conduct, pb_people_reports, pb_voice, pb_hiring_internal, the
Step 6 modules, pb_time_pay, pb_leave_setup: EXIT 0, 0 ERROR.

| Run | Suites | Result |
|---|---|---|
| A | pb_people_reports 20, pb_conduct 54, pb_pay_scales 43, pb_contract_lifecycle 10, pb_contract_rules 19, pb_review_forms 47 (incl. Step 9 seams), pb_voice 47, pb_pay 136, pb_job_change 22, pb_employee_vault 21, pb_me_portal 93, pb_people_hub 27, pb_retro 61 | **600 tests, 6 failed + 2 errors = recorded baselines**: pb_me_portal ×5 (test_05_grid E, test_01_profile E, test_06_font, test_12_vi_po, test_t1_7), pb_people_hub ×2 (contracts action, lens order), pb_pay test_t4c. (`TestMeHomeSource.test_01` now passes.) |
| B | pb_hiring 530, pb_hiring_internal 53, pb_bank_ocr 55, pb_records 120, pb_approval_config 150, biz_approval_workflow 69 | **977 tests, 20 failed + 7 errors**: the recorded baselines (pb_hiring 10 = W3-C/S6-B list; pb_bank_ocr 4 errors test_07/07b/09/15; pb_approval_config u10, the look, z06d, z06e, u13) **plus 8 pb_hiring public-page tests** (apply page 05–11, joining pages, request page) that fail **identically on the 19.1 code** with the same local conf (proven: same 12 failures with `origin/19.1`'s pb_hiring_internal on a copy) — a local set-up artifact (W3M-1), not the merge. |

Both local databases and their file folders dropped; no other builder's database touched.

## 2. Backups and rehearsal (server)

**Backups** `/odoo/backups/wdgap-w3-20261117T210906Z/`: payobook 82,970,196 bytes, payobook_template
30,510,664, p0clone 30,932,832, rize 45,503,046, sudima 32,963,337 — each read back with `pg_restore -l`;
each database's file folder hard-linked (10,188 / 582 / 174 / 1,274 / 1,214 files); previous trees of
the 9 modules (`previous-trees.tgz`). Evidence `/tmp/wdgap-w3-20261117T210906Z/`. Staged =
`git archive 201feacda`, 9 trees hash-checked = commit.

**Rehearsal — PASSED** (hidden rize copy: database marked as a template before restore, every job and
mail server off; 479 s; then a second short copy for the probe; both dropped with `--force`, file
folders removed):

| Check | Result |
|---|---|
| Upgrade | EXIT 0 in 68 s; **0 ERROR, 0 Traceback**; versions = manifests |
| Payslips old code vs new code — runs 2110, 2112, 2115, 2116 (India + Vietnam, 174 payslips, 5,736 lines) | **0 differing payslips**; 53 computed (India) identical line for line; 121 refused **identically** before and after for reasons already there (2112: text in a number column; 2116: "the source changed" / "exactly one effective contract"; 2115: 1 "preparation does not match"); run totals identical; "figures add up" true/true |
| Contracts (+ kind/treatment/link columns), contract pay lines, dated changes, payslips, lines, line total, runs, bank accounts, bank changes, pay reviews, pay records, scale rises, conduct cases/letters, applicants, approval requests, outbox, mails, to-dos, users, employees, group memberships | **identical** after the upgrade and at the end, except **messages +4**: empty tracking notes the upgrade writes on two Rize job records and two server actions (it re-imports job records; same 4 on live, W3M-4) |
| Nothing queued to send | 0 new mails, 0 to-dos, 0 approval outbox rows from the upgrade |
| Scale-rise + pay-review job run once | nothing to do (`{}`) |
| DEMO pay review, start 1 Dec 2026 (probe, rolled back) | Apply → "Applies on 1 Dec 2026", wage unchanged, 0 dated records; on the day → wage 10,500,000, ONE dated record "From the pay review"; job again → nothing |
| DEMO Renew of a Vietnam fixed-term, Permanent contract | form ready-filled Fixed-term + Permanent (offered: Not set / Permanent — no trial); new contract Fixed-term, Permanent, linked to the old one |
| Renewal-link check on the copy | 0 pairs |

Not provable by recompute: rize's Vietnam runs refuse before and after (pre-existing), so the Vietnam
pay formula's reading of the treatment was not exercised on real rize data; no existing contract's
kind/treatment changed (checksum identical) and W3-B T4 proves a renewed Permanent contract computes
exactly like the old one.

## 3. Read-only live checks (20:14 UTC and again inside the go-live)

| Check | payobook | payobook_template | p0clone | rize | sudima |
|---|---|---|---|---|---|
| Open START by anyone | none (last: Codex 13:12 DONE + VERIFIED notes) | | | | |
| Server | disk 26 GB free of 77; 1.7 GB memory available; one service process | | | | |
| Live trees of the 9 modules = `origin/19.1` before the merge | yes (no module newer on the server — nothing rolled back) | | | | |
| Jobs total / active | 111 / 58 (156 OFF) | 99 / 40 | 99 / 48 | 99 / 91 | 99 / 90 |
| Pay reviews with no start date | 0 | 0 | 0 | 0 | 0 |
| Pay reviews | 1 draft | none | none | none | none |
| Conduct cases / named people | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| Bank changes waiting (Compliance › Bank) | 0 | 0 | 0 | 0 | 0 |
| Bank-copy batch rows | 0 | 0 | 0 | 0 | 0 |

rize has one other request waiting in the Approvals inbox: "Bank details for 4 people" (a Records Desk
request from Codex's 11-17 client update, RD00290) — not a Compliance › Bank change; untouched.

## 4. Go live

- Activity check: first attempt (21:24:24) refused on one rize request — a bot's `GET /bizapp` answered
  with a redirect (no session); the filter was tightened to answered requests and the second attempt
  found **no signed-in activity on rize/payobook since 21:09:54** → stop 21:24:54.
- Per database (order payobook_template, p0clone, sudima, rize, payobook):
  `-u pb_people_reports,pb_conduct,pb_pay_scales,pb_people_advanced,pb_contract_lifecycle,pb_contract_rules,pb_hiring_internal,pb_bank_ocr`;
  signal row + bundle purge + `web.assets.version` = `wdgap-w3-20261117T210906Z`. Upgrades 63, 63, 64,
  67, 79 s — all EXIT 0, 0 ERROR.
- Start 21:30:49, port up 21:30:50: **356 s down (5 min 56 s)**. Five sites warmed: 200.

### Versions before → after (all five)

| Module | Before | After |
|---|---|---|
| pb_people_reports | 19.0.1.0.0 | 19.0.1.1.0 |
| pb_conduct | 19.0.1.0.0 | 19.0.1.1.0 |
| pb_pay_scales | 19.0.1.1.0 | 19.0.1.2.0 (+ seam test file) |
| pb_people_advanced | 19.0.1.1.3 | 19.0.1.1.5 |
| pb_contract_lifecycle | 19.0.1.3.3 | 19.0.1.3.5 |
| pb_contract_rules | 19.0.1.0.1 | 19.0.1.0.2 |
| pb_hiring_internal | 19.0.1.1.0 | 19.0.1.2.0 |
| pb_bank_ocr | 19.0.1.4.0 | 19.0.1.5.0 |
| pb_review_forms | 19.0.1.0.1 | 19.0.1.0.1 (test file) |

### Verification
- **Trees**: all 9 server trees byte-identical to `201feacda`. **Versions**: manifest = `latest_version`
  ×5, 0 mismatches.
- **Jobs**: equal to the snapshot on all five (111/58, 99/40, 99/48, 99/91, 99/90). payobook_template job
  45 "Employee Vault: document expiry check" was switched on by the upgrade and switched straight back
  off. payobook job 156 still OFF. No new job (W3-B reuses the scale-rise job).
- **Data before = after** on payobook, payobook_template, p0clone, sudima: every item of §2's list.
  rize: identical except messages +4 (the tracking notes, W3M-4).
- **Silent ×5**: 0 conduct cases, nobody named; 0 bank changes waiting; **0 bank-copy batch rows on rize
  and sudima**; 0 batch notices; 0 pay records waiting.
- Server log since the stop: **0 ERROR/CRITICAL, 0 Traceback** (re-checked after the walk). One service
  process. Sites 200 ×5. Lock released.

### Unlinked renewals (read-only check, run after go-live — the tool ships with the new code)

| Site | Unlinked renewals | Already joined by dates | Red "past the rule" warning now → if linked |
|---|---|---|---|
| payobook (demo) | 7 people | all 7 (next-day renewals) | 0 → 0 |
| payobook_template | 0 | — | 0 → 0 |
| p0clone | 0 | — | 0 → 0 |
| rize | 0 | — | 0 → 0 |
| sudima | 0 | — | 0 → 0 |

Lists: `outputs/wdgap-w3-renewal-links-2026-11-17/` (main checkout, never committed). Nothing changed.

## 5. Checks on payobook.com (look-only; everything tried was rolled back)

As QA Test (uid 6672) inside the server's shell, rolled back (no password used):

| Screen | Result |
|---|---|
| People › Insights → People reports | opens; **no "Hidden" anywhere**; month-by-month rows (10 for 2026 so far) and quarters; "Last 12 months" offered; Excel built (8 KB) |
| Talent › Conduct | refused to QA: "Conduct cases are seen only by the people HR names for them on the Access screen…" (0 cases, nobody named) |
| Pay Review (DEMO review, start 1 Dec 2026, one demo person) | Apply → chip **"Applies on 1 Dec 2026"**, wage 5,000,000 before and after, 0 dated records, "Take it back" offered → "Taken back. Nobody's pay changed, and the review is approved again." — then the whole transaction rolled back |
| Contracts → Renew on a running fixed-term demo contract | the dialog's "Kind of contract (Vietnam)" and "Payroll treatment (Vietnam)" are shown, ready-filled from the old contract (Open-ended / Not set — the payobook demo has no contract marked Fixed-term or Permanent; the rehearsal proved Fixed-term + Permanent on rize data) |
| An existing demo payslip PDF (144281) | renders, 152 KB, real PDF |

payobook counts identical before and after these checks.

Browser (owner's signed-in session, my own tab, nothing pressed that saves): People › Insights → People
reports — tiles, "Headcount at each month end" line, "Last 12 months", Download; no "Hidden", no vendor
name; People › Pay → Review opens (demo review "Being written"). **Console: no errors.** Tab closed.

Other four sites (server shell as their administrator, read-only, rolled back): People reports open with
no "Hidden" and the month rows; "Last 12 months" offered; Excel builds (8–13 KB); Conduct board refused
to the un-named administrator; 0 cases.

## 6. Held / left off

- Nothing held back.
- **Not done on purpose**: creating or approving a bank-copy batch (the W3-C builder does it after this
  DONE line, BG4); naming anyone for conduct; applying a real pay review; renewing a real contract.

## 7. Questions for the owner (plain words)

The questions in the three phase reports were all answered on 17–18 Nov (CD4–CD6, RN3, PRV2, BG2–BG4).
Still open from them:
1. **Rize: 126 people with Indonesian bank accounts** are left out of the bank copy until there is an
   Indonesian bank file. Do you want that bank file built next?
2. **Sudima: 257 people** whose bank account is in another name (or a close name) are left out of the
   copy. Who checks that list with Sudima?
3. **Payobook demo** has no contract marked "Fixed-term" or "Permanent", so the new ready-filled Renew
   boxes show "Open-ended / Not set" in demos. Should the demo world get a few fixed-term, Permanent
   contracts so the feature can be shown?

## 8. New gotchas (ledger)
W3M-1 (local conf without database listing breaks public-page tests), W3M-2 (postgres cannot read dumps
under `/odoo`), W3M-3 (report renders HTML while `current_test` is set; `res.company.country_id` not
stored), W3M-4 (upgrade re-imports job records: re-activated jobs, tracking notes; activity check counts
only answered requests). Builders' rows W3A-1..4, W3B-1..4, W3C-1..6 referenced in the ledger.
