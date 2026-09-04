# Integrations Program — Cycle 4: the abm tenant — inspection, the secrets report, and the seeding

> STATUS: FINAL — reconciled against Cycles 1–3, all shipped/deployed/live-verified. Read `CYCLE2_REPORT.md` and `CYCLE3_REPORT.md` (in this directory) for full detail; ledger binding through **W140**.

## Cycle 3 shipped reality (confirmed — build on this, don't re-derive)
- Zoho catalog: **10 feeds** on a zoho connector (auto-instantiated on create via C1's create-hook), exactly **3 flagged ABM** (badges render in the cockpit). Live demo connector already shows `39 mappings · 10 feeds`; studio feed picker lists all ten with mapped-counts.
- Vendor mapping templates: **32 target codes, substring-law-audited** (test_05 gates the shipped XML). The handover's suggested codes were corrected: **NAMEEN/NAMEVN** (not ENFULLNAME/VNFULLNAME), **VNDACCOUNT**; `GIVENNAME` was DROPPED (FirstName de-dupes by source_path — do not re-add it). 17 new zoho rows, all `endpoint_code='zohoemployees'`; 14 pre-existing rows stamped by an only-if-empty by-XML-ID migration (24/24 stamped). Three Darwin rows deliberately unstamped.
- Transformation-rule templates shipped + instantiation (commit c9a5f773). **The filter namespace is `rec`, NOT `record`** (engine evaluates with `rec` and swallows exceptions — a `record.get(...)` expression silently zeroes the feed; test_03b gates this). **DEPCOUNT and WORKEDHRS are `python` rules** (tabular section / seconds+H:MM parsing), guarded with `isdigit` not try/except.
- **Engine bug fixed in-cycle (efbb64b5)**: Odoo 19 removed safe_eval's `nocopy` — every `rule_type='python'` rule had returned `default_value` since the port. abm gets this fix via your WP-2 upgrade; your seeded python rules DEPEND on it — verify the fix's presence on abm post-upgrade (the commit's test asserts numbers, run it in your suite pass if applicable).
- `preview_transform` exception hygiene + board/studio count-honesty line shipped (aa993d87, 752a551c).
- **W121 applies concretely**: Cycle 3 shipped an unfreeze migration (endpoint_code stamping) — abm's catch-up upgrade CROSSES it → run the second `-u` pass and verify by row count + per-XMLID, exactly as WP-2 already mandates.
- ⌘K palette: not a bug — MAX_ROWS=12 + IA seq 2000+; owner decision pending elsewhere; not your scope.

Purpose: the abm tenant database gets the whole program's payoff — the Zoho People connector with the legacy-ABM feed catalog, the field mappings and transformation rules bound to the owner's real config **"AB Mauri Payroll Vietnam"**, all visible and editable in the redesigned screens. Plus the one comparison the owner explicitly asked for: the hardcoded legacy Zoho secrets vs the `zoho.*` system parameters.

## Owner rulings (FINAL — these override everything else)
1. **Catalog + mappings only.** The connector ships `connection_status='disconnected'`, NO credentials written anywhere. No live Zoho HTTP calls.
2. **Target**: the existing Formula Engine config named **"AB Mauri Payroll Vietnam"** in the `abm` DB. Bind to ITS input columns; do not create/modify configs.
3. **Secrets comparison (report item, not an action)**: compare the hardcoded values in `om_hr_payroll/models/hr_zoho_staging.py:208-210` (client_id `1000.4ZLJF4JSMFITHC41U2VXB7UJWRV11L`, client_secret `989fa207c8fd7360ca8edf5c046d2c406ce9901661`) against the `zoho.client_id` / `zoho.client_secret` (and any other `zoho.%`) `ir.config_parameter` rows in the **abm** DB (check apex `payobook` too, report both). SAME → state "same, fine" in the report. DIFFERENT → report the difference (values redacted to first/last 4 chars) and DO NOTHING ELSE about it — the owner decides. **No code scrub of om_hr_payroll either way this cycle.**
4. abm is not live (owner's earlier ruling), but it shares the cluster with LIVE `payobook` and `acme` — full production discipline applies.

## Preconditions (verify, don't assume)
- IA Cycle 7 ran the abm module catch-up (ledger W120–W126) — **verify** our modules (`pb_hr_payroll_formula`, `pb_integrations`, `pb_import_advanced`, `pb_settings`, `pb_formula_studio`, `pb_hub`, `pb_import_kit`, `pb_sidebar`…) are `state='installed'` on abm. If a needed module is missing, install it with the C7-proven ritual (`update_list()` + targeted `-i`, NEVER `-u base` — see W120-W126 and `docs/handovers/ia/CYCLE7_ABM_AND_BACKLOG.md` §Production discipline, which is binding here too).
- Cycles 1–3 upgraded modules **only on `payobook`** — abm still runs the pre-program schema (the degrade rail cf2d197a is what keeps its board alive). This cycle brings abm current: scoped `-u pb_hr_payroll_formula,pb_formula_studio,pb_settings,pb_import_advanced,pb_hub,pb_integrations` (+pb_import_kit if C1/C2 bumped it ⟲C2) on `-d abm` — which also loads Cycle 3's noupdate catalog/template data rows (W13.1: verify by count after).
- Conventions binding through W130 + C2/C3 additions ⟲. Environment/deploy facts: `CYCLE1_ENDPOINTS_AND_NAV.md` §Environment (admin credential line stale per W129). Read `CYCLE2_REPORT.md` + Cycle 3's report file ⟲C3 for what actually shipped.

## The work

## Pre-verified facts (Fable ran WP-1's read-only inspection 2026-08-20 — do not re-derive)
- Config confirmed: **id 7, "AB Mauri Payroll Vietnam", state=draft** on abm; **40 input rules + 36 formulas**. Input codes include: EMPLOYEECODE, EMPLOYEENAME, EMPLOYEESTATUS, DATEOFJOINING, LASTWORKINGDAY, LOCATION, COSTCENTERFORPAYROLL, BASESALARY, GASALLOWANCE, PHONEALLOWANCE, MEALALLOWANCE, RESPONSIBILITYALOWANCE (sic — typo is IN the config, match it as-is), PARKINGALLOWANCE, TAXIALLOWANCE, RECOGNITIONBONUS, OTHERINCOME, OTHERBONUS, BONUSSTIP, SALESINCENTIVE, THIRTEENTHMONTHSALARY, SEVERANCEALLOWANCE, REIMBURSEMENTPAYMENT, ADJUSTMENT, MARSHINSURANCEREFUNDNONTAX, OT15HOURS, OT2HOURS, OT3HOURS, NIGHTSHIFTHOUR, OTNIGHTSHIFTWEEKDAY, OTNIGHTSHIFTWEEKENDDAY, OTNGIHTSHIFTHOLIDAY (sic), STANDARDWORKINGHOUR, ACTUALWORKINGHOURSINCLUDINGPAIDLEAVE, ACTUALWORKINGHOURSEXCLUDINGPAIDLEAVE, NUMBEROFDEPENDENTS, MONTHLYPIT, OTHERDEDUCTION, SHUIPARTICIPATION, TUPARTICIPATION, PAIDUNUSED-family (fetch the exact remaining codes with the WP-1 query — 40 total). Mapping is direct: legacy advantage codes GAZ/PHONE/MEAL/RESP/PARK/TAXI → the *ALLOWANCE inputs; OT buckets 150/200/300% → OT15HOURS/OT2HOURS/OT3HOURS; nightshift 210/270/390 → the OTNIGHTSHIFT* trio; attendance seconds→hours → STANDARDWORKINGHOUR + the two ACTUALWORKINGHOURS inputs; dependent count → NUMBEROFDEPENDENTS.
- **Secrets comparison RESOLVED (owner-confirmed 2026-08-20)**: the `zoho.*` params live on the LEGACY production system (none exist on this cluster). Owner showed them: client_id `1000.A5Q405LJ…`, secret `fc10d02bb…` — **DIFFERENT from the hardcoded pair** (`1000.4ZLJ…`/`989fa207…`), i.e. the hardcoded block is an old, separate OAuth client. **Owner ruling: do NOT remove the hardcoded code yet** — the parameters are being re-homed into the new Integration configuration screens; once the owner has tested those, removing the hardcoded block becomes a BACKLOG item (record it in your report's owner-decisions section as: "backlog — scrub om_hr_payroll hardcoded Zoho creds + the UserError echo after owner signs off on the new credential screens; owner also to revoke the old client in Zoho's console"). Nothing in this cycle touches om_hr_payroll.
- abm module states: all program modules installed but at PRE-program versions (pb_hr_payroll_formula 19.0.1.48.4, pb_formula_studio 19.0.1.69.0, pb_import_advanced 19.0.1.1.0, pb_settings 19.0.1.0.0, pb_integrations 19.0.1.2.0, pb_hub 19.0.1.2.0) → WP-2's `-u` list is exactly right. `pb_demo` is UNINSTALLED on abm (correct — keep it so). `om_hr_payroll` installed 19.0.1.0.2 but the legacy `zoho_staging_data` table does NOT exist on abm (models likely never loaded there; context only).

### WP-1 — Read-only inspection (FIRST, before any write)
On the server, against `abm`:
1. Config: `SELECT id, name, state FROM hr_formula_config WHERE name ILIKE '%mauri%'` → confirm "AB Mauri Payroll Vietnam"; list its input rules: id, code, name, column letter where `column_type='input'`. Capture the full list in the report.
2. `SELECT key, value FROM ir_config_parameter WHERE key LIKE 'zoho%'` on abm AND on payobook → the secrets comparison (ruling 3).
3. Module state per Preconditions.
4. Legacy tables presence: `zoho_staging_data` / `zoho_employee_data` row counts (context for the report only).
5. Does abm have demo/pb_demo installed? (It should NOT get demo connectors — if pb_demo is installed there, note it and ensure the seeding below is not demo-flagged.)

### WP-2 — Bring abm current (module upgrade)
Full ritual; fresh staging NOT needed (the shared addons tree is already current from C1–C3 deploys — but verify tree versions = repo for the whole reverse-dep closure first, W118). Window shape = **W136's stall-proof unit** (stop→poll-zero→upgrade→`EXIT=$?`→`service start` INSIDE the unit), with W128's pre-stop `find -newermt` foreign-file check.
Rules that bit Cycle 7 doing exactly this job — obey them:
- **W120**: your `-u` list's reverse-dep closure may drag excluded modules to the DISK version — compute the closure, check it against your intentions, and the post-run evidence is a per-module VERSION DIFF, not a count.
- **W121**: a catch-up `-u` that crosses a noupdate-unfreeze migration needs a SECOND `-u` pass, and a version number never proves data rows landed — verify Cycle 3's catalog/template rows on abm by **row count + per-XMLID check** (new noupdate records DO insert on first load; it's updates they skip — still verify, don't assume).
- **W124**: if anything in the delta gained a models/ package or an import-time patch since abm's last restart-exposure, the restart is part of the deploy.
- **W122** (only if you run any suite against a tenant/clone): `--db-filter='^<db>$'`, and diff failure SETS against a baseline before believing any red.
Evidence: EXIT=0, clean log, endpoint/template tables exist on abm, Cycle 3's rows counted on abm, per-module version diff table, payobook + acme untouched (log grep + health 200 before/after the window).

### WP-3 — The seeding (ORM, idempotent, backend)
Mechanism ⟲: prefer JSON-RPC against the running registry (shell needs the service stopped — the ledger's shell-vs-registry-lock rules); mint access per W129's temp-user procedure ON abm (single-company, removed after) or reuse whatever mechanism C7's report proved for driving abm. All writes idempotent (search-before-create by code/output_key/source_field), so a re-run creates nothing.

Seed on abm:
1. **Connector** "Zoho People (ABM)": `connector_type='zoho'`, `auth_type='oauth2'`, `connection_status='disconnected'`, country VN, NO credential fields written. If Cycle 3's create-hook auto-instantiates the catalog ⟲C3, creating the connector gives the 7 endpoints; else run `action_sync_endpoint_catalog()`.
2. **Field mappings** bound to "AB Mauri Payroll Vietnam" inputs: apply the vendor template (`action_apply_mapping_template(config_id)`) first, then the ABM-specific pass — for each input rule of the config, match via the legacy payslip code map (`om_hr_payroll/models/hr_payslip.py:333-389`: ACTBASE→actual_basicsalary, OT15→ot_15amount, SIEIGHT→social_ins8, MONPIT→monthly_pit, NETPAY→net_pay, TCTE→total_cte, …) composed with the staging-field→Zoho-key renames (the CYCLE3 handover's tables). Where a config input has no legacy/Zoho counterpart → leave unmapped, add to the report's unmatched table. Where a Zoho field has no config input → same, other direction. **Do not invent mappings.**
3. **Transformation rules** from Cycle 3's rule templates (OT buckets, DEPCOUNT, WORKEDHRS) — instantiate for the connector; plus any abm-specific python transform lines the C3 tables mark as backend-seeded (H:MM parse, gender lower) if the template path didn't already create them ⟲C3.
4. **Endpoint stamps**: every mapping carries the right `endpoint_id` (employees feed for master-data fields; OT/attendance outputs whichever C3 established).

### WP-4 — Validation on abm (Chrome MCP)
Via the abm tenant host (wildcard DNS: `abm.payobook.com` — verify it resolves/serves; else Host-header against 8069 the way C7 validated ⟲). Temp validation user on abm (W129/W130 procedures).
Walkthrough, screenshots at each step: Settings → Integrations (the C1 deep-link — on abm the category card count decides page-vs-direct ⟲C2); the Zoho People (ABM) connector card shows the feed catalog with legacy-ABM badges; connector cockpit strip: feeds present, disconnected status honest, credentials panel shows all "Not set"; Mapping Studio: FROM = Zoho People (ABM)·Employees, TO = "AB Mauri Payroll Vietnam", the seeded wires render with transform pills; open one transform popover (÷3600) — preview behaves with no store data (empty-sample path must not crash); everything editable (draw + delete a scratch wire, confirm delete). Zero console errors; payobook/acme health checks bracket the session.

### Binding non-goals
No om_hr_payroll edits. No credentials written on any DB. No Zoho HTTP traffic. No pushes. No demo data on abm. Never stage `ABM/`, `.claude/settings.json`, `thaco/`. No changes to payobook/acme data. The seeding script lives in the repo (e.g. `tools/abm_seed_integrations.py` or a `pb_*` module hook — your call, report it) so it is versioned; ops evidence lives in the report.

## Numbered evidence items (this cycle is ops-heavy; each needs proof in the report)
1. WP-1 inspection tables (config + input codes; zoho params comparison verdict; module states; legacy row counts).
2. abm upgrade EXIT=0 + catalog/template row counts on abm + payobook/acme unharmed evidence.
3. Idempotency: seeding run twice → second run creates 0 records (counts before/after).
4. The mapping table: config input code → Zoho source path → transform → endpoint, plus both unmatched tables.
5. Chrome walkthrough screenshots (≥6 states above).
6. Temp user created and removed (show absence after).
7. Full scoped test-suite run still green on the REPO side if any repo code changed (seeding script only ≠ module code; state which).
8. Ledger entries (W-next) + `CYCLE4_REPORT.md` committed with the full report.

## Report back
The secrets verdict FIRST (same/different — redacted values if different). Then evidence 1–8, commit hashes, deviations, owner-decision items (credentials wiring when ready; the om_hr_payroll scrub decision; anything unmatched that needs the owner's payroll knowledge).
