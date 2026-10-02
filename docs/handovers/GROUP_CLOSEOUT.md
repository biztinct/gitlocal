# GROUP — what was built, where it is, and what is still yours to decide

*One group, every payroll, one truth. Seven phases, 2026-09-07 to 2026-09-08.*

Read the first four sections in plain English; the engineering account is at the
end. The programme ledger with every ruling and every gotcha is
`docs/handovers/GROUP_LEDGER.md`; the owner-facing design it was built from is
`docs/design/group-blueprint.html`.

---

## 1. What is live, and where

Everything below is live on **payobook.com** (the master), on the **AB Mauri**
tenant, on the **golden template** every new tenant is cloned from, and on the
rehearsal clone. Nothing here changes a payslip that has already been paid.

### Your group — Settings cog › Group

Your companies drawn as one tree, with the money the board reads in, how an
exchange rate is picked for a month, and when your financial year starts.
Underneath: a twelve-month strip showing which months already have an exchange
rate and which do not — and where there is no rate, the screen says so and
leaves the amounts in the money they were paid in. **No amount is ever stored
converted.** Below that, your **divisions**: the parts of the business that do
not stop at a company border, built from your own departments in one press.

The demo group on payobook is **Payobook Group (PBG)**, in dong, "the last rate
of the month", year starting January, with Payobook Vietnam JSC and Payobook
Singapore Pte Ltd in it, and eight divisions covering 4,533 people.

### Who is paid by what — inside Mapping

A picture with your teams and divisions down the left, your payroll schemes
down the right, and a drawn line for every attachment. Press **"Draft the map
from what you paid"** and the product reads your own payroll history and
proposes the whole map; accept it and every future pay run knows who is paid by
what. Coverage rings say how many people each scheme actually covers, and an
exceptions queue names anybody nobody pays.

New in this last phase: **the lines are a gesture.** Drag a team onto a scheme
to attach it, hover a line to follow it end to end, pull a line off the board to
take it away — and every one of those has a keyboard equivalent, so nothing here
needs a mouse.

### The pay run

The run wizard now asks which scheme is running, scopes itself to one legal
entity, and stamps the scheme on the run and on every payslip — so a report can
say which scheme produced a number a year later.

### Explorer — Payroll › Analytics Explorer

Every payroll number, with a **breadcrumb that walks down**: group › country ›
company › division › department › job. It remembers the scheme that paid each
line, the version of that scheme in force at the time, the money it was paid in,
the person, the full-time equivalent, and whether the row is a mid-month
advance. You can read the whole group in one currency, and every converted
figure carries the rate and the date it came from; anything that could not be
converted is listed with the reason.

New in this last phase: a bar you can drill into now **says so before you click
it**, and the drill is an animation rather than a swap, so you can see where you
went.

### The Decision Room — People › Plan

The what-if planner, now scope-aware: plan the group, a country, a company, a
division or a single payroll scheme, with a head count on every rung. Each
company is computed in its own money under its own country's rules and converted
only for reading. Plans can be proposed, approved and sent back, with versions
that keep everything. The **exact-cost lane** runs a plan's people through their
own scheme's real formulas rather than an average.

New in this last phase: below 1200 pixels the plan dock becomes a stack of
cards, and above it the row actions are pinned so they are never scrolled out of
reach.

### Where people work — Assignments

For somebody who spends part of a month in another company in the group: the
days, the share, the full-time equivalent, and the two ways it can be paid —
each entity pays its own days, or home pays and the other entity is charged. It
ships **switched off**: until somebody writes a stretch of days, nothing
changes.

New in this last phase: a **live estimate under the month strip while you
drag** — roughly what each entity would pay, each in its own money, never added
together, with the exact two-payslip preview still behind it.

### Pay — People › Pay

* **Pay bands** — the band picture with a dot per person, five health cards each
  carrying its own definition, drag an edge and see what it costs before you
  release it, place a new hire, import and export. A company that has never
  written a band opens the screen on **its own bands, already drawn from the
  wages it already pays**; nothing is saved until you press "Use these".
* **Fairness** — the gap by gender at the same level, by level, by division, the
  spread inside one job, and who is paid least for the same work. It refuses to
  mix two currencies and says which one it kept.
* **Pay review** — a worksheet that opens FULL, with a suggested rise on every
  row, a budget meter, a live fairness line that says whether this round widens
  the gap, five kinds of self-explaining limit, calibration, a four-signature
  cascade, one preview and one write with letters, and a full undo for 24 hours.
* **Pay changes** — a promotion or a correction between reviews, through the same
  guidance and the same approvals.
* **Your pay, explained** — the employee's own page at `/my/pay`.

New in this last phase: **"Fit to this family"** rescales the band picture to one
job family (and says the widths no longer compare between families), a **dense
mode** puts twice as many bands on a screen, and the review worksheet's "what to
know" chips now sit under the person's name, so the table fits a normal laptop
with no sideways scrolling.

### Who sees what — Settings cog › Group

**The new thing in this phase.** By default nobody is limited: everybody sees
whatever their companies already allow, exactly as before. Limit somebody here —
to **everything**, **one country**, **one company** or **one division** — and
every screen above narrows for them: the group, who is paid by what, the
Explorer, the Decision Room, assignments and pay.

The card's own answer to "am I sure?" is the hero: pick a person and the right
half of the panel shows, in one sentence, **exactly what they would see** — the
division, the companies, the head count — and lists every screen with the same
answer beside it. It is the same rule the screens themselves use, so it cannot
drift away from the thing it describes. If what somebody was limited to is later
archived, they go back to seeing what they saw before and the card warns you,
rather than locking them out in silence.

---

## 2. Ten minutes to try it

1. Open the **Settings cog › Group**. Look at the tree, then at the twelve-month
   exchange-rate strip. Click any grey month: it opens the rate list for exactly
   that month with a sentence telling you what to do.
2. Scroll to **Divisions**. Press "Attach a department", tick five or six teams,
   and press "Attach these" — the footer tells you how many people they bring
   before you press it.
3. Scroll to **Who sees what**. Press "Limit somebody", pick a person, choose
   "One division", pick a division. Read the right-hand half: that is their
   screen. Press Cancel — nothing was saved.
4. Go to **Payroll › Mapping › Who is paid by what**. Drag a team from the left
   onto a scheme on the right. Hover one of the drawn lines and watch it light up
   at both ends. Pull a line off and drop it on the bar that appears.
5. Go to **Payroll › Analytics Explorer**. Hover a bar: it offers to look inside.
   Click it and walk down to a division, then a department, then a job.
6. Go to **People › Plan**. Press the scope chip at the top and pick a division.
   Move the head-count slider and watch the profit line.
7. Go to **People › Pay › Pay bands**. Press "Use these" — no, do not: read the
   proposal, then press **Dense rows** and **Fit to this family** to see the same
   bands two other ways.
8. Go to **People › Pay › Fairness** and read the first sentence.

---

## 3. What the numbers are built from

| The number | Comes from | Is it an assumption? |
|---|---|---|
| Who is paid by what | The scheme map, and failing that the company's only active scheme | No — it is configuration you accepted |
| Every figure in the Explorer | Payslips that were actually computed, rebuilt into fact tables every 30 minutes | No |
| A converted figure | A `res.currency.rate` row under the policy the group chose | No — and where there is no rate, nothing is invented |
| A division's people | Departments attached to that division on the date being read | No |
| A plan's cost | Your roster and your pay, plus the levers you moved | The LEVERS are yours; the starting point is real |
| A plan's exact cost | Each person run through their own scheme's real formulas | No |
| A split month | The days you drew, the home calendar's working days | The DAYS are yours |
| A pay band | What you entered, or the proposal drawn from wages you already pay | The proposal is a suggestion until you accept it |
| A fairness gap | Facts from the last full payroll plus open contracts | No |
| A suggested rise | The guidance grid × how well somebody did × where their pay sits | The GRID is yours |

---

## 4. Decisions still yours

1. **Reset the administrator password.** The login recorded for `payobook` in the
   ledger no longer works, and the same is true of the AB Mauri tenant. Every
   phase validated with a temporary account which was archived afterwards
   (section 5). Resetting your own password is not something to do for you.
2. **Enter exchange rates.** There is genuinely no Singapore-dollar-to-dong rate
   on the master database, so every group figure that needs one honestly says so.
   One rate row per month per pair is all it takes.
3. **Confirm the seven non-Vietnamese rule sets with an adviser.** Eight
   countries ship with contribution rules; Vietnam's are the ones this product
   has always used and are known good. The other seven were written from public
   rates and have not been checked by a local adviser.
4. **Turn on day-based pay for joiners and leavers,** per company, if you want
   somebody who starts mid-month to be paid for the days they worked. It is off.
5. **Choose the split-month pattern** if anybody in your group works across two
   entities. The default is "each entity pays its own days".
6. **Enter your pay bands, or accept the proposal.** Every database currently
   carries zero bands, and the screens open on a proposal drawn from your own
   wages.
7. **Assign visibility.** Nobody is limited today. Deciding who should be is a
   business decision, not a technical one.
8. **Push the commits.** The whole programme is committed and NOT pushed.
9. **One board narrows by company only.** Insights (Payroll › Insights) is
   held to the companies a limited person may see, and its department
   leaderboard to their teams, but it has no division of its own — so somebody
   limited to a division inside a single company reads that one board at
   company level. Every other screen in the product narrows properly. It is
   listed as a Phase 8 candidate.
10. **The dark palette is a platform job, not this programme's.** The `pbim`
   design kit has one set of colours and no dark variant, so "dark mode" today
   re-tints the platform's chrome around a cockpit whose own surface stays light.
   Giving the kit a dark palette would change every Payobook cockpit at once and
   belongs to a platform release of its own.

---

## 5. Temporary logins created across P1–P7

Every one of these was created because the recorded administrator password no
longer works, and every one is **archived**. Reactivating any of them is a single
write; none of them is a way in while archived.

| Database | Login | Why |
|---|---|---|
| payobook | `group.p3@payobook.com` | P3 browser walk |
| payobook | `group.p6a@…`, `group.p6a.reader@…`, `group.p6a.vi@…` | P6a walk |
| payobook | `p6b.hr@…`, `p6b.finance@…`, `p6b.ceo@…`, `p6b.vi@…`, `p6b.me@…` | P6b approval cascade |
| payobook | `p7.ceo@…`, `p7.country@…`, `p7.head@…`, `p7.vi@…` | P7 visibility walk |
| abm | `wfplan.validator@payobook.com` (id 246) and later siblings | every phase |
| p9clone | the same five P7 names, plus each phase's own | rehearsal |

---

## 5b. What was tidied away, and what deliberately was not

**Tidied (nothing destructive, nothing that was real configuration):**

* Every temporary login created for this phase is archived on payobook, on AB
  Mauri and on the rehearsal clone.
* Every visibility row created for this phase is **deleted** — payobook, AB
  Mauri and the golden template carry **zero**. Nobody is limited; the feature
  is there and switched off, which is the only honest state to hand over in.
* The whole rehearsal on the clone — a group, eleven divisions and their
  attachments, twelve accepted scheme lines, one attachment made by dragging,
  one 902-person review and five accounts — was removed and verified gone.

**Left alone on purpose, because it is yours and not litter:**

| What | Where | Why it stays |
|---|---|---|
| The accepted scheme map, 12 lines | payobook, Payobook Vietnam JSC | real configuration you accepted in P2 |
| Company 6 switched back on | payobook | it joined the group in P1 |
| The "Board draft" plan and the ₫2,200B revenue target | payobook, company 5 | your demo plan from the Decision Room programme |
| Four sets of planning assumptions | payobook, company 5 | one per scope you opened; the model working, not litter |
| Two "RIZE … (test)" departments outside every division | payobook | left out on purpose in P1 |
| The Settings hub's own breadcrumb reading "Unnamed" | everywhere | platform-wide and older than this programme |
| Five failing tests on the rehearsal clone | p9clone | that clone's own data drift; a clean database has none |

---

## 6. Engineering summary

The authoritative account of every phase — versions, test counts, timings,
rulings and the gotcha ledger GR1–GR60 — is `docs/handovers/GROUP_LEDGER.md`,
and each phase has its own handover beside it (`GROUP_P1_…` to
`GROUP_P7_…`). What follows is the shape of it.

### The modules this programme built or changed

| Module | Version at the end of P7 | What it is |
|---|---|---|
| `pb_group` | 19.0.2.0.0 | the group, `pb.fx`, divisions, the Group screen, **who sees what** |
| `pb_scheme_map` | 19.0.2.0.0 | who is paid by what: the resolver, the board, the wires |
| `pb_explorer` | 19.0.2.2.0 | the fact tables and the Explorer |
| `pb_insights` | 19.0.5.1.0 | the payroll board, company-scoped |
| `pb_decision_room` | 19.0.4.4.0 | the scope-aware planner |
| `pb_workseg` | 19.0.1.1.0 | one person, two entities |
| `pb_pay` | 19.0.3.0.0 | bands, fairness, review, changes, the portal page |
| `pb_import_kit` | 19.0.1.17.0 | the shared design kit and the one icon set |
| `pb_formula_studio` | 19.0.1.180.0 | the Mapping screen the scheme board lives in |

Also touched across the programme: `pb_budget`, `pb_people_hub`,
`pb_hr_payroll_formula`, `pb_payrun_wizard`, `pb_employee_vault`,
`pb_contracts`, `pb_lifecycle`, `pb_hr_flow`, `pb_pip`, `pb_probation`,
`pb_payruns`, `pb_hr_payroll_analytics`, `payroll_analytics_approval`,
`pb_demo`.

### The invariants the tests enforce

1. **Nothing changes for a person with no visibility row** — asserted on the
   helper, on the record rules and on every facade.
2. **No amount is ever stored converted**, and a missing rate is shown rather
   than guessed.
3. **A company with one active scheme and no map entries produces the identical
   pay-run population** before and after the scheme map.
4. **A payslip computed with the split-month hook live and with it neutered is
   the same figure to the digit** (902 payslips, one savepoint, both passes).
5. **A budget row moved from the retired module matches row by row**, not just
   in total.
6. **Every word of every GROUP screen exists in Vietnamese**, with no
   placeholder lost and the word "Odoo" nowhere in any translation.

### What was removed

`pb_hr_workforce_planning` is **uninstalled** on every database and no table of
it remains. Its merit matrices, compensation cycles, performance scores,
guardrails, budget actuals and pay grades were carried across first and the
move was proved row by row.

### Phase 8 candidates

1. **A rate source connector** — pull `res.currency.rate` rows from a bank or a
   published feed on a schedule, so the coverage strip fills itself.
2. **Segment-aware statutory reporting** — a split month is understood by payroll
   and by the Explorer, but a government report still reads one entity at a time.
3. **Review → pay-file automation** — an applied pay review writes contracts;
   the next run still has to be started by hand.
4. **A dark palette for the design kit** (see decision 9).
5. **A full-bleed phone frame** for the cockpits — they work at 390 px, but they
   are laid out as a narrow desktop rather than designed for a phone.
