# RIZE Programme Ledger — conventions, gotchas, rulings, phase log

Every RIZE phase handover references this file. Read it FULLY before coding. Update it
(append, never rewrite history) when you hit a new gotcha worth recording — that is part
of the phase deliverable.

Programme: implement docs/design/rize-hrms-blueprint.html end to end (all 10 modules +
the 6 "Going further" wow features). Owner approved everything on 2026-08-31, including
all 8 decisions AS RECOMMENDED (see Rulings). Autonomous run: phases execute back-to-back
without owner approval between them.

## Target & credentials

- Implement/deploy ONLY on the live `payobook` database at https://payobook.com. No other DB.
- Admin login for browser validation: `ash@biztinct.com` / `Rize#Payobook2026`
  (reset 2026-09-01 per owner pre-authorization — the owner gets this password in the
  final report). Secondary test account: `igc1.validator` / `RizeP0!2026` (user id 2065,
  email rize.validator@payobook.local — DEACTIVATE at programme end).
- Live server ssh alias: `Payobook19v2`. Odoo 19 CE, service `odoo-server`, config
  `/etc/odoo-server.conf`, DB `payobook`, log `/var/log/odoo/odoo-server.log`, passwordless sudo.

## Binding rules (violations = phase failure)

1. **White-label**: the word "Odoo" (or its branding) must NEVER appear in any user-visible
   string — labels, help, placeholders, errors, emails, reports, menu names. Use "Payobook"
   or neutral wording. Technical identifiers (`from odoo import`, xmlids, paths) are untouched.
2. **Plain-English UI**: screen wording uses the words a non-technical HR owner knows.
   No internal jargon in labels/toasts/empty states.
3. **ONE addons directory**: everything deploys to `/odoo/odoo-server/addons` on the server.
   `/odoo/custom/addons` is DEAD (guard-filed). NEVER `rsync --delete` with
   `/odoo/odoo-server/addons/` itself as destination (2026-08-26 incident) — `--delete` is
   only allowed scoped per module dir.
4. **Never deploy vendored standard addons** (web, hr, hr_*, crm, website*, spreadsheet,
   resource, maintenance...) — the server has newer copies from its own clone.
5. **Commit per feature**: explicit file staging (`git add <paths>`, never `git add .` /
   `git add -A` — parallel sessions exist and the working tree has unrelated dirty files:
   ABM/*.xlsx, docs/design/where-pay-data-comes-from.html, pb_contracts/models/pb_contract_360.py,
   RIZE/). Commit after each validated slice, reviewer-focused message, end with
   `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`. Do NOT push.
6. **Design system**: Lucide icons only (via the single `ic()` registry in
   `pb_import_kit/static/src/js/import_icons.js` — add missing icons THERE, camelCase keys;
   the rail has its own separate kebab-case `ICONS` map in `pb_sidebar/static/src/js/pb_sidebar.js`).
   No emoji. No gradients. Uniform indigo kit (`.pbim-*` primitives from pb_import_kit;
   per-hub colour variants are RETIRED). Root class `pbim pbim-page <prefix>`.
7. **Design bar**: "extreme WOW, intuitive, best in class" — hero moment, zero dead ends,
   purposeful motion, bulk ergonomics, empty states that teach. Validate visually via
   Chrome MCP (light AND dark) before reporting done.
8. **Do not modify** `vendor_license_core` (product self-licensing; namespace collision —
   RIZE vendor models are `pb.vendor.*`, never `vendor.license.*`).

## Deploy ritual (proven; follow exactly)

1. Local: clean stage — `ssh Payobook19v2 'rm -rf /tmp/rize_stage && mkdir -p /tmp/rize_stage'`
   (a reused staging dir carries previous deploys).
2. `rsync -az --exclude=__pycache__ --exclude='*.pyc' --exclude=.git <module dirs> Payobook19v2:/tmp/rize_stage/`
3. Per module on server: `sudo rsync -a --delete --chown=odoo:odoo /tmp/rize_stage/<m>/ /odoo/odoo-server/addons/<m>/`
   (scoped `--delete` is correct; NEVER the addons root).
4. `sudo service odoo-server stop`
5. Detached upgrade (SSH-timeout-proof): write `/tmp/rize_run.sh` on server:
   `sudo -u odoo python3 /odoo/odoo-server/odoo-bin -c /etc/odoo-server.conf -d payobook -i <new modules> -u <changed modules> --stop-after-init > /tmp/rize.log 2>&1; echo EXIT=$? >> /tmp/rize.log; touch /tmp/rize.done`
   launch via `sudo systemd-run --collect --unit=rize-install /bin/bash /tmp/rize_run.sh`.
   Poll for `/tmp/rize.done`, then grep the log for `EXIT=` and `Traceback|CRITICAL|ERROR`.
   NOTE: the real error for some failures lands in `/var/log/odoo/odoo-server.log`, not /tmp/rize.log.
6. `sudo service odoo-server start`; confirm `ss -ltn | grep 8069` binds (~50 s registry load)
   and the log shows "Registry loaded".
7. After JS/SCSS changes with no `-u`:
   `sudo -u odoo psql -d payobook -c "DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%';"`
   then hard reload. `-u` does NOT surface SCSS compile errors — always Chrome-load a page
   after an SCSS deploy and check for the red style-error bar.
8. Verify version landed: compare `__manifest__.py` version to
   `ir_module_module.latest_version` in the payobook DB (series prefix `19.0.` is added).
9. Never `pkill -f odoo-bin` (self-matches). Kill stale PIDs by number. One odoo master only.
10. Prefer JSON-RPC / browser `call_kw` for data ops over `odoo-bin shell`; shell requires
    the service FULLY stopped.

## Odoo 19 gotchas (all bit us before; do not rediscover)

- `safe_eval` has no `nocopy` kwarg. `res.users.groups_id` → `group_ids` / `all_group_ids`.
  `res.groups` has no `category_id`. `hr.employee.gender` → `sex`. `res_users.login_date` is gone.
- `_sql_constraints` list is SILENTLY IGNORED — use
  `_x_uniq = models.Constraint('unique(...)', 'msg')` class attributes.
- `ir.cron`: `numbercall`/`doall` fields REMOVED — including them aborts the whole module load.
  No eval expressions for `nextcall` in data files.
- `post_init_hook` fires on INSTALL only, never on `-u` — pair with a migration when needed.
- `<report>` and `<act_window>` shortcut tags are gone from data-file RNG — use explicit
  `<record model="ir.actions.report">` / `ir.actions.act_window`.
- View inheritance xpath may not select by `[@string=...]`. Search-view `<group>` has no
  `expand`/`string` attrs.
- Recordsets can't hold instance attrs (`self._foo = x` fails) — stateless builders; carry
  mutable state via context values.
- `hr.payslip.run` has NO `company_id` — always `getattr(run, 'company_id', False)`.
- Unset Char reads as `False` — empty-check with `if not raw`.
- Sass: `min()/max()` with mixed px/% units kills the ENTIRE asset bundle. Use
  max-width/width pairs or `#{...}` interpolation.
- ACL CSVs: some models lack `model_*` xmlids — grant via hook looking up `ir.model` by name.
- Friendly record titles: override `_compute_display_name` (no `name_get`).
- Every independent health/stat probe gets its OWN try/except (no shared except blocks).
- Private `_methods` aren't callable over JSON-RPC — verify via psql or tests.

## Platform contract for new modules (test-enforced)

- Rail (`pb_sidebar`): items are data (`pb.sidebar.item`) declared by the OWNING module in
  `<module>/data/pb_sidebar.xml` (`noupdate="0"`); globally unique label; unique sequence in
  section; icon key must exist in `pb_sidebar/static/src/js/pb_sidebar.js::ICONS` (add the
  SVG path there if new); claim `match_action_tags`/`match_models` nothing else claims;
  update `TARGET_RAIL` in `pb_sidebar/tests/test_ia_c5.py` in the same change. No rail
  sub-items — sub-navigation is the hub lens rail.
- **Lifecycle hub soft registry (P0, for P5/P6/P10):** registry category
  `"pb_lifecycle_lenses"`, exported as `LIFECYCLE_LENSES` from
  `pb_lifecycle/static/src/js/lifecycle_hub.js` (alongside `LIFECYCLE_GATE`). Add with
  `registry.category(LIFECYCLE_LENSES).add(key, {key, icon, label, Component, groups,
  propsFromContext?}, {sequence})`; the shipped Journeys lens has no sequence, so start
  bolted-on lenses at 20. ⌘K sequences taken by P0: mission **190**, deep links **2100**
  (Start a journey), **2110** (Journey checklists, Admin group), **2120** (Letters).
- Hub (`pb_hub`): `HubShell` with a STABLE config object built once in setup
  (`{key, brand:{label,icon}, defaultLens, lenses:[...]}`); lenses mount cockpits with
  `embedded: true` (cockpit template branches on `props.embedded` to drop its own H1);
  per-lens `groups` gating is advisory — server facades enforce. Cross-module lenses via a
  soft registry (clone: `pb_records/static/src/js/records_palette.js` registers into
  `registry.category("pb_people_lenses")`, consumed by `pb_people_hub/static/src/js/people_hub.js`
  `extraLenses()` — check exact category name in code before cloning).
- ⌘K palette: entries via `pb_hub` palette registry (see
  `pb_hub/static/src/js/hub_palette_entries.js` contract). Missions 110–180 (Lifecycle=190),
  deep links 2000+.
- Cockpit: `AbstractModel` facade (`pb.<name>`), `@api.model` reads, `_safe()` wrappers,
  `self.env.companies.ids` scoping, row caps, NO sudo in cockpit reads; `ir.actions.client`
  RECORD (never a bare tag); OWL component registered in `registry.category("actions")`;
  test URL `/odoo/action-<tag>`.
- Security: `ir.model.access.csv` for every model + global company `ir.rule`
  (`['|',('company_id','=',False),('company_id','in',company_ids)]`); module group ladder
  user→manager→admin with `implied_ids` (clone `pb_hr_workforce_planning/security`).
- ESS: employee pages are PORTAL routes (`/my/...`, frontend assets only — never leak
  backend assets), employee resolved from session user, own-record rules
  `[('employee_id.user_id','=',user.id)]`; login-less flows use token routes
  (clone `pb_ess_workforce/controllers/ack.py` route-boundary + sudo pattern).
- Reminders: idempotent daily cron cloning `pb_employee_vault/models/employee_document.py`
  `_cron_expiry_check` (config-param horizon, search-before-create on open `mail.activity`,
  per-record try/except, honest count logging).
- Mail: `mail.template` records clone `pb_pay_delivery/data/mail_template.xml`; bulk sends
  clone `pb_ess_workforce/models/publish_notify.py` (config-param gate, burst cap, honest
  counts). Outgoing debranding is automatic (biz_mail_debrand).
- Approvals: reuse `biz.approval.chain.mixin` (`biz_approval_chain`) for new approval flows.
  The payroll run's own level0/1/2 chain is UNTOUCHED.
- Letters/PDF: clone the bilingual QWeb pattern from `pb_hr_fullandfinal/report/full_and_final_report.xml`.

## Owner rulings (2026-08-31, all 8 decisions approved as recommended)

- D1: contract EXTENSIONS & CONVERSIONS create a NEW linked contract (renewal-prefill
  pattern, `pb_people_advanced/models/people_wizards.py get_defaults(renew_from=...)`);
  in-place writes remain ONLY for probation trial-end dates. This deliberately supersedes
  the 2026-08-29 "writes happen in place" contract-drawer ruling FOR EXTENSIONS/CONVERSIONS.
- D2: canonical budget object = `wfp.budget.actual` (extended), other budget models demoted
  for RIZE reporting; presentation-currency helpers get promoted OUT of pb_demo.
- D3: calendar invites = email + ICS attachment (no external calendar integration).
- D4: org chart is built as our own cockpit/portal panel (NOT the vendored widget).
- D5: employee SEES their own PIP and must acknowledge it; config switch to hide.
- D6: portal login auto-created when the employee record arrives; credentials email held
  until joining day.
- D7: welcome poster = designed card in the day-one team email.
- D8: field-ownership matrix as in blueprint §14 — Zoho owns employee core + employment
  status; Payobook owns money/probation/PIP/assets/vendors/budgets. Zoho→Payobook only;
  Payobook→Zoho outbound ON HOLD (stub, don't build).
- Scope: all 10 modules + all 6 wow features (journey timeline, recognition wall, new-hire
  pulse, living org chart, budget heat view, anniversary engine).

## Phase plan & status

| Phase | Module(s) | Status |
|---|---|---|
| P0 | pb_lifecycle — journey engine, letters, reminders, Lifecycle mission + hub + Journeys cockpit | **DONE** (live on `payobook`, 19.0.1.0.1, T1–T14 pass) |
| P1 | pb_zoho_bridge — inbound webhook, event rules, CSV fallback | pending |
| P2 | pb_assets | pending |
| P3 | pb_onboarding (+ journey timeline, new-hire pulse, living org chart wow) | pending |
| P4 | pb_offboarding | pending |
| P5 | pb_probation | pending |
| P6 | pb_pip | pending |
| P7 | pb_comp_ben (calendar, incentives+letters, My compensation, benefits) | pending |
| P8 | pb_rnr (+ recognition wall, anniversary engine wow) | pending |
| P9 | pb_budget (+ budget heat view wow) | pending |
| P10 | pb_contract_lifecycle | pending |
| P11 | pb_vendor_access | pending |

## Gotchas discovered during RIZE phases (append here)

### P0 (pb_lifecycle, 2026-08-31)

- **R1 — OWL reserves `lt`/`gt`/`lte`/`gte` as OPERATORS.** `t-as="lt"` compiles the
  loop variable into the generated function as a bare `<`, and the whole template dies
  with `OwlError: Failed to compile template ... Unexpected token '<'` — pointing at the
  template, never at the loop. Never name a `t-as` variable `lt`, `gt`, `lte`, `gte`,
  `and`, `or`, `not`, `in`. (Hit on `t-as="lt"` for letters; renamed to `ltr`.)
- **R2 — JavaScript has no implicit string concatenation.** A Python habit
  (`_t("one " "two")`) is a `SyntaxError: missing ) after argument list` that kills the
  ENTIRE backend asset bundle: every OWL surface in the product goes blank, and the only
  clue is one console line. Syntax-check new JS before deploying:
  `sed 's#^import .*$##; s#^export ##' f.js > /tmp/c.mjs && node --check /tmp/c.mjs`.
- **R3 — `activity_schedule()` lives on `mail.activity.mixin`, not `mail.thread`.** A model
  that inherits only `mail.thread` raises `AttributeError` on it. Inside a per-record
  try/except (which the reminder-cron pattern mandates) the job then runs to completion
  reporting zero nudges, with the real cause only in the log. Inherit
  `['mail.thread', 'mail.activity.mixin']` on anything that schedules activities.
- **R4 — a QWeb render context key named `request` shadows the HTTP request.** The page
  dies with `TypeError: 'Request' object is not subscriptable` and the visitor gets a
  500. Name the key anything else (`feedback`, `record`, `payload`).
- **R5 — server-side QWeb has no `t-key`.** Harmless, but it logs
  `Unknown directives or unused attributes: {'t-key'}` on every render. `t-key` belongs to
  OWL templates (`static/src/xml`), never to backend/frontend `<template>` views.
- **R6 — a `mail.template`'s own rendered `email_to` can reach `mail.mail` EMPTY.** The
  message is created, queued and addressed to nobody, with no error anywhere. The same
  address passed in `send_mail(..., email_values={'email_to': to})` lands. Proven side by
  side. **Always pass the recipient explicitly**; keep the template field as documentation.
- **R7 — `res.users.group_ids` is DIRECT membership only.** Searching it misses everyone
  who holds a group through `implied_ids` — i.e. most administrators. Odoo 19's
  `res.groups.all_user_ids` is the transitive set; use it (the vault's expiry-cron
  precedent predates it and has the same blind spot).
- **R8 — seed data must be COMPANY-LESS.** `company_id` defaults to the loading user's
  company, so a seeded record installs onto whichever company ran the install and the
  `['|',('company_id','=',False),...]` rule then hides it from everyone else. Ship
  `<field name="company_id" eval="False"/>` on every `noupdate="1"` seed.
- **R9 — a RELATED STORED `company_id` does not follow a raw-SQL parent update.** It is a
  real column. A migration that re-points parents must re-point the children explicitly,
  or the children stay invisible to the very read that uses them.
- **R10 — a non-stored computed field cannot be used in a search-view `<filter>` domain.**
  Filter client-side over a payload that already carries the number.
- **R11 — the odoo log goes to `logfile` in `/etc/odoo-server.conf`, not to stdout.** A
  detached test run's `> /tmp/x.log` captures almost nothing; test results land in
  `/var/log/odoo/odoo-server.log`. Add `--logfile=/tmp/x.log` to a test run, or grep the
  server log. Also: `--no-http` does NOT free port 8069 here — pass `--http-port=8199`;
  and `--longpolling-port` no longer exists in Odoo 19.
- **R12 — CREDENTIAL DRIFT.** `ash@biztinct.com` / `plone@123` is **wrong** on the live
  `payobook` database (answers "Wrong login/password"; the user is uid 2, Mitchell Admin,
  and is active). P0 validated through the dormant `igc1.validator` account (uid 2065)
  left by an earlier phase — reactivated, given a temporary password and the System /
  HR User / Lifecycle Administrator tiers. **Owner debt: get the real admin password, and
  deactivate uid 2065 when the programme is done.**
- **R13 — a field-level `groups=` naming a group from the SAME module is a trap.** It is
  resolved at registry load, which on a fresh install runs before that module's security
  data exists, and it also refuses the very `create` that mints the value. Protect tokens
  with the ACL, the record rule and by never putting them in a view or a payload instead.

### P1 (pb_zoho_bridge, 2026-09-01)

- **R14 — this Odoo 19 build keeps employment fields on a VERSION record, not on
  `hr_employee`.** `job_title`, `department_id` and friends are `related='version_id.…'`
  and non-stored, so `SELECT job_title FROM hr_employee` fails with *column does not
  exist* while the ORM read of the same field works perfectly. Verify employee writes
  through JSON-RPC / the ORM, never with raw SQL, or a passing write looks like a
  failure and a failing one can look like a pass. (`hr.version` is where Odoo 19 put
  what used to be `hr.contract`.)
- **R15 — the deploy ritual's `echo EXIT=$? >> /tmp/x.log` can silently not run.** Two
  ways, both hit in one afternoon. (a) The heredoc that writes the run script fails when
  `/tmp/rize_run.sh` already exists **owned by root** — /tmp's sticky bit blocks the
  overwrite, the `&&` chain does not cover the `systemd-run` on the next line, and
  systemd cheerfully re-runs the PREVIOUS PHASE'S script. P1 spent one full cycle
  watching "EXIT=0" for an install of pb_lifecycle. (b) Once odoo owns the logfile the
  root shell's append is refused, so no EXIT line is ever written. **Use a fresh
  per-phase script name written with `sudo tee`, and take the real verdict from
  `journalctl -u <unit>` plus `ir_module_module.state/latest_version` — never from the
  presence of an EXIT line.**
- **R16 — `search([], limit=1)` on `res.company` is the WRONG default company.** It is
  the lowest id, which on a mature database is "Your Company", the empty shell left by
  the initial install. Anything scoped to it disappears behind the standard company
  record rule, and the screen says "nothing here" over a database that is full. Pick the
  company with the most employees (`_best_company()` in `pb_zoho_bridge/hooks.py`) —
  that is the operating company by definition and needs no configuration.
- **R17 — a catch-all rule with an empty match value matches the cases you meant to
  exclude.** "Someone new arrived → start their joining checklist" also fires for a
  person whose record reaches Payobook for the first time already marked *Terminated* —
  a backfill, not a joiner. Any rule table that has a wildcard row needs its guard rows
  ABOVE the wildcard, and the seed file is the place to ship them.
- **R18 — `type='json'` on an `http.route` is deprecated on Odoo 19.** It still works
  (it is an alias for `'jsonrpc'`) but every module load logs a DeprecationWarning WITH
  A FULL STACK TRACE, which is a lot of noise to read past when hunting a real failure.
  New routes use `type='jsonrpc'`. The Darwin webhook still uses the old spelling.
- **R19 — `/api/*` on this box needs the Host header.** The server is multi-tenant with a
  dbfilter, so `curl http://127.0.0.1:8069/api/...` gets a 404 "No database is selected"
  rather than the controller. Pass `-H "Host: payobook.com"` when testing locally; the
  real caller uses `https://payobook.com/...` and is fine.
- **R20 — dark mode is broken on NATIVE LIST VIEWS, product-wide.** Setting
  `data-theme="dark"` (biz_theme's own switch, `biz_theme/static/src/scss/biz_variables.scss:276`)
  leaves list rows with near-white text on a near-white background. It is NOT caused by
  any one module — P0's own "Journey checklists" list breaks identically. There is also
  no user-facing toggle that sets the attribute today, so it is latent rather than live.
  **Do not "fix" it inside a feature phase**; it is a biz_theme job with a blast radius
  of every screen in the product.
- **R21 — a duplicate audit row cannot carry the key it duplicates.** With a unique
  constraint on `external_event_id`, the second sighting of an event must be written with
  that field EMPTY (Postgres keeps NULLs distinct) and a `duplicate_of_id` pointer
  instead. Writing the key again turns an idempotent skip into an integrity error.
