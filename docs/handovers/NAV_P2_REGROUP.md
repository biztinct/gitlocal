# NAV P2 — regroup the menu (moves, renames, aliases, Learn, Access)

Read first: `docs/handovers/NAV_LEDGER.md` (R1–R13, verified plumbing, gotchas) and `docs/handovers/NAV_P1_REPORT.md`
(what P1 shipped). Design of record: `docs/design/payobook-navigation-review-20261019.html` sections 12.4 (revised
menu) and 13 (what exists inside each screen). Owner decisions locked 2026-10-20: "Pay Run" → "Payroll"; Ask HR becomes
an item on Home; Learn stays visible; Learn and Access must follow every menu change in the same phase.

Two implementers run in parallel on the same working tree:
- **Agent A (code):** Part A below. Builds, tests locally, commits, **stops at the deploy gate** and reports.
- **Agent B (Learn):** Part B below. Edits the Learn sources, regenerates, runs the pb_learn tests, commits. No deploy.
Fable announces the service stop to the other sessions, then sends Agent A the go for the risky-tier deploy.
Agent A never edits `pb_learn/`; Agent B never edits anything outside `pb_learn/` and `docs/tutorial_poc/`.
Both stage explicit paths only.

## 1. Target state (what the menu looks like after P2)

Sidebar (dark rail), sections unchanged (Overview / Operate / Understand / Grow / System):

| Section | Entry (EN / VI) | xmlid of `pb.sidebar.item` | Action tag | Seq | groups_id (4,ref) | Note |
|---|---|---|---|---|---|---|
| Overview | Home / Trang chủ | `pb_home_hub.item_home` (exists) | `pb_home_hub` | 10 | — | gains ASK HR lens |
| Operate | **Payroll** / Lương | `pb_payhub.item_pay_run` (exists, **xmlid unchanged**, label changes) | `pb_pay_hub` | 10 | unchanged | |
| Operate | People / Con người | `pb_people_hub.item_people` (exists) | `pb_people_hub` | 20 | unchanged | gains Joiners, Probation, Exits, Contracts |
| Operate | **Hiring** / Tuyển dụng | `pb_hiring.item_hiring` (**new**) | `pb_hiring_hub` (**new**) | 24 | `pb_hiring.group_hiring_user` + `hr.group_hr_user` | |
| Operate | Workforce / Lực lượng lao động | `pb_mission.item_workforce` (exists) | `pb_workforce` | 30 | unchanged | loses Trips |
| Operate | **Expenses** / Chi phí | `pb_expenses_hub.item_expenses` (**new**) | `pb_expenses_hub` (**new**) | 35 | `hr.group_hr_user` + `account.group_account_invoice`? → use `hr_expense.group_hr_expense_team_approver` and `hr.group_hr_user` | |
| Operate | ~~Ask HR~~ | `pb_ask_hr.item_ask_hr` → `active=False` | | | | becomes Home lens |
| Operate | ~~Lifecycle~~ | `pb_lifecycle.item_lifecycle` → `active=False` | | | | hub action kept as a redirector |
| Understand | Insights, Compliance | unchanged | | | | Insights lens "Payroll Report" → label "Payroll"; Compliance lens "Young workers" → label "Safeguards" |
| Grow | **Talent** / Nhân tài | `pb_talent_hub.item_talent` (**new**) | `pb_talent_hub` (**new**) | 5 | `hr.group_hr_user` | sits above Learn |
| Grow | Learn | unchanged | | 10 | | loses Training |
| System | Settings | unchanged | | | | 18 categories → 7 rail groups |

Rails after P2 (short label EN → VI; lens key; source):

| Hub | Rail (in order) |
|---|---|
| Home | PULSE (Tổng quan) `pulse` · INBOX? keep key `approvals` label **Inbox** (Hộp thư) · **ASK HR** (Hỏi Nhân sự) `askhr` new lens · WALL `wall` · ANNOUNCE `coming_up` |
| Payroll | RUN · RUNS · **INPUTS** (Đầu vào) `import` · RESULTS · PAYSLIPS · ADJUST · SETTLE · **PAY OUT** (Chi trả) `deliver` · CALENDAR · AWARDS (keys unchanged; order unchanged from today) |
| People | EMPLOYEES · RECORDS · PAY · WHERE THEY WORK · ASSETS · **JOINERS** `newjoiners` · **PROBATION** `probation` · **EXITS** `exits` · **CONTRACTS** `contracts` (renewals board from pb_contract_lifecycle) · PLAN. Praise, Goals and Announce leave. Sequence: employees, records 40, pay 45, where 48, assets 50, newjoiners 52, probation 54, exits 56, contracts 58, plan. |
| Hiring (new) | OVERVIEW `overview` (the hiring board) · INTERVIEWS `interviews` (board with `startTab:"interviews"`) · TALENT POOL `bank` (board with `startTab:"bank"`) |
| Workforce | unchanged minus TRIPS |
| Expenses (new) | TRIPS `trips` (PbTrips embedded) · CLAIMS `claims` (the existing claims list, embedded) |
| Insights | PULSE · EXPLORER · WORKFORCE · **PAYROLL** (label of the `payroll` lens) · BUDGET · HIRING · TRAINING · GOALS |
| Compliance | FILINGS · BANK · **SAFEGUARDS** (Bảo vệ) `young_workers` key unchanged · AUDIT |
| Talent (new) | GOALS `goals` · GROWTH (Phát triển) `pip` · TRAINING `training` · PRAISE `praise` |
| Learn | LESSONS · TEAM · SETUP (label of the `settings` lens; VI "Thiết lập") |
| Settings | COMPANY · ACCESS · PAYROLL · HR · WORKFLOWS · INTEGRATIONS · SYSTEM (groups of the 18 categories, see A6) |

Full names (page header / tooltip) stay the long form: "Payroll inputs", "Payments and delivery", "New joiners", "Growth plans", "Young workers and safeguards", "Payroll report", "Learn settings".

## 2. Binding non-goals

- No new business screens except the two embeds (Ask HR kanban on Home, Claims list on Expenses) which wrap existing views. No APPLICANTS/OFFERS registers, no readiness, no TEAM page, no org chart (P3).
- No change to lens keys, action tags of existing hubs, model names, approval routes, or data.
- No change to the employee portal.
- No "Odoo" in any user-visible string (R9). Lucide icons only.
- Do not delete the Lifecycle hub module or its action; it becomes a redirector (A4).

---

## Part A — code (Agent A)

### A1. Payroll rename (labels only, keys unchanged)

- `pb_payhub/data/pb_sidebar.xml:46-58` `item_pay_run`: `name` → "Payroll". Keep xmlid, tag, matches.
- `pb_payhub/static/src/js/pay_hub.js:86` brand label → `_t("Payroll")`; `:121` and `:256` back labels → "Payroll"; lens labels `:112-126`: import → `_t("Inputs")`, deliver → `_t("Pay out")`.
- `pb_payhub/static/src/js/pay_hub_palette.js:55-59` mission row label "Payroll", sublabel "Payroll operations", add `keywords: ["pay run", "đợt lương"]` (see A5). Lens rows: Inputs/Pay out labels; keep `sublabel` "Pay Run Hub" → "Payroll".
- `pb_hub/static/src/js/hub_palette_entries.js:117-137` sublabels "Pay Run" → "Payroll".
- `pb_import/learn_manifest.py:24` label if it says "Import" as a tab name → "Inputs" (check it is a tab label, not an action name).
- `pb_hr_workforce` Insights lens label "Payroll Report" → "Payroll" (find the registration in `pb_hr_workforce/static/src/js/payroll_report.js` or its palette; key `payroll` stays).
- `pb_young_worker` Compliance lens label "Young workers" → "Safeguards" (key unchanged); hub header/full name "Young workers and safeguards".
- `pb_learn` lens "Settings" → **Agent B owns pb_learn**; Agent A does not touch it. (Agent B renames the Learn lens label to "Setup".)
- `pb_demo/hooks.py:46-49` locks entries by item NAME: update "Pay Run" → "Payroll" if matched by name.
- Translations (R: PO rules below): in each owning module's `i18n/vi_VN.po`, update/add msgstr: "Payroll" → "Lương" (pb_payhub, pb_hub), "Inputs" → "Đầu vào", "Pay out" → "Chi trả", "Safeguards" → "Bảo vệ". For the stored sidebar item name, a translation fix is TWO fixes: the `.po` AND the stored jsonb value (`pb.sidebar.item.name` with lang vi_VN) — write it in a migration or a post-init step so every DB shows "Lương" (memory: LOOK program).

### A2. Hiring hub (inside `pb_hiring`)

- New `pb_hiring/static/src/js/hiring_hub.js` cloning the shape of `pb_insights_hub/static/src/js/insights_hub.js` (export `HIRING_LENSES = "pb_hiring_hub_lens"`; `config = { key:"hiring", brand:{label:_t("Hiring"), icon:"userPlus"}, feature:"lifecycle", defaultLens:"overview", lenses:[overview, interviews, bank, ...extraLenses()] }`). Lenses:
  - `overview`: icon `layoutGrid`, label `_t("Overview")`, Component `PbHiringBoard`, groups = the HIRING gate from `hiring_palette.js:50-69`, probe `pb.hiring.can_open`, `propsFromContext` as today (`pb_role_id`→`roleId`).
  - `interviews`: icon `calendarClock`, label `_t("Interviews")`, same Component with `props:{startTab:"interviews"}` (verify the board honours `startTab` for "interviews" as it does for "bank" at `hiring_board.js:288-290`; if not, add the two-line support there).
  - `bank`: icon `bookOpen`, label `_t("Talent pool")`, `props:{startTab:"bank"}`.
  - HUB_LENS_GATES registration for the three, `hubFeature:"lifecycle"` (pattern `compliance_hub.js:144-149`).
- Template `pb_hiring/static/src/xml/hiring_hub.xml` = `<HubShell config="config" action="props.action or {}"/>`; register action tag `pb_hiring_hub`; `ir.actions.client` record `pb_hiring.action_pb_hiring_hub` in `pb_hiring/views/hiring_views.xml` (pattern `pb_insights_hub/views/pb_insights_hub_action.xml`).
- Sidebar: `pb_hiring/data/pb_sidebar.xml` (new file, `noupdate="0"`), record `item_hiring`: section `pb_sidebar.sec_payrun`, seq 24, icon `user-plus` (must be in the closed ICONS map of `pb_sidebar.js:16-72`; if absent, add it there with the Lucide path), `action_xmlid pb_hiring.action_pb_hiring_hub`, `action_tag pb_hiring_hub`, `match_action_tags pb_hiring_hub,pb_hiring_board,pb_hiring_numbers?` (numbers stays in Insights: do not claim it), `match_models hr.applicant,pb.hiring.requisition,pb.hiring.offer,pb.hiring.interview`, groups `(4, pb_hiring.group_hiring_user)`, `(4, hr.group_hr_user)`. Remove those model claims from Lifecycle's item if present (no double claims: `test_ia_c5.py:346`).
- Remove the Hiring registration from LIFECYCLE_LENSES (`hiring_palette.js:50-71`) and re-point its palette rows (`:186-192, :323`) and `hiring_setup.js:384-386`, `hiring_board.js:282,679` (`setPlaceSub("pb_hiring_hub","overview",…)`) to the new hub. `sidebar_door.py:29-46, 68-112`: force `pb_hiring.item_hiring` visible and send hiring-only users to `pb_hiring.action_pb_hiring_hub`.
- `pb_dashboard.js:122,130,131` Home chips for hiring → new hub; exits → `pb_people_hub` lens `exits`.
- `pb_zoho_bridge/static/src/js/zoho_palette.js:30` `requires:"pb_lifecycle_hub"` → `"pb_hiring_hub"` or the right hub per row.
- Feature keys: `pb_hub/static/src/js/hub_features.js:62-65` and `pb_tenancy/models/pb_sidebar.py:62-74` `FEATURE_BY_TAG`: add `pb_hiring_hub: "lifecycle"`, `pb_talent_hub: none`, `pb_expenses_hub: "workforce"`; `pb_tenancy/tests/test_features.py:247` updated.
- Role gates: `pb_vendor_access/hooks.py:778-797` `SCREEN_GATES` add Hiring (recruiter / talent lead / hiring roles as the catalogue names them), Expenses (finance / budget-holder), Talent (recognition, growth-plans, learning roles); new migration `pb_vendor_access/migrations/19.0.<next>/post-ensure_screen_gates.py` calling `ensure_screen_gates` (pattern of `migrations/19.0.1.6.0`). Bump `pb_vendor_access` version accordingly.

### A3. People hub gains the lifecycle boards

- Re-point registrations from LIFECYCLE_LENSES to `PEOPLE_LENSES` ("pb_people_hub_lens") with sequences 52/54/56/58 and `feature:"lifecycle"` on each lens (keeps the tenancy switch): `pb_onboarding/.../onboarding_palette.js:41-47` (label "Joiners", full name "New joiners"; icon `userCheck` → add to the icon helper if missing, else keep `sunrise`), `pb_probation/.../probation_palette.js:39-45` (icon `flag` or keep `stamp`), `pb_offboarding/.../exits_palette.js:38-44` (icon `logOut` or keep `powerOff`), `pb_contract_lifecycle/.../contractlife_palette.js:39-45` (label "Contracts"). Their manifests add `pb_people_hub` to depends (cycle-free, verified). Keep `LIFECYCLE_GATE` groups on each lens as today.
- **Contracts collision:** People already has a "Contracts" door (`people_hub.js:168-172`, `action_pb_people_contracts`, the contracts register). Resolution: the People rail item CONTRACTS is the `pb_contract_lifecycle` board (renewals) and that board gets a visible "All contracts" button opening `pb_people_hub.action_pb_people_contracts` (the register) with `pb_back` to People › contracts. Remove the old "Contracts" link inside Employees (`people_hub.js:168-172`) so there is one door.
- Palette rows (`onboarding_palette.js:62`, `exits_palette.js:65`, `probation_palette.js:66`, `contractlife_palette.js:65`) → `pb_people_hub.action_pb_people_hub` + same lens keys; add `keywords:["lifecycle"]`.
- People HUB_LENS_GATES (`people_hub.js:191-196`) picks them up through the registry; confirm `feature` is passed through (`people_hub.js:152-159` spreads the def).
- Remove Praise, Goals, Announce from People: `pb_rnr/rnr_palette.js:63-69` → TALENT_LENSES; `pb_goals/goals_palette.js:76-85` → TALENT_LENSES; `pb_hr_comm/comm_palette.js:82-88` (People Announce calendar) → becomes a second tab inside the Home `coming_up` lens (PbHrCommHome gets a "Calendar" tab that mounts PbHrCommCalendar; the standalone action stays). Update their palette rows (`rnr_palette.js:98`, `goals_palette.js:96`, `comm_palette.js:141-142,179-180`).

### A4. Lifecycle retired, kept as a redirector

- `pb_lifecycle/data/pb_sidebar.xml:44-53` `item_lifecycle` → `active=False`, plus a migration in `pb_lifecycle` that sets `access_customized=False` then `active=False` on every DB (the biz_access guard at `pb_sidebar_item_ext.py:64-78` drops `active` writes for customized entries in install mode; use SQL in the migration if the ORM guard still blocks).
- `pb_lifecycle/static/src/js/lifecycle_hub.js`: the `pb_lifecycle_hub` client action stays registered but its component, on mount, reads `pb_lens` from `props.action.context` and `doAction`s the new place with the same lens: `hiring`→`pb_hiring.action_pb_hiring_hub` lens `overview` (`pb_focus==="bank"` → lens `bank`); `newjoiners|exits|probation|contracts`→`pb_people_hub.action_pb_people_hub` same key; `pip`→`pb_talent_hub.action_pb_talent_hub` lens `pip`; `journeys` or none → `pb_lifecycle.action_pb_journeys` (standalone Journeys, tag `pb_journeys`). Use `openHub()` from `hub_nav.js:93-125` so `pb_back` is set. The Journeys cog/back door (`lifecycle_hub.js:97-105`) → Settings › HR.
- Journeys lives on in Settings: register a `pb_settings_category` entry key `hr_journeys`? No: add a card to the HR group (A6) in `pb_lifecycle/static/src/js/lifecycle_palette.js` with `requires:"pb_journeys"`, opening `pb_lifecycle.action_pb_journeys`. Palette rows `lifecycle_palette.js:40,51` → `pb_journeys`; `requires` at `:41,52,63,73` → `pb_journeys`.
- `pb_lifecycle/views/pb_lifecycle_action.xml:13-16` unchanged. Comment URLs in `offboarding_views.xml:262`, `probation_views.xml:341` updated.

### A5. Search aliases (old words keep working, R10)

- Extend the palette contract: `pb_hub/static/src/js/hub_palette_entries.js:5-18` documents an optional `keywords: string[]`; the matcher `pb_hub/static/src/js/hub_palette.js:119-128` includes `(entry.keywords||[]).join(" ")` in the haystack (still plain substring, lower-cased).
- Add keywords: Payroll mission row `["pay run","đợt lương","chạy lương"]`; Payroll lens rows import `["import","nhập"]`, deliver `["deliver","delivery","chi trả"]`; People row `["lifecycle","vòng đời"]` and the four moved lens rows `["lifecycle"]`; Hiring row `["lifecycle","recruit","recruitment","vòng đời"]`; Talent row `["praise","goals","training","growth plans","pip","khen ngợi","mục tiêu","đào tạo"]`; Expenses row `["trips","travel","business trip","claims","công tác","chuyến đi"]`; Home ASK HR lens row `["ask hr","hr request","hỏi nhân sự"]`; Compliance safeguards row `["young workers","lao động chưa thành niên"]`.
- Old deep links: `pb_hub/static/src/js/hub_palette_entries.js:165` (`pb_workforce` lens `trips`) → `pb_expenses_hub` lens `trips`; `pb_mission/data/pb_sidebar.xml:91` drop `pb_trips` from Workforce's claims; `pb_business_trip/data/pb_sidebar.xml:27-36` stays inactive.
- `pb_mission`: remove the built-in `trips` lens (`pb_mission.js:174-178, :57, :245, :547`; `pb_mission.xml:126-128`) and its gate row (`:824-826`); drop `pb_business_trip` from `pb_mission/__manifest__.py:95` only if nothing else in pb_mission imports it (grep first). `pb_mission/tests/test_static.py:44,523` updated.

### A6. Settings: 7 rail groups

- Add `group` to the category contract: built-ins in `pb_settings/static/src/js/settings_hub.js:132-241` get `group`: formula/structures/statutory/payroll → `payroll`; org/company → `company`; integrations → `integrations`; nav → `access`. Registry entries (`pb_settings_category`) get `group` in their own modules: `biz_access` nav/access → `access`; `pb_vendor_access` vendors → `access`; `pb_blueprint` guided_setup → `system`; `pb_group` group → `company`; `pb_approval_config` approvals → `workflows`; `pb_tenancy` about → `system`; `pb_hiring` hiring → `hr`; `pb_hr_comm` announcements → `hr`; `pb_payai_actions` → `system`; `pb_demo_seed` → `system`; Journeys card (A4) → `hr`. Unknown/absent group → `system`.
- `allCategories()` (`:326-332`) unchanged; add `groups()` = fixed order `[company, access, payroll, hr, workflows, integrations, system]` with labels/icons: COMPANY `building` (Công ty), ACCESS `key` (Truy cập), PAYROLL `calculator` (Lương), HR `sliders` (Nhân sự), WORKFLOWS `workflow` (Phê duyệt), INTEGRATIONS `plug` (Kết nối), SYSTEM `globe` (Hệ thống); a group with no allowed category is hidden (R6).
- `settings_hub.xml:55-69`: the nav becomes the rail standard (R1: 72 px, label under icon; reuse the P1 numbers from `hub_shell.scss`; class names may stay `pbst-nav*`), one button per group; the canvas lists the group's categories as titled sections of their cards (keep the category title + cards markup; a sole-card category still opens its card on click of its title). `setCat` → `setGroup` with the same localStorage memory and place publishing (`:647-663`); `pb_lens` arrival maps a category key to its group so existing deep links (`access_palette.js:105-129` `pb_lens:"screens"`) still land.
- `settings_hub.scss:123-170, 302-305` restyled to the rail; narrow rules per R5.
- Learn's `hub_settings` replica reads `MENU.settings.lenses` as cards: **Agent B** updates MENU to the 7 groups.

### A7. Home: Ask HR lens and Inbox label

- `pb_ask_hr`: add `pb_ask_hr/static/src/js/askhr_lens.js` registering into `HOME_LENSES` ("pb_home_hub_lens") key `askhr`, seq 15 (between Approvals and Wall), icon `messageSquare` (add to the icon helper if missing), label `_t("Ask HR")`, groups `["base.group_user"]`; Component `PbAskHrLens` renders Odoo's `View` (`@web/views/view`, props `{type:"kanban", resModel:"pb.ask.hr.ticket", context:{search_default_filter_open:1}, display:{controlPanel:{"top-left":false,"bottom-left":false}}}` or whatever this build's `View` accepts; see `web/static/src/views/view.js:206-230`) inside a `.pbhub-canvas`-friendly wrapper so the existing kanban (New / With HR / Answered / Closed) appears in the Home canvas; record rules keep employees on their own tickets. Keep the native action and menu for admins. Palette row with keywords (A5).
- `pb_ask_hr/data/pb_sidebar.xml:16-25` `item_ask_hr` → `active=False` with the same migration treatment as Lifecycle. Add `pb_ask_hr.action_pb_ask_hr_ticket` and model `pb.ask.hr.ticket` to Home's `match_action_xmlids` / `match_models` (`pb_home_hub/data/pb_sidebar.xml`) so the sidebar highlights Home on the native screen. `pb_ask_hr` depends on `pb_home_hub` (verify no cycle).
- Home lens `approvals` label → `_t("Inbox")` (VI "Hộp thư"); key unchanged. `pb_home_hub/i18n/vi_VN.po`.

### A8. Expenses hub (new module `pb_expenses_hub`)

- Clone `pb_insights_hub` (10 files). Manifest depends: `pb_hub`, `pb_settings`, `pb_business_trip`, `pb_me_expense`, `hr_expense`. Action tag `pb_expenses_hub`, xmlid `pb_expenses_hub.action_pb_expenses_hub`. Brand `{label:_t("Expenses"), icon:"wallet"}`, `feature:"workforce"`, `defaultLens:"trips"`.
- Lenses: `trips` (icon `plane`, label `_t("Trips")`, Component `PbTrips` with `props:{embedded:true}`, groups as the Workforce Trips lens had — `[]` means everyone with the item), `claims` (icon `receipt`, label `_t("Claims")`, Component `PbClaimsLens` = `View` list over `pb.expense.claim` using the existing list/search views, groups `hr_expense.group_hr_expense_team_approver`). Registry `EXPENSES_LENSES = "pb_expenses_hub_lens"` for later add-ons. HUB_LENS_GATES registration `hubFeature:"workforce"`.
- Sidebar item `item_expenses` (section Operate, seq 35, icon `wallet` → add to ICONS if missing, `match_action_tags pb_expenses_hub,pb_trips`, `match_models pb.business.trip,pb.expense.claim,hr.expense`, groups `(4, hr.group_hr_user)`, `(4, hr_expense.group_hr_expense_team_approver)`). Remove `pb.business.trip` from Workforce's `match_models` if claimed there.
- Palette mission row seq 135 with keywords (A5); lens rows for trips/claims.

### A9. Talent hub (new module `pb_talent_hub`)

- Clone `pb_insights_hub`. Depends: `pb_hub`, `pb_settings`, `pb_learn` (for the Grow section xmlid `pb_learn.sec_learn` only; verify no cycle: pb_learn must not depend on pb_talent_hub or on pb_goals/pb_rnr/pb_pip/pb_training — check with a script over manifests). Action tag `pb_talent_hub`, brand `{label:_t("Talent"), icon:"graduationCap"}`, no hub feature, `defaultLens:"goals"`, registry `TALENT_LENSES = "pb_talent_hub_lens"`, lenses = `extraLenses()` only (hub has no built-in lens; if the registry is empty the shell shows its empty state).
- Re-point registrations with `pb_talent_hub` added to their manifests: `pb_goals` goals (seq 10), `pb_pip` pip (seq 20, label "Growth", full "Growth plans", keep PIP_GATE + probe, `feature:"lifecycle"`), `pb_training` training (seq 30, remove from LEARN_LENSES), `pb_rnr` praise (seq 40). Insights lenses for goals/training/hiring stay where they are.
- Sidebar item `item_talent` (section `pb_learn.sec_learn`, seq 5, icon `graduation-cap` → ICONS map, `match_action_tags pb_talent_hub`, `match_models pb.goals.sheet?,pb.pip.case,pb.training.assignment,pb.rnr.*` (use the real model names from each module), groups `(4, hr.group_hr_user)`).
- Palette rows `goals_palette.js:96`, `rnr_palette.js:98`, `pip_palette.js:77`, `training_palette.js:66,77` → Talent hub; keywords (A5). `pb_people_hub` HUB_LENS_GATES loses praise/goals/announcements automatically (registry).

### A10. Tests Agent A must update and run

`pb_sidebar/tests/test_ia_c5.py` (TARGET_RAIL, MATCH_* , double-claim and label tests; fix the pre-existing `wfp` vs `pb_pay.*` disagreement at `:169-175` to match the data file), `pb_mission/tests/test_static.py`, `pb_tenancy/tests/test_features.py`, `pb_hiring/tests/test_hiring.py`, `pb_training/tests/test_training.py`, `pb_workseg/tests/test_static_contract.py`, `pb_pay/tests/test_static_contract.py`, `pb_settings` tests, new tests for the two new hubs (clone `pb_insights_hub/tests/test_insights_hub.py`), the pb_lifecycle redirector (a JS unit test or a tour is fine), and a test that `item_lifecycle` and `item_ask_hr` are inactive after upgrade. Run: `odoo-bin -c <local conf> -d <local db> --test-enable --test-tags /pb_sidebar,/pb_mission,/pb_tenancy,/pb_hiring,/pb_training,/pb_settings,/pb_expenses_hub,/pb_talent_hub,/pb_vendor_access,/pb_lifecycle --stop-after-init` and report the counts.

### A11. Translations (PO rules — crash risk)

Every new `.po` entry needs all three: `#. module: <name>` as the FIRST comment line, then `#. odoo-javascript` or `#. odoo-python`, then at least one `#: code:addons/<module>/<path>:0` occurrence. Missing the first crashes the registry load of every DB on upgrade; missing the others drops the string silently. Run the parse gate on the box before deploying (memory po-translation-loading-rules; the script is in the ledger gotcha row). New modules get an `i18n/vi_VN.po` with the hub label and lens labels.

### A12. Local verification (before the deploy gate)

Run on a local DB with vi_VN installed if possible. Chrome walk, as `base.group_system`:
1. Sidebar shows Home, Payroll, People, Hiring, Workforce, Expenses, Insights, Compliance, Talent, Learn, Settings; Lifecycle and Ask HR gone; count 11.
2. Each hub rail matches §1 exactly (order, labels, two-line fit in EN and VI).
3. Old links: `/bizapp/action-pb_lifecycle_hub` (no context) → Journeys; with `pb_lens=hiring` → Hiring › Overview; `pb_lens=exits` → People › Exits; `pb_lens=pip` → Talent › Growth. `pb_workforce` lens trips → Expenses › Trips (via the palette row).
4. Palette: typing "pay run", "lifecycle", "trips", "praise", "ask hr", "young workers" finds the new places.
5. Home › Ask HR shows the kanban with four columns; an HR user sees all, a plain user only their own (two logins).
6. Expenses › Claims lists claims; Trips board works embedded (approve/refuse buttons present).
7. Settings rail shows 7 groups; every one of the 18 categories is reachable under its group; `pb_lens:"screens"` deep link still lands on Access › Screens.
8. Access › Screens lists Hiring, Expenses, Talent with role gates (after the migration), Lifecycle and Ask HR as "off the menu".
9. Console clean on every hub; `python -m pytest`-style counts for the Odoo tests in A10.
10. Hiring-only user (member of `pb_hiring.group_hiring_user` only) lands on the Hiring hub after login (`sidebar_door.py`).

Then commit (explicit paths, one commit per area is fine: payroll rename / hiring hub / people regroup / lifecycle redirect / expenses hub / talent hub / settings groups / home ask-hr / aliases / tests), **do not push yet**, and return the report `docs/handovers/NAV_P2A_REPORT.md` with: diff summary per module, test counts, Chrome evidence for 1–10, the exact `-i` and `-u` module lists for the deploy, migrations included, and anything that deviated.

### A13. Deploy (only after Fable's go) — RISKY tier

Per CLAUDE.md and ledger R12. Modules: `-i pb_expenses_hub,pb_talent_hub` and `-u` every module touched (list from A12). Order: (1) `pg_dump -Fc` each of the four DBs to `/odoo/backups/nav-p2-<date>/` (run from root: `sudo -u postgres pg_dump -Fc db > file`); (2) PO parse gate on the staged tree; (3) stage + per-module scoped rsync + hash check (new modules too); (4) `sudo service odoo-server stop` (wait for zero `odoo-bin -c` processes); (5) detached `systemd-run` upgrade on **p0clone first** (`-i … -u … --stop-after-init`, sentinel file, poll), grep log for `EXIT=0` and no `traceback|CRITICAL`; if clean, same on `payobook`, `payobook_template`, `rize` one at a time; (6) per DB: `INSERT INTO orm_signaling_assets DEFAULT VALUES; DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%';` bump `web.assets.version`; (7) start service, confirm "Registry loaded" and port 8069; (8) verify each DB: module `latest_version` matches manifests (normalise the `19.0.` prefix), served bundle contains `pb_hiring_hub`, stored VI name of `item_pay_run` is "Lương"; (9) Fable does the payobook.com walk. Never touch `abm`. If p0clone fails, start the service immediately and report; do not continue to the other DBs.

---

## Part B — Learn (Agent B)

Source of truth: `docs/tutorial_poc/author/data.js` (lesson text, hub screens, intents, scenarios) and `docs/tutorial_poc/author/practice-data.js` (MENU + practice facts). Outputs are generated by `docs/tutorial_poc/author/tools/gen_learn_data.py` (`learn_content.json`, `fixture.js`, anchors `practice` block, sidebar data, `vi_VN.po` — its merge keeps hand-kept `.po` entries; still diff the `.po` after running and restore anything lost). Never hand-edit generated files.

B1. **Hub screens** (`data.js:9733-10133`): add `hub_hiring` (tag `pb_hiring_hub`, xmlid `pb_hiring.action_pb_hiring_hub`, tabs overview/interviews/bank), `hub_talent` (`pb_talent_hub`, tabs goals/pip/training/praise), `hub_expenses` (`pb_expenses_hub`, tabs trips/claims); remove `hub_lifecycle` tabs hiring/newjoiners/exits/probation/pip/contracts and retire the hub screen (keep a `live_fallback` or drop it: `places.js` must not resolve to a dead hub); add tabs newjoiners/probation/exits/contracts to `hub_people` (remove praise/goals/announcements); rename `hub_pay` name "Pay Run"→"Payroll"/"Lương", tabs import→"Inputs"/"Đầu vào", deliver→"Pay out"/"Chi trả"; `hub_workforce` drop trips; `hub_insights` payroll tab "Payroll"; `hub_learn` drop training, settings tab → "Setup"/"Thiết lập"; `hub_settings` → the 7 groups as its tabs (keys company/access/payroll/hr/workflows/integrations/system) with the categories listed in each tab's `line`.
B2. **Places** on every station/screen whose `places` start with `pb_lifecycle_hub:` → the new hub+lens (hiring → `pb_hiring_hub:overview`; hiringrole → `pb_hiring_hub:overview`; joiners → `pb_people_hub:newjoiners`; probation → `pb_people_hub:probation`; exits → `pb_people_hub:exits`; contractends → `pb_people_hub:contracts`; growth → `pb_talent_hub:pip`). `sidebar_key` values pointing at `pb_lifecycle.item_lifecycle` → the new items (`pb_hiring.item_hiring`, `pb_people_hub.item_people`, `pb_talent_hub.item_talent`); `SIDEBAR_KEYS` and `SCREEN_ACTION_TAGS` in `gen_learn_data.py:97-197` updated.
B3. **Breadcrumb words** (EN and VI, every occurrence listed in the fact-find): "Pay Run › X" → "Payroll › X" / "Lương › X"; "Pay Run › Import" → "Payroll › Inputs" / "Lương › Đầu vào"; "Pay Run › Deliver" → "Payroll › Pay out" / "Lương › Chi trả"; "Lifecycle › Hiring" → "Hiring › Overview" / "Tuyển dụng › Tổng quan"; "Lifecycle › New joiners/Probation/Exits/Contracts" → "People › …" / "Con người › …"; "Lifecycle › Growth plans" → "Talent › Growth" / "Nhân tài › Phát triển"; "People › Praise/Goals" → "Talent › …"; "People › Announce" → "Home › Announce › Calendar"; Workforce tab lists drop Trips (`data.js:6597, 6623, 14665`); "Lifecycle access." prerequisites (`:3071,3095,3141,3163`) → "People access." / "Talent access." as appropriate; glossary `:1504,1512,2041,2047,2053`; missions `:8890-8891, 9158`; intents `:11127, 11434-11600`; `wherelives` (`:10732-10756`) rewritten for eleven pages; "Nine pages on the menu" lesson (`:4352-4359`) → eleven pages, with the new list EN/VI; `:7125` Ask HR tip → "from Home › Ask HR".
B4. **Chrome lines**: keep line key `lifecycle`; label EN "Joining and leaving", VI "Gia nhập và nghỉ việc" (`data.js:85-91, 755-761`; `LINE_ORDER` unchanged).
B5. **Practice MENU** (`practice-data.js:2072-2210`): Pay Run→Payroll (+tabs Inputs/Pay out), People tabs regrouped, Lifecycle hub removed, Hiring/Talent/Expenses hubs added, Workforce minus Trips, Learn minus Training (settings → Setup), Settings → 7 groups; `SUB_SCREENS` unchanged. Section comments can follow.
B6. **MENU_ORDER** (`pb_learn/static/src/journey/library.js:33-42`) → home, payrun (label Payroll), people, hiring (`pb_hiring.item_hiring`, tag `pb_hiring_hub`), workforce, expenses (`pb_expenses_hub.item_expenses`), insights, compliance, talent (`pb_talent_hub.item_talent`), learn? (today absent; add it: `pb_learn.item_learn` if that is the xmlid), settings; `LINE_GROUP` (`:48-51`) lifecycle → people. Update `tests/js/library.test.mjs:110-116`, `test_learnrev_p3.py:61-74,162-180` (it checks each item is an active rail item: new items exist only after Agent A's data files load, so the test must read the data files or be tolerant until deploy), `test_learnrev_p2.py:95` ('Next: Payroll › Run'), `test_coach.py:261,399`, `test_scenario.py:491`, `guide_panel.test.mjs:441`, `test_nextbest.py:336`.
B7. **Learn lens label**: `pb_learn/static/src/hub/learn_hub.js:96` "Settings" → "Setup" (VI "Thiết lập" in `pb_learn/i18n/vi_VN.po` with the three-line rule from A11).
B8. Regenerate (`python3 docs/tutorial_poc/author/tools/gen_learn_data.py`), run `--check`, run the pb_learn Python and JS tests, bump `pb_learn` patch version in its manifest (Agent B owns the bump), commit `pb_learn/` + `docs/tutorial_poc/author/` with explicit paths, **do not push**, return `docs/handovers/NAV_P2B_REPORT.md`: counts of breadcrumbs changed per word, hub screens added/removed, test results, the `.po` diff summary (prove no hand-kept entries were lost), and a list of lessons whose screenshots/tours should be re-recorded (none should: scenarios use anchors, not selectors).

---

## 3. Report-back checklist (both agents)

- Deviations from this spec and why; new gotchas appended to `NAV_LEDGER.md` (date, phase, gotcha, rule).
- R11 self-score in five lines.
- Exact file list committed, commit hashes, nothing pushed.
