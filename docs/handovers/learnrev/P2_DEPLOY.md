# LEARNREV P2 — deploy record

Deployer: Opus, 2026-10-17. Tier: **normal** (JS/SCSS + Python, one new selection value, no stored-data change).
Scope: P2 (Guide panel, field cards, Right now actions, Explain / whatnext from screen state), merged on 19.1 at
`253df7987`. Status: **live on payobook, rize, payobook_template, abm**; files and versions verified; Guide switched ON
on payobook only; browser walk L1–L8 on payobook.com: **7 pass, 1 fail (L3, see below)**. Not pushed.

## Commits (branch 19.1)
| Commit | What |
|---|---|
| `b8a4da724` | Ship: patch bumps of the 7 modules changed in `f61f2de32..253df7987` (below). |
| this doc | P2_DEPLOY.md, ledger LR41–LR43. |

## Modules (from the diff, LR33)
`git diff --name-only f61f2de32..HEAD` grouped by module: pb_learn (25 files), pb_formula_studio (9), pb_dashboard (2),
pb_hub, pb_payroll_ai_insights, pb_payruns, pb_payslip_review (1 each). **pb_payrun_wizard and pb_approval_config did not
change** — not bumped, not deployed. PA60 dry run (`rsync -rcn` of `git archive HEAD` against the server, before the
clone and again right before the stop): exactly the **46** files of the range (39 + 7 manifests) differ, nothing else;
pb_payai_actions (tested, not deployed) is byte-identical to HEAD on the server.

| Module | Before (all 4 DBs) | After (all 4 DBs) |
|---|---|---|
| pb_learn | 19.0.20.5.6 | 19.0.20.5.7 |
| pb_formula_studio | 19.0.1.201.33 | 19.0.1.201.34 |
| pb_payruns | 19.0.3.0.1 | 19.0.3.0.2 |
| pb_hub | 19.0.1.11.1 | 19.0.1.11.2 |
| pb_dashboard | 19.0.2.2.5 | 19.0.2.2.6 |
| pb_payslip_review | 19.0.1.3.1 | 19.0.1.3.2 |
| pb_payroll_ai_insights | 19.0.3.12.3 | 19.0.3.12.4 |

## Clone test (HEAD `b8a4da724`)
Clone `lrp2dclone` = `pg_dump --exclude-table-data=hr_payslip_line payobook | psql` (322 MB, restore 07:55:47 →
07:57:07 UTC; LR16/LR26). Prep before odoo-bin: `payroll_ai_config` 0 active / 0 keys, every `*api_key*` parameter
blank (checked, abort otherwise; LR17), 88 jobs and the mail server off, `base.group_user` → `group_payai_user`
implied on the clone only (LR18). Stage `/tmp/p2dstage` = `git archive HEAD` of the 7 modules (pb_hub staged from HEAD
beside pb_learn) + `pb_home_hub` linked read-only. `--addons-path=/tmp/p2dstage,/odoo/odoo-server/addons`, ports
8097/8096, `-u` the 7 + pb_payai_actions, tags `/pb_learn`, `/pb_formula_studio:TestStudioExperience`,
`/pb_formula_studio:TestLaneLabels`, `/pb_payruns`, `/pb_payai_actions:TestOneChatClient`.

**457 tests, 1 failed, 0 errors** (07:57–08:00 UTC). The one failure is the known baseline
`TestQuestionMining.test_07b` (asserts the question-mining job is active; the clone switches jobs off).
`TestCoach.test_11` passed (AI off). Per-module stats lines: pb_learn 401, pb_payruns 114, pb_formula_studio 17,
pb_payai_actions 5. No other ERROR line, no model call. Clone dropped with `dropdb --force`; filestore, stage and the
comparison folder removed.

## Deploy
Before the stop: no `odoo-bi[n] … stop-after-init` running, no rollout unit, lock free (checked 07:54 and 08:01).
`ListAgents` / `SendMessage` are not available to this agent, so coordination was the server check alone. Ran as unit
`lrp2-deploy` under `flock -n /tmp/payobook-studio-deploy.lock`; stage = clean `/tmp/deployP2` from `git archive HEAD`
(the old `/tmp/deployP2` was another program's September leftover, cleared); per-module `rsync -a --delete` into
`/odoo/odoo-server/addons/<m>/`; `~/pb_upgrade.sh` per DB, payobook first.

| Step | UTC |
|---|---|
| Lock taken | 08:01:28 |
| Service stopped | 08:01:47 |
| Files copied | 08:01:48 |
| payobook / rize / payobook_template / abm `-u` started | 08:01:48 / 08:02:51 / 08:03:38 / 08:04:24 |
| Guide switch (shell, service still stopped) | 08:05:06 → 08:05:11 |
| Service started (port 8069 bound) | 08:05:16 |

**Downtime ~3.5 min** (08:01:47 → 08:05:16). Every `-u` EXIT=0; 0 ERROR/CRITICAL in the four upgrade logs, the switch
shell and the service log after start.

- **Vietnamese:** the range's `vi_VN.po` changes only ADD msgids (pb_formula_studio 2: the Re-classify tooltip and
  toast; pb_learn 1: "Field card rated"); no msgstr was reworded, so no overwrite load was needed (LR20/LR29 not
  triggered). The plain `-u` loads the new entries.
- **Files:** all 7 module trees byte-identical stage ↔ server after the deploy (`rsync -rcn`, 0 differing files).
- **Versions:** `latest_version` = the new manifest version for all 7 modules in all 4 DBs (table above).
- **Assets:** purge + `web.assets.version` bump + `orm_signaling_assets` row per DB.
- **Scheduled jobs:** payobook 37 → 37, rize 69 → 69 (no job newly on). The upgrade switched **abm** 20 jobs and
  **payobook_template** 23 jobs back on — switched off in the same script; both **0**.
- `payai.voice_enabled` on payobook: True before, True after. payobook.com and rize.payobook.com: HTTP 200.

## Guide switch (step 4)
Set on **payobook only**, inside the deploy window (service stopped, so every worker starts with fresh caches), by
`odoo-bin shell -d payobook` running `env['learn.settings'].set_switch('guide', True)` as `__system__` (uid 1, holds
Administrator; the database's own admin account is the owner's login, so it was not used). Service log:
`WARNING payobook … learning setting guide switched ON by __system__ (uid 1). Parameter pb_learn.guide_enabled is now
True.` Read back after start:

| DB | `pb_learn.guide_enabled` |
|---|---|
| payobook | **True** |
| rize | unset (= off) |
| payobook_template | unset (= off) |
| abm | unset (= off) |

LR39 reminder: on rize, payobook_template and abm the treatment board now has no column explanations (the expander is
gone and the Guide is off) until someone switches the Guide on there.

## Browser walk (LIVE payobook.com, QA Test, own headless Chrome on 9558, sign-in by `fetch('/web/session/authenticate')`)
Screenshots: `/private/tmp/claude-502/-Users-adity-Documents-GitHub-gitlocal/d3a7939f-6b40-427b-9e7d-c5a89b5a6ab8/scratchpad/p2/walk/`.
Error + rejection collector installed after each load; it stayed empty on every step.

| # | Result | Evidence |
|---|---|---|
| L1 Component treatment ≥ 1280 px | **pass** — 1440 px: docked, panel 420 × full height under the top bar, page padded 420 px, corner button hidden; This screen · Right now · Fields on this screen · Tasks · Understand + Ask; path "Before this Formula Engine › Mapping › Component treatment › Next Run / Runs"; (i) on all six headers (lane, report_group, pay_role, rollup, run_signal, value_kind); Right now on "Payobook Retail — End-Month Payroll": "3 pay runs were computed before your last change …" + Open run. **Show**: on "Test G2" (1 row waiting) and "Payobook Scale Demo — 250 Columns" (250 waiting) Right now said "N rows still need your answer on Pay role …" + Show; Show switched the board's chip from "All 250" to "Needs your answer 250". Live data has no scheme where only some rows wait, so the row count could not visibly shrink (P2's clone walk B2 showed the narrowing on staged data). | `p2d_l1_docked.png`, `p2d_l1_show.png`, `p2d_l1_show250.png` |
| L2 Pay role (i) → card; Esc | **pass** — card "Pay role": six choices with when, How it is filled, Used by 6 + "and 8 more", If you change it, Open in the Guide / Watch this field. Esc closed the card only, focus back on the Pay role (i), Guide still docked. | `p2d_l2_card.png` |
| L3 Explain this screen | **FAIL (not a regression)** — the answer is "Composed from the guide": one AI-written paragraph ("…To proceed, you need to clear any chips that are present before making any changes…"), no "You are here", no "Next" steps, no column lines; buttons Watch / Practise this / Open the Guide / Open the lesson. Cause: payobook has `pb_learn.compose_enabled` = True and 2 active AI connections, and `explain_screen` returns `_explain_composed(floor)` whenever compose is on — which rewrites from `_explain_wire_text` (the older authored screen text), discarding the Guide-shaped floor. P2's clone walk had AI off, so it never saw this (LR42). Product code not changed. | `p2d_l3_explain.png` |
| L4 typed "What should I do next here?" | **pass** — "From the guide", the live step ("3 pay runs were computed before your last change … Recompute them …"), Open the Guide / Open the lesson; no model answer. | `p2d_l4_whatnext.png` |
| L5 Runs board | **pass** — docked; Right now "17 draft pay runs can be checked and submitted for approval: …" + Open; Open stays on Pay Run › Runs with the first draft's card focused ("Payobook Construction — End-Month Payroll · October 2026"). | `p2d_l5_runs.png`, `p2d_l5_open.png` |
| L6 Vietnamese | **pass** — titles Màn hình này / Ngay lúc này / Các trường trên màn hình này / Tác vụ / Hiểu rõ; path and Right now in Vietnamese; headers Thành phần … Loại giá trị; six (i) found; card "Vai trò trong lương", Cộng vào thực nhận …, "và 8 chỗ khác", Mở trong Hướng dẫn / Xem trường này. QA Test switched back to **en_US** (read back from the database). | `p2d_l6_vi.png` |
| L7 Learning page | **pass** — "Your journey" with its seven sections; console: only the old brand-icon manifest size warning. | `p2d_l7_learning.png` |
| L8 rize.payobook.com (not signed in) | **pass** — `/web/login` and `/` 200; logged-out load: no failed request, no 4xx/5xx, no console error or warning, no Guide element. | `p2d_l8_rize.png` |

## Not done / open (for Fable)
1. **L3 — Explain on a database with "compose" on** (LR42): the Guide-shaped Explain never shows on payobook while
   `pb_learn.compose_enabled` is on. Choices: skip the rewrite when the floor carries `guide_door`, or give the
   composer the Guide material instead of the old text; or switch compose off on payobook (an owner call — it changes
   every typed miss too). The composed paragraph's "clear any chips" sentence is the model's reading of the old authored
   next step.
2. Show's narrowing was not visible on live data (every waiting scheme has all its rows waiting); covered by the clone
   walk B2.
3. Guide is OFF on rize, payobook_template, abm (as instructed) — LR39 applies there.
4. P2 report open items 1–5 unchanged.
5. Not pushed.

## Owner decisions 2026-10-17 22:40 Sydney (applied by Fable)
- **Guide switch ON for rize and payobook_template** as well (owner: yes). Set by direct SQL on `ir_config_parameter`
  (`pb_learn.guide_enabled = True`) followed by `INSERT INTO orm_signaling_default DEFAULT VALUES` on each DB so the
  running workers drop their parameter cache. abm left OFF (retired tenant). Read-back: payobook True, rize True,
  payobook_template True, abm unset.
- **Keep `pb_learn.compose_enabled` ON for payobook** (owner: yes). The L3 Explain rewrite is fixed in P3 (S10).
