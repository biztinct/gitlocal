# Approval Matrix · Phase 7 — deploy checklist, and the whole P1–P7 wave

The live box `Payobook19v2` has been unreachable since Phase 1 (ledger AM13,
AM14), so P1–P7 are ONE deferred deploy wave. §1–§6 below are Phase 7's own
payload. **§7 is the whole wave, in order, and it is what Phase 8 executes** —
it replaces reading the five earlier deploy docs one at a time, though they
stay current and are worth having open for their "first checks on the screen"
sections.

Read `APPROVAL_MATRIX_LEDGER.md` first — §"Deploy contract" is the procedure;
this is only the payload.

## 1. Modules, in this order

| Module | Version | Action | Why it is in the wave |
|---|---|---|---|
| `biz_approval_workflow` | 19.0.1.5.0 | `-u` | **the proposal mixin.** A change written down before anybody may make it: snapshot re-check, the permission the original door required, the audit line, the fast lane. Plus the Vietnamese for every P1 refusal string |
| `pb_approval_config` | 19.0.1.5.0 | `-u` | the "Letters to people" catalogue row, two new responsibilities, **the spreadsheet importer** and its review screen; the `end-` relay |
| `pb_hr_payroll_formula` | 19.0.1.131.0 | `-u` | **four proposal records**: statutory, mappings, the scheme map, demo data. Plus `action_publish` on a legislation pack and the gate on its raw `state` write |
| `pb_statutory` | 19.0.1.3.0 | `-u` | the two config wizards gain the payroll-manager permission they never had, and propose |
| `pb_hr_payroll_vietnam` | 19.0.1.2.0 | `-u` | tax bands, insurance policy, insurance adjustment — all four doors propose |
| `pb_formula_studio` | 19.0.1.191.0 | `-u` | legislation packs, rate tables and the scheme mapping doors propose |
| `pb_scheme_map` | 19.0.2.1.0 | `-u` | attach / detach / accept the drafted map propose |
| `pb_pay` | 19.0.3.5.0 | `-u` | **pay bands.** Move an edge, save a band, link a job, accept the suggestions, import a sheet, the guidance grid, the company-wide review limits |
| `pb_group` | 19.0.2.1.0 | `-u` | **exchange rates and a group's money policy** |
| `pb_budget` | 19.0.2.3.0 | `-u` | a budget upload and an expense travel the same route |
| `pb_tenants` | 19.0.2.3.0 | `-u` | **the platform.** Nine doors, and the only route in the product that asks for two of the same responsibility |
| `pb_demo` | 19.0.1.11.0 | `-u` | the demo world is only built on a demo database, or with an approval |
| `pb_demo_seed` | 19.0.1.1.0 | `-u` | the same, for the small demo worlds |
| `pb_probation` | 19.0.1.2.0 | `-u` | **verdicts.** Pass is immediate; fail, extend and terminate travel a route |
| `pb_pip` | 19.0.1.2.0 | `-u` | the same verdict route, over a performance plan |
| `pb_lifecycle` | 19.0.1.4.0 | `-u` | **letters.** Generating stays free; sending is the act |
| `pb_people_advanced` | 19.0.1.1.0 | `-u` | the two guided wizards gain the HR permission they never had, and propose |
| `pb_close` | 19.0.1.3.0 | `-u` | **reopening a closed day**, and the bulk door's gate raised to the lock model's |
| `pb_comp_ben` | 19.0.1.4.0 | `-u` | **reopening a pay month**, with a reason |
| `pb_hr_fullandfinal` | 19.0.1.2.0 | `-u` | **final settlements** gain a status, and cannot be printed until approved |
| `pb_govt_reports` | 19.0.1.2.0 | `-u` | **statutory filings.** The module had no permission check at all; now it has one, and a route |

**One `-u` does most of it**, as in P5 and P6: every module above depends,
directly or through the chain, on `biz_approval_workflow`, so

```
-u biz_approval_workflow
```

cascades to the whole set. Three of them have gained a NEW dependency and are
worth naming so nothing is missed if the cascade is not used:

| Module | New dependency | Why |
|---|---|---|
| `pb_statutory` | `pb_hr_payroll_formula`, `biz_approval_workflow` | the statutory proposal record lives in the payroll engine, which is the only module the cockpit, the country tables and the studio all reach |
| `pb_govt_reports` | `pb_hr_payroll_base`, `biz_approval_workflow` | the payroll roles it had never checked |
| `pb_people_advanced`, `pb_close`, `pb_group`, `pb_lifecycle`, `pb_probation`, `pb_tenants`, `pb_hr_fullandfinal` | `biz_approval_workflow` | each now holds a proposal record of its own |

**Nothing is destructive.** Four new columns on `hr.full.final.settlement`
(`state`, `approved_at`, `approved_by`, `seat_user_ids`), one on `pb.hr.letter`
(`seat_user_ids`), and eleven new tables. No state machine is replaced, no
column is removed.

## 2. Before you start — fourteen more routes are published per company

From the moment they exist they are IN FORCE. Every one is the ladder that was
already in the code, or — for the five doors that had NO gate at all — the
ladder that always should have been.

| Process | The route that ships | What changes on day one |
|---|---|---|
| Statutory rates and tables | Payroll manager → Country director | **a real change**: these doors had no permission check, and now need one |
| Pay bands and guidance | Head of pay | dragging a band edge asks first |
| Rates, policy and budgets | Finance approver → Finance controller | an exchange rate is two signatures |
| Who is paid by what | Payroll manager | wiring a team to a scheme asks first |
| Mapping and feed changes | Payroll manager | the fetch schedule and mapping activation ask first |
| Customer accounts and rollouts | **Platform owner → Platform owner** | two owners, on a platform database only |
| Demo data | Country director | only where the database is NOT a demo or template one |
| Probation and plan verdicts | Their manager → HR lifecycle team *(only when the verdict is fail or terminate)* | pass is unchanged |
| Letters to people | HR lead | generating is unchanged; sending asks |
| New people and first contracts | HR lead | **a real change**: these wizards had no permission check |
| Reopening closed days | Payroll manager | closing is unchanged |
| Final settlements | HR lead → Finance approver | the settlement cannot be printed until approved |
| Reopening a pay month | Payroll manager | closing is unchanged; reopening needs a reason |
| Statutory filings | Payroll manager | **a real change**: this module had no permission check |

**Five gates are NEW, not re-routed.** Tell whoever runs these screens before
the wave, because somebody will meet a refusal they have never seen:

1. `pb.statutory.wizard.create_policy` / `create_tax_table` — now needs
   **Payroll manager** (`pb_hr_payroll_base.group_payroll_base_manager`).
2. `pb.filing.flow.generate` — now needs **Payroll officer or manager**.
3. `pb.people.onboard.wizard.create_employee` and
   `pb.people.contract.wizard.create_contract` — now need **HR**
   (`hr.group_hr_user`).
4. `vietnam.insurance.adjustment.action_apply` — was reachable by a payroll
   USER; now needs **Payroll manager**.
5. `pb.close.unlock_days` — asked for an officer while the lock model it calls
   asked for a manager. It now asks for the manager, which is what reopening a
   day has always required.

**Two responsibilities are new**: **Finance controller** and **Platform
owner**. Both are seeded from whoever holds the group the job was done by —
check them, because the person a group happens to list first is not
necessarily the person the business means.

**One catalogue row is new**: `letters` → `pb.hr.letter`.

## 3. Migrations and seeds that run by themselves

| Script | What it does |
|---|---|
| `pb_hr_payroll_formula .../19.0.1.131.0/post-p7_routes.py` | the statutory, mapping, scheme-map and demo routes, per company |
| `pb_pay .../19.0.3.5.0/post-bands_route.py` | the pay-band route |
| `pb_group .../19.0.2.1.0/post-fx_route.py` | the rates, policy and budget route |
| `pb_tenants .../19.0.2.3.0/post-platform_route.py` | the platform route (only where `pb.tenant` exists) |
| `pb_probation .../19.0.1.2.0/post-verdict_route.py` | the verdict route |
| `pb_lifecycle .../19.0.1.4.0/post-letter_route.py` | the letter route |
| `pb_people_advanced .../19.0.1.1.0/post-newhire_route.py` | the new-hire route |
| `pb_close .../19.0.1.3.0/post-unlock_route.py` | the reopen-a-day route |
| `pb_comp_ben .../19.0.1.4.0/post-month_route.py` | the reopen-a-month route |
| `pb_hr_fullandfinal .../19.0.1.2.0/post-fnf_route.py` | **marks every EXISTING settlement `approved`** (they were produced and mostly paid; the new column defaults to "being prepared", so without this a historical settlement would read as about to happen and could no longer be printed), then the settlement route |
| `pb_govt_reports .../19.0.1.2.0/post-filing_route.py` | the filing route |
| `pb_approval_config .../19.0.1.5.0/end-p7_adapters.py` | **an `end-` script, and that is the point** (ledger AM75): the duck-typed relay that asks every adapter in the registry for its default route, after the whole graph is loaded |
| each module's `post_init_hook` | the same seeds, on a FRESH install, where no migration runs at all |
| `res.company.create` | a company made later gets all fourteen |

Every one is idempotent; running all of them in a row creates exactly one of
everything.

## 4. After the upgrade, per database

1. **Assets ritual — YES.** `pb_approval_config` ships new JS, XML and SCSS
   (the spreadsheet door).
   `DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%';` then bump the
   `web.assets.version` `ir.config_parameter`, then restart.

2. **Check the eleven new tables exist.** A model whose module was not updated
   leaves its table missing and logs `Model … has no table` at registry load —
   the symptom, not the disease (ledger AM64):
   ```sql
   SELECT to_regclass('pb_statutory_proposal'),
          to_regclass('pb_mapping_proposal'),
          to_regclass('pb_schememap_proposal'),
          to_regclass('pb_demo_proposal'),
          to_regclass('pb_bands_proposal'),
          to_regclass('pb_fx_proposal'),
          to_regclass('pb_tenant_proposal'),
          to_regclass('pb_verdict_proposal'),
          to_regclass('pb_newhire_proposal'),
          to_regclass('pb_unlock_proposal'),
          to_regclass('pb_month_proposal'),
          to_regclass('pb_filing_proposal'),
          to_regclass('pb_approval_proposed_person');
   ```
   All thirteen must be non-null on the master. `pb_tenant_proposal` is
   platform-only and will be null on a tenant, which is correct.

3. **Check the new columns exist:**
   ```sql
   SELECT column_name FROM information_schema.columns
    WHERE table_name = 'hr_full_final_settlement'
      AND column_name IN ('state', 'approved_at', 'approved_by');
   SELECT to_regclass('hr_full_final_settlement_seat_rel'),
          to_regclass('pb_hr_letter_seat_rel');
   ```

4. **Check the fourteen routes landed, per company:**
   ```sql
   SELECT c.name, p.key, w.name, v.status
   FROM biz_approval_binding b
   JOIN res_company c ON c.id = b.company_id
   JOIN biz_approval_process p ON p.id = b.process_id
   JOIN biz_approval_workflow w ON w.id = b.workflow_id
   LEFT JOIN biz_approval_workflow_version v ON v.id = w.published_version_id
   WHERE p.key IN ('statutory','bands','fx','schememap','mappings',
                   'tenant','demo','verdict','letters','newhire',
                   'unlock','fnf','month','filing')
     AND b.active AND b.scope_key = ''
   ORDER BY c.name, p.key;
   ```
   Fourteen rows per company on the master (thirteen on a tenant — no
   `tenant` row), every one `published`.

5. **Check the catalogue tells the truth:**
   ```sql
   SELECT key, model_name FROM biz_approval_process
   WHERE key IN ('statutory','bands','fx','schememap','mappings',
                 'tenant','demo','verdict','letters','newhire',
                 'unlock','fnf','month','filing')
   ORDER BY key;
   ```
   No `model_name` may be null. Then open the Matrix: every one of the
   thirty-nine rows must read as protected rather than "Not connected yet".

6. **Fill the two new seats.** **Finance controller** signs the second half of
   every exchange-rate and budget change; **Platform owner** is the pair of
   people who may pause or close a customer. Both are seeded from
   `base.group_system` holders where nothing better was found, which is a
   starting point and not an answer.

7. **The people a route names must be able to do the thing.** The last
   approver carries it out AS THEMSELVES (safety rail 5, ledger AM54). Each
   proposal declares the permission its original door required and refuses by
   name if the approver does not hold it:
   * statutory — **Payroll manager**;
   * pay bands — **Pay manager** (`pb_pay.group_pay_manager`) or a group admin;
   * rates and budgets — **Group administrator**;
   * mappings and the scheme map — **Formula manager**;
   * platform and demo — **Settings / system administrator**;
   * new hires — **HR**;
   * reopening a day — **Attendance or payroll manager**;
   * reopening a month — **Payroll manager**;
   * filings — **Payroll officer or manager**.
   A country director who holds none of these will approve and then be
   refused when it applies, leaving the request `approved` with a block
   reason. Either give that person the permission or make the last step
   somebody who has it.

8. **Every database**, not just one: `payobook`, `payobook_template`, and
   every tenant (`psql -l`; today at least `abm`, `acme`, `rize`). Tenants get
   everything the master gets **except** `pb_tenants`, `pb_demo`,
   `pb_demo_portal`, `pb_website`. `pg_dump -Fc` each tenant first.

## 5. First checks on the screen

1. **Approvals → the Matrix.** Thirty-nine rows, seven areas, and nothing
   reading "Not connected yet".
2. **"Bring in from a spreadsheet".** The panel opens, takes an `.xlsx`, and
   answers "10 draft route(s) made from 10 row(s). Nothing is in force until
   somebody publishes it." Each row lists the route it read, the warnings it
   could not resolve, and the people it will not guess at.
3. **Settings → Statutory → new insurance policy.** As somebody who is not a
   payroll manager: refused by name. As the payroll manager: "Sent for
   approval", nothing created.
4. **Pay bands → drag an edge and let go.** The dry run still answers
   instantly while dragging; letting go says who it is with.
5. **Approvals → My turn**, as the country director, on the statutory change.
   The drawer lists what would change, before and after.
6. **Approve it.** The policy is created, once, and the trail carries a
   `biz.audit.entry` naming who proposed it and who approved it.
7. **Tenants (platform database only) → pause a customer.** The typed slug is
   still required. Type it and the answer is "Pausing Acme was sent for
   approval — it is with …". The customer is NOT paused.
8. **Final settlements.** Generate one for a leaver: it is created in "Being
   prepared" and sent in. Try to print it: refused with the name of whoever
   holds it. Approve it as both, and the print works.
9. **Filing flow.** Choose a filing, set its scope, press Generate: "Sent for
   approval". Approve it and the artifact is produced then.
10. **Switch Vietnamese on** and walk the Approvals screens: the refusals, the
    event lines and the proposal drawers are all in Vietnamese, including the
    engine's own ~60 refusal strings, which had none until this phase.

## 6. Rollback

Everything in P7 is additive — new tables, new columns, new rows — with one
data repair (§3, `hr.full.final.settlement.state`) that only writes what was
already true. To roll back a database, restore the per-database `pg_dump`
taken in §4.8.

To stop a route being in force WITHOUT rolling back, set that process to
**"No approval needed"** in the Matrix. Every door then behaves exactly as it
did before the phase — a press writes at once — and every use is still
recorded as a request. That is a published choice, not a bypass, and it is the
answer to "we are not ready for this yet" for all fourteen.

The five NEW GATES are the one thing a fast lane does not undo: they are
permissions, not routes. If one of them has to come off in a hurry, the answer
is to give the person the group, never to remove the check.

---

# 7. THE WHOLE WAVE — P1 to P7, in order

**This section is what Phase 8 executes.** It assumes nothing has been
deployed since Phase 1. The per-phase docs (`APPROVAL_MATRIX_P3_DEPLOY.md`
… `_P6_DEPLOY.md`) stay current and carry the screen walks; this is the
single ordered list.

## 7.1 Before the box is touched

1. **Reach the box.** `ssh Payobook19v2`. If it does not answer, stop: every
   step below assumes it does (ledger AM13/AM14).
2. **List the databases.** `psql -l`. Expect at least `payobook`,
   `payobook_template`, `abm`, `acme`, `rize`. Write the list down; every
   step is repeated for every one of them.
3. **Back up every tenant AND the master**:
   `pg_dump -Fc -f /odoo/backups/pre-approval-<db>-$(date +%F).dump <db>`
   for each. The wave publishes ~37 routes per company and adds five new
   permission gates; a restore is the rollback.
4. **Check the addons directory contract** (CLAUDE.md): `addons_path` is a
   single entry, `/odoo/odoo-server/addons`. `/odoo/custom/addons` is a guard
   FILE. Never recreate it.
5. **Split ours from the vendor's**:
   `git -C /odoo/odoo-server ls-files addons | cut -d/ -f2 | sort -u`.
   Everything in that list is the server's own and must NOT be deployed from
   this repo (`web`, `hr`, `hr_*`, `mail`, `website*`, `resource`,
   `spreadsheet`, …).

## 7.2 The files

The full module set, P1–P7. Rsync all of them in one pass; install/upgrade in
the order of §7.4.

```
biz_approval_workflow  pb_approval_config
pb_payruns  pb_hr_payroll_formula  pb_pay_delivery  pb_records  pb_zoho_bridge
pb_timesheet_approval  pb_import_batch  pb_import_wizard  pb_payrun_wizard
pb_comp_ben  pb_hr_fullandfinal  pb_audit  pb_compliance_hub  pb_blueprint
payroll_analytics_approval  pb_learn  pb_home_hub  pb_hub
pb_assets  pb_attendance_flow  pb_bank_ocr  pb_business_trip
pb_contract_lifecycle  pb_me_portal  pb_offboarding  pb_pay  pb_rnr
pb_timeoff  pb_hr_workforce  pb_mission  pb_team  biz_access  pb_tenancy
pb_statutory  pb_hr_payroll_vietnam  pb_formula_studio  pb_scheme_map
pb_group  pb_budget  pb_tenants  pb_demo  pb_demo_seed  pb_probation  pb_pip
pb_lifecycle  pb_people_advanced  pb_close  pb_govt_reports
```

```bash
sudo rm -rf /tmp/deployAM && mkdir -p /tmp/deployAM
rsync -az --exclude=__pycache__ --exclude='*.pyc' --exclude='.DS_Store' \
      <the list above> Payobook19v2:/tmp/deployAM/
# then, PER MODULE, on the box:
sudo rsync -a --delete /tmp/deployAM/<m>/ /odoo/odoo-server/addons/<m>/
```

**NEVER** `--delete` with `/odoo/odoo-server/addons/` itself as the
destination (ledger, and the 2026-08-26 incident).

## 7.3 The one new module

`biz_approval_workflow` and `pb_approval_config` are **installs**, not
upgrades: they have never been on the box. Everything else in §7.2 is an
upgrade. `biz_approval_chain` is already installed.

## 7.4 The command, per database

Stop the service, then run one detached unit per database with a sentinel
(ledger §"Deploy contract" 4):

```
-i biz_approval_workflow,pb_approval_config -u <every other module in §7.2>
```

In practice `-u biz_approval_workflow,pb_team` after the install cascades to
almost all of it; `pb_team` is named separately because it no longer depends
on the engine, and `pb_audit`/`pb_compliance_hub` because their only change is
a manifest description.

Order matters in exactly one place: `pb_approval_config`'s `end-` scripts run
after the whole graph is loaded, so they see every adapter. That is automatic —
nothing to sequence by hand.

Poll the sentinel; then `grep -E 'EXIT=|Traceback|CRITICAL|ERROR' /tmp/x.log`.
Two ERROR lines used to be normal and are now fixed (ledger AM82); anything
else is real.

## 7.5 What the wave publishes — the whole count

**About 37 default routes per company**, in seven areas:

| Phase | Processes it puts in force |
|---|---|
| P2 | `generic` ("Other request") |
| P3 | `payrun` |
| P4 | `timesheet`, `scheme` |
| P5 | `bankfile`, `release`, `journal`, `payslips`, `records`, `runonly`, `loads`, `arrivals` |
| P6 | `assets`, `correction`, `bankchange`, `trip`, `awards`, `extension`, `master`, `resign`, `paychange`, `payreview`, `recognition`, `leave`, `overtime`, `roles`, `support` |
| P7 | `statutory`, `bands`, `fx`, `schememap`, `mappings`, `tenant`, `demo`, `verdict`, `letters`, `newhire`, `unlock`, `fnf`, `month`, `filing` |

**Ten responsibilities have to be filled per company**: Approver, HR lead,
Finance approver, Payroll manager, Country director, Equipment team, Head of
pay, HR lifecycle team, Finance controller, Platform owner. Every one is
seeded from whoever holds the group the job used to be done by, and every one
should be checked by a human before anybody relies on it.

**One state machine IS replaced** (P3, the only destructive piece in the whole
programme): `hr.payslip.run.state` becomes `draft / approval_pending / done /
cancel`. The `pre-` migration **ABORTS the whole upgrade, by name, if any run
is sitting in `level1` or `level2`**. Check for those first:

```sql
SELECT id, name, state FROM hr_payslip_run WHERE state IN ('level1','level2');
```

Move each one to `done` or `draft` before the wave, or the upgrade stops.

## 7.6 Per database, after the upgrade

1. **Assets ritual — YES**, once per database, at the end:
   ```sql
   DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%';
   ```
   then bump `web.assets.version` in `ir_config_parameter`, then restart.
2. **Every table check** in §4.2 of this doc, plus P5 §4.2 and P6 §4.2.
3. **The route census**, which replaces all three per-phase queries:
   ```sql
   SELECT c.name, count(*) AS routes,
          count(*) FILTER (WHERE v.status <> 'published') AS not_published
   FROM biz_approval_binding b
   JOIN res_company c ON c.id = b.company_id
   JOIN biz_approval_workflow w ON w.id = b.workflow_id
   LEFT JOIN biz_approval_workflow_version v ON v.id = w.published_version_id
   WHERE b.active AND b.scope_key = ''
   GROUP BY c.name ORDER BY c.name;
   ```
   `not_published` must be 0 everywhere.
4. **The catalogue census**:
   ```sql
   SELECT count(*) FILTER (WHERE model_name IS NULL OR model_name = '')
     AS rows_with_no_model FROM biz_approval_process;
   ```
   Must be 0.
5. **The seats census**:
   ```sql
   SELECT r.key, count(*) FROM biz_approval_responsibility x
   JOIN biz_approval_role r ON r.id = x.role_id
   WHERE x.active GROUP BY r.key ORDER BY r.key;
   ```
   Ten keys, at least one holder each, per company.
6. **The one company switch** (P5 §4.7): *Post a payroll journal entry when a
   pay run is finished* — **OFF, and it stays off** unless the company's
   accountant asks for it.
7. **Version check**, per database (CLAUDE.md §Verifying): compare each
   manifest version to `ir_module_module.latest_version`, normalising the
   `19.0.` prefix.
8. **Content check**: hash each module tree on both sides, skipping
   `__pycache__`, `*.pyc` and `.DS_Store`.

## 7.7 Tenants

Tenants get everything the master gets **except** `pb_tenants`, `pb_demo`,
`pb_demo_portal`, `pb_website`. Consequences for this wave:

* the `tenant` catalogue row exists on a tenant but is never seeded with a
  route, because `pb.tenant` is not in the registry there. That is correct and
  the seed guards for it explicitly.
* the `demo` row is seeded only where `pb.demo.seed` or `pb.demo.generator`
  exists. On `rize` (which has `pb_demo_seed`) it is; on a tenant with
  neither, it is not.
* every other route is identical to the master's.

Back up, install, verify, one tenant at a time. Never all four at once.

## 7.8 The tests, on the box

Scratch database, service left running, on the spare ports:

```bash
createdb -T payobook_template am_verify
sudo -u odoo python3 /odoo/odoo-server/odoo-bin -c /etc/odoo-server.conf \
  -d am_verify -u biz_approval_workflow --test-enable --stop-after-init \
  --http-port=8199 --gevent-port=8198 --log-level=test
```

`--test-enable` only runs tests for modules it installs/updates, so the
cascade is what gives the coverage. Expect the suite counts recorded in each
phase report.

## 7.9 The order of the walk, once it is up

P3 §5, P4 §5, P5 §5, P6 §5 and §5 of this document, in that order. The first
five minutes that matter: Home → Approvals opens; a pay run can be sent in; a
bank file needs two people; a laptop request draws its real route; a statutory
rate asks before it is written.
