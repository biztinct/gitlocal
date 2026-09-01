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
