# WDGAP S8-A — Pay structure (pay scales + build from a total): report

## PAUSED (owner pause, 2026-11-15 ~23:20 Sydney)

**Where I stopped.** All code for both new modules is written, committed and pushed on
`wdgap-s8a`; the two new test suites pass (pb_pay_scales 20/20, pb_pay_package 11/11);
vi + id translations committed. The full-suite branch run of
`/pb_pay,/pb_contracts,/pb_pay_scales,/pb_pay_package,/pb_people_advanced` was STOPPED
part-way (owner pause) — no result recorded.

**Exact next step on resume** (scripts in the scratchpad folder `.../scratchpad/s8a/`,
test database `wdgap_s8a_t` kept, both new modules installed in it):
1. Re-run the branch full suite:
   `UPGRADE=pb_pay,pb_contracts,pb_pay_scales,pb_pay_package OUT=branch_full TAGS=/pb_pay,/pb_contracts,/pb_pay_scales,/pb_pay_package,/pb_people_advanced bash .../scratchpad/s8a/branch.sh`
   and compare the pb_pay/pb_contracts failure set with the baseline
   (`baseline_failures.txt`: 3 failed + 2 errors; the 2 `TestPayStaticContract` errors
   are artefacts of the pristine-copy path and must PASS on the branch). For
   `/pb_people_advanced` there is no baseline yet: any failure must be checked against
   origin/19.1 behaviour.
2. Browser walk: seed with `walk_seed.py` (odoo shell on `wdgap_s8a_t`), start a server on
   `127.0.0.1:8571` with `--max-cron-threads=0`, walk People › Pay › Scales (inside the
   People hub), the contract drawer chip + "Build from a total", People › Add a contract
   (wage pre-filled + reason line), console clean.
3. Finish this report (sections below marked TODO), commit, push, drop `wdgap_s8a_t` and
   its filestore.

## 1. What was built (status: code complete, verification partly done)

- **pb_pay_scales 19.0.1.0.0 (new)** — scale / grade / version (dated, no overlap) /
  cell (amount or coefficient × base rate, rounding unit) / grade allowances; job → grade
  on the existing `pb.pay.band.job` (`pb_scale_grade_id`); placement row
  `pb.pay.scale.placement` gives On scale / Pinned (reason) / Drifted, computed at read
  time, never a write to `hr.contract`. People › Pay › **Scales** tab (via the new
  `pb_pay_tabs` registry): ladder grid with people per cell, +% by row / column / table,
  versions, "Start from what you pay", health cards, "place the people already paid a
  step", grade drawer (jobs, allowances), wire check per scheme. Joiners: People › Add a
  contract / Add employee open with the wage from step 1 and ask why when a typed wage is
  not a step; empty wage filled on create (contract wizard, Updates joiners sheet, Hiring
  "joined" only when the offer has no monthly pay). Grade allowances written only for the
  person's scheme's items, logged "From the pay scale" on the start date. Chips on the
  contract drawer (Bring to step / Keep this pay / Mark on step) and the employee panel.
  ⌘K 3460 "Pay scales".
- **pb_pay_package 19.0.1.0.0 (new)** — "Build from a total" card from the contract
  drawer: yearly or monthly total, basic as a share or fixed amount, one item takes the
  rest; W2-C engine + search reused; total = gross + employer contributions, a scheme's own
  total-cost line (≥ gross) is not counted twice. Read-only; "Use these figures" stages
  wage + pay line in the drawer, saved through the contract's normal approval.
- **Edited outside new modules (lane):** `pb_pay/static/src/js/pay_hub.js` (registry seam),
  `pb_pay/__manifest__.py` 19.0.3.9.0, `pb_contracts/static/src/js/contract_360.js` +
  `xml/contract_360.xml` (extra header chips, Build-from-a-total link),
  `pb_contracts/__manifest__.py` 19.0.1.15.0, `pb_contracts/i18n/vi_VN.po` (2 entries).

## 2. Tests so far

| Suite | Result |
|---|---|
| baseline `/pb_pay,/pb_contracts` (origin/19.1 pristine) | 201 tests, 3 failed, 2 errors (list in scratch `baseline_failures.txt`) |
| `/pb_pay_scales` S1–S11 (rail SQL spy, golden payslip, rights, joiners, chip) | 20/20 pass |
| `/pb_pay_package` P1–P10 (India CTC exact 28,200, total line not double-counted, read-only, rights) | 11/11 pass |
| branch full suite | TODO (stopped by the pause) |
| static: py_compile, XML parse, `node --check` on every new/edited JS | pass |
| PO gate (PoFileReader) | pass: 193 (scales) / 57 (package) strings reach the screen per language; no platform name |

## 3–8. TODO on resume

Owner questions, contracts for other phases, deploy notes, left for later, ledger rows.
