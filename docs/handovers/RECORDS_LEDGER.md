# RECORDS — conventions + gotcha ledger

**Program (started 2026-08-29):** one-time pay data + the Records Desk (bulk update · export ·
import) over the pay scheme's MAPPED record fields. Owner-approved brief:
`~/.claude/plans/i-want-you-to-peaceful-popcorn.md`. Phases: **R1** "This run only" pay data ·
**R2** Records Desk (grid, filters, apply/undo, People door) · **R3** export/import round trip +
remaining doors · **R4** (conditional) defect round + close-out.

Module versions at program start: **pb_hr_payroll_formula 19.0.1.100.0 · pb_payrun_wizard
19.0.1.13.0 · pb_import_batch 19.0.2.0.0 · pb_formula_studio (see manifest) · pb_people (see
manifest)**. `om_hr_payroll` stays untouched (CR1).

**`C18` (docs/FORMULA_ENGINE_CONVENTIONS.md), `MJ1–MJ52`, `S1–S20`, `CR1–CR33`, `MF1–MF41` STILL
BIND.** This file adds `RD`-numbered entries and restates only the rules that are load-bearing
every single time.

---

## Standing rules (bind every phase)

- **The design bar is binding and is scored in every phase report** (C18.145): *extreme WOW,
  intuitive, out-of-this-world, best in class* — a named hero moment; zero dead-ends (empty,
  loading, error, partial, huge states all designed; every failure names its reason and its next
  step); plain language over code vocabulary; motion with purpose; keyboard + bulk ergonomics
  where rows are involved; measured against the best SaaS tool in the category, not stock Odoo.
  Lucide/SVG icons, never emoji.
- **White-label absolute.** No user-visible string may contain "Odoo" — labels, chips, tooltips,
  help text, placeholders, empty states, error/toast messages, menu and action names, field
  `string=`/`help=`, selection labels, reports, exported files, `.po` msgstr. Use **Payobook** or a
  neutral term. Never rewrite technical identifiers (`from odoo import`, model/XML ids, `odoo-bin`,
  addon names, log messages, code comments, engineering docs including this one).
- **Neutrality rail on every phase that touches the batch.** A normal (non-one-time) batch must
  produce byte-identical `formula_input_values` before and after; prove it with an md5 in the
  test AND a "branch never entered" counter (S3/J9 pattern, `_sourcing_*_counter` precedent in
  `payroll_import_batch.py`).
- **Never call `action_process` in a test against live data.** Writeback code is exercised on
  records the transaction created (J3/J10 rule).
- **Terse output.** One-line bash where possible; never dump file contents into the chat.
- **Commit per phase**, explicit file staging (never `git add .` — `ABM/*.xlsx` are the owner's
  working files and stay unstaged), reviewer-focused message, **do not push**.
- **Asset cache.** Any JS / SCSS / OWL-XML change ⇒ bump that module's manifest version and `-u`
  it; a manifest `assets` list change needs a full service RESTART (C18.53); SCSS errors surface
  only at page load (MF12). Clear `/web/assets/%` per DB after JS/SCSS changes.
- **Deploy contract** (CLAUDE.md): ONE addons dir `/odoo/odoo-server/addons`; clean staging dir
  first; per-module `rsync --delete` scoped to the module dir, NEVER to the addons root. Deploy
  **abm first**, validate there, then **payobook + payobook_template**. **acme is excluded**
  (owner ruling 2026-08-26). Verify tree hashes AND `ir_module_module.latest_version` per DB.
- **Tests run scoped**: `-u <mods> --test-enable --test-tags /<mod>,/<mod> --stop-after-init`
  (C18.40), backgrounded, poll the log, kill by PID (C18.54). Take the baseline yourself first
  (MJ11); 3 pre-existing reds are known (`TestBankDestinations.test_09`,
  `TestEndpointFieldCatalogue.test_05c`, pb_integrations `TestLedgers.test_the_ledgers_never_sudo`).
- **Live validation uses abm.** Login ash@biztinct.com / J5validate!2026 (verify first; the
  documented apex password does not authenticate over RPC — CR33 — so drive live checks through
  the authenticated Chrome-MCP session, `fetch('/web/dataset/call_kw', …)` from inside the page).
- **Plain English on every surface** — the screen's vocabulary, not the code's.

## RD ledger

(Entries added by each phase report. Numbering continues across phases.)

### R1 (2026-08-29)

1. **`hr.contract.create` already gives a new contract one advantage line per EXISTING
   template** (`om_hr_payroll/models/hr_contract.py:107-113`). A fixture that creates the
   template and then creates its OWN `hr.contract.advantage` line ends up with TWO lines for
   one code; `_get_contract_advantage_map` keys by code and the reader silently picks one of
   them. Create the template FIRST, create the contract, then WRITE the amount onto the line
   the contract already has. (Cost one red test on the first live run.)
2. **The baseline md5 has to be taken with the SAME test file, on the pre-change checkout.**
   The R1 test imports `ONE_TIME_NO_EMPLOYEE` from the model, which does not exist at HEAD, so
   the file cannot simply be run there. The working recipe: generate a *probe* copy (strip the
   import, keep only the neutrality case, log the md5 with `_logger`, never `print` — stdout
   goes to `/dev/null` when odoo-bin is backgrounded with `--logfile`), drop it into the
   server's `tests/` with one appended `from . import …` line, take the baseline run, then
   restore `tests/__init__.py` from the backup and delete the probe. Recorded md5 for R1:
   `78b40cab23740f61b20629a9be9fd4df`.
3. **Never `pkill`/`pgrep -f` a pattern that appears in your own remote command line.**
   `ssh host 'pkill -f stop-after-init'` matches the remote shell running that very command and
   kills the ssh session: the symptom is a bare `Exit code 255` with nothing done. Capture the
   PID in a separate call and `kill -9 <pid>` (C18.54 with the extra clause).
4. **`odoo-bin -u` refuses more than one database**: `-d payobook,payobook_template -u …` exits
   2 with "Cannot use -i/--init or -u/--update with multiple databases". One `-u` run per DB.
   Worse, when the invocation is backgrounded with `nohup … &` the failure is invisible — no
   logfile is ever created and the site stays DOWN. Run deploy upgrades through a **foreground**
   ssh (backgrounded on the *local* side) so the exit code and usage error come back.
5. **A `<odoo>` root element is not a white-label violation**, and neither is `✕` (U+2715, the
   close button) or `→`. A "no Odoo / no emoji" source assertion must strip the document element
   and XML comments first, and must define emoji as the pictograph planes + anything followed by
   U+FE0F + a named list — not "the whole symbol block". The broad version fails on the wizard's
   own close button and only teaches the next engineer to delete the assertion.
6. **On abm, a spreadsheet row matches an employee by `identification_id`/`barcode`, not by the
   source system's code.** Employees carry `pb_source_ref = '3:<zoho id>'` but an *excel* batch
   does not produce that ref (the config's `connector_id` is unset — the standing owner debt
   from JOURNEY), so a file keyed on the Zoho Employee Code matches nobody. In a one-time run
   that is *correct behaviour* and it lands as the R1 exception sentence; for live validation,
   key the file on `identification_id`.
7. **The pay-run wizard's employment-status panel ("Run for just a few people…") does not always
   render** — on one reload abm showed 42 eligible with the status chips, on the next 152 with
   no chips and no picker. Pre-existing (VALUEKIND P4 surface), unrelated to R1, but it means a
   UI-driven live validation can suddenly be about to compute the whole workforce. Drive
   `attach_spreadsheet` through `call_kw` on a run you created yourself when you need a
   one-person blast radius.

### R2 (2026-08-29)

8. **`_log_contract_component_change` cannot be called on a `.new()` probe.** It writes
   `'import_batch_id': self.id`, and `self` on a probe is a `NewId` — which cannot be stored,
   so the create raises. The Records Desk files the identical `hr.contract.advantage.change`
   row itself, minus that one key, with `change_source='manual'` and
   `notes='Records Desk apply #<id>'`. Anything else that reaches the batch helpers through a
   probe must be read for `self.id` before it is used.
9. **`write_date` is the TRANSACTION timestamp, not the row's.** Odoo defaults it to SQL
   `now()`, and PostgreSQL's `now()` is the transaction start — so every row written anywhere
   in one test carries the same stamp and `assertNotEqual(rec.write_date, before)` can never
   pass. "Did this record change" is asked of the VALUES and of the audit trail
   (`pb.records.change` has no row for it), never of `write_date`. Cost one red test.
10. **`0.0 in (None, False)` is `True` in Python.** The emptiness test `raw in (None, False)`
    therefore blanks every ZERO — on the live walk it made a whole Basic Salary column read
    empty when every contract holds 0. MJ15 says `0` is a value; test it with
    `isinstance(raw, (int, float))` or `raw is None`, never with `in`.
11. **A per-person question over a 4,500-person roster is a 147-SECOND page fetch.** The first
    Records Desk counted its four facet groups by walking the match set in Python and asking
    each employee for its latest contract state (`employee.contract_ids.sorted(...)`), four
    times, on every page. Measured on payobook: 147s for one page of 100. Two rules came out
    of it, both now in `pb_records_desk.py`: (a) a per-person fact is read ONCE for the whole
    roster into a dict (`_ctx_states`, one `search_read` over contracts) and every filter and
    facet reads that dict; (b) the FACETS are computed only when asked for — the client sends
    `with_facets` on the first page and never again as the window moves. After: 488ms with
    facets, 125ms without.
12. **A "virtualised" grid whose scroller is not height-constrained renders everything.**
    The window size comes from `clientHeight`, which is only meaningful when an ancestor caps
    it; drop the component into a host that does not (a hoot fixture, a print stylesheet) and
    the scroller grows to its own content, `clientHeight` becomes 207,000px and all 4,500 rows
    land in the DOM. Cap the window (`MAX_WINDOW = 120`) rather than trusting the measurement.
    The hoot test is what caught it, because a test fixture IS that host.
13. **`sanitize_acc_number` returns a TUPLE `(number, damaged)`**, not a string
    (`bank_account_util.py:49`). Unpacking it as a string gives `"('123', False)".strip()` and
    an `AttributeError` three frames away. The `damaged` half is the useful one: a value that
    WAS there and cannot be trusted is refused with a sentence rather than silently dropped.
14. **A cell editor's `keydown` must `stopPropagation`, or the grid re-reads the same key.**
    The editor commits on Enter and closes; the SAME event then bubbles to the grid, which is
    listening for Enter as "start editing" and — the editor now being closed — opens one on
    the next row. Symptom on the live walk: every Enter left a stray editor open below. Every
    key an editor handles stops there (`RdCellEditor.onKey`, `RdPicker.onKey`).
15. **A typed OPTIONAL OWL prop still rejects `null`** (W35, hit again). `lookupFor(col)`
    returned `null` for a column with no typeahead and every non-many2one editor died on
    "Invalid props for component 'RdCellEditor': 'lookup' is not a function". Return
    `undefined` — that is the only value OWL reads as "absent".
16. **An XML comment may not contain `--`.** A `<!-- ===== header ===== -->` banner drawn with
    dashes is not well-formed XML and the OWL template file fails to parse — which surfaces as
    a dead cockpit, not as a syntax error. Use `=` for rules inside comments, and parse every
    new template file locally (`xml.dom.minidom.parse`) before deploying it.
17. **Clearing `/web/assets/%` is NOT enough after changing a JS/SCSS file** — Odoo caches the
    built bundle in the worker process, so the next request re-serves the old one from memory
    and the browser sees no change at all (no manifest edit needed for this; C18.53's restart
    rule is broader than it reads). Ritual after every asset edit: rsync, delete the
    attachments, `service restart`, hard reload.
18. **`res.company.create` links the new company to whoever created it**
    (`base/models/res_company.py:311`). A test about NOT seeing another company's employees has
    to `write({'company_ids': [(3, other.id)]})` on `env.user` and invalidate, or `env.companies`
    silently contains the company the test is trying to be outside of.
19. **hoot specifics R2 paid for**: `mountWithCleanup` boots the full web env, which
    fetches the mail store — without `defineMailModels()` every mounting test dies on
    "could not get model discuss.channel". `toBeTruthy` does not exist (use `toBe(true)` or
    `toHaveLength`). `click(el, {ctrlKey: true})` does not carry the modifier to the handler —
    dispatch a `new MouseEvent("click", {bubbles: true, ctrlKey: true})`. A component that
    listens for keys on itself must be `.focus()`ed before `press()`.

### R3 (2026-08-29)

20. **`openpyxl.load_workbook(read_only=True)` throws the cell COMMENTS away.** A read-only
    worksheet hands back `ReadOnlyCell`s, and a `ReadOnlyCell` has no `.comment` — which is
    exactly where a column's technical identity (`id: f:hr.contract:shuipart`) lives, and
    therefore the whole reason a retyped heading still lands on the right field. The R3 handover
    specified `read_only=True`; the code loads normally instead, and the 10 MB size guard is what
    keeps that affordable. Same trap for `sheet_state` on the hidden sheet.
21. **`hr.employee.barcode` is validated: alphanumeric, no accents, at most 18 characters.** A
    fixture that mints readable badge ids like `R3-0001` dies in `setUpClass` with "The Badge ID
    must be alphanumeric without any accents and no longer than 18 characters" — and a
    `setUpClass` failure counts as ONE error and silently runs none of the class's tests, so the
    suite total barely moves and the failure is easy to read as unrelated. Use `R30001`.
22. **`field._description_selection(env)` returns a list of (key, label) TUPLES**, not the
    `{'key','label'}` dicts the desk's cards carry (`_selection_pairs` builds those). `p['key']`
    over the raw result is `TypeError: tuple indices must be integers`. Wrap it in `dict()`.
23. **A blank cell in a FILE is not the same gesture as an emptied cell in the GRID.** On the
    grid, clearing a cell means "clear this" (`_coerce` treats `''` as an explicit clear). In a
    file it means nothing at all — the column simply was not filled in. Treating the two the same
    makes dropping an exported blank template wipe every mapped field of everyone in it. Blank
    cells are counted (`cells_blank`, said on screen as "15 empty cells were left alone") and
    never staged.
24. **An identity heading may collide with a MAPPED field's label, and identity has to win.**
    ABM maps `hr.employee.work_email`, whose card is labelled "Work Email"; the identity column
    the export writes is headed "Work email". With label-matching ahead of identity, that column
    was read as a destination — its own comment ("Identity … It is never imported") became untrue
    and 15 unchanged emails counted as `same` changes. Order is: header comment → hidden sheet →
    the three STRICT identity labels → card label → the batch's looser identity spellings
    (`MSNV`, `emp code`) → ignored. Strict identity before label, loose identity after it: a card
    genuinely called "Code" must not be eaten by the loose list.
25. **A `<button>` inside a `<button>` is not valid markup, and the Journey's wire geometry walks
    `body.children` reading `dataset.id`** (`journey_board.js:387`). A node's secondary action is
    therefore a SIBLING `<div>` after the node button, carrying no `data-id` — `_measure` reads
    straight past it and the wires still land on the node.
26. **`dragenter`/`dragleave` fire for every element the pointer crosses**, so a boolean drop
    flag turns the overlay off the instant the file moves over the text inside the zone. Keep a
    DEPTH counter (`+1` on enter, `-1` on leave, reset on drop). The desk's whole-grid veil uses
    the other half of the same trick: ignore a `dragleave` whose `relatedTarget` is still inside
    `currentTarget`.
27. **`_t()` returns a LAZY `TranslatedString` that THROWS when evaluated before translations are
    loaded** ("Cannot translate string: translations have not been loaded",
    `translation.js:168`). Concatenating `_t` fragments into a sentence evaluates them, so a
    PURE function that builds a counted sentence works in the app (mounting loads translations)
    and dies in hoot. Call `patchTranslations()` from `@web/../tests/web_test_helpers` inside any
    test that calls such a function directly — at module level it cannot register its cleanup.
28. **One employee can hold the same string in two identity fields.** The row index is built over
    `barcode`, `employee_id`, `pb_source_ref` and `identification_id`; on ABM the badge id IS the
    id-card number, so a naive `bucket.setdefault(code, []).append(id)` lists that person twice
    and the row is refused as "2 people carry the code …". De-duplicate on the way in.
29. **Excel's list `DataValidation` is a FORMULA, and a formula is capped at 255 characters** —
    and its items are comma-separated, so a label containing a comma silently splits into two
    choices. A long or comma-bearing choice list gets NO dropdown (the header comment carries the
    values instead); a dropdown missing half its choices is worse than no dropdown.
30. **On ABM there is no mappable BOOLEAN destination**, so "set it to Yes" is exercised through
    a selection whose values happen to be `YES`/`NO` (`hr.contract.shuipart`). The boolean path
    itself is covered by the Python suite, which picks a writable boolean off the registry.
31. **`_get_latest_contract` per person is a four-MINUTE export on 4,533 people.** It sorts an
    employee's `contract_ids` in Python AND writes an INFO line naming the candidates, once per
    call (`payroll_import_batch.py:2950`) — the grid never noticed because it pages 100 at a
    time, and the export is the one surface that walks the whole roster. RD11's rule (a) applies
    unchanged: read the fact ONCE for the whole set. `_io_contracts` does it in one `search_read`
    and picks the winner with the SAME key (`date_start or date.min`, then id) — in Python, not
    in `ORDER BY`, because PostgreSQL sorts NULLs LAST ascending while that method sorts a
    date-less contract FIRST, and the two disagree precisely for the contract with no start date.
    Measured on payobook, 4,533 people × 31 mapped columns: **>4 minutes → 8.7 s** (113 KB
    workbook); the blank template is 0.6 s. The bank read needs its own prefetch
    (`employees.mapped('bank_account_ids')`) — it walks a second o2m that the contract prefetch
    does not cover.
32. **An `ir.actions.client` XMLID resolves to a DIFFERENT numeric id on every database.** On abm
    `pb_records.action_pb_records_desk` is action 883; on payobook 883 is the "Pull Data with
    Options" wizard and the desk is 1343. A `/bizapp/action-<id>` deep link copied between
    databases silently opens somebody else's screen. Resolve the XMLID through `ir.model.data`
    per DB before driving a live check.
33. **A round trip over ALL 42 of ABM's mapped fields reports exactly one change, and it is a
    DATA defect, not a code one.** Employee "HR ADMIN" carries a Date of Joining in the year 24
    (`0024-12-01`), and glibc's `strftime('%Y')` — which is what `fields.Date.to_string` uses,
    and therefore what `_mapped_record_value` returns — does NOT zero-pad, while
    `date.isoformat()` does. The desk shows `Date of Joining: 24-12-01 → 0024-12-01`. Applying it
    writes the identical date, so nothing is at risk; the comparison lives in R2's `_same` and is
    left alone for one corrupt record. **Owner debt: fix that employee's joining date.**
34. **ABM has two employees carrying the same id-card number** (`066196005153`, one of them LINH
    DO), so a file keyed on it lists that row as "2 people carry the code … — this row cannot say
    which one" rather than guessing. Correct behaviour, and the round trip is how it was found.
    **Owner debt: one of those two codes is wrong.**
