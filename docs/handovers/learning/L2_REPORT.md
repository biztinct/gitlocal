# LEARNING L2 — Required training and country packs — report

Implementer: Opus, 2026-10-21. Spec: `L2_REQUIRED_TRAINING.md`. Ledger: `LEARNING_LEDGER.md` (new rows start at LN26).
Status: **PAUSED (owner usage limit) — work in progress, nothing tested, nothing deployed.**

## Where I stopped (2026-10-21 ~22:10 AEDT)

Committed as one WIP commit (`wip(training): LEARNING L2 in progress …`). **The module will NOT install/upgrade
in this state**: the manifest already lists assets that are not written yet (see "Next"). No test has run.

### Done (server side, written, not yet run)
- `pb_training` manifest → **19.0.1.6.0** (carries L1's unreleased 19.0.1.5.1 portal page-title fix — must be in
  the deploy plan and live walk: "portal /my/training page titles no longer say (ESS)").
- `models/training_common.py`: reason `required` ("Required"), dial `pb_training.enforce_cap` (500),
  `P_PACK_SWITCH = 'pb_training.pack.%s.%s'`.
- `models/hr_employee_ext.py`: `pb_safety_group` (1–6), `pb_posh_ic_member`, `pb_sg_experienced` (groups hr_user).
- `models/hours.py`: `slide.channel.pb_hours` + `_pb_hours()`; `assignment.hours` written on the done crossing;
  `pb.employee.document.hours` (test certificates from the course; uploads take optional `hours`).
- `models/requirement.py`: `pb.training.requirement` (audience × target × timing, headcount ratio fields,
  `unverified`/`ship_inactive`/`pack_paused`/`template_id`), set-based `evaluate()` (one audience search per rule,
  one assignment read, one document read, set-based join dates), `_cell()` state order per §3.1,
  `_shortfalls()` (per-site headcount lines), `_due_for/_assignment_vals`, `_convert_legacy()`, packs
  (`PACKS`, `_switch_pack` idempotent on/off/restore). Assignment gains `requirement_id`.
- `models/automation.py`: leg 5 `_enforce_requirements` (cap, savepoints, no-login skip, guard), runs beside the
  schedules leg; renewal leg skips courses owned by an auto-assign requirement (`_required_owned_courses`).
- `models/schedule.py`: F3 fix — day-one rule department match is `child_of`.
- `models/pb_training_required.py`: facade — `_can_manage/_require_manager`, F5 fix (`new_rule/new_schedule`
  manager-only), `matrix()`, `required_rules()`, `save_requirement`, `toggle_requirement_auto`,
  `archive_requirement`, `assign_from_cell`, `bulk_assign_required`, `set_safety_group`, `matrix_xlsx`,
  `matrix_pdf` (transient `pb.training.matrix.export`, no sudo), `required_settings`, `save_required_settings`,
  `switch_pack`, `safety_chip`, `_required_overview/_required_fragment`; verbs added to `_VERBS`.
- `models/required_reports.py`: Numbers section + 3 tiles + `country_reports`; the four country reports
  (`country_report_rows(cc)` → documented columns; `country_report_xlsx(cc)`); Overview queue chip "Missing
  required training" + headline fragment; `pb.my.training.required_for_me()`.
- `analytics._core` `hours_total`; learning record shows hours; tiles/board use the course's hours.
- Data: `data/pack_vn.xml`, `pack_in.xml`, `pack_id.xml`, `pack_sg.xml` (templates, noupdate, company empty,
  archived; [U] rows `unverified`). Migration `migrations/19.0.1.6.0/post-requirements.py` (enforce_cap row +
  legacy conversion). ACL rows + global company record rule. `views/requirement_views.xml` (admin fallback
  list/form, settings client action record, employee form fields, course hours). `report/required_matrix.xml`
  (landscape A4, 40 rows a page).
- `static/src/js/required_lens.js` (PbRequiredLens: tabs, matrix, popover, bulk bar, drawer, exports).

### Next (in order)
1. Write `static/src/xml/required_lens.xml` + `scss/required_lens.scss` (template for the JS above).
2. Write `js/required_settings.js` + `xml/required_settings.xml` (client action `pb_training_required_settings`,
   Settings card registered into `pb_settings_category` with `group: "hr"` from `training_palette.js`).
3. Write `js/safety_group_chip.js` + `xml/safety_group_chip.xml` (`pb_employee_360_chips`, calls `safety_chip`).
4. `training_palette.js`: REQUIRED lens → `PbRequiredLens` with `propsFromContext` (tab / state / pack);
   Overview JS: queue chip `required` opens the matrix on `state`; Overview tile; Numbers XML/JS: "Required
   training" section + "Country reports" buttons (`country_report_xlsx`); My learning: "Required for you" chips;
   certificates drawer: optional hours field.
5. Tests `tests/test_requirements.py`, `tests/test_packs.py` (T1–T15); update `test_learning_rail.py` (required
   lens component/props, Overview queue now five chips).
6. VI translations (export .pot, add msgstr for every new string; PO gate).
7. Local DB `am_l2_t` (copy of `am_l1_final`), own addons overlay before the scratchpad `stage` (do not touch the
   L1 server on :8069), upgrade, run suites, Chrome walk T16; demo seed `docs/handovers/learning/l2_demo_seed.py`.
8. Split the WIP into commits (a)–(e) is no longer possible cleanly; plan: keep this WIP commit and follow with
   feature-scoped commits for the rest; say so in the final report.

### Deviations so far (to carry into §3)
- Safety group / IC member / SG experienced sit in the Work page's Location group (stock `employee_type` is on the
  Payroll page, HR managers only).
- "Confirm with Rize" note is written tenant-neutral ("Confirm before switching on: …") because pack templates are
  on every tenant DB (another customer's name must not show to them). Easy to change if the owner wants "Rize".
- Settings card registers with `group: "hr"` in its own descriptor, so `pb_settings` needs no change (no
  `pb_settings` upgrade).
- `note` is Text (plain) not Html. Name patterns match whole words (so "SIO" never matches "Pension"); `|`
  separates alternatives.
- `vn_osh_retrain` ships unverified and does not detect job changes/absences (no reliable signal); `id_p2k3_report`
  is an unverified certificate-style reminder row.
- Day-one due date for somebody who joined long before the rule: today + days (not a past date).
- Enforcement leg runs beside the schedules leg (it makes assignments), not behind the reminders switch.
- Upload hours: HR drawer only (portal upload form untouched).
