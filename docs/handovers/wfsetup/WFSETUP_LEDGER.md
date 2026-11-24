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
| P1 | New screen shell (7-step rail, status facade, live-preview panel) + step 1 Shifts + step 2 Working weeks | built + tested locally 2026-11-24 (`fd11e1e6a`, report WFSETUP_P1_REPORT.md) |
| P2 | Step 3 Who works what: selection table, team strip, bulk give-a-week / one-off shift / late rule, undo | built + tested locally 2026-11-24 (report WFSETUP_P2_REPORT.md) |
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

- **WS1** CSS prefix `pbws-` is free (grep 2026-11-24) and now taken by `pb_workforce_setup`. Root is `.pbim.pbws`.
- **WS2** An attendance-only user (no `base.group_user`-style company read, as `new_test_user(groups='hr_attendance.group_hr_attendance_officer')` builds it) gets AccessError on `self.env.company.name`. Read the company with `sudo()` AFTER the gate.
- **WS3** `upd_p6_t_tpl` is behind `19.1` code: the registry fails (17 models without a table, `res_company.pb_weekday_location_defaults` missing). Run `-u all` once on the copy (~4 min) before tests or a walk. It also lacks `pb_shift_patterns` / `pb_workforce_workspace` / `pb_form_studio` (installed by depending on them).
- **WS4** Client-action URL state: call `props.updateActionState({step})` in `setup()` as well as on change, and read it back from `router.current` (match `cur.action` against the action id / xml id). Without the setup-time call the first load rewrites the URL without `?step=` and the next reload loses it.
- **WS5** Local walk server keeps serving the old asset bundle after a static edit, even with `?debug=assets`: purge `ir_attachment` `/web/assets/%` and restart (scratch `serve.sh` pattern).
- **WS6** Chrome MCP `drag` sends only the two end points (no pointer path) — test drag-painting with synthetic `pointerdown`/`pointerenter` events; Chrome windows stop at 500 px wide — use `emulate` viewport for 400 px.
- **WS7** Per-row CSS grids with an `auto` column misalign a shared time axis (each row sizes its own column). Use `grid-template-columns: subgrid` on the rows with gutter columns on the card.
- **WS8** `pb.shift.pattern.member._order` is `pattern_id, team_id, id`: compare member id lists sorted in tests.

- **WS9** `pb_attendance_policy`'s roster create hook (`policy.py:241-244`) reads the HR-only `hr.employee.pb_attendance_policy_id` AS THE CALLER: every roster create by an attendance manager without HR rights raises AccessError once that module is installed (15 `pb_shift_patterns` tests, and the live draft engine on Sudima). `pb_workforce_setup/models/roster.py` fills `pb_policy_id` from a sudo read first. Any new roster writer must pass `pb_policy_id` itself or rely on that guard.
- **WS10** Inside the web client a `useExternalListener(window, 'keydown', …)` never receives Escape (the hotkey layer stops it before it bubbles to window). Listen in the capture phase (`{ capture: true }`) and return early while a drawer is open.
- **WS11** Sass evaluates `min()`/`max()` with mixed units (`min(560px, 64vh)`, `min(480px, 100%)`) and fails the WHOLE backend bundle ("A css error occured, using an old style"; server log "Incompatible units"). Write `unquote("min(…)")`.
- **WS12** The Undo toast closes after 8 s: in a scripted walk, Apply and Undo must happen in the same `evaluate_script` call. Chrome MCP `take_screenshot`/`take_snapshot` with `filePath` only accept the MCP workspace roots (not the scratch folder nor the worktree) — keep screenshots inline.
- **WS13** `td { display: flex }` turns the cell into a non-cell and breaks the table; put a flex `div` inside the `td`. Use `table-layout: fixed` + `<colgroup>` so a long name never pushes the last columns out of a ~750 px centre column.
- **WS14** A drawer that focuses its first radio option on open shows a focus ring that reads as a second selection; focus the dialog element (`tabindex=-1`) instead.
- **WS15** "Has a working week" = a member row covering TODAY (P1 case 16). A future start shows "starts <date>" and still counts under "No working week yet"; default the date to today so the team bar fills on Apply.

## Owner rulings (2026-11-24, on cards)
- R1 Codex has FINISHED with the Workforce screens — build freely, replace its setup screen. (Still read /opt/deploy-notes.md before deploying.)
- R2 Go live first on **sudima + payobook**; rize / payobook_template / p0clone follow in one batch when the owner says (row in docs/deploy/PENDING.md).
- R3 Trim the daily Workforce menu once setup has its own home: remove Shifts & patterns, Rules & calendars, Connections and the
  card-style People list from the unified workspace tabs; keep Overview, Roster, Timesheets, More. (Phase P5.)
