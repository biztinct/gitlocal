# DOCSTUDIO wave 1a — merge and deploy report (phases R + X, RISKY tier)

Merge-and-deploy agent, 2026-11-22 (UTC). Handover `DOCSTUDIO_W1A_DEPLOY_HANDOVER.md` (main checkout).
**Result: merged, pushed to `19.1` at `eac0d01d6`, LIVE on all five databases** (payobook,
payobook_template, p0clone, rize, sudima). abm untouched. Nothing failed; nothing restored.

## 1. Merge

Sparse release worktree `gitlocal-worktrees/docstudio-w1a`, branch `docstudio-w1a-merge` cut from
`origin/19.1` @ `4eaee9db3` (= both branches' branch point; `origin/19.1` had not moved, so no
extra `pb_explorer` re-run was owed). A full checkout did not fit on the Mac (disk full at 88 %,
gotcha DS-W1A-1), so the worktree checks out only the three modules + docs.

| Commit | What |
|---|---|
| `5fdf09ba0` | merge `origin/docstudio-r` (`993195e9f`) `--no-ff` — no conflict |
| `8ac512099` | merge `origin/docstudio-x` (`5ccdfd664`) `--no-ff` — no conflict |
| `eac0d01d6` | deploy scripts `docs/handovers/docstudio/w1a/` (clones of `formstudio/fs16/`) — **pushed, deployed** |

The two branches touch disjoint files (R: `pb_report_builder/` + its report; X: `pb_excel_layout/`,
5 `pb_explorer` files + its report). Static gates on the merged diff (47 files): py_compile 0
failures, XML 0 failures, PO gate 6 files (vi, id, pot × 2 modules) 0 empty / 0 vendor word
(re-run on the server's own reader: same), vendor word in added user-visible strings 0 (only
`@odoo-module`, PO headers and test assertions). Unpushed diff scanned for credentials: none.
Push `4eaee9db3..eac0d01d6` (fast-forward, no force).

## 2. Post-merge tests (local, ONE database `docstudio_w1a_t`, dropped after)

Database = copy of `upd_p6_t_tpl`, brought to the LIVE module set: the 38 modules installed on
`payobook_template` but missing locally installed, the 53 stale ones upgraded (no tests) → 306
installed = live 306. Addons path = official addons, an overlay folder (first) holding the module
trees under test, then a clean `origin/19.1`-equivalent tree.

| Run | Code | Result |
|---|---|---|
| Baseline | `origin/19.1` (`pb_explorer` 19.0.2.8.0) `-u pb_explorer,pb_insights_hub,pb_insights,pb_people_reports` | pb_explorer 101, pb_insights 48, pb_insights_hub 40, pb_people_reports 24: **2 failed** — `test_the_lens_order_matches_the_mockup`, `test_the_feature_set_is_intact` |
| Merged | `eac0d01d6` trees, `-i pb_report_builder,pb_excel_layout -u` the four | pb_excel_layout **29/29**, pb_explorer **101/101**, pb_insights 48, pb_insights_hub 40, pb_people_reports 24: **the same 2 failures**; plus 1 error in `pb_report_builder` `TestReportBuilderFollowUp.setUpClass` = a harness artefact (the test reads `pb_insights_hub/…/insights_hub.js` from its own folder's sibling; the overlay folder did not hold it) |
| Merged, re-run | same, `pb_insights_hub` tree added to the overlay | pb_report_builder **31/31** |

Failure set = the recorded baselines. (R recorded 3; its third, `test_82_tiles_reconcile_with_the_records`,
passes on this database — data-dependent.) The expected `pb_explorer` ERROR log lines (a test's
"schedule failed; the others carry on") appear identically in the baseline run.

**Combined check the builders could not do (contracts C1 + C2)** — both modules installed, browser
(Chrome, local server, test login on the throwaway database): Insights → Build a report shows the
four tabs; an example opened shows **"My Excel layout" in the toolbar, disabled with "Save the report
first."** (C2); after Save it opens "Your own Excel file, filled with these figures"; a workbook
dropped in → sheet grid, outline "3 columns × 1 rows from A3"; clicking B6 → "from B6"; **Try it →
file `payobook_people_by_country_and_contract_type_2026-11-22.xlsx` produced** (C1). Console: 0
errors / 0 warnings. Server side the same through `w1a_probe.py` (saved built report → `_pbxl_table`
→ board `inspect` + `try_it`, headings kept, rows filled, rolled back). No edit was needed.

## 3. Rehearsal (hidden copy of rize, dropped after)

Restored from the prep dump into `w1a_rh_rize` (hidden as a template while jobs and mail servers
were switched off, BEFORE anything else); 312 employees = live. Then
`-i pb_report_builder,pb_excel_layout -u pb_explorer` with the staged trees first on the path:

- exit 0 in 68 s; 0 ERROR, 0 Traceback (warnings = the usual manifest notices); hook line
  "Insights side-menu entry opened to 4 more group(s)".
- All data checksums identical except **messages +6**: 3 scheduled jobs and their 3 server actions
  get a tracking note because the cascade upgrade resets their name from the data file ("Payobook: …")
  and the brand rewrite names them back ("Rize: …"). Names end unchanged; no email. Same on live.
- Jobs: 20 re-activated on the copy (all were off there) — expected for a cascade; on live the
  snapshot repair would switch back any that were off (none needed it).
- Probe after: report builder opens, 10 subjects, 10 examples, an example runs (230 rows), Excel
  file made, saved report → filled layout 230 rows, schedule "Send as" field present; rolled back.
- Copy dropped (0 left).

## 4. Go-live

Notes read first: no open START, no HOLD; lock free; 15 minutes with no signed-in requests on
rize/payobook/sudima. Announced to the orchestrator session (this agent has no ListAgents; asked it
to relay). Python libraries for the service user checked before the stop: openpyxl 3.1.2, lxml 5.2.1.
Staged with `git archive eac0d01d6` of the three modules; staged trees = commit; live `pb_explorer`
= `origin/19.1` before. START 07:42, **service stopped 07:45:18, port up 07:52:43 — 445 s down**,
DONE 07:52, NOTE 08:00 UTC. Lock taken with `flock`, file removed after.

| Database | Upgrade | pb_explorer | pb_report_builder | pb_excel_layout | Jobs active (total) before → after | Backup (right before the stop) |
|---|---|---|---|---|---|---|
| payobook_template | exit 0, 70 s, 0 ERROR | 19.0.2.8.0 → 19.0.2.9.0 | 19.0.1.0.0 installed | 19.0.1.0.0 installed | 40 (99) → 40 (99) | golive-payobook_template.dump 31.5 MB |
| p0clone | exit 0, 63 s, 0 ERROR | same | same | same | 48 (99) → 48 (99) | golive-p0clone.dump 32.0 MB |
| sudima | exit 0, 67 s, 0 ERROR | same | same | same | 91 (100) → 91 (100) | golive-sudima.dump 37.2 MB |
| rize | exit 0, 70 s, 0 ERROR | same | same | same | 91 (99) → 91 (99) | golive-rize.dump 46.1 MB |
| payobook | exit 0, 76 s, 0 ERROR | same | same | same | 58 (111) → 58 (111); job 156 off | golive-payobook.dump 84.0 MB |

Backups folder `/odoo/backups/docstudio-w1a-20261122T073625Z/` (prep dumps + file-folder hard links
+ the go-live dumps + `previous-trees.tgz`). Per database: asset purge + `web.assets.version` =
`docstudio-w1a-20261122T073625Z` + signalling row. payobook_template's jobs: no job was re-activated
by the upgrade, so none needed switching back; its 40 active jobs are unchanged from before (the
script restores the snapshot, it does not switch off jobs that were already on).

## 5. Verification (evidence `/tmp/w1a-20261122T073625Z/verify.txt` on the server)

- **Trees**: the 3 server trees byte-identical to `eac0d01d6` (hash of sorted file md5s, skipping
  `__pycache__`, `*.pyc`, `.DS_Store`).
- **Versions**: manifest = `latest_version`, state `installed`, for all 3 modules × 5 databases (15/15).
- **Jobs**: id lists and active states identical to the prep snapshot ×5; no new job row; payobook job 156 off.
- **Data** (employees, contracts, payslips, lines, users, group memberships, approvals, mail queue,
  documents, …, checksums): identical ×4; rize messages +6 (the job/server-action notes above). Only
  expected moves: +5 record rules, the two new tables (0 rows), and the Insights side-menu entry's
  groups (+4 of the report builder's gate groups on every database, among them the HR officer group —
  owner ruling R-b 1).
- **Nothing mailed**: mail queue identical before → after on all five.
- **Server log** since the stop: 0 ERROR/CRITICAL, 0 Traceback, 0 asset errors; one service
  process; five login pages 200.
- **Compiled screen code** (`web.assets_web` built per database): carries the report builder tab and
  the Excel-layout button ("Save this view first") on all five.
- **Probe as administrator** ×5 (rolled back): report builder opens, 10 subjects, 10 examples, an
  example runs, Excel file made (file name without the vendor word), saved report fills a layout
  (rows = report rows), schedule "Send as" present. After everything: **0 saved reports, 0 layouts,
  0 Explorer views on all five** (nothing left behind).

## 6. Browser walk and functional checks on payobook.com

The QA login's password is not typed into a browser (safety rule; precedent S5M-4). So:

**a. Functional steps as the QA login (uid 6672) on live payobook, in a server shell, rolled back**
(`w1a/w1a_walk_probe.py`): report builder opens; example "Time off, attendance and assets per person"
+ one more field + grouped by department → 48 groups, 4,581 rows; saved (My reports 1); Excel
download made (4,581 rows, 1 sheet); Explorer: view saved → "Use my Excel layout" inspect (1 sheet,
11 columns) → Try it at B6 → file made (30 rows × 11 columns) → layout saved → "Download in my
layout" made the filled file (no fallback) → the "Send regularly" drawer lists **1 "Send as"
choice**; Try it from the saved built report → 4,581 rows. All rolled back (0 left, checked).

**b. HR-officer-level login** (existing user id 2333, HR officer, no payroll or analytics group; no
login created), same shell, rolled back: the Insights side-menu entry now matches the user's groups
(rail button visible); the report builder opens; Explorer schema, Explorer query and Pulse all
**refused**; 9 examples offered (the one needing Hiring access is left out). "Only the Build a report
tab" follows from those gates (the hub shows a tab only when its gate passes); it is also R-b's test
22 (passed in §2). This user was NOT walked in a browser (no password typed).

**c. Look-only browser walk** in the owner's signed-in browser (Mitchell Admin, payobook.com), nothing
saved: Insights shows PULSE / EXPLORER / REPORTS / BUILD A REPORT; Explorer toolbar shows "My Excel
layout" beside Download Excel, disabled, with "Save this view first"; Build a report → example
"Joiners this quarter" opened (2 DEMO rows) → Company field added → grouped by Department (one group,
2) → Excel produced `Payobook Joiners this quarter 2026-11-22.xlsx` (caught in the page, not saved to
disk); left without saving. Console: 0 errors across a fresh load of both tabs.

**Not done in the browser** (done in the shell instead, 6a): saving a report, saving an Explorer view,
uploading a workbook, Try it, the Send regularly drawer — each would have created records under the
owner's own account.

**Findings (cosmetic, no defect blocking):**
- Build a report, grouped view: the group row reads "DEMO Sales Vietnam 2" and stays collapsed; the
  Name column is empty until the group is opened — fine, just note that a grouped report opens folded.
- Two download names follow different styles: the report builder's Excel is
  "Payobook Joiners this quarter 2026-11-22.xlsx" (spaces), the Excel-layout file is
  "payobook_people_by_country_and_contract_type_2026-11-22.xlsx" (lower case, underscores). Worth one
  convention later.

## 7. Left undone / follow-ups

- Browser walk as the QA login and as an HR officer (needs someone to sign in; functional checks were
  done server-side as those users instead).
- Other sessions could not be listed from this agent (no ListAgents tool); the orchestrator was told and
  the deploy notes + lock were respected.
- Local worktree `gitlocal-worktrees/docstudio-w1a` removed after the push of this report; local test
  database and its file folder dropped; no `w1a_*` database left on the server.

## 8. Gotchas → ledger

- DS-W1A-1 | The Mac had ~1.1 GB free: a full worktree checkout failed at 88 % ("No space left on
  device") | use a sparse worktree (`git worktree add --no-checkout` + `sparse-checkout set --no-cone`
  the modules + docs) and test against a clean existing tree with an overlay folder placed first.
- DS-W1A-2 | An overlay addons folder breaks tests that read a SIBLING module's file through their own
  path (`pb_report_builder/tests/test_rb_followup.py` reads `../pb_insights_hub/...`): setUpClass
  FileNotFoundError | put every module whose files a test reads into the overlay too.
- DS-W1A-3 | Local template copies have `admin` archived; the only active administrator is the
  recovery login | for a local browser walk set a throwaway password on that user in the throwaway
  database, never in a shared one.
- DS-W1A-4 | `-u pb_explorer` cascades into modules whose jobs carry a brand-rewritten name; on rize
  the upgrade leaves 6 tracking notes on technical records (names reset then rewritten back) | expect
  "messages +6" on rize (0 elsewhere); allow it in a data-identical gate.
- DS-W1A-5 | In Odoo 19 `res.users.group_ids` holds direct groups only; a visibility check must use
  `all_group_ids` (implied groups), or an HR officer reads "no match" wrongly.
