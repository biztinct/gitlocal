# CONTRACTLIFE SCOPE — say what the decisions board counts, and show the rest

Owner finding 2026-11-04 on `rize.payobook.com`: the Workforce › Contracts
*decisions* board (module `pb_contract_lifecycle`, screen tag `contractends`)
says "All 40" while the tenant has 210 running/draft contracts and 241 active
people. Nothing on the screen says that it only tracks contracts **with an end
date** (plus interns and contractors). Owner ruling: the screen must say so,
and must also let the reader see the **open-ended** contracts and **all** of
them.

Binding rules: `docs/handovers/fillin/FILLIN_LEDGER.md` §0 (plain English,
never "Odoo", design bar, browser validation on rize, four-DB deploy, commit
per feature). Do not touch any module other than `pb_contract_lifecycle`
(+ its `.po`).

## Decision (made — do not re-open)

1. The board keeps its purpose (decisions on contracts that end) and its
   default view, but the first tab is renamed **"With an end date"** (count
   unchanged, 40 on rize). The tab row becomes:
   `With an end date 40 · Ending within 60 days 26 · Nobody has decided 28 ·
   Waiting to be agreed 0 · Interns and contractors 0 · Open-ended 170 ·
   All contracts 210`.
2. **Open-ended** lists draft/running contracts with no end date for
   permanent people. Their cards are *quiet*: grey step line reading
   "Open-ended · nothing to decide", no "Raise the decision" button, no
   "Somebody has to choose" badge, the two ghost buttons (Open this contract ·
   The decision → only "Open this contract") remain. Days-left shows "No end
   date".
3. **All contracts** = both.
4. The four step counters (01 Running … 04 Decided) keep counting the
   decision population only. Under the counters add one muted line:
   "170 open-ended contracts have nothing to decide — see Open-ended." (number
   live; hidden when 0).
5. The info banner at the top stays; its second sentence gains: "This screen
   tracks contracts with an end date, plus interns and contractors."

## Plumbing (verified 2026-11-04 — do not re-derive)

* Facade `pb.contractlife` (`pb_contract_lifecycle/models/pb_contractlife.py`),
  a `pb.filter.mixin` board: `_pbf_base_domain :301-310` (today: company +
  state in draft/open + (date_end set OR active non-permanent employee)),
  `_pbf_builtin_views :477`, `_cl_rules :329` (every card fact as a domain),
  `_pbf_spec :390` (filters incl. `step` at `:449-455`), `get_board_head :500`
  (strip counts), `get_board_page :544`, `_cl_step_counts :577`, `_row :186`
  (card payload). Client `static/src/js/contractlife_board.js`, template
  `static/src/xml/contractlife_board.xml`. The old unpaged `get_board :93`
  still exists (nightly step uses no cap, R76) — leave it.
* `NON_PERMANENT_TYPES` from `models/contract_common.py`.
* rize numbers today: 210 draft/open contracts, 40 with an end date (36 open +
  4 draft), 170 open-ended, 241 active people (41 of them have no draft/open
  contract — not this board's problem).
* Filter-kit precedent for built-in views with a fixed domain: the Contracts
  roster `pb_contracts/models/pb_contracts.py:223-231`; counts per tab refresh
  after an action (FILTER kit 1.3.0).
* Gotcha from FILTER: a board inside a hub lens must not create its own
  scroll container (`FILTER_CLOSEOUT.md` §3 / memory filter-program 11-03).

## Build

1. `_pbf_base_domain` → company + state in draft/open (no more). Add a rule
   `dated` = `['|', ('date_end','!=',False), '&', ('employee_id.active','=',True),
   ('employee_id.employee_type','in', NON_PERMANENT_TYPES)]` and `undated` =
   `~dated` in `_cl_rules`. Every existing step/decision/attention rule gets
   `& dated` so the head strip, the step counters and the "Nobody has decided"
   counts do not change.
2. `_pbf_builtin_views`: `dated` (label "With an end date", default),
   existing ones unchanged, `open_ended` ("Open-ended", domain `undated`),
   `all` ("All contracts", `{}`). Make `dated` the default view (check how the
   kit picks the default: first entry, or a `default: True` key — read
   `pb_filter_kit`).
3. `_row`: add `'open_ended': bool` and, for such rows, `days=None`,
   `step='open'`, `decision=None`, `needs=False`. Card template branches on
   `row.open_ended` (quiet style; reuse the existing muted tone classes).
4. `get_board_head`: add `'open_ended': count(undated)`; template line under
   the counters.
5. Banner sentence; `.po` EN+VI for the new strings.
6. Bump `pb_contract_lifecycle` manifest patch version.

## Tests (numbered; report each)

| # | Case | Expect |
|---|---|---|
| S1 | rize, open the board | first tab "With an end date 40"; counters unchanged (26/28/0/0); new tabs "Open-ended 170", "All contracts 210" |
| S2 | click Open-ended | 170 quiet cards, no Raise button, "Open-ended · nothing to decide", "No end date" |
| S3 | click All contracts | 210; search by name finds an open-ended person |
| S4 | the muted line under counters reads "170 open-ended contracts…" and disappears on a DB with 0 (p0clone or payobook_template — check and say which you used) |
| S5 | "Run today's steps" still raises only dated contracts (compare the would-raise count before/after on rize; do not actually run it on rize) |
| S6 | console clean on all three tabs; screenshots in `docs/handovers/contractlife_scope_shots/` |
| S7 | unit test in `pb_contract_lifecycle/tests/` if the module has a tests package: base domain counts dated/undated correctly on a tiny fixture (skip with a stated reason if no package exists) |

## Deploy

Commit `feat(contract-lifecycle): the board says it tracks contracts with an
end date; Open-ended and All contracts tabs`, push `19.1`; announce; deploy
`full` (`pb_contract_lifecycle`) to the four DBs; START/DONE lines; versions
verified per DB.

## Report (`docs/handovers/CONTRACTLIFE_SCOPE_REPORT.md`)

S1–S7 with evidence, deploy evidence, a 3-line plain-English summary for the
owner, and any gotcha.
