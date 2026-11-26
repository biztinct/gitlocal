# PSCHEME P3 — report: merge, lessons, release ×5, fill DRY RUN

Release engineer, 26–27 Nov 2026. Worktree `gitlocal-worktrees/pscheme`, branch `pscheme`, pushed to `19.1`.
Engineering document: real technical names on purpose. No client names, client figures or credentials here — the
dry-run table with names is only in the main checkout's `outputs/` (never committed).

## 1. Result

**LIVE ×5** (`payobook`, `payobook_template`, `p0clone`, `rize`, `sudima`; never abm) at `209907ade`, 26 Nov 2026
20:12–20:23 UTC, **629 s down**. Every upgrade exit 0 with only the three known `payroll_analytics` schema lines; versions =
manifests ×5; jobs = before ×5 plus the ONE new daily job; nothing re-activated on payobook; "who pays each active
person" identical before/after on all five; 0 ERROR in the server log since the stop; sites 200 ×5. **The one-time fill
was NOT applied and "Fill empty Country of Work" was NOT run anywhere** — dry run only (§7), the apply tool waits on the
server for the owner. A and B passed locally before the push. Live browser look: not done (§6.5) — owner asked for two
minutes.

| Commit | What |
|---|---|
| `59f6961a4` / `d470ab4c1` / `f4cd570a2` | A.1 merges: `pscheme-p2a`, `pscheme-p2b`, `origin/19.1` (§2) |
| `3565e1c5d` | A.3 "Upload sheet" source + A.4 `pb_scheme_map` whole in vi_VN and id_ID |
| `9ec7de00a` | B lessons, practice replica, anchors; Add employee no-team card |
| `d11451f3a` | C/D release scripts `p3/ps3_*` and the fill tool |
| `209907ade` | A.4 plural fix ("recent pay run(s)"), ledger PS-c1..PS-c5 — **pushed to 19.1** (`5d01d4371..209907ade`, fast-forward) |
| (this file) | report |

## 2. Merge notes (A.1)

- `pscheme-p2a` merged clean (no conflicts).
- `pscheme-p2b`: conflicts only where both streams appended — `pb_scheme_map/__manifest__.py` (2.7.0 vs 2.6.1 →
  **19.0.2.8.0**), `tests/__init__.py` (both imports kept), the three `pb_scheme_map` i18n files (rebuilt as P2a's
  file + P2b's two appended entries; git had interleaved the hunks mid-entry), the ledger (both gotcha lists kept).
- `pb_hr_payroll_formula`: only P2b had bumped it (1.175.0); one more bump → **19.0.1.176.0**.
- `origin/19.1` (19 commits of DOCSTUDIO close-out, incl. `pb_learn` 19.0.20.10.0) merged clean.
- Ledger R10 (lessons ARE updated) survived both merges.
- Architect confirmations applied: P2a deviations 1–10 kept as built; P2b-3 fixed (A.3).

## 3. A — tidy and tests

**A.3** `pb.person.scheme.source` gains `('sheet', 'Upload sheet')`. Updates writes it for a new-employee row
(`updates_person_scheme.py:236`) and for a lasting sheet's pay scheme change (`:498`); a person a pay data file
creates keeps `import` ("Pay data file"). Board label added. Tests `pb_updates` T8 and `test_H6` updated deliberately
(`'import'` → `'sheet'`).

**A.4** `pb_scheme_map` catalogues checked against a fresh `odoo-bin i18n export` of the merged code (479 terms):
- vi_VN: 23 missing (the PS-a8 strings of other sessions + "Upload sheet" + "Advance") → translated.
- id_ID: 167 missing (the old stub gap + the same 23) → translated (vocabulary of the existing file: skema gaji,
  tim, penggajian, Pemetaan).
- the repo `.pot` lacked 26 exported terms → added. After the fix: export 479 = in `.pot`, 0 missing in vi, 0 in id;
  placeholders kept; 0 vendor word; Odoo's own `PoFileReader` parses both (513 entries).
- Found by the suite: the Mapping suggestion line's plural hack (`pay run<t t-if>s</t>`) exported a lone "s" no
  translation can carry (`test_p7_vietnamese` t4/t4c failed only after). Rewritten as whole phrases "recent pay run"
  / "recent pay runs" (vi + id). PS-c2.

**A.2 suites (same before/after rule).** Tags `/pb_scheme_map,/pb_new_hire,/pb_payrun_wizard,/pb_hr_payroll_formula,
/pb_employee_vault,/pb_contracts,/pb_updates,/pb_job_change,/pb_loans,/pb_retro,/pb_expense_payroll,/pb_pay,/pb_me_tax,
/pb_decision_room,/pb_pay_package,/pb_import_wizard,/pb_import_batch,/pb_learn` on two copies of `p3_base` (= `ps_base`
+ `pb_pay_package` at `origin/19.1` code). "Before" = `git archive origin/19.1` (`5d01d4371`) as the addons path.

| | Tests | Failed | Errors |
|---|---:|---:|---:|
| before (`origin/19.1`) | 2,210 | 12 | 7 |
| after (`9ec7de00a`) | 2,281 (+71 new) | 14 | 7 |
| after the plural fix, `/pb_scheme_map` re-run (`209907ade`) | 99 | 0 | 0 |

- The two extra "after" failures were `pb_scheme_map` `TestVietnameseIsComplete` t4 / t4c (the lone "s", above),
  fixed and re-run green. **Every other failing line is byte-identical before and after**: P1's environmental list
  (`TestS5fLeaverBackpay` F01–F09, the two duplicate-key fixtures, `TestCd1Contract360.test_01`,
  `TestDecisionRoomStaticContract.test_t14`, `TestRd49SyncCost` 02ab / 02i, `TestRecordsR1OneTime.test_07b`,
  `TestS2dTaxFlow.test_t9`, `TestT3bLetterToken.test_t3b_9`, `pb_pay` `TestVietnameseIsComplete.test_t4c`) plus five
  `pb_learn` lines already failing on `origin/19.1` (`TestAnchorRegistry.test_05`, `TestComposer.test_03b`,
  `TestGuideTruth` 02 / 02b, `TestLearnrevP4.test_c1`). Nothing fails only after; nothing fails only before.
- Per-module counts after: scheme map 99, new hire 232, job change 39, Updates 308, pay package 26, formula 835,
  learn 494, pay-run wizard 159 (the rest unchanged).
- `gen_learn_data.py --check` clean; `check_contract.py` exit 0.

**A.2 walks** (local `p3_w` = the P2a walk world upgraded to the merged code; Claude-in-Chrome; console read):

| # | Where the streams meet | Result |
|---|---|---|
| (i) | Change job (P2b) for a person on Indonesia monthly staff with an IDR contract → Country of work Singapore, Singapore monthly staff, from today (sent through the board's own `send`, approved by its two approvers). People › side panel › Pay & tax: **"Singapore monthly staff · SGD · Their own pay scheme since 26 Nov 2026"**, the P2a contract note **"Their contract is now in SGD. Check their pay amounts."** with Open the contract / Got it, no amber line (country and scheme agree), "Paid by" chip the same; full form: Country of Work Singapore, salary in SGD. Rows: old one ends 25 Nov, new `job_change` row from 26 Nov. | pass |
| (ii) | Upload sheet (P2b) with one joiner (Indonesia, "Indonesia monthly staff") → judged "Their own pay scheme, from the sheet." → added after approval → row `source = sheet` from 1 Dec. Mapping board (P2a): Indonesia Operation "85 have their own" lists the joiner "Indonesia monthly staff · Since 1 Dec 2026"; the fill drawer: "Already have their own: 89" (= every person with a row, the joiner included), the joiner in no group. Drawer closed without applying. | pass |
| console | errors only, both walks and the lessons walk | clean |

## 4. B — lessons (R10)

Edited in the AUTHOR SOURCE `docs/tutorial_poc/author/data.js` and generated (PS-c1); `pb_learn/i18n/vi_VN.po`
untouched (compared byte for byte). `pb_learn` **19.0.20.11.0**. Every line en + inline vi:

| Where | Now teaches |
|---|---|
| Glossary "division" | a division can have a usual pay scheme; what pays a person is their own pay scheme |
| Add employee overview (`sc_people`) | the Country of work fills in the person's own pay scheme; another scheme of that country can be picked |
| Add employee practice, step 3 "Pick the team" — means | the country fills in the person's own pay scheme; the team is where they work, its usual scheme only a starting point |
| same step — affects | the Pay scheme box shows the scheme that will pay this person |
| Mapping station "Who is paid by what" line | each team's usual scheme, who has their own; Give everyone their own pay scheme starts here |
| Contract panel step "Paid by" — means | Paid by names the person's own scheme; Change pay scheme changes it from a date; a change during a month starts with the next pay run |
| Practice replica `engine/screens.js` (new employee) | Country of work → Team → **Pay scheme** chip "<scheme> · Usual" + "Filled in from the Country of work. This person's own pay scheme; you can pick another pay scheme of Vietnam." |
| `anchors.json` `nh-step-role` (product block, hand) / `rep-newemp-team` (practice block, generated) | re-described the same way |
| Product help: Add employee "Add a team first" card | "Every new person joins a team." (the "team decides how they are paid" clause gone; pot/vi/id) |

Walked on `p3_w` (Learning › Employees and contracts › Try): the replica draws the Pay scheme chip under Team; step 3's
card reads the new sentences in English and, after Tiếng Việt, in Vietnamese (replica too); console clean.

## 5. C — release (risky tier)

### 5.1 Timeline (UTC, 26 Nov 2026; Sydney 27 Nov)
| Time | Step |
|---|---|
| 19:43 | server state read after the session restart: no PSCHEME line in the deploy notes, last release DOCSTUDIO CLOSE (DONE 02:53, verified 03:03), no HOLD; `/tmp/payobook-studio-deploy.lock` an empty stale file nobody holds (PS-c5); service up; five sites 200; no copy or file of mine on the server |
| 19:45 | pushed `5d01d4371..209907ade` to `19.1` (fast-forward; nobody had pushed since the A.1 merge) |
| 19:48–19:52 | prep (`ps3_prep.sh`): staged = commit; live trees = `19.1` base ×11; previous trees saved; PO gate (0 vendor word); dependency closure (130 modules) installed ×5; vi + id active ×5; all eleven shipped modules installed ×5 (no new module anywhere); dumps ×5 read back + file folders linked; counts; job snapshots; who-pays on the old code ×5; 26 GB free |
| 19:53–19:57 | rehearsal on hidden `ps3_rh_rize` — passed (§5.2) |
| 19:57–20:09 | rehearsal on hidden `ps3_rh_payobook` — passed |
| 20:09 | START line; `ps3_tries.sh` in a systemd unit; 15 quiet minutes on rize/payobook/sudima, no HOLD, lock taken, go-live dumps ×5, who-pays ×5 on the old code |
| 20:12:23 | service stopped; per-module scoped `rsync --delete` of the eleven trees into `/odoo/odoo-server/addons` |
| 20:12–20:21 | `-u` of the eleven, one database at a time |
| 20:22:52 | service up; asset purge + `web.assets.version` ×5; DONE line 20:23; lock released |
| 20:23–20:27 | verification (`ps3_verify.sh`), read-only look as the QA user, NOTE line |
| 20:26 | fill DRY run on all five (§7) |

Other local sessions were not messaged before the stop (no agent list available to this session); the START line
in the deploy notes, the lock and the 15-minute quiet check were the coordination.

### 5.2 Rehearsals (hidden template copies, jobs + mail servers off first, dropped after)
| Copy | Result |
|---|---|
| `ps3_rh_rize` (313 people, 231 active) | `-u` exit 0 in 102 s, 3 ERROR (the known `payroll_analytics` lines), 0 Traceback; versions ok; who-pays old = new (md5 identical, 0 person rows); fill DRY wrote nothing; **REAL fill**: 227 people given their own scheme (`source fill`, saved at once), next month's pay runs: 227 people in a main run before and after, **0 in two main runs, 0 missing, 0 moved**, every filled person in exactly one main run; **Undo this fill** (`fill_undo`, the drawer's call): 227 rows removed, 0 left, pay-run population back to before; jobs: the new job only (28 re-activated on the copy, all were off — the go-live switches such ones back off) |
| `ps3_rh_payobook` (4,583 people) | `-u` exit 0 in 126 s, the same 3 known lines; versions ok; who-pays identical; fill DRY wrote nothing; new job only |
Data on both copies: identical before/after except the release footprint (two new empty columns
`hr_employee.pb_paid_by_own`, `hr_contract.pb_ps_check_amounts` move the chain's whole-row hashes; compared WITHOUT those
columns the rows are identical; +1 server action = the new job; a few technical chatter notes). Copies dropped (0 left).

### 5.3 Go-live
| Database | Exit / time / ERROR | Jobs active before → after |
|---|---|---|
| payobook_template | 0 / 98 s / 3 known | 40 → 41 (84, 85, 86, 91 re-activated by `-u`, switched straight back off) |
| p0clone | 0 / 96 s / 3 known | 49 → 50 |
| sudima | 0 / 96 s / 3 known | 91 → 92 |
| rize | 0 / 102 s / 3 known | 92 → 93 |
| payobook | 0 / 120 s / 3 known | 59 → 60 (none re-activated; job 156 still off) |
The +1 everywhere is `pb_scheme_map.cron_person_scheme_boundaries` (daily, active). **Downtime 629 s.**

### 5.4 Verification (live, read-only)
| Check | Result |
|---|---|
| Trees | all 11 = `209907ade` (byte-identical, `__pycache__` / `*.pyc` / `.DS_Store` skipped) |
| Versions | manifest = installed ×5 (pb_scheme_map 19.0.2.8.0, pb_hr_payroll_formula 19.0.1.176.0, pb_contracts 19.0.1.17.0, pb_import_batch 19.0.2.2.3, pb_import_wizard 19.0.1.4.2, pb_job_change 19.0.1.1.0, pb_new_hire 19.0.1.8.1, pb_pay_package 19.0.1.1.1, pb_payrun_wizard 19.0.1.49.0, pb_updates 19.0.1.9.0, pb_learn 19.0.20.11.0) |
| Jobs | prep snapshot → now: identical ×5 except the one new daily job; re-activated: none; switched off: none |
| Data right before the stop vs after | identical ×5 apart from the footprint in §5.2 (and the expected `x_` lines) |
| `pb.person.scheme` | exists ×5 with **0 rows**; `pb.person.scheme.fill` 0 rows |
| Who pays each active person (map answer per kind of run + next month's pay-run population per scheme) | **identical ×5** right before the stop (old code) and after (new code): payobook 4,582 people / 3 companies, template 1, p0clone 12, rize 231, sudima 678 |
| Compiled code | Pay scheme block, fill drawer, Country of work prompt, learn replica present ×5; "Upload sheet" source label ×5; vi + id active ×5 |
| Server log since the stop | 0 ERROR / CRITICAL, 0 Traceback, 0 asset errors; one service process |
| Sites | five × 200 |

### 5.5 Live look (C.5)
Not done in a browser: this session does not type a password into a live site, and the owner's admin login is never
used (NH76). Instead the screens' own calls were run **as the QA user** on payobook in a read-only shell (rolled back):
Mapping board allowed for companies 1, 2, 5, 6; banner figures "N people still follow their team" (21 / 7 / 4,554 / 0;
0 have their own; 0 paid by another country's scheme; no fill yet; "Give everyone…" offered); one person's Pay scheme
block (what the side panel and the Change pay scheme dialog read): "From <team>'s usual pay scheme" / "The only pay
scheme in this company", end-of-month, 7 / 1 choices, in English and in Vietnamese ("cuối tháng", "Theo chương trình
lương thường dùng của …"). **Owner: a two-minute look on payobook is asked for** (§9).

## 6. What is left
- **Server**: backups `/odoo/backups/pscheme-p3-20261126T2005Z/` (prep + go-live dumps ×5, file-folder links,
  `previous-trees.tgz`) and the fill tool in its `fill/` folder with the five dry-run folders (names only there);
  evidence `/tmp/pscheme-p3-20261126T2005Z/`. Rehearsal copies dropped (0). The weekly backup prune (Mondays 16:40
  UTC, keeps the newest 5, removes entries older than 3 days) may remove that folder from 30 Nov — the tool is also in
  the repo (`docs/handovers/pscheme/p3/`).
- **Local**: worktree `gitlocal-worktrees/pscheme` (kept for this report); `pscheme-p2a` / `pscheme-p2b` worktrees
  removed (branches kept); databases `ps_*`, `ps2a_*`, `ps2b_*` (except `ps_base`, `ps2b_base`) and `p3_*` (except
  `p3_base`, the live-like base for the next phase) dropped; no local server running. The `p3a_*`, `p3b_*`, `p3c_*`
  databases belong to other sessions and were not touched.
- **Main checkout**: `outputs/pscheme-fill-dry-run-2026-11-27/` (client table with team and scheme names + the raw
  dry-run files) — never committed.

## 7. D — the one-time fill: DRY RUN on live (nothing written)

`fill_apply(..., dry=True)` returns before any write (`pb_person_scheme_fill.py` `fill_apply`: `if dry or not groups:
return summary`; P2a T9), and `ps3_fill.py` also runs it inside a transaction that is rolled back and compares a
snapshot before/after (unchanged ×5). Rows on every live database after the dry runs: 0 / 0.

| Database | Company | People | Ready | From Country of work | Check these | Needs your choice: several | …: no scheme for the country | …: no Country of work | Already have their own | No Country of work (whole company) | "Fill empty Country of Work" would fill | The fill would give |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| payobook | 1 | 21 | 0 | 0 | 0 | 0 | 21 | 0 | 0 | 0 | 0 | 0 |
| payobook | 2 | 7 | 7 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 7 |
| payobook | 5 | 4,554 | 4,510 | 0 | 0 | 44 | 0 | 0 | 0 | 0 | 0 | 4,510 |
| payobook_template | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 (company country not offered) | 0 |
| p0clone | 1 | 12 | 0 | 0 | 0 | 0 | 0 | 12 | 0 | 12 | 0 (company country not offered) | 0 |
| rize | 1 | 231 | 227 | 0 | 0 | 0 | 0 | 4 | 0 | 4 | 4 (all from the company's country) | 227 |
| sudima | 1 | 678 | 0 | 0 | 0 | 0 | 678 | 0 | 0 | 0 | 0 | 0 |

Who would get which scheme (Ready + From Country of work), schemes named generically:
- payobook company 2: scheme 1 (VN, end of month) 7.
- payobook company 5: six VN end-of-month schemes, each with its paired VN mid-month advance (A13: a real advance
  only): 799 / 909 / 500 / 600 / 700 / 1,002 people.
- rize: scheme 1 (ID, regular) 126, scheme 2 (IN, regular) 29, scheme 3 (SG, regular) 2, scheme 4 (VN, regular) 70.
- sudima: none — its only pay scheme is still a draft, so every person reads "no pay scheme for their country yet".
- payobook company 1: its people's country has no active scheme in that company (demo).

**Apply command** (one database at a time, only after the owner says so; data only, no restart; refuses while
another release is open or a HOLD stands; writes START/DONE, takes a dump first, writes the undo record):

    sudo bash /odoo/backups/pscheme-p3-20261126T2005Z/fill/ps3_fill.sh <db> apply

(`<db>` one of the five; `… <db> dry` repeats the counts.) It ticks Ready + From Country of work only; Check these /
Needs your choice stay for a person in the drawer. Where a company has a second approver the request waits in
Approvals (pending, no rows until approved). "Fill empty Country of Work" is a separate screen action (People ›
Employees) and should run BEFORE the fill where wanted.

**Undo path**: Mapping › Who is paid by what › **Pay scheme fill** › **Undo this fill** (the latest fill of a
company; rehearsed on the rize copy: 227 removed, pay runs back to before); or the undo record
`<run folder>/person_scheme_fill_<db>.csv` (one `unlink` line per created row) in an `odoo-bin shell`; or the dump
`<run folder>/<db>-before-fill.dump` taken right before.

## 8. Gotchas (ledger §4)
PS-c1 (lesson content is generated from the author source), PS-c2 (plural hack exports a lone "s"), PS-c3 (no
`department_id` column on `hr_employee`), PS-c4 (walk users and the People side panel), PS-c5 (stale lock file).

## 9. Questions for the product owner (plain words)
1. **Give everyone their own pay scheme — go ahead?** Nothing has changed yet: today everyone is still paid the way
   they were. If you say yes, each person gets written down with the pay scheme that pays them today, and nobody's
   pay changes. On rize that is 227 of 231 people; on the payobook demo 4,517 people. You can undo it from the
   Mapping screen. Shall I run it, and on which sites?
2. **Rize: 4 people have no Country of work.** The "Fill empty Country of Work" button would set all 4 to the
   company's own country. Is that right for them, or should HR set each one by hand first?
3. **Sudima: nobody can be given a pay scheme yet**, because its only pay scheme is still a draft. Should we wait
   until that pay scheme is switched on and run the fill for Sudima then?
4. **Payobook demo: 44 people need a choice** — their country has several pay schemes and no team rule says which.
   They stay as they are unless someone picks for them in the drawer. Leave them, or pick?
5. **A two-minute look, please**: on payobook.com open one person (People › side panel › Pay & tax: the Pay scheme
   block), then Mapping › Who is paid by what (the line "N people still follow their team"), and open and close
   "Change pay scheme" without saving. I did not sign in to the live site myself.


## 10. Addendum (27 Nov): the fill applied on rize and payobook (owner decisions)

Owner decisions by card: apply on rize and payobook only; rize's 4 people without Country of work left for HR ("Fill
empty Country of Work" NOT run); payobook's 44 "needs your choice" people to get their TEAM's usual scheme where one
exists; sudima waits; template / p0clone not run. Full account in `PSCHEME_CLOSEOUT.md` §2–§3.

- First apply on rize failed before anything was written (the `odoo` user could not read its settings file inside
  the root-only backup folder; FAILED line in the notes, 0 rows). `ps3_fill.sh` now works in a private temp folder and
  copies the results next to the dump; re-run → DONE.
- rize: **227** people given their own scheme (227 rows). payobook company 5: **4,510** people (9,020 rows: main + its
  real mid-month advance). payobook company 2: 7 people **sent for approval** (second approver; 0 rows until approved).
- The 44: every one has NO team usual scheme (23 without a team, 21 in five teams with no map line; the ladder without
  the person rule answers nothing) — none could be given one by the owner's rule; all 44 left.
- Before/after (`ps3_fillcheck.py`): main "who pays them" changed 0, real advance changed 0, next month nobody in two
  main runs, nobody missing, nobody moved (both databases, every company). The 227 rize "advance" answers that were the
  main scheme by a team line "for any run" (PS6) are no longer shown as an advance (A13; expected).
- "Paid by" settled with Mapping's "Work it out again" (`ps3_settle.py`, `pb.scheme.board.recompute`): rize 227 stored
  advance artefacts cleared; payobook 1 stored-empty person filled with the scheme the map already gave; 0 left stale.
- Banner: rize 227 of 231 have their own (4 follow their team); payobook company 5 4,510 of 4,554 (44).
- Server log: 0 ERROR / CRITICAL since the release. No service stop.
