# MAPFIX Phase B — A complete field catalogue, re-routable colour coding, and nothing left behind

Read `docs/handovers/MAPFIX_LEDGER.md` FIRST (owner decisions MF-B1…B4, verified facts) plus
`docs/handovers/COLROLES_LEDGER.md` (CR1-CR33 bind; CR6 chmod + psql check, CR20 websocket hang,
CR33 RPC password, and: live mapping validation must use **abm**, not the apex admin session).
Phase A shipped readable ≤12-char codes and renamed every existing code — the mapping board will now
show short codes; that is expected.

Line numbers below are pre-Phase-A. Phase A edited `pb_formula_studio.py`, both import wizards and
`formula_rule.py` — **re-locate by SYMBOL**.

## Scope

This phase turns the Employee/Contract mapping board from a curated shortlist into the place where
**every** imported column gets resolved.

1. **Generated field catalogue** (MF-B1) replacing `_EC_CURATED`, including many2one, grouped.
2. **Re-routable colour coding** (MF-B2/B3): contract-component cards become wirable; wiring one to
   a native field demotes it from a component; plain columns can be promoted to amount OR text
   components. Existing contract data is KEPT as history.
3. **Reconciliation step** (MF-B4): before finishing, every unresolved column is listed, pre-ticked
   to become a contract component, individually untickable to leave as `reference`.

**Binding non-goals**: NO error-dialog or Primary Key work (Phase C). NO changes to the bank sync
mechanics themselves (Phase 3 of COLROLES shipped and validated those). NO new overlay — extend the
existing employee mode of the mapping board.

## Build spec

### B1. The field catalogue — generated, grouped, complete

Replace `_EC_CURATED` (`pb_formula_studio.py:5005-5015`) with a computed catalogue.

**Inclusion rule** — a field on `hr.employee` / `hr.contract` is mappable when it is:
- stored (`store=True`), not `readonly`, not a compute without an inverse,
- `ttype` in the widened set: today's `_EC_TTYPES` (:5003) **plus `many2one`** (MF-B1). The batch has
  always supported m2o — `_coerce_mapped_value` does search-by-name-else-create and
  `_sync_employee_contract_mirror_fields` mirrors `job_id`/`department_id`/`resource_calendar_id`/
  `company_id` — the UI simply could not express it. Keep one2many/many2many excluded (the mapping
  model's own domain excludes them).
- not on the deny-list.

**Deny-list** (technical noise, not user data): `create_uid`, `create_date`, `write_uid`,
`write_date`, `__last_update`, `display_name`, `id`, anything starting `message_`, `activity_`,
`access_`, `rating_`, `website_message_`; plus `active`, `color`, `sequence`, `parent_path`, avatar/
image fields, and computed presence/kanban helpers. Build it as an explicit tuple of names +
prefixes with a comment saying why, so it is auditable.

**Grouping into lanes** (the curation moves from *what you may map* to *what you see first*):
`Identity` (name, employee_id, barcode, identification_id, passport_id, registration_number) ·
`Personal` (gender, birthday, place_of_birth, country_id, marital, children, …) ·
`Contact` (work_email, work_phone, mobile_phone, private_email, private_phone, address fields) ·
`Job & Organisation` (job_title, job_id, department_id, parent_id, coach_id, company_id,
resource_calendar_id) · `Contract terms` (all hr.contract fields: wage, wage_type, hourly_wage,
date_start, date_end, trial_date_end, structure/type, notes, …) · `Bank account` (the existing four
synthetic `b:` cards, `_BANK_LANE_ROLES` :5026) · `Other employee fields` / `Other contract fields`
(the honest remainder, so nothing is hidden).
Order lanes as above; within a lane, curated-first then alphabetical. Ship the lane definition as
data-in-code (a dict of lane → field names, plus a fallback lane) so adding a field later is a
one-line edit, and any field NOT named in a lane still appears under "Other …".

`_ec_right_items` (:5074), `ec_search_fields` (:5210) and `ec_model_fields` (:5221) all read from the
new catalogue; search must still reach fields outside the default lanes (i.e. search is broader than
or equal to the catalogue). Verify the m2o widening does not break `_coerce_mapped_value` for a
field whose comodel has no `name` (rare; fall back to `display_name`/id and log).

### B2. Colour coding becomes a suggestion (MF-B2/B3)

Today COLROLES Phase 3 renders contract-component cards as **non-wirable** badged cards
(`_mc_item`-built left items; badge "Contract component" / "Text component"). That was correct then
and is wrong now.

- **Left cards become wirable regardless of component status.** Keep the badge (it tells the truth
  about where the value currently goes) but allow a wire to be drawn to any right-hand card.
- **Wiring a component to a native field DEMOTES it**: in the create path
  (`employee_mapping_create`, was :5010-ish / the `b:`-prefix branch added in P3), when the left rule
  has `is_contract_component`, clear `is_contract_component` and `is_text_component`, set
  `column_role` appropriately for the destination (bank → `bank`; hr.employee → `profile` unless the
  field is an identity field → `identity`; hr.contract → `contract`), and set
  `column_role_source='user'`. **Do not delete or alter any existing
  `hr.contract.advantage.template` or its lines** (MF-B3: history is kept; the component simply
  stops being written to on the next run). Return a note in the RPC result so the UI can say so.
- **Unwiring** restores nothing automatically — the column becomes unresolved and shows up in the
  reconciliation step (B3). That is the intended loop.
- **Promotion both ways**: Phase 3 shipped `employee_mapping_make_text_component`. Generalise to
  `employee_mapping_make_component(rule_id, value_type)` accepting `'amount'|'text'`, keeping the
  old method as a thin alias if anything calls it. Promotion sets `is_contract_component=True`,
  `is_text_component=(value_type=='text')`, `column_role` = `payroll` for amount / `contract` for
  text (COLROLES CR-A2), `column_role_source='user'`, and removes any existing native mapping wire
  for that rule (a column has ONE destination).
- **UI affordances**: on a left card, a small menu/hover action offering "Make amount component",
  "Make text component", and (when it is a component) "Send to a field instead…" which simply
  focuses the right column for wiring. Distinct chips for amount vs text (COLROLES used red-tinted
  for amount, indigo for text — keep those).
- When a demotion happens on a rule whose template already has contract lines carrying values, the
  RPC result must include a human sentence the UI shows once, e.g. *"Existing contract values for
  this component are kept as history; new imports will write to <field> instead."* (MF-B3).

### B3. Reconciliation — "nothing left behind" (MF-B4)

A new step reachable from the mapping board (a footer bar button, e.g. "Resolve remaining N
columns", enabled whenever N > 0; plus an entry in the board header counts).

- **Unresolved** = a rule that is NOT a contract component, has NO mapping row, and whose
  `column_role` is not already `reference`, and which is not `column_type` formula/constant
  (computed columns need no destination). Payroll-role input columns that feed formulas ARE resolved
  by definition — exclude any rule whose code appears in another rule's `formula_dependencies`
  (comma-split; see COLROLES CR2) and say so in the dialog's footnote.
- The dialog lists each unresolved column: name, code, column letter, a few sample values, the
  inferred value type (amount vs text — reuse the classifier's `is_texty_sample` logic), and a
  pre-ticked "Make contract component" checkbox. Unticking marks it `column_role='reference'`,
  `column_role_source='user'` — imported and stored, but written nowhere.
- Apply is one RPC (`employee_mapping_resolve_remaining(config_id, decisions)`), all-or-nothing, and
  returns the refreshed board payload. Ticked rows go through the same promotion path as B2 so there
  is one implementation.
- After applying, the board's unresolved count must read 0 and the footer button disappears.
- Empty state: when N == 0 from the start, show a quiet confirmation ("Every column has a
  destination") rather than a button.

### B4. Health-hint alignment

COLROLES Phase 2 shipped `idunmapped`/`bankunmapped`. With reconciliation in place, add or adjust so
an unresolved column is visible outside the board too: ensure `idunmapped` (or a new `unresolved`
kind) counts exactly what B3 counts, so the problems rail and the board never disagree. Check what
Phase 2/3 actually shipped before adding a duplicate kind.

## Numbered test cases

Odoo TransactionCase (coded for CI; live-verified per the COLROLES method):
1. Catalogue includes `hr.employee.name` and the four mirror m2o fields (`job_id`, `department_id`,
   `resource_calendar_id`, `company_id`); excludes `create_uid`, `message_follower_ids`,
   `__last_update`; every returned field is stored + writable + allowed ttype.
2. Every catalogue field lands in exactly one lane; unlisted fields fall into "Other …"; no field
   appears twice.
3. `ec_search_fields` reaches at least one field that is NOT in any default lane (search ⊇ catalogue).
4. Mapping an m2o (`department_id`) end-to-end: batch run resolves the name to an existing
   department, and creates one when missing (`_coerce_mapped_value` path) — assert both.
5. Demotion: a rule with `is_contract_component=True` + an existing template WITH lines carrying
   values, wired to `hr.employee.job_title` → flags cleared, role/source updated, mapping row
   created, **template and lines still exist untouched**, RPC returns the history sentence.
6. After demotion, a batch run writes `job_title` and no longer writes the advantage line.
7. Promotion to amount and to text sets the right flags/role and removes any pre-existing native
   mapping for that rule.
8. Promote → demote → promote round-trip leaves exactly one destination at every step (never two).
9. Unresolved set: excludes formula/constant columns, excludes rules referenced by another formula,
   excludes already-mapped and already-component rules, includes the rest.
10. `employee_mapping_resolve_remaining`: ticked → component with the inferred value_type; unticked →
    `reference` + source `user`; all-or-nothing on a bad payload; board count reads 0 after.
11. Reconciliation is idempotent (running it again finds nothing).
12. Health-hint count equals the board's unresolved count on the same fixture.

Frontend (hoot if the suite exists, else scripted Chrome-MCP DOM assertions):
13. Component cards are wirable; badges still render; lane headers render in the specified order.
14. Footer button appears with the right count and disappears after resolving.

## Deploy + live verification

1. Local: python compile, JS parse (.mjs copy + `node --check`), XML parse, SCSS compile if touched.
2. Deploy per ledger ritual (`-u pb_hr_payroll_formula,pb_formula_studio` as touched) to all 4 DBs,
   chmod, sentinel, **psql `latest_version` verification**, restart, port bound.
3. Chrome-MCP on **abm** (action-742; park other tabs on `about:blank` first — CR20):
   - Right column now shows lanes incl. Identity with **Employee Name**, and Job & Organisation with
     Department/Job Position — screenshot.
   - Wire one of ABM's colour-coded components to a native field; confirm the demotion notice and
     that the contract still shows its historical component values (open a contract and check).
     **Then undo it** (re-promote) so abm is left as found — record what you changed and restored.
   - Open the reconciliation dialog on ABM's config, screenshot the list with counts, untick one row
     to see the `reference` outcome, then **cancel** without applying (leave abm unchanged) — unless
     the list is empty, in which case screenshot the empty state.
4. Self-review diff vs spec; ONE feature-scoped commit (include ledger + this handover), no push.

## Report back

Catalogue size per model (before: 15 employee / 7 contract; after: N/M) and the lane breakdown;
per-test results; screenshots taken; exactly what was changed and restored on abm; deviations;
MF-numbered gotchas appended; files touched; manifest versions; commit hash.
