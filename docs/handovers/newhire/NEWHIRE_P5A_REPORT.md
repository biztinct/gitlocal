# NEWHIRE P5a — report (languages, lessons, ready-to-merge)

Built on worktree `gitlocal-worktrees/newhire` (branch `newhire`), 2026-11-25. Not pushed, nothing deployed, no server access.
Test DB `nh8_m` = copy of `nh3_base` + the merge + `-u pb_new_hire,pb_learn` (and the upstream-changed modules). Walk DB
`nh6_base` (P4 walk world) upgraded to this code; vi_VN and id_ID were already active there. "Without the studio" DB `nh9_y`
= copy of `nh3_base` with `pb_new_hire` uninstalled (NH67).

## 0. Merge notes (handover §1)

`git merge origin/19.1` → merge commit `975ad290c`. 28 upstream commits (WFSETUP P6–P10b, workspace settings, 239 files).
**No conflicts**: upstream touched no file this branch changed. `pb_hr_payroll_formula` changed on both sides in different
files (upstream: clock source, provenance, its `.po`, manifest 19.0.1.169.1 → 19.0.1.170.0; ours since P1:
`contract_fill_in.py` factor-out, never bumped) — the manifest stays at upstream's 19.0.1.170.0, no bump of ours needed
(our change is Python only). No manifest that we bumped was bumped upstream.

| Run | Before (pre-merge, P4) | After the merge |
|---|---|---|
| `pb_new_hire` full suite | 112 / 112 (P4, `nh5_b`) | **112 / 112** (`nh8_m`, merge commit) |

## 1. What was built

`pb_new_hire` 19.0.1.4.0 → **19.0.1.5.0**; `pb_learn` 19.0.20.8.10 → **19.0.20.9.0**.

| Part (commit) | Files |
|---|---|
| §6 P4 follow-ups (`1c2cc4b46`) | `models/hiring.py` (buddy context + `_hand_over_buddy` override; `_bank_reader_on`; no-reader bank row; identity `received_until`; `hiring_valid_until` check and value; `_file_copy(expiry=)`; "Bank paper" title), `models/studio.py` (draft key), `static/src/js/new_hire_studio.js` (draft key), `step_docs.js` (bank Ask / I have it when nothing reads papers; the date box), template + scss (the date box), `tests/test_hiring.py` (F1–F3) |
| §2 languages (`f167da9fe`) | `i18n/pb_new_hire.pot`, `vi_VN.po`, `id_ID.po`; `models/ask.py` (`label_kind`, `_labels`, `item_label`, page-batched words), `docs_legs.py` / `studio_docs.py` (the `kind` of each ask; `_bank_options` skipped for words), `invite.py` (`_lang_of`, email in the person's language, HR note in the HR person's), `data/mail_template.xml` (`lang` from `ctx['pb_nh_lang']`), `controllers/welcome.py` (translated title), `migrations/19.0.1.5.0/post-migrate.py`, `tests/test_p5a.py` |
| §3 lessons (`29d8dd528`) | studio template (12 `data-coach` anchors); `pb_learn/static/src/anchors.json`, `static/content/learn_content.json` (generated), `static/src/engine/screens.js` (replica), `fixture.js` (generated), `tests/test_scenario.py`, `__manifest__.py`; `docs/tutorial_poc/author/data.js`, `practice-data.js`, `contract.json`, `tools/replay_tests.py`; `pb_people/learn_manifest.py` (comment) |

### 1.1 Languages as built
- The template was exported with the product's own exporter (`odoo-bin i18n export -d nh8_m pb_new_hire`), so every entry
  carries `#. module:`, `#. odoo-python|odoo-javascript` and `#: code:addons/pb_new_hire/…:0` (or `model:` / `model_terms:`).
  Header made neutral ("Payobook") so the whole files can be scanned for the vendor word.
- Translations: six parallel passes (3 chunks × 2 languages) against one fixed glossary built from the product's existing
  `.po` files and Learn's terms, each checked by a script (placeholders, markup, vendor word, emoji, edge whitespace), then
  read on screen. One wording fix after the walk: "the hire" had become "hồ sơ tuyển dụng" (a recruitment file) in 11
  Vietnamese sentences → "hồ sơ nhân viên mới" / "nhân viên mới".
- **Asked items in the reader's language (P3b question 1, decided)**: a row keeps its item `key` and a new `label_kind`
  (`item` = the row's own words, `card` = a card whose number HR typed, `number` = a card that came across from Hiring).
  `pb.new.hire.ask._labels()` works the words out from step 5's own list (`_detail_items`) in the reader's language — one
  list per (country, company) for a whole page, so the New joiners board stays one batched read (V10 caught a per-person
  version during the run). The stored `label` is only the fallback for an item no longer listed; a paper falls back to its
  plain name first. Migration 19.0.1.5.0 marks old rows by comparing their stored words with the list in every installed
  language (only `id_number` / `tax_number` can differ).
- **Emails**: the welcome message and reminders are written in the person's language (sign-in's, else the employee
  record's): the template's `lang` reads `ctx['pb_nh_lang']`, the items and the need words are built in that language. The
  chatter note and the sender's own answer stay in the sender's language. The HR note 3 days before day one is written in
  the HR person's language.
- **Shared-module strings added in P1/P2**: none. The three `via` sentences in `pb_scheme_map` were moved unchanged by the
  P1 factor-out and are not shown by the studio; `pb_scheme_map` has no translation files at all (pre-existing).

### 1.2 Lessons as built
- Anchors: `nh-rail`, `nh-sources`, `nh-step-who|role|pay|sched|docs|welcome|check`, `nh-record`, `nh-example`, `nh-send`
  — registered in `anchors.json` `product` (screen `newhire`, `reserved: true`: no lesson points at them yet), the studio
  template added to the scanned templates.
- `pe-head`'s description, the `addperson` answer and `sc_people` rewritten for the seven-step screen (three required steps,
  the team decides the pay scheme, the rest already answered, a second person approves, bank asked in the welcome link).
  The practice lesson is now 6 steps: open → name → team → wage (a number input, either thousands mark) → Send (guarded)
  → roster. The replica draws the rail's seven names, the three required steps' decisive field each and Check and add's
  Send; it says plainly that it is a practice copy drawn under the roster.
- Generator: `pb_learn/i18n/vi_VN.po` backed up first; the generator left it untouched this time (1,108 lines before and
  after, byte-identical). `--check` is clean. 28 + 19 English/Vietnamese pairs written (data.js + replica).
- Learn has no Indonesian (bilingual en/vi leaves by design) — NH70.

### 1.3 The old window's dependants (§4)
| Dependant | What it gave the old window | Through the studio |
|---|---|---|
| `pb_pay_scales/models/joiners.py:86` (+ `PbContractWizardScales`) | `pb_scale_pin_reason` passed by context; an empty wage filled from the scale; `place_new_contract` | same `create_employee` / `create_contract` chain (P1 T09: wage from the scale, contract placed; T7b: the keys still travel) |
| `pb_pay_scales/static/src/xml/joiner_hint.xml:41` (+ `joiner_hint.js`) | the pay-scale hint line on the old form | dead under the takeover by design; the studio calls `joiner_suggest` itself (`pay_hint`, step 3) — T7b |
| `pb_orgchart/models/onboard_fill.py:20` | `fill_job_id` lowers the role's to-hire count on the real create | `fill_job_id` is a draft key; lowered once, on approval (P1 T10) |
| `pb_orgchart/static/src/js/orgchart_edit.js:360` | opens `pb_onboard_wizard` with manager / team / job prefilled | the takeover passes `params.prefill` to `load()`; T7 and walk W5 (team + manager filled, no job from a manager's menu) |
| `pb_updates/models/updates_joiners.py:824` | `create_employee(vals)` with the old keys, `NEWHIRE_WRITE: False` | no `pb_nh` key → straight to `super()`: no leg, no ask row, no reminder flag — T7c |

No gap found, so nothing new was built for §4. Without `pb_new_hire` the old window keeps working: T8 (registration
untouched, the takeover only in this module's assets, no dependant depends on the studio) + walk W-T8 on `nh9_y`.

### 1.4 §6 follow-ups as built
- **Buddy**: `_leg_hiring_close` passes `pb_nh_buddy_chosen` = step 6 had a buddy; `pb.hiring.offer._hand_over_buddy`
  returns `'studio'` for that one call when the offer is being joined by the studio (`NH_JOIN_CTX`) and HR chose one.
- **Bank paper with no reader**: `_bank_reader_on()` = `payroll.ai.config.get_config_for_purpose('doc_ocr')` for the
  company (feature-checked) — exactly what the bank screens and the reading itself use (note: that lookup falls back to ANY
  active AI setting). No reader → row default Ask, choices Ask / I have it, sentence "<First>'s bank paper will be on their
  record. The account details are asked for in the welcome link."; the leg files the paper as "Bank paper" (Other papers).
- **Identity card**: the matched row shows "Valid until (optional)" when the ID category needs a date; a date that has
  passed is refused in step 5 with its fix; with a date the card is filed in "ID Document" with that expiry.

## 2. Results

### 2.1 Numbered tests
| # | Test | Result |
|---|---|---|
| T1 | PO parse gate (`PoFileReader`) both languages; 947 / 947 msgids each; placeholders and markup identical; three loading markers on every entry; `Language:` header | pass |
| T2 | no vendor word in the `.pot` / both `.po` (whole files, the two markers aside), any msgstr, any Python message, the mail template, the welcome page | pass |
| T3 | SG / ID / VN paper names in vi and id; the stored jsonb carries vi; step 5 for a vi HR officer (personal details, bank, the card); a plain name in vi | pass |
| T4 | English maker + English approver; the person reads vi: `/my/welcome` cards, home row, summary in vi (and id); the board for English HR in English; the card-only row reads the card | pass |
| T4b | an item no longer listed keeps its stored words; a paper keeps its plain name in the reader's language | pass |
| T4c | the 19.0.1.5.0 migration marks a card row (English words and Vietnamese words), leaves an item row | pass |
| T5 | welcome email for a vi sign-in: subject and body Vietnamese, items in vi, no "Get started"; the sender's answer English; a reminder for an id sign-in in Indonesian | pass |
| T5b | the HR note for an Indonesian HR person: summary and sentence in Indonesian | pass |
| §5 | reminders with every mail server off: nothing queued for the person, nothing written on them, no error | pass |
| T6 | `pb_learn` suite (in the neighbour run, §2.2) | see §2.2 |
| T7 | org chart prefill (role and manager menus); pay-scale hint and keys; Updates sheet call untouched | pass |
| T8 | old window registration untouched; takeover only in this module's assets; no dependant depends on the studio | pass |
| F1 / F1b | buddy: HR's choice wins at the close; empty step 6 → Hiring's buddy | pass |
| F2 / F2b | bank paper without a reader (Ask default, sentence, paper filed, no bank request); with a reader P4 behaviour; the real probe off / on | pass |
| F3 | ID card: date filed with its expiry, leg green; past date and bad date refused in step 5 | pass |

**`pb_new_hire` full suite (final code, `29d8dd528` + this docs commit)**: **130 / 130, 0 failed, 0 errors** (520 s,
`nh8_m`). P4 was 112; +18 = F1–F3 (5) and test_p5a (13). One earlier run of the same suite caught V10 (the board read
the step 5 list once per person) — fixed before the commits; one run was interrupted from outside mid-way and re-run.

### 2.2 Suites of every module touched or extended (before = merge commit code, after = P5a)
Modules `/pb_people_advanced, /pb_hiring, /pb_updates, /pb_onboarding, /pb_me_portal, /pb_lifecycle, /pb_people,
/pb_learn, /pb_orgchart, /pb_pay_scales` on two fresh copies of `nh3_base`; "before" = the three modules P5a changes
(`pb_new_hire`, `pb_learn`, `pb_people`) from `975ad290c` placed first in the addons path (NH66).

| Run | Tests | Failed | Errors |
|---|---|---|---|
| before (`nh9_a`) | 1,603 | 19 | 8 |
| after (`nh9_b`) | 1,603 | 17 | 5 |

**No new failure**: every one of the 22 after is also in the before list, with byte-identical messages for the Learn checks
that P5a's files feed (anchor registry "stray anchors" — same list, no `nh-*` entry; guide truth `02` / `02b`; LearnrevP4
practice copies: the "Tax returns" govreports column). The 5 that failed only before (two provider-elevation tests, a
Learn hub config test, two Learn node suites) passed after — run-order / timing noise, not caused by P5a. The rest are
pre-existing: Hiring privacy / interviews / stages / numbers / joining, My Payobook home cards and source, portal-only
doors, client review, registers, composer.

Learn authoring checks: `gen_learn_data.py --check` clean; `test_scenario_rules.py` 20 refusals + 1 acceptance;
`test_step_shape.py` 0 failed; `check_contract.py` the same 3 pre-existing failures before and after (govreports country
catalogue), anchor lint 313 → 314 referenced, all present; `replay_tests.py` fails to import identically before and after
(`odoo.addons.pb_learn.models._brand`, pre-existing).

### 2.3 Browser walks (Claude-in-Chrome, local; Chrome's own page translation switched off per page, NH61)
| # | Walk | Result |
|---|---|---|
| W1 | whole studio in Vietnamese (`nh6_base`, Lina Hartono from Hiring): scripted scan of every step's text, tooltips and screen-reader labels + the papers drawer → no English of ours. English left = data of other modules: the joining checklist's step names (`pb_onboarding` seed data has no Vietnamese at all), a company's own field help, the scheme's line names | pass |
| — | found during W1: the bank row from Hiring with no reader showed only "Came across" (no Ask / I have it) — **fixed** (`step_docs.js`); "hồ sơ tuyển dụng" wording — **fixed** | fixed |
| W2 | the same in Indonesian; at a 340 px studio root with its narrow rules forced (NH45): `scrollWidth` 340 on all 7 steps, no clipped label; the step rail scrolls sideways on its own (`overflow-x: auto`, 1,409 px of chips) | pass |
| W3 | `/my/welcome` as Wulan in vi and id, two real 390 px frames: one column, `scrollWidth` 390, every card and line translated, browser title "Thông tin khi vào làm của bạn" / "Data bergabung Anda" (was the template's English name — fixed, NH72) | pass |
| W4 | lesson "Add your first employee" end to end in English (6 of 6, "End of the walkthrough") and Vietnamese (6 of 6; "9.500.000" accepted) | pass |
| W5 | org chart › Budi Santoso › Add a team member › A new starter › Open the form → studio (the P4 unsent draft question first: "Start Indonesia Operation") → team Indonesia Operation, manager Budi Santoso, country Indonesia filled, job empty | pass |
| W6 | console errors across W1–W5: none. Server log: one error, a missing file-store image of the copied walk DB (seen in P3b/P4), not this module | pass |
| W-T8 | `nh9_y` (studio uninstalled): no studio code in the bundle; People › Employees › Add employee opens the old three-step window (Orang / Role / Kontrak) → Create employee → "Sent for approval — Dewi Lestari" (the approver), reference NEW00388; the saved request carries the typed name "DEMO NH Old Window" | pass |

## 3. Self-review against the handover — deviations
1. **No Indonesian lesson text**: Learn's content is English + Vietnamese by construction; "add vi/id for every new lesson
   string" is met for vi only (NH70).
2. **Studio anchors are `reserved`**: the handover asked to register them with truthful texts; no lesson or answer points
   at them yet (the `addperson` answer still shows the Employees header, where the door is), so the registry's own rule
   requires `reserved: true`.
3. **The lesson keeps the `rep-newemp-*` names** for open / name and adds `team` / `wage` / `send` (replacing `div` /
   `save`), so contract checks and the bilingual-parity exemption for the typed name still apply.
4. **The stored `label` stays** on ask rows as a fallback (an item a company later took off its list); rendering is by key.
5. **Bank reader check = the product's lookup**, which falls back to any active AI setting, not only a document-reader
   one — mirrored on purpose (it is what decides whether the paper can be read).
6. **A received bank row without a reader offers Ask / I have it** (not Not needed: it is needed before the first pay).
7. **Two small fixes found on the walk**, inside this phase's scope: the bank row's choices (§6 bug) and the welcome page's
   browser title (a translation leftover).
8. The `.pot` header names Payobook instead of "Odoo Server" so whole files can be gated.
9. The P3b scripted approval and walk users were reused; HR's language was changed with the top-bar switch (NH63).

## 4. Design bar (ledger rule 4)
- **Hero moment — 8/10.** A Vietnamese HR officer adds a person in Vietnamese end to end, and the new person reads the
  same items in their own language on the phone page and in the email, whatever language HR wrote in.
- **Zero dead-ends — 9/10.** The bank paper with no reader now has a real choice and says what happens; a passed
  valid-until date says why and what to do.
- **Plain language — 8/10.** Glossary terms reused from the product; one mistranslation caught on screen and fixed.
- **Motion / keyboard** — unchanged from P4 (the new date box fades in like its row).

## 5. Ready-to-go-live checklist (for the deploy phase — not run)
| Module | Version (live → repo) | Installed on (payobook / payobook_template / p0clone / rize / sudima) | JS / SCSS (asset purge) | `noupdate` data | Scheduled jobs | Migrations | Writes on install to existing records |
|---|---|---|---|---|---|---|---|
| `pb_new_hire` | not installed → **19.0.1.5.0** (install) | none yet; D10: payobook only until the closeout | yes (backend + frontend bundles) | `data/papers.xml` (14 shipped paper rows) | **none** created; reminders ride on `pb_lifecycle`'s existing `cron_lifecycle_reminders` (off on payobook, on elsewhere); with email off they send and write nothing (test §5) | `19.0.1.3.0`, `19.0.1.5.0` — neither runs on a fresh install (`version` empty) | **none** — proven on `nh9_y`: 20 tables' counts and newest change times identical before / after `-i`, active jobs 41 → 41; the only new rows are the module's own (1 mail template, 14 paper rows, its screens / fields / rules) |
| `pb_learn` | 19.0.20.8.10 → **19.0.20.9.0** (upgrade) | all five | yes (`screens.js`, `fixture.js`, content JSON) | unchanged (`learn_tenant_slots.xml`, `learn_sidebar_item.xml` as before) | none new | none | none |
| `pb_people` | 19.0.1.3.5 → 19.0.1.3.6 (P2's bump; P5a only edits a comment in `learn_manifest.py`) | all five | P2 change is Python | — | — | — | none |
| `pb_scheme_map`, `pb_probation`, `pb_hr_payroll_formula` | no bump of ours (P1 Python-only factor-outs: restart, no `-u`); `pb_hr_payroll_formula` 19.0.1.170.0 is upstream's own bump (WFSETUP P10b) and ships with that work | all five | no | — | — | — | none |

Also for the deploy phase:
- Translations load only for languages ACTIVE on a database; check `res_lang` per database (the walk DB had vi and id).
- On an upgrade the shipped paper rows receive vi/id names automatically (NH71); nothing a company typed is overwritten.
- Purge `/web/assets/%` per database and restart after the JS (deploy contract step 6). Locally a browser that had
  already loaded the old wording kept it after a restart until its IndexedDB `localization` cache was cleared (NH62):
  on the QA walk after go-live, clear it (or use a fresh browser profile) before judging wording.
- No new dependency: every module `pb_new_hire` depends on is on all five databases (FACTS_ONBOARD §M3).

## 6. New gotchas
NH61–NH72 in the ledger: Chrome's page translation in walks; the browser's translation cache; the language switch; a
test's `with_user` has no language; a fixture named `id`; the full disk; the broken recipe base; the mail body as one
msgid; the Learn guard rule reads titles; Learn has no Indonesian; upgrades fill missing languages on `noupdate` rows;
`/my` page titles.

## 7. Open questions for the architect / owner
1. **Joining checklist step names** ("Choose their buddy", "Laptop and equipment"…) and equipment names are English on
   every database for Vietnamese and Indonesian users — `pb_onboarding` / `pb_assets` seed data has no translations.
   Translate those modules next (outside this module)?
2. **Learn in Indonesian**: the content format is English + Vietnamese only. Add Indonesian to Learn, or accept English
   lessons for Indonesian users?
3. **Languages per live database**: which of the five have Vietnamese / Indonesian switched on? Translations only load for
   active languages.
4. **Step 2's rail line** says "Team, job and country needed" even when the team and country are already filled (P1
   wording) — make it name only what is missing? (No behaviour change was allowed in P5a.)

## 8. Commits (not pushed)
- `975ad290c` NEWHIRE P5a: merge origin/19.1 into newhire
- `1c2cc4b46` NEWHIRE P5a: P4 follow-ups — buddy, bank paper without a reader, ID card valid-until
- `f167da9fe` NEWHIRE P5a: Vietnamese and Indonesian, asked items in the reader's language
- `29d8dd528` NEWHIRE P5a: lessons follow the screen — studio anchors, Add employee lesson and replica
- this docs commit (report, ledger NH61–NH72)

Local leftovers (not in git): DBs `nh8_m` (test), `nh9_a` / `nh9_b` (before / after neighbour runs), `nh9_y` (studio
uninstalled, then installed for the §5 proof), `nh6_base` (walk; maker's password and languages changed for the walk);
scratch `p5a/` (glossary brief, checker, `build_po.py` that rebuilds both `.po` from the `.pot` + `tr_vi.json` /
`tr_id.json`, the two template exports, install snapshots), `walk_p5a.py`, `walk_y.py`, `mkdb.sh`, `base5/` (slim
before snapshot). Removed to free disk (NH66): superseded `nh5_a`, `nh7_a`, `nh7_b` and code snapshots `base`, `base3`.
