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
