# BLUEPRINT Phase B6 — Finish, Vietnamese, the Excel round trip, polish, closeout

Read `docs/handovers/BLUEPRINT_LEDGER.md` FULLY (every ruling; every gotcha B1–B5 appended —
GR5 on `.po` files is a database-killer), all five phase reports, `BLUEPRINT_PLAN.md`
§"Step 6 · Finish" and §"Verification", and the owner decisions block in the ledger.

## 1. Goal (plain English)

The journey ends properly and reads properly in Vietnamese. **Finish** shows what was built,
what still needs a decision, which optional tasks were done or skipped, and one button that
finishes the setup and opens the configuration. The Excel-workbook starting point is walked all
the way through on a real small workbook. Every screen of the journey is available in
Vietnamese. The "one more hour" items from the earlier reports are done. The programme closes
with a closeout document the owner can read.

## 2. Scope — in
- Finish step (real): tiles, identity card (incl. calendar/payment choices), **Decisions still
  open** (review items from B2/B3/B4 statuses), optional-task statuses, evidence line, the
  finish gate (server), Finish & open, Discard this draft.
- Excel starting point end to end: a small fixture workbook with an employee-id column that the
  legacy review accepts; the round trip proven in Chrome; return lands on Pay rules with the
  imported components listed and code-form formulas shown; imported rules are `manual` (no
  recipe) and the Components tab says so honestly.
- `i18n/vi_VN.po` for `pb_blueprint` (every `_t()` and QWeb string), generated with the repo's
  tooling, validated per GR5, loaded on all four DBs; the picker's "Resume setup" strings in
  `pb_formula_studio`'s `.po` too.
- Polish pass: the "one more hour" items from B1–B5 reports (header on 390 px in one row; rail
  ticks animate in sequence; thin panels gone; `prefers-reduced-motion` everywhere; focus rings;
  aria on every control; count-up reuse), ⌘K/palette entry "New configuration" in `pb_hub`'s
  palette registry if the pattern is a one-liner (`hub_palette_entries.js`), a Settings hub card
  "Resume setup" for drafts if `pb_settings` exposes a registry (else skip and say so).
- Closeout: `docs/handovers/BLUEPRINT_CLOSEOUT.md`.

## 3. Scope — binding non-goals
- No new features beyond the plan. No approval matrix. No re-skin of the legacy import review
  (that is its own later phase; this phase only proves the round trip with a fixture).
- No push. No deletion of the owner's demo configurations.

## 4. Design (bar: "extreme WOW, intuitive, out-of-this-world experience, best in class")

### 4.1 Finish step
Eyebrow "06 / A CONFIGURATION YOU CAN EXPLAIN", H1 **"Ready to review. Built to evolve."**,
lead "Finish the setup to open the configuration. Activating it for real pay runs stays a
separate, checked step."
Three tiles (count-up): Pay components · Formula rules · Inputs. Identity card: name, code,
company, country, pay cycle, effective from, starter + version, situations chips, calendar
(cut-off / payday rule / late-input policy), payment (currency / bank identifier type),
rule pack + version + "aligned / N values differ".
**Decisions still need an owner** card: one row per review item (from `bp_components` review
reasons, B3's owner questions surfaced as items on the relevant components, B4 `needs_review`
tasks, B5 pending confirmations), each with a plain title, one sentence, and a **Go** link to
the step/tab/component that resolves it. Count chip "N open". Text: "You can finish with open
decisions. Formulas that do not work or checks that failed must be fixed first."
**Checks** line: "12 of 12 checks passed · run 5 min ago" or the amber/rose state with "Run the
checks" link (B5 evidence).
**Optional setup** card: Source mapping / Payslip layout / Approvals with their status pills and
"Change" links back to Connect.
Primary **Finish & open** (disabled with an inline reason when the gate fails: "2 formulas do not
work — fix them on Pay rules" / "The checks have not been run since the last change" / "No
scenario has confirmed expected numbers yet"); secondary "Save & close"; overflow: "Discard this
draft" (confirmation names the configuration and the count of components; refused when payslips
exist). On success: toast "Setup complete. Opening the configuration." and Formula Studio opens
on it; the picker card shows the normal ring; reopening the journey on a finished configuration
lands on Finish in read mode with "Open the configuration" and a link "Revisit the setup"
(which reopens the steps read-write while the configuration is still draft; read-only otherwise).

### 4.2 Finish gate (server, `bp_finish`, extending B1's)
Refuse with a plain reason when: any rule failed to convert (`python_formula` empty — B1's
check); `has_errors` after the BP-R12 fix; evidence stale; `tests_failed > 0`; no confirmed
scenario; final outputs not asserted (B5 coverage). Open decisions do NOT block. Idempotent.

### 4.3 Vietnamese
Generate `pb_blueprint/i18n/vi_VN.po` with `tools/refresh_pb_vi.py` (read its header for the
exact invocation; it separates extraction from translation and fills gaps from the glossary);
review every msgstr for screen vocabulary ("cấu hình lương" for configuration, "kỳ lương" for
pay cycle, "lương thực nhận" for take-home pay — reuse the glossary's existing choices, never
invent when the glossary has one); no "Odoo" in any msgstr; every entry carries
`#. module: pb_blueprint` (GR5) — validate with the polib one-liner from GR5 before deploying.
Add the new `pb_formula_studio` strings ("Resume setup", "Still being set up — step %s of 6")
to its `vi_VN.po` the same way. Load with `-u` (or `--i18n-overwrite` if the ledger's tooling
says so) on all four DBs; verify by switching the validator user to Vietnamese and walking all
six steps + both dialogs; screenshot each in VI.

### 4.4 Excel round trip
Build `pb_blueprint/tests/fixtures/small_payroll.xlsx` with openpyxl (one sheet, header row:
Employee ID, Name, Basic, Allowance, Days, Gross with an Excel formula `=C2+D2`, Net `=F2-…`;
three data rows). Prove in Chrome: Start → Import Excel workbook → the legacy review with the
draft pre-scoped → select the sheet, key column "Employee ID", accept the proposed components →
finish → the journey opens at Pay rules with the imported components listed as "Written as
Excel" with their code-form formulas; hero shows a number once a sample is added (the import may
not create one — B1's `_ensure_sample` runs on load if absent: verify). Add a Python test that
drives the wizard models directly with the fixture and asserts the return action and the rule
count.

### 4.5 Polish list (do all; report each)
B1: header one row at 390 px; rail ticks animate in sequence; thin-step previews (now moot —
verify no thin panel remains). B2–B5: whatever their reports listed under "with one more hour".
Global: `prefers-reduced-motion` honoured for every animation; visible focus rings on every
interactive element; `aria-live="polite"` on the hero number and the evidence chip; Escape
ladder consistent; tab order audited on each step; toasts never the only place a failure is
explained.

## 5. Tests
1. Finish gate: each refusal reason reproduced; success path; idempotent; finished configuration
   reopens in read mode; `bp_discard` refused with payslips.
2. Review-items aggregation includes at least one item from each source (B2 review, B3 owner
   question, B4 needs_review, B5 pending) on a prepared draft.
3. Excel fixture import returns the journey action and creates N rules, all `manual`.
4. `.po` validity (GR5 regex over every entry), no "Odoo" in msgstr, every `_t()` literal in
   `pb_blueprint` JS/XML/py has an entry (write a small source-scan test that extracts literals
   and checks the catalogue — tolerate `%s` placeholders).
5. The white-label + vocabulary gates extended to the `.po`.

## 6. Deploy + acceptance (bump `pb_blueprint` 19.0.1.5.0, `pb_formula_studio` +1)
1. Finish on a Complete draft that ran and confirmed its checks: tiles, identity incl. calendar,
   decisions list with Go links that land correctly, optional statuses, Finish & open works.
2. Finish blocked: stale evidence → reason + link; failed check → reason; no confirmed scenario →
   reason; fix each → enabled.
3. Discard this draft → confirmation → gone from the picker; refused on a draft with a payslip
   (simulate by linking one via shell on p9clone).
4. Finished configuration → journey opens in read mode; "Revisit the setup" reopens editing.
5. Excel round trip end to end (§4.4) on payobook; cancel path still returns.
6. Vietnamese: all six steps, both dialogs, the picker card, the Finish decisions — no English
   leaks (list any string that could not be translated and why); numbers keep `en-US` grouping
   unless the glossary says otherwise (state the choice).
7. Polish: 390 px header single row; rail tick animation; reduced-motion respected (emulate);
   keyboard-only walk of the whole journey; ⌘K entry opens the journey (if implemented).
8. All four DBs; gates green; final `git log` of the programme listed in the closeout.

## 7. Closeout (`docs/handovers/BLUEPRINT_CLOSEOUT.md`) — written for the owner, plain English
What was built (one paragraph per step), how to use it (from the picker), what changed for
existing screens (Resume setup cards, the BRACKET "2 errors" fix), the numbers (commits, tests,
modules + versions per DB), owner decisions still open (5-band vs 7-band tax schedule for July
2026; union dues 0.5% vs 1%; overtime exemption scope; the temporary validator user
`look.p4@payobook.com` to archive; the two demo configurations to keep or remove; push), and
suggested next programmes (re-skin the Excel review; approval matrix; employer-paid tax
gross-up; guaranteed-net recipe). Then the engineering appendix: ledger pointer, gotcha
range, file map.

## 7b. Addendum after the B5 report (binding)
- **Baseline live on all four DBs**: `pb_blueprint 19.0.1.4.0`, `pb_hr_payroll_formula 19.0.1.125.0`
  (B5 fixed the formula-manager delete right on `hr.formula.test.result` — a security file; name it
  in the closeout), `pb_formula_studio 19.0.1.184.0`, `pb_import_kit 19.0.1.19.0`, `pb_hub 19.0.1.9.0`,
  `pb_pay_delivery 19.0.1.2.0`. Tests: 130 Python + 4 lint + 109 hoot — keep green, report the new counts.
- Server files: `blueprint.py, blueprint_studio.py, blueprint_components.py, blueprint_tax.py,
  blueprint_calendar.py, blueprint_connect.py, blueprint_outputs.py, blueprint_tests.py, payday.py,
  recipe_*.py, essentials_recipes.py, workbook_vocabulary.py, formula_config_ext.py, formula_rule_ext.py,
  formula_sample_ext.py (adds `hr.formula.sample.data.bp_origin`), formula_studio_ext.py`. Put B6's
  server code in `blueprint_finish.py` (`_inherit = 'pb.blueprint.studio'`), extending B1's
  `bp_finish` gate rather than replacing it; reuse `bp_evidence` (B5) for the checks line and
  `review_items` (recipe_schema) + `bp_readiness` (B4) + `bp_tests` (B5) for the decisions list.
  Client: `step_finish.js` exists from B1 (minimal) — grow it; `evidence_chip.js` is shared; text
  helpers follow the `connect_text.js`/`outputs_text.js` pattern (`_t()` inside functions only).
- **The mounted-component hoot fixture** (a mocked `pb.blueprint.studio` so a tab can be mounted
  in a test) has been deferred by B2, B4 and B5. Build it in this phase and mount at least the
  Finish step and the Components tab with it; if it genuinely cannot be done in reasonable time,
  say so with the exact obstacle — do not defer silently a fourth time.
- **Owner questions for the closeout** — copy B3's report §13 items 1–4 verbatim (5 vs 7 tax
  bands for July 2026; union dues 0.5% vs 1%; overtime exemption whole line vs premium;
  short-contract threshold 5,000,000 vs 2,000,000) and add: the temporary validator user
  `look.p4@payobook.com` (archive, or provide the working admin password); the three demo setup
  configurations on payobook ("Vietnam · Monthly payroll (guided setup)", "… — setup in
  progress", "Vietnam · Complete (guided setup demo)") to keep or remove; the B5 access-row change;
  push (≈33 programme commits on top of ~104 already unpushed on 19.1).
- Gotchas BP41–BP46 are in the ledger (a child setting parent state during render; the studio's
  replay finds spreadsheet references only; sentences built from labels). Read before coding.
- The B1 report's deferred item 1 (a full workbook import) is this phase's §4.4; the B2 report
  §11.4 and every later report note the browser bridge floors the viewport at 500 px — say so
  again rather than claiming a 390 px capture.

## 8. Report (`docs/handovers/BLUEPRINT_PHASE_B6_REPORT.md`)
Results 1–8; the `.po` generation command and the count of entries; strings that could not be
translated; the fixture workbook layout; the finish-gate reasons as implemented; polish items
done/not done; gotchas; self-score; the closeout path.
