# ORGCHART P1 — the chart, read-only (new module `pb_orgchart`)

Read `docs/handovers/orgchart/ORGCHART_LEDGER.md` first. Its §0 rules, §1
facts and §2 decisions bind this phase; do not re-derive anything listed
there. Then open `docs/design/org-chart-poc.html` in a browser and use it for
ten minutes: it is the spec. Port its behaviour; do not redesign it.

## 1. Scope

Deliver a new module `pb_orgchart` that adds an **Org chart** tab to the People
hub, right after Employees, showing the real company from `hr.employee.parent_id`.
Read-only in this phase: everything a person can *see* in the POC, nothing they
can *change*.

1. **Module skeleton**: manifest (summary in plain English, no "Odoo"),
   `models/pb_orgchart.py` (AbstractModel facade `pb.orgchart`), `security/`
   (no new models → no access CSV; still create the folder with a README if
   empty is awkward), `static/src/{js,xml,scss}`, `i18n/vi_VN.po`, `tests/`.
2. **Lens registration** `static/src/js/orgchart_lens.js`: clone
   `pb_workseg/static/src/js/workseg_lens.js`; key `orgchart`, icon `workflow`
   (or `gitBranch` if it reads better on the rail — screenshot both, pick one,
   say which), label `_t("Org chart")`, Component `PbOrgChart`, groups
   `EMPLOYEE_GATE` imported from `@pb_people_hub/js/people_hub`, sequence 30.
   Also register the component as client action tag `pb_orgchart` (standalone
   door + `requires` probe for P4's ⌘K row).
3. **Payload RPC** `pb.orgchart.get_chart()` (ledger D4):
   ```python
   {
     'people': [{'id', 'name', 'ini', 'title', 'dept_id', 'dept', 'loc', 'type',
                 'joined': 'YYYY-MM-DD' | False, 'manager_id': int | False,
                 'dotted_id': False,            # P2 fills this
                 'status': '' | 'new' | 'leave' | 'leaving', 'status_note': '',
                 'user_id': int | False, 'avatar': '/web/image/hr.employee/<id>/avatar_128' | False}],
     'open_roles': [{'id': 'job-<id>', 'job_id', 'title', 'dept_id', 'dept', 'loc',
                     'count', 'manager_id': int | False, 'hiring': 'Open · 2 to fill'}],
     'departments': [{'id', 'name', 'color': '#hex'}],
     'locations': ['Hà Nội', ...], 'types': ['Full-time', ...],
     'me': int | False, 'may_write': bool, 'truncated': bool,
     'counts': {'people': n, 'open': n, 'no_manager': n, 'levels': n},
   }
   ```
   * `status`: `new` when joined within 30 days (`_join_date` helper, ledger
     §1); `leave` when `'is_absent' in Emp._fields and e.is_absent` (hr_holidays
     installed) with note "On leave today"; `leaving` when a departure date
     within 30 days exists — use `departure_date` if `'departure_date' in
     Emp._fields` (grep `hr/models/hr_employee.py` / `hr_version.py` first;
     if it lives on the version, read through the employee), else the running
     contract's `date_end` within 30 days. Note: "Last day 28 Nov".
   * `type`: ledger §1 (employee_type or contract type), mapped to plain
     words: employee → "Full-time", contractor/freelance → "Contractor",
     student/trainee → "Trainee", part-time only if the contract type says so.
   * `loc`: `work_location_id.name` else `address_id.city` else
     `company_id.name`.
   * Department colours: a fixed 10-colour palette (the POC's eight plus two)
     assigned by department id order; stable across loads.
   * Open roles: ledger D3 — this phase reads `hr.job` where
     `no_of_recruitment > 0` in the allowed companies; `manager_id` =
     `department_id.manager_id.id` (the `pb_manager_id` field arrives in P2;
     write the resolver so P2 only adds the first branch).
   * Everyone active in `self.env.companies`. `may_write` =
     `self.env.user.has_group('hr.group_hr_user') or has_group('base.group_system')`
     — P1 only *reports* it (the client hides nothing yet, there is nothing to
     hide); P2 uses it.
   * `truncated`/`get_branch(manager_id)` per D4. Implement both; test with a
     forced limit (context key `pb_orgchart_limit`) so the test does not need
     1,500 people.
   * Per-person try/except (ledger §0.9). One `search_read` for employees, one
     for jobs, one for departments. Measure: payload for rize must build in
     under 1 s (log the timing at DEBUG; report it).
4. **The component** `static/src/js/orgchart.js` (+ `orgchart.xml`,
   `orgchart.scss`), class `PbOrgChart`, root `pbim pbim-page pboc`, loading
   with `.pbim-busy`. Port from the POC:
   * Layout: `layout()` with leaf stacks (`app.js` layout block, G3),
     `bounds()`, `fit()` (min zoom 0.42, centre-on-top rule), `centerOn()`,
     `zoomAt()`, pan (pointer), wheel (ctrl/⌘ = zoom, else pan; preventDefault;
     `touch-action:none`), minimap with click-to-go.
   * Head: breadcrumb "People · Org chart", title, the one-sentence subline
     ("67 people across 8 teams, 4 levels deep · 2 open roles · updates itself
     whenever an employee record changes"), actions: **Find me** (hidden when
     `me` is false), **Export ▾** (Spreadsheet = client-side CSV like
     `pb_people`'s export; Print = `window.print()` with the POC print CSS;
     Picture/PDF/Share rows present but marked "Coming soon" and disabled —
     P4), and the primary button slot (P2's "Plan changes" — leave an empty
     slot, do not draw a dead button).
   * The six numbers that focus: per manager, open roles, no manager yet,
     wide teams (10+), dotted lines (0 in P1, grey), new this month. Pressing
     one dims everyone else and shows the bottom hint pill with "Show
     everyone".
   * Toolbar: search (⌘K-free: `/` focuses it; suggestions list with arrow
     keys + Enter = jump), Team / Location / Employment chips with menus (G1
     wrapper), Colour-by chip, Levels chip, view segment (Top-down · Sideways
     · Teams · List), Compact chip. Floating tools top-right of the canvas:
     zoom −/%/+/fit, expand all, collapse, keyboard help. (The time machine
     button is P3 — do not draw it.)
   * Cards: avatar (real `/web/image` avatar when the employee has one, else
     initials on the team colour), name, title, team · location, tags (open
     role, joined N days ago, on leave, leaving, N direct reports / wide
     span), hover quick actions (P1: only "Open side panel"; the +/move/more
     buttons arrive in P2 — leave the pill with one button, not three dead
     ones), the +N / chevron toggle, `stk` toggle placement, "You" ribbon on
     `me`, dashed amber open-role card.
   * Edges: SVG bezier top-down / sideways, elbow trunk for stacks, highlight
     of the chain on hover/selection (drawn last), dotted amber edges (P2
     data, draw the code path now).
   * "No manager yet" lane above the chart for people without a manager
     (and open roles without one), wording from the POC. On a company where
     *nobody* has a manager (nomgr scenario) show the POC's empty state copy
     but with the button reading "Set managers on the employee records" and
     opening Employees (the suggest feature is P3; do not promise it).
   * Side panel (right, overlays the canvas under 1500 px): profile, status
     note banner, chain of managers (each a button that selects that person),
     facts (Reports to, Also reports to "—", Team size direct · total, Level
     n of m, With us, Employment, Employee record → **Open**), tabs Team /
     Peers (History is P2 — render the tab disabled with tooltip "Coming
     soon"? No: do not draw it until P2). Footer buttons: P1 only **Open
     employee record** (drawer via `pb_people_drawer` registry, else the
     `pb_employee_detail` action). The "Add team member / Change manager /
     Dotted line" buttons arrive in P2.
   * Views: Teams grid (per department, lead first), List (indented table,
     fold toggles).
   * Keyboard: arrows, Enter, Space, `/`, F, E, C, +, −, Esc.
   * Legend pill that opens on hover; colour-by legend contents.
   * States: loading, empty (no employees → "Nobody is in the roster yet" +
     Employees door), error (payload failed → sentence + Retry), truncated
     (banner "Showing the top 3 levels of 1,840 people — open a team to load
     it"), huge (420 people must render under 400 ms after payload; measure).
   * `embedded` prop accepted and ignored (the shell passes it).
5. **Standalone action** `views/pb_orgchart_action.xml`: client action
   `action_pb_orgchart` (tag `pb_orgchart`, name "Org chart") so a deep link
   and P4's ⌘K row have an XMLID. Not on the sidebar (the hub tab is the door).
6. **Translations** `i18n/vi_VN.po` for every JS/Python string (ledger §0.8).
7. **Unit tests** (§5) and the **report** (§7).

### Non-goals (binding)
* No writes of any kind, no drag-and-drop, no dialogs that change data. (Port
  the pointer-drag code only if it is trivially switched off; otherwise leave
  it for P2.)
* No dotted-line field, no `pb_manager_id` on jobs, no planning mode, no time
  machine, no suggest-a-chart, no picture export, no ⌘K rows, no lessons.
* No change to `pb_people_hub`, `pb_people`, `hr`, or any other module except
  **adding missing Lucide paths to the kit** (ledger §1 Design system) in its
  own commit.
* No pay data on the chart (ledger D8).

## 2. Plumbing — verified, do not re-derive

All in ORGCHART_LEDGER §1. Of note for this phase:
* Lens registration precedent `pb_workseg/static/src/js/workseg_lens.js`;
  gate `EMPLOYEE_GATE` `people_hub.js:67-72`; sequence 30.
* Facade precedent `pb_people/models/pb_people.py` — `_initials :18`,
  `_join_date :23`, `_safe :41`, `_fields` guard `:59`; roster row
  try/except `:455-463`.
* Component precedent `pb_people/static/src/js/people.js` — services,
  `onWillStart` load, drawer registry `:63-71`, action fallback `:122-123`.
* Shell lens contract `hub_shell.js:73-109`; child props `:518-525`.
* Employee fields `hr/models/hr_employee.py:191-199`; version fields
  `hr/models/hr_version.py:119-122`.
* Jobs `hr/models/hr_job.py:17-21`.
* Manifest/assets precedent `pb_people_hub/__manifest__.py` (assets under
  `web.assets_backend`, XML templates listed there too).

## 3. Design to build

Hero moment: the chart **draws itself** — cards settle into place with the
POC's 350 ms ease, the chain to the top lights up when you hover anyone, and
the six numbers at the top turn into filters the moment you press them.

### 3.1 Python — `models/pb_orgchart.py`
```python
class PbOrgChart(models.AbstractModel):
    _name = 'pb.orgchart'
    _description = 'Payobook org chart data'

    LIMIT = 1500
    PALETTE = ['#5A4BB0', '#0F7B4F', '#2563EB', '#B45309', '#0F7C6B',
               '#DC2655', '#7C3AED', '#64748B', '#0E7490', '#9D174D']

    @api.model
    def get_chart(self):
        Emp = self.env['hr.employee']
        co_ids = self.env.companies.ids or [self.env.company.id]
        ... one search_read on hr.employee (fields list, active, company in co_ids)
        ... one search_read on hr.job (no_of_recruitment > 0)
        ... one search_read on hr.department (for colours + manager_id)
        ... build rows with try/except per person
        ... truncation: if len(rows) > limit: keep depth <= 2 (compute depth from manager map), truncated=True
        return payload

    @api.model
    def get_branch(self, manager_id):
        """Everyone under this manager, any depth — same row shape."""
```
Mirror `pb_people`'s style: helpers at module level, `_logger.debug` on a bad
row, never raise to the client.

### 3.2 JS — files
* `static/src/js/orgchart.js` — the component (state, payload, layout,
  render helpers as getters/methods; the OWL template reads positions from a
  `useState` map so cards animate through CSS transitions on `transform`).
* `static/src/js/orgchart_layout.js` — pure functions ported from the POC
  (`layout`, `bounds`, `effMgr`, `kids`, `descendants`, `ancestors`,
  `colorOf`, `legendItems`). Unit-testable in isolation; keep them free of
  DOM.
* `static/src/js/orgchart_lens.js` — registration (§1.2).
* `static/src/xml/orgchart.xml` — templates: page, head, kpis, bar, canvas
  (nodes `t-foreach` over positioned rows, edges `t-raw` of an SVG string is
  acceptable), side panel, list, teams, minimap, hint, empty/error states.
* `static/src/scss/orgchart.scss` — the POC CSS under `.pbim.pboc`.

OWL notes: positions/transforms as inline `t-att-style`; edges SVG built as a
string in a getter (`t-out` of a markup — the markup must be created ONCE per
change, not per render, see memory "OWL markup flicker"); wheel listener added
in `onMounted` with `{ passive: false }` on the canvas ref; keyboard listener
on the page root with `tabindex="0"`, removed in `onWillUnmount`.

### 3.3 Words on screen (plain English; reuse the POC's)
Title "Org chart". Subline as the POC. Numbers: "per manager", "open roles",
"no manager yet", "wide teams (10+)", "dotted lines", "new this month".
Lane: "No manager yet · set a manager on the employee record". Empty: "Nobody
is in the roster yet". Error: "The chart could not be loaded. Try again." with
a Retry button. Truncated banner as §1.4.

## 4. Safety rails
* Read RPC never writes; no `sudo()` for employee reads (the gate already
  grants read). Jobs/departments may be read with `sudo()` only for names and
  counts if the user lacks hr.job read — try without first, report which.
* Multi-company: `self.env.companies`, never `self.env.company` alone.
* Archived employees never appear. A manager who is archived or in another
  company makes the person a root (lane), not a crash.
* No per-row RPC; no N+1 (`search_read`, then dicts).

## 5. Test cases (numbered — run them all, report each with evidence)
Unit (`pb_orgchart/tests/test_orgchart_p1.py`, `TransactionCase`, build a
small company: CEO → 2 heads → 5 staff, one open job, one person without a
manager, one archived):
1. `get_chart()` returns every active person once, `manager_id` correct, the
   archived one absent.
2. The person with no manager has `manager_id: False` and `counts.no_manager == 1`.
3. The open job appears in `open_roles` with `manager_id` = the department's
   manager and `count == no_of_recruitment`.
4. Department colours are stable across two calls and distinct for the first
   10 departments.
5. With context `pb_orgchart_limit=3`, `truncated` is true, only depth ≤ 2
   rows return, and `get_branch(head_id)` returns the head's staff.
6. A person whose manager is archived becomes a root (no exception).
7. `status` is `new` for a person whose first contract started 10 days ago.
8. A person with `is_absent` (skip if hr_holidays absent — say so) gets
   `status == 'leave'`.
9. `me` equals the current user's employee id; `False` for a user with none.
10. `may_write` is true for an HR user, false for a plain user.
Browser (rize + payobook, Chrome MCP, console clean):
11. People hub shows the **Org chart** tab after Employees; opening it draws
    the chart under 2 s; subline numbers match `counts`.
12. Hover a card: chain highlights; click: side panel with chain buttons;
    chain button selects that person and centres.
13. Press +N on a stacked/folded manager: branch opens with the POC motion;
    press the chevron: folds.
14. Each of the six numbers focuses and the hint pill clears it.
15. Search "agronomist" → suggestions; Enter jumps and opens the panel.
16. Team filter, Location filter, Employment filter, Colour-by location,
    Levels = 2 each change the canvas; Clear (×) restores.
17. Sideways, Teams, List, Compact each render; List fold toggles work.
18. Zoom −/+, fit, wheel-pan, ⌘-wheel zoom, minimap click.
19. Keyboard: arrows move selection, Enter opens panel, Space folds, F fits,
    Esc closes.
20. Find me centres on the signed-in person (rize: a user with an employee
    link — see memory "Login not linked"); hidden when the user has none.
21. Open employee record opens the drawer (payobook has the vault) and the
    fallback action where it is absent (test by temporarily removing the
    registry entry in the console, or on a DB without the vault — say which).
22. Export → Spreadsheet downloads a CSV with name, title, team, manager,
    location; Print opens the print dialog with the chart alone.
23. Narrow window (1150 px): side panel overlays, toolbar wraps without
    overlap, KPI strip compact.
24. A company with nobody managed (p0clone or a demo company: temporarily
    clear `parent_id` on a test company's employees in a transaction you roll
    back, or use the unit test) shows the lane + empty-state copy.
25. No console errors on any of the above; no "Odoo" anywhere on screen.

## 6. Deploy / verify
Ledger §0.4. `full` deploy (new module, must be **installed** on all four
DBs — `-i pb_orgchart`, then verify `ir_module_module.state='installed'` and
`latest_version` per DB). Asset purge + restart. Then the browser cases on
rize and payobook.

## 7. Report back — `docs/handovers/orgchart/ORGCHART_P1_REPORT.md`
1. Files added/changed, commits (hashes), kit icon additions.
2. Each numbered test with evidence (unit log excerpt; screenshot paths under
   `docs/handovers/orgchart/p1_shots/`).
3. rize facts: active employees, how many have a manager, open jobs, depth,
   payload build time, render time; same for payobook.
4. Whether `hr_org_chart` is installed per DB (informational).
5. Deploy table (ledger §0.4 format).
6. Self-score against the design bar (ledger §0.2) with one honest sentence
   per bullet; deviations from the POC and why.
7. Gotchas for the ledger §3 (append them yourself, numbered G5+).
8. Learn lessons/tours that mention People tabs (for P4).
9. Anything P2 needs that you prepared (e.g. the drag code switched off).
