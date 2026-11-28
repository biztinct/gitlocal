# WFSETUP P5a — take over the old entry points, trim the Workforce menu, vi/id wording, lessons, final polish

Read first: `WFSETUP_LEDGER.md`, `WFSETUP_OWNER_RULINGS.md` (**R3** drives the trim), `WFSETUP_FACTS.md` sections 0, H, I
(**do not re-derive**), the P1–P4 reports. Worktree `/Users/adity/Documents/GitHub/gitlocal-worktrees/wfsetup`, branch
`wfsetup`. No deploy, no server access (deploy is P5b, a separate handover).

## 1. Scope
1. Every old door into "Set up Workforce" opens the new studio.
2. The unified Workforce menu is trimmed to daily work (R3).
3. Duplicate setup cards in Settings disappear; nothing becomes unreachable.
4. Vietnamese and Indonesian wording for the whole studio.
5. Lessons / tours / help that mention the old screens are brought up to date.
6. A final consistency pass over all seven steps.

### Binding non-goals
- No new features in the seven steps. No calculation changes. No change to what the daily screens (Roster board,
  Attendance & hours, Overtime approvals, Close) do.
- Do not delete the old lenses or the old `WorkforcePanel` code paths other modules import — hide and redirect.
- Do not uninstall or remove any module.

## 2. Plumbing decisions (made)

### 2.1 Takeover (this is the one phase allowed to edit `pb_workforce_workspace`; bump its version)
- Settings: the category `workforce_workspace` (facts §0, `workspace.js:137-143`) keeps its place and label "Workforce setup";
  its card becomes kind `tag` → `pb_workforce_setup_studio` so the back chip returns to Settings (facts H "Settings card"),
  label "Set up Workforce", sub "Shifts, working weeks, who works what, late and overtime rules, holidays and time clocks —
  seven steps, in order." Since `pb_workforce_setup` depends on `pb_workforce_workspace`, do the override from OUR module
  (re-register the category with `{force: true}`) so `pb_workforce_workspace` alone still works where our module is not
  installed (R2: only sudima + payobook get the studio first).
- The old client action tag `pb_workforce_setup` and the Mission lens `setup`: when our module is installed they open the
  studio (re-register from our module with `{force: true}`; the lens entry becomes a thin component that does
  `doAction('pb_workforce_setup.action_setup_studio')`, or simply remove the lens and repoint the "Guided setup" button).
  The **Guided setup** button on the Workforce tab bar stays, labelled "Workforce setup", and opens the studio.
- `PbSettingsHub.openCard` redirects (facts §0, `workspace.js:225-243`) for policies / people / rosters / calendars /
  connectors → point at the matching studio step (`rules`, `people`, `live`, `holidays`, `clocks`) via action context
  `pb_wfs_step`, which the studio reads on open.
- Settings › HR "Attendance calculation" category (registered by `pb_attendance_policy/static/src/js/settings.js:5-21`):
  when our module is installed, remove that category from the registry (from OUR module, no edit there). Its five doors are
  all covered by studio steps. The existing advanced rules screen stays reachable from the studio's rules step (the
  "more than one set of rules" state and a quiet "Advanced rules screen" link at the foot of step 4 for managers).
- The company switch "Use unified Workforce workspace" lived on the old setup screen. It must remain doable on screen
  (owner rule): add it to the studio's top bar as a small "⋯" menu, administrators only: "Workforce menu: Grouped tabs /
  Classic menu", with the sentence "This changes only how the Workforce menu is arranged." It calls the same company write.

### 2.2 Trim the unified Workforce tabs (R3)
In `pb_workforce_workspace/static/src/workspace.js` `GROUPS` (`:19-28`), when `pb_workforce_setup` is installed (detect via
`registry.category('actions').contains('pb_workforce_setup_studio')`), the tab bar is exactly:
**Overview** (Factory overview, Today) · **Roster** (Roster board; "Review roster" stays only if it has rows to show — else
hide it) · **Timesheets** (Attendance & hours, Overtime approvals, Close & send to payroll) · **More** (time off,
approvals, field, insights — as today) · and the **Workforce setup** button.
Removed from the tabs AND from "More": shift library, recurring patterns, people & assignments, attendance policies,
overtime definitions, overtime ceilings, working calendars, holidays, data connectors. Their lenses stay registered (other
screens link to them: the rotation editor link in step 2, "Clock details", the Schedule's Patterns button), they are just
not listed. Without our module installed the menu is unchanged.
Every in-app link that used to land on a removed tab must land somewhere sensible: the Factory overview's "People" /
"Review setup" buttons → studio step 3 / the studio; the Schedule's "Templates" button → studio step 1; the OT desk's rate
link → studio step 4. Grep for `pbWorkforce.go(` and `pb_workspace_section` and list every caller in the report with its new target.

### 2.3 Wording in Vietnamese and Indonesian
- `pb_workforce_setup/i18n/vi_VN.po`, `id_ID.po` and a `.pot`. Follow facts I exactly (three loading rules; parse gate;
  one OWL sentence per line; selection labels; reused msgid must fit). Cover JS, XML templates and Python sentences
  (UserErrors, status texts, toast summaries, holiday suggestion names).
- Sentences with numbers must be built from ONE translatable sentence with placeholders (no concatenating halves), so word
  order can change; plural forms in English handled by two msgids, not by adding "s".
- Tone: plain, the words a Vietnamese / Indonesian HR officer uses ("ca làm việc", "tuần làm việc", "tăng ca", "ngày nghỉ lễ" /
  "shift", "minggu kerja", "lembur", "hari libur nasional"). No English left on screen except product and people names.
  The white-label rule applies to msgstr too.
- Proof: install vi_VN and id_ID on the local test DB, switch the user language, walk all seven steps in each language,
  and screenshot each step. A static test fails on any msgid of the module without a vi and id msgstr.

### 2.4 Lessons, tours, help
Search `pb_learn*`, `pb_coach`, `pb_help*`, tours (`web_tour` registries), and `docs/` user guides for: "Set up Workforce",
"Guided setup", "Shift library", "Recurring patterns", "Rules & calendars", "Connections", "Attendance policies",
`pb_workforce_setup`, `action_workspace_setup`, `pb_workspace_section`. Update every lesson step, selector and screenshot
reference that the takeover/trim breaks (owner standing rule: lessons follow screen changes). If the learning generator
rewrites .po files, restore them (known trap). List what was found, changed, or confirmed untouched.

### 2.5 Final consistency pass (all seven steps)
- One vocabulary: check every string against the ledger's word list; fix strays.
- Every step: loading, empty, error, read-only (officer) states present and consistent; headings, eyebrow "Step N of 7",
  Back / Next buttons behave the same; Next from step 7 absent.
- Keyboard: Tab order sane on each step; Esc closes drawers/confirm panels; focus returns to the trigger.
- The right panel never shows an administrator/system account by default and survives a person being archived.
- First-run experience on an EMPTY company (no shifts, no weeks, nobody assigned, no rules, no holidays, no clocks): walk
  1 → 7 and make sure a new customer can get to "Workforce is live" without leaving the studio once. Fix what blocks it.
- Returning experience on a fully set-up company: all green, step 7 shows the published-to date; opening the studio lands on
  the first step that is not green (or step 7 when all are).
- Remove dead code, console logs and unused CSS left by earlier phases.

## 3. Design bar (verbatim, binding)
"extreme WOW, intuitive, out-of-this-world experience, best in class." Zero dead-ends, plain language, motion with purpose,
keyboard + bulk ergonomics. Lucide via `ic()`, never emoji. One solid primary per bar. No "Odoo" in any user-visible string,
in any language.

## 4. Numbered test cases
1. JS/static: with our module installed the Settings category has one card of kind `tag` targeting `pb_workforce_setup_studio`.
2. Static: `GROUPS` when trimmed lists exactly the four groups; none of the nine removed keys appears in "More".
3. Python: existing `pb_workforce_workspace` suite still green (11); our full suite green; `/pb_attendance_policy` green.
4. Static: every msgid has vi and id msgstr; `PoFileReader` parses both files; the three markers present on every entry;
   no "Odoo" in any msgstr; placeholders (`%s`, `%(name)s`, `{…}`) identical between msgid and msgstr.
5. Static: no user-visible string in the module is built by concatenating translated fragments around a number (grep for
   `_t(…) +` patterns; list exceptions).
6. Lessons: any tour/lesson selector that referenced a removed tab now resolves (run the learning module's own checks).
Browser walk (manager, then officer, then administrator):
B1 Settings › HR › Workforce setup → studio opens, back chip returns to Settings.
B2 Workforce menu shows the four tabs + "Workforce setup"; no removed tab reachable from the bar or from "More".
B3 Each rerouted link from §2.2 lands on its studio step.
B4 Settings › HR shows no "Attendance calculation" cards; advanced rules screen reachable from step 4's foot link.
B5 "⋯" menu (administrator only): switch to Classic menu and back; officers/managers do not see it.
B6 Vietnamese: all seven steps, the three drawers, toasts, a refusal sentence — no English left. Screenshots.
B7 Indonesian: same.
B8 Empty company: 1 → 7 to "Workforce is live" without leaving the studio.
B9 Fully set-up company: opens on the right step; all green.
B10 A database WITHOUT `pb_workforce_setup` installed (uninstall is not required — use a second small DB with only
    `pb_workforce_workspace`): the old menu and old setup screen behave exactly as before. Console clean everywhere.

## 5. Report back (`WFSETUP_P5A_REPORT.md`, committed)
As P1 §5, plus: the table of rerouted callers; the lessons/tours findings; the list of modules and versions changed in the
whole programme (for the deploy handover) with, for each, whether it needs install or upgrade and whether it adds stored
fields. On a usage limit: WIP commit, "Where I stopped", end with PAUSED.
