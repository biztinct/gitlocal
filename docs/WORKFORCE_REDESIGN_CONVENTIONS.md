# Workforce Redesign — Program Conventions & Gotcha Ledger (W-rules)

Program: rebuild the WORKFORCE section as **Option B "Mission Control", staged through Option A's
consolidation, powered by Option C's engine** — per the approved dossier
`docs/WORKFORCE_REDESIGN_OPTIONS.html` (mockups A/B/C + P0–P4 roadmap live there).

Every phase handover in `docs/handovers/WORKFORCE_P*.md` references this file. **Opus: when you hit a
new gotcha or make a binding convention decision, append a numbered W-rule here in the same commit.**
Cross-program rules (deploy ritual, formula-input registry, C18.x gotchas) stay in
`docs/FORMULA_ENGINE_CONVENTIONS.md` — reference them, don't duplicate.

## Program operating model (locked by owner, 2026-08-17)

- **W0.1** Cycle = Fable designs handover → **Opus 5 implements, tests, and self-reviews** → owner says
  "opus done" → Fable designs the next phase. **Fable does NOT code-review Opus's work in this program**
  (owner decision, token economy). Opus therefore owns quality end-to-end: every feature commit ships
  with its tests, and Opus performs an explicit self-review pass (read your whole diff against the
  handover before reporting done).
- **W0.2** Roadmap: P0 foundation → P1 consolidation (Today board + Time hub, 14→7 items) →
  P2 Schedule instrumentation → P3 Mission Control shell → P4 engine (tolerances, locks, ack, pulse).
  Each may split into sub-sessions (P1a/P1b…) — the handover says which.
- **W0.3** Commit-per-feature: one focused commit per work package, explicit file staging,
  reviewer-grade message. Never push unless the owner asks.

## Design-system laws

- **W1 One-accent law.** Every Workforce surface consumes `--pbim-*` tokens
  (`pb_import_kit/static/src/scss/import_tokens.scss`). Allowed identities: the indigo primary
  `#5A4BB0`, or the *promotion of an existing pbim semantic* (precedent: Overtime Desk promoted amber
  `#D97706` / hover `#B45309`). Canonical promoted-green scale (Leave): primary `#2E7D4F`, hover
  `#246A42`, soft `#E3F2E9`. **Never invent a hex.** Chart categorical order (CVD-validated):
  `#5A4BB0 → #D97706 → #2563EB → #DC2668`.
- **W2 Icons.** Lucide only, via `ic()` / the `IC` registry in
  `pb_import_kit/static/src/js/import_icons.js`. New icons are ADDED to that registry — no new
  per-module icon files from P0 onward. Never FontAwesome, never emoji.
- **W3 No gradients on chrome.** Flat fills only. Exception: `conic-gradient` as a *chart* fill
  (donut gauges, e.g. pb_team's compliance donut) is legitimate data-viz, not chrome.
- **W4 Context law.** Department, week and person selection come from the shared `wf_context` service
  (pb_wf_kit). Redesigned surfaces must not ship private department/week pickers.
- **W5 Every record is a door.** No dead-end surfaces: avatars/rows/KPIs open a drawer, popover, or a
  deep-link with a return path. Native-form escapes use `target:"new"` + `onClose` reload
  (Business Trips precedent) — never `target:"current"` with no way back.
- **W6 Kit-first.** Shared UI (context bar, drawer, ribbon, and later dock/popover) lives in
  `pb_wf_kit`. Cockpits import it; they never fork copies.

## Engineering rails

- **W7 i18n.** Every new `.po` entry carries `#. module: <name>` AND a `#. odoo-python` /
  `#. odoo-javascript` marker (Odoo 19 loads nothing without them — C18.74); run
  `msgfmt --check-format` before deploy.
- **W8 Sidebar hygiene.** `pb.sidebar.item` sequences are unique within a section; a sidebar item's
  `groups_id` must match any legacy menu twin's gate. `pb_sidebar/data/pb_sidebar_data.xml` is
  `noupdate="0"` (verified 2026-08-17) — record edits land via plain `-u pb_sidebar`.
- **W9 Testing.** Tests are committed WITH the feature commit, never promised. Never run a bare
  `--test-tags` without a scoping `-u` (C18.40 — legacy om_hr_payroll test imports crash DB init).
- **W10 Deploy.** Follow the established live ritual (Sudima A–M precedent): md5 parity repo↔server,
  scoped `-u`, kill stale odoo-bin before `-u`, stale-assets purge
  (`DELETE FROM ir_attachment WHERE name LIKE '%.assets_%' OR url LIKE '/web/assets/%'` + restart) when
  an OWL change doesn't appear, then **Chrome-MCP validation on the live site is mandatory** before
  reporting done (C18.71: OWL template errors only surface at runtime — `-u` + tests are not enough).
- **W11 Behavior freeze in restyle phases.** A phase marked "pixels only" (P0) touches CSS/SCSS/XML
  templates and explicitly listed data records — no model, facade, ACL, or workflow changes beyond the
  handover's list.
- **W12 Money/security rails.** Never widen sudo; existing gates and the C18 formula-input registry
  are untouchable except where a handover explicitly says otherwise.

## Ledger

- **W13 `noupdate` is per-FILE, and the Workforce sidebar items are spread over seven files.**
  W8 recorded that `pb_sidebar/data/pb_sidebar_data.xml` is `noupdate="0"`. That is only true of
  *that* file. The 14 Workforce items actually come from seven data files, and three of them ship
  `<odoo noupdate="1">`, so a plain `-u <module>` silently does nothing to their records:
  | file | noupdate (before P0) |
  |---|---|
  | `pb_sidebar/data/pb_sidebar_data.xml` | 0 |
  | `pb_hr_workforce/data/pb_sidebar.xml` | 0 |
  | `pb_team/data/pb_sidebar.xml` | 0 |
  | `pb_driver_checkin/data/pb_sidebar.xml` | 0 |
  | `pb_timeoff/data/pb_sidebar.xml` | **1** → flipped to 0 in P0 WP-H |
  | `pb_business_trip/data/pb_sidebar.xml` | **1** |
  | `pb_attendance_flow/data/pb_sidebar.xml` | **1** |
  Rule: before editing any `pb.sidebar.item`, check the *declaring* file's `<odoo noupdate=…>`.
  **And flipping it to 0 is NOT enough on an existing database — see W13.1.**
- **W13.1 `noupdate` lives in the DATABASE, and Odoo never refreshes it. (Proven on the live server,
  2026-08-17 — this cost P0 a second deploy round.)** `ir_model_data.noupdate` is a per-record column.
  `IrModelData._build_update_xmlids_query` (Odoo 19, `base/models/ir_model.py` ~:2425) writes only
  `(model, res_id, write_date)` on conflict — the `noupdate` column is never in the UPDATE list — and
  `Model._load_records` (`odoo/orm/models.py` ~:5163) skips any record whose STORED flag is set:
  `if not (update and d_noupdate): to_update.append(data)`.
  Therefore editing `<odoo noupdate="1">` → `"0"` only changes what a *fresh* install records. On
  every existing database the record stays frozen **forever** and `-u <module>` silently applies
  nothing — no error, no warning, the log looks perfectly healthy. P0 shipped Leave seq 30→32,
  `-u pb_timeoff` returned EXIT 0, and the database still said 30.
  To actually move such a record: flip the file attribute (for future installs) **AND** ship a
  `migrations/<new-version>/post-migrate.py` that clears the stored flag and applies the value —
  bumping the manifest version, since migrations only run on a version change. Precedent to clone:
  `pb_timeoff/migrations/19.0.1.0.3/post-migrate.py`. Keep it idempotent and only overwrite the old
  value, so an admin's later customization is not overruled.
  **Still frozen as of P0** (`noupdate="1"`, untouched because P0 had no reason to move them):
  `pb_business_trip/data/pb_sidebar.xml` (Business Trips) and
  `pb_attendance_flow/data/pb_sidebar.xml` (Attendance Control). P1 renumbers the whole section —
  it must ship the same unfreeze migration for both, or those two items will not move.
  **Always assert the DB value after `-u`.** A repo-only "fix" is indistinguishable from a real one
  unless something reads the database back; that is what `pb_wf_kit/tests/test_p0.py
  ::test_moved_items_landed_on_their_new_sequences` is for, and it is what caught this.
- **W14 A `var()` fallback is a real colour, not a comment.** Surfaces that mount OUTSIDE a `.pbim`
  root — native-form field widgets (`pb_business_trip` trip composer), Leaflet pins rendered at
  document level (`pb_driver_checkin`) — never see the `--pbim-*` custom properties, because those are
  emitted by `@include pbim-root-vars` inside the `.pbim` selector only (`import_kit.scss` :7-8). In
  those files the fallback is what actually paints, so it must carry the correct pbim hex. Corollary:
  `--pbim-primary-soft` **does not exist** in `import_tokens.scss` — the soft indigo token is
  `--pbim-soft`. Referencing the wrong name yields a permanently-fallback colour that looks like a
  theme bug. Check the name against the `pbim-root-vars` mixin before using it.
- **W15 You cannot alpha-suffix a `var()`.** `var(--x, #abc)33` is invalid CSS; the whole declaration
  is dropped silently (found on two live borders in `trip_composer.scss`). Use
  `color-mix(in srgb, var(--x, #hex) 20%, transparent)`. Confirmed safe through Dart Sass — unlike
  mixed-unit `min()/max()`, `color-mix()` passes straight through to the bundle.
