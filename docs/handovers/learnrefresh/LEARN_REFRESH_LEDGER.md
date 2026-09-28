# LEARN REFRESH — conventions and gotcha ledger

Program: bring everything the owner calls "Learn" up to date with the product as
it is on 2026-09-27 — Learn hub (Lessons / Training / Team / Settings), the
helper ("Ask Payobook" button: Guide me / Ask / Practice tabs), walkthroughs
(scenarios: Watch / Try / Do it live), practice tasks (missions), the practice
company (replica), the welcome tour, glossary, suggested questions, and Ask
Payobook's product knowledge (pb_payroll_ai_insights).

Content was written 2026-08-09/10. Since then the rail went 38 → 8 hubs, pay-run
approval was replaced by the approval engine + one inbox, and ~a dozen areas
shipped. Owner decisions 2026-09-27: **whole app, 5 steps, phased (Fable designs
→ Opus builds, reviews, tests, deploys) back-to-back in one session.**

Inherits: `docs/handovers/PBLEARN_LEDGER.md` and `docs/handovers/LEARNOS_LEDGER.md`
(read their rule lists once; everything below is ADDITIONAL or a correction).
Ledger ids here: **LR1, LR2 …** — append when you hit a new gotcha.

## Steps (program plan)

| Step | Scope | Handover |
|---|---|---|
| 1 | Helper knows every hub tab; every "open the real screen" goes to hub › tab; hub-level orientation for all 9 hubs; Ask Payobook knows hub tab names; anchor registry catches up | `STEP1_HELPER_KNOWS_THE_TABS.md` |
| 2 | Payroll core rewrite: practice company gets the new rail + approval flow; Dashboard→Pulse, Approvals→one inbox, Run Payroll (scheme first), Pay Runs (Draft / Waiting for approval / Done), Payslips, Import ("This run only" vs update records), Formula (studio without Settings panel; New configuration journey); their walkthroughs, missions (m1, m2, mL1), welcome tour, intents, glossary, Ask Payobook product prompt | step 2 file |
| 3 | New lessons, payroll setup: New configuration (Blueprint), Mapping, Component treatment, Approval Matrix, Records Desk, schemes & currencies (+ Group/FX) | step 3 file |
| 4 | New lessons, wider app: People › Pay (bands, review), Decision Room, Lifecycle (Hiring, New joiners, Exits, Probation, Growth plans, Contracts), Workforce (Today, Time, Time Off, Overtime, Close), Access & delegation, Compliance (Filings, Bank, Audit) | step 4 file |
| 5 | Fill the 12 outline-only lessons; role paths + chapters redone over the new station set; Team readiness; final sweep (every station reachable, every anchor alive, VI parity, Ask Payobook suggested questions) | step 5 file |

## Standing rules (bind every step; put them in every agent's head)

- **White-label**: the word "Odoo" never appears in any user-visible string (labels,
  lesson text, glossary, toasts, .po msgstr). Technical identifiers untouched.
- **Plain English** in every lesson line: the words on the SCREEN, not code words.
  No model names, no state keys (`approval_pending`), no xml-ids in lesson copy.
- **Design bar (owner's words, verbatim): "extreme WOW, intuitive, out-of-this-world
  experience, best in class."** Every step must name its hero moment; zero dead-ends
  (every state — empty, loading, error, partial, huge — designed, every failure names
  its reason and next step); plain language over code vocabulary; motion with purpose;
  keyboard + bulk ergonomics where rows are involved; measured against the best
  consumer/SaaS tool in the category. Lucide icons, never emoji. Score the phase
  report against this bar.
- **Bilingual**: every new/changed learner string has EN + VI in data.js. VI must not
  use "trình duyệt" for approval (it means web browser) — the approval vocabulary is
  "phê duyệt"; follow the PBLEARN_LEDGER VI audit rules.
- **Truth over polish**: every number, button label, tab name and state name in a
  lesson must be read from the current code/screen, never from the old lesson.
  "A KPI tile is a query — read the method, not the caption."
- **No credentials in the repo** (public). Logins live in the owner's memory notes;
  never paste a password into a doc, commit or test.
- **Commit per feature**, explicit `git add <paths>` (never `-A`), message ends with
  `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`. Never push.

## Content pipeline (verified — do not re-derive)

- Source of truth: `docs/tutorial_poc/author/data.js` (+ `practice-data.js`).
  Generated: `pb_learn/static/content/learn_content.json`. Never hand-edit the JSON.
- Generate: `python3 docs/tutorial_poc/author/tools/gen_learn_data.py`.
  **LR1 (trap):** the generator OVERWRITES `pb_learn/i18n/vi_VN.po` with a tiny
  version, wiping ~1,000 entries. ALWAYS `git checkout pb_learn/i18n/vi_VN.po`
  right after generating, and add hand-written .po entries only AFTER that restore.
- Gates after generating: `tools/check_contract.py` (6 pre-existing failures from the
  approval-route commit — they are exactly the stale approval content step 2 fixes;
  after step 2 the count must be 0), `tools/jargon.py` (glossary scan),
  `tools/replay_tests.py`, `tools/simulate_resolver.py`, `tools/test_scenario_rules.py`.
- JS chrome strings: `T(key)` reads `chrome` keys; new chrome keys go in data.js
  chrome with en+vi. Language = `RT.lang`.
- **LR2 minifier:** no literal space right after `}` inside a template literal in
  pb_learn JS — use `${SP}`. Tests read the coach source: `COACH_ACTIONS` must list
  every `data-act` the coach emits.
- PO entries need all three: `#. module:<m>`, `#. odoo-javascript` (for JS strings),
  `#: code:addons/<m>/<path>:0`. Parse-gate the .po before deploy.

## Product map as of 2026-09-27 (verified from code; do not re-derive)

Rail: Home (`pb_home_hub`) · OPERATE: Pay Run (`pb_pay_hub`), People (`pb_people_hub`),
Lifecycle (`pb_lifecycle_hub`), Workforce (`pb_workforce`, module pb_mission) ·
UNDERSTAND: Insights (`pb_insights_hub`), Compliance (`pb_compliance_hub`) ·
GROW: Learn (`learn_hub`) · Settings (`pb_settings_hub`, a category page, not lenses).

Lenses (tabs), in order — each hub's own list + registry additions:
- Home: Pulse · Approvals (the one inbox, `pb_approval_config`) · Wall · Announce.
  (Decision Room and Goals were REMOVED from Home on 2026-09-24, commit 5c20a48b0.)
- Pay Run: Run · Runs · Payslips · Results · Import · Deliver · Adjust (tabs Retro,
  Proration) · Settle (tab Full & Final) · Calendar · Awards.
- People: Employees (Contracts is now a button inside Employees + per-row "Contract"
  drawer — commit c9e5f2ee4) · Records · Pay · Where they work · Assets · Praise ·
  Goals · Announce · Plan (Decision Room on top).
- Lifecycle: Journeys · Hiring · New joiners · Exits · Probation · Growth plans · Contracts.
- Workforce (pb_mission; lens context key is `pb_shell_lens`, NOT `pb_lens`): Today ·
  Schedule · Time · Time Off · Overtime · Trips · Approvals (team) · Close · Holidays · Field.
- Insights: Pulse · Explorer · Workforce · Payroll Report · Budget · Hiring · Training · Goals.
- Compliance: Filings · Bank · Young workers · Audit.
- Learn: Lessons · Training · Team · Settings (admins).
- Settings categories: Formula Engine, Salary Structures, Statutory, Integrations
  (+ Mapping), Payroll defaults, Companies & Tenants, Navigation, Your company,
  Vendors, Guided setup → New configuration, Access & delegation, Group, Approvals
  (Approval Matrix, Approvals inbox), Hiring, About Payobook, Announcements, Demo data.
- **Lens visibility**: groups AND (since 5c20a48b0) optional `probe: {model, method}` —
  a tab is hidden unless the server says the user can open it. Never promise a
  learner a tab without the same gate.

Old name → where it lives now: Dashboard → Home › Pulse · Approvals → Home › Approvals ·
Run Payroll → Pay Run › Run · Pay Runs → Pay Run › Runs · Payslips → Pay Run › Payslips ·
Import Data → Pay Run › Import · Full & Final → Pay Run › Settle · Proration / Retro →
Pay Run › Adjust · Employees → People › Employees · Contracts → People › Employees ›
Contracts · Formula Engine → Settings › Formula Engine · Salary Structures → Settings ›
Salary Structures · Statutory → Settings › Statutory · Integrations → Settings ›
Integrations · Insights → Insights › Pulse · Explorer → Insights › Explorer ·
Workforce Analytics → Insights › Workforce · Government Reports → Compliance › Filings.

Pay run approval today: run states `draft → approval_pending → done / cancel`; board
columns **Draft · Waiting for approval · Done**; a draft offers "Submit for approval" /
"Reject"; route comes from the Approval Matrix (seed route "Payroll check → HR lead
review → Finance approval"; a tenant may have 2 steps); a refusal returns the run to
Draft with the reason (NOT "cancels 48 payslips"). Closeout: `docs/handovers/APPROVAL_MATRIX_CLOSEOUT.md`.

## Hub plumbing (verified)

- `pb_hub/static/src/js/hub_shell.js`: `state.lens`, `setLens(key)` (:357), arrival
  from context `pb_lens` / `pb_focus` / `pb_back` (`_arrival` :153), last lens kept in
  localStorage per hub (`hubLensStorageKey(config.key)`).
- `pb_hub/static/src/js/hub_nav.js`: `openHub(actionService, {tag|xmlid, lens,
  lensKey, focus, back})` (:52). `HUB_LENS_KEY = "pb_lens"`.
- `pb_mission/static/src/js/pb_mission.js` is its own shell (`state.lens` :276,
  `setLens` :547) — any "current tab" signal must be published from BOTH shells.
- Hubs mount the old cockpits as lens components with `props.embedded`; the current
  action's tag while inside a hub is the HUB's tag (e.g. `pb_pay_hub`), so matching
  on action tag alone finds nothing.

## Browser checks

- payobook.com (demo world) with the QA login from the owner memory note
  `payobook-qa-login.md` (QA lacks pay-run access — use the demo login from
  `pb-demo-environment.md` for walkthrough checks). One walk on payobook.com; other
  DBs get automated checks. Console must be clean. Check VI too.

## Deploy (see project CLAUDE.md — binding)

- One addons dir `/odoo/odoo-server/addons`; fresh staging dir; per-module scoped
  `rsync -a --delete /tmp/deployX/<m>/ /odoo/odoo-server/addons/<m>/`; NEVER `--delete`
  into the addons root. Never deploy vendored standard addons.
- Upgrade EVERY DB: payobook, payobook_template, abm, rize (abm is retired but still
  gets upgrades; acme no longer exists — check `psql -l` before assuming).
- **LR3:** after a JS asset purge + `web.assets.version` bump the running server still
  served the old bundle until `sudo service odoo-server restart`. Restart.
- Tiered deploy rule: looks-only / normal / risky — say which tier in the report.
- Module tests: `--http-port=8099 --gevent-port=8098 --max-cron-threads=0` on a
  throwaway clone; drop the clone (and its filestore) after. 4 pre-existing pb_learn
  failures at 2026-09-24 (anchor registry 01 and 05 — step 1 fixes these; test_learn_hub
  path artifact; cron inactive on template).

## Gotchas found during this program

- LR1 generator wipes vi_VN.po (above). LR2 minifier `${SP}`. LR3 restart after purge.
- LR4 `.lrn-moment` is the Journey's class; helper moment cards are `.lrn-hmoment`.
- LR5 a group change via `odoo-bin shell` is not seen by the running server until
  `insert into orm_signaling_default default values; insert into orm_signaling_groups default values;`.
- LR6 **"Where am I" is `@pb_hub/js/hub_place` (step 1).** HubShell, pb_mission and pb_settings
  publish `{tag, lens, lenses (already gated), hubLabel, ready}`; `setPlaceSub` for inner tabs
  (Pay Run Adjust/Settle via LedgerCockpit `onTab`), `holdDetail("contract")` for the contract
  drawer. Ownership + `seq`: the next hub mounts BEFORE the old one unmounts, so a clear only
  works for the owner, and a reader that just navigated must wait for `seq` to change (else it
  reads the hub it left). `switchLens(key)` calls the owning shell's own lens switch.
- LR7 **OWL `useEffect` deps are NOT a subscription** — they are computed after render. To
  re-run on a reactive store, READ it during render (coach root `t-att-data-place="placeKey"`).
- LR8 **The Pay Run › Runs lens is `PbPayruns` (payruns.xml), not the kanban** the pk-* anchors
  were written on. Step 1 added pk-kpis / pk-tabs / pk-card to payruns.xml (registry `also`);
  their copy is still the old kanban's ("five numbers") — step 2 rewrites it.
- LR9 **pb_approval is deleted**, so check_contract's anchor-lint used to SKIP silently (a
  missing template file skipped the whole lint). It now lints, and prints retired-anchor uses
  as a warning line (13 uses of 6 retired anchors at end of step 1).
- LR10 Journey arrival deep link: the Lessons lens gets `wantsArrival`; HubShell now hands ONE
  arrival object per hub mount (`_arrivalProp`) and the Journey remembers consumed ones in a
  WeakSet, so tab-hopping does not replay a deep link. Focus grammar: station:/scenario:k:mode/
  lesson:/suggest:/practice. All lesson doors go through `engine/places.js openLearn`.
- LR11 Vietnamese tab labels on screen are weak in places (Run and Runs both "Chạy", Deliver
  "Giao hàng", Explorer "Nhà thám hiểm", Statutory "Biên chế", Companies & Tenants "Người thuê
  nhà"). Hub orientation content matches them (truth over polish); fixing the module .po files
  is an owner-visible item, not a learn-content change.
- LR12 **Journey click delegation checks `[data-station]` BEFORE `[data-act]`**: any button in
  the Journey carrying `data-station` opens that station and its own data-act never runs. Use
  another attribute name (`data-screen`).
- LR13 **Two navigations to one hub race**: `begin()` opens a walkthrough's entry screen while
  the overlay enters step one, whose `nav` is usually the same screen; the superseded doAction
  never resolves. `scenario_service.navigate` now shares one in-flight promise per destination
  and skips navigating when already on that hub tab.
- LR14 HubShell only PATCHES once the new lens's onWillStart finishes, so a place published
  from an effect lags slow lenses by seconds. `setLens` also publishes synchronously (all
  three shells); the effect stays for arrival, restore and access changes.
- LR15 The QA login now HAS pay-run access (Your Company). A no-access walkthrough could not be
  reproduced with it; step 1 verified the blocked card by forcing the reach answer. A real
  no-pay-run user is needed for future no-access checks.

- LR16 **Replica CSS classes collide with the helper's.** `.lrn-drawer` (coach.scss, position:fixed)
  and `.lrn-tl` (journey.scss:743) were already taken; a replica drawn with them floated over the
  page. New replica classes are `lrn-a*` (`lrn-adrawer`, `lrn-atl`). Grep every new class name
  across pb_learn/static/src before using it.
- LR17 **The demo world's pay-run route is "No approval needed"** (payobook, Payobook Vietnam JSC):
  a submitted demo run goes straight to Done. Company "Payobook" (id 2) has "Pay run approval" but
  its seats resolve to nobody (request goes `blocked`). Live approval checks need a temporary
  one-step route inside a rolled-back shell transaction (step 2 did this; zero residue).
- LR18 **The QA login cannot open pay runs** (`hr.payslip.run` access refused) despite LR15; the demo
  login (`pb_demo.group_payobook_demo`) can read them but cannot CREATE a run (account.journal
  read refused). Server-side checks go through `odoo-bin shell` (stop nothing; exit cleanly).
- LR19 **JS/template translations are served straight from the .po files** — deploy + restart is
  enough, no `-u` needed. Only a STORED label (pb.sidebar.item name) needs `-u` (filled when the
  lang key is missing) or `--i18n-overwrite`.
- LR20 `web.assets.version` is a 14-digit timestamp on these DBs — bump it as `bigint`, and never put
  the purge DELETE and the bump in one `psql -c` (one failure rolls back both).
- LR21 A walkthrough can be RETIRED (`retired: true` in data.js): the generator emits the flag, the
  map (journey.js), the Coach offers (scenario_service `forScreen`) and the server
  (`explain_scenario_offer`) skip it; progress rows keep their meaning. sc_mapping is retired.
- LR22 Ask Payobook's classifier sent "who approves my pay run?" to the generic knowledge prompt;
  the onboarding category now names this app's approval questions explicitly.

## Step 2 facts for later steps

- **Station keys unchanged** (progress survives); titles renamed to tab names: dashboard → "Pulse",
  approvals → "Approvals", runpayroll → "Run", payruns → "Runs", import → "Import".
- **New intents:** `whoapproves`, `stuckwaiting`, `sentbackvsturneddown`, `thisrunonly`. `confidence`
  is now "What do the import counts mean?" (there is no score on the pay-data import).
- **Glossary:** retired gate, tier, approvalChain, payrollOfficer; added approvalRoute, routeStep,
  inbox, sentBack, turnedDown, payScheme, payData, thisRunOnly, hub ("Rail"), tab.
- **Anchors added (product):** inbox.xml `ai-head ai-scope ai-tabs ai-card ai-route ai-drawer ai-facts
  ai-decide ai-turndown ai-sendback ai-approve ai-move ai-withdraw`; payruns.xml `pk-run pk-divchips
  pk-steps pk-route pk-card-actions pk-rejected`; promoted `fs-views fs-command`.
  **Practice:** `rep-tabs rep-fs-stage rep-fs-tools rep-settings`. **Retired/removed:** `pa-*`,
  `fs-simulate`, `rep-dash-runs`. `pw-division`, `pk-datechips`, `pk-tabs`, `in-trend` are reserved.
- **Replica:** `MENU` is the 9-hub rail with each hub's lenses (`screen` = replica screen; none =
  quiet tab). New screen `hub_settings`. Fixture exports `FNB`, `ROUTE`, `LATER`. Status keys:
  payrun draft/approval_pending/done/cancel; payslip draft/verify/done/cancel; chains payrun
  (two `branches`), route, formula.
- **Tenant slots** `hrTierName` / `gmTierName` are declared but unused (kept for existing overrides).
- **PayAI** envelope: `open_lesson` or `open_walkthrough` (whitelist `_KNOWN_WALKTHROUGHS`); the chat
  opens a walkthrough as Learn focus `scenario:<key>:watch`.
- **Product fixes shipped:** `_approval_reject` on hr.payslip.run; engine `_approval_withdraw` hook
  (default no-op, called from `engine.cancel`) + pay-run impl (back to Draft).
- **Pre-existing test failures (not step 2):** pb_learn test_07b (cron on template), pb_payroll_ai_insights
  test_data_access_06, test_egress 04d/04e, pb_approval_config test_u10 (res.users access in outbox)
  and test_z06d (pb_formula_studio has no Phase-7 block).

- LR23 **`ct-` is taken by Contracts** (ct-head, ct-filters, ct-kpis, ct-roster in pb_contracts). The
  step 3 handover's `ct-` prefix for Component treatment would have re-pointed two contract anchors;
  treatment anchors are **`tr-*`** (tr-head, tr-filters, tr-table). Check every new prefix against all
  four registry blocks (product, practice, foreign wildcards, pattern) before laying it.
- LR24 **Mapping publishes its tab** (`mapping_studio.js _publishPlace`, hubKey "mapping", lens =
  the mode id, switchTo = setMode). Its lens context key is **`pb_mode`**, so the content declares a
  `hub_mapping` screen with `hub.lens_key: "pb_mode"` — that is what lets `openScreen` open Mapping ON
  a tab (Component treatment = place `pb_mapping_studio:treatment`). The three Settings cockpits
  without tabs (guided setup, Approval Matrix, Group) have no place: they ground by
  `SCREEN_ACTION_TAGS` and open by the screen's `open` xml-id. A Settings category key is NOT a
  usable place for them — `openHub` on pb_settings_hub ignores `pb_lens` and would land on the
  remembered category.
- LR25 A scenario `nav` / `entry.nav` may now be a **screen key** whose screen has `places` or
  `open` (generator `nav_screens`); the engine resolves a key before an xml-id. Used by sc_treatment.
- LR26 Glossary gotchas: the permission-group entry owns the alias **"groups"** (avoid the word in
  prose); every single-word term/alias needs a BARE_ALIASES reason (added `subtotal`); a 29-word
  sentence fails the generator — split, don't trim meaning.
- LR27 **⌘K matches label + sublabel only.** Stations carry a bilingual `search` phrase that the
  Learn palette rows show in the sublabel ("Lesson · 7 min · currency, exchange rate…"), so a
  lesson is found by what it is about. Retired walkthroughs are no longer offered in ⌘K.
- LR28 New lesson moment **`tick`** (`visuals.js runTick`): the replica element named by
  `moment.from` carries `data-from` / `data-to`, and the number counts between them. Used for the
  guided setup's take-home figure (Allowances added: +allowance − tax).
- LR29 Product Vietnamese was machine-grade on the taught setup labels (Pay role "Trả vai trò",
  Tells the run "Kể về cuộc chạy", Scheme "sơ đồ"/"Lược đồ", Continue to pay rules "Tiếp tục trả quy
  tắc"…). Fixed the taught ones in pb_formula_studio / pb_blueprint vi_VN.po (JS/template strings:
  deploy + restart is enough, LR19). **pb_records has no Vietnamese for the Records Desk screen at
  all** — Vietnamese users see English there; the VI lesson names the buttons in Vietnamese. Owner item.
- LR30 **Who can see the setup screens on payobook.com.** The demo login opens the guided setup,
  Mapping, the Records Desk and Group, but NOT Component treatment ("You need payroll officer
  access…"), the Approval Matrix ("could not be opened") or Insights › Explorer (the hub moves it
  off the tab). The QA login opens Approval Matrix, Group and Explorer, but not Mapping (no
  Formula User group: mapping_pickers refuses hr.integration.connector) and not People › Records.
  Step 3 validated treatment by giving QA the Formula User group for the check and removing it
  after. A walkthrough over a screen the reader cannot open degrades to centred cards; stations
  without a sidebar leaf are always "reachable" (learn_runtime `_station_reach`), so nothing
  warns first — a step-5 item.
- LR31 The Ask Payobook model omits the "Show me" action for most plain "how do I…" questions (it
  sent one only when the user wrote "show me"), step 2's included. `_content_handoff` now asks
  pb_learn's resolver (`learn.intent.resolve` → intent `watch`) and offers that walkthrough,
  through the same whitelist. Tests test_action_envelope 16/17.
- LR32 A synthetic Ctrl/Cmd+K keydown does not open the ⌘K palette in Chrome MCP; click the header's
  "Search surfaces and actions" button. Setting the input value needs the native setter + an
  `input` event.

## Step 3 facts for later steps

- **Stations (setup line, chapter 3):** blueprint "New configuration", mapping "Mapping", treatment
  "Component treatment", matrix "Approval Matrix", records "Records Desk", schemes "Schemes and
  currencies". Each has `roles` (officer/hr/approver/owner — step 5 builds paths from it) and a
  bilingual `search` phrase. Lessons **L7–L12** in that order.
- **Replica screens:** blueprint (+ sub blueprint_rules), mapping (+ sub mapping_sheet), treatment,
  matrix (+ sub matrix_builder), records, schemes (Settings › Group). The explorer replica gained
  the money switch + Compare schemes panel. MENU: People › Records, Settings › Guided setup /
  Group / Approvals open replicas; Mapping and treatment live under Integrations (`also`).
- **Walkthroughs:** sc_blueprint, sc_mapjourney (replaces retired sc_mapping), sc_treatment
  (`nav: "treatment"` — a screen key), sc_matrix, sc_records, sc_schemes; all Watch + Try.
- **Intents:** newscheme, wherefrom, notaddup, changeroute, bulkupdate, currency (resolver cases in
  simulate_resolver.py). whoapproves/stuckwaiting now also cover the matrix screen.
- **Glossary:** guidedSetup, startingPoint, sampleEmployee, setupCheck, schemeProposal, dataSource,
  sourcePriority, transformationRule, mappingJourney, componentTreatment, payRole, subtotal,
  valueType, approvalResponsibility, approvalCover, recordsDesk, ratePolicy, groupCurrency;
  approvalRoute and mapping (column mapping) definitions updated.
- **Screens / places:** hub_mapping (tag pb_mapping_studio, lens_key pb_mode); mapping claims every
  Mapping tab except treatment; records = pb_people_hub:records; blueprint / matrix / schemes open by
  `open` and ground by SCREEN_ACTION_TAGS.
- **Anchors (product):** bp-status bp-rail bp-foot bp-pay bp-identity bp-country bp-starters
  bp-audience (bp-reallife reserved); mp-story mp-modes mp-ramp mp-jbar mp-lanes; tr-head tr-filters
  tr-table; am-hero am-tabs am-bulk am-table (am-filters, am-foot reserved); rd-head rd-scheme rd-file
  rd-history rd-review rd-fields (rd-who, rd-empty reserved); gp-head gp-tree gp-rates (gp-divisions
  reserved); ex-money. Contract checks `setup-lesson-anchors`, `setup-cockpit-action-tags`.
- **Ask Payobook:** PAYROLL SETUP block in ONBOARDING_SYSTEM_PROMPT; _KNOWN_LESSONS += L7–L12;
  _KNOWN_WALKTHROUGHS += the six; `_content_handoff` fallback (LR31).
- **Versions after step 3:** pb_learn 19.0.17.1.0, pb_blueprint 19.0.1.11.6, pb_formula_studio
  19.0.1.201.2, pb_approval_config 19.0.1.6.1, pb_records 19.0.1.3.2, pb_group 19.0.2.1.1,
  pb_explorer 19.0.2.5.1, pb_payroll_ai_insights 19.0.3.7.0 — all four databases.
- **Pre-existing test failures (not step 3):** pb_learn test_07b; pb_payroll_ai_insights
  test_data_access_06, test_egress 04d/04e; pb_approval_config test_u10, test_z06d;
  pb_formula_studio test_net_pay_candidates test_01 ("the fixture must have no net pay" — a
  template-data expectation, untouched by this step).

- LR33 **A hub tab's gate is now askable without opening the hub** (`@pb_hub/js/hub_gates`). Each hub
  registers the lens gates its config already declares in registry `pb_hub_lens_gates` (tag → fn returning
  `[{key, groups, probe, feature, hubFeature}]`); HubShell's `_resolveAccess` now calls the same
  `resolveLensAccess`. pb_learn's `places.resolveLensReach` fills `lensReach["tag:lens"]`, `reachable()` reads
  it, and the Journey marks such stations `gated` ("No access in your company" + "you can still read the
  lesson"). Registered: people, lifecycle, compliance, home, workforce (pb_mission). A hub that registers
  nothing stays "unknown", never "no".
- LR34 **A walkthrough whose screen refuses its reader after landing** now ends on the no-access card
  (`scenario_overlay.js refusalOnScreen`): an `.o_error_dialog`, the hub place saying the step's lens is not
  among the reader's tabs, or a refusal sentence (EN/VI regex) inside an alert-like box — checked only while
  the step's anchor is missing, after a 700 ms grace; anchorless intro cards listen for 2.5 s. `sc.refuse()`
  / `sc.screenOfStep()` in the service.
- LR35 **Narrow screens (≤ 900 px) dock the lesson card** as a bottom sheet (`spotlight.js DOCK_BELOW`), scroll
  the anchored control clear above it, and fold to its title line (`data-spot-fold`, its own listener — not a
  data-act, LR12). The real-screen walkthrough card docks the same way (`ui.card.docked`).
- LR36 **Glossary collisions the wider app hit:** `confidenceScore` owned the bare alias "score" (a pay
  review's Score is a performance score) — dropped; `flag`'s definition was payslip-only — widened to
  Workforce › Close; "ceiling" is the INSURANCE ceiling (write "limit" for overtime); "period" is the PAY
  period — `probation` owns "trial period" (longest match wins); `test_explain::test_04` pins `filing` as the
  LAST glossary entry, so new terms go before it.
- LR37 The composer corpus cap moved 36,000 → 44,000 (`learn_intent._CORPUS_CAP`; widest corpus 37,677).
- LR38 **Product Vietnamese on the wider app:** biz_access (Access & delegation) has NO vi_VN.po — the screen is
  English for everyone, so the replica and the VI lesson name its buttons in English (owner item). pb_hiring had
  2 entries; step 4 added the taught labels to pb_hiring / pb_onboarding / pb_offboarding / pb_probation / pb_pip /
  pb_contract_lifecycle (+ pb_tenants "Welcome aboard"). Still weak/global: hiring "Open" (number and button share
  one msgid → "Mở"), "Step X of 4" is built from "Step" + "of" → "Bước 1 của 4", the request wizard's tab names are
  hard-coded English, "Roles"/"Met"/"Done"/"Joined this month" clash across modules; Workforce: Board "Ban",
  Checked out "Đăng xuất", Est. gross "Ước tính. thô thiển", Audit Stream "Truyền phát", Login lens "Ống kính
  đăng nhập"; pb_probation's po has 19 entries the reader drops.
- LR39 FACTS_STEP4 corrections found in code: only Hiring has a Next line (per role card) — the five other
  Lifecycle boards have no Next box; Time Off's head in the hub has only month + Apply on behalf ("File leave"
  is the dialog's submit); the Overtime panel is "Overtime rules & ceilings" and the button is "Bonus Hours";
  "Violations in the last 30 days"; "New bank-change request" is a drop zone; Contracts' choices read Make it
  permanent / Extend it / Let it end; Pay review "Close the review"; Decision Room's Exact cost and Propose
  exist only on saved-plan rows; Growth plans' gate is pb_pip groups only (no admin fallback).
- LR40 `replay_tests` "bridge suite did not run" is pre-existing: `engine/runtime.js` imports `@web/core`
  (LEARN v3), which the node harness cannot resolve. Not a step 4 regression.
- LR41 **The Journey never painted a spotlight on its FIRST render.** `onPatched` runs `_afterPaint`,
  `onMounted` did not — so a Try (or lesson) opened by deep link into a freshly mounted Learn hub showed the
  replica with no card until something re-rendered (pre-existing; seen on sc_records too). `onMounted` now
  calls `_afterPaint()` (which also walks the Lifecycle road).
- LR42 Demo boards are often EMPTY (no pay review, no leavers, no trials on payobook.com), so a Watch step on a
  list or a drawer finds nothing. Lifecycle list anchors (`hi-row`, `nj-list`, `ex2-list`, `pr-list`,
  `gw-list`, `cl-list`) are also laid on each board's "nobody here yet" branch (one renders at a time), and
  drawer / open-review steps are Try-only with a Watch step that says what an open one shows. People › Pay's
  Review tab is opened by pressing it: pattern anchor `pp-tab-<key>` (registry `pattern` block — the
  generator and the contract lint now treat every pattern key as a prefix).
- LR43 The hub canvas scrolls through an `overflow:hidden` ancestor that only `scrollIntoView` moves — a
  manual `scrollTop` found no scroller. The docked card scrolls with `scrollIntoView({block:"start"})` and
  `body.lrn-docked .lrn-screen` gets 55vh of bottom room so the last control can clear the sheet.

## Step 4 facts for later steps

- **Lines:** `lifecycle` and `workforce` added to LINE_ORDER (overview, payrun, people, lifecycle, workforce,
  insights, compliance, setup) and to chapter 2 in journey.js CHAPTERS. Lifecycle draws the hero road
  (journey.js `LIFE_TRAIL` hiring → joiners → probation → exits; walker position per browser in
  `pbLearnLifeTrail`).
- **Stations and lessons (key · line · lesson):** paybands · people · L13; payreview · people · L14 (star);
  decisionroom · people · L15; peoplemore · people · L28 (short); hiring · lifecycle · L16 (star); joiners ·
  lifecycle · L17 (star); probation · lifecycle · L19; growth · lifecycle · L25 (short); contractends ·
  lifecycle · L26 (short); exits · lifecycle · L18 (star); wftoday · workforce · L20; wftime · workforce · L21;
  wfclose · workforce · L22 (star); access · setup · L23 (star); govreports · compliance · L24 (renamed
  "Government filings", now star + full lesson); compliancemore · compliance · L27 (short). All carry `roles`
  and a bilingual `search`.
- **Replica screens:** paybands, payreview (budget meter `rep-pr-budget`, `meter` moment), decisionroom,
  hiring (+ sub `hiring_request`), joiners, probation, growth, contractends, exits, wftoday, wftime, wfclose,
  access (English, like the product), filing_flow (sub of govreports), compliancemore, peoplemore. Classes
  `lrn-y*`. New pipeline chains `review`, `hiring`, `exit`. New icons: briefcase, log-out, key, scale, sliders,
  hourglass, sprout, file-signature, sun, timer, repeat.
- **Screens (helper):** the station keys above plus `wftimeoff`, `wfovertime` (places for those two
  Workforce tabs) and `hiring_request`, `filing_flow`. People › Pay publishes its inner tab
  (`pb_people_hub:pay/bands|fairness|review|changes`). SCREEN_ACTION_TAGS gained the standalone board tags,
  `pb_access_board`, `pb_filing_flow`. Access opens by `biz_access.action_pb_access_board`, the filing flow by
  `pb_govt_reports.action_pb_filing_flow`.
- **Walkthroughs:** sc_paybands, sc_payreview (W+T), sc_decisionroom, sc_hiring (W+T), sc_joiners, sc_exits
  (W+T), sc_probation, sc_wftoday, sc_wftime, sc_wfclose (W+T), sc_access, sc_filings. Watch presses only
  `pp-tab-review` (a tab switch).
- **Intents:** bandcheck, whosignsreview, whatif, raisehire, newjoiner, leaver, endtrial, approveot, lockweek,
  delegate, fileinsurance (resolver cases in simulate_resolver.py).
- **Glossary:** payBand, inTheBand, payReview, calibration, decisionRoom, exactCost, hiringRequest,
  candidateStage, buddy, probation, clearance, growthPlan, needsYou, lockWeek, accessRole ("Role" would collide
  with Hiring's Roles tab), handOver, seeItAs; filing and flag widened; "Final settlement" stays fullFinal's alias.
- **Anchors (product):** pp-* (pay.xml, pay_review.xml; pattern pp-tab-), dr-*, hi-*, nj-*, ex2-*, pr-*, gw-*,
  cl-*, wf-* (pb_mission, pb_dock, pb_close_lens, pb_today, time_hub, pb_timeoff, pb_ot_desk), ac-*
  (access_board.xml), cp-* (filing_flow, bank, young worker, audit). Unreferenced ones are `reserved`.
  Contract checks `wider-app-lesson-anchors`, `wider-app-open-actions`; anchor-lint now covers every scanned
  template and prefix.
- **Ask Payobook:** THE WIDER APP block in ONBOARDING_SYSTEM_PROMPT; `_KNOWN_LESSONS` += L13–L24,
  `_KNOWN_WALKTHROUGHS` += the twelve; test_action_envelope test_18.
- **Tab gates (LR33):** `@pb_hub/js/hub_gates`; step 5's "every station reachable" sweep should read
  `lensReach` rather than trust `visible_stations` for hub-tab stations.
- **Versions after step 4 (all four databases):** pb_learn 19.0.18.0.0, pb_hub 19.0.1.10.1, pb_payroll_ai_insights
  19.0.3.8.0, pb_pay 19.0.3.5.2, pb_hiring 19.0.1.3.4, pb_mission 19.0.1.11.1, biz_access 19.0.1.4.3,
  pb_govt_reports 19.0.1.2.1 (+ patch bumps on every other module that got anchors).
- **Pre-existing test failures seen on the clone (not step 4):** pb_learn test_07b; pb_payroll_ai_insights
  test_data_access_06, test_egress 04d/04e; and in modules that only got anchors: pb_bank_ocr 07/07b/09/15,
  pb_timeoff 03/05, week entry 06, pb_decision_room t2/t22, pb_govt_reports filing flow ×2, pb_young_worker
  09b, pb_people_hub gates ×2 (pb_demo group absent on the template), biz_access empty-home people lens —
  all Python/data logic, none touched by an attribute.
- **Validation logins:** the QA login sees every step-4 tab except Filings (no filing group) and Praise/Goals/
  People-Announce; the demo login is refused every step-4 tab, and every walkthrough ends on the no-access card.

- LR44 **Some taught screens have no Vietnamese in the product at all** and the replica says so rather than
  inventing it: the Pay Run ledgers (Adjust/Settle descriptor words — KPI labels, facets, metrics, drawer — are
  plain Python strings in `ledger_cockpits.py`, never wrapped in `_()`), the contract drawer (pb_contracts has no
  entries for Terms/Components/History/save bar), Payroll Report (inline JS template, nothing extracted), the
  connection screen (connector_cockpit + Python action labels), most of Calendar and Awards. The fixture helper
  `EN("…")` (practice-data.js) marks such a label: same words in both languages; the VI lesson names the English
  label and glosses it. Owner item: wrap/translate them in the product.
- LR45 **Pay Run › Settle draws no tab strip** (ledger.xml renders `pbl-tabs` only past one tab), so `lg-tabs` exists
  on Adjust only. **There is no "factor" on the Proration screen**: the row shows Old / New / Prorated money; the
  days (Basis, Period days, Old days, New days) live in the row's drawer. Old content taught "read the factor".
- LR46 **Folding a station = alias + migration, never a silent delete.** `STATION_ALIASES` in data.js (contracts →
  employees, proration/retro → adjust) is emitted as `station_aliases` (generator refuses an alias whose old key is
  still a station or whose target is not); `learn.content.station()`, `learn.progress.record`, `learn.event.log`
  and the Journey's deep links resolve it. Migration 19.0.19.0.0 re-keys/merges progress rows and re-keys event
  history; a retired "done" arrives as "in_progress" (the new lessons are full lessons nobody has taken).
- LR47 **A .po entry copied from another module is dead weight when its code never emits the string.** pb_probation
  carried 19 approval-engine strings with only `#. module:` (no odoo-* marker, no occurrence) — the reader dropped
  them, and pb_approval_config already translates them. Removed. Check with a marker/occurrence scan, not by eye.
- LR48 **Replica icons must exist in `journey/icons.xml`** (`replay_tests test_02` fails otherwise): there is no
  `megaphone`, `wallet`, `trending-down` or `list` — use message-circle, banknote, receipt, list-checks.
- LR49 macOS has no `timeout`; wrap remote calls in `gtimeout` (MacPorts) on this workstation.
- LR50 **Hiring's "Open" count shared the button's msgid** (global JS translations are keyed by msgid only), so it
  read "Mở". The count is `_t("Open roles")` now; "Step X of 4" is one `_t("Step %(n)s of %(total)s")` sentence
  ("Bước X/4"); the request wizard's tab names moved from a template array literal (never extracted) to a `_t` getter.
- LR51 **A hub-tab screen needs a matcher of its own for the Coach** (`test_coach::test_14`): give it the
  standalone boards' action tags in `SCREEN_ACTION_TAGS` (adjust → pb_retro/pb_proration, declared AFTER the
  proration/retro screens so a standalone board still grounds on its own screen). A screen that lost its station
  needs its own `name` in SCREEN_CTX, or the generator names it by its key (bundle test_06). Settings screens
  whose sidebar leaf retired need `open:` (Salary Structures, Integrations) or "Open" goes nowhere.
- LR52 **Ask Payobook left every step-5 question without a button, and sent "where is the budget" to the data
  path.** The classifier now names these areas and says "where do I see / where is / how do I" and app-behaviour
  "why / do I need" questions are about using the app; `_lesson_handoff` offers the lesson whose station `search`
  phrases appear in the question (whole phrase, name weighs less), on the onboarding AND knowledge paths. The
  station `search` words are therefore also PayAI's routing table — keep them phrased as people ask.
- LR53 **Browser automation over the map writes real progress** (every started lesson is a row). Clean the QA
  login's rows written that day afterwards (`learn_event` is append-only — leave it).

## Step 5 facts (final state, 2026-09-28)

- **40 stations, every one a full lesson (5–9 steps).** New: afterrun L32, adjust L30, reports L38. Rewritten
  from outline: employees L29 (+ contract drawer), fullfinal L31, structures L33, integrations L34, insights L35,
  explorer L36, workforcean L37. Deepened to 5 steps: L20, L25–L28. Retired keys (aliases): contracts →
  employees, proration/retro → adjust. Lesson keys run LW, LA, L1–L38.
- **Lines/chapters:** LINE_ORDER overview, payrun, setup, people, lifecycle, workforce, insights, compliance;
  CHAPTERS ch1 Get around (overview) · ch2 Run pay (payrun) · ch3 Set up pay (setup) · ch4 People and their
  journeys (people, lifecycle) · ch5 Workforce · ch6 Understand and comply (insights, compliance).
- **Paths (learn_path.py):** officer 16, approver 7, hr 10, manager 7 (new; guessed from hr_attendance
  officer/manager, after hr), owner 10. MILESTONES m_employee → employees.
- **Anchors added:** lg-tabs/-steps/-rowact/-drawer, rs-head/-compare/-grid, dl-bank/-release/-slips,
  pc-hero/-months, aw-put/-steps/-table, pe-contracts/-rowcontract, cd-tabs/-body/-save, ic-actions/-fetch,
  rp-pick/-kpis/-tabs, bg-months/-heat. Practice: rep-cd-*, rep-ig-arrivals, rep-pm-announce/-plan.
- **Versions (all four databases):** pb_learn 19.0.19.0.0, pb_payroll_ai_insights 19.0.3.9.0, biz_access
  19.0.1.4.4, pb_records 19.0.1.3.3, pb_hiring 19.0.1.3.5, pb_formula_studio 19.0.1.201.3 and patch bumps on
  pb_payrun_ledgers, pb_payrun_results, pb_pay_delivery, pb_comp_ben, pb_people, pb_contracts,
  pb_import_advanced, pb_hr_workforce, pb_budget, pb_mission, pb_today, pb_audit, pb_workforce_insights,
  pb_explorer, pb_probation. pb_hr_payroll_formula: Python + .po only (no bump; net_role selection VI written
  to `ir_model_fields_selection` by SQL on each DB).

## Step 6 gotchas (2026-09-28)

- LR54 **Nothing may touch the cursor between `cr.execute` and `cr.fetchall`.** `get_param` (and any ORM read that
  misses the cache) runs its own query on the same cursor, and the fetch then returns THAT query's rows — the first
  `pb_review_flags` returned `{}` for every run. Read settings before the query.
- LR55 **`hr_payslip` has no index on `employee_id`.** A per-payslip `LATERAL` "previous payslip" lookup seq-scanned the
  table once per row: 4.5 ms × 900 = 13 s for one run. Set-based instead: `DISTINCT ON (c.id)` over a join, and the
  net line as `DISTINCT ON (slip_id)` over just those payslips' lines (0.4 s).
- LR56 **The settlement summary crashed from 2026-09-22 (6d1f8d4d6) until step 6.** `_build_component_summary` wraps
  rule values in a plain `_Line` object and called `pb_pay_band()` / `_fields` on it — AttributeError on every
  settlement with a figure, so hand-made ones failed and the monthly load's automatic ones were silently never made.
  The summary now reads the rule's own `net_role` (info / mixed / employer_cost are not money on a settlement).
- LR57 **"Demo boards are empty" was mostly the reader, not the data** (corrects LR42). The QA login's default company
  was 1 ("Your Company"); the demo world lives in company 5. With `cids=5` Exits (9 leavers), Probation (10), Growth
  plans, Hiring (13) are full. Lifecycle › Contracts still shows zeros to a reader without `hr.contract` read — the
  board swallows the refusal (`_safe`) and says "nothing ending" instead of "no access" (owner item).
- LR58 **`_register` is an Odoo model attribute** (a bool). A helper method named `_register` on a model fails with
  "'bool' object is not callable". Prefix helpers (`_walk_register`).
- LR59 **A migration only sees the modules its module depends on.** pb_demo's 19.0.1.12.0 migration found no
  `pb.pay.review` (pb_pay is not a dependency) and skipped the review; it was laid by a shell run of the same
  idempotent method afterwards. Runtime (`action_generate_all`) has the full registry.
- LR60 **The default pay-run route cannot be walked by one demo login**: `independent` hands step 1 to the backup when
  the submitter holds it, and HR lead review is per part of the business (no seat per scheme on the demo). The demo
  company's route is published with HR lead company-wide and independence off (3 steps and "different people per
  step" kept). Tenants keep theirs.
- LR61 `rsync --delete a b c dest/` deletes every OTHER directory in `dest/` — never share a staging dir between
  sessions/agents (step 6 used /tmp/s6stage for the parent, /tmp/s6t5 for the translation agent).
- LR62 postgres cannot read `/odoo/backups` (like it cannot write there): restore with
  `sudo cat x.dump | sudo -u postgres pg_restore -d clone`.
- LR63 **The live server's cron threads attach to a freshly restored clone** (the dbfilter limits HTTP, not cron) —
  three sessions held `s6clone` open. Immediately after a restore: `UPDATE ir_cron SET active=false; UPDATE
  ir_mail_server SET active=false; DELETE FROM mail_mail;`, and terminate backends before `dropdb`.
- LR64 The QA login holds `pb_pip.group_pip_head` directly, so a browser check of Growth plans with it does not prove
  the administrator fallback; `pb_pip/tests/test_admin_access.py` does.
- LR65 Hùng's take-home in the practice company is +26.4% on June — UNDER the 30% default — so lessons teach the new
  flag and still keep "the overtime jump a person must spot" (truth over polish).
