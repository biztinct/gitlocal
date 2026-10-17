# Approval Matrix — close-out

**The programme is live.** Phases 1–7 were deployed to every database on
`Payobook19v2` on 15 September 2026 as one wave. This file is what somebody
picking the programme up next needs: what is in force, what was found on the
way in, and what is still open.

Read `APPROVAL_MATRIX_LEDGER.md` first — AM1–AM150. The per-phase deploy docs
(`APPROVAL_MATRIX_P3..P7_DEPLOY.md`) are the payload; `P7_DEPLOY.md` §7 is the
whole-wave checklist that this run followed.

---

## 1. What is in force

One approval engine (`biz_approval_workflow`) under one Approval Matrix
(`pb_approval_config`), with an adapter per business object. Every sign-off in
the product goes through it.

| Database | Companies | Published routes | Seats filled |
|---|---|---|---|
| `payobook` (master) | 4 | 168 (42 each) | 40 |
| `payobook_template` | 1 | 40 | 9 |
| `abm` | 1 | 40 | 9 |
| `rize` | 1 | 41 | 9 |
| `p9clone` (scratch) | 3 | 126 | 30 |
| `rztest` (scratch) | 1 | 40 | 9 |

Nothing is left unpublished anywhere, and no catalogue row claims to be
watching something nobody is checking.

**Why the counts differ.** A tenant has no `pb_tenants`, so the platform row
(`tenant`) never gets a route — correct, and guarded for explicitly. `demo` is
seeded only where a demo module exists, which is why `rize` has 41 and the
other tenants 40.

**Ten responsibilities** are seeded per company from whoever held the group
that used to do the job: Approver, HR lead, Finance approver, Payroll manager,
Country director, Equipment team, Head of pay, HR lifecycle team, Finance
controller, Platform owner (master only). **Every one should be checked by a
person** — the first holder of a group is not necessarily who the business
means.

**60 modules** were deployed, all byte-identical to the repository and all at
their manifest version on every database.

---

## 2. What the wave found that testing could not

Six faults surfaced during the go-live that eight rounds of local suites had
not. Each is a ledger entry; the pattern behind them is worth keeping.

1. **The module list was short by ten** (AM145). The deploy document named 51
   modules; a repo-vs-live version diff found ten more that Phases 3–7 had
   changed — including the chain module the whole engine inherits from, and
   seven screens that filter pay runs by status. Left behind, those screens
   would have shown nothing, silently. **A wave's payload is the version diff,
   never a hand-written list.**
2. **One translation entry stopped an entire upgrade** (AM146). Odoo's PO
   reader crashes on an entry whose comment does not begin with its module
   name, and the error names no file. Eight files had 213 such entries. It
   passed every local suite because test databases have no second language
   installed, so the files are never read.
3. **A clean translation file still crashed** (AM146). The reader merges the
   module's `.pot` template into the `.po`; one bad entry in the template
   killed a translation file that had just been verified.
4. **1,100 translated strings were never reaching the screen** (AM147). A
   string also needs a marker saying whether it is Python or a screen string,
   and a source reference. Without them it is dropped in silence. The box was
   reporting "no translation" for 33 modules whose files are full of
   Vietnamese. 938 strings were recovered for the wave's modules.
5. **A module was installed before its sibling was upgraded** (AM148). The
   weekly timesheet module does not depend on pay runs, so it was built
   against a settings field that Phase 3 had removed. Fixed by ordering, in
   two stages, not by changing code.
6. **The pre-flight query was narrower than the migration's own guard**
   (AM149), and **the seed relay does not re-run without a version change**
   (AM150), which left one tenant without its demo-data route.

**The rehearsal is what caught all of them.** Every fault above was hit on a
scratch clone of the master, not on a real database.

---

## 3. How the wave was actually run

Kept here because P8 is the shape any future wave should take.

1. Back up every database first (`/odoo/backups/approval-wave/`, six dumps).
2. Diff repo vs live versions; deploy the difference.
3. Stage the modules, sync **per module** with `--delete` scoped to that
   module, never to the addons root.
4. Prove every module tree is byte-identical on both sides.
5. Parse every PO file on the box with Odoo's own reader. This gate is new,
   and it is the one that would have saved the two failed attempts.
6. Clear whatever the migration guards refuse — read the guard's constant.
7. **Rehearse on a clone of the master.** Do not skip this.
8. Then the real databases, one at a time, stopping at the first failure.
9. Asset purge and `web.assets.version` bump per database; restart.
10. Census every database: routes, unpublished, seats, catalogue honesty,
    module versions, content hashes.

---

## 4. Open items for the owner

1. **Name two platform owners, each with a backup.** The platform route needs
   two signatures. With one owner and no backup, every platform action blocks
   — fail-closed, by design. The master has `platform_owner` seeded from
   whoever holds system rights; confirm it names the right people.
2. **Seat a Finance approver in every company using the contract drawer.** A
   pay rise reaches that rung; an empty seat only shows up the first time
   somebody tries.
3. **A two-person company can stall on its own request.** Where the person a
   route names is the one who sent it in, the backup is seated automatically;
   with no backup the request warns rather than blocks, and an approvals admin
   can move it. Small companies should either name a third person or relax the
   repeated-person rule.
4. **Five new permission gates are not routes.** Statutory wizard, filing
   flow, both people wizards and the insurance adjustment now require a
   permission that was missing entirely. A fast lane does not undo them; if
   one needs lifting, give the person the group, never remove the check.
5. **"My team" in the inbox got wider.** Supervisors whose dock was empty will
   find it full — people who clock in on a badge have no login, and the queue
   now follows the seat as well as the person. That is the fix, but it is a
   visible change.
6. **The journal switch stays off** unless the company's accountant asks.
7. **~1,200 Vietnamese strings outside the wave's modules still do not load**
   (AM147). The fix is mechanical and proven; it was scoped to the wave's 40
   modules deliberately. The rest is a contained follow-up.
8. **On a tenant, the platform row reads "Not connected yet."** It is honest
   in the sense that nothing there can raise the request, but it reads as a
   gap to a customer. Worth hiding rows whose feature is not installed.
9. **Nothing is pushed.** The branch carries the whole programme plus this
   wave's fixes.

---

## 5. The screen walk

The four Phase-7 screens were walked on a local whole-chain copy before the
wave (recorded in `APPROVAL_MATRIX_P7_DEPLOY.md` §"Walk record"), and the
Phase-6 screens before that (`P6_DEPLOY.md` §7). On the live box, the login
page renders with freshly built assets, no style errors and no vendor name in
the text.

**The signed-in walk on the live box has not been done** — it needs a login
the deploying session does not hold. The first five minutes that matter, in
order: Home → Approvals opens; a pay run can be sent in; a bank file needs two
people; a laptop request draws its real route; a statutory rate asks before it
is written.
