# Approval Matrix · Phase 6 — deploy checklist

The live box `Payobook19v2` has been unreachable since Phase 1 (ledger AM13,
AM14), so P1–P6 are one deferred deploy wave. This file is P6's half of it,
written so the wave can be run without re-reading any code. Run the P3, P4 and
P5 deploy docs first; all three are still current.

Read `APPROVAL_MATRIX_LEDGER.md` first — §"Deploy contract" is the procedure;
this is only the payload.

## 1. Modules, in this order

| Module | Version | Action | Why it is in the wave |
|---|---|---|---|
| `biz_approval_workflow` | 19.0.1.4.0 | `-u` | **the shim.** Every `biz.approval.chain.mixin` consumer can now run on the engine; a new `_approval_advance` hook; `fill_role_from_group`; "who this is about" as a real link + one data migration |
| `pb_approval_config` | 19.0.1.4.0 | `-u` | four new catalogue rows, three new responsibilities, the division scope resolver, the inbox's three scopes and the dock's queue; the `end-` relay |
| `pb_assets` | 19.0.1.1.0 | `-u` | asset requests on the engine + route + seat rule + migration |
| `pb_attendance_flow` | 19.0.1.1.0 | `-u` | attendance fixes; **the fix is applied at the END of the route** |
| `pb_bank_ocr` | 19.0.1.2.0 | `-u` | bank account changes; its own catalogue row at last |
| `pb_business_trip` | 19.0.1.2.0 | `-u` | trips, with the cash advance as the request's amount |
| `pb_comp_ben` | 19.0.1.3.0 | `-u` | awards |
| `pb_contract_lifecycle` | 19.0.1.1.0 | `-u` | contract extensions; its own catalogue row |
| `pb_me_portal` | 19.0.1.2.0 | `-u` | employee record changes |
| `pb_offboarding` | 19.0.1.1.0 | `-u` | resignations |
| `pb_pay` | 19.0.3.4.0 | `-u` | pay changes **and** pay reviews (a new catalogue row) |
| `pb_rnr` | 19.0.1.1.0 | `-u` | recognition (a new catalogue row) |
| `pb_timeoff` | 19.0.1.3.0 | `-u` | **time off.** Every leave now travels a route |
| `pb_hr_workforce` | 19.0.4.16.0 | `-u` | **overtime**, and the "nothing to think about here" verdict moved here |
| `pb_mission` | 19.0.1.9.0 | `-u` | the Approvals lens is the one inbox; the dock reads it; `pb_team` is no longer a dependency |
| `pb_team` | 19.0.2.0.0 | `-u` | **retired to a redirect.** The model is gone; the saved link still opens |
| `biz_access` | 19.0.1.3.0 | `-u` | role grants can be asked for |
| `pb_tenancy` | 19.0.1.5.0 | `-u` | support access is the customer's decision |
| `pb_close` | unchanged code | — | only its clean-batch TEST changed |
| `pb_payruns` | 19.0.2.0.0 (unchanged) | files + restart | one Python change only: its responsibility seeder no longer re-seats a seat the business has ended (ledger AM101). No data, no views — the `-u` cascade above already covers it |

**One `-u` does most of it.** Every module above depends, directly or through
the chain, on `biz_approval_workflow`, so `-u biz_approval_workflow` cascades.
`pb_team` does not (it no longer depends on the engine at all), so the command
is:

```
-u biz_approval_workflow,pb_team
```

## 2. Before you start

**Thirteen new default workflows are published per company**, and from the
moment they exist they are IN FORCE. Every one is the ladder that was already
in the code, so day one behaves like day zero — but the people it names have to
exist:

| Process | The route that ships | What it means |
|---|---|---|
| Asset requests | Their manager → Equipment team | unchanged from the old two rungs |
| Attendance corrections | Their manager, **only when the fix is worth 15 minutes or more** | smaller fixes are applied at once and recorded |
| Bank account change | HR lead → Finance approver | unchanged, but its own row at last |
| Business trips | Their manager → Finance approver → HR lead | unchanged |
| Awards | Head of pay | unchanged |
| Contract extensions | Their manager → HR lifecycle team | unchanged |
| Employee record changes | HR lead | unchanged |
| Resignations | Their manager → HR lifecycle team | unchanged |
| Pay changes | HR lead → Finance approver *(only above guidance)* → Country director | today's ladder exactly, including the condition that used to be a setting read in Python |
| Pay reviews | same | as above |
| Recognition | Their manager → HR lead | unchanged |
| Time off | Their manager *(when the leave type asks for one)* → HR lead *(when it asks for an officer)* | **exactly what each leave type already said.** A type set to "None needed" never reaches a route |
| Overtime | Their manager | unchanged |
| Role changes | Approver | NEW: asking already needs the right to manage access, so this is a second pair of eyes |
| Support access | Approver | NEW: nobody from support gets in until somebody here says so |

**Six catalogue rows are new or repointed.** `payreview` (`pb.pay.review`),
`bankchange` (`pb.bank.change.request`), `recognition` (`pb.rnr.nomination`)
and `extension` (`pb.contract.extension`) are new rows; `master` is repointed
from `hr.employee` to `pb.profile.change.request` and `assets`, `correction`,
`trip`, `awards`, `resign`, `roles` and `support` gain the model that can
actually hold a request. The data file is `noupdate`, so each adapter's own
seed does this and it needs nothing from you. The `resign` row is renamed from
"Resignations and contract extensions" to "Resignations" — only if it is still
the name that shipped.

**Three responsibilities are new**: Equipment team, Head of pay, HR lifecycle
team. Each is seeded with whoever holds the group the old ladder checked — the
first of them as the holder, the second as the backup — so no route starts out
blocked. **Check them**: the person a group happens to list first is not
necessarily the person the business means.

**Nothing is destructive.** No state machine is replaced, no table is dropped,
no column is removed. `pb.team`'s model is removed but its module, its action
and its rail row stay, so a saved link still opens.

## 3. Migrations and seeds that run by themselves

| Script | What it does |
|---|---|
| `biz_approval_workflow .../19.0.1.4.0/post-subject_links.py` | fills "who this is about" as a real link on every request that already exists (it was a Json list, which cannot be searched) |
| one `post-` per adapter module (13 of them) | that module's default route, per company |
| `pb_approval_config .../19.0.1.4.0/end-p6_adapters.py` | **an `end-` script, and that is the point** (ledger AM75): it relays the seed to every adapter in the registry after the whole graph is loaded, and mends the `resign` row's name |
| each module's `post_init_hook` | the same seeds, on a FRESH install, where no migration runs at all |
| `res.company.create` (`pb_approval_config`) | a company made later gets all of them |

Every one is idempotent; running all of them in a row creates exactly one of
everything.

## 4. After the upgrade, per database

1. **Assets ritual — YES.** `pb_approval_config`, `pb_mission` and `pb_team`
   all ship JS/SCSS, and one component moved between modules.
   `DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%';` then bump the
   `web.assets.version` `ir.config_parameter`, then restart.

2. **Check the new table and the new columns exist:**
   ```sql
   SELECT to_regclass('pb_access_request'),
          to_regclass('biz_approval_request_subject_rel'),
          to_regclass('pb_asset_request_res_users_rel');
   ```
   All three must be non-null. The third is the "asked to decide" link the
   asset request grew; every chain consumer has one of its own, named after
   its own table.

3. **Check the routes landed, per company:**
   ```sql
   SELECT c.name, p.key, w.name, v.status
   FROM biz_approval_binding b
   JOIN res_company c ON c.id = b.company_id
   JOIN biz_approval_process p ON p.id = b.process_id
   JOIN biz_approval_workflow w ON w.id = b.workflow_id
   LEFT JOIN biz_approval_workflow_version v ON v.id = w.published_version_id
   WHERE p.key IN ('assets','correction','bankchange','trip','awards',
                   'extension','master','resign','paychange','payreview',
                   'recognition','leave','overtime','roles','support')
     AND b.active AND b.scope_key = ''
   ORDER BY c.name, p.key;
   ```
   Fifteen rows per company, every one `published`.

4. **Check the catalogue tells the truth:**
   ```sql
   SELECT key, model_name FROM biz_approval_process
   WHERE key IN ('assets','correction','bankchange','trip','awards',
                 'extension','master','resign','paychange','payreview',
                 'recognition','leave','overtime','roles','support')
   ORDER BY key;
   ```
   No `model_name` may be null.

5. **Fill the seats.** Five responsibilities now carry a route that runs every
   day: **HR lead**, **Finance approver**, **Country director**, **Equipment
   team**, **Head of pay**, **HR lifecycle team** and the engine's own
   **Approver**. HR lead is per part of the business
   (`fallback_to_company = False`) — but every route this phase ships asks for
   it at COMPANY scope on purpose (ledger AM80), so a company-wide holder
   covers all of them until somebody narrows a route deliberately.

6. **The people a route names must be able to do the thing.** The last
   approver carries it out AS THEMSELVES (safety rail 5, ledger AM54):
   * time off — needs the **Time off officer** role, or the request lands
     approved with "…is not allowed to record time off" on it;
   * overtime — needs the attendance officer/manager role or line management;
   * role changes — needs **Access team**;
   * everything else — the group its own ladder always checked.

7. **Tell the managers about the Workforce Approvals lens.** It is the same
   screen it was, with every other kind of request in it, and it now has a
   "Mine / My team / Everyone" switch at the top. The old **Team Approvals**
   link still works and lands there.

8. **Every database**, not just one: `payobook`, `payobook_template`, and every
   tenant (`psql -l`; today at least `abm`, `acme`, `rize`). Tenants get
   everything the master gets except `pb_tenants`, `pb_demo`, `pb_demo_portal`,
   `pb_website`. `pg_dump -Fc` each tenant first.

## 5. First checks on the screen

1. **Workforce → Approvals.** The lens is the Approvals inbox, scoped to "My
   team", with the scope switch above the tabs and the line that says watching
   is not deciding. The dock down the side lists every kind of request, not
   four.
2. **Ask for a laptop** (Assets → a new request → Send). The form's stepper
   shows the real route with the real names — "Their manager · <name>", then
   "Equipment team · <name>" — instead of the four fixed rungs.
3. **Approve it as the manager.** The record moves to "Manager approved"; the
   request is still open; the equipment desk's step is now the live one.
4. **Cancel a request that is half way through.** The open request is
   withdrawn with "Withdrawn from the record itself: Cancelled" and leaves
   nobody's inbox holding it.
5. **Book a day off** on a leave type approved by the manager. It appears in
   the manager's inbox beside everything else; approving it there validates
   the leave.
6. **Access → give somebody a role.** The toast reads "Sent for approval —
   <name>" with a *See the request* door, and nothing is written until it is
   approved.
7. **Old link check**: open `/odoo/action-pb_team`. It says "Taking you to
   Approvals…" and lands on the Workforce Approvals lens.

## 6. Rollback

Everything in P6 is additive — new tables, new columns, new rows — with one
data migration that only fills in a link from a list that was already there.
`pb.team`'s MODEL is removed, which is the one irreversible piece: restoring it
means restoring the module's previous version from git, not from the database.
To roll back a database, restore the per-database `pg_dump` taken in §4.8.

To stop a route being in force WITHOUT rolling back, set that process to
**"No approval needed"** in the Matrix. Every door then behaves exactly as it
did before the phase — a press writes at once — and every use is still
recorded as a request. That is a published choice, not a bypass, and it is the
answer to "we are not ready for this yet" for all fifteen.

## 7. Walk record (15 Sep, local `am_walk6` = `am_tpl` + `-u all`, Fable)

All seven checks of §5 pass. People: Thao Staff (asset user) reports to Minh Manager; Unpaid leave set to manager-approved for the walk.

| # | Check | Result |
|---|---|---|
| 1 | Workforce → Approvals | The one inbox scoped to "My team", the "Watching, not deciding" line, all kinds in the dock |
| 2 | Ask for a laptop → Send | Stepper: "Sent in · Thao Staff", "Their manager · Minh Manager", "Equipment team · Administrator" |
| 3 | Manager approves from the inbox | Record "Manager approved"; request `pending`; step `mgr` done, `equipment` active |
| 4 | Cancel half way | "Withdrawn from the record itself: Cancelled"; request `cancelled`, equipment step skipped, seats closed |
| 5 | Book a day off (manager-approved type) | In the manager's inbox beside the laptop; HR-lead step skipped; approve → leave `validate`, request `applied` |
| 6 | Access → give Minh a role | Toast "Sent for approval — Administrator · See the request"; nothing written; `pb.access.request` pending. A role with no permission is refused with its own sentence |
| 7 | `/odoo/action-pb_team` | Lands on the Workforce Approvals lens |

Fixed during the walk: the dock printed a raw UTC stamp (commit "the approvals dock shows the time the way the inbox does", AM103). Left for P7 polish: the record stepper's own stamp (old chain widget) and the record's "Sent in" line use the raw UTC form; the dock's team/organisation split files a request waiting on *you* under "Other requests" when the person it is about does not report to you.

Suites after the close-out fixes (all `EXTRA=biz_approval_workflow` unless noted): engine 48, config 78, assets 10, timeoff 13, workforce 42, biz_access 124, tenancy 106, mission 54 (`EXTRA=pb_approval_config,pb_team`), pay runs 60 — all green.
