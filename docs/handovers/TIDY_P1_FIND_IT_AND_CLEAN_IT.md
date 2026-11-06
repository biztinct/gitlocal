# TIDY Phase 1 — "Find it & clean it": two real doors, and the RIZE test data gone

Read `docs/handovers/TIDY_LEDGER.md` FIRST and fully, then the GROUP ledger's rules,
gotchas and deploy ritual (`docs/handovers/GROUP_LEDGER.md`). Do not re-derive the
plumbing facts; they were verified today.

## 0. What you are building, in one paragraph
The owner read "Mapping → Who is paid by what" and "Where they work" in the closeout and
could find neither. The first is a tab that says "Scheme assignment"; the second only
opens from ⌘K. Fix both so a person finds them where they would look, with the words the
owner uses. Then remove every trace of the RIZE-named test data from the live
`payobook` database (and p9clone), because it appears in pay-run pickers and on a Budget
card during customer demos. Owner authorised the deletion in writing; the ledger's rule
14 governs how.

## 1. Deliverables

### 1a. "Who is paid by what" is what the tab says
- `pb_formula_studio/static/src/js/mapping/mapping_studio.js:133` label → "Who is paid
  by what"; hint stays plain ("Say which payroll scheme pays each part of the workforce.").
  Update `pb_formula_studio/i18n/vi_VN.po` (the msgid at ~7483; keep the `#. module:`
  comment form, GR5) with the Vietnamese already used by `pb_scheme_map`'s palette row
  for the same words (read it from `pb_scheme_map/i18n/vi_VN.po`; do not invent a
  second translation). Grep every `.po`, `.js`, `.xml`, `.py` for "Scheme assignment"
  and fix all of them. Bump `pb_formula_studio` version.
- Add a **second door** so a person who is on the People side finds it too: on the
  Employee 360 there is already a "Paid by" chip (P2); leave it. Nothing else.

### 1b. "Where they work" is a lens on the People hub
- New file `pb_workseg/static/src/js/workseg_lens.js` registering into
  `pb_people_hub_lens` exactly as Pay does (`pb_pay/static/src/js/pay_palette.js:46-52`):
  `key: "where"`, `icon: "mapPin"` (add to `ic()` if absent, GROUP rule 5),
  `label: _t("Where they work")`, `Component: PbAssignmentsScreen`, `groups:
  WORKSEG_GATE`, `wantsArrival: true`, sequence **48** (after Pay 45, before Plan).
  Add the file to the manifest asset bundle after `assignments.js`; add `pb_people_hub`
  to `pb_workseg`'s `depends` only if it is not already reachable (check the graph —
  `pb_people_hub` must not depend on `pb_workseg`; a cycle fails install).
- `PbAssignmentsScreen` must work with NO `action` prop and with `props.arrival`: read
  focus from `props.arrival.focus` when present, else `props.action.context.pb_focus`.
  When embedded, hide its own back chip (the hub has one) — follow whatever
  `PbPayScreen` does with `props.embedded`.
- Inside the lens, the three things a person may want are one segmented control at
  the top, in these words: **"The month strip"** · **"Same person?"** · **"Charged
  between entities"**. The third opens `pb_workseg.action_pb_cost_transfers` in the
  breadcrumb with a return door (`pb_back` to the People hub, lens `where`); if the
  screen already has a focus switch, extend it rather than add a second one.
- Keep the ⌘K rows; point their action at the hub with `lens: "where"` and the same
  `focus`, so both roads arrive at the same place with the same breadcrumb.
- The closeout and blueprint used "Where they work"; the action name stays "Where
  people work" — make them the same words. Use **"Where they work"** everywhere
  (action name, lens, ⌘K row, chip label if it differs). Vietnamese for the new/changed
  strings in `pb_workseg/i18n/vi_VN.po`. Bump `pb_workseg` version.

### 1c. The RIZE test data is renamed (OWNER AMENDMENT 2026-09-08 — supersedes the
### deletion steps below; they are kept for the record)
Owner, after seeing the Growth Plans and Probation drawers full of good demo content on
those people: "If you have not already deleted RIZE data then even renaming it by
removing RIZE from the data is fine and even better so there is some demo data …
renaming is easier than delete." So: **rename, do not delete.**
- Employees (27) + their users/partners (15, incl. 2324): realistic Vietnamese full
  names in the style of the existing demo people, unique, no collisions; partner name =
  employee name; login `firstname.lastname@example.com`. Mapping table old→new in the
  report and the ledger phase log.
- Departments 656/657/658 → plausible names for the demo company (no "test", no codes);
  their budget lines stay.
- Pay runs 1524–1526 → names in the style of the existing runs (no "RIZE"/"test"/
  "neutral").
- Sweep every text/jsonb column (names, notes, descriptions, subjects, mail bodies,
  chatter, growth-plan objectives, probation comments, coaching notes) for "RIZE" and
  the internal codes ("P4 Manager", "P6 HR"…) and replace with the new names so the
  drawers read naturally. Anything with no sensible rename → neutral name, listed.
- Re-sweep to 0 case-insensitive "rize" outside real words; screenshots of the pay-run
  picker, Budget, Growth Plans and Probation with no RIZE (B4/B5 extended).
- Rule 14 applies to the rename as it did to the deletion: `pg_dump` first, ORM writes
  in one transaction, before/after table. If a deletion had already been committed on
  `payobook` before the amendment arrived: stop, do not restore, report.

Original deletion steps (superseded):
Scope: `payobook` (live) and `p9clone`. NOT abm, NOT payobook_template (both verified
clean; re-verify with the sweep and report the zeros).
1. `pg_dump` of `payobook` to `/odoo/backups/payobook_before_tidy_p1_<ts>.dump` (custom
   format). Same for p9clone. Record sizes and paths.
2. **Sweep** first, write it to the report as a table: for every table in
   `information_schema.columns` that has a column named `name`, `display_name`, `login`,
   `email`, `number`, `code` or `ref` (text/varchar/jsonb), count rows where that column
   `ILIKE '%rize%'` (jsonb: `::text ILIKE`). Exclude tables starting with `ir_`,
   `mail_tracking`, `bus_`, and any row where the match is "prize"/"Rizer"-style real
   words (report them, don't delete). This is how you find what the ledger table did
   not (jobs, pay bands, decision plans, lifecycle cases, pb.person, pay review lines,
   partners, mail followers…).
3. Delete via `odoo-bin shell` (server must be up for the shell; WFPLAN ledger says how)
   in ONE transaction, `sudo()`, in dependency order, each step counted before/after:
   a. `hr.payslip` in runs 1524–1526 (5) → `hr.payslip.run` 1524–1526.
   b. Fact rows for those runs: `pb.fact.run` / `pb.fact.line` / `pb.fact.emp` where the
      run id matches (ORM if the model allows unlink; else raw SQL on exactly these three
      tables, named here per rule 14). Then re-run `pb.budget.actuals` `sync()` for the
      window so the budget lines those runs produced are re-totalled.
   c. Every record the sweep found that hangs off the 27 employees (lifecycle cases,
      probation, PIP, reviews, ratings, pay changes, work segments, `pb.person`,
      applicants, attachments, `hr.version`) — ORM unlink; if a model refuses because of
      a state, force with `.with_context(force_delete=True)` or set the state that
      allows it, and say so.
   d. `hr.contract` on those employees (13) → `hr.employee` 17122–17148 (27).
   e. `pb.budget.line` on departments 656/657/658 (3) → any `pb.budget.expense` on them
      → `hr.department` 656/657/658 (children first; check `parent_id`).
   f. `res.users` 2324, 2326–2342 (15): their `res.partner` too unless the partner is
      referenced elsewhere (then archive the partner and say so). Any employee's
      `user_id` pointing at them is already gone by (d).
   g. Everything else the sweep found with "RIZE" in it (jobs, bands, plans, rule sets,
      tags, mail channels…) — delete if clearly test data; if it holds real-looking
      figures or is referenced by real rows, **stop and list it** in the report instead
      (the owner decides; do not guess).
   h. Re-run the sweep; every count must be 0 except the reported exceptions.
4. After: purge nothing else; restart not needed. Open the pay-run picker and the
   Budget lens as a validator and screenshot: no "RIZE" anywhere.

### 1d. Ledger + commits
- Append gotchas (T-numbers) and the P1 phase log to `TIDY_LEDGER.md`.
- Commits (rule 4): one for 1a, one for 1b, one for the ledger. 1c is data, not code —
  it goes in the report and the ledger phase log, with the dump paths.

Non-goals: no change to the scheme board itself; no rail item; no change to how the
month strip works; nothing on abm.

## 2. Design (the bar)
**"extreme WOW, intuitive, out-of-this-world experience, best in class."** Hero of this
phase: opening People and seeing **Employees · Contracts · Records · Pay · Where they
work · Plan** — the lens is simply there. Plain words: "Who is paid by what", "Where they
work", "The month strip", "Same person?", "Charged between entities". Zero dead-ends:
the ⌘K row and the lens land on the same screen with the same breadcrumb back to
People; the cost-transfers list has a return door. Lucide via `ic()`; no emoji. No
"Odoo" anywhere (rule 1).

## 3. Tests (p9clone; numbered)
- T1 The Mapping screen tab reads "Who is paid by what" (DOM assertion in the existing
  mapping test file; `grep` shows zero "Scheme assignment" in the repo's `pb_*`).
- T2 The People hub lens list contains `where` at sequence 48, gated by
  `WORKSEG_GATE`; a user without those groups does not see it (existing hub-lens test
  pattern in `pb_pay/tests` or `pb_records/tests`).
- T3 Arriving via ⌘K with `focus: "merge"` and via the lens with `pb_focus: "merge"`
  both open "Same person?"; arriving with no focus opens the strip.
- T4 The RIZE sweep on p9clone returns 0 after deletion; the sweep on abm and
  payobook_template returns 0 before; the pay-run picker's RPC no longer returns a run
  named RIZE; `pb.budget.get_board` no longer has a function named RIZE.
- T5 Earlier suites for `pb_workseg`, `pb_formula_studio` (mapping tests only, they are
  large), `pb_people_hub`, `pb_budget` green (same known drift set as GROUP P7).
Browser (p9clone then payobook; validator; 1440 + 390; EN + VI; `docs/handovers/
tidy_p1_shots/`): B1 People hub with the new lens; B2 the lens open (strip), the
"Same person?" segment, the "Charged between entities" segment and its way back;
B3 Mapping tab "Who is paid by what"; B4 pay-run picker with no RIZE cards; B5 Budget
heat view with no RIZE tile; B6 ⌘K "Where they work" row lands on the lens.

## 4. Deploy
p9clone (tests + data cleanup rehearsal) → payobook (dump, deploy, upgrade
`pb_formula_studio pb_workseg`, cleanup, asset purge) → abm → payobook_template
(deploy + upgrade only; NO data step). Verify versions and tree hashes per DB.

## 5. Report back
1. Three sentences: where the two screens now are, what was deleted, what was kept.
2. The sweep table before/after per DB, dump paths and sizes, the exceptions list (rows
   named RIZE you did NOT delete and why).
3. T1–T5 / B1–B6 table; deploy evidence per DB; commits; new T-gotchas; self-score
   against the bar.
