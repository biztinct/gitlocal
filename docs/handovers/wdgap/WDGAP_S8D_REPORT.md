# WDGAP S8-D — Step 8 follow-ups (SC1, SC3, EX1, PC1): report

Branch `wdgap-s8d` (from `origin/19.1` @ `c24630ccc`), pushed, not merged, not deployed.
One commit per item. RISKY tier (wages and contract pay lines).

| Item | Commit | Modules (version) |
|---|---|---|
| SC1 Raise the scale in one request (+ SC2 on the chip) | `22e5e7503` | `pb_pay_scales` 19.0.1.0.0 → **19.0.1.1.0**; one test adjusted in `pb_job_change` |
| SC3 Build from a total on Hiring offers | `fa6745d78` | `pb_pay_package` 19.0.1.0.0 → **19.0.1.1.0** (new dependency `pb_hiring`) |
| EX1 A renewal carries the old pay lines | `fb78ea063` | `pb_people_advanced` 19.0.1.1.2 → **19.0.1.1.3**, `pb_contract_lifecycle` 19.0.1.3.2 → **19.0.1.3.3**, `pb_contract_rules` 19.0.1.0.0 → **19.0.1.0.1** |
| PC1 Pay › Changes → Change job | `6fc7f9df7` | `pb_job_change` 19.0.1.0.0 → **19.0.1.0.1** |

No `pb_lifecycle`, `pb_me_portal`, `pb_explorer`, `pb_pack_*`, formula engine, `pb_pay` or
`pb_hiring` file was edited; no vendored addon. No legal minimum wage, no automatic step-up.

## 1. What was built (what HR sees)

### SC1 — "Raise the scale" (`pb_pay_scales`)

People › Pay › Scales gets a primary button **Raise the scale** (disabled while a rise of that
scale is waiting) and a **Scale rises** strip of the scale's requests. The rise drawer:

1. **The new table** — "In force from", How: *By a percentage* / *By a flat amount* / *Type the new
   table* (a coefficient scale rises through its base rate), the grid old → new with "+x%", a reason.
   A rise never lowers a step (refused with the cell named).
2. **Who moves** — five quiet cards: *Moves* (indigo), *Above step* (SC2: already paid the new step or
   more — pay kept, nothing written), *Pinned* (untouched, reason shown), *Cannot move* (amber, the plain
   reason beside each name: contract not running / ends before the rise / no amount for their step /
   paid in another money / another pay change, job change or rise for them is waiting), *Left out*
   (HR un-ticked them with "Leave out" / "Put back"). A drifted person paid BELOW their new step moves
   up to it and is marked "Was paid differently from their step". People on the scale's jobs who were
   never placed are counted in one sentence (the rise does not reach them).
3. **What it costs** — one line per currency (never added): a month and for twelve months, worked out
   through each person's own pay rules (basic pay and what follows from it + the employer's
   contributions, the W2-C engine and the S8-A totals rule), falling back to the wage difference where a
   scheme cannot be read (said under the figures).
4. A rise starting in a month already paid says so (months listed). After it is written,
   **Re-work those months** opens draft Past-month re-works (one per scheme) through `pb_retro`'s own
   door (probe; C-6: no back-pay input is written here).
5. **Send for approval** → ONE request in the Approvals inbox (new process **`scaleraise`** "Pay scale
   rises", own data row, route seeded per company: **HR lead → Finance approver**, no manager step — the
   pay-change precedent; existing seats reused through `fill_role_from_group`, never re-seated). The
   preparer is the maker (`maker_uids`), so each database's own independence setting applies. The inbox
   card shows who moves (now → new), the counts and the cost per currency.
6. On approval the **new version** is written (joiners from that day start on it). Wages are written
   **on the effective date**: today/past at approval, future by the quiet hourly job "Pay scales: write
   approved rises on their day" (row-locked, one transaction each, safe on an empty set). Per person:
   `hr.contract.wage` + a **dated `hr.contract.advantage.change`** for the scheme's wage input (source
   "From the pay scale", effective date = the rise's date — the record Change job writes and the
   Past-month re-work reads) + a `pb.pay.apply` row (`pb_scale_raise_id`, no 24-hour undo) + **one letter**
   (new letter type "Pay scale rise letter" by `selection_add`; printed by `pb.pay.apply._make_letters`,
   25 inline, the rest by the existing pay-letters job; filed in the person's documents like every
   letter). A person whose pay changed since sending is **skipped** with the reason; the others move.
   Applying twice writes nothing twice.
7. **Take it back** before the day: the version goes (the table before it is in force again), nobody's
   pay changed. After the day only a new request changes pay.

SC2 on the existing chip (S8 deploy follow-up): a person paid above their step now reads
**"Above step · Grade, step N"** (still counted with Drifted) and is never offered "Bring to step" (a cut);
a person paid exactly another step of their grade (a Change job raise) gets **"Mark on step N"**
(placement only).

### SC3 — "Build from a total" on a Hiring offer (`pb_pay_package`)

On a draft offer (Hiring board › request › offer panel), a **Build from a total** button beside
"Add a line" (recruiters who see the offer's money). The same card as the contract drawer: total a year
or a month, basic pay share or amount, the item that takes the rest, pay scheme (the role's team's scheme
first). **Use these figures** works it out again on the server and writes the split as the offer's
**monthly pay lines**: basic pay, the allowances the scheme derives (e.g. HRA), the balancing item
(e.g. special allowance), and the employer's contributions as statutory lines ("Paid by the company on top
of pay"); the scheme's own "total cost" line is not counted again; bonuses, benefits and one-off lines
stay. The offer shows "Built from a total of ₹12,00,000 a year (₹1,00,000 a month) with …". The offer
letter's `${lines}` table therefore prints basic pay and allowances. When the person **joins**, the normal
joiner path (`_ensure_contract`, already agreed by the offer route) starts the contract on the basic pay
line as the wage and writes the tagged pay items (only those of the scheme that pays the person) as
contract pay lines, each logged "From offer …" dated the start. Offers without it: unchanged. Plain
refusals: "This pay scheme does not have the pay items a total can be split into…", offer in another
money, offer already sent for sign-off, a scheme with no gross line, rights.

### EX1 — a renewal carries the old contract's pay lines

* **Contracts › Renew** (People contract dialog): opens with **"Pay lines carried over"** — each line with
  its amount; HR changes an amount or **Take off** / **Put back** before **Create contract**.
* **Contract decisions board › Extend / Make it permanent**: the new (draft) contract starts with the same
  pay lines; HR still changes them in the contract drawer before it runs.
* Every carried line is logged in the pay-line trail, dated the new start, "Carried from <old contract>".
  The old contract is never touched. **No backfill.**
* **Read-only check** for the deploy agent: `pb_contract_lifecycle/tools/renewal_lost_pay_lines.sql`
  (see §5).
* Found and fixed on the way (EX1's own path): S8-B's `pb_contract_rules` override of
  `_build_new_contract` dropped the `contract_type` argument, so **"Make it permanent" raised a TypeError
  wherever `pb_contract_rules` is installed** (all five databases once Step 8 is live). Passed through;
  the fixed-term note is written for an extension only.

### PC1 — Pay › Changes sends new raises to Change job (`pb_job_change`, by inheritance)

Pay › Changes keeps its list and history. **New pay change** still asks for the person; picking one opens
**Change job** prefilled as a pay change (`pb_start_for_employee(emp, {'reason_kind': 'pay', 'source':
'pay_changes'})`) with the line "Their new pay opens in Change job: one sign-off for the whole change, and
the new pay starts on the date you choose." A database without `pb_job_change`, and anybody outside the
Change job gate, keeps today's form exactly (the patch lives only in `pb_job_change`'s assets; `pb_pay`
untouched). **Bulk actions:** Pay › Changes has none (no selection, no bulk button) — kept as is. The yearly
*Pay Review* (a round of rises) is a different tab and still applies at once — owner question 1.

## 2. Files edited outside new files (file : lines)

| File | Change |
|---|---|
| `pb_people_advanced/models/people_wizards.py` | `get_defaults` prefill `lines` (:148-158); new `_renewal_lines` (:167-181), `_carry_renewal_lines` (:183-243); `create_contract` carries when `renew_from` (:295-306) |
| `pb_people_advanced/static/src/js/contract_wizard.js`, `xml/contract_wizard.xml`, `scss/wizards.scss` | "Pay lines carried over" block; `renew_from` sent with the form |
| `pb_contract_lifecycle/models/contract_review.py` | `_build_new_contract` vals `'renew_from': old.id` (:651-654) |
| `pb_contract_rules/models/contract_rule_hooks.py` | `_build_new_contract(self, start, new_end, contract_type=None)` passes it on; note only when `new_end` (:65-72) |
| `pb_pay_package/models/package.py` | `package_solve` split into `_solve_for(subject, …)` (unchanged maths; S8-A suite green); `bands` for offers; `use` also for an offer subject |
| `pb_pay_scales/models/placement.py`, `screen.py` | "Above step" label + `is_above_step`; chip: no "Bring to step" above step; "Mark on step N" |
| `pb_job_change/tests/test_wdgap_s8_merge_seams.py` | M1 chip assertion follows SC2 ("Above step", no stage door, "Mark on step 2") |
| manifests | versions above; `pb_pay_package` depends `pb_hiring` |

## 3. Tests

Local, ONE database `wdgap_s8d_t` (copy of `upd_p6_t_tpl`, 45 modules brought to `origin/19.1`, Step 8
modules + `pb_retro` installed), ports 8881–8888, dropped at the end with its filestore.

### 3.1 New tests — 32, all pass (tag `wdgap_s8d`)

| # | Case | Result |
|---|---|---|
| R1 | preview maths: 5% on amounts (5.5 M → 5,775,000 …), On scale moves, drifted-below moves up (marked), above new step = "above" (SC2), Pinned untouched, contract ending before the rise = "cannot" with reason; Leave out / Put back; flat amount; a typed table that lowers a step refused; 0% refused | PASS |
| R2 | real cost: (275,000 + 290,000) × 1.17 (employer insurance through the scheme's own rules) a month, ×12 a year; a person paid by an INR scheme = "cannot" ("paid in INR"), one cost line per currency | PASS |
| R3 | process row + seeded route; preparer = maker; decided seat by seat **HR lead → Finance** (Finance holds no pay role); wage unchanged until the last decision; Finance reads its seat only | PASS |
| R4 | **GOLDEN**: SQL spy on contracts, pay lines, amount changes, payslips, payslip lines, pay records, letters — zero writes across draft, preview, leave-out, send, refusal; no version until approved | PASS |
| R5 | approved for today: wages written; one DATED change row per mover (`pay_scale`, code BASIC, effective = the day); one pay record each; new version from the day, old ends the day before; movers On scale; above-step + pinned + ended untouched; one letter per mover (type "Pay scale rise letter", shows 5,775,000); applying twice = zero writes | PASS |
| R6 | future date: "Approved, starts later", zero pay-table writes, version waits; a joiner resolves to the new amount from that day only; job before the day does nothing; on the day writes it (by the job), dated row on the day; second run zero writes | PASS |
| R7 | take back before the day: version removed, previous in force again, wage untouched, job has nothing; after start → refused | PASS |
| R8 | pay changed after sending → that person skipped ("changed since"), the other moves | PASS |
| R9 | past date (1 Sep, Sep + Oct paid at 44 M): months listed; rise 10% → 48.4 M; no back-pay input (C-6); "Re-work those months" → DRAFT re-work for that person/scheme/months, worked out **BASICPAY +8,800,000**; paid payslips byte-identical; second press = same re-work | PASS |
| R10 | rights: plain user reads/prepares nothing; pay viewer reads, cannot prepare or send | PASS |
| R11 | silent install: no rise, quiet job active and idle; a new company gets the route | PASS |
| R12 | SC2 chip: paid above step → "Above step", no "Bring to step"; paid exactly step 2 → "Mark on step 2" | PASS |
| O1 | offer ₹12,00,000/yr on a DEMO India scheme: basic 50,000 (wage), HRA 20,000 (not a contract item), special 28,200 (item SPECIAL), employer PF 1,800 statutory; "Employer cost" total line and "Gross pay" not added; old monthly line replaced, yearly bonus kept; offer = 1,00,000 a month; note on the board row | PASS |
| O2 | the letter table lists Basic + DA, House rent allowance, Special allowance, Employer provident fund | PASS |
| O3 | joining: contract wage 50,000, SPECIAL line 28,200 (logged "From offer …", dated start), no HRA line; twice = once | PASS |
| O4 | offer without it: wage = biggest monthly earning, no pay line, as before | PASS |
| O5 | refusals: scheme without the items, offer in USD vs INR scheme, offer sent for sign-off, plain user | PASS |
| O6 | open + solve write nothing | PASS |
| X1 | decisions-board extension: new draft contract carries meal + phone; trail rows dated the start "Carried from …"; old contract's lines untouched | PASS |
| X2 | Renew form: prefill lines; HR changes meal, takes phone off → exactly that; another person's contract never lends lines; a plain new contract unchanged | PASS |
| X3 | the draft's lines can be changed before it runs | PASS |
| X4 | Make it permanent carries the lines (and no longer crashes — the `pb_contract_rules` signature fix) | PASS |
| X5 | read-only check lists the linked renewal (2 lost) and the by-dates one (phone lost), not the S8-D renewal; no write | PASS |
| X6 | golden: a renewal writes no payslip/payslip line; another contract's pay lines unchanged | PASS |
| PC1–3 | door opens Change job prefilled as a pay change, creates nothing; only `pb_job_change` carries the door (pb_pay files untouched); gate mirrors the server, fallback keeps the old form | PASS |

### 3.2 Suites vs baseline

Baseline = the same database with the PRISTINE `origin/19.1` copies of the five edited modules first on
the path, run BEFORE any edit (PRD-2). Every suite's module in `-u` (S5B-4).

| Run | Suites | Tests | Failed / errors |
|---|---|---|---|
| Baseline | pb_pay_scales 22, pb_pay_package 14, pb_job_change 23, pb_contract_lifecycle 6, pb_contract_rules 11, pb_hiring 688, pb_people_advanced 0 | 764 | **8 failed, 2 errors — all pb_hiring** |
| Branch | pb_pay_scales 36, pb_pay_package 22, pb_job_change 28, pb_contract_lifecycle 14, pb_contract_rules 11, pb_hiring 688 | 799 | **the identical 10 pb_hiring entries** (after one S8-A chip test was aligned with SC2, below) |

After the walk fixes the five Step 8 suites were run again (pb_pay_scales 36, pb_pay_package 22,
pb_job_change 28, pb_contract_lifecycle 14, pb_contract_rules 11 = 111 tests): 0 failed (two rise tests
were made robust against the walk's own DEMO rise in the same database — R6 "≥ 1 started", R11
company-scoped). pb_hiring was not re-run after the walk fixes: its only change is the offer template
inheritance, checked in the browser.

Baseline pb_hiring set (unchanged by the branch): `TestRecruitPrivacy.test_02b…`, `…test_08_the_resume_bank`
(errors); `TestClientReview.test_hiring_only_cannot_read_access_directory`,
`TestRecruitInterviewsP5.test_07b…`, `TestRecruitJoining.test_11…`, `TestRecruitPrivacy.test_02…`,
`TestRecruitPrivacyFiles.test_02…`, `TestRecruitStages.test_13…`, `TestRegistersP9.test_08…`,
`TestTheCover.test_t7…` (failures).

Deliberate test changes (SC2): S8-A `test_s8_board_people_and_placing` placed a person paid 6.0 M on step 2
(5.8 M) and expected "Bring to step 5,800,000" — a pay CUT the owner ruled out (SC2). Now: no stage door,
"Above step"; placed on step 3 (6.1 M) → "Bring to step 6,100,000". Merge seam M1 likewise ("Above step",
"Mark on step 2").

Static gates: `py_compile`, XML parse, `node --check` on every changed file; PO gate (`PoFileReader`):
pb_pay_scales vi/id 571 rows (340 code strings), pb_pay_package 83 (75), pb_job_change 327 (260),
pb_people_advanced vi 86 / id 12 (new file); placeholders identical; no vendor word in any msgstr.

### 3.3 Browser walk (local `s8d.localhost:8887`, DEMO data, `--max-cron-threads=0`)

* People › Pay › **Scales** (inside the People hub): "Raise the scale" → draft → 5%, reason → See who moves:
  5 move (e.g. DEMO Lan Bui 9,750,000 → 10,240,000, +595,350 a month incl. 21.5% employer insurance),
  1 above step (DEMO Dung Vo), 1 pinned (DEMO Khanh Do); cost VND 2,235,600 a month / 26,827,200 for
  twelve months → Send for approval → "Sent for approval — Administrator".
* Approvals inbox: the card "Pay scale rise · DEMO Retail store scale", facts (5 people, 5.4% average,
  cost a month) and the who-moves table; **"You cannot approve this one"** for the preparer
  (independence). Decided by two DEMO approvers → "Approved, starts later" (1 Dec 2026), new version
  "COMING" chip, strip "SR00057 · Approved, starts later · 5 people", "Take it back".
* Contracts **Renew** (DEMO Mai Fixed): "Pay lines carried over" meal 730,000 / phone 200,000; meal →
  800,000, phone taken off → create → new-hire approval → applied: draft contract with meal 800,000 only,
  trail "Carried from DEMO Mai fixed term" dated the new start.
* Hiring › DEMO Analyst › Details › Offer & joining › Offer: **Build from a total** → ₹12,00,000 a year →
  special allowance ₹28,200 exact → Use these figures → offer lines Basic + DA 50,000 / HRA 20,000 /
  Special 28,200 / Employer PF 1,800 (statutory) / joining bonus kept; "100,000 INR a month"; note line.
* Pay › **Changes** › New pay change: the line "Their new pay opens in Change job…", pick DEMO An Tran →
  Change job opens on "Pay change" with Pay ticked.
* Console: no errors on these screens; vi strings served (`/web/webclient/translations`).

Walk findings, fixed (in the commits after the item commits):
1. **The offer button's template inheritance pointed at the wrong template** (the offer panel is the
   board's `pb_hiring.RoleDetails` part) — the xpath failed and the WHOLE Hiring board stopped rendering.
   No Python test can see this (gotcha S8D-1). Fixed: inherit `RoleDetails`, anchor on the letter picker.
2. The offer card opened on the company's first scheme even when it could not split anything, with no way
   to pick another → now opens on the first scheme in the offer's money that has the items.
3. A fresh draft at 0% listed people as "above step" → nobody is listed until the table goes up.
4. A slow first open could make two drafts; unnamed drafts had no way out → one drawer at a time + "Remove
   this draft".
5. Layout: "How" on its own row; new amounts no longer wrap mid-figure; rows without a job title.

## 4. Contracts other phases rely on

* `pb.pay.scale.raise` (+ `.line`), process key `scaleraise`; `pb.pay.apply.pb_scale_raise_id`;
  `hr.contract.advantage.change.change_source = 'pay_scale'` rows dated the rise's start.
* Screen API on `pb.pay.scales`: `raise_list(scale_id)`, `raise_save(scale_id, vals, raise_id)`,
  `raise_read(raise_id)`, `raise_toggle(raise_id, contract_id, leave_out)`,
  `raise_act(raise_id, 'send'|'cancel'|'take_back'|'rework'|'remove')`.
* `pb.pay.package.offer_open(offer_id, config_id)`, `offer_solve(offer_id, …)`, `offer_use(offer_id, …)`;
  offer line fields `pb_item_code`, `pb_item_wage`, `pb_from_total`; offer `pb_total_config_id`,
  `pb_total_note`; JS card prop `offerId`. `pb.pay.package._solve_for(subject, …)` (subject = contract or
  offer).
* `pb.people.contract.wizard.create_contract(vals)` accepts `renew_from` (+ optional `lines`:
  `[{template_id, amount, drop}]`); `get_defaults(renew_from)` prefill `lines`.
* `pb_contract_lifecycle/tools/renewal_lost_pay_lines.sql` (read-only).

## 5. Deploy notes

**Tier: RISKY** (wage writes, contract pay lines, a new model + approval process). Order: after (or with)
the Step 8 go-live (Step 8 is LIVE since `38e1b524e` on `origin/19.1`; none of the six modules changed on 19.1 after this branch was cut, so the merge is clean).

* Modules (all five databases, never `abm`): `-u pb_pay_scales,pb_pay_package,pb_job_change,
  pb_contract_lifecycle,pb_people_advanced,pb_contract_rules`. If Step 8 is not live yet they are `-i`
  for the four S8 modules at these versions. `pb_pay_package` now depends on `pb_hiring` (installed on all
  five per the S8 deploy report — check again).
* `pb_pay_scales` 19.0.1.1.0 migration (`post-migrate`) seeds the "Pay scale rises" route for every
  company (HR lead → Finance approver, seats filled only where never set up); a fresh install does the same
  in the post-init hook. New quiet hourly job "Pay scales: write approved rises on their day" — reads one
  empty list until a rise is approved. Nothing else is written on install/upgrade; no data migration, no
  backfill, nothing sent.
* Asset purge + restart (JS/XML/SCSS in five modules).
* **Rehearsal on a rize clone should prove:** upgrade EXIT 0, no new ERROR; recompute a few runs old vs new
  = 0 differing payslips (W2M-4: count the ones that compute); contracts / pay lines / change rows / pay
  records identical after the upgrade; one `scaleraise` route per company; then on the clone only: a DEMO
  scale + DEMO people → a rise approved for today writes the wages + one dated change row each, a rise for
  a future date writes nothing until the job runs on that date; a DEMO renewal through the decisions board
  carries the pay lines; "Make it permanent" no longer fails.
* **EX1 read-only check, per database** (the file ships inside the module; postgres cannot enter `/odoo`,
  QFM-2):

  ```
  sudo cat /odoo/odoo-server/addons/pb_contract_lifecycle/tools/renewal_lost_pay_lines.sql \
    | sudo -u postgres psql -d <db> -P pager=off
  ```

  It opens a READ ONLY transaction and rolls back. Columns: company, person, current contract, its start,
  earlier contract, how linked (board / by dates), lines lost, the lines (code + amount). Hand the list to
  the owner; change nothing.
* Live look after deploy: People › Pay › Scales shows "Raise the scale" (pay team); Approval Matrix lists
  "Pay scale rises"; a draft offer shows "Build from a total"; Pay › Changes "New pay change" opens Change
  job; the Contracts Renew dialog lists the carried pay lines.

## 6. Owner questions (plain English)

1. **The yearly Pay Review still raises pay at once.** Single raises from Pay › Changes now go through
   Change job (one sign-off, start date honoured). The Pay Review round (many people at once) still writes
   the new pay when HR presses Apply, whatever start date it shows. Should the review round also wait for
   its start date? (Pay › Changes itself has no bulk action; nothing else changed there.)
2. **Renewed contracts and the Vietnam contract kind.** A renewal now copies the pay lines, but not the
   Vietnam "definite / indefinite" kind or the "trial agreement" flag. Copying the trial flag would be
   wrong (a renewal after a trial is not a trial). Should an extension copy the Vietnam contract kind?
   (Recommended: yes for an extension, never the trial flag.)
3. **The Contracts "Renew" button does not link the new contract to the old one** (only the contract
   decisions board does), so the fixed-term counting does not see renewals made with that button. Link
   them too? (It may make some people show the red "past the rule" warning.)
4. **A scale rise raises the wage only.** Allowances that belong to a grade (meal, housing set on the
   scale) are carried into the new table unchanged and are not raised on people's contracts. Should a rise
   also be able to raise grade allowances?
5. **Renewals already made that lost pay lines:** after go-live the deploy agent runs the read-only check
   on each database and sends the list. Then: add the missing lines by hand, or leave them?

## 7. Left for later

* A scale rise moves the WAGE only; a grade's allowances in the new version are copied unchanged and are
  not written onto contracts (a rise of allowances needs its own rule).
* "Show me one payslip" preview, Decision Room / Budget board forecast lines, group-currency roll-up of the
  cost (blueprint P3 extras).
* Automatic arrears: a past-dated rise is found by the Past-month re-work and paid through its own
  sign-off (C-6); nothing is paid back by itself.
* Time-based step-ups, wage floors (Step 1), employee "your place on the scale" page.
* The Contracts "Renew" button does not write the renewal link (`pb_renewed_from_id`) — only the decisions
  board does — so S8-B's fixed-term counting does not see Renew-button renewals (owner question 3).
* Renewals still do not copy `vietnam_contract_type` / `pb_payroll_contract_type` (owner question 2).

## 8. Gotchas → ledger

| # | Gotcha |
|---|---|
| S8D-1 | A `t-inherit` whose xpath matches nothing does not fail one button: the WHOLE screen stops rendering (OwlError "Element '<xpath …>' cannot be located"), and no Python test sees it. The Hiring offer panel is the `pb_hiring.RoleDetails` template (t-called by the board), not `pb_hiring.PbHiringBoard`. Open every inherited screen in the browser after an asset purge. |
| S8D-2 | An xpath on an attribute holding an arrow function (`@t-on-click="() => this.x()"`) is fragile; anchor on a class (`hasclass('pbhr-tpl')`). |
| S8D-3 | `hr.formula.config.currency_id` follows the scheme's `country_code`: a VN scheme created with USD reads VND. A "paid in another money" fixture needs another country (IN → INR). |
| S8D-4 | Writing `pb_paid_by_id` BEFORE creating the person's contract: the contract marks "Paid by" stale and `schemes_for_employee` re-resolves through the map (often nothing). Fixtures write "Paid by" after the contract. |
| S8D-5 | S8-B's `pb_contract_rules._build_new_contract(start, new_end)` dropped `contract_type`, so "Make it permanent" raised TypeError wherever `pb_contract_rules` is installed (fixed here). An override must keep every keyword the base method's callers pass. |
| S8D-6 | `--test-tags /module` runs only modules in `-u`; a walk seed committed into the test database is seen by later suite runs — make "nothing exists" assertions company-scoped. |
