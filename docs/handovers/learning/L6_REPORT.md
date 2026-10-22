# LEARNING L6 — Numbers and the Overview, finished — report

Implementer: Opus, 2026-10-22. Spec: `L6_NUMBERS_OVERVIEW.md` (incl. the "Carried in from L3–L5 walks" block). Ledger:
`LEARNING_LEDGER.md` (candidate rows from LN59 in §5).
Status: **AT DEPLOY GATE** — built, committed (WIP + fixes), tested locally (suites + Chrome walk). Not deployed. Not pushed.

## 1. What ships (committed on 19.1, not pushed)

| Module | Live now | After L6 |
|---|---|---|
| pb_training | 19.0.1.9.0 | **19.0.1.10.0** — one new column (`pb_training_session.cost`, plus a stored related currency), six new client-action records (Learning settings and its five card doors), no new table, no migration, nothing existing rewritten. |
| pb_home_hub | 19.0.1.4.0 | **19.0.1.4.1** — Home › TEAM's Learning section gets three quiet chips (two new counts in the payload, no amounts). Minimal NAV-module touch: `team_facade._training`, `team_lens.{js,xml,scss}`, `vi_VN.po`. |
| pb_learn | 19.0.20.6.0 | **19.0.20.6.1** — Help's description of Learning now lists the final eleven tabs (generated content only; `vi_VN.po` unchanged). |
| pb_training_growth | 19.0.1.0.0 | unchanged (reloads with `-u pb_training`) |
| pb_settings | — | **unchanged**: the "Learning" category names its own group (`group: "hr"`) like L2's card did, so no `GROUP_OF_CATEGORY` edit and no server gate row is needed (the server gate reads the descriptor's groups). |

### What a user sees
- **Learning › Numbers** — new filters **site, country, kind of training** (each offered only when the data has more than one).
  New tiles (grey at zero): **Hours of training**, **Spent on training**, **Course rating**. New and extended sections, in order:
  - **Hours** — "20.25 hours of training, by 14 people · 1.45 hours each on average"; by kind (Online · In a room or on site ·
    Toolbox talk), by department, by course, by person (ten, then "Show more people", "The spreadsheet has everybody").
    A course finished by attending a session counts once.
  - **Sessions** (L4, unchanged).
  - **Cost** — one sentence ("$ 7,500,000 spent on training · 1% of this year's allowances used"), lines for claims agreed (and paid),
    outside courses agreed (money set aside) and sessions, the allowance line, the HR-operations budget line when budgets are used,
    and L5's course requests by state (L5's "Requests and spend" folded in here). Two currencies are never added up.
  - **Required training** — the matrix's own summary for the same department / site / country, by rule, site, department,
    **country** and **safety group**; a plain sentence when there are no rules yet.
  - **Did it work?** — L5's Ratings and Did it work? as one section (ratings, recommend %, managers' answers, top courses).
  - **Skills** (L5), **Country reports** (all four packs: a switched-on pack is a download, a switched-off one says "off" and where
    to switch it on), **Certificates** (L1), **What people claimed back**.
  - **Spreadsheet** gains **Hours** (by person), **Cost**, **Compliance**, **Effect** and the flat **Assignments** sheet (one row per
    assignment: employee, department, job, site, country, safety group, course, kind, why, path, requirement, assigned on, due,
    finished on, state, score, hours, certificate valid until, version).
- **Learning › Overview** — the headline is built from every block: the situation sentence, then at most three concerns, worst first
  (late → late on a path → missing required → certificates expiring → sessions to close → requests → follow-ups). What waits is in
  amber chips in that order; everything at zero sits in one grey line ("Nothing waiting on …"). Nothing waiting = the calm hero
  "All clear. N people are in date." with a green tick. Sessions block gains "seats free". On a phone the departments fold away.
- **Settings › HR › Learning** (replaces L2's "Required training" category) — five cards, each opening one screen on its tab:
  **Report pack** (on/off, weekly/monthly, who gets it — addresses checked as you type, at most 20 — **Preview the email**,
  **Send me a test**), **Reminders** (switch, manager / HR lead days, certificate reminders, renewal window, morning cap),
  **Feedback** (course feedback, manager follow-up and its days), **Country packs** (the L2 screen, embedded), **Day one**.
  Every switch has the sentence of what it does under it, with its numbers. Training managers read; only the **head of training**
  (or a system administrator) saves. The Required tab's settings link now opens Country packs here.
- **Report pack email** (English, LD10) — adds hours (and the top five people), cost against the allowance (and the budget line),
  required training, ratings and managers' answers, a link into Learning; the attachment is the full spreadsheet with every sheet.
- **Home › TEAM** (managers) — three quiet chips under the Learning line: courses late today · certificates of my people running out
  within 30 days · training requests (course and more-time) waiting on me (opens the inbox).
- **Learning record PDF** — a **Sessions** table (course, kind, held on, attended / did not come, hours), "N sessions attended" in the
  summary line, and hours counted once (a course finished by attending counts through the attendance).
- **Sessions** — a session can carry **What it cost** (New session drawer; shown on the session page; added up in Numbers › Cost).
- **Every Learning screen** tells "no access" apart from "could not load": a failed read (server restart, 502) shows
  "That did not load — Nothing was changed. The server may be busy for a moment. Try again." with a **Try again** button (fixed on
  Courses / Assigned / Claims, Numbers, the toolbox-talk drawer; the other lenses already had it, now tested on all of them).
- **Help** — the Learning page description lists Overview · My learning · Courses · Paths · Assigned · Required · Tests ·
  Certificates · Claims · Skills · Numbers with one line each (EN + VI); the practice copy's menu has the eleven tabs.
- **Found and fixed in the walk (pre-existing since L5):** a percentage written next to a named placeholder printed "%%" in the
  browser ("80%% would recommend", "1%%"). Fixed in all six places (course drawer, outside course page, Tests results, Numbers).

## 2. Tests

Local runtime `/Users/adity/odoo19`, overlay `scratchpad/l6stage/{pb_training,pb_training_growth,pb_home_hub,pb_learn}` in front of
the L0 staging tree. Test databases are copies of `am_l5_walk` (L5's walked DB, pb_training 19.0.1.9.0) plus its filestore (LN30),
run exactly as the live upgrade: `-u pb_training,pb_home_hub,pb_learn`.

| # | Result |
|---|---|
| T1 | **Pass** (3): 3 h online + a 2 h session attended = 5 h for that person (courses 1, sessions 1 — the room course counted once, through the attendance); the no-show has no hours; a 15-minute toolbox talk = 0.25 h; total = Σ people = Σ departments; by kind 3 / 2 / 0.25; a range two months back is empty with the sentence; kind filter "toolbox" = 0.25; department filter; the Hours tile; the screen gets ≤ 50 people. |
| T2 | **Pass** (4): claim agreed 1,000,000 + outside course agreed 500,000 + session cost 250,000 = 1,750,000; allowance total = company figure × people, used 1,500,000, used % rounded; budget line read only when `pb_budget` is installed and left untouched; `one_currency` raises on two currencies (no total drawn); empty sentence. |
| T3 | **Pass** (2): no rules → `compliance` is null; with a rule, percent / missing / people equal `_matrix_data(filters)['summary']` for no filter and a department filter; the four splits exist and add up. |
| T4 | **Pass** (2): three answers → count 3, average = recount, recommend % = share of 4–5; empty state. |
| T5 | **Pass**: the five new sheets exist; Assignments header = the nineteen columns in order; one row per assignment; department, course, kind ("Online" / "In a room or on site"), why, state and hours resolved; the Hours sheet lists the person. |
| T6 | **Pass** (3): calm with nothing waiting ("Nobody is on a course yet.", every chip still in `queue`, all zero, `waiting` empty); "All clear. 1 person is in date."; two late + one missing required + one session to close → concerns late, required, sessions in that order, the situation sentence first, at most three, `waiting` only counts > 0. |
| T7 | **Pass** (4): plain user and trainer refused; training manager reads (`can_write` false) and is refused on save; head of training saves; round trip (addresses split on `,` `;` and new lines, de-duplicated; period; five numbers; switches); the reminders sentence carries the new days; a bad address or an out-of-range number changes nothing (nothing half-written); 25 addresses refused; the morning job with reminders off sends nothing and the new manager days are what the job reads. |
| T8 | **Pass** (3): the body carries "Most hours of training", the person, the hours sentence and "Open Learning"; preview for managers only; **Send me a test → exactly one mail, to the presser's own address, with the spreadsheet attached, and the period is not used up**; a plain user is refused; the recipient list is capped at 20. |
| T9 | **Pass**: a certificate running out in 10 days counts (90 days does not), names the person; a course request waiting on the manager's live seat counts 1 for the manager and 0 for a report; Home › TEAM carries `expiring` 1 / `waiting` 1 and no amount-like key. pb_home_hub's own `test_team_p3c` (forbidden-key walk) in the suites below. |
| T10 | **Pass** (5): no vendor word, no emoji in the six new files; Vietnamese present; **every Learning lens component (14) sets `failed` on a failed read, never `allowed = false` in a catch, and its template has the failed branch with a retry**; Help content's hub_learning has exactly the eleven tabs; the Settings category is "learning" with the five cards and no "required_training". |
| Suites | `/pb_training,/pb_training_growth,/pb_learning_hub,/pb_home_hub` on a fresh copy with `-u pb_training,pb_home_hub,pb_learn`: **429 tests, 2 failed, 10 errors** — the 2 are `TestTheAssignmentsTab` ×2 (pre-existing since L0); the 10 errors were the claims test classes stopping in setUpClass because the seeded walk DB already holds a 2026 company allowance (a test-data clash, not L6) — fixed in the test (`22f74c1e8`) and those 10 classes rerun **61 tests, 0 failed** (§9). L5's follow-up test had the same kind of clash and is isolated too (`c71f23071`). |
| PO gate | pb_training 2,290 rows, 0 code rows without a value; pb_home_hub 88 / 0. `pb_learn/i18n/vi_VN.po` unchanged by the regeneration. |
| Help checks | generator `--check` up to date (6 files); `check_contract` 73 passed; step shape 0 failed; scenario rules ok; jargon lint clean; "gõ DUYỆT" = 1; `pb_payruns` present; 0 "These figures do not add up"; JS library 111/0, guide_panel 117/0, lesson_panel 113/0. |

**T11 — local Chrome walk** (`localhost:8074`, `am_l6_walk` = L5's walked DB upgraded, seeded with `l6_demo_seed.py`, company 1):
- **Head of training (admin), EN — Overview:** "11 people are on 8 courses. 8 are past their date. 5 people are late on a path. 38
  people are missing required training." Amber chips in priority order: 8 Past their date · 5 Late on a path · 38 Missing required
  training · 3 Certificates expiring · 1 Follow-ups waiting on managers; grey line "Nothing waiting on" Claims to agree · More time
  requests · Sessions to close · Course requests waiting. Sessions block shows "0 seats free".
- **Numbers:** site and kind filters offered; tiles 20.25 Hours of training · $ 7,500,000.00 Spent on training · 4.2 Course rating;
  Hours by kind (Online 1.25 h · In a room or on site 18 h · Toolbox talk 1 h, matching the Sessions section's 19 hours), by
  department, by course, by person with Show more people; Cost lines + allowance line + course requests; Required training by rule /
  site / department / country / safety group; Did it work? (4.2 out of 5 from 6 ratings · 83% would recommend; managers 3.5/5 ·
  100% used); Country reports (two downloads, two "off"); spreadsheet downloads (61 rows; the Renewals report builds).
- **"Could not load":** with the board / numbers reads forced to fail in the browser, Numbers and Courses show "That did not load …
  Try again" (screenshot `outputs/learning-l6-20261022/local-numbers-could-not-load.jpg`); Try again after the reads recover → the
  board draws.
- **Settings › HR › Learning:** five cards; old "Required training" category gone; Reminders tab — manager days 2 → 3 → Save →
  "Saved." and the sentence now says "the manager after 3 days late"; Report pack — "not-an-address is not an email address." with
  Save disabled, Undo; Preview the email modal (subject, "Nobody is set to receive it yet.", the attachment name, the body); Send me a
  test disabled with "Add an email address to your profile to get a test copy." (local admin has no address — the send is T8);
  Country packs tab = the four pack switches without the duplicated switches.
- **Session page:** the cost shows ($ 3,500,000.00); the New session drawer has "What it cost (optional)" with its note.
- **Manager (manager.p3c, VI) — Home › TEAM:** "Đào tạo — 3 người có khóa đào tạo bắt buộc đã quá hạn"; chips **4 khóa học trễ hạn**
  (amber) · **2 chứng chỉ hết hạn trong 30 ngày tới** (amber) · **0 yêu cầu đào tạo đang chờ bạn** (grey). Screenshot
  `local-team-chips-vi.jpg`.
- **Vietnamese (server-side, `lang=vi_VN`):** Overview "11 người đang học 8 khóa. 8 người đã quá hạn. 5 người bị trễ hạn ở lộ trình.
  38 người còn thiếu đào tạo bắt buộc."; Hours "20.25 giờ đào tạo, của 14 người · trung bình 1.45 giờ mỗi người." with the kinds in
  Vietnamese; Cost "Đã chi $ 7.500.000,00 cho đào tạo · đã dùng 1% ngân sách đào tạo năm nay."; settings sentences in Vietnamese.
- **Learning record (HTML render, one `article`):** Sessions table and "1 session attended" in the summary; hours counted once.
- **Help content served:** hub_learning has the eleven tabs with Vietnamese lines.
- **Console:** no errors on any screen read. **Not walked:** phone width (the agent's window cannot be resized; CSS written: hero and
  chips first, departments fold behind Show), the PDF itself (no PDF engine on this Mac — the record is one document, as before).

## 3. Deviations from the handover, and why

1. **No `pb_settings` change.** The handover asked for `GROUP_OF_CATEGORY.learning = "hr"` and a server gate row. The descriptor's
   own `group: "hr"` wins in `groupOf()`, and `resolve_gates` reads the descriptor's `groups` — the L2 precedent. So pb_settings
   is not upgraded.
2. **Sessions had no cost.** "Session costs" needed a field: `pb.training.session.cost` (company currency, stored related), set in
   the New session drawer. New column, no migration.
3. **Sign-offs (LD5) are not built**, so `by_kind.signoff` is always 0 and the Overview's "sign-offs waiting" concern is **sessions to
   close** (the closest real "waiting to be signed off" in the product); the sessions block carries `signoffs: 0` for shape.
4. **`queue` keeps every chip** (L0–L5 contract and tests; quiet board); the handover's "rows only when > 0" is a new `waiting` list
   (worst first) that the hero draws in colour, with the zero ones in one grey line.
5. **"Requests waiting on HR"** = course requests waiting for any decision (the board's own count), plus claims and more-time
   requests as one "requests" concern; follow-ups waiting on managers are the last concern.
6. **Calm count "N people are in date":** with rules, the people the matrix covers less those missing something; without rules,
   everybody put on a course who is not past a date.
7. **Compliance** reuses `required_reports._required_numbers` with the Numbers filters (department, site, country) — one computation
   for the `required` (L2 keys) and `compliance` (L6 keys) blocks.
8. **Hours rule:** finished courses by the day they were finished, plus attended session hours by the day the session was held; an
   assignment finished through attendance adds only what it counts for above the attended hours (so blended courses add their
   lessons' part, room courses add nothing twice).
9. **Allowance total** = every active person's allowance for the year (their own figure, else the company's) — on payobook that is
   headcount × the company figure, so the used % is small. Used = claims agreed + outside courses agreed for that year.
10. **Budget line** = HR-operations budget lines of the year (read only, one currency or none).
11. **Ratings + Did it work?** are one section now; "Requests and spend" moved into Cost (no second copies — carried-in note).
12. **The screen gets 50 people on the Hours block** (by_person is trimmed unless the spreadsheet / pack asks for everybody).
13. **`pb_home_hub` test not edited**: the TEAM check is in `pb_training/tests/test_l6.py` (T9), skipping itself when pb_home_hub is
    absent; pb_home_hub's own forbidden-key walk covers the new keys.
14. **The "%%" fix** touched L5 strings in `course_extras.js`, `outside_lens.js`, `training_tests_lens.js` (and their `.po` entries:
    the msgid loses the `%%`, the percent rides the value).

## 4. Vietnamese

`pb_training/i18n/vi_VN.po`: **162 new entries** and 78 existing entries gained the marker or occurrence the new screens need (LN48);
text-level merge, **pure additions** apart from the five "%%" msgids rewritten on purpose (§3.14). Words said through `tr()` (hours
kinds, "N sessions attended") are `odoo-python` entries. `pb_home_hub/i18n/vi_VN.po`: 8 new entries. Mail bodies, subjects and the
pack stay English (LD10). "Report pack" = **Báo cáo định kỳ**, "Send me a test" = **Gửi thử cho tôi**, "All clear" = **Mọi thứ ổn**.

## 5. Ledger rows to add after the deploy (candidates, from LN59)

- LN59: **The web client's `sprintf` does not turn `%%` into `%` when the placeholders are NAMED** (`_t("%(pct)s%% …", {pct})`
  prints "80%%"); positional `_t("%s%% …", n)` is fine. Put the percent sign in the value (`pct: \`${n}%\``) and keep `%%` out of
  named msgids. Found in the L6 walk; it had been on the course drawer, the outside course page and Tests since L5.
- LN60: **`odoo-bin … --stop-after-init --no-http` still refuses to start when its `http_port` is taken** ("Address already in use")
  — locally a test run beside a walk server needs its own config port; a run killed this way logs a KeyboardInterrupt, not a test
  result.
- LN61: **A Numbers payload is big enough to read once**: the spreadsheet and the pack pass the board they already built through a
  context cache (`pb_numbers_cache`), and the screen gets the first 50 people on Hours (`pb_numbers_full` for everybody).
- LN62: **In-browser failure drill for a lens:** Odoo 19's ORM calls go through `XMLHttpRequest`, not `fetch` — patch
  `XMLHttpRequest.prototype.send` (dispatch `error`/`load` with status 502) to see a lens's "could not load" state without stopping a
  server.

## 6. Score against the design bar

1. **Hero moments:** the Overview sentence built from every block, worst first, and the calm "All clear" with a green tick; Numbers'
   Hours (kinds / departments / courses / people that all add up) and Cost against the allowance; Settings — the sentence under every
   switch that changes as you type and save.
2. **Zero dead ends:** every new block has an empty sentence; "could not load" is a retry, never a refusal; a pack that is off says
   where to switch it on; "Send me a test" says why it is unavailable; a bad address is named before Save.
3. **Plain language EN + VI:** walked in both; whole sentences only (fragments around values removed from the new templates).
4. **Motion:** rise-in on the settings screen; off under reduced motion.
5. **Weakest:** phone width not walked; the pack's real send and the PDF are only produced live.

## 7. Owner items (plain English)

1. **The report pack stays off** on every database (as today). Turn it on in Settings › HR › Learning › Report pack, put in who should
   get it, press "Preview the email" and "Send me a test" first. On payobook a test address (training.pack@example.com) is already
   typed in from an earlier phase.
2. **Only the head of training can change the Learning settings.** Training managers can see them. Say if training managers should
   be able to change them too.
3. **"Required training" moved:** it is now the "Country packs" card inside the new "Learning" settings card group, next to Report
   pack, Reminders, Feedback and Day one.
4. **Sessions can have a cost** (trainer, room, materials). It adds up in Numbers › Cost. Old sessions have none. On payobook the two
   demo sessions now carry 3,500,000 ₫ and 4,500,000 ₫.
5. **Allowance used % looks small on payobook** because the allowance is counted for every person in the company (headcount × the
   company figure).
6. **Practical sign-off is still not built** (your earlier decision), so the Overview counts "sessions to close" where the plan said
   "sign-offs waiting".
7. **A small display fault from L5 is fixed:** some percentages showed as "80%%" on the course drawer, outside courses and Tests.

## 8. Deploy plan (at the gate) — normal tier

**Why normal:** three modules, no new module, no migration, no new table, nothing existing rewritten; one new column with no default
needed (`pb_training_session.cost`, plus a stored related currency column computed on upgrade). **I still recommend backups**
(new columns; cheap). `-u pb_home_hub` and `-u pb_learn` reload the modules that depend on them (the hubs), so expect a longer `-u`
log than L5 and **jobs re-activated by the reload** (LN18) — snapshot and restore the active job ids on every database.

**Live facts (read-only, 2026-10-22 ~11:00 UTC):** pb_training 19.0.1.9.0, pb_training_growth 19.0.1.0.0, pb_home_hub 19.0.1.4.0,
pb_learn 19.0.20.6.0, pb_settings 19.0.1.10.0, pb_budget 19.0.2.3.4 installed on p0clone, payobook, payobook_template, rize; active
jobs p0clone 26, payobook 37, payobook_template 0, rize 69 (72/73 active on p0clone and rize, off on payobook_template); the report pack
is OFF on all four (`pb_training.report_pack = 0`; payobook carries a typed test address `training.pack@example.com`, last period
`2026-08`); HTTP server pid up, health 200; last lines of `/opt/deploy-notes.md`: ChatGPT's payroll releases DONE 09:40 UTC, no open
START. The pack job record (`cron_training_pack`) is **not changed** by L6: it stays active where it is active (p0clone, payobook,
rize) and off on payobook_template; the feature switch stays off, so it only logs what it would send.

1. Read `/opt/deploy-notes.md` right before START (LN58) — no open START; HTTP pid up. Lock with a detached unit (LN25):
   `sudo systemd-run --collect --unit=l6-lock /usr/bin/flock /tmp/payobook-studio-deploy.lock /bin/sleep 10800`. START line
   `… | Claude (LEARNING L6) | START | pb_training,pb_home_hub,pb_learn | p0clone,payobook,payobook_template,rize | ~8 min, service stopped during -u | Numbers/Overview finished, Settings › Learning, TEAM chips, Help eleven tabs; git <head>; backups first; p0clone first`.
   Announce to peer sessions.
2. Versions before = 19.0.1.9.0 / 19.0.1.4.0 / 19.0.20.6.0 ×4 (nobody shipped L6 — LN15).
3. Backups (LN25): `sudo sh -c "sudo -u postgres pg_dump -Fc <db> > /odoo/backups/learning-l6-20261022/<db>.dump"` ×4, each `pg_restore -l`.
4. Stage: `sudo rm -rf /tmp/deployL6 && mkdir -p /tmp/deployL6`; `git archive <L6 head> pb_training pb_home_hub pb_learn` (check
   `git log <L6 head>..HEAD -- pb_training pb_home_hub pb_learn` is empty, LN44) → upload; per module
   `sudo rsync -a --delete /tmp/deployL6/<m>/ /odoo/odoo-server/addons/<m>/` (never the addons root); tree hashes = local (skip
   `__pycache__`, `*.pyc`, `.DS_Store`); PO gate on the box (expect pb_training 2,290 / 0, pb_home_hub 88 / 0, pb_learn unchanged);
   one addons path.
5. Snapshot active job ids per DB (expect 26 / 37 / 0 / 69).
6. Stop the service (wait on the PID, LN35). Detached unit + sentinel, one DB at a time, **p0clone first**:
   `odoo-bin -c /etc/odoo-server.conf -d <db> -u pb_training,pb_home_hub,pb_learn --stop-after-init`; grep EXIT, Traceback, ERROR,
   CRITICAL. Then payobook, payobook_template, rize. Stop at the first failure and restore that DB.
7. Asset ritual per DB (signal, delete `/web/assets/%`, bump `web.assets.version`); start; registry loaded; warm payobook / rize /
   p0clone; **jobs back to the exact snapshot sets** (payobook_template 72/73 off again; switch off anything else the reload
   re-activated, LN18).
8. Verify per DB: pb_training 19.0.1.10.0, pb_home_hub 19.0.1.4.1, pb_learn 19.0.20.6.1 **installed**; column
   `pb_training_session.cost` (0 / empty everywhere except payobook after the seed); six records `pb_training.action_pb_training_settings*`;
   `pb_training.report_pack` still 0 ×4; stored Help names unchanged (`pb_learn.item_learn_journey` = Help / Trợ giúp, LN7);
   0 ERROR lines since the start; `/web/health` 200.
9. Demo data, **payobook only**, service stopped:
   `sudo -u odoo /odoo/odoo-server/odoo-bin shell -c /etc/odoo-server.conf -d payobook --no-http < docs/handovers/learning/l6_demo_seed.py`
   (puts 3,500,000 / 4,500,000 on the two DEMO Site safety walk sessions where no cost is set; changes no setting; prints the Numbers
   / Overview / settings sentences as demo.hr; cancels anything queued — expect 0). Restart, warm.
10. DONE line containing **"LEARNING L6 DONE"**, release the lock (`systemctl stop l6-lock`).

### Live walk — what needs which login (server-side facade calls, ledger LN43)

The admin tab (head of training, company 5) covers: **Overview** (headline worst first, amber chips in order, the grey "Nothing waiting
on" line, Sessions "seats free"); **Numbers** (site / kind filters, the three new tiles, Hours, Cost with the allowance line and course
requests, Required training by site / department / country / safety group, Did it work?, Country reports with "off", Download the
spreadsheet → sheets Hours, Cost, Compliance, Effect, Assignments); **Settings › HR › Learning** (five cards, each tab; read and Undo —
**do not Save and do not press Send me a test on live** unless you want a mail to the admin's own address); Required › the settings
link lands on Country packs; a session page shows its cost; Help › the Learning page lists eleven tabs; Vietnamese labels.

`odoo-bin shell -d payobook`, `env(user=<uid>, context={'allowed_company_ids':[5],'lang':'vi_VN'})`, strip `tz` (LN50/51), roll back:

| Walk item | Login (uid) | Call | Expect |
|---|---|---|---|
| Settings read-only for a training manager | demo.hr@example.com (6678) | `env['pb.training'].settings_get()` | `allowed True`, `can_write False`, words in Vietnamese; `settings_set({'reminders': False})` → AccessError |
| Settings write for the head of training | admin (2) | `settings_set({'manager_days': 3})` then `settings_get()['words']['reminders']` | "… sau 3 ngày trễ …" (roll back) |
| Pack preview | 6678 | `env['pb.training.pack'].preview()` | subject "Training — September 2026", html with "Open Learning", `to` = ['training.pack@example.com'] |
| Test send goes to the presser only | 6678 (has an email) | `env['pb.training.pack'].send_test()` then the newest `mail.mail` | exactly one new mail, `email_to` = demo.hr's address, attachment present; `report_pack_last` unchanged — **roll back** |
| Numbers blocks | 6678 | `env['pb.training.analytics'].get_numbers('2026-07-24','2026-10-22',{})` | `hours.headline`, `cost.headline` (sessions 4,500,000 ₫ if the closed one is in range), `compliance.by_country`, `effect.ratings_count` 6 |
| Overview composer | 6678 | `env['pb.training'].overview()` | `headline` starts with the situation sentence, ≤ 3 concerns; `waiting` keys in order late → paths → required → certs → …; `calm` False |
| Home › TEAM chips | lam.ngo@example.com (2326) | `env['pb.my.training'].team()` → `expiring_certs`, `waiting_on_me`; `env['pb.home.team'].with_company(5).get_team()['training']` | `waiting` = 1 while request 1 waits on lam (if L5's request 1 was not decided since); `expiring` = his people's certificates within 30 days; no amount keys |
| Learning record sessions | demo.hr (6678) as admin | `env['report.pb_training.report_learning_record']._record(env['hr.employee'].browse(21182))` | `sessions` has the closed DEMO Site safety walk ("Đã có mặt"), summary "… · đã dự 1 buổi học" |
| Record PDF (one document) | admin | `/my/training/record.pdf` as demo.hr is portal-side; or `_render_qweb_pdf('pb_training.report_learning_record', [21182])` | `%PDF-`, one record id |

## 9. Final local state

- Commits on 19.1 (not pushed): `c52835660` (wip — everything, installs), `c71f23071` (fix — walk fixes: what waits worst first, the
  "%%" percent display, L5 follow-up test isolation, screenshots), `22f74c1e8` (test — claims classes isolated), and the docs commit
  with this report. **Deploy tree = `22f74c1e8`** for pb_training, pb_home_hub, pb_learn.
- **Final suites** (fresh copy of `am_l5_walk` + filestore, `-u pb_training,pb_home_hub,pb_learn --test-tags
  /pb_training,/pb_training_growth,/pb_learning_hub,/pb_home_hub`, run on `c71f23071`): 429 tests, 2 failed (`TestTheAssignmentsTab`
  ×2, pre-existing) and 10 setUpClass errors in `test_claims` (seeded allowance clash) → fixed in `22f74c1e8`, the ten classes rerun:
  **61 tests, 0 failed, 0 errors**. pb_home_hub alone (with the sibling modules visible to its source scans): **45 tests, 0 failed**.
  L6 classes: **28 / 28**. The `ir_attachment` foreign-key line in the log is pre-existing (L2–L5 logs).
- Tree under test = repo tree (`diff -rq` of the overlay against the repo: identical for all four modules).
- Walk server on **8074** (`am_l6_walk`) left running for the coordinator; test DBs `am_l6_t1`, `am_l6_t2` kept. The L5 walk server on
  8073 was stopped (L5 is complete) to copy its database.
