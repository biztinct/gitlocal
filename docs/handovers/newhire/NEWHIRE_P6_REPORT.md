# NEWHIRE P6 — checklist + equipment names in vi/id, studio on the other four sites (report)

Release engineer, 25 Nov 2026 (UTC). Handover `NEWHIRE_P6_HANDOVER.md`. Engineering receipt: real technical names on
purpose. No credentials, client names or client data in this file.

**Result: GO. Pushed to `19.1` (`b763d7d49`, the deployed commit) and LIVE on all five databases, 354 s of downtime
(09:53:36–09:59:30 UTC).** `pb_new_hire` 19.0.1.5.0 is now installed on **payobook_template, p0clone, sudima, rize**
(already on payobook): People › Employees › Add employee is the seven-step screen everywhere. The joining-checklist
step names and descriptions, the checklist name and the equipment names read in Vietnamese and Indonesian on all five.
Every database exit 0, 0 ERROR, nothing restored. abm and `_test_sudima_policy_20261119` untouched. Nothing was created
on rize, sudima, p0clone or the template.

## 1. Part 1 — what a Vietnamese / Indonesian reader saw in English, and the fix

### 1.1 The records (all shipped `noupdate` data; English only on all five databases before P6)
The joining checklist every new joiner gets is `pb_onboarding.journey_template_rize_onboarding` "New joiner — the full
welcome", 11 steps: 9 from `pb_onboarding`, 1 from `pb_training`, 1 from `pb_goals`. The old 5-step skeleton
`pb_lifecycle.journey_template_onboarding` is switched off everywhere and was left as it is.

| Module | xml id | Field(s) | English |
|---|---|---|---|
| pb_onboarding | `journey_template_rize_onboarding` | name | New joiner — the full welcome |
| pb_onboarding | `step_rize_buddy` | name, description | Choose their buddy |
| pb_onboarding | `step_rize_laptop` | name, description | Laptop and equipment |
| pb_onboarding | `step_rize_access` | name, description | Tool access |
| pb_onboarding | `step_rize_intro_form` | name, description | Tell us about you |
| pb_onboarding | `step_rize_poster` | name, description | Welcome card to the team |
| pb_onboarding | `step_rize_day1` | name, description | Day-one introduction |
| pb_onboarding | `step_rize_credentials` | name, description | Send their sign-in details |
| pb_onboarding | `step_rize_data` | name, description | Finish your own details |
| pb_onboarding | `step_rize_orientation` | name, description | Welcome session |
| pb_training | `step_training_day1` | name, description | Put them on their first courses |
| pb_goals | `step_rize_goals` | name, description | Open their goals for the year |
| pb_assets | `cat_laptop`, `cat_phone`, `cat_sim`, `cat_idcard`, `cat_credit_card`, `cat_monitor`, `cat_email`, `cat_login`, `cat_software`, `cat_phone_number` | name | Laptop, Phone, SIM card, ID card, Company card, Monitor, Email account, System login, Software licence, Phone number |

Where they are read: studio step 6 (checklist name, step titles, equipment chips), Journeys (a checklist's steps), the
New joiners drawer (same server call), `/my` joining page, the no-login link page, equipment requests (category).

### 1.2 What was built (commit `1de6257e9`, fix `b9a11bd69`)
- **`.po` entries** in each owning module (`vi_VN.po`, `id_ID.po`; `pb_onboarding/i18n/id_ID.po` is new and holds only
  these 19 entries): 33 rows × 2 languages. msgids are the XML English byte for byte (generated from the XML, test T1).
  Translations reuse the product's terms (người đồng hành / pendamping, hành trình / perjalanan, đợt lương /
  penggajian, Buổi chào đón, yêu cầu thiết bị / permintaan perlengkapan). No vendor word and **no product word** in any
  new msgstr ("the system": hệ thống / sistem), so a white-label tenant never reads the master product's name.
- **`pb_lifecycle` 19.0.1.22.0**: `pb.journey.template.step.description` translatable (column text → jsonb on
  upgrade, standard conversion `{"en_US": old}`; table holds ~50 rows). `models/seed_translations.py`
  `apply_seed_translations(env, module, targets)`: reads the module's OWN `.po`, writes vi/id onto shipped rows only
  where the stored English is still the shipped English (a white-label tenant's brand rewrite of that English counts as
  unchanged, via biz_debrand's own rewrite), only for an active language that is missing or holds a copy of the English;
  never the English, never a renamed row, never a company's own row; idempotent. Post-migrate in each of the four
  modules calls it (`pb_onboarding` 19.0.1.5.0, `pb_assets` 19.0.1.4.0, `pb_training` 19.0.1.15.0, `pb_goals`
  19.0.1.6.0).
- **Running checklists** (NH79): a checklist's steps are the case's own copies, in the language of whoever opened it,
  so translating the template alone changes nothing on a running checklist. `pb.journey.task._pb_shown_texts()` shows
  the step's words in the reader's language while the task still holds one of the step's own versions; a step changed
  in that journey keeps its words. Read-only. Used by `pb.journeys.get_case` (Journeys + New joiners drawer), the `/my`
  joining page (`pb_onboarding/controllers/portal.py`) and the link page (`pb_lifecycle/controllers/token_pages.py`).
- **`biz_debrand`** (files only, version unchanged — a bump cascades an upgrade of every dependant): the clean-up that
  runs at the end of every upgrade read `pb_journey_template_step.description` as plain text (NH80). Its plain-text pass
  now skips jsonb columns, the column is listed as translated, and a journalled text cell that became jsonb is restored
  per language.
- Column readers checked: only `biz_debrand/models/scrub.py` read these columns raw (fixed above); an old one-off
  migration of pb_lifecycle (19.0.1.0.1) touches another column. No JS reads them raw.

### 1.3 Tests
`pb_onboarding/tests/test_p6_translations.py` (tag `newhire`), 11 tests:

| # | Test | Result |
|---|---|---|
| T1 | `.po` parse, markers, every xml id exists, msgid = XML English, msgstr filled, no vendor/product word, every shipped row covered | pass |
| T2 | shipped rows get vi + id (38 values for pb_onboarding), English unchanged | pass |
| T3 | a renamed step is left exactly as it is (its unchanged description is still translated) | pass |
| T4 | a second run writes nothing | pass |
| T5 | a company's own step with the same English is untouched | pass |
| T6 | a copy of the English in vi is replaced; a company's own Vietnamese is kept | pass |
| T7 | white-label: English that went through the brand rewrite still counts as shipped | pass |
| T8 | running checklist: vi / id reader see the step words; a step changed in the journey keeps its words; a checklist opened in Vietnamese reads English for an English reader; nothing written | pass |
| T9 | equipment names vi / id; second run writes nothing | pass |
| T10 | the clean-up's plain-text pass no longer trips on the jsonb column; the translated pass rewrites every language | pass |
| T11 | the training and goals steps | pass |

**Suites of every touched module + the studio** (`/pb_lifecycle,/pb_onboarding,/pb_assets,/pb_training,/pb_goals,
/biz_debrand,/pb_new_hire`), before (19.1 copies of the six modules first in the path) vs after, two copies of the walk
database: before **1,081 tests, 4 failed + 1 error**; after **1,092 tests (+11 new), 5 failed, 0 errors**.
- Same in both: `biz_debrand` test_05 (bot-shaped label), test_09 (product rule opt-in), `pb_training` T5 numbers row.
- Before only: `biz_debrand` test_04 ("the scan reaches this product's modules") and a `pb_lifecycle` studio test
  error — the slimmed "before" folder hides sibling modules from the scan; the studio test passed after.
- After only: `biz_debrand` test_01 "no product name where no seam can reach it" names `pb_demo_portal/
  signup_recovery_mail.xml` (not touched by P6; the before run could not see that module, same cause as test_04).
- After only, **caught and fixed**: `pb_training` test_t9 read "no Acmework login" — my T7 wrote the brand settings,
  and the brand is cached in memory beyond a test rollback. T7 now fakes the brand lookup (`b9a11bd69`); re-run of
  T1–T11 + `pb_training` TestBulk on the merged code: **15 / 15**.

### 1.4 Local walks (Claude-in-Chrome; Chrome's own page translation off, font check 0; console clean)
Walk database `nh10_p6` (copy of the P5a walk world, real `-u` of the five modules: exit 0, 73 s, 0 ERROR).
| # | Walk | vi | id |
|---|---|---|---|
| W1 | studio step 6: checklist name, step titles, equipment chips | "Nhân viên mới — chào đón trọn vẹn, 11 bước"; "Chọn người đồng hành" … "Buổi chào đón"; "Máy tính xách tay, Điện thoại …" | "Karyawan baru — sambutan lengkap, 11 langkah"; "Pilih pendamping" … "Sesi sambutan"; "Laptop, Telepon, Kartu SIM …" |
| W2 | New joiners drawer of a checklist opened in English before the upgrade | step names + descriptions Vietnamese | Indonesian |
| W3 | Journeys › a checklist | — | "Laptop dan perlengkapan / To Do / Permintaan diajukan otomatis …" |
| W4 | Equipment requests list | "Máy tính xách tay (LT)", "Tài khoản email (EM)", "Thẻ nhân viên (ID)" | "Akun masuk sistem (LG)", "Kartu ID karyawan (ID)" |
| W5 | English reader | unchanged English | |

## 2. Part 2 — release

### 2.1 Timeline (UTC, 25 Nov 2026)
| Time | Step |
|---|---|
| 08:26 | deploy notes read: DOCSTUDIO PDFFIX had an open START (retry); built Part 1 meanwhile |
| 08:53 / 08:58 | PDFFIX DONE + verified; its commit `9b0e4dbea` reached `19.1` (`b994ccee0`) ~09:15; merged into the P6 branch (one conflict: `pb_training` version line → 19.0.1.15.0 on top of their 19.0.1.14.1; their report files kept) |
| 09:24 | P6 tests + `pb_training` TestBulk on the merged code: 15 / 15 |
| 09:25 | pushed `b994ccee0..b763d7d49` to `19.1` (fast-forward); staged from `git archive b763d7d49` |
| 09:25–09:29 | prep: staged = commit; **server trees = 19.1 before P6** (all 7, so PDFFIX's `pb_training` is the base, nothing rolled back); PO gate; renamed-rows gate; dependency closure (128) installed ×5; vi + id active ×5; dumps ×5 read back; file-folder links; counts; job snapshots |
| 09:29–09:34 | rehearsals on hidden copies of **sudima** and **rize** (§2.3) — passed |
| 09:35–09:40 | rize copy browser walk (§2.4); copy dropped 09:40:54 |
| 09:41 | START line; try 1 refused itself: an employee was using their own pages on rize (last request 09:35) |
| 09:51 | try 2: quiet since 09:36 on rize/payobook/sudima; go-live dumps ×5; notes re-read; lock taken |
| 09:53:36 | service stopped; per-module scoped rsync; addons = staged |
| 09:53–09:58 | install/upgrade one database at a time (§2.5) |
| 09:59:30 | service up; five sites 200; DONE line; lock removed |
| 10:00–10:08 | verification (§2.6), live read-only looks, letter check; NOTE line 10:08 |

Backups `/odoo/backups/newhire-p6-20261125T0925Z/` (prep dumps, go-live dumps, file-folder hard links,
`previous-trees.tgz`, rollback plan). Evidence `/tmp/newhire-p6-20261125T0925Z/`.

### 2.2 What shipped
| Module | Version | Where | How |
|---|---|---|---|
| `pb_new_hire` | 19.0.1.5.0 (files unchanged) | **installed on payobook_template, p0clone, sudima, rize**; already on payobook | `-i` on the four |
| `pb_lifecycle` | 19.0.1.21.0 → 19.0.1.22.0 | all five | `-u` |
| `pb_onboarding` | 19.0.1.4.0 → 19.0.1.5.0 | all five | `-u` (+ migration) |
| `pb_assets` | 19.0.1.3.0 → 19.0.1.4.0 | all five | `-u` (+ migration) |
| `pb_training` | 19.0.1.14.1 → 19.0.1.15.0 | all five | `-u` (+ migration) |
| `pb_goals` | 19.0.1.5.1 → 19.0.1.6.0 | all five | `-u` (+ migration) |
| `biz_debrand` | 19.0.2.11.0 (unchanged; Python only) | all five | files + restart |

Release gates (prep): server copies of all seven = `19.1` before P6 (`b994ccee0`) — nothing newer or different;
`.po` parse ×14 files, 0 vendor word; **renamed shipped rows: none on any database** (NH78) — on rize one description
differs only by the tenant's brand name, which the migration treats as unchanged.

### 2.3 Rehearsals (hidden template copies; jobs, mail servers, incoming mail off first; staged code first)
| Copy | Command | Result |
|---|---|---|
| `nh6_rh_sudima` (680 people) | `-i pb_new_hire -u pb_lifecycle,pb_onboarding,pb_assets,pb_training,pb_goals` | exit 0, **52 s**, 0 ERROR, 0 Traceback; translations written: 38 + 20 + 4 + 4 values, renamed none; 11 steps and 10 categories carry vi + id; data = install footprint only (6 new employee columns, +1 mail template, +4 record rules); checklists unchanged; copy dropped |
| `nh6_rh_rize` (313 people) | same | exit 0, **48 s**, 0 ERROR, 0 Traceback; same writes; employee values over every existing column **identical to live** (checksum), the 6 new columns empty; +4 technical change notes (2 scheduled jobs, 2 server actions, as P5b); running checklists identical to live; the brand-rewritten buddy description got vi + id; no product word in any new word; kept for the walk, then dropped |

### 2.4 Browser on the rize copy (tunnel; two throwaway logins made on the copy, gone with it; console clean)
- People › Employees › **Add employee opens the seven-step screen** ("0 of 7 steps done"); "From Hiring" tile: "No
  signed offers are waiting".
- An Indonesian team, a job, Country of work Indonesia: currency **IDR**, trial 3 months, Indonesian letter,
  KTP / NPWP / PTKP / BPJS / Kartu Keluarga papers. **No pay scheme is shown**: "No pay scheme pays <team> yet. You can still add the person. Set who pays this team in Mapping before the first pay run." The
  payslip example says the same (see §3.1).
- Step 6 reads "Sign-in to My <tenant brand>" (the white-label name, not the product's), checklist "New joiner — the full welcome, 11 steps", 10
  equipment chips.
- One DEMO hire sent **on the copy**: "DEMO NH P6 Rehearsal is added … **No welcome message: This site does not send
  email. Copy the welcome link and send it to DEMO yourself.**" 0 mail rows queued; 11 checklist steps, 4 equipment
  requests, contract letter (PDF, 38,622 B) — all on the copy, dropped with it.
- Vietnamese reader: New joiners drawer — every step name and description Vietnamese, "Sao chép đường dẫn chào
  mừng" offered; Indonesian reader (same server calls): steps and the hire's equipment requests in Indonesian.

### 2.5 Go-live (order payobook_template → p0clone → sudima → rize → payobook; staged = `b763d7d49`)
| Database | Command | Exit / time / ERROR | Jobs active before → after |
|---|---|---|---|
| payobook_template | `-i pb_new_hire -u <five>` | 0 / 52 s / 0 | 40 → 40 |
| p0clone | same | 0 / 48 s / 0 | 49 → 49 |
| sudima | same | 0 / 48 s / 0 | 91 → 91 |
| rize | same | 0 / 50 s / 0 | 92 → 92 |
| payobook | `-u <five>` | 0 / 54 s / 0 | 59 → 59 |

Asset purge + `orm_signaling_assets` + `web.assets.version = newhire-p6-20261125T0925Z` per database. No job was
re-activated, no new job row (`pb_new_hire` creates none), so nothing to add to `pb_tenants.template_active_crons`.
**Downtime 354 s.**

### 2.6 Verification (live)
| Check | Result |
|---|---|
| Trees | all 7 server trees = commit `b763d7d49` |
| Versions | manifest = `latest_version` (normalised) for all 7 modules on all five; `pb_new_hire` installed on all five |
| Jobs vs prep snapshot | identical ×5 (59/40/49/92/91 active); payobook job 156 off; lifecycle reminders off on payobook, on elsewhere (unchanged) |
| Data right before the stop vs after | payobook identical; the four new sites exactly the rehearsed install footprint; running checklists (`journey_tasks` checksum) identical ×5; the 6 new employee columns empty ×5 |
| Compiled code | studio + takeover + Learn replica in the bundle on all five; old window still registered |
| Server log since the stop | 0 ERROR / CRITICAL, 0 Traceback, 0 asset errors, 0 white-label clean-up warnings; one service process |
| Sites | five × 200 |
| Live read-only look (`p6/nh6_look.py`, server shell, rolled back) | rize: a checklist opened before the release reads in vi and id; equipment names vi + id ×5; "From Hiring" tile answers ×5 (0 waiting); payobook Vietnamese team "Retail" → scheme "Payobook Retail — End-Month Payroll", ₫, example December 2026: ₫16,530,000 gross → ₫15,056,500 take-home, 13 lines; Vietnam papers listed. Row counts inside the shell identical, and 66 checksummed count lines per database identical to the moment after the upgrade ×5 — **the example and the looks left no trace** |
| Rehearsal copies | both dropped, file folders gone, rehearsal service stopped, throwaway logins gone |

### 2.7 Contract letter after the PDF tool change (payobook, the P5b demo person; rendered with the "download" call, nothing filed, rolled back)
PDF produced: 137,602 B, A4, **2 pages**, made by the new tool (wkhtmltopdf 0.12.6.1, patched Qt). Opened and looked at:
- Page 1: company letterhead now prints (logo, "Payobook Vietnam JSC / Vietnam"), date top right, the bilingual
  two-column table (Vietnamese | English) intact — no overlap, no cut text, borders right; footer "Trang 1/2".
- Page 2: letterhead again, **only the two signature blocks**, footer "Trang 2/2".
- Compared with the letter filed for the same person in P5b with the old tool: **1 page**, no letterhead, no footer,
  signatures on page 1. The new tool's larger drawing plus the letterhead gap pushes the signatures onto their own page.
  Not changed here (the letter template belongs to the document session) — reported to the owner and the PDF session.

### 2.8 Rollback plan (written to the evidence folder before the stop; not needed)
Same as P5b: a failing database inside the window → previous trees back from `previous-trees.tgz`, the failed and
already-done databases restored from the go-live dumps, FAILED line; after go-live → report first, files from the tar,
data only if it changed and the owner agrees; `pb_new_hire` can be uninstalled per site (old window returns). The
translations are additive (vi/id keys on shipped rows only).

## 3. Findings, deviations, open items

### 3.1 For the owner
1. **rize and sudima: the new screen cannot name the pay scheme or show a first-payslip example yet.** rize has 4
   active pay schemes but **none of its 32 teams is linked to one** in Mapping; sudima has **no active pay scheme**
   (its clock-pay scheme is still a draft). The screen says so plainly and lets HR add the person ("Set who pays this
   team in Mapping before the first pay run"). Currency, trial period, contract letter and papers still follow the
   country. Linking teams to schemes is tenant setup (not changed here); the old window never showed a scheme either.
2. **Contract letter is now 2 pages** with the signatures alone on page 2 (§2.7) — a layout tune for the PDF session.
3. **Indonesian users still see English screen labels** on the New joiners board and the equipment screens (the
   modules have almost no Indonesian screen translations: `pb_onboarding` none, `pb_assets` 4 phrases), and some
   Vietnamese labels are missing there too ("0% complete", "Task", column titles of Equipment requests). Only the names
   (data) were in scope; translating those screens is a next step if wanted.
4. Not translated (outside the four screens): the "Tell us about you" questions on the joiner's link page, the old
   switched-off 5-step checklist, step names inside the lifecycle reminder emails.
5. Learn has no Indonesian (unchanged, NH70).

### 3.2 Deviations
1. **`biz_debrand` changed without a version bump** (files + restart): a bump would upgrade every module that depends
   on it on all five. Needed because making the step description translatable broke its plain-text pass (NH80).
2. **`pb_training` and `pb_goals` added** to the handover's module list: their steps are 2 of the 11 on the joining
   checklist.
3. **Running checklists are translated at display time**, not by migrating their stored copies (NH79): no change to
   the checklist table, no conflict with the white-label journal on rize; a step changed in a journey keeps its words.
4. **Renamed rows**: the migration never writes them, but the framework's own translation loading would (NH78). The
   release was gated on "no renamed shipped row" (none on any database). Pinning a renamed row's missing languages to
   the company's own words would close the gap for the future but writes onto a renamed row — an architect call.
5. Browser walks on the rize copy and locally; live proven with server checks (never as the owner's admin, NH76).
   Live browser look on rize/sudima not done — **ask the owner for a two-minute look** (People › Employees › Add
   employee) on each site.
6. The letter check used the "download" call (files nothing) instead of saving another letter to the demo person.

### 3.3 Left behind
- Live payobook: nothing new (the letter was rendered, not filed). rize, sudima, p0clone, template: nothing created.
- Backups `/odoo/backups/newhire-p6-20261125T0925Z/`, evidence `/tmp/newhire-p6-20261125T0925Z/` on the server.
- Local: worktree `gitlocal-worktrees/nh-p6`; walk database `nh10_p6` (dropped at the end of this phase).

## 4. Design bar
- Hero moment: a Vietnamese HR officer opens a joiner's checklist that an English colleague started last week and
  reads every step in Vietnamese; an Indonesian manager sees "Laptop dan perlengkapan" on the same checklist.
- Zero dead-ends: a step renamed by the company keeps the company's words; a site with no linked pay scheme says why
  and what to do.
- Plain language: product glossary terms; no product name inside translated steps.

## 5. New gotchas
NH78–NH82 in the ledger.
