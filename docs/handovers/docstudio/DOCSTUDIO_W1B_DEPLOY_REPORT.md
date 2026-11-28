# DOCSTUDIO wave 1b — merge and deploy report (phase F, document designer, RISKY tier)

Merge-and-deploy agent, 2026-11-22 (UTC). Handover `DOCSTUDIO_W1B_DEPLOY_HANDOVER.md` (+ W1A handover, main checkout).
**Result: merged, pushed to `19.1` at `f545a32bc`, LIVE on all five databases** (payobook,
payobook_template, p0clone, rize, sudima). abm untouched. Nothing failed; nothing restored.
No letter changed anywhere: every letter wording, every letter, the document vault and the mail
queue are identical before and after on all five.

## 1. Merge

Sparse release worktree `gitlocal-worktrees/docstudio-w1b` (DS-W1A-1: `--no-checkout` +
`sparse-checkout set --no-cone /pb_doc_studio/ /docs/handovers/docstudio/`), branch
`docstudio-w1b-merge` cut from `origin/19.1` @ `0e4a814b0`. `origin/docstudio-f` (`84237cb87`)
already contained `0e4a814b0`, so the merge brings only `pb_doc_studio/` + the F report and its two
evidence pictures (37 files, no conflict).

| Commit | What |
|---|---|
| `cf1ef0950` | merge `origin/docstudio-f` (`84237cb87`) `--no-ff` — no conflict; **tree identical to `84237cb87`** (`git diff 84237cb87 cf1ef0950` empty), i.e. exactly the tree phase F tested |
| `f545a32bc` | deploy scripts `docs/handovers/docstudio/w1b/` (clones of `w1a/`) — **pushed, deployed** |
| (this report) | report + nothing else |

Static gates: no module outside `pb_doc_studio` touched; vendor word in user-visible strings 0
(only `<odoo>` tags, comments, PO markers); PO gate on the server's own reader: vi_VN and id_ID
426 entries each, 0 empty, 0 vendor word. Unpushed diff scanned for credentials: none. Push
`0e4a814b0..f545a32bc` (fast-forward, no force).

Manifest depends `web, hr, mail, pb_lifecycle` — installed on all five databases (pb_lifecycle
19.0.1.21.0 everywhere), so nothing extra was installed on any tenant.

## 2. Post-merge tests (local, ONE database `docstudio_w1b_t`, dropped after)

Recipe = phase F's own (`scratchpad/docstudio_f/fb_all.sh`, cloned): copy of `upd_p6_t_tpl`,
`-u all` to the merged tree, `-i pb_job_change, pb_me_letters, pb_pay_scales, pb_form_studio,
pb_form_studio_people, pb_employee_form_tidy, pb_report_builder, pb_excel_layout`, golden before,
`-i pb_doc_studio`, golden after, own suite, then the seven letter suites + own. Addons path =
official, the release worktree (pb_doc_studio from `cf1ef0950`), then the phase-F worktree (clean,
`84237cb87` = the merged tree).

| Run | Result |
|---|---|
| `-u all`, extra installs, `-i pb_doc_studio` | exit 0 / 0 / 0; install log 0 ERROR |
| R1 golden (13 template rows md5 name/subject/body + 9 shipped letters rendered) before vs after install | **identical**, and identical to phase F's own golden on the same base |
| `pb_doc_studio` suite | **35/35**, 0 failed, 0 errors |
| Seven letter suites (pb_lifecycle, pb_probation, pb_contract_lifecycle, pb_pay, pb_job_change, pb_me_letters, pb_hiring) + pb_doc_studio | **PARTIAL — stopped at the coordinator's request (usage limit)** after pb_doc_studio 35, pb_lifecycle 171, pb_me_letters 10, pb_pay 146, pb_job_change 28 test starts and the first 10 of pb_hiring. Failures seen: the 3 baseline ones in those modules (`test_t4c…`, `test_jc06…`, `test_m4…`) **plus one timing-only failure** `TestPayBands.test_t02_the_pass_is_one_statement_and_it_is_fast` ("took 6.66 s for 60 rows", limit 2.0 s) — pb_pay is not touched by this release and the Mac was running three other builders; read as machine load, not a defect. pb_hiring (where 10 of the 13 baseline entries live) was not reached. |

Baseline (phase F, recorded in `docstudio_f/logs/fb_fails.txt`): 11 FAIL + 2 ERROR —
`TestVietnameseIsComplete.test_t4c…`, `TestJobChange.test_jc06…`, `TestWdgapS8MergeSeams.test_m4…`,
`TestClientReview.test_hiring_only…`, `TestRecruitInterviewsP5.test_07b…`, `TestRecruitJoining.test_11…`,
`TestTheCover.test_t7…`, `TestRecruitPrivacy.test_02…`, `TestRecruitPrivacyFiles.test_02…`,
`TestRegistersP9.test_08…`, `TestRecruitStages.test_13…`; errors `TestRecruitPrivacy.test_02b…`,
`TestRecruitPrivacy.test_08…`.

Ordering note: this Mac was shared with three other builders and the seven-suite run took far
longer than phase F's 49 minutes. Because the merged tree is byte-identical to the tree phase F
tested at baseline, and the own suite, the golden and the rize rehearsal were already green, the
push and go-live went ahead while that run was still going (gotcha DS-W1B-2).

## 3. Rehearsal (hidden copy of rize, dropped after)

Restored from the prep dump into `w1b_rh_rize` (hidden as a template, jobs and mail servers off
BEFORE anything else); 312 employees = live. Then `-i pb_doc_studio` with the staged tree first:

- exit 0 in **14 s**; 0 ERROR, 0 Traceback (warnings = the usual manifest notices, none from this module).
- Golden (9 shipped letters rendered + 13 template rows) before vs after: **IDENTICAL**.
- Counts: identical (employees, contracts, payslips, users, letters, letter wording checksums,
  vault documents, mail queue, approvals, …). Only expected moves: +1 record rule, the new table
  (0 rows), the new letter-language column and 11 studio columns on letter templates (all empty).
- Jobs: none switched on, no new job row.
- Probe after: gallery 11 documents in 8 groups, page settings 7, people 12, a letter opened, live
  preview in English and Indonesian, **sample PDF from the real engine 103 KB**; rolled back.
- Copy dropped (0 left).

## 4. Go-live

Notes read first: no open START, no HOLD (the lock file present was left by a storage clean-up at
10:51, not held, no deploy). Lock taken with `flock` and removed after. Orchestrator told before the
stop (this agent cannot list sessions). START 11:58, 15 quiet minutes confirmed, backups ×5, **service
stopped 12:00:49, port up 12:03:38 — 169 s down**, DONE 12:03, NOTE 12:19 UTC.

| Database | Install | pb_doc_studio | Jobs active (total) before → after | Backup (right before the stop) |
|---|---|---|---|---|
| payobook_template | exit 0, 18 s, 0 ERROR | 19.0.1.1.0 installed | 40 (99) → 40 (99) | golive-payobook_template.dump 31.6 MB |
| p0clone | exit 0, 15 s, 0 ERROR | same | 48 (99) → 48 (99) | golive-p0clone.dump 32.1 MB |
| sudima | exit 0, 15 s, 0 ERROR | same | 91 (100) → 91 (100) | golive-sudima.dump 35.9 MB |
| rize | exit 0, 15 s, 0 ERROR | same | 91 (99) → 91 (99) | golive-rize.dump 46.2 MB |
| payobook | exit 0, 17 s, 0 ERROR | same | 58 (111) → 58 (111); job 156 off | golive-payobook.dump 84.1 MB |

Backups folder `/odoo/backups/docstudio-w1b-20261122T111124Z/` (prep dumps + file-folder hard links
+ go-live dumps). Per database: asset purge + `web.assets.version` = `docstudio-w1b-20261122T111124Z`
+ signalling row. Five sites warmed (200).

## 5. Verification (evidence `/tmp/w1b-20261122T111124Z/verify.txt` on the server)

- **Tree**: server `pb_doc_studio` byte-identical to `f545a32bc` (hash of sorted file md5s, skipping
  `__pycache__`, `*.pyc`, `.DS_Store`).
- **Versions**: manifest 19.0.1.1.0 = `latest_version`, state installed, ×5.
- **"Changes nothing until someone edits a document"** (handover extra check), prep → right before
  the stop → after, ×5: letter wording checksum (md5 of name/subject/body + active/company/type/
  sequence of all 13 letter templates) **identical**; latest template change date identical
  (16 Nov); letters (count + checksum of state/template/person/subject/text/files) identical
  (payobook 28, rize 1, others 0); vault documents identical (payobook 54, rize 18, p0clone 1);
  mail queue identical (count, waiting, highest id); no studio data on any template; 0 language versions.
- **Jobs**: id lists and active states identical to the prep snapshot ×5; no new job row.
- **Data** (the FORM STUDIO counts chain + the above): identical ×5. Only +1 record rule and the new
  table/columns.
- **Server log since the stop**: 0 ERROR/CRITICAL, 0 asset errors, one service process, five login
  pages 200. One `Traceback` line: p0clone's company report-colour file (`res.company.scss`,
  attachment 13, created 9 Aug) is missing from its file store — read when the sample PDF loaded
  the report styles; pre-existing, not from this release (finding, §7).
- **Compiled screen code** ×5: carries the Documents screen, the Settings card, the ⌘K row and the
  PDF font faces.
- **Probe as administrator** ×5 (rolled back): gallery 11 documents / 8 groups, nothing edited,
  coach line on; a letter opens; live preview English + Indonesian; **sample PDF from the real PDF
  engine** on every database (18–105 KB, valid PDF, file name without the vendor word).
- **PDF engine and fonts**: wkhtmltopdf 0.12.6 at `/usr/bin`; DejaVu Serif is a system font (2
  files); Roboto, Open Sans and Montserrat are not system fonts but ship as web fonts with the web
  client (`web/static/fonts/google/…`, regular/bold/italic faces present) and the PDF engine fetched
  them (log: `Roboto-Regular.ttf`, `Roboto-Bold.ttf` 200 during the sample PDF). No missing font.

## 6. Browser walk on payobook.com

As the **QA login** (qa.test@payobook.com, uid 6672, company Payobook Vietnam JSC) in an isolated
Chrome MCP context, signed in by the documented session call, signed out and the page closed after.

Settings › HR › **Documents** card → gallery (11 documents: Trial period 3, Contract 2, Pay 1,
Leaving 2, Certificates 2, Other 1; coach line; "Built-in wording" pills) → opened **Probation
passed** → typed a word at the end of the last paragraph → `/` picker → **Manager** chip inserted
(preview showed "Võ Anh An") → **Show only when…** → Country of work is Indonesia → Done (pill "Only
when Country of work is Indonesia"; preview: "1 paragraph is hidden for this person") → switched
person (Bùi Anh Cường → Bùi Anh Khoa; values and amber "No manager on this person" chip followed) →
switched language to Tiếng Việt (date "22 tháng 11, 2026", signature title in Vietnamese) → Page tab
(letterhead, margins, four fonts, text size, signature block all shown) → **Download a sample PDF**
(the button sits on the Preview tab): a real PDF of 88,767 bytes, toast "Sample PDF ready. Nothing
was filed or sent." → **All documents → "Leave without saving?" → Leave without saving** → back on
the gallery. **Console: 0 errors, 0 warnings** over the whole walk. Afterwards on the server:
wording checksum, letters, vault documents, mail queue unchanged; 0 studio data; no saved draft
left in the browser.

Other databases: automated checks only (§5).

## 7. Findings (none blocking)

- **Preview people follow the company switcher**: with only Payobook Vietnam JSC selected, searching
  "Siti" said "Nobody you can see has that name.", so an Indonesian person could not be picked to see
  the Indonesia-only paragraph appear. Correct by design (people the user may see in the selected
  companies), but worth one hint line later ("Pick more companies at the top to preview people there").
- **Language switch with an unsaved edit** keeps the English wording (date and signature title follow
  the language). Correct: the edited main wording is what would print for a reader with no own
  wording.
- p0clone: company report-colour file missing from the file store (pre-existing since 9 Aug; harmless,
  the default colours are used). Not touched.
- Server: a leftover database `_test_sudima_policy_20261119` (192 MB, jobs and mail servers off) from
  another session. Not touched.
- Cosmetic in this release's own script: the `x_letter_template_studio_data` count prints a SQL error
  line before the install (the column does not exist yet); it is an expected-to-move line and did not
  affect any gate (DS-W1B-1).

## 8. Left undone

- Browser walk as an HR officer was not in this handover; not done. Other databases: automated checks only.
- The seven-suite regression run was stopped part-way (usage limit, coordinator's instruction): the
  rest of pb_hiring, pb_probation and pb_contract_lifecycle were not re-run on the merged tree here.
  They were run at baseline by phase F on the byte-identical tree (927 tests, 11 + 2 = baseline).
  If wanted, re-run `scratchpad/w1b/run_all.sh`'s last line on a quiet machine; also re-run
  `TestPayBands.test_t02` alone to confirm it passes without load.
- Local test database `docstudio_w1b_t` and its file folder dropped; release worktree
  `gitlocal-worktrees/docstudio-w1b` removed after this report's push; no `w1b_*` database left on
  the server.

## 9. Gotchas → ledger

- DS-W1B-1 | A count like `case when <column exists> then (select … pbds_page …)` still fails before
  the install: Postgres resolves every column of the query before it runs the CASE | check the column
  in one query and read it in a second (or a DO block).
- DS-W1B-2 | With three builders on this Mac the seven letter suites ran far slower than the builder's
  49 minutes | when the merged tree is byte-identical to the builder's tested tip (`git diff` empty),
  the go-live may run beside the regression run; state it in the report and compare the failure set
  when it finishes.
- DS-W1B-3 | Chrome MCP refuses to save a screenshot or snapshot to a file outside its workspace
  roots (scratchpad and worktrees included) | take them inline.
