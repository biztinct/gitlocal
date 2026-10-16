# ETP E1 — Expenses on My Payobook — implementation report (Opus)

Handover: `E1_HANDOVER.md`. Ledger: `ETP_LEDGER.md`. Not committed, not deployed.
Clone: `p0clone`, port 8099, staging `/tmp/deployE1` (staged: `pb_me_expense` + `pb_me_portal`; the staged
pb_me_portal differs from the server copy in exactly the five files of commit 875f3b89b — the 19.0.3.4.0
pre-work — checked with `diff -rq` before the first run). Final run 2026-10-16 00:24–00:27 server time.

## 1. Files added (one new module; nothing else edited)

| File | What |
|---|---|
| `pb_me_expense/__manifest__.py` | "Employee Self-Service Portal — expenses" / "Claim back what you paid for, from My Payobook", 19.0.1.0.0, Hidden/Tools, auto_install, depends `pb_me_portal, hr_expense, biz_approval_workflow, pb_approval_config`, post_init_hook, frontend scss + one interaction. |
| `__init__.py` | `post_init_hook` → `seed_all` (default route for every company). |
| `models/expense_claim.py` | `pb.expense.claim` (mail.thread + `biz.approval.chain.mixin`): fields per D1 (+ `receipt_count`, `paid_on`); `register_chain('pb.expense.claim', 'expense', submit_state='submitted', driven=('approved',), …)` with NO `date_field`; ladder hooks (send → `_check_ready`; approved → expenses `_do_approve(check=False)` as the decider; refused → `_do_refuse(reason)`); engine answers `_approval_reject` (reason kept), `_approval_return` (sent back → draft + reason), `_approval_withdraw` (taken back → draft; mirrors an inbox withdrawal too), `_approval_manager_uids`; `_chain_title/_company/_facts/_fact_specs/_revision_values` (sorted `[expense id, amount, attachment id]`), `_approval_detail` (receipt rows + chips for the inbox drawer); `_sync_paid`; backend buttons; `_approval_seed_default` (Their manager → Finance approver) + `seed_all`. |
| `models/hr_expense.py` | The one stock field `hr.expense.pb_claim_id` (index, set null); stock Approve / Refuse / Reset refuse with "This receipt is part of claim %s. Decide it from Approvals." while the claim has an open request; `write` override → `_sync_paid` when `state/approval_state/account_move_id` change. |
| `models/me_expense.py` | Facade `pb.me.expense`: guards (`emp.user_id == env.uid`), `categories`, `trips_for`, `check_receipt` (bounded size, type from the file's own bytes, amount parsed in the reader's separators, category whitelist, no future date, own trip), `new_claim`, `add_receipt`, `remove_receipt`, `send` (route laid on demand, expenses `approval_state='submitted'` + `manager_id=False`, then the engine), `withdraw` (engine.cancel), `reopen`, `own_claims`, `status`, `steps`, page payloads with tokened receipt links, `waiting_on_you`. `ExpenseRefusal(key, sentence)`. |
| `models/pb_me_home.py` | Needs-you row "1 expense claim refused — fix and resend"; My requests source per D9; `get_my_requests` re-reads "paid" first. |
| `controllers/portal.py` | `PbMeExpensePortal(PbMePortal)`: the eight routes of the Scope, `expense_count` counter, ownership guard `_ex_claim` (`_ess_own_employees`), styled 404, every refusal re-renders with the typed values kept. |
| `views/portal_templates.xml` | Breadcrumbs, home tile, own icon template `ex_icon` (Lucide), pill, alert, the receipt block (drop area / camera / amount / chips / date / company card / folded note), send button with its three "not yet" reasons, list page, new-claim page, receipt card, claim page, 404. |
| `views/expense_claim_views.xml` | Backend list + form (statusbar, Approve/Refuse for the fallback ladder, receipts tab, chatter) + search + action + menu "Expense claims" under stock Expenses, `group_hr_expense_team_approver`. No rail item. |
| `security/ir.model.access.csv`, `security/pb_me_expense_security.xml` | `base.group_user` 1110, team approver 1111; global company rule; own rule; seat rule (read + write, AM60); team-approver rule (stock approver shape + seat); expense officers/accountants all. No portal row. |
| `data/ir_sequence_data.xml`, `data/approval_process.xml` | `EXP/%(year)s/` padding 4; catalogue row `expense` ("Expense claims", area money, money=True). |
| `static/src/scss/expense.scss`, `static/src/interactions/expense_form.js` | `.pbex-*` layer; the interaction (preview, separators as you type, receipts added in place + running total, send-button reasons, Cmd/Ctrl+Enter, Esc folds the note, double-submit lock, drag highlight, j/k on the list, address-bar clean-up). |
| `i18n/vi_VN.po` | 197 entries built from the clone's own export (`trans_export` in a read-only shell), three rules each. |
| `tests/common.py`, `test_expense.py`, `test_pages.py`, `test_po_gate.py` | E1.1–E1.10, E1.12 (34 tests). |

## 2. Results

Final clone run (`-u pb_me_expense,pb_me_portal,hr_expense --test-enable --test-tags /pb_me_expense,/pb_me_portal`):
```
odoo.tests.stats: pb_me_expense: 34 tests 26.81s 17131 queries
odoo.tests.stats: pb_me_portal: 125 tests 76.82s 33892 queries
odoo.tests.result: 1 failed, 1 error(s) of 121 tests when loading database 'p0clone'
FAIL:  TestMeHome.test_02_tile_meta_default_and_hidden          <- pb_me_portal pin, not this module (§6)
ERROR: TestPbMePortal.test_01_profile_change_flow_and_audit      <- known M19
```
Every pb_me_expense test passes. PO parse gate on the server: `PoFileReader` reads 245 rows from
`pb_me_expense/i18n/vi_VN.po`. No warning from the module in the log.

| # | Test(s) | Result |
|---|---|---|
| E1.1 | `test_e1_1_categories` | pass. Shared and own-company expense categories offered; another company's, a priced one (Mileage-like) and a non-expense product are not; FOOD → `utensils`, others → `receipt`. |
| E1.2 | `test_e1_2_new_claim_as_an_employee_login`, `_2b_refusals_create_nothing`, `_2c_more_receipts_and_remove`; HTTP half in `test_e1_9*` | pass. Draft claim `EXP/2026/…`, `create_uid` = the employee login on claim and expense; expense employee/company/claim/product/currency/amount right, `own_account`, draft; one attachment `hr.expense/<id>`, set as main; thumb `/web/image/<att>/480x480?access_token=` and full `/web/content/<att>?access_token=` — GET as the employee login 200 (image content type). "1,250,000" reads as 1,250,000; a PDF works; company card → `company_account`. Refused with key + words, nothing created: 10 MB + 1 (`size`), text bytes declared as PNG (`type`), 0 and "abc" (`amount`), priced / other company (`category`), next year (`date`), no file (`nofile`). Remove takes the file with it. |
| E1.3 | `test_e1_3_send` | pass. `submitted`, `submitted_on`; each expense `approval_state=submitted`, `state=submitted`; one `biz.approval.request` on `pb.expense.claim`, submitter = the employee login, pending; second send → "already sent"; empty draft → "Add at least one receipt…". |
| E1.4 | `test_e1_4_the_route_approve`, `_4b_refuse_then_fix_and_resend`, `_4c_sent_back_is_a_draft_with_the_reason` | pass. Two steps: seat 1 = the manager, seat 2 = the finance holder; status names step + person; manager decides (engine `decide`) → still submitted, finance active; finance decides → claim `approved`, request `applied`, every expense `approved`, `manager_id` = the finance user (stock's `_do_approve` writes who decided), `approval_date` set. Reject with a reason → `refused`, `refusal_reason`, every expense `refused`, pill tone `act`; reopen → draft, expenses draft (`approval_state` empty), reason still shown; send again → `attempt` 2, reason cleared. Sent back → draft with the reason. |
| E1.5 | `test_e1_5_no_manager_login_blocks_with_a_plain_sentence`, `_5b_…expense_approver…`, page `test_e1_5_blocked_says_so_on_the_page` | pass — **the engine BLOCKS, it never skips**: request `blocked`, `block_reason` "No manager is recorded for the people this is about, so nobody can be asked."; the claim stays `submitted` and its expenses `submitted` (no auto-approval, unlike stock); `status()` = "Waiting approval" + blocked + "Nobody is set up to approve this yet. HR can fix the route."; the page says it with an Ask HR button. HR sets the manager → `engine.repair` → pending → approves normally. An expense approver set on the employee is the manager seat. |
| E1.6 | `test_e1_6_take_back`, `_6b_withdrawn_from_the_inbox_is_mirrored` | pass. Withdraw on submitted → draft, request `cancelled`, expenses draft; second press → False; on approved → refusal "already approved…". An inbox withdrawal (engine.cancel by the submitter) also makes the claim a draft. |
| E1.7 | `test_e1_7_stock_buttons` | pass. Approve / Refuse / Reset on an expense of a submitted claim → the plain UserError; an expense with no claim still approves by stock. |
| E1.8 | `test_e1_8_ownership`, `_8b_backend_access`, page `test_e1_8_another_persons_claim_is_a_404` | pass. Other person's claim not in `own_claims`; send/withdraw/reopen/status/remove/add/new on it → AccessError, nothing changes; GET → 404 styled ("We could not find that claim"), all five POSTs → 404, unknown id → 404. Employee login: AccessError on a backend search; full account reads only its own; no portal ACL row; a seat holder reads the claim. |
| E1.9 | `test_e1_9_flow_for_an_employee_login`, `_9b_…full_account`, `_9c_refusals_render_the_page`, `test_e1_9a_home_hooks` | pass, both logins. Empty words → new page (drop area, camera input, one chip per category, amount, date = today; trip block shown only when the person has an approved trip — the bridge is installed on p0clone and the fixture trip makes it appear) → no file: reason, nothing created, note/amount kept → POST with `files={'receipt': …}` + `action=send` (forged `employee_id` ignored) → `/my/expenses/<id>?done=sent`, tokened thumbnail 200, amount, "Waiting approval", step name, manager's name, toast "Sent to … (Their manager)." → list card + "1 waiting" → home tile + `expense_count` 0 → refused: home "1 expense claim refused — fix and resend", counter 1, My requests "Refused — your turn" `act`, claim page reason + Fix and resend → reopen → add a receipt → send (attempt 2) → approved: My requests "Approved — being paid" `ok`. Wrong type / zero refused in words; `action=add` → draft + claim page; two receipts in one POST; second receipt's error is "Receipt 2: …"; take back; Send with an empty add-form sends. |
| E1.10 | `test_e1_10_paid`, page `test_e1_10_paid_strip` | pass. Cheapest stock path on the clone: a company-paid expense with a journal entry is "paid" in stock's `_compute_state`; the write is the one stock's posting makes (`account_move_id`). The claim turns `paid`, `paid_on` today, stepper's last step done, list strip "$ 64,000.00 paid this year", green pill. |
| E1.11 | the run above | pb_me_expense 34 green; pb_me_portal 125 with only §6's pin failure and M19 (`test_11_every_icon_name_is_drawn` passes). |
| E1.12 | `TestPoGate` (5) + server parse gate | pass. Three rules, msgstr everywhere, no vendor name; every word of every page template has a VI line for its own view; the code words of pages/home/My requests have a line; `/vi/my/expenses/new` and `/vi/my/expenses` render in Vietnamese in the walk. |
| E1.13 | browser walk | done, below. |

### E1.13 — browser walk (staged clone, 8099 tunnelled, own headless Chrome)
Temporary logins `e1.ui.employee@example.com` (employee login, "Lan Nguyen") and `e1.ui.manager@example.com`
(internal, "Hoa Tran", her manager). Both now **archived with scrambled passwords**; UI server stopped,
tunnel closed.
Employee, desktop: sign-in lands on `/my`, Expenses tile present → `/my/expenses/new`: Send reads "Add a
receipt first" (disabled) → photo chosen: it fills the card with a fade → amount typed "185000" shows
"185,000", Send now says "Pick what it was first" → Meals chip, note, Esc folds the note → "Add another
receipt" adds Receipt 2 in place → PDF + 45,000 + Travel → running total "$230,000.00" → **Ctrl+Enter**
sends → claim page, toast "Sent to Hoa Tran (Their manager).", stepper Sent → Their manager → Finance
approver → Paid → list card. Phone (390 px, touch media emulated): "Take a photo" camera button shows, form
fits, no sideways scroll; list and claim pages.
Manager: backend Approvals inbox → card "Expense claim · Lan Nguyen · 2 receipts" → drawer shows the facts
(amount in USD, 2 receipts, Meals, Travel & Accommodation, not older than 30 days, every receipt has its
photo), the receipt rows and the route → **Turn it down** with a reason → turned down. Backend claim list
opens.
Employee again: `/my` Needs-you row; claim page "Refused. Here is why: The receipt date is cut off…" +
**Fix and resend** → draft with "What to fix, from the last time" → Send for approval → toast "Sent to Hoa
Tran (Their manager)."; phone width; Vietnamese pages.
Console: nothing from these pages. Seen and not ours: the clone's website-logo 500 on every page (known
since T3a), and pb_learn's "translations have not been loaded" warning in the backend (known since T2).
Found by the walk and fixed before the final run: (1) QWeb dropped `data-pbex-block="0"` (a 0 value drops
the attribute), so the first receipt had no preview — now `str()`; (2) on a phone the big amount input's
natural width pushed the form past the screen — `width: 100%` + `minmax(0, 1fr)`; (3) "Send for approval"
on a draft with the add-form left empty posted an empty receipt — the route now just sends (test added).
Screenshots (25, scratchpad `e1walk/shots/`, not versioned): 01-home, 03-new-empty, 04-new-photo-chosen,
05-new-two-receipts, 06-claim-sent, 07-list, 08/09 new on phone, 10 list phone, 11 claim phone, 12a–12e
inbox + turn down + backend list, 13 home needs-you, 14 claim refused, 15 My requests, 16 draft again, 17
resent, 18/19 phone, 20/21 Vietnamese. (02 was retaken after the first claim existed; the empty state was
seen in the first pass — "No claims yet." — and is asserted by the HttpCase.)

## 3. Design self-score
- **Hero moment — the receipt is the card.** The new-claim page opens on one big dashed "Snap or choose a
  receipt" area (drop a file on it on a desktop; on a phone a second "Take a photo" button opens the camera);
  the chosen photo fills the card with a fade (a PDF shows a document glyph and its name, "Choose another"
  sits on it), and How much / What it was / When settle in under it. The amount is 38 px with the currency as
  a quiet prefix and separators as you type; categories are one-tap icon chips; the date is a one-tap pill;
  the note is folded.
- **One solid button**: "Send for approval", which explains itself until it can be pressed (Add a receipt
  first / Type the amount first / Pick what it was first). "Add another receipt" stacks receipts in place
  with a running total.
- **Zero dead-ends**: every refusal is a sentence on the same page with what was typed kept; too big / wrong
  type are said under the drop area before sending; a blocked route is a sentence with Ask HR; refused →
  reason + Fix and resend; draft after a refusal still shows what to fix; another person's claim is a styled
  404; empty states for the list and each filter.
- **Quiet board**: strip "1 need you · 2 waiting · $ 64,000.00 paid this year", chips All / Waiting on you /
  With someone / Done, cards with the receipt thumbnail; the only coloured pill is "Refused — see why".
- **Motion with purpose**: photo fade, fields settle, receipt slides in, pill pops on change, toast with a
  green tick slides in and fades, the fresh card slides into the list; all off under reduced motion.
- **Keyboard**: Cmd/Ctrl+Enter sends, Esc folds the note, j/k/arrows on the list, chips are real radios.
- Self-score **8.5/10**. Short of 10: no OCR (non-goal) so the amount is typed; the stepper shows route step
  names ("Their manager") rather than friendlier words when HR renames nothing; the add-receipt form on a
  draft claim is a full block rather than a compact "+".

## 4. Learn impact
Grepped `learn_content.json`, `anchors.json`, `engine/screens.js`, `engine/fixture.js`,
`docs/tutorial_poc/author/data.js` for `/my`, expenses, claims: the only `/my` mention is "Only an employee?
You start on My Payobook". **Nothing in Learn is affected.**

## 5. Decisions the handover did not make + proposed ledger rows
1. **What the engine does with a missing manager (D2/E-R4)**: the manager step resolves to nobody, the
   request is created **blocked** with "No manager is recorded for the people this is about, so nobody can be
   asked." — the step is never skipped and nothing is approved by itself; the claim and its expenses wait in
   `submitted`. The portal says "Nobody is set up to approve this yet. HR can fix the route." with Ask HR.
   When HR fills in the manager, the engine's own `repair()` (Approvals → stuck request) moves it on.
2. **"Their manager" for an expense** = the expense approver HR set on the employee (stock field), else the
   line manager's login (stock's own order); an archived login or an employee login is not a seat (they
   cannot use the inbox) — the request then blocks with the sentence above.
3. **A company with no expense route gets one on its first send** (idempotent `lay`); only if that fails does
   the claim's own fallback ladder apply (an HR expense approver presses Approve on the backend form).
4. **Finance seat**: seeded only when the finance responsibility was never set up for the company, from
   payroll managers or expense managers (trip seeds from payroll managers alone; whichever runs first wins).
5. **Catalogue row owned by this module** (pb_training's rule), area "Money out", flagged as money.
6. **Sent back** by an approver → draft with the reason shown; an **inbox withdrawal** is mirrored on the claim
   (`_approval_withdraw`; the shim does not do it, ledger E8).
7. **Every receipt needs its file**; the file type is decided from the file's own first bytes (not what the
   browser says); WEBP accepted (pb_me_portal's upload list lacks it, so this module has its own); 20 receipts
   per claim.
8. **Drafts count as "Waiting on you"** on the list and the home tile count; My requests keeps D9's tones
   (draft = off).
9. **`paid_on`** added on the claim (own model) for "paid this year"; "paid" is also re-read when the pages and
   My requests are read, because a payment registered later only changes a computed field.
10. The **refusal reason stays on the draft** after Fix and resend ("What to fix, from the last time") and is
    cleared on the next send.
11. The handover listed Approve / Refuse / Reset for the stock guard; stock **Submit** on an expense inside a
    draft claim is not guarded (no open request yet; the claim's send re-checks everything).

Proposed ledger rows:
| # | Gotcha / fact | How to apply |
|---|---|---|
| E14 | Stock `hr.employee` fills `expense_manager_id` from the manager's login when `parent_id` is set; clearing the manager does not always clear it. "No manager" for an expense means both empty. | Tests and walks of the blocked path clear both fields. |
| E15 | QWeb drops an attribute whose value is `0` (`t-att-data-x="0"` renders nothing), like an empty `t-out` (T25). | Pass `str(value)` for numeric data attributes. |
| E16 | `/web/image/<attachment id>/480x480?access_token=…` and `/web/content/<id>?access_token=…` serve an employee login (200) — verified in an HttpCase. | Use them for receipt thumbnails and full views. |
| E17 | Headless Chrome with `mobile: true` still reports `hover: hover`; `(hover: none)` CSS never applies. | In a walk: `Emulation.setEmulatedMedia({features: [hover none, pointer coarse]})` + touch emulation. |
| E18 | p0clone's company currency is USD (2 decimals); Vietnamese writes `230.000,00`. | Amount parsing and the script use the reader's language separators; tests compare `formatLang` output. |
| E19 | `pgrep -f '<pattern>'` inside `ssh "…"` matches the remote `bash -c` carrying the same pattern, so a wait loop never ends. | Anchor the pattern (`'^/usr/bin/python3 /odoo/odoo-server/odoo-bin.*8099'`). |
| E20 | A module's terms are exported with `trans_export(lang, [module], fh, 'po', env)` from `odoo-bin shell --addons-path=/tmp/deployEx,…` (the `i18n export` sub-command takes no addons path, so it misses a staged module's code terms). | Build the `.po` from that export. |

## 6. Needs a change in a shared module (listed, not done)
- **pb_me_portal `tests/test_me_home.py` `test_02_tile_meta_default_and_hidden`** pins the Me-strip order to
  six URLs; the 19.0.3.4.0 pre-work added `/my/expenses` to the `me` group, so the pin now fails with or
  without this module. Fix: append `'/my/expenses'` to the expected list (one line). E2/E3 add to `time`,
  which this test does not pin.
- Nothing else. (pb_me_portal's `_UPLOAD_MIME_OK` lacks WEBP; this module carries its own list, so no change
  is needed.)

## 7. Self-review
**Scope**
- Module, manifest (name/summary/depends/category/version/hook/assets): done.
- D1 model + fields + `pb_claim_id`: done (+ `receipt_count`, `paid_on` on the own model).
- D2 route, `_chain_*`, no `date_field`, default route via post_init_hook, missing-manager sentence: done.
- D3 send under sudo after the guard, never `action_submit`, `_do_approve` / `_do_refuse` from the claim,
  stock-button guard: done.
- D4 fix and resend (attempt 2): done. D5 take back via the engine: done (+ inbox mirror).
- D6 one receipt = one expense, attachment as main, tokened links: done. D7 categories + own icon template:
  done. D8 trip (soft): done, rendered only when the person has a trip.
- D9 tile, needs-you, My requests: done. D10 backend list/form/menu/ACL/rules, no portal row: done.
- Routes, facade API, VI, Learn: done. Tests E1.1–E1.13: done.
**Non-goals**: no OCR, email-in, mileage (priced categories excluded), foreign currency, card feed, editing a
sent amount, per-expense approval; no edits to pb_me_portal, hr_expense views, pb_trip_expense_bridge or
pb_business_trip; no sidebar item; no stock field beyond `hr.expense.pb_claim_id`: all respected.
**Safety rails**: every sudo write follows `_ex_claim` / the facade's `env.uid` guard; employee, company,
currency, state, approval_state and manager are never read from a request (forged `employee_id` tested);
uploads bounded, sniffed, bound to an existing expense inside one savepoint; only the engine approves; every
POST failure re-renders with words.
**White-label**: no vendor name in any user-visible string (gate on msgstr; manifest name/summary clean).
**Side effects on the clone only**: p0clone has pb_me_expense 19.0.1.0.0 installed, pb_me_portal at
19.0.3.4.0, hr_expense re-upgraded, the expense route laid for "My Company", walk claims EXP/2026/0059 and
0060 (both waiting on the archived walk manager) and two archived walk logins. Live service, port 8069 and
every live database untouched; p1clone/p2clone, their staging dirs and the sibling modules untouched.
