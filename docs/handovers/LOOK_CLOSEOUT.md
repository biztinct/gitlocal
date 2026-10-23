# LOOK — closeout

**The programme is finished.** Four phases, designed and built on 2026-09-08 and
2026-09-09, all four live on every database. This page is the whole of it in plain
words, and the last section is the only one that needs a decision from anybody.

You asked for four things, in your own words:

> let a band open out to its own width on hover; a quarter or "March to June" range on the
> Budget strip; the same month strip on the Pulse and Explorer screens; and the Pay Review
> calibration chart, which is now the only picture in the product that can still drop
> people from view.

All four are done, and each one turned out to be hiding something worse underneath it.

---

## 1. What the four phases delivered

### P1 — a pay band opens out to its own width

**The problem.** A pay band was drawn against the whole company's pay scale, so a band
covering 6.6M to 11M dong on a scale reaching 136M was a smear 37 pixels wide. On your own
"Construction · level 2" band that smear was 544 people drawn as nine marks.

**What it does now.** Hover a band and it unrolls in place onto its own money scale — 544
people become 67 marks over 71% of the row, with a ruler underneath in that band's own
money, a hairline above showing which slice of the company scale you are looking at, and
one sentence saying out loud that this row's width no longer compares with its neighbours.
Three ways in (hover, a button, or starting a drag), one way out (Escape), and it is never
remembered between visits, because it is a way of LOOKING and not a setting.

**The thing underneath.** A picture that stops its ruler lying has to stop its marks lying
too: zoomed in, every mark was printing "12 people · 9.0M ₫ to 9.0M ₫" for bins fifty
thousand dong wide. Both ends of any money range now take their decimals from that range's
own width.

### P2 — everybody is on the calibration picture

**The problem.** The calibration chart in a pay review drew the first 900 people and said
so, on the one screen where the people at the edges are the entire point of the meeting.

**What it does now.** It changes shape instead of dropping anybody. Four and a half
thousand people open as five honest distributions: a busy stretch of the scale becomes a
bar that says how many are standing there and opens their names; a quiet one draws each
person. **On the rehearsal review of 4,510 people the picture draws 117 bars and 102
marks, and what every drawn element accounts for adds to 4,510 exactly** — measured in the
browser against the database. Proven again at 902 people and at 12.

It also gained the three things a calibration meeting asks for and never had: the shape of
each score's spread, a tick at the middle of each score's rises, and every limit drawn
across the picture with its own sentence underneath.

And it got **five times faster**: 902 people in 20–34 milliseconds where the old 900-person
version took 162.

### P3 — a stretch of months on the Budget board

**The problem.** The Budget board could be read by the year and by a single month, and
nothing in between. "How did March to June go" had no answer.

**What it does now.** Sweep four chips and the whole board — every number, every word,
every colour, the headline sentence, the drill, the table and both exports — becomes about
those four months, with the chips under your hand fusing into one band as you go. The
sweep costs **one** read of the database, not four.

The words follow: "March to June: 5 of 7 functions went over budget; Information Technology
by the most (192.8bn VND, 122% over)". Four quarter brackets sit over the strip, and a
quarter is a quarter of YOUR financial year — on a July year-start, Q1 is July to
September and the board says so rather than leaving you to guess.

**The thing underneath.** The single month key that threaded through nine functions and
both exports became an ordered LIST of months, which for the year is all twelve. That is
why a month, a quarter, "March to June" and the year are now one piece of code with a
different list: the promise that a period is a scope became a property of the code rather
than a promise about it. It was proven by capturing **117 real board readings** before the
change and again after: **0 values changed, 0 keys missing**.

### P4 — the period on the home page and on Explorer

**The problem, and it is the worst one in the programme.** The home page — the first screen
every tenant sees — reported **₫16.8M of monthly payroll under a headcount of 4,533
people**, and never said which month the ₫16.8M was about. It was a single November test
payslip. A number with no period on it is a number nobody can check.

**What it does now.** It says "Figures for November 2026 · the latest payroll month" above
the numbers, says the month again on the money card itself, and puts a strip of every
payroll month underneath — each chip showing how many people were paid that month, so the
shape of the year is readable before you press anything. Press June 2026 and ₫16.8M becomes
**₫117.3B**.

On the Explorer, the sentence the screen reads as — *Show total cost By department Over
month Where …* — was missing its clause about time. It now has a **When**, between "Over"
and "Where", with seven starting points that each name the dates they mean and a strip of
months whose bars are the weight of the measure you are currently asking about. Change the
measure and the strip redraws. Set a period and every number, the chart, the people count,
the warnings, the drill and the spreadsheet follow it — and the link you copy carries it,
which it did not before.

**The thing underneath.** Measuring the strip found that the home page's own figures take
**twelve and a half seconds** to work out on any real payroll month. The payslip-lines
table is 1.7 GB on a machine with 1.9 GB of memory, so it can never be held in memory and
reading it always costs that. The page is quick today only because the newest month on
this data has one payslip in it; a customer whose newest month has four thousand would
wait twelve seconds for their home page, every time. It is now **2.1 seconds** for a real
month and **16 milliseconds** for the default one, with every figure identical.

---

## 2. Every module, and where it ended up

| Module | Version now | What it is |
|---|---|---|
| `pb_pay` | **19.0.3.3.0** | Pay bands, fairness and pay review — P1 and P2 |
| `pb_budget` | **19.0.2.2.1** | The Budget board — P3, and P4's one-line motion fix |
| `pb_explorer` | **19.0.2.3.0** | The Analytics Explorer — P4 |
| `pb_dashboard` | **19.0.1.2.0** | The home page's figures — P4 |
| `pb_home_hub` | **19.0.1.1.0** | The Home screen that holds them — P4, one word |

All five are live on **p9clone, payobook, abm and payobook_template**, every one verified
byte-identical between the repository and the server and every version verified against
what each database says it has installed.

## 3. The numbers that prove each phase's claim

| Phase | The claim | The proof |
|---|---|---|
| P1 | a band opens out and nobody is lost | 37 px of 1,053 (3.49%) → 746 px (70.83%); 9 marks → 67; **544 people drawn in both states**; 0 overlapping marks; a ruler of five distinct labels on a band a tenth of a per cent wide |
| P2 | nobody is dropped from the calibration picture | **4,510 = 4,510** counted in the browser against the database, over 117 bars and 102 marks; again at **902 = 902** and **12 = 12**; the words "the first N people" appear in no file |
| P3 | a stretch of months is a scope, equal to the year | **117 board readings before and after: 0 values changed, 0 keys missing**; four quarter brackets landing on the pixel; seven shapes of saved link, none landing on an empty board |
| P4 | every figure names the period it is about | ₫16.8M → **₫117.3B** on pressing June, matching the database to the digit; the home page's own figures **12.5 s → 2.1 s**; the Explorer's month strip **131 ms** |

Across the four phases: **45 numbered tests in P1–P3 and 19 in P4, all passed**; the
automated suites grew from 248 tests at P1 to 398 at P4 with **no regression at any
point** — every failure in every run reproduced by a control run with the phase's code
taken back out.

**Vietnamese is complete on every screen the programme touched**: 812 terms in `pb_pay`,
299 in `pb_budget`, 274 in `pb_explorer`, 88 in `pb_dashboard` — none untranslated, none
with a lost number placeholder, and the word "Odoo" in no translation and no file header.

**Nothing was written to your live data.** Every phase rehearsed on the clone, undid what
it created and proved it gone; the payslip, pay-run, budget and analytics row counts on all
four databases are exactly what they were before the programme started.

## 4. The full list of gotchas (the L-series)

Written for engineers, kept here so the next programme does not pay for them again.

| # | In one line |
|---|---|
| L1 | A boolean `false` ARIA attribute renders as nothing at all — write it as a word. |
| L2 | A fixed pixel height cannot hold a translated sentence; it prints over the next row on a phone. |
| L3 | Re-scaling a row when a drag starts moves the grip out from under the hand — anchor the held edge first. |
| L4 | A picture that stops its ruler lying has to stop its marks lying too. |
| L5 | A capture-phase Escape handler outranks every element's own; a gesture in flight must be its first rung. |
| L6 | Two colour names the shared kit does not define, so the radii using them silently resolve to zero. |
| L7 | The shared money scale said "1 people" (fixed in P2). |
| L8 | A refused band move still raised an undo bar saying "Band moved." (fixed in P2). |
| L9 | The browser's translator writes ONE per cent sign for a named value and TWO for a positional one. |
| L10 | Whatever is under the hand is exempt from every drawing cap, or it vanishes mid-gesture. |
| L11 | A mark drawn at the middle of its bin cannot follow a hand — draw the held one where the hand is. |
| L12 | `overflow: hidden` on a plot deletes the numbers up its own side. |
| L13 | The five words a rating is CALLED were invisible to the translator (fixed). |
| L14 | A reason written on a review row is frozen in the language it was written in. **Still open.** |
| L15 | Never edit a translation file by search and replace; rebuild it from a fresh export. |
| L16 | Prove a keyboard contract with the browser's own key press, never a scripted one. |
| L17 | A sentence written either side of a value in a printed template is TWO half-sentences to a translator. |
| L18 | One chip transition sat outside the reduced-motion guard (closed in P4). |
| L19 | A table can be too big to read even once — 1.7 GB against 1.9 GB of memory is twelve seconds, every time. |
| L20 | Scrolling a chosen chip into view needs measured rectangles, and needs doing again after the layout settles. |
| L21 | A strip inside a dropdown must not close on its first press, or its keyboard does nothing after one key. |
| L22 | The Explorer's whole vocabulary was English on a Vietnamese screen (measures fixed; **the thirteen starting-point names are still open**). |
| L23 | A test can pass alone and fail in a wide run — only a wide control run says whose fault it is. |

---

## 5. What is left for you to decide

Nothing here is broken. These are the choices and the loose ends the programme could not
make on your behalf.

### Decisions

1. **Push the work, or keep holding it.** There are now **135 commits** finished and
   waiting on the `19.1` branch, seven of them this phase's. Everything is already live on
   all four databases; pushing is about the code's own history, not about what customers
   see. Nobody has pushed since before the GROUP programme, so this is a large single
   decision and it is yours.
2. **Your own administrator password.** The password on file for **payobook** does not
   work, and neither does the one for **abm**. Every phase since GROUP has worked around
   it by making a temporary user, using it, and switching it off again — this phase used
   `look.p4@payobook.com`, now archived on all four databases. Resetting your own password
   is not something a phase should do without being asked.

### Loose ends, cheapest first

3. **The Insights screen prints "0 employee(s)".** The bracketed plural that was thought
   to be on the home page is actually on the Insights screen. One line.
4. **"Division" is translated as the arithmetic word.** Six modules translate it "Phép
   chia" (division as in ÷) where the rest of the product correctly says "Khối". The
   Explorer's copy is fixed; the other six are not.
5. **Thirteen Explorer starting points print in English** to a Vietnamese reader — "Cost
   Explorer", "Statutory Ledger" and so on. Twenty-six short phrases (L22).
6. **A reason written on a pay-review row is frozen in the language it was written in**
   (L14). A review last recalculated by an English reader shows an English explanation to
   a Vietnamese one. The fix is to store the ingredients and build the sentence when it is
   read, which touches every such note and is a piece of work of its own.
7. **The design kit has no dark palette** (GR38 in the GROUP ledger). Turning on dark mode
   re-tints the platform's own frame and leaves every one of our screens exactly as
   designed. It has been reported as "walked in dark mode" by several phases and that
   claim was never true; it is a release of the shared kit, not of any one screen.
8. **Three tests in the sidebar module have been failing since the old planning module
   was retired** (T19 in the TIDY ledger). They point at screens that no longer exist. It
   belongs to whoever finishes that retirement.
9. **Four tests fail in a wide multi-module run** on the rehearsal database and pass when
   each module is run on its own. All four are older than this programme and reproduce
   with its code taken out (L23). They are rehearsal-data drift, not customer-facing, but
   they make every future "did anything break" answer harder to read.

### Inherited from GROUP and TIDY, still open

10. **A future month that has already been spent on is judged like a finished one** on the
    Budget board. That is the rule TIDY shipped deliberately; if it should read
    differently for a stretch of months, that is a one-line ruling from you.
11. **Nobody has recorded a performance score on AB Mauri**, so a pay review there draws
    all 152 people in the middle column and says so. Correct, and also a company that
    cannot calibrate anything until somebody scores.
12. **The six per-country payroll modules cannot be installed** on this platform version.
    They are heritage; nothing points at them.

---

*Phase reports: `LOOK_P1_REPORT.md`, `LOOK_P2_REPORT.md`, `LOOK_P3_REPORT.md`,
`LOOK_P4_REPORT.md`. Everything an engineer needs is in `LOOK_LEDGER.md` and the parent
ledgers it names.*
