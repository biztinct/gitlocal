# DOCSTUDIO close-out — Stream L (lessons) — REPORT

Branch `docstudio-close-l`, cut from `origin/19.1` @ `95ba36ccf` (2026-11-26). Builder and tester:
Opus. Worktree `/Users/adity/Documents/GitHub/gitlocal-worktrees/docstudio-close-l`. Nothing
deployed, the live server not touched. Local database `docstudio_cl_base` (copy of `nh12_base`
+ `-i pb_report_builder,pb_excel_layout,pb_report_pdf,pb_me_letters`; the bridges auto-installed).

## 1. Lessons added (EN + VI)

Each lesson runs over a practice copy of its screen (`pb_learn/static/src/engine/screens.js`) and
every step points at an anchor laid on the REAL template, so the Coach can point at the live
screen too. Each lesson ends on the step that makes something (Save, Save layout, Save to
documents, Save look) and a check question.

| Key | Station (line) | Title | Steps | Practice copy |
|---|---|---|---|---|
| L43 | `reportbuilder` (Insights) | Build your own report | 6 | Insights › Build a report: Each row is, fields, column menu, filter bar / group, name, tools |
| L44 | `excellayout` (Insights) | Fill my own Excel layout | 7 | the button, its list, the set-up window (steps, their own sheet, fields, Try it / Save layout), Explorer's Send as |
| L48 | `reportpdf` (Insights) | Design the PDF of a report | 7 | PDF button, Design the PDF (look, Paper, Page, Columns, the real first page), PDF in my look |
| L45 | `docstudio` (Setup) | Design a letter | 8 | Settings › HR › Documents gallery, then the designer: fields, Show only when, preview with a real person, languages, Page, Save / Make a copy for… |
| L46 | `offerletters` (Lifecycle) | Offer letters and certificates | 6 | Hiring group card, the designer on an offer letter (Preview with · An offer, offer fields, candidate signature), the Hiring offer panel's language box, Certificates card |
| L47 | `contractdocs` (People) | Contract documents per country | 6 | the contract panel's Contract document button and the sheet: Sample wording line, the two-language paper, missing chips, Download PDF / Save to documents, Saved versions |

Seven practice screens: `reportbuilder`, `excellayout`, `reportpdf` (under Insights › Build a
report), `docstudio`, `docdesigner`, `offerletters` (under Settings › HR › Documents), `contractdocs`
(under People › Employees). Labels are the screens' own words; the Vietnamese is each module's own
`vi_VN.po` msgstr.

Paths: HR + Build a report, Design a letter, Offer letters and certificates, Contract documents;
owner + Build a report, Design the PDF (`pb_learn/models/learn_path.py`). My Excel layout is in no
required path (set up once by one person).

Anchors laid on the product templates (attribute only, no behaviour): `rb-*` (pb_report_builder),
`xl-*` (pb_excel_layout), `pd-*` (pb_report_pdf, pb_report_pdf_send — `rp-` was already taken by
the Payroll Report), `ds-*` (pb_doc_studio), `dh-*` (pb_doc_studio_hiring), `dm-*`
(pb_doc_studio_me), `dc-*` (pb_doc_contracts). 44 registered; `ds-filter`, `ds-paper`, `pd-look`,
`dc-head`, `dc-note` are `reserved` (laid, no step points at them yet).

## 2. Existing lessons, anchors and replicas the department's screens touched

| Screen changed | What Learn had | Changed |
|---|---|---|
| Insights tabs (new "Build a report") | Insights orientation (hub_insights tabs) and the practice Insights tab strip | tab line added; practice tab strip has Build a report |
| Settings › HR (new Documents card) | Settings orientation "HR" line, practice Settings › HR cards | HR line names Documents; `documents` category line; practice card |
| Explorer head (My Excel layout, PDF) + Send regularly (Send as) | Explorer replica draws no toolbar buttons and no drawer; L36 never names them | nothing to change; L44 / L48 teach them |
| Hiring offer panel (language box) | Hiring role replica draws no offer panel; no lesson names Which letter | nothing to change; L46 step 5 teaches it |
| Contract panel (Contract document) | contract drawer replica draws no Next step row (A2 report §2 test 19) | nothing to change; L47 teaches it |
| My Payobook certificates | no Learn lesson covers My Payobook certificates | nothing to change; L46 step 6 covers the designer side |
| PayAI (Ask) | lesson whitelist + product facts | L43–L48 whitelisted, offered, and three fact lines (Documents, Contract document, Build a report / Excel layout / PDF); "My Payobook" written through the brand slot (`%(brand)s`) |

## 3. Tests vs baseline

Baseline on the same database before any change: pb_learn **422 tests, 4 failed + 1 error** =
the known five (anchor registry 05 stray anchors of other modules, composer 03b, guide truth 02 /
02b, learnrev P4 c1).

| Run | Result |
|---|---|
| pb_learn after (first run) | 4 failed + 1 error known **+ test_bundle 06** (L48 step 1 "PDF." identical in both languages) → fixed (`ea92e0042`) |
| pb_payroll_ai_insights | first run: known test_egress 04e **+ prompt_branding 02 / 04** ("My Payobook" literal in my fact line) → fixed (`brand` slot); re-run: **132 tests, 1 failed = the known 04e** |
| pb_learn + the eight studio suites, final code | see §3.1 |
| Stray anchors list (registry 05) | byte-identical to baseline: no `rb/xl/pd/ds/dh/dm/dc` entry |
| `gen_learn_data.py --check` | clean; `pb_learn/i18n/vi_VN.po` unchanged by the generator (md5 before = after) |
| `test_step_shape.py` / `test_scenario_rules.py` / `jargon.py` | 0 failed / 20 refusals + 1 acceptance / clean |
| `check_contract.py` | the same 3 failures as `origin/19.1` (c1 pe-filters, explorer-explains-why, govreports) — all in modules this stream did not touch; new pin `docstudio-lesson-anchors` passes; anchor lint 353 referenced, all present |
| node suites (guide panel, lesson panel, library) | 117 / 113 / 111 passed, 0 failed (library pin 44 → 50 stations) |
| Every step's anchor drawn by its practice copy (node, EN + VI) | 80 / 80 |

### 3.1 Final run
`-u` of all ten touched modules, tags = pb_learn + the eight studio modules: **572 tests, 6 failed
+ 1 error.**

| Suite | Tests | Result |
|---|---|---|
| pb_learn | 494 (422 post-install) | the known five only (registry 05 with the same stray list, composer 03b, guide truth 02 / 02b, learnrev P4 c1) |
| pb_report_builder | 31 | 0 failed |
| pb_excel_layout | 29 | 0 failed |
| pb_report_pdf / pb_report_pdf_send | 21 / 5 | 0 failed |
| pb_doc_studio | 43 | 0 failed |
| pb_doc_studio_hiring | 22 | 0 failed |
| pb_doc_contracts | 23 | **1 failed: test_01_install_is_silent** — the "Employment certificate" template's change time (2026-11-26 00:50:49) is this copy's `-i pb_me_letters`, done AFTER pb_doc_contracts was installed on the source copy; the test compares template change times with pb_doc_contracts' install time. A local install-order artefact, not these anchors |
| pb_doc_studio_me | 14 | **1 failed: test_a1_12_portal_flow** — the certificate came back as HTML, not PDF: this Mac has no PDF engine (handover: PDF proof happens on the server) |

The two studio failures are environment-only (install order of the local copy; no PDF engine);
this branch changes only `data-coach` attributes and versions in those modules.

## 4. What was walked in a browser (Chrome MCP, local, own isolated browser context)

- All six lessons opened from their deep link, every step stepped through with Next, in English
  and then in Vietnamese: **40 / 40 steps — the anchor is drawn and the spotlight sits on it**
  (checked by rectangle, within 3 px). Vietnamese titles, four lines and the check question
  (L48) read in Vietnamese. Console: no errors, no warnings.
- Found and fixed in the walk: the spotlight was left 150–200 px below a control that needed a
  long scroll (L46 step 6, L48 step 7). Cause: the practice spotlight placed itself 190 ms after a
  smooth scroll started. Fix in `engine/spotlight.js`: place again at 700 ms, guarded so a later
  step's placement wins. Practice cards of Documents compacted.
- Real screens (local): Insights › Build a report carries `rb-top, rb-tools, rb-rowis, rb-fields,
  rb-bar, rb-table, xl-button, pd-button`; My Excel layout is grey with "Save the report first.".
  Settings › Documents carries `ds-hero, ds-filter, ds-group, dh-prints, dm-prints`; the offer
  letter's designer carries `ds-top, ds-fields, ds-langs, ds-toolbar, ds-paper, dh-sign,
  ds-preview`, the Page tab `ds-page`.

**Not walked in a browser:**
- `dh-with` on a real screen: the local administrator has no Hiring access, so the designer shows
  "You cannot see any offer." and draws no "Preview with" line (correct behaviour).
- The Hiring offer panel's language box (`dh-lang`), the contract panel and its Contract document
  sheet (`dc-*`): the local copy has no draft offer and 0 running contracts. These anchors are
  proven by the template pin (`check_contract.py` item `docstudio-lesson-anchors`) and the
  registry test, not by eye. Stream D should check them on payobook.com.
- Phone width; a non-administrator reader of the lessons.

## 5. Deviations

1. **No Indonesian lesson text.** Learn's content format is English + Vietnamese only (NH70,
   NEWHIRE P5a report §3). Every new learner string has EN + VI. The product strings the lessons
   quote already have vi + id in their modules; this stream added no product string (anchors are
   attributes), so no module `.po` changed.
2. **One engine change outside lesson content** (`pb_learn/static/src/engine/spotlight.js`, the
   re-placement above) — needed for the new long practice copies, benefits every lesson.
3. **Anchor prefix `pd-`** for the PDF designer, not `rp-` (taken by the Payroll Report).

## 6. Versions (deploy notes)

| Module | Before | After | Why |
|---|---|---|---|
| pb_learn | 19.0.20.9.0 | 19.0.20.10.0 | stations, lessons, practice copies, spotlight |
| pb_payroll_ai_insights | 19.0.3.13.1 | 19.0.3.13.2 | lesson whitelist + facts |
| pb_report_builder | 19.0.1.1.0 | 19.0.1.1.1 | anchors |
| pb_excel_layout | 19.0.1.0.0 | 19.0.1.0.1 | anchors |
| pb_report_pdf | 19.0.1.1.0 | 19.0.1.1.1 | anchors |
| pb_report_pdf_send | 19.0.1.0.0 | 19.0.1.0.1 | anchors |
| pb_doc_studio | 19.0.1.4.0 | 19.0.1.4.1 | anchors |
| pb_doc_studio_hiring | 19.0.1.1.0 | 19.0.1.1.1 | anchors |
| pb_doc_studio_me | 19.0.1.0.0 | 19.0.1.0.1 | anchors |
| pb_doc_contracts | 19.0.1.1.0 | 19.0.1.1.1 | anchors |

Assets change in all ten: purge `/web/assets/%` and restart. No data, no job, no mail, no
migration. **Merge note:** stream Z may bump some of the same manifests (pb_doc_studio,
pb_doc_studio_hiring, pb_report_pdf); keep the higher version and make sure it is above both.
Template lines changed here are single attributes on existing tags.

## 7. Design self-score ("extreme WOW, intuitive, out-of-this-world experience, best in class")

8/10. Hero: open a lesson and the practice copy of the new screen lights each control in turn,
in the reader's language, with the four lines naming exactly what the screen shows; the same
anchors reach the live screen for "Show me". Short of 10: no walkthrough (Watch / Try) for the
new screens yet; practice copies are drawn, not interactive (nothing typed or saved in them).

## 8. Left for later

- Walkthroughs (Watch / Try) for Build a report and the Document studio.
- Indonesian lessons (Learn has no Indonesian).
- A question / intent for "how do I change a letter's wording" (PayAI already routes to L45).

## 9. Gotchas (ledger rows)

- DS-L1 | The practice spotlight placed itself once, 190 ms after a SMOOTH scroll began; a control
  far down a tall practice copy was left with the hole where the control had been | place again
  after the scroll settles (700 ms), guarded per step (`spotlight.js`).
- DS-L2 | Anchor prefixes are global across the registry and `check_contract.py`: `rp-` already
  belonged to the Payroll Report | grep `anchors.json` for a prefix before choosing one.
- DS-L3 | `shellHTML(screen)` draws the shell only; a practice copy's body is `SCREENS[key]()` |
  render `SCREENS[key]()` to check a replica in node.
- DS-L4 | PayAI's product prompt is %-formatted with `%(brand)s`; "My Payobook" written literally
  fails `test_prompt_branding` 02 / 04 | write `My %(brand)s`.
