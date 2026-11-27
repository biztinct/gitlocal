# JOINING — build handover

**For:** the coding session that builds, tests and releases the Joining portal.
**Design:** `JOINING_DESIGN.md` (what the user sees — binding). **Facts:** `JOINING_FACTS.md` (plumbing — do
not re-derive). **Rules and gotchas:** `JOINING_LEDGER.md` (binding; append to it as you learn).
**Prototype:** `docs/design/joining-portal-poc.html` (look, tone, wording; the design doc wins on differences).

Quality bar, verbatim from the owner: **"exceptional premium, extreme WOW, a novice can work without
training"**, and "the style and theme in sync with our existing design".

---

## 0. Before you write code

1. Work in a **new git worktree** from `origin/19.1` (branch `joining`). Never in
   `/Users/adity/Documents/GitHub/gitlocal` itself (FACTS F0).
2. `git cherry-pick 840036012` if `tools/release.sh` is missing on your base (FACTS F0).
3. Copy `docs/handovers/joining/` and `docs/design/joining-portal-poc.html` from the main checkout into your
   branch; commit as `JOINING docs: design pack`.
4. Read, in this order: `JOINING_LEDGER.md`, `JOINING_DESIGN.md`, `JOINING_FACTS.md`, then
   `docs/handovers/newhire/NEWHIRE_LEDGER.md` and `docs/handovers/recruit/RECRUIT_LEDGER.md` (their numbered
   gotchas are referenced here as NHnn / RCnn), then `CLAUDE.md` (deploy contract).
5. Find the local run/test recipe in `docs/handovers/newhire/NEWHIRE_FACTS_CORE.md:486-492` and get a baseline:
   run the suites of `pb_hiring`, `pb_new_hire`, `pb_onboarding` **before any change** and record the failures.
   Only the same failures are acceptable afterwards.

## 1. Scope

Build one new module **`pb_joining`** ("Joining portal") plus the smallest possible seams in existing modules.

In scope:
- A. Joining record + items + signed papers (staging; never the employee record).
- B. Public phone pages at `/join/<token>` with one-time code, sections, uploads, signing, send.
- C. Trigger on offer signed; follow first-day changes and did-not-join; "Invite someone".
- D. The Joining board as a tab in the Hiring hub and the People hub; drawer; accept / send back; link strip;
  first-day details; papers-to-sign settings; ⌘K row.
- E. Landing in Add employee: a third step-5 way "From {first name}", files and signed papers carried by new
  legs, the "From Hiring" tile chip, joining closed on add.
- F. Emails (4), reminders, HR nudges, erase-after-close job.
- G. en + vi_VN + id_ID; tests; browser walks; release to five databases.

### Binding non-goals

- N1. **No write to `hr.employee`, `hr.contract`, `res.partner.bank`, `pb.employee.document` or any `/my`
  change-request model from `pb_joining` outside the Add employee pipeline.** Values land only through
  `pb.new.hire.send` → proposal → legs.
- N2. No second catalogue of fields, bank rules or validation. Use `pb.new.hire`'s step-5 catalogue and
  `pb.bank.format` (FACTS F7, F8).
- N3. No card reading / OCR. No SMS or WhatsApp sending. No 7/30/60/90 check-ins. No trial-period reminder.
- N4. No change to the existing after-hire welcome link (`pb.new.hire.invite`, `/my/welcome`), the Joiners
  board, or any `/my` form.
- N5. No change to `pb.journey.case` (it still needs an employee). The welcome checklist still starts at Add.
- N6. No new system package or Python dependency on the server. No new Odoo standard-module dependency (the
  shared addons directory means a new dependency can break other databases — RC68/RC70).
- N7. No edit inside `pb_hiring`'s core flow. Extend by `_inherit` from `pb_joining` (precedent:
  `pb_new_hire/models/hiring.py:706`). Edits to `pb_new_hire` are allowed **only** to add an extension seam that
  does not exist (see §4.5) — list each one in the report.
- N8. Never deploy, restore or touch the `abm` database. Never deploy this repo's copies of standard addons.
- N9. The word "Odoo" never appears in anything a user can see (labels, help, toasts, emails, public pages,
  manifest `name`/`summary`, `.po` msgstr). Technical identifiers are untouched.
- N10. No credentials, real personal data or client names in the repo. Demo records are prefixed `DEMO`.

## 2. How the four old objections are answered (do not weaken)

| Old objection (FACTS F9) | Answer in this build |
|---|---|
| Token pages never expire, no rate limit, no CSRF | Link expiry (§3.3), per-record + per-address limits (§3.4), session-bound pages with `csrf=True` on every POST. |
| `/my` write entry points refuse non-employees | They are not called. Staging only (N1). |
| Would need sudo entry points and rebuild five forms | One staging model; forms rendered from the single catalogue; values enter through the studio's own `send`. |
| Who proposed the bank account? | The HR person who presses Add in the studio — exactly as "I have it" today. The second-person rule is unchanged. |

## 3. Data model and security (`pb_joining`)

Manifest: name "Joining portal", summary "New people send their own details before day one", version
`19.0.1.0.0`, depends `pb_new_hire`, `pb_hiring`, `pb_people_hub`, `pb_onboarding`, `pb_filter_kit`,
`pb_import_kit`, `pb_hub`, `website` only if `pb_hiring` already pulls it (it does via
`website_hr_recruitment`). `web.assets_backend`: board scss/js/xml, studio patch. `web.assets_frontend`:
`joining_page.scss`, `joining_page.js`. Explicit file lists, no globs.

### 3.1 Models

**`pb.joining`** (mail.thread for history; `_order = 'first_day, id'`)

| Field | Type | Notes |
|---|---|---|
| `name` | Char, required | the person's full name |
| `company_id` | M2o, required, index | |
| `origin` | Selection `hiring` / `invited` | |
| `offer_id` | M2o `pb.hiring.offer`, index, ondelete set null | unique when set (SQL partial index or constraint) |
| `applicant_id` | related `offer_id.applicant_id`, stored | |
| `job_title` | Char | from `offer.job_title` or the invite |
| `job_id`, `department_id`, `manager_id` | M2o | from the requisition / invite |
| `payroll_country` | Char(2) | Country of work code, same meaning as the studio's `payroll_country` |
| `first_day` | Date, required | follows `offer.expected_join_date or start_date` |
| `email`, `phone` | Char | personal contact |
| `lang` | Char | applicant `pb_lang`, else company partner lang |
| `state` | Selection `invited` / `filling` / `to_check` / `added` / `cancelled` | board steps 1–4 + closed |
| `token` | Char, index, copy=False | `secrets.token_urlsafe(32)`; `groups='base.group_system'` |
| `opened_at`, `last_seen_at`, `submitted_at`, `added_at`, `cancelled_at` | Datetime | |
| `link_sent_at`, `link_copied_at`, `link_mode` (`email` / `pass_on`) | | drives the "Link to pass on" chip |
| `reminded_at`, `remind_count`, `hr_nudged_at` | | |
| `code_hash`, `code_until`, `code_tries`, `code_issued_at`, `code_issue_count`, `code_window_start`, `code_locked_until`, `code_by_hr` | | §3.4; all `groups='base.group_system'` |
| `item_ids` | O2m `pb.joining.item` | |
| `sign_ids` | O2m `pb.joining.sign` | |
| `day_time`, `day_place`, `day_ask_for`, `day_bring`, `manager_note` | Char/Text | first-day details |
| `employee_id`, `proposal_id` | M2o | set by the studio pipeline |
| `progress`, `at_risk`, `risk_reason`, `sent_back_count`, `bank_later` | computed, stored | for the board; recompute on item write and daily |
| `cancel_reason` | Char | |

**`pb.joining.item`** — one per catalogue item key per joining (`unique(joining_id, key)`)

| Field | Notes |
|---|---|
| `joining_id`, `key` | key = the catalogue's item key (`personal`, `emergency`, `id_number`, `tax_number`, `tax_status`, `tax_regime`, `tax_fund`, `insurance`, `bank`, `paper-<cat_id>`) |
| `values` | Json — exactly the studio's `have` shape for that item (`{field: value}`; bank uses the `BANK_CHECK` keys). JSON-plain (NH8). |
| `none_fields` | Json list — fields the person ticked "I do not have one yet" |
| `attachment_ids` | M2m `ir.attachment` (files on `res_model='pb.joining.item'`, `public=False`, no access token) |
| `issue_date`, `expiry_date`, `no_expiry` | for papers / ID card |
| `state` | `empty` / `saved` / `later` / `accepted` / `returned` |
| `return_note`, `decided_by_id`, `decided_on` | |
| `from_hiring` | Boolean — Hiring already holds this paper (from `_received_for`) |

**`pb.joining.paper`** — the company's papers to sign: `name` (translate), `company_id`, `country_code`
(blank = all), `attachment_id` (PDF), `sequence`, `active`.

**`pb.joining.sign`** — `joining_id`, `paper_id`, `paper_name` (copied), `paper_sha256`, `signature`
(Binary attachment=True, PNG), `signer_name`, `signed_on`, `ip`, `user_agent`, `signed_attachment_id`
(original PDF + one signing page, merged with `odoo.tools.pdf.merge_pdf`). The signing page is a QWeb PDF
report: paper name, sha256, signer name, date/time (company timezone), the signature image, "Signed on a
phone through the joining link sent to {masked contact}".

**`pb.joining.board`** — AbstractModel inheriting `pb.filter.mixin`; the board's only server door (§5).

Settings: company fields `pb_joining_day_place`, `pb_joining_day_bring`; parameters
`pb_joining.auto_invite` (default `1`), `pb_joining.remind_days` (3), `pb_joining.remind_max` (4),
`pb_joining.risk_days` (7), `pb_joining.link_days_after_start` (14), `pb_joining.erase_days` (30).

### 3.2 Access

- `ir.model.access`: internal users get **no** direct access to `pb.joining*`; `base.group_system` full. All
  screens go through `pb.joining.board` methods, which check the gate and then `sudo()` scoped to
  `company_id in env.companies` and re-check every id passed in (precedent FACTS F5 narrow right).
- Gates on `pb.joining.board`:
  - `_can_read()` = `pb.hiring.can_open()` true, **or** lifecycle reader (`pb.onboarding._can_read`), **or**
    `pb_new_hire.group_joiners_board`, **or** passes the studio's `require_hr` test.
  - `_can_manage()` = passes the studio's HR gate (the same test `require_hr` applies,
    `pb_people_advanced/models/newhire_approval.py:43`).
  - `_can_link()` = `_can_manage()` or Hiring `_can_recruit()` for that offer.
- Payload rule: for a reader who is not `_can_manage()`, item rows carry `key, label, state` only — **no
  `values`, no files, no reveal**. Enforce in the payload builder, test it.
- Record rules: company rule on every model anyway (defence in depth).
- Public controllers use `sudo()` on exactly one record resolved from the token, after the session check.

### 3.3 Link lifecycle

`_for_token(token) -> (record|None, status)` with status `invalid | closed | ok`:
- `invalid`: token shorter than 20 chars, unknown, `cancelled` more than `erase_days` ago, or today >
  `first_day + link_days_after_start`. `closed`: `cancelled`. Both render the same "not active" page.
- A bad-link counter per client address (10 per 600 s, in-memory — precedent
  `pb_lifecycle/controllers/token_pages.py:35-55`) answers the same page while tripped.

### 3.4 One-time code (write this part with care; unit-test every branch)

- 6 digits from `secrets.randbelow(10**6)`, zero-padded. Stored only as
  `sha256(f"{token}:{code}")` hex in `code_hash`; compare with `hmac.compare_digest`.
- **Person-requested code** (email): valid 10 minutes; issue at most 1 per 60 s and 5 per rolling hour per
  joining (`code_issue_count`, `code_window_start`). Issued automatically on the first GET of the code screen
  when none is live and email is possible; again on "Send me a new code".
- **HR-shown code** (`board.show_code`): valid 48 hours, single use, `code_by_hr=True`; issuing cancels any
  live code; returned once to the caller, never stored in clear, logged on the joining's history ("Code shown
  by {user}") without the digits.
- Verify: `code_tries += 1` first; 5 wrong → clear the code, `code_locked_until = now + 15 min`. Success →
  clear the code, set `request.session['pbj'] = {str(joining.id): expiry_ts}` (14 days) and `opened_at`.
- Every page and POST after the code screen requires that session entry for that joining and not expired;
  otherwise redirect to the code screen. The link alone reveals only: company name/logo, the person's first
  name, the masked contact.
- Emails with a code are created and sent immediately (`mail.mail` + `send()`), never left in a queue, and the
  code is not written to chatter or logs.
- Never log a code, a token, or an item value at INFO.

### 3.5 Other rails

- All POST routes: `methods=['POST'], csrf=True`. All routes `auth='public', website=True, sitemap=False`.
  Add `X-Robots-Tag: noindex` and `Cache-Control: no-store` on every response; `Referrer-Policy: no-referrer`.
- Sensitive fields (`pb_new_hire` `SECRET_FIELDS` + `account_number` + every insurance/tax number) are never
  rendered back in full on the phone — masked, with "Change".
- Uploads: JPEG/PNG/PDF by sniffed type, ≤ 10 MB each, ≤ 12 files per item, ≤ 50 MB per joining; read
  `MAX+1` bytes; replace = unlink the old attachment.
- Save budget per joining: 120 POSTs / 300 s (precedent `pb_hiring/controllers/request_pages.py:32-56`).
- Erase job: `erase_days` after `cancelled_at`, and `erase_days` after `added_at`, delete item values, files,
  signatures (after `added`, the copies on the employee are the record). Keep the joining row with name,
  dates and state for the board's history.
- Handlers catch everything and render the calm problem page; no traceback reaches a public visitor.

## 4. Architecture by area

### 4.1 Catalogue adapter (the heart of N2)

`pb.joining._catalogue()` returns the sections of DESIGN §5 for this joining by calling the studio's own
step-5 builder for `payroll_country` + company (the function behind `details_options` / `_detail_items`,
FACTS F7) **in sudo with the joining's company**, then:
- drops nothing, renames nothing; groups items into sections by key;
- sets `insurance` askable for the portal (its fields become optional inputs);
- marks papers Hiring already holds using `pb.new.hire._received_for` (FACTS F2) → `from_hiring=True`, not
  asked;
- attaches the bank format specs from `pb.bank.format.specs`/`choices` for the bank section.

`pb.joining.item._save(values, none_fields, files…)` validates with the studio's own checkers
(`_check_value`, `pb.bank.format.check`, `normalise_number` — FACTS F7/F8) and stores the **clean** values.
If the studio's checkers are private methods on the abstract model, call them through
`self.env['pb.new.hire']`; do not copy their bodies. A test asserts that for every country the studio supports,
every catalogue field appears on the phone and round-trips through `_save` to a value the studio's
`_validate_docs` accepts.

### 4.2 Public controller (`controllers/joining.py`) and pages

Clone the structure of `pb_hiring/controllers/joining_pages.py` (language env, one template per state, problem
keys by redirect), with `csrf=True`.

| Route | Purpose |
|---|---|
| `GET /join/<token>` | state router: not-active / code / welcome / hub / sent / day-one |
| `POST /join/<token>/code` | verify |
| `POST /join/<token>/code/new` | new code by email |
| `POST /join/<token>/lang` | set language |
| `POST /join/<token>/start` | leave the welcome screen |
| `GET /join/<token>/s/<key>` | a section page |
| `POST /join/<token>/s/<key>` | save a section (`later=1` for bank) |
| `POST /join/<token>/file` | upload one file for an item (returns JSON for the script, redirect without) |
| `POST /join/<token>/file/remove` | remove one file |
| `GET /join/<token>/paper/<int:paper>` | sign page for one paper |
| `GET /join/<token>/paper/<int:paper>/pdf` | the paper PDF (resolved from the joining's company, never by attachment id alone) |
| `POST /join/<token>/paper/<int:paper>/sign` | sign (signature PNG data URL ≤ 300 KB, name, tick) |
| `POST /join/<token>/laptop` | answers Hiring's open laptop item through `pb.hiring.prejoin`'s own answer method |
| `POST /join/<token>/send` | send to HR / send again |

- Server-rendered QWeb (`views/joining_pages.xml`) on `web.frontend_layout`, website header and footer hidden
  for these pages; root `<div id="wrap" class="pbjp" t-att-lang="page_lang">`. Every form works without
  script; `static/src/js/joining_page.js` (plain JS, no framework) adds: code boxes, upload progress + photo
  downscale, signature pad (pointer events on a `<canvas>`, exported as PNG), "Saved" chip, disabled-button
  hints. The signature pad is the only step that needs script; without it show "Open this page in your phone's
  browser to sign."
- Showing the paper: if the server already has a way to rasterise PDF pages (check for PyMuPDF `fitz` or
  `pdftoppm` — N6 forbids installing one), render pages as images. Otherwise show a large **"Open the paper"**
  button (opens the PDF route in a new tab) above the tick, and record that it was opened. Say which path you
  took in the report.
- SCSS `static/src/scss/joining_page.scss`, prefix `.pbjp-`, literal colours from DESIGN §6.1, Inter + Manrope
  (reuse the self-hosted Inter; add Manrope the way `pb_new_hire` does), `.pbjp [hidden]{display:none!important}`
  (RC72). Mobile-first at 360px; the sticky footer honours `env(safe-area-inset-bottom)`.
- Inline SVG icon template `pbjp_icon` (precedent `pb_hiring/views/joining_pages.xml:14-34`).
- All words come from Python (`_()`), passed to the template as plain values (RC49).

### 4.3 Trigger and Hiring follow-ups (`models/hiring_ext.py`, `_inherit='pb.hiring.offer'`)

- `_on_signed(kind, label, quiet=False)`: `res = super()`; if `not quiet` and the offer's applicant is not
  internal and `flag(env, 'pb_joining.auto_invite', '1')`: `leg(lambda: env['pb.joining']._open_for_offer(self))`.
- `_open_for_offer(offer)`: idempotent (reuse an existing joining); fill from the offer + requisition
  (FACTS F1); Country of work from `requisition.country_id.code`; build items from the catalogue; then
  `_send_link()`.
- `_send_link()`: when `pb.new.hire.invite._mail_on()` and `email` → send email key `joining_link` and set
  `link_mode='email'`; else `link_mode='pass_on'` and schedule an activity for the offer's recruiter / the
  inviter ("Pass the joining link to {name}").
- `action_change_join_date`: after `super()`, set the joining's `first_day`.
- `action_did_not_join`: after `super()`, `joining._cancel(reason)`. And the reverse: the drawer's "They are
  not joining" on a Hiring joining calls the offer's `action_did_not_join`.
- Add one `BUILTINS` tuple in Hiring's automation list by extending the list from `pb_joining` (if `BUILTINS`
  cannot be extended without editing `pb_hiring`, add the switch to the Joining board's own settings instead
  and report it): sentence "When an offer is signed, send the person their joining link", switch
  `pb_joining.auto_invite`.
- Emails: for Hiring-origin joinings use `pb.hiring.message.template` keys (`selection_add`) `joining_link`,
  `joining_code`, `joining_reminder`, `joining_back`, seeded for installed languages only (RC30, RC92/93),
  sent through `_mail_candidate`. For invited joinings (no applicant) render the same template rows with a
  small local sender that mirrors `_mail_candidate`'s language fallback and `_sender(company)`. One wording
  source, two callers.

### 4.4 Board (`static/src/js/joining_board.js`, `xml/joining_board.xml`, `scss/joining_board.scss`)

Clone `PbOnboardingBoard`'s skeleton (FACTS F5): lock card, header, QuietGlance, QuietSteps, `PbFilterLayout`,
card grid, own `jnb-scrim > jnb-drawer`. CSS prefix `jnb-` under `.pbim.jnb`; only `--pbim-*` variables.

Register the same component twice:
- `registry.category("pb_hiring_hub_lens").add("joining", {key:"joining", icon:"userPlus", label:_t("Joining"),
  title:_t("Joining"), Component: PbJoiningBoard, groups:[…read groups…], probe:{model:"pb.joining.board",
  method:"can_open"}}, {sequence: 30})`
- `registry.category("pb_people_hub_lens").add("joining", {…same…, feature:"lifecycle"}, {sequence: 51})`
- ⌘K: `registry.category("pb_hub_palette").add("joining_board", {…, action:{xmlid: <People hub action
  xmlid>, lens:"joining"}, keywords: "joining joiner new starter pre-boarding onboarding"}, {sequence: 2510})`.

`pb.joining.board` public methods (all gate-checked; ids re-checked; return plain dicts):

| Method | Returns / does |
|---|---|
| `can_open()` | bool |
| `get_board()` | `{allowed, can_manage, kpis:{joining, to_check, at_risk, pass_on, started_week}, steps:[4 counts], mail_on}` |
| `get_page(filters, search, sort, offset, limit)` | `{rows, total, offset}`; row keys: `id, name, initials, job, country, country_code, first_day, first_day_label, days, state, step, progress, chips[{tone, icon, text}], prejoin{done,total}, origin` |
| `get_one(id)` | head + `link{mode, masked, sent_at, copied_at, opened_at, last_seen_at, remind_count, locked}` + `items[{key,label,icon,state,source,fields[{label,value,masked}],files[{id,name,mime,url}],note,decided_by,decided_on}]` + `signs[…]` + `day{…}` + `foot{can_add, waiting_for_person, approval_waiting}` |
| `reveal(id, key, field)` | one clear value, manage only, logged |
| `file(id, attachment_id)` | via a `/pb_joining/file/<id>/<att>` `auth='user'` controller that calls the gate |
| `send_again(id)`, `copy_link(id)`, `show_code(id)`, `remind_now(id)` | rate-limited 1/min per joining per action (precedent `RATE_SECONDS`, `pb_new_hire/models/invite.py:47`); `copy_link` returns the URL; `remind_now` returns `{sent}` or `{message}` (ready text to paste) |
| `accept(id, key)`, `undo(id, key)`, `send_back(id, key, note)`, `accept_all(id)` | manage only; state changes; `send_back` moves the joining to `filling` and triggers the `joining_back` email / pass-on activity |
| `set_day(id, vals)`, `change_first_day(id, date, reason)`, `not_joining(id, reason)` | |
| `invite(vals)` | manage only; creates an `invited` joining |
| `papers_load()`, `papers_save(rows)` | papers-to-sign settings (manage only) |
| `studio_door(id)` | manage only; returns the action dict that opens Add employee for this joining (§4.5) |

Filter spec (`_pbf_spec`): step, country, department, first-day window, flags, origin; `_pbf_search_fields`
name/job/department; sorts per DESIGN §8.3.

### 4.5 Landing in Add employee (`models/studio_ext.py`, `static/src/js/studio_patch.js`)

Clone the **`hiring` received-file precedent** end to end (FACTS F6: `RECEIVED_CTX`, `_detail_items` override
`pb_new_hire/models/hiring.py:334-385`, `_values_docs` override `:419-440`, leg `_leg_hiring` `:598`,
`_file_copy` `:539-554`). Concretely, in `pb_joining`, `_inherit='pb.new.hire'`:

1. **Door:** `studio_door` opens `pb_new_hire.action_new_hire_studio` with `params/context {joining_id}`; a
   small JS patch on `NewHireStudio` reads it on start and calls `joining_draft(joining_id)`, then patches the
   draft exactly the way `bringAcross` does (`new_hire_studio.js:575-610`) and jumps to the first step with a
   missing required answer, else step 7.
2. **`joining_draft(joining_id)`** (HR gate): if the joining has an offer → start from
   `offer_draft(offer_id)['draft']`; else from the invite (`name, date_start, personal, payroll_country,
   job_title, department_id, parent_id`). Add `joining_id` and `items = {key: 'joining'}` for every accepted
   item, `'ask'` for later/none items. **No values go to the browser for `joining` rows** except what the
   review already showed, masked.
3. **A new step-5 choice `joining`:** add it beside the existing choices (`CHOICES`, `_doc_choices`); in
   `_detail_items` under a `JOINING_CTX` context add to each matching item
   `item['joining'] = {on, by, line, fields:[{label, value(masked if secret)}], files:[names]}` and
   `default='joining'`. In the studio's step-5 template add the third option and the teal source chip (DESIGN
   §9.1).
4. **`_validate_docs` / `_values_docs` overrides:** for items chosen `joining`, read the accepted values from
   `pb.joining.item` **on the server**, re-run the studio's own value checks, and merge them into the same
   places a `have` choice would (`vals['pb_nh_details']`, the bank keys). Add `vals['pb_nh_joining_id']`.
   A `joining` item needs no browser file. Result must stay JSON-plain (NH8) and pass the proposal's replay.
5. **New legs** registered in the studio's leg order: `joining_files` right after `papers` (copies item files
   to `pb.employee.document` through the same `pb.people.vault_upload_batch` call the `papers` leg uses, with
   issue/expiry dates; ID card expiry rule NH56 — when the person ticked "no end date" use the same optional
   "Valid until" handling the Hiring paper path uses), `joining_signs` (files each signed PDF as an employee
   document in the contract/policy category the `letter` leg uses, or the nearest existing category — report
   which), and `joining_close` last (sets `employee_id`, `added_at`, `state='added'`; idempotent; if the
   proposal is still pending it sets `proposal_id` only and the state flips when the proposal applies).
6. **Seams in `pb_new_hire`:** `DRAFT_KEYS` and `LEG_ORDER`/`CHOICES` are module constants. If they cannot be
   extended from another module, make the minimum change in `pb_new_hire` to allow it (e.g. a
   `_draft_keys()` / `_leg_order()` hook returning the constant), bump its version, keep its tests green, and
   list the change in the report. No other edits there.
7. **"From Hiring" tile chip:** extend `_offer_row` (`hiring.py:220`) output with
   `joining: {state, progress, checked}` and render the chip in the tile row.
8. Hire withdrawn / rejected: `joining.proposal_id` cleared, state back to `to_check`.

### 4.6 Jobs (`data/ir_cron.xml`)

One daily cron `pb_joining.cron_joining_daily` → `pb.joining._cron_daily()`:
reminders (every `remind_days` while `invited`/`filling`, max `remind_max`; email when possible, else an
activity "Remind {name} — copy the message from the Joining board"), HR nudge at `risk_days` before first day
(activity to the inviter/recruiter + HR), recompute `at_risk`, erase job (§3.5), expire stale codes. Each
joining in its own savepoint; a failure is logged and skipped. Note `/opt/deploy-notes.md` records the active
cron count per database — your release adds exactly one.

## 5. Phases (commit and test at the end of each; one feature = one commit, pushed)

| Phase | Delivers | Proof |
|---|---|---|
| **P1 Record + phone** | models, access, catalogue adapter, code, all public pages except signing, send; minimal "invite" server method for tests | T1–T22; phone walk at 360px in en/vi/id |
| **P2 Board** | board + drawer + accept/send back + link strip + invite + first-day details + hub tabs + ⌘K; trigger on signed; emails; Hiring follow-ups | T23–T44; back-office walk as HR, recruiter, plain employee |
| **P3 Add employee + signing** | step-5 `joining` way, legs, tile chip, papers-to-sign settings, sign pages, signed PDF | T45–T60; end-to-end walk signed offer → employee |
| **P4 Jobs, words, release** | cron, vi/id, static tests, full regression, release ×5, live proof | T61–T70; §8 |

Commit subjects: `JOINING P1: <plain outcome>` etc. Stage files explicitly — never `git add -A`. End each
commit message with the co-author line your tooling normally adds.

## 6. Test cases (write them as real tests, tag `joining`; `HttpCase` for pages)

Bases to reuse: `JoiningCase._signed()` (FACTS F11) for a signed offer; `NewHireCommon` / `DocsCommon` for the
studio.

**Record, link, code**
- T1 signing an offer creates exactly one joining with name, first day, country, job from the offer/requisition.
- T2 signing twice / replay with `quiet=True` creates none / no second.
- T3 internal candidate → none. T4 switch off → none.
- T5 unknown token, short token, cancelled-and-old, past `first_day+14` → same "not active" page, HTTP 200.
- T6 GET with a good token and no session shows the code screen and nothing but first name + masked contact.
- T7 correct code → session set, `opened_at` set, code cleared. T8 wrong ×5 → locked 15 min, right code refused.
- T9 expired code refused. T10 new-code limit 1/60 s and 5/hour. T11 HR-shown code valid 48 h, single use,
  cancels the emailed one; digits not in chatter.
- T12 section GET/POST without session → redirect to code. T13 POST without CSRF token refused.
- T14 a second joining's session does not open the first.

**Sections**
- T15 for each of VN, ID, IN, SG: every catalogue field is on the phone; valid values save; the stored
  `values` pass the studio's `_validate_docs` as a `have` draft.
- T16 invalid tax number / bank account → the catalogue's message under the field; nothing saved.
- T17 a country outside the catalogue (MY) → no tax section; bank uses the MY format.
- T18 saved sensitive value is not present in the next GET's HTML (masked).
- T19 bank "later" → state `later`, send allowed, `bank_later` true.
- T20 upload: wrong type refused; >10 MB refused; replace removes the old attachment.
- T21 paper Hiring already holds is shown as held and not required.
- T22 send blocked until required sections are done; after send state `to_check`, pages read-only except bank
  when later.

**Board**
- T23 gate: plain employee → `allowed:false`; recruiter → rows but items without `values`/files; HR → values.
- T24 ids from another company refused. T25 glance and step counts match rows.
- T26 chips: at-risk at ≤7 days unsent; "Link to pass on" when mail is off and never copied; "Not opened yet".
- T27 `accept`, `undo`, `accept_all`; T28 `send_back` needs a note, flips to `filling`, reopens that section
  only, sends the email / creates the activity.
- T29 `reveal` logs and is refused for a recruiter. T30 `copy_link`/`send_again`/`show_code` rate limits.
- T31 `invite` creates an invited joining; needs email or mobile. T32 `set_day` values show on the phone.
- T33 change of join date in Hiring moves `first_day`. T34 did-not-join in Hiring cancels; "They are not
  joining" from the drawer runs Hiring's action.
- T35–T38 emails: `joining_link` in the applicant's language; mail off → `mail_off` path sets `pass_on`; code
  email sent immediately; reminder email content lists missing sections.
- T39 both hub tabs registered and probe-gated (static/JS test or tour). T40 ⌘K row present.
- T41 drawer payload for step 4 is read-only. T42 concurrent accept is idempotent.
- T43 file download controller refuses a recruiter. T44 lock card for a refused reader.

**Add employee**
- T45 `joining_draft` for a Hiring joining = `offer_draft` + `joining_id` + `items` (`joining` for accepted).
- T46 `joining_draft` for an invited joining opens with team/job/wage needed.
- T47 `send` with `joining` items writes the same employee fields as the equivalent `have` draft (compare two
  hires field by field, per country VN/ID/IN/SG).
- T48 bank from the joining creates the waiting second-person bank request, proposer = the HR sender.
- T49 files become employee documents with dates; ID card without end date handled.
- T50 signed papers filed on the employee; T51 `joining_close` sets employee, state `added`, idempotent.
- T52 pending approval → state stays `to_check`, flips on apply; T53 withdrawn/rejected → back to `to_check`.
- T54 a tampered browser draft cannot inject values for a `joining` item (server reads the item).
- T55 "From Hiring" tile row carries the joining chip data. T56 existing `pb_new_hire` suite unchanged.
- T57 sign: tick + ink + name required; T58 signed PDF = original + signing page, sha256 recorded; T59 a
  signed paper cannot be signed twice; T60 send-back of a signed paper lets it be signed again.

**Jobs, words, static**
- T61 reminders every 3 days, max 4; T62 HR nudge at 7 days; T63 erase after 30 days leaves the row, removes
  values/files/signatures; T64 one failing joining does not stop the job.
- T65 no vendor name in any user-visible string of `pb_joining` (clone S1); T66 every icon name exists in
  `IC`; T67 no emoji; T68 every `_t`/`_()` string is in the `.pot`, and vi_VN/id_ID entries carry the three
  markers; T69 public pages render with `lang=vi_VN` and `id_ID`.
- T70 full suites of `pb_hiring`, `pb_new_hire`, `pb_onboarding`, `pb_people_hub` = baseline failures only.

## 7. Browser walks (mandatory — a screen is not done until it has been used in a browser with the console open)

Local, each with zero console errors and screenshots saved under `docs/handovers/joining/shots/`:

- W1 phone 360×740: code → welcome → every section → sign → send, in English; repeat the first three screens
  in Vietnamese and Indonesian. Compare side by side with the prototype's phone tab.
- W2 desktop 1440: Hiring › Joining and People › Joining as HR — glance, steps, filters, card, drawer, accept,
  send back, show a code, invite someone, first-day details, papers to sign.
- W3 same board as a recruiter (no values) and confirm a plain employee has no tab.
- W4 Add as employee → Add employee opens on step 7 with teal "From {name}" rows → add → card moves to Ready
  for day one → employee record shows the details, papers, signed papers; bank waits for a second person.
- W5 send-back loop: HR sends the tax number back → phone shows the amber card and only that section opens →
  send again → HR accepts.
- W6 widths 1180, 820, 600 for the board and drawer; 320 and 480 for the phone.

## 8. Release (owner decision O7: you release to all five)

Databases: **`payobook`, `payobook_template`, `p0clone`, `rize`, `sudima`** — these five and no others. One
addons directory: `/odoo/odoo-server/addons` (see `CLAUDE.md`, "Deploy contract").

1. Merge `joining` into `19.1` (fast-forward or rebase; do not rewrite `19.1`), push.
2. Read `/opt/deploy-notes.md` on the server (`ssh Payobook19v2 'tail -40 /opt/deploy-notes.md'`). If there is a
   `HOLD` line or a `START` without `DONE`, stop and tell the owner.
3. Tier: **risky** (new module, new stored data). Modules = `pb_joining` + every existing module you edited.
   From the repo root on the owner's Mac:
   `WHO="Codex JOINING" tools/release.sh risky pb_joining,<edited…> +pb_joining,<edited…>`
   (the `+` prefix installs; the script takes the lock, writes the START/DONE notes, checks last night's
   backups, snapshots and restores cron states, upgrades all five, refreshes assets, verifies hashes and
   versions). Do not hand-roll these steps. If the result is not `OK`, stop and report the log; do not retry
   blindly.
4. Go live only when nobody has been active on rize, payobook or sudima for 15 minutes (the convention in the
   notes file).
5. After `OK`, verify and add a NOTE line to `/opt/deploy-notes.md`: module trees identical to the commit;
   manifest version = installed version on all five (`pb_joining 19.0.1.0.0`); active cron count per database
   = before + 1; zero ERROR/Traceback in the server log since the start; the five sites answer 200.
6. Live proof on **payobook only** (demo data lives there): as an HR user, "Invite someone" →
   `DEMO Joiner One`, walk the phone flow with a shown code, accept, Add as employee (leave the demo employee
   in place — demo data is never deleted). On `rize` and `sudima`: open Hiring › Joining and People › Joining
   and confirm they load and are empty; **create nothing there**.
7. The owner signs in for you if a live login is needed; never put a password in a file, a commit or a note.

## 9. Report back — `docs/handovers/joining/JOINING_REPORT.md`

1. What was built per phase, with commit hashes.
2. Test counts per module: before / after, and the named baseline failures.
3. Every deviation from `JOINING_DESIGN.md` and why (especially: PDF display path taken, any seam added to
   `pb_new_hire`, where the `BUILTINS` switch ended up, the document category used for signed papers).
4. Walk results W1–W6 with screenshot paths.
5. Release result: script output summary, the NOTE line written, cron counts, versions ×5.
6. New ledger entries (J-numbers) you added.
7. Open questions for the owner, written as plain real-world questions.
8. Lessons in Learn that describe Add employee, Hiring › Offers or People › Joiners and now need a sentence
   about Joining (list them; do not rewrite lessons in this build).
