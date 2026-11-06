# TIERS T3a — "Ask HR" tickets + "My requests" on My Payobook (handover for Opus)

Read first: `TIERS_PROGRAM.md`, `TIERS_LEDGER.md` (rules T-R1…R12, rows T1–T23), `T2_HANDOVER.md` + `T2_REPORT.md`
(what is live: employee logins are portal/share users; every `/my` seam is sudo after an ownership guard), then the
files named below. Repo `CLAUDE.md` applies (one addons dir; never "Odoo" in a user-visible string). You do not
deploy; Fable does. Plain words in every string a person can see; engineering words in code comments and docs.

T3 is split: **T3a (this)** = Ask HR + My requests + the home hooks they need. **T3b (next)** = clock in/out on the
portal + notices (announcements) on the home. Do not start T3b work.

## What T3a is, in the owner's words
"General employees … raising tickets … and other activities like that … features should be provided in the portal
itself." After T3a an employee (employee login or full account alike) can ask HR a question from My Payobook, see
HR's answer in a conversation on the same page, and see **every** request they ever made (leave, timesheet fix,
profile change, asset, resignation, overtime, Ask HR) in one list with its status. HR answers from a queue in the
backend using the ordinary chatter "Send message".

## Design (binding — the owner's bar, verbatim)
"**extreme WOW, intuitive, out-of-this-world experience, best in class.**" Not "clean and functional" — the screen
should make someone stop. Every surface you build must state and satisfy:
- a **hero moment** (a live preview, a diff that animates in, a grid that feels like a spreadsheet, a single
  reassuring sentence in plain language) — name it in the report;
- **zero dead-ends**: every state (empty, loading, error, partial, huge) is designed, every failure names its reason
  and its next step;
- **plain-language over code vocabulary** on every label, toast and summary;
- **motion with purpose** (enter/exit, progress, state change) — never decorative jitter;
- **keyboard + bulk ergonomics** where rows are involved;
- measured against the best consumer/SaaS tool in that category (Zendesk's help-centre "My requests", Slack's
  thread, Gusto's "Ask"), not against stock.
Concretely for T3a: the look is MEHOME's (`pb_me_portal/static/src/scss/me_portal.scss`: `pbme-*` classes, pbim
tokens from pb_import_kit, Inter, Lucide SVG icons — never emoji, never gradients, never the stock portal table
look). Hero moments: (1) on **Ask HR → New**, the form's first line is a single sentence "Tell HR what you need —
they usually answer within a working day." and the category picker is a row of icon chips, not a `<select>`; (2) the
**ticket page** is a conversation: the employee's messages right-aligned in the brand tint, HR's left with the HR
person's photo (`/my/photo` only serves the person's OWN photo — for HR authors use the initials avatar the home
already draws, no `/web/image`); state is a quiet pill ("With HR", "Answered", "Closed") that animates when it
changes; (3) **My requests** is one timeline grouped by month, each row = kind icon + title + a status pill in the
quiet-board palette (grey at rest, colour only when something waits on the person), with a top strip "2 waiting on
you · 3 with HR · 14 done". Empty states say what the page will show once there is something ("Nothing asked yet.
When you ask HR a question, it lives here with their answer.").

## Decisions already taken (do not re-open)
- **D1 A ticket is a conversation, not an approval.** No biz_approval_workflow for Ask HR. (The engine drops share
  users from every notification, `outbox.py:70`; a ticket needs none of its ladder.)
- **D2 New module `pb_ask_hr`** (depends `pb_me_portal`, `hr`, `mail`, `portal`): the model, the HR queue, the portal
  pages. `pb_me_portal` gains only the hooks (needs-you registry, generic need row, "My requests" page, tiles).
- **D3 Portal seams are sudo after an ownership guard (T-R11).** No `base.group_portal` ACL rows. The ticket's own
  `access_token` (portal.mixin) is what the e-mail link carries; the page itself checks ownership from the session.
- **D4 HR replies with the ordinary chatter "Send message" on the backend form.** A comment (`mail.mt_comment`, not
  a note) from an internal user → state `answered` and the employee is e-mailed by stock mail (they follow the
  ticket); a reply from the employee on the portal → state `with_hr`. Notes stay internal and never show on the
  portal.
- **D5 "My requests" lives in pb_me_portal with soft sources** (`'model' in self.env` guards, like `pb.me.home`'s
  `optional()`); it never adds a dependency. Sources are a list other modules can extend (`_my_requests_sources()`
  super-chain). pb_ask_hr adds its own source.
- **D6 No new stored field on an existing model.** New tables are fine (`pb.ask.hr.ticket`). Configuration (the HR
  owner per company) is an `ir.config_parameter` written from Settings, not a column.
- **D7 Translations ship with the code**: `i18n/vi_VN.po` for pb_ask_hr and the new strings in pb_me_portal, in the
  exact shape the loader needs (below). Green tests prove nothing about `.po` files — follow the three rules.

## Scope (binding)

### 1. Module `pb_ask_hr`
Manifest: name "Ask HR", summary "Employees ask HR from My Payobook; HR answers from one queue", category
"Human Resources", depends `['pb_me_portal', 'hr', 'mail', 'portal']`, `application: False`, version
`19.0.1.0.0`, license LGPL-3, author Payobook, data: security csv + rules xml, views, menu, settings view, mail
templates (if any), `assets`: frontend scss/js under `web.assets_frontend` as pb_me_portal does
(`pb_me_portal/__manifest__.py:57-66`).

**Model `pb.ask.hr.ticket`** (`models/ticket.py`), `_inherit = ['mail.thread', 'mail.activity.mixin',
'portal.mixin']`, `_order = 'last_activity_on desc, id desc'`:
- `name` Char "Subject", required; `number` Char "Number" (`ASK-00042`, sequence `ir.sequence` `pb.ask.hr.ticket`,
  company-scoped); `employee_id` Many2one `hr.employee` required, index; `company_id` related stored from the
  employee (plain `fields.Many2one` with default from employee — compute stored is fine on a NEW model);
  `category` Selection: `pay` "Pay & payslips", `leave` "Leave & attendance", `documents` "Documents & letters",
  `benefits` "Benefits & insurance", `equipment` "Equipment & access", `other` "Something else" — default
  `other`; `description` Html "What you need" (sanitized); `state` Selection `new` "New", `with_hr` "With HR",
  `answered` "Answered", `closed` "Closed", default `new`, tracking; `user_id` Many2one `res.users` "HR owner",
  domain share=False, tracking; `last_activity_on` Datetime (set on create and every public message);
  `answered_on`, `closed_on` Datetime; `closed_by` Selection `employee` / `hr`; `attachment_ids` Many2many
  `ir.attachment` (the employee's files); `portal_url` via `_compute_access_url` → `/my/ask-hr/<id>`.
- `_mail_post_access = 'read'` is NOT needed (we post under sudo from the portal); keep the default.
- `create()`: number, `last_activity_on`, subscribe the employee's `work_contact_id`/`user_id.partner_id` as
  follower (so HR's "Send message" e-mails them with the portal link); if the company's HR owner is set
  (`ir.config_parameter` key `pb_ask_hr.owner_uid.<company_id>`), set `user_id`, subscribe them and
  `activity_schedule('mail.mail_activity_data_todo', user_id=…, summary=…)`; else nothing (the queue is the
  discovery, precedent `pb_profile_change_request.py:265-269`).
- `message_post()` override: after `super()`, when `message_type == 'comment'` and the subtype is not internal
  (`subtype_id.internal` False): author is the employee (author partner == employee's partner, or `self.env.user`
  is the employee's user) → state `with_hr` (unless closed → `with_hr` too: a reply reopens), else (internal user)
  → state `answered`, `answered_on = now`; always `last_activity_on = now`. Keep it in one small method
  `_pb_on_public_message(author_is_employee)` so tests can call it.
- Actions: `action_take()` (assign to me, `new`→`with_hr`), `action_answer_done()` (HR marks answered without a
  message — rare; keep), `action_close()` (`closed`, `closed_by='hr'`, `closed_on`), `action_reopen()`
  (`with_hr`). Employee-side methods for the portal: `_portal_reply(body, attachments)` (sudo caller passes the
  employee; posts a comment with `author_id` = employee's partner, `message_type='comment'`,
  `subtype_xmlid='mail.mt_comment'`), `_portal_close()` (`closed_by='employee'`), `_portal_reopen()` (allowed
  within 14 days of `closed_on`).
- `_portal_messages()`: the public thread for the page — `message_ids` filtered `message_type == 'comment'`,
  `not subtype_id.internal`, ordered date asc; each: author name, `is_employee` (author partner == employee's
  partner), body (sanitized html), date, attachments (tokened URLs `/web/content/<id>?download=true&access_token=`
  via `generate_access_token`, same as T2's documents).
- Security (`security/ir.model.access.csv`): `hr.group_hr_user` 1,1,1,0; `hr.group_hr_manager` 1,1,1,1;
  `base.group_system` 1,1,1,1; `base.group_user` 1,0,0,0 + rule own (`employee_id.user_id = user.id`) read only
  (so a full-account employee can also read their own from the backend chatter e-mail link — but the portal is the
  product surface). Company rule global. **No portal rows.**
- HR owner setting: `res.config.settings` fields `pb_ask_hr_owner_id` Many2one `res.users` (not stored) with
  `get_values`/`set_values` on the parameter `pb_ask_hr.owner_uid.<company_id>`; shown under the existing HR
  settings block (read how pb_me_portal or pb_hr_comm place a settings block; if none, add a small block under
  `hr.res_config_settings_view_form`). Label "Who picks up Ask HR questions", help "New questions are assigned to
  this person and appear on their to-do list. Leave empty to let the HR team pick them up from the queue."

**HR queue (backend)** — design bar applies ("legacy surfaces get upgraded, never left stock"): the queue is a
**kanban grouped by state** (New / With HR / Answered / Closed) with cards showing number, subject, employee name +
photo (backend may use `/web/image/hr.employee`), category chip, "waiting 3 d" age, HR owner avatar; quick action
on the card "Take it". The form view is the native form skinned by the VU form engine (that is the house pattern:
`vu-form` skin applies automatically; do not add `vu-form-native`): header with the state statusbar + buttons Take
it / Close / Reopen; left column the question (employee card, category, description, attachments); right the HR
owner + dates; chatter below — the **chatter is the answer box**, so the form's first line under the title says in
muted text "Reply with Send message. Notes stay private." List view as the secondary view with the same columns.
Menu: under `hr.menu_hr_root` "Ask HR" (sequence after the existing pb_me_portal "Profile changes" menu
`views/profile_change_views.xml:103-108`), groups `hr.group_hr_user`; action default filter "Open" (`state` in
new/with_hr), search filters New / With HR / Answered / Closed / Mine. The left-menu entry must also exist as a
`pb.sidebar.item` if that is how the Payobook left menu is populated (read `pb_sidebar` and how pb_me_portal's
"Profile changes" reaches the menu: grep `item_` in `pb_me_portal/data` / `pb_payhub/data`); if the sidebar is
data-driven, add the item under the People section with icon `message-circle-question` (Lucide).

**Portal pages** (`controllers/portal.py`, class extending `CustomerPortal`, helper `_ess_employee()` cloned from
`pb_me_portal/controllers/portal.py:34-43` or imported from a shared helper if pb_me_portal exposes one — read it):
- `GET /my/ask-hr` — list: strip "1 answered · 2 with HR · 5 closed", tabs Open / Closed, rows (subject, category
  chip, state pill, last activity "2 h ago", unread marker when HR answered after the employee's last message),
  button "Ask HR".
- `GET /my/ask-hr/new`, `POST /my/ask-hr/new` — category chips, subject, description (plain textarea, newlines →
  paragraphs; no rich editor), up to 3 files (reuse pb_me_portal's upload checks: size/type from
  `/my/documents/upload` `:254-316`), creates under sudo with `employee_id` forced from the session; redirect to
  the ticket page with a toast "Sent to HR".
- `GET /my/ask-hr/<int:id>` — ownership guard (sudo browse, `employee_id == _ess_employee()` else 404); the
  conversation; reply box (textarea + up to 3 files) `POST /my/ask-hr/<id>/reply`; "That solved it" `POST
  /my/ask-hr/<id>/close` (when not closed); "Reopen" `POST /my/ask-hr/<id>/reopen` (closed < 14 days). Each POST
  redirects back with `?done=…` and the page renders the toast. Errors render the page with the reason (never a
  500, never a stock error page): use pb_me_portal's error pattern (the `pbme-empty-ic--err` block T2 tests look
  for; read `pb_me_portal/views/portal_templates.xml` for the markup).
- `?access_token=` on the ticket page: accepted via `_document_check_access('pb.ask.hr.ticket', id, token)` so the
  e-mail link works for a signed-in person whose session employee matches **or** whose token matches; still
  `auth='user'`.
- Breadcrumbs + the `pbme-*` layout as the other `/my` pages (`no_breadcrumbs` logic in `portal_my_home_ess`).
- Tile on the home: inherit `portal.portal_my_home`, `portal.portal_docs_entry` with `url='/my/ask-hr'`, title
  "Ask HR", subtitle "Questions and answers", `placeholder_count='askhr_count'`; and a row in pb_me_portal's
  `_TILE_ROWS` (item 2) so it lands in the right section with its icon.
- Needs-you: via the hook in item 2, a row "HR answered your question" (count of tickets in `answered` whose last
  public message is HR's) linking to `/my/ask-hr`.

### 2. `pb_me_portal` hooks + "My requests"
- **Needs-you registry**: `pb.me.home._pbme_needs(emp)` (`models/pb_me_home.py:509-573`) stays; add
  `_pbme_needs_extra(self, emp, put)` (no-op) called at the end before ordering, and make `NEEDS_ORDER` accept
  unknown keys at the end (append in insertion order). `put()` accepts `label`, `sub`, `icon` (Lucide name), `tone`
  for rows the templates do not know; `pbme_need_row` (`views/portal_templates.xml:342-388`) and
  `pbme_need_sentence` (`:144-164`) get a **generic branch** rendering those keys. The known rows are unchanged.
- **Tiles**: add `_TILE_ROWS` entries for `/my/ask-hr` (group `people`, icon `message-circle-question`) and
  `/my/requests` (group `me` or wherever "Profile"/"Documents" sit — read `GROUPS` `:53` — icon `list-checks`);
  `_TILE_WORDS` with `_lt` strings; VI in `i18n/vi_VN.po`.
- **My requests** (`controllers/portal.py` new route `GET /my/requests`, model method
  `pb.me.home.get_my_requests(emp)` or a new abstract `pb.me.requests` — your call, one place): sources via
  `_my_requests_sources()` returning a list of dicts `{key, model, label, employee_field, date_field, state_field,
  states: {value: (label, tone)}, url: callable(rec) → str, title: callable(rec) → str}` — one per installed model:
  `hr.leave` (states confirm/validate1 "Waiting approval" tone `wait`, validate "Approved" `ok`, refuse "Refused"
  `no`, cancel "Cancelled" `off`; url `/my/work/leave`; title `"<type> · <from> – <to>"`), `hr.attendance.correction`
  (draft "Draft" `off`, submitted "With your manager" `wait`, approved "Applied" `ok`, refused "Refused" `no`; url
  `/my/work/timesheet?week=<iso monday of date>`; title "Timesheet fix · <day>"), `pb.profile.change.request`
  (draft "Draft", hr_review "With HR" `wait`, approved "Applied" `ok`, refused "Refused" `no`; url
  `/my/profile/request/<id>`), `pb.asset.request` (draft, submitted "Waiting for the manager" `wait`,
  manager_approved "With HR" `wait`, approved "Approved" `ok`, refused "Turned down" `no`, cancelled; url
  `/my/assets`; title "Asset · <what>"; skip if the model is absent), `pb.resignation` (draft, submitted "With the
  manager" `wait`, manager_ok "With HR" `wait`, approved "Accepted" `ok`, refused "Not accepted" `no`, withdrawn
  "Withdrawn" `off`; url `/my/resignation`), `hr.overtime.request` (draft, submitted "Waiting approval" `wait`,
  approved `ok`, refused `no`; url `/my/work/overtime`; title "Overtime · <date>"), and pb_ask_hr adds
  `pb.ask.hr.ticket` (new "Sent" `wait`, with_hr "With HR" `wait`, answered "Answered — your turn" `act`, closed
  "Closed" `off`; url `/my/ask-hr/<id>`). Facts for each model are in `T3_SCOUT` §4 (states, fields, orders) —
  the scout's table is reproduced at the end of this file. Every read is `sudo()` keyed on `employee_id = emp.id`
  (T-R11); each source wrapped in the same `optional()` savepoint so one broken source never blanks the page.
  Page: top strip (counts by tone), filter chips (All / Waiting on you / With someone / Done), rows grouped by month
  of the sort date, 50 per page with "Show earlier". Tone `act` = colour (the person must do something), `wait` =
  quiet amber dot, `ok`/`off` = grey (quiet-board palette: grey at zero, colour only to act).
- Version `pb_me_portal` → `19.0.3.2.0` (+ `test_06_font` pin, ledger T7).

### 3. Translations (D7) — the three rules a PO entry needs or it crashes / stays English
1. `#. module: <name>` first line of the comment — missing → the registry load CRASHES.
2. `#. odoo-python` or `#. odoo-javascript` marker AFTER the module line — missing → silently dropped.
3. `#: code:addons/<module>/<path>:0` occurrence (or `#: model:ir.model.fields,field_description:…` for fields /
   `#: model_terms:ir.ui.view,arch_db:<module>.<view_id>` for views) — missing → dropped.
Copy the shape of `pb_me_portal/i18n/vi_VN.po` entries. Run the parse gate on your files before reporting:
`python3 -c "import sys; sys.path.insert(0,'/odoo/odoo-server'); from odoo.tools.translate import PoFileReader; [list(PoFileReader(open(p,'rb'))) for p in sys.argv[1:]]" <po files>` on the server (or locally with the Odoo 19 checkout at `/Users/adity/odoo19/odoo`).

### 4. Learn (standing rule: lessons follow screen changes)
Grep `pb_learn/static/content/learn_content.json`, `pb_learn/static/src/anchors.json`, the replicas in
`pb_learn/static/src/engine/{screens,fixture}.js` and `docs/tutorial_poc/author/data.js` for `/my` and the employee
home. If a lesson describes the home's tiles or Needs-you, update its EN + VI words for the two new tiles; do not
write new lessons. Report what you found (or "nothing in Learn is affected").

### 5. Tests (numbered; clone run T-R9)
Fixtures: `share_emp` (portal user + employee, from `pb_me_portal/tests/test_portal_accounts.py` `_make_share`),
`plain` (internal + employee), `hr` (internal + `hr.group_hr_user`). HttpCases pin `dbfilter` (ledger T6).
- **T3.1** model: create → `new`, number `ASK-…`, employee partner follows; `_pb_on_public_message(True)` → `with_hr`;
  `(False)` → `answered` + `answered_on`; `action_close` → `closed`/`hr`; `_portal_reopen` within 14 days →
  `with_hr`; after 14 days → UserError with plain words.
- **T3.2** `message_post` as `hr` with `subtype_xmlid='mail.mt_comment'` → `answered`, a `mail.mail`/notification
  exists for the employee's partner; `message_post` as `hr` with `mail.mt_note` → state unchanged, not in
  `_portal_messages()`.
- **T3.3** HttpCase as `share_emp`: `GET /my/ask-hr` 200 (empty state words); `POST /my/ask-hr/new` with a
  category, subject, text and one small PDF → ticket exists for their employee, `create_uid` = share user (sudo
  keeps uid), attachment bound, redirect to `/my/ask-hr/<id>`, page shows the message and "Sent" pill; `POST
  …/reply` → second message, state `with_hr`; as `hr` on the backend `message_post` comment → page shows HR's
  reply left-aligned, pill "Answered", needs-you row on `/my` "HR answered your question"; `POST …/close` →
  "Closed"; `POST …/reopen` → `with_hr`. Another person's ticket → 404, never 500. Same flow as `plain` passes.
- **T3.4** `GET /my/ask-hr/<id>?access_token=<wrong>` as the owner → 200 (session owns it); as another employee
  with the right token → 200; wrong token + not owner → 404.
- **T3.5** HR owner parameter set → ticket `user_id` set, activity scheduled for them, they follow; unset → no
  owner, no activity.
- **T3.6** My requests, TransactionCase: with one record of each installed source (create them sudo with minimal
  fields — read each model's required fields; skip a source whose module is absent) `get_my_requests(emp)`
  returns one row per record with the right label/tone/url and sorted by date desc; a broken source (patch one
  source's `title` to raise) is skipped with a warning and the others still return.
- **T3.7** HttpCase as `share_emp` and `plain`: `GET /my/requests` 200, the strip counts match, filter chips work
  (`?filter=act`), month groups render, empty state words when nothing.
- **T3.8** Needs-you generic branch: `put('t3_probe', 1, '/my/requests', label='Probe', sub='x', icon='bell')`
  renders without error and appears last; existing rows unchanged (T2's home tests still pass).
- **T3.9** Tiles: `tile_meta('/my/ask-hr')` and `('/my/requests')` return their group/icon; `/my` as `share_emp`
  shows both tiles in their sections.
- **T3.10** Backend: `hr` opens the Ask HR action (`ir.actions.act_window` loads, kanban + form views parse,
  `get_views` ok); `action_take` assigns; access: `plain` can read own ticket, cannot read another's, cannot
  write; `share_emp` has no ACL at all (AccessError on `search` without sudo — asserts D3).
- **T3.11** PO gate passes for `pb_ask_hr/i18n/vi_VN.po` and `pb_me_portal/i18n/vi_VN.po`.
- **T3.12** Existing suites green: pb_me_portal (T1/T2 tests), pb_me_portal_website; name the known M19 error.
  Clone: `-i pb_ask_hr -u pb_me_portal --test-tags /pb_ask_hr,/pb_me_portal,/pb_me_portal_website` (the clone
  command and the `/home/ubuntu` log trick are in ledger T-R9/T17; stage pb_ask_hr + pb_me_portal into
  `/tmp/deployMH` — and keep the OTHER modules already staged there from T2 in place, or re-stage all of
  `pb_me_portal pb_me_portal_website biz_access pb_zoho_bridge pb_demo pb_ess_workforce pb_ask_hr` so the badge
  test's neighbour (`pb_schedule`) stays absent only where it already was; the `TestP8Badges` staging artefact is
  known, ledger-worthy, not yours).
- **T3.13** Browser check on the clone (port 8099 tunnelled, as T2 did): as a temporary employee login walk Ask HR
  (new → reply → close → reopen) and My requests; as a temporary HR user walk the kanban + form + "Send message";
  console clean. Archive the temporary logins after (T2's practice).

## Non-goals (do not do)
- No clock in/out, no notices/announcements (T3b). No approvals engine on tickets (D1). No portal ACL rows (D3).
- No change to pb_ess_workforce, pb_assets, pb_offboarding, pb_hr_workforce, pb_attendance_flow, pb_hr_comm,
  biz_approval_workflow, hr, mail, portal — My requests reads them softly.
- No SLA timers, no satisfaction rating, no public knowledge base, no ticket re-assignment UI beyond "Take it" +
  the owner field, no e-mail-in channel.
- No new stored field on an existing model (D6). No vendor name in any user-visible string.

## Safety rails
- Every sudo write in a `/my` route sits after the ownership guard and forces `employee_id` from the session.
- Uploads reuse pb_me_portal's size/type checks; attachments are bound to the ticket (`res_model`/`res_id`) and
  downloaded only with their token.
- `_portal_messages()` never returns internal notes (`subtype_id.internal`) or non-comment messages.
- The reply/close/reopen POSTs are idempotent-safe: a second submit of a closed ticket's close shows "Already
  closed", never an error.

## Report back (write `docs/handovers/tiers/T3A_REPORT.md`)
1. Files changed/added, one line each. 2. T3.1–T3.13 results with the clone log's summary lines and the browser
walk (screens visited, console). 3. Design self-score against the bar (hero moments named, dead-ends, motion). 4.
Learn impact. 5. Decisions the handover did not make + proposed ledger rows. 6. Self-review, one line per Scope and
Non-goal item.

## Appendix — scout facts for the "My requests" sources (checked 2026-10-15)
| Model (file:line) | State field and values | Employee field | Sort date | Portal page today |
|---|---|---|---|---|
| `hr.leave` (stock `hr_holidays/models/hr_leave.py`) | `state` :129-134 confirm / refuse / validate1 / validate / cancel | `employee_id` :153 | `date_from` :172 (`request_date_from` :212) | `/my/work/leave` (`pb_ess_workforce/controllers/portal.py:125`) |
| `hr.attendance.correction` (`pb_attendance_flow/models/attendance_correction.py:41`) | `state` :77-82 draft / submitted / approved / refused | `employee_id` :49 | `date` :58 | shown per day on `/my/work/timesheet` |
| `pb.profile.change.request` (`pb_me_portal/models/pb_profile_change_request.py:61`) | `state` :87-92 draft / hr_review / approved / refused | `employee_id` :69 | `create_date` | `/my/profile/request/<id>` |
| `pb.asset.request` (`pb_assets/models/asset_request.py:22`) | `state` :59 draft / submitted / manager_approved / approved / refused / cancelled | `employee_id` :31 | `needed_by` :43 | none |
| `pb.resignation` (`pb_offboarding/models/resignation.py:54`) | `state` :109 draft / submitted / manager_ok / approved / refused / withdrawn | `employee_id` :64 | `submit_date` :75 | `/my/resignation` |
| `hr.overtime.request` (`pb_hr_workforce/models/overtime_request.py:22`) | `state` :76-80 draft / submitted / approved / refused | `employee_id` :28 | `date` :38 | `/my/work/overtime` |
Home plumbing: `pb.me.home.get_home_data` `pb_me_home.py:224-259`, `optional()` `:187-212`, `_pbme_needs` `:509-573`,
`NEEDS_ORDER` `:63-68`, `_TILE_ROWS` `:75-114`, `_TILE_WORDS` `:119-142`, `tile_meta` `:172-184`; templates
`pbme_bento` `portal_templates.xml:174-213`, `pbme_need_row` `:342-388`, `pbme_need_sentence` `:144-164`,
`portal_docs_entry_pbme` `:80-105`; tile precedent `pb_assets/views/portal_templates.xml:16-23`; VI
`pb_me_portal/i18n/vi_VN.po` (`_lt` entries tagged `code:addons/pb_me_portal/models/pb_me_home.py:0`).
Stock portal thread facts (not used — D4 renders our own): `/mail/message/post` `mail/controllers/thread.py:209-238`,
token check `portal/utils.py:16-17`, `portal.mixin` `_portal_ensure_token` `portal/models/portal_mixin.py:34`.
