# WDGAP W2-D1 — Past-month re-work (read-only): report

Branch `wdgap-w2d1` (from `origin/19.1` @ 7f0fa3aad), not merged, not deployed.
New module **`pb_retro` 19.0.1.0.0** ("Payobook Past-Month Re-work"). No other module
was edited. Depends on `om_hr_payroll`, `pb_hr_payroll_formula`, `pb_formula_studio`
(the W2-C evaluation helper and error probe are imported, not copied), `pb_payruns`,
`pb_payhub`, `pb_hub`, `pb_import_kit`, `pb_filter_kit`.

## 1. What was built

| Piece | Where |
|---|---|
| `pb.retro.review` — scheme, months (from–to, finished payslips whose period ends in them), everyone or the people picked, reason (required), contract changes left out, state draft → worked out → closed (+ cancelled), who/when, time taken, scheme stamp at working-out | `pb_retro/models/retro_review.py` |
| `pb.retro.whatif` — one typed value: payslip (person + month), pay item (number inputs of the scheme only), value, note (required) | same |
| `pb.retro.slip` — the stored snapshot per payslip: result (no difference / would change / cannot be compared exactly / could not be worked out / not re-worked), why, drift items, error item, scheme-version flags, what changed (JSON), was and difference per band (gross, deductions, take-home, employer cost) | same |
| `pb.retro.line` — one pay item that would change: was, worked-out-again baseline, would be, difference, currency, cause (which overlay rows drove it, from the formula dependency chain) | same |
| `_RetroWork` — one compiled scheme per chunk, one payslip at a time (§2) | same |
| `pb.retro.board` — board, filter panel, guided "New re-work" (preview, people, payslip options, save), chunked working-out (start / chunk of 40 / finish), result, people page, drill to the payslip, Excel | `pb_retro/models/retro_board.py` |
| Screen "Past-month re-work" — OWL cockpit, quiet glance, filter kit, Lucide icons; Payroll hub lens "Past months" (sequence 50) and one ⌘K entry (4420) | `static/src/js/retro_board.js`, `retro_palette.js`, `xml/retro_board.xml`, `scss/retro_board.scss` |
| Rights: payroll managers (`om_hr_payroll.group_hr_payroll_manager`, the people who approve/reopen a pay run) and administrators; global company rules on all four models | `security/` |
| `vi_VN.po`, `id_ID.po` | `i18n/` |

**The screen.** Empty board: a hero card explaining the idea (read-only, checked first,
kept as a record) and "Start a re-work". Guided New re-work: 1 Pay scheme (only schemes
with finished payslips) → 2 Months (click first then last; Extra counts shown) → 3 People
(everyone, or tick people) → 4 What changed (detected contract changes pre-listed, each
can be left out; a what-if grid person / month / pay item / was / new value / note, Enter
adds a row) + Why → **Work it out** (progress bar per 40 payslips). Result: scheme-version
banner, the hero strip per currency ("Take-home **+6,802,000 ₫** across 2 people · Gross
pay +9,270,000 · Income tax +1,523,000 · Social insurance +945,000 · Employer cost
+1,575,000" on the walk), "What happens next" (nothing paid or changed; one-off in
Updates — "Open Updates" only where `pb_updates` is installed, probed by xmlid), What
changed (with pro-rating per month, "already paid back", "left out", "replaced by a
what-if"), Worth a look (drift / errors / Extra & top-up), Person by person (Would change /
Worth a look / Everyone, search, month tables was / would be / difference, reason said
once per month, ≈ on drifted months, Payslip drill). Change / Excel / Close / Cancel /
Work out again.

## 2. How one payslip is re-worked

1. Base = the payslip's stored `formula_input_values` (loan instalments and one-offs
   included, exactly as computed; nothing is re-read or reserved).
2. **Sanity gate**: those inputs evaluated with no overlay through
   `formula_program.run_payslip` (the loop the payslip path itself runs) and turned into
   payslip lines through the W2-C `_Engine` (same line filter as
   `_create_payslip_lines_from_formulas`, bands through `pb_pay_totals` on an in-memory
   payslip). Compared with the stored lines item by item, written in the currency
   (Excel rounding). Any difference → "cannot be compared exactly", items named;
   differences are then measured against this baseline, never against the stored line,
   and marked ≈.
3. Overlay: contract changes (`hr.contract.advantage.change`) whose pay item is an input of
   the scheme, effective on or before the payslip's period end, **entered after the
   payslip was last computed** (= newest `create_date` of its lines; lines are re-made on
   every compute), not a "checked" or "filled in by Payobook" row, amount actually moved:
   (new − old) × days covered ÷ days in period (scheme's proration basis,
   `_get_proration_days`), `excel_round` to the scheme's proration places. A change the
   existing retro flow already paid back for that payslip
   (`hr.payroll.retro.adjustment`) is listed and not applied. A what-if value replaces the
   stored value (and a contract change of the same item).
4. Errors: the W2-C probe (`_Engine.diagnose`) on the baseline and on the result; a
   formula that raises upstream of any payslip line → "could not be worked out", naming the
   pay item; every other payslip continues.

## 3. Is a past run's scheme version recoverable? (handover 2c) — **No**

What exists: each payslip stores `formula_content_hash` (stamp of the money rules that
computed it) and `formula_milestone_id`; components keep `hr.formula.rule.version` rows
(outgoing formula text + some fields). Not enough to rebuild a past formula SET: default
values are not versioned, a removed component loses its history (`ondelete='cascade'`),
added components have no "before", and nothing snapshots the scheme as a whole. So D1
always evaluates with **today's** scheme and uses the stamp to say, per payslip, whether
today's scheme is the one that computed it.

Banner text: **"Worked out with today's version of the scheme"** — "N of M payslips were
worked out with an earlier version. Payobook does not keep earlier versions as a whole, so
today's formulas are used for every month." / "N payslips carry no record of which version
worked them out." When every stamp matches: "Same version of the scheme". If the scheme
changes after the re-work was worked out: "The scheme changed after this was worked out —
work it out again".

## 4. Tests

Local, one database (`wdgap_w2d1_t` = copy of `upd_p6_t_tpl` brought to `origin/19.1`, 33
modules `-u`, `pb_loans` installed so R1 covers loan instalments), dropped afterwards.

`pb_retro` — **21 tests, 0 failed** (`pb_retro/tests/test_retro.py`):

| # | Case | Result |
|---|---|---|
| T1 | no overlay → stored lines reproduce, status "no difference", no lines | PASS |
| T1b | genuine compute path (`compute_sheet_with_formulas`, contract wage → BASIC) reproduces | PASS |
| T2 | contract change effective 16 Aug, three months (Aug 16/31 pro-rated, crosses the 46.8M insurance cap; progressive tax): BASIC, SI, PIT, take-home, employer SI per month = hand-computed forward evaluation; Sep = Oct (cap); a change known before computing is ignored; cause on each line = the change | PASS |
| T2b | a change left out is not applied; preview lists it with its months | PASS |
| T3 | what-if value = hand; a what-if needs a note, a covered payslip, a number input | PASS |
| T3b | what-if replaces a contract change of the same item, shown as "replaced" | PASS |
| T4 | stored take-home edited (+1,000): "cannot be compared exactly", item named, difference netted against the baseline, would be = was + difference, ≈ in the people view | PASS |
| T4b | scheme formula changed since → scheme-changed flag + banner; payslip without stamp → "unknown" | PASS |
| T5 | division by a zero input: that payslip "could not be worked out — Hourly rate (it divides by zero)"; the other payslip changes | PASS |
| T6 | **R1**: SQL spy — no INSERT/UPDATE/DELETE on any table but `pb_retro_*` across working-out, result, people, export; counts + newest write date of payslips, lines, runs, period inputs, loans, loan instalments, one-offs, retro rows, contract changes, contracts, rules, schemes unchanged; stored inputs byte-identical; loan line never differs | PASS |
| T6b | the spy sees a real write | PASS |
| T7 | Extra-run payslip listed "not re-worked — Extra run", preview counts it apart | PASS |
| T8 | **R4**: SGD scheme in cents (1.33 × 7.65 %), VND in dong; board rows and roll-up per currency, never added | PASS |
| T9 | rights: payroll officer refused everywhere (board, layout, preview, options, create); manager of another company sees nothing and is refused; manager here **without formula rights** does the whole thing (preview, save, chunks, result, export, leave a change out → back to draft → no differences) | PASS |
| T10 | **R3** working out twice → identical lines, rows and overlay JSON | PASS |
| T11 | caps: 13 months refused, 12 fine; people cap (patched to 1) refused; last-before-first and blank reason refused | PASS |
| T12 | Excel: one "Amounts in VND" block, totals, second sheet one row per payslip, no vendor name | PASS |
| T13 | **R5** silent install: no job, empty board, one palette entry, one hub lens, no "Odoo" in visible strings | PASS |
| T14 | change already paid back by the existing retro flow → not counted again for that payslip, still applied to later months | PASS |
| T15 | chunks of 2 = one go; a chunk ignores payslips outside the re-work and ones already done | PASS |
| T16 | 40 payslips in one chunk (logged timing) | PASS |

Existing suites `/pb_formula_studio,/pb_hr_payroll_formula` (no `retro` tests exist in
`pb_hr_payroll_formula`; the whole two suites were run instead):

| Run | Result |
|---|---|
| Baseline (before `pb_retro` existed in the DB) | 1268 tests, **11 failed, 1 error** |
| After (`pb_retro` installed, same database, `-u` all three, final code) | 1289 tests (1268 + pb_retro's 21), **11 failed, 1 error — the identical 12** (`diff` of the failure lists: empty); pb_retro 21/21 |

Baseline failure set (identical to PR-A's 12, all on unchanged code): TestOneMappingHome ×4,
TestJourneyView ×2, TestNetPayCandidates 01, TestRd49SyncCost ×2, TestRecordsR1OneTime 07b,
TestRunsrcPcBoardLane 14, TestSchemeCtxCurrency 04.

Static gates: `py_compile` all files; `node --check` both JS files; the three XML files
parse; white-label grep of static/ and views/ clean; PO gate (`PoFileReader`) both files:
**251 code strings that reach a screen + 127 model terms, 0 empty**, placeholders checked
per entry.

### 4a. Browser walk (local, `127.0.0.1:8741`, `--max-cron-threads=0`)

Seed (local only, scratchpad `w2d1/seed.py`): scheme "DEMO Office — End-Month" (basic,
meal allowance, loan, gross, capped insurance, progressive tax, take-home, employer
insurance), three DEMO people, finished September and October runs, one Extra run, An's
pay rise 30M → 36M from 16 Sep entered after the payslips.

- Standalone page: empty board hero → Start a re-work → scheme preselected (only one) →
  months Sep–Oct → "Only the people I pick" An + Binh → What changed: An's rise detected
  ("+9,000,000 ₫ in all", Sep 15 of 30 days) → what-if Binh / Oct / Meal allowance, was
  730,000 → 1,000,000, note → Why → Work it out: 4 payslips in 0.6 s. Result as in §1;
  An Sep checked by hand (basic 33M, SI 3,465,000, tax 2,203,000, take-home 28,062,000).
- Change → left An's rise out → worked out again: +216,000 ₫ for 1 person, rise listed
  "Left out of this re-work".
- Payroll hub → "Past months" lens: board with filter panel and tabs; result scrolls inside
  the hub (no-scroll trap checked).
- Payslip drill opens the payslip form; palette entry and lens present in the registries.
- Export checked through the server call (7 KB workbook) — no file was downloaded in the
  browser.
- vi / id: server sentences and the 196 screen strings come back translated.
- Console: clean on the re-work screen. The hub's default Pay runs lens logs two RPC errors
  on this local copy because the local admin has no formula rights (ledger PRD-6) — not this
  screen.

Walk findings fixed (commit 2d403c537): months listed newest first (now oldest → newest),
the reason repeated under every line (now once per month), deductions going up shown
green (now rose), "1 months" / "1 contract changes", person search on its own line, "+1
extra" unreadable on a picked month.

## 5. R1–R7

| Rail | Result |
|---|---|
| R1 read-only towards payroll | PASS — T6 SQL spy + counts/stamps; nothing outside `pb_retro_*` is written; loans and one-offs fed as stored |
| R2 baseline honesty | PASS — every payslip is gated first; drift named and netted (T4); a difference is never stored for a payslip that was not gated |
| R3 deterministic | PASS — T10, T15 |
| R4 currencies / rounding | PASS — one currency per re-work (the scheme's), every roll-up keyed by currency, Excel one block per currency; only `excel_round` on money (T8) |
| R5 silent install | PASS — T13; no data, no job, no mail; empty board + one palette entry + one hub lens |
| R6 errors isolated | PASS — T5 |
| R7 translations / white-label | PASS — vi + id, PO gate, white-label greps (T13, static gate) |

## 6. Timing

One chunk of 40 payslips (8 components, each with a contract change): **0.74 s**
on the local Mac (T16). Per payslip: two evaluations, two error probes, in-memory lines.
The walk's 4 payslips: 0.4–0.6 s end to end. A 50-component demo scheme is ~5–6× the
formula work per payslip (W2-C measured ~3 ms per evaluation there): expect roughly
2–4 s per 40 payslips, so 500 people × 12 months (6,000 payslips) ≈ 5–10 minutes with the
progress bar. Not measured on a real demo copy (disk).

## 7. What D2 needs (for the orchestrator's owner question)

**More sources of "what changed"** — each needs a read-only, per-period re-read that does
not reserve or consume anything:

| Source | What it would need |
|---|---|
| Attendance (worked days, overtime) | the attendance/feed figures by payslip period re-read now and compared with what the payslip stored; the ranked resolver (`_declared_source_walk` / `_get_formula_input_values`) has no read-only "replay for a past period" mode — one would be added, and the stored `formula_input_sources` tells which inputs came from attendance |
| Leave (unpaid days, leave payouts) | same, from approved leave in the period; the period-input carrier (`hr.payroll.period.input`) reserves/consumes — a replay must read without reserving |
| Feeds (connected systems) | today only the latest pulled rows are kept per data type; a late correction can be detected only if the feed row for that period changed since the payslip — needs a "feed row changed after the payslip" signal per input |

**How to pay a difference — the choice for the owner:**

| Option | Tax and insurance | Fund and tax-office totals | Effort / risk |
|---|---|---|---|
| A. One-off in Updates (today, by hand) | worked out by THIS month's formulas on the lump — progressive tax lands at this month's rate, not the re-worked months' | all lands in this month's fund payments | none to build; tax can differ from the re-work |
| B. Back-pay items in this month's run, carrying the re-worked tax and insurance differences | exactly the re-work's figures | lands in this month's fund payments, labelled as for earlier months | moderate: new pay items + a feed from `pb.retro.line`; the run's own formulas must not tax it again |
| C. A correction (Extra) payslip dated in each re-worked month | exactly per month | lands in the right months — but those months' fund payments are already approved/paid ("figures changed since approval") and past filings need amending | highest; touches closed months |
| D. Reopen the original runs | — | — | not recommended: those people were already paid |

## 8. Deviations from the handover

1. A per-payslip result model (`pb.retro.slip`) beside `pb.retro.line`: the "cannot be
   compared exactly", "could not be worked out" and "not re-worked" states belong to a
   payslip, not to a pay item, and the screen needs the per-payslip totals.
2. Only pay items that change are stored as lines (an unchanged item has no line): the
   snapshot of 500 people × 12 months × 50 items would be 300,000 rows of zeros.
3. Contract changes recorded as "Checked, no change" or "Filled in by Payobook from the
   scheme's usual answer" are not overlay sources (the payslip already used that value).
4. A contract change the existing retro flow already paid back for a payslip is not applied
   again for that payslip (listed as such) — otherwise D2 would pay it twice.
5. Months are the months the payslip's period ENDS in (the pay run board's reading). Any
   payslip that is not in a regular run is "not re-worked" (Extra and top-up).
6. Contract changes and the scheme are read under sudo after the payroll-manager gate: a
   payroll manager on these databases holds no formula rights (found by T9).
7. "Change" on a worked-out re-work sends it back to draft (the snapshot would no longer
   match what it says it covers).

## 9. Owner questions (plain words)

1. **How should a difference be paid?** (table in §7) — the one D2 question.
2. Re-work also attendance, leave and connected-system figures, or only contract amounts
   and typed values? (each is its own piece of work, §7)
3. Who may see re-works: only the people who approve pay runs (built), or the whole pay
   team?

## 10. Deploy notes

New module: `-i pb_retro` on all five databases (`payobook`, `payobook_template`,
`p0clone`, `rize`, `sudima`; never `abm`) — tenant-sync rule, it is safe on every tenant.
Risky tier only because it is a new install: no existing table changes, no stored data
written, no job, no mail. Asset purge + restart. After: Payroll hub → "Past months" shows
the empty board; ⌘K "Past-month re-work". Nothing else to upgrade.

## 11. Gotchas → ledger

Added to `WDGAP_LEDGER.md` as W2D1-1 … W2D1-4.
