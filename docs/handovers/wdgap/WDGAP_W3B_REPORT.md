# WDGAP W3-B — pay review waits for its start date (PRV1), renewals (RN1, RN2): report

Branch `wdgap-w3b` (from `origin/19.1` @ `19fd98032`, which carries the S8-D merge), pushed,
not merged, not deployed. One commit per item (+ a walk-fix commit and this report).
RISKY tier: PRV1 changes WHEN wages change.

| Item | Commit | Modules (version) |
|---|---|---|
| PRV1 the yearly Pay Review waits for its start date | `3c6a1247a` (+ walk fix `0844f3e4d`, §3.4) | `pb_pay_scales` 19.0.1.1.0 → **19.0.1.2.0** |
| RN1 a renewal copies the Vietnam contract kind | `d1fe98a40` | `pb_people_advanced` 19.0.1.1.3 → **19.0.1.1.4**, `pb_contract_lifecycle` 19.0.1.3.3 → **19.0.1.3.4** |
| RN2 Renew links new → old from now on + read-only check | `7f2d88ce3` | `pb_people_advanced` (bumped once, by RN1), `pb_contract_rules` 19.0.1.0.1 → **19.0.1.0.2** |

No `pb_pay`, `pb_lifecycle`, `pb_me_portal`, `pb_explorer`, `pb_pack_*`, formula-engine or vendored
file was edited. No back-pay input is written anywhere (C-6). No new job (the existing one is reused).

## 1. What was built (what HR sees)

### PRV1 — the Pay Review waits for its start date (`pb_pay_scales`, by inheritance)

Where: People › Pay › Review › a review › Apply. Who approves and who may press Apply is unchanged.

* **Start date in the future** — the preview says "Nothing is written today. The new pay is written on
  1 Dec 2026; until then contracts and payslips stay as they are." and "You can take it back until 1 Dec
  2026, on one button." Apply writes NOTHING on any contract, pay line, dated change or payslip; each
  person gets a pay record in the new state **"Waiting for its day"** (wage seen at Apply → new wage). The
  review's chip reads **"Applies on 1 Dec 2026"** with an indigo line "New pay for 2 contracts is written on
  1 Dec 2026. Until then nothing changes on any contract or payslip, and you can take it back." and
  **Take it back** (until the start of that day in the company's time zone). Close waits for the day.
* **On the day** the existing quiet hourly job of `pb_pay_scales` ("write approved rises on their day",
  `pb.pay.scale.raise._cron_apply_due`) also writes due reviews: one review per transaction, row-locked,
  idempotent. Per person: `hr.contract.wage` + ONE dated `hr.contract.advantage.change` (new source
  **"From the pay review"**, effective date = the review's start date, for the wage input of the person's
  scheme — BASIC / WAGE / BASE — when it has one; the same record Change job and Raise the scale write) and
  the pay record becomes "Applied"; letters as before (pay-review letter, 25 inline, rest by the pay
  letters job). A person whose pay moved since Apply, whose contract stopped running or ends before the
  start is **skipped with the reason** (never overwritten) and listed on the review. Take-back closes once
  written.
* **Start date today or earlier** — the original Apply runs untouched (golden: same wages, same 24-hour
  take-back, same letters), plus the same dated record per person dated the review's own start date. A
  take-back within the 24 hours also writes the way back as a dated record (Change job precedent).
* **Start date in a month already paid** — after Apply the review shows an amber banner **"This change
  starts in a month already paid."** "1 person was paid for September 2026, October 2026 before their new
  pay was written." with **Re-work those months**: it opens NEW draft Past-month re-works (one per pay
  scheme) for those people and months through `pb_retro`'s own door and gate (`pb.retro.board.save_review`,
  in the reader's rights), straight on the re-work. A second press opens the same one ("Open the re-work").
  Without `pb_retro`: "Tell the pay team: they can work out any difference by hand on the next pay run."
* **No start date** — exactly as before (golden; no dated record). How common: **none can exist** —
  `pb.pay.review.effective_date` is `required=True` with a default of today and the column is NOT NULL
  (checked on the local copy); the old-screens migration also always sets it. The local template has 0
  pay reviews; `pb_demo` creates none (grep). Deploy agent: `SELECT count(*) FROM pb_pay_review WHERE
  effective_date IS NULL` should be 0 everywhere.
* **Reviews applied before this change** are untouched: the job reads only rows in the new state, which only
  a new Apply writes; their take-back writes no dated record (none was written for them).

### RN1 — a renewal copies the Vietnam contract kind (`pb_people_advanced`, `pb_contract_lifecycle`)

* The same renewal path S8-D fixed for pay lines (`pb.people.contract.wizard.create_contract` with
  `renew_from`, used by Contracts › **Renew** and by the decision board's `_build_new_contract`) now carries
  `vietnam_contract_type` (Fixed-term / Open-ended / Seasonal) from the old contract.
* **Never the trial**: a "probation" kind is not carried (the new contract keeps the field's default,
  open-ended); a trial typed on the form is refused; `pb_payroll_contract_type` (the Vietnam payroll trial
  treatment) is never touched.
* The Renew dialog shows **"Kind of contract (Vietnam)"** prefilled with the old kind (on a Vietnam company,
  or whenever the old kind is not the default) so HR can change it before saving. Board extension: the draft
  contract carries it (changeable on the contract form before it runs).
* **"Make it permanent"** (no end date) still makes an open-ended contract (`vn_kind='indefinite'` passed).
* Everything is probed: a database without the Vietnam payroll module sees nothing new.

### RN2 — the Renew button links new → old, from now on (`pb_people_advanced`, `pb_contract_rules`)

* `create_contract(renew_from=…)` writes `pb_renewed_from_id` (the link the fixed-term count reads,
  `pb.contract.rule.chain`) — same person only, field probed. No backfill.
* **Read-only check** for the deploy agent: `pb_contract_rules/tools/renew_button_links_check.py`
  (server shell, READ ONLY transaction, rolled back) → `pb.contract.rule.renew_link_report()`: past renewals
  with no link (same person, new contract starting within 31 days after the old one ended, nothing linked to
  either, no contract between them), the gap, whether the dates already join them (gap ≤ the rule's break,
  default 30 days — then the link changes nothing), and how many people would show the red "past the rule"
  warning on their latest contract **now** vs **if linked** (a what-if through `chain(..., links=…)`, nothing
  written), with the names of those newly warned. Honest limit: for past contracts the system cannot tell a
  Renew-button renewal from one made by hand or imported, so every such pair is listed.

## 2. Files edited (file : what)

| File | Change |
|---|---|
| `pb_pay_scales/models/review_dated.py` (new) | `hr.contract.advantage.change.change_source` += `pay_review`; `pb.pay.apply`: state += `scheduled`/`skipped`, `pbs_change_id`, overrides `preview_review`, `apply_review`, `undo_review`, new `_pbs_schedule`, `_pbs_start_review`, `_pbs_start_due_reviews`, `_pbs_log`, lock; `pb.pay.review`: `pbs_paid_months_json`, `pbs_rework_ids_json`, `_pbs_status`, `_pbs_paid_info`, `pbs_open_rework`, `_before_approval_transition` (Close waits); `pb.pay.reviews`: `_card`, `_actions`, `pbs_open_rework` |
| `pb_pay_scales/models/scale_raise.py` | `_cron_apply_due` also calls `pb.pay.apply._pbs_start_due_reviews()` (tally keys `review_*`) |
| `pb_pay_scales/static/src/js/review_dated.js`, `xml/review_dated.xml`, `scss/scales.scss` (new/appended) | patch of `PbPayReview` (`pbsRework`), template inheritance of `pb_pay.PbPayReview` (banner after `pp-review-actions`, preview lines) |
| `pb_pay_scales/__manifest__.py` | version, two assets, one description sentence |
| `pb_people_advanced/models/people_wizards.py` | `get_defaults` prefill `vn_kind`/`vn_kind_show` + `vn_kinds`; `VN_KINDS`, `_vn_kind_field`, `_vn_kinds`, `_renewal_kind`, `_kind_for_new`; `create_contract` finds `old` once, writes kind + `pb_renewed_from_id` |
| `pb_people_advanced/static/src/js/contract_wizard.js`, `xml/contract_wizard.xml` | "Kind of contract (Vietnam)" select on Renew |
| `pb_contract_lifecycle/models/contract_review.py` | `_build_new_contract`: no end date → `vn_kind='indefinite'` |
| `pb_contract_rules/models/contract_rule.py` | `chain(..., links=None)`, `check_extension(..., links=None)` (read-only what-if), `renew_link_report()` |
| `pb_contract_rules/tools/renew_button_links_check.py` (new) | the read-only check |
| i18n | `pb_pay_scales` vi/id +33 entries, `pb_people_advanced` vi/id +4 |

## 3. Tests

Local database `wdgap_w3b_t` (restore of the S6-merge base dump, every module behind the PRISTINE
`origin/19.1` tree upgraded, Step 9 modules installed, jobs and mail off; dumped once and restored per run),
ports 8931–8934, dropped at the end with its filestore.

### 3.1 New tests — 15, all pass (tag `wdgap_w3b`)

| # | Case | Result |
|---|---|---|
| V1 | future date: preview line; Apply → SQL spy: zero writes on contracts, pay lines, dated changes, payslips, payslip lines; rows "Waiting for its day"; card "Applies on …", Take it back on, Close off; job before the day: nothing; on the day: both wages written, ONE dated record each (`pay_review`, BASIC, the start date, old→new amounts); job again: zero writes; take-back refused after | PASS |
| V2 | today AND 40 days back: GOLDEN — final wages equal the OLD Apply's on the same review (run by the old code, rolled back); 24-hour take-back stays; dated records dated the review's start; take-back → old wages + reverse dated records | PASS |
| V2b | a scheme with no wage input: wages written, no dated record | PASS |
| V3 | take back before the day: zero pay writes, review approved again, job never writes it; applied again then after the deadline → refused "can no longer be taken back" | PASS |
| V4 | Apply twice → refused, zero writes; Close refused while waiting; a person whose pay moved since → skipped with reason, never overwritten, listed on the card; job again zero writes; Close works after the day | PASS |
| V5 | start 1 Sep, Sep + Oct finished: note + banner "This change starts in a month already paid."; NO back-pay input (C-6); Re-work → DRAFT `pb_retro` re-work for that person, worked out **BASICPAY +8,800,000** (Sep + Oct × 4,400,000); paid payslips byte-identical; second press = same re-work; without `pb_retro` → calm note, door refuses in words | PASS |
| V6 | no start date (forced on the copy: NOT NULL dropped in the test transaction) → wages = old Apply's, no dated record, no waiting rows | PASS |
| V7 | group review over a VND and a USD company: each row keeps its own money, the card shows a count and a date only, each contract gets its own figure on the day | PASS |
| V8 | a review applied by the old code: the job writes nothing (spy), no "Applies on", take-back writes no dated record | PASS |
| N1 | Renew prefill `definite`, kinds offered never include a trial, new contract `definite`; HR picks Seasonal → `seasonal`; old untouched | PASS |
| N2 | old trial contract → prefill empty, new = default `indefinite`, `pb_payroll_contract_type` not copied; `vn_kind='probation'` on the form → not written | PASS |
| N3 | board extension carries `definite` and the link; Make it permanent (no end) → `indefinite` | PASS |
| N4 | Renew writes `pb_renewed_from_id`; a plain new contract and another person's contract → no link | PASS |
| N5 | button renewal after a 59-day break (> 30-day rule break): chain 2, next extension past the Vietnam rule (number 3); the same dates unlinked → 1 | PASS |
| N6 | read-only check: lists the 59-day and next-day unlinked pairs, not the linked one; gap and "joined by dates" right; the 59-day person is newly warned if linked, the next-day one is not; SQL spy: zero writes; the tool sets READ ONLY and rolls back | PASS |

### 3.2 Suites vs baseline (baseline on the pristine tree BEFORE any edit, PRD-2; every suite's module in `-u`, S5B-4)

| Run | Suites | Tests | Failed / errors |
|---|---|---|---|
| Baseline | pb_pay 136, pb_pay_scales 32, pb_job_change 22, pb_contract_lifecycle 10, pb_contract_rules 9, pb_people_advanced 0 | 209 | **1 failed**: `pb_pay TestVietnameseIsComplete.test_t4c…` (known, S8-B baseline) |
| Branch | same + 15 new (pb_pay_scales 41, pb_contract_rules 15) | 224 | **the same 1**, identical assertion text (md5 equal) |

The pb_pay suite runs WITH this override active (its T6 apply/undo/letter/position tests go through the
new today-path) — green. Same logged noise both sides (`pb_pay_rating` unique-violation test, S8-D R8
traceback). Re-run after the walk fix: see §3.4.

Static gates: `py_compile`, XML parse, `node --check` on every changed file; PO gate (`PoFileReader`):
pb_pay_scales vi/id 604 rows (369 code), pb_people_advanced vi 90 / id 16; placeholders identical; no
vendor word in any msgstr; new `.po` header unchanged ("Payobook 19.0").

### 3.3 Browser walk (local `w3b.localhost:8933`, own cookie jar, `--max-cron-threads=0`, inside the People hub)

Seed (local only, scratchpad `w3b/walk_seed.py`): DEMO Lan Bui / DEMO Minh Tran (12 M / 18 M), DEMO Hoa Pham
(30 M, finished Sep + Oct payslips on "DEMO Office scheme"), DEMO Mai Fixed (fixed-term, Vietnam kind
fixed-term, ends in 20 days); two approved reviews.

* People › Pay › Review › "DEMO Yearly review 2027" (starts 1 Dec 2026) › Apply: preview shows both new
  lines; "Apply the new pay" → chip **Applies on 1 Dec 2026**, indigo banner, Take it back; contracts still
  12 M / 18 M. Take it back → "Taken back. Nobody's pay changed, and the review is approved again." → Apply
  shows again.
* "DEMO Mid-year correction" (starts 1 Sep) › Apply: old 24-hour toast + "This change starts in a month
  already paid."; amber banner "September 2026, October 2026" + **Re-work those months** → opened the
  Past-month re-work board straight on a NEW draft "DEMO Office scheme Sep 2026 – Oct 2026 · Pay review
  DEMO Mid-year correction starts on 1 Sep 2026, in a month already paid."
* Contracts › DEMO Mai Fixed › **Renew**: "Kind of contract (Vietnam)" = Fixed-term (options Fixed-term /
  Open-ended / Seasonal, no trial); chose Seasonal, dates, Create → new-hire route ("Sent for approval");
  applying that request (shell, local) made contract 3021 **seasonal**, linked to 3020, chain count 2.
* The read-only tool ran on the walk copy through `odoo-bin shell` (prints the table and counts).
* Console: no errors from these screens (one 500 on the login page before sign-in = missing local filestore
  images, S6A-7; letter PDF not printed locally = no wkhtmltopdf, S6A-6/S9A-4 — the change still applies).

### 3.4 Walk finding, fixed

"1 people were paid for …" → "One person was paid for …" (and "One person was not written on the day:");
vi/id added; `/pb_pay_scales,/pb_contract_rules` re-run: see the result line in §3.5.

### 3.5 Re-run after the walk fix

`-u` the four edited modules + pb_pay, pb_job_change; tags `/pb_pay_scales,/pb_contract_rules`: **56 tests, 0 failed, 0 errors**. Translations checked loaded: vi "Applies on %s" → "Áp dụng từ %s", id "Open-ended" → "Tanpa batas waktu"; the two web strings of the banner present in the vi web catalogue.

## 4. Rails

| Rail | Proof |
|---|---|
| Nothing written before the start date | V1, V3 (SQL spy, zero writes on the five pay tables) |
| Same final wages as before for today/past | V2 golden against the old code on the same review |
| No back-pay input (C-6) | V5 (retro adjustments none; draft re-work only, through pb_retro's own gate) |
| Never two currencies added | V7; the screen shows counts and dates only |
| Idempotent | V1/V4 (job twice, Apply twice: zero writes) |
| Silent on upgrade | no data migration; new states/fields empty; the job searches one empty set; nothing sent |
| Old reviews untouched | V8 |
| Trial never carried | N2 |
| Check is read-only | N6 (spy), READ ONLY transaction in the tool |
| White-label | gates above; no vendor word in any new string or msgstr |

## 5. Contracts other phases rely on

* `pb.pay.apply.state` += `scheduled` ("Waiting for its day"), `skipped` ("Not written"); `pbs_change_id`.
  Readers that filter `state = 'applied'` (portal "your pay", letters job, pay-change count) see a waiting
  rise only once it is written.
* `hr.contract.advantage.change.change_source` += `pay_review` (read by proration and `pb_retro` like any
  source except `checked`/`auto_default`).
* `pb.pay.apply._pbs_start_due_reviews(limit=20)` (called by the scale-rise job); `pb.pay.reviews.pbs_open_rework(review_id)`.
* `pb.people.contract.wizard.create_contract(vals)` accepts `vn_kind`; `get_defaults(renew_from)` prefill
  `vn_kind`, `vn_kind_show`, top-level `vn_kinds`.
* `pb.contract.rule.chain(contract, rule=None, links=None)`, `check_extension(contract, months, links=None)`,
  `renew_link_report(window_days=31, months=None)`.

## 6. Deploy notes

**Tier: RISKY** (when wages are written). Order: after the S6 + S8-D go-live (this branch sits on it).

* `-u pb_pay_scales,pb_people_advanced,pb_contract_lifecycle,pb_contract_rules` on all five databases
  (`payobook`, `payobook_template`, `p0clone`, `rize`, `sudima`; never `abm`). Asset purge + restart (JS/XML/
  SCSS in two modules). No migration, no backfill, nothing sent.
* Before: `SELECT count(*) FROM pb_pay_review WHERE effective_date IS NULL` (expect 0) and
  `SELECT state, count(*) FROM pb_pay_review GROUP BY 1` (approved-not-applied reviews are the ones whose
  next Apply behaves the new way — tell the owner if any exist).
* **Rehearsal on a rize clone should prove:** upgrade EXIT 0, no new ERROR; recompute a few runs old vs new =
  0 differing payslips (W2M-4: count the ones that compute); contracts, pay lines, dated changes, pay records
  identical after the upgrade; the scale-rise job runs once with an empty tally; on the clone only: a DEMO
  review approved with a future date → Apply writes no contract; with the clone's date moved (or a review
  dated today) the job writes wage + one dated record; a DEMO Renew of a Vietnam fixed-term contract carries
  the kind and the link.
* **RN2 read-only check, per database** (the file ships in the module; stdin, so postgres file access is not
  needed):

  ```
  sudo -u odoo /odoo/odoo-server/odoo-bin shell -c /etc/odoo-server.conf -d <db> \
      --no-http --max-cron-threads=0 \
      < /odoo/odoo-server/addons/pb_contract_rules/tools/renew_button_links_check.py
  ```

  Prints the unlinked pairs (company, person, old contract, old end, new contract, new start, gap days, rule,
  already joined by dates) and "red warning now N, if linked M; would newly show it: <names>". Change nothing;
  hand the counts to the owner.
* Live look: People › Pay › Review on a review with a future date shows the preview line; the Contracts Renew
  dialog of a Vietnam fixed-term contract shows "Kind of contract (Vietnam)".

## 7. Deviations and decisions taken (reversible)

1. **Where the code lives**: in `pb_pay_scales` by inheritance, not in `pb_pay`, because the job the handover
   names (the scale-rise dated-apply job) lives there and `pb_pay` cannot depend on it. Consequence: a database
   with `pb_pay` but without `pb_pay_scales` keeps today's behaviour (all five have both).
2. **A person whose pay moved between Apply and the day is skipped, not overwritten** (as Change job and Raise
   the scale do); the review lists them with the reason. Today's same-day Apply has no such check (golden).
3. **Letters are printed on the day**, when the pay is written (as Raise the scale), not at Apply.
4. **Take-back for a future review** lasts until the start of the day in the company's time zone; after the
   job writes, it is closed. Past/today keeps the 24 hours.
5. RN1: on a renewal of a trial the new contract shows Open-ended (the field's own default), not empty.

## 8. Owner questions (plain English)

1. **The Vietnam "payroll treatment" box (Permanent / Probation) is still left empty on a renewed contract**,
   as before. You ruled "never the trial flag", so it is not copied at all. Should "Permanent" be copied when
   the old contract said Permanent? (It is read by the Vietnam pay formula, so this one can change pay.)
2. **Somebody's pay changes between pressing Apply and the start date** (for example a promotion): Payobook
   now leaves that person out on the day and lists them on the review, instead of overwriting the newer pay.
   Is that what you want, or should the review win?

## 9. Left for later

* Raise the scale and Change job do not yet see a waiting pay review as "a rise for them is waiting" (the
  later writer simply finds the pay moved and skips with the reason).
* The scale-rise job's name still says "rises"; it also writes due pay reviews (named in its code).

## 10. Gotchas → ledger

| # | Gotcha |
|---|---|
| W3B-1 | The worktree guard refuses shell lines that mention a path containing "gitlocal" together with pipes/grep/loops (PRA-5): log summaries need a scratch script (`summ.py`). |
| W3B-2 | A golden "same as the old code" test can call the base class function directly (`OldApply.apply_review(self.Apply, id)`) inside a savepoint that is rolled back by raising — it still dispatches `self.*` calls to overrides, so keep the comparison to final values. |
| W3B-3 | `pb.pay.review.effective_date` is NOT NULL; a "no date" test must `ALTER TABLE … DROP NOT NULL` inside the test transaction (DDL rolls back in PostgreSQL). |
| W3B-4 | A take-back deadline tied to "the start of the day" must be closed by the writer too (`undo_until = now − 1 s`): a job run on a simulated day (or a time-zone mismatch) otherwise leaves a take-back that undoes written pay. |

## Follow-up RN3 (owner ruling, 2026-11-17) and PRV2

**PRV2** — owner confirmed "leave them out and list them" (§8 question 2): no change.

**RN3** — a renewal copies the Vietnam payroll treatment (`hr.contract.pb_payroll_contract_type`) **only
when the old contract says Permanent**; Probation is never copied (the new contract stays empty, as before);
an empty one stays empty. This answers §8 question 1.

* Where: the same path as RN1 — `pb.people.contract.wizard.create_contract` with `renew_from`, so both the
  Contracts **Renew** button and the decision board's extension (`_build_new_contract`, which the contract
  rules module passes through) carry it. New helpers `_treat_field`, `_renewal_treatment`,
  `_treatment_for_new` in `pb_people_advanced/models/people_wizards.py`; field probed (`pb_employee_vault`).
* The Renew dialog shows **"Payroll treatment (Vietnam)"** ready-filled ("Permanent" or "Not set"; no trial on
  offer) on a Vietnam company or whenever the old contract has a treatment; HR's choice wins (`pay_treatment`
  in the form; a trial typed in is refused).
* **"Make it permanent" unchanged**: `_build_new_contract` with no end date passes `pay_treatment=''`, so
  nothing is carried there (as before).
* Versions: `pb_people_advanced` 19.0.1.1.4 → **19.0.1.1.5**, `pb_contract_lifecycle` 19.0.1.3.4 →
  **19.0.1.3.5**. vi/id: three new strings ("Payroll treatment (Vietnam)", "Permanent", "Not set").

Tests (tag `wdgap_w3b`, `pb_contract_rules/tests/test_wdgap_w3b_renewals.py`), all PASS:

| # | Case |
|---|---|
| T1 | old Permanent → form prefilled Permanent (options "Not set"/"Permanent", no trial) → new Permanent; board extension → Permanent |
| T2 | old Probation → new empty (Renew and board); old empty → new empty |
| T3 | HR override wins (Permanent → "Not set" = empty; empty → Permanent); "probation" typed → not written; Make it permanent → empty (unchanged) |
| T4 | **payslip golden**: a scheme whose social-insurance line reads the treatment off the contract (`contract.pb_payroll_contract_type` source, `IF(PTYPE="Permanent", BASIC×10.5%, 0)`) computes the renewed Permanent contract exactly like the old one for the same inputs (identical lines, SIEMP 2,100,000); the same renewal with the treatment removed computes differently — the carry is what keeps pay the same |

Suites re-run on a fresh copy with the branch tree (`-u pb_people_advanced,pb_contract_lifecycle,
pb_contract_rules,pb_pay_scales`, tags `/pb_contract_rules,/pb_contract_lifecycle,/pb_pay_scales`): **70
tests, 0 failed, 0 errors**. PO gate green. Browser: Contracts › DEMO Vietnam Permanent contract › Renew shows
"Kind of contract (Vietnam) = Fixed-term" and "Payroll treatment (Vietnam) = Permanent"; console clean.

**Deploy-note change.** This is pay-reading data (the Vietnam pay formula reads the treatment), but only on
contracts made by a renewal AFTER the upgrade; no existing contract or payslip is written. `-u` adds
`pb_people_advanced` and `pb_contract_lifecycle` (already in the list). The rize rehearsal's old-vs-new
recompute of existing payslips **must still show 0 differences** — say so in the deploy report; on the clone,
a DEMO renewal of a Permanent-treatment contract should show Permanent on the new contract.
