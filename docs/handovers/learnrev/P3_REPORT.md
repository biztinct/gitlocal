# LEARNREV P3 — report (the Library: a calm Learning page)

Implementer: Opus, 2026-10-17. Worktree `.claude/worktrees/agent-ab61355d132eb02a0`, branch `learnrev-p3`, started at
`4be6f2af7` (the P3 handover, 19.1 tip at the time). **Not pushed, not deployed.** Handover: `P3_HANDOVER.md`, plus the
coordinator's S10 (Explain never rewritten when it is the Guide's).

## Scope
| Item | Result | Notes |
|---|---|---|
| S1 Map body replaced | **Done** | `journey/library.js` (pure renderer) + `library.scss`; journey.js `_mapBody` renders it. Lesson player, mission, Try, practice, missions list and outline untouched; `_applyDeepLink` keeps every arrival key. `LINE_ORDER` kept (test_nextbest pins it). |
| S2 Continue card | **Done** | Server next step when the page has it, else first required not done; "your path as <Role> · N of M done · Change" (role chips in place, `learn.path.set_role` as before); reason "Required for you as <Role>." plus "picked from your access…" when guessed (no `path.roles[].why` exists server-side, so the role name is the reason); steps not minutes; Continue starts / resumes the lesson. Month-end = one line + Watch. Nothing started → tour line. No role → "Pick what you do". All done → says so. |
| S3 Path strip | **Done** | Required stations in menu order, done / current / to do, dashed "Change role"; hidden with no path. Wraps (Owner has 10). |
| S4 Browse by screen | **Done** | `MENU_ORDER` mirrors the rail (8 groups); group = hub holding most of a screen's places, else the line (`LINE_GROUP`; the `sidebar_key` fallback is useless — LR44). Row: ring, title, one line, Guide + the Watch / Try its walkthroughs have, ≤ 1 status (Required / Not in your menu). Rows focusable, Enter = Guide. Two columns of groups ≥ 840 px; groups fold on a phone. |
| S5 One search | **Done** | Screens, fields (new `rpc_index`), terms, tasks, lessons; kind chips; accents folded, both languages matched; drawn in place (caret kept); Enter / arrows / Escape; empty → "Nothing matches “q”." + Ask PayAI (draft, not sent). ⌘K field rows ("Pay role · Field on Component treatment"), palette-only (`door: false`, LR45). Tie on a column that sits on two screens → its home screen (LR51). |
| S6 Removals | **Done** | Overall ring, badge, streak, tiers, Start here, Find it in, Show me how rows, tour card, Lifecycle road, header Reduce motion, Practice missions button. `skill_tree` / `streak` still served (test d). Settings: "Reduce motion" on this device; the streaks/badge switch no longer offered. |
| S7 Practice row | **Done** | End of Browse; "Practice on the demo company" (demo DB) / "Practice on a copy"; + "Guided practice" (the missions list). `_practiceCardHTML` remains the door. Team readiness row for `can_see_team`. |
| S8 a header | **Done** | "Guide · Component treatment" (full place as tooltip), up to two lines at the docked width, pill on one line. |
| S8 b fold | **Done** | First message of a drawer session folds the sections to titles + "Show the Guide" (re-expands, remembered per screen). Hook: `helper.guideArgs()` (LR46) — no PayAI change. |
| S8 c Runs board | **Done** | pb_payruns: under `body.lrn-docked` at 1280–1600 px the board takes its 1180 px layout. |
| S8 d LR30 gate | **Done** | `guide_truth`: a manifest column must be one text node (tags kept) — synthetic `<br/>` manifest fails, real 8 manifests pass. |
| S9 Lessons follow | **Done** | hub_learn tab line + next step, chrome rewordings (Learn / Search… / Guided practice / "on your path" / Open Learn), practice help answer; ~45 new chrome keys EN + VI; regenerated, `vi_VN.po` untouched (LR28 merge held). |
| S10 Explain (coordinator) | **Done** | `explain_screen` returns a Guide-shaped floor (`guide_door`) before the composer flag is read; screens without a manifest are still composed. Pinned order kept (`test_explain` 02/02a/02b). |

Deviations: commit split follows files, not hunks — the search's page half is in the Library commit (same file), the
`openHelper({guide})` seam is in the drawer commit (coach.js), the server index and S10 in commit 1. The tour line
says steps ("…: 8 steps"), not "8-minute" (G29: one unit). B8's `station:treatment` arrival was driven through the
⌘K station row (same arrival focus) rather than a typed URL.

## Tests
| Test | Result |
|---|---|
| T1 node `tests/js/library.test.mjs` (via `test_learnrev_p3::test_h`) | **103/103** locally (node 24) and on the clone (node 18) |
| T2 `test_learnrev_p3.py` (a)–(h) | **9/9** on the clone (a index EN+VI, a2, b no orphan, c MENU_ORDER = rail, d bootstrap contract, e retired words, f LR30, g S10, h node) |
| T3 truth gate | **0 errors**, 8 manifests (offline + `TestGuideTruth`); `TestAnchorRegistry` green |
| P2 node suite | **117/117** |
| PayAI node suites | client_fix 82, gaps_doors 10, oc2 167, oc3 266, rich 90 — all pass (= P2) |
| `gen_learn_data.py --check` | up to date |
| `check_contract.py` | only the known `grid-hint` |
| `replay_tests.py` | 238 pass / 3 fail — identical to the branch point (measured on `git archive 4be6f2af7`) |
| Full clone run (`/pb_learn`, `/pb_hub`, PayAI `TestOneChatClient`, `TestLaneLabels`, `TestStudioExperience`) | **400 tests, 2 failures**: `test_07b` (known baseline — jobs off on the clone) and pb_hub `test_every_palette_entry_points_at_a_registered_action` (staging artefact: walks the folders beside pb_hub; 0 missing on the full checkout — LR50). First run also caught `test_bundle::test_06` ("⌘K" as a chrome key), fixed (LR49). |
Also updated (they pinned retired things): `test_refresh_paths::test_06` (chapters → `LINE_GROUP`),
`test_practice::test_08` (map door = the Library's Practice row).

Clone: `pg_dump payobook --exclude-table-data=hr_payslip_line | psql lrp3clone` (LR16/LR26); AI config off and every
`*api_key*` blanked (LR17); jobs and mail servers off; base.group_user → PayAI User on the clone only (LR18); Guide
switch ON on the clone only; staged from `git archive HEAD` in `/tmp/p3stage` (only pb_learn, pb_hub, pb_payruns differ
from the server — the other 10 staged modules byte-identical, LR33); `--addons-path=/tmp/p3stage,/odoo/odoo-server/addons`,
ports 8095/8094. **Dropped with `dropdb --force`; no filestore left; staging removed.**

## Browser checks (clone on 127.0.0.1:8095 via ssh tunnel; own headless Chrome 9559; QA login by `fetch('/web/session/authenticate')`)
Screenshots: `/private/tmp/claude-502/-Users-adity-Documents-GitHub-gitlocal/d3a7939f-6b40-427b-9e7d-c5a89b5a6ab8/scratchpad/p3/walk/`.
| # | Result | Evidence |
|---|---|---|
| B1 1440 × 900 | **pass** — Continue + strip + 8 groups in menu order, 42 rows at 52 px, page **2,048 px** (≤ 2,600), no retired word, no sideways scroll | `p3_b1_library.png`, `p3_b1_library_full.png` |
| B2 Guide on Component treatment | **pass** — the board opens, Guide docked, This screen open, "Guide · Component treatment" | `p3_b2_guide.png` |
| B3 "pay role" | **pass** (after the walk fix) — field rows first; opens the treatment board with Fields open and the Pay role card at the top of the panel | `p3_b3_search.png`, `p3_b3_field.png` |
| B4 "xyzzy" | **pass** — "Nothing matches “xyzzy”." + Ask PayAI → chat opens with "xyzzy" in the box, not sent | `p3_b4_empty.png`, `p3_b4_ask.png` |
| B5 Change → Owner | **pass** — card "your path as Owner · 0 of 10", strip redrawn (10), chips close | `p3_b5_owner.png` |
| B6 Vietnamese | **pass** — whole page Vietnamese (groups, chips, reason, box); "vai trò" → field first | `p3_b6_vi.png`, `p3_b6_vi_search.png` |
| B7 ⌘K "pay role" | **pass** — "Pay role · Field on Component treatment" (and Mapping's); PayAI's door list holds 0 field rows | `p3_b7_cmdk.png` |
| B8 deep links | **pass** — `station:treatment` (⌘K row) → outline; P0's "Open the lesson" from the Guide → outline | `p3_b8_deeplink.png` |
| B9 400 px | **pass** — one column, groups folded (0 rows shown), tap opens a group, no sideways scroll | `p3_b9_phone.png`, `p3_b9_phone_open.png` |
| B10 Runs docked | **pass** — hero in two columns (415 + 415 px), every button inside the card | `p3_b10_runs_docked.png` |
| B11 header + fold | **pass** — header full; a sent message folds all 5 sections + "Show the Guide"; re-expands 4 open, remembered `{"treatment":1}` | `p3_b11_folded.png`, `p3_b11_shown.png` |
| B12 console | **clean** — error / rejection / console.error collector empty at every step | — |
Also: Learn › Settings "Reduce motion" device switch toggles `pbLearnPrefs.motion`; no streaks row (`p3_settings_motion.png`).

## Page height
**Before 8,092 px** (live payobook today, QA login, `.lrn-root`; 42 cards, "Not on your path" 37 times) → **after 2,048 px**
(clone, same user, 1440 × 900). Note: `.o_action_manager.scrollHeight` reads 767–854 px on both, because the Learn hub
scrolls inside `.pbhub-lens` (LR52) — the handover's B1 selector under-reports.

## Design bar (1–5)
| Bullet | Score | Why not 5 |
|---|---|---|
| Hero moment (Continue says what, why, how long; strip; menu-ordered rows) | 4 | the page header still reads "Payobook · Learning" (shared with the lesson views), not just "Learn"; 2,048 px is ~2.3 screens, not 1.5 |
| Zero dead ends (empty search → Ask; not in menu → outline + grey note; no role → pick; all done; Guide off → Explain) | 5 | — |
| Plain screen words EN + VI, never the brand word | 5 | — |
| Motion with purpose (one settle-in on a role pick; reduced motion; switch in Settings) | 4 | the Settings lens is administrators-only, so others rely on the system setting |
| Keyboard (rows focusable, Enter = Guide, search Enter / arrows / Escape) | 4 | no arrow-key movement between rows |
| Design system (palette tokens, Lucide via `ic()`, no emoji, no gradients) | 5 | — |
| vs Linear docs / Duolingo | 4 | the corner Ask PayAI button still floats over rows while scrolling (space is reserved only at the end) |

## Commits (branch `learnrev-p3`, not pushed)
`69840e891` index + drawer door + S10 · `cf7f0cae1` the Library (S1–S7, search page half, Settings) · `6f6a66409` ⌘K field
rows · `a489affde` drawer guide option + S8 a–d · `3a66027b1` content S9 + regeneration · `69ed7558e` tests ·
`c60d84ccf` fix "⌘K" out of chrome · `6f64c8147` walk fixes · (this report + ledger).

## Ledger rows added
LR44 menu order and the useless legacy `sidebar_key` · LR45 palette rows are PayAI doors unless `door: false` · LR46
`guideArgs()` = the send signal · LR47 restart the clone server after a re-stage · LR48 CDP viewport is per session ·
LR49 identical EN/VI chrome fails parity · LR50 pb_hub palette test needs a full checkout · LR51 a column on two
screens → home station's `search` · LR52 measure `.lrn-root`, not `.o_action_manager`. (Numbered from LR44 so the
coordinator's LR41–LR43 from `5def87ad5` merge cleanly; both append to the table's tail.)

## Deploy notes (for Fable; tier: normal — JS/SCSS + Python, no stored field, no data)
`-u pb_learn` (new asset files in the manifest, new `rpc_index` / S10 Python, regenerated content), `pb_hub` (palette
service JS), `pb_payruns` (SCSS) — asset purge + `web.assets.version` bump + `orm_signaling_assets` per DB, and restart
(LR47). No `.po` change. The coordinator's live S10 finding is fixed by this build on payobook (compose ON + Guide ON).

## Open items
1. Page header "Payobook · Learning" (journey.xml topbar, shared by every Journey view) — handover §3 says "Learn".
   Left as is: changing the brand/learn labels touches the lesson player's chrome (P4 scope).
2. The fixed Ask PayAI button overlaps rows mid-scroll on the Library (and every page); the Library reserves 88 px at the
   end only. A page-wide fix belongs to the drawer/launcher, not this page.
3. "Reduce motion" lives in Learn › Settings, which is administrators-only (as the handover asked); non-admins get the
   system setting only.
4. ⌘K lists Mapping's "Pay role" before treatment's (the palette's own order); the Library search ranks them right.
5. On the clone (AI off) "What does the pay role mean?" got the guide's honest "no answer" — an intent gap for P4/P5,
   not a Library issue.
6. `path.roles` carries no `why`, so the reason names the role, not the seat ("because you hold the Payroll approval
   seat"); adding a why per role is a `learn.path` change the handover ruled out (§4).
