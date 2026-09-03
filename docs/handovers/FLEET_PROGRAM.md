# FLEET program — shipping to the fleet, and running it like a SaaS

Status: ACTIVE (started 2026-09-03). Source of the gap list: `docs/SAAS_RELEASE_STRATEGY.html`
("Shipping to the Fleet"). Owner picked the phased Fable-designs / Opus-builds cycle for the whole
stream and excluded three gaps (1 off-box backups, 2 restore drill, 11 sandbox). Everything else
in that document's PRIORITIES section is in scope here.

## Owner rulings (binding, 2026-09-03)

1. **Payments: invoices first, card later.** Each month the platform raises an invoice per customer
   from their plan and usage; the owner marks it paid when the bank transfer arrives. Overdue →
   reminders → suspension (auto-suspend is a platform switch, default OFF; suspending a live payroll
   customer without a human pressing something is not the default). No payment provider now; the
   invoice model must leave room for one later.
2. **Plans must support ALL THREE price structures, selectable per plan:** per active employee per
   month; per payslip produced per month; flat price per company by employee band (tiers). The
   meter therefore collects BOTH counts (active employees, payslips in the month) every time.
3. **Alerts by email only.** The apex already has an outgoing mail server (`ir_mail_server` row:
   Gmail, starttls) but 185 queued mails failed for two config reasons — no default sender
   (`mail.default.from` / catchall not set) and empty recipients. The alerts phase fixes the sender
   config and proves a real delivery before claiming alerts work.
4. **Memory ceiling: guard now, resize when the owner says.** Build the capacity gauge + a refusal
   to provision past the safe count + the exact resize runbook. The AWS resize itself is a separate
   owner-scheduled step (30–60 min downtime).
5. Standing rules apply (see every handover): no "Odoo" in any user-visible string; plain-English
   UI copy in the screen's vocabulary; Lucide icons via the shared `ic()` registries; `--pbim-*`
   tokens; no gradients/emoji; the WOW bar verbatim; commit per feature, never push.

## The six phases

| Phase | Gaps closed | What ships |
|---|---|---|
| **P1 Drift & stamp** | 3, 4 | Version-aware "In step with master" (install AND update), module-list refresh before install, 0-skipped check, `pb.release` cut from the master, release stamp per tenant, nightly drift check, the golden template on the same screen |
| **P2 Release & rollout** | 4, 9 (banner, what's new) | Rings (rehearsal / canary / early / everyone), a queued per-tenant rollout job with lock + retry + health gate + stop rule, the tenant-side agent module `pb_tenancy` (banner, what's-new, the push-parameter seam every later phase uses) |
| **P3 Alerts, capacity, status** | 5, 8, 9 (status page) | `pb.alert` events + dedup + email delivery (sender config fixed and proven), platform "Outgoing mail" check made real, memory gauge + provisioning guard + resize runbook, static status page nginx serves at `/status` with a staleness self-check, planned-maintenance notice |
| **P4 Feature switches** | 6 | `pb.feature` catalogue on the apex, per-tenant on/off with reason, pushed to tenants, `pb_tenancy` helpers (server + JS) and a `feature_key` gate on sidebar items so a switched-off feature vanishes cleanly |
| **P5 Plans, trial, suspend, invoices** | 7 | `pb.plan` (three price structures), tenant `trial`/`suspended`/`pending_deletion` states with a retention clock, monthly usage meter, invoices (own model, PDF, email, mark paid, overdue → reminder → optional auto-suspend), seat-limit enforcement + trial/limit banners on the tenant, customer-side "Plan & usage" card |
| **P6 Support access with a trail** | 10 | "Open as support" from the cockpit: reason required, one-time token, time-boxed session as the recovery account, every access logged on the tenant where the customer's administrator can read it, customer switch to refuse support access |

Handovers (all written 2026-09-03; later ones are adjusted from earlier reports before launch):
`FLEET_P1_DRIFT.md` · `FLEET_P2A_TENANCY.md` · `FLEET_P2B_ROLLOUT.md` ·
`FLEET_P3_ALERTS_CAPACITY_STATUS.md` · `FLEET_P4_FEATURE_SWITCHES.md` ·
`FLEET_P5_PLANS_BILLING.md` · `FLEET_P6_SUPPORT_ACCESS.md`.

Each phase: Fable writes `docs/handovers/FLEET_P<n>_*.md`, launches an Opus agent with it, reads
the report, updates the ledger below, designs the next. Owner is not asked between phases unless
a phase report shows a failure, a spec deviation, or a destructive/irreversible step.

## Verified plumbing (2026-09-03 — do not re-derive)

### The platform, as it is
- One server (`ssh Payobook19v2`), one process (no `workers`, no cron time limit — threaded), one
  `addons_path=/odoo/odoo-server/addons`, `dbfilter = ^%d$`, `limit_time_real = 1200`. Framework
  is Odoo 19 at git `db2cd8c1` (2026-06-16). RAM 1.9 GB. Registry LRU: `odoo/orm/registry.py:97`
  sizes it from `limit_memory_soft` (unset → 2048 MB / 15 MB ≈ 136) — i.e. NOT a real bound;
  physical RAM is the bound.
- Databases: `payobook` (master, 224 installed modules, 2.2 GB), `abm` (live tenant AB Mauri, 220
  installed), `payobook_template` (golden template, 203 installed, 117 MB), `p9clone` (1.7 GB
  rehearsal clone of the master from ACCESS P9 — owner debt: drop when no longer needed),
  `postgres`. Tenant `acme` (id 1) is **decommissioned**; its DB is gone. `pb_tenant` rows: 1 acme
  decommissioned, 2 abm live.
- Live drift today: abm has `pb_settings` and `pb_vendor_access` at 19.0.1.6.0 vs master 19.0.1.7.0
  (the Sync screen shows abm "in step" — the bug P1 fixes). Template is 21 modules behind.
- nginx: `sites-enabled/_` (apex, `server_name payobook.com`, `location ^~ /web/database/ {return 404;}`),
  `pb-wildcard`, `pb-tenant-abm.payobook.com.conf`. `/var/www/html` exists.
- Outgoing mail: 1 `ir_mail_server` (Gmail starttls, active). `mail_mail` states: outgoing 15,
  sent 11, cancel 176, exception 185 (reasons: "You must either provide a sender address explicitly
  or configure … mail.default.from"; "At least one valid recipient").

### `pb_tenants` (apex-only cockpit; never installed on a tenant)
- Manifest `pb_tenants/__manifest__.py` v19.0.1.4.0, depends `web, pb_import_kit, pb_sidebar, pb_hub`;
  assets `tenants.scss`, `pbtn_icons.js`, `tenants.js`, `tenants.xml`. Data: `security/ir.model.access.csv`
  (3 models, `base.group_system` full), `views/pb_tenants_action.xml` (client action tag `pb_tenants`),
  `data/pb_sidebar.xml`, `data/cron.xml` (nightly backups 19:30, certs 03:15, health hourly).
- Models `pb_tenants/models/tenant.py`: `pb.tenant` (state draft/provisioning/live/error/decommissioned;
  health cache fields; cert fields; `backup_ids`, `domain_ids`), `pb.tenant.backup`, `pb.tenant.domain`.
- Facade `pb.tenants` AbstractModel in `pb_tenants/models/service.py` (1730 lines). Every RPC starts
  with `_require_admin()` (:288). Helpers: `_param` :294, `_pg_cursor(db)` autocommit SQL :314,
  `_db_exists` :324, `_tenant_env(db)` ORM env on another DB, commits on success :353, `_probe` :360,
  `_log_line` :403, `_human` :414. Fleet: `get_fleet_data` :423, `_tenant_brief` :449,
  `_platform_status` :464 (checks list incl. `smtp` = `ir_mail_server` count > 0 :489 — a lie by
  omission, P3 replaces it). Provisioning :593–731 (`PROVISION_STEPS` :231; `_step_configure` sets
  `pb.tenant.slug` param :677 and re-enables template crons from param
  `pb_tenants.template_active_crons` :725–730). `_step_admin` :733; rails :770–980;
  `_ensure_break_glass` :792 (recovery account `platform.recovery@payobook.com`, no password, no
  email, has `base.group_system`). Sync: `TENANT_SYNC_NEVER` :171, `TENANT_SYNC_NEVER_PREFIXES` :193,
  `sync_split` :196 (NAMES ONLY), `_installed_on` :1102 (names only), `sync_report` :1123,
  `sync_install` :1178, `_sync_install` :1193 (`button_immediate_install` then a fresh env +
  `pb.access.reseed_catalogue()`). Detail/health :1388–1457 (`HEALTH_PROBES` :246). Backups
  :1461–1506, staging restore :1509, offboard :1545, domains :1573–1636, crons :1640–1730.
- Cockpit `pb_tenants/static/src/js/tenants.js` (388 lines): `PbTenants` OWL component, services
  orm/action/notification/dialog, `hubBack` chip, `state.view` ∈ fleet | wizard | sync | detail;
  `ic()` :52 merges `TIC` (pbtn_icons.js) with the kit registry. Sync screen :231–283; detail
  :284–381. Template `static/src/xml/tenants.xml` (529 lines): fleet :6, sync :293–390, detail
  :393+ with tabs overview/backups/domains/danger. SCSS `.tnx` scoped, `--pbim-*` tokens.
- Tests `pb_tenants/tests/`: `test_currency.py`, `test_tenant_admin_rails.py` (guards only),
  `test_tenant_sync.py` (pure `sync_split` + never-list asserted against disk + source-text
  assertions). Pattern: the decision is a pure function; the cross-database write is proven on a
  clone at deploy time and reported.

### Seams the later phases use
- **Tenant-side hook point:** `pb_sidebar/models/pb_sidebar.py` — `pb.sidebar.item` has `groups_id`
  :45, `restricted`/`restriction_reason` :51–57 (locked teaser), the ONE visibility rule
  `_state_for` :85, `visibility_for` :92, `get_sidebar_data` :121 (builds `_item_dict` :150). A
  `feature_key` gate slots into `_state_for`/`get_sidebar_data` (P4).
- **WebClient patch precedent (banner mount):** `biz_theme/static/src/js/biz_sidebar_menu.js:217`
  `patch(WebClient, {components: {...WebClient.components, BizSidebar}})`.
- **Settings hub cards:** `pb_settings/static/src/js/settings_hub.js` `CATEGORIES` :126 (card =
  `{id, tag|xmlid, icon, …}`); server gates `pb.settings.resolve_gates`
  (`pb_settings/models/pb_settings.py:110`) with `PLATFORM_ONLY_*` refusal. Customer-facing cards
  ("Plan & usage", "Support access", "What's new") are added here (P5/P6/P2).
- **Request seams (Odoo 19, server copy):** `odoo/addons/base/models/ir_http.py` `_authenticate`
  :271, `_authenticate_explicit` :276, `_pre_dispatch` :298, `_dispatch` :347, `_post_dispatch`
  :359; `addons/web/models/ir_http.py` `_pre_dispatch` :57, `session_info` :79.
  `odoo/http.py` `Session.authenticate(env, credential)` :1201 (credential dict has `login`,
  `password`/`type`; `finalize` :1240).
- **Tenant admin role:** `pb_vendor_access.role_tenant_administrator` (hooks.py:371), a bundle
  WITHOUT `base.group_system`. The customer's "administrator" is that role, so any customer-facing
  platform card must gate on something the role holds (the `access-team` ability is REQUIRED for
  the role — hooks.py:375) or on `pb.company.profile`'s existing gate, never on `group_system`.
- **Payslip meter:** tenants have `hr_payslip` (`om_hr_payroll/models/hr_payslip.py:30`,
  `date_from` :47, `date_to` :49, `state` :53). Active employees: `HEALTH_PROBES` SQL already.
- **Mail precedent on the apex:** `pb_lifecycle/models/letter.py:251` `action_send` builds
  `mail.mail` — note its :270 comment on empty `email_to`.

### Deploy + verify (authoritative: repo `CLAUDE.md` deploy contract)
- Clean staging dir; per-module scoped `rsync --delete` into `/odoo/odoo-server/addons/<m>/`;
  NEVER `--delete` with the addons dir itself as destination. `-d payobook` for the master.
- `pb_tenants` is installed on the master ONLY. `pb_tenancy` (from P2) is installed on the master,
  the template AND every tenant (it is a product module; the never-list stays the four).
- Every `odoo-bin` run alongside the live service passes `--http-port=8199 --gevent-port=8198`
  (or `--no-http` for shells) and `--max-cron-threads=0`. Detached `systemd-run` + sentinel for
  anything longer than an SSH keepalive. Never `pkill -f odoo-bin`.
- After JS/SCSS: purge `/web/assets/%` attachments AND bump `web.assets.version` per DB.
- Verify per DB: tree hashes repo↔server; `latest_version` vs manifest (normalise the `19.0.`
  prefix); "0 modules skipped" in the log; 15-minute cron window clean.
- Tests: `--test-enable --test-tags /pb_tenants -u pb_tenants -d <scratch or payobook>` — a
  bare `--test-tags` without a scoping `-u` crashes DB init (W9).
- Chrome-MCP validation on the live cockpit is mandatory before reporting done (design mandate).
  If the MCP tools are disconnected, drive Chrome over CDP on `127.0.0.1:9222` from a Node script
  (see the standing approval memory) — never skip.

## Design bar (verbatim, binding on every phase)

**"Extreme WOW, intuitive, out-of-this-world experience, best in class."** Not "clean and
functional" — the screen should make someone stop. Every phase must state and satisfy:
- a **hero moment** (a live preview, a diff that animates in, a grid that feels like a spreadsheet,
  a single reassuring sentence in plain language) — name it in the design;
- **zero dead-ends**: every state (empty, loading, error, partial, huge) is designed, every failure
  names its reason and its next step;
- **plain-language over code vocabulary** on every label, toast and summary;
- **motion with purpose** (enter/exit, progress, state change) — never decorative jitter;
- **keyboard + bulk ergonomics** where rows are involved (multi-select, shift-range, paste, undo);
- measured against the best consumer/SaaS tool in that category (Vercel, Linear, Stripe
  dashboards), not against stock Odoo.
Palette/tokens: `--pbim-*` (pb_import_kit), indigo `#5A4BB0` primary; promoted semantics only
(green `#2E7D4F`, amber `#D97706`, blue `#2563EB`, rose `#DC2668`); never invent a hex. Lucide
icons via `ic()`; new glyphs go in `pb_tenants/static/src/js/pbtn_icons.js` `TIC` (apex) or the
kit registry (shared). The phase report scores itself against this bar.

## Rails (every phase)

- **R1 Never a silent write to a customer's database.** Every cross-DB action is a person
  pressing a button with a dry run available, OR a queued job the person started, with a per-tenant
  log line. Crons may READ tenants freely; a cron that WRITES to a tenant (rollout worker, meter
  snapshot, banner push) only does what a person queued, and says so in the tenant's log.
- **R2 The never-list stands.** `pb_tenants`, `pb_demo`, `pb_demo_portal`, `pb_website` and the
  `pb_platform*` prefix never reach a tenant. Re-asserted on the literal list about to be written.
- **R3 The master is upgraded first, the template second, tenants last.** Nothing ships to a
  tenant at a version the master has not run.
- **R4 Rehearse on a restore.** Before the first real tenant of any phase's live validation, run
  the action on `<slug>-staging` restored from the tenant's latest backup.
- **R5 Cross-DB writes go through `_tenant_env` (ORM), never raw SQL**, so `ir.config_parameter`
  and other ormcaches on the running tenant registry are invalidated. Raw SQL is for reads.
- **R6 Pure decisions, tested.** Any decision that a test cannot reach because it touches another
  database is lifted into a pure function with its own test (precedent: `sync_split`, `currency_change`).
- **R7 Plain-English strings, no "Odoo".** Every user-visible string; technical identifiers untouched.
- **R8 Template hygiene.** Anything installed on `payobook_template` that creates crons: disable
  them afterwards and append their ids to `pb_tenants.template_active_crons` (the provisioning
  step re-enables from that list). A template with a live cron is a template with a hot registry.

## Ledger (F-numbers — every phase appends; gotchas AND rulings)

- **F1** (P0, 2026-09-03) `sync_split` compared names only; `abm` sat 2 versions behind while
  green. Version comparison must normalise the `19.0.` series prefix on BOTH sides and compare
  int-tuples (`1.10.0 > 1.9.0`).
- **F2** (P0) Python/JS behaviour reaches every DB at the next restart (shared addons tree);
  only XML/data/schema wait for `-u`. Hence R3, and hence the "master behind its own files" check.
- **F3** (P0) Odoo `ir.module.module.update_list()` is per-database; a `depends` added on the
  master leaves tenants unable to load until each tenant's list is refreshed (the 2026-08-19
  27-skipped incident). Refresh the list on the tenant before every install.
- **F4** (P0) `button_immediate_install/upgrade` rebuilds that DB's registry and closes the env;
  anything after it needs a fresh `_tenant_env`.
- **F5** (P0) The apex mail server exists but `mail.default.from` is unset → every mail without an
  explicit `email_from` dies in `exception`. Alerts set `email_from` explicitly AND fix the ICP.
- **F6** (P0) Registry LRU is sized from `limit_memory_soft`, which is unset → ~136 slots. The
  memory guard must measure real RSS/free memory, not the LRU.
- **F7** (P1, 2026-09-03) **The skipped check.** `Registry(db)._init_modules` is the set of modules
  the registry actually loaded (`odoo/orm/registry.py:256`, filled in
  `odoo/modules/loading.py:237`); `loading.py:495` computes the server's own "Some modules are not
  loaded" from the same idea. So *skipped = installed-in-the-database − `_init_modules`*, which is
  what `pb.tenants._skipped_on(db)` returns. It answers `-1` when the attribute is missing or empty
  rather than a green 0. Measured 0 on `payobook`, `abm` and `payobook_template`. No log grepping
  needed; the log fallback in the P1 spec was not used.
- **F8** (P1) **The two version fields are named the opposite way round.**
  `ir.module.module.latest_version` is the version THIS DATABASE has applied;
  `installed_version` is a compute off the manifest ON DISK
  (`addons/base/models/ir_module.py:285-289` says so in a comment). Both carry the `19.0.` series —
  `installed_version` because Odoo runs `adapt_version()` over the manifest — so `norm_version`
  handles either shape. Rail R3's check is `installed_version > latest_version`.
- **F9** (P1) **Upgrading anything on the golden template switches its scheduled jobs back on.**
  The template had 0 active jobs; upgrading `pb_settings` + `pb_vendor_access` left 9 active,
  because their cron records reload with `active` true. R8 is therefore not a build-time chore, it
  is part of every template touch, and `sync_bring_in_step` runs `template_cron_plan` at the end of
  each template run. The recorded list `pb_tenants.template_active_crons` went 41 → 52 ids: the 9
  live ones had never been recorded because they were created after the template was built.
- **F10** (P1) **A keyboard shortcut bound to `window` never fires in this web client.** Something
  in the shared client listens for `keydown` on `<body>` and stops the event there, so a `window`
  listener (the obvious place, and where the cockpit's `r`/`Esc` started) hears nothing at all —
  silently. Bind to `document` with `{capture: true}` and bow out for `INPUT`/`TEXTAREA`/
  contenteditable and for any open `.o_dialog`/`.modal.show`.
- **F11** (P1) The deny-list, the split and every version judgement now live in
  `pb_tenants/models/sync_rules.py`; `service.py` re-exports the names, so existing imports are
  unchanged. `test_tenant_sync.py`'s source-text assertions were retargeted (`_rules_source()` for
  the owner-rule quote; `sync_bring_in_step` for the third guard) and gained the update path
  (`button_immediate_upgrade`), a `-u base` prohibition and a read-only assertion on the new cron.
- **F12** (P1) `pb.tenants.sync_bring_in_step` accepts three targets and nothing else: a tenant id,
  the string `template`, or `<slug>-staging` where `<slug>` is a real tenant (rail R4's rehearsal
  door). Every other name is refused by name. `sync_install` is now a thin wrapper over it.
- **F13** (P2A, 2026-09-03) **`HttpCase` cannot reach a single route on this server without
  `--db-filter=.*` on the command line.** The live configuration picks the database out of the
  hostname (`dbfilter = ^%d$` in `/etc/odoo-server.conf`), and a test client calls itself on
  `127.0.0.1`, which resolves to a database named `127`. Every route then answers **404 with an
  HTML body**, so the failure looks like a broken controller rather than a routing mismatch — it
  cost two full test cycles here. The full command is
  `odoo-bin -c … -d payobook -u <mods> --test-enable --test-tags /<mods> --db-filter=.*
  --http-port=8199 --gevent-port=8198 --max-cron-threads=0 --stop-after-init`.
  Second half of the same gotcha: `self.authenticate('admin', 'admin')` fails on every live
  database, because the administrator's password is not `admin`. An `HttpCase` here creates its own
  user with a known password in `setUp` (see `pb_tenancy/tests/test_tenancy.py`).
  Also: `odoo-bin`'s output does NOT go to the shell — `logfile = /var/log/odoo/odoo-server.log` is
  set in the config, so a `> /tmp/x.log` redirect captures nothing but the sentinel. Read the
  server log for `odoo.tests.result: N failed, M error(s) of K tests`.
- **F14** (P2A) **The tenant-side poll runs on every visible tab, not only while a notice is
  showing.** The P2A spec asked for the cheaper rule (poll only while a notice is up, plus on
  becoming visible); that rule cannot satisfy the phase's own acceptance test, because a page with
  no notice would never discover that one had been sent. `pb_tenancy`'s service therefore polls
  `/pb_tenancy/state` every 60 s **while `document.visibilityState === "visible"`**, plus
  immediately when a hidden tab comes back after more than 60 s. Measured consequence, and it is
  the one to remember when validating: **a background tab does not update.** Chrome-MCP drives
  several tabs, and the tenant tab is hidden while the cockpit tab is being driven — so "the bar
  did not appear" during validation was the design working, not a failure. Bring the tenant tab to
  the front (`select_page` with `bringToFront`) before timing anything.
- **F15** (P2A) **An OWL `t-foreach` loop variable must never be called `lt`.** `t-as="lt"` compiles
  to `<.id` / `<.name` in the generated JavaScript — the template compiler rewrites the name into a
  literal `<` — and the WHOLE component then fails with
  `Failed to compile template "…": Unexpected token '<'` and a blank screen with an "our side" error
  dialog. Nothing points at the loop; the only clue is the generated source in the console. Assume
  the same for any other HTML-entity name (`gt`, `amp`, `quot`). Name loop variables for what they
  hold (`cust`, `row`, `mod`).
- **F16** (P2A) **JavaScript built-ins are not in scope inside an OWL template.** A template
  expression is compiled against the component, so `String(x)` becomes `ctx.String(x)` and throws
  `TypeError: ctx.String is not a function` — but only when that branch is first rendered, which
  here was the moment a `t-foreach` over an initially-empty list gained its first row. Coerce on the
  component side; templates hold property access and comparisons only.
- **F17** (P2A) **`<input type="datetime-local">` speaks the reader's wall clock; the server speaks
  UTC.** Passing one straight to the other moves every window by the operator's offset (seven hours
  on this box) with no error anywhere — the platform owner types "22:00 tonight" and the customer's
  bar announces maintenance in the middle of their morning. `tenants.js` converts both ways
  explicitly (`_forInput` UTC→local for the two boxes, `_toUtc` local→UTC for the preview AND the
  send, so the preview cannot disagree with what is delivered). Verified end to end: 22:00–01:00
  local typed on the cockpit stored as `12:00–15:00` UTC and rendered back as `tonight 22:00–01:00`
  on the customer's screen.
- **F18** (P2A) **Where the tenant banner mounts, and why not where P1's spec guessed.** Two modules
  on this build (`biz_theme/static/src/xml/biz_sidebar_menu.xml:8` and
  `pb_sidebar/static/src/xml/webclient_patch.xml:4`) already `position="replace"` the SAME
  `//ActionContainer` node; a third would be a race between load orders. `pb_tenancy` inserts
  `<PbTenancyBanner/>` **after `//NavBar`** instead, which nothing else touches. The server's own
  `web.WebClient` is four lines (`NavBar` inside `t-if="!state.fullscreen"`, then `ActionContainer`,
  then `MainComponentsContainer`), so the bar inherits the fullscreen guard — correct: a full-screen
  surface is a surface with no chrome.
- **F19** (P2A) **Only the `pb.tenants` facade's OWN cross-database writes go through `_tenant_env`;
  the asset ritual on a tenant does not.** Purging `/web/assets/%` and bumping `web.assets.version`
  with `psql` leaves the running tenant registry's ormcache holding the old version. The attachments
  being gone makes the bundle rebuild anyway, so the visible result is right — but restart the
  service after the SQL rather than relying on that.
- **F20** (P2A) `ir.config_parameter.set_param(key, '')` **writes an empty string, it does not
  delete the row** (`addons/base/models/ir_config_parameter.py:94` unlinks only on `False`/`None`).
  So clearing a notice leaves `pb_tenancy.notice` present and empty, which is what the reader
  expects. Related: `pb_tenants.template_active_crons` lives on the **template's** database, not the
  master's — looking for it on `payobook` finds nothing and looks like data loss. On
  `payobook_template` it holds 52 ids, and all 58 of that database's scheduled jobs are inactive
  (rail R8, verified after this phase's install).
- **F21** (P2A) `type='json'` is a **deprecated alias** on this framework — `odoo/http.py:788` logs
  "Since 19.0, @route(type='json') is a deprecated alias to @route(type='jsonrpc')" on every boot.
  New routes use `type='jsonrpc'`, and a read-only one adds `readonly=True`.
- **F23** (P2B, 2026-09-03) **An unset Datetime reads as `False`, not `None`.** Every helper that
  takes "a moment or nothing" must test falsiness, not identity: `if dt is None` lets the boolean
  through and the next line asks it for its `tzinfo`. It broke the state machine the first time a
  wave finished (`ring_done_at` empty). Same family as F20.
- **F24** (P2B) **`ir.config_parameter.get_param` cannot express "deliberately empty", and lies
  about "absent".** It answers **`False`** for a key that is not there — not `None` — and its body
  ends in `or default`, so a value explicitly set to `''` also comes back as the default. A list
  parsed from it therefore became `["False"]`, a filter that filters nothing and looks exactly like
  a working one. Any setting where empty is a meaningful answer must `search` the
  `ir.config_parameter` row and read `.value` (`pb.tenants._log_ignore` is the pattern).
- **F25** (P2B) **The health gate needs an ignore list, because this box makes noise.**
  `vendor_license_core` writes one `ERROR` on **every registry load of every database** ("License
  check FAILED: missing — License file not found at /opt/vendor_license/license.json"). It stopped
  the first rehearsal of the first rollout on a copy that was in perfect health. A gate that cries
  wolf on every run is a gate the owner learns to click past. `rollout_rules.DEFAULT_LOG_IGNORE`
  plus the setting `pb_tenants.health_ignore` (one substring per line, case-insensitive); ignored
  lines are still RECORDED on the task and counted on screen, never deleted.
- **F26** (P2B) **Restoring a database logs errors of its own**, so a health window that starts
  before the restore blames the update for them: `odoo.sql_db: bad query … SELECT latest_version
  FROM ir_module_module` ×2, because the framework asks a half-built database what version it is
  on. The rehearsal's window starts when the UPDATE starts. Related, and rail R4: the restore call
  belongs INSIDE the `try` whose `finally` drops the copy — outside it, a damaged backup leaves a
  part-restored database on a box with 1.9 GB of RAM.
- **F27** (P2B) **The health gate's exact log query.** `/var/log/odoo/odoo-server.log`, last
  ≤ 20 MB only (the file is ~85 MB), lines matching
  `^(<ts>),\d+ \d+ (\w+) (\S+) ([^:]+): (.*)$` where the level is `ERROR`/`CRITICAL`, the database
  column equals the target database, and the timestamp is ≥ the moment the update started. **The
  server's clock is UTC and the framework stores UTC, so the two compare as strings with no
  arithmetic** — the day this box moves to a local zone, that comparison is what quietly stops
  working. The logger name is kept in the stored line: it is the only part that says which piece of
  the product complained.
- **F28** (P2B) **A rollout is written down once and walked; the tests must stand down the real
  fleet.** `TransactionCase` on `payobook` runs against real `pb.tenant` rows and real `pb.rollout`
  rows, so a live customer joins every plan (`filtered()` stops being a singleton) and a genuinely
  paused rollout makes every test fail with "one is already going out" — the guard working, against
  the suite. `setUp` decommissions the tenants and aborts the rollouts inside the transaction,
  which is rolled back and never reaches them.
- **F29** (P2B) **A test cursor's `commit` refusal is bolted to the INSTANCE, not the class.**
  `patch.object(type(self.env.cr), 'commit', …)` does nothing; `patch.object(self.env.cr, 'commit',
  lambda: None)` is what lets a cron body that commits per customer be tested at all.
- **F30** (P2B) **"Run now" skips the window, never the queue.** `advance()` only ever looks at the
  CURRENT wave, so setting `run_now` on a customer in a later wave silently did nothing. That is
  the right behaviour — the order of the waves is the safety argument — so it is now a refusal by
  name pointing at "Continue now", and the button is only offered inside the active wave.
- **F31** (P2B) **Rail R4 must be enforced, not hoped for.** With the only usable backup file moved
  aside, `plan_tasks` shrugged, left the rehearsal out with a warning, and offered to update a real
  customer with nobody having rehearsed anything. No backup + at least one live customer is now a
  blocker on Start, naming the customer and the button that takes a backup.
- **F32** (P2B) **A customer's window has to be SAID in the customer's clock.** `render_range`
  formats whatever it is handed, so handing it UTC printed "today 15:00–18:00" on a screen whose
  next line said "on their clock". `to_local(dt, tz)` converts first; the plan and the Updates tab
  now read "tonight 22:00–01:00 · their time · Asia/Ho_Chi_Minh". F17 is the same trap pointing the
  other way.
- **F33** (P2B) **Measured: one customer task is seconds, not minutes, on this fleet.** abm
  (1.2 GB, 153 employees) took **8 s** for a one-module version move and **1 s** with nothing to do;
  the golden template 8 s and 1 s; the rehearsal **80–86 s**, of which ~60 s is the restore of a
  219 MB backup. So the "being updated right now" bar is genuinely up for about a second here — a
  fact to remember when validating, not a bug. The pre-notice, the in-progress notice and the clear
  are all provable from `pb_tenant.provision_log` and the rollout's own trail.
- **F34** (P3, 2026-09-03) **Measured: a second customer's registry costs about
  5 MB of resident memory on this box, and that number is far too small to be the
  capacity guard.** RSS before and after `_tenant_env()` on `payobook_template`:
  219.4 → 224.0 MB (**+4.6 MB**, 0.8 s); a second call on the same database
  **+0.0 MB** (registries are cached); `abm` after it **+3.9 MB** (0.9 s); with a
  real read workload on top of each (all users, all modules, all field
  definitions, 500 employees, a view count) **+5.6 MB** and **+4.9 MB**. Repeated
  in a second process: identical. Odoo's own comment sizing the registry LRU says
  "a registry takes 10MB of memory on average", so the measurement is in the
  expected place. But a per-customer cost of 5 MB puts "room for 54 more
  customers" on a 1.9 GB box, which is a guard that can never fire. The resident
  registry is not what a customer costs: sessions, asset caches and the working
  set of a pay run are, and they are transient and unmeasurable at rest. So
  `pb_tenants.tenant_cost_mb` is set to **60** — the measured 5 MB plus a
  deliberate allowance — and it is a setting, on the Alert-settings dialog, to be
  re-weighed as customers are added. With 870 MB free and 400 MB reserved that
  reads "room for 7 more customers". **The number in the setting is a policy, not
  a measurement; the measurement is the 5 MB above.**
- **F35** (P3) **The cockpit's own stylesheet has TWO root blocks, and the second
  one is not `.tnx`.** `tenants.scss` is `.tnx { … }` (lines 2–292) and then
  `.tnx-notice { … }` (300+), and the detail/updates/timeline rules live inside
  the SECOND. A block appended "at the end of the file, before the closing brace"
  therefore compiles to `.tnx-notice .tnx-capbar` and matches nothing — the
  capacity bar shipped 0 px tall with no error anywhere. P3's styles are now their
  own root-scoped section (the two dialogs are scrims, exactly like the notice
  composer, which is why that block is root-scoped in the first place).
- **F36** (P3) **`min()` in SCSS is the compiler's own function and it refuses to
  mix units.** `max-height: min(64vh, 640px)` fails the WHOLE bundle, and the
  failure is not local: the cockpit renders as unstyled HTML under a red banner
  reading "A css error occured, using an old style to render this page". Use a
  single unit, or `#{}` interpolation.
- **F37** (P3) **The shared kit out-specifies a bare class.** Kit buttons are
  styled `.pbim .pbim-btn.outline` (three classes); a state rule written
  `.tnx-alertchip.bad` (two) loses, silently. The alerts chip stayed indigo while
  a customer was unreachable. Any state colour on a kit control needs `.pbim` on
  the front.
- **F38** (P3) **A static page has no reader to ask what time it is.** F17 and F32
  are about converting to a KNOWN clock — the operator's browser, the customer's
  zone. A file on disk has neither, so a window rendered straight from the stored
  UTC printed "today 12:34–18:34" for a maintenance slot the owner typed as 22:34.
  The public page now converts to the platform's own zone and NAMES it
  ("tonight 19:34–01:34 · Asia/Ho_Chi_Minh"), which is the only honest form.
  Verified live against the customer's own bar showing 22:34–04:34 in the reader's
  browser clock at the same moment: two different sentences, both correct.
- **F39** (P3) **The 15-minute sweep must read the log ONCE, not once per
  customer.** P2B's `_log_errors_since` reads a 20 MB tail for one database; the
  sweep asks about every live customer plus the master every quarter of an hour.
  `_log_error_counts(dbnames, since)` does the same regex, tail and ignore list
  (F25) in a single walk. The master's own error count is gathered and is
  deliberately NOT alerted on — this box logs its own test runs and the licence
  line, and a rule for it would have to be written against that noise first.
- **F40** (P3) **The stamp that says "we told you" is only written when the
  message actually left.** If a send fails and the alert is stamped anyway, the
  problem goes quiet for two hours on the strength of an email nobody received —
  the exact failure this phase exists to end. `_speak()` stamps per record after
  `_send_alert_mail` returns ok, and a failed send raises `alert_channel_down`,
  which is the one kind `reconcile()` never resolves on its own (no reading can
  see it) and the one kind that is rendered as a banner at the top of the fleet.
- **F41** (P3) **Validation alerts must be DELETED, not left to resolve.** A
  resolved critical becomes an incident on the PUBLIC page for seven days. The
  three alerts raised by moving thresholds during live validation
  (`backup_stale:abm`, `cert_expiring:abm`, `disk_low`) were unlinked afterwards
  so the page does not advertise incidents that never happened. Any future live
  test of the alert path has to end the same way.
- **F42** (P3) **The go-live checklist used to hide itself the moment the five
  provisioning checks were green**, which would have hidden P3's two new rows —
  including the "Send a test email" button, which is wanted on a good day too.
  The card now shows while ANY check is unfinished and is one click away from the
  live strip ("Platform checks") when they are all green.
- **F43** (P3) **The word "odoo" reached a user-visible string through a system
  ACCOUNT name.** "create /var/www/pb-status and give it to the odoo user" is a
  technical instruction, and the standing rule is still absolute for anything on
  a screen: it is now "…and let the application write to it". The test that
  caught it asserts `'odoo' not in a['text'].lower()` for every alert kind and is
  worth copying into any phase that writes operator-facing sentences.
- **F44** (P3) **A file written by a model is not rolled back by a test.** The
  suite runs against a fabricated fleet inside a transaction that is thrown
  away — but `alert_ack`, `alert_resolve` and P2A's `notice_send` all rewrite
  `/var/www/pb-status/index.html`, which is not in that transaction. A test run
  on the live platform therefore PUBLISHED a page built from invented customers.
  It was harmless the day it was found and one fabricated critical away from
  telling the world about an incident that never happened. `_write_status_page`
  now returns early when `odoo.tools.config['test_enable']` is set — at the
  writer, not in each test, because the next caller will be written by somebody
  who has not read the comment. Proved: the page's timestamp does not move
  across a full 238-test run, and moves again on the next five-minute job.
  Odoo 19 has no `registry.in_test_mode()`; `config['test_enable']` is the
  marker the framework itself uses.
- **F45** (P4, 2026-09-03) **A `<function>` in a data file with no arguments
  needs `@api.model` on the method.** `odoo/tools/convert.py:193` reads the
  FIRST argument of a `<function model= name=/>` as the records to call it on
  (`record_ids, *args = args`) unless the method carries the model-level
  marker. With neither, the upgrade dies on **"not enough values to unpack
  (expected at least 1, got 0)"** and the traceback names the XML line, not the
  method it could not reach — `pb_tenants/data/pb_feature.xml`'s closing
  `_push_features_here` cost a whole upgrade cycle. `_seed_feature_keys` in
  `pb_tenancy` was written the same way and was fine, because it happened to
  carry the decorator.
- **F46** (P4) **`@api.model` IS NOT INHERITED, and forgetting it on an
  override takes the whole left menu away from everybody.** The browser calls
  `pb.sidebar.item.get_sidebar_data` with no ids; the framework decides how to
  call it by reading the marker off the function it is about to invoke
  (`odoo/service/model.py:86`). `pb_tenancy`'s override of it left the
  decorator off, so every page in the product came back with no navigation and
  a "Something went wrong on our side" dialog, one minute after the master was
  upgraded. **No Python test can see this**: a test calls the method directly
  and both shapes work. The gate is now an assertion on the MARKER
  (`test_t3_03`), for `get_sidebar_data` and `visibility_for` both.
- **F47** (P4) **`useState`'s return value IS the subscription.** A component is
  registered against the reads it makes THROUGH the object `useState` hands
  back; `useState(someReactive)` with the result discarded watches nothing at
  all, silently. Three surfaces had it that way and would each have needed a
  page reload to notice a switch. Second half of the same rule: watch a value
  that only changes when the answer changes. `apply()` replaces the feature
  maps with fresh objects on every read, so a component watching a map would
  repaint once a minute for ever — `features_sig`, one string, is what they
  watch.
- **F48** (P4) **A browser-side reactive cannot update a menu the SERVER drew.**
  The rail is fetched once per page load, so no amount of watching state in the
  browser redraws it. `pb_tenancy` compares the answer it just polled with the
  one it had and fires the rail's own `PB_SIDEBAR:RELOAD` bus event when they
  differ — and deliberately not on the first read, which is the same answer the
  page was painted from a moment ago.
- **F49** (P4) **Python-style adjacent string literals blanked the whole backend
  again — and the gate that catches them exists.** `_t("part one "\n "part
  two")` in `pb_hub/static/src/js/hub_feature_off.js` produced an unparseable
  `web.assets_backend`, an empty page and a completely clean server log. W74 all
  over again, and `pb_hub/tests/test_static.py` has asserted against it since
  the last time. It did not fire because the phase ran its tests scoped to the
  two modules it was WRITING (`/pb_tenants,/pb_tenancy`). **The test scope must
  name every module the phase edits**, which here was six.
- **F50** (P4) **Two presses of "Start rollout" inside ninety seconds are two
  rollouts, and they destroy each other's practice run.** The "already going
  out" blocker is real, but `rollout_start` runs the whole rehearsal before it
  commits, so a second call in that window sees no rollout at all. Both then
  restore and drop `abm-staging` under each other: the first dies with
  "connection already closed", the second with "could not serialize access due
  to concurrent update", and both stop — correctly — with nothing having
  reached a customer. `rollout_start` now takes
  `pg_advisory_xact_lock(hashtext('pb_tenants.rollout_start'))` on entry, so the
  second press waits and then gets the refusal it should have had.
- **F51** (P4) **The rehearsal copy is a shared resource with one name.** Every
  rollout's practice run is `<slug>-staging`, restored and dropped by whoever
  is running. That is fine while exactly one rollout exists (F50 now enforces
  it) and is the reason a paused rollout must be called off rather than left
  lying about: a second one started later would restore the same copy again.
