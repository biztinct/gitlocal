# WDGAP S2-F — dependants note (TD4) + Suggest for Indonesian schemes: built, live ×5

Builder + deployer, 2026-11-18 (UTC). Handover `WDGAP_S2F_HANDOVER.md` (copied beside this report);
method of `WDGAP_S2_DEPLOY_HANDOVER.md` and the proven S2 / IDB1-F scripts (`/tmp/s2_*` on the server,
derived into `/tmp/s2f_*`).

**Result: LIVE on all five databases** (payobook, payobook_template, p0clone, rize, sudima) at
`34f8a96d3` (`origin/wdgap-s2f`, branched from `origin/19.1` @ `aec5e14e0`; `19.1` fast-forwarded with
this report). `pb_form_lines` 19.0.1.1.0 → **19.0.1.1.1**, `pb_me_tax` 19.0.1.0.0 → **19.0.1.0.1** ×5.
**98 s down** (12:53:18–12:54:56 UTC). Deploy notes START 12:48, DONE 12:59 UTC. abm, pbf_preview,
recruit_connect untouched; both live trees were byte-identical to `origin/19.1` before (nothing newer on
the server, nothing rolled back). Nothing held. No JS/SCSS changed → no asset purge.

## 1. Fix 1 (TD4) — the HR-only "Tax dependants: Does not match" note, `pb_me_tax`

**Can "not set" be told from a real 0?** Partly (verified in code, `odoo/orm/fields_numeric.py`
`Float.convert_to_column` / `convert_to_record`, and on live data):
* The ORM reads a NULL `amount` as 0.0 but only ever WRITES a number. A component line created without an
  amount keeps NULL → **NULL = never written = "not set"**. That is the payobook demo case: `NPT` on 4,513
  running contracts, **4,512 NULL**, 1 written.
* A stored **0** can NOT be told apart from "not filled in": the contract screen writes the template's
  default (0) the moment a line is added. So the handover's fallback applies: **0 with confirmed
  dependants = not set → no note; 0 with none confirmed = equal → no note.**

Rule now (`pb_me_tax/models/hr_employee.py` `_pbtx_vn_written` + `_pbtx_vn_counts`): for each code in the
setting (`VNREGISTER,DEPS,NPT`), take only lines whose column is not NULL (read with SQL after a flush);
a code whose lines are all empty is skipped and the next code is tried; the first written figure is
compared; a written 0 with confirmed dependants → nothing to compare. **A note needs a real, non-zero
figure on the contract that differs from the confirmed dependants.** The contract is never written.

Tests (`tests/test_followup_td4.py`, all pass; S2-D T7 / DL.1–3 still pass):

| # | Test | Result |
|---|---|---|
| TD4.1 | line created with no figure (column NULL, asserted) + 2 confirmed → no note; reading writes nothing | PASS |
| TD4.2 | 0 and nobody confirmed → no note; 0 and 2 confirmed → no note | PASS |
| TD4.3 | 2 on the contract, 2 confirmed → no note | PASS |
| TD4.4 | 3 vs 2 → note naming both; 3 vs none confirmed → note; contract value unchanged | PASS |
| TD4.5 | empty `VNREGISTER` + `DEPS` 1, 2 confirmed → note from `DEPS` | PASS |
| TD4.6 | empty → no note; HR writes 3 → note; writes 1 (= confirmed) → none | PASS |

**Notes per live database (read-only probe, rolled back; counts only):**

| Site | Before | After |
|---|---|---|
| payobook (demo) | 2,454 of 4,581 | **1** (the one demo contract with a written figure) |
| payobook_template | 0 | 0 |
| p0clone | 0 of 12 | 0 |
| rize | 20 of 229 | **20** — every one is a real, non-zero contract figure that differs (none empty, none 0) |
| sudima | 0 of 651 | 0 |

## 2. Fix 2 — Suggest on Form lines for Indonesian schemes, `pb_form_lines`

**Why Suggest found nothing** (read-only SQL on live rize; pay ITEM names are configuration): rize's four
Indonesian schemes (`focused payroll` 7121 has the 244 payslips; 3943 archived, 7096, 7116) name the
items in plain English, and **every contribution and the tax item is marked "Included in another total"**
(`net_role_detail` — they add up into "Total income" / "Total deduction"). Suggest skipped every such
part. Names: `Old age employee` / `Old age company` (employer cost), `Pension employee` / `Pension
company`, `Accident insurance income` / `… deduction`, `Life insurance income` / `… deduction`, `BPJS
health employee`, `BPJS health company income` / `… deduction`, `Payable tax` (`PIT`), `BPJS TK wage base`,
`BPJS health wage base`. Confirmed from the scheme's own rate items: Accident insurance rate 0.24 % = JKK,
Life insurance rate 0.30 % = JKM, JHT employer 3.7 %, JP employer 2 %, health employer 4 %; the
employer's JKK / JKM / health premiums are carried as **income** items (taxable) and mirrored as
deductions. Generic enough to match safely — no customer code is used.

Change:
* New catalogue flag `suggest_parts` ("Suggest offers parts of a total") on **9 lines only**: BPJS TK
  JHT/JP employee + employer, JKK, JKM; BPJS Kesehatan employee + employer; BPMP PPh 21. There, a part may
  be proposed; a whole item still beats a part and the first pay role listed beats the next. On every
  other line both new ranks are 0 → **ordering and results unchanged** (`models/form_map.py`).
* Wider words (and roles `employer_cost,earning` on JKK / JKM / health employer) — table in
  `models/suggest_s2f.py`; two wage lines get words only (`bpjs tk wage`, `bpjs health wage`).
* Catalogue is `noupdate="1"`: XML changed for new installs, and the post-migration
  `migrations/19.0.1.1.1/post-s2f_suggest_words.py` writes the new words/roles/flag **only on a line whose
  words and roles still equal the value shipped before** (a changed line is left alone, logged);
  running it again changes nothing. **Suggest still never saves.**

Tests (`tests/test_s2f_suggest.py`, all pass):

| # | Test | Result |
|---|---|---|
| F2.1 | a scheme with the customer's names → JHT/JP/JKK/JKM/health employee + employer, both wage bases, PPh 21 = Payable tax; one per scheme per line; no total offered; nothing saved | PASS |
| F2.2 | a whole item beats a part (JP employee); employer cost beats income (health employer) | PASS |
| F2.3 | other countries: every non-Indonesian line has the flag off; Vietnam still never proposes a part and does propose the whole item | PASS |
| F2.4 | migration: old words → new (10 lines), a line someone changed left alone, other 303 lines untouched, second run = "already" | PASS |
| F2.5 | migration values = shipped XML; a fresh install carries them | PASS |

**What Suggest proposes now on rize** (live, read-only, rolled back; per line, × each of the 4
Indonesian schemes):

| Form | Line | Proposed |
|---|---|---|
| BPJS TK | JHT employee / employer | Old age employee / Old age company |
| | JP employee / employer | Pension employee / Pension company |
| | JKK employer | Accident insurance income |
| | JKM employer | Life insurance income |
| | Wage | BPJS TK wage base |
| BPJS Kesehatan | employee / employer | BPJS health employee / BPJS health company income |
| | Wage | BPJS health wage base |
| Monthly tax (BPMP) | PPh 21 withheld | **Payable tax** (new) |
| | Gross / Rate | Grossed-up gross / Monthly TER rate (unchanged) |

Before: BPJS TK 0, BPJS Kesehatan 0, BPMP 8 proposals (gross + rate only). After: 28 / 12 / 12. Nothing
mapped on any site (0 before, 0 after). payobook demo company: still nothing to suggest (its Indonesian
scheme has no such items). **Owner note:** the Gross line proposes rize's "Grossed-up gross" (unchanged
by this fix; the Step 2 rehearsal matched gross by hand) — "Total income" may be the better item; HR
picks on the screen.

Other suites on the same local copy: `pb_form_lines` 77 + 5, `pb_me_tax` 65 → 0 failed; `pb_govt_reports`,
`pb_compliance_hub`, `pb_employee_vault`, `pb_me_tax_cert` 101 → 1 failed = the recorded S2-A baseline
`test_generating_a_vn_filing_produces_a_real_file`. Local copy `wdgap_s2f_t` (of `upd_p6_t_tpl`, 50 behind
modules `-u`) dropped after. Static: py_compile, XML parse; no vendor word in added user-visible text;
no credentials.

## 3. Deploy

* Read-only first: no open START (last: Step 2 NOTE 09:43); disk 24 GB free; one service process; live
  trees of both modules = `origin/19.1` (19.0.1.1.0 `19f4e0eb69c0`, 19.0.1.0.0 `57df0844a9e3`).
  Staged = `git archive 34f8a96d3` (`7fbbaaaf820c`, `2ce7e6a9d212`).
* **Backups** `/odoo/backups/wdgap-s2f-20261118T124848Z/`: payobook 83,788,178 bytes, payobook_template
  30,933,770, p0clone 31,366,015, rize 45,720,230, sudima 31,948,994 — each read back (`pg_restore -l`);
  file folders hard-linked (10,197 / 582 / 175 / 1,283 / 1,207 files); previous trees
  `previous-trees.tgz`. Evidence `/tmp/wdgap-s2f-20261118T124848Z/`.
* **Rehearsal** (hidden rize copy, jobs + mail off, 121 s, dropped `--force`, file folder removed):
  upgrade EXIT 0 in 17 s, 0 ERROR, 0 Traceback; migration "updated" ×11; versions = manifests; counts
  before = after except the Suggest words (expected); probe as live below and wrote nothing; bank-copy
  batch 59 approved (as live).
* **Go live**: 0 answered signed-in requests on rize/payobook since 12:38 → stop 12:53:18; upgrades
  17 / 18 / 19 / 17 / 20 s (payobook_template, p0clone, sudima, rize, payobook), all EXIT 0, 0 ERROR,
  migration "updated" ×11 each; no job re-activated; start, port up 12:54:56: **98 s down**; sites 200 ×5.
* **Verify**: trees = commit; manifest = `latest_version` ×5 (0 mismatches); jobs = snapshot ×5
  (111/58, 99/40, 99/48, 99/91, 99/90; payobook 156 off); **data before = after ×5** — contracts +
  components, payslips + lines + total, runs, employees, dependants, bank accounts / fields / changes /
  files, payment lists, releases, detail requests, approval requests (86 / 0 / 6 / 173 / 362), mails,
  outgoing 0, to-dos, messages, users, groups, documents, form mappings 0, filings 0, form settings;
  only the Suggest words moved (same checksum ×5 = rehearsal); 9 lines with the flag ×5.
  **Bank-copy batches**: rize 59 approved (earlier, by Codex), **sudima 358 waiting — untouched**.
  Server log from the stop's line: 3,977 lines, **0 ERROR/CRITICAL, 0 Traceback**; one process.
* Not checked in a browser: the change has no screen of its own (the note simply no longer shows; Suggest
  is the existing button) — proved through the same server calls the screens use.

## 4. Gotchas → ledger
S2F-1 (Float NULL vs 0), S2F-2 (Suggest skipped every "part of a total").
