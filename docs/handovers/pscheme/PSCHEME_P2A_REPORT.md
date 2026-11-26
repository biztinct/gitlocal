# PSCHEME P2a — report: Mapping re-worded, "Set for everyone in this team", the one-time fill, Country of work prompt, the contract follows

Implementation engineer, 26 Nov 2026. Worktree `gitlocal-worktrees/pscheme-p2a`, branch `pscheme-p2a` from `59e68e10e`.
Local only: nothing pushed, no live server or database. Engineering document: real technical names on purpose; no
client data, no credentials (walk logins are local-only, in the scratch seed).

## 1. Result

**GO for P3** — T1–T14 pass, walks W1–W8 and the one-run check pass with a clean console, the before/after suites
differ only as listed in §4.2. Two deviations want an architect nod (§3.1, §3.2); neither breaches ledger §1/§2.

| Commit | What |
|---|---|
| `75dbbdc7a` | A–E server: many-person requests, team set, one-time fill + undo + log, country net, contract follows; T1–T12 |
| `1ebf3de01` | screens: Mapping wording/counts/banner/chip, the four drawers, panel amber line + contract note, prompt, strip |
| `6956f73e7` | walk fixes + vi_VN / id_ID for every new string (179 msgids) |
| `40473e00f` | ledger PS-a1..PS-a9 |
| (this file) | report |

## 2. What changed on screen (screen words)

**A. Mapping › Who is paid by what**
- One calm line under the head count: "Each person has their own pay scheme. A team's usual scheme is the starting
  point for new people and for anyone without one."
- Every team line now reads **Usual** before its scheme. Each team row (and every team inside it) counts
  "N on the usual scheme" and "M have their own"; M opens the names with their scheme and "Since 1 Nov 2026".
- Attach panel: "New people in <team> start on this pay scheme. People with a pay scheme of their own keep it."
  The toast after attaching says the same.
- "Nobody pays these people yet": "A pay run leaves them out until they have a pay scheme. Give them one of their
  own, or set their team's usual pay scheme." — a **Give them a pay scheme** button (the fill drawer, only these
  people) and, per person, **Set their team's usual pay scheme**. Reasons say "They have no pay scheme of their
  own, and their team has no usual pay scheme yet." or the person's own reason ("Their own pay scheme has ended…").
- Banner while anyone still follows their team: "N people still follow their team. Each person keeps the pay scheme
  that pays them today, written down as their own. Nothing changes in anybody's pay." + **Give everyone their own
  pay scheme**. Afterwards a quiet **Pay scheme fill** button (history, undo).
- Amber chip "N paid by another country's scheme" → the list (D.1).
- "Suggest who pays each team" drawer title: "Each team's usual pay scheme, by country of work" (nothing else).
- A person's waiting team/fill request shows on their panel ("Waiting for approval: … · With …").

**B. Set for everyone in this team…** (person-plus icon on each team row that has people)
- Pay scheme cards (the team's majority Country of work first, "Usual" on the team's own), the mid-month advance
  switch (the team's real advance line, else the scheme's single paired advance), "Show N more pay schemes".
- "Without a pay scheme (N)" — ticked, "From 1 Nov 2026, the first day of this month."; All / None; shift-click
  ticks a range.
- "Already have their own (M)" — unticked master tick "Also move these M people", a From date (1st of next month)
  with "A change during a month starts with the next pay run. Their current pay scheme still pays December 2026."
  or "First pay run on the new pay scheme: …"; each row "Indonesia monthly staff → Indonesia large scheme" or
  "no change".
- Anyone whose Country of work is not the scheme's: unticked in both groups, "Works in Singapore. Indonesia monthly
  staff is a pay scheme of Indonesia."
- Live sentence "87 people will be paid by Indonesia large scheme: 4 from 1 Nov 2026, 83 from 15 Dec 2026." and
  "Set for 87 people" / "Ask for this change".

**C. Give everyone their own pay scheme** (hero below)
- Hero ring + "247 people, and nobody has a pay scheme of their own yet." / "188 of 247 people have a pay scheme of
  their own." + "Each person keeps the pay scheme that pays them today, written down as their own from 1 Nov 2026.
  Nothing changes in anybody's pay."
- Groups: **Ready** (ticked, collapsed) · **From their Country of work** (ticked) · **Check these** (unticked, per
  row "Keep <today's>" / "<their country's>", bulk "Keep today's" / "Their country's"; a country with no scheme
  says "No pay scheme for Malaysia yet. Add one") · **Needs your choice** (a chooser per row, bulk "All 25 in
  Vietnam: [scheme]", reasons with "Fill empty Country of Work" / "Add a pay scheme") · "Already have their own:
  N". Grouped by country then team with counts, 60 rows a page + "Show more (N left)", search by name, live sum.
- Done: "231 of 247 people have a pay scheme" / "All 247 people have a pay scheme" / "Sent for approval to …".
- "Last fill: 26 Nov 2026 by …, 148 people." + **Undo this fill** → "Undo takes off the pay schemes this fill gave
  146 people. They go back to their team's usual pay scheme. 2 people changed since keep theirs: …" → Keep it /
  Undo this fill.

**D. Country of work**
- Panel › Pay scheme: amber "Putu works in Vietnam but is paid by Singapore monthly staff." + Change pay scheme
  (dialog preselected to the fitting scheme; nothing preselected when the country has several).
- "Paid by" chip: an amber "Works in Vietnam" row (full sentence in the tooltip). Contract drawer › Components strip:
  the same amber sentence.
- After saving a Country of work (Full details or the workspace Pay tab) the dialog opens at once with "Country of
  work is now Vietnam. Change the pay scheme too?" and **Not now**; the panel and chip update either way.
- Board list "Paid by a pay scheme of another country": each person, "Works in Vietnam · paid by Singapore monthly
  staff (Singapore)", "Fits their Country of work: Vietnam monthly staff", Change pay scheme; one **Change these N
  to <scheme>** button per scheme that fits a group (from the 1st of next month).

**E. The contract follows**
- Dialog: "This also changes their contract's currency to SGD from 1 Nov 2026." when the picked scheme brings
  another contract currency.
- After a change that takes effect (today or by the daily job): the running contract's Country of work and currency
  follow, the new scheme's usual answers are filled ("Payobook filled in 4 answers…"), and the panel says "Their
  contract is now in SGD. Check their pay amounts." with Open the contract / Got it (also cleared by editing the
  wage).

**Hero moment (W3):** one drawer turned "83 of 247 people have a pay scheme of their own" (the rest following their
team) into "231 of 247 people have a pay scheme" — the 112 safe people ticked already, 5 of the 8 "Check these" in
one bulk press, 31 of the 44 "Needs your choice" in two bulk picks, one press to apply — and "Undo this fill" was
still there afterwards and worked (W4). (On the untouched copy the same drawer opened on "247 people, and nobody has
a pay scheme of their own yet"; W5 filled 188 of them in one approved request.)

## 3. Deviations (each with its reason)

1. **T4 — a person changed while the request waits refuses the WHOLE request** (named). Reason: an approver approved
   exactly that list; carrying out a part writes something nobody approved as a whole; it is P1's tested path; asking
   again is one press because the drawers plan again from what is there. *Architect: confirm or ask for "skip and
   name".*
2. **The one-time fill never moves a contract** (E.1 runs for hand, team, hire, job change; not `source='fill'`).
   Reason: the fill writes down who pays people today and must change nobody's pay; a contract whose country differs
   from its scheme is left as it is (it was already so). *Architect: confirm.*
3. **E.1 fill-in only when the contract's country moves** — T11 says a same-country change leaves the contract
   untouched, so "newly known → scheme changed" is implemented in the follow path (`_ps_follow` calls
   `_pb_fill_in_newly_known` for the people whose contract moved), not in the nightly recompute.
4. **Mismatch bulk per fitting scheme** — "Change these N" is offered per scheme that fits a group (a superset of
   "when one target fits").
5. **Advance in the fill** — only today's REAL advance (A13) of the same country as the scheme the person gets; a
   paired advance is never guessed. Team drawer default: the team's real advance line, else the single paired one.
6. **Undo is per person**: a person whose rows changed in any way keeps ALL their rows (removing only their main row
   would leave an advance without a month).
7. **No Country of work but paid today** → "Needs your choice" (today's scheme first in the chooser), not Ready.
8. **P1 fix (PS-a5)**: `person_set` in lane `'none'` was refused by the writer's own guard.
9. **Empty team**: the team button is not drawn on a team with nobody (no dead-end to reach); the drawer still has a
   designed empty state.
10. **D.2 walked on the workspace Pay tab** (same `FormController` hook as Full details; the native form was not
    walked separately).
11. `pb_contracts` (strip line + version) edited — not in P2b's list.

No ledger §1/§2 decision was left un-honoured.

## 4. Tests

### 4.1 Numbered tests — all pass (`pb_scheme_map/tests/test_p2a_*.py`, tag `pscheme_p2a`)

| # | Test | Result |
|---|---|---|
| T1 | `TestP2aBoard.test_t1_board_counts_own_list_and_reasons` | pass |
| T2 | `test_t2_team_plan` (groups, sub-team with its own line left out, other country unticked) | pass |
| T3 | `test_t3_team_apply_fast_lane` (1st of month / move date, old row ends the day before, advance, map untouched, idempotent) | pass |
| T4 | `test_t4_team_apply_second_approver` (nothing until approved, waiting on each panel, a moved person refuses all by name, re-ask applies) | pass |
| T5 | `TestP2aFill.test_t5_plan_groups` (ready, country, check, several, none, no country, own, A13) | pass |
| T6 | `test_t6_apply_rows_equal_the_plan` (rows = plan, source fill, 1st of month, rerun writes nothing, answers equal before for month + advance) | pass |
| T7 | `test_t7_five_thousand_people` (5,000 people; ≤ 120 queries, < 20 s, ≤ 15 queries more than for 3 people) | pass — see §4.3 |
| T8 | `test_t8_undo` | pass |
| T9 | `test_t9_dry_writes_nothing` | pass |
| T10 | `TestP2aBoard.test_t10_country_net` (true / false / later row / waiting change / list / bulk) | pass |
| T11 | `TestP2aFollow.test_t11_contract_follows` (today, boundary day, same country, idempotent, wage clears, fill never moves, card currency) | pass |
| T12 | `TestP2aBoard.test_t12_rights` | pass |
| T13 | `TestP2aStatic.test_t13_words_and_translations` (179 msgids: in the catalogue, vi + id, no banned word, placeholders kept) + `test_t13_source_literals`; scratch diff scan of 252 added visible strings: no Odoo / rung / config / cycle | pass |
| T14 | `test_t14_dependency_rail` + `test_static_contract` (incl. the dependency rail) + P1's 63 tests | pass |

Deliberate test update: `test_static_contract.test_t12_the_bundle_is_the_files_on_disk_in_the_right_order` (four new
asset files).

### 4.2 Suites before / after (P1's list)

`/pb_scheme_map,/pb_new_hire,/pb_payrun_wizard,/pb_hr_payroll_formula,/pb_employee_vault,/pb_contracts,/pb_updates,
/pb_job_change,/pb_loans,/pb_retro,/pb_expense_payroll,/pb_pay,/pb_me_tax,/pb_decision_room` (`-u` of the same 14
modules) on two fresh copies of `ps_base`. "Before" = a full `git archive` of `59e68e10e` (the P2a base) as the
addons path.

- **before**: 1,799 tests, 8 failed + 6 errors (3,420 s).
- **after**: 1,814 tests (+15, this phase's new tests), 8 failed + 6 errors (3,125 s).
- **The 16 failing lines are byte-identical on both sides** — the same pre-existing, environmental list as P1 §4.2
  (`TestS5fLeaverBackpay` F01–F09, two duplicate-key fixtures, `TestCd1Contract360.test_01`,
  `TestDecisionRoomStaticContract.test_t14`, `TestRd49SyncCost` 02ab / 02i, `TestRecordsR1OneTime.test_07b`,
  `TestS2dTaxFlow.test_t9`, `TestT3bLetterToken.test_t3b_9`, `TestVietnameseIsComplete.test_t4c`). Nothing fails
  only after; nothing fails only before. Per-module counts differ only for `pb_scheme_map`.
- `pb_new_hire`'s suite (the hire also goes through the contract-follow hook, PS-a4) is unchanged.
- The whole `pb_scheme_map` suite was also run on its own during the build: 75 / 75.

### 4.3 T7 at size

Measured in the after suite: **5,008 people planned in 29 queries and 0.92 s**; the same plan for 3 people costs 27
queries (the roster, the map, the rules and the schemes are each read once; no per-person query). Ceilings asserted:
≤ 120 queries, < 20 s, ≤ 15 queries more than for 3 people.

## 5. Walks (local `ps2a_w` fast lane, `ps2a_w5` second approver; Claude-in-Chrome; console read every walk)

| # | What I did and saw | Result |
|---|---|---|
| W1 | Board: the calm line, "USUAL" on every line, "92 on the usual scheme", after W2 "9 on the usual scheme · 83 have their own" → the names with "Since 1 Nov 2026" | pass |
| W2 | Indonesia Operation drawer: cards ("Usual" on Indonesia monthly staff), 5 Singapore people unticked with the reason, click + shift-click unticked 4 → "Set for 83 people"; applied (fast lane), counts moved, banner 247 → 164. Again: other card, master tick, From 15 Dec → the one-payslip sentence and "87 … : 4 from 1 Nov 2026, 83 from 15 Dec 2026" (closed without saving) | pass (fixes: scroll body, mouseup, PS-a1) |
| W3 | Fill on 247 people: Ready 112, Check 8, Needs your choice 44; "Their country's" bulk, "All 25 in Vietnam" + "All 6 in Indonesia" bulk picks, search "Hui" → one row; applied 148 → "231 of 247 people have a pay scheme"; banner 16; a person's panel "Their own pay scheme since 1 Nov 2026" | pass |
| W4 | Undo this fill → names the 2 people changed since → undone; banner back (159); a person reads "From Finance's usual pay scheme" | pass (fix: count in the done line) |
| W5 | `ps2a_w5`: HR officer → "Ask for this change" → "Sent for approval to DEMO P2A Payroll manager"; a person's panel shows the waiting request; payroll manager → Approvals: plain rows per scheme ("Indonesia monthly staff · 77 people from 1 Nov 2026") → Approve → 188 rows `source=fill`, log asked by the HR officer, carried out by the payroll manager | pass |
| W6 | Workspace Pay tab: Country of Work Singapore → Vietnam, Save → the dialog with "Country of work is now Vietnam. Change the pay scheme too?" → Not now → amber line on the panel, "Works in Vietnam" on the chip; amber Change → Vietnam monthly staff → "Changes to Vietnam monthly staff on 1 Dec 2026", amber gone. Board list → "Change these 4 to Vietnam monthly staff" → done | pass (fixes: refresh after Not now, no wrong preselect, per-scheme bulk) |
| W7 | Person with a VND contract → Singapore monthly staff from 1 Nov: "This also changes their contract's currency to SGD from 1 Nov 2026."; after save the panel shows "Their contract is now in SGD. Check their pay amounts.", the contract shows S$, 4 usual answers filled, the strip shows the amber line; Open the contract opens it | pass |
| W8 | HR officer in the fast lane: "A payroll manager carries out pay scheme changes here, and nobody is set up to approve one…", button disabled, no undo; Malaysia: "No pay scheme for Malaysia yet." + Add a pay scheme; teams with nobody have no team button; no Country of work → Fill empty Country of Work | pass |
| Runs | `_scheme_population` for every scheme of company 1: November on `ps2a_w` (Indonesia Operation paid by two schemes) and December on `ps2a_w5`: 0 people in two main runs | pass |
| vi | Board, banner, fill drawer, groups and reasons in Vietnamese (`font` nodes 0) | pass — two English strings belong to another stream (PS-a8) |
| 340 px | Fill drawer at 340 px: `scrollWidth` 340 = `clientWidth`, nothing overflows | pass |
| Console | errors only, every walk | clean |

## 6. Design bar self-score (out of 10)

| | Score | Why |
|---|---|---|
| Hero moment | 9 | One drawer, the ring fills, the safe 194 are one press, bulk picks for the rest, undo is there the next day. Minus one: after apply the list of the people still open stays under the done card (useful, but busier than a clean finish). |
| Zero dead-ends | 9 | Every group names its reason and its fix; blocked readers see why before pressing. Minus one: "Add a pay scheme" opens the scheme builder, not a pre-filled new scheme of that country. |
| Plain language | 9 | Screen words only; dates "1 Nov 2026"; the demo first name reads "DEMO" (fixture naming). |
| Motion | 8 | Banner entrance, ring fill, done pop, segment press; reduced motion respected. |
| Keyboard + bulk | 9 | Shift-range ticks, select all/none, bulk per group and per country, Esc closes drawers, Ctrl+Enter applies, cards with arrows; row buttons answer Enter/Space. |

## 7. The release script (P3) — dry and real fill

Run per database, per company, in `odoo-bin shell` (superuser; the product's own path):

```python
cid = <company id>
B = env['pb.scheme.board'].with_context(allowed_company_ids=[cid])
dry = B.fill_apply(cid, ['ready', 'country'], dry=True)          # writes nothing
print('DRY', dry['people'], dry['left'], dry['by_group'], dry['plan_counts'])
for s in dry['schemes']:
    print('  ', s['scheme'], '+', s['advance'] or '-', s['people'])
# --- only after reading the dry run ---
out = B.fill_apply(cid, ['ready', 'country'])
print('REAL applied', out.get('applied'), 'pending', out.get('pending'), 'people', out['people'],
      'fill', out.get('fill_id') or (out.get('result') or {}).get('fill_id'), out.get('message'))
env.cr.commit()
```

- Prints: people given a scheme, people left (check + choice), counts by group used, the plan's counts
  (`ready / country / check / choice / own`), and per scheme (+ advance) the head count.
- Only Ready and From-Country-of-work are ticked by the script; Check these / Needs your choice stay for a person on
  screen (the drawer).
- Where the company has a second approver, the real call answers `pending` ("Sent for approval to …"); a payroll
  manager approves in Approvals. Undo = "Undo this fill" on screen (the log `pb.person.scheme.fill` keeps the rows).
- Run "Fill empty Country of Work" BEFORE the dry run (FACTS T10). Expect PS-a2 on companies with one scheme per kind.

## 8. Lesson and help sentences now untrue (for P3)

- `pb_learn/static/content/learn_content.json:25294` (vi `:25295`) "Which pay scheme pays each part of the
  workforce." — Mapping › Who is paid by what now sets each team's USUAL scheme; people have their own.
- No lesson covers the banner, the fill drawer, the team drawer, the other-country list or the Country of work prompt.
- Every P1 §8 item still stands.

## 9. Versions, ids, rights, strings

| Module | Version |
|---|---|
| `pb_scheme_map` | 19.0.2.7.0 |
| `pb_contracts` | 19.0.1.17.0 |

- New model `pb.person.scheme.fill` (`pb_scheme_map.model_pb_person_scheme_fill`), access rows
  `access_pb_person_scheme_fill_formula_user`, `…_payroll_user`, `…_hr_user` — read only (written under sudo).
- New field `hr.contract.pb_ps_check_amounts`.
- New proposal kind `person_unfill` ("Undo a pay scheme fill"); kind `person_set` payload may carry `groups`.
- New board methods: `person_set_many`, `team_plan`, `team_apply`, `team_own_people`, `fill_plan`, `fill_apply`,
  `fill_undo`, `fill_undo_write`, `mismatch_people`, `mismatch_change`, `contract_note_dismiss`.
- No new group, cron or menu.
- msgids: `pb_scheme_map` +179 (vi_VN 179, id_ID 179), 6 retired; `pb_contracts` 0.

## 10. Gotchas

Ledger §4 PS-a1..PS-a9.

Local state: `ps2a_w` (fast lane walk world, 247 people), `ps2a_w5` (second approver), `ps2a_dev`, `ps2a_a`
(after suite); `ps2a_b` and `ps2a_t` dropped. Walk and test servers stopped. Base databases untouched.

## 11. Files changed (for the merge with P2b)

`pb_scheme_map/`: `__manifest__.py`, `models/__init__.py` (4 lines appended), `models/pb_person_scheme_board.py`
(the lane-'none' fix only), `models/pb_scheme_map.py` (coverage reasons), new `models/pb_person_scheme_{many,fill,
team,follow}.py`, `security/ir.model.access.csv` (3 rows appended), `i18n/{pb_scheme_map.pot,vi_VN.po,id_ID.po}`
(entries appended, 6 removed), `static/src/js/{person_scheme,scheme_map_board,scheme_map_chip}.js`, new
`static/src/js/{person_fill,person_scheme_prompt}.js`, `static/src/xml/{person_scheme,scheme_map}.xml`, new
`static/src/xml/person_fill.xml`, new `static/src/scss/person_fill.scss`, `tests/__init__.py`,
`tests/test_static_contract.py`, new `tests/{p2a_common,test_p2a_board,test_p2a_fill,test_p2a_follow,
test_p2a_static}.py`, `tests/p2a_msgids.txt`. `pb_contracts/`: `__manifest__.py`, `static/src/{js/contract_360.js,
xml/contract_360.xml,scss/contract_360.scss}`. `docs/handovers/pscheme/PSCHEME_LEDGER.md`.
Expected conflicts with P2b: `pb_scheme_map/__manifest__.py` (version, assets/data lists), `models/__init__.py`,
`security/ir.model.access.csv`, the three i18n files, `tests/__init__.py` — all appends; take both.

## 12. Questions for the product owner (plain words)

1. **A team request where one person was changed in the meantime.** Today the whole request stops and names that
   person; HR presses once to ask again for the rest. Is that right, or should the others go through and only the
   changed person be left out?
2. **The one-time fill and contracts.** The fill only writes down who pays people today, so it never changes a
   contract. Some people's contracts may be in another currency than their pay scheme (it was already so). Should
   the fill also move those contracts, or leave them for HR to look at?
3. **People with no Country of work.** The fill asks you to choose for them (today's scheme is offered first)
   instead of giving them today's scheme by itself. Keep it that way, or give them today's scheme too?
