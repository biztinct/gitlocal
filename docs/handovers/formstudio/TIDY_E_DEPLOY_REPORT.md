# TIDY-E — deploy report (merge, rehearse, live ×5, Country of Work fill, verify)

Merge-deploy-verify agent, 2026-11-19 (UTC). Handover `TIDY_E_DEPLOY_HANDOVER.md` (main checkout,
same folder; method of `WDGAP_S2_DEPLOY_HANDOVER.md` and the proven S2-F scripts, derived into
`/tmp/te_*` on the server).

**Result: LIVE on all five databases** (payobook, payobook_template, p0clone, rize, sudima) at
`6435da8eb` (`origin/tidy-e-merge` = `origin/19.1` @ `d0b7b6a93` + `origin/tidy-e` @ `883055489`;
the module trees are identical to the first merge `8aa804ba1`; `19.1` fast-forwarded with this report
after one more tools-only merge of `038dd551c`). `pb_employee_form_tidy` **19.0.1.0.0 installed ×5**;
`pb_hr_payroll_formula` shipped as files only (the one widened test file; same version, no upgrade).
**111 s down** (12:46:40–12:48:31 UTC). Deploy notes START 12:11, DONE 13:00 UTC. abm, pbf_preview,
recruit_connect untouched; no Codex module touched (both live trees = `origin/19.1` before; nothing
newer on the server, nothing rolled back).

**Country of Work fill: pressed on four databases, HELD on sudima** (preview: 650 of 651 people
"No pay set-up pays this person yet" — see §4). Owner question 1.

## 0. Before anything
`TIDY_E_REPORT.md` on `origin/tidy-e` is complete (no PAUSED, 13 numbered tests PASS). Deploy notes:
no open START (last entries Codex "Attendance policies DEPLOYED", "Rize demo company correction
APPLIED/VERIFIED", "Rize demo credentials APPLIED" — data/tools only, no module change, no restart).

## 1. Merge + local tests
Branch `tidy-e-merge` from `origin/19.1` @ `bcc752375`, `--no-ff` merge of `origin/tidy-e` — no
conflicts (19.1 side: attendance policy + Sudima tools + one `pb_hr_payroll_formula` model file; TIDY-E
side: the new module + one `pb_hr_payroll_formula` test file). Later `--no-ff` merges of `origin/19.1`
(`d0b7b6a93`, `038dd551c`) touch `tools/` only.

Local run (Mac, copies of `upd_p6_t_tpl`, `-u pb_people,pb_hr_payroll_formula,pb_records,
pb_formula_studio,pb_payrun_wizard,pb_hr_payroll_base`, tags `/pb_people,/pb_hr_payroll_formula,
/pb_records` [+ `/pb_employee_form_tidy`]):

| Run | Tests | Failed + errors |
|---|---|---|
| baseline: `origin/19.1` tree, module not installed | 841 | 4 + 0 |
| merged tree + `-i pb_employee_form_tidy` | 864 (module 33) | **4 + 0 — the same four** |

The four (pre-existing, in the builder's baseline list): `TestRd49SyncCost.test_02ab`, `test_02i`,
`TestRecordsR1OneTime.test_07b`, `TestSchemeCtxCurrency.test_04`. Static: py_compile, no vendor word in
any msgstr / XML / JS string of the module. Local databases dropped.

## 2. Backups and rehearsal
**Backups** `/odoo/backups/tidy-e-20261119T121104Z/`: payobook 83,704,199 bytes, payobook_template
31,045,779, p0clone 31,486,400, rize 44,644,360, sudima 36,502,728 — each read back (`pg_restore -l`);
file folders hard-linked (10,198 / 582 / 175 / 1,281 / 1,210 files); previous `pb_hr_payroll_formula`
tree. Evidence `/tmp/tidy-e-20261119T121104Z/`. Staged = `git archive 6435da8eb` (2 trees = commit).

**Rehearsal — PASSED** (hidden rize copy, every job and mail server off, 1,737 s, dropped `--force`,
file folder removed):

| Check | Result |
|---|---|
| Install | EXIT 0 in 15 s; 0 ERROR, 0 Traceback; 19.0.1.0.0 |
| Data before vs after install (contracts full rows, payslips full rows, lines + total, runs, employees full rows, versions, dependants, bank accounts/fields/changes/files, payment lists, releases, approvals, mails, to-dos, messages, users, groups, documents) | **identical**; only the new empty fill log |
| Payslips old code vs new code — runs 2111 (Indonesia, 122), 2110 (India, 27), 2113 (Singapore, 2), 2112 (Vietnam, 60) | **211 payslips, 6,914 lines, 0 differing**; 151 recomputed identical; the 60 Vietnam payslips are refused identically before and after (pre-existing, as in S2) — so Vietnam is proved by "refused the same", not by numbers |
| Same, after pressing the fill on the copy | 0 differing |
| Form as HR manager (view-render call, same rule evaluation as the module's test 1), one person per Country of Work | VN: 113 boxes (99 general + 14 Vietnam); ID 103 (98 + 5); IN 103 (98 + 5); SG 103 (100 + 3); none: 98 general + the "Set Country of Work…" line. Removed boxes shown 0, other-country boxes 0, newly visible 0, general boxes changed 0 — every person |
| Save the form (as HR manager) with hidden boxes holding values | 123 stored boxes compared per person × 5 → **0 changed** (rolled back) |
| Dates with the year | 25 date boxes carry the year option |
| Payroll-ready on the copy | before: with bank 0, not payroll-ready 230, 0 %; after: with bank 194, not payroll-ready 62, 84 % |
| Fill preview on the copy | 3 empty, 0 to fill, 3 "No contract" |
| Bank-copy batch on the copy | approved=59 before and after |

## 3. Go live
- Quiet check passed: no answered signed-in request on rize/payobook since 12:30:25 (last rize
  activity 12:24) → counts taken, still quiet → stop 12:46:40.
- `rsync` 2 trees (scoped `--delete`), then per database (template, p0clone, sudima, rize, payobook)
  `-i pb_employee_form_tidy`: 20 / 14 / 14 / 16 / 15 s, all EXIT 0, 0 ERROR; asset bundles purged +
  signal row + `web.assets.version` = `tidy-e-20261119T121104Z`. No job switched on by the install.
- Start, port up 12:48:31: **111 s down**. Five sites 200.

### Verification
- Trees = commit; manifest = `latest_version` ×5.
- Jobs = snapshot ×5 (111/58, 99/40, 99/48, 99/91, 100/91); payobook job 156 still OFF.
- **Data before = after install ×5** and **after install = after fill ×5** (whole employee rows except
  Country of Work, contracts, payslips, lines, bank, approvals, mails, messages); the fill moved only
  Country of Work (payobook) and added one fill-log row where pressed.
- Bank-copy batches: rize 59 approved (earlier, by Codex), **sudima 358 waiting — untouched**.
- Server log from the stop: 0 ERROR/CRITICAL; one WARNING traceback = a scheduled job interrupted by
  the service stop itself (12:46:41, payobook_template, not this module). One service process.
- Mails: none created (counts identical).

## 4. Payroll-ready and Country of Work per database (counts only)

"Payroll-ready" = the People list figures as an HR manager with all their companies.

| Site | Not payroll-ready before → after | Payroll-ready % before → after | Moved ready → not ready | Moved not ready → ready |
|---|---|---|---|---|
| payobook (demo, QA Test, 4 companies) | 81 → 81 | 98 % → 98 % | 0 | 0 |
| payobook_template | 1 → 1 | 0 → 0 | 0 | 0 |
| p0clone | 12 → 12 | 0 → 0 | 0 | 0 |
| rize | **230 → 62** | **0 % → 84 %** | 0 | **168** |
| sudima | 651 → 651 | **0 % → 99 %** | 0 | 0 |

Nobody anywhere had only the old typed Account Number, so nobody became "missing bank". Sudima: 642 of
651 now have an approved bank, but all 650 contracts are still drafts, so nobody is "ready" (the
percentage reads bank details only — pre-existing People-list rule).

**Fill Country of Work** (pressed as an HR manager — payobook QA Test with its 4 companies, the
administrator elsewhere — `create({})` → preview → `action_fill()`, exactly what the button calls):

| Site | Empty before | Preview "Will be set to" | Left empty, because | Filled | Still empty |
|---|---|---|---|---|---|
| payobook | 4,581 | Vietnam 4,515 | no contract 53, no pay set-up 13 | **Vietnam 4,515** | 66 |
| payobook_template | 1 | — | no contract 1 | 0 | 1 |
| p0clone | 12 | — | no contract 5, no pay set-up 7 (no pay set-up exists) | 0 | 12 |
| rize | 3 | — | no contract 3 (the 2 staff logins + the demo employee moved into Rize Farms today) | 0 | 3 (ID 126, IN 29, SG 2, VN 70 unchanged) |
| sudima | 651 | — | no pay set-up 650, no contract 1 | **NOT PRESSED** | 651 |

Nobody paid under two countries on any site. Second preview after each fill: nothing more to do.
**Sudima held**: its one Vietnam pay set-up is not linked to anyone (650 draft contracts with no "Paid
by" scheme, no payslips, no scheme assignment), so the handover's "do not confirm a preview that looks
wrong" applies. Until Country of Work is set, Sudima's employee pages show no Vietnamese boxes (only
the "Set Country of Work to see country details" line for HR).

## 5. Checks (look-only)
- **rize** (customer testing): no sign-in; read-only view-render as the administrator after go-live:
  same box counts as the rehearsal for VN / ID / IN / SG / none; label "Country of Work"; Mapping
  offers it in the "job" lane.
- **payobook.com**: server-side as QA Test (rolled back) — a Vietnam employee shows 108 boxes (9
  Vietnam), removed 0, other-country 0; Date of Joining carries the year; Country of Work label; filters
  "Payroll-ready" (Ready to be paid 4,500 / Missing something 81) and "Bank details" (On file 4,500 /
  Missing 81); People list shows the "Fill Country of Work" button (66 empty); Mapping "Country of
  Work"; backend bundle builds and contains the new button code. **Not seen in a real browser**: this
  agent may not type a password into a non-test host; the browser walk (desktop + phone, console) is
  the builder's local walk only.
- **Found and fixed at go-live — Vietnamese label**: the stored Vietnamese name of Country of Work
  kept the old "Payroll Country" wording ("Bảng lương Quốc gia") on all five databases, because
  installing a module never overwrites a stored translation (Indonesian was empty and took "Negara
  Kerja"). Written to "Quốc gia làm việc" ×5 through the ORM (`update_field_translations`) + cache
  signal; undo = write the old text back. **Code follow-up**: a fresh install has the same gap — the
  module needs a post-install step that writes this one translation (ledger TE-D1).

## 6. Owner questions (plain words)
1. **Sudima**: nobody at Sudima is linked to the Vietnam pay set-up yet, so the "Fill Country of Work"
   button cannot decide and we did not press it. Their employee pages now hide the Vietnamese boxes
   (insurance, tax, dependants) until Country of Work is set. Should we set Vietnam for all 651 Sudima
   staff now (HR can also do it through an Updates sheet), or wait until their pay set-up is linked
   to the contracts and then press the button?
2. **Payobook demo**: 66 demo people (53 without a contract, 13 not paid by any pay set-up) stay without
   a Country of Work and show no country boxes. Fine as demo data, or set them to Vietnam?
3. From the builder (still open): Rize's 3 people without a contract keep no country boxes until HR
   sets Country of Work by hand — fine? Should the side panel and Home's "paid with bank" figure also
   move to the approved bank account later?

## 7. Gotchas → ledger
- TE-D1: a module that relabels an EXISTING field does not change its stored translation in a
  language that already has one (vi kept "Bảng lương Quốc gia"; id was empty and updated). Fix the
  stored value AND ship a post-install write (LOOK rule: a translation fix is two fixes).
- TE-D2: the fill's "pay set-up" signal needs a contract "Paid by" scheme or payslips; a tenant whose
  scheme is not yet linked (sudima) gets everyone "No pay set-up" — check the preview before pressing.
- TE-D3: Payroll-ready % on the People list = people with bank ÷ headcount (not ready ÷ headcount), so
  sudima shows 99 % next to 651 not payroll-ready (pre-existing rule, unchanged).
