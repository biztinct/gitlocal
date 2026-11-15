# WDGAP W2-A — report: running totals that follow the tax year (and are fast)

Branch `wdgap-w2a` from `origin/19.1` @ 4c9c82a40. Not merged, not deployed.
Handover: `WDGAP_W2_A_HANDOVER.md`. Ledger rows W2A-1 … W2A-8.

## 1. What was built

| Module | Version | What changed |
|---|---|---|
| `pb_hr_payroll_formula` | 19.0.1.166.0 → **19.0.1.167.0** | New stored field `hr.formula.config.tax_year_start_month` (Selection '1'..'12', "Tax year starts in", default January, tracked). ONE helper `models/tax_year.py`: `tax_year_key`, `tax_year_bounds(_for_key)`, `tax_year_label(_for_key)` ("2026" / "2026–27"), `tax_quarter_bounds`; scheme methods `_pb_tax_year_*` and month-based twins `_pb_tax_year_*_for` reached through the registry (no other module imports the file). Field shown on the scheme form next to the cycle AND on the application-sources form (the one the scheme action actually opens, W2A-7). R2: onchange warning "Year-to-date figures for this scheme will be counted from April from now on. Finished payslips are not changed." when finished payslips exist; nothing recomputed. Scheme settings follow no approval today (only `rule_ids` / money fields are gated, `scheme_gate.py`) — mirrored: a direct, tracked write. Engine source `history.ytd.<CODE>` counts from the scheme's tax-year start; new siblings `history.qtd.<CODE>` (quarter of the TAX year) and `history.mtd.<CODE>` (finished payslips of the same calendar month: its earlier periods, plus a finished payslip of the month that starts on or after this period — an Extra run reads the regular payslip). Catalogue words "Posted quarter-to-date: " / "Posted month-to-date: " (the existing English-only pattern). An Extra-run / top-up payslip counts once (W2A-3). Batch read: one search (as the caller — rights, record rules, explicit company) + one column read per chunk of people on the request memo; prefetch hint from compute, preflight, preparation and the approval check. Final-tax-month reminder (payroll preparation) follows the tax year ('year_end' + the month's name when it is not December). vi_VN. |
| `pb_updates` | 19.0.1.7.4 → **19.0.1.8.0** | `_plan_for_slip`, its ledger window, joined-this-year (D31) and the usual-sign sample (`_conventions`) use the tax year of the scheme concerned. A figure row stores `tax_year_start_month` only when its tax year does not start in January; old rows store nothing and keep their calendar meaning; `tax_year_label` is computed (no migration). The sheet (per person, by their own scheme via the scheme map, else their latest payslip's scheme), the home tile, the cover-date check, the year-to-date view and its downloads name and pick "this tax year" of the companies' schemes (January when they differ). Year buttons show labels ("2026–27"); "Last year" picks the tax year's last day. No scheme-map lookup and no extra reads while every scheme is on January. vi + id. |
| `pb_me_portal` | 19.0.3.6.1 → **19.0.3.7.0** | `/my/taxsheet` sums the current tax year of the most recent payslip's scheme; tile "Tax year 2026–27" (January keeps "YTD 2026"). No year switcher (none existed). vi + id. |

## 2. Tests

New: `pb_hr_payroll_formula/tests/test_wdgap_w2a_tax_year.py` (12) and
`pb_updates/tests/test_wdgap_w2a_tax_year.py` (9, two of them HTTP).

| # | Case | Result |
|---|---|---|
| T1 | Helper bounds, months 1/4/7 (and 3), leap years (29 Feb 2028), day before/after the start, labels incl. "1999–00", tax quarters, unreadable month = January, new scheme defaults to January | pass |
| T2 | April–March scheme across March/April: 1 Mar → gap (not known), 1 Apr → 0, 1 May → April only (400), 1 Jun → 900; calendar scheme same months 1,500; qtd of the tax year; mtd 0 for a regular month, 500 for an Extra run of May | pass |
| T2b | mtd for a second half-month; a gap inside the month is not known | pass |
| T3 | Extra run (Feb) + top-up (Mar) counted once: 3,300 (old reader: conflict); a second REGULAR payslip for one month still stops | pass |
| T4 | Gap → not known; D27 blank joining date → the sentence; joined on the tax year's first day → 0; missing component → not available | pass |
| T5 | **R1 golden**: 60 people × 4 period starts × 3 codes = 720 answers, batch reader == old per-person reader (kept in the test as the oracle), byte-identical as JSON and same evidence key order; every outcome kind exercised; outside a memo too; the record-context fact equals the oracle | pass |
| T6 | R2 warning text, onchange shows it, nothing recomputed, Vietnamese served | pass |
| T7 | R4: a mid-year move to another-currency scheme → gap, never added | pass |
| T8 | R5: another company's payslip never read; a login without payroll rights gets the same answer from batch and oracle (and not the total) | pass |
| T9 | Catalogue offers ytd/qtd/mtd with the established words | pass |
| T10 | Final tax month: December (calendar), March (April scheme) | pass |
| T11 | Timing (below) | pass |
| U1 | Sheet rows carry their tax year: April person 2026 + month 4 ("2026–27"); January person 2026, no month | pass |
| U2 | Updates plan under April start: 300,000 before + Jul–Oct 400,000 = 700,000; tax 70,000; Mar 2027 = same tax year with the gap months named; Apr 2027 = new year, nothing | pass |
| U3 | Joined May 2026 (April scheme) = joiner, 300,000; joined Feb 2026 = last tax year, nothing for Nov, joiner for March | pass |
| U4 | A calendar row never feeds an April scheme | pass |
| U5 | Year-to-date view reads each person's own tax year | pass |
| U6 | R1 January everywhere: home (this/last year, min/max, default), cover-check sentence word for word, view, old rows' label; no scheme-map lookup | pass |
| U7a | Tax summary opening figures follow the page's tax year | pass |
| U7 / U7b | HTTP: April employee page "Tax year 2026–27", totals Apr+May (9,000); January page "YTD 2026", totals Jan–May (15,000) | pass |

**Full suites** (`/pb_hr_payroll_formula,/pb_updates,/pb_me_portal`, fresh copies of `upd_p6_t_tpl`):

| Run | Tests | Failed | Errors |
|---|---|---|---|
| Baseline (`origin/19.1` copies of the 3 modules first on the path) | 1,029 | 7 | 2 |
| W2-A | **1,050** (+21 new) | 7 | 2 |

The failure set is identical and is the known baseline (PR-A / PR-C / PR-D reports):
TestRd49SyncCost ×2, TestRecordsR1OneTime 07b, TestSchemeCtxCurrency 04, pb_me_portal ×5
(TestMeHomeCards 05/06, TestMeHomeSource 12, TestPortalOnlyDoors t1_7, TestPbMePortal 01).

(The field was added to the application-sources form after the full run, during the walk; that
one-line view change was loaded by a clean `-u` of the walk copy and seen on screen.)

Static gates: JS parses (3 files), XML well-formed, pyflakes clean on new code, PO files parse with
the framework's own reader (`scratchpad/w2a/pogate.py`) and every new msgid reaches a row with its
marker; no "Odoo" in any new user-visible string.

## 3. R1 / R6 proof

- **R1 (January = byte-identical)**: T5 (720 answers equal to the old reader, as JSON); U6 (desk
  answers word for word); U7b (tax sheet totals and tile); the unchanged UPDATES P5/P5b/P5c/P5d/P5e
  suites (hand-worked year-to-date and plan figures) all pass. The only January answer that changes
  is deliberate: an Extra-run/top-up payslip in the range used to stop the total; it now counts once (W2A-3).
- **R6 (demo runs)**: the demo regular path is untouched by design (it never reads `history.*`;
  `_plan_for_slip` returns at once with no mapping — no database has one). Proof run: the demo
  division path's golden test (`pb_demo` TestDemoExtraRun, regular ₫9,900,000 / ₫20,000,000) with
  `-i pb_demo` passes on base AND on W2-A (5/5 both). The real 47-run demo world could not be copied
  locally (2–5 GB free, its template is pre-PR-A, W2A-5) — **the deploy rehearsal on a live clone
  must recompute one regular demo run per demo scheme before/after**.

## 4. Timing — 40-person chunk (T11, 40 people × 10 finished months × 2 components)

| Reader | Time | Queries |
|---|---|---|
| Old (one search per person and component) | 1.75 s | 163 |
| Batch (one search + one column read per chunk) | 1.02 s | 45 |

## 5. Browser walk (local copy, 127.0.0.1)

Scheme form → "Tax year starts in" January → April: the plain warning appears; saved. Updates ›
Year-to-date figures before Payobook: buttons "2026–27 / 2025–26", sentence "from the start of the tax
year to 31 Oct 2026"; "2025–26" picks 31/03/2026. Year-to-date view 2026–27: April + May only (49,000,000,
2 months); 2025–26: Jan–Mar "known so far" with "Not covered: April 2025 to December 2025". Employee
login → My Payobook › Tax sheet: tiles "Tax year 2026–27", 49,000,000; the Vietnamese page serves
"Năm tính thuế 2026–27". Console: no errors on any page.

## 6. Reports that still mean the CALENDAR year (owner follow-up, not changed)

1. Insights (Explorer) periods "This year / Last year" — the group's FINANCIAL year (`pb_group.fiscal_start_month`), and the "year" grain groups by calendar year.
2. Pay run board filter "This year" — calendar year.
3. Compliance › tax tables "This year" filter — calendar year.
4. Pay calendar board (`pb_comp_ben` paycal) — calendar year.
5. Guided setup's manual `<CODE>YTD` input convention (U42) — a typed input, no date logic.
6. The Formula Studio scheme panel does not show the new setting (another builder is in that module); it is on the scheme forms.

## 7. Owner questions (plain words)

1. **One company, two tax years?** If a company has schemes that start their tax year in different
   months, the Updates screens count "this tax year" as the calendar year, while each person's own
   figures follow their scheme. Is that acceptable, or should mixed set-ups be refused?
2. **Should the Formula Studio scheme panel show "Tax year starts in"** next to the cycle (a small
   change in the Studio module, which another builder holds today)?
3. **Guided setup for India**: leave new Indian schemes on January (as now, packs untouched), or start them in April?

## 8. Deploy notes — RISKY tier (pay calculation inputs; new stored fields)

- `-u pb_hr_payroll_formula,pb_updates,pb_me_portal` on all five. New columns:
  `hr_formula_config.tax_year_start_month` (filled '1' by the default), `pb_updates_ytd_line.tax_year_start_month`
  (left empty — nothing migrated). Expect the 3 PRM-4 `payroll_analytics` ERROR lines.
- JS/XML assets changed in `pb_updates` (asset purge + version bump) and a portal template in `pb_me_portal`.
- Rehearse on a live clone (jobs and mail off): every scheme reads January after the upgrade;
  application-data drafts computed before the deploy still pass approval (fingerprints unchanged, T5);
  recompute one regular demo run per demo scheme before/after (R6); open a rize ID pay run's year-to-date inputs.
- Nothing changes on screen until somebody picks another month on a scheme.

## 9. Gotchas → ledger

W2A-1 (name collision in `_ytd_rows`), W2A-2 (fingerprint = whole answer), W2A-3 (Extra/top-up counted
once), W2A-4 (`not in` keeps old NULL rows), W2A-5 (disk; R6 on a clone), W2A-6 (localhost cookies
shared between parallel walk servers), W2A-7 (the scheme action opens the application-sources form),
W2A-8 (Chrome auto-translation hides the Vietnamese page).
