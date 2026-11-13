# UPDATES — Phase 5e report (tax summary counts an advance until its month-end payslip is finished)

Implemented, tested, deployed and checked on 2026-11-14 by the Opus implementation agent, against
the owner's prompt of 2026-11-14 (the prompt was the spec) and `UPDATES_LEDGER.md`. Owner decision
recorded as **D33**; new fact **U54**, gotchas **G98–G99**. Closes `UPDATES_CLOSEOUT.md` §2 item 1
(P5d R10.1).

Built in its own git worktree reset to `origin/19.1` (G94).

## R0. Rollback note (written before deploying)

- **What the deploy changes.** `pb_updates` 19.0.1.7.3 → **19.0.1.7.4** on `payobook`,
  `payobook_template`, `p0clone`, `rize`, `sudima` (`-u pb_updates` on each, one service stop).
  Python (one flag on one helper + the tax summary's call and words), the tax summary template
  extension, the portal stylesheet, one new test file, 2 Vietnamese + 2 Indonesian entries appended.
  **No field, table, record rule, job or mail. No stored data is written** by the upgrade or by the
  code: only how the employee's own tax summary READS its totals.
- **Backups.** Tier 3 as P5d: five `pg_dump -Fc` first, in `/odoo/backups/updates-p5e-<TS>/`, with
  the previous module tree `pb_updates.prev`.
- **Restore** = scoped `rsync -a --delete pb_updates.prev/ /odoo/odoo-server/addons/pb_updates/`,
  stop, `-u pb_updates` on the five, asset signal + purge + version bump, start.
- **Pay runs.** No year-to-date mapping on any of the five databases (P5d R7) and the pay-run path
  is not changed at all (default of the flag); Y9 re-run (R5).
- Nothing is applied, mapped or loaded on `rize` or `sudima`.

---

## R1. What shipped

| Module | Version | What |
|---|---|---|
| `pb_updates` | 19.0.1.7.3 → **19.0.1.7.4** | D33 on the employee's own tax summary; tests A1–A5; 2 vi + 2 id entries |

Files: `models/updates_ytd.py` (`_person_window(..., count_pending=False)`; `_tax_summary_counted`
passes `True`, adds the words and `ytd_counted_for_now`), `views/ytd_portal.xml` (the outlined pill
with a Lucide clock for "counted for now"; the old pill markup is unchanged for every other row),
`static/src/scss/ytd_portal.scss` (`.pbme-taxrow-adv-now`), `tests/test_updates_p5e.py`,
`tests/__init__.py`, `i18n/vi_VN.po`, `i18n/id_ID.po`, manifest.

**Not touched:** `pb_me_portal`, the year-to-date view, its download, "Download for the pay run",
the popover, both pay-run seams, any tax formula, scheme, payslip or stored result, and the other
sessions' modules (`pb_lifecycle`, `pb_hiring`, `pb_me_expense`, `pb_timeoff`, attendance connector
modules, `docs/handovers/workflow2`).

## R2. The rule as coded (D33)

`_person_window(ledger, emp_id, covers_to=None, upper=None, count_pending=False)` — for a finished
advance payslip (`cycle_type = mid_cycle`):

| Its month has … | Default (view, downloads, popover, pay runs) — P5c/P5d | `count_pending=True` (tax summary only) |
|---|---|---|
| a finished month-end payslip of a linked scheme | `advance` — not added | same |
| a finished month-end payslip, no link between the two | `split` — shown apart, not added | same |
| no finished month-end payslip; its scheme IS linked to a month-end scheme | `advance_only` — not added, month not counted | **`pending` — counted** (added to the year's totals) |
| no finished month-end payslip; its scheme is linked to NO month-end scheme | `advance_only` | `advance_only` — unchanged (prompt rail) |

"Linked" = a row in `hr.payroll.cycle.component.mapping` for the advance's scheme (any end scheme,
archived rows included — the same table P5c reads). As soon as the month-end payslip is finished,
the next page load classifies the advance as `advance` again: nothing is stored.

On the page:

- The row pill reads **"Mid-month advance · counted until the month-end payslip is finished"**,
  outlined indigo with a Lucide clock (12 px), and may wrap; the "not added" / "shown apart" pills
  keep P5d's look and markup. The owner's example wording was "Counted until the month-end payslip
  is finished"; the "Mid-month advance ·" lead was kept so the row still says what it is, like its
  neighbours (R8.1).
- The note under the table, only when such a row exists: "Each month is counted once in the year to
  date: a mid-month advance is part of that month's month-end payslip, so it is not added again.
  Until that month-end payslip is finished, the advance is counted on its own." Otherwise P5d's note
  is unchanged.
- Totals: the pending advance's amounts are read off its own lines with P5c's `_slip_amount` and
  shown in the page's sign (`_row_sign`): on the demo world the advance's lines carry pay role
  "information", so they are added exactly as the page prints them.

## R3. Tests

| # | Case | Result |
|---|---|---|
| A1 | QUA: April + May linked advance and month-end, June the linked advance only (100,000 gross, −10,000 tax, −8,000 contributions). Page alone 500,000. Now gross **300,000** = 200,000 month-end + 100,000 June advance; tax **−30,000**; contributions −24,000. June row: "Mid-month advance · counted until the month-end payslip is finished" (`ytd_counted_for_now` = [June]); April/May advances "Mid-month advance · not added"; the new note; rows unchanged | PASS |
| A2 | The June month-end payslip is then finished: gross **300,000** (3 month-ends), tax −30,000; the June advance reads "not added"; nothing "counted for now"; P5d's note; **equal to the year-to-date view** (gross, tax, contributions) and months counted 3 | PASS |
| A3 | Same QUA before June's month-end: the helper's default still says `advance_only` and leaves it out; year-to-date view paid gross 200,000, tax 20,000, months 2; the popover lists 2 payslips counted, not the June advance; with figures before Payobook to 31 March and a mapping, a July pay period is **refused** (`_plan_blocked`), "Download for the pay run" gives her no value and no adjustment row | PASS |
| A4 | YAN (no advance): page values identical (`qc == page`). RIA (an advance of a scheme linked to NOTHING, no month-end that month): not added, "Mid-month advance · waits for month end", nothing counted for now (P5d). ZOE (every advance has its month-end) and WES (unlinked advance + month-end, shown apart 70,000) exactly as P5d | PASS |
| A5 | No vendor name in the new sentences; the template carries `ytd_counted_for_now` | PASS |
| A5 | Full `pb_records` + `pb_updates`, local isolated tree (this worktree), copy of `upd_p3c_t_tpl`, `-u pb_records,pb_updates,pb_import_advanced,pb_clock` | **343 tests, 0 failed, 0 errors** (P5d's 10 and P5c's 18 unchanged and green); one ERROR line = the expected "Error processing line" of P5 Y6c (G68) |
| A5 | `.po` parse gate (`PoFileReader`): vi_VN 1,456 rows (1,454 + 2), id_ID 10 rows (8 + 2), every new entry has `#. module:` + `#. odoo-python` + `#: code:`; 0 placeholder mismatches; 0 "Odoo" in any msgstr; 0 new duplicates (30 pre-existing same-text rows, unchanged); the old files are byte prefixes of the new ones | PASS |

P5d's test class is reused by subclassing (`TestUpdatesP5e(TestUpdatesP5d)`, its company, schemes and
link); the Odoo test loader runs only a class's own methods, so P5d's cases still run once (G98).

## R4. Browser (local copy of live payobook, console read)

Local copy of live payobook (`upd_p5e_pay` = a copy of P5d's walk copy), `127.0.0.1:8899`,
before = P5d's code (commit on `origin/19.1` before this phase), after = this phase's code with
`-u pb_updates`. Browser: Claude in Chrome (G99), signed in to the LOCAL copy only. **Console: 0
errors.** Screenshots in `outputs/updates-p5e/` (main tree, not committed):

- `01-tax-summary-9409-before.jpg` — demo person 9409: gross 58,478,450, tax **0**; the June advance
  row says "Mid-month advance · waits for month end".
- `02-tax-summary-9409-after.jpg` and `03-tax-summary-9409-after-rows.png` — gross **81,199,445**
  (= 58,478,450 + the June advance 22,720,995), social insurance −3,328,000, tax **−91,450** (= the
  June advance's tax); the June pill is outlined with a clock and reads "Mid-month advance · counted
  until the month-end payslip is finished"; the April/May advances keep "not added"; the new note.

HTTP capture of the page (tiles, every table row, notes), before vs after:

| Person | Advances | Result |
|---|---|---|
| 12092, 12105, 12501 | none | **identical** (tiles, rows, notes) |
| 9409 | April/May linked + June advance without month-end | gross 58,478,450 → 81,199,445; tax 0 → −91,450 |
| 9884 | same shape | gross 174,039,426 → 195,562,664 (+ June advance 21,523,238; this copy also carries P5d's walk figures before Payobook); tax −4,298,738 → −4,540,850 |

The visible page text holds no vendor name (`document.body.innerText`). A 1,920 px page has no
horizontal scroll; the new pill wraps under the period name when the column is narrow.

## R5. Y9

P5's `y9_capture.py` (P2d's E1): Retail end-month, 12 people, December 2026, six modes, on a fresh
restore of the read-only live payobook dump of 2026-11-12 (P5b's), jobs and mail off. With this
phase's code, without and with two mappings + figures for 20 other people: **`e1_new0.json` and
`e1_new1.json` are byte-identical to P5d's** (`no-file 4ecfc38110407470`, `pay-file
d88c66c183d0edd1`, `template f9755a528c321347` — the hashes P5 recorded).

## R6. Deploy evidence

Tier 3, as P5d. `/opt/deploy-notes.md` read first (last entries: the Attendance connector
deploys, all DONE/VERIFIED; no open START); START and DONE lines appended; flock
`/tmp/payobook-studio-deploy.lock` (free); unit `updates-p5e-20261113T211057Z`; evidence
`/tmp/updates-p5e-20261113T211057Z/` on the server.

- **Deployed from the pushed commit** `8edb68c13`: `git archive` → staging; tree hash
  `ae9489b8c7d158c2` (58 files) = worktree = staging = server after the copy. Dry-run before
  (`rsync -anc`): content differs only in this phase's 8 files (manifest, 2 po, model, scss,
  tests `__init__`, new test file, portal template); the server's tree before was P5d's commit
  (`e78d0cb8c10cead3`) — nobody else had changed `pb_updates`.
- **Dumps first**: `/odoo/backups/updates-p5e-20261113T211057Z/` — payobook 78M, payobook_template
  27M, p0clone 28M, rize 40M, sudima 28M; previous tree `pb_updates.prev`.
- **Downtime 86 s** (stop 21:12:35, listening 21:14:01 UTC): `-u pb_updates` on the five, EXIT=0
  each, 0 ERROR in the five upgrade logs. No test ran in the stopped window (G19).
- Jobs: an `id → active` snapshot of every job before; after the upgrades each job was set back to
  exactly its before-state (nothing needed changing: 0 rows each) and compared again after start.
- Assets: signal row + `/web/assets/%` purge + `web.assets.version = upd-p5e-20261113T211057Z` ×5.

| Check | payobook | payobook_template | p0clone | rize | sudima |
|---|---|---|---|---|---|
| `pb_updates` latest_version | 19.0.1.7.4 | 19.0.1.7.4 | 19.0.1.7.4 | 19.0.1.7.4 | 19.0.1.7.4 |
| tree hash | `ae9489b8c7d158c2` = commit | ← | ← | ← | ← |
| jobs id → active, before / after | identical (51 active) | identical (32) | identical (40) | identical (83) | identical (82) |
| data counts before / after (users, payslips + inputs/results hash, lines, runs, joining dates, year-to-date rows, batches, mail queue) | identical | identical | identical | identical | identical |
| languages active | en, vi, id | en, vi, id | en, vi, id | en, vi, id | en, vi, id |

- Server log since the stop: **0 ERROR / CRITICAL**; one service process; payobook.com,
  rize, sudima, p0clone answer 200.
- **Live suites on p0clone after start** (service running, ports 8471/8472, no upgrade): `pb_records` 134 + `pb_updates` (343 tests in all), **0 failed**; one ERROR line = the expected "Error processing line" of P5 Y6c (G68). DONE line appended to `/opt/deploy-notes.md` after this.

## R7. Live checks (read only)

`odoo-bin shell` on the server after the deploy, log files in the evidence folder, ports
8475/8476 and 8477/8478, **rolled back** (`live_ro.py`); nothing written anywhere; no password used
on any live site.

**payobook** (figures before Payobook 0, mappings 0 — no pay run reads any of this):

| Demo person | Page alone (no counting) | P5d (yesterday) | **Now** | Year-to-date view (unchanged) |
|---|---|---|---|---|
| **9409** | gross 119,266,856, tax −91,450 | gross 58,478,450, tax **0** | gross **81,199,445**, tax **−91,450** = her June advance's tax (−91,450) | paid gross 58,478,450, tax 0, months 3 |
| 9884 | gross 149,988,367, tax −2,207,002 | gross 83,039,426, tax −1,198,738 | gross **104,562,664**, tax **−1,440,850** (+ June advance 21,523,238 / −242,112) | paid gross 83,039,426, tax 1,198,738, months 4 |

Each has exactly one advance "counted until the month-end payslip is finished" (June) and two "not
added" (April, May).

**rize** (read only): 0 finished payslips, 0 figures, 0 mappings, no advance scheme — nothing on
Rize's pages changes.

## R8. Deviations, and why

1. **Pill wording** "Mid-month advance · counted until the month-end payslip is finished" instead of
   the owner's example "Counted until the month-end payslip is finished": the first walk showed the
   bare sentence on a row with nothing else saying it is an advance (the other advance rows say
   "Mid-month advance · …"). The note under the table uses the owner's sense word for word.
2. **An advance of a scheme linked to no month-end scheme and with no month-end payslip** keeps
   P5d's pill "Mid-month advance · waits for month end" and is not counted (prompt rail; once its
   month-end payslip is finished it becomes "shown apart", as P5d). Not changed, as instructed.
3. **Commit attribution** uses the session's own line (`Co-Authored-By: Claude Opus 5.5`).
4. **Main tree not brought up to date by this agent** (G96): run `fetch` + `merge --ff-only
   origin/19.1` from a session working in `/Users/adity/Documents/GitHub/gitlocal`.

## R9. For the owner

Nothing blocks. One thing to know: on payobook.com every demo employee with a June mid-month advance (the demo's
open month, whose month-end payslips are drafts) now sees June's advance in their year totals on
their own tax summary, with the new label. The People › Updates year-to-date screen still leaves
it out and still says June is not finished — the two screens now differ on purpose for such people
until June's month-end payslips are finished (D33).
