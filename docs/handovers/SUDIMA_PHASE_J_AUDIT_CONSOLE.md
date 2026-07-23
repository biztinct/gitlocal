# SUDIMA Phase J — Audit Console (Compliance Trail, Who/What/Old→New)

**Scope item:** #20 Audit Trail & Compliance (*Partial*): chatter exists, but no dedicated audit model view, no login/logout log surface, no salary-adjustment audit, no consolidated compliance console.
**Module:** NEW `pb_audit` (console overlay — the engine is Phase H's `biz_audit_trail`; this phase surfaces and consolidates).
**Ledger:** C1, C2, C18 binding (esp. C18.32 PII scoping + retention, C18.40 scoped test runs, C18.41 idempotent hooks).
**Prerequisites:** Phase H shipped (`biz_audit_trail` entries flowing, incl. wage = salary adjustments). Consumes F/G/I logs when present (soft-hooked).

---

## 1. Scope

1. **Compliance console cockpit**: one filterable stream over every audit source in the platform — field changes (`biz.audit.entry`), approval transitions (`biz.approval.step.log`), bank master changes (`pb.employee.bank.history`), bank-file exports (`bank.export.log`, soft), payslip deliveries (`pb.payslip.delivery`, soft), logins (`res.users.log` — verify at kickoff it is present and queryable on live, it is Odoo core).
2. **Salary-adjustment view**: the wage-change lens (from Phase-H contract audit) — employee, old→new, %, actor, date; manager-gated values.
3. **Retention & export**: config-driven retention GC per source (own rows only — never vacuum other modules' logs), XLSX export of any filtered view.

### Binding non-goals
- **NO new logging** — every event surfaced already exists (H writes them); this phase READS. If a wanted event is missing, that's a hand-back note, not a J-scope write hook.
- **NO cross-module vacuuming** — `pb_audit`'s GC touches only `biz.audit.entry` (via the engine's own cron config); other logs keep their owners' retention.
- **NO tamper-proofing theater** (hash chains/blockchain) — append-only + forced actor/stamp (H) is the guarantee we ship.
- **NO end-user access** — this is a payroll-manager/admin console only.

---

## 2. Verified plumbing facts (do not re-derive)

- ✓ **Sources and their shapes** (all verified in-repo):
  - `biz.audit.entry` — model/res_id/res_display/field/old/new/user forced/stamp forced (Phase H — read its final shape at kickoff).
  - `biz.approval.step.log` — res_model, res_id, from_state→to_state, forced user/stamp, note (`biz_approval_chain/models/biz_approval_log.py:6-49`; trail fetch `_for_record` :44-48).
  - `pb.employee.bank.history` — old/new bank fields, change_source ocr_request|manual, changed_by/at (`pb_bank_ocr/models/pb_employee_bank_history.py:21-83`).
  - `bank.export.log` — period, totals, format, created_by (`payroll_analytics_approval/models/bank_export_log.py:6-36`) — module OPTIONAL → `if 'bank.export.log' in self.env`.
  - `pb.payslip.delivery` — per-slip sent/failed/skipped (Phase F) — soft-hook.
  - `res.users.log` — Odoo core create-only login log (rows created at login; `create_uid` = the user, `create_date` = login time). Surface logins from it; note: it records logins only (no logouts in core — say so in the UI as "Sessions started", don't fake logout data).
- ✓ **XLSX export precedent**: in-memory xlsxwriter → base64 → Binary re-open (`pb_hr_workforce_planning/wizards/export_wizard.py:32-84`).
- ✓ **Retention/vacuum discipline**: `biz_doc_ocr` cron vacuum shape — savepoint-wrapped, write_date clock, non-positive param falls back (C18.40, `biz_doc_ocr/models/biz_doc_ocr.py` `_vacuum_jobs`).
- ✓ **Cockpit pattern**: bank cockpit (`pb_bank_ocr/views/pb_bank_ocr_action.xml:3`, `static/src/js/pb_bank_ocr.js:24-60`); sidebar item data records; pbim tokens + `ic()` Lucide map (`pb_import_kit/static/src/js/import_icons.js:6-56`).
- ✓ **Access-gate pattern**: `_is_hr`/`_is_finance` group checks (`pb_bank_ocr/models/pb_bank_ocr_cockpit.py:26-36`).
- ✓ Wage values in payloads are two-tier serialized (Phase-H precedent: event visible, value manager-only).

---

## 3. Architecture

### `pb_audit` (depends: `biz_audit_trail`, `biz_approval_chain`, `pb_bank_ocr`, `pb_sidebar`, `pb_import_kit`; soft: `payroll_analytics_approval`, `pb_pay_delivery`)

```
pb_audit/
├── models/pb_audit_console.py   pb.audit.console (AbstractModel RPC facade — READ ONLY)
├── wizards/audit_export.py      filtered-view XLSX export
├── security/                    console: om_hr_payroll.group_hr_payroll_manager + base.group_system
├── views/ + data/pb_sidebar.xml sidebar item "Audit", section Admin, icon `scroll-text`
└── static/src/                  cockpit (tag pb_audit)
```

**RPC facade `pb.audit.console`** (every method `_require_manager()` first):
- `get_stream(filters, offset)` — normalized rows from all present sources: `{stamp, source, icon, actor{id,name,avatar}, employee{...|null}, title, old, new, ref{model,res_id}}`, merged + sorted desc, paged 50. Filters: date range, source kind, actor, employee, model, free text. Per-source adapters live in one place (`_SOURCES` registry dict: key → {model, available(), fetch(filters), normalize(row)}) — adding a future source is one entry (no-silent-caps: sources absent from the deploy are listed as "not installed" in the payload, not just missing).
- `get_salary_lens(filters)` — `biz.audit.entry` where model=hr.contract, field=wage: employee (resolve via the contract), old→new, delta %, actor, stamp. Values only when caller has `om_hr_payroll.group_hr_payroll_manager` (the console gate already guarantees it — but keep the two-tier serializer for future gate widening).
- `get_login_lens(filters)` — `res.users.log` grouped by user/day + a per-user last-30-sessions sparkline; internal users only.
- `get_kpis()` — events today/7d, top actors, sources present, oldest retained entry + retention setting.
- Export wizard: takes the SAME filters, streams up to a hard cap (50k rows — cap surfaced in the UI, C18 no-silent-caps), xlsxwriter pattern.

**Retention**: expose the engine's `biz_audit_trail.retention_days` (+ per-source note that other logs govern themselves) on a small settings card (manager-gated, native-form-free — edit via the cockpit card, writes the config param through a gated method).

---

## 4. WOW-UX specification (exceptional, out-of-world — binding F–J rule: legacy surfaces get upgraded, never left stock)

The console is a net-new bespoke OWL cockpit — no native list views on menus; the export is a cockpit action, not a wizard form. Chrome-MCP validate edge cases: empty DB day (designed empty state), 50k-cap notice, absent optional sources.

1. **Stream**: a premium ledger feel — day-grouped timeline, monospaced old→new diff chips (`old ⟶ new`, rose→green), source-colored rail dots (field=indigo, approval=violet, bank=teal, export=slate, delivery=green, login=cyan), actor avatars, employee chips deep-linking to the Phase-H 360 drawer, sticky filter bar with instant chips (Today · This week · By me · Salary only · Logins).
2. **Salary lens**: table with delta badges (+8.3% amber if >10%, rose if >25% — thresholds config), sparkline of adjustments per month, "export this view" tile.
3. **Login lens**: per-user session cards with day sparklines; wording "Sessions started" (core logs logins only — honest labeling).
4. **KPI hero**: events counter (odometer animation), sources-present pills (absent ones ghosted with "not installed"), retention dial.
5. pbim tokens, white+rail hero, Lucide only (`scroll-text`, `banknote`, `log-in`, `filter`), no gradients/emoji; empty states designed.

---

## 5. Safety rails

1. **The console is READ-ONLY** — no method writes anything except the export wizard's own Binary and the gated retention param; verify no `write`/`unlink` on foreign models anywhere in the module.
2. **Manager+system gate on every RPC** (`_require_manager` first line, AccessError otherwise — test as employee AND as plain HR-user).
3. **PII discipline (C18.32)**: bank account numbers render masked in the stream (`•••• 1234` — reuse the `_mask` pattern `pb_bank_ocr_cockpit.py:38-40`); full values only in the source record via deep-link (where its own rules gate).
4. **Export cap surfaced**; export file carries the same masking as the view.
5. **Soft-hooks fail closed-and-visible**: an absent source shows "not installed", an erroring adapter logs + shows "source unavailable" (never a blank stream).
6. Deep-links respect the target's own access rules (no sudo reads to "help").

---

## 6. Test cases

**Server:**
1. Stream merge: seed one row in each available source → `get_stream` returns all, sorted desc, correctly normalized (old/new populated for field changes, states for approvals).
2. Filters: by employee, by source, by actor, date range, free text — each narrows correctly; pagination stable (no dupes across pages).
3. Gates: employee user AND plain hr-payroll-USER get AccessError on every RPC; manager passes.
4. Masking: a bank-history row's account renders masked in stream AND export.
5. Salary lens: wage 5,000,000→6,000,000 shows +20.0% with correct actor; a non-wage contract entry does not appear.
6. Login lens: a fresh login creates a `res.users.log` row that appears (create a session via test cursor login or seed the row); wording fields correct.
7. Optional sources: with `payroll_analytics_approval` absent (simulate via registry check mock), payload lists the source as not installed and the stream still returns.
8. Export: filtered export ≤ cap rows, masked values, opens as valid XLSX; cap notice when truncated.
9. Read-only proof: module-level test asserting `pb.audit.console` methods perform no create/write/unlink on foreign models (e.g., exhaustive method call sweep with a write-recording registry patch, or at minimum assert stream/lens calls leave row counts unchanged).
10. Retention card: setting the param via the gated method as manager works; as HR-user raises.

**Chrome MCP:**
11. Console with seeded mixed events — stream, filters, deep-link to a 360 drawer (screenshots).
12. Salary lens + export download (screenshot).
13. Empty-state day + ghosted absent source (screenshot).

---

## 7. Deploy & verify

Ritual (`--uid=odoo`). `-i pb_audit --test-tags /pb_audit` (C18.40). Live: the console should already show REAL history (Phase D–I activity: bank approvals, corrections, deliveries, logins) — screenshot the live stream as the demo artifact. Demo stays pristine (console writes nothing).

---

## 8. Report back

1. Tests 1–13 + screenshots.
2. `res.users.log` live posture (row counts, any retention cron core runs — `res.users.log` is vacuumed by core GC? report what you find).
3. Stream performance on the live DB (worst-case unfiltered page latency; the sources must be indexed enough — report any needed index and add it in-module).
4. Deviations, file list, versions; gotchas → C18 wording.

---

## Kickoff line (paste into the Opus session)

> Read `docs/handovers/SUDIMA_PHASE_J_AUDIT_CONSOLE.md` and `docs/FORMULA_ENGINE_CONVENTIONS.md` (C1, C2, C18 binding — esp. C18.32/40/41), then implement Phase J exactly as specified: new `pb_audit` — a READ-ONLY compliance console over biz_audit_trail + approval logs + bank history + soft-hooked export/delivery/login sources, with the salary-adjustment lens, masked PII, filtered XLSX export, and a WOW bespoke cockpit (no native views on menus). Tests §6, deploy §7, report §8. The console never writes anything — if an event you want to show doesn't exist yet, report it, don't log it.
