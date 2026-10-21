# NAV P3d — Home › Ask HR as a Payobook board — report

Implementer: Opus, 2026-10-21. Spec: `docs/handovers/NAV_P3D_ASK_HR_BOARD.md` §1–6. Ledger: seven new P3d rows in
`docs/handovers/NAV_LEDGER.md`. **Stopped at the deploy gate — nothing deployed, nothing pushed.**

## 0. Exact deploy lists

```
-u pb_ask_hr,pb_learn
```
Rsync (scoped `--delete` per module): `pb_ask_hr`, `pb_learn`. No `-i`, no new table (`pb.ask.hr` is an
AbstractModel), no ACL, no record rule, no data file, no sidebar change. **One migration**:
`pb_ask_hr/migrations/19.0.1.2.0/post-nav_p3d_reload_terms.py` (re-reads pb_ask_hr's own `.po` with overwrite, so
the stored Vietnamese status / pill / filter words follow the two changed words — see §5.4). Versions: pb_ask_hr
19.0.1.1.0 → **19.0.1.2.0**, pb_learn 19.0.20.5.15 → **19.0.20.5.16**. PO gate files: `pb_ask_hr/i18n/vi_VN.po`
(changed: 87 new entries, 13 shared entries gain markers/occurrences, 3 msgstr changed); `pb_learn/i18n/vi_VN.po`
byte-identical to HEAD. JS/SCSS changed → asset purge + `web.assets.version` bump + `orm_signaling_assets` + warm-up
per DB. Served-asset checks after deploy: JS contains `"pb.ask.hr","get_board"` (or `pbhub.askhr.filters.v1`), CSS
contains `.pbah-board`. Tree hashes of the committed modules (`git archive HEAD`, same script as P3c), equal to the
locally tested tree: **pb_ask_hr `2db6bf0b8fe2`, pb_learn `64194a1bc11f`**.

Staging note (ledger P3b): the local tree was P3c's (HEAD at `34e3565d2` with the seven `7a2deccb4` modules pinned to
`3f4ff7be4`) with my two modules + `docs/tutorial_poc` over it. Commits since then on HEAD (ChatGPT's mapping fixes,
VIFIX tools) touch neither module. For the box, stage `git archive HEAD pb_ask_hr pb_learn` only.

## 1. What changed, per file

| File | What |
|---|---|
| `pb_ask_hr/models/askhr_board.py` (new) | `pb.ask.hr` facade, everything AS THE READER (no `sudo(` in the file — a test pins it). `get_board()`: exact step counts (`_read_group`), open questions (cap 500) + 60 newest closed, cards (number, subject, one line of the question unless it repeats the subject, category + label, person name + department via `hr.employee.public`, owner, `mine`, age words, `late` = new and > 2 working days, `answered_week`, new-reply dot: for HR "the person wrote last" on new/with HR, for others "HR answered" on answered), glance figures, "Last question answered X ago", and for HR only the median first reply over questions asked in the last 30 days (§5.5). `get_owners()`: active internal users in HR or admin, in the companies being looked at, "you" first. `act(verb, payload)`: `take` / `hand` / `close`, refuses anybody without write access before touching anything, reads the ids through the rules, skips closed ones and says so. Words in the reader's language and decimal mark ("1,5 ngày"). |
| `pb_ask_hr/models/ticket.py` | `_pb_set_owner(user, remind)` — the one way a question changes hands (owner, new → with HR, follower, the open to-do moves; a hand-over to someone else schedules one when there was none; no second "assigned" mail). `action_take` now calls it (same outcome as before + the to-do follows). New `action_hand_to(user_id)` (only somebody in the HR team or an admin, else "Pick somebody in the HR team.") and `action_close_with_note(note, tell_person)` (public reply or private note, then the existing `action_close`). |
| `pb_ask_hr/static/src/js/askhr_lens.js`, `xml/askhr_lens.xml`, `scss/askhr_lens.scss` (new scss) | The board: head (title, refresh, "Open as a list" for HR, "Ask a new question" for others), QuietGlance (`ah-glance`), QuietSteps (`ah-steps`), filter chips (Mine, Nobody has it yet with its count, categories in use) + search with `/`, "N questions at <step>" / "Showing x of y" + Clear, "Select all here", cards (`ah-card`, Take it `ah-take`, Hand to…), keyboard line, bulk bar (Take it / Hand to… / Close with a note / clear), Hand-to sheet (search, arrow keys), close sheet (note + "Tell the person" / "Keep it inside HR"), empty states, skeleton, failure with Try again, phone layout, reduced motion. Filters remembered per person under `pbhub.askhr.filters.v1`. Lens key/seq/groups and the ⌘K row unchanged. |
| `pb_ask_hr/static/src/scss/ask_hr_backend.scss` | The P2 `.pbah-lens` View wrapper block removed (unused); the native kanban styles stay. |
| `pb_ask_hr/controllers/portal.py` | `_render_new` → `_ask_hr_render_new` (live 403 bug, §5.2). |
| `pb_ask_hr/i18n/vi_VN.po` | See §0; owner's words as given. |
| `pb_ask_hr/migrations/19.0.1.2.0/post-nav_p3d_reload_terms.py` (new) | §5.4. |
| `pb_ask_hr/__manifest__.py` | 19.0.1.2.0, the new scss, description paragraph. No new depends. |
| `pb_ask_hr/tests/test_board_p3d.py` (new), `tests/__init__.py`, `tests/test_ask_hr.py` | 18 tests (§2); the P2 "mounts the real kanban" test now checks the registration only. |
| `docs/tutorial_poc/author/data.js`, `practice-data.js` | Home's Ask HR tab line (what HR can do, others see only their own), Home `next` sentence (HR: the ones nobody has yet), `PRACTICE.askhr`, practice menu Ask HR → screen `askhr`. EN + VI. |
| `pb_learn/static/src/engine/screens.js` | Small `askhr` replica: numbers + median, four steps, Mine / Nobody has it yet chips, three cards, Take it on the late one nobody has. |
| `pb_learn/static/src/anchors.json` | `ah-glance`, `ah-steps`, `ah-card`, `ah-take` reserved, file `pb_ask_hr/static/src/xml/askhr_lens.xml`, added to the scanned templates. |
| `pb_learn/static/content/learn_content.json`, `engine/fixture.js`, `__manifest__.py` | Regenerated; 19.0.20.5.16. |
| `docs/handovers/vifix/tools/vifix_replica_drift.py` | One mapping line for the new `askhr` replica (it reported "real screen not found"). |

## 2. Tests

Local runtime `/Users/adity/odoo19`, test DB `am_nav_p3d_t` (copy of `am_nav_p3c_t`), baseline `am_nav_p3d_base`
(same copy, HEAD code). The committed trees are hash-identical to the tested tree (§0).

| Run | Result |
|---|---|
| `test_board_p3d` (18) | **18 passed**: counts add up to every question and match each state; `late` only for new questions older than 2 working days; `answered_week`; card fields (number, person, department, category, nobody, line); **an employee sees only their own questions — another person's subject, answer and name appear nowhere in the JSON**; an employee who asked nothing gets an empty board with the Ask door; an employee cannot `take`/`hand`/`close`/`get_owners` (AccessError, nothing changed); no `sudo(` in the facade; Take it via the board = Take it on the form (state, owner, follower); Hand to: owner, state, follower, the to-do goes to the receiver, handed on again it moves (not doubled), never to a non-HR user, "you" first in the picker; Close told (public reply on the person's page) vs kept (internal note), closed_by HR, already-closed skipped and said; unknown verb / unreadable ids refused; **median over the 30-day window = 4 days** for replies at 2/4/6 days (the 6-day one had the person's own reply first; a 40-day-old one and an unanswered one excluded; "Mark answered" counted); first reply stays the first when `answered_on` moves later; new-reply dot for whoever is next; filter fields + category order + the storage key; the tab is the board (no `@web/views/view`), anchors, quiet board templates, no vendor name, native views still there; the owner's Vietnamese words in the .po; the new-question page helper is not shadowed; decimal mark "1.5 days" / "1,5 ngày". |
| Full `-u pb_ask_hr,pb_learn`, `--test-tags /pb_ask_hr,/pb_learn` (451 tests) | 7 failed / 8 errors — **exactly the baseline's 15 names** (433 tests on HEAD): TestStatutoryRightNow ×7 + its setUpClass, TestGuideTruth.test_01, TestLearnrevP5.test_f2, and five pb_ask_hr tests that already fail on HEAD on this copy because the users read Vietnamese (`TestAskHrModel.test_t3_1_lifecycle` expects an English error; `TestAskHrPages.test_t3_3/3b/3c/4` expect English page text). Nothing fails only with P3d. TestAnchorRegistry and the rest of TestGuideTruth (guide_truth.py) pass; the migration ran in the upgrade ("re-read with overwrite"), stored status vi = "Nhân sự đang xử lý". |
| Learn JS `library` / `guide_panel` / `lesson_panel` | **111 / 117 / 113 passed, 0 failed** |
| `gen_learn_data.py --check` | "generated data is up to date (6 files)" |
| `check_contract.py` | 73 checks passed |
| `vifix_replica_drift.py` | askhr: 27 labels checked, 0 Vietnamese drift; the 6 "gone" items are practice data (the three questions and departments), as on every other replica. |
| PO gate (Odoo `PoFileReader`) | pb_ask_hr 317 rows (113 code, 0 without a value or marker), pb_learn 240 (77 code, 0 bad); no vendor name in any msgstr. |
| `get_board` cost (HR, 7 questions, warm) | median **45 ms, 20 queries**. |

## 3. Chrome walk (local `localhost:8069`, DB `am_nav_p3d`, seeded)

Seed (local only, `odoo shell`, passwords in the scratchpad only): HR officers "DEMO Phạm Thu Hà" (Vietnamese) and
"DEMO Lý Minh Tâm"; askers "DEMO Đinh Thị Yến" and "DEMO Võ Quang Huy" (English, made a department head so he is
staff, not employee-only — §5.3), "DEMO Trương Thị Mai" (department head, asked nothing). Seven questions: 2 new (one
5 days old), 2 with HR (one where the person replied after HR's answer), 1 answered, 2 closed.

| # | Check | Result |
|---|---|---|
| 1 | HR board, Vietnamese | **Pass.** "2 mới (amber) · 2 nhân sự đang xử lý · 1 đang chờ người hỏi · 4 đã trả lời tuần này · 6.5 ngày …" (decimal fixed afterwards to the reader's mark, unit-tested "1,5 ngày"); steps Mới / Nhân sự đang xử lý / Đã trả lời / Đã đóng with "1 câu hỏi chờ quá 2 ngày làm việc" on Mới; cards with person · department, category chip, age (amber 5 ngày), "Chưa ai nhận" amber, Nhận xử lý / Chuyển cho…. |
| 2 | Keyboard Take it | **Pass.** Focus a card, ↓ moves, **T** → toast "Câu hỏi này giờ là của bạn.", With HR 3, "3 câu hỏi là của bạn". |
| 3 | Hand to… | **Pass.** **H** opens the sheet (focus in the search after the fix, ↓ into the list, Esc closes); picking Lý Minh Tâm → "Đã chuyển cho DEMO Lý Minh Tâm.", card shows her avatar. "Người hỏi vừa phản hồi" dot on the question where the person wrote last. |
| 4 | Filters persist | **Pass.** "Của tôi" on → form → breadcrumb back → still on; reload → still on. (Found: a colleague on the same browser inherited it invisibly — fixed, per-person storage.) |
| 5 | Bulk close with a note | **Pass.** Select all here → untick one → Đóng kèm ghi chú → note → "Báo cho người hỏi" → "Đã đóng 2 câu hỏi."; DB: both public replies, closed by HR. Again with "Chỉ lưu trong Nhân sự" → internal notes (subtype internal). Space selects the focused card. |
| 6 | Card → form → back | **Pass.** Native form (status bar "Nhân sự đang xử lý" — the migration's stored word), chatter present; breadcrumb "Trang chủ" lands back on HỎI NHÂN SỰ, not on the first tab. Same from "Mở dạng danh sách" (now the list view). |
| 7 | Calm empty state | **Pass.** All open closed → "Không có gì đang chờ. Câu hỏi gần nhất được trả lời cách đây chưa đến một giờ." + "Xem câu hỏi đã đóng". |
| 8 | Non-HR reader, English | **Pass.** "Your questions to HR · Ask a new question"; glance "1 waiting for HR · 1 answered, your turn (amber) · 1 closed"; only his three questions; no checkboxes, no Take it, owner shown; "HR replied" dot; Enter opens his own `/my/ask-hr/24` page with the reply box. |
| 9 | Ask a new question | **Fail → fixed.** `/my/ask-hr/new` answered **403** (§5.2, also from the portal's own list); after the rename the page renders. |
| 10 | Never asked | **Pass.** Mai (Vietnamese): "Bạn chưa hỏi Nhân sự điều gì." + Đặt câu hỏi mới. |
| 11 | Nobody matches | **Pass** (seen during #4's bug): "Nobody matches" + Clear. |
| 12 | Console | **Clean** on every screen walked (error filter). |
| — | Not walked | Phone width (CSS written, not seen); a plain employee-only login (they never reach Home — §5.3); Access › Screens (no sidebar item changed — R8 not affected). |

## 4. Learn (R7) and Access (R8)

Home's Ask HR tab line, the Home `next` sentence, `PRACTICE.askhr` and the practice menu entry (EN + VI), the
`askhr` replica, four reserved anchors, regenerated, `.po` unchanged, pb_learn bumped. No lesson step points at the
board yet (reserved). No screen guide is owned by pb_ask_hr (no `learn_manifest.py`). Access: no sidebar entry or lens
added, moved or renamed — nothing new for the Screens lens.

## 5. Deviations (spec vs code) and decisions

1. **Form in the main screen, not a side sheet.** Odoo draws no chatter inside a dialog and the chatter is the answer
   box; the board makes the breadcrumb return to the Ask HR tab (`rememberHere`). Ledger row.
2. **Live bug fixed in passing:** `/my/ask-hr/new` was 403 wherever Expenses is installed (method name shared with
   pb_me_expense's portal controller). Every "Ask a new question" link on the employee pages was a dead end. Ledger.
3. **"Employee view" = non-HR staff.** An employee-only person is sent to `/my` for every backend URL, so the board's
   own-questions view serves department heads and other staff; their card opens their own `/my/ask-hr/<id>` page (the
   backend form is read-only for them). The Ask button opens `/my/ask-hr/new` (the asking page) rather than the list.
4. **Two shared Vietnamese words changed everywhere** ("With HR" / "with HR" → "Nhân sự đang xử lý", "Nobody has it
   yet" → "Chưa ai nhận") with a migration that re-reads pb_ask_hr's terms with overwrite. This also changes the
   employee's portal pill and the native screens' words. Ledger.
5. **Median = first public HR answer**, not `answered_on − create_date` (`answered_on` is the last answer). HR only.
6. **"Answered this week" is a filter across steps** (steps unlit), counted over every question the reader can see.
7. **Filters per person** in `pbhub.askhr.filters.v1` (`{uid: …}`); the step is not remembered (lands on the first
   step with something in it).
8. **Close with a note defaults to "Tell the person"** — closing without telling leaves the person with a closed
   question and no reason; "Keep it inside HR" is one click.
9. Commit trailer: the session's attribution rule (`Co-Authored-By: Claude Opus 5.5`), as P3a–P3c.

## 6. Commits (local, NOT pushed)

`52d9041db` feat(nav-p3d): Home › Ask HR as a Payobook board · `455ad535a` feat(nav-p3d): Learn knows the Ask HR board
(also carries the one-line VIFIX drift-tool mapping) · `6ed7a5b12` docs(nav-p3d): report and seven ledger rows.

## 7. Deploy plan (for the coordinator's go — normal tier)

R14 START line in `/opt/deploy-notes.md` + `flock /tmp/payobook-studio-deploy.lock`, no other `odoo-bin -c` running,
cron snapshot, clean `/tmp/deployP3D` from `git archive HEAD pb_ask_hr pb_learn`, checksum dry run (expect only this
phase's files; `pb_ask_hr/static/src/scss/askhr_lens.scss`, `models/askhr_board.py`, `migrations/19.0.1.2.0/`,
`tests/test_board_p3d.py` new), stop, per-module scoped `rsync -a --delete`, tree hashes (§0), PO gate on the box,
`-u pb_ask_hr,pb_learn` on p0clone → payobook → payobook_template → rize (never abm), check the log for "re-read with
overwrite", asset signal + purge + version bump, start, warm each bundle with one login curl per DB, crons back to the
snapshot, versions, DONE line. Live checks: served JS has `pbhub.askhr.filters.v1`, CSS has `.pbah-board`;
`/my/ask-hr/new` answers 200 for a signed-in employee (curl with a session is an owner step); payobook.com browser
walk with an HR login is an owner step (an agent may not type the QA password).

## 8. R11 self-score

1. Hero moment: "Nobody has it yet" in amber turns into your face with one key (T), the card slides to With HR and
   the step says "3 are yours" — the queue is worked from the keyboard.
2. Zero dead ends: every card opens something the reader can act on (HR: the form with its answer box, back to this
   tab; others: their own conversation page); found and fixed the 403 on the asking page; every empty state has a door.
3. Plain language both ways, the owner's Vietnamese, numbers in the reader's decimal mark, no vendor name.
4. Motion with purpose: 120 ms slide on a step change, the bulk bar rises once, nothing else; off under reduced motion.
5. Keyboard: arrows, Enter, Space, T, H, /, Esc, arrow keys in the picker, focus lands in each sheet. Weakest: phone
   width not walked, and the Back button from a person's portal page lands on Home's first tab (full-page navigation).
