# Integrations Cycle 4 — implementation report (the abm tenant)

> Written incrementally during the cycle, committed at milestones. Read with
> `docs/handovers/integrations/CYCLE4_ABM_SEEDING.md` (the spec) open.
> Ledger binding through **W140**; this cycle appends **W141+**.

## The secrets verdict — FIRST, because the owner asked for it first

**CLOSED, and the answer is DIFFERENT — but the cycle does nothing about it,
per the owner's ruling.**

Three statements, each with its own evidence:

1. **There are no `zoho.*` system parameters anywhere on this cluster.**
   Queried on all four databases:

   ```sql
   SELECT key, length(value), left(value,6)||'...'||right(value,4)
   FROM ir_config_parameter WHERE key ILIKE '%zoho%';
   ```

   | database | rows |
   |---|---|
   | `abm` | **0** |
   | `payobook` | **0** |
   | `acme` | **0** |
   | `payobook_template` | **0** |

   This confirms the handover's pre-verified fact: the `zoho.client_id` /
   `zoho.client_secret` parameters the owner showed live on the **legacy
   production system**, not here. So the literal comparison the ruling asked
   for — hardcoded pair vs `ir.config_parameter` rows — has no rows on this side
   to compare against.

2. **The comparison is answerable anyway, because the owner has already
   re-homed those credentials into the new Integration screens — on `abm`.**
   WP-1 found a Zoho connector on `abm` that this program did not create:

   ```
   hr_integration_connector id=1  "Zoho People"  type=zoho  auth=oauth2
   connection_status = error        api_endpoint = https://api.zohopeople.com/v2/hr
   create_uid = 2 (ash@biztinct.com)   create_date = 2026-08-19 01:18:57
   client_id     len=35   1000.A…Z2ML     md5 d607af88c1fcd832ce8a015166a8c55d
   client_secret len=42   fc10…2813       md5 487c9ac6b0be1a4b1c6d6bc1f92e04a1
   ```

   Those redacted fingerprints are the **legacy production pair** the owner
   showed (`1000.A5Q405LJ…` / `fc10d02bb…`) — same prefixes, and the owner is
   the record's author. The re-homing the handover describes as "in progress"
   is therefore already done on `abm`, by hand, the day before this cycle.

3. **Hardcoded ≠ re-homed, proven by hash.**
   `om_hr_payroll/models/hr_zoho_staging.py:208-210` holds

   ```
   client_id     = "1000.4ZLJ…V11L"   md5 02bc6830f57c3867a06f87cb5d74bf3c
   client_secret = "989fa207…1661"    md5 1eae67fb433db08f1cf5d72530f474f7
   ```

   Neither md5 matches the pair stored on `abm`. **The hardcoded block is an
   old, separate OAuth client**, exactly as the owner said.

**Action taken: none, deliberately.** Owner ruling 3 and the handover's
pre-verified-facts section both say the hardcoded block stays until the owner
has tested the new credential screens. Nothing in this cycle touches
`om_hr_payroll`, and no credential value was written, read into a payload, or
copied anywhere. See the owner-decisions section for the backlog item this
raises.

---

## Commits

| # | hash | what |
|---|---|---|
| 1 | *(pending)* | docs(integrations): Cycle 4 report — WP-1, the secrets verdict |

Nothing pushed. `.claude/settings.json`, `thaco/` and `ABM/` never staged.

---

## Evidence 1 — WP-1 read-only inspection

All queries read-only, run as `sudo -u odoo psql` with the service **up**.

### 1a — The target config

```sql
SELECT id, name, state FROM hr_formula_config WHERE name ILIKE '%mauri%';
--  7 | AB Mauri Payroll Vietnam | draft
```

One config on the whole database (`hr_formula_config` has exactly one row,
id 7), `country_id = 241` (Vietnam), **40 input rules + 36 formula rules** —
the handover's pre-verified numbers reproduce exactly.

The 40 input columns of config 7 (`hr_formula_rule`, `column_type='input'`,
ordered by sequence — this is the table the mappings bind to):

| col | code | name |
|---|---|---|
| A | `EMPLOYEECODE` | Employee Code |
| B | `EMPLOYEENAME` | Employee Name |
| C | `DATEOFJOINING` | Date of Joining |
| D | `EMPLOYEESTATUS` | Employee Status |
| E | `LASTWORKINGDAY` | Last Working Day |
| F | `LOCATION` | Location |
| G | `BASESALARY` | Base Salary |
| H | `GASALLOWANCE` | Gas Allowance |
| I | `PHONEALLOWANCE` | Phone Allowance |
| J | `MEALALLOWANCE` | Meal Allowance |
| K | `RESPONSIBILITYALOWANCE` | Responsibility Alowance *(typo is in the config)* |
| L | `PARKINGALLOWANCE` | Parking Allowance |
| M | `TAXIALLOWANCE` | Taxi allowance |
| N | `STANDARDWORKINGHOUR` | Standard Working Hour |
| O | `ACTUALWORKINGHOURSINCLUDINGPAIDLEAVE` | Actual Working Hours including Paid leave |
| P | `ACTUALWORKINGHOURSEXCLUDINGPAIDLEAVE` | Actual Working Hours excluding paid leave |
| X | `RECOGNITIONBONUS` | Recognition Bonus |
| Y | `OTHERINCOME` | Other Income |
| Z | `PAIDLEAVEUNUSED` | Paid Leave Unused |
| AA | `OTHERBONUS` | Other Bonus |
| AB | `BONUSSTIP` | Bonus - STIP |
| AC | `MARSHINSURANCEREFUNDNONTAX` | Marsh Insurance refund (Non-tax) |
| AD | `ADJUSTMENT` | Adjustment |
| AE | `SHUIPARTICIPATION` | SHUI Participation |
| AF | `TUPARTICIPATION` | TU Participation |
| AG | `SALESINCENTIVE` | Sales Incentive |
| AH | `THIRTEENTHMONTHSALARY` | Thirteenth Month Salary |
| AI | `SEVERANCEALLOWANCE` | Severance Allowance |
| AJ | `REIMBURSEMENTPAYMENT` | Reimbursement Payment |
| AK | `OT15HOURS` | OT 1.5 Hours |
| AL | `OT2HOURS` | OT 2 Hours |
| AM | `OT3HOURS` | OT 3 Hours |
| AN | `NIGHTSHIFTHOUR` | Night shift hour |
| AO | `OTNIGHTSHIFTWEEKDAY` | OT Night shift week day |
| AP | `OTNIGHTSHIFTWEEKENDDAY` | OT Night shift weekend day |
| AQ | `OTNGIHTSHIFTHOLIDAY` | OT Ngiht shift Holiday *(typo is in the config)* |
| BJ | `NUMBEROFDEPENDENTS` | Number of Dependents |
| BN | `MONTHLYPIT` | Monthly PIT |
| BO | `OTHERDEDUCTION` | Other Deduction |
| BX | `COSTCENTERFORPAYROLL` | Cost center for Payroll |

The handover's "PAIDUNUSED-family" resolves to the single code
**`PAIDLEAVEUNUSED`** (column Z).

### 1b — The `zoho.%` parameter comparison

See the secrets verdict above. Zero rows on all four databases.

### 1c — Module states on abm (pre-upgrade)

| module | abm state | abm version | payobook version | disk version |
|---|---|---|---|---|
| `pb_hr_payroll_formula` | installed | 19.0.1.48.4 | 19.0.1.51.0 | 19.0.1.51.0 |
| `pb_formula_studio` | installed | 19.0.1.69.0 | 19.0.1.70.4 | 19.0.1.70.4 |
| `pb_integrations` | installed | 19.0.1.2.0 | 19.0.1.5.0 | 19.0.1.5.0 |
| `pb_import_advanced` | installed | 19.0.1.1.0 | 19.0.1.3.0 | 19.0.1.3.0 |
| `pb_import_kit` | installed | 19.0.1.3.0 | 19.0.1.5.0 | 19.0.1.5.0 |
| `pb_settings` | installed | 19.0.1.0.0 | 19.0.1.2.0 | 19.0.1.2.0 |
| `pb_hub` | installed | 19.0.1.2.0 | 19.0.1.3.0 | 19.0.1.3.0 |
| `pb_sidebar` | installed | 19.0.3.0.0 | 19.0.3.0.0 | 19.0.3.0.0 |
| `pb_hr_payroll_base` | installed | 19.0.1.2.0 | 19.0.1.2.0 | 19.0.1.2.0 |
| `om_hr_payroll` | installed | 19.0.1.0.2 | 19.0.1.0.2 | 19.0.1.0.2 |
| `pb_demo` | **uninstalled** | — | installed 19.0.1.9.0 | — |

Every module the cycle needs is installed — **no `-i` was required**, so C7's
`update_list()` + targeted-install ritual was not exercised. `pb_demo` is
uninstalled on abm and **stays that way** (non-goal: no demo data on abm); the
seeding below is consequently not `is_demo`-flagged, and could not be: the
`is_demo` fields are `pb_demo`'s own `_inherit` additions and do not exist as
columns on this database.

Installed-module counts: abm **205**, payobook **209** (the four are
`pb_demo`, `pb_demo_portal`, `pb_coach`, `pb_website` — all deliberately
tenant-excluded by IA Cycle 7).

The schema evidence that abm is pre-program, independent of version numbers:

```sql
SELECT table_name FROM information_schema.tables
WHERE table_name LIKE 'hr_integration%';
--  hr_integration_connector, hr_integration_field_mapping,
--  hr_integration_mapping_template, hr_integration_mapping_test_line,
--  hr_integration_mapping_test_wizard, hr_integration_onboarding_wizard,
--  hr_integration_sync_wizard
```

`hr_integration_endpoint`, `hr_integration_endpoint_template` and
`hr_api_transformation_rule_template` are **absent**, and
`hr_integration_mapping_template.endpoint_code` is **absent** — Cycle 1's and
Cycle 3's schema has never reached this database. That is what WP-2 fixes, and
it is why the board on abm has been running on the degrade rail (cf2d197a).

### 1d — Legacy table presence on abm

| table | exists | rows |
|---|---|---|
| `zoho_staging_data` | **no** | — |
| `zoho_employee_data` | **no** | — |
| `zoho_staging_field_mapping` | yes | **0** |
| `zoho_staging_import_wizard` | yes | 0 |

So the two *data* models of the legacy Zoho pipeline have never been loaded on
abm, while the two *wizard* models have — and the wizard's field-mapping table
is empty, so there is no legacy per-tenant mapping configuration to inherit.
Every mapping decision in WP-3 therefore has to be read out of the legacy
**code**, which is what the mapping table below does, line by line.

### 1e — Existing integration data on abm (pre-seed)

```
connectors 1 | field_mappings 0 | mapping_templates 65 | transformation_rules 0 | data_stores 0
```

The single connector is the owner's own — see the secrets verdict, item 2. It
has **no mappings, no feeds and no stored payloads**; it has credentials and a
`connection_status='error'`, i.e. somebody pressed Test Connection and it did
not connect. **This cycle does not touch it** (see the deviation note).

The 65 vendor mapping-template rows are the pre-Cycle-3 set:

| connector_type | abm | payobook (post-C3) |
|---|---|---|
| zoho | **14** | **31** |
| darwin | 13 | 13 |
| sap | 13 | 13 |
| workday | 13 | 13 |
| oracle | 12 | 12 |

The 17 Zoho rows Cycle 3 shipped are the delta WP-2's upgrade must land.

### 1f — pb_demo / demo flags

`pb_demo` is `uninstalled` on abm and was not installed by this cycle. No
demo connectors exist on abm; nothing seeded here carries a demo flag.

---

## Pre-flight for WP-2 (W118 + W120), run before any window

**W118 — repo ↔ disk parity.** Every `__manifest__.py` under the repo root was
compared against `/odoo/odoo-server/addons`. Custom-module drift: **0**. (The
only line the diff printed is the repo's own vendored `addons/` copy of the
Odoo core manifest, which is not an addon on the server path.) So the shared
addons tree already carries C1–C3 — **no rsync, no staging directory, nothing
to deploy**. This cycle's only server-side code action is the `-u`.

**W120 — the reverse-dependency closure, computed before running.** Closure of
`pb_hr_payroll_formula, pb_formula_studio, pb_settings, pb_import_advanced,
pb_hub, pb_integrations, pb_import_kit` over abm's installed set = **66
modules**. Of those, the ones whose version differs between abm's database and
the disk — i.e. the ones an upgrade will actually move — are exactly **7**:

| module | abm now | disk (target) | in my `-u` list? |
|---|---|---|---|
| `pb_hr_payroll_formula` | 19.0.1.48.4 | 19.0.1.51.0 | yes |
| `pb_formula_studio` | 19.0.1.69.0 | 19.0.1.70.4 | yes |
| `pb_integrations` | 19.0.1.2.0 | 19.0.1.5.0 | yes |
| `pb_import_advanced` | 19.0.1.1.0 | 19.0.1.3.0 | yes |
| `pb_import_kit` | 19.0.1.3.0 | 19.0.1.5.0 | yes |
| `pb_settings` | 19.0.1.0.0 | 19.0.1.2.0 | yes |
| `pb_hub` | 19.0.1.2.0 | 19.0.1.3.0 | yes |

**Dragged modules not in the list: none.** The other 59 closure members are
already at their disk version, so the cascade re-runs them at the same version
— which is why the evidence for this window is the per-module version diff
below and not a count (W120.3). `pb_import_kit` is in the list precisely
because of W136's corollary: it is the asset-only module everybody leaves out.

**W124 — restart exposure.** The running `odoo-bin` (pid 3678414) started
**2026-08-20 06:09:47**, which is after every C1–C3 file landed on disk, so the
live process already imports the current code; no import-time patch is waiting.
The W136 unit restarts the service at the end regardless.

**W128 — pre-stop foreign-file check.** Run immediately before the window; see
Evidence 2.

---

*(sections below appended as each work package lands)*
