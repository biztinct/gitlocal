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
- Tenants get the stock `website` homepage on `/` (pb_website is apex-only);
  backend entry is `/odoo`. Cosmetic; revisit if clients notice.
- RAM: the box has 1.9 GB. Each *served* database (apex + every active tenant) holds a
  registry in the threaded process. **Upgrade the Lightsail bundle to ≥4 GB before
  onboarding real client tenants.**
- Rollback of the whole platform change: restore conf backup
  `/etc/odoo-server.conf.pre-saas`, rename DB+filestore back to `Payobook19v2`,
  remove the `pb-wildcard` nginx symlink, restart.
