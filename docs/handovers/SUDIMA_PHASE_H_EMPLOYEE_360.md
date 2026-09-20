# SUDIMA Phase H — Employee 360 (Document Vault + Employment-History Timeline)

**Scope item:** #2 Employee Master Management (*Partial*): a document repository (contracts/certs/IDs) and employment-history logs (role/dept/salary timeline) are not surfaced.
**Modules:** NEW **`biz_audit_trail`** (generic field-change audit engine — also the foundation Phase J's console consumes) + NEW **`pb_employee_vault`** (documents + the Employee 360 drawer in People).
**Ledger:** C1, C2, C18 binding (esp. C18.24/31 sentinel-guarded verification fields, C18.25 orphan-attachment pattern, C18.32 private sudo services + PII record rules, C18.40).
**Prerequisites:** none of F–G (parallel-safe); Phase D patterns are the precedents.

---

## 1. Scope

1. **Generic audit engine** `biz_audit_trail`: watch configured fields on configured models; append-only old→new entries with forced actor/stamp. Payobook wiring this phase: `hr.employee` (department, job title, manager, company, active) + `hr.contract` (wage, state, dates, structure).
2. **Document vault**: per-employee documents with config-driven categories, expiry tracking, HR verification flag, strict access rules.
3. **Employee 360 drawer** in the People cockpit: profile header + document grid + a unified employment timeline (audit entries + bank history + approval logs + contract events).

### Binding non-goals
- **NO OCR on vault documents** (biz_doc_ocr integration is a future phase; upload is plain attachment).
- **NO audit CONSOLE UI** — that's Phase J; this phase ships the engine + the per-employee timeline only.
- **NO cost-centre-code field work** (#2 mentions it; it's already carried on contracts as `costcenter` — surface, don't remodel).
- **NO backfill of history** — the timeline starts at install (existing bank-history/approval-log rows DO appear since they already exist).
- **NO employee self-service upload** — HR-side vault this phase; ESS upload arrives in Phase I on top of it.

---

## 2. Verified plumbing facts (do not re-derive)

- ✓ **No generic write-audit exists** — repo-wide search confirms only the two targeted logs: `pb.employee.bank.history` (`pb_bank_ocr/models/pb_employee_bank_history.py:21-83`, hr.employee write-hook :52-83 with `_BANK_AUDIT_TOKEN` sentinel :18) and `biz.approval.step.log` (`biz_approval_chain/models/biz_approval_log.py:6-49`, forced `user_id`/`stamp` at create :39-40, `_for_record()` trail fetch :44-48). No `contract.component.change` model exists in this repo — do not reference it.
- ✓ **Contracts are `hr.contract`** (Odoo core), not hr.version — pb_contracts cockpit reads hr.contract directly (`pb_contracts/models/pb_contracts.py:28-109`: states draft→running→expired, wage, struct_id fallback structure_type_id, `costcenter` field carried). `hr.version` exists only for work-entries (`hr_work_entry/models/hr_version.py:17-42`) — irrelevant here.
- ✓ **People cockpit RPC**: `pb.people` AbstractModel (`pb_people/models/pb_people.py:33-246`) — roster payload per employee: name, avatar, job_title, department, parent_id manager, work_email, contract state/wage, tenure, banking status. The 360 drawer extends THIS model's payloads (inherit, add `get_employee_360(employee_id)`); theme = the `.pbim.ppl` teal variant.
- ✓ **Attachment upload pattern (C18.25)**: create `ir.attachment` first WITHOUT res_model/res_id, create the business record, then write res_model/res_id back — clone `pb_bank_ocr/models/pb_bank_ocr_cockpit.py:122-141` (`create_from_upload`). Driver-selfie sudo variant at `pb_driver_checkin/controllers/driver_app.py:148-158`.
- ✓ **Sentinel rails**: `_SYS_FIELDS`/token pattern for verification fields (`pb_bank_ocr/models/pb_bank_change_request.py:45-57` + write guard) — the vault's `verified` flag follows C18.31 (HR testimony, not client-writable).
- ✓ **mail.thread is NOT field-audit**: hr.payslip inherits mail.thread (`om_hr_payroll/models/hr_payslip.py:32`) but no field tracking exists anywhere — chatter is messages, not old→new.
- ✓ **Timeline sources that already exist**: bank history rows, approval step logs (`res_model`/`res_id` keyed — filter per employee via the consumer models' `employee_id`), contract records themselves (create dates + state).
- ✓ Versions: pb_people 19.0.1.0.0, pb_contracts 19.0.1.0.0.

---

## 3. Architecture

### `biz_audit_trail` (generic engine — depends `base` only; zero Payobook imports)

```
biz_audit_trail/
├── models/
│   ├── biz_audit_rule.py    biz.audit.rule (model_name, field_names csv, active, company_id?)
│   ├── biz_audit_entry.py   biz.audit.entry (append-only)
│   └── biz_audit_mixin.py   biz.audit.mixin — write-hook helper
├── security/                entries: system + configurable reader group; rules: system-only write
└── data/ir_cron_gc.xml      retention vacuum (config param biz_audit_trail.retention_days, default 730, write_date clock — C18.40)
```

- **`biz.audit.entry`** (append-only like the step log — clone :6-49 discipline): `model_name`, `res_id`, `res_display` (char snapshot — survives record deletion), `field_name`, `field_label`, `old_value`, `new_value` (both display-format Chars via `convert_to_display_name`/field convert), `user_id` FORCED to env.uid at create, `stamp` FORCED now, `company_id`. `write()`/`unlink()` raise except for the GC cron path (sentinel token) and system.
- **`biz.audit.mixin`**: consumer models `_inherit` it; its `write()` looks up active `biz.audit.rule` rows for `self._name` (ormcached per model, cache cleared on rule write — do NOT re-read rules per write), snapshots watched old values, calls super, logs diffs batch-wise. Rule lookup absent → zero overhead beyond one cached check. **The mixin never blocks the write** — logging failures log an exception and pass (a broken audit may not break HR operations; but flushes must not swallow the entry silently in tests — assert entries in the same transaction).
- Rules are DATA per deployment: this phase ships Payobook rules for `hr.employee` (`department_id, job_title, parent_id, company_id, active`) and `hr.contract` (`wage, state, date_start, date_end, struct_id, structure_type_id`) via thin `_inherit = ['hr.employee'-model + 'biz.audit.mixin']` glue classes in `pb_employee_vault`. **Wage entries are the #20 "salary-adjustment audit" foundation.**

### `pb_employee_vault` (depends: `hr`, `biz_audit_trail`, `pb_people`, `pb_sidebar`, `pb_import_kit`)

- **`pb.employee.document.category`** (config records, DATA defaults noupdate="1": Labor Contract, ID Document, Degree/Certificate, Health Check, Work Permit, Other): `name`, `code`, `requires_expiry` Bool, `sequence`.
- **`pb.employee.document`**: `employee_id`, `category_id`, `name`, `attachment_id` (C18.25 pattern on upload), `issue_date`, `expiry_date` (required when category.requires_expiry), `verified` Bool + `verified_by/at` — **sentinel-guarded** (`_VAULT_SYS_TOKEN`; only the HR-gated `action_verify()` sets them; client write raises — C18.31), `note`, `company_id`, `active`.
  - **Record rules (C18.32 — documents are PII)**: employees read ONLY their own (`employee_id.user_id = user`); HR (om_hr_payroll.group_hr_payroll_user) read/write company-scoped; unlink manager-only. ACL: no create for plain users this phase (HR uploads; ESS upload comes in Phase I with its own rule).
  - Expiry cron: documents expiring in N days (param, default 30) raise `mail.activity` on the employee for HR + feed the 360 drawer's "expiring" chips.
- **Timeline service** `pb.employee.timeline` (AbstractModel, HR-gated like `pb_bank_ocr_cockpit._is_hr` :26-36): `get_timeline(employee_id)` merges, newest-first, capped 100 + "load more":
  1. `biz.audit.entry` rows for (`hr.employee`, id) and (`hr.contract`, employee's contract ids),
  2. `pb.employee.bank.history` rows,
  3. `biz.approval.step.log` rows for the employee's `pb.bank.change.request` / `pb.business.trip` / `hr.attendance.correction` records (resolve each consumer model's ids by employee_id — soft-hook per model existence),
  4. contract lifecycle events (created, state changes come from audit entries once live).
  Each item: `{stamp, kind, icon, title, detail, actor}` — presentation-ready, no raw values leak beyond what the caller may read (service is HR-gated; the OWN-employee variant comes in Phase I).
- **Employee 360 drawer** (extends the People cockpit): inherit `pb.people` RPC + a drawer component in `pb_people`'s action via a NEW assets bundle contribution from pb_employee_vault (People stays installable without the vault — the drawer registers only when its JS is present; use a soft component registry add, same pattern as trip overlay chips). Tabs: Profile (existing data + cost-centre from contract) · Documents (grid, upload, verify, expiry chips) · Timeline.

---

## 4. WOW-UX specification (exceptional — binding F–J rule: legacy surfaces touched get upgraded, never left stock)

The 360 drawer, documents grid and timeline are bespoke OWL inside the People cockpit — no native form ever surfaces to an HR user for vault documents (native views off-menu, admin fallback only). Exception (established Phase-E precedent): pure admin CONFIG models (`biz.audit.rule`, document categories) may use native list/form views behind the manager gate — they are not demo surfaces. Chrome-MCP validate edge cases: employee with zero documents/zero history (designed empty states), 100+ timeline events (load-more), expired-document styling.

1. **360 drawer** (teal `.ppl` theme): header with large avatar, name, position chip, manager chip, tenure ring; three tabs. Slide-in over the roster, ESC closes, deep-linkable (`?emp=`).
2. **Documents tab**: category-grouped cards — file-type icon, name, issue→expiry line, expiry countdown chip (green >90d, amber ≤90d, rose expired), verified shield (filled = verified, with verifier + date tooltip); drag-drop upload zone per category.
3. **Timeline tab**: vertical timeline, kind icons (briefcase = contract, building = department, banknote = wage — masked as "Wage updated" for non-managers, credit-card = bank, check = approvals), actor avatars, relative dates, month separators.
4. Lucide only; wage VALUES visible only to payroll managers (others see the event, not the number).

---

## 5. Safety rails

1. **Append-only audit** — entries reject write/unlink (GC sentinel + system excepted); actor/stamp forced server-side (clone :39-40).
2. **Audit never blocks business writes**; rule lookup is ormcached (registry-load lesson C18.41 — no per-write table scans).
3. **`verified` is HR testimony** — sentinel-gated exactly like C18.31 verification fields; a client write of `verified*` raises AccessError.
4. **PII scoping**: document reads own-only for employees, company-scoped for HR; timeline RPC HR-gated this phase; wage values manager-gated in the payload (two-tier serialization, not CSS hiding).
5. **C18.25** upload ordering for attachments; attachment unlink cascades handled (document unlink removes its attachment).
6. **No silent truncation**: timeline cap surfaces "showing 100 of N".

---

## 6. Test cases

**Server:**
1. Audit engine: write department_id + job_title on an employee → exactly 2 entries with correct old/new display values, forced actor; unwatched field (e.g. `work_phone`) → 0 entries.
2. Contract wage change → entry (the salary-adjustment record); state draft→open → entry.
3. Rule off (active=False) → no entries; rule cache invalidates on rule toggle (write after toggle logs again).
4. Entries are append-only: write/unlink as HR raises; GC cron with aged write_date vacuums past retention, keeps young rows (clone the biz_doc_ocr vacuum test shape).
5. Audit failure isolation: monkeypatch entry create to raise → employee write still succeeds, exception logged.
6. Vault: HR uploads (C18.25 order verified: attachment res_model/res_id set after), employee user reads own docs only (colleague's raises/is empty), plain user cannot create; expiry required when category demands it.
7. `verified` forgery: employee (and even HR via direct write) setting `verified=True` raises; `action_verify()` as HR sets verified_by/at correctly.
8. Expiry cron: doc expiring in 10 days creates one activity, idempotent on re-run.
9. Timeline merge: seed one dept change + one wage change + one bank-history row + one approval log → `get_timeline` returns all four, newest-first, wage value masked for an HR-user-without-manager-group payload, present for manager.
10. Record-deletion survival: delete the contract → its audit entries remain with `res_display` intact.

**Chrome MCP:**
11. 360 drawer from People roster: three tabs render, deep-link works (screenshot).
12. Upload + verify + expiry chips (screenshot).
13. Timeline with mixed events (screenshot); wage masking as a non-manager demo user.

---

## 7. Deploy & verify

Ritual (`--uid=odoo`). `-i biz_audit_trail,pb_employee_vault -u pb_people --test-tags /biz_audit_trail,/pb_employee_vault` (C18.40). Demo: seed a small document set + a few audited changes on PERSISTENT demo employees via the pb_demo generator (Phase-E lesson — generator-owned, regen-proof); report the generator diff. Verify drawer live on a demo minor (they already have history: bank rows + corrections make good timeline content).

---

## 8. Report back

1. Tests 1–13 + three screenshots.
2. Measured write overhead: time 1000 employee writes with rules on vs off (the mixin must be ~free when unwatched).
3. Generator diff for demo documents/timeline fixtures.
4. Deviations, file list, versions; gotchas → C18 wording.

---

## Kickoff line (paste into the Opus session)

> Read `docs/handovers/SUDIMA_PHASE_H_EMPLOYEE_360.md` and `docs/FORMULA_ENGINE_CONVENTIONS.md` (C1, C2, C18 binding — esp. C18.24/25/31/32/41), then implement Phase H exactly as specified: generic `biz_audit_trail` (append-only, rule-driven, ormcached, never blocks writes) wired to hr.employee + hr.contract, and `pb_employee_vault` (categorized documents with sentinel-guarded verification + expiry, and the Employee 360 drawer with the merged timeline in People). Tests §6, deploy §7, report §8. Audit entries are append-only with forced actor/stamp — nothing client-supplied ever sets who or when.
