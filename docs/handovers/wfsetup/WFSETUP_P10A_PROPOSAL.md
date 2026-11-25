# WFSETUP P10a — how clock hours feed Sudima's pay from 1 Dec 2026 (study + proposal)

Agent: Opus 5.5, 25 Nov 2026. Brief: `WFSETUP_P10A_STUDY_HANDOVER.md`. Owner rulings R8–R12 in `WFSETUP_OWNER_RULINGS.md`.
Read-only study: SELECTs on live `sudima` only (no temp objects left, no writes on any database), no code changed.
Engineering document: real technical names on purpose. No names, employee numbers or credentials in this file.
Line refs are `origin/19.1` at `892ad5442` unless marked "server" (the server's own standard-addon copy).

**White-label rule for P10b (binding):** no user-visible string may say "Odoo" — labels, chips, help, toasts,
refusal lists, template headers, payslip lines. Use "Payobook" or neutral words. Technical identifiers unchanged.

---

## 0. Verdict in five lines

1. **Mechanism: keep Sudima on the pay data file (path B) and add a "From the clocks" source** that, from a
   scheme-level date (1 Dec 2026), replaces the file's value for exactly three hour inputs and fills two new
   information-only inputs. Every other column stays on the file. Sep–Nov runs are untouched by construction.
2. Switching Sudima to application-data payroll (path A) is **rejected**: it has no file, so ~31 monthly money
   columns × ~650 people would have to be typed into the worksheet each month (contradicts R9), and its
   paid-days rule needs a weekly sign-off for every person-week plus a calendar that does not exist yet (§2).
3. **Lateness (R10) reaches pay only through paid normal hours**, which the rules already cut by the late time and
   the band deduction. Nothing else may deduct lateness; three guards make a second deduction impossible (§5).
4. A December run is **refused with a named list** whenever a clock number is missing or doubtful — never zeros (§6).
5. Leading zeros: **60 clock numbers / 5,519 punch records gain a match; 0 collisions on sudima** (§8).

## 1. What is on live sudima today (2026-11-25, measured)

| Fact | Value |
|---|---|
| Pay schemes | **one**: id 7844 `SUDIMA_SEP_2026_AUDIT` "Sudima September 2026 — Print-Audit review", **state = draft**, `payroll_basis=timesheet`, `standard_day_basis=calendar`, `application_data_enabled=false`, `application_effective_from=2026-09-01`, lanes `api,excel,records` all on, no structure. Built by `tools/install_sudima_payroll_review.py` (so the P10a brief's "unknown whether it is the live scheme" is settled: it is the only one). |
| Pay runs / payslips / pay data files | **0 / 0 / 0** (`hr_payslip_run`, `hr_payslip`, `hr_payroll_import_batch` all empty). There are no trial runs; the only pay data is the **650 September test cases** stored on the scheme (`hr_formula_sample_data`, + 1 archived). |
| Contracts | 650, **all draft**. The run wizard only picks people with a running contract (`pb_payrun_wizard/models/pb_payrun_wizard.py:_eligible_employees`). |
| Rules (`pb.attendance.policy` id 2) | **draft**, tz Asia/Ho_Chi_Minh, capture 2 h before / 6 h after, night premium **off**. Bands — worker: 0–1 min 0 h (confirmed); **1–10 min 0 h NOT confirmed** (blocks activation, `policy.py:68-87`); ≥10 min **4 h** (confirmed). Manager: 0–10 min 0 h; ≥10 min 1 h. Shift rules: day 07:30–16:30, normal window 9 h, 1 h unpaid break from +4 h ⇒ **8 h planned normal**; two night templates "review". |
| People on the rules | 651 active people set to Worker on policy 2; **27 active people with no policy**. |
| Roster | 12,384 **draft** day shifts, 19 Nov–16 Dec, 517 people, **Mon–Sat only, all `pb_day_kind=weekday`**, no Sundays. Nothing after 16 Dec. |
| Attendance / overtime entries / weekly timesheets / late decisions | 0 / 0 / 0 / 0. Built-in extra-hours lines 0. |
| Time off, public holidays | **0 `hr_leave` rows; 0 company-wide calendar leaves (no public holidays anywhere)**. 73 leave types exist. |
| Work calendars | all 678 active people on cal 1 "Standard 40 hours/week" (Mon–Fri, 8 h). The three Sudima 6-day calendars (202/203/205) are assigned to nobody. |
| Overtime limits (`pb_ot_ceiling`, global row) | daily 4 h, monthly 40 h, annual 200 h (special 300 h). Rates (`hr_overtime_config` VN rows): weekday 150 %, rest day 200 %, holiday 300 %, night 130 %. |
| Company | `pb_timesheet_payroll = true`; `pb_timesheet_block_run` NULL (off). Built-in extra hours: `attendance_overtime_validation = no_validation`. |
| Modules | pb_attendance_policy 19.0.1.0.0, pb_time_pay 19.0.1.1.0, pb_timesheet_approval 19.0.1.1.1, pb_hr_payroll_formula 19.0.1.169.1, pb_payrun_wizard 19.0.1.47.0, pb_clock 19.0.1.4.3. |

### 1.1 The scheme's inputs and the formulas that read hours/days (scheme 7844)

40 inputs, every one `data_source=excel`, default 0, one `excel` source row ("Audit|<label>"). Hour/day inputs:

| Col | Code | Label | September test cases (650) |
|---|---|---|---|
| I | `VNPAIDDAYS` | Paid day equivalents | 0–29; **312 fractional** (25.5 ×174, 26 ×207, 25.75 ×35…). Client sheet: ordinary days **+ annual leave** (setup review 2026-11-07 §3); includes the paid public holidays of the month. Already carries `application_source_key=period.paid_day_equivalents` (unused: path A is off). |
| J | `VNLEAVEQTY` | Leave / meal quantity in source | **0 for all** (× `VNLEAVERATE` 50,000 = meal pay) |
| L | `VNOTHOURS` | Normal overtime base hours | 619 have OT; avg 65.4 h; max 97 h; **549 above 40 h** (avg 31.5 h above) |
| M | `VNPREMHOURS` | Overtime premium equivalent hours | **603 of 619 = exactly 0.5 × L** (weekday 150 %); 4 ≈ 1.0 × L (rest day 200 %); 12 between (mixes). So M = Σ hours × (rate − 1). |
| N | `VNSUNDAYHOURS` | Sunday base hours | **0 for all** (Print-Audit puts rest-day work in L/M at 200 %) |
| G, H | `VNDIVISOR`, `VNHOURSDAY` | Monthly divisor / hours per salary day | 26 and 8 for everyone |

Formulas (live `excel_formula`, unchanged by this proposal except §4.3):

```
VNDAYRATE  = IF(VNBASIS=1, (VNBASE+VNRESP+VNPOS)/VNDIVISOR, VNBASE+VNRESP+VNPOS)
VNBASEHOUR = IF(VNBASIS=1, VNBASE/VNDIVISOR, VNBASE) / VNHOURSDAY
VNREGULAR  = VNDAYRATE * VNPAIDDAYS              (earning)
VNLEAVEPAY = VNLEAVEQTY * VNLEAVERATE            (earning)
VNOTPAY    = VNBASEHOUR * VNOTHOURS              (earning)
VNPREMPAY  = VNBASEHOUR * VNPREMHOURS            (earning, tax-free: subtracted in VNATAX)
VNSUNPAY   = VNDAYRATE / VNHOURSDAY * VNSUNDAYHOURS   (earning, tax-free)
VNATAX     = VNGROSS - VNPERSONAL - VNOTHERDED - VNINS - VNPREMPAY - VNSUNPAY - VNSAT + VNTAXCARRY
```

So basic pay = day rate × paid days (monthly: (basic+resp+pos)/26 per day; daily: the daily rates); overtime is
priced on the **basic** hourly rate only. **No lateness or absence deduction input exists** — lateness today can
only show up as a smaller `VNPAIDDAYS`.

### 1.2 Answers to the brief's four questions

1. Scheme/run: 7844 is the only scheme, **draft**; no runs. A December run would use 7844 — after it is activated
   and the contracts are running (owner question Q5).
2. Inputs/formulas: §1.1. Paid days = I; standard days = G (fixed 26, a contract component); overtime = L (all
   types) + M (premium part); Sunday = N (unused); night = none (shift allowance `VNSHIFT` is money on the file);
   lateness/absence = none.
3. Paid leave and paid public holidays enter **only inside the file's paid-days number**. Payobook holds no leave
   records and no holidays for Sudima. ⇒ The clock number alone would drop them (§4.3, Q1).
4. `LATEMIN`, `EARLYMIN`, `REGHRS`, `TOTHRS`, `WORKDAYS`, `OTHRS*`, `BONHRS`: **referenced nowhere** in Sudima's
   scheme (no input, no formula). `pb_time_pay` has 0 late decisions on sudima.

## 2. Mechanism — chosen: path B + a "From the clocks" source (path A rejected)

### 2.1 Why not switch Sudima to path A (application data) on 1 Dec

| Need | Path A (application data) | Path B + clock source |
|---|---|---|
| R9 "everything else stays on the spreadsheet" | **No file at all.** The 31 money inputs (allowances, deductions, insurance, advance, relief, tax exceptions) would need a value per person per month from records or approved monthly adjustments (`payroll_period_input.py:392-440`, exactly one approved row each) — ≈20,000 cells/month typed in the worksheet, which has no upload (`payroll_review.xml`). | File unchanged except three columns now read from the clocks. |
| Sudima's two summed hour columns (all OT types in L, premium part in M) | One key per input (`application_source_key`); no key sums types or applies (rate − 1). Would need new inputs + formula rewrites on the same scheme that Sep–Nov files use. | Clock keys are defined to match L and M exactly; formulas unchanged. |
| Paid days from attendance (lateness) | Only `payroll_basis=timesheet` reads attendance (`application_payroll_source.py:494-610`): every person-week must be an **approved** packet (~2,900/month), and regular hours are checked against the **work calendar** — all 678 people are on a Mon–Fri calendar, so every Saturday shift is a conflict ("Regular work … exceed scheduled hours", line 580). Never used live (Rize runs path A on `contractual`). | Day equivalents per shift from the rule's own planned normal hours — no calendar dependency. |
| Contracts, certification | Needs running contracts, exactly one per person, and a per-run certification of four channels (lines 759-776, 994-1021). | Needs running contracts (any run does). |
| Leave / holidays | From `hr.leave` + calendar holidays — Sudima has none. | Stays on the file (Q1). |
| Strengths | Frozen immutable snapshot, certified coverage, mature on Rize. | Small, date-gated change; reuses provenance chips. Snapshot gap closed by a clock stamp (§3.6). |

**Safer: path B + clock source.** Path A would change *how Sudima works* (no file, weekly sign-offs, calendars,
certification) on the same day it starts using clocks; path B changes three numbers on the file they already use.

### 2.2 Refinement of the brief's preferred shape

The brief proposed a new `kind='clock'` row on `hr.formula.rule.source_ids`. **Rejected in that form:**
`formula_rule_source.py:51-53` forbids a fourth kind ("these are the kinds a RUN can be asked to read, and a run
carries at most two payloads"), and the ranked lanes (`formula_config.py:400-525`) are *fallback* orders — the clock
must **override** the file from a date, never fall back to it. **Clone the RUNSRC precedent instead** (`period_key`):

- `hr.formula.rule.pb_clock_key` — Selection of the keys in §4.1, input rules only (clone `period_key`,
  `formula_rule.py:703-735`; label "Answered by the clocks"). Written through `set_source_binding('clock', key)`
  (clone the `pay_run` branch, `formula_rule.py:435-444`; `clear_source_binding` branch at :474) so every board and
  chip keeps one entry point. Shown first in `declared_sources()` (clone the splice at :404-410) — display only.
- `hr.formula.config.pb_clock_from` — Date "Hours from the clocks from", tracked; empty = off. **One date per
  scheme, not per input:** a half-switched month (overtime from the clocks, paid days from the file) is exactly the
  double-count shape we must not allow. Editable on the scheme's Sources tab (SC-4 card) and in the component
  editor's source card ("From the clocks — from 1 Dec 2026").
- Gate per payslip: `date_from >= pb_clock_from` ⇒ clock; `date_to < pb_clock_from` ⇒ file exactly as today;
  a period that crosses the date ⇒ refused ("This pay period starts before and ends after the clock start date.
  Split it at that date.").

## 3. Architecture (P10b seams)

### 3.1 The provider (in `pb_attendance_policy`, which already depends on `pb_hr_payroll_formula`)
New `pb_attendance_policy/models/clock_payroll.py`: `hr.formula.config._pb_clock_facts(employee, date_from,
date_to)` → `{key: {'value', 'status': 'resolved'|'conflict'|'missing', 'reason', 'evidence'}}` plus a person-level
`blockers` list. Base stub in `pb_hr_payroll_formula` returns `{}` (then the overlay refuses: "Clock hours are not
installed for this scheme"). Reuse `_fact()` shape from `application_payroll_source.py:117`.

### 3.2 The overlay (in `pb_hr_payroll_formula`, new `models/clock_source.py`, one function)
`apply_clock_values(config, payslip_like, input_values, prov)`: if the scheme has `pb_clock_from` and the period is
on/after it, for every input with `pb_clock_key`: take the fact; `resolved` ⇒ overwrite the value and write
provenance `input_provenance.entry('employee_field', key=<clock key>, via='clock')` (add `'clock'` to `VIAS`,
`input_provenance.py`; plain chip words "From the clocks"); anything else ⇒ collect. Any collected reason ⇒
`UserError` listing them all. **Never falls back to the file cell, never to the default 0.** Called at:
- path B: `payroll_import_batch.py` `_transform_data_to_formula_inputs`, **after the pay-period fill (:4890-4913) and
  before constants (:4915)** and the proration/retro/carryover adjustments;
- file-less resolver: `hr_payslip_formula.py:_get_formula_input_values`, after its period fill (:860-875) — so
  "Recompute" without an import line cannot quietly return file-era numbers.
Path A is not touched (no clock keys there).

### 3.3 Neutrality rail
No scheme anywhere has `pb_clock_from` today ⇒ the overlay returns at its first line. P10b test: resolve a file row
for a scheme without the date and for a period before the date — `input_values` and provenance **byte-identical**
to today (SOURCING S1 md5 method), and a counter proving the clock branch was never entered.

### 3.4 Information-only inputs stay information-only (R11)
Constraint on `hr.formula.rule`: an input whose clock key is information-only (§4.1 "info") must have
`net_role='info'`, `appears_on_payslip=False`, and **no formula may reference it** (check every formula rule's
dependencies on save of either side; plain refusal "“Actual hours” is shown for information and cannot be used in a
formula. Pay is worked out from paid hours."). Same check repeated in the pre-run list.

### 3.5 Pre-run check seam
Clone `pb_timesheet_approval/models/payrun_wizard.py:85-133` into `pb_attendance_policy` (inherit
`pb.payrun.wizard`): before `create_and_compute` and `compute_batch`, if the chosen scheme is clock-sourced for the
period, call the provider for every eligible person and raise one grouped refusal (§6). Also expose a read-only
`pb_clock_readiness(config_id, date_start, date_end)` for the wizard's data step panel.

### 3.6 Stamp (the snapshot gap of path B)
The overlay writes a stamp of the facts it used (`_stamp` of shift/request ids + write dates + values) into the
provenance entry. Run/payslip approval (`write` to `level1`/`verify`/`done`, clone the guard idea of
`application_payroll_source.py:1176-1185`) recomputes the stamp and refuses if hours changed after computing:
"Clock hours changed after these payslips were computed. Recompute before approving."

## 4. The clock keys and the mapping

### 4.1 Exact key definitions (provider, per person, payslip period `[date_from, date_to]`)

Rows read:
- **S** = `hr.shift.planning` with `employee_id`, `date` in the period (**shift date = local start date**, overnight
  belongs to its start date — `policy.py:229`), `state='published'`, `pb_policy_id.state in ('active','retired')`.
  Per shift date, never "weeks whose Monday is in the period" (`timesheet_packet.py:802-819` is NOT used: 1 Dec
  2026 is a Tuesday and the week of 30 Nov would land in November).
- **O** = `hr.overtime.request` for the person with `date` in the period, any origin (rule-made or typed; the rules
  refuse a day that already has a typed entry, `policy.py:380-383`, so no duplicates).

| Key | Definition | Use |
|---|---|---|
| `clock.worked_days` | Σ over S of `proof.normal_hours / shift_rule.normal_hours` (planned normal hours of that shift's rule, 8.0 for Sudima's day shift), each shift counted only if its calculation is current (`att._pb_policy_valid(date)`). Rounded to 4 dp at the end. Rest-day/holiday shifts contribute 0 (all their hours are overtime, `engine.py:47`). | pay |
| `clock.paid_normal_hours` | Σ `proof.normal_hours` over the same shifts, 2 dp. Already **minus late time and band deduction**. | info (shown beside days) |
| `clock.ot_hours` | Σ over O with `state='approved'` and type in weekday/weekend/holiday of `approved_hours` **(+ `bonus_hours` if Q2 = "pay all")**. Excluded: refused (zeroed by `action_refuse`), requests the manager gave as time off (`pb_comp_choice == 'time_off'` when the field exists — same rule as `pb_time_pay/models/hr_payslip.py:101-103`). | pay |
| `clock.ot_premium_hours` | Σ of the same hours × (`rate_multiplier` − 1) per request ⇒ weekday ×0.5, rest day ×1.0, holiday ×2.0 today. Per-type multipliers recorded in evidence. `rate_multiplier` is a stored related of the current OT rule (`overtime_request.py:69-71`), hence the stamp (§3.6). | pay |
| `clock.over_limit_hours` | Σ `bonus_hours` of the same requests (hours above the 4 h/day, 40 h/month, 200 h/year limits, `ot_ceiling.py:136-146`). | info |
| `clock.actual_hours` | Σ `proof.worked_hours` over S (time at work inside the capture window after the unpaid break, before any lateness deduction; includes overtime time). Not the request field `actual_hours` (naming trap: that one is PAID overtime). | info (R11) |
| `clock.late_minutes` | Σ `proof.late_minutes` over S. | info |
| `clock.deduction_hours` | Σ `proof.penalty_hours` over S (band deductions). | info |

Conflicts (person blockers; any one ⇒ refusal, §6): a shift in S without calculated attendance or whose
calculation is not current, or whose status is an error other than "no punches at all"; a shift with exactly one
punch; an overtime entry in O in `draft`/`submitted`; an approved `night` or `extended` entry (no pay input maps
them — mirror of path A's "Approved overtime has no pay-affecting mapping", `application_payroll_source.py:804-810`);
`rate_multiplier` missing or < 1; any `hr.attendance` of the person in the period without `pb_policy_roster_id`
(clock hours outside a shift — e.g. made by the old pairing before the rules were active, P8 report §blocker 2);
clock punches on a local date in the period with **no published shift** (Sunday work with no rest-day shift);
the person has **no published shift in the whole period** (unless excluded from the run).
A published shift with **zero punches** is not a blocker: it is an absence and counts 0 (listed for information
on the readiness panel; paid leave/holiday comes from the file column, §4.3).

### 4.2 Mapping table — Sudima input → source from 1 Dec 2026

| Col | Input | From 1 Dec | Note |
|---|---|---|---|
| A–B | `VNID`, `VNNAME` | file | identity |
| C–H | `VNBASIS`, `VNBASE`, `VNRESP`, `VNPOS`, `VNDIVISOR`, `VNHOURSDAY` | file | rates |
| I | `VNPAIDDAYS` | **clock `clock.worked_days`** | worked-day equivalents only; leave + holidays via the new column (Q1) |
| J–K | `VNLEAVEQTY`, `VNLEAVERATE` | file | meal quantity (0 today) |
| L | `VNOTHOURS` | **clock `clock.ot_hours`** | Q2 decides whether over-limit hours are in it |
| M | `VNPREMHOURS` | **clock `clock.ot_premium_hours`** | |
| N | `VNSUNDAYHOURS` | file, **must be empty in clock months** (refusal otherwise) | Sunday work arrives as rest-day overtime in L/M; a number here would pay it twice |
| O–AN | all 30 money inputs and tax flags | file | unchanged |
| new | `VNLEAVEDAYS` "Paid leave and holiday days" | file (Q1 option A) | default 0; Sep–Nov files have no such column ⇒ 0 ⇒ unchanged |
| new | `VNACTUALHOURS` "Actual hours (from punches)" | clock `clock.actual_hours`, info | R11; never in a formula |
| new | `VNPAIDHOURS` "Paid normal hours" | clock `clock.paid_normal_hours`, info | shown beside paid days |
| new | `VNLATEMIN` "Late minutes" | clock `clock.late_minutes`, info | never in a formula (§5) |
| new | `VNOVERLIMIT` "Overtime above the legal limit" | clock `clock.over_limit_hours`, info | so HR can see it whatever Q2 says |

### 4.3 The one formula change (Q1 option A)
`VNREGULAR = VNDAYRATE * (VNPAIDDAYS + VNLEAVEDAYS)`. Sep test cases still pass (`VNLEAVEDAYS` = 0). Guard: in a
month **before** the clock date `VNLEAVEDAYS` must be empty (the file's paid days already include leave there);
refused otherwise. Under Q1 option B (Sudima records time off and holidays in Payobook) no formula changes and
`clock.worked_days` gains + approved paid leave days + calendar holiday days (reuse the leave/holiday day logic of
`application_payroll_source.py:444-492`), with Sudima's 6-day calendar assigned first.

### 4.4 Worked example (anonymised, December-like month)

Daily-paid worker: basic 250,000/day, responsibility 20,000/day, position 0, divisor 26, 8 h per salary day ⇒
day rate 270,000; basic hourly rate 31,250. Month: 26 rostered weekday shifts (07:30–16:30, 8 h normal after a 1 h
unpaid break) of which 1 is a public holiday (not worked) and 1 is paid annual leave ⇒ 24 worked shifts; on 2 of
them the person arrived 15 min late (worker band ≥ 10 min ⇒ 4 h deducted); 4 h weekday overtime in the month,
approved; 1 Sunday worked, 8 h paid after break, on a rest-day shift, approved.

Clock facts: paid normal hours = 22 × 8 + 2 × (8 − 0.25 − 4) = **183.5 h**; worked days = 22 + 2 × 0.46875 =
**22.9375**; overtime hours = 4 + 8 = **12**; premium hours = 4 × 0.5 + 8 × 1.0 = **10**; late minutes 30;
deduction hours 8; actual hours = 22 × 8 + 2 × 7.75 + 4 + 8 = **203.5** (paid 195.5; the 8 h gap is the two band
deductions). File: leave + holiday days = 2.

| Line | Before (file, typed from the attendance register, no lateness cut) | After (clock) |
|---|---|---|
| Paid days | 26 | 22.9375 + 2 = 24.9375 |
| Regular salary | 270,000 × 26 = **7,020,000** | 270,000 × 24.9375 = **6,733,125** |
| Overtime base pay | 31,250 × 12 = 375,000 | 375,000 |
| Overtime premium pay | 31,250 × 10 = 312,500 | 312,500 |
| Time pay total | **7,707,500** | **7,420,625** (−286,875) |

Each late day costs (0.25 h late + 4 h band) / 8 = 0.53125 day = **143,437.5**. Premium pay stays tax-free, so
taxable income also falls by 286,875. For a monthly-paid person on 7,800,000/month (day rate 300,000) a late day
costs 159,375. If Q2 = "within the limit only", this example is unchanged at 4 h + 8 h *except* that the 4 h/day
limit splits the Sunday into 4 h paid + 4 h over-limit — today's limit applies to every overtime type.

## 5. Lateness (R10) with no double deduction

- **The only door:** paid normal hours. The rules never count late time as worked (`engine.py:28`, work starts at
  `max(first punch, shift start)`) and remove the band hours from worked normal time first (`engine.py:43-50`).
  `clock.worked_days` divides those paid hours by 8 ⇒ lateness reaches `VNREGULAR` once.
- **No deduction input.** `VNLATEMIN`/`VNACTUALHOURS` are information-only and refused in formulas (§3.4).
- **`pb_time_pay` cannot add a second one.** Its late-minute rung runs only in `_get_formula_input_values`, never on
  file runs (`pb_time_pay/models/hr_payslip.py:25`, ledger S5-1), and only for schemes with inputs coded `LATEMIN`
  /`EARLYMIN` or sourced `time.late_minutes`/`time.early_minutes` (`time_pay.py:67-71`). P10b guard: a scheme with
  `pb_clock_from` set may not hold such an input (refused on save and in the pre-run list:
  "Late minutes are already taken off through the late rules. Remove this column to avoid taking them off twice.").
  Follow-up (not P10b): the Close screen's late/early suggestions for people on an active rule set should say
  "already taken off by the late rules" instead of offering Confirm.
- **The file:** HR must not put lateness into any money column (e.g. Other deduction). Operational note in the
  readiness panel; not enforceable.

## 6. Pre-run check (December and later)

Must be true before computing (owner's order R9 plus what the code needs):

| # | Check | Today on sudima |
|---|---|---|
| 1 | Scheme 7844 active; people's contracts running | draft; 650 draft contracts (Q5) |
| 2 | Rules confirmed (policy active) | draft; worker 1–9 min band not confirmed |
| 3 | December roster published for every person in the run, 1–31 Dec, rest-day/holiday shifts where people work | drafts to 16 Dec; 27 people without rules; 134 without an inferred pattern (sudima-attendance README) |
| 4 | Clock-ins on; leading-zero matching live (§8) | off |
| 5 | Every shift calculated and current; every punch day has a shift; no attendance outside shifts | n/a |
| 6 | Every December overtime entry approved or turned down | n/a |
| 7 | Built-in extra hours off (§7) | on (default ruleset) |
| 8 | File: Sunday hours empty; leave column filled (Q1); no `LATEMIN`-type column | n/a |
| 9 | (Only if Q3 = yes) every person-week signed off — existing switch "Block the run until every week is approved" | off |

Screen behaviour: the run wizard's data step shows a **"Hours from the clocks"** panel (people ready / people
needing attention) once a clock-sourced scheme and a period on/after the date are chosen; Compute is refused with
one grouped list, e.g. "This pay run can't be worked out yet — 37 people need attention: Overtime waiting for a
decision (21) · Shift not worked out yet (9) · Punches on a day with no shift (5) · No shifts this month (2)", each
row naming the person and dates and linking to the roster / overtime / attendance screen. The payslip-level overlay
raises the same reasons (defence in depth). **Never a silent zero.** On a clock-sourced column the pay data template
header says "From the clocks — leave blank" and any number typed there is ignored and shown beside the clock value
("The pay file says 26; the clocks say 22.94 — the clocks are used"), not blocked.

## 7. Built-in extra hours (R12) — the on-screen way, proven by reading

- The stock attendance app counts extra hours whenever a person's **version** has an overtime ruleset
  (server `hr_attendance/models/hr_attendance.py:318-320`: `ruleset_sudo = version_sudo.ruleset_id; if ruleset_sudo:`)
  and then runs that ruleset's `rule_ids` (:331).
- **Archiving the ruleset is NOT enough**: a Many2one still returns an archived record, so `if ruleset_sudo` stays
  true and its rules still run. Rules have no `active` field (server `hr_attendance_overtime_rule.py`).
- **Clearing per person is not robust**: the employee form's "Overtime Ruleset" field edits only the current
  version (server `hr_employee.py:52`, related `version_id.ruleset_id`), and every new version/new hire gets the default
  ruleset again (`hr_version.py:17-23`). Sudima: 680 versions, 679 point at the Default Ruleset.
- **What works: remove both rules from the "Default Ruleset"** (Attendances › Configuration › Overtime Rulesets ›
  Default Ruleset › delete "Employee Schedule Rule" and "Non Working Days Rule" › Save). With no rules,
  `_get_overtime_undertime_intervals_by_employee_by_attendance` returns nothing (server
  `hr_attendance_overtime_rule.py:546-557`) ⇒ no extra-hours lines for anyone on sudima, new hires included. Both
  rules are `noupdate=1` data, so an upgrade does not re-create them. Today there are 0 lines to clean.
- Sudima settings of the two rules before removal (for an undo): rule 1 quantity / per day / expected hours from
  contract / paid / rate 1.0; rule 2 timing / per day / expected hours from contract / paid / rate 1.0.
- Not checked in a browser (read-only study): whether that stock menu (`menu_hr_attendance_overtime_rulesets`,
  active) is reachable from Payobook's navigation for a Sudima admin. **P10b gives it a screen twin** (owner rule):
  Workforce setup › Rules: "Built-in extra hours count: Off — overtime comes from your rules", which removes the
  rules of the company's ruleset(s) and stores their settings so "On" restores them. Run it before clock-ins go on.

## 8. Leading zeros (R8)

Three places compare clock numbers:
- `pb_clock/models/clock_pairing.py:229-253` `_code_index` — exact only, across `pb_clock_code`, `barcode`,
  `identification_id` (rank 0/1/2, active first).
- `pb_clock/models/clock_lens.py:640-650` (auto-assign of unmatched numbers) — exact only; `_suggest`
  (`clock_lens.py:414-432`) already offers leading-zero variants.
- `pb_attendance_policy/models/policy.py:286-302` — exact, then "no leading zeros" but only over `pb_clock_code` /
  `barcode`, and searches punches for `{code, stripped}` only (misses a clock that *adds* zeros).

Proposal: one stdlib helper `pb_clock/models/clock_code.py` `norm(code)` = trimmed; if all digits ⇒
`lstrip('0') or '0'`; otherwise unchanged. `_code_index`: exact pass first (unchanged), then a normalised pass for
codes without an exact hit, over the same three fields; exactly one person ⇒ match (punch note "matched ignoring
leading zeros"); two or more ⇒ stay unmatched and listed as "same number for two people" on the numbers screen,
never auto-picked. `clock_lens` auto-assign and `policy.py` peers call the same index; `policy.py` searches events
with the bounded variant set `{core} ∪ {'0'*k + core, k=1..4}` (the `_suggest` precedent). All sites.

Counts on sudima (connectors 4–8, the owner's connector 1 excluded):

| | Numbers | Records |
|---|---|---|
| Clock numbers seen | 663 | 60,219 |
| Exact match today | 578 | 54,396 (90.3 %) |
| **Match only after ignoring zeros, one person** | **60** | **5,519** ⇒ 99.5 % |
| **Two or more people after ignoring zeros (collisions)** | **0** | 0 |
| Exact match but another person equal after zeros | 0 | 0 |
| No match at all (Sudima must say who) | 25 | 304 |

People-side: 677 badge numbers (63 start with 0), 642 ID-card numbers (all start with 0, 12 digits), no
`pb_clock_code` set; **0 numbers shared by two people after stripping zeros** across all three fields. Unrelated
data note: 3 ID-card numbers are each on two people exactly (no clock sends them).

## 9. Test cases for P10b (numbered)

1. Neutrality: scheme without `pb_clock_from` and a period before the date ⇒ inputs + provenance byte-identical; clock branch counter 0.
2. Worked example §4.4 ⇒ `VNPAIDDAYS` 22.9375, `VNOTHOURS` 12, `VNPREMHOURS` 10, `VNREGULAR` 6,733,125; provenance via `clock`.
3. File carries 26 in I and 12 in L for a December period ⇒ clock values used, file values shown beside.
4. Period crossing the clock date ⇒ refused.
5. Draft overtime in the period ⇒ refused naming person/date; after approval ⇒ computes.
6. Refused overtime ⇒ 0 and not a blocker. Time-off-in-lieu overtime ⇒ excluded.
7. Shift with one punch ⇒ refused; zero punches ⇒ 0 and listed as absence.
8. Punches on a Sunday with no shift ⇒ refused; add a rest-day shift, recalculate ⇒ rest-day overtime at ×1.0 premium.
9. Attendance without a shift in the period ⇒ refused.
10. `VNSUNDAYHOURS` non-empty in a clock month ⇒ refused; `VNLEAVEDAYS` non-empty before the date ⇒ refused.
11. Formula referencing `VNACTUALHOURS` ⇒ save refused; scheme with clock date + `LATEMIN` input ⇒ refused.
12. Recalculate a shift after computing ⇒ approval refused until recompute (stamp).
13. 30 Nov shift excluded from December; 31 Dec night shift ending 1 Jan included in December.
14. Q2 both settings: over-limit hours in/out of `VNOTHOURS`, always in `VNOVERLIMIT`, never in both.
15. Leading zeros: "12" vs badge "012" matches; "12" vs "012" and "0012" on two people ⇒ unmatched + listed; exact still wins.
16. Built-in extra hours Off ⇒ creating policy attendance makes 0 `hr.attendance.overtime.line`; On restores.
17. Sep test cases (650) still pass after the formula change.
18. File-less Recompute of a December payslip still applies the clock values.

## 10. Open questions for the owner (plain English)

- **Q1 — Paid leave and public holidays.** The clocks only know days people worked. Today the pay spreadsheet's
  "paid days" also includes annual leave and public holidays, and Payobook holds no leave or holidays for Sudima.
  *Option A (recommended, nothing new for Sudima's HR):* add one column "Paid leave and holiday days" to the pay
  spreadsheet; pay = (days worked from the clocks + that column) × day rate. *Option B:* Sudima records every
  approved leave in Payobook and we add their public holidays to the work calendar; then the spreadsheet needs
  nothing. If neither is done, people on leave would be underpaid.
- **Q2 — Overtime above the legal limit.** Payobook splits approved overtime at 4 h a day and 40 h a month. In
  September 549 of 619 people with overtime went over 40 h (31.5 h over on average), and the pay sheet paid all of
  it as overtime. *Recommended:* pay all approved overtime as today and show the part above the limit separately.
  *Alternative:* pay only hours within the limit and let Sudima pay the rest some other way on the spreadsheet —
  this would cut pay for most workers unless they do.
- **Q3 — Weekly sign-off.** Should a December pay run wait until every person's weekly timesheet is signed off
  (about 2,900 a month, manager then HR lead), or is it enough that every overtime entry was approved or turned
  down? *Recommended:* overtime decisions only; turn on the weekly block later if wanted.
- **Q4 — 27 working days in December.** December has 27 Monday–Saturday days. With the divisor of 26, a
  monthly-paid person with perfect attendance gets 27/26 of their salary (about 4 % more). The September sheet does
  the same (paid days up to 29). Keep it, or cap monthly-paid people at one month's salary?
- **Q5 — Turning the scheme on.** Sudima's only pay scheme is still the draft "September review" copy and all 650
  contracts are drafts, so a December run would find nobody. Who confirms the scheme and contracts are ready to
  switch on, and by when?

## 11. Gotchas found (for the ledger)

- G1 `hr.overtime.request.rate_multiplier` is a *stored related* of the current OT rule — editing a rate rewrites
  every request's multiplier, approved ones included. Stamp it at pay time.
- G2 The OT limit counts every type, so a rest-day 8 h shift is split 4 + 4 by the daily limit; if night premium is
  ever switched on, night entries also eat the monthly limit although they are not extra hours.
- G3 Archiving the stock overtime ruleset does nothing (§7).
- G4 1 Dec 2026 is a Tuesday: any "week belongs to the month of its Monday" rule moves 1–6 Dec into November.
- G5 The rules engine only works out the last 35 days of published shifts whose capture window has ended
  (`policy.py:443-453`); a December run in early January is inside that window, a late correction may not be.
