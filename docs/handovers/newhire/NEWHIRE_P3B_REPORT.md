# NEWHIRE P3b — report (welcome message, the page it lands on, reminders, tracker)

Built on worktree `gitlocal-worktrees/newhire` (branch `newhire`), 2026-11-25. Not pushed, nothing deployed, no server access.
Local DB `nh4_base` = copy of `nh3_base` (P3a walk world) + `pb_me_privacy` installed + walk settings (`walk_p3b.py`).

## 1. What was built

`pb_new_hire` 19.0.1.2.0 → **19.0.1.3.0**. New dependency: `auth_signup` (already pulled in by `portal`, explicit now).
New data: `data/mail_template.xml`, `views/welcome_templates.xml`; migration `migrations/19.0.1.3.0/post-migrate.py`.

| Layer | Files |
|---|---|
| Architect answers (a)–(c) | `studio_docs.py` (choice `number` on the merged card rows, `card_url`, values/asks), `docs_legs.py` (`CONTRACT_COPY`: VN social insurance, IN UAN/ESI, SG NRIC copied to the running contract like the VN tax code), `paper.py` (`plain_name` fallback, editor shows plain names), `data/papers.xml` + migration (labels for the four certificate rows) |
| The link and the message | `models/invite.py` — `pb.new.hire.invite` (`_link`, `send`, `copy_link`, `send_again`, `card`, `_board`, `_nh_remind_asks`, `_nudge`), employee fields `nh_remind, nh_reminded_on, nh_hr_nudged, nh_sent_at, nh_copied_at, nh_details_ticked`, leg `invite` (last), reminders inside `_cron_lifecycle_reminders` |
| Sign-in by personal email | `welcome_legs.py` (`_login_private`, LEG_ORDER + `invite`), `studio_welcome.py` (`_login_address`: email mode with either address) |
| The reader | `ask.py` — `refresh()` batched (a fixed number of reads for any number of people), `summaries()`, `summary()`, `_tick_details_step()` |
| `/my/welcome` + home row | `controllers/welcome.py`, `models/my_welcome.py` (`pb.new.hire.welcome.page`, `_pbme_needs_extra` row), `views/welcome_templates.xml`, `static/src/scss/welcome_page.scss` |
| New joiners board | `models/joiners.py` (`get_joiners_page` / `get_joiner` add `asked`, one batched read), `static/src/js/joiners_board.js` (patch), `xml/joiners_board.xml` (t-inherit), `scss/joiners_board.scss` |
| Studio | step 5 invite card + phone preview (`step_docs.js`, xml, scss), three-state card rows, `remind` key (`new_hire_studio.js`, `studio.py` DRAFT_KEYS), done card "What <first> has been asked for" + Copy (`step_check.js`), step 7 truthful line, step 1 hint (POC wording), `load().mail_on`, `studio_util.copyText/docAskedOf` |
| Tests | `tests/test_invite.py` (V1–V12 + X1–X3, 28 tests incl. 4 over HTTP); `test_docs.py` D7 and `test_welcome.py` W16 updated on purpose; `test_static.py` now also scans `data/` |

**Files touched outside `pb_new_hire`: none.** (`pb_onboarding`, `pb_me_portal`, `pb_lifecycle`, `pb_zoho_bridge` are extended by
inheritance / template inheritance / JS patch only.)

### 1.1 Plumbing decisions as built
- **Link** = `partner.signup_prepare(signup_type='signup')` + `partner._get_signup_url_for_action(url='/my/welcome')` (the bridge's
  `pb_portal_signup_url` calls + the landing page). Never signed in (`login_date` empty) → sign-up link; signed in before → the plain
  `<base>/my/welcome`. Only for an employee-tier login whose login is an email; a clock-number login gets no link.
- **No mail server** = no active `ir.mail_server` (precedent `pb_explorer._pbx_mail_on`, `pb_voice._voice_mail_on`).
- **Sent with no document attached** (`model/res_id` False) and `auto_delete`: the queued mail is the only place the link exists at
  rest (NH42). The employee's chatter gets "Welcome message sent to <address>." / "Reminder … sent to …" / "<user> copied the
  welcome link." — never the link.
- **Who may Send again / Copy**: HR manager, access manager, administrator. Once a minute per person each (`nh_sent_at`,
  `nh_copied_at`).
- **Personal-email sign-in**: own small method reusing the bridge's building blocks (same user values, `no_reset_password`,
  `_link_employee_login`); an existing login with that address is reused only when it is employee-tier and no other employee
  holds it, else the leg fails with the handover's sentence. The work-email path still calls `_auto_create_login` unchanged.
- **Board batching**: `pb.new.hire.invite._board(ids)` = one `summaries()` (3 request searches + 1 document search + rows) for
  the whole page, in its own savepoint.

## 2. Results

### 2.1 Numbered tests (`-u pb_new_hire --test-tags /pb_new_hire`)
**95 / 95 pass**, twice: on `nh5_b` (a clean copy of the P3a database `nh3_base`) and on the walk database `nh4_base`
(52 P1+P2 + 15 P3a + 28 P3b; static gates included). The first full run on the walk database showed 8 failures that were the
tests' own assumptions about database state (another mail server, other joiners, a published privacy notice); the tests now
hold on any database (commit `9dcf801c2`, ledger NH49).

**Neighbour suites** (modules extended by inheritance): `/pb_me_portal, /pb_onboarding, /pb_lifecycle, /pb_people_advanced`,
281 tests, run on two fresh copies of `nh3_base` — committed code (`git archive HEAD`) vs P3b code: **the same 6 not-ok in both,
nothing new** (pb_me_portal `test_05_grid`, `test_06_font`, `test_01_registry_covers_every_tile`, `test_12_vi_po…`,
`test_01_profile_change_flow_and_audit`, `test_t1_7_portal_only_person_is_bounced_to_my` — pre-existing on this local base).

| # | Test | Result |
|---|---|---|
| V1 | personal-email sign-in: step 6 email mode available, sub-line names the address; login = private email, employee-tier, linked both ways; free portal login reused; internal login with that address → failed leg with the exact sentence; both addresses → login = work email, message to the personal one | pass (4 tests) |
| V2 | `_link`: `/web/signup?…token=…redirect=%2Fmy%2Fwelcome`, token resolves to the partner; after a first sign-in the token dies and the plain page is returned; validity sentence follows `auth_signup.signup.validity.hours` (144 h → 6 days, 48 h → 2 days, 30 h → 30 hours) | pass (2) |
| V3 | welcome message queued to the private address, every asked label in it, a skipped item not, "Get started", "works for 6 days", subject "Welcome to <company> — a few things before Monday 7 December", no document attached, auto-delete; no "odoo" in subject/body nor in the debranded outgoing form (`_prepare_outgoing_list`); `nh_reminded_on` set; chatter note. No mail server → amber leg "This site does not send email…"; code → "has no email sign-in…" (asks stay); none → "has no sign-in yet…"; nothing asked → green "nothing to ask …, so no welcome message" | pass (5) |
| V4 | after approval + a copy: the link is in no `mail_message` except the queued mail's own, not in payload/result/answer, not in `ir_logging`, not on the chatter | pass |
| V5 | `/my/welcome` over HTTP: own asks only (another person's label absent), To do / Sent, waiting for HR / Done, first-pay chip, card links; all done → "That is everything. See you on Mon 7 Dec." + home link; no asks → redirect to `/my` | pass (2) |
| V6 | sign-up link → set password → privacy notice with `next=%2Fmy%2Fwelcome` → agree → `/my/welcome` | pass |
| V7 | home row "Finish your joining details", n = open count, url `/my/welcome`; gone when all done | pass |
| V8 | "Finish your own details" (`pb_onboarding.step_rize_data`) ticks only when everything is done, with the note, once (re-opened by HR stays open) | pass |
| V9 | reminders: 2-day cadence, once a day, stops when done; off with `pb_new_hire.ask_reminders=0`, with `pb_lifecycle.reminders_enabled=0`, with `nh_remind` off; mail server off → nothing sent, nothing written; the lifecycle job runs the piece; HR note once, 3 days before day one, to the proposer, exact sentence | pass (3) |
| V10 | board `asked` shape; `_board` for 3 people uses no more queries than for 1 (+2 tolerance); HR manager can send/copy, HR officer cannot; `get_joiners_page` rows carry `asked` | pass |
| V11 | Copy twice in a minute refused, Send again right after the welcome refused, both work after a minute; HR officer → AccessError | pass |
| V12 | `load().mail_on`; `card()` for the done card; P1–P3a suites + static gates (see §2.1b) | pass |
| X1 | number-only card rows: number saved, the card asked (`/my/documents` for a self-uploadable ID card, `/my/tax/change/tax_number` for NPWP/PAN), refused without the number, `number` on another row falls back | pass (2) |
| X2 | VN social insurance number and tax code on employee AND running contract | pass |
| X3 | every shipped paper row has its own label; no "Degree / Certificate" / "ID Document" in the editor; plain names for unlabelled categories | pass |

### 2.2 Browser walk (local server `nh4_base`, Claude-in-Chrome, 1440 px; console read)

| # | Walk | Result |
|---|---|---|
| F1 | step 5 invite card, four states: asks ("One link, 8 things to finish", "Sent to wulan.pratiwi@example.net as soon as the hire is approved. Due before Mon, Dec 7.", reminders switch, password line, bank shield, phone preview with 8 rows + "Start · about 12 minutes"); none ("Nothing to send", "See you on Mon, Dec 7. Nothing to fill in."); no email (amber + "Add an email in step 1"); site without email (amber "This site does not send email…"). KTP row: Ask for both / I have the number / I have both; number typed → "The number is saved. Wulan is asked for the KTP (identity card) on My Payobook."; rail "8 for Wulan, 1 with you" | pass (title and password line fixed for the no-link state during the walk) |
| F2 | send → pending done card "What Wulan has been asked for" (8 rows, "0 of 8 done") → approved as Dewi Lestari → legs green incl. "welcome message to wulan.pratiwi@example.net"; queue: one mail to the personal address, no document, 8 items, first-pay chips, Get started, 6-day line | pass (letter leg amber: no PDF tool locally, NH20) |
| F3 | signed out; sign-up link → stock sign-up form (name/email prefilled) → password → privacy notice (`next=/my/welcome`) → agree → `/my/welcome`; 390 px frame: one column, no sideways scroll (`scrollWidth 390`), screenshot `shots/p3b/f3_welcome_390.jpg` (scratch) | pass (date and plural wording fixed during the walk) |
| F4 | `/my/details/bank` from the Bank card: bank paper + numbers → sent → card "Sent, waiting for HR"; certificate uploaded on `/my/documents` → "Done"; HR lead approves the bank change → "Done" | pass |
| F5 | board: chip "Asked from Wulan · 2 of 8 details" (grey: 12 days out); drawer list with states and first-pay lines; Send again → reminder queued (only open items, plain page link since Wulan had signed in) + chatter note; Copy → rate-limit answer inside a minute, then the link field with "It opens the welcome page. Wulan signs in as usual." | pass (clipboard hang, toast under the drawer and title-case badges found and fixed, NH46/NH47) |
| F6 | reminder job by hand over 27 Nov … 5 Dec (rolled back): sent 28 Nov, 3 Dec, 5 Dec (2-day cadence, once a day); HR note once on 4 Dec to Dewi Maker "Wulan Pratiwi starts on … and 2 things needed for the first pay are still missing." | pass (date in the note made readable) |
| F7 | remaining items completed on the record → checklist step "Finish your own details" done with the note; `/my/welcome` finish state (green ring, "That is everything. See you on Mon 7 Dec.", Go to your home page); home "Nothing needs you right now" | pass |
| F8 | employee-number person (login DEMO-0901): no welcome link; after sign-in + privacy notice, `/my/welcome` lists their 2 asks | pass |
| F9 | console (errors only): bus "ConnectionLost" from server restarts only; server log: nothing from our code (copied-DB missing filestore images, wkhtmltopdf) | pass |
| extra | fast lane: added-person done card with "Copy the welcome link" → sign-up link in the fallback field + "It works for 6 days, or until Dian signs in."; studio at a 340 px root with its narrow rules forced (NH45): one column, phone 250 px, `scrollWidth 340` | pass |

## 3. Self-review against the handover — deviations

1. **Sending the welcome message as a "document-less" mail** (`model=False`) and `auto_delete=True` — the handover only said the link
   may live in the outgoing mail; without this it would also sit on the employee's chatter (NH42).
2. **Reminders with email off**: the email part does nothing and writes nothing; the HR note (an in-app activity) is still made,
   because on the three sites without email it is the only way HR hears. Both are under the person's reminders switch.
3. **Send again** sends a *reminder* (only what is still open); with nothing open it answers "Nothing is waiting…" and sends nothing.
4. **No `?next=`** on the cards: none of `/my/profile`, `/my/details/*`, `/my/tax/*`, `/my/documents` honours a return parameter
   (checked); the person comes back through the home row (and the page's own back link). Foreign forms untouched.
5. **The home row** is put BEFORE the hook chain's `super()` (NH41); it shows while anything is open (n = open) and, when only
   waiting items remain, as a grey "Your joining details" row (n = waiting) — the handover said "while open or waiting, n = open",
   which would drop the row at n = 0.
6. **Journey tick** lives in `summary()` (the server reader every caller uses), marked once on the employee.
7. **Copy for someone already signed in** gives the plain page link (the sign-up link is dead after the first sign-in).
8. **Answer (b)** also copies the Singapore NRIC to the contract (`singapore_nric_fin`, an HR-kept number with a contract copy);
   India PAN is NOT copied (a tax number, no precedent) — say if wanted.
9. **One place a vault word is still shown**: on `/my/welcome`, a paper uploaded through My documents says which kind to choose
   there ("choose “ID Document” as the kind of paper") — that is the word the upload page's list shows.
10. **Stock sign-up page** (`/web/signup`) is the website's standard form (broken logo image on the walk DB) — not ours, unchanged.
11. **400 px studio proof** could not use a real 400 px window this session (NH45); proven with the narrow rules forced.
12. Approvals in the walk were made with the engine's own `decide` as the HR lead (shell), the same call the inbox makes; the
    inbox screen itself was walked in P3a.

## 4. Design bar (ledger rule 4), scored honestly
- **Hero moment — 8/10.** One link → password once → privacy → a page that says "Welcome, Wulan — 8 things to finish before
  Mon 7 Dec", each card one tap into the right form; the board's chip and list tick over by themselves. Missing: the board chip has
  no live update while open (refresh button), and the sign-up page is the stock one.
- **Zero dead-ends — 9/10.** Every state of the invite card names its fix; no email / code / none / site without email all say
  what happens instead; rate limit and gates answer in words; the done card copies or shows the link.
- **Plain language — 8/10.** Screen words throughout; ask labels are stored in the approver's language (P5 .po does not
  re-translate stored labels — see §6).
- **Motion — 7/10.** Staggered phone rows and page cards, ring entrance, card hover lift; reduced-motion safe.
- **Keyboard — 8/10.** Reminders switch is a real switch, link field selects on focus, every card is a link.

## 5. What can be sent, and when (rail of this phase)
| What | To | When | Where email is off |
|---|---|---|---|
| Welcome message (our template) | personal email, else work email | at apply (fast lane: on Send), when something is asked and the person has an email sign-in | not queued; amber leg + chatter note; HR copies the link |
| Reminder (same template, open items only) | same | every 2 days while open, until 14 days after day one; or "Send again" | nothing sent, nothing written |
| "Account created" (stock `auth_signup`) | the person | when they set the password through the link | stock behaviour |
| HR note (activity) + stock "assigned to you" email | proposer of the hire, else the checklist's HR owner | once, 3 days before day one (or at once if later) if a first-pay item is not done | the activity is still made (in-app) |

**Link lifetime on this build:** `auth_signup.signup.validity.hours` (unset on all five DBs → 144 h = 6 days); dies at the first
sign-in; a new link is minted at every send/copy and older ones stay valid until their own expiry (NH43).

## 6. New gotchas
NH41–NH49 in the ledger: home hook chain order; template mail lands on the chatter; stateless sign-up links + stock
account-created mail; assets not rebuilt locally; narrow-width proof; clipboard can hang; board drawer above toasts and
title-case badges; activity assignment emails; tests must not assume the database's mail servers, joiners or privacy notice.

## 7. Open questions for the architect / owner
1. **Stored ask labels and language**: labels are written in the approver's language at apply; a Vietnamese employee reading
   `/my/welcome` sees them in that language. Translate at read time from the item key (needs a key→label map) in P5?
2. **Older links stay valid** after "Send again" (stateless). Acceptable, or rotate by changing `signup_type` per send?
3. **Reminders with email off**: keep the HR note on those sites (current), or nothing at all?
4. **Rate limit** is per action (copy and send separately). One shared minute instead?
5. **pb_me_tax's own "Add your tax number" home row** shows next to ours for the same thing. Hide ours' tax items, or leave both?

## 8. Commits (not pushed)
- `a6d6a625b` NEWHIRE P3b: server side of the welcome message, /my/welcome, reminders and the New joiners tracker
- `46e10dc3b` NEWHIRE P3b: on screen — the invite card, the asked list, the New joiners chip
- `9dcf801c2` NEWHIRE P3b: tests hold on any database
- this docs commit (report, ledger NH41–NH49, fact corrections)

(`54b40ad09` "NEWHIRE P4: handover" between them is the architect's, not this phase's.)

Local leftovers (not in git): DB `nh4_base` (+ filestore) with the P3b walk (Wulan Pratiwi through the link; Dian Lestari via the
fast lane — **new hires on that DB now need no approval**; mail server "DEMO nowhere" → 127.0.0.1:1025, nothing listening;
web.base.url = localhost:8291; a published privacy notice); scratch `walk_p3b.py` (setup + the two test passwords),
`runt4.sh`, `runth.sh` (HTTP tests on 8311), `restart4.sh`, `approve.py`, `approve_bank.py`, `remind.py`, `finish.py`,
`codeperson.py`, `shots/p3b/`.
