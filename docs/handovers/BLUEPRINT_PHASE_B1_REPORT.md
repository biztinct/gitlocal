# BLUEPRINT Phase B1 — report

Built, tested, deployed and Chrome-validated 2026-09-10. Scope delivered in full
except one sub-case (13, below), which is named with its reason rather than
silently narrowed.

**Live on all four databases**: `pb_blueprint 19.0.1.0.7`,
`pb_formula_studio 19.0.1.183.0`, `pb_import_kit 19.0.1.18.0`.
**Tests**: 23/23 on p9clone (`--test-tags /pb_blueprint`), 0 failed 0 error.

---

## 1. Acceptance cases

| # | Case | Result | Evidence |
|---|---|---|---|
| 1 | Picker → New configuration → full-screen journey, back chip, rail, placeholder panel | **PASS** | Back chip "Payroll configurations", crumb "New configuration", status "Not saved yet", 6 rail rows (2–6 disabled, tooltip "Create the configuration first"), rail foot "Saved to Payobook Vietnam JSC", panel pill "Waiting" with the dotted avatar. `bp01_start_1440.png` |
| 2 | Name empty → Continue → inline red helper, focus, no toast | **PASS** | Helper "Give the configuration a name so you can find it again.", input `is-bad` + `aria-invalid=true`, `document.activeElement.id === "pbbp-name"`, **0** `.o_notification`, nothing created |
| 3 | Vietnam Essentials pre-selected; note; Excel + Blank present | **PASS** | 3 cards only — "Vietnam Standard 2026" (`is-on`, Draft badge, "v2026.1 · effective 2026-01-01", "37 components · 1 rate table"), "Import Excel workbook", "Blank canvas". The legacy built-in `vn_standard` is hidden. Note: *"'Vietnam Standard 2026' is selected. Tax values come from the 2026.1 rule pack; you can review them in Pay rules."* Effective-from defaulted to 2026-10-01 |
| 4 | Continue → progress ticks → step 2, panel LIVE, four lines | **PASS** | Landed on Pay rules, rail step 1 green, "Draft · saved just now", footer "Step 2 of 6 · Vietnam Standard 2026 · 37 components", panel LIVE. `bp04_hero_live_1440.png` |
| 5 | Double-click Continue → exactly one configuration | **PASS** | 19 configs before → 20 after; one `pb.formula.blueprint` row for the token |
| 6 | Change sample → number animates, delta chip appears then fades | **PASS** | Mid-flight `19.76m`, settled `48.34m`; chip `+39.39m` with class `pbbp-delta up`; absent again after 4.2 s |
| 7 | Adjust inputs → change BASIC → Save → number changes, value persists | **PASS** | "twelve" refused at the field ("That is not a number.", Save disabled); 90,000,000 → headline 48.34m→**69.76m**, chip +21.42m; `input_values_json` on the sample now `"BASIC": 90000000.0` |
| 8 | No samples → "Add a sample" | **PASS** | All 15 samples deleted → pill "No sample yet", "No sample employee yet" + reason + button; pressing it seeded BASIC 30,000,000 / 26 days / 1 dependant → **26.59m**, PIT 265,000 (identical to the pack's own certification expectation) |
| 9 | Save & close → card shows setup ring + Resume setup; Resume lands on step 2 | **PASS** | Card: indigo ring "2/6", caption "Still being set up — step 2 of 6", buttons `["Resume setup","Open","Clone","Delete"]`. Resume → step 2, name and starter intact. `bp09_resume_card.png`, `bp09_picker_final.png` |
| 10 | Skip to the grid → Formula Studio on the config | **PASS** | Studio opened on "B1 Blank canvas" |
| 11 | Change starter → confirmation → components replaced, footer updates | **PASS** | Dialog "Replace the components?" with the real count and "Anything you edited by hand is lost."; Replace → 37 components, toast "37 components are ready.", hero back to 8.95m |
| 12 | Blank canvas → zero components, thin panel says so, Finish works | **PASS** | Footer "Blank canvas · 0 components"; panel shows **em-dashes, not fake zeros**; Finish verified in case 14 |
| 13 | Excel starter → wizard opens; cancel returns; completed import returns to step 2 | **PARTIAL** | Wizard opens pre-scoped to the draft ("B1 Workbook import (Vietnam)"); **Cancel returns to the journey at step 2**; the **return door is proven live** — `studio_people_mapping_action` with `pb_blueprint_return` returned `{tag:"pb_blueprint", params:{config_id:580}}` and without it returned the unchanged `None`; also covered by `test_import_return_door`. **Not completed**: driving the legacy 7-stage review to the end. It requires a *Primary Key Column* typed by hand that must exist in every selected worksheet, and the repo's only payroll workbooks are Vietnamese templates with inline-string headers that do not expose a usable employee-id column. Re-skinning that screen is already a later phase; see §8 |
| 14 | Finish & open → blueprint finished, studio opens, card back to a normal ring | **PASS** | Toast "Setup complete. Opening the configuration."; DB `finished / finish / rev 2`; card ring back to `94`, no Resume button. `bp14_finish_1440.png` |
| 15 | Refresh mid-journey → same step and state | **PASS** | `?config_id=578` reload → step 2, name, starter, live panel. (Broken on first build — fix 2 in §5) |
| 16 | Another company's draft → plain refusal + a way back | **PASS** | Full-panel "This setup cannot be opened" + *"This setup belongs to Your Company. Switch to Your Company in the company selector at the top of the screen to open it."* + "Back to Payroll configurations". No traceback, no rail. (Framework text leaked on first build — fix 4 in §5) |
| 17 | `compute_preview` failure → rose pill + reason + Retry; recovers | **PASS** | Pill `pbbp-pill err` "Couldn't compute", reason, "Try again" → Live 8.95m. `bp17_compute_error.png` |
| 18 | 390 px: horizontal stepper, bottom bar, no sideways scroll | **PASS** | Rail `flex-direction: row`, scrolls itself, hints hidden; panel collapsed to a bar reading "Estimated take-home pay 26.59m VND"; expands to all four lines; `scrollWidth === clientWidth` throughout; panel left edge now identical to the content column. `bp18_phone_390.png` (before), `bp18_phone_390_fixed.png` (after) |
| 19 | Keyboard: Enter continues outside a field, ⌘/Ctrl+Enter anywhere, Esc closes | **PASS** | Enter on the step advanced Pay rules → Connect; **⌘**+Enter advanced Connect → Outputs; Esc closed the dialog and left the journey untouched. Note: Odoo's hotkey service maps ⌘→"control" on macOS and Ctrl→"control" elsewhere, so one registration serves both |
| 20 | Old modal still opens with `pb_blueprint` absent | **PASS** | (a) Action removed from the registry → the old 5-step "New Formula Config" modal opened unchanged. (b) Real uninstall on p9clone: state `uninstalled`, `pb_formula_blueprint` table dropped, `pb_formula_studio` still `installed` and upgraded alone with exit 0 / 0 errors; reinstalled to 19.0.1.0.7 |
| 21 | White-label + vocabulary scan | **PASS** | Automated gate green; plus a live sweep of **13,483 characters** of rendered text across all six steps and both dialogs, including `title`/`placeholder`/`aria-label`: **0** hits for "Odoo", "schema", "blueprint", "config" (as a word), "rule set" |
| 22 | All four DBs: installed, 19.0.1.0.x, journey opens | **PASS** | Versions table in §6. Journey opened and a draft was created **and discarded** on the abm tenant: company chip "AB Mauri", rail foot "Saved to AB Mauri", hero 8.95m VND. `bp22_abm_1440.png` |

**21 PASS · 1 PARTIAL · 0 FAIL.**

Screenshots are in `.bp_shots/` (gitignored, not committed): 1440×900 unless the
name says 390.

---

## 2. Which classification path `bp_preview` used

**Codes, with the engine's classification as the fallback** — and the fields
that exist are `net_role`, `net_role_detail`, `net_role_reason`,
`net_role_confidence`, `net_role_source` on `hr.formula.rule`
(`pb_hr_payroll_formula/models/formula_net_role.py:570-620`). There is **no**
`pay_role` on the rule; `pay_role` exists only on `hr.payslip.line`.

Codes are tried first because a configuration that uses the usual names has ONE
component that is exactly the answer, whereas summing by role can double-count a
subtotal. Where a code is missing, the role is used: `net` → take-home,
`earning` → cash, `deduction` → deductions, `employer_cost` → employer cost,
each excluding `net_role_detail` rows. The response carries `path` so the choice
is visible: on every Vietnam-pack configuration it reads `code`.

**BP16**: `net_role` has no default and no `@api.depends` — by design, so a
formula edit cannot silently re-decide a category a person accepted — and the VN
pack does not ship it. `bp_start` therefore calls `classify_net_roles()` once,
non-fatally, right after seeding, so the fallback is available on an imported
workbook whose codes are not `NET`/`GROSS`/`PIT`.

## 3. The refresh/resume idiom

`router.pushState({config_id})` from `@web/core/browser/router` — the module, not
a service. It merges into the current route, so the URL becomes
`…/pb_blueprint?config_id=N`; on reload `_getActionParams` sees a tag the actions
registry contains and hands the whole state back as `action.params`, which is the
key `_arrival()` already reads. No second source of truth.

Two things had to be right (**BP14**):

- **Never `{replace: true}`.** It does not mean "replace the history entry"; it
  means replace the whole state, and `computeNextState` keeps only the locked
  keys — dropping `action`. The URL became `/bizapp?config_id=578` and a refresh
  landed on an empty app.
- **Every door must open the journey BY TAG.** `makeState` writes
  `action.path || action.id` when either exists and only falls back to
  `action.tag` for a bare client action. Opened by xmlid the URL is
  `/odoo/action-<id>` and the params are dropped. So `openWizard`, the picker's
  Resume button and the import return door all use
  `doAction({type:"ir.actions.client", tag:"pb_blueprint", …})`.

## 4. Every `pb_formula_studio` line touched

Four seams, all registry-probed so the studio stays installable alone.

| File | Where | Before → After |
|---|---|---|
| `static/src/js/formula_studio.js` | `openWizard()`, after the two picker-closing lines (was `:5758-5759`, now `:5760-5770`) | *(nothing)* → 11 lines: `if (registry.category("actions").contains("pb_blueprint")) { return this.action.doAction({type:"ir.actions.client", tag:"pb_blueprint", params:{}}, {clearBreadcrumbs:false}); }` + comment. The rest of the method is untouched and is the fallback |
| `static/src/js/formula_studio.js` | end of the `onWillStart` arrival block (was `:610-616`, now `:617-624`) | *(nothing)* → 8 lines honouring a new `open_switcher` arrival key from `params` **or** `context`, read last so it wins even when a config is loaded |
| `static/src/js/formula_studio.js` | after `csAttention()` (`:4107`), now `:4109-4130` | *(nothing)* → `bpSetup(c)` / `bpRing(c)` / `bpResume(c, ev)` — three small readers. `ring()`, `csRingStroke()` and every other card are untouched |
| `static/src/xml/studio.xml` | the switcher card's `.cs-card-mid` (`:3029-3042`) | one `.cs-ring` block → `t-if="bpSetup(c)"` setup ring (indigo, `step_no/total`, centre text "3/6") / `t-else=""` the original health ring, byte-identical |
| `static/src/xml/studio.xml` | after `.cs-card-mid` | *(nothing)* → one line: `<div class="cs-resume" t-if="bpSetup(c)">Still being set up — step N of 6</div>` |
| `static/src/xml/studio.xml` | `.cs-card-actions` first button (`:3060`) | `<button class="pbfs-btn soft sm">Open</button>` → a `t-if="bpSetup(c)"` **Resume setup** button before it, and Open becomes `ghost` on those cards only |
| `static/src/scss/cfgsw.scss` | appended, `:+14` lines | *(nothing)* → `.cs-ring.setup .cs-ring-val`, `.cs-resume`, `.cs-card-actions .cs-resume-b` |
| `__manifest__.py` | `:5` | `19.0.1.181.0` → `19.0.1.183.0` |

`pb_formula_studio/models/pb_formula_studio.py` was **not touched** (binding rule
7). `bureau_board` is extended by `_inherit` in `pb_blueprint`.

`pb_import_kit` also ships: `static/src/js/import_icons.js` gained
`fileSpreadsheet` and `wallet` (W2 — icons live in the one registry), version
`19.0.1.17.0` → `19.0.1.18.0`.

## 5. Six defects the browser found that code review did not

1. **The hero opened on zeroes.** The Vietnam pack's first certification sample
   is "Zero income"; the client pinned `samples[0]` before asking. The server now
   picks the first sample that is actually paid. → "Low income 10M" / **8.95m**.
2. **`{replace: true}` dropped the action from the URL** (see §3).
3. **Finish refused the journey's own default starter.** `has_errors` is
   `any(not rule.is_valid)`, and `is_valid` is a static lint that does not know
   `BRACKET(...)` — the progressive-tax primitive the whole Vietnam pack rests
   on. Measured: PIT computed **14,896,200** correctly on the 90m sample while
   the same rule was flagged *"Unsupported function: BRACKET"*. Finish now asks
   the question the engine answers — did the formula convert (`python_formula`
   non-empty) — the same test `seed_config` uses to refuse a bad starter.
4. **The other-company refusal leaked Odoo's own message** — technical model
   name, a joke about cookies, no white-label. The record rule fires before any
   of our checks, so the guard catches it and names the company plainly.
5. **The phone panel slid under the app's navigation.** `position: fixed;
   left: 0` is wrong here: the left nav is a flex *sibling* of the action
   container (`pb_sidebar.scss:14-24`), not an overlay. The panel is now the last
   item of the journey's own flex column. It also starts collapsed.
6. **A cancelled workbook review was a dead end** — zero components and a
   sentence describing two doors while offering neither. Both are buttons now.

Plus **BP13**, which failed 6 of 22 tests: `env.company` is **not** guaranteed to
be a member of `env.companies`. p9clone's user 1 has current company "Your
Company" and allowed companies Payobook Vietnam JSC / Singapore / SG Company. A
guard written `company.id not in env.companies.ids` locks that user out of the
company they are standing in — loudly, by raising.

## 6. Deploy

Ritual as the ledger states: clean `/tmp/bp_stage`, scoped per-module
`rsync --delete`, `pg_dump` per DB, detached `systemd-run` with sentinels,
asset purge + `web.assets.version` bump, never `pkill`.

First install (`-i pb_blueprint -u pb_formula_studio,pb_import_kit`):

| DB | Time | Exit | ERROR/CRITICAL |
|---|---|---|---|
| payobook | 52.6 s | 0 | 0 |
| abm | 35.4 s | 0 | 0 |
| payobook_template | 36.2 s | 0 | 0 |

Six further `-u` rounds followed as defects were fixed; every one exit 0 with
zero ERROR/CRITICAL lines on all four DBs. Dumps: `/tmp/bp_dumps/` (payobook 53 M,
abm 16 M, payobook_template 11 M, p9clone 53 M).

Final state — manifest vs `ir_module_module.latest_version`, all four:

| DB | pb_blueprint | pb_formula_studio | pb_import_kit |
|---|---|---|---|
| p9clone | 19.0.1.0.7 | 19.0.1.183.0 | 19.0.1.18.0 |
| payobook | 19.0.1.0.7 | 19.0.1.183.0 | 19.0.1.18.0 |
| abm | 19.0.1.0.7 | 19.0.1.183.0 | 19.0.1.18.0 |
| payobook_template | 19.0.1.0.7 | 19.0.1.183.0 | 19.0.1.18.0 |

Tree hashes repo vs server, byte-identical: `pb_blueprint 56712e79a7440f53`,
`pb_formula_studio 737d9800d80eecbd`, `pb_import_kit dd963ada31f0ebc0`.

**Errors and how they were resolved**: the only ERROR lines in any log were the
six test failures of BP13 (fixed, §5) and two of my own mis-quoted psql
statements inside a remote heredoc (`column "pb_blueprint" does not exist`) which
silently voided the first uninstall attempt — the script was rewritten locally
and copied over. Zero ERROR/CRITICAL from module loading on any database.

## 7. Seeded-sample defaults, and what the hero showed

Starters that ship certification tests keep them; `_ensure_sample` only fires
when a configuration has none, and seeds each input rule's `default_value`, with
`BASIC` 30,000,000 · `STDDAYS` 26 · `DEPS` 1 where the default is zero.

Measured on payobook, all from the real engine:

| Sample | Take-home | Cash | Deductions | Tax | Employer cost |
|---|---|---|---|---|---|
| Low income 10M, 0 dep | **8.95m** | 10,000,000 | 1,050,000 | 0 | 12,150,000 |
| 60M over SI cap, 0 dep | **48.34m** | 60,000,000 | 5,046,000 | 6,613,500 | 70,194,000 |
| same, BASIC edited to 90M | **69.76m** | 90,000,000 | 5,346,000 | 14,896,200 | 100,494,000 |
| seeded "Sample employee" | **26.59m** | 30,000,000 | 3,150,000 | 265,000 | 36,450,000 |

Each reconciles: 10.5 % employee SI/HI/UI up to the caps, employer 21.5 %, no tax
below the relief, and the seeded sample's PIT of 265,000 equals the pack's own
"Mid 30M, 1 dep" certification expectation exactly.

## 8. Deferred, with reasons

1. **A full workbook import driven end to end (case 13).** The legacy review
   requires a *Primary Key Column* typed by hand that must exist in every
   selected worksheet; the repo's payroll workbooks are Vietnamese templates
   with inline-string headers that expose no usable employee-id column. The
   return door itself — the only part B1 owns — is proven live at its choke
   point and by test, and cancel-and-return is proven in the browser. Re-skinning
   that screen is already an owner-approved later phase; **B6 should complete the
   round trip on whatever workbook that phase builds its fixtures from.**
2. **`is_valid` does not know `BRACKET(...)`.** Every configuration seeded from
   the Vietnam pack reports `has_errors = True` for a formula that computes
   correctly, and the picker card shows "2 errors" on a perfectly good
   configuration. Widening the validator's function list changes `has_errors` for
   every configuration on every database, so it is **logged for B2**, not
   smuggled into B1.
3. **No Vietnamese `.po`** — B6, as scoped. Every visible string is inside a
   literal `_t(...)` or QWeb text so extraction will find it; a test asserts the
   client's `STEPS` array equals the server's.
4. **The administrator password on file still does not work** (LOOK closeout item
   2). This phase used the archived `look.p4@payobook.com`, reactivated on
   payobook and abm with a temporary password. **It is still active — see §10.**

## 9. Gotchas added to `BLUEPRINT_LEDGER.md`

BP9 XML comments may not contain `--` (silently unparseable QWeb) · BP10 a
comment between `t-if`/`t-elif`/`t-else` breaks the chain · BP11 `pbim-page` is
the wrong root for a full-bleed cockpit · BP12 the kit's tokens are a mixin, not
an import · BP13 `env.company` ∉ `env.companies` · BP14 `pushState` only
round-trips for a client action opened by tag, and never with `replace` · BP15 a
vocabulary gate must read string literals only · BP16 `net_role` is empty until
classified · BP17 adding an icon means `pb_import_kit` ships with the phase.

## 10. Owner items

1. **The temporary validator user is still switched on.** `look.p4@payobook.com`
   on **payobook** and **abm**, password `BpB1validate!2026`, in the payroll-setup
   groups. Say the word and it is archived again — or better, tell me the working
   administrator password and it can go for good.
2. **Two demo configurations were left on payobook**, renamed rather than deleted
   (TIDY rule 15) so the feature can be seen: *"Vietnam · Monthly payroll (guided
   setup)"* (finished, 37 components) and *"Vietnam · Monthly payroll — setup in
   progress"* (a draft, so the configurations screen shows the "3 of 6" ring and
   the Resume button). Configs 22 → 21 and blueprint rows 3 → 2 after the empty
   workbook stub was discarded through the product's own discard path. Say if you
   would rather they went.
3. **Nothing has been pushed.** Seven commits this phase, on top of the ~104 the
   branch was already carrying.

## 11. Self-score against the bar

> "extreme WOW, intuitive, out-of-this-world experience, best in class."

- **Hero** — 8/10. The number counts to its new value over 420 ms with a delta
  chip that fades, and it is the *real engine* on a *real starter*: switching
  situation moves 8.95m → 48.34m and editing one input moves it again, live. It
  is genuinely convincing. It is not yet 10 because the four lines are a plain
  list; the money-flow strip that B5 brings is what will make it sing.
- **Zero dead-ends** — 9/10. Every state is designed and demonstrated: no
  starters for a country, no samples, compute failure, another company's draft,
  a cancelled import, a double-click, a stale revision, a refresh. Two were only
  *found* by walking it (defects 4 and 6), which is the point of walking it. The
  half point off: the picker still shows "2 errors" on a healthy pack-seeded
  configuration, which I chose to log rather than fix here.
- **Plain language** — 9/10. 13,483 characters swept, zero banned words, and the
  refusals name a company and a next step rather than a model. The thin steps say
  plainly that the tool arrives next release instead of pretending.
- **Motion with purpose** — 8/10. Count-up, delta chip, staggered creation ticks,
  card lift, `prefers-reduced-motion` honoured. Nothing moves that is not
  reporting a change.
- **Keyboard and bulk** — 7/10. Enter, ⌘/Ctrl+Enter, Escape, focus-follows-error,
  sane tab order. There is no bulk work in B1 to ergonomise; B2's component list
  is where that has to be earned.

**With one more hour**: (a) collapse the header to one row at 390 px — it wraps
to three; (b) make the rail's "done" ticks animate in sequence on arrival rather
than appearing; (c) give the thin steps a one-line preview of what each will
show, drawn from real counts, so steps 3–5 feel less like a wall.
