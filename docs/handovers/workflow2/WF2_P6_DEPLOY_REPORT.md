# WORKFLOW-2 · P6b + P6c + P6d — go-live report

20 November 2026 (UTC). Worktree `gitlocal-worktrees/wf2-p6`. Deployer: Opus (same session as the coordinator's brief).

**Result: LIVE on all five databases** (payobook, payobook_template, p0clone, rize, sudima; abm untouched).
Go-live at `dfdbd0fae` — **323 s down** (10:31:01–10:36:24 UTC). Then a **hotfix** at `8a8af6488`
(My Leave answered an error page for everybody, see §5) — **6 s restart** (10:44:32–10:44:38).
`origin/19.1` = `8a8af6488` = everything live. Deploy notes: START 09:48, DONE 10:37, HOTFIX START 10:44, DONE 10:49.

## 0. In plain words (for the owner)

- **Live everywhere:** Workflow Studio in Vietnamese and Indonesian (English unchanged); time off "Sent back" with
  the reason and "Ask again"; and the new small addition: a sent-back time off request now shows on the employee
  home under **Needs you** ("1 time off request sent back — ask again"), like sent-back trips and expense claims.
  It disappears once the person asks again.
- **One mistake, fixed in 8 minutes:** right after the go-live, the employee page **My Leave** showed "Something
  went wrong" for everybody on all five sites. Cause: an older leave module of ours did not accept the new
  "Ask again" input. Fixed with a 6-second restart at 10:44. The server log shows nobody but this check opened
  My Leave in those 8 minutes.
- **One thing to know:** if a Studio designer changes their own language, the Studio can keep the old language for
  up to 2 days unless they press Ctrl+Shift+R (the website's general 2-day cache for script files). First opens
  are correct. See §7 question 1.

## 1. Commits

| Commit | What |
|---|---|
| `f371f050a` → rebased `dfdbd0fae` | **P6d**: `pb_timeoff` `_pbme_needs_extra` row (`leave_sent_back`), vi/id, tests 13–14, HTTP home check in `pb_ess_workforce` |
| `8a8af6488` | **Hotfix**: `pb_leave_setup.get_my_leave(*args, **kwargs)` pass-through + test `p1b` |
| (this) | Report, ledger G101–G103, closeout, 3 screenshots |

Rebase onto `origin/19.1` `caa048ab8` (Form builder Batch 2): **no conflicts**, no file shared with the 22 upstream
commits (Batch 2 touched `pb_me_portal`, `pb_me_details`, `pb_learn`, `pb_form_studio*`, … — none of ours).
`origin/wf2-p6` (old base) was **not** force-pushed: the rebased branch is `origin/wf2-p6-live`; `19.1` was
fast-forwarded (`caa048ab8..dfdbd0fae`, then `..8a8af6488`).

## 2. P6d — the employee home reminder

- Reuses pb_me_portal's existing TIERS T3a hook `_pbme_needs_extra(emp, put)` exactly as `pb_me_trip`
  (sent-back trips) and `pb_me_expense` (refused claims) do — **no second mechanism; pb_me_portal not edited**.
- Code: `pb_timeoff/models/leave_sent_back.py` (`PbMeHomeSentBack._pbme_needs_extra`). Counts the person's
  requests that are refused AND marked sent back AND not yet asked again (same rule as the My requests
  "your turn" row). One → links straight to Ask again (`/my/work/leave?again=<id>#pbew-ask`); several → the
  earliest row on My Leave; without the employee My Leave module → `/my/requests`. Grey line: kind · dates.
  Amber, umbrella icon; the top sentence when it is the only thing waiting.
- Goes away the way the others do: when the person acts (asks again). There is no "dismiss" on the trip or
  expense rows either, so none was added.
- Words (vi / id): "1 time off request sent back — ask again" = "1 yêu cầu nghỉ phép bị trả lại — gửi lại" /
  "1 permintaan cuti dikembalikan — ajukan lagi"; plural and the two sentences likewise (P5b glossary words).
- Version: `pb_timeoff` stays **19.0.1.13.0** (P6c's raise; nothing was live yet).

## 3. Tests (local, rebased tree, `wf2p6c_at` copy; dropped after)

| Suite | Result | Baseline |
|---|---|---|
| `/pb_timeoff` | 145 run, 0 failed, **6 errors** (`TestLeaveRules`, G60) — incl. new 13, 14 | 6 errors |
| `/pb_ess_workforce` | 156 run, 0 failed, 0 errors — incl. the HTTP pass with the home check | 0 |
| `/pb_approval_config` | 173 run, **4 failures** (the known four: no-gradient look, u13, z06d, z06e) | 4 |
| Studio suite (`run_suite.py`, rolled back) | **165/165** | 165 |
| `/pb_leave_setup` + ask-again HTTP (hotfix, `pb_leave_setup` installed) | 61 + 3 run, 0 failed, 0 errors (incl. `p1b`, `test_p4_the_page`) | — |

PO gate (platform reader) on the staged files: pb_lifecycle vi 2,122 / id 1,924 entries, pb_timeoff vi 258 / id 76,
pb_ess_workforce vi 310 / id 17 — all parse; 0 empty; the vendor word in no msgstr. Diff scanned: no passwords.

## 4. Rehearsal (hidden copies of all five, jobs + mail off, `dropdb --force` after — 0 copies left)

Backups first: `/odoo/backups/wf6-20261120T094835Z/` (payobook 84 MB, template 31, p0clone 32, rize 45, sudima 35;
read back; file folders linked; previous trees saved). Server PO gate passed.

| Copy | Upgrade | Data restored vs upgraded | Notes |
|---|---|---|---|
| rize | 50 s, 0 ERROR | identical except messages +4 (upgrade notes) | **211 payslips / 6,914 lines: 0 differing** (31 computed, 180 refused identically); **G80 held** (Access abilities 89, ability links 91, role links 100 — identical checksums); Studio suite **163/165** (see below) |
| p0clone | 44 s, 0 ERROR | identical | Studio suite **164/165** |
| sudima | 45 s, 0 ERROR | identical | |
| payobook | 66 s, 0 ERROR | identical | |
| payobook_template | 46 s, 0 ERROR | identical | |

Studio suite on real data: `t8` errors on both copies because the rehearsal's staging folder held only the three
shipped modules and the test reads `pb_me_expense` source by path (a staging artefact; passes on the real tree);
`s4` "nobody has the new right" fails on rize only because the owner gave "See everyone's approvals" to one person
there (D32). Neither is a code fault. Every copy: words vi **1,135** / id **1,135**, sent-back pre-count **0**.

## 5. Go-live ×5 and the hotfix

Order rize, payobook_template, p0clone, payobook, sudima (one command each,
`-u pb_lifecycle,pb_timeoff,pb_ess_workforce --no-http --max-cron-threads=0`): **51 / 45 / 46 / 66 / 47 s, all exit 0,
0 ERROR**. First try: lock free, no HOLD line, no other open START (re-read right before the stop), 15 minutes with
no signed-in activity on rize/payobook (since 10:13:39). Fresh dumps ×5 taken right before the stop
(`golive-<db>.dump`, read back). Asset signal + purge + `web.assets.version = wf6-20261120T094835Z` per database.

Verification (`wf6_verify.sh`, read-only):
- 3 trees = commit; manifest = `latest_version` on all five (pb_lifecycle 19.0.1.21.0, pb_timeoff 19.0.1.13.0,
  pb_ess_workforce 19.0.1.5.0).
- Jobs = snapshot ×5 (111/58, 99/40, 99/48, 99/91, 100/91), none re-activated, no new job; payobook job 156 OFF;
  sudima's workflow job OFF (D11).
- Data before the stop = after ×5, except rize messages +4 (upgrade notes, as every go-live).
- Time off marked sent back by the upgrade: **0 ×5** (pre-count 0 ×5 — no time off had been sent back before).
- Access abilities and role links identical ×5 (G80).
- Studio words vi 1,135 / id 1,135 ×5; the words address refuses signed-out visitors (303) ×5.
- Server log since the stop: 0 ERROR, 0 Traceback, 0 asset errors; one service process; five sites 200.
- Stored-value translation fixes: **none listed** by the P6b/P6c reports (code words load from the files; template
  terms and field labels load with the upgrade) — nothing to write.

**Hotfix (G101).** The payobook.com check (§6) opened My Leave as an employee → "Something went wrong" (500).
`pb_leave_setup` (WDGAP S5-A) overrides `get_my_leave(self)` with no arguments; P6c's page calls
`get_my_leave(again=…)`. Every database has both modules, so My Leave failed for everybody from 10:36:24.
Local tests missed it because the test base did not have `pb_leave_setup` installed (G102) — its own HTTP test
would have caught it. Fix: pass every argument through (`8a8af6488`), method-only, no version raise (G29);
staged from the pushed commit, scoped rsync of `pb_leave_setup`, restart 10:44:32 → 10:44:38 (**6 s**), after
checking that nobody but this session had been signed in during the previous 15 minutes and the notes had no
HOLD/open START. Server log 10:36–10:44: **one** My Leave error, this check's own; no one else hit it.
After: tree = commit; 0 ERROR from users (the 7 lines logged are this check's own: 6 unsendable mails to the
throwaway demo address on payobook — that database has no sender address, known — and one lookup of mine).
`latest_version` of `pb_leave_setup` unchanged (19.0.1.1.0, files only).

## 6. Checks

**payobook.com** (QA login, administrator; signed-in browser):

| Check | Result |
|---|---|
| Workflow Studio, English | list, cards, "Create workflow" exactly as before; console clean |
| Workflow Studio, Vietnamese (QA language switched, put back to English after) | list "Quy trình / Việc của tôi / Hoạt động / Tạo quy trình / 7 bước / Mở"; editor "Thiết kế / Chạy thử / Kiểm tra / Hành trình / Theo giai đoạn / Lưu đồ / Người thực hiện / THÊM BƯỚC…"; designer-typed titles stay as typed; screenshot `p6_deploy_screens/vi_studio_list.png`. Needed a fresh copy of the words file — see §7 Q1 |
| Time off sent back (throwaway DEMO employee with its own employee login) | sent from My Leave → sent back by the manager with a reason → **home "Needs you": "1 time off request sent back — ask again · Unpaid · 12/14/2026"** + top sentence (`home_needs_you_sent_back.png`) → My Leave row: amber "Sent back", "Your approver sent this back to you. It was not refused, and no days were taken.", the reason, **Ask again** → form filled in (kind, day, 09:00–11:00, note, banner with the reason; `my_leave_ask_again.png`) → sent with 14:00–16:00 → "Asked again. Your new request is waiting for approval." → old row "Asked again on 11/20/2026", **home reminder gone** |
| Console | no errors on the employee pages or the Studio |
| Vendor word | not on any page opened |

Notes from the payobook check: time off for **Payobook Vietnam JSC** is set to "No approval needed" (owner, 23 Sep),
so nothing there can be sent back; the DEMO employee was moved to **Payobook Singapore Pte Ltd** (manager approves).
Two first attempts were approved at once (the creator was the approver / the no-approval route). **Undone:** the
asked-again request withdrawn, the two approved DEMO days cancelled by the employee, the DEMO login and employee
archived (both inactive now). **Kept** as demo data: one DEMO request "Sent back" (Unpaid, 14 Dec) of the archived
DEMO employee.

**Other four sites** (server side, read-only, rolled back; nobody signed in as a customer): My Leave + employee home
built for the newest employees with a login — template 1/1, p0clone 5/5, rize 5/5, sudima 1/1 (payobook 5/5) — 0
failed; words vi/id 1,135 each; login page 200 and My Leave → sign-in (303) on all five.

## 7. Owner questions

1. **Studio language after a language change.** The website keeps every script file for 2 days in each browser.
   So a designer who switches their own language sees the Studio in the old language until they press
   Ctrl+Shift+R (or 2 days pass); everyone opening it for the first time since today gets their own language.
   Fix option: a small change so the Studio's word list is never kept (about 25 KB more per Studio open, no
   downtime). Do you want that, or is "press Ctrl+Shift+R after changing language" fine?
2. **Payobook demo, time off approvals.** Payobook Vietnam JSC's time off is "No approval needed", so a visitor to the
   demo cannot see "Sent back" / "Ask again" there. Keep it, or switch the demo company back to "Their manager
   approves"?

## 8. Not done / left as is

- The Studio suite was not run on a live database (run on the rize and p0clone rehearsal copies instead, §4).
- Vietnamese/Indonesian wording of the home reminder was checked by tests (en/vi/id), not on screen in vi/id.
- The QA account cannot turn down a request (no read access to calendar entries) — existing, not from this release.
- 6 failed outgoing mails on payobook (to the throwaway `example.invalid` address) stay in the mail queue as failed.

## 9. Server artefacts

Evidence `/tmp/wf6-20261120T094835Z/` (steps, rehearsal, verify, probes); scripts `/tmp/wf6_*.sh`, `wf6_probe.py`,
`wf6_open.py`, `wf6h_hotfix.sh`; backups `/odoo/backups/wf6-20261120T094835Z/` (prep dumps, `golive-*.dump`,
previous trees incl. `previous-tree-pb_leave_setup.tgz`).
