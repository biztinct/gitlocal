# WDGAP S8-A — Pay structure (pay scales + build from a total): report

Branch `wdgap-s8a` (from `origin/19.1` @ abc2259b6), pushed, not merged, not deployed.
New modules `pb_pay_scales` 19.0.1.0.0 and `pb_pay_package` 19.0.1.0.0; `pb_pay`
19.0.3.8.0 → **19.0.3.9.0**, `pb_contracts` 19.0.1.14.0 → **19.0.1.15.0**. No `pb_pack_*`,
no pay-run or formula-engine file, no `pb_lifecycle`, no `pb_me_portal` touched.

## 1. What was built

### J4 — pay scales, stage 1 (`pb_pay_scales`)

| Piece | What it is |
|---|---|
| Models | `pb.pay.scale` (country, money, companies, family, amounts or coefficient × base rate, 1–12 steps, rounding unit), `pb.pay.scale.grade`, `pb.pay.scale.version` (dated; two versions never overlap — the band rule cloned; an ended version is read-only), `pb.pay.scale.cell`, `pb.pay.scale.package` (grade allowances per version, each naming a contract pay line) |
| Job → grade | new field `pb_scale_grade_id` on the EXISTING `pb.pay.band.job` (no second job map); only jobs already in a band of the scale's country can sit on a grade |
| On scale / Pinned / Drifted | `pb.pay.scale.placement` (one row per contract: grade, step, pinned + reason). State is worked out when read (scale version in force today vs the contract wage), never stored, so a cell edit shows "Drifted" at once. **Placing, pinning or editing the scale never writes `hr.contract`.** Read-only `hr.contract.pb_scale_state` / `pb_scale_label` (computed, not stored) |
| People › Pay › **Scales** tab | first tab (via a registry seam in `pay_hub.js`). Ladder grid: amount + people per cell; click to type, Tab/Enter; "+%" per grade row, per step column, whole table; staged edits + "Save N changes" with the line "Nobody's pay changes"; versions as chips (in force / coming / ended), "New version" (date + grow %), remove a version not yet started; four quiet cards (On scale, Pinned, Drifted amber, Not placed yet indigo with "Place the N people paid exactly a step"); wire check per paying scheme ("reads basic pay from the contract" / "when a pay data file is loaded, the file's basic pay wins" / "no basic pay item from the contract wage"); "Start from what you pay" (median / quartiles of today's wages, staged, never saved by itself); grade drawer (rename, order, jobs, allowances, remove); people drawer per cell / state with "Mark on step N", "Keep this pay", "Unpin", and the person's contract drawer; scale details (name, steps, rounding, companies, notes, remove); ⌘K 3460 "Pay scales"; action `pb_pay_scales.action_pb_pay_scales` |
| Joiners start on the scale | job → band link in force on the start date → grade → scale (active, serving the company) → version on the start date → **step 1**. People › Add a contract opens with the wage filled + "From the pay scale: ₫… — Grade, step 1 of …"; a typed wage that is a step stays On scale at that step; any other typed wage wins and asks "Why is it different?" (reason → Pinned). Add employee asks when job/date change. Server side, an EMPTY wage is filled on create (contract wizard, Updates joiners sheet row with a job and no wage — shown in the review grid before sending, Hiring "joined" only when the agreed offer had no monthly pay — the offer's trail says so; an agreed offer wage is kept and pinned "Offer agreed"). Grade allowances are written on the NEW contract only when it is On scale, only for pay items the person's own scheme has (SCHEMECTX), each logged in the pay-line trail as "From the pay scale" dated the contract start |
| Chips | contract drawer header: "On scale · Grade, step N", "Pinned · reason", "Drifted · …" with **Bring to step** (stages the wage in the open form; Save follows the contract's normal approval) and **Keep this pay**; "Not on the scale yet · Grade" with "Mark on step N" (wage already a step) or "Use step 1". Employee side panel: the same line through `pb_employee_360_chips` |

### Build from a total (`pb_pay_package`)

Contract drawer link "Build from a total" beside "Work back from take-home". Card: total
package (a year / a month), basic pay item + share of the total (default 50%) or a fixed
amount, the item that takes the rest (suggested by name: special / balance / flexi), scheme
picker when two. The scheme's own formulas fill everything that follows basic; the W2-C
search (`take_home_solver.solve`, reused as-is) finds the balancing item so that **gross pay
+ employer contributions = the monthly total** (both from the one totals rule). A scheme line
in the employer band that already reaches gross pay (the India pack's `ERCOST = GROSS +
EPFCOMP + ESICOMP`) is treated as a total line and NOT counted again, with a sentence saying
so. Answer: one sentence, four totals (gross, employer, total a month + a year, take-home,
each with "was"), pay items now → new, the payslip lines (changed only / all). **Use these
figures** stages wage (+ pay line) in the open drawer; nothing is written until the drawer's
Save, which went "Sent for approval" in the walk. Plain refusals: nobody pays the person,
fewer than two items, no gross line, same item twice, bad total / share, an item the total
does not move, basic too large, formula error, an item the contract does not hold.

## 2. Files edited outside the new modules (all in the lane)

| File | Change |
|---|---|
| `pb_pay/static/src/js/pay_hub.js` | `pb_pay_tabs` registry: `extraTabs()`, tabs drawn before the tab named by `before`, `extraTab` getter, breadcrumb/title, no band load for an extra tab |
| `pb_pay/__manifest__.py` | 19.0.3.9.0 |
| `pb_contracts/static/src/js/contract_360.js`, `xml/contract_360.xml` | `header.extra_chips` (stage a wage / run one server method then re-read); "Build from a total" link via `pb_build_total` |
| `pb_contracts/__manifest__.py`, `i18n/vi_VN.po` | 19.0.1.15.0; 2 entries |

Rendering of the extra Pay tab's heading and body is a `t-inherit` of `pb_pay.PbPayScreen`
from `pb_pay_scales` (pay.xml untouched). Wizards, Updates, Hiring, drawer payload: `_inherit`
/ `patch()` only.

## 3. Tests

Local, one database (`wdgap_s8a_t`, copy of `upd_p6_t_tpl` brought to origin/19.1), dropped
at the end with its filestore.

| # | Case | Result |
|---|---|---|
| S1 | versions never overlap; version on a date; coefficient 2.34 × ₫2,340,000 → ₫5,480,000 at a 10,000 unit; step out of range refused | PASS |
| S2 | **RAIL**: SQL spy on `hr_contract`, `hr_contract_advantage(_change)`, `hr_payslip(_line)`, `hr_employee`, `hr_version` — zero writes across save cells, new version, place matching, pin, unpin, board, people; wage / write date / lines unchanged; person reads Drifted after the cell moved | PASS |
| S2b, S2c | spy sees a real write; an ended version refuses edits | PASS |
| S3, S3b | resolver: step 1 + sentence; job on no grade; before the first version; scale only for another company; scale in other money than the scheme that pays the person | PASS |
| S4 | Add a contract: dialog pre-filled; EMPTY wage filled on create; On scale; meal allowance written (scheme has it), phone allowance NOT (scheme lacks it); one trail row "From the pay scale" on the start date | PASS |
| S5, S5b, S5c | typed step → On scale step 2; typed other → Pinned with the screen's reason; no reason → "Typed when hired"; job on no scale → nothing; suggestion reads the typed wage; Add employee passes the reason to the contract | PASS |
| S6 | Updates joiners: job + no wage → scale amount in the grid; typed wage untouched; no job → nothing | PASS |
| S7 | Hiring joined: no monthly pay → scale wage + trail message; agreed wage kept, pinned "Offer agreed" | PASS |
| S8, S8b–d | board counts, place matching (only exact steps), people by cell, place / pin / unpin, chip stage door, employee chip; drawer header carries the chip; masked wage gets no stage door; grades / jobs / versions (+10% copy, previous ends the day before, allowances carried, remove a future version re-opens the previous); start from what you pay saves nothing | PASS |
| S9 | rights: plain user — board says not allowed, writes AccessError, models unreadable; pay viewer reads, cannot write | PASS |
| S10 | **golden**: payslip of an untouched contract computed before and after placing others, editing cells, a new version and a joiner create — identical lines | PASS |
| S11 | no "Odoo" in any user-visible string of the module | PASS |
| P1, P1b | India-shaped DEMO scheme built in the test: ₹12,00,000 a year, basic 50% → basic 50,000, HRA 20,000, employer PF 1,800 → **special allowance 28,200 EXACT**, total 100,000 a month; the "Employer cost" total line not counted twice (note); same answer without that line | PASS |
| P2 | read-only: SQL spy, zero INSERT/UPDATE/DELETE across open + solve | PASS |
| P3 | figures re-evaluated by the engine give the reported total (₹3.6 L, 12 L, 27.5 L) | PASS |
| P4–P9b | basic too large; item the total does not read; refusals (same item, no target, bad share, no balance, no gross line); fixed basic + monthly total (special 42,200); plain user refused; use payload stages wage + SPECIAL; an item the contract does not hold is not offered | PASS |
| P10 | white-label | PASS |

**Suites.** Baseline (origin/19.1 pristine copies of pb_pay, pb_contracts first on the path):
`/pb_pay,/pb_contracts` 201 tests, **3 failed, 2 errors** — `TestCd1Contract360.test_01_payload_carries_every_top_level_key`,
`TestPayBands.test_t02_the_pass_is_one_statement_and_it_is_fast`,
`TestVietnameseIsComplete.test_t4c_the_catalogue_covers_the_whole_exported_template`, and two
`TestPayStaticContract` errors that are artefacts of the pristine path (sibling module files not
found). Branch `/pb_pay,/pb_contracts,/pb_pay_scales,/pb_pay_package,/pb_people_advanced`:
**232 tests, 3 failed, 0 errors — the identical 3**; the two static-contract tests now run and
PASS (icons from the shared set, no invented colour). `pb_people_advanced` has no tests of its
own. After the walk fixes (new modules only): `/pb_pay_scales,/pb_pay_package` 32/32.

**Static gates.** py_compile; XML parse of every template; `node --check` on every new/edited
JS; PO gate (`PoFileReader`): pb_pay_scales vi 196 / id 196, pb_pay_package vi 59 / id 59
strings reach the screen, pb_contracts vi parses; no platform name in any msgstr.

**Browser walk** (local copy, `http://s8a.localhost:8571`, DEMO data, console clean): People hub
› Pay — tab row "Scales · Bands · Fairness · Review · Changes", hub does not scroll; scale
details → companies; Not placed yet 10 → "Place the 7 people paid exactly a step" → On scale 7,
people per cell; cell 5,500,000 → 5,600,000, "Save 1 change" → Drifted 1 (DB wage unchanged);
Drifted list → contract drawer chip "Drifted · Store associate, step 1 · Bring to step · Keep
this pay" → Bring to step staged "5,600,000 was 5,500,000", Discard; Build from a total on an
India DEMO scheme: ₹12,00,000 → special allowance ₹28,200 + note on "Employer cost" → Use these
figures → "Save 2 changes" → "Sent for approval"; standalone ⌘K action with Back to People;
People › Add a contract for a joiner: wage box filled "$5,600,000.00 — Store associate, step 1
of DEMO Retail store scale", 5,700,000 typed → "Why is it different?" + reasons → create →
new-hire approval; employee panel chip "On scale · Store associate, step 2". **Walk findings
fixed** (commit 73b75830f): the hire-screen patch broke the dialog's own `setup` (error on
open); hint now says why a scale is not used; "Keep this pay" for a person paid no step;
"1 job"; chip doors wrapped; Build-from-a-total wording when nobody pays the person and when
the balancing item is not a contract pay line.

## 4. Rails

| Rail | Result |
|---|---|
| Nothing changes an existing contract or payslip until a user applies a scale/package | S2 SQL spy (zero payroll-table writes from every scale operation); placements are their own table; wage moves only through the contract drawer's Save + approval (walk: "Sent for approval") |
| Golden: untouched contracts' payslips byte-identical | S10 |
| Joiner writes only on CREATE, only an empty box, shown before saving | S4–S7; hire screens pre-fill and explain; the Updates grid shows the scale amount before sending |
| SCHEMECTX: never another scheme's component | S4 (phone allowance not written) |
| Read-only calculator | P2 |
| No wage floors, revisions, arrears, step-ups | not built (left for later) |
| White-label / translations | S11, P10, PO gate |
| Rights | S9, P8; every screen call gated, then sudo inside the reader's companies |

## 5. Contracts other phases rely on

- `registry.category("pb_pay_tabs")` entry `{icon, label, title, subtitle, before, Component}` — any module may add a Pay tab (the heading/body inherit lives in `pb_pay_scales/static/src/xml/pay_screen.xml`; a second module adding a tab without depending on pb_pay_scales would need that inherit too — or the orchestrator can move it into pay.xml in a prep commit).
- Contract drawer `header.extra_chips`: `[{key, icon, label, tone, title, stage_wage, stage_label, action: {model, method, args, label}}]`, filled by overriding `pb.contracts._cd_header` (call super, append).
- `pb.pay.scales.resolve(job, company, day, employee) → {found, why, grade, scale, version, step, amount, sentence, steps}`; `joiner_suggest(employee_id, job_id, date_start, company_id, wage)`; `place_new_contract(contract, reason, source, note)`; `contract_chip(contract_id)`. S8-B's Change job can read the grade/step of a person (`pb.pay.scale.placement`) and offer "to Grade, step" later.
- `pb.pay.package.package_open(contract_id, config_id)`, `package_solve(contract_id, total, period, basic_mode, basic_value, basic_code, balance_code, config_id)` → `use: {wage, items: [{code, name, amount}]}`; JS `registry.category("pb_build_total").get("open")(overlay, {contractId, onUse}, onClosed)`. Hiring offers can call the same server method later.
- New field `pb.pay.band.job.pb_scale_grade_id`; `hr.contract.advantage.change.change_source` += `pay_scale`. No field added to `pb.pay.apply` (seam table). No new stored field on `hr.contract`.

## 6. Deploy notes (risky tier: wage on create, new modules)

- `-u pb_pay,pb_contracts` and `-i pb_pay_scales,pb_pay_package` on all five databases; asset purge; restart. No data migration; both modules install empty (no scale, no job on a grade → no joiner default anywhere until a customer writes a scale).
- `pb_pay_scales` depends on `pb_hiring`, `pb_updates`, `pb_people_advanced`, `pb_scheme_map`, `pb_employee_vault`, `pb_contracts`, `pb_pay`: check they are installed on every database first (a missing one would be force-installed).
- `pb_pay_package` depends on `pb_formula_studio` (W2-C engine) and `pb_contracts`.
- Rehearsal: recompute a few rize payslips old vs new = 0 differences (nothing in this step touches a pay run; the golden test is local). FACTS §12 item 2 counts (renewals losing pay lines, contract vs employee job, typed cost centres) are S8-B/S8-C's measurements, not taken here (no live access).
- Live check after deploy: People › Pay › Scales opens empty with "Write your first pay scale"; a contract drawer shows the new link under the wage for a pay-team login; whether any live database has an India scheme is unknown from the repo (`hr.formula.config` country IN).

## 7. Owner questions (plain words)

1. **Moving people when the scale goes up.** Today a new table only marks people "Drifted"; each one is brought to the new step from their contract, one approval each. Do you want the next stage — one "raise the scale" request that moves everybody on it, with the true cost, one sign-off and letters?
2. **People already paid above their step.** When the scale moves, should they stay where they are (design default: keep their pay, show Pinned) or also get the same percentage?
3. **Build from a total for Indian offers.** Should Hiring offers get the same "build from a total" box, so the offer letter shows the split?

## 8. Left for later

Legal minimum wages / wage floors (Step 1, D2) · scale revisions with true cost, approval, apply-all + 24-hour undo, arrears, letters (blueprint P3) · time-based step-ups and the Home queue (P4) · the pay policy paragraph per scheme and house rules (P2) · employee portal "your pay on the scale" · Pay Review / Pay changes speaking in grades and steps · scale ticks in the band picture · group view across countries · time scrubber beyond version chips · paste a grid from a spreadsheet, block select · Formula Studio Tools entry for Build from a total (no Tools registry exists; contract drawer only) · Build from a total in Hiring offers · Explorer column for grade (C-5).

## 9. Gotchas → ledger

- **S8A-1** An object-literal method that calls `super` keeps the `super` of the literal it was WRITTEN in. Copying it into another object (a "merge" of two patch objects) and patching that one makes `super.setup` undefined — the dialog then fails to open. Patch each class with its own literal (a factory function), never a merged copy.
- **S8A-2** Local walks: signing in on `127.0.0.1:<port>` logged another builder's walk out (shared cookie jar for the host, W2A-6). Use a host of your own: `http://<phase>.localhost:<port>` resolves to the machine and keeps its own cookies.
- **S8A-3** A non-stored computed field without `@api.depends` (scale standing) is cached for the whole transaction: a test that reads it, changes the scale, and reads again sees the old answer. `env.invalidate_all()` between (every screen request is a new environment, so the screens are fine).
- **S8A-4** On local template copies the company currency (USD) differs from a Vietnam scheme's (VND): anything that compares "the money the person is paid in" must take it from the scheme that pays them, and fixtures must build the scale in the scheme's money.
- **S8A-5** The full `/pb_pay,/pb_contracts` run took ~45 minutes overnight because the Mac slowed down; `caffeinate -dimsu -w <pid>` brought it back (PRM-5).
