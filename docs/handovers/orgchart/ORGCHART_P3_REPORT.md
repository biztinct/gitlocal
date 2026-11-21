# ORGCHART P3 — report (planning mode, time machine, suggest a chart)

Implemented per `ORGCHART_P3.md` and `ORGCHART_LEDGER.md`. `pb_orgchart`
**19.0.1.2.0 is live on all four databases** (`payobook`, `payobook_template`,
`p0clone`, `rize`); `abm` not touched. Browser walk on rize.payobook.com as the
signed-in admin (Ash Sohani) and payobook.com as the signed-in demo admin
(Mitchell Admin); both sessions were already open, no login was typed.

**Read first:**
1. **Approve was not clicked in the browser.** The browser tool's safety check
   refused the Approve click on the request. I did not route around it.
   "Approved → made live" is proved by unit tests 06/07/08/11 on p0clone; in
   the browser the request was sent, found in the inbox, opened, read and then
   **withdrawn** by its sender.
2. **That withdrawal found a real bug** (G23): a withdrawn plan stayed "Waiting
   for approval" for ever. Fixed (`89f83c663`, test 05b) — a withdrawn plan is a
   draft again. The rize test plan, withdrawn before the fix, was set to draft
   by one SQL line (logged in `/opt/deploy-notes.md`) and then discarded in the
   app. **No rize employee was changed at any point** (values compared with the
   pre-test snapshot: identical).
3. **Vietnamese screenshot not taken** (case 20). The coordinator relayed an
   owner ruling allowing `qa.test@payobook.com` to be switched to Vietnamese;
   switching a login's language is an account-setting change, a relayed message
   is not the owner's own consent, and no qa.test session was open. The ruling
   is recorded in the ledger; P4 can do it once the owner confirms in chat.

## 1. Files and commits

| Commit | What |
|---|---|
| `635185624` | Kit glyphs `redo`, `wand` (file sync, kit version unchanged — G5) |
| `337acb17c` | Server: plan models + approval chain + apply/cron + projection + time machine + suggest + plan RPCs; P2 writes split into `_do_*` helpers; onboarding fill hook; access, rules, process row, cron, hook + migration; 15 tests |
| `7b25be830` | Client: Plan changes / Publish, Plans menu, draft bar, changes panel, undo/redo, outlines + ghost lines, publish/discard/suggest dialogs, time slider + banner; new-starter form passes `fill_job_id`; 202 PO entries |
| `89f83c663` | Fixes from the browser walk: withdrawn plan → draft (test 05b); "Add to plan"; "1 suggested change"; owner ruling wording on approvals (EN+VI); suggest rows vs Bootstrap `.row`; future note without "0 approved plans"; ledger owner rulings 3–4 |
| (this commit) | this report, ledger G22–G28, `p3_shots/` |

Files (new): `models/pb_orgchart_plan.py` (`pb.orgchart.plan`, `.plan.change`,
`register_chain('pb.orgchart.plan','orgplan', submit_state='pending',
driven=('approved',), date_field='effective_date')`, hooks, `_apply`,
`_cron_apply_due`, `seed_all`), `models/pb_orgchart_project.py` (projection
`_proj_base`/`_vapply`/`_project`/`_proj_view`, `_view_for`, past/future views,
`_starters`, plan RPCs, `suggest_chart`, `plan_use_suggestion`),
`models/onboard_fill.py`, `hooks.py`, `migrations/19.0.1.2.0/post-migrate.py`,
`data/approval_process.xml` (process `orgplan`, noupdate), `data/ir_cron.xml`,
`security/ir.model.access.csv`, `security/pb_orgchart_security.xml`,
`static/src/js/orgchart_plan.js`, `tests/test_orgchart_p3.py`.
Changed: `pb_orgchart.py` (`get_chart(plan_id, as_of, expand)`,
`get_branch(…, plan_id, as_of)`, `_graph(view)`, `_rows(view)`,
`_open_roles(view)`), `pb_orgchart_write.py` (RPC → `_do_*` split, behaviour
identical), `orgchart.js`, `orgchart_edit.js`, `orgchart_dialog.js`,
`orgchart.xml`, `orgchart.scss`, `vi_VN.po` (352 → 568 entries),
`__manifest__.py` (19.0.1.2.0; depends + `pb_people_advanced`,
`biz_approval_chain`, `biz_approval_workflow`; post_init_hook),
`pb_people_advanced/static/src/js/onboard_wizard.js` (file sync, version
unchanged), `pb_import_kit/static/src/js/import_icons.js` (file sync).

Carry-over §1.4 — **which change I picked:** a `create_employee` override on
`pb.people.onboard.wizard` inside `pb_orgchart` (`onboard_fill.py`), keyed on
`fill_job_id`, which the chart puts in the pre-fill only for "Fill this role ›
A new starter" and the form sends back. It lowers the job's to-hire count once
the employee is really created — at once, or later when a new-hire approval is
carried out (the same method runs again with the stored values) — never below
0, and not when the job was changed on the form. Smaller than a context flag
(no context reaches the RPC, and a deferred new-hire approval would lose it).

## 2. Tests

### Unit — **52 of 52 pass** (36 P1+P2 unchanged + 16 P3)

p0clone, scratch addons dir first (`--addons-path=/tmp/oc3_test/addons,/odoo/odoo-server/addons
-u pb_orgchart --test-enable --test-tags /pb_orgchart --stop-after-init
--max-cron-threads=0 --http-port=8199 --gevent-port=8198`), log
`/tmp/oc3_test/t.log`, last line `0 failed, 0 error(s) of 52 tests`. Zero
"no translation language detected" warnings from `pb_orgchart` after G27.

| # | Case | Test | Result |
|---|---|---|---|
| 1 | `plan_open` creates one draft, same on the second call; one per person; plain user refused | test_01 | PASS |
| 2 | move: projection shows it, live tree unchanged | test_02 | PASS |
| 3 | loop judged against the projection (not the live tree), plan unchanged | test_03 | PASS |
| 4 | remove a change → projection reverts; batch undo + redo | test_04 | PASS |
| 5 | submit → pending, one request in the engine, HR-team seat holds the boss; detail rows; plain user and another HR user cannot send someone else's plan; sent plan locked | test_05 | PASS |
| 5b | withdrawn plan → draft, editable, nothing live (G23) | test_05b | PASS |
| 6 | approve with today → applied; move, dotted line, new role made; every change `applied`; coach unchanged | test_06 | PASS |
| 7 | future date → stays approved; cron the day before → nothing; cron on the day → applied | test_07 | PASS |
| 8 | target archived in between → that change `error` ("has left"), the other applied, plan stays approved with `apply_error` + chatter; retry leaves the applied change alone | test_08 | PASS |
| 9 | `get_chart(plan_id)`: `changed_ids`, `ghost_edges`, a virtual role, a closed role gone, plan summary; filling a virtual role refused | test_09 | PASS |
| 10 | past: two tracked moves dated −10 / −5 days → manager as of −12, −7, −1; joiner hidden; no open roles; read only | test_10 | PASS |
| 11 | future: approved plan projected at +20, not at +3; leaver hidden | test_11 | PASS |
| 11b | accepted offer → "Starts …" card under the requisition's manager by its date only | test_11b | PASS (pb_hiring present) |
| 12 | suggest on a fixture (team manager, parent team, team lead → top by "Giám đốc" title, left out: no-manager team with no parent / no team), never touches a managed person, no loop | test_12 | PASS |
| 13 | "Use it": draft with 4 changes, one batch, nothing live | test_13 | PASS |
| 14 | new-starter form with `fill_job_id`: 2 → 1; job changed on the form → no change; never below 0 | test_14 | PASS |

### Browser (cases 14–21) — evidence in `p3_shots/`

| # | Case | Result | Evidence |
|---|---|---|---|
| 14 | Plan changes → drag two people, add a role, swap → bar counts 4; outlines + ghost lines; panel lists the POC labels; Undo/Redo; Discard restores | **PASS** — rize: Use it (1) + drag Demo Le Thi Hoa onto Dhruv Sawhney (sheet with the amber line, "Add to plan" after the fix) + new open role "P3 Test Planner" (A new starter hidden in plan mode) + swap DEMO Probation Colleague ⇄ DEMO Lifecycle Manager (offered because the projection gives the manager a manager) → badge 4, 4 cards outlined, 2 dashed rose lines; Undo 4 → 3 (Redo lit), Redo → 4. A second drag landed during the glide and did nothing (one-go drag, G21). Discard on payobook: confirm dialog → live chart, toast "Plan discarded — the chart is back to how it was." | `T14_rize_*`, `T14_payobook_discard_dialog.jpg` |
| 15 | Publish → dialog → send → toast; Plans "Waiting for approval"; inbox shows the rows; approve → live | **PARTIAL** — dialog lists the 4 changes, "Your approver, HR team (Ash Sohani), gets one request covering all 4", date, name, message; sent → toast "Sent to the HR team for approval. You'll be told when it is live."; Plans menu "P3 browser test … · 4 changes · goes live 5 Nov 2026 · Waiting for approval"; inbox card "Org chart change: … (4 changes)", drawer with facts (3 people, 4 changes, 1 new role, crosses teams: Yes), the 4 rows, "Goes live on" / "Planned by", route HR team → Ash Sohani. **Approve refused by the browser tool's safety check**; withdrawn instead → found G23 (fixed). rize data unchanged throughout. | `T15_rize_*` |
| 16 | Resume a draft after reload | **PASS** — reload opens the live chart (234 without a manager), Plans has an amber dot and "You have a draft with 4 changes · Resume"; Resume → bar, badge 4, 4 outlines, panel 4 | `T16_rize_reload_plans_menu_resume.jpg` |
| 17 | Time machine 200 days back on payobook | **PASS** — 4,547 → 4,429 people (joined since: hidden), 0 open roles, 2 levels; amber banner "You are looking at Apr 19, 2026…" + note; button "200 days ago"; Plan changes and card edit buttons gone; Back to today restores. Tracked history on payobook starts 31 Aug 2026 (6 manager rows); Thái Ngọc Diệp (moved under Ngô Bảo Lâm 15 Sep) is not in his team on 1 Sep and is on 20 Sep and today (same read the screen uses). Redraw ≈ 4 s on 4,500 people incl. the 250 ms pause | `T17_payobook_200_days_ago.jpg` |
| 18 | +60 days: approved plan moves, leaver gone, offer ghost | **PARTIAL** — 4,547 → 4,541 (the 6 people with a departure date disappear). payobook has **no approved plan** (approval refused, see 15) and **no accepted offers** (offers: submitted 1, dropped 1, joined 4) → no "Starts …" cards; both covered by unit tests 11/11b | `T18_payobook_in_60_days.jpg` |
| 19 | Suggest on rize, Use it, Discard | **PASS** — see §4 for the counts; Use it → planning mode with the change; Discard (with the plan) at the end | `T19_rize_*` |
| 20 | Vietnamese dialog + bar screenshot | **PARTIAL** — not taken (Read first, 3). The live app serves **409** chart strings in Vietnamese (`/web/webclient/translations`, `cache:'no-store'`, G19), every sampled P3 string present ("Lập kế hoạch", "Công bố thay đổi", "Gợi ý sơ đồ", "Thêm vào kế hoạch", the approvals sentence …) | measurements |
| 21 | Console clean; no "Odoo" (incl. request detail) | **PASS** — no console errors on rize or payobook; "Odoo" scan of chart text, titles, placeholders, labels: 0; the inbox drawer screenshot has none; `.po` msgstr and module strings: 0 | `T15_rize_inbox_request_detail.jpg` |

## 3. Approval route as seeded (process `orgplan`, workflow "Org chart changes")

Laid by the 19.0.1.2.0 migration (`seed_all`); queried from
`biz_approval_binding` / `biz_approval_workflow(_version)` /
`biz_approval_responsibility` after the deploy:

| Database | Company | Binding | Version | Independence | HR team holder |
|---|---|---|---|---|---|
| p0clone | My Company | active | published v1 | on | platform.recovery@payobook.com |
| payobook_template | My Company | active | published v1 | on | platform.recovery@payobook.com |
| rize | Rize Farms | active | published v1 | **off** (copies rize's extension route — owner ruling 2026-09-18) | ash@biztinct.com |
| payobook | Your Company / Payobook / Payobook Vietnam JSC / Payobook Singapore Pte Ltd | active ×4 | published v1 | on | ash@biztinct.com |
| payobook | **SG Company** | **none** | — | — | nobody holds the HR lifecycle seat (its extension route is missing too) |

Route = one step, "HR team", responsibility `lifecycle` (G25 — the catalogue
has no "people" responsibility). On SG Company, sending a plan tries to lay the
route and otherwise answers "Approvals for org chart changes are not set up for
SG Company yet…".

## 4. What Suggest a chart finds

* **rize** (Rize Farms): 236 people without a manager (the 234 in the lane +
  the 2 tops of the two small trees). **1 placed**: DEMO Lifecycle Manager →
  Dhruv Sawhney (he is the only "Chief Executive Officer" without a manager, so
  he is the top). **233 left out: "Their team has no manager set, and no team
  above it has one"** — rize's team records carry no team managers; **1 left
  out: not in any team.** In plain words: on rize the suggestion can only help
  once team managers are filled in on the team records.
* **payobook** (Payobook Vietnam JSC): 648 people without a manager (the 10 in
  the lane + the tops of ~640 small teams). **632 placed** — 630 under the
  manager of the team above theirs, 2 under their own team's manager; **16 left
  out** (9 in teams with no manager anywhere above, 5 in no team, 2 team leads
  with no single top person); **no top person** (nobody has a CEO / General
  Director title). Not used on payobook (read-only call).

## 5. Tracking fields verified on the box

`mail_tracking_value`: `field_id`, `old_value_integer`, `new_value_integer`,
`mail_message_id` (+ char/float/datetime/text twins); `mail_message.date`,
`model`, `res_id`. History available: payobook 6 `parent_id` rows from
2026-08-31; rize 26 `parent_id` + 2 dotted rows, all 2026-11-04 (P2's tests);
p0clone none. `hr_employee.first_contract_date` is a stored column (join date
for hiding in the past view, then earliest contract start, then created on);
`hr_version.departure_date` (leavers in the future view).

## 6. Deploys

All with `/odoo/ops/filter_deploy.sh`, staged from committed HEAD (`git
archive`), staging dir cleaned first, START/DONE in `/opt/deploy-notes.md`.
Before the first deploy the live trees of `pb_import_kit`, `pb_people_advanced`
and `pb_orgchart` equalled their pre-P3 commit (no foreign work overwritten);
lock free (`fuser` empty); no open START. `ListAgents` is not available in
this session — coordination was the deploy notes and the lock. Gates before
each: libsass compile of `orgchart.scss` on the box OK; `PoFileReader` 564 /
568 rows, none empty.

| Deploy | Commit | Modules → version | Window (UTC) | p0clone / template / rize / payobook | Jobs before/after | Evidence |
|---|---|---|---|---|---|---|
| A full | `7b25be830` | pb_orgchart **19.0.1.2.0** (`-u`); pb_import_kit + pb_people_advanced files only (19.0.1.22.1 / 19.0.1.1.2 unchanged) | 19:02:25–19:04:42 | EXIT=0 errors=0 ×4 | 32/28/74/42 unchanged by the script → **new job switched on by hand** on template/rize/payobook (G22) → 32/29/75/43 | `/tmp/orgchart-p3-run-20261104190225` |
| B full | `89f83c663` | pb_orgchart 19.0.1.2.0 | 19:28:57–19:31:36 | EXIT=0 errors=0 ×4 | 32/29/75/43 unchanged | `/tmp/orgchart-p3b-run-20261104192856` |

p0clone was already at 19.0.1.2.0 from the unit-test run (its job came on
there). Sites warm 200 after both. Backups in `/odoo/backups/<run name>`.

## 7. Live data left as found

* **rize:** the five people the test plan touched — values identical to the
  pre-test snapshot (Demo Le Thi Hoa → Demo Vo Thanh Son, coach Demo Vo Thanh
  Son; DEMO Lifecycle Manager no manager; DEMO Probation Colleague → DEMO
  Lifecycle Manager; 5 people with a manager). No job was created (the plan was
  never approved). What stays: plan 1 "P3 browser test (put back afterwards)"
  in state **Discarded** with its chatter, and the **withdrawn** request in the
  approvals history ("Finished" tab) — the audit trail, not deleted. One data
  fix: that plan's state pending → draft (SQL, logged) so it could be discarded
  in the app.
* **payobook:** one discarded test plan (1 planned change, never sent); no
  employee changed; no demo data deleted.

## 8. Design-bar self-score, and deviations

Hero moment: press **Plan changes** and the chart becomes a sandbox — drag
people anywhere, amber outlines and dashed rose lines mark every move, the
panel reads the effect in one paragraph, one tap sends it; drag the time slider
and the chart rewinds. Delivered on both tenants.

* **Every state designed** — empty plan panel with a Suggest door; stale change
  ("No longer possible: …") and failed change ("Could not be made: …") rows;
  read-only plan view bar; time banner; Plans menu empty/loading; discard
  confirm; suggest loading/failed; fast-lane wording when no approval is
  needed.
* **Plain language** — every label is a sentence; the approver is named
  ("HR team (Ash Sohani)"); EN + VI; no "Odoo".
* **Motion with purpose** — cards glide into the projection, changed cards
  flash, the panel slides in; nothing animates per pointer move (G12/G15
  rules kept: card state is `data-st~="chg"/"fut"`).
* **Keyboard** — ⌘Z / ⇧⌘Z undo/redo in plan mode; Enter in dialogs.
* **Short of best** — a plan change redraws the whole payload (≈0.5 s on
  payobook's cut chart, fine on rize); Approve not proved in the browser; the
  shared inbox drawer clips long change rows.

Deviations from the handover / POC, and why:
1. **Responsibility `lifecycle`, not `people`** (G25): no `people`
   responsibility exists; the HR lifecycle team already decides extensions.
   Step title "HR team" as asked.
2. **Independence follows the company's extension route** — honours rize's
   owner ruling (one login) without a per-tenant special case.
3. **Batches**: several people moved at once, and a suggestion, are one batch;
   one Undo takes the batch out (POC undo pops one change).
4. **"Move only them"** is one change with `whole_team = false` (the POC
   created one change per left-behind report).
5. **Extra RPCs**: `plan_add_changes` (batch), `plan_undo`,
   `plan_use_suggestion` (server re-works the suggestion and adds it in one
   batch, skipping any the plan no longer allows).
6. **Apply writes as the person who planned it** (`with_user(planner).sudo()`),
   so the History tab names the planner; the approver is on the request trail.
7. **Past view shows no open roles** (they are today's vacancies) and today's
   titles/teams; future view keeps today's open roles plus approved plans'.
8. **A new starter is not plannable**: the "A new starter" option is hidden in
   planning mode (it opens the live new-employee form).
9. **New open roles in a plan are virtual** ("New in this plan"); filling or
   moving them is refused with a sentence; "Take this role out of the plan" on
   the right-click menu.
10. **Withdrawn plan → draft** (G23), not in the handover.
11. **Plans menu** also lists my applied/turned-down plans of the last 30 days.
12. Model field labels (`string=`) of the two new models have no Vietnamese
    entries — they appear on no screen of this phase.

## 9. Gotchas appended to the ledger (§3)

G22 deploy script switches a new job off · G23 chain bridge has no withdrawn
hook · G24 never a `.row` class (Bootstrap) · G25 no "people" responsibility;
independence copied; SG Company without a holder · G26 new companies get a
lifecycle holder (tests reuse it) · G27 `_()` needs an env in its frame · G28
the browser tool may refuse Approve.

## 10. For P4 and the closeout

**P4 needs:**
* Approve a plan in the browser (or confirm the owner is happy with unit-test
  proof) — then a plan made live and undone on rize with the stored
  `undo_snapshot` per change (restore in reverse order).
* The Vietnamese screenshot (dialog + draft bar) once the owner confirms the
  qa.test language switch in chat.
* Export of the projection (picture/PDF of a plan; the CSV exports what is
  drawn, including a plan's projection).
* Lessons: "Plan changes" (sandbox → publish → approval), the time slider,
  Suggest a chart. No Learn lesson mentions the chart today.
* Speed: plan-mode redraw re-reads the payload; the pan/zoom Web Animation
  idea from P2 still stands.
* Engine owner: G23 likely affects the other chain consumers; the inbox drawer
  clips long detail rows; SG Company on payobook has no HR lifecycle holder.

**Open owner questions (running list):**
1. Pay on the chart (D8) — dropped; still wanted for managers?
2. A public read-only share link (D9) — needs a privacy decision.
3. Comparing two plans side by side (scenario compare).
4. The past view does not bring back people who have left since — should it?
5. Spreadsheet of a cut chart: export only what is loaded, or everyone?
6. A virtualised canvas for very large charts (4,500+ people).
7. May qa.test@payobook.com be switched to Vietnamese for screenshots? (relayed
   ruling says yes — please confirm directly).
8. rize: the suggestion places almost nobody because team records have no
   managers — fill team managers on rize, or set managers by hand?
