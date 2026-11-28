# SCHEMECTX Phase 2 — contract components follow the person's scheme and country

Read `SCHEMECTX_LEDGER.md` first, then `RUNSRC_LEDGER.md` §0, then the Phase 1
report (`SCHEMECTX_PHASE_1_REPORT.md`) for anything it corrected.

## 1. The defect, as the owner saw it

People → Contracts → open a contract → **Components** tab: "Demo Nguyen Thi Mai"
shows 19 components, and the list grows on every contract each time a payroll
scheme is added — Indian components on Vietnamese people and vice versa. The
owner attaches people to schemes in Mapping → **Who is paid by what**, and wants
the contract to show only the components of the scheme (and so the country)
that pays that person; and wants reports / analytics / insights to group and
filter by country and by payroll scheme.

## 2. Scope

1. The contract drawer's Components tab, its "add a component" list and its
   count badge are scoped to the scheme(s) that pay the person.
2. The employee compensation card is scoped the same way.
3. New contracts stop receiving a line for every component in the catalogue.
4. One-off clean-up of the stray lines already stored (owner ruling 10b).
5. Analytics: country comes from the scheme; AI insights and pay run results
   can group/filter by scheme and country.

### Binding non-goals

* Do NOT add a scheme or country column to `hr.contract.advantage.template`.
  The catalogue stays a flat list keyed by `code`; the SCHEME's rules say which
  codes belong to it. (Two schemes may share a code — that is legitimate.)
* Do NOT add a stored scheme field to `hr.contract`. The person carries it.
* Do NOT make `pb_contracts` depend on `pb_scheme_map` or
  `pb_hr_payroll_formula`. Probe with `self.env.get(...)` / `in _fields`.
* NEVER delete, zero, or silently hide a line that holds a non-zero amount or a
  non-empty text value.
* Do NOT change how a payslip reads a contract line. No payslip amount may move.
* A read RPC never writes (rule 8): opening the drawer creates nothing.

## 3. Verified plumbing — do not re-derive

| Fact | Where |
|---|---|
| Line model `hr.contract.advantage` (`contract_id`, `advantage_template_id`, related `advantage_template_code`/bounds, `amount`); typed extension `value_type`, `text_value` | `om_hr_payroll/models/hr_contract.py:7-43`; `pb_hr_payroll_formula/models/contract_advantage_typed.py:26-47` |
| Catalogue `hr.contract.advantage.template` — name, code, bounds, default; NO company/country/scheme | `om_hr_payroll/models/hr_contract.py:128-136` |
| **The fan-out**: `HrContract.create` does `Template.search([])` and creates one line per template. Old-style `@api.model def create(self, vals)`, uses `record[0]` | `om_hr_payroll/models/hr_contract.py:117-125` |
| Templates are created per scheme rule, matched by code only | `pb_hr_payroll_formula/models/payroll_import_batch.py:5156-5181` (`_get_or_create_advantage_template`), rules from `_get_contract_component_rules :5151-5154` |
| VN profile adds 19 templates | `pb_payroll_mapping_vn/hooks.py:23-53`; `models/vn_profile.py:150`; `models/formula_config.py:186-204` |
| Writers ALREADY get-or-create a missing line — nothing depends on the fan-out having run: import sync `payroll_import_batch.py:5227-5369` (creates at `:5333`, `:5352`); Records Desk `pb_records/models/pb_records_desk.py:1154-1175`; drawer save `pb_contracts/models/pb_contract_360.py:1361` | — |
| Readers that iterate existing lines | `payroll_import_batch.py:2156`, `:5184`; `pb_comp_ben/models/employee_comp.py:246-266` |
| Drawer: `get_contract_360 :499` → `_cd_payload :515` → `_cd_components :722-805`; lines by contract only `:730`; `addable` = whole catalogue `:784`; scheme used only as a tie-break in `_cd_rule_by_code :306-336`; optional-model probe precedent `:318` | `pb_contracts/models/pb_contract_360.py` |
| Drawer UI rows `contract_360.xml:264-325`; badge `:176` ← `contract_360.js:511` (`compRows.length + staged adds`); getters `:505-507` | `pb_contracts/static/src/` |
| **The precedent to copy** — scheme-scoped component rules (contract components OR text components) | `pb_records/models/pb_records_desk.py:185-193` `_component_rules(config_id)` |
| Person → scheme, stored on the employee: `pb_paid_by_id` (regular run), `pb_paid_by_advance_id` (advance run), `pb_paid_by_stale`; refreshed by `_pb_recompute_paid_by :116` + cron `:182` | `pb_scheme_map/models/hr_employee.py:47-60` |
| Authoritative resolve (when the stored value is stale): `pb.scheme.map.resolve(employee, cycle_type, on_date)` | `pb_scheme_map/models/pb_scheme_map.py:271` |
| Scheme carries country | `formula_config.py:104-120` |
| Explorer dimension registry: `'scheme'` (`col: config_id`) and `'country'` (`col: company_id`, `derive: 'country'`) already exist; filters `:157-175`; derive `:921`; where-clause `:1861`; facts carry `config_id` `pb_fact.py:105-113, 175-181, 205-211` | `pb_explorer/models/pb_explorer.py:112-137` |
| AI insights query payslips/employees with NO scheme or country dimension | `pb_payroll_ai_insights/models/payroll_data_query.py:497, 653, 711` |
| Results group by `formula_config_id`, no country | `pb_payrun_results/models/payrun_results.py:93-163` |
| Decision Room already scopes by country and scheme — leave it | `pb_decision_room/models/pb_decision_scope.py:38` |
| "Who is paid by what" is a tab of the Mapping home — find its action/params in `pb_scheme_map` (the TIDY programme added the door; `TIDY` ledger T-entries) | — |

## 4. Architecture

### 4.1 The one question, answered in one place (pb_hr_payroll_formula)

On `hr.formula.config`:

```python
@api.model
def schemes_for_employee(self, employee):
    """The scheme(s) that pay this person: regular first, then advance.
    Empty recordset when pb_scheme_map is absent or nobody covers them."""

@api.model
def component_scope_for_employee(self, employee):
    """{'known': bool, 'schemes': [{'id','name','country_code','country_name'}],
        'codes': set()}  — codes = contract + text component rule codes of
        those schemes (same domain as pb_records._component_rules)."""
```

`schemes_for_employee`: if `'pb_paid_by_id' in employee._fields` read the stored
fields; when `pb_paid_by_stale` is set (or both are empty) and `pb.scheme.map`
is installed, fall back to `resolve()` — a READ, it must not store. `known` is
False when the scheme map is not installed at all → callers behave exactly as
today (test 8). Refactor `pb_records._component_rules` to share the domain only
if it is a two-line change; otherwise leave it.

### 4.2 Drawer (`pb_contracts`)

`_cd_components` asks `self.env.get('hr.formula.config')` for the scope, then:

* **known + schemes found** → rows are the scheme's component set:
  * a line whose code ∈ codes → normal row;
  * a code ∈ codes with NO stored line → a **virtual row** (`id: False`,
    `template_id` set, amount 0, same fills/bounds chips). Editing it goes
    through the drawer's existing add path (`:1361`) — verify that save handles
    `id: False` rows as an add; extend minimally if not. The read creates nothing.
  * a line whose code ∉ codes and holds a value → `other_rows` (same row shape);
  * a line whose code ∉ codes and is empty → dropped from the payload.
  * `addable` = catalogue ∩ codes, minus what is shown (normally empty now —
    hide the "add" affordance when empty rather than show a dead control).
* **known + no scheme** → `rows` = only lines that hold a value, plus
  `scope_state: 'unassigned'`.
* **not known** → today's behaviour, unchanged.

Payload adds `scope: {state, schemes:[…]}`. `count` = `len(rows)` (not other).
`total` unchanged in meaning (sum of shown + other — it is what the contract holds).

UI (`contract_360.xml/js/scss`), to the design bar:

* A scope strip at the top of the tab: Lucide `layers` + **"Rize Vietnam
  Payroll"** + country chip **"Vietnam"**; two schemes → both, labelled
  "Regular" / "Advance". Clicking the scheme name opens it in the studio
  (`doAction`, with a way back).
* "Other values on this contract" — a folded group under the list with a count,
  one line of explanation: "Held on this contract, but not used by the scheme
  that pays this person." Rows stay editable so a value can be cleared.
* Unassigned empty state: Lucide `route` icon, "No payroll scheme pays this
  person yet", one sentence, primary button **"Choose who is paid by what"** →
  the Mapping tab. Zero dead ends.
* Motion: the list re-flows with the kit's existing row transition; no new
  animation library. 390px must not overflow. EN + VI.

### 4.3 Stop the fan-out (`om_hr_payroll`)

Replace the `create` override body: keep a modern `@api.model_create_multi`
create that calls `super()` and returns — **no** template loop. Nothing depends
on it (§3: every writer get-or-creates). Before removing, grep the repo's
custom modules for code that assumes `contract.advantages_ids` is complete
(e.g. indexing by code without a guard) and for tests asserting the fan-out;
fix/adjust those. `om_hr_payroll` is ours (not in the server's odoo git clone —
confirm with `git -C /odoo/odoo-server ls-files addons | cut -d/ -f2 | sort -u`
before deploying it; if it IS standard there, stop and report instead).

Prove pay neutrality: `payroll_import_batch.py:2156` iterates existing lines —
show that an absent line and a zero line produce the same payslip inputs.

### 4.4 Comp card (`pb_comp_ben`)

`employee_comp.py:246-266`: skip lines outside the scope unless they hold a
value. `pb_comp_ben` already depends on `pb_hr_payroll_formula`. Add a `tests/`
package (none exists) with the one test below.

### 4.5 Clean-up (owner ruling 10b) — a script, not a migration

`tools/schemectx_cleanup_contract_lines.py`, run with `odoo-bin shell` **with
the service stopped** (ledger: shell vs running registry hang), per database,
`--dry-run` by default:

1. For each open/draft contract whose employee has ≥1 resolved scheme: select
   lines with code ∉ scope codes AND `amount` in (0, NULL) AND empty `text_value`.
2. Write them to `/root/schemectx_cleanup_<db>_<date>.csv`
   (line id, contract id, employee, template id, code, amount, text) — this is
   the rollback file; the script has a `--restore <csv>` mode that recreates them.
3. `--apply` deletes them and prints counts: contracts touched, lines deleted,
   lines kept-because-non-zero, people skipped-because-unassigned.
4. People with no scheme, and archived contracts, are skipped entirely.

Order: `pg_dump` the DB first → dry-run on `rztest` → apply on `rztest` →
re-run the Phase 2 tests + a payslip recompute diff on `rztest` → then `rize`,
then the remaining four. If a DB has nobody assigned (likely `payobook_template`)
it deletes nothing — that is correct, report it.

### 4.6 Analytics

* **Explorer**: the `country` dimension derives from the fact row's scheme
  country when `config_id` is set, company country otherwise (`:921` + the
  where-clause at `:1861` so the filter agrees with the grouping). An India
  scheme inside a Vietnamese company must land under India.
* **Pay run results**: add the scheme's country (code + name) beside each
  scheme group so the screen can label/group by it.
* **AI insights**: `_query_salary_data`, `_query_payroll_cost_data`,
  `_query_department_data` accept optional `scheme` and `country` filters and a
  `group_by` of `scheme` / `country`, joined through the payslip's scheme
  (probe the field; module stays installable without the formula engine). Add
  both words to whatever intent/keyword table routes a question to a query so
  "cost by country" and "by payroll scheme" resolve. Show amounts with the
  scheme currency dict from Phase 1 — never sum two currencies into one number;
  when a grouping mixes currencies, return one row per currency.

## 5. Test cases (report each by number, PASS/FAIL + evidence)

1. Person on a VN scheme → drawer rows ⊆ that scheme's codes.
2. Same person with a stray non-zero IN line → it is in `other_rows`, not `rows`, not lost.
3. Stray zero line → in neither list; still in the database (before clean-up).
4. Scheme code with no stored line → virtual row `id False`; opening the drawer wrote nothing (line count unchanged).
5. Saving a value on a virtual row creates exactly one line.
6. Person on regular + advance schemes → union of both; strip shows two schemes.
7. Person with no scheme → `scope.state == 'unassigned'`, rows = valued lines only.
8. Registry without `pb_scheme_map` fields (simulate by patching the probe) → payload identical to pre-change.
9. `addable` ⊆ scope codes.
10. New contract → zero lines created; import sync afterwards creates only the file's components.
11. Payslip neutrality: recompute a fixture slip with zero-lines present vs absent → identical lines.
12. Comp card ignores empty out-of-scheme lines, keeps valued ones.
13. Clean-up dry-run deletes nothing; apply never selects a non-zero or text-valued line; `--restore` recreates the exact set.
14. Explorer: fact row with IN scheme under a VN company groups AND filters as India.
15. AI insights: group by scheme, group by country, mixed currencies → one row per currency.
16. Existing suites green: `/pb_contracts`, `/pb_records`, `/pb_scheme_map`, `/pb_explorer`, `/pb_payroll_ai_insights`, `/pb_payroll_mapping_vn`, `/om_hr_payroll`, `/pb_hr_payroll_formula` (pre-existing reds listed separately).

## 6. Deploy + verify

Ledger rule 13. Bump every manifest touched. PO parse gate. All six DBs;
hash-compare; versions per DB; assets purge + `web.assets.version`; restart.

Chrome MCP, `rize.payobook.com`, 1440 + 390, console read:

* a. Contracts → "Demo Nguyen Thi Mai": strip names the scheme + Vietnam; the list is that scheme's components only; badge matches.
* b. Attach one demo team to **Rize India Payroll** in Who is paid by what (the owner cleared free testing; note exactly what you attached so it can be undone, and prefer a DEMO-prefixed person/team) → that person's drawer shows the India scheme's components and ₹.
* c. A person in an uncovered team → the unassigned state; its button lands on Who is paid by what.
* d. Edit a virtual row, save, reopen → value held.
* e. Explorer: group by Country and by Payroll scheme.
* f. Ask the insights assistant "payroll cost by payroll scheme".

## 7. Commits

(1) scope helper, (2) drawer + comp card, (3) fan-out removal, (4) clean-up
tool, (5) analytics. Explicit staging, no push,
`Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.

## 8. Report back

`docs/handovers/SCHEMECTX_PHASE_2_REPORT.md`: tests by number; clean-up counts
per DB and the CSV paths; what was attached on rize for validation; handover
facts that were wrong; new SC gotchas in the ledger; commit hashes; anything
not browser-validated and why. Return a ≤250-word summary.
