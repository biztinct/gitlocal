# UPDATES — Phase 5d report (tax summary counts each month once; mid-year joiners)

Implemented, tested, deployed and checked on 2026-11-13 by the Opus implementation agent, against
the owner's prompt of 2026-11-13 (the prompt was the spec) and `UPDATES_LEDGER.md`. Owner decisions
recorded as **D29–D32** (A–D of the prompt). New facts **U52–U53**, gotchas **G94–G97**.

Built in its own git worktree branched from `origin/19.1` (G94): another session's deploy had taken
Phase 5c's uncommitted code live from the shared working tree on 2026-11-12 (G93).

## R0. Rollback note (written before deploying)

- **What the deploy changes.** `pb_updates` 19.0.1.7.2 → **19.0.1.7.3** on `payobook`,
  `payobook_template`, `p0clone`, `rize`, `sudima` (`-u pb_updates` on each, one service stop).
  Python, the year-to-date screen's XML/SCSS, the tax summary template extension, one new frontend
  stylesheet, one new test file, Vietnamese entries appended, one new Indonesian file.
  **No field, table, record rule, job or mail. No stored data is written** by the upgrade or by the
  code: everything is in how numbers are READ.
- **Backups.** Tier 3: five `pg_dump -Fc` first, in `/odoo/backups/updates-p5d-<TS>/`, with the
  previous module tree `pb_updates.prev`.
- **Restore** = scoped `rsync -a --delete pb_updates.prev/ /odoo/odoo-server/addons/pb_updates/`,
  stop, `-u pb_updates` on the five, asset signal + purge + version bump, start. The dumps are only
  needed if something unexpected wrote data (nothing in this phase does).
- **Pay runs.** There is no year-to-date mapping on any of the five databases (census R9), so no pay
  run reads any of this; Y9 re-run (R6).
- Nothing is applied, mapped or loaded on `rize` or `sudima`.

---

## R1. What shipped

| Module | Version | What |
|---|---|---|
| `pb_updates` | 19.0.1.7.2 → **19.0.1.7.3** | D29 tax summary counted like "paid in Payobook"; D31 mid-year joiners paid in Payobook alone; tests Z1–Z7 (10 cases); 8 Vietnamese entries appended; `id_ID.po` (8 entries, new) |

Commit `3994b1cce` (code, pushed to 19.1 before the deploy), plus the docs commit. Files: `models/updates_ytd.py`
(`_tax_summary_counted`, `_summary_sign`, `_row_sign`; `_joined_in`, `_joiner_covered`,
`_joiner_label`, `_joiner_plan`, `_plan_ledger`; `_plan_for_slip` calls them),
`models/updates_ytd_desk.py` (`_ytd_rows`, `_ytd_cell_note`, `get_ytd_cell_detail`,
`download_for_payrun`), `models/updates_ytd_payrun.py` (`ytd_key`, `joined` in the payslip's
sources), `controllers/ytd_portal.py`, `views/ytd_portal.xml`, `static/src/xml/updates_ytd.xml`,
`static/src/scss/updates_desk.scss`, `static/src/scss/ytd_portal.scss` (new, `web.assets_frontend`),
`tests/test_updates_p5d.py`, `i18n/vi_VN.po`, `i18n/id_ID.po`, manifest.

**Not touched:** `pb_me_portal` (not edited — override only), any tax formula, scheme rule, payslip,
stored pay result, application-data certification, `history.ytd`, and the other session's modules
(`pb_lifecycle`, `pb_hiring`, `pb_me_expense`, `pb_timeoff`, `pb_clock`, `docs/handovers/workflow2`).
No change for D30 (same pay period twice) and D32 (month below zero).

## R2. D29 — the employee's own tax summary (how it was changed)

**By override, not by editing `pb_me_portal`.** `pb_updates` already overrides `/my/taxsheet`
(P5, `controllers/ytd_portal.py`): the page's own values are computed by `pb_me_portal` exactly as
before, then `_tax_summary_counted` runs, then P5's `_tax_summary_opening` (figures before Payobook).
The main tree was not consulted for `pb_me_portal` because nothing in it was edited.

What `_tax_summary_counted` does (reusing P5c's helpers, nothing copied):

1. Reads the page's own payslips of the summary's year (`qcontext['rows']`, done payslips, the 48
   latest) and the person's ledger (`_ledger`) for the summary's codes.
2. **If none of those payslips is a mid-month advance, it returns at once: the page is exactly as
   before** (U52).
3. Otherwise it keeps only amounts read off payslip LINES (the page never shows stored results) and
   classifies every payslip with `_person_window`: counted, advance (linked → not added), advance
   whose month-end payslip is not finished (not counted, like P5c), advance that cannot be matched
   (shown apart, not added).
4. Each code's year total = the sum of `_slip_amount` over the counted payslips — P5c's signs: pay
   figures keep their sign; a deduction / employer cost is an amount in the scheme's usual sign, so
   a refund month reduces — written back in the page's own sign (`_summary_sign`: the scheme's
   usual sign on the latest payslip that has it; a deduction the scheme writes negative stays
   negative on the page, exactly as before).
5. The rows are untouched; each advance row gets a small indigo pill: "Mid-month advance · not
   added" / "· waits for month end" / "· shown apart"; under the table one plain note ("Each month
   is counted once in the year to date …") and, when there are any, the unmatched advances' amounts
   per column, apart.

## R3. D31 — the rule as coded (mid-year joiners)

For one person, one figure, one tax year, when the person has **no stored "before Payobook" line
for that figure** in that year (`pb.updates.ytd.line`, state `set`):

```
joined  = employee.date_of_joining            # the employee record only; NEVER the contract start
          and joined.year == tax year          # (a)  blank -> stays "not known" (D27)
pay run: and joined <= the pay period's last day
window  = _person_window(ledger, emp, covers_to=None, upper=<pay period's first day> | None)
counted = window['counted']                    # P5c: advances never added, each month once
if no counted payslip:
    complete only in a pay run whose period starts in or before the joining month (nothing in between)
else:
    first = counted[0]                         # earliest end date
    (c) month(first.date_from) <= month(joined)
    (b) every month from month(first.date_to) to <the month before the pay period> (pay run)
        or to the latest month counted (view) has a counted payslip
    and the figure itself is 'complete' under P5c (_figure_paid: every payslip that should carry
        it does; no advance that cannot be matched); "Months counted" = months in the window
then: before = 0, paid = P5c's paid in Payobook, total = paid, a year total,
      "Joined <d MMM y> — Payobook payslips only"
else: exactly P5c ("Known so far", "Not covered: …", nothing reaches a pay run)
```

Where it shows / goes:
- **Year-to-date view**: the cell is a total with an indigo chip "Joined 1 May 2026 — Payobook
  payslips only"; the cell's sentence (and the view download's "complete?" column) starts with it;
  "How this number was worked out" shows it as its own line. A person with no figures at all who
  qualifies loses the row chip "Not covered: …" (by (c) nothing is uncovered).
- **"Download for the pay run"**: the value, "Joined … — Payobook payslips only" in Check, and a
  Monthly adjustments row whose reason reads "Year-to-date figures from Updates: joined 1 May 2026,
  700000 paid in Payobook (Payobook payslips only)." An item that does not qualify for the same
  person stays blank with a sentence.
- **Pay runs** (both seams, every non-application mode): the mapped item receives the value; the
  payslip's sources record `key: updates_ytd:joined`, `ytd: {before: 0, paid, value, joined, slips}`.
  There is no figure row, so nothing is held in `pb.updates.ytd.use` (nothing to lock); a figure
  loaded later replaces this rule for later payslips.
- A person WITH a figure row for that figure: the row wins, unchanged (Z5). Rule C is per figure:
  a person with a gross figure but no tax figure can receive tax under rule C if they qualify.

## R4. Tests

| # | Case | Result |
|---|---|---|
| Z1 | ZOE: linked advance + month-end April–June. Page alone: gross 600,000, tax −60,000. Now gross **300,000**, tax **−30,000**, employee social −24,000; equal to the year-to-date view's paid in Payobook (300,000 / 30,000 / 24,000); 6 rows still listed, the 3 advances say "Mid-month advance · not added" | PASS |
| Z2a | YAN: month-end only → the whole page value set identical (`qc == page`), gross 270,015 | PASS |
| Z2b | XIA: advances + figures before Payobook (500,000 up to 31 Mar) → gross 800,000; the "Before Payobook (up to 31 Mar 2026)" row still there | PASS |
| Z2c | WES: an advance linked to nothing (70,000) + month-end (100,000) → 100,000 counted, 70,000 shown apart, not added | PASS |
| Z2d | the page template carries the new parts | PASS |
| Z3 | JOY joined 1 May, month-end payslips May→November, no figures: view gross 0 + 700,000 = 700,000, a year total, "Joined 1 May 2026 — Payobook payslips only" (cell, sentence, popover); months 7; tax 70,000. December payslip with three mappings: gross 700,000, tax 70,000, months 7 + 1 = 8; sources `updates_ytd:joined`, before 0 / paid 700,000; nothing locked; "Download for the pay run": 700,000, the sentence, 3 adjustment rows "joined 1 May 2026" | PASS |
| Z3b | PIA joins 1 December: December payslip receives 0 and month 1; a November pay period (before joining) receives nothing | PASS |
| Z4 | KIM (June missing), LEO (no joining date), MIA (joined 2025), NED (first payslip June, joined May): not a total, no "Joined" text, plan `{}`, the December payslip gets nothing from Updates, download says "No figures before Payobook for 2026", no adjustment row; P5c's chips stand (KIM 1 month missing; LEO and MIA "Not covered" January–April; NED May) | PASS |
| Z5 | OLA joined May WITH a gross figure (50,000 up to 30 Apr): 50,000 + 700,000 = 750,000 from the figure row, no "Joined" text, `line_id` set | PASS |
| Z6 | full `pb_records` + `pb_updates`, local isolated tree (the worktree), copy of `upd_p3c_t_tpl`, `-u pb_records,pb_updates,pb_import_advanced,pb_clock` | **134 + 276, 0 failed** (P5c's 18 and P5's cases unchanged and green; one expected G68 line) |
| Z6 | Y9 — see R6 | see R6 |
| Z6 | review 4,575 × 73 — see R6 | see R6 |
| Z7 | `.po` parse gate (`PoFileReader`): vi_VN 1,454 rows (P5c 1,446 + 8), id_ID 8 rows, all 8 new reach a screen (`#. module:` + `#. odoo-python` + `#: code:`), 0 placeholder mismatches, 0 "Odoo" in any msgstr, 0 new duplicates (30 pre-existing same-text rows, unchanged); vi_VN.po old file is a byte prefix of the new one. Z7 test + P5 Y12 scan: no vendor name in any new sentence | PASS |

## R5. Browser (local copy of live payobook, 127.0.0.1:8897, console read: 0 errors)

Screenshots in `outputs/updates-p5d/` (main tree, not committed):

- `01-tax-summary-before.jpg` — demo person 9884 (ess2.demo, has advances and walk figures before
  Payobook on this copy): gross 240,988,367; April and May each listed twice and added twice.
- `02-tax-summary-after.jpg` — gross **174,039,426** = 91,000,000 before Payobook + 83,039,426
  (April, May, July, November month-end payslips); the three advances carry indigo pills; the note
  under the table. The year-to-date view shows the same 174,039,426 for this person (and a shell
  check: gross and tax equal, R7).
- `03-ytd-joiner-cell-and-popover.jpg` — demo person 10913 (joined 4 May 2026, no figures): every
  figure cell carries "Joined 4 May 2026 — Payobook payslips only"; the popover lists the May
  month-end payslip counted, two advances not counted with why, and the joined line.

Before/after HTTP capture of the tax summary page (`capture.py`, tiles + table + notes), old code
(P5c, commit on origin/19.1) vs new code on the same copy:

| Person | Advances | Result |
|---|---|---|
| 12092, 12105, 12501 (local self-service logins made on the copy) | none | **identical** (tiles, every table row, notes) |
| 9884 | yes | gross 240,988,367 → 174,039,426; tax −5,307,002 → −4,298,738 |
| 9409 | yes | gross 119,266,856 → 58,478,450; tax −91,450 → 0 (the only tax was on the June advance, whose month-end payslip is not finished: "waits for month end") |

The pill was first written with an inline style; the portal ignores inline styles (G95) — moved to
a frontend stylesheet, re-walked.

## R6. Y9, speed

| Check | Where | Result |
|---|---|---|
| **Y9** (P5's `y9_capture.py` = P2d's E1): Retail end-month, 12 people, December 2026, six modes (no file compute + recompute, pay file create + recompute, monthly template create + recompute) | a fresh restore of the read-only live payobook dump of 2026-11-12 21:26 UTC (P5b's), jobs and mail off, never walked on | old code (P5c) and new code, each without a mapping and **with two mappings + figures for 20 other people (and 2025 figures for these 12)**: **4 of 4 runs identical, 6 of 6 modes each**, and identical to the hashes P5 recorded: no-file `4ecfc38110407470`, pay-file `d88c66c183d0edd1`, template `f9755a528c321347`; `e1_old0.json` = `e1_new0.json`, `e1_old1.json` = `e1_new1.json` byte for byte. None of the 12 joined in 2026 (joining dates 2019–2025), so D31 does not reach them. |
| First attempt on P5c's walk copy | — | discarded: that copy carries P5c's walk figures and codes (pay-file hash differs before any change, and the mapped old run stops on a walk person's missing months). Not a finding. |
| review 4,575 × 73 | local copy of live payobook | **14.8 s / 15.3 s** (≤ 25 s), 0 changes, 60,080 same, 1,499 unmatched — as P5/P5c |
| year-to-date view, first page (4,476 people) / whole-roster view download | same | 1.45 s / 13.4 s (P5c 1.85 s / 11.9 s; measured while another local run was busy) |
| employee tax summary page | same, HTTP | no measurable change; the extra work happens only for a person whose year has an advance (one ledger read of their own payslips) |

## R7. Live checks (read only)

`odoo-bin shell` on the server, after the deploy, log files in the evidence folder, ports
8475/8476 and 8477/8478, **rolled back** (`live_ro.py`); nothing written anywhere.

**payobook** (viewer = the QA login, server-side and read only; no password used on any live site):

| | Result |
|---|---|
| figures before Payobook / mappings / figure set-ups | 0 / 0 / 0 — so no pay run reads any of this |
| demo person 9884 (has advances), tax summary year 2026 | page alone: gross 149,988,367, tax −2,207,002; **now gross 83,039,426, tax −1,198,738**, 3 advances marked "not added" |
| the same person in the year-to-date view (as the QA user) | gross total **83,039,426**, tax **1,198,738** → **equal** (gross and tax) |
| rule D31 on payobook | 283 active people joined in 2026, 280 with finished payslips, **85 now read "Joined … — Payobook payslips only"** (all Payobook Vietnam JSC, the demo world) |
| browser, look only, an existing session (no sign-in) | Updates › Year-to-date figures, demo person "Lê Phương Trang" (joined 4 May 2026): every cell carries the joined chip; console 0 errors (`outputs/updates-p5d/04-live-payobook-joiner.jpg`) |

**rize** (read only):

| | Result |
|---|---|
| figures / mappings / set-ups / finished payslips | 0 / 0 / 0 / **0** (487 drafts) |
| active people / joined in 2026 / joining date blank | 241 / **38** / **132** |
| **would qualify under D31 today** | **0** — nothing is finished yet. When Rize's payslips are finished, the 38 people who joined in 2026 can qualify (if each month from their joining month is finished); the 132 with a blank joining date stay "not known" (D27, D31 (a)). |
| anything else changed | no: the deploy's before/after counts (users, payslips with their inputs/results hash, lines, runs, employees with joining dates, year-to-date rows, batches, mail queue) are identical, job id list identical (83). |

## R8. Deploy evidence

Tier 3. `/opt/deploy-notes.md` read first (last entries: the Attendance connector deploys, all
DONE/VERIFIED; no open START); START and DONE lines appended; flock
`/tmp/payobook-studio-deploy.lock` (free); unit `updates-p5d-20261113T032205Z`; evidence
`/tmp/updates-p5d-20261113T032205Z/` on the server.

- **Deployed from the pushed commit**: `git archive 3994b1cce pb_updates` → staging; tree hash
  `e78d0cb8c10cead3` (57 files) = worktree = staging = server after the copy. Dry-run before:
  content differs only in this phase's files (manifest, controller, 3 models, 2 po, 2 scss, 2 xml,
  tests); every other file identical apart from timestamps; the server's tree before was P5c's
  commit (`1a7928b8ec579630`, = `origin/19.1` before this phase) — nobody else had shipped P5d.
- **Dumps first**: `/odoo/backups/updates-p5d-20261113T032205Z/` — payobook 76M, payobook_template
  27M, p0clone 28M, rize 40M, sudima 28M; previous tree `pb_updates.prev`.
- **Downtime 87 s** (stop 03:23:42, listening 03:25:09 UTC): `-u pb_updates` on the five, EXIT=0
  each, 0 ERROR in the five upgrade logs. No test ran in the stopped window (G19).
- Assets: signal row + `/web/assets/%` purge + `web.assets.version = upd-p5d-20261113T032205Z` ×5.

| Check | payobook | payobook_template | p0clone | rize | sudima |
|---|---|---|---|---|---|
| `pb_updates` latest_version | 19.0.1.7.3 | 19.0.1.7.3 | 19.0.1.7.3 | 19.0.1.7.3 | 19.0.1.7.3 |
| tree hash | `e78d0cb8c10cead3` = commit | ← | ← | ← | ← |
| active jobs before / after (id lists) | 51 / 51 identical | 32 / 32 | 40 / 40 | 83 / 83 | 82 / 82 |
| data counts before / after | identical | identical | identical | identical | identical |
| figures / mappings | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| languages active | en, vi, id | en, vi, id | en, vi, id | en, vi, id | en, vi, id |

- **Live suites on p0clone after start** (service running, ports 8471/8472, no upgrade):
  `pb_records` 134 + `pb_updates` 276, **0 failed**; one ERROR line = the expected "Error processing
  line" of P5 Y6c (G68).
- Server log since the stop: **0 ERROR / CRITICAL**. Sites answer 200 (payobook, rize, sudima,
  p0clone). One service process.

## R9. Deviations, and why

1. **Commit attribution** uses the session's own line (`Co-Authored-By: Claude Opus 5.5`) instead
   of the prompt's "Claude Fable 5.2": the code was written by the Opus agent.
2. **Rule C is applied per figure** (the prompt's "no stored line for a figure"): a person with a
   gross figure but no tax figure can receive tax under rule C.
3. **A pay period that ends before the joining date receives nothing** (Z3b): the prompt is silent;
   a payslip before joining means the joining date or the payslip is wrong.
4. **No figure row → nothing locked** in `pb.updates.ytd.use` (there is no row to lock); the
   payslip's own sources say where the number came from.
5. **The tax summary of a person whose year has no advance is left exactly as `pb_me_portal`
   builds it** (early return), as the prompt requires, even in the corner cases where P5c's signs
   would differ (two schemes writing a deduction with opposite signs; a payslip with two lines of
   one code).
6. **Indonesian**: `pb_updates` had no Indonesian file; `id_ID.po` is new and holds only this
   phase's 8 strings (so the rest of the Updates screens stay English for an Indonesian user, as
   before; the tax summary page's new lines are Indonesian).
7. **Main tree not brought up to date by this agent**: the worktree harness refuses any git command
   aimed at the main tree (G96). See R11.

## R10. For the owner

Nothing blocks. Two things the owner may want to know or choose:

1. **An advance whose month-end payslip is not finished yet** (the demo's June) is not counted on the
   employee's tax summary — the same rule as the year-to-date view (P5c). On payobook.com demo
   person 9409's tax for the year now reads 0: the only tax on her page sits on the June advance.
   The row says "Mid-month advance · waits for month end". If the owner prefers the summary to count
   such an advance until its month-end payslip is finished, that is a small change (summary only).
2. **Rize**: rule D31 needs the joining date on the employee record. 132 of Rize's 241 active people
   have none; for them the December year-to-date stays "not known" unless figures before Payobook are
   loaded or the joining date is filled in. (P5b/D27 already decided no joining date is filled in by
   Payobook.)

## R11. Git

- Code commit `3994b1cce` and the docs commit, each with explicit paths, credential scan clean
  (no password / token / secret in the diff), rebased on `origin/19.1` (no new commits there) and
  pushed `HEAD:19.1`.
- **Main tree not updated by this agent.** The worktree harness refuses any git command aimed at
  `/Users/adity/Documents/GitHub/gitlocal` (`git -C …` is blocked, G96), so the
  `fetch` + `merge --ff-only origin/19.1` there must be done from the main session. Nothing of this
  phase was ever written into the main tree; the screenshots are in
  `/Users/adity/Documents/GitHub/gitlocal/outputs/updates-p5d/` (not committed).
- Local copies used: `upd_p5d_pay` (walk copy: local passwords for five self-service logins and the
  admin, three local self-service logins created for people without one — local only),
  `upd_p5d_y9` (Y9), `upd_p5d_t_*` (suites).
