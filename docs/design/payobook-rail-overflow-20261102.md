# Submenu rail: overflow, clipping and the fold — design note

Date: 2026-11-02 (Sydney). Status: BUILT + LIVE ×4 DBs 2026-11-02 (owner: build directly, 80px/10px, no Joiners+Probation merge, location row kept; plus WHERE THEY WORK → LOCATION, ACCESS & DELEGATION → ACCESS).
Mock: `docs/design/rail-overflow-poc.html` (also published as a private artifact).
Standard it refines: NAV ledger R1/R2/R4/R5 (`docs/handovers/NAV_LEDGER.md`), owner ruling 2026-10-20 (memory `submenu-rail-standard`).

## 1. Symptom

Owner screenshot 2026-11-02: People hub, ~870 px tall Chrome window. The rail scrolls inside itself and the labels WHERE THEY WORK, ACCESS & DELEGATION, PROBATION, CONTRACTS, WORKFORCE are clipped at the sides.

## 2. Verified facts (payobook.com, Chrome viewport 1487×877, 2026-11-02 ~07:50 AEDT)

| Fact | Value | Where |
|---|---|---|
| Chrome above the rail | top navbar 46 + hub bar `.pbhub-top` 50 + `nav.pbhub-location` 45 = **141 px** | measured |
| Rail geometry | 72 px wide; `.pbhub-rail__in` padding 14/0, gap 4, `overflow-y:auto`; button 60 px, `padding 9px 3px`; label box 64 px, 9 px/800/.04em Inter, 2-line clamp | `pb_hub/static/src/scss/hub_shell.scss:218-296` |
| Item height | 52 px (1-line label), 63 px (2-line) | measured |
| People rail | **13** items, needs 771 px, had 736 → scrolls 35 px | measured |
| Payroll rail | **14** items (Run · Runs · Payslips · Results · Inputs · Pay out · Adjust · Settle · Budget · Calendar · Awards · Access & delegation · Reports · Insights), needs 816 px | measured |
| Hiring rail | 10 items, needs exactly 736 px | measured |
| **Root cause of the clipping** | When the rail overflows, a classic (non-overlay) scrollbar takes **16 px**: `offsetWidth − clientWidth = 16`, so `clientWidth = 56` and the 60 px button + 64 px label box are cut by `overflow-x:hidden`. Overlay scrollbars (trackpad-only Mac) steal nothing, so the bug is invisible on some machines and present on every Windows PC and every Mac with a mouse. | measured |
| Label widths at 9px/800/.04em | WORKFORCE 62 · CONTRACTS 61 · DELEGATION 61 · EMPLOYEES 58 · PROBATION 57 · WHERE THEY 64 (box 64) · VI: LỰC LƯỢNG 56, NGƯỜI MỚI 53, HỢP ĐỒNG 52, NGHỈ VIỆC 50 | canvas measure |
| At 10px/700/.02em | WORKFORCE 67 · DELEGATION 66 · CONTRACTS 65 · EMPLOYEES 62 · WHERE THEY 68 · VI max LỰC LƯỢNG 60 | canvas measure |
| Who puts what on People | employees (hub) · records (pb_records) · pay 45 (pb_pay) · where 48 (pb_workseg) · access (biz_access `access_studio.js:437-446`, registered on People, Hiring AND Payroll, groups `base.group_user`) · assets 50 · joiners 52 · probation 54 · exits 56 · contracts 58 · **workforce 85 (pb_insights_hub `registerModuleInsight("workforce")`, a report)** · insights (hub) · plan (hub) | code |
| Who puts what on Payroll beyond the hub's 9 | paycal (Calendar), awards, **budget (pb_budget via registerModuleInsight)**, **reports (pb_insights_hub registerModuleInsight("payroll"))**, access (biz_access) | code |
| Workforce rail | own copy of the same numbers, `pb_mission.scss:240-286`; "change both or neither" | ledger |
| Fold-to-More precedent in the kit | none; the shell has no overflow handling beyond `overflow-y:auto` (R2 "scrolls inside itself") | `hub_shell.js:314-321`, `hub_shell.xml:88-115` |

Height budget in the wild (rail = viewport − 141): Windows 1366×768 laptop ≈ 516 px (9 one-line items); MacBook Air 13" ≈ 704 px; owner's window 736 px; Full HD ≈ 828 px.

## 3. Proposal — three layers (all three recommended)

### Layer 1 — content: fewer, shorter items
- **Every report item becomes a tab inside INSIGHTS.** People: `workforce` (Workforce insights) → tab of Insights. Payroll: `report` (Payroll report) and `budget` → tabs of Insights. Mechanism: `registerModuleInsight` stops registering a rail lens and instead registers a tab the module-insights lens (`PbModuleInsights`) draws; old deep links (`lens: "workforce"`) land on Insights with that tab selected (R10).
- **Access & delegation → short word ACCESS** (VI "Truy cập"), full name in `title` and the location row, **pinned at the bottom of the rail under a hairline** (a `pinned: true` flag on the lens def → `margin-top:auto` + divider). Hiring's SET-UP joins the pinned zone. Pinned items are the first to fold (Layer 2).
- **People order**: EMPLOYEES · CONTRACTS · PAY · RECORDS · JOINERS · PROBATION · EXITS · WHERE THEY WORK · ASSETS · INSIGHTS · PLAN ‖ ACCESS. Contracts moves next to Employees (one-door law; today it sits 10th because of its sequence 58). Counts: People 13 → 11+1, Payroll 14 → 11+1, Hiring 10 → 8+2. Other areas (4–8 items) unchanged.
- Optional owner merges (§6): JOINERS+PROBATION as one item with two tabs (People → 10+1); RECORDS reached only from Employees › Select (it already opens from the roster's Bulk update).

### Layer 2 — mechanics: a fold instead of a scrollbar (shared kit + Workforce rail)
- `.pbhub-rail__in` gets `overflow:hidden`; a `ResizeObserver` on the rail measures item heights and folds from the end (pinned first, then the tail of the main list) into a **MORE** button (Lucide `ellipsis`, label "More"/VI "Thêm", small count of folded items) when the sum exceeds the available height.
- The **selected lens is never folded**: if it would be, it swaps with the last visible main item.
- MORE opens a popover to the right of the rail: icon + full name per folded lens, queue counts where R3 allows, keyboard reachable (ArrowDown from the last visible item enters the popover; Esc closes; Enter opens). Same `setLens()`; the popover closes on choice.
- Phone strip (< 768 px) unchanged: horizontal scroll, no fold.
- Belt-and-braces: even if folding were disabled, the scroller never shows a width-stealing bar (`scrollbar-width:none` + `::-webkit-scrollbar{display:none}`, wheel/keyboard still scroll, fade edge as the affordance).

### Layer 3 — width: 72 → 80 px
- Rail 80, button 68 (`padding 7px 3px`), label box 72, label **10 px / 700 / .02em**, icon **20 px** (the §12.3 numbers the design doc asked for; P1 shipped 18/9 for lack of width). Item height stays 52 px (7+20+5+12+7 = 51, rounded by line box).
- Every current word fits with ≥ 5 px spare in EN and VI. Canvas loses 8 px (0.5 % at 1487 px).
- Same numbers in `pb_mission.scss` (Workforce rail) — or fold Workforce onto the kit in the same phase (ledger says both carry the numbers until folded).

### Optional — reclaim the location row
`nav.pbhub-location` (45 px, "People › Employees") repeats the brand in the hub bar and the selected rail item. Folding it into the hub bar (brand › lens, back chip stays) frees 45 px on every screen = one more visible item. Owner call; it changes the top of every hub.

## 4. Learn / Access follow-ups (ledger R7, R8)
Any label or placement change updates lessons, tours, coach anchors and practice replicas (EN + VI) and bumps `pb_learn`; the Access screens lens must show the new rail. "Access & delegation" is named in Learn's Settings tabs (ledger row 2026-10-21 P2 Learn) — grep "Access & delegation", "Workforce insights", "Payroll report", "Budget" in `learn_content.json` and the manifests before the build.

## 5. Test cases (for the handover)
1. People at 877 px: no scrollbar, no clipping, 11 items + Access visible or folded per height; selected never hidden.
2. Payroll at 657 px (Windows laptop): MORE appears, popover lists the folded lenses with full names; choosing one selects it and it swaps into view.
3. Keyboard: ArrowDown from the last visible item opens/enters MORE; Esc returns.
4. Deep link `lens=workforce` on People lands on Insights › Workforce tab; `lens=report` / `lens=budget` on Payroll likewise.
5. VI labels at 80 px: no word clipped (measure LỰC LƯỢNG, NGƯỜI MỚI, TRUY CẬP, NƠI HỌ / LÀM VIỆC).
6. Phone (< 768 px): horizontal strip unchanged.
7. Workforce rail: same width/label numbers.
8. Access lens on People/Hiring/Payroll: label ACCESS, title "Access & delegation(s)", pinned under the hairline.
9. Learn lessons that mention the renamed/moved items are updated (grep evidence).
10. `pb_hub` version bump + asset purge per DB (looks-only deploy ritual).

## 6. Decisions for the owner
1. Phased workflow (Fable handover → Opus builds) or build directly?
2. Width/text: 80 px + 10 px labels (recommended) vs keep 72 px / 9 px and do only the fold.
3. Merge Joiners + Probation into one item? (optional)
4. Fold the "People › Employees" row into the dark bar? (optional, +45 px everywhere)
