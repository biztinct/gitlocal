# WDGAP S6-A report — My details, papers and consent

Branch `wdgap-s6a` (from `origin/19.1` @ `abc2259b6`). Implementer + tester. No deploy,
no live server touched. Local database `wdgap_s6a_t` (copy of `upd_p6_t_tpl`, brought to
19.1) — dropped at the end of the phase.

## 1. What was built, per item

### Item 1 — my details with approval (new module `pb_me_details` 19.0.1.0.0)
- **/my/details**: all my details in one place — me (photo, marital status), bank account
  (masked, last four), ID papers (national ID, passport, work permit; numbers masked), family,
  and "Your changes" with status pills (Not sent yet / Waiting for HR / Approved / Sent back /
  Turned down, with the approver's reason). Tile under "More" for now (`TILES.setdefault`;
  see §8), a door card on
  `/my/profile` (QWeb xpath; its "separate secure flow" sentence now has a door).
- One request model `pb.me.detail.request` (kinds: add / change / remove a family member, ID
  paper with scan, photo, marital status). Created only by `pb_portal_create` for the
  session's own employee from a per-kind whitelist; nothing on the record changes until the
  route says yes; `_pb_apply` then writes exactly what was proposed (sudo, uid kept).
  Process `me_details` (default route: HR lead), adapter with before/after rows in the
  Approvals inbox, sent back → draft with reason → change and send again; withdraw.
- ID paper: number written to `identification_id` / `passport_id` (+expiry) / `permit_no`
  (+expiry); the scan filed as a vault document (ID or Work permit category) marked
  verified by the approver. "Valid until" is required (the vault categories require it).
- Family list `pb.employee.family` (one list per employee; HR keeps it from the backend too).
- **E1 (tax never moves by itself)**: in a Vietnam company an approved change that touches a
  member who counts for tax puts the member at "Waiting for HR to confirm for tax" (plus a
  to-do for the approver). Only `action_confirm_tax` (pay team: `group_hr_payroll_user`)
  writes or ends the `vietnam.employee.dependent` row pay reads; "Leave pay as it is" leaves
  it. Outside Vietnam nothing waits and nothing reaches pay. **`pb_hr_payroll_vietnam` was
  not edited** — the tick is held on the family member.
- HR board **People › Family** (lens, gate HR or pay team): waiting-for-tax cards with the
  tick, changes waiting, decided in the last 30 days. Quiet glance, one coloured number.
- My requests sources (details + bank) and a "HR sent a change back" Needs-you row.

### Bank details — through the bank-document check, one second person
- `pb_bank_ocr` gets a portal door (`pb_portal_start/update/send/withdraw/view`): the
  caller passes the SESSION's employee and the uploaded bytes; the attachment is made by
  the method (no attachment id ever comes from a browser — `_extract` reads as superuser),
  employee/company forced, document read, checks shown in plain words, numbers masked.
- A My Payobook request travels the **Updates bank route `records_bank`** (design default:
  same bank approvers as the Updates sheet — one second person, rize's named people), via
  `_approval_process_key_for` / `_engine_managed`; the route is laid for a company that has
  none. Second-person hooks (`_approval_step_people`, `_approval_may_decide`, the opt-in
  seams pb_records adds to the engine): never the proposer or the account's owner, never a
  self-service / support / demo login; named route with nobody else → waits with the
  "add a person to the bank details route" sentence; role route → the Updates second
  person. **Fail-closed**: a self-service change is never written without a second
  person's approve decision. Staff-started requests keep the `bankchange` route; they only
  gain "support/demo/self-service logins never decide".
- Approve / send back / turn down / withdraw run under sudo (a named approver may hold only
  a read seat — found by test B11, ledger row S6A-1).

### BANK STORE FINDING (FACTS §0.1) — fixed
- `pb_bank_ocr._apply_to_master` (staff screen and My Payobook): after writing the four
  `vietnam_bank_*` fields it now upserts the employee's bank account (`res.partner.bank` on
  the work contact, linked, put first by `sequence`) — `_pb_mirror_to_accounts`.
- `pb_records._write_bank` (Updates sheet + Records screen, approve AND undo): after writing
  the account it puts that account first and writes the four fields (branch cleared when
  the bank changes); the history row is labelled "Updates or Records".
- Duplicates are looked for in both stores (`_pb_duplicates_in_accounts`).
- **Read-only check for the deploy agent**: `env['hr.employee'].pb_bank_store_check(company_ids=None, limit=0)`
  → `{'checked', 'counts': {same, neither, accounts_only, bank_file_only, different}, 'rows': [...]}`;
  writes nothing (test B5 proves it), numbers masked to the last four.
- Dead code after `return` in `pb_bank_ocr.write()` repaired as `_approval_can` (FACTS §0.3).

### Item 2 — certificates (new module `pb_me_letters` 19.0.1.0.0, owner ruling E2)
- /my/certificates: employment certificate (no pay figures) issued AT ONCE as a PDF; salary
  certificate (agreed monthly wage of the running contract, server-computed) waits for ONE HR
  click — process `me_certificate` (HR lead) in the Approvals inbox; approving prints, files
  and logs it; the employee gets "Your salary certificate is ready" on the home page until
  downloaded. Purpose (bank / visa / renting / other + "who it is for"), language (English,
  Vietnamese, Indonesian when installed). Refused in plain words with no running contract or
  with pay on hold. Numbered `CERT/<year>/NNNN`, filed under "Degree / Certificate", logged
  on the certificate and the letter. Download streamed by the route after the ownership
  check. No email sent (download is the delivery; tenant email is off on three databases).
- Letter engine **by inheritance only** — `pb_lifecycle` not edited. Signatures relied on
  (FACTS §9): `pb.letter.template.letter_type` (`selection_add` on the TEMPLATE only),
  `pb.hr.letter.create`, `pb.hr.letter.action_generate()` (fills placeholders from
  `context_json`, `_make_pdf()`, `_file_in_vault()`), `pb.hr.letter._joining_date(employee)`,
  fields `attachment_id`, `document_id`, `rendered_html`, `subject`; report
  `pb_lifecycle.action_report_hr_letter` (used through `_make_pdf`). Never called:
  `action_send` / `_action_send_now` (so the letters approval route and email are not used).
  A company's own active template of the same kind wins over the shipped one.

### Item 3 — consent (new module `pb_me_privacy` 19.0.1.0.0, owner ruling E3)
- Per-company notice `pb.privacy.notice` (title + body translatable, version given on
  publish, words locked once published, replaced versions kept); neutral starting wording
  naming no law and no vendor. Per-EMPLOYEE answer `pb.privacy.consent` (exact wording shown,
  language, when, login, screen/paper, recorded by), rows never edited.
- The door: `ir.http._pre_dispatch` on GET pages under `/my` (deep links included, language
  prefix handled), fail-open, cached per session against a publish stamp. It offers "I have
  read and agree" and "I do not agree" — both recorded, both continue to the page asked for.
  Same version never asked twice; a new version asks again; `next` only follows My Payobook
  paths. No notice published → nobody asked (silent install).
- /my/privacy: my answer, the words, change my answer, Ask HR. Tile under "More" (only when
  a notice exists).
- HR board **People › Privacy** (lens, gate `hr.group_hr_user`): agreed / agreed on paper /
  said no / not answered yet (each person at exactly one), search, company picker, "Record
  paper consent" with who and when, notice line (see / write a new version). Managers see
  nothing (no ACL, no lens).

## 2. Files edited outside the new modules

| File | Change |
|---|---|
| `pb_bank_ocr/models/pb_bank_change_request.py` | `def _approval_can` restored (dead code); 3 new sys fields in `_SYS_FIELDS`; `_apply_to_master` calls `_pb_mirror_to_accounts`; `_find_duplicates` adds `_pb_duplicates_in_accounts` |
| `pb_bank_ocr/models/pb_employee_bank_history.py` | source `updates` ("Updates or Records") named by context `pb_bank_history_source` (label only; a row is always written) |
| `pb_bank_ocr/models/pb_bank_two_stores.py`, `pb_bank_self_service.py` | new files (mirror, cross-store duplicates, store check; portal door + second-person rule) |
| `pb_bank_ocr/models/__init__.py`, `__manifest__.py` (19.0.1.3.0), `tests/*`, `i18n/vi_VN.po` (30 entries appended), `i18n/id_ID.po` (new, the 30 new strings) | |
| `pb_records/models/pb_records_desk.py` | `_write_bank` only (the one bank-lane method) |
| `pb_records/__manifest__.py` (19.0.1.10.2), `tests/__init__.py`, `tests/test_wdgap_s6a_bank_file_store.py` | |

Not edited: `pb_lifecycle`, `pb_me_portal`, `pb_hr_payroll_vietnam`, `pb_pack_*`, any other phase's files.

## 3. Tests

All on `wdgap_s6a_t`. Employee-side calls made as a real **portal** login (ORM `with_user`
and HTTP `authenticate`).

| # | Test | Result |
|---|---|---|
| B1 | approval writes both stores; new account read first; store check sees no gap | PASS |
| B2 | an existing account is kept, the new one goes first; same number again adds nothing | PASS |
| B3 | a duplicate held only as somebody's bank ACCOUNT is found | PASS |
| B4 | restored `_approval_can` (owner submits; unrelated login cannot; HR advances) | PASS |
| B5 | store check: `bank_file_only` / `accounts_only` / `different`, masked, writes nothing | PASS |
| B6 | history label "Updates or Records"; a made-up label falls back to manual, row still written | PASS |
| B7 | portal door: other employee refused, wrong file refused, owned attachment, form cannot set state/employee, portal has no model right, view masks | PASS |
| B8 | My Payobook change travels `records_bank`; proposer never seated / may not approve; second person approves → both stores; history names the approver | PASS |
| B9 | named route with only the proposer waits with the route sentence; role route finds the Updates second person | PASS |
| B10 | fail-closed: no second person's yes → nothing written | PASS |
| B11 | withdraw → draft; sent back with reason (by a read-only-seat approver) → "sent back" + reason | PASS (found + fixed the sudo bug) |
| B12 | the platform support login is never seated and may not approve | PASS |
| R1–R4 | Updates/Records bank lane reaches the four fields, new account first, branch cleared, "same" writes nothing, undo puts both back | PASS |
| D1–D13 | family add waits → member; E1 waiting (VN) and tick-only dependant write; outside VN nothing waits; remove counted → end on tick; ID paper (expiry required) → number + verified scan; photo; marital; sent back → resend; guards (other's member, other employee, HR cannot create/edit, portal no rights, form cannot set state/employee); withdraw; inbox detail; My requests + Needs you; board + tick through the board | PASS |
| H1–H6 | HTTP as portal: overview masks number, no other person's data, no vendor word; every form 200; send over HTTP for own employee only; other people's ids show nothing; bank upload → check page; profile door + home tile | PASS |
| C1–C7 | employment at once (numbered, filed, no pay figure, logged); salary waits for HR, nothing filed before, issued with the wage, ready row until download; turned down with reason; guards; no contract / pay on hold refused; company wording wins; letter kinds added on the template only | PASS |
| P1(cert)–P2 | HTTP: ask + download own PDF; other person's certificate 404 | PASS |
| P1–P7 | silent install; versioned + locked; answer with exact words; new version asks again; HR board four places + paper consent with who/when; managers see nothing; two companies answered separately | PASS |
| P8–P11 | HTTP door: none without a notice; deep link → notice → "I do not agree" continues to the payslips; agree once, never again, new version asks again; `next` can't leave the site | PASS |
| PO gates | vi_VN + id_ID parse, three loader rules, no empty line, no vendor word — three new modules | PASS |

**Full suites vs baseline**

| Suite | Tests | Failures | vs baseline |
|---|---|---|---|
| pb_bank_ocr | 34 (20 + 14 new) | 4 errors: test_07, 07b, 09, 15 | = baseline |
| pb_records | 140 (134 + 6 new) | 0 | = baseline |
| pb_me_portal (not edited; run because of the home hooks) | 125 | test_05_grid, test_06_font, test_12_vi_po…, test_t1_7…, test_01_profile_change_flow… | = the known pre-existing set (PR-C/PR-D/QF5 reports). `test_02_tile_meta…` failed while my tiles sat in "Me" → moved to "More" (C-3), now passes |
| pb_me_details / pb_me_letters / pb_me_privacy | 26 / 16 / 18 | 0 | new |

Final runs after the last edit: `t5` (pb_bank_ocr 34, pb_me_details 26, pb_me_letters 16,
pb_me_privacy 18, pb_me_portal 125) and `t6` (pb_me_details + pb_me_portal again, on the copy with
the walk's published notice set aside — ledger S6A-8): every failure is in the baseline set above;
all new tests pass. pb_records' last full run (`t3`, 140 tests, 0 failures) was after its last change.

**Browser walk** (Chrome, `http://127.0.0.1:8951`, portal login + HR login, console clean):
privacy door on a deep link → agree → back on /my/payslips; /my/details (phone width 614 px);
family member sent → "Waiting for HR"; bank document uploaded → check page → sent ("Sent for
approval" toast; HR's inbox did NOT get it — it went to the second person); HR inbox detail
(before/after rows + tax chip) → Approve; People › Family (inside the hub) → card → Confirm for
tax → card gone, member shows "Counts for tax"; People › Privacy → counts → Record paper consent
→ "Agreed on paper, recorded by"; /vi and /id pages fetched (translated headings, no vendor word).
Fixed from the walk: unstyled selects; truncated inbox chip; a certificate that could not be
printed left a numbered "waiting" row and showed the raw printer error — now one savepoint and a
plain sentence. Not walkable locally: printing the PDF (no wkhtmltopdf on the Mac; the tests use
the test-mode HTML render) — check one certificate download at go-live.

Static gates: py_compile, XML parse, `node --check`, pyflakes clean; white-label grep of every
user-visible file and msgstr: none.

## 4. Rails

- Portal paths: session employee only, no employee id from a request, sudo after the guard;
  tested as a real PORTAL login (ORM `with_user(portal)` and HTTP `authenticate`), including
  crafted ids of other people's family member / request / bank change / certificate.
- No ACL for portal or plain internal users on any new model (seat read rule only for
  people a route asked); HR cannot edit what an employee proposed; tax state only through
  the tick; consent rows never edited.
- Money: bank change is fail-closed on a second person; numbers masked on every /my page,
  in My requests and in the store check.
- White-label: no "Odoo" in any user-visible string or msgstr (static grep + PO gates).
- Silent install: no notice → nobody asked; no crons; no emails; no demo data; boards empty.

## 5. Contracts other phases may rely on

- `hr.employee.pb_bank_store_check(company_ids=None, limit=0)` → dict as in §1 (read-only).
- `pb.bank.change.request.pb_portal_start(employee, data, filename, mimetype, doc_kind='other')`,
  `.pb_portal_update(values)`, `.pb_portal_send()`, `.pb_portal_withdraw()`, `.pb_portal_view()`;
  field `pb_origin` (`staff` / `self_service`).
- `pb.me.detail.request.pb_portal_create(employee, kind, values, member=None, upload=None, request_id=None)`.
- `pb.employee.family` (`tax_state` none/waiting/confirmed, `action_confirm_tax`, `action_not_for_tax`).
- `pb.me.certificate.pb_portal_request(employee, kind, purpose, lang=None, note=None)`.
- `pb.privacy.consent._pb_pending(user)` → `(notice, employee)`; stamp param `pb_me_privacy.stamp`.
- Approval process keys added: `me_details`, `me_certificate`. People hub lenses: `family` (seq 88), `privacy` (seq 90).
- `pb.me.home` overrides call `super()` and append (tiles `/my/details`, `/my/certificates`, `/my/privacy`; needs-you keys `details_sent_back`, `certificate_ready`; My requests keys `my_details`, `my_bank`, `certificate`).

## 6. Deploy notes (for the step go-live)

- Install order: `-u pb_bank_ocr,pb_records` then `-i pb_me_details,pb_me_letters,pb_me_privacy`
  (all three need `pb_bank_ocr`/`pb_lifecycle`/`pb_people_hub` installed — check per database).
  Post-init hooks lay the `me_details` and `me_certificate` routes (HR lead, filled from the
  payroll-user group) on every company; idempotent.
- **Before go-live, run the store check read-only on all five databases** and report the
  counts: `env['hr.employee'].pb_bank_store_check()['counts']` (shell; no commit needed).
- Asset purge after install (new frontend + backend bundles).
- Merged test runs: on a database where a privacy notice has been published, other modules'
  /my HTTP tests meet the notice first (ledger S6A-8). At go-live no notice exists anywhere.
- Risky tier (bank details = money; access rules). Nothing changes a payslip figure; the only
  pay-reaching path is the pay team's tax tick (Vietnam dependants), which writes the same
  table HR edits by hand today.
- The `records_bank` route now also decides **My Payobook** bank changes. On rize it names
  ash/debalina/thao/wildan (UPDATES D14) — that is intended; check the route on each
  database has somebody other than a self-service/support/demo login.

## 7. Owner questions (plain words)

1. **Who approves an employee's own bank change?** Built as the design default: the same
   people as the Updates sheet's bank route — ONE second person (on rize: ash, debalina, thao or
   wildan). Bank changes HR types on the staff bank screen keep their two-step route (HR lead,
   then Finance). Keep it so, or should both use the same one-person route?
2. **Salary certificate figure.** It shows the agreed monthly salary on the running contract
   (before tax). Some banks ask for take-home pay of the last 3 months instead — add that as a
   second line, or keep one figure?
3. **Before go-live: people whose two bank records disagree.** The check lists them (numbers
   masked). For each, which is right — the account the bank file pays today, or the one the
   Updates sheet shows? Nothing is changed until you say.
4. **Privacy notice wording.** We ship a neutral starting text that names no law. Each customer
   (rize, sudima, payobook demo) must review and publish its own; until it does, nobody is asked.
   Who will write rize's?

## 8. Left for later

- A pay data file import (`pb_hr_payroll_formula._sync_employee_bank_account`) still writes
  only the bank ACCOUNT, not the four fields the bank file reads (outside this lane). The
  store check lists the people it affects; a fix is a one-method change there.
- No automatic e-mail when a salary certificate is ready (home-page row + My requests only).
- A national ID's expiry is kept on the filed document only (the employee record has no
  field for it).
- The candidate's application consent is not carried to the employee at hire (FACTS §4.2, optional).
- New icons (id-card, landmark) would need a pb_me_portal prep commit; existing icons used.
- **Tiles under "More" (C-3)**: the My details and Certificates tiles belong in "Me", but
  pb_me_portal's home test pins the "Me" list. One orchestrator prep commit: add
  `/my/details` and `/my/certificates` to that test's list, then change `group` to `'me'` in
  `pb_me_details/models/pb_me_home.py` and `pb_me_letters/models/pb_me_home.py`.
- HR boards are new People-hub lenses (Family, Privacy); certificates and detail changes have
  no board of their own — they are decided in the Approvals inbox (native read-only lists exist
  for each model, not on the menu).

## 9. Gotchas → ledger rows

| S6A-1 | S6-A | The engine runs `_approval_return` / `_approval_reject` / `_approval_apply` AS THE DECIDER. A named approver of the Updates bank route can hold only a READ seat (seat rule), so a record write there raised AccessError ("send back" failed) — not seen with HR deciders. **Fix:** every adapter write in those hooks runs on `self.sudo()` (uid kept). Test with a decider who has no write right. |
| S6A-2 | S6-A | `order='version desc'` puts a draft's empty version FIRST (PostgreSQL sorts NULL first in DESC): "next version = last + 1" gave 1 again. **Fix:** filter `version > 0` (or `NULLS LAST`). |
| S6A-3 | S6-A | The ID-document and work-permit vault categories REQUIRE an expiry date (`_check_expiry_required`): filing a scan without one failed inside the approval and the engine swallowed it ("approved but could not be carried out"). Ask for the date on the form. |
| S6A-4 | S6-A | `pb_me_portal/tests/test_me_home.py` test_02 pins the exact list of "Me" tiles, so a new module's `TILES.setdefault(..., group='me')` fails pb_me_portal's suite. Until a prep commit updates that test, new tiles go under "More" (C-3). |
| S6A-5 | S6-A | Terms extraction only sees `_(` / `env._(`: a local alias `_t = self.env._` hides every string from the .pot. Name the alias `_`. |
| S6A-6 | S6-A | A portal route that creates a record and then calls something that may raise (PDF printing) must do both in ONE savepoint, or the controller's `except UserError` keeps the half-made record (a numbered certificate stuck "waiting"). Locally the Mac has no wkhtmltopdf: printing raises; tests pass only because test mode renders HTML. |
| S6A-8 | S6-A | Once a company has a PUBLISHED privacy notice, every HTTP test of another module that opens /my as an employee of that company (pb_me_portal ×24 seen) is sent to the notice first and fails — a local walk that published one broke them. Not a code fault: run merged suites on a copy with no published notice (`UPDATE pb_privacy_notice SET state='replaced' WHERE state='published'` on the COPY only), and fixtures that test /my pages must answer or replace the notice. |
| S6A-7 | S6-A | `upd_p6_t_tpl` copies have no filestore for the template's attachments: the local server logs FileNotFoundError on logos/images — harmless, not a regression. One test run showed a 29-minute pause between two tests (Mac asleep); re-run was 204 s. |
