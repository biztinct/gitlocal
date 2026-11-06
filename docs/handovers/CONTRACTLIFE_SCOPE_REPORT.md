# CONTRACTLIFE SCOPE — report (2026-11-04 Sydney / 2026-11-03 UTC)

Handover: `docs/handovers/CONTRACTLIFE_SCOPE_HANDOVER.md`. Module touched:
`pb_contract_lifecycle` only (+ its `vi_VN.po`). `pb_filter_kit` not touched.

## For the owner (plain English)

1. The Contracts decisions board now says what it counts: the first tab is
   **"With an end date 40"**, and the purple notice says "This screen tracks
   contracts with an end date, plus interns and contractors."
2. Two new tabs: **"Open-ended 170"** (grey cards, "nothing to decide", no
   buttons except "Open this contract") and **"All contracts 210"**. A grey
   line under the four steps reads "170 open-ended contracts have nothing to
   decide — see Open-ended" and opens that tab.
3. Nothing about the decisions changed: 26 ending, 28 nobody has decided,
   26 would be raised by "Run today's steps" — same as before. Live on all four
   sites.

## Commits (branch 19.1, pushed)

| Commit | What |
|---|---|
| `edf9154a9` | feat(contract-lifecycle): the board says it tracks contracts with an end date; Open-ended and All contracts tabs (19.0.1.3.2) |
| `eb94d25a9` | fix(contract-lifecycle): no empty chip row on a card with nothing to flag (template only, found in browser check) |

## What was built (engineering)

* `_pbf_base_domain` = company + state draft/open only.
* New `_cl_dated_domain` = `date_end != False OR employee_id any [active, employee_type in NON_PERMANENT_TYPES]`
  and `_cl_open_ended_domain` = `date_end = False AND employee_id not any [same]`.
  Written with `any` / `not any` on the many2one, NOT `~dated`: negating a
  dotted-path condition does not keep contracts with no employee. Verified
  dated + open-ended = base, overlap 0, on all four DBs (table below).
* `_cl_rules`: every review rule (`none/upcoming/decide/extension/conversion/done/lapsed`)
  and so `needs`, the four `steps`, `attention` carry `dated`; `undated`
  (intern with no end date) also carries `dated` (keeps the old "active
  person" condition). Attention option "Nothing needed" = `dated & ~attention`.
  New keys `dated`, `open_ended`.
* New hidden choice section `scope` (label "Contracts"; options "With an end
  date" / "Open-ended"). Built-in views, in order: `dated` (start view — the
  kit takes the first), `ending`, `undecided`, `waiting`, `temps` (+`scope: dated`),
  `open_ended`, `all` ("All contracts", `{}`).
* `get_board_head`: kpis and `total` count `base & dated` (unchanged numbers);
  new `all_total`, `open_ended`.
* `_row`: `open_ended` flag (Python twin of the domain, type read under sudo);
  for such rows review ignored, `needs=False`, `review_label` "Nothing to decide".
* Client: quiet card branch (`is-open-ended` grey background, "Open-ended ·
  nothing to decide" step line, "No end date", no "The decision" / "Raise the
  decision", no "No end date on the paperwork" chip, card top opens the
  contract drawer); muted line under the steps with a "see Open-ended" link
  (`kit.useView('open_ended')`); "Show all contracts" now opens the All
  contracts view; empty-state panel switched to `all_total`; a dedicated empty
  panel when the start tab is empty but open-ended contracts exist (p0clone).
* Banner: the sentence is the second sentence in all three variants.
* `vi_VN.po`: 10 new msgids + python/js markers added to 3 existing ones
  ("Contracts", "All contracts", "No end date"); polib parse 107 entries,
  unique msgids. No "Odoo" in any added user-visible string (diff scanned).
* Manifest 19.0.1.3.1 -> 19.0.1.3.2.

## Tests

| # | Result | Evidence |
|---|---|---|
| S1 | PASS | rize, browser: tab row `With an end date 40 · Ending within 60 days 26 · Nobody has decided 28 · Waiting to be agreed 0 · Interns and contractors 0 · Open-ended 170 · All contracts 210`; numbers line 26 / 28 / 0 / 0 / 0; Running 40 contracts, 28 need a decision. Identical to the before-RPC (`all 40, ending 26, undecided 28, waiting 0, temps 0`; steps running 40 / undecided 28). Shot `01_with_an_end_date.jpg` (before: `00_before.jpg`). |
| S2 | PASS | Open-ended: "170 of 210 contracts"; DOM check on the 60 loaded cards: 60 `is-open-ended`, 0 containing "Raise the decision" / "The decision" / "Somebody has to choose", step line "Open-ended · nothing to decide", when "No end date", "Where it stands: Nothing to decide"; four steps read 0 on this tab. Shots `02_open_ended.jpg`, `03_open_ended_quiet_cards.jpg`. |
| S3 | PASS | All contracts: "Showing 60 of 210", mix of dated (orange) and quiet cards; search "Le Thi Hoa" -> 1 of 210, the open-ended Demo Le Thi Hoa card. Shots `04_all_contracts_search.jpg`, `05_all_contracts.jpg`. |
| S4 | PASS | rize: line reads "170 open-ended contracts have nothing to decide — see Open-ended"; the link opens the Open-ended tab (60 of 170). Zero case checked on **payobook_template** (server shell, `get_board_head` as admin): `open_ended 0` -> the line's text is empty, so it is not rendered (that DB has no contracts at all, so it shows the "No contract has an end date on it" panel). p0clone has 0 dated / 7 open-ended -> the start tab shows the new "everybody is open-ended — See Open-ended" panel. |
| S5 | PASS | "Would raise" (`_due_for_decision`, unchanged code, its own domain with `date_end` between today and today+lead) = **26 before and 26 after** on rize. Not run on rize. |
| S6 | PASS | Console after a fresh load and switching With an end date -> Open-ended -> All contracts -> With an end date: no errors or warnings (only the pre-existing breadcrumb/debranding/tour log lines). Shots in `docs/handovers/contractlife_scope_shots/`. |
| S7 | SKIPPED | The module has no `tests/` package (handover: skip with reason). Equivalent check done live instead: domain counts per DB, below. |

Domain check (server shell, sudo, read-only, rolled back), before the deploy:

| DB | draft/open contracts | dated (new) | old base | open-ended | overlap |
|---|---|---|---|---|---|
| rize | 210 | 40 | 40 | 170 | 0 |
| p0clone | 7 | 0 | 0 | 7 | 0 |
| payobook_template | 0 | 0 | 0 | 0 | 0 |
| payobook | 4,523 | 7 | 7 | 4,516 | 0 |

After the deploy, `get_board_head` + views: payobook `dated 7, ending 3, waiting 2, temps 4, open_ended 4516, all 4523`; p0clone `dated 0, open_ended 7, all 7`.

## Deploy

* START/DONE (+ a hash-correction NOTE) lines in `/opt/deploy-notes.md`.
  Announcement to other sessions: `ListAgents` was not available in this
  subagent; the coordinator announced it (confirmed by message).
* `full` (edf9154a9): run dir `/tmp/cls-run-20261103215459`, result **OK**;
  backups taken; upgrade EXIT=0 errors=0 on p0clone, payobook_template, rize,
  payobook; crons on before/after 31/28/74/42 unchanged; sites 200;
  `latest_version` 19.0.1.3.2 on all four.
* `looks` (eb94d25a9, template only, version unchanged): `/tmp/cls-run-looks1`,
  result **OK**, assets purged on all four.
* Content: module tree hash `ec3906fd601f` on the server = repo at eb94d25a9.

## Deviations

* Rule naming: the handover said `undated = ~dated`. `_cl_rules` already had an
  `undated` key (intern/contractor with no end date, used by the "Needs
  somebody" filter), so the complement is `open_ended`, and it is written
  explicitly with `not any` instead of `~` (see above).
* The scope tabs use a hidden filter section, so the "With an end date",
  "Open-ended" and "Interns and contractors" tabs show a removable chip
  "Contracts: With an end date / Open-ended". Removing it shows all contracts.
* Extra: dedicated empty panel for a DB whose contracts are all open-ended,
  and the empty chip row fix (second commit).

## Gotchas (for the ledger)

* **Negating a dotted-path domain is not the complement.** `~(employee_id.active = True & …)`
  becomes path conditions that drop rows with no employee. Use
  `('employee_id', 'any', [...])` and `('employee_id', 'not any', [...])`
  and prove `A + B = base, A & B = 0` on the live data.
* **A builtin view can only carry `filters`, not a domain** (pb_filter_kit).
  To give a view a fixed population, add a `hidden: True` choice section and
  put it in the view's filters.
* The kit remembers the last tab per browser session; after a deploy that
  renames views, an old session lands on whatever view key still matches
  (`all` now means 210, not 40). New sessions start on the first view.
* Follow-up outside this module (not done, scope rule): `pb_learn` keeps a
  replica of this screen (`screens.js`, key `contractends`). Its tab names
  ("All") are now out of date; per "lessons follow screen changes" it needs a
  refresh in a pb_learn pass.
