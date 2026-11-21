# LEARNREV P1 — deploy record

Deployer: Opus, 2026-10-17. Tier: **normal**. Scope: P1 content engine (merged at `3086feecd`) + the LR27 label rename
+ two small fixes found on the way. Status: **live on payobook, rize, payobook_template, abm**; files and versions
verified; browser checks B1–B4 pass on payobook.com (QA Test). Not pushed.

## Commits (branch 19.1)
| Commit | What |
|---|---|
| `1b4d44cf6` | LR27: `net_role` "Pay role", `net_role_detail` "Included in another total", `net_role_source` help says "the Included in another total tick"; vi_VN patched as text ("Vai trò trong lương", "Đã tính trong tổng khác"); treatment manifest retires "Net Pay Role" / "Folded Into a Total". |
| `148641f4d` | pb_payruns vi_VN typos on the run card/form: "Enhân viên" → "Nhân viên" (×2), "DCác khoản khấu trừ" → "Các khoản khấu trừ" (live in every DB since 3f8e2538b). |
| `04065df32` | Ship: patch bumps of 10 modules (below). |
| `ee1f95e5c` | Treatment header "Included in another total" read English on a Vietnamese screen (B2 finding, LR30): one text node in a capped span; vi entry "Đã tính trong một tổng khác"; pb_formula_studio .33. |
| this doc | P1_DEPLOY.md, ledger LR29–LR33, `tools/vi_overwrite_guard.py` + `tools/vi_overwrite_load.py`. |

Offline gates at `1b4d44cf6` and `ee1f95e5c`: truth gate over the checkout (`guide_truth.check_files` on all 8
manifests) 0 errors; `check_contract.py` only the known `scenario-anchors-exist` (`grid-hint`) baseline. Server
`PoFileReader` on every changed .po: pb_hr_payroll_formula 3,961 entries, pb_payruns 373, pb_formula_studio 2,535 — all
parse; the new msgids load with the right Vietnamese.

## Deviation: 10 modules, not 8
`pb_dashboard` and `pb_payslip_review` carry P1's `learn_manifest.py` and the server did not have it (dry-run diff:
that file only). Without them the dashboard and payslips Guides are absent live and the truth gate's
`test_01_every_promised_screen_has_a_manifest` fails. Both were staged, tested, bumped and upgraded with the rest (LR33).

## Clone test (merged tree P0+P1+LR27, before the ship commit)
Clone `lrp1clone` = `pg_dump --exclude-table-data=hr_payslip_line payobook | psql` (323 MB, restore 1.5 min; LR16/LR26).
Prep before any odoo-bin start: AI connection off (`payroll_ai_config` 0 active / 0 keys, every `*api_key*` parameter
blank — checked, abort otherwise), jobs and mail servers off, `base.group_user` → `group_payai_user` implied **on the
clone only** (LR18). Stage = `git archive HEAD` of the 10 modules in `/tmp/p1stage` + `pb_hub`, `pb_home_hub` linked
in (read-only siblings for `test_learn_hub`). Ports 8099/8098, `-u` 10 modules, tags `/pb_learn`,
`/pb_formula_studio:TestStudioExperience,TestColumnRoles,TestLaneLabels`,
`/pb_hr_payroll_formula:TestNetRoleClassifier,TestValueKinds,TestLearnrevNetWords`, `/pb_payruns`.

**521 tests, 1 failed, 0 errors** (06:21–06:26 UTC, 5 min — 0 model calls). The one failure is the known baseline
`pb_learn test_questions.test_07b` (clone jobs off). `TestCoach.test_11` passed (AI off). Learn hub 7/7 with pb_hub
linked. Per class: TestNetRoleClassifier 36, TestValueKinds 33, TestCoach 28, TestRunTotals 16, TestStudioExperience 11,
TestGuide 9, TestLearnHub 7, TestColumnRoles 6, TestGuideTruth 4, TestLearnrevNetWords 3, TestLearnrevLessonDoor 3,
TestLaneLabels 2. The Vietnamese overwrite + put-back was rehearsed on the clone (same counts as live, below). Clone
dropped with `dropdb --force`; no filestore folder had been created. (`p0clone` on the server is not mine; left.)
`ee1f95e5c` (one template text node + one .po entry) was not clone-tested: no test reads that template text; gates
above + the live B2 check cover it.

## Deploy per database
Server check before each stop (`pgrep -af "odoo-bi[n].*stop-after-init"`, rollout units, lock holders): clear both
times. Both rounds ran under `flock -n /tmp/payobook-studio-deploy.lock`; stage from `git archive HEAD` into a clean
`/tmp/deployP1` (`/tmp/deployP1b` for round 2); PA60 dry-run diff = exactly P1's files + bumps (round 2: the 4 Studio
files); per-module `rsync -a --delete` into `/odoo/odoo-server/addons/<m>/`; `~/pb_upgrade.sh` per DB, payobook first.

| Round | Lock taken | Service stopped | Service started | Down |
|---|---|---|---|---|
| 1 (10 modules + Vietnamese) | 06:29:49 | 06:30:16 | 06:35:12 | ~5 min |
| 2 (pb_formula_studio, header fix) | 06:40:26 | 06:40:29 | 06:41:37 | ~1 min |

`ir_module_module.latest_version` — identical before and after in all four DBs (payobook, rize, payobook_template,
abm); every `-u` EXIT=0, 0 ERROR/CRITICAL in the 8 upgrade logs, the 4 Vietnamese-load logs and the service log after
each start.

| Module | Before | After |
|---|---|---|
| pb_learn | 19.0.20.5.5 | 19.0.20.5.6 |
| pb_formula_studio | 19.0.1.201.31 | 19.0.1.201.33 |
| pb_hr_payroll_formula | 19.0.1.148.15 | 19.0.1.148.16 |
| pb_payruns | 19.0.3.0.0 | 19.0.3.0.1 |
| pb_payrun_wizard | 19.0.1.32.3 | 19.0.1.32.4 |
| pb_approval_config | 19.0.1.6.2 | 19.0.1.6.3 |
| biz_approval_workflow | 19.0.1.7.0 | 19.0.1.7.1 |
| pb_scheme_map | 19.0.2.5.2 | 19.0.2.5.3 |
| pb_dashboard | 19.0.2.2.4 | 19.0.2.2.5 |
| pb_payslip_review | 19.0.1.3.0 | 19.0.1.3.1 |

- Files: all 10 module trees byte-identical staged-commit ↔ server (`rsync -rcn`, 0 differing files), after each round.
- Assets: purge + `web.assets.version` bump + `orm_signaling_assets` per DB, both rounds.
- Scheduled jobs: payobook 37 → 37, rize 69 → 69 (no job newly on). Round 1's upgrade switched **abm** 23 jobs and
  **payobook_template** 26 jobs back on — switched off at once; both **0**. Round 2 switched none on.
- `payai.voice_enabled` on payobook: True before, True after both rounds. payobook.com and rize.payobook.com: 200.

## Vietnamese overwrite load (LR20) — pb_hr_payroll_formula, pb_payruns, pb_scheme_map
Hand-edit check first, read-only, per DB (`tools/vi_overwrite_guard.py snap` + `candidates`): for every model term in
the new .po files, the stored vi_VN value was compared with the NEW msgstr and the OLD (deployed) msgstr. Stored ≠ new
and = old → an intended reword. Stored ≠ new and ≠ old, not empty → a value that did not come from these files:

| DB | Rewords (stored = old file) | Values from elsewhere (put back) | Empty (filled by the plain `-u`) |
|---|---|---|---|
| payobook | 22 | **20** | 32 |
| rize, payobook_template, abm | 22 | **14** each | 32 |

The "from elsewhere" values are **not hand edits by a person** but shared records whose Vietnamese another module
loaded better: "Display Name" on 15 (payobook) / 9 (others) records — stored "Tên hiển thị", our file says
"Hiển thị Tên" (wrong word order); record-type names "Gán phương án lương" (file: "Phân công kế hoạch tiền lương"),
"Phiếu lương Đợt" (file: "Bảng lương" / "Đợt phiếu lương"), "Hợp đồng nhân viên" (file: "Hợp đồng lao động") ×2.
Decision: run the overwrite as specified, then write those values back from each DB's own pre-deploy snapshot, so
only P1's rewords change (LR29). Verified after: 20/20, 14/14, 14/14, 14/14 equal to before.

Result per DB (identical in all four; raw overwrite → net after put-back):

| Module | Field/selection texts | Screen layouts (views) |
|---|---|---|
| pb_hr_payroll_formula | 28 (payobook) / 22 → **18** | **2** (rule form + search: "Loại cột", "Loại thành phần") |
| pb_payruns | 3 → **2** ("Tổng thu nhập", "Tổng thực nhận") | **3** (run card + form typos fixed; card "Journals" → "Bút toán"; search "Kỳ lương") |
| pb_scheme_map | 5 → **2** ("Chương trình lương" label + help) | 0 |

Among the 18: "Vai trò Lương Ròng" → "Vai trò trong lương", "Gấp thành tổng" → "Đã tính trong tổng khác", "Thành phần
Loại" → "Loại thành phần" (×3), "Cột Loại" → "Loại cột", "Hợp đồng Thành phần" → "Thành phần hợp đồng" (×3), "Hằng số
Giá trị" → "Giá trị cố định" (×2), and five help texts rewritten in plain Vietnamese. Snapshots per DB are on the server
in `/tmp/lrp1vi/` (`<db>.pre / postu / postload / final.json`, `<db>.cand`).

## Browser checks (payobook.com, QA Test, headless Chrome 9556, sign-in by `fetch('/web/session/authenticate')`)
Screenshots in `/private/tmp/claude-502/-Users-adity-Documents-GitHub-gitlocal/d3a7939f-6b40-427b-9e7d-c5a89b5a6ab8/scratchpad/walk/`.

| Check | Result |
|---|---|
| **B1** Component treatment, English (scheme "Payobook Retail — End-Month Payroll", 54 rows) | **PASS.** Headers Component / Comes from / Report group / Pay role / Included in another total / Run signal / Value type (unchanged). Pay role choices: — not set —, Added to net pay, Taken off net pay, Net pay itself, Employer cost, Information only, Both added and taken off (unchanged). "Net Pay Role" / "Folded Into a Total" in text, tooltips or options: 0. `p1_b1_treatment_en.png` |
| **B2** same, Vietnamese | **PASS after `ee1f95e5c`.** First look: every header Vietnamese except "Included in another total" (LR30) — fixed and redeployed (round 2). Now: Thành phần / Đến từ / Nhóm báo cáo / Vai trò trong lương / Đã tính trong một tổng khác / Tín hiệu cho đợt lương / Loại giá trị. Value type dropdown: 9 Vietnamese options (Số tiền (tiền tệ) … Có / Không); raw English options in any dropdown: 0. `p1_b2_treatment_vi.png` |
| **B3** Learning page → Component treatment outline (via Explain this screen → Open the lesson) | **PASS** EN and VI: none of "Subtotal", "Tổng phụ", "Tells the run", "Báo cho đợt lương", "Group", "Net Pay Role", "Folded Into a Total". `p1_b3_outline_en.png`, `p1_b3_outline_vi.png` |
| **B4** `learn.guide.rpc_guide('treatment', {'config_id': 51})` as QA Test (scheme "Payobook Information Technology — Mid-Month Advance") | **PASS** EN and VI. Keys: `screen, right_now, fields, actions, doors, lang, missing`; `missing` = []; 6 fields: lane, report_group, pay_role (6 choices, 14 readers), rollup, run_signal (2), value_kind (9); labels EN "Pay role", "Included in another total", "Run signal", "Value type"; `right_now` = {ok, items}, 1 item: "Information Technology Jun 2026 — Mid-Cycle Advance was computed before your last change to this scheme. Recompute it …". (P1's "33 readers" is the sum over the six fields: 0+3+14+6+3+7.) `p1_b4_en.json`, `p1_b4_vi.json` |

QA Test language: switched to vi_VN by RPC for B2–B4 and **restored to en_US** (read back). Console: only the
pre-existing brand-icon manifest size warning.

## Not done / open (for Fable)
- **Field label vs column, still** (LR31): `component_type` label "Component Type" / "Loại thành phần" under the
  column "Report group" / "Nhóm báo cáo" (the Guide's report_group card shows it). VI rollup: field "Đã tính trong
  tổng khác" (as instructed) vs column, manifest and 9 lesson texts "Đã tính trong một tổng khác" — pick one at the
  next lesson regeneration.
- **English left on the Vietnamese treatment screen** (pre-existing, LR32): the "What do these settings mean?"
  expander, report group values (Earnings / Information / Deductions), the grey hints ("from pay role", "a formula does
  arithmetic on it"), FROM/TO, and stored reasons that mix languages ("Added into lương thực nhận through …"). English
  board text still says "(Subtotal)" in the expander and "subtotal flags" in the Re-classify tooltip and toast.
- P2 handover T2 uses `Included in<br/>another total` as a fixture; still valid as a pure-function test, and the live
  header now matches the column text directly. If P2 edits `component_treatment.xml`, keep the header one text node.
- Not pushed (Fable pushes 19.1).
