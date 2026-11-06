# FILLIN P2 — the screens: Yes/No and words, "Filled in by Payobook", To check

Read `docs/handovers/fillin/FILLIN_LEDGER.md` first (rules §0, facts §1,
decisions §2, gotchas §3), then `FILLIN_P1_REPORT.md` — **where the P1 report
names a field or method differently from this document, the report wins.**

P1 shipped (server): `hr.contract.advantage.pb_fill / pb_checked_by /
pb_checked_at`; `hr.contract.pb_fillin_unchecked()` (returns a recordset —
wrap it, return ids/rows over RPC) and `pb_fillin_check(line_ids=None)`
(returns int; raises `AccessError` for non-managers — its rule is
`_pb_fillin_may_check`, mirror it for every new write RPC instead of
`_cd_may_write`); change-log sources `auto_default` and `checked`;
`hr.formula.rule.value_labels` with `value_label_options()`,
`value_label_for(amount)` and **`value_label_control()` → 'toggle' |
'select' | ''** (use this to pick the editor, do not re-derive the {0,1}
rule in JS); rize scheme 7121 seeded with usual answers and words. Read
FILLIN_P1_REPORT.md §6 ("Facts P2 needs") in full — it also tells you that
the History tab today prints every unknown source as "From a pay data file"
(`_cd_change_sentence`, `pb_contract_360.py:1073-1087`), which A4 fixes.

## 1. Scope — six surfaces, in this order (one commit + deploy per block)

### Block A — contract panel (pb_contracts) + lessons
A1. **Words instead of money.** On the Components tab a row whose rule has
    `value_labels` (or `value_kind == 'boolean'`) shows the word, never
    "Rp1": `Yes`, `No`, `Insurance-premium tax only`… A row with labels
    {0,1} edits as a **toggle**; any other label set edits as a **pick-list**
    (`CdEditor` kinds `toggle` / `select` with `options`, exactly as the
    YES/NO contract fields do — `pb_contract_360.py:110-111, 718`). A rule
    with `value_kind` integer/quantity and no labels shows a plain number,
    no currency sign. Money stays money.
A2. **"Filled in by Payobook" tag.** A line with `pb_fill == 'auto'` shows an
    amber tag `Filled in by Payobook · not checked` when unchecked, and a
    muted `Filled in by Payobook · checked by <name> on <date>` when checked.
    The row keeps its existing source tag.
A3. **Looks right.** When the contract has unchecked lines, the Components
    tab header shows one quiet line: `Payobook filled in 3 answers for this
    contract.` with a button **All correct** (ghost, `check` icon). Pressing
    it calls `pb_fillin_check()` and reloads the panel. Editing a filled-in
    line and saving un-marks it (server already does this) — the panel just
    reloads. Hidden for readers without write rights (`can_write`).
A4. **History tab** sentences for the two new change sources: "Filled in by
    Payobook from the scheme's usual answer" and "Checked by <name>, no
    change" (`pb_contract_360.py:1073-1087`).
A5. **Lessons.** The Learning replica of the contract panel
    (`pb_learn/static/src/engine/screens.js` around `:595-700`,
    `data-coach="rep-cd-comps"`; fixture `fixture.js:966`) shows components;
    if it shows any flag-like value as money, show it as a word, and add one
    "Filled in by Payobook · not checked" tag to one row so the lesson
    matches the screen. Bump `pb_learn` patch version (the deploy gate needs
    it — see the comment at the top of `pb_learn/__manifest__.py`).

### Block B — Contracts board "To check" (pb_contracts) + employee chip (pb_employee_vault)
B1. **View tab "To check N".** New built-in view on the Contracts roster
    (`_pbf_builtin_views`, `pb_contracts.py:223-231`). A built-in view can
    only carry `filters`, so add a **hidden choice section** `fillin`
    (precedent: `pb_contract_lifecycle/models/pb_contractlife.py:488-500`)
    with one option `unchecked` whose domain is
    `[('advantages_ids', 'any', [('pb_fill','=','auto'), ('pb_checked_at','=',False)])]`.
    The tab goes after "Running". Count refreshes after an action (kit 1.3.0).
B2. **Card.** `_contract_row` (`:234`) adds `fillin: {n, answers: [{label,
    value_text}]}` for unchecked lines (label = rule/template name, value_text
    = the word via `value_label_for`, else the number). The card
    (`static/src/xml/contracts.xml:51-70`) shows, under the period line, an
    amber chip `3 answers to check` and, on the To check view only, the
    answers inline as small chips: `BPJS TK covered: Yes · BPJS health
    covered: Yes · Tax allowance mode: Insurance-premium tax only`, plus two
    small buttons **Looks right** (calls `pb_fillin_check` for that contract,
    then `loadPage()` + head reload) and **Change** (opens the contract
    panel on the Components tab — add an optional `tab` prop to
    `Contract360Drawer`, default `terms`). Clicking elsewhere on the card
    still opens the panel.
B3. **All look right.** On the To check view, a toolbar button `All N look
    right` opens a confirm dialog that states the count and names the first
    five people ("…and 12 more"); on confirm, calls a new
    `pb.contracts.fillin_check_all(domain)` that checks every unchecked line
    of the contracts matching the current filters/search, in the caller's
    rights, and returns how many. Toast: "Checked 17 contracts."
B4. **Employee panel chip.** New chip component in `pb_employee_vault`
    (registry `pb_employee_360_chips`, clone
    `pb_scheme_map/static/src/js/scheme_map_chip.js`): amber `3 answers to
    check`, tooltip "Payobook filled these in from the scheme's usual
    answers when the contract was created. Open the contract to check or
    change them." Server: `pb.people.fillin_pending(employee_id)` →
    `{n, contract_id}` over the person's draft/running contracts; silent ORM
    call; renders nothing when n == 0. The chip is a `<button>` that calls
    the drawer's `openContract()` — pass it through `chipProps` as
    `onOpenContract` (`employee_360.js` `get chipProps`, `:66-72`; keep the
    props object stable per empId as the comment there demands).

### Block C — pay run (pb_payruns + pb_payrun_wizard) + studio (pb_formula_studio)
C1. **Run card advisory.** `_run_checks` (`pb_payruns.py:2340`) gains an
    amber **advisory** entry `{key: 'fillin', icon: 'clipboardCheck'}`:
    text `3 people have answers Payobook filled in that nobody has checked`,
    detail `BPJS and tax settings were filled in from the scheme's usual
    answers when their contracts were created. Check them once; the run can
    still go ahead.`, owner HR, `next` = a door to the Contracts roster on
    the To check view (`ir.actions.client` tag `pb_contracts` with
    `params.view='fillin'` — add that param handling in `contracts.js`
    where `?contract=` is read, `:63-70`). Count = distinct employees of the
    run's payslips whose contract has unchecked lines; fed at `:547-551`
    like `unsourced`. Advisory ⇒ does NOT make the run unready.
C2. **Wizard preview.** `scheme_preview` (`pb_payrun_wizard.py:543-569`)
    adds `'unchecked': n` (people among `covered` with unchecked lines).
    Template `payrun_wizard.xml:86-103` area: under the covered count, a
    muted line with a `clipboardCheck` icon: `3 of them have answers Payobook
    filled in that nobody has checked` + link "Open the Contracts list"
    (same door as C1). Hidden when 0.
C3. **Studio: the usual answer and the words.** In the inline component
    editor (`studio.xml:1299-1300`, draft via `setDraftField`
    `formula_studio.js:2873`): relabel "Default value" → **Usual answer for
    a new contract** with help text `Every new contract for a person this
    scheme pays starts with this value. Leave 0 for none.`; when
    `is_contract_component` and the draft has `value_labels` with {0,1},
    render a Yes/No toggle; with other labels a pick-list; else the number
    input. Add a field **Words for each value** (text input, placeholder
    `0=No;1=Yes`) shown for input rules. Server: NEW file
    `pb_formula_studio/models/studio_fillin.py` with `_inherit =
    'pb.formula.studio'` that (a) extends `_EDIT_FIELDS` with
    `'value_labels'` (class attribute, `super()._EDIT_FIELDS + (...)` style)
    and (b) overrides `get_component_edit` to add `value_labels` and
    `value_kind` to the returned dict. **Never edit
    `pb_formula_studio.py`.** Also show, on the scheme's components list
    where a contract component is listed, the usual answer as a word when
    labels exist (find the list cell that prints `default_value`; if there
    is none, skip and say so).
C4. **Pay data file note (optional, small).** The Employee records column
    note for a rule with labels gains one sentence listing them
    (`1 = Yes, 0 = No`). Find where the column note is written for the
    monthly workbook (`tools/prepare_rize_sg_id_master.py:166` is the seed
    script, NOT the generator; grep `note` in `pb_payroll_templates`). If it
    is more than ~20 lines, skip and report.

### Non-goals
* No change to how values are computed, imported or exported (numbers stay
  numbers).
* No bulk "check" anywhere except B3, and B3 always confirms with the count.
* No new menu entry or standalone screen: review lives on the Contracts
  roster and the contract panel.
* No `abm`.

## 2. Plumbing — verified, do not re-derive

(FILLIN_LEDGER §1 holds the rest.)
* Panel rows carry `value_kind` already (`pb_contract_360.py:832, 882`);
  add `value_labels` (parsed list) and `pb_fill`, `pb_checked_by_name`,
  `pb_checked_at` to `_cd_comp_row` (`:802`). `compEntry`
  (`contract_360.js:862`) decides the editor kind: extend it to `toggle` /
  `select` / `integer` from the row. Row tags: `contract_360.xml:137-140`.
  Panel load: `get_contract_360` (`:498`); save: `save_contract_360`
  (`:1562`) — "All correct" is a separate RPC, not a save.
* Rights: mirror `_cd_may_write` (`:245-260`) for every new write RPC.
* Contracts roster: `pb.contracts` board (`pb_contracts.py`), spec
  `_pbf_spec :171-190`, views `:223-231`, row `:234`; page RPC
  `get_contracts_page`; JS `contracts.js` (deep link params `:63-70`,
  `loadPage :95`, drawer props `:84`).
* Filter kit facts: a hidden section is never listed but its option chip
  names it while on; builtin views carry filters only; the kit remembers
  the last view key per browser session (CONTRACTLIFE report).
* Chip seam: `employee_360.js:52-72` (`extraChips`, `chipProps`), XML
  `employee_360.xml:28-41`.
* Pay run: `_run_checks :2340` (entries `{key, tone, icon, text, detail,
  owner, next, advisory, more}`; rose = not ready; advisory never blocks),
  fed at `:547-551`. Wizard: `scheme_preview :543-569`; JS
  `payrun_wizard.js:754-774` (`state.scheme.preview`); XML `:86-103`.
* Studio: `_EDIT_FIELDS` `pb_formula_studio.py:2600-2608`, used at `:2665`;
  `get_component_edit :2611`; editor XML `studio.xml:1296-1301`; JS
  `formula_studio.js:2873`.
* Icons: each module's `ic()` helper (Lucide). Check `clipboardCheck`
  exists in the icon set used by that module; else use `check` / `listChecks`.
* Lessons: `pb_learn` replica + fixture as in A5; "lessons follow screen
  changes" is a standing rule.

## 3. Safety rails
* Every new RPC that writes re-checks rights server-side; never trust
  `can_write` from the client.
* `fillin_check_all` applies the SAME domain the roster used (`pbf_domain`
  from the kit) so nobody checks a contract they cannot see.
* Words come from the rule's labels only; never invent a label in JS. A
  label missing for a value shows the number.
* No `.po` regression: new strings EN + VI, PO parse gate before deploy.
* Browser validation on rize for every block, console read, screenshots in
  `docs/handovers/fillin/p2_shots/`.

## 4. Test cases

| # | Case | Expect |
|---|---|---|
| T1 | rize, open an Indonesia contract panel › Components | the four flags show words (Yes / No / Insurance-premium tax only…), no "Rp" |
| T2 | edit BPJS TK covered | toggle; Tax allowance mode → pick-list with three words; Save writes 1/0/2 (check via psql) |
| T3 | a contract with unchecked lines (create one in a rollback-free way: pick an Indonesia person without a running contract from the P1 smoke list and create a draft contract through the New contract button on rize — tell the owner which person; delete nothing) | amber tags on the filled lines; header line "Payobook filled in N answers…"; **All correct** stamps them; tags turn muted with name/date; History shows both sentences |
| T4 | Contracts roster › To check tab | count matches psql; card shows chips with the answers; Looks right clears the card and the count drops; Change opens the panel on Components |
| T5 | All N look right | confirm names count and people; after confirm the tab reads 0; toast |
| T6 | employee panel for that person | amber chip "N answers to check"; click opens the contract panel; after checking, no chip |
| T7 | pay run card for a run including that person | amber advisory line, run still "ready"; the door opens the roster on To check |
| T8 | new pay run wizard › pick the Indonesia scheme | "N of them have answers…" line; hidden when 0 |
| T9 | studio › scheme 7121 › open BPJS TK covered | "Usual answer for a new contract" is a Yes/No toggle showing Yes; Tax allowance mode a pick-list showing Insurance-premium tax only; "Words for each value" editable; saving round-trips (psql) |
| T10 | rights: a user with HR but not contract-manager rights | sees tags, no All correct / Looks right / All look right; the RPCs refuse |
| T11 | console clean on every screen above; screenshots saved |
| T12 | lessons: the practice contract panel shows the word and the tag |

## 5. Deploy
Per block: commit, push `19.1`, announce (ask the coordinator to announce if
`ListAgents` is unavailable to you), `filter_deploy.sh full` with the block's
modules on the four DBs, START/DONE lines, versions verified. Bump every
touched module's patch version.

## 6. Report (`docs/handovers/fillin/FILLIN_P2_REPORT.md`)
T1–T12 with evidence; deploy evidence; the contract you created for T3 (who,
id) so the owner can decide to keep or delete it; deviations; proposed
ledger gotchas; 5-line plain-English summary.
