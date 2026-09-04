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
| 1 | `e64b314f` | docs(integrations): Cycle 4 report — WP-1 inspection and the secrets verdict |
| 2 | `8c8ba59c` | feat(tools): the abm tenant's Zoho integration, seeded from the legacy evidence |
| 3 | `cb46f1fe` | docs(integrations): Cycle 4 report — the abm upgrade and the seeding |
| 4 | `66747680` | docs: Cycle 4's ledger — W141-W145 — and the abm validation |

Nothing pushed (74 commits ahead of `origin/19.1`, four of them this cycle's).
`.claude/settings.json`, `thaco/`, `ABM/` and the screenshot directory were
never staged — verified by `git log --name-only` over the four commits.

**One repo file changed**: `tools/abm_seed_integrations.py` (+349). No module
code, no `om_hr_payroll`, no manifest, no version bump — everything else this
cycle did was operations, and it lives in this report.

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

## Evidence 2 — WP-2: the abm upgrade

### The window

One W136 stall-proof unit, `/tmp/i4up.sh`, launched with
`systemd-run --no-block --unit=i4up --collect` (W133). The unit owns the whole
window: it stops the service, polls for zero `odoo-bin`, upgrades **twice**
(W121), captures each exit code, and starts the service again — so a stall on
my side could not have left payobook.com down.

```
06:38:39 STOP service
06:38:40 poll 1: odoo-bin procs = 1
   …     (polls 2-5)
06:38:55 poll 6: odoo-bin procs = 0
06:38:55 PASS 1 -u pb_hr_payroll_formula,pb_formula_studio,pb_settings,
                   pb_import_advanced,pb_hub,pb_integrations,pb_import_kit -d abm
06:39:40 PASS 1 EXIT=0
06:39:40 PASS 2 (W121 second pass) — same list
06:40:19 PASS 2 EXIT=0
06:40:19 START service
06:40:28 is-active: active
```

**`EXIT1=0 EXIT2=0`.** Total service interruption **1 min 49 s**. Registry load
for abm 41.8 s per pass. `--http-port=8274` and a private `--logfile` per pass
(W131 rule 1, W132 rule 1) — 8069 was never bound by anything but the service,
before or after.

Both passes were put in the SAME unit deliberately: W121 needs two passes, and
two windows would have meant two outages for the live neighbours.

Pre-stop checks (W68 / W128), run at 06:38 immediately before launching:

* `ps -eo pid,lstart,cmd | grep "[o]doo-bin"` — one process, the service's own
  (pid 3678414, started 06:09:47). No foreign run.
* `find /odoo/odoo-server/addons -name '*.py' -newermt "2026-08-20 06:09:47"
  -not -path '*__pycache__*'` — **two hits**, and W128 says anything it lists
  is code my restart will publish. They were
  `pb_hr_payroll_formula/models/api_transformation_rule.py` and
  `pb_hr_payroll_formula/tests/test_integration_endpoints.py`, both **md5-identical
  to the repo** (`536bc2872a62…`, `3704cfd34fae…`) at commit `efbb64b5` — Cycle
  3's own W137 fix, rsynced at 06:14 *after* the 06:09:47 restart and therefore
  not yet live in the serving process. So the restart published this program's
  previous cycle's already-tested fix, not a foreign session's work. Checked,
  identified and recorded rather than assumed — which is the whole point of the
  check.

### EXIT=0 and a clean log

`grep -c CRITICAL` = 0 in both pass logs; `grep " ERROR "` = nothing in either.

### The per-module version diff (W120.3 — a version table, not a count)

| module | abm before | abm after | disk | payobook |
|---|---|---|---|---|
| `pb_hr_payroll_formula` | 19.0.1.48.4 | **19.0.1.51.0** | 19.0.1.51.0 | 19.0.1.51.0 |
| `pb_formula_studio` | 19.0.1.69.0 | **19.0.1.70.4** | 19.0.1.70.4 | 19.0.1.70.4 |
| `pb_integrations` | 19.0.1.2.0 | **19.0.1.5.0** | 19.0.1.5.0 | 19.0.1.5.0 |
| `pb_import_advanced` | 19.0.1.1.0 | **19.0.1.3.0** | 19.0.1.3.0 | 19.0.1.3.0 |
| `pb_import_kit` | 19.0.1.3.0 | **19.0.1.5.0** | 19.0.1.5.0 | 19.0.1.5.0 |
| `pb_settings` | 19.0.1.0.0 | **19.0.1.2.0** | 19.0.1.2.0 | 19.0.1.2.0 |
| `pb_hub` | 19.0.1.2.0 | **19.0.1.3.0** | 19.0.1.3.0 | 19.0.1.3.0 |

Seven modules moved, exactly the seven the pre-flight predicted; the other 59
members of the closure re-ran at their existing version. **Nothing was dragged**
(the failure W120 records), and abm is now at parity with both the disk and
payobook for the whole closure.

### The schema arrived

```
hr_integration_endpoint
hr_integration_endpoint_template
hr_api_transformation_rule_template
```

All three tables now exist on abm, and `hr.integration.endpoint._schema_ready()`
answers **True** — so the degrade rail (cf2d197a) is no longer what is holding
abm's board up, and its feed counts are now real numbers rather than dropped
phrases (W139).

### The migration ran

```
2026-08-20 06:39:10 INFO abm
odoo.upgrade.pb_hr_payroll_formula.19.0.1.51.0.post-stamp_endpoint_codes:
IG-C3: stamped endpoint_code on 24 of 24 vendor mapping template row(s);
the rest already named a feed.
```

Logged in **pass 1 only** — by pass 2 the module was already at 19.0.1.51.0, so
no migration was due. The second pass therefore changed nothing, and that is the
correct outcome to report rather than to hide: W121's two-pass rule exists
because the *ordering* (data load before post-migrate) can strand a row, and
this cycle's evidence is that no row was stranded, proven below by identity
rather than by the pass count.

### Cycle 3's rows on abm — count AND per-XMLID (W121.3)

Counts, which now match payobook's Cycle-3 table line for line:

```
 endpoint_tmpl    | zoho               |     7
 endpoint_tmpl    | darwin             |     2
 rule_tmpl        | zoho               |     8
 map_tmpl_stamped | zohoemployees      |    26
 map_tmpl_stamped | zohosalary         |     2
 map_tmpl_stamped | zohoattsummary     |     1
 map_tmpl_stamped | zohoovertime       |     1
 map_tmpl_stamped | zoholeave          |     1
 map_tmpl_stamped | darwinemployees    |     8
 map_tmpl_stamped | darwincompensation |     2
 map_tmpl_stamped | (blank)            |    41
```

abm's zoho mapping templates went **14 → 31** (the 17 Cycle 3 shipped), and the
total went 65 → 82.

Counts are the weaker half. The per-XMLID check joins `ir_model_data` to each
shipped table on both databases and compares the resulting rows **as text**,
including the fields a wrong load would corrupt:

| table | key + compared fields | abm rows | payobook rows | diff |
|---|---|---|---|---|
| `hr.integration.mapping.template` | xmlid, source_path, target_code, **endpoint_code**, transformation_type | 82 | 82 | **identical** |
| `hr.integration.endpoint.template` | xmlid, code, data_type, path, is_legacy_abm | 9 | 9 | **identical** |
| `hr.api.transformation.rule.template` | xmlid, output_key, rule_type, source_data_type, **filter_expression** | 8 | 8 | **identical** |

Zero disagreements out of 99 rows — including every `endpoint_code` the
migration wrote and every `filter_expression` (the `rec`-namespace strings whose
corruption would silently zero a feed, W-C3).

### W137's fix is live on abm

The running process (pid 3691893, started **06:40:20** by my unit) imports the
fixed `api_transformation_rule.py`. A tree-wide grep for the removed kwarg
(W137 rule 3) finds `nocopy` in exactly one file and **only inside the
explanatory comment Cycle 3 left at the site** (lines 428, 432) — no live
`nocopy=` argument anywhere in `/odoo/odoo-server/addons`. This is load-bearing
for WP-3: two of the eight rules seeded below (`DEPCOUNT`, `WORKEDHRS`) are
`rule_type='python'` and would silently return their default without it.

### payobook and acme unharmed

| check | before window | after window |
|---|---|---|
| `https://payobook.com/web/login` | **200** | **200** |
| `https://acme.payobook.com/web/login` | **200** | **200** |
| `https://abm.payobook.com/web/login` | **200** | **200** |

Log grep across 06:38–06:41 for `payobook` / `acme` lines at ERROR or CRITICAL:
**none**. The only WARNING lines in the window belong to `payobook_template`'s
routine post-restart registry chatter (`_sql_constraints is no longer
supported`, `model field.access has no _description`) — pre-existing, present
on every restart, and unrelated.

No rsync, no staging directory, no file was written into the addons tree by
this cycle at all (the W118 pre-flight proved the tree was already current), so
there was no opportunity to disturb a neighbour's code.

---

## Evidence 3 — WP-3: the seeding, and that it is idempotent

### Mechanism, and a deviation worth stating

The script is **`tools/abm_seed_integrations.py`** — versioned in the repo, as
the handover requires. It is a plain ORM script driven through
`odoo-bin shell -d abm --no-http`, **with the live service UP**.

The handover expected JSON-RPC because "shell needs the service stopped". On
this box that turned out not to hold, and it was tested rather than assumed: a
read-only probe (`hr.integration.connector.search([])` +
`_schema_ready()`) ran cleanly alongside the serving process. The reason is
narrow and worth recording — the shell-vs-server rule in the ledger is about
**schema** work and `ir_ui_view` lock contention; this script writes only
`hr_integration_*` / `hr_api_transformation_rule` rows, which nothing else on
the box touches, and cross-process cache invalidation is handled by Odoo's own
registry signalling. Choosing shell over JSON-RPC therefore **saved a second
service window** on a cluster hosting two live databases, which is the trade the
ledger's uptime rules exist to make. (New rule W141 below.)

### The temp user (W129) — and the ACL it proved

`ig-c4-validator@abm.local`, **uid 8**, created through the shell, single-company
(company 1 "AB Mauri" only, `company_ids` and `company_id` in the same `write`).
Every seeding write ran **as that user**, not as the superuser — so the seeding
is proof that a real integration administrator could have done this by hand,
rather than proof that `sudo` can.

That choice immediately earned its keep: the first attempt **failed with an
AccessError**, because the user held *Formula Manager* but not *Formula
Administrator*, and `ir.model.access.csv:11` puts connector `create` behind
`group_formula_admin`. Holding `base.group_system` did not help, because model
access is granted by ACL rows and not by being an administrator. The group was
added and the run repeated. A `sudo()`-ed script would have sailed past this and
told us nothing about who can actually use the feature.

Groups finally held: `base.group_user`, `base.group_system`,
`pb_hr_payroll_formula.group_formula_user` / `_manager` / `_admin`,
`pb_hr_payroll_base.group_payroll_base_manager`,
`pb_hr_payroll_base.group_payroll_integration_user`.

### Run 1 — what it created

```
CONFIG     id=7  'AB Mauri Payroll Vietnam'  state=draft  inputs=40
CONNECTOR  created id=3
           status=disconnected  auth=oauth2  credentials_set=False
CATALOG    {'created': 0, 'skipped': 7}   feeds now = 7
TEMPLATE   {'applied': 0, 'suggested': 31, 'total': 31,
            'rules_created': 8, 'rules_skipped': 0}
ABM PASS   created=10  bound=5  unchanged=0  conflicts=0
TOTALS     feeds=7  mappings=41  wired=15  rules=8  credentials_set=False
```

`CATALOG created:0 / skipped:7` is Cycle 1's create-hook working: the seven feeds
already existed because `create()` catalogued them the instant the connector was
created, so the explicit sync had nothing left to do. `applied: 0, suggested: 31`
is D114.2 working exactly as it did on payobook — none of Cycle 3's generic
vendor target codes (`EMPID`, `BASIC`, `NAMEVN`…) matches this tenant's input
codes (`EMPLOYEECODE`, `BASESALARY`…), so no template row became load-bearing on
its own guess. **The 15 wires below are the ABM pass**, and every one of them
carries a citation rather than a guess.

`bound=5` are template rows the ABM pass gave a target (`EmployeeID`,
`Employeestatus`, `Dateofjoining`, `LocationName`, `Full_Name_Vietnamese`);
`created=10` are source paths no vendor template names — the two raw attendance
keys and the eight rule outputs.

### Run 2 — idempotence, measured

Row counts taken from the database immediately before and after a second
identical run:

| | connectors | field mappings | feeds | transformation rules |
|---|---|---|---|---|
| before run 2 | 2 | 41 | 7 | 8 |
| **after run 2** | **2** | **41** | **7** | **8** |

```
CONNECTOR  reused id=3
CATALOG    {'created': 0, 'skipped': 7}
TEMPLATE   {'applied': 0, 'suggested': 0, 'total': 0,
            'rules_created': 0, 'rules_skipped': 8}
ABM PASS   created=0  bound=0  unchanged=15  conflicts=0
```

**Second run creates nothing and writes nothing.** `unchanged=15` is the
stronger statement: it is not that the script skipped the rows, it is that it
re-derived all fifteen bindings and found each already correct.

### No credentials, on any connector, anywhere

```sql
SELECT client_id, client_secret, api_key, access_token, refresh_token,
       username, password FROM hr_integration_connector WHERE id = 3;
-- all seven columns NULL
```

`connection_status = 'disconnected'`. No HTTP call to Zoho was made by anything
in this cycle; the connector has no stored payloads (`hr_api_data_store` is
still empty on abm).

### The owner's own connector was not touched

| id | name | status | mappings | feeds | rules | write_date |
|---|---|---|---|---|---|---|
| 1 | Zoho People *(the owner's)* | error | 0 | 0 | 0 | **2026-08-19 01:22:16** |
| 3 | Zoho People (ABM) *(seeded)* | disconnected | 41 | 7 | 8 | 2026-08-20 06:46:20 |

Connector 1's `write_date` is unchanged from the day before this cycle. See the
deviations section for why a second connector was created rather than seeding
onto the owner's, and the owner-decision item that follows from it.

### The seven feeds on the seeded connector

| code | name | data type | ABM | path |
|---|---|---|---|---|
| `zohoemployees` | Employees | employee | **yes** | `forms/P_Employee/records` |
| `zohoattsummary` | Attendance summary | attendance | **yes** | `attendance/getSummaryReport` |
| `zohoovertime` | Overtime requests | custom | **yes** | `forms/overtime_request/getRecords` |
| `zohosalary` | Salary form | salary | no | `forms/P_Salary/records` |
| `zoholeave` | Leave records | leave | no | `api/v2/leavetracker/leaves/records` |
| `zohoattdaily` | Attendance by date | attendance | no | `attendance/getAttendanceByDate` |
| `zohotimesheet` | Timesheets | custom | no | `timetracker/gettimesheet` |

Exactly three carry the legacy-ABM flag, which is what the badges in the cockpit
render.

### The eight transformation rules

| output key | type | source data type | name |
|---|---|---|---|
| `DEPCOUNT` | **python** | employee | Dependants with a PIT number |
| `WORKEDHRS` | **python** | attendance | Actual working hours incl. paid leave |
| `OTHRS150` | sum | custom | Overtime 150% — hours |
| `OTHRS200` | sum | custom | Overtime 200% — hours |
| `OTHRS210` | sum | custom | Overtime 210% — hours |
| `OTHRS270` | sum | custom | Overtime 270% — hours |
| `OTHRS300` | sum | custom | Overtime 300% — hours |
| `OTHRS390` | sum | custom | Overtime 390% — hours |

---

## Evidence 4 — the mapping table

### The 15 wires: config input ← Zoho source · transform · feed

Every row's evidence column is a line of the legacy ABM application, and every
one of them is stored on the mapping's own `notes` field, so the answer is
visible in the UI and not only in this document.

| # | config input (code) | source path | transform | feed | state | legacy evidence |
|---|---|---|---|---|---|---|
| 1 | `EMPLOYEECODE` | `EmployeeID` | direct | `zohoemployees` | active | staging :333 → `employee_id` |
| 2 | `EMPLOYEENAME` | `Full_Name_Vietnamese` | direct | `zohoemployees` | active | staging :345 → `full_name_vn`; `hr_zoho.py:348` names the employee `full_name_vn or first_name` |
| 3 | `EMPLOYEESTATUS` | `Employeestatus` | direct | `zohoemployees` | active | staging :335 |
| 4 | `DATEOFJOINING` | `Dateofjoining` | direct | `zohoemployees` | active | staging :352 (+ :354-363 `yyyy-MM-dd`, silent-False on a bad value) |
| 5 | `LOCATION` | `LocationName` | direct | `zohoemployees` | active | staging :336 |
| 6 | `NUMBEROFDEPENDENTS` | `DEPCOUNT` *(rule)* | direct | `zohoemployees` | active | staging :367-373 — counts `tabularSections['Dependent and Dependent Health Insurance']` rows having a `Dependent_PIT_Number` |
| 7 | `STANDARDWORKINGHOUR` | `expectedWorkingHours` | **÷ 3600** | `zohoattsummary` | active | staging :562-563 → `standard_whr` |
| 8 | `ACTUALWORKINGHOURSEXCLUDINGPAIDLEAVE` | `totalWorkedHours` | **÷ 3600** | `zohoattsummary` | active | staging :564-565 — the key says "hours" and carries **seconds** |
| 9 | `ACTUALWORKINGHOURSINCLUDINGPAIDLEAVE` | `WORKEDHRS` *(rule)* | direct | `zohoattsummary` | active | staging :566-577 — `(paidLeaveSeconds + totalWorkedHours)/3600`, two different units in one payload |
| 10 | `OT15HOURS` | `OTHRS150` *(rule)* | direct | `zohoovertime` | active | staging :503-511 — Σ`Actual_Pay_Hour` where `OT_Type=='150%'` and approved |
| 11 | `OT2HOURS` | `OTHRS200` *(rule)* | direct | `zohoovertime` | active | staging :513-521 |
| 12 | `OT3HOURS` | `OTHRS300` *(rule)* | direct | `zohoovertime` | active | staging :522-530 |
| 13 | `OTNIGHTSHIFTWEEKDAY` | `OTHRS210` *(rule)* | direct | `zohoovertime` | active | staging :531-539, `overtime_nightshift_210_hour` "Nightshift **Normal**" = the weekday bucket (legacy payslip code `OTNW`/`otns_weekamount`) |
| 14 | `OTNIGHTSHIFTWEEKENDDAY` | `OTHRS270` *(rule)* | direct | `zohoovertime` | active | staging :540-548, "Nightshift **Weeekend**" (`OTNO`/`otns_offamount`) |
| 15 | `OTNGIHTSHIFTHOLIDAY` | `OTHRS390` *(rule)* | direct | `zohoovertime` | active | staging :550-557, "Nightshift **Holiday**" (`OTNH`/`otns_holamount`) |

The three night-shift rows are the ones that could plausibly have been wired
wrong. The mapping is not read off the percentages but off the legacy field
LABELS (`Normal` / `Weeekend` / `Holiday`, typo and all) cross-checked against
the legacy payslip code map's own weekday/offday/holiday triple
(`hr_payslip.py:346-348`). Two independent statements of the same ordering.

`feed` is the endpoint the value is **derived from**, not the store row the
engine writes `computed_data` onto (which, per
`api_transformation_rule.py:247-255`, is the salary row if one exists and the
employee row otherwise). A user reading `OTHRS150` wants to be told it comes
from the overtime request form.

### UNMATCHED A — the 25 config inputs with no Zoho source

The legacy Zoho import writes exactly **24 of `zoho.staging.data`'s fields**
from the employee form and **11 more** from the attendance/overtime pass.
Everything else on that model — every allowance, every bonus, the base salary,
the cost centre, the PIT — is declared, read by the payslip builder, shown in
the legacy views, and **never written from a Zoho payload**. Those columns came
from the ABM spreadsheet. That is why 25 of the 40 inputs are unmapped, and it
is a finding rather than a shortfall.

| config input | why there is no source |
|---|---|
| `BASESALARY` | `staging.base_salary` (:64) is never written by the import. Zoho's `P_Salary` form does expose a `Salary` field — the legacy ABM app never called it. **Owner question.** |
| `GASALLOWANCE` `PHONEALLOWANCE` `MEALALLOWANCE` `RESPONSIBILITYALOWANCE` `PARKINGALLOWANCE` `TAXIALLOWANCE` | `staging.*_allowance` (:65-70) — spreadsheet-sourced |
| `RECOGNITIONBONUS` `OTHERINCOME` `PAIDLEAVEUNUSED` `OTHERBONUS` `BONUSSTIP` `SALESINCENTIVE` `THIRTEENTHMONTHSALARY` `SEVERANCEALLOWANCE` `REIMBURSEMENTPAYMENT` | :71-83 — spreadsheet-sourced |
| `MARSHINSURANCEREFUNDNONTAX` `ADJUSTMENT` `OTHERDEDUCTION` | :76, :77, :94 — spreadsheet-sourced |
| `SHUIPARTICIPATION` `TUPARTICIPATION` | :78-79 — spreadsheet-sourced |
| `LASTWORKINGDAY` | `staging.last_workday` (:62) declared, never written |
| `COSTCENTERFORPAYROLL` | `staging.costcenter` (:63) declared, never written |
| `NIGHTSHIFTHOUR` | `staging.nightshift_hour` (:87) is never written. The legacy's only night-shift numbers are the 210/270/390 OT buckets, which are already wired (rows 13-15). `overtime_nightshift_200_hour` is declared at :56 and never written either. |
| `MONTHLYPIT` | a computed payroll **output** in the legacy (payslip code `MONPIT` → `zoho.employee.data.monthly_pit`, `hr_payslip.py:362`), not something Zoho delivers |

### UNMATCHED B — the 26 Zoho fields with no config input

These are Cycle 3's vendor template rows that landed on the connector and found
nothing in this config to feed. They stay `suggested` with no target, render
under "Unassigned" in the studio, and are exactly the material the owner needs
if the config ever grows a column for them.

| source path | feed | what it is |
|---|---|---|
| `FirstName` `LastName` `Nick_Name` | `zohoemployees` | name parts; the config has one name column, wired to `Full_Name_Vietnamese` |
| `EmailID` `Mobile` `Date_of_birth` `Gender` `Employee_type` | `zohoemployees` | employee master data the config does not take |
| `Department` `Designation` | `zohoemployees` | org data; the config's `LOCATION` is a site, not a department |
| `Pan_Number` `PIT_Number` `UAN_Number` `Aadhaar_Number` `PAN_or_TaxID` | `zohoemployees` | tax identifiers |
| `Bank_Name` `Bank_Account_No` `Bank_Account_Number_VND` `Insurance_Book_Number` | `zohoemployees` | payment + insurance identifiers |
| `Zoho_ID` | `zohoemployees` | the vendor's own row id |
| `No_of_Dependents` | `zohoemployees` | **deliberately not used** — the legacy counts dependants from the tabular section, so `DEPCOUNT` is the faithful source and this flat key is not |
| `Salary` `Other_Allowance` | `zohosalary` | the P_Salary form the legacy ABM app never called — see `BASESALARY` above |
| `Total_working_days` | `zohoattsummary` | days, where the config wants hours; the legacy reads `expectedWorkingHours` |
| `Overtime_hours` | `zohoovertime` | a flat total, where the legacy sums `Actual_Pay_Hour` per `OT_Type` |
| `LeaveTaken` | `zoholeave` | the config has no leave-days input |

The last four rows are the interesting ones: in each case a plausible-looking
Zoho field exists and was **not** used, because the legacy application computed
the number a different way. Wiring them would have been the "invent a mapping"
failure the handover forbids, and each would have been wrong in a way that
produces a number rather than an error.

---

## Evidence 5 — WP-4: the Chrome walkthrough on abm

Environment: the shared `chrome-devtools-mcp` profile was **free**, so W130's
own-Chrome-over-CDP fallback was not needed. Host: **`abm.payobook.com`** over
the wildcard DNS (verified 200 before the pass), backend prefix `/bizapp`.
Persona: the temp validator **uid 8**, authenticated over
`/web/session/authenticate` (W130's corollary), removed at the end (Evidence 6).
Viewport 1600×1000.

Screenshots are in **`.ig-c4-shots/`** in the repo working directory,
deliberately **untracked** — evidence, not a deliverable; delete after review.

### 5a — Settings → Integrations ✅ `01`, `02`

The Settings hub renders on abm with the eight-item rail. The **Integrations
category shows a TWO-card section page** — "Integrations" and "Mapping Studio" —
identical to payobook. Cycle 1's single-card auto-open self-retired here exactly
as designed the moment Cycle 2's second card arrived; nothing tenant-specific was
needed.

### 5b — the board: two connectors, and the contrast is the point ✅ `03`

Back chip "Settings" present. KPI row:

```
2 Connectors · 0 Connected · 1 Errors · 0 Synced records ·
41 Field mappings · 0 Staged records · 7 Feeds · 7 stale
```

**The Feeds tile is present**, which is W139's positive case (`feeds_known:
true`) — proof from the client side that the schema arrived and abm is no longer
riding the degrade rail. Both connector cards render:

```
Zoho People         · Zoho People · Never synced ·  0 mappings · 0 feeds · 0 staged · 0 synced · [Error]
Zoho People (ABM)   · Zoho People · Never synced · 41 mappings · 7 feeds · 0 staged · 0 synced · [Disconnected]
```

The owner's own connector sits beside the seeded one, unchanged and honestly
described. Same vendor, same screen, two different states — which is what makes
the seeded one legible.

### 5c — the connector cockpit: 7 feeds, 3 ABM badges ✅ `04`

Header `Zoho People (ABM)` · type chip `Zoho People` · endpoint chip
`https://people.zoho.com/people/api` · status **Disconnected**. Kebab (⋮) present
top-right, "Open record" absent from the toolbar (Cycle 1's demotion, intact on
abm).

`Feeds 7`, and **exactly three carry the ABM badge** — asserted in the DOM
(`abmBadgeCount: 3`), not by eye:

```
Employees            EMPLOYEE MASTER DATA   ABM   Never synced · 0 staged · 0 pulled · 27 mapped
Attendance summary   ATTENDANCE             ABM   Never synced · 0 staged · 0 pulled ·  4 mapped
Overtime requests    CUSTOM / OTHER         ABM   Never synced · 0 staged · 0 pulled ·  7 mapped
Salary form          SALARY / COMPENSATION        Never synced · 0 staged · 0 pulled ·  2 mapped
Leave records        LEAVE / TIME-OFF             Never synced · 0 staged · 0 pulled ·  1 mapped
Attendance by date   ATTENDANCE                   Never synced · 0 staged · 0 pulled ·  0 mapped
Timesheets           CUSTOM / OTHER               Never synced · 0 staged · 0 pulled ·  0 mapped
```

Every feed offers `Sync · View data · Map fields`. All read "Never synced",
which is the truth on a connector that has never had credentials.

### 5d — the credentials panel: everything "Not set" ✅ `05`

```
🔒 Credentials  OAuth 2.0                                        [Edit]
   ✕ Client ID   ✕ Client Secret   ✕ Refresh Token
   ✕ Authorization URL   ✕ Token URL   ✕ OAuth Scope
```

Six keys, six not-set markers, no value and no masked prefix anywhere in the
payload — which is Cycle 1's `is_set`-booleans-only contract holding on a real
tenant. Beside it: `Field mappings 41`, `Transformations 8`, `0 STAGED RECORDS`.

### 5e — the Mapping Studio: the wires are wires ✅ `06`, `07`, `12`

"Map fields" on **Employees** lands on

```
FROM · Zoho People (ABM) · 206 fields · never synced · [Employees] ══ 6 mapped / 3 suggested ══▶
TO · AB Mauri Payroll Vietnam · 40 input columns · VN · draft
```

back chip "Zoho People (ABM)". On **All feeds** the headline is the one that
matters: **`15 mapped`** — every seeded wire, on one board (`12`).

Two numbers need explaining, and both are honest:

* **the left column shows 206 `hr.employee` fields, not Zoho paths.** That is
  `get_available_source_fields`' documented fallback: *"Falls back to
  hr.employee's own fields (ir.model.fields) when nothing is stored yet."*
  This connector has no stored payload and never will until somebody enters
  credentials, so there is no vendor schema to show. The fallback is a
  deliberate design decision from Cycle 1, not a defect this cycle introduced.
* **the real Zoho sources appear anyway, under an "UNASSIGNED" group** — which
  is `api_mapping_data`'s W79 guard: a wire whose source path is not in the
  current field list is *kept and labelled*, never dropped. So the board shows
  `Dependants with a PIT number / DEPCOUNT`, `Join date / Dateofjoining`,
  `Employee ID / EmployeeID` … with solid wires drawn into `Employee Code`,
  `Employee Name`, `Date of Joining`, `Employee Status` (`07`). The orange
  dashed lines beside them are live 85 % name-match *suggestions* against the
  fallback fields — visibly different from the accepted wires, which is right.

`27 mapped` in the cockpit vs `6 mapped` in the studio for the same feed is the
same distinction Cycle 3 documented: the cockpit counts mapping ROWS on the
feed, the studio counts WIRES, and a wire needs a target.

### 5f — the ÷3600 transform popover, on a connector with no data ✅ `08`, `09`, `10`

Switching the feed to **Attendance summary** gives
`3 mapped / 5 suggested` and three source cards —
`Worked hours incl. paid leave / WORKEDHRS`,
`Expected working hours (seconds) / expectedWorkingHours`,
`Total worked hours (seconds) / totalWorkedHours` — carrying pills
`=`, `÷3600`, `÷3600`.

Opening a `÷3600` pill:

```
Transform on the wire
  Operation      [Divide by]
  Factor / value [3600]
  ÷3600  →  0
  [Cancel] [Save]
```

**The empty-sample path does not crash.** The preview strip renders
`÷3600 → 0` because `_sample_payload()` finds no stored row and no stub, so the
value is empty and the shared op ladder returns 0 — a number, not a traceback,
and not a spinner that never resolves. That is the case the handover singled
out, and it is also Cycle 3's `preview_transform` exception-hygiene fix
(`aa993d87`) doing its job on a database that has never pulled anything.

### 5g — everything is editable: a scratch wire drawn and deleted ✅ `11`

Armed `Badge ID / barcode` (an unmapped left card) — the board answered
*"Click a target component to connect"* — then clicked `Night shift hour /
NIGHTSHIFTHOUR` (an unmapped input).

| | story bar | transform pills | DB rows on connector 3 | wired |
|---|---|---|---|---|
| before | 3 mapped | 3 | 41 | 15 |
| after draw | **4 mapped** | **4** | **42** (`id 43 barcode → 197, active, create_uid 8`) | 16 |
| after delete | **3 mapped** | **3** | **41** | **15** |

The wire persisted server-side under the validator's own uid, and the ⋮-less
`Remove mapping` control took it away cleanly. The seeded state is **byte-for-byte
where it started**: 41 mappings, 15 wired.

### 5h — console and network hygiene ✅

Three surfaces, each freshly navigated:

| surface | XHR/fetch | ≥400 | console errors | console warnings |
|---|---|---|---|---|
| Integrations board | 13 | **0** | **0** | 1 |
| Connector cockpit | 14 | **0** | **0** | 0 |
| Mapping Studio | 15 | **0** | **0** | 0 |

Every request 200 (two 304s on a cached static JSON), including
`pb.integrations/get_board`,
`pb.import.connector.cockpit/get_connector_detail`,
`pb.formula.studio/mapping_pickers` and `api_mapping_data`.

The single warning is `biz_debrand`'s manifest icon size — pre-existing, outside
this cycle's modules, and the same one Cycle 3 recorded on payobook.

**One non-defect worth recording**: navigating to
`/bizapp/pb_integrations/pb_import_connector_cockpit` *directly* renders
"Could not load this connector." That is correct — the cockpit takes its
`connector_id` from the arrival params (`connector_cockpit.js:41-48`), and a bare
URL carries none. Reached through the board (the only door the UI offers) it
loads every time. Recorded so nobody reports it as an abm regression.

---

## Evidence 6 — the temp user, created and removed

```
mint    IGC4-UID=8 login=ig-c4-validator@abm.local companies=[1] is_system=True
teardown IGC4-TARGET=[8]
         IGC4-AI-CONVERSATIONS=1
         IGC4-UNLINKED=ok
         IGC4-PARTNER-UNLINKED=ok
         IGC4-REMAINING=0
```

Absence, read back from the database afterwards:

```sql
SELECT id, login, active FROM res_users WHERE login LIKE 'ig-c4%';   -- 0 rows
SELECT count(*) FROM res_partner WHERE name ILIKE '%IG-C4%';         -- 0
```

abm's user list is back to what it was: `__system__`, `ash@biztinct.com`,
`public`, `portaltemplate` and three archived probes from earlier cycles.

**The teardown did not work the first time, and the failure mode is a new rule
(W144).** `unlink()` raised a foreign-key violation from
`payroll_ai_conversation` — the "Stuck?" PayAI widget had opened a conversation
for the validator during the browser pass, so the validation created its own
blocker. Worse, the `except` branch's `write({'active': False})` ran on the
**same poisoned cursor** and silently committed nothing: the script printed a
tidy fallback message while the user stayed active, which a `SELECT` caught and
the log did not. The fix was to remove that one conversation row (scoped to this
uid — this cycle's own residue), then unlink, with a `rollback()` before any
fallback.

---

## Evidence 7 — tests

**No module code changed in this cycle.** The only repo addition is
`tools/abm_seed_integrations.py`, an ops script that is not part of any addon,
is not imported by any module, and ships in no manifest — so no test suite
covers it and none needed amending. `git diff --stat` over the cycle's code
commit is one file, +349 lines, under `tools/`.

The handover's condition ("full scoped test-suite run still green on the REPO
side **if any repo code changed**") therefore does not fire. Cycle 3's scoped run
— `0 failed, 0 error(s) of 109 tests` across `pb_formula_studio`,
`pb_hr_payroll_formula`, `pb_import_advanced`, `pb_integrations`, `pb_settings`
— remains the standing verdict for exactly the code abm now runs, and abm is at
those same versions (Evidence 2's version table).

Deliberately **not** run: a suite against `abm` itself. It would have needed
`--db-filter='^abm$'` (W122) and a baseline diff to mean anything, and W131's
rule 2 makes a test process on the production box a risk taken only for a
question that needs answering. The question here — "does this code work?" — was
already answered on payobook by the same commits, and the question that is
actually about abm — "did the data land?" — is answered by the per-XMLID
comparison in Evidence 2, which is stronger than a green suite.

The script was syntax-checked (`ast.parse`) and self-reviewed for the two things
that would matter: **no credential literal appears anywhere in it**, and its only
`sudo()` is a single READ of the config (configs are record-rule-gated; the
Mapping Studio reads them the same way). Every WRITE goes through the plain
`env` of the validating user.

---

## Evidence 8 — ledger

Five new rules, **W141–W145**, appended to
`docs/WORKFORCE_REDESIGN_CONVENTIONS.md` in the same commit as this report.
Summarised in the report-back below.

---

## Self-review against the handover

| the handover asked | done? |
|---|---|
| WP-1 read-only inspection FIRST, before any write | yes — the whole of Evidence 1 ran with the service up and nothing written |
| the secrets comparison as a REPORT ITEM, no action | yes — and closed with hash evidence rather than prefixes; `om_hr_payroll` untouched (`git diff` over the cycle shows one file, under `tools/`) |
| bind to the config's inputs; do not create/modify configs | yes — config 7 read only, passed to `action_apply_mapping_template` **by id**; the connector was never written onto the config |
| connector disconnected, NO credentials anywhere | yes — all seven credential columns NULL, verified by `SELECT` and by the UI's six "not set" markers |
| no Zoho HTTP traffic | yes — nothing in this cycle calls out; "Test connection" was never pressed |
| no demo data on abm | yes — `pb_demo` still uninstalled; the `is_demo` columns do not exist on this database, so the seeding could not have flagged anything even by accident |
| idempotent seeding | yes — second run `created=0 bound=0 unchanged=15`, counts identical |
| never invent a mapping | yes — 15 wires each citing a legacy line; 25 inputs left unmapped with a recorded reason; four plausible Zoho fields deliberately unwired |
| the script lives in the repo | yes — `tools/abm_seed_integrations.py` |
| W136 window shape, ending in `service start` inside the unit | yes — and it did start the service, at 06:40:19, from inside the unit |
| W120 closure computed BEFORE the run | yes — 66 modules, 7 predicted to move, 7 moved, 0 dragged |
| W121 second pass + per-XMLID verification | yes — both passes EXIT=0; 99 rows compared row-by-row against payobook, zero differences |
| W128 pre-stop foreign-FILE check | yes — it fired, and the two hits were identified by checksum rather than assumed |
| W129 temp user, removed after | yes — and the removal itself is a new rule |
| payobook + acme bracketed | yes — 200/200 before and after, zero ERROR lines from 06:38 onward |
| never stage `.claude/settings.json`, `thaco/`, `ABM/`; never push | yes — every commit staged by explicit path; `git log origin/19.1..HEAD` unpushed |

Two things I checked twice, because they are the ones that would be expensive to
get wrong:

1. **The night-shift triple.** 210/270/390 → weekday/weekend/holiday is asserted
   from two independent sources (the legacy staging field labels and the legacy
   payslip code map's `OTNW`/`OTNO`/`OTNH`), not from the percentages.
2. **`active` vs `suggested`.** Every wire I set to `active` has a source path
   that legacy production code reads by name from a live payload. Nothing was
   promoted on a name-similarity guess — the 31 template rows that arrived on
   similarity are all still `suggested` with no target, exactly as D114.2
   requires.

---

## Deviations from the handover

1. **A NEW connector was created rather than seeding onto the one already on
   abm.** WP-1 found `hr_integration_connector` id 1, "Zoho People", authored by
   the owner on 2026-08-19 with real credentials and
   `connection_status='error'`. The handover — written before that record was
   known — says to create "Zoho People (ABM)", disconnected, no credentials.
   I followed it literally and left connector 1 untouched (its `write_date` is
   still 2026-08-19 01:22:16). Reasoning: seeding onto a live record holding
   real secrets, on a production cluster, on the strength of my own inference
   about what the owner meant it for, is a decision with an owner — and the
   literal path is fully reversible, whereas the other is not. The consequence
   is two Zoho connectors on the board, which is legible rather than confusing
   (see 5b), and the merge is one decision away. **Owner-decision item below.**
2. **The seeding ran through `odoo-bin shell` with the service UP, not over
   JSON-RPC.** The handover preferred JSON-RPC on the belief that shell needs
   the service stopped. Probed rather than assumed: it does not, for a
   data-only script. Choosing it avoided a second production window. (W141.)
3. **`EMPLOYEENAME` is wired to `Full_Name_Vietnamese` with no fallback.** The
   legacy names an employee `full_name_vn or first_name` (`hr_zoho.py:348`).
   Reproducing the `or` faithfully needs a `python` transform, and the studio's
   transform popover deliberately offers eight ops with python absent — so I
   would have shipped, onto the flagship wire of the very screen this cycle
   validates, a transform the owner cannot edit there. The primary source is
   wired; the fallback is recorded in the mapping's `notes` and raised as an
   owner decision.
4. **No test-suite run.** No module code changed; reasoning in Evidence 7.
5. **The `zoho.%` comparison was extended beyond the two databases named.** The
   ruling says abm and payobook; I also checked `acme` and
   `payobook_template`, because "no rows on this cluster" is a much stronger
   statement than "no rows on these two" and costs one more query.

---

## Owner decisions

1. **The two Zoho connectors on abm — merge, or keep?** Connector 1 is yours
   (credentials, status *error*); connector 3 is the seeded catalogue (41
   mappings, 7 feeds, 8 rules, no credentials). Two ways to join them, both
   cheap: paste the credentials into "Zoho People (ABM)" through its
   Credentials panel and archive connector 1; or tell me to move the 41
   mappings + 7 feeds + 8 rules onto connector 1 (a single scripted `write`).
   I did not choose, because one of them archives a record you made.
2. **Backlog — scrub the hardcoded Zoho credentials.** Remove the hardcoded
   block and the `UserError` echo in `om_hr_payroll/models/hr_zoho_staging.py`
   (:208-210) **after** you have tested the new credential screens, and revoke
   the old client (`1000.4ZLJ…`) in the Zoho console. It is a different, older
   OAuth client from the one you are re-homing, so revoking it cannot break the
   new configuration. Recorded per the handover's instruction; nothing was done
   this cycle.
3. **`BASESALARY` — should it come from Zoho's `P_Salary` form?** The legacy ABM
   application never called that endpoint; base salary came from the
   spreadsheet. Zoho does expose `Salary` on `forms/P_Salary/records`, and the
   feed is catalogued and ready. Wiring it is a payroll decision, not a code
   one. The same question applies to `Other_Allowance`.
4. **`EMPLOYEENAME`'s fallback** — should an employee with an empty
   `Full_Name_Vietnamese` fall back to `FirstName`, as the legacy did? If yes it
   needs a python transform (not editable in the studio popover) and I should
   ship it deliberately.
5. **`No_of_Dependents` vs `DEPCOUNT`.** I wired the computed rule, because the
   legacy counts dependants having a PIT number out of the employee form's
   tabular section rather than trusting the flat field. If Zoho's flat
   `No_of_Dependents` is authoritative in your tenant, that is a one-line
   change and a better one.
6. **Housekeeping**: the four Integrations handover documents
   (`CYCLE1_ENDPOINTS_AND_NAV.md`, `CYCLE2_MAPPING_STUDIO.md`,
   `CYCLE3_ZOHO_CATALOG.md`, `CYCLE4_ABM_SEEDING.md`) and `PROGRAM_STATE.md` are
   **untracked** in git, while every cycle *report* is committed. The
   methodology wants the handovers versioned too. Not mine to commit
   unilaterally — flagging it.
7. **Nothing has been pushed**, this cycle or any of the three before it.

---

## New W-rules

| rule | one line |
|---|---|
| **W141** | The shell-vs-service rule is about SCHEMA, not about writes — a data-only ORM script runs fine through `odoo-bin shell` beside the live service, and choosing it over JSON-RPC saves a production window. Probe read-only first. |
| **W142** | A seeding script that `sudo()`s proves nothing about who can use the feature. Run it as the temp validation persona; the AccessError is the finding. `base.group_system` does not grant an `ir.model.access` row. |
| **W143** | W128's scan has a THIRD case: the file newer than the running process is often your own programme's, rsynced by the previous cycle after the last restart. Settle it with a checksum against the repo, not a guess in either direction. |
| **W144** | A temp validation user can be FK-blocked at teardown by rows the VALIDATION itself created — and a failed `unlink()` poisons the cursor, so the `except` branch's archive fallback commits nothing while printing success. |
| **W145** | Two namespaces, one feature apart: a transformation RULE's `filter_expression` evaluates with `rec`, a field MAPPING's python transform with `record`. Applying Cycle 3's lesson to the neighbour breaks it. |
