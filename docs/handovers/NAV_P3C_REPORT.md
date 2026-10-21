# NAV P3c — Home › Team for people who manage others — report

Implementer: Opus, 2026-10-21. Spec: `docs/handovers/NAV_P3C_HOME_TEAM.md` §1–5. Ledger: five new P3c rows in
`docs/handovers/NAV_LEDGER.md`. **Deployed 2026-10-21 02:17–02:21 UTC on all four databases, normal tier, under the
shared deploy lock — see §9.**

## 0. Exact deploy lists

```
-u pb_home_hub,pb_approval_config,pb_probation,pb_goals,pb_learn
```
Rsync (scoped `--delete` per module): `pb_home_hub`, `pb_approval_config`, `pb_probation`, `pb_goals`, `pb_learn`.
No `-i`, no migration script, no new table (`pb.home.team` is an AbstractModel), no ACL, no data file, no sidebar
change. Versions: pb_home_hub 19.0.1.3.0 → **19.0.1.4.0**, pb_approval_config 19.0.1.6.5 → **19.0.1.6.6**,
pb_probation 19.0.1.4.0 → **19.0.1.4.1**, pb_goals 19.0.1.2.0 → **19.0.1.2.1**, pb_learn 19.0.20.5.14 → **19.0.20.5.15**.
PO gate files: `pb_home_hub/i18n/vi_VN.po` (changed: 71 entries); the other four `.po` files unchanged
(pb_learn byte-identical to HEAD). JS/SCSS changed → asset purge + `web.assets.version` bump + warm-up per DB.
Served-asset checks after deploy: JS contains `pb.home.team` and `area:`; CSS contains `.pbtm-hero`.

Staged from `git archive HEAD` at `34e3565d2` (the two feature commits plus the request-focus fix, §9.1). HEAD also carries other
sessions' commits; none of them touch these five modules.

## 1. What changed, per file

| File | What |
|---|---|
| `pb_home_hub/models/team_facade.py` (new) | `pb.home.team` (AbstractModel). `can_open()`: any active employee with `parent_id.user_id = me` (sudo count, never raises). `get_team()`: reports = active direct reports in `env.companies`; each section in a savepoint, every other module through `self.env.get` (`_model()`), an uninstalled module = absent key. Sections: **today** (pb_today's own `_row` over the reports with its shift/grace rules when installed, else punches + approved leave; plus "not working today" from the working calendar), **decisions** (`pb.approval.inbox.list_requests(tab='mine', scope='me')` as the reader, cards → five tiles, amounts never read out), **probation** (`manager_user_id = me` AND a report, states consolidation / one_on_one / verdict, `pb_gate` not hr/ceo/approved), **goals** (check-ins planned/missed within 7 days, reviews planned within 14, same double filter, open years only), **training** (`pb.my.training.team()` reduced to counts + who is overdue), **hiring** (requested by or asked of me, in flight, confidential guard, `write_url` only for the request that is mine to write). Words built on the server in the reader's language (`format_date`). |
| `pb_home_hub/static/src/js/team_lens.js` (new) | `PbTeamLens` registered into `HOME_LENSES` as `team` (icon `users`, label "Team", title "My team", sequence 12, probe `pb.home.team.can_open`). Hero numbers filter the face strip in place; faces are buttons (arrow keys / Home / End via `railKeydown`); doors: inbox `area:<key>`, People › Probation `person:<id>` (only for readers who can open it), Talent › Goals `tab:checkins|reviews`, `/my/training/team`, hiring request page / Hiring board `pb_role_id` / `/my/hiring`, person drawer (HR) or the public employee page. Every door carries `pb_back` → Home › Team. |
| `pb_home_hub/static/src/xml/team_lens.xml`, `scss/team_lens.scss` (new) | Hero (light tint, eyebrow, sentence, faces with status dots, colour key), calm line, Waiting on you (QuietGlance), Conversations due (two cards), Learning, Hiring; skeleton, failure state with Try again, reduced-motion, phone layout. Anchors `tm-hero`, `tm-waiting`, `tm-conversations`, `tm-learning`, `tm-hiring`. |
| `pb_home_hub/__init__.py`, `models/__init__.py`, `__manifest__.py` | models import; three assets; 19.0.1.4.0; description paragraph. **No new depends.** |
| `pb_home_hub/i18n/vi_VN.po` | 71 entries (27 python, 22 JS, 22 template), each `#. module` / `#. odoo-python|odoo-javascript` / `#: code:…:0`; the owner's words used as given (Đội của tôi, Đang chờ bạn, Nghỉ phép, Chưa bắt đầu, Đi muộn, Cuộc trò chuyện đến hạn, Đào tạo, Yêu cầu tuyển dụng của tôi, Hôm nay không có gì cần bạn). |
| `pb_home_hub/tests/test_team_p3c.py` (new), `tests/__init__.py`, `tests/test_home_hub.py` | 16 tests (§2). The old "hub ships no model and no python at all" test now asserts exactly one AbstractModel facade, no table, no security folder. |
| `pb_approval_config/static/src/js/inbox.js` | `focusArea()`: `pb_focus: "area:<key>"` lights that area chip on arrival, once per arrival (WeakSet); `request:<id>` unchanged. |
| `pb_probation/static/src/js/probation_board.js`, `probation_palette.js` | Lens `wantsArrival: true`; `pb_focus: "person:<id>"` opens that person's drawer once per arrival. |
| `pb_goals/static/src/js/goals_board.js`, `goals_palette.js` | Lens `wantsArrival: true`; `pb_focus: "tab:checkins|reviews"` opens that tab once per arrival. |
| `docs/tutorial_poc/author/data.js`, `practice-data.js` | `hub_home.tabs.team` ("Team" / "Đội của tôi" + one line), the Home `next` sentence ("If people report to you, Team shows your day with them on one screen."), practice MENU entry after Inbox. |
| `pb_learn/static/src/anchors.json` | Five `tm-*` anchors `reserved: true`, file `pb_home_hub/static/src/xml/team_lens.xml`, screen `team`; that file added to the scanned templates. |
| `pb_learn/static/content/learn_content.json`, `engine/fixture.js`, `__manifest__.py` | Regenerated; 19.0.20.5.15. |
| Learn commit also carries | The Learn session's two owner-requested hunks (gitlocal-09), kept as asked: `gen_learn_data.py` `SCREEN_ACTION_TAGS['payruns'] = 'pb_payruns'`; four English lines in data.js now "Figures do not add up". After my regeneration: `learn_content.json` payruns `action_tags` = `pb_payruns`, zero "These figures", "gõ DUYỆT" = 1; vi_VN.po byte-identical. |

## 2. Tests

Local runtime `/Users/adity/odoo19`, staging tree = `git archive HEAD` minus outputs/RIZE with the seven modules of
`7a2deccb4` pinned to `3f4ff7be4` (ledger), my five modules over it; the committed trees were diffed against the tested
tree: **identical**. Test DB `am_nav_p3c_t` (copy of `am_nav_p3b`); baseline `am_nav_p3c_base` (same copy, HEAD code).

| Run | Result |
|---|---|
| `test_team_p3c` (16) | **16 passed**: can_open true/false by reports (incl. a user with no reports); exactly the 3 reports, never the fourth under another manager, never an archived one; buckets add up to the strip (attendance → in, approved leave → on leave, nothing → not started); a planned shift with no punch → "late, not in yet", amber, still counted under not started (pb_today's own rule); decisions total = `counts.mine`, tiles sum to it, process area switch moves the cards from Other to Overtime; `list_requests` only ever called with tab mine / scope me; probation rows only `manager_user_id = me` AND a report AND my step; goal rows the same even when the reader holds the goals HR group; training = `pb.my.training.team()` counts; hiring excludes a confidential role not mine and an agreed one, puts "waiting on you" first, hands out the writing link only for the request that is mine to write, no `budget` key; five modules faked absent → five keys absent, strip still drawn; **recursive walk: no key containing amount / salary / wage / budget / cost / money / currency / pay_ / pip / growth / red_flag / flag / training_pending / score / rating / verdict**; the walker proven to reach nested lists; no new manifest dependency, no `pb.pip`, no hard `self.env['pb.…']`; lens registration + probe + anchors; no vendor name in any `_t()` word or template text; every door names its filter. |
| Full `-u` of the five modules, `--test-tags /pb_home_hub,/pb_approval_config,/pb_probation,/pb_goals,/pb_learn` (762 tests) | 6 failed / 8 errors — **exactly the baseline's 13 names** (746 tests on HEAD: TestStatutoryRightNow ×7, TestGuideTruth.test_01, TestLearnrevP5.test_f2, TestInboxFacade.test_no_fact…, TestP7Vietnamese ×2, TestSeed.test_u12). Nothing fails only with P3c. TestAnchorRegistry and the rest of TestGuideTruth pass (guide_truth runs inside TestGuideTruth; the Learn session's sentence change passes it). |
| Learn JS `library` / `guide_panel` / `lesson_panel` | **111 / 117 / 113 passed, 0 failed** |
| `gen_learn_data.py --check` | "generated data is up to date (6 files)"; readability max 28 words |
| `check_contract.py` | 73 checks passed |
| PO gate (Odoo `PoFileReader`) | pb_home_hub 80 rows, pb_learn 240, pb_approval_config 726, pb_probation 65, pb_goals 27 — 0 code rows without a value |
| `get_team` cost (manager with 3 reports, 5 inbox cards, warm) | median **172 ms, 122 queries** (most of it the inbox's own card build and the training refresh); `can_open` 1 ms. |

## 3. Chrome walk (local `localhost:8069`, DB `am_nav_p3c`, seeded)

Seed (local only, `odoo shell`): manager "DEMO Trần Minh Quân" (internal user only, Vietnamese) with 3 direct reports —
Hoa in since 07:19 on a shift, Nam on a shift 75 min ago with no punch, Linh on approved leave to Fri — and
"DEMO Hoàng Văn Khác" under another manager; 4 requests through the real "their manager" routes (2 leave, overtime,
trip) plus the leave's own request; Nam's 1:1 due Fri, Hoa's recommendation (trial ends Sun); Hoa's monthly
conversation 6 days late, Linh's half-way review in 10 days; Nam 8 days past a required course; one hiring request
asked of the manager, one sent in.

| # | Check | Result |
|---|---|---|
| 1 | HR admin without reports | **Pass.** Rail PULSE · INBOX · ASK HR · WALL · ANNOUNCE — no Team. |
| 2 | Manager: hero adds up | **Pass.** "Đội của bạn gồm 3 người · 1 có mặt hôm nay · 1 đi muộn · 1 nghỉ phép · 1 chưa bắt đầu · 5 việc đang chờ bạn" — 1 + 1 + 1 = 3 faces; Nam amber, Hoa green, Linh blue; tooltips "Nam · đi muộn, chưa có mặt (79 phút)", "Linh · nghỉ phép đến Th 6 23 thg 10". Rail word "ĐỘI CỦA TÔI" fits on two lines. |
| 3 | Hero number filters the faces | **Pass.** "1 đi muộn" pressed → only Nam lit, `aria-pressed` true; pressing again clears. |
| 4 | Waiting on you → inbox area | **Pass.** "3 Nghỉ phép" → Home › Inbox, My turn, the **Giờ** (Time) chip on, 4 time cards, back chip "← Đội của tôi" returns to the Team tab. |
| 5 | Probation, plain manager | **Changed after the walk** (see §5.1): the spec's review form refused the manager ("You don't have access"). Rows are now plain text with the line "The HR team runs these reviews and will ask you for each step." Re-walked: rows flat, note shown. |
| 6 | Probation, reader who can open the board | **Pass.** Admin given one temporary report + review: row → People › PROBATION with that person's drawer open, back chip "← My team". (Temporary data removed after.) |
| 7 | Goals | **Pass.** Hoa's row → Talent › Goals on **Monthly conversations** showing Hoa 6 days overdue; Linh's row → the **Reviews** tab; back chip returns. |
| 8 | Learning | **Pass.** "1 người có khóa đào tạo bắt buộc đã quá hạn · Nam · trễ 8 ngày" → `/my/training/team` showing Nam 8 days overdue. Browser Back lands on Home's first tab (the portal is a separate page). |
| 9 | Hiring | **Pass after a fix** (§5.2): "DEMO Weekend cashier · Đang chờ bạn viết · Đang chờ bạn" → the request-writing page; first version sent a plain manager to `/my/hiring`, which does not list a request they were asked to write. |
| 10 | Faces open the person | **Pass.** Plain manager: keyboard End + Enter on Linh → her public employee page with the Home breadcrumb. HR reader: the People screen's person drawer. |
| 11 | Keyboard | **Pass.** Arrow keys move between faces (focus ring visible), Home/End jump, Enter opens; every door is a real button. |
| 12 | English | **Pass.** "Your team of 3 · 1 in today · 1 late · 1 on leave · 1 not started yet · 5 things waiting on you"; tiles Time off / Overtime and timesheets / Expenses and trips / People / Other. |
| 13 | Access › Screens (R8) | **Pass, unchanged.** Lists left-menu entries only; Home "Everybody with a login" as before. No sidebar item, so nothing new to list. |
| 14 | Console | **Clean** on the Team tab and every door. One pre-existing warning on Home load for a plain user: "pb_home_hub: could not read the period state" (the pay tracker; not touched). |
| — | Not walked | Phone width (CSS written, not seen); a database without one of the modules (covered by test 10); the green "all accounted for" calm line (covered by code, the seed always had something due). |

## 4. Learn (R7)

Home's Team tab line and practice menu entry (EN + VI), the Home "next" sentence, five reserved anchors, regenerated,
`.po` unchanged, pb_learn bumped. No lesson step points at Team (reserved anchors). No screen guide is owned by
pb_home_hub, so no guide wording of mine changed; the Learn session's "Figures do not add up" sentence passes the guide
truth test.

## 5. Deviations (spec vs code) and decisions

1. **No probation form door for a plain manager.** The review form refuses them on `feedback_request_ids`; the board is
   HR's. Rows are informational with a plain sentence; the board door is offered to readers who can open it. Ledger row.
2. **Hiring door is three-way:** the writing page (`/hiring/r/<token>`, only for the request that is the reader's to
   write — the same link the email carries), else the Hiring board on the role, else `/my/hiring`. Ledger row.
3. **Faces use initials unless a real photo exists** (every employee stores a generated one-letter picture). Ledger row.
4. **Conversations due are two row cards, not QuietSteps** (QuietSteps is a pipeline). Hero numbers filter in place.
5. **"Off today"** added as a fifth bucket (no shift today and the working calendar says not a working day), so a
   weekend never reads "8 not started yet". Leave uses the Today board's states (`validate`, `validate1`).
6. **"Expenses and trips" door** filters the inbox only when its cards share one area; otherwise My turn unfiltered.
7. **Station "home"** does not exist in Learn; the sentence went into `hub_home.next`.
8. **No ⌘K row** for Team (the palette cannot probe; a row would show to people with no reports).
9. **Person drawer for HR readers** is the People screen's own drawer and shows what it always shows (it masks wages
   for non-payroll managers itself). Nothing from it enters the Team payload.
10. Commit trailer: the session's attribution rule (`Co-Authored-By: Claude Opus 5.5`), as P3a/P3b.

## 6. Deploy plan (as written at the gate; carried out in §9)

Normal tier: R14 START line in `/opt/deploy-notes.md` + lock, cron snapshot, clean `/tmp/deployP3C` from
`git archive` of the two commits, per-module scoped rsync, tree hashes, PO gate on the box, `-u` list above on
payobook / payobook_template / p0clone / rize (never abm), asset purge + version bump + `orm_signaling_assets`, start,
warm each bundle with one login curl per DB, crons back to the snapshot, versions, DONE line. Live checks: served JS has
`pb.home.team`, served CSS has `.pbtm-hero`; the payobook.com browser walk with a manager login is an owner step (an
agent may not type the QA password).

## 7. R11 self-score

1. Hero moment: one sentence and a row of faces — "Your team of 3 · 1 in today · 1 late · 1 on leave · 1 not started
   yet · 5 things waiting on you" — the numbers add up to the faces, and pressing one lights the faces it means.
2. Zero dead ends: every tile opens the screen already filtered with a way back; where no screen exists for the
   reader (probation, a plain manager) the card says who runs it instead of offering a door that ends on "no access".
3. Plain language, both languages, the owner's Vietnamese words; dates in the reader's own format; no money anywhere.
4. Motion with purpose: faces pop in staggered, sections rise once, dimming on filter; all off under reduced motion.
5. Keyboard: faces arrow/Home/End/Enter, every door a button with a focus ring. Weakest: phone width not walked, and
   `get_team` costs ~170 ms because the inbox builds full cards to be counted.

## 8. Commits (pushed to origin/19.1)

`fcabc8977` feat(nav-p3c): Home › Team for people who manage others ·
`e40b45577` feat(nav-p3c): Learn knows Home › Team (also carries the Learn session's LR80 tag and "Figures do not add
up" hunks) · `d7aa9ba2f` docs(nav-p3c): report and five ledger rows · `34e3565d2` fix(nav-p3c): a request focus always
wins over an inbox area · (this deploy record). The push also carried ChatGPT's four commits above them
(`97ba269df`, `c338cb081`, `ca14c26c1`, `f1b13ddff`) as they were, owner-approved; none of them is in this deploy.

## 9. Deploy record (normal tier, 2026-10-21 02:17–02:21 UTC, Payobook19v2)

### 9.1 Before the stop: PayAI's request focus (coordinator's check)

PayAI opens ONE request from Home › Inbox with `pb_focus: "request:<id>"` (hub `arrival.focus`, falling back to
`action.context.pb_focus`). The two arrivals were already exclusive (one `pb_focus` string; `focusArea` matches only
`^area:[a-z]+$`, `focusRequest` only `^request:…`), and the area starts empty, so a focused request is never filtered
out. Made explicit anyway in `34e3565d2`: `const area = focus ? "" : focusArea(arrival);` — the area is read only when
there is no request focus. Checks: `test_team_p3c.test_15` pins the guard and both parsers (pb_home_hub 55 tests,
0 failures, rerun locally); and a node check that evaluates the three real functions out of `inbox.js`:
`arrival request:42` → request 42, no area · `context request:42:team` → request 42 scope team, no area ·
`arrival area:time` → area time · `area:bogus` → nothing · empty arrival + `context request:7` → request 7, no area —
**5/5**. The served bundle contains the guard (`const area=focus?"":focusArea(arrival)`).

### 9.2 Lock and notes

`/opt/deploy-notes.md` at 01:41 had an open START from "Claude Opus (VIFIX P1 audit)" (a read-only clone with its own
odoo-bin on 127.0.0.1:8077); the lock itself was free. Polled every 2 min; its DONE (clone dropped, process stopped)
landed at 02:17 and no other START was open. ChatGPT was also waiting (01:49 coordination line). Ran at once as one
detached unit under `flock /tmp/payobook-studio-deploy.lock` (script: START line → check no other `odoo-bin -c` →
cron snapshot → checksum dry run → stop → copy → hash → PO gate → four upgrades, p0clone first → asset steps → start →
warm-up → crons → versions → Learn content → DONE line). Service down **3 min 9 s** (stop 02:18:00, port 8069 back
02:20:52). START 02:17 and DONE 02:21 lines in the notes file; lock free afterwards.

| Step | Result |
|---|---|
| Staging | `git archive HEAD` of the five modules at `34e3565d2` (289 files) into a clean `/tmp/deployP3C`; tree hashes equal to the locally tested tree and to the local stage: pb_home_hub `355b1c89206a`, pb_approval_config `c272a3da38a0`, pb_probation `7d7380b3e407`, pb_goals `41c7fd0967b9`, pb_learn `9715bf5d5639`. |
| PO gate on the staged files (local, Odoo `PoFileReader`) | 80 / 726 / 65 / 27 / 240 rows, 0 code rows without a value. |
| Overwrite check | `rsync --dry-run --checksum`: content changes are exactly this phase's files (pb_home_hub: `__init__`, manifest, vi_VN.po, new models/, team_lens.js/.scss/.xml, tests; pb_approval_config: manifest, inbox.js; pb_probation: manifest, probation_board.js, probation_palette.js; pb_goals: manifest, goals_board.js, goals_palette.js; pb_learn: manifest, learn_content.json, anchors.json, fixture.js). No deletions. |
| Crons before | p0clone 26, payobook 37, payobook_template 0, rize 69. |
| Copy + hashes | Per-module scoped `rsync -a --delete`; live tree hash = staged for all five; owner as the other modules. |
| PO gate (on the box) | pb_home_hub 80, pb_approval_config 726, pb_probation 65, pb_goals 27, pb_learn 240 rows — **0 failures**. |
| Upgrades `-u pb_home_hub,pb_approval_config,pb_probation,pb_goals,pb_learn` | p0clone EXIT=0 43 s · payobook EXIT=0 46 s · payobook_template EXIT=0 39 s · rize EXIT=0 39 s; 0 CRITICAL, 0 ERROR, 0 tracebacks (only the docstring RST warning from another module, as in P3b). |
| Assets | Per DB `INSERT INTO orm_signaling_assets`, `/web/assets/%` attachments deleted, `web.assets.version` = 1792549249917. |
| Start | Port 8069 up, `/web/health` 200, "Registry loaded" ×3 in the log since the stop, **0 ERROR/CRITICAL since start**. |
| Warm-up (one at a time) | payobook.com, rize.payobook.com, p0clone.payobook.com: login 200; `web.assets_web.min.css` 3.78 / 3.69 / 3.69 MB, `.min.js` 13.7 / 13.5 / 13.5 MB — none empty; served JS has the team lens key (`pb.home.team`) and the request-wins guard; served CSS has `.pbtm-hero`, on all three. payobook_template has no hostname (files identical, versions current). |
| Crons after | The upgrade switched on 18 jobs in payobook_template (43, 44, 51, 54–58, 60, 62, 63, 67, 68, 71–75), as in P2/P3a/P3b; switched off again. **Final: p0clone 26, payobook 37, payobook_template 0, rize 69** (expected 26 / 37 / 0 / 69). |
| Versions | pb_home_hub 19.0.1.4.0, pb_approval_config 19.0.1.6.6, pb_probation 19.0.1.4.1, pb_goals 19.0.1.2.1, pb_learn 19.0.20.5.15 on all four databases. |
| Live Learn content | payobook.com `learn_content.json` (1.61 MB): "gõ DUYỆT" = **1**, "These figures" = 0, payruns `action_tags` = **pb_payruns**, Home's Team tab ("Đội của tôi") present. |
| Not done | The payobook.com browser walk (coordinator's instruction; an agent may not type the QA password). |
