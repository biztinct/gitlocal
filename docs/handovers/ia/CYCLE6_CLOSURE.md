# IA Redesign — Cycle 6 (closure): the owner's rulings

Program context: C1–C5 complete (rail 38→8, hubs live). This cycle executes the owner's explicit rulings on the debts C4/C5 surfaced. Handovers C1–C5 + conventions (binding through **W110**) in the usual places.

## ⚠ Production discipline (unchanged)
payobook.com production. W93/W94, W68, W75. Use C5's ritual: pg_dump clone for all testing; minimal planned production window; count files + checksums; prefer UNVERIFIED over improvising.

## Workstreams (all are OWNER RULINGS — none is optional)

### 1 — W105 money visibility: "anyone who can see the payslip records"
The owner's rule: a user may see `hr.payslip.line` records exactly when they can see the parent payslip. They do NOT know the group names — derive them:
- Enumerate `hr.payslip`'s effective access on this codebase/DB: every `ir.model.access` row and every record rule (om_hr_payroll + pb_* + hr modules). Report the table.
- Give `hr.payslip.line` matching reachability — read ACLs for the same groups, and record rules that scope lines through their parent slip (domain via `slip_id`, mirroring each payslip rule's domain shape — the line rule must not be broader than the slip rule). Prefer one rule per payslip rule, named to make the mirroring obvious.
- Ship in the module that owns the payslip rules today (verify owner; likely om_hr_payroll or pb_hr_payroll_base) + migration if needed.
- Verify: the Payroll Report (Insights hub · payroll lens) shows real money for an officer persona and a manager persona (probe users, archived after); a persona who cannot see a payslip still sees nothing of its lines; `pb_insights`'s sudo stays untouched (note in report if it could now be dropped — do not drop it).

### 2 — VN filings: fix the Odoo-19 field drift
C4 finding: `tang_ld`, `giam_ld`, `bhxhdstk01` read `hr.employee.address_home_id`; `bhxh630` reads `bank_account_id` — both gone in Odoo 19. Fix the legacy wizard code (in `pb_hr_govt` / `pb_hr_payroll_vietnam` — locate exactly):
- First verify what Odoo 19's `hr.employee` actually provides on this build (private address fields / `work_contact_id`; bank accounts via whatever the model now carries) — read the model, don't guess from upstream docs.
- Map each removed field to the correct Odoo-19 source, preserving the report's semantic (home address = employee's private/home address, not the office; bank account = the employee's payroll bank account as used by Pay & Deliver — check how `pb_pay_delivery` resolves accounts and use the same resolution so filings and payments agree).
- Evidence: all **5 VN filings** generate real artifacts through the filing flow on demo data (C4 got 2 of 5); spot-check the produced xlsx cells that come from the fixed fields (address/bank visible, not blank) for at least 2 employees with known data.

### 3 — W108 pb_learn: separate screen-identity from rail-reachability
Owner ruling: do the design change now; the Coach/tour/lesson **content** revamp is future work — change plumbing, not lessons.
- Today `learn.runtime` resolves a station's reachability through `get_sidebar_data()` leaves, and `learn.screen._primary()` reads screen matchers off the SAME leaf — which is why the naive repoint would corrupt screen grounding (C5's W108 analysis; re-read it).
- Split the concerns: screen identity keeps using the retired leaves' matchers (they still exist, inactive — or lift the matcher data into learn's own layer); reachability gets its own resolver that answers "which ACTIVE rail item reaches this screen" using the same match-matrix indexes the sidebar/highlight uses (C5's `_isClaimed()` work is the precedent seam).
- The 19 stations must stop saying "not in your menu" and instead name the real path (e.g. "Pay Run → Payslips"). Lesson text stays untouched.
- pb_learn data is GENERATED — implement via the generator/runtime code paths, regenerate with `docs/tutorial_poc/author/tools/gen_learn_data.py`, never hand-edit generated files (C5 followed this; W-ledger has the rule).
- Evidence: all 19 previously-broken stations resolve to correct hub paths (list them); screen grounding unchanged (the Coach still identifies the screens it identified before — run the learn suite incl. the 3 anchors C5 registered); `msgfmt` clean.

### 4 — Insights' 5 native-list drills (doctrine-compliant)
`pb_insights/static/src/js/insights.js` — `openRun` :398, `_openEmployees` :467, `openLeave` :485, `openOvertime` :501, `openBonusHours` :521 (re-verify lines). Decision rule:
- If an existing hub lens shows the same population with equivalent filter semantics → `openHub` deep-link with back chip "Insights": leave → Workforce·timeoff; overtime + bonus hours → Workforce·overtime; `openRun` → Pay Run·runs with `arrival.focus` on the run.
- If no lens matches the drill's filtered subset (e.g. near-cap-OT employee lists) → in-cockpit ledger+drawer (fourth use of the C3/C4 clone pattern) inside pb_insights.
- Report the chosen mapping per drill. No `target:"current"` escape into a bare native list may remain in pb_insights (grep + click gate, like the door tests).

### 5 — Tenant-DB errors on `acme` / `payobook_template`
Pre-existing module-loading/cron errors, started 2026-08-19 01:55 — **that timestamp is the C2 incident's first outage window**, so treat "pre-existing" with suspicion: diagnose root cause from the logs (what exactly fails to load, since when, which modules). Likely candidates: registry damage from the addons-tree delete/restore, or new-module drift between the shared addons tree and per-tenant installed lists. Fix per tenant DB (upgrade/registry repair — whatever the diagnosis demands), using the same production discipline (these are live tenant DBs; smallest steps; document every command). Evidence: both DBs load clean, crons run, zero module-loading errors over a fresh observation window; `payobook` untouched and still clean.

### 6 — Demo ⌘K gap: restriction-aware palette
C5's cutover means demo non-admins reach Formula Engine / Structures / Statutory / Integrations via ⌘K (rail blocks them, palette doesn't). Owner wants it closed. Do NOT strip pb_demo's formula group (the demo world needs it to compute). Instead give the global palette **restriction parity with the rail**: palette entries whose action tag/xmlid falls under a `restricted` sidebar section/item (the same server-side state `get_sidebar_data()` exposes / strips actions for) render with the padlock affordance and open the SAME upsell AlertDialog instead of navigating (`pb_sidebar.js:195–211` precedent; W-rules on restriction UX). Non-demo DBs: zero behavior change (nothing is restricted there). Evidence: demo persona ⌘K → the four setup entries show the lock + dialog, everything else navigates; admin on demo unaffected; production (unrestricted) byte-identical palette behavior.

### Binding non-goals
Planning revamp stays backlog (owner ruling). No lesson-content changes in pb_learn. No pb_insights sudo removal. No other backlog items (pre-existing 3 test failures stay — they belong to the other session/stream; do not "fix" `pb_today`'s hex test, just don't break it further).

## Tests (evidence for each)
1. W105: access table reported; officer + manager probes see real Payroll Report money (non-zero, equal to a sudo cross-check for the same scope); a no-payslip-access probe sees none; line rules provably not broader than slip rules (rule-by-rule comparison in the report).
2. VN filings: 5/5 generate artifacts; field-fix cells spot-checked non-blank and correct for 2 known employees; delivery-account resolution matches pb_pay_delivery's for the same employee.
3. pb_learn: 19 stations list with resolved paths; learn suite green; generated-files-only diff (git evidence); msgfmt clean.
4. Insights: per-drill mapping table; grep gate = zero native-list escapes; each converted drill exercised live (click → hub lens with back chip, or drawer opens).
5. Tenants: root-cause statement with log evidence; both DBs clean over an observation window; payobook log clean.
6. Palette parity: demo persona lock+dialog on the four entries; admin unaffected; unrestricted DB unchanged (DOM diff of palette rows).
7. Full regression: entire suite green apart from the 3 known pre-existing failures (same three, no new ones); one combined run, exit 0.
8. Chrome sweep of Insights hub + filing flow + Learn + ⌘K on demo clone: 0 console errors, 0 non-warmup ≥400s.
9. Production window(s) documented (expected: one short window for module upgrades; tenant repairs itemized separately); health 200 before/after.

## Self-review (mandatory)
Rule-mirroring audit line-by-line (the money rules are the riskiest artifact this cycle — a too-broad line rule is a data leak; re-read each domain twice); field-mapping semantic check against two real employee records; verify the palette lock cannot block unrestricted users; verify learn changes touch only generator/runtime + regenerated outputs; re-run affected tests after fixes.

## Commits (per feature, explicit staging, do NOT push; never stage `.claude/settings.json`, `thaco/`, `ABM/`)
Suggested: (1) fix(payroll-access): payslip-line rules mirror payslips (W105); (2) fix(pb_hr_govt): Odoo-19 field drift in VN filings; (3) feat(pb_learn): reachability resolver split (W108); (4) feat(pb_insights): doctrine-compliant drills; (5) fix(tenants): <per diagnosis>; (6) feat(pb_hub): restriction-aware palette; (7) docs/ledger.

## Report back
- The payslip access table + the mirrored rules, side by side.
- VN field mapping (old → new, with the semantic justification).
- The 19-station resolution list. Per-drill mapping. Tenant root cause. Palette parity mechanism.
- Per-test evidence, commit hashes, deviations, new W entries.
