# WFSETUP P10c — report: two "From the clocks" labels (B5 + B6), live ×5

Agent: Opus 5.5, 25 Nov 2026 (times UTC). Handover `WFSETUP_P10C_HANDOVER.md`. Built in worktree
`gitlocal-worktrees/wfsetup-p10c` from `origin/19.1`, rebased twice onto peer releases (WS78); code commit
`d1c4dbf5c` on `19.1` (deployed). Engineering receipt: real technical names on purpose.

## 1. What changed

| Where | What |
|---|---|
| B5 — `pb_hr_payroll_formula` 19.0.1.173.0 (`integrations/excel_connector.py`, `models/clock_source.py`, `models/formula_config.py`) | `generate_template(..., clock_notes={rule_id: text})`. `_build_pay_data_template` passes `hr.formula.config._pb_clock_template_notes()`. The template has no pay period, so the trigger is the scheme's clock date: each clock-answered input column (`_pb_clock_rules()`, every clock key incl. "left empty") keeps its HEADING (the re-import key, WS76), gets a grey heading (fill `EEF0F3`, grey bold font) and a cell note whose first line is **"From the clocks from <date> — leave blank for those months"** above the old note (name, code, column letter). No clock date, or no clock-answered column ⇒ `{}` ⇒ the old workbook. Date via `_pb_clock_from_label()` = babel `medium` in the reader's language ("Dec 1, 2026" en_US, "1 thg 12, 2026" vi, "1 Des 2026" id). |
| B6 — `pb_formula_studio` 19.0.1.216.0 (`models/pb_formula_studio.py`, `static/src/xml/studio.xml`, `static/src/scss/studio.scss`) | `_source_block` adds `source.clock = {key, from, label, hint}` via `_source_clock_chip(rule)` — only for an input with `pb_clock_key` on a scheme with `pb_clock_from`. New template `pb_formula_studio.SrcClockChip` (Lucide clock, `ce-srcchip s-clock`, the pay period's violet family with a thin ring) is t-called in BOTH editor bodies right after "Set to read" (WS77). Chip **"From the clocks — from <date>"**; tooltip "Answered by the clocks: <fact>. Pay periods from <date> take this value from the clocks, not the pay data file; earlier pay periods read it as before." Read-only, no new action. The declared source (`declared`) is untouched (WS75). |
| Translations | vi_VN + id_ID for the three new sentences. `pb_formula_studio` gets its first `id_ID.po` (just these two). PO gate on the box: every file ok, 0 empty, 0 vendor word. |
| Deploy scripts | `docs/handovers/wfsetup/p10c/` — the `p10b/` scripts trimmed to two modules (no connector zip handling) + `p10c_bundle.py`. |
| Learn | Checked: no lesson, tour or replica shows the template's headings or the editor's source card (the Mapping replica only shows the "Download a template" button, on a scheme without a clock date). Nothing to change. |

Not changed (binding non-goals held): no calculation, no stored field, no change to which inputs come from the
clocks, no data change on live, nothing in `pb_clock` / `pb_attendance_policy` / `pb_workforce_setup`.

## 2. Tests

New `pb_formula_studio/tests/test_p10c_clock_labels.py` — **7/7 pass**:
1. `test_01` clock-dated template (flat and multi-sheet): the three clock columns carry the sentence + old note + grey
   heading; headings, order and sheets unchanged; Employee Code / Meal Allowance identical to before; still headings only.
2. `test_01b` the date follows the reader's language (vi "1 thg 12, 2026", id "1 Des 2026", en "Dec 1, 2026").
3. `test_02` no clock date (keyed and unkeyed, flat and multi-sheet) and "clock date but nothing keyed": every zip part
   byte-identical to the pre-P10c call (only `docProps/core.xml`, the creation stamp, excluded).
4. `test_02b` the marked template still round-trips through header discovery.
5. `test_03` source payload: chip with label/date/key/hint for the three clock inputs, nothing for the others or
   without a date, declared source identical to an unkeyed twin, unbinding removes it.
6. `test_03b` the chip is t-called in both editor bodies.
7. `test_04` vi + id msgstr present, code-type, `odoo-python` marker, placeholders kept, no vendor word.

Full suites `pb_hr_payroll_formula` + `pb_formula_studio` on a local copy, unchanged `origin/19.1` vs P10c on the
same database: **1,274 → 1,281 tests, 8 failures/errors before and the same 8 after** (pre-existing: Journey cold
start, net-pay candidates, four One-Mapping-Home static checks, RUNSRC board lane two chips, scheme-context currency).

Local browser (Chrome, a seeded draft scheme with three clock inputs): the chip renders beside "Set to read" in
English ("From the clocks — from Dec 1, 2026"), Vietnamese ("Từ máy chấm công — từ 1 thg 12, 2026") and Indonesian
("Dari mesin absensi — mulai 1 Des 2026") with the tooltip translated; Meal Allowance shows no chip; Full mode shows
it in both source cards. Console: 0 errors, 0 warnings.

## 3. Deploy (normal tier, labels only) — LIVE ×5

- Before: Codex "Attendance Rules" had an open START on `pb_hr_payroll_formula` (shipped 19.0.1.172.0). Waited for its
  DONE (11:40), rebased, bumped to 173, checked live tree = origin tree for both modules before staging (WS78).
- Prep 11:48–11:50 (`p10c_prep.sh 20261125T1148Z`): staged = commit; previous trees saved; PO gate clean.
- START 11:50 (`p10c_tries.sh` in a `systemd-run` unit). Tries 1–2 waited (sign-in activity on sudima until 11:43:49);
  try 3 at 12:00: backups ×5 `/odoo/backups/wfsetup-p10c-20261125T1148Z/golive-*.dump`, stop 12:04:30, scoped
  `rsync -a --delete` per module, `-u pb_hr_payroll_formula,pb_formula_studio` one database at a time:
  payobook_template 115 s, p0clone 132 s, rize 122 s, payobook 136 s, sudima 128 s, exit 0 each (only the known 3
  `payroll_analytics` lines each); asset purge + `web.assets.version` ×5; start 12:17:04.
  **Downtime 755 s (12.6 min).** DONE 12:17, verification NOTE 12:23.
- Verification (`p10c_verify.sh`): 2 trees = commit; versions ×5 below; jobs = prep snapshot ×5 (59/40/49/92/91 active;
  payobook_template 84, 85, 86, 91 re-activated by `-u` and switched straight back off); data right-before-stop = after
  on payobook, payobook_template, p0clone, sudima; rize +6 chatter messages (technical job notes, as in P10b); clock
  connections unchanged ×5; server log since start 0 ERROR, 0 Traceback, 0 asset errors; sites 200 ×5.
  The probe's "clock chip template False" is a probe flaw (it looked in the JS files; templates live in the bundle's
  template assets) — a second read-only probe found `SrcClockChip` in the template assets.

## 4. Versions (installed = manifest on payobook, payobook_template, p0clone, rize, sudima)

pb_hr_payroll_formula 19.0.1.173.0 · pb_formula_studio 19.0.1.216.0

## 5. Live look

- **sudima, look-only** (read-only `odoo-bin shell`, rolled back; no login enabled): scheme 7844 still **draft**, clock
  date 2026-12-01; the editor payload carries **11 chips "From the clocks — from Dec 1, 2026"** (vi "Từ máy chấm công —
  từ 1 thg 12, 2026") — the 4 paid inputs + 7 information columns P10b mapped; the template marks the same 11 headings
  (Paid day equivalents, Normal overtime base hours, Overtime premium equivalent hours, Sunday base hours, Days worked,
  Paid leave days, Public holiday days, Paid normal hours, Actual hours, Late minutes, Overtime above the legal limit).
- **payobook.com, QA login**: template download for "Payobook Retail — End-Month Payroll" ok (11 columns); studio and
  component editor open; payobook has no scheme with a clock date, so no chip — the card reads exactly as before;
  console clean. Edit cancelled, session signed out.
- Nothing confirmed, published, switched on, approved or run; no data written on any database.

## 6. Unsure / notes

- **Set to read says "No source" beside the chip** on sudima's clock inputs whose file binding is not declared — true
  (before 1 Dec nothing else feeds them) but it reads a little odd next to the chip. Left as is: changing the declared
  wording is a source-ranking question (WS75), out of scope.
- The chip is shown from the moment a date is set, also for months before it — by design the label carries the date.
- Full editing mode shows the source card twice (pre-existing, WS77); the chip follows both.
- The template mark is a cell note + grey heading, not heading text (WS76). In Excel a note shows on hover; the grey
  heading is the at-a-glance signal.
- Codex's new clock key "Late working days (for allowance rules)" has no vi/id translation yet (WS79) — not touched.

## 7. Ledger

WS76–WS79 added to `WFSETUP_LEDGER.md`. B5 + B6 marked done in `WFSETUP_BACKLOG.md`.
