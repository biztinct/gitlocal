# NAV P2 — Part A report (code): regroup the menu

Implementer: Agent A (Opus), 2026-10-21. Spec: `docs/handovers/NAV_P2_REGROUP.md` Part A (A1–A12). Ledger:
`docs/handovers/NAV_LEDGER.md` (six new P2 (code) rows). **Stopped at the deploy gate: A13 not run, nothing pushed.**
Deploy tier when the go comes: **risky** (new modules, data migrations, menu entries switched off).

## 1. What changed, per module

| Module | Version | What |
|---|---|---|
| pb_hub | 1.11.4 → 1.12.0 | Lens contract gains optional `title` (full name = rail tooltip). Palette contract gains `keywords`; matcher searches them; service passes them through. Pay Run sublabels → Payroll; Approvals row → Inbox; Workforce › Trips row → Expenses › Trips; Young Workers row keywords. Feature map: `pb_hiring_hub`/`pb_journeys` → lifecycle, `pb_expenses_hub` → workforce, People lenses newjoiners/probation/exits/contracts and Talent `pip` → lifecycle. |
| pb_payhub | 1.5.0 → 1.6.0 | Brand, sidebar entry name, action name, back chips → **Payroll**; Import → **Inputs** (tooltip "Payroll inputs"), Deliver → **Pay out** (tooltip "Payments and delivery"). Rail ORDER unchanged. Palette: Payroll row with keywords pay run / đợt lương / chạy lương; Inputs / Pay out rows with old words. Migration `19.0.1.6.0/post-nav_p2_payroll_name.py` writes the stored Vietnamese name "Lương" (entry + action), flushing first. Stale `.po` record occurrences removed so the importer cannot write "Đợt lương" back. |
| pb_insights_hub | 1.2.0 → 1.2.1 | Lens `payroll` label "Payroll" (tooltip "Payroll report"). |
| pb_compliance_hub | 1.2.1 → 1.2.2 | Lens `young` label **Safeguards** (tooltip "Young workers and safeguards"); palette keywords "young workers", "lao động chưa thành niên". |
| pb_comp_ben | 1.5.3 → 1.5.4 | Calendar/Awards palette sublabel "Pay Run Hub" → "Payroll" (found in the walk). |
| pb_import_kit | 1.22.0 → 1.22.1 | `messageSquare` icon (Lucide). |
| pb_import | (no bump) | Screen-guide docstring only. Rsync, no `-u`. |
| pb_payruns, pb_formula_studio | 3.0.7 → 3.0.8, 1.202.9 → 1.202.10 | Screen guides: "Pay Run › Results" → "Payroll › Results" (EN + VI "Lương › Kết quả"). **Agent B must regenerate Learn for these.** |
| pb_hiring | 2.8.1 → 2.9.0 | New Hiring hub `pb_hiring_hub` (action `pb_hiring.action_pb_hiring_hub`): Overview / Interviews / Talent pool over the existing board; board honours `startTab:"interviews"`; place published as `pb_hiring_hub:<lens>` (`overview/role` on a role page). New entry `item_hiring` (Operate, seq 24, `user-plus`, groups hiring user + HR user). No longer registers into the Lifecycle registry; palette rows, set-up back door, sidebar door (`HIRING_ITEM`, `HIRING_HUB`), hiring-only first screen → new hub. Settings category Hiring → group HR. Install hook + migration `19.0.2.9.0` run the role catalogue + gates. |
| pb_people_hub | 2.0.3 → 2.1.0 | Employees "Contracts" button opens People › Contracts when present (one door), else the register. Register's back door → People › Contracts. |
| pb_onboarding, pb_probation, pb_offboarding, pb_contract_lifecycle | +minor each | Boards register into People (52 Joiners, 54 Probation, 56 Exits, 58 Contracts) with the Lifecycle gate and `feature:"lifecycle"`; depend on pb_people_hub; palette rows → People with "lifecycle" keyword. Contracts board: "All contracts" button (gated on the contracts register's ACL). |
| pb_lifecycle | 1.4.4 → 1.5.0 | `pb_lifecycle_hub` is a **function client action** (redirector): hiring→Hiring Overview (focus bank → Talent pool), newjoiners/probation/exits/contracts→People same key, pip→Talent Growth, journeys or nothing→Journeys; passes `pb_back`/`pb_role_id`; falls back to Journeys if a target is missing. Template file deleted. `item_lifecycle` inactive, seq 982, claims emptied; migration `19.0.1.5.0` does it in SQL (flush first). Journeys gets a back chip and a Settings › HR category; palette rows open Journeys. Tests added (`tests/test_nav_p2.py`). |
| pb_talent_hub | **new** 19.0.1.0.0 | GROW › Talent (entry `item_talent`, seq 5 above Learn, `graduation-cap`, HR user). Shell only; `TALENT_LENSES` registry. Install hook runs role catalogue + gates. vi_VN.po, tests. |
| pb_goals, pb_pip, pb_training, pb_rnr | +minor each | Register into Talent: goals 10, pip 20 (label **Growth**, tooltip Growth plans, gate/probe/lifecycle switch kept), training 30 (off the Learn hub), praise 40. Depend on pb_talent_hub. Palette rows → Talent. |
| pb_expenses_hub | **new** 19.0.1.0.0 | OPERATE › Expenses (entry `item_expenses`, seq 35, `wallet`, HR user + expense approver; claims `pb_expenses_hub,pb_trips`, claim action, trip/claim/expense models). Trips = trips board embedded; Claims = native claims list through web `View` (Waiting approval filter, approver gate). Install hook runs catalogue + gates. vi_VN.po, tests. |
| pb_mission | 1.11.2 → 1.12.0 | Trips lens removed; `pb_trips` claim removed; old `pb_shell_lens:"trips"` link hands on to Expenses › Trips. Keeps `pb_business_trip` dependency (the dock decides trip approvals). |
| pb_ask_hr | 1.0.0 → 1.1.0 | Home › **Ask HR** lens (seq 15) = native kanban via web `View` (open-questions filter; card opens the native form, breadcrumb back to Home). Depends on pb_home_hub. `item_ask_hr` inactive, seq 983, claims emptied; migration `19.0.1.1.0`. |
| pb_home_hub | 1.2.1 → 1.3.0 | Approvals tab label **Inbox** (tooltip "Approvals inbox"). Home entry claims the Ask HR action and model. |
| pb_hr_comm | 1.0.2 → 1.1.0 | Announce leaves People; Home › Announce gets two tabs, Coming up and Calendar (calendar for the comms team only). Palette rows → Home. Settings category → HR. |
| pb_settings | 1.9.2 → 1.10.0 | Rail standard (72 px, 60 px buttons, 9 px capital labels, keeps labels on small laptops, sideways strip on phones). 7 groups in fixed order; a group page lists its categories as sections; sole-card category titles open their card; `pb_lens` with a category or group key lands on the group; place publishing by group. |
| pb_vendor_access | 1.13.2 → 1.14.0 | SCREEN_GATES: + Hiring (recruiter / talent lead / head of hiring), Expenses (budget roles), Talent (recognition, growth plans, goals, training roles); − Lifecycle. `ensure_screen_gates` flushes first. Migration `19.0.1.14.0` runs catalogue + gates. |
| pb_tenancy | 1.6.0 → 1.6.1 | FEATURE_BY_TAG + Hiring (lifecycle), Expenses (workforce); new entries are stamped at create time. |
| pb_dashboard | 2.2.6 → 2.2.7 | Home chips: exits → People › Exits, hiring → Hiring › Overview. |
| pb_zoho_bridge | 1.2.0 → 1.2.1 | Palette presence probe `pb_journeys`. |
| pb_sidebar | 3.2.3 → 3.2.4 | Icons `user-plus`, `wallet`, `graduation-cap`; `test_ia_c5` updated (target rail, match matrix, highlight cases, the two retirements, People xmlid claims fixed to the data file). |

Vietnamese: 20 `.po` files touched, every new entry has `#. module:` first, then `#. odoo-javascript`, then occurrences;
labels are exactly Fable's list (Lương, Đầu vào, Chi trả, Hộp thư, Hỏi Nhân sự, Người mới, Tuyển dụng, Tổng quan, Phỏng vấn,
Kho ứng viên, Chi phí, Công tác, Hoàn chi phí, Nhân tài, Phát triển, Bảo vệ, Công ty / Truy cập / Lương / Nhân sự /
Phê duyệt / Kết nối / Hệ thống). **Parse gate (Odoo `PoFileReader`, local): 20/20 parse, 0 failures; every new entry
reach a screen.** No "Odoo" in any new user string.

## 2. Tests (A10)

Local runtime `/Users/adity/odoo19`. DBs: `am_nav_base` = fresh install of HEAD (202 modules, vi_VN) → copy upgraded
exactly like the deploy → copies for tests. Because that DB's admin defaulted to Vietnamese (which breaks
English-sentence assertions everywhere), both test copies were switched to English, and the same tag list was run
against an untouched **HEAD baseline** on the same base.

| Run | Tests | Failed | Errors |
|---|---|---|---|
| P2 (`am_nav_p2_en`) | 1,793 | 50 | 1 |
| HEAD baseline (`am_nav_head_en`) | 1,765 | 54 | 1 |

**Failing only with P2: none.** Failing only at HEAD (fixed by P2): 4 (`test_ia_c5` match matrix and highlight matrix,
`test_settings` single-card rule, a pb_vendor_access re-seed test). The 51 shared failures are local-environment
ones present before P2 (28 pb_hiring mail/portal, 5 pb_ask_hr portal pages, biz_access mail, pb_mission/pb_sidebar
retired workforce-planning actions not installed here, gate groups of modules not installed, government-filings group).
New suites: pb_expenses_hub 11, pb_talent_hub 10, pb_lifecycle 7 — all pass. Per module: biz_access 213, pb_ask_hr 24,
pb_comp_ben 3, pb_compliance_hub 46, pb_dashboard 77, pb_goals 215, pb_hiring 487, pb_home_hub 37, pb_hr_comm 98,
pb_hub 34, pb_insights_hub 40, pb_mission 60, pb_onboarding 7, pb_pay 128, pb_payhub 43, pb_people_hub 35, pb_pip 5,
pb_probation 13, pb_settings 93, pb_sidebar 48, pb_tenancy 136, pb_training 249, pb_vendor_access 105, pb_workseg 55,
pb_zoho_bridge 14. Logs: scratchpad `tests_p2_en.log`, `tests_head_en.log`.

**Upgrade path** (copy of HEAD install, `-i pb_expenses_hub,pb_talent_hub -u <list>`): EXIT=0, 0 ERROR, 204 modules in
40 s. Found and fixed by this run: (1) Payroll stayed "Đợt lương" (raw SQL before the ORM flush + stale `.po`
occurrences); (2) Hiring got no roles (gate pass before flush, and hiring roles not yet in the catalogue). Final run:
Payroll "Lương" on entry and action; Hiring 3 roles, Expenses 4, Talent 11; Lifecycle and Ask HR inactive in the 900 band.

## 3. Chrome walk (A12), local `localhost:8069`, DB `am_nav_p2`

| # | Check | Result |
|---|---|---|
| 1 | Sidebar | **Pass.** 11: Home, Payroll, People, Hiring, Workforce, Expenses, Insights, Compliance, Talent, Learn, Settings. Lifecycle and Ask HR gone. |
| 2 | Rails EN + VI | **Pass.** Home PULSE·INBOX·ASK HR·WALL·ANNOUNCE; Payroll RUN·RUNS·PAYSLIPS·RESULTS·INPUTS·PAY OUT·ADJUST·SETTLE·CALENDAR·AWARDS; People EMPLOYEES·PAY·WHERE THEY WORK·ASSETS·JOINERS·PROBATION·EXITS·CONTRACTS (RECORDS/PLAN modules not installed locally); Hiring OVERVIEW·INTERVIEWS·TALENT POOL; Workforce without Trips; Expenses TRIPS·CLAIMS; Insights …·PAYROLL·…; Compliance BANK·SAFEGUARDS·AUDIT (Filings needs a group the local admin lacks); Talent GOALS·GROWTH·TRAINING·PRAISE; Learn LESSONS·TEAM·SETUP; Settings 7 groups. Tooltips carry full names. VI (admin switched to vi_VN): every word matches the list, sidebar "Lương"; **no label clipped in EN or VI**. |
| 3 | Old links | **Pass.** Lifecycle with no tab and `/bizapp/action-pb_lifecycle_hub` → Journeys; `hiring` → Hiring Overview; `hiring`+bank → Talent pool; `exits` → People Exits; `contracts` → People Contracts; `pip` → Talent Growth; with `pb_back` Journeys shows the back chip. Workforce `pb_shell_lens:trips` → Expenses Trips. |
| 4 | Palette | **Pass.** "pay run" → Payroll; "lifecycle" → Hiring, Journeys, New joiners, Exits, Probation; "trips" → Expenses, Trips; "praise" → Talent, Praise; "ask hr" → Ask HR (Home); "young workers" → Safeguards. Mission rows in menu order (fixed during the walk). |
| 5 | Ask HR | **Pass.** Kanban New / With HR / Answered / Closed; HR officer sees all 3; "Take it" moves a card; a card opens the native form with Home as the way back. A plain internal employee is sent to their own pages (/my) by the standing landing ruling, so checked through the same data call as that user: **2 of 3, only their own.** |
| 6 | Expenses | **Pass.** Claims list with Waiting approval filter, no second breadcrumb; Trips board embedded with Approve as Manager / Refuse on a submitted local test trip. |
| 7 | Settings | **Pass.** 7 groups; all 17 categories installed here reachable under their group (Salary Structures, Statutory not installed locally); category deep links (`hiring`, `journeys`, `integrations`) land on their group. Access card `pb_lens:"screens"` lands on Access › Screens. |
| 8 | Access › Screens | **Pass.** Hiring (Recruiter, Talent lead, +1), Expenses (budget roles), Talent (Recognition, +9) "sees it"; Lifecycle and Ask HR "off the menu"; header counts 11 entries. |
| 9 | Console | **Pass.** No browser console errors. Server log: only image requests on /my and two payroll-analytics jobs, unrelated. |
| 10 | Hiring-only user | **Pass.** Lands on the Hiring hub (Overview); rail items open the matching inner tab. |

## 4. Deploy lists (A13, after Fable's go)

```
-i pb_expenses_hub,pb_talent_hub
-u pb_ask_hr,pb_comp_ben,pb_compliance_hub,pb_contract_lifecycle,pb_dashboard,pb_formula_studio,pb_goals,pb_hiring,pb_home_hub,pb_hr_comm,pb_hub,pb_import_kit,pb_insights_hub,pb_lifecycle,pb_mission,pb_offboarding,pb_onboarding,pb_payhub,pb_payruns,pb_people_hub,pb_pip,pb_probation,pb_rnr,pb_settings,pb_sidebar,pb_tenancy,pb_training,pb_vendor_access,pb_zoho_bridge,pb_learn
```
Rsync (scoped `--delete` per module): every module above plus `pb_import` (docstring only, no `-u`), the two new
modules, and Agent B's `pb_learn`. Migrations included: `pb_payhub/19.0.1.6.0`, `pb_lifecycle/19.0.1.5.0`,
`pb_ask_hr/19.0.1.1.0`, `pb_hiring/19.0.2.9.0`, `pb_vendor_access/19.0.1.14.0`. Post-step per DB: asset purge +
`INSERT INTO orm_signaling_assets` + `web.assets.version` bump (without the signal the server keeps serving the old
bundle — seen locally). Agent B regenerates Learn for the two screen-guide strings before the deploy.

## 5. Deviations

1. Insights/Compliance labels live in `pb_insights_hub`/`pb_compliance_hub` (handover said pb_hr_workforce/pb_young_worker); Compliance key is `young`.
2. Payroll rail order kept as today (the §1 table showed another order but also said "unchanged").
3. Settings group word **CONNECT** (tooltip "Integrations"): INTEGRATIONS measures 73 px, wider than the rail. VI unchanged ("Kết nối"). Learn's English Settings tab label may say "Integrations" — Agent B to align.
4. Settings groups: a fallback key→group table in pb_settings instead of editing eight more modules; `group` set explicitly only in modules already touched.
5. The Employees "Contracts" button is kept (it also gates the per-person contract control and a Learn anchor) and opens People › Contracts.
6. pb_mission keeps `pb_business_trip` (dock approvals). pb_demo unchanged (it locks no entry named "Pay Run").
7. Retired entries moved to the 900 band (982, 983) per W18; role catalogue re-run before gating; feature key stamped at create.
8. A Learn-facing note: the Learn entry xmlid is `pb_learn.item_learn_journey` (the handover guessed `item_learn`).
9. The payobook.com walk is not done (local only, by instruction).

## 6. Self-score (R11)

1. Hero moment: eleven entries, each one place you'd look; Ask HR one tap from Home; Hiring, Expenses, Talent findable by name.
2. Zero dead ends: every old Lifecycle/Trips link lands on its new tab; old words still find places in ⌘K.
3. Plain language: one-word rail labels in EN and VI, full names in tooltips.
4. Motion: none added beyond the P1 pill.
5. Keyboard: Settings rail now uses the shared arrow-key helper.

## 7. Commits (local, not pushed)

9f9ebeece payroll rename + aliases · 9527d39f9 Hiring hub · 7b26c106f People regroup · f2c5d9aba Lifecycle redirector ·
cd8b544b2 Talent hub · 9b965cf78 Expenses hub · 2c1b3a2ba Home Ask HR + Announce · 3f93e8606 Settings groups ·
b6790559c tests + ledger · (this report).
