# RECRUIT Programme Ledger — conventions, gotchas, rulings, phase log

Every RECRUIT phase handover references this file. Read it FULLY before coding, and
append to it (never rewrite history) whenever you hit a gotcha worth recording — that
is part of the phase deliverable.

Programme: rebuild Payobook Hiring to Rize's ATS requirements. The owner approved the
gap register `docs/design/rize-recruit-gap.html` (lines G-01…G-58, rulings R1–R12) on
2026-09-30 and the phased workflow (Fable designs → Opus implements + tests in the same
session; no Fable bulk code review — the phase REPORT is what Fable reads). The UX design
every phase builds to is `docs/design/rize-hiring-experience.html` (the "blueprint").
Phase handovers: `docs/handovers/recruit/RECRUIT_P<n>_*.md`.

## Inherited rules (apply verbatim)

`docs/handovers/RIZE_LEDGER.md` sections **"Binding rules"**, **"Deploy ritual"**,
**"Odoo 19 gotchas"** and **"Platform contract for new modules"** apply to every RECRUIT
phase exactly as written there. In particular: white-label (never the word "Odoo" in a
user-visible string), plain-English UI, ONE addons directory, never `rsync --delete`
against the addons root, never deploy vendored standard addons, commit per feature with
explicit staging and no push, Lucide icons via the single `ic()` registry in
`pb_import_kit/static/src/js/import_icons.js`, demo data named DEMO and registered with
`pb.demo.seed`, translations need the three comment lines per `.po` entry.

## The design bar (owner's words — verbatim in every handover, scored in every report)

> "exceptional premium, extreme WOW, a novice can work without training" (2026-09-30), on
> top of the standing bar "extreme WOW, intuitive, out-of-this-world experience, best in
> class": a named **hero moment**; **zero dead-ends** (every state — empty, loading, error,
> partial, huge — designed, every failure names its reason and its next step);
> **plain-language over code vocabulary**; **motion with purpose**; **keyboard + bulk
> ergonomics** wherever rows exist; measured against the best SaaS tool in the category,
> never against stock Odoo. Legacy surfaces a build touches get upgraded, never left
> stock. Validate in Chrome (light AND dark) and read the console before reporting done.

## Owner rulings (RC-D)

- **RC-D1 (2026-09-30)** Only Recruiters and the Talent lead move candidates between
  stages. Line managers (the person who raised the request / reporting manager) see the
  board for their roles, leave notes and fill scorecards, but cannot drag. A set-up
  switch may widen this later; ship it OFF.
- **RC-D2 (2026-09-30)** Rize's vocabulary is the PRODUCT DEFAULT for every client:
  stage set, first-look outcomes, and the role tier rename "Hiring manager" → **"Talent
  lead"** (tiers: Recruiter / Talent lead / Head of hiring). Each client can rename stages
  in Hiring set-up.
- **RC-D8 (2026-09-30, owner)** The stage formerly named "Recruiter phone screen" is
  called **"Recruiter review"** (key `phone` stays). Any document or string that still says
  "phone screen" is wrong; fix it on sight.
- **RC-D3 (2026-09-30)** Google Calendar + Meet is built in phase 5 and tested with our
  own Google account; Rize's admin authorises on their side later.
- **RC-D4 (2026-09-30)** Deploy scope = `payobook` (demo data only, OK to test there),
  `rize` (NOT in production; pb_hiring is NOT installed there yet — first deploy is an
  INSTALL), `payobook_template` (must carry every feature so it can be cloned for any new
  client). **NOT `abm`** (being decommissioned).
- **RC-D5 (from the call, R1)** Exactly ONE hard gate in the whole flow: no offer is sent
  unless the role's hiring request is agreed. Every other sign-off is record + notify.
  Reasons are offered, never demanded.
- **RC-D6 (2026-09-30, Fable)** "Role" on the board stays the `pb.hiring.requisition`
  record (one record = one role). Phase 3 adds a "request facet" (a role can exist with
  request_state = none / asked / sent in / agreed) rather than making `hr.job` the row.
  Phase 1 must not hard-code anything that assumes a role always has an agreed request
  before it can show candidates.
- **RC-D7 (2026-09-30, Fable)** Demo candidates on `payobook` carry ordinary Vietnamese /
  Indonesian person names (no customer name anywhere), emails `demo.cand.<n>@example.com`,
  and are registered with `pb.demo.seed` under one label per phase. The "DEMO" prefix rule
  (RIZE_LEDGER rule 9) protects the customer's name; a plain person name leaks nothing.
  Job/role titles, departments and notes must still never contain "Rize".

## Targets & logins

- Server ssh alias `Payobook19v2`, Odoo 19 CE, service `odoo-server`, config
  `/etc/odoo-server.conf`, log `/var/log/odoo/odoo-server.log`, passwordless sudo.
- Databases: `payobook` (https://payobook.com), `rize` (tenant, not in production),
  `payobook_template` (golden template). Backups dir `/odoo/backups/<date>-recruit-p<n>/`,
  written from root: `sudo -u postgres pg_dump -Fc <db> > /odoo/backups/.../<db>.dump`.
- Browser validation on payobook.com:
  - `demo.recruiter@example.com` / `RizeW2!2026` — Recruiter tier (uid 4446).
  - `demo.talentlead@example.com` / `RizeR1!2026` — Talent lead tier (P1 creates it,
    registered with pb.demo.seed).
  - `demo.hiringmanager@example.com` / `RizeR1!2026` — a line manager who raised a demo
    request, NO hiring group (P1 creates it) — used to prove "cannot drag".
  - QA login for post-deploy checks: see memory `payobook-qa-login` (qa.test@payobook.com).
- ⌘K palette block for RECRUIT: **4000–4099** (3500 block is taken by wave 2 Hiring).

## Gotchas found before phase 1 (do not rediscover)

- **RC1** `togglePanel` is defined TWICE in `pb_hiring/static/src/js/hiring_board.js`
  (:801 add/remove a panel member; :1006 open/close an accordion). The later wins, so the
  panel-picker buttons at `hiring_board.xml:1163` and `:1169` call the accordion. Rename the
  accordion one (`toggleSection`) when you touch the file.
- **RC2** The board's four step chips (request / publish / recruit / joined) track the
  ROLE's request state (`stageOf(r)` js:328), not candidate stages. Candidate stages live
  on `hr.recruitment.stage.pb_key` (`journey.py:11-21`, 15 keys, OUTCOMES at :21).
- **RC3** `get_requisition` candidate rows (`pb_hiring.py:518-560`) carry `stage` (name),
  `stage_seq` — NO `stage_id` and NO `pb_key`. A drag board needs the key; add it.
- **RC4** Stage lookups are inline `search([('pb_key','=',key)], limit=1)` in six places
  (`journey.py` :94 :112 :116 :125 :137 :144 :336). Add one `_stage(key)` helper and use it.
- **RC5** `hr.recruitment.stage` has NO `active` field (`hr_recruitment/models/
  hr_recruitment_stage.py`). Retiring the six stock stages = move their applicants to the
  mapped pb stage, clear `template_id`, then `unlink()`; `-u hr_recruitment` may re-create
  them (noupdate data with a missing xmlid), so the retirement must be IDEMPOTENT and run
  from pb_hiring's seed on every upgrade (dependency order guarantees pb_hiring runs after).
- **RC6** `pb_hiring` does NOT use the kit's `QuietGlance`/`QuietSteps`; it has its own
  `.pbhr-glance` / `.pbhr-steps4` markup (`hiring.scss:977-1068`). Example kit call site:
  `pb_onboarding/static/src/xml/onboarding_board.xml:69-82`. Kit t-call params are
  q-prefixed (`qGlance`, `qSteps`, `qStepPick`) — a plain `t-set="glance"` crashes when the
  component has a `glance` getter.
- **RC7** `ic()` falls back to `IC.check` for an unknown icon name (not a blank) — a wrong
  name draws a tick. 142 icons exist; add missing Lucide paths to `IC` only.
- **RC8** Drag precedent: vendored `web/static/src/core/utils/sortable_owl.js:13` exports
  `useSortable` (the stock kanban uses it at `web/static/src/views/kanban/kanban_renderer.js:100-141`
  with `elements`, `groups`, `connectGroups`, `onDrop`). Custom boards elsewhere use raw
  HTML5 DnD (`pb_scheme_map`, `pb_formula_studio`). Prefer `useSortable`.
- **RC9** The stock "New" stage carries the "Application Acknowledgement" mail template
  (`hr_recruitment/data/hr_recruitment_data.xml:44-46`) and fires through `_track_template`
  (`hr_applicant.py:875-889`) unless context `just_moved`. pb stages carry no template.
- **RC10** Stock `hr.applicant.write` (:650-671) already maintains `date_last_stage_update`,
  `last_stage_id`, `kanban_state` reset and `no_of_recruitment` on hired moves — do not
  duplicate that in pb code.
- **RC11** Lens `probe: {model, method}` (pb_hub `hub_shell.js:67-88`, gates in
  `hub_gates.js:35-60`) hides a hub tab unless the `@api.model` call is truthy; pb_hiring
  uses `pb.hiring.can_open`. A group change made via `odoo-bin shell` is not seen by the
  running server until `insert into orm_signaling_default default values; insert into
  orm_signaling_groups default values;`.
- **RC12** Access-screen roles are a fixed catalogue in `pb_vendor_access/hooks.py`
  (`CATALOGUE` rows :142/:147/:151 for hiring, group map :431-433). Renaming a role =
  change the row label + `catalogue_vi.py` entry + a migration calling `ensure_catalogue(env)`
  (pattern: `pb_vendor_access/migrations/19.0.1.10.0/post-migrate.py`) + bump the manifest.
- **RC13** Any act_window dict a facade returns to `doAction` MUST include
  `'views': [[False, 'form']]` or the web client throws "reading 'map'".
- **RC14** Asset changes on the live box: purge `/web/assets/%` attachments AND bump
  `web.assets.version` AND `INSERT INTO orm_signaling_assets DEFAULT VALUES` per DB, or
  browsers keep the old bundle for up to two days.
- **RC15** Menu hiding: set `active` to False on the stock `ir.ui.menu` via a data record
  (`<record id="hr_recruitment.menu_hr_recruitment_root" model="ir.ui.menu"><field
  name="active" eval="False"/></record>`), never delete. Stock ids:
  `hr_recruitment.menu_hr_recruitment_root` (+ children `menu_crm_case_categ0_act_job`,
  `menu_hr_job_position`, `menu_hr_job_position_interviewer`, `menu_hr_talent_pools`,
  `menu_crm_case_categ_all_app`, `menu_hr_recruitment_configuration`) and
  `website_hr_recruitment.menu_job_pages`.

## Gotchas found in phase 1 (2026-09-30)

- **RC16** `journey_options` read `pb.hiring.message.template` AS THE USER, and only
  hiring groups have read on it — so for a line manager (no hiring group) the board's
  load threw, the catch set `allowed=false`, and the one person the read-only board is
  for saw "Hiring is looked after by the hiring team". R158's class again: every read a
  board makes for somebody without the groups needs its own sudo/probe. Fixed (sudo;
  only field names leave the method) and pinned by `test_rc16_*`.
- **RC17** Stock `hr.applicant.copy_data` appends " (copy)" to `partner_name` unless the
  context carries `no_copy_in_partner_name`. "Fit for other role" copies the SAME person
  onto another role, so it passes the flag.
- **RC18** Stock `hr.applicant.write` sets `last_stage_id` from the LAST record of a
  multi-record write. Bulk moves write one applicant at a time (also needed for the
  per-applicant `from_key` Undo returns).
- **RC19** The web client's hotkey handling sees Escape before a plain `window` keydown
  listener: the drawer never closed on Esc. Listen with `{capture: true}` and
  `stopPropagation()` only when the board actually consumed the key.
- **RC20** An inline rename that saves on Enter AND on blur saves twice: Enter removes the
  input, which fires blur, and the second call reads a stale "old" name — so its Undo
  "restored" the new name. Guard on `state.editing === st.id`. (Found live; the stage was
  put back by hand on payobook the same minute.)
- **RC21** On a role with eleven working columns the Closed rail is a long horizontal
  scroll from the card being dragged; `useSortable` edge-scrolls, but a drop target you
  cannot see is a dead end. The rail is `position: sticky; right: 0` on the board.
- **RC22** Rehearsing on a clone WITHOUT touching the live addons: run odoo-bin with
  `--addons-path=/tmp/p1_addons,/odoo/odoo-server/addons` (first path wins — the shadowing
  trap working for us). Tests that read a sibling module by relative path
  (`../pb_import_kit/...`) need that sibling symlinked into the first path too.
- **RC23** Restoring a clone: postgres cannot read `/odoo/backups/` (odoo-owned) — pipe it:
  `cat x.dump | sudo -u postgres pg_restore --no-owner --role=odoo -d clone`. The LIVE
  server's cron threads connect to every database, so the clone runs live crons at once
  (disable `ir_cron` and `ir_mail_server` straight after the restore) and `dropdb` needs
  `--force`.
- **RC24** `odoo-bin shell` reads stdin as an interactive console: a multi-line script with
  functions breaks on dedent. Feed it one line: `echo 'exec(open("/tmp/x.py").read())'`.
- **RC25** The Lifecycle rail item is gated on `hr.group_hr_user`, so a Talent lead or a
  line manager without HR-officer rights has no rail door to Hiring. They arrive by ⌘K
  ("Who we are hiring", "Hiring set-up") or the direct link
  `/bizapp/action-pb_hiring.action_pb_hiring_board`. The Hiring lens itself now admits
  `base.group_user` and lets the `can_open` probe decide. Owner item (P3's email link to
  the manager's page is the real door).
- **RC26** `pb_hiring` was ALREADY INSTALLED on `rize` (19.0.1.3.5), contrary to RC-D4's
  note; P1 was an upgrade there. The six stock stages were retired on all three databases
  (payobook moved 45 candidates, rize and the template none).
- **RC27** The Chrome MCP profile can be locked by a parallel session ("browser is already
  running", isolatedContext too). A headless `puppeteer-core` harness against the installed
  Chrome works for real pointer drags (`npm install --cache ./npmcache` — the global npm
  cache is not writable); never wait for `networkidle` on this web client (the bus keeps a
  connection open) — wait for `load` plus a selector.
- **RC28** ⌘K and set-up numbers after P1: `hiring_setup` **4000** ("Hiring set-up"); the
  Settings "Hiring" category now opens with the Hiring set-up card and is offered to the
  Talent lead as well as the Head of hiring.

## Gotchas found in phase 2 (2026-09-30)

- **RC29** Install a language AFTER `-u pb_hiring`, never before. The new code adds
  `ir.attachment.pb_form_key`; any registry loaded with the new code before the column
  exists fails on the first attachment read (`lang_install` reads the language flags,
  which are attachments). Order per DB: `-u pb_hiring` → `/tmp/p2_lang.py` through
  `odoo-bin shell` (installs `id_ID` with the `base.language.install` wizard + its
  `website_ids`, adds `vi_VN` + `id_ID` to every website, then re-runs `seed_forms`).
- **RC30** `update_field_translations` RAISES for a language that is not active. Every seed
  filters to installed languages, so a language installed later gets its seeded words from
  the next `-u` (or `seed_forms(env)`), never by hand.
- **RC31** "Missing translation" = the language has NO KEY in the raw JSONB column, never
  "equals English" ("CV" is "CV" in all three). `_raw()` in `forms_p2.py` reads the column.
  Role copies are made by copying the raw JSONB (`_copy_raw`), so no language is lost.
- **RC32** An OWL handler may not contain statements: `t-on-keydown="(ev) => { if (...) {...} }"`
  compiles `if` as a variable, the WHOLE template fails ("Unexpected token '{'") and the
  action shows the generic "Something went wrong". Put it in a method. Recipe that catches
  it before a deploy: load `@odoo/owl` (npm) into a headless page and call
  `new owl.App(owl.Component, {templates}).getTemplate(name)` for every `t-name`
  (scratch `owlcheck.js` pattern; ~2 s).
- **RC33** A client's website floats its own header over the page (payobook.com does): a
  `position: sticky` bar inside the public page slides under it. The apply page keeps its
  progress line non-sticky.
- **RC34** Public-page styles avoid `:has()` (Sass-compiler and old-browser risk); the page
  script toggles `.is-checked` on the chosen rows instead. `.pb-apply` colours are custom
  properties (`--pba-*`), and `.rz-site .pb-apply` re-tints them from pb_hiring's own
  stylesheet, so `rize_website` did not change.
- **RC35** Never greet a candidate with `name.split(' ')[0]`: in Vietnamese the first word is
  the FAMILY name ("Cảm ơn bạn, Phạm." — caught live). The thank-you uses the full name. The
  "Application received" email's `{{first_name}}` token still splits (owner item, P8).
- **RC36** Headless checks: the payobook login form fades in (wait for `visible`); the public
  page's script arrives deferred (wait for `form.pba-form[data-pba-ready]` before testing
  its client-side checks — a click before that is a plain HTML submit, which the server
  still refuses); an element below the fold of an inner scroll pane must be scrolled into
  view before a pointer drag.
- **RC37** With `vi_VN` + `id_ID` on the website, payobook.com and the rize site now carry a
  language switcher and `/vi/…` `/id/…` URLs everywhere, and `website.auto_redirect_lang`
  (on) sends a visitor whose browser prefers Vietnamese/Indonesian to those URLs (marketing
  pages are not translated). Owner item; switch `auto_redirect_lang` off if unwanted.
- **RC38** The role's market picks the first language only when there is no `frontend_lang`
  cookie, the page is in the website's default language, and that language is both on the
  website and offered by the form (`COUNTRY_LANG`: VN → vi_VN, ID → id_ID); query string
  (utm_*) is kept on the redirect.
- **RC39** P1 quirk seen, not fixed: a card says "Applied yesterday" for an application made
  after 17:00 UTC (P1's `_card` compares the UTC create date with the user's today).
- **RC40** ⌘K and doors after P2: `hiring_forms` **4010** ("Application forms"); the Settings
  "Hiring" category gains an "Application forms" card; the Hiring set-up "Application forms"
  card opens `pb_hiring.action_pb_hiring_forms`; a role's Details → "Advert & publishing"
  shows "Application form: … · Change · Preview · Edit".

## Gotchas found in phase 3 (2026-10-01)

- **RC41** A record inside a `<data noupdate="1">` block is NOT reloaded on `-u` even when
  its `ir_model_data.noupdate` is flipped to false first — the loader honours the FILE's
  flag. A noupdate record whose meaning changes (P3: `rule_requisition_own`, the two "a role
  is yours to recruit" emails) is written by the post-migration from the module's own data
  file (`post-10_request_facet._noupdate_records`, lxml), and only where it still carries the
  product's old words.
- **RC42** `biz_approval_workflow.chain_shim.register_chain(..., state_field=...)` (the one
  P3 kwarg, default `'state'`): the route can drive a field other than `state`. The chain
  mixin's write token only guards `state`, so `pb_hiring` guards `request_state` itself:
  **system-only writes** (`env.su`). The engine's `biz_chain_engine_write` context flag is
  NOT accepted — a browser can send any context key.
- **RC43** `fields.Html(translate=True)` is TERM-based on this build:
  `update_field_translations('body', {lang: '<html>'})` dies with "'str' object is not a
  mapping". Pass `{lang: {en_term: lang_term}}`; the JD template seed pairs
  `field.get_trans_terms()` of the two languages in order (same `_body()` shape).
- **RC44** Creating a company lays approval routes AND gives `hr_lead` to the publisher
  (Mitchell Admin) at once. A test that needs its own Head of HR re-points that
  responsibility; creating a second one trips the overlap constraint.
- **RC45** `payobook` company 5 (the demo company) and `rize` have the hiring request bound
  to **"No approval needed"** (owner, uid 2, 2026-09-23). There, Send in = agreed at once.
  The migration re-publishes the "Hiring request" workflows but never touches a fast lane.
  To show the Head of HR step in a browser on payobook, swap bindings 11940→171 and the
  company-5 `hr_lead` seat (id 22, normally `demo.a3.an`, a portal user) for a few minutes,
  then put both back (done 2026-10-01, rollback script `/tmp/p3_swap.sh off`).
- **RC46** `pb.hiring.bgv` has no `mail.activity` mixin — a to-do about a check is scheduled
  on the ROLE (`activity_schedule` on the bgv raises AttributeError, swallowed by `leg`).
- **RC47** Three P1/P2 tests fail on **payobook's own data with the old code too** (proved
  on an untouched clone running 19.0.2.1.0): `test_01_the_seed_makes_the_17_stages`
  (somebody reordered stages on payobook, sequence 1120 ≠ 120),
  `TestRecruitApplyPage.test_06` (payobook's Tech roles form has two fields with the same key
  → "Expected singleton") and `test_08_09` (the page refuses the full application on that
  form). All pass on rize. Left as they are: the tests assume the product's seed, payobook is
  a demo world people edit. Run the suite on a rize clone for the clean baseline.
- **RC48** A board read that goes through the approval engine reads AS THE SYSTEM: the reader
  may read the role without being allowed to open an old sign-off on it
  (`pb.hiring._waiting`, `_agree_holders_names`). Found live: "could not read the sign-off
  state" on every older role for the recruiter.
- **RC49** QWeb on a public page and mail templates call no private method (`_x()`): pass
  values from the controller; mail links are public computed fields (`pb_request_url`,
  `pb_share_url`) on the record.
- **RC50** Deploy hygiene seen this phase: `service odoo-server stop` can leave the old
  master alive for >5 s — wait on its PID before `-u`. A staging dir chowned to `odoo` makes
  the next `rsync` fail (`chown -R ubuntu` first). `-u pb_hiring` re-activates pb_hiring's own
  crons on a clone, and the live server's cron threads then race the test run ("could not
  serialize access") — switch crons off again after every `-u` on a clone. `pkill -f` over
  ssh matches its own shell.
- **RC51** The `hiring_jd` catalogue row has no `active` field: it is retired by switching
  its bindings off and `covered_by_key='hiring_request'` (reads "covered", not "not
  connected"). An advert waiting in an inbox was withdrawn on payobook (1).
- **RC52** Doors and numbers after P3: no ⌘K row added. The set-up "Who does what" card is
  now inline on Hiring set-up (`.pbhr-su-who`); `pb_hiring.sender`,
  `pb_hiring.ask_escalate_days` (3), `pb_hiring.docreq_trigger` (on_check_clear),
  `pb_hiring.referral_announce` (1) are the new parameters; `res.company.pb_budget_flag_user_ids`
  the budget watchers. Token routes: `/hiring/r/<token>` (+ `/save` JSON, `/file`, `/send`),
  `/hiring/j/<token>` (+ `/comment`).

## Gotchas found in phase 4 (2026-10-01)

- **RC53** `pb.hiring.country.rule.recruiter_id` is REQUIRED, so retention cannot live on
  that table (a market could not get its months without naming a recruiter). Retention is
  its own table `pb.hiring.retention.rule` (company, country, months, purge_mode, note);
  `res.company.pb_retention_months` stays the fallback. `_months_for(company, country)` is
  the one lookup (the consent sentence uses it too: the role's market).
- **RC54** Field `groups` on a stored compute is safe (computes run as the system), but EVERY
  non-sudo read of the field by a user outside the group raises — the approval route's
  `_chain_revision_values` re-reads offer lines as the LAST approver (a Head of HR / Finance
  seat with no hiring group). It now reads `self.sudo()`. The inbox's `_record_of` is
  already sudo, so `_approval_detail` keeps showing amounts to a seat.
- **RC55** `_offer_row` is now called with `offer.sudo()` and masks after: the native money
  fields carry `groups=pb_hiring.group_hiring_user`, so the old non-sudo read would have
  emptied the line manager's whole offer list through `_safe`.
- **RC56** Requisition BUDGET fields deliberately carry NO field `groups`: the in-app "Raise
  a hiring request" wizard and the manager's request page write `budget_cost` as the line
  manager. Budget is masked in every payload instead (`_mask_money_row`), and the Request
  section shows the figures only to the hiring team and the request's own writer
  (`requested_by_user_id` / `asked_user_id`).
- **RC57** `requested_by_user_id` is a stored compute on `requested_by_id` only: giving the
  employee a login AFTER the role exists leaves it False (record rules on offers/stage logs
  then miss the manager). Tests that link a login late must recompute it
  (`env.add_to_compute` + `_recompute_recordset`). Real roles: the login exists first.
- **RC58** A file a reader outside the hiring team may open is served as
  `/web/content/<id>?access_token=<t>` (per-attachment token, `generate_access_token()`);
  without the token they get 404 (no read on the candidate). Taking a FILE part away from
  anybody regenerates the token of every tokened file on that candidate — other sharers get
  the fresh link on their next drawer load. The hiring team's own links carry no token.
- **RC59** The rehearsal staging dir: after `chown -R odoo` a plain `rsync` into it fails
  half-way and the next test run silently uses the OLD files; and the `.done` sentinel
  written by root cannot be removed by `ubuntu`, so a wait loop returns at once on the
  previous run's result. Stage to a ubuntu-owned dir and `sudo rsync` across; `sudo rm` the
  sentinel (scratch `p4sync.sh` pattern).
- **RC60** The Chrome MCP profile was locked again (RC27); the P4 walk ran headless
  puppeteer-core against the installed Chrome. First page load after an asset purge took
  >60 s on payobook.com — give `waitForSelector` 180 s.
- **RC61** Doors and numbers after P4: ⌘K **4020** "Resume bank" (hub lens `hiring`,
  `focus: "bank"` → `propsFromContext` `startTab`); Hiring set-up gains a seventh card
  `retention` (inline). Params: `pb_hiring.retention_enabled` (0, the nightly leg),
  `pb_hiring.referral_announce` now defaults 0 and was written 0 on all three DBs. Icons
  added to `ic()`: `share2`, `tag`, `hourglass`. New recruiter-screen strings are English
  only (Fable's P4 brief); P4 adds no candidate-facing sentence.

## Phase log

- **P1** (handover `RECRUIT_P1_BOARD.md`) — started and LIVE 2026-09-30: pb_hiring 19.0.2.0.0 +
  pb_vendor_access 19.0.1.11.0 on payobook, rize, payobook_template (backups in
  `/odoo/backups/2026-09-30-recruit-p1/`). 225/225 pb_hiring tests on a rize clone. Demo on
  payobook: role "DEMO Territory Manager" (req 936) + 28 candidates, 4 interviews, logins
  demo.talentlead / demo.hiringmanager, label "RECRUIT P1 board candidates". Gotchas RC16–RC28.
  API left for P2/P3: `journey_stage`, `get_candidate`, `get_timeline`, `get_setup`,
  `role_glance` (see the P1 report).
- **P2** (handover `RECRUIT_P2_FORMS.md`) — LIVE 2026-09-30: pb_hiring 19.0.2.1.0 on payobook,
  rize, payobook_template (backups in `/odoo/backups/2026-09-30-recruit-p2/`); `id_ID`
  installed and `vi_VN` + `id_ID` added to every website on the three DBs. 248/248 pb_hiring
  tests on a rize clone (225 + 23 new). Four templates per company, every role its own copy
  (payobook 14, rize 3). Demo on payobook: role "DEMO Territory Manager" now uses a copy of
  Tech roles (+ "Do you have a motorbike?" in three languages on the Tech roles template),
  its job published, 3 candidates (Võ Ngọc Hân / Vo Ngoc Han — the duplicate pair — and
  Dewi Lestari), label "RECRUIT P2 application-form candidates". Gotchas RC29–RC40.
  API left for P3/P4: `get_forms`, `get_form`, `pb_form_answers`, `pb_consent_on/_text`,
  `pb_lang`, `pb_country_id`, `pb_possible_duplicate_id`, `pb_same_person_id`,
  `res.company.pb_retention_months`.
- **P3** (handover `RECRUIT_P3_REQUESTS.md`) — LIVE 2026-10-01: pb_hiring 19.0.2.2.0 on
  payobook, rize, payobook_template (+ `biz_approval_workflow` code: the `state_field` kwarg,
  no upgrade needed); backups in `/odoo/backups/2026-10-01-recruit-p3/`. Migration rehearsed
  on clones of payobook and rize; 285/285 pb_hiring tests on the rize clone, 282/285 on the
  payobook clone (the three RC47 data failures, also failing on the old code). Website
  browser-language redirect off on all three. Demo on payobook (label "RECRUIT P3 requests"):
  DEMO Field Agronomist (asked of DEMO Hiring Manager, reminded), DEMO Regional Sales Lead
  (sent in over the confirmed budget, agreed via company 5's no-approval lane), DEMO Plant
  Manager (open, confidential), and three DEMO QA roles from the browser walk; company 5's
  budget watcher = DEMO Talent Lead. Gotchas RC41–RC52. API left for P4–P6:
  `request_state`, `requisition._offer_block_reason()` / `pb.hiring._offer_block_reason(req)`,
  `pb.hiring._sender(company)` (+ `res.company.pb_hiring_sender`), `_request_facts()` on
  every row, the token routes above.
- **P4** (handover `RECRUIT_P4_PRIVACY.md`) — LIVE 2026-10-01: pb_hiring 19.0.2.3.0 (+ pb_import_kit
  icons, no version change) on payobook, rize, payobook_template (backups in
  `/odoo/backups/2026-10-01-recruit-p4/`). Rehearsed on a payobook clone: 297/300 (the three RC47
  data failures); 15 new tests. Nightly clean-up OFF and referral announcement OFF on all three.
  `hr_recruitment_skills` already installed on all three (now a dependency). Demo on payobook
  (label "RECRUIT P4 privacy"): three shares with DEMO Hiring Manager on DEMO Territory Manager,
  two recruiter notes (one shared), five Future-fit people with skills + "Keep in touch", one
  past-date candidate (anonymised by the head-of-hiring Run now during the walk), Indonesia 24
  months rule, plus the walk's own records. Gotchas RC53–RC61. API left for P5–P8:
  `pb.hiring.share.parts_for`, `pb.hiring._parts`, `_doc_rows(app, parts, tokenised)`,
  `_regenerate_tokens`, `pb.hiring.note` + `_notes_payload`, `search_bank`/`bank_options`,
  `get_retention_preview`, `hr.applicant._pb_retention_protected()` / `_pb_anonymise()`,
  `pb.hiring.retention.rule._months_for`.
