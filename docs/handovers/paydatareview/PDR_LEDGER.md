# PAYDATA REVIEW (PDR) — conventions and gotcha ledger

Programme opened 2026-11-05 from the owner's screenshots of the Rize Indonesia
pay run, step 2 "Review pay data" (rize scheme **7121 "Rize Indonesia Payroll —
focused payroll"**, preparation **#19**, period 2026-10-01..31, 113 people).
Indonesia is **not live** on rize — every Indonesia run there is a test.

Three complaints, all confirmed live:

1. **Slow.** `open_payroll_review` = 49 s (server log 2026-11-05 01:38:15:
   15,519 queries, 4.9 s SQL, 43.8 s Python).
2. **1,240 false red cells.** "Needs a value" on columns whose blank already
   means 0 / No in every formula.
3. **1 / 0 flags.** Yes/no columns show 1 / 0. We invented them (commit
   `da88ea82b`, 2026-10-14); the client's files never use 1 / 0 and write
   "Yes / No".

| Phase | What it delivers | Handover |
|---|---|---|
| P1 | Speed (open ≤ 10 s, previews stream in), blank = 0 / No for the 11 columns, final-tax-month reminder | `PDR_P1.md` |
| P2 | Y / N everywhere a user sees (worksheet, pickers, pay data file, contract panel already done), Tax allowance mode words — LIVE 2026-11-05 | `PDR_P2.md`, `PDR_P2_REPORT.md` |

## Owner rulings 2026-11-05 (asked once — do NOT re-ask)

- **R1** Blank counts as 0 / No for the 10 period columns (Final tax period,
  Prior YTD taxable gross, Prior YTD deductible JHT and JP, Job expense eligible
  months, Prior YTD PPh21 withheld, Prior qualifying severance paid, Prior
  severance tax withheld, Approved final-period tax allowance, Final-period YTD
  reviewed, Severance eligibility confirmed) and for **Employer reimburses
  employee BPJS**, **plus a reminder** in a person's final tax month (December,
  or the month they leave). The reminder never blocks.
- **R2** Y / N on every screen and in the pay data file (file still accepts
  1 / 0). **1 / 0 stays stored and in the formulas.** Columns: BPJS TK covered,
  BPJS health covered, Employer reimburses employee BPJS, Final tax period,
  Final-period YTD reviewed, Severance eligibility confirmed.
- **R3** Tax allowance mode words: **None · Insurance tax · All tax**, with a
  one-line hint ("All tax = the company pays all the employee's tax (net
  salary)"). Values 0 / 1 / 2 unchanged.
- **R4** Phased: Fable designs, Opus builds and self-reviews, same session.
- BPJS TK covered / BPJS health covered keep being required: their usual answer
  is Yes, so a missing contract line is a real problem (1 person on rize today).

## 0. Binding rules for every phase

1. **Never "Odoo" in any user-visible string** (labels, help, errors, chips,
   tooltips, `.po` msgstr). Use "Payobook" / "the system". Technical names stay
   in code, comments, commits and these docs. White-label tenants (rize) must
   not show "Payobook" either where a seam already swaps it.
2. **Plain English on screen.** Words on the screen, never codes
   (`IDFINALTAXPERI`, `period.input.*`, "provenance").
3. **Design bar is binding, verbatim from the owner: "extreme WOW, best in
   class".** Lucide icons, never emoji. Locked palette, light-tint hero, no
   gradients. Grey at zero, colour only when there is something to act on.
4. **Deploy contract = repo `CLAUDE.md`** (one addons dir, clean staging dir,
   per-module scoped `rsync --delete`, never `--delete` into the addons root,
   never deploy vendored standard addons, verify hash + `latest_version` on all
   four DBs: `payobook`, `payobook_template`, `p0clone`, `rize`). **Never
   `abm`.** Stage from `git archive HEAD` (as every other session does), use
   `tools/filter_deploy.sh`, read and append `/opt/deploy-notes.md`
   (START / DONE lines, same format as the existing ones). Purge
   `/web/assets/%` and bump `web.assets.version` per DB after JS/SCSS.
5. **Commit per feature, stage files explicitly** (other sessions have
   uncommitted work in this tree — `pb_clock/`, `pb_orgchart/`,
   `pb_hr_workforce/`, `pb_hr_payroll_formula/models/column_role_classifier.py`).
   Never `git add .`/`-A`. Push `19.1` after each verified commit. Scan for
   passwords before committing. Never commit `RIZE/`, `outputs/`, client names.
6. **Usage limit:** at 97 % or any 429, commit WIP with "PAUSED" in the
   message and stop with a report of where you are.
7. **Browser validation is mandatory** before calling any screen done (Chrome
   MCP, screenshot + console). Never save cells on the owner's live
   preparation #19 — read-only checks there; edits only on a throwaway copy.
8. The test-only demo rule: no "RIZE" in demo records; never delete demo data
   on payobook.

## 1. Verified plumbing (do not re-derive)

### Worksheet
* Client: `pb_payrun_wizard/static/src/js/payroll_review.js` (185 lines) +
  `static/src/xml/payroll_review.xml`. Open = `orm.call('pb.payrun.wizard',
  'open_payroll_review', [payload])` (js:22); saves call
  `hr.payroll.preparation` methods with `[id, revision, ...]` (js:101).
* Server entry: `pb_payrun_wizard/models/application_payroll_wizard.py:61`
  `open_payroll_review` → `hr.payroll.preparation._open()` → `.workspace()`.
* Model: `pb_hr_payroll_formula/models/payroll_preparation.py`.
  - `workspace()` :239 — builds columns, calls `_resolved()` (:225) → `_raw()`
    (:156) which calls `config._application_employee_inputs(e, …)` **once per
    person** (:168). Then for each person a formula preview via
    `hr.formula.sample.data.new(...)._evaluate_rules_with_dependencies(...,
    readonly=True)` (:281-283) — **only when the row has no issue** (:277).
  - `ready` (:307) calls `self._resolved(True)` a second time when
    `state == 'reviewed'`.
  - `save_cells` (:313) and `review` (:438) both end in `self.workspace()`, so
    every saved cell rebuilds the whole worksheet.
  - Red cell rule (:264-266): `issue = conflict or (missing and required and
    not optional)`. `optional` = `_optional(rule)` (:112) or
    `_settlement_zero(rule)` or `cell['not_applicable']`.
  - `_optional` (:112): `_optional_record_input(rule)` OR (`application_source_key
    == 'period.input.'+code` AND `application_zero_allowed` AND numeric kind AND
    settlement `none` AND not a contract component).
* `pb_hr_payroll_formula/models/application_payroll_source.py`
  - `_optional_record_input` :25 — no source key, not `is_required`, not
    `application_source_required`, numeric/text.
  - `_application_settings_stamp` :195 — hashes the scheme + every rule's
    write_date. Called once per person today (:640).
  - `_application_time_values` :216 — two `calendar.get_work_hours_count`
    calls **per day per person** (:232-233); 7,006 calls for 113 people.
  - `_application_dependency_usage` :453 — walks the pay formulas'
    dependency closure; called twice per person (:563 and via
    `_application_refresh_input_requirements` :504). 0.39 s per call on rize.
    The second call's answer depends only on the values of refs that appear in
    `IF(ref = literal, …)` predicates (`_application_branches` :53).
  - `_application_refresh_input_requirements` :501 — sets `required`,
    `not_applicable`, blockers, and writes optional blanks as 0 / '' into
    `row['values']` with provenance `src: optional_blank` (:522-527).
  - `_application_employee_inputs` :534 — non-key inputs (contract components
    like `IDERREIMBUBPJS`) are `missing` unless the legacy resolver sourced
    them (:595-600). Contract lines live in `hr_contract_advantage`
    (`amount`, `text_value`, `pb_fill`, `pb_checked_*`).
* Formula preview / compute engine:
  - `pb_hr_payroll_formula/models/formula_sample_data.py:597`
    `_evaluate_rules_with_dependencies` (worksheet preview, Studio).
  - `pb_hr_payroll_formula/models/hr_payslip_formula.py:235` — the payslip
    twin. **Application-mode payslips (Rize Indonesia) run it with
    `readonly=True`** (:244), i.e. the same `_run_formula` path.
  - Both: topological sort, then every rule, then up to 2 more full passes.
  - `formula_rule.py:2312` `_run_formula` — per formula, per call: rebuilds
    `column_map` over all scheme rules, re-converts Excel → Python
    (`_convert_excel_to_python` :1067), coerces **every** value, runs a
    debug-only substring loop over every value (:2389) regardless of log level,
    `assert_safe_expression`, then `eval` of the source string.
  - Measured 2026-11-05: **8.77 s per person** for scheme 7121 (409 rules).
* biz_access: `biz_access/models/studio_policy.py:247` — a Python
  `__getattribute__` on `base` runs on every attribute access of every record
  (24.9 M calls during one worksheet open under the profiler). It only does
  work for fields in `RESOURCES`; the cost is the Python-level hook itself.
* Request-scoped memo precedent: `self.env.cr.cache` (a dict cleared when the
  cursor closes; `odoo/sql_db.py:170, 534`). Used by
  `pb_attendance_flow/models/attendance_cockpit.py:284`,
  `pb_approval_config/models/inbox_facade.py:249`. Namespace keys as tuples
  starting with the module name.

### rize data (2026-11-05)
* Indonesia schemes on rize: 7121 (active, focused payroll), 7116 (draft
  "application sources 2026-10-21"), 7096 (archived master-data). No other DB
  has Indonesia schemes (`payobook` only has `Viet Retail` 18).
* On 7121 the 10 period columns are `is_required = t`,
  `application_zero_allowed = f`, settlement `none`, keys
  `period.input.<CODE>`. Bonus / THR / Incentive etc. already have
  `application_zero_allowed = t` (that is the "1849 blank cells" line).
* Flags on 7121 (`value_kind integer`, contract components, `is_required t`):
  `IDBPJSTKCOVERE` AX default 1, `IDBPJSHEALCOVE` AY default 1,
  `IDERREIMBUBPJS` AZ default 0, `IDTAXALLOWMODE` BA default 1; value_labels
  `0=No;1=Yes` (×3) and `0=None;1=Insurance-premium tax only;2=All tax (net
  salary)`. FILLIN D2: **No = no contract line**, so 109 of 113 people have no
  Reimburse line.
* Red cells by column on prep #19: IDERREIMBUBPJS 109; IDFINALTAXPERI,
  IDPRIORYTDTAXA, IDPRIOYTDJHTJP, IDJOBEXPENELIG, IDPRIOYTDPPH21,
  IDPRIOQUALSEVE, IDPRIORSEVETAX, IDFINALALLOW, IDYTDREVIEW, IDSEVELIG 113
  each; IDBPJSTKCOVERE 1 (real).
* Formulas reading them (blank = 0 is safe in all): `IDTAXALLOWREGU` (M),
  `PIT` (AN), `IDANNUATAXAPKP` (BH), `IDSEVERANCETAX` (AO), `IDBPJSALLOW` (N),
  `IDGROSSUPRESID` (BS), `IDLEAVBALAPAID` (O), and the scheme's own check
  `IDREADY` (NH) which already says "Review final-period YTD" when Final tax
  period = 1 and YTD reviewed ≠ 1.

## 2. Gotchas (append as found)

* **G1 — paused WIP in HEAD.** Commit `503279518` "WIP (PAUSED): import Gender
  / Marital Status…" (IMPORT-GENDER, another session) bumped
  `pb_hr_payroll_formula` to `19.0.1.163.2` and changed
  `models/payroll_import_batch.py`; its test file was **not yet run** and it is
  **not deployed** (live = 163.1). Any deploy of `pb_hr_payroll_formula` from
  HEAD ships it. Read `docs/handovers/orgchart/IMPORT_GENDER_FIX_REPORT.md`
  first; see P1 §6 for the rule.
* **G2 — profiler inflates ~3.4×.** 49 s live became 167 s under cProfile.
  Judge speed by the werkzeug log line (`… 200 - <queries> <sql s> <other s>`)
  or by wall clock in a shell **without** the profiler.
* **G3 — `odoo-bin shell` on this 2-core box** is slow (prep #19 `_raw()` took
  105 s in a shell vs 49 s served). Always `env.cr.rollback()` at the end;
  never restart the service while a shell is alive (boot can hang — see
  payobook-deploy memory). Prefer a throwaway DB copy for anything that writes.
* **G4 — preparations are per user.** Prep #19 belongs to uid 2 (the owner).
  Opening the worksheet as the owner reuses it; saving a cell there changes
  the owner's real draft. Read-only only.
* **G5 — the preview never ran on rize Indonesia.** Every row had an issue, so
  `workspace()` skipped `_evaluate_rules_with_dependencies`. Remove the issues
  and it runs for all 113 rows: **≈ 16 minutes** at today's 8.77 s/row. The
  speed work and R1 must ship together.
* **G6 — `_cell_stamp`** hashes value/status/sources/evidence. Changing how a
  cell resolves changes its stamp, so a saved correction on that cell turns
  into "The source changed…". Open Indonesia preps #18 and #19 have no saved
  corrections (revision 1), so nothing breaks today.
* **G7 — the worksheet no longer computes previews (P1 S3).** `workspace()`
  returns result cells with `value: None` and `preview: 'pending'|'blocked'`;
  the numbers come from `hr.payroll.preparation.preview_rows(revision, ids)`
  (≤ 25 people, owner only, stale revision refused). Any test or tool that
  read result values out of `workspace()` must call `preview_rows` instead
  (4 existing tests were migrated in P1).
* **G8 — request memo.** `config._application_memo()` (D4) is the ONLY cache.
  It lives in `env.cr.cache[('pb_hr_payroll_formula.app_memo', config_id)]`
  plus `('pb_hr_payroll_formula.access_memo',)`, is removed by the context
  manager that installed it, and is emptied by any `hr.formula.rule`
  create/write/unlink or `hr.formula.config` write. Something new that is
  scheme-level and read per person: put it behind `_application_memoize`.
  Something that depends on a person's records: never memoise across people.
* **G9 — timing on the shared 2-core box is noisy.** The same served open on
  the throwaway copy measured 13.1 s and 22.3 s an hour apart (another
  session's deploy running). The profiler inflates the new code ~4.7× (G2 was
  3.4× on the old code). Judge by the live werkzeug line, quiet box.
* **G10 — a served harness on a copy:** `odoo-bin … -d <copy> --db-filter=^<copy>$
  --http-port=8195 --workers=0`, started with `setsid -f` from a root script
  (a `nohup … &` inside `ssh '…'` dies with the ssh session). Stop it by the
  PID that `ss -ltnp` shows on the port — `pkill -f "http-port=8195"` inside
  `ssh '…'` kills your own shell (exit 255; same family as orgchart G48).
* **G11 — a copy goes stale against the live tree.** pdr_test (copied 04:48)
  could not load the live addons at 07:15 because CLOCK-2 had added
  `res.company.pb_clock_*` columns since. `-u <that module>` on the copy first.
* **G12 — `/etc/odoo-server.conf` sets a logfile.** A test run without
  `--logfile=…` writes its results into `/var/log/odoo/odoo-server.log`,
  not your redirect; and a scratch dir the `odoo` user writes into must be
  `chmod a+w`.
* **G13 — real final-tax-month people exist in October.** On rize prep #19,
  7 people already have a contract end (or approved last day) inside
  Oct 2026, so the reminder shows on the live October worksheet; no December
  copy is needed to see it.
* **G14 — the worksheet payload is opt-in light (P2).** The browser sends
  `context={'pr_compact': True}` on every call that returns `workspace()`
  (open, save_cells, review, submit). Light cells carry only truthy flags,
  `value`, `tone`, a cell-specific `reason` and a trimmed `edit`; name, owner,
  rule id and words live on the **column**. Python callers and tests get the
  full shape. Any new JS call that returns a worksheet must pass the same
  context, and any new per-cell field must be added to `_compact_cell`.
* **G15 — only the rows in view are drawn.** The grid DOM holds ~25 of 113
  rows. Code that looks a cell up by `[data-cell=…]` must bring its row into
  the window first (`revealCell`). Row height is measured from the first drawn
  row (62.5 px today), so a row taller than the others would drift the
  spacers — keep row content on fixed lines.
* **G16 — a selected cell shows `state.value`, not the cell.** After a paste or
  any refresh, `accept()` must reset `state.value` from the server when nothing
  is pending (found in the browser: a pasted "No" still read "Yes").
* **G17 — rize Indonesia contracts have no HR Responsible.** All 103 contracts
  of preparation #19 lack it, so the full contract form refuses every save
  ("Complete the required fields: HR Responsible"). Owner data item; test
  contract-form edits on a copy after filling it.
* **G18 — a save reference is 8–100 characters.** `save_cells` refuses a
  shorter `mutation`; test references like `'p2-t2-1'` fail with "Save up to
  500 cells at a time with a unique save reference."
* **G19 — words that name 0 switch on P1's "usual answer".** `_application_usual_no`
  fires for any numeric contract component with usual value 0 whose words name
  0. Adding words to such a rule (7116 / 7096 Tax allowance mode) turns a
  missing line from red into "usual answer". Check `default_value` before
  adding words to a contract component.
* **G20 — `value_label_for('')` used to read "No"** (`float('' or 0)`); a blank
  now reads `''`. Display code must still treat `None` / `''` as blank before
  asking for a word (`value_to_text` does).
* **G21 — a monthly file round trip is not "zero changes" on rize.** The file
  pre-fills Paid days / Period days suggestions the month has not saved yet,
  so re-uploading an untouched download proposes 226 changes there. Judge a
  round trip by the columns you changed.
* **G22 — `pb_contracts` now inherits the full contract form (P3).** Before P3
  it only inherited the history form; the form-level home is
  `pb_contracts/views/hr_contract_form_views.xml`
  (`hr_contract_view_form_pb_hr_responsible_optional`). HR Responsible is
  optional there on every database (owner ruling 2026-11-05); G17 no longer
  blocks contract-form tests on rize.
* **G23 — a fifth tenant, `sudima`, exists since 2026-11-05 13:21 UTC** (cloned
  from payobook_template by another session). It is not in the four-database
  deploy set, so a `-u` there is not automatic: after any deploy its files are
  new but its `latest_version` is old (views/data not loaded). Ask before
  adding it to `DBS`.
* **G24 — a pay package line keeps no component code.** The only trace is the
  note the build writes ("… (CODE)."). Counting lines by origin = parse the
  note, then find the rule with the panel's preference.
* **G25 — a fresh DB copy can get a live connection.** The main service holds a
  session on a new copy within minutes (dbfilter `^%d$`); `dropdb` refuses —
  use `dropdb --force`.
* **G26 — F2 trusts the rule's value type.** A count marked `money` with no words
  (payobook `NPT` = number of dependants) still becomes an earning line. Fix the
  rule, not the package code.
* **G27 — clearing an HTML field in the form stores `<div …><br></div>`, not
  NULL.** Add-then-clear browser checks leave that behind; harmless on screen.
