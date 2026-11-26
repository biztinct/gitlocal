# PSCHEME P1 — report

## PAUSED (2026-11-26, coordinator: owner going offline)

Stopped on the coordinator's instruction, after finishing the edit in hand. **No code has been loaded into Odoo or
tested.** Nothing was pushed, released or run on a server. Result line: **NO-GO for P2 (phase not finished).**

### Done (written, not run, not tested)
| Area | File | What |
|---|---|---|
| A.1 model | `pb_scheme_map/models/pb_person_scheme.py` (new) | `pb.person.scheme` cloned from `pb.division.link`. Fields as specified, kind of run derived from the scheme (stored related). Constraints: dates in order, no final settlement, scheme of the person's company, no overlap per (person, kind). Each one gives a plain sentence. Stale marks on create / write / unlink for the people touched. Daily `_cron_mark_boundaries` (rows starting today or ended yesterday). |
| A.2 / A.3 rung | `pb_scheme_map/models/pb_scheme_map.py` | `RUNGS` per A2. New `ADVANCE_RUNGS` and `SKIP_PERSON` (`pb_scheme_skip_person`) constants. `_person_rows_for` (ledger A4), `_person_schemes` (one ORM search per roster, skipped under the context key), `_person_answer` (adds `date_from` to the answer), `_rung_person` (A3 authoritative, with plain "none" sentences per case). Called in `resolve_many` between segment and team; `full_final` falls through. `resolve_for_draft` answers from `values['scheme_id']` / `['advance_scheme_id']` first (`_draft_person`). |
| A.4 | `pb_hr_payroll_formula/models/hr_payslip_formula.py` | Payslip rung 3 passes `on_date=self.date_from`. |
| B.1 | `hr_employee.py`, `pb_scheme_board.py`, `pb_hr_payroll_formula/models/scheme_component_scope.py` | The two map copies use `ADVANCE_RUNGS`. The formula literal is now `('person','department','division','rule')`. `segment` was dropped there: it was a no-op, because a segment answers every kind with the one scheme already added as main. That makes the three lists equal (A6). |
| B.2 / B.4 | `pb_scheme_map/models/hr_employee.py` | New stored `pb_paid_by_own`, written by the recompute. An `hr.employee.write` with `payroll_country` marks stale only (A7). |
| D.2 / D.4 board | `pb_scheme_map/models/pb_person_scheme_board.py` (new) | `person_set` (HR may ask; lane = fast / route / none; refuses up front when the lane would carry it out but the user lacks the carry-out right). `_person_propose` (kind `person_set`, snapshot, target = the person). `_person_set_write` (D.2 semantics, idempotent). `person_scheme` read API (main / advance / next change / waiting / history / choices of the Country of work and others / paired advances / lane / default date). Helpers for snapshot and "moved" words. |

### Half-done (needed before anything can load)
- `pb_scheme_map/models/__init__.py` does not import `pb_person_scheme` or `pb_person_scheme_board` yet.
- `pb_scheme_map/security/ir.model.access.csv` is not written: read-only for the map's READ_GROUPS, no write for
  anyone. It must also be added to the manifest `data`. The manifest comment "declares no table of its own" must change.
- The cron record is not yet in `pb_scheme_map/data/ir_cron.xml`. Planned xml id: `cron_person_scheme_boundaries`,
  daily, code guarded on the registry like the existing one.
- Manifest versions not bumped (pb_scheme_map, pb_hr_payroll_formula).

### Not started
- D.1 proposal kind in `pb_hr_payroll_formula/models/schememap_approval.py`. Plan:
  - label `person_set` "Change a person's pay scheme";
  - `_proposal_kind_label` override that returns `_()` words for all six kinds;
  - `_live_snapshot` / `_proposal_moved` / `_proposal_rows` / `_apply_person_set` for `person_set`, delegating to the
    board (`_person_snapshot`, `_person_moved_words`, `person_set` under `SCHEMEMAP_WRITE`).
- C.2 / C.3 pay run (`pb_payrun_wizard`). Plan:
  - `scheme_preview` gains `elsewhere` / `elsewhere_people`: people answered by another scheme on the person rung,
    whom the ladder under `pb_scheme_skip_person` would put in this run;
  - a quiet grey line on step 1 with a toggle and names;
  - the help sentence becomes two options.
  - Finding: the existing "not covered" panel (`payrun_wizard.xml:92`) is orphaned. `toggleNotCovered` is never bound
    since the scheme picker moved into a dialog. Plan: add a quiet toggle line for it too, and report that as an
    addition.
- E Add employee: `_scheme_for` / `decides` / `_values` / `create_ext` hire write, the advance switch, retiring the
  amber sentences, intro texts. Detailed plan in the working notes below.
- F panel + dialog + contract strip. Decision taken: `pb_scheme_map` owns the side-panel block. Checked: adding
  `pb_employee_vault` to its depends makes no cycle, and none of the vault, contracts, wizard or formula modules
  reaches `pb_scheme_map`.
  - Template plan: put the block inside the generic `pev-sec` section and hide its `dl` for `kind === 'pb_scheme'`.
    Do not touch the section's `t-if`: the bank panel sets that attribute, and the inherit order is not guaranteed.
  - Contract drawer plan: client-side registry `pb_person_scheme` only. `pb_contracts` gets no new dependency.
- All tests T1–T29, both suites, walks W1–W7, translations, ledger gotchas, commit split.

### Local state
- Databases:
  - `ps_base` = copy of `nh12_base` with `pb_job_change`, `pb_loans`, `pb_retro` and `pb_expense_payroll` installed
    (the suite list needs them);
  - `ps_b` = a "before" copy.
  - Both are local Postgres only, and both are kept. Filestores are in this session's scratchpad `data/`.
- "Before" tree: a `git archive` of `2902c2121` in the scratchpad `before/` folder (1.0 GB). Confs: `ps.conf`
  (worktree), `psb.conf` (before tree), `psw.conf` (walk, port 8445). Scripts: `mkdb.sh`, `runt.sh`.
  - The scratchpad is session-specific. A resumed session may need to re-create these: copy the confs from the NEWHIRE
    P8 scratch `p8.conf` pattern, and re-archive.
- The "before" suite on `ps_b` was started and **stopped mid-run on purpose** (pause). It has no result and must be
  re-run from scratch. No local server is running.

### Next three steps on resume
1. Finish the half-done wiring: `__init__` imports, the access csv in the manifest, the cron record, version bumps.
   Then add the `person_set` kind to `schememap_approval.py`. Load on a copy of `ps_base` (`-u pb_scheme_map,
   pb_hr_payroll_formula`) and fix load errors.
2. Write `pb_scheme_map/tests/test_person_scheme.py` (T1–T21). Restart the "before" suite on a fresh copy of
   `ps_base` in the background while coding.
3. Build E (Add employee) and C (pay run), then F (panel, dialog, contract strip), translations, walks and the report.

### Working notes for E (so they are not re-derived)
- `_scheme_for`:
  - `usual` = the ladder answer only when it is of the chosen Country of work. Drop the `team_rung` exception, so the
    country leads (R1).
  - `own` = the chosen scheme when it is one of the country's options. Pass `scheme_id` / `advance_scheme_id` into
    `resolve_for_draft`; `honoured` then follows.
- `decides`:
  - Keep the P7 mismatch sentence (only reachable when the country has no scheme).
  - With no scheme at all: "No pay scheme for <country> yet" (problem) plus a calm fix.
  - Remove the not-honoured and rule branches.
  - `pay_line` = "<Name> will be paid by <scheme> from <first day>." Add kwargs `advance_scheme_id=None, name=False`
    to `decides` / `places` / the payslip example / `_values`.
- New payload keys `pb_nh_own_scheme_id` and `pb_nh_advance_scheme_id`. On a payload without them, resolve after
  create and write the row only for a Country of work scheme, plus the ladder's advance (rungs in `ADVANCE_RUNGS`), so
  the pay run stays as today.
- The hire write: in `create_ext.create_employee` after the contract, before the legs, not in `PREVIEW_CTX`. It calls
  `pb.scheme.board.with_context(SCHEMEMAP_WRITE)._person_set_write(emp, main, adv or False, date_start, 'hire')`.
- Client draft key `advance_scheme_id` (null = default: one paired advance means switched on, several means none).
  Reset it on a scheme or country change. Add it to EXAMPLE_INPUTS, the decides trigger keys, `sendDraft` and
  `exampleDraft`.
- Scheme kind words on screen come from `pb.scheme.map.cycle_words`. Never use the selection labels: "Mid-Cycle" and
  "End-Cycle" contain "cycle".

## Gotchas found so far (to append to ledger §4 on resume)
- PS1. The proposal mixin's generic `_proposal_moved` prints snapshot KEYS to the user ("12 (was [...], now [...])").
  A `person_set` snapshot keyed by employee id needs its own `_proposal_moved` with names (board
  `_person_moved_words`).
- PS2. Fast lane plus a proposer without the carry-out group: the engine catches the gate error, the request turns
  "approved" with `block_reason`, and `answer_message()` then says "Sent for approval." That is a false sentence, so
  `person_set` refuses up front with a plain sentence (`_person_blocked`).
- PS3. `hr.formula.config.cycle_type` selection labels are "Mid-Cycle" / "End-Cycle" (the word "cycle" on screen).
  Use `cycle_words`.
