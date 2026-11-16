# WORKFLOW-2 · Phase 6b report — the Studio editor in Vietnamese and Indonesian

## PAUSED (17 Nov 2026, 09:20 AEDT) — owner went offline, coordinator asked for a pause

Nothing was deployed. Nothing on the server was touched. No local Odoo server was started.

**Done (committed as work in progress, NOT reviewed, NOT tested):**
- The previous agent's uncommitted 6b draft is committed as-is on `wf2-p6` so it is not lost:
  - `pb_lifecycle/static/workflow/i18n.js` — global `_t(text, values)`, `_t.n(...)`, `_t.on`, `_t.load(...)`; swaps the one English line in `index.html` before first paint.
  - `pb_lifecycle/controllers/workbench_words.py` — `GET /pb_lifecycle/workflow/words.js` (auth user), builds `{msgid: msgstr}` from `pb_lifecycle`'s `.po` (entries marked `odoo-javascript` with an occurrence under `static/workflow/`), cached by (lang, module version), ETag.
  - `controllers/__init__.py` import; both cache keys bumped to `wf2-p6b` (G11: iframe `v=` in `workflow_studio.js`, inbox/strip keys, and every `?v=` in `index.html`).
  - Phrases wrapped with `_t(...)` in: app.js (48 calls), stages.js (101), steps.js (68), actions.js (29), people.js (28), conditions.js (26), insights.js (23), templates.js (19), graph.js (12), forms.js (9), record-context.js (5).
- Checked at pause: all workbench scripts concatenated in load order pass `node --check` (G73); the controller compiles.

**Not done / half-done:**
- Not wrapped yet: `schedule.js`, `repeat.js` (0 calls each), `drag.js`, `icons.js` (probably nothing visible — confirm). Wrapped files are not yet audited for completeness or for English byte-identity (some sentences were merged into one phrase with named holes, e.g. the wait step summary in app.js — each needs checking).
- Not checked: that `get_po_paths` / `JAVASCRIPT_TRANSLATION_COMMENT` exist with these signatures in this Odoo 19 build; `_t` name collisions across workbench files (one global scope).
- No `.po` entries (vi_VN, id_ID), no tests, no coverage script, no golden-file / pixel-diff proof, no browser screenshots, no version bump (`pb_lifecycle` still 19.0.1.20.0).
- Phase 6c not started.
- Upstream check done: nothing under `pb_lifecycle` changed on `origin/19.1` since P6a; the workbench files last changed in P5c, so the draft sits on current code. `pb_timeoff` and `pb_me_portal` did change upstream (QF3 and later) — relevant to 6c.

**Local environment note:** local PostgreSQL was down after a reboot (stale `postmaster.pid` naming an unrelated process). The file was renamed to `postmaster.pid.stale-20261117`; the brew service was starting up (recovery) at pause time. No test databases were created.

**Exact next step on resume:**
1. Wait for local PostgreSQL to accept connections; pick a base DB (`am_wf2p6a_ui` or similar) and clone it to `wf2p6_*`.
2. Verify `odoo.tools.translate.get_po_paths` and `JAVASCRIPT_TRANSLATION_COMMENT` in `/Users/adity/odoo19/odoo`.
3. Record the English golden files from the pre-draft code (`git stash` is not usable — use a second worktree at `41eeabd73`), then finish wrapping (schedule.js, repeat.js, audit the rest), compare English DOM byte-for-byte, then `.po` vi/id, tests, coverage script, browser proofs, bump to 19.0.1.21.0, commit; then 6c per `WF2_P6C_HANDOVER.md`.
