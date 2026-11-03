# FILLIN P1 — report (server: a new contract starts with the scheme's usual answers)

Implemented per `FILLIN_P1.md` + `FILLIN_LEDGER.md`. Code commit: **`ef836533e`**
on `19.1`, pushed (see deviation D2 for why the message on that commit is a
CONTRACTLIFE one). Deployed to the four databases at 22:07–22:13 UTC
2026-11-03; rize seeded; live smoke rolled back.

## 1. What was built

| Piece | Where |
|---|---|
| Fill on `hr.contract.create` (all creators), `pb_skip_fill_in` honoured | `pb_hr_payroll_formula/models/contract_fill_in.py` `HrContractFillIn.create / _pb_fill_in_defaults / _pb_fill_one` |
| Fill when "Paid by" goes empty → scheme | `pb_scheme_map/models/hr_employee.py` `_pb_recompute_paid_by` (collects `newly_known`) → `_pb_fill_in_newly_known` |
| Marks `pb_fill` / `pb_checked_by` / `pb_checked_at` + write hook | `contract_fill_in.py` `HrContractAdvantageFillIn` |
| `pb_fillin_unchecked()`, `pb_fillin_check(line_ids=None)` | `contract_fill_in.py` `HrContractFillIn` |
| Change sources `auto_default`, `checked`; model-level `log()` | `models/contract_component_change.py` |
| One search-by-code `template_for_rule(rule)` | `contract_fill_in.py`; batch `_get_or_create_advantage_template` now delegates |
| Batch `_log_contract_component_change` delegates to `log()` | `models/payroll_import_batch.py` |
| `hr.formula.rule.value_labels` + `value_label_options()`, `value_label_for(amount)`, `value_label_control()` | `contract_fill_in.py` `HrFormulaRuleValueLabels`; pure parser `parse_value_labels()` |
| Idempotent seed applier `hr.formula.config._pb_apply_usual_answers(spec)` | `contract_fill_in.py` |
| rize seed | `tools/seed_fillin_rize_indonesia.py` |
| VI translations (9 rows: 7 field/selection labels, 1 help, 1 error) | `pb_hr_payroll_formula/i18n/vi_VN.po` |
| Tests (tag `fillin`, 18 cases) | `pb_hr_payroll_formula/tests/test_fillin_p1.py` |
| Versions | `pb_hr_payroll_formula` 19.0.1.163.1, `pb_scheme_map` 19.0.2.5.5 |

Safety rails as built: own savepoint per contract + WARNING with traceback;
never a code the contract already has (lines read AFTER `super()`, FI2); never a
text component, never a non-numeric `value_kind` (identifier/text/date), never a
template whose `value_type` is text; nothing when `known` is False or nobody
pays; **only `state='active'` schemes** give usual answers; only `draft`/`open`
contracts; one indexed pre-check (`_pb_fill_anything_to_fill`) so a database
with no usual answers does no map walk and no flush per contract.

## 2. Tests — T1–T12 (+5 extra cases)

Run on `p0clone` from a scratch addons dir listed first
(`--addons-path=/tmp/fillin_test/addons,/odoo/odoo-server/addons`, the CLEANMAP
precedent: tests before the live deploy), `-u pb_hr_payroll_formula
--test-enable --test-tags /pb_hr_payroll_formula:TestFillInP1,/pb_hr_payroll_formula:TestSchemeCtxP2Scope
--stop-after-init --max-cron-threads=0 --http-port=8199 --gevent-port=8198`.
Log: `/tmp/fillin_test/t1.log` on the box.
Result line: **`0 failed, 0 error(s) of 24 tests`** (18 FILLIN + 6 SCHEMECTX P2).

| # | Case | Result | Evidence |
|---|---|---|---|
| T1 | draft contract → FIFLAG=1, FIMODE=1 `auto`, none for FIZERO/FITEXT; 2 `auto_default` rows, `changed_by` = creator | PASS | log `pb fill-in: 2 lines on contract 5317 for FI Scheme` |
| T2 | `advantages_ids` command with FIFLAG=0 → stays 0, `pb_fill=False`; FIMODE filled; 1 change row | PASS | `pb fill-in: 1 lines on contract 5318` |
| T3 | person nobody pays → contract saves, no lines, no rows | PASS | |
| T4 | `component_scope_for_employee` patched to raise → contract saves, WARNING `pb fill-in: contract <id>` captured by `assertLogs` | PASS | |
| T5 | `write({'amount': 0})` → `pb_fill=False`, `pb_checked_by=uid`, `pb_checked_at` set; other line untouched | PASS | |
| T6 | HR officer (hr.group_hr_user only) → `AccessError`, nothing stamped; payroll manager → 2 stamped, `pb_fill` stays `auto`, 2 `checked` rows by the manager, unchecked empty, second call returns 0 | PASS | |
| T6b | `pb_fillin_check(line_ids=[flag])` stamps only that line | PASS | |
| T7 | import sync, file lacks the column → FIFLAG stays 1 and `auto`, unchecked (FI1) | PASS | |
| T7b | file states the same value (1) → amount 1, mark cleared, checked stamp set | PASS | (new sync branch, decision D4) |
| T7c | file states 0 → amount 0, mark cleared | PASS | |
| T8 | `contract.copy()` → no `pb_checked_*` travels; original keeps its stamps | PASS | see §5 copy fact |
| T8b | import `_create_new_contract_for_components` copy → no lines before the sync | PASS | |
| T9 | `0=No;1=Yes`, three-word mode, spaces + trailing `;` parse; `yes`, `0=No;x=Yes`, `0=;1=Yes`, duplicate value, `=No`, None, `''`, `;;` → `[]`; `value_label_for(1.0)=='Yes'`, `(7)==''`; control toggle/select/'' | PASS | |
| T10 | no scheme → contract, no lines; map line added; `_pb_recompute_paid_by(employee_ids=[e])` → `pb_paid_by_id` set, FIFLAG/FIMODE filled; re-mark stale + recompute → still 2 rows (no double fill) | PASS | `pb fill-in: 2 lines on contract 5314` |
| T11 | `pb_skip_fill_in` → no lines | PASS | |
| T11b | a `close` contract → no lines | PASS | |
| T12 | `_pb_apply_usual_answers` writes FIMODE+FIZERO, reports FINOPE missing, second run writes nothing, contract line count unchanged | PASS | live proof too: §4 second seed run |

**Regression — whole `pb_hr_payroll_formula` + `pb_scheme_map` suites** (same
scratch recipe, `-u pb_hr_payroll_formula,pb_scheme_map`, log
`/tmp/fillin_test/t2.log`): **698 tests, 4 failed, 5 errors — none caused by
this phase.**
* The 4 failures (`TestRd49SyncCost.test_02ab`, `.test_02i` — cron inactive on
  p0clone; `TestRecordsR1OneTime.test_07b`; `TestSchemeCtxCurrency.test_04` —
  degenerate currency fixture) **fail identically on the old code**: baseline
  run from the live addons dir before deploy, `4 failed, 0 error(s) of 32 tests`
  (`/tmp/fillin_test/base.log`).
* The 5 errors are all `TestSchemeMapStaticContract` reading sibling modules'
  files (`pb_payrun_wizard/static/…`, `import_icons.js`) relative to the module
  root — `FileNotFoundError` under `/tmp/fillin_test/addons`. An artefact of the
  scratch dir, not of the code (pb_scheme_map's static files were not changed).

Active scheduled-job counts checked after the three test `-u` runs: p0clone 31,
payobook_template 28, rize 74, payobook 42 — unchanged.

## 3. Deploy evidence

`/odoo/ops/filter_deploy.sh full /tmp/fillin_stage pb_hr_payroll_formula,pb_scheme_map pb_hr_payroll_formula,pb_scheme_map /tmp/fillin-run-20261103220731`,
staged from committed HEAD (`git archive`), staging dir cleaned first. PO files
read back with `PoFileReader` on the box before the deploy (3,970 rows; all 9
new rows load). START/DONE lines written in `/opt/deploy-notes.md`.

| DB | upgrade | errors | jobs before/after | pb_hr_payroll_formula | pb_scheme_map | new columns |
|---|---|---|---|---|---|---|
| p0clone | EXIT=0 | 3* | 31 / 31 | 19.0.1.163.1 | 19.0.2.5.5 | pb_fill, pb_checked_by, pb_checked_at, value_labels |
| payobook_template | EXIT=0 | 3* | 28 / 28 | 19.0.1.163.1 | 19.0.2.5.5 | same |
| rize | EXIT=0 | 3* | 74 / 74 | 19.0.1.163.1 | 19.0.2.5.5 | same |
| payobook | EXIT=0 | 3* | 42 / 42 | 19.0.1.163.1 | 19.0.2.5.5 | same |

\* the known `payroll_analytics … contains null values` schema notices
(country/date_from/date_to), present on every upgrade, unrelated.
Result `OK`; sites warm 200; module trees byte-identical repo vs server
(`pb_hr_payroll_formula` b1b89bddaac9, `pb_scheme_map` a46f96742bd0). abm not
touched.

**Who is affected today:** before the seed, no ACTIVE scheme on any of the four
databases had a non-zero usual answer on a numeric contract component (only
archived rize schemes 3938/3941 did — see FI8), so the deploy changed nothing
for new contracts until the rize seed below.

## 4. rize seed output (`tools/seed_fillin_rize_indonesia.py`, rize only)

```
scheme 7121 'Rize Indonesia Payroll — focused payroll' state=active
contract lines before: count=11061 max(write_date)=2026-10-22 23:06:24.407963
--- before
IDBPJSTKCOVERE   id=33489  default_value=0.0  value_labels=''
IDBPJSHEALCOVE   id=33490  default_value=0.0  value_labels=''
IDERREIMBUBPJS   id=33491  default_value=0.0  value_labels=''
IDTAXALLOWMODE   id=33492  default_value=0.0  value_labels=''
written: ['IDBPJSTKCOVERE', 'IDBPJSHEALCOVE', 'IDERREIMBUBPJS', 'IDTAXALLOWMODE']
--- after
IDBPJSTKCOVERE   id=33489  default_value=1.0  value_labels='0=No;1=Yes'
IDBPJSHEALCOVE   id=33490  default_value=1.0  value_labels='0=No;1=Yes'
IDERREIMBUBPJS   id=33491  default_value=0.0  value_labels='0=No;1=Yes'
IDTAXALLOWMODE   id=33492  default_value=1.0  value_labels='0=None;1=Insurance-premium tax only;2=All tax (net salary)'
contract lines after:  count=11061 max(write_date)=2026-10-22 23:06:24.407963
committed
```
psql afterwards: the four rows as above; `hr_contract_advantage` count 11061,
max(write_date) 2026-10-22 23:06:24.407963 (unchanged); lines with `pb_fill`
set: 0. Second run: `written: nothing (already set)`, counts unchanged.

## 5. Live smoke on rize (shell transaction, ROLLED BACK)

```
before: lines (11061, 2026-10-22 23:06:24.407963) change rows 9177
employee 5285 Aradea Putra Suriya paid by 7121 Rize Indonesia Payroll — focused payroll stale False
existing contracts [(3501, 'close', '2025-10-14', '2026-10-14')]
smoke contract 3649 draft
  line IDBPJSHEALCOVE   amount=1.0 pb_fill=auto checked_at=False words='Yes'
  line IDBPJSTKCOVERE   amount=1.0 pb_fill=auto checked_at=False words='Yes'
  line IDTAXALLOWMODE   amount=1.0 pb_fill=auto checked_at=False words='Insurance-premium tax only'
  change IDTAXALLOWMODE   0.0 -> 1.0 source=auto_default by=Rize notes='Filled in from the usual answer on Rize Indonesia Payroll — focused payroll'
  change IDBPJSHEALCOVE   0.0 -> 1.0 source=auto_default by=Rize notes='…'
  change IDBPJSTKCOVERE   0.0 -> 1.0 source=auto_default by=Rize notes='…'
unchecked ['IDBPJSTKCOVERE', 'IDBPJSHEALCOVE', 'IDTAXALLOWMODE']
after rollback: lines (11061, 2026-10-22 23:06:24.407963) change rows 9177
ROLLED BACK True
```
(5285 has one contract, closed 2026-10-14 — a new draft from 2026-11-01 is the
realistic case. "Pays back" (IDERREIMBUBPJS) usual answer 0 → no line = No, as
designed. `by=Rize` is the shell's system user's display name on this tenant.)

## 6. Facts P2 needs

* **Line fields** (`hr.contract.advantage`): `pb_fill` Selection
  `[('auto', 'Filled in by Payobook')]` (False = a person or a file wrote it),
  `pb_checked_by` m2o res.users, `pb_checked_at` Datetime; all `copy=False`.
  Unchecked = `pb_fill == 'auto' and not pb_checked_at`. A checked fill keeps
  `pb_fill='auto'` with the stamp; a human/file write gives `pb_fill=False` +
  stamp.
* **Rule**: `hr.formula.rule.value_labels` Char; `value_label_options()` →
  `[{'value': float, 'label': str}]`; `value_label_for(amount)` → str or `''`;
  `value_label_control()` → `'toggle'` (labels exactly {0,1}, or `value_kind`
  boolean with no labels) / `'select'` / `''`. Pure parser importable:
  `odoo.addons.pb_hr_payroll_formula.models.contract_fill_in.parse_value_labels`.
* **Contract methods**: `contract.pb_fillin_unchecked()` → recordset of
  `hr.contract.advantage` (callers' rights; a recordset, so an RPC wrapper
  should return ids/rows, not the recordset). `contracts.pb_fillin_check(line_ids=None)`
  → int (lines stamped); `None` = every unchecked line of those contracts,
  a list = only those ids. Writes one `checked` change row per line.
* **Access rule for `pb_fillin_check`** (`_pb_fillin_may_check`): superuser, or
  (admin or `hr.group_hr_user` or `pb_hr_payroll_base.group_payroll_base_officer`)
  AND (`hr_contract.group_hr_contract_manager` or
  `om_hr_payroll.group_hr_payroll_manager`) AND `hr.contract` write ACL; plus
  record-rule `check_access('write')` on the contracts. Refusal = `AccessError`
  "You cannot confirm the answers on a contract. Ask an administrator for the
  right to change contracts." (VI shipped). On p0clone the contract-manager
  group does NOT imply `hr.group_hr_user`; the payroll manager implies both.
* **sudo**: lines and change rows are written with `sudo()` (an HR officer may
  create a contract but has read-only ACL on `hr.contract.advantage`, and the
  change log is create-only for formula managers). `changed_by` is set
  explicitly to the acting user (cron user for trigger b). The scope helper and
  rules are read with sudo.
* **Change sources** on `hr.contract.advantage.change`: `auto_default` ("Filled
  in by Payobook from the scheme's usual answer", notes `Filled in from the usual
  answer on <scheme>`, old 0 → new default, effective date = contract start) and
  `checked` ("Checked, no change", old = new = amount, notes `Checked by <name>,
  no change`).
* **copy()**: the handover's premise does not hold — `advantages_ids` is a
  One2many and is **not** copied by `contract.copy()` (Odoo default
  `copy=False`). A copy goes through `create`, so it is filled like any new
  contract (fresh `auto`, unchecked, no stamps — T8). The import's
  new-contract-for-components copy is created with `pb_skip_fill_in` because the
  sync writes every component on it straight after (T8b).
* **Payload keys added: none.** Adding `pb_fill`/`value_labels` to
  `_cd_comp_row/_cd_virtual_row` means a `pb_contracts` change and deploy;
  left for P2.
* **History tab wording gap (P2 must fix):** `pb_contracts`
  `_cd_change_sentence` (`pb_contract_360.py:1073-1087`) maps any unknown source
  to "From a pay data file", so an `auto_default` or `checked` row currently
  reads "From a pay data file" on the contract panel's History tab. Add the two
  sources there.
* `template_for_rule(rule)` on `hr.contract.advantage.template` (`@api.model`)
  is now the ONE get-or-create by code; `hr.contract.advantage.change.log(...)`
  the one row writer (runs in caller's rights; call `.sudo()` when needed).

## 7. Decisions I made that the handover did not cover

1. **Active schemes only.** Usual answers are read only from `state='active'`
   schemes: archived rize scheme 3938 still carries `LUONGHOPVND` default
   34,802,300 (a salary) and `NGUOIPHUTHUO` 2; 3941 `MEDICALREIMB` 15,000.
2. **Numeric kinds only** (money, decimal, integer, quantity, rate, boolean),
   and never onto a text-typed template.
3. **Cheap pre-check** (one `search_count`) so databases with no usual answers
   pay nothing per contract create; `env.flush_all()` before the map is asked,
   because the map reads teams in raw SQL (FI5).
4. **FI1 completed in the sync**: a new `elif found and line_obj.pb_fill` branch
   in `_sync_contract_components` rewrites the same amount so the write hook
   un-marks it (no change row; nothing changed). Without it, every new contract
   created by a pay data file that states the usual answer would sit in the
   "To check" list forever. This is a small behaviour addition beyond "the write
   hook side effect" — flagging it (T7b).
5. **Import copy not filled** (`pb_skip_fill_in` on the copy in
   `_create_new_contract_for_components`) — see §6 copy fact.
6. **Access mirrors the panel plus the payroll manager** (§6); a bare
   contract-manager without an HR/officer role is refused, as on the panel.
7. **Seed logic as a model method** (`_pb_apply_usual_answers`) so T12 tests the
   very code the script runs; the script carries only the rize spec and the
   before/after proof, and aborts (rollback) if the line fingerprint moves.
8. **Patch bump**: `19.0.1.163.0 → 19.0.1.163.1`, `19.0.2.5.4 → 19.0.2.5.5`.
9. **`log()` runs in the caller's rights** so the import batch's access is
   exactly as before; the fill and the check call it via `sudo()`.

## 8. Deviations from the handover / brief

* **D1 — no announcement to other sessions.** `ListAgents` is not available in
  this agent's toolset, so I could not discover or message the live sessions.
  Mitigation: read `/opt/deploy-notes.md` (no deploy in progress; contractlife
  and f3 learn deploys had finished with `OK`), wrote START/DONE, the script's
  lock was free.
* **D2 — the code commit carries the wrong message.** I staged the FILLIN files
  explicitly; the parallel CONTRACTLIFE SCOPE session ran `git commit` while
  they were staged and they landed in its commit **`ef836533e`
  "docs(handovers): CONTRACTLIFE SCOPE report + screenshots"** (pushed). Content
  is byte-identical to what I tested and deployed. I did not rewrite pushed
  history; the intended message is in this report. (FI6.)
* **D3 — T8 premise** (copy copies lines) is false; tested what is true (§6).
* **D4 — sync branch added** (decision 4).
* Tests were run before the deploy from a scratch addons dir (CLEANMAP
  precedent), not from the live dir.

## 9. Proposed ledger gotchas

**FI4 — `contract.copy()` copies no component lines.** `advantages_ids` is a
One2many (default `copy=False`); a copy goes through `create` and is filled like
a new contract. Any path that copies a contract and then writes its components
itself must pass `pb_skip_fill_in` (the import's
`_create_new_contract_for_components` does).

**FI5 — the scheme map answers in raw SQL.** `pb.scheme.map._departments_for`
reads `hr_version`/`hr_contract` with `cr.execute`, so a team written earlier in
the same transaction is invisible until flushed. The fill flushes first; tests
must `env.flush_all()` before resolving.

**FI6 — a parallel session's bare `git commit` sweeps your staged files.**
Stage and commit in one call (`git commit -m … -- <paths>`), or commit
immediately after `git add`; never leave files staged while waiting on a test.

**FI7 — `TestSchemeMapStaticContract` errors when run from a scratch addons
dir** (it reads sibling modules' static files relative to its own root). Five
`FileNotFoundError`s there are not a regression.

**FI8 — archived schemes keep stale usual answers** (rize 3938: a salary as
`default_value`). Read usual answers from active schemes only.

**FI9 — the History tab calls every unknown change source "From a pay data
file"** (`pb_contract_360._cd_change_sentence`); a new `change_source` needs a
sentence there in the same change.

## 10. Plain-English summary (for the owner)

1. From today, when someone creates a new contract for a Rize Indonesia person, Payobook fills in four answers by itself: BPJS TK covered = Yes, BPJS Health covered = Yes, Tax allowance = "Insurance-premium tax only", and Pays back BPJS = No.
2. Every answer Payobook fills in is marked "Filled in by Payobook, not checked" and logged; if a person or a pay data file changes it, the mark goes away and we record who did it.
3. A manager can now confirm those answers ("Looks right") — the server side is ready; the buttons and screens come in the next phase.
4. No existing contract was changed (11,061 contract lines before and after), and nothing changes for the other companies and schemes, because none of them has a usual answer set.
5. Tested (18 new checks pass), live on all four databases, and tried once on Aradea Putra Suriya without saving — it filled the three answers correctly.
