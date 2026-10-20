# LEARNREV P5b — writing guide for the lesson / walkthrough rewrite (S1, S2)

For the Opus writers the P5b implementer launches, one per product area. Scope and rules come from
`P5_HANDOVER.md` §0–§3 and `P5_SPLIT.md` (P5b); this page is the working detail. Read it whole.

## 0. Binding rules (verbatim from the program)
- Design bar: **"Extreme WOW, intuitive, out-of-this-world experience, best in class."** Hero: open ANY screen, press
  Understand, and every step reads **Look at · It means · It affects · Press** beside the real control, in English or
  Vietnamese, with **no sentence that names a label the screen does not show**.
- White-label: the word **"Odoo" never appears** in anything a user reads (any language). Technical names in comments
  are fine.
- Plain screen words only ("pay run", "pay scheme", "the connected system"), never code vocabulary (`net_role`,
  `value_kind`, "rung", "provenance", model names, field names).
- No emoji anywhere.

## 1. What you deliver
For each lesson / walkthrough you own: ONE block file in your output folder, named `<key>.js` (e.g. `L10.js`,
`sc_matrix.js`), holding the whole entry rewritten. Get the starting text with
`python3 docs/handovers/learnrev/tools/p5b_blocks.py extract docs/tutorial_poc/author/data.js <key> > <out>/<key>.js`
and edit that file. A lesson block starts with the line `  L10: {` and ends with `  },`; a walkthrough block starts with
`  {`, then `    key: "sc_x",`, and ends with `  },` (exactly the `extract` output shape).

**Never edit anything in the repository** (not data.js, not templates, not .po). Read only. Write only in your output
folder. Validate with:
`python3 docs/handovers/learnrev/tools/p5b_blocks.py validate <out>/*.js` — it splices your blocks into a private
mirror and runs every generator gate (language/jargon, 28-word limit, step shape, `press` anchors, field steps,
bilingual parity, retired labels via the replica/anchor checks). Finish only when it prints `GATES PASSED` with no
"not four-line" step. Run it on your own files only.

## 2. The step shape
Exemplars to read first (already rewritten in P4, in data.js): lesson **L9** (Component treatment), **LA**
(approvals), **L2** (payruns); walkthroughs **sc_treatment**, **sc_payrun**, **sc_records**.

A lesson step:
```js
{
  screen: "matrix", anchor: "am-table",
  /* source: pb_approval_config/static/src/xml/matrix_room.xml:212 */
  kicker: B("Read a route", "Đọc một lộ trình"),
  title: B("…", "…"),
  look: B("What to look at, named exactly as the screen shows it.", "…"),
  means: B("What it means.", "…"),
  affects: B("What it changes or feeds — who or what downstream.", "…"),
  press: B("What to press (optional, only a real control, only when the reader really presses).", "…"),
  tip: B("…", "…"),            // optional, keep good existing ones
  consequence: B("…", "…"),    // keep where the old step had one
},
```
- **Remove `body`** from every step you rewrite. A step with `look` must carry `means` AND `affects`.
- **One idea a step.** Keep the steps 1:1 with the old ones (same order, `screen`, `anchor`, `moment`, `requires`,
  `tip_requires`, `variants`): rewrite the words, not the structure. Split a step only when its old body really
  teaches two unrelated ideas — then both halves keep the same screen/anchor; say so in your notes.
- Keep `kicker`, the lesson `title`, `goal`, `mins`, `quiz` (reword a quiz only when it names a label the screen no
  longer shows; the correct option's feedback opens "Yes." / "Đúng vậy." and wrong ones "Let's rethink that." /
  "Hãy nghĩ lại một chút." as today).
- **Sentences ≤ 28 English words (hard gate); aim for ≤ 16.** Short, concrete, present tense. Each line is one or two
  sentences. No `<b>` tags in the four lines (they are escaped as text); quote labels by writing them plainly with a
  capital, the way L9 does ("The Included in another total column.").
- **No ASCII double quote inside a string** (LR40: the authoring tool can mangle `\"`). If you must quote, use “ ” or
  rephrase.
- `look` begins with the thing to look at ("The Status column.", "The Needs people chip above the table."). `press`
  begins with the control ("Publish this route, once Try an example names a real person."). `means` says what it is in
  plain words. `affects` says the consequence downstream (pay run, payslip, bank file, who gets asked, what the next
  screen shows), never "it affects things".
- **`press` only on a product anchor** — never on a `rep-*` (practice-copy) anchor and never on a retired one
  (`pb_learn/static/src/anchors.json`, blocks `product` / `pattern`; `retired: true` entries are out). On a `rep-*`
  step, fold the action into `look` / `means` ("Opening a row walks these five steps.") and give no `press`.

### Field steps (the 16 manifest screens)
When a step is about a column / field of one of these screens, add `field: "<screen>.<key>"` (lesson: on the step;
walkthrough: inside `say`), author only `look` (and `press` if real), and **do not author `means` / `affects`** — the
generator writes them from the field's own help and readers (truth by construction; the validator refuses an authored
one). Field keys (column as shown):
- approvals: state "Waiting for a decision", sent_in_by "sent in by", due "Due", facts "The facts, as they were when it was sent in", waiting_for "Waiting for", route "The route"
- dashboard: net_pay, people_paid, average_net, total_cost, month_chart, needs_you, pay_schemes
- employees: not_ready "Not payroll-ready", ready_share "Payroll-ready", headcount "Headcount", running "Running contracts", expiring "Expiring within 30 days", wage "Monthly wage", contract_button "Contract"
- formula: component, source, formula, depends, value_kind, preview, on_payslip
- govreports: filings "Government Reports", country "Country", company_line "Statutory filings for"
- import: total_lines "Lines", matched "Matched", errors "Errors", status "Status"
- mapping: sources, source_order, sample, storage, value_kind, pay_role
- matrix: route "Process and the route it follows", applies "Applies to", status "Status", needs_people "Needs people", version "Version"
- payreview: budget "Budget", fairness "Fairness", blockers "What stops approval", scores "Scores"
- payruns: stage, net, gross, people, balance, unsourced, waiting_on_you
- payslips: need_review, status, net_total, gross_total, breakdown
- records: person "Person", review "Review your changes", history "History", undo "Undo", export "Export with data", import "Import a file"
- runpayroll: scheme, batch_name, date_from, date_to, pay_data_mode, coverage, need_review
- statutory: rates, employee, employer, ceiling, brackets, rate, contributions
- treatment: lane, report_group, pay_role, rollup, run_signal, value_kind
- wftime: timeline "Timeline", week_grid "Week Grid", exceptions "Exceptions", import "Import"
The full field data (help, used_by, VI column) is in `<scratchpad>/p5b/manifests.json` (path given in your prompt) —
read it so your `look` uses the column's exact words in both languages.

### Screens without a manifest: the `source:` comment
For every step on a screen that has no manifest, put ONE comment line in the step:
`/* source: <module>/static/src/xml/<file>.xml:<line> */` citing the template line that holds the label your `look`
(or `press`) names (or the `_t("…")` line in the screen's JS). Find the template from the anchor:
`anchors.json` → `product[<anchor>].file`, then `grep -n 'data-coach="<anchor>"'` in it. For a `rep-*` anchor cite the
replica line in `pb_learn/static/src/engine/screens.js` AND, when the real screen has the same label, its template line.
The next manifest wave replaces these steps' hand-written lines; the comment is how it finds them.

## 3. Truth — the rule that matters most
**Every label you name must be on that screen.** Before writing a `look` / `press`, open the template (and, for the
Vietnamese, the module's `i18n/vi_VN.po`) and check the exact words:
- English: the template text or `_t("…")` literal, case as shown (whitespace aside).
- Vietnamese: the `msgstr` for that msgid in the module's `i18n/vi_VN.po` (the screen the Vietnamese reader sees). The
  Vietnamese `look` / `press` names the Vietnamese label, never the English one (P4 rule: `press` in the reader's
  language). If the .po has no Vietnamese for that label, write the label in English in the VI line as the screen
  shows it, and list it in your notes as a VI gap (do not edit the .po).
- The OLD body may name things that are no longer on screen (screens moved since it was written). Do not carry them.
  If the old step's whole point is gone from the screen, rewrite it around what is there now and say so in notes.
- Numbers and names from the practice company (Loan Installment, June, Mai Linh, …) are fine when the old text used
  them; do not invent new figures.
- Never promise something the screen does not do. When unsure, say less.

## 4. Vietnamese
Natural, plain Vietnamese a payroll officer in Hồ Chí Minh City would write; correct diacritics; no mixed-language
sentence (except proper names, Payobook, PayAI, demo people/components, file kinds like Excel). One concept, one word:
- pay run **đợt lương** · payslip **phiếu lương** · pay scheme **chương trình lương** · net pay **lương thực nhận /
  thực nhận** · gross **tổng thu nhập** · deduction **khấu trừ** · component **thành phần** · approval route **lộ trình
  phê duyệt** · Approvals inbox **hộp Phê duyệt** · draft **nháp** · recompute **tính lại** · bank file **tệp chi
  lương** · pay data **dữ liệu lương** · employee **nhân viên** · contract **hợp đồng** · overtime **tăng ca** ·
  attendance **chấm công** · leave **nghỉ phép** · probation **thử việc** · hiring request **đề xuất tuyển dụng** ·
  candidate **ứng viên** · pay band **khoảng lương** · pay review **xét lương** · headcount **sĩ số** · filing **báo
  cáo bắt buộc** · press **bấm** · screen **màn hình** · tab **tab** · column **cột** · row **dòng** · chip **nhãn**.
- The glossary in data.js (`const GLOSSARY`) and the screen's own `.po` win over this list where they differ; the
  screen's label wins for any label you quote.
- Same English sentence → same Vietnamese sentence everywhere in your blocks.

## 5. Walkthroughs (`SCENARIOS`)
Rewrite only the `say` of each step (and the scenario `tagline` if it names a label not on screen). Never change a
step's `key`, `anchor`, `nav`, `screen`, `act`, `guard`, `value`, `modes`, nor the scenario's `key`, `match`, `entry`,
`modes`, `screens`. `press` only on steps where the person really presses (`act: "click"` / `"input"`, or a Try step
that asks them to act on a product anchor); an observe step in a Watch-only walkthrough gets no `press`. Keep the
"I only read" style tips where they exist.

## 6. Your notes (return them as your final message, short)
1. Files written (one per key) and the validator's last line.
2. Per key: steps before → after, field steps used, steps split (why), steps whose old point is gone from the screen.
3. VI gaps: labels on screen with no Vietnamese in the module .po (module, msgid).
4. Candidate Try checks: walkthrough steps where the person acts on the real screen and a read-only check of their
   own record would be cheap (scenario.step → what to check, which model).
5. Anything you could not verify.
