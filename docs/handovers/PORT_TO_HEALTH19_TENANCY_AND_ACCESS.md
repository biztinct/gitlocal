# Porting the tenant platform AND the Access home from Payobook to health19

Written 2026-09-04 by Fable in the Payobook repo (`/Users/adity/Documents/GitHub/gitlocal`, branch
`19.1`) for a NEW Fable session opened in `/Users/adity/Documents/GitHub/health19` (branch `19.0`).
Owner's ask: "the SaaS functionality of creating and managing tenants … and the implementation of
the access management module — the new way we are doing roles / groups with a better UI."

**Read this whole file before doing anything. Then read, in the Payobook repo:**
`docs/handovers/FLEET_CLOSEOUT.md` → `FLEET_PROGRAM.md` (rails R1–R8, ledger F1–F68) →
`docs/SAAS_RUNBOOK.md` → `docs/handovers/ACCESS_CLOSEOUT.md` → `ACCESS_PROGRAM.md` (rulings,
ledger A–F). Copies of all of these sit next to this file in `health19/docs/handovers/from_payobook/`.

---

## 0. The one-paragraph verdict

Both things the owner wants exist, work, and are live on Payobook (`payobook.com`): a tenant
platform (`pb_tenants` on the master + `pb_tenancy` on every tenant) and an Access home
(`biz_access` generic core + `pb_vendor_access` Payobook overlay). **They cannot be copied into
health19 as they are.** Their *logic* is product-neutral, but their *manifests and UI* lean on
Payobook's UI kit (four modules that in turn declare the whole payroll stack as dependencies), and
health19 already has its own left rail, its own theme and icon set, and a third-party access app
(Cybrosys `access_roles`) that four health modules depend on. The clean route is the one Payobook
already used once for access: **generic cores + a thin product overlay**. Part of that split is
best done in the Payobook repo first (so Payobook and health19 share one core rather than two
forks); the rest is health19 work. This document lays out both halves and says which is which.

---

## 1. What exists in Payobook today (verified 2026-09-04)

| Module | Where | Size | Version | What it is |
|---|---|---|---|---|
| `pb_tenants` | master only | 2.3 MB, ~60 files | 19.0.2.1.0 | The cockpit: provisioning (clone golden template → configure → admin → HTTPS → verify), backups (nightly/manual/final), restore-to-staging, custom domains + per-host certs, fleet health, **In step with master** (version-aware install + update, skipped check), releases, **rollout waves** (rehearsal → template → canary → early → everyone, night windows per tz, health gate, pause/retry/skip/abort), **alerts** by email + digest, capacity gauge + provisioning guard, public **status page** writer, **feature switches** matrix, **plans / trial / paused / invoices** (PDF, email, mark paid), **Open as support** with a trail |
| `pb_tenancy` | master + template + every tenant | 568 KB | 19.0.1.4.0 | The tenant-side agent: reads pushed parameters; notice bar (before/during updates), release toast, **What's new**, features (fail-open), **paused door**, seat limit on `hr.employee.create`, trial bar, **Plan & usage** card, **Support access** page + one-time-link login + rose support bar |
| `biz_access` | every DB | 552 KB | 19.0.1.1.0 | **Access, in plain English**: roles as bundles of abilities (each ability = curated groups), Roles / People / Screens / Hand-overs lenses, role builder with live rail preview, "See it as…", delegation with auto-revert + audit, tenant-admin rails (debug blocked server-side, Settings hub split, forbidden-group tripwire) |
| `pb_vendor_access` | every DB | 376 KB | 19.0.1.7.0 | The Payobook overlay: 35 abilities → 23 roles seeded (`hooks.py`), the **Tenant administrator** role (`role_tenant_administrator`), vendors register (unrelated — leave behind) |

Everything above is committed and pushed on `19.1` (latest `4cac83d6`). Test counts at the last
runs: 454–517 green across the touched modules. Screenshots per phase: `docs/handovers/fleet_p*_shots/`,
`access_p*_shots/`.

### 1.1 Declared dependencies vs what the code really uses

This is the whole problem, so it is a table.

| Module | Manifest `depends` | What the code actually imports/inherits from outside itself |
|---|---|---|
| `pb_tenants` | web, pb_import_kit, pb_sidebar, pb_hub, pb_tenancy | JS: `@pb_import_kit/js/import_icons` (`ic()`), `@pb_hub/js/hub_nav` (`HubBackChip`, `hubBack`); xmlids `pb_vendor_access.role_tenant_administrator`, `biz_access.group_access_manager`, `pb_dashboard.action_pb_dashboard`; SQL on tenants: `hr_employee`, `hr_payslip` (meters + health probe) |
| `pb_tenancy` | web, pb_import_kit, pb_hub, pb_settings, pb_sidebar, **hr** | JS: `import_icons`, `hub_nav`, `@pb_settings/js/settings_hub` (soft registry `pb_settings_category`); Python `_inherit`: `hr.employee`, `ir.http`, `res.users`, `pb.sidebar.item`, `pb.sidebar.section`; template `t-inherit="web.WebClient"` (after `//NavBar`); data `pb_sidebar_features.xml` (feature keys on 5 Payobook rail items) |
| `biz_access` | base, hr, mail, pb_import_kit, pb_hub, pb_settings, pb_sidebar | JS: `import_icons`, `hub_nav`, `settings_hub`; Python `_inherit`: `pb.sidebar.item` (the Screens lens reads/writes the rail's gates) |
| `pb_import_kit` | web, **pb_theme** (→ hr, hr_contract) | tokens SCSS + `ic()` registry (102 Lucide glyphs) + shared kit components |
| `pb_hub` | web, pb_import_kit, **pb_wf_kit** | `hub_nav.js` (back chip), `hub_shell.js` (lens shell + feature gate), `hub_features.js`, `hub_feature_off.js`, palette service |
| `pb_sidebar` | web, biz_theme, **pb_hr_payroll_base, hr_attendance** | the rail: `pb.sidebar.section/item` with `groups_id`, `restricted`, `feature_key`; the ONE visibility rule `_state_for`; `get_sidebar_data`, `visibility_for` |
| `pb_settings` | web, pb_hub, pb_import_kit, **om_hr_payroll, pb_hr_payroll_base**, pb_sidebar, biz_audit_trail | the Settings hub (categories + cards, soft registry, `resolve_gates` with platform-only refusal + feature gate) |

Transitive install order if copied verbatim: `biz_theme → pb_theme → pb_import_kit → report_xlsx →
om_hr_payroll → pb_hr_payroll_base → pb_sidebar → pb_wf_kit → pb_hub → biz_audit_trail →
pb_settings → pb_tenancy → pb_tenants` — i.e. the payroll engine would be installed in a
healthcare product. **Not acceptable.** The bold dependencies are manifest-only (data xmlids,
SCSS variables, one context service); the code paths the tenant/access modules use do not need
them.

### 1.2 Product-specific couplings inside the two tenant modules (counted)

| Coupling | `pb_tenants` | `pb_tenancy` | What it must become |
|---|---|---|---|
| The word "Payobook" in user-visible strings | 113 | 95 | a product-name parameter / `_t` with a brand token (Payobook's white-label rule applies to health19 too: never "Odoo") |
| `payobook.com` | 10 | 2 | already mostly `pb_tenants.base_domain`; finish the job |
| `/bizapp` backend prefix | 1 | 17 | `pb_tenants.backend_prefix` exists on the apex side; the tenant side must read it too (health19 also runs `biz_deroute` — check its prefix) |
| never-list `pb_demo`, `pb_demo_portal`, `pb_website`, `pb_tenants`, prefix `pb_platform` | yes | — | a parameter + overlay hook (health19's list will be `health_*demo*`, the cockpit itself, the marketing site) |
| `pb_vendor_access.role_tenant_administrator` (rails), `biz_access.group_access_manager` (customer-side page gate) | 4 | 1 | parameters resolved by xmlid, provided by the overlay |
| `pb_dashboard.action_pb_dashboard` (tenant home action) | 1 | — | parameter |
| Meters: `hr_employee` active count, `hr_payslip` produced count | 4 SQL | 3 SQL + `hr.employee.create` override | a **meter registry** (key, label, table guard, SQL) + a **seat-limit model** parameter; health19 has `hr` (via `health_base`) so a staff meter still works, but the sold unit is likely patients/encounters |
| Feature catalogue seed (10 Payobook parts: Insights, Workforce, Lifecycle, …) | data | rail keys | overlay data |
| Plan seeds (Starter/Growth/Enterprise, VND) | data | — | overlay data |
| Status page components ("Payroll processing", "Customer sites"…) | code | — | parameter list |
| Invoice PDF branding | QWeb | — | brand tokens from the overlay |
| Settings hub category "About Payobook" | — | `settings_hub` registry | the health Settings surface (see §2) |

Parameters already in place (53 of them, all `pb_tenants.*` / `pb_tenancy.*`): base_domain,
template_db, backup_root, public_ip, backend_prefix, break_glass_login, tenant_admin_rails*,
alert_*, billing_*, invoice_*, capacity_reserve_mb, tenant_cost_mb, health_ignore, status_dir,
status_tz, auto_suspend, suspend_after_days, rollout_start, template_active_crons; tenant-side
access, access_text, features, invoices, notice, paused_page, plan_name, pushed_at,
recovery_login, release*, seat_limit, support_allowed, support_gone_page, trial_ends.

---

## 2. What health19 has that collides (verified 2026-09-04)

- **127 custom modules under `health19/addons/`** (health_*, biz_*, account_* OCA, access_roles…).
  No `biz_theme`, `pb_import_kit`, `pb_hub`, `pb_sidebar`, `pb_settings`.
- **Its own left rail**: `health_cms_sidebar` (`cms.sidebar.section/item`: name, section, parent,
  sequence, `icon` = **FontAwesome class**, action_xmlid/tag, **`role_ids` M2M → `access.role`**,
  `effective_role_ids`, match_* fields). Two rails on one screen is not an option: the port must
  **adapt to this rail**, not install `pb_sidebar`.
- **Cybrosys `access_roles` is load-bearing**: `health_base`, `health_cms_sidebar`,
  `health_field_requirements`, `health_user_admin` depend on it; 69 code references to
  `access.role`, 8 to `access_roles.access_role_group_administrator`, 6 to `role.management`.
  Payobook retired the same app in ACCESS P6 (`docs/handovers/ACCESS_P6_GENERIC_RETIRE.md` — the
  uninstall + migration recipe, and the ledger entry on why `role-apply` hard-SETs groups and wipes
  manual grants). health19's migration is bigger because the rail's gates ARE `access.role` rows.
- **Its own theme and icons**: `health_theme` (Việt Úc Clinic, the `vu_*` form engine — the same
  lineage as Payobook's `biz_theme` form skin, see the `vu-form-engine-decision` memory), FontAwesome
  in the rail (`fa fa-circle-o`). The kit's Lucide `ic()` registry would be new there.
- **Branding**: `biz_debranding` ("Business Debranding (Viet Uc Care)") with a `brand_name`
  field; `biz_deroute` present (check its prefix — Payobook's is `/bizapp`).
- **`hr` IS installed** (`health_base` depends on it) — the seat-limit override and a staff meter
  survive; but the product's unit of sale is more likely patients / encounters / invoices
  (`health_emr`, `health_invoicing`). Meters must be pluggable (§1.2).
- **Servers**: `~/.ssh/config` has `Health18` (13.239.227.131), `VietUcUAT` (52.64.215.106),
  `TaupoHealth` (52.63.217.105). Domain seen in docs: `vafhs.com`. Which box becomes the SaaS
  apex, what its DB is called, whether it is single-DB today, its RAM, its nginx layout, its
  certbot state, its mail server — **all unverified; the health session verifies them first**
  (checklist in §5).
- health19 has a memory-relevant history: `access_roles` reload-storm fix ports (memory
  `access-roles-f4-fix`: 007a93e6 + 0a888907 on health19, not pushed; VAFHS deployment "still
  needs the ops purge").

---

## 3. Strategy: generic cores + product overlays (recommended)

Precedent: ACCESS P6 split `biz_access` out of `pb_vendor_access` precisely so "the owner can reuse
it in another left-rail application" (ACCESS ruling 3). Finish that idea for the kit and the tenant
modules, then health19 consumes the cores verbatim and writes overlays.

```
                      generic (shared, copied verbatim into health19/addons)
  ┌──────────────┐   ┌────────────────┐   ┌──────────────┐   ┌──────────────┐
  │   biz_kit    │◄──│  biz_access    │   │ biz_tenancy  │◄──│ biz_tenants  │
  │ tokens, ic() │   │ roles/lenses   │   │ tenant agent │   │ the cockpit  │
  │ back chip,   │   │ rail ADAPTER   │   │ meters, door │   │ (apex only)  │
  │ features svc,│   │ interface      │   │ banner, …    │   │              │
  │ settings reg │   └───────┬────────┘   └──────┬───────┘   └──────┬───────┘
  └──────────────┘           │ implemented by    │ configured by     │
        Payobook overlay:  pb_sidebar adapter · pb_vendor_access · pb_tenants_payobook (thin)
        health19 overlay:  health_access (cms_sidebar adapter + clinic role catalogue) · health_tenancy
```

### 3.1 `biz_kit` (new, ~small) — depends `['web']`
Extracted, not rewritten: `pb_import_kit/static/src/scss/import_tokens.scss` (tokens; the
Payobook indigo becomes a default the overlay overrides — health19 has its own palette,
`Healthcare_Colour_Palette.pdf`), `import_icons.js` (`ic()`, 102 Lucide glyphs), `pb_hub`'s
`hub_nav.js` (`openHub`, `hubBack`, `HubBackChip`), `hub_features.js` (features service +
`featureGate`), `hub_feature_off.js` (the "not switched on for your company" page), and
`pb_settings`' **soft category registry + `resolve_gates`** (server model + the hub component, so a
product without a Settings hub gets one). Payobook's `pb_import_kit`/`pb_hub`/`pb_settings` then
depend on `biz_kit` and re-export (or the pb_* modules keep their files and the biz_* cores import
from `@biz_kit/...` — the second is less churn; pick it).

### 3.2 `biz_access` — replace the hard `pb.sidebar.item` inherit with a rail adapter
Today `biz_access/models/pb_sidebar_item_ext.py` inherits `pb.sidebar.item` and the Screens lens
reads/writes `groups_id`. Define `biz.access.rail` (AbstractModel) with `entries()`,
`visibility_for(user)`, `set_gate(entry_id, role_ids)`, `preview(user_or_roles)`; ship the
`pb_sidebar` implementation inside Payobook's overlay and a `health_cms_sidebar` implementation
in `health_access` (its gate is `role_ids` → the adapter maps role bundles ↔ `cms.sidebar.item`
role links, and `effective_role_ids` becomes a compute over bundles). Drop `hr` from
`biz_access`'s depends unless a real `hr.employee` read remains (check `pb_access_facade.py`).

### 3.3 `biz_tenancy` + `biz_tenants` — parameterise the couplings in §1.2
- Product name: one `_brand()` helper reading `biz_tenants.brand` (default from the overlay), used
  by every string that says "Payobook" (208 occurrences — mechanical, but each one must still
  read well: "Payobook will be updated tonight" → "{brand} will be updated tonight").
- Meter registry: `biz.tenants.meter` (key, label, table_guard, sql, unit) seeded by the overlay;
  the billing meter, the health probe, the seat count and the plan `pricing` structures all read it.
  Seat-limit hook: parameter `biz_tenancy.seat_model` (default `hr.employee`) + a generic
  `create` guard registered on that model at load (or an overlay that inherits the model — simpler
  and explicit; prefer the overlay).
- Rails: `tenant_admin_role_xmlid`, `access_manager_group_xmlid`, `tenant_home_action_xmlid`,
  never-list + prefix, status components list, plan seeds, feature catalogue — all overlay data
  or parameters; the cores seed nothing product-specific.
- Backend prefix on the tenant side: read `biz_tenants.backend_prefix` (pushed like the rest).
- The Settings category "About {brand}" registers through `biz_kit`'s registry; the overlay says
  where it lands.

### 3.4 Why not "copy and trim" inside health19 instead
It works once and forks forever: every fix Payobook makes to rollouts, alerts, billing or the
Access home would have to be hand-ported. The owner runs both products; one core, two overlays is
the only shape that stays honest.

---

## 4. Work plan

### Half A — in the Payobook repo (`gitlocal`), BEFORE health19 starts consuming
Fable designs / Opus builds, same cycle as FLEET. Three phases, each deployed and validated on
Payobook exactly as before (rails R1–R8, tests over every touched module, Chrome validation,
ledger). Nothing user-visible changes on Payobook when it is done — that is the acceptance test.

| Phase | Scope | Proof |
|---|---|---|
| **G1 biz_kit** | extract tokens/icons/back-chip/features/settings-registry into `biz_kit`; `biz_access`, `pb_tenancy`, `pb_tenants` import from it; pb_* kit modules depend on it | Payobook screens pixel-identical; imports resolve; tests green |
| **G2 biz_access rail adapter** | `biz.access.rail` + the `pb_sidebar` implementation moved into the Payobook overlay; `hr` dependency dropped if unused | Roles/People/Screens lenses unchanged; the Access-home passport test still passes |
| **G3 biz_tenancy / biz_tenants** | rename + parameterise §1.2 (brand, domain, prefix, never-list, xmlids, meters, seeds, status components, invoice brand); `pb_tenants_payobook` overlay holds the Payobook data | Fleet cockpit + tenant screens unchanged on payobook/abm; `sync_report`, a dry-run rollout, an alert cron run, a billing preview all identical to before |

Renaming modules in place on live databases needs a migration (Odoo treats a renamed module as
uninstall + install): keep the technical names `pb_tenants`/`pb_tenancy` if the migration cost is
too high and only make them generic *inside* — the name is not the coupling. Decide in G3's design.

### Half B — in health19 (the new session)
| Phase | Scope |
|---|---|
| **H0 Verify** | the §5 checklist against the chosen server; write `health19/docs/SAAS_RUNBOOK.md` from Payobook's, with health19's values |
| **H1 Kit + Access core** | copy `biz_kit`, `biz_access` (+ `biz_audit_trail` if `biz_access` still needs it) into `health19/addons/`; palette overlay (health tokens); install on a scratch copy of the health DB first |
| **H2 `health_access` overlay + retire `access_roles`** | clinic role catalogue (abilities → curated `health_*` groups; the ACCESS P1 handover is the recipe), the `cms.sidebar` rail adapter, migrate each `access.role` → a role bundle and each rail `role_ids` gate → role links, port `health_user_admin`'s user-admin flows onto the People lens or keep it (health decision), then uninstall `access_roles` per ACCESS P6 (its `role-apply` wipes manual groups — read that ledger entry before touching users). Four health manifests drop the dependency. |
| **H3 SaaS plumbing on the server** | golden template DB from the health module set (minus demo/site/cockpit), `dbfilter = ^%d$`, `list_db = False`, nginx wildcard block + `/web/database` 404, wildcard DNS + per-host HTTP-01 certs, the three scripts (`pb-domain-attach/detach`, `pb-tenant-cert` → renamed) + sudoers, backups dir, `/var/www/<brand>-status` + nginx `/status`, mail `default.from`, RAM check (Payobook's box is 1.9 GB and holds ~11 more customers at 60 MB each — measure, don't assume) |
| **H4 `health_tenancy` overlay + cockpit** | brand, domain, prefix, never-list, tenant-admin role xmlid (from H2), home action, meters (staff / patients / encounters / invoices — the owner picks the sold unit), plan seeds (VND, placeholders), feature catalogue over the health rail (which `cms.sidebar` items / hubs are switchable), status components; install `biz_tenants` on the apex; provision one **pilot tenant** from the template |
| **H5 Validation** | every FLEET live check (L-lists in `FLEET_P*` handovers) re-run on the pilot: drift/update, release + rollout waves with rehearsal, notices, alerts email, capacity, status page, features, plan/invoice/paused door on staging, support access with trail. Chrome-driven. |

---

## 5. Facts the health session must verify before H1 (do not assume)

1. Which server is the apex (`Health18` / `VietUcUAT` / `TaupoHealth`), its RAM, cores, disk,
   `workers`, `addons_path` (ONE directory rule from Payobook's CLAUDE.md — check for shadowing),
   `dbfilter`/`db_name`, `list_db`, `proxy_mode`, log path, Odoo git revision (Payobook is 19 at
   `db2cd8c1`; the request seams in `FLEET_PROGRAM.md` are pinned to that).
2. Database names on the box; whether the product is single-DB today; filestore path.
3. Domain (`vafhs.com`?), registrar and whether a wildcard A record + wildcard/auto-renewing
   certs are possible (Payobook's DNS-01 wildcard does NOT auto-renew — per-host HTTP-01 certs do;
   ledger + runbook).
4. nginx vhosts, existing `location` blocks, whether `/web/database/` is already 404'd.
5. Outgoing mail server + `mail.default.from` (Payobook's alerts died on this — F5).
6. `biz_deroute` prefix on health19; whether `health_theme` hides `NavBar` (the banner mounts after
   `//NavBar` — F18) and whether two modules already `position="replace"` `//ActionContainer`.
7. Which `access.role` rows exist, which users hold them, which rail items are gated by them, what
   `health_user_admin` does that the People lens does not.
8. What health19's tests look like and how to run them beside a live service (Payobook needs
   `--http-port=8199 --gevent-port=8198 --max-cron-threads=0 --db-filter=.*` — F13).

---

## 6. Rules that carry over unchanged

- **Rails R1–R8** (FLEET_PROGRAM.md): never a silent write to a customer DB; never-list re-checked
  on the literal list; master → template → tenants; rehearse on a restore; ORM through
  `_tenant_env` for cross-DB writes; pure decisions with tests; plain English, never "Odoo";
  template crons disabled + recorded.
- **White-label**: the product name in strings is the overlay's brand; "Odoo" never appears
  anywhere a user reads (both products already run debranding).
- **Design bar** (verbatim in every handover): "extreme WOW, intuitive, out-of-this-world
  experience, best in class" — hero moment, zero dead-ends, plain language, motion with purpose,
  keyboard/bulk ergonomics; Lucide via `ic()`, no emoji, no gradients; Chrome validation mandatory.
- **Commit per feature, explicit staging, never `git add .`, push only when the owner says.**
- **Ledger practice**: append gotchas with numbers (F-, A–F); the health port starts its own
  (`H-`) and cites Payobook's by number.
- **Payobook gotchas that WILL bite again**: F13 (tests 404 without `--db-filter=.*`), F14
  (visible-tab poll), F15 (`t-as="lt"`), F17/F32 (datetime-local vs UTC), F19 (restart after asset
   SQL), F21 (`type='jsonrpc'`), F23/F24 (False vs None; `get_param` lies about empty), F25 (log
   ignore list), F28/F29 (tests must stand down the real fleet; patch cursor commit on the instance),
   the P4 rule "run tests over EVERY touched module", the P5 findings (a helper of the same name
   silently replacing an earlier one; a fail-open guard opening the paused door; cache invisibility
   for writes from outside the running server), and the ACCESS ledger on `access_roles`.

---

## 7. Exact source paths (Payobook repo, branch `19.1` at `4cac83d6` or later)

```
/Users/adity/Documents/GitHub/gitlocal/pb_tenants/          the cockpit (apex)
/Users/adity/Documents/GitHub/gitlocal/pb_tenancy/          the tenant agent
/Users/adity/Documents/GitHub/gitlocal/biz_access/          the Access home core
/Users/adity/Documents/GitHub/gitlocal/pb_vendor_access/    the Payobook overlay (role catalogue in hooks.py — the shape to copy, not the content)
/Users/adity/Documents/GitHub/gitlocal/pb_import_kit/       tokens + ic()            ┐
/Users/adity/Documents/GitHub/gitlocal/pb_hub/              back chip, features, off-page  ├ become biz_kit (G1)
/Users/adity/Documents/GitHub/gitlocal/pb_settings/         settings registry + gates ┘
/Users/adity/Documents/GitHub/gitlocal/pb_sidebar/          the rail (do NOT port; adapter only)
/Users/adity/Documents/GitHub/gitlocal/pb_tenants/tools/    pb-domain-attach, pb-domain-detach, pb-tenant-cert (server scripts)
/Users/adity/Documents/GitHub/gitlocal/docs/SAAS_RUNBOOK.md, SAAS_RESIZE_RUNBOOK.md, SAAS_RELEASE_STRATEGY.html
/Users/adity/Documents/GitHub/gitlocal/docs/handovers/FLEET_*.md, ACCESS_*.md, fleet_p*_shots/, access_p*_shots/
```

---

## 8. Decisions only the owner can make (ask ONCE, at the start of the health session)

1. **Run Half A in the Payobook repo first** (recommended; ~3 phases) — or copy-and-trim inside
   health19 and accept two forks?
2. Which server is the health SaaS apex, and the domain for tenants (`<slug>.vafhs.com`?).
3. The sold unit for plans (staff / patients / encounters / invoices) and the three plan seeds.
4. Alert recipients; the brand name as it should read in a sentence ("Viet Uc Care"?).
5. Retire `access_roles` on health19 in H2, or keep it read-only beside `biz_access` for a while?
6. The never-list for health tenants (demo modules, marketing site, the cockpit).
7. Which health rail items / hubs are switchable features.
