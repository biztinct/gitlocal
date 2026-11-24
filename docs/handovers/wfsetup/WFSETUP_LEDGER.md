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
| P5a | Take over the old doors, trim the Workforce menu, vi/id wording, lessons check, final pass, step 7 plan once | built + tested locally 2026-11-25 (report WFSETUP_P5A_REPORT.md) |
| P5c | Polish: publish makes the roster day by day (progress in ~3 s), translated Workforce tab bar, numbers in the user's language | built + tested locally 2026-11-25 (report WFSETUP_P5A_REPORT.md, P5c section) |
| P5b | Deploy + live browser walk + closeout | LIVE 2026-11-24 19:48 UTC: setup screen on sudima + payobook, workspace + overtime fix ×5, 551 s down (report WFSETUP_P5B_REPORT.md) |
| P6 | Honest clocks (step 6 states + "Switch clock-ins on", step 7 / finish wording), every Undo redraws the step | see WFSETUP_P6_REPORT.md |

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

- **WS32** Odoo 19 exports translations with `odoo-bin i18n export -c <conf> -d <db> -o <file>.pot <module>` (the old `--i18n-export` option is gone: "no such option -o" means the subcommand is missing). JS strings and XML template text are read from the files on disk, so a code-only change needs no `-u` before re-exporting; resync the `.po` files from the new `.pot` (entries no longer in it drop out).
- **WS33** A Mission lens that hands over to another screen must open it with `stackPosition: "replaceCurrentAction"`, and the button path must be intercepted in `PbMission.setLens` BEFORE `super` runs: `setLens` stores the lens in localStorage, and a remembered hand-over lens bounces every later visit to Workforce. Also clear a remembered `setup` lens on start (`workspace.js` onWillStart).
- **WS34** One-letter weekday msgids (`_t("T")` for Tuesday AND Thursday, `_t("S")` for Saturday AND Sunday) cannot be translated (Vietnamese T3/T5, Indonesian S/K). Use luxon `DateTime.toFormat("ccccc")` of a known Monday-to-Sunday run.
- **WS35** Settings categories: a later module re-registers another module's category with `{ sequence, force: true }` and drops one with `registry.category("pb_settings_category").remove(key)` — the asset order follows the dependency order, so the later module wins. A one-card category opens its card straight away; a `tag` card gets the Settings back chip, an `xmlid` card only the breadcrumb.
- **WS36** A baseline run from a `git archive` snapshot must include `pb_import_kit` next to the snapshot: `test_static.test_s2_every_icon_exists` reads it through the module's parent folder (one false ERROR otherwise).
- **WS37** Inside one test transaction `write_date` is `now()` of that transaction and never moves: a fingerprint built on `max(write_date)` sees a create/unlink (count, max id) but not a plain write. Real requests are separate transactions, so it works live; a test must bump `write_date` by SQL to stand in for "a later request".
- **WS38** `pb_learn` `TestAnchorRegistry.test_05_no_stray_anchors` fails on `19.1` for anchors in other modules (`pb_payrun_wizard`, `pb_payslip_review`, `pb_contracts`, `pb_pay_delivery`, `pb_govt_reports`, `pb_approval_config`) — not this programme's files.
- **WS39** The translation export only sees a LITERAL first argument: a helper `count(text, n)` that calls `_t(text, …)` silently drops those msgids (the screen stays English). Write `_t("%s people", …)` at each call site.
- **WS40** The asset transpiler binds `_t` to the module's own translations only when the import is exactly `import { _t } from "@web/core/l10n/translation";` — DOUBLE quotes and nothing after the semicolon (`js_transpiler.GETTEXT_RE`, `^…require("…");$`). Single quotes or a trailing comment fall back to the global table: whichever module's translation won ("More" became "Selengkapnya", "Field" stayed English) — it can look half-working. Pinned by `pb_workforce_workspace` `test_02`.
- **WS41** Go-live engine work can be split into consecutive day ranges with an identical result only if (a) each range first removes the drafts the engine will take away on the NEXT day (`Eng.plan(next_day)['remove']`) and (b) nobody is on two working weeks on the same day (else one pass, `_live_split_ok`). Each engine call has ~0.6–0.9 s fixed cost: batch ~1,000 shifts per call (one day at 700 people, a week at 120).
- **WS42** Numbers: `toLocaleString()` follows the BROWSER; the web client's `formatFloat` (`@web/core/utils/numbers`) and server `formatLang(env, n, digits=0)` follow the user's language (2.402 / 7,5 in vi and id). Never group years. Locally, signing in on the English login page set the walk users' language to English — switch with the language menu (or `frontend_lang` cookie) before a vi/id walk; a SQL change of `res_partner.lang` needs a server restart (cached user context).

- **WS43** On sudima `base.user_admin` (uid 2) is `hr@sudima.local` WITHOUT Settings rights: `TestP5aPlan.test_05_admin_menu_flag` fails on a sudima copy (it assumes uid 2 is an administrator). Data assumption, not code. A test needing an administrator should create one.
- **WS44** Sudima's six clock connections have `publish_punches = False`: 0 `pb_clock_punch`, 0 `hr_attendance`; the data sits in `pb_clock_connector_event`. The calculation job then marks every published shift "A first and last punch are required." — rehearse a real calculation only on a database with punches.
- **WS45** A database restored on the live box as `IS_TEMPLATE true` is invisible to the live job runner AND the web front; serve it with a separate `odoo-bin` on 127.0.0.1 (`dbfilter` empty, `list_db = True`, `-d <copy>`) through an ssh tunnel (`p5b/wfs_rh_serve.sh`). Chrome MCP screenshots cannot be written outside the tool's own folders: keep them inline.
- **WS46** After Undo of a step 3 "Late rule" change the table keeps showing the applied rule until reload (database is right). Seen live on payobook 2026-11-24. P6: not reproduced on a small local company (the plain path redraws); the reproducible fault was an Undo pressed after leaving step 3 and coming back within the 8 s — the old step's `orm` refused ("Component is destroyed") and nothing was undone. Fixed in the one undo path (WS48).

- **WS47** WS44 drew the wrong conclusion. The late and overtime rules read a PC's received records directly (`pb.clock.connector.event` state `ready`/`posted`/`duplicate`, `pb_attendance_policy/models/policy.py:298-302`) whether or not the connector's "Send accepted records to attendance" (`publish_punches`) is on. With it off, records stay `ready` ("Received. Attendance processing is not enabled for this source."). The switch turns them into ledger punches (`pb.clock.punch`) and legacy pairing (skipped for people on an ACTIVE rule set, `policy.py:578-587`), and switching it on replays every `ready` record already received (`_cron_process`). Sudima's 0 attendance in the P5b rehearsal was because no record was newer than 23 Nov (the PCs read MDBs that the terminals no longer feed), not the switch.
- **WS48** A toast Undo closure that calls a step component's own `orm` (`useService("orm")`) fails with "Component is destroyed" once that step was left — the service is bound to the component. Undos go through the studio (`onToastUndo`, `{method, args, kind}`), which then reloads the step on screen through `registerReload` and the studio data.
- **WS49** pb_clock's own "heard from" rules: a PC is "Contact overdue" after `max(60, 3 × interval_minutes)` minutes (`pb_clock/static/setup/setup.js:53`), a machine is "Silent" after 180 s (`clock_lens.js:435`). Step 6 uses exactly these (P6), so a 15-minute PC reads "Not heard from since 14:05" one hour after its last call.
- **WS50** OWL: focusing the button that opened an inline question from `requestAnimationFrame` runs BEFORE the patch that draws the button again — focus falls to `body`. Return focus from a `useEffect` keyed on the question state (runs after the patch).

## Owner rulings (2026-11-24, on cards)
- R1 Codex has FINISHED with the Workforce screens — build freely, replace its setup screen. (Still read /opt/deploy-notes.md before deploying.)
- R2 Go live first on **sudima + payobook**; rize / payobook_template / p0clone follow in one batch when the owner says (row in docs/deploy/PENDING.md).
- R3 Trim the daily Workforce menu once setup has its own home: remove Shifts & patterns, Rules & calendars, Connections and the
  card-style People list from the unified workspace tabs; keep Overview, Roster, Timesheets, More. (Phase P5.)
