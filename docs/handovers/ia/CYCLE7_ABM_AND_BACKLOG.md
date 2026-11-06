# IA Redesign — Cycle 7: abm catch-up install + backlog closure

Program context: C1–C6 complete and CLOSED (rail 38→8, hubs live, W105 money rules, tenants acme/payobook_template repaired). This cycle executes three new owner rulings given 2026-08-20:

1. **abm DB go-ahead**: "Install all the modules which were changed/created/updated on payobook but not installed in abm database. ABM is not live yet so you can do that."
2. Close backlog item: the pre-existing `hr_timesheet` multi-company `session_info` 500 (W100 family).
3. Close backlog item: drop `pb_insights`'s sudo now that real access rules exist (W105) — **conditional, see WS3**.

Prior handovers C1–C6 in `docs/handovers/ia/`; conventions binding through **W119** (`docs/WORKFORCE_REDESIGN_CONVENTIONS.md`). Read the **C6 report's tenant-repair section** before touching abm — it is the proven procedure.

## ⚠ Production discipline (unchanged, non-negotiable)
The box serves payobook.com in production; `abm` is a tenant DB on the SAME cluster/server. abm itself is not live (owner's words) but the server, the `payobook` DB, and `acme` ARE.
- W93/W94: never `rsync --delete` into the shared addons tree; `--files-from` disables recursion; count files + checksums before/after any tree touch.
- **W118/W119**: never reuse a shared/pre-existing staging dir — create a FRESH, session-unique staging path (e.g. `/tmp/c7stage.$RANDOM`), verify it's empty before use, delete it after.
- W68: never stop/restart/kill a server another session started; check for other sessions' activity before any service window.
- **NO code deploy should be needed for WS1 at all** — the addons tree already carries everything (C6 proved repo↔server parity 0/251). If you find a module missing from the server tree, STOP and report; do not improvise a sync.
- **NEVER `-u base` on any tenant DB** — C6 clone-measured it destroying the rail (50 items → 2). The repair verbs are `update_list()` + targeted `-i` (and `-u` only for specific already-installed modules if the diagnosis demands it).
- `hr_timesheet` in the repo is a **Feb-2026 community snapshot** (like ~87 others). Deploying it would DOWNGRADE the server's Odoo (W93 lesson). The WS2 fix must therefore live in a CUSTOM module, never in the snapshot, and the snapshot file must not be rsynced.

## Workstream 1 — abm: install the payobook module delta
Owner authorization is explicit and abm-scoped. The goal: abm ends up with the same custom-module feature set as `payobook`.

1. **Diagnose exactly like C6 did for acme**: abm has the identical 27-module `ir_module_module` snapshot drift (crons failing every 5 min since dependency drift). Re-confirm from the log/DB rather than assuming the number.
2. **Compute the delta**: `SELECT name FROM ir_module_module WHERE state='installed'` on `payobook` minus the same on `abm`. Restrict the install list to our custom modules (`pb_*`, `biz_*`, `om_hr_payroll`, `payroll_*`, `access_roles`, and any other custom names that appear — judge by addons provenance, not prefix alone) — Odoo pulls community dependencies in automatically; do NOT hand-install community modules that only entered `payobook` as dependencies (they'll come in via depends) and do NOT install anything `payobook` itself doesn't have installed.
   - **Deliberate exclusions to consider and REPORT**: `pb_demo` / demo-world modules and `pb_tenants` (platform cockpit) — install them on abm ONLY if `payobook_template`/`acme` have them; the template is the reference for what a tenant should carry. Where template and payobook disagree, follow the template for tenant-shaped modules and payobook for product modules; report every judgment call in a table (module → installed where → decision → why).
3. **Repair + install ritual** (C6's proven two-command shape, extended):
   - `update_list()` on abm first (via the same mechanism C6 used — read its report).
   - Then a detached `-d abm -i <delta list> --stop-after-init` unit (deploy-memory sentinel pattern). If C6's repair needed the service stopped, follow that precedent; if it ran alongside the live service, follow THAT precedent — match C6 exactly and document which.
   - Never `-u base`. If any module errors on install, capture the error, skip-and-report rather than force.
4. **Evidence**: post-install `state='installed'` counts payobook vs abm with the remaining diff enumerated and justified (each remaining difference must be a deliberate exclusion from step 2); abm loads clean (registry load line, zero module-loading errors); abm crons run over a fresh observation window (≥15 min) with zero errors; `payobook` and `acme` logs untouched/clean across the same window; abm rail renders the Six-Missions 8-item rail (Chrome MCP screenshot via the tenant host or `-d`-scoped session — however C6 verified acme).

## Workstream 2 — hr_timesheet multi-company 500 (W100)
Symptom: users whose ONLY company is the VN demo company get a 500 from `session_info`. The crash site is the community override `hr_timesheet/models/ir_http.py:19` — `result["user_companies"]["allowed_companies"][company.id]` KeyErrors when a company in `user.company_ids` is absent from the session's `allowed_companies` dict.
1. **Diagnose first**: pull the real traceback from `/var/log/odoo/odoo-server.log` (and re-read W100 in the conventions ledger) to confirm the exact key mismatch mechanism on THIS build (which company id, why absent — cids cookie? archived company? demo-company data gap?) — don't fix from my hypothesis alone.
2. **Fix in a custom seam**: a defensive `session_info` override in an existing always-installed custom module (prefer an existing module already touching `ir.http` or session plumbing — locate candidates and report your choice; a new micro-module is acceptable only if no honest seam exists). The override must be **behavior-preserving for every user the bug doesn't hit**: same payload keys/values, only the crashing path guarded (e.g. iterate the intersection, or `.get()`-guard with a log warning). Do NOT edit the `hr_timesheet` snapshot in the repo and do NOT rsync it.
3. If the diagnosis reveals a DATA root cause (e.g. the demo company genuinely missing from allowed_companies due to a fixable record state), fix the data too — but the defensive guard ships regardless (other tenant DBs can reproduce the same shape).
4. **Evidence**: the previously-500ing persona (user whose only company is the VN demo company — C6/W100 will name one, else create a probe user, archive after) loads the backend clean, `session_info` 200; a multi-company user's session payload is byte-identical before/after (diff the JSON); timesheet UoM widget still works for a normal user (smoke).

## Workstream 3 — pb_insights: drop the sudo (conditional)
Owner ruling: "Insights' sudo can now be dropped since real access rules exist." The W105 line rules + mirrored ACLs make the payslip reads rule-safe — but `pb_insights/models/pb_insights.py:39-49` documents that the board's gate groups (`group_payroll_base_manager`, `group_payroll_analytics_user`, `group_payroll_super_admin`) are a SUPERSET of the payslip ACL union (C18.75: the pb_* ladder holds no `hr.payslip` ACL at all). So a mechanical sudo-strip would hand `analytics_user` an AccessError on a board they see today. The ruling's intent is cleanup, not regression:
1. **Enumerate first**: for each gate group, what `hr.payslip` / `hr.payslip.line` ACL + record-rule access does it hold post-W105? Table in the report.
2. **Drop sudo on the payslip/money read paths** (`pb_insights.py:248`, `:894`, and any other slip/line reads). The soft-dep pulse sudos (`:1001`, `:1011` — workforce models) get the same treatment ONLY if their models' ACLs cover the gate groups; otherwise they keep sudo with a one-line comment saying why (report the decision per site).
3. **Where a gate group lacks payslip read ACL**: grant that group read-only `ir.model.access` on `hr.payslip`/`hr.payslip.line` (scoped by the existing W105 record rules — no new rules, no rule widening). This is NOT a policy widening in practice: those groups already saw full-company money through this exact sudo'd board; it converts an invisible bypass into an auditable grant. State this rationale in the report. If you find a gate group that should arguably NOT see money at all, do not decide — keep sudo, flag it as an owner question.
4. **Company scoping**: the explicit `company_id IN %s` SQL predicates must survive untouched — record rules ADD to them, not replace.
5. **Evidence**: per-gate-group persona parity — board payload (hero, trend, leaderboard, statutory split) BEFORE (sudo, from a git-stash run or the C6 numbers) vs AFTER for `base_manager`, `analytics_user`, `super_admin` personas: identical numbers. A no-group probe still gets the `_require()` AccessError. `test_06` (read-only grep gate) still green. pb_insights suite green. The Insights hub payroll lens (Payroll Report) unaffected (it reads its own path — smoke it anyway).

### Binding non-goals
- The four payobook modules with repo-newer-than-DB versions (`biz_debrand`, `biz_theme`, `pb_bank_ocr`, `pb_pay_delivery`) stay untouched — other sessions' work (W68.3), NOT this cycle.
- No pushes. No Planning work. No pb_learn content work. Do not "fix" the 2 known pre-existing test failures (pb_timeoff test_05, pb_today hex).
- `ash@biztinct.com` and all other passwords: never touch.

## Tests (evidence for each)
1. abm: delta table (module → decision), post-install parity counts, clean registry load, cron observation window clean, rail screenshot, payobook/acme unharmed (log grep + health 200 before/after any window).
2. hr_timesheet: probe persona 500→200; multi-company session payload byte-diff empty; UoM widget smoke.
3. pb_insights: gate-group ACL table; per-persona parity numbers; no-group AccessError; suites green.
4. Full regression: entire suite in ONE combined run, exit 0 apart from the 2 known pre-existing failures (same two, no new ones).
5. Chrome sweep: Insights hub + a normal backend load with the fixed persona — 0 console errors, 0 non-warmup ≥400s.
6. Every production window (if any) documented with duration + health checks; W118 fresh-staging-dir compliance stated explicitly.

## Self-review (mandatory)
Re-read the sudo-drop diff against the gate-group table (an over-broad ACL grant is a money leak — check the record-rule scoping twice); verify the session_info override cannot change any existing user's payload; verify nothing was installed on abm that the template/payobook comparison doesn't justify; re-run affected tests after fixes.

## Commits (per feature, explicit staging, do NOT push; NEVER stage `.claude/settings.json`, `thaco/`, or the untracked `ABM/` directory)
Suggested: (1) fix(session): defensive session_info guard for single-demo-company users (W100); (2) refactor(pb_insights): drop sudo behind W105 rules + gate-group ACL grants; (3) docs(ia): ledger + C7 notes. abm work is ops — it lives in the ledger/report, not code.

## Report back
- abm decision table + final parity diff + cron-window evidence.
- W100 root-cause statement (traceback-grounded) + chosen seam + why.
- Gate-group ACL table + per-site sudo decision + persona parity numbers.
- Per-test evidence, commit hashes, deviations, new W entries.
