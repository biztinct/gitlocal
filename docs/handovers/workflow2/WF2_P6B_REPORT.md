# WORKFLOW-2 · Phase 6b report — the Studio editor in Vietnamese and Indonesian

**Status: BUILT, NOT LIVE.** Branch `wf2-p6` (worktree `gitlocal-worktrees/wf2-p6`), rebased on `origin/19.1` on 20 Nov (clean, no conflicts: nothing under `pb_lifecycle`, `pb_timeoff` or `pb_me_portal` had changed upstream except one `pb_me_portal` test line). Nothing deployed, no server touched. The 17 Nov pause note is closed by this report.

## 0. In plain words (for the owner)

- A designer whose language is Vietnamese or Indonesian now sees Workflow Studio's own screens in that language: the workflow list, My tasks, Activity, the five views, every step's settings, Try it out, Review, Activity, the Stages sheet, Settings, schedules and "Repeat for each…".
- English screens are exactly as before (checked surface by surface).
- Review's problem list ("Choose an available value and comparison.") and the status, field and group names inside Studio now also follow the reader's language.
- Still in English: the words a designer typed (workflow names, step titles, section names) and what a published version saved when it was published — these are content, not screen text.

## 1. Commits, version

| Commit | What |
|---|---|
| `5ba665483` | (17 Nov draft, rebased) `_t` mechanism, words route, 11 files wrapped |
| `e64d74955` | Wrapping finished (`schedule.js`, `repeat.js`, leftovers), English comparisons kept, read calls carry the reader's language, cache function testable; `pb_lifecycle` **19.0.1.21.0** |
| `eb55701a0` | Vietnamese + Indonesian `.po` entries (workbench phrases + 51 definition-check sentences), `_definition_words` |
| `e85d5ec50` | Studio tests w1–w4, coverage script, golden/screens script, fixture, `.po` merge script, `_t` unit check |
| `143eadb07` | "Next 5 starts" / start history days in the reader's language (`_schedule_day`, babel; English unchanged), test w5; three Indonesian sentences reworded |
| `e6d85aec4` (+ this hash fix) | This report, closeout, ledger, screenshots |

Cache keys (G11/G17): both `wf2-p6b` (iframe `v=` in `static/src/js/workflow_studio.js`, inbox/strip keys, every `?v=` in `index.html`).

## 2. How it works

- `static/workflow/i18n.js` (first script): one global `_t(text, values)` — a plain object lookup, English text as the fallback, named holes `%(name)s`; `_t.n(count, one, many)`; `_t.later()` marks word tables; `_t.on` switches the few English grammar helpers (a/an, ’s, 1st/2nd, plural "s") off in another language.
- `GET /pb_lifecycle/workflow/words.js` (`controllers/workbench_words.py`, `auth='user'`, read-only): `_t.load({...})` with the `pb_lifecycle` `.po` entries marked `odoo-javascript` that have an occurrence on a workbench file, for the signed-in person's language. Files found with the framework's `get_po_paths`, read with polib (the framework reader keeps only the first occurrence). Built once per (language, module version) per process; ETag + `no-cache` (a reload gets 304). English gets an empty dictionary. Loaded synchronously in `<head>` before any screen script, so there is no English flash; the one line in `index.html` ("Opening your workflows…") is swapped as the parser inserts it. If the script fails, the editor works in English.
- Sentences built from parts are one phrase with named holes where English stays byte-identical; the schedule sentences reuse the server's own msgids (`Every %(days)s at %(time)s`, …) so client and server say the same.
- **Read calls carry the language (G97).** The workbench's `rpc()` sent a context with only the company, and the call replaces the context, so everything the ORM translates (status names, field labels, group names) came back English even though the server's `_()` sentences were translated. Read-only calls (`RPC_READS` in `app.js`, 23 methods) now add `lang`; saving calls and the email template editor (`template_detail`, `template_preview`, `save_template`) do not, so what is saved never depends on the designer's language. English readers send `en_US`: proven identical by the golden files.
- **Schedule days.** "Next 5 starts" and the start history printed the day with `strftime` (English); `_schedule_day` now uses babel's short day in the reader's language, English byte-identical.
- **Definition checks (G100).** The 51 fixed sentences of the pure `workflow_definition.validate` were English constants; `_definition_words` (in `workflow_studio.py`) passes each through `_()` at the boundary (Review and the save refusal). Codes untouched (G2).

## 3. Phrase counts per file

`node tools/workflow_studio/p6b_words.cjs coverage --po-dir pb_lifecycle/i18n`. Before = the code at `9cedc9249` (no mechanism: every phrase English in both languages).

| File | phrases | `_t` calls | English left (vi / id) before → after | allow-listed (not text) |
|---|---|---|---|---|
| app.js | 260 | 285 | all → 0 / 0 | 4 (HTML entities) |
| stages.js | 206 | 234 | all → 0 / 0 | 2 (form paths) |
| steps.js | 123 | 136 | all → 0 / 0 | 10 (saved-English comparisons, selectors) |
| schedule.js | 106 | 123 | all → 0 / 0 | 0 |
| repeat.js | 94 | 115 | all → 0 / 0 | 8 (CSS, a comparison) |
| actions.js | 80 | 87 | all → 0 / 0 | 3 (console text, paths) |
| forms.js | 69 | 74 | all → 0 / 0 | 0 |
| templates.js | 67 | 73 | all → 0 / 0 | 2 (preview CSS, `{{ object.`) |
| people.js | 53 | 55 | all → 0 / 0 | 0 |
| insights.js | 52 | 54 | all → 0 / 0 | 2 (CSS) |
| conditions.js | 47 | 51 | all → 0 / 0 | 0 |
| graph.js | 34 | 39 | all → 0 / 0 | 7 (CSS) |
| record-context.js | 29 | 29 | all → 0 / 0 | 0 |
| drag.js | 2 | 2 | all → 0 / 0 | 0 |
| icons.js | 0 | 0 | — | 0 |
| **distinct** | **1,135** | | **0 / 0** | |

The handover's estimate of ~466 counted distinct sentences roughly; the real set (every label, aria-label, toast, option, grammar variant) is 1,135. `.po`: 1,007 new Vietnamese and 1,017 new Indonesian entries; 128 / 118 phrases reuse an existing server entry (the `odoo-javascript` marker and the workbench occurrence were added after its `#. module:` line; its translation kept). Plus 51 definition-check sentences per language (`odoo-python`). Text edits only (no re-export): `git diff --numstat` 0 lines removed, except one: Vietnamese "People" was "Số người" ("number of people"); its only use is the Studio view tab, now "Người thực hiện". No `.pot` exists in `pb_lifecycle` (none was created: a `.pot` filters its `.po`). Parse gate (`PoFileReader`): both files pass. No "Odoo" in any msgstr. Translations used P5b's glossary (`WF2_P5B_REPORT.md` §3) and the existing server entries as the vocabulary.

## 4. Tests

- **Studio suite** (`tools/workflow_studio/run_suite.py`, rolled back, `wf2p6_suite2` = local copy upgraded to this branch): **165/165** (160 + w1–w5). Baseline after the rebase, before any 6b work: 160/160 (the 152 of P5b + 8 of P6a). New:
  - w1 dictionary holds only workbench phrases, right language, English empty, a Python-only sentence not served, a shared sentence served with the server's words;
  - w2 every translation keeps its holes and tags, no banned word (both languages, all entries);
  - w3 built once per (language, version), plain-ASCII script, different ETag per language/version, the route needs a signed-in person (`auth='user'`: the public gets the login redirect, never words);
  - w4 definition checks: codes and English kept; every fixed sentence translated in both languages;
  - w5 "Next 5 starts" days: English exactly as before, the reader's weekday/month otherwise.
- **`_t` unit** (`node tools/workflow_studio/p6b_i18n_unit.cjs`): 19/19 — English identity, holes, a missing phrase stays English, unknown hole left as written, no double filling, `_t.n`, `_t.later`, broken payload → English, no prototype lookups.
- **Approvals suite** (`--test-tags /pb_approval_config`): 173 tests, **the known 4 failures exactly** (`test_the_look_invents_no_colour_and_carries_no_gradient`, `test_u13_…`, `test_z06d_…`, `test_z06e_…`; closeout §4), nothing new.
- Time-off suites: see `WF2_P6C_REPORT.md` §5 (6c's work; 6b does not touch time off).
- All workbench scripts concatenated in load order pass `node --check` (G73); `_t`, `RPC_READS`, `schedNth`, `SCHED_MONTHS_SHORT`, `schedReviewCount` declared once.

## 5. English unchanged (golden files) and pixels

`tools/workflow_studio/p6b_golden.cjs` on a local copy with `ui_fixture_p6b.py` (44 workflows: every step type, a repeat over time-off days — running — and over a list question, weekly and monthly schedules, a record-date start, a field-change start). It serves the workbench files itself (pre-phase files from `9cedc9249`, or this branch's), so no browser cache is involved (G17), and walks every surface: list, My tasks, Activity, a progress page, a task page, and per workflow the five views, the inspector of every step and of the start, Try it out, Review, Activity, Stages, Settings.

Result (final code, server restarted, captured back to back): **522 surfaces, 0 differences** (`GOLDEN surfaces=522 differ=0`); the four canvases (Journey, By stage, Across, Flowchart) of two drafts: **8 screenshots, 0 pixel differences**. Console errors 0 in both runs. The only difference ever seen (an earlier run) was a progress page's "Updated 15:03 / 15:16" — the run itself had been touched between the two captures; the comparison now masks that one timestamp.

## 6. Vietnamese and Indonesian on screen

Same walk as a Vietnamese and an Indonesian login: every one of the 522 surfaces drawn in Vietnamese and in Indonesian at 1280 px and at 390 px — **0 console errors, 0 clipped buttons/chips/labels** (the script checks every visible button, pill, chip and label for cut-off text). Workbench phrases left in English on screen: **0** (the remaining English text is designers' own words, the fixture's saved step titles/buttons, and other modules' group names such as "Announcements officer", which have no Vietnamese/Indonesian in their own module). Two translation fixes came from looking at the screens: Vietnamese "People" (§3) and three Indonesian sentences that started with a lower-case word. At 390 px the longer Vietnamese button "Tạo quy trình" wraps to two lines like the English one does; nothing is cut. Screenshots in `p6b_screens/` (`vi_`/`id_`, `1280_`/`390_`), all looked at. Speed: first paint of the Studio (local, to the first drawn screen, median of 6 loads, two rounds): before 200–234 ms, after 234 ms in English and 250 ms in Vietnamese — within the +100 ms budget (one extra small request, 304 after the first). The words script is 109 KB (vi) / 76 KB (id) uncompressed, built once per process and answered with 304 afterwards; the backend's own translation download for a vi/id login grows by the same entries (G98: 108 → 1,226 `odoo-javascript` entries in vi).

## 7. Deviations from the handover

1. **1,135 phrases, not ~466** (§3).
2. **Read calls now carry the reader's language** (§2, G97) — needed for the editor to be in the reader's language at all (status, field and group names); writes unchanged. Not in the handover's list; behaviour for English readers proven identical.
3. **51 server sentences translated** (`workflow_definition.py` checks, G100) — server words P5b had not covered; shown on Review.
4. **Schedule days** in the reader's language (`_schedule_day`, server) — the dates under "Next 5 starts" were English in every language.
5. No `.pot` (none exists; creating one would filter the `.po`).
6. Golden pixel comparison: the four canvases of two drafts compared as screenshot hashes (identical), not a fuzzy diff.
7. Deploy not done (this run is build-only, owner's word); go-live in §10.

## 8. Still English, and why

- **Words a designer typed or a version saved**: workflow and step names, section names ("Prepare / Do the work / Finish" of a new workflow are saved in the designer's language at creation), button labels, notes; and on a progress page the stage and line words saved with the published version ("0 of 5 days"). Content, not screen text.
- **Sentences built with a name inside** in the definition checks (`“%s” cannot sit inside work in parallel…`, 4 of 55) — formatted in the pure module before the boundary.
- **The email template editor** reads and saves without a language on purpose (§2); its labels are translated, the template's own text is the designer's.
- **Area/module labels saved on a workflow** ("Time off", "Expenses" on the list cards) — saved text.

## 9. Overlaps found (R2a)

None. One mechanism, no framework; the dictionary is the module's own `.po`; server sentences are reused, not translated twice.

## 10. Go-live (with 6c, one outage; only on the owner's word)

**Modules:** `-u pb_lifecycle,pb_timeoff,pb_ess_workforce` (6c's two where installed — check `ir_module_module` per database first). `pb_lifecycle` cascades to its 14 dependents (G29/G70); `pb_me_portal` needs no `-u`.

**Databases:** payobook, payobook_template, p0clone, rize, sudima (sudima last; its Studio job stays off, D11). **Never abm.**

**Steps** (procedure of `WF2_P6B_HANDOVER.md` §4 / P5b):
1. Read `/opt/deploy-notes.md` (no open START from another session in the last 12 h, G14); append START "Claude WORKFLOW-2"; `flock` read-only (G9); one service process by `ps` (match `odoo-bin -c /etc/odoo-server.conf` only, G62).
2. `pg_dump` all five (6c adds two columns and a unique index to `hr_leave`); run 6c's read-only pre-count (`WF2_P6C_REPORT.md` §4) per database; snapshot active cron id lists and mail/outbox/to-do counts.
3. Clean staging; `git archive` the three modules; scoped `rsync -a --delete` per module into `/odoo/odoo-server/addons/<m>/` with a before-tarball; **parse gate** on the server for the touched `.po` files (`pb_lifecycle` vi/id, `pb_timeoff` vi/id, `pb_ess_workforce` vi/id).
4. Stop the service; `-u` per database with `--no-http --max-cron-threads=0` (G9); 0 ERROR; job id lists identical (G53), sudima job still off; message deltas read (G64).
5. Per database `INSERT INTO orm_signaling_assets DEFAULT VALUES; DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'`; start; one process; warm each site.
6. Verify: tree hashes equal the repo; `latest_version` pb_lifecycle 19.0.1.21.0 (+ 6c's) on all five; on p0clone fetch `/pb_lifecycle/workflow/words.js` as a vi and an id login and count entries (1,135 each); Studio suite on p0clone (rolled back); 6c's migrate log count equals its pre-count. Browser check with the QA login on payobook (English Studio unchanged).
7. DONE line in the notes file.

**Stored values to fix by hand:** none for 6b (code translations load from the `.po` at runtime, G81 — the upgrade log line "no translation for language" is expected). 6c: none (its report §11).

**Never** create, approve, move, grant or send anything on a live site.

## 11. Gotchas (ledger G97–G100)

See `WF2_LEDGER.md`.
