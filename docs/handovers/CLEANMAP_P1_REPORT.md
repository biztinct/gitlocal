# CLEANMAP P1 — phase report

**Built 2026-09-19/20 by Opus, from `CLEANMAP_P1_LEFT_LIST_HANDOVER.md`.**
Shipped as `pb_formula_studio 19.0.1.199.0`. Live on `payobook`, `abm`,
`payobook_template`, `rize`, `rztest`. Nothing pushed.

## 1. CM1 confirmed — with one correction

Read read-only off **rize batch 1128** (`Rize Vietnam Payroll · August 2026 —
pay data`), the first import line's `raw_data_json`, key order as stored:

| # | key |
|---|---|
| 1 | `Mã nhân viên\n(Code)` |
| 2 | `Họ và tên (Full name)` |
| 3 | `Vị trí\n(Position)` |
| 4 | `Loại (Type)` |
| 5 | `Tham gia BHXH (SHUI Joining)` |
| 6 | `Ngày bắt đầu \n(Commencing  date)` |
| 7 | `Ngày ký hợp đồng \n(Date contract)` |
| 8 | `Ngày làm việc cuối cùng\n(Last working date)` |
| 9 | `Lương hợp đồng (Gross contract salary USD)` |
| 10 | `Lương hợp đồng (Gross contract salary VND)` |
| 11 | `Lương bảo hiểm (Insurance salary)` |
| 12 | `Ngày công chuẩn\n(Standard working days)` |
| … | … |
| 43 | `Hỗ trợ sự cố (Support for incident)` |
| 44 | `Salary\|Mã nhân viên\n(Code)` |
| … | … |
| 86 | `Salary\|Hỗ trợ sự cố (Support for incident)` |
| 87–174 | `Salary\|A`, `A`, `Salary\|B`, `B`, … `Salary\|AR`, `AR` |

**174 keys**, in three blocks. The handover said "every `heading` +
`Sheet|heading` for every column FIRST"; the truth is *all* bare headings
(1–43), *then* all `Sheet|heading` (44–86), then the letter PAIRS (87–174).
The fold was written to the real shape — see ledger **CM5**.

**43 unique headings but 44 letters.** Two columns in the workbook carry the
same heading text and `base_row = row.copy()` collapses them, so the heading
count is one short of the column count. That is why the fold decides a
letter-shaped key by the **unbroken A, B, C… run of letters written for that
sheet** (44) and not by the heading count (ledger **CM6**); and why
`Salary|AR` / `AR` fold away with no canonical card to point at (**CM7**).
Nothing on rize binds them.

## 2. Card counts on rize, before → after

`import_mapping_data(config 3938 "Rize Vietnam Payroll", …)`, measured through
the live session on `rize.payobook.com`.

| FROM | before | after |
|---|---|---|
| *(default — no FROM asked)* | **180** cards: 43 template file + 131 pay run + 6 pay-run lane | **49**: 43 + 6 |
| `Rize Vietnam Payroll · August 2026 — pay data` (batch 1128) | **180** (same three lanes) | **49**: 43 pay-run columns + 6 pay-run lane |
| `Rize_Vietnam_Payroll_Templatev2 DATA.xlsx — template file` | *not reachable — it was not a FROM entry* | **49**: 43 template columns + 6 pay-run lane |

* Cards whose label is a bare column letter: **0** on every FROM (was 88).
* Wires with no card: **0** on every FROM, before and after.
* "Mapped, but not in this file": **empty** on rize — all 41 spreadsheet
  bindings use the `Salary|heading` spelling and all 41 are cards.
* Mapped wires: **42** before and after (41 columns + 1 pay-run period).

### The one suggestion that disappeared (deviation from the handover)

The handover predicted "still 42 mapped, **1 suggested**". Reality after is
**42 mapped, 0 suggested**, and that is correct:

* the suggestion was drawn from the **duplicate bare-heading card**
  `Phụ cấp khác (Others)` onto component `PHUCAPKHACA`;
* the real column, `Salary|Phụ cấp khác (Others)`, is already bound — to
  component `PHUCAPKHAC` (id 14222), whose name is character-for-character the
  same;
* the board has always refused to suggest from a column that is already wired.
  With one card per column instead of four, that rule now applies.

**Owner debt surfaced:** the Rize Vietnam scheme has two components both named
"Phụ cấp khác (Others)" — `PHUCAPKHAC` (fed by the column) and `PHUCAPKHACA`
(fed by nothing). Only the duplicate card was keeping the second one visible.

## 3. Tests

Run on the live box against `p9clone` (a clone of the production database, so
the fixtures meet real data), `odoo-bin -u pb_formula_studio --test-enable
--test-tags /pb_formula_studio --http-port=8199`.

**Baseline first** — the same suite on the code at `b8509939d`, from a scratch
addons dir, so a failure can be told from a regression.

### Python (handover §5, 1–14) — `tests/test_cleanmap_left_list.py`, new

| # | test | result |
|---|---|---|
| 1 | multi-sheet, 9 columns × 4 names → 9 cards, keys `Sheet\|heading`, letters A–I | PASS |
| 2 | alias map sends `heading`, `Sheet\|A`, `A` to `Sheet\|heading` | PASS |
| 3 | `Total` on two sheets → two cards, both re-prefixed | PASS |
| 4 | secondary sheet (qualified-only letters) folds too | PASS |
| 5 | single-sheet shape byte-identical (+ the old 01–04, 06–12) | PASS |
| 6 | FROM = a pay run draws nothing from the template file or from history | PASS |
| 7 | a rule bound to `Ghost Column` → exactly one Lane C card, its wire on it | PASS |
| 8 | a rule bound to the BARE heading → re-pointed, no Lane C, no suggestion | PASS |
| 9 | every wire starts from a card, on both shapes and on `source='sample'` | PASS |
| 10 | `batch_id='sample'` → sample columns + six period cards, `context_id == 'sample'`, no int-cast crash | PASS |
| 11 | no file, no batch → "Already used…" + "From this scheme's history" still there | PASS |
| 12 | `contexts[0]['kind'] == 'sample'` only when a sample exists | PASS |
| 13 | read-only: row counts + `source_binding_key` checksum unchanged across every FROM | PASS |
| 14 | six period cards on every FROM | PASS |

### The regression suite

`test_runsrc_left_columns` **12/12 PASS**, `test_excel_onramp` **PASS**,
`test_mapping_studio` **PASS**, `test_journey_view` — see below.
Whole module: **430 of 432 PASS**.

**Two failures, both pre-existing** (proved by the baseline run on the same
database):

* `TestJourneyView.test_03j_the_run_lane_is_a_ghost_when_nothing_was_processed`
  — `AssertionError: True is not false`. Fails identically on the baseline
  code. It reads whatever formula config is first on the database and asserts
  against its processed batches; on `p9clone` that data does not satisfy it.
* `TestJourneyTransformations.test_07a2_the_board_opens_on_a_connector_that_HAS_rules`
  — fails identically on the baseline code. Nothing in this phase touches the
  Transformations board.

### Tests this phase had to change, and why

* **`test_runsrc_left_columns.test_05`** — REWRITTEN, as the handover directs.
  It pinned RUNSRC A's known gap ("a row that arrives as a dict has no
  aliases; keep every key"). That is the defect. It now asserts one card per
  real column, keyed `Sheet|heading`. The reversal is deliberate and cites the
  handover in the docstring.
* **`test_runsrc_left_columns.test_06`** — it was **already RED** before this
  phase (baseline: *2 failed of 12*). RUNSRC A1b started stripping `Sheet|` off
  a card's LABEL and this assertion was never updated:
  `AssertionError: Lists differ: ['Employee code', 'Basic salary'] != ['SEVL|Employee code', 'SEVL|Basic salary']`.
  It now asserts the card's `id` *and* its label. Ledger **CM8**.
* **`test_excel_onramp.test_13`** — a docstring-pinning test. It required the
  words "FOUR lanes" in `import_mapping_data`'s docstring; the four lanes are
  what this phase removed. It now requires the sentence the docstring makes
  instead: *"one file source is on screen at a time"*.

### Browser (handover §5, 15–20) — Chrome MCP, `rize.payobook.com`

Signed in as `ash@biztinct.com` (uid 2) in the existing session.

| # | check | result |
|---|---|---|
| 15 | FROM = August 2026 pay data → **49 fields**, **0** cards labelled a bare letter, 42 mapped, every wire on a card, console clean | PASS (**0** suggested, not 1 — §2) |
| 16 | switch FROM to the template file → 43 + 6 = 49, same 42 wires | PASS |
| 17 | re-read the SAME workbook ("Replace file…") → `context_id == 'sample'`, 49 fields, the board lands on the template-file FROM | PASS (the read timestamp it wrote was restored) |
| 18 | search box still offers *Use "A" as a spreadsheet column* | PASS |
| 19 | single-sheet schemes unchanged | PASS — see the table below |
| 20 | the new strings render in Vietnamese | PASS (directly for the FROM entry, see below) |

Console on the board: **clean**. The only message is a pre-existing
accessibility notice ("a form field element should have an id or name"), which
is unrelated and present before the phase.

**Lane C rendering** was verified by putting the `orphan` class on a card in
the browser (a DOM-only simulation — no live database has a binding that
qualifies): amber wash, amber plug, sublabel "this file has no such column",
under the lane heading "MAPPED, BUT NOT IN THIS FILE". The compiled stylesheet
served to the browser contains the rule, which also proves the SCSS bundle
rebuilt without a Sass error.

**Dark mode**: this cockpit has no dark variant on this build — setting
`data-theme="dark"` on `<html>` changes nothing on it, before or after the
phase. Nothing was regressed; there is simply no dark surface here to check.

**Test 20 detail.** `import_mapping_data` read with `lang=vi_VN` on rize
returns the FROM entry as
`Rize_Vietnam_Payroll_Templatev2 DATA.xlsx — tệp mẫu` (English:
`… — template file`). The other four new strings sit in the same appended block
of the same `.po`, in the same format, and the parse gate on the box confirmed
each one carries `odoo-python` / `odoo-javascript` and a valid occurrence — but
they could not be rendered on a live screen, because no database has a binding
that opens Lane C.

### Test 19 in full — every scheme with a file, on payobook and abm

Reconstructed from the live data (the old fold + the old four-lane union
against the new lanes), because I could not sign in to `payobook.com` or
`abm.payobook.com` — see §7.

| database | scheme | file shape | cards before | cards after | Lane C |
|---|---|---|---|---|---|
| payobook | Payobook Corporate Office — End-Month | single-sheet | 9 | **9** | 0 |
| payobook | VPTQ Mid Cycle | single-sheet | 186 | **186** | 0 |
| payobook | Payobook Retail — End-Month | single-sheet | 9 | **9** | 0 |
| payobook | VPTQ End Cycle | merged | 198 | **54** | 0 |
| abm | AB Mauri Payroll | merged | 218 | **59** | 0 |
| rize | Rize Vietnam Payroll | merged | 180 | **49** | 0 |
| rize | Rize India Payroll | single-sheet | 34 | **34** | 0 |

Every single-sheet scheme is unchanged, as the handover requires. Every merged
workbook gets the cure. **No binding landed in "Mapped, but not in this file"
on any database.**

## 4. Deviations from the spec, and why

1. **The alias map is used differently on the two storage shapes** (ledger
   **CM9**). On the merge shape a wire is re-pointed at the column's card. On
   the interleaved shape a component bound to a bare column letter keeps a card
   of its own in the file lane, restored from the stored keys — that is RUNSRC
   A's pinned behaviour (`test_02`, `test_12`, which the handover requires to
   stay green untouched) and it is truthful: the file really does have a column
   `B`. Re-pointing there would have broken two green tests to say the same
   thing.
2. **The RD60 default ladder no longer leaves this scheme** (ledger **CM11**).
   Its last three rungs accepted any load on the database, so a scheme whose
   only file had been dropped on this board opened on **another scheme's pay
   run** — harmless while the list was a union, fatal once the list obeys FROM.
   Every load on every live database carries a scheme (checked 2026-09-19), so
   those rungs only ever mis-fired. New order: this scheme's pay-data load →
   this scheme's any load → this scheme's template file → the no-file state.
   Found by `test_excel_onramp` 03/04/04b, which went red on the first run.
3. **A batch belonging to another scheme is ignored server-side, and the
   client clears FROM when the scheme changes** (ledger **CM12**). Found in the
   browser: switching TO from Rize India to Rize Vietnam left FROM reading
   "Rize India Payroll · August 2026 — pay data, 75 fields" over a Vietnam
   scheme — the header naming one file over another file's columns.
4. **One suggestion fewer on rize** — §2 above.

Everything in the binding non-goals held: `raw_data_json`,
`_raw_data_from_row`, `_load_multisheet_data`, `source_binding_key` and
`import_sample_columns_json` are untouched; the resolver, the create/delete
paths, the suggestion scoring, the right-hand column, the file strip and the
other tabs are untouched.

## 5. Deploy / verify

`pb_formula_studio` only, `19.0.1.198.0` → **`19.0.1.199.0`**. Clean staging
dir `/tmp/deployCM1`, per-module `rsync -a --delete` into
`/odoo/odoo-server/addons/pb_formula_studio/`, PO parse gate green
(2 304 rows, 2 265 reach a screen, all five new strings carry
`odoo-python`/`odoo-javascript`), all databases upgraded, `/web/assets/%`
attachments purged and `web.assets.version` bumped per database, service
restarted.

**Content check** — SHA-256 over every file of the module tree (skipping
`__pycache__`, `*.pyc`, `.DS_Store`), repo vs server:

```
repo   fc7403bce867bcfa3e9593ab70b437ea67151e70688318fe9751feff026e9ac9
server fc7403bce867bcfa3e9593ab70b437ea67151e70688318fe9751feff026e9ac9
```

**Version check** — `ir_module_module.latest_version` per database:

| database | pb_formula_studio | upgrade exit |
|---|---|---|
| payobook | 19.0.1.199.0 / installed | 0 |
| abm | 19.0.1.199.0 / installed | 0 |
| payobook_template | 19.0.1.199.0 / installed | 0 |
| rize | 19.0.1.199.0 / installed | 0 |
| rztest | 19.0.1.199.0 / installed | 0 |
| p9clone *(test clone)* | 19.0.1.199.0 / installed | 0 |

`addons_path` is still the single entry `/odoo/odoo-server/addons`, and
`/odoo/custom/addons` is still the guard file. Every scratch directory used for
the baseline run was removed.

## 6. Ledger

New entries **CM5–CM12** in `CLEANMAP_LEDGER.md`.

## 7. What I could not do

* **I could not sign in to `payobook.com` or `abm.payobook.com`** — no
  credentials (a standing owner debt). Test 19 for those two databases was done
  by reconstructing both card counts from their live data instead of by opening
  the board. Everything else in the browser was done on `rize.payobook.com`,
  where the session was already signed in as `ash@biztinct.com`.
* **Lane C has no live example**, so its two Vietnamese strings were proved by
  the parse gate rather than read off a screen, and its card was styled-checked
  by simulation in the DOM.
* **`acme` no longer exists** on the cluster; the databases are `payobook`,
  `abm`, `payobook_template`, `rize`, `rztest` (+ the `p9clone` test clone).
  All were upgraded.
* I killed a 9-hour-old Chrome instance that was holding the automation profile
  so this session could attach. The signed-in session survived (the profile is
  on disk).
