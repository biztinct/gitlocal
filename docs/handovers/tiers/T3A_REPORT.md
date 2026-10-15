# TIERS T3a — "Ask HR" + "My requests" — implementation report (Opus)

Handover: `T3A_HANDOVER.md`. Ledger: `TIERS_LEDGER.md`. Not committed, not deployed.
Clone runs: `p0clone`, port 8099, staged from `/tmp/deployMH` (final run 2026-10-15 08:08–08:12 server time).
Staged set: `pb_me_portal pb_me_portal_website biz_access pb_zoho_bridge pb_demo pb_ess_workforce pb_ask_hr pb_sidebar`
(pb_sidebar added because one of its spec tests gained the new rail row; its non-test files are byte-identical to the
server's — hashed before staging).

## 1. Files changed / added

| File | What |
|---|---|
| `pb_ask_hr/__manifest__.py` (new) | "Ask HR", summary per spec, depends `pb_me_portal, hr, mail, portal`, 19.0.1.0.0, LGPL-3, frontend scss+js, backend scss. |
| `pb_ask_hr/models/ticket.py` (new) | `pb.ask.hr.ticket` (mail.thread, activity mixin, portal.mixin): fields per spec (+ non-stored `waiting_days`, `last_public_by`, related `employee_name`); `create()` (number `ASK-00042`, employee follows, HR owner from `pb_ask_hr.owner_uid.<company>` → `user_id`, follower, to-do); `message_post()` override → `_pb_on_public_message(author_is_employee)`; HR actions `action_take/answer_done/close/reopen`; portal side `_portal_create/_portal_reply/_portal_close/_portal_reopen/_portal_can_reopen/_portal_messages` (public comments only, tokened attachment links). The owner's to-do is completed when the question is answered or closed. |
| `pb_ask_hr/models/pb_me_home.py` (new) | Extends `pb.me.home`: `_pbme_needs_extra` adds "HR answered your question" (state answered AND last public word is HR's); `_my_requests_sources` adds the Ask HR source (Sent / With HR = wait, "Answered — your turn" = act, Closed = off). |
| `pb_ask_hr/models/res_config_settings.py` (new) | `pb_ask_hr_owner_id` (not stored) ↔ parameter per company. |
| `pb_ask_hr/controllers/portal.py` (new) | Subclass of pb_me_portal's `PbMePortal` (reuses `_ess_employee`, upload limits). `/my/ask-hr`, `/my/ask-hr/new` (GET/POST), `/my/ask-hr/<id>` (+ `?access_token=`), `/reply`, `/close`, `/reopen`; `askhr_count` counter. Ownership guard `_ask_hr_own`; files checked before anything is created (≤3, PDF/JPG/PNG, ≤10 MB); styled 404; errors come back as `?error=` with words. |
| `pb_ask_hr/views/ticket_views.xml` (new) | Kanban grouped by state (all four columns via `group_expand`), cards: number, "waiting N d" (amber at ≥2 d), subject, employee photo+name, category chip, "Take it", owner avatar. List (secondary). Native form (VU skin applies) with Take it / Mark answered / Close / Reopen + statusbar, hint "Reply with Send message. Notes stay private.", chatter. Search: Open (default), New, With HR, Answered, Closed, Mine, Nobody has it yet, group-bys. Action + menu under `hr.menu_hr_root` seq 87. |
| `pb_ask_hr/views/portal_templates.xml` (new) | Breadcrumbs, home tile, pill / ago / toast / alert / files / picker parts, list, new-question page, conversation page, 404 page. |
| `pb_ask_hr/views/res_config_settings_views.xml` (new) | "Ask HR" block after the Employees block in HR settings. |
| `pb_ask_hr/security/ir.model.access.csv`, `security/pb_ask_hr_security.xml` (new) | hr user 1110, hr manager 1111, system 1111, base.group_user 1000 + own-read rule; HR/system all-records rule (group rules OR); global company rule. No portal row. |
| `pb_ask_hr/data/pb_ask_hr_data.xml`, `data/pb_sidebar.xml` (new) | Sequence `ASK-` padding 5; rail item "Ask HR" (see decision 1). |
| `pb_ask_hr/static/src/scss/ask_hr.scss`, `ask_hr_backend.scss`, `static/src/interactions/ask_hr.js` (new) | `.pbah-*` layer on the pbme kit; kanban card skin; file chips + client warnings, Ctrl/Cmd+Enter, auto-grow, double-submit lock, address-bar clean-up, arrow keys on the list. |
| `pb_ask_hr/i18n/vi_VN.po` (new) | 178 entries, built from the clone's own export, three rules each. |
| `pb_ask_hr/tests/test_ask_hr.py`, `test_po_gate.py`, `__init__.py` (new) | T3.1–T3.5, T3.6 (own source), T3.9 (tile), T3.10, T3.11. |
| `pb_me_portal/models/pb_me_home.py` | `NEED_TONES`, `REQUEST_BUCKETS/TONES`, `MY_REQUESTS_PAGE/PER_SOURCE`; `put()` sanitises tone; `_pbme_needs_extra` hook (own savepoint, failure logged); unknown keys appended after `NEEDS_ORDER`; `_my_requests_sources()` (6 soft sources), `_my_requests_rows`, `get_my_requests(emp, bucket)` (M-R4 own-employee guard, one `optional()` savepoint per source); tiles `/my/requests` (me, list-checks, teal) and `/my/ask-hr` (people, message-circle-question, indigo) + `_TILE_WORDS`. |
| `pb_me_portal/controllers/portal.py` | `GET /my/requests` (filter, page × 50, month groups, soft Ask HR button). |
| `pb_me_portal/views/portal_templates.xml` | Breadcrumb; "My requests" tile (employee home only); generic branches in `pbme_need_sentence` and `pbme_need_row`; 10 new Lucide glyphs in `ess_icon`; `portal_my_requests` page. |
| `pb_me_portal/static/src/scss/me_portal.scss` | My requests styles, `.pbme-chips`, empty-state button spacing; Me strip is now an auto-fit grid (six tiles sit six across); reduced-motion rules. |
| `pb_me_portal/static/src/interactions/my_requests.js` (new) | Arrow/j/k/Home/End between rows. |
| `pb_me_portal/__manifest__.py` | 19.0.3.1.0 → **19.0.3.2.0**; registers `my_requests.js`. |
| `pb_me_portal/i18n/vi_VN.po` | 42 new entries; 8 existing entries gained the `pb_me_home.py` code occurrence + `odoo-python` marker. Rest of file untouched (text edits, no re-wrap). |
| `pb_me_portal/tests/test_my_requests.py` (new), `tests/__init__.py` | T3.6, T3.7, T3.8, T3.9. |
| `pb_me_portal/tests/test_me_home_cards.py` | `test_06_font` pin → 19.0.3.2.0 (ledger T7). |
| `pb_me_portal/tests/test_me_home.py` | Me-strip order pin gains `/my/requests`. |
| `pb_me_portal/tests/test_me_home_source.py` | `portal_my_requests` joins the source/VI gates. |
| `pb_me_portal/tests/test_portal_icons.py` | Two registry-style icon call sites allowed (`it.get('icon')`, `r['icon']`). |
| `pb_sidebar/tests/test_ia_c5.py` | Rail spec table: `pb_ask_hr.item_ask_hr` (operate, 22, inbox, "Ask HR") + its match model/xmlid rows. Test-only edit. |

## 2. Test results (clone log, final run)

```
-i pb_ask_hr -u pb_me_portal,pb_sidebar --test-tags /pb_ask_hr,/pb_me_portal,/pb_me_portal_website,/pb_sidebar:TestIaCycle5Rail,/pb_sidebar:TestIaCycle5MatchMatrix
odoo.tests.stats: pb_ask_hr: 23 tests 13.52s 7577 queries
odoo.tests.stats: pb_me_portal: 116 tests 48.22s 26188 queries
odoo.tests.stats: pb_me_portal_website: 6 tests 1.87s 842 queries
odoo.tests.stats: pb_sidebar: 22 tests 0.47s 591 queries
odoo.tests.result: 3 failed, 1 error(s) of 125 tests when loading database 'p0clone'
ERROR: TestPbMePortal.test_01_profile_change_flow_and_audit                      <- pre-existing M19
FAIL:  TestIaCycle5Rail.test_every_retired_item_still_points_at_something_that_resolves   <- pre-existing (see below)
FAIL:  TestIaCycle5MatchMatrix.test_every_live_item_claims_exactly_the_matrix_it_was_given <- pre-existing
FAIL:  TestIaCycle5MatchMatrix.test_the_representative_highlight_matrix          <- pre-existing
```
The three pb_sidebar failures are drift from other programmes, not T3a: the People item now claims
`pb_decision_room, pb_pay` where the table still says `wfp_dashboard`, and `pb_hr_workforce_planning` is not
installed on p0clone (retired items point at its actions). The two tests the new row could break —
`test_the_rail_is_exactly_the_target_table` and `test_every_rail_icon_exists_in_the_fixed_set` — pass.
No warning from pb_ask_hr or pb_me_portal in the run (only the existing deliberate ones from M-tests).

| # | Test(s) | Result |
|---|---|---|
| T3.1 | `test_t3_1_lifecycle`, `_1b_` (a reply reopens), `_1c_` (subject required) | pass. new, `ASK-…`, `create_uid` = employee login, partner follows, html paragraphs; with_hr → answered (+`answered_on`) → closed/hr → reopen → with_hr; second close no-op; 15 days → UserError "…more than 14 days ago. Ask a new question instead." |
| T3.2 | `test_t3_2_hr_comment_answers_and_mails_a_note_does_not` | pass. HR comment → answered, `mail.notification` (email) for the employee's partner; note → state unchanged, not in `_portal_messages`, no notification; employee reply → with_hr, author = their partner. |
| T3.3 | `test_t3_3_flow_for_an_employee_login`, `_3b_flow_for_a_full_account`, `_3c_a_wrong_file_is_refused` | pass. Empty-state words; new page draws 6 chips + all 3 fields; missing subject → reason, nothing created; create with PDF (a forged `employee_id` in the form is ignored) → ticket for own employee, `create_uid` = user, attachment bound, tokened link returns the bytes, redirect + "Sent" pill + toast; empty reply → reason; reply → with_hr; HR comment → left bubble, "Answered", HR note NOT shown, unread marker on list, "HR answered your question" on `/my`; close → Closed (+ "Already closed" on a second press); reopen → with_hr; another person's ticket GET/reply/close/reopen → 404 (styled), nothing changed. |
| T3.4 | `test_t3_4_access_token` | pass. Owner + wrong token → 200 with composer; other employee + right token → 200 read-only ("shared link", no composer); wrong/no token → 404. |
| T3.5 | `test_t3_5_hr_owner_setting`, `_5b_settings_…` | pass. Parameter set → owner, one to-do for them, follower; HR answer completes the to-do; unset → none; a portal account as owner is ignored. Settings write/read the parameter. |
| T3.6 | `TestMyRequestsModel.test_t3_6_*` (+ `_6b` broken source, `_6c` other employee) and pb_ask_hr `test_t3_6_ask_hr_on_my_requests` | pass. All six sources had a fixture on p0clone (asset, leave, overtime, profile, resignation, timesheet_fix): one row each with the source's label/tone/url, newest first, counts add up, filter keeps counts whole. A source whose `title` raises is skipped with a WARNING naming the model, the rest return. Ask HR row: Sent/wait → "Answered — your turn"/act. |
| T3.7 | `test_t3_7_*` (employee login), `_7b_*` (full account) | pass. Empty words; strip `0 / 1 / 1`; 2 rows; month header; `?filter=wait` 1 row; `?filter=act` 0 rows + "Nothing is waiting on you"; junk params → 200, all rows. |
| T3.8 | `test_t3_8_generic_needs_you_row`, `_8b_` (broken extra) | pass. Probe row last, unknown keys in insertion order, zero dropped, bad tone → slate; row and sentence render; known row unchanged; a raising extra is logged and the home still builds. |
| T3.9 | `test_t3_9_tile_meta`, `test_t3_9b_home_shows_the_requests_tile_in_me`, pb_ask_hr `test_t3_9_home_tile_in_people` | pass. Registry group/icon; `/my` puts My requests in `me` and Ask HR in `people`; `/my/counters` returns `askhr_count`. |
| T3.10 | `test_t3_10_backend_queue_and_access`, `_10b_sidebar_and_menu` | pass. Action loads (kanban first), all four views parse, form carries the hint, four state groups even when empty; Take it assigns + subscribes; plain reads own, AccessError on another's and on write, search = own only; employee login AccessError on search; no portal ACL row exists. Menu parent and rail item checked. |
| T3.11 | `TestPoGate` (3 tests) + server parse gate | pass. `PoFileReader` on the server: pb_ask_hr 220 rows, pb_me_portal 353 rows. Every entry has the module line, an occurrence, the `odoo-python` marker for code, a msgstr, no vendor name; every Ask HR page word has a VI line. Live check on the clone: `/vi/my/ask-hr/new` lead line, chips, `/vi/my/requests` pills (code strings) all render in Vietnamese. |
| T3.12 | the run above | pb_me_portal 116 (T1/T2 suites + new), pb_me_portal_website 6 — green except M19. |
| T3.13 | browser walk | done, below. |

### T3.13 — browser walk (clone, staged code, port 8099 local-only, tunnelled)
Chrome MCP's own browser was held by another session's profile, so I drove a separate headless Chrome over the
DevTools protocol (same engine, own profile). Two temporary logins: `t3a.ui.employee@example.com` (employee login,
portal) and `t3a.ui.hr@example.com` (internal + HR officer). Both are now **archived with scrambled passwords**; the
UI server is stopped and the tunnel closed.

Employee: sign-in lands on `/my` → My requests tile in the Me strip, Ask HR tile in People → `/my/ask-hr` empty
state → New: chips, subject, details, a PDF (chip "proof.pdf 1 KB"), **Ctrl+Enter** sent it → ticket page, toast
"Sent to HR…", pill "Sent", address bar cleaned → reply → pill "With HR".
HR: rail shows "Ask HR" (inbox icon, lit on the queue) → kanban New 0 / With HR 1 / Answered 0 / Closed 0, card
"ASK-00015 · today · subject · Lan T3a Test · Pay & payslips · Take it" → Take it (button gone, avatar shown) →
form (VU skin: `vu-state--with_hr`), hint line, statusbar → **Send message** in the chatter → statusbar "Answered";
then a Log note.
Employee again: HR bubble on the left with initials, pill "Answered", the note did NOT show; `/my` Needs you "HR
answered your question" and top line "Your next pay lands in 16 days. · HR answered your question."; list row with
unread dot; "That solved it" → Closed + toast; Reopen → With HR + toast; phone width (390 px) ticket and new pages;
My requests (strip, row, arrow key moved focus to the row), `?filter=act` empty state, phone width.
Console: no error from these pages. Seen and not ours: the website logo image 500 (the clone's filestore lacks the
file — every page), pb_learn's "translations have not been loaded" warning (known since T2), and on the HR form a
415 from the chatter's PDF preview of my synthetic 1-page-less test PDF.
Two defects found by the walk and fixed before the final run: a bare Sass `min(78%, 620px)` broke the whole frontend
style bundle (now `unquote(...)`), and the details `<textarea t-out>` vanished when empty (an element with an empty
`t-out` is dropped; now a body `<t t-out>`); T3.3 now asserts all three fields are drawn. On phones the chips were
one per row; they now sit two across.
Screenshots (17): scratchpad `walk/shots/` (not versioned).

## 3. Design self-score against the bar
- **Hero moments**: (1) New question — the first line is the one reassuring sentence, the category picker is a row of
  icon chips (real radios, keyboard-native), and a "What happens next" card answers the anxiety before it arises;
  (2) the conversation — right/left bubbles in the brand tint, HR with an initials avatar and an "HR" tag, the
  thread always ends with one line saying where things stand and what happens next, and the pill pops once when the
  state just changed; (3) My requests — one month-grouped timeline, quiet grey pills, the only coloured pill is the
  one waiting on the person, strip "0 waiting on you · 1 with someone · 0 done".
- **Zero dead-ends**: every empty state says what will appear (Ask HR none / none open / none closed; My requests
  none / per filter with "Show everything"); every refusal names its reason and the next step (subject, file
  type/size/count, empty reply, closed > 14 days, "did not go through"); another person's ticket is a styled 404;
  a shared-link reader is told why there is no reply box; a second "That solved it" says "Already closed".
- **Motion with purpose**: rows/bubbles settle in once, toast slides in and fades, pill pops on change, file chips
  appear; all off under reduced motion. No loops.
- **Keyboard**: Ctrl/Cmd+Enter sends both forms, double-submit lock, arrow/j/k on both lists, radios arrow natively.
- **Backend**: kanban + skinned form; quiet card, amber only after 2 days waiting.
- Self-score **8/10**. What keeps it from 10: no live update (HR's answer appears on reload, not in place); the
  HR side is a skinned native form rather than a bespoke cockpit; the "Send reply" and "That solved it" primaries
  sit in two adjacent cards when a question is answered.

## 4. Learn impact
Grepped `learn_content.json`, `anchors.json`, `engine/screens.js`, `engine/fixture.js`, `docs/tutorial_poc/author/data.js`:
no lesson describes the employee home's tiles or its Needs you card (the only `/my` mention is "Only an employee?
You start on My Payobook"). **Nothing in Learn is affected.**

## 5. Decisions the handover did not make
1. **Rail item in OPERATE, icon `inbox`.** The People section is retired (inactive), so an item there would never
   draw; the rail's icon set is closed and has no `message-circle-question`. Item `pb_ask_hr.item_ask_hr`, Operate,
   seq 22 (between People 20 and Lifecycle 25), gated `hr.group_hr_user`; pb_sidebar's spec table got the row. This
   makes the rail nine items — **an IA call Fable/the owner may want to reverse** (delete the data file + the three
   table lines; the native menu stays).
2. **Controller subclasses `PbMePortal`** (import) instead of cloning `_ess_employee` — one helper, one guard.
3. **Token readers are read-only.** `?access_token=` lets another signed-in person read; only the owner can reply,
   close or reopen.
4. **The question itself is the opening bubble** (from `description` + `attachment_ids`), not a posted message.
5. **"Waiting on you" pill tone**: drafts stay `off` (counted under Done) exactly as the spec's states say; refused
   (`no`) gets a rose dot inside a grey pill so "Refused" is not mistaken for "Approved".
6. **"Ask HR" in Vietnamese is "Hỏi Nhân sự"**, "HR" → "Nhân sự"/"phòng nhân sự", matching the existing files;
   the existing VI for "My requests" ("Đơn của tôi") was kept.
7. **Owner's to-do is completed** when HR answers or anyone closes; the assignment e-mail is suppressed
   (`mail_auto_subscribe_no_notify`) — the to-do is the signal.
8. **Me strip became an auto-fit grid** so the sixth tile does not stretch alone across a second row.
9. **Tiles are drawn on the employee home only** (`t-if="pbme_home"`): a customer login gets no dead "My requests".
10. Pre-existing pb_me_portal VI gaps the export surfaced (approval-matrix labels in `pb_profile_change_approval.py`,
    ~14 strings) were **left alone** — not T3a's words.

### Proposed ledger rows
| # | Gotcha / fact | How to apply |
|---|---|---|
| T24 | libsass evaluates a bare CSS `min()/max()` with mixed units (`min(78%, 620px)`) and the WHOLE `web.assets_frontend` bundle falls back to "A css error occurred" — tests stay green. | Write `unquote("min(78%, 620px)")`; after any SCSS change load one page and check the bundle has no `css_error_message`. |
| T25 | QWeb drops an element whose `t-out` value is empty (`<textarea t-out="text"/>` with `text=None` renders nothing). | Put the value in a body: `<textarea …><t t-out="text or ''"/></textarea>`; assert form fields exist in the HttpCase. |
| T26 | Two browser contexts in one headless Chrome: the background one never renders the backend (OWL waits on animation frames), even after `Page.bringToFront`. | Drive the backend walk in its own browser instance. |
| T27 | The rail is a closed spec: a new `pb.sidebar.item` must also be added to `pb_sidebar/tests/test_ia_c5.py` `TARGET_RAIL` (+ match tables) and use an icon from the closed set in `pb_sidebar.js`. | One data record + three table lines; never a new icon name without editing pb_sidebar.js. |
| T28 | `formatted_read_group` honours `group_expand` only with `context read_group_expand=True`. | Set it when asserting kanban columns in a test. |

## 6. Self-review
**Scope**
1. pb_ask_hr module, model, create/message_post/actions/portal methods, security (no portal row), settings, kanban +
   form + list + search + menu + rail, portal pages (list, new, ticket, token, reply/close/reopen, 404, toasts,
   errors), tile + counter, needs-you row: done. Deviation: rail section/icon (decision 1).
2. pb_me_portal hooks (`_pbme_needs_extra`, generic row + sentence, unknown keys last), tiles, My requests (sources
   super-chain, soft, savepoint each, strip, chips, month groups, 50 + Show earlier), version 19.0.3.2.0 + pin: done.
3. Translations: both files, three rules, export-built, parse gate run: done.
4. Learn: checked, nothing affected: done.
5. Tests T3.1–T3.13: done (all T3 tests green; pre-existing M19 + 3 pb_sidebar drift failures named).

**Non-goals**
- No clock in/out, no notices: done (untouched).
- No approvals engine on tickets: done.
- No portal ACL rows: done (asserted in T3.10).
- No change to pb_ess_workforce, pb_assets, pb_offboarding, pb_hr_workforce, pb_attendance_flow, pb_hr_comm,
  biz_approval_workflow, hr, mail, portal: done (read softly only). pb_sidebar: test table only.
- No SLA timers, ratings, knowledge base, re-assignment UI, e-mail-in: done.
- No new stored field on an existing model; no vendor name in any user-visible string: done (VI gate checks msgstr).

**Safety rails**: every sudo write sits after `_ask_hr_own` / `_ess_employee`, `employee_id` forced from the session
(a forged form value is ignored — tested); files checked before any create, bound to the ticket, downloaded only
with their token; `_portal_messages` filters to public comments (tested with a note); close/reopen idempotent.

**Side effects on the clone only**: p0clone has pb_ask_hr 19.0.1.0.0 and pb_me_portal 19.0.3.2.0 installed, ticket
ASK-00015 and two archived `t3a.ui.*@example.com` logins. Live service, port 8069 and the payobook database were not
touched.
