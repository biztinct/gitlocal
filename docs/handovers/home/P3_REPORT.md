# HOME P3 — report (cards, polish, Vietnamese, clean-up, Learn words)

Builder: Opus, 2026-10-12. Not pushed, not deployed. Commits (oldest first):
`a3346c1b7` walk fixes W1–W4 · `a7af06dbe` server touches · `c202ab0fb` cards + closing row ·
`aac71c2cd` old payload deleted, 19.0.2.2.0 · `b13f9164d` tests 1–8 · `990a8610b` Vietnamese ·
`a6811b862` Learn words (pb_learn 19.0.20.5.0) · `53e84dff7` clone-walk CSS fix · this report + ledger H36–H42.

## P2 walk findings
| # | Outcome |
|---|---|
| W1 | **Fixed.** Second half of the headline: pay run(s) waiting on me → "N pay run(s) need your approval"; else chips on Needs you → "1 thing needs you" / "N things need you" (count of chips, not their sum); else "nothing is waiting on you". |
| W2 | **Fixed.** The visible `·` stays `aria-hidden`; a visually hidden " · " span sits beside it (`.pbd-vh`). |
| W3 | **Fixed.** Prepare/Approve rows name the run by its division (now_run / awaiting_run / runs lookup, falling back to the name); the full name is the row's `title`. |
| W4 | **Fixed.** Ghost height = max(latest month, month so far). Seen on the clone: October so far 66 M over September 60 M — the ghost wraps its fill. |
| W5 | **No change, verified.** P2 already does it: the panel pill reads "Not finished" (amber) for a past month with runs that are not all done; "Latest" stays on the newest all-done month (`latest` from the server). |
| W6 | **No change.** Data. Coming up's weekday comes from the ISO date (luxon), so "Sun 1 Nov" is the calendar row's real weekday — not mislabelled. |
| W7 (new, clone walk) | **Fixed.** A long delta ("about the same as Aug", longer in VI) pushed the figure sparkline into the next card; column is `minmax(0, 1fr)` and the delta wraps. |

## What shipped
- **People this month** (hidden when `people` is None): "N people with an active contract", Joined + "N more/fewer than <month>"/"same as", Leaving + amber "N settlements to check" (→ Exits), Out today stacked bar (indigo tints a/b/c + "Other leave" for types past the top 3) with legend, 7-day strip (today indigo, weekends grey, labels on today and the peak, hover title "Mon 12 Oct · 23 out"); a week with nobody out is one quiet line. Rose "N people have no active contract and cannot be paid · Fix in Contracts". "Open People".
- **<Month> pay runs** (always drawn): monogram, division name (full name as tooltip), badge Preparing / Not started / Waiting on you / Waiting on <name> / Waiting for approval / Done, count + bar, net (+ "so far" while draft), balances / rose "does not balance"; rose bank note naming the run with the most people and "N more in other runs" (→ People), amber "N pay values are missing a source" (→ that run); empty: "No pay run this month yet" + the hero's act as an outline button. Cancelled runs are not drawn.
- **Hiring** (hidden when None): open roles · candidates; four rows (None rows hidden, zeros grey, over budget rose); rose write-ups note; every row opens Hiring.
- **Keep learning** (hidden when None) → Learn hub, Lessons tab, `station:<key>`; streak with flame. **Pay schemes** (carries `dash-formula` now): "N schemes in use · N components", "every <month> run uses a tested scheme" only when no failing scheme, all tests passed and the month has runs; quiet green "All N tests passed, 2 hours ago" / rose "N tests failing" or "N schemes failed their last check"; ghost "Open Formula Studio".
- **Server**: `upcoming` adds next month's cut-off (`extra.month`) when this month's has passed or is missing; `runs[i].waiting_on` (open seat on the active step, never me). `foreign_runs` was already there (P2).
- **Clean-up**: `get_dashboard_data`, `_payroll_months`, `_resolve_period`, `_period_kpis`, `_month_words`, `_month_state`, `_as_month_key`, `_today`, `_END_CYCLE` deleted; `TestPayrollMonth` p1–p8 + p10 deleted, p9 kept as `test_10`; LEGACY_UNGUARDED gone; test_12 compares with `_activation()`. No caller anywhere (`pb_home_hub` comments updated; other modules' `get_dashboard_data` are their own models).
- **Vietnamese**: fresh `.pot` (261 msgids, exported on the clone), full `vi_VN.po` (no empty msgstr, placeholders kept, Pay Runs nouns: đợt lương, phiếu lương, chương trình lương). Units read "tỷ / triệu / nghìn".
- **Learn**: LW now 5 Home steps (hero, **new** button step on `dash-runpayroll`, chart, figures, Pay schemes) + new quiz on the headline; Pulse station outline, screen blurb/next, tour steps, first-day intent, column glossary (People paid / Net pay / Average net / Total cost); the Home **replica** redrawn (the lesson runs over it, H39); `contract.json` pins run-total facts instead of deleted code; anchor descriptions updated. EN + VI.

## Tests (bench `p0clone`, fresh stage `/tmp/h3s2` = pb_dashboard + pb_import_kit + pb_learn; `-u pb_dashboard,pb_learn --test-tags /pb_dashboard,/pb_learn`)
`pb_dashboard: 76 tests — 0 failed`. `pb_learn: 302 tests — 1 failed, 1 error, neither mine`:
- `TestLearnHub.test_the_config_is_built_once…` — `FileNotFoundError: /tmp/h3s2/pb_learn/../pb_hub/static/src/js/hub_shell.js` (reads a sibling module that is not in the 3-module stage; same family as H22).
- `TestQuestionMining.test_07b_the_cron_exists…` — `cron.active is False`: the clone has every cron switched off by design (P1 recipe).

| # | Test | Result |
|---|---|---|
| 1 | four cards guarded (`t-if` + getter returns null on a None section); runs card always drawn; `dash-formula` on Pay schemes | pass |
| 2 | every run state from the field's selection run through `runBadge()` **in node** (v18 on the clone): cancel → none, others → a key; reachable keys == RUN_BADGES | pass |
| 3 | `bankNote/sourceNote/weekBars/runProgress` **in node** on fixtures: biggest run named (5, run 2, +2 more), no note at zero, peak day, draft-with-nothing-done has no bar | pass |
| 4 | no `get_dashboard_data` / `_period_kpis` / `_payroll_months` / `_resolve_period` on the model; no caller in any `pb_*` module on the addons path | pass |
| 5 | `vi_VN.po` parses (polib), no empty msgstr, msgids == .pot msgids both ways, placeholders equal, no brand word, module line; every `_t("…")` in the JS is in the .pot (freshness) | pass |
| 6 | this month's cut-off passed → next month's in Upcoming with `extra.month`; while ahead → only this month's | pass |
| 7 | submitted run on a one-person route: approver sees `awaiting_me` and `waiting_on` None; another reader sees the approver's name | pass |
| 8 | every `dash-*` anchor the lesson content uses exists once on Home, and all five are taught | pass |
| 9 | browser walk on the clone | **done** — see below |
| + | Learn `check_contract.py` 73/73; `gen_learn_data.py` jargon lint clean; offline OWL render (H27) of 11 payload shapes with zero errors | pass |

**Walk (test 9)**: temporary server on the clone (port 8099, memory-capped unit, ssh tunnel), clone seeded with 6 people, 5 done months and 2 October runs (one draft, one submitted), calendar rows. 1440 px and 1100 px, English and Vietnamese (admin switched to vi_VN): hero, chart, panel, steps, coming up (next month's cut-off "Last day for November changes"), People / pay runs / Hiring / Pay schemes all render; no sideways scroll at 1100 (row re-flows to 2 columns); a run row opened Pay Run › Runs on that run with the "Home" back chip. Console: one pre-existing pb_learn warning ("lesson rows not added to the search"), nothing from Home. Learn card not seen (next-best flag off on the clone, H15). Screenshots were viewed in the session only (the browser tool cannot save into the scratchpad).

## Design-bar self-score (1–5)
- Every card names a problem AND the next step: **5** — bank, source, no-contract, write-ups, failing tests each say what to do and open where to do it.
- Nothing at zero is coloured: **5** — zero counts grey, notes only above zero, no ring anywhere.
- Every row is a door: **5** — run rows, hiring rows, joined/leaving, notes, links, lesson, Formula Studio.
- Vietnamese reads as naturally as English: **4** — full coverage and natural phrasing; money still prints a dot decimal ("66.0 triệu") and month labels read "tháng 10 2026" (P2 formatters, untouched).
- Best in class overall: **4** — matches the prototype; real-data polish on payobook (many runs, long names) is for Fable's walk.

## Modules to upgrade on deploy
`pb_dashboard` (19.0.2.2.0 — Python, assets, i18n) and `pb_learn` (19.0.20.5.0 — content, replica, SCSS). Purge `/web/assets/%`. `pb_home_hub`: comment-only edits, no upgrade needed. `pb_import_kit`: unchanged.

## Ledger rows added
H36 bracketed-s also bans call arguments · H37 i18n export option order + header · H38 run `done` is 0 for drafts/submitted runs · H39 the Home lesson runs over the replica; contract pinned deleted code · H40 jargon lint + pb_learn `.po` overwrite · H41 imported TestCase classes run twice · H42 p0clone now holds walk data.

## Deviations (with reasons)
1. **Run row counts** (H38): the handover's "done of slips" read "0 of N" for every draft and submitted run. Draft → "N payslips prepared" (bar only once some are done); submitted → "N people" with a full bar (the prototype's wording); done → "N of N payslips".
2. **Rose test line** reads "N tests failing" with the ghost "Open Formula Studio" beside it (not the label twice); a failing scheme with no failing test says "N schemes failed their last check".
3. **Bank note** names the biggest run with its own count and adds "and N more in other runs" when others have some; it opens People (where a bank account is added).
4. **Extra words**, each for a state the table did not cover: "No payslips yet", "Other leave", "Nobody is out today / this week.", "No pay scheme yet" + one line on what a scheme is, "Your next lesson", "just now", "Open the run to choose where each one comes from.", the footer "Figures are the pay run totals and match the payslips exactly." (prototype).
5. **Next month's cut-off** also appears when this month has no calendar row (not only when it has passed).
6. **Learn replica** redrawn (not in the scope list) — the lesson runs over it, so new words over the old drawing would teach a screen that no longer exists.
7. **W7 CSS fix** to the P2 figure grid (found on the walk).

## Left for the owner / Fable
- The Learn "Keep learning" card only appears where Learn's next-best suggestion is switched on (off on the clone and most databases).
- Vietnamese money keeps "." as the decimal mark and "tháng 10 2026" month labels (P2 formatters) — say if they should localise.
- `pb_learn`'s `gen_learn_data.py --check` reports its own `vi_VN.po` STALE at HEAD (pre-existing; H40).
- **p0clone is no longer empty** (H42): 7 walk runs, admin active with a temporary password, admin language Vietnamese. Tests assert on deltas, so they still pass; restore from `payobook_template` if a clean clone is wanted.
