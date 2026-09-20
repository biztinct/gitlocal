# SCHEMECTX Phase 1 — a scheme's currency follows its country

Read `SCHEMECTX_LEDGER.md` first (binding rules + gotchas), then
`RUNSRC_LEDGER.md` §0 (deploy contract, six databases).

## 1. The defect, as the owner saw it

On `rize.payobook.com` the scheme **Rize India Payroll** has country India, yet
the pay run wizard's Scope panel says **Currency VND** and amounts show ₫.

## 2. Scope

1. The scheme resolves the right currency for its country even when that
   currency is inactive, on create AND for every scheme already stored.
2. Every screen and stored figure that belongs to a scheme shows/stamps the
   scheme's currency, falling back to the company's only when there is no scheme.
3. The guided journey's step 1 shows, live beside Country, what the scheme will
   pay in — the help text already promises "Decides the currency".

### Binding non-goals

* Do NOT activate any currency (ledger rule 9).
* Do NOT add a manual currency picker. Country decides. (A stored override is a
  later decision for the owner.)
* Do NOT touch exchange-rate logic in `pb_group/models/pb_fx.py`; only read it.
* Do NOT convert or restate any historical amount. Only the currency *label*
  stamped on rows changes, and only where the scheme's currency differs from
  the company's.
* Do NOT edit `pb_formula_studio/models/pb_formula_studio.py` (rule 7).

## 3. Verified plumbing — do not re-derive

| Fact | Where |
|---|---|
| Root cause: `_compute_currency_id` searches `res.currency` by name with the default active filter, then `or self.env.company.currency_id`. INR is inactive in base data → VND | `pb_hr_payroll_formula/models/formula_config.py:851-864` |
| `@api.depends('country_code')` only, so the stored wrong value never heals by itself | same |
| Same defect pattern (explicit `('active','=',True)`) | `pb_hr_payroll_base/models/hr_payroll_structure_base.py:151-154`; its `res.country.currency_id` fallback `:142-144` |
| Correct lookup precedent (`active_test=False`) | `pb_explorer/models/pb_explorer.py:1097-1099, 1114`; `pb_demo/models/demo_generator.py:99` |
| Journey create writes `name, country_code, cycle_type, company_id, state` only — currency relies on the compute | `pb_blueprint/models/blueprint_studio.py:302` (`bp_start`), `:350-356` |
| Journey step 1 form + Identity card; help text "Decides the currency…" | `pb_blueprint/static/src/js/step_start.js:25`; `static/src/xml/steps.xml:40-90`, help `:71`; country list `blueprint_studio.py:220` |
| Wizard payload: `'currency': self.env.company.currency_id.name or 'VND'` | `pb_payrun_wizard/models/pb_payrun_wizard.py:376` |
| Wizard scheme cards carry no currency | same file `_scheme_cards :64-103`; JS `static/src/js/payrun_wizard.js:413` (`chosenScheme`); Scope panel `static/src/xml/payrun_wizard.xml:135-139` |
| Pay run currency from company | `pb_payruns/models/hr_payslip_run.py:249-250` (`pb_currency_id`), computed `:319, :326`; also `:534, :704` |
| Payslip statement `cur = company.currency_id` | `pb_payslip/models/hr_payslip.py:50` → `:163` |
| Results: primary config symbol OK at `:258`, company/`'₫'` fallback at `:364-372` | `pb_payrun_results/models/payrun_results.py` |
| Facts stamp `currency_id` from a company map although `config_id` is on the same row | `pb_explorer/models/pb_fact_builder.py:439` (row `:436`), map `:583-586`; fields `pb_explorer/models/pb_fact.py:115, :182, :214` |
| Already scheme-currency (heal once the compute is fixed): studio chip `pb_formula_studio.py:1337` → `studio.xml:54`; blueprint `blueprint_outputs.py:104`, `blueprint_calendar.py:74-75, 367-368`, `blueprint_finish.py:193`; payslip render `pb_hr_payroll_formula/models/hr_payslip_formula.py:1369-1370` | — |
| Studio's other create path hard-defaults VN | `pb_formula_studio/models/pb_formula_studio.py:14118-14123` |
| FX: `_as_currency` already searches with `active_test=False`; `rate()` returns `known: False` when no rate row exists | `pb_group/models/pb_fx.py:101-104, 126-145, 226, 273` |
| pb_demo overrides the wizard entrypoints — any NEW wizard entrypoint must be overridden there too; changing a payload key of an existing one must be mirrored | `pb_demo/models/demo_payrun.py` |
| Existing tests that assert currency | `pb_blueprint/tests/test_finish.py:280`, `test_tax_calendar.py:340`, `test_blueprint.py:156` |

Line numbers were read on 2026-09-19 at commit `aa52da324`; if one is off by a
few lines, find the quoted code, do not re-investigate the design.

## 4. Architecture

### 4.1 The one resolver (pb_hr_payroll_formula)

In `formula_config.py`:

* Hoist the country→currency-name dict to a module constant `COUNTRY_CURRENCY`.
* `@api.model _currency_for_country(country_code)` — returns a `res.currency`
  record: by name with `.sudo().with_context(active_test=False)`; if absent,
  the `res.country` (by code) `.currency_id`; else empty recordset.
* `_compute_currency_id` uses it, and falls back to
  `record.company_id.currency_id or self.env.company.currency_id` (record's own
  company first — today it ignores it).
* `scheme_currency()` (single record or empty): returns
  `{'id', 'name', 'symbol', 'position', 'decimals'}` from `currency_id`, else
  the company's. `@api.model currency_by_country()` returns the same dict per
  selectable country code — a pure read for the journey.
* Fix the same defect in `hr_payroll_structure_base.py:151-154`.

### 4.2 Heal stored rows

`pb_hr_payroll_formula/migrations/<new version>/post-migrate.py`: recompute
`currency_id` for every config (`active_test=False` on the config search too,
archived schemes included). Log one line per changed row (id, name, old → new).
Bump the manifest to that version.

### 4.3 Readers

Each takes the scheme's currency when a scheme is known, company's otherwise:

* **Wizard**: each scheme card gains `currency` (the dict). The payload's
  top-level `currency` becomes the dict of the pre-selected scheme. JS: the
  Scope panel reads `chosenScheme.currency` so it changes the instant another
  card is picked; show `name` with the symbol ("INR · ₹"). Any amount formatted
  in the wizard's later steps (pay data, compute, review) uses the same dict —
  grep the wizard JS/XML for `₫`, `VND`, `currency` and route them all through
  one formatter. Mirror any payload change in `pb_demo/models/demo_payrun.py`.
* **Pay run** `pb_currency_id`: from the run's scheme (`formula_config_id` or
  whatever the run carries — read the model), company fallback. Add the scheme
  field to `@api.depends`. Stored? then recompute in the migration of `pb_payruns`.
* **Payslip statement** `hr_payslip.py:50`: slip's scheme currency first.
* **Results** `payrun_results.py:364-372`: scheme currency before company; drop
  the literal `'₫'` last resort in favour of the company symbol.
* **Facts** `pb_fact_builder.py`: build a `config_id → currency_id` map once
  beside the company map; row uses it when `cfg_id` is set. After deploy,
  rebuild facts ONLY for runs whose scheme currency ≠ company currency (use the
  builder's existing rebuild entrypoint; report the row counts). Confirm the
  Explorer's presentation-currency conversion treats those rows as foreign
  (it converts from the row's `currency_id` — verify, do not change).
* Grep the custom `pb_*` modules for other `company.currency_id` / `'VND'` /
  `'₫'` literals sitting next to a `config`/`formula_config` in scope. Fix the
  ones on a scheme-owned screen; LIST (don't fix) the rest in the report.

### 4.4 Journey step 1 — the hero moment

`bp_templates` (or `bp_load`, whichever feeds the Identity card — one of them,
not both) returns `currency_by_country`. Under the Country select, replace the
static help with a live chip: Lucide `banknote` icon + **"Pays in ₹ INR"**, the
symbol cross-fading (150ms) when the country changes; keep the rest of the help
sentence ("…the statutory rules and how people are matched."). If `pb.fx`
exists (`self.env.get`) and the scheme currency ≠ the presentation currency and
`rate()` is `known: False`, add one quiet amber line: "No exchange rate for INR
yet — group totals will leave this scheme out until one is added." No dead end:
it is a hint, never a blocker. EN + VI. Phone width (390) must not overflow.

Studio VN hard-default: in `pb_blueprint/models/formula_studio_ext.py`
(`_inherit 'pb.formula.studio'`), wrap that create method so an absent
`country_code` takes the company's country when it is one of the eight codes,
else stays VN. If the method's shape makes a wrap unsafe, leave it and say why.

## 5. Safety rails

* The INR `res.currency` row's `active` must be byte-identical before/after.
* Pay neutrality: no payslip line amount may change. Before deploy, on `rztest`,
  dump `(slip_id, code, total)` for all payslip lines; after upgrade dump again;
  diff must be empty.
* A scheme whose country currency equals the company currency must produce
  byte-identical payloads except for the new `currency` dict shape.
* Read RPCs (`bp_templates`/`bp_load`, wizard open) perform zero writes.

## 6. Test cases (report each by number, PASS/FAIL + evidence)

1. New config `country_code='IN'` → `currency_id.name == 'INR'` with INR inactive.
2. After (1) INR `active` is still False; no `res.groups` membership changed.
3. Config with a country whose currency name is missing → `res.country.currency_id` used.
4. Company fallback uses the config's own `company_id`, not `env.company` (two-company fixture).
5. Migration: force a config's stored `currency_id` to VND via SQL, run the heal, → INR; a VN config untouched.
6. Wizard payload: every scheme card has the currency dict; India card = INR/₹.
7. Wizard JS (hoot): choosing another card changes the Scope currency.
8. `hr.payslip.run.pb_currency_id` = scheme currency; run with no scheme = company.
9. Payslip statement payload for an India slip carries INR.
10. Results payload: no `'₫'` literal for an India run.
11. Fact builder: row with India config → INR; row without config → company currency.
12. `pb.fx`: INR→VND with a rate row `known: True`; without → `known: False`, and the journey hint string is returned.
13. `currency_by_country()` returns 8 codes, and calling it writes nothing (assert no `write_date` moved on any config; or query-count on writes = 0).
14. Existing suites still green: `/pb_blueprint`, `/pb_payrun_wizard`, `/pb_payruns`, `/pb_explorer`, `/pb_hr_payroll_formula` (report pre-existing reds separately — see RUNSRC closeout for the known one).
15. Pay-neutrality diff (§5) is empty.

## 7. Deploy + verify

Ledger rule 13 + RUNSRC ledger §0 rule 5. Modules expected: `pb_hr_payroll_formula`,
`pb_hr_payroll_base`, `pb_blueprint`, `pb_payrun_wizard`, `pb_payruns`, `pb_payslip`,
`pb_payrun_results`, `pb_explorer`, `pb_demo` (if mirrored) — bump each manifest
you touch. PO parse gate first. Upgrade all six DBs; hash-compare trees; compare
versions per DB; purge assets + bump `web.assets.version`; restart; confirm
"Registry loaded" and no CRITICAL.

Chrome MCP on `rize.payobook.com` (1440 and 390, console read, screenshots into
the scratchpad, not the repo):

* a. Payroll configurations → New configuration → switch Country Vietnam ↔ India: chip reads "Pays in ₫ VND" / "Pays in ₹ INR". Do not save a junk scheme — leave without creating, or discard the draft.
* b. Open **Rize India Payroll** in the studio: header chip shows ₹.
* c. Run payroll wizard: pick Rize India Payroll → Scope says INR; pick Rize Vietnam → VND. Do not create a run.
* d. SQL per DB: `SELECT c.name, c.country_code, cur.name FROM hr_formula_config c LEFT JOIN res_currency cur ON cur.id=c.currency_id` — every row's currency matches its country.

## 8. Commits

One per feature, explicit staging, no push: (1) resolver + heal, (2) readers,
(3) journey chip + studio default. Messages in the repo's voice (see `git log`).
End each with `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.

## 9. Report back

Write `docs/handovers/SCHEMECTX_PHASE_1_REPORT.md`: the 15 tests by number;
the heal log per DB (which schemes changed currency); fact rows rebuilt per DB;
the list of company-currency literals found but NOT fixed; any handover fact
that was wrong; new gotchas appended to the ledger as SC3+; commit hashes;
what you could not validate in the browser and why. Return a ≤250-word summary.
