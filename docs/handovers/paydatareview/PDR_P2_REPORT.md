# PDR P2 — report (Yes / No and words wherever a flag is shown)

Spec: `PDR_P2.md`; rules and gotchas: `PDR_LEDGER.md` (G14–G21 added by this phase).
Implementer: Opus, 2026-11-05. Live on all four databases at 09:21 UTC; rize data step 09:21 UTC.

## 0. In plain words

* **Review pay data** now reads **Yes / No** for BPJS TK covered, BPJS health covered,
  Employer reimburses employee BPJS, Final tax period, Final-period YTD reviewed and
  Severance eligibility confirmed, and **None · Insurance tax · All tax** for Tax
  allowance mode. Picking a value in the side panel is a two-button **Yes | No**
  switch (or a short list for Tax allowance mode, with the one-line explanation
  under it). Typing **y / n / yes / no / 1 / 0** into a grid cell also works.
  The number behind it (1 / 0, 0 / 1 / 2) is what is saved and what the formulas use.
* The final-tax-month reminder now says "Set Final tax period to **Yes**" (no "(1)").
* The worksheet sends **8 times less data** (4.54 MB → 0.57 MB) and only draws the
  rows on screen (about 25 of 113). The grid is on screen in **10.6 s** (was 11.9–12.4 s
  after P1, 49 s before P1). The remaining time is the server reading everyone's
  employee and contract records (9–10 s), which this phase was told not to touch.
* **The pay data file** writes **Y / N** (and the Tax allowance words) with an Excel
  drop-down; on upload it reads Y, n, YES, no, 1, 0, " y ", the words in any case.
  Anything else is a plain line: "Name: Final tax period needs Y or N." A "Y" never
  turns into 0.
* **The full contract form** (Contract Components list) has an **Answer** column that
  shows and edits Yes / No and the Tax allowance words. Picking No keeps the line with 0.
* Records Desk, the pay run results grid, the pay data review grid and the run
  input review also read the words (§4).

## 1. Before / after (open "Review pay data", Rize Indonesia, preparation #19, 113 people)

| What | Before (live today) | After (live, 09:22 UTC) |
|---|---|---|
| Data sent to the browser | 4,532,556 bytes (10,848 cells, 96 columns) | **570,368 bytes** (same cells, light shape) |
| Server time (werkzeug line) | 9.2 s quiet (08:18) / 24.4 s while my test copies ran (08:58) | 9.8 s / 8.9 s / 9.0 s (2,428–2,518 queries, ~1 s SQL) |
| Round trip of the call in the browser | 28.8 s (busy box) | 10.0 s (light) / 11.5 s (old full shape, for comparison) |
| Grid on screen | 11.9–12.4 s (P1 report) | **10.6 s**, 27 rows / 2,592 cells drawn instead of 113 / 10,848 |
| Red cells / reminders / blank cells | 1 / 7 / 2,979 | 1 / 7 / 2,979 (unchanged — non-goal held) |

Target ≤ 8 s **not met** (§6 D1). The browser's own share went from ~2–3 s to ~0.6 s;
what is left is the server, and ~35 % of that is the legacy employee/contract reader
(`_get_formula_input_values` chain) that W1b says not to change. Its share is the same
as in P1 (the shell breakdown in `PDR_P1_REPORT.md` §1 still applies).

## 2. Tests

Full suites on a throwaway copy of p0clone with the new code (scratch addons), then
every failure re-run on the **old live code** on the same copy.

| Suite run | Result |
|---|---|
| pb_hr_payroll_formula, pb_payroll_templates, pb_payrun_wizard, pb_contracts, pb_records, pb_payrun_results, pb_formula_studio — 1,536 tests | 12 fail + 2 error |
| of which mine | 2: T2 (a save reference shorter than 8 characters in the test) and T3 (wrong assumption that Monthly bonus stays blank after the grid saves its default 0). Both fixed; re-run of the 136 P2-related tests: **0 fail** |
| the other 12 | TestRd49SyncCost 02ab, 02i; TestRecordsR1OneTime 07b; TestSchemeCtxCurrency 04 (copy's company currency is USD: "fixture is degenerate"); TestCd1Contract360 01 (FILLIN's `fillin` key not in the test's list); TestJourneyView 04a; TestNetPayCandidates 01; TestOneMappingHome ×4; TestRunsrcPcBoardLane 14 — **all 12 fail the same on the old live code: pre-existing** |

**No new failures.**

| Test | What | Result |
|---|---|---|
| T1 | worded column carries `labels` + `control` (+ `hint`); a saved 1 is the number 1 and its word is Yes; an unmatched 7 stays 7; a column without words has none (`test_p2_t1_*`, `test_p2_t1b_*` compact payload) | **Pass** |
| T2 | saving "1", "Yes", "y" all store the integer 1 in `edits_json`; previews identical (15 = 1×10+5); "maybe" refused with "Final tax period needs Y or N." | **Pass** |
| T3 | download writes Y / N and "All tax", list validation `"Y,N"` and `"None,Insurance tax,All tax"` on the right column, header note "Y or N…", a blank stays blank; change list reads "Yes → No" | **Pass** (unit) + real rize file on the copy: Monthly adjustments Final tax period / YTD reviewed / Severance: blank ×113 with Y,N lists; Employee records: BPJS TK Y ×111 (1 blank = the 1 real missing line), health Y ×113, Reimburses Y ×4 / blank ×109, Tax mode "Insurance tax" ×109 / "All tax" ×4 |
| T4 | upload: Y, n, YES, no, 1, 0, " y ", "1" → numbers; "All tax"/"all tax" → 2; "maybe" and "Y" for Tax mode → plain issue lines. Engine import (a file attached to a run): Y / yes / " y " / "1" give exactly the inputs and formula results of 1 (`slip_y == slip_1`, 125); "maybe" stops the row with the sentence; `validate_line` names it per row | **Pass** |
| T5 | a numeric column without words still refuses "Y" ("Workbook One · Monthly bonus: Enter a valid number."); engine import keeps a non-worded "Y" as before | **Pass** |
| T6 | download → upload unchanged: 0 changes (unit test); real rize files on the copy: records file **0 changes, 0 issues**; monthly file 0 changes in any worded column (226 pre-existing "changes" are Paid days / Period days suggestions the file pre-fills — G21) | **Pass** |
| T7 | contract line with words: Answer "Yes"; choosing "No" stores 0 and keeps the line; "y" → 1; "maybe" refused; unmatched 7 shows "7"; a component without words shows its number; form onchange moves the amount | **Pass** (unit) + browser on the copy: picked No on contract 3512 → line 33701 amount 0, same line id |
| T8 | open time + payload (§1); Next issue lands on BPJS TK covered (Arief Andani Hidayat), focused, filter "Needs attention"; "Final tax month" filter → 7 rows; scroll to the end draws the last rows (Zudi Rahman); paste "n⇥N / yes⇥1" saved 4 cells as 0,0,1,1; grid typing "n" saved 0; "maybe" → "BPJS TK covered needs Y or N." and nothing saved — on the throwaway copy | **Pass** (open-time target: see D1) |

Browser checks (Chrome; live = read-only on the owner's preparation #19, which is
still revision 1 with no edits; edits only on the throwaway copy):

| Check | Result | Shot (`p2_shots/`) |
|---|---|---|
| B1 worksheet shows Yes / No and Tax mode words | **Pass** live | `live_B1_yes_no_on_worksheet.jpg`, `live_B1_final_tax_month_reminder_no_1.jpg` |
| B2 side panel toggle + hint | **Pass** (copy) | `copy_B2_toggle_side_panel.jpg`, `copy_B2_tax_mode_select_hint.jpg` |
| B3 this month's file: Y / N present, drop-down | **Pass** — file built on the rize copy with the live code (a live download writes a receipt row; kept off live) | — (cell counts in T3) |
| B4 contract panel shows the words | **Pass** live (RPC read of contract 3512: Yes / Yes / No / "Insurance tax" + the hint line) | — |
| B5 full contract form Answer column | **Pass** live (read) + copy (edit + save) | `live_B5_contract_form_answer_column.jpg`, `copy_B5_contract_form_answers.jpg` |
| Console | 0 errors on live and on the copy | — |

## 3. What changed (by work item)

* **W1 worksheet** — `payroll_preparation.py`: `_column_words` (:435) puts
  `labels` / `control` / `hint` on every column; `save_cells` accepts words for a worded
  rule (paste); the reminder drops "(1)"; the usual-answer reason is translated at
  display. `payroll_review.js`: `word()` (:185) shows the word, `toNumber()` (:196)
  turns typed / pasted text into the number, `pick()` (:211) drives the toggle / list;
  `payroll_review.xml:41-44` toggle, list and hint.
* **W1b payload + rows** — `pr_compact` context (`payroll_preparation.py:392`,
  `_compact_cell` :447, `_history_data` :467): per-cell name / owner / rule / key /
  provenance / long reasons move to the column or are dropped; history and review are
  trimmed to what the screen reads. Python callers (tests, `_assert_scope`) keep the full
  shape. Windowed rows: `rowWindow` (:83), spacer rows (`payroll_review.xml:25`),
  `revealCell` (:93) for Next issue.
* **W1c** — vi_VN for the P1 sentences (usual answer, reminder, December / last month of
  work, filter option, "Working out previews") and every new string, in
  `pb_payrun_wizard/i18n/vi_VN.po` (JS + template) and `pb_hr_payroll_formula/i18n/vi_VN.po`
  (server). PO gate passed on the box.
* **W2 file** — one helper `value_from_words` (`contract_fill_in.py:109`) behind
  `rule.value_from_text` (:182) / `value_to_text` (:168). Called from: templates download
  (`templates.py:674`, lists `_word_lists` :739), records/legacy upload review
  (`templates.py`, `_from_words`), monthly grid `_input_value` (`input_review.py:155`),
  engine import `normalize_input_value` (`payroll_import_batch.py:4380`), the contract-sync
  normaliser (`:5234`), `validate_line` (`payroll_import_line.py:216`), Records Desk
  `_coerce`, worksheet `save_cells`.
* **W3 data (rize)** — §5. New field `value_labels_hint` on the rule
  (`contract_fill_in.py:158`); no existing rule field fitted (only `validation_message`,
  `value_kind_reason`, which screens use for other things).
* **W3b full contract form** — `HrContractAdvantageWords` (`contract_fill_in.py:353`):
  `pb_value_words` + `pb_amount_word` (inverse writes `amount`); rule found by
  `_pb_component_rules` (:232, same preference as the contract panel); widget
  `pb_value_word` (`static/src/js/value_word_field.js`); view
  `view_hr_contract_form_component_words` (`contract_advantage_typed_views.xml`).

## 4. W4 audit — every other screen that shows a flag value

| Screen | Where the value is drawn | Now | Note |
|---|---|---|---|
| Records Desk grid + change review | `pb_records/models/pb_records_desk.py:953` `_word_label` (from `_read_cell` :899 and `_coerce` :1020) | **Words** | Typing "Yes" is accepted server-side. A cell edited in the grid shows the number until saved (`records_cells.js:78` `labelFor`) — small follow-up |
| Pay run input review ("On record" / values) | `pb_payroll_templates/models/run_input_review.py:103`, `static/src/run_input_review.xml:48-49` | **Words** | mapped cells get words through Records Desk |
| Monthly pay data review grid, Prior, inspector, change list | `pb_payroll_templates/static/src/monthly_review.js:13` `wordFor`, :73-74; `models/input_review.py:232` | **Words**, and the grid cell reads/accepts words | — |
| Pay run results grid | `pb_payrun_results/models/payrun_results.py:80`, `static/src/js/payrun_results.js` `fmt` | **Words**, no total for a worded column | all 7 rize flags are report-visible, so this was printing "Rp1" |
| Contract panel | `pb_contracts/models/pb_contract_360.py:849` `_cd_value_hint`; `static/src/xml/contract_360.xml:161` | Words (FILLIN) **+ hint line** while editing | — |
| Payslip PDF (themed) | `pb_hr_payroll_formula/report/payslip_themed.xml:109-110` | **Still numbers** | only if a worded rule is on the payslip (none of the 7 is); the value would also be added into the section subtotal — needs a text line, not a relabel |
| Employee portal payslip | `pb_me_portal/views/portal_templates.xml:609`, `controllers/portal.py:601-604` | **Still numbers** | same condition as the PDF |
| Source journey (Atlas) | `pb_source_atlas/static/src/xml/atlas.xml:319-321` via `atlas.js:382` `kindly`; raw value set at `models/pb_source_atlas.py:933` | **Still numbers** | small display fix; left to keep this deploy to the touched modules |
| Pay package from the contract | `pb_comp_ben/models/employee_comp.py:201` (`_lines_from_contract`) | **Still numbers** — flags become "earning" lines of 1 / 2 | a meaning bug, not a label: worded rules should be skipped there |
| Contract change history list / form | `pb_hr_payroll_formula/views/contract_component_change_views.xml:13-14, 42-43` (`old_amount` / `new_amount`) | **Still numbers** | needs a computed word like W3b's |
| Formula Studio live preview | `pb_formula_studio/static/src/js/formula_studio.js:1001, 1727` | Numbers (by design: formula authors see the number) | — |
| Employee side panel, pay run checks, payslip form | — | not affected (no component values shown) | — |

## 5. rize data step (W3)

On rize only, one transaction, after the code deploy; rehearsed first on the copy
(red cells stayed 1, reminders 7, blank cells 2,979 with the words on).

* `IDFINALTAXPERI`, `IDYTDREVIEW`, `IDSEVELIG` → `0=No;1=Yes` (schemes 7121, 7116, 7096).
* `IDTAXALLOWMODE` → `0=None;1=Insurance tax;2=All tax` and the hint "All tax = the
  company pays all the employee's tax (net salary). Insurance tax = only the tax on the
  insurance premium." (same three schemes).
* 12 rules, `write_date` moved. Backup table `rize.pb_bak_pdr_words_20261105` (12 rows).
* The FILLIN seed tool (`tools/seed_fillin_rize_indonesia.py`) now carries the short words,
  so re-running it does not put the long ones back.

**Undo** (run as `sudo -u postgres psql -d rize`):

```sql
UPDATE hr_formula_rule r
   SET value_labels = b.value_labels,
       value_labels_hint = b.value_labels_hint,
       write_date = now() at time zone 'utc'
  FROM pb_bak_pdr_words_20261105 b
 WHERE r.id = b.id;
```

## 6. Deviations

1. **D1 open time** — grid on screen 10.6 s, target ≤ 8 s. Payload and drawing are done
   (4.54 → 0.57 MB, 10,848 → ~2,600 cells drawn); the server itself takes 9–10 s and its
   largest part is the legacy record reader the handover kept out of scope. The next step
   is Fable's call: memoise the scheme-level parts of that reader inside the request memo.
2. **Payload shape is opt-in** (`pr_compact` context) rather than replacing the
   `workspace()` shape: tests and Python callers keep the full cells, the worksheet asks
   for the light one on every call.
3. **W3 on 7116 / 7096 has a side effect on those two non-live schemes**: their
   Tax allowance mode has usual answer 0, so with words that name 0, P1's "no contract
   line = usual answer" rule now reads a missing line there as "None" instead of red.
   On the live scheme 7121 nothing changes (usual answer 1). Undo above restores it.
4. **Extra fixes found in the browser**: a selected cell kept showing its old text after
   a paste changed it (now refreshed from the server); the Answer column on the contract
   form is 140 px wide so "Insurance tax" is not cut.
5. **Extra surfaces fixed** beyond the handover's list because they printed the flags on
   rize: pay run results (all 7 flags are report-visible) and the run input review.
6. **B3** checked on the copy (a live download writes a receipt row).
7. **Found, not fixed (owner data)**: all 103 rize Indonesia contracts in preparation #19
   have no **HR Responsible**, so the full contract form refuses to save any change there
   ("Complete the required fields: HR Responsible"). The new Answer column works once that
   field is filled (proved on the copy).

### Self-review against the non-goals

| Non-goal | Held? |
|---|---|
| No formula text, `value_kind` change, nothing stored as text | Yes — words are converted to the number at every entry; `edits_json` stores ints (T2); contract `amount` stays a number (T7) |
| No change to which cells are issues / optional / reminders | Yes — 1 / 7 / 2,979 before and after on prep #19 (copy and live) |
| No Formula Studio redesign | Yes — only a new rule field; the Studio was not touched |
| No words added to Vietnam / India / Singapore rules | Yes — only rize Indonesia rules got data; other schemes have no `value_labels` (checked all four databases) |
| `outputs/` untouched | Yes |
| "Odoo" never on screen; plain English; Lucide-only | Yes — new strings scanned; no new icons |
| 1 / 0 stays stored and in the formulas; a "Y" never becomes 0 | Yes — T4 / T5 / T7 |

## 7. Commits, versions, deploy

| Commit | What |
|---|---|
| `b1e6d1e3a` | engine: one word helper, import, contract form Answer column, PO, tests (`test_pdr_p2_words.py`) |
| `2e1dd3939` | worksheet: words, toggle / list / hint, light payload, drawn rows, PO, tests |
| `dd1d3745b` | pay data file: Y / N, lists, upload, review grid words, tests |
| `c77ba86aa` | Records Desk, pay run results, contract panel hint |
| (this commit) | report, ledger G14–G21, shots |

Versions live ×4 (payobook, payobook_template, p0clone, rize): `pb_hr_payroll_formula`
19.0.1.165.0, `pb_payrun_wizard` 19.0.1.43.0, `pb_payroll_templates` 19.0.1.7.0,
`pb_contracts` 19.0.1.12.2, `pb_records` 19.0.1.8.2, `pb_payrun_results` 19.0.1.5.3.
Deployed 09:14:50–09:21:00 UTC from `git archive c77ba86aa`, `filter_deploy.sh full`:
EXIT=0 ×4 (errors=3 ×4 = the known payroll_analytics schema notes), crons 33/29/76/44
unchanged, tree hash = stage ×6, latest_version ×4, assets purged + `web.assets.version`
bumped ×4, sites 200. Live-vs-stage diff before the deploy was exactly the 32 P2 files.
Backups `/odoo/backups/pdr-p2-run-20261105091450`. Code undo = redeploy `68794bc64`'s
trees of the six modules (the new rule / contract-line fields are harmless if left).
Throwaway copies `pdr2_p0`, `pdr2_rz` dropped with their file stores.
