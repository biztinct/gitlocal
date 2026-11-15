# WDGAP S5-A — report: kinds of leave and how they are earned (`pb_leave_setup`)

## PAUSED (owner pause, 2026-11-15) — where I stopped

Stopped at a safe point on the coordinator's owner-pause message. Nothing is half-written.

- **Done and committed** on branch `wdgap-s5a` (from `origin/19.1` @ `abc2259b6`):
  - `eed734399` pb_timeoff 19.0.1.12.0 — balance board ignores days that ran out; own companies' kinds only.
  - `8b138cb38` pb_leave_setup 19.0.1.0.0 — the whole module (screen, drawer, build-up job, ready-made kinds, My Leave overrides, vi/id `.po`, 36 tests).
  - `8b138cb38` already holds two small test fixes made after the last run (S2 action-groups probe, S10 comment stripping); the WIP commit holds this report.
- **Last test result** (`pb_leave_setup` alone, local copy `wdgap_s5a_t`): 36 tests, 2 left failing — both were TEST bugs, fixed after that run, not yet re-run:
  S2 (`ir.actions.client` has no `group_ids` here) and S10 (the scan read an XML comment that names the vendor in engineering text).
- **Baseline recorded before any edit** (same copy, unchanged tree): pb_timeoff 129 + pb_ess_workforce 146 + pb_me_team 22 = 297 tests,
  1 failed + 8 errors: `TestLeaveRules` ×6, `TestTimeoff` 03/05, `TestP8Adversarial.test_ack_week_only_touches_my_own_shifts`.
- **Interrupted:** the full combined run (`pb_leave_setup,pb_timeoff,pb_ess_workforce,pb_me_team`) was stopped mid-run by the pause; no result.
- **Test database kept:** `wdgap_s5a_t` (pb_leave_setup installed, no walk data yet). Scratch scripts: `scratchpad/s5a/` (`run.sh`, `fails.sh`, `why.sh`, `mkpo.sh`, `walk_seed.py`).

### Exact next step on resume

1. `bash scratchpad/s5a/run.sh wdgap_s5a_t full1 -u pb_leave_setup,pb_timeoff,pb_ess_workforce,pb_me_team --test-enable --test-tags /pb_leave_setup,/pb_timeoff,/pb_ess_workforce,/pb_me_team` (background, poll `full1.done`), then `bash scratchpad/s5a/fails.sh full1` and compare with the baseline list above (`base.fails`).
2. If green against baseline: seed the walk (`odoo-bin shell -c scratchpad/s5a/odoo.conf -d wdgap_s5a_t < scratchpad/s5a/walk_seed.py`), start a server with `--max-cron-threads=0` on `127.0.0.1:<port>`, walk in Chrome: Settings › HR › Kinds of leave, list + quiet board + set-up check, drawer (all five steps, preview), Ready-made kinds (VN), switch on; then `/my/work/leave` as `demo.s5a.emp` (earned-so-far line); console clean; 614 px width.
3. Fill sections 1–8 below, commit, push, drop `wdgap_s5a_t` and its filestore.

---

## 1. What was built (summary; full detail to be written on resume)

| Item | What HR / the employee gets |
|---|---|
| 1 Set-up screen | "Kinds of leave" (client action `pb_leave_setup.action_pb_leave_kinds`, tag `pb_leave_kinds`) from Settings › HR (registry `pb_settings_category`, key `leave_kinds`, seq 42) and ⌘K (`wf_leave_kinds` 3830, `wf_leave_starters` 3840). Filter-kit list, quiet glance + three steps (switched on / waiting for review / switched off), set-up check card (kinds with no pay decision; people with no date of joining; ready-made kinds to review). Five-step drawer: what it is (name in en/vi/id, company, country) · how people take it (unit, approver, Only HR can enter this, backdating, document) · pay (paid/partly/unpaid/not decided, who pays) · allowance (counted, how earned, days a year, waiting period, service steps, most a person can hold, days run out, take ahead, start month, carry warning) · what it means + what people see (rules in words, service table, tile and form mock). Read gate: Time Off team; write gate: Time Off administrator, HR manager, system. |
| 2 Build-up | Engine A: `pb.leave.earning` audit row per person × kind × month (or year), unique key, advisory lock shared with the Rize policy; one allocation per person, kind and leave year (`hr.leave.allocation.pb_ls_year`), set (not added to) from the posted rows. Daily job `cron_leave_earning`, quiet, safe on an empty database. L2: `pb_ls_take_ahead` default OFF. Kinds left at "Given by HR" (the default) are never touched; hours kinds and policy-bound kinds never earn. |
| 3 Ready-made kinds | `pb_leave_setup/data/starters.json`: VN, ID, IN, SG, TH, KH, MY; three names each, a source note per figure; applied on demand per company, created switched OFF and "waiting for review", never twice, never `pb_policy_code` / `pb_policy_category`. Kinds whose pay is genuinely split (TH maternity, KH sick) are "not decided yet" and cannot be switched on until HR decides. |
| Fix | Balances ignore days that ran out: HR board (`pb.timeoff._balances` via new `_pb_balance_numbers` / `_pb_expired_parts`) and My Leave (override of `pb.ess.workforce.get_my_leave`); equal to core's "balance after". |

## 2. Contracts other phases rely on

- New `hr.leave.type` fields, all with defaults and no required constraint: `pb_ls_earning` ('none' default), `pb_ls_days_per_year`, `pb_ls_waiting_months`, `pb_ls_max_balance`, `pb_ls_take_ahead`, `pb_ls_expire_months`, `pb_ls_earn_from`, `pb_ls_step_ids`, `pb_ls_hr_only`, `pb_ls_starter_key`, `pb_ls_starter_version`, `pb_ls_review`, `pb_ls_sources`. S5-B can create its in-lieu kind without knowing them.
- `pb.ess.workforce.get_my_leave` keeps every key; balance rows may carry new optional keys `pb_earned`, `pb_earned_label`, `pb_next_label`, `pb_ahead_label`. `_my_appliable_types` additionally drops `pb_ls_hr_only` kinds.
- `pb.timeoff._pb_balance_numbers(emp_ids, type_ids, today=None)` → `{(emp, type): {'allocated','taken','balance'}}`; `_pb_expired_parts(...)` → `{(emp, type): (days_ran_out, taken_from_them)}`.

## 3–8. Tests table, rails, deploy notes, owner questions, left for later, gotchas

To be written on resume (see "Exact next step").
