# WORKFLOW-2 · Phase 6b handover — the Studio editor in Vietnamese and Indonesian

Designer: Claude (Fable), 14 November 2026. Implementer: Opus agent, same session. Runs after phase 6a is live.
Owner instruction (14 Nov): "finish off all the remaining items" — this is closeout item 1.

Read first: `WF2_LEDGER.md` (binding; esp. G11/G17 two cache keys, G73 workbench scripts share one scope, G81–G83); `WF2_CLOSEOUT.md` §3 item 1; `WF2_P5B_REPORT.md` (the `.po` rules, the golden-file "English unchanged" method, the glossary used — reuse it exactly); `WF2_P6A_REPORT.md` (what it touched in the workbench); then this file. Target: `pb_lifecycle` next minor version after 6a.

White-label (binding): "Odoo"/"OdooBot" never visible, in any language. Plain words (R8) in every language.

## 1. What to build
The workbench (`pb_lifecycle/static/workflow/*.js`, an iframe app of classic scripts, ~466 distinct English phrases; largest `app.js`, `steps.js`, `people.js`, `stages.js`; `repeat.js` ~29, `schedule.js` ~22) and the OWL wrapper have no translation mechanism.

1. **One tiny mechanism, no framework.** A `t(text, values)` in the workbench that looks the English phrase up in a dictionary and falls back to the English text; placeholders by name. The dictionary is served once per load by a small controller (auth user, cached by language + module version) built from the module's own `.po` — entries marked `#. odoo-javascript` with occurrences on the workbench files (`code_translations.get_web_translations('pb_lifecycle', lang)` or the build's equivalent: verify what this build exposes; do not hand-roll a `.po` parser if the framework has one). The language is the signed-in person's. The dictionary must be loaded **before** first paint (no flash of English, no layout jump); if it fails to load, the editor works in English and says nothing.
2. **Wrap the phrases file by file.** Every visible string: labels, buttons, placeholders, titles/tooltips, aria-labels, empty states, confirmations, toasts, canvas labels (measure text after translation — Vietnamese runs ~20–30% longer: no clipped button, chip or canvas node at 1280 px and at 390 px). Sentences built from parts become one phrase with named placeholders (word order differs per language) — but only where the English output stays byte-identical.
3. **Server sentences already translated in P5b** are shown as returned; do not translate twice.
4. **Translate** all phrases to `vi_VN` and `id_ID` with P5b's glossary; `.pot` too; three markers per entry; never regenerate a `.po`; parse gate.
5. **English byte-identical.** Golden-file proof per canvas and panel (Journey, By stage, Across, Flowchart, People, Stages, Settings, Try it out, Review, Activity, My tasks, inspector of each step type incl. repeat and schedule): rendered text and DOM identical before/after in `en_US`. Pixel-diff the four canvases for two shipped drafts.

## 2. Rails
- No behaviour change, no restyle (R1), no new job, no schema change. Performance: first paint of the Studio no slower than +100 ms (report numbers); `t()` is a plain object lookup.
- Workbench scripts share one scope (G73): one global name for the mechanism, checked against collisions. Both cache keys bumped (G11/G17): `wf2-p6b`.
- Live: never create, enable, start, approve, move, grant or send anything. Never `abm`. Other sessions' files are not yours; explicit paths in commits; no credentials.

## 3. Tests and proofs
- Unit: dictionary endpoint returns only workbench phrases, right language, cached, refuses the public; missing phrase → English; placeholders preserved in every msgstr (script).
- Coverage script: every string literal that reaches the DOM in the workbench files is either wrapped or on a short allow-list (names, symbols) — report the remaining-English count per file per language (target 0).
- Browser (local, a `vi_VN` login and an `id_ID` login; remember G82): screenshots of every canvas and panel listed in §1.5 in both languages at 1280 px and the main ones at 390 px; console clean; no clipped text.

## 4. Deploy and verify
As P5b: notes file START/DONE "Claude WORKFLOW-2" (re-read before START; wait for other sessions; one service process by `ps`), flock, clean staging, scoped rsync with before-tarball, parse gate on the server, `-u pb_lifecycle` ×5 (payobook, payobook_template, p0clone, rize, sudima last; G80 holds on rize), job lists and mail/outbox/to-do counts identical, sudima Studio job off, asset purge ×5, restart, one process, warm, hashes + `latest_version` ×5, 0 ERROR. On p0clone after the upgrade: fetch the dictionary as a vi and an id login and count entries.

Commit per feature. Do not push.

## 5. Report back (`WF2_P6B_REPORT.md`)
Commits, version; phrase counts per file per language before/after; proofs; timings; deviations; gotchas; update `WF2_CLOSEOUT.md` §3 item 1 in place and add a short "Phase 6" section (what 6a and 6b closed, what remains and why).
