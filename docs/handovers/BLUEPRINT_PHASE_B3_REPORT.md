# BLUEPRINT Phase B3 — report

Built, tested, deployed and Chrome-validated 2026-09-10. Scope delivered in
full; the deferred items in §12 are the ones the handover already assigned to a
later phase, plus one pre-existing failure that is diagnosed rather than fixed.

**Live on all four databases**: `pb_blueprint 19.0.1.2.0`,
`pb_pay_delivery 19.0.1.2.0` (one new seam, §10).
`pb_hr_payroll_formula 19.0.1.124.0`, `pb_formula_studio 19.0.1.183.0` and
`pb_import_kit 19.0.1.18.0` are unchanged from B2 — no engine change was
needed and no icon was added, so neither module had to ship.

**Tests**: 108 Python on p9clone (`--test-tags /pb_blueprint`), 0 failed
0 error — B1's 23 and B2's 56 among them, all still green; plus
`/pb_hr_payroll_formula:TestBracketLint` 4/4. In the browser, 16 new hoot tests
for the tax arithmetic, all passing; 4 pre-existing hoot failures in B1's
`blueprint_steps.test.js` remain and are diagnosed in §12.

**Certification**: the Vietnam · Complete starter passes its own five-person
suite through the real engine on **all four databases**, and blocks the install
if it ever stops (proven by a real uninstall and reinstall on p9clone).

---

## 1. Acceptance cases

| # | Case | Result | Evidence |
|---|---|---|---|
| 1 | Start shows Vietnam · Complete first and pre-selected; create a draft; footer and hero | **PASS** | Cards in order: **Vietnam · Complete** (`is-on`, "v2026.1 · effective 2026-01-01", "93 components · 1 rate table"), Vietnam Standard 2026, Import Excel workbook, Blank canvas. Both Vietnam cards carry a new plain line saying what they give you. Draft created → footer "Step 2 of 6 · **Vietnam · Complete · 111 components**", hero **27.04m VND** with cash 30,500,000 · deductions 3,150,000 · income tax 315,000 · employer cost 36,950,000 — the certified "Full month · local" figures exactly. `b3_01_tax_1440.png` |
| 2 | Tax tab: pack card aligned; 7 bands with derived "to"; try-income at 40,000,000 | **PASS** | "Vietnam Statutory Parameters 2026 · Version 2026.1 · in force from 1 January 2026", badge **Aligned with the pack**, authority line cited. 7 rows, every "to" derived, last "No upper limit", first row's start locked with "from the first dong". Try 40,000,000 → **6,750,000**, effective **16.9%**. Hand-check: 5,000,000×5% + 5,000,000×10% + 8,000,000×15% + 14,000,000×20% + 8,000,000×25% = 250,000+500,000+1,200,000+2,800,000+2,000,000 = **6,750,000** ✓ |
| 3 | Band 2 rate 10 → 12, Save → income tax changes; reload → persisted | **PASS** | Income tax **315,000 → 328,000**, take-home 27.04m → 27.02m, try-an-income 6,750,000 → 6,850,000. Hand-check: TAXABLE 5,650,000 → 250,000 + 650,000×12% = **328,000** ✓. Reloaded from the server still 12%. A `hr.formula.rule.version` row with reason `legislation` is asserted by test 3 |
| 4 | Add a band; it sorts into place; a duplicate start is refused inline | **PASS** | "Add a band" appended at 85,000,000 and the band above it derived its "to" automatically; typing 3,000,000 and leaving the field re-sorted it to position 2 with every "to" following. Setting band 2's start to 5,000,000 → inline **"Two bands start at the same amount."**, Save `disabled=true`, nothing written |
| 5 | Personal relief 15.5m → 11m → drift, ghost hint, ↺ chip, sync modal applies | **PASS** | Badge "1 value differs from the pack"; income tax 328,000 → **872,500**, take-home 26.48m with a −544.5k chip. Hand-check: relief 4,500,000 lower → TAXABLE 10,150,000 → 250,000 + 5,000,000×12% + 150,000×15% = **872,500** ✓. Field turned amber with **"↺ pack: 15,500,000"**; pressing it restored the value in the box. The sync dialog listed exactly one row — Personal relief · DEDUCTSELF · 11,000,000 · 15,500,000 · **+4,500,000** — and applying it returned the badge to "Aligned with the pack". `b3_02_sync_modal.png` |
| 6 | Insurance: CAPLO 46.8m → 20m → deductions drop | **PASS** | Employee deductions **3,150,000 → 2,200,000**, income tax 328,000 → 442,000, employer cost 36,950,000 → **34,900,000**. Hand-check: SIBASE = MIN(30m, 20m) = 20m → 8%+1.5% = 1,900,000, UI still on the 30m base = 300,000 → 2,200,000 ✓; employer 17.5%+3% of 20m + 1% of 30m = 4,400,000 ✓ |
| 7 | Routes disclosure: Complete shows three; Essentials explains instead | **PASS** | On Complete: "Other ways income can be taxed **3**" → 20%, 10%, 5,000,000. On an Essentials draft: *"This configuration taxes every employee as a resident on an ordinary contract. The Vietnam · Complete starting point adds a route for people who are not tax resident and one for contracts shorter than three months."* |
| 8 | Calendar: cut-off, payday rules, a real date, late-input policy | **PASS** | Last working day → **"Friday 30 October 2026** is the next payday in the company calendar (1 non-working day skipped)." with "Working days come from “Standard 40 hours/week”." (31 Oct 2026 is a Saturday ✓). Second last working day → **Thursday 29 October 2026** ✓. Fixed day 31 in October → 31st is a Saturday → Friday 30th ✓ (the 30-day-month case is covered by test 6d, which is the only place a 30-day month was reachable). Cut-off 25 → *"Anything approved after the 25th of the month waits for the next run."* Late policy and SWIFT saved and re-read. `b3_03_calendar_1440.png` |
| 9 | Pay & Deliver door with a back chip that returns to the Calendar tab | **PASS** | Opens the cockpit; chip **"New configuration"** top-left; pressing it returns to the journey on the **Calendar & payment** tab with the same draft. Required one seam in `pb_pay_delivery` (§10) — until then the door was one-way. `b3_04_paydeliver.png` |
| 10 | Components tab on Complete: 38 library rows, TRANSPORT, PIT, PREMINSALW | **PASS** | Earnings **24** · Deductions **8** · Benefits & employer costs **9** · Inputs & fixed values **61** · Totals **9** = **111**. TRANSPORT: *"For employees in eligible roles, calculate an amount that depends on the grade of 1200000 / 800000 / 500000 by grade, prorated by paid working days."* PIT: *"For everyone, calculate income tax, by the route that applies to the person of Income the tax bands apply to using Vietnam income tax (monthly, seven bands)"*, proof strip 328,000, plus the new line saying the bands live on the Tax tab. PREMINSALW: *"The same as another component · Taxable · Paid by scheme"*. PRIVHLTHEE / PRIVHLTHDEP / OTHERBEN all show **Needs a decision** with the employer-paid-tax and insurance review items. `b3_05_transport_editor.png`, `b3_06_pit_editor.png` |
| 11 | A configuration that is no longer a draft → read-only on both tabs | **PASS** | Tax: *"These values are read only here — This configuration is no longer a draft. Its values are managed from the components grid, where every change is versioned."* 24 of 25 text inputs disabled (the 25th is "try an income", which writes nothing), Save buttons gone. Calendar: the same banner, no save bar, 9 controls disabled. Every server gate refused independently (test 5) |
| 12 | Blank canvas → guidance, not a broken page | **PASS** | *"There is no income tax table in this configuration yet."* + *"No income-tax table yet. Add one from the grid, or start from a Vietnam starting point on the Start step."* + Open the grid. Relief and insurance cards absent entirely — only the constants that exist are shown. Badge **"None of the pack's values are used here"** (it said "No rule pack for this country" under the pack's own name at first — defect 4 in §9) |
| 13 | Narrow viewport: tables scroll inside their cards, no sideways page scroll | **PASS** | At 500 px: `document.scrollWidth === clientWidth === 500` and `body` likewise, while the band table scrolls itself (460 inside 355). Values stack to one column, the try-an-income strip goes vertical, the rail lies down as a horizontal stepper and the pay panel becomes a bottom bar. `b3_07_tax_narrow.png` |
| 14 | All four databases; the starter present on each; vocabulary gate green | **PASS** | Versions and hashes in §11. On **abm**: a Complete draft seeded 111 components, pack aligned, 7 bands, 3 routes, payday "Friday 30 October 2026", currency VND, Pay & Deliver door present, hero **27.04m** — the same certified number as on payobook. Rail foot "Saved to AB Mauri". Vocabulary sweep of **13,798 characters** of rendered text across all three tabs, both dialogs and the pack popover: after the fix in §9 defect 1, **0** hits for Odoo, schema, blueprint, config, rule set or recipe. **0** console errors. `b3_13_abm_tax.png` |

**14 PASS · 0 FAIL.**

Screenshots are in `.bp_shots/` (gitignored, not committed), 1440×900 unless
the name says otherwise. The browser bridge floors the viewport at 500 px on
this machine (B2 §11.4), so case 13 exercises the 899 px breakpoint at 500 px
rather than at 390 px; a device-accurate 390-px capture is not something I
could take, and I have not claimed one.

---

## 2. The `legislation_code` resolution path used

**The starter's own `components_json`, with the pack's code as the fallback.**

`hr.formula.rule` does **not** store `legislation_code` — the field exists only
on a template component and is consumed at seed time to resolve the value
(`formula_config_template.py:266-281`). So `_legis_rule_map` rebuilds the map
from the starter the blueprint records (`{legis_code: component_code}` from the
template) and looks each component up with the studio's own
`_legis_constant`. Where the starter says nothing — a blank canvas, an imported
workbook, or a starter that has since changed — it falls back to matching the
pack's own code against a component code, which is exactly what the
estate-wide rollout does for every configuration.

That fallback matters and is asserted: nothing in a Vietnam configuration is
called `EESI`, so without the starter map the social-insurance rate would show
as unmatched. `test_the_rate_is_matched_through_the_starter_not_its_name`
proves `EESI → SIRATE` and `ERUI → UIEMPR`.

`pb.formula.studio._legis_eval` was **not** reused: it evaluates a whole pack
against a whole configuration and returns rows keyed by the pack's vocabulary,
whereas this screen needs the drift list, the unmatched list and the per-value
rows in one pass with the component's own name on each. `_legis_constant` — the
one piece that is genuinely shared — is called directly.

## 3. The Vietnam · Complete starter, in full

`data/config_template_vn_complete.xml`, generated by
`tools/gen_vn_complete.py`. **93 components** (42 inputs, 16 constants, 34
formulas, one `input` that is also a total's source) plus the `VNTAX` table.
Seeding through the guided setup provisions 18 more helper rules (the `<CODE>TX`
taxable-part companions), giving the **111** the screen reports.

Every formula in the file is the guided compiler's own output for the sentence
stored beside it. That is the point of the generator: a starter whose Excel was
typed by hand drifts from its sentence the first time either is touched.

| Letter | Code | Name | Type | Group | Amount |
|---|---|---|---|---|---|
| A | BASIC | Contract salary | input | helper | input |
| B | DEPS | Registered dependants | input | helper | input |
| C | STDDAYS | Standard working days | input | helper | input |
| D | PAIDDAYS | Paid working days | input | helper | input |
| E | HOURSDAY | Hours in a working day | input | helper | input |
| F | PAYMONTH | Month being paid (1 to 12) | input | helper | input |
| G | ISLOCAL | Local employee (1 = yes) | input | helper | input |
| H | ISINSURED | In the insurance scheme (1 = yes) | input | helper | input |
| I | ISUNION | Union member (1 = yes) | input | helper | input |
| J | ISRESIDENT | Tax resident (1 = yes) | input | helper | input |
| K | CONTRACTMTH | Months on this contract | input | helper | input |
| L | TAXCOMMIT | Signed the single-employer tax commitment | input | helper | input |
| M | ROLEGRADE | Pay grade (1, 2 or 3) | input | helper | input |
| N | SERVDAYS | Days of service this year | input | helper | input |
| O | ANNUALDAYS | Working days in a full year | input | helper | input |
| P | HRSWD | Weekday overtime — hours this run | input | helper | input |
| Q | HRSWE | Weekend overtime — hours this run | input | helper | input |
| R | HRSHOL | Public-holiday overtime — hours this run | input | helper | input |
| S | HRSNIGHT | Night work — hours this run | input | helper | input |
| T | ENROLPREM | Enrolled in family health cover | input | helper | input |
| U | ENROLHLTH | Enrolled in private health cover | input | helper | input |
| V | ENROLDEP | Dependants enrolled in private health cover | input | helper | input |
| W | PRIVINSAMT | Private insurance allowance approved | input | helper | input |
| X | HLTHEEAMT | Private health premium — employee | input | helper | input |
| Y | HLTHDEPAMT | Private health premium — dependants | input | helper | input |
| Z | ADJDEDAMT | Prior-period deduction approved | input | helper | input |
| AA | PAIDVAR | Variable bonus approved this run | input | helper | input |
| AB | DEDUCTSELF | Personal relief | constant | helper | *pack* |
| AC | DEDUCTDEP | Relief per registered dependant | constant | helper | *pack* |
| AD | SIRATE | Social insurance — employee | constant | helper | *pack* |
| AE | HIRATE | Health insurance — employee | constant | helper | *pack* |
| AF | UIRATE | Unemployment insurance — employee | constant | helper | *pack* |
| AG | SIEMPR | Social insurance — employer | constant | helper | *pack* |
| AH | HIEMPR | Health insurance — employer | constant | helper | *pack* |
| AI | UIEMPR | Unemployment insurance — employer | constant | helper | *pack* |
| AJ | CAPLO | Social and health insurance ceiling | constant | helper | *pack* |
| AK | CAPHI | Unemployment insurance ceiling | constant | helper | *pack* |
| AL | UNIONCAP | Union dues ceiling (253,000) | constant | helper | manual |
| AM | UNIONRATE | Union dues — employee (0.5%) | constant | helper | manual |
| AN | UNIONEMPR | Union contribution — employer (2%) | constant | helper | manual |
| AO | NONRESRATE | Flat rate, not tax resident (20%) | constant | helper | manual |
| AP | SHORTRATE | Withholding, contract under 3 months (10%) | constant | helper | manual |
| AQ | SHORTTHRESH | Payment at which withholding starts | constant | helper | manual |
| AR | SALARYPAID | Basic salary for the days worked | formula | earning | contract |
| AS | UNIFORM | Uniform allowance | input | earning | input |
| AT | SEVERSTAT | Statutory severance allowance | input | earning | input |
| AU | OTHEREXMP | Other exempt reimbursement | input | earning | input |
| AV | ALENCASH | Unused annual-leave encashment | input | earning | input |
| AW | TRANSPADD | Additional transportation | input | earning | input |
| AX | TRANSPORT | Transportation allowance | formula | earning | role |
| AY | PHONEALLOW | Phone allowance | formula | earning | fixed |
| AZ | PRIVINSALW | Private insurance allowance for expatriates | formula | earning | input |
| BA | PREMINSALW | Premium health cover for family members | formula | earning | linked |
| BB | LOGISINC | Logistics incentive | input | earning | input |
| BC | AGROINC | Season agronomy incentive | input | earning | input |
| BD | LAUNCHINC | New product launch incentive | input | earning | input |
| BE | VARPAY | Variable bonus | formula | earning | percent_contract |
| BF | REFERINC | Referral incentive | input | earning | input |
| BG | OTHERTAX | Other taxable allowance | input | earning | input |
| BH | ADJADD | Prior-period addition | input | earning | input |
| BI | ADJDEDUCT | Prior-period deduction adjustment | formula | earning | input (sign −1) |
| BJ | NONCASHBEN | Taxable non-cash benefit | input | earning | input |
| BK | OTWD | Weekday overtime pay | formula | earning | hourly 150% |
| BL | OTWE | Weekend overtime pay | formula | earning | hourly 200% |
| BM | OTHOL | Public-holiday overtime pay | formula | earning | hourly 300% |
| BN | NIGHTPREM | Night-work premium | formula | earning | hourly 30% |
| BO | MONTH13 | Thirteenth-month salary | formula | earning | annual_ratio |
| BP | SIBASE | Social and health insurance base | formula | total | insurance_base |
| BQ | UIBASE | Unemployment insurance base | formula | total | insurance_base |
| BR | SIDED | Social insurance deducted | formula | deduction | percent_of |
| BS | HIDED | Health insurance deducted | formula | deduction | percent_of |
| BT | UIDED | Unemployment insurance deducted | formula | deduction | percent_of |
| BU | UNIONDUES | Union dues | formula | deduction | percent_of (capped) |
| BV | EEDED | Insurance deducted from pay | formula | total | sum_group |
| BW | ASSESSPAY | Assessable pay before relief | formula | total | taxable_base |
| BX | TAXABLE | Income the tax bands apply to | formula | total | taxable_base |
| BY | PIT | Personal income tax | formula | deduction | **pit_vn** |
| BZ | ADVANCE | Salary advance recovery | input | deduction | input |
| CA | PRIORDED | Prior-period deduction | input | deduction | input |
| CB | OTHERDED | Other deduction | input | deduction | input |
| CC | SICOMP | Social insurance — employer | formula | benefit | percent_of |
| CD | HICOMP | Health insurance — employer | formula | benefit | percent_of |
| CE | UICOMP | Unemployment insurance — employer | formula | benefit | percent_of |
| CF | PRIVHLTHEE | Private health cover — employee | formula | benefit | input |
| CG | PRIVHLTHDEP | Private health cover — dependants | formula | benefit | input |
| CH | UNIONER | Union contribution — employer | formula | benefit | percent_of |
| CI | OTHERBEN | Other company benefits | input | benefit | input |
| CJ | SHUILOCAL | Statutory cover — local employees | formula | benefit | sum_group (plan total) |
| CK | SHUIFOREIGN | Statutory cover — foreign employees | formula | benefit | sum_group (plan total) |
| CL | GROSS | Gross pay | formula | total | sum_group |
| CM | BENEFITVAL | Value of benefits in kind | formula | total | sum_group |
| CN | NET | Take-home pay | formula | total | net_total |
| CO | ERCOST | Total employer cost | formula | total | employer_total |

**Three code renames from the handover's §5.4 list**, all forced by the
registry's rule that no code may contain another (BP29):

- **`TAXGROSS` → `ASSESSPAY`** — `GROSS` is inside `TAXGROSS`;
- **`NONCASH` → `BENEFITVAL`** — `NONCASH` is inside `NONCASHBEN`;
- the per-component helpers the handover named (`OTWDHRS`, `PRIVHLTHEMPIN`, …)
  are **named inputs** (`HRSWD`, `HLTHEEAMT`, `ENROLHLTH`, `PRIVINSAMT`,
  `ADJDEDAMT`, `PAIDVAR`) for the same reason. The 38 workbook codes are lifted
  from `WORKBOOK_COMPONENTS` verbatim, including `UNIONER` rather than the
  handover's `UNIONMEMB`, per §9b.

**One component added that the handover did not list**: `PAIDVAR`, the switch
that says a variable bonus is approved this run. Without it a bonus of 10% of
salary was paid every month for ever (BP32).

## 4. The five people, and the numbers checked by hand

Expected values are **engine-generated** (`tools/vn_complete_expect.py` run on
p9clone, saved to `tools/vn_complete_expected.json`, baked in by the
generator), never typed. Three numbers per person are re-derived here by hand.

| | Full month · local | Joined mid-month | Foreign · not resident | Short contract | Enrolled in private health |
|---|---|---|---|---|---|
| Contract salary | 30,000,000 | 30,000,000 | 60,000,000 | 6,000,000 | 30,000,000 |
| Days paid of 26 | 26 | **13** | 26 | 26 | 26 |
| Dependants | 1 | 1 | 0 | 0 | 1 |
| Local / insured / resident | 1/1/1 | 1/1/1 | **0**/1/**0** | 1/**0**/1 | 1/1/1 |
| Months on contract | 12 | 12 | 12 | **2** | 12 |
| Salary paid | 30,000,000 | 15,000,000 | 60,000,000 | 6,000,000 | 30,000,000 |
| Gross pay | 30,500,000 | 15,250,000 | 60,500,000 | 6,500,000 | 30,500,000 |
| Insurance base | 30,000,000 | 15,000,000 | **46,800,000** | 6,000,000 | 30,000,000 |
| Insurance deducted | 3,150,000 | 1,575,000 | 4,446,000 | **0** | 3,150,000 |
| Assessable pay | 30,500,000 | 15,250,000 | 60,500,000 | 6,500,000 | **32,500,000** |
| Taxed income | 5,650,000 | **0** | 40,554,000 | 0 | 7,650,000 |
| **Income tax** | **315,000** | **0** | **12,100,000** | **650,000** | **515,000** |
| **Take-home** | **27,035,000** | **13,675,000** | **43,954,000** | **5,850,000** | **26,835,000** |
| Employer cost | 36,950,000 | 18,475,000 | 70,094,000 | 6,500,000 | 38,950,000 |

**Full month · local.** SIDED = 8% × min(30,000,000, 46,800,000) =
**2,400,000**; with HI 1.5% (450,000) and UI 1% (300,000) that is 3,150,000.
Taxed income = 30,500,000 − 3,150,000 − 15,500,000 − 6,200,000 =
**5,650,000**. Tax = 5,000,000 × 5% + 650,000 × 10% = **315,000**. Take-home =
30,500,000 − 3,150,000 − 315,000 = **27,035,000**. (The 500,000 above the
contract salary is the phone allowance, prorated to a full month.)

**Joined mid-month.** Salary paid = 30,000,000 × 13/26 = **15,000,000**, and
the phone allowance halves with it (250,000). Taxed income =
MAX(0, 15,250,000 − 1,575,000 − 15,500,000 − 6,200,000) = **0**, so no tax at
all. Take-home = 15,250,000 − 1,575,000 = **13,675,000**.

**Foreign · not tax resident.** Insurance base is capped: min(60,000,000,
46,800,000) = **46,800,000** → SI 3,744,000 + HI 702,000 = 4,446,000, and
unemployment insurance is **0** because it does not apply to a foreign
employee. Tax takes the non-resident route: 20% × assessable pay 60,500,000 =
**12,100,000**, with no relief. Take-home = 60,500,000 − 4,446,000 −
12,100,000 = **43,954,000**.

**Short contract.** Not in the insurance scheme, so nothing is deducted.
Two months on the contract and no single-employer commitment, and assessable
pay 6,500,000 is above the 5,000,000 threshold → 10% withheld = **650,000**.
Take-home = 6,500,000 − 650,000 = **5,850,000**. Employer cost equals gross
pay: no contributions are due.

**Enrolled in private health.** The employer pays a 2,000,000 premium for
dependants (`PRIVHLTHDEP`), whose taxable value to the employee is
`PREMINSALW`, also 2,000,000 — so assessable pay is 30,500,000 + 2,000,000 =
**32,500,000** while cash earnings stay 30,500,000. Taxed income = 32,500,000 −
3,150,000 − 15,500,000 − 6,200,000 = 7,650,000 → 250,000 + 2,650,000 × 10% =
**515,000**. Take-home = 30,500,000 − 3,150,000 − 515,000 = **26,835,000**.
Employer cost = 36,950,000 + 2,000,000 = **38,950,000** — the premium counted
**once**, not twice (BP33).

Two independent checks that the arithmetic is the estate's, not a new one:
`SHUILOCAL` 6,450,000 equals SICOMP + HICOMP + UICOMP exactly, and the
"Full month · local" employer cost of 36,950,000 is B1's own 36,450,000 plus
the phone allowance and its employer contributions.

## 5. Certification

The pack's own harness, run on the template through
`certify_module_templates(env, 'pb_blueprint')` from a `post_init_hook` — the
same call `pb_pack_vn` makes, discovered through `ir.model.data` so it cannot
certify somebody else's template by accident.

- **Install gate proven**: `pb_blueprint` was uninstalled on p9clone (state
  `uninstalled`) and installed fresh. Log line:
  `F113 certification PASSED for vn_complete_2026 (module pb_blueprint): 5 tests`,
  exit 0, zero ERROR/CRITICAL.
- **Every database**, run explicitly through `run_certification`:

| Database | Passed | Checks | Failures |
|---|---|---|---|
| p9clone | **True** | 5 people × 18 values | none |
| payobook | **True** | 5 × 18 | none |
| abm | **True** | 5 × 18 | none |
| payobook_template | **True** | 5 × 18 | none |

- **And after the guided setup has touched it**, which is the claim that
  matters: `test_a_guided_draft_reproduces_the_certified_numbers` creates a
  draft through `bp_start`, lets it provision its helper inputs and regenerate
  every formula from the sentences, and asserts all 90 expected values again to
  ₫1. The sentences produce the certified numbers.

## 6. What "insurance basis" and "rounding" do

Both are stored on the blueprint (`tax_json`) and both are **wired into the
compiler**, not just displayed.

**Insurance basis** rewrites the `basis` of every `insurance_base` recipe and
regenerates:

- *What was actually paid* (`actual`, the default) → `MIN(<sum of every earning
  marked as counting toward insurance>, <ceiling>)`. On Complete that is
  `MIN(SALARYPAID, CAPLO)`, so a person who joined on the 13th has half the
  insurance base.
- *The contract salary* (`contract`) → `MIN(BASIC, CAPLO)`. A short month does
  not reduce anybody's cover.

`test_the_insurance_basis_changes_what_the_base_adds_up` asserts the stored
recipe flips, and the compiler unit test asserts the two formulas differ by
exactly which letter they read.

**Rounding** rewrites the `round` field of every earning, deduction and benefit
**that already rounds**: `"0"` emits `ROUND(…,0)`, `"down"` emits
`ROUNDDOWN(…,0)` (toward zero — the choice a payroll makes when it must never
pay a fraction more than the rule allows). A component set to keep every
decimal is **left alone**, which is why the Essentials starter — deliberately
exact so its own certification expectations stay byte-identical — is untouched
by the control, and the card says so in words.

## 7. The payday algorithm, and what it reads

`models/payday.py`, no ORM in it at all.

```
payday_for(rule, day, year, month, workdays, holidays) -> (date, weekends, holidays)
```

- `last_working` starts at the last day of the month and steps **back** to the
  first day that is both a working weekday and not a company closure.
- `second_last_working` does that, then steps back once more from the day
  before it.
- `fixed` starts at the chosen day, or at the month's last day when the chosen
  day is beyond it ("the 31st" in a 30-day month means the 30th), then steps
  back the same way.
- The two counts are what was stepped **over**, so the sentence "weekends and
  one public holiday skipped" is answerable rather than decorative.

Its inputs come from the company, in `_company_calendar`:

- **working days** = the weekdays on `res.company.resource_calendar_id`'s
  attendances (Monday is 0). A company with no working calendar gets Monday to
  Friday and is **told so** on screen rather than given a wrong date.
- **public holidays** = `resource.calendar.leaves` on that calendar (or on no
  calendar at all) with **`resource_id = False`** — a closure that belongs to
  nobody in particular is a day the company is shut, which is what a public
  holiday is — expanded day by day across the month in question.

The month is the one the configuration is meant to start in, unless that is
already behind us, in which case the month after this one: a payday that has
been and gone tells nobody anything.

## 8. The compiler extensions, as implemented

`pit_vn` is the **17th** amount kind. It compiles to three nested routes and
every route beyond the bands is optional, so a configuration without the
constants taxes everybody on the bands exactly as before:

```
=IF(ISRESIDENT=0, ROUND(ASSESSPAY*NONRESRATE,0),
   IF(CONTRACTMTH<3,
      IF(AND(ASSESSPAY>=SHORTTHRESH, TAXCOMMIT=0), ROUND(ASSESSPAY*SHORTRATE,0), 0),
      ROUND(BRACKET(VNTAX, TAXABLE),0)))
```

(shown with codes; what is stored is letters, BP-R4).

Also added, each because leaving it out would have produced a wrong number:

| Addition | What it is for |
|---|---|
| `employer_share_pct < 100` on a benefit | Provisions `<CODE>EE` — a deduction for the employee's half — from the same sentence, so the two halves cannot drift. Proven live: 70/30 on a 1,000,000 premium gives 700,000 and 300,000 |
| `treatment.plan_total` | A roll-up of employer costs already counted individually. Never a member of any group sum, including the employer-cost total, so a scheme is never charged twice |
| `treatment.tax_bearer == 'employer'` | No arithmetic change; a review item in words, amber on the row and named in the editor |
| `round: "down"` | `ROUNDDOWN(…,0)` |
| `audience: "local_insured"` | `AND(ISLOCAL=1, ISINSURED=1)` — unemployment insurance in one word instead of two nested sentences |
| `amount.max` | A ceiling on the amount itself: union dues stop at 253,000 |
| `amount.basis` on an insurance base | Contractual or actual eligible pay (§6) |
| `amount.deduct_contributions` on a taxable base | Assessable pay before relief, for the flat-rate routes |
| `inputs: {...}` | A recipe may NAME the input it reads (BP29) |
| `of.exclude` on `net_total` / `employer_total` | Keeps a benefit mirror out of the employer's cost (BP33) |

Two behaviours that were **wrong before** and are fixed: "taxed the same way as
the original" returned the original's *value* (BP31), and a payment "the scheme
decides" was paid every run (BP32).

## 9. Nine defects the browser found that code review did not

1. **Somebody else's jargon reached a payroll manager.** The "where these
   values come from" panel rendered the rule pack's own `description`, and the
   shipped Vietnam pack's reads *"Serves both existing-config rollout (B4) and
   new-config template seeding (F113)"*. The white-label gate reads **our**
   files, and no file of ours contained those words. The field is no longer
   sent to the client at all, and a new test scans the whole `bp_tax_data` and
   `bp_calendar_data` answers (BP34).
2. **"Aligned With The Pack"** — BP19 again: the kit's badge is
   `text-transform: capitalize`, right for a status word, wrong for a sentence.
3. **The pack's name printed twice**, once as the heading and again at the
   start of the line under it.
4. **"No rule pack for this country" under the pack's own name** on a blank
   canvas — a pack that exists but matches nothing here is a different
   situation, and saying the wrong one reads as a contradiction.
5. **Income tax was a dead end.** Somebody opening PIT to change 10% to 12% saw
   a band-table picker and no hint of where the bands are.
6. **The Pay & Deliver door was one-way** (§10).
7. **A cut-off day of 31 was silently pulled back to 28** instead of refused
   (BP35).
8. **The sticky save bar read as text floating over a radio button**; the sync
   dialog's four short columns were squeezed into a scrollbar they did not
   need; a component code was glued to the end of its own label.
9. **The first persona came out 3,000,000 too high** — a variable bonus of 10%
   of salary paid every single month (BP32). Found by hand-checking the
   engine's own answer against arithmetic, which is why the report does that.

## 10. Files touched outside `pb_blueprint`

`pb_formula_studio`, `pb_hr_payroll_formula`, `pb_import_kit` and `pb_pack_vn`
were **not touched at all**. Every icon the two new tabs use (`landmark`,
`barChart`, `shield`, `userCheck`, `clock`, `coins`, `inbox`, `calculator`,
`receipt`, `external`, `scrollText`, `lock`, `trash`, `plus`, `undo`,
`refresh`, `chevron`, `chevronDown`, `table`, `alert`, `x`) was already in the
one registry, so the kit did not have to ship.

| File | Where | Before → After |
|---|---|---|
| `pb_pay_delivery/static/src/js/pb_pay_delivery.js` | `setup()`, `:28` | *(nothing)* → 4 lines reading `pb_back` from the action context |
| `pb_pay_delivery/static/src/js/pb_pay_delivery.js` | before `pickRun`, `:73-85` | *(nothing)* → `goBack()`, 13 lines |
| `pb_pay_delivery/static/src/xml/pb_pay_delivery.xml` | top of the root div, `:6-9` | *(nothing)* → the chip, `t-if="back"` |
| `pb_pay_delivery/static/src/scss/pb_pay_delivery.scss` | before `.pbpd-picker-head` | *(nothing)* → `.pbpd-back`, 16 lines |
| `pb_pay_delivery/__manifest__.py` | `:32` | `19.0.1.1.0` → `19.0.1.2.0` |

Deliberately **not** imported from `pb_hub`: `pb_pay_delivery` does not depend
on it, and an import of a module absent from the bundle takes the whole backend
down rather than failing locally.

## 11. Deploy

Ledger ritual: clean `/tmp/bp_stage`, scoped per-module `rsync --delete`,
`pg_dump` per database before the first upgrade, service stopped for the
production upgrades, asset purge plus a `web.assets.version` bump, never
`pkill`.

Dumps taken before the first upgrade: `/tmp/bp3_dumps/payobook.dump` (53 M),
`abm.dump` (16 M), `payobook_template.dump` (11 M).

| Database | Upgrade | Exit | ERROR / CRITICAL |
|---|---|---|---|
| payobook | ok | 0 | **0** |
| abm | ok | 0 | **0** |
| payobook_template | ok | 0 | **0** |

Five further rounds followed as the browser found defects; every one exit 0
with zero ERROR or CRITICAL from module loading on any database. p9clone was
upgraded eight times by the test runs, plus one full uninstall and reinstall to
prove the certification gate, all exit 0.

Final state — manifest vs `ir_module_module.latest_version`, all four:

| Database | pb_blueprint | pb_pay_delivery | starter templates | Complete certifies |
|---|---|---|---|---|
| p9clone | 19.0.1.2.0 | 19.0.1.2.0 | 7 | **yes** |
| payobook | 19.0.1.2.0 | 19.0.1.2.0 | 7 | **yes** |
| abm | 19.0.1.2.0 | 19.0.1.2.0 | 7 | **yes** |
| payobook_template | 19.0.1.2.0 | 19.0.1.2.0 | 7 | **yes** |

Tree hash repo vs server across both modules, byte-identical:
`6b9ee193263c311cb9b1c4acbb64fb26`.

**Errors and how they were resolved**: one test failure on the first run
(`_clamp` pulled an out-of-range cut-off day into range instead of refusing it
— defect 7, fixed), one hoot expectation I had written wrongly (the effective
rate on 40,000,000 is 16.88%, not 13.63%), and the nine browser defects in §9.
Zero ERROR or CRITICAL from module loading on any database, on any round.

## 12. Deferred, with reasons

1. **Employer-paid tax gross-up** — a binding non-goal (§3 of the handover).
   Recorded instead as a review item on `PRIVHLTHEE` and `PRIVHLTHDEP`, amber
   on the row, in words: *"The employer pays the tax on this: the value is
   taxed to the employee for now, and the employer's top-up is not worked out
   yet."* Guaranteed-net contracts likewise.
2. **The overtime exemption is the whole line, not the premium part** — the
   handover's own ruling, shipped with a review item on all four overtime
   components: *"Confirm which part of overtime is tax free."* See §13.
3. **A hoot test that mounts the Tax or Calendar tab.** The 16 new hoot tests
   cover the pure arithmetic — the band maths, the derived upper bound, the
   refusals, the number formats. Mounting either component needs a mocked
   `pb.blueprint.studio`, which is a fixture worth building once for B5 where
   there are three surfaces to cover; the behaviour is covered live in cases
   2–8 meanwhile.
4. **Four pre-existing hoot failures in `blueprint_steps.test.js`** (B1's
   suite). They throw *"translations have not been loaded"* when they stringify
   a `_t()` label defined at `blueprint_steps.js`'s module scope. BP28's fix
   was applied at import time, in a root `beforeEach`, and in a `beforeEach`
   inside every `describe` — the identical guard works for `recipe_text.test.js`
   and for B3's own `tax_math.test.js` (16/16). Diagnosed and documented as
   BP36; **not** fixed, because the remaining candidates (mocking the
   translation service, or asserting on keys rather than words) change what
   those tests are for, and they are not B3's. B4 should settle it.
   One real improvement did land: the failure used to be a bare
   `toBeTruthy is not a function` TypeError — a matcher this hoot build does
   not have — which hid the actual cause.
5. **A device-accurate 390-px capture.** The browser bridge floors the viewport
   at 500 px on this machine (B2 §11.4). The breakpoint under test is 899 px,
   so the layout was genuinely exercised; I have not claimed a 390-px shot.
6. **No Vietnamese `.po`** — B6, as scoped. Every visible string is inside a
   literal `_t(...)` or QWeb text, so extraction will find it. Note for B6:
   `blueprint_tax.value_label` and `payday`'s weekday and month names are
   functions for exactly the reason B2's helper labels are — a module-level
   `_t()` runs at import time, before any language is known.

## 13. Owner questions (§8 of the handover)

1. **Five bands or seven?** The workbook proposes a **five-band** 2026 schedule
   (Law 109/2025, in force from 1 July 2026); the shipped rule pack carries
   **seven**. B3 ships the pack's seven and makes changing them a two-minute
   job on screen. The proper vehicle for the new schedule is a new pack version
   — say the word and it is a small, dated, auditable change rather than an
   edit to every configuration.
2. **Union dues: 0.5% or 1%?** The workbook says both in different places.
   **0.5% is shipped**, with a ceiling of 253,000 a month, and the union
   components are switched off by default (the "union member" flag starts at
   no). Changing the rate is one field on the Tax tab.
3. **Overtime: is the whole payment tax free, or only the premium above the
   normal rate?** The law exempts the *premium*; the workbook says "PIT exempt
   for qualifying OT". **The whole line is treated as tax free while the
   evidence is held**, which is the workbook's reading, and all four overtime
   components carry a visible review item saying so. If the premium-only
   reading is right, it is a change to one sentence per component.
4. **The short-contract threshold.** The handover specified **5,000,000** and
   that is what ships. Circular 111/2013 says **2,000,000**. One field on the
   Tax tab either way, but somebody should decide which is right for you.
5. **Two demo configurations are on payobook.** B1's two, plus one this phase
   left deliberately: *"Vietnam · Complete (guided setup demo)"*, a finished
   111-component draft you can open to see the new tabs with real numbers in
   them. Everything else created during validation was discarded through the
   product's own path (payobook back to 22 configurations, abm unchanged).
6. **The temporary validator user is still switched on**, unchanged from B1 and
   B2: `look.p4@payobook.com` on payobook and abm, password
   `BpB1validate!2026`. Say the word and it is archived — or better, tell me
   the working administrator password and it can go for good.
7. **Nothing has been pushed.** Six commits this phase, on top of the thirteen
   from B1 and B2 and the ~104 the branch was already carrying.

## 14. Self-score against the bar

> "extreme WOW, intuitive, out-of-this-world experience, best in class."

- **Hero** — 9/10. The hero of this phase is the try-an-income slider sitting
  directly under the bands you are editing: drag it and the tax moves as the
  handle moves, edit a rate and both the slider's answer and a real person's
  take-home pay move within a second, in the same eyeline. The band table's
  derived upper bound is the quiet part I am proudest of — it is not validation,
  it is a shape in which the mistake cannot be made. A point off because the
  hero panel still shows four plain lines; the money-flow strip B5 brings is
  what will make that sing.
- **Zero dead-ends** — 9/10. Every state was designed and walked: no pack for a
  country, a pack that matches nothing here, no band table at all, a schedule
  that cannot be right (three different refusals, each naming its reason), a
  configuration that has stopped being a draft (two different reasons, said
  apart), a company with no working calendar, a month whose last day is a
  Sunday, a fixed day beyond the end of a short month, Pay & Deliver not
  installed, and 500 px. Half a point off for the one I had to build rather
  than find: the Pay & Deliver door was a genuine dead end until I added a chip
  to another module.
- **Plain language** — 9/10. 13,798 characters swept, zero banned words, and
  the defect I am most glad of is the one no file scan could catch: another
  module's engineering description reaching a payroll manager through my
  screen. The refusals name the thing and the next step — "Two bands start at
  the same amount", "The first band has to start at zero, or income below it
  would not be taxed at all". A point off because "None of the pack's values
  are used here" is still a sentence I had to think about twice.
- **Motion with purpose** — 8/10. The tried income highlights the band it lands
  in; the payday preview dims while the server works it out; the save bar
  rises with a shadow rather than floating; the hero's count-up and delta chip
  carry every save. Nothing moves that is not reporting a change, and
  `prefers-reduced-motion` is honoured. Unchanged from B1's toolkit rather
  than extended.
- **Keyboard and bulk** — 7/10. Enter stays inside a number field instead of
  walking off the step, tab order is sane, every control is labelled for a
  screen reader, and the band rows re-sort on blur rather than while typing.
  There is no bulk work on these two tabs to ergonomise, and I did not add
  arrow-key movement between band rows, which is the obvious next gain.

**With one more hour**: (a) arrow keys and Enter-to-add between band rows;
(b) a before → after pair on the try-an-income strip when a rate changes, so
the effect of the edit is visible without remembering the old number;
(c) settle BP36 so B1's four hoot tests are green again.
