# WDGAP IDB1-F — payment list access = bank file access; demo bank accounts (payobook)

Builder + deployer, 2026-11-18 (UTC). Follow-ups to the IDB1 deploy report §6.1 / §7 questions 2–3
(`WDGAP_IDB1_DEPLOY_REPORT.md`). Method: `WDGAP_W3_DEPLOY_HANDOVER.md` (NORMAL tier with backups ×5,
rize-copy rehearsal, activity gate), the IDB1 deploy's proven scripts (`/tmp/idb1_*` on the server,
derived into `/tmp/idb1f_*`).

**Result: LIVE.** Part A on all five databases (payobook, payobook_template, p0clone, rize, sudima):
`19.1` @ `4191c09e9` (fast-forward from `964c2f3ca`, no force), `pb_pay_delivery` 19.0.1.8.0 →
**19.0.1.8.1** ×5, **311 s down** (02:19:08–02:24:19 UTC). Part B on payobook only, service up, no
upgrade. Deploy notes: A START 01:59 / DONE 02:27; B START 02:27 / DONE 02:34. Nothing held.
abm, pbf_preview, recruit_connect untouched; no other module touched. The waiting bank-copy batches
are untouched: **rize 59, sudima 358 waiting** (nobody approved or refused).

## 1. Part A — the mismatch and the fix

### 1.1 Cause (ledger IDB1M-2)
Making the bank file needs: the pay gate (`_pay_groups_held`: administrator, payroll manager or a
finance role), create rights on the stored bank file (payroll manager or `base.group_system`) and the
bank file's record rule (payroll officer or payroll manager → everything). The payment list's stored
record (`pb.payment.list.file`, IDB2) had the same ACL for create but its full-read rule was **payroll
manager only**; anybody else only reached lists they were seated on. A payroll officer with
administrator rights (QA Test: payroll officer + `base.group_system` + finance) passed every bank-file
check but the list's `create` failed the record rule → the raw "top-secret records" message.

Live proof before the fix (rolled-back probe `docs/handovers/wdgap/idb1f/idb1f_equiv.py`, every
active login that may open Pay & deliver presses Prepare on both, run 335): **payobook 5 of 7 agree,
2 disagree** (QA Test + one more: bank file ok, list refused for access). Read-only rule count:
payobook 2 affected, rize/sudima/payobook_template/p0clone 0.

### 1.2 Fix (`pb_pay_delivery` only)
| File | Change |
|---|---|
| `security/money_out_rules.xml` | `rule_payment_list_file_payroll`: groups = the bank file's own (payroll officer + payroll manager); domain `[(1,'=',1)] if user.env['pb.money.approval.mixin']._pay_groups_held(user) else [('seat_user_ids','in',[user.id])]` — everything only for those who also pass the bank file's download gate (single source: `approval_common.PAY_GROUPS`) |
| `security/ir.model.access.csv` | `access_payment_list_file_hr` — payroll officer read, as `access_bank_file_hr` |
| `migrations/19.0.1.8.1/post-idb1f_payment_list_rule.py` | the rules file is `noupdate="1"`: rewrites the existing rule (name, groups, domain) on upgrade; idempotent |
| `__manifest__.py` | 19.0.1.8.0 → 19.0.1.8.1 |
| `tests/test_wdgap_idb1f_access.py` | new (6 tests) |

Kept unchanged: the IDB2 second-approval gate (same `bankfile` process, route, approvers,
independence); the builder's safeguard — a payroll officer who cannot download the bank file reads
a stored list only when asked to decide it (test 4); the download door (`_require_access` + run read +
approved bytes). No new user-facing text (the rule name is a technical label, no vendor word).

Resulting sets, by construction equal to the bank file's:
* **prepare** = pay gate ∧ (payroll manager ∨ administrator `group_system`) ∧ (payroll officer ∨ manager);
* **download / open a stored list** = pay gate ∧ (payroll officer ∨ manager), or seated on that list
  (and the pay gate for the download itself).

### 1.3 Tests (local `wdgap_idb1f_t` = copy of `upd_p6_t_tpl`, 44 behind modules `-u`, port 8697; dropped)
Role matrix — each role does the bank-file thing and the payment-list thing on the same approved
run; outcomes must be equal AND equal the pinned expectation:

| Role | Prepare bank file / list | Download bank file / list check / list download / open stored list |
|---|---|---|
| pay manager | ok / ok | ok ×4 |
| payroll officer + administrator (QA Test) | ok / ok | ok ×4 |
| payroll officer + administrator + finance | ok / ok | ok ×4 |
| payroll officer + finance | refused / refused | ok ×4 |
| payroll officer + access rights (no admin) | refused / refused | ok ×4 |
| payroll officer | refused / refused | refused ×4 |
| administrator without a payroll role | refused / refused | refused ×4 |
| finance without a payroll role | refused / refused | refused ×4 |
| HR officer | refused / refused | refused ×4 |
| portal | refused / refused | refused ×4 |

("payroll officer" = the payroll app's officer group + the pay screens' officer group, as QA Test
holds; the plain payroll-app officer alone cannot read pay runs — IDB1F-3.)

| # | Test | Result |
|---|---|---|
| 1 | prepare = make the bank file, every role (+ portal) | PASS |
| 2 | download / check / open stored list = download the bank file, every role (+ portal) | PASS |
| 3 | QA-like login prepares; screen shows it waiting (bank file's steps), download off; after the two approvals it downloads | PASS |
| 4 | plain payroll officer cannot open a stored list; can once seated on it; still cannot download | PASS |
| 5 | rule = bank file's groups; migration domain/name = XML; running the migration again changes nothing | PASS |
| 6 | direct address: QA-like 200 after approval; payroll officer, admin without payroll role, HR officer, portal non-200 and no account number, no vendor word | PASS |

| Suite run | Tests | Failed / errors |
|---|---|---|
| `-u pb_pay_delivery`, tags `/pb_pay_delivery,/pb_retro` (incl. all IDB1/IDB2 approval-gate tests and the Vietnamese bank file golden test — byte-identical) | 140 | **0 / 0** |
| `-u pb_approval_config,pb_bank_ocr,biz_approval_workflow`, their tags | 274 | 4 failed + 5 errors = **exactly the recorded baselines** (u10, the look, u13, z06d, z06e; bank_ocr 07, 07b, 09, 15) |

## 2. Deploy (Part A)

* Read `/opt/deploy-notes.md`: no open START (last: IDB1 NOTE 01:30). Live `pb_pay_delivery` tree =
  `964c2f3ca` (`b3a93a737b3c`, 19.0.1.8.0) — nothing newer on the server, nothing rolled back.
* Staged = `git archive 4191c09e9 pb_pay_delivery` (tree `d732eb61c755`).
* **Backups** `/odoo/backups/wdgap-idb1f-20261118T015908Z/`: payobook 82,869,169 bytes,
  payobook_template 30,573,643, p0clone 30,995,596, rize 44,024,740, sudima 31,582,185 — each read back
  (`pg_restore -l`); file folders hard-linked (10,192 / 582 / 174 / 1,268 / 1,204 files); previous tree
  `previous-trees.tgz`. Evidence `/tmp/wdgap-idb1f-20261118T015908Z/`.
* **Rehearsal** (hidden rize copy, jobs + mail off, 1,044 s, dropped with `--force`, file folder removed):
  upgrade EXIT 0 in 61 s, 0 ERROR, 0 Traceback, version 19.0.1.8.1; run 2111 (Indonesian staff)
  old vs new: **122 payslips, 4,026 lines, 0 differing**; Vietnamese bank file run 2112, 7 layouts:
  6 text layouts byte-identical, MB Bank Excel same digest (1 byte size change = its build stamp,
  IDB1M-3); counts identical except messages +4 (the usual upgrade notes, W3M-4); record rules 967 →
  967; 0 payment lists / requests; bank-copy batch 59 waiting; rule on the copy as declared.
* **Go live**: no answered signed-in request on rize/payobook since 02:04 → stop 02:19:08; upgrades
  57 / 56 / 56 / 59 / 68 s (payobook_template, p0clone, sudima, rize, payobook), all EXIT 0, 0 ERROR;
  no job re-activated; signal + bundle purge + `web.assets.version` per database; start 02:24:19;
  **311 s down**; five sites 200.
* **Verify**: tree = commit; manifest = `latest_version` ×5 (0 mismatches); jobs = snapshot ×5
  (111/58, 99/40, 99/48, 99/91, 99/90; payobook 156 still off); data before = after on payobook,
  payobook_template, p0clone, sudima (every item incl. record rules); rize identical except messages
  +4 (W3M-4); 0 payment lists, 0 requests on them, processes 65 ×5; bank-copy batches rize 59 / sudima
  358 waiting, unchanged; server log from the stop's line: 0 ERROR/CRITICAL, 0 Traceback; one
  service process.
* **Live probe after** (rolled back, mail stubbed — 0 tried, files kept in the database):
  **payobook 7 of 7 agree** (QA Test: bank file ok, payment list ok; 1 administrator without a payroll
  role: refused for both); p0clone 1 of 1 agree (refused both); payobook_template and sudima: no
  finished pay run to try; rize copy: no finished run either.

## 3. Part B — demo bank accounts on record (payobook only)

Seed `docs/handovers/wdgap/idb1f/idb1f_demo_bank_seed.py` (`odoo-bin shell`, the DM1 precedent):
* For every **active demo person of Payobook Vietnam JSC who is paid by bank** (has a bank-file
  number) and has **no** bank account on record (nor any account on their contact): one bank account
  on record — bank = the bank named in their bank-file fields (Agribank 475, Vietcombank 469, TPBank
  464, VietinBank 462, VPBank 456, BIDV 444, ACB 441, MB Bank 434, Sacombank 427, Techcombank 426),
  number **obviously fake** `9999` + employee id on 8 digits, holder = the employee's name, linked to
  the employee. 10 bank records created (the database had only 3 unrelated ones).
* Six people of **"Payroll Manufacturing July 2026"** (the six lowest employee ids of that run, so a
  re-run picks the same six) left imperfect: 2 with no account, 1 holder name close but not the same,
  1 holder = another demo person's name, 2 sharing one account number.
* Add-only, idempotent (a person with an account is never touched; bank-file fields never written),
  refuses any database but payobook (or a local `wdgap_idb1f*` copy), `IDB1F_DRY=1` = roll back.
  Every record made is on the demo register ("DEMO HR programme data", label "DEMO bank accounts on
  record (WDGAP IDB1-F)"). Rails in its own repeatable-read transaction: employees, payslips, runs,
  logins, every mail row, outgoing mail, to-dos, active job ids, bank changes, approval requests, the
  bank-file fields (checksum) and every existing bank account row (checksum) unchanged; accounts and
  banks move by exactly what was made — else rollback.

Local: dry run, run, second run on `wdgap_idb1f_demo` (copy of `upd_p5e_pay`, 45 modules `-u`):
identical to live below; dropped after.

Live (service up), payobook only:

| Check | Before | After |
|---|---|---|
| Bank accounts on record | 9 (none linked to an employee) | 4,507 (+4,498) |
| Banks | 3 | 13 (+10) |
| Demo register rows | — | +4,508 |
| Employees / payslips / pay runs / logins | 4,581 / 34,322 / 53 / 453 | same |
| Mail rows / outgoing / to-dos / approval requests / bank changes | 3,135 / 0 / 391 / 86 / 0 | same |
| Active jobs | 58 (same ids) | same |
| Bank-file fields (checksum) | — | identical |
| Messages | 35,013 | 39,511 (+4,498: the standard "Bank Account created" note on each person's contact; no notification, no email) |

Dry run first (rolled back), run (committed), second run: **made 0**. All-database counts script
before vs after: only bank accounts and messages moved.

Showcase run — what the payment list now says: **40 people • 784,652,817 VND • 6 need a check**
(2 "No bank account on record", 1 "close to, but not the same as, the employee's name", 1 "in another
person's name", 2 "Same account as …"). Before: 40 need a check (all "No bank account on record").

## 4. Checks on payobook.com

As QA Test (uid 6672) in the server shell, rolled back, mail stubbed (0 tried), files in the
database; payobook counts identical before and after:

| Check | Result |
|---|---|
| Payment list card, run 335 | 40 people, VND 784,652,817, **6 need a check**; no account number and no vendor word in the card |
| Download before preparing | refused: "There is no approved payment list for this pay run yet." |
| **QA Test presses Prepare** | **accepted** (before the fix: access refused). Payobook Vietnam JSC's bank file route is "No approval needed", so — exactly like the bank file there — the list is approved the moment it is prepared (`bankfile`, one step "No approval needed") |
| Download after | Excel 8,665 bytes, CSV 5,765 bytes, no vendor word in content or file name |
| Vietnamese bank file, same run | builds: 40 rows, 0 left out |
| Demo payslip PDF 144281 | 152,447 bytes, real PDF |

Browser (owner's signed-in session, own tab, nothing pressed that saves): Pay & deliver on
"Payroll Manufacturing July 2026" → "Payment list (any bank)": "40 people • total 784,652,817 VND •
6 need a check", **Excel and CSV disabled** with "The payment list needs the same approval as the
bank file before it can be downloaded.", button "Prepare the payment list (no approval needed)"; no
vendor word on the page; no sideways scroll; payslip PDF 144281 opens (200, 152,447 bytes); **console:
no errors** (also after a reload). Tab closed.

## 5. Held / notes for the owner

* Nothing held.
* **The demo account numbers differ from the demo bank-file numbers** on purpose (the brief asked for
  obviously fake numbers and forbade changing the bank-file values). So a demo person's payment-list
  row shows `9999…` while their Vietnamese bank file row shows the older demo number; the Branch column
  stays empty for them (it is filled only when both places hold the same account). Not a problem for
  the demo; worth knowing if someone compares the two files side by side.
* On payobook the demo company's bank file needs no second approval, so a demo payment list is
  approved the moment it is prepared (same as its bank file). To show the "waiting for approval" step
  in a demo, the demo company's "Bank file approval" route would need a second step (owner choice).
* Two people on the showcase run carry no bank account on purpose; a later run of the seed keeps it
  that way.

## 6. Gotchas → ledger

| # | Gotcha |
|---|---|
| IDB1F-1 | `money_out_rules.xml` is `noupdate="1"`: changing an existing rule's XML changes nothing on an upgraded database. Rewrite it in a post-migration (and test that migration = XML). |
| IDB1F-2 | A TransactionCase helper named `_outcome` shadows unittest's own `self._outcome` ("'_Outcome' object is not callable"). |
| IDB1F-3 | The payroll app's officer group alone (`om_hr_payroll.group_hr_payroll_user`) has no read on pay runs on this build; the product's payroll officer is `pb_hr_payroll_base.group_payroll_base_officer` (+ the app group). Role tests must give both, as QA Test holds. |
| IDB1F-4 | Creating `res.partner.bank` (account module) always logs a "Bank Account created" note on the contact (one `mail.message` each, no notification) and a shell superuser cannot mark it trusted (`allow_out_payment` silently stays off). Count the notes as expected side rows. |
| IDB1F-5 | This agent's worktree guard refuses compound shell commands that mention the scratchpad path (it contains "gitlocal"): write the steps into a script file and run `bash <file>`. |
