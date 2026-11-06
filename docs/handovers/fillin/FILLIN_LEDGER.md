# FILLIN — conventions and gotcha ledger

Programme opened 2026-11-04 from a Rize client question ("is BPJS TK covered an
amount or an ID number?") and the owner's follow-up: *how do the BPJS / tax
flags get their value on a NEW employee, can they be changed on the contract,
and give me a way to review the defaults you add on my behalf.*

Three findings, two phases:

| Phase | What it delivers | Handover |
|---|---|---|
| P1 | **Server.** A new contract starts with the paying scheme's *usual answers* (rule `default_value`); every line Payobook fills in is marked and logged; a human edit un-marks it; "Looks right" checks it; rules can carry *words for each value*; rize Indonesia seeded (TK Yes, Health Yes, Pays back No, Tax allowance mode 1). | `FILLIN_P1.md` |
| P2 | **Screens.** Contract panel shows Yes/No and words, and "Filled by Payobook · not checked" with *Looks right*; Contracts board gets a **To check** view with the answers on the card; employee panel chip; pay run advisory + wizard count; studio shows "Usual answer for a new contract" and the words. | `FILLIN_P2.md` (written after the P1 report) |

Owner rulings 2026-11-04, asked once, do not re-ask:
1. A new contract is **filled in** with the usual answers (not left empty).
2. Flags show as **Yes/No and words**, never "Rp1" / "Rp0".
3. The owner wants a **review mechanism** for everything Payobook fills in by itself — a human must be able to see it, confirm it, or change it, and the pay run must say when nobody has.
4. Workflow: **phased, Fable designs, Opus builds**, same session.

## 0. Binding rules for every phase

Read `docs/handovers/SCHEMECTX_LEDGER.md` §0 first; its rules bind here
**verbatim**, with these updates:

1. **Plain English on screen, never "Odoo"** in any user-visible string
   (labels, help, errors, chips, tooltips, `.po` msgstr). Technical names stay
   in code, comments, commits and these docs.
2. **Design bar is binding**: extreme WOW, best in class, Lucide icons via the
   module's `ic()` helper, never emoji. Grey at zero, colour only when there is
   something to do (quiet board pattern).
3. **Browser validation is mandatory** for any screen change: open it on
   `rize.payobook.com` with Chrome MCP, read the console, screenshot.
   `rize` is the validation tenant (the owner cleared it). No login is written
   anywhere; if no session is open, say so in the report.
4. **Deploy set is FOUR databases and no other**: `payobook`,
   `payobook_template`, `p0clone`, `rize`. **Never `abm`.** One addons
   directory: `/odoo/odoo-server/addons`. Use `/odoo/ops/filter_deploy.sh`
   (`full` for Python/XML/manifest, `looks` for JS/SCSS/XML-template only),
   launched detached with `systemd-run`, result file polled. Write the
   START/DONE lines in `/opt/deploy-notes.md`. Announce the deploy to the other
   live sessions (`ListAgents` → `SendMessage`) before starting.
5. **Tests**: Python unit tests live in `pb_hr_payroll_formula/tests/` (see the
   existing `test_records_r5_record_rung.py` for the fixture style). Run on
   `p0clone` with the SCHEMECTX recipe (alternate ports, scoped `-u`); report
   each numbered case with evidence. Never `--test-tags` without `-u`.
6. **Commit per feature** on branch `19.1`, scan the diff for secrets first,
   push. Commit message ends with the attribution line given in the session.
7. **Never edit `pb_formula_studio/models/pb_formula_studio.py`**; extend with
   `_inherit`. Its XML/JS may be edited.
8. **A read RPC never writes.**
9. **Never recreate the old fan-out.** A new contract gets a line ONLY for a
   rule of the scheme that pays the person, ONLY when that rule's usual answer
   is non-empty, and ONLY for a code the contract does not already have
   (`om_hr_payroll/models/hr_contract.py:117-140` explains why the fan-out was
   removed; SCHEMECTX ledger rule 10(b)).
10. **Filling in must never block creating a contract.** Wrap the fill in its
    own try/except, log at WARNING with the traceback, and let the contract
    save.

## 1. Verified facts — do NOT re-derive

### Where a flag lives
* A per-contract value is an `hr.contract.advantage` line: `contract_id`,
  `advantage_template_id`, `amount`, `text_value`
  (`om_hr_payroll/models/hr_contract.py:24`, typed in
  `pb_hr_payroll_formula/models/contract_advantage_typed.py:28`).
* The catalogue `hr.contract.advantage.template` (`code`, `name`,
  `default_value`, `value_type` amount/text) is FLAT and shared across schemes
  (`om_hr_payroll/models/hr_contract.py:143-152`). **Its `default_value` is
  NOT the usual answer** — it is used only when a line is added by hand with
  no amount (`pb_contracts/models/pb_contract_360.py:1424`).
* The usual answer is the **scheme rule's** `hr.formula.rule.default_value`
  (`pb_hr_payroll_formula/models/formula_rule.py:558`), because components are
  scoped by scheme (SCHEMECTX P2). `is_contract_component :673`,
  `is_text_component :787`, `value_kind` Selection `:807-823` (money, decimal,
  integer, quantity, rate, identifier, text, date, boolean), `value_kind_source`
  `:847`.
* A missing line resolves to 0 at compute time:
  `pb_hr_payroll_formula/models/payroll_import_batch.py:4743-4752`
  (`contract_component` when a line exists, `contract_component_default` → 0.0
  when not). The template default is never consulted there.
* `normalize_input_value` `:4299-4335`: a numeric kind with an empty cell
  returns `rule.default_value`; a boolean kind returns a bool.

### Who pays a person (the scheme)
* `hr.employee.pb_paid_by_id` (+ `_advance_id`, `_rung`, `_stale`) —
  `pb_scheme_map/models/hr_employee.py:47-60`; bulk recompute
  `_pb_recompute_paid_by :116`; `hr.contract.write` marks stale on
  `department_id`/`state` change `:209-222` (no `create` override).
* Resolver `pb.scheme.map.resolve / resolve_many`
  (`pb_scheme_map/models/pb_scheme_map.py:274, 339`), order `:18-41`: work
  segment → team → parent teams → division → employee rule → the company's
  only active scheme → nobody.
* **The helper to call at contract creation**:
  `hr.formula.config.schemes_for_employee(employee)` and
  `component_scope_for_employee(employee)`
  (`pb_hr_payroll_formula/models/scheme_component_scope.py:65, 173`) — resolves
  live when the stored answer is stale or empty, returns `{known, schemes,
  codes}`; codes = rules with `is_contract_component` or `is_text_component`
  (`:155-158`).
* Dependency direction: `pb_scheme_map` depends on `pb_hr_payroll_formula`
  (`pb_scheme_map/__manifest__.py:45`). So the fill-in lives in
  `pb_hr_payroll_formula`; a hook that needs `pb_paid_by_id` lives in
  `pb_scheme_map`.
* rize today: 241 active people, 16 with no "Paid by", 3 stale.

### Every place a contract is created (all must get the defaults)
* New contract button → `pb_contract_wizard` → `create_contract`
  (`pb_people_advanced/models/people_wizards.py:154, 198`) via a
  `pb.newhire.proposal` approval.
* Pay data file import → `_create_contract`
  (`payroll_import_batch.py:1822, 1881`) then `_sync_contract_components`
  `:5286`. The sync covers only the batch's scheme rules `:5210`; for a code
  NOT in the file with an existing line it keeps the line's amount
  (`:5350-5356` builds `new_value` from `existing_line.amount`); for a code not
  in the file with NO line it creates 0.0 as `import_default` `:5380`.
  Template get-or-create helper `_get_or_create_advantage_template(rule,
  cache)` `:5215` (instance method on the batch; the fill-in needs its own
  copy — same search-by-code, same `value_type` choice).
* Hiring offer closure `pb_hiring/models/offer_closure.py:306`; demo seeder
  `pb_demo_seed/seeds/people.py:356-365, 400`; `pb_demo/models/demo_employees.py:133, 224`;
  Zoho/legacy importers (`om_hr_payroll/models/hr_zoho.py:462`, etc.).
* **One `create` override on `hr.contract` catches all of them.**

### Change log and provenance
* `hr.contract.advantage.change` (`pb_hr_payroll_formula/models/contract_component_change.py:49-60`):
  `change_source` import / import_default / manual, `changed_by`, `changed_at`,
  `import_batch_id`. The contract panel's History tab reads it
  (`pb_contract_360.py:1073-1087` sentences). Nothing today records
  "filled automatically, nobody checked".

### Contract panel (pb_contracts)
* Components tab rows: `_cd_components :900`, stored line `_cd_comp_row :802`,
  virtual (no line yet) `_cd_virtual_row :844`, scope `_cd_scope :773`
  (scoped / unassigned / off). `value_kind` is already in the payload
  (`:832, :882`) but **nothing reads it**: `compEntry`
  (`static/src/js/contract_360.js:862`) hard-codes kind `money`/`text` — that
  is the "Rp1".
* `CdEditor` kinds `:342-346`: money, number, integer, text, date, **select**,
  **toggle**, m2o; select/toggle take `options`. Used today only by the YES/NO
  contract fields `tupart`/`shuipart` (`pb_contract_360.py:110-111, 718`).
* Row tags: `fills_label` (where the value comes from, `_FILLS :130-199`),
  `requires_new_contract`, and `virtual` → "not filled in yet"
  (`static/src/xml/contract_360.xml:137-140`).
* Save: `save_contract_360 :1562`, judged by `_cd_judge_components :1298`,
  writes `:1613-1663`, logs via `_cd_log_component :1798` as `manual`.

### Boards and checks
* Contracts board views `_pbf_builtin_views` (`pb_contracts/models/pb_contracts.py:223-231`);
  card row `_contract_row :234`; filter spec `_pbf_spec :171-190`.
* Employee panel chip seam: registry `pb_employee_360_chips`, cloned from
  `pb_scheme_map/static/src/js/scheme_map_chip.js` (silent ORM call, tooltip
  for the "why").
* Pay run checklist `_run_checks` (`pb_payruns/models/pb_payruns.py:2340`),
  entries `{key, tone, icon, text, detail, owner, next, advisory}`; rose = not
  ready, amber advisory does not block; fed at `:547-551` (`unsourced` is the
  precedent). Wizard `scheme_preview` (`pb_payrun_wizard/models/pb_payrun_wizard.py:543-569`)
  rendered at `static/src/xml/payrun_wizard.xml:86-103`.
* Studio component editor: "Default value" number input
  `pb_formula_studio/static/src/xml/studio.xml:1299-1300`; draft fields saved
  through `setDraftField`; rule read-back includes `default_value`
  (`pb_formula_studio.py:2602, 2630`).

### rize Indonesia
* Active scheme **7121 "Rize Indonesia Payroll — focused payroll"** (ID);
  7116 draft, 7096/3943 archived. The four flag rules on 7121: `IDBPJSTKCOVERE`
  (AX), `IDBPJSHEALCOVE` (AY), `IDERREIMBUBPJS` (AZ), `IDTAXALLOWMODE` (BA) —
  all `value_kind=integer`, `value_kind_source=user`, `default_value=0`.
* Current lines: TK 121/121 = 1, Health 121/121 = 1, Tax mode 117/121 = 1,
  Reimburses 4 lines all = 1 (everyone else has no line = No).
* The August client file is the source of those values; Arief Andani Hidayat
  (ID27) is TK = No because the file says "BPJS Manpower deactivated start from
  Aug-26".

## 2. Design decisions (binding)

**D1 — the usual answer is the scheme rule's `default_value`.** Not the
template's. One scheme = one country = one set of usual answers. Changing a
usual answer later never touches existing contracts.

**D2 — a line is filled in only when the usual answer is non-empty** (a number
≠ 0; text rules have no usual answer and are skipped). "No" is the absence of
a line, exactly as the engine already treats it. The review surfaces therefore
list what WAS filled in, and the contract panel shows the rest as "not filled
in yet".

**D3 — marking.** New fields on `hr.contract.advantage`:
`pb_fill` Selection `[('auto', 'Filled in by Payobook')]` (False = a person or
a file wrote it), `pb_checked_by` (res.users), `pb_checked_at` (Datetime).
Unchecked = `pb_fill='auto' and not pb_checked_at`. A human write to
`amount`/`text_value` (drawer save, Records Desk, import with a found value)
**clears `pb_fill`** and stamps `pb_checked_*` with the writer. "Looks right"
keeps `pb_fill='auto'` and stamps `pb_checked_*`. The change log gains
`change_source='auto_default'` ("Filled in by Payobook from the scheme's usual
answer") and `'checked'` ("Checked by <name>, no change").

**D4 — words for each value, engine-safe.** New `hr.formula.rule.value_labels`
Char, format `0=No;1=Yes` or `0=None;1=Insurance-premium tax only;2=All tax
(net salary)`. Parsed by a helper to `[{value, label}]`. **The engine, the pay
data file and the formulas keep seeing numbers**; only display layers read the
words. A rule whose labels are exactly {0,1} (or whose `value_kind` is
`boolean`) renders as a Yes/No toggle; any other label set renders as a
pick-list. We do NOT retype the four rules to `boolean` — `NUMERIC_KINDS`
handling of a bool at `normalize_input_value` is a different code path and the
guard formula `IF(OR(AX2<0,AX2>1…` expects numbers.

**D5 — two fill triggers.** (a) `hr.contract.create` (all creators). (b) The
moment "Paid by" becomes known for a person who had none (recompute in
`pb_scheme_map`): fill their draft/running contracts' missing codes. Neither
ever overwrites an existing line.

**D6 — review surfaces (P2).** Contract panel (per line tag + per contract
"All correct"), Contracts board **To check** view (answers as chips on the card,
"Looks right" / "Change" per card, "All N look right" with a confirm that
states the count), employee panel chip, pay run advisory line + wizard count.
"Looks right" needs the same right as editing the contract.

## 3. Gotchas (append as FI<n>)

**FI1 — the pay data file is a human source.** A value found in the file
replaces a filled-in answer and un-marks it; a column absent from the file must
leave the filled-in line alone (`payroll_import_batch.py:5350-5356` already
keeps an existing amount — verify with test T7, never assume).

**FI2 — `advantages_ids` commands in `create` vals.** The seeder and some
importers pass lines inside the contract's create vals. After `super()` those
lines exist, so the fill must read `contract.advantages_ids` AFTER super and
skip their codes.

**FI3 — scope can be unknown at create.** A contract created before the
employee has a team or before the map covers them resolves `known=False`.
Fill nothing, raise nothing; trigger (b) catches it later.

<!-- FI4–FI9 taken verbatim from FILLIN_P1_REPORT.md §9 (2026-11-04) -->

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


**FI10 — a pay data file that states the same value Payobook filled in CONFIRMS the line** (P1 deviation 4, accepted by Fable): the import sync stamps `pb_checked_*` and clears `pb_fill` when the file value equals the filled-in value, so file-confirmed answers never sit in "not checked" forever.

**FI11 — P1 code landed in commit `ef836533e`** (the parallel CONTRACTLIFE report commit swept its staged files, FI6). History was not rewritten; the P1 report carries the intended message.

<!-- FI12–FI15 taken verbatim from FILLIN_P2_REPORT.md §7 (2026-11-04) -->

**FI12 — the brand rewrite renames "Payobook" in these strings.** On a tenant
with a brand (rize) every "Filled in by Payobook" reads "Filled in by Rize",
in Python and JS strings alike. Screenshots and tests must expect the tenant
brand; never hard-code "Payobook" in a test assertion that runs on a tenant.

**FI13 — on rize an HR officer cannot read contracts without "Records desk —
view".** `hr.group_hr_user` alone gets an AccessError on `hr.contract`; rights
tests there need that group too.

**FI14 — the New contract dialog says "No contract exists yet" even when the
route applied at once** (NEW00001 applied in the same call and contract 3650
exists). Not a FILLIN bug; worth a look in `pb_people_advanced` contract wizard.
Also: the Contracts board's own "New contract" button opens the wizard with
no employee (no person field) — only the employee page's button works.

**FI15 — pb_payruns is shared with the PAY RUN SCREEN session**: commit only
your hunk (blob on HEAD + `update-index`), never `git add` the whole file, and
bump the manifest past HEAD right before committing.

