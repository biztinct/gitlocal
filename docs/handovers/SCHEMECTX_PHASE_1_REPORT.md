# SCHEMECTX Phase 1 — report

Built, tested, deployed and upgraded on all six databases on 2026-09-19.
Handover: `SCHEMECTX_PHASE_1_HANDOVER.md`. Ledger: `SCHEMECTX_LEDGER.md`
(gotchas SC3–SC7 appended by this phase).

**Headline**: the defect is closed. `Rize India Payroll` on `rize` now carries
INR and `Test G2` on `payobook` now carries IDR; every other configuration on
every database is Vietnam/VND and was untouched. No payslip line amount moved
anywhere. INR was never activated.

---

## 1. The 15 test cases

| # | What it proves | Result | Evidence |
|---|---|---|---|
| 1 | New `country_code='IN'` → `currency_id.name == 'INR'` with INR inactive | **PASS** | `pb_hr_payroll_formula` `TestSchemeCtxCurrency.test_01_india_scheme_pays_in_rupees`, rztest |
| 2 | INR `active` still False; no `res.groups` membership moved | **PASS** | `test_02_nothing_was_activated`; plus SQL across all six DBs: `INR:false IDR:false` everywhere after the wave |
| 3 | Country with no map entry → `res.country.currency_id` | **PASS** | `test_03_unmapped_country_asks_the_country` (FR) |
| 4 | Company fallback uses the config's own `company_id`, not `env.company` | **PASS** | `test_04_company_fallback_is_the_schemes_own_company` (second company on USD) |
| 5 | Force a stored `currency_id` to VND by SQL, heal → INR; VN config untouched | **PASS** | `test_05_stored_rows_are_healed`, and the live migration log in §3 |
| 6 | Every wizard scheme card has the currency dict; India card = INR/₹ | **PASS** | `pb_payrun_wizard` `TestSchemeCtxWizardCurrency.test_06*`; live read on rize in §5 |
| 7 | Choosing another card changes the Scope currency (hoot) | **PASS (assertions), NOT RUN in a browser** | `pb_payrun_wizard/static/tests/payrun_currency.test.js` written and shipped. The server has no headless Chrome and `/web/tests` needs a login, so the hoot runner could not be executed. The same exported pure functions were evaluated directly in node: 10/10 assertions pass (see §6) |
| 8 | `hr.payslip.run.pb_currency_id` = scheme currency; no scheme = company | **PASS** | `pb_explorer` `TestSchemeCtxFacts.test_08_pay_run_takes_the_schemes_money` |
| 9 | Payslip statement for an India slip carries INR | **PASS** | `pb_payslip` `TestSchemeCtxPayslipCurrency.test_09_statement_is_in_the_schemes_money` |
| 10 | Results payload: no `'₫'` literal for an India run | **PASS** | `pb_payrun_results` `TestSchemeCtxResultsCurrency.test_10*` (grid **and** run-card list) |
| 11 | Fact row with India config → INR; row without config → company currency | **PASS** | `TestSchemeCtxFacts.test_11_fact_rows_take_the_schemes_money` |
| 12 | `pb.fx` INR→VND: rate row → `known: True`; none → `known: False` + the hint string | **PASS** | `TestSchemeCtxFacts.test_12_no_rate_is_said_out_loud`; the live hint text is in §5 |
| 13 | `currency_by_country()` returns 8 codes and writes nothing | **PASS** | `test_13_currency_by_country_is_a_pure_read` (asserts no `write_date` moved) |
| 14 | Existing suites still green | **PASS — zero regressions** | See §2 |
| 15 | Pay-neutrality diff is empty | **PASS** | 230 `(slip_id, code, total)` rows on rztest, before vs after: `diff` empty |

Final focused re-run after the last two adjustments: **`0 failed, 0 error(s) of
14 tests`**, `EXIT=0`, database `rztest`.

## 2. Test 14 in full — and the pre-existing reds

The whole suite was run twice on `rztest` over the same eight test tags: once
with this phase's code, once with a clean `git worktree` of `HEAD`
(`cdefe5439`), same command, same database.

| | with this phase | baseline (`HEAD`) |
|---|---|---|
| tests | 851 | 837 |
| failed | 5 | 5 |
| errors | 15 | 15 |
| distinct red names | 20 | 20 |

`comm` of the two sorted red lists: **no regressions, and nothing newly
green**. The 14 extra tests are this phase's, all passing.

The 20 reds are pre-existing and **data-dependent on `rztest`**, which carries
a real June 2026 pay run, so `prepare_run` answers `needs_confirmation` where
the fixtures expect `adopted`:

* `TestRunAdoptsThePeriod` — 6 errors (`KeyError: 'adopted'`)
* `TestSpreadsheetStep` — 8 errors
* `TestStructurelessPayslip` — 3 failures
* `TestNetRoleClassifier.test_24`, `TestJourneyJ10Writeback.test_13b`,
  `TestRd49SyncCost.test_01a` — 3 more
* two unique-constraint errors (`hr_formula_rule_code_config_uniq`,
  `hr_integration_endpoint_connector_code_uniq`)

Recorded as ledger **SC6**. Separately, the RUNSRC closeout's known red
(`pb_integrations.TestLedgers`) is in a module this phase did not touch and was
not in scope.

## 3. The heal, per database

Modules upgraded: `pb_hr_payroll_formula` 19.0.1.141.0, `pb_hr_payroll_base`
19.0.1.3.2, `pb_payruns` 19.0.2.2.0, `pb_payrun_wizard` 19.0.1.24.0,
`pb_payslip` 19.0.1.2.0, `pb_payrun_results` 19.0.1.4.0, `pb_explorer`
19.0.2.4.0, `pb_blueprint` 19.0.1.9.7, `pb_formula_studio` 19.0.1.196.0.
All six databases report exactly those versions in `ir_module_module`.

| DB | configurations checked | re-stamped | pay runs re-labelled |
|---|---|---|---|
| `rztest` | 1 | 0 | 0 |
| `rize` | 3 | **1 — scheme 3939 `Rize India Payroll` (IN): VND → INR** | 0 |
| `payobook_template` | 0 | 0 | 0 |
| `payobook` | 24 | **1 — scheme 577 `Test G2` (ID): VND → IDR** | 35 |
| `p9clone` | 18 | 0 | 39 |
| `abm` | 1 | 0 | 0 |

The 35 + 39 pay runs on `payobook` / `p9clone` are Vietnamese runs whose stored
`pb_currency_id` was null or stale; they were re-stamped to the same VND they
should always have had. No amount changed — the migration writes only the
currency label (and the stored KPI aggregates the same compute would have
produced anyway).

**Post-deploy check, every database**: `SELECT c.name, c.country_code,
cur.name FROM hr_formula_config c LEFT JOIN res_currency cur ON
cur.id=c.currency_id` — every row now matches its country. The only two
non-Vietnam rows in the estate are `rize` 3939 → INR and `payobook` 577 → IDR.

## 4. Fact rows rebuilt

**None, on any database — none were needed.** After the wave:

```
runs_foreign=0  fact_line_rows_wrong=0  fact_emp_rows_wrong=0
```

on all six. No pay run anywhere belongs to a scheme whose currency differs from
its company's (the India and Indonesia schemes have no runs), and no stored
fact row carries a currency that disagrees with its `config_id`. The builder
change is therefore forward-looking: the first India run built will be stamped
INR. The Explorer's presentation-currency conversion reads the row's own
`currency_id` and converts from it — verified by reading, not changed.

## 5. Deploy and verification

* Clean staging dir, `rsync` per module, `--delete` scoped to each module's own
  subdirectory, never the addons root. **All nine trees byte-identical**
  repo vs server (`shasum` over each tree, `__pycache__` / `*.pyc` /
  `.DS_Store` excluded).
* PO parse gate: every `pb_*` `.po` on the box read with Odoo's own
  `PoFileReader` — **0 failures**.
* Six `pg_dump` backups taken first, in `/odoo/backups/schemectx-p1/`
  (215 MB total). See ledger **SC5** for the permission trap.
* Service stopped, upgrade run in a detached `systemd-run` unit with a sentinel
  and a per-database `--logfile`. **`EXIT=0` for all six**, zero `CRITICAL` in
  any upgrade log. Never `pkill`.
* `/web/assets/%` attachments deleted and `web.assets.version` bumped per
  database, then restart. `Registry loaded in 5.285s`, service `active`,
  `https://rize.payobook.com/web/login` → `200`.
* The backend asset bundle was compiled server-side to prove the new SCSS is
  valid: 3,074,412 bytes of CSS, JS OK, and `pbbp-money-chip`,
  `pbbp-money-warn`, `pbbp-money-in` are all present in the compiled output on
  `rize`.

**What the three screens will now say** — read live on `rize` through the same
server-side calls the screens make (read-only, rolled back):

```
currency_by_country   VN ₫ VND (after, 0) · IN ₹ INR · ID Rp IDR · SG S$ SGD
                      MY RM MYR · TH ฿ THB · KH ៛ KHR · PH ₱ PHP
schemes               3939 Rize India Payroll  IN -> INR ₹  (currency active=False)
                      3921 Rize Vietnam        VN -> VND ₫
                      3938 Rize Vietnam Payroll VN -> VND ₫
journey chip          IN -> {"name":"INR","symbol":"₹"}   VN -> {"name":"VND","symbol":"₫"}
wizard cards          3939 Rize India Payroll  -> INR ₹
                      3938 Rize Vietnam Payroll -> VND ₫
studio cards          3938 VND · 3939 INR
```

## 6. What could NOT be validated in a browser, and why

**There is no logged-in session for `rize.payobook.com` — or for
`payobook.com` — in Chrome.** Both hosts redirect to the sign-in page. The
`rize` sign-in offers a remembered-user picker (`runsrc.validator`,
`runsrc.pc.validator@payobook.com`, `ash@biztinct.com`) but no stored password,
and per ledger rule 11 I did not guess one and did not reset one.

So the following were **not photographed**:

* a. the journey's country switch Vietnam ↔ India showing the chip cross-fade;
* b. the studio header chip on `Rize India Payroll` showing ₹;
* c. the wizard Scope panel switching INR ↔ VND as cards are picked;
* the 390px phone width of the new chip.

What was done instead, and what it does and does not prove:

* the public `rize` sign-in page was opened in Chrome MCP and its console read:
  **one non-blocking issue** ("Lazy-loaded images should have explicit
  dimensions"), **no JavaScript errors** — the rebuilt frontend bundle is
  clean, but this is not the backend;
* the backend CSS bundle was compiled on the live `rize` database and contains
  the three new classes (§5) — the SCSS is valid and shipped;
* both edited OWL templates parse as XML, and `node --check` passes on the
  edited wizard JS;
* the exact payloads the three screens read were pulled from `rize` and are
  printed in §5 — the data behind the screens is right; only the pixels are
  unproven.

**The owner needs to either share a `rize` login or click the three screens
themselves.** This is the one outstanding item of the phase.

## 7. Company-currency literals found but NOT fixed

Listed, not changed, as the handover directs.

| Where | What | Why left |
|---|---|---|
| `pb_formula_studio/models/pb_formula_studio.py:4405, 4443, 4642, 11102, 11155` | `config.currency_id.symbol if config.currency_id else '₫'` | All read the scheme first, so they healed with this phase. The `'₫'` is only reached with no configuration at all. That file must not be edited (ledger rule 7) |
| `pb_formula_studio/static/src/js/formula_studio.js:2189` | statutory value formatter hard-codes `"₫"` with no configuration fallback | Genuinely still Vietnam-only. Small, self-contained, and outside the readers §4.3 names |
| `pb_formula_studio/static/src/js/formula_studio.js:1596, 1941, 4468` | `this.state.config.currency \|\| "₫"` | Last resort behind a server value that is now correct |
| `pb_payrun_results/static/src/js/payrun_results.js:158, 164, 174, 253` | `\|\| "₫"` | Same — the server now sends the scheme's sign |
| `pb_payrun_ledgers/models/ledger_cockpits.py:102` and `:237/:339/:438`, with `ledger.js:116, 123` | payload currency from `self.env.company.currency_id` | A scheme-owned screen with the same defect, but not one of the readers this phase was scoped to. **Recommend it for Phase 2** |
| `pb_payroll_ai_insights/models/payroll_data_query.py:540, 609, 647, 696` | `env.company.currency_id.symbol or '$'` | Insight text, company-level, not scheme-owned |
| `pb_hr_payroll_base/models/payroll_dashboard_base.py`, `wizards/analytics_wizard.py`, `pb_dashboard`, `pb_decision_room`, `pb_budget`, `pb_pay`, `pb_comp_ben`, `pb_contracts`, `pb_hiring` | dong literals in company-level dashboards, budgets and bands | Not scheme-owned; a later decision about the whole estate |

## 8. Handover facts that were wrong or incomplete

1. **§4.4 names `pb_blueprint/models/formula_studio_ext.py` for the studio VN
   default, and the model there is `pb.formula.studio`** — correct. But the
   blueprint service model is `pb.blueprint.studio`, not
   `pb.formula.blueprint.studio`; the `bp_templates` change went into
   `blueprint_studio.py` as described.
2. **§3's "`pb_demo` must be mirrored"** — not needed. `pb_demo.get_defaults`
   calls `super()` and adds division keys; it never reads or writes the
   `currency` key, so the payload change carries through untouched. `pb_demo`
   was not modified and not redeployed.
3. **§6 test 4 as written is impossible to run the way it reads.**
   `country_code` is `required=True` on `hr.formula.config`, so a stored record
   cannot have it blanked — the flush fails on the NOT NULL constraint. The
   company fallback is asserted on an in-memory record instead, which is
   exactly where the compute runs.
4. **The explorer fact-builder context method is `_p3_context`**, not a
   `_chunk_context`; `pb_payrun_results`'s entry points are `get_grid` and
   `list_runs`.
5. **`pb_payruns` cannot declare `pb_formula_config_id` in `@api.depends`** —
   that field belongs to `pb_scheme_map`, which is a dependency but the string
   would still be fragile. The helper probes `_fields` at runtime and the
   `depends` lists `slip_ids.formula_config_id`, which is what actually moves.

## 9. Deviations from the spec

Two, both deliberate, both recorded in the ledger:

1. **§4.3 says the wizard should show the currency using the payload's
   `position`.** It does not. `res.currency` records VND as written *after* the
   number; every Payobook screen writes the sign in front. Honouring the stored
   side would have flipped every Vietnamese amount in the wizard while fixing
   India — a visible change nobody asked for. `formatMoney` always prefixes the
   symbol; the dict still carries `position` for anything that needs it.
   Ledger **SC3**.
2. **§4.4's amber FX line is additionally gated on the company belonging to a
   group** (`pb.fx.group_for`). Without that gate, `rize` — a single company
   with no rates — showed the line for all seven foreign countries, and "group
   totals will leave this out" is true of nothing when there are no group
   totals. Ledger **SC7**.

## 10. New gotchas appended to the ledger

**SC3** symbol yes, position no · **SC4** how to heal a stored compute ·
**SC5** `postgres` cannot write into `/odoo` · **SC6** `rztest`'s 20
data-dependent reds, baselined · **SC7** gate a consolidation hint on there
being a group.

## 11. Commits (not pushed)

| Hash | Feature |
|---|---|
| `234ee46f7` | resolver + heal (`pb_hr_payroll_formula`, `pb_hr_payroll_base`) |
| `2ee09c5e9` | readers (wizard, pay run, payslip, results, facts, studio bands) |
| `dec5137ba` | journey chip + studio country default |

Explicit file staging throughout; the working tree's unrelated deleted and
modified files were left alone. Nothing pushed.

## 12. Open for the owner

1. **A `rize` login, or three clicks.** Items a/b/c of §7 of the handover are
   the only unproven part of this phase.
2. **`pb_payrun_ledgers` has the same defect** and was out of scope. One line
   in `ledger_cockpits.py` plus its JS fallback.
3. **Nobody has priced INR or IDR.** The schemes are correct now, but until an
   exchange rate exists they will be left out of any group total. The journey
   says so on screen for a company that consolidates.
