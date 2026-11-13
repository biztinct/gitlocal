# MAPFIX — Readable codes, complete mapping, silent errors: conventions + gotcha ledger

**STATUS: PROGRAMME COMPLETE — Phases A, B, C, D, E and F designed, built, deployed and live on
abm · acme · payobook · payobook_template (2026-08-23).** Final module versions:
pb_hr_payroll_formula **19.0.1.72.0** · pb_formula_studio **19.0.1.126.0** ·
biz_theme **19.0.1.4.0** · om_hr_payroll 19.0.1.0.2 (never touched — CR1). Commits: Phase A
`f658974f`, Phase B `470590bd`, Phase C `6f6066e1`, Phase D `c79c15a8`, Phase E `15071c57`,
Phase F = the commit that carries this line (a hash cannot name itself; it is quoted in the Phase F
report). **Pushed through `15071c57` (Phase E); Phase F is NOT pushed.**

Follow-on programme to COLROLES (see `docs/handovers/COLROLES_LEDGER.md` — its standing rules and
gotchas CR1–CR33 STILL BIND; this file adds MF-numbered entries). Phases: A codes+rename,
B mapping catalogue + re-routing + reconciliation, C error-dialog suppression + Primary Key guard,
D the five defects the owner reported against the live Phase-B board, E the two defects
reported against the live Phase-D board, F the filtered-wire defect reported against the live
Phase-E board plus the two follow-ups E deferred (MF36).

## Standing rules (inherited from COLROLES — re-read that ledger, these are the critical few)

- **White-label absolute**: no user-visible string may contain "Odoo".
- **Deploy ritual**: rsync → `sudo chmod -R a+rX` the synced dirs (**CR6** — `rsync -a` preserves Mac
  0600 modes; the odoo user then cannot read `__manifest__.py`, the upgrade logs "not installable,
  skipped" and **odoo-bin still exits 0**) → stop → detached `systemd-run` unit looping
  **`sudo -u odoo /odoo/odoo-server/odoo-bin -c /etc/odoo-server.conf -d <db> -u <mods>
  --stop-after-init`** over **abm acme payobook payobook_template** with EXIT sentinel → start →
  **verify `ir_module_module.latest_version` in psql on all 4** (with `sudo -u postgres`, MF17)
  before believing the deploy.
  **The `sudo -u odoo` is not optional (MF35, corrected here in Phase F):** `systemd-run` runs the
  unit as ROOT, odoo-bin then fails peer auth with `FATAL: role "root" does not exist` on every DB
  in about ninety seconds, and the loop still writes `EXIT[db]=1`. The service itself runs as `odoo`
  (`/etc/init.d/odoo-server`, `USER=odoo`). This ritual as written is the one Phase F used, green
  on all four databases first try.
- **CR20**: a browser tab holding a websocket hangs a detached `odoo-bin` in "Initiating shutdown";
  park validation tabs on `about:blank` first, confirm zero pids BY PID. Test output goes to
  `/var/log/odoo/odoo-server.log` (grep -a), not the /tmp sentinel.
- **CR33**: the documented apex password no longer authenticates over RPC — drive live checks
  through the browser session.
- Live role/mapping validation must use **abm** (payobook's role-bearing configs are company 2 and
  invisible to the apex admin session).
- Migrations: `migrations/<version>/post-<sentence_slug>.py`, WHY/WHAT-IS-NOT-TOUCHED docstring,
  `table_exists` guard, idempotent, log per-DB counts.
- Commit per phase, explicit staging, **do not push**.
- Versions at programme start: pb_hr_payroll_formula **19.0.1.68.0** · pb_formula_studio
  **19.0.1.114.0** · biz_theme **19.0.1.3.0** · om_hr_payroll 19.0.1.0.2 (leave untouched — CR1).

## Owner decisions (locked)

- MF-A1 **Code style**: readable words, **≤12 chars**, accent-folded, noise words dropped
  ("Constant"), acronyms + trailing numbers preserved. Examples the owner approved:
  `Chi trả phép năm chưa sử dụng` → `CHIPHEPNAM`; `Tỷ lệ % tạm ứng thưởng HQCV` → `TYLETUHQCV`;
  `Constant SI-HI-IU Total 10.5%` → `SIHIIUTOT105`; `Employee Status` → `EMPSTATUS`.
- MF-A2 **Existing codes: auto-rename everything now** on all 4 DBs via migration — atomic and
  orphan-safe (rules + `hr.contract.advantage.template.code` + `hr.salary.rule.code` together),
  with a verified before/after per DB. Owner accepted the risk; the implementation must earn it.
- MF-B1 **Field catalogue**: generated, not hand-curated — every writable stored field on
  hr.employee/hr.contract **including many2one**, grouped into lanes, technical fields denied,
  search retained for the tail.
- MF-B2 **Colour coding is a suggestion, not a verdict**: a contract-component card must be
  re-routable to a native Employee/Contract/Bank field (which demotes it from being a component),
  and a plain column must be promotable to an amount OR text component.
- MF-B3 **Re-routing a component that already has contract data: ALLOW and KEEP the history.**
  The component stops being written to; existing `hr.contract.advantage` lines and their
  `hr.contract.advantage.change` audit rows stay as historical record. Nothing is destroyed.
  (This SUPERSEDES the Phase-3 "detach refusal" behaviour for the re-route path.)
- MF-B4 **Reconciliation step**: before finishing, list every column with no native mapping and no
  component; pre-tick all as "become a contract component"; the user may untick individual rows to
  leave them imported-but-unused (role `reference`). Nothing is left silently unresolved.
- MF-C1 **Error technical details: hidden from users, still available in developer mode.** Suppress
  wherever a normal user can see them — including the portal/website/login bundles, which today get
  the stock dialog entirely.
- MF-C2 **Primary Key**: guard at the field (`required` on the Select Worksheets step) so the user
  never reaches the server raise. Note the raise was never removed — `git log -S` shows it was ADDED
  in 31936f64; the field has never had `required` in this repo's history.
- MF-A3 **CLOSED 2026-08-23 — legacy short-but-lossy codes stay as they are.** Phase A's
  "already conforms" skip left codes like `MCLNGHL` (from `Mức lương HĐLĐ`, accents deleted rather
  than folded) untouched, where the new generator would say `MUCLUONGHDLD`. The owner was asked and
  chose to LEAVE THEM: they are short and they work, re-deriving means more churn on live data for
  cosmetic gain, and the skip is load-bearing — it is what protects `BASIC`, which
  `_get_formula_input_values` reads by name. **Do not write a follow-up migration for these.**

## Verified facts (do not re-derive)

- **Root cause of long/ugly codes**: `re.sub(r'[^A-Za-z0-9]', '', label)` is ASCII-only, so accented
  Vietnamese letters are DELETED, not folded — `Chi trả phép năm chưa sử dụng` → `CHITRPHPNMCHASDNG`
  (lossy AND long). `strip_accents()` already exists at
  `pb_hr_payroll_formula/models/column_role_classifier.py:207-214` (handles `đ`, which NFD does not
  decompose) — reuse it.
- **The converter contract, precisely** (`docs/FORMULA_ENGINE_CONVENTIONS.md` C5 vs C13 — they
  CONTRADICT; C13 is correct and empirically verified):
  - **HARD**: codes must be underscore-free. `[A-Z]+` / `[A-Z][A-Z0-9]{1,}` exclude `_`, so
    `SI_EMP` survives raw into the eval → NameError → 0.
  - **NOT a correctness issue**: substring collisions. `_convert_excel_to_python`
    (`pb_hr_payroll_formula/models/formula_rule.py:871-884`) uses a greedy `[A-Z][A-Z0-9]{1,}` and a
    `(?<!')` lookbehind, so `SI`/`SIEMP` both resolve. Non-substring is cosmetic. **Phase A should
    correct C5 in the conventions doc** rather than perpetuate the contradiction.
  - **Real floors**: ≥6 normalized chars to stay in the fuzzy header-match fallback
    (`payroll_import_batch.py:2478`, `:2509`); ≥3 for `_compute_dependencies`' `code_refs`
    (`formula_rule.py:1247`); ≥2 for the converter's code pass. A code must NOT equal any
    `column_letter` in its config or `rename_component` skips the formula rewrite
    (`pb_formula_studio.py:3879`) and the letter pass hijacks it.
- **Generators** (four): live import = `multisheet_import_wizard._generate_code` (:3264-3294,
  cap 40) → `_dedupe_code_c5` (:3296-3347, letter suffixes, always terminates);
  `formula_import_wizard._generate_code_from_label` (:1881-1902, cap 10, DIGIT suffixes that
  truncate the base); `excel_connector._generate_code_from_header` (:944-981) still emits
  **underscores** (legacy fallback, only when no `code_generator` is injected);
  `_gen_rate_table_code` (`pb_formula_studio.py:3593-3605`, shares the rule-code namespace).
- **`rename_component`** (`pb_formula_studio.py:3833-3918`) rewrites referencing formulas +
  sample-data JSON + writes a version row. **Gaps it must gain in Phase A**:
  `hr.contract.advantage.template.code` (**the biggest orphan risk** — matched by STRING at
  `payroll_import_batch.py:3083-3108`; renaming without it silently mints a second template and
  every existing contract line stays on the old one → amounts read 0), `hr.salary.rule.code`,
  `hr.formula.budget.line.code`, boundary/shadow/simulation code strings, and a batch mode.
- **`hr.formula.rule.code` has NO shape constraint** (only `unique(code, config_id)`,
  `formula_rule.py:1508-1513`). The reusable validator is
  `formula_config_template._assert_codes_convertible` (`formula_config_template.py:185-212`).
  **Live C5 violators that must be fixed before any constraint is added**:
  `pb_formula_studio.py:6904-6907` (`add_component` mints `NEW_1`) and demo data
  `pb_hr_payroll_formula/data/demo_formula_config.xml:80,91,102,113` (`SI_EMP`, `TOTAL_DED`).
- **Short codes change behaviour elsewhere**: `_group_for` (`pb_formula_studio.py:78-92`) matches
  `SI`/`HI`/`UI`/`TAX`/`DED` as SUBSTRINGS of the code — a short code containing `SI` lands in
  Deductions (the CR10 trap, flagged at `pb_formula_studio.py:3959-3960`). Same for
  `_is_employee_code_rule` (`payroll_import_batch.py:2981-3016`) and
  `column_role_classifier._marker_hit` (:298-303).
- **Regression gates (MANDATORY after any code/converter change)**:
  `python3 pb_hr_payroll_formula/tools/excel_semantics_battery.py` (70+ cases, exit 0 = green) and
  `python3 pb_hr_payroll_formula/tools/import_resolution_battery.py`.
- **Mapping catalogue today**: `_EC_CURATED` (`pb_formula_studio.py:5005-5015`) = 15 employee + 7
  contract hand-typed fields; `name` absent. `_EC_TTYPES` (:5003) has **no `many2one`**, so
  department/job/calendar/company cannot be wired — even though `_coerce_mapped_value`
  (`payroll_import_batch.py:1109-1170` pre-P1) does m2o search-by-name-else-create and
  `_sync_employee_contract_mirror_fields` mirrors exactly those four m2o fields. Search exists:
  `ec_search_fields` (:5210), `ec_model_fields` (:5221), right items `_ec_right_items` (:5074).
  Bank lane roles `_BANK_LANE_ROLES` (:5026), `b:` id prefix.
- **Error dialogs**: `biz_theme/static/src/js/biz_error_dialogs.js` — `BizErrorDialog` (:108),
  variant map (:69-79), registry force-override (:196-200), `technicalDetails` getter (:141-149),
  `showTechnicalDetails` already gated on `window.odoo.debug` (:151-160), `stripOdoo` (:212) applied
  ONLY in `bizRpcFallbackHandler` (:278-279) / `bizDefaultHandler` (:302-303) — **not** on the
  registry-routed UserError path that produced the owner's screenshot. Template
  `biz_theme/static/src/xml/biz_error_dialogs.xml:45-54`; "Copy details" (:56-59) gated on
  `hasDetails`, NOT on `showTechnicalDetails`.
  **Coverage gaps**: biz_theme registers error assets in `web.assets_backend` ONLY
  (`biz_theme/__manifest__.py:73-75`) → portal/website/login get stock "Odoo Error" + traceback;
  `RedirectWarningDialog` not overridden; `WarningDialog` used directly at
  `web/static/src/model/relational_model/relational_model.js:719`; `error_service.js:117` has a
  hardcoded "…Odoo framework…" string no seam reaches.
  `"Odoo Server Error"` origin: a plain (untranslated) literal in core `odoo/http.py` plus vendored
  copies at `web/controllers/export.py:639,687`, `web/controllers/report.py:147`,
  `report_xml/controllers/report.py:92`; re-generated client-side at
  `web/static/src/core/errors/error_dialogs.js:120-130`. Reaches the dialog via `rpc.js:59-65` and
  is baked into the traceback string at `error_utils.js:123`.
  biz_debrand's JS seam (loaded in BOTH bundles) is
  `biz_debrand/static/src/js/biz_debrand_runtime.js` (`__manifest__.py:34-41`).
- **Primary Key**: raise at `multisheet_import_wizard.py:544-545` in `action_process_sheets` (:524),
  triggered by the "Select Columns" button (`multisheet_wizard_views.xml:391-394`); field rendered
  at `:71-74` inside `<div invisible="state != 'select_sheets'">` with **no** `required`; field def
  `:128-131`; the only onchange (:173-182) is a propagator that returns early when empty.

## Phase status

- **Phase A — DONE, live on abm · acme · payobook · payobook_template (2026-08-23).**
  Versions: pb_hr_payroll_formula **19.0.1.69.0** · pb_formula_studio **19.0.1.115.0**.
  Renames: abm 64/99, payobook 152/1360, acme & payobook_template 0 (no structures).
  5 `hr.contract.advantage.template` codes moved alongside; 0 refused, 0 withdrawn, 0 orphans.
  Compute neutrality: 0 cell diffs over 19 real payslips + a synthetic fingerprint of all 19
  configurations. Live tests on abm: 32/32.
- **Phase B — DONE, live on abm · acme · payobook · payobook_template (2026-08-23).**
  Versions: pb_hr_payroll_formula **19.0.1.70.0** · pb_formula_studio **19.0.1.117.0**.
  Catalogue: `_EC_CURATED`'s 15 employee + 7 contract hand-typed names replaced by a generated
  catalogue — **193 destinations on abm** (134 hr.employee + 55 hr.contract + 4 bank cards), in
  eight lanes: Identity 3 · Personal 8 · Contact 5 · Job & organisation 7 · Contract terms 7 ·
  Bank account 4 · Other employee fields 114 · Other contract fields 45.
  Contract-component cards are wirable and re-routable; existing `hr.contract.advantage` data is
  kept as history (MF-B3). Reconciliation ships as a footer bar + dialog; the problems rail's
  `idunmapped`/`bankunmapped` now read the SAME `_ec_unresolved` set (abm: board 5, rail 5).
  Live tests on abm: 18/18 (12 new + the 6 COLROLES role tests).
- **Phase C — DONE, live on abm · acme · payobook · payobook_template (2026-08-23).**
  Versions: biz_theme **19.0.1.4.0** · pb_hr_payroll_formula **19.0.1.71.0**.
  MF-C1: `stripOdoo` moved to the top of `biz_error_dialogs.js` and applied inside
  `BizErrorDialog` itself (message getter + every part of `technicalDetails`), so the
  registry-routed `UserError` path is sanitised too; "Copy details" re-gated from `hasDetails`
  to `showTechnicalDetails`; `WarningDialog.prototype` and `RedirectWarningDialog.prototype`
  patched (title + message) — RedirectWarning kept its own class so its action button survives;
  the error JS/XML/SCSS now also ship into **`web.assets_frontend`** (portal/website/login).
  MF-C2: `required="state == 'select_sheets'"` on the multisheet wizard's Primary Key field
  (state-conditional — see MF19), plus a "(required)" placeholder/bullet and a fuller `help`.
  The server-side raise was NOT removed and still fires for RPC callers.
  Regression guard: 5 hoot tests in `biz_theme/static/tests/biz_error_dialogs.test.js`
  (`web.assets_unit_tests`), 5/5 green live at `/web/tests?filter=biz_error_dialogs`.
  Live tests on abm: 10/10 numbered cases.
- **Phase D — DONE, live on abm · acme · payobook · payobook_template (2026-08-23).**
  Versions: pb_hr_payroll_formula **19.0.1.72.0** · pb_formula_studio **19.0.1.121.0**.
  Five owner-reported defects against the live Phase-B board:
  **D1** (crash `'int' object has no attribute 'startswith'`) fixed at BOTH ends — the canvas'
  `case "Enter"` now resolves through the focused side's list instead of reading the shared
  `ui.focusId` raw, and `employee_mapping_create` coerces with `_ec_spec()` and refuses cleanly;
  the same wrong-type guard was applied to `api_/import_/scheme_mapping_create` and every
  `_mapping_delete` in the family (`self._as_id`).
  **D2** — Escape now runs through ONE ladder (`_escape`): menu → transform popover → armed
  component → search text → selected wire; `onSearchKey`'s unconditional `stopPropagation` is gone,
  so the banner's "Esc to cancel" is true from the search box, a card and the board background.
  **D3** — the three hover pills became ONE fixed-width (22px) in-flow `⋮` trigger plus an anchored
  popover menu with a sentence per verb; name and code are legible in every state (0 overlaps over
  19 cards at 1440 and at 1024).
  **D4** — selection destinations print their permitted values with the STORED code
  (`≤4 short values` inline, otherwise `N values — a, b, …` + full list in the tooltip).
  **D5** — many2one behaviour UNCHANGED; the card now says "Creates the … if it does not exist yet"
  or "Must already exist — will not be created", derived from `m2o_creates_missing()`, the import
  batch's own predicate.
  abm board: 193 right cards, 56 notes (24 selection + 32 m2o), whole-board RPC 132 ms / 69 KB.
  Tests: 9 new Python (`TestMappingDefects`) + 12 Phase-B = 21/21 green on abm; hoot 41/41 green at
  `/web/tests?filter=mapping_canvas` (15 of them new). abm left exactly as found (10 mappings, ids
  `1,2,30,31,32,33,35,36,37,38`; rule 662 `DESIGNATION` restored to contract/text/auto).
- **Phase E — DONE, live on abm · acme · payobook · payobook_template (2026-08-23).**
  Version: pb_formula_studio **19.0.1.124.0** (pb_hr_payroll_formula and biz_theme untouched).
  **E1** — a note that had to CUT its value list is now the way to open it. The Phase-D `⋮` popover
  gained a `kind`; `_openMenu`/`_placeMenu`/the scrim/the Escape rung are shared, so there is still
  ONE popover implementation and one MF27 measure-then-place. `_ec_selection_note` emits
  `values: [{key,label}]` + `total` **only when the inline text hid something**, which makes
  "truncated" and "clickable" the same condition on both sides of the wire; a complete note stays a
  `<div>` with no button semantics.
  **E2** — `_ec_is_mappable` asked STORED where it meant WRITABLE (MF30). Catalogue **193 → 236**
  cards; the two card-construction sites are one (`_ec_field_item` resolves lane, lane_order and
  note itself), the appended card is spliced at the end of its own lane (MF32), and a wire to a
  destination the catalogue refuses is kept but marked `warn` (`_ec_unmappable_note`).
  abm board: 236 right cards, 76 notes (30 selection + 46 m2o), 22 of them openable carrying 215
  value rows; whole-board RPC **131 ms / 101 KB** (Phase D: 132 ms / 69 KB — 10.8 KB of the growth
  is the structured value lists, the rest is the 43 extra cards). 0 bounding-box overlaps over 255
  cards / 947 element pairs at 1440 **and** at 1024, hover/focus states included.
  Tests: 6 new Python (`TestMappingSelectionValues`) = 27/27 green on abm; hoot **48/48** green at
  `/web/tests?filter=mapping_canvas` (7 new). abm left exactly as found — 20 mappings, ids
  `1,2,30,31,32,33,36,37,38,50…60`, no `hr.formula.rule` writes; nothing was created or deleted.
- **Phase F — DONE, live on abm · acme · payobook · payobook_template (2026-08-23).**
  Version: pb_formula_studio **19.0.1.126.0** (pb_hr_payroll_formula and biz_theme untouched).
  **F1** — *scrolled out of view ≠ filtered out of the set*. `isFilteredOut(side, id)` is now the
  ONE predicate: the geometry loop skips a wire either of whose ends it excludes, and
  `hiddenWires(side)` is read off that same pass instead of recounting over `ui.geom`. A wire whose
  end is merely SCROLLED past is untouched — it still clamps to the band edge and still aggregates
  into a "N mapped above/below" chip (CR21). A suppressed wire keeps its chip
  (`aggregateDocks(geom, suppressed)`), so it is counted and still reachable — `clickDock` looks in
  both sets and `jumpTo` clears the filter — but it is not DRAWN. A selection that lands on a
  suppressed wire is dropped, so `w`-walking and `selWire` can never point at an invisible wire.
  Live on abm: Bank lane pill → **1 wire drawn, 16 counted, 1 + 16 = 17** (the unfiltered total),
  chips read "5 hidden by filter above" + "11 hidden by filter below"; same numbers for a search
  term, for Unmapped (0 + 17), and for lane + Mapped + search combined; `clear` restores all 17 and
  the chips revert to the "mapped below" vocabulary.
  **F2** — `placeInLane` (`mapping_geometry.js`, the pure kernel) is the client twin of
  `_ec_place_in_lane`; `mapEmpRight` inserts each session extra at the end of its own lane instead
  of concatenating them after the catalogue (MF36 (b)). See **MF40** — the UI cannot currently reach
  this path, so the fix is latent and was validated by driving `addEmpField` on the live board.
  **F3** — `employee_mapping_create` applies `_ec_is_mappable` before writing, refusing with
  `_ec_unwritable_msg` — the same sentence `_ec_unmappable_note` puts in its tooltip, built in one
  place. CREATE only: a pre-existing row pointing at a refused field still loads, still draws its
  wire and still renders `warn`. `b:` bank specs return before the guard and never meet it.
  Tests: 5 new Python (`TestMappingCreateGuard`) — **63/63 green on abm**, 0 failed, 0 errors;
  hoot **60/60** green at `/web/tests?filter=mapping_canvas` (12 new: 9 F1 + 3 F2).
  Board unchanged: 236 right cards, 76 notes, 17 wires, 0 console errors, 0 bounding-box overlaps
  over 255 cards / 139 element pairs at 1440 **and** at 1024.
  abm left exactly as found — `hr_payslip_import_mapping` diffed byte-for-byte before and after
  (20 rows, ids `1,2,30,31,32,33,36,37,38,50…60`), and `hr_formula_rule` for config 14 diffed too
  (99 rows, no demotion). Nothing was created, deleted or moved.

## Gotchas discovered (append per phase, MF-numbered)

- MF1 (A): **`hr.contract.advantage.template` is GLOBAL and shared across structures.** On
  `payobook` every one of the 26 templates is used by rules in BOTH config 5 (VPTQ End Cycle) and
  config 6 (VPTQ Mid Cycle). A template can only carry one code, so a code with a template may
  move only if EVERY rule carrying it moves to the SAME new name — otherwise the structures left
  behind read 0. `_rename_code` therefore refuses a lone rename when siblings exist
  (`siblings_renamed=` is the escape the migration uses), and the migration runs a reconciliation
  pass that withdraws the whole group if the proposals disagree or if any member was skipped.
  Convergence is explicitly allowed: the second sibling finds the old-code template gone and one
  under the new code, which is a no-op, not a collision.
- MF2 (A): **the "already conforms" skip is load-bearing, not just an idempotency trick.**
  `hr_payslip_formula._get_formula_input_values` hard-codes `{'BASIC'|'WAGE'|'BASE': 'wage'}` and
  the `WD_`/`HOURS` code prefixes. `BASIC` exists on 13 payobook configs; renaming it to
  `BASICSALARY` would have silently detached the wage. Skipping every code that is already
  `^[A-Z][A-Z0-9]*$` and ≤12 protects it for free. The cost: lossy-but-short legacy codes
  (`MCLNGHL` for "Mức lương HĐLĐ") are left alone. **Owner decision pending** — a follow-up pass
  could rename by readability rather than by shape, but it needs that hard-coded map fixed first.
- MF3 (A): **substring avoidance must exclude column letters.** `_dedupe_code_c5` treats a
  collision as "exact OR substring". Feed it the config's column letters and every real code
  "collides" with column `A`. `reserved` is therefore tested for EQUALITY only
  (`component_code._collision_tests`).
- MF4 (A): **de-duplication has to respect the length cap.** `SIHIIUTOT105` + `A` is 13 characters.
  `dedupe_code_c5(..., max_len=12)` trims the base to make room. Before bolting a letter on,
  `build_component_code` retries the candidate WITH its leading noise word restored — which is what
  distinguishes "Constant SI-HI-IU Total 10.5%" (`CONSIHIIU105`) from "SI-HI-IU Total 10.5%"
  (`SIHIIUTOT105`) readably instead of as `SIHIIUTOT10A`.
- MF5 (A): **`total` must NOT be dropped as a leading noise word.** The handover's suggested
  NOISE_WORDS list contains it; dropping it turned "Total Deduction" into `DEDUCTION`, sitting next
  to "Other Deduction". `LEADING_NOISE` is a deliberately narrower subset
  (`constant/const/column/col` + VN fillers). And a leading noise word is only dropped while a real
  WORD token still follows — otherwise `COL2024` became `C2024`.
- MF6 (A): **`_group_for` drift is real and was accepted.** Renaming changes which lexicon
  substrings a code contains, so 9 abm and 16 payobook columns move outline bucket (e.g.
  `TOTALCOSTTOEMPLOYER`→`TOTACOSTTOER` leaves Totals for Earnings). Matching the lexicon against
  the accent-folded NAME as well would fix it on abm (0 changes today, drift 9→1) but re-buckets
  **95** payobook columns immediately, because folded Vietnamese is full of `HI`/`SI`/`TAX`
  substrings ("Chi…" contains "HI"). CR10 stands: `_group_for` was left alone. Every caller is
  display-time (studio outline, explain trace, suggested payslip section) — nothing persists a
  grouping, so no live payslip was re-sectioned.
- MF7 (A): **`import_resolution_battery.py` could not run at all on a bare interpreter.** The
  wizard imports `markupsafe` (ships with Odoo, not with system python3, and PEP-668 blocks
  `pip install`), and the battery's shim only rewrote `..formula_engine` imports, not `..models`.
  Both are now shimmed inside the battery. A "mandatory gate" that nobody can execute is not a
  gate — check that the batteries actually RUN before trusting a green.
- MF8 (A): **`hr.payslip.line` is not a free-form row.** It refuses a create with no `contract_id`
  (om_hr_payroll), and the table has NOT NULL on `category_id` and `salary_rule_id`. Any fixture
  that fabricates payslip history needs all three; three test runs were burned discovering them one
  at a time.
- MF9 (A, environment): CR20's shutdown hang fires even with **both browser tabs parked on
  `about:blank`** — the detached `odoo-bin` sat at ~4% CPU for 10+ minutes after
  `odoo.tests.result` had already been written. Read the RESULT out of
  `/var/log/odoo/odoo-server.log` and stop the unit; do not wait for the sentinel. And check for
  zero pids BEFORE launching the next unit — two `odoo-bin` processes upgrading the same database
  concurrently is a much worse problem than a slow shutdown.
- MF10 (A): three live paths copied a code in from outside without normalising it, and the new
  shape constraint would have raised on all of them:
  `hr_payroll_structure_formula.action_create_formula_config` (copies `hr.salary.rule.code`
  verbatim — those genuinely are `SI_EMP`, `BASIC_SALARY`), `formula_import_wizard._import_from_json`
  (`IMPORT_%d` fallback plus any code inside the uploaded file), and `pb_formula_studio.add_component`
  (`NEW_1`). All three now route through `component_code.normalize_code`, which passes a conforming
  code through UNCHANGED. When adding a constraint, grep for who WRITES the field, not just who
  reads it.
- MF11 (B): **on Odoo 19 `hr.employee.department_id`, `job_id` and `resource_calendar_id` are NOT
  STORED.** The stored copies live on `hr.contract`, where they are declared
  `compute='_compute_employee_contract', store=True, readonly=False`
  (`hr_contract/models/hr_contract.py:28,30,37,51`). Two consequences, both of which broke a first
  cut of this phase:
  (a) a `store=True` catalogue rule offers Department **on the contract only** — so a lane may not
  be tied to one model. `_EC_LANES` therefore reads `(key, ((model, names), …))` and
  "Job & organisation" draws from both, because the reader looks for "Department" under that
  heading whichever record holds it;
  (b) **"a compute without an inverse is not writable" is FALSE for a stored compute.** That rule
  belongs to UNSTORED computes; a stored one with `readonly=False` is Odoo's ordinary editable
  computed field, and excluding it removed the four most-wanted destinations on the board. The
  guard is now `field.compute and not field.store and not field.inverse` — which `store=True`
  already covers, and is kept only so the reasoning is visible in the code.
- MF12 (B): **an asset-bundle rebuild is triggered by the module UPGRADE, not by the file's
  mtime.** A `.scss` copied into `/odoo/odoo-server/addons/` AFTER the `-u` had already run served
  the OLD compiled bundle indefinitely: `getComputedStyle(...).position` still read `static` after
  a hard reload with `ignoreCache`, while the OWL templates (which shipped in the same `-u`) were
  current — so the markup was new and its CSS was not, which is the single most confusing shape a
  stale deploy can take. Either re-run `-u` after any late asset edit, or purge with
  `env['ir.attachment'].search([('url','=like','/web/assets/%')]).unlink()` per database. The
  browser cache is never the culprit; the attachment is.
- MF13 (B): **CR22's lesson, repeated verbatim.** A card grew from one hover verb to three; three
  buttons IN THE FLOW reserve their width even at `opacity: 0`, and `.mc-item-label > span` has
  `min-width: 0` — so every left card rendered its name as a **single character** while looking
  perfectly fine in the DOM. Neither a unit test nor an RPC probe can see it; only a screenshot
  can. `.mc-item-acts` is now `position: absolute` over the right of the card behind a short white
  fade. Any future per-card affordance must come out of the flow the same way.
- MF14 (B): **a payroll column that prints on the payslip HAS a destination.** The handover's
  unresolved rule excluded only formula-fed payroll columns, which on a VPTQ-shaped structure would
  have listed dozens of pay columns in a dialog whose rows are **pre-ticked to become contract
  components** — a destructive default dressed as tidiness. `_ec_unresolved` therefore also treats
  `column_role == 'payroll' and appears_on_payslip` as resolved (the payslip line IS where the
  value lands). Documented deviation; abm's count is 5, all of them people columns.
- MF15 (B): **promoting to an AMOUNT component makes the card vanish.** CR-A2 gives an amount
  component role `payroll`, and the people board hides the payroll lane until asked — so the card
  the user just acted on disappears from under the pointer (W40). Both promotion paths
  (`mapEmpAction`, `applyReconcile`) now switch `mapEmpPayroll` on before reloading. Any future
  verb that can change a column's ROLE has to ask whether the new role is one this board shows.
- MF16 (B): **`employee_mapping_create` returning a `msg` on SUCCESS was a new shape.** `mapDraw`
  only ever read `msg` on `ok === false`, so the demotion sentence — the entire reassurance that
  contract history survives a re-route — was computed, returned and thrown away. Live-verified
  after the fix ("Department now goes to Department instead of the contract."). When a generic
  dispatcher gains a success payload, grep for every caller of that dispatcher, not of the RPC.
- MF17 (B, environment): the apex/abm **`psql` invocation in the deploy ritual needs
  `sudo -u postgres`** — `psql -U odoo` fails peer authentication as `ubuntu` and bare `psql` fails
  with `role "ubuntu" does not exist`. A CR6 verification that silently errors is a CR6
  verification that did not happen.
- MF18 (C): **on the frontend a named server exception never reaches a dialog at all.** Portal
  and website populate the `error_notifications` registry with every one of them
  (`AccessError`, `UserError`, `ValidationError`, `MissingError`, `SessionExpired`, `504`…), and
  `rpcErrorHandler` checks that registry FIRST — so a live `UserError` on `/my` is a toast, not a
  dialog, whatever the `error_dialogs` registry says. On top of that,
  `swallowAllVisitorErrors` (`error_handlers.js`, **sequence 0**) discards every error when
  `!user.isInternalUser && !odoo.debug && !session.test_mode` — a public visitor sees nothing at
  all. So the handover's gap 1 is real but narrower than it reads: the stock, ungated traceback
  dialog was reachable on frontend pages only for **unnamed** failures (client-side JS crashes,
  raw 500s with no `exceptionName`) and only for **internal users or debug sessions**. That is
  exactly what the new `web.assets_frontend` entry now covers — verified both ways on `/my`.
  Lesson: before shipping a component into a second bundle, check which *handler* actually runs
  there; the registry being right proves nothing on its own.
- MF19 (C): **a parent `<div invisible="…">` does NOT make its fields invisible for validation.**
  `record._isInvisible(fieldName)` (`web/static/src/model/relational_model/record.js:782-785`)
  evaluates the FIELD's own `invisible` modifier and nothing else, and `_checkValidity` skips a
  field only on that basis. A plain `required="1"` on a field parked inside a step-gated div is
  therefore enforced on EVERY step of the wizard — including the ones where the field is not
  rendered, which dead-ends Back and Next. The Primary Key guard is written
  `required="state == 'select_sheets'"` for that reason; the handover's "the web client skips
  required-validation there" was wrong, and the state-conditional fallback it offered is the only
  correct form.
- MF20 (C): **a visibility gate has to be checked against every string that names the thing it
  hides.** Gating "Copy details" on developer mode left the crash variant still saying "if it
  keeps happening, copy the details and share them with support" — an instruction the user now
  has no button for. `VARIANTS.crash.hint` was rewritten with the gate, not after it.
- MF21 (C): **biz_debrand's `_t` patch masks whether your own patch works.** `_t("Odoo Warning")`
  already comes back as "Payobook Warning" on every DB where `biz_debrand` is installed, so both
  the patched and unpatched `WarningDialog` render a clean title and the live check proves
  nothing. Probe with a LITERAL the translation seam cannot see — mounting the dialog with
  `{title: "Odoo Warning", message: "Odoo Server Error: probe"}` returned "Warning" /
  "Server Error: probe", which is the only evidence that the component-level scrub is live.
  (The scrub still earns its place: it is what makes `biz_theme` correct as a standalone base
  with no brand overlay, and it is the only thing that reaches the untranslated literals —
  `odoo/http.py`'s "Odoo Server Error" and `error_service.js`'s third-party-script traceback.)
- MF22 (C, environment): the required-field toast ("Missing required fields") is rendered in the
  main notification container, which a **full-screen wizard dialog covers** — the only visible
  signal of the block is the red field label. Adequate here, but a required guard inside a
  fullscreen modal must never depend on the toast being seen.
- MF23 (C, testing): the multisheet wizard refuses a plain workbook —
  "Could not detect header rows from color-coded Excel file". Any end-to-end fixture for it has
  to carry the CR-A4 colour convention; `ABM/ABM Template.xlsx` in the repo is a known-good one
  (99 components, single sheet `SEVL`, PK header "Employee Code").
- MF24 (D): **`x or ''` is a FALSY guard, not a TYPE guard, and the difference is a crash.**
  `employee_mapping_create` read `spec = target_spec or ''` and then called `spec.startswith('b:')`.
  `123 or ''` is `123`, so the guard let an integer through untouched and the user got
  `'int' object has no attribute 'startswith'` — from a line written to make exactly that
  impossible. The client had sent it because `ui.focusId` is ONE value shared by both columns
  (see MF25). Every RPC in the family had the same shape somewhere: `.startswith` on a value that
  might not be a string (`api_`, `import_`) or `int()` on one that might not be a number (`scheme_`,
  every `_delete`). When an id crosses a browser boundary, coerce it; a `msg` refusal is always
  better than a traceback on a screen whose job is to be friendly.
- MF25 (D): **one focus value for two columns is a bug waiting for a keystroke.** The arrow keys
  had always resolved `ui.focusId` through the focused side's list (`findIndex`, falling back to
  index 0), so the mismatch was invisible; `case "Enter"` read it raw, and "Send to a field
  instead…" is the one verb that flips `focusSide` to `right` while `focusId` still holds a LEFT id.
  The fix resolves through the list like its neighbours — and STRICTLY, with no index-0 fallback:
  moving a focus ring onto the first row is harmless, drawing a WIRE to it because nothing was
  focused is a write nobody asked for. `_relocateFocus` (called when a search applies) is what
  keeps the gesture usable: it puts a visible focus on the top hit, so "type, press Enter" still
  completes and the card it acted on is the card that was highlighted.
- MF26 (D): **CR22/MF13, third act — and the lesson is now general.** Three verbs IN the flow
  crushed the card's name to one character (MF13); the same three lifted OUT of the flow covered
  the name and code instead (this phase's D3). Both are one failure: *an affordance whose width
  depends on how many verbs there happen to be cannot share a line with the text.* The answer is a
  trigger of a CONSTANT width, in the flow, where `min-width: 0` ellipsises the label beside it and
  a bounding-box assertion can prove no overlap in any state — and the verbs move into a menu,
  which has room to say what each one does. Deliberately visible at rest (dimmed): hover-only
  discovery has now proved fragile twice, and touch has no hover at all.
- MF27 (D): **a popover cannot be positioned from an ESTIMATED height.** The first cut placed the
  menu with `16 + 46 × rows`; the rendered menu with its hint sentences is ~215px, so it was clipped
  by the mapping overlay's own footer bar — visible only in a screenshot, and only for a card low in
  the column. Render, MEASURE, then correct: `_placeMenu` runs in a DOUBLE `requestAnimationFrame`
  (OWL patches on the first one) and flips or floors the menu against the board's real box. The same
  double-rAF is what makes focus land on the first row — a single one fires before the patch and
  `menuRef.el` is still null, which is why the first live check found the menu open with focus left
  behind.
- MF28 (D, testing): **a test that names a field asserts a property of the DATABASE.**
  `test_04` was written against `hr.employee.marital` — which on this Vietnamese build is **not
  stored** (`vietnam_marital_status` is), so the catalogue correctly omits it and the test failed on
  a working build. MF11's family. It now iterates every selection card the catalogue offers and
  checks the RULE (every stored key is printed somewhere on the card). Same trap in the hoot suite:
  `.mc-item-more` renders only when the adapter passes `onLeftAction`, because `itemActions()` is
  gated on it — a mount without that prop legitimately has no trigger to measure.
- MF29 (D): **read a selection with the ORM's own resolver, not by hand.** `field.selection` has
  three spellings — a literal list, a callable, and the NAME of a method as a string — and
  `hr.employee.certificate` uses the third. Iterating a string yields characters, every entry failed
  the `isinstance(entry, (list, tuple))` test, and the card silently said nothing at all while 23
  other selection cards were correct. `field._description_selection(env)` is what `fields_get` calls:
  it handles all three, applies `selection_add`, and returns translated labels. One card out of 193
  is exactly the size of defect a screenshot does not catch and a count does (24 selection fields,
  23 notes).
- MF30 (E): **on Odoo 19 `hr.employee` is a DELEGATE — `_inherits = {'hr.version': 'version_id'}`
  (`hr/models/hr_employee.py:43`).** `employee_type`, `marital`, `sex`, `passport_id`,
  `identification_id`, `ssnid`, `job_title`, `wage`, the six private-address fields, the contract
  dates and 30 more are therefore RELATED, **non-stored** fields on hr.employee — and every one of
  them takes a write, because the ORM writes through to the version row. `_ec_is_mappable`'s
  `not field.store` clause refused all of them, which is the whole of E2: the six-value Employee
  Type selection the owner photographed off the form was simply not in the catalogue, and never
  could be. **MF11 was a symptom of this, not the disease** — "department_id is not stored on
  hr.employee" is true because it is delegated, not because it is uncomputable.
  The rule is now `readonly ⇒ no`, then `store OR inherited OR related OR inverse` — i.e. *can this
  receive a value*, which is the only question a mapping destination has to answer; where the row
  physically lands is the ORM's business. Live effect on abm: **hr.employee 133 → 173 (+40),
  hr.contract 56 → 59 (+3, `permit_no`/`visa_no`/`visa_expire`, delegated the other way from
  `employee_id`), bank 4 unchanged — 193 → 236 cards. Nothing was LOST** (0 fields left the
  catalogue), so the change is purely additive. Four hr.version plumbing names were denied in the
  same breath (`version_id`, `date_version`, `last_modified_date`, `last_modified_uid`); three of
  them would otherwise have been gained, and `version_id` is registry-readonly and was never
  offered. When a predicate names a STORAGE property, ask whether the behaviour you want is
  actually storage.
- MF31 (E): **the `ir.model.fields` domain was a second, quieter copy of the inclusion rule — and a
  copy that could not be widened.** `_ec_right_items` and `ec_model_fields` both carried
  `('store','=',True), ('readonly','=',False)` in the SQL, so a field excluded there never reached
  `_ec_is_mappable` at all and fixing the predicate would have changed nothing. Worse, the two
  disagree: `ir.model.fields` is a stored snapshot and the registry is live (the abm counts differ
  by one field in each model, in opposite directions). The domain is now `_ec_catalogue_domain` —
  model + ttype, a cheap first pass over 330/106 rows — and the registry decides. One rule, one
  place; a duplicated predicate is a predicate that will be half-fixed.
- MF32 (E): **`right.append(...)` put a card in a lane it does not belong to, and grew a second
  group heading for it.** The canvas emits a group header whenever `group` CHANGES between
  consecutive rows, so a wired Identity field tacked on below "Other contract fields" drew its own
  "Identity" heading at the very bottom of the board. `_ec_place_in_lane` inserts by `lane_order`
  instead. Any future "…but keep this one visible" append has the same shape: give the card its
  metadata AND put it where that metadata says it goes, or the metadata is decoration.
- MF33 (E): **a root-level `keydown` handler steals Enter from every button inside it.**
  `MappingCanvas.onKeydown` is bound to the board root, so Enter on a focused `<button>` fired the
  button's own click AND fell through to `case "Enter"`, which acts on the focus ring — it armed a
  column, and with a column already armed it **drew a wire**. So the keyboard route into the new
  value list mapped something on the way in: E1's own trap, one input device over, and the `⋮`
  trigger (D3) had been carrying it silently since Phase D. Found only by pressing the key on the
  live board — the mouse path was clean and every unit test passed. `onKeydown` now returns early
  for Enter/Space whose `target` is a `BUTTON` or `A`. **`INPUT` is deliberately not in that list**:
  "type in the search box, press Enter to wire the top hit" is a promise the board makes and MF25's
  `_relocateFocus` exists to keep it.
- MF34 (E): **one field can be bigger than the whole board.** `hr.employee.tz` has **597**
  timezones; sending them all as structured values is ~30 KB of payload and a 30 KB `title=`
  attribute for ONE card out of 236 — and the pre-existing tooltip would have carried them too, the
  moment the predicate let `tz` into the catalogue. `_EC_SEL_VALUES_MAX = 120` caps both the list
  and the tooltip, and the popover SAYS it is showing a subset ("Showing the first 120 of 597")
  rather than quietly dropping the tail. Structured values cost 10.8 KB of abm's 94 KB payload.
- MF35 (E, environment): **the ledger's `systemd-run` deploy ritual runs the unit as ROOT**, and
  odoo-bin then fails peer auth with `FATAL: role "root" does not exist` — on all four DBs, in
  about ninety seconds, with the loop still writing `EXIT[db]=1`. The service itself runs as `odoo`
  (`/etc/init.d/odoo-server`, `USER=odoo`); the runner script needs `sudo -u odoo` in front of
  `odoo-bin`. CR6's lesson with the sign flipped: a RED sentinel is not proof of a broken build
  either — read the log before believing either colour.
- MF36 (E, scope — two follow-ups deliberately NOT taken; **both CLOSED in Phase F**, (a) as F3 and
  (b) as F2 — see MF40 for what (b) turned out to be worth): (a) **`employee_mapping_create` does not
  apply `_ec_is_mappable`.** E2(3) makes an unwritable destination SAY so; it does not stop a user
  wiring more columns to it, because the mapping model's own domain accepts any non-readonly field
  and the handover asked only that the card be marked. There is one live instance:
  **`payobook` mapping 16 → `hr.contract.active`** (deny-listed as record plumbing), which now
  renders as a `warn` card on that database — the feature has a real subject, not just a test.
  (b) **the CLIENT still appends session extras at the end of the right column.** `_ec_place_in_lane`
  fixes the server's append (MF32), but `mapEmpRight` (`formula_studio.js`) concatenates the
  "Add a field to map…" extras after the whole catalogue regardless of `lane_order`, so a pinned
  extra still draws a duplicate group heading at the bottom. The E2 invariant is true of
  `employee_mapping_data(...)['right']`, which is what it was written about; it is not yet true of
  what the canvas finally renders. Both are one-line-ish and both are owner decisions, not defects
  this phase was asked to fix.
- MF37 (E, testing): **you cannot observe Odoo's RPCs by patching `window.fetch` from a Chrome-MCP
  probe.** The web client captures `browser.fetch` at module load, so a hook installed afterwards
  sees NOTHING — and "zero RPCs" then reads as proof when it is only proof that the hook is blind.
  It cost a real write on abm: a probe that clicked a right-hand CARD (to set `focusSide`) while a
  left column was armed did exactly what the board promises — it re-pointed `Employee Code` from
  `hr.employee.employee_id` to `hr.contract.state`, deleting mapping 1 and minting 85, while the
  hook reported an empty call list. **The oracle for "did the board write anything" is the DATABASE**
  (`select count(*), string_agg(id) from hr_payslip_import_mapping`), taken before and after. Restored
  by moving row 85 back to `hr.employee.employee_id` under id 1 with its original timestamps; no
  `hr.formula.rule` was touched. And the safe way to probe a write-capable gesture is to leave
  nothing armed — a failed guard then moves a focus ring instead of writing a row.
- MF38 (F): **"is this end hidden" was being asked of the DOM, and the DOM cannot tell you WHY.**
  `hiddenL` was `!L.map.has(id)` — the card has no measurable rect — which is true both when a
  filter excluded it and when the props say it is there but it has not rendered or is mid-transition.
  Two different facts under one flag, and the canvas then treated them identically: it docked the
  wire on the column edge. That is right for the second (transient, and the dock is the honest
  fallback) and wrong for the first, which is the owner's hanging arrows. `isFilteredOut` asks the
  FILTER STATE — `hasFilter(side)` then `_passes(side, item)`, the same call `leftView`/`rightView`
  make — so "filtered" is decided by the thing that does the filtering. The dock branch survives
  underneath it, untouched, for the case it was actually written for. **When a flag can be true for
  two reasons and you only handle one of them, the flag is the bug, not the handler.**
- MF39 (F): **the reveal bar is now effectively unreachable, on purpose.** `ui.reveal` and
  `revealText` exist so that double-clicking a wire whose end is behind a filter SAYS so instead of
  silently clearing the reader's search (C7). With F1 a filtered wire has no path, no hub and no
  hit-area, so nothing can double-click it; `centreBoth` is reachable only from `selWire`, which can
  no longer hold a suppressed wire. The machinery was deliberately KEPT — it still fires for the
  transient `hiddenL` case above, its four hoot tests still pass, and deleting live-tested UI to
  chase dead code is how a phase acquires a regression it did not need. The way back to a hidden
  wire is now the dock chip, which was always the more direct verb (it clears the filter rather than
  explaining it).
- MF40 (F, scope): **F2 fixes a path the UI cannot currently reach — and that is worth knowing
  before somebody "verifies" it and concludes it does not work.** `mapEmpExtras` only ever receives
  an id that is NOT already in `mapData.right` (`mapEmpRight` filters on `seen`). Since Phase E the
  right column is the WHOLE catalogue (236 on abm — `employee_mapping_data` is called with
  `context_id` false, so `_ec_right_column('')` filters nothing), and both pickers —
  `ec_search_fields` and `ec_model_fields` — are strict subsets of that same catalogue. So every
  field a user can pin is already on the board and no extra is ever appended. The defect MF36 (b)
  described is real in the code and latent in the product; it becomes live the moment anything
  narrows the served catalogue (a `context_id` search, a lazy right column, a per-user field
  allow-list). Validated by calling `addEmpField` on the live board with a card the catalogue does
  not carry: it landed at index 5, the end of the Identity lane, and the board kept exactly eight
  lane headings instead of growing a ninth at the bottom.
- MF41 (F, testing): **two Chrome-MCP facts that make a live check look broken when it is fine.**
  (a) the hoot runner renders inside `document.querySelector("hoot-container").shadowRoot`, so
  `document.body.innerText` is the EMPTY STRING and `document.title` is `""` — a probe that polls
  either sees nothing forever and reads as a hung suite while the screenshot shows 60/60 green. Read
  the shadow root, or read the screenshot. (b) the studio component IS reachable from a probe:
  `odoo.__WOWL_DEBUG__.root` plus a walk over `__owl__.children` finds `PbFormulaStudio`, which is
  how a client-only path (F2's `addEmpField`) can be exercised live without an RPC — and, per MF37,
  the DATABASE diff is still what proves nothing was written.
