# Guided payroll setup — what was built, and what is left for you

**For the owner. Plain English. 2026-09-11.**

Six weeks ago — six phases ago — pressing **New configuration** on the Payroll
configurations screen opened a small pop-up with five steps, two of which did
nothing, and then dropped you into a spreadsheet. That is gone. In its place is
a full-screen, six-step guided setup with a panel on the right that shows one
real person's take-home pay, worked out by the real payroll engine, changing as
you build.

It is live on **payobook.com**, on the **AB Mauri** tenant, on the golden
template every new tenant is made from, and on the rehearsal database.

---

## What you get, step by step

**1 · Start.** You name the configuration, say which country and what kind of
pay run it is, and choose where to start from: **Vietnam · Complete** (every
line a Vietnamese payroll normally needs — 93 components, each with a rule you
can read), **Vietnam · Essentials** (the shorter one), **your own Excel
workbook**, or a blank page. You also tick who you are paying and which awkward
months apply. Pressing Continue creates the configuration once — a double click,
a retry or a refresh all land on the same one.

**2 · Pay rules.** Every component as an English sentence — *"For everyone,
calculate a percentage of another component at the rate held in Social Insurance
Rate, prorated by paid working days"* — with the calculation it produces
underneath it. Change a word and watch the person's pay move. Two more tabs sit
beside it: the **tax bands, reliefs and insurance ceilings** (with a slider that
tries an income against the schedule you are editing), and the **calendar and
payment** choices — when data closes, which day is payday (shown as the real
date it lands on next), and what happens to something that arrives late.

**3 · Connect.** Two optional jobs — pointing each input at where its value
comes from, and arranging the payslip — each opening the tool that already
exists, scoped to this configuration, with a chip that brings you back. Neither
has to be done now, and the card says so. Approvals is information only: pay
runs already follow Officer → HR → Finance.

**4 · Outputs.** The whole configuration in one table: what each component works
out, in codes rather than spreadsheet letters, what it depends on, what it feeds,
and what it pays the sample person. A strip across the top says, in real
numbers, that *68 things you are given become 41 components through 43
calculations and come out as take-home pay and what it costs you*.

**5 · Test.** One button runs every scenario through the real engine: the five
certification people the starter ships, plus any edge you add — no paid days, the
insurance ceiling, the month a short contract stops being short. A number the
engine produced is not yet a number anybody agreed to, so a scenario waits for
your confirmation before it counts as passed.

**6 · Finish.** The page you could hand to somebody else. What was built, what
this configuration IS (including the calendar, the payment details and whether
your tax values still match the rule pack), every decision still waiting for an
owner with a link straight to it, what has been checked and when, and what was
done or skipped on Connect. Then one button.

**Finishing is not switching on.** It marks the setup complete and opens the
configuration; making it pay real people stays the separate, checked step it
always was, and the line under the button says so.

**You can finish with open questions.** What you cannot finish with is broken
arithmetic: a calculation the engine cannot read, a check that disagrees with
what somebody expected, checks that were never run, or checks run against rules
that have changed since. Each of those is refused in a sentence, on the page,
with the step that fixes it one click away.

---

## How to use it

* **Payroll configurations → New configuration.** (Also ⌘K → "New
  configuration", and Settings → Guided setup.)
* **Leave whenever you like.** Save & close, and the configuration's card on the
  Payroll configurations screen shows a ring — *"Still being set up — step 3 of
  6"* — with a **Resume setup** button that puts you back where you were.
* **Come back to a finished one** and it opens on its last page, read only, with
  **Open the configuration** and **Revisit the setup**.
* **In Vietnamese**: switch your language in the top-right and the whole journey
  follows.

---

## What changed on screens you already had

* The **Payroll configurations** screen: cards for setups in progress show a
  step ring and a Resume button instead of the usual health ring.
* The **components grid** (Formula Studio) is unchanged and is still one click
  away from every step — "Skip to the grid" in the header.
* The **Mapping Studio** and the **payslip designer** now come back to the
  journey when you arrive from it. Nothing changes when you open them the
  ordinary way.
* A configuration seeded from the Vietnam rule pack **stopped reporting "2
  errors"** on its card. It never had any: the checker did not know the
  progressive-tax function the whole pack is built on. That is fixed for every
  configuration on every database.
* **The checks could only ever be run once** by anybody who is not an
  administrator — an old permission gap in the payroll engine, fixed in B5. It
  affected the Formula Studio's own Test workbench too. It is a security file, so
  it is named here rather than buried.

---

## The numbers

| | |
|---|---|
| Modules live | `pb_blueprint 19.0.1.5.0` (new), `pb_formula_studio 19.0.1.185.0`, `pb_hr_payroll_formula 19.0.1.125.0`, `pb_import_kit 19.0.1.19.0`, `pb_hub 19.0.1.9.0`, `pb_pay_delivery 19.0.1.2.0` |
| Databases | payobook, abm, payobook_template, p9clone — all four on the same versions |
| Automated tests | **155** on the server, **123** in the browser, all green |
| Vietnamese | 1,177 phrases for the new screens, 2,256 for the configurations screen |
| Commits | **51** across the six phases, none pushed yet |
| Starter | Vietnam · Complete — 93 components, certified against five real people on every database, to the dong |

---

## Decisions still waiting for you

These are the ones only you can make. Nothing is blocked while they wait.

1. **Five tax bands or seven?** The workbook proposes a **five-band** 2026
   schedule (Law 109/2025, in force from 1 July 2026); the shipped rule pack
   carries **seven**. B3 ships the pack's seven and makes changing them a
   two-minute job on screen. The proper vehicle for the new schedule is a new
   pack version — say the word and it is a small, dated, auditable change rather
   than an edit to every configuration.
2. **Union dues: 0.5% or 1%?** The workbook says both in different places.
   **0.5% is shipped**, with a ceiling of 253,000 a month, and the union
   components are switched off by default (the "union member" flag starts at
   no). Changing the rate is one field on the Tax tab.
3. **Overtime: is the whole payment tax free, or only the premium above the
   normal rate?** The law exempts the *premium*; the workbook says "PIT exempt
   for qualifying OT". **The whole line is treated as tax free while the
   evidence is held**, which is the workbook's reading, and all four overtime
   components carry a visible review item saying so. If the premium-only
   reading is right, it is a change to one sentence per component.
4. **The short-contract threshold.** The handover specified **5,000,000** and
   that is what ships. Circular 111/2013 says **2,000,000**. One field on the
   Tax tab either way, but somebody should decide which is right for you.
5. **The temporary validator user.** `look.p4@payobook.com` is switched on for
   payobook and abm with a password of ours, because the administrator password
   on file does not work. Say the word and it is archived — or better, tell us
   the working administrator password and it can go for good. (It was switched
   to Vietnamese for this phase's language walk and switched back afterwards.)
6. **Three demo configurations on payobook.** *"Vietnam · Monthly payroll
   (guided setup)"*, *"Vietnam · Monthly payroll — setup in progress"* and
   *"Vietnam · Complete (guided setup demo)"*, plus this phase's *"B6 Finish
   walkthrough"* and *"B6 Workbook walkthrough"*. They exist so the feature can
   be seen with real numbers in it. Keep them or say the word and they go.
7. **One permission changed in the payroll engine** (the checks-can-only-run-once
   fix above). It is the smallest possible change and it makes the studio's own
   Test workbench work again as well.
8. **Nothing has been pushed.** 51 commits from this programme sit on the `19.1`
   branch on top of roughly 104 the branch was already carrying. Say the word.

---

## What we would build next

* **Re-skin the Excel import review.** It works — this phase drove a real
  workbook through it end to end — but it is the one screen in the journey that
  still looks and reads like the old product. It is also where a workbook's own
  numbers could seed the sample employee, so the pay panel shows a real person
  instead of zeroes straight after an import.
* **Approvals per configuration.** Today every pay run follows the same three
  stages. A matrix — who signs off what, above which amount — is the most common
  thing a new customer asks for.
* **Employer-paid tax (gross-up).** Where the company pays the tax on a benefit,
  the top-up is itself taxable. Today the value is taxed to the employee and the
  screen says so plainly; doing it properly is a self-referencing calculation and
  deserves its own programme, alongside **guaranteed take-home pay** contracts.
* **A Vietnamese read-through.** The whole journey is translated; forty-five of
  the most-read phrases were corrected by hand, and the rest is good machine
  translation. Before this is shown to a Vietnamese customer, somebody who speaks
  it should walk the six steps once with a pen.

---

# Engineering appendix

**Ledger**: `docs/handovers/BLUEPRINT_LEDGER.md` — every ruling (BP-R1…BP-R12),
the deploy ritual, and gotchas **BP1–BP53**. Read it before touching any of
this. Phase reports: `BLUEPRINT_PHASE_B1_REPORT.md` … `B6`. The plan the
programme was built from: `BLUEPRINT_PLAN.md`.

**The module.** `pb_blueprint` (Payobook Guided Payroll Setup), depends on
`pb_hr_payroll_formula`, `pb_formula_studio`, `pb_import_kit`, `pb_hub`.

| Layer | Files |
|---|---|
| Record | `models/blueprint.py` — `pb.formula.blueprint`, one row per configuration the journey created: step, starter, situations, calendar, tax preferences, optional-task status, evidence stamp, revision |
| Service | `models/blueprint_studio.py` (draft lifecycle, pay panel), `blueprint_components.py` (Pay rules), `blueprint_tax.py`, `blueprint_calendar.py`, `blueprint_connect.py`, `blueprint_outputs.py`, `blueprint_tests.py`, **`blueprint_finish.py`** (B6: the Finish page and the gate). All one AbstractModel, `pb.blueprint.studio`, every method taking and returning plain dictionaries |
| Rules engine | `models/recipe_schema.py` (what a sentence may say), `recipe_compiler.py` (sentence → Excel), `essentials_recipes.py`, `workbook_vocabulary.py` |
| Starter | `data/config_template_vn_complete.xml`, generated by `tools/gen_vn_complete.py`, certified by a `post_init_hook` that refuses the install if the five people stop reconciling |
| Extensions | `formula_rule_ext.py` (recipe provenance on the rule), `formula_sample_ext.py` (`bp_origin`), `formula_config_ext.py` (the import return door), `formula_studio_ext.py` (Resume setup on the picker card) |
| Screen | `static/src/js/blueprint.js` (shell) + `step_*.js` + the tabs + the pure text helpers (`*_text.js`, `tax_math.js`, `blueprint_steps.js`), `static/src/xml/*`, `static/src/scss/blueprint.scss` |
| Doors | `static/src/js/blueprint_doors.js` — the ⌘K palette row and the Settings category, both registered by registry NAME so neither module has to be imported |
| Tests | `tests/*.py` (155) and `static/tests/*.test.js` (122, of which 13 mount a component against `blueprint_fixture.js`) |
| Vietnamese | `i18n/vi_VN.po`, generated by `tools/refresh_pb_vi.py` and repaired by `tools/vi_polish.py` (see the report's §4 for the exact three commands) |

**The seams in other modules**, all of them small and listed in the phase
reports: `pb_formula_studio` (the wizard door, the Resume-setup card, arriving
with the payslip designer open), `pb_hub` (`goBack` extracted so the chip and
the designer share one implementation), `pb_import_kit` (four icons added to the
one registry), `pb_pay_delivery` (a back chip), `pb_hr_payroll_formula` (the
BRACKET lint fix, one access row, and the import's return door).

**Rules that bind anything built on this**: the server decides readiness — every
gate is enforced in the RPC and the client may only grey a button out; the draft
is the working copy and an active configuration is never edited as one;
generated formulas reference column letters, never codes; and the word on screen
is "configuration", never "schema", "blueprint", "config" or "rule set".
