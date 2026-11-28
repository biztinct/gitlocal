# WDGAP IDB1 — deploy report (merge IDB1 + IDB2; live ×5; verify)

Merge-deploy-verify agent, 2026-11-18 (UTC). Handover `WDGAP_IDB1_DEPLOY_HANDOVER.md` (copied beside
this report; method of `WDGAP_W3_DEPLOY_HANDOVER.md` and the S5/S6/S8/S9 chain).

**Result: merged, pushed to `19.1` at `e293e6180` (fast-forward from `8741d628c`, no force), LIVE on all
five databases** (payobook, payobook_template, p0clone, rize, sudima). `pb_pay_delivery` 19.0.1.6.0 →
19.0.1.8.0 ×5. **315 s down** (01:13:35–01:18:50 UTC). Deploy notes START 00:13, DONE 01:20 UTC. abm,
pbf_preview, recruit_connect untouched; no other module touched (Codex's modules not in the set). Nothing
held back. The waiting bank-copy batches on rize (59) and sudima (358) are untouched — nobody approved or
refused them. One follow-up found (§6.1): payroll officers who also hold a finance or administrator role
get a raw access message on "Prepare the payment list" (payobook demo: 2 logins; rize: none).

## 1. Merge

Branch `wdgap-idb1-merge` from `origin/19.1` @ `8741d628c` (W3 deploy report + DM1 demo seed), `--no-ff`
merge of `origin/wdgap-idb1` @ `1321bd707` (IDB1 + Follow-up IDB2) = **`e293e6180`**. One conflict, the
ledger (DM1 row vs IDB1 row) — resolved keeping both rows. No merge-time code edit: the merged
`pb_pay_delivery` tree is identical to the builder's branch (`git diff origin/wdgap-idb1 HEAD --
pb_pay_delivery` empty). Pushed `8741d628c..e293e6180 19.1` (fast-forward, no force) and the merge branch.

Version: `pb_pay_delivery` 19.0.1.6.0 → **19.0.1.8.0** (builder). No new module. Nothing outside
`pb_pay_delivery` changes (plus the builder's docs and the read-only count script).

### 1.1 Static gates (merged diff vs `8741d628c`, 23 files)
py_compile 13 Python files: 0 failures. XML 2: 0. `node --check` of the screen script: ok. PO parse
(`PoFileReader`): `vi_VN.po` 506 entries, `id_ID.po` 88 — 0 failures, **0 msgstr naming the vendor**, both
headers "Payobook 19.0". Vendor word on added lines: only tests asserting its absence and `.po` code
markers. Credentials: none (test logins get a random one-off password at run time, `secrets.token_urlsafe`).

### 1.2 Seams (merged tree) — all pass

| Seam | Proof |
|---|---|
| Vietnamese bank file byte-identical | IDB1 test 7 (golden stamps from the pre-IDB1 code, four layouts) on the merged tree: pass; and unchanged after building both payment lists. Rehearsal on real rize runs: §2 |
| Its existing approval untouched | the bank file's suites (`pb_pay_delivery` 73) and `pb_approval_config` 150 / `biz_approval_workflow` 69 on the merged tree: only recorded baselines; no route, catalogue row or approval process added (rehearsal: processes 65 → 65, same checksum) |
| List refused before its own approval — screen + direct address | `test_idb2_1` + the address test (non-200, no account number); rehearsal: "There is no approved payment list for this pay run yet." |
| Refused for anyone who cannot download the bank file | test 8 / IDB2 officer + portal tests (download, check, screen, address); rehearsal: both rize logins without the pay role refused prepare, check and screen (access refused) |
| Nothing in the Approvals inbox after upgrade | `test_idb2_4`; rehearsal and live ×5: 0 payment lists, 0 requests on them |
| A bank change waiting for approval (BK2 / the BG1 batches) is never used | tests 2, 5, 5b; rehearsal: the 4 people of the Indonesian run with a waiting bank-copy change carry their **approved** account, none flagged as a change (the copy proposes the same account) |

### 1.3 Combined local run (Mac, ONE database `wdgap_idb1m_t` = copy of `upd_p6_t_tpl`, port 8641)

Base: `-u` the 44 modules behind the tree, `-i pb_retro` (depends on `pb_pay_delivery`): EXIT 0, 0 ERROR.
Run A: `-u` and `--test-tags` `/pb_pay_delivery,/pb_approval_config,/pb_bank_ocr,/pb_retro,/biz_approval_workflow`:

| Suite | Tests | Failed / errors |
|---|---|---|
| pb_pay_delivery (incl. 23 IDB1/IDB2 tests) | 73 | 0 |
| pb_approval_config | 150 | 4 failed + 1 error = recorded baselines (u10, the look, u13, z06d, z06e) |
| pb_bank_ocr | 55 | 4 errors = recorded baselines (test_07, 07b, 09, 15) |
| pb_retro | 61 | 0 |
| biz_approval_workflow | 69 | 0 |
| **Total** | **408** | **4 failed + 5 errors = exactly the recorded baselines** |

Local database and its file folder dropped; no other builder's database touched.

## 2. Backups and rehearsal (server)

**Backups** `/odoo/backups/wdgap-idb1-20261118T001351Z/`: payobook 82,776,685 bytes, payobook_template
30,536,420, p0clone 30,961,910, rize 44,007,517, sudima 33,046,194 — each read back with `pg_restore -l`;
each database's file folder hard-linked (10,215 / 582 / 174 / 1,270 / 1,220 files); previous tree of
`pb_pay_delivery` (`previous-trees.tgz`). Evidence `/tmp/wdgap-idb1-20261118T001351Z/`. Staged =
`git archive e293e6180` (tree hash = commit); live tree before = `19.1` before the merge (nothing newer
on the server — nothing rolled back).

**Rehearsal — PASSED** (hidden rize copy: marked as a template before restore, every job and mail
server off; 1,252 s; then a second short copy for the payment-list probe, 180 s; both dropped with
`--force`, file folders removed):

| Check | Result |
|---|---|
| Upgrade `-u pb_pay_delivery` | EXIT 0 in 59 s; **0 ERROR, 0 Traceback**; version 19.0.1.8.0 |
| Payslips old code vs new code — runs 2110, 2111 (Indonesia), 2112, 2115 (236 payslips, 7,542 lines) | **0 differing payslips**; 175 computed identical line for line (India 53, **Indonesia 122**); 61 refused **identically** before and after (2112: 60, 2115: 1, pre-existing); run totals identical; "figures add up" true/true |
| Contracts, payslips, lines, line total, runs, bank accounts, bank-file fields, bank changes, bank files, money releases, approval requests, approval processes, outbox, trail lines, mails, to-dos, users, employees, group memberships | **identical** after the upgrade and at the end, except **messages +4** — the same empty tracking notes every upgrade writes on two Rize jobs and two server actions (W3M-4; proven on the second copy: ir.cron 62, 63, ir.actions.server 978, 983, empty bodies). Record rules 964 → 967 (the list's own company and approver rules) |
| Nothing in anybody's inbox after the upgrade | 0 payment lists, 0 requests on them; approval processes 65 → 65 (same checksum) |
| The waiting bank-copy batch on the copy | **59 waiting before, after the upgrade, after the probe — untouched** |
| Vietnamese bank file, old code vs new code — runs 1591 and 2112, all 7 layouts | the 6 text layouts **byte-identical**; the Excel layout (MB Bank) identical sheet and strings, its file 1 byte shorter only because the "built at" stamp inside the workbook is a new time (same digest of every part but the stamp; built again on the new code: same digest) |

**Payment list on the copy only** (run 2111 "TEST ID August 2026 — monthly Excel import", Indonesian
staff, marked approved inside the probe's transaction; everything rolled back — the list, both stored
files, the request, the trail lines; 0 lists and 0 files left on the copy before it was dropped; no file
written to any folder; e-mail sending stubbed — 0 tried):

| | |
|---|---|
| People in the list | **122** (all of the run; none on hold, paid another way or already paid) |
| Total per currency | **IDR 1,202,094,026** (122 people) — one currency only |
| Need a check | **4**: 3 "account holder name close to, but not the same as, the employee's name", 1 "account in another person's name" |
| No bank account on record | 0 |
| In the Vietnamese bank file | 0 Yes (the Vietnamese file leaves all 122 out; the card says the list can pay all 122) |
| People with a waiting bank change | 4 — all 4 carry the approved account, none flagged |
| Approval | process = the bank file's own (`bankfile`); **Rize's bank-file route today is "No approval needed"** (see §6) so the list was approved the moment it was prepared — exactly what the Vietnamese bank file does on Rize |
| Download | Excel 15,017 bytes, CSV 21,682 bytes (127 lines: header, 122 rows, totals); vendor word in neither; 3 trail lines (approval + 2 downloads) |
| Refusals | before preparing: "There is no approved payment list for this pay run yet."; 2 rize logins without the pay role refused prepare / check / screen |

## 3. Read-only live checks (23:55 UTC and again inside the go-live)

| Check | payobook | payobook_template | p0clone | rize | sudima |
|---|---|---|---|---|---|
| Open START by anyone | none (last: DM1 DONE 22:56, Codex VERIFIED 22:55) | | | | |
| Server | disk 26 GB free of 77; 1.6 GB memory available; one service process | | | | |
| Live `pb_pay_delivery` = `19.1` before the merge | yes, 19.0.1.6.0 (nothing newer on the server) | | | | |
| Jobs total / active | 111 / 58 (156 OFF) | 99 / 40 | 99 / 48 | 99 / 91 | 99 / 90 |
| Payment-list table | none | none | none | none | none |
| Approval processes | 65 | 65 | 65 | 65 | 65 |
| Stored bank files | 0 | 0 | 0 | 0 | 0 |
| Bank changes waiting (all = the bank-copy batch) | 0 | 0 | 0 | **59** | **358** |
| Bank-file route today | 3 companies: Payroll check → Finance approval; **Payobook Vietnam JSC: No approval needed** | Payroll check → Finance approval | same | **"Bank file approval" r2 = one step "No approval needed"** (18 Sep, independence-off change) | Payroll check → Finance approval |

**Who the Vietnamese file leaves out today** (builder's read-only count, active people, counts only):

| Site | Left out of the Vietnamese file | Of them with an approved bank account (the payment list can pay) | No account at all |
|---|---|---|---|
| payobook (demo) | 81 (3 companies) | 0 | 81 |
| payobook_template | 1 | 0 | 1 |
| p0clone | 12 | 0 | 12 |
| **rize** | **223** | **188** (Bank Central Asia 70, Mandiri 25, BRI 15, BNI 7, CIMB Niaga 2 … and Vietnamese banks whose bank-file fields are empty) | 35 |
| **sudima** | **651** | **642** (BIDV 586, Vietcombank 27 …) | 9 |

Many of the rize/sudima Vietnamese-bank people are in the waiting bank-copy batches; once a site approver
presses "Approve all" they move into the Vietnamese file.

## 4. Go live

- Activity check: signed-in work on **payobook** (one outside address, Access, Module insights, Learn)
  until 00:58:22 — re-checked every 10 minutes (00:43, 00:53, 01:03: busy; **01:13: quiet**, 30 min of
  waiting). The go-live script re-checked and found no answered signed-in request on rize/payobook since
  00:58:35 → stop 01:13:35.
- Per database (order payobook_template, p0clone, sudima, rize, payobook): `-u pb_pay_delivery`; signal
  row + bundle purge + `web.assets.version` = `wdgap-idb1-20261118T001351Z`. Upgrades 57, 57, 57, 60, 68 s
  — all EXIT 0, 0 ERROR. No job re-activated.
- Start 01:18:48, port up 01:18:50: **315 s down (5 min 15 s)**. Five sites warmed: 200.

### Verification
- **Tree**: server `pb_pay_delivery` byte-identical to `e293e6180`. **Versions**: manifest =
  `latest_version` ×5, 0 mismatches.
- **Jobs**: equal to the snapshot on all five (111/58, 99/40, 99/48, 99/91, 99/90); payobook job 156
  still OFF.
- **Data before = after** on payobook, payobook_template, p0clone, sudima — every item of §2's list;
  rize identical except messages +4 (the usual upgrade notes, W3M-4). Record rules +3 ×5 (the list's own).
- **Silent ×5**: 0 payment lists, 0 requests on them (nothing in anybody's Approvals inbox); approval
  processes 65; **bank-copy batches: rize 59 waiting, sudima 358 waiting — same as before, no approver
  has acted**; bank changes waiting 0 elsewhere.
- Server log since the stop: **0 ERROR/CRITICAL, 0 Traceback** (two traceback blocks seen in the first
  scan belong to warnings at 00:43–00:57, before the stop: the Module insights screen and a My Payobook
  landing check — pre-existing, not this module). One service process. Sites 200 ×5.

## 5. Checks on payobook.com (look-only; everything tried was rolled back)

As QA Test (uid 6672) inside the server's shell, rolled back, e-mail sending stubbed (0 tried), files
kept in the database so nothing reached the file folder; payobook counts identical before and after:

| Screen | Result |
|---|---|
| Pay & deliver › "Payroll Manufacturing July 2026" (demo, approved) — Payment list card | **40 people • total 784,652,817 VND • 40 need a check** (the demo people have bank-file numbers but no approved bank account, so every row says "No bank account on record"); no account number and no vendor word in the card |
| Download before approval | refused: "There is no approved payment list for this pay run yet." |
| Send for approval / approve | **not possible as QA Test**: QA is a payroll officer + finance + administrator but not a payroll manager — "Prepare" is refused with the standard access message (§6.1). Payobook Vietnam JSC is on "No approval needed", so there is no second person to try anyway. The full approval path was proven on the rize copy (§2). Nothing created |
| The Vietnamese bank file on the same run | still builds (Vietcombank CSV, 40 rows, 0 left out); QA can prepare the bank file record (tried, rolled back) |
| An existing demo payslip PDF (144281) | renders, 152,447 bytes, real PDF |

Browser (owner's signed-in session, my own tab, nothing pressed that saves): Pay & deliver → the run
list → "Payroll Manufacturing July 2026": Money out shows the bank file card, then **"Payment list (any
bank)"** — "Name, bank, account number and amount for everybody paid by bank transfer…", "40 people •
total 784,652,817 VND • 40 need a check", **Excel and CSV buttons disabled**, the reason "The payment
list needs the same approval as the bank file before it can be downloaded.", the button "Prepare the
payment list (no approval needed)" and "Account numbers come from approved bank details only. Read the
Check column before paying." No vendor name. **Console: no errors** (after a reload). Tab closed.

Other four sites (server shell as their administrator, read-only, rolled back): Pay & deliver opens on
all four; payobook_template and sudima have no pay run yet (the screen's three files are in the screen
bundle); p0clone's latest run shows the card (1 person, USD) with download refused before approval;
rize's latest run (a draft test run) shows the card with 0 people and download refused. Logins 200 ×5.

## 6. Held / left off

- Nothing held back.
- **Not done on purpose**: approving or refusing the bank-copy batches; preparing or approving a payment
  list on any live site; changing any approval route.

### 6.1 Follow-up for a builder (small)
The payment list's full-read rule is payroll manager only (IDB2's deliberate narrowing), but Pay &
deliver also opens for administrators and finance roles. A **payroll officer who also has a finance or
administrator role** sees "Prepare the payment list" and, on pressing it, gets the standard
"top-secret records" access message instead of a plain sentence (the bank file works for them).
Who is affected now: payobook demo 2 logins (QA Test + one more); rize 0; sudima, payobook_template,
p0clone: only administrators without any payroll group, who cannot prepare the bank file either.
Fix options for the builder: hide/explain the button for people who cannot prepare it, or give the same
people as the bank file the right to prepare it (owner choice — see question 2). Fails closed; no data
exposed.

## 7. Questions for the owner (plain words)

1. **Rize's bank file needs no second approval today.** Its "Bank file approval" setting was changed on
   18 Sep (when "whoever sent it in may not decide it" was switched off) into a single "No approval
   needed" step, although its description still says a payroll manager and a finance approver check it.
   The new payment list follows the bank file, so on Rize the pay team can prepare and download it
   straight away. Do you want Rize's bank file and payment list to need a second person again?
2. Two Payobook demo logins (QA Test among them) can open Pay & deliver and make the bank file, but get
   an "access" message when they press "Prepare the payment list". Should the people who can make the
   bank file also be able to prepare the payment list, or should the button simply say they need a payroll
   manager?
3. The Payobook demo people have bank-file numbers but no approved bank account, so every demo payment
   list says "No bank account on record" for everyone. Add demo bank accounts so the list can be shown
   with real-looking rows?

## 8. New gotchas (ledger)
IDB1M-1 (rize bank-file route is "No approval needed" despite its summary), IDB1M-2 (finance/admin
payroll officers refused at Prepare), IDB1M-3 (Excel bank layout carries a build-time stamp), IDB1M-4
(probe files land in the file folder unless stored in the database; mail stub; `_pay_groups_held`
location; log scans by line number).
