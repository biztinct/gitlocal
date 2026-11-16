# WDGAP S9-C report — Employee voice (anonymous surveys)

Branch `wdgap-s9c` (from `origin/19.1` @ `abc2259b6`). Implementer + tester + self-review.
No deploy, no live server touched. Local database `wdgap_s9c_t` (copy of `upd_p6_t_tpl`,
brought to 19.1), dropped at the end with its file store folder.

## 1. What was built — new module `pb_voice` 19.0.1.0.0

**HR (Talent › Voice tab, ⌘K "Employee surveys", Settings › HR › Employee surveys)**
- Survey rounds: name, a word to everyone, companies asked (+ optional departments), closing
  date, smallest group shown (5, can be raised, never lowered), reminders every N days.
- Questions: library of 15 (en/vi/id) added with "Add from the library" (every language is
  copied), "Add our company values" (Praise's values, probed), or HR's own — kinds: agree/
  disagree 5 steps, would recommend 0–10 (eNPS), pick one option, written comment.
  Questions and audience lock once sent out ("Make a copy to ask again").
- Board: quiet glance (being set up / open / with results / action plans; grey at zero,
  amber/rose only to act), round cards with answered-of-asked bar, drawer with Overview,
  **Who can answer** (asked / can sign in / no login yet with names + **"Make sign-in
  slips"** → Access › People where "Logins for workers" prints slips — ruling P5), Results,
  Action plans. Send out / Close now / Copy / Delete (drafts) with plain confirmations.
- Results (only after close): picker "Everyone asked / each company / each department";
  answered x of y; would-recommend score with yes/maybe/no; themes by share who agree
  (weakest first, "+" starts an action plan on that theme); question by question (stacked
  5-step bar, average; choice distribution); **written comments (HR only)**; Excel download.
  Hidden groups say why and carry no figure.
- Action plans: what we will do, theme, owner (staff login), due date, status, progress
  note. The owner gets a standard to-do and a "Needs you" row; can update status/progress
  on My Payobook or the backend, nothing else.

**Employees (My Payobook only, ruling P5)**
- "Needs you" row ("A short survey is waiting — Anonymous. Open until …"), a "Your voice"
  card on the home while one waits, a "Surveys" tile under More (only for someone who has
  been asked — C-3), `/my/voice` (waiting / answered, still open / closed / plans I own),
  `/my/voice/<id>` form with the anonymity promise on top, one answer per person, a
  thank-you after sending. Works at phone width; translated pages checked in Vietnamese.

**Managers** — "Team voice" card on `/my/team` (template inherited by xpath, controller adds
its value to the page's own context): latest closed round, their **team** when that group
can be shown, otherwise their **department**, otherwise a plain sentence; answered x of y,
would-recommend, themes; never comments; their own open action plans.

## 2. Anonymity — exactly how it is guaranteed, and the test for each point

The design goes further than the shift-pulse precedent. The privacy contract is the
docstring of `pb_voice/models/voice_box.py`.

| # | Guarantee | How | Test |
|---|---|---|---|
| 1 | **No answer row exists at all.** | While a round is open the database holds NO answer content. Each answer is written as a sealed file OUTSIDE the database (`<filestore>/pb_voice/<round>/<random>.sealed`). | A02: after 6 answers, every text column of every table in the database is searched for the comment text — found nowhere; the sealed files hold it and carry no id, name, login or e-mail. |
| 2 | **No ORM stamps.** | The one table that ever holds answers (`pb.voice.box`) has `_log_access = False`: no `create_uid/write_uid/create_date/write_date` columns exist; no foreign key except to the round. | A01: table columns are exactly `id, round_id, marks, sealed`; FK only to `pb_voice_round`. |
| 3 | **Nothing about the person is written by answering.** | The answer request writes ONE thing in the database: a code added to the sorted "has answered" list. No message, activity, mail, bus note, follower, log; the round and who-was-asked rows are not touched; no `track=True` page view; no log line names the person. | A04: before/after max ids of mail_message, mail_activity, mail_mail, bus_bus, mail_followers, ir_logging, res_device_log — no new row; round and invite write stamps unchanged. |
| 4 | **No transaction-id / insertion-order / time link.** | Answers enter the database ONCE, when the round closes, in a single write, as COUNTS per group cell (how many chose each step) plus comments sorted by cell, question and text. So no row id, sequence, PostgreSQL `xmin`, order or time belongs to any answer. (Odoo 19 inserts `res_device_log` — user, IP, time — in the request's own transaction, `odoo/addons/base/models/res_device.py:94`; storing an answer in that transaction would have shared its `xmin`.) | A05: after close the box holds counts only (6 answers in cells), comments sorted, no name/login anywhere, cell keys are group ids only. |
| 5 | **"Who has answered" is a separate yes/no list that cannot be joined.** | A sorted list of HMAC-SHA256 codes of the person, keyed with a random per-round key kept in the FILE STORE (never in the database). Sorted → no answering order. Used only for: one answer per person, reminders, the person's own Needs-you row. HR never sees per-person participation — only "x of y answered". | A03: codes are 40-hex, sorted, equal no employee/user id or name; the key's hex is found in no database column; the key file exists outside. A09 + H01: second answer refused (ORM and HTTP). |
| 6 | **After close, nobody can tell who answered.** | Close wipes the list and, once the close commits, destroys the key and every sealed file. | A05 / A05b: list = `[]`, key gone after commit, folder gone, `_voice_unanswered()` empty. |
| 7 | **Cells are never small.** | When a round is sent out, groups (company, department, the manager's team) are fixed and each person's combination of groups is coarsened until every combination covers at least the floor of INVITED people (small teams/departments are counted one level up). | A08: every stored cell ≥ 5 invited; a team of 4 and a department of 2 get no group; A08b: same holds for floors 5, 6, 8, 12. |
| 8 | **Too few answers: nothing kept.** | Fewer than the floor in the whole round at close → sealed answers destroyed, nothing stored, "no results". | A06: comment found nowhere in the database; results state "too_few". |
| 9 | **HR cannot read the raw store.** | `pb.voice.box` has one all-zero access line (no group can read/write); only the results facade reads it under sudo behind its own gate; who-was-asked "cell" field is system-only. | A07: HR and a system administrator get AccessError on search/read; HR does not see the cell field. F07: a portal login has no right on any pb_voice model. |
| 10 | **Floor of 5 for numbers AND comments; comments HR only.** | One facade (`pb.voice`) for screen, Excel and manager card. Hidden group → no figure, no count, no comment. | R02 (Ops 3 answers: no figures, no count, its comment not in its view), R07 (Excel: hidden rows say "Hidden", no figure), R08/R08b (card has no comments; hidden when too few). |
| 11 | **No working out by subtraction.** | Secondary suppression over EVERY group anyone sees in the round (HR's companies/departments and managers' teams): PAIRS — two overlapping shown groups may not differ by 1–4 answers; PARTS — a group minus its shown parts of one kind may not leave 1–4. Smaller/finer group hidden until stable. | R03 (company 8 vs Sales 6 → Sales and the team hidden), R04 (Sales 5 + Ops 5 + General 3 → one department hidden), R05 (team 5 inside department 7 → one hidden), R05b (6 random answer patterns over 27 people: no shown pair/part ever differs by 1–4). |
| 12 | **Results only after close.** | Figures that move while open would show one answer at a time to somebody watching. | R01. |
| 13 | **HR of another company / plain staff see nothing.** | Record rules + "every company the round asked must be one you can see" (otherwise whole-round minus own company = another company). | R09, R07b, H03 (non-HR gets 404 on the Excel address). |

**What is NOT protected (said in the help text, not promised away):** somebody with access
to the SERVER itself (its disk) while a round is open could read sealed files or the key.
That is a system administrator, not HR and not a database user. After close even they
cannot. Cross-round comparison (two rounds asking almost the same people) is not
suppressed — different questions and times; noted under Left for later.

**Rating questions are required** (only comments are optional): otherwise a question
answered by 1–2 people inside a shown group could be singled out.

## 3. Reminders and email (tenant rule)

- "Does this system send email" = an active outgoing mail server (QF2 rule). Tenants with
  email off: **nothing is ever queued** (F04: no invitation, no reminder; the day's reminder
  is still stamped; the "Needs you" row appears for the person and disappears once they
  answer). The board says so in one line.
- With email: one invitation each at send-out; reminders every N days ONLY to people who
  have not answered (worked out with the key), `auto_delete` so the mail rows go once sent
  (F05: 27 invitations, 24 reminders after 3 answered, none the next day).
- The daily job closes rounds past their closing day (F06) and tidies sealed folders; on a
  database with no round it reads one empty table.

## 4. Files touched outside the new module

None. `pb_me_portal`, `pb_me_team`, `biz_access`, `pb_talent_hub`, `pb_settings`,
`pb_lifecycle`, `pb_ess_workforce`, `pb_explorer`, `pb_pack_*` untouched.
Hooks used (all call `super()`): `pb.me.home._pbme_extra_cards`, `._pbme_needs_extra`,
`TILES.setdefault('/my/voice', group 'more')`, `PbMePortal`, `PbMeTeamPortal._team_page`
(adds `pbv_team` to the page's qcontext), QWeb inherit of `pb_me_team.portal_my_team`
(xpath `//div[hasclass('pbmt')]` inside — the most stable anchor), `portal.portal_my_home`
docs entry. **No existing module needs a version raise.**

## 5. Tests

`wdgap_s9c_t`, employee-side calls as real PORTAL logins (ORM `with_user` + HTTP).

| Series | Tests | Result |
|---|---|---|
| A01–A09 (+A05b, A08b) anonymity, DB-level | 11 | PASS |
| R01–R09 (+R05b, R07b, R08b, R08c) results, floor, subtraction, Excel, manager card, rights | 13 | PASS |
| F01–F10 silent install, send-out rules, answer checks, reminders without/with email, auto-close, portal rights, action plans, library languages, who-can-answer/board | 10 | PASS |
| H01–H04 HTTP as portal (answer once, not asked, Excel route, team card) | 4 | PASS |
| P01–P03 PO gate (vi + id parse with the loader, every msgid covered, module/occurrence/odoo-python markers, placeholders kept, no vendor word in any msgstr or user-visible file), translations reach the screen | 3 | PASS |

**Suites vs baseline** (baseline recorded on the same database BEFORE any pb_voice code):

| Suite | Tests | Failures | vs baseline |
|---|---|---|---|
| pb_voice | 41 test methods | 0 | new |
| pb_me_portal (hooks used, not edited) | 125 | the same 5: test_05_grid (E), test_06_font (F), test_12_vi_po… (F), test_01_profile_change_flow… (E), test_t1_7… (F) | **= baseline**. Baseline: test_05_grid (E), test_06_font (F), test_12_vi_po… (F), test_01_profile_change_flow… (E), test_t1_7… (F) |
| pb_me_team (template inherited, not edited) | 22 | 0 | **= baseline** (0) |

Final combined run (`-u pb_me_portal,pb_me_team,pb_voice`, all three suites, after the last code change): "3 failed, 2 error(s) of 150 tests" — exactly the five pb_me_portal baseline items above. The translation tests were run once more after the last .po regeneration.

**Browser walk** (own isolated browser contexts at `http://127.0.0.1:8937`, server with no
scheduled jobs; HR = admin on a DEMO company, 8 portal walkers + a staff manager + 5 people
with no login): empty Voice tab inside Talent (quiet, grey) → New survey → Add from the
library (5 ticked) → board drawer "Who can answer" (14 asked / 9 can sign in / 5 no login,
names) → "Make sign-in slips" lands on Access › People with "Logins for workers" and a way
back → Send out (confirmation) → employee home: Needs you row, Your voice card, Surveys
tile → form → answered (thank-you, "Answered, still open"); database then held only the
mark, the answer was a sealed file → 5 more answers → Close now → Results (everyone,
company, department; themes; comments HR only) → action plan from the weakest theme
(owner = the manager) → Excel 200 → manager's /my/team "Team voice" card (team 6 of 8,
themes, own plan, no comments) → owner updates the plan on /my/voice → Vietnamese
/vi/my/voice and the form at 390 px phone width. Console clean on every page (the only
500s are the template's missing logo/favicon files, ledger S6A-7). Fixed from the walk:
backend bundle broke on `min(640px, 100vw)` (S9C-2), unstyled buttons/badge/select on my
pages (S9C-3), question titles sitting on the card border, ISO dates on screen → reader's
format, Close now now lands on Results.

Static gates: py_compile, XML parse, `node --check`, pyflakes clean; vendor-word scan of
views/static/data and every msgstr: none.

## 6. Contracts other phases may rely on

- Models: `pb.voice.round` (`action_open`, `action_close`, `voice_my_rounds(emp)`,
  `voice_form(emp)`, `voice_submit(emp, answers, comments)`, `can_open()`),
  `pb.voice.question`, `pb.voice.invite`, `pb.voice.group`, `pb.voice.library`,
  `pb.voice.action`, `pb.voice.box` (no rights), facade `pb.voice` (`get_board`,
  `get_round`, `get_results(round_id, group)`, `save_action`, `results_xlsx`,
  `manager_card(emp)`).
- Home: card key `voice` (template `pb_voice.pbme_card_voice`), Needs-you keys
  `voice_survey`, `voice_actions`; tile `/my/voice` (More).
- Talent lens key `voice` (seq 50), palette rows `voice_board` 2900 / `voice_library` 2910,
  Settings category `voice` (group hr), client action tag `pb_voice_board`.
- Routes: `/my/voice`, `/my/voice/<id>`, `/my/voice/<id>/answer` (POST),
  `/my/voice/plan/<id>` (POST), `/pb_voice/results/<id>.xlsx`.
- Cron `pb_voice.cron_voice_daily` (daily, quiet when empty).

## 7. Deploy notes (for the Step 9 go-live)

- `-i pb_voice` on all five databases (depends on pb_me_portal, pb_me_team, pb_talent_hub,
  pb_settings, pb_import_kit, pb_filter_kit, biz_access, hr, mail — all present). Asset
  purge after install (new backend + frontend files).
- Risky tier: new access rules; nothing touches pay.
- **The file store matters for open rounds**: sealed answers and each round's key live in
  `<data_dir>/filestore/<db>/pb_voice/`. A database copied or restored WITHOUT its file
  store while a round is open loses that round's answers so far and its "has answered"
  list (a new key is made; people could answer again). Rehearsal clones made with
  `createdb -T` have no file store — fine, there is no round at go-live.
- Silent: no round, no email, no card, no tile until HR sends a round out; the library is
  offered only.
- Workflow Studio shows "View workflow / Set up workflow" on the round form (it lists every
  model with a company — S9-F9). Harmless (HR's own records); answers have no model to offer.

## 8. Owner questions (plain words)

1. **Results open only when a survey closes.** While it is open HR sees only "x of y have
   answered". If results moved while people were still answering, someone watching could
   see one person's answers appear. Keep it this way?
2. **Every rating question must be answered; only comments are optional.** If a question
   could be skipped, a question answered by only one or two people in a team could give
   them away. Keep it required?
3. **HR sees results by company and department; managers see their own team.** Should HR
   also see each team's results? (Teams are about 5 people, so most would show as hidden,
   and showing them to HR makes more combinations to hide.)
4. **Library wording in Vietnamese and Indonesian** was written by us. Please have a native
   speaker read the 15 questions and the five answer words before customers use them.

## 9. Defaults taken without asking (state in the step report)

- Surveys are our own small module, not the standard survey tool (FACTS §7).
- Action plans are our own simple list, not workflow tasks.
- When a manager's team is too small, the card shows their department (the FACTS Q4 wording
  the owner accepted); otherwise a plain "counted in the company's results" sentence.
- No filter panel on the board (a company runs a few surveys a year): the glance numbers
  filter the cards instead.
- First build groups: company, department, manager's team. No tenure or age bands.

## 10. Left for later

- Tenure / age band groupings (only where every cell passes the floor).
- A summary of written comments by PayAI.
- An optional invitation as an announcement (probe `pb.hr.comm.post`) — not built.
- A proper "People" tile for Surveys on the home (needs the pb_me_portal prep commit, C-3).
- Comparing two rounds over time (trend lines) and cross-round suppression.
- `_workflow_capabilities` declaration for rounds (not needed now).

## 11. Gotchas → ledger rows

| # | Phase | Gotcha |
|---|---|---|
| S9C-1 | S9-C | Odoo 19 writes `res_device_log` (user, IP, time) IN THE REQUEST'S OWN TRANSACTION once an hour per device (`odoo/addons/base/models/res_device.py:94`). Anything "anonymous" written in the person's request shares its PostgreSQL `xmin` with a row naming them, and `xmin` is readable with plain SQL. Anonymous content must not be written in the person's own transaction (pb_voice seals it outside the database and writes it once at close). |
| S9C-2 | S9-C | Sass `min()`/`max()` in a backend `.scss` (`width: min(640px, 100vw)`) is evaluated by the old compiler: "Incompatible units: 'vw' and 'px'" — the WHOLE backend bundle falls back to "A css error occurred" and the app is unstyled. Use `width` + `max-width`. |
| S9C-3 | S9-C | `.pbme-btn--pri` / `--out` and the `.pbme-badge--<tone>` colours are scoped to the employee HOME; on a module's own /my page they render as plain white buttons and bare icons. Style them in the module's own scope. |
| S9C-4 | S9-C | Odoo 19 has no `--i18n-export` flag: `odoo-bin i18n export -c conf -d db -o file.pot module`, and it reads views from the DATABASE — `-u` the module first or the .pot carries the old view text. |
| S9C-5 | S9-C | `cr.postcommit` / `cr.postrollback` callbacks do not run on a test's own savepoint; files a test writes outside the database stay. Clean them in `tearDownClass` (pb_voice tests remove their round folders). |
| S9C-6 | S9-C | A native `<legend>` in a bordered card sits ON the card's top border; `float: left; width: 100%` on the legend plus `clear: both` on the next element puts it inside. |
