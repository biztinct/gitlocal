# WFSETUP P1 — report (screen shell + Shifts + Working weeks)

Built 2026-11-24 in the worktree `gitlocal-worktrees/wfsetup`, branch `wfsetup`. Not pushed, not deployed.
Engineering document: real technical names on purpose. Screen strings contain no vendor name (static gate S1).

## 1. Result summary

| What | Result |
|---|---|
| Numbered tests 1–17 (`tests/test_setup.py`, tag `wfsetup`) | **17 / 17 pass** |
| Test 18 static gates (`tests/test_static.py`, 4 methods) | **4 / 4 pass** |
| `/pb_workforce_workspace` suite | before 11 → after 11, 0 failed |
| `/pb_shift_patterns` suite | before 29 → after 29, 0 failed |
| Combined result line | before: `0 failed, 0 error(s) of 32 tests`; after: `0 failed, 0 error(s) of 53 tests` |
| Browser walk B1–B10 | **10 / 10 pass** (notes on B5 and B10 below) |
| Console during the walk (manager + officer + basic user) | clean: no errors, no warnings |

Commands (private conf in the scratch area, addons path = this worktree):
`-d wfs1_base -u pb_workforce_setup,pb_workforce_workspace,pb_shift_patterns --test-enable
--test-tags /pb_workforce_setup,/pb_workforce_workspace,/pb_shift_patterns --stop-after-init`.
Baseline was the same two suites on the same database before the new module existed.

### Numbered tests
| # | Case | Result |
|---|---|---|
| 1 | load gates: basic AccessError, officer `can_edit False`, manager `True`, 7 steps in order | pass |
| 2 | create 22:00→06:00 break 30 → overnight, 0.5 h break, company, code, type night | pass |
| 3 | same initials → `FD`, `FD-2`; shared `ND` avoided → `ND-2` | pass |
| 4 | refusals: empty name, start = end, break ≥ length, negative break | pass |
| 5 | officer: save/copy/remove shift, save/remove week → AccessError | pass |
| 6 | 08–17 → 20–04 sets overnight, back clears it; type not re-derived | pass |
| 7 | remove: unused deleted; in a week refused with count; roster-only archived | pass |
| 8 | copy → "(copy)", new code, same times/break/colour, own company | pass |
| 9 | shapes 1×7, 2×7; 5-day and Tuesday start `editable False` + reason; save refused | pass |
| 10 | create → Monday start, 7 days, one team offset 0, slots match, off days empty | pass |
| 11 | edit with 2 teams / 3 members → team and member ids unchanged, unchanged day keeps its row | pass |
| 12 | shrink 2→1 drops days ≥ 7; with a team offset 7 → plain refusal, nothing changed | pass |
| 13 | other company's shift refused; 9 weeks refused; empty name refused | pass |
| 14 | remove week with current member → "1 person works this week…"; past-only → archived | pass |
| 15 | company isolation both ways, with two companies allowed | pass |
| 16 | member ended yesterday + member starting tomorrow both count as "no working week" | pass |
| 17 | `person_week`: team offset 7 on 14 days shows week 2; past member shows no week; default person has a week; `find_people.has_week` | pass |
| 18 | static: no vendor name (js/xml/scss/views, manifest, Python messages); every icon name exists; no emoji; new tag | pass |

### Browser walk (local server, port 8190, host `wfs1.localhost`, `--max-cron-threads=0`)
| # | Result | Notes |
|---|---|---|
| B1 | pass | rail, progress "2 of 7", both steps, right panel; console clean |
| B2 | pass | end time 17:00 → 18:30: bar, "9.5 h paid" and times changed on input; Save → Done; reload keeps 18:30 and the step |
| B3 | pass | each starter opens a focused, unsaved row; Save creates it; Night draws two segments and says "ends next day" |
| B4 | pass | copy → "Night (copy)" opens; Remove → "Yes, remove" → gone + message; removing a used shift shows "This shift is used in 2 working weeks. Take it out of them first." + "Go to working weeks" |
| B5 | pass | click paint, keyboard (arrow to next day + Space), drag across Mon–Fri; "Saving…" → "Saved"; database rows verified; reload keeps them. **Drag was driven with synthetic pointer events** — the browser tool's drag sends only the two end points (that also painted the two end days correctly) |
| B6 | pass | add rotation week → "Repeats every 2 weeks", paint nights in week 2, remove last week → back to "47.5 h a week"; teams/members untouched in DB |
| B7 | pass | New working week appears with its name selected; typed name + Enter saved ("Saved" shown); remove → confirm → archived; removing a week with people shows "2 people work this week. Move them to another week first." |
| B8 | pass | picker search "Thu H" + Enter → strip = rotation week 2 (14:00, 22:00 ×3, 14:00, 22:00, Off), caption "· week 2"; person without a week → empty state + "Go to who works what" opens step 3 |
| B9 | pass | officer: read-only line on both steps, no inputs, no edit buttons, painting does nothing, only "Open the rotation editor" and step navigation remain; console clean. Basic user: designed error card "Attendance access is required." + Try again |
| B10 | pass | 1440, 1100, 800: no horizontal scroll, nothing clipped (scripted check of every element's right edge). Chrome windows stop at 500 px, so **400 was checked with an emulated 400×860 viewport**: no scroll, nothing clipped |

Also walked: 34 shifts (page scrolls, rail and panel stay sticky); a 70-character shift name (ellipsis, full name in `title`); empty company (no shifts → four starters in the centre; step 2 → "Add a shift first" → Go to shifts; no working week → centred "New working week"; panel "Nobody works for this company yet."); reload on `?step=weeks` lands on step 2.

### Visual differences from the prototype at 1440 that remain
1. Crumb reads "Workforce setup · <company>" — no "Settings ›" (P1 is not reached from Settings), no "Design proposal" chip, no "What I found and changed" button (prototype-only).
2. Display font: Manrope is not hosted in the product (no CDN allowed), so headings fall back to Inter. Slightly narrower headings.
3. Teal is the Schedule's teal (≈ #2A7195), not the prototype's #0F8B8D (see §4).
4. Remove buttons are never disabled; a used shift/week explains itself on click instead (prototype greys them out).
5. Right panel: no sliders and dark result box (P3, by the handover); a per-day list of shift times sits under the strip.
6. Time inputs render 12-hour ("06:30 PM") in a 12-hour browser locale — same native control as the prototype.
7. Final small polish made after the last 1440 screenshots (step-dot colour order as in the prototype, 9.5 px times inside day cells, shift hint hidden when the list is empty) was checked only on the empty-company screens, not re-screenshotted on the full data set.

## 2. Deviations from the handover (and why)
1. `remove_shift`: the refusal counts **active** working weeks only. Slots of archived working weeks still block a delete (FK restrict), so such a shift is archived instead — the user cannot see archived weeks here, so refusing would be a dead end.
2. Remove (shift and week) is a two-step inline confirm ("Yes, remove" / "Keep it", 5 s), not immediate.
3. A starter adds a **local** row; the record is created on Save (no stray records when abandoned). Leaving or opening another row saves it first, per the saving model.
4. Working weeks are listed by id (stable while renaming), not by name.
5. Step texts: "N shifts ready", "N working weeks ready" / "Build a working week"; people step with 0 employees → `todo` "No people yet"; singular forms ("1 person has no working week").
6. Extra payload keys: `colors`, `max_weeks`, `person` in `load()`; `missing`/`total` on the people step; `days` (raw cycle) and `teams` on week rows; `label/date/today/name/color` per day and `week_id/week_no` in `person_week`.
7. A whole-week rotation with a non-Monday start is shown rotated so columns stay real weekdays (still read-only).
8. Phone widths (≤600 px) show the start time only inside a painted day; the full name is in its accessible label.
9. Test database: `upd_p6_t_tpl` is behind the current code (registry would not load), so the copy got one `-u all` before use; the same single DB served baseline, tests and the walk, then was dropped with its filestore.
10. `pb_timeoff` is a valid dependency (no cycle: `pb_mission` already depends on it).

## 3. Facts that proved wrong or stale
- J.1 "use `upd_p6_t_tpl`": the template no longer loads against `19.1` code — 17 models have no table (`pb.clock.connector`, `pb.updates.ytd.*`, `pb.list.layout`, …) and `res_company.pb_weekday_location_defaults` is missing. Needs `-u all` (~4 min) first. Also `pb_shift_patterns`, `pb_workforce_workspace`, `pb_form_studio` are not installed in it.
- J.1 test counts: `pb_workforce_workspace` reports **11** and `pb_shift_patterns` **29** in `odoo.tests.stats` (the result line counts 32 for both); facts say 9 and 18 + static.
- H icons: `arrowLeft` is absent as stated, but `back` (a left arrow) exists — used for the back buttons.
- Not in the facts: with only the attendance officer group (as the test fixture builds it) the officer cannot read `res.company` (`biz_access` + ACL path) — `self.env.company.name` raised AccessError (WS2).

## 4. Colour mapping
Source: `pb_schedule/static/src/scss/pb_schedule.scss` `$pbsc-accent` (index → token). Chosen indices:
indigo **1** (`--pbim-primary`), teal **6** (mix green 55 % + cyan ≈ #2A7195 — the only teal-like one of the eleven),
amber **4**, blue **3** (`--pbim-cyan` #2563EB), rose **5**, green **2**. One table: `COLOURS` in `models/setup.py`,
sent to the client in `load()['colors']`; CSS classes `pbws-c-<name>` paint the same expressions as the Schedule, so a
shift looks the same on both screens. Unknown stored indices display as indigo and are kept on save — the client only
sends `color` when the user picked one.

## 5. Self-review against §3 (design bar)
| Bullet | Score /5 | Note |
|---|---|---|
| Hero: 24-hour bar reshaping as you type | 5 | segments, break gap and overnight split move on every input; bars aligned by subgrid |
| Hero: painting a week by dragging | 4 | click, drag, keyboard, autosave marker; drag verified synthetically only |
| Zero dead-ends | 4 | every empty/refused state names the next step; non-whole-week rotations get a door |
| Plain language | 5 | shift / working week / day off / unpaid break; no field names |
| Motion with purpose, reduced motion | 4 | bar/colour transitions, row open, marker; all off under reduced motion |
| Keyboard + bulk ergonomics | 4 | Enter saves, Esc cancels, arrow-key grid, Fill Mon–Fri/Sat, picker fully keyboard |
| One solid primary per bar | 4 | holds per bar; the empty "No working week yet" card and the Next bar are both solid on one screen |
| Lucide only, no gradients, white-label | 5 | static gates; track hairlines are plain 1 px lines |

**Weakest point:** the right panel. In P1 it repeats what the centre shows (strip + list) and its default person is
simply the first name alphabetically who has a week (on test data: "Administrator"). It earns its space only when P3
adds the pay example. Second weakest: the 1040 px and 600 px fallbacks are viewport media queries, so their real trigger
depends on the sidebar width.

## 6. New gotchas → ledger WS1–WS8 (appended).

## 7. Commits (branch `wfsetup`)
- `fd11e1e6a` feat(pb_workforce_setup): guided Workforce setup screen — shifts and working weeks (WFSETUP P1)
- this report + ledger gotchas (docs commit, see `git log`)
