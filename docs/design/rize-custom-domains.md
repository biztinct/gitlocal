# Rize custom domains — jobs.rize.farm + people.rize.farm → one `rize` database

Status 2026-10-03: BUILT + LIVE, waiting for Rize IT's DNS. Commits ef5135f1e (routing),
850e2da70 (careers site). `server_wide_modules = base,rpc,web,biz_host_db`; both hosts in
/etc/odoo-host-db.map, attached over HTTP; /etc/cron.d/pb-domain-pending issues HTTPS within
~10 min of DNS pointing here (log /var/log/pb-domain-pending.log).

## Switch-over checklist (run when each host's HTTPS is live)

1. people.rize.farm live → rize DB: `web.base.url = https://people.rize.farm` (keep
   `web.base.url.freeze = True`). Staff email links then use it.
2. jobs.rize.farm live (Zoho retired) → `website` id 1 `domain = https://jobs.rize.farm`.
   Candidate-facing links (job pages, apply confirmations) then use it.
3. rize.payobook.com is left working as an alias (no 301): its nginx block is managed by
   pb-tenant-cert and the daily cert cron would overwrite a hand-added redirect.
4. Browser check both hosts; publish at least one role before announcing jobs.rize.farm.

The original design follows.

## Goal

| Address | Serves | Who |
|---|---|---|
| `jobs.rize.farm` | Public careers site (`/jobs`, role pages, apply form) + candidate portal (`/my`, sign-up/login) | Public, portal users |
| `people.rize.farm` | The backend (today's `rize.payobook.com`) | Rize staff |
| `rize.payobook.com` | 301 → `people.rize.farm` after cut-over (keeps old bookmarks working) | — |

All three hit the SAME Odoo process and the SAME `rize` database. A role published at
people.rize.farm is on jobs.rize.farm instantly — there is nothing to sync.

## Verified facts (2026-10-02 — do not re-derive)

1. `/etc/odoo-server.conf`: `dbfilter = ^%d$`, `list_db = False`, `proxy_mode = True`.
   `db_filter()` (`odoo/http.py:389`) takes the FIRST host label → `jobs.rize.farm` looks for a
   database named `jobs`, `people.rize.farm` for `people`. Neither exists → no-database page.
2. **`pb_tenants/tools/pb-domain-attach` is broken for this.** It sets
   `proxy_set_header X-Odoo-dbfilter ^<slug>$`, but nothing on the server reads that header
   (no `dbfilter_from_header`-style server-wide module; grep of `odoo/http.py` finds only
   `X-Odoo-Database`). Core `X-Odoo-Database` (`http.py:1801`) is NOT a substitute: it still
   has to pass `db_filter` for the host, and it marks the session stateless
   (`session.can_save = False`) so nobody could stay logged in.
   That script also uses the `certbot --nginx` installer — the trap recorded in
   [[saas-multitenant-platform]] (it can rewrite the wrong block). Don't use it as-is.
3. `rize` DB: `web.base.url = https://rize.payobook.com` (frozen); one website (id 1, "Rize",
   `domain` empty); `auth_signup.invitation_scope = b2c` (public sign-up open);
   `website_hr_recruitment`, `pb_hiring`, `rize_website`, `portal`, `biz_deroute` installed.
   **0 of 59 roles are published** — jobs.rize.farm will show an empty list until some are.
4. DNS today: `rize.farm` zone on Google Cloud DNS (`ns-cloud-d1..4.googledomains.com`).
   `jobs.rize.farm` = CNAME → `recruit.cs.zohohost.com` (their LIVE Zoho Recruit careers page).
   `people.rize.farm` does not exist. Apex/www on Wix. MX = Google Workspace. No CAA record
   (Let's Encrypt allowed).
5. Our server: `rize.payobook.com` → 3.104.113.197 (Lightsail static IP; it has changed 3 times
   historically — hence CNAME, not A, in the IT request).
6. nginx: `sites-enabled/pb-tenant-rize.payobook.com.conf` is the template to clone (has the
   `/web/database/` 404, websocket block, static caching, 80→443 redirect).

## Our side — build steps

1. **Host → database routing (server-wide, the only code).** Small server-wide module
   (`biz_host_dbfilter`, clone of OCA `dbfilter_from_header`): if request header
   `X-Odoo-dbfilter` is present, use it instead of `config['dbfilter']` in `db_filter()`.
   Add to `server_wide_modules` in `/etc/odoo-server.conf` (keep `base,web` first); restart.
   - **Security rail:** every OTHER nginx block (`_`, `pb-default`, `pb-wildcard`, every
     `pb-tenant-*.conf`, in both `location /` and `location /websocket`) must
     `proxy_set_header X-Odoo-dbfilter "";` — otherwise any visitor could send the header
     and pick another tenant's database. Test this explicitly with curl.
   - Fix `pb-domain-attach` to the same shape (certonly + own block) so the Tenants screen's
     "Domains" tab actually works for the next customer.
2. **nginx blocks** `pb-tenant-jobs.rize.farm.conf` / `pb-tenant-people.rize.farm.conf`, cloned
   from the rize block, with `X-Odoo-dbfilter ^rize$` in both locations; certs via
   `certbot certonly --nginx --cert-name pb-tenant-<host> -d <host>` (auto-renews).
   - jobs host: `location = /` → 302 `/jobs`; backend paths (`/odoo`, `/bizapp`, exact `/web`)
     → 302 `https://people.rize.farm$request_uri`. Keep `/web/login`, `/web/signup`,
     `/web/reset_password`, `/web/assets|image|content`, `/my`, `/hiring/*`, `/jobs*` open.
   - people host: `location = /` → 302 `/web/login`; `/jobs*` → 302 to jobs host.
   - rize.payobook.com: 301 → people.rize.farm (after owner confirms cut-over).
3. **rize DB settings:** `web.base.url = https://people.rize.farm` (stay frozen);
   `website(1).domain = https://jobs.rize.farm` (website-aware links — job pages, apply
   confirmations, portal invites to candidates — then use the jobs host). Check: portal
   invitation / password-reset mails to candidates carry jobs.rize.farm, staff mails carry
   people.rize.farm.
4. Update `pb.tenant` rize record / Domains tab so the fleet screen + cert cron know the hosts.

## Verification

- `curl -I` each host: 200/302 as above, valid cert, `X-Odoo-dbfilter` spoof from outside on
  `abm.payobook.com` / `payobook.com` does NOT switch database.
- Browser (Chrome MCP): publish a test role at people.rize.farm → visible at
  jobs.rize.farm/jobs → apply → application appears in Hiring at people.rize.farm.
  Candidate sign-up → lands on `/my` at jobs host. No "Odoo" anywhere (white-label rule).
- Other tenants (`payobook.com`, `abm`, template) unchanged.

## Request to Rize IT (as sent)

- `people.rize.farm` CNAME → `rize.payobook.com`, TTL 300.
- `jobs.rize.farm`: replace the Zoho CNAME with CNAME → `rize.payobook.com`, TTL 300
  — ONLY on the agreed cut-over date (it switches off the Zoho careers page).
- No proxy/CDN in front; don't add a CAA record that excludes letsencrypt.org; leave
  MX/Wix records untouched. We issue and renew HTTPS certificates ourselves.
