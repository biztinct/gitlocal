# SOURCING — closeout

**Programme complete. Six phases, live on abm · acme · payobook · payobook_template (2026-08-25).**
Read this instead of the six phase reports. Detail: `SOURCING_DESIGN.md` (design + phase split),
`SOURCING_LEDGER.md` (conventions + gotchas S1–S27), `SOURCING_PHASE_S{1..6}_HANDOVER.md`.
**The owner's guide is `SOURCING_WALKTHROUGH.md`** — written for a reader, not an engineer.

Final module versions: **pb_hr_payroll_formula 19.0.1.78.0 · pb_formula_studio 19.0.1.129.0 ·
pb_integrations 19.0.1.12.0 · pb_workforce_payroll_bridge 19.0.1.2.0 · pb_trip_payroll_bridge
19.0.1.1.0** · om_hr_payroll 19.0.1.0.2 (never touched — CR1).
Commits: S1 `6724892c` · S2 `d074ce9f` · S3 `c960d022` · S4 `59835a8f` · S5 `3e273842` · S6 = the
commit carrying this file. **Nothing is pushed.**

---

## The question this answered

*"Where does this number come from?"* — which the product could not answer about its own payroll.
Three things were broken and one was being thrown away:

- **API field mappings never fired.** The only code honouring them was gated on a `source_type` no
  loader produces. Every wire on the API board was decorative.
- **23 mappings had silently lost their component.** `ON DELETE SET NULL` fired in SQL; the board
  went on displaying the remembered code as though the wire were live.
- **"Excel mapping" was not a concept.** One overloaded Char carried spreadsheet headers, feed keys,
  sheet-prefixed names and column letters, with nothing to say which.
- **The answer already existed and was discarded.** The resolver computed `resolved_source` and the
  matched header key for every component of every employee, logged them for two hardcoded component
  names, and dropped them — roughly forty thousand times a run.

## What shipped, and the gate each passed

| Phase | Shipped | Gate |
|---|---|---|
| **S1** Provenance | `formula_input_sources` on the payslip; the `input_provenance` vocabulary (8 `src` × 18 `via`) and its single translation point; all three writers of `formula_input_values` write the sibling; the matched key captured on every path; adjustments recorded via `adj` | **Byte-identical** recompute, 1,883 input + 2,394 computed codes, md5 `b1dcd785…` |
| **S2** Severed + lineage data + gate | Remembering `target_rule_code`/`target_column_letter`; `is_severed`; the 4-tier repair; `legacy_component_code`; uncapped `_consumed_field_names` + stored `consumed_field_paths`; `output_key` constraint; widened connector gate | **23/23 repaired**, 0 remaining; full recompute a no-op; post-repair recompute byte-identical |
| **S3** Bindings + two sources | `source_binding` (+key/stamp), `binding_dangling`; `raw_data_topup_json` + `source_origin`; merge-not-unlink top-up; binding-wins / fallback / ignored | **Byte-identical AND the bound branch entered 0 times** — two independent proofs |
| **S4** Every screen | `source` block on the serializer (declared + actual); shared `source_vocab.js`; chips on rail, card, Cell Editor, grid header, both boards | **0 overlaps** at 1440/1024; **zero writes** (checksum identical); payload +5.2% |
| **S5** Lineage + sealed + cockpit | "Derived here" lane; lineage popover; sealed calculated components (3 enforcement points); inline rule creation; cockpit reverse links; 4 health hints; S15 header fix | **0 overlaps at both widths, 0 codes truncated**; **14/14 orphan rules surfaced**; zero writes |
| **S6** The owner's three defects | One pill per fact (de-duplicating assembler + shared label sub-template); the Excel board writes a real binding and works with no file; a live wire is a declared source; lineage on the component; the owner's walkthrough | **0 duplicate pills / 0 overlaps** at 1440+1024, all five adapters, both hosts; **8 rule outputs surfaced on a board that showed none**; Excel binding proven end to end; **zero net writes**, neutrality md5 unchanged |

**The neutrality gate held across all six phases**: the same md5 (`b1dcd785739e1c0f49d304ee5428229a`)
before S1 and after S6, over every payobook import line.

### What S6 changed about the honest state above

S6 is the owner's review of the live result, and it moved two rows of the table below:

- **Bindings are no longer waiting for a mechanism, only for a decision.** S3 built them and nothing
  wrote one; S12 found `data_source_field` empty everywhere because the tab that wrote it had never
  worked. Both mapping boards now write a real `set_source_binding(…, origin='board')`, and the
  spreadsheet board draws itself with no file loaded — you can name a column by typing its heading.
- **The 26 components abm already had a source for now say so.** `declared` read the S3 binding and
  the component's nature and ignored the live wires drawn years earlier, so 8 rule-fed and 18
  feed-fed components rendered "No source chosen". A live mapping is now a declared source, which is
  also what put "Rule output" and a lineage button on a board that had shown neither (**S24**).

---

## Live vs latent — read this part

Several things are **built, tested and correct, but not yet doing anything on live data**, because
the data to exercise them does not exist yet. None of this is a defect; it is the honest state.

| Thing | Status | Why |
|---|---|---|
| Provenance blob | **LIVE but empty on history** | Written on every new run. payobook's 28,281 existing payslips predate it and carry NULL — the UI says *"This scheme has not been run yet"* rather than inventing an answer. |
| Repaired wires (23) | **LIVE but dormant** | The repair is real and `is_severed` is now 0 everywhere. The wires only *fire* on a `connector`/`api_data_store` batch, and **all 6 live batches are `excel`** — so they changed no payslip. Proven, not assumed. |
| Widened connector gate | **LIVE, unreachable by current data** | No `api_data_store` batch exists on any of the four databases. Proven on payobook_template with an integration test. |
| Bindings | **LIVE, none set** | `data_source_field` turned out to be empty on every rule on every database (**S12**), so the migration correctly bound nothing. S3's binding is the first explicit statement of source these databases have ever held — it is waiting for a person to make one. |
| Top-up (two sources) | **LIVE, unused** | No run has a second source yet. Exercised end-to-end on payobook_template. |
| Uncapped lineage extractor | **LIVE, latent** | Max consumed paths on live data is 3; the old cap was 4. Correct, and currently invisible (MF40's shape). |
| `declared` vs `actual` disagreement, `fell_back` | **Built, never yet displayed** | Both need a run with a provenance blob. They render the moment one exists. |

### What becomes visible on the first real feed-backed run

1. **Every chip gains an "actual"** — the rail, cards, Cell Editor and grid stop saying "not been run
   yet" and start naming the key that actually matched.
2. **The 709 renames become visible.** On payobook, *709 of 709* spreadsheet-sourced components match
   under a key **different** from their code (Vietnamese sheet-prefixed headers like
   `Bảng lương tạm ứng kỳ 1|Họ và tên` feeding `HVTN`). That correspondence was computed and discarded
   on every run; it now shows on the card.
3. **The repaired wires start carrying values**, and the mapping-beats-header precedence (**S9**)
   becomes observable — with the displaced value recorded as `ignored` rather than dropped.
4. **The "chosen source produced nothing" hint** can fire for the first time.

---

## Gotchas (S1–S27) — the ones worth carrying to the next programme

**Operational**
- **S17** — `odoo-bin -u` in a detached unit **does not reload the running service's Python**. It
  deploys, upgrades green, and still serves the old payload. **The signature is a shell and a browser
  disagreeing about the same method.** Always `service odoo-server restart` after a model change;
  purge `/web/assets/%` when assets look stale (MF12).
- **S1** — the four databases are remote; `sudo -u postgres psql` only works over `ssh Payobook19v2`.
- **S7** — the payroll data is on **payobook**, not abm (abm: 0 batches, 0 payslips). An earlier read
  had this backwards. Every recompute gate runs on payobook; UI validation runs on abm (CR13).
- **S20** — a board method that takes a connector will silently use the wrong one; no config on any
  database has `connector_id` set. Name the connector in the test.
- **S19** — `pb_integrations` does not import `_`; new translated strings raise at call time.

**Design / correctness**
- **S3** — you cannot recover an identity by re-applying the transform that destroyed it. Forward-
  mapping remembered codes through the new generator resolved 6/15 and **collided** include/exclude
  paid leave onto one code. Rejected; never propose it again.
- **S4/S5** — the rename ledger (`hr.formula.rule.version`, `reason='rename'`) is an exact old→new
  map. Tiers "exact" + "rename ledger" resolved **15/15** with no heuristic.
- **S5 (field)** — a stored related is not a memory; it is a cache that has not been invalidated yet.
  The 23 remembered codes survived by luck, and the repair itself would have spent it.
- **S6** — "severed" must mean NULL FK **plus** a remembered code, or a repairer walks 250 never-wired
  rows and reports 242 false verdicts.
- **S8** — adding a keyword to a model method is breaking when other modules override it. Two bridges
  did, on all four databases, and killed the payslip recompute path. **Grep for overrides first.**
- **S9** — an explicit mapping **beats** a name-matched header; the guard that looks like it says
  otherwise is in the wrong scope to. Unobservable until the gate opened.
- **S13** — when a binding falls back, search the other side by the **bound key** first. A fallback
  that cannot find the obvious reports "nothing arrived" with authority.
- **S14 / S16 / S18** — this codebase has duplicated UI blocks: two component editors, and two item
  templates on the mapping canvas. **A chip added once renders for nobody.** When an addition does not
  appear, check whether the surrounding *already-working* markup is there.
- **S15** — reserve space, never truncate a code (owner ruling). `max-width` resolves against the cell
  and does nothing at all on an inline element.
- **S21/S22 (S6)** — three chips answering three questions can still collide on one word, and the fix
  belongs in a **de-duplicating assembler**, not at each producer. And a branch covering two cases
  (`formula` + `constant`) must not hardcode one of them: the loud duplicate was standing in front of
  a wrong label on nine cards.
- **S23 (S6)** — `declared` ignored the most explicit statement of source these databases hold: a
  drawn mapping. **Audit what the database already asserts before adding a screen that says it
  asserts nothing.**
- **S24 (S6)** — S20 with a price tag. A user-visible fact must never depend on a default nobody
  chose: abm's board tie-broke onto the connector with no transformation rules and the product looked
  like it had none.
- **S25 (S6)** — **dead payload ships silently.** `meta.createRule` has been sent since S5 and is read
  by nothing; `onRightBlocked`/`onLineage` were never passed by either host, so the sealed refusal was
  server-only and "Open rule" had never rendered. **Grep the client for every new payload key before
  calling a phase done.**
- **S26 (S6)** — S17 has a one-command objective test: the running `odoo-bin` pid's start time must be
  **later** than the module row's `write_date`. Diagnose it that way instead of waiting for a shell and
  a browser to contradict each other. And when picking a phase up from an interrupted session, `md5sum`
  the deployed tree against the working tree — a correct version number only proves a `-u` ran.
- **S27 (S6)** — the owner's guide was written from the design table and inverted its own instruction:
  it said the last three chips "cannot be connected", but the last row is *no chip*, which is exactly
  the state of a component waiting to be mapped. **Walk a user-facing doc against the product.**

---

## What the owner still has to decide

1. **Push.** Six commits (`6724892c`, `d074ce9f`, `c960d022`, `59835a8f`, `3e273842`, S6) are on
   `19.1` and **not pushed**. Nothing leaves this machine until you say so.
2. **payobook's cross-company repair.** Its 8 mappings were repaired on exact-code matches into
   company 2 while the connector is company 1. Evidence was exact, not heuristic, and it cannot affect
   a payslip — but it is a judgement call you may want reversed. Pre-repair snapshots are at
   `/tmp/s2_pre_{abm,payobook}.txt` on the server.
3. **S11 — payobook's 14 orphan transformation rules**, 4 with underscored keys
   (`NUM_TAX_DEPENDENTS`, `TOTAL_LEAVE_DAYS`, `TENURE_YEARS`, `NET_SALARY`) that silently compute 0.
   Left untouched per ruling O-5. The health hint now surfaces all 14. They are either wanted (and
   need renaming + wiring) or they are dead (and should be archived).
4. **The 268 unsourced inputs on payobook / 34 on abm.** They resolve by name-matching today, which
   works until a column is renamed. Binding them is now possible; nobody has.
5. ~~**A shared label sub-template for the mapping canvas** (S18).~~ **Done in S6** — it was indeed
   the third time, and it was the reported defect.
6. **S25 — the right column has no action menu**, so `meta.createRule` ("Create a rule for this",
   reported as shipped in S5) is payload nothing renders. Giving that column a menu would also give it
   "Clear the source". Small, deliberate, and out of S6's scope; say whether you want it.
7. **abm's two connectors.** *Zoho People* holds 18 wires and no rules; *Zoho People (ABM)* holds the
   8 transformation rules and 15 wires — and seven components are wired on **both**. The board picks
   the first by mapping count. Nothing is broken, and it is probably not what you meant: either
   consolidate onto one connector, or set the scheme's connector explicitly so nothing has to guess.
8. **Nothing to decide — recorded so you know it changed.** The re-verification pass corrected one
   sentence in `SOURCING_WALKTHROUGH.md`. It had told you that components with **no chip** cannot be
   connected; they are the only ones that are *waiting* to be, and section 4 of the same guide walks
   you through connecting one. Corrected in place (**S27**); no code change.

---

## How to verify any of this yourself

```
ssh Payobook19v2
sudo -u postgres psql -d payobook -tAc "select count(*) from hr_integration_field_mapping where is_severed"   -- 0
sudo -u postgres psql -d abm      -tAc "select count(*) from hr_integration_field_mapping where target_rule_id is not null"  -- 33
```
Both numbers above were re-checked on 2026-08-25 and are current.

Recompute neutrality — this is the exact invocation, and it rolls back at the end:

```
ssh Payobook19v2
sudo -u odoo bash -c 'CAPTURE_OUT=/tmp/check.json \
  /odoo/odoo-server/odoo-bin shell -c /etc/odoo-server.conf -d payobook --no-http < /tmp/s3_neutral.py'
md5sum /tmp/check.json      # must be b1dcd785739e1c0f49d304ee5428229a
```

It also prints `BOUND_BRANCH_ENTERED` (must be `0` while no binding is set) and `TOPUP_LINES`.

Confirm the running service actually holds the deployed Python (**S17**, **S26**) — the module row must
be written *before* the live process started:

```
sudo -u postgres psql -d abm -tAc "select latest_version, write_date from ir_module_module where name='pb_formula_studio'"
ps -eo pid,lstart,cmd | grep -a '[o]doo-bin'      # server clock is UTC
```

Batteries: `python3 pb_hr_payroll_formula/tools/{provenance,excel_semantics,import_resolution}_battery.py`.
