# WDGAP W3-C report — IM2 (movers not asked for papers) + BG1 (bank-gap copy batches)

Branch `wdgap-w3c` (from `origin/19.1`). Builder = implementer + tester + self-reviewer.

| Task | Status |
|---|---|
| **IM2** (code, `pb_hiring_internal` 19.0.1.1.0 → 19.0.1.2.0) | **DONE** — built, tested, not deployed (rides the next go-live) |
| **One notice per batch** (code, `pb_bank_ocr` 19.0.1.4.0 → 19.0.1.5.0) | **DONE** — built, tested, not deployed (rides the wave-3 go-live). See "Follow-up: one notice per batch" at the end. |
| **BG1 under owner rulings BG2–BG4** | Script + lists updated (names must match; Rize leaves out banks the bank file does not know). **Live batches NOT created** — BG4: only after the wave-3 go-live's DONE line. |
| **BG1** (data task on live `rize` + `sudima`) | **HELD before live (gate 3: "only if the rehearsal is clean") — nothing changed on either live database; no batch exists on either site (re-checked 2026-11-17 12:59 UTC).** The coordinator's later "resume, create the batches" messages repeated the original brief and came before these findings were reported, so the hold stands until somebody who has read §2.5 says which option to run. Gate 1 met, gate 2 (rehearsal) run in full on both sites and the mechanics passed, but the rehearsal found two things that break the brief's own rules: (1) the product's own path is NOT silent at this size; (2) on sudima 230 of the 615 accounts are in somebody else's name. Both need a decision / a small code change first (§2.6). |

---

## 1. IM2 — a person who already works here is not asked for papers at offer time

**Ruling IM2 (2026-11-17):** internal movers are not asked for papers at offer time; HR can
still request by hand.

**Seam (no STOP needed):** the automatic "ask for the papers" lives in `pb_hiring`, not
`pb_lifecycle`: `pb.hiring.offer._docreq_fire(moment)` (`pb_hiring/models/requests_p3.py`,
called from `draft_for` — "when the offer is drafted" / "when the check is clear" —, from the
background check's `_after_answer`, and from `record_decision('accepted')`). The company's
moment is the setting `pb_hiring.docreq_trigger`. HR's by-hand ask is
`pb.hiring.offer.action_request_documents()` (`pb_hiring/models/offer.py`) — untouched. Same
pattern as IM1 (override from `pb_hiring_internal`, `_pbhi_internal()` decides).

**What changed** (only `pb_hiring_internal/`, by inheritance; no `pb_hiring` or `pb_lifecycle`
file edited):

| File | Change |
|---|---|
| `models/offer.py` (after `_lay_out_prejoin`) | `_docreq_fire(moment)`: internal candidate → `False` (nobody asked, at any of the three moments); otherwise `super()`. `_documents_ready()`: internal candidate with NO papers request → `(True, '')`, so the offer panel does not nag and the chatter never says "sent … before every document was in"; once HR asks by hand, `super()` (the usual "N documents still missing"). |
| `models/staff_moves.py` (`PbHiringFacadeInternal`) | `_journey(req)` after `super()`: for an internal candidate with no papers request the role drawer's "Documents" chip reads **"Already works here"** (tone done) instead of "Not asked for yet"; after a by-hand ask it counts papers as usual. |
| `i18n/vi_VN.po`, `i18n/id_ID.po` | "Already works here" → "Đã làm việc tại công ty" / "Sudah bekerja di sini" (odoo-python marker + occurrence; PO gate test B42 covers it). |
| `__manifest__.py` | 19.0.1.2.0; one description bullet ("No papers asked of a mover"). |
| `tests/test_wdgap_w3c_im2_papers.py` (new), `tests/__init__.py` | IM2-1 … IM2-6 below. |

External candidates: every override calls `super()` unless the candidate is internal
(`hr.applicant.pb_internal` + `employee_id`, the S6-B rule) — proven by the "outsider
unchanged" tests at each moment.

### 1.1 Tests (`--test-tags /pb_hiring_internal`, local `wdgap_w3c_t`)

| # | Test | Result |
|---|---|---|
| IM2-1 | moment "when the offer is drafted": mover (with an email address, so only the ruling can stop it) → no papers request made at all | PASS |
| IM2-1b | same moment, outside candidate → asked, as before | PASS |
| IM2-2 | "when the check is clear": mover not asked at drafting nor when the check clears later | PASS |
| IM2-2b | same, outside candidate → asked on the clear check | PASS |
| IM2-3 | "when the candidate accepts": mover → nothing missing, the "Offer sent" note has no "before every document was in", accepting asks nothing | PASS |
| IM2-3b | same, outside candidate → "Nobody has asked…" before, asked on acceptance | PASS |
| IM2-4 | HR asks a mover by hand → request goes out; from then on missing papers count again | PASS |
| IM2-5 | role drawer "Documents" chip: mover "Already works here" (done); after a hand ask it counts papers | PASS |
| IM2-5b | outside candidate's chip unchanged ("Not asked for yet", todo) | PASS |
| IM2-6 | the chip's words have vi + id translations, no vendor word | PASS |

### 1.2 Suites — baseline recorded BEFORE any edit, same database

Run: `-u pb_hiring,pb_hiring_internal --test-tags /pb_hiring,/pb_hiring_internal` on
`wdgap_w3c_t` (copy of `upd_p6_t_tpl`, the 40 custom modules behind the branch `-u`,
`pb_hiring_internal` + `pb_job_change` installed as on live).

| Suite | Before the edit | After the edit |
|---|---|---|
| `pb_hiring` + `pb_hiring_internal` | 573 tests, 8 failed + 2 errors | 583 tests (+10 IM2), 8 failed + 2 errors — **the same 10** |

The 10 (all `pb_hiring`, identical to the S6-B recorded baseline): TestClientReview.test_hiring_only_cannot_read_access_directory,
TestRecruitInterviewsP5.test_07b, TestRecruitJoining.test_11, TestRecruitPrivacy.test_02 / 02b / 08,
TestRecruitPrivacyFiles.test_02, TestRecruitStages.test_13, TestRegistersP9.test_08,
TestTheCover.test_t7. Every `pb_hiring_internal` test passes (IM1, C-1, C-2, static/PO gate
B40–B43 included). Local database dropped at the end.

No browser walk: IM2 adds no screen; the only visible change is one chip word on the existing
role drawer (proven by IM2-5 through the drawer's own server payload).

---

## 2. BG1 — copy recorded bank accounts into the bank-file fields (rize, sudima)

### 2.1 Gate 1 — Step 6 go-live

`/opt/deploy-notes.md`: `2026-11-16 19:56 UTC | WDGAP S6 (Claude WDGAP) | DONE` (closes the
19:44 START); no open START when I began (a Codex release started 20:14 and finished 20:24
UTC while I was rehearsing — my work during that window was read-only on live and on my own
copies; its change, `pb_hr_payroll_vietnam` 19.0.1.2.3, touches no bank field — checked in
the diff). Gate 1 met; no polling was needed.

### 2.2 How the batch is built (product methods only, no code change, no raw SQL)

Script `docs/handovers/wdgap/w3c_bg1/bg1_batch.py` (odoo shell, `MODE`/`NAME_RULE` prepended):
1. Re-runs the read-only check `hr.employee.pb_bank_store_check()` (CURRENT state) and takes
   its "accounts only" rows.
2. Keeps a person ONLY when: active; exactly ONE bank account on record (archived ones
   counted); all four bank-file fields empty; the account is active and on the person's own
   work contact; number 6–19 digits and not damaged; the account has a bank name; the number
   is held by nobody else (either store, whole database); `res.bank` name lookup returns this
   very bank (so approving can never re-point the account); a holder name with no stray
   spaces (so approving can never rewrite it); no other bank change waiting; and (new, see
   §2.6) the holder-name rule. Everybody else is listed with a plain reason.
3. For each person kept: `pb.bank.change.request._pb_hold_from_import(employee, vals, hold)`
   — the BK2 import path — with `vals` = exactly the account on record (number, bank name,
   holder; branch blank, because an account has no branch and the product's own
   account→bank-file copy in `pb_records._write_bank` clears the branch too) and ONE `Hold`
   for the whole site: key `bank-gap-copy,<db>,2026-11-17`, label
   **"Bank details already on record — copy to the bank file (N people)"**. That method makes
   the waiting change (`pb_origin='import'`, no document), runs the bank checks and sends it
   on the `records_bank` route ("Bank details — a second person") as each database has it.
4. Checks inside the same transaction (fingerprint of both bank stores + every bank-account row
   before/after; every new change in "waiting"; none left as a draft) and commits only if all
   pass (`MODE='run'`). Idempotent: a person with a waiting change from this batch is skipped,
   so a second run creates nothing.

**Proposer identity: the system's own service user (`base.user_root`, id 1).** It is archived
(never signs in, never gets messages), it is on no approval route, and it is not a bank
approver on either site, so EVERY approver can approve the batch. It shows as "Rize" on rize
and "Payobook" on sudima (its debranded display name). Not the administrator: on rize the
administrator login (id 2) IS one of the four named bank approvers; on sudima id 2 is one of
the two people the route seats.

**Independence: as each database has it, nothing invented.** Both routes have
`independent: True`, "repeated: different", one step "A second person".
- rize: named people — ash@biztinct.com, debalina@rize.farm, thao@rize.farm, wildan@rize.farm.
  Thao and Wildan are themselves in the batch: the product never seats a person on their own
  bank change, so 187 rows each (the other three can approve theirs).
- sudima: the "finance" role → seats hr@sudima.local and ash@biztinct.com.

### 2.3 Counts (rehearsal, built from the state of 2026-11-16 20:06 UTC rize / 20:17 UTC sudima)

Re-checked read-only on live 2026-11-17 12:59 UTC: unchanged (rize 198 "account only", 188
active; sudima 642), **no bank-copy batch exists on either site**, no bank change waiting.

| | rize | sudima |
|---|---|---|
| Read-only check: account on record, bank-file fields empty | 198 | 642 |
| Archived people — skipped, listed | 10 | 0 |
| Left out: no bank name on the account | 0 | 11 |
| Left out: the same account number is on record for another person (8 pairs) | 0 | 16 |
| More than one account / other ambiguity | 0 | 0 |
| **Waiting changes the batch makes (any holder name)** | **188** | **615** |
| …of which the account holder's name matches the person | 183 | 358 |
| …close, not the same | 3 | 27 |
| …**in another person's name** | 2 | **230** |
| …bank the bank file does not recognise (copied, but the bank file still leaves them out as "unknown bank") | 126 (Indonesian banks: BCA 70, Mandiri 25, BRI 15, BNI 7, DBS 2, Panin 1; plus a few Vietnamese spellings) | 0 |

### 2.4 Rehearsal proof (fresh copies of both live databases on the server)

Copies `bg1w3c_rize`, `bg1w3c_sudima`: restored with the database marked as a template first
(invisible to the live job runner), every job and mail server switched off, real counts
asserted (311 / 653 employees, identical table, constraint and index counts to live). Both
copies dropped (`dropdb --force`); no file folder was created; dumps deleted.

| Check | rize | sudima |
|---|---|---|
| Batch run | 188 waiting, 0 drafts, 27 s | 615 waiting, 0 drafts, 91 s |
| Nothing changed by the batch (checksums of employees, bank accounts, contracts, contract versions, payslips, lines, runs, contacts, banks — before vs after) | identical | identical |
| Approver sees ONE row on Compliance › Bank | "Bank details already on record — copy to the bank file (188 people) · 188 waiting" (as debalina) | "… (615 people) · 615 waiting" (as hr@sudima.local) |
| "Approve all in this file" (the button's own call `pb.bank.ocr.approve_import`) | "188 approved." | "615 approved." |
| (a) both bank stores agree for every included person | 188 / 188 | 615 / 615 |
| (b) the read-only check afterwards lists only the left-out people | yes — 10 (the archived) | yes — 27 |
| (c) nothing else changed: only the four bank-file fields (+ the write stamp) of included people; bank accounts, contracts, contract versions, payslips, lines, runs, contacts, banks identical | yes (employee rows identical with those 4 fields excluded) | yes |
| History rows ("approved by") | 188 | 615 |
| (d) bank file | no run is finished on rize (every payslip is a draft), so no real file; the bank file's own row check on every run: "Rize Vietnam Payroll · October 2026" **0 → 54 of 63** people in the file (9 still out: 6 unknown bank, 3 no account at all); TEST VN Aug **0 → 45 of 60**; TEST ID Aug **0 → 4 of 122** (118 "unknown bank" — the bank file is the Vietnam one) | sudima has no pay run at all — not testable |

### 2.5 Why BG1 is held (the two findings)

**(1) Not silent — the product path sends one notice PER PERSON to EVERY approver.** Each
waiting change is its own approval; the approvals engine queues "Your approval is needed" for
every open seat, and its job (`biz_approval_workflow.cron_outbox`, ON on both sites) turns each
into a message + a to-do. Measured on the copies by running that job once:

| | rize | sudima |
|---|---|---|
| To-dos created | 750 (188 + 188 + 187 + 187) | 1,230 (615 + 615) |
| Bell notifications | 1,500 | 2,460 |
| Emails queued (all approvers are set to "by email"; no mail server, so they would fail — nothing leaves) | 1,500 | 2,460 |

The to-dos stay after approval (the engine never closes them — on live rize today 26 of 103
finished approvals still carry open to-dos), and if nobody approves within 2 working days the
reminder job adds the same number again, then escalations. The brief says the only visible
effect may be the one batch row and the approvers' inbox row, so I did not run it on live.
This is also how BK2 behaves for a large pay data file import.

**Small code change that fixes it** (rides the next go-live; `pb_bank_ocr`, by inheritance,
~40 lines + tests + vi/id): override `biz.approval.outbox._queue` in a new
`pb_bank_ocr/models/pb_bank_import_quiet.py` — when the request's record is a
`pb.bank.change.request` with `pb_origin == 'import'` and a `pb_import_key`, and `kind` is
`your_turn`/`reminder`/`escalation`/`approved`, replace the dedupe key with
`'bankimport-%s-%s-%s' % (kind, pb_import_key, user.id)` (the existing dedupe check then keeps
exactly ONE row per approver per batch) and put `bank_import_label` + the waiting count in the
payload; override `_body()` so that row reads "N bank changes from "<label>" are waiting for
you. Approve them on Compliance › Bank." `returned` / `rejected` stay per row. Nothing in
`pb_bank_ocr` or `pb_records` uses the single-notice "already told" question, so no area
message starts sending instead. Tests: a 3-person batch → 1 outbox row per approver per kind;
a 1-person staff-screen change → unchanged; approve-all still works; BK2 suite unchanged.

**(2) Sudima: 230 of the 615 accounts are in another person's name.** 189 of those holder
names are the names of OTHER Sudima workers, almost always a neighbouring record (employee
number ±1 to ±4 for 166 of them; no two people simply swapped). That pattern looks like the
account list was shifted by a few rows when it was loaded. Copying those accounts into the
bank file would pay those people's wages into a colleague's account. The approver would see a
red "name does not match" on each, but 230 one-by-one send-backs is not a safe way to catch
it. The script now has a holder-name rule (`NAME_RULE`, default `'match_only'` — only names
that match, the bank check's own green band); with it, sudima would be 358 people and rize
183; the rest are listed for HR.

### 2.6 What happens next (nothing is pending on live)

1. Owner decides the two questions in §4.
2. The quiet-notice change (§2.5 (1)) is built and goes live with the next go-live.
3. Then: re-rehearse on fresh copies (the script and copy kit are in
   `docs/handovers/wdgap/w3c_bg1/`; also test the undo there), dumps of live rize and sudima
   into `/odoo/backups/`, START note, `MODE='run'` on rize then sudima, check the waiting
   counts and that no bank store moved, DONE note with the undo.

**Undo, once a batch exists (to be proven on the next rehearsal copy):** in an odoo shell on
the site, `KEY = 'bank-gap-copy,<db>,2026-11-17'`, then for every
`env['pb.bank.change.request'].sudo().search([('pb_import_key', '=', KEY), ('state', 'in',
('hr_review', 'finance_review'))])`: `env['biz.approval.engine'].sudo().cancel(
r._chain_open_request(), 'Bank-gap copy withdrawn')` (the product's own withdraw — the same
call My Payobook's "take it back" makes; the change returns to draft, nothing is written),
`env.cr.commit()`. An approver can also send back single rows from the Approvals inbox.

### 2.7 What the approver will see and press (once it runs)

Compliance › Bank → a box "Bank changes from imports, waiting for you" with one row
**"Bank details already on record — copy to the bank file (N people) · N waiting"** and a
button **"Approve all in this file"** → "Approve all of them?" → **"Yes, approve all"** →
"N approved." Each change can be opened from Approvals to look at it or send it back. Nothing
changes where anyone is paid until then. (The box title says "imports" and the button says
"in this file" — the product's existing words for BK2; the row label explains what it is. The
label is a stored text, English only: that field is not translatable.)

### 2.8 Lists (never committed)

`/Users/adity/Documents/GitHub/gitlocal/outputs/wdgap-bank-gap-2026-11-17/`:
`rize-included.csv`, `rize-left-out.csv`, `sudima-included.csv`, `sudima-left-out.csv` (account
numbers masked to the last 4; columns include the name check the approver would see and
whether the bank file knows the bank), and `rehearsal/` (summaries, checksums, the bank-file
row check). The lists are from the rehearsal state; the live run rebuilds them from the state
at that moment.

### 2.9 What I touched on the server

Read-only odoo shells on live `rize`/`sudima` (every one rolled back; the bank-file row check
used an unsaved wizard), `pg_dump` of each (read-only) to make the copies, my own folder
`/tmp/bg1w3c`, the two copies (dropped), and one NOTE line in `/opt/deploy-notes.md` (20:32
UTC: held, nothing changed). No deploy, no restart, no rsync, no write to any live database.

---

## 3. Gotchas (ledger rows)

| # | Gotcha |
|---|---|
| W3C-1 | A copy of a live database restored with `pg_restore --single-transaction` fails on this server ("out of shared memory … max_locks_per_transaction"). Restore without it; keep the copy hidden from the live job runner by marking the database `IS_TEMPLATE true` BEFORE the restore (and `false` again before `dropdb --force`). |
| W3C-2 | `make_copy.sh … | tail` ended silently right after the restore twice although the copy was complete; check table/constraint/index counts against live and switch the jobs off by hand. |
| W3C-3 | Do NOT dry-run a batch on a LIVE database "and roll back": record numbers come from database sequences, which a rollback does not give back. Dry runs belong on copies. |
| W3C-4 | The approvals engine notifies per approval request: a 600-row bank batch (or BK2 file import) gives each approver 600 to-dos and 1,200 queued emails, and the engine never closes to-dos after a decision. |
| W3C-5 | `recordset.mapped('user_id.login')` de-duplicates — never count per user with it. |
| W3C-6 | The worktree guard refuses shell lines containing `$(…)`/pipes with paths containing "git" (`gitlocal`): put them in a scratchpad script (ledger PRA-5 again). |

## 4. Owner questions (plain words)

1. **Sudima — 230 people's bank account is in someone else's name**, and for 189 of them that
   name is another Sudima worker, usually the person next to them in the list. It looks like
   the account list was shifted when it was loaded. Copy only the 358 people whose name
   matches their account (and give HR the list of the other 257 to check with Sudima), or
   copy all 615 and let the approver judge each red name?
2. **Rize — 126 of the 188 bank accounts are at Indonesian banks** (BCA, Mandiri, BRI, BNI…).
   The Vietnam bank file does not know those banks, so after the copy those people are still
   left out of the bank file ("unknown bank"). Copy them anyway (the two records then agree),
   or leave them out?
3. **Approvers would get one to-do and two emails per person** (rize 750 to-dos, sudima 1,230)
   with the product as it is. Build the small change first so each approver gets ONE notice
   per batch (recommended), or go ahead as it is?

## 5. Left for later

- BG1 live run (after §4 and the quiet-notice change) — scripts ready.
- The engine never closes the other approvers' to-dos after a decision (26 of 103 finished
  approvals on rize carry open to-dos today) — an engine fix, outside this lane.
- Payobook demo's reverse gap (4,500 people) — not in scope (owner: not unless asked).

---

## Follow-up: one notice per batch (coordinator, 2026-11-18)

**Asked:** when bank changes are held as a batch (a pay data file or the old Vietnam employee
import — BK2 —, a connected system's records refresh, or the BG1 copy batch), each approver gets
ONE to-do and at most ONE email per batch, naming the count and pointing to Compliance › Bank; the
to-do is marked done when the batch is fully decided; single bank changes exactly as today.

**Built** in `pb_bank_ocr` (the module that owns the bank hold path), by inheritance — new file
`pb_bank_ocr/models/pb_bank_batch_notice.py`; no `biz_approval_workflow`, `pb_records`,
`pb_lifecycle`, `pb_pack_*` or `pb_me_portal` file edited. `pb_bank_ocr` 19.0.1.4.0 → 19.0.1.5.0.
- `biz.approval.outbox._queue` (inherited): for an approval whose record is a bank change with
  `pb_origin == 'import'` and a `pb_import_key`, "Your approval is needed" / "Still waiting" /
  "Overdue" get the dedupe key `bankbatch-<kind>-<batch key>-<user>` — the outbox's own
  "already queued" check then keeps ONE row per approver per batch. The proposer's "approved"
  is queued only when nothing in the batch is waiting any more (one "decided" message per batch).
  Two new columns on the outbox: `pb_bank_batch_key`, `pb_bank_activity_id`.
- `biz.approval.outbox._deliver` (inherited, batch rows only): ONE message to the approver (their
  one email when they read by email) "N bank changes from "<batch>" are waiting for you. Open
  Compliance › Bank and press "Approve all in this file"…" with a link to the bank screen, and ONE
  to-do "N bank changes waiting for your approval: <batch>", created without the separate "you
  have been assigned" email. A later reminder/escalation for somebody who already has the batch's
  to-do only refreshes it (no second to-do, no second email). A notice still queued when the batch
  is already decided is not delivered.
- `pb.bank.change.request.write` (inherited): when a batch change's status moves (approved,
  turned down, sent back, withdrawn), the batch's to-dos are refreshed — the count still waiting,
  or marked done when nothing is waiting.
- Single bank changes (My Payobook, HR's bank screen, the Updates sheet) have no batch key, so the
  engine's notices are untouched; who may decide (second person, never the proposer) untouched.
- 6 new sentences, vi + id.

**Tests** (`pb_bank_ocr/tests/test_wdgap_w3c_batch_notice.py`) — all PASS:

| # | Test |
|---|---|
| N1 | batch of 3 → one queued notice, ONE to-do (count "3", points to Compliance › Bank) and at most ONE email per approver; the proposer is never asked |
| N2 | "Approve all in this file" → 3 approved, the to-do is marked done, none left open |
| N3 | one of 3 approved → the to-do stays open and says 2 |
| N4 | a single change from HR's bank screen → the engine's own per-change notice and to-do, exactly as before |
| N5 | the proposer may not approve; "Approve all" as the proposer approves 0 ("3 left waiting: you ran this import") |
| N6 | a reminder for an approver who has the batch's to-do → still one to-do, no second email |
| N7 | batch decided before the delivery job ran → no to-do at all |
| N8 | the proposer gets ONE "decided" notice for the whole batch, none per person |
| N9 | the new sentences have vi + id translations, no vendor word |

**Suites, baseline = the unedited `pb_bank_ocr` from `origin/19.1` on the same fresh database:**


| Suite | Before (unedited `pb_bank_ocr`) | After |
|---|---|---|
| `pb_bank_ocr` + `pb_records` | 166 tests, 0 failed, 4 errors | 175 tests (+9), 0 failed, the same 4 errors |

The 4 are the Step 6 recorded baseline (TestBankOcr test_07, 07b, 09, 15). Local database
`wdgap_w3c_t` (fresh copy of `upd_p6_t_tpl`, every custom module behind the branch `-u`) dropped.

**Deploy notes (wave-3 go-live):** `-u pb_bank_ocr` on all five (normal tier: adds two columns to
the approvals' notice queue, no data rewritten, nothing re-sent; rows already queued keep their
old shape). Nothing waits on any site today, so there is nothing to migrate. After the go-live,
the BG1 batches (BG4) give each approver one to-do: rize ash, debalina, thao, wildan; sudima
hr@sudima.local, ash.

## Owner rulings BG2–BG4 (2026-11-18) — script and lists updated, live run waits for the go-live

- **BG2** Sudima: only people whose account-holder name matches their own name. **BG3** Rize:
  leave out accounts at banks the Vietnam bank file does not know; the matching-name rule too.
  **BG4** create the live batches only after the wave-3 go-live's DONE line.
- Script `docs/handovers/wdgap/w3c_bg1/bg1_batch.py`: defaults are now `NAME_RULE='match_only'`
  (the bank check's own "matches" band) and `BANK_RULE='known_only'` (the bank file's own bank
  list), each leaving the person out with a plain reason.
- Counts (rehearsal state; the live run rebuilds them at that moment):

| | rize | sudima |
|---|---|---|
| In the batch | **61** | **358** |
| Left out: the bank file does not know this bank | 126 | 0 |
| Left out: the account is in another person's name | 1 | 230 |
| Left out: the account name is close to, not the same as, the person | 0 | 27 |
| Left out: the same account number is on record for another person | 0 | 16 |
| Left out: no bank name on the bank account | 0 | 11 |
| Left out: archived (no longer working here) | 10 | 0 |
| Total | 198 | 642 |

- Lists (never committed): `outputs/wdgap-bank-gap-2026-11-17/rize-in-the-batch.csv`,
  `rize-left-out.csv`, `sudima-in-the-batch.csv`, `sudima-left-out.csv` (account numbers masked to
  the last 4, a plain reason per person).
- Live: nothing created, nothing changed. Next (after the go-live DONE line): fresh copies →
  rehearse with the new defaults and the undo → dumps → START note → run rize, then sudima → DONE
  note. Approvers then press "Approve all in this file" on Compliance › Bank.
