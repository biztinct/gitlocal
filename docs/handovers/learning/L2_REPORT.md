# LEARNING L2 — Required training and country packs — report

Implementer: Opus, 2026-10-21/22. Spec: `L2_REQUIRED_TRAINING.md`. Ledger: `LEARNING_LEDGER.md` (candidate rows LN26+ in §5).
Status: **COMPLETE** — LIVE ×4 DBs: 19.0.1.6.0 at 2026-10-22 04:22 AEDT (17:22 UTC), fixes 19.0.1.6.1 / 19.0.1.6.2 at 04:34 / 05:20 AEDT. Live walk by Fable passed after the two fixes (§9). Not pushed.

## 1. What shipped (committed on 19.1, not pushed)

| Module | Live now | After L2 |
|---|---|---|
| pb_training | 19.0.1.5.0 | **19.0.1.6.2** (19.0.1.6.0 + two live fixes; migration `19.0.1.6.0/post-requirements.py`). Also carries L1's unreleased 19.0.1.5.1 (portal `/my/training` page titles without "(ESS)", commit `f7182ccde`). |
| every other module | — | **unchanged**. The Settings card names its own group (`group: "hr"`), so pb_settings is not touched; no module depends on pb_training, so `-u pb_training` reloads only it. |

Commits (on top of L1's `100bf2990`):
- `5746c6516` wip — requirement model + set-based evaluation, four pack data files, migration, employee fields, hours,
  enforcement leg (leg 5), F3 child_of fix, F5 manager-only rule forms, Required facade, exports, settings reads/writes,
  Overview / Numbers / My learning facades, four country reports (server side; did not install on its own).
- `a0069d5d0` feat — Required lens screens, Settings screen + card, People chip, Overview / Numbers / My learning UI
  (makes the WIP install again).
- `43405737c` fix — requirement country falls back to the company's partner country.
- `710282f6d` i18n — Vietnamese for L2 (pure additions).
- `1247fdbc1` test — T1–T15.
- `ddd2e48b5` fix — local walk fixes + isolated L2 tests. `68536e8f4` docs — report at the gate + demo seed.
- `5e9948e54` fix (19.0.1.6.1) — auditor PDF as one document; one Required-for-you line per course (both found in the live walk).
- `8b7e5a1c8` fix (19.0.1.6.2) — the print-out takes up to 200 people at a time (found verifying the PDF live).
- closing commit — seed fixes, this report, ledger rows LN26–LN35.

The planned five commits (a)–(e) became the WIP commit plus feature commits on top, because the owner's usage limit paused the
build mid-way (coordinator's instruction: one WIP commit). Every commit after `a0069d5d0` installs.

### What a user sees
- **Learning › Required** (rail label unchanged, REQUIRED / BẮT BUỘC): four inner tabs.
  - **Matrix** (default): one sentence over the grid — "92% in date across 214 people · 12 expiring · 5 missing" — with the percent
    as a quiet ring, and four state chips (Missing / Expiring / Under way / Not due yet) that filter the rows. Filters: name,
    department (with everything under it), job, site, country, safety group, rule. Grid: sticky header and first columns, 200
    people a page with "Showing N of M — narrow it by department or site". A missing / expiring / not-due cell opens "Assign now";
    ticked rows get "Assign now" and (managers) "Set safety group". "Download the spreadsheet" (grid + Gaps sheet) and "Print for
    an auditor" (landscape A4, 40 people a page, filters and legend). Headcount rules (fire wardens, first-aiders) show a per-site
    "Sites short of trained people" line instead of a column.
  - **Rules**: every rule with its kind, what it needs, how often, who it is for, the legal note, pack tag, "To confirm" tag;
    managers: New rule (drawer), Edit, Assigns itself / Assign by hand, Switch off / on. Pack chips filter by pack.
  - **Day one** / **Comes round again**: the new rules of that kind, plus the old day-one rules / schedules read-only with a
    "Converted" tag.
- **Settings › HR › Required training**: the four country packs as switches with "Review the rules"; the renewal window, the
  morning cap and the day-one switch. The Singapore line carries the Skills Development Levy note.
- **Overview**: "N people are missing required training." in the headline, a fifth chip "Missing required training" (opens the
  matrix on Missing), and a Required training block (in date %, missing, expiring).
- **Numbers**: three tiles (in date %, missing, expiring), a Required training section (by rule / department / site) and
  "Country reports" buttons for the packs switched on.
- **My learning**: "Required for you" with the state of each rule and a Start button when a course is assigned.
- **People drawer**: "Safety group 3" and the site, when set. **Employee form** (Work page, Location group): Safety training group,
  Internal Committee member, More than six years in the sector. **Course form**: Hours.
- **Morning job**: leg 5 puts the course on whoever is missing it (rules with "Assign it by itself" only), reason "Required".

## 2. Tests

Local runtime `/Users/adity/odoo19` (venv), overlay `scratchpad/l2stage/pb_training` in front of L0/L1's staging tree. Test DB
`am_l2_t` = copy of `am_l1_final` **plus its filestore** (a template copy does not copy the filestore — ledger candidate LN30).

| # | Result |
|---|---|
| T1 | **Pass** (5): department reaches sub-departments; job; contractors in / out; site; safety group; country = work address, else company (a Vietnamese national at the Singapore office is under Singapore); a rule that needs an audience covers nobody until given one. |
| T2 | **Pass** (4): document evidence valid / expiring ("Expires in 10 days"); "SIO" does not match "Pension" (whole words); the rule's 12 months beats the test's 24 (and 24 makes it valid); open course → under way, finished → valid, out of audience → exempt, joined 3 days ago → not due; a course rule with no course linked is quiet ("No course linked yet"), counted nowhere, never assigned. |
| T3 | **Pass** (3): counts add up, missing first, state and accent-blind name filters; 201 people → truncated, 200 + 1 over two pages; **50 people × 5 rules evaluated in under 30 queries**. |
| T4 | **Pass** (2): a rule with two courses → two day-one requirements, a schedule → one recurring (validity = how often); second run makes none; day-one rule department match is child_of. |
| T5 | **Pass** (2): reason Required + requirement link, due today + days; no-login person skipped and counted; no second open one; cap 1 → 1 made, 1 capped; auto off → nothing; converted legacy rule → nothing. |
| T6 | **Pass**: the renewal leg skips a certificate whose course a rule owns; enforcement assigns once, due the day the old one runs out; running both again keeps one assignment. |
| T7 | **Pass**: joined 3 days ago → not due, nothing assigned; joined 400 days ago → due today + 14; "Assign now" on the not-due cell → due joining date + 14. |
| T8 | **Pass** (2): course hours beat the lessons' total; stored at the finish and not rewritten later; an hours rule says "6 of 8 hours" (under way), valid at 6. |
| T9 | **Pass** (2): trainer reads but cannot create (AccessError); manager can; employee cannot read; trainer cannot save a rule / open the old rule form / set a safety group, but can assign from a cell; plain user gets `allowed: false`; manager's save keeps only real safety groups. |
| T10 | **Pass** (3): pack on copies every template once (auto off, unverified ones archived), on again copies nothing, off archives all (none deleted), on again restores exactly what was on; every pack has templates; copies keep name and code; settings read says rules / to confirm / switched on. |
| T11 | **Pass** (2): groups 1–6 carry hours / months / refresher per §3.6.1 (g4 12 months, g3 licence); fire, first-aid and retrain rows are "to confirm" and off; "Renewals due in 30 days" lists the 20-day person, not the 100-day one, with hours, card number and trainer. |
| T12 | **Pass** (4): India register (contractor shown as Contractor), Indonesia licence register (forklift SIO yes, pension letter no), Singapore hours ("3", "Singapore national"), Indonesia fire-warden site shortfall line. |
| T13 | **Pass**: Overview percent / missing people / chip and Numbers percent / missing equal an independent recount. |
| T14 | **Pass** (2): spreadsheet for 0, 1 and 250 people (Gaps sheet names the rule); PDF for 0 and 250 (7 pages of 40); the PDF reads the matrix as the reader — another company's person and rule never appear; no `sudo()` in the render path. |
| T15 | **Pass** (3): no "Odoo", no emoji in the 12 new files; VI words present; "Required" reason says "Bắt buộc" to a Vietnamese reader. |
| Suites | `/pb_training,/pb_learning_hub,/pb_employee_vault` with the upgrade: **296 tests, 2 failed, 0 errors** — the 2 are `TestTheAssignmentsTab` ×2, which also fail before L2 (they count the copied DB's own assignments; listed in the L0 and L1 reports). Final `/pb_training` re-run after the walk fixes and test isolation: **297 tests, same 2 pre-existing failures only** (§9). PO gate (Odoo's PoFileReader): 890 rows, 0 code rows without a value. |
| T16 | Local Chrome walk, `localhost:8070` / `am_l2_t`. Detail below. |

T16 detail (local, seeded with `l2_walk_seed*.py` in the scratchpad: Vietnam pack on, safety groups, three DEMO rules, the L1 certificates):
- **Head of training (admin), EN.** Overview: "… 38 people are missing required training."; fifth chip "38 Missing required training"
  (amber) → Required › Matrix on Missing. Required training block: 2% in date · 85 missing · 1 expiring.
- **Matrix:** "2% in date across 38 people · 1 expiring · 85 missing · 5 under way"; ring; chips 85 / 1 / 5 / 1 — **all five cell
  states seen** (Missing, Not on file, Expires in 20 days, On the course due …, Valid until …, Due by … for the joiner). Assign now
  on a missing cell → missing 85→84, under way 5→6. Ticked two rows → Set safety group → "2 people are now in Group 2 — Safety
  officers." and the row tags changed. Bulk Assign now on two people with no login → nothing assigned (correct), but the message
  read "0 courses put on." in green — **fixed**: "No course was put on. … no login yet." as a warning.
- **Found and fixed in the walk:** filter dropdowns stacked full-width (a global `select {width:100%}`) → `width:auto` in the bar;
  Settings screen buttons unstyled (no `.pbim` ancestor outside the hub) → root gets `pbim`; India session rule with no course
  linked showed 38 red "Missing" → quiet "No course linked yet" (counted nowhere, never assigned; test added).
- **Spreadsheet:** `Required training 2026-10-21.xlsx`, 38 rows. **PDF: not produced locally** — this Mac has no PDF tool (same as
  L1); the live box has one → live-walk item.
- **Rules:** New rule drawer (name, course, department, safety group 4, 12 months) → saved; Edit opens it filled, renamed and
  saved; Assigns itself ↔ Assign by hand; Switch off shows "Switched off", Switch on clears it. Day one lists DEMO Induction and
  the "old day-one rules are switched off" note; Comes round again lists the yearly rule. (No legacy rows on this DB.)
- **Settings › HR › Required training** card present; screen shows four packs (Vietnam on: 11 rules · 5 to confirm · 6 switched
  on); India switched on → "India — harassment-awareness sessions is on for My Company. Review the rules …"; Review the rules →
  Rules tab filtered on India (4 rules). Renewal window saved 45 then back to 60.
- **Numbers:** three new tiles; Required training section by rule / department / site; Country reports buttons "Renewals due in 30
  days" and "Awareness session register"; both spreadsheets build (0 rows on this data — correct).
- **People drawer:** "Safety group 2" and "DEMO Site North" chips.
- **Manager (VI), My learning:** "Bắt buộc với bạn": DEMO Forklift licence "Chưa có trong hồ sơ"; the Vietnam group-4 rule under its
  Vietnamese name "Huấn luyện an toàn — nhóm 4 (người lao động khác)" "Đang học, hạn 26 thg 10 2026" with **Bắt đầu**; the yearly
  rule "Hiệu lực đến 21 thg 10 2027". Screenshot `outputs/learning-l2-20261022/local-manager-my-learning-required-vi.jpg`.
- **Matrix in Vietnamese** (facade with `lang=vi_VN`): "2% còn hiệu lực trên 38 người · 1 sắp hết hạn · 84 còn thiếu · 7 đang học";
  "Mỗi năm", "Lặp lại định kỳ", "Đang học, hạn 20 thg 11 2026", "Chưa có trong hồ sơ", "Không áp dụng".
- Console: no errors on any page walked. Not walked: phone width (the agent's window cannot be resized; CSS written: grid scrolls in
  its own box, hero / filters / rules stack, drawer one column), the PDF (no tool locally).

## 3. Deviations from the handover, and why

1. **Commit shape:** one WIP commit + feature commits instead of (a)–(e) (owner's usage-limit pause, coordinator's instruction).
2. **"Confirm with Rize" is written "Confirm before switching on: …"** — pack templates are on every tenant database, so another
   customer would read Rize's name. One word to change if the owner wants it.
3. **Employee fields sit in the Work page's Location group**, not after `employee_type`: the stock `employee_type` is on the
   Payroll page, which only HR managers see. Two more Booleans were needed by the packs (India Internal Committee member,
   Singapore more than six years in the sector).
4. **No pb_settings change:** the Settings card names `group: "hr"` itself (`GROUP_OF_CATEGORY` not edited, no pb_settings upgrade).
   The card opens its own client action (`pb_training_required_settings`).
5. **`note` is plain text**, not Html (it is a tooltip / a line under the rule).
6. **Name patterns match whole words** (accent-blind) and `|` separates alternatives ("Lisensi K3|SIO|Forklift").
7. **Rules with no course linked are quiet** ("No course linked yet", grey, counted nowhere, never assigned) — the handover asks
   for a quiet column note; without this the India session rule made the whole company red.
8. **Day-one due date** for somebody who joined long before the rule existed: today + days (not a date already in the past).
9. **Leg 5 runs beside the schedules leg**, not behind the reminders switch — it makes assignments, like a schedule does. People
   with no login are skipped and counted.
10. **`vn_osh_retrain`** ships "to confirm" and does not detect a job change or a long absence (no reliable signal); HR picks the
    people. **`id_p2k3_report`** is a "to confirm" certificate-style reminder row. **Headcount rules** group by work location, else
    department name (owner item: what is a "site").
11. **Hours on uploads:** HR's certificate drawer only (the portal upload form is untouched).
12. **Trainers can assign from a cell** (assigning is the trainer's job), but cannot create / edit / switch rules or set safety
    groups (§3.7 fix; the old "New day-one rule / New schedule" doors are manager-only too).
13. Vietnamese: 377 new entries incl. the 26 pack rule names and their legal notes (shown in the Rules tab and as column
    tooltips). Older Numbers-page words that were already untranslated before L2 are untouched.

## 4. Vietnamese

`pb_training/i18n/vi_VN.po`: 377 new entries, 62 existing entries gained the `odoo-python` / `odoo-javascript` marker or an
occurrence they now need; **no existing msgstr changed** and the file diff is pure additions (merged at text level: polib
re-wraps existing entries, and Odoo's PoFileReader needs `#. module:` as the first comment line). Message ids from Odoo's own
export of the module (`odoo-bin i18n export`); words said through `tr(env, …)` added as `odoo-python` entries.

## 5. Ledger rows to add after the deploy (candidates, from LN26)

- LN26: `res.company.country_id` is a non-stored related field — an employee domain on it raises "Cannot convert … to SQL"; use
  `company_id.partner_id.country_id`.
- LN27: A client action opened from Settings (outside any hub) has no `.pbim` ancestor, and `.pbim-btn` / `.pbim-panel` are
  scoped under `.pbim` — give the screen's root the `pbim` class or its buttons render as plain browser buttons.
- LN28: A global `select { width: 100% }` stacks every select in a flex filter bar on its own line; set `width: auto` on bar selects.
- LN29: Odoo 19 has no `--i18n-export`: `odoo-bin i18n export -c <conf> -d <db> -o <file>.pot <module>`. Never save a
  module `.po` through polib (it re-wraps existing entries); merge at text level, and keep `#. module:` the first comment line
  of an entry or PoFileReader crashes on load.
- LN30: `createdb -T` copies the database but not `data/filestore/<db>` — copy the filestore too, or attachments (company logo)
  are missing and reports log FileNotFoundError.
- LN31: Locally, after an SCSS change, restart the server — deleting `/web/assets/%` attachments alone still serves the old bundle.
- LN32: The local Mac pauses for minutes at a time (a 0.4 s test showed 17 minutes; a registry load took 15 minutes). Judge speed
  from a single test run, never from wall time.

## 6. Score against the design bar

1. **Hero moments:** the matrix sentence with the in-date ring; the Settings pack switches with "Review the rules"; My learning's
   "Required for you" with one Start button.
2. **Zero dead ends:** every cell says where it stands ("Not on file", "On the course, due …", "Due by …", "No course linked yet");
   every refusal is a sentence (no login, no course linked, already on it, not for them); empty states say how rules arrive
   (write one / switch on a pack).
3. **Plain language EN + VI:** walked in both; pack rule names and legal notes translated.
4. **Motion:** rise-in, drawer slide; off under reduced motion.
5. **Weakest:** the PDF was not produced locally; phone width not walked; the Vietnam safety groups are empty until HR fills them
   (owner item 3).

## 7. Owner items (plain English)

1. **"Confirm with Rize" notes** say "Confirm before switching on" instead, because every customer database gets the country packs
   and should not see Rize's name. Say if you want "Rize" in them.
2. **What is a "site"?** The matrix filter and the fire-warden / first-aider check use the employee's Work location when it is
   filled in, and otherwise their department. Today nobody's Work location is filled in, so sites are departments.
3. **Vietnam safety groups start empty.** Nobody is in group 1–6 until HR sets it (one by one on the employee form, or many at once
   from the matrix with "Set safety group"). By law "group 4" is everybody else; the system does not assume it. Do you want
   everybody without a group to count as group 4 in Vietnamese companies?
4. **Rules marked "To confirm"** arrive switched off (Vietnam: retraining, fire groups 1–3, first-aiders; India: mock drills;
   Indonesia: production-machine licences, safety committee report, SMK3; plus the handover's open questions per country). They need
   Rize's answers before anyone switches them on.
5. **Rules you write yourself assign by themselves** from the next morning (the handover's default); country-pack rules never do
   until you switch "Assigns itself" on per rule.

## 8. Deploy plan (as at the gate) — risky tier

**Why risky:** new table (`pb.training.requirement`, 26 template rows per DB), three new employee columns, hours columns on course /
assignment / certificate, a migration that converts live day-one rules and schedules. **For the coordinator's HOLD line:** HEAD
installs and upgrades cleanly again since `a0069d5d0`; with the walk fixes (§9) the suites are green except the two pre-existing
failures.

**Live facts (read-only, 2026-10-21 ~17:20 UTC):** pb_training 19.0.1.5.0 on all four; active jobs payobook 37, payobook_template 0,
p0clone 26, rize 69; no open START in `/opt/deploy-notes.md` (last line: the coordinator's HOLD note). Live day-one rules /
schedules: payobook 1 / 3, others 0 / 0 → the migration should log "1+ from day-one rules (one per course), 3 from schedules" on
payobook and 0 / 0 elsewhere. Payobook demo facts for the seed: company 5 "Payobook Vietnam JSC", course 27 "DEMO Agronomist
basics", departments Manufacturing (133) and Construction (157), demo joiners 20208 / 20209 present.

1. `cat /opt/deploy-notes.md` — no open START from anybody. Take the lock with a detached unit (LN25):
   `sudo systemd-run --collect --unit=l2-lock /usr/bin/flock /tmp/payobook-studio-deploy.lock /bin/sleep 10800`. START line
   `… | Claude (LEARNING L2) | START | pb_training | p0clone,payobook,payobook_template,rize | ~10 min, service stopped during -u | …`.
   Announce to peer sessions.
2. Versions before = 19.0.1.5.0 ×4 (nobody shipped L2 — a "combined" release from HEAD could have, ledger LN15).
3. Backups (LN25): `sudo sh -c "sudo -u postgres pg_dump -Fc <db> > /odoo/backups/learning-l2-20261022/<db>.dump"` ×4, each checked
   with `pg_restore -l`.
4. Stage: `sudo rm -rf /tmp/deployL2 && mkdir -p /tmp/deployL2`; `git archive HEAD pb_training` → upload; scoped
   `sudo rsync -a --delete /tmp/deployL2/pb_training/ /odoo/odoo-server/addons/pb_training/` (never the addons root); tree hash =
   local (skip `__pycache__`, `*.pyc`, `.DS_Store`); PO gate on the box with its PoFileReader (expect 890 rows, 0 empty code rows).
5. Snapshot active job ids per DB (expect 37 / 0 / 26 / 69).
6. Stop the service. Detached unit + sentinel, one DB at a time, **p0clone first**: `-u pb_training --stop-after-init`; grep EXIT,
   Traceback and the migration line "legacy rows converted to required training — N from day-one rules, M from schedules"; then
   payobook, payobook_template, rize. Stop at the first failure and restore that DB from its dump.
7. Asset ritual per DB (signal, delete `/web/assets/%` attachments, bump `web.assets.version`); start; registry loaded; warm
   payobook / rize / p0clone with one curl each; jobs back to the snapshot (pb_training's own job records reload with `-u`: on
   payobook_template switch 72/73 back off if they come back on, LN18).
8. Verify per DB: version 19.0.1.6.0; `pb_training_requirement` has 26 rows with no company (11 VN, 4 IN, 8 ID, 3 SG) and none
   active; `hr_employee` has `pb_safety_group`, `pb_posh_ic_member`, `pb_sg_experienced`; `pb_training.enforce_cap` = 500; **no
   pack switched on anywhere**; converted rows link back to their rule / schedule; `pb_training.day1_auto` unchanged; 0 ERROR lines
   since start; `/web/health` 200.
9. Demo data, **payobook only**, service stopped: `odoo-bin shell -d payobook --no-http < l2_demo_seed.py` (safety groups on up to 20
   DEMO people in Manufacturing / Construction, two Safety Officers, two managers; DEMO Field safety basics, DEMO Forklift licence,
   DEMO Induction — all assign-by-hand; Vietnam pack on for company 5 with group 4 linked to course 27; prints the matrix sentence
   and the five state counts; runs the morning job once inside a rolled-back savepoint — expect 0 required courses put on). Restart,
   warm.
10. DONE line, release the lock (`systemctl stop l2-lock`).

**Live walk (Fable, ledger LN16), payobook.com:** Overview fifth chip and sentence; Required › Matrix (all five states on company 5,
filters, Assign now on one DEMO cell, bulk Set safety group on DEMO people, spreadsheet, **Print for an auditor — the PDF is
produced for the first time here**); Rules drawer create / edit / switch off-on; Day one / Comes round again with the payobook
"Converted" rows (1 rule, 3 schedules); Settings › HR › Required training (pack switches, Review the rules); Numbers tiles, section
and "Renewals due in 30 days"; People drawer safety-group chip; My learning "Required for you" as the HR lead and the learner; the
Vietnamese rail and matrix; **portal `/my/training` page titles no longer say "(ESS)"** (L1's 19.0.1.5.1 rides this deploy); console
clean.

## 9. Final local state (before the gate)

- **Walk fixes** (closing commit): quiet "No course linked yet" state (test added), "No course was put on." as a warning,
  filter dropdowns sized to their words, Settings screen gets the `.pbim` scope, VI for the new sentence.
- **Tests isolated:** the first re-run after the walk failed 5 L2 tests because the walked database now held real rules, packs,
  sites and certificates in its own company. The L2 test classes now run in a company of their own (`DEMO L2 Co`) and the
  morning leg takes an optional list of rules (`_enforce_requirements(today, rules=None)`; the job passes none). Another
  deployer gates releases on the suites run on p0clone (deploy log), so the tests must not depend on what a database holds.
- **Final `/pb_training` suite on HEAD's code:** `-u pb_training --test-tags /pb_training` → **297 tests, 2 failed, 0 errors** —
  only `TestTheAssignmentsTab` ×2 (pre-existing, see §2). PO gate 890 rows, 0 code rows without a value. Tree on the local
  overlay = repo tree.

## 9b. Live walk and the two fixes (2026-10-22)

**Fable's live walk on payobook.com (HR lead):** the Required lens works — "0% in date across 4547 people · 1 expiring · 12066
missing · 64 under way", the five state tiles, filters; Day one shows the 3 "Converted" rows; portal titles fixed ("My training |
Payobook", "My certificates | Payobook"); no console errors. **Two bugs:**

1. **"Print for an auditor" failed live:** "Tried to convert multiple documents in wkhtmltopdf using unpatched QT". The template
   called `web.external_layout` once per 40-row block, i.e. one document per page; the live wkhtmltopdf (unpatched QT) cannot merge
   documents. **Fix (19.0.1.6.1):** `external_layout` called once, each block ends with `page-break-after: always` inside the single
   document; one record id to `_render_qweb_pdf` (it always was). Test: `_render_qweb_pdf` mocked → exactly one id; the HTML render
   has exactly one `class="article"` and two page breaks for 85 people (ledger LN33).
2. **My learning listed "DEMO Induction — On the course, due 26 Oct 2026 — Start" twice:** the converted day-one rule and a schedule
   both point at that course. **Fix (19.0.1.6.1):** "Required for you" merges lines by course (most urgent state, then the earliest
   due); the matrix keeps a column per rule. Test added; live check: the HR lead now has one line.

**Found while verifying the PDF live (my RPC-equivalent check, see below):** the one-document PDF works but a printed page of 40
people is ~3.7 MB from the live engine — the whole demo company (4,547 people) came to **428 MB**, one department (1,002 people) to
96 MB: no browser takes that as one answer. **Fix (19.0.1.6.2):** the print-out takes up to 200 people (5 pages); above that it says
"That is N people. The print-out takes up to 200 at a time — narrow it by department, site, job or rule. The spreadsheet has
everybody." (EN + VI). Test updated (250 people → the sentence; one person → a PDF).

**PDF verification on payobook (19.0.1.6.2):** run on the server as the HR lead (`demo.hr@example.com`, uid 6678, training manager),
`allowed_company_ids [5]`, through `odoo-bin shell` with the user set on the environment and the transaction rolled back — I may not
type a production password (ledger LN16), so this is the server-side equivalent of the RPC call: filter "expiring" (1 person) →
`%PDF-`, 424,305 bytes; one person → 426,690 bytes; everybody / a rule covering 4,547 → the refusal sentence. 0 ERROR lines.

**Local suite on the final code:** `/pb_training` 299 tests, 2 failed — the same two pre-existing `TestTheAssignmentsTab` tests.

**Fix deploys** (normal tier, own START 17:32 / DONE 18:21 UTC, lock `l2b-lock`; no backups needed — no data change, the 17:15
backups stand): 19.0.1.6.1 at 17:33 and 19.0.1.6.2 at 18:19 UTC — EXIT=0 ×4 each time, 0 tracebacks, tree hash = commit, PO gate
891 / 0, service down ~80 s and ~70 s, crons 26 / 37 / 0 / 69 (payobook_template 72/73 switched back off after each `-u`), all
three sites 200.

**Note for the owner (demo only):** the demo "DEMO Induction" rule points at the two L1 demo joiners' departments, and they have none
— so on payobook it covers everybody in company 5 (that is why it appears for the HR lead). Harmless on demo data; say if you want it
narrowed.

## 10. Deploy record (GO DEPLOY 2026-10-21 17:14 UTC / 04:14 AEDT)

| Step | Result |
|---|---|
| Notes / lock | no open START; lock held by detached unit `l2-lock` from 17:14 to the DONE line; START 17:14, DONE 17:22 UTC (DONE carries "LEARNING L2 DONE", clearing the HOLD note on 5746c6516) |
| Versions before | pb_training 19.0.1.5.0 on all four (nobody had shipped L2) |
| Backups | `/odoo/backups/learning-l2-20261022/` p0clone 25.0 MB, payobook 77.8 MB, payobook_template 24.8 MB, rize 33.2 MB (each `pg_restore -l` ok) |
| Files | `git archive 68536e8f4 pb_training` → clean `/tmp/deployL2` → scoped `rsync --delete`; tree hash equal (c2942e18…); PO gate on the box 890 rows / 0 empty code rows |
| Upgrade | detached unit `l2-upgrade`, p0clone → payobook → payobook_template → rize: **EXIT=0 ×4**, 0 tracebacks / ERROR lines |
| Migration | "legacy rows converted": payobook **1 from day-one rules, 3 from schedules**; p0clone, payobook_template, rize 0 / 0 |
| Assets / start | signal + `web.assets.version=learning-l2-20261022` + `/web/assets/%` deleted on all four; service down 17:16:35–17:18:28 (the old process took a few seconds to exit after `systemctl stop`; checked by PID, never pkill); health 200 |
| Warm | payobook.com 200, rize.payobook.com 200, p0clone.payobook.com 200 |
| Crons | 26 / 37 / 0 / 69 = snapshot. payobook_template: `-u pb_training` re-activated 72/73 (training jobs) — switched back off (LN18) |
| After | 19.0.1.6.0 ×4; 26 templates per DB (VN 11, IN 4, ID 8, SG 3), none active; 3 employee columns, 4 hours / link columns; enforce cap 500; day-one switch unchanged (0); no pack on anywhere except payobook company 5 (demo); 0 ERROR lines since restart |
| Demo seed (payobook) | 3 short stops (~15 s each, 17:19–17:22): run 1 made DEMO Field safety basics (31), DEMO Forklift licence (32), DEMO Induction (33), Vietnam pack on for company 5 (11 copies, g4 linked to course 27), 14 rules registered; run 2 fixed worker safety groups (demo names carry no DEMO prefix → 20 workers in groups 3/4); run 3 filed one DEMO forklift licence with 20 days left on a plant worker (document 165) for an expiring cell. Matrix on company 5: "0% in date across 4547 people · 1 expiring · 12066 missing · 64 under way" — valid 5, expiring 1, missing 12066, under way 64, not due 5 (all five states). Morning job test run rolled back: 0 required courses put on. Seed fixes are in `l2_demo_seed.py` (uncommitted until the closing commit). |
| Live walk | pending (Fable, LN16) |
