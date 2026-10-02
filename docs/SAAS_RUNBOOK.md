# Payobook SaaS Platform Runbook

Operational reference for the multi-tenant platform (Tenant Mission Control, `pb_tenants`).
Server: ssh alias `Payobook19v2`. Strategy: `docs/SAAS_STRATEGY.html`.

## Architecture (live since 2026-08-09)

- **Apex database renamed:** `Payobook19v2` → **`payobook`** (filestore moved too;
  pre-rename safety dump at `/odoo/backups/pre_saas_Payobook19v2.dump`).
  All deploy commands now use `-d payobook`.
- **Routing:** `/etc/odoo-server.conf` has `dbfilter = ^%d$` and `list_db = False`.
  Odoo maps the first hostname label to the database: `payobook.com` → `payobook`,
  `acme.payobook.com` → `acme`. Database names must equal subdomain labels.
- **nginx:** apex block unchanged (`sites-available/_`); new wildcard block
  `sites-available/pb-wildcard` (symlinked in sites-enabled) proxies `*.payobook.com`
  to 127.0.0.1:8069 with websocket headers. It currently uses the **apex certificate** —
  swap to the wildcard cert when issued (see below).
- **Golden template DB:** `payobook_template` — full Payobook module set minus
  `pb_demo, pb_demo_portal, pb_website, pb_coach, pb_tenants`. Unreachable via web
  (underscore is invalid in hostnames). All its crons are disabled; the active-cron set
  is recorded in `ir.config_parameter` key `pb_tenants.template_active_crons` and
  re-enabled per tenant by the provisioning "configure" step.
- **Tenant manager:** `pb_tenants` module installed on the apex DB only.
  Sidebar → Admin → Tenants (system administrators only).
- **Custom-domain automation:** `/usr/local/bin/pb-domain-attach|pb-domain-detach`
  (root-owned, arg-validated), sudoers drop-in `/etc/sudoers.d/pb-tenants` lets the
  `odoo` user run exactly these two.
- **Backups:** `/odoo/backups/tenants/<slug>/` — nightly cron on the apex DB keeps the
  last 14 nightly dumps per tenant; manual/final kept forever.

## Go-live: registrar DNS (one-time, manual)

1. Add at the registrar: **A record, host `*`, value = current server public IP**
   (the Tenants cockpit shows it live; it equals what `payobook.com` resolves to).
2. Wildcard TLS certificate (DNS-01; requires a one-time TXT record):
   ```bash
   sudo certbot certonly --manual --preferred-challenges dns \
        -d '*.payobook.com' --cert-name payobook-wildcard
   # add the shown _acme-challenge TXT at the registrar, wait, continue
   sudo sed -i 's#/etc/letsencrypt/live/payobook.com/#/etc/letsencrypt/live/payobook-wildcard/#' \
        /etc/nginx/sites-available/pb-wildcard
   sudo nginx -t && sudo systemctl reload nginx
   ```
   Manual DNS-01 certs do **not** auto-renew (repeat ~every 80 days) — moving DNS to
   Route 53 later enables full automation (`certbot-dns-route53`).
3. Re-check in the cockpit: Tenants → "Re-check platform". All checks green → tenants
   are reachable at `https://<slug>.payobook.com`.

## Golden template rebuild (when the product changes shape)

Normally NOT needed — code deploys upgrade the template like any DB (see below).
Full rebuild only for a from-scratch template:

```bash
sudo -u odoo psql -d postgres -c 'DROP DATABASE IF EXISTS payobook_template;'
# phase A: base + resource
sudo -u odoo python3 /odoo/odoo-server/odoo-bin -c /etc/odoo-server.conf \
     -d payobook_template -i base,resource --stop-after-init
# seed everything fresh installs are missing (all discovered 2026-08-09, scripts
# preserved in the session scratchpad; re-create via odoo shell on the template):
#  1. resource.resource_calendar_std_35h / _38h  (demo-only in stock Odoo 19,
#     but referenced by hr_contract's regular data) — copy resource_calendar_std
#     + ir.model.data rows in module 'resource'
#  2. pb_hr_flow.action_hr_flow_wizard placeholder act_window, noupdate=False
#     (om_hr_payroll/views/hr_contract_views.xml:14 forward-references it — repo debt;
#     pb_hr_flow's real record overwrites the placeholder at install)
#  3. load the chart of accounts BEFORE om_hr_payroll_account installs —
#     env['account.chart.template'].try_loading('generic_coa', company=browse(1))
#     (creates account.1_expense_salary / 1_salary_payable that its data refs;
#     also: pb_payruns needs journal_id, which om_hr_payroll_account adds, so the
#     module cannot simply be excluded)
# phase B: everything (list = installed-on-apex minus pb_demo,pb_demo_portal,
#          pb_website,pb_coach,pb_tenants)
# post-build: record + disable crons:
sudo -u odoo psql -d payobook_template -c \
  "INSERT INTO ir_config_parameter(key, value)
   SELECT 'pb_tenants.template_active_crons', string_agg(id::text, ',')
   FROM ir_cron WHERE active;
   UPDATE ir_cron SET active = false;"
```

## Code deploys with tenants (the new ritual)

Same staged-rsync + detached `systemd-run` ritual as before, with two changes:
1. `-d payobook` (renamed DB).
2. Loop the `-u` step over **every tenant DB + the template**:
   `payobook`, `payobook_template`, then each live tenant slug
   (list: `SELECT slug FROM pb_tenant WHERE state='live'` on the apex DB).
   Test on a staging restore of one tenant first (cockpit → Backups → Restore to staging).

## Known debt / decisions

- `om_hr_payroll/views/hr_contract_views.xml:14` points the Payroll root menu action at
  `pb_hr_flow.action_hr_flow_wizard` — an undeclared forward dependency. Fresh installs
  need the placeholder seed. Proper fix: move the action assignment into `pb_hr_flow`
  (menu record override) and `-u om_hr_payroll,pb_hr_flow` — do in a normal deploy window.
- `vendor_license_core` logs a "license missing" warning in every new DB
  (`/opt/vendor_license/license.json` absent on this box) — non-fatal, same as apex.
- **Tenant cron `Cleanup Old Analytics Data` (server action #651, from
  `payroll_analytics_approval`) errors with `NameError: name 'fields' is not
  defined`** every run — a pre-existing bug in that action's Python (it uses
  `fields.Date...` without importing/whitelisting `fields` in the `safe_eval`
  scope). Non-fatal (just a failed cron job), but noisy in every tenant now that
  crons are active. Fix: add `fields` to the action code's eval context (or
  rewrite the date math with `datetime`) and `-u payroll_analytics_approval`.
- Tenants get the stock `website` homepage on `/` (pb_website is apex-only);
  backend entry is `/odoo`. Cosmetic; revisit if clients notice.
- **`pb_explorer`'s fact builder cannot run on a database without `pb_demo`.**
  `pb_fact_builder._coverage()` selects `fc.pb_division` from `hr_formula_config`,
  and that column is declared by `pb_demo/models/demo_generator.py:37` — a field
  the demo module adds to a shared model. On `abm`, `acme` and
  `payobook_template` the build raises
  `psycopg2.errors.UndefinedColumn: column fc.pb_division does not exist`
  (11 of `pb_explorer`'s tests fail there for this one reason). Latent today
  because those databases have no payslip runs to build facts FROM; it becomes a
  failing "Payobook: build analytics facts" cron the first time a tenant runs
  payroll. Found in IA Cycle 7, NOT fixed there (untouched module, its own tests
  needed): the fix is a column probe like `pb_insights._dept_source()`, or moving
  the field out of `pb_demo`.
- RAM: the box has 1.9 GB. Each *served* database (apex + every active tenant) holds a
  registry in the threaded process. **Upgrade the Lightsail bundle to ≥4 GB before
  onboarding real client tenants.**
- Rollback of the whole platform change: restore conf backup
  `/etc/odoo-server.conf.pre-saas`, rename DB+filestore back to `Payobook19v2`,
  remove the `pb-wildcard` nginx symlink, restart.

## Tenant module-list drift (diagnosed + repaired 2026-08-19, IA Cycle 6)

**Symptom.** `acme` and `payobook_template` logged two failing crons every five
minutes from 2026-08-19 03:14 onward:

```
ERROR acme odoo.addons.base.models.ir_cron: Job 'Document OCR: retry pending jobs' (44) server action #782 failed
    KeyError: 'biz.doc.ocr.job'
ERROR acme odoo.addons.base.models.ir_cron: Job 'Payobook: build analytics facts' (46) server action #853 failed
    KeyError: 'pb.fact.run'
```

**Root cause — NOT the C2 addons-tree incident**, despite the timestamps being
neighbours. `ir_module_module` is a per-database snapshot written by
`update_list()`. The golden template was built on 2026-08-09; `pb_wf_kit`
(Workforce P0) and `pb_hub` (IA Cycle 1) were written after it, so **no tenant
database has a row for either module at all** — `acme` knows 764 modules, the
apex knows 838. Their code nevertheless lives in the shared addons tree that
every database loads, and modules the tenants DO have installed
(`pb_integrations`, `pb_structures`, `pb_govt_reports`, `pb_hr_workforce`)
later gained a `depends` on them. On the first restart after that
(2026-08-19 03:14) the module graph could not satisfy those depends and skipped
**27 modules**:

```
WARNING payobook_template odoo.modules.module_graph: module pb_integrations: some depends are not loaded (pb_hub, pb_wf_kit), skipped
…
ERROR payobook_template odoo.modules.loading: Some modules are not loaded, some dependencies or manifest may be missing: [27 modules]
```

Everything about that is quiet: `ir_module_module.state` still reads
`installed` for all 27, the registry loads in 0.9s and logs "Modules loaded."
The only loud consequence is a cron whose server action names a model from a
skipped module. See **W116** in `docs/WORKFORCE_REDESIGN_CONVENTIONS.md`.

**Repair, per tenant DB** (`/tmp/tenant_repair.sh <db>`, run detached):

```bash
# 1. refresh the per-database module list — update_list() ALONE, from a shell.
#    NOT `-u base`: that upgrades base AND every dependent, i.e. the whole
#    database. Measured on a clone of acme (Cycle 6): pb_sidebar went
#    19.0.1.7.1 -> 19.0.3.0.0, which ran the Cycle-5 rail cutover on a tenant
#    holding none of the hub modules and took the rail from 50 active items
#    to 2. The block below said `-u base` until Cycle 7 corrected it; if you
#    are reading this from an older copy, do not run that line.
echo "env['ir.module.module'].update_list(); env.cr.commit()" | \
sudo -u odoo python3 /odoo/odoo-server/odoo-bin shell -c /etc/odoo-server.conf \
  -d <db> --no-http --max-cron-threads=0
# 2. install ONLY the two roots of the skip chain; their own deps come with them
sudo -u odoo python3 /odoo/odoo-server/odoo-bin -c /etc/odoo-server.conf \
  -d <db> --http-port=8198 --max-cron-threads=0 -i pb_hub,pb_wf_kit --stop-after-init
```

**What the repair deliberately does NOT do.** It does not upgrade `pb_sidebar`
and it does not install the six hub modules. Tenant `pb_sidebar` is at
19.0.1.7.1 — the PRE-rail-cutover rail. Upgrading it would run the Cycle-5
migration and retire thirty-four rail items into hubs that are not installed on
that database, i.e. a rail of buttons whose actions do not resolve (W79/W107.2).
Tenant navigation is untouched by this repair; bringing tenants onto the Cycle-5
rail is a separate, deliberate rollout.

**Verify.** After the repair, per DB:

```bash
sudo grep -a "<db>.*some depends are not loaded" /var/log/odoo/odoo-server.log | tail
sudo grep -a "<db>.*Some modules are not loaded" /var/log/odoo/odoo-server.log | tail
sudo grep -a "ERROR <db> odoo.addons.base.models.ir_cron" /var/log/odoo/odoo-server.log | tail
```

All three must be silent for the observation window. Add "0 modules skipped" to
the post-deploy checklist beside the `latest_version` assertion (W33.2) — a
skipped module is invisible in `ir_module_module.state`.

**Standing rule this creates.** Adding a `depends` to an existing module is a
deploy step on EVERY database on the cluster, not only the one being worked on.
Enumerate `pg_database` and refresh each module list.

## Bringing a tenant DB up to the apex's module set (abm, 2026-08-19, IA Cycle 7)

> **2026-09-03 (FLEET P1): this is now a button.** Tenants cockpit → *In step with master* →
> *Bring in step*, on any customer OR on the golden template (which has its own row). It runs the
> four-step unit below in order — `update_list()`, install the missing, upgrade the stale, re-seed
> the access catalogue — then checks that nothing was skipped
> (`Registry(db)._init_modules`, ledger F7), switches the template's scheduled jobs back off
> (rail R8, ledger F9) and stamps the customer with the release it is now on. *Preview* is a dry
> run that writes nothing. The facade also accepts `<slug>-staging` so the rehearsal on a restore
> (rail R4) goes through exactly the same code. Read the section below anyway before you press it:
> it is the reasoning the button implements, and W120/W121 still apply.
>
> **Releases.** `pb.release` is a photograph of what the master runs, cut from the same screen. A
> customer is measured against the current release rather than against a moving master, and the
> nightly job *Payobook Tenants: drift from the release* (02:30) re-reads every customer — READ
> ONLY — so the fleet screen is honest in the morning. Nothing installs on a schedule, ever.


The repair above stops the crons failing. It does **not** give the tenant the
product: `abm` was 18 custom modules and 38 stale module versions behind
`payobook`. The owner authorised the catch-up for `abm` specifically ("ABM is
not live yet so you can do that"); the same procedure is what a deliberate
tenant rollout looks like, and it needs the same authorisation each time.

**No code deploy is involved.** The addons tree is shared, so every module is
already on disk — verified before starting by diffing repo manifest versions
against `/odoo/odoo-server/addons` for all 251 custom modules (3 mismatches,
all of them this cycle's own pending changes). A module missing from the tree
is a STOP, not an improvisation.

**Decide the list from three databases, not one.** `payobook` is the product
reference; `payobook_template`/`acme` are the tenant reference. Modules only
`payobook` has and no tenant has are the ones to argue about:

| module | payobook | template/acme | decision |
|---|---|---|---|
| `pb_demo`, `pb_demo_portal` | yes | no | EXCLUDE — the demo world would inject 4.5k fake employees into a client database |
| `pb_tenants` | yes | no | EXCLUDE — the SaaS platform cockpit belongs to the apex |
| `pb_website` | yes | no | EXCLUDE — apex-only marketing site; tenants keep the stock homepage |
| the other 14 | yes | partly | INSTALL — product modules (`pb_hub`, `pb_wf_kit`, the six hubs, `pb_today`, `pb_schedule`, `pb_close`, `pb_ess_workforce`, `pb_settings`, `pb_mission`) |

**The four-step unit** (rehearse on a `pg_dump` clone first — the clone caught
step 4):

```bash
# 1  update_list() alone, as above. NEVER -u base.
# 2  targeted -u of the already-installed modules whose version is behind the
#    reference. Beware W120: -u cascades to reverse dependencies, so check the
#    closure of anything you meant to exclude.
# 3  targeted -i of the delta list. Odoo pulls community dependencies itself;
#    never hand-install those.
# 4  -u pb_timeoff a SECOND time. Step 2 crossed pb_timeoff's unfreeze
#    migration, and a post-migrate runs AFTER that upgrade's data load, so the
#    Leave rail item lands on its file's values only on the next pass (W121).
```

**Evidence that the catch-up worked**, in this order: installed-module count and
the enumerated remaining diff (must equal the deliberate exclusions exactly); a
version diff per module against the reference DB; `pb_sidebar_item` joined to
`ir_model_data` and diffed row-by-row against the reference (this is what proves
the RAIL, and it is where W121 showed up); a fresh registry load with zero
skipped modules; a >=15 minute cron window with zero errors; and the apex plus
every other tenant's log clean across the same window.

---

## Status page (FLEET P3, 2026-09-03)

`https://payobook.com/status` is a **static file that nginx serves itself**. The
application writes it; nginx hands it out. That is the whole point: it is
readable on the day the application is not.

### What the platform writes

* `pb.tenants._write_status_page()` renders `alert_rules.render_status_page()`
  into `/var/www/pb-status/index.html`, temp file plus `os.replace` so a reader
  arriving mid-write gets the old page rather than half of the new one.
* Driven by the cron **"Payobook Tenants: public status page"** every 5 minutes,
  by the end of every alert sweep, and by every `notice_send` / `notice_clear`.
* It contains NO customer name, slug or count — `alert_rules.status_state()` is
  the only door between what the platform knows and what the page says, and a
  test (`test_t6_status_page_never_names_a_customer`) feeds it names and asserts
  none come out.
* A public notice's window is printed in the platform's own zone with the zone
  NAMED (`tonight 19:34–01:34 · Asia/Ho_Chi_Minh`), because a file has no reader
  to ask. Setting: `pb_tenants.status_tz`, default the platform company's zone.

### The nginx part (a deploy step, done once — already applied on this box)

`/etc/nginx/sites-available/_`, immediately BEFORE `location / {`:

```nginx
  location = /status {
    alias /var/www/pb-status/index.html;
    default_type text/html;
    add_header Cache-Control "no-cache";
  }
  location ^~ /status/ {
    alias /var/www/pb-status/;
    default_type text/html;
    add_header Cache-Control "no-cache";
  }
```

`^~` on the folder is load-bearing: the vhost has a regex location for
`.(js|css|png|…)$`, and a regex beats a plain prefix. Without it anything with
an extension under `/status/` would be proxied to the application instead.

```bash
sudo mkdir -p /var/www/pb-status
sudo chown odoo:odoo /var/www/pb-status      # the application writes it
sudo nginx -t && sudo systemctl reload nginx
```

The odoo user cannot run nginx (sudoers grants exactly three scripts), so this
is an SSH step, not something the cockpit can do.

### Proving it is nginx and not the application

```bash
curl -sI https://payobook.com/status | head
```

`Last-Modified` and `ETag` are the proof: nginx stamps a file it serves off
disk, and the application stamps neither. `pb.tenants._status_served()` asks the
same question from the box (127.0.0.1:443 with SNI) and the cockpit's **Public
status page** checklist row is green only when the file is under 15 minutes old
AND that request answered 200 with the page in it.

### If the page goes stale or missing

The page checks its own age in the reader's browser and says so after 15
minutes. On the platform side, a missing or unwritable folder raises the alert
`status_page_unwritable`. Recreate the folder with the two commands above.
