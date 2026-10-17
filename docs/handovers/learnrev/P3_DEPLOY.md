# LEARNREV P3 — deploy record

Deployer: Opus, 2026-10-17. Tier: **normal** (JS/SCSS + Python, no stored field, no data, no `.po`). Scope: P3 (the
Library Learning page, one search, ⌘K field rows, the docked Guide's header and fold, the Runs board under a docked
Guide, S10 Explain fix), merged on 19.1 at `da2de379f`. Status: **live on payobook, rize, payobook_template, abm**;
files and versions verified; browser walk L1–L9 on payobook.com: **9 pass**. Not pushed.

## Commits (branch 19.1)
| Commit | What |
|---|---|
| `ff562dded` | Ship: patch bumps of the 3 modules changed in `b8a4da724..da2de379f` (below). |
| this doc | P3_DEPLOY.md, ledger LR53–LR56. |

## Modules (from the diff, LR33)
`git diff --name-only b8a4da724..HEAD` outside `docs/`: pb_learn (22 files), pb_hub (1), pb_payruns (1) — nothing else.
`.po` files in the range: 0, so no Vietnamese overwrite load (LR20/LR29 not triggered). PA60 dry run (`rsync -rcn` of
`git archive HEAD` against the server): exactly **26** files differ (22 + 2 + 2, incl. the bumped manifests), before the
clone and again right before the stop; pb_payai_actions (tested, not deployed) byte-identical to HEAD on the server.

| Module | Before (all 4 DBs) | After (all 4 DBs) |
|---|---|---|
| pb_learn | 19.0.20.5.7 | 19.0.20.5.8 |
| pb_hub | 19.0.1.11.2 | 19.0.1.11.3 |
| pb_payruns | 19.0.3.0.2 | 19.0.3.0.3 |

## Clone test (HEAD `ff562dded`)
Clone `lrp3dclone` = `pg_dump --exclude-table-data=hr_payslip_line payobook | psql` (323 MB, restore 09:11:07 →
09:12:32 UTC; LR16/LR26). Prep (P3's `prep.sql`) before odoo-bin: `payroll_ai_config` 0 active / 0 keys, every
`*api_key*` parameter blank (checked, abort otherwise; LR17), 88 jobs and the mail server off, `base.group_user` →
`group_payai_user` implied on the clone only (LR18); the clone inherits payobook's Guide ON and compose ON. Stage
`/tmp/p3dstage` = `git archive HEAD` of pb_learn, pb_hub, pb_payruns, pb_payai_actions + `pb_home_hub` linked
read-only + `_siblings/` (every other module's `.js`, no manifest — LR53). `--addons-path=/tmp/p3dstage,
/odoo/odoo-server/addons`, ports 8095/8094, `-u pb_learn,pb_hub,pb_payruns,pb_payai_actions`, tags `/pb_learn`, `/pb_hub`,
`/pb_payruns`, `/pb_payai_actions:TestOneChatClient`.

**483 tests, 1 failed, 0 errors** (09:12–09:16 UTC). Per module: pb_learn 412, pb_payruns 114, pb_hub 34,
pb_payai_actions 5. The one failure is the known baseline `TestQuestionMining.test_07b` (the clone switches jobs off).
`TestLearnrevP3` 9/9, `TestGuideClient` 1/1, `TestCoach` 28/28 (incl. test_11, AI off), `TestOneChatClient` green.
**pb_hub `test_every_palette_entry_points_at_a_registered_action` passed** — the LR50 staging artefact is gone with
`_siblings/`. No model call. Clone dropped with `dropdb --force`; no filestore folder; stage removed.

## Deploy
Before the stop: no `odoo-bi[n] … stop-after-init`, no `odoo-bin shell`, no rollout or deploy unit, lock free (checked
09:09 and 09:17). `ListAgents` / `SendMessage` are not available to this agent, so coordination was the server check
alone. Ran as unit `lrp3-deploy` under `flock -n /tmp/payobook-studio-deploy.lock`; stage = clean `/tmp/deployP3` from
`git archive HEAD` (3 modules only); per-module `rsync -a --delete` into `/odoo/odoo-server/addons/<m>/`;
`~/pb_upgrade.sh` per DB, payobook first.

| Step | UTC |
|---|---|
| Lock taken | 09:17:53 |
| Service stopped | 09:18:10 |
| Files copied | 09:18:11 |
| payobook / rize / payobook_template / abm `-u` started | 09:18:11 / 09:19:08 / 09:19:52 / 09:20:37 |
| Service started (port 8069 bound) | 09:21:21 (registry loaded 09:21:24) |

**Downtime ~3 min 11 s** (09:18:10 → 09:21:21). Every `-u` EXIT=0; 0 ERROR/CRITICAL in the four upgrade logs and in
the service log from the stop to the post-start check (09:18 → ~09:23, 6,374 lines). Lock released.

- **Files:** all 3 module trees hash-identical stage ↔ server (sha1 of every file, `__pycache__`/`.pyc`/`.DS_Store`
  skipped).
- **Versions:** `latest_version` = the new manifest version for all 3 modules in all 4 DBs (table above).
- **Assets:** purge + `web.assets.version` bump + `orm_signaling_assets` row per DB; the live page serves
  `@pb_learn/journey/library` (checked in the browser).
- **Scheduled jobs:** payobook 37 → 37, rize 69 → 69 (no job newly on). The upgrade switched **abm** 20 jobs and
  **payobook_template** 23 jobs back on — switched off in the same script; both **0**.
- `payai.voice_enabled` on payobook: True before, True after (untouched). payobook.com and rize.payobook.com: HTTP 200
  (`/web/login` and `/`).

## Guide switch read-back (owner decision 2026-10-17 — not changed)
| DB | `pb_learn.guide_enabled` before | after |
|---|---|---|
| payobook | True | **True** |
| rize | True | **True** |
| payobook_template | True | **True** |
| abm | unset | **unset** |

## Browser walk (LIVE payobook.com, QA Test, own headless Chrome on 9560, sign-in by `fetch('/web/session/authenticate')`)
Viewport 1440 × 900 applied per CDP session (LR48). Error + rejection + console.error collector installed after each
load; empty at every step. Screenshots:
`/private/tmp/claude-502/-Users-adity-Documents-GitHub-gitlocal/d3a7939f-6b40-427b-9e7d-c5a89b5a6ab8/scratchpad/p3/walk/`.

| # | Result | Evidence |
|---|---|---|
| L1 Learning page 1440 × 900 | **pass** — Continue card ("Continue · your path as Approver · 0 of 7 done · Change", Pulse, "Required for you as Approver. 9 steps…", Continue); path strip 7 stations + Change role; 8 groups in menu order Home · Pay Run · People · Lifecycle · Workforce · Insights · Compliance · Settings; 42 rows at 52 px; none of "Not on your path", badge, streak, Overall, Your journey, Show me how, Practice missions; no overall ring; no sideways scroll. **Page height (`.lrn-root` = `.pbhub-lens` scrollHeight) 2,012 px live** (clone 2,048 px; old page 8,092 px). | `p3d_l1_library.png`, `p3d_l1_library_full.png` |
| L2 Guide on Component treatment | **pass** — board opens (54 rows, "Payobook Retail — End-Month Payroll"), Guide docked, header "Guide · Component treatment", This screen open with You are here (Before this Formula Engine › Mapping › Component treatment › Next Run / Runs), Right now 1 item. | `p3d_l2_guide.png` |
| L3 search "pay role" | **pass** — "9 found": field Pay role ×2, term, lesson, screen; the first field row opens the treatment board with Fields on this screen open and the Pay role card at the top of the panel (in view). | `p3d_l3_search.png`, `p3d_l3_field.png` |
| L4 Explain this screen (payobook: compose ON, AI connections active) | **pass (S10 fixed live)** — the new answer is the Guide-shaped one: "About this screen · Explain this screen", the purpose sentence, "1. You are here: Mapping › Component treatment 2. Next: Pay Run › Run", column lines (Comes from, Report group, Pay role), "Grounded in: Component treatment", Watch / Practise this / Open the Guide / Open the lesson. `explain_screen('treatment')` returns `guide_door: true`, `source_kind: screen`, blocks p · steps · p · p · p · source — no model rewrite. (Older "Composed from the guide" replies from before the fix are still in QA Test's chat history above it — LR55.) | `p3d_l4_explain_top.png`, `p3d_l4_explain.png` |
| L5 Vietnamese | **pass** — QA Test switched to vi_VN by RPC: page Vietnamese end to end (Học tiếp, "Lộ trình Người phê duyệt · Đã xong 0/7 · Đổi", reason, groups Trang chủ … Cài đặt, chips Hướng dẫn / Xem / Thử, search box); 0 English words from the check list. "vai trò" → "Tìm thấy 12", field Vai trò trong lương first. Switched back to **en_US** (read back from the database: en_US). | `p3d_l5_vi.png`, `p3d_l5_vi_search.png` |
| L6 ⌘K "pay role" | **pass** — rows "Pay role · Field on Component treatment · What the net pay formula does…" and Mapping's "Pay role · Field on Mapping" (listed first — P3 open item 4), plus the lesson; PayAI's door list holds **0** field rows. (Run from the Learning page: the Mapping surfaces keep their own ⌘K — LR54.) | `p3d_l6_cmdk.png` |
| L7 P0 lesson door | **pass** — ⌘K `learn.station.treatment` → outline "Component treatment"; the treatment Guide's Understand › Open the lesson → outline "Component treatment". | `p3d_l7_lesson.png` |
| L8 Runs board docked | **pass** — Guide docked ("Guide · Runs"); month summary in two columns 415.5 + 415.5 px (card 148–981 px); "5 are still drafts", "1 is approved and ready to pay", "Submit 5 drafts for approval" all inside the card. | `p3d_l8_runs_docked.png` |
| L9 console | **clean** — collector empty at every step; CDP console on fresh loads of Learning, Mapping › Component treatment and Pay Run Hub: only the startup log lines and the pre-existing brand-icon manifest size warning. | — |

## Not done / open (for Fable)
1. **Explain via the Ask chip does not fold the Guide** (seen in L4): after pressing "Explain this screen" the sections
   stay open and the answer is read in the short Ask area under them. The S8 b fold hooks `guideArgs()`, which only a
   routed (typed) sentence calls (LR46); the chip's `explain_screen` path never reaches it. Not a walk item; a P4 call.
2. **Runs board, two draft counts side by side** (L8 screenshot): the month summary says "5 are still drafts" (October)
   while the Guide's Right now says "17 draft pay runs can be checked…" (every month). Both true; reads as a
   contradiction. Right now could say "across all months" or follow the board's month filter.
3. **Vietnamese top-bar search placeholder** "Giao diện tìm kiếm, hành động..." (pb_hub, pre-existing) reads "search
   interface, actions" — a mistranslation of "Search surfaces, actions…". Fix in a .po pass.
4. P3 report open items 1–6 unchanged (page header "Payobook · Learning", Ask PayAI button over rows mid-scroll,
   Reduce motion admin-only, ⌘K Mapping row first, pay-role question intent gap, no per-role why).
5. Not pushed.
