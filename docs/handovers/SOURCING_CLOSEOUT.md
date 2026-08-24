# SOURCING — closeout

**Programme complete. Five phases, live on abm · acme · payobook · payobook_template (2026-08-25).**
Read this instead of the five phase reports. Detail: `SOURCING_DESIGN.md` (design + phase split),
`SOURCING_LEDGER.md` (conventions + gotchas S1–S20), `SOURCING_PHASE_S{1..5}_HANDOVER.md`.

Final module versions: **pb_hr_payroll_formula 19.0.1.78.0 · pb_formula_studio 19.0.1.128.0 ·
pb_integrations 19.0.1.12.0 · pb_workforce_payroll_bridge 19.0.1.2.0 · pb_trip_payroll_bridge
19.0.1.1.0** · om_hr_payroll 19.0.1.0.2 (never touched — CR1).
Commits: S1 `6724892c` · S2 `d074ce9f` · S3 `c960d022` · S4 `59835a8f` · S5 = the commit carrying
this file. **Nothing is pushed.**

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

**The neutrality gate held across all five phases**: the same md5 (`b1dcd785739e1c0f49d304ee5428229a`)
before S1 and after S5, over every payobook import line.

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

## Gotchas (S1–S20) — the ones worth carrying to the next programme

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

---

## What the owner still has to decide

1. **Push.** Five commits (`6724892c`, `d074ce9f`, `c960d022`, `59835a8f`, S5) are on `19.1` and
   **not pushed**. Nothing leaves this machine until you say so.
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
5. **A shared label sub-template for the mapping canvas** (S18) — the third time a chip has had to be
   added twice. Small, and it stops the next one being a bug.

---

## How to verify any of this yourself

```
ssh Payobook19v2
sudo -u postgres psql -d payobook -tAc "select count(*) from hr_integration_field_mapping where is_severed"   -- 0
sudo -u postgres psql -d abm      -tAc "select count(*) from hr_integration_field_mapping where target_rule_id is not null"  -- 33
```
Recompute neutrality: `/tmp/capture.py` on the server, compared against `/tmp/before.json`
(md5 `b1dcd785739e1c0f49d304ee5428229a`). Batteries:
`python3 pb_hr_payroll_formula/tools/{provenance,excel_semantics,import_resolution}_battery.py`.
