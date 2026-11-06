# FILLIN P2 — report (screens: Yes/No and words, "Filled in by Payobook", To check)

Implemented per `FILLIN_P2.md`, `FILLIN_P1_REPORT.md` §6 and `FILLIN_LEDGER.md`,
with the coordinator's mid-phase rule for `pb_payruns` (see deviation D1).
All six modules live on the four databases (`payobook`, `payobook_template`,
`p0clone`, `rize`); `abm` not touched. Browser walk on rize.payobook.com as
the signed-in admin (Ash Sohani) — a session was open, no login was typed.

Note on the brand: on rize every "Payobook" in these strings is shown as
**"Rize"** by the white-label rewrite layer (`biz_debrand_rewrite`), so the
screenshots read "Filled in by Rize · not checked". That is the existing
tenant-brand seam working, not a different string.

## 1. What was built

| Block | Piece | Where |
|---|---|---|
| A1 | Component rows read the rule's words: `_cd_value_view(rule, amount, symbol)` → display word + editor kind (`toggle` / `select` / `integer` / `number` / `money`) + options, from `value_label_control()` / `value_label_options()`; integer/quantity/decimal/rate/identifier show a plain number, money stays money; virtual rows too | `pb_contracts/models/pb_contract_360.py` (`_cd_comp_row`, `_cd_virtual_row`); `contract_360.js` `compEntry` reads `row.edit_kind` + `row.options` |
| A2 | `fill`, `fill_checked`, `fill_tag` on each row (`_cd_fill_tag`): amber "Filled in by Payobook · not checked", muted "… · checked by <name> on <date>" | same + `contract_360.xml` `CdComponentRow`, `.pbc-comp-fill` |
| A3 | `components.fillin = {n, can_check}`; header line "Payobook filled in N answers for this contract." + **All correct** → `pb.contracts.cd_fillin_check(contract_id)` → `contract.pb_fillin_check()`; `can_check` = `_pb_fillin_may_check()` (P1's rule) | `pb_contract_360.py` `_cd_may_check`, `cd_fillin_check`; `contract_360.js` `checkFillin` |
| A4 | History: `auto_default` "Filled in by Payobook from the scheme's usual answer" (amber), `checked` "Checked by <name>, no change" (green, no from→to). History values now use the words too (no more "Rp0 → Rp1") | `_cd_change_sentence`, `_cd_history_components` |
| A5 | Learn practice contract panel: new row UNION "Union member" = **Yes** with the amber tag | `pb_learn/static/src/engine/fixture.js`, `screens.js` |
| B1 | Hidden choice section `fillin` (option `unchecked`, domain `advantages_ids any [pb_fill=auto, pb_checked_at=False]`), only where the P1 fields exist; built-in view **To check** after Running | `pb_contracts/models/pb_contracts.py` `_fillin_spec`, `_pbf_builtin_views` |
| B2 | Card: `fillin {n, answers[{label, value_text}]}` (one search per page, words via `value_label_for`); amber chip "N answers to check" on every view; on To check the answers as chips + **Change** (panel opens on Components — new optional `tab` prop) + **Looks right** (`fillin_check_contract`) | `pb_contracts.py` `_fillin_rows`, `fillin_check_contract`; `contracts.js/.xml/.scss` |
| B3 | Bar on To check: "All N look right" → confirm dialog with the count and first five names ("…and N more") via `fillin_preview_all`, then `fillin_check_all(filters, search)` — the roster's own `pbf_domain` AND the fillin domain, caller's rights; toast "Checked N contracts." Empty To check list reads "Nothing to check" (green) | `pb_contracts.py`; `contracts.js` `allLookRight` |
| B4 | `pb.people.fillin_pending(employee_id)` → `{n, contract_id}` (draft/running contracts); amber chip button in `pb_employee_360_chips`, opens the contract on Components via `onOpenContract`; chips receive only the props they declare (`chipPropsFor`) | `pb_employee_vault/models/pb_people_360.py`, `static/src/js/fillin_chip.js`, `employee_360.js/.xml/.scss` |
| C1 | `_run_checks` amber **advisory** `fillin` (icon `listChecks`), owner "HR team", count = distinct people on the run's payslips whose draft/running contract has unchecked lines; never makes a run unready | `pb_payruns/models/pb_payruns.py` (only `_run_checks`) |
| C2 | `scheme_preview` returns `unchecked` among covered people; muted line under the scheme field + "Open the Contracts list" (opens `pb_contracts` with `params.view='fillin'`); hidden when 0 | `pb_payrun_wizard` model, JS, XML, SCSS |
| C3 | New `pb_formula_studio/models/studio_fillin.py` (`_inherit`, `pb_formula_studio.py` untouched): `_EDIT_FIELDS` + `value_labels`; `get_component_edit` adds `value_labels`, `value_kind`, `value_label_view` (judged by the rule's own `value_label_control` on an unsaved record); `studio_value_labels(text, kind)` re-reads words as they are typed; save refuses words that do not parse. Editor: "Usual answer for a new contract" (contract components) as Yes/No toggle or pick-list, else number; help text; "Words for each value" field with live warning | `studio_fillin.py`, `studio.xml`, `formula_studio.js`, `studio.scss` |
| C4 | Pay data file note — **skipped** (deviation D4) | — |

Every new string has EN + VI (`vi_VN.po` in pb_contracts, pb_employee_vault,
pb_payruns, pb_payrun_wizard, pb_formula_studio); PO gate (`PoFileReader`) run
on the staged copies before every deploy — all OK. No user-visible "Odoo".

## 2. Tests T1–T12

| # | Case | Result | Evidence |
|---|---|---|---|
| T1 | rize, contract 3444 (RM Dimas Radithya Pratomo) › Components | PASS — BPJS health covered **Yes**, BPJS TK covered **Yes**, Employer reimburses **No** (not filled in yet), Tax allowance mode **Insurance-premium tax only**; no "Rp" on any flag; money rows still Rp | `p2_shots/T1_panel_words_top.jpg`, `T1_panel_words_tax_mode.jpg` |
| T2 | edit on the T3 contract 3650 | PASS — TK edits as a Yes/No toggle; Tax allowance mode as a three-word pick-list (current value lit); Save → psql `IDBPJSTKCOVERE=0`, `IDTAXALLOWMODE=2`, both `pb_fill` cleared + checked stamp by uid 2; change rows `manual 1→0`, `manual 1→2` | `T2_tax_mode_picklist.jpg`, `T2_after_save_tk_no.jpg`; psql lines 35574/35576, change rows 31467/31468 |
| T3 | New contract for **Aradea Putra Suriya (ID115, employee 5285)** → draft contract **3650** "Aradea Putra Suriya - 2026-11-03" | PASS — 3 lines filled (`auto_default` rows 31464–31466): amber tags; header "Payobook filled in 3 answers…"; All correct stamped the remaining line, tag turned muted "checked by Ash Sohani on 03 Nov 2026", header gone; History shows both new sentences | `T3_new_contract_filled_in_tags.jpg`, `T3_all_correct_muted_tag.jpg`, `T3_history_sentences.jpg` |
| T4 | Contracts › To check | PASS — tab "To check 1" = psql 1 (only contract 3650 has an unchecked line); card chip "1 answer to check" + "BPJS health covered: Yes"; Change opened the panel on Components; Looks right → toast "Aradea Putra Suriya: answers confirmed.", tab 0 | `T4_to_check_view_card.jpg`, `T4_change_opens_components.jpg`, `T4_looks_right_count_0.jpg` |
| T5 | "It looks right" (N = 1) | PASS — confirm "Confirm the answers Rize filled in on 1 contract (Aradea Putra Suriya)? Nothing is changed…", button "Confirm 1 contract"; after confirm toast "Checked 1 contract.", tab 0; empty list then reads "Nothing to check" | `T5_all_look_right_confirm.jpg`, `T5_after_confirm_0.jpg`, `T5_nothing_to_check.jpg` |
| T6 | Employee panel for Aradea | PASS — amber chip "1 answer to check" beside Paid by; click opens contract 3650 on Components; after checking `fillin_pending(5285)` = `{n: 0}` → chip renders nothing | `T6_employee_chip.jpg`, `T6_chip_opens_contract.jpg` |
| T7 | Pay run board, existing draft run 2114 "TEST ID August 2026 — application inputs without Excel" (includes 5285) | PASS — amber line "1 person has answers Rize filled in that nobody has checked yet." owner HR team; card still "Ready to send in". **No door button** (D1). Nothing run or created | `T7_run_card_advisory.jpg` |
| T8 | Wizard › Indonesia scheme (preview only, left with Cancel/door, nothing created) | PASS — November period: Aradea not covered (her only running-period contract is the draft) → line hidden (`unchecked: 0`); August period: "1 of them has answers Rize filled in that nobody has checked · Open the Contracts list"; the link opens Contracts on To check | `T8_wizard_hidden_when_0.jpg`, `T8_wizard_line_fixed.jpg`, `T8_wizard_door_to_check.jpg` (first version wrapped badly: `T8_wizard_line_before_fix.jpg`, fixed in 671bf55d5) |
| T9 | Studio › scheme 7121 › BPJS TK covered / Tax allowance mode | PASS — "Usual answer for a new contract" is a Yes/No toggle on Yes; Tax allowance mode a pick-list on "Insurance-premium tax only"; typing `0=No;1=Yes;2=Maybe` switches to a pick-list live, `yes` shows the amber "These words do not read yet…" line. Round trip: saved words `0=No; 1=Yes` → psql `value_labels='0=No; 1=Yes'`, `default_value=1`; saved back `0=No;1=Yes` → psql restored. Usual answers never changed | `T9_studio_tk_toggle.jpg`, `T9_studio_tax_mode_picklist.jpg`; psql rule 33489 |
| T10 | Rights (shell on rize, rolled back): rize has no HR-only user, so a temporary user with Employee + HR officer + Records desk — view (needed on rize to read contracts at all) was created inside the transaction | PASS — panel loads, `can_write False`, `fillin {n:1, can_check: False}`, tag visible; `cd_fillin_check`, `fillin_check_contract`, `fillin_check_all` all return "You cannot confirm the answers on a contract…"; direct `pb_fillin_check` → AccessError; page `can_check False` (no Looks right / bar); `fillin_pending` still answers (read); nothing stamped. Note: an HR officer WITHOUT Records desk cannot read `hr.contract` on rize at all (rize ACL) | shell output in this session (`/tmp/fillin_t10.py` on the box) |
| T11 | Console | PASS — no console errors on Contracts board + panel, Employees + panel, Pay runs board, Run Payroll wizard, Formula Studio editor, Learn practice | `read_console_messages` (errors only) after each walk: none |
| T12 | Learn › Practice on a copy › Employees | PASS — practice contract panel shows "UNION Union member … Yes" with "Filled in by Rize · not checked" | `T12_learn_practice_panel.jpg` |

Extra server check before the block C deploy (shell on rize, scratch addons,
rolled back): `_EDIT_FIELDS` carries `value_labels` (25 fields);
`studio_value_labels` toggle/select/invalid/boolean answers correct;
`get_component_edit(33489)` returns `value_labels`, `value_kind`,
`value_label_view`; `save_component(…, {'value_labels': 'garbage'})` refused;
wizard `_fillin_unchecked` = 1.

## 3. Deploy evidence

All with `/odoo/ops/filter_deploy.sh`, staged from committed HEAD (`git archive`),
staging dir cleaned first, START/DONE lines in `/opt/deploy-notes.md`.
Before each deploy the live tree was compared with the previous commit (no
foreign work overwritten — except `pb_payruns`, which shipped the PRS session's
committed 6eb39d6a3 as the coordinator asked).

| Deploy | Commit | Modules → version | Window (UTC) | p0clone / template / rize / payobook | Jobs before/after | Evidence |
|---|---|---|---|---|---|---|
| A full | e1bce1180 | pb_contracts 19.0.1.11.0, pb_learn 19.0.20.8.5 | 22:22:54–22:27:30 | EXIT=0 errors=0 ×4 | 31/28/74/42 unchanged | `/tmp/fillin-p2a-run-20261103222254` |
| B full | 1207a1456 | pb_contracts 19.0.1.12.0, pb_employee_vault 19.0.1.5.0 | 22:33:04–22:37:30 | EXIT=0 errors=0 ×4 | unchanged | `/tmp/fillin-p2b-run-20261103223304` |
| C full | 12e57634d | **pb_payruns 19.0.3.3.1** (HEAD incl. PRS P1 6eb39d6a3), pb_payrun_wizard 19.0.1.39.0, pb_formula_studio 19.0.1.211.0 | 22:40:47–22:45:36 | EXIT=0 ×4 | unchanged | `/tmp/fillin-p2c-run-20261103224047` |
| C looks | 671bf55d5 | pb_payrun_wizard template + SCSS (version unchanged) | 22:52 | assets purged ×4 | — | `/tmp/fillin-p2c2-run-20261103225209` |
| B follow-up full | 9807cd1aa | pb_contracts 19.0.1.12.1 | 22:55:05–22:58:51 | EXIT=0 errors=0 ×4 | unchanged | `/tmp/fillin-p2b2-run-20261103225505` |

Script result `OK` every time; sites warm 200; `latest_version` equals the
manifest on all four databases for every module (script "version" lines).
Final tree hashes repo HEAD = server: pb_contracts e98fcd827bc8, pb_learn
61d4b6a502ff, pb_employee_vault 926336513ec8, pb_payruns 1193cf4e9134,
pb_payrun_wizard ce45eebef01a, pb_formula_studio df6da1f2edc2. `abm` not touched.

## 4. The T3 contract (owner decides: keep or delete)

* **Aradea Putra Suriya** (ID115, employee 5285), contract **3650**
  "Aradea Putra Suriya - 2026-11-03", **draft**, start 2026-11-03, open-ended,
  wage 0, structure "Base for new structures". Created through the New contract
  button on her employee page (request NEW00001 — the route applied at once;
  the dialog nevertheless said "No contract exists yet…", see §7 note 3).
* Its component lines after the tests: BPJS health covered = Yes (filled in by
  Payobook, checked by Ash Sohani); **BPJS TK covered = No and Tax allowance
  mode = All tax (net salary) are TEST VALUES from T2** — if the contract is
  kept, set them back (Yes / Insurance-premium tax only) or delete it.
* Test-fixture writes on this contract only: twice (before T3 and before T5)
  the Health line's checked stamp was cleared with SQL
  (`/tmp/fillin_reset.sql`: `pb_checked_by/at = NULL` on line 35575, contract
  3650 only, amount untouched) so the review buttons could each be pressed on
  a real unchecked answer. The history keeps every "checked" row truthfully
  (three "Checked by Ash Sohani, no change" rows).
* Also touched on rize: rule 33489 words saved as `0=No; 1=Yes` and back to
  `0=No;1=Yes` (T9). Nothing deleted. No pay run created or run.

## 5. Deviations

* **D1 — no door on the pay run card's advisory line (C1).** Mid-phase the
  coordinator restricted `pb_payruns` to `_run_checks` + its feed + manifest +
  `.po`, because the PAY RUN SCREEN session owns that module's JS/form now. The
  door needs a `next.key` handler in `payruns.js`, so the line ships with
  `next: None` and its detail says "Check them once under Contracts › To check".
  The count query lives inside `_run_checks` (one small query per open card)
  instead of a board-level helper, for the same reason. The text is a whole
  sentence ("…nobody has checked yet.") because the new pay run screen reuses
  `_run_checks`. **Follow-up:** once PRS lands, add `if (key === "fillin")` →
  `doAction({tag: 'pb_contracts', params: {view: 'fillin'}})` in
  `openCheck` and set `next` (the wizard's `openFillin` is the precedent).
* **D2 — card chip placement (B2).** The amber "N answers to check" chip sits
  in the card's status column beside the Draft/Running badge rather than under
  the period line: the card is a single flex row and a period sub-line would
  have shifted every card on every view. On the To check view the answers and
  the two buttons get a full-width strip under the card.
* **D3 — studio list cell (C3).** No list cell prints `default_value` on the
  scheme's components list (`grep default_value` finds only the editor input),
  so nothing to change there.
* **D4 — C4 skipped.** The monthly workbook's column notes are not written in
  one ~20-line place I could find quickly; left for a later phase.
* **D5 — "Default value" label kept for non-contract input rules.** The handover
  relabels it to "Usual answer for a new contract"; that is only true for
  contract components (for other input rules `default_value` is the value an
  empty pay-data cell takes), so the label switches on `is_contract_component`.
* **D6 — git pull before block C** was a fetch: `origin/19.1` had nothing new,
  and a `pull --rebase --autostash` would have stashed the PRS session's
  uncommitted `pb_payruns.py` edits. My `pb_payruns.py` hunk was committed from
  a blob built on HEAD (`git update-index --cacheinfo`), so their 13 uncommitted
  hunks stayed in the working tree, uncommitted.
* **D7 — T10 used a temporary user inside a rolled-back shell transaction**
  (no HR-only user exists on rize, and no password may be typed).
* No `ListAgents` here; the coordinator announced the deploys.

## 6. Small extras (inside scope, found on the walk)

* Pick-lists open with the current value lit (`CdPicker` `current` prop) — also
  benefits the contract's own selection fields.
* Wizard hint re-laid as one sentence with the link inline (671bf55d5).
* "Nothing to check" empty state on the To check list (9807cd1aa).

## 7. Proposed ledger gotchas

**FI12 — the brand rewrite renames "Payobook" in these strings.** On a tenant
with a brand (rize) every "Filled in by Payobook" reads "Filled in by Rize",
in Python and JS strings alike. Screenshots and tests must expect the tenant
brand; never hard-code "Payobook" in a test assertion that runs on a tenant.

**FI13 — on rize an HR officer cannot read contracts without "Records desk —
view".** `hr.group_hr_user` alone gets an AccessError on `hr.contract`; rights
tests there need that group too.

**FI14 — the New contract dialog says "No contract exists yet" even when the
route applied at once** (NEW00001 applied in the same call and contract 3650
exists). Not a FILLIN bug; worth a look in `pb_people_advanced` contract wizard.
Also: the Contracts board's own "New contract" button opens the wizard with
no employee (no person field) — only the employee page's button works.

**FI15 — pb_payruns is shared with the PAY RUN SCREEN session**: commit only
your hunk (blob on HEAD + `update-index`), never `git add` the whole file, and
bump the manifest past HEAD right before committing.

## 8. Plain-English summary (for the owner)

1. A contract now shows BPJS and tax settings as **Yes / No and words** (for example "Insurance-premium tax only"), never "Rp1", and you change them with a Yes/No switch or a short list.
2. Anything Rize filled in by itself carries an amber "**Filled in · not checked**" tag; one press of **All correct** (on the contract) or **Looks right** (on the Contracts list) confirms it, and the history says who checked it.
3. The Contracts list has a new **To check** tab, the employee panel shows "1 answer to check", the pay run card warns (without blocking) and the Run Payroll window says how many people still have answers nobody checked.
4. In the setup screen, each contract setting now has "**Usual answer for a new contract**" and "**Words for each value**".
5. Live on all four companies' systems. For the test I made one draft contract for **Aradea Putra Suriya (contract 3650)** — please keep or delete it; if you keep it, set BPJS TK back to Yes and Tax allowance to "Insurance-premium tax only" (I changed them to test saving).
