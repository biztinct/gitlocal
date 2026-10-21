# NAV P3b — Payroll: readiness on the run cards — report

Implementer: Opus, 2026-10-21. Spec: `docs/handovers/NAV_P3B_PAYROLL_READINESS.md` §1–5. Ledger: six new P3b rows in
`docs/handovers/NAV_LEDGER.md`. **Not deployed — stopped at the deploy gate (§6 waits for the coordinator's go).**

## 0. Exact deploy lists

```
-u pb_payruns,pb_learn
```
Rsync (scoped `--delete` per module): `pb_payruns`, `pb_learn`. `pb_payhub` unchanged (no file touched; its tests
run unchanged). No `-i`, no migration scripts, no data change, no new model or field. Versions: pb_payruns
19.0.3.0.8 → **19.0.3.1.0**, pb_learn 19.0.20.5.13 → **19.0.20.5.14**. PO gate files: `pb_payruns/i18n/vi_VN.po`
(changed), `pb_learn/i18n/vi_VN.po` (unchanged, `cmp` before/after). Served-asset checks after deploy: JS contains
`Ready to send in` and `pb_shell_lens: "close"`; CSS contains `.pbr-checks`.

Stage from the **commit** (`git archive HEAD pb_payruns pb_learn`), not the working tree. Note: HEAD also carries
another session's commits (`7a2deccb4`, `57b8ac352`) in other modules; they are not in this -u list and not mine
to deploy.

## 1. What changed, per file

| File | What |
|---|---|
| `pb_payruns/models/pb_payruns.py` | `get_board_data` builds one readiness context per load (`_readiness_context`): Payroll owner per company (`_payroll_owners`, `biz.approval.responsibility.resolve(company, payroll_mgr, [''])`, pool first user), close status per open run (`_close_status`, ONE `pb.wf.lock._locked_pairs` call over every open run's days; weeks by pb_close's rule in `_close_weeks`), attendance owner per run (`_attendance_owners`, ONE grouped SQL on `hr_payslip ⋈ hr_employee.attendance_manager_id`, flushed first), and whether the reader may open Workforce › Close (`_close_door`). Per run `_run_checks` → `checks` (sent_back · unsourced · balance · close_week, each `{key, tone, icon, text, full?, detail, owner{name, short, uid, me, team}, next{key,label}|None, advisory, more}`), `ready`, `close_weeks{closed,total}`. Period gains `cutoff`, `pay_date`, `cutoff_in_days`, `pay_in_days`, `cutoff_label`, `pay_label` (`_calendar_dates`: company row before shared, read as the system; labels formatted on the server from the DATE, so no west-of-UTC shift). Old keys (`unsourced`, `balance_ok`, `balance_gap`, `return_note`…) kept. `pb_comp_ben` / `pb_close` / `pb_mission` read softly (`env.get`, `'pb.wf.lock' in env`, `env.ref(..., raise_if_not_found=False)`); **no new depends**. |
| `pb_payruns/static/src/js/payruns.js` | `notes(b)` → `checks(b)` (server lines + green "Ready to send in"; none on Done/Rejected). `deadline(p, rs)` for the hero (before / day-before / today / after cut-off; after pay day green "Paid on …" when every run of the month is paid, else amber "Pay day was …"; absent without a calendar row). Owner helpers `ownerLabel` / `ownerTitle` ("you"), `weeksClosed`, `openCheck` (run → the run; close → `pb_mission.action_pb_workforce` with `pb_shell_lens: "close"` and a `pb_back` chip to Payroll › Runs, or to the standalone board). |
| `pb_payruns/static/src/xml/payruns.xml` | Card: `ul.pbr-checks` (`data-coach="pk-checks"`), each line icon · sentence (2-line clamp) · door · owner chip (`pk-owner`). Hero: `.pbr-deadline` (`pk-deadline`) under the range. Quick look: the checklist in full sentences with "Owner" and the full name, door, "Weeks closed 3 of 4"; the duplicate sent-back line and the duplicate unsourced line in The money are dropped while the checklist shows them. No new `!props.embedded` guard. |
| `pb_payruns/static/src/scss/payruns.scss` | `.pbr-checks` / `.pbr-chl` (tone in icon + soft wash; advice line white with an amber edge), `.pbr-owner` (`.is-me` brand tint, `.is-team`), `.pbr-deadline`, quick-look `.pbr-pchecks`; old `.pbr-note` rules removed; reduced-motion covers the line fade. |
| `pb_payruns/i18n/vi_VN.po` | 30 new entries (13 python, 15 board JS, 2 template), each with the three comment lines; 6 existing entries gained the flag of the side that now says them (5 JS words the server now says; "Submit for approval" gained the JS flag — it was English on the card in Vietnamese, pre-existing). |
| `pb_payruns/learn_manifest.py` | Runs guide reads the server file too (`_BOARD_PY` in `templates`); balance column "Figures do not add up". |
| `pb_payruns/tests/test_readiness_p3b.py` (new), `tests/__init__.py`, `tests/test_board_redesign.py` | 15 tests (below); the period test pins the four new keys. |
| `pb_payruns/__manifest__.py` | 19.0.3.1.0 + comment. |
| `docs/tutorial_poc/author/data.js` | Runs station `what`: the checklist (owners, Ready to send in, attendance advice never stops Submit) and the cut-off / pay-day line, EN + VI. |
| `docs/tutorial_poc/author/practice-data.js` | F&B card `checks` (sent back → Phan Minh Tú; attendance week of 27 Jul → Lê Thu Trang, advice); `boardDeadline` "Changes closed Tue 28 Jul · People are paid on Wed 5 Aug" (VI in the product's own date format). |
| `pb_learn/static/src/engine/screens.js` | `payruns` replica: hero deadline line (`pk-deadline`), card checklist with owner chips (`pk-checks`, `pk-owner`), green ready line when a row is ready. |
| `pb_learn/static/src/anchors.json` | `pk-checks` (repeats), `pk-owner` (repeats), `pk-deadline` — all `reserved: true`, file `pb_payruns/static/src/xml/payruns.xml`. |
| `pb_learn/tests/guide_truth.py` | One key: the replica exemption "Figures don't add up" → "Figures do not add up" (outside the brief's Learn file list; see §5.4). |
| `pb_learn/static/content/learn_content.json`, `static/src/engine/fixture.js` | Regenerated. |
| `pb_learn/__manifest__.py` | 19.0.20.5.14. |

## 2. Tests

Local runtime `/Users/adity/odoo19`. Staging tree = `git archive HEAD` minus outputs/docs/RIZE + `docs/tutorial_poc`,
with the seven modules of another session's commit `7a2deccb4` pinned back to `3f4ff7be4` (they break registry load on
the local copies — ledger row) and only pb_payruns / pb_learn from this phase over it. The committed pb_payruns and
pb_learn trees were diffed against the tested tree: **identical**. Test DB `am_nav_p3b_t` (copy of `am_nav_p3a`);
baseline DB `am_nav_p3b_base` (same copy, HEAD code for both modules).

| Run | Result |
|---|---|
| `test_readiness_p3b` (17) | **17 passed** (after the started-weeks change; `/pb_payruns` + `/pb_payhub` rerun: only the 3 baseline names fail): period keys with no row; future dates and days ahead; company row beats shared, past dates negative; every card carries checks/ready/close_weeks; sent back owned by the preparer (given name in the card text, full name in the quick look); sent back + no source data + open week in spec order with owners; owner fallback Payroll manager → "Payroll team"; balance gap text; "me" flag; pb_close week rule (a week counts only its days in the period); max two week lines then "+2 more weeks", gone when locked, count kept; a reopened day reopens its week; ready only for a clean draft (Done → no checklist); Submit still offered with an open week; Learn's own ready rule unchanged. |
| `/pb_payruns` + `/pb_payhub` (152 tests) | 3 failed — **the same 3 names fail on the baseline** (`TestRevivedRunsCockpit.test_the_division_filter…` literal check, `TestStandaloneUnchanged.test_every_embedded_guard…`, `TestInLensLedger.test_get_detail…`). `test_board_redesign`, `test_board_currency`, `test_approval_engine`, `test_payhub` otherwise pass. |
| Final run, `-u pb_payruns,pb_learn --test-tags /pb_payruns,/pb_payhub,/pb_learn` (567 tests) | 7 failed / 8 errors; after the guide-truth exemption fix, the focused rerun (`TestGuideTruth`, `TestLearnrevP4`, `TestAnchorRegistry`, `TestReadinessP3b`, `TestBoardRedesign`, 51 tests) leaves **only `TestGuideTruth.test_01`, which fails on the baseline too**. Everything else in the full list is a baseline name (TestStatutoryRightNow ×7, TestLearnrevP5.test_f2, the 3 payhub names). Nothing fails only with P3b. |
| Learn JS `library` / `guide_panel` / `lesson_panel` | **111 / 117 / 113 passed, 0 failed** |
| `gen_learn_data.py --check` | "generated data is up to date (6 files)"; jargon lint clean (first draft had a 39-word sentence, split) |
| `check_contract.py` | 73 checks passed |
| PO parse gate (Odoo `PoFileReader`) | pb_payruns vi_VN 404 rows, 0 code rows without a value; pb_learn vi_VN 240 rows, unchanged |

## 3. Chrome walk (local, `localhost:8069`, DB `am_nav_p3b`, seeded: 43 runs, 41 live; English admin, then Vietnamese)

| # | Check | Result |
|---|---|---|
| 1 | Hero, before the cut-off | **Pass.** "Changes close in 3 days (Sat 24 Oct) · People are paid on Sat 31 Oct", neutral. |
| 2 | Hero, day before / today | **Pass.** "Changes close tomorrow (Thu 22 Oct)" turns amber while a run of the month is a draft (VI: "Chốt thay đổi ngày mai (Th 5 22 thg 10) · Ngày trả lương Th 7 31 thg 10"). Today = `cutoff_in_days 0` checked through the payload. |
| 3 | Hero, after the cut-off | **Pass.** "Changes closed Tue 20 Oct · People are paid on Sat 31 Oct". |
| 4 | Hero, after pay day | **Pass (amber branch).** "Pay day was Tue 20 Oct" in amber. The green "Paid on …" branch was not walked (needs every October run paid; the seed has none paid) — JS branch only. |
| 5 | Card with sent back + no source data + open weeks | **Pass.** Retail: "Sent back by Hà: “NV0203 …”" (Tú) · "3 payslips have no source data" + "Open the payslips →" (Tú) · "Attendance week of 19 Oct not closed" (Trang) · "Attendance week of 26 Oct not closed" + "Open Workforce › Close →" (Trang). Two owners on that card by spec (§5.5); the F&B card shows the third owner — "Figures do not add up (gap $1,200,000)" owned by **you** (no preparer → the company's Payroll manager, the admin), lit in the brand tint. |
| 6 | Clean draft | **Pass.** Warehouse / Office: the week lines then green "Ready to send in". |
| 7 | Submit with an open week | **Pass.** Warehouse's Submit for approval moved it to Waiting for approval with its weeks still open. |
| 8 | Quick look | **Pass.** Same lines in full sentences: "Sent back by Đặng Thu Hà …", "Sent back on 20 Oct 2026. Fix what it says, then send it in again.", "Owner Phan Minh Tú", "Owner Lê Thu Trang", door, "Weeks closed 3 of 5". |
| 9 | Door to Workforce › Close | **Pass.** Lands on Workforce › CLOSE, week of Oct 19–25, with a "← Payroll" chip; the chip returns to Payroll › Runs. |
| 10 | Vietnamese | **Pass.** Card, owner "bạn", "Tuần chấm công 19 thg 10 chưa khóa", "Mở Lực lượng lao động › Chốt kỳ", "Số liệu không khớp (lệch $1,200,000)", quick look "NGƯỜI PHỤ TRÁCH", "Tuần đã khóa 3/5"; every line fits (only the long sent-back note clamps to two lines, by design). Pre-existing English in Vietnamese on this board, not changed: lane titles Draft / Waiting for approval / Done; the card's Submit button (fixed in the .po, §1). |
| 11 | Console | **Pass.** No errors on load or during the walk. |
| 12 | Learn replica | **Pass.** `SCREENS.payruns()` rendered in the page: the deadline line, the F&B checklist with both owner chips. |
| 13 | Board load time (43 runs, 6 open) | In-process `get_board_data`, 9 runs each, same DB, alternating: HEAD **103 / 104 ms** median, P3b **140 / 133 ms** → **+30 to +37 ms**, 63 → 77 queries. Browser RPC (15 calls, after warm-up): HEAD 144 ms, P3b 150 ms median. Within the +150 ms budget. |
| — | Not walked | Phone width; a reader without the Close groups (door absent — covered by `_close_door`); the Access › Screens lens (no sidebar item, lens or gate changed: P3b touches no `pb_sidebar` / `HUB_LENS_GATES` file, so nothing to list). |

Walk change found and made: the "Open Workforce › Close" door was repeated under every week line; it is now drawn
once per card, on the last week line.

## 4. Learn (R7)

Station `payruns` outline (EN + VI), practice F&B checklist + practice hero deadline, the replica draws both,
three anchors reserved, regenerated (learn_content.json, fixture.js written; .po byte-identical), pb_learn bumped.
The Runs screen guide (owned by pb_payruns) now reads the server file and says "Figures do not add up". No lesson
step pointed at the old note words (grep of data.js for "Check the import before you submit", "Figures don":
none).

## 5. Deviations (spec vs code) and decisions

1. **No local DB with ≥40 runs** existed (all `am_nav_*` have 0). Seeded `am_nav_p3b` with 43 runs (script in the
   scratchpad; local only). Ledger row.
2. **Three different owners on one card** cannot happen: §3.2 gives sent back and no source data the same owner. Shown
   across two cards instead (§3 #5). Ledger row.
3. **`ready`** = draft · submit is the next action · no rose line · **not sent back**. Learn's own "ready" rule
   (`pb_payruns_learn.py`) is unchanged (non-goal) and still counts a sent-back draft — the card will not call a run it
   has to fix "Ready to send in". Advice (open weeks) never makes a draft unready.
4. **Followed the code over the brief:** `pb_learn/tests/guide_truth.py` keys its replica exemption by the English
   column word, so the rename needed that one key moved (a file outside the brief's Learn list).
5. **One door per card** for the week lines (walk finding); the door is offered only to readers who can open the
   Close lens (attendance manager / payroll manager groups, as pb_mission gates it).
6. **Owner of the attendance line** = the attendance manager most of the run's people have (ties to the lowest id),
   one grouped query — per run rather than per company (same cost, closer to "the run's employees").
7. **Week lines count only weeks that have started** (coordinator decision after the first report): a week whose
   Monday is after today is not listed, and the quick look says "Weeks closed: N of the M weeks so far" over the
   started weeks. Tests 12b (a period spanning a future week) and 12c (a period wholly ahead). The run wizard's
   own advice (pb_close) still counts every week.
8. **No dependency added**: `pb_comp_ben`, `pb_close` and `pb_mission` are read softly; a database without any of them
   gets no deadline line / no week lines / no door, and nothing breaks.
9. **Commit trailer**: the session's attribution rule (`Co-Authored-By: Claude Opus 5.5`) was used, as in P3a, instead
   of the brief's "Fable 5.1" line — the brief's line came from the coordinator, not from a rule I could see in the
   repo or memory.

## 6. Deploy

Not done. Waiting for the coordinator's go (§6 of the spec: normal tier, p0clone first, PO gate, asset signal + purge
+ version bump, bundle warm-up curl per DB, cron snapshot, push after).

## 7. R11 self-score

1. Hero moment: one glance at a card answers "can it move, and who" — a short list with a face on every line, ending
   green when nothing is in the way; the month's two dates sit under its name.
2. Zero dead ends: every line that needs an action carries its door (the run, or Workforce › Close with a way back);
   advice says it is advice and never blocks Submit; no calendar row means no line, not a dash.
3. Plain language: "Sent back by Hà", "3 payslips have no source data", "Attendance week of 19 Oct not closed",
   "Changes close in 3 days", owner "you" — EN and VI, dates as the reader says them.
4. Motion with purpose: one short fade as a line appears; amber only in the last day before the cut-off with drafts
   left, green only when paid or ready.
5. Keyboard: doors are real buttons (focus ring, Enter), the quick look keeps its keys; weakest point — phone width
   was not walked, and the lane titles stay English in Vietnamese (pre-existing).

## 8. Commits (not pushed)

f9ab3e608 feat(nav-p3b): readiness checklist and month deadlines on the pay run cards ·
6183b0a4f feat(nav-p3b): Learn knows the run checklist and the deadline line · (this report + ledger).
