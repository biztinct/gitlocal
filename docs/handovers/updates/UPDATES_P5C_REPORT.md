# UPDATES — Phase 5c report ("paid in Payobook" counted honestly)

Implemented, tested, deployed and checked on 2026-11-13 by the Opus implementation agent, against
the owner's prompt of 2026-11-13 (the prompt was the spec) and `UPDATES_LEDGER.md`. It closes the
three counting faults P5b found in the Updates year-to-date screen (ledger G85, G86, G87; P5b
report R9.2). New facts **U49–U51**, gotchas **G89–G93**; no new owner decision (questions in R11).

R0 below was written BEFORE the deploy. **What actually happened (R9):** before this phase deployed,
another session's deploy (Attendance connector, Codex, 22:52–22:55 UTC) copied this session's
then-UNCOMMITTED `pb_updates` working tree to the server and ran `-u pb_updates` on all five
databases. The tree it carried is byte-identical to commit `9a2b8130c` (hash `977e36ff45d2b387`), so
no second upgrade was run; this phase verified it instead (R9).

## R0. Rollback note (written before deploying)

- **What the deploy changes.** `pb_updates` 19.0.1.7.1 → **19.0.1.7.2** on `payobook`,
  `payobook_template`, `p0clone`, `rize`, `sudima` (`-u pb_updates` on each, one service stop).
  Python, the year-to-date screen's JS/XML/SCSS, one new test file and appended `vi_VN.po`
  entries. **No field, table, record rule, view record, job or mail.** No stored data is written by
  the upgrade or by the code: every change is in how numbers are READ.
- **Files:** the previous tree is kept as `/odoo/backups/updates-p5c-<TS>/pb_updates.prev`.
  Restore = scoped `rsync -a --delete pb_updates.prev/ /odoo/odoo-server/addons/pb_updates/`,
  stop, `-u pb_updates` on the five, asset signal + purge + version bump, start.
- **Data:** no dump is required (no schema change); none is needed for a rollback either, because
  nothing is written. Nightly backups (19:30 UTC) stand.
- **Pay runs:** there is no year-to-date mapping and no figure on any of the five databases
  (census in R9), so no pay run reads any of this; Y9 re-run byte-identical (R8).
- Nothing is applied, mapped or loaded on `rize` or `sudima`.

---

## R1. What shipped

| Module | Version | Where | What |
|---|---|---|---|
| `pb_updates` | 19.0.1.7.1 → **19.0.1.7.2** | upgraded on all five | one computation for "paid in Payobook" (`_ledger` › `_person_window` › `_figure_paid`), used by the year-to-date view, its download, "Download for the pay run" and the value a mapped pay item receives; incomplete / doubtful sums never presented as totals; pay runs and "Download for the pay run" refuse them with a sentence; "How this number was worked out" on each cell (lazy); 18 new tests; 53 Vietnamese entries (append only) |

Files: `models/updates_ytd.py` (the computation, the refusal rule and its sentences),
`models/updates_ytd_desk.py` (view rows, notes, downloads, popover RPC `get_ytd_cell_detail`),
`models/updates_ytd_payrun.py` (both seams refuse through `_plan_blocked`; the payslip's sources
record which payslips were added and any month below zero), `static/src/{js,xml,scss}` (cells,
chips, popover), `tests/test_updates_p5c.py`, `i18n/vi_VN.po`, manifest version.
**Not touched:** any tax formula, scheme rule, payslip, stored pay result, pay-engine file,
`pb_me_portal`, and the other session's modules (`pb_lifecycle`, `pb_hiring`, `pb_me_expense`,
`pb_timeoff`, `docs/handovers/workflow2`).

The employee tax summary (`/my/taxsheet`) does **not** share this code: `pb_me_portal` sums its own
lines (`pb_me_portal/controllers/portal.py:450-495`); `pb_updates` only adds the figures before
Payobook on top. It has the advance double count too — see R11.3 (not changed: another module).

## R2. Fault 1 — partial coverage (G85)

**Cause.** `pb_updates/models/updates_ytd_desk.py` (HEAD `3fe572c19`) line 1148:
`found = bool(mine_rows) or not had` — "paid in Payobook" was treated as known when ANY of the
person's finished payslips in the window carried one of the figure's pay items. The delivery path
did the same (`updates_ytd.py:546`, `info['unknown'] = bool(had) and not any(...)`). Old demo
payslips (no stored results, no taxable-pay line) plus one new run gave a confident-looking
number that added one month.

**Rule now applied** (`updates_ytd.py` `_figure_paid`, called by every reader):

- A finished payslip **should carry** a figure when its pay scheme has at least one of the figure's
  pay items (`hr_formula_rule` codes of `formula_config_id`), or it actually carries one, or it
  names no scheme (cannot be placed → assumed to). A payslip of a scheme that does not have the item
  at all is **not expected** to carry it and is not flagged.
- **complete** = every payslip that should carry it does. **partial** = some do: the amount of
  those that do is shown, marked "3 of 11 payslips have this figure" (amber chip), the Total column
  reads "Known so far" (not a year total), the view download leaves the total blank and fills the
  new "· complete?" column ("Incomplete: 3 of 11 payslips have this figure"), and a pay run /
  "Download for the pay run" refuses the person with a sentence (`_plan_blocked`, `_gap_sentence`).
- **unknown** (none of them carries it, or no pay item is chosen): "—" as before, chip "Paid in
  Payobook not known", refused in a pay run as before.
- The "no silent zero" stop of P5 is extended (`_plan_blocked`): a month with no finished
  payslip, unknown, **partial**, **overlap** (§R5) and **an advance that cannot be matched**
  (§R4) all stop the payslip.

| Test | Result |
|---|---|
| C1 Ada: 4 finished payslips of a scheme with taxable pay, 2 kept it (50,000; −20,000) → `partial`, 2 of 4, paid 30,000 (signed), not a total; P5's code showed 370,000 as a total | PASS |
| C2 Ivy: July on a scheme without the item (not expected) + August with it → `complete` 1 of 1, total 260,000 | PASS |
| C3 the same Ada with a mapping: `_plan_for_slip` `incomplete='partial'`; computing her November payslip raises "only 2 of the 4 finished payslips…"; "Download for the pay run": blank value, Check sentence, no Monthly adjustments row | PASS |
| C4 view download: "Taxable pay · complete?" column; Ada's taxable total blank with the marker; gross total 1,000,000 "Complete" | PASS |

## R3. Fault 2 — sign (G86)

**Cause.** `updates_ytd.py` (HEAD) line 460 `SUM(ABS(l.total))` and line 481
`abs(float(text))`: every amount was counted as its size, so a negative taxable base (reliefs
larger than pay) or a refund month counted as positive.

**How the engine stores amounts (evidence).** A payslip line's amount IS the stored calculation
result, same sign: `pb_hr_payroll_formula/models/hr_payslip_formula.py:956`
(`amount = computed_values.get(rule.code, 0.0)`) and `payroll_import_batch.py:3991, 4023`
(`normalize_payslip_amount` → `'total': amount`). Deductions are NOT stored as positive magnitudes
on lines: the sign is whatever the scheme's formula gives — negative on the demo world (`PIT`,
`SIEMP` … all −; `demo_catalog.py:51` `_PIT = "=-MAX(…"`), positive on Rize Indonesia (PIT, JHT, JP
+). The one pay-band rule counts deductions and employer costs as their size because of exactly that
(`om_hr_payroll/models/pay_bands.py:93-110`, `if band in ('DED', 'ERCOST'): amount = abs(amount)`).

**Rule now applied** (`_slip_amount`, `_conventions`), by the line's pay role (`pay_role`, else
the scheme's `net_role` for a value read from stored results, else the one pay-band rule's category
fallback DED/DEDUCTION/COMP):

| Figure kind | Pay role | Counted as |
|---|---|---|
| Gross pay | earning | signed |
| Taxable pay | information | signed; a month below zero is shown ("Includes a month below zero (June 2026)") |
| Income tax withheld | deduction | size, in the scheme's usual sign: a month with the OPPOSITE sign (a refund) reduces the year |
| Employee contributions | deduction | same |
| Employer contributions | employer cost | same |
| A pay item as its own figure | its own role | deduction/employer cost as above; anything else signed |
| Months counted | — | each month once (§R4) |

"Usual sign" = the sign most of the scheme's latest 100 finished payslips of the tax year carry for
that pay item (`CONV_SAMPLE`); a tie falls back to the size (the one pay-band rule). The same answer
serves the view, both downloads and a pay run.

**Taxable pay below zero — what the tax formulas do.**
- Rize Indonesia (`rize`, scheme 7121, read live): the annual taxable base is
  `IDANNUATAXAPKP = MAX(0, FLOOR(BC30 + Z30 − … , …))` where BC30 is "Prior YTD taxable gross" — the
  prior year-to-date amount enters the annual formula **additively, signed**; only the YEAR result is
  floored at 0. So for Rize, a month below zero reduces the year's sum: the signed sum is what the
  scheme itself does. (Rize's taxable-gross pay item "Total income" `IDTOTALINCOME =SUM(L30:X30)` had
  no month below zero on any payslip.)
- The demo world (payobook): the MONTHLY formula pays no tax on a month below zero
  (`demo_catalog.py:51` `IF(TXBASE<=0,0,…)`); no annual formula exists, so the code cannot tell what a
  year sum should do. **The signed value is summed and the row says "Includes a month below zero"**;
  question for the owner R11.1.

| Test | Result |
|---|---|
| S1 Ada: gross 4 × 100,000 = 400,000; tax (scheme writes −10,000 ×3, then +4,000 refund) = 30,000 − 4,000 = **26,000** (P5: 34,000), total 56,000, refund month shown; employee contributions 4 × 8,000 (stored −) = 32,000; employer 4 × 17,500 (stored +) = 70,000; taxable signed with October below zero shown; a pay item as a figure (Cyd's clawback −5,000) = −5,000 shown | PASS |
| S2 usual sign read per scheme: monthly PIT −1, employer cost +1 | PASS |

## R4. Fault 3 — double count of mid-month advances (G87)

**How an advance relates to the month-end payslip (evidence).**
- A scheme's kind is stored: `hr.formula.config.cycle_type` `mid_cycle` = "Mid-month advance"
  (`formula_config.py:74-79`; screens: `pb_explorer/models/pb_explorer.py:108`,
  `pb_blueprint/models/blueprint_studio.py:34`).
- The engine links an advance scheme to the month-end scheme it is carried to:
  `hr.payroll.cycle.component.mapping` (mid component → end component, menu "Mid-Cycle to End-Cycle
  Mapping"); `_create_mid_cycle_carryovers` (`payroll_import_batch.py:2404`) carries the advance's
  amount into the month-end payslip, which takes it back off.
- The demo world: "Mid and End share the FULL spine (… GROSS, insurance, PIT …) … End receives
  ADVPAY as an INPUT and pays NET = FULLPAY − ADVPAY" (`pb_demo/models/demo_catalog.py:218-226`);
  on its advance payslips GROSS/PIT/SIEMP carry pay role **information** (10,685 lines), i.e. the
  advance's own scheme says they are working figures, not pay.
- Every report already defaults to main runs (`pb_explorer/models/pb_fact_builder.py:137-146`,
  `is_advance`).

**Rule now applied** (`_person_window`): a finished payslip of an advance scheme is **never added**.
- Its month has a finished month-end payslip of a scheme it is linked to (a mapping row, active or
  archived) → not counted; "How this number was worked out" lists it under "not counted" with "the
  month-end payslip carries the whole month and takes the advance back off".
- Its month has a month-end payslip but no link → **cannot be determined**: the advance is shown
  apart ("+ X in mid-month advances, shown apart and not added"), the cell is not a total, a pay run
  refuses with "…Link the advance's pay scheme to its month-end pay scheme in Mid-Cycle to
  End-Cycle Mapping…".
- No month-end payslip that month → not counted, and the month is not a month counted ("the
  month-end payslip is not finished yet").
- Every other finished payslip (top-up, awards, bonus, full and final, a second scheme) is pay and
  is counted. Months counted = each month once.
- Two finished payslips of the SAME scheme for the SAME dates (e.g. two test runs) are both counted
  (a second run of one scheme can be real pay) but never quietly: row chip "Same pay period twice",
  a note in the cell and the downloads' Check (R11.2).

| Test | Result |
|---|---|
| D1 Ben: July + August advance (100,000 each, linked) and month-end (100,000 each) + an August top-up of another scheme (20,000) → gross **220,000** (P5: 420,000), total 720,000; months 2 (6 + 2 = 8); tax 10,000 × 2 + 2,000 = 22,000 | PASS |
| D2 Cyd: month-end only → 200,000, total 700,000 | PASS |
| D3 Dee: advance of a scheme linked to nothing + month-end → `split`, 100,000 counted, 100,000 shown apart, not a total; pay run refuses with the sentence naming the mapping screen | PASS |
| D4 an advance with no month-end payslip that month → not counted | PASS |
| D5 two finished payslips of one scheme for July → both counted (300,000), "Same pay period twice", note; a pay run not refused (R11.2) | PASS |

## R5. The window — hand-computed fixtures

All in `tests/test_updates_p5c.py` (company of its own, today 20 Nov 2026, figures before Payobook
up to 30 Jun 2026 unless said):

| # | Fixture | Hand computation | Result |
|---|---|---|---|
| W1 | Ada, November period, "Total so far this year, before this pay period" | gross 600,000 + Jul–Oct 400,000 = **1,000,000**; tax 30,000 + 26,000 = **56,000**; "Months so far, including this pay period": 6 + 4 + 1 = **11** | PASS |
| W1 | Ada, October period | 600,000 + Jul–Sep 300,000 = **900,000**; months 6 + 3 + 1 = **10** | PASS |
| W1 | Ben, September period | 500,000 + 220,000 (advances not added, top-up added) = **720,000**; months 6 + 2 + 1 = **9** | PASS |
| W2 | Hal, figures up to **15 Jul**; a payslip 1–31 Jul straddles it; August 1–31 | July overlaps → `overlap`, not added, not a total; paid = August 100,000; months counted 7 + August = 8 (July already in the figures); a September pay run refuses: "…the payslip for 1 Jul 2026 to 31 Jul 2026 … overlaps the figures before Payobook, which cover up to 15 Jul 2026…" | PASS |
| W3 | Eve, figures (300,000), no payslips | view: total 300,000 (a total: nothing finished yet); July period: 300,000; August period: July missing → refused, never 300,000 | PASS |
| W4 | Fay, payslips March–April, no figures, no joining date | 200,000 "Known so far"; row chip "Not covered: January 2026 to February 2026"; download for the pay run lists her with "No figures before Payobook for 2026…" and no value | PASS |
| W4 | Gus, same payslips, joined 1 March 2026 | covered from March: a year total | PASS |
| H1–H3 | "How this number was worked out": Ben's gross lists 3 payslips counted (two month-ends + the top-up, 20,000) and 2 advances not counted, with why; Ada's taxable shows the 2 payslips without it; a year outside this/last refused; no vendor name in any new sentence | PASS |

**Faults found in the window and fixed here:**
1. Each person's window started after the LATEST "covers up to" of all their figures
   (`updates_ytd_desk.py:1124` HEAD, `covers = max(...)`): a figure loaded up to 30 Sep beside another
   up to 31 Oct lost October. Now each figure uses its own date (the delivery path already did).
2. A payslip straddling "covers up to" was dropped silently from the sum and its month reported
   missing; now it is named ("overlaps the figures before Payobook") and refused in a pay run.
3. Months counted included an advance-only month (June on the demo: 1,850 people counted one month
   too many) and a month already inside the figures (a mid-month "covers up to"). Fixed.
4. A person with payslips and no figures before Payobook showed a total that looked like a year
   total while January–March had nothing at all. Now "Known so far" + "Not covered: …" (the joining
   date, when filled in, moves the start).
5. "Download for the pay run" wrote a value into the wide sheet even when it could not be worked out
   (only the Monthly adjustments tab left it out), and silently left out people with no figures. Now
   the value is blank with the reason, and everyone the scheme pays is listed.

## R6. The real data — demo world (local copy of live payobook, read only)

`_ytd_rows(2026)` for all 4,476 people, old code vs new code (`cmp_capture.py`, rolled back):

| Figure | People whose "paid in Payobook" changed | Over-count removed (whole roster) |
|---|---|---|
| Gross pay | 4,465 | ₫278,959,238,159 (advances added on top of month-end payslips, April–June) |
| Income tax withheld | 3,710 | ₫15,358,505,337 |
| Employee contributions | 4,465 | ₫17,551,406,500 |
| Employer contributions | 4,465 | ₫35,860,037,500 |
| Months counted | 1,850 | June advance-only months |
| Taxable pay | 0 amounts changed; **5 people** that P5 showed as a full number are now "1 of 4 / 2 of 5 … payslips have this figure" | — |

Example (demo person 10080, Retail): gross old 119,119,644 → new **67,741,176** = 15,747,566 (April
month-end) + 14,497,654 (May) + 19,155,956 (July) + 18,340,000 (October awards run); the April, May
and June advances are listed as not counted; June, August, September missing.

## R7. Rize — read only (live `rize`, psql; and a rolled-back what-if on a local copy)

Live census today: **no finished payslip on rize at all** (487 drafts); **no mid-month advance
scheme** (every scheme `regular`) and no mid-to-end mapping; **0 figures, 0 mappings**. The four
"focused payroll" schemes are active; Indonesia = 7121.

What each fault would have done to Rize's December figures:

| Fault | Would it have hit Rize? |
|---|---|
| 1 Partial coverage | Unlikely: every Rize payslip is engine-computed and keeps its results (244 of 244 Indonesia drafts carry them), and Rize's taxable gross is a printed line. It would hit only a payslip of a scheme without the chosen pay item, which is now not flagged. |
| 2 Sign | **Yes.** Person **5343**'s August TEST payslip (final tax period) has PIT **−3,925,731** (a refund: annual PPh21 0 − 3,925,731 withheld). P5's code would count +3,925,731 as tax withheld; the corrected count is −3,925,731 (the Indonesia scheme writes PIT positive, so a negative month is a refund). No negative taxable month exists on rize. |
| 3 Advances | No: Rize has no advance scheme. **But** August has TWO test runs of the same Indonesia scheme for the same people (2111 "monthly Excel import" and 2114 "application inputs", 122 + 122 drafts). If both were ever finished, every figure would double; now both are counted but every row says "Same pay period twice" and the pay-run download's Check says to check one is not a test. |

What-if on a local copy of today's rize dump (August TEST runs marked finished inside a rolled-back
transaction; figure set-up as P5 R6 recommends — taxable ← Total income, tax ← Payable tax,
employee contributions ← Old age + Pension employee):

| Person | Figure | P5 code (one run finished) | Corrected | Note now |
|---|---|---|---|---|
| 5343 | Income tax withheld | 3,925,731 | **−3,925,731** | Includes a month below zero (August 2026) |
| 5343 | Taxable pay | 2,205,394 | 2,205,394 | — |
| 5228 | Income tax withheld | 5,668,170 | 5,668,170 | — |
| 5228 | Employee contributions | 841,863 | 841,863 | — |
| 5229 | Taxable pay | 20,815,025 | 20,815,025 | — |
| all three | — | shown as totals | "Known so far" | "Not covered: January to July 2026" (no figures loaded, no joining date) |

With BOTH August test runs finished, P5's code doubled everything (5228 tax 11,336,340); the
corrected code also counts both (they are real finished payslips) but says "Same pay period twice".

## R8. Tests, Y9, speed

| Suite / check | Where | Result |
|---|---|---|
| `TestUpdatesP5c` (18 cases, §R2–R5) | local isolated tree (G13: `git archive HEAD` + this module), copy of `upd_p3c_t_tpl` | **18, 0 failed** |
| full `pb_records` + `pb_updates` | same, `-u pb_records,pb_updates,pb_import_advanced` | **134 + 263, 0 failed** (P5's 21 cases unchanged and green) |
| the same suites on **live p0clone** after start, ports 8471/8472, no upgrade | server | **134 + 264, 0 failed**; one ERROR line = the expected "Error processing line" of P5 Y6c (G68) |
| **Y9** (P5's `y9_capture.py` = P2d's E1) on a fresh copy of today's live payobook dump, Retail end-month, 12 people, December 2026, six modes | local | pre-phase code, new code, new code **with two mappings and figures for other people**: **6 of 6 identical in all three**, and identical to the hashes P5 recorded: no-file `4ecfc38110407470`, pay-file `d88c66c183d0edd1`, template `f9755a528c321347` |
| review 4,575 × 73 | local copy of live payobook | **18.1 s / 16.1 s** (≤ 25 s) — 0 changes, 60,080 same, 1,499 unmatched, as P5 |
| year-to-date view, first page (4,476 people) | local copy | cold 1.85 s (old code 1.61), pages 0.70–0.85 s (old 0.60); popover 0.05 s |
| the same | **live payobook** (shell) | warm **1.05–1.53 s**; the very first call of a fresh process 7.7 s (cold caches; the running server is warm) |
| whole-roster view download | local copy | 11.9 s (old 11.2 s) |
| `.po` | `pb_updates/i18n/vi_VN.po` | built from `odoo-bin i18n export -l pot` (G6); 53 entries appended (old file a byte prefix), `PoFileReader` 1,446 rows, 0 placeholder mismatches, 0 duplicates, 0 "Odoo" in any msgstr, every new entry has `#. module:` + `#. odoo-python/javascript` + `#: code:` (G2) |

Browser (G3): local copy of live payobook on `127.0.0.1:8895`, company Payobook Vietnam JSC, console
read: **0 errors**. Screenshots in `outputs/updates-p5c/` (not committed): `01-view-known-so-far`,
`02-how-this-number-was-worked-out` (taxable pay, 1 of 4 payslips, three payslips "Does not have this
figure"), `03-live-payobook-view-popover` (live payobook.com, an existing session, look only — no
sign-in with a password). Escape and a click elsewhere close the popover, focus returns to the
amount. Walk-copy set-up said here: a local password for the admin login and five demo people given
figures before Payobook — local copy only. Vietnamese: the screen was switched to Vietnamese on the
copy; Chrome's own page translation turned the text back into English in the DOM (G92), so the
Vietnamese was checked by the parse gate and the untranslated remainder.

## R9. Deploy evidence

**Deploy, as it happened.** `pb_updates` reached all five databases inside the Attendance
connector deploy (Codex, START 22:52 / DONE 22:55 UTC in `/opt/deploy-notes.md`, "combined
repository snapshot", 100 s down, backups recorded by that deploy). That deploy took the whole
working tree, including this session's uncommitted `pb_updates` (version already bumped to
19.0.1.7.2). It is not the deploy this phase planned (R0); by luck, the tree it took was this phase's
final, fully tested state.

**This phase's own entry** — unit `updates-p5c-20261112T230538Z` under
`flock /tmp/payobook-studio-deploy.lock` (free), START 23:05 / DONE 23:13 UTC, evidence
`/tmp/updates-p5c-20261112T230538Z/` on the server. **No restart, no `-u`, 0 s down.**

| Check | payobook | payobook_template | p0clone | rize | sudima |
|---|---|---|---|---|---|
| `pb_updates` latest_version | 19.0.1.7.2 | 19.0.1.7.2 | 19.0.1.7.2 | 19.0.1.7.2 | 19.0.1.7.2 |
| tree hash (one addons dir) | `977e36ff45d2b387` = commit `9a2b8130c` | ← | ← | ← | ← |
| figures / mappings / figure set-ups | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| active jobs now (P5b after) | 51 (50) | 32 (32) | 40 (39) | 83 (82) | 82 (81) |
| job added since P5b | 155 | — | 91 | 91 | 91 |

The added job on four databases is "Attendance connectors: review received records" — the connector
deploy's own ("new processing cron active except template"), not this phase's. Nothing else
appeared or disappeared (id lists compared with P5b's evidence lists).

- Assets: signal row + `/web/assets/%` purge + `web.assets.version = upd-p5c-20261112T230538Z` on all
  five (the connector deploy had purged but not bumped the version).
- Server log since 22:52 UTC: **0 ERROR**.
- Live checks, read only, rolled back (`odoo-bin shell` with a log file, ports 8475/8476): payobook —
  view 4,476 people, popover answers (2 payslips counted, 2 advances not counted), counts of figures,
  mappings, figure set-ups, payslips and mails identical before/after; rize — view answers, 0 people
  (nothing finished, nothing loaded), counts identical.
- **Downtime caused by this phase: 0 s.** The code went live inside the connector deploy's 100 s.
- No pg_dump: no field or table was added (the connector deploy recorded its own backups).

## R10. Deviations, and why

1. **No deploy of my own** (R9): the files were already live and identical; a second `-u` would only
   have added downtime. Verified instead, with the lock and START/DONE lines.
2. **Two finished payslips of one scheme for the same dates are counted, not refused** (§R4): a
   second run of one scheme can be real pay (a bonus run on the month-end scheme), and a December pay
   run with no way past a refusal is worse than a visible note. Owner question R11.2.
3. **"Usual sign" from the scheme's latest 100 finished payslips of the tax year**, not the whole
   year (G90: speed). A tie falls back to the size.
4. **The employee tax summary is not changed** (another module's own sums; R11.3).
5. **People with no figures before Payobook still receive nothing in a pay run** (P5's Y9 rail,
   unchanged); "Download for the pay run" now names them with a sentence instead of leaving them out.
   Owner question R11.4.

## R11. Needs an owner decision

1. **A month of taxable pay below zero** (reliefs larger than pay). On Rize Indonesia the tax formula
   itself adds the prior months signed and only floors the year (`IDANNUATAXAPKP`), so the signed sum
   is right there. On the demo schemes the monthly tax simply pays nothing for such a month and there
   is no annual formula, so the code cannot tell. Today: the signed sum is used and the cell says
   "Includes a month below zero". Alternative: count such a month as 0. Which one should a year total
   use for a scheme without an annual formula?
2. **The same pay period paid twice by one scheme** (e.g. Rize's two August TEST runs, if both were
   ever finished). Today: both counted, a "Same pay period twice" chip, and "check one is not a test"
   in the pay-run download. Alternative: refuse that person in a pay run until one is cancelled — safer
   for test runs, but it also stops a real bonus run made on the month-end scheme.
3. **Employee tax summary (`/my/taxsheet`, module `pb_me_portal`)** adds every finished payslip,
   advances included: on payobook.com an employee's year-to-date gross, insurance and tax show about
   double for April–June. Not changed here (another module). Fix it the same way (advances never
   added)?
4. **People with payslips but no figures before Payobook** (a mid-year joiner on Rize): a pay run gives
   their year-to-date pay items nothing (the P5 rule that runs without figures stay exactly as before).
   For Rize's December, load 0 for each figure for anyone who joined this year, or decide that a
   person with no figures should receive "paid in Payobook" alone.
5. **Rize's two August TEST runs** (2111, 2114) are drafts with the same 122 Indonesia people; delete
   them, or make sure neither is ever finished.
6. P5b R9.1 (demo payslips without taxable pay) stands: on payobook.com taxable pay reads "Paid in
   Payobook not known" or "1 of 4 payslips have this figure" — now said honestly.

## R12. New facts and gotchas (ledger U49–U51, G89–G93)

- U49 sign of lines vs stored results, by scheme; U50 how an advance relates to the month-end
  payslip; U51 what Rize's and the demo's tax formulas do with a month below zero.
- G89 per-figure "covers up to"; G90 the usual-sign query cost; G91 label formatting cost; G92
  Chrome translates a Vietnamese page back to English; G93 another session's deploy took this
  session's uncommitted module tree live.

