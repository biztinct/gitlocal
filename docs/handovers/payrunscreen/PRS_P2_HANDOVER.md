# PRS P2 — the new pay run screen (client) + go-live

Read first: `PRS_LEDGER.md` (C1–C12, R1–R3, gotchas) and `PRS_P1_REPORT.md`
(the payload as actually built — it wins over the P1 handover where they
differ). Visual + behavioural spec: `docs/design/payrun-screen-prototype.html`
(open it, click through all six moments; copy its CSS tokens and spacing).

## Design (binding, owner's words)

"extreme WOW, intuitive, out-of-this-world experience, best in class." A hero
moment; zero dead-ends (every state — empty, loading, error, partial, huge —
designed; every failure names its reason and its next step); plain language
over code vocabulary; motion with purpose; keyboard + bulk ergonomics where
rows are involved; measured against the best SaaS tool in the category, not
stock Odoo. Score the result against this bar in the report.

Hero moment = the money card ("63 people take home ₫1.62 billion …" + the
three-part bar growing in) beside the checks card whose ticks land one by one
and settle on "Everything checks out".

## Goal

The native pay run form (`hr.payslip.run`) shows the screen in the mock-up,
fed by `pb.payruns.get_run_screen`. Same URL, same record, same breadcrumbs —
nobody has to learn a new place.

## Scope

1. **OWL view widget** `pb_payrun_screen` (`registry.category("view_widgets")`,
   clone the shape of `biz_theme/static/src/js/vu_progress_rail.js:127`) in
   `pb_payruns/static/src/js/payrun_screen.js` + `xml/payrun_screen.xml` +
   `scss/payrun_screen.scss`. Loads `get_run_screen(resId)` on mount and after
   every action. Renders, in this order: header (back link, title once, chips,
   status pill, Downloads menu, More menu, ONE primary button) · date-mismatch
   banner (amber, R2) · sent-back / rejected banner · 5-step journey · money
   card + checks card · who-signs-it-off (draft/pending) OR pay-and-deliver
   (done) · people (team column + search + three tabs + sortable table) ·
   what happened (history).
2. **Form arch** (`pb_payruns/views/hr_payslip_run_form_enhance.xml`): add
   `vu-no-hero` to the `<form>` class (suppresses the auto "R2 / DRAFT" card —
   `biz_theme/static/src/js/vu_form_compiler.js:30,148-154`); put the widget
   first in `<sheet>`; make the old pieces `invisible="1"` — vu_progress_rail,
   the five alerts, the KPI band, `slip_ids`, the name label + h1 — **hide,
   never delete** (C7: other layers xpath onto them). Hide the native
   `<header>` with CSS scoped to `.pb-payrun-form` (keep the nodes).
3. **Run settings card** = the native `//sheet/group` restyled (class
   `pb-prs-settings`), moved after the widget, with plain labels
   (`string=` overrides on the fields in this view): Run name, Work dates,
   Full month in working days (+ its note), Books it is posted to
   (journal_id), Reverses an earlier run (credit_note). Editable only in draft
   (existing readonly rules); saving uses the form's own save. After a save the
   widget reloads its payload (dates may have changed the checks). The
   optional "Application data review" and "Finance pack" groups stay, styled as
   cards below it, shown only when they have content (their existing rules).
4. **Buttons** go through the form so save-before / reload-after behave like a
   native header button: use `env.onClickViewButton` (FormController's
   `useViewButtons`; confirm the Odoo 19 signature in the server's
   `web/static/src/views/view_button/view_button_hook.js`), falling back to
   `action.doActionButton`. Confirmations with the dialog service's
   `ConfirmationDialog`, always with an explicit title (C1). Texts = payload
   `confirm`.
5. **Quick look** side panel on row click (portal to body, PRS-G1): name, job,
   team, flag, take-home box, Pay / Deductions / Company pays on top, read from
   `hr.payslip.pb_statement_json` when `statement_available`, else the row's
   four figures; footer "Trace" (atlas, if offered) + "Open full payslip"
   (act_window `hr.payslip` form, that id). ↑/↓ moves, Esc closes.
6. **Bulk bar** when rows are ticked (shift-click selects a range): only the
   verbs P1's `bulk` flags allow. Delete = delete those draft payslips (PRS-G9),
   with a confirm naming the count.
7. **Keyboard:** `/` focuses search (not while typing in an input), Esc closes
   the top layer, Ctrl/⌘+Enter presses the primary (its confirm first). Show the
   hints as small key caps, like the mock-up.
8. **States:** loading = skeleton of the same layout (no spinner-only page);
   RPC error = a card that says what failed in plain words + "Try again" + "Show
   the classic layout"; empty run (no payslips) = the mock-up's empty card;
   >100 people = first 100 rows + "Show 100 more" (counts and team totals stay
   whole-run); a person search with no match = "Nobody matches …" + Show
   everyone; rejected run = rose banner with the reason, everything read-only.
9. **Escape hatch:** More › "Show the classic layout" toggles a class that
   unhides the native header, alerts, KPI band and slip list for this browser
   tab only — so no existing tool is ever unreachable.
10. **Header-button guard (new convention C13 — add it to the ledger):** a
    test that reads the composed form arch
    (`env['hr.payslip.run'].get_views([(False, 'form')])`) and asserts every
    `<header><button name=…>` is either offered in `get_run_screen.actions`/
    `primary` or listed in an explicit RETIRED set with a one-line reason
    (e.g. Generate Payslips → primary "Make payslips" + More "Add or remake
    payslips"). A future module adding a header button then fails a test
    instead of silently vanishing.
11. **Stray "New" in the breadcrumb** (seen on rize 1591 above "Back to Pay
    runs"): find the cause and fix it if it is ours; if it is core behaviour,
    say so in the report and leave it.
12. **vi_VN** for every new string (JS `_t` → `#. odoo-javascript`), C9.
13. **Learn** (C8): search anchors/lessons/replicas that point at the pay run
    FORM (not the board) and update them EN+VI; bump `pb_learn` if touched.
14. **Version bump** `pb_payruns` manifest (minor) and a manifest comment line.
    P1 (6eb39d6a3) left it at 19.0.3.3.0 — this bump covers P1 + P2. If another
    session has bumped it meanwhile, go past theirs.
15. **Payload fixes from owner rulings R4 + R5** (ledger): fast-lane route row
    amber with the R4 sentence + the R4 confirm wording on the primary;
    previous-run choice narrowed to R5 (find how "kind of run" is already
    expressed — the approval context's `kind_key` / the scheme map's
    CYCLE_SELECTION in `pb_scheme_map.models.formula_scheme_assignment`, used at
    `hr_payslip_run.py:~880` — and reuse it, do not invent a new notion).
    Update T7 and add T17 (fast lane amber) + T18 (June mid-month run is NOT
    the comparison for a July end-of-month run).
16. **Big runs:** P1 measured ~630 ms for 520 payslips, most of it the
    who-signs-it-off preview. Add `get_run_screen(run_id, parts=…)` (or a
    second small RPC) so the screen renders everything else first and fills
    the route card a moment later with its own skeleton — for every run, not
    only big ones (one code path).

## Coordination (another session is deploying today)

Session `gitlocal-f3` announced live deploys of pb_contracts, pb_learn,
pb_employee_vault, pb_contract_lifecycle, pb_hr_payroll_formula, pb_scheme_map
AND **pb_payruns + pb_payrun_wizard + pb_formula_studio**. Before editing,
`git log -5 -- pb_payruns` and `git status pb_payruns` to see their changes;
never overwrite or stage their files; if you both touch one file, keep both
changes. Before your deploy: read `/opt/deploy-notes.md`, wait until every
START has a DONE, and stage from `git archive HEAD` so whatever pb_payruns
HEAD holds (theirs + yours) ships together — say in the report which of their
commits rode along. Message them (ListAgents → SendMessage to `gitlocal-f3`)
before your `-u`/restart and wait for an ack or 10 minutes.

## Non-goals (binding)

- No change to how pay is calculated, approved, paid or delivered; no new
  server behaviour beyond what P1 shipped (small payload fixes found while
  building are fine — list them).
- The Pay Run board, the payslip form and the approvals inbox are untouched.
- No change to any rize record (R2). Do not recalculate, submit or edit any
  run on rize, p0clone or payobook_template while testing.

## Safety rails

- Every widget call wrapped so one failed section shows its own error line,
  never a blank screen.
- Read the browser console after every load (PRS-G8).
- No `localStorage` for anything that matters (tab-only toggles only).

## Test cases

Python (in `test_run_screen.py` or a new file): T14 header-button guard (item
10); T15 the composed form view still validates with every module installed;
T16 `vu-no-hero` present on the form arch.
Browser (Chrome MCP, payobook.com, QA login, demo company `cids=5`) — find
demo runs in each state and walk:
B1 draft with payslips: hero, ticks, primary "Send for approval" opens its
   confirm; press Cancel (do not send).
B2 draft with no payslips (create a NEW run only if the demo world has none;
   name it "DEMO PRS empty run" and delete it afterwards): empty card, Make
   payslips opens the generate window; close it.
B3 pending run: who-signs-it-off shows live seats; primary right for the QA
   user.
B4 done run: pay-and-deliver steps; primary "Pay & deliver" opens the existing
   screen; go back.
B5 people: search, three tabs, team filter, sort each column, open quick look,
   ↑/↓, Esc, tick rows + shift-range, bulk bar appears (do NOT press delete).
B6 Downloads menu: Excel and PDF download; Payroll report opens.
B7 More menu: every item opens or confirms; cancel every confirm.
B8 settings: edit working days on a draft, save, payload refreshes; revert.
B9 Show the classic layout and back.
B10 phone width (~400px): no sideways page scroll; table scrolls in its box.
B11 console: zero errors on every screen above.
B12 rize run 1591 — OPEN ONLY: date-mismatch banner reads right, currency
   ₫ with no ".00", 63 people, nothing pressed.

## Deploy (normal tier — Python, views, assets, translations)

Follow C11 to the letter: read `/opt/deploy-notes.md`, announce to other live
sessions, flock, START line, cron snapshot. Clean staging dir; stage only
`pb_payruns` (+ `pb_learn` if touched) from `git archive HEAD`; scoped
`rsync --delete` per module; stop; `-u` each module on `payobook`,
`payobook_template`, `p0clone`, `rize` one at a time (stop at the first
failure); PRS-G3 asset purge + signalling row + version bump per DB; start;
warm each site with one curl. Verify: module trees byte-identical (skip
`__pycache__`, `*.pyc`, `.DS_Store`); manifest version = `latest_version` in
all four DBs; cron counts match the last DONE line; log grep for
`Traceback|CRITICAL|ERROR` since start. DONE line. Then B1–B12.

## Report back (`PRS_P2_REPORT.md`)

1. What was built, with screenshots saved for B1, B3, B4, B5 (quick look open)
   and B12.
2. Python test results (whole pb_payruns suite) and B1–B12 pass/fail.
3. Deploy evidence (versions per DB, hashes, cron counts, log grep).
4. The breadcrumb "New" finding.
5. Learn impact (what changed, or "nothing points at the form").
6. Self-score against the design bar, and anything in the mock-up not built
   (with why).
7. New ledger rows. Commit hash(es). Do NOT push.
