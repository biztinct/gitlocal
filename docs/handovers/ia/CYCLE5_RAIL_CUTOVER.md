# IA Redesign — Cycle 5 (final): Home + People hubs, and the rail cutover

Program: Option A "Six Missions" — this cycle delivers the finished product. Mockup `docs/PAYOBOOK_IA_REDESIGN_OPTIONS.html` (Option A rail + Home/People hubs). Prior handovers C1–C4 in `docs/handovers/ia/`; conventions binding through **W105**.

## ⚠ Production discipline (unchanged)
payobook.com production box. W93/W94, W68, W75. C4's pg_dump-clone testing pattern is the preferred ritual — reuse it. Prefer UNVERIFIED over improvising.

## Scope
1. **Home hub** — module `pb_home_hub`, tag `pb_home_hub`: lenses `pulse(activity)·approvals(inbox)` mounting `pb_dashboard` + `pb_approval` (C2 embedded pattern), needs-you data in the approvals lens (pb_approval IS the queue — no separate dock build), period tracker reusing `pb.pay.hub.get_period_state()` (chip click → opens the Pay hub at the mapped lens via `openHub`).
2. **Dashboard legacy-links fix**: `pb_dashboard/static/src/xml/pb_dashboard.xml:21,111` hero + "Open analytics →" open the legacy native `hr.analytics.dashboard` form (`pb_hr_payroll_analytics.action_open_hr_analytics_dashboard`) — retarget both to the Insights hub (`openHub`, back to Home). No other Dashboard changes.
3. **People hub** — module `pb_people_hub`, tag `pb_people_hub`: lenses `employees(users)·contracts(file)·plan(trending-up)` mounting `pb_people`, `pb_contracts` (embedded pattern), and **Plan = a minimal launcher lens** (OWNER RULING: Planning gets minimal menu change ONLY — its screens/flows are a separate future revamp). Plan lens = a card grid (kit-styled) of the existing 7 Planning actions opening the EXISTING screens completely unchanged: `pb_hr_workforce_planning.action_wfp_dashboard` (tag `wfp_dashboard`), `action_wfp_scenario`, `action_wfp_forecast`, `action_wfp_grade`, `action_wfp_merit_matrix`, `action_wfp_cycle`, `action_wfp_tagging_wizard`. Do NOT embed the planning dashboard, do NOT reskin any planning screen, do NOT alter their actions.
4. **THE RAIL CUTOVER** — `pb_sidebar` data rewrite to the Option A rail (below), retiring every absorbed item.
5. **⌘K promotion** — hub entries lose "(preview)", become the primary Surfaces group; old surface entries remain as deep links.
6. **Polish**: `pb_bank_ocr`'s 9 FontAwesome glyphs → `ic()` (C4 finding).

### Binding non-goals
No Planning screen changes (ruling above). No Mission Control changes. No fixes for W105 (payslip-line record rules = money-visibility policy, owner's call), the VN legacy-wizard removed-field breakages, the Insights Pulse drills, or the tenant-DB load errors — all stay in the report as owner decisions/backlog. Old client actions all stay registered (bookmarks keep working).

## The target rail (exact)
Sections (pb.sidebar.section) after cutover — reuse existing section records where possible (rename/renumber), retire the rest; item sequences follow W8/W18:

| section (seq) | items (seq · icon · label → action) |
|---|---|
| overview 10, show_label=False | 10 · home · **Home** → tag `pb_home_hub` |
| operate 20 "OPERATE" | 10 · zap · **Pay Run** → tag `pb_pay_hub` · 20 · users · **People** → tag `pb_people_hub` · 30 · compass · **Workforce** → `pb_mission.action_pb_workforce` (item record UNTOUCHED except section/seq if needed) |
| understand 30 "UNDERSTAND" | 10 · trending-up · **Insights** → tag `pb_insights_hub` · 20 · shield · **Compliance** → tag `pb_compliance_hub` |
| grow 40 "GROW" | 10 · book-open* · **Learn** → `pb_learn.action_learn_journey` (keep its existing record; NOTE it is GENERATED data — regen via `docs/tutorial_poc/author/tools/gen_learn_data.py` if you must touch it, don't hand-edit) |
| system 50, show_label=False | 10 · settings* · **Settings** → tag `pb_settings_hub` |

*`book-open`/`settings` exist in `pb_sidebar.js`'s closed ICONS set? **Verify** (audit said defined-but-unused: `settings`; `book-open` may be missing) — extend the ICONS dict in `pb_sidebar/static/src/js/pb_sidebar.js:15–55` if needed (it's a closed set; unknown names silently render a circle).

**Gating**: hub items UNGATED (pb_mission precedent, rationale at `pb_mission/data/pb_sidebar.xml:35–43` — the shell gates its lenses per W95). Settings item ungated too (the hub hides all categories a user can't open; verify the empty-state renders — C3 deviation 4 said it's proven by construction only; now it becomes reachable, so prove it live with a probe persona).

**Match matrices** (active-item highlighting; clone pb_mission's pattern; this also RESOLVES the C1 hand-back double-claims — after cutover no two active items may share a tag/xmlid/model; update C1's pinned equality test):
- Home: tags `pb_home_hub,pb_dashboard,pb_approval`; models —
- Pay Run: tags `pb_pay_hub,pb_payrun_wizard,pb_payslip_review,pb_payrun_results,pb_import,pb_import_wizard,pb_pay_delivery,pb_fullfinal,pb_proration,pb_retro`; xmlids `pb_payruns.action_pb_payruns_kanban`; models `hr.payslip.run,hr.payslip,hr.payroll.import.batch`
- People: tags `pb_people_hub,pb_people,pb_contracts,pb_employee_detail,pb_contract_detail,wfp_dashboard`; xmlids the 6 other planning actions; models `hr.employee,hr.contract`
- Workforce: keep pb_mission's existing 13-tag list
- Insights: tags `pb_insights_hub,pb_insights,pb_explorer_cockpit,pb_workforce_insights,payroll_report_dashboard`
- Compliance: tags `pb_compliance_hub,pb_govt_reports,pb_bank_ocr,pb_young_worker,pb_audit` + the filing-flow tag
- Settings: tags `pb_settings_hub,pb_formula_studio,pb_structures,pb_statutory,pb_integrations,pb_import_connector_cockpit` + onboarding-flow tag; xmlids `base.action_res_users,base.action_res_company_form,pb_sidebar.action_pb_sidebar_item,pb_sidebar.action_pb_sidebar_section,om_hr_payroll.action_hr_payroll_configuration` (verify) + tag `pb_tenants`; models `hr.integration.connector,hr.formula.config,hr.payroll.structure,hr.salary.rule,vietnam.insurance.policy,vietnam.tax.table,vietnam.tax.slab`
Verify each tag/xmlid exists before writing; anything ambiguous → report, don't guess silently.

**Retirements**: every absorbed item → `active=False`, sequence moved to the 900 band (W18 convention, pb_mission precedent) — Dashboard, Approvals, the 10 PAY RUN items, SETUP's 4, People's 2, INSIGHTS' 3, COMPLIANCE's 3, PLANNING's 7, ADMIN's 6 (Audit moves under Compliance's match only — its rail item retires; it stays reachable via the Compliance hub lens + ⌘K). Empty sections → `active=False`. All via data + **migration** for live DBs (noupdate handling per C1 precedent; the pb_learn item is generated data — coordinate, don't clobber).

**Demo-lock remap** (`pb_demo/hooks.py:13–15` + `post_init_demo` :147–171): the lock set names retired items (`{Import Data, Roles & Access, Companies, Menu & Sidebar}`, section `admin`, tag `pb_import`). Preserve equivalent strength on the new rail: restrict the **Settings** rail item on demo DBs (covers Roles/Companies/Menu&Sidebar/Navigation) and keep the `pb_import` tag restriction (still blocks the standalone import cockpit; the pay-hub Import lens: verify what the demo persona experiences and pick the minimal mechanism — group-gate the lens for demo or accept it, DOCUMENT the choice). Also re-check `_hide_salary_structures` and `_retire_analytics_menu` hooks still make sense post-cutover (they reference old items). Update hooks + report the mapping.

**navigateHome**: `pb_sidebar.js:260–263` `_homeAction` = first indexed item with an `action_xmlid` — the new Home item uses a TAG not xmlid; verify home navigation still lands on the Home hub (give the Home item an action_xmlid for the hub action record if that's what it takes).

## Tests (evidence for each)
1. Fresh-eyes rail: exactly 8 items in 5 sections in the spec order, on both a migrated DB (clone) and a fresh module -u; screenshot.
2. Every rail item opens its hub/cockpit; Home hub shows pulse+approvals with tracker; chip click lands on the Pay hub's mapped lens with back chip Home.
3. Dashboard's two legacy analytics links now open the Insights hub (back → Home); the legacy `hr.analytics.dashboard` action is opened by nothing in Payobook (grep gate).
4. People hub: employees/contracts lenses embedded clean; Plan lens shows 7 cards; each opens the UNCHANGED existing screen (spot-check 3 incl. the native list ones — they still render native, that's correct per ruling); no Planning view/action file diffs in the cycle (git evidence).
5. Highlight matrix: open each of ~20 representative old tags/xmlids/models (payslips list, connector cockpit, proration standalone, planning scenario, structures cockpit, users list…) → exactly ONE rail item lights, per the match matrices; no double-claims (updated C1 test green).
6. Retired items: 900-band + inactive on the migrated clone; `get_sidebar_data()` returns none of them; old bookmarks (standalone actions) still open and highlight the right hub item.
7. Demo-lock remap proven with the demo persona: Settings item shows the restriction dialog; import restriction equivalent-or-better; document the Import-lens choice; `_hide_salary_structures`/`_retire_analytics_menu` behave sanely.
8. Settings empty-state: probe persona with no gate groups sees the "nothing available" state (C3's unproven branch), not a blank page.
9. ⌘K: hub entries primary (no "(preview)"), old deep links still work, yield matrix re-run across all 6 hubs + Mission Control + Studio.
10. pb_bank_ocr: 0 FontAwesome glyphs, visual parity screenshots.
11. Full regression: entire unit suite (183 + new sidebar/migration/hub tests) green in one run, exit 0.
12. Chrome sweep: all 6 hubs + Settings + Mission Control, 0 console errors, no ≥400 non-warmup assets; production health checks before/after deploy (C4 clone ritual; count files + checksums per W93/W94).
13. navigateHome lands on the Home hub.
14. `pb_learn` item intact (generated-data coordination proven — regen tool output or untouched diff).

## Self-review (mandatory)
Diff-read all data/migrations against the target-rail table; walk every match matrix entry against the audit's action inventory; verify no section/item sequence collisions anywhere (W8/W18 full-table SQL); verify the migration is idempotent (run twice on the clone); verify demo hooks; re-run affected tests after fixes.

## Commits (per feature, explicit staging, do NOT push; never stage `.claude/settings.json`, `thaco/`, `ABM/`)
Suggested: (1) feat(pb_home_hub); (2) feat(pb_people_hub) + Plan launcher; (3) fix(pb_dashboard): analytics links → Insights hub; (4) feat(pb_sidebar): the cutover data + migration + tests; (5) feat(pb_demo): lock remap; (6) refactor(pb_bank_ocr): icons; (7) feat(pb_hub): ⌘K promotion; (8) docs/ledger.

## Report back
- Final rail table as shipped + full match matrix + retirement count.
- Demo-lock mapping decision. Import-lens choice. navigateHome resolution.
- Highlight-matrix evidence (test 5 table). Migration idempotency proof.
- Per-test evidence, commit hashes, deviations, new W entries.
- A one-paragraph "state of the product" suitable for the owner's final report.
