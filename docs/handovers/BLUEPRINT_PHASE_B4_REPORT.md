# BLUEPRINT Phase B4 — report

Built, tested, deployed and Chrome-validated 2026-09-10. Scope delivered in
full. The deferred items in §11 are the ones the handover already assigned to a
later phase, plus one measurement the automation bridge cannot take.

**Live on all four databases**: `pb_blueprint 19.0.1.3.0`,
`pb_formula_studio 19.0.1.184.0`, `pb_import_kit 19.0.1.19.0`,
`pb_hub 19.0.1.9.0`. `pb_hr_payroll_formula 19.0.1.124.0` and
`pb_pay_delivery 19.0.1.2.0` are unchanged from B3 — no engine change was
needed.

**Tests**: **106 Python** on p9clone (`--test-tags /pb_blueprint`), 0 failed
0 error, of which **14 are new**; plus `/pb_hr_payroll_formula:TestBracketLint`
4/4. In the browser, **67 hoot tests under `@pb_blueprint`, all green** — the
**four failures of BP36 are gone** (§5) and 22 of the 67 are new.

---

## 1. Acceptance cases

| # | Case | Result | Evidence |
|---|---|---|---|
| 1 | Connect renders three cards with the identity strip; statuses Not started; real coverage numbers on a Complete draft | **PASS** | Identity strip "Payobook Vietnam JSC · B4 Connect walkthrough `B4_CONNECT_WALKTHROUGH`" + "0 of 2 tasks done. Neither one has to be finished before you carry on." Cards: Source mapping **"0 of 52 inputs have a source"**, Payslip layout **"0 of 111 components placed · 46 in the tray"**, Approvals "Already in place". Both work cards offer Open · Skip for now · "Manage later: Settings → … · same configuration" |
| 2 | Open source mapping → studio on the draft → wire an input → back chip → journey at Connect, card highlighted, coverage 1 of N, In progress → Mark as done → Done | **PASS** | Mapping Studio header **TO "B4 Connect walkthrough · 52 input columns · VN · draft"**, Journey tab, chip "New configuration". Wired `HRSWD` → employee **Badge ID** (board reported "1 mapped"). Back → Connect, coverage **"1 of 52 inputs has a source · 1 from employee records"**, pill **In progress**; the purple ring was observed by a MutationObserver on arrival and had faded by 1.4 s. "Mark as done" → **Done** |
| 3 | Add a component → Connect → mapping card "Needs another look" naming the new input; re-mark → Done | **PASS** | Added "Site allowance" through Add component; its approved-amount recipe provisions the input `SITEALLOWAIN`. Card: **Needs another look**, *"1 component was added since you mapped: SITEALLOWAIN"* + *"Open it again to take care of them, then mark it done."* Re-marked → **Done**, message gone |
| 4 | Open payslip designer → studio opens WITH the overlay already open on the draft; place a component; close → journey again at Connect; coverage; In progress → done | **PASS** | Designer opened on "B4 Connect walkthrough", **UNPLACED · 47**. Dropped "Take-home pay" into a new section. Close → **journey at Connect**, coverage **"1 of 113 components placed · 45 in the tray · 1 section"**, pill In progress → Done |
| 5 | Remove a placed component → payslip card "Needs another look" listing it | **PASS** | "Field bonus" placed, marked done, then removed on the Components tab → **Needs another look**, *"1 component you had placed has gone since: FIELDBONUS"*. (First attempt read Done, correctly — see BP40) |
| 6 | Skip for now → Skipped + Undo; Skip the rest → only Not-started flips; Continue lands on Outputs | **PASS** | Skip → **Skipped** + *"Skipped for now. Nothing is weaker for it — you can come back whenever you like."* + **Undo skip** → Not started. Then mapping opened (In progress) and **Skip the rest & review outputs** → mapping stayed **In progress**, payslip became **Skipped**, and the journey landed on **step 4, "Nothing hidden. Nothing assumed."** |
| 7 | Approvals card: pill, text, "How approvals work today" modal; no button | **PASS** | Pill "Already in place" (teal), the owner's sentence verbatim, the chain **Officer review → HR review → Finance approval** as chips, and the modal's three numbered lines. **No button and no skip** on the card. Escape closed the modal and left the journey on step 3 (BP20) |
| 8 | Uninstall guard: remove `pb_mapping_studio` from the registry → explanation, no dead button | **PASS** | Card: *"The mapping screen is not installed on this database, so there is nothing to open. Everything else on this step still works."*, **zero buttons**; the payslip card kept both of its. Registry entry restored afterwards |
| 9 | Refresh on Connect → same statuses; other-company draft → refusal | **PASS** | `?config_id=587` reload → step 3, pills `Done · Needs another look · Already in place`. A configuration that does not exist: *"That configuration no longer exists. It may have been deleted."* — same `_guard`, untouched; the other-company branch is B1's, still covered by `test_blueprint.py`. **The URL was broken on the first build and fixed — BP38, §5** |
| 10 | 390 px: cards stack; doors reachable; back chip visible in both studios | **PASS** | At the bridge's floor of **500 px**: `pbbp-cn-grid` is one column of 397 px, the skip strip goes vertical, the rail lies down as a horizontal stepper, the pay panel becomes a bottom bar, both doors reachable, and `documentElement.scrollWidth === clientWidth` and `body` likewise. A device-accurate 390-px capture is not something this bridge can take (B2 §11.4) |
| 11 | abm: the same round-trips on a fresh draft; all four DBs on the new versions | **PASS** | On **abm**: identity strip "AB Mauri", 52 inputs / 111 components / 46 in the tray, hero 27.04m VND. Mapping round trip (wired `HRSWD` → Badge ID, back chip, "1 of 52 inputs has a source · 1 from employee records") and designer round trip (opened with the overlay, closed → journey) both work. Versions and tree hashes in §8. **0 console errors** on either database |

**11 PASS · 0 FAIL.**

Vocabulary sweep of the step and its modal, including `title` / `placeholder` /
`aria-label` / `alt` and both disclosures opened: **3,111 characters**, **0** hits
for Odoo, schema, blueprint, config or rule set. **0** console errors on payobook
and on abm.

Both walkthrough drafts on payobook and the one on abm were discarded through
the product's own path; the estate is back to B3's baseline (payobook 22
configurations / 3 setup rows, abm 1 / 0).

---

## 2. The mapping-model field names used, per lane

Verified against the live models before coding, as the handover asked.

| Lane | What it means on screen | Where the fact lives |
|---|---|---|
| **api** | "from the connected system" | `hr.integration.field.mapping.target_rule_id` (active rows only — `active` exists on that model and the default search honours it), **plus** any component that declares `feed` or `rule` through `hr.formula.rule.declared_sources()` |
| **excel** | "from spreadsheets" | a declared source of kind `excel` with a non-empty key (`hr.formula.rule.source_ids`, read through `declared_sources()`) |
| **records** | "from employee records" | `hr.payslip.import.mapping` with `salary_structure_id = <config>` and `component_id in <inputs>`, **plus** declared `employee_field` / `contract_field` / `bank_account`, **plus** `is_contract_component` |
| **cycle** | "carried from the mid-month run" | `hr.payroll.cycle.component.mapping` with `end_cycle_config_id = <config>` and `end_component_id in <inputs>` (active rows only) |

Two deliberate choices, both stated because they change the number:

- **It is a UNION of what a component DECLARES and what somebody DREW**, not
  either alone. On these databases the two are recorded independently — a wire
  can exist without an S3 binding and a binding without a wire — and counting
  only one of them would tell a person their work had not been saved. The
  declared half is the only way the "from spreadsheets" figure can ever be
  non-zero, because a spreadsheet column is a binding and not a row in a
  mapping table.
- **Inputs only.** `rule_ids.filtered(column_type == 'input')`. A calculated
  column works its own value out and a fixed value already has one, so counting
  them would inflate coverage with components nobody has to connect — asserted
  by `test_readiness_counts_every_lane_and_only_inputs`, which draws a wire onto
  a formula rule and checks the number does **not** move.

Payslip placement reads exactly what the designer itself reads
(`pb.formula.studio.payslip_studio_data`): `appears_on_payslip` **and**
`payslip_identifier` is **placed**; `appears_on_payslip` with no section is the
**tray**; sections are `hr.payslip.config` rows bound by `salary_structure_id`.

---

## 3. The `optional_status_json` shape

```json
{
  "mapping":  {"status": "not_started|in_progress|configured|skipped",
               "opened_at": "2026-09-10 07:41:02",
               "done_at":   "2026-09-10 07:44:19",
               "snapshot":  ["ADJDEDAMT", "ANNUALDAYS", "..."]},
  "payslip":  {"status": "…", "opened_at": "…", "done_at": "…",
               "snapshot":     ["NET", "FIELDBONUS"],
               "snapshot_all": ["ADJADD", "ADVANCE", "..."]},
  "approvals": {"status": "info"}
}
```

Four things about it:

- **`needs_review` is never stored.** It is what `bp_readiness` says about a
  `configured` task whose components have changed since, and a stored copy of
  that answer is a copy that goes stale the moment somebody adds a component.
  `stored_status` is returned beside `status` so the difference is visible; a
  test asserts the stored word stays `configured` while the shown one is
  `needs_review`.
- **`snapshot` is what was true when somebody pressed "Mark as done"** —
  the input codes for mapping, the placed codes for payslip. `snapshot_all` (a
  superset of the handover's shape, and the one addition to it) is every
  component code at that moment, which is what makes "3 components were added
  since you arranged the payslip" answerable as well as "1 you had placed has
  gone".
- **An EMPTY snapshot means "we do not know", not "there was nothing".** A
  draft finished before this phase carries a status and no snapshot; without
  this it would be told every component in the configuration had just been
  added. Found by a test, not by a user.
- **B1's one-word shape still opens.** `optional_status()` coerces
  `{"mapping": "configured"}` into the dict, once, so nothing downstream ever
  sees a bare string. `test_a_draft_from_before_this_phase_still_opens` asserts
  it on a real draft.

`bp_task_open` stamps `opened_at` and lifts `not_started`/`skipped` to
`in_progress` without bumping the revision — opening a door is not a change
anyone can conflict with. `bp_task_set` and `bp_skip_rest` do bump it: deciding
that something is finished is exactly the kind of thing two people can disagree
about.

---

## 4. Every `pb_formula_studio` line touched

Two seams, both minimal, both listed here as the handover requires. **`pb_formula_studio/models/pb_formula_studio.py` was NOT touched** (binding rule 7).

| File | Where | Before → After |
|---|---|---|
| `static/src/js/formula_studio.js` | the import line, `:44` | `import { HubBackChip, hubBack, openHub } from "@pb_hub/js/hub_nav";` → the same plus **`goBack`** |
| `static/src/js/formula_studio.js` | the `onWillStart` arrival block, immediately after the `peopleSignal` line (was `:605`, now `:605-616`) | *(nothing)* → 12 lines, 6 of them the comment: read `pbfs_open_payslip` from `a.params` **or** `a.context`, remember `hubBack(this.props)` as `this._psBack`, and `await this.openPayslip()` |
| `static/src/js/formula_studio.js` | `closePayslip()` (was `:4756`, one line, now `:4767-4785`) | `closePayslip() { this.state.psOpen = false; }` → the same first line, then: if `this._psBack` is set, clear it and `goBack(this.action, back)`. **The old behaviour is untouched when no `pb_back` is present** — the designer opened from inside the grid still just closes |
| `__manifest__.py` | `:5` | `19.0.1.183.0` → `19.0.1.184.0` |

Two other modules ship with this phase:

| File | Where | Before → After |
|---|---|---|
| `pb_hub/static/src/js/hub_nav.js` | before `HubBackChip`, `:104-124` | *(nothing)* → **`export function goBack(actionService, back)`**, 21 lines with its comment: the chip's own click logic, extracted |
| `pb_hub/static/src/js/hub_nav.js` | `HubBackChip.goBack()`, was `:143-150` | five lines of `openHub(...)` → `goBack(this.actionService, this.props.back);` — **one implementation, not two that must never drift** |
| `pb_hub/__manifest__.py` | `:44` | `19.0.1.8.1` → `19.0.1.9.0` |
| `pb_import_kit/static/src/js/import_icons.js` | end of `IC`, `:272-278` | *(nothing)* → **`layoutList`** and **`checkCheck`** (W2: icons live in the one registry, which means the kit ships with the phase that adds one — BP17) |
| `pb_import_kit/__manifest__.py` | `:12` | `19.0.1.18.0` → `19.0.1.19.0` |

---

## 5. How auto-return on designer close is wired, and the three defects the browser found

**The wiring.** The Connect card opens Formula Studio by tag with
`params/context: {config_id, pbfs_open_payslip: true}` and
`additionalContext: {pb_back: {label, tag: "pb_blueprint", context: {config_id,
step: "connect", task: "payslip"}}}`. The studio's arrival block reads the key,
records `hubBack(this.props)` and opens the overlay. `closePayslip()` then calls
`goBack(this.action, back)` — **the same function the back chip's click handler
calls**, extracted for this purpose rather than copied. Nothing about the
designer's own behaviour changes when it is opened the ordinary way, because
`_psBack` is only ever set by that one arrival key.

The journey's side of the door: `_arrival()` now also reads `step` and `task`,
`resume()` honours the step a studio names (it beats the step the draft was
saved on — the person pressed a chip that said "New configuration", and landing
them anywhere else would be the chip lying), and the named card is ringed for
1.4 s while its numbers are re-read from the server rather than trusted.

**Three defects the browser found that code review did not:**

1. **`?config_id=N` was wiped from the URL on the way back**, so a refresh after
   returning from either studio landed on an empty journey. `_rememberInUrl`
   runs in `onWillStart` and the action manager writes its own route state a
   moment later at mount; that only leaves the draft alone for a door carrying
   it in `params`, which is the picker's Resume button and **no return door** —
   `pb_back` travels in the context. Re-asserted in `onMounted` (**BP38**).
2. **A card said "You opened it, and nothing is connected yet" directly under a
   coverage line reading "1 of 52 inputs has a source"** — at exactly the moment
   somebody is looking for confirmation that their work landed. The hint is now
   a function of the same numbers the card shows (**BP39**), and a hoot test
   holds it there.
3. **A person who opened a door and changed their mind had nowhere to go.**
   "Skip for now" was offered only on a task nobody had touched, so an
   `in_progress` card had no skip and no undo. It is offered on both now.

---

## 6. BP36, settled

**All 67 hoot tests under `@pb_blueprint` are green**, including the four in
`blueprint_steps.test.js` that B3 diagnosed and could not fix. Confirmed twice,
in two separate tabs, on a freshly built bundle.

The guard was **correct all along**, and this is the useful half of the answer:
`beforeEach` at a test file's top level registers on hoot's GLOBAL callback
registry (`web/static/lib/hoot/core/runner.js:725-734` — with no current suite
it lands on `this._callbacks`), so it runs before every test in the session; and
the runner's order is `fifo` by default (`hoot/core/config.js:171`), so a run is
deterministic rather than a lottery that happened to come up green. The failing
run was therefore reading an **older `web.assets_unit_tests` bundle than the one
on disk** — a hoot result is only as fresh as the bundle that tab loaded
(**BP37**).

To take the whole class off the table rather than merely observe it absent,
`connect_text.js` builds **every** `_t()` inside a function. A label created at
module scope is a lazy `TranslatedString` whose `valueOf()` can refuse; one
created at call time, with the flag set, is an ordinary string. None of the 22
new tests can hit the lazy path at all.

The only red in a run filtered on `pb_blueprint` is
`@html_builder / custom_tab / builder_components / builder_number_input /
sanitized values / clamp to min value when pressing down arrow with min > 0`,
which times out after 5 s under load. It is Odoo's own test, it is not in this
programme's tree, and it passed in the run before it.

---

## 7. Tests

**Python — `pb_blueprint/tests/test_connect.py`, 14 new, all green.**

| # | What it holds | 
|---|---|
| 1 | `bp_readiness` counts every lane and only inputs; an API mapping and a record mapping give `mapped 2` with the right lanes; **a wire onto a calculated column does not move the number** |
| 2 | the fourth lane: a mid→end cycle mapping counts, on a draft created as `end_cycle` |
| 3 | a configuration with no components says so rather than showing zeroes |
| 4 | placing two components moves placed/tray/sections; **deleting the section returns them to the tray**, not off the payslip |
| 5 | the status machine walks and reverses: not_started → opened → in_progress → configured; a new input → `needs_review` with `changed_since == ['B4SITEDAYS']` while the STORED word is still `configured`; re-mark clears it; skip and undo |
| 6 | `bp_skip_rest` touches only `not_started`, and a second press says nothing happened |
| 7 | `bp_task_set('configured')` with zero coverage is refused **for both tasks, by name**, and nothing is written |
| 8 | approvals can be neither opened nor skipped |
| 9 | the approvals card names three stages and says what each does |
| 10 | a draft from before this phase — one word per task — still opens, and is not told every component is new |
| 11-14 | source assertions: both doors open BY TAG with `pb_config`/`pb_mode` and a `pb_back` carrying `config_id` + `step: "connect"`; never by xmlid; the registry guard is present; the studio reads `pbfs_open_payslip` from params **or** context and `closePayslip` returns only when `pb_back` exists; the chip and the designer share one `goBack`; `step_thin` no longer claims `connect` |

The white-label gate now also scans the whole `bp_readiness` payload: this step
renders two things it did not write — the mapping screen's own refusal and the
approval stage names, which are read from the pay-run screen's field labels so
this card can never name a stage the board does not (BP34).

**Hoot — `pb_blueprint/static/tests/connect_text.test.js`, 22 new, all green.**
Six suites: the status words (every state has a word and a class of its own, an
unknown one reads as *not started* and never as *done*), the coverage line (only
the lanes with something in them are named; singular and plural; nothing to map
is said in words rather than as "0 of 0"), the payslip line, what changed since
(the codes are named because a count alone is not actionable; a long list is cut
and says it was cut), and what a person may press.

**Whole suite**: 106/106 Python on p9clone, 67/67 hoot under `@pb_blueprint`,
plus `TestBracketLint` 4/4. B1's 23, B2's 56 and B3's are all among them and all
still green.

---

## 8. Deploy

Ledger ritual: clean `/tmp/bp_stage`, scoped per-module `rsync --delete`,
`pg_dump` per database before the upgrade, detached upgrade per database, asset
purge plus a `web.assets.version` bump, service restart, never `pkill`, never
`--delete` into the addons directory itself.

Dumps before the upgrade: `/tmp/bp4_dumps/payobook.dump` (53 M), `abm.dump`
(17 M), `payobook_template.dump` (11 M).

| Database | Upgrade | Exit | ERROR / CRITICAL |
|---|---|---|---|
| payobook | ok | 0 | **0** |
| abm | ok | 0 | **0** |
| payobook_template | ok | 0 | **0** |

p9clone was upgraded three times by the test runs, every one exit 0. Two further
asset-only rounds followed as the browser found the three defects in §5 (JS and
QWeb live in the bundle, so a purge and a restart is the whole deploy for them).

Final state — manifest vs `ir_module_module.latest_version`, all four:

| Database | pb_blueprint | pb_formula_studio | pb_import_kit | pb_hub |
|---|---|---|---|---|
| p9clone | 19.0.1.3.0 | 19.0.1.184.0 | 19.0.1.19.0 | 19.0.1.9.0 |
| payobook | 19.0.1.3.0 | 19.0.1.184.0 | 19.0.1.19.0 | 19.0.1.9.0 |
| abm | 19.0.1.3.0 | 19.0.1.184.0 | 19.0.1.19.0 | 19.0.1.9.0 |
| payobook_template | 19.0.1.3.0 | 19.0.1.184.0 | 19.0.1.19.0 | 19.0.1.9.0 |

Tree hashes repo vs server, byte-identical: `pb_blueprint 1a98ad4ccd88d173`,
`pb_formula_studio d917d5477463bf20`, `pb_import_kit 28d45ea5a9afe60a`,
`pb_hub f583a448c65a2175`.

**Errors and how they were resolved**: one test failure on the first run — an
empty snapshot was being read as "there was nothing" rather than "we do not
know", so a legacy draft was told all eight of its inputs had just been added
(fixed, §3) — and the three browser defects in §5. Zero ERROR or CRITICAL from
module loading on any database, on any round.

---

## 9. Gotchas added to `BLUEPRINT_LEDGER.md`

**BP37** the four BP36 failures were a stale unit-test bundle, not a broken
guard — with the two facts that prove a hoot run is deterministic, and the rule
that removes the class (every `_t()` inside a function) · **BP38**
`router.pushState` from `onWillStart` is overwritten at mount for any door whose
payload travels in the context · **BP39** a status hint must be a function of the
same numbers the card shows · **BP40** "needs another look" can only be proven by
changing something that was in the snapshot.

---

## 10. Commits

Six, in the order each piece was verified, with explicit paths and nothing
unrelated staged (the `RIZE/` and `design_poc/` trees were never touched):

1. `feat(blueprint): the Connect step's server half — readiness, status, doors`
2. `feat(import-kit): layoutList and checkCheck in the one icon registry`
3. `feat(hub): expose goBack(), the click handler behind the back chip`
4. `feat(blueprint): step 3 becomes the Connect step, not a placeholder`
5. `feat(formula-studio): open the payslip designer on arrival, and return on close`
6. `test(blueprint): the Connect step, in Python and in the browser`

Plus this report and the ledger gotchas. **Nothing has been pushed.**

---

## 11. Deferred, with reasons

1. **No approval matrix, no change to `pb_payruns` / `biz_approval_chain`** — a
   binding non-goal, and the owner's ruling. The card is information and says
   so; the modal reads the three stage names from the pay-run screen's own field
   labels, so it cannot drift from the board.
2. **No new mapping editor and no new payslip editor** (BP-R8). Both doors open
   the tool that already exists, on this draft, with a way back. Nothing of
   either studio's code was copied.
3. **No bilingual label editing beyond what the payslip designer already
   offers** (BP-R9), and **no Vietnamese `.po`** — B6, as scoped. Every visible
   string is inside a literal `_t(...)` or QWeb text, and `connect_text.js` puts
   every one of them inside a function so the extractor sees a real literal.
4. **The Outputs and Test steps** stay thin panels — B5, as scoped. `step_thin`
   now serves only those two.
5. **A hoot test that mounts the Connect step.** The 22 new ones cover the pure
   layer — every sentence the cards say. Mounting the component needs a mocked
   `pb.blueprint.studio`, the same fixture B2 and B3 deferred; the behaviour is
   covered live in cases 1–11 meanwhile, and B5 is the phase where one fixture
   would serve three surfaces.
6. **A device-accurate 390-px capture.** The automation bridge floors the page
   viewport at 500 px on this machine (B2 §11.4, B3 §12.5). The breakpoints
   under test are 1100 px and 899 px, so the phone layout was genuinely
   exercised; I have not claimed a 390-px shot.
7. **An end-to-end spreadsheet mapping.** The wire drawn in cases 2 and 11 is an
   employee-record destination, which is the lane the Employee & contract board
   creates by clicking. Wiring a spreadsheet column needs an uploaded import
   batch, which is the workbook fixture B1 §8.1 already deferred to the phase
   that re-skins that screen. The `excel` lane is covered by the coverage-line
   tests and by the lane test's by-lane assertions.

---

## 12. Owner items

1. **The temporary validator user is still switched on**, unchanged from B1, B2
   and B3: `look.p4@payobook.com` on payobook and abm, password
   `BpB1validate!2026`. Say the word and it is archived — or better, tell me the
   working administrator password and it can go for good.
2. **The three demo configurations B1 and B3 left on payobook are untouched.**
   Everything this phase created — two drafts on payobook, one on abm — was
   discarded through the product's own path, so the estate is back to 22
   configurations on payobook and 1 on abm.
3. **B3's owner questions (its §13) are still open** and were not acted on, as
   the handover instructed.
4. **Nothing has been pushed.** Six commits this phase, on top of the nineteen
   from B1–B3 and the ~104 the branch was already carrying.

---

## 13. Self-score against the bar

> "extreme WOW, intuitive, out-of-this-world experience, best in class."

- **Hero** — 8/10. The hero of this phase is the round trip: press one button,
  land inside a tool that is already scoped to your draft, do one real thing,
  press the chip, and the card you left is ringed with a number that has
  *moved* — "0 of 52 inputs have a source" becomes "1 of 52 inputs has a source
  · 1 from employee records" without anybody typing a status anywhere. It works
  in both directions and on both databases. Two points off because the step is
  three cards rather than one picture: the money-flow strip B5 brings is what
  will make the whole journey sing, and this step is deliberately quiet
  underneath it.
- **Zero dead-ends** — 9/10. Every state is designed and was walked: nothing to
  map, nothing to place, a tool not installed, a draft the mapping board cannot
  select, a task opened and abandoned, a task skipped and un-skipped, a task
  finished and then undermined by a change (both ways — something added, and
  something placed that has gone), a configuration that no longer exists, a
  refresh, and 500 px. The "Manage later: Settings → …" line on every card is
  the small thing I am most pleased with: the commonest fear at this point in a
  setup is that "not now" means "never", and one muted sentence answers it. Half
  a point off for the skip that was missing on an in-progress card until the
  browser found it, and half for the fact that a *Done* task cannot be put back
  to *Not started* — arguably right, but it is a door I did not think about
  until writing this.
- **Plain language** — 9/10. 3,111 characters swept, zero banned words, and the
  defect I am gladdest of is the one no gate could catch: a card contradicting
  its own number. Every refusal names the thing and the next step — "Nothing is
  connected yet, so there is nothing to mark as done. Open the source mapping
  and point at least one input at where its value comes from." A point off
  because "0 of 2 tasks done. Neither one has to be finished before you carry
  on." is two sentences where a better writer would need one.
- **Motion with purpose** — 8/10. The ring on the returned card, and nothing
  else: it fades over 1.4 s, it is the only thing that moves on this step, and
  it exists solely to answer "where was I". `prefers-reduced-motion` is honoured
  through B1's blanket rule. Unchanged from the existing toolkit rather than
  extended, which is the right call for a step whose job is to be quiet.
- **Keyboard and bulk** — 7/10. Enter stays inside the step rather than walking
  off it (BP20), the modal takes focus on mount and answers Escape, tab order is
  sane, and "Skip the rest" is the bulk gesture this step actually needs. Three
  points off: there is no keyboard route between the three cards beyond tab, and
  no shortcut for the two doors.

**With one more hour**: (a) let a *Done* task be reopened, so the only
irreversible thing on the step stops being irreversible; (b) put the coverage
number in the rail's Connect hint, so the step reports itself from two steps
away; (c) shorten the identity strip's progress sentence to one clause.
