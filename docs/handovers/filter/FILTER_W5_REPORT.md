# FILTER wave 5 — report (Payroll A: Salary Structures, Payslips, Pay Runs)

Branch `worktree-agent-a15dd561c7f420a85`, rebased on `19.1` @ `15049168f`
(kit 1.2.0, W1/W2/W4 merged). Builder: Opus. Tested on the shared preview
(`pbf_preview`, a copy of payobook) while the holder file named `w5`
(07:00–07:27 UTC). Nothing touched the live addons, the live databases or
`/opt/deploy-notes.md`.

**Summary: all three screens converted and passing T1–T22 (where they apply)
and W5-T1…T4 on the preview.** Testing found five small defects, all fixed and
re-tested (blank date preset, two doubled chip labels, rejected runs called
"Approved · to pay" in the list, a refused Submit toasting "Server Error").
Speed work was needed on Pay Runs: the card builder read every payslip of every
run; it is now one query each (4.6 s → 0.3 s for 48 cards, which the old
`get_board_data` — Learn's "Right now" — also gains).

| Screen | Result |
|---|---|
| Salary Structures (`pb_structures`) | PASS |
| Pay Run › Payslips (`pb_payslip_review`) | PASS |
| Pay Runs (`pb_payruns`, standalone and Payroll › Runs lens) | PASS |

Modules for the live deploy (sync + `-u` on all four DBs; each gains a
dependency on `pb_filter_kit`, so `-u` is required, not looks-only):

| Module | Manifest version |
|---|---|
| pb_structures | 19.0.1.2.0 |
| pb_payslip_review | 19.0.1.4.0 (also now declares `pb_import_kit`) |
| pb_payruns | 19.0.3.3.0 |
| pb_learn | 19.0.20.7.1 (rebased on W1's 20.7.0; other waves also edit `screens.js`/`anchors.json`/`learn_content.json` — expect a merge there) |

pb_filter_kit unchanged (1.2.0).

---

## 1. Per screen

### 1.1 Salary Structures — `pb.structures` → `hr.payroll.structure`, screen `structures`
- Base `[]` (structures stay shared across companies, by design).
- Sections: **Status** (choice: Active also counts a structure with no state, as the card does; Draft; Deprecated; Archived), **Payroll country**, **Pay schedule** pinned; Base structure, How pay is worked out (formulas / salary rules, only with `pb_hr_payroll_formula`), Contract type (many2many last hop), Currency, Country, Company, Built on, Employees covered (number), Last changed (date, explicit presets).
  On payobook (4 structures, all draft): only Payroll country and Last changed show; the rest appear with variety (verified with 64 test structures).
- Views: All structures · Active · Drafts · Deprecated · Changed this month.
- Sorts: Name A–Z (default) · Name Z–A · Recently changed first · Most employees first.
- Page 60 (`get_structure_page`); numbers line from `get_board_head` over the whole catalogue; Active / Draft / Deprecated tick the panel.
- States: skeleton, "No salary structures yet" (with New structure), "No structures match these filters" (with Show all), failure toast.
- Removed: own search box, date chips, country chips, schedule chips, the 240-row cap. `get_board` kept (R4).
- Learn: `sr-filters` now on the layout's `coach`; replica strip redrawn; anchor text updated.

### 1.2 Pay Run › Payslips — `pb.payslip.review` → `hr.payslip`, screen `payslips`
- The run picker stays above the panel as the scope control, riding on every call as `pbf_ctx.run_id`; base = that run + active companies; a run change reconfigures the panel (filters are remembered across runs — "Needs review in Sales" carries over).
- Sections: **Where it is** (verify/level1/level2 = "Waiting for approval"), **Review** (Needs review / Looks fine, `domain_method` over the run's one review-flags query), **Department** pinned; Job position, Pay structure, Payroll scheme, Company, Kind of payslip, Paid (payment stamp, with pb_pay_delivery), Period ends.
  On payobook: Where it is (all draft), Job, Structure, Scheme, Company, Kind, Paid hide themselves.
- Views: All in this run · Need review · Waiting for approval · Done · Refunds.
- Sorts: Name A–Z (default) · Name Z–A · Payslip number · Newest payslips first.
- Page 60 (`get_slip_page`), which also returns the step strip's counts against every other filter (R1) with "N need review"; a step press ticks it, the lit step lets go. The detail pane re-selects the first flagged payslip of the page when the open one leaves it (verified).
- Speed: the review flags (one SQL, ~2.5 s on the 1,000-payslip run) are kept per worker 120 s keyed by the run's payslips (count + last write) and threshold → counts 40 ms, page 160 ms after the first call.
- Removed: the client `filter`, "Showing … press a step" line. `get_review_data` kept (R4: tests, Learn manifest).
- Learn: new `ps-filters` (reserved) on the layout; `ps-chips` text now names the steps; replica strip added.

### 1.3 Pay Runs — `pb.payruns` → `hr.payslip.run`, screen `payruns`
- Base = the board's company rule as a domain (live payslips' company, else the scheme's). Verified on the copy: same 53 runs as the old rule, no extra, none missing.
- Sections: **Where it is**, **Pay period ends** (this/last month, this quarter, this/last year, pick dates), **Division** pinned (scheme names: "Information Technology", plus "No division"); Paid (Approved, not paid yet / Paid — from the payslips' payment stamp, so the handover's "needs the payment models" debt is closed), Whose turn (Waiting on me / on someone else), Sent back, Checks, Payroll scheme, Currency, Prepared by, Kind of run, People paid, Net pay (money), Company (only for readers in several companies).
- Views: All pay runs · Waiting on me · This month · Sent back · Approved, not paid · Rejected.
- Sorts: Latest period first (default) · Oldest period first · Name A–Z · Most people first · Biggest gross first · Biggest net pay first. List headers pick the matching sort.
- Lanes stay. Each lane = server page of its state (30) with its own "Show N more"; header count = the panel's "Where it is" count (R1 — supersedes W82; template comment says so); header flags counted over the whole filtered lane. A lane header ticks that step (others fold); pressing it again lets go; Escape lets go too. Only Rejected ticked → three slim rows. The Rejected drawer follows the filters, opens by itself on Rejected, and when the filters hide rejected runs says "1 rejected pay run is not shown by these filters · Show them too".
- Hero (un-narrowed, its own month list from `get_board_head`): phrases tick their filters (stage or paid + this month), lit = exactly those filters; second press goes home. Hero month = runs whose period ENDS this month (the filter's rule).
- List view = one server page (60) in the panel's sort.
- Bulk (R6): selection pruned to the runs on screen after every load; shift-select walks the shown lane/list rows; the bulk bar reads shown runs only.
- `useNavigationState` keeps only layout (board/list, open months, cursor, scroll); filters/search/sort are the kit's. "/" is the kit's.
- `get_board_data` kept for Learn's "Right now" and tests (R4), now sharing `_board_cards`.
- Removed: months switch, division chips, own search box, client `visible()` narrowing, "Showing … press a step" line, the 240/60 caps.
- Learn: `pk-divchips` moved to the layout's `coach` (key kept so its lesson lands); its lesson now describes the panel and says the lane counts follow the filters (EN+VI); replica toolbar replaced by the filter strip; anchor text updated. 21 `payruns` lessons otherwise unchanged (pk-steps / pk-kpis text still true).

## 2. Test matrix (preview, Chrome DevTools MCP 1440×900; T21 at 420×860)

Test data on the copy: 64 structures (`W5TEST Structure *`) and 4 runs (`W5TEST run 0–3`, one set to Rejected) — all deleted afterwards. No saved views left; `pbf:*` storage cleared; tab closed.

| Test | Structures | Payslips | Pay Runs |
|---|---|---|---|
| T1 open, counts, first tab, list | pass | pass | pass |
| T2 tick → chip, own count stays, others recount | pass | pass | pass |
| T3 OR within section | pass (32→48) | pass (112→201) | pass (12→19) |
| T4 AND across | pass | pass | pass |
| T5 Only | pass | pass | pass |
| T6 find + Enter + Escape | pass ("sing") | pass ("ware") | pass ("manuf") |
| T7 nothing matches | pass | pass | pass |
| T8 date preset + range | pass | kit ¹ | pass (Jun 2026 range → 12) |
| T9 number | pass (1,000 or more) | n.a. (no stored net, R2) | pass (₫15B or more) |
| T10 chip jump / × / clear all | pass | kit ¹ | kit ¹ |
| T11 search + Escape | pass | pass | pass |
| T12 sorts | pass (4) | pass (4) | pass (list headers + menu, 6) |
| T13 Show N more | pass (60→68) | pass (60→120 of 520) | pass (Done lane 30→35) |
| T14 save / rename / share / delete | pass | kit ¹ | kit ¹ |
| T15 built-in views | pass | pass | pass |
| T16 numbers line / hero | pass | pass (Need review) | pass (hero phrases, lane headers) |
| T17 hide + reload | pass | kit ¹ | pass (filters survive reload) |
| T18 link | pass | kit ¹ | kit ¹ |
| T19 bulk on the filtered set | n.a. | n.a. | pass (W5-T2) |
| T20 empty + show all | pass | pass | pass (nothing-matches banner) |
| T21 phone drawer | pass | kit ¹ | pass (one column, no sideways scroll) |
| T22 Vietnamese | pass | pass | pass |
| Console errors/warnings | clean | clean | clean |

¹ Same kit code path, exercised in full on Structures.

Wave tests:
- **W5-T1** Division Retail → lanes 18/0/35 → 3/0/9, header counts and the Done flag change; hero phrase "6 are still drafts" → chips "Where it is: Draft" + "Pay period ends: This month", Draft lane lit, the other two fold. PASS.
- **W5-T2** search "W5TEST" → tick the 3 test drafts → narrow to "W5TEST run 0" → bulk bar "1 pay run selected", sheet lists 1, Submit → exactly one `action_approval_submit` call (log), the server refused it (no payslips) and the toast now says why. Real demo runs untouched; nothing computed or approved. PASS.
- **W5-T3** run Logistics (520, Need review 502) → Corporate Office: panel reloads, 500 payslips, Need review 0, steps and numbers recount. PASS.
- **W5-T4** Contract type lists Vietnam Permanent Monthly 64 · Vietnam Contract Hourly 42 · CT 21 · Any contract type 4. PASS.
- Payroll hub lenses: Runs and Payslips render embedded (no title, panel inside the lens, keyboard ↓ / Enter / Escape / "/" work).

Speed on the copy (ms): layout / counts / page — Structures 95 / 38 / 39; Payslips (520-payslip run) 1,243 first, then 40 / 160; Pay Runs 1,325 / 523 / 593 (list 437).

Screenshots (Chrome DevTools MCP, local):
`/Users/adity/.claude/projects/-Users-adity-Documents-GitHub-gitlocal/9210e315-2d9d-4acd-ba15-28e97cb48de6/tool-results/`
`mcp-chrome-blob-1793430512914-43sl5f.jpg` (Structures, empty for a filter), `…1793430810060-djlaom.jpg` (Structures, phone drawer),
`…1793430824327-48ag7n.jpg` (Payslips), `…1793430939472-w00wb3.jpg` (Pay Runs board),
`…1793431091752-v74p7d.jpg` (Pay Runs, Rejected view), `…1793431303734-1n3gjc.jpg` (Pay Runs in the Payroll hub).

## 3. Deploy evidence (preview rehearsal only — the live deploy is the coordinator's)
- `pbf_preview.sh upgrade pb_filter_kit,pb_structures,pb_payslip_review,pb_payruns,pb_learn`: **EXIT=0, 0 new ERROR/CRITICAL lines** (twice: first build, final build with translations). The script's own `errors=11` counts lines appended at 02:49 UTC by the hold race, not this run.
- Server log during the pass: only `bus.websocket … concurrent update` / `mail_presence` lines (platform, several tabs); no `Filter section … hidden` / `Filter counts … failed`.
- PO gate (server `PoFileReader`) passed for the three `.po` files.
- Live: not touched. Cron counts / hashes / per-DB versions: n.a. for builders.

## 4. Kit gaps and design debts

Kit gaps (pb_filter_kit unchanged):
1. A date section with `presets: 'past'|'future'` always offers "none"; without a `none_label` it renders a blank radio (F34). Worked around with explicit preset lists. Ask: drop "none" when no `none_label` is given.
2. No way to page a kanban lane through the kit — each lane pages through the screen's own call (`lane=<key>`, `offset`). Works, but every board will re-write it.

Design debts:
- Pay Runs search is `ilike` on name and division label; the old board also matched the period text ("June") — use Pay period ends instead.
- Hero "this month" = runs whose period ENDS this month (the filter's rule); the month's stage still uses the hub's overlap rule, so a 25th-to-24th run that ends next month counts toward the stage but not the sentence.
- Net pay (Pay Runs) compares each run in its own currency; a mixed-currency board filters by the number only.
- Payslips: no Net pay number section (no stored net, R2); the review-flags SQL itself takes ~2.5 s on a 1,000-payslip run (pre-existing), now paid once per 2 minutes per worker.
- Done lane months are grouped from the loaded page; a month split by "Show more" shows its count for the loaded part.
- Pre-existing, not fixed: the flag dot on a payslip card overlaps the net figure at the 380 px list width; 49 older pb_payruns strings (run form, split wizard) have no Vietnamese.

## 5. Self-score (design bar)

| Screen | Hero moment | Zero dead-ends | Plain language | Motion | Keyboard / bulk |
|---|---|---|---|---|---|
| Structures | numbers line = views; contract types counted | skeleton, empty catalogue (New structure), empty filter, failure toast | yes | kit + skeleton shimmer (reduced-motion safe) | "/", kit keys; no bulk on this screen |
| Payslips | steps follow every filter with "N need review"; detail follows the list | skeleton, no payslips yet, empty filter, failure toast | yes | kit + skeleton | "/", kit keys |
| Pay Runs | lanes follow the panel, folded lanes still count, hero phrases are filters | lane-level empties, nothing-matches banner, hidden-rejected line, refusal says why | yes; R1 sentence in Learn | FLIP kept, ghost lanes | ↑↓←→ Enter Space S Esc ?, bulk on shown runs only |

## 6. Commits (branch `worktree-agent-a15dd561c7f420a85`)
- `dd90499b1` feat(filter): Salary Structures on the shared filter panel
- `59da8f638` feat(filter): Pay Run › Payslips on the shared filter panel
- `9eed8daad` feat(filter): Pay Runs on the shared filter panel + Learn (pb_learn 20.7.1)
- `286ef2713` fix(filter): translatable search placeholders (F29)
- `c15209d32` fix(filter): wave 5 test-pass fixes
- `a2ab7c097` / `dfc80c189` / `8de13d08a` i18n(filter): Vietnamese for Structures / Payslips / Pay Runs
- this report + ledger F31–F34 (docs commit)

Not committed: nothing of the product. Not pushed, not merged.

## 7. New gotchas
Appended to `FILTER_LEDGER.md` §4: **F31** (per-click row cost — profile the
row builder; cross-request TTL cache for slow Python facts), **F32** (`#. modules:`
plural lines and foreign references in a multi-module export), **F33**
(detach `restart`/`upgrade` with `setsid nohup … & disown`; never kill the
shared 8170 tunnel on the Mac), **F34** (blank "none" date preset). The hold
race this wave hit is W1's F26 (script fixed by the coordinator, `15049168f`).
