# NAV P3a — Hiring: APPLICANTS and OFFERS registers — report

Implementer: Opus, 2026-10-21. Spec: `docs/handovers/NAV_P3A_HIRING_REGISTERS.md` §1–5. Ledger: seven new P3a rows in
`docs/handovers/NAV_LEDGER.md`. **Deployed 2026-10-20 23:41–23:52 UTC on all four databases, normal tier — see §8.** (Two modules, no migration,
no data change.)

## 0. Exact deploy lists

```
-u pb_hiring,pb_learn
```
Rsync (scoped `--delete` per module): `pb_hiring`, `pb_learn`. No `-i`. No migration scripts. Versions:
pb_hiring 19.0.2.9.0 → **19.0.2.10.0**, pb_learn 19.0.20.5.12 → **19.0.20.5.13**. PO gate files:
`pb_hiring/i18n/vi_VN.po` (changed), `pb_learn/i18n/vi_VN.po` (unchanged). Served-JS check: `startTab: "applicants"`.

## 1. What changed, per file

| File | What |
|---|---|
| `pb_hiring/models/registers_p9.py` (new) | `get_applicants(filters, cursor)` — roles as the reader (record rules) or the cover clause, one role per job, applicants read as the system, filters role / recruiter / family (play · offer · joined · closed) / words on the server and figure filters (waiting_mine · late · iv_week · duplicate) after the cards are built, cap 600 with `total` / `capped`, columns in journey order with count and typical days, `roles` (with each role's stage keys and `can_move`), `recruiters`, `glance`. Cards are **`_candidates(req)`** — every phase's card fields and P4's mask — plus `role_id / role / recruiter / can_move`. `get_offers(filters)` — `_offer_row` (masked) plus `step`, `waiting_mine` (open seat on the offer's route), `docreq {in, wanted, deadline, state, overdue}`, `bgv {state, flags, pending}` (team only), `recruiter`, `can_recruit`, `joining_days / joining_soon / joined_month`, `case_id`, `employee_id`, translated `state_label`; five step counts; flag counts. `_act_journey_stage` with `register: True` refuses a stage one of the people's roles does not use, before anybody moves. `_offer_kpis` adds `offers_waiting_mine`, `joining_soon`, `joined_month` from the same rows. |
| `pb_hiring/models/board_p1.py` | `_candidates(req)` honours context `pb_hiring_app_ids` (the register's slice of a role) — no copy of the card builder. |
| `pb_hiring/views/offer_views.xml` | Bug fix: list decoration, filter `f_joined`, two header buttons and the Day one page tested `state == 'closed'`; now `joined`. |
| `pb_hiring/static/src/js/hiring_registers_p9.js` (new) | Patch of `PbHiringBoard`: the two home tabs, their loading, filters persisted in `pbhr.applicants.v1` / `pbhr.offers.v1`, board / list (sortable), selection only on cards whose role the reader moves, the move menu listing only stages every chosen person's role uses (with a sentence when roles differ), the offer row menu, the Joiners hand-over (`openHub` → People › Joiners, back chip to Hiring › Offers). While a register shows, `reloadRole`, `refresh`, `p6Refresh`, `cards`, `canMove`, `stageByKey`, `flatOrder`, `closedCards`, `nextKeyFor`, `moveTargets`, `offer`, `onKey` answer from the register, so the drawer and every joining dialog work unchanged. |
| `pb_hiring/static/src/js/hiring_board.js` | Overview strip: Offers waiting on you · Joining soon · Joined this month open Offers pre-filtered; Offers out, Candidates, Referrals this month removed (10 figures). `kcMove(cd)` (the card asks per card). |
| `pb_hiring/static/src/js/hiring_hub.js` | Lenses applicants (`columns`, "Applicants", tooltip "Applications across jobs") and offers (`send`, "Offers", tooltip "Offers and joining checks") between Overview and Interviews; `HUB_LENS_GATES` updated. |
| `pb_hiring/static/src/js/hiring_palette.js` | ⌘K rows Applicants (keywords applications, candidates, pipeline, ứng viên) and Offers (offer letters, joining, lời mời, nhận việc), seq 3501/3502. |
| `pb_hiring/static/src/xml/hiring_p9.xml` (new) | The two templates. Anchors `hi-applicants`, `hi-applicants-board`, `hi-offers`, `hi-offers-steps`, `hi-offer-row`. |
| `pb_hiring/static/src/xml/hiring_board.xml` | Inner tabs Applicants / Offers; the role strip and four steps hide on the two register tabs (each has its own hero). |
| `pb_hiring/static/src/xml/hiring_board_p1.xml` | Card: per-card move, role line on Applicants. Move menu: mixed-roles sentence. **Bug fix:** the drawer's Advance / Not this time called `candCard()` unbound and threw on every role page (live since RECRUIT P1). |
| `pb_hiring/static/src/scss/hiring_p9.scss` (new) | Hero, view switch, role line, tables, pills, fixed-position row menu, phone rules; tokens only, dark via P1's palette. |
| `pb_hiring/i18n/vi_VN.po` | 90 new entries (`#. module:` / `#. odoo-javascript` or `#. odoo-python` / `#: code:…:0`), 8 existing python entries gained the JS flag. Offers in Vietnamese is the module's existing **"Lời mời"** throughout (shared entry untouched; see §5). |
| `pb_hiring/tests/test_registers_p9.py` (new) | Tests 1–7 of the spec plus the rail-order check. |
| `pb_learn` + `docs/tutorial_poc` | See §4. |

## 2. Tests

Local runtime `/Users/adity/odoo19`, DB `am_nav_p3a_t` = copy of `am_nav_p2_en` (P2 HEAD install, English admin). The final runs used a clean `git archive` of HEAD with only pb_hiring and pb_learn from this phase over it (another session's uncommitted changes in the shared tree break any local server — ledger row).

| Run | Result |
|---|---|
| `test_registers_p9` (8 tests: spec 1–7 + rail order) | **8 passed, 0 failed** |
| Full `/pb_hiring` (497 tests, includes test_hiring, test_offer, test_privacy_p4, test_joining_p6) | 28 failed — **the identical 28 test names that fail in the P2 baseline log on the same base** (`comm` of the two sorted lists: nothing only in P3a, nothing only in P2). They are the local mail/portal/agency/Calendly ones P2 recorded. |
| Final run on the committed code, `-u pb_hiring,pb_learn --test-tags /pb_hiring,/pb_learn` (pb_hiring 497 + pb_learn 487 tests) | 29 failed, 9 errors — **exactly** the 28 pb_hiring baseline names above plus the 10 pb_learn names that fail on a copy of the same base running the code **before** P3a (`am_nav_p3a_base`, run alongside: 2 failed, 8 errors — TestGuideTruth.test_01, TestLearnrevP5.test_f2, TestStatutoryRightNow ×7, TestRecordsRightNow setUpClass). Nothing fails only with P3a. The anchor registry tests (`test_anchor_registry`, incl. 05/08) pass. |
| Learn JS `library` / `guide_panel` / `lesson_panel` | **111 / 117 / 113 passed, 0 failed** |
| `gen_learn_data.py --check` | exit 0, "generated data is up to date (6 files)" |
| `check_contract.py` | 73 checks passed |
| PO parse gate (Odoo `PoFileReader`) | pb_hiring vi_VN.po 3,221 rows, 0 code rows without a value; every new row names a P3a file |

Test 5's "real route" branch (the person holding the open seat sees `waiting_mine`) ran only if this database's offer
route opened a seat for a hiring user; the wiring is also proven by patching `_chain_my_seat` both ways.

## 3. Chrome walk (local, `localhost:8069`, DB `am_nav_p3a`, DEMO hiring world: 3 roles, 16 people, 6 offers)

| # | Check | Result |
|---|---|---|
| 1 | Rail order | **Pass.** OVERVIEW · APPLICANTS · OFFERS · INTERVIEWS · TALENT POOL; tooltips carry the full names. |
| 2 | Applicants board | **Pass.** "13 people in play · 3 roles · 2 waiting on you · 0 opinions late"; one column per stage across the three roles, role line on every card, empty columns folded, Closed rail. |
| 3 | Drawer from a card | **Pass.** Opens; **Advance** moved the person to the next stage of their own role, toast with Undo, board refreshed, drawer stayed open on them. (Before the fix in §1 this button threw — on the role page too.) |
| 4 | Bulk Move to across roles | **Pass.** Two people on two roles: the menu listed only shared stages (Assignment absent — one role does not use it) with the sentence; Recruiter review moved both, the board refreshed. |
| 5 | Filters persist | **Pass.** Role filter + List view survived a reload; the rail reopened on APPLICANTS; list sorts by column. |
| 6 | Offers strip and rows | **Pass.** 01 In approval 1 · 02 With the candidate 1 · 03 Accepted and signing 2 ("2 joining in 30 days") · 04 Joined 1 · 05 Did not happen 1; papers "0 of 6 in · past the date", check "All clear" / "1 flag", joining "In 9 days" etc., money column for the hiring team. |
| 7 | Row ⋯ menu | **Pass.** Signed row: Open the candidate, Open the offer, Remind about documents, Change the joining date, Confirm they joined, Did not join. Accepted row: only Open ×2 + Record the signed copy. Remind → "Reminder sent."; Change the date → drawer + date dialog → row shows the new date; Record the signed copy (with a file) → row became Signed, toast as the role panel's. |
| 8 | Joining soon / tiles | **Pass.** Overview "Joining soon 2" → Offers with "Joining in 30 days" on, soonest first; "Joined this month" → the joined row. |
| 9 | Handed to People › Joiners | **Pass.** Lands on People › JOINERS with a "Hiring" back chip; the chip returns to Hiring › OFFERS. (The Joiners board does not read `pb_focus` yet, so the person is not highlighted.) |
| 10 | Empty states | **Pass.** "No offer matches these filters" / "Nobody matches these filters", each with Clear. |
| 11 | ⌘K | **Pass.** "pipeline" → Applicants; "đề nghị" → Offers (walked before the keyword became "lời mời", see §9). |
| 12 | Vietnamese | **Pass.** Rail TỔNG QUAN · ỨNG VIÊN · ĐỀ NGHỊ · PHỎNG VẤN · KHO ỨNG VIÊN at walk time (now LỜI MỜI, §9), every label measured as fitting its box; tooltips "Hồ sơ ứng tuyển theo mọi vị trí", "Đề nghị và kiểm tra trước ngày vào" (now "Lời mời và kiểm tra trước ngày vào"); strip and both registers in Vietnamese (state pills, papers, check). Two words fixed during the walk: the check said "Xoá" (Clear) → "All clear" / "Không có vấn đề"; the state pills were English → translated. |
| 13 | Console | **Pass** on the final code (two errors met and fixed during the walk: `String()` in a template, the unbound `candCard()`). |
| — | Not walked | A non-team reader in the browser (covered by tests 2 and 5); phone width; the Access › Screens lens (no sidebar change; check after deploy as the spec says). Screenshots: Applicants board, Offers register (paths in the hand-back message). |

## 4. Learn (R7)

- `data.js` `hub_hiring.tabs`: applicants "Applicants / Ứng viên" and offers "Offers / Đề nghị" between overview and
  interviews, one line each EN + VI (Offers = "Lời mời"). Station `hiring` outline `what` gains one sentence per tab (EN + VI).
- `practice-data.js`: MENU Hiring lenses add applicants and offers (quiet tabs, no replica); the practice Overview
  strip follows the product (Candidates and Offers out out; Offers waiting on you 0, Joining soon 1, Joined this month 0).
- `anchors.json`: five product anchors, `reserved: true`, file `pb_hiring/static/src/xml/hiring_p9.xml`;
  `hi-offer-row` `repeats: true`; `hi-tabs` description updated.
- Regenerated: 2 files written (learn_content.json, fixture.js), 4 unchanged; **`pb_learn/i18n/vi_VN.po` byte-identical
  before/after** (`cmp`). pb_learn 19.0.20.5.13.
- No lesson pointed at "Offers out", "Candidates" or "Referrals this month" (grep of data.js: none; practice-data.js: the
  strip only).

## 5. Deviations (spec vs code) and decisions

1. **"Waiting on you" on Applicants** keeps the role board's existing meaning: a first look or an interview outcome
   owed on that person. **Decided 2026-10-21** (coordinator); the spec's sentence now says the same. The request
   sign-off stays on the Overview figure.
2. **Offer steps:** five steps, every offer at exactly one (quiet-board rule). Drafts sit in **In approval** ("Being
   prepared or signed off"). **Joining soon** is a flag on step 03, a chip and an Overview figure, not a sixth step —
   it is a subset of Accepted and signing.
3. **Offers filter on the client** over the newest 200 the server returns (instant chips); `get_offers` also accepts
   every filter (used by the tests). Steps and counts are over all 200.
4. **Overview strip:** to stay at ten figures, Candidates and Referrals this month (count-only, no door) left as well as
   Offers out.
5. **Vietnamese "Offers" = "Lời mời"** — the module's existing word, **decided 2026-10-21** (coordinator): rail LỜI MỜI,
   full name "Lời mời và kiểm tra trước ngày vào", every P3a string that names an offer says "lời mời". The shared
   `Offers` entry is untouched, so Hiring numbers (Insights) is unchanged. The first build had used "Đề nghị".
6. Spec named the list decoration and `f_joined`; the same `closed` test also hid two header buttons and the **Day
   one** page on the offer form — fixed with them.
7. **Live bug fixed:** the candidate drawer's Advance / Not this time (unbound `candCard()`), on every role page.
8. Offer state words are translated on the register only; the role's Offer panel still shows the English list label to
   a Vietnamese reader (ledger row, follow-up).
9. Typical days per column = the people in that column now (a role's stage-log figure does not add across roles).
10. Commit trailer: the session's attribution rule (`Co-Authored-By: Claude Opus 5.5`) was used instead of the brief's
    "Fable 5.1" line.

## 6. Gotchas appended to the ledger (7)

OWL templates see no JS globals (`String`); bare method calls in handler arrows lose `this` (the live drawer bug);
shared Vietnamese words (`Offers`, `Clear`); untranslated offer state words and the `_(row['x'])` extractor trap; bare
dates through `dayShort` show a day early west of UTC; local walks must run from `git archive HEAD` + own modules
because other sessions' uncommitted model changes break any server on the shared tree (and `--dev=assets` +
`?debug=assets` for fresh bundles); rail vs inner tabs can disagree (P2 design, follow-up).

## 7. R11 self-score

1. Hero moments: Applicants opens on one sentence of four live filters over one pipeline of every role; Offers reads
   left to right as the life of an offer, with what is waiting on you lit.
2. Zero dead ends: every empty state says why and carries a door; joined rows hand over to People › Joiners and back;
   a mixed move says in one sentence why a stage is missing instead of failing.
3. Plain language: "In 9 days", "0 of 6 in · past the date", "All clear", "Did not happen" — the words on a recruiter's
   desk, EN and VI.
4. Motion with purpose: only the existing card landing / toast and a short fade on the row menu; nothing decorative.
5. Keyboard: Esc closes menu / drawer / selection, arrows step through people in the drawer, Enter opens a list row;
   weakest point — the inner tab bar and the rail can disagree (ledger), and the offer table scrolls sideways below
   ~1,500 px.

## 8. Deploy record (normal tier, 2026-10-20 23:41–23:52 UTC, Payobook19v2)

Coordinator's go after the service-stop announcement. Service down **4 min 14 s** (stop 23:42:32, port 8069 back
23:46:49). `abm` not touched (no such database on the box).

| Step | Result |
|---|---|
| Staging | From the **commit** only: `git archive HEAD pb_hiring pb_learn` at `3f4ff7be4` into the scratchpad, 307 files byte-identical to HEAD (git blob hash per file); uploaded to a clean `/tmp/deployP3A`. |
| Overwrite check | `rsync --dry-run --checksum` against live: content changes are exactly this phase's files (pb_hiring: manifest, vi_VN.po, models/__init__, board_p1, registers_p9 new, hiring_board/hub/palette/registers_p9 JS, hiring_p9.scss new, hiring_board/_p1/p9 XML, offer_views, tests; pb_learn: manifest, learn_content.json, anchors.json, fixture.js); every other file timestamp-only; no deletions. |
| Crons before | payobook 37, payobook_template 0, p0clone 26, rize 69. |
| Stop | `service odoo-server stop`; zero `odoo-bin -c` processes. |
| Copy + hashes | Per-module scoped `rsync -a --delete`; tree hash live = staged: pb_hiring `491f3338…`, pb_learn `5db6e468…`. Owner as the other modules (ubuntu). |
| PO gate (on the box, Odoo `PoFileReader`) | 3 files (pb_hiring vi_VN 3,221 rows, id_ID 101; pb_learn vi_VN 240), **0 failures**. |
| p0clone | `-u pb_hiring,pb_learn`, detached (`systemd-run`) with sentinel: **EXIT=0**, registry 38 s, 0 Traceback/CRITICAL, 0 ERROR. |
| payobook | EXIT=0, 43 s, 0 / 0. |
| payobook_template | EXIT=0, 34 s, 0 / 0. |
| rize | EXIT=0, 36 s, 0 / 0. |
| Assets | Per DB `INSERT INTO orm_signaling_assets DEFAULT VALUES`, `/web/assets/%` attachments deleted, `web.assets.version` = 1792540005528. |
| Start | Active, port 8069, `/web/health` 200, "Registry loaded" ×4, **0 ERROR/CRITICAL since start**. |
| Warm-up | One at a time: login page on payobook.com, rize.payobook.com, p0clone.payobook.com (all 200), then the backend bundles once each: `web.assets_web.min.css` 3.76 MB / 3.67 MB / 3.67 MB, `.min.js` 13.7 / 13.4 / 13.4 MB — none empty. payobook_template has no hostname (a tenant template), so its bundles generate on first use. |
| Crons after | The upgrade switched on 18 jobs in payobook_template (43, 44, 51, 54–58, 60, 62, 63, 67, 68, 71–75), as in P2; switched off again. **Final: payobook 37, rize 69, p0clone 26, payobook_template 0** — as expected. No new active job elsewhere. |

| Check | p0clone | payobook | payobook_template | rize |
|---|---|---|---|---|
| pb_hiring latest_version | 19.0.2.10.0 | 19.0.2.10.0 | 19.0.2.10.0 | 19.0.2.10.0 |
| pb_learn latest_version | 19.0.20.5.13 | 19.0.20.5.13 | 19.0.20.5.13 | 19.0.20.5.13 |
| Served JS has `startTab: "applicants"` | 1 | 1 | no hostname (files identical, version current) | 1 |
| Live `learn_content.json` "gõ DUYỆT" | 1 | 1 | (same file) | 1 |

**Push:** `origin/19.1` `fb059bfeb..3f4ff7be4` — this phase's five commits plus the docs commit `4beabbdfa` that sat under
them. Not pushed: `7a2deccb4` ("policy-backed application payroll", another session), which landed on local 19.1 after
my last commit; pushing it is that session's call. This report commit therefore sits on top of it locally and is
pushed only if that session (or the coordinator) pushes 19.1.

Still open: the payobook.com browser walk (coordinator), and the Access › Screens look (no sidebar change expected).

## 9. After review (2026-10-21)

Coordinator decisions applied in one follow-up commit: Offers = "Lời mời" everywhere (16 P3a msgstrs, ⌘K keyword,
Learn hub tab, station sentence, practice menu and strip; the shared `Offers` entry restored byte-for-byte), and the
spec's "waiting on you" sentence aligned with the board. Learn regenerated (`--check` 0, contract 73 ✓, JS
111/117/113, pb_learn vi_VN.po unchanged); pb_hiring vi_VN.po parses (3,221 rows). Not re-walked in the browser:
the change is translation text only, checked through the parser (`Offers` → Lời mời, `Offers and joining checks` →
Lời mời và kiểm tra trước ngày vào). "LỜI MỜI" is shorter than "KHO ỨNG VIÊN", which fits.

## 10. Commits

ab404c958 fix(hiring): offer views test the joined state · 37975c295 feat(nav-p3a): Applicants and Offers registers ·
b4481dfb2 feat(nav-p3a): Learn knows Applicants and Offers · 8b336f661 docs(nav-p3a): report, spec, ledger ·
3f4ff7be4 fix(nav-p3a): Offers stays "Lời mời"; waiting on you as on the board · (this deploy record).
