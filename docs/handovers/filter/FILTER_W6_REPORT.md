# FILTER wave 6 — report (Payroll B + data)

Branch `worktree-agent-ac21d7c58ed161c48` (reset to `19.1` @ `d857c857b`, kit
1.2.0, before any work — the worktree had been created from an older commit).
Builder: Opus. Tested on the shared preview (`pbf_preview`, a copy of payobook)
— nothing touched the live addons, the live databases or `/opt/deploy-notes.md`.

**Summary: all five screens converted and passing T1–T22 and W6-T1…T4 on the
preview.** Testing found one real defect (Records Desk ignored the hand-picked
arrival in the grid — fixed, F31) and one translation-merge trap (shared terms,
F32 — fixed before shipping).

| Screen | Result |
|---|---|
| Import › Recent batches (`pb_import`) | PASS |
| Pay-run ledgers — Full & Final, Proration, Retro (`pb_payrun_ledgers`) | PASS (standalone and in the Pay hub) |
| Records Desk (`pb_records`) | PASS after one fix (hand-picked arrival) |
| Statutory › Data (`pb_statutory`) | PASS (policy / tax / adjustment / dependent) |
| Integrations — Connectors + Data (`pb_integrations`) | PASS |

Modules for the live deploy (sync + `-u` on all four DBs: every one gains a
dependency on `pb_filter_kit` and has Python changes):

| Module | Manifest version |
|---|---|
| pb_import | 19.0.1.7.0 |
| pb_payrun_ledgers | 19.0.1.4.0 |
| pb_records | 19.0.1.7.0 |
| pb_statutory | 19.0.1.5.0 |
| pb_integrations | 19.0.1.15.0 |
| pb_learn | 19.0.20.6.6 (other waves also bump pb_learn and edit `anchors.json` / `screens.js` — expect a merge on those files and on `learn_content.json`) |

pb_filter_kit was NOT changed (only staged to the preview as the handover asked).

---

## 1. Per screen

### 1.1 Import › Recent batches — `pb.import` → `hr.payroll.import.batch`, screen `import`
- Base: the reader's companies (unchanged from the old board).
- Sections: **Where it is** (Draft · Loaded · Matched · Validated · Processing · Done · Stopped with an error · Cancelled — the steps' own words), **Where the data came from**, **Pay period starts** pinned; Problems (Needs attention / No problems), Pay scheme, Connected system, Pay run, Use once, Company, Country, Started.
  Hidden on payobook (one value): Where the data came from, Connected system, Country.
- Views: All batches · Needs attention · In progress · Done this month (done + started this month — there is no "done on" date) · Drafts.
- Sorts: Newest first (default) · Oldest first · Latest pay period first · Most problem lines first · Name A–Z.
- Page 60 (`get_batch_page`); the 20-row cap and the status chip row are gone.
- The steps and the numbers line read the kit's counts (`always: ['state','errors']`) so they follow the filters (R1); a step ticks "Where it is"; Completed / In progress / With errors toggle their filters. **"With errors" now counts "stopped with an error OR some lines unreadable"** = the Needs attention view (W6-T3) — which is what the Learn glossary always said it counted.
- `get_import_data` still returns its 20 rows (the Learn facade reads them, R4).
- Embedded as Pay hub › Inputs: verified (no title, panel inside the lens).
- Learn: `im-batches` stays on the whole panel (its lesson describes the rows: Lines, Matched, Errors); the layout carries a new **`im-filters`** (reserved); replica draws the strip. *Deviation:* the handover said `im-batches` → layout coach; moving it would have pointed its lesson at the toolbar instead of the rows.

### 1.2 Pay-run ledgers — `pb.fullfinal` / `pb.proration` / `pb.retro`, screens `fullfinal` / `proration` / `retro`
- `pb.ledger.mixin` inherits `pb.filter.mixin` (shared hooks: model, screen key, company base, currency); each ledger declares its spec, views, sorts. New `get_head` (words, KPIs, step definitions) + `get_page` (60 a page). `get_data` kept (tests read it, R4), rebuilt from the same row/KPI helpers.
- Full & Final sections: **Where it is** (Being prepared · Sent back to be fixed · Waiting for approval · Approved · Turned down), **Source**, **Department** pinned; Checks (Ready to check / Could not be worked out / Nothing to check), Waiting on me (literal domain on the stored `seat_user_ids`; no Python fact needed), Pay scheme, Job position, Batch, Net payable (money), Settled on, Approved on, Company.
  Hidden on payobook: Waiting on me, Approved on, Company.
- Proration: **Component**, **Batch**, **Where it is** pinned; Department, Pay scheme, Counted by, Prorated amount, Effective, Company. Retro: **Component**, **Applied in batch**, **Where it is** pinned; Department, Pay scheme, Up or down, Delta, Period start, Company. (Pins follow the Learn lessons: F&F "Auto or Manual" → Source; Proration "answer one person" → Component + Batch.)
- Views: F&F All settlements · Ready to check · Waiting on me · Approved this month · Manual. Proration All lines · Posted this month · Still draft. Retro All adjustments · Posted this month · Still draft · Cancelled.
- Steps (F&F) read the kit's counts (`always: ['status','check','mine']`); a step ticks its states; flags (waiting on you / ready to check / sent back) are counted the same way. KPI figures with a facet call `toggleFilters`. Row action ("Send for approval") reloads the head and the kit, keeping view and filters.
- Hub `tabs` switch = `kit.reconfigure({model})`; each ledger keeps its own remembered filters and saved views (W6-T2).
- Removed: facet chips/selects, date chips, own search, "Showing all… press a step" line, 400-row cap.
- Learn: `lg-facets` = the layout's coach (shared by three screens); anchor description updated; replica `ledgerHTML()` draws the panel strip per ledger (`LEDGER_VIEWS`); two lessons reworded **at the source** (`docs/tutorial_poc/author/data.js`, L-steps on lg-facets: "Filters, then the Source section…", "The Component and Batch sections in Filters…") and `learn_content.json` regenerated (`gen_learn_data.py`; F36).

### 1.3 Records Desk — `pb.records.desk` → `hr.employee`, screen `records`
- Counts under sudo **behind the desk's own gate** (`_pbf_records` sudo; `pbf_layout` returns the refusal sentence for non-readers; `pbf_counts` / `pbf_find_values` call `_check_read()` first). Base = the desk's company scope + active.
- Sections = `pb.people._pbf_spec()` (same words as Employees; "Payroll-ready" unpinned) + **Employment status** (pinned; the pay feed's own words, one value per status the feed delivers, plus "Not stated in the feed") + hidden **Hand-picked** arrival section (from `ctx.picked`).
  On payobook the feed reports **no** statuses, so Employment status and the "Resigned per feed" view hide themselves (data-driven, correct). Hidden: Work country.
- **RD11 timing** (preview shell, payobook copy, 4,575 people): feed read `_pbf_feed` **84 ms, once per request** (cursor cache); `pbf_counts` for the pinned sections 219 ms; `pbf_layout` 399 ms; first window of 60 rows 1.2 s warm in the browser / 2.0 s cold (the old `search_people` first page: 3.2 s cold).
- Views: All people · Running contracts · No contract · Resigned per feed (only when the feed reports leavers) · Hand-picked (only when arriving with ids).
- Sorts: the Employees list's (Name A–Z / Z–A / Newest joiners / Longest serving).
- New `search_page` serves the grid's windows; "select all matching", the export and `matching_ids` send `{pbf, search, sort}` and `_matching` runs `pbf_domain` for that shape — **W6-T1: two filters → panel "208 of 4,575", select all matching → "All 208 people selected"** (103 ms).
- Fix after testing: the grid / select-all / export calls now send `context.pbf_ctx` (F31) — before, "Hand-picked 5" listed everybody.
- The rail is replaced by `<PbFilterLayout coach="'rd-who'">` around the WHAT strip and the grid, stretched to full height (F35); the panel scrolls on its own.
- `search_people` / `_facets` kept (their tests read them, R4).
- Learn: `rd-who` stays (layout coach), description updated; replica `records()` draws the panel strip.

### 1.4 Statutory › Data — `pb.statutory` with `ctx.kind`, screens `statutory:policy|tax|adjustment|dependent`
- R5: the board's policy and tax rosters stay as they are (tax = union of two models).
- Policies and tax tables are counted with archived rows (`active_test` off — the table always listed them); adjustments and dependents carry the W97 `_employee_scope` subquery in the base domain. A forged kind falls back to a real table.
- Sections: policy **Active or archived**, **Effective from**, **Company** pinned + Effective to; tax **Active or archived**, **Tax year**, **Company** + Country; adjustment **Status**, **Insurance**, **Kind of adjustment** + Adjusted on, Reason, Department, Employee, Company; dependent **Status**, **Relationship**, **Department** + Relief right now, Relief from, Employee.
- Views: All policies · Active · Archived; All tax tables · Active · This year; All adjustments · Draft · This month; All dependents · Waiting to be checked · Eligible.
- New `get_ledger_head` (now translatable words + columns — they were English literals) + `get_ledger_page` (60 a page); row builders shared with `get_ledger` (kept for its tests). Kit deferred until the Data view opens; tab switch = `reconfigure`.
- The "newest 400 loaded, narrow the search" foot is gone (paging: dependents 60 → 120 of 3,851).
- **W6-T4** (preview shell, throwaway one-company payroll officer, rolled back): adjustments total 1 of 46, matched 1, page 1, rows naming an employee the reader cannot read: 0.
- Learn: `st-data` stays (foreign); new **`st-data-filters`** on the layout (reserved). The replica does not draw the Data view (checked).

### 1.5 Integrations — `pb.integrations` with `ctx.kind`, screens `connectors` and `integrations:mapping|store|rule`
- Two panels: one over the connector cards (`get_connector_page`), one over the open Data table (`get_ledger_head` + `get_ledger_page`), both deferred until their view opens.
- Connectors: base `[]`, `active_test` off (ruling) — **archived connectors are listed with an "Archived" badge**. Sections **Connection**, **System**, **Last synced** (none = "Never synced") pinned; Last sync result, Feeds (only where the feed table exists), Records pulled, Sign-in method, Country, Company, In use or archived. Views: All connectors · Needs attention · Never synced · Synced today · Spreadsheet feeds. Connected / Errors on the numbers line tick "Connection". `get_board` still ships `composerConnectors` and the KPIs (R4).
- Data: base = the readable-connector scope as a record-rule subquery. Mappings **Connector**, **Mapping state**, **Feed** + Health, Target rule, Transform, Source data type, Required; store **Connector**, **Status**, **Data type** + Feed, Matched employee, Pulled, Period from, Pulled by, Changed since last pull, Used in batch, Company; rules **Connector**, **On or off**, **Errors** + Kind of rule, Reads, Built with, Source records, Last failed. Views per §32.
- Deep links (connector, feed, data type) arrive as **initial filters** — chips the reader sees and drops; the connector chip carries across the three tables. Verified: "View data" for a feed → Connector + Feed chips; dropping Feed → 14 rows.
- The module's `_facets` copy is deleted; the scope banners are gone (the chips replace them).
- Learn: `ig-filters` = the connectors layout's coach (description updated); **`ig-data` moved from `foreign` to declared** (test_06 forbids both); new `ig-data-filters` (reserved); replica strip redrawn.

---

## 2. Test matrix (preview, Chrome DevTools MCP 1440×900; T21 at 420×860)

| Test | Import | Ledgers (F&F / Pro / Retro) | Records Desk | Statutory Data | Integrations |
|---|---|---|---|---|---|
| T1 open, counts, first tab, list | pass | pass | pass | pass | pass |
| T2 tick → chip, own counts stay, others recount | pass | pass | pass | pass | pass |
| T3 OR within section | pass | kit ¹ | kit ¹ | kit ¹ | kit ¹ |
| T4 AND across | pass (9 of 11) | pass (steps follow) | pass (208) | pass | pass |
| T5 Only | pass | kit ¹ | pass | kit ¹ | kit ¹ |
| T6 find + Enter + Escape | pass | kit ¹ | kit ¹ | kit ¹ | kit ¹ |
| T7 nothing matches | pass | kit ¹ | kit ¹ | kit ¹ | kit ¹ |
| T8 date preset + range | pass | kit ¹ | kit ¹ | kit ¹ | kit ¹ |
| T9 number | n.a. | pass (₫50M or more → 18) | kit ¹ | n.a. | kit ¹ |
| T10 chip jump / × / clear all | pass (page did not scroll) | pass | pass | pass | pass |
| T11 search + / + Escape | pass ("VPTQ" 5 of 11) | pass | pass ("Nguyễn" 246) | pass | kit ¹ |
| T12 sorts | pass (5) | pass (4) | kit ¹ | kit ¹ | kit ¹ |
| T13 Show N more | n.a. (11 rows) | pass (60 → 88) | pass (virtual windows) | pass (60 → 120 of 3,851) | pass (60 of 238) |
| T14 save / rename / share / delete | pass | pass (Retro save; not on Proration) | kit ¹ | kit ¹ | kit ¹ |
| T15 built-in views | pass | pass | pass | pass | pass |
| T16 numbers line / steps | pass | pass | n.a. | n.a. | pass |
| T17 hide + reload | pass | kit ¹ | kit ¹ | kit ¹ | kit ¹ |
| T18 link → same filters | pass | kit ¹ | kit ¹ | kit ¹ | kit ¹ |
| T19 bulk / export on the filtered set | n.a. | n.a. (row action keeps filters) | pass (W6-T1) | n.a. | n.a. |
| T20 empty + way back | pass (filter and search) | pass | pass ("Clear the filters") | pass | pass |
| T21 phone drawer | pass | kit ¹ | CSS checked (F35) | kit ¹ | kit ¹ |
| T22 Vietnamese (`pbf_layout`, lang vi_VN) | pass | pass | pass | pass (all 4 kinds) | pass (all 4 kinds) |
| Console errors/warnings | clean ² | clean | clean | clean | clean |

¹ Same kit code path, exercised in full on Import (and the ledgers for T9/T13/T14).
² One run showed ConnectionLost toasts: the preview server had died / the tunnel dropped (F34). The kit's failure toast ("The list could not be refreshed…") and each screen's own ("The batches could not be loaded…") fired as designed.

Wave tests:
- **W6-T1** Records Desk: Running + one department → panel "208 of 4,575"; select all matching → "All 208 people selected". PASS. Employment section: not exercised (the payobook feed reports no statuses); its feed read costs 84 ms once per request.
- **W6-T2** Pay hub › Adjust: Retro (Component chip + a saved view) → Proration (own views, no Retro view, its own "Posted this month") → Retro (chip and view back) → Proration (its filters back). PASS.
- **W6-T3** Import: With errors 3 = Needs attention 3. PASS.
- **W6-T4** Statutory adjustments, one-company reader: 1 of 46, no unreadable employee. PASS.

Speed on the payobook copy (ms, layout / counts of every section / first page): Import 124/119/36 · F&F 117/99/235 · Proration 84/108/160 · Retro 79/84/162 · Records 409/765/1,219 · Statutory policy 41/58/32, tax 52/35/30, adjustment 105/220/127, dependent 202/1,753 (all 6 sections incl. Employee; the panel normally counts only the open ones)/162 · Connectors 90/68/141 · Mapping 80/78/59 · Store 75/93/60 · Rules 52/53/76.

Screenshots (Chrome DevTools MCP, local files under
`/Users/adity/.claude/projects/-Users-adity-Documents-GitHub-gitlocal/9210e315-2d9d-4acd-ba15-28e97cb48de6/tool-results/`):
`mcp-chrome-blob-1793415269842-3uzy6g.jpg` (Import), `…1793415694692-0wpdm4.jpg` (Import phone drawer),
`…1793429483788-q81kfe.jpg` (Pay hub › Settle), `…1793429605610-x6pt97.jpg` (Records Desk).

Test data touched on the preview copy: one settlement sent for approval (Ready to check row action); a throwaway user created and rolled back in a shell. No saved views left (checked); `pbf:*` storage cleared; tab closed.

## 3. Deploy evidence (preview rehearsal only — the live deploy is the coordinator's)
- `pbf_preview.sh upgrade pb_import,pb_payrun_ledgers,pb_records,pb_statutory,pb_integrations,pb_filter_kit`: **EXIT=0** (the first attempt failed with "could not serialize access" — another wave was upgrading the same preview at the same time, the hold race F26; rerun when idle). The script's "errors=N" counts the whole shared `upgrade.log`; none of its ERROR lines are from these modules.
- `ir_module_module.latest_version` on pbf_preview: pb_import 19.0.1.7.0, pb_payrun_ledgers 19.0.1.4.0, pb_records 19.0.1.7.0, pb_statutory 19.0.1.5.0, pb_integrations 19.0.1.15.0, pb_learn 19.0.20.6.6, pb_filter_kit 19.0.1.2.0.
- No `Filter section … hidden` / `Filter counts … failed` lines. Server log ERRORs during the test window are chat-presence write races from several browser tabs (other waves on the same preview).
- PO gate (server `PoFileReader`) passed on all five files; no `.pot` files (F20).
- Live: not touched. Cron counts / hashes / per-DB versions: n.a. for builders.

## 4. Kit gaps and design debts

Kit gaps (pb_filter_kit unchanged):
1. **`ctx` reaches only the kit's own calls** (F31). Every screen with a ctx-built section must remember to forward it. Ask: `kit.context` (or `kit.kw()`) exported for the screen's own calls.
2. **No per-value `domain_method` arguments.** Records' employment statuses are data (one per status the feed delivers), so they use literal id domains built from a cursor-cached read instead of `domain_method`.
3. **"Hidden arrival" sections** need a `_pbf_worth_showing` override (Records "Hand-picked"). Ask: a section flag `hidden: True` (shown only while on).

Design debts:
- Integrations: the numbers line counts connectors in use (31, 25 connected) while the panel lists archived ones too (33, 26 connected) — honest per its own words, but two scopes on one screen.
- Records Desk on payobook: Employment status never appears (no feed statuses); its behaviour on a tenant whose feed reports statuses (e.g. Rize) is unverified on a preview.
- Statutory dependents: counting every section at once is 1.75 s (Employee section over 3,851 rows); the panel only counts open sections, so normal use is far lower.
- Records Desk window of 60 rows is ~1.2 s warm (the per-row cell reads); unchanged per row, faster than before.
- Pre-existing, not fixed: older untranslated strings in pb_records / pb_statutory / pb_integrations (listed by the export, not part of this wave); the export also lists field names as msgids (extraction noise, left out).
- `pb_payhub/tests/test_payhub.py` expects 2 `!props.embedded` in ledger.xml; the file had 3 before this wave and still has 3 (pre-existing mismatch).

## 5. Self-score (design bar)

| Screen | Hero moment | Zero dead-ends | Plain language | Motion | Keyboard / bulk |
|---|---|---|---|---|---|
| Import | steps + numbers follow the panel; "With errors" now honest | skeleton, filter/search/no-batches states with the right button (Show every batch / Load pay data) | yes | kit + skeleton pulse (reduced-motion safe) | `/`, kit keys; no bulk |
| Ledgers | one panel, three ledgers, each remembering its own filters; steps follow | skeleton, empty with "Show them all", row action keeps place | yes | kit + skeleton | `/`, kit keys; row action |
| Records Desk | the Employees vocabulary on the bulk-edit desk; select all matching = the panel's count | gate refusal, empty grid "Clear the filters", hand-picked chip | yes | kit | grid keys unchanged; select all matching over the whole set |
| Statutory Data | 3,851 dependents paged and counted, no "newest 400" caveat | skeleton, empty with "Show the whole table" | yes; tables now translatable | kit + skeleton | `/`, kit keys |
| Integrations | deep links become visible, droppable chips that follow you across tables | skeleton, empty, "Connect a system" when there are none | yes | kit + skeleton | `/`, kit keys |

## 6. Commits (branch `worktree-agent-ac21d7c58ed161c48`)
- `4aec79808` feat(filter): Import batches on the shared filter panel (+ pb_learn 19.0.20.6.6, im-filters)
- `87b8ae864` feat(filter): Pay-run ledgers (Full & Final, Proration, Retro) on the shared filter panel (+ lessons at the source, regenerated content)
- `e9b42896e` feat(filter): Records Desk WHO on the shared filter panel
- `148c38737` feat(filter): Statutory Data view on the shared filter panel
- `823843233` feat(filter): Integrations connectors and Data on the shared filter panel
- `9b1495bee` fix(filter): Records Desk grid honours the Hand-picked arrival
- `145fede16` i18n(filter): Vietnamese for the wave 6 filter panels
- this report + ledger F31–F36 (docs commit)

Not committed: nothing of the product. Scratch files were kept in the session scratchpad (prefixed `w6_`). Not pushed, not merged. Preview released (`release w6`).

## 7. New gotchas
Appended to `FILTER_LEDGER.md` §4 as **F31–F36** (19.1 already holds F26–F30
from wave 1): ctx only on kit calls; shared msgids in the export; wrong-sense
cross-module translations; the tunnel dies in a pause / restored filters;
full-height layouts; generated Learn content.
