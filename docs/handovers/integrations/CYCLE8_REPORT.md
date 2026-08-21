# Integrations Program — Cycle 8 report: The Rule Composer

> Handover: `CYCLE8_RULE_COMPOSER.md`. Conventions: `docs/WORKFORCE_REDESIGN_CONVENTIONS.md`
> (binding through W157, this cycle appends W158+) and `docs/FORMULA_ENGINE_CONVENTIONS.md`.
> **Written incrementally and committed at every milestone** — a stall must not
> lose the record (the handover says so because Cycles 2 and 7 both stalled).

_Status: IN PROGRESS. Server half DEPLOYED and verified on all three databases; WP-3 (the composer component) building in parallel._

---

## WP-1 — model + engine: guided rules as first-class citizens — **DONE**

`pb_hr_payroll_formula` 19.0.1.59.0 → **19.0.1.60.0**.

### What shipped

| file | what |
|---|---|
| `formula_engine/rule_formula.py` (new, 470 lines) | the Excel lane: `Cell` (a payload value that reads as text and computes as a number), `resolve_ref` (exact key, then case/space/underscore-insensitive), the recursive converter, the closed function table, `eval_rule_formula` |
| `models/api_transformation_rule.py` | six spec fields + `plain_summary` + `last_error`/`last_error_at`; the guided engine; the traced twin; the vocabulary constants; the same six fields mirrored on the template model and added to `_COPIED` |
| `models/rule_assistant.py` (new) | `hr.api.rule.assistant` — the drafting gateway and its deterministic floor |
| `views/api_transformation_rule_views.xml` | the `last_error` alert, `builder_mode`, `plain_summary`, the TAKE step and the Excel formula |
| `tests/test_rule_composer.py` (new) | handover tests 1, 2, 3, 5, 6, 7 + the summary/no-platform-name assertions |

### Design decisions worth reading

**Preview == execution is a fact about the code, not a promise.** There are two
primitives — `_builder_expand` (which rows the sentence is about) and
`_builder_run` (the sentence). Execution calls them with no trace; the
composer's preview calls **the same two** with a dict, and the loops that
compute the answer fill it in as they go. `test_06` runs both entry points over
identical specs and asserts the numbers are equal; `test_06c` previews a rule
that has never been saved (`Rule.new(...)`), proving the draft path is the same
engine and writes nothing.

**None is not zero.** `_unit_value` and `_row_value` return `None` for a value
that is missing or unreadable, and the aggregate SKIPS it — exactly as
`_execute_aggregate` skips a `float()` that raises. Returning 0 would drag an
average down and break a minimum. `test_01c` asserts each conversion produces a
number *and that it is not zero*, which is the assertion shape W137 was
diagnosed by.

**Zero `safe_eval` on the guided path.** Conditions are evaluated natively on
plain dicts by `_condition_matches`, which never raises: a condition that cannot
be evaluated does not match. That is the same leniency the legacy
`except Exception: pass` filter had, and payroll depends on it.

**One equality, two lanes.** `is`/`is_not` compare as numbers when both sides
read as numbers and as trimmed, case-insensitive text otherwise — the same rule
`excel_streq` and the `Cell` class apply. The two lanes agreeing about equality
is not a nicety; the same rule is meant to give the same answer in either.

**`IF` is lazy.** `IF([h]=0, 0, 100/[h])` must not raise on a zero row and drop
it from the aggregate — a wrong answer that looks exactly like a right one.
The converter wraps both branches in lambdas (`test_03e`).

**The silent-failure gap.** `_flag_error` writes only when the message CHANGES
(a broken rule on a 4 000-row pull would otherwise be 4 000 identical writes)
and `_clear_error` writes only when there is something to clear. The value still
falls back to `default_value`, exactly as before — what is new is that the
reason is on the record instead of in a log nobody reads during a pull.

### Parity table (handover test 2) — asserted in `test_02*`

Fixtures reproduce the real payload shapes: overtime rows that are rejected,
pending, of the wrong band, missing their hour count and carrying `'n/a'`
instead of a number; four dependants of whom two have no PIT number; four
attendance days including one malformed in both halves.

| rule | legacy path | guided path | excel path | expected |
|---|---|---|---|---|
| OTHRS150 | 6.5 | 6.5 | — | 6.5 |
| OTHRS200 | 3.0 | 3.0 | — | 3.0 |
| OTHRS210 | 0.0 | 0.0 | — | 0.0 |
| OTHRS270 | 0.0 | 0.0 | — | 0.0 |
| OTHRS300 | 1.25 | 1.25 | — | 1.25 |
| OTHRS390 | 0.0 | 0.0 | — | 0.0 |
| DEPCOUNT | 2 | 2.0 | — | 2 |
| WORKEDHRS | 11.5 | 11.5 | 11.5 | 11.5 |

Both halves are asserted: that the two paths agree, **and** that the number is
the one the legacy application computed. An equality alone would pass if both
were broken.

### Deviation from the handover's commit plan

Commits 1 and 2 (`guided model + native engine + last_error` and `the Excel
lane`) are **one commit**. `formula_engine/rule_formula.py` holds `Cell` and
`resolve_ref`, and the GUIDED lane uses both — every condition and every value
step resolves its field through `resolve_ref`, because a novice who reads
`Actual Pay Hour` off the screen must not have to know the API spells it
`Actual_Pay_Hour`. Splitting the file across two commits would have shipped an
intermediate commit that does not import. The commit message names both halves.

---

## ⚠ A parallel session is editing `pb_hr_payroll_formula` — W157, again

`git status` shows four files modified that this cycle never touched, adding a
payslip `note_html` feature:

```
 M pb_hr_payroll_formula/models/formula_config.py       (+10)
 M pb_hr_payroll_formula/models/hr_payslip_formula.py   (+4)
 M pb_hr_payroll_formula/models/payslip_config.py       (+5, a new fields.Html)
 M pb_hr_payroll_formula/report/payslip_themed.xml      (+4)
```

That is exactly the incident Cycle 7 ended with: `rsync <module>/` would publish
another session's work in progress to two live databases and an `-u` would bless
it — and one of those files adds a COLUMN, which is a schema change that would
land without its own upgrade being intended.

**Handling**: the deploy is FILE-SCOPED (W157 rule 1) — every file this cycle
owns is transferred by name, and none of the four above is transferred. They are
not staged, not committed and not touched. `git show --stat` on every commit
confirms only this cycle's files are in them.

---

## WP-2 — composer RPCs — **DONE**

`pb_integrations` 19.0.1.6.0 → **19.0.1.7.0**. `models/rule_composer.py`
extends `pb.integrations` (no sudo, caller's rights, as the rest of the file).

| RPC | law |
|---|---|
| `rule_composer_data` | one call, the existing provenance ladder, per-feed `synthetic` flag |
| `rule_preview` | the traced engine run; refuses `python` in `preview_transform`'s wording family |
| `rule_save` | **fail-closed**, whitelisted, catalogue-checked, key-checked |
| `rule_archive` | same gate |
| `rule_propose` | drafts; never writes; the draft is re-checked by the save validator |

**The gate proof.** `_rule_can_edit` is the deliberate opposite of the Mapping
Studio's `_can_edit`, which ends `except Exception: return True`. That is
defensible where it decides whether a pencil is drawn and indefensible where it
decides whether a write runs. `test_04b` monkeypatches `res.users.has_group` to
raise and asserts the gate refuses.

**`python_code` cannot be reached.** `_rule_draft_vals` is the only place a spec
becomes values and it assembles them key by key from a literal list.
`test_04c` posts a legal guided spec carrying `python_code`,
`filter_expression` and `aggregate_field`, asserts the save SUCCEEDS, then reads
the row back and asserts all three are empty. `test_04d` proves an existing
python rule is refused outright rather than merely hidden.

## WP-4 — migration + parity — **DONE**

`migrations/19.0.1.60.0/post-rules_become_sentences.py` + the data file made
guided-native for fresh installs. Idempotency and edit-protection are driven,
not asserted: `test_04` runs `_convert` twice (8 changed, then 0 changed / 8
skipped) and `test_04c` retunes a filter and watches the migration leave it
alone.

`test_zoho_catalog.ZOHO_RULES` amended IN this commit with the reasoning beside
the dict (W138), plus a new assertion that every shipped catalogue row is
`guided` and carries a summary — so the data gets its own test rather than
being a surprise inside somebody else's.

---

## Deploy — the server half

W136 stall-proof unit `c8deploy` (the unit stops the service, upgrades all three
databases, purges the asset cache and starts the service itself, launched with
`systemd-run --no-block`, W133).

**FILE-SCOPED, per W157.** The staging tree was built with
`git archive HEAD -- <20 paths>` and transferred file by file with `install`.
Never `rsync <module>/`. Proof the parallel session's work was not published:

```
absent(good) pb_hr_payroll_formula/models/payslip_config.py
absent(good) pb_hr_payroll_formula/models/formula_config.py
absent(good) pb_hr_payroll_formula/models/hr_payslip_formula.py
absent(good) pb_hr_payroll_formula/report/payslip_themed.xml
staged manifest version = 19.0.1.60.0   (their uncommitted bump to .61.0 was not shipped)
```

Pre-stop scan (W128/W143): one `odoo-bin` (the service, started 01:56:39 UTC),
and `find … -newermt` over the addons tree returned **nothing** — no foreign run
and no foreign file already on the server.

| database | result |
|---|---|
| payobook | `EXIT_payobook=0` |
| abm | `EXIT_abm=0` |
| payobook_template | `EXIT_payobook_template=0` |

`PUBLISHED=0`, `ACTIVE=active`, `payobook=200`, `abm=200`.

Versions after, identical on all three: `pb_hr_payroll_formula 19.0.1.60.0`,
`pb_integrations 19.0.1.7.0`, `pb_import_kit 19.0.1.9.0`.

### The migration, read back off the live databases

```
payobook          templates 8 converted / 0 left alone; rules 8 converted / 0 left alone
abm               templates 8 converted / 0 left alone; rules 8 converted / 0 left alone
payobook_template templates 0 converted / 8 left alone; rules 0 converted / 0 left alone
```

`payobook_template`'s "8 left alone" is the idempotency guard doing its job:
its catalogue rows are not `noupdate`-frozen, so the upgrade reloaded the
now-guided-native data file and the post-migration correctly found nothing left
to convert. All three databases end in the same state.

**The owner's abm board, as it now reads** (`plain_summary`, straight out of the
database):

```
OTHRS150   Adds up Actual_Pay_Hour over Custom / Other records
           where OT_Type is 150% and ApprovalStatus is Approved
 …200 …210 …270 …300 …390 — the same sentence, one band each
DEPCOUNT   Counts rows in tabularSections.Dependent and Dependent Health
           Insurance on each Employee Master Data record
           where Dependent_PIT_Number is present
WORKEDHRS  Adds up totalWorkedHours plus paidLeaveHours over Attendance records
```

That last line is the one the cycle was for. It was fifteen lines of
`str(r.get(...)).strip()` / `isdigit()` arithmetic under a heading that said
"Python Expression (Advanced)".

## The abm recompute comparison — **8 / 8 identical**

Read-only: the script browses each live rule, builds an IN-MEMORY twin
(`new()`, never a row) carrying that rule's own retained provenance —
`builder_mode='python'` plus the untouched `python_code` / `filter_expression` —
and runs both over the same records. No sync action was called; the owner's
connector id 1 was not touched.

abm's seeded connector is deliberately disconnected and has no stored rows, so
the comparison runs over the stated fixture (overtime rows that are rejected,
of the wrong band and carrying `'n/a'`; four dependants of whom two have no PIT
number; four attendance days including one malformed in both halves). A
comparison over an empty store would have been `0 == 0`, which proves nothing.

| rule | mode | legacy twin | guided | same | provenance kept |
|---|---|---:|---:|:--:|---|
| OTHRS150 | guided | 6.5 | 6.5 | ✓ | filter |
| OTHRS200 | guided | 3.0 | 3.0 | ✓ | filter |
| OTHRS210 | guided | 0.0 | 0.0 | ✓ | filter |
| OTHRS270 | guided | 0.0 | 0.0 | ✓ | filter |
| OTHRS300 | guided | 1.25 | 1.25 | ✓ | filter |
| OTHRS390 | guided | 0.0 | 0.0 | ✓ | filter |
| DEPCOUNT | guided | 2 | 2.0 | ✓ | python |
| WORKEDHRS | guided | 11.5 | 11.5 | ✓ | python |

`ALL_MATCH=True`  `ALL_GUIDED=True`  every `last_error` empty.

---

## Tests — **144 run, 1 failed, 0 errors**, and the one failure is pre-existing

Scoped suite over `pb_hr_payroll_formula`, `pb_integrations`, `pb_import_kit`
and `biz_debrand`, on **payobook**, in its own window on its own port
(`--http-port=8099 --gevent-port=8098`) with the real service up throughout.

```
2026-08-21 04:08:50  1 failed, 0 error(s) of 144 tests   (payobook)
```

The failure is `TestBizDebrandHttp.test_database_manager_debranded` — the stock
database-manager page still carries `odoo.com` in its own markup. Its file was
last touched **2026-07-04**, this cycle touched no `biz_debrand` file at all,
and Cycle 7 recorded the same `EXIT_TESTS=1` for it. Pre-existing.

**The brand gate is green**: `test_01_no_user_visible_platform_name` ran and
passed across all 94 `pb_*`/`biz_*` modules with this cycle's new strings in
the tree, as did `test_02` (the gate proving it can still fail) and `test_04`.

### Three defects the live run found, all fixed

| # | what | why it mattered |
|---|---|---|
| 1 | the composer offered **200 `hr.employee` columns** as the Zoho connector's fields | `get_available_source_fields`'s third layer is this product's own schema, right for the Mapping Studio and meaningless for a rule. A rule built on `activity_exception_decoration` would not error — it would answer a well-shaped 0 forever. Dropped in all three places it could leak (picker, save validator, assistant), with `fields_known` carrying the honest reason. **W164** |
| 2 | a **lowercase output key was accepted** | `rule_save` upper-cased it before the validator could see it, so the rule that capitals matter was enforced by a coercion nobody is told about. Now refused, with the correct spelling in the message. **W165** |
| 3 | `test_03d` could not pass | Odoo's `TransactionCase` overrides `assertRaises` and its override cannot take a TUPLE — `TypeError` before the code under test runs, reported as though the hardening were broken. **W160** |

### Two runs lost to the environment, both now W-rules

* `--no-http` does **not** stop an Odoo 19 test run binding `http_port`, so
  W131's own escape hatch does not work on this build — the run died in
  pre-flight on `Address already in use`. **W158**
* `payobook_template` has **no administrator**, so
  `_check_at_least_one_administrator` refuses every `res.users.create` on it
  and six suites died in `setUpClass`. A Cycle 1 test that has passed for
  months failed identically, which is what identified it as an environment fact
  rather than a regression. **W159**

---

## ⚠ Incident: one worktree, two agents, one git index — W166

The composer component (WP-3) was built by a child agent in this same
worktree. It had run `git add` on its files; a moment later the parent ran
`git commit` for an unrelated documentation change, and **that commit took the
whole index** — 2 000 lines of a UI landed inside a commit whose message
described a ledger update.

Explicit file staging, which is what W157 asks for and what every commit in this
cycle did, does not prevent this: `git commit` commits the INDEX, not the paths
the caller happened to name.

**Repaired**: `git reset --soft HEAD~1`, `git restore --staged pb_integrations
pb_import_kit`, re-commit only the two docs files. The child's working files
were not touched at any point, and it was told, because its next `git commit`
would otherwise have found nothing staged with no way to discover why.

Audit after the repair — every file in every one of this cycle's commits:

```
foreign-file audit (thaco / ABM / .claude / pb_formula_studio / ONBOARDING):  CLEAN
foreign pb_hr_payroll_formula files (payslip_config, formula_config,
        hr_payslip_formula, payslip_themed):                                 CLEAN
```

---

_(WP-3, the live pass and the final ledger follow as they land.)_
