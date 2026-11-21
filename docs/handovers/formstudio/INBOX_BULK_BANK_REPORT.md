# INBOX-BULK-BANK — approve many bank-detail requests at once (report)

Builder, tester, self-reviewer and deployer, 2026-11-21 (UTC). Handover
`INBOX_BULK_BANK_HANDOVER.md` (main checkout). Branch `inbox-bulk-bank` from `origin/19.1` @ `ce098597a`.

**Result: LIVE on all five databases** (payobook, payobook_template, p0clone, rize, sudima; abm untouched) at
`01ec108c5` (module trees; later commits on the branch are scripts and this report), **554 s down**
(02:21:42–02:30:56 UTC). Deploy notes: START 02:00, DONE 02:31 (written by the tries script), NOTE 02:36.
**Nothing was approved on any live site by this work.**

**Important context found on the way:** the 358 waiting sudima requests were already approved on live at
23:42–23:43 UTC (before this phase went live) by another Claude session, on the owner's instruction,
through the approval engine as the owner's seat (deploy notes NOTE 23:43; backup
`/odoo/backups/sudima-before-bank-approvals-20261120T2342.dump`). A second NOTE (00:04) corrected 181
employees' accounts the same way. So on live sudima there is nothing left to approve today; the feature is
live for the next upload, and test 8 was run on a hidden copy restored from that 23:42 backup (358 still
waiting there).

## 1. What was built

| Part | Where | What |
|---|---|---|
| Middle tier | `biz_approval_workflow/models/process.py` | New field `bulk_confirm` ("Several at once, with an extra confirmation"). `BULK_CONFIRM_KEYS = {records_bank, bankchange}` — the only `money` rows that may carry it; constraint `_check_bulk_confirm_money` refuses it on any kind that pays money out. Helpers `_bulk_mode`, `_bulk_modes_allowed`, `_set_bulk_mode`; `create()` gives a newly born bank-detail row the tier (same pattern as `bulk_ok`). |
| One-time step | `biz_approval_workflow/migrations/19.0.1.9.0/post-bulk_confirm_defaults.py` | Column arrives False (silent), then `_seed_bulk_confirm_defaults()` switches the tier on ONCE for `records_bank` and `bankchange` (marker `biz_approval_workflow.bulk_confirm_seeded`); a later "off" survives upgrades. |
| Trail | `biz_approval_workflow/models/event.py` | Event kind `setting_changed`; shown under the History "publishes" family. |
| Inbox server | `pb_approval_config/models/inbox_facade.py` | `_needs_confirm(process)`; `_can_bulk` lets a confirm-tier kind past the money/`bulk_ok` gates (my turn, pending, not stuck, independence unchanged); card gains `bulk_confirm`. `decide_many(..., confirmed=False, batch_size=None)` refuses confirm-tier rows unless `confirmed is True`; every bulk decision's note reads "Approved with Approve selected, together with N others[, after the extra check]." New `select_all_ids(filters, search)` (cap 1,000, only my open seats) and `bulk_summary(ids)` (counts, kinds, bank count, other-name count, pay count). |
| Other-name count | `pb_employee_bank_panel/models/inbox_other_name.py` | Fills "N of them are in another person's name" with the payment list's own name test (`_pb_name_band` → 'other') on the PROPOSED holder; counts only. |
| Inbox screen | `inbox.js` / `inbox.xml` / `inbox.scss` | "Select all N that I can approve" pill (only when it reaches beyond the loaded page); selection kept across pages while the filter is the same; Approve selected → server summary → the extra-check dialog for bank details (count, kind, other-name line, pay line, "Pay will be sent to these accounts.", Review the list, required tick "I have checked these bank details", button off until ticked) → groups of 50 with "120 of 358 approved", a bar and Stop; failures listed as before and stay ticked; the not-reached ones stay ticked after Stop. |
| Setup switch (R13) | `matrix_facade.py` (`_bulk_payload`, `set_bulk_mode`), `builder.js` / `builder.xml` | Route editor › Safeguards step: card "Can be approved several at once?" with One at a time / Several at once / Several at once, with an extra confirmation. Tenant administrator (`base.group_system`) only, written as the person (catalogue rails apply); bank-detail money kinds offer only off / extra-confirmation; payment kinds are drawn disabled with "Money leaves the company with this kind, so each one is approved on its own." Saved at once (not part of the route); one trail line per change. |
| Words | vi_VN + id_ID | 50 new msgids in `pb_approval_config` (+ `.pot`), new `pb_approval_config/i18n/id_ID.po` (the new words plus the inbox selection words reused), 5 in `biz_approval_workflow`. |
| Learn | — | No lesson shows the inbox tick boxes (searched `pb_learn`, `pb_coach`, `pb_payai`): nothing to update. |

Kinds switched on (the one-time step): **`records_bank`** (Bank details from Records and Updates — every bank
change since ruling BK1, imports included) and **`bankchange`** (Bank account change — the older
bank-document route). No other kind; every other `money` row (awards, backpay, bankfile, expense, fundpay,
hiring_offer, hiring_request, jobchange, journal, loan, payreview, release, scaleraise, tripadvance) stays
one at a time.

Versions: biz_approval_workflow 19.0.1.8.0 → 19.0.1.9.0, pb_approval_config 19.0.1.9.4 → 19.0.1.10.0,
pb_employee_bank_panel 19.0.1.0.0 → 19.0.1.1.0. `-u biz_approval_workflow` cascades to its installed
dependents (~141 modules per database).

## 2. Tests (handover numbering)

Local: `ibb_base` = `wf2p6_base` + `-u biz_approval_workflow` + `-i pb_employee_bank_panel` on `origin/19.1` code.
Baseline = the same `--test-tags` run with the `origin/19.1` copies of the three modules (other modules
linked unchanged); new = the branch. Local databases dropped after.

| Run | Tests | Failed / errors |
|---|---|---|
| Baseline `/biz_approval_workflow,/pb_approval_config,/pb_employee_bank_panel` | 227 | 4 / 0 |
| Baseline `/pb_bank_ocr,/pb_records` | 175 | 0 / 4 |
| New, all five tags together | **411** (+9 new) | **4 / 4 — the identical set** |

The common set is pre-existing: static `test_the_look…` (`inbox.scss:98 #F8F9FC`, old line), P7 Vietnamese
z06d / z06e, u13 "70 terms exported but not translated" (unchanged count — every new msgid has vi), and
`TestBankOcr` 07 / 07b / 09 / 15 (errors on this base before and after).

| # | Test | Where | Result |
|---|---|---|---|
| 1 | Bank-detail card tickable, payment kind refused (card + direct `decide_many` even with `confirmed=True`, constraint refuses the tier on a payment kind, a row forced by SQL still refused, tier off → one at a time again) | `test_inbox_bulk_bank.test_01`; browser (Fund payment card's box disabled with "Money leaves the company…") | PASS |
| 2 | Extra check required: `decide_many` without `confirmed` (and with a truthy non-boolean) refuses every row, nothing changes; summary counts; with `confirmed` all approved, each note "together with 2 others, after the extra check" | `test_02` | PASS |
| 3 | "Select all" over a filter of 120 → 120 offered (not somebody else's, not another kind); 3 groups of ≤50; all approved; one approved alone vs the 119 together: request/step/seat shape identical, decision fields identical except the note | `test_03`; sudima copy (§3) for the real bank accounts | PASS |
| 4 | Independence: my own request never offered, never approved | `test_04` | PASS |
| 5 | One failure in a group does not stop the rest (4 of 5 approved, the busy one untouched) | `test_05` | PASS |
| 6 | Silent upgrade + one-time step: only `records_bank`/`bankchange`; no request, decision, mail or job changes; second run 0; customer "off" survives; the migration file itself | `test_06`; 5 rehearsal copies "counts restored vs upgraded: identical" | PASS |
| 7 | The switch: admin can set all three answers (one trail line each, none for a repeat); bank kind only off/extra; payment kind disabled with reason and every "on" refused; approval-admin who is not the administrator and an ordinary user refused; route editor carries it | `test_07`; browser | PASS |
| 8 | Hidden sudima copy (the 23:42 backup: 358 waiting), as the owner's seat | §3 | PASS |
| 9 | vi/id PO gate, forbidden word, console, phone width | §3 PO gate on the server; added-lines grep: the vendor word only in import lines / PO markers; browser console: no errors (only the local worker warnings); dialog at 500 px (the narrowest this browser window goes) fits, no sideways scroll | PASS |
| — | "Another person's name" count with the payment list's name test | `pb_employee_bank_panel/tests/test_inbox_other_name.py` (2) | PASS |

Browser walk (local copy, 130 waiting DEMO bank requests + 3 leave + 1 payment): "Select all 130 that I can
approve" → "130 selected" → Approve selected → the check (title "Approve 130 bank details changes
together?", kind chip, "None of them is in another person's name.", amber "Pay will be sent to these
accounts.", Review the list, tick, "They are approved 50 at a time…", Approve off until ticked) → Review
the list closed it with 130 still selected → approve → Stop pressed during group 1 → "Stopped after 50 of
130 were approved… the rest are still selected" (80 kept) → approve again → "50 of 80 approved" → "80
approved." → tabs recount. Decision notes in the database: 50 × "together with 129 others, after the extra
check", 80 × "together with 79 others…". Route editor › Safeguards card: radio switch saved ("Saved. It
applies straight away."), "Several at once" drawn disabled for the bank kind.

## 3. Rehearsal (hidden copies with the LIVE installed module set; jobs + mail off; all dropped, 0 left)

Prep `ibb_prep.sh` (00:21 UTC): staged trees = commit, live trees = `origin/19.1`, previous trees saved,
PO gate (biz_approval_workflow vi 192/0 empty, id 22/0; pb_approval_config vi 1,010 rows / 70 empty =
the old template-only rows, id 1,009 / 936 empty = only the new words are Indonesian; bank panel 37/0;
0 vendor word), five dumps read back (`/odoo/backups/ibb-20261121T002146Z/`), file folders linked, job
snapshots, read-only probes.

| Copy | Upgrade (`-u biz_approval_workflow,pb_approval_config,pb_employee_bank_panel`, cascades) | Data restored vs upgraded | One-time step | /my + My Leave old vs new |
|---|---|---|---|---|
| sudima (23:42 backup) | 158 s, exit 0, 0 ERROR | identical | `bankchange`, `records_bank` | 1 internal login: identical once the per-session block is left out (re-checked with a page diff: the only changing line also changes between two reads of the same code) |
| rize | 155 s, exit 0, 0 ERROR | identical | same | 3 people identical (page diff, bodies compared) |
| p0clone | 140 s, exit 0, 0 ERROR | identical | same | no employee login |
| payobook | 131 s, exit 0, 0 ERROR | identical | same | 3 people byte-identical |
| payobook_template | 152 s, exit 0, 0 ERROR | identical | same | no employee login |

On every copy after the upgrade: inbox opens, route editor shows the switch ("confirm", allowed off/confirm,
editable for the administrator), the style bundle compiles and carries the check dialog's styles. The
upgrade switched on 34 jobs (payobook 14) on copies where all were off — the live go-live restores the
job snapshot (as every cascade go-live).

**Test 8 — sudima copy, seat of the owner (the same seat the 23:43 live approvals used):**
select all offered **358** (all with the extra check) in 1.9 s; summary: 358 bank-detail, **0 in another
person's name, 0 also change pay**; without the check: 0 done / 3 refused; one approved alone, then
**357 together in 8 groups (10.1–10.7 s per group of 50; 105 s for the whole run incl. counts)**, 0 failed;
alone vs together: request applied, bank change approved, seats/steps, the employee's bank-file number /
holder / bank and the approved account number / holder all = the proposal — **identical**; decision fields
identical but the note ("…together with 357 others, after the extra check."); **358 of 358 now read the
proposal**; requests pending 358 → 0, applied 0 → 358; joining checklist "Bank account" missing **9 → 9**
(the approved accounts already matched — the proposals filled the bank-file fields); bank accounts 642 →
642 (hash unchanged), mails 20 → 20, queued notices 10 → 10. Payslips: sudima has **no payslips** yet, so
the "three payslips identical" check is empty there (0 / 0); payslips were checked on rize instead:
**211 payslips / 6,914 lines old vs new code, 0 differing** (31 computed, 180 refused identically).

## 4. Go-live ×5 and verification

* The tries started 01:20 behind a clean rehearsal (`ibb_after_rehearsal.sh`). Waited for the open START
  of Claude FORMSTUDIO FS-14 (DONE 01:52); our START 02:00; two tries refused by the new rule "another
  session wrote a deploy-notes line in the last 20 minutes" (FS-14's NOTE 01:56); try 7 at 02:20 found
  15 quiet minutes on rize, payobook AND sudima, the lock free, no HOLD → fresh backups ×5
  (`golive-*.dump`) → stop 02:21:42.
* Upgrades (cascade): payobook_template 107 s, p0clone 101, sudima 102, rize 105, payobook 125 — all
  exit 0, 0 ERROR. Asset purge + `web.assets.version = ibb-20261121T002146Z` per database. Port listening
  02:30:56; five sites 200.

| Check (after) | Result |
|---|---|
| Trees | 3 = commit |
| Versions | manifest = installed on all 15 rows (19.0.1.9.0 / 19.0.1.10.0 / 19.0.1.1.0) |
| Jobs | = snapshot ×5 (111/58, 99/40, 99/48, 99/91, 100/91); payobook_template had 8 re-activated by the cascade, switched back by the script; payobook job 156 off |
| Data before the stop vs after | identical ×5 (requests, steps, seats, decisions, notices, mails, bank accounts, bank changes, employee bank-file fields, processes, routes, payslips) — only the new column: `records_bank`, `bankchange` on ×5 |
| Server log since the stop | 4,357 lines; upgrade logs 0 ERROR / 0 Traceback; 1 chat-presence write conflict on rize at the moment of the stop (websocket, not ours); 0 asset errors; one service process |
| Screens ×5 (server side, as each site's administrator) | inbox head + My approvals page open; route editor for bank details shows the switch at "with an extra confirmation", allowed off / extra, editable for the administrator; the style bundle compiles and carries the check dialog's styles |
| My Leave ×5 | identical before / after for every person checked |
| /my | identical on template / p0clone and for 1 of 3 people on rize and payobook; different for the others. The "before" pages were read at 00:45, before another deployer's go-live (FS-14, My Payobook page builder, 01:52) and 1 h 45 of use; the rehearsal compared the page bodies before and after THIS upgrade on the same copy (rize, 3 people, both pages) and found 0 changed lines, and payobook's copy was byte-identical — so the difference is not from this change |
| payobook.com in the browser (QA login) | Approvals inbox opens; Workflows › Bank details from Records and Updates › Safeguards shows "Can be approved several at once?" with "Several at once, with an extra confirmation" chosen and "Several at once" drawn off; console clean. Nothing changed, nothing approved. |

Live sudima today: 0 bank-detail requests waiting (539 already applied by the other session's work at
23:42–00:03), so the new "Select all" control has nothing to offer there right now — it appears the next
time more than one page of requests is waiting.

## Click path for the owner (next time a batch of bank changes is waiting)
1. Open **Approvals** (Home › Approvals, or the bell's "Waiting on you").
2. Optional: filter **What kind of request** = "Bank details from Records and Updates".
3. Press **Select all N that I can approve** (next to "Select all on this page…"). The bar at the bottom says "N selected".
4. Press **Approve selected**. The check opens: count, how many are in another person's name, "Pay will be sent to these accounts."
5. Press **Review the list** if you want to look first (your ticks stay), then Approve selected again.
6. Tick **I have checked these bank details**, press **Approve N**. Watch "120 of 358 approved"; **Stop** halts after the current group of 50.

Switch: open any route for a kind (Approvals › Workflows › the kind) › step 3 **Safeguards** › card
**Can be approved several at once?** (administrator only).

## 5. Gotchas (ledger rows)

* IBB-1 `-u biz_approval_workflow` cascades to every installed approval adapter (~141 modules): about
  100–125 s per database live, 130–160 s on a busy copy → ~9 minutes down for five sites. A field on the
  engine's catalogue is never a "small" go-live.
* IBB-2 Another session can change a live database by shell with no web activity to see (the 358 were
  approved that way at 23:43). The go-live now also waits while any other deployer wrote a deploy-notes
  line in the last 20 minutes (`notes_ok` → `RECENT-OTHER`).
* IBB-3 An internal login's `/my` carries the per-session block (`odoo.__session_info__`), which differs
  between two reads of the same code: leave it out of page hashes (the FS-13 hash did not, because it
  read portal logins).
* IBB-4 `/odoo` answers 301 to `/bizapp` on this build: a probe that wants the backend page and its
  style bundle must follow it.
* IBB-5 `pb_filter_kit.pbf_domain` returns a `Domain`; combine with `Domain.AND([...])`, not list
  concatenation.
* IBB-6 OWL text next to a `t-esc` (e.g. "· N could not be approved") is safer as one `_t()` string in the
  component than as template text around the expression.
* IBB-7 The phone-width tray's "Clear" sits partly under the floating PayAI button at ~500 px
  (pre-existing layout, not changed here).

## 6. Not done / notes
* The 358 waiting sudima requests were already approved on live before this went live (another session,
  owner's instruction) — nothing for the owner to press today.
* sudima has no payslips yet, so "three payslips identical" could only be checked on rize (211 / 0 differing).
* `pb_approval_config` had no Indonesian catalogue; the new one carries only this phase's words and the
  inbox selection words it reuses (the rest of the module stays English in Indonesian, as before).
* The browser window cannot go below 500 px; the phone check was at 500 px.

