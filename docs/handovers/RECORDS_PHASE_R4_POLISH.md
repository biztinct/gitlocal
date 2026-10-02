# RECORDS Phase R4 — defect round + close-out

Program: RECORDS. Phase 4 of 4 (conditional round, triggered by the R1–R3 self-scores). Modules:
`pb_records`, `pb_payrun_wizard`. Read `docs/handovers/RECORDS_LEDGER.md` (RD1–RD34) first;
R1 `6fbbe1b4`, R2 `2bc0aee2`, R3 `42a43687` are committed and live.

## Design bar (binding — score the report against it)

> "Extreme WOW, intuitive, out-of-this-world experience, best in class." Every surface names its
> hero moment; zero dead-ends; plain language over code vocabulary; motion with purpose; keyboard +
> bulk ergonomics; measured against the best SaaS tool in the category, not stock Odoo. Lucide
> icons, never emoji. Chrome-MCP walk every flow. Never the word "Odoo" in a user-visible string.

## The defects (each named by a phase report; fix ALL, in this order)

**D1 — Apply button occluded (R3).** At 1600px the desk's Review-drawer Apply button is partly
under the floating PayAI / "Stuck?" bubble. A primary action under another layer is a dead-end.
Fix in `pb_records` only: give the drawer footer a bottom safe-area that clears the bubble
(measure the bubble's box live; do not move the bubble — it belongs to another module), and run
the overlap sweep precedent (`pb_formula_studio/tools/mapping_overlap_sweep.js`, MJ38) over the
desk at 1280 / 1440 / 1600 / 1920 with the drawer open: 0 same-layer overlaps of user-openable
elements.

**D2 — Review drawer at scale (R2).** 140 people with the identical change render 140 rows.
Collapse: group by (field, old → new) when a group has ≥ 3 people — one row *"SHUI Participation:
YES → NO · 140 people"* with a chevron that expands to the names; mixed changes stay per person.
The count line stays exact. Keyboard: Enter/Space toggles a group; the tablist still walks with
arrows. Applies to grid-mode and file-mode alike.

**D3 — Header crowding ≤ 1280px (R3).** Export (split) + Import drop + History + Review compete.
Collapse Export/Import into one **File** menu (Export with data · Export blank template · Import a
file) below 1440px; keep the drag-anywhere overlay. Review stays a standalone primary button at
every width.

**D4 — "Not in Payobook yet" exceptions (R1).** In the pay-run Review step, the one-time
exceptions are a flat list. Group them under one heading *"N people in the file are not in Payobook
yet — they were listed, not paid"* with a next step: **Open Records Desk** is wrong here (nothing to
edit); the right door is the Import wizard (`pb_import_wizard`'s action, probed via the actions
registry) labelled *"Add these people"*, plus a *Copy names* button. `pb_payrun_wizard` only.

**D5 — Template-DB test (R3).** `TestRecordsR2Desk.test_09` fails on `payobook_template` because
`res.company.create` raises "You must have at least an administrator user." (template DB
`access_roles` data). Make the fixture create the second company through whatever precedent the
repo already uses on that DB (grep tests for `res.company` creation with a user), or `skipTest`
with the exact reason when no admin user is active — never delete the case.

**D6 — Progress for a large import (R3).** `import_peek` shows only a busy veil. Return a
`progress` stream is over-engineering; instead show *"Reading N rows…"* from the client-side row
count (parse the header + count rows client-side is not possible for .xlsx) — so: the server
returns `rows` early in a first cheap call `import_probe(file)` (parse only, no matching, ≤ 300ms
on 4.5k rows), the client shows *"Matching 4,512 rows to people…"* while `import_peek` runs.
Two calls, one veil with a real sentence.

**Housekeeping.** `.r3shots/` is untracked — add it to `.gitignore` beside `.r1shots/` (commit
`b9ed86ab` precedent) and delete both dirs' contents after you have finished validating.
Update `RECORDS_LEDGER.md` with a `### R4` section and a **Close-out** block: final versions per
module, the four commits, the owner debts (26-red pre-existing test set on the wide tag run; HR
ADMIN date year 0024; duplicate id-card `066196005153` on two abm employees; `connector_id` unset
on every scheme; `payobook_template` has no active users so it can never be UI-smoked).

## Tests

- D1: the sweep result (counts per width) in the report; a hoot test that the drawer footer's
  bottom offset ≥ the bubble reserve.
- D2: hoot — 140 identical changes → 1 group row + expand/collapse; 3 mixed → 3 rows; count line
  exact; Python untouched.
- D3: hoot — at 1280 the File menu exists and the split buttons do not; at 1440 the reverse.
- D4: Python — `attach_spreadsheet(one_time=True)` return still carries `unmatched`; hoot — the
  Review step groups N exceptions under the heading with the button present only when the
  import-wizard action is registered.
- D5: the suite passes on abm AND payobook_template (report both counts).
- D6: Python — `import_probe` returns `rows` and creates nothing; timing on payobook's 4.5k file.
- Neutrality: payslip count + md5 unchanged on abm (`7dbeb2df1ff76ab1de11d7e43448d8f4`, 36).

## Deploy + verify

Bump `pb_records` → 19.0.1.2.0, `pb_payrun_wizard` → 19.0.1.15.0. Baseline first (RD tags), abm
→ restart → assets (RD17) → Chrome walk of D1–D4 + D6 with screenshots at 1280/1440/1600 → payobook
+ payobook_template → hashes + `latest_version`. Restore anything changed. Commit (explicit
paths): `fix(records): review grouping, apply-button clearance, file menu, one-time exception
grouping, template-DB test (R4)`. Do not push.

## Report back

Test counts baseline/after per DB; D1–D6 each with evidence + screenshots; the sweep table; the
design-bar self-score; RD entries; the close-out block you wrote; anything left out and why.
