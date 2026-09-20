# RUNSRC — ledger

**Programme**: the pay run becomes a *source*. Two strands:

* **Strand 1 (Phase A)** — the Spreadsheet board's left column shows one card
  per real column again, and stops inventing 85% suggestions from bare column
  letters.
* **Strand 2 (Phases B, C)** — the run's own period start, period end and
  **standard working days** become values every scheme can read, with standard
  working days editable on the guided pay-data wizard so a holiday month can be
  set to 20 without touching the file.

Owner decisions taken 2026-09-18, before any code:

* **Phased Fable/Opus workflow**, run back-to-back in one session.
* **Standard working days defaults to the Mon–Fri count of the period.** Not a
  holiday-calendar subtraction (only as good as a list nobody maintains), not a
  per-scheme constant. The user adjusts it on the run.

Every handover in this programme references THIS file. Append new gotchas as
**RS<n>**, one ledger for the whole stream, never a second file.

---

## 0. Binding rules for every phase

1. **Plain English on every user-visible string.** Never the word "Odoo" in
   anything a user can see — label, help, placeholder, toast, error, `.po`
   msgstr. Technical identifiers (`from odoo import …`, model/XML ids,
   `odoo-bin`, addon names, log lines, code comments, this document) are
   untouched. Use "Payobook", the product, or a neutral phrase.
2. **The design bar is binding**: extreme WOW, intuitive, out-of-this-world,
   best in class. Hero moment, zero dead-ends, plain language, purposeful
   motion, bulk ergonomics. Lucide icons via the kit's `ic()` registry, never
   emoji. Validate in Chrome MCP and read the console.
3. **Browser validation is mandatory.** A green test suite is not a done UI.
   Open the screen, read the console, take the shot.
4. **Commit per feature.** Explicit file staging, reviewer-focused message.
   Do not batch phases into one commit. Do not push.
5. **Deploy contract — ONE addons directory.** Everything goes to
   `/odoo/odoo-server/addons`. Never `--delete` into that directory itself;
   `--delete` is correct only scoped to one module's own subdirectory. Clean
   the staging dir first. Upgrade **every** database and compare each manifest
   version against `ir_module_module.latest_version` per DB. **Six databases,
   listed below — the "four databases" wording elsewhere in this repo is
   stale.**

   **The database list, corrected by Phase B 2026-09-18 — there are SIX, and
   `acme` is gone**: `payobook`, `abm`, `payobook_template`, `rize`, `rztest`,
   `p9clone`. Earlier documents in this programme say four; they are wrong.
   `rztest` is a real-data clone of `rize` and is the right place to run a
   test suite that must not touch a customer's live scheme.
6. **Run the tests you are given, by number, and report each one PASS/FAIL with
   the evidence.** A phase report that says "tests pass" without the numbers is
   not a phase report.

## 1. Inherited facts — do NOT re-derive these

### 1.1 A file's columns are stored under TWO keys each

`pb_hr_payroll_formula/models/payroll_import_batch.py:488` `_raw_data_from_row`
writes, for every column of a row:

```python
raw_data[header] = row[col_idx]
col_letter = ColumnManager.index_to_letter(col_idx)
if col_letter not in raw_data:
    raw_data[col_letter] = row[col_idx]
```

so a 9-column file produces an 18-key dict: `Employee code`, `A`,
`Employee name`, `B`, …

**This is load-bearing and must never be changed.** The resolver's
column-letter fallback reads it, and compiled formulas address components by
letter (`GROSS` reads `values['AS']` on the reference Vietnamese scheme).
Clearing or narrowing it silently drops components out of gross pay — it was
tried once and reverted.

The board's job is therefore to *display* one card per real column while the
aliases stay in the data and stay reachable by typing.

### 1.2 The dropped-file lane already solved this

`peek_source_columns` (`payroll_import_batch.py:507`) returns
`[{key, sheet, header, letter, sample, preferred}]` and marks exactly one
spelling per real column as `preferred` (`:576-584`). `_import_left_columns`
(`pb_formula_studio/models/pb_formula_studio.py:8551`) honours `preferred` for
the dropped-file lane at `:8580-8589` — and then, four lines later at
`:8591-8593`, adds a card for *every* raw key of the loaded batch. That
asymmetry is the whole of the A/B/C bug.

### 1.3 `_norm` is one character away from a false 85%

`pb_formula_studio/models/pb_formula_studio.py:5737`:

```python
def _norm(s):
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())
```

The suggestion loop (`:8503-8523`) scores `0.85` when
`rc in cn or cn in rc`. With `cn = 'a'` (a bare column-letter key) that is
`'a' in 'manhanvien'` → **True**. Every one-letter key therefore suggests
itself at 85% onto the first component whose code contains that letter. This
is the source of the bogus 85% chips on the live Vietnamese board.

Related settled fact (MAPFIX): the converter's real floors are **code ≥6 chars
for the fuzzy header fallback**, ≥3 for the dependencies regex, and a code must
never equal a column letter. Substring collisions between *codes* are safe —
the converter matches greedily. The floor being violated here is the fuzzy
one.

### 1.4 The pay period is ALREADY a first-class source — it just answers one thing

`pb_hr_payroll_formula/models/pay_period.py` is stdlib-only, importable by the
bare-`python3` battery, and:

* `PERIOD_CODES = ('PAYMONTH',)` — matched on the component's **CODE**, upper
  case, because that is what formulas reference.
* `PERIOD_VIA = 'pay_period'`; provenance `src` is `'period'`.
* `period_values(date_from, date_to)` — **the month is the month the period
  ENDS in** (a 26 Sep → 25 Oct run is the October run).
* `fill_period_inputs(values, unresolved, date_from, date_to)` — writes only
  codes **already present in `values` AND in `unresolved`**, so it can never
  add a component to a run and can never beat a declared source. Returns the
  codes it filled. **Nothing in this module raises.**

Both resolvers already call it, last among the sources:

* `models/hr_payslip_formula.py:812-816`
* `models/payroll_import_batch.py:4628-4632`

And the vocabulary already carries it:

* `input_provenance.py:47` — `'period'` is in `SOURCES`.
* `pb_formula_studio/models/pb_formula_studio.py:785-791` —
  `_SOURCE_LABELS['period'] = "Pay period"`.

**So Strand 2 is an extension of an existing, working seam, not a new source.**

### 1.5 Where a run's dates live

* `hr.payroll.import.batch.date_from` / `.date_to` — Period Start / Period End,
  `payroll_import_batch.py:167-168`; presets at `:400-422`.
* The guided wizard's step 1 already collects them
  (`pb_import_wizard/static/src/xml/import_wizard.xml:54-64`,
  `static/src/js/import_wizard.js:37,83-87`) and
  `pb_import_wizard/models/pb_import_wizard.py:142` `create_and_load` copies
  them onto the batch at `:153-156`. Presets are built by `_period_presets()`
  at `:17-35`, deliberately mirroring the native form's onchange.
* `hr.payslip.date_from` / `.date_to` — the payslip resolver's own dates.
* A batch that produced a run carries `payslip_run_id`
  (`get_summary` reads it, `pb_import_wizard.py:101`).

### 1.6 Identity is matched ONCE, not per lane (answers the owner's question)

* `payroll_import_batch.py:823-830` `_extract_employee_fields` — first tries a
  built-in list of headings (`employee_code`, `employee code`, `emp_code`,
  `emp code`, `emp. code`, `empcode`, …), then lets a declared mapping
  override it.
* `:1810` `_get_employee_identifier_value` looks for an **Employee & contract**
  mapping onto `hr.employee` `employee_id` / `identification_id` / `barcode`,
  and reads the value through
  `_get_mapped_value_for_field` (`:1794`) →
  `_get_rule_raw_value(..., allow_column_letter=False)`.
* Data-store (API) rows use `_identity_from_store_row` (`:899`) with
  `EXTERNAL_CODE_HEADER_CANDIDATES`, plus the same mapping override.

So: the identity column needs **one** wire, in Employee & contract, and only
when the heading is not one the built-in list recognises. The Spreadsheet →
Scheme lane feeds *pay values*; declaring the identity column there is
optional and only matters when the component cannot otherwise be found by
name. **Note the `allow_column_letter=False`** — identity is deliberately
never resolved by column letter.

## 2. Gotchas (append here as RS<n>)

**RS1 — a test run steals port 8069 when the service is stopped.** `odoo-bin
--test-enable --stop-after-init` binds the HTTP port and starts serving the
live tenants if `odoo-server` is down, then sits there instead of exiting.
Twice in the Phase A session a "hung" upgrade was a finished test run serving
payobook and rize from a process pointed at another database. Always pass
`--http-port=8079 --gevent-port=8081` to a test run, and check
`ss -ltn | grep 8069` before assuming the service owns it.

**RS2 — use `odoo-bin --logfile` or you are reading the wrong log.** A
`> /tmp/x.log` redirect captures nothing: the process logs to the path in
`/etc/odoo-server.conf`, a 1.5 GB shared file that `grep` treats as binary.
Pass `--logfile=/tmp/<run>.log` on every detached run.

**RS3 — the Vietnamese board lives on the `rize` tenant, NOT on payobook.**
`Rize Vietnam` (3921) / `Rize Vietnam Payroll` (3938) and batch 1113 are in the
`rize` database; payobook has no scheme of that name. Validate this
programme's screens on **rize.payobook.com**. Two handovers in this programme
sent an agent to the wrong database.

**RS4 — a heading that is a letter one column too far cannot be recovered.**
If column 1 is headed `X` and column 2 is headed `A`, the loader's own writer
overwrites its `A` alias with column 2's value and the key becomes
indistinguishable from an alias. The fold drops the `A` card and column 2 shows
as `B`. One card per column either way and nothing is orphaned, but no rule can
recover the intent from the stored dict.

**RS5 — a phase's own validation user needs the Formula Engine group AND a
company.** A temporary validator could not read a single scheme (`AccessError`,
then "Access to unauthorized or invalid companies") holding neither *Formula
Manager* nor a company beyond "Your Company". Granting the group from
`odoo-bin shell` is not enough on its own — the running server keeps a cached
group set until an ORM write goes through the live process.

**RS6 — the source vocabulary is duplicated and only the Python half knows the
pay period.** `pb_formula_studio/models/pb_formula_studio.py:798` maps
`'period' → "Pay period"`. Its client-side twin,
`pb_formula_studio/static/src/js/source_vocab.js`, does not: `SOURCES` (`:21`)
has no `period` entry, `srcLabel` (`:52`) falls through to `_t("No source")`,
and `READ_KINDS` (`:42`) omits it so `srcDisagrees` reports a false
disagreement — *"Last run used a different source: No source"* about a
component that is working perfectly. Wrong since the period became a source.
**Any new source kind must be added in BOTH places.** Fixed in Phase C —
**and see RS13: there were four places, not two.**

**RS7 — a container-width problem cannot be solved with a viewport media
query.** Three boxes in the import wizard's `iw-row2` rendered 115px wide at a
1440px viewport, because the panel is 366px regardless of the window.
`repeat(auto-fit, minmax(150px,1fr))` measures the panel, which is the thing
that actually constrains them.

**RS8 — a float that means "nobody said" reads as zero on screen.**
`pb_std_work_days` is deliberately not back-filled, so every pre-existing run
shows `0.00`, which reads as "paid against no working days". The answer is a
non-stored note stating the effective number in words underneath. The ban is on
a stored compute overwriting a user's value, not on a sentence describing it.

**RS9 — `odoo-bin shell` needs the subcommand before the options.**
`odoo-bin -c … -d db shell` fails with `unrecognized parameters: shell`;
`odoo-bin shell -c … -d db` works.

**RS10 — a whole-module test run OOM-kills this box.**
`--test-tags /pb_hr_payroll_formula` (540 tests) died at EXIT=137 part-way.
Run test classes by name. Related and older: never compile
`web.assets_backend` in a shell.

**RS11 — a failing test rolls the whole upgrade back and can hang in
shutdown.** A process sat stuck for minutes after "Initiating shutdown". Kill
by PID, **never** `pkill -f odoo-bin` — that reaps the live service too.

**RS12 — two agents deploying to one box will collide.** Phase A and Phase B
ran concurrently; Phase B's `pb_hr_payroll_formula` files were on disk ahead of
two databases' schema for part of the window, which broke every import-batch
read on them, and its deploy stopped the live service for several minutes.
Both recovered, but **phases that share a server must run one at a time** even
when they share no files. Verify the live box yourself after concurrent
phases — Phase A's closing warning about `abm` and `payobook_template` was
already stale when it was written.

**RS13 — the source vocabulary was in FOUR places, not the two RS6 named, and
the two RS6 missed are the two that decide whether a chip appears at all.**
`mapping_canvas.js` carried a private label map inside `srcChip` AND another
inside `srcChips`; `journey_board.js` carried a third inside `runSources`. Each
is a `labels[kind]` lookup whose miss path is `continue` / `|| kind` — so a
source kind they do not know renders **no chip at all** (not a wrong chip, not
an error: nothing), and the Journey lane printed the raw internal word
`period` on a screen an owner reads. Phase C's Chrome validation caught this
one minute after the server side was proven correct by 31 green tests: the
wire saved, the board reloaded, and the card showed one chip where two were
due. **Fixed by deleting all three copies** — both files now
`import { srcLabel } from "../source_vocab"`, and `test_journey_j10_record_
source.test_07b`, which used to ASSERT the duplication (`count(...) == 2`),
now asserts its absence. `none` is the one kind that must stay un-chipped.

**RS14 — a kind that belongs to no lane is dropped, silently, at resolve
time.** §4.4 of the Phase C handover predicted it and it is real:
`formula_config._source_kind_rank()` is built by walking the scheme's ENABLED
LANES and extending `_LANE_KINDS[lane]`, so `'pay_run'` — added to
`_SOURCE_RANK` but to no lane — is absent from `_config_kind_rank()`, and
`declared_sources()` filters on exactly that. The board saves, the chip
appears, the number never lands. Any future source kind needs a lane entry in
the same commit. Verified on an untouched scheme (`source_priority` still
`api,excel,records`): after the fix the rank ends `…, 'contract_component',
'pay_run'` and `_source_lane_order()` appends `payrun` last.

**RS15 — `payrun` is a LANE but not a PRIORITY TOKEN, and the split is
deliberate.** Putting it in `SOURCE_LANES` is what makes the kind readable;
letting a person type it into `source_priority` would let them rank the run
ABOVE the pay data file, which contradicts the standing ruling that the run
replaces the value that was missing and never the value somebody stated. So
`_check_source_priority` validates against a new `_PRIORITY_LANES` (the same
three), and `_source_lane_order()` pins `payrun` last whatever the stored
string says. The Settings lane picker (`formula_studio.js srcLaneList`) and
`_source_lane_counts` are hardcoded to the three and needed no change.

**RS16 — the studio's `_source_rank()` is `_SOURCE_RANK`, which is NOT the
resolver's full rank.** It holds only the kinds that can be a `source_ids`
ROW; `contract_component` has always been appended after the sort rather than
found in it, and `pay_run` now is too. The Phase C handover said the chip
chain would light up "with no display work" because `_declared_source` reads
`declared_sources()` — it does, and then `if spec['kind'] not in rank:
continue` drops it, and `out.sort(key=lambda d: rank.index(...))` would have
raised on it. A new kind needs an explicit append in
`pb_formula_studio._declared_sources`.

**RS17 — the board's declaration kind and its DISPLAY kind are different
words on purpose.** `declared_sources()` says `pay_run` (the name of a
declaration); every display surface says `period` (the word the provenance
writes when a run actually fills a value). They must not be unified: a card
whose declared chip and actual chip used different words for one thing would
report a permanent false disagreement through `srcDisagrees`.

**RS18 — one component, two wires, two cuts.** A component may now carry a
spreadsheet column and a pay-run answer at once, so `import_mapping_delete`
can no longer mean "this component's wire". The pay-run wire's `ref` is the
string `'p:<rule id>'` and the column's is the bare id; the endpoint branches
on the prefix. The handover asked for `import_mapping_delete` to "also clear
`period_key`" — that would have made cutting the column silently remove the
run as well, which is the exact bug the method's own comment warns about in
the other direction.

**RS19 — `rztest` has ten test failures that are its DATA, not the code.**
A real-data clone of `rize`, it makes fixture-based tests find live records
instead (`TestStructurelessPayslip` picks up scheme 3921; `TestRecordsR1One
Time` reads a real job title). The same ten classes are green on
`payobook_template`, which has two of its own (`TestRd49SyncCost` cron rows
switched off on that database). **Baseline both before changing anything**, or
half a day goes into failures that were there when you arrived.

**RS20 — the source vocabulary was in a FOURTH place after RS13, and it is the
`.po`.** RS6 fixed the server label, RS13 deleted three duplicate client maps —
and on a Vietnamese screen the chip still read **"Pay period"** in English.
`pb_formula_studio/i18n/vi_VN.po` had the entry, with a correct Vietnamese
`msgstr`, carrying **only `#. odoo-python`**. `CodeTranslations._load_web_
translations` filters on `odoo-javascript`, so `srcLabel`'s `_t("Pay period")`
never found it. Every one of the other ten labels in `source_vocab.js` carried
both markers; this one was added by Phase C's server edit and the JS occurrence
was never merged in. **A shared label used from both Python and JS needs BOTH
markers and BOTH occurrence lines in one entry** — and a green test suite can
never see this, because a test database has no second language installed.

**RS21 — an always-known name must not be folded into a catalogue that means
"nothing could be learned".** `pb_integrations.rule_composer._rule_draft_vals`
guards its field check with `if known and …`: an EMPTY catalogue means the
source has never sent anything, so every hand-typed name is accepted (a check
that could not run must not be reported as a check that failed). Adding the six
pay-run operand names to `known` would have made it permanently non-empty and
silently switched that leniency off for every brand-new connector. They are
held in a separate `run_names` set and unioned only at the comparison. Same
trap on the client: `catalogueEmpty` had to exclude the run group, or the
"this feed has not sent anything yet" note disappears for ever.

**RS22 — this codebase asserts its shipped data by COUNT, in other modules.**
Adding one row to `transformation_rule_templates.xml` failed
`pb_hr_payroll_formula.TestZohoCatalogue.test_03` (`rules_created` 9 != 8,
against a hard-coded `ZOHO_RULES` dict), and adding one lane to
`pb_blueprint.LANE_OF_KIND` failed `pb_blueprint.TestConnect` (`by_lane` is
asserted as an exact dict). Neither is a defect — both are the catalogue
guarding itself — but **a vendor template or a lane is never a one-file
change**, and the test that breaks lives in a module you did not think you were
touching.

**RS23 — `hr.payslip.run.create` fills the Mon-Fri default when the value is
FALSY, so a fixture that wants a stored zero has to write it afterwards.**
Phase B's `create` override reads `if not vals.get('pb_std_work_days')`, and
`0.0` is falsy, so `create({'pb_std_work_days': 0.0})` stores 21. A negative
survives (it is truthy). A test asserting "zero means nobody said" has to write
the zero in a second statement or it is testing the default.

**RS24 — a fixture period must be one no real database can own.**
`_period_context` SEARCHES for the pay run or pay-data load behind the period it
is handed, so a test fixture dated August 2026 finds `rize`'s and `rztest`'s
real August run and reads its standard working days instead of the Mon-Fri
default. The Phase D suite uses **August 2036** — same 21 Monday-to-Friday days,
hand-countable, and no customer has a run in it. Generalises RS19: on a
real-data clone, a fixture DATE is as dangerous as a fixture name.

**RS25 — `pb_integrations.TestLedgers.test_the_ledgers_never_sudo` has been red
since SOURCING S5, and nothing in this programme touched it.**
`pb_integrations/models/pb_integrations.py` now contains seven `sudo(` calls and
the test asserts none. Found by running the whole module rather than the classes
a phase changed. Not fixed here — the sudo calls may well be correct and the
test the stale half — but somebody has to decide which, and until then that
module's suite is not green.

**RS26 — the guided lane can ADD, and that is the whole of what it can do.**
A guided rule's DERIVE step is `value_steps`, a list of `{field, contains}`
whose values are summed (`_row_value`); there is no operator vocabulary, so
`a / b * c` cannot be written in it at any length. The composer's **Excel lane**
is where arithmetic lives, and it is still a no-code lane edited in the same
popup. So "guided or python" is a false pair: the real ladder is **steps →
formula → advanced**, and a spec that says "guided, or python if guided is
unavailable" should usually mean the middle one.

**RS27 — a validator user needs the right ACTIVE COMPANY, not just the groups.**
RS5 said the group was not enough; this is the other half. With every company in
`company_ids` but "Your Company" active, `pb.integrations.get_ledger` answered
*"This seems to be a multi-company issue"* and the Data tab rendered "This table
could not be loaded." Nothing was wrong with the code. Switch the company in the
top bar before concluding anything from an empty cockpit.
