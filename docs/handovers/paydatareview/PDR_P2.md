# PDR P2 — Yes / No and words wherever a user sees a flag

Read `PDR_LEDGER.md` (rules §0, plumbing §1, gotchas §2) and
`PDR_P1_REPORT.md` first. Binding; do not re-derive.

## 1. Goal (plain words)

Owner ruling R2 / R3: the yes/no columns read **Yes / No** on every screen and
**Y / N** in the pay data file (the file also accepts Yes, No, 1, 0, any
case). Tax allowance mode reads **None · Insurance tax · All tax** with a
one-line hint. **1 / 0 (and 0 / 1 / 2) stay stored and in the formulas.**

Columns (rize schemes 7121, 7116, 7096): BPJS TK covered `IDBPJSTKCOVERE`,
BPJS health covered `IDBPJSHEALCOVE`, Employer reimburses employee BPJS
`IDERREIMBUBPJS`, Final tax period `IDFINALTAXPERI`, Final-period YTD reviewed
`IDYTDREVIEW`, Severance eligibility confirmed `IDSEVELIG`; plus Tax allowance
mode `IDTAXALLOWMODE`.

The mechanism already exists from FILLIN: `hr.formula.rule.value_labels`
("0=No;1=Yes"), `parse_value_labels` (`contract_fill_in.py:58`),
`value_label_options()` / `value_label_for()` / `value_label_control()` (toggle
for a {0,1} pair, select otherwise), and the contract panel's renderer
`pb_contracts/models/pb_contract_360.py:807` `_cd_value_view` (the reference
look: Yes first, words from the rule only). P2 makes the worksheet and the
pay data file use it, generically: **any** rule with words gets this, in any
country.

## 2. Non-goals (binding)

* No formula text changes; no `value_kind` change; nothing stored as text.
* No change to which cells are issues / optional / reminders (P1 owns that).
* No Formula Studio redesign (the studio already edits `value_labels`).
* Vietnam / India / Singapore schemes get the behaviour only through rules
  that already have words; do not add words to their rules.
* Do not change the client deliverables in `outputs/`.

## 3. Design (binding)

**W1 — worksheet** (`pb_payrun_wizard` JS/XML + `payroll_preparation.workspace`):
* Each column carries `labels` (the parsed options) and `control`
  (`toggle` / `select` / `''`) from the rule.
* A cell whose value has a word shows the word ("Yes", "No", "All tax"); an
  unmatched number shows the number (never hide a value). Blank stays blank.
* The side panel's "Value for this run" becomes a two-button Yes / No toggle
  (toggle) or a select (select), Yes first as on the contract panel; saving
  still sends the number. Typing into a toggle cell in the grid accepts
  y / n / yes / no / 1 / 0 and saves the number.
* The side panel shows the rule's hint line under the control when there is
  one (W3).
* The P1 reminder text says "Set Final tax period to Yes (1)" — drop the
  "(1)" now that the cell reads Yes / No.

**W1b — finish the open-time target (P1 missed it: ~10 s server, ~12 s to the
grid on screen, 4.6 MB payload, ~11,000 cells).** Target: grid on screen
≤ 8 s for prep #19 (113 people).
* Trim the per-cell payload: send only what the grid draws per cell; move
  per-cell detail (reason text, source owner, evidence-free fields that are the
  same for a whole column) to the column, or fetch it when a cell is selected
  (the side panel already makes a call, `payroll_review.js:70`). Measure the
  payload before / after.
* Draw rows as they come into view (windowed rendering of the grid body;
  keep keyboard navigation, "Next issue", filters and paste working).
* Do NOT touch the older employee / contract value reader
  (`_get_formula_input_values` chain) in this phase — Fable's call: the
  remaining gain there is not worth the risk now. Report its share again.

**W1c — translations.** Add `vi_VN` msgstr for the P1 sentences too (usual
answer reason, reminder line, filter option, "Working out previews").

**W2 — pay data file** (`pb_payroll_templates`, and the engine import):
* Download (`templates.py:536 download`): for a rule with Yes/No words, write
  **"Y" / "N"**; for other worded rules write the word ("All tax"). Add an
  Excel list validation on those columns (Y,N or the words) and a header note
  "Y or N" / the word list. A blank stays blank.
* Upload review (`templates.py:709 _numeric`, `:821`;
  `input_review.py:143 _input_value`): accept, for a worded rule only:
  Y / N / Yes / No (any case, trimmed), any label word (any case), or the
  number. Anything else → the existing issue line with a plain message:
  "%s: %s needs Y or N." (Yes/No rules) / "%s: %s needs one of: None,
  Insurance tax, All tax." Put the conversion in ONE helper on the rule
  (`value_from_text(raw) -> float`, raising ValueError with that message) and
  call it from every parse point; pass the rule (or its labels) down.
* Engine import (a spreadsheet attached to a run): find the single place in
  `pb_hr_payroll_formula/models/payroll_import_batch.py` where a rule-bound
  raw cell becomes a number (there are ~5 `float(cleaned)` copies — trace which
  one a run's attached file goes through, `templates.py:1204
  _get_value_for_rule` is the template entry) and convert words there with the
  same helper. **A "Y" must never silently become 0.** Test it (T4).

**W3 — rize words** (data, rize only; backup table + undo like P1 §5):
* `IDFINALTAXPERI`, `IDYTDREVIEW`, `IDSEVELIG` → `value_labels = '0=No;1=Yes'`.
* `IDTAXALLOWMODE` → `'0=None;1=Insurance tax;2=All tax'` (R3).
* Hint for `IDTAXALLOWMODE`: "All tax = the company pays all the employee's
  tax (net salary). Insurance tax = only the tax on the insurance premium."
  Store it in the rule's existing description/help field if there is one that
  screens may show (check `hr.formula.rule` fields); if none fits, add
  `value_labels_hint` (Char) next to `value_labels`. Show it in the worksheet
  side panel and the contract panel option list.
* Same three schemes; `write_date` moves.

**W3b — full contract form (owner asked 2026-11-05, MUST fix).** The full
contract form's "Contract Components" list (`om_hr_payroll/views/
hr_contract_views.xml:89-99`, `advantages_ids` list editable, `amount` column;
extended by `pb_hr_payroll_formula/views/contract_advantage_typed_views.xml`
view `hr.contract.form.typed.components`, live id 2829 on rize) shows and asks
for the raw number, so a user editing BPJS TK covered there types 1 / 0. Make a
line whose component has words show and edit them (Yes / No, or the select of
words) while `amount` still stores the number — e.g. a computed
`amount_choice` Selection-like char field on `hr.contract.advantage` with an
inverse writing `amount`, shown instead of `amount` when the rule has words,
or a small list widget. The words come from the paying scheme's rule with
that component code (the same rule lookup the contract panel uses in
`pb_contract_360.py`); no rule / no words → the number column as today.
Picking "No" keeps today's semantics (a line with 0 — do not delete the line).
Test it (T7) and screenshot it (B5).

**W4 — surface audit.** Find every other screen that shows a contract
component / input value to a user and would print 1 / 0 for these rules:
Records Desk (`pb_records`), employee side panel pay / contract tabs, the pay
run screen exceptions list, payslip input lines, the pay data review
(`input_review.py`). Fix each with `value_label_for()` when it is a small,
display-only change; list the rest in the report with file:line.

## 4. Tests

* **T1** worksheet payload: a worded column carries `labels` + `control`; a
  value 1 cell displays "Yes"; an unmatched value 7 displays "7".
* **T2** save from the toggle sends 1 / 0 and stores the number in
  `edits_json`; formula preview equal to the numeric save.
* **T3** file download: Yes/No rule writes Y / N; Tax mode writes the word;
  list validation present; a blank stays blank.
* **T4** upload review + engine import: Y, n, YES, no, 1, 0, " y " → numbers;
  "All tax" / "all tax" → 2; "maybe" → the plain issue line; an attached file
  carrying "Y" computes the same payslip as one carrying 1 (E-style exactness
  on a throwaway copy).
* **T5** rules without words are untouched: a numeric column still rejects
  "Y" with the existing message.
* **T6** reimport of a downloaded file round-trips with zero changes.
* **T8** open time: grid on screen ≤ 8 s in the browser for prep #19
  (read-only), payload size before / after; Next issue, filters, keyboard and
  paste still work with windowed rows (on a throwaway copy for paste/save).
* **T7** full contract form: a worded component line shows "Yes"; choosing
  "No" stores amount 0; a component with no words still shows the number.
* Suites of `pb_payroll_templates`, `pb_payrun_wizard`,
  `pb_hr_payroll_formula`, `pb_contracts`, `pb_formula_studio` green (mark
  pre-existing failures).
* **B1–B4** (Chrome MCP, rize, read-only on the owner's prep #19): worksheet
  shows Yes / No and Tax mode words; side panel toggle + hint; download this
  month's file and open it (Y / N present, dropdown); contract panel shows the
  new words for the three new columns. Screenshots to `p2_shots/`.

## 5. Deploy, report

Normal-risk deploy ritual (CLAUDE.md, ledger §0.4); modules as touched
(expect `pb_payrun_wizard`, `pb_payroll_templates`, `pb_hr_payroll_formula`,
maybe `pb_contracts`, `pb_records`); bump each version; `-u` where views /
data / fields change; all four DBs; W3 data on rize after.
Lessons: grep `pb_learn` for replicas of the worksheet or the contract flags
and update them in the same work (standing rule).
Translations: add `vi_VN` entries in `pb_payrun_wizard/i18n/vi_VN.po` for new
strings (msgstr must not say "Odoo"; follow the PO loading rules).

Report `PDR_P2_REPORT.md`: tests, screenshots, W4 audit table, deviations,
gotchas (append to ledger), commits, versions, undo statements.
