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
- **D9 (owner, 2026-09-01): do NOT clean up demo/test data created during phase testing —
  payobook.com is a demo database.** Every handover's "clean up test records" test case is
  hereby waived: leave test employees/journeys/records in place (tidy is nice, deletion is
  not required). Test users/passwords still get LISTED in reports for the final summary,
  and mails must still go to safe @example.com/test addresses.

## Phase plan & status

| Phase | Module(s) | Status |
|---|---|---|
| P0 | pb_lifecycle — journey engine, letters, reminders, Lifecycle mission + hub + Journeys cockpit | **DONE** (live on `payobook`, 19.0.1.0.1, T1–T14 pass) |
| P1 | pb_zoho_bridge — inbound webhook, event rules, CSV fallback | **DONE** (live on `payobook`, 19.0.1.0.0) |
| P2 | pb_assets — register, handovers, requests, People-hub Assets lens, `/my/assets` | **DONE** (live on `payobook`, 19.0.1.0.0, T1–T13 pass) |
| P3 | pb_onboarding (+ journey timeline, new-hire pulse, living org chart wow) | **DONE** (live on `payobook`, 19.0.1.0.0, T1–T16 pass) |
| P4 | pb_offboarding — resignation, clearances, handover, the settlement gate, Exits lens, /my/resignation | **DONE** (live on `payobook`, 19.0.1.0.0, T1-T16 pass) |
| P5 | pb_probation — policy, `pb_probation_state`, the review machine, the training gate, Probation lens, `/my/journey` card | **DONE** (live on `payobook`, 19.0.1.0.0, T1–T16 pass) |
| P6 | pb_pip — coaching, the plan, the decision, `/my/growth`, its OWN group ladder | **DONE** (live on `payobook`, 19.0.1.0.0, T1–T15 pass) |
| P7 | pb_comp_ben (calendar, incentives+letters, My compensation, benefits) | **DONE** (live on `payobook`, 19.0.1.0.0, T1–T13 pass; one additive edit to pb_payhub — assets only, no version bump) |
| P8 | pb_rnr (+ recognition wall, anniversary engine wow) | **DONE** (live on `payobook`, 19.0.1.0.0, T1–T12 pass; one additive JS edit to pb_home_hub — a soft lens registry, now test-enforced — and one icon added to pb_import_kit) |
| P9 | pb_budget (+ budget heat view wow) | **DONE** (live on `payobook`, 19.0.1.0.0, T1–T11 pass, T12 waived by D9; two additive JS edits — a soft lens registry on pb_insights_hub, now test-enforced, and one icon in pb_import_kit) |
| P10 | pb_contract_lifecycle | **DONE** (live on `payobook`, 19.0.1.0.0, T1–T13 pass, T14 waived by D9; one fallback-safe edit to `pb_hr_payroll_analytics`, its own commit) |
| P11 | pb_vendor_access — vendor register + agreements, the role catalogue, hand-overs that auto-revert, two Settings panels | **DONE** (live on `payobook`, 19.0.1.0.0, T1–T13 pass, T14 = memberships reverted / records left per D9; one additive JS edit to `pb_settings` — a soft CATEGORY registry, now test-enforced) |

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

### P2 (pb_assets, 2026-09-01)

- **R22 — a PARTIAL unique index needs an explicit flush, or a legitimate handover is
  refused.** `pb_asset_assignment` carries
  `CREATE UNIQUE INDEX ... (asset_id) WHERE state = 'open'` (a plain unique constraint
  would forbid the SECOND completed loan of the same laptop, which is the history the
  table exists to keep). A transfer closes one row and opens the next in one breath —
  and Odoo 19 leaves the `write` in the towrite buffer while the immediately following
  `create` flushes its own INSERT first, so the index sees two open rows and the user
  gets a raw Postgres message on a perfectly legal action. `self.env.flush_all()` at the
  end of the CLOSING method makes the order a property of that method rather than of
  every caller's luck.
- **R23 — `currency._convert()` with no rate returns the amount UNCHANGED.** It does not
  raise and it does not answer zero: 32,000,000 ₫ comes back as "32,000,000 USD", which
  is not a rounding error but a lie by a factor of twenty-six thousand. On this database
  every currency reports `rate = 1.0` for the operating company, so EVERY conversion is
  silently a no-op. Test for it before showing the number: two DIFFERENT currencies
  reported at the SAME rate means nobody has told the database what a dong is worth, and
  the honest answer is to show nothing.
- **R24 — `read_group` is gone on Odoo 19.** `_read_group(domain, groupby, aggregates)`
  replaces it and returns a list of TUPLES whose first element is a recordset, not dicts
  with `('id', 'name')` pairs. Keep a `mapped()` fallback around it.
- **R25 — ordering a Selection-backed list by `kind` sorts alphabetically, not by
  importance.** `_order = 'kind, sequence, name'` put every DIGITAL category above every
  physical one, so the "Add an item" dialog defaulted to *Email account* on a register
  that is mostly laptops. Let the `sequence` column carry both the grouping and the
  priority, and never let a dialog's default fall out of an incidental sort.
- **R26 — equal-specificity CSS is decided by SOURCE ORDER, and a kit file's later
  generic rule wins.** `.ast-country { width: 190px }` in the filters block was overruled
  by `.ast-in { width: 100% }` two hundred lines below it; the country picker ate its own
  row and pushed the filter chips down. Qualify the narrow rule (`.ast-in.ast-country`)
  rather than moving blocks around.
- **R27 — a country list has TWO jobs and needs two lists.** The FILTER bar must offer
  only countries the data actually uses (a filter that matches nothing is a broken
  promise), but the ADD dialog must offer every country or the register can never grow
  past the office it started in. Ship `countries` and `countries_all` separately, and
  default the dialog to `env.company.country_id` — an alphabetical world list defaults a
  Vietnamese user to Afghanistan.
- **R28 — fold accents before slugging a filename, never strip them.** A plain
  `[^A-Za-z0-9]` pass turns "Bùi Hữu Dũng" into `B_i_H_u_D_ng`, which nobody can read and
  which collides with every other name of the same shape. NFKD + drop combining marks,
  then hand-map `đ`/`Đ` (Vietnamese `đ` carries no combining mark, so NFKD leaves it).
  Same finding as the MAPFIX component-code fix — it is worth doing once, centrally.
- **R29 — the ESS demo logins are PASSWORDLESS by design (`pb_demo`, C18.14).** They are
  not broken accounts; an admin sets a password at demo time. P2's portal tests set
  `RizeP2!2026` on `ess1.demo@payobook.com` (employee 10080) and
  `ess2.demo@payobook.com` (employee 9884). **Owner debt: clear those passwords at
  programme end**, exactly as with uid 2065.
- **R30 — a journey-opening extension must be idempotent, because it is reached twice.**
  `pb.journey.case.action_open()` and the connected system's `_after_offboard` BOTH lead
  to the same case, since `pb.zoho.pipeline._open_case()` already calls `action_open()`
  itself. The append helper de-duplicates on the FINISHED task name ("Return: VN-LT-00001
  MacBook"), which is the only identity such a task has. Anything P3–P11 bolts onto a
  journey hook needs the same treatment.

### P3 (pb_onboarding, 2026-09-01)

- **R31 — a column a later phase adds to `pb.journey.template.step` does NOT
  reach `pb.journey.task`.** P0 builds its task values from a FIXED dict, and
  that is the right shape for it — a task is the case's own copy of a step, so
  the copy is deliberate and explicit. But it means P3's `automation_key` was
  dropped on the floor for all nine steps of the first live arrival, and the
  only symptom was steps that never ran themselves: no laptop request, and
  three day-one emails waiting forever for a human. There is no error and
  nothing in the log. **Extend `_generate_tasks()`, copy from `step_id` right
  after `super()`, and only where the task's own value is empty** so a value
  set by hand on a running case survives. Every phase from P4 on that adds a
  step column has to do the same.
- **R32 — the kit's `.pbim-stats` is a grid with NO COLUMNS.** That is on
  purpose (each cockpit knows how many numbers it has), but a lens that does
  not declare `grid-template-columns` opens on a stack of full-width tiles and
  looks broken. Copy `.lcj-kpis` (`pb_lifecycle/static/src/scss/journeys.scss:33`):
  five columns, three under 1180px, two under 700px.
- **R33 — `.pbim-badge` capitalises every word.** Correct for a status word
  ("Approved"), wrong for a sentence: the buddy dialog's eligibility reasons
  rendered as *"Only 0 Month(S) Here — A Buddy Needs At Least 6."* Any badge
  that carries a SENTENCE has to set `text-transform: none` itself.
- **R34 — a sentence split across several `t-esc` nodes loses the whitespace
  between them.** OWL collapses the newline, and the empty state read
  "There are2 new joiners on this board". Build the whole sentence in ONE
  expression rather than interleaving text nodes and `t-esc`.
- **R35 — an XML comment ruled with hyphens is not well-formed XML.**
  `<!-- ---------- before they arrive ---------- -->` in a data file is a parse
  error at module load that takes the entire file with it. (W22 again, this
  time in a `data/` file rather than an OWL template — the rule is the same
  everywhere: rule section comments with `=`, never `-`.)
- **R36 — the live server's clock is a DAY BEHIND the agent's local date.** A
  test that writes `date.today()` from the laptop into a record the cron finds
  with `due_date <= today` writes tomorrow, the cron finds nothing, and the
  feature looks broken when it is fine. Take "today" from the server (or write
  a date safely in the past) whenever a date-driven job is being tested.
- **R37 — `mail.mail.unlink()` over JSON-RPC cascades into
  `mail.message.unlink()` and is REFUSED, even for uid 2.** To take test
  traffic out of the outgoing queue without an SMTP send, write
  `state = 'cancel'` on the messages instead of deleting them. (This database
  has a live `smtp.gmail.com` server and an hourly queue cron, so anything
  left `outgoing` really does go out.)
- **R38 — `pb.asset.country_id` is NOT NULL and there is no `available`
  state.** The states are `spare / assigned / repair / to_scrap / scrapped /
  deactivated`. Creating a test asset without a country is a raw Postgres
  not-null violation, and writing `available` is a plain ValueError.
- **R39 — the PORTAL surface has no dark mode at all.** Neither biz_theme's
  `data-theme="dark"` attribute nor an emulated `prefers-color-scheme: dark`
  changes a single pixel of `/my/...`: the website frontend is light-only by
  design, and R20's native-list problem is a BACKEND one. So "check the portal
  in both themes" is satisfied by checking that every colour resolves — which
  is why every rule in `portal_onboarding.scss` carries a literal fallback
  beside its token. Do not go looking for a portal dark palette to fix.
- **R40 — `_read_group` cannot be called over JSON-RPC** (private method), and
  neither can any other `_`-prefixed helper. Aggregates during validation go
  through psql, or through a public facade method written for the purpose.
- **R41 — the ⌘K seed file's deep links run to 2370, not 2360.**
  `pb_hub/static/src/js/hub_palette_entries.js` auto-numbers its entries
  `DEEP_LINK_BASE + (i + 1) * 10` over 37 rows, so the occupied range is
  2010-2370 and grows every time somebody adds a seeded row. P2 took 2200-2220
  and P3 was told to take 2300-2320 — both sit ON TOP of seeded entries
  (`structures` is 2300, `statutory` 2310, `integrations` 2320). It is not an
  error, because the keys differ and both rows render, but the order of two
  unrelated palette rows then depends on registration order rather than on a
  number anybody chose. **P3 moved to 2400-2420; P4 onwards start at 2500**,
  and count the seed file rather than trusting the comment in it.

### P4 (pb_offboarding, 2026-09-01)

- **R42 — `t-att-class` with a DICT is an OWL thing, and server-side QWeb is
  not OWL.** `<div class="pbme-step" t-att-class="{'pbme-step--done': x}">`
  compiles, renders and produces
  `class="{'pbme-step--done': True, 'pbme-step--current': False}"` — the
  Python dict's REPR, written into the attribute. Worse, `t-att-class`
  REPLACES the static `class=` rather than adding to it, so the element also
  loses the class every rule was written against. No error, no warning: the
  resignation status stepper simply rendered as four lines of unstyled text
  with no dots. In a `<template>` (portal, website, reports) the only correct
  form is `t-attf-class="base #{cond and 'mod' or ''}"`. Inside
  `static/src/xml` OWL templates the dict form is right and merges with the
  static class — the two look identical and behave completely differently.
- **R43 — a public `@api.model` helper that takes a RECORD is called with an
  INTEGER over JSON-RPC.** A recordset argument does not survive the wire; it
  arrives as a plain id. An integer walks straight past `if not employee`,
  answers `False` to every `getattr`, and — inside the try/except that every
  one of these helpers correctly has — silently returns the FALLBACK. P4's
  notice policy offered a Vietnamese leaver 30 days instead of 45 with no
  error anywhere and no wrong-looking screen. Any public method whose argument
  is a record must coerce at the door (`pb.notice.policy._as_employee`), and
  any RPC validation of one must be read with this in mind before it is
  believed.
- **R44 — a gate that has nothing to check PASSES.** `pb.exit.clearance
  .pending_for()` answers "nothing pending" for a leaving checklist that has
  no clearance rows at all — which is true, and which meant the final
  settlement gate waved through every exit opened before this module existed.
  A probe over a set that is empty because it was never populated is
  indistinguishable from a probe over a set that is empty because everything
  is done. Any phase that adds a REQUIRED companion record to an existing
  parent has to backfill the parents that already exist, and the backfill
  belongs in the daily job (idempotent) rather than in a migration nobody
  reruns. P4's `_backfill_clearances()` is the shape.
- **R45 — the kit's `.pbim-modal` carries NO padding and IS a column flex
  box.** Deliberately: it is built for the `__head` / `__body` / `__foot`
  rails, which pad themselves. A free-form dialog that only sets a width
  therefore inherits `padding: 0` and `overflow: hidden`, and its heading is
  clipped flush against the left edge while its textarea runs off the right.
  A dialog that writes its own contents must set `display: block`, its own
  padding and its own `overflow: auto`. (P3's `.obb-modal` sets a width and
  nothing else — worth a look the next time somebody opens the buddy dialog.)
- **R46 — bracketed plurals are the tell.** "9 step(s)", "1 clearance(s)",
  "2 thing(s)" is how a screen announces it was written by a programme rather
  than by a person, and this product's whole voice is the other thing. Use
  `offboarding_common.counted(n, one, many)` (or the same two lines inline in
  JS/QWeb). Log lines keep the shorthand — nobody reads a log for its prose.
- **R47 — a mail queued with `force_send=False` on THIS database goes out
  within the second.** The hourly queue cron is not what sends it; something
  flushes at commit. R37's advice to cancel test traffic still applies but the
  window is far smaller than "an hour": cancel in the same script that sent,
  and assume anything addressed to a real mailbox has already arrived. Test
  with `@example.com` addresses only — and note that the lifecycle-manager
  fallback puts `ash@biztinct.com` on every HR notification, so the owner sees
  test traffic whatever you do.
- **R48 — `hr.full.final.settlement` has no chatter and P4 deliberately did
  not give it one.** Adding `mail.thread` to a model the payroll batch creates
  in bulk is a change with a blast radius far wider than an exit. The closure
  note goes to the leaving checklist's chatter, which is where somebody would
  look for it anyway. Its `_sql_constraints` list is also silently ignored on
  Odoo 19, so the "one settlement per employee per date" rule is not actually
  enforced — a pre-existing hole, not P4's, but do not rely on it.

### P5 (pb_probation, 2026-09-01)

- **R49 — a duplicate test whose key can be FALSE matches every row that is
  also empty.** `_make_feedback_requests` deduplicated on
  `respondent_user_id = False OR respondent_email = <theirs>`, and on this
  database most employees have no login — so the SECOND peer was recognised as
  "already asked" because the FIRST peer also had no user, and a three-person
  review silently sent one link. `sent: 1` was the only symptom, and it looks
  like a mail failure rather than a domain bug. **Only the identifiers a record
  actually HAS may go into an idempotency key**; a record with none has no
  identity to be a duplicate of and must be created. (The same shape as R21 —
  an audit row cannot carry the key it duplicates — reached from the other
  direction.)
- **R50 — ordering by a Selection column sorts by the STORED STRING.** A board
  that wanted "the live one first" wrote `order='state, id desc'` and got
  `closed` before `consolidation` before `feedback` … because that is
  alphabetical order, not lifecycle order. The Probation lens showed "Closed"
  for a person whose second round had just been scheduled, and the live review
  was invisible. Never let a state's importance be implied by its spelling —
  ask the question in a domain (`state in OPEN`) and fall back, which is what
  `pb.probation.review.for_employee()` does.
- **R51 — `t-out` ESCAPES a plain string and only renders `markup()` raw.**
  An `Html` field crossing JSON-RPC arrives in the browser as a plain string,
  so a cockpit that hands it to `t-out` puts `<h4>How they were rated</h4>` on
  the screen — the report's own source code, rendered as prose. Wrap it once
  with `markup()` from `@odoo/owl` (the codebase's existing idiom — see
  `pb_dashboard`), and only where the HTML was built server-side with every
  interpolated value `escape()`d.
- **R52 — R43 bites inside a module as easily as across one.** P5's own
  `pb.training.track.tracks_for()` / `ensure_for_employee()` are public,
  take a record, are called with records internally — and blew up with
  `'int' object has no attribute 'job_id'` the first time a test called them
  over RPC. Every public method whose argument is a record needs the
  `_as_employee` coercion at the door, including the ones a phase writes for
  itself.
- **R53 — a "run it now" button must do exactly what the night does.**
  `run_probation_automation` originally ran four of the daily job's five
  pieces (it left out the trial-state top-up), which meant the number it
  reported could not be compared to the morning's log — and the one piece it
  skipped was the only one reachable for testing, because everything else in
  the cron chain is a private method (R40).
- **R54 — a switch that is off and does not SAY so is reported as broken.**
  `pb_probation.auto_trigger` ships off, because the first night after install
  would otherwise open a review and email a manager for every trial period
  already inside its lead time. Off, the daily job COUNTS them and logs the
  number ("3 would have had a review opened tonight"), and the lens says the
  same thing on screen with the same number. The kill-switch/log-only first run
  is worth copying for any phase whose cron writes to people.
- **R55 — the live database has NO employee with a trial end date.** All 4,537
  are `pb_probation_state = 'passed'` after the backfill, and every
  `employee_type` is `employee`, so the `na` branch never fired in anger. A
  phase that needs somebody mid-trial has to make one. (It also means the
  backfill's expensive path — the ORM pass over the exceptions — was never
  exercised at scale; the cheap path, one UPDATE over 4,537 rows, ran in
  well under a second.)

### P6 (pb_pip, 2026-09-01)

- **R56 — reading ONE field of an `hr.employee` reads FORTY, and about forty
  of them are behind payroll groups.** `employee_id.name` prefetches every
  stored field of the record, `check_field_access_rights` is applied to the
  whole prefetch, and this build's employee carries `payroll_country`,
  `insurance_code`, `trade_union_fee_code`, `tham_gia_bhxh` and some
  thirty-odd more behind `groups=`. So a reader who holds a NEW module's
  group but not the payroll ones gets `AccessError: The fields
  "location,full_name_vn,org_employee_type,…"` — forty names nobody asked
  for — in the middle of an action that wanted a first name. It is invisible
  to any phase whose testers are administrators, which is every phase before
  this one. **A module with its own group ladder must read employee
  attributes as the system** (`pb.pip.case._person()`,
  `pb.pip._emp()`); the security boundary stays the search that found the
  record. The alternative — requiring the new group's holders to also hold
  the payroll groups — hands out far more than it withholds.
- **R57 — a `noupdate` seed is skipped only if the FILE says so AND the
  `ir_model_data` row says so.** They are ANDed, both directions. Clearing
  `ir_model_data.noupdate` in SQL is not enough on its own (P6 watched a
  reworded letter template not land, twice), and neither is stripping the
  file attribute. To genuinely reload a seeded record on this database:
  `UPDATE ir_model_data SET noupdate=false WHERE module='<m>'`, strip
  `noupdate="1"` from the file, `-u`, then re-sync the clean file. And
  **restore the flags PRECISELY afterwards** — P6 set all 212 rows back to
  `noupdate=true`, which silently froze its own `ir.ui.view` records, and the
  next three template edits did not reach the screen. Only the genuinely
  seeded families (`mail.template`, `pb.letter.template`, the module's own
  seed models, `ir.config_parameter`, the `ir.rule` records inside a
  noupdate block) want the flag set.
- **R58 — `(0, 0, {...})` inside a one2many in a seed file mints new
  children on EVERY load.** It is a CREATE command with nothing to match on,
  so there is no update path: three reloads of the same data file turned
  three focus areas into nine, and the dialog rendering them showed each one
  three times. There is no error and the parent record looks fine. **Every
  seeded child gets its own `<record>` and its own xmlid**, so it is matched
  and updated like anything else.
- **R59 — a `noupdate` config-parameter write DOES invalidate the record-rule
  cache, so a switch expressed as a computed field on `res.users` bites
  immediately.** `ir.rule._compute_domain` is memoised in the `default`
  ormcache group; `ir.config_parameter.write` clears `stable`, and
  `registry.__caches_groups__['stable'] = ('stable', 'default',
  'templates.cached_values')`. That is what makes the shape work: a rule
  domain of `[('requested_by_user_id', '=', user.id if
  user.pip_manager_sees_own else -1)]` reading a non-stored computed field
  that answers a config parameter. ONE source of truth, no sync job, no
  toggled `ir.rule.active` to drift out of step with the setting, and no
  re-login. Proven both ways in the same session.
- **R60 — `ir.rule` group rules are ORed, so ADDING a narrow rule for a new
  group SILENTLY NARROWS anyone who holds both.** P0 put only GLOBAL company
  rules on `pb.employee.checkin` / `pb.feedback.request` / `pb.hr.letter` and
  no group rules at all, so today a lifecycle manager sees every row. Adding
  one rule limiting the PIP group to `pip_case_id != False` would have meant
  a lifecycle manager who is also given the PIP group has exactly ONE
  applicable group rule — the narrow one — and loses sight of every
  onboarding check-in in the company. **Ship the pair**: an explicit
  "everything" rule for the existing tiers beside the narrow one for the new
  tier. Any phase that borrows a model from an earlier phase and wants to see
  less of it has to do this.
- **R61 — an Html field edited in a plain textarea shows its own tags.**
  Obvious said out loud, invisible while the field is empty: `coaching_html`
  looked perfect until somebody saved once and came back to
  `<p>Spoke on the 1st.</p>` in the box they were typing in. A cockpit drawer
  that edits prose wants a `Text` field; `Html` is for something that is
  rendered and never re-entered, or for a surface with a real editor in it.
- **R62 — a portal home card gated on a COUNTER is never drawn.**
  `portal.portal_my_home` fetches its counters lazily after the page renders,
  so at render time `growth_count` is not a number and `t-if="growth_count"`
  is simply false. There is no error. A card whose PRESENCE is conditional
  needs its own eagerly-computed key, set in a `home()` override on every
  path through it (QWeb raises on a name it has never heard of, so a missing
  key turns a hidden card into a 500 for the whole of `/my`).
- **R63 — the lens rail label box is 60px.** "Probation" fills it exactly;
  "Improvement plans" measured 76px and spilled outside the rail. Measure a
  new lens label in the DOM before shipping it
  (`getBoundingClientRect().width` against the parent's), and prefer a label
  whose LONGEST WORD fits — the box wraps between words but never inside
  one. P6 renamed the surface to "Growth plans", which fits at 54px and has
  the better property of being the same phrase the employee reads on their
  own page.

### P7 (pb_comp_ben, 2026-09-01)

- **R64 — A CONTRACT COMPONENT IS NOT NECESSARILY MONEY, and the scheme's own
  metadata cannot tell you which is which.** Bootstrapping a pay package from
  contract 1 produced 1,014,240,048 ₫ a year against a wage of 15,000,000 a
  month, because `Ngạch lương` is a salary GRADE of 60,000,000, `NPT` is a
  count of dependants (3) and `Tỷ lệ %` is a ratio (1) — and all three carry
  `value_kind='money'` with no net role on this tenant, exactly like the meal
  allowance beside them. There is no rule that separates them, so do not invent
  one. The bootstrap PROPOSES instead: every line off the contract arrives
  `checked = False`, is shown with its number so a human can judge it, counts
  towards no total, and `action_activate` REFUSES while any is unchecked —
  naming each one and saying to tick it or delete it. The wage line is checked,
  because a wage is money by definition. A total that is always true is worth
  more than a total that is usually complete. Any phase that derives money from
  somebody else's typed field inherits this problem.
- **R65 — R60 bites INSIDE a module as easily as across one.**
  `pb.benefit.enrollment` shipped the narrow "my own enrolment" rule for the
  portal without the wide pay-team rule beside it, and `read` on the enrolment
  the phase had just created was refused for uid 2. Rules are ORed over the
  rules that APPLY, so a narrow rule shipped alone is a narrowing. Ship the
  pair, in the same file, always — including for a model your own module owns.
- **R66 — `hr.payslip.run` HAS NO CHATTER on this build.** No `mail.thread`, so
  every `message_post` the finance pack wanted for an honest note was an
  AttributeError — and the first live test failed twice over: once on a bad bank
  format, and again on the note that was explaining it. Do NOT add `mail.thread`
  to the run (P4 declined the same for `hr.full.final.settlement`, and the run
  is worse: the payroll batch creates these in bulk). The outcome lives in a
  `pb_pack_note` Text field on the run, surfaced on the native form, written
  through a `_pb_note` helper that swallows its own failures. A note is a
  courtesy and must never be able to affect an approval.
- **R67 — a bad config value must be answered with the list of what IS
  accepted.** `pb_comp_ben.bank_format` set to something the export wizard does
  not know raised a raw ORM ValueError at the user. The field is now asked what
  it accepts (`Wizard._fields['bank_format'].selection`) and the skip says so:
  "… is not a bank this build knows. The ones it knows are acb, bidv,
  generic, …". Any config parameter that feeds a Selection should do this.
- **R68 — a heading that asserts a sign is wrong half the time.** A statutory
  line entered as a POSITIVE number inflated the package under a heading that
  read "What is taken off by law". The heading now FOLLOWS the sign — "What is
  taken off by law" or "Paid on your behalf by law" — and the amount's help says
  to enter a deduction as a negative. Never let a label make a promise the data
  is free to break.
- **R69 — a try/except around a parse swallows the permission error of the field
  it is parsing.** `dependants()` wrapped `json.loads(enrolment.dependants_json)`
  with the field READ inside the try, so an AccessError came out as "unreadable
  family list" — a permission problem reported to the user as a data problem,
  with nothing in the log to say otherwise. Read the field OUTSIDE the try; only
  the parse belongs inside it.
- **R70 — `done_payslip_run()` is NOT the done transition on this build.** Its
  own docstring (`pb_payruns/models/hr_payslip_run.py:550`) says it is the
  **draft → level0** entry; the final Finance approval that writes 'done' is
  `action_payslip_run_level2_done` (`:472`). The P7 handover named the wrong one
  from the method's name alone. Hooking it would have built a finance pack on
  submission and marked awards paid before anybody had approved them. Read the
  docstring, not the name.
- **R71 — `payroll_import_batch._create_payslip` ALWAYS CREATES**
  (`payroll_import_batch.py:3512`) — there is no "find the slip this run already
  has for this person and update it" path. So processing an import batch against
  a run that has already been computed puts a SECOND payslip on one person for
  one month, the exact duplicate `pb_payrun_wizard._adopt_loose_slips` exists to
  prevent — and the run an award is aimed at is by definition already computed.
  The award lane therefore uses the one-time batch only as the audit record and
  the safety rail (`one_time`, `auto_create_employees=False`,
  `auto_create_contracts=False`, `create_payslips=False`), creates its lines
  DIRECTLY rather than through a generated XLSX, and DELIVERS by merging the
  amount into the existing payslip's `formula_input_values` **and** the run's own
  import-line blob, then rebuilding the lines with the batch's own
  `_compute_and_create_payslip_lines` — the function the Recalculate button uses
  (`hr_payslip_formula.py:913`). Writing the blob too is what makes the award
  survive a later recompute, because `action_recompute_formula_lines` re-reads
  the sources (RD45). The value is SET, not added, so the lane is idempotent. A
  person with no payslip in the run is REPORTED, never created. Anything that
  needs to put a number onto an EXISTING payslip must use this lane.
- **R72 — the pay component code is a REQUIREMENT, not a preference.** A
  payslip's inputs are `config.rule_ids` where `column_type == 'input'`
  (`hr_payslip_formula.py:492`). A number written under a code the run's scheme
  has never heard of is read by nothing and lands nowhere — no error, no line,
  no total. The feed therefore REFUSES a run whose scheme has no input component
  with the configured code (`pb_comp_ben.incentive_code`, default `INCENTV`) and
  the preview names the scheme that is missing it. It never auto-edits a formula
  scheme: adding the component is a human act on the Mapping screen.
- **R73 — `pb_payhub` had no soft lens registry.** Its eight lenses were a
  literal array, so P7 added ONE additive edit: the exported constant
  `PAY_LENSES = "pb_payhub_lens"` and an `extraLenses()` spread at the end of the
  list, an exact clone of `pb_people_hub`'s (`people_hub.js:113`). The eight
  shipped lenses carry no sequence, so bolted-on ones start at 20 (P7 took
  **Calendar 20, Awards 30**). The edit is JS ONLY — no manifest bump — so the
  deploy needs the asset-cache purge and never a `-u pb_payhub`, and anyone
  verifying it should read the registry in the browser
  (`odoo.loader.modules.get("@web/core/registry").registry.category("pb_payhub_lens")`)
  rather than trust a version number. Same trick verifies ⌘K rows through
  `registry.category("pb_hub_palette")`.
- **R74 — the ESS demo passwords drift between phases.** R29's `RizeP2!2026` on
  `ess1.demo@payobook.com` (employee 10080, uid 1984) no longer worked at P7 and
  the portal test read as a broken route rather than a stale password. Do not
  debug the route: set the password again as admin (`res.users.write` over
  `call_kw`) before testing any `/my/...` surface. P7 set **`RizeP7!2026`**.
  Owner debt, with R29's: clear these at programme end.
- **R75 — ⌘K blocks after P6.** P7 took the **2800** block (cb_paycal 2800,
  cb_awards 2810, cb_packages 2820, cb_benefits 2830, cb_my_pay 2840). P8 starts
  at 2900.

### P8 (pb_rnr, 2026-09-01)

- **R76 — a CAP that is right for a SCREEN is a bug in a CRON.**
  `upcoming_celebrations` capped its answer at sixty, which is correct for the
  wall's side strip and for the mood board — and silently wrong for the two
  jobs that WRITE to people. A seven-day window on this tenant holds a hundred
  and forty-two managers' worth of celebrations, so the Monday heads-up told
  the first sixty rows' managers and nobody else, reported a cheerful number,
  and logged no error. Any read shared between a payload and a job needs the
  cap as a PARAMETER, and the job passes "no cap". The same trap is waiting in
  every `_read` a later phase reuses for a cron.
- **R77 — `hr_employee.first_contract_date` is a REAL COLUMN that is not
  WRITABLE on this build.** It exists in Postgres (unlike the `hr.version`
  family of R14) and it reads back fine, but a `create`/`write` carrying it is
  dropped on the floor: it is derived. A fixture built with one has no join
  date at all, so it has no work anniversary and no joiner row in the digest,
  and nothing anywhere says so. The join date must come through the
  `pb_people._join_date` ladder — the column, then `min(hr_contract.date_start)`,
  then `create_date` — and a test fixture that needs one needs a real
  `hr.contract`.
- **R78 — Postgres on this box has NO `unaccent` extension**
  (`select * from pg_extension` — it is not there). So `ilike '%bui%'` does not
  find "Bùi", and about four and a half thousand of the five thousand people on
  this tenant have an accent in their name. Any people-picker has to fold
  accents in PYTHON (`rnr_common.fold`, NFKD plus the hand map for `đ` — R28's
  helper, reached from the other direction) over a `search_read` of the two
  columns it needs, never a domain `ilike` and never a `search` of records
  (R56: one field of an `hr.employee` prefetches forty).
- **R79 — an administrator's own `hr.employee` sits in company 1**, the empty
  shell the initial install left (R16 from the other end). So ANY facade that
  scopes to `self._me().company_id` answers an administrator with an empty
  screen — P8's colleague picker offered nobody at all until it was scoped to
  `self.env.companies.ids` instead. The company boundary is a property of the
  SESSION, not of where somebody's employee record happens to live; enforce it
  at the moment of writing, not at the moment of listing.
- **R80 — a chip that counts one thing over a list that shows another is two
  bugs.** The wall's value chips counted `pb.company.value.nomination_count`,
  which includes praise its writer asked to keep PRIVATE. The result said
  "Excellence 1" over a wall with no Excellence story on it: a filter that
  matches nothing (R27) AND a quiet admission that a private story exists.
  Any count beside a filtered list must be computed from THAT LIST'S OWN
  domain — here `pb.rnr.nomination._public_domain()`, the single clause that
  decides what the wall shows.
- **R81 — the Awards lens's "Put into a pay run" dialog picks by the RUN'S
  MONTH, not by what is approved.** `pb.oneoff.feed._pick` falls back to
  `approved_for_month(run.date_end)` when no ids are passed, and the P7 lens
  passes none. So an award raised in September cannot be put into the August
  run FROM THE BUTTON — the dialog simply does not list it — even though
  `preview_for_run(run_id, [ids])` says it is payable and `queue_for_run` does
  it correctly. Not a defect in either module; it is a real limit on the
  button, and anybody proving a cross-month award has to call the API with
  explicit ids. Worth an owner decision if recognition awards routinely need to
  ride an older run.
- **R82 — `/web/image/hr.employee/<id>/image_128` draws a grey CAMERA when the
  field is unset; `avatar_128` draws a real default avatar** (a coloured disc
  with the person's initial). Both answer 200, so nothing looks broken to a
  test — it just looks broken to a person. Use `avatar_128` for anything
  person-shaped.
- **R83 — `pb_home_hub` had no soft lens registry.** Its two lenses were a
  literal array, so P8 added ONE: the exported constant
  `HOME_LENSES = "pb_home_hub_lens"` and an `extraLenses()` spread at the end
  of the list — an exact clone of `pb_people_hub`'s (`people_hub.js:82`) and of
  what P7 did to `pb_payhub` (R73). The edit is JS ONLY — no manifest bump — so
  the deploy needs the asset-cache purge and never a `-u pb_home_hub`, and the
  seam is now enforced by
  `pb_home_hub/tests/test_home_hub.py::test_a_later_module_can_bolt_a_lens_on_without_editing_this_hub`.
  The two shipped lenses carry no sequence, so bolted-on ones start at 20 (P8
  took **Wall 20**). On the People hub, Records is 40 and Assets is 50, so
  **Praise took 60**.
- **R84 — "Recognition" does not fit the 60px lens rail (R63), and the fix was
  the same one P6 found.** Eleven characters with no break in them measure
  wider than the box, exactly as "Improvement" did. The label is **"Praise"**,
  which measures 37px against a 60px box — narrower than the shipped
  "Employees" (61px) and "Contracts" (63px), which both marginally overflow
  today — and which has the better property of being the same word the
  employee reads on their own page and on the wall.
- **R85 — `prefers-reduced-motion` cannot be emulated through Chrome MCP**
  (`emulate` exposes colour scheme and viewport, not media features). The
  stronger proof is the COMPILED CSS: put every moving declaration
  (`opacity: 0`, the transform AND the animation) inside
  `@media (prefers-reduced-motion: no-preference)`, then fetch the deployed
  bundle and read the block back. Under a reduced-motion preference none of the
  three is applied at all, so the surface paints finished on the first frame
  with nothing to recover from — which is a different and better property than
  declaring an animation and then cancelling it. `@keyframes` must live at the
  TOP LEVEL of the stylesheet: nested inside a selector, Sass emits it nested
  too and no browser plays it.
- **R86 — ⌘K blocks after P7.** P8 took the **2900** block (rnr_wall 2900,
  rnr_board 2910, rnr_values 2920, rnr_cycles 2930, rnr_my 2940). P9 starts at
  **3000**.
- **R87 — the ESS/manager fixture passwords, again (R29/R74).** P8 set
  `rize.p8.mate@example.com` / `RizeP8!2026` (uid 2333, employee 17138) and
  re-set `rize.p4.boss@example.com` / `RizeP4!2026` (uid 2326). Owner debt with
  the rest: clear these at programme end.

### P9 (pb_budget, 2026-09-01)

- **R88 — a RATE ROW BELONGS TO A COMPANY, and R23's tell is not enough on
  its own.** R23 says two different currencies reported at the SAME rate
  means nobody has told the database what one is worth. True, and
  insufficient: a currency with NO `res.currency.rate` row at all silently
  reads as 1.0, so converting it into one that DOES have a rate produces a
  plausible-looking number built on nothing — a brand-new currency came back
  convertible into dong at 26,330 to one. And `_get_rates` reads only the
  rows whose `company_id` is empty or is the company being converted FOR, so
  a probe that ignores the company answers "known" about a rate the
  conversion is then not allowed to use. Ask both questions:
  a rate row exists, VISIBLE TO THIS COMPANY, dated on or before the day —
  and only then apply the 1.0 guard. **On this tenant all 163 rate rows
  belong to company 1 ("Your Company")**, so the operating company
  (Payobook Vietnam JSC, company 5) genuinely cannot convert anything and the
  per-row manual rate is the only honest answer there.
- **R89 — `report.sudo()._render_qweb_pdf()` RENDERS AS SUPERUSER, and a
  report that re-reads its own data then sees every company.** P7's precedent
  sudoes the report record, which is fine for a report over records the
  caller already holds; it is a leak the moment the template calls a facade.
  P9's budget summary carried another company's departments into a
  company-scoped reader's PDF, with totals that disagreed with the
  spreadsheet exported beside it — and nothing looked wrong. Render as the
  caller (`report.with_context(allowed_company_ids=self.env.companies.ids)`)
  AND put the company clause explicitly in every facade search, which is the
  Explorer's own rule (C18.11/18) reached from a new direction.
- **R90 — a Monetary is rounded to its CURRENCY, so an unrounded write is
  "changed" for ever.** Dong keeps no cents: 103,634,883.44 was written, read
  back as 103,634,883, and found different on the next run. The figures were
  identical every time and only the COUNT lied — "10 department-months
  updated" every night, on a job whose whole claim is that it is idempotent.
  Round to the target currency (`currency.round(value)`) BEFORE comparing and
  before writing, and a nightly job's report becomes a number somebody can
  act on.
- **R91 — `hr.department.complete_name` is COMPUTED and NOT STORED on this
  build.** `search(..., order='complete_name')` dies with *Cannot convert
  hr.department.complete_name to SQL*. Sort in Python
  (`.sorted(lambda d: ...)`), which is where a translated tree path has to be
  sorted anyway. (`search_read` of it is fine — only ORDER BY is not.)
- **R92 — a swallowed exception logged at DEBUG is invisible on a live
  server.** The `safe()` wrapper every cockpit facade uses returned its
  default and said nothing, so a job that half worked reported a cheerful
  small number and no error — R54 and R76's shape reached from a third
  direction. Log at WARNING with `exc_info=True`; the caller still gets its
  default, and the failure is findable.
- **R93 — `wfp.budget.actual` was an EMPTY SHELL, which is why D2 could name
  it canonical without a migration.** Zero rows, zero writers, zero views;
  its only references in the codebase were its own two ACL lines and a
  one2many on the scenario. That is what made three overrides safe:
  `scenario_id` optional (a budget is not a by-product of a compensation
  scenario), `company_id` from `related='scenario_id.company_id'` to the
  row's own stored column (without it a scenario-less row carries NO company,
  and a company-less row is visible to everybody — R8), and `currency_id`
  following the row's own `pb_currency_id`. **Overriding a field to drop its
  `related` works**: Odoo 19 merges field attributes down the MRO with
  `attrs.update(self._args__)` and gates on `if self.related:` truthiness
  (`odoo/orm/fields.py:399,539`), so an explicit `related=False` in the
  inheriting class clears it.
- **R94 — the column map, for anybody reading a budget row.**
  `forecast_cost` / `forecast_headcount` are the BUDGET and only the upload
  or a person writes them; `actual_cost` / `actual_headcount` are the SPEND
  and only the actuals job writes them; `variance_amount` is the first minus
  the second and `variance_pct` that over the budget, both computed by the
  model as it shipped. The actuals job never NAMES a forecast column, and
  `pb_budget/tests/test_budget.py` greps the file to keep that true.
- **R95 — the Cost Explorer mirror, written out once.** A budget row's
  payroll figure is `measure=total_cost, dimension=department_id,
  grain=month, filters={}` — i.e. `SUM(amount) FROM pb_fact_line WHERE
  run_id IN <built, non-cancelled runs> AND company_id IN <companies> AND
  category_type IN ('basic','allowance','employer_cost') AND
  COALESCE(is_rollup, FALSE) = FALSE GROUP BY department_id, month`, with the
  head count from `pb_fact_emp` because a distinct count at component grain
  double-counts people. Two deliberate differences: no `_RUN_SCAN` 200-run
  cap (R76 — right for a screen, wrong for a job) and it never builds facts,
  it reports what is not built yet. Proven equal to the dong: Engineering,
  June 2026 = 28,620,552,880 ₫ on both surfaces.
- **R96 — `pb_insights_hub` had no soft lens registry.** Its four lenses were
  a literal array, so P9 added ONE: the exported constant
  `INSIGHTS_LENSES = "pb_insights_hub_lens"` and an `extraLenses()` spread at
  the end of the list — an exact clone of what P7 gave `pb_payhub` (R73) and
  P8 gave `pb_home_hub` (R83). JS ONLY, so the deploy needs the asset-cache
  purge and never a `-u pb_insights_hub`, and the seam is now enforced by
  `pb_insights_hub/tests/test_insights_hub.py::TestSoftLensRegistry`. The four
  shipped lenses carry no sequence, so bolted-on ones start at 20 (P9 took
  **Budget 20**). "Budget" is six characters and sits well inside the 60px
  label box (R63).
- **R97 — a lens can be the ONLY lens somebody sees, and that is correct.** A
  budget holder holds no analytics group, so the Insights hub opens for them
  with Budget alone on the rail — `HubShell._resolveAccess` falls back to the
  first allowed lens, so nobody lands on a lens they cannot read. The hub's
  own ⌘K row is still gated on the analytics union and does NOT offer them
  the mission; their door is this module's own palette row. Worth knowing
  before adding a lens whose readers are not the hub's usual readers.
- **R98 — ⌘K blocks after P8.** P9 took the **3000** block (bdg_board 3000,
  bdg_upload 3010, bdg_expenses 3020, bdg_rows 3030). P10 starts at **3100**.
- **R99 — the P9 test logins** (D9: left in place, listed for the owner).
  `rize.p9.head@example.com` (uid 2336, budget holder, employee 17139, manages
  the test function 657), `rize.p9.finance@example.com` (2337),
  `rize.p9.plain@example.com` (2338), `rize.p9.wfp@example.com` (2339),
  `rize.p9.both@example.com` (2340) — all `RizeP9!2026`. Owner debt with
  R29/R74/R87: clear these at programme end.

### P10 (pb_contract_lifecycle, 2026-09-01/02)

- **R100 — a job that skips only OPEN work re-does the work that is FINISHED.**
  `_due_for_decision` skipped a contract while its decision was open, which is
  the obvious test and the wrong one: the night after a contract was extended
  the SAME contract was raised again and its manager emailed about it, for
  ever, because "done" is not "open". A nightly job that creates a record per
  parent has to test for ANY child, not for an unfinished one — and the manual
  door (`open_for`) has to refuse by name, saying what was decided and pointing
  at the contract that followed. The same shape is waiting in every phase whose
  cron opens a case per record.
- **R101 — a REQUIRED field with a DEFAULT cannot tell you whether anybody has
  said.** `employee_type` is required and defaults to `employee`, so "nobody
  has typed this person" and "somebody deliberately made this person permanent"
  are the same stored value. The nightly top-up therefore read the contract of
  somebody who had just been converted, saw the word "contractor" in the
  category they used to be on, and typed them back — every night, reporting a
  cheerful count. A guess can only lose to a statement if the statement is
  WRITTEN DOWN: `pb_employment_type_set` is set by every deliberate write (a
  person, the connected system, a conversion) and the guess never looks at a
  record that carries it.
- **R102 — reusing another phase's machine means inheriting its SIDE EFFECTS,
  not just its flow.** P5's `kind` field made a conversion evaluation free —
  but all three of P5's verdict handlers write `pb_probation_state`, and the
  extend one moves `trial_date_end`, which is the one in-place employment write
  ruling D1 carves out FOR PROBATION. Run against a conversion those are false
  records: a two-year contractor's file read "Trial period: Not passed" about a
  trial period they never had. Snapshot the fields the borrowed machine writes
  and put them back for your own kind; do not fork six things it does
  correctly to change one.
- **R103 — a borrowed machine's WORDS are part of its behaviour.** P5's four
  emails and three letters say "trial period" and "probation" — right for a
  trial period, wrong for somebody being considered for a permanent contract
  after two years on fixed terms. The first live conversion told a manager
  "…'s trial period ends soon — who should we ask?", and the one that did not
  pass sent the person a letter saying their employment had not been confirmed,
  over a board whose own consequence copy promises "nothing is created and
  nobody is told they failed". Reworded WITHOUT touching P5's `noupdate` seeds
  (R57 — that means the `ir_model_data` dance across every live review): the
  later module ships its own templates and swaps them in with a two-line
  `_mail` override keyed on `kind`, and suppresses the borrowed letters when it
  is sending its own.
- **R104 — R56 can eat a SUCCESS and report it as a failure.** The person who
  agrees a contract extension is the employee's own MANAGER, who holds no HR
  group by definition — and `private_email` carries `groups="hr.group_hr_user"`.
  So the first live approval built the new contract, closed the decision and
  filed the letter, then died working out who to email, inside the caller's
  try/except, and posted "the new contract could not be prepared" over a
  contract that had been created a line earlier. Two rules out of it: every
  address helper reads the employee AS THE SYSTEM, and the notification legs
  (letter, mail) get their own guards so paperwork can never be reported as a
  failed agreement.
- **R105 — a term of N months ENDS THE DAY BEFORE the anniversary.** Twelve
  months from 1 Nov 2026 is 31 Oct 2027, not 1 Nov — `add_months` alone makes
  every contract a day long, the next term starts on the 2nd, and each renewal
  walks one more day from the date it is meant to keep. `contract_common
  .term_end()` is `add_months(start, months) - 1 day` and is the only thing
  that should compute a contract's end.
- **R106 — a heuristic word list must not contain a word that is TRUE OF BOTH
  SIDES.** "fixed-term" was in the contractor list, and a fixed-term EMPLOYEE
  is an employee — the whole premise of this phase is that permanent staff can
  be on an agreement with a date on it. The live backfill retyped a test
  employee off a contract called "P10 fixed-term — …" and out of the headcount.
  The "Fixed-term contractor" contract type still matches, on the word
  "contractor" that is actually in it.
- **R107 — `hr.contract.type` is ALREADY SEEDED on this database, twelve rows
  from the standard `hr` module, "Intern" among them** (`hr.contract_type_intern`,
  id 7) — not the three rows `om_hr_payroll/data/hr_contract_type.xml` implies.
  A `<record>` of our own would have put a SECOND row called Intern in the
  picker, and a picker with two identical options is a picker nobody can use.
  ENSURE by name from a hook that the daily job also calls, never seed. (P10
  created only "Fixed-term contractor", id 83.) `hr.contract.type` also has NO
  `company_id` on this build — probe before setting one.
- **R108 — `format_date(env, d)` with no pattern answers the LOCALE's format,
  and for an `en_US` admin that is `02/01/2027`** — the first of February to
  half the world and the second of January to the other half, printed beside a
  board that writes "1 Feb 2027" from `toLocaleDateString`. Two date formats on
  one screen is one too many and an ambiguous one on a contract letter is worse
  than that. Pass `date_format='d MMM y'` for anything a person reads.
- **R109 — a facet's sort order is part of what it MEANS.** Month chips sorted
  by count read "October 2026, November 2026, August 2026, December 2026…" and
  a reader looking for next month had to hunt. A `YYYY-MM` key sorts
  chronologically as a string; any facet whose values have a natural order
  wants that order, not the biggest-first default the other facets use.
- **R110 — the assets bundle does NOT always rebuild on `-u`.** P10's lens was
  absent from `registry.category("pb_lifecycle_lenses")` in the browser after a
  clean `-i` with EXIT=0, on a module whose JS had been on disk the whole time.
  The purge is the fix (`DELETE FROM ir_attachment WHERE url LIKE
  '/web/assets/%'` then a hard reload), and the check that matters is reading
  the registry in the browser rather than trusting the version number (R73's
  advice, reached from the install side rather than the JS-only side).
- **R111 — ⌘K blocks after P9.** P10 took the **3100** block (contracts_board
  3100, contracts_decisions 3110, contracts_extensions 3120). P11 starts at
  **3200**. Lifecycle-hub lens sequences are now Journeys (none), New joiners
  20, Exits 30, Probation 40, Growth plans 50, **Contracts 60**; P11 starts at
  70. "Contracts" measures 63px in the 60px rail label box — the same marginal
  overflow as the People hub's own shipped "Contracts" (63px) and "Employees"
  (61px), and the shortest label that is still the word on the screen.
- **R112 — the P10 test cast** (D9: left in place, listed for the owner).
  Employees **17140-17147** (`rize.p10.a@example.com` … `rize.p10.h@example.com`,
  company 5, department "RIZE P4 (test)", manager 17122) each with an end-dated
  contract 14581-14588, plus **17148** "RIZE P10 Arriving Intern"
  (`rize.p10.intern@example.com`) created through the connected-system path to
  prove an arriving intern arrives AS an intern. None of them has a login. The
  approvals were made as **`rize.p4.boss@example.com` / `RizeP4!2026`** (uid
  2326, R87's account, password unchanged) to prove a manager who holds NO HR
  group can agree an extension.


### P11 (pb_vendor_access, 2026-09-01/02)

- **R113 — "the live one first" is the WRONG headline for a register whose job
  is to raise problems.** `pb.vendor.agreement_state` ranked `expiring` then
  `running` then `expired`, so a supplier with a three-year licence running AND
  a support contract that lapsed last month rendered as **Running**, the lapsed
  row was invisible on the board, and the "already run out" figure beside it
  read **zero** over a register that had one. Both halves were individually
  defensible and together they were a lie. Rank the PROBLEM first — ended,
  ending soon, running, not started, replaced — and within a band the one that
  ends soonest, because that is the date somebody has to act on. R80 reached
  from the other side: there the chip was wrong about the list, here the LIST
  was wrong about the data.
- **R114 — the kit's scrim is `.pbim-modal-scrim` and the modal is its CHILD,
  not its sibling.** `.pbim-modal` carries no positioning of its own (R45 covers
  its padding; this is the other half): the scrim is `position: fixed` with
  `display:flex; align-items:center`, and that is the only thing that centres a
  dialog. Written as a sibling — with a hand-rolled `.pbim-scrim` class that
  does not exist — five dialogs rendered unstyled at the kit's default 1040px,
  at the very bottom of the document, with no dimming. Nothing errored.
  **And do not nest the dialog's own rules under the cockpit's root class.**
  `modal.scss:43` says why in the kit's own words: "a scrim mounts OUTSIDE the
  surface that opened it as often as inside". A descendant selector makes a
  dialog's whole appearance depend on where in the DOM it lands, and the day
  something portals it the rules vanish silently. Own classes, tokens
  re-declared on the scrim.
- **R115 — a blind `str.replace` on template indentation is how you close the
  wrong `</div>`.** Adding the scrim's closing tag by matching
  `'        </div>\n      </div>\n\n      <!--'` inserted it correctly for the
  dialogs followed by a comment and NOT for the last one in each file — which
  left the count balanced, the XML parsing cleanly, and the whole dialog block
  sitting OUTSIDE the cockpit's root div. The tell was in the browser, not the
  parser: `scrim.parentElement.className` read `o_action_manager`. **Verify OWL
  template nesting by walking the parsed tree** (each scrim is a direct child of
  the root and holds exactly one modal), never by "it still parses".
- **R116 — R110 again, and the purge is NOT the fix on this build.**
  `DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'` answered
  **DELETE 0** every single time: this server has ZERO asset attachment rows and
  serves `/web/assets/debug/web.assets_web.css` — an unversioned URL — straight
  out of the bundler. So there is nothing to purge and the stale copy is in the
  BROWSER. Separate the two questions before touching anything: `curl` the
  bundle URL and grep for your own rule. If the server has it, the fix is
  `emulate` with `Cache-Control: no-cache` plus a reload with `ignoreCache`; if
  the server does not, it is a deploy or a Sass error. A restart alone changes
  nothing either way.
- **R117 — a phrase-frame with one word swapped produces "You does not have".**
  `_("%(who)s does not have …", who=… if other else _("You"))` is the tidy
  version and it is ungrammatical for exactly one of its two cases — and a
  translator handed the frame and the word separately cannot fix a verb they
  were never given (W80). Branch the WHOLE sentence. Same shape: a job that
  reports "0 permissions were taken back" is a machine writing; "and nothing
  needed taking back" is the same fact in words a person uses, and zero is a
  real and common outcome here (the borrower already held it).
- **R118 — a white-label gate must strip COMMENTS before it greps.** The
  obvious test failed on `<!-- \`<act_window>\` is gone from the Odoo 19
  data-file RNG -->` — the exact sentence that stops the next contributor
  reintroducing the bug. The rule binds user-visible STRINGS; engineering
  comments must be able to say the real name. Same lesson as W101/W114 inside
  `pb_settings`, whose own tag gate then failed on this module's registry
  example (`tag: "pb_vendors_board"` in a doc comment) — that gate now reads
  `_code(_js())` like every other gate in the file.
- **R119 — `pb_settings` had no soft registry.** Its eight categories were a
  literal array, so P11 added ONE, exactly as P7 gave `pb_payhub` (R73), P8
  `pb_home_hub` (R83) and P9 `pb_insights_hub` (R96) — here over CATEGORIES
  rather than lenses, because that is the unit this hub is made of:
  `SETTINGS_CATEGORIES = "pb_settings_category"`, `extraCategories()`, and an
  `allCategories()` that **every rule in the file then reads** (the gate pass,
  the card filter and the action probe all had to move off `CATEGORIES` — a
  bolted-on category gated against the literal array renders UNGATED, and group
  resolution fails open by design so nothing about that is visible at runtime).
  JS ONLY, no manifest bump, and the seam is now enforced by
  `pb_settings/tests/test_settings.py::TestSoftCategoryRegistry`. The eight
  shipped categories carry no sequence, so bolted-on ones start at 20 — P11 took
  **Vendors 20, Access & delegation 30**. Each has exactly ONE card, so the
  hub's own `soleCard` rule opens it directly instead of drawing a section page
  whose only content is that door.
- **R120 — the catalogue is a HOOK, not a data file, and that is what keeps the
  dependency list honest.** Every role profile points at a group owned by a
  different module; a `<record ref="pb_pip.group_pip_head">` would make `pb_pip`
  a hard dependency of a module about suppliers. The hook resolves each xmlid,
  SKIPS the ones this database has never heard of, and says which in the log —
  R107's "ensure by name, do not seed a record whose partner may not exist",
  reached from the dependency side. One direction it must NOT fail in: a
  RESTRICTED row whose gate group is missing is **not offered at all**, never
  shown to everybody.
- **R121 — the delegation snapshot must be MEASURED, not predicted, and that is
  the whole security design.** `applied_group_ids` is
  `after − before` read back off `res.users.group_ids` (with an
  `invalidate_recordset` between, or the second read is the cached first).
  Predicting it from the profiles is wrong in both directions: it over-removes
  (a borrower who already held the group in their own right loses it
  permanently because a two-week loan ended — proven live: snapshot `[]`, job
  reported "nothing needed taking back", they kept it) and it under-describes
  (edit the profile mid-window and the end takes back something the start never
  gave). Odoo materialises only the DIRECT group on write; the implied tier
  rides along in `all_group_ids` and leaves again with it.
- **R122 — ⌘K blocks after P10.** P11 took the **3200** block (va_vendors 3200,
  va_access 3210, va_delegate 3220, va_history 3230, va_roles 3240). A P12 would
  start at **3300**.
- **R123 — the P11 test cast and what was put back.** Vendors **11** (RIZE P11
  Talent Partners, owner uid 2326) and **12** (RIZE P11 Cloudline Software,
  owner uid 2333); agreements 17–20 plus the renewal; one attachment. Six
  `pb.access.delegation` rows, all closed. **Every group membership this phase
  touched was reverted** — `rize.p4.boss@example.com` was given the vendor-owner
  and equipment-manager groups for T4/T7 and both were taken back, and
  `rize.p9.plain@example.com` ended holding exactly the one group it started
  with. Verified against a snapshot taken before the first write; all four test
  users read identical to before P11. Records themselves are left in place
  per D9. Passwords re-set to the ledger's values (R74's drift): `RizeP4!2026`,
  `RizeP6!2026`, `RizeP8!2026`, `RizeP9!2026`.
- **R124 — never put `&` (or any XML-special char) in a `res.groups.privilege`
  or `ir.module.category` name.** Odoo 19 assembles the res.users form's
  access-rights arch by embedding privilege names into `<group string="…">`
  WITHOUT escaping, so `Pay Packages & Awards` (P7) and `Vendors & Access`
  (P11) made the arch unparseable — opening ANY user from Settings → Users
  died in an OwlError dialog ("An error occured while parsing … [object
  HTMLCollection]"). Found live 2026-09-01 when the owner tried to change
  their own password. Fix: renamed both to "and" (commit 20101c48) in XML +
  live DB (`res_groups_privilege` 58/61 and the two `ir_module_category`
  rows, jsonb `{"en_US": …}`), files rsynced; **a service restart is
  required** — the generated arch is cached in the running registry, so the
  SQL rename alone still crashes until restart. Verify with
  `SELECT id,name FROM res_groups_privilege WHERE name::text LIKE '%&%'`
  (must be zero rows) and by opening a user form.
- **R125 — a hand-built `ir.actions.act_window` dict MUST carry `views`.**
  `_preprocessAction` (web/static/src/webclient/actions/action_service.js:442)
  runs `action.views.map(...)` unconditionally for act_window, and the
  ORM-computed `views` field exists only on real `ir.actions.act_window`
  RECORDS — a dict returned from a facade RPC and passed to `doAction` has
  `view_mode` but no `views`, so the client throws `TypeError: Cannot read
  properties of undefined (reading 'map')`, which the theme's error handler
  shows as the generic "Something went wrong on our side" dialog with NO
  useful console line (the message only appears if you attach an
  `unhandledrejection` listener before clicking). Every cockpit "open this
  record" door was affected; found 2026-09-01 on Lifecycle → Probation →
  card → **Open the review**. Fix = add `'views': [[False, 'form']]`
  (mirroring each `view_mode`) — done for 22 dicts in the RIZE modules plus 5
  pre-existing cockpit-reachable ones (pb_payruns journals/payments,
  pb_young_worker rules, pb_hr_payroll_base dashboard + import wizard);
  commit 9564a8a7, Python-only (rsync + restart, no `-u`). **Regression gate:
  an AST sweep** — walk every `pb_*/**/*.py`, flag any Dict literal whose
  `type` is `ir.actions.act_window` and which lacks `views` when its
  enclosing function name appears in any `.js` — must report zero.
- **R126 — the rail must survive a drill-down; judge the STACK, not the
  action.** `PbSidebar._resolveVisibility` only asked whether the CURRENT
  action was ours, which every cockpit drill-down fails: `pb.probation.review`
  is dotted (the `pb_` prefix test missed it) and `hr.contract` / `hr.employee`
  / `pb.hr.letter` are not ours by name at all. So "Open the review" / "Their
  record" replaced the Payobook rail with Odoo's native app menu mid-click —
  the product changing its own chrome inside one journey. Fix (commit
  95398c4f): `isPb()` also accepts `pb.`, and new `_openedFromOurs()` reads
  `window.location.pathname` — Odoo 19 keeps the WHOLE stack in the path
  (`/bizapp/pb_probation_board/pb.probation.review/4`) — showing the rail when
  any ANCESTOR segment is a rail-claimed tag/xmlid/model. URL over remembered
  state: survives refresh + pasted links, self-clears on app change. Trailing
  segment excluded so a bare `/bizapp/hr.contract/1` gets no rail. **Any new
  cockpit that opens records needs nothing extra — the path carries it.**
- **R127 — a monetary field needs BOTH a matched inset and enough width, or
  the currency symbol prints on the number.** The widget draws the symbol in
  an absolutely positioned overlay: an invisible ghost copy of the value, then
  the symbol right after it. It reads correctly only while (a) the overlay and
  the input share their horizontal padding and (b) the field is wide enough
  for value + symbol — the ghost carries `max-width:100%`, so a too-narrow
  field CLAMPS it and the symbol lands mid-number. Both failed here:
  `vu-form` gave inputs an 11px inset and left the overlay on Odoo's 8px (3px
  drift), and Odoo's `o_hr_narrow_field` caps the contract wage at 128px —
  fine for `5,000.00`, hopeless for `12,200,000 ₫`, which rendered `12,200,00₫`.
  Fixed in `vu_form_engine.scss` (overlay re-pinned to 11px) and
  `backend.scss` (`o_hr_narrow_field` cap lifted, 9.5rem floor, host
  `.o_row.mw-50` released so `/ month` does not wrap). **VND/IDR/KHR-sized
  amounts are this product's norm — never trust a width tuned for two decimal
  places.** Asset change: purge `ir_attachment` `/web/assets/%` + restart.
