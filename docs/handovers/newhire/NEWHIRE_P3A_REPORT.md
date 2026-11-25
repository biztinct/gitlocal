# NEWHIRE P3a — report (Details and documents: what is needed, who gives it)

Built on worktree `gitlocal-worktrees/newhire` (branch `newhire`), 2026-11-25. Not pushed, nothing deployed, no server access.

## 1. What was built

`pb_new_hire` 19.0.1.1.0 → **19.0.1.2.0**. New dependencies (all on the five live databases, FACTS_ONBOARD §M3):
`pb_employee_vault, pb_me_portal, pb_me_details, pb_me_tax, pb_bank_ocr, pb_employee_bank_panel`. First security files of the
module (`security/ir.model.access.csv`, `security/rules.xml`) and first data file (`data/papers.xml`, noupdate).

| Layer | Files |
|---|---|
| Papers per country | `models/paper.py` — `pb.new.hire.paper` (category, country_code, need, label, sequence, company_id, active; unique index on category+country+COALESCE(company)); `for_country`, `display_label`, editor gate. Seeds ID/VN/IN/SG/MY |
| Ask rows | `models/ask.py` — `pb.new.hire.ask`, `refresh()`, `summary(employee)`; HR read/write, own user read (record rule), company rule |
| Step 5 facade | `models/studio_docs.py` — `details_options`, `_detail_items`, `papers_edit_load/save/reset`, `_validate_docs`, `_values_docs`, `_check_value`, `_file_problem`, `_papers_tile` |
| Legs + holding | `models/docs_legs.py` — legs `details`, `papers`, `asks`; bank outcome as a leg row; `pb.newhire.proposal.pb_nh_files` (Json) + hold/drop on withdraw/reject/return; `_apply_employee` names its proposal for the papers leg; drawer rows; `pb.contracts._cd_unmask_wage` context override (letter) |
| Changed P1/P2 files | `studio.py` (`send(draft, files)`, DRAFT_KEYS `items`/`have`, real `has_bank` fact, papers tile in `decides`), `welcome_legs.py` (LEG_ORDER, three sentences, letter leg context), `studio_welcome.py` (letter switch-off removed, timeline `role`) |
| Client | `step_docs.js` (new: `StepDocs`, `NhDrawer`), `new_hire_studio.js` (keys, files in memory, rail, sendable), `studio_util.js` (doc helpers), `record_panel.js` (Who does what, bank line), `step_check.js` (row, warnings, lines), `step_role.js` (Papers needed tile), xml, scss |
| Tests | `tests/test_docs.py` (D1–D11, 15 tests); `test_welcome.py` W10c rewritten to the new letter rule |

**Files touched outside `pb_new_hire`: none.**

### 1.1 The exact field written per item, per country (the details leg, on `hr.employee`)

| Item | ID | VN | IN | SG | MY |
|---|---|---|---|---|---|
| Personal details | `birthday, sex, private_street, private_city, private_phone` | same | same | same | same |
| Emergency contact | `emergency_contact, emergency_phone` | same | same | same | same |
| ID number | `identification_id` | `identification_id` **+ `vietnam_citizen_id`** | `identification_id` | `identification_id` **+ `singapore_nric_fin`** (when that field exists — not on the walk DB) | `identification_id` |
| ID card (merged) | vault doc, `cat_id_document` ("KTP (identity card)") | "Citizen ID card" | "Aadhaar card" | "NRIC or work pass" | "MyKad or passport" |
| Tax number | `pb_npwp_number` (+ NPWP card merged, `cat_tax_paper`) | `vietnam_tax_code` **+ running contract `vietnam_tax_code`** | `pb_in_pan_number` (+ PAN card merged) | — | — |
| Other tax kinds | `pb_id_ptkp_status` | — | `pb_in_tax_regime` | `pb_sg_shg_fund` | — |
| Numbers HR keeps | `pb_bpjs_employment_number, pb_bpjs_health_number` | `vietnam_social_insurance_number` | `pb_in_uan_number, pb_in_esi_number` | — | — |
| Bank | NOT written by the leg: `bank_name/account_number/account_holder` ride in the old keys; `_apply_employee` → `_pb_send_bank` → `_pb_hold_new_hire` (a bank change a second person approves, proposed by the maker) | same | same | same | same |
| Papers | one `pb.employee.document` per file via `pb.people.vault_upload_batch` (unverified) | same | same | same | same |

## 2. Results

### 2.1 Numbered tests (`-u pb_new_hire --test-tags /pb_new_hire`, local DB `nh3_base`)
**67 / 67 pass** (24 P1 + 28 P2 + 15 P3a; 66 in one full run, the icon test D11 added after and run with pb_people_advanced). `/pb_people_advanced` (incl. `test_fs16_newhire_bank`): **8 / 8 pass**.

| # | Test | Result |
|---|---|---|
| D1 | seeds per country (ID 4 rows in order, SG 2, VN 3, IN Aadhaar/PAN first); company row beats default (and keeps the usual label); inactive company row = not needed; another company keeps the usual list; back to usual | pass |
| D2 | HR officer: no link, load/save refused, no create; HR manager: company rows only where something changed, inactive row for "Not needed", shipped rows byte-identical, reset deletes company rows | pass |
| D3 | item keys/labels per country, ID card and tax card merged ("KTP (identity card) and number", "NPWP card and number", "PAN card and number"), VN tax code a detail, insurance not askable with the sentence (default Later), non-self-upload paper "Only HR can add this paper." (default Later), step 2 tile `{2 required, 2 optional, before first pay: KTP}` | pass |
| D4 | have without number → `have-identification_id`; number without file → `file-id_number`; skip bank refused ("needed before the first pay"); expiry required; text/plain refused with the vault sentence; >10 MB refused with the vault sentence; paper without file; HR-kept numbers empty; nothing proposed | pass |
| D5 | fast lane VN: identification_id + vietnam_citizen_id, tax code on employee AND contract, birthday, address, emergency, social insurance; legs ok. Bad NPWP / PAN refused at SEND with pb_me_tax's sentences. D5b SG two stores (conditional on the field) | pass |
| D6 | bank through the studio: bad number refused at send ("6 to 19 digits"); pending proposal `has_bank` True, drawer "•••• 8901", full number never in rows; approve → one bank change waiting, proposed by the maker, holder = name, not payroll-ready; bank leg row ok | pass |
| D7 | pending: one private attachment on the proposal, none on an employee, no file data in the payload; approve → document in the right category, unverified, same bytes, held file gone, `pb_nh_files` cleared; reject and withdraw delete the file; fast lane files directly, nothing held | pass |
| D8 | asks: 6 rows (SG) with urls, need, category for the merged ID card, proposal link; open → waiting (profile request, id_paper and tax_fund detail requests, bank change) → done (values on record, papers in the documents; ID number alone stays waiting until the card is there); `summary` counts; asks leg message. D8b nothing asked when all with HR | pass |
| D9 | approver without payroll-manager right: letter available (no switch-off), approve → letter document filed, leg ok; gate closed outside that call | pass |
| D10 | drawer rows: "NRIC or FIN •••• 567D", "Account number •••• 6789", "Papers attached", "Will be asked"; no file content in payload/result/facts | pass |
| D11 | P1 + P2 suites green (52), static gates (5), server item icons exist in the registry | pass |

### 2.2 Browser walk (local server `nh3_base` = copy of the P2 walk world, Claude-in-Chrome, 1440 px; console read)

| # | Walk | Result |
|---|---|---|
| E1 | Indonesia, defaults: 8 for Wulan (Later on BPJS), rail "8 for Wulan, 0 with you", Who does what "You 1 · Wulan 8 · Manager and IT 3", bank line "Wulan will be asked", summary card with 8 chips | pass |
| E2 | bank "I have it": row opens, rail amber "Finish: Bank account", bar slides, bank line "waiting for a second approval after sending"; typed BCA + number. KTP "I have it": NIK typed, PDF dropped (name, 10 KB), Valid until red until filled, removed (dates kept), re-attached → "6 for Wulan, 2 with you" | pass (focus-after-open fixed during the walk, NH34) |
| E3 | presets: ask-all → 8/0, button disabled; have-all → 9 rows open, "6 rows to finish"; ask-all now sends HR-only rows back to Later (changed during the walk) | pass |
| E4 | wrong type → "Only JPG, PNG or PDF documents are accepted."; 11 MB → "Choose a non-empty file up to 10 MB."; drop box amber, row sub "Attach the Highest certificate to finish this row." | pass |
| E5 | editor drawer: NPWP card → Needed before first pay, Work Permit added (Later: HR-only), saved (toast, list changed); Back to the usual list; Esc closes; HR officer sees no link | pass (drawer padding fixed, NH33) |
| E6 | send → "Wulan Sari is with Dewi Lestari for approval" (NEW00328), private held attachment; inbox drawer rows NIK •••• 0002, Bank BCA, Account •••• 2245, Papers attached, Will be asked, Left for later; approved as the HR lead → DB: NIK on record, KTP document (unverified, expiry 2031-04-30), bank change BCR/2026/0013 hr_review proposed by Dewi Maker, 6 ask rows open with urls, legs details/bank/papers/asks ok, no held attachment left | pass except the letter leg: "The PDF could not be made right now" (no wkhtmltopdf locally, NH20) — it now gets past the pay gate |
| E7 | Withdraw and change: held file deleted, step 7 intact, step 5 still has the file in memory and the NIK; resend works; after a reload the row says "The page was reloaded, so the file is no longer here. Add the file again." (amber drop) | pass |
| E8 | Singapore: personal, emergency, Self-help group fund, bank, NRIC or work pass and number, Degree / Certificate. Vietnam: Personal tax code, Social insurance number (Later), Citizen ID card and number, Health check (Asked at joining), certificate | pass |
| E9 | 500 px window + studio root 340 px: one column, segmented control full width, form and drop fit; `scrollWidth` 340 (only the step strip scrolls sideways, as P1) | pass |
| E10 | keyboard: focus the answer, ArrowRight moves Ask → I have it → Not needed, Enter opens the form and focuses its first box, Tab through name → phone → next row | pass (one unreproduced lost keystroke on the first try, §3.9) |
| E11 | console (errors only): two bus "ConnectionLost" from server restarts, nothing from the studio; server log: no error from our code (pre-existing biz_access logged-out and missing-filestore-image traces of the copied DB; the expected wkhtmltopdf error) | pass |

**D: 11/11 groups pass (67 + 8 tests). E: 11/11 pass**, E6 with the local-only PDF caveat.

## 3. Self-review against the handover — deviations

1. **Letter "with sudo"** (§1.6): sudo cannot open it — `_pbdc_pay` asks `_cd_unmask_wage()` (`has_group`) and then reads the
   wage with `env(su=False)` (NH32). Implemented as a context key set only by the letter leg that makes
   `pb.contracts._cd_unmask_wage` answer yes for that one call. Same decision, honest mechanism. P2's fast-lane switch-off
   and the approver warning are removed; W10c now asserts the new rule.
2. **Merged rows live in the Papers card** (group `papers`), since they carry a file; the handover lists `id_number` third in
   the item order. The merged "I have it" needs BOTH the number and the file (as the employee's own page asks both).
3. **Item list choices**: `later` is offered only on can't-ask rows (plus "Not needed" when optional); a can't-ask first-pay
   paper left "Later" is a warning row on step 7, not a block. An invalid choice from the screen falls back to the item's
   default, except an explicit skip of a first-pay item, which is refused (D4).
4. **Personal phone**: step 1's personal phone is the one source (`_have` folds it in server-side; the step 5 box writes
   `personal` while it holds a phone).
5. **File sentences**: the vault has no separate validator, so its exact sentences (same msgids) are re-checked in
   `_file_problem`; the real write is still `vault_upload_batch`, which checks again.
6. **pb_me_tax validator**: called as `_pb_check('tax_number', …, attachment=True)` — the proof file is not what is judged at
   send time; its numbers sentences are the employee-facing ones ("…when your NIK is used as your NPWP").
7. **Bank row in the legs** is added by `_apply_employee` after FS-16 sends it (not a leg in the runner), inserted after
   `details`; non-sent outcomes are already noted on the employee by FS-16, so no second chatter line.
8. **Ask-all preset** also sets HR-only rows to Later (walk finding: otherwise a half-typed "I have it" stayed behind).
9. **E10**: on the very first keyboard pass one typed phone number did not land (Tab from the name box, then typing); three
   re-tries in the same states could not reproduce it. Logged, not fixed.
10. Handover §3 rail 3 says to mask numbers "in the chatter": the details leg writes with `tracking_disable`, so no value
    reaches the chatter at all; drawer and done card mask to the last 4.
11. Handover slip (§3, third rail) corrects itself mid-sentence ("…after typing loses focus? No — keep them readable…"):
    followed the corrected intent — readable while typing, masked in the drawer / done card.

## 4. Design bar (ledger rule 4), scored honestly

- **Hero moment — 8/10.** Flipping a row opens its form with a height animation, the rail turns amber with the row's name,
  the Who does what bar slides (flex transition), the bank line changes words and icon. Missing: the bar has no numbers
  animation and the opened form is not yet a FLIP of the row.
- **Zero dead-ends — 9/10.** Every impossible answer is visible with its reason; every unfinished row says what it lacks
  (number, file, valid-until date, "Add the file again" after a reload); file errors use the side panel's sentences; no
  country → a card that jumps to step 2; non-editors see no editor link; the editor has a way back to the usual list.
- **Plain language — 8/10.** Screen words; vault category names are English product names ("ID Document",
  "Degree / Certificate") where a country row has no label.
- **Motion — 8/10.** Row open/close, drop hover scale, file chip lands, bar flex, drawer slides; all off under reduced motion.
- **Keyboard — 8/10.** Arrows move the answer (roving tabindex), Enter opens the form and focuses it, Esc closes the drawer,
  Tab is trapped in the drawer, closed forms are `inert`.
- **Versus BambooHR / Rippling onboarding packets** — on par for "who gives what" with a per-country list; behind on the
  phone preview and reminders (P3b).

## 5. New gotchas
NH32–NH40 in the ledger: the pay gate needs more than sudo; SCSS order vs modifier class; focus after an OWL change;
unstored computed answers cached in a transaction; vault's base64-length check first; `/my/tax` offers kinds by the
scheme's country; company row label fallback; vault category names are untranslated product words; post_install tests run
only for modules being updated.

## 6. Open questions for the architect / owner
1. **Second ID store**: VN `vietnam_citizen_id` and SG `singapore_nric_fin` are written together with `identification_id`
   (open question 8). Should the VN social insurance number / India UAN-ESI also be copied to the running contract
   (`hr.contract.vietnam_social_insurance_number`, `uan_number`, `esi_number`) as the tax code is?
2. **Merged "I have it" needs number AND file.** If HR has only the NIK, they must type it later on the record. Allow a
   number-only answer that still asks the person for the card?
3. **Asks need a sign-in**: P3a records asks whatever step 6's sign-in choice is. With "Not yet", P3b's invitation is the
   only way in — P3b must decide what happens to asks when nobody can sign in.
4. **Tax kinds follow the scheme's country on `/my/tax`** (NH39): a team-scheme/country mismatch makes the ask url refuse.
5. **Category wording**: vault categories have English names; should the papers table seed labels for every row (e.g. SG
   "Highest certificate") so nothing shows "Degree / Certificate"?

## 7. Seams for P3b
- `pb.new.hire.ask.summary(employee)` → `{total, done, waiting, open, items:[{key, label, state, need, url}]}` — the ONE
  reader (welcome page, home row via `_pbme_needs_extra`, board chip, reminders). It refreshes first.
- `pb.new.hire.ask` rows: `employee_id, key, label, need, url, sequence, state, done_on, category_id, company_id,
  proposal_id`; `refresh()` is cheap and idempotent (sudo write of its own state only).
- `url` values: `/my/profile`, `/my/details/papers?kind=national_id`, `/my/tax/change/<kind>`, `/my/details/bank`,
  `/my/documents`. The privacy gate keeps `?next=` (FACTS §A5).
- Asks are created by the `asks` welcome leg (after `papers`, before `login`); P3b's invitation leg can read them in the same
  apply (`state['…']` is not used; query by employee).
- Screen: the summary card in `StepDocs` (`.pbnh-asksum`, `summaryTitle/summaryLine`) is the place for the phone preview and
  the reminders switch; `docTallyOf(nh)` / `docChoiceOf` give the ask list client-side.

## 8. Commits (not pushed)
- `4d5c75858` NEWHIRE P3a: handover
- `0e5f0d3eb` NEWHIRE P3a: server side of step 5 (details and documents)
- `df5d5dd14` NEWHIRE P3a: step 5 on screen (details and documents)
- `d866b2f4c` NEWHIRE P3a: step 5 item icons exist in the shared registry (D11)
- this docs commit (report, ledger NH32–NH40, fact corrections)

Local leftovers (not in git): DB `nh3_base` (+ filestore copy) = P2 walk world + P3a walk (Wulan Sari applied, approval route
ON); scratch `runt.sh` (test runner that kills the hung shutdown), `restart3.sh`, `check3.py`, `probe_p3.py`.
