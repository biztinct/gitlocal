# Approval Matrix · Phase 3 — deploy checklist

The live box `Payobook19v2` has been unreachable since Phase 1 (ledger AM13,
AM14), so P1–P3 are one deferred deploy wave. This file is P3's half of it,
written so the wave can be run without re-reading any code.

Read `APPROVAL_MATRIX_LEDGER.md` first — §"Deploy contract" is the procedure;
this is only the payload.

## 1. Modules, in this order

`-i` for the three that are new (P1/P2 never installed on the live boxes), `-u`
for the rest. One `odoo-bin` invocation per database with the whole list is
fine; the order below is only for reading.

| Module | Version | Action | Why it is in the wave |
|---|---|---|---|
| `biz_approval_chain` | (P1) | `-i` | the engine's own dependency |
| `biz_approval_workflow` | 19.0.1.1.0 | `-i` | the approval engine (P1) |
| `pb_approval_config` | 19.0.1.1.0 | `-i` | Matrix, People, inbox, the catalogue (P2); P3 adds the pay-run count/kind on a card and the cross-module seed |
| `pb_payruns` | 19.0.2.0.0 | `-u` | **the phase.** Adapter, four states, split, seeds, two migrations |
| `pb_payrun_wizard` | 19.0.1.22.0 | `-u` | submits through the engine |
| `pb_payslip_review` | 19.0.1.2.0 | `-u` | the single-payslip ladder is retired |
| `pb_payhub` | 19.0.1.4.0 | `-u` | period tracker reads the new states |
| `pb_payrun_results` | 19.0.1.3.0 | `-u` | status facets |
| `pb_insights` | 19.0.5.2.0 | `-u` | run-state chips |
| `pb_dashboard` | 19.0.1.3.0 | `-u` | "pending payslips" count |
| `pb_comp_ben` | 19.0.1.1.0 | `-u` | the finance pack hooks `_approval_apply` |
| `pb_learn` | 19.0.13.2.0 | `-u` | live-mission predicates |
| `pb_hr_payroll_analytics` | 19.0.1.3.0 | `-u` | payslip-state domain |
| `payroll_analytics_approval` | 19.0.1.4.0 | `-u` | **the sudo hole is closed here** |
| `pb_home_hub` | 19.0.1.2.0 | `-u` | Approvals lens (P2 debt AM23) |
| `pb_formula_studio` | 19.0.1.189.0 | `-u` | Approvals tab on a scheme's settings |
| `pb_blueprint` | 19.0.1.9.1 | `-u` | the Connect step's Approvals card |
| `pb_approval` | 19.0.2.0.0 | `-u` | **retired to a redirect** — do NOT uninstall |

`pb_scheme_map` and `pb_group` are new dependencies of `pb_payruns`. Both are
already installed on every live database; if a tenant somehow lacks one, the
`-u` will pull it in as an `-i` automatically.

## 2. Before you start: the one thing that will stop the upgrade

`pb_payruns/migrations/19.0.2.0.0/pre-retire_tier_chain.py` **aborts the whole
upgrade** if any pay run is still sitting in `level0`, `level1` or `level2`, and
names them. That is deliberate: those states cease to exist, and a run left in
one becomes a row nothing can read, approve or walk back.

Check it first, per database, and finish or reject anything it finds:

```sql
SELECT id, name, state FROM hr_payslip_run
WHERE state IN ('level0','level1','level2') ORDER BY id;
```

Expected on a clean box: 0 rows. If it returns rows, do NOT force past it —
approve or reject each run on the old ladder, then upgrade.

## 3. Migrations that run by themselves

| Script | What it does |
|---|---|
| `pb_payruns .../pre-retire_tier_chain.py` | the abort check above; then drops `pb_sendback_note/uid/date/from` and deletes the `pb_payruns.officer_review` parameter |
| `pb_payruns .../post-seed_payrun_route.py` | gives every company the route it already had — "Payroll check → HR lead review → Finance approval", published and bound company-wide, with today's holders of the old officer / HR-manager / final-approver groups named in its seats (first holder = person, second = backup) |
| `pb_approval .../post-retire.py` | removes the retired cockpit's `pb.approval` model row and its own view/ACL `ir_model_data`. Uninstalls nothing |

`post_init_hook` does not run on `-u`, which is why the seed is mirrored as a
migration (ledger).

## 4. After the upgrade, per database

1. **Assets ritual — YES.** Every module in the table but two ships assets.
   `DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%';` then bump the
   `web.assets.version` `ir.config_parameter`, then restart.
2. **Check the seed landed:**
   ```sql
   SELECT c.name, w.name, v.status
   FROM biz_approval_binding b
   JOIN res_company c ON c.id = b.company_id
   JOIN biz_approval_workflow w ON w.id = b.workflow_id
   LEFT JOIN biz_approval_workflow_version v ON v.id = w.published_version_id
   JOIN biz_approval_process p ON p.id = b.process_id
   WHERE p.key = 'payrun' AND b.active AND b.scope_key = '';
   ```
   One row per company, workflow "Pay run approval", status `published`.
3. **Check the seats are filled.** Open Approvals → People & backups. Any of
   Payroll manager / HR lead / Finance approver left empty means the old group
   had no holder in that company; name somebody before the first pay run, or
   the first submission is refused with that seat named. This is the designed
   fail-closed behaviour, not a fault — but it is better found here.
   **HR lead is per part of the business** (`fallback_to_company = False`), so
   a company-wide holder does NOT cover a scheme; each scheme in use needs its
   own, or the route sticks. Seen on the local walk.
4. **Every database**, not just one: `payobook`, `payobook_template`, and every
   tenant (`psql -l`; today at least `abm`, `acme`, `rize`). Tenants get
   everything the master gets except `pb_tenants`, `pb_demo`, `pb_demo_portal`,
   `pb_website`. `pg_dump -Fc` each tenant first.

## 5. First checks on the screen

1. **Home → Approvals** — the lens the P2 debt (AM23) could not be walked for.
2. **Pay Runs board** — three columns: Draft · Waiting for approval · Done. A
   draft card offers "Submit for approval" and "Reject", and nothing else.
3. **Submit a draft run** — the card moves to Waiting for approval and a card
   appears in Approvals showing the route, the amount, "N payslips" and the
   kind of run.
4. **Open the run's own form** — one sentence under the header naming the route
   and whose desk it is on.
5. **A scheme's settings → Approvals tab**, and **New configuration → Connect →
   Approvals** — the same panel in both, agreeing with the Matrix.

## 6. Rollback

The only destructive step is the `pre-` migration's column drops. Everything
else is additive. To roll back: restore the per-database `pg_dump` taken in §4.
Do not attempt to reinstate the tier chain by hand — the state values are gone
from the selection and the old ACL/gate code has been deleted.
