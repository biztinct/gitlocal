# HOME P3 — cards, polish, Vietnamese, clean-up (handover for Opus)

Read first: `HOME_PROGRAM.md`, `HOME_LEDGER.md` (every rule and row), `P2_HANDOVER.md` + `P2_REPORT.md` (the
component you are extending — its class names, state, words table, doors), `P1_REPORT.md` (payload facts), and
the build target `docs/design/home-dashboard-prototype.html` sections 6–7 (the three cards and the closing row).
CLAUDE.md rules apply. `<<P2 walk findings, if any, are listed at the end of this file — fix them FIRST>>`

## Design bar (verbatim, binding)
"Extreme WOW, intuitive, out-of-this-world experience, best in class." For P3: every card names a problem AND the
next step (amber/rose notes), nothing at zero is coloured, every row is a door, and the Vietnamese reads as
naturally as the English. Score the report against it.

## Scope (P3)
1. **People this month** card (`people` section; hidden when `None`, H14): sub "%(n)s people with an active
   contract"; Joined `joined` ("%(d)s more/fewer than %(prev month)s", or "same as"); Leaving `leaving` with an
   amber link "%(n)s settlements to check" when `settlements_to_check > 0` (→ Exits board); "Out today" stacked
   bar from `out_breakdown` (two indigo tints + legend; hidden when `out_today` is None); the 7-day strip from
   `week` (today indigo, weekends grey, direct labels on today and the peak, hover value); rose line
   "%(n)s people have no active contract and cannot be paid · Fix in Contracts" when `no_contract > 0`; link
   "Open People".
2. **<Month> pay runs** card (`runs`): sub "%(n)s runs" (+ ", one per office" NEVER — no invented words); each
   row = monogram (`initials`, soft indigo), name, badge by state (draft+slips>0 → indigo "Preparing"; draft+0 →
   slate "Not started"; approval_pending → amber "Waiting on you" when `awaiting_me` else amber "Waiting on
   %(who)s" if P1 exposes it else "Waiting for approval"; done → green "Done"), "%(done)s of %(slips)s payslips"
   with a progress bar (done/slips; 100 % when done), net at the right ("so far" while draft), "balances" / rose
   "does not balance" from `balance_ok`; a rose note "%(n)s people in %(run)s have no bank account · Add one
   before payday, or they will be paid in cash" when any `no_bank > 0` (sum per run, name the biggest); amber
   note "%(n)s pay values are missing a source" when `unsourced > 0`; link "Open pay runs". Row click → the
   Runs board focused on the run (P2 door).
3. **Hiring** card (`hiring`; hidden when `None`): sub "%(open)s open roles · %(candidates)s candidates"; list
   rows Interviews this week / Roles over budget (rose when > 0) / Offers waiting for a reply / Referrals this
   month (rows with `None` hidden); rose/amber note for `writeups_overdue > 0` ("%(n)s interview write-ups
   overdue · Remind the interviewers, or decide without them"); link "Open Hiring".
4. **Closing row**: **Keep learning** (`learn`; hidden when `None`): "Keep learning" eyebrow, lesson title,
   "%(m)s minutes · %(reason)s", outline button "Start lesson" (→ `learn.scenario.begin` / the existing
   `SCENARIO_SERVICE` door the activation checklist uses, or the Learn hub lesson by key), streak "%(d)s-day
   streak" (muted). **Pay schemes** (`schemes`): "%(active)s schemes in use · %(components)s components",
   "every %(month)s run uses a tested scheme" ONLY when `failing_configs == 0` and `tests_passed == tests_total`;
   green quiet line "All %(n)s tests passed, %(ago)s" or rose "%(n)s tests failing · Open Formula Studio";
   ghost button "Open Formula Studio" (`pb_formula_studio.action_pb_formula_studio`). Move `data-coach="dash-formula"`
   here (H9).
5. **Server touches** (small, in `get_home_data`): `upcoming` adds NEXT month's cut-off when this month's has
   passed (reads the next `pb.payroll.calendar` row); `months[i].foreign_runs` if P2 asked for it and it is not
   there yet; `runs[i].waiting_on` (name of the current step's approver when `approval_pending` and not me — one
   read through `optional('biz.approval.request')`, bounded to the period runs).
6. **Clean-up**: delete `get_dashboard_data`, `_payroll_months`, `_resolve_period`, `_period_kpis`, the formula
   block they used and every test that pins them (`test_p3`, `test_p4`, the month strip tests); `test_04`'s
   allowance for the old unguarded formula read goes away. Nothing else may still call `get_dashboard_data`
   (grep the whole repo: pb_learn content, docs/tutorial_poc, pb_demo…; fix callers).
7. **Vietnamese**: `pb_dashboard/i18n/vi_VN.po` for every new string (JS `_t`, template literals extracted by the
   platform — run the export on the clone: `--i18n-export` for `pb_dashboard` to refresh `.pot`, then fill
   `vi_VN.po`). Rules (memory `po-translation-loading-rules`): every entry needs a `msgid` that matches the source
   exactly, a non-empty `msgstr`, and the `#. module: pb_dashboard` header lines the loader expects; parse the file
   with `polib` before shipping; placeholders `%(n)s` kept verbatim. Screen words in VI follow the existing Pay Runs
   board `.po` (same nouns for pay run / payslip / scheme).
8. **Learn words**: update the Home lesson(s) in `pb_learn/static/content/learn_content.json` (and
   `docs/tutorial_poc/author/data.js` if it is the source) so the five anchors' sentences describe the new screen
   (hero, the primary button, the month chart, the four figures, the Pay schemes card). EN + VI. Bump pb_learn.
9. **Empty / small tenants**: with zero runs the three cards still render (runs card says "No pay run this month
   yet" + the primary door; People shows counts; Hiring hidden when absent).

## Binding non-goals
No new data sources beyond item 5. No dark mode, no Chart.js, no deploy (Fable), no change to the P2 hero/chart
except walk fixes listed at the end. No "Odoo". No per-module icon map (add to the kit).

## Numbered tests (`tests/test_home_cards.py`; everything earlier stays green)
1. Cards hide when their section is `None` (People, Hiring, Learn) — template `t-if` present and a source test
   that the three section names are guarded.
2. Run badge words cover every state the server can emit (`draft`, `approval_pending`, `done`, `cancel` → cancel
   rows are not rendered) — words-table ↔ server test like P2's.
3. `no_bank` note names the run with the biggest count; `unsourced` note appears only when > 0 (source checks on
   the JS getters with a fixture payload — write the getters as pure functions exported from the JS module and
   assert their behaviour from Python by reading… no: write them as pure functions and test them with a 20-line
   `node` script if `node` exists on the clone; otherwise source-string checks. Say which in the report).
4. `get_dashboard_data` no longer exists; the repo has no caller (grep test in the suite over `pb_*`, `docs/` excluded).
5. `vi_VN.po` parses with `polib`, has no empty `msgstr`, and every `msgid` exists in the fresh `.pot`.
6. Upcoming includes next month's cut-off once this month's passed (server test with a seeded calendar row).
7. `runs[i].waiting_on` is the approver's name on a submitted run where the seat is held by another user; absent
   when it is me.
8. Learn content: the five Home anchors referenced by the lesson exist in the template (source test joining the
   JSON and the XML).
9. Browser walk on the clone as P2 (if memory allows) incl. the VI language switch for one user.

## Deliverables / report / how to run — as P2 (`P3_REPORT.md`; stage `pb_dashboard pb_import_kit pb_learn`;
`-u pb_dashboard,pb_learn --test-tags /pb_dashboard,/pb_learn`). Version `pb_dashboard` `19.0.2.2.0`.
Commits `feat(home): P3 …`. Ledger rows H-next.

## P2 walk findings (payobook.com, QA login, 2026-10-12, pb_dashboard 19.0.2.1.1) — fix FIRST, number them W1…W6 in the report
Walked at 1440 px: hero, needs-you, chart, month panel, steps, coming up all render with real data; console clean
(two old warnings from other screens); ← → moves the month, tooltip shows ("March 2026 · No pay run"), the
primary opens Pay Run hub › Runs focused on the run with the Home back chip. Already fixed and live (H31–H33):
people once per month, account number = bank account, division names. Still to fix:
- **W1 Headline contradicts the line below it.** h1 says "nothing is waiting on you" while Needs you lists 1
  settlement + 1 renewal + 21 write-ups. Rule: the second half of the h1 speaks for ALL of `needs_you`:
  awaiting_me ≥ 1 → "%(n)s pay run needs your approval" (as now); else `needs_you` non-empty → "%(n)s things need
  you" (n = number of chips, not the sum); else "nothing is waiting on you".
- **W2 Headline reads "20 days to paydaynothing is waiting on you" to a screen reader** (the "·" is a decoration).
  Put a visually hidden " · " text node (or an `aria-label` on the h1) between the two pieces.
- **W3 Steps card names the run by its long name** ("Payobook Information Technology — End-Month Payroll ·
  October 2026 run in progress") while the hero says "Information Technology". Steps card uses `division` (fall
  back to the name); the full name goes in the row's `title` attribute.
- **W4 In-progress ghost column is shorter than its own fill** when the month so far exceeds the latest month
  (payobook: October so far 65.8 bn vs July 35.0 bn). Ghost height = max(latest month, so far).
- **W5 "Latest completed" lands on July** because June, August and September each hold a draft run (demo data).
  Keep the rule (every run done), but the month-panel pill for a month that has runs and is NOT all done should
  read "Not finished" (P2 has this word) and the chart's "Latest" label stays on the newest all-done month. No
  change unless the P2 code does otherwise — verify and say so.
- **W6 Payday "Sun 1 Nov" / cut-off "Sun 25 Oct"** come from the demo calendar rows (weekend dates). Data, not
  code — no change; mention in the report only if Coming up mislabels the weekday.
