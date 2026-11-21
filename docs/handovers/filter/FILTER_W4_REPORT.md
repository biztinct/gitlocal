# FILTER wave 4 — report (HR services)

Branch `worktree-agent-ab72418d1572b5747` (based on `19.1` @ `7fd77c7ad`, kit 1.1.0).
Builder: Opus. Tested on the shared preview (`pbf_preview`, a copy of payobook) —
nothing touched the live addons, the live databases or `/opt/deploy-notes.md`.

**Summary: all five screens converted and passing T1–T22 and W4-T1…T4 on the preview.**
One fix found by testing (Ask HR empty state) and one pre-existing translation
defect found and fixed (pb_approval_config's stale `.pot`, see F15).

| Screen | Result |
|---|---|
| Vendors (`pb_vendor_access`) | PASS |
| Praise (`pb_rnr`) | PASS |
| Assets register (`pb_assets`) | PASS (incl. W4-T2 bulk on the whole matching set) |
| Home › Ask HR (`pb_ask_hr`) | PASS after one fix (empty state → "Start again") |
| Approvals inbox (`pb_approval_config`) | PASS (scopes, doors, 42-lesson tab words kept) |

Modules for the live deploy (sync + `-u`, all four DBs; every one gains a
dependency on `pb_filter_kit`, so `-u` is required, not looks-only):

| Module | Manifest version |
|---|---|
| pb_vendor_access | 19.0.1.16.0 |
| pb_rnr | 19.0.1.4.0 |
| pb_assets | 19.0.1.2.0 |
| pb_ask_hr | 19.0.1.3.0 |
| pb_approval_config | 19.0.1.7.0 |
| pb_learn | 19.0.20.6.4 (other waves also bump pb_learn and edit `screens.js`/`anchors.json` — expect a merge on those three files) |

---

## 1. Per screen

### 1.1 Vendors — `pb.vendors` → `pb.vendor`, screen `vendors`
- Base: active + the reader's companies (record rules do the rest; nothing sudoed in a count).
- Sections: **What they do**, **Agreement** (none = "No agreement yet"), **Who looks after them** pinned; Looked after by me (choice), Team they work with, Country, Next agreement ends (future presets), Company.
  Hidden on payobook (one value or none): Looked after by me, Team, Country, Company.
- Views: All vendors · Coming up for renewal · Already run out · Nothing recorded · I look after.
- Sorts: Name A–Z (default) · Name Z–A · Agreement ending soonest · Newest on the register.
- Page size 60 (`get_vendor_page`); headline sentence said about the same filtered list.
- Search: kit `ilike` OR the board's folded Python match (no `unaccent` on this Postgres) — "bui" finds "Bùi …"; memoised per request.
- Spreadsheet follows the filters (every page) when any are on; the whole register otherwise.
- Removed: type/agreement chip rows, own search box, 800-row cap and its "first part of the register" note. `get_board` kept for the spreadsheet (R4).
- Learn: nothing in Learn describes this screen (`grep -c "vendor\|pbva" pb_learn/static/src/anchors.json pb_learn/static/src/engine/screens.js` → 0, 0).

### 1.2 Praise — `pb.rnr` → `pb.rnr.nomination`, screen `praise`
- Base: the reader's companies; nomination search never sudoed; refusal for readers without recognition rights is the panel's refusal too (`pbf_layout` → `refused`).
- Sections: **Where it is** (Being written / With their manager / With HR / Decided / Not this time), **Value**, **Who it is about** pinned; What was decided, Who wrote it, Their department, Quarter, Written, Decided, Quarter winner, Who can see it, Award (money). None hidden on payobook.
  People/value/quarter names are counted as the reader and labelled as the system (the rows already read them that way, R56).
- Views: All praise · Waiting on a manager · Waiting on HR · Not this time · Given money this quarter (outcome awarded + decided since 1st of the quarter, a date range) · Quarter winners.
- Sorts: Newest first (default) · Oldest first · Most recently decided · Biggest award first.
- Step strip kept: counts follow every other filter (server, from the page call); a press ticks that step in "Where it is" and keeps the other filters; pressing the lit step lets go. Numbers line presses = the views' filters.
- Page size 60. Removed: value chip row, own search, "Showing … press a step" line, 300 cap note.
- Learn: only the recognition Wall has Learn content (`rep-pm-wall`); the Praise list has none.

### 1.3 Assets register — `pb.assets` → `pb.asset`, screen `assets`
- Base: the reader's companies; no sudo. Requests segment unchanged.
- Sections: **Status** (generic labels; a digital row keeps "Active/Available" on the row), **Physical or account**, **Category** pinned; Country, Who has it, Their department, Warranty ends (future), Bought on, Arrived on, Cost (money), Passed on, Company.
  Hidden on payobook's 2 real items: kind, category, country, warranty, bought, arrived, cost, reused, company (they show once the register has variety — verified with test items).
- Views: All items · Spare physical · Out with people · Under repair · Warranty ending in 60 days (today → +60 days, the badge's own rule) · Switched-off accounts.
- Sorts: Newest code first (default) · Oldest code first · Name A–Z · Warranty ending soonest · Most expensive first.
- Bulk (R6): header tick = the page; then **"Select everything matching (N)"** → one server call (`matching_ids`, cap 2,000, says so when capped); allowed statuses from each picked item's kind; a filter change drops a stale selection. Export follows the filters.
- Every figure on the numbers line except "Leavers still holding" (Python, kept as a figure) now filters.
- Learn: no Learn entries (`grep -c "pb_assets\|\"ast-" pb_learn/static/src/anchors.json` → 0).

### 1.4 Home › Ask HR — `pb.ask.hr` → `pb.ask.hr.ticket`, screen `askhr`
- No base domain: record rules split HR (every question) from everybody else (own questions); nothing sudoed. Asker names come through `hr.employee.public`.
- Sections: **Where it is**, **Category**, **Who in HR has it** (none = "Nobody has it yet") pinned; HR only: Mine, Waiting ("New, over 2 working days" via `domain_method`, one read of new questions, 98 ms); Who asked, Their department, Asked, Answered, Closed, Closed by, Company.
- Views HR: Open questions · Nobody has it yet · Mine · Answered this week · New, waiting · Closed (paged: the 60-closed cap is gone). Employee: Open questions · Answered, your turn · Closed · Everything you asked.
- Sorts: Newest first · Waiting longest first · Latest activity first · Recently closed first.
- Step strip: counts follow the other filters; a press = that step only (other filters kept); the lit step again = all open steps. Bulk Take / Hand / Close act on the cards shown; "Select all shown" in the panel toolbar.
- Removed: Mine / Nobody / category chip row, own search, per-user localStorage memory (`pbhub.askhr.filters.v1`), the "only the most recent closed" note.
- Fix after testing: the empty state's button is now **"Start again"** → first view (was: clear everything, which lit no matching tab for HR).
- Learn: `coach="'ah-filters'"`, declared in `anchors.json`; replica strip in `screens.js askhr()` now draws the panel (Open questions · Nobody has it yet · Mine · Filters · search). `ah-glance/ah-steps/ah-card/ah-take` unchanged. Lesson text (`tabs.askhr.line`) still true.

### 1.5 Approvals inbox — `pb.approval.inbox` → `biz.approval.request`, screen `approvals`
- Mine / My team / Everyone stays above the panel and rides on every call as `pbf_ctx.scope`; `_pbf_records()` and the base domain are exactly `_scoped(scope)` (reader's rights for Mine; the gated sudo read with company/team boundary for the wider two) + `state in` the listed piles. Org scope falls back to Mine for a reader who may not see it. A scope change reconfigures the panel and keeps the same view.
- **The four tabs are the first four views, same words**: My turn · All I can see · Sent back · Finished; then My turn today · Late · Sent back to me · Finished this month · Pay area waiting.
- Sections: **Where it is** (waiting / sent back / finished), **Part of the business**, **When it is due** (Late / Due today / Due later / No due date — presets cannot say "now") pinned; My turn (`domain_method`: one search + `_is_mine`, memoised per request), What kind of request, Sent in by, Sent in, Finished on, Amount (filtered, never added; no currency prefix), Currency, Company.
- Sorts: Newest sent in first · Oldest sent in first · Due soonest · Biggest amount first.
- Paging: 60 per page by **offset**, not the id cursor (`id < cursor` is wrong under `submitted_at` order and under the sort menu). Money line = per-currency sums of the shown "mine" cards.
- Doors: `request:<id>[:scope]` and now also `params: { request_id }` (Records Desk, Statutory, tenant console — previously ignored) locate pile + scope first, then open on that tab's view with the drawer; `area:<x>` opens My turn in that area. The FilterKit is built by hand (`new FilterKit`) so the door resolves before the first panel load.
- Learn: 42 lessons keep the tab words. `ai-tabs` is set on the panel's view row by `inbox.js` (MutationObserver; kit gap 1); `coach="'pbam-filters'"` on the bar, declared in `anchors.json`; `ai-tabs` description updated; replica gains the filter strip. No lesson describes the old area/due chips (searched `learn_content.json` for due today / chip / filter + inbox/approval/my turn: one unrelated hit about a pay-run chip).
- Embedded as Home › Inbox: verified (no hero, panel inside the lens).

---

## 2. Test matrix (preview, Chrome DevTools MCP at 1440×900; T21 at 420×860)

Test data: 68 vendors, 86 assets, 62 nominations, 64 tickets and one employee
login were created on the preview copy for paging/bulk/role tests and deleted
afterwards (vendors by SQL — no unlink right). One real asset that matched the
W4-T2 filter was set back to Spare. No saved views left; `pbf:*` storage cleared.

| Test | Vendors | Praise | Assets | Ask HR | Approvals |
|---|---|---|---|---|---|
| T1 open, counts, first tab, list | pass | pass | pass | pass | pass |
| T2 tick → chip, own counts stay, others recount | pass | pass | pass | pass | pass |
| T3 OR within section | pass | pass | pass | pass | pass |
| T4 AND across | pass | pass | pass | pass | pass |
| T5 Only | pass | pass | pass | pass | pass |
| T6 find + Enter + Escape | pass | pass | pass ¹ | pass | pass |
| T7 nothing matches | pass | pass | pass | pass | pass |
| T8 date preset + range | pass | pass | pass | pass | pass |
| T9 number | n.a. | pass (₫1 or more) | pass (₫5M or more) | n.a. | pass |
| T10 chip jump / × / clear all | pass | pass | pass | pass | pass |
| T11 search + Escape | pass | pass | pass | pass | pass |
| T12 sorts | pass | pass | pass | pass | pass |
| T13 Show N more | pass (60→71) | pass (60→72) | pass (60→68) | pass (60→64) | pass (60→65) |
| T14 save / rename / share / delete | pass | kit ² | kit ² | kit ² | kit ² |
| T15 built-in views | pass | pass | pass | pass | pass |
| T16 numbers line | pass | pass | pass | pass | n.a. (no numbers line) |
| T17 hide + reload | pass | kit ² | kit ² | kit ² | pass |
| T18 copy link → new tab | pass | kit ² | kit ² | kit ² | pass |
| T19 bulk / export on the filtered set | pass (23 vs 75 rows) | n.a. | pass (65 vs 88; W4-T2) | pass (Take on 11 Pay questions → exactly 11) | n.a. |
| T20 empty + show all | pass | pass | pass | pass (after fix) | pass |
| T21 phone drawer | pass | kit ² | kit ² | kit ² | pass |
| T22 Vietnamese | pass | pass | pass | pass | pass (after .pot refresh) |
| Console (errors/warnings) | clean | clean | clean | clean ³ | clean |

¹ Enter after typing "physic" ticked nothing: the term matched a section NAME ("Physical or account") and the kit's `pickFirstFound` skips those by design; "laptop" + Enter ticked Category Laptop.
² Same kit code path, exercised in full on Vendors (and T17/T18/T21 again on Approvals, whose kit is hand-built).
³ As the employee login, Home logs `pb_home_hub: could not read the period state` (warn) — pre-existing, not this screen.

Wave tests:
- **W4-T1** Vendors "bui" → "Bùi W4TEST Thịnh Phát 07" (1 of 71); "thinh phat" also finds it. PASS.
- **W4-T2** Assets: Spare physical (65 > one page) → header tick (60) → "Select everything matching (65)" → Change status → Under repair: exactly 65 changed (`repair` 0→65, `spare` 87→22 = the 22 digital items untouched). PASS.
- **W4-T3** Ask HR as a plain employee (preview login, deleted after): total 4 = their own questions, views/counts only theirs, one asker; Vendors/Assets/Praise answer with their refusal sentence. PASS.
- **W4-T4** Approvals: Mine 75 → My team 1 → Everyone 75, view kept on switch; the Records Desk door (`params.request_id` = a sent-back request) lands on Sent back with the drawer open; `request:219:org` lands on Everyone › Sent back. PASS.

Speed on payobook copy (ms): layout / counts / page — Vendors 108/127/49, Praise 142/150/400, Assets 62/140/150, Ask HR 90/111/104, Approvals 97/152/769 (60 cards; the card builder reads steps and seats per request — same per-card cost as before, which loaded 120).

Screenshots (Chrome DevTools MCP, local files):
`/Users/adity/.claude/projects/-Users-adity-Documents-GitHub-gitlocal/9210e315-2d9d-4acd-ba15-28e97cb48de6/tool-results/`
`mcp-chrome-blob-1793410901337-emfun4.jpg` (Vendors), `…1793411044563-sn75t0.jpg` (Vendors save view),
`…1793411292060-swza0w.jpg` (Vendors phone drawer), `…1793411304040-2kcdau.jpg` (Praise),
`…1793411437861-hj3gy8.jpg` (Assets), `…1793411557402-ix126s.jpg` (Ask HR),
`…1793411680746-z2146z.jpg` (Approvals), `…1793411773440-3pcbhn.jpg` (Approvals door + drawer),
`…1793411796221-9dpn25.jpg` (Approvals as Home › Inbox).

## 3. Deploy evidence (preview rehearsal only — the live deploy is the coordinator's)
- `pbf_preview.sh upgrade pb_vendor_access,pb_rnr,pb_assets,pb_ask_hr,pb_approval_config,pb_learn`: **EXIT=0 errors=0**, twice (build, then with translations).
- `grep -E " (ERROR|CRITICAL) " /tmp/pbf_preview/server.log` → none; no `Filter section … hidden` / `Filter counts … failed` lines.
- PO gate (ledger §5, server's `PoFileReader`) passed for all five modules.
- Live: not touched. Cron counts / hashes / per-DB versions: n.a. for builders.

## 4. Kit gaps and design debts

Kit gaps (pb_filter_kit unchanged):
1. **No coach anchor for the view row.** Approvals needs `data-coach="ai-tabs"` on the tabs (42 lessons) — set by DOM + MutationObserver in `inbox.js`. Ask: a `viewsCoach` prop on `PbFilterLayout`.
2. **`useFilterKit` loads on willStart, before a door can be resolved.** Approvals builds `new FilterKit(...)` by hand to locate the request's pile/scope first. Ask: a `defer: true` option (screen calls `kit.load()`).
3. **Labels are read with the reader's rights.** People sections over `hr.employee` for non-HR readers needed `_pbf_list_values`/`_pbf_label_values` overrides (Praise, Assets: labels as the system; Ask HR: via `hr.employee.public`). Ask: a section key `label_sudo` or `label_model`.
4. **Date presets** lack "this quarter", "next 60 days", "today", "overdue (before now)": used a computed range (Given money this quarter, Warranty 60 days, Answered this week) and a choice section (When it is due).
5. **A ticked value with 0 matches is appended after the list**, out of selection order (Ask HR "Where it is": New, Closed, Answered, With HR).
6. **`toggleFilters({})` with no "everything" view** leaves the previous tab lit with a dirty dot (Ask HR, Approvals). Screens use `useView(views[0])` for "start again". Ask: `kit.home()`.
7. **`pickFirstFound` skips sections whose name matches the term** — Enter does nothing for "physic" on Assets.
8. **Strip counts**: the kit counts only open sections, so step strips get their counts from the screen's page call (`skip='step'`), not from `kit.counts`.

Design debts:
- Assets Cost and Approvals Amount mix currencies; Assets shows the company's symbol in the range hint, Approvals none. A per-currency number filter would be honest.
- Approvals 60-card page takes ~0.8 s (card builder), unchanged per card.
- "Part of the business" (Approvals) reuses an existing translation "Bộ phận" (department); "Mảng công việc" would be truer — left as the existing entry.
- Pre-existing, not fixed: duplicate msgid "The whole company" in pb_approval_config's PO; untranslated older strings in these modules (e.g. Vendors "Nothing recorded yet"); `pe-filters` fails the Learn anchor test (F17).
- Self-score is below.

## 5. Self-score (design bar)

| Screen | Hero moment | Zero dead-ends | Plain language | Motion | Keyboard / bulk |
|---|---|---|---|---|---|
| Vendors | numbers line = views, folded search kept | skeleton, filter/search/empty-register states, refusal | yes | kit + card stagger (reduced-motion safe) | `/`, kit keys; no bulk on this screen |
| Praise | step strip follows the panel | all states; refusal | yes | kit + skeleton pulse | `/`, kit keys |
| Assets | "Select everything matching (N)" across pages, kind-aware bulk | all states, capped selection says so | yes | kit + skeleton | header tick, matching set, bulk bar |
| Ask HR | step strip + "New, over 2 working days" as a real filter | all states incl. employee "never asked"; Start again | yes | list slide-in kept | T/H/Space/Enter kept, bulk over shown |
| Approvals | scope + doors land on the right pile with the panel set | all states; per-tab empty copy kept | yes; tab words unchanged | kit | `/`, Escape closes drawer |

## 6. Commits (branch `worktree-agent-ab72418d1572b5747`)
- `bdb85ff44` feat(filter): Vendors on the shared filter panel
- `92052a2ed` feat(filter): Praise on the shared filter panel
- `770ee5d02` feat(filter): Assets register on the shared filter panel
- `398825622` feat(filter): Home › Ask HR on the shared filter panel
- `647ab1188` feat(filter): Approvals inbox on the shared filter panel (+ pb_learn: anchors, replica, version)
- `87ea34f48` i18n(filter): Vietnamese for the Vendors filter panel
- `1f6bf87d4` i18n(filter): Vietnamese for the Praise filter panel
- `1b4790af4` i18n(filter): Vietnamese for the Assets filter panel
- `1e962977c` fix(filter): Ask HR empty state starts again on the open questions; Vietnamese
- `5fdf47c5d` i18n(filter): Vietnamese for the Approvals filter panel; refresh the stale POT
- this report + ledger F13–F20 (docs commit)

Not committed: nothing of the product. Scratch test harness files (`.w4_*`) deleted. Not pushed, not merged.

## 7. New gotchas
Appended to `FILTER_LEDGER.md` §4 as **F13–F20** (preview dies with the ssh
session; i18n export argument order; stale .pot drops translations; Python code
terms need a code reference; Learn anchor test needs a literal; Claude-in-Chrome
stuck narrow → DevTools MCP; shared scratchpad; memoise Python facts per request).
