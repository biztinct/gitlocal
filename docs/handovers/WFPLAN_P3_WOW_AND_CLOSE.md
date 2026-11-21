# WFPLAN Phase 3 — "Wow and close": motion, phone, Vietnamese, Home, closeout

Read `docs/handovers/WFPLAN_LEDGER.md` FIRST and fully (rules, credentials incl. the WF15
addendum with the archived abm validator logins, plumbing, gotchas WF1–WF22, deploy
ritual), then `WFPLAN_P1_DECISION_ROOM.md` and `WFPLAN_P2_LOOK_CLOSER.md` for what is
live. Phases 1 and 2 are COMPLETE (`pb_decision_room` 19.0.2.0.0 on p9clone, payobook,
abm, payobook_template). This phase finishes the product and writes the closeout.

## 0. What you are building, in one paragraph

Nothing new is invented in this phase; what exists is made finished. The room gets the
last of its motion (the demand picture and the bridge animate between states, the year
strip breathes when a month changes), a phone layout a CEO can actually use on the way
to a meeting (stage first, levers in a bottom sheet, month strip that scrolls), full
keyboard reach, Vietnamese for every word on the screen and in the brief, a "Decision
Room" lens on the Home hub so the owner reaches it in one press, the "one small
experiment" card scaled to the team so it is always a real question, and a closeout
document that tells the owner exactly what is live, what it cost, what they still have
to decide, and how to use it. The "Classic planning tools" fold stays — retiring it is
the owner's call and the closeout puts that decision in front of them.

## 1. Scope and binding non-goals

Deliverables:
1. `pb_decision_room` 19.0.3.0.0 (§3–§7), `pb_hub` bump (feature map for the Home lens),
   `pb_import_kit` bump only if an icon is missing.
2. `pb_decision_room/i18n/vi_VN.po` complete (§5), loaded on every DB (both DBs have
   `vi_VN` active).
3. Tests T37–T50, browser walks B25–B36, deployed and verified on p9clone, payobook,
   abm, payobook_template.
4. `docs/handovers/WFPLAN_CLOSEOUT.md` (§8), ledger phase log + gotchas (WF23+),
   feature-scoped commits, phase report (§9).

Non-goals (do NOT build):
- No new levers, tabs, models or facade reads beyond what §3–§6 name. No PDF engine.
- Do not retire, hide or reword the "Classic planning tools" fold. Do not touch
  `pb_hr_workforce_planning/`.
- Do not delete the owner's data on payobook: the "Board draft" plan and the ₫2,200B
  target on company 5 stay (listed as owner debts in the closeout). abm stays as found.
- Do not change the owner's passwords. Reactivate the archived abm validator users for
  browser walks and archive them again when done.

## 2. Design (the bar, the hero of this phase)

**The bar (owner's words, verbatim): "extreme WOW, intuitive, out-of-this-world
experience, best in class."** Hero of this phase: **the phone.** Open People → Plan on a
390 px screen and the dark stage fills the first view: the big number, the line, the
month scrubber. One thumb-reach bar at the bottom — "Shape your plan" — lifts a sheet
with the levers; drag a slider and the stage behind it moves. This is the CEO-in-a-taxi
moment. Second hero: **Vietnamese** — the same room, every sentence, in the language of
the company that runs it, with money read the way Vietnamese finance reads it
(₫2.200 tỷ, 840 triệu).

Motion with purpose only: the demand picture's three lines tween to their new shape
(300 ms, ease-out) instead of snapping; the bridge bars grow from the running level on
tab open; a changed month card pulses once. Everything obeys "Motion off" and
`prefers-reduced-motion`. No decorative jitter.

Keyboard: impact cards are buttons (`Enter`/`Space` opens the tab); tabs are a
`role="tablist"` with `←/→` and `Home/End`; sliders take `←/→` (1) and `Shift+←/→` (10);
the month scrubber takes `←/→`; `Space` toggles play when the timeline has focus; `Esc`
closes sheet and dialogs (capture phase, WF4); `⌘Z` undoes; `⌘S` saves (opens the name
dialog); focus rings visible on every control (`:focus-visible`, 2 px `#5A4BB0` ring on
light, `#CBC2EE` on the dark stage).

## 3. Finishing the room (cockpit + scss + engine)

- **One small experiment scales to the team**: `n = max(5, round(team.heads × 0.01))`,
  rounded to the nearest 5 above 20. Copy: "Twenty more people in Manufacturing would
  add ₫X of profit." The engine's `marginal()` takes `n`; the button reads "Preview N
  more people". (Phase 2's own first-improvement.)
- **Demand picture tween**: keep the previous series; on change, interpolate 300 ms via
  `requestAnimationFrame`; skip when motion is off. Same for the bridge on open and the
  room-to-hire line on team change.
- **Month card pulse** on the selected month change (scale 1 → 1.04 → 1, 240 ms).
- **Phone layout (≤ 720 px)**: order = page heading (compact: title + Undo/Save icons),
  goal compass (pills scroll horizontally), stage (canvas 200 px, hero ≥ 40 px), year
  strip (horizontal scroll with snap, selected month centred), story, impact cards
  stacked, detail workspace (tabs scroll), stress, dock (table scrolls inside itself,
  actions sticky right per WF6). The control room becomes a **bottom sheet**: a fixed
  bar "Shape your plan · <scene name>" with `sliders` icon; tap → sheet slides up to
  85 vh with a grab handle, scrolls inside, has "Done"; backdrop tap / Esc closes; the
  stage stays visible above the sheet's top edge at 85 vh? — no: at ≤ 720 px the sheet
  covers, so **the hero number and delta pill are mirrored in the sheet's header** so a
  lever's effect is visible while dragging. Sheet state is per-session only.
- **Tablet (721–1100 px)**: control room stacks above the story as today; nothing else.
- **Focus + keyboard** per §2. Add `aria-live="polite"` to the story caption (exists?
  verify) and to the preview banner.
- **Money formatter, Vietnamese words** (`decision_format.js`): `makeFormat(cur, lang)`
  — when `lang` starts with `vi`: compact suffixes `nghìn` (10³), `triệu` (10⁶), `tỷ`
  (10⁹), thousands separator `.` and decimal `,` (₫2.200 tỷ · ₫840 triệu · ₫12,5 triệu);
  `parseCompact` accepts `tỷ/ty/triệu/trieu/nghìn/nghin` and k/m/b/t in either
  language. The room reads `user.lang` (`@web/core/user`). Node checks cover both.
- **Brief in Vietnamese**: the QWeb brief is rendered in the user's language (`_()`
  strings in the template + the client's formatted numbers); date in the user's
  locale.

## 4. The Home lens

- `decision_palette.js`: `registry.category(HOME_LENSES).add("decide", { key:
  "decide", icon: "target", label: _t("Decision Room"), Component: PbDecisionRoom,
  groups: DECISION_GATE, feature: "people_plan" }, { sequence: 30 })` — import
  `HOME_LENSES` from `@pb_home_hub/js/home_hub` (precedent `pb_rnr/static/src/js/
  rnr_palette.js:69-76`). Add `pb_home_hub` to the manifest `depends`.
- `pb_hub/static/src/js/hub_features.js`: add `"pb_home_hub#decide": "people_plan"` and
  `"pb_home_hub.action_pb_home_hub#decide": "people_plan"` (check the exact xmlid of the
  Home action in `pb_home_hub/views/`). Bump `pb_hub`.
- The component must render identically whether mounted from People (Plan hero slot),
  Home (lens) or the deep link; the lens memory keys differ per hub, nothing else.
- ⌘K: the existing "Decision Room" row keeps opening the People hub (one door in the
  palette, not two).

## 5. Vietnamese (`i18n/vi_VN.po`)

- Export the template: on p9clone,
  `odoo-bin -c … -d p9clone --i18n-export=/tmp/pb_decision_room.pot --modules=pb_decision_room --stop-after-init`
  (spare ports), copy back to `i18n/pb_decision_room.pot`, then write `vi_VN.po` with
  EVERY msgid translated — templates, JS `_t()`, model `string=`/`help=`, selection
  labels, constraint/error sentences, the brief, the assumption sentences, the group
  names. Precedent for tone and register: `pb_people/i18n/vi_VN.po`,
  `pb_home_hub/i18n/vi_VN.po` (formal, plain, no anglicisms where a Vietnamese word
  exists; keep "Payobook" untranslated; never "Odoo").
- Load: the `-u` on each DB loads the `.po` for the active language automatically; verify
  with a user whose `lang = vi_VN` (create a temporary validator with vi_VN on p9clone
  and payobook company 5; archive after).
- T-test: every msgid in the `.pot` has a non-empty msgstr in `vi_VN.po`; no msgstr
  contains "Odoo"; the `.po` compiles (`msgfmt -c`-equivalent via `polib` if present,
  else Odoo's loader without warnings).

## 6. Performance and robustness pass

- Goal finder and headroom already < 150 ms; keep. Add a guard so `candidates()` never
  runs twice concurrently (a second click while "Exploring…" is ignored).
- `ResizeObserver` on the story column redraws every canvas (stage, demand, bridge,
  room, ring) — verify none leaks when the lens unmounts (`onWillUnmount` disconnects).
- Play-through stops on `visibilitychange` (exists? verify) and on lens change.
- A 10-minute-old baseline shows "Roster as of 14:02 · Refresh" in the assumptions
  dialog header; Refresh calls `get_room(refresh=True)` and keeps the current plan.

## 7. Tests (numbered; all must pass on p9clone)

Server: T37 `.po` completeness/compile/no-"Odoo" (§5); T38 `render_brief` in `vi_VN`
context returns Vietnamese section headings and the Vietnamese money words; T39 Home
lens: `pb_home_hub` present in depends; the `hub_features` map carries both `decide`
keys; T40 all earlier suites (`/pb_decision_room`, `/pb_people_hub`, `/pb_hub`) green.
Engine/node: T41 `makeFormat(VND, 'vi_VN').compact(2.2e12) === '₫2.200 tỷ'`,
`(8.4e8) === '₫840 triệu'`, `(1.25e7) === '₫12,5 triệu'`; `parseCompact('2.200 tỷ')`,
`'840 trieu'`, `'2,2 tỷ'` (vi decimal comma) round-trip; English unchanged; T42
`marginal(n)` with team scaling: 4,533-person team → n = 45 → "45 more people"; a
40-person team → 5; T43 tween helper reaches its target exactly at t ≥ 1 and is a no-op
when motion is off.
Static: T44 every new icon exists in `IC`; T45 no template expression uses `not` (exists);
T46 every `aria-*` id referenced exists in the template; T47 the SCSS has no gradient
and no mixed-unit `min()/max()`.
Browser (payobook company 5, abm via reactivated validators, English AND Vietnamese
user, 1440 and 390, light and dark; screenshots `docs/handovers/wfplan_p3_shots/`):
B25 phone 390: stage first, bottom bar, sheet opens/closes (tap, Esc, backdrop), a
lever moves the mirrored hero in the sheet header and the stage behind; no page
overflow; B26 year strip snaps and centres the selected month; B27 keyboard-only
walk: Tab to a card → Enter opens its tab → ←/→ across tabs → Tab to a slider → Shift+→
steps 10 → ⌘Z undoes → ⌘S opens Save → Esc closes; visible focus ring at each stop;
B28 Motion off: no tween anywhere, values still update; reduced-motion OS setting same;
B29 Vietnamese user: every visible string Vietnamese (list any English survivors as
failures), money reads ₫… tỷ/triệu, brief in Vietnamese; B30 Home → Decision Room lens
present for a decision user, absent for a user without the group, locked/hidden when
`people_plan` is off (flip the feature on p9clone only); B31 experiment card names the
scaled number and the preview matches it; B32 Refresh roster keeps the plan and updates
the "as of" time; B33 lens switch mid-play stops playback, no console errors after
unmount/remount ×5; B34 everything from B1–B24 that a layout change could break
(re-walk B3, B11, B13, B16, B20, B22 quickly at 1440); B35 dark mode at 390;
B36 abm: Vietnamese and English both, sheet and Home lens.

## 8. The closeout (`docs/handovers/WFPLAN_CLOSEOUT.md`)

Write it for the owner first (plain English), engineers second. Precedent for structure:
`docs/handovers/RIZE_CLOSEOUT.md`. Sections:
1. **What is live and where** (People → Plan, Home → Decision Room, ⌘K, deep link), one
   paragraph per surface in plain words, with screenshots linked.
2. **How to use it in five minutes**: type a target → move a lever → set goals → find
   paths → try/keep → save → compare → print the brief. Ten short numbered steps.
3. **What the numbers are built from** (roster source per DB in plain words, the
   assumptions list, what is an assumption vs a record, the 10-minute refresh).
4. **Owner decisions still open**, each as a real-world question with what changes on
   screen and what it costs either way: retire the Classic planning tools fold (and
   uninstall `pb_hr_workforce_planning` — note `pb_budget` depends on `wfp.budget.actual`,
   so "uninstall" needs a `pb_budget` change first: say so); push the commits; reset the
   abm admin password; keep or delete "Board draft" + the ₫2,200B target; switch
   `people_plan` on/off per tenant.
5. **Owner debts and temporary users** (every temporary login created in P1–P3, its
   state now, what to do).
6. **Engineering summary**: modules + versions per DB, commit list P1–P3, test counts,
   timings, the ledger's gotcha range, seams added (`pb_people_hub_plan_hero`, Home lens,
   palette `focus`), what Phase 4 could be (shift rosters from real schedules, actuals
   vs plan once a pay run closes, multi-year).

## 9. Report back (plain-English first)

1. Three sentences a CEO understands: what the phone view does, what Vietnamese users
   see, where the room is reachable now.
2. Results table T37–T47, B25–B36 with evidence paths.
3. Deploy evidence per DB; `.po` loaded proof (a Vietnamese string read back via
   `ir.translation`-equivalent / the JS translation endpoint).
4. Deviations; new gotchas WF23+; phase log updated; closeout path.
5. Self-score against the bar and the one thing to improve first.
6. Commit list.
