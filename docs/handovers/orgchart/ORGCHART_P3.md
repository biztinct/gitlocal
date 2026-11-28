# ORGCHART P3 — planning mode, time machine, suggest a chart

Read `ORGCHART_LEDGER.md` first (§0, §1, §2, and §3 up to the gotchas P2
appended), then `ORGCHART_P1_REPORT.md` §9 and `ORGCHART_P2_REPORT.md`
(especially how the write helpers are factored and what P2 says P3 needs).
The POC (`docs/design/org-chart-poc.html`) is the spec for planning mode
(the "Plan changes" button, draft bar, changes panel, publish dialog, amber
outlines and red ghost lines), the time machine slider and the "Suggest a
chart" dialog.

## 1. Scope

In `pb_orgchart` (bump to `19.0.1.2.0`):

### 1.1 Planning mode — ledger D7
1. **Models** `models/pb_orgchart_plan.py` (+ access CSV, + `register_chain`):
   * `pb.orgchart.plan` — `name` (Char, "Q1 restructure of the Southern
     field team"), `company_id`, `state` Selection draft / pending /
     approved / refused / applied / discarded, `effective_date` (Date,
     required, default today), `note` (Text, "Message to the approver"),
     `change_ids`, `applied_at`, `applied_by`, `apply_error` (Text).
     `_inherit = ['mail.thread', 'mail.activity.mixin', 'biz.approval.chain.mixin']`,
     `_approval_transitions` `{('draft','pending'): None, ('pending','approved'):
     None, ('pending','refused'): None, ('draft','discarded'): None}`,
     `_approval_dead_states = ('refused', 'discarded')`. Chain:
     `register_chain('pb.orgchart.plan', 'orgplan', submit_state='pending',
     driven=('approved',), date_field='effective_date')`; hooks cloned from
     `pb_contract_lifecycle/models/contract_extension_approval.py`
     (`_chain_title` = "Org chart change: <name> (<n> changes)",
     `_chain_facts` = `changes` int, `people` int, `new_roles` int,
     `crosses_teams` bool; `_approval_detail` rows = one per change with its
     plain label; `_approval_seed_default` route = `role_step(_('HR team'),
     'people')` with `Seed.fill_role_from_group(company, 'people',
     'hr.group_hr_manager')`; `seed_all` called from a post-init hook like the
     precedent's module does — find how `pb_contract_lifecycle` calls
     `seed_all` and mirror it).
   * `pb.orgchart.plan.change` — `plan_id` (cascade), `sequence`, `kind`
     Selection move / dotted / unassign / swap / new_role / fill_role /
     close_role, `employee_id`, `from_manager_id`, `to_manager_id`,
     `job_id`, `title` (Char, new role), `reason` (the hr.job reason
     selection), `label` (Char, stored, computed in plain English with `_()`
     exactly as P2's toast labels), `applied` (Boolean), `error` (Char).
   * Access: plan + change readable by `EMPLOYEE_GATE` holders, writable by
     `hr.group_hr_user` + system; approvers act through the engine.
2. **Apply**: `plan._apply()` runs each change in sequence through the SAME
   internal helpers P2's RPCs use — `_set_managers` for every `parent_id`
   write (ledger §0.12, G16: coach and the two approvers keep their value),
   `_loop_in(changes)` for the loop judgement, `_snap`/`restore` for the
   per-change undo snapshot (P2 report §8). If a kind has no helper split
   out yet, split it now, keeping the RPC behaviour identical and P2's tests
   green. Each change sets `applied` or
   `error` (a sentence); the plan goes `applied` when all are applied, else
   stays `approved` with `apply_error` listing the failures and a chatter
   message; the cron retries daily. Triggers: on reaching `approved` with
   `effective_date <= today` apply at once; otherwise a daily `ir.cron`
   "Apply approved org chart changes" (data XML; find a cron precedent with
   `grep -rl "ir.cron" pb_*/data | head`). A change whose `from_manager_id`
   no longer matches reality still applies (the destination is the intent)
   and notes it in `error`-free chatter text "<name> had moved to <x> in the
   meantime".
3. **Projection**: `_project(plan)` → `{emp_id: manager_id}` after applying
   the plan's changes virtually over the live tree (plus virtual open roles
   and dotted lines). Used by validation (loops are judged against the
   projection, not the live tree) and by the chart.
4. **RPCs** (all rights-checked like P2; every error a sentence):
   * `plan_open()` → the caller's open draft for the current company (one per
     user per company; create if none) → `{plan_id, name, effective_date,
     note, changes: [...]}`.
   * `plan_add_change(plan_id, change)` → validates against the projection
     (loop, self, cross-company, archived, "already there"), appends, returns
     the full plan payload.
   * `plan_remove_change(plan_id, change_id)`, `plan_set(plan_id, {name,
     effective_date, note})`, `plan_submit(plan_id)` (→ `action_submit`:
     `_advance_state('pending')`, chatter "Sent to the HR team",
     activity on the approvers as the precedent does), `plan_discard(plan_id)`,
     `plans_list()` → mine (draft/pending/approved) + the company's pending
     ones, for a "Plans" menu.
   * `get_chart(plan_id=None, as_of=None)` — with `plan_id` returns the
     projected tree plus `changed_ids` (people whose manager/dotted/job
     differ from live), `ghost_edges` (`[{from_manager_id, emp_id}]` for
     moved people), `virtual_roles` and `plan` summary. With `as_of` see §1.2.
5. **Client**:
   * Head: the primary button slot becomes **Plan changes** (live mode) /
     **Publish changes (n)** (plan mode) exactly as the POC; a small **Plans
     ▾** menu beside it lists `plans_list()` (open draft, waiting for
     approval, approved — with state pill and "Open" that loads that plan's
     projection read-only when not draft).
   * Draft bar (POC wording), changes side panel (list with remove, impact
     block "Effect of the plan", Publish / Undo / Redo / Discard). Undo =
     remove the last change; Redo = re-add it (client keeps a redo stack of
     change dicts).
   * In plan mode every P2 action (drag, sheets, context menu, bulk set
     manager) calls `plan_add_change` instead of the live RPC; the sheets
     show the POC's amber line "Goes into your planned changes — nothing
     moves until you publish" and the effective date field is hidden on the
     sheet (it lives on the publish dialog).
   * Chart in plan mode shows the projection: amber outline on `changed_ids`,
     dashed red ghost edge from the old manager, virtual open roles as
     dashed cards, the lane as projected.
   * Publish dialog (POC): list of changes, "Before it goes live" block,
     effective date, message → `plan_submit`. After submit: the chart
     returns to live, a toast "Sent to the HR team for approval. You'll be
     told when it is live." and the Plans menu shows it as waiting.
   * Approval inbox: the request appears through the engine (nothing to
     build); verify it opens and that approving a plan with today's date
     applies it and the chart updates.
   * `may_write` false: no Plan changes button (a viewer cannot plan either).

### 1.2 Time machine
1. `get_chart(as_of='YYYY-MM-DD')`:
   * **Past** (`as_of < today`): manager at `as_of` from `mail.tracking.value`
     rows on `hr.employee` for `parent_id` (and `pb_dotted_manager_id`):
     for each person, the oldest tracking row with message `date > as_of`
     gives `old_value_integer` as the manager then; no such row → current
     value. People whose join date (P1's helper) is after `as_of` are hidden;
     a manager hidden that way is skipped up the chain (the POC's `effMgr`
     rule). Verify the tracking field names on the box (`mail.tracking.value`:
     `field_id`, `old_value_integer`, `new_value_integer`, `mail_message_id`;
     `mail.message.date`); the `mail` module is not vendored in this repo.
     Archived-since people are NOT resurrected (say so in the payload note;
     closeout item).
   * **Future** (`as_of > today`): approved-not-yet-applied plans with
     `effective_date <= as_of` projected; people with `departure_date <=
     as_of` hidden; **future starters** from `pb.hiring.offer` in an accepted
     state with `start_date <= as_of` drawn as ghost cards "Starts <date>"
     under the offer's manager (read `pb_hiring/models/offer.py:122, 179` and
     the offer's requisition/department to find the manager; fall back to the
     department manager; none → the lane). pb_hiring is a SOFT dependency:
     guard with `'pb.hiring.offer' in self.env`.
   * The payload carries `as_of` and a one-line `as_of_note` ("Showing who
     reported to whom on 4 Jun 2026 · people who have since left are not
     shown").
2. Client: the POC's time button in the floating tools ("Today" / "N days
   ago" / "In N days") with the slider (−365…+90), the note under it, "Back
   to today"; the chart re-fetches on release (not on every tick — debounce
   250 ms). While not on today: all write affordances hidden and a slim amber
   banner "You are looking at <date>. Go back to today to make changes."

### 1.3 Suggest a chart
1. `suggest_chart()` (read-only) → `{changes: [{employee_id, to_manager_id,
   why}], left_out: [{employee_id, why}], summary}` built from:
   (a) `hr.department.manager_id` (`hr/models/hr_department.py:25`) — a
   person with no manager whose department has a manager who is not them →
   that manager; (b) else the parent department's manager, walking up
   `hr.department.parent_id`; (c) a department manager with no manager →
   the parent department's manager, else the company top; (d) the company
   top = the one active person whose title matches
   /chief executive|\bceo\b|managing director|general director|giám đốc/i
   and who has no manager; several or none → no top, those people stay
   left out with the reason "No one top person could be worked out".
   Never suggests a loop (validate with the projection helper), never
   touches a person who already has a manager.
2. Client: the lane header and the "nobody managed" empty state get a
   **Suggest a chart** button (POC dialog: "How it was worked out" with the
   real counts, "Use it" / "Not now"). **Use it** creates/loads the open
   draft plan with those changes and switches to plan mode — nothing is
   live until published. Say what it finds on rize (234 lane people) and
   payobook (18) in the report.

### 1.4 Small carry-over from P2
"Fill this role → A new starter": when the new-employee form saves a person
with the role's `job_id` (the form is opened pre-filled with it), lower that
job's `no_of_recruitment` by one (never below 0) — one guarded line where the
wizard creates the employee (`pb_people_advanced/models/people_wizards.py`,
`create_employee`/the onboarding create — grep), or an `hr.employee` create
hook in `pb_orgchart` keyed on a context flag the pre-fill sets. Pick the
smaller change and say which. Unit test it.

### 1.5 Translations, tests, report
Every new string in `vi_VN.po` (ledger §0.8); check the loaded terms with
`cache: 'no-store'` (G19); unit tests §5; report §7. SCSS gate before any
deploy touching styles (ledger §0.11); deploy lock check (§0.13).

### Non-goals (binding)
* No picture/PDF export, no share link, no ⌘K rows, no lessons, no
  virtualised canvas (P4). No email templates beyond what the chain mixin and
  precedent already send (an activity + chatter is enough; if the precedent's
  `_notify` needs a mail template, create ONE plain template "Org chart
  changes to approve" — no "Odoo" in it).
* No scenario comparison side by side (closeout candidate).
* Never apply a plan without an `approved` state, even for a system user.

## 2. Plumbing — verified, do not re-derive
* Approval engine: ledger §1 "Approval engine"; precedent files named there;
  `action_submit` precedent `contract_extension.py:141-175`; transitions
  `:59-65`.
* Department manager `hr/models/hr_department.py:25`, parent tree
  `parent_id` on the same model.
* Offers `pb_hiring/models/offer.py:122` (`start_date`), `:179` (`state`,
  `OFFER_STATES` above it).
* Tracking: `parent_id` and `pb_dotted_manager_id` are `tracking=True`
  (ledger §1, P2).
* P2's write helpers and their tests (P2 report §1).

## 3. Design to build
Hero moment: **press Plan changes and the chart becomes a sandbox** — drag
people anywhere, watch amber outlines and red ghost lines mark every move,
read the one-paragraph effect of the plan, then send it to the HR team in
one tap; drag the time slider and the chart rewinds to who reported to whom
on any day of the last year.

Keep the POC's words. The "Before it goes live" block names the real
approver role ("the HR team") and the real effective date.

## 4. Safety rails
* Loops judged against the projection; a change that would create one is
  refused with the POC sentence.
* One open draft per user per company; opening the tab with a draft present
  does NOT auto-enter plan mode — the Plans menu shows "You have a draft with
  3 changes · Resume".
* Applying is idempotent per change (`applied` flag); the cron never
  double-applies; errors never raise out of the cron (log + chatter).
* `as_of` reads never write; the time machine is disabled while in plan
  mode (and vice versa).
* Approving/refusing stays with the engine's own screens; do not add a
  second approve button on the chart.

## 5. Test cases
Unit (`tests/test_orgchart_p3.py`):
1. `plan_open` creates one draft and returns the same on a second call.
2. `plan_add_change` move: projection shows the move; live tree unchanged.
3. A change that would loop against the projection (not the live tree) is
   refused; the plan is unchanged.
4. Remove a change; the projection reverts.
5. `plan_submit` → state pending, a request exists in the engine's inbox
   model for the HR role; a plain user cannot submit someone else's plan.
6. Approve (through the engine's own method) with `effective_date` = today →
   plan applied, employee `parent_id` changed, each change `applied`.
7. Approve with a future date → not applied; run the cron method with a
   frozen "today" ≥ the date → applied.
8. A change that fails at apply time (the target archived in between) →
   `error` on that row, plan stays `approved`, others applied, chatter
   message; cron retry leaves applied rows alone.
9. `get_chart(plan_id)` returns `changed_ids`, `ghost_edges`, virtual roles.
10. `get_chart(as_of=past)` after two tracked manager changes returns the
    manager as of each date; a person who joined after the date is hidden.
11. `get_chart(as_of=future)` includes an approved-not-applied plan's moves
    and hides a person with `departure_date` before the date; an accepted
    offer with an earlier `start_date` appears as a ghost (skip with a note if
    pb_hiring is absent in the test DB).
12. `suggest_chart` on a fixture (department managers, parent departments,
    one CEO) suggests the right manager for every lane person, leaves out a
    person in a department with no manager and no parent, never a loop.
13. "Use it" path: a plan is created from the suggestion with n changes.
Browser (rize + payobook; console clean; `p3_shots/`):
14. Plan changes → drag two people, add a role, swap → draft bar counts 4,
    amber outlines and ghost lines visible, changes panel lists them with the
    POC labels, Undo/Redo work, Discard restores.
15. Publish → dialog → send → toast; Plans menu shows "Waiting for approval";
    the Approvals inbox shows the request with the change rows; approve it
    (as an HR manager) → the chart shows the moves live. **On rize undo the
    live result afterwards (a reversing plan or P2 undo) and leave the data as
    found; say so.**
16. Resume a draft from the Plans menu after a reload.
17. Time machine: slide to 200 days ago on payobook (the demo world has
    tracking history? If none, create two tracked moves on a p0clone/demo
    person first and rewind past them) — the manager shown changes; the
    banner and note read right; write affordances hidden; Back to today.
18. Slide forward 60 days: an approved future plan's moves appear; a person
    with a departure date disappears; an accepted offer's ghost card appears
    (payobook has offers? say).
19. Suggest a chart on rize: dialog shows how many it can place; Use it →
    plan mode with the changes; Discard. Report the counts and why the
    left-out ones were left out.
20. Vietnamese: one dialog and the draft bar screenshot in vi_VN.
21. No console errors; no "Odoo" on screen (including the approval request
    detail and any mail template).

## 6. Deploy / verify
Ledger §0.4; `full` (new models, access, cron, chain seed). Verify the seed
laid the `orgplan` route on every company of the four DBs (query the
engine's definition table, name it in the report). PO gate. Browser cases.

## 7. Report back — `ORGCHART_P3_REPORT.md`
Files/commits; each test with evidence; the approval route as seeded per
DB; tracking field names verified; what suggest-a-chart finds on rize and
payobook; deploy table; design-bar self-score; new gotchas appended to the
ledger; anything P4 needs (export of the projection, lessons content, the
list of open closeout questions so far: pay on the chart, public share link,
scenario compare, archived-since in the past view, CSV on a cut chart,
virtualised canvas).
