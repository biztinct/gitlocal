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
| P3 | Step 4 Late and overtime rules + real live preview calculation + automatic holiday/rest-day marking | built + tested locally 2026-11-25 (report WFSETUP_P3_REPORT.md) |
| P4 | Step 5 Holidays, step 6 Time clocks, step 7 Check and go live (publish) | built + tested locally 2026-11-25 (report WFSETUP_P4_REPORT.md) |
| P5a launched 2026-11-25; P5b = deploy | Take over the Settings card, vi/id translations, lessons/tours touched, deploy + browser walk, closeout | |

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

- **WS16** `resource.calendar.leaves`: `company_id` is COMPUTED from `calendar_id` (no calendar → the acting user's company), and the stock create shifts public-holiday times into the acting user's time zone. Tests and seeds must do what `pb.holidays._create_row` does: `calendar_id` = the company calendar, create a century out, then `write` the real UTC bounds. Otherwise the holiday lands on the wrong company or the wrong day and `_pb_holiday_map` never sees it.
- **WS17** The backend bundle carries a global `[type="number"], [type="text"] … { display: block; width: 100% }`. An input inside a sentence must say `display: inline-block` itself.
- **WS18** A number box that is half typed ("0.") reports `value === ""`. Never write `NaN`/empty back into reactive state from `t-on-input`: OWL re-applies `t-att-value`, wipes the box and "0.5" became "50" in the walk. Leave the stored value alone, mark the box, block saving until it holds a number (`step_rules.js num()/pending()`).
- **WS19** `hr.overtime.config` rates are live for every overtime request the moment they are written. A screen that edits rates as part of a draft / "new version" must hold them on the draft (`pb.attendance.policy.pb_pending_rates`) and apply them on Confirm; otherwise "the current rules stay in use until you confirm" is false and Discard cannot undo.
- **WS20** Rate rows are picked by the PERSON's nationality (`hr.employee.country_id`, HR-only), not the company's country; a person with no nationality only ever matches rows without a country. The one resolver is `hr.overtime.config._pb_pick` (pb_hr_workforce 4.25.0): company+country > company > country > global. A company row WITHOUT a country is the row that reaches everyone in the company.
- **WS21** `engine.calculate` does not apply the clock window; `_policy_calculate` drops punches outside `start − capture_before … end + capture_after` first. A hypothetical example must apply the window itself or it pays punches the real job ignores.
- **WS22** Web client `_t()` / sprintf has no `%%` escape: write "150 %" with a template string, not `_t("%s %%")`.
- **WS23** Active rule sets are immutable, but a shift's times are not: changing a shift in step 1 while rules are in use can leave an ACTIVE per-shift line that no longer fits (the calculation then refuses that shift). `rules()` flags it per line; the fix is Change the rules → Confirm. Draft lines are re-synced automatically.

- **WS24** Never set the studio's reactive state (e.g. the bar button) from a step's `onWillStart` path: the studio re-renders before the step is mounted, OWL makes a NEW step whose `willStart` loads again — an endless RPC loop (seen: `holidays()` every 30 ms). Set parent state from `onMounted` on (`this.mounted` guard).
- **WS25** `pb.holidays.add / add_many / remove` gate on `env.user` groups (`pb.timeoff._require_officer`); `sudo()` keeps `env.user`, so an attendance manager is refused even with sudo. Behind our own gate call `_create_row` (and `_forget_demo` + unlink for removal) with sudo. `add` stores kind `public` (field default).
- **WS26** The pattern engine skips a wanted day only when an existing shift OVERLAPS it in time: a night one-off on a day-shift day gets the day shift added back ("refilled"). Go-live filters those creates out of the plan and deletes the ones `apply` just made on hand-decided days.
- **WS27** `pb.shift.patterns.preview / make_drafts` snap the start to Monday; the engine then REMOVES this week's untouched drafts on past days (past days are never wanted). Call `engine.plan / apply(patterns, today, last)` to leave the past alone.
- **WS28** `hr.shift.planning.state` is tracked: publishing thousands of rows without `tracking_disable` writes one chatter line per row. Publish with `tracking_disable=True, mail_notrack=True`.
- **WS29** A container `keydown` handler that `preventDefault`s Enter (a calendar grid) also swallows Enter on buttons inside it (an inline question strip). Act only when `ev.target` is a day cell.
- **WS30** The attendance settings screen (`hr_attendance.action_hr_attendance_settings`, `res.config.settings`) needs administrator rights — never a door for an attendance manager.
- **WS31** The stock public-holiday create is heavy: 10 suggested days = 449 queries / 4.6 s. Show busy state; never loop `add_day_off` per day from the client. Chrome MCP `wait_for` returns the WHOLE accessibility snapshot (12 calendars = 500 nodes) — poll with `evaluate_script` instead.

## Owner rulings (2026-11-24, on cards)
- R1 Codex has FINISHED with the Workforce screens — build freely, replace its setup screen. (Still read /opt/deploy-notes.md before deploying.)
- R2 Go live first on **sudima + payobook**; rize / payobook_template / p0clone follow in one batch when the owner says (row in docs/deploy/PENDING.md).
- R3 Trim the daily Workforce menu once setup has its own home: remove Shifts & patterns, Rules & calendars, Connections and the
  card-style People list from the unified workspace tabs; keep Overview, Roster, Timesheets, More. (Phase P5.)
