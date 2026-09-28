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
