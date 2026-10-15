# ETP E1 — Expenses on My Payobook (handover for Opus)

Read first: `ETP_PROGRAM.md`, `ETP_LEDGER.md` (rules E-R1…E-R13, rows E1–E13), then the TIERS precedents
`../tiers/T3A_HANDOVER.md` + `T3A_REPORT.md` (pb_ask_hr: a new glue module with a portal form, uploads, a My
requests source, a needs-you row, VI) and `../tiers/T3B_REPORT.md` (clone run + tunnelled browser walk). Repo
`CLAUDE.md` applies. You do not deploy; Fable does. Plain words in every string a person can see. **Your clone is
`p0clone`, port 8099, staging `/tmp/deployE1`** (E-R7). Two sibling builds run at the same time on p1clone/p2clone —
never touch their staging dirs, databases or modules (`pb_me_trip`, `pb_me_project_time`) and never edit
`pb_me_portal` (E-R1).

## What E1 is, in the owner's words
"Expenses … on the portal … premium and intuitive and user friendly." After E1 every employee can **claim back
what they paid for from My Payobook**: photograph the receipt, type the amount, pick what it was, send; see where
the claim is; fix and resend a refused one; see what was paid.

## Design (binding, E-R10)
Measured against Expensify / Rydoo / Spendesk on a phone. **Hero moment: the receipt is the card.** The new-claim
page opens on one big dashed "Snap or choose a receipt" area (camera on a phone, file picker on a desktop); the
moment a file is chosen the image appears full-width with a soft fade (PDF → a document glyph with the filename),
and the three fields that matter slide in under it: **How much** (big numeric input, the company currency as a
quiet suffix, thousands separators as you type), **What it was** (category chips, one tap, not a dropdown), **When**
(defaults to today, one tap to change). A one-line note is optional and folded away ("Add a note"). The Send
button is the only solid button on the page and reads "Send for approval"; under it a quiet "Add another receipt"
turns the claim into a multi-receipt claim (receipts stack as cards, total at the bottom). Zero dead-ends: no
file → the amount field still works and the Send button says "Add a receipt first" (disabled, with the reason); too
big / wrong type → the reason under the drop area; the server refuses → the page re-renders with the typed values
kept (ledger T25 for textareas) and the reason in a `pbme` alert.
**The list page** (`/my/expenses`) is a quiet board: a one-line strip "2 waiting · ₫1,200,000 paid this year",
filter chips All / Waiting on you / With someone / Done, then claim cards (receipt thumbnail, title, amount,
status pill, date) newest first; a refused claim is the ONE coloured pill ("Refused — see why") with the reason
on the claim page and a "Fix and resend" button. Empty state: "No claims yet. Snap a receipt and we take it from
there." with the primary button. Motion: the thumbnail fades in; a sent claim's card slides into the list with a
green tick toast "Sent to <step name>". Keyboard: on desktop Cmd/Ctrl+Enter sends; Esc on the note folds it.

## Decisions already taken (do not re-open)
- **D1 The approval carrier is a new model `pb.expense.claim`** (ledger E2): fields `name` (sequence `EXP/%(year)s/`
  padding 4, cloned from `pb_business_trip/data/ir_sequence_data.xml`), `employee_id` (required, index),
  `company_id` (required), `currency_id` (related to company currency, stored), `expense_ids` (One2many
  `hr.expense.pb_claim_id` — a NEW field on `hr.expense`, `index=True`, `ondelete='set null'`, the only field this
  module adds to a stock model), `total` (computed stored: sum of `total_amount_currency`), `state` Selection
  `draft / submitted / approved / refused / paid` (`paid` = every expense `state in ('paid','done')`, recomputed by
  a small `_sync_paid()` called from an `hr.expense.write` override when `state`/`approval_state` changes — keep it
  cheap: only expenses with a claim), `note` Text, `refusal_reason` Text (copied from the engine's reason on
  reject), `submitted_on`, `decided_on`. `mail.thread` for the chatter (`_mail_post_access='read'` not needed —
  nobody but HR reads it in the backend). `_order = 'id desc'`.
- **D2 The engine route**: `register_chain('pb.expense.claim', 'expense', submit_state='submitted',
  driven=('approved',), employee_field='employee_id', amount_field='total', currency_field='currency_id')` + a
  `_chain_*` family cloned from `pb_training/models/claim_approval.py` (title "Expense claim · <who> · <n receipts>",
  facts: `amount` (unit = currency code, AM25), `receipts` (int), `categories` (char, comma list), `has_receipt_file`
  (bool: every expense has an attachment), `over_30_days` (bool: any expense date older than 30 days at
  submission)); `_chain_revision_values` = the sorted list of (expense id, amount, attachment id). **No
  `date_field`** (read the long comment in claim_approval.py about the live defect). Default route laid by
  `post_init_hook` for every company and by a `migrations/19.0.1.0.0/post-expense_approval.py`-style script is not
  needed on first install — clone `pb_business_trip/models/pb_business_trip_approval.py:94-109` + `__init__.py:11-13`:
  `route(manager_step(_('Their manager')), role_step(_('Finance approver'), 'finance'))`. Read how the engine treats a
  manager step when the employee has no manager user (search `manager_step` in `chain_shim.py` and the engine's
  `blocked` state / `repair()`), and make the portal SAY it (E-R4): a blocked request shows "Nobody is set up to
  approve this yet. HR can fix the route." with an Ask HR link when pb_ask_hr is installed (soft check `'pb.ask.hr.ticket' in self.env`).
- **D3 What "send" does, under sudo after the guard** (E-R2/E-R3): claim must be `draft` and have ≥ 1 expense,
  every expense `total_amount_currency > 0` and `product_id` set and an attachment; then for each expense
  `expense.sudo().write({'approval_state': 'submitted', 'manager_id': False})` (never `action_submit`, ledger E1)
  and `claim.sudo().action_submit()` → the shim → engine. On `_approval_apply` (via the chain's driven `approved`):
  each expense `sudo()._do_approve()` — read its exact signature at `hr_expense.py:1440-1450` on the server copy
  (`sudo -n sed -n 1430,1480p /odoo/odoo-server/addons/hr_expense/models/hr_expense.py`) and pass what it needs;
  `approval_date`/`manager_id` as stock writes them. On reject (`_approval_reject` / the chain's refused path —
  read how `register_chain` maps a refusal, `chain_shim.py`): each expense `sudo()._do_refuse(reason)`, the claim
  `refused` + `refusal_reason`. Stock `hr.expense.action_approve / action_refuse / action_reset` on an expense whose
  claim has an open request raise `UserError(_("This receipt is part of claim %s. Decide it from Approvals."))`
  (precedent `pb_timeoff/models/hr_leave_approval.py:334-375`); without an open request stock behaviour is untouched.
- **D4 Fix and resend**: a `refused` claim → "Fix and resend" → claim back to `draft` (expenses `sudo()._do_reset_approval()`
  or the equivalent that puts `approval_state` back to… read `:1452` and what draft means in `_compute_state`),
  the person edits/removes receipts, sends again (`attempt` 2 in the engine — the engine counts it).
- **D5 Withdraw**: a `submitted` claim can be withdrawn by its owner ("Take back") → `engine.cancel`-style
  withdrawal — read `biz_approval_workflow/models/engine.py:1458-1486` and the shim's state write that withdraws an
  open request (`chain_shim.py:666-708`); the claim returns to `draft`, expenses to their draft approval state.
- **D6 One receipt = one `hr.expense`** created under sudo with: `name` (category name + date unless a note is
  given), `date`, `employee_id` = the session employee, `company_id` = the employee's company, `product_id`,
  `currency_id` (company currency in this release — a currency picker is a non-goal), `total_amount_currency`,
  `payment_mode` (`own_account`; a "Paid with a company card" toggle sets `company_account`), `description` = note,
  `pb_claim_id`. Then the attachment: `ir.attachment` sudo create (`res_model='hr.expense'`, `res_id`, `datas`),
  `expense.sudo()._message_set_main_attachment_id(att, force=True)` (ledger E4). Receipts render through
  `/web/image/<att.id>/480x480?access_token=…` (thumb) and `/web/content/<att.id>?access_token=…` (full), tokens via
  `att.sudo().generate_access_token()[0]` (E-R6).
- **D7 Categories**: `product.product` sudo search `[('can_be_expensed','=',True), ('company_id','in',[False, emp.company_id.id])]`
  ordered by name, minus any product with a non-zero `standard_price` for that company (Mileage, ledger E5).
  Shown as chips with a small glyph per code (FOOD → `utensils`, TRANS & ACC → `car`, COMM → `phone`, GIFT →
  `gift`, else `receipt`) drawn by the module's OWN icon template `pb_me_expense.ex_icon` (E12).
- **D8 Which trip** (soft, no dependency): when `'pb_trip_id' in self.env['hr.expense']._fields` and
  `'pb.business.trip' in self.env`, the new-claim form offers "Which trip was this for?" listing the employee's own
  trips with `state == 'approved'` and `date_to >= today - 60 days` (sudo search filtered on the session employee);
  chosen → `pb_trip_id` on each expense of the claim. Otherwise the block is not rendered.
- **D9 Home**: tile `/my/expenses` (already in the registry — draw it with `portal_docs_entry` guarded
  `t-if="pbme_home"`, `placeholder_count` = claims waiting on the person); needs-you row via `_pbme_needs_extra`
  (`act`, "1 expense claim refused — fix and resend" → `/my/expenses/<id>`); My requests source via
  `_my_requests_sources` (`key='expense_claim'`, model `pb.expense.claim`, states `draft→('Draft','off')`,
  `submitted→('Waiting approval','wait')`, `approved→('Approved — being paid','ok')`, `paid→('Paid','ok')`,
  `refused→('Refused — your turn','act')`, `url` → the claim page, `title` → "Expense claim · ₫1,200,000 · 2 receipts").
- **D10 Backend**: a plain list + form for `pb.expense.claim` (name, employee, total, state, expenses tab, chatter)
  under the stock Expenses menu — admin fallback only, `groups="hr_expense.group_hr_expense_team_approver"`; no
  cockpit, no sidebar item (T27: the rail is a closed spec — do not add one). ACL: `base.group_user` 1,1,1,0 on the
  claim (so staff can see their own in the backend), team approver 1,1,1,1, company rule + own-or-approver rule
  cloned from `hr_expense/security/ir_rule.xml` `ir_rule_hr_expense_employee`'s shape; **no portal row** (E-R2).

## Scope (binding)
Module `pb_me_expense`: name "Employee Self-Service Portal — expenses", summary "Claim back what you paid for,
from My Payobook", depends `['pb_me_portal', 'hr_expense', 'biz_approval_workflow', 'pb_approval_config']`
(check that pb_training's manifest lists the same approval modules; mirror it), `auto_install: True`, category
Hidden/Tools, version `19.0.1.0.0`, `post_init_hook`, assets in `web.assets_frontend` only (scss + one
interaction `static/src/interactions/expense_form.js`: preview, amount formatting, chips, Cmd+Enter, "Add another
receipt" without reload — the no-JS path is a second POST that adds a receipt and re-renders).
Routes (`controllers/portal.py`, class extending `PbMePortal`):
- `GET /my/expenses` (list; `?filter=act|wait|done`), `GET /my/expenses/new`, `POST /my/expenses/new` (creates the
  draft claim + first receipt; `action=send|add` decides whether to send now or stay in draft to add more),
  `GET /my/expenses/<int:id>` (claim page: receipts as cards, status stepper from the request's steps when one
  exists — read `biz.approval.request.step` / `seat` names the way pb_business_trip's `approval_widget_json` does —
  the refusal reason, the buttons the state allows: Send / Add receipt / Remove receipt / Take back / Fix and
  resend), `POST /my/expenses/<id>/receipt` (add), `POST /my/expenses/<id>/receipt/<int:exp>/remove` (draft only),
  `POST /my/expenses/<id>/send`, `POST /my/expenses/<id>/withdraw`, `POST /my/expenses/<id>/reopen` (D4).
  Every POST: ownership guard → sudo → savepoint → redirect with `?done=` / re-render with the reason.
- Facade `pb.me.expense` (AbstractModel) holds the logic so tests can call it without HTTP: `own_claims(emp,
  bucket)`, `categories(emp)`, `trips_for(emp)`, `new_claim(emp, receipt=(name, bytes, mime), amount, product_id,
  date, note, company_card, trip_id)`, `add_receipt(claim, …)`, `remove_receipt(claim, expense)`, `send(claim)`,
  `withdraw(claim)`, `reopen(claim)`, `status(claim)` → `{state, label, tone, step, reason, can: {...}}`.
Translations: `i18n/vi_VN.po` for every string (E-R9). Learn: E-R12.

## Tests (numbered; clone run E-R7; fixtures as T3a: `share_emp` portal login with an employee, `plain` full
account with an employee, `hr` with `hr_expense.group_hr_expense_manager`; a finance role holder for the route —
read how pb_training's tests put someone in the `finance` / `hr_lead` seat and clone it)
- **E1.1** `categories(emp)` lists the can_be_expensed products of the employee's company and the shared ones, not
  another company's, not a priced one.
- **E1.2** `new_claim` as `share_emp`: one `pb.expense.claim` draft, one `hr.expense` with `employee_id` = their
  employee, `company_id` = the employee's company, `pb_claim_id`, `create_uid` = the share user, one attachment with
  `res_model/res_id` and set as main attachment; the receipt URL carries a token and `GET` as the share user is 200.
  Oversize (10 MB + 1) → refused with the plain reason, no claim; wrong type → refused; amount 0 → refused.
- **E1.3** `send` → claim `submitted`, every expense `approval_state='submitted'` and stock `state='submitted'`, one
  `biz.approval.request` (`res_model='pb.expense.claim'`), submitter = the share user; `send` on an empty draft →
  refused; a second `send` → refused ("already sent").
- **E1.4** the route: the manager seat decides (as the manager user, through the engine's own decide method — read
  pb_training's tests) → with finance; finance approves → claim `approved`, every expense `state='approved'`,
  `manager_id` set as stock sets it; refuse with a reason → claim `refused`, `refusal_reason` = the reason, every
  expense `state='refused'`; `reopen` → draft again, expenses back to draft; `send` again → attempt 2.
- **E1.5** no manager user on the employee → what happens is ASSERTED (blocked with the plain sentence on the
  portal, or the step skipped — whichever the engine does) and reported; the portal never shows a bare state.
- **E1.6** `withdraw` on `submitted` → draft, request withdrawn/cancelled, expenses draft; on `approved` → refused.
- **E1.7** stock buttons: `action_approve` on an expense of a submitted claim raises the plain UserError; on an
  expense with no claim stock behaviour is unchanged (a plain expense still approves).
- **E1.8** ownership: `plain`'s claim is invisible to `share_emp` (`own_claims`), `GET /my/expenses/<plain's>` →
  404 (styled), POSTs on it → 404, never a write.
- **E1.9** HttpCase as `share_emp` AND `plain` (T-R6): `GET /my/expenses` 200 (empty-state words) → `GET /new`
  200 (drop area, chips, amount, date = today) → `POST` with `files={'receipt': …}` + `action=send` → redirect to
  the claim page `?done=sent`, page shows the thumbnail (tokened), the amount, the pill "Waiting approval", the
  step name; list shows the card; home `/my` shows the tile with the count and, after a refusal, the needs-you row;
  `/my/requests` shows the row with tone `act` after refusal and `ok` after approval; D8 block absent when the trip
  bridge field is missing on the clone, present otherwise.
- **E1.10** `paid`: set the expenses to paid the way stock does (find the cheapest stock path on the clone —
  `account_move_id` paid or `_compute_state` inputs) → `_sync_paid` → claim `paid`, the list strip says "paid this year".
- **E1.11** Existing suites green: `-i pb_me_expense -u pb_me_portal,hr_expense --test-tags /pb_me_expense,/pb_me_portal`
  (pb_me_portal's `test_11_every_icon_name_is_drawn` must still pass — the three new glyphs are in the registry).
  Known clone artefacts: ledger T31/T35, M19.
- **E1.12** PO gate on `i18n/vi_VN.po`; every page/tile/needs-you/My-requests word has a VI line for its own view.
- **E1.13** Browser walk on the staged clone (tunnelled, T3B_REPORT §T3b.12 recipe; a temporary employee login
  archived after): phone width 390 px AND desktop: new claim with a photo, send, see it in the list, refuse it from
  the backend inbox as the approver, see the reason + "Fix and resend", resend; console clean; screenshots named in
  the report.

## Non-goals (do not do)
- No OCR, no email-in, no mileage, no foreign currency, no company-card feed, no editing of an expense's amount after
  sending (withdraw → edit → resend instead), no per-expense approval, no edits to `pb_me_portal`, `hr_expense`
  views, `pb_trip_expense_bridge` or `pb_business_trip`, no sidebar item, no new fields on stock models beyond
  `hr.expense.pb_claim_id`.

## Safety rails
- Every sudo write sits after the ownership guard; `employee_id`, `state`, `approval_state`, `manager_id` never come
  from the request; the claim id in the URL is re-checked against `_ess_own_employees()`.
- Uploads per E-R5; the attachment is bound only after the expense exists; a failed create unlinks it.
- The engine is the only thing that approves; `_do_approve` is reached only from `_approval_apply`.
- A failure on any POST re-renders with the reason — never a traceback, never a bare 500.

## Report back (write `docs/handovers/etp/E1_REPORT.md`)
1. Files changed/added. 2. E1.1–E1.13 results with the clone log's summary lines and the browser walk. 3. Design
self-score against the bar (hero moment named). 4. Learn impact. 5. Decisions + proposed ledger rows (including
exactly what the engine does with a missing manager). 6. Anything you believe needs a change in a shared module
(listed, not done). 7. Self-review per Scope and Non-goal item.
