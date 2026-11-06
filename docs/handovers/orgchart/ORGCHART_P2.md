# ORGCHART P2 — changing the chart, live

Read `ORGCHART_LEDGER.md` first (§0 rules, §1 facts, §2 decisions, §3
gotchas incl. the G5+ that P1 appended), then `ORGCHART_P1_REPORT.md` (what
shipped, where it deviated). The POC (`docs/design/org-chart-poc.html`) stays
the spec: this phase ports everything the POC does in **live** mode (not in
"Plan changes" mode, which is P3).

## 1. Scope

In `pb_orgchart` (bump to `19.0.1.1.0`):

1. **Two new fields** (ledger D2, D3), both `tracking=True`, plain-English
   strings and help, no migration needed:
   * `hr.employee.pb_dotted_manager_id` — "Also reports to" (dotted line).
   * `hr.job.pb_manager_id` — "Reports to on the org chart"; plus
     `hr.job.pb_reason` Selection `growth` "Growth — new position" /
     `backfill` "Backfill — someone is leaving" / `cover` "Cover for leave",
     optional.
   Payload: `people[].dotted_id` now real; `open_roles[].manager_id` =
   `pb_manager_id` → else `department_id.manager_id` (the resolver P1 wrote).
2. **Write RPCs** on `pb.orgchart`, every one guarded by
   `_may_write()` (`hr.group_hr_user` or `base.group_system`; else
   `{'error': "Only an HR user can change who reports to whom."}`), every one
   answering ledger D5's shape `{'ok': True, 'label': ..., 'undo': {'method':
   ..., 'args': [...]}}`:
   * `move(emp_id, manager_id, whole_team=True)` — the POC's move sheet.
     Refuses a loop server-side ("Can't do that — Giang is inside Bình's own
     team."), refuses self, refuses an archived or other-company manager.
     `whole_team=False` first re-parents `emp`'s direct reports to `emp`'s
     old manager (or to nobody if there was none). Undo = `move` back +
     the reports back.
   * `set_dotted(emp_id, manager_id_or_false)` — undo = previous value.
   * `unassign(emp_id)` — `parent_id = False` → the lane. Undo = move back.
   * `swap(emp_id)` — swap places with their manager, POC semantics: `emp`
     takes the manager's manager and the manager's other reports; the
     manager reports to `emp` and takes `emp`'s former reports. Refused when
     the manager has no manager (top of the chart) — "The top of the chart
     has nobody to swap with." Undo = `swap(manager_id)`.
   * `add_open_role(manager_id, title, reason=False)` — creates an `hr.job`
     (`name=title`, `department_id` = the manager's, `no_of_recruitment=1`,
     `pb_manager_id`, `pb_reason`); if a job with that name in that
     department already exists, bumps `no_of_recruitment` and sets
     `pb_manager_id`. Undo = decrement / unlink if it was created now with
     no other data.
   * `fill_role(job_id, emp_id)` — writes the person's `job_id`,
     `job_title`, `parent_id` (the role's manager) and decrements
     `no_of_recruitment` (never below 0). Undo = restore the three fields +
     increment.
   * `close_role(job_id)` — `no_of_recruitment = 0`. Undo = restore.
   * `move_many(emp_ids, manager_id)` — the same as `move(whole_team=True)`
     for several people in one transaction (all-or-nothing; one loop or
     refusal fails the lot with a sentence naming the person). Undo = each
     person's previous manager. This is what rize needs most: 234 of its 241
     people have no manager today (ledger G6), and setting them one drag at
     a time is not world-class.
   * `get_history(emp_id)` (read) — ledger D6: rows from
     `mail.tracking.value` for `parent_id` and `pb_dotted_manager_id` on
     `hr.employee` `emp_id`, newest first:
     `[{'when': 'YYYY-MM-DD', 'what': 'Moved from Giang to Dũng', 'who': 'Name'}]`
     (join `mail.message` for `date`/`author_id`; field by
     `field_id.name`). Old/new names resolved through `hr.employee.browse`
     with `exists()`; a deleted person reads "someone no longer here".
   `hr.job` writes: check whether `hr.group_hr_user` may write `hr.job`
   (`hr/security/ir.model.access.csv`); if not, write the job with `sudo()`
   AFTER our own `_may_write()` and say so in the report.
3. **The client**, ported from the POC's live mode:
   * **Pointer drag** of a card onto another (G2): ghost card, green "over"
     / rose "bad" (client-side loop check mirrors the server's), drop → the
     **move sheet** (whole team / only them, "What changes" list, no
     effective date in live mode — dates are P3), confirm → `move` → toast
     with **Undo** (notification service `buttons`), chart re-fetches
     `get_chart()` and re-lays out with the POC motion. Dropping on a
     collapsed manager expands them.
   * **Multi-select and bulk set manager**: ⌘/Ctrl-click and Shift-click
     select several cards (the lane especially); a "Select all N here" link
     on the lane header; a selection bar at the bottom ("12 people selected ·
     Set manager… · Clear") — Set manager opens the manager picker and calls
     `move_many`; dragging any selected card drags the whole selection (one
     ghost with a count badge) onto a manager. Selection state is a data
     attribute (G12).
   * **Card quick actions** on hover/selection: Add team member, Change
     manager, More (context menu). **Right-click** opens the same menu:
     Open side panel · Add a team member · Change manager · Add/Change
     dotted-line manager · Swap places with <manager> · Expand/Collapse team
     · Show only this team · Remove from <manager>'s team · (open role:) Fill
     this role · Close this open role.
   * **Dialogs** (in-page overlay, POC styling, OWL `t-on-click` handlers):
     Change manager (picker with search, excludes self and own descendants),
     Dotted line (picker), Add team member (Someone already here / A new
     open role with title + why / A new starter → opens the new-employee
     wizard `pb_onboard_wizard` from `pb_people_advanced` with the manager,
     team and title pre-filled — verify how that action takes params or
     context; if it cannot be pre-filled, open it plain and report), Fill
     role (Promote or move someone / A new starter).
   * **Side panel**: footer buttons (Add team member · Change manager ·
     Dotted line; open role: Fill this role), History tab (`get_history`),
     "Also reports to" fact live.
   * **Numbers**: "dotted lines" live and colour-aware.
   * **Edges**: dotted amber bezier for `dotted_id`.
   * **`may_write` false**: no drag, no quick actions, no context-menu write
     rows; side panel footer reads "Ask an HR user to change who reports to
     whom." (one sentence, no button).
   * **Every refusal** from the server shows as the server's sentence in a
     rose toast; never a traceback dialog.
4. **Translations** for every new string (ledger §0.8).
5. **Unit tests** (§5) and the **report** (§7).

### Non-goals (binding)
* No planning mode, no effective dates, no approval, no time machine, no
  suggest-a-chart (P3). No picture/PDF export, no ⌘K rows, no lessons (P4).
* No chatter posts beyond what field tracking already writes (D6). No
  emails.
* No change to `coach_id`, ever. No new sidebar items.

## 2. Plumbing — verified, do not re-derive
* Ledger §1 "The employee record": `parent_id :191` tracking, `coach_id`
  trap `:794-800`, `job_title`/`job_id` on the version `hr_version.py:119-120`.
* Ledger §1 "Open roles": `hr.job.no_of_recruitment` `hr_job.py:21`, CHECK ≥ 0 `:46`.
* Write-judge precedent `pb_contracts/models/pb_contract_360.py:245-260`;
  error-dict precedent `pb_people.py:467-481`.
* New-employee wizard: `pb_people_advanced` (`pb.people.onboard.wizard`,
  client action tag `pb_onboard_wizard`, 3 steps Person → Role → Contract;
  memory "Payobook People redesign"). Grep its JS for how it reads
  `props.action.params` / `context` before deciding how to pre-fill.
* Notification buttons: `this.notif.add(message, { type, buttons: [{ name,
  onClick, primary }] })` — grep `buttons:` in `pb_*/static/src/js` for a live
  example before using it.
* Tracking rows: `mail.tracking.value` (`field_id`, `old_value_integer`,
  `new_value_integer`, `mail_message_id`), `mail.message` (`model`,
  `res_id`, `date`, `author_id`).

## 3. Design to build
Hero moment: **drag someone onto their new manager and watch the team glide
across** — the ghost card follows the pointer, the target lights green, the
sheet says in one sentence what will change, and one tap of Undo glides it
back.

Keep every word from the POC's dialogs and toasts (`actions.js`
`dialogHtml()`, `applyChange` labels, context menu rows). Server labels
(`label` in the RPC result) are the toast text; build them server-side with
`_()` so Vietnamese works.

### 3.1 Performance rules from P1 (binding — ledger G11, G12; report §9)
* Card state during drag/selection is a **data attribute** (`data-over`,
  `data-sel`), never a class; the ghost card is inserted ONCE at drag start
  and then only its `transform` changes; `elementFromPoint` → closest
  `[data-id]` for the target. No DOM insertions per pointer move.
* After one write, **patch `this.nodes` then `buildIndex` + `relayout()`**
  (cards keep identity by signature) rather than a full `load()`; a full
  reload only after `move_many`, `fill_role` and `add_open_role`.
* Dialogs and the selection bar are single insertions (one style recalc each)
  — acceptable; never re-insert them per keystroke (keep them mounted, toggle
  with a data attribute).
* Measure drag on payobook at 667 cards: pointer-move work must stay under
  16 ms; report the number.

## 4. Safety rails
* Server is the judge: loops, self, cross-company, archived, rights — all
  refused on the server even if the client already greyed them out.
* `swap` and `whole_team=False` touch several records: do them in one
  transaction, and compute the undo payload BEFORE writing.
* `fill_role` never lets `no_of_recruitment` go negative; `close_role` on a
  job with people already in it only zeroes the target (never archives the
  job).
* Re-fetch the payload after every write (no client-side guessing of the
  new tree); keep selection and viewport.

## 5. Test cases
Unit (`tests/test_orgchart_p2.py`):
1. `move` whole team: reports follow; result label and undo payload; undo
   restores exactly.
2. `move` only-them: reports go to the old manager; with no old manager they
   go to the lane.
3. `move` into own descendant refused with the POC sentence; into self
   refused; into archived refused; into another company refused.
4. `set_dotted` set/clear + undo; tracking row written.
5. `unassign` + undo.
6. `swap` POC semantics on a 3-level fixture; refused at the top.
7. `add_open_role` creates; second call with same title+dept bumps the
   target; undo of a fresh create unlinks; undo of a bump decrements.
8. `fill_role` writes job, title, manager; decrements; never below 0; undo.
9. `close_role` + undo.
10. `get_history` returns the move from test 1 with names and author.
11. A plain user (no HR group) gets the refusal sentence from every write
    RPC and nothing changes.
11b. `move_many` of three people succeeds in one go; with one of them being
    the target's ancestor the whole call is refused and none moved; undo
    restores all three.
Browser (rize + payobook; console clean; screenshots in `p2_shots/`):
12. Drag a person onto another manager → sheet → Move now → toast with
    Undo → Undo restores.
13. Drag onto own descendant → rose outline, drop refused with the sentence.
14. Change manager via the card button and via the side panel.
15. Dotted line: add, see the amber dashed edge and the number, clear it.
16. Add team member: existing person; new open role (dashed card appears
    under the manager, number goes up); new starter opens the wizard
    (pre-filled or not — say which).
17. Fill an open role with an existing person; the person's card moves,
    the role card disappears when the target hits 0.
18. Swap places; Undo.
19. Remove from team → lane; drag back out of the lane.
20. Close an open role.
21. History tab shows the moves from 12–19 with who and when.
21b. On rize: select five people in the lane (⌘-click + Shift-click), the
    selection bar appears, "Set manager…" → pick a manager → all five move
    under them with one toast; Undo puts all five back. Then drag a
    selection of three onto a manager. **Do this on a rollback-able basis
    or undo it afterwards — rize is a live tenant; leave it as you found it
    and say so.**
22. As a user without HR rights (rize has staff logins — see memory
    "Login not linked"): no drag, no quick actions, the footer sentence.
23. Every toast/dialog in Vietnamese when the user's language is vi_VN
    (switch a test user; screenshot one dialog).
24. No console errors; no "Odoo" on screen.

## 6. Deploy / verify
Ledger §0.4; `full` deploy (new fields) to the four DBs; PO gate; browser
cases on rize and payobook.

## 7. Report back — `ORGCHART_P2_REPORT.md`
Files/commits; each test with evidence; the hr.job rights finding; the
wizard pre-fill finding; deploy table; design-bar self-score; new gotchas
appended to the ledger (G-numbered); anything P3 needs (e.g. the move
sheet already has a slot for an effective date).
