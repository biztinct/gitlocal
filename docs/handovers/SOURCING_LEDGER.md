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

- **S9 (S2, design): an explicit connector mapping BEATS a name-matched header — the guard that looks
  like it says otherwise is in the wrong scope to.** The S2 spec claimed the
  `if rule.code not in input_values` guard (`payroll_import_batch.py:2801`) means "a mapping can only
  fill a gap, never overwrite a header". Backwards: the mapping block (`:2737`) runs BEFORE the input
  loop and assigns unconditionally, so the loop's guard SKIPS a code the mapping already filled. The
  precedence is mapping > header, which is the correct way round (it is the owner's "per-component
  binding decides") but was **unobservable for as long as the gate was shut**, so nobody had ever seen
  it. Caught by a live gate test asserting the opposite and failing. Two consequences: the precedence
  is now stated in the code, and because a mapping can DISPLACE a value that genuinely arrived, the
  displaced value is recorded as `ignored` in provenance rather than dropped — the owner's rule is
  that the unused side is reported. **When a gate has never opened, the behaviour behind it is a
  guess until you run it; assert the precedence you believe in and let the test disagree.**

- **S10 (S2, environment): reconnecting a `renamed` mapping legitimately CHANGES `target_rule_code`,
  and that is the remembering compute working, not failing.** After the repair, 9 of abm's 15 rows
  show a changed code (`DATEOFJOINING` → `DATEOFJOININ`, `NUMBEROFDEPENDENTS` → `NOOFDEPENDEN`, …) —
  exactly the 9 whose verdict was `renamed`. The memory is only authoritative while there is no FK;
  the moment one exists the field tracks the live code again, which is the whole point. The 6 `exact`
  rows are unchanged because their remembered code already equalled the live one. **A before/after
  diff of this column is expected to be non-empty after a repair, and empty after a mere recompute.**

- **S11 (S2, finding): payobook's 14 transformation rules feed NOTHING, and 4 of them cannot work at
  all.** After repairing all 8 severed mappings there, every one of its rule `output_key`s still has
  zero consumers — its severed mappings were vendor identity fields (`employee_id`, `full_name`,
  `email`, …), not rule outputs. Separately, four keys violate the converter contract with
  underscores: `NUM_TAX_DEPENDENTS`, `TOTAL_LEAVE_DAYS`, `TENURE_YEARS`, `NET_SALARY` — an underscored
  key survives raw into the eval, raises `NameError` and silently reads 0. Left exactly as they are
  per owner ruling O-5 (the constraint governs create/write, never load), and reported here so the
  S5 health hint "rule output consumed by nobody" has a known first customer. abm is the opposite:
  all 8 of its rule outputs now have exactly one live consumer.

- **S12 (S3, finding): `data_source_field` is EMPTY on every rule on every live database.** The Char
  that the studio's Import-columns tab writes (`import_mapping_create` →
  `rule.write({'data_source_field': col})`) has never been used on abm or payobook: 0 of 54 abm input
  rules and 0 of 315 payobook input rules carry a value. Every component on both databases resolves
  purely by header/column-letter matching — which is exactly what S1 measured from the other side
  (376 `header` + 333 `column_letter` = the 709 spreadsheet-sourced components). Consequences: the S3
  migration correctly bound NOTHING (it logged `no candidate rules` on all four); the "legacy
  highest-priority candidate" is theoretical rather than load-bearing on live data; and **the binding
  introduced by S3 is the first explicit statement of source that these databases have ever held.**
  It also means the neutrality gate is doubly satisfied — with nothing bound, the bound branch is
  unreachable, which is what the counter measured.

- **S13 (S3, design): when a binding falls back, search the other side by the BOUND KEY first, not
  only by the component's own name.** The first cut searched the other blob with the component's
  natural candidates (name, code, column letter) and missed a feed carrying the value under the bound
  key itself — `BONUSPAY` bound to the spreadsheet column `Bonus Col`, empty in the file, present in
  the feed as `Bonus Col`, was reported as `binding_empty` while 750 sat one key away. The same column
  is very often called the same thing in both sources, so the bound key is the single most likely name
  on EITHER side. Now `[bound_key] + candidates + column_candidates`. **A fallback that cannot find
  the obvious is worse than no fallback: it reports "nothing arrived" with authority.**

- **S14 (S4, design): there are TWO component editors in `studio.xml`, and the one with the Advanced
  accordion is not the one the Edit button opens.** The Cell Editor block was added beside the
  `Advanced` accordion (`studio.xml:~1411`) exactly as the design said — and rendered for nobody. The
  panel the Edit button actually opens is the inline editor at `:1221` (`.ce-body`, type-switched
  bodies for formula/input/constant), which has no `.ce-sec` at all. Diagnosed by querying the live
  DOM for `.ce-sec-h` and getting an EMPTY list — i.e. the *pre-existing* Advanced heading was missing
  too, which is what proved the whole block was in the wrong editor rather than the new markup being
  broken. **When a UI addition does not appear, first check that the surrounding, already-working
  markup is there; if it is not, you are editing the wrong template.**

- **S15 (S4, found not fixed): the grid header has a PRE-EXISTING overlap — `.g2-code` runs ~5px under
  `.g2-addsc`.** Surfaced by S4's bounding-box measurement, not introduced by it (the source glyph
  contributes ZERO overlaps at 1440 and 1024 once pinned to the free bottom-right corner). It cannot be
  fixed with a `max-width` on the code: `max-width` resolves against the CELL while the code starts
  after the column letter, so the code still reaches the button — and on a non-replaced INLINE element
  it does nothing at all until `display:inline-block` is added, which is a second trap in the same
  fix. The honest repair is to reserve right padding on the header, which changes every column's
  layout and risks truncating exactly the ≤12-char codes MAPFIX Phase A created. **Reported for an
  owner decision rather than force-fixed inside a phase about chips.**

- **S16 (S4, design): the mapping canvas has two item templates, and the right column has its own.**
  `mapping_canvas.xml:92` (left) renders `<span t-esc="it.label"/>` plus chips; `:193` (right)
  rendered `<div class="mc-item-label" t-esc="it.label"/>` — a bare text node with no chip slot at
  all. A chip added only next to the left column's `provChip` therefore rendered nothing on the right,
  while every server payload and every client helper checked out. **Also: `prov` was the wrong field
  to reuse.** It means "where did this CARD come from" (vendor catalogue / live sync / Payobook's own
  field) and `provChip` only understands `catalog`/`odoo`/`mapping`, so arbitrary source kinds
  silently returned null. Source is a SECOND axis and now has its own `srcKind` + `srcChip` +
  `.mc-src`. **Two questions about one card need two chips; overloading the first one answers
  neither.**

- **S17 (S4, environment): `odoo-bin -u` in a detached unit does NOT reload the running service's
  Python.** The upgrade process is a separate process: it updates the database and rebuilds the asset
  bundles, and the already-running `odoo-server` keeps its previously imported modules in memory. A
  model change therefore deploys, upgrades green, and still serves the OLD payload — observed as a
  board returning `prov`/`provKind` (a superseded key set) while a shell on the same server returned
  the new `srcKind`. **A shell and a browser disagreeing about the same method is the signature.**
  Add `sudo service odoo-server restart` after any Python change, and remember MF12's companion
  remedy for assets: `delete from ir_attachment where url like '/web/assets/%'` then restart.

- **S18 (S5, design): the mapping canvas's RIGHT column needs every chip added twice — this is S16
  again, and it will happen a third time.** The sealed-card badge was added beside the left column's
  `badge(it)` call and rendered on nothing, exactly as the source chip did in S4. `mapping_canvas.xml`
  has two item blocks (`:92` left, `:193` right) and they do not share a label sub-template. **Any
  future chip must be added to BOTH, or the right column silently omits it** — and the omission looks
  like a data problem, not a template one, because every server payload and client helper checks out.
  The durable fix is a shared label sub-template; not done here because S5 is the last phase and the
  change would touch every card on both boards.

- **S19 (S5, environment): `pb_integrations` does not import `_`.** `from odoo import api, fields,
  models` — no translation function, because nothing in the module had ever translated a string. New
  user-facing text there raises `NameError: name '_' is not defined` at CALL time, not import time, so
  it deploys clean, upgrades green, and only fails when somebody opens the board. Import `_`
  explicitly when adding the first translated string to a module.

- **S20 (S5, testing): a board method that takes a connector will silently use the WRONG one.**
  `api_mapping_data(config_id)` falls back to a default connector when the config has none — and per
  S3 **no config on any live database has `connector_id` set**, so every test and every board that
  omits it lands on connector 1. On abm the transformation rules live on connector **3**; the first
  lineage test therefore reported "0 computed fields, 0 lineage cards" against fully working code.
  **When a fact is per-connector, name the connector in the test; a plausible empty result is the
  most expensive kind.**

- **S21 (S6, design): three chips answering three questions can still collide on one word — and the
  fix belongs in the assembler, not at each producer.** `provChip` ("where did this CARD come from"),
  `srcChip` ("what feeds this COMPONENT") and `badge` ("what the card IS") are correctly three
  separate questions, and S4/S5 added the second and third without anybody checking what happens when
  two of them answer *the same word*. On a calculated component both said **Calculated**, so all 45
  sealed cards on abm rendered `CALCULATED CALCULATED`. Patching `_mc_right_item` alone would have
  fixed today's collision and left the next one to be discovered by the owner. `itemChips(it)` now
  assembles the three and **drops any chip whose label duplicates an earlier one**, so the invariant
  "a card never renders two pills with the same text" holds for boards not yet written. **An
  N-producer slot needs a de-duplicating assembler, not N careful producers.**

- **S22 (S6, finding): a branch that covers two cases must not hardcode one of them.** The same
  `if not wirable:` block badged `formula` AND `constant` cards with the literal `"Calculated"`, so
  abm's nine fixed-value columns carried `Fixed value` (chip) beside `Calculated` (badge) — not a
  duplicate but a **contradiction**, and nobody reported it because the duplicate next to it was
  louder. The badge label now comes from the card's own kind. **When you fix a reported defect, check
  the other rows the same code path produces: the loud bug is often standing in front of a wrong one.**

- **S23 (S6, design): `declared` ignored the most explicit statement of source these databases
  actually hold.** `_declared_source` read the S3 binding and the component's own nature and stopped.
  A **live `hr.integration.field.mapping`** — a wire somebody drew on a board, years before bindings
  existed — said nothing on any screen. On abm that silenced 8 components fed by transformation-rule
  outputs and 18 fed by vendor fields: every one of them rendered "No source chosen" while a wire was
  attached. It is now a tier between the binding and the nature, computed once per config in one
  search, with `rule` beating `feed` when a component is wired on two connectors (seven of abm's are)
  so the answer cannot depend on row order. **"Explicit" is not a synonym for "the newest mechanism";
  audit what the database already asserts before adding a screen that claims it asserts nothing.**

- **S24 (S6, environment): S20's cost, measured.** abm has two connectors — 1 *Zoho People* (18
  mappings, all wired, **0 transformation rules**) and 3 *Zoho People (ABM)* (41 mappings, 15 wired,
  **all 8 rules**) — and config 14 has no `connector_id`, so `_api_active_connector` tie-breaks on
  mapping count and lands on **connector 1**. The owner's board therefore had no "Derived here" lane
  and no lineage anywhere, correctly, and the product looked like it had none at all. The lane was
  never conditional on synced data (`_catalog_source_fields` has contributed rule outputs pre-sync
  since Integrations Cycle 4). The fix is not to change the tie-break — connector 1's 18 wires are
  real — it is that **a component's lineage must not be scoped to whichever connector a board
  guessed**: `_lineage_for_config` unions every connector that can reach the scheme. **S20 said "name
  the connector in the test"; S24 adds "and never let a user-visible fact depend on a default nobody
  chose".**

- **S25 (S6, finding): dead payload ships silently.** `_mc_right_item` has written
  `meta.createRule` since S5 — the "Create a rule for this" affordance the closeout reports as
  shipped — and **no template or component reads the key**. The right column has no action menu at
  all. Likewise neither host passed `onRightBlocked` or `onLineage`, so S5's sealed-card refusal was
  server-only and the lineage popover's **"Open rule"** button had never once rendered. All three are
  invisible in every test that checks a payload rather than a pixel. **A server key nothing renders is
  indistinguishable from a feature; grep the client for every new payload key before calling a phase
  done.** (`onRightBlocked` and `onLineage` are wired in S6; `createRule` is left dead and reported.)

- **S26 (S6 re-verification, environment): S17 has a cheap objective test — stop diagnosing it from
  symptoms.** The documented signature of "the running service never reloaded the Python" is *a shell
  and a browser disagreeing about the same method*, which you only notice after writing a test that
  contradicts itself. There is a direct check, and it costs one command:
  compare `ir_module_module.write_date` for the upgraded module against the **start time of the running
  `odoo-bin` pid** (`ps -o lstart= -p <pid>`; the server clock is UTC). Restart-after-upgrade ⇒ the
  process start is LATER than the module write. Here `21:57:56Z` vs `22:07:40Z` — satisfied, proven in
  seconds, with no browser involved. **When a phase is picked up from an interrupted session, verify
  the deploy the same way: per-file `md5sum` of the deployed tree against the working tree** (all nine
  files matched), because "the version number is right" only proves a `-u` ran, not that the files
  under it are the ones you are reading. Note `/odoo` is `0750 odoo:odoo`, so every such check needs
  `sudo` — an `ls` that says *Permission denied* is the ledger's CR6 trap wearing a different hat, and
  is **not** evidence the deploy is broken.

- **S27 (S6 re-verification, finding): the owner-facing doc was written from the design table, not from
  the running product — and inverted the one instruction it exists to give.** `SOURCING_WALKTHROUGH.md`
  listed the eight chips and then said *"the last three cannot be connected to anything"*. Two of them
  (`Calculated`, `Fixed value`) genuinely cannot. The third is **no chip at all** — which is precisely
  the state of a component that is *waiting to be connected*, and the only kind the guide's own
  spreadsheet walkthrough actually wires (`NIGHSHIFHOUR` has no chip until you feed it). A reader
  following the guide would have skipped every component the guide was written to teach him to map.
  The sentence is true of the *sealed* set and was copied onto a table whose last row means the
  opposite. **A user-facing doc must be walked against the product, not derived from the spec table it
  was designed alongside: the design table is grouped by "cannot be wired", the rendered board is not.**

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
- **S2 — Severed mappings, lineage data, widened gate. DONE + live on abm · acme · payobook ·
  payobook_template (2026-08-24).** pb_hr_payroll_formula **19.0.1.75.0** · pb_integrations
  **19.0.1.11.0**. Shipped: explicit `ondelete='set null'`; `target_rule_code` and
  `target_column_letter` as REMEMBERING stored computes; stored `is_severed`; `_severed_verdicts()`
  (writes nothing) + `action_repair_severed()` with the four-tier ladder; `legacy_component_code` in
  `component_code.py`; uncapped `_consumed_field_names()` + stored `consumed_field_paths`;
  `@api.constrains('output_key')` (create/write only, O-5) with `OUTPUT_KEY_RE` as the single
  definition the composer imports; the `NUM_DEPENDENTS` placeholder and help corrected; the widened
  connector gate.
  **Repair: 23 of 23 applied, 0 still severed** — abm 15 (6 `exact`, 9 `renamed`, scope `company`;
  all 8 rule outputs now have exactly one live consumer), payobook 8 (7 `exact`, 1 `renamed`, scope
  **`cross_company`** — connector in company 1, components in company 2, codes matching exactly).
  Pre-repair snapshots at `/tmp/s2_pre_{abm,payobook}.txt` on the server.
  **A full upgrade-time recompute of the new computes was a byte-identical no-op on both databases**
  (the ordering proof). **Neutrality: the post-repair payobook recompute is byte-identical to the
  pre-S1 baseline** (`b1dcd785739e1c0f49d304ee5428229a`) — repairing the wires changed no payslip
  number, because all 6 payobook batches are `source_type='excel'` and the gate does not open for
  them. Gotchas **S9**, **S10**, **S11**.
- **S3 — One run, two sources. DONE + live on abm · acme · payobook · payobook_template
  (2026-08-25).** pb_hr_payroll_formula **19.0.1.77.0**. Shipped: `source_binding` +
  `source_binding_key` + origin/date/uid stamp and `set_source_binding()` on `hr.formula.rule`
  (two Chars, never an FK); non-stored `binding_dangling`; a constraint refusing a half-set binding
  and a binding on a calculated component; `raw_data_topup_json` + `source_origin` + `get_topup_data()`
  on the import line; `lookup_in_with_key(data, candidates)` (the existing ladder, parameterised);
  the bound branch with binding-wins / fallback+`fell_back` / `ignored` (reusing S2's
  `ignored_side`); `_identity_from_file_row` / `_identity_from_store_row` as pure moves;
  `_merge_topup_rows` + `action_top_up_from_data_store` (merges, never unlinks);
  the `19.0.1.77.0` provable-only back-fill migration.
  **Neutrality, both forms: byte-identical to the pre-S1 baseline
  (`b1dcd785739e1c0f49d304ee5428229a`) AND `_sourcing_bound_branch_entered == 0`** — the new path was
  never reached, not merely in agreement. 15/15 tests, including a dual-source run on
  payobook_template where the feed binding won over a spreadsheet value and recorded it as `ignored`.
  Gotchas **S12**, **S13**.
- **S4 — Every screen says where a value comes from. DONE + live on abm · acme · payobook ·
  payobook_template (2026-08-25).** pb_formula_studio **19.0.1.127.0**. Shipped: `source` block on the
  studio serializer (`declared` + `actual`, computed once per config — one payslip read, not one per
  component); `_declared_source` / `_source_actuals` / `_source_employee_dest_ids` / `_source_note`;
  the shared `source_vocab.js` (8 kinds, labels, one `srcSentence`) imported by the studio AND the
  grid so five surfaces cannot paraphrase one fact; `SrcIco` glyphs; chips on the components rail,
  the card hero subtitle, the Cell Editor (a new "Where this value comes from" section, with the
  legacy block relabelled "Manual classification (does not affect import)"), the grid column header,
  and the right column of both mapping boards via a new `srcKind`/`srcChip`/`.mc-src` axis.
  **Measured: 0 bounding-box overlaps from the new chips at 1440 AND 1024** (rail 78/78 rows, board
  41 chips, grid glyph pinned bottom-right); 3 pre-existing grid-header overlaps found and reported
  (**S15**). **Payload +5.2%** (6.5 KB on 126.4 KB for 86 components; +3.9 KB on 74.8 KB for 53),
  server-side cost 49.6 ms for 99 rules. **Zero writes proven**: payobook `hr_formula_rule` checksum
  `eb80d6757a8f4a79a9f57e3b5ba13512` identical before and after, all counts unchanged; abm unchanged
  (bound=0, severed=0, wired=33). Gotchas **S14**, **S15**, **S16**, **S17**.
- **S5 — Lineage in place, sealed components, cockpit. DONE + live on abm · acme · payobook ·
  payobook_template (2026-08-25).** pb_formula_studio **19.0.1.128.0** · pb_hr_payroll_formula
  **19.0.1.78.0** · pb_integrations **19.0.1.12.0**. Shipped: the "Derived here" post-pass (computed
  provenance survives a sync; `expected_missing` never set on a computed key — the amber "not sent"
  lie is gone); lineage as a THIRD payload on the shared popover (summary · Reads · If nothing
  matches · Feeds · Open rule); calculated components shown and sealed on both boards (45 badged on
  abm) with the refusal enforced in `clickRight`, on the Enter path through it, AND server-side in
  both create RPCs; inline "Create a rule for this" with a converter-legal pre-filled key; cockpit
  "Feeds these components" / "Produced by" / "Lost its component" / a Feeds count column; four health
  hints on `get_board`; and **S15 fixed under the owner's ruling — the header reserves space for the
  what-if button and the code is never truncated.**
  **Measured: 0 overlaps at 1440 AND 1024 across rail, grid and board, and 0 codes truncated** — the
  pre-existing 3/2 from S4 are now 0/0. **S11 acceptance PASSED: the orphan-rule hint surfaces 14 of
  payobook's 14 rules** (and correctly 0 on abm, where S2 wired all 8). Zero writes: payobook rule
  checksum `eb80d6757a8f4a79a9f57e3b5ba13512` unchanged. Gotchas **S18**, **S19**, **S20**.
- **S6 — One pill, an Excel source you can choose, lineage where it belongs. DONE + live on abm ·
  acme · payobook · payobook_template (2026-08-25).** pb_formula_studio **19.0.1.129.0**. Three
  owner-reported defects, spec at `SOURCING_PHASE_S6_HANDOVER.md`, owner guide at
  `SOURCING_WALKTHROUGH.md`.
  Shipped: **D1** — sealed cards send no `srcKind` and their badge label comes from their own kind
  (`Calculated` / `Fixed value`), the de-duplicating `itemChips` assembler, and a **shared
  `McItemLabel` sub-template rendered by both columns** (the durable fix for S16/S18, closeout open
  item 5). **D2** — `import_mapping_data` never returns `no_batch`; three left-hand lanes (batch
  columns · bound keys · legacy `data_source_field`); the search box takes a heading or a column
  letter as typed (`canAddLeft`/`onAddLeft`); `import_mapping_create` writes a real
  `set_source_binding('excel', …, origin='board')` and no longer writes `data_source_field`;
  `api_mapping_create` writes the symmetric `feed`/`rule` binding; both deletes clear only their own
  binding; `_binding_replaced` returns a sentence naming both sides. **D3** — `_source_wire_dests`
  makes a live field mapping a declared source (`rule` beats `feed`, ties on lowest id);
  `_lineage_for_config` unions every connector that can reach the scheme; right-column cards carry
  lineage; both hosts now pass `onLineage` and `onRightBlocked`.
  **Measured on abm:** 99 right cards, **0 duplicate-pill cards**, 36 `Calculated` + 9 `Fixed value`
  (was 45 × `Calculated Calculated`, 9 of them contradicting their own chip); **8 `Rule output` chips
  with lineage** where the board previously showed none; **0 bounding-box overlaps at 1440 AND 1024**
  across all five adapters on both the full-screen studio and the overlay. Excel binding proven end to
  end (`NIGHSHIFHOUR` ← `excel`/`Basic Salary VND`/`board`), the switch to `feed` proven with its
  sentence, and both removals proven to clear it. **Neutrality: payobook `input_values` byte-identical,
  md5 `b1dcd785739e1c0f49d304ee5428229a`.** **Zero net writes: all four databases restored to their
  pre-test checksums.**
  Gotchas **S21**, **S22**, **S23**, **S24**, **S25**.

  **Independent re-verification (2026-08-25, second session — the phase was interrupted mid-way and
  every claim above was re-run from scratch against the deployed code and the live databases).**
  Deployed tree confirmed byte-identical to the working tree on all nine changed files (md5 per file);
  `latest_version = 19.0.1.129.0` on all four; **S17 satisfied** — the upgrade wrote the module row at
  `21:57:56Z` and `odoo-server` restarted at `22:07:40Z`, i.e. *after* it, so the running service holds
  the new Python. T1 36 `Calculated` + 9 `Fixed value`, T2 **0** duplicate-pill cards over **149/99/257/1/0**
  cards on the five adapters × two hosts × {1440, 1024} — **10 board-width combinations, 0 duplicates,
  0 overlaps, 0 clipped glyphs**. T4–T8 re-proven with a *different* key (`NIGHSHIFHOUR` ←
  `excel`/`Gross Salary VND`/`board`, `data_source_field` NULL), the switch sentence captured in both
  directions, and the delete proven to clear binding **and** legacy Char. T9–T11 8 rule-output chips +
  lineage on the owner's own connector-1 board; all **7** dual-wired components byte-identical across two
  independent loads, `NOOFDEPENDEN` → `rule`/`DEPCOUNT` (rule beats feed). T12 refusal on mouse, on
  **Enter**, and on both create RPCs. T13 all four DBs restored **exactly**: abm rules
  `38b09d9b32f70251fe138915451e2bed` / mappings `5c7eae5e44ace0f30440e80a47bbd280`, payobook rules
  `06eb9ed19cb628474d19cba8c759f688` / mappings `26928ec4ed0252c2cc0d28fa4afff79f`, acme and
  payobook_template empty. T14 neutrality re-run live: `b1dcd785739e1c0f49d304ee5428229a`,
  `BOUND_BRANCH_ENTERED 0`. T15 three batteries green. Zero console errors; no user-visible "Odoo".
  Gotchas **S26**, **S27**; one owner-facing error corrected in the walkthrough (closeout item 8).
