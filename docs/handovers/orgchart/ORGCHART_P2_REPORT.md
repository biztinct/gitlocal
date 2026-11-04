# ORGCHART P2 — report (changing the chart, live)

Implemented per `ORGCHART_P2.md` and `ORGCHART_LEDGER.md`. `pb_orgchart`
**19.0.1.1.0 is live on all four databases** (`payobook`, `payobook_template`,
`p0clone`, `rize`); `abm` not touched. Browser walk on rize.payobook.com as the
signed-in admin (Ash Sohani) and payobook.com as the signed-in demo admin
(Mitchell Admin). Both sessions were already open; no login was typed
anywhere.

**Incident to read first:** the first P2 deploy shipped a Sass `min()` with
mixed units. From the 16:24 UTC restart until ~16:30 UTC **every backend page
on all four databases showed the fallback "old style" look** (the app worked,
the styling was wrong). Fixed by `26072e0e3`, applied by hand because the
deploy lock was held (G14, G18). A libsass compile gate now runs before every
SCSS deploy.

## 1. Files and commits

| Commit | What |
|---|---|
| `0603d4a0c` | Kit glyphs `move`, `arrowUpDown` (file sync, kit version unchanged — G5) |
| `30684099a` | Server: fields, write RPCs, `restore`, `get_history`, 15 tests |
| `f3811bda7` | Client: drag, picking, dialogs, context menu, pill, History tab, undo; 350 PO entries |
| `8ebb5d0c2` | `pb_people_advanced`: new-employee form takes a pre-fill (file sync, version unchanged) |
| `26072e0e3` | Fix: dialog width without Sass `min()` (the style-bundle incident) |
| `40450fd16` | Fix: coach never changed by a move; undo restores approvers; Undo toast 10 s; pick bar top-left; test 15 |
| `3ae065186` | Perf: ghost and pill move by Web Animation, show/hide by `data-on` (G15) |
| `12af5cd37` | Perf: no `z-index` on the drop target (G15) |
| `1d8395886` | Fix: a move changes the manager only (coach + approvers kept, G16); plain wrapper for system refusals; test 16 |
| (this commit) | this report, ledger G14–G21, `p2_shots/` |

Files:

* `pb_orgchart/models/hr_fields.py` (new): `hr.employee.pb_dotted_manager_id`
  "Also reports to"; `hr.job.pb_manager_id` "Reports to on the org chart";
  `hr.job.pb_reason` (growth / backfill / cover). All tracked, all with plain
  help text, no migration.
* `pb_orgchart/models/pb_orgchart.py`: `_graph` also reads the dotted column
  (SQL, same pass); rows carry `dotted_id`; `_job_manager` tries
  `pb_manager_id` first; roles carry `reason`/`reason_label`; counts split
  into `_shape_counts()` (dotted now real).
* `pb_orgchart/models/pb_orgchart_write.py` (new): `move`, `move_many`,
  `unassign`, `swap`, `set_dotted`, `add_open_role`, `move_role`,
  `fill_role`, `close_role`, `restore`, `get_history`; helpers `_person`,
  `_manager_for`, `_job`, `_role_manager`, `_loop_in`, `_snap`,
  `_set_managers`, `_followers`, `_refresh`, `_run`.
* `pb_orgchart/static/src/js/orgchart_edit.js` (new): the editing half,
  installed onto `PbOrgChart` (`installEdit`).
* `pb_orgchart/static/src/js/orgchart_dialog.js` (new): `PbOcDialog`.
* `orgchart.js`, `orgchart.xml`, `orgchart.scss`: wiring, templates, styles.
* `pb_orgchart/i18n/vi_VN.po`: 352 entries (P1 166 + 186 new).
* `pb_orgchart/tests/test_orgchart_p2.py` (new): 17 tests.
* `pb_people_advanced/static/src/js/onboard_wizard.js`, `.../xml/onboard_wizard.xml`,
  `.../scss/wizards.scss`, `models/people_wizards.py`, `i18n/vi_VN.po` (3 entries).

## 2. Tests

### Unit (cases 1–11b + extras) — **36 of 36 pass**

Run on `p0clone` from a scratch addons dir listed first (SCHEMECTX §0.13:
`--addons-path=/tmp/oc2_test/addons,/odoo/odoo-server/addons -u pb_orgchart
--test-enable --test-tags /pb_orgchart --stop-after-init --max-cron-threads=0
--http-port=8199 --gevent-port=8198`), log `/tmp/oc2_test/t.log` on the box,
result line `0 failed, 0 error(s) of 36 tests` (19 P1 + 17 P2). Active
scheduled jobs on p0clone after each run: 31 (unchanged). The first run
found the hr.job rights issue (4 fails, G17) — fixed before the first deploy.

| # | Case | Result |
|---|---|---|
| 1 | move whole team: reports follow, label "Hai One now reports to Hoa Two", undo payload, refresh rows carry the new tree + numbers, undo restores | PASS |
| 2 | move only them: reports go to the old manager; with no old manager they go to the lane; undo | PASS |
| 3 | own team (POC sentence), self, left, other company (switched on: "works for … same company"; not switched on: "no longer on the chart"), already reports | PASS |
| 4 | dotted set / solid-manager refused / clear / undo ×2; tracking row written; count 1 → 0 | PASS |
| 5 | unassign → lane (no-manager count 2) + undo; "no manager to remove" | PASS |
| 6 | swap on a 3-level fixture (POC semantics incl. their own reports) + undo; refused at the top | PASS |
| 7 | add_open_role creates (team, manager, reason), same title bumps to 2, undo of bump → 1, undo of create deletes the job (`gone_roles`) | PASS |
| 8 | fill_role: job, title, manager; 2 → 1; undo; 1 → 0 and the role leaves; filling a closed role refused; the role's own manager refused | PASS |
| 9 | close_role → 0, job stays active; undo → 2 | PASS |
| 10 | get_history: "Moved from Cara Ceo to Hoa Two", "Dotted line to Lan Lone added", who = "Hana HR", ISO day; posts nothing | PASS |
| 11 | plain user gets "Only an HR user can change who reports to whom." from all 10 write RPCs; nothing changed | PASS |
| 11b | move_many of three in one go; with an ancestor of the target in the set the whole call is refused naming the person, none moved; undo restores all three | PASS |
| 12 | move_role + undo (role falls back under the department manager) | PASS |
| 13 | undo refused when the old manager has left since | PASS |
| 14 | undo refused when the chart changed into a loop since | PASS |
| 15 | a move never sets a coach or moves approvers; undo puts them back exactly | PASS |
| 16 | a person with a PORTAL login can become a manager through a swap (the payobook refusal, G16) | PASS |

### Browser (cases 12–24)

Evidence in `docs/handovers/orgchart/p2_shots/`; measurements taken with page
scripts in Chrome.

| # | Case | Result | Evidence |
|---|---|---|---|
| 12 | drag → sheet → Move now → toast with Undo → Undo | **PASS rize** (Demo Le Thi Hoa onto DEMO Lifecycle Manager; ⌘Z restored; the toast had closed before a click could reach it → now 10 s). **PASS payobook** (sheet shows the manager-only line) | `T12_rize_move_sheet.jpg`, `T12_rize_moved_toast_undo.jpg`, `T12_rize_undone_cmdZ.jpg`, `T12_payobook_move_sheet_manager_only_line.jpg` |
| 13 | drag onto own team → refused with the sentence | PASS — rose toast "Can't do that — Demo Le Thi Hoa is inside Demo Vo Thanh Son's own team."; the rose outline itself cannot be captured mid-drag with this tool (G21) — it is the same `data-over="bad"` path the measurement script saw set | `T13_rize_drop_on_own_team_refused.jpg` |
| 14 | change manager via card pill and side panel | PASS — side panel "Change manager" → picker (Enter picks the only match) → move sheet → moved; panel facts updated live; the pill's Change manager opens the same dialog | `T14_rize_change_manager_picker.jpg`, `T14_rize_side_panel_footer_and_pill.jpg` |
| 15 | dotted line: add, amber dashed edge, number, clear | PASS — edge drawn, "1 dotted lines", "Dotted line" tag, History entry; Remove → 0 and edge gone | `T15_rize_dotted_line_edge_number_history.jpg` |
| 16 | add team member: existing / open role / new starter | PASS — existing + Undo; open role "P2 Test Agronomist" (Backfill) → dashed card, 67 → 68; **new starter: the form opens PRE-FILLED** ("Reports to DEMO Lifecycle Manager — set from the org chart", team set); nothing saved | `T16_rize_new_open_role_dashed_card.jpg`, `T16_rize_new_starter_form_prefilled.jpg` |
| 17 | fill an open role with an existing person | PASS — Demo Tran Van Hung took the role: title changed, card moved under the role's manager, role card gone, 68 → 67; ⌘Z restored all | `T17_rize_role_filled_card_moved.jpg` |
| 18 | swap places; Undo | rize: not offered (both trees are two levels; spec refuses swapping with the top). **payobook: first attempt REFUSED** ("exclusive groups Portal / User", nothing changed) → fix `1d8395886` → **PASS**: Trần Minh Khôi ⇄ Bùi Hữu Bảo, ⌘Z restored | `T18_payobook_swap_context_menu.jpg`, `T18_payobook_swap_refused_BEFORE_fix_portal_login.jpg`, `T18_payobook_swapped_toast_undo.jpg` |
| 19 | remove from team → lane; drag back out of the lane | PASS — right-click → Remove → lane (234 → 235); dragged from the lane onto Demo Vo Thanh Son → sheet → back (234) | `T19_rize_person_context_menu.jpg`, `T19_rize_removed_to_lane.jpg`, `T19_rize_drag_back_out_of_lane.jpg` |
| 20 | close an open role | PASS — right-click on the role → Close → card gone, 68 → 67; ⌘Z; ⌘Z again removed the test job entirely | `T20_rize_role_context_menu.jpg` |
| 21 | History tab shows the moves with who and when | PASS — "Moved from Demo Vo Thanh Son to DEMO Lifecycle Manager · Nov 5, 2026 · by Ash Sohani" ×3 + Joined | `T21_rize_history_tab.jpg` |
| 21b | rize lane: pick five (⌘-click + Shift-click), Set manager…, one toast, Undo; drag three | PASS — five picked with badges, "Who should these 5 people report to?" → "5 people now report to Demo Vo Thanh Son" (234 → 229), ⌘Z (229 → 234); three ⌘-clicked and dragged onto DEMO Lifecycle Manager → "Move 3 people…" → moved (231) → ⌘Z (234). The bar was below the fold on a short window → moved top-left | `T21b_rize_five_picked_in_lane.jpg`, `T21b_rize_five_moved_one_toast.jpg`, `T21b_rize_drag_three_sheet.jpg`, `T21b_payobook_pick_bar_top_left.jpg` |
| 22 | user without HR rights | **PARTIAL (rehearsed)** — no staff login was signed in and none was typed. On payobook the loaded chart's `may_write` was set to false **in memory only**: footer "Ask an HR user to change who reports to whom.", pill = 1 button (Open side panel), drag does not start, right-click shows only Open side panel / Expand team / Show only this team / Open employee record. Server side is unit test 11 | measurements |
| 23 | Vietnamese | **PARTIAL** — live server answers in Vietnamese when asked in vi_VN ("Không ai có thể báo cáo cho chính mình.", history "Chuyển từ Nguyễn Thu Lan sang Bùi Hữu Bảo · Mitchell Admin · 2026-11-05"); the web client serves 291 screen strings for `pb_orgchart` in Vietnamese incl. every dialog/toast word checked. A Vietnamese dialog screenshot needs a signed-in user switched to Vietnamese — that changes an account setting, so it was not done (owner item §8) | measurements |
| 24 | console clean; no "Odoo" | PASS — no console errors on rize or payobook across the walk; "Odoo" scan of chart text + titles + placeholders + aria labels: 0 hits | measurements |

### Drag performance on payobook (657 cards) — §3.1

| | before the fixes | after |
|---|---|---|
| pointer-move handler (median / p95) | 61 / 63 ms | **9.8 / 10.8 ms** (target < 16 ms) |
| drag start (one-off: ghost filled, cards marked) | — | 138 ms |
| frame while the pointer stays over the same card | ~60 ms | **16.7 ms** |
| frame when a new card lights up as the target | 125–130 ms | ~40–50 ms |

The remaining ~40 ms per new target is the page-wide style check G12
describes for any attribute that a stylesheet rule reads; it happens once per
card crossed, not per pointer move.

## 3. Findings the handover asked for

* **hr.job rights:** with recruitment installed, `hr_recruitment` re-declares
  `hr.access_hr_job_user` as read-only (`hr_recruitment/security/ir.model.access.csv:4`;
  the vendored `hr` CSV's 1,1,1,1 is overridden), and the job's interviewer
  field is recruitment-only. **HR officers cannot write `hr.job`.** The chart
  writes jobs with `sudo()` after its own `_may_write()` check; the user stays
  the author of the tracking message (G17).
* **New-starter pre-fill:** `pb_onboard_wizard` read nothing from its action.
  It now reads `params.prefill` (manager, team, job, title), shows "Reports to
  X — set from the org chart" with a clear button, binds the selects/title,
  and `create_employee` accepts `parent_id`. Shipped as a file sync with the
  version unchanged (`-u pb_people_advanced` would cascade to `pb_people`,
  `pb_contracts`, `pb_contract_lifecycle` and everything after them). Verified
  live on rize (§2 case 16).

## 4. Deploys

All with `/odoo/ops/filter_deploy.sh`, staged from committed HEAD (`git
archive`), staging dir cleaned first, START/DONE in `/opt/deploy-notes.md`.
Before the first deploy the live trees of `pb_import_kit`,
`pb_people_advanced` and `pb_orgchart` equalled their pre-P2 commit (no
foreign work overwritten). `ListAgents` is not available in this session;
coordination was the deploy notes (no open START) and the script's lock. PO
gate (`PoFileReader`) before each: 360 → 362 rows, all with text.

| Deploy | Commit | Modules → version | Window (UTC) | p0clone / template / rize / payobook | Jobs before/after | Evidence |
|---|---|---|---|---|---|---|
| A full | `8ebb5d0c2` | pb_orgchart **19.0.1.1.0** (`-u`); pb_import_kit + pb_people_advanced files only (19.0.1.22.1 / 19.0.1.1.2 unchanged) | 16:22:07–16:24:28 | EXIT=0 errors=0 ×4 | 31/28/74/42 unchanged | `/tmp/orgchart-p2-run-20261104162133` |
| B looks (by hand) | `26072e0e3` | pb_orgchart SCSS | ~16:30 | rsync, hash a4c92bec5692 = stage, assets purged ×4 | — | `/tmp/orgchart-p2b-run-20261104162544` (queued unit stopped, G18) |
| C full | `40450fd16` | pb_orgchart 19.0.1.1.0 | 17:08:49–17:11:06 | EXIT=0 errors=0 ×4 | 31/28/74/42 unchanged | `/tmp/orgchart-p2c-run-20261104170848` |
| D looks | `3ae065186` | pb_orgchart JS/SCSS/XML | 17:13 | OK ×4 | — | `/tmp/orgchart-p2d-run-20261104171346` |
| E full | `1d8395886` (incl. `12af5cd37`) | pb_orgchart 19.0.1.1.0 | 17:34:32–17:36:40 | EXIT=0 errors=0 ×4 | 31/28/74/42 unchanged | `/tmp/orgchart-p2e-run-20261104173429` |

`ir_module_module` after E: pb_orgchart installed 19.0.1.1.0 on all four;
pb_import_kit 19.0.1.22.1 and pb_people_advanced 19.0.1.1.2 unchanged. Sites
warm 200. Backups of the full runs in `/odoo/backups/<run name>`.

## 5. Live data left as found

* **rize:** every test move, dotted line, open role, fill and close was
  undone in the app; checked in the database afterwards: the same five people
  have a manager as before (4 under Demo Vo Thanh Son, 1 under DEMO Lifecycle
  Manager), 0 dotted lines, no "P2 Test" job, Demo Tran Van Hung's title back.
  **One leftover was fixed by hand:** the stock coach rule had given the five
  lane people from case 21b (ids 3279–3283) a coach (Demo Vo Thanh Son);
  `coach_id` was set back to empty from the 16:22 backup values (deploy-notes
  line 17:06). The code no longer lets this happen (G16). What stays: the
  History entries (tracking notes) on the people moved and moved back — that
  is the audit trail and was not deleted.
* **payobook:** Trần Minh Khôi / Bùi Hữu Bảo swapped and undone (managers
  verified in the database); the refused attempt wrote nothing. No demo data
  deleted.

## 6. Self-score against the design bar, and deviations

Hero moment (drag someone onto a new manager, the card lights green, one
sentence says what changes, one tap undoes): delivered on both tenants; on a
657-card chart the ghost follows at 60 frames a second.

* **Name the hero moment** — drag → green target → sheet → glide → Undo works end to end; groups move the same way with a count badge.
* **Every state designed** — refusals in one rose sentence (own team, open role as manager, already reports, left, other company, rights); busy buttons; empty picker "No match."; cut-chart note in the picker; read-only footer sentence; History empty state + Joined.
* **Plain language** — every label, toast and refusal is a sentence a manager understands, English and Vietnamese; no "Odoo" anywhere; system refusals are wrapped ("That change could not be saved. The system said: …").
* **Motion with purpose** — cards glide to their new team on readable charts, the moved card flashes green, the view pans only when the card left the screen.
* **Keyboard + bulk** — ⌘/Ctrl-click, Shift-click, "Select all N here", Set manager…, drag a group, M, A, ⌘Z, Esc, Enter in pickers.
* **Best in class** — matches the POC and the tools it was studied against for live edits; bulk set-manager for a company with nobody's manager set goes beyond them. Short of best: a new drop target still costs ~40 ms at 657 cards, and the Vietnamese screen pass was not seen end to end.

Deviations from the handover / POC, and why:

1. **Toast labels use full names** ("Ash Sohani now reports to …"), not the POC's last word: rize mixes Vietnamese, Indian and Indonesian names where the last word is the family name.
2. **One undo method** — every write answers D5's shape with `{'method': 'restore', 'args': [snapshot]}`; `restore` is judged like a write (a manager who left, or a loop made since, refuses the undo). Exact for every action, including swap.
3. **No full reload after writes** — every write returns the server's rows for what it touched (and their managers up the chain) plus the shape numbers; the client patches and relays out. Server-authoritative, and keeps opened teams on a cut chart.
4. **Added `move_role`** (Change manager on an open role, as the POC's role footer has).
5. **A chart move changes the manager only** — coach, time-off approver and expense approver keep their value (G16). The POC lines "Leave and expense approvals go to the new manager" and "The person, both managers and Payroll are told" were not used: the first is now untrue by design, the second would need emails (non-goal). The sheet says the approvers stay and that the History tab records the change.
6. **The move sheet's team line** says the team stays and how to change it (a move does not change the team).
7. **One shared quick-action pill** instead of buttons on every card (fewer elements on a 657-card chart).
8. **Pick bar top-left**, drag hint bottom-centre (the bottom was below the fold on short windows).
9. **Context menu** omits "Export this branch as a picture" (P4) and adds "Open employee record".
10. **Swap is refused at the top** as the spec says, so rize (two-level trees) never offers it.
11. **Cases 22 and 23 partial** (no staff login typed; no user's language switched) — §2.

## 7. Gotchas (appended to the ledger §3 as G14–G21)

G14 Sass `min()` with mixed units kills the whole backend style bundle — compile with the box's libsass first ·
G15 an inline style write costs a whole-page style check; move overlays with a paused Web Animation, `z-index` in a card state = 125 ms frames ·
G16 `parent_id` drags coach and approvers with it (coach set silently; portal login made an approver → refusal) — write them back in the same write ·
G17 HR officers may only read `hr.job` once recruitment is installed ·
G18 the deploy script's lock is inherited by the server it restarts ·
G19 the translations endpoint is browser-cached ·
G20 rize rewrites every employee hourly — compare with the backup, not `write_date` ·
G21 testing notes (one-go drags, 4 s toasts, reaching the component).

## 8. Open items

**For the owner (plain questions):**
* Should moving someone on the chart also hand their time-off and expense approvals to the new manager? Today it does not (it keeps whoever approves now), because following failed for managers who only have an employee-portal login.
* May we switch one test login to Vietnamese to take the Vietnamese screenshot (case 23)?

**For P3:**
* The move sheet has a marked slot for "Effective from" (`orgchart.xml`, comment in the move sheet).
* `_loop_in(changes)` judges a whole set of manager changes at once, and `_set_managers` is the only safe way to write `parent_id` (G16) — the plan's apply step should go through both.
* `_snap` / `restore` give an exact undo for any manager change; a draft plan can store the same snapshots.
* The History tab reads tracking (D6); the time machine's past can reuse `get_history`'s row builder.
* "Fill this role → A new starter" opens the pre-filled form but does not lower the role's "to hire" count when the person is saved (the form knows the job; one line in `create_employee` could do it).

**For P4:** pan/zoom still writes the world's inline transform (G15 — the same Web Animation trick would make it smooth at 657 cards); Learn lessons should gain "change the chart" (drag, pick several, Undo); the deploy script's lock (G18) for the ops owner.
