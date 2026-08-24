# SOURCING — conventions + gotcha ledger

**STATUS: DESIGN COMPLETE, IMPLEMENTATION NOT STARTED (2026-08-24).** Design:
`docs/handovers/SOURCING_DESIGN.md`. Owner-approved brief:
`~/.claude/plans/i-want-you-to-giggly-hummingbird.md`. Five phases: **S1** provenance persisted ·
**S2** severed mappings + lineage data + widened connector gate · **S3** bindings and one run from two
sources · **S4** source on every screen · **S5** lineage in place, sealed components, cockpit.

Module versions at programme start: **pb_hr_payroll_formula 19.0.1.72.0 · pb_formula_studio
19.0.1.126.0 · pb_integrations 19.0.1.10.0 · biz_theme 19.0.1.4.0 · om_hr_payroll 19.0.1.0.2**
(om stays untouched — CR1).

**COLROLES `CR1–CR33` and MAPFIX `MF1–MF41` STILL BIND.** Read
`docs/handovers/COLROLES_LEDGER.md` and `docs/handovers/MAPFIX_LEDGER.md` before any phase. This file
adds `S`-numbered entries and restates only the operational rules that are load-bearing every single
time.

---

## Standing rules (bind every phase)

- **White-label absolute.** No user-visible string may contain "Odoo" — labels, chips, tooltips, help
  text, placeholders, empty states, error and toast messages, menu and action names, field
  `string=`/`help=`, selection labels, reports, exported files, `.po` msgstr. Use **Payobook** or a
  neutral term. **Never rewrite technical identifiers** — `from odoo import`, module/model/XML ids,
  `odoo-bin`, config paths, addon names, log messages, code comments, and engineering docs (including
  this one) keep the real name.
- **Terse output.** One-line bash where possible; never dump file contents into the chat.
- **Commit per phase**, explicit file staging, reviewer-focused message, **do not push** until asked.
- **Asset cache.** Any JS / SCSS / OWL-XML change ⇒ bump that module's manifest version and `-u` it.
  SCSS errors surface only at page load in the browser, never in `-u` output. (**MF12**)
- **Migrations.** `migrations/<full-module-version>/post-<sentence_slug>.py`, docstring stating WHY
  and WHAT IS NOT TOUCHED, `table_exists` guard (shared addons tree, per-DB schemas), idempotent, only
  rewrite rows still carrying shipped values, log per-DB counts.
- **Live validation uses abm.** payobook's role-bearing configs are company 2 and invisible to the
  apex admin session (**CR13**). Formula Studio action id: 742 on abm, 1160 on payobook.
- **The documented apex password no longer authenticates over RPC** (**CR33**) — drive live checks
  through the authenticated Chrome-MCP browser session (`fetch('/web/dataset/call_kw', …)` from inside
  the page), which also carries the right `allowed_company_ids`.
- **Mandatory regression gates, every phase:**
  `python3 pb_hr_payroll_formula/tools/excel_semantics_battery.py` and
  `python3 pb_hr_payroll_formula/tools/import_resolution_battery.py`, both exit 0.
  Check they actually RUN before trusting a green (**MF7**).
- **The neutrality gate is pass/fail, not advisory.** A single-source run must produce byte-identical
  `input_values` and payslip lines before and after every phase, proven by recomputing real payslips
  and diffing. A config with no active mappings must be completely unaffected by the widened connector
  gate.

## The deploy ritual (corrected form — this is the one that works)

1. rsync modules from the Mac → `/tmp/stage/` on the server, then `sudo rsync` into
   `/odoo/odoo-server/addons/`.
2. **`sudo chmod -R a+rX` the synced module dirs. Non-optional (CR6).** `rsync -a` preserves Mac 0600
   modes; the odoo user then cannot read `__manifest__.py`, the upgrade logs *"not installable,
   skipped"* — **and `odoo-bin` still exits 0**. A green EXIT sentinel is not proof of an upgrade.
3. Park every Chrome-MCP validation tab on `about:blank` (**CR20**), then
   `sudo service odoo-server stop`, then confirm **zero `odoo-bin` pids BY PID**. Never `pkill -f`
   (**MF9** — two concurrent upgrades of one database is far worse than a slow shutdown).
4. Write `/tmp/<unit>_run.sh` looping over **abm acme payobook payobook_template**:
   `sudo -u odoo /odoo/odoo-server/odoo-bin -c /etc/odoo-server.conf -d <db> -u <mods> --stop-after-init`
   capturing `EXIT[$db]=$?`, ending `touch /tmp/<unit>.done`.
   **The `sudo -u odoo` is not optional (MF35):** `systemd-run` runs the unit as ROOT and odoo-bin
   then fails peer auth with `FATAL: role "root" does not exist` on every DB in about ninety seconds,
   while still writing `EXIT[db]=1`. The service itself runs as `odoo`
   (`/etc/init.d/odoo-server`, `USER=odoo`).
5. Launch detached: `systemd-run --collect --unit=<unit> /bin/bash /tmp/<unit>_run.sh`.
6. Read the RESULT from `/var/log/odoo/odoo-server.log` (`grep -a`, `grep odoo.tests.result`), **not**
   the `/tmp` sentinel, then `systemctl stop <unit>` rather than waiting on a hung shutdown (**MF9**).
7. `service odoo-server start`; check `systemctl is-active` and port 8069 bound.
8. **Verify `ir_module_module.latest_version` in psql on all four databases**, as
   `sudo -u postgres psql -d <db> -tAc "…"` (**MF17** — `psql -U odoo` fails peer auth as `ubuntu`,
   bare `psql` fails with `role "ubuntu" does not exist`; a verification that silently errors is a
   verification that did not happen).

A RED sentinel is not proof of a broken build either (**MF35**). Read the log before believing either
colour.

## The write-oracle rule (MF37) — restated because this programme will tempt it

**You cannot observe Odoo's RPCs by patching `window.fetch` from a Chrome-MCP probe.** The web client
captures `browser.fetch` at module load, so a hook installed afterwards sees nothing — and "zero RPCs"
then reads as proof when it is only proof that the hook is blind. It has already cost a real write on
abm. **The oracle for "did the UI write anything" is the DATABASE**, counted before and after. For
this programme the before/after query set is:

```sql
select count(*), count(*) filter (where target_rule_id is null), md5(string_agg(id::text,',' order by id))
  from hr_integration_field_mapping;
select count(*), md5(string_agg(id::text||':'||coalesce(source_binding,'')||':'||coalesce(source_binding_key,''), ',' order by id))
  from hr_formula_rule;                      -- from S3 onward
select count(*), string_agg(id::text, ',' order by id) from hr_payslip_import_mapping;
```

The safe way to probe a write-capable gesture is to leave nothing armed — a failed guard then moves a
focus ring instead of writing a row.

---

## Verified facts (do not re-derive)

Established 2026-08-24 against the code and the live databases. Full detail in
`SOURCING_DESIGN.md` §0.

- All nine facts handed down in the brief **hold**. Six gained a refinement; two of those changed the
  design (S3, S4 below).
- **`hr.integration.field.mapping.target_rule_id` is read in exactly ONE place in the payroll
  pipeline** — `payroll_import_batch.py:2696`, behind `source_type == 'connector'`. The resolver's
  other mapping lookup (`mapping_by_rule`, `:2648-2661`) reads a **different model**,
  `hr.payslip.import.mapping`. That one line is the entire blast radius of the gate and of the repair.
- **Severed audit (read-only, 2026-08-24).** Severed := `target_rule_id IS NULL` **AND**
  `target_rule_code` non-empty.

  | DB | total | NULL FK | **severed** | active |
  |---|---|---|---|---|
  | abm | 59 | 41 | **15** | 33 |
  | payobook | 252 | 250 | **8** | 194 |
  | acme | 0 | 0 | 0 | 0 |
  | payobook_template | 0 | 0 | 0 | 0 |

  abm's 15 = the **8** transformation-rule `output_key`s (`OTHRS150/200/210/270/300/390`, `DEPCOUNT`,
  `WORKEDHRS`) + **7** vendor fields. payobook's other 242 NULL-FK rows were **never wired** (185
  active with no remembered code, 57 unaccepted `suggested`); only **2** mappings in the whole payobook
  database have a live `target_rule_id`.
- **Where the payroll data actually is** (corrected in S1, see **S7**): `batches / import lines /
  payslips / payslip lines / formula configs` —
  **abm 0 / 0 / 0 / 0 / 1** · **acme 0 / 0 / 0 / 0 / 0** ·
  **payobook 6 / 35 / 28281 / 719352 / 18** · **payobook_template 0 / 0 / 0 / 0 / 0**.
  All 6 payobook batches are `source_type='excel'`; **there is no `api_data_store` batch on any
  database**, so widening the connector gate is a no-op against every row of live data.
  **Consequence: any gate that recomputes real payslips must run on `payobook`.** abm remains the
  place for live *UI* validation (CR13), but it has no payroll to recompute.
- There are **three** writers of `formula_input_values`, not one: `payroll_import_batch.py:2157`,
  `hr_payslip_formula.py:474` (recompute via the import line) and `hr_payslip_formula.py:108`
  (recompute with no import line, `_get_formula_input_values` at `:318`). All three must write
  `formula_input_sources`.
- `hr.formula.rule.version` with `reason='rename'` is an **exact rename ledger** — `snapshot_json`
  carries the pre-rename `code` plus `rule_id` (64 rows on abm). See S4.

---

## Gotchas discovered (append per phase, S-numbered)

- **S1 (design, environment): the four "live" databases are not on this machine.** `sudo -u postgres
  psql` from the repo answers `sudo: unknown user postgres`; abm / acme / payobook /
  payobook_template live on the **Payobook19v2** host (`3.25.57.42`, `~/.ssh/config`). Every psql fact
  in this programme is taken as `ssh Payobook19v2 "sudo -u postgres psql -d <db> -tAc '…'"`. A local
  psql that errors is not evidence of anything.

- **S2 (design): `hr_formula_rule.name` is a plain `varchar`, not a jsonb translation column.**
  `name->>'en_US'` raises `operator does not exist: character varying ->> unknown`. Select it directly.
  Do not assume a field is translatable because its sibling models' are; `hr_api_transformation_rule`
  likewise has `active`, not `is_active`. Check `information_schema.columns` before writing the query,
  not after it fails.

- **S3 (design, ruling): forward-mapping a remembered code through `component_code.build_component_code`
  is WRONG and DANGEROUS, and must not be proposed again.** Run against all 15 real severed codes on
  abm it resolves **6/15** — only the ones an exact match already gets — **misses both examples the
  brief names** (`NUMBEROFDEPENDENTS` → `NUMBEROFDEPE` vs live `NOOFDEPENDEN`;
  `ACTUALWORKINGHOURSINCLUDINGPAIDLEAVE` → `ACTUALWORKIN` vs live `ACTUWORKHOUR`) — and it
  **collides**: `…INCLUDINGPAIDLEAVE` and `…EXCLUDINGPAIDLEAVE` both produce `ACTUALWORKIN`, and
  `OTNIGHTSHIFTWEEKDAY` and `OTNIGHTSHIFTWEEKENDDAY` both produce `OTNIGHTSHIFT`. Silently wiring
  weekday overtime into the weekend-night component is a wrong payslip. **The generator is lossy;
  you cannot recover an identity by re-applying the transform that destroyed it.** The two collision
  pairs are permanent test cases: they must return `ambiguous`, never a pick.

- **S4 (design): the rename ledger nobody knew existed makes the repair exact.**
  `hr_formula_rule_version` rows with `reason='rename'` carry the **pre-rename `code`** inside
  `snapshot_json` alongside `rule_id` (64 rows on abm, written by
  `rename_component` via `with_context(formula_version_reason='rename')`,
  `formula_rule.py:1750-1758`). Matching remembered codes against it resolves 9 of abm's 15 exactly;
  the other 6 were never renamed and an exact code match gets them. **Tiers 0+1 = 15/15, zero
  heuristics, zero ambiguity.** The third tier (invert the *legacy* generator —
  `re.sub(r'[^A-Za-z0-9]','',rule.name).upper()[:40]` — and compare) also scores 15/15 standalone,
  including the misspelled `OT Ngiht shift Holiday`, because it inverts the lossy transform instead of
  re-applying it. It is kept as a safety net for databases whose version history has been pruned.

- **S5 (design): `target_rule_code` survived 15 severings by ACCIDENT, and the luck is nearly spent.**
  It is a **stored related** (`integration_field_mapping.py:94-98`), which normally blanks when its FK
  blanks. It kept its value only because `ON DELETE SET NULL` fires in **SQL** and never triggers an
  ORM recompute. The next ORM write that touches `target_rule_id` would recompute the related and
  **erase every remembered code**, destroying repairability for good. It must become a *remembering*
  stored compute — copy the code when there is one, keep the previous value when there is not — which
  also makes a full upgrade-time recompute a no-op. Same treatment for `target_column_letter`
  (`:88-92`). **A stored related is not a memory; it is a cache that happens not to have been
  invalidated yet.**

- **S6 (design): "severed" must mean NULL FK *plus* a remembered code.** On payobook, `target_rule_id
  IS NULL` alone selects **250** rows, of which **242 were never wired to anything** (185 active with
  no remembered code, 57 unaccepted `suggested` template guesses). A repairer built on the looser
  predicate would walk 250 rows, find nothing to remember, and report 242 false `no_match` verdicts —
  burying the 8 that matter. The same trap on abm: 41 NULL, 15 severed, 26 never wired.

---

- **S7 (S1, environment): the payroll data is on `payobook`, not `abm` — and an earlier reading of
  this ledger had it backwards.** The design's first draft said "abm has 6 batches and every one is
  excel; payobook has none". It is the exact reverse: `batches / import lines / payslips / payslip
  lines / configs` = **abm 0/0/0/0/1 · acme 0/0/0/0/0 · payobook 6/35/28281/719352/18 ·
  payobook_template 0/0/0/0/0**. The cause was reading a two-query psql result where the FIRST query
  returned nothing: the single line of output belonged to the second database, and was attributed to
  the first. **A psql result with fewer blocks than queries has silently dropped one — label every
  database in the query itself (`select 'abm', …`) rather than relying on statement order.** The
  substantive conclusion survived and got stronger (no `api_data_store` batch exists on ANY of the
  four, so widening the gate is a no-op everywhere), but the consequence matters:
  **any gate that recomputes real payslips must run on `payobook`.** abm stays the place for live UI
  validation (CR13) and has no payroll to recompute.

- **S8 (S1, design): adding a keyword argument to a model method is a BREAKING change when other
  modules override it — and two of them did, on all four databases.**
  `hr.payslip._get_formula_input_values` is overridden by `pb_workforce_payroll_bridge` (OT hours) and
  `pb_trip_payroll_bridge` (trip days / per-diem), both `installed` on abm, acme, payobook and
  payobook_template. They sit ABOVE the base producer in the MRO, so the moment the base caller passed
  `provenance=…` the outermost override raised
  `TypeError: _get_formula_input_values() got an unexpected keyword argument 'provenance'` and **the
  entire payslip recompute path was dead** — caught only because the S1 verification actually invoked
  a recompute rather than trusting that the resolver test covered it. Both bridges now accept and
  FORWARD the keyword, and record their own entries (`src='employee_field'` with
  `via='overtime_request'` / `'business_trip'` — the value is the employee's own approved records, and
  `via` is what stops a chip sending the reader to the employee form for an overtime total).
  **Before extending any model method's signature, `grep -rn "def <name>"` across every module in the
  tree, not just the one you are editing — and make the test exercise the real entry point, because a
  unit test of the inner function passes happily while the outer one is broken.**

## Owner decisions (locked)

*(none yet beyond the seven in the brief — recorded here as they are made)*

- **S-D1** Per-component binding decides which source wins; the unused side is reported, never
  silently dropped.
- **S-D2** One run = primary + explicit top-up. `source_type` stays the base source; an explicit
  "also pull from…" step adds the second.
- **S-D3** Fall back, but say so — if the bound source is empty for an employee, use the other and
  mark it (`fell_back`).
- **S-D4** Source must be visible in the components rail, cards + Cell Editor, grid column headers,
  and both mapping boards.
- **S-D5** Calculated components are shown but sealed — visible, non-wirable, badged; never hidden.
- **S-D6** Full lineage in place (popover/card), not on a separate screen.
- **S-D7** Both surfaces get it: Formula Studio **and** the Integrations cockpit.
- **S-D8** An unbound input may offer inline rule creation, launching the rule composer with its code
  pre-filled as the output key.

## Open — awaiting the owner

- **O-1** Authorise repairing payobook's 8 severed mappings (S2 audits and reports; it will not write).
- **O-2** How to prove the widened gate actually fires without disturbing abm. Proposal:
  payobook_template + an integration test; abm untouched.
- **O-3** Confirm `data_source` is demoted-and-kept, not removed (it is written by both import wizards
  and read for a wizard preview at `multisheet_import_wizard.py:3037,3057`).
- **O-4** Repair all 15 abm severed mappings, or only the 8 rule outputs? Recommend all 15.
- **O-5** `output_key` constraint scope if any of the four DBs holds a violating key.

## Phase status

- **S1 — Provenance becomes real. DONE + live on abm · acme · payobook · payobook_template
  (2026-08-24).** pb_hr_payroll_formula **19.0.1.73.0** · pb_workforce_payroll_bridge **19.0.1.2.0** ·
  pb_trip_payroll_bridge **19.0.1.1.0**. Shipped: `hr.payslip.formula_input_sources`; the plain-python
  `input_provenance` vocabulary (8 `src` × 18 `via`) and the single translation point; provenance
  filled by all three writers of `formula_input_values`; the matched header key captured on every path
  instead of only for `collaborate`; adjustments (proration/retro/carryover) recorded via `adj`.
  **Neutrality gate PASSED — byte-identical**: old vs new resolver over all 35 payobook import lines,
  1,883 input codes + 2,394 computed codes, `cmp` clean and md5 equal
  (`b1dcd785739e1c0f49d304ee5428229a`). 0 invariant failures. Live distribution on payobook:
  `src` excel 709 · contract_component 631 · none 298 · constant 140 · employee_field 105.
  **709 of 709 spreadsheet-sourced components matched under a key DIFFERENT from their code** (Vietnamese
  sheet-prefixed headers such as `Bảng lương tạm ứng kỳ 1|Họ và tên` → `HVTN`) — the fact the product
  could not previously state, discarded 709 times per run. Gotchas: **S7**, **S8**. Databases left as
  found (`with_sources=0` after rollback; severed still 15 on abm / 8 on payobook).
- **S2 — Severed mappings, lineage data, widened gate.** NOT STARTED.
- **S3 — One run, two sources.** NOT STARTED.
- **S4 — Every screen says where a value comes from.** NOT STARTED.
- **S5 — Lineage in place, sealed components, cockpit.** NOT STARTED.
