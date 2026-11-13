# SUDIMA Phase G — Attendance Workflow (Missing-Punch, Late Rules, Corrections, Bulk Import)

**Scope item:** #4 Attendance Management (*Partial + Needs WOW-UX*): missing-punch workflow, late-arrival/early-departure rules, multi-tier correction approvals, bulk import wizard, and a branded cockpit over the raw engines.
**Module:** NEW `pb_attendance_flow` (overlay — the approval engine is the existing `biz_approval_chain`; no new generic engine needed).
**Ledger:** C1, C2, C18 binding (esp. C18.17 one-permission-world, C18.24 sentinel writes, C18.37 merge-never-replace shared payloads, C18.38 report-don't-retro-enforce, C18.40 scoped test runs).
**Prerequisites:** Phase B (grid + `pb_entry_source` rail), Phase C (`biz_approval_chain`, trip-day seam), Phase E (young-worker punch constraint — corrections and imports must survive it).

---

## 1. Scope

1. **Exception engine**: a per-day feed of attendance exceptions — missing punch, missing check-out, late arrival, early departure — computed against published shifts, minus approved-trip days and validated leaves.
2. **Correction workflow**: `hr.attendance.correction` request (create/adjust/delete a punch) on the approval chain, manager-approved, applied by a single guarded writer.
3. **Late/early rules as config**: per-company grace minutes and counting policy — DATA, not constants.
4. **Bulk import wizard**: CSV/XLSX → map → validate → commit, per-row error isolation.
5. **"Attendance Control" cockpit**: exceptions queue, corrections pipeline with the stepper, compliance KPIs.

### Binding non-goals
- **NO changes to `biz_week_grid` internals** or the Phase-B save path — the grid stays the bulk-entry surface; this phase is the exception/correction surface.
- **NO auto-fixing**: the system never invents a punch; every mutation is a human-approved correction.
- **NO payroll changes** — attendance feeds payroll exactly as today.
- **NO device/kiosk integrations** (RFID/face modules stay unsurfaced this phase).
- **NO retro-enforcement**: historical days are REPORTED in the feed, never mutated (C18.38).

---

## 2. Verified plumbing facts (do not re-derive)

- ✓ **Shift compliance already computed**: `hr.shift.planning.compliance_status` (`pending|on_time|late|early_leave|absent|overtime`) with a hardcoded 15-min tolerance (`pb_hr_workforce/models/shift_planning.py:80-101`) — absent = no `actual_check_in` and `end_datetime` past. This phase makes the tolerance config-driven and consumes the statuses; it does not duplicate the math.
- ✓ **Shift fields**: `employee_id`, `date`, `start_datetime/end_datetime`, `actual_check_in/out`, `state` (`draft/published/completed/cancelled`) (`shift_planning.py:10-114`); templates carry `start_hour/end_hour/is_overnight` (`shift_template.py:19-46`); 5 demo templates seeded (`data/shift_template_data.xml:5-63`).
- ✓ **Grid source rail**: `hr.attendance.pb_entry_source` selection currently `('grid',)` — device punches have blank source and are never grid-mutated (`pb_hr_workforce/models/hr_attendance.py:6-17`). Extend via `selection_add` with `correction`, `import`.
- ✓ **Per-cell savepoint + stale-token pattern to clone**: `save_week_entries` (`attendance_weekentry.py:393-471`, savepoint :456-459, token = write_date snapshot :73-79,483-484).
- ✓ **Trip-day exclusion seam**: `pb.business.trip._get_trip_day_map(employees, date_from, date_to)` → `{employee_id: set(ISO dates)}` of APPROVED trip days (`pb_business_trip/models/pb_business_trip.py:348-376`). `pb_business_trip` IS a hard dependency of the demo stack — still, resolve via `if 'pb.business.trip' in self.env` so the module stays installable without trips.
- ✓ **Leaves**: `hr_holidays` is in the stack (dep of om_hr_payroll `__manifest__.py:17`); validated leave days exclude an absence exception (domain on `hr.leave` state `validate`).
- ✓ **Approval chain**: `biz.approval.chain.mixin` — `_approval_transitions` dict, `_CHAIN_WRITE_TOKEN` object-identity sentinel, `_advance_state`, `_approval_can` override for person-specific tiers, append-only `biz.approval.step.log` with forced user/stamp (`biz_approval_chain/models/biz_approval_mixin.py:12-175`, log :6-49). **Manager-tier precedent to clone**: `pb.business.trip._approval_can` (:168-196) — tier passes when the user IS `employee_id.parent_id`'s user, no group needed.
- ✓ **Stepper widget**: `biz_approval_stepper` reads `approval_widget_json` (`biz_approval_chain/static/src/js/approval_stepper.js:20-98`); themeable via `--bac-*` props.
- ✓ **Young-worker punch constraint fires on ANY create/write** incl. corrections and imports (`pb_young_worker/models/hr_attendance.py:18-41`) — friendly per-row surfacing needed, never a batch-killing traceback.
- ✓ **Import UX kit**: `pb_import_kit` = pure assets (tokens `import_tokens.scss:1-50`, `ic()` Lucide map `import_icons.js:6-56`); batch-pipeline cockpit precedent `pb_import/models/pb_import.py:38-146`. No attendance file-import exists today (only connector sync via `pb_import_advanced` `sync_wizard.py:14`).
- ✓ **Cockpit pattern**: `pb_bank_ocr` action tag + AbstractModel RPC facade + OWL (`pb_bank_ocr/views/pb_bank_ocr_action.xml:3`, `static/src/js/pb_bank_ocr.js:24-60`). Sidebar: `pb.sidebar.item` data records, icon = Lucide name string (`pb_sidebar/data/pb_sidebar_data.xml`).
- ✓ Versions: pb_hr_workforce 19.0.4.6.0, biz_approval_chain 19.0.1.0.3.

---

## 3. Architecture

### `pb_attendance_flow` (depends: `pb_hr_workforce`, `biz_approval_chain`, `pb_sidebar`, `pb_import_kit`; soft-hooks to `pb_business_trip`, `hr_holidays`)

```
pb_attendance_flow/
├── models/
│   ├── attendance_rule.py        pb.attendance.rule (per-company grace/policy config)
│   ├── attendance_exception.py   pb.attendance.exception.engine (AbstractModel — the feed)
│   ├── attendance_correction.py  hr.attendance.correction (chain mixin + guarded apply)
│   └── hr_attendance.py          pb_entry_source selection_add ('correction','import')
├── wizards/attendance_import.py  pb.attendance.import.wizard (upload→map→validate→commit)
├── models/attendance_cockpit.py  pb.attendance.flow (RPC facade for the cockpit)
├── data/attendance_rule_data.xml VN defaults (noupdate="1"): grace_in 15, grace_out 15
├── security/ + views/ + static/src/ (cockpit, tag pb_attendance_flow)
```

**Config — `pb.attendance.rule`** (per company, C18.20 two-search company-else-global): `grace_in_minutes` (default 15 — replaces the :93 hardcode via a small `shift_planning.py` inherit that reads the rule), `grace_out_minutes`, `count_late_as` (`report_only|deduct_flag`) — Phase G only REPORTS (`report_only`); the deduction flag is future payroll wiring, present in config but unused (documented).

**Exception engine** (`pb.attendance.exception.engine`, all `@api.model`, batch): `get_exceptions(employees, date_from, date_to)` → rows `{employee_id, date, kind: missing_punch|missing_checkout|late|early_leave, shift_id, detail, minutes}` computed from published `hr.shift.planning` + `hr.attendance` of the local day, **minus** trip days (soft-hook) **minus** validated leave days **minus** days before the employee's first contract day. Late/early read `compliance_status` where a shift row exists; `missing_checkout` = open punch older than N hours (config, default 16). Batched like `pb.young.worker.check_period` (one search per model per cohort — clone that shape from `pb_young_worker/models/young_worker_rule.py:217-343`).

**Correction — `hr.attendance.correction`** (chain mixin): `employee_id`, `date`, `correction_type` (`create|adjust|delete`), `attendance_id` (required for adjust/delete; must belong to employee+date), `new_check_in`, `new_check_out`, `reason` (required), `exception_kind` (link back to the feed row that spawned it). Transitions:
```python
_approval_transitions = {
    ('draft', 'submitted'): None,                                   # owner or officer files it
    ('submitted', 'approved'): 'hr_attendance.group_hr_attendance_officer',
}
```
with `_approval_can` overridden so the employee's manager (`parent_id` user — clone trip :168-196) may also approve. On approve (`_after_approval_transition`): **the single guarded writer** `_apply()` creates/writes/unlinks the `hr.attendance` row `with_context(pb_att_correction=_CORR_TOKEN)` (module-level `object()` — C18.24) and stamps `pb_entry_source='correction'`. A small `hr.attendance` write/unlink guard: rows with `pb_entry_source == 'correction'`… no — simpler and stronger: corrections may touch ANY row (that's their job), but ONLY via `_apply()`; the guard is that `hr.attendance` refuses `unlink` of device-sourced rows (blank source) UNLESS the sentinel context is present (extends the Phase-B rail to deletes). Young-worker constraint fires naturally on apply — surface its ValidationError as the correction's refusal reason, not a crash.

**Import wizard** (`pb.attendance.import.wizard`, TransientModel, pbim shell): upload (binary) → parse CSV/XLSX → column mapping (employee by `employee_code` else exact name; date; check_in; check_out; tz = employee calendar) → `validate()` dry-run returns per-row verdicts (unknown employee, overlap with existing punch, young-worker cap breach, malformed time) → `commit()` writes valid rows `pb_entry_source='import'` under **per-row savepoints** (clone :456-459); result = created/skipped counts + downloadable error report. Never partial-writes a row.

**Cockpit** (`pb.attendance.flow.get_control_data()`): KPI strip (open exceptions, pending corrections, late % this week, imports this month) · exceptions queue grouped by kind with "File correction" one-click (pre-filled) · corrections kanban (chain states + stepper) · import launcher. HR/officer gated (`_is_hr` pattern from `pb_bank_ocr_cockpit.py:26-36`). Sidebar item "Attendance Control", section Workforce, icon `clock`.

---

## 4. WOW-UX specification (exceptional — and any legacy surface touched gets upgraded, binding F–J rule)

All Phase-G surfaces are net-new bespoke OWL — nothing stock reaches the user. If your build path surfaces a legacy view (e.g. a native `hr.attendance.correction` form or the raw hr.attendance list), replace it with the bespoke experience; native views live off-menu as admin fallbacks only. Chrome-MCP validate the edge cases (zero exceptions, 100+ exceptions, refused correction) — empty and overflow states must be designed.

1. **Exceptions queue**: day-grouped rows — kind icon (`alert-circle` missing punch, `log-out` missing checkout, `timer` late, `door-open` early), employee avatar, shift chip (template code + hours), minutes badge (amber <30, rose ≥30), one-click "File correction" that opens the pre-filled composer.
2. **Correction composer**: split card — left the day's punches timeline (device rows locked with a shield tooltip), right the proposed change with live before/after delta; the chain stepper renders on the right rail.
3. **Import stepper**: pbim wizard shell (upload → map with auto-guessed columns → validation table with green/rose row pills → commit summary). Clone the Import-kit look (`.pbim` shell); errors downloadable.
4. KPIs pulse rose when open exceptions > 20. Lucide only; no gradients/emoji.

---

## 5. Safety rails

1. **Single-writer**: every attendance mutation from this module goes through `_apply()` under the sentinel; device-row deletion is blocked without it. State changes only via the chain (`_CHAIN_WRITE_TOKEN` — already enforced by the mixin).
2. **Approver ≠ requester** on corrections: the submitting user cannot approve their own request (check in `_approval_can`); admin excepted.
3. **The feed is read-only** — computing exceptions never writes anything.
4. **Trip/leave awareness**: a trip day or validated leave day can never produce a missing-punch exception (test both).
5. **Young-worker + grid rails intact**: corrections/imports trip the daily-cap constraint like any punch; the grid's token/stale logic is untouched.
6. **Import isolation**: one bad row never rolls back the batch; nothing is written during `validate()`.
7. Config edits payroll-manager gated; grace bounds 0–120 constrained.

---

## 6. Test cases

**Server:**
1. Exception engine: seeded week (shift published, no punch → missing_punch; punch in late 20 min → late with minutes; check-out 40 min early → early_leave; open punch 20h → missing_checkout) returns exactly those rows.
2. Trip exclusion: an approved trip day with a published shift and no punch produces NO exception; a validated leave day likewise.
3. Grace config: with grace_in=30 the 20-min-late row disappears; company-B rule isolation (C18.20 two-search).
4. Correction lifecycle: employee files adjust → manager (parent_id user, no officer group) approves → attendance updated, `pb_entry_source='correction'`, `biz.approval.step.log` rows exist; requester cannot self-approve (AccessError).
5. Delete-type correction removes a grid row; a DEVICE row (blank source) unlink without the sentinel raises; via approved correction succeeds.
6. Direct `write({'state': 'approved'})` on a correction raises (mixin token — regression of C18.24).
7. Young-worker: a correction pushing Minor 17 past the daily cap is refused with the friendly law message and the correction lands in `refused` with the reason, not a traceback.
8. Import: 5-row file (1 unknown employee, 1 overlapping punch, 1 cap breach, 2 good) → validate flags 3, commit creates exactly 2 with `pb_entry_source='import'`; re-import of the same file creates 0 (overlap detection).
9. Grid untouched: `save_week_entries` behavior on a corrected day still respects tokens (stale token → refused).
10. Adults regression: a 12h device punch for an adult creates no exception when no shift is published, and nothing blocks it (report-only world).

**Chrome MCP:**
11. Cockpit queue with seeded exceptions; file-correction flow end-to-end with stepper (screenshots).
12. Import wizard full pass on a demo file incl. the error table (screenshot).
13. Manager approval from the manager's login (the parent_id tier).

---

## 7. Deploy & verify

Ritual (`--uid=odoo`, stale-PID kill). `-i pb_attendance_flow -u pb_hr_workforce --test-tags /pb_attendance_flow,/pb_hr_workforce` (C18.40: never bare). Seed demo exceptions on persistent demo employees (reusable, not throwaway — extend `pb_demo` generator if you add fixtures, per the Phase-E lesson). Verify §6.11-13 live; leave the demo world clean (imports rolled into demo data or removed).

---

## 8. Report back

1. Tests 1–13 + three screenshots.
2. The shift_planning grace inherit — exact diff (it touches Phase-B territory; confirm compliance_status math unchanged for the default 15).
3. Demo fixture strategy you used (generator-owned?).
4. Deviations, file list, versions; new gotchas → C18 wording.

---

## Kickoff line (paste into the Opus session)

> Read `docs/handovers/SUDIMA_PHASE_G_ATTENDANCE_WORKFLOW.md` and `docs/FORMULA_ENGINE_CONVENTIONS.md` (C1, C2, C18 binding — esp. C18.24/37/38/40), then implement Phase G exactly as specified: new `pb_attendance_flow` with the exception engine (trip/leave-aware), sentinel-guarded correction workflow on biz_approval_chain, config-driven grace rules, the bulk import wizard with per-row savepoints, and the Attendance Control cockpit. Tests §6, deploy §7, report §8. The system never invents a punch — every mutation is a human-approved correction through the single guarded writer.
