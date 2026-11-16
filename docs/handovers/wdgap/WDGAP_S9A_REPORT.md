# WDGAP S9-A — report: review forms

Branch `wdgap-s9a` (from `origin/19.1` @ abc2259b6). Built, tested and self-reviewed by the
implementation agent. NOT merged, NOT deployed. Owner rulings applied: P1, P2, C-3, C-5.

## 1. What was built

New module **`pb_review_forms`** (19.0.1.0.0). Everything is inheritance from it; the only
existing file edited is `pb_goals/__manifest__.py`.

| Item | What | Where |
|---|---|---|
| P1 one form per goal year | `pb.review.form` (unique per `pb.goal.cycle`) + `pb.review.form.line`. Parts: the goals score (from the sheet), up to **8 skills or values** (always rated, both sides), up to **8 HR questions** (rated / written / pick one of a list; answered by both, employee only or manager only; "must be answered"). Draft → "In use" (`action_publish` refuses with every problem in words: shares not 100, a share with nothing under it, choice with < 2 answers, missing "shown from" date, closed year). | `models/review_form.py`, `models/rf_common.py` |
| Five-point scale | The five words are pb_goals' own `RATINGS` ("Well below" … "Well above"), so the employee's and the manager's words are the goals words. | `rf_common.py` (imports `goals_common.RATINGS`) |
| The filled-in form | `pb.review.entry` (one per **existing** year-end `pb.goal.review` row — no second review object) + `pb.review.answer` (one row per line per side). States: own view todo/started/sent; manager todo/started/finished; shown on; read / wants to talk; PDF + filed document. **No employee or line-manager access right on either model**; HR (Goals administrator and up) may read, never their own (record rule). | `models/review_entry.py`, `security/*` |
| Employee first | My Payobook page `/my/goals/review/<id>`: steps 1 Your own view → 2 Your manager → 3 Read and confirm; rating pills, text, pick-list; "Save for later" / "Send to my manager" (all required lines checked; once sent it cannot change). Reached from a card inside the review row on `/my/goals` (xpath on `pb_goals.gl_year`; the old "say what you would like said" box is hidden on a form review) and from a **Needs you** row on the home ("Give your own view for your review"; later "Your review is ready to read"). | `controllers/portal.py`, `views/portal_templates.xml`, `models/me_home.py` |
| Then the manager | Goals drawer (OWL `patch()` of `PbGoalsBoard` + `t-inherit` of `pb_goals.GoalsDrawerYear`): a "Review form" panel on the end-of-year row with status chips; the employee's view beside each line (only once SENT), the manager's rating pills / answers, the **overall comment**, the overall result and its parts after each save; Save / Finish the review. Finishing without the employee's view asks first ("Finish without their own view?") and is recorded. The old "Write it up" button is hidden on a form review (not removed — QF4-W4). | `static/src/js/goals_drawer_patch.js`, `static/src/xml/goals_drawer.xml`, `models/facade.py` (`drawer_*`) |
| Then the overall comment | Required to finish; the goals must be scored when the goals share > 0. The review row is written up through its OWN `action_review_done` as the manager (state, frozen goals score and chatter line exactly as today). | `facade._finish` |
| Hide-until | "When the employee sees the manager's part": **as soon as the manager finishes** or **from a date HR chooses**. Before that the employee's page payload contains NO manager data at all; the review row's `manager_note` holds a neutral sentence (the real comment is copied at sharing); the goals score/marks are blanked on `/my/goals`, in the Goals drawer and on the Scores tab FOR THAT PERSON ONLY (an HR lead's own review included). Sharing happens: at finish (first mode), by a quiet daily job on the day, by HR's "Show them now", by the person opening their page after the day, or when the goal year is closed. | `goals_ext.py`, `review_entry._release`, `data/review_forms_data.xml` (job) |
| Acknowledgement | "I have read this" and "I want to talk about it" (after sharing only). "Talk" opens an Ask HR question in the person's name (probe — no dependency) whose text says only that they would like to talk about their review; nothing from the review is copied (every HR user reads Ask HR). | `facade.my_ack`, `_ask_hr` |
| PDF filed | At sharing: one review rendered per call (`ir.actions.report` on the entry, no `pb.hr.letter` row), attached and filed in the employee's documents under a new category **"Performance review"** (data, `noupdate`). The employee downloads it through `/my/goals/review/<id>/pdf` (ownership proved, never `/web/content`). A PDF that cannot be made never un-shares the review (savepoint, warning in the log, retried on download). | `review_entry._file_pdf`, `report/review_form_report.xml` |
| Locked after the first review | The first own view sent or the first manager finish stamps `locked_at`; from then on lines, shares, name and intro are refused (model `write`/`create`/`unlink` guards), only WHEN it is shown may change; "Stop using it" is gone. New version = "Copy to another goal year". | `review_form.py`, `facade.studio_copy` |
| HR builder + preview | Settings › HR › **Review forms** (own category key `reviews`, group `hr`) and ⌘K row (probe `pb.review.forms.can_open`): goal years on the left (status chip, lock icon), a guided five-step screen (The result · Skills and values · Questions · Showing it · Check and use), every "Next" saves, "Add the company values" (probe of Praise values), a quiet progress strip (grey at zero; amber-free, indigo only where something waits: "Waiting to be shown", "Want to talk"), "Show them now", "Preview as the employee" (the real employee page on an unsaved entry, nothing saved, HR only). Writing needs **HR lead for goals**; Goals administrators can look. | `static/src/js/review_forms_studio.js`, `static/src/xml/review_forms_studio.xml`, `static/src/scss/*` |
| P2 pay | `pb.goal.set._pay_score()` overridden: in a goal year whose form is IN USE (and the sheet is scored at year end) it returns the **overall review result** = Σ share × part ÷ Σ shares, parts on 0–5 (goals score; average of the manager's skill ratings; average of the manager's rated questions); the employee's own ratings never count. Unfinished → `None` (skipped, never 1). `_freeze()` adds `review_basis`, `review_overall`, `review_parts` to the frozen year, so the close stamp and a closed year's pay reading use the frozen overall. **No form in use → `super()` untouched** (golden tests). A review written up the old way before the form went into use stays on goals. | `models/goals_ext.py` |
| Translations | `i18n/pb_review_forms.pot`, `vi_VN.po`, `id_ID.po`: 298 entries each, all translated, exported with `odoo-bin i18n export` (three markers per entry), header "Payobook 19.0". | `i18n/*` |

### pb_goals (the only out-of-module edit)

`pb_goals/__manifest__.py`: the Apps text no longer says "any link to pay … not here" (S9-F8);
a bullet says the year's scores reach the pay review and that a review form in use makes the
pay review start from the overall result. Version **19.0.1.5.0 → 19.0.1.5.1**.

## 2. Tests

Local database `wdgap_s9a_t` (copy of `upd_p6_t_tpl`, `-u all` with the branch tree), own
port 8957, own browser hosts (`s9a.localhost`, `worker.s9a.localhost`, `mgr.s9a.localhost`
— see gotcha S9A-1). Dropped afterwards with its filestore.

Command: `odoo-bin -u pb_review_forms --test-enable --test-tags /pb_review_forms`.
**38 tests, 0 failed, 0 errors** (see §2.2 for the full-suite run).

| # | Case | Test | Result |
|---|---|---|---|
| 1 | One form per goal year (database refuses a second); a DRAFT form changes nothing (not applied, pay score = base) | `TestForms.test_01_*` (2) | PASS |
| 2 | The five words are pb_goals' `RATINGS`; a rating outside them is refused | `test_02` | PASS |
| 3 | 9 questions / 9 skills refused, 8 accepted; publish refuses shares ≠ 100, a pick-list with one answer, a dated reveal with no date; share > 100 refused; only the HR lead writes (Goals administrator and a line manager refused; administrator may look) | `test_03_*` (3) | PASS |
| 4 | Employee first: draft allowed, send needs every answer, nothing after sending; manager finish refused until the own view is sent unless "without it" (recorded); overall comment and every manager line required; goals must be scored; the review row is written up with the comment and the goals score frozen on it; the manager does not see a DRAFT own view; the drawer row says it is a form review | `TestFlow.test_04_*` (6) | PASS |
| 5 | Hide-until (date): the employee's payload has no result, no manager words, nothing of the comment; review row note neutral; `/my/goals` reviews and score hidden; drawer marks blank for the person; `drawer_form` for the person = "your own page"; nothing filed; manager sees it. The day comes → job shares 1 (0 before); show-now; closing the year shares; "as soon as the manager finishes" shares at once; an HR lead never sees their own early (facade AND ORM rule) | `TestShowing.test_05_*` (6) | PASS |
| 6 | Acknowledgement refused before sharing; read; talk → Ask HR question in the person's name with no review words; another person refused | `test_06` | PASS |
| 7 | PDF made and filed under "Performance review" for the person; the file holds the comment; download for the person only | `test_07` | PASS |
| 8 | First sent review locks: line edit, share edit, "Stop using it" refused; a locked form still takes a new "shown from" day and nothing else; copy makes next year's draft with the same lines | `TestLockAndPreview.test_08_*` (2) | PASS |
| 9 | HR preview as the employee: the page payload, editable, NO row written; refused to an employee | `test_09` | PASS |
| 10 | P2: 70/30 → overall 3.85 from goals 4.0 and skills 3/4; unfinished → None; rated questions with a share (50/25/25 → 2.88); close freezes `review_overall`, keeps the goals `score`, stamps the employee's latest score from the overall (4); a review written up before the form stays on goals | `TestPay.test_10_*` (4) | PASS |
| 11 | **Golden, no form:** `_pay_score` equals pb_goals' own function on open scored / unscored / closed sheets, no `review_basis` in the frozen year; `/my/goals` reviews + scores, drawer review rows + scores, Scores tab equal pb_goals' own functions (employee and manager); **pay review "Read scores from Goals"** dry run on a closed and an open year identical (JSON) with and without the override, also with a draft form present | `test_11_*` (2) + `TestPayReviewGolden.test_11` | PASS |
| 12 | **Real portal login** (HttpCase): own page 200 with the form; another person's review → redirect, no content; sending through the page's own POST (CSRF) works; a crafted POST on another person's review changes nothing; ORM search on entry / answer / form refused for the portal login AND a plain internal employee; another person's PDF → redirect; after finishing the page shows "I have read this" and the comment; `/my/goals` shows the card; a portal login cannot open HR's preview; HR can | `TestPortal.test_12_*` (2) | PASS |
| 13 | Silent: without a form nothing is made by opening pages, the job returns 0, no Needs-you row; the sharing job queues no mail | `TestQuiet.test_13_*` (2) | PASS |
| 14 | Needs-you rows through the real pb_me_portal hook chain (super() of every Step 6 module) | `test_14` | PASS |
| 16 | Drawer form: a stranger refused (read and save); Goals administrator reads, cannot edit or save; HR lead edits; the person cannot save the manager's part | `test_16` | PASS |
| 17 | Every `.pot` msgid has vi and id; no vendor word in any msgstr, template, report or JS string | `TestStatic.test_17_*` (2) | PASS |
| 18 | Install is silent (measured on the local copy): mail queue 0 → 0, activities 0 → 0, documents 0 → 0, forms/entries 0; one new job (16:45 UTC daily, `noupdate`, quiet); the only new messages are the standard "Scheduled Actions created" notes on the job record | manual (psql before/after) | PASS |
| 19 | Static gates: `py_compile`, XML parse, manifest parse, PO gate (`PoFileReader`, placeholders kept, `module:` marker, 181 code rows reach a screen per language), vendor-word grep | `scratchpad/s9a/static_gate.sh`, `po_gate.py` | PASS |
| 20 | Browser walk (Claude in Chrome, local copy, own hosts): HR builds a form in the five steps (company values added, a written question, date reveal, intro), puts it in use (progress strip grey at zero), previews as the employee; the portal worker sees the Needs-you row, opens the form, rates, sends ("Sent to your manager…", step 2); the manager opens the drawer, sees the employee's view beside each line, rates, writes, saves (overall 3.94 = 0.7×4 + 0.3×3.8) and finishes ("Finished. They can read it from 12/20/2026."); the worker's `/my/goals` shows no score and no comment, only "You can read it from 12/20/2026."; HR presses "Show them now" ("1 finished review is shared now."); the worker sees the result, presses "I have read this", then "I want to talk about it" → their Ask HR question; Settings › HR shows the Review forms card, which opens with "Back to Settings". Vietnamese and Indonesian pages fetched as HTML show the translated words. Console: 0 errors on every page. Two fixes from the walk: the screen now opens on the RUNNING goal year, and the "locked" note is one whole sentence with its date. | PASS |

### 2.2 Full suites vs baseline

Baseline (before any change, same database): `/pb_goals,/pb_me_portal,/pb_pay:TestQf4GoalScores`
→ 299 tests, **3 failed, 2 errors, all pb_me_portal, all pre-existing**:
`TestMeHomeCards.test_05_grid` (E), `TestPbMePortal.test_01_profile_change_flow_and_audit` (E),
`TestMeHomeCards.test_06_font` (F), `TestMeHomeSource.test_12_vi_po_parses_and_covers_the_new_words` (F),
`TestPortalOnlyDoors.test_t1_7_portal_only_person_is_bounced_to_my` (F). pb_goals 197 green,
pb_pay QF4 9 green.

After (fresh copy, `-u all -i pb_review_forms`, then `-u pb_review_forms,pb_goals,pb_me_portal`
with `/pb_review_forms,/pb_goals,/pb_me_portal,/pb_pay:TestQf4GoalScores`): **337 tests, 3 failed,
2 errors — exactly the baseline five** (`diff` of the two failure lists: identical).
pb_review_forms 38/38, pb_goals 197/197, pb_pay QF4 9/9, pb_me_portal 93 with the same five
pre-existing. The `-u all -i pb_review_forms` on the fresh copy logged no ERROR line; after it
the mail queue, forms and filled-in reviews were all 0.

## 3. Self-review against the handover

- Lane: new module only + `pb_goals/__manifest__.py` (description + version). No edit to
  `pb_lifecycle`, `pb_me_portal`, `pb_explorer`, `pb_pay`, `pb_pack_*`, `pb_employee_vault`,
  `pb_ask_hr`, `pb_rnr`. The pb_me_portal hook calls `super()` first (proved through the real
  chain of Step 6 modules in test 14).
- P2 only through `_pay_score` (and `_freeze`, so the close stamp follows); golden tests on the
  seam and on the pay review's reading.
- Portal: every employee read/write in `pb.review.forms` after `employee_id.user_id == uid`;
  the manager's part is not in the employee payload before sharing (not just hidden).
- White-label: no vendor word in any string, template, report, JS or msgstr (test 17).
- Design: cockpit page with back chip, Lucide icons from the shared set, locked palette, no
  gradients, quiet strip (grey at zero), phone-safe portal (everything wraps/stacks).

## 4. Defaults taken, deviations, and what was NOT done

- **The form is used at the END-OF-YEAR review only.** The half-way review keeps its written
  note as today (the screen says so). FACTS asked for "yearly appraisals".
- **A person whose review is not finished has no overall result** for the pay review (shown
  under "no score" there), even if their goals are scored. Mixing goals-only and overall
  results in one review would compare unlike things. Owner question 2.
- **The goals score is hidden from the person too** while their review is held back (date
  mode) — on their page, in their drawer and on the Scores tab. Closing the year shares
  everything (the year-end email tells them their score anyway).
- **Left for later (not in my lane):**
  1. The pay review's "Read scores from Goals" drawer still says "goals score" / "No goals
     score for this year" in a year with a form (pb_pay text; the numbers are right).
  2. No proper My Payobook TILE for the review page (C-3): it is reached from the review card
     on My goals and from the Needs-you row. A tile = a pb_me_portal `_TILE_ROWS` change.
  3. Existing pb_goals rights, not changed (would change years without a form): an employee
     login may WRITE its own `pb.goal.review` row through the API (`rule_review_portal` /
     `rule_review_mine` have write), and an employee with a FULL login can read the key-result
     marks through the API before the "shown from" day. The review form's own content is
     safe (separate model, no access right).
  4. The PDF was not rendered locally (this Mac has no PDF engine; the review was still
     shared and the failure logged once, as designed). It must be checked on the rehearsal
     clone: finish one demo review there and open the filed PDF.

## 5. Contracts other phases rely on

- `pb.review.forms` (AbstractModel): `studio_load/save/publish/unpublish/copy/values/show_now`,
  `drawer_form/drawer_save`, `my_form/my_save/my_ack/my_pdf`, `preview`, `needs_rows(emp)`,
  `can_open()`.
- `pb.goal.set._pay_score()` keeps its return shape (float 0–5 or None); frozen year gains keys
  `review_basis` ('form'), `review_overall`, `review_parts`.
- Routes: `/my/goals/review/<review_id>` (+ `/save`, `/ack`, `/pdf`),
  `/my/goals/review-form/<form_id>/preview`.
- Needs-you keys: `review_self`, `review_read`. Settings category key `reviews`. ⌘K id `review_forms`.
- Document category xmlid `pb_review_forms.cat_performance_review` (code `REVIEW`).

## 6. Deploy notes

- **Install** `pb_review_forms` (`-i`) on all five databases; **upgrade** `pb_goals` (`-u`,
  19.0.1.5.1 — manifest text only). Never abm.
- Tier: **risky** (new module with new access rules and a pay-review seam). Backups first;
  rehearse on a clone with jobs and mail off. Seam test with the S9-B/S9-C modules and the
  Step 6 modules on the employee home (Needs-you hook chain).
- New job "Review forms: share finished reviews on their day" (16:45 UTC, `noupdate`, no mail).
- Asset purge + restart (new backend and frontend assets). PO gate on the box after rsync.
- Rehearsal check: one finished review → the PDF in that person's documents opens.

## 7. Owner questions (plain words)

1. The finished review is filed as a PDF in the person's documents. Payroll staff can open
   every document there today, so they could read reviews too. Is that acceptable, or should
   performance reviews be closed to payroll staff (a small follow-up)?
2. In a year with a review form, somebody whose manager has not finished their review shows
   as "no score" in the pay review, even if their goals are scored. Is that right, or should
   the pay review fall back to the goals score for them?
3. The form is used only at the end-of-year review; the half-way review stays a written note.
   Do you also want the form at the half-way review?
4. Should the review page get its own tile on the My Payobook home? Today it is reached from
   "My goals" and from the "Needs you" list. (It needs a small change in the self-service
   module.)

## 8. Gotchas → ledger

| # | Gotcha |
|---|---|
| S9A-1 | Browser cookies are per HOST, not per port: signing in on `127.0.0.1:<my port>` was undone by another builder's server on `127.0.0.1` ("Logged into database 'wdgap_s8c_t', but dbfilter rejects it; logging session out"). **Fix:** walk on `http://<name>.localhost:<port>` (Chrome resolves every `*.localhost` to the machine) — a different name per login (`s9a.localhost`, `worker.s9a.localhost`) gives each its own session. |
| S9A-2 | pb_goals' facades hand sheets around as `sudo()` records of the CALLER's environment, but a test (or another module) may pass a sheet from a different user's environment. A "who is reading" check on the record (`self.env.uid`) then answers for the wrong person. **Fix:** ask with `sheet.with_env(self.env)` inside the facade. |
| S9A-3 | `pb.review.entry.new()` (an unsaved record) is enough to render the employee page for HR's preview: related fields through an empty review are empty, nothing is written. |
| S9A-4 | Local Macs have no PDF engine: `_render_qweb_pdf` raises "Unable to find Wkhtmltopdf" outside tests (tests get HTML). Anything that files a PDF must hold its own savepoint, and the PDF itself is checked on the server rehearsal. |
| S9A-5 | Odoo's `HttpCase` + a `TransactionCase` fixture class: `class T(Fixture, HttpCase)` works (MRO is valid, the fixture's `setUpClass` chain runs once) and avoids re-running borrowed tests. |
