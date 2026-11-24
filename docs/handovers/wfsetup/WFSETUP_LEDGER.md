# WFSETUP — Workforce Setup Studio: programme + conventions + gotcha ledger

Started 2026-11-24 (Sydney). Owner approved the design prototype and asked for the phased build.

- **Design of record (binding look + behaviour):** `docs/design/workforce-setup-prototype.html`
  (published: https://claude.ai/artifact/Y1uxeNGK1fecJwjG5ShcuN). Open it in a browser before coding any phase.
- **Facts (do not re-derive):** `docs/handovers/wfsetup/WFSETUP_FACTS.md`
- **Worktree / branch:** `/Users/adity/Documents/GitHub/gitlocal-worktrees/wfsetup` on `wfsetup` (from 19.1 @ 8067b4834).
  Never build in the shared checkout — other sessions (Codex `codex/*` branches) ship from it.

## Why (study findings, 2026-11-24)
The live `pb_workforce_workspace` "Set up Workforce" screen is arranged by storage, not by task: 8 tabs / up to 5 sub-tabs /
a third row; every catalogue is the same card of raw field labels; 678 people as cards, 40 a page, no selection and no bulk
action; every record opens the generic premium record form; no visual of a shift or week; steps never complete.

## Phases
| # | Scope | Status |
|---|---|---|
| P0 | Facts doc | done 2026-11-24 |
| P1 | New screen shell (7-step rail, status facade, live-preview panel) + step 1 Shifts + step 2 Working weeks | launched 2026-11-24 |
| P2 | Step 3 Who works what: selection table, team strip, bulk give-a-week / one-off shift / late rule, undo | |
| P3 | Step 4 Late and overtime rules + real live preview calculation | |
| P4 | Step 5 Holidays, step 6 Time clocks, step 7 Check and go live (publish) | |
| P5 | Take over the Settings card, vi/id translations, lessons/tours touched, deploy + browser walk, closeout | |

## Standing rules every handover repeats
1. White-label: the word "Odoo" never appears in any user-visible string. Technical identifiers untouched.
2. Design mandate (verbatim): "extreme WOW, intuitive, out-of-this-world experience, best in class." Hero moment = the live
   "See it on a real person" panel. Zero dead-ends, plain language, motion with purpose, keyboard + bulk ergonomics.
   Lucide icons only, never emoji. One solid primary button per bar. No gradients. Palette = pbim tokens.
3. Plain words on screen: "working week" not pattern, "late rule" not attendance category, "shift" not template,
   never model/field names, never "Tz", "policy", "draft roster rows".
4. Everything done from the backend must be doable on screen (owner 2026-11-19).
5. No new calculation engine and no parallel write path: reuse existing models, validations and ACLs.
6. Commit per feature with explicit paths; never commit credentials; never commit client folders (RIZE/, SUDIMA/, outputs/*client*).
7. Deploy only from the deploy phase, following CLAUDE.md "Deploy contract" + /opt/deploy-notes.md START/DONE. Never abm.
8. On a 429 / session limit: one WIP commit, "Where I stopped" in the report, end with PAUSED.

## Gotcha ledger
(WS1…) — append as hit.

## Owner rulings (2026-11-24, on cards)
- R1 Codex has FINISHED with the Workforce screens — build freely, replace its setup screen. (Still read /opt/deploy-notes.md before deploying.)
- R2 Go live first on **sudima + payobook**; rize / payobook_template / p0clone follow in one batch when the owner says (row in docs/deploy/PENDING.md).
- R3 Trim the daily Workforce menu once setup has its own home: remove Shifts & patterns, Rules & calendars, Connections and the
  card-style People list from the unified workspace tabs; keep Overview, Roster, Timesheets, More. (Phase P5.)
