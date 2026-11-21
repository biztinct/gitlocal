# WDGAP PR-C — Hold one person's pay (and pay them later) — report

Branch `wdgap-prc` (from `origin/19.1` at d3fba29ea). Not merged, not deployed, no live server touched.
Handover: `WDGAP_PR_C_HANDOVER.md`; facts: `WDGAP_PR1_FACTS.md`.

## 1. What was built

| Module | Version | What |
|---|---|---|
| `pb_pay_delivery` | 19.0.1.4.2 → **19.0.1.5.0** | The hold itself, and every money-out door re-checks it |
| `pb_payslip_review` | 19.0.1.4.0 → **19.0.1.5.0** | "Hold pay" / "Release hold" on the payslip review screen; "On hold" chip, count and filter; run flag |
| `pb_me_portal` | 19.0.3.5.3 → **19.0.3.5.4** | A held payslip is hidden from the employee (list, detail/PDF by id, tax sheet, home pay card) |

**The hold** (`pb_pay_delivery/models/pay_hold.py`, new): `hr.payslip` gains `pb_pay_hold` (indexed),
`pb_hold_reason`, `pb_hold_by`, `pb_hold_on`, `pb_hold_released_by`, `pb_hold_released_on`
(the five detail fields are `groups='om_hr_payroll.group_hr_payroll_user'`, see R5).
`action_pb_hold(reason)` (reason ≥ 6 characters, also a stored constraint) and
`action_pb_release_hold()`. Allowed for the pay team (`PAY_GROUPS`, same as the bank file), in the
payslip's own company, never on your own payslip, on a payslip that is calculated (draft with lines,
waiting, or done) and not paid and not in a released bank file. Each hold/release writes a note on the
payslip's history (author = the person) and one `biz.audit.entry` (the module's existing one-call
`pb.money.approval.mixin.audit`). `hr.payslip.run.pb_hold_summary()` (who, why, by whom, amount, per
currency) and a run `_approval_detail` that lists held people for the run's approver when anyone is held.

**Bank file** (`bank_export_wizard.py`, `bank_file.py`): a held payslip gets the reason "On hold" (first
in the list) and is left out; the left-out row also carries slip id, amount, reason, held by. New stored
fields on `pb.bank.file`: `slip_ids` (exactly which payslips the file pays — new relation table
`pb_bank_file_slip_rel`), `held_count`, `held_total`, `follow_up`. `prepare()` now never puts an
already-paid payslip in a file (`pb_unpaid_only`), and `_supersede_earlier` never replaces a file whose
money was released (and withdraws a release still waiting on a replaced file). `_control_total_matches_run`
compares the file with the run minus people on hold minus people an earlier released file paid; the
evidence note and the approval detail say how they add up:
"Bank file 7,500,000 = run 11,500,000 − 3,000,000 on hold (1 person) − 1,000,000 left out for other reasons".
The file's approval detail lists the held people first ("On hold · reason", "Held by …").

**Release** (`payment_release.py`): `prepare()` and `_approval_apply()` both refuse a file that carries
a payslip held after the file was prepared ("…Prepare the bank file again — it will leave them out — and
have it approved before releasing the money."). Apply stamps **only the payslips in the released file**
(see §4). A release withdrawn because its file was replaced goes back to "Being prepared".

**Payslip send-out** (`payslip_delivery.py`): a held payslip is never sent (not even by "Send to
everybody again"); its line reads "Not sent: pay on hold" and the batch counts `held_count`. Once the
hold is released the next send (the "Send the N that were held" button) sends it. The approval context
leaves held payslips out of the count and the stamp.

**Pay & deliver screen** (`pb_pay_delivery.py` + JS/XML/SCSS): an amber "N people's pay is on hold" group
above the left-out list (who, why, held by, when, amount, **Release hold**); the hero shows, per
currency, "on hold · paid · still to pay" (never added across currencies; the hero total is one
currency, others listed beside it); the bank-file card shows the total sentence, "Follow-up file" /
"Money released" tags, and a red note when someone in the file was held after it was prepared; after a
release, "N people released from hold can be paid now" + the button "Prepare a payment file for the N
people released from hold" (or "…not paid yet" when they were left out for other reasons); "Everybody who
can be paid has been paid" when nothing is left; earlier releases stay listed on the release card; the
send-out shows "N on hold, not sent", an "On hold" pill and "Send the N that were held". New RPC
`release_hold(run_id, slip_id)`.

**Payslip review screen**: an "On hold" count in the numbers line (grey at zero, amber otherwise,
click filters), an "On hold" filter, a quiet "On hold" chip on the person's card, and in the detail
pane: "Hold pay" → in-page reason box (≥ 6 characters, Esc cancels, Ctrl/⌘+Enter confirms) → amber
"Pay on hold" card with reason, by whom, when and "Release hold". Plain notes when the reader cannot act
(own pay; not in the pay team; already paid / in a released file / not calculated). RPCs `hold_slip`,
`release_slip_hold`, guarded on the field so the screen works without `pb_pay_delivery`.

**Run flag** (`pb_payslip_review/models/review_flags.py`, one separate block `_pb_review_hold_flags`
appended after the query, not inside it): a held payslip is flagged `kind='hold'`, reason "Pay on hold"
(appended "· Pay on hold" when already flagged), so the Run lens's Review step and Payslip review both
count it under "Need review". The loans builder can clone the same pattern in its own override.

Translations: 66 new + 2 extended entries in `pb_pay_delivery/i18n/vi_VN.po`, 21 new in
`pb_payslip_review/i18n/vi_VN.po` (neither module has an `id_ID.po`). Every entry has the module line,
the `odoo-python`/`odoo-javascript` marker and a `code:addons/…:0` occurrence; terms were taken with the
same extractors Odoo uses (babel python/javascript, `babel_extract_qweb`), and a re-check lists 0 new
term without a translation.

## 2. Tests

Local copies of `upd_p6_t_tpl` (one at a time, dropped after each run), `-u pb_updates,pb_pay_delivery,
pb_payslip_review,pb_me_portal`, tags `/pb_pay_delivery,/pb_payslip_review,/pb_me_portal`.
Baseline = the same run with the three modules taken from `origin/19.1` (a copy put first on the path).

| Suite | Baseline (origin/19.1) | PR-C |
|---|---|---|
| pb_pay_delivery | 29 tests, 0 failing | 45 tests, 0 failing (the old ones plus 12 new test methods; counts as Odoo's stats line prints them) |
| pb_payslip_review | 11 tests, 0 failing | 11 tests, 0 failing |
| pb_me_portal | 125 tests, 5 failing | 125 tests, the same 5 failing |

The 5 pb_me_portal failures exist on unchanged code and are unrelated (`test_05_grid`, `test_06_font`,
`test_12_vi_po_parses_and_covers_the_new_words`, `test_01_profile_change_flow_and_audit`,
`test_t1_7_portal_only_person_is_bounced_to_my`); the failure set is identical.

New file `pb_pay_delivery/tests/test_wdgap_prc_hold.py` (tag `wdgap_prc`):

| # | Case | Test | Result |
|---|---|---|---|
| 1 | Reason required (≥ 6, also stored constraint); by/on; release by/on; history notes by the person; audit entries; hold twice / release twice refused | `test_01` | PASS |
| 1b | Run flag `kind='hold'`; `pb_hold_summary`; run approval detail lists the held person; review screen `get_slip_detail` / `hold_slip` / `release_slip_hold`; "On hold" count | `test_01b` | PASS |
| 2 | Held slip left out with "On hold"; not in the file's bytes; `slip_ids`; control total = run − held (matches once nobody else is left out); evidence note + sentence; file approval detail lists the held person; Pay & deliver payload | `test_02`, `test_02c` (everybody held → plain refusal) | PASS |
| 2 / R3 | Golden: nobody held → file bytes (sha256), control total, rows, left-out list, control-total check, screen preview, send-out list, release amount/people and the paid stamps of the people in the file are identical to `origin/19.1` on the same fixture (recorded by running the same test on the old code) | `TestPrcGolden.test_r3_…` | PASS |
| 3 | Release stamps only the file's people; held person and the person left out for bank details stay unpaid | `test_03` | PASS |
| 4 | Send-out skips held (also with "send to everybody again"), counts it; employee's own list and home pay card hide it; after release it is visible and "send the 1 that was held" sends exactly one | `test_04` | PASS |
| 5 | Race: hold after the file was approved → release refused with "Prepare the bank file again"; release asked before the hold → refused at the moment it is carried out, nobody stamped; prepare again → old file replaced, its waiting release withdrawn, new file without the held person releases normally | `test_05` | PASS |
| 6 | Cannot hold a paid payslip, one in a released file, a rejected one, or one not calculated | `test_06` | PASS |
| 7 | Follow-up: offered after release, "from hold"; contains only the released person; first released file untouched (not replaced, stamps and references unchanged); own approval and release; a second follow-up try replaces only the follow-up; identity released files + held + other left out = run total (before and after); nothing left → no new file, screen says so | `test_07` | PASS |
| 8 | Two currencies in one run: totals per currency, hero in one currency, held per currency | `test_08` | PASS |
| 9 | Plain employee and payroll officer (no pay role) refused; employee cannot read hold reason/by/on through the ORM; never on your own payslip (hold or release), payload says why; another company's payslip refused | `test_09` | PASS |
| 10 | Existing suites — failure set equals baseline | above | PASS |
| 11 | Browser walk | §3 | PASS, except "send the held payslip" (no PDF tool on this Mac; covered by test 4) |
| 12 | Static gates: `py_compile` of every changed Python file; `lxml` parse of both OWL templates; PO gate (`PoFileReader`) on both `.po` (0 failures; no "Odoo" in any msgstr); no "Odoo" in any added user-visible string | — | PASS |

## 3. Browser walk

Local copy `wdgap_prc_walk` (from `upd_p6_t_tpl`, seeded by `scratchpad/prc/walk_seed.py`: four DEMO
people, run "DEMO June 2026" approved, ₫/$ 46,000,000; bank file and release routes set to "no approval
needed" so one login can walk it), server with `--max-cron-threads=0`, Claude in Chrome. Dropped
afterwards.

1. Payslip review, before: numbers line "0 On hold" in grey; detail pane shows "Hold pay" + its one-line
   explanation. Console clean.
2. Hold DEMO Binh Tran: the reason box opens with the cursor in it, "Hold pay" stays disabled under 6
   characters; after confirming: toast, "1 Need review" and "1 On hold" turn amber, the card shows "Pay on
   hold" and an "On hold" chip, the detail shows the amber card (reason, "Held by Administrator · 14 Nov
   2026", "Release hold"). Found: the existing "!" review dot overlapped the amount on a flagged card —
   fixed (`:has(.psr-flagdot)` padding).
3. Pay & deliver: hero "$ 6,500,000 on hold · $ 39,500,000 still to pay"; the amber "1 person's pay is on
   hold" group with reason, held by, date, amount and "Release hold"; "3 payslips ready"; payslips lane
   "3 recipients · 1 on hold, not sent".
4. Prepare the file: "3 payments · $ 39,500,000", "Bank file 39,500,000 = run 46,000,000 − 6,500,000 on
   hold (1 person)". Release with a reference: hero "$ 39,500,000 paid · $ 0 still to pay", "Everybody who
   can be paid has been paid — Release a hold above to pay that person with a follow-up file."
5. Send payslips: the local Mac has no PDF tool, so the send-out request stopped with the PDF error (same
   on unchanged code); the server tests cover sending, skipping the held payslip and "Send the 1 that
   was held" (test 4).
6. Release the hold from Pay & deliver: the group disappears, "1 person released from hold can be paid
   now", button "Prepare a payment file for the 1 person released from hold". Prepared: "1 payments · $
   6,500,000 · Bank file 6,500,000 = run 46,000,000 − 39,500,000 paid by an earlier file (3 people)",
   "Follow-up file" tag; the first release stays listed. Released: two "Money released" rows, run reads
   "Paid", "$ 46,000,000 paid · $ 0 still to pay". Found: the follow-up's reference box was pre-filled
   with the first transfer's reference — fixed (cleared for a file with no release yet).
7. Payslip review on a paid person: "DEMO An Nguyen has already been paid (2026-11-14), so this pay can
   no longer be held." No console errors at any step (re-checked after the two fixes, assets rebuilt).

## 4. Who gets marked "paid" on release — what changed (scope item 4)

**Before:** approving a payment release stamped `pb_paid_on` + the bank reference on **every finished
payslip of the run** — including people the bank file had left out (invalid account, unknown bank,
missing holder, no net pay). They read "Paid" although the bank was never asked to pay them, and the
run read "Paid" as a whole.

**Now:** only the payslips that are **rows of the released file** are stamped. A person on hold is
never stamped. A person left out for bank details is **no longer stamped** — this is a deliberate change
(I judged the old behaviour plainly a bug: it wrote a bank reference on money that did not go through
the bank). What it means:
- they stay "Not paid yet" (Payslip review's Paid filter, the Pay & deliver totals "still to pay");
- the run stays "Approved, not paid" on the Pay runs board until they are paid;
- once their bank details are fixed, Pay & deliver offers "Prepare a payment file for the N people not
  paid yet" — the same follow-up file as for a released hold.
- Files made before this change carry no list of their payslips; they are read back as "done payslips
  minus the people in the file's left-out list", which is exactly what they contained.

There is **no "mark as paid another way" button** (cash, cheque). If a customer pays some people outside
the bank file, their run will now never read "Paid" — see owner question 2.

Awards queued into the run (`pb.oneoff.feed.mark_paid_for_run`) are still marked paid per RUN on the
first release (unchanged, `pb_comp_ben` out of scope): an award to a held person is marked paid with
the first file. Follow-up below.

## 5. Self-review against the rails

| Rail | Result |
|---|---|
| R1 held never paid / in a file / delivered | Every door checks the flag at the moment it acts: file generation (`_row_sources`), release prepare AND apply (`_pb_refuse_held`), stamp filter, send-out loop. The race is test 5. PASS |
| R2 paid or released cannot be held | `_pb_hold_blocker` (paid stamp, or in any released file of the run). Test 6. PASS |
| R3 nobody not held is dropped | Golden test against the old code (bytes, totals, lists, stamps of the file's people). The only difference is §4 (people left out for bank details, deliberately). PASS |
| R4 follow-up | Never contains a paid payslip (`pb_unpaid_only`); never replaces a released file; identity tested before and after. PASS |
| R5 rights / multi-company | Pay team only (AccessError otherwise, also the RPCs); own payslip refused both ways; other company refused; employee portal hides the payslip everywhere it is read (list, page/PDF by id, tax sheet, home card); reason/by/on are payroll-only fields. **Recommendation:** no second person for placing a hold (it only delays money and is fully audited); see question 1 for lifting it. PASS |
| R6 demo world | `pb_demo` has no Pay & deliver override; the walk ran with no holds first and the screen was unchanged (golden covers the server side). PASS |
| R7 white-label, plain words, quiet, Lucide, vi, versions | No product/vendor name in any new string; amber only where someone must act (release a hold), grey otherwise; Lucide icons from the shared set (`pause`, `play`, `checkCircle`, `clock`, `repeat`); vi entries; three version bumps. PASS |

Design bar ("extreme WOW, best in class"): the hero moment is the one sentence that makes the bank file
and the run add up ("Bank file … = run … − … on hold (2 people)") and the per-currency "on hold · paid ·
still to pay" line; zero dead-ends (every refusal names its reason and next step; "Everybody left to pay
is on hold", "Everybody who can be paid has been paid"); keyboard on the reason box. Not done: bulk hold
of several people at once (not asked; the server action takes several payslips).

## 6. Deviations

- Pay & deliver shows the "On hold" group always (not only behind the "left out — view" toggle), because
  it is the one place to release a hold.
- `validation.excluded` in the Pay & deliver payload now lists only people left out for bank details;
  held people are in `holds` (the "left out" count still counts both). After a release the preview is of
  the NEXT file (paid people are not in it).
- Hold-detail fields are payroll-only (`groups=`) — added because an employee login can read its own
  payslip through the ORM (ledger PRC-W1).

## 7. Follow-ups

1. Awards (`pb_comp_ben` `mark_paid_for_run`) are marked paid per run, not per person; a held person's
   award reads paid with the first release. Make it take the released payslips.
2. "Mark as paid another way" for people paid outside the bank file (question 2).
3. Bulk "Hold pay" for several selected payslips (the server already accepts several).
4. A route fact "people on hold" so a business can send files with holds to a second approver.
5. If a draft run is recalculated by deleting and recreating payslips, a hold on a draft payslip is lost
   (holds are normally placed after calculation; the payslip history keeps the note).

## 8. Owner questions (plain words)

1. **Should lifting a hold need a second person?** Today anyone in the pay team except the held person
   can lift it, and it is recorded. A second person is safer but slower when the reason is cleared.
2. **People the bank file leaves out (for example missing bank details) are no longer marked "paid" when
   the money is released.** If some customers pay those people in cash, do you want a "Mark as paid
   another way" button, or should they always be paid through a follow-up bank file?

## 9. Deploy notes (RISKY tier — money-out path, new stored fields)

- New stored columns on `hr_payslip` (6) and `pb_bank_file` (3), new table `pb_bank_file_slip_rel`, new
  stored count on `pb_payslip_delivery_batch`, new selection value on `pb_payslip_delivery.state`. No
  backfill: existing files are read back from their left-out list (§4).
- Upgrade `pb_pay_delivery`, `pb_payslip_review`, `pb_me_portal` on all five databases; backups and the
  clone rehearsal first; asset purge (JS/XML/SCSS changed in two modules).
- Check after: Pay & deliver on a paid run (payobook demo) — same totals, no hold group, "Everybody who can
  be paid has been paid"; Payslip review shows "0 On hold" in grey.
- PO gate on the box for the two `.po` files.

## 10. New gotchas → ledger

PRC-W1 (employee can read own payslip via ORM), PRC-W2 (old release stamped everybody), PRC-W3 (template
has no pay run; walk seed) added to `WDGAP_LEDGER.md`.
