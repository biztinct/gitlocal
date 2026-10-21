# LEARNING L3 — Learning paths — report

Implementer: Opus, 2026-10-22. Spec: `L3_PATHS.md`. Ledger: `LEARNING_LEDGER.md` (candidate rows LN36+ in §5).
Status: **AT DEPLOY GATE** — built, committed (commits (a)–(e) below), tested locally (suites + Chrome walk). Not deployed. Not pushed.

## 1. What shipped (committed on 19.1, not pushed)

| Module | Live now | After L3 |
|---|---|---|
| pb_training | 19.0.1.6.2 | **19.0.1.7.0** — no migration (three new tables, two new columns on the assignment, one on the requirement; nothing existing is rewritten) |
| pb_training_growth (new) | — | **19.0.1.0.0** — bridge, `auto_install`, depends `pb_pip` + `pb_training` (both installed on all four DBs, checked read-only) |
| pb_pip, every other module | — | **unchanged** (the bridge extends pb_pip by inheritance only; no module depends on pb_training, so `-u pb_training` reloads only it and the new bridge) |

Commits: see §10 (hashes filled at commit time).

### What a user sees
- **Learning › PATHS** (new rail item between Courses and Assigned, icon "route", VI **Lộ trình**; the rail now has ten items — the target).
  - **Board:** one sentence ("2 paths · 10 people on a path · 5 late · 1 finished") and a card per path: name, purpose chip
    ("For a role / For a career move / For a skill"), people · finished, total hours, "Given on day one to …", a warning chip
    when a course on it is not published, the one-sentence blurb, and the **station line** (the quiet board's QuietSteps): one
    station per step plus "Finished", the count of people at each step now, "Later steps wait for this one" on gate steps, and a
    rose "N late" flag. Pressing a station opens the path page on the people at that step. Archived paths sit in one line under
    the cards with a "bring it back" chip. Empty state: "No paths yet. A path puts several courses in order …" with New path.
  - **Path page:** the big station line, chips Not started · Under way · Late · Finished (counted), name search, and a row per
    person: state chip, "At step 2 of 3: DEMO Pesticide handling", a dot rail (done tick, now ring, open, waiting dashed) with the
    percent, **Due = the date of the step they are on** plus "Whole path: 60 days left", why they were put on it, **Open their
    courses** (Assigned lens, searched on their name; the Assigned rows now say "Step 1 of 3 · DEMO New agronomist") and
    **Remove from path**. Buttons: Enrol people, Edit path, Archive / Bring back.
  - **New path / Edit path drawer:** name, purpose, days for the whole path, one sentence, the courses in order (type to add,
    drag to move, up / down buttons for the keyboard, a "Later steps wait for this one" tick and days per step, a "Not published"
    chip), "Give it to new joiners on their first day" with departments / jobs, "Their trial period waits for every course on it".
    It cannot be saved without a name and at least one course, and says which is missing.
  - **Enrol people drawer:** People (accent-blind search, ticked list, chips) · A department (with everything under it) · A job ·
    Everybody; why; whole path due by (empty = the path's days). The answer is one sentence: who was put on, who was already on
    it, who has no login.
- **My learning:** "My path" right under the hero — per path: name, purpose, Late / Finished chips, "Đang ở bước 1/2: …", the dot
  rail with "after <step it waits for>" under waiting steps, and **Continue** (opens the current step's next lesson). The **Next
  up hero now prefers the path's current step** and names the path.
- **Portal `/my/training`:** the same block (after the three numbers) for plain employees, with Continue.
- **Overview:** a sixth queue chip **Late on a path** (opens Paths filtered to the paths where somebody is late), "N people are
  late on a path." in the headline when N > 0, and a Learning paths block (paths · people on a path · finished this quarter · late).
- **Numbers:** **By path** table (with a "Not on a path" row so it adds up), a "learning path" filter, and a "By path" sheet in
  the spreadsheet.
- **Required › Rules:** a rule can need **"A learning path"** (pick the path). The matrix cell says "Not on the path" / "On the
  path, 50% done" / "Valid until …"; Assign now puts the person on the path (reason Required).
- **Talent › Growth (growth plans):** inside an objective — a quiet chip "DEMO Operator to line leader · 40%" (grey before, indigo
  on it, rose late, green finished), **Enrol** while the person is not on the path, and a "Learning path" picker.
- **Day one:** the joining-checklist step also puts a joiner on every day-one path for their department (and everything under
  it) or job, under the same day-one switch (off on payobook).
- **Morning job:** a new leg brings every open path enrolment up to date (opens the next step for anybody whose gate finished),
  after the required-training leg and before the chasing.

## 2. Tests

Local runtime `/Users/adity/odoo19` (venv), overlay `scratchpad/l3stage/{pb_training,pb_training_growth}` in front of the L0 staging
tree. Test DBs are copies of `am_l2_t` (L2's walked DB, at pb_training 19.0.1.6.2) **plus its filestore** (LN30), run exactly as the
live upgrade: `-i pb_training_growth -u pb_training`.

| # | Result |
|---|---|
| T1 | **Pass** (4): three tables and the assignment links; name unique per company (another company may reuse it); no steps → "Add at least one course."; a course twice → refused; reorder keeps the same step rows; a trainer cannot write a path; plain user → `allowed: false`. |
| T2 | **Pass** (5): gate holds step 2 back; no-gate steps open at once; step dates capped by the whole path's date; no-login skipped and named; already on it → `already`; a second open enrolment refused; trainer may enrol (assigned_by = trainer), plain user → AccessError. |
| T3 | **Pass** (2): an open assignment on step 1's course is ADOPTED (linked, reason kept, one open row); a course finished before counts at once and opens the next step. **Found and fixed by T3:** the first build counted an existing open assignment for a step but never linked it. |
| T4 | **Pass** (3): finishing the gate (the learner's own "mark as done") opens the next steps the same moment, percent 33, current step 2, "At step 2 of 3"; late (path date) → Late; all done → Finished, 100%, completed today, "Finished all 3 steps"; an assignment's own refresh going overdue makes the enrolment Late. |
| T5 | **Pass**: removing a person takes off only the course nobody started; the started one and the finished one stay (links cleared on the started one); enrolment "Taken off the path"; on again later is allowed. |
| T6 | **Pass**: day-one switch off → the note names the path, nobody enrolled; on → enrolled once (reason Day one), a second run enrols nobody; by job; nobody outside the audience. |
| T7 | **Pass** (2): one broken row does not stop the leg (the other enrolment still goes Late); the leg runs after "put required courses on people" and before the chasing. |
| T8 | **Pass**: 4 people on a 3-step path → stations [2, 1, 0, 1] add up to 4; "1 late" on station 1; "Finished" last; "2 people"; kpis and headline. |
| T9 | **Pass** (2): rows, counts and the dot rail ([done, now, next]); state, station and accent-blind name filters; enrol by department (child_of), job, everybody (the one person not yet on it); everybody again → nothing, warning; remove names the person. |
| T10 | **Pass** (2): `home()['paths']` shape; [now, waits, waits] with "after <gate course>"; Continue = step 1's course; "At step 1 of 3: …"; source rail that the hero prefers the path step; Vietnamese `where_words` differ from English. |
| T11 | **Pass** (2): Overview block (paths, people, late), chip `paths`/`overdue`, headline "1 person is late on a path."; Numbers By path adds up to the total with "Not on a path", path filter, spreadsheet has "By path". |
| §3.6 | **Pass**: a path rule — Not on the path → Assign now (reason Required) → On the path → a second Assign now refused → Valid; column "Path: …", can assign. |
| T12 | **Pass** (5, bridge): objective points at a path (chip "not on it yet"), `get_case` carries `path` and `path_options`, clearing it empties `path`; Enrol enrols once (reason Leadership programme, `objective_id` set), second press says already; growth-plan gate holds for a stranger; no path → refused; manifest auto_install with exactly the two sides, neither side names the bridge; no vendor name. **pb_pip's own suite green.** |
| T13 | **Pass** (3): no "Odoo", no emoji in the new files; rail label `Paths` / `Lộ trình` (every word ≤ 8 letters); the new Vietnamese present. |
| Suites | `/pb_training,/pb_training_growth,/pb_pip,/pb_learning_hub` on a fresh copy with `-i pb_training_growth -u pb_training`: see §9 (final run). The only failures are `TestTheAssignmentsTab` ×2 — they fail before L3 too (they count the copied DB's own assignments; listed in the L0, L1 and L2 reports). The `ir_attachment` foreign-key line in the log is pre-existing (in every L2 log). |
| PO gate | pb_training 1,126 rows, 0 code rows without a value; pb_training_growth 27 rows, 0. |
| T14 | Local Chrome walk, `localhost:8071` / `am_l3_t2` (seeded with `l3_demo_seed.py` + a local growth plan). Detail below. |

T14 detail (local):
- **Head of training (admin), EN.** Rail OVERVIEW · MY LEARNING · COURSES · **PATHS** · ASSIGNED · REQUIRED · TESTS · CERTIFICATES ·
  CLAIMS · NUMBERS. Overview headline ends "… 5 people are late on a path."; chip "5 Late on a path" → Paths "Showing the paths
  where somebody is late." with only New agronomist; Learning paths block "2 paths · 10 people on a path · 1 finished this quarter ·
  5 late on a path". Screenshot `outputs/learning-l3-20261022/local-paths-board.jpg`.
- **Board → station 01 → path page** on that step (station ringed), chips Not started 1 · Under way 0 · Late 5 · Finished 0, dot
  rails, Due + "Whole path: …". `local-path-page.jpg`.
- **Enrol people** (search "tran" → DEMO Trần Minh Quân) → "1 person is now on DEMO New agronomist." (7 people); **Remove from path**
  → "… is off DEMO New agronomist. 1 course they had not started is taken off their list." (6). `local-enrol-drawer.jpg`.
- **Edit path:** moved step 3 up, ticked a gate, saved → station line in the new order; put it back the same way.
- **New path:** "Start with a name people will recognise." → "Add at least one course." (Save disabled) → typed "demo" (seven
  courses with hours), added two, **dragged** the second above the first, ticked a gate and day one for Administration → "DEMO Walk
  path is ready. Put people on it with Enrol people."; card shows "Given on day one to Administration"; empty path page "Nobody is
  on this path yet"; **Archive** → "… is archived. Nobody new can be put on it; the people already on it carry on." and the
  Archived chip.
- **Open their courses** → Assigned lens searched on "DEMO Đỗ Văn Nam", row "DEMO Handling customer data — Step 1 of 3 · DEMO New
  agronomist".
- **Numbers:** By path (Not on a path 16 · New agronomist 6 · Operator to line leader 10), "Every learning path" filter works.
- **Required:** a rule needing the career path → cells "Not on the path" / "On the path, 50% done"; Assign now on a cell → "Administrator
  is on the path DEMO Operator to line leader, due 20 Dec 2026."; the rule drawer offers "A learning path", hides Course, lists paths.
- **Growth plan (Talent › Growth):** objective shows "DEMO Operator to line leader · not on it yet", Enrol and the picker; Enrol →
  chip "· 0%" in indigo, Enrol gone. `local-growth-plan-chip.jpg`.
- **Manager (VI), My learning:** hero "VIỆC TIẾP THEO — DEMO Leading a line — read this first" with the path name; "Lộ trình của tôi ·
  DEMO Operator to line leader · Cho lộ trình thăng tiến · Đang ở bước 1/2: DEMO Leading a line" with the dot rail; **Tiếp tục** →
  `/my/training/831/2654` (the lesson). `local-my-path-vi.jpg`.
- **Plain employee (nam.p3c, VI), portal `/my/training`:** both paths with "Trễ hạn" on the late one, rails and Tiếp tục.
  `local-portal-my-path-vi.jpg`.
- **Found and fixed in the walk:** (1) pressing a station on a board card crashed ("Cannot read properties of undefined") — an arrow
  in the template naming the loop variable runs later inside QuietSteps' own `t-call`, where the variable is gone; the handler is now
  built in JS at render time (`stationPicker`) — ledger candidate LN36. (2) Rows read "Late" over the whole path's "60 days left" in
  red, because the course they were on was overdue; Due now shows the current step's date with "Whole path: …" under it (EN + VI).
- Console: after the fix, no errors on any page walked (only the two pre-fix errors from the old bundle). Not walked: phone width
  (the agent's window cannot be resized; CSS written: hero / cards stack, table scrolls in its own box, drawers one column).

## 3. Deviations from the handover, and why

1. **Verb names** `enrol_path` / `unenrol_path` (not `enrol` / `unenrol`): `pb.training.enrol` / `unenrol` already exist and put people
   on a COURSE. New path is `save_path` without an id (one verb for new and edit).
2. **`stations` is a method** (`_stations()`), not a JSON field: it is only ever read by the facade, which also needs the late counts.
3. **A "Finished" station is added** after the steps, so every enrolled person is at exactly one station (the QuietSteps contract) —
   otherwise finished people would be at none and the counts would not add up to the people on the path.
4. **`requirement_id` on the path is not added**; the link is `pb.training.requirement.path_id` (target "A learning path"), which is
   what the matrix and Assign now need.
5. **Enrolment states** add **`cancelled`** ("Taken off the path") for unenrol; state is a stored column written by `_refresh()` (the
   assignment's own rule), not a stored compute.
6. **A course shared by two paths counts on both**: a step whose course the person is already doing (open) is that step's assignment,
   and is linked to the first path that adopted it. So a person on two paths that share a course sees the shared step "open" on the
   second path even if a gate comes before it there — they are genuinely on that course.
7. **Adopted assignments keep their state and due date**: on the local copy five people adopted overdue course assignments, so the
   path shows them Late at once (true; the same will happen live where a demo person already has an overdue course 27).
8. **Day-one paths with no department or job picked go to everybody in the company** (the rule precedent's empty-audience reading);
   the drawer says so.
9. **Demo spread (§6) differs:** course 27 ends in a test that only 2 demo people on payobook have passed, and the seed never fakes a
   pass (it would file a certificate nobody earned). New agronomist therefore shows most people at step 1 and the passers past the
   gate; the career path (no tests) carries the 2 / 2 / 1 spread. The seed prints the real counts.
10. **The growth-plan picker sits on each objective in the plan drawer** (with the chip and Enrol), not in the "add objective"
    dialog — the dialog's save calls `add_objective` with fixed arguments inside pb_pip, which the bridge must not edit.
11. **Path page Due** = the current step's date, with the whole path's date under it (walk finding §2).

## 4. Vietnamese

`pb_training/i18n/vi_VN.po`: **189 new entries** (rail, board, page, drawers, server sentences, selection labels, field labels and
help, Overview / Numbers / My learning words, the Required target), 10 existing entries gained a marker or occurrence; the diff is
pure additions (text-level merge, LN29). Words said through `tr()` (`At step %s of %s: %s`, `Finished all %s steps`, `On the path,
%s%% done`, `Not on the path`, the purposes and states) are `odoo-python` entries. `pb_training_growth/i18n/vi_VN.po`: new file, 27
entries (all of the bridge's words; the stock "Display Name" / "ID" / the pb_pip model description left English like everywhere else).

## 5. Ledger rows to add after the deploy (candidates, from LN36)

- LN36: **An arrow in a template that names a loop variable, passed into a shared `t-call` (QuietSteps' `qStepPick`), runs later in the
  called template's context, where the loop variable is undefined** ("Cannot read properties of undefined (reading 'id')"). Build the
  handler in JS at render time (`t-value="stationPicker(pcard.id)"`). Arrows that only use `this` are fine.
- LN37: Learning paths ADOPT an open assignment on a step's course (link, keep reason / date / state) — so a path can be Late the day
  somebody is put on it, and a course shared by two paths counts on both. Read a path's state through `_step_rows()`, never by
  `assignment_ids` alone.
- LN38: `pb_training`'s Overview queue now has a sixth chip only when the company has a path (`has_paths`); tests that assert the
  queue length must run in a company of their own (L0's T7 does).

## 6. Score against the design bar

1. **Hero moments:** the station line on every path card (counts at each step, rose "late" flag, press a station to see those people);
   the learner's "My path" dot rail with one Continue, and the Next up hero that now points at the path's step.
2. **Zero dead ends:** every empty state says what to do (no paths → New path / "a training manager can make the first one"; nobody on
   a path → Enrol people; nothing matches → Show everybody); the path drawer says what is missing; every refusal is a sentence
   (archived path, already on it, no login, 200-person cap, another company's path).
3. **Plain language EN + VI:** walked in both; rail label fits.
4. **Motion:** rise-in, drawer slide; off under reduced motion.
5. **Weakest:** phone width not walked; New agronomist's demo spread is thin because only two demo people have passed course 27's test.

## 7. Owner items (plain English)

1. **A course on two paths counts on both.** If someone is already doing "Pesticide handling" because of one path, a second path that
   also has it shows that step as open for them, even if it would normally wait for an earlier step. Say if you want the second path
   to hold it back instead.
2. **People already late on a course are late on the path straight away.** Putting someone on a path whose first course they were
   already late on keeps that course and its date. Say if you would rather the path give them a fresh date.
3. **A day-one path with no department or job picked goes to every new joiner in the company** (only while day-one training is on —
   it is off on payobook).
4. **Demo:** "DEMO New agronomist" starts with the real "Agronomist basics" course, which ends in a test only two demo people have
   passed, so most demo people sit at step 1. The career path shows the fuller picture.
5. **Not Learning's, but found:** the L4 handover (`L4_SESSIONS_SIGNOFF.md`, fact F11) has two demo passwords written in it, in a commit
   that is on this computer only (not pushed). It must be cleaned before anything is pushed.

## 8. Deploy plan (as at the gate) — risky tier (new module install)

**Why risky:** a new module (`pb_training_growth`) is installed on all four databases, and pb_training gains three tables. No data is
rewritten, no migration.

**Live facts (read-only, 2026-10-22 ~06:50 AEDT):** pb_training 19.0.1.6.2 and pb_pip 19.0.1.3.0 installed on p0clone, payobook,
payobook_template, rize; pb_training_growth not known yet; active jobs p0clone 26, payobook 37, payobook_template 0, rize 69; last line
of `/opt/deploy-notes.md` is L2's fix DONE (18:21 UTC 10-21) — no open START. Payobook demo facts for the seed: company 5, course 27
"DEMO Agronomist basics" (4 lessons + a test; 2 people have passed it), jobs DEMO Site / Field / Junior / Senior Agronomist, 6 growth
plans in company 5.

1. `cat /opt/deploy-notes.md` — no open START from anybody. Lock with a detached unit (LN25):
   `sudo systemd-run --collect --unit=l3-lock /usr/bin/flock /tmp/payobook-studio-deploy.lock /bin/sleep 10800`. START line
   `… | Claude (LEARNING L3) | START | pb_training,pb_training_growth(new) | p0clone,payobook,payobook_template,rize | ~10 min, service stopped during -i/-u | …`.
   Announce to peer sessions.
2. Versions before = pb_training 19.0.1.6.2 ×4 and no pb_training_growth (nobody shipped L3 — LN15).
3. Backups (LN25): `sudo sh -c "sudo -u postgres pg_dump -Fc <db> > /odoo/backups/learning-l3-20261022/<db>.dump"` ×4, each checked with
   `pg_restore -l`.
4. Stage: `sudo rm -rf /tmp/deployL3 && mkdir -p /tmp/deployL3`; `git archive HEAD pb_training pb_training_growth` → upload; per module
   `sudo rsync -a --delete /tmp/deployL3/<m>/ /odoo/odoo-server/addons/<m>/` (never the addons root; the new module's directory is
   created by the scoped rsync); tree hash = local for both (skip `__pycache__`, `*.pyc`, `.DS_Store`); PO gate on the box (expect
   1,126 / 0 and 27 / 0).
5. Snapshot active job ids per DB (expect 26 / 37 / 0 / 69).
6. Stop the service (wait on the PID, LN35). Detached unit + sentinel, one DB at a time, **p0clone first**:
   `odoo-bin -c /etc/odoo-server.conf -d <db> -i pb_training_growth -u pb_training --stop-after-init`; grep EXIT and Traceback;
   then payobook, payobook_template, rize. Stop at the first failure and restore that DB from its dump.
7. Asset ritual per DB (signal, delete `/web/assets/%` attachments, bump `web.assets.version`); start; registry loaded; warm payobook /
   rize / p0clone with one curl each; jobs back to the snapshot (on payobook_template switch 72/73 back off if `-u` re-activated them,
   LN18; the new module ships no job).
8. Verify per DB: pb_training 19.0.1.7.0, pb_training_growth 19.0.1.0.0 **installed**; tables `pb_training_path`,
   `pb_training_path_step`, `pb_training_path_enrolment` exist (0 rows except payobook after the seed); columns
   `pb_training_assignment.path_enrolment_id/path_step_id`, `pb_training_requirement.path_id`, `pb_pip_objective.path_id`,
   `pb_training_path_enrolment.objective_id`; 0 ERROR lines since start; `/web/health` 200.
9. Demo data, **payobook only**, service stopped:
   `sudo -u odoo /odoo/odoo-server/odoo-bin shell -c /etc/odoo-server.conf -d payobook --no-http < docs/handovers/learning/l3_demo_seed.py`
   (three DEMO courses; the two DEMO paths; the demo learner and up to five more at step 1 of New agronomist, the course-27 passers past
   the gate; the HR lead and four more on the career path at 2 / 2 / 1; one DEMO growth plan's first objective pointed at the career
   path; prints the station counts; the path leg run once and rolled back). Restart, warm.
10. DONE line, release the lock (`systemctl stop l3-lock`).

**Live walk (Fable, ledger LN16), payobook.com:** as the HR lead — Learning rail with PATHS; Overview "Late on a path" chip and the
Learning paths block; Paths board station lines (press a station → path page on that step), filters, dot rails, Due + "Whole path";
Enrol people (one DEMO person) and Remove from path; Edit path (reorder, gate) and New path (empty guards); Open their courses → Assigned;
Numbers By path + spreadsheet sheet; Required rule with "A learning path" and Assign now from a cell; Talent › Growth → the DEMO plan's
objective chip, Enrol → "· 0%". As the learner (`demo.learner@example.com`) — My learning "My path" and Continue, and `/my/training`'s
block. Vietnamese rail label "Lộ trình". Console clean.

## 9. Final local state (before the gate)

- **Final suites on the committed code** (fresh copy of `am_l2_t` + filestore, `-i pb_training_growth -u pb_training --test-tags
  /pb_training,/pb_training_growth,/pb_pip,/pb_learning_hub`): **333 tests, 2 failed, 0 errors** — only `TestTheAssignmentsTab` ×2
  (pre-existing, §2). The first full run also caught two of mine — the portal stylesheet rule that every colour variable carries a
  literal fallback (R39) flagged the portal dot rail's `var(--pbtr-cols)`; fixed with `var(--pbtr-cols, 4)`.
- **Tree under test = repo tree** (`diff -rq` of both modules against the overlay: identical), so `git archive HEAD` ships what was tested.
- PO gate: pb_training 1,126 rows / 0 empty code rows; pb_training_growth 27 / 0.
- Local walk server stopped; walk DB `am_l3_t2` kept.

## 10. Commits (on 19.1, on top of L2's closing `5747c3b6d`; not pushed)

- `c731e43e2` (a) feat(training): learning paths — models, enrolment engine, day-one, daily leg (19.0.1.7.0)
- `b1975292b` (b) feat(training): PATHS lens, path page, drawers
- `e87afc3bc` (c) feat(training): My path on My learning and the portal; Overview and Numbers (+ VI, tests T1–T11, §3.6, T13)
- `b0f40c720` (d) feat(training-growth): growth plan objective → learning path bridge (new module 19.0.1.0.0, test T12)
- (e) docs: this report, the demo seed `l3_demo_seed.py`, walk screenshots `outputs/learning-l3-20261022/`, ledger phase log

Shared files (manifest, `models/__init__.py`) went into (a) with their final content, so (a) and (b) are feature-scoped but not each
separately installable (the manifest lists the lens files); (c) is, and (d) on top of it.
