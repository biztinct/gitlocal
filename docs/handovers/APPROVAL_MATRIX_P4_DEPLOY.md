# Approval Matrix · Phase 4 — deploy checklist

The live box `Payobook19v2` has been unreachable since Phase 1 (ledger AM13,
AM14), so P1–P4 are one deferred deploy wave. This file is P4's half of it,
written so the wave can be run without re-reading any code. P3's half is
`APPROVAL_MATRIX_P3_DEPLOY.md` and is still current; run it first.

Read `APPROVAL_MATRIX_LEDGER.md` first — §"Deploy contract" is the procedure;
this is only the payload.

## 1. Modules, in this order

| Module | Version | Action | Why it is in the wave |
|---|---|---|---|
| `biz_approval_workflow` | 19.0.1.2.0 | `-u` | two new adapter hooks (`_approval_card_count`, `_approval_detail`) |
| `pb_approval_config` | 19.0.1.2.0 | `-u` | the inbox asks the adapter for its own count and its own small table |
| `pb_hr_payroll_formula` | 19.0.1.129.0 | `-u` | **half the phase.** `pb.scheme.proposal`, the five doors, the content hash, the payslip stamps, the release `state`; one migration |
| `pb_formula_studio` | 19.0.1.190.0 | `-u` | merge / release / roll-back go through a proposal; the propose facades and the buttons |
| `pb_source_atlas` | 19.0.1.13.0 | `-u` | the words for the new provenance source |
| `pb_blueprint` | 19.0.1.9.2 | `-u` | the shared content hash, and the Connect step's real scheme-change panel |
| `pb_timesheet_approval` | 19.0.1.0.0 | **`-i`** | **the other half.** The weekly packet, the freeze, the payroll rung, the grid panel |

`pb_close`, `pb_attendance_flow` and `pb_workforce_payroll_bridge` are new
dependencies of `pb_timesheet_approval`. All three are already installed on
every live database; if a tenant somehow lacks one the `-i` pulls it in.

## 2. Before you start

Nothing aborts this upgrade — there is no destructive step and no state
machine is being replaced. Two things are worth knowing in advance:

1. **Two new default workflows are published per company** — "Weekly
   timesheet" (Their manager → HR lead) and "Scheme change" (Scheme owner →
   Payroll manager → Country director). From the moment they exist they are IN
   FORCE: a week cannot be paid from until it is approved where the company
   turned that on, and a live pay scheme's formulas cannot be edited in place.
   That is the phase. If a company is not ready for one of them, the answer is
   a published choice — set that process to "No approval needed" in the
   Matrix — not a code change.
2. **Two catalogue rows are repointed** at the records that can actually hold a
   request (`biz.approval.process.model_name`): `timesheet` →
   `pb.timesheet.packet`, `scheme` → `pb.scheme.proposal`. The data file is
   `noupdate`, so this is done by each adapter's own seed and needs nothing
   from you.

## 3. Migrations and seeds that run by themselves

| Script | What it does |
|---|---|
| `pb_hr_payroll_formula .../19.0.1.129.0/post-scheme_approvals.py` | writes `state = 'approved'` onto every existing `hr.formula.release` (they WERE signed off, by whoever sealed them, under the rules of the day), then seeds the scheme-change route for every company |
| `pb_hr_payroll_formula` `post_init_hook` | the same seed, on a fresh install |
| `pb_timesheet_approval` `post_init_hook` | the weekly-timesheet route for every company |
| `res.company.create` (both modules) | a company made later gets both routes |

Every one is idempotent; running all of them in a row creates exactly one of
everything.

## 4. After the upgrade, per database

1. **Assets ritual — YES.** Five of the seven modules ship assets.
   `DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%';` then bump the
   `web.assets.version` `ir.config_parameter`, then restart.
2. **Check the two tables exist.** A model whose module was not updated leaves
   its table missing and logs `Missing not-null constraint on
   pb.scheme.proposal.<field>` at registry load — the symptom, not the disease
   (ledger AM57):
   ```sql
   SELECT to_regclass('pb_scheme_proposal'), to_regclass('pb_timesheet_packet');
   ```
   Both must be non-null.
3. **Check the seeds landed:**
   ```sql
   SELECT c.name, p.key, w.name, v.status
   FROM biz_approval_binding b
   JOIN res_company c ON c.id = b.company_id
   JOIN biz_approval_process p ON p.id = b.process_id
   JOIN biz_approval_workflow w ON w.id = b.workflow_id
   LEFT JOIN biz_approval_workflow_version v ON v.id = w.published_version_id
   WHERE p.key IN ('timesheet','scheme') AND b.active AND b.scope_key = ''
   ORDER BY c.name, p.key;
   ```
   Two rows per company, both `published`.
4. **Check the seats are filled — this is where a route sticks.**
   * **HR lead is per part of the business** (`fallback_to_company = False`).
     A company-wide holder does NOT cover a division, so every division that
     records hours needs its own HR lead or the first week blocks. Seen on the
     local walk: the request said *"Nobody holds "HR lead" for Walk Line 1
     yet"*, and naming one plus pressing **Try again** on the stuck request
     mended it without anybody resubmitting.
   * **The last step of the scheme-change route carries the change out, as
     themselves** (safety rail 7, ledger AM54). A country director who holds no
     Formula Engine role will approve a proposal and then be refused when it
     applies, leaving the request `approved` with a block reason. Either give
     that person write access to pay schemes, or make the last step somebody
     who has it.
5. **Decide the two company switches** (Settings → Weekly timesheets):
   * *Payroll reads approved timesheets* — **on by default**. Hours, worked
     days and overtime then come from approved weeks. Turn it OFF for any
     company that is mid-period on this upgrade and has weeks nobody has
     approved yet, or their next run resolves those codes from nothing.
   * *Block the run until every week is approved* — **off by default**. An
     unapproved week is a note on the pay run, not a refusal.
6. **Every database**, not just one: `payobook`, `payobook_template`, and every
   tenant (`psql -l`; today at least `abm`, `acme`, `rize`). Tenants get
   everything the master gets except `pb_tenants`, `pb_demo`, `pb_demo_portal`,
   `pb_website`. `pg_dump -Fc` each tenant first.

## 5. First checks on the screen

1. **Workforce → weekly grid.** The right-hand rail carries a "This week's
   approvals" panel, one line per person, and the tray a "Send N week(s) for
   approval" button. Press it.
2. **Approvals → My turn** (as the person's manager). The card reads
   `44.5 h incl. 4.5 h overtime`, `A week of hours`, and names who it is with.
   Open it: the facts carry real units, and a seven-row **Day by day** table
   sits under them with the overtime chips.
3. **Approve as the manager, then as the HR lead.** The grid row turns
   *Approved*, and the week's own overtime is approved with it (the packet's
   note says how many entries).
4. **Try to change a day in that week.** Every path — the grid, the attendance
   form, an overtime entry — refuses with *"…the week of 07 Sep for <name> has
   been approved. Ask for it to be sent back if it has to change."*
5. **A scheme's settings → lifecycle buttons.** Where a scheme-change route is
   published they read **Propose for approval** (and *Propose merge into …* on
   a branch), with one quiet line under them saying where the change goes.
6. **Edit a formula on a LIVE scheme.** Refused: *"… is live, so what it pays
   cannot be changed here. Create a branch, make the change there, then propose
   it."* Branch it, change it there, press **Propose merge** — the proposal
   appears in Approvals; approve it and the parent takes the change and a
   release is sealed.
7. **New configuration → Connect → Approvals.** Two panels now: the pay-run
   route and the scheme-change route, agreeing with the Matrix.

## 6. Rollback

Everything in P4 is additive — new tables, new columns, new rows. There is no
destructive migration. To roll back, restore the per-database `pg_dump` taken
in §4.6. To stop a route being in force WITHOUT rolling back, set that process
to "No approval needed" in the Matrix: the doors then behave exactly as they
did before the phase, and every use is still recorded as a proposal.
