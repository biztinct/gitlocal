# WDGAP W2-C — Work back from take-home: report

Branch `wdgap-w2c` (from `origin/19.1` @ 4c9c82a40), not merged, not deployed.
Modules: `pb_formula_studio` 19.0.1.212.0 → **19.0.1.213.0**, `pb_contracts`
19.0.1.13.0 → **19.0.1.14.0**. No change to `pb_hr_payroll_formula` (read-only use of
`_pb_formula_steps`, `formula_program.run_sample`, `excel_semantics`,
`value_kind_classifier`, `schemes_for_employee`, `_contract_component_values`), no
`pb_pack_*`, no pay-run module.

## 1. What was built, and where it is reached

A calculator. It never changes a payslip, a contract or a pay run.

| Where | How a person gets there |
|---|---|
| Formula Studio, Live preview | Preview a real employee → pick a run → a person → **Work back from take-home** (a dashed button under "Real numbers · Keep as sample · Clear") |
| Formula Studio, Tools (⌘K) and the text palette (⌘⇧K) | **Take-home calculator** (Analyze lane). With nobody on screen it opens the person picker and says "Pick a real employee first". |
| Contract drawer (People › Contracts, Employees › Contract) | A quiet **Work back from take-home** link under the Monthly wage cell — only when the wage is editable and not masked. **Use this amount** copies the figure into the open form (staged, "was …" shown, Save bar "Save 1 change"); nothing is written until Save, which follows the wage change's normal approval. |

The card: take-home wanted, pay item to change (number inputs of the scheme; default = the
item the pay run fills from the contract wage — codes `BASIC`/`WAGE`/`BASE` or a mapping
to the contract's wage — else the scheme's base-pay heuristic, else "choose"), pay scheme
(when the person has two), "Now" figures, where the other figures come from ("as on the
payslip of 10/01/2026" or "from the contract and the scheme's usual values"). The answer:
hero figure + one plain sentence, both neighbours when the exact figure is unreachable, a
Now / Worked back table (the item, gross pay, deductions, take-home, employer
contributions, with deltas), and the full payslip at that figure with changed lines
marked (indigo bar) and an "Only what changed" filter. Footer: "Worked out in N tries ·
x s".

Server: `pb.formula.studio.take_home_open(config_id, payslip_id, contract_id)` and
`take_home_solve(config_id, target, item_code, payslip_id, contract_id)`
(`pb_formula_studio/models/take_home.py`); the search is ORM-free in
`take_home_solver.py`. Card: `static/src/js/take_home.js`, `xml/take_home.xml`,
`scss/take_home.scss`, opened through the overlay service (`openTakeHome`, soft registry
`pb_take_home` → `open`).

## 2. Solver outcomes

| Outcome | When | What the person reads |
|---|---|---|
| exact | the lowest item value whose take-home, written in the currency, IS the target | "To take home 25,000,000 ₫, Basic Salary must be 23,066,529 ₫." |
| closest | rounding or a step jumps over the target | "… cannot be reached exactly — the scheme's rounding or a tax step jumps over it. Closest: Basic Salary 22,039,044 ₫ gives 23,999,999 ₫; Basic Salary 22,039,045 ₫ gives 24,000,001 ₫." + Just under / Just over chips |
| not possible — flat | take-home does not move with the item (not in the net formula) | "Take-home does not change when X changes …" |
| not possible — goes down | the item takes money off (loan instalment) | "Take-home goes down when X goes up …" (added after the walk) |
| not possible — never | it moves but never reaches (a capped take-home) | "Take-home never reaches T: even with X at V, take-home is N." |
| not possible — already above | even with the item at 0 take-home is above the target | "Take-home is already N with X at 0, which is above T." |
| falls (note) | take-home drops somewhere as the item rises | answer = lowest value found + "Take-home goes down at one point as X rises (between …)" |
| formula error | a formula that take-home depends on raises for this person (before the solve, and again at the answer) | "… the formula for “Income tax” has an error for this person (it divides by zero). Fix it in Formula Studio first." |
| garbage / limit / bad target | not a number; 200 tries used; target ≤ 0 | one sentence each |

Method as specified: bracket [T, 1.6T] (widen ×2 up to 8 times, or drop to 0 when T is
already reached), 12-point grid **from where the search started** to the top it reached,
lowest crossing, bisection on the currency grid to one smallest unit (≤ 60 halvings),
200 evaluations per request, answer re-evaluated (R2). Rounding:
`excel_semantics.excel_round` with the scheme currency's decimals.

## 3. Tests

Local, one database at a time (prefix `wdgap_w2c_`), dropped afterwards (filestore too).
`wdgap_w2c_t` = copy of `upd_p6_t_tpl` brought to `origin/19.1` (32 modules behind) with
pristine copies of the two touched modules first on the path; baseline run before any
edit was loaded.

| # | Case | Result |
|---|---|---|
| 1 | Flat 10 % tax, VND: 12,000,000 → 13,333,333 (closed form: lowest whole dong with ROUND(0.9x) ≥ 12,000,000); changed lines = basic, tax, take-home; gross/net totals | PASS |
| 2 | Progressive marginal tax + insurance on a 46,800,000 cap; targets 12M / 30M / 60M; forward check (value reaches, value − 1 does not); insurance line frozen above the cap | PASS |
| 3 | Step bonus at 10,000,000: target 9,200,000 → closest, 9,999,999 → 8,999,999.1 and 10,000,000 → 9,500,000 | PASS |
| 4, 4b, 4c, 4d | item not in take-home → flat; capped take-home → never; allowance already above → already; deduction item → goes down (above and below today's take-home); allowance worked back exactly | PASS |
| 5, 5b | formula dividing by a zero input in take-home's path → refused naming "Income tax"; the same error in a formula take-home does not read → solves | PASS |
| 6 | rises, falls, rises again → lowest (13,333,333) + note | PASS |
| 7, 7b, 7c, 7d | 10-try cap → `limit` after exactly 10 calls; 1e12 target in < 120 tries; garbage ('abc', NaN, inf, None, True) → refused after 1 try; constant scheme → flat; no take-home line → said plainly | PASS |
| 8, 8b | **R1**: SQL spy on the cursor — no INSERT/UPDATE/DELETE during open + solve by payslip and by contract; write dates, stored inputs and row counts unchanged; 8b proves the spy sees a real write | PASS |
| 10, 10b | **R4**: SGD 2 decimals → 1,082.84 (cents); VND whole dong | PASS |
| 11, 11b | **R5**: plain internal user → refused (rights); payroll user, person/contract/scheme in another company → refused (company); same user in own company → served | PASS |
| 12, 12b, 12c | contract door: wage item `BASIC` from the contract (no payslip) → 18,000,000 needs 20,000,000, "Use" allowed, contract unchanged; scheme whose item is not read from the wage → "Use" not offered; text inputs not offered as items | PASS |
| 13 | no "Odoo" in the card's user-visible text | PASS |
| 20 | **every demo scheme** on a real demo payslip (12 Payobook schemes incl. the 6 advance schemes, whose payslips store no inputs → scheme defaults, as the Live preview reads them): target = today's take-home × 1.1; forward check through the sample evaluator = reported take-home | PASS (on the demo copy; skipped elsewhere) |
| R2 | every case with a figure: the figure fed through `preview_from_payslip` (a new payslip carrying it) gives the reported take-home, both neighbours too | PASS |

**Full suites `/pb_formula_studio,/pb_contracts`, `-u` both:**
baseline **671 tests (587 counted), 8 failed, 1 error**; branch **697 (611 counted), the
identical 9** (before the walk fixes) — `TestCd1Contract360.test_01_payload_carries_every_top_level_key`,
`TestJourneyView` ×2, `TestNetPayCandidates` 01, `TestOneMappingHome` ×4,
`TestRunsrcPcBoardLane` 14 (all fail on unchanged code). Final re-run after the walk
fixes: see §3a.

Demo-world copy (`wdgap_w2c_demo`, copy of `upd_p5e_pay`, jobs and mail servers off):
`TestW2cTakeHome` **25/25** (test 20 ran, 12 schemes).

Static gates: py_compile OK; `node --check` (module) on take_home.js, formula_studio.js,
contract_360.js OK; the three XML templates parse; PO gate (`PoFileReader`) on both
`vi_VN.po`: every new string reaches the screen (`pb_formula_studio`: 65 new entries + 5
existing ones given the new occurrence; `pb_contracts`: 1 new); no "Odoo" in any new user-visible string.

### 3a. Final full-suite re-run

After commit 45e2e5d56, on a fresh copy built the same way: **698 tests (612 counted), 8 failed,
1 error — the identical 9 as the baseline** (`diff` of the failure lists: empty). Database
dropped afterwards.

## 4. Timing per solve (demo world, one person each, local Mac)

| Scheme | Components | Outcome | Tries | Solve |
|---|---|---|---|---|
| Retail — End-Month | 54 | exact (16,770,000 → Basic 13,872,696) | 33 | 0.11 s |
| Manufacturing — End-Month | 51 | exact | 33 | 0.10 s |
| Logistics — End-Month | 52 | exact | 33 | 0.11 s |
| Corporate Office — End-Month | 53 | exact | 33 | 0.10 s |
| Information Technology — End-Month | 53 | closest (25,562,000: ±1 dong of Basic moves take-home by ~2 dong) | 33 | 0.11 s |
| Construction — End-Month | 50 | exact | 32 | 0.10 s |
| the six Mid-Month Advance schemes | 53–56 | exact | 30–31 | 0.09–0.10 s |
| VPTQ End / Mid Cycle | 86 / 85 | no take-home line and no base-pay item (Vietnamese codes, no pay roles) → "choose a pay item" / "no take-home line" | — | 0.01 s |

Opening the card: 0.1–0.3 s. In the browser the whole round trip was 0.5–0.7 s.

## 5. Browser walk (local demo copy, branch code, QA login with a local-only password)

- Formula Studio → Corporate Office End-Month → Preview a real employee → October run →
  Bùi Anh Nam → **Work back from take-home**: card shows Now (Basic 19,600,000; take-home
  21,626,200; "as on the payslip of 10/01/2026"). 25,000,000 + Enter → "Basic Salary must
  be 23,066,529 ₫", 13 lines changed, highlighted; Now/Worked back table. Console clean.
- Loan Installment as the item, 30,000,000 → "Take-home goes down when Loan Installment
  (in) goes up …" (after the fix; before it read "never reaches … even at
  12,288,000,000").
- Double click on the door → one card.
- Contracts → Bùi Anh Nam (19.6M) → drawer → link under Monthly wage → card (loading line
  first, then the amount box focused) → 24,000,000 → closest (22,039,044 / 22,039,045) →
  **Use this amount** → wage cell "22,039,045, was ₫19,600,000", header 22,039,045, Save bar
  "Save 1 change"; database still 19,600,000. Escape closed the card only (drawer stayed);
  Discard; Escape closed the drawer. Console clean.

Walk findings fixed (commit 45e2e5d56): totals box squeezed to one row; card appeared only
after the first read (now mounts with "Reading this person's pay…"); amount box not
focused; double card; loan sentence.

## 6. R1–R6

| Rail | Result |
|---|---|
| R1 read-only | PASS — SQL spy: zero INSERT/UPDATE/DELETE across open + solve (payslip and contract doors); stamps and counts unchanged (tests 8, 8b). In-memory payslip and lines only (`.new()`). |
| R2 reported gross gives reported net | PASS — every case through `preview_from_payslip`; demo world through the sample evaluator; the solver's answer is re-evaluated by the engine before it is reported. |
| R3 terminates | PASS — 200-try ceiling (test 7: exactly 10 calls with a 10 cap), ≤ 60 halvings, garbage refused after one try, constant / falling / capped schemes end in a sentence. Real schemes: 30–34 tries. |
| R4 rounding | PASS — `excel_round` with the scheme currency's decimals; VND whole dong, SGD cents (test 10). No Python `round()` on money in the new code. |
| R5 rights | PASS — pay team (`om_hr_payroll.group_hr_payroll_user`, or administrator) only; payslip, contract, person and scheme must be in the user's companies (test 11, 11b). Reads run under sudo after those checks, so a payroll officer without formula rights is served. |
| R6 demo / translations / version | PASS — demo data untouched (local copies only, dropped); 66 new `vi_VN` entries (no `id` file in either module); PO gate; both versions bumped. |

## 7. Deviations from the handover (and why)

1. **Error check is our own probe, not `_evaluate_rules_with_dependencies(errors=…)`.** That
   out-parameter is never filled on either path: the compiled `_evaluate` AND
   `_run_formula` both catch every exception and answer 0.0, and the non-read-only path
   also writes (`_compute_dependencies`, diagnostics). The probe re-runs each compiled
   formula once with the exception let through (`_Engine.diagnose`), at today's figure and
   at the answer. Only errors in formulas that take-home depends on refuse (from the stored
   dependency lists, which over-report — stricter, never laxer); an erroring formula
   take-home never reads does not block the answer (test 5b).
2. **Lowest crossing instead of early stop.** Bisection runs to one smallest unit and
   returns the LOWEST item value that reaches the target (the honest "minimum needed",
   and the source of both neighbours). Cost: 30–34 tries on real schemes, far under 200.
3. **Grid from the starting point**, not from the widened bottom — otherwise a take-home
   that rises, falls and rises again is never seen falling (test 6).
4. **"Goes down" outcome** added for deduction items (walk finding).
5. **Contract door copies only into the wage**, and only when the chosen item is the one
   the pay run fills from the contract wage; otherwise the card says why it cannot.
6. Take-home is `pb_pay_totals()['net']` on an in-memory payslip's lines. During the
   search only the take-home lines are built (net sums only those lines, so it is the same
   figure); the before/after payslip uses every line.

## 8. Owner questions (plain words)

1. **Several people at once?** Today the calculator does one person. Do you want a version
   that takes a list (for example a spreadsheet of agreed take-home figures) and gives the
   pay for each? Customer demand so far: unknown — none recorded.
2. **"Net basis" contracts later?** Some customers agree pay as take-home and want the
   system to keep the take-home fixed every month (re-working the pay when tax or
   insurance changes). This phase only works the figure out once. Do you want that later?
3. The VPTQ schemes on the demo world have no take-home line marked, so the calculator
   says it cannot work there. Should the category review be run on them?

## 9. Deploy notes

Normal tier: `-u pb_formula_studio,pb_contracts` on the five databases, asset purge,
restart. No data change, no new model, no stored field. After deploy: Formula Studio →
any scheme with payslips → Preview a real employee → Work back from take-home; and a
contract drawer as a payroll manager (link under Monthly wage). The link does not show for
people who cannot see or edit the wage — expected.

## 10. Gotchas → ledger

- **W2C-1** `pb_payruns` overrides `hr.payslip.line.pb_pay_totals` to total PER `slip_id`:
  lines without a payslip (`hr.payslip.line.new(...)` alone) total **0** for everything. In-memory lines
  must belong to an in-memory payslip (`hr.payslip.new({'line_ids': [Command.create(...)]})`).
  The existing **offer calculator** (`offer_calc`) builds bare lines, so its Earnings /
  Deductions boxes are empty wherever `pb_payruns` is installed (all live databases) —
  not fixed here (out of scope), one-line fix available.
- **W2C-2** `_evaluate_rules_with_dependencies(..., errors=dict)` is never filled — both
  `_run_formula` and the compiled `_evaluate` swallow exceptions — and the non-read-only
  path writes. Detect formula errors by re-running the compiled step with the exception
  let through.
- **W2C-3** A live scheme's formula cannot be edited in a test (scheme gate: "Create a
  branch…"); build the test scheme whole instead of editing it.
- **W2C-4** A local copy made with `createdb -T` by the OS user is owned by that user;
  the web client lists only databases owned by `odoo` and shows the database manager.
  `ALTER DATABASE … OWNER TO odoo` before a browser walk.
