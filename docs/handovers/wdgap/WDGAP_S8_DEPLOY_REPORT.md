# WDGAP Step 8 — deploy report (merge S8-A, S8-B, S8-C; go live ×5)

**PAUSED (owner pause, 2026-11-16 09:13 UTC) — NOT LIVE. Nothing on the five live databases or the
live module trees changed; the service was never stopped (0 s down).** The deploy-notes START of
08:56 is closed by a NOTE "held, nothing changed (owner pause)"; the deploy lock is released.

**Exact next step on resume:** re-fetch `origin/19.1`; if it moved past `ee5ee069c`, merge it in and
re-run the seam suites (§1.3 run C tags). Then, from `scratchpad/s8m/`: `stage.sh d12b8d26b
<pushed commit>` → read-only `precheck.sh` → `s8_prep.sh <commit>` (new START + fresh dumps — the
08:56 dumps are stale once anyone writes) → `s8_rehearse.sh rize wdgaps8_reh_rize 2110,2115,2116`
(optional again: it already passed on this commit) → `s8_golive.sh` → `s8_verify.sh` → DONE line
→ §5 look-only checks on payobook.com → the renewal count on a payobook copy (§2.2, not taken).

Merge-deploy-verify agent, 2026-11-16 (UTC). Handover `WDGAP_S8_DEPLOY_HANDOVER.md` (method of
`WDGAP_S5_DEPLOY_HANDOVER.md` and the W2B chain).

## 0. Order with the Step 5 go-live

Merge and all local testing ran while Step 5 was not yet live. Polled the deploy notes and
`origin/19.1` (bounded loops) until the WDGAP S5 DONE line (08:52 UTC, 431 s down) and `origin/19.1`
= `d12b8d26b` (Step 5 merge) were both there; then merged `origin/19.1` in and re-ran the seams that
Step 5 can touch (§1.3 run C). Nothing was pushed or done on the server before that.

## 1. Merge

Branch `wdgap-s8-merge` from `origin/19.1` @ `abc2259b6`; `--no-ff` in the order `wdgap-s8a`
(ba1f6adbe), `wdgap-s8b` (1f1f29d03), `wdgap-s8c` (7b4f07159). **No conflict.** Code is disjoint: only
S8-A edits existing modules (`pb_pay` 19.0.3.8.0 → 19.0.3.9.0, `pb_contracts` 19.0.1.14.0 →
19.0.1.15.0, raised by the builder); S8-B and S8-C edit no existing file. No further version raise
was needed. Then `origin/19.1` (`d12b8d26b`, Step 5 + back pay) merged in — no conflict.

Pushed: `d12b8d26b..ee5ee069c  19.1` (fast-forward, no force). Commits: 3 phase merges, `061622d4c`
(seam tests), the 19.1 merge, `ee5ee069c` (handover copies + ledger), this report.

### 1.1 Static gates (merged diff vs `origin/19.1`, 137 files)

py_compile 60: 0 failures. XML 28: 0. `node --check` on every changed JS: ok. PO gate
(`PoFileReader`) 17 `.po`/`.pot`: 0 failures, 0 msgstr naming the vendor; re-run on the server's own
reader for the 16 `.po` of the 9 staged modules: all parse. Vendor name in added user-visible strings:
**0** (the lines flagged are `<odoo noupdate="1">` roots and `.po` headers). Product name in `biz_*`: none.

### 1.2 Seams

New tests: `pb_job_change/tests/test_wdgap_s8_merge_seams.py` (M1–M4) and
`pb_plan_hiring/tests/test_wdgap_s8_merge_seams.py` (M5–M7), tag `wdgap_s8m`.

| # | Seam | Result |
|---|---|---|
| a | FACTS §9 "Shared seams" table — every row | **M4 pass**: `_master_fields` carries S8-B's two fields and the existing cost-centre box (both `super()`); `_build_new_contract` is overridden ONLY by `pb_contract_lifecycle` + `pb_contract_rules` (S8-C does not), `costcenter` is in `CARRIED_FIELDS` and S8-C's stored link follows the text on a new contract (`s8m-ren ` → the list entry); `hr.contract` fields of A (`pb_scale_state`, not stored) and C (`pb_cost_centre_id`, stored) coexist; `pb.pay.apply.job_change_id` is S8-B's only. Org chart JS and the person-panel header: separate patches, seen in the browser (c, f). |
| b | Change job with a pay change on a contract on an S8-A scale | **M1 pass**: placed on step 1 → Change job to step 2's figure → contract reads **Drifted** ("… step 1"); a pinned person raised → stays **Pinned**; the placement rows untouched; SQL spy: no write to `hr_payslip`, `hr_payslip_line`, `pb_pay_scale_placement`. |
| c | Past-dated Change job → draft Past-month re-work; with Step 5 in, sending it for payment works | **M2 pass, before and after the Step 5 merge**: change dated 1 Sep (Sep + Oct paid at 44M, raise to 50M) → "Re-work those months" opens a DRAFT re-work for that person, scheme, Sep–Oct; worked out it sees BASICPAY +12,000,000; after the Step 5 merge `action_send_for_payment` → **approved**, back-pay entries only for that person, both paid payslips untouched. |
| d | Cost-centre history (CC1) + S8-B transfer | **M3 pass**: transfer to a team whose usual cost centre is different → the running contract **keeps** its cost centre (only NEW contracts take the team's), past and draft payslip lines unchanged; then a move dated today → the finished payslip keeps "S8M-SHOP", this month's draft follows "S8M-WH". |
| e | Pause hiring × plan → draft requests | **M5–M7 pass**: paused TEAM — its line says why and makes nothing, the other line is made (1 made / 1 skipped); paused COMPANY — every line says so, 0 made; a ROLE paused on its own — the press is refused with the pause sentence and **nothing** is made, not even the open line (see S8M-4: safe, but HR must untick that line). |
| f | Assets in one bundle; browser smoke desktop AND phone | Local copy, `s8m.localhost:8863`. Claude in Chrome (desktop 1440): one bundle registers actions `pb_job_change`, `pb_job_change_open_rework`, `pb_org_jobs`, `pb_agency_staff`, `pb_retro_board`, Pay tab `scales`, `pb_build_total`, People lenses Jobs + Agency staff; Pay › Scales empty "Write your first pay scale"; person panel "Change job" icon → guided flow; contract drawer "Build from a total" beside "Work back from take-home"; Jobs lens (4 parts); Agency staff lens empty. The shared Chrome window cannot be resized, so phone width ran in headless Chrome (Playwright) at **390 px and 1440 px**: Pay scales, Job changes, Change job, Jobs, Agency staff and (after the Step 5 merge) Shift patterns — all render, **no horizontal overflow, 0 console errors** on every screen. (The only console line is a 500 for the website favicon on the login page — the local copy has no filestore.) |
| g | Hub / People hub failures S8-C could not baseline | Baseline on an `origin/19.1` archive WITHOUT the new modules (`wdgap_s8m_b`, `-u pb_hub,biz_audit_trail,pb_people`): the same 3 fail (`TestHubKitStaticGates.test_the_kit_stacks_nothing_above_twenty`, `TestPeopleHubStatic.test_the_contracts_action_opens_the_board_with_a_way_back`, `…test_the_lens_order_matches_the_mockup`). **Pre-existing; none caused by S8.** |

### 1.3 Combined local runs (Mac)

| Run | Database | Result |
|---|---|---|
| Base A — `origin/19.1` archive, no S8 modules; suites of pb_pay, pb_contracts and every module S8 extends (pb_hub, pb_people_hub, pb_hiring, pb_orgchart, pb_offboarding, pb_decision_room, pb_records, pb_contract_lifecycle, pb_vendor_access, pb_scheme_map, pb_employee_vault, pb_updates, pb_retro, pb_lifecycle, biz_audit_trail, pb_people) | `wdgap_s8m_b` | 1,588 tests, **15 failed, 2 errors** |
| Run A — merged tree, the 7 new modules installed, same suites + the 7 new | `wdgap_s8m_t` | 1,668 tests, **15 failed, 2 errors — identical set to Base A** (pb_hiring 11+2, pb_decision_room 3, pb_contracts 1, pb_pay 1 [t4c catalogue], pb_people_hub 2 — all in the builders' recorded baselines). New suites: pb_pay_scales 22, pb_pay_package 14, pb_job_change 17, pb_contract_rules 11, pb_agency_staff 10, pb_org_structure 14, pb_plan_hiring 6 — all pass. |
| Base B / Run B — `-u pb_hub,biz_audit_trail,pb_people` (their tests are at-install, S8M-1) | both | 69 tests each, the same 3 failures (seam g) |
| Seams 1–2 | `wdgap_s8m_t` | M1–M7 pass (first run found two test-side issues: a write-spy that counted the fixture's own flush, S8M-3; a renewal path the test could not drive — replaced by the override check) |
| Run C — after merging the Step 5 `19.1`: `-u` pb_hr_payroll_formula, pb_mission, pb_retro, pb_source_atlas, pb_timeoff, pb_hub, pb_people_hub; `-i` pb_leave_setup, pb_time_pay, pb_shift_patterns; suites of pb_job_change (+seams), pb_plan_hiring (+seams), pb_pay_scales, pb_pay_package, pb_retro, pb_contracts, pb_pay, pb_mission, pb_hub, pb_people_hub, pb_time_pay, pb_leave_setup, pb_shift_patterns | `wdgap_s8m_t` | 544 tests, **6 failed**: the 5 recorded ones (hub 1, people hub 2, contracts 1, pay t4c) + **`pb_hub` `TestPaletteRowsFollowTheirTabs.test_every_tab_row_carries_its_tabs_gate` — caused by STEP 5, not S8**: the S5-C ⌘K row "Make drafts" (`wf_patterns_make`, attendance managers) sits on a Patterns tab gated for officers. Deliberately narrower; it needs a line in that test's reviewed list (ledger S8M-5). Step 5 is already live with it; nothing in S8 touches it. Back pay (pb_retro 60 tests), time into pay 63, leave set-up 49, shift patterns 29, Mission 61: all pass. |

Local databases `wdgap_s8m_b`, `wdgap_s8m_t` dropped with their filestores. No other builder's database touched.

## 2. Rehearsal (server, owner-shortened; rize copy)

Evidence `/tmp/wdgap-s8-20261116T085641Z/`; backups `/odoo/backups/wdgap-s8-20261116T085641Z/`
(payobook, payobook_template 33.0 MB, p0clone 33.4, rize 46.5, sudima 33.3; each read back with
`pg_restore -l`) + previous `pb_pay` / `pb_contracts` trees. Staged = `git archive ee5ee069c`,
9 trees hash-checked = commit.

### 2.1 rize copy — PASSED (took 4 min 59 s)

Restored hidden from the live job runner, jobs + mail servers off, real counts asserted (311
employees, 487 payslips). Recompute with the live code, `-u pb_contracts,pb_pay -i` the seven new
with the staged code, recompute again (both rolled back), copy dropped.

| Check | Result |
|---|---|
| Upgrade | EXIT 0 in 45 s; **0 ERROR**, 0 Traceback (749 WARNING lines: the usual view/registry notices) |
| Versions | pb_pay 19.0.3.9.0, pb_contracts 19.0.1.15.0, the seven new 19.0.1.0.0 installed |
| Recompute old vs new | runs 2110 + 2115 + 2116, 114 payslips, 3,516 lines: **0 differing payslips**, run totals identical. Of these, 53 actually compute (2110 27, 2115 26); run 2116 refuses all 60 and 2115 one — identically before and after (W2M-4) |
| Contracts, wages, pay lines, payslips, lines, line totals, payslip and line cost centres (hashes), runs, jobs, teams, hiring requests, mails, to-dos, audit rows | **identical after install and at the end** |
| New rows | only the 2 fixed-term rule rows (Vietnam, Indonesia) and 1 "Job changes" route; 0 scales, placements, job changes, agency staff, levels, cost centres, moves, linked contracts, paused jobs, rehire marks, plan requests |
| New jobs | 2, quiet: "Change job: start approved changes on their day" (hourly), "Organisation: make cost-centre changes on their date" (daily); run once by hand: nothing to do |

### 2.2 Measurements (read-only, on the rize copy; nothing changed)

- **Fixed-term limits (rize):** Vietnam rule — 58 people whose latest contract is fixed-term with an
  end date (+7 trial agreements, not counted); **15 are AT the limit** (2 in a row: the next one
  should be permanent, a 12-month renewal would get the red warning); **0 already past it**.
  Indonesia: no running Indonesian contract has an end date, so none is near the 5-year limit.
- Renewals made in the system: 18; **0 lost pay lines** on rize so far.
- Contracts with a typed cost centre: 97, using 4 different texts. Running contracts whose job differs
  from the person's: 8.
- **payobook copy: NOT measured** — its 4 GB restore had just finished when the owner paused; the copy
  was stopped and dropped (FACTS SQL note: the person's job lives on `hr_employee.current_version_id`,
  ledger S8M-2).

## 3. Read-only live checks (08:5x UTC, after the Step 5 DONE)

| Check | payobook | payobook_template | p0clone | rize | sudima |
|---|---|---|---|---|---|
| Open START by anyone | none (last: WDGAP S5 DONE 08:52) | | | | |
| Server | disk 28 GB free of 77; memory 2.3 GB available; one service process; lock free | | | | |
| Jobs total / active | 106 / 53 (job 156 OFF) | 94 / 35 | 94 / 43 | 94 / 86 | 94 / 85 |
| pb_hiring, pb_orgchart, pb_offboarding, pb_decision_room, pb_vendor_access, pb_lifecycle | all installed | all | all | all | all |
| Every dependency of the 7 new modules | installed | installed | installed | installed | installed |
| New tables already there | none | none | none | none | none |
| Contracts / payslips / lines | 4,534 / 34,322 / 873,586 | 0 / 0 / 0 | 7 / 39 / 111 | 271 / 487 / 16,179 | 650 / 0 / 0 |

## 4. Go live — NOT DONE (owner pause)

The service was never stopped; no `rsync` into the addons directory; no `-u`/`-i` on any live
database. Live trees of `pb_pay` / `pb_contracts` are still `d12b8d26b`; the seven new modules are
absent. **`origin/19.1` is therefore ahead of the live server** by the S8 code (`ee5ee069c`). Deploy
notes: START 08:56, NOTE 09:13 "held, nothing changed (owner pause)". Lock unit stopped, lock free.

## 5. Checks on payobook.com — not done (nothing to check until live)

## 6. Held / follow-ups

- **Held: the whole go-live** (owner pause). Resume = §0 of this file's header.
- Step 5 follow-up (not S8): the ⌘K "Make drafts" row's test listing (S8M-5).
- Minor wording seen in the walk (S8-B, not fixed): the People "More" fold and the breadcrumb show the
  Agency staff lens as "People an agency supplies — not on your payroll" (its description) instead of
  "Agency staff". S8-C Jobs filter panel on an empty database reads 'Nothing matches "" here'.
- After a Change job raise to exactly another step, the person reads "Drifted" (placement still on the
  old step) — HR keeps or re-places it from the chip; a "move to step N" door belongs with S8-D.

## 7. Questions for the owner (plain words, carried from the three builders)

1. **Renewed contracts lose their allowances.** When a fixed-term contract is extended, the new
   contract starts without the old one's pay lines (meal, phone …), so they read 0 on the next payslip
   unless HR types them again. Should an extension copy them across automatically? (Recommended: yes.
   On rize none of the 18 renewals so far has lost a line.)
2. **Pay › Changes still writes a raise at once**, whatever start date it shows, and its Undo puts back
   the pay but not the job. Should Pay › Changes send people to the new "Change job" (one sign-off,
   honours the date), or learn to wait for the date itself?
3. **Vietnam and Indonesia fixed-term rules** were filled from the law as read (Vietnam: 2 fixed-term
   contracts in a row, up to 36 months each; Indonesia: 5 years in total). Can your adviser confirm
   them, and should other countries get a row? (On rize, 15 Vietnam staff are already at 2 in a row.)
4. **Pause switch on the org chart** — also wanted there, or is People › Jobs enough? (Recommended: later.)
5. Already ruled, no question: scale rises keep people paid above their step (SC2); finished payslips
   keep their cost centre (CC1); a job's level does not fill people's "Job level" box (JL1); "raise the
   whole scale" and "Build from a total" on Hiring offers come as S8-D (SC1, SC3).

## 8. New gotchas (ledger)

S8M-1 (at-install suites need their module in `-u`), S8M-2 (`hr_employee.current_version_id`),
S8M-3 (flush before a write spy), S8M-4 (a role paused on its own refuses the whole plan press),
S8M-5 (Step 5's ⌘K row narrower than its tab). The three builders' rows S8A-1..5, S8B-1..7,
S8C-1..8 are in the ledger too.
