# FLEET P3 — Alerts that reach a human, the capacity guard, and the status page

Program doc: `docs/handovers/FLEET_PROGRAM.md` (READ FIRST, incl. ledger). Stands on P1
(`release_state`, `master_behind_files`), P2A (notices, `push_tenancy`), P2B (`pb.rollout.state`).
Gaps 5, 8 and the status half of 9 from `docs/SAAS_RELEASE_STRATEGY.html`.

## What this phase makes true (plain words)

1. When something breaks — a backup fails, a customer's site stops answering, a certificate is
   about to lapse, an update is paused, a customer's background jobs error, disk or memory runs
   low, the mail channel itself breaks — **an email reaches the owner within 15 minutes**, says
   what is wrong in one sentence and what to do next, and a second email says when it is over.
   No repeats every 15 minutes: one email per problem, a reminder every few hours while it is
   still open, and a short morning summary.
2. The Tenants cockpit has an **Alerts** view (open / acknowledged / history) and a chip in the
   header; the go-live checklist's "Outgoing mail" row becomes true only when a real email has
   actually been delivered, with a **Send a test email** button.
3. The cockpit shows **how many more customers this machine can safely hold**, measured (not
   assumed), and the New-tenant wizard refuses to create one past that point, pointing at a
   one-page resize runbook. The owner decides when to resize; the platform stops him from finding
   out the hard way.
4. **`payobook.com/status`** is a public page nginx serves on its own — it stays up when the app
   is down — showing overall health, planned maintenance, and the last week's incidents, without
   naming any customer. If the page has not been refreshed for 15 minutes it says so itself.
   That page is the hero moment: calm, honest, one glance.

## Binding NON-goals

- Email only (owner ruling). No Telegram/SMS/PagerDuty. Leave a `channel` seam in the sender so
  one can be added later, nothing more.
- No AWS resize. The runbook is written; the gauge and the guard are built; the resize is the
  owner's.
- No customer names, slugs or counts on the public status page. Ever.
- No change to what P1/P2 do; P3 only READS their fields and adds the sender/alerts.

## Verified facts for this phase

- Outgoing mail: `ir_mail_server` on the master = Gmail `smtp.gmail.com` starttls, `smtp_user
  ash@biztinct.com`, `from_filter` empty, active. 185 mails died with "You must either provide a
  sender address explicitly or configure … `mail.default.from`" (F5) or empty recipients. So:
  set `email_from` explicitly on every alert mail AND set `mail.default.from` (and
  `mail.catchall.domain` = `payobook.com` if unset) on the master as part of this phase — report
  the values you set. Verify the ICP keys first (`ir_config_parameter` on payobook).
- Recipients default: every active internal user in `base.group_system` with an email (owner is
  `ash@biztinct.com`). Param `pb_tenants.alert_emails` overrides (comma list).
- Machine: 1.9 GB RAM, 2 cores, disk 58 GB (50 % used). The single Odoo process was at 565 MB RSS
  after 3 h uptime serving master + abm (+ template/staging registries as touched). Registry LRU is
  not a bound (F6). Read `/proc/meminfo` (`MemTotal`, `MemAvailable`) and `/proc/self/status`
  (`VmRSS`); count loaded registries via `odoo.modules.registry.Registry.registries` (an LRU —
  `len()` and keys work; verify on the server).
- nginx apex vhost `/etc/nginx/sites-available/_`: `location / { proxy_pass … }` and a regex
  static-asset location; no `/status` location yet. `status` is already in `RESERVED_SLUGS`
  (`service.py:43`) so no tenant can ever claim it. Add `location = /status { alias
  /var/www/pb-status/index.html; default_type text/html; }` and `location /status/ { alias
  /var/www/pb-status/; }` BEFORE `location /` in the same file (nginx picks the exact match
  regardless of order, but keep it readable), `sudo nginx -t`, `sudo systemctl reload nginx`.
  Create `/var/www/pb-status` owned `odoo:odoo` at deploy. The odoo user cannot run nginx
  commands (sudoers grants exactly three scripts) — the page is a FILE the app writes; nginx
  config is a deploy step you do over SSH once.
- Log reader: shared with P2B's health gate (`ERROR <db> ` lines since a timestamp; tail ≤ 20 MB).
- Precedent for a fleet KPI strip and checklist rows: `get_fleet_data` (`service.py:423`) and
  `_platform_status` (`:464`, the `smtp` check at `:489` is the one you replace).
- `pb_tenants.template_active_crons` is the source of truth for the template; "template hot
  cron" = any `ir_cron.active` row on `payobook_template` (read-only SQL).

## Architecture

### Alerts (`pb_tenants/models/alert.py`, rules in `alert_rules.py`)

- `pb.alert`: `key` (Char, unique among open — e.g. `backup_failed:abm`), `kind` Selection
  (`backup_failed`, `backup_stale`, `tenant_down`, `cert_expiring`, `drift`, `rollout_paused`,
  `template_hot_cron`, `tenant_errors`, `disk_low`, `memory_high`, `mail_failing`,
  `master_behind_files`, `alert_channel_down`), `severity` (`critical`/`warning`/`info`),
  `title`, `text` (what + next step, plain English), `tenant_id`, `state` (`open`/`acknowledged`/
  `resolved`), `first_seen`, `last_seen`, `count`, `notified_at`, `resolved_at`,
  `acknowledged_by`. ACL `base.group_system`.
- **Pure rules** (T1–T4): `readings_to_alerts(readings: dict) -> list[dict]` — one function
  turns a plain dict of readings (per-tenant health/backup/cert/drift, rollout states, template
  crons, error-line counts, disk, memory, mail queue, master-behind-files) into alert dicts with
  key/kind/severity/title/text. Thresholds are arguments with defaults (disk < 15 % or < 5 GB;
  MemAvailable < 250 MB or RSS > 70 % of MemTotal; backups stale > 30 h; cert < 21 d wildcard /
  < 14 d tenant; ≥ 3 error lines in 15 min; drift behind > 7 d after the release date).
  `reconcile(open_alerts, fresh: list[dict], now) -> (to_create, to_bump, to_resolve)`.
  `should_notify(alert, now, interval_critical=2h, interval_warning=6h) -> bool`.
  `digest_lines(open_alerts) -> list[str]`.
- `_cron_alerts` every 15 min: gather readings (reads only; re-probe live tenants' HTTP quickly),
  rules, reconcile, then send: a "new problem" email per created alert (batched into ONE email
  when several appear in the same run), a reminder when `should_notify`, a "resolved" email for
  resolved criticals. `_cron_alert_digest` daily 08:00 (tenant tz of the master company or
  `Asia/Ho_Chi_Minh`): one email listing what is open, or "Nothing open. All 1 customers healthy."
- Sender `_send_alert_mail(subject, body_html, kind)`: `mail.mail` with explicit `email_from`
  (param `pb_tenants.alert_from`, default the mail server's `smtp_user`), `email_to`, `auto_delete`
  False, then `.send()` synchronously so the outcome is known NOW; if it raises or lands in
  `exception`, create/bump `alert_channel_down` (state visible in the cockpit as a rose banner —
  the one alert that cannot email itself) and log at ERROR. Subject prefix `[Payobook] `,
  severity word, tenant name. Body: plain, short, the next step, a link to the cockpit.
- Config dialog "Alert settings" (cockpit): recipients, from address, reminder intervals,
  thresholds — all ICP params `pb_tenants.alert_*`, validated (emails, ranges).

### Outgoing-mail truth

- Replace the `smtp` check in `_platform_status` with `mail`: ok when a `mail.mail` in state
  `sent` exists in the last 7 days AND `mail.default.from` is set; hint otherwise names which half
  is missing. Button **Send a test email** → `mail_test()` sends to the alert recipients via the
  sender above and returns sent / failed with the reason in plain words ("Gmail refused the
  login" etc. — map the common SMTP errors, fall back to the raw message).
- Set `mail.default.from` and `mail.catchall.domain` on the master if empty (deploy step through
  the ORM, reported).

### Capacity

- Pure `capacity_verdict(mem_total_mb, mem_available_mb, rss_mb, loaded_registries, live_tenants,
  cost_per_tenant_mb, reserve_mb) -> {'level': 'ok'|'warn'|'full', 'headroom': int, 'reason'}`.
  `cost_per_tenant_mb` is a param (`pb_tenants.tenant_cost_mb`) whose DEFAULT you MEASURE: RSS
  before and after loading the template registry through `_tenant_env`, twice, and record the
  number in the ledger; `reserve_mb` default 400 (Postgres + OS + headroom). `warn` when headroom
  ≤ 1; `full` when headroom ≤ 0.
- Fleet KPI strip: "Room for N more customers" with a bar (ok green / warn amber / full rose) and
  a tooltip with the numbers (RAM, in use, per-customer cost, reserve). Provisioning:
  `provision_start` refuses on `full` with the sentence "This machine cannot safely hold another
  customer. Resize it first — the runbook is one page." and the wizard shows the runbook path;
  `warn` shows a caution line in the wizard and proceeds.
- `memory_high` / `disk_low` alerts come from the same readings.
- Write `docs/SAAS_RESIZE_RUNBOOK.md`: Lightsail snapshot → create instance from snapshot with the
  8 GB bundle → move the static IP (verify the current IP is a Lightsail static IP; if not, say
  what to do) → boot → verify checklist (service active, registry loaded, `payobook.com`, abm,
  `/status`, certs) → set `pb_tenants.tenant_cost_mb` unchanged, delete the old instance after 48 h.
  Mark every fact you could not verify as **OWNER TO CONFIRM**. Expected downtime stated honestly.

### Status page

- Pure `render_status_page(state: dict, now) -> str` (T6): inputs = overall level, components
  list (`Sign-in & web app`, `Payroll processing`, `Email delivery`, `Customer sites`) each
  ok/degraded/maintenance, active + planned public notices (title, text, window), last-7-days
  incidents (anonymised: "A customer site was unreachable for 12 minutes" — kind + duration, never
  the name), `updated_at`. Output: one self-contained HTML file, inline CSS, the Payobook indigo
  as the single accent, system font stack, light/dark via `prefers-color-scheme`, no external
  requests, one inline script that compares `updated_at` to the browser clock and shows the
  staleness line after 15 min. **Test asserts no tenant name/slug appears** for a state that
  contains them.
- Derivation: components from open alerts (`tenant_down` → Customer sites degraded;
  `mail_failing`/`alert_channel_down` → Email delivery degraded; `rollout` running/waiting on a
  tenant ring → Customer sites maintenance; `master_behind_files`/`disk_low`/`memory_high` →
  Sign-in & web app degraded when critical). Incidents = resolved critical alerts in 7 days.
- P2A's notice dialog gains a checkbox "Also show on the public status page" (`public` flag in
  the notice JSON); `notice_send`/`notice_clear` re-render the page.
- `_cron_status_page` every 5 min AND at the end of `_cron_alerts` and every notice change:
  write `/var/www/pb-status/index.html` atomically (temp file + `os.replace`). Directory missing →
  a `warning` alert `status_page_unwritable` (add the kind) rather than a crash.
- Cockpit: the platform checklist gains "Public status page" (ok when the file is < 15 min old
  and `https://payobook.com/status` answers 200 through nginx) with a "Open" link.

### Alerts view (cockpit)

- Fleet head chip "Alerts · 2" (rose when any critical open). View: three groups (Critical,
  Warning, Acknowledged), each row = icon, title, tenant, "since 14:02 · seen 6×", the next-step
  sentence, buttons Acknowledge / Resolve (typed reason optional) / Open tenant. History tab: last
  30 days resolved, with durations. Empty state: "Nothing open. The platform will email you the
  moment that changes." Keyboard: `a` acknowledge focused row, `Esc` back.

### Tests

- **T1** `readings_to_alerts` every kind, thresholds at the edge; **T2** `reconcile` create/bump/
  resolve; **T3** `should_notify` intervals + severity change; **T4** `digest_lines`;
  **T5** `capacity_verdict` ok/warn/full + zero-division safety; **T6** `render_status_page`:
  contains levels/notices/incidents, NO names, valid HTML skeleton, staleness script present;
  **T7** model: `_cron_alerts` with a monkeypatched readings gatherer and a captured sender —
  creates, does not re-send within the interval, resolves; `alert_channel_down` raised when the
  sender raises; **T8** `mail_test` maps a fake SMTP error to plain words; **T9** existing tests.

### Live validation

- **L1** Deploy; `-u pb_tenants -d payobook`; nginx location added + reload; `/var/www/pb-status`
  created; ICP mail keys set; tests green.
- **L2** **Send a test email** → `mail_mail` state `sent`, SMTP accepted in the log; checklist row
  green. (You cannot see the inbox — say that; the owner confirms receipt.)
- **L3** Trigger a real alert without harming anything: set `pb_tenants.alert_disk_pct` to 99 →
  next cron run → `disk_low` created, ONE email sent; run the cron again → no second email;
  restore the threshold → resolved + "resolved" email (only if it was critical — disk_low is
  warning, so verify the no-resolved-mail path too). Restore all params. Screenshot the alert row.
- **L4** Capacity: measured cost in the ledger; the KPI shows the number; simulate `full` by
  setting `tenant_cost_mb` huge → wizard refuses with the sentence → restore.
- **L5** Status page: `curl -sI https://payobook.com/status` served by nginx (check the file is
  what you get, e.g. an `ETag`/`Last-Modified` from nginx, not an app response); send a public
  notice → appears within 5 min (or immediately via the notice path); Chrome screenshot in light
  and dark; the staleness line verified by faking `updated_at` in a local copy.
- **L6** Digest: run `_cron_alert_digest` once by hand → one email.
- **L7** Chrome-MCP screenshots to `docs/handovers/fleet_p3_shots/`: alerts view (filled/empty),
  settings dialog, KPI capacity bar, test-email result, status page.

## Design (verbatim bar)

"Extreme WOW, intuitive, out-of-this-world experience, best in class." Hero: the status page —
measured against Vercel/Stripe status pages (calm, one glance). Alerts view measured against
Linear's triage. Zero dead-ends: every alert carries its next step; the one alert that cannot
email itself is visible on screen. Plain language in every email and label. Motion with purpose
(new-alert row enters, resolved fades). No "Odoo" — including email bodies and the status page.

## Deploy + verify — as before. Manifest `pb_tenants` → 19.0.1.8.0. nginx change recorded in
`docs/SAAS_RUNBOOK.md` (append a "Status page" section). Cron window clean on every DB.

## Report back — the standard list, plus: the ICP mail values set, the measured per-tenant
memory cost, the exact nginx block, and the emails' subjects/bodies as sent (copy one of each).
