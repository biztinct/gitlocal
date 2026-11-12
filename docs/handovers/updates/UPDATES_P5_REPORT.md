# UPDATES — Phase 5 report (year-to-date figures before Payobook, D20)

Implemented, tested, deployed and checked on 2026-11-12/13 by the Opus implementation agent,
against `UPDATES_P5_HANDOVER.md` and `UPDATES_LEDGER.md`. Numbering: D20 was free; the handover's
facts went in as **U40–U44** (U45 was taken by P6); new gotchas are **G65–G70**.

R0 below was written BEFORE the deploy, as the handover asks.

## R0. Rollback note (written before deploying)

- **What the deploy changes.** `pb_updates` 19.0.1.6.0 → **19.0.1.7.0** on all five databases
  (`payobook`, `payobook_template`, `p0clone`, `rize`, `sudima`). New dependency `pb_me_portal`
  (installed on all five, 19.0.3.5.3; not edited). Five new tables (`pb_updates_ytd_line`,
  `pb_updates_ytd_figure`, `pb_updates_ytd_map`, `pb_updates_ytd_use`, `pb_updates_ytd_ask`), one
  new column on `pb_updates_batch` (`ytd_covers_to`), one on `pb_records_apply` (`updates_ytd`),
  five record rules, one QWeb view inheriting the employee tax sheet
  (`pb_updates.portal_my_taxsheet_ytd`), selection value `ytd` on the batch/layout kind. No data
  is written by the upgrade; no scheduled job; no mail.
- **Files:** the previous `pb_updates` tree (19.0.1.6.0, git `c729509f6`) is kept as
  `/odoo/backups/updates-p5-<TS>/pb_updates.prev`. Restore = scoped
  `rsync -a --delete pb_updates.prev/ /odoo/odoo-server/addons/pb_updates/`, `-u pb_updates` on the
  five databases (the old manifest drops the `pb_me_portal` dependency and the tax-sheet view is
  removed by the upgrade), asset signal + purge + version bump, restart.
- **Data:** five dumps `/odoo/backups/updates-p5-<TS>/<db>.pre-updates-p5.dump`, taken before the
  service stops.
- **What a files-only rollback leaves behind:** the five tables and two columns (an old registry
  ignores them). With no mapping (`pb_updates_ytd_map` empty — true on every database at deploy)
  nothing reads them in any pay run, so a rollback cannot change any payslip. If a year-to-date
  update is **waiting for approval**, withdraw it first (Updates home → Withdraw): the old code
  would try to write its empty plan as a records change on approval (nothing would be written).
- Nothing on `rize` or `sudima` is mapped, loaded or changed by this phase.

---

## R1. What shipped

| Module | Version | Where | What |
|---|---|---|---|
| `pb_updates` | 19.0.1.6.0 → **19.0.1.7.0** | upgraded on all five | the fourth kind of sheet, the store and its approval adapter, the year-to-date view and its downloads, the set-up, the guarded pay-run delivery, the employee tax summary override, the P6 "way out" links on the Updates screens |

Nothing else changed. `pb_me_portal` (the employee tax sheet) is a new dependency and is NOT
edited: the override is a controller subclass + one inherited QWeb view in `pb_updates`
(`controllers/ytd_portal.py`, `views/ytd_portal.xml`). An untracked `pb_me_portal/i18n/id_ID.po`
belongs to another session; it was not touched, staged or deployed. No file in `pb_lifecycle`,
`pb_hiring`, `pb_me_expense`, `pb_timeoff`, `pb_approval_config` or `docs/handovers/workflow2` was
edited. `pb_hr_payroll_formula`, `pb_payrun_wizard`, `pb_payroll_templates` untouched: every pay-run
seam is an override in `pb_updates`. No tax formula, bracket table, country pack or scheme rule
changed; no new application-data source key; no "opening payslip".

New files: `models/updates_ytd.py` (store, figures, mappings, uses, questions, approval adapter,
the numbers), `models/updates_ytd_payrun.py` (seams, wrappers, D11), `models/updates_ytd_desk.py`
(screens, view, downloads, set-up), `controllers/ytd_portal.py`, `views/ytd_portal.xml`,
`static/src/js/updates_ytd.js`, `static/src/xml/updates_ytd.xml`, `tests/test_updates_p5.py`.
Edited: `updates_lanes.py` (way out), the desk JS/XML/SCSS (fourth kind), `updates_review.js`
(grid words), security CSV + rules, manifest, `vi_VN.po` (+264, append only).

## R2. How it works (plain)

- **Store** `pb.updates.ytd.line`: person, tax year (the year of "Figures cover up to"), figure,
  amount, covers-to date, Source note, the named update; states waiting / set / replaced / cleared /
  undone / refused / cancelled / returned / rejected. One `set` row per person + tax year + figure
  (partial unique index). Access only through the screens' methods (read-only rights for payroll
  officers, company rules).
- **Figures**: gross pay, taxable pay, income tax withheld, employee social contributions, employer
  social contributions, months counted — plus any pay item a payroll manager names as a figure
  (key = its code). "Paid in Payobook" for a fixed figure adds up the pay items chosen in Set up;
  default = the known codes the company's tax summary shows or its schemes have (payobook: GROSS,
  TXBASE, PIT, SIEMP+HIEMP+UIEMP, SICOMP+HICOMP+UICOMP).
- **Sheet**: Start → tax year (this/last) + "Figures cover up to" → download (people × figures +
  Source, existing figures shaded, Read me) or own file → Match → Review (one verdict, `_ytd_cell`:
  not a number, negative, months not a whole number 0–12, more than two decimals, waiting in another
  update, used by a finished pay run, CLEAR) → Apply. A person who joined after the date gets an
  amber "Joined after this date" tag (allowed). Approval: the update's ONE `pb.records.apply`
  (`updates_ytd`), records (pay) route; approving it sets the rows (a later sheet replaces, CLEAR
  removes, a figure a finished payslip used is refused with "… was used in pay run X. It can no
  longer be changed here."). Undo takes back what this update set and brings back what it replaced,
  unless a finished payslip used it.
- **View** (Updates home → "Year-to-date figures"): per person and figure Total, with Before Payobook
  + Paid in Payobook under it; people with figures first; "N months missing" chip; search; 50 per
  page; Download (one row per person, three columns per figure); "Download for the pay run".
- **Delivery** only through `pb.updates.ytd.map` (scheme + input pay item + figure + "Before Payobook
  only" / "Total so far this year, before this pay period" / "Months so far this year, including
  this pay period"). Seam 1 (no file): fills the item only when no other source does. Seam 2 (pay
  data file, monthly workbook): a NUMBER in the file that differs → the run stops and asks (D11),
  same buttons as one-offs (Run Payroll review step + Updates home card, ids `y:<n>`); equal → once.
  The value and both parts go in the payslip's input sources (`via: updates_ytd`, `ytd: {before,
  paid, …}`); the payslip holds the figure (`pb.updates.ytd.use`), locked when finished, released
  when cancelled/deleted. If a month between the figures and the pay period has no finished payslip,
  or none of the person's finished payslips carries the figure's pay items, the payslip is refused
  with a sentence — never a silent before-only or 0.
- **Application-data runs**: nothing delivered (seam 1 returns at once in that mode, as P2d).
  "Download for the pay run" gives the mapped items' values for a chosen pay period: a wide sheet,
  plus a "Monthly adjustments" tab whose columns the Monthly adjustments list imports as they are
  (`employee_id/.id`, `config_id/.id`, `component_id/.id`, dates, value, unit, reason, evidence —
  checked: 11 rows imported as drafts on a copy). Each row still needs approving there, as today.
- **Employee tax summary** (`/my/taxsheet`): for a figure that is exactly one code the summary
  shows (GROSS, PIT), the amount is added to that code's year total and listed in an extra row
  "Before Payobook (up to <date>)", tiles say "Includes before Payobook"; a figure of several codes
  (employee social contributions = SI+HI+UI) is listed under the table, never split. People without
  figures see the page exactly as before. Signs follow the summary (a deduction stored negative
  stays negative).
- **Way out (P6 deviation 1)**: under "Nobody else in <company> can approve bank details yet — add
  one in Access" (and its named-route twin) on the Apply step, the Done screen and Past updates:
  "Give someone a role in Access" / "Name a Finance approver" / "Add a person to the bank details
  route" — only for people who can use them (the inbox's own helper `_second_person_fix` for a
  request; the same two gates before anything is sent), else "Only your administrator can add
  someone who may approve bank details. Ask them to add one — they can then try this again from
  here."

## R3. Tests Y1–Y12

New file `pb_updates/tests/test_updates_p5.py` — 21 cases in three classes (`TestUpdatesP5`, "No
approval needed"; `TestUpdatesP5Route`, a real HR-lead route; `TestUpdatesP5WayOut`). A company of
its own in Ho Chi Minh City, today frozen at 12 Nov 2026; scheme "P5 Monthly" with GROSS/PIT inputs
(defaults, so every payslip carries those lines) and four inputs that receive figures only when
mapped; Ann and Bob with a FINISHED October payslip, Cal with none.

| # | Case | Result |
|---|---|---|
| Y1 | `test_Y1_sheet_review_approve_replace_clear_undo` — "125,000" read as 125,000; 6 figures set at once; Source kept; sent back unchanged = `same`, 0 changes; 125,000 → 130,000 shows old → new, old row `replaced`; CLEAR removes Bob's; undo of the clear brings Bob's back, undo of the replace brings 125,000 back; Past updates kind/state. `test_Y1b_…` — download (headings, Read me says nothing changes tax, no "Odoo"), read back as our sheet with its date, sent straight back = 0 changes; a draft of this kind saved, listed with its date, discarded | PASS |
| Y2 | `test_Y2_bad_cells_and_dates` — "abc", 13 months, −5, 2.5 months, three decimals refused with sentences; dates outside this/last year or blank refused; joined after the date → amber tag, still `ok`; −3 sent past the screen refused by the server | PASS |
| Y3 | `TestUpdatesP5Route` — outlook names the HR lead; approve (drawer title "Year-to-date figures before Payobook", headline "Year-to-date figures for 2026…", rows `set`); send back / turn down / cancel → rows `returned` / `rejected` / `cancelled`, nothing set | PASS |
| Y4 | `test_Y4_view_…` — Ann gross 125,000 + 1,000 (October line) = 126,000; tax 12,000 + 100; months 9 + 1 = 10; a pay item named as a figure summed by its own code; December finished and November not → "1 month missing", paid 2,000; download headings | PASS |
| Y5 | `test_Y5_employee_tax_summary` — GROSS 1,000 → 126,000, PIT 100 → 12,100, extra row title "Before Payobook (up to 30 Sep 2026)"; a several-code figure listed apart, not split; a person without figures: page values unchanged; the view carries the row | PASS |
| Y6 | `test_Y6_…` no-file run: mapped items receive 126,000 (125,000 + 1,000), 11 months (9 + October + this period), 12,000 (before only); sources record both parts, `via updates_ytd`; 3 uses `in_run`; recalculate: still once. `Y6b` — December with November missing: refused "…no finished payslip for November 2026…". `Y6c` — pay data file without the column: 126,000 from Updates; monthly template file: the filler 0 is a blank → 126,000. `Y6d` — figure whose pay items are on none of the payslips: refused "…has the pay items that make up Taxable pay…"; "Before Payobook only" works | PASS |
| Y7 | `test_Y7_…` file 999 vs 126,000 → no payslip from the file for Ann, question stored (`y:` id) and shown on the Run Payroll review step and the Updates home; Bob's equal 81,000 → once, no question; "Use the Updates amount" → 126,000 with the file's 999 as the ignored side. `Y7b` — "Use the file's amount" → 999, no figure held. `Y7c` — an open question blocks finishing her payslip | PASS |
| Y8 | `test_Y8_…` finished payslip → use `used`; a new value and CLEAR refused "…was used in pay run P5 November…"; undo keeps it ("…so it stays"); payslip cancelled → released, a new value accepted | PASS |
| Y9 | In suite `test_Y9_…`: mapping and no figures, figures and no mapping → inputs and sources identical to the plain payslip. **Out of suite on a fresh read-only copy of live payobook** (Retail end-month, 12 people, December 2026; `y9_capture.py` = P2d's E1): pre-phase code vs new code vs new code **with two mappings on that scheme and figures for 8 other people and for these 12 in 2025** — **6 of 6 identical in all three**: no-file compute/recompute `4ecfc38110407470`, pay-file create/recompute `d88c66c183d0edd1`, template create/recompute `f9755a528c321347` (the same hashes P2d recorded) | PASS |
| Y10 | `test_Y10_…` application-data context: nothing delivered; "Download for the pay run": `Gross so far (P5GROSSYTD)` 126,000, months 11, Cal's Check names the missing months; Monthly adjustments tab has the import columns and 2 rows for Ann | PASS |
| Y11 | Earlier kinds: local isolated tree (G13: HEAD snapshot + this module) on a copy of the live template's shape, `-u pb_records,pb_updates,pb_import_advanced`: **pb_records 134 + pb_updates 230, 0 failed** (twice). Live p0clone after start: same, 0 failed (R5). Speed: R4 | PASS |
| Y12 | `.po`: built from `odoo-bin i18n export -l pot` (G2/G6); 264 new entries appended (existing file byte-identical as a prefix), `PoFileReader` 1,391 rows, 0 untranslated, placeholders checked per entry, 0 "Odoo" in any msgstr; split template sentences rewritten as whole sentences first; `test_Y12_no_vendor_name_in_new_strings`; the four other modules' model names the exporter lists are left untranslated (as P3a/P4) | PASS |
| — | `test_setup_needs_a_payroll_manager` (officer can see, not map; HR without payroll: no tile, refused) and `TestUpdatesP5WayOut` (admin gets links, a plain user the sentence, route twin) | PASS |

## R4. Timings

Fresh read-only copy of live payobook (4,575 people), local, uid 2:

| Step | Pre-phase (P4 report) | This phase | Target |
|---|---|---|---|
| Lasting sheet, 73 columns | 18.9 s / 12.0 s | 11.6 s / 11.9 s | — |
| **Review 4,575 × 73** | 14.1 s / 13.3 s | **13.6 s / 12.0 s** | ≤ 25 s ✔ |
| Answer | 0 changes, 60,075 same, 1,499 unmatched | 0 changes, 60,083 same, 1,499 unmatched | — |
| Year-to-date sheet, whole roster (4,547 people) | — | 1.5 s (live payobook 1.7 s) | — |
| Year-to-date read / review, whole roster | — | 0.3 s / 1.2 s (live 2.1 s) | — |
| Year-to-date view, first page / whole download | — | 0.7 s (live 1.1 s) / 8.2 s (4,477 people) | — |
| Updates home | — | 0.7 s | — |

A pay run with no mapping pays one cached query per scheme (per transaction) and a string check of
each payslip's sources; Y9 shows the results unchanged.

## R5. Browser walk and screenshots

My own local server on a fresh copy of live payobook (127.0.0.1:8797, jobs and mail off), company
Payobook Vietnam JSC, console read at every step: **0 errors**. Screenshots in `outputs/updates-p5/`
(not committed). Local-only set-up, said here: a local password for the admin login; three input
items on the Retail end-month scheme ("Taxable pay so far", "Tax withheld so far", "Months so far");
six Retail people given codes WALKY1–6; one demo self-service login (DEMO Nguyen Van An) given a
local password.

1. `01-home-five-tiles` — the fifth tile and the "Year-to-date figures" door (tiles now fit five
   across).
2. `02-start-ytd-kind` — four kinds, the tax year switch (2026/2025), "Figures cover up to", the
   figure chips, "Nothing here changes how tax is calculated."
3. `03-match-columns` — own headings ("YTD gross", "PIT withheld so far", "Months worked", "Where
   from") matched; kinds "Year-to-date figure" / "Kept with the figures".
4. `04-review-refusals`, `05-fixed-totals` — "This sheet sets 21 year-to-date figures for 6 people:
   tax year 2026, before Payobook up to 31 Mar 2026. 3 cells need your attention."; totals per
   column; −5000 fixed on screen to 95,000,000 → totals update.
5. `06-apply-card`, `07-done`, `08-home-past-update` — totals card, "Set now: your company needs no
   approval for these.", "Set 22 figures", Done with "See the year-to-date figures", Past updates row.
6. `09-ytd-view` — people with figures first, Total over Before + Paid; demo payslips carry no
   taxable base, so Taxable pay "paid" shows "—" (G66).
7. `13-setup-send-to-pay-run` — Set up: "Paid in Payobook adds up", pay items as figures, "Send to a
   pay run" per scheme with three mappings on Retail end-month.
8. `10-clash-card` — a pay-file run for August (staged server-side, a file with 12,345 for one
   person): "A pay run found two amounts for one pay item … From Updates 81,000,000 ₫ or In the pay
   data file 12,345 ₫" with the two buttons; the person with the equal number got it once; the others
   received before + paid with both parts in their sources.
9. `12-download-for-pay-run` — the Retail scheme, August 2026, message names how many values cannot
   be worked out yet (the Check column).
10. `11-employee-tax-summary` — /my/taxsheet as the demo self-service person: GROSS and PIT tiles
    "Includes before Payobook", the row "Before Payobook (up to 31 Mar 2026)", employee social
    contributions listed apart.
11. `14-way-out-apply-step`, `15-way-out-done` — on the P6 walk copy (Finance seat emptied locally):
    the tenant admin's bank change shows "Waiting for a second person. Nobody else in P6 Walk Co can
    approve bank details yet — add one in Access." with **Give someone a role in Access** (that admin
    has Access but not approvals set-up on that copy, so the Finance link is rightly absent); the link
    opens Access. The plain sentence for someone with neither: test `TestUpdatesP5WayOut`.
12. `16-live-payobook-ytd-view` — live payobook.com, look only, an existing session: the view;
    console 0 errors.

Found and fixed on the walk: five tiles wrapped to a lonely fifth row; deductions summed as minus
amounts (G67); a code no payslip carries counted as a confident 0 (G66 — now "—" and a refusal in a
pay run); a choice reported the Updates amount when the payslip kept the file's number (now reads the
payslip back); the "Waiting for a pay run" card's one-off sentence over a year-to-date question;
the toast named a pay item by its code; the mapping row and pay-run pickers stretched.

## R6. Rize Indonesia — how December takes its year-to-date inputs, and the exact steps (read only)

Checked read-only on live `rize` on 2026-11-12 (psql and one rolled-back `odoo-bin shell`, log
`/tmp/p5_ev/rize_ro.log` on the server). Nothing was mapped, loaded or changed on rize.

| What | Finding |
|---|---|
| Scheme Indonesia's people are paid under | **"Rize Indonesia Payroll — focused payroll"** (id 7121): the scheme map sends all **126** Indonesia people there for December. Active, and **runs from application data** (switched on). Two older Indonesia schemes exist (7096 archived, 7116 draft); nobody resolves to them. |
| The final-period items | All on 7121 as items the pay run fills in, each with a reviewed monthly-adjustment source (`period.input.<code>`) and, for a run with a pay data file, its column: BB **Final tax period** (`IDFINALTAXPERI`), BC **Prior YTD taxable gross** (`IDPRIORYTDTAXA`), BD **Prior YTD deductible JHT and JP** (`IDPRIOYTDJHTJP`), BE **Job expense eligible months** (`IDJOBEXPENELIG`), BF **Prior YTD PPh21 withheld** (`IDPRIOYTDPPH21`), NF **Final-period YTD reviewed** (`IDYTDREVIEW`); also NE **Approved final-period tax allowance** and BW **Prior severance tax withheld**. All default to 0. |
| The pay items behind them | a month's taxable gross: **Total income** (`IDTOTALINCOME`); employee JHT: **Old age employee** (`IDOLDAGEEMP`); employee pension (JP): **Pension employee** (`IDPENSIONEMP`); PPh21: **Payable tax** (`PIT`). Employee BPJS health (`IDBPJSHEALTEMP`) is not part of BD. |
| How Rize's runs work | No finished payslip on rize yet (487 drafts). Only TEST runs for August 2026 (one "application inputs without Excel" and one "monthly Excel import" per country). Indonesia's "Review pay data" sheet (application data only) exists for August (sealed) and October (drafts). |
| Monthly adjustments today | 0 for Indonesia. |
| The engine's own year-to-date source | Not used by 7121 (no item reads `history.ytd.*`). |
| Joining dates | All 126 Indonesia people have **no joining date** on their record; 19 have no contract. |
| Tax summary codes | `GROSS,SIEMP,HIEMP,UIEMP,PIT` (the default). |

**Route: "Download for the pay run".** The Indonesia scheme runs from application data and those
runs certify their inputs, so Updates never feeds them. December's BC/BD/BE/BF go in as monthly
adjustments, as they would today — but worked out by Payobook instead of typed. (If Rize ever runs
December with a monthly pay data file instead, the direct route applies: the run fills those items by
itself and stops and asks where the file has a different number.)

**December steps for an administrator** (plain words, ready to hand to the owner):

1. **Load what was paid before Payobook.** People › Updates → New update → "Year-to-date figures
   before Payobook". Tax year 2026. "Figures cover up to" = the last day before Rize's first
   Indonesia pay period paid on Payobook (for example 31 October 2026 if November is the first).
   Download the sheet and fill, per person, from the old payroll's year-to-date report: **Taxable
   pay** (taxable gross, without qualifying severance), **Employee social contributions** (only the
   deductible employee JHT + pension — not BPJS health), **Income tax withheld** (PPh21), **Months
   counted** (job-expense months so far); put the report's name in Source. Send it; once approved,
   the figures show on the Year-to-date figures screen and on each person's tax summary.
2. **Say which pay items count as "paid in Payobook"** (Year-to-date figures → Set up, once):
   Taxable pay ← "Total income"; Employee social contributions ← "Old age employee" and "Pension
   employee" (remove the Vietnamese defaults only if Vietnam's people should not count — each person's
   payslips only carry their own country's items, so leaving them does no harm); Income tax withheld
   ← "Payable tax".
3. **Choose which pay item receives which figure** (same Set up, scheme "Rize Indonesia Payroll —
   focused payroll"): Prior YTD taxable gross ← Taxable pay · "Total so far this year, before this
   pay period"; Prior YTD deductible JHT and JP ← Employee social contributions · same; Prior YTD
   PPh21 withheld ← Income tax withheld · same; Job expense eligible months ← Months counted ·
   "Months so far this year, including this pay period".
4. **Finish every Payobook month in between.** Every month from the figures' date to November must
   be a finished pay run; the Year-to-date figures screen shows "months missing" for anyone with a
   gap.
5. **Download for the pay run**: Year-to-date figures → "Download for the pay run" → that scheme,
   pay period December 2026. The "Check" column says Ready, or what cannot be worked out yet. The
   "Monthly adjustments" tab has one row per person and item: import it on the Monthly adjustments
   list (Payroll), then approve the rows there as today.
6. **Enter the other final-period items as today**: Final tax period = 1, Final-period YTD reviewed =
   1 after checking, the approved final-period tax allowance where it applies.
7. Run December from application data as usual. The scheme's own December formula does the annual
   tax with these inputs exactly as it would with typed ones — no tax rule was changed.

## R7. The silent-zero finding (`_application_history_value`) — not fixed, as instructed

`pb_hr_payroll_formula/models/application_domain_sources.py:476-518`. The engine's own
`history.ytd.<CODE>` source (application-data runs) takes the person's start as
`employee.date_of_joining or contract.date_start` (`:481`). When the joining date is blank and the
contract starts on the first day of the pay period being run — the normal shape of a client that
migrated mid-year with contracts created at go-live — `lower >= start` and it answers
**`0.0 zero_confirmed`, "no prior service days this year"** (`:485-486`): a confident zero for
everything paid before Payobook, which a December reconciliation would then trust. Read-only probe
on rize: for an Indonesia person (no joining date, contract from 2024-07-01) the source answers
`missing / posted_history_or_opening_balances_missing` for December (correct), and
`0.0 / zero_confirmed` when asked for the period starting on the contract start (the trap). All 126
Indonesia people on rize have no joining date; none of 7121's items reads this source today, so
nothing on rize is affected now.

**Proposed fix (for the engine's owner, not done):** only treat "no earlier service" as a confirmed
zero when the start is a real joining date; when it is only the contract start, answer `missing`
with a new reason (e.g. `employment_start_unconfirmed_for_history`) unless year-to-date figures
before Payobook cover that period:

```python
joined = employee.date_of_joining
start_known = bool(joined)
joined = joined or (contract.date_start if contract else False)
...
if lower >= start:
    if not start_known:
        return source_result(reason='employment_start_unconfirmed_for_history')
    return source_result(0.0, 'zero_confirmed', reason='no_prior_service_days_this_year')
```

**Failing test sketch (fails today):**

```python
def test_history_ytd_blank_joining_is_not_a_confirmed_zero(self):
    emp = self.env['hr.employee'].create({'name': 'Mid-year arrival', 'company_id': self.company.id})
    contract = self._contract(emp, date_start='2026-11-01')   # created at go-live
    res = self.config._application_history_value(
        'history.ytd.GROSS', emp, contract, date(2026, 11, 1))
    self.assertNotEqual(res['status'], 'zero_confirmed')       # today: 0.0 zero_confirmed
```

## R8. Deploy evidence (five databases)

Unit `updates-p5-20261112T131152Z` under `flock /tmp/payobook-studio-deploy.lock` (free; the
WORKFLOW-2 P5b deploy had finished at 12:24 UTC). START 13:11 / DONE line in `/opt/deploy-notes.md`.
Evidence `/tmp/updates-p5-20261112T131152Z/` on the server. Tier 3.

- Before: the server's `pb_updates` tree = pre-phase commit `c729509f6` (`f6b79563672fdc1d`); staged
  tree = repo `97273a46c` (`85b897fb642edd66`). Clean staging folder, per-module scoped rsync of
  `pb_updates` only; no standard addon, no other module.
- **Backups, before the stop**: `/odoo/backups/updates-p5-20261112T131152Z/` — payobook 79,331,322 B,
  payobook_template 27,891,056, p0clone 28,228,945, rize 41,591,475, sudima 27,832,831
  (`*.pre-updates-p5.dump`), plus `pb_updates.prev`. Nightly backups untouched.
- `-u pb_updates` on all five: EXIT=0, **0 ERROR/CRITICAL** in every upgrade log.
- **Downtime 93 s** (13:12:59–13:14:32 UTC), serving again at 13:14:41. **No test in the stopped
  window** (G19).
- Active scheduled jobs: identical id lists before/after — 50 / 32 / 39 / 82 / 81; nothing
  re-activated, nothing lost, no new job.
- Assets: signal row + `/web/assets/%` purge + `web.assets.version` bump on all five.
- Users, payslips (count + id/state/inputs hash), pay runs (count + id/state hash), employees, named
  updates, mail queue: **identical before/after on all five**.
- After: tree hash repo = server `85b897fb642edd66`; sites payobook.com, rize, p0clone, sudima 200;
  server log since start: 0 ERROR.
- **Live p0clone after start (ports 8471/8472): pb_records 134 + pb_updates 230 tests, 0 failed**;
  one ERROR line, the expected "Error processing line" of Y6c (G68).
- rize: no change by anyone else showed up in this deploy's census (users, payslips, runs,
  employees, updates, mail queue identical).

| Check | payobook | payobook_template | p0clone | rize | sudima |
|---|---|---|---|---|---|
| `pb_updates` latest_version | 19.0.1.7.0 | 19.0.1.7.0 | 19.0.1.7.0 | 19.0.1.7.0 | 19.0.1.7.0 |
| `pb_updates_ytd_*` tables / tax-sheet view / rules | 5 / 1 / 5 | 5 / 1 / 5 | 5 / 1 / 5 | 5 / 1 / 5 | 5 / 1 / 5 |
| upgrade log ERROR | 0 | 0 | 0 | 0 | 0 |
| active jobs before → after | 50 → 50 | 32 → 32 | 39 → 39 | 82 → 82 | 81 → 81 |
| mappings / figures after the checks | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |

## R9. Live checks

1. **Live payobook, server-side as the QA user, read only, rolled back** (`odoo-bin shell`, logfile in
   the evidence folder): Updates home answers year-to-date available / may send / may set up,
   default date 31 Oct 2026, 0 people, 0 mappings; the sheet for the whole roster (4,547 people, 7
   columns) in 1.7 s; read back as our sheet and sent straight back: **0 changes** (3,049 rows
   matched, 1,498 namesake rows unmatched, as in P4); a draft of this kind saved, listed, discarded;
   the view (4,476 people with a finished payslip this year) in 1.1 s; set-up read (defaults GROSS /
   TXBASE / PIT / SIEMP+HIEMP+UIEMP / SICOMP+HICOMP+UICOMP, 12 schemes). Counts of updates, figures,
   mappings, approval proposals, mails and payslips identical; transaction rolled back — **nothing
   written**.
2. **Throwaway copy `p5copy_payobook`** (restored on the server from a fresh dump WITHOUT scheduled
   jobs and mail servers — 0 and 0 — dropped with `--force` at 13:29 UTC, dump deleted): as the QA
   user, gross / tax / months for 2 DEMO people (DEMO Recruiter, DEMO Nguyen Van An) as at 30 Sep
   2026 — approved at once (company 5's records route is "No approval needed"), RD00185, 6 rows `set`;
   the view showed them (before 96,000,000 / 4,200,000 / 9; nothing paid since); Undo: "6 figures
   were taken back."; payslips (34,322) and mail (3,135) unchanged, no mapping.
3. Browser, look only, payobook.com with an existing session: the home's fifth tile and the
   year-to-date view render, console 0 errors (`16-live-payobook-ytd-view`). rize and sudima: not
   opened; nothing applied there.

Left behind on purpose: nothing on live payobook (the write check ran only on the dropped copy).

## R10. Deviations from the handover, and why

1. **Figure codes ("paid in Payobook") are a per-company set-up with defaults**, not "the same codes
   the employee tax summary uses" alone: the summary is a flat list of codes with no meaning per
   figure (and has no taxable or employer codes). Defaults = the known codes the summary shows or the
   company's schemes have; a payroll manager changes them on Set up.
2. **"Paid in Payobook" that cannot be known is never 0.** A month with no finished payslip between
   the figures and the pay period, or finished payslips that carry none of the figure's pay items
   (G66), refuses that payslip with a sentence (delivery) and shows "—" (view). The handover asked
   for a chip; a silent understated total in a December tax step is the silent-zero class of bug.
3. **A third delivery basis**, "Months so far this year, including this pay period", for months
   counted only — Rize's BE counts the current month.
4. **Another source wins on the no-file path.** When something else (a connected system, a record
   mapping) already fills a mapped item, the figure is not sent there (handover: "ONLY when no other
   source supplies that item"); D11's stop applies to the pay data file and the month's workbook.
5. **Tax summary: one-code figures only** are added to a code's total; a several-code figure is listed
   under the table, never split. Signs follow the summary.
6. **Who may do what**: see/download/view = payroll officer and up (the figures are pay data);
   send a sheet = that plus permission to change employee records; set-up and mappings = payroll
   manager (the Tenant administrator reaches it through "Payroll administrator") or system.
7. **"Download for the pay run" has two tabs**: the wide sheet for a pay-data-file run, and a Monthly
   adjustments tab whose `…/.id` columns the list's own import takes as they are (G69) — the way an
   application-data run already takes these inputs; approval there is unchanged.
8. **The way out before anything is sent** (Apply step) is built in `pb_updates` with the same two
   gates as the inbox's helper (`pb.access.can_manage`, `_can_config`), because there is no request
   yet; with a request (Done screen, Past updates) the inbox's own `_second_person_fix` answers.
   `pb_approval_config` is reached by soft checks only (no new dependency).
9. **Demo-division pay runs on payobook** (pb_demo's shortcut) do not read figures at compute time,
   as P2d R8.1 for one-offs; a Recalculate does (seam 1). No mapping exists on payobook.
10. **The view lists everyone with a figure or a finished payslip this year** (people with figures
    first), 50 per page, rather than only people with figures, so "paid in Payobook" is visible for
    all.

## R11. New gotchas (ledger G65–G70)

Raw SQL after an ORM write needs a flush; demo-world payslips carry no computed values; deduction
lines are stored negative on the demo scheme; the pay-file batch turns a refusal into an "Error
processing line" log line; the list import takes `/.id` columns; re-signing-in on a local walk
resets the company (set the `cids` cookie).

## R12. Needs an owner decision / owner action

1. **Rize December**: follow R6's seven steps in December (load figures, two set-up screens,
   finish November, download, import + approve the Monthly adjustments, enter the final-period flags,
   run). Rize must confirm which pay item is its monthly taxable gross ("Total income" looks like
   it) and whether any qualifying severance was paid on Payobook.
2. **Rize joining dates**: all 126 Indonesia people have no joining date. Not needed for these
   figures, but it is exactly the case where the engine's own year-to-date source would give a
   confident zero (R7). Fill them, or schedule R7's fix.
3. **R7 silent zero**: approve the proposed fix in the payroll engine (a separate, small change with
   its own test).
4. **payobook demo**: the demo payslips have no taxable base, so "Taxable pay" shows "—" for paid in
   Payobook there. Fine for a demo; say if the demo generator should store computed values.
