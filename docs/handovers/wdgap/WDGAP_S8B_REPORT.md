# WDGAP S8-B — A person's working life: report

Branch `wdgap-s8b` (from `origin/19.1` @ abc2259b6), not merged, not deployed.
Three NEW modules; **no existing file was edited** (everything else by
`_inherit`, template inheritance and `patch()`).

| Module | Version | Depends (hard) |
|---|---|---|
| `pb_job_change` | 19.0.1.0.0 | base, hr, mail, om_hr_payroll, biz_audit_trail, biz_approval_workflow, pb_approval_config, pb_hr_payroll_formula, pb_import_kit, pb_filter_kit, pb_hub, pb_pay, pb_lifecycle, pb_employee_vault, pb_orgchart, pb_scheme_map, pb_records (`pb_retro` is a PROBE, never a dependency) |
| `pb_contract_rules` | 19.0.1.0.0 | base, hr, om_hr_payroll, pb_import_kit, pb_hub, pb_contract_lifecycle, pb_records |
| `pb_agency_staff` | 19.0.1.0.0 | base, hr, mail, pb_import_kit, pb_filter_kit, pb_hub, pb_people, pb_people_hub, **pb_vendor_access** (the agency is a vendor — the deploy agent must check it is installed on every tenant first, or installing this module installs it) |

## 1. What was built

### 1.1 `pb_job_change` — one guided "Change job"

- **`pb.job.change`** (+ `pb.job.change.line`): one person, one reason kind
  (Promotion / Transfer / Pay change / Something else), one start date, one
  reason, and every new value: job, job title, team, manager, place of work,
  working hours, company, monthly pay, pay lines.
- **One sign-off route (J1)**: new process key **`jobchange`** ("Job changes",
  area people, money) in the module's own data file; default route seeded per
  company (post-install + new companies), reusing the existing seats:
  **Their manager** (only when the manager has a login — fact `has_manager`;
  rize's 40 managers without a login would otherwise block every request) →
  **HR lead** → **Finance approver only when `above_guidance`** (the company's
  Pay setting "Finance signs pay changes above …%", the same fact
  `pb.pay.change` uses). Route facts: kind, changes_pay, pay_rise_pct,
  above_guidance, above_band, changes_team, changes_scheme, has_manager,
  new_wage. Seats read their request (record rule); the adapter reads its own
  context/detail under sudo (W2B-2) — proven with a Finance approver holding
  no HR or payroll group (JC15).
- **Everything together, on the start date**: the person (current version in
  place) AND the running contract's job / team / working hours / company
  (facts §1.1), the wage with a `pb.pay.apply` row (`job_change_id`, old wage
  kept, `letter_state='none'` so the Pay job never prints a pay-review letter
  for it), every pay line get-or-create with a **dated**
  `hr.contract.advantage.change` row (effective date = start date), and — when
  the paying scheme has a BASIC/WAGE/BASE input — a dated change row for the
  wage too, so the Past-month re-work and proration can see it. All in one
  savepoint: all or nothing.
- **Future dates**: approved → "Approved, starts later" (`scheduled`),
  **nothing written**; the quiet hourly job `Change job: start approved changes
  on their day` writes it in the company's time zone (the Records desk's
  `_today_for`), row-locked (SKIP LOCKED), idempotent, one transaction per
  change, three bad days → sent back with a quiet to-do (never an email).
- **Moved since**: every value it covers is snapshotted when sent; at apply
  (or on the day) a value somebody else moved → nothing written, named in the
  sentence; a scheduled one is sent back.
- **Past dates (J2)**: allowed; the finished request lists the months already
  paid (finished regular-run payslips ending on/after the start date) with
  **"Re-work those months"**: it opens a NEW **draft** Past-month re-work for
  that person, that scheme and those months through `pb_retro`'s own door and
  gate (`pb.retro.board.save_review`), straight on that re-work. No back-pay
  input is written (C-6). `pb_retro` is probed (`'pb.retro.review' in env`);
  the JS door looks the board up in the actions registry when pressed (no
  import). Without it: "Tell the pay team: they can work out any difference by
  hand on the next pay run."
- **Take it back**: 24 hours, only when nothing moved since: person, contract,
  wage (`pb.pay.apply._restore`), pay lines (with reverse dated change rows)
  and the letter voided.
- **Letters** by `selection_add`: Promotion letter / Transfer letter / Job
  change letter (template made once in code, filed in the vault).
- **One event on the trail**: one `biz.audit.entry` summary; the person's
  timeline folds every field line the write produced into one "Job changed —
  Promotion" item.
- **"Paid by" before/after**: a read-only context override of the scheme map's
  roster read (`_departments_for`); the screen says "Paid by changes from X to
  Y" and the route gets `changes_scheme`. It also names the scheme's pay items
  that read a moved value (application-data keys + record sources).
- **Screens**: "Job changes" board (quiet glance, filter kit), person picker,
  guided flow (1 What changes · 2 The details · 3 When and why) with a live
  "What this does" panel worked out on the server, one change's page (status,
  before/after, sign-off progress, banners, letter, take back, cancel).
  Doors: a **"Change job"** icon button (tooltip "Change job: …") in the person's side panel header + a chip
  when a change is waiting or starts later; **"Change job"** in the org chart
  person panel; ⌘K 4460 "Change someone's job", 4461 "Job changes".
- Rights: prepare/see = HR manager, pay manager, payroll manager; pay
  FIGURES only for the pay team — an HR manager without pay rights sees no
  wage and cannot send a pay change ("The pay team adds pay changes").

### 1.2 `pb_contract_rules` — fixed-term renewal rules (J3)

- **`pb.contract.rule`** (editable by HR managers and lifecycle managers; list
  + form, ⌘K 4465 "Fixed-term contract rules", "The rule" button on the
  decision drawer): country, optional company (a company row wins), contracts
  allowed in a row, longest single contract, longest time in a row, the break
  that starts a new row, "What counts", "Where the rule comes from".
- Seed rows (noupdate): **Vietnam** 2 in a row, 36 months each (Labour Code
  2019 art. 20); **Indonesia** 60 months in a row (PP 35/2021 art. 8). Both say
  "To confirm with an adviser".
- **Counting**: contracts with an end date, excluding trial agreements
  (`vietnam_contract_type`/`pb_payroll_contract_type` = probation), linked by
  renewal or starting within the break; plus HR-typed
  **"Earlier fixed-term contracts (before this system)"** and months on the
  person (HR-only fields; on the employee form Settings tab and in the Updates
  catalogue via `_master_fields`, super() kept).
- **Extend past the rule**: red warning in the decision dialog with the
  sentence ("This would be fixed-term contract number 3 in a row. Vietnam
  rule allows 2, then the next one should be permanent."), what was counted,
  the source, and **"Make it permanent instead"** beside it. **Never blocked.**
  The reason (already required) is written down as the reason for going past
  the rule, on the decision and the extension; the extension's route gains the
  fact **`past_fixed_term_rule`** and its detail a "Fixed-term rule: Goes past
  it" chip; the new contract gets a note.
- Drawer line: "Fixed-term contract 2 in a row · In a row since … · The next
  one should be permanent under Vietnam rule."

### 1.3 `pb_agency_staff` — agency staff (J5)

- **`pb.agency.worker`**: name, agency (`pb.vendor`), role, team, site,
  manager here, start/end, phone, email, notes, papers (PDF/PNG/JPG ≤ 10 MB),
  status (on site / starting later / ended). **Not an employee**: no employee,
  contract, login or payslip link — nothing in pay, time or payslips can point
  at it (AG1 scans the registry).
- People › **"Agency staff"** lens (sequence 59), ⌘K 4470; quiet glance (on
  site, starting later, ending in 30 days, ended), filter kit, side drawer
  (add / change / papers / "Last day is today" / delete for HR managers).
- **"+N agency staff" beside the People headcount**, never added to it
  (`pb.people._roster_kpis` + a `patch()` of the glance; shown only when > 0).
- The agency's drawer in **Vendors** lists "Their people here" (HR only).
- Rights: HR officers keep them, HR managers delete; company rule.

## 2. Cross-step contract C-1 (binding, for S6-B)

`env['pb.job.change'].pb_start_for_employee(employee_id, vals=None)` →

```python
{'type': 'ir.actions.client', 'tag': 'pb_job_change', 'name': 'Change job',
 'target': 'current', 'params': {'employee_id': <id>, 'vals': {...cleaned}}}
```

Creates nothing; the guided flow opens prefilled and the person reviews and
sends it. `employee_id` may be an id or a record; an unknown person raises
`UserError`. Accepted `vals` keys (anything else is dropped):

| Key | Type | Fills |
|---|---|---|
| `job_id`, `department_id`, `parent_id`, `work_location_id`, `resource_calendar_id`, `company_id` | int (or record) | new job / team / manager / place of work / working hours / company |
| `job_title` | str | new job title |
| `wage` | float | new monthly pay (turns the Pay section on) |
| `lines` | `[{'code': str, 'amount': float}]` | new pay-line amounts |
| `effective_date` | date / 'YYYY-MM-DD' | start date (else today) |
| `reason` | str | why |
| `reason_kind` | 'promotion' / 'transfer' / 'pay' / 'other' | kind (default promotion) |
| `source`, `source_ref` | str | where it came from (e.g. `'internal_hire'`, the applicant ref) — kept on the record |

Probe for it with `'pb.job.change' in env`.

## 3. Tests

Local database `wdgap_s8b_t` (copy of `upd_p6_t_tpl` brought to the worktree
tree, 33 modules `-u`, `pb_retro` installed), dropped afterwards.

### 3.1 New suites — 32 tests (JC1–JC15, CR1–CR9, AG1–AG8), 0 failed

| # | Case | Result |
|---|---|---|
| JC1 | C-1 action, prefill, unknown keys dropped, nothing created | PASS |
| JC2 | one route: manager (login) → HR → Finance only above guidance; no manager login → step left out | PASS |
| JC3 | apply today: person + contract together, wage + `pb.pay.apply`, dated pay-line and wage change rows, letter, one trail line | PASS |
| JC4 | future date: scheduled, nothing written, job writes it on the day, second run writes nothing | PASS |
| JC5 | moved underneath: refused and named; scheduled one sent back | PASS |
| JC6 | past date in a paid month: months listed, dated row, draft re-work for that person/month/scheme opened (same one twice), no back-pay row, finished payslip identical; without the re-work module a calm sentence | PASS |
| JC7 | take back within 24 h; refused after the window; refused when moved since | PASS |
| JC8 | rights: HR officer refused; HR manager without pay rights sees no figure and cannot send pay; seat manager reads only their seat; another company sees nothing | PASS |
| JC9 | checks: nothing changes, own manager, cycle, a year ahead, reason, second live change | PASS |
| JC10 | letter types by selection_add; transfer letter made | PASS |
| JC11 | silent install: quiet job on an empty set, process row, route seeded for a new company, empty board | PASS |
| JC12 | "Paid by" what-if read-only; scheme change shown | PASS |
| JC13 | golden: a finished payslip's lines byte-identical after a job change | PASS |
| JC14 | timeline shows ONE event, field lines folded | PASS |
| JC15 | real route decided seat by seat (manager → HR lead → Finance with no HR/payroll group); Finance's decision writes it | PASS |
| CR1 | seed rows + sources; negative numbers refused | PASS |
| CR2 | counting: link, short break, long break, trial excluded, earlier contracts typed in | PASS |
| CR3 | Vietnam 3rd contract → warning, never blocked; 40-month contract → warning; first renewal → none | PASS |
| CR4 | Indonesia > 60 months → warning; within → none | PASS |
| CR5 | extension past the rule allowed, reason still required, written down, route fact + detail chip | PASS |
| CR6 | drawer line "2 in a row", rose, "next one should be permanent" | PASS |
| CR7 | Updates catalogue gains the two fields (super kept); HR-only `groups=` | PASS |
| CR8 | no rule for the country: silent | PASS |
| CR9 | a company's own rule wins | PASS |
| AG1 | never payroll by construction (no links; registry scan) | PASS |
| AG2 | "+N" beside the headcount, headcount unchanged, only those on site | PASS |
| AG3 | board figures + filters + search by agency | PASS |
| AG4 | rights (plain user refused, HR officer keeps, HR manager deletes, other company invisible) | PASS |
| AG5 | checks (dates, foreign manager, name; last day today) | PASS |
| AG6 | papers: types, add, remove | PASS |
| AG7 | Vendors drawer lists them for HR only | PASS |
| AG8 | silent install: no job, empty board | PASS |

### 3.2 Suites of the modules inherited from (no file edited)

Run on the same database before the new modules existed (baseline) and with
them installed (after), same code otherwise:

| Suite | Baseline | After |
|---|---|---|
| pb_contract_lifecycle, pb_employee_vault, biz_audit_trail, pb_lifecycle, pb_orgchart, pb_scheme_map, pb_vendor_access | 0 failed | 0 failed |
| pb_pay | 2 failed: `TestVietnameseIsComplete.test_t4c…` (catalogue), `TestPayBands.test_t02…` (timing, 3.05 s > 2 s) | 1 failed: the same t4c, identical assertion text; t02 passed (timing) |
| pb_people_hub | 2 failed: `test_the_contracts_action_opens_the_board_with_a_way_back`, `test_the_lens_order_matches_the_mockup` | the same 2, identical assertion text |
| pb_records | 1 failed: `TestRecordsR4Polish.test_15f…` (timing) | 0 failed (timing) |
| **Total** | 696 tests (after) | **3 failed, 0 errors — all in the baseline set, same messages** |

The after-run includes the three new suites.

Static gates: `py_compile` every file, `node --check` every JS file, every XML
parses, white-label grep of the three modules' XML/JS/SCSS/PO clean, PO gate
(`PoFileReader`) on all six files: placeholders identical per entry, no
"Odoo" in any msgstr — pb_job_change 300 entries (258 code strings that reach
a screen), pb_contract_rules 57 (21), pb_agency_staff 93 (86), in vi and id.
Untranslated entries are only generic inherited field labels (Created by,
Followers…).

### 3.3 Browser walk (local `s8b.localhost:8795`, `--max-cron-threads=0`)

Seed (local only, scratchpad `s8b/seed.py`): DEMO An Tran (Accountant, Finance,
20,000,000 ₫ + meal 730,000 ₫, a finished October payslip on scheme "DEMO
Office — End-Month"), DEMO Lan Nguyen (manager with a login), DEMO Binh Le
(2nd fixed-term contract, renewed from the first, ends in 30 days), three
DEMO agency staff of "DEMO Staffing Partners".

- People › Employees: "+2 agency staff" beside "4 Headcount" (headcount
  unchanged); "Change job" on An's side panel opens the guided flow.
- Change job: kinds, sections, step 2 (job → Senior Accountant, team → Tax,
  pay 26,000,000 ₫, meal 1,000,000 ₫), step 3 (15 Oct, a past month): the
  panel said "a date in the past", "starts in a month already paid: October
  2026", the route "Their manager (DEMO Lan Boss) → HR lead → Finance
  approver" and "Finance signs too, because the rise is above the guidance".
  Sent → "Sent for approval — DEMO Lan Boss"; page "Waiting for DEMO Lan Boss".
- Decided seat by seat (manager, HR, Finance — DEMO logins): Done. The page
  shows before/after, the paid-month banner and "Re-work those months" → the
  Past-month re-work opened straight on a NEW draft re-work "DEMO Office —
  End-Month · Oct 2026 · Change job JC00105: DEMO An Tran's change starts on
  15 Oct 2026, in a month already paid."
- Employees: An reads Senior Accountant · DEMO Tax; monthly wage total moved
  to 41.0M; org chart card moved under DEMO Tax; the org chart person panel
  shows "Change job". Timeline: ONE item "Job changed — Promotion · From 15
  Oct 2026 · Job … · Team … · Monthly pay … · Meal allowance …".
- People › Agency staff (inside the hub, rail did not scroll): glance 2 on
  site / 1 starting later / 1 ending in 30 days / 0 ended, filters, drawer.
- People › Contracts › Binh: "Fixed-term contract 2 in a row · In a row since
  15 Dec 2024 · The next one should be permanent under Vietnam rule" (rose)
  with "The rule"; "Extend it" shows the red "This goes past the fixed-term
  rule" box with the counted line, the source and "Make it permanent
  instead", which switches the dialog to Make it permanent.
- vi / id: server sentences come back translated (state "Hoàn tất", kind
  "Thăng chức", rows "Công việc"; Indonesian rule sentence "Ini akan menjadi
  kontrak waktu tertentu ke-3 berturut-turut…").
- Console: no errors on any of these screens.

Walk findings, all fixed and covered by a test where it was logic:
1. Kind buttons had no words — a second `_label` method of the same model
   (record names) shadowed the selection-label helper → renamed
   `_sel_label`; JC1 asserts the labels.
2. "Monthly pay 0 ₫ → …" in the preview — the unsaved copy had no contract;
   "now" now reads the running contract; JC9 asserts it.
3. The contract decision drawer raised "missing 1 required positional
   argument" — my `get_contract` override (and the Vendors `get_vendor` one)
   lacked `@api.model`, so the RPC id became a recordset → fixed; CR6 and AG7
   now call through `call_kw`, the RPC door.
4. Agency drawer's Role box empty (`job_title` not returned) → fixed; AG4.
5. The person panel header was crowded by a fourth button → "Change job" is
   an icon button with its words in the tooltip; capitalised status badges
   ("On Site") → `text-transform: none`; the person picker's search had a
   double border; sign-off step "now" dot.
6. Locally the letter is not printed (no wkhtmltopdf on the Mac: "Unable to
   find Wkhtmltopdf"); caught, logged, the change still applies. The server
   has it; in tests the letter is made (HTML).

## 4. Rails

| Rail | Result |
|---|---|
| Nothing written before the start date | JC4 (person, contract, wage, pay lines, change rows all unchanged while scheduled) |
| Payslips of untouched people/contracts unchanged; no recompute | JC13 (finished payslip byte-identical); nothing recalculates a payslip |
| No back-pay input (C-6) | JC6 (retro-adjustment count unchanged; only a DRAFT re-work through pb_retro's own door) |
| Scheme change shown before sending | JC12 + preview "Paid by changes from X to Y", route fact |
| Never two open contracts / never a new contract | the change writes the running contract in place |
| Fixed-term rule never blocks | CR3, CR5 (`blocked` empty, extension created) |
| Agency staff cannot reach pay | AG1 |
| Silent install | JC11, AG8; one quiet hourly job (pb_job_change), no mail, no data except the two rule rows and the route seed |
| White-label | gates above |

## 5. Must-report items (not fixed — other modules' files)

1. **Pay › Changes writes the wage at once and ignores its start date**
   (`pb_pay/models/pb_pay_change.py` `action_apply`, the `contract.wage` write
   ~`:419-423`). A fix there would: hold an approved pay change whose
   `effective_date` is in the future (new state or a `scheduled` flag), write it
   from a daily job on the day, and log a dated `hr.contract.advantage.change`
   for the wage input. It also writes the new job on the CONTRACT only
   (`:424-431`, failure swallowed) — the employee keeps the old job — and
   **Undo restores the wage only, not the job** (`_restore`,
   `pb_pay_apply.py:312-334`). Simplest honest fix: send job moves through
   Change job (`pb_start_for_employee`) instead of `new_job_id`.
2. **A renewed contract does not carry the old contract's pay lines,
   `vietnam_contract_type` or `pb_payroll_contract_type`**
   (`pb_contract_lifecycle/models/contract_review.py` `_build_new_contract`
   ~`:606-697` + `CARRIED_FIELDS` `:59-64`). A fix: in `_build_new_contract`
   (or an override of it), after the new contract is created, copy every
   `hr.contract.advantage` line of the old contract (template + amount/text)
   onto the new one — each logged with `contract_component_change.log(...,
   'manual', effective_date=start)` — and copy the two type fields. **This
   changes pay** (allowances that read 0 today on the renewed contract would be
   paid), so it is an owner decision. Measured count: the local copy has no
   contracts, so the counts must be taken on a rize/payobook clone by the
   deploy agent with the SQL in §8.
3. Change job does NOT change `hr.version` dated versions (standing ruling: in
   place) and does not touch `/my/team` (manager-started proposals are a
   later item; `pb_start_for_employee` is the server method they can call).

## 6. Deploy notes

- New modules, `-i` on all five databases (`payobook`, `payobook_template`,
  `p0clone`, `rize`, `sudima`; never `abm`): **first check `pb_vendor_access`,
  `pb_orgchart`, `pb_contract_lifecycle`, `pb_records`, `pb_scheme_map` are
  installed on each** (hard dependencies would force-install them).
- Install order: `pb_contract_rules`, `pb_agency_staff`, `pb_job_change` (any
  order works; no dependency between them).
- Asset purge + restart (new JS/SCSS).
- **Touches pay → rehearsal**: Change job writes wages and pay lines only when
  a person sends and approves one; installing changes nothing. A short rize
  rehearsal: install on a clone, recompute one finished run old vs new (0
  differences expected, nothing was changed), then do one Change job on a DEMO
  person on the clone and check the next draft payslip reads the new wage.
- After install: route "Job changes" appears in the Approval Matrix for every
  company; People › Agency staff (empty); ⌘K "Change someone's job"; the two
  rule rows under "Fixed-term contract rules".
- No data migration.

## 7. Owner questions (plain words)

1. **Renewed contracts lose their allowances.** When a fixed-term contract is
   extended, the new contract starts without the old one's pay lines (meal,
   phone, etc.), so they read 0 on the next payslip unless HR types them again.
   Should an extension copy them across automatically? (Recommended: yes —
   it changes what those people are paid back to what they were paid.)
2. **Pay › Changes still writes a raise at once**, whatever start date it
   shows. Should Pay › Changes send people to the new "Change job" (one
   sign-off, honours the date), or should Pay › Changes itself learn to wait
   for the date?
3. **Vietnam and Indonesia rule rows** were filled from the law as we read it
   (Vietnam: 2 fixed-term contracts, 36 months each; Indonesia: 5 years in
   total). Can your adviser confirm them, and should other countries get a row?

## 8. Left for later

- Measured counts on live clones (facts §12.2): renewals whose new contract
  lost pay lines, open contracts whose job/team differs from the person's,
  contracts with a typed cost centre — SQL in
  `scratchpad/s8b/measure.sql` (copied here):
  `SELECT count(*) FILTER (WHERE coalesce(n.lines,0) < coalesce(o.lines,0)) FROM hr_contract c JOIN hr_contract p ON p.id = c.pb_renewed_from_id LEFT JOIN (SELECT contract_id, count(*) lines FROM hr_contract_advantage GROUP BY 1) n ON n.contract_id = c.id LEFT JOIN (SELECT contract_id, count(*) lines FROM hr_contract_advantage GROUP BY 1) o ON o.contract_id = p.id;`
  (local copy: 0 contracts, so all counts 0 — not meaningful).
- Pay › Changes "New change" deep-link into Change job (an edit of `pb_pay`).
- Manager-started job changes on `/my/team` (self-service team).
- Agency staff clock-in / timesheets / invoices (non-goals).
- The renewal pay-line carry (owner question 1).
- "Paid by" what-if covers team and company moves; a scheme map RULE written
  as an employee domain is still read with today's values.

## 9. Gotchas → ledger rows (for the orchestrator to add; the ledger file is
not edited here, so eight parallel branches do not collide on it)

| # | Gotcha |
|---|---|
| S8B-1 | `hr.contract.vietnam_contract_type` DEFAULTS to `indefinite` on every contract (`pb_hr_payroll_vietnam`), so it cannot be read as "permanent"; only its `probation` value means anything. A first draft that treated `indefinite` as permanent counted 0 fixed-term contracts everywhere. |
| S8B-2 | A route `manager` step blocks the whole request ("No manager is recorded…") when the person's manager has no login — rize's 40 managers. Give the step a condition on a `has_manager` fact instead of shipping it bare. |
| S8B-3 | `selection_add` on a RELATED selection (`pb.hr.letter.letter_type`, related to the template) is ignored with a warning; add values on the source field only. |
| S8B-4 | `_(variable)` with a selection label has no code translation entry (the label is a model term): read labels with `field._description_selection(env)`. Odoo 19 has no `--i18n-export` server flag: `odoo-bin i18n export -c <conf> -d <db> -o <file>.pot <module>`. |
| S8B-5 | A filter-kit / board search on `vendor_id.name` as an HR officer reads `pb.vendor`, which HR does not hold: resolve the ids under sudo first (`vendor_id in sudo-search ids`) and read names with `label_sudo`. |
| S8B-6 | Field `_module` of `create_uid`/`write_uid` is the NEW module: a "this record links to nothing in pay" test must skip the magic fields. |
| S8B-7 | Local runs: a port another builder's run holds makes the whole run exit at start ("Address already in use") with no test output — pick a port block per phase (S8-B used 8791–8795). |
