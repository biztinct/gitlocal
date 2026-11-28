# UPDATES — Phase 2b report (pay items by pay scheme, CLEAR, one contract)

Implemented, tested, deployed ×5 and checked live on 2026-11-11 by the Opus implementation
agent, against `UPDATES_P2B_HANDOVER.md` and `UPDATES_LEDGER.md`.

**Shipped:** `pb_records` 19.0.1.8.6 and `pb_updates` 19.0.1.1.0, live on `payobook`,
`payobook_template`, `p0clone`, `rize`, `sudima`. Never `abm`, `pbf_preview`,
`recruit_connect_20261023`.

Commits: `a3af8edea` (pb_records seams + contract tie) · `c57d04d51` (Updates scheme-aware
pay items, CLEAR, tests, translations) · the docs commit that carries this report, the
handover and the ledger.

---

## R1. Tests B1–B15

New file `pb_updates/tests/test_updates_p2b.py` — a company of its own with five pay schemes
on a scheme map (team A → "Monthly staff" X/Y/T; team B → "Daily rate" Y; team C → "Field
monthly" W (end of month) + "Field advance" Z (mid-month); team N → no line, two schemes per
kind of run so "the only scheme" never answers).

| # | Case | Result |
|---|---|---|
| B1 | `test_B1_item_only_in_one_scheme` — Ann (Monthly) `ok`; Bob (Daily) `off_scheme`, the sentence names Bob, "P2B Daily rate" (with how the map knows) and "P2B Site allowance"; no rule code in it; only Ann's change in `changes`; scheme names on the person rows | PASS |
| B2 | `test_B2_a_line_already_on_the_contract_stands` — Bea (Daily) already has X = 250 → `ok`, old "250" | PASS |
| B3 | `test_B3_nobody_covers_the_person` — desk verdict `ok`, row `no_scheme: true`, strip `no_scheme: 1` | PASS |
| B4 | `test_B4_monthly_and_off_cycle_schemes` — Cat (Field monthly + Field advance): Z (mid-month only) `ok`, W `ok`, Y `off_scheme` naming both schemes; `scheme_ids` = both | PASS |
| B5 | `test_B5_apply_drops_an_off_scheme_change` — `apply` called directly: off-scheme change dropped, `nothing: True`, `skipped_off_scheme: 1`, sentence; nothing written. Mixed with an in-scheme change: written 1, skipped 1, batch `values_off_scheme = 1`, Past-updates row carries it | PASS |
| B6 | `test_B6_a_scheme_item_with_no_line_anywhere` — Z not on the Records screen's catalogue, offered by Updates with its scheme; applied → new line 1200 (proves the context reaches the write inside the approval engine's fast lane); undone from the **Records desk's** `undo_apply` → line gone | PASS |
| B7 | `test_B7_read_columns_counts_the_schemes_in_the_file` — `schemes` with head-counts (Daily 2, Monthly 1, Field monthly 1, Field advance 1), biggest first, `no_scheme: 1`; pay items carry `schemes`; `file_schemes` (identity chosen by hand) gives the same counts | PASS |
| B7b | `test_B7b_recheck_and_the_sheet` — recheck gives `off_scheme` + the person's scheme; the sheet: pay items of the people's schemes only (Field bonus left out), Bob's X cell blank + grey `EEEEF2`, Bea's real 250 shown, a "Read me" sheet after "Records" mentioning CLEAR and grey cells, no "Odoo"; the sheet sent straight back = 0 changes | PASS |
| B8 | `test_B8_clear_then_undo_restores_everything` — CLEAR / `clear` / ` Clear ` on job title (text), manager (named reference), contract end date (date), Transport (amount → shown "0", old "120"), Uniform size (text pay item); applied 5; all emptied / 0; Undo restored 5, every value equal to before | PASS |
| B8b | `test_B8b_clearing_what_is_empty_is_the_same` — CLEAR on a pay item with no line and on an empty end date → `same`, nothing sent | PASS |
| B9 | `test_B9_clear_refused_on_required_and_bank` — wage "Wage cannot be empty.", start date "… cannot be empty.", bank name "Bank details cannot be removed from a file. Change them on the employee record."; recheck reads `clear` the same way | PASS |
| B10 | `test_B10_records_screen_keeps_its_rules` — every plain Master card identical inside the Updates catalogue; Y/Z/W/T only in Updates'; Records import keeps CLEAR as text; an emptied wage on the Records grid is still `ok` (today's behaviour); a scheme-only card is still unknown to the Records desk | PASS |
| B10 (out of suite) | Before/after capture on a local copy of payobook (4,575 people), pre-phase code vs new code: `get_fields(0)`, `_cards(0)` (105 ids), `get_fields(scheme)`, the **whole-roster export cell by cell** (4,576 × 102), `import_peek` of a Records-screen file containing CLEAR / `clear`, `preview_changes` with emptied wage / job / bank — **12 of 12 identical** (hashes `95ce467a…`, `d844ec4b…`, `4377b1a7…`, `638e0773…`) | PASS |
| B11 | `test_B11_two_contracts_with_the_same_start` — lower id picked by both `_get_latest_contract` and `_io_contracts`; untouched sheet: 0 changes, item `same`. (Fails on the pre-phase code, as it should.) | PASS |
| B12 | `pb.scheme.map` absent | N/A — `pb_scheme_map` is installed on all five databases (19.0.2.5.5), so it is now a declared dependency and the soft check was dropped, as the handover allows |
| B13 | Full suites | Local isolated tree: **134/134** (pb_records 94 incl. the P2a golden — identical; pb_updates 40 = 27 + 13). Live `p0clone`, after start, `--http-port 8471`: **134/134**, 0 ERROR lines. The new file fails 13/13 against the pre-phase pb_records (it tests what it claims) |
| B14 | Speed, local copy of payobook, 4,575 × 73 | see R2 — review 11.8 s, sheet 15.7 s cold / 10.3 s warm |
| B15 | `.po` gate + "Odoo" scan | `PoFileReader` reads both files (pb_updates 321 rows, pb_records 290); all 307 pb_updates strings translated; 4 new pb_records strings translated (the 57 older untranslated model-field strings are pre-existing); no "Odoo" in any msgid/msgstr; P1's `test_no_odoo_in_visible_strings` passes. Built from `odoo-bin i18n export -l pot`, appended without rewrapping |

Browser walk (handover §8) — R4.

## R2. Timings

Local copy of payobook (dump taken 04:40 UTC today), uid 2, same machine, same input:

| Step (4,575 people) | Pre-phase code | This phase | Target |
|---|---|---|---|
| Sheet, 73 columns (cold / warm) | 16.8 s / 10.8 s | 15.7 s / 10.3 s | ≤ 20 s ✔ |
| Read the columns | 3.0 s | 4.5 s (+1.4 s: people found + pay schemes counted) | — |
| Review, 73 columns | 12.3 s / 12.0 s | 11.8 s / 11.7 s | ≤ 25 s ✔ |
| Pay-items sheet (26 columns) / columns / review | — | 17.0 s / 3.8 s / 11.2 s; round trip 0 changes, 78,572 "same" | — |
| **Scheme resolve on its own** (`_people_schemes`, 4,575 people, `any` + every kind of run on the map) | — | **0.74 s** (4,510 known) | — |
| Whole scheme context (resolve + pay items + contract lines) | — | 1.30 s | — |

The resolve only runs when the file brings a pay item in, so the 73-column review is unchanged.
Live (QA login, 3-row file): read columns 0.8 s, review 1.0 s.

## R3. Deploy evidence (five databases)

Unit `updates-p2b-20261111T050621Z` under `flock /tmp/payobook-studio-deploy.lock`; START
05:06 / DONE 05:14 UTC in `/opt/deploy-notes.md`. Evidence `/tmp/updates-p2b-20261111T050621Z/`.

- Dry run: only this phase's files differed (pb_records 5, pb_updates 13 incl. 2 new); the
  server's copies of all 16 changed files were byte-identical to the pre-phase commit
  `46134de0a` — nobody's newer work overwritten.
- Normal tier: no dumps; previous module trees in `/odoo/backups/updates-p2b-20261111T050621Z/`.
- `-u pb_records,pb_updates` on all five: EXIT=0, **0 ERROR/CRITICAL** in every upgrade log.
  New column `pb_updates_batch.values_off_scheme` present on all five.
- Active scheduled jobs before → after: 49→49, 31→31, 38→38, 81→81, 80→80; none newly active.
- Assets: signal row + `/web/assets/%` purge + `web.assets.version` bump on all five.
- **Downtime 1 min 35 s** (05:06:49–05:08:24). **No test ran in the stopped window** (G19);
  the suites ran after start on 8471/8472.
- Sites after start: payobook.com, rize, p0clone, sudima all 200. Server log since start:
  0 ERROR, 0 Traceback.

| Check | payobook | payobook_template | p0clone | rize | sudima |
|---|---|---|---|---|---|
| `pb_records` latest_version | 19.0.1.8.6 | 19.0.1.8.6 | 19.0.1.8.6 | 19.0.1.8.6 | 19.0.1.8.6 |
| `pb_updates` latest_version | 19.0.1.1.0 | 19.0.1.1.0 | 19.0.1.1.0 | 19.0.1.1.0 | 19.0.1.1.0 |
| state | installed | installed | installed | installed | installed |

Tree hashes (sha256 of sorted per-file sha256, skipping `__pycache__`, `*.pyc`, `.DS_Store`),
repo = server: `pb_records` e6f16c42a6fc5e78 = e6f16c42a6fc5e78; `pb_updates`
84284f798cb891f8 = 84284f798cb891f8.

## R4. Browser walk (local) and live check

**Local walk** (copy of payobook, my own local server, active company Payobook Vietnam JSC;
one extra pay item "DEMO Walk allowance" added to the local Retail scheme so an item no
contract has yet could be shown). Console read at every step: **no errors**. Screenshots in
`outputs/updates-p2b/` (not committed):

1. Match: the quiet line "Each person's pay scheme is worked out for you, the same way a pay
   run does it." with head-count chips; picking "Work email" by hand recounted them
   (Manufacturing 2 / Retail 2 / Logistics 1, end-month and mid-month each). "Goes to"
   groups: topics, then "Payobook Retail — End-Month Payroll · 2 people in this file", then
   "Kept on contracts only". (`01-match…`; the chip count was hidden by truncation on long
   scheme names — fixed: the count is now its own pill, `08-…`.)
2. Review: "This file will make 6 changes for 4 people. 2 rows need your attention."; the
   scheme strip; Cleared cell (eraser, old struck through); two greyed cells with the ban
   icon and the sentence as tooltip; "Not in their pay scheme · 2" (grey) beside the
   filters; chip filter Retail → only the two Retail people; the off filter → only the
   two; button counts exclude greyed values (`02-…`, `03-…`).
3. Fix row on a cleared cell: "Job Title is emptied. Today it is Cashier." (`04-…`). A row
   that matched nobody bound by hand to a Manufacturing person: its pay-item value turned
   grey (recheck applies the same verdict).
4. Apply: "3 values will be skipped because those pay items are not in the person's pay
   scheme." (`05-…`). Done: "7 changes are in for 5 people" + the skipped line (`06-…`).
   Past updates: "… 3 values were skipped …" (`07-…`). Undo: "7 values are back as they were."
5. Widths: rows are one height within a grid (76 px with pay items, 58 px without); a file
   with no pay item shows no strip, no scheme line and no grey legend entry (`09-…`); no
   sideways page scroll at content widths 1,030 and 1,190 px (`10-…`). See R6.6 on 1280/1440.

**Live check on payobook** (server-side as the QA user, the P2a method; log
`outputs/updates-p2b/live-walk-log.txt`):

1. Before: Bùi Hữu Bảo (Retail, demo login ess1) job "Cashier", pay item "Mức lương HĐLĐ" 0;
   Bùi Hữu Dũng (Manufacturing, demo login employee) job "Machine Operator"; Đinh Gia Huy
   (Manufacturing, no contract) 0 contracts, 0 lines.
2. File (own headings): Bảo pay item 1,234,567; Dũng job title CLEAR; Huy pay item 999.
3. Columns: head-counts after choosing the email column — Manufacturing 2 (end + mid), Retail 1.
4. Review (1.0 s): Bảo `ok` 0 → 1,234,567; Dũng `ok` Cleared; Huy **`off_scheme`** — "Đinh Gia
   Huy is paid under Payobook Manufacturing — End-Month Payroll and Payobook Manufacturing —
   Mid-Month Advance, which have no Mức lương HĐLĐ."; 2 changes sent.
5. Apply "P2b live check" — **with Huy's value added back by hand to prove the server rail**:
   written 2, people 2, `skipped_off_scheme 1`, reference RD00172, no approval route.
   Values changed as typed; Huy still 0 contracts, 0 lines.
6. Past updates: "P2b live check", applied, 2 values, `values_off_scheme 1`, file kept.
7. Undo: restored 2, 0 skipped. **Final snapshot equal to step 1 — RESTORED.**
8. Browser, look only (existing session, nothing applied): payobook People › Updates opens,
   Past updates shows "P2b live check … Put back … by QA Test · Undone"; console clean
   (`11-…`). sudima: Updates home opens, "No updates yet", console clean (`12-…`).
   Nothing applied on rize or sudima.

Left behind on purpose (audit, not data): 1 named update marked Undone with its file, the
desk's apply/undo rows and per-value audit rows, 2 component history rows on Bảo's contract
(0 → 1,234,567 → 0), chatter tracking on the two people, 1 remembered heading layout.
No demo data deleted.

## R5. Self-review against the handover

- **§2 non-goals — respected.** No dates, one-offs, approval split, joiners, drafts.
  `pb.scheme.map` only read. G17 untouched. No cross-request cache (every context dies with
  its call). `pb_lifecycle`, `pb_hiring`, `pb_me_expense`, `pb_timeoff`,
  `docs/handovers/workflow2` not touched, staged or deployed.
- **Records screen exactly as today:** proven by B10 in the suite and the 12/12 identical
  before/after capture. The only `pb_records` behaviour change is the contract tie (§6).
- **§4.2 verdict table:** known+in → desk verdict; known+not in → `off_scheme` (greyed, never
  sent, not counted as a problem); unknown → desk verdict + row `no_scheme`; exception for a
  line already on the contract. Enforced in `review`, `recheck` and `apply`.
- **White-label / plain words:** every new sentence uses "pay scheme" / "pay item"; no model
  name, card id or rule code in a sentence (B1 asserts it); no "Odoo".
- **Design:** indigo chips with count pills, grey (never red/amber) for off-scheme, amber dot
  only for "no pay scheme yet", Lucide `layers`/`ban` from the kit, `eraser` drawn locally
  (see R6.4), one primary button per bar. Honest scores: clarity 5, zero dead-ends 4 (a
  person bound by hand does not update the scheme chips' counts), motion 4 (no new motion),
  best in class 4.

## R6. Deviations, and why

1. **No in-scheme pay item exists on live payobook's company 5** — none of its schemes has a
   contract-component rule, and every demo-world contract has a line for every saved pay
   item (G23). The live check's "in-scheme change" therefore used a pay item already on the
   person's contract (the §4.2 exception path); the off-scheme value used a person with a
   scheme and no contract. A real "scheme item with no line anywhere" was proven in B6 and on
   the local walk (local-only rule).
2. **`file_schemes` (new read-only method):** head-counts were only possible when the
   identity column was recognised on read; a person who picks "Work email" by hand now gets
   the counts too. Not in the handover; small, read-only, tested in B7.
3. **The sheet's notes go on a new "Read me" sheet** after "Records": the exporter had no
   notes area. The import reads the "Records" sheet by name, so round trips are unchanged
   (B7b). Grey fill done (hook = 10 lines in `export_records`).
4. **`eraser` icon is drawn in `updates_review.js`** (same Lucide path, same 24-unit grid)
   rather than added to `pb_import_kit`, so this phase deploys two modules, not three.
5. **"Goes to" stays a native select.** A group's "second line" is not possible inside an
   `<option>`, so "Used by several pay schemes" options read "Transport · Monthly staff, Daily
   rate" (the prototype's own select is native too). Typing to search works across groups.
   "Other pay schemes" is a disabled, empty group used as the divider.
6. **1280/1440 widths:** the Claude-in-Chrome window resize did not change the page's CSS
   width (it stayed 1,920 px); Chrome DevTools MCP was held by another session (G20).
   Narrow widths were checked by constraining the content column to 1,030 and 1,190 px (the
   content width at 1280 and 1440 with the side rail): no sideways scroll, rows one height.
7. **`CLEAR` is not translated:** `_("CLEAR")` exists (and is honoured), but its Vietnamese
   msgstr is "CLEAR", because the sheet's notes and the match screen tell people to type
   CLEAR in every language.
8. **P1 tests pinned to "no scheme known"** (G24) so T18 keeps testing what it was written for.
9. **An undone update's Past-updates note** shows "Put back …" only, not the skipped count
   (the skipped line shows while it is applied, and on the done screen).

New gotchas → ledger G20–G24; new facts U17, U18; G16 marked fixed.

## R7. Phase 2c research (from the code; live queries read-only)

**1. Which pay-run mode the active schemes use, and which one-off store each reads.**
The mode is chosen per RUN, not stored on the scheme. Application-data mode needs
`hr.formula.config.application_data_enabled` + `application_effective_from`
(`pb_hr_payroll_formula/models/application_payroll_source.py:201,203`, constraint
`:218-222`) and is used when the wizard skips the file (`pb_payrun_wizard/models/
application_payroll_wizard.py:114`, run stamped `:139`; payslip check
`application_payroll_source.py:1053-1055`). Monthly-template mode has no scheme field: the
run is started from Templates (`pb_payroll_templates/static/src/templates.js:173`) and the
server builds `Payobook-month-YYYY-MM.xlsx` (`templates.py:1131-1146`, recognised by name
`:1184-1191`). Everything else is the plain pay file / no file (`hr_payslip_formula.py:198`).

| Mode | Store it reads | Chain |
|---|---|---|
| Application data | `hr.payroll.period.input` | `hr_payslip_formula.py:190,197` → `payroll_period_input.py:479-487` → `application_payroll_source.py:1065-1071` → `:725,753` → `payroll_period_input.py:404-457` (search `:417-420`, value `:450`) |
| Monthly template | `pb.payroll.month.inputs` | `templates.py:1146` → `_engine_file :1002` → `_current :525-530`; recompute `:1193`, `:1211-1212` |
| Plain pay file / no file | none | — |
| Any mode, after compute | `pb.oneoff.feed` pushes approved awards | `oneoff_feed.py:440-470` |

| Database | Active schemes | Modes in use | Store read |
|---|---|---|---|
| payobook | 15 (VPTQ End/Mid 5–6, demo divisions 42–53, Scale Demo 89) | plain/no file (10 of 10 runs that record a scheme); app-data flag NULL on all; 0 template batches | none in use |
| payobook_template | 0 | — | — |
| p0clone | 0 | — | — |
| rize | 4 (7118 VN, 7119 IN, 7120 SG, 7121 ID) | both: app-data enabled from 2026-08-01 (4 TEST runs) and monthly template (4 TEST runs); real October run 1591 on archived scheme 4760 used the template file | period inputs (2 approved) and month inputs (574 rows; 60/27/2/122 for 2026-08 on the active four) |
| sudima | 0 active (1 draft) | — | — |

So only rize uses stored one-offs today, and it uses both stores.

**2. `hr.payroll.period.input` before a run exists.** Yes: the period is `config_id` +
`date_from` + `date_to` (all required, `payroll_period_input.py:43-48`); no run link at
creation (`reserved_run_id` sealed, `:19,64`). Created `draft` (`:155-159`), needs `reason`
and `evidence_reference` (`:55-56,141`), same company/scheme, an input component
(`:136-139`), span ≤ 366 days (`:140`); one approved row per company/scheme/employee/
component/dates (`:104-109,262-268`); approve needs a pay-formulas manager
(`:127-130,253`), approved rows are frozen (`:167`). Dates match EXACTLY (`:418`). In
application-data mode a run with one approved row resolves it (`:450`), reserves it on
compute (`:487` → `:318-331`), consumes it when the slip is done/paid (`:504-506` →
`:333-348`), releases it on cancel/delete (`:499-502,509-512`). Any draft row is a
`conflict` (`:432-434`) → blocker (`application_payroll_source.py:710-712`) that stops run
creation (`application_payroll_wizard.py:126-128`) and compute (`application_payroll_source.py:1073-1075`).
Plain-file and template runs never read this store.

**3. A "Scheduled" state on `pb.records.apply`.** Selection `records_approval.py:59-65`.
Python switches on state/applied at `records_approval.py:123,125,310,315,320,326,345-347`;
`records_learn.py:64,92`; `pb_records_desk.py` apply answer `:1906-1907`, undo row
`:1955-1956`, history `:2061-2068`; `pb_updates/models/updates_desk.py` `_batch_state`
`:575-588`, `_batch_row` `:595,612-613`, `undo` `:651,656-659` (line numbers before this
phase's insertions); `pb_hr_payroll_formula/models/payroll_preparation.py:211-214` (not
applied = pending) and `:551-553` (`state in ('draft','pending')` — a Scheduled row would slip
through unless added). Screens: Records History `pb_records/static/src/xml/records_desk.xml:756-790`
+ toast `records_desk.js:626-640`; Updates Past updates `updates_desk.xml:83-84`,
`updates_desk.js` tone/icon maps and note (unknown state falls back to muted/info);
`pb_payrun_wizard/static/src/js/payroll_review.js:332-333` opens the standard form; the
engine calls `_approval_apply` at `biz_approval_workflow/models/engine.py:1117`.
**`undo_apply` cannot cancel an unwritten apply today:** it never checks `applied`; an
unwritten apply has no `change_ids`, so it creates an empty undo row, marks the source
`undone`, returns ok with 0 restored, and leaves `state` and the approval request alone —
`_approval_apply` ignores `undone`, so **the change would still be written later**. Only the
screens prevent this today (live: sudima has 2 `pending` applies with `applied=false`).
P2c needs a real cancel path.

**4. Proration / automatic back pay.** Off everywhere: `use_proration` true on 0 schemes and
`use_auto_retro` true on 0 schemes, in any state, on all five databases (payobook flags are
NULL on schemes 42–89). Application-data mode also refuses a scheme with proration on
(`application_payroll_source.py:733-734`).

SQL used (read-only): `SELECT id,name,state,company_id,application_data_enabled,
application_effective_from,use_proration,use_auto_retro FROM hr_formula_config WHERE
state='active'`; runs with their schemes from `hr_payslip_run`/`hr_payslip`; template batches
from `hr_payroll_import_batch WHERE import_filename LIKE 'Payobook-month-%'`;
`pb_payroll_month_inputs` grouped by scheme/period; `hr_payroll_period_input`;
`pb_incentive` by state; `pb_records_apply` by state/applied/undone; counts of
`use_proration`/`use_auto_retro`. Unverified: the template switch is read from front-end
code; payobook's no-file runs were checked through import-batch links only.

## 8. Needs an owner decision / owner action

1. **payobook's pay schemes have no pay items of their own.** On Payobook Vietnam JSC every
   pay item is "Kept on contracts only", and every demo contract carries every one of them,
   so the greyed "not in their pay scheme" cells will almost never appear in a demo there.
   If you want to show this feature in a demo, a pay scheme needs its own pay items (a
   setup task, not code).
2. **A person can count under two schemes** (end-of-month and mid-month advance) — the strip
   shows both chips with the same people. That is what the scheme map says; say if you would
   rather see only the "who pays this person" scheme in the chips.
3. Carried over from P2a: QA sign-in in the browser by the owner; G17 (a typed manager name
   that matches nobody proposes a new employee).
4. The live check left one more "Undone" update ("P2b live check") in payobook's Past
   updates; say if you want these removed.
