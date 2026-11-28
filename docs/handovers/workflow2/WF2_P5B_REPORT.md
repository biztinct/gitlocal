# WORKFLOW-2 · Phase 5b report — Vietnamese and Indonesian, tidy-up, closeout

Builder: Claude (Opus implementation agent), 12 November 2026. Handover: `WF2_P5B_HANDOVER.md`. Ledger: `WF2_LEDGER.md` (G80–G83 added, P5b row marked). Programme closeout: `WF2_CLOSEOUT.md`.

## 0. In plain words (for the owner)

- **Live on all five sites.** Everything WORKFLOW-2 added that people see outside the Studio editor now reads in **Vietnamese** and **Indonesian** for people whose language is set to one of them: the task page, the employee home's **My tasks**, the page behind an email link, the link email itself, the progress strip on a record, the **Tasks** part of the Approvals inbox ("receipt 2 of 3", "Do all in turn"), the dock line, reminders and "late" notes, the "sent back" emails, the status words, and the Studio's own server messages (checks, warnings, schedule sentences).
- **Messages now go out in the reader's language**: a reminder to a Vietnamese manager is in Vietnamese even when the job runs at night; the link email to someone with no login is in their language (or the company's), and the link opens the page in that language when the site offers it.
- **English is exactly as before** — checked word for word against the screens before this phase.
- **Not translated (by design):** the Studio editor's own buttons and labels (about 466 phrases) — it never had a way to translate; this is the first item in the closeout's open list.
- **One problem found and fixed during the deploy**: the first attempt stopped on rize because the new "See everyone's approvals" ability (now held by Debalina) could not be rewritten by an upgrade. Everything was put back automatically, nothing changed for anyone; the fix keeps that ability out of upgrades, and the second attempt went through on all five.

## 1. Commits, versions

| Commit | What |
|---|---|
| `427911a07` | Schedule sentences translatable (`workflow_schedule.py` lazy sentences; `words()` / `issues()` take the reader's language) |
| `2ce73e3e7` | Messages and pages in the reader's language (reminders, pass-ups, team notes, past-target notes; link email + link language prefix; goal-change and resignation sent-back emails; home list verbs; built-in buttons "I confirm" / "Done") |
| `78f66f5d0` | Vietnamese and Indonesian `.po` entries, 13 modules, 26 files; `pb_lifecycle` 19.0.1.19.0 |
| `6d432a0ba` | Tests (p1 English golden, p2 languages reach the surfaces, p3 reader's language), proof script, scope list, UI fixture, browser script |
| `3f72fae96` | Ability "See everyone's approvals" kept out of upgrades (G80) |
| (docs commit) | This report, the closeout, ledger, screenshots |

Not pushed. Versions live: **`pb_lifecycle` 19.0.1.19.0**; all others unchanged (`pb_timeoff` 19.0.1.10.0 and `pb_me_expense` 19.0.1.2.0 were upgraded at the same version to load their stored translations; the other ten modules carry code translations that a restart loads). `biz_approval_workflow` and `pb_approval_config` code untouched; `biz_approval_workflow` got translation files only (server tree hashed equal to the repo before overwrite).

## 2. What was translated — counts per file and language

`_()` strings (and lazy `_lt` sentences) whose Vietnamese / Indonesian translation is missing. Before = this phase's start (P5c §13 counted the same files). After = 0 everywhere; on the live sites only strings that are the same in both languages remain identical (§3).

| File | strings | before no vi / no id | after |
|---|---|---|---|
| `pb_lifecycle/models/workflow_contract.py` | 39 (+16 constant labels) | 39 / 39 | 0 / 0 |
| `workflow_stage.py` | 58 | 58 / 58 | 0 / 0 |
| `workflow_steps.py` | 70 (+6 type words) | 69 / 70 | 0 / 0 |
| `workflow_people.py` | 70 | 68 / 68 (+2 new) | 0 / 0 |
| `workflow_people_design.py` | 22 | 22 / 22 | 0 / 0 |
| `workflow_home.py` | 6 | 6 / 6 | 0 / 0 |
| `workflow_strip.py` | 42 | 42 / 42 | 0 / 0 |
| `workflow_time.py` | 8 | 8 / 8 | 0 / 0 |
| `workflow_reach.py` | 25 | 25 / 25 | 0 / 0 |
| `workflow_schedule_run.py` | 18 | 18 / 18 | 0 / 0 |
| `workflow_schedule.py` | 53 (were ~25 plain constants) | all / all | 0 / 0 |
| `workflow_timetable.py` | 2 | 2 / 2 | 0 / 0 |
| `workflow_repeat.py` | 64 | 64 / 64 | 0 / 0 |
| `workflow_models.py`, `workflow_progress.py`, `workflow_configuration.py`, `workflow_record_context.py` (not in §13; run words and Studio messages) | 49 + 38 + 8 + 3 | 47 / 49, 38 / 38, 8 / 8, 3 / 3 | 0 / 0 |
| `workflow_studio.py` (all, incl. 37 WF2 strings; + operator and start words) | 122 (+30 constants) | 121 / 122 | 0 / 0 |
| `pb_lifecycle/controllers/token_pages.py`, `my_tasks.py` | 2, 3 | 2 / 2, 3 (were plain English) | 0 / 0 |
| `pb_lifecycle` static `workflow_inbox*.js/xml`, `workflow_strip.js/xml`, `workflow_record.xml`, `workflow_studio.js` | 57 | 57 / 57 | 0 / 0 |
| `pb_lifecycle` pages (task page, task body, field rows, My tasks, strip page, "For you" card, run form) | 59 terms | 59 / 59 | 0 / 0 |
| link email (name, subject, body); right + ability name/description | 5 | 5 / 5 | 0 / 0 |
| `pb_hiring/models/workflow_contract.py` (+ 15 built-in automation sentences) | 26 | 22 / 26 (+15 id) | 0 / 0 |
| `pb_hiring` `stage_add.py`, set-up screen additions, joining note | 13 + 18 + 4 | 10 / 13, … | 0 / 0 |
| `pb_timeoff/models/workflow_contract.py` | 15 | 13 / 13 | 0 / 0 |
| `pb_timeoff` sent-back email | 3 | 3 / 3 | 0 / 0 |
| `pb_me_expense/models/workflow_contract.py`, `workflow_lines.py`, `expense_messages.py` | 13, 6, 27 | 10 / 13, 4 / 6, 0 / 1 | 0 / 0 |
| `pb_me_expense` claim status words, Indonesian (employee page labels + statuses) | 9 | – / 9 | 0 |
| `biz_approval_workflow/models/workflow_contract.py` | 8 | 7 / 8 | 0 / 0 |
| `pb_payruns/models/workflow_contract.py` (+ 4 status names) | 9 | 7 / 9 | 0 / 0 |
| `pb_contract_lifecycle`, `pb_probation`, `pb_employee_vault` `workflow_timetable.py` | 4, 4, 3 | 3 / 4, 4 / 4, 3 / 3 | 0 / 0 |
| `pb_goals`, `pb_offboarding` sent-back emails | 3, 3 | 3 / 3, 3 / 3 | 0 / 0 |
| `pb_me_portal` "Waiting for approval", `pb_mission` dock line | 1, 5 | – / 1, 2 / 5 | 0 / 0 |

Files: 975 msgids in scope (`tools/workflow_studio/data_p5b_scope.json`); 26 `.po` files; new `id_ID.po` in `pb_lifecycle`, `pb_payruns`, `biz_approval_workflow`, `pb_contract_lifecycle`, `pb_probation`, `pb_employee_vault`, `pb_goals`, `pb_offboarding`, `pb_me_portal`, `pb_mission`. Entries appended or merged (an existing entry gets the missing marker / occurrence; its existing translation is kept), never re-exported; **entry counts only grew** (no entry lost, `git diff --numstat` shows 0 deleted lines in every `.po`). No `.pot` exists in any of the 13 modules. Every entry: `#. module:`, `#. odoo-python` / `#. odoo-javascript` (code), `#: code:addons/<module>/<path>:0` or `#: model[_terms]:…`. Placeholders (`%s` order, `%(name)s`), tags and `t-*` expressions checked by script for all 1,914 translations; no "Odoo" in any msgstr. Parse gate (`PoFileReader`) locally and on the server (staged and after rsync): 26 files, 0 failures.

## 3. Glossary used (from the shipped `.po` files)

| English | Vietnamese | Indonesian |
|---|---|---|
| workflow | quy trình | alur kerja |
| task / My tasks | việc / Việc của tôi | tugas / Tugas saya |
| step / stage | bước / giai đoạn | langkah / tahap |
| Approvals / approval / approver | Phê duyệt / phê duyệt / người phê duyệt | Persetujuan / persetujuan / pemberi persetujuan |
| Waiting for approval / Second approval | Đang chờ phê duyệt / Duyệt cấp 2 | Menunggu persetujuan / Persetujuan kedua |
| send back / sent back | trả lại / đã bị trả lại | kembalikan / dikembalikan |
| pay run / payslip | đợt lương / phiếu lương | penggajian / slip gaji |
| time off | nghỉ phép | cuti |
| expense claim / receipt | yêu cầu hoàn chi phí / biên lai | klaim pengeluaran / struk |
| candidate / Hiring | ứng viên / Tuyển dụng | kandidat / Rekrutmen |
| contract / trial period | hợp đồng / thời gian thử việc | kontrak / masa percobaan |
| manager / team / HR | quản lý / nhóm / nhân sự | atasan / tim / HR |
| employee home / link / reminder | trang chủ nhân viên / liên kết / lời nhắc | beranda karyawan / tautan / pengingat |
| record / line | hồ sơ / dòng | catatan / baris |
| Do it now / Do all in turn / Take it | Làm ngay / Làm lần lượt / Nhận xử lý | Kerjakan sekarang / Kerjakan bergiliran / Ambil |
| Needs attention / Retry / Done / late | Cần chú ý / Thử lại / Xong / trễ hạn | Perlu perhatian / Coba lagi / Selesai / terlambat |
| Already happens / Try it out / Review | Đã tự diễn ra / Chạy thử / Kiểm tra | Sudah berjalan sendiri / Coba / Tinjau |

"Workflow Studio" and "Payobook" stay as names. Full brief: kept with the batch files (scratch); the table above is binding for later phases.

**Identical by design** (counted as "still English" by the proof, correct as they are): `%(each)s, %(how)s`, `%(verb)s: %(what)s` (format only), "Workflow Studio" ×2 (name), and in Indonesian 11 month names / short months that are the same words (April, September, November, Jan, Feb, Mar, Apr, Jun, Jul, Sep, Nov).

## 4. Tests and the loaded proof

**Local** (`am_wf2p5b` = clone of `am_wf2p5c` with vi_VN + id_ID installed; `am_wf2p5b_area` = clone without them):
- Studio suite **152/152** (149 + p1, p2, p3); P5b tests also pass on the database without the two languages (p2 skips).
- p1 `test_wf2p5b_p1_english_is_byte_identical`: schedule sentences (23 patterns) and checks, every area contract and "already happens" list, durations, repeat words, inbox items, staff strip, task page data and HTML, reminder / pass-up / team payloads, progress, the link email (subject + body), the employee claim strip and its page — rendered in English and compared with `tests/data/wf2p5b_english_baseline.json`, **written by the pre-phase code** (worktree at `01bffb23f`). Equal.
- p2 (languages installed): every surface again in vi and id — **vi 368 / id 336 strings changed** locally, something on every surface, no "Odoo".
- p3: reminders follow the reader's language (English reader: identical), link email language from the contact with that address.
- Area message suites (`run_p5a.py`: expenses, time off, goals, resignation, pay — P5a + P2b) **55/55** (the goal and resignation sent-back paths changed).
- t17 now also scans the schedule's lazy sentences for banned words.

**Live, p0clone after the upgrade** (inside the deploy): Studio suite **152/152**; p2 there: **vi 401, id 362** strings changed across all 15 surfaces.

**Live, all five databases** (`p5b_language_proof.py`, read only, run with the service stopped): every one of the 975 strings in scope × its languages — what Odoo's own loader returns from the server's `.po` (code) and what is stored (views, mail templates, the right and ability, claim statuses): **vi 928 checked, 4 identical by design; id 986 checked, 15 identical by design; stored values 51/51 correct** — on payobook, payobook_template, p0clone, rize and sudima alike.

**Browser** (local `am_wf2p5b_ui`, Playwright + Chrome, both languages, console clean, screenshots looked at — `docs/handovers/workflow2/p5b_screens/`):

| Screen | vi | id |
|---|---|---|
| Employee home **My tasks** (`/my/todo`) | `vi_1_my_todo.png` | `id_1_my_todo.png` |
| Task page (with the strip, line "biên lai 1 trên 2" / "struk 1 dari 2", button "Tôi xác nhận" / "Saya konfirmasi") | `vi_2_task_page.png` | `id_2_task_page.png` |
| No-login link page (`/vi/workflow/t/…`, `/id/…`) | `vi_3_link_page.png` | `id_3_link_page.png` |
| Record strip on the claim | `vi_4_record_strip.png` | `id_4_record_strip.png` |
| Approvals inbox Tasks group with line tasks, "Làm lần lượt" / "Kerjakan bergiliran" | `vi_5_inbox_tasks.png` | `id_5_inbox_tasks.png` |
| Link email as queued | `vi_6_link_email.png` | `id_6_link_email.png` |

The script fails on English left in the WORKFLOW-2 words of each screen; both runs pass. Words that remain English on those screenshots are a designer's own words (step titles, button labels a designer typed, "I paid this myself."), record data, or not WORKFLOW-2 (the claim form's own field labels, a welcome tour pop-up).

## 5. Consolidation (§1.5)

Done: nothing needed changing — and nothing was changed, by choice:
- **Inbox card and the Studio "My tasks" row** already both read the server's line words (`line.words` from `_line_words`); there is one builder.
- **`workflow_schedule.words` vs `schedWords` (schedule.js)** and **`_repeat_words` vs `repWords` (repeat.js)**: the panels that already have a server answer show it (`p.words || schedWords(…)`, `p.words || repWords(n)`); the editor's own copies draw while you type, before any server round trip. Replacing them would add a server call per keystroke (a visible delay = R1) and, now that the server sentence is translated, would put Vietnamese sentences into an English editor. Left, listed; they disappear naturally when the editor gets its translation mechanism (closeout open item 1), which can then read the server's words.
- **Date formats on screens**: the editor formats dates itself; changing it changes pixels. Left.

## 6. Deploy evidence

Normal tier (no schema change, no data rewritten). Notes file START/DONE as "Claude WORKFLOW-2", `flock`, clean staging from `git archive`, before-tarballs, parse gate on the staged files and again in the addons folder, service stopped throughout, exactly one service process checked before (UPDATES P4's DONE at 11:40 read first; no other `odoo-bin`), launched with no "odoo-bin" in the command (G62).

- **Attempt 1** (START 12:10 UTC, commit `6d432a0ba`): payobook, payobook_template, p0clone upgraded; **rize failed** — "This ability is used by assigned roles" while rewriting the new ability (G80; D32 had given a role holding it to Debalina at 11:24). The script restored the 13 trees and re-upgraded the three databases with them; rize's failed upgrade changed nothing; sudima not reached. Service back at 12:14; jobs and mail/outbox/to-do/message counts identical to before on all five; sites 200. The FAILED note named p0clone by mistake (variable reused) — a correction line was added.
- **Fix** `3f72fae96` (ability in a `noupdate` block, like the other three abilities); proven locally with an assigned role (`am_wf2p5b_g80`: `-u pb_lifecycle` exit 0).
- **Attempt 2** (START 12:15, DONE 12:24, commit `3f72fae96`): 454 s, **437 s down**. Server trees for all 13 modules hashed equal to the repo at `005516c75` before (nobody else's work overwritten) and equal to `3f72fae96` after. `-u pb_lifecycle,pb_timeoff,pb_me_expense --no-http --max-cron-threads=0` exit 0 on all five, 0 ERROR/CRITICAL; suite on p0clone 152/152; sudima last.
- **Jobs**: active id lists identical before/after: 50 / 32 / 39 / 82 / 81; sudima's Studio job **off**; none newly switched on.
- **Sent nothing**: emails / outgoing / Approvals outbox / to-dos identical before→after on all five (payobook 3,135 / 0 / 161 / 391; template 0 / 0 / 0 / 0; p0clone 34 / 17 / 8 / 9; rize 846 / 0 / 124 / 89; sudima 18 / 0 / 6 / 4). rize messages +4 = the four job / server-action change notes of the upgrade (G64), nobody notified.
- `latest_version` ×5: pb_lifecycle **19.0.1.19.0**; every other module unchanged (list in the evidence `version-*.txt`). "See everyone's approvals" holders unchanged (rize 1 = Debalina, others 0). 0 workflows switched on anywhere.
- One service process after start; sites 200 (payobook.com, p0clone, rize, sudima); 0 ERROR in the service log since the start; assets signalled and purged ×5.
- "no translation for language id_ID" still printed for `pb_hiring`, `pb_mission`, `pb_probation`, `pb_contract_lifecycle`: their `id_ID.po` hold code translations only, which that log line does not count (G81). Gone for `pb_lifecycle`, `pb_goals`, `pb_offboarding`. The language proof shows all of them load.
- Workbench files unchanged → no cache-key bump (`wf2-p5c` stays).
- Evidence: `/tmp/wf2-p5b-20261112T121525Z/` (steps, gate, upgrade logs, suite, proof, jobs, queues, versions, hashes, warm, processes); first attempt `/tmp/wf2-p5b-20261112T121011Z/`. Trees before: `/odoo/backups/wf2-p5b-20261112T121525Z/`.

Nothing created, switched on, started, approved, moved, granted or sent. ABM untouched. No mail server touched (D29).

## 7. Deviations from the handover

1. **Scope widened inside `pb_lifecycle`**: all server strings of every `workflow_*.py` were translated (also `workflow_models.py`, `workflow_progress.py`, `workflow_configuration.py`, `workflow_record_context.py` and the pre-WF2 strings of `workflow_studio.py` — run states and messages that reach people and designers), plus constant words that reach `_()` through a variable (operator words, start labels, value types, "runs when" words, pay run status names, Hiring's built-in automation sentences in Indonesian).
2. **Small code changes to make the words reach people** (English unchanged, proven by p1/p3): reminders/pass-ups/team/past-target notes built in the recipient's language; the link email in the contact's (else company's) language with a `/vi` or `/id` prefix on the link when the website offers that language; goal-change and resignation sent-back emails rendered in the employee's language (as time off/expenses do — the templates are `noupdate`, so the language is passed at send time instead of a new template field); the employee home's list verbs (plain English in the controller) and the built-in "I confirm" / "Done" buttons translated.
3. **Indonesian claim status words** (`pb_me_expense`: 4 page labels, 5 statuses) added — pre-existing gap, but they appear on the WORKFLOW-2 strip.
4. **Deploy needed a second attempt** (G80) and one code fix outside translations: the P5c ability record moved into a `noupdate` block.
5. **"No `no translation for language` line"** cannot hold for modules whose `id_ID.po` carry only code translations (G81); proven loaded instead.
6. **Consolidation**: no code changed (§5).

## 8. Still English, and why

- **Studio editor screens** (`static/workflow/*.js`): out of scope (§1.3) — closeout open item 1.
- **Stored history**: activity / progress history lines are written once, in English (the worker's language), and stay as written.
- **Designer's own words** (workflow names, step titles, button labels, notes) and record data: content, not translatable.
- **Not WORKFLOW-2 strings**, shown inside Studio's "Already happens" / contracts: Hiring's own stage names and descriptions (`hr.recruitment.stage` data), "Other request" status labels (`biz_approval_workflow` selection — another session's module), the Approvals route sentences ("After it is sent in, Their manager approves, only when validation_type is one of manager, both." — also an R8 wording gap in `biz_approval_workflow`), "Employee Contract" (the stock model name). Listed for their owners.
- **Rest of the employee claim page in Indonesian** (`pb_me_expense` id has ~60 entries overall): pre-existing.
- The no-login link page opens in the reader's language only where the website offers it — all five live sites offer English, Vietnamese and Indonesian today (checked 12 Nov), so it works everywhere now (closeout open item 13).

## 9. Gotchas (ledger G80–G83)

G80 ability records must be `noupdate`; G81 the "no translation" log line ignores code-only `.po`; G82 language cache / website language for no-login readers; G83 golden files must skip set-up-dependent output on other databases. See `WF2_LEDGER.md`.

## 10. Owner decisions needed

None required. One optional: build the Studio editor's translation (closeout open item 1, ~2 days).
