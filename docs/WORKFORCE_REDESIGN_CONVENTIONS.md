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

- (append W13+ here as gotchas are hit)
