# NEWHIRE P3b — the welcome message, the page it lands on, reminders, and the tracker

Read first: `NEWHIRE_LEDGER.md` (binding; D8 is the heart of this phase), `NEWHIRE_P3A_REPORT.md` (the ask rows and the
`summary` reader you build on — its "seams P3b should call" section wins over this handover where they differ in naming),
`NEWHIRE_FACTS_ONBOARD.md` §A6–A7 (My Payobook home hooks and deep links), §B (links — read B5 twice), §F6–F7 (New joiners
board row and the reminder job), §G (sign-ins). **Do not re-derive.** Open the POC: step 5's phone preview and the
"What <name> has been asked for" card after sending.

Work ONLY in `/Users/adity/Documents/GitHub/gitlocal-worktrees/newhire` (branch `newhire`). No deploy, no server access.

**Hero moment**: the new person opens one link on their phone, sets a password once, and lands on a page that says
"Welcome, Sari — 4 things to finish before Mon 7 Dec", each a single tap into the right form; back in HR's New joiners
board the same four things tick over by themselves.

## 1. Scope
1. A **sign-in for people who only have a personal email** (the usual case before day one).
2. The **welcome message** (email) with the signed sign-up link, sent when the hire is approved; and a **"Copy the
   welcome link"** path for sites with no outgoing email (three of the five live sites send no email, by the owner's choice).
3. **`/my/welcome`** — the page the link lands on — and the matching rows on the My Payobook home.
4. **Reminders** every 2 days until done, and a nudge to HR 3 days before the first day when something needed for pay is
   still missing.
5. **New joiners board**: an "asked" chip + list per person, with "Send again" and "Copy the welcome link".
6. Studio step 5: the real invite card (phone preview, reminders switch, truthful wording) replaces P3a's quiet summary;
   the done card shows "What <first name> has been asked for".
7. The joining checklist's "Finish your own details" step ticks itself when every ask is done.

### Binding non-goals
- No no-login page that writes anything; no change to the guards of the self-service entry points; no change to
  `auth_signup.signup.validity.hours` (it would change every invitation in the system).
- No new scheduled job (the template-jobs list would need it) — extend the existing reminder job.
- No change to the forms under `/my/profile`, `/my/details`, `/my/tax`, `/my/documents` beyond what §2.4 names.
- No "From Hiring" (P4), no `.po`/Learn (P5).

## 2. Plumbing decisions (made — follow them)

### 2.1 Sign-in by personal email (leg `login`, extended)
P2's `email` mode needs a work email. Add: when the mode is `email` and there is no work email but a `private_email`,
create the same employee-tier (portal) login `_auto_create_login` creates, with the private email as login and address.
Do it by reusing that method's own building blocks (read `pb_zoho_bridge/models/zoho_pipeline.py:586-640`: the user
vals, `no_reset_password=True`, the same-address reuse rule, `_link_employee_login`) through a small method in
`pb_new_hire` — if `_auto_create_login` can take the address by a context key or a tiny inherited hook with no behaviour
change for other callers, prefer that and cover it with a test of the unchanged path. An existing user with that
address: link it only if it is a portal user not linked to another employee; otherwise the leg fails with "A sign-in
with <email> already exists for someone else. Create the sign-in from Access." Step 6's `email` mode becomes available
with either address; its sub-line names the address that will be used. When both exist, the sign-in uses the work email
and the welcome message goes to the personal one (step 1's hint returns to the POC wording).

### 2.2 The link (never stored)
`pb.new.hire.invite` (AbstractModel, `models/invite.py`):
- `_link(employee) -> str`: person never signed in → `partner.signup_prepare(signup_type='signup')` then
  `partner._get_signup_url_for_action(url='/my/welcome')` (FACTS_ONBOARD §B5; verify the exact call the bridge's
  `pb_portal_signup_url` compute uses and reuse it). Already signed in once → the plain `/my/welcome` URL (they sign in
  normally). Read "has signed in" the way the stock sign-up code does (`login_date`).
- The link is built at send/copy time and returned to the caller; it is never written to a field, the chatter, a log, a
  payload or a result dict that is stored.
- `send(employee, kind='welcome'|'reminder') -> {ok, sent:bool, to, message}`: renders the mail template (§2.3) with the
  link in the rendering context, to the private email else the work email. No outgoing mail server for the company/db, or
  no address → `{ok False, sent False, message}` with the plain reason and next step ("This site does not send email.
  Copy the welcome link and send it to <first name> yourself."). Detect "no mail server" the way the product already
  does elsewhere (find the precedent — e.g. how Access decides to show a printed slip instead of emailing).
- `copy_link(employee_id) -> {ok, link, expires_hint}` — HR manager or access manager only; logs "<user> copied the
  welcome link" on the employee chatter (no link in the note). `expires_hint` "Works for 6 days, or until <first name>
  signs in." from the real validity setting.
- Leg `invite` (after `asks`, needs `login`): when there is at least one ask and a login → `send(employee, 'welcome')`;
  result row green "Welcome message sent to <address>" / amber with the reason. No asks → no message, row says so.
  `login_mode == 'code'` or `none` → amber "No welcome link: <first name> has no email sign-in. They can still finish
  these after signing in with the employee number." — and the asks remain visible on `/my/welcome` once they do sign in.

### 2.3 The welcome message
`data/mail_template.xml`: one template on `hr.employee`, subject "Welcome to <company> — a few things before <first day>".
Body (plain, mobile-first, the company's own name, no product vendor name anywhere — white-label rule; the product name
"Payobook" may appear only where `pb_me_portal` itself shows it): greeting, the first day, the list of asked things
(from `summary`), ONE button "Get started", one line "You will choose a password the first time. The link works for 6
days; ask HR for a new one after that." The reminder uses the same template with a different intro line and only the
items still open. Languages: strings translatable; the template is rendered in the employee's language when set.
Outgoing-mail debranding (`biz_mail_debrand`) applies automatically — confirm with a rendered-mail test that the word
"Odoo" is absent from subject, body and footer.

### 2.4 `/my/welcome` and the home rows (controllers + templates in `pb_new_hire`)
- Route `/my/welcome` (`type='http', auth='user', website=True` as the sibling `/my/*` pages are declared — copy the
  decorator and the layout template the `pb_me_details` pages use). Employee = the signed-in user's employee; none → the
  page the other `/my` pages show for "no employee" (reuse). Calls `asks.refresh()` then `summary`.
- Layout (clone the visual language of `/my/journey` + `/my/details`): heading "Welcome, <first name>"; a progress ring
  "2 of 6 done"; "Before <first day>" list — one card per ask: icon, label, state chip (To do / Sent, waiting for HR /
  Done), need chip ("Needed for your first pay"), and the whole card is the link to `ask.url` with `?next=/my/welcome`
  where the target page honours a return parameter (check each; where none exists, the user comes back via the page's own
  back link — do not patch foreign forms). All done → a designed finish state ("That is everything. See you on <day>." +
  link to My Payobook home). No asks at all → redirect to `/my`.
- After a form is submitted on a target page the person should find their way back: add the `/my/welcome` row to the
  home's needs list via `_pbme_needs_extra` (FACTS_ONBOARD §A6): one row "Finish your joining details" with `n` = open
  count, url `/my/welcome`, shown while any ask is open or waiting.
- The privacy-notice gate keeps `?next=` (§A5) — test the full first visit: link → set password → notice → `/my/welcome`.
- Journey step: when `summary.open == 0 and waiting == 0` after a `refresh()`, tick the case's "Finish your own details"
  task (`step_rize_data`, found by its template-step xmlid; `action_done` with a payload note "Ticked when the joining
  details were finished") — once, idempotent, in `refresh()`'s caller on the server, not in the controller.

### 2.5 Reminders (extend `_cron_lifecycle_reminders`, FACTS_ONBOARD §F7)
Inherit the model that owns `_cron_lifecycle_reminders` and add `_nh_remind_asks()` to its run, gated by the config
parameter `pb_new_hire.ask_reminders` (default '1') and by the base `reminders_enabled` switch. Per employee with open
asks and `nh_remind` True (a Boolean on `hr.employee` set from step 5's switch; lives in `pb_new_hire`):
- every 2 days since `nh_reminded_on` (Date on the employee), while the first day is in the future or less than 14 days
  past: `invite.send(employee, 'reminder')`; set `nh_reminded_on` only when sent.
- once, 3 days before the first day (or immediately if the hire was approved later than that), when a `first_pay` ask is
  not done: one activity for the HR contact (the proposer of the hire, else the checklist's HR owner) on the employee:
  "<name> starts on <day> and <N> things needed for the first pay are still missing." (`nh_hr_nudged` Boolean).
- Stops by itself when everything is done. Never reminds an archived employee or a withdrawn/rejected hire (no employee).
New stored fields on `hr.employee` are fine here because they live in `pb_new_hire` (D10).

### 2.6 New joiners board (patch from `pb_new_hire`; do not edit `pb_onboarding` files)
- Server: extend `pb.onboarding._row` (precedent `pb_employee_bank_panel/models/joining_checklist.py:90`) with
  `asked = {total, done, waiting, open, items:[{key,label,state,need}], can_send:bool, can_copy:bool, has_login:bool}`
  from `summary` (after a cheap `refresh()` for the rows on the page — batch it; no N+1).
- Client: `t-inherit` the board's row template to add a chip ("2 of 6 details" — grey at zero-open/all-done per the quiet
  board pattern: colour only when HR must act, i.e. `first_pay` items open within 7 days of the first day → amber) and,
  in the row's detail view, an "Asked from <first name>" list with the state chips plus two buttons: "Send again"
  (`invite.send` reminder; result toast) and "Copy the welcome link" (`copy_link` → clipboard with a fallback
  select-the-text field; toast "Link copied. It works for 6 days, or until <first name> signs in."). Study how the board's
  existing row extensions patch JS/XML and do the same.
- Facade methods for the buttons live on `pb.new.hire.invite`, gated as §2.2.

### 2.7 Studio
- Step 5 invite card per POC: left = "What <first name> receives" (count, address it goes to, due date, the reminders
  switch → draft key `remind`, the shield hint about the bank second approval, and the true sentence "<first name>
  chooses a password the first time."); right = the phone preview listing the asks (staggered enter, reduced-motion safe)
  with "Start · about N minutes". States: no asks ("Nothing to send"); no email sign-in possible (amber: "No email
  address yet, so no welcome link. Add one in step 1, or <first name> can finish these after signing in with the employee
  number."); site sends no email (`load()` tells the screen): "This site does not send email. After approval, copy the
  welcome link from New joiners and send it yourself."
- Done card (pending and applied): the POC's "What <first name> has been asked for" list. Applied + can copy → a "Copy
  the welcome link" button right there.
- Values keys: `remind` (bool). Leg order now: … `details` → `papers` → `asks` → `login` → `case` → `buddy` →
  `equipment` → `letter` → `invite` (invite last: it needs the login and the asks; confirm asks do not need the case).

## 3. Safety rails
- The link: built on demand, returned once, never persisted or logged (grep the test DB's chatter, mail queue bodies are
  the only place it may appear — and only in the outgoing mail itself). Add a test that scans `mail_message.body`,
  `ir_logging` (if used) and the proposal JSON for `signup`/`token=` after a full apply.
- `copy_link` and "Send again" are HR-manager/access-manager only and rate-limited per employee (not more than once a
  minute; plain message otherwise).
- `/my/welcome` shows only the signed-in person's own asks; an HR user opening it sees their own (usually none → `/my`).
- Reminders respect the site's mail lock: if sending is impossible the job does nothing and writes nothing.
- No email may be sent by the test suite or the browser walk to a real address: walk world uses example.com addresses and
  the local server has no outgoing server unless you add a local catcher (say which).

## 4. Tests (tag `newhire`) — V1…
V1 login by private email (new user, reuse, clash → failed leg); work-email path unchanged.
V2 `_link`: sign-up link for a never-signed-in user carries the redirect to `/my/welcome`; plain URL after a login.
V3 `send`: mail created to the private address with the open items and no vendor name; no mail server → `{sent False}` +
   sentence; leg rows for email / code / none modes.
V4 link never persisted (the scan in §3).
V5 `/my/welcome` (HttpCase): own asks only; states; all done → finish state; no asks → redirect; another user's asks not shown.
V6 first-visit chain with the privacy gate keeps `next`.
V7 home needs row count; disappears when done.
V8 journey step ticks itself once when all done; not before.
V9 reminders: 2-day cadence, stops when done, respects both switches, `nh_remind` off → none; HR nudge once, 3 days before.
V10 board row `asked` shape, batching (assert query count does not grow per row), gates on `can_send`/`can_copy`.
V11 rate limit. V12 P1–P3a suites green, static gates.
Browser walk (local mail catcher or the mail queue list as evidence): F1 step 5 invite card states (asks / none / no
email / site without email); F2 send → approve → mail in the queue with the right list; F3 open the sign-up link in a
private window: set password → notice → `/my/welcome` at phone width (≤ 400 px) — screenshot; F4 finish the bank ask via
`/my/details/bank` and one paper via upload → `/my/welcome` shows "Sent, waiting for HR" / "Done"; HR approves the bank
request → Done; F5 New joiners board chip + list update; "Send again", "Copy the welcome link" (paste into a private
window → works); F6 run the reminder job by hand twice (cadence) and the HR nudge; F7 all done → journey step ticked,
home row gone, finish state; F8 employee-number sign-in person sees `/my/welcome` after signing in; F9 console clean on
every screen touched (backend and `/my`).

## 5. Report back — `NEWHIRE_P3B_REPORT.md`
Same sections as P3a. Add: every email/activity this phase can send and when; exactly what is true about link lifetime on
this build; what a site with email switched off sees at each point. Commit feature-scoped with explicit paths, report +
ledger gotchas as the final docs commit. Do not push.
