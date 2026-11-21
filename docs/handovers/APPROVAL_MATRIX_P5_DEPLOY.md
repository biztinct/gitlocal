# Approval Matrix · Phase 5 — deploy checklist

The live box `Payobook19v2` has been unreachable since Phase 1 (ledger AM13,
AM14), so P1–P5 are one deferred deploy wave. This file is P5's half of it,
written so the wave can be run without re-reading any code. Run
`APPROVAL_MATRIX_P3_DEPLOY.md` and `APPROVAL_MATRIX_P4_DEPLOY.md` first; both
are still current.

Read `APPROVAL_MATRIX_LEDGER.md` first — §"Deploy contract" is the procedure;
this is only the payload.

## 1. Modules, in this order

| Module | Version | Action | Why it is in the wave |
|---|---|---|---|
| `biz_approval_workflow` | 19.0.1.3.0 | `-u` | one model → two processes, the shared seeder, `_approval_reject`, a "tell someone" step that really tells |
| `pb_approval_config` | 19.0.1.3.0 | `-u` | the `end-` relay that lays every adapter's route; the drawer keeps a chips-only detail |
| `pb_hr_payroll_formula` | 19.0.1.130.0 | `-u` | **pay data.** `action_process` asks; the two catalogue rows; one migration |
| `pb_pay_delivery` | 19.0.1.3.0 | `-u` | **money out.** Bank file, release, journal, send-out; the cockpit; one migration |
| `pb_records` | 19.0.1.3.0 | `-u` | **the desk proposes.** One migration that also repairs the history |
| `pb_zoho_bridge` | 19.0.1.1.0 | `-u` | **arrivals wait.** One migration |
| `pb_comp_ben` | 19.0.1.2.0 | `-u` | awards are marked paid by the release, not by the run |
| `pb_hr_fullandfinal` | 19.0.1.1.0 | `-u` | settlements are built only from a file that was really processed |
| `pb_import_batch` | 19.0.2.2.0 | `-u` | the Commit button says what the press costs |
| `pb_import_wizard` | 19.0.1.3.0 | `-u` | "Sent for approval" instead of "Import complete · 0 rows" |
| `pb_payrun_wizard` | 19.0.1.23.0 | `-u` | the wizard says the pay data is waiting |
| `pb_audit` / `pb_compliance_hub` | unchanged code | `-u` only if convenient | two manifest descriptions that made every load log `(ERROR/3) Unexpected indentation` |

**One `-u` does it all.** Every module above depends (directly or through the
chain) on `biz_approval_workflow`, so `-u biz_approval_workflow` cascades to
the whole set. That is how the walk database was built and it is the
recommended command — see §3 for why the order matters less than it looks.

## 2. Before you start

**Eight new default workflows are published per company**, and from the moment
they exist they are IN FORCE:

| Process | The route that ships | In force means |
|---|---|---|
| Bank file creation | Payroll manager → Finance approver | the file that pays a company cannot be produced by one person any more |
| Payment release | Finance approver → Country director | two real signatures before money is called sent |
| Payroll journal | **No approval needed** | nothing changes; the whole lane is behind a company switch that is OFF |
| Payslip send-out | **No approval needed**, HR lead told | the usual press still sends |
| Records Desk bulk changes | HR lead → Finance approver **when bank details change** | the desk proposes instead of writing |
| "This run only" pay data | Payroll manager | a one-press commit becomes a request |
| Past pay data loads | Payroll check → HR lead | same |
| Arrivals from a connected system | HR lead | the webhook stops writing by itself |

If a company is not ready for one of them, the answer is a published choice —
set that process to **"No approval needed"** in the Matrix — never a code
change. Doing so still records every use as a request.

**Eight catalogue rows are repointed** at the records that can actually hold a
request (`bankfile` → `pb.bank.file`, `release` → `pb.payment.release`,
`journal` → `pb.payroll.journal`, `payslips` → `pb.payslip.delivery.batch`,
`records` → `pb.records.apply`, `runonly` and `loads` → both to
`hr.payroll.import.batch`, `arrivals` → `pb.zoho.arrival.batch`). The data file
is `noupdate`, so each adapter's own seed does this and it needs nothing from
you.

**Nothing is destructive.** No state machine is replaced, no table is dropped,
no column is removed. The one data migration REPAIRS rather than changes: see
§3.

## 3. Migrations and seeds that run by themselves

| Script | What it does |
|---|---|
| `pb_pay_delivery .../19.0.1.3.0/post-money_out.py` | the four money-out routes per company |
| `pb_records .../19.0.1.3.0/post-records_approval.py` | marks **every existing `pb.records.apply` row as carried out** (they were — the new `applied`/`state` columns default to "being prepared", so without this the History tab would claim last March's changes are about to happen), then the desk route |
| `pb_hr_payroll_formula .../19.0.1.130.0/post-import_approval.py` | the two pay-data routes |
| `pb_zoho_bridge .../19.0.1.1.0/post-arrivals.py` | the arrivals route |
| `pb_approval_config .../19.0.1.3.0/end-p5_adapters.py` | **an `end-` script, and that is the point.** It relays the seed to every adapter in the registry. A `post-` script runs while `pb_approval_config` is loading, and every adapter module depends on it — so at that moment half of them are not in the registry and the loop silently finds nothing. `end-` scripts run after the whole graph is loaded (`loading.py` STEP 3.5), which is the first moment the question has its real answer |
| each module's `post_init_hook` | the same seeds, on a fresh install |
| `res.company.create` (every module) | a company made later gets all eight |

Every one is idempotent; running all of them in a row creates exactly one of
everything. That is proven by `pb_approval_config`'s own `test_u12`.

## 4. After the upgrade, per database

1. **Assets ritual — YES.** Five of the modules ship JS/SCSS.
   `DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%';` then bump the
   `web.assets.version` `ir.config_parameter`, then restart.

2. **Check the new tables exist.** A model whose module was not updated leaves
   its table missing and logs `Model … has no table` at registry load — the
   symptom, not the disease (ledger AM64):
   ```sql
   SELECT to_regclass('pb_bank_file'), to_regclass('pb_payment_release'),
          to_regclass('pb_payroll_journal'), to_regclass('pb_zoho_arrival_batch');
   ```
   All four must be non-null.

3. **Check the eight routes landed, per company:**
   ```sql
   SELECT c.name, p.key, w.name, v.status
   FROM biz_approval_binding b
   JOIN res_company c ON c.id = b.company_id
   JOIN biz_approval_process p ON p.id = b.process_id
   JOIN biz_approval_workflow w ON w.id = b.workflow_id
   LEFT JOIN biz_approval_workflow_version v ON v.id = w.published_version_id
   WHERE p.key IN ('bankfile','release','journal','payslips',
                   'records','runonly','loads','arrivals')
     AND b.active AND b.scope_key = ''
   ORDER BY c.name, p.key;
   ```
   Eight rows per company, every one `published`.

4. **Check the catalogue tells the truth:**
   ```sql
   SELECT key, model_name FROM biz_approval_process
   WHERE key IN ('bankfile','release','journal','payslips',
                 'records','runonly','loads','arrivals') ORDER BY key;
   ```
   No `model_name` may be null. (`connected` is computed, not stored — open the
   Matrix and every one of the eight must read as protected rather than
   "Not connected yet".)

5. **Fill the seats — this is where a route sticks.** Four responsibilities now
   carry money:
   * **Payroll manager** and **Finance approver** — the bank file needs both.
   * **Country director** — the second signature on a release. A company that
     leaves this empty cannot release a payment at all.
   * **HR lead is per part of the business** (`fallback_to_company = False`).
     A company-wide holder does NOT cover a division, so every division whose
     people appear in a Records Desk change needs its own HR lead. A change
     that spans two divisions goes to the company route instead, by design.

6. **Every person who carries out a money action needs the Pay & Deliver role**
   (safety rail 5). The final approver of a bank file, a release, a journal or
   a send-out performs it AS THEMSELVES, and is refused by name if they hold
   neither the Payroll Manager nor a Finance group. A country director who
   holds no payroll role will approve a release and then be refused when it
   applies, leaving the request `approved` with a block reason. Either give
   that person the role or make the last step somebody who has it. Same shape
   as ledger AM54.

7. **Decide the one company switch** (Settings → the company form):
   *Post a payroll journal entry when a pay run is finished* — **OFF by
   default, and it must stay off unless the company's accountant asks for it.**
   Confirming payslips has never written to the books on this build, and the
   salary-rule → account mapping is not maintained for the formula workflow.
   Turning it on makes every finished run produce one balanced entry that
   follows the payroll-journal route.

8. **Every database**, not just one: `payobook`, `payobook_template`, and every
   tenant (`psql -l`; today at least `abm`, `acme`, `rize`). Tenants get
   everything the master gets except `pb_tenants`, `pb_demo`, `pb_demo_portal`,
   `pb_website`. `pg_dump -Fc` each tenant first.

## 5. First checks on the screen

Walked on `am_walk5` on 13 Sep; each of these is what was actually seen.

1. **Pay & Deliver → pick a run.** A run that has been paid wears a **Paid**
   chip on its picker card and in the hero. A run that is not approved yet
   shows an amber strip at the top saying so, and the Prepare button is dead.
2. **Prepare bank file for approval.** The card grows a status line —
   *Waiting for approval · Olive Officer · See the request* — over two step
   pips naming Payroll check and Finance approval, and the stored file tile
   underneath (`bidv_2026-06-01-2026-06-30.csv · 3 payments · 317 B ·
   29,600,000`). The button becomes *Prepare it again and send it in*.
3. **Try to download it now.** Refused: *"There is no approved bank file for
   this pay run yet. The one that was prepared is with Olive Officer."*
4. **Approvals → My turn**, as each of the two. The card reads
   `3 payments`, the facts carry real units (`29,600,000 USD`, not "decimal"),
   and the drawer's small table lists who was left out — or says everybody is
   in the file, with the bank and the filename as chips.
5. **Back on the cockpit.** Green *Download approved file*. Press it: the file
   downloads and the record remembers who took it.
6. **Prepare it again with a different bank.** The old file turns
   *Replaced by a newer file*, its open request is withdrawn, and downloading
   the old one says *"A newer bank file has replaced this one. Download that
   one instead."*
7. **Payment release.** Until the file is approved the card says *Waiting for
   the bank file*. After it, type a bank reference and send: two steps appear,
   *First signature · Finance* and *Second signature · Country director*,
   named. Approve as both — they must be two different people — and the run
   turns **Paid**, every payslip carries the date and the reference, and the
   awards queued into that run are marked paid.
8. **Records Desk → change a bank account → Apply.** Nothing is written. The
   toast reads *Sent for approval — Hana HR* with a *See the request* door, and
   History lists the change as waiting with the person holding it. The route
   shows **two** steps because the change touches bank details; a change that
   does not shows one. Approve as both and the account is written, with the
   per-value trail exactly as before.
9. **A pay-data file → Commit.** The button reads **Send for approval** where a
   route applies. The batch stays `validated`, nothing is processed, and the
   cockpit names who is holding it.
10. **Guided setup / the pay-run wizard** with a file attached: the wizard now
    says the pay data is with somebody for approval and that the payslips are
    made once it is approved — instead of walking the person to a summary that
    says nothing was created.

## 6. Rollback

Everything in P5 is additive — new tables, new columns, new rows — with one
data repair (§3, `pb.records.apply`) that only writes rows that were already
true. There is no destructive migration. To roll back, restore the
per-database `pg_dump` taken in §4.8.

To stop a route being in force WITHOUT rolling back, set that process to
**"No approval needed"** in the Matrix. The doors then behave exactly as they
did before the phase — a press writes at once — and every use is still
recorded as a request. That is a published choice, not a bypass, and it is the
answer to "we are not ready for this yet" for all eight processes.
