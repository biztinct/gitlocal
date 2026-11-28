# Rize custom domains

The staff hostname is **hrms.rize.farm**, replacing the previously planned
people.rize.farm. Both staff and careers addresses serve the existing `rize`
database; no database is copied or created.

| Address | Purpose | Cutover |
|---|---|---|
| hrms.rize.farm | Staff app; `/` redirects to `/bizapp`, then sign-in when signed out | DNS confirmed 2026-11-14; deploy HTTPS and mapping using the steps below |
| jobs.rize.farm | Careers, applications and candidate accounts | Still on Zoho on 2026-11-14; wait for a separate authorised cutover |
| rize.payobook.com | Existing working alias | Keep working |

## Routing and certificates

- `/usr/local/bin/pb-domain-attach hrms.rize.farm rize` writes the exact hostname
  mapping in `/etc/odoo-host-db.map`, generates nginx configuration and requests
  a dedicated certificate using `certbot certonly --nginx`. Do not use the
  Certbot nginx installer, which can modify another hostname's server block.
- The existing server-wide `biz_host_db` module reads changes to the map without
  an application restart. The ordinary `dbfilter = ^%d$` alone would incorrectly
  look for a database named `hrms`.
- Install `pb_tenants/tools/nginx/pb-domains/hrms.rize.farm.d/rize.conf` at the
  matching path under `/etc/nginx/pb-domains/` before attaching the domain.
- Install the jobs snippet too: backend links on the future careers host point
  to `https://hrms.rize.farm`. This does not change the jobs DNS or website domain.
- Certificates renew through `certbot.timer`; the certificate deploy hook
  reloads nginx. Verify renewal with a dry run restricted to this certificate.
- Remove the obsolete people.rize.farm mapping and nginx block after hrms works.
  Preserve unrelated mappings, standard addons and other tenants' configuration.

## Staff cutover

1. Verify the authoritative CNAME is `hrms.rize.farm -> rize.payobook.com`, TTL 300.
2. Back up the affected configuration and databases, retain the Rize backup
   permanently, and preserve other sessions' newer deployed module content.
3. Deploy the snippets and attach hrms using the existing domain script.
4. After HTTPS works, set `web.base.url = https://hrms.rize.farm` in **rize only**,
   keeping `web.base.url.freeze = True`. Use the ORM and signal cache changes.
5. Register hrms as an active custom domain for the existing Rize tenant in the
   platform's `payobook` database. Do not provision another tenant.
6. Verify HTTP-to-HTTPS, certificate hostname, root-to-app-to-login, database
   isolation, old alias, static assets, and Chrome sign-in/navigation.
7. Verify combined custom-module hashes and installed versions across
   payobook, payobook_template, p0clone and rize (also preserve the live sudima
   tenant). Upgrade only installed modules if a module upgrade is required.

No module upgrade is required for hostname-specific nginx snippets and domain
settings. ABM is retired: do not provision, upgrade or alter its archived data
or retired hostname response.

## Later careers cutover

Wait for explicit authorisation before replacing the Zoho CNAME at jobs.rize.farm.
Once its DNS and HTTPS are ready, change Rize website 1's domain to
`https://jobs.rize.farm`, then verify published roles and the candidate journey.
Do not change that website domain during the staff-only cutover.

## DNS responsibility

Rize IT manages the rize.farm zone on Google Cloud DNS (ns-cloud-d1 through d4).
Use a CNAME to `rize.payobook.com.` for each approved hostname, TTL 300, without
proxying or URL forwarding. Preserve the apex, www, email and other DNS records.
Payobook manages application routing and HTTPS certificates.
