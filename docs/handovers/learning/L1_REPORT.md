# LEARNING L1 — Certificates and expiry — report

Implementer: Opus, 2026-10-21. Spec: `L1_CERTIFICATES.md`. Ledger: `LEARNING_LEDGER.md` (rows LN17–LN25
written after the deploy).
Status: **COMPLETE — LIVE ×4 DBs 2026-10-21 10:17 UTC (21:17 AEDT); live walk by Fable passed 21:25 AEDT.** Rulings on §7 in ledger LD10. One follow-up committed but not deployed: the tab-title fix `f7182ccde` (pb_training 19.0.1.5.1, §10).

## 1. What shipped (committed on 19.1, not pushed)

| Module | Live now | After L1 |
|---|---|---|
| pb_training | 19.0.1.4.1 | **19.0.1.5.0** (+ migration `19.0.1.5.0/post-certificates.py`, new dependency `hr_skills_survey` — installed on all four DBs, checked read-only) |
| pb_vendor_access | 19.0.1.14.0 | **19.0.1.15.0** (+ migration `19.0.1.15.0/post-retire_training_gates.py`) |
| pb_import_kit, pb_employee_vault, pb_me_portal, pb_learning_hub, hr_skills_survey | — | **unchanged** (`award` was already in `ic()`) |

Commits:
- `48de35b5f` (a) feat(training): certificate record fields + migration + validity on test certificates
- `e4ba89a8b` (b) feat(training): uploads, wallet page, learning record PDF
- `d9c423280` (c) feat(training): renewal ladder + auto re-assignment
- `1370fb167` (d) feat(training): Certificates lens, Overview and Numbers tiles (+ item 9, pb_vendor_access)
- (e) this report + the demo seed script `docs/handovers/learning/l1_demo_seed.py`

Shared files (manifest, `models/__init__.py`, `training_common.py`, the `.po`) went into the first commit that needed
them with their final content, so (a)–(c) are feature-scoped but not each separately installable; (d) is. No foreign
commit touches pb_training or pb_vendor_access since L0 (`git log bcd15a279..HEAD -- …` empty). Committed tree =
tested tree (byte-identical, `git archive HEAD` vs the staging tree).

## 2. Tests

Local runtime `/Users/adity/odoo19`, staging tree from L0 (seven `7a2deccb4` modules pinned, ledger NAV P3b) with
pb_training + pb_vendor_access rsynced from the repo. Test DB = fresh copy of `am_l0_t2` (L0's walked DB). Baseline =
same copy, same suites, with HEAD-before-L1 copies of the two modules overlaid first in `addons_path`.

| # | Result |
|---|---|
| T1 | **Pass** (2): pass with validity 12 → `training_source='test'`, attempt linked, issue = attempt end, expiry = +12 months, name "(2026)"; validity 0 → no expiry, state `none`. |
| T2 | **Pass** (2): second pass a year later files a second document and the first gets `renewed_by_id`; the same pass noticed again files nothing; the résumé line (hr_skills_survey) still written; a pre-L1 row (old name, no link) is linked, not duplicated. |
| T3 | **Pass**: back-fill gives test/claim source, links course/test/attempt, stamps expiry only where the test has validity, leaves ordinary files alone, second run changes nothing. |
| T4 | **Pass** (2): all five states and their words; `training_state` searches with `=`, `in`, `!=`. |
| T5 | **Pass** (2): 11 MB → "The file is bigger than 10 MB."; `.exe` → "Only PDF, JPG or PNG files."; good PDF → `upload`, unchecked, attachment on hr.employee; licence without a date refused; a login with no employee → "Only employees can add certificates." |
| T6 | **Pass** (3): trainer's `add_certificate` verb → verified, `verified_by` = the trainer; plain user → AccessError and `{'allowed': False}`; Verify verb. |
| T7 | **Pass** (5): 59 days out → one renewal course (reason Renewal, due = expiry), second run none; outside the window / already expired → none; open assignment → none, no error, the button says why; archived course → none; button assigns as the person who pressed it. |
| T8 | **Pass** (4): keys x60/x30/xm14/x7/x0/xh0 once each on their day, nothing twice in a morning, nothing after the day; a late starter gets only its band; renewed rows skipped; cap respected; `cert_reminders` off → nothing. |
| T9 | **Pass**: three templates render, subject carries the valid words, no vendor word, no `#4F46E5`, brand `#5A4BB0`. |
| T10 | **Pass** (4, own company): tiles = independent recount (30/60/90/expired/in date/never), headline sentence, problem-first order, accent-blind search, department includes sub-departments, paging, another company's rows never show. |
| T11 | **Pass** (3): Overview block + "1 certificate expires within 30 days." + queue chip into the register on `expiring_30`; nothing said at zero; Numbers four tiles, By certificate adds up, `cert_expiring`, spreadsheet has a Certificates sheet. |
| T12 | **Pass** (2): record renders for 0, 1 and many rows; another person's record refused for a plain user, allowed for a trainer. |
| T13 | **Pass** (3): wallet lists only own documents, next-to-expire first, counter; home card + routes exist; a course tile carries its certificate. |
| extra | **Pass**: LN11 (Talent gate lost the training roles), LN10 (server words in Vietnamese with an env; English without), L1 VI words present. L0 rail tests updated to nine lenses and a four-chip queue. |
| T14 | `/pb_training,/pb_learning_hub,/pb_employee_vault,/pb_me_portal,/pb_vendor_access` with all five upgraded: **451 tests, 7 failed + 1 error — every one also fails on the baseline**: TestTheAssignmentsTab ×2 (count the copied DB's own assignments; listed in L0's report too) and pb_me_portal TestMeHomePage.test_04, TestMeHomeCardsPage.test_page_draws_the_cards, TestMyRequestsPage ×2, TestPbMePortal.test_01 (error). Nothing fails only with L1. PO gate: pb_training 390 rows, 0 code rows without a value. |
| T15 | Local Chrome walk, `localhost:8069` / `am_l1_t` (L0's DB upgraded + 12 seeded DEMO certificates, one renewal course). Detail below. |

T15 detail (local):
- **Head of training (admin), EN:** rail OVERVIEW · MY LEARNING · COURSES · ASSIGNED · REQUIRED · TESTS · CERTIFICATES · CLAIMS ·
  NUMBERS. Overview headline "11 people are on 5 courses. 8 are past their date. 3 certificates expire within 30 days."; chip
  "3 Certificates expiring" (amber) → Certificates on the 30-day filter (3 rows). Certificates section on Overview: 3 expire
  within 30 days (amber) · 2 have expired (rose) · 9 in date (green) · 1 never expires (grey) — each opens the register.
- **Register:** "12 certificates. 3 expire within 30 days, 2 have expired."; tiles 3/5/7/2/9/1 (quiet colours, active tile
  ringed); search "do van" finds Đỗ Văn Nam's three; expired rows first; every row says what happens next ("Renewal course
  assigned, due 30 Nov 2026", "Add the new one when it is issued."). Verify → toast "DEMO First aid certificate is marked as
  checked.", shield appears, button gone. Add drawer: person search "binh" → DEMO Lê Văn Bình; licence with no date keeps
  the button disabled; with a date and a real PDF → "DEMO Crane signaller card is on DEMO Lê Văn Bình's record.", headline
  moves to 13. Download → 200 application/pdf.
- **Same in Vietnamese:** rail TỔNG QUAN · CỦA TÔI · KHÓA HỌC · ĐÃ GIAO · BẮT BUỘC · KIỂM TRA · **CHỨNG CHỈ** · HOÀN TIỀN · SỐ LIỆU,
  every label one line in its 60 px button. "14 chứng chỉ. 4 chứng chỉ hết hạn trong 30 ngày tới, 2 đã hết hạn." Numbers: four
  new tiles in VI, "Chứng chỉ" breakdown (DEMO Working at height 8 · 2 hết hạn trong 30 ngày tới · 1 đã hết hạn).
- **Manager (VI), My learning:** "Chứng chỉ của tôi" with the renewal certificate "Đã giao khóa gia hạn, hạn 30 thg 11 2026 ·
  Hết hạn sau 40 ngày" and **Bắt đầu gia hạn** → `/my/training/83` (the refresher course); course card shows reason "Gia hạn"
  and the certificate chip; due words now Vietnamese from the server ("Còn 5 ngày").
- **Plain employee (nam.p3c, VI), portal:** home card "Chứng chỉ của tôi" sits in the Growth section (order 204, after the
  allowance card). Wallet: hero card "CẦN BẠN XỬ LÝ TRƯỚC — DEMO Pesticide handling permit — Hết hạn 10 ngày trước · Hãy thêm chứng
  chỉ mới khi được cấp." with one button "Thêm chứng chỉ mới". Upload through the real form with a PDF → notice "Đã thêm vào chứng
  chỉ của bạn…", card "Tải lên · Nhân sự chưa kiểm tra". Licence without a date → "Giấy phép cần có ngày hết hiệu lực." on the page;
  somebody else's record → "Bạn chỉ có thể in hồ sơ học tập của chính mình." (found English in the walk — fixed, see §3.9).
- **Learning record:** the HTML render reads as a transcript (title, person, job, "Tính đến …", one summary line, Courses finished,
  Certificates and licences with Issued by / Issued / Valid until / Checked). **The PDF itself was not produced locally** — this
  Mac has no PDF tool (the route catches it and says so on the wallet); the live box has `/usr/bin/wkhtmltopdf`, so the PDF is a
  live-walk item.
- Console: no errors on any page walked. Not walked: phone width (window resize does not reach the agent's background tab; CSS
  written: tiles wrap 6→3→2, table scrolls in its own box, drawer one column, wallet hero stacks).

## 3. Deviations from the handover, and why

1. **Migration folder is `19.0.1.5.0`, not `19.0.1.4.0`:** the DBs are at 19.0.1.4.1, so a 1.4.0 migration would never run.
   The back-fill is a model method (`pb.training.certificate._backfill()`) so the demo seed can run it again after giving
   survey 17 its validity (handover §6 expects the migration to stamp document 145 — it can only do so if the validity is set
   first; the seed re-runs it).
2. **Verify for a trainer without an HR group:** the vault's `action_verify` refuses anybody who is not HR, and the training
   tiers do not include HR. So `_pb_training_verify` calls `action_verify` for an HR user and otherwise the vault's own
   sanctioned write `_vault_sys_write` (the method `action_verify` itself calls) with the same three values — the testimony
   names the person who pressed Verify. The guarded fields are never written directly.
3. **Item 9 ignores the "kept across upgrades" stamp:** all four live Talent entries carry `access_customized` (set in bulk on
   every entry by `biz_access` 19.0.1.5.0), so honouring it would change nothing anywhere. A training role opens nothing inside
   Talent any more, so removing it can take nothing away. A role is only removed when none of its abilities is still in
   Talent's gate (a Tenant administrator keeps Talent through Head of goals). Locally: 3 role links removed.
4. **Renewal courses only for certificates not yet expired** (`expiry_date >= today`): a back-filled certificate that ran out
   years ago would otherwise become a renewal course overdue on the day it is made, mailing its manager and the HR lead the same
   morning. Those are for HR to decide with "Assign the refresher". Due date = the expiry (as specified).
5. **Ladder keys fire once per band, not on an exact day** (x60 = 31–60 days, x30 = 8–30, x7 = 1–7, x0 = the day; manager at
   ≤14; HR on the day): a missed night still sends, and a certificate added with 20 days left gets the 30-day mail rather than a
   late 60-day one. Leg 3b (renewals) and leg 4 run inside the existing "reminders on" branch, as the handover's numbering says.
6. **Mail stays English end to end.** Item 10 translates the server words for screens (`env._` with the reader's language). The
   mail computes keep their English because the template bodies have no Vietnamese; translating only the inserted words would
   produce half-Vietnamese, half-English mail. Per-recipient mail is for a later phase.
7. **The certificates card on the employee home** is registered from pb_training into the home page's card list (a plain
   module-level dict) instead of editing pb_me_portal (non-goal). Without it the card landed in "More" with a plain icon —
   caught by pb_me_portal's own test. No short text (that test wants every short text in pb_me_portal's `.po`), so the card
   shows its own translated description.
8. **Register people picker** offers people without a login (a licence belongs to the person); the course picker still does not.
9. **Portal refusal sentences were always English** (they are built once at import). They are now translated when the page is
   drawn; the new L1 ones have Vietnamese, the older ones stay English until translated (pre-existing gap, LN10 family).
10. **Two vault reminder systems both run** (spec non-goal): the vault's own job still raises one HR to-do 30 days out; L1's
    ladder sends the emails. Neither was switched off.
11. Report action id is `action_report_learning_record` (template keeps `report_learning_record`; one xml id cannot be both).

## 4. Vietnamese

`pb_training/i18n/vi_VN.po`: 202 new entries (all L1 words: register, drawer, wallet, record, Overview, Numbers, server
sentences, selection labels, Licence / permit). 15 existing entries (the reasons, states and due words) only gained the
`odoo-python` marker and a `training_common.py` occurrence so the server can say them — no msgstr changed. Message ids for
views and JS were taken from Odoo's own export of the module, so they match exactly. Older untranslated portal/Numbers text
(pre-L1) is untouched.

## 5. Ledger rows (written as LN17–LN25; the list below is what was found during the build)

- LN16: `biz_access` 19.0.1.5.0 stamped every left-menu entry `access_customized`, so the stamp no longer marks a human edit
  (all four live Talent rows carry it). A gate retirement that honours it is a no-op.
- LN17: The vault's `action_verify` is HR-only and the training tiers hold no HR group — verify through `_vault_sys_write`.
- LN18: The employee home sorts `/my` cards through `pb_me_home.TILES`; a module adding a portal card must register it (from its
  own side) or it lands in "More". Its test also wants every short card text in pb_me_portal's `.po`.
- LN19: The ORM hands a non-stored field's search method an `OrderedSet` for `in` (Odoo 19): never `isinstance(value, list)`.
- LN20: `env._()` (not `_()`) for words said from a plain function: `_()` with no language in the frame falls back to the
  user's language and logs a WARNING with a stack in cron; `env._` reads the env and defaults to English.
- LN21: Portal routes render in the website's language; `_PROBLEMS`-style dicts built at import are English — translate at render.

## 6. Score against the design bar

1. **Hero moments:** register — one sentence over six quiet tiles; wallet — "Needs you first" card with one button (Start renewal /
   Add the new one); record — a one-line summary over two tables, company letterhead.
2. **Zero dead ends:** every certificate says what happens next; every refusal is a sentence on the page; the register's empty
   state says how certificates arrive; renewal clash says who is already on the course and until when.
3. **Plain language EN + VI:** walked in both; rail label fits.
4. **Motion:** rise-in, drawer slide, all off under reduced motion.
5. **Weakest:** the PDF was not produced locally (live item); phone width not walked.

## 7. Owner items (plain English) — ruled in ledger LD10: (1) mails stay English for now, (2) no automatic refresher for certificates that ran out before go-live, (3) both expiry reminders stay on

1. **Reminder emails are in English** for everybody, including the new certificate emails. Making them Vietnamese for Vietnamese
   staff means translating the email texts themselves — a later phase, unless you want it sooner.
2. **Certificates that ran out before this went live** do not get a refresher course put on automatically (it would arrive
   already late and email managers the same morning). HR can press "Assign the refresher" on any of them in the register.
3. **Two reminders for the same certificate**: the older document system still raises an HR to-do 30 days before any document
   expires; the new one emails the person, their manager and the HR lead. Say if you want one of them switched off.

## 8. Deploy plan (as at the gate)

**Situation (10:10 UTC, read-only):** `/opt/deploy-notes.md` has an **open START from ChatGPT at 10:04 UTC** (pb_formula_studio,
pb_hr_payroll_formula, pb_payroll_templates, pb_payrun_wizard, all four DBs, commit `3f3dd4fa3`); the service is stopped for it.
My plan starts only after their DONE (or FAILED + their all-clear). Their commit is below mine on 19.1, so if they redeploy
"combined committed repository state" from a later HEAD they could carry L1 too (ledger LN15) — check versions first.

**Tier: normal** (new fields + migrations on existing modules; no new module), with backups because the migration writes
existing vault rows. Live facts (read-only): `hr_skills_survey` installed on all four; surveys with validity: 0 on every DB;
"— certificate" vault rows: payobook 5, others 0; Talent rows all stamped (handled, §3.3).

1. `cat /opt/deploy-notes.md` — no open START; if anybody else's is open, wait. `flock /tmp/payobook-studio-deploy.lock` for the
   whole run; START line `… | Claude (LEARNING L1) | START | pb_training,pb_vendor_access | p0clone,payobook,payobook_template,rize | ~6 min | …`.
   Announce to peer sessions.
2. Verify nobody already shipped L1: `latest_version` of pb_training / pb_vendor_access per DB (expect 19.0.1.4.1 / 19.0.1.14.0).
3. Backups: `pg_dump -Fc` of all four DBs into `/odoo/backups/learning-l1-20261021/`.
4. Stage: clean `/tmp/deployL1`; `git archive HEAD pb_training pb_vendor_access` → upload; per-module scoped
   `sudo rsync -a --delete /tmp/deployL1/<m>/ /odoo/odoo-server/addons/<m>/` (never the addons root); tree hash = local; PO gate
   on `pb_training/i18n/vi_VN.po` with the box's PoFileReader.
5. Snapshot active cron ids per DB (expect payobook 37, template 0, p0clone 26, rize 69).
6. Stop the service (already stopped if right after ChatGPT); detached unit + sentinel, one DB at a time, **p0clone first**:
   `-u pb_training,pb_vendor_access --stop-after-init`; grep EXIT / Traceback and the two migration log lines (back-fill counts,
   "retired left-menu role gates — 1 entry checked, N role link(s) taken off"); then payobook, payobook_template, rize; stop at
   the first failure and restore that DB from its dump.
7. Asset ritual per DB (`orm_signaling_assets`, delete `/web/assets/%` attachments, bump `web.assets.version`); start; registry
   loaded; warm payobook / rize / p0clone with one curl; crons back to the snapshot (disable any new active one); versions =
   19.0.1.5.0 / 19.0.1.15.0 on all four; the three new switches present; Talent row no longer lists the training roles.
8. Demo data, **payobook only**, service stopped: `odoo-bin shell -d payobook < l1_demo_seed.py` (survey 17 validity 12 →
   back-fill stamps document 145; three DEMO certificates on two DEMO employees, registered; the morning job run once inside a
   rolled-back savepoint and its counts reported — expected: no renewal course for document 145, it is not inside 60 days).
   Restart, warm.
9. Live Chrome walk on payobook.com (T15): Certificates register (tiles, filters, Verify, Add with a real PDF, Download),
   Overview headline + chip, Numbers tiles, My learning "My certificates", wallet upload, **the learning-record PDF download**
   (first time it is produced for real), VI rail labels, console clean. **Sign-in:** my safety rules do not let me enter a
   password on a production site, even one I am given (NAV ledger P1 hit the same wall). So the live walk needs browser tabs
   that are already signed in as the QA admin, the HR lead and the learner (the owner signs in, I walk), or it becomes an owner
   step; everything server-side (versions, migration logs, register counts through the shell) I verify myself.
10. DONE line, release the lock, ledger rows LN16+, final report.

## 9. Deploy record (GO DEPLOY 10:12 UTC)

| Step | Result |
|---|---|
| Notes / lock | ChatGPT DONE 10:11; my START 10:12 written before any change; lock held by a detached `flock` unit until the DONE line |
| Versions before | pb_training 19.0.1.4.1, pb_vendor_access 19.0.1.14.0 on all four (nobody had shipped L1) |
| Backups | `/odoo/backups/learning-l1-20261021/` p0clone 24.9 MB, payobook 76.5 MB, payobook_template 24.7 MB, rize 32.9 MB (each `pg_restore -l` ok) |
| Files | `git archive HEAD` (741728d68) → clean `/tmp/deployL1` → per-module `rsync --delete`; tree hashes equal; PO gate 390 rows / 0 empty code rows |
| Upgrade | detached unit, p0clone → payobook → payobook_template → rize: **EXIT=0 ×4**, 0 tracebacks; registry 17–23 s each |
| Migrations | Talent: "1 entry checked, 3 role links taken off" on every DB. Back-fill: payobook 2 test + 3 claim rows, 5 linked, 0 stamped; others 0 |
| Demo seed (payobook) | survey 17 validity 12 → 2 test certificates stamped (doc 145 valid until 16 Sep 2027); docs 162 (forklift licence, 20 days, Joiner Mai 20208), 163 (first aid, 75 days, Joiner Khanh 20209), 164 (pesticide permit, expired 10 days ago) registered on the demo register; morning job test run (rolled back): 0 renewal courses (doc 145 is not inside 60 days), 1 certificate reminder would have gone; 0 mails / 0 assignments left behind |
| Assets / start | signal + `/web/assets/%` deleted + version bump on all four; one odoo-bin; service down ~140 s (10:13:55–10:16:10) |
| Warm | payobook.com 200, rize 200, p0clone 200 (template has no public host) |
| Crons | 26 / 37 / 0 / 69 = snapshot. On payobook_template the dependent-module reload re-activated 5 shipped crons (pb_vendor_access vendor alerts 51, hiring 67/68, training 72/73) — switched back off |
| After | versions 19.0.1.5.0 / 19.0.1.15.0 ×4; three switches present ×4; LIC category ×4; register rows payobook 8; no training-only role on Talent ×4; 0 ERROR lines since restart; `/web/health` 200 |
| DONE | 10:17 UTC; lock released |

### Live walk (Fable, payobook.com, HR lead, 21:25 AEDT) — PASSED
Learning rail nine items incl. CERTIFICATES; register "8 certificates. 1 expires within 30 days, 1 has expired." with the six
tiles (1 / 1 / 2 / 1 / 4 / 3), department and job filters and the table; Numbers shows the four new tiles;
`/my/training/record.pdf` returns a real PDF (200, application/pdf, 149,583 bytes, `%PDF-1.4`) — the first one produced, closing
§2's local gap; `/my/training/certificates` renders with the upload form; no console errors.

One nit found: the wallet's browser-tab title read "My certificates (ESS)" (internal jargon) — fixed in §10.

## 10. Follow-up after the walk

- **Tab titles** (`f7182ccde`): the website layout uses the QWeb view's name as the tab title unless the page sets one, so all six
  `/my/training` pages showed "… (ESS)". Each page now sets its own title — My training, the course name, the lesson name, My
  team's training, My training allowance, My certificates (Vietnamese "Chứng chỉ của tôi") — and the view names lose the suffix.
  Checked locally: "Chứng chỉ của tôi | BizApp", "DEMO Forklift refresher | BizApp", "Forklift refresher — lesson 1 | BizApp".
  pb_training suite unchanged (only the two known old failures). Bumped to 19.0.1.5.1. **Not deployed** — the coordinator scoped
  this turn to commit only; it rides the next pb_training upgrade (likely L2's deploy, which must therefore carry 19.0.1.5.1+).
- The same "(ESS)" tab title appears on portal pages in about ten other modules (employee home and payslips, expenses, trips,
  project time, goals, hiring, equipment, pay and awards, leaving, improvement plans) — ledger LN23; not Learning's to change.
- Ledger rows LN17–LN25 written (bulk access stamp, the dependent-module cron re-activation, vault verify, home-card registry,
  OrderedSet in search methods, `env._`, tab titles, import-time refusal words, ops notes).
