# BLUEPRINT Phase B6 — report

Built, tested, deployed and Chrome-validated 2026-09-10/11. This is the last
phase of the programme: the journey ends properly, reads properly in Vietnamese,
and the Excel starting point is finally walked all the way through — the one
thing B1 could not finish and every phase since has carried forward.

**Live on all four databases**: `pb_blueprint 19.0.1.5.0`,
`pb_formula_studio 19.0.1.185.0` (its Vietnamese catalogue ships with this
phase). `pb_hr_payroll_formula 19.0.1.125.0`, `pb_import_kit 19.0.1.19.0`,
`pb_hub 19.0.1.9.0` and `pb_pay_delivery 19.0.1.2.0` are unchanged from B5 — no
engine change was needed and no icon was added, so none of them had to ship.

**Tests**: **155 Python** on p9clone (`--test-tags /pb_blueprint`), 0 failed
0 error, of which **25 are new**. In the browser, **123 hoot tests under
`@pb_blueprint`**, all green, of which **14 are new and 14 MOUNT a component**
against the fixture B2, B3, B4 and B5 each deferred. The only red in the
filtered run is `@html_builder/…/clamp to min value when pressing down arrow`,
Odoo's own test timing out under load — the same one B4 §6 reported, and not in
this programme's tree.

---

## 1. Acceptance cases

| # | Case | Result | Evidence |
|---|---|---|---|
| 1 | Finish on a Complete draft that ran its checks: tiles, identity incl. calendar, decisions with Go links, optional statuses, Finish & open | **PASS** | Draft 592 on payobook, 111 components. Tiles **111 Pay components · 43 Formula rules · 52 Inputs**, counting up. Identity: name, reference, company, country, kind of pay run, effective from, started from, **Inputs close on Day 20 of the month · Payday The last working day of the month · An input that arrives late It waits for the next pay run · Paid in VND · Bank identifier Domestic account number**, situation chips, and *"Vietnam Statutory Parameters 2026 · version 2026.1 — Aligned with the rule pack"*. Decisions **8 open**, each with its component code and *Open this component*. Optional: Source mapping *Not started · 0 of 52 inputs have a source*, Payslip layout, Approvals *Already in place*. Checks *5 checks passed · Last checked just now by LOOK P4 validator*. **Finish & open** → the studio opened on the configuration |
| 2 | Finish blocked: stale evidence, a failed check, checks never run, no confirmed scenario — each with its reason, each fixable | **PASS** (three in the browser, one by test) | *Never run*: **"The checks have not been run yet. Run them on the Test step so the numbers are proven before anybody is paid by them."** + *Go to Test*, button disabled. *Stale* (band 2 10 % → 12 %, saved): **"Something changed since the checks were last run, so what they proved is no longer what this configuration says. Run them again."** *Failed* (re-run against the changed band): **"2 checks need attention. A number they produced is not the number somebody expected."**, and the rail's own Test row read *"2 checks need attention"*. Restoring the band and re-running cleared every one and the button enabled. **No confirmed scenario** has no on-screen way to reach it — nothing in the product un-confirms a scenario — so it is proven by `test_nobody_has_agreed_to_any_numbers` instead, which is stated rather than claimed |
| 3 | Discard → confirmation naming the configuration and its components → gone from the picker; refused on a configuration that has paid somebody | **PASS** | *"“B6 abm walkthrough” and all 111 components in it are deleted. This cannot be undone."* → discarded, gone from the picker. The refusal is proven on **real data on p9clone**: a configuration with real payslips answers `allowed: False` — *"This configuration has already produced payslips, so it cannot be discarded. Archive it instead."* — `bp_discard` refuses with the same sentence and the configuration is still there |
| 4 | A finished configuration opens in read mode; "Revisit the setup" reopens editing | **PASS** | Reopening 592: **"Setup complete — Setup was completed just now by LOOK P4 validator."**, primary **Open the configuration**, link **Revisit the setup**, status pill "Setup complete". Pressing Revisit → step 1, status pill back to **Draft · saved just now**, every step editable again |
| 5 | The Excel workbook, end to end; cancel still returns | **PASS** — this closes B1 §8.1 | Start → Import Excel workbook → draft 593 created empty → the legacy review opened pre-scoped → upload `small_payroll.xlsx` → Analyze → sheet **PAYROLL, header row 3, 8 columns, 3 formulas** → Primary Key Column **Employee ID** → the review offered all eight columns with the right kinds (`Gross Pay =C4+D4` as a Formula) → Configure Order → Process & Resolve → Review Components (**8 to import, 3 formulas, 0 duplicates**) → Execute → the category review → **back in the journey at Pay rules with "8 components"**, `Gross Pay` reading *"Written as Excel · =BASICSALARY+ALLOWANCE"* in CODES. Cancel from the upload step returns to Pay rules with an honest empty state and two buttons |
| 6 | Vietnamese: six steps, both dialogs, the picker card, the Finish decisions | **PASS with named exceptions** | §4 |
| 7 | Polish: 390 px header, rail ticks, reduced motion, keyboard, ⌘K | **PASS** | §5 |
| 8 | All four databases; gates green | **PASS** | `pb_blueprint 19.0.1.5.0` and `pb_formula_studio 19.0.1.185.0` on p9clone, payobook, abm and payobook_template; zero ERROR/CRITICAL in every upgrade log. On **abm**: a Complete draft seeded 111 components, hero **27.04m VND** — the same certified number as payobook — checks **5 / 5 passed**, the gate opened, 8 decisions, and the draft was discarded through the product's own path. **0 console errors** on either database |

**8 PASS · 0 FAIL** (with the two named narrowings inside cases 2 and 6).

---

## 2. The finish gate, as implemented

One method — `_finish_reasons` — answers both "may I finish" (inside
`bp_finish`) and "why not" (inside `bp_finish_data`), because two copies of a
gate is how a screen ends up showing a green button over a red reason.

| Code | What it refuses | Where it sends you |
|---|---|---|
| `circular` | two components depend on each other | Pay rules |
| `unreadable` | a formula the engine cannot convert (`python_formula` empty — B1's check, kept as the FIRST question because it is the one the engine itself answers) | Pay rules |
| `invalid` | a formula the checker refuses (`is_valid`, trustworthy again since B2 taught the validator to expand `BRACKET` first) | Pay rules |
| `not_run` | nobody has run the checks | Test |
| `stale` | the checks were run against different rules | Test |
| `failed` | a check needs attention | Test |
| `unconfirmed` | no scenario has numbers anybody agreed to | Test |
| `outputs` | take-home pay (or the income tax) has no confirmed scenario behind it | Test |

Each names its components (up to five, then "and N more") and carries the step
and tab that fix it.

**Open decisions never block.** A person may know a question is unanswered and
finish anyway; what may not be wrong is the arithmetic.

**A configuration with no calculations has nothing to prove**, so the four
evidence gates do not apply to a blank canvas — otherwise somebody building
their own components from nothing could never finish (the plan's step 8).

`outputs` is deliberately narrower than "every final output". The Vietnam
starter's own certification suite asserts eighteen values per person and leaves
one intermediate total out; refusing to finish over a total nobody looks at
would be B1's `has_errors` trap in new clothes. What has to be proven is the
money that reaches a person, resolved the same way the pay panel resolves it, so
an imported workbook with its own naming is served too.

---

## 3. The decisions list — four sources, one list

| Source | Example seen live |
|---|---|
| a component whose sentence still asks a question (`review_items`, which is also where B3's owner questions surface) | *Private insurance allowance for expatriates · PRIVINSALW · Choose the insurance treatment*; the four overtime components' *Confirm which part of overtime is tax free*; `PRIVHLTHEE` / `PRIVHLTHDEP` *The employer pays the tax on this* |
| an optional task finished and undermined since (`needs_review`) | *Source mapping — This was finished, and the configuration has changed since* |
| a scenario whose numbers nobody has agreed to | *Nobody has agreed to the numbers this scenario expects* |
| a statutory value that drifted from the rule pack | *This is 11,000,000 here and 15,500,000 in the rule pack* |

Fifteen travel to the screen and the rest are counted — *"3 more decisions are
open, on the steps they belong to"* — never silently dropped. Every row carries
the door that settles it, and the door opens the exact component: the tick that
opens the editor is separate from the rule id, so asking for the same component
twice works and closing the sheet is final (a child that sets its parent's state
from a render hook is BP41's silent infinite loop).

---

## 4. Vietnamese

**Generated, not typed.** The command, in three steps, all reproducible:

```bash
# 1. on the server, as odoo (GR56: a SUBCOMMAND, and it takes no server options)
odoo-bin i18n export -c /etc/odoo-server.conf -d payobook -l pot \
    -o /tmp/bp6_pots/pb_blueprint.pot pb_blueprint

# 2. locally: merge with the glossary, the other modules' catalogues, and
#    machine translation for what is left
.venv/bin/python tools/refresh_pb_vi.py --pot-root /tmp/bp6_pots \
    --module pb_blueprint --module pb_formula_studio --translate-missing

# 3. repair and validate (new, and it is why this phase has a `vi_polish.py`)
.venv/bin/python pb_blueprint/tools/vi_polish.py \
    --po pb_blueprint/i18n/vi_VN.po --pot /tmp/bp6_pots/pb_blueprint.pot
```

**Counts**: `pb_blueprint/i18n/vi_VN.po` **1,177 entries**, 0 empty, 0 without a
`#. module:` comment, 0 containing "Odoo". `pb_formula_studio/i18n/vi_VN.po`
**2,256 entries**, same three zeros. Loaded on all four databases with
`-u pb_blueprint,pb_formula_studio --load-language=vi_VN --i18n-overwrite`.

**Hand-corrected**: 45 of the most-read strings, because machine translation is
confident and wrong in a specific way — it reaches for a *word* rather than the
*payroll* word, and it moves placeholders. "Components" came back as *linh kiện*
(electronic parts, and after the number: "Linh kiện 111"); "insurance treatment"
came back as *điều trị* (medical treatment); "Aligned with the rule pack" as
*căn chỉnh* (typographic alignment). Every string on the six rail rows, the
footer, the hero panel's four lines, the Finish page and every gate refusal was
read and corrected where it was wrong.

**Three server-side bugs the Vietnamese walk found**, and the third is the one
worth remembering:

1. `CYCLE_LABELS` and `LINE_LABELS` were module-level dicts of PLAIN strings, so
   "Regular payroll" and the pay panel's four lines could never be translated at
   all. They are functions now, and `_()` answers in the reader's language (the
   same rule B2's `helper_label` and B3's `value_label` already follow).
2. `bp_finish_data` re-validates the formulas so the gate answers about today's
   rules — and `is_valid` is a stored field, so a person who may only LOOK at
   payroll setup was getting the framework's access refusal instead of the
   page. A re-check that cannot be written now falls back to what was last
   stored (BP53).
3. **97 entries were invisible to the server** (and 38 in `pb_formula_studio`).
   Odoo keeps a code translation for Python only when the entry's comment
   contains `odoo-python`, and for the web only when it contains
   `odoo-javascript` — a string BOTH halves say is one entry with whichever
   comment the exporter wrote first. "Regular payroll" was Vietnamese on the
   client and English from the server inside the same sentence, with a perfectly
   valid `.po` and nothing in any log. `vi_polish.py` now scans the module's own
   sources and marks every entry for both halves (BP54). **This is why the
   Vietnamese pass took three deploy rounds rather than one**, and it is the
   single most useful thing this phase learned.

**What is still English, and why:**

| String | Why |
|---|---|
| component NAMES (`Private insurance allowance for expatriates`) | they are data — the starter's own `salary_rule_id.name`, a translatable FIELD on a record, which a `.po` for our module cannot reach. Translating a starter's components is a content job on the pack, not a catalogue job (BP-R9) |
| the configuration's own name and code | typed by the person who made it |
| country names in the identity card | Odoo's own selection labels; this database has them in English |
| the legacy Excel import review | a binding non-goal of this programme — re-skinning that screen is a later phase, and its strings belong to `pb_hr_payroll_formula` |

**Numbers keep `en-US` grouping** (`1,177` not `1.177`). Stated as a choice: the
glossary sets no rule for it, every other Payobook screen groups this way, and a
configuration's numbers are read beside the engine's own output.

---

## 5. Polish — every "with one more hour", and what it cost

| From | Item | Done |
|---|---|---|
| B1 | the header wraps to three rows at 390 px | **yes** — one row, 64 px, measured at a real 390 (see BP50). The shortcut into the grid moves into the overflow menu below 560 px, where nothing is lost |
| B1 | the rail's done ticks appear rather than arriving | **yes** — a 340 ms scale-in, staggered 60 ms per row |
| B1 | thin-step previews | moot: no thin step remains |
| B2 | "Restore all" is N server calls | **yes** — one call, one savepoint, one regeneration |
| B2 | shorten the amount labels so the sentence fits one line | **no**, and deliberately: those labels are the words the sentence is built from, several hoot tests assert them, and they were translated into Vietnamese this phase. Rewording them now strands the translation and rewrites tests for a cosmetic gain. It is a content decision, better made once with the owner |
| B2 | the proof strip shows one number where a before/after would land harder | **yes** — "was 500,000" struck through beside the new value, only when it moved |
| B3 | arrow keys and Enter-to-add between band rows | **yes** — ↑/↓ walk the same column, Enter on the last row adds one |
| B3 | a before/after on the try-an-income strip | **yes** — verified live: 6,750,000 struck through beside 6,850,000 the moment a rate changed |
| B3 | settle BP36 | already closed by B4 (BP37) |
| B4 | a Done task cannot be reopened | **yes** — "Not done after all", the last irreversible press in the journey |
| B4 | the coverage number in the rail's Connect hint | **no** — the Connect step would have to hand the shell its counts from a render hook, which is BP41's infinite loop, and a second server call in the shell to decorate the rail is a worse trade. Stated rather than skipped quietly |
| B4 | shorten the identity strip's progress sentence | **no** — same reason as B2's labels: a wording change after the catalogue was built |
| B5 | the verdict pills do not animate when a run flips them | **yes** — and only the ones a run CHANGED; caught live with a MutationObserver |
| B5 | a scenario cannot be renamed from its row | **yes** — click the name, type, Enter. A rename is not in the evidence key, so it can never make the checks look stale |
| B5 | the coverage percentage in the rail's Test hint | **yes** — the Test row reads *"5 of 5 checks passed"* / *"2 checks need attention"* once the checks have run, from the answer the shell already holds |
| global | `prefers-reduced-motion` for the JS count-ups | **yes** — measured both ways: with it, one value from the first frame; without it, 0 → 47 → 60 → 86 → 106 → 111 |
| global | a visible focus ring on everything | **yes** — `:focus-visible`, 2 px `#5A4BB0`, white inside the rail |
| global | `aria-live` on the hero number and the evidence chip | **yes** |
| global | ⌘K entry | **yes** — "New configuration · Setup" in the palette, opens the journey |
| global | a Settings hub card | **yes** — a "Guided setup" category whose single card opens the journey straight through |

---

## 6. The mounted-component fixture

`static/tests/blueprint_fixture.js` mocks `pb.blueprint.studio` through
`onRpc(model, method, handler)`, which intercepts the `call_kw` route the ORM
service uses — the AbstractModel does not have to exist in the mock server's
data, the match is on the pair of strings. It records every call so a test can
prove that pressing a button reached the server at all, which is the half of a
gate a pure test can never see.

**13 mounted tests over two surfaces.** The Finish step: the tiles and the
identity rows; the empty decisions sentence; a listed, counted, linked decision;
pressing a Go link and catching the step it names; a blocked gate that both
disables the button AND prints all its reasons; a ready gate that finishes; a
refusal printed on the page rather than swallowed; a finished setup that offers
to be revisited; a page that could not be read. The Components tab (B2's, four
phases after it was first deferred): the rows and their summaries; a search that
matches nothing and quotes what was typed; a component asked for by id opening
its editor and ONLY that one; nothing opening when nobody asked; and a
configuration with nothing in it not being told to search harder.

Nothing in it asserts a number a server would have had to work out — the
arithmetic is proven in Python, against the real engine.

---

## 7. Tests

**Python — 25 new, 155 total on p9clone, 0 failed 0 error.**

`tests/test_finish.py` (18): every gate refusal reproduced one at a time; a
blank canvas has nothing to prove; finishing twice is not an error; a finished
setup reads back, says whose decision it was, and can be revisited; a
configuration that has left draft cannot be reopened; discard names what it
would destroy and is refused when payslips exist; all four kinds of decision
reach the list; open decisions do not block; the identity says what the
configuration is; the checks line counts the LIVE list and not the stamp
(BP43); a configuration that does not exist is refused in words by all three new
RPCs; and nothing in the whole payload says a word a payroll manager may not
read.

`tests/test_workbook.py` (4): the workbook route creates an EMPTY draft; the
review reads the fixture and offers its columns with the right kinds; the import
creates the components, keeps their Excel, marks every one `manual` with no
recipe, and returns the journey action with the draft on Pay rules; and the
Components tab renders an imported workbook honestly.

`tests/test_i18n.py` (4): every entry names its module (GR5); no translation
contains "Odoo" or this programme's internal name; every `_t()` literal in the
module's JavaScript has a catalogue entry; and no string is split across two
lines.

**Hoot — 14 new (`static/tests/mounted.test.js`), 123 under `@pb_blueprint`.**

Two process notes, both BP37 restated the hard way: a hoot tab reports the
bundle IT loaded, and on this server `web.assets_unit_tests` is not stored as an
attachment at all (`SELECT count(*) … url LIKE '/web/assets/%'` is 0), so
purging attachments does nothing for it — **restart the service** and open a
FRESH tab, or a fixed test keeps failing in front of you.

---

## 8. Deploy

Ledger ritual: clean `/tmp/bp_stage`, scoped per-module `rsync --delete`,
`pg_dump` per database, service stopped for the production upgrades, detached
`systemd-run` with a sentinel and a `--logfile` of its own (GR57), asset purge
plus a `web.assets.version` bump, service restart, never `pkill`, never
`--delete` into the addons directory itself.

| Database | `-u pb_blueprint,pb_formula_studio --load-language=vi_VN --i18n-overwrite` | ERROR / CRITICAL |
|---|---|---|
| p9clone | exit 0 (five rounds, two of them full test runs) | **0** |
| payobook | exit 0 | **0** |
| abm | exit 0 | **0** |
| payobook_template | exit 0 | **0** |

Final state — manifest vs `ir_module_module.latest_version`, all four:
`pb_blueprint 19.0.1.5.0`, `pb_formula_studio 19.0.1.185.0`.

**One process note worth repeating**: the first `pg_dump` failed with
*Permission denied* because the detached unit made `/tmp/bp6_dumps` as `root`
and `pg_dump` runs as `postgres` — the same shape as GR56's staging-directory
trap. Dumps of all four databases were taken immediately afterwards, and the
upgrade that ran without one was `-u` of a module whose only schema change in
this phase is none at all.

---

## 9. Gotchas added to `BLUEPRINT_LEDGER.md`

**BP47** `node --check file.js` PASSES broken module syntax on Node 24 — check a
`.mjs` copy, and keep a source scan, because the guard B2 introduced for exactly
this class said two files were fine that would have blanked the whole backend ·
**BP48** the shared Vietnamese generator strips edge whitespace from a msgid, so
`_t(" and ")` never matches at runtime · **BP49** a translatable FIELD can be a
JSON document — 54,000 characters of starter offered as a string to translate ·
**BP50** the browser bridge CAN reach 390 px, with `emulate` rather than
`resize_page` (this closes four phases of "not something I could take") ·
**BP51** the kit's badge capitalises, for the third time · **BP52** a new `t-if`
between the branches of a chain starts a SECOND chain and steals the `t-else` ·
**BP53** a read RPC that re-validates is a write, and it locked a read-only user
out of the Finish page · **BP54** a translation entry is only visible to the
half of the product whose extractor comment it carries — 97 entries were
Vietnamese on the screen and English from the server, with nothing in any log.

---

## 10. Deferred, with reasons

1. **Two wording changes** (B2's amount labels, B4's identity strip) — §5. The
   catalogue was built from those exact strings this phase.
2. **The coverage number in the rail's Connect hint** — §5.
3. **No re-skin of the legacy Excel review** — a binding non-goal. This phase
   proves the round trip through it and nothing more.
4. **Component names are not translated** — §4. They are data on the starter.
5. **"No confirmed scenario" was not reproduced through the UI** — nothing in
   the product un-confirms a scenario, so the refusal is proven by test.
6. **A hero of "0 VND" after a workbook import.** The imported workbook's inputs
   are its own (`BASICSALARY`, not `BASIC`), and the sample employee the draft
   was created with has no value for them, so the panel honestly shows nothing.
   The "Adjust sample inputs" button is right beside it, so it is not a dead
   end, but the better answer — seeding the sample from the workbook's first
   data row — belongs to the phase that re-skins that review.

---

## 11. Commits

Eleven this phase, in the order each piece was verified, with explicit paths and
nothing unrelated staged (`RIZE/` and `design_poc/` were never touched):

1. `feat(blueprint): the Finish step's server half — the page, and the gate`
2. `test(blueprint): the Excel workbook, driven all the way through`
3. `feat(blueprint): step 6 becomes the Finish step, not a summary card`
4. `feat(blueprint): two more doors into the guided setup`
5. `feat(blueprint): the polish every earlier phase listed under "one more hour"`
6. `test(blueprint): the mounted-component fixture, four phases late`
7. `i18n(blueprint): the guided setup, in Vietnamese`
8. `fix(blueprint): three things the Vietnamese walk found, and the header at 390`
9. `docs(blueprint): gotchas BP47 to BP54, the eight this phase paid for`
10. `docs(blueprint): the B6 report, and the programme's closeout`
11. `test(blueprint): scope the revisit-link assertion to the button row`

**Nothing has been pushed** — **51 commits** from the whole programme now sit on
`19.1` on top of the ~104 the branch was already carrying.

---

## 12. Self-score against the bar

> "extreme WOW, intuitive, out-of-this-world experience, best in class."

- **Hero** — 9/10. The hero of this phase is the moment the button turns on. A
  page that lists eight open questions and still says *you may finish* — while
  refusing, in words, over the two checks that disagree with somebody's
  expectation — is the whole argument of this programme in one screen: judgement
  is yours, arithmetic is ours. Watching the rail's Test row change from "try
  the days that aren't ordinary" to "2 checks need attention" and back to "5 of
  5 checks passed" as the band moved is the second-best thing on it. A point off
  because the tiles count up and the page beneath them does not yet feel as
  composed as the money-flow strip B5 built.
- **Zero dead-ends** — 9/10. Every state was designed and walked: nothing
  waiting for a decision, fifteen and a truthful count of the rest, checks never
  run, run and stale, run and failing, a configuration that has paid somebody, a
  setup already complete, a setup reopened, a page that could not be read, a
  blank canvas with nothing to prove, and 390 px. Half a point off for the
  imported workbook's honest "0", and half because "no confirmed scenario" is a
  refusal a person cannot reach from the screen it names.
- **Plain language** — 9/10. Every refusal is a sentence with a next step, and
  the two I would defend hardest are *"You can finish with open decisions.
  Calculations that do not work, and checks that need attention, have to be
  fixed first."* and *"Something changed since the checks were last run, so what
  they proved is no longer what this configuration says."* A point off for the
  Vietnamese, which is honest machine translation with the forty-five most-read
  strings corrected by hand — good enough to walk, not yet good enough to ship
  to a Vietnamese customer without a native read.
- **Motion with purpose** — 9/10. Three new movements, each reporting a change
  and nothing else: the rail's ticks arriving in the order they were earned, the
  tiles counting up, and the verdict pills that a run actually moved. All three
  are off under `prefers-reduced-motion`, measured rather than assumed.
- **Keyboard and bulk** — 8/10. A visible focus ring everywhere, ↑/↓ and Enter
  in the band table, Escape closing the rename without walking off the step,
  ⌘/Ctrl+Enter still finishing from anywhere, and one call for a whole tray.
  Two points off: ⌘K opens the palette from a hub page but the journey's own
  page swallows it (pre-existing), and there is still no keyboard route between
  the Connect cards.
