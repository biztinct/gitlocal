# Integrations Program — Cycle 8 report: The Rule Composer

> Handover: `CYCLE8_RULE_COMPOSER.md`. Conventions: `docs/WORKFORCE_REDESIGN_CONVENTIONS.md`
> (binding through W157, this cycle appends W158+) and `docs/FORMULA_ENGINE_CONVENTIONS.md`.
> **Written incrementally and committed at every milestone** — a stall must not
> lose the record (the handover says so because Cycles 2 and 7 both stalled).

_Status: **COMPLETE**. All four work packages shipped, deployed to payobook / abm / payobook_template, and live-validated on both live databases._

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
2026-08-21 04:08:50  1 failed, 0 error(s) of 144 tests   (payobook)   after WP-1/2/4
2026-08-21 04:42:24  1 failed, 0 error(s) of 144 tests   (payobook)   CONFIRMATION, after WP-3
```

The run was repeated at the very end because WP-3 changed `pb_integrations
/models/pb_integrations.py` (`_ledger_rule` / `_detail_rule`) after the first
run — a suite that was green before the last Python change is not a green
suite. Same verdict, same single failure.

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

## WP-3 — the Rule Composer component — **DONE**

Built by a child agent against the WP-2 payload as a fixed contract
(`2995cb8d`), plus three follow-up fixes from the live pass. `pb_integrations`
→ **19.0.1.8.0**.

`rule_composer.js` (≈990 lines) / `.xml` (≈480) / `.scss` (≈390), mounted as a
sibling of `WfDrawer` inside `PbIntegrations` — the drawer still opens the
mapping and store ledgers, unchanged. Chrome from the new `.pbim-modal*`
primitive plus the shared `.pplw-*` wizard shell; class prefix `.itgrc-*`.

The composer's kernel is exported and PURE — `suggestOutputKey`,
`keyAfterRename`, `emitSpec`, `toFormula`, `toSteps`, `railSentence`,
`readOnlyReason`, `PreviewPump` — because the six rules it enforces all fail
invisibly. The preview pump is `mapping_canvas._tfPreview`'s mechanism
extracted: 260 ms debounce plus a monotonic `++token` supersede, with the timer
functions injected so a test can drive a manual clock and resolve two requests
in the wrong order.

`_ledger_rule` now prints the rule's own sentence in place of the selection
label, turns the badge error-toned when `last_error` is set, and carries
`connector_id` per row. `_detail_rule` gained the `date_check_operator` /
`date_check_value` rows that were declared on the model and never rendered.

## Live validation (handover test 10)

W129 temporary single-company validators created through `odoo-bin shell`
(`c8val`, uid 2282/2293 on payobook, uid 12 on abm), used for the whole pass and
removed in the same session — **proven by `SELECT`, not by the script's output**
(W144.3):

```
payobook: NO ROW      abm: NO ROW
```

abm's teardown cleared a `payroll.ai.conversation` first — the exact row that
FK-blocked Cycle 4's teardown and made W144.

### abm — the owner's board

| what | result |
|---|---|
| all 8 rules open as sentences | ✓ the `WHAT IT DOES` column carries the full generated sentence for every one |
| WORKEDHRS re-shot against the owner's original | ✓ `.ig-c8-shots/abm-BEFORE-workedhrs-drawer.png` → `abm-AFTER-workedhrs-composer.png` |
| synthetic banner on the never-synced connector | ✓ *"These rows are illustrations of what this source will send. They are not records that were received."* |
| "Describe it" via the deterministic fallback | ✓ *"The assistant is not configured, so these steps were matched from the words you used."* — and the draft was correct |
| console errors | **0** |
| responses ≥400 | **0 / 21** |

The WORKEDHRS composer computes `619200 s / 3600 + 16:30 = 188.5` live from the
catalogue illustration, and the modal scrolls inside itself while the page
behind it does not move.

### payobook — two rules built from scratch, as a novice

| rule | clicks | result |
|---|---:|---|
| **Count dependants** — `DEPENDANTS` | **9** | rail read `7 records → 7 match → 7` before saving |
| **Sum days where leave type is Annual Leave and status is Approved** — `ANNUALLEAVEDAYSAPPRO` | **20** | rail read `5 records → 3 match → 4`, the two Sick Leave rows struck through, per-record values 1 / 2 / 1 |

Both counts include every typed field (the name, the two condition values, three
picker searches). The output key was suggested from the name in both cases and
never overwrote anything typed.

The Excel lane, live on the second rule: `[days] * 8` over the same chip-built
filter gave **32** (3 matches × 8); `[days] + NOPE([days])` put the human
message in the proof rail *and disabled Save*; switching back to the steps
restored `days` exactly and the rail returned to `5 records → 3 match → 4`.

`last_error` surfaced in both places — the ledger badge turned `Error`-toned and
the proof rail read *"The last time this rule ran it failed: …"* beside a live
preview that still computed 7. Flag set and cleared on a rule this pass created.

### The gates, refused live through the deployed RPC

| attempt | refusal |
|---|---|
| `builder_mode='python'` | "The composer can only write guided rules and formulas. Advanced rules are edited in the backend form." |
| guided spec carrying `python_code` + `filter_expression` | **saved** — and the row read back `python_code: false`, `filter_expression: false`, `builder_mode: guided` |
| field not in the catalogue | "This source does not have a field called “Invented_Field”." |
| lowercase key | "“c8lowerx” has to be capital letters and digits, starting with a letter — try “C8LOWERX”." |
| underscored key | "“C8_UNDER” contains an underscore. Formulas cannot read an underscored name — try “C8UNDER”." |
| substring collision | "“DEPENDANTSX” and the existing “DEPENDANTS” contain one another. A formula would rewrite the shorter inside the longer and work out 0 — rename one so neither contains the other." |
| formula naming an unknown function | "NOPE is not a function this rule can use. The ones it understands are: ABS, AND, …" |
| `__import__("os")` as a formula | "This formula uses something that is not allowed in a rule. …" |
| `rule_preview` on a python rule | `{ok: false, readonly: true}` — `preview_transform`'s wording family |

Console errors on payobook: **0**. Responses ≥400: **0 / 80**. Layout clean at
**1450** and **1920** — card 1040 px, 0 children outside its bounds, no
horizontal page scroll, body scrolls inside itself at both.

### JavaScript suite — **15/15 green in the browser**

`.ig-c8-shots/payobook-hoot-pb-integrations-green.png`. It took three rounds,
and each round is a finding:

1. `expect(...).toBeTruthy` — **hoot has no such matcher** (its family is
   `toBe` / `toEqual` / `toMatch` / `toBeGreaterThan` / `toBeCloseTo` /
   `toBeWithin` and the DOM ones), and hoot counts `expect()` called without a
   matcher as a FAILURE rather than a vacuous pass. `node --check` parses it
   perfectly happily.
2. `_t` on a LAZY string throws *"translations have not been loaded"* the
   moment a PURE test reads it. The branch returning `""` passed, so the test
   looked like it exercised all three branches while two could not evaluate at
   all. Fixed with the framework's own `patchTranslations()`.
3. W156's corollary, concretely: the tests page loads
   `a3e5252/web.assets_unit_tests.min.js` and I had warmed `09c2e6f` (the
   *setup* bundle). Forcing a different URL updates a different cache key and
   proves nothing — read the href out of the page, then force **that**.

### Three defects the live pass found in the UI

| # | what | why it mattered |
|---|---|---|
| 1 | **WORKEDHRS opened read-only** | the composer decided the lane with `builder_mode === "python" \|\| has_python`. `has_python` means "a python expression is still STORED on this row" — true of exactly DEPCOUNT and WORKEDHRS after the migration, because it deliberately keeps the original program as provenance. The one decision that makes the conversion auditable was also the one locking the owner out of both converted rules. The lane is `builder_mode` alone; `has_python` is now rendered for administrators as a collapsed *"How this rule was written before"* |
| 2 | the two matcher/translation faults above | a suite that runs but whose assertions cannot execute is W81 wearing a green local gate |
| 3 | *(not a defect)* | an apparent "lane switch loses the value steps" was my own probe double-clicking the switch. A clean single-click test shows `["days"] → formula → ["days"]` and the rail returning to the identical `5 records → 3 match → 4` |

## Deploy — the whole cycle

| unit | what | result |
|---|---|---|
| `c8deploy` | WP-1 / WP-2 / WP-4, three databases | `EXIT_payobook=0` `EXIT_abm=0` `EXIT_payobook_template=0` `ACTIVE=active` |
| `c8tests` | first scoped run | died in pre-flight — **W158** |
| `c8tests2` / `c8tests3` / `c8tests4` | scoped suite | 144 tests, 1 pre-existing failure |
| `c8deploy2` | WP-3, three databases | `EXIT_payobook=0` `EXIT_abm=0` `EXIT_payobook_template=0` `ACTIVE=active` |
| asset-only publishes ×3 | the three live fixes | no window needed (W136's corollary) |

Final versions, identical on all three databases:

```
pb_hr_payroll_formula 19.0.1.60.0
pb_integrations       19.0.1.8.0
pb_import_kit         19.0.1.9.0
```

`payobook=200`, `abm=200`, `systemctl is-active odoo-server = active`.

## Left on the live databases, deliberately

Two rules on payobook's **Demo HRIS** connector, built during the novice pass
and kept because they work and they demonstrate the feature: `DEPENDANTS` and
`ANNUALLEAVEDAYSAPPRO`. Delete them if they are unwanted — nothing depends on
them. The gate-probe rule `C8SMUGX` was removed. Nothing on abm was created,
edited or synced; **the owner's connector id 1 was never touched** and no
`Fetch fields` or sync action was pressed anywhere.

## Ledger

**W158–W167** appended to `docs/WORKFORCE_REDESIGN_CONVENTIONS.md` (168 rules
total): the `--no-http` test-port trap; a golden template having no
administrator; `TransactionCase`'s `assertRaises` refusing a tuple; a `str`
subclass as spreadsheet-cell semantics; preview==execution by construction;
fail-open vs fail-closed needing a test that breaks what it asks; a discovery
ladder's last layer leaking into a second caller's question; a silent correction
blinding its own validator; two agents sharing one git index; and W128's scan
needing `sudo` or it cannot fail.
