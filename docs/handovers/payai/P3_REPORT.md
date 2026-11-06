# PAYAI P3 — report (Red tier + Learn tie-in)

Implemented by Opus, 2026-10-12, against `P3_HANDOVER.md`. Nothing deployed to any live database. All clone runs
staged from `git archive HEAD` (PA38/PA41) into `/tmp/p3stage` on `Payobook19v2`, database `p0clone`, port 8099,
detached `systemd-run` units `p3-test-1…4`.

**Ship commit: `3ec1d7cb9`** — `pb_payai_actions` 19.0.2.1.0 → **19.0.3.0.0** (the only manifest that moved, bumped
only there, PA41). Commits of this phase (branch 19.1, not pushed):

| commit | what |
|---|---|
| `891eb193b` | fix(payai): P3-W1…W6 live-walk fixes (+ their tests) |
| `3b3cb40f0` | the Red tier + cards + tests + Learn tie-in — **labelled "wip"**: other sessions committed on top of it (`002dfdcc8`, `3d3fdbcb8`) before it could be reworded, and rewriting would rewrite theirs (PA44) |
| `2cd6298a0` | test: P1 tools-schema test counts the Red tools |
| `3ec1d7cb9` | ship: version bump; message describes the whole phase |
| (this) | docs: P3_REPORT.md + ledger PA43–PA50 |

## P3-W1…W6 (walk findings) — all done, `891eb193b`
| # | Finding | Fix | Test |
|---|---|---|---|
| W1 | "…for Retail End-Month for Vũ Khánh Chi only" — the scheme slot swallowed the person; the question echoed the name | `RunPayroll.normalise_texts` → `_split_people`: "<a> for/with/just <b>" splits when one side is a scheme the wizard's own list knows (`resolve_scheme`); "<x> only" with no scheme words → people. Month words are cut by spaces, not folded, so a name keeps its spelling (`_without_month`). People resolved through `eligible_preview(search=…)` on the chosen scheme (as the person); several → "Which person do you mean?" chips; unknown → "I could not find … among the people this scheme pays". Plan People row: **"Vũ Khánh Chi (1 of 3)"** (named people of all the scheme covers, `scheme_preview` without the shortlist); vals carry `employee_ids`. The clarify question echoes the said word only when ≤ 3 words AND every word is one the chips themselves use (`runner._echo_word`) — a name can never pass. Tools prompt + slot descriptions tell the model to keep people out of `scheme`. | `test_w1_people_split_and_one_person_run` (walk sentence end-to-end; **exactly 1 payslip**, for her), `test_w1b_people_ambiguous_and_unknown` |
| W2 | "A October 2026 run … already exists" | Title is now "**<scheme> already has a run for <month>**" (no article). Sweep: it was the only "A %s" title. | P2 test 02 (exact title), `test_w2_no_article_before_a_month` |
| W3 | unknown pay value → dead-end refusal | `_closest_fields`: ≤ 6 chips ranked by shared words then `difflib` ratio, sublabel "now <value>" / "not set" (read with the Records Desk's own `_probe`/`_read_cell`, as the person), a note "I could not find … These are the closest…", the door **Open People › Records**, and Cancel | `test_w3_unknown_pay_value_offers_the_closest` (chip → plan) |
| W4 | send payslips offered a Draft run | `resolve_run(states=('done',))` for send_payslips; none → "**No approved run for <month> yet.**" with the Runs board door (`_missing_card` honours the resolver's door) | P2 test 08 (updated), `test_w4_send_payslips_offers_approved_runs_only` |
| W5 | cancel on a clarify card left it `clarify` | `runner.cancel` accepts `planned` and `clarify` → `cancelled`, same audit line; every question card now carries a Cancel button; older question cards lose it when superseded | `test_w5_cancel_a_question` |
| W6 | "Expired" in the console | `payai.task.state` label `expired` → "**Not answered in time**" (label only) | `test_w6_expired_reads_plainly_in_the_audit` |

## Red tier (`payai/actions_red.py`)
| Action | word | reason | what it records |
|---|---|---|---|
| `approve_item` | APPROVE | optional note (typed in the card's Note box; "with the note …" in the sentence pre-fills it) | `pb.approval.inbox.decide(…, 'approve', note, expected_lock_revision, idempotency_key='payai-task-<id>')` |
| `send_back_item` | SEND BACK | required — from the sentence ("… because …", "…: …", "… — …") or one typed question "What should change? Type the reason." (≥ 6 characters, the facade's own floor) | `decide(…, 'return', reason, …)` → run back to draft with the note |
| `reject_item` | REJECT | required, same way ("Why is it rejected?") | `decide(…, 'reject', reason, …)` → run Rejected, payslips cancelled |

- **Item**: only the person's OWN inbox (`list_requests(tab='mine', scope='me')`). Words match title, process, kind,
  scope label, sender, frozen facts and (pay run) the run's name/scheme/division; a month must fall in the run's dates.
  One → plan; several → chips; nothing said → the one waiting / chips of what is waiting. Not in their inbox but
  visible (`tab='all'` scope `me`, then `org` when the inbox allows it) → **"This is not waiting for you"**: "“<title>”
  is waiting for <names> at "<step>"…", **Remind <first name>** chip(s) (≤ 3 seat holders) and **Open my approvals**.
  Nothing anywhere → "Nothing is waiting for your decision…" (+ chips of what IS waiting, when there is some).
  Somebody who cannot see the request learns nothing about it (test 2, plain user).
- **Remind** = the engine's own reminder: `biz.approval.outbox._queue('reminder', seat holder, …)` (the overdue cron's
  kind: on delivery a chatter note + a to-do), at most once a day per person and step, plus a `reminded` event in the
  approval trail under the asker's name ("Lan Payai asked PayAI to remind Minh Payai about …"). A second press the same
  day: "… was already reminded about this today." (PA48). It is a follow-up the server offered (`offer.actions =
  ['remind']`), never a catalogue Action (non-goal: no new Actions).
- **Red plan card** (rose header `--pbim-rose-soft`): title "Approve <request title>"; subtitle "Decide · your decision
  as <step> · PayAI cannot undo it"; slots: the request (origin pill), **Figures** as frozen at send-in (pay run:
  "N people · ₫X net" from `net_total`/`employee_count` — the run band, one pay-band rule; others: the drawer's detail
  rows "old → new", the card count, the amount), **Step** "HR Manager check, 1 of 2", **Then** "Finance release ·
  Finance Payai" / "Nobody: approving finishes it" / "<name> still has to approve this step too" / "Back to <sender>" /
  "It ends here"; one note on what happens next ("Nobody is paid by approving."); the typed-word block above the
  buttons; **Open my approvals instead** · Cancel. No "Do it" button exists on a Red card.
- **Who comes next** is read off the request's OWN frozen steps and seats, with today's hand-overs applied by
  `biz.approval.delegation.covering` — exactly what `engine._activate_next` opens (deviation 3). Test 3 pins the plan's
  promise to the live seat after the decision (07/07b pattern).
- **Confirm** (`runner.confirm(…, how, word, note)`, RPC `rpc_confirm_task(task_id, how, word, note)`): Red refuses
  `tap` and `voice` ("This one needs typing … A tap or a spoken yes never counts."), spoken "go ahead" included; the
  word is checked on the server (`' '.join(word.split()).upper() == confirm_word`); a wrong word answers an inline hint
  (`inline: True` → drawn under the box, never a toast), task stays planned; then expiry, one-in-flight, the gate
  (tier switch `payai_tier_decide`, Home screen, read on requests), a fresh plan + fingerprint (request, lock revision,
  live step, open seats) → changed → "Things changed since I showed you this plan" fresh card; then `decide` with the
  plan's lock revision and the task key. A lock/seat move in the very last instant → `registry.Stale` → fresh card,
  nothing decided (PA47). A second confirm → the stored done card; the engine key would also stop a second decision.
- **Independence rule**: the inbox's own `conflict` for the person → refused "Somebody else has to decide this" with the
  engine's sentence ("You were part of preparing or sending this in, so you cannot also approve it. Ask someone else,
  or ask for an exception to be set up."). If an exception exists the card says PayAI never uses one and offers the
  inbox. No exception grants, no reassign, no deciding for anybody else.
- **Result**: "Approved as HR Manager check. It moves to Finance release (Finance Payai). Nobody has been paid yet." /
  "Sent back to <sender> with your reason. The run is a draft again." / "Rejected. The run and its payslips are
  cancelled, and <sender> is told why."; doors Open the run · Open my approvals · Learn; audit line **"Recorded:
  approved by <name> via PayAI, typed confirmation, <time>."**; `payai.task.confirm_kind='typed'`; no undo.
- **Voice**: the plan is read back "This is a decision. I need you to type the word APPROVE on the card; voice cannot
  confirm it." and the card carries "This one needs typing" (design page).
- **Typed-word UI** (`PayaiTypedConfirm`, chat_patch.js + cards.xml): above the buttons; optional Note box (approve);
  hint "Type APPROVE to confirm. A spoken yes does not count here." with the Lucide keyboard; monospace box,
  placeholder = the word, focused when the card arrives (live plans only); button lights the instant the word matches
  (trimmed, any case, inner spaces collapsed), a soft pop on enable; Enter submits; wrong word → inline `role=alert`
  hint; narrow card → box and button one full row each. Reduced motion honoured.
- **Audit console**: `pb.audit.console._fetch_payai` (inherited inside pb_payai_actions) adds `badge: Typed
  confirmation` to typed rows; `static/src/xml/audit_badge.xml` draws a rose chip with the keyboard icon beside the
  actor (pb_audit itself untouched, so nothing else to deploy).

## Learn tie-in
| done card | scenario key | why |
|---|---|---|
| run_payroll | `sc_payrun` | "Run a pay run" (watch/try/do) |
| submit_run (sent / approved straight away) | `sc_payrun` | its last step is "Submit for approval sends it along its approval route" |
| approve_item / send_back / reject on a **pay run** | `sc_payslips` | "Read a pay run and its payslips" — what an approver does on the screen; **no scenario exists for deciding in the Approvals inbox** (P4 item) |
| decisions on other processes | none — the "Open my approvals" door instead | no fitting walkthrough |

**P2 bug found and fixed**: P2's done card sent `scenario: 'payrun'`; every scenario key is `sc_*`, `begin()` answers
`false` for an unknown key, so the button did nothing (PA43). Keys now come from `learn_action('<sc_key>')`; the chat
shows "That screen could not be opened…" when `begin()` answers false. Test 10 reads `learn_content.json` and asserts
each key exists, is not retired and has `watch`.

## Tests — `pb_payai_actions/tests/test_payai_p3.py` (+ P1/P2 updated)
Clone runs (`p0clone`, port 8099, `-u` = the modules tested, PA35):

| run | code | command | result |
|---|---|---|---|
| p3-test-1 | `891eb193b` (W fixes) | `-u pb_payai_actions --test-tags /pb_payai_actions` | `pb_payai_actions: 44 tests` · `0 failed, 0 error(s) of 38 tests` · 0 skipped · EXIT=0 |
| p3-test-2 | `3b3cb40f0` (Red) | same | `pb_payai_actions: 58 tests` · `1 failed … of 50 tests`: P1 `test_11` still capped the offered tools at Green+Amber → test updated (`2cd6298a0`) |
| p3-test-3 | `2cd6298a0` | `-u pb_payai_actions,pb_audit --test-tags /pb_payai_actions,/pb_audit` | `pb_audit: 12 tests 1.60s` · `pb_payai_actions: 58 tests 17.42s` · **`0 failed, 0 error(s) of 60 tests`** · EXIT=0 |
| **p3-test-4** | **`3ec1d7cb9` (ship)** | `-u pb_payai_actions,pb_audit,pb_payrun_wizard,pb_payroll_ai_insights --test-tags` the same four | `pb_audit: 12 tests 1.42s 1299 queries` · `pb_payai_actions: 58 tests 17.50s 17813 queries` · `pb_payroll_ai_insights: 128 tests 2.23s` · `pb_payrun_wizard: 71 tests 10.87s` · `9 failed, 14 error(s) of 227 tests` — **all 23 pre-existing**: 3 = PA11 vi_VN copy (`test_data_access.test_06`, `test_egress.test_04d/04e`); **20 = PA40** pb_payrun_wizard fixed-2026 tests (7 `test_run_adopts_the_period` incl. `KeyError: 'adopted'`, 8 `test_spreadsheet_step`, 5 `test_two_schemes_one_month`) because p0clone still holds the **3** done "Walk Sales Jun/Jul/Aug" 2026 runs (ids 1173–1175, checked by SQL after the run). pb_payai_actions and pb_audit: 0 failures, 0 errors, 0 skipped. `latest_version` on p0clone: pb_payai_actions 19.0.3.0.0 |

(The stats line counts 8 more than the methods: 13 P1 + 18 P2 + 7 W + 12 Red = 50 methods.)

| # | Test | Asserts | Result |
|---|---|---|---|
| 1 | `test_01_plan_card_for_the_seat_holder` | plan/decide/planned; title; "PayAI cannot undo it"; figures "1 person · … net" (frozen); "HR Manager check, 1 of 2"; "Finance release · Finance Payai"; typed word APPROVE + hint + note field; no `do`; vals = request, step, lock revision; nothing decided | pass |
| 2 | `test_02_not_the_approver` | sender (scope me) and an unrelated payroll manager (scope org) → "This is not waiting for you" naming Minh, chip "Remind Minh", inbox door; Remind → outbox `reminder` for the seat holder +1, `reminded` event under the asker; again → "already reminded", no second row; un-offered value → AccessError; a user who cannot see it learns no name; request still pending, no decision | pass |
| 3 | `test_03_typed_word_mismatch_then_match_then_twice` | "aprove" → inline hint, still planned, no decision; "  approve " + note → `decide` called **once** with `payai-task-<id>` (spy), reason = note; second confirm → done card, still one decision; plan's "Then" = live step + seat after the decision; outcome sentence; no undo | pass |
| 4 | `test_04_tap_voice_and_switch` | voice-asked plan read-back + "needs typing" note; `tap`/`voice` with the right word → "This one needs typing", still planned; spoken "go ahead" with the switch ON → "never counts"; `payai_tier_decide=False` → refused (Settings › PayAI can act), new asks refused; no decision | pass |
| 5 | `test_05_seat_moved_between_plan_and_confirm` | `pb.approval.inbox.move_it` to a backup → confirm → new task, "Things changed", refused naming Backup Payai, old task expired, no decision | pass |
| 6 | `test_06_independence_rule` | sender holds the first seat (no backup) → refused with the engine's sentence, no typed block, no decision | pass |
| 7 | `test_07_send_back_asks_for_the_reason` | no reason → typed question; the reason "Approve the overtime first, then send it again" (reads like an order) is taken as the reason on the SAME task (PA49); plan "Back to Prep Payai", word SEND BACK, no note box; "send  back" → returned, `return_note` = reason, run draft | pass |
| 8 | `test_08_reject_with_reason` | reason from the sentence; plan says payslips are cancelled; REJECT → request rejected with the reason, run `cancel` | pass |
| 9 | `test_09_lock_revision_moved` | joint step: the other half approves meanwhile → fresh plan, no decision; lock bumped inside Do it (patched `decide`) → `Stale` → fresh card, no decision; the fresh card then decides exactly once | pass |
| 10 | `test_10_learn_doors_carry_real_scenario_keys` | approve → `sc_payslips`; run payroll → `sc_payrun`; submit → `sc_payrun`; each key exists in `learn_content.json`, not retired, has `watch` | pass |
| 11 | `test_11_audit_under_the_persons_own_name` | task done/typed; audit line; decision `user_id` and `create_uid` = the approver; `decided` event "Minh Payai approved …", no "PayAI" in the engine trail; console row badge "Typed confirmation", actor Minh; an Amber row has no badge | pass |
| 12 | `test_12_no_back_door` | Home locked (Access-home `visibility_for`) → approve and reject refused `screen_off`; a plan made while on → refused at confirm once locked; no decision | pass |
| 13 | W1–W6 tests above | — | pass |

Weak-test review (a test that passes with its guard removed): checked each — removing the server word check, the
`how != 'typed'` refusal, the tier switch, the `mine`-only item search, the conflict refusal, `expected_lock_revision`,
the `Stale` handler, the idempotency key, the reason-first typed answer, the Home gate or the audit override each makes
its test fail. Tests 5 and 9-part-1 are covered by two guards (fingerprint at re-plan AND the `Stale` path at `decide`);
removing one alone still passes — the second guard is pinned on its own by test 9-part-2.

## Design bar (verbatim: "Extreme WOW, intuitive, out-of-this-world experience, best in class.") — self-score, code only
- Hero moment, the typed-word confirm: **4** — word in the hint, autofocus, instant enable with a soft pop, Enter
  submits, inline wrong-word hint, note box for the approver; not yet seen in a browser.
- Deliberate, not bureaucratic: **4** — one box, one word, the figures/step/next on the same card; no dialogs.
- Zero dead-ends: **5** — not yours → who + Remind + inbox; seat moved / lock moved → fresh card; wrong word → hint;
  voice/tap → "needs typing"; preparer → the engine's reason + the inbox; nothing waiting → what is waiting; W3/W4/W5.
- Plain language: **4** — screen words throughout, "Odoo" absent from every new string; EN only (P4 for VI).
- Lucide / locked palette (rose Red header) / no gradients / no emoji: **5**.
- Motion with purpose + accessibility: **4** — labelled input + `aria-describedby` hint, `role=alert` error,
  `aria-invalid`, reduced motion; spinner on the typed button while it works.

## Deviations (with reasons)
1. **Commit shape** — Red + Learn landed in `3b3cb40f0` labelled "wip" (PA44); the ship commit's message carries the
   description. No other module's history touched.
2. **Key `send_back_item`** replaces the P1 stub key `send_back` (the handover's name). `actions_stubs.py` keeps only
   the never tier.
3. **"Who comes next" from the request's frozen seats**, not `_route_steps`: `_route_steps` previews the published
   version as it reads today; a request follows the seats frozen when it was sent in (+ hand-overs at activation),
   which is what the card must promise. Test 3 holds the promise to the outcome.
4. **No `scope='everyone'`** on `get_request` (scopes are me/team/org): PayAI looks in `me`, then `org` only for people
   the inbox lets read the whole company. `team` is not used (P4 candidate).
5. **Remind** = the outbox `reminder` (the to-do is created by the outbox on delivery), not a direct `mail.activity`.
6. **Approve on non-pay-run processes** gets no Learn door (no fitting scenario); the inbox door instead.
7. **W1 echo rule** is "≤ 3 words, every word a chip word" rather than "no name-like token" (no reliable name test;
   the chip-word rule cannot echo a name).
8. **W3 current values** read with the Records Desk's private `_probe`/`_read_cell` (read-only, as the person).
9. **Audit badge inside pb_payai_actions** (inherit + template extension), so pb_audit needs no deploy.
10. Red adds `typed` to the card contract: `{id:'typed', word, label, hint, icon, note?:{label,value,placeholder}}`;
    inline answers carry `inline: True`.

## DEPLOY NOTES (Fable deploys — PA14 go-ahead; PA41 check `latest_version` before/after)
| module | version at ship `3ec1d7cb9` | stored field? | installed | upgrade |
|---|---|---|---|---|
| pb_payai_actions | 19.0.2.1.0 → **19.0.3.0.0** | **no new field**; `payai.task.state` selection LABEL "Expired" → "Not answered in time" (key unchanged) | **payobook only** | payobook only |

No other module changed in this phase (pb_audit, pb_learn, pb_payrun_wizard untouched by P3). Sequence:
`-u pb_payai_actions` on payobook → `DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'` → restart. SCSS was
compiled with the server's libsass on the staged tree: `sass ok 16378 … @container passed through`. **Red goes live the
moment it deploys**: `payai_tier_decide` is already ON for payobook's companies (P1 post_init, owner decision 2).
Stage from `git archive 3ec1d7cb9 pb_payai_actions`, never the working tree.

## WALK LIST for Fable on payobook.com (visible window, console open; PA24/PA42)
Before: Settings › PayAI can act — "may decide" on. Pick in Home › Approvals (My turn) a demo pay run waiting at its
FIRST of two or more steps for the login you walk with (a demo run, `is_demo`, so it can be put back). Note its
month and scheme words.
| # | Type (or do) | Expected |
|---|---|---|
| 1 | "Approve the <month> <scheme words> run" as the seat holder | rose-headed card "Approve <run title>", subtitle "Decide · your decision as <step> · PayAI cannot undo it"; Figures "N people · ₫X net"; Step "<step>, 1 of N"; Then "<next step> · <name>"; note "After you, it goes to … Nobody is paid by approving."; Note box; hint "Type APPROVE to confirm…" with the box FOCUSED; Approve button grey |
| 2 | type `aprove` | button stays grey; press Enter → inline red hint "That is not the word yet. Type APPROVE." (no toast) |
| 3 | clear, type `approve` | button lights the instant the word matches; Enter submits |
| 4 | before step 3, hold the mic and say "go ahead" | note "This one needs typing … A spoken yes never counts."; the card still waits for the word |
| 5 | after 3 | card turns green: "Approved as <step>. It moves to <next> (<name>). Nobody has been paid yet."; doors Open the run · Open my approvals · Learn to do this yourself (opens "Read a pay run and its payslips"); audit line "Recorded: approved by <you> via PayAI, typed confirmation, …" |
| 6 | Audit console › PayAI rows | the approve row shows the rose "Typed confirmation" chip |
| 7 | put it back (safe on demo data): as the NEXT step's holder say "Send the <month> <scheme> run back because walk test" (or withdraw it from the inbox as the sender) | send back: plan with Reason "walk test", Then "Back to <sender>", word SEND BACK; after it the run is a draft again |
| 8 | as somebody who is NOT on the route but can see it (the sender, or a payroll manager): "Approve the <month> <scheme> run" | "This is not waiting for you" naming the seat holder(s), chip "Remind <first name>", Open my approvals; press Remind → "Reminded <name> … Recorded."; press again (new ask) → "already reminded about this today" |
| 9 | "Send the <month> run back" with no reason | question "What should change? Type the reason."; type a reason → the plan, same card thread |
| 10 | "Run December 2026 payroll for Retail End-Month for Vũ Khánh Chi only" (W1) | plan with People "Vũ Khánh Chi (1 of N)", scheme said; Cancel |
| 11 | a run month that exists (W2) | "<scheme> already has a run for <month>" |
| 12 | "Give <person> a lunch stipend of 500,000" (W3) | "Which pay value do you mean?" + note + ≤ 6 chips "now …/not set" + Open People › Records + Cancel |
| 13 | "Send the <month with only a draft run> payslips" (W4) | "No approved run for <month> yet." + Runs board door; no draft chip |
| 14 | any question card → Cancel (W5) | "Cancelled · Nothing was done." with the audit line |
| 15 | a run's done card → Learn to do this yourself | the "Run a pay run" walkthrough starts (was silent in P2) |
| 16 | phone width / narrow drawer | the typed box and the Approve button one full row each |
Any "Odoo" on a card = fail.

## Open items for P4 (Vietnamese + close-out)
- VI for every P3 string (Red cards, typed hint, needs-typing note, Remind, W1–W6 copy) and the **VI confirm words**
  (e.g. DUYỆT / TRẢ LẠI / TỪ CHỐI — accept both EN and VI in `_norm_word`; fold diacritics).
- VI phrasings for approve / send back / reject and the reason tail ("vì …").
- A Learn scenario for deciding in the Approvals inbox (none exists; approve uses `sc_payslips` for pay runs only).
- The Approvals inbox has no deep link to one request (`openId` is component state): "Open my approvals instead"
  opens the list, not the request — add `pb_focus` support in `pb_approval_config/static/src/js/inbox.js`.
- `team` scope for the not-yours lookup (a line manager seeing their people's requests).
- Browser walk of the typed component (autofocus inside the helper drawer, history reload of a live Red card).
- Carried from P2: PA28 (`formula_config_id` to `compute_batch`), engine idempotency keys for Records / delivery /
  filing, PA32 (Compliance screen for officers without Government Reports), PA40 fixture debt (move pb_payrun_wizard
  tests to a far-future year), PA11 vi_VN copy tests.
