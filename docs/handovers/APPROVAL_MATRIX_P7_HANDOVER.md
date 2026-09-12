# Approval Matrix · Phase 7 — Setup & rules, platform, remaining people/time gaps, spreadsheet import, Vietnamese

**Handover from Fable (design) to Opus (build) · read `APPROVAL_MATRIX_LEDGER.md` first and append. Phases 1–6 are merged locally. Live server may still be down (AM14): test locally, end with the deploy checklist. Phase 8 (deploy wave + close-out) follows once the box answers.**

## 1. Scope

Every remaining catalogue row gets a real adapter with a **proposal record** where the write today is immediate. The pattern for all of them (clone it): a small stored proposal model `pb.<area>.proposal` holding `kind`, the target reference, `payload_json` (the exact write), a `snapshot_json` of the current values, `state` via engine; the existing RPC/action creates the proposal and submits; `_approval_apply` re-checks the snapshot against live values, performs the original write body as the final approver (who must hold the original gate group, else block + reassign), logs a `biz.audit.entry`; fast lane → immediate as today. Where a module has **no ACL at all** (statutory wizard, people wizards, filing flow) add the missing ACL/gate in the same change.

**A. Setup & rules** (each module adds `biz_approval_workflow, pb_approval_config` to depends):
1. `statutory` — `pb.statutory.wizard.create_policy(vals)` :762 and `create_tax_table(vals)` :782 (no ACL today: add `_require_manager` = `pb_hr_payroll_base.group_payroll_base_manager` and an ACL csv), `vietnam.tax.table.action_create_default_slabs` :120, `vietnam.insurance.adjustment.action_apply` :158 (payroll *user* can apply today), form-CRUD on `vietnam.insurance.policy`/`vietnam.tax.slab` (add `write` override → proposal when a non-fast workflow is published), legislation pack publish (`hr.formula.legislation.pack.state → published`: add `action_publish` + gate the raw write) and `pb.formula.studio.legislation_apply(pack_id, config_id=None, config_ids=None)` :3644, rate tables `save_rate_table(config_id, payload)` :11560 / `delete_rate_table` :11599 (note: when the config is **active**, P4's scheme-change rule already forces a branch; the `statutory` process covers packs/tables/policies that are not part of a scheme branch). Facts: `kind`, `rows_changed`, `effective_date`, `configs_affected`. Default seed: Payroll manager → Country director.
2. `bands` — `pb.pay.bands.save_band` :1594, `move_edge(dry_run=False)` :959 (add the `_require_write` before the write branch), `set_band_range` :1052, `link_job/unlink_job` :1616/:1624, `accept_suggestion` :1378, `import_bands`→`_write_import` :1560; guidance `pb.pay.reviews.save_guidance_cell` :473, `make_default_guidance` :464; limits (`pb.pay.review.limit` via `pb.pay.settings.limit_ids`, add a `write` hook). Facts `bands_changed`, `max_move_pct`, `employees_affected` (positions recomputed only on apply). Default: Head of pay.
3. `fx` — `res.currency.rate` create/write (add a model `write/create` hook in `pb_group` → proposal when managed), `pb.group.room.save_group` :758 (policy fields `fx_policy`, `presentation_currency_id`, `fiscal_start_month`, `split_pay_policy`), budgets `pb.budget.upload.wizard.apply` :159, `pb.budget.add_expense` :1149. Facts `rates_changed`, `budget_lines`, `amount_total`, `policy_changed`. Default: Finance approver → Finance controller (new role `finance_controller`).
4. `schememap` — `pb.scheme.board.attach` :394, `detach` :429, `accept_draft` :453 (wraps `pb.scheme.map.accept_draft` :675 which has no gate — keep it private to the board), `pb.formula.studio.scheme_mapping_create/delete` :8488/:8516. Facts `employees_moved`, `schemes`. Default: Payroll manager.
5. `mappings` — connector schedule fields (`integration_cron.py:102-151` write), `action_fetch_available_fields` :1229, mapping activation (`action_test_field_mappings` :1104 and template apply :1066 setting `active_state='active'`), `action_auto_map` :1323, `action_repair_severed` :1243, studio `api_mapping_*` :6081-6506, `mapping_*` :5402-5457, `import_mapping_*` :7992-8383, `mapping_template_*` :7761-7904, `api_transform_save` :7694. Group under one proposal per "mapping session": the studio already snapshots (`api_mapping_restore(snapshot)` :6506) — the proposal payload is that snapshot diff. Facts `mappings_changed`, `activations`, `schedule_changed`. Default: Payroll manager. (Catalogue row currently `soon` → connected.)

**B. Platform** (`pb_tenants`, `pb_tenancy`, `pb_demo_seed`; platform-only, never installed on tenants — keep that):
6. `tenant` — `tenant_suspend` :842, `tenant_schedule_deletion` :884, `offboard` :2713, `rollout_start` :337 / `rollout_abort` :908, `tenant_set_plan` :773, `features_bulk` :252 / `feature_save` :295, `restore_staging` :2677. Replace the typed-slug confirmation with a proposal + request (key `tenant`, kinds per op); the typed slug stays as the *confirmation* in the request drawer for destructive kinds. Facts `kind`, `tenants_affected`, `destructive` (bool). Default: **Joint: two platform owners** (role `platform_owner`, pool of `base.group_system` holders seeded) — the owner may relax it to fast lane. Cockpit: each destructive button becomes "Propose…" with the request door; the fleet screen shows pending proposals.
7. `demo` — `pb.demo.seed.action_load` :131 / `action_remove` :187 and `pb.demo.generator.action_generate_all` :314: proposal when the DB is not a demo/template DB (facts `records`, `is_demo_db`). Default: Tenant administrator.

**C. People/time gaps:**
8. `verdict` — `pb.probation.review.action_verdict(verdict, …)` :770 and `pb.pip.case.action_verdict` :775 / `action_terminate` :982: proposal only for `fail`/`extend`/`terminate` kinds (pass stays immediate unless the workflow says otherwise via condition `verdict`). Facts `verdict`, `tenure_months`. Default: Their manager → HR lifecycle team, condition "only when verdict is fail or terminate" on the second step.
9. `letters` — `pb.hr.letter.action_send` :251 (generate stays free; sending is the act). Facts `letter_type`, `has_pay_figures`. Default: HR lead.
10. `newhire` — `pb.people.onboard.wizard.create_employee(vals)` :56 and `pb.people.contract.wizard.create_contract(vals)` :130 (no ACL today: add `_require_hr` + csv). Facts `wage`, `has_bank`, `contract_type`. Default: HR lead (maker-checker).
11. `unlock` — `pb.wf.lock.unlock_day` :316 and `pb.close.unlock_days` :863 (tighten its gate to the lock model's `_MANAGE_GROUPS`). Facts `days`, `days_in_closed_payroll` (bool). Default: Payroll manager.
12. `fnf` — `hr.full.final.generate.wizard.action_generate` :96 (creation is the act; add `state` to `hr.full.final.settlement`: draft/approved with `pb_approved_*`, download only when approved or fast lane). Facts `net_amount`, `employees`. Default: HR lead → Finance approver.
13. `retro` — carry-over/proration/retro rows are created `posted` inside import processing (`payroll_import_batch.py:2155-2558`); they are already covered by the `loads` request (P5). Here: add a standalone proposal only for **manual** retro adjustments created from the ledger cockpits (if a create door exists; else mark the row as covered by `loads` and document it). Default: Payroll manager → Finance approver.
14. `month` — `pb.payroll.calendar.action_reopen` :109 and `pb.paycal.set_state` :144 (reopen requires a reason and a proposal; close stays immediate). Facts `month`, `runs_done_in_month`. Default: Payroll manager.
15. `filing` — `pb.filing.flow.generate` :400 (no module ACL: add `_require_officer` + csv) → proposal; artifacts are produced on apply. Facts `country`, `filing_key`, `period`. Default: Payroll manager. (Row `soon` → connected.)
16. `payslips` etc. already done (P5); `support`, `roles` (P6).

**D. Spreadsheet import** (`pb_approval_config`):
17. "Import from spreadsheet" door: upload `.xlsx`, read the sheet named `Approval Matrix` with `ExcelConnector.load_workbook_multisheet(file_content)` :720 + `load_sheet_with_detection('Approval Matrix')` :886 (`pb_hr_payroll_formula/integrations/excel_connector.py` — `pb_approval_config` may import that module only if `pb_hr_payroll_formula` is installed; guard with `in self.env.registry._init_modules` and otherwise fall back to a plain openpyxl read of that sheet), parse the ten-row shape (`Stage, Transaction / Object, Maker Role, Reviewer Role, Final Approver Role, Named Approver, Backup / Delegate, Threshold / Limit, SLA, Setup Status, Evidence / Control`), map each row to a catalogue process by a small synonym table (row text → process key; unknown → "Other request"), build a **draft** workflow per row (roles from the reviewer/final columns via synonyms → `hr_lead`, `finance`, `payroll_mgr`, `director`; "+" → joint; named people become **proposed** responsibility rows shown in People & backups as "Proposed from spreadsheet · choose the account" until a user is picked; SLA text → `due` when parseable ("1 working day" → working_days 1; "By Day 15" → calendar_day 15; else none) with a warning; threshold text → a warning note, never a condition), and show a review screen listing what was created and what remains unresolved. Nothing is published by the import. Test with `RIZE/VIETNAM/Zoho_Payroll_Vietnam_Final_Configuration_and_Data_Setup_Pack_COMPLETED.xlsx`.

**E. Vietnamese + polish:**
18. Run `tools/refresh_pb_vi.py` for every module touched in P1–P7 (export POTs with the local runtime first: `odoo-bin -c … -d <db> --i18n-export=/tmp/pb_i18n_pots/<module>.pot --modules=<module>`), fill `vi_VN.po`, add/extend each module's Vietnamese test (copy `pb_explorer/tests/test_p7_vietnamese.py`).
19. Static contract tests on every touched module; a repo-wide grep test in `pb_approval_config` that no `.po` msgstr or shipped JS/XML in the touched modules contains "Odoo".
20. Catalogue: every row connected except any you had to leave (`soon`) — list them; process descriptions and areas reviewed; presets updated with the new roles.

**Non-goals:** deployment (P8), N-of-M pools (ledger note), project timesheets.

## 2. Verified plumbing
All file:line references above come from the 12 Sep map (statutory, bands, fx/budgets, scheme map, mappings, platform, people/time gaps, importer utilities, VI tool). Re-read each before editing; the P7 map's risk order: `pb.statutory.wizard` (no ACL), `pb_people_advanced` wizards (no ACL), `pb.filing.flow` (no module ACL), `vietnam.insurance.adjustment.action_apply` (user-level), `pb.close.unlock_days` (officer-level), `pb_tenants` destructive ops (single admin + typed slug).

## 3. Safety rails
1. Adding a proposal must never loosen an existing gate; where a gate was missing, add it.
2. Platform proposals never run on tenant DBs (`pb_tenants` is platform-only); the `tenant` process row is seeded only where `pb_tenants` is installed.
3. Snapshot check on apply for every proposal; mismatch → returned with the difference named.
4. The importer creates drafts and proposed people only; it never publishes, never assigns a real account by name similarity.

## 4. Tests
| ID | Scenario |
|---|---|
| Z01 | Each new adapter: proposal created; fast lane immediate; approve → original write body executed once; snapshot mismatch → returned |
| Z02 | Missing gates added: statutory wizard, people wizards, filing flow refuse unauthorised users |
| Z03 | Platform: suspend/abort/schedule-deletion require an applied joint request; typed slug still required in the drawer; not seeded on tenants |
| Z04 | Verdict: pass immediate; fail/terminate routed; extend routed |
| Z05 | Importer: the RIZE workbook → 10 drafts, roles mapped, joint rows, proposed people unresolved, SLA parsed where possible, nothing published; unknown row → Other request |
| Z06 | VI `.po` complete for every touched module; repo-wide "Odoo" gate passes |
| Z07 | Matrix shows every row connected/live per seeds; static contracts |

## 5. Test, validate, deploy checklist
Local runs for every touched module; Chrome (local): statutory wizard → proposal → approve; Pay bands move edge → proposal; Tenants (platform DB) → propose suspend → joint approve; Import from spreadsheet → review screen. End with the **complete deploy wave checklist for P1–P7** (every module, install vs upgrade per DB, migrations in order, seeds, asset ritual, tenant backups, verification queries), because P8 executes it verbatim.

## 6. Report back
Per P2 §8 plus: the list of catalogue rows left `soon` and why, the gates you added, and the importer's synonym table.
