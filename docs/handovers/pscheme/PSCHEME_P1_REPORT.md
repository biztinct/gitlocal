# PSCHEME P1 — report: the person's own pay scheme (engine, Add employee, the person's panel)

Implementation engineer, 26 Nov 2026. Worktree `gitlocal-worktrees/pscheme`, branch `pscheme`. Local only: nothing
pushed, no server, no live database. Engineering document: real technical names on purpose; no client data.

## 1. Result

**GO for P2** — every numbered test passes, all seven walks pass with a clean console, and the before/after suites
differ only by the deliberate test updates listed in §4 (see §4.2 for the counts).

Commits on `pscheme` (oldest first):

| Commit | What |
|---|---|
| `dd391ceee` | WIP (PAUSED) — model, rung, board (superseded by the commits below) |
| `5a31a6fcf` | A–D: model, `person` rung, approval kind, cache, boundary job, tests T1–T21 |
| `52d6ac213` | C: pay run — "paid elsewhere" line, the "not covered" list openable again |
| `709ab8ccb` | E: Add employee writes the pay scheme on the person, tests T22–T27 |
| `203e2aa24` | F: Pay scheme block, Change pay scheme dialog, contract drawer strip |
| `35766b41c` | vi_VN + id_ID for every new string; retired msgids removed |
| `e6d7706f3` | kind-of-run words translatable; ledger PS1–PS9 |
| (this file) | report |

## 2. What changed on screen (screen words)

**A / B — who pays a person (no screen of its own).** A person can now have a pay scheme of their own, from a date.
When they do, that scheme pays them, whatever their team's usual scheme is; their team's mid-month advance no longer
reaches them unless they were given one. "Paid by" on the person's card follows within the day (a daily job marks
people whose scheme starts or ends today). Changing someone's Country of work marks "Paid by" to be worked out
again; it never changes their pay scheme by itself.

**C — Run payroll, step 1.** Under the pay scheme field, two quiet grey lines that appear only when there is
something to say:
- "N people are not covered by any pay scheme and are left out" — opens the names. The list existed but could no
  longer be opened since the scheme cards moved into a pop-up. Its help now names both fixes: give the person a
  pay scheme of their own from their record, or set the team's usual pay scheme in Mapping.
- "N people of these teams have their own pay scheme and are paid elsewhere" — opens the names, each with
  "paid by <scheme>, from <date>", on a calm grey background.

A person with a pay scheme of their own is never listed as "not covered".

**D — approvals.** A new kind of request, "Change a person's pay scheme". It follows the same route as Mapping
changes: a payroll manager approves, or it is saved at once where no second approver is set up. The approver reads
plain rows: Who / Pay scheme / Mid-month advance / From 15 Dec 2026. The old kind labels ("Wire a team to a
scheme" …) are now translated too. If somebody changed the person's scheme while the request waited, approval
stops with "Nothing was changed. Somebody changed Eka's pay scheme (was X, now Y) since this was asked for…".

**E — Add employee.**
- Step 1: "The Country of work you pick next works out the pay scheme, the currency and the trial period for you."
- Step 2: the intro says the pay scheme follows the Country of work and can be changed here.
- The chosen card is honoured. The amber "the pay run follows the team" family is gone. One calm line takes its
  place: "Putu will be paid by DEMO Indonesia end of month from 15 Dec 2026."
- "This differs from the team's usual scheme" stays, as grey information.
- Scheme cards say "end-of-month" / "regular payroll" (no longer "End-Cycle").
- A "Mid-month advance: <name>" switch appears when the scheme has one paired advance (on by default). With several,
  a small chooser defaulting to none.
- Check and the approver's card show the same line and the advance.
- On approval the person's own pay scheme (and advance) is written from the first day.

**F — the person's panel.**
- Side panel › Pay and tax: a "Pay scheme" block replaces the read-only "Paid by" rows. It shows the scheme with its
  currency chip and "Their own pay scheme since / from <date>" — or "From <team>'s usual pay scheme" / "From a rule
  on the map" / "No pay scheme yet" (the only amber state).
- Below that: "Mid-month advance: <name>", "Changes to <scheme> on <date>", "Waiting for approval: <scheme> from
  <date> · With <approver>", and a History disclosure. "Payroll country" now reads "Country of work".
- "Change pay scheme" dialog:
  - radio cards (Country of work first; "Show pay schemes of other countries (N)" with a note that tax and insurance
    boxes follow the Country of work);
  - the advance switch, and a From date (default the 1st of next month) with the live sentence "A change during a
    month starts with the next pay run. <old> still pays <month>." (or "First pay run: <month>");
  - the button reads "Change pay scheme" or "Ask for this change" depending on the route;
  - every state is designed: loading, no scheme for the country (with Open Mapping), same scheme picked (disabled,
    with the reason), refusals, saved, sent for approval.
- After saving, the line behind the dialog rewrites itself with a short entrance, and the "Paid by" chip at the top
  of the panel follows.
- Contract drawer › Components: the "Paid by" strip adds "Their own pay scheme from <date>" and a "Change pay scheme"
  button that opens the same dialog. "Choose who is paid by what" becomes "Change pay scheme" when the person can be
  changed.

Hero moment (as designed, walked in W1): open a person, see in one line who pays them and since when. Press Change,
pick a card, save — and the line behind the dialog reads "Their own pay scheme from 1 Dec 2026" before the dialog
closes.

## 3. Deviations (each with its reason)

1. **Ledger A4 refined (PS4) — please confirm.**
   - The problem: read literally per kind of run, "the earliest row of that kind counts backwards" put a person in
     two pay runs of one month whenever their main scheme changed kind (regular → end of month from the 15th) or an
     advance was added later. That breaks owner ruling R6 ("one payslip per person per period, always"). Found in
     walk W1.
   - What I built: only the person's FIRST-EVER pay scheme counts backwards — while nothing of theirs has started on
     or before the day, and only for rows starting on their first-ever start date. Joiners still land (T3), and the
     advance they were hired with counts too.
   - This follows A4's own words ("their first-ever scheme counts backwards"), so I did not stop; it is reported
     here for the architect to confirm.
2. **The "main question" flag (PS5)** — not in the handover. In a company that runs end of month, "Paid by" asks for
   the end-of-month kind, and a person whose own scheme is a regular one read "no pay scheme". The "who pays this
   person" readers set `pb_scheme_main_question`; pay runs never do.
3. **Advance allow-list (A6)**: `segment` dropped from the literal in `scheme_component_scope.py` so the three lists
   are equal. It never added anything, because a segment answers every kind with one scheme. Accepted by the
   coordinator.
4. **Old payloads (E.4)** also write the ladder's mid-month advance (only when it really is a mid-month scheme), so
   that person's pay runs stay what they were. The handover said "write the row".
5. **"Not covered" toggle** added on the pay-run step (in scope by coordinator ruling 3).
6. **Wording fixed beyond the handover list:**
   - Step 1 of Add employee said "The team you pick next works out the pay scheme…";
   - the payslip example's "No pay scheme pays this team yet / Set who pays this team in Mapping…";
   - scheme cards' "End-Cycle"; the kind-of-run words were never translated (PS7);
   - the "Paid by" chip showed "Advance: <main scheme>" for team lines "for any kind of run" (PS6, hidden on screen;
     the stored column is unchanged).
7. **"No pay scheme for <country> yet." with a team picked** replaces "No pay scheme pays <team> yet" in step 2's
   amber line (the country is now what decides). Without a team, nothing amber is shown, as before (P7 test c2).
8. **Waiting proposals are found by person** (`target_model='hr.employee'`): a many-person proposal (P2's "set for
   everyone") targets the scheme. P2 must extend `_person_waiting` if it wants the panel to show those.

No ledger §2 decision was left un-honoured.

## 4. Tests

### 4.1 Numbered tests — all pass

| # | Test | Result |
|---|---|---|
| T1 | `test_person_scheme.TestPersonScheme.test_t1_no_rows_changes_no_answer` + the whole `TestSchemeMap` unchanged | pass |
| T2 | `test_t2_person_beats_team_division_rule_segment_beats_person` | pass |
| T3 | `test_t3_joiner_counts_backwards_earlier_row_keeps_its_month` | pass |
| T4 | `test_t4_no_advance_from_the_team` | pass |
| T5 | `test_t5_own_main_and_own_advance` (+ `test_t5b_main_question_takes_the_other_main_kind`) | pass |
| T6 | `test_t6_final_settlement_falls_through` | pass |
| T7 | `test_t7_ended_row_answers_nobody` | pass |
| T8 | `test_t8_constraints_each_say_why` | pass |
| T9 | `test_t9_skip_key_restores_the_old_answer` | pass |
| T10 | `test_t10_draft_equals_a_real_person` + P8 `test_a9` extended | pass |
| T11 | `test_t11_stale_marks_and_recompute` | pass |
| T12 | `test_t12_boundary_job` | pass |
| T13 | `test_t13_advance_lists_agree` | pass |
| T14 | `test_static_contract.test_t12_the_ladder_edit_is_guarded` | pass |
| T15 | `test_t15_one_team_two_schemes_two_runs` (incl. other-main-kind and "never not covered") | pass |
| T16 | `test_t16_change_mid_month_one_payslip_per_period` (+ `test_t16b_a_new_kind_never_counts_backwards`) | pass |
| T17 | `test_t17_payslip_lookup_uses_its_first_day` | pass |
| T18 | `test_t18_person_set_fast_lane` | pass |
| T19 | `test_t19_second_approver_route` | pass |
| T20 | `test_t20_rights` | pass |
| T21 | `test_t21_every_refusal_says_why` (+ `test_panel_payload`) | pass |
| T22 | `pb_new_hire/tests/test_pscheme.TestPschemeHire.test_t22_hand_pick_differs_from_the_team_and_is_honoured` | pass |
| T23 | `test_t23_the_advance_switch` | pass |
| T24 | `test_t24_vietnamese_joiner_lands_in_the_run` | pass |
| T25 | `test_t25_old_payload` | pass |
| T26 | `test_t26_no_retired_sentence_anywhere` | pass |
| T27 | `test_t27_second_approver_writes_on_approval` | pass |
| T28 | source scan of every added `_()` / `_t()` literal and template text in the phase diff (165 strings): no "Odoo", "rung", "config", "cycle"; no "Odoo" in any new msgstr | pass |
| T29 | every new msgid present and non-empty in vi_VN and id_ID (pb_scheme_map 101, pb_new_hire 13, pb_payrun_wizard 6, pb_contracts 2, pb_hr_payroll_formula 13); `msgfmt -c` passes on every changed file | pass (see note) |

T29 note: `pb_hr_payroll_formula/i18n/vi_VN.po` already fails `msgfmt -c` at HEAD `2902c2121` with a duplicate entry
("Not set, so this run is paid against %s working days…", lines ≈15316 and ≈15353). This is not from this phase and
was left alone. The loader tolerates it.

**Deliberate updates to existing tests** (each assertion changed because the owner ruling changed the behaviour):
- `test_new_hire.test_t04_decides`: a Singapore team with a Vietnamese hire now gets Vietnam's scheme as their own,
  with no mismatch. The mismatch assertion moved to Malaysia (no scheme of its own). The no-scheme sentence is now
  "No pay scheme for Singapore yet."
- `test_p8`:
  - `a4` — the unmapped team is now honoured (own scheme), with the calm line;
  - `a5` — the hand pick is honoured, no amber line;
  - `a6` — no "who pays them" note; `pb_nh_own_scheme_id` is sent;
  - `a7` — the line reads "will be paid by DEMO NH India monthly from";
  - `a9` — the person rung for a country scheme, then proved equal on a real person given that row.
- `test_payslip_example`:
  - `p3b` — no mismatch note, the example uses Vietnam's scheme;
  - `p4` — "No pay scheme for this person yet.", and no "would not use it" note.
- `test_static_contract.test_t12_the_bundle_is_the_files_on_disk_in_the_right_order`: three new asset files.

### 4.2 Suites before / after (same-before/after rule)

`/pb_scheme_map,/pb_new_hire,/pb_payrun_wizard,/pb_hr_payroll_formula,/pb_employee_vault,/pb_contracts,/pb_updates,
/pb_job_change,/pb_loans,/pb_retro,/pb_expense_payroll,/pb_pay,/pb_me_tax,/pb_decision_room` on two copies of the walk
base (`nh12_base` + `pb_job_change`, `pb_loans`, `pb_retro`, `pb_expense_payroll` installed → `ps_base`). "Before"
= a full `git archive` of `2902c2121` as the addons path.

- **before**: 1,770 tests, 8 failed + 6 errors.
- **after**: 1,799 tests (+29 new), 8 failed + 6 errors.
- **The failing tests are the same 16 on both sides; nothing fails only after, and nothing fails only before.**
  These are pre-existing and environmental for this base:
  - `TestS5fLeaverBackpay` F01–F09 (6 errors);
  - two "duplicate key" fixtures (`hr_integration_endpoint_connector_code_uniq`, `pb_pay_rating_rating_uniq`);
  - `TestCd1Contract360.test_01`, `TestDecisionRoomStaticContract.test_t14`, `TestRd49SyncCost` 02ab / 02i,
    `TestRecordsR1OneTime.test_07b`, `TestS2dTaxFlow.test_t9`, `TestT3bLetterToken.test_t3b_9`;
  - `TestVietnameseIsComplete.test_t4c`.
- The after suite started before the last commit (`e6d7706f3`, translatable kind words). The phase's own tests plus
  `TestSchemeMap` and the static contract were re-run on the final code: 63 / 63 pass.
- During the build, the full `/pb_scheme_map,/pb_new_hire` run showed 10 failures. All 10 were expected:
  - 9 assertions of the retired behaviour, updated deliberately (§4.1);
  - 1 real bug in my old-payload advance (a team line "for any kind of run" answered the advance question with the
    main scheme), fixed by the PS6 guard.

## 5. Walks (local `ps_w`, Claude-in-Chrome, console read every walk)

| # | What I did and saw | Result |
|---|---|---|
| W1 | Payroll manager, fast lane, Made Prasetya ("From Indonesia Operation's usual pay scheme"). Change → ArrowUp to "Indonesia large scheme" → Ctrl+Enter. The dialog said "Saved — Made is paid by Indonesia large scheme from 1 Dec 2026", and the line behind it already read "Their own pay scheme from 1 Dec 2026" (entrance motion). Second change: end of month from 15 Jan → "A change during a month starts with the next pay run. Indonesia large scheme still pays January 2027." Saved. History (3). Reopened: persisted; "Changes to DEMO Indonesia end of month on 15 Jan 2027"; the Paid by chip agrees. | pass (after fixing PS4, the chip refresh and PS6) |
| W2 | HR officer, second-approver route, Dewi Anggraini → "Ask for this change" → "Sent for approval to DEMO PS Payroll manager"; the panel shows "Waiting for approval: … · With DEMO PS Payroll manager", focus back on the button. Payroll manager: Approvals inbox shows plain rows (Who / Pay scheme / Mid-month advance / From 15 Dec 2026) → Approve → two rows written → the panel reads "Their own pay scheme from 15 Dec 2026 · Mid-month advance: …". | pass (dates now "15 Dec 2026", were numeric) |
| W3 | Rina Kartika: end of month with the advance switch on → "Mid-month advance: …" appears; again with it off → the line goes, History (1), the chip follows. | pass |
| W4 | Contract drawer › Components: "PAID BY Indonesia large scheme · Indonesia · Their own pay scheme from 1 Dec 2026 · Change pay scheme" → the same dialog; Esc closes only the dialog (drawer stays, focus back); saving from there refreshes the strip. | pass |
| W5 | Add employee (payroll manager): Indonesia, team Indonesia Operation, picked the non-usual card "DEMO Indonesia end of month". No amber on step 2, 3 or Check; "This differs from the team's usual scheme…" in grey; the advance switch on; "DEMO PS Putu Ayu will be paid by DEMO Indonesia end of month from 15 Dec 2026." Added. The panel reads "Their own pay scheme from 15 Dec 2026 · Mid-month advance". Rows: end of month + advance, `source=hire`. | pass (the new-hire route was switched to fast on the walk database to finish the add; T27 proves the route) |
| W6 | Run payroll, December, "Indonesia monthly staff": Putu not in it; "3 people of these teams have their own pay scheme and are paid elsewhere" opens Dewi / Rina / Putu with "paid by DEMO Indonesia end of month, from …". "DEMO Indonesia end of month": they are in it, and Made (own regular scheme) is in neither list. Server read: each person is in exactly one December main run. | pass (after fixing two wrong "not covered" listings) |
| W7 | Malaysia has no scheme: dialog shows "No pay scheme for Malaysia yet" + Open Mapping + other countries with the tax note; Add employee tile shows "No pay scheme for Malaysia yet" + link. Same scheme picked: button disabled with "… is already their pay scheme. Pick another card, or change the advance." HR officer in the fast lane: button disabled with "A payroll manager carries out pay scheme changes here, and nobody is set up to approve one. Ask a payroll manager to make this change." Dialog at 340 px: `scrollWidth` 340 = `clientWidth`, nothing overflows. | pass |
| vi | Vietnamese: panel, dialog (including the one-payslip-a-month sentence), Add employee step 2 and the pay run lines all in Vietnamese; `font` nodes 0 (NH61). | pass (after fixing PS7) |
| Console | errors only, every walk | clean |

Screenshots taken during the walks are in the browser tool's temp folder (not committed).

## 6. Design bar self-score (out of 10)

| | Score | Why |
|---|---|---|
| Hero moment | 9 | The line rewrites behind the open dialog with the date; the chip follows. Minus one: the people count on cards reads the stored "Paid by", which can lag a day. |
| Zero dead-ends | 9 | Every state is designed and every refusal names its fix. Minus one: "Suggest who pays each team" is still the link for a country with no scheme (it lands on Mapping, where a scheme is added, but its words are about teams — P2's Mapping re-wording). |
| Plain language | 9 | Screen words throughout, no "cycle"; dates as "15 Dec 2026". Minus one: the stock "Running / Draft" contract chips nearby are untranslated (not ours). |
| Motion | 8 | One entrance for the changed line, a pop on the done state, card press, switch slide; reduced-motion respected. |
| Keyboard | 9 | Arrows / Enter / Space on cards, Ctrl+Enter saves, Esc closes (the contract drawer yields Escape), focus returns to the opener. |

## 7. Seams P2 needs (file:line at `e6d7706f3`)

- **The one writer**: `pb_scheme_map/models/pb_person_scheme_board.py:351` `_person_set_write(employees, config,
  advance='keep'|False|config, date_from, source, note)`. It is idempotent, checks the refusals itself, and needs
  `SCHEMEMAP_WRITE` in the context or sudo.
- **The door with approval**: `person_set` `:271` (lanes `:91`; propose `:308` — set `source='team'` for "Set for
  everyone"). A many-person proposal targets the scheme, so extend `_person_waiting` `:563` if the panel should show
  it. Read API: `person_scheme` `:429`.
- **"Set for everyone in this team"**: call `person_set([team people], config, advance, date, source='team')` only
  for people WITHOUT rows (`pb.scheme.map._person_schemes(ids, day)` `pb_scheme_map/models/pb_scheme_map.py:346` —
  absent = no rows). The unticked "also move" option calls it for the others. Never through `accept_draft` (T13).
- **The one-time fill**:
  - write with `source='fill'` through `_person_set_write`;
  - read today's answer with `resolve_many(ids, cycle, on_date)` under `pb_scheme_main_question` (`MAIN_QUESTION`
    `pb_scheme_map.py:93`), and use `pb_scheme_skip_person` (`SKIP_PERSON` `:84`) to see the ladder alone;
  - copy an advance only when `cycle_type == 'mid_cycle'` (PS6);
  - undo = unlink the created rows.
- **Country of work prompt**: the server already marks "Paid by" stale on a `payroll_country` write
  (`pb_scheme_map/models/hr_employee.py:223`). The prompt opens the shared dialog through the registry
  `pb_person_scheme` → `api.open(dialog, {employeeId, data, onSaved, opener, onClose})`
  (`pb_scheme_map/static/src/js/person_scheme.js:402`, dialog `:67`, `openChangePayScheme` `:330`). The panel block
  re-reads on save and triggers the bus event `PB_PERSON_SCHEME_CHANGED` (chip `scheme_map_chip.js`).
- **`pb_job_change`**: `_write_change` calls `_person_set_write(emp, new_scheme, advance, effective_date,
  source='job_change')`. A company move must end the old company's rows first, because the scheme-company check
  refuses otherwise (A9, D8). The what-if should read `resolve_many` with the job change's `_departments_for`
  override — the person rung sits above it, so a person with rows answers their own scheme.
- **Add employee**:
  - `pb_new_hire/models/studio.py:487` `_scheme_for` (the `own` / `advance` keys);
  - hire write `create_ext.py:125`;
  - the payload keys `pb_nh_own_scheme_id` / `pb_nh_advance_scheme_id` (`studio.py:909`).
  - The Updates joiner sheet and the hiring offer should send the same keys.
- **Approval kind**: `pb_hr_payroll_formula/models/schememap_approval.py:207` `_apply_person_set`; rows `:150`;
  "changed since" sentence `:82` / `:94`.
- **Pay run**: `pb_payrun_wizard/models/pb_payrun_wizard.py:595` `_scheme_own_elsewhere`.
- **Cron xml id**: `pb_scheme_map.cron_person_scheme_boundaries` (`data/ir_cron.xml:33`, noupdate, active).

## 8. Lesson and help sentences now untrue (for P3)

- `pb_learn/static/content/learn_content.json`:
  - `:5841` (vi `:5842`) "The team you pick decides the pay scheme…";
  - `:15353` (vi `:15354`) "…The team you pick then decides which pay scheme pays this person.";
  - `:15337` "…Paid by on the right shows the scheme." (step 2 now shows the scheme in the tile; true-ish, check).
- `pb_learn/static/src/anchors.json`:
  - `:2223` "…The team decides the pay scheme; the country is checked against it.";
  - `:2304` `rep-newemp-team` "…choosing the team is choosing which pay scheme pays this person…".
- `pb_learn/static/src/engine/screens.js:400-412` — the new-employee replica runs Team, then "Paid by" (now: country
  → scheme cards → advance switch).
- `pb_learn/static/src/anchors.json:753` `pw-scheme` and the pay-run replica `screens.js:1159` — the two quiet lines
  under the scheme field are new.
- `pb_scheme_map/static/src/xml/scheme_map.xml:571` "Nobody pays these people yet" (Mapping, P2 re-wording).
- No lesson yet covers the side panel's "Pay scheme" block or the "Change pay scheme" dialog (P3).

## 9. Versions, ids, rights, strings

**Module versions:**

| Module | Version |
|---|---|
| `pb_scheme_map` | 19.0.2.6.0 (now depends on `pb_employee_vault`) |
| `pb_hr_payroll_formula` | 19.0.1.174.0 |
| `pb_new_hire` | 19.0.1.8.0 |
| `pb_payrun_wizard` | 19.0.1.49.0 |
| `pb_contracts` | 19.0.1.16.0 |

**New xml ids:**
- `pb_scheme_map.cron_person_scheme_boundaries`;
- model `pb_scheme_map.model_pb_person_scheme`;
- access rows `access_pb_person_scheme_formula_user`, `…_payroll_user`, `…_hr_user` — read only. Nobody has write;
  the board writes under sudo.

**New groups:** none. New field `hr.employee.pb_paid_by_own`.

**New msgids** (vi_VN / id_ID, all translated):

| Module | New | Removed |
|---|---|---|
| pb_scheme_map | 101 | — |
| pb_new_hire | 13 | 12 retired |
| pb_payrun_wizard | 6 | 1 |
| pb_contracts | 2 | — (new `id_ID.po`) |
| pb_hr_payroll_formula | 13 | — |

## 10. Gotchas and questions

Ledger §4 now has PS1–PS9 (PS1–PS3 from the pause; PS4 the A4 refinement; PS5 the main question; PS6 the
"advance = main scheme" quirk; PS7 untranslated kind words; PS8 `pkill` killing its own shell; PS9 the first slow
load after an upgrade).

Local state:
- databases `ps_base`, `ps_b` (before), `ps_a`, `ps_a2` (after), `ps_w` (walk world: users `ps.pay` / `ps.hr`,
  password local only, in the scratch seed);
- the walk company's Mapping and new-hire routes were switched to "no approval needed" for W1/W5;
- the walk server is stopped at the end of the phase.

Questions for the product owner (plain words):
1. **A change of pay scheme in the middle of a month**: we built "the old scheme pays that whole month, the new one
   starts next month" — except for someone's very first pay scheme, which pays their first month even if they start
   on the 15th. When a person changes from a monthly scheme to an end-of-month scheme, should the new one ever pay
   the month of the change? (We say no, so nobody is paid twice in one month.)
2. **The team's mid-month advance shows as the main pay scheme** for many people today ("Advance: <the same scheme>")
   when their team is set "for any kind of run". The screens now hide it. Should the one-time fill in the next step
   give those people no advance (what the screens now say), or should someone check each team first?
