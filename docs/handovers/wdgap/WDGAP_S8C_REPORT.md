# WDGAP S8-C — Organisation (pb_org_structure, pb_plan_hiring) — report

## PAUSED (owner pause, 2026-11-15 ~12:20 Sydney-local run time)

**Where I stopped:** both modules are built, installed on the local test database
`wdgap_s8c_t` (kept) and their own 16 tests pass (`/pb_org_structure,/pb_plan_hiring`:
0 failed, 0 errors). The regression run of the inherited suites with the new modules
installed (`after` label) was STOPPED part-way by the pause — it must be run again.

**Exact next step (in order):**
1. Re-run the regression suites with the new modules installed:
   `bash scratchpad/s8c/suite.sh after pb_hiring,pb_orgchart,pb_offboarding,pb_decision_room,pb_org_structure,pb_plan_hiring /pb_hiring,/pb_orgchart,/pb_offboarding,/pb_decision_room,/pb_org_structure,/pb_plan_hiring`
   (scratchpad = `/private/tmp/claude-502/-Users-adity-Documents-GitHub-gitlocal/684f830c-6ed1-451c-a2de-0875eedd2479/scratchpad/s8c/`),
   then `bash summ.sh after` and compare `after.fails` with `base.fails`
   (baseline on unchanged code: 11 failed, 2 errors of 692 — list in `base.fails`).
2. Baseline for `/pb_hub,/pb_people_hub`: with the new modules they give 3 failures
   (`test_the_kit_stacks_nothing_above_twenty`, `test_the_contracts_action_opens_the_board_with_a_way_back`,
   `test_the_lens_order_matches_the_mockup`); the tests read only pb_hub / pb_people_hub
   files, but a true baseline run on a fresh copy without the new modules is still owed.
3. Translations: re-export the `.pot` (`odoo-bin i18n export … -o org.pot pb_org_structure`,
   same for `pb_plan_hiring`) because templates changed after the first export (whole
   sentences, PRD-3), then build `i18n/vi_VN.po` + `i18n/id_ID.po` (+ `.pot`) for both
   modules from the dictionaries already written in scratch `tr_org.py` / `tr_plan.py`
   (msgid → (vi, id)); drop pure `model:ir.model,name:` entries of models these modules
   only inherit; PO parse gate with `PoFileReader`.
4. Browser walk inside the People hub (Jobs lens: all four parts, job page, pause),
   the Hiring board (paused chip + banner + offer warning), the Exits drawer (would
   rehire) and the Decision Room dock ("Hiring requests" dialog): seed with scratch
   `seed_walk.py` (DEMO names, local only; activates admin/admin on the LOCAL copy),
   server with `--max-cron-threads=0` on `127.0.0.1`, console clean.
5. Version stays 19.0.1.0.0 (new modules). Finish this report (sections below), commit,
   push, drop `wdgap_s8c_t` and its filestore.

## What is built (summary, to be completed)

- `pb_org_structure` (new): job levels ladder (`pb.job.level`, `hr.job.pb_level_id`),
  job page (level, description, pay band read from Pay by probe); cost centres list
  (`pb.cost.centre`) kept in step with `hr.contract.costcenter` by a stored compute
  `hr.contract.pb_cost_centre_id`; dated moves (`pb.cost.centre.move`, today or later,
  daily quiet job); history guard in `hr.contract.write` so finished / past payslip
  lines keep their cost centre on every writer of the text; team's usual cost centre
  for new contracts; pause hiring per company / team (and teams under it) / role with
  C-2 `hr.job.pb_hiring_paused` (stored boolean); stops new requests, send-in, opening,
  adverts, careers page + application form, org-chart new open role; offers carry on
  with a warning; would-rehire mark (HR only) in the Exits drawer + quiet candidate chip.
- `pb_plan_hiring` (new): approved Decision Room plan → draft hiring requests, unique
  (plan, line) link, dock summary, role page names the plan.
- No existing file edited.
