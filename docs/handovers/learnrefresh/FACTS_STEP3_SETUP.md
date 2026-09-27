# Verified facts for Step 3 (read from code 2026-09-27; code wins if it moved)

NO `data-coach` anchors on: pb_blueprint, Mapping screen, pb_scheme_map, Component
treatment, pb_approval_config (matrix + inbox), pb_records, pb_group. Existing nearby:
Explorer ex-head, ex-trail, ex-rail, ex-when, ex-filters, ex-headline, ex-table
(pb_explorer/static/src/xml/explorer.xml); Formula Studio fs-mapping (studio.xml:140);
pw-scheme (payrun_wizard.xml).

## Guided setup — New configuration (pb_blueprint)
Reach: Settings › Guided setup › New configuration; ⌘K "New configuration"; Formula
Studio Settings tab opens it in edit mode (old panel says "Settings have moved" / Open
the guided setup). Shell: crumb name+code, Editing chip; status pill Not saved yet /
Saving… / Draft · saved 2 min ago / Setup complete / Could not save — retry; buttons
Skip to the grid, Save & close (Close before it exists), ⋮ Discard this draft; footer
"Step N of 6 · N components", Back, Continue names its destination; Pay rules Continue
walks its tabs first; Finish in edit mode = Save changes.
Steps (blueprint_steps.js:28-71):
1 Start "Name, starter, who you pay": Identity (Company, Configuration name, Country with
  live "Pays in ₹ INR" chip, Pay cycle Regular / Mid-month advance / End-month / Full and
  final, Effective from = 1st of next month); "How would you like to start?" starters
  Vietnam · Complete, Essentials, Import Excel workbook, Blank canvas (Certified/Draft
  badges); "Who are you paying?" Local / International / Short-term / Guaranteed
  take-home; "Real life belongs in the design" Joiners & leavers ✓, Annual & event-based
  pay ✓, Salary changes within a month, Corrections & arrears. Progress lines on
  Continue. Edit mode: "Built from" card; country locked once components/payslips exist;
  Advanced card (reference code, legacy structure, workbook switches).
2 Pay rules: tabs Components · Tax & protection · Calendar & payment; each component a
  sentence + formula; "Months that are not ordinary" (Part-month pay, Back-pay).
3 Connect: Source mapping (Open source mapping), Payslip layout (Open payslip designer);
  pills Not started / In progress / Done / Skipped / Needs another look; Approvals card
  with real per-scheme choices for Pay run and Scheme change; Skip the rest & review
  outputs; "Where the numbers come from, and where they post": connected system, ranked
  lanes Connected system / Spreadsheet / Payobook records (↑/↓, on/off, "N components read
  this"), "A lower source may only fill an empty box, never overwrite one."; accounting.
4 Outputs "See what your rules create.": filters Final outputs / Inputs & fixed values /
  Earnings / Deductions / Benefits & employer costs / Behind the scenes / Edited by hand /
  Needs a decision; inspector How it is worked out / What feeds it / What it feeds / Step
  by step.
5 Test "Try the days that aren't ordinary.": Run the checks, Add boundary cases, Try with
  a real person, Confirm all waiting; Scoreboard; a check is evidence only once confirmed.
6 Finish: What you decided / Decisions still need an owner / What has been checked /
  Optional setup; "Ready when you are" / "This setup is complete"; refused when a
  calculation is broken or checks not run/stale; FINISH ≠ ACTIVATE. Edit mode: "What you
  changed" What/Was/Is now table, Save changes, Open the components grid.
Panel "See it in someone's pay": Estimated take-home pay (+/− chip), Cash earnings,
Employee deductions, Income tax, Employer cost; Try a different situation; Adjust sample
inputs; "Calculated by the real payroll engine… Sample data only."; states no sample /
error Try again; bottom bar under 1200px.
Proposals (scheme_proposal.py): Put the scheme live / Merge a branch / Seal a release /
Roll a release back / Retire; with a route → "Propose for approval"; without → happens
at once and recorded.

## Mapping (Settings › Integrations › Mapping; ⌘K; Studio "Mapping" button)
Header: FROM <source> ══ N mapped / N suggested ══▶ TO <scheme>. Tabs: System fields →
Scheme · Transformations · Spreadsheet columns → Scheme · Employee & contract ⇆ · Who is
paid by what · Mid ↔ End cycle · Component treatment · Journey (Journey = default
landing). Toolbar Accept all ≥90%, Suggest mappings, Apply template…, Save as template…,
scheme chip, "← Journey". First-run strip "1 Pick your source · 2 Pick your scheme · 3
Draw a wire, or let us suggest them".
Journey: lanes Files & systems · Feeds · Transformations · Scheme · Payobook Source;
headline "N need a source · N fed · N not fed yet · N need attention"; Filter the
journey…; card body expands fields, ↗ opens the matching tab; Payobook Source groups
Employee, Contract, Bank, Contract pay components, Pay run → Open Records Desk.
"From this pay run · <Month>" lane: Pay month, Pay year, Days in the period, Standard
working days, Day the period starts, Day the period ends.
Excel on-ramp: "Drop this period's spreadsheet here to see its columns" (headings + one
example only; imports no numbers); Download a template built from this scheme; after:
Load this file as a pay run…, Replace file…, Template, Forget.
Source chips: Spreadsheet, Connected system, Rule output, Contract component, Employee
record, Contract record, Bank account, Calculated, Fixed value, Pay period; conflict
chips Wired twice / Feed wins / Spreadsheet fallback. Conflict dialog "“X” will read more
than one source": Add source / Use the spreadsheet instead / Use the feed instead /
Cancel; feed-over-feed Keep both wires / Use <conn> instead.
Who is paid by what (pb_scheme_map): "X of Y people are covered by a scheme.", N not
covered, N to work out again, Draft the map from what you paid, Work it out again;
columns Who / Paid by; drag team onto scheme; draft panel "The map, read from what you
paid" (Accept the N everyone agreed on, Accept all N, Not now); may be "Sent for
approval."

## Component treatment (Mapping tab)
"How each component is treated"; Re-classify from the formulas (keeps rows you set);
Save N change(s); chips All / Needs your answer / Stored differently / Type says
otherwise; columns Component · Comes from · Group · Pay role · Subtotal · Tells the run ·
Value type. Pay role: Added to net pay / Taken off net pay / Net pay itself / Employer
cost / Information only / Both added and taken off. Value type: Amount (currency),
Decimal number, Whole number, Quantity (hours, days), Percentage / rate, Reference code,
Text, Date, Yes / No. Tells the run: Whether the person is still employed / Hours
actually worked. Warning → Set all of them to Information only. Review popup after an
Excel import ("Nothing here says which component is net pay." / "N components to
settle" / Apply N selected). The run's "These figures do not add up" banner is plain
text pointing here (not a link). Teach: per scheme, affects every run; pay role decides
net arithmetic; subtotal prevents double counting; non-money types can't touch net;
saving never rewrites existing payslips — recompute.

## Approval Matrix (Settings › Approvals)
"Approval Matrix — Every check, in one place…"; Bring in from a spreadsheet, Create a
workflow; tabs Matrix · People & backups · History; columns Process and the route it
follows / Applies to / Status / Version; statuses In use / Draft / Needs people / Not
connected yet / Decided with another. No approval needed bulk → Switch off approval for
N (+Undo; still recorded). Import reads sheet "Approval Matrix". Presets "Start from a
route you already know". Builder Purpose · People · Safeguards · Review · Publish; step
kinds Review, Final approval, Joint approval, Any one of a team, Only when…, Tell
somebody, No approval needed; amount bands; Safeguards Who may not decide? / What must be
attached? / When is it due? / And if it is late?; Review "Try an example"; Publish this
route ("New requests follow it from…"; affects new requests only). People & backups:
Arrange cover. History filters. Per-scheme choice: Use the company flow / Use a
different flow for this scheme / No approval required.

## Records Desk (People › Records; roster Bulk update; run wizard "Open Records Desk";
Mapping Payobook Source card)
"Records Desk"; scheme pill "N fields"; File: Export with data / Export blank template /
Import a file; History; Review N changes. Only fields the scheme maps (none → Open
Mapping). Import tabs Changes · Unmatched · Ignored columns; matched by employee code /
work email / name; Apply N · leave M. Apply → route "Records Desk bulk changes" ("Sent
for approval — <who>") or fast lane writes at once; Undo per apply, skips values changed
since; moved value → whole proposal sent back.

## Schemes, currency, Group
"Pays in ₹ INR" (+ amber warning if no rate). Scheme money read first everywhere; a pay
run is per scheme; two schemes in one month = two payrolls. Settings › Group: "Your
group", Edit the group, History; company tree (currency, rate policy, "N pay schemes");
Exchange rates: The last rate of the month / The rate on the day the pay run ends / The
average rate for the month; 12-month strip; rate changes need approval; Divisions
(Suggest divisions, Add a division); How split months are paid; Who sees what (Limit
somebody). "Nothing is stored in the group currency." Explorer › Compare schemes: Group
currency / Each in its own money; "Two currencies, kept apart…"; Not converted reason;
Per person.
