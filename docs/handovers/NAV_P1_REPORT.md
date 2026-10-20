# NAV P1 report — the rail standard everywhere (looks only)

Implementer: Opus, 2026-10-20. Spec: `docs/handovers/NAV_P1_RAIL_STANDARD.md`. Ledger: `docs/handovers/NAV_LEDGER.md`
(four new gotcha rows added). Deploy tier: **looks-only**. No `-u`, no restart, no manifest version change.

## 1. Diff summary

| File | + / − | What |
|---|---|---|
| `pb_hub/static/src/scss/hub_shell.scss` | 73 / 29 | Hover-widening rail replaced by the R1 rail (72 px, 60 px buttons, icon above 9 px/800 capital label, soft pill, focus ring, two-line clamp). Labels kept below 1099 px. New `< 768 px` horizontal strip. Lock styles untouched. |
| `pb_hub/static/src/xml/hub_shell.xml` | 8 / 7 | `is-calm` binding and `mouseleave` handler removed; 2026-10-02 comment replaced by the 2026-10-20 ruling; icon 17 → 18; `t-on-keydown` on the rail `nav`. Classes, `title`, `aria-current`, `is-on`, `is-locked` unchanged. |
| `pb_hub/static/src/js/hub_shell.js` | 12 / 6 | `railCalm` removed from state and from `setLens`; header comment corrected (72 px); `onRailKeydown` next to `setLens`. |
| `pb_hub/static/src/js/hub_nav.js` | 41 / 0 | New exported `railKeydown(ev, selector)`: ArrowUp/Down (and Left/Right for the phone strip) with wrap-around, Home/End; moves focus only. |
| `pb_mission/static/src/scss/pb_mission.scss` | 50 / 8 | Rail 76 → 72 px; focus ring; two-line clamp; below 1099 px the rail no longer shrinks or hides labels; `< 768 px` strip. |
| `pb_mission/static/src/xml/pb_mission.xml` | 3 / 2 | Icon 17 → 18; `t-on-keydown` on the rail `nav` (`data-coach="wf-tabs"` kept). |
| `pb_mission/static/src/js/pb_mission.js` | 4 / 1 | Imports `railKeydown`; `onRailKeydown` next to `setLens`. |
| `pb_hub/__manifest__.py` | 1 / 1 | Description: "76px lens rail" → "72px". |
| `pb_comp_ben/static/src/js/comp_ben_palette.js` | 3 / 3 | Stale comment: label box now "72px rail, 60px buttons, 64px label box, two lines". Comment only. |

No lens arrays, labels, icons, order, gates, localStorage keys, arrival routing, strings, fields, menus or
translations changed. No new user-visible string (and none containing "Odoo").

## 2. Test results

**Important limit.** The payobook.com browser walk with the QA login was **not done**: my safety rules do not allow me
to type a password into a production sign-in page (only localhost or a staging/test-named host qualifies), and the
browser had no existing session. Instead I verified with a **local harness** served from `127.0.0.1`: the real CSS
compiled by the server's own libsass from the deployed SCSS, the real rail markup, the real lens labels per hub (EN
and the VI msgstr from the modules' `.po` files), Inter font, and the real `pb_hub.HubShell` / `pb_mission.PbMission`
templates compiled and mounted in OWL 2.8.2 (the server's own `owl.js`). Every test that needs live data, sign-in or
the Access board is marked **not run live** below. An owner walk on payobook.com is still needed for those.

| # | Test | Result | Evidence |
|---|---|---|---|
| 1 | Home rail 72 px, 4 items, labels visible, pill | **Pass (harness)** | rail `getBoundingClientRect` w = 72; 4 buttons 60 × 52 px; labels shown without hover; `.is-on` = `#EDEAF8` / `#5A4BB0`. Live: not run. |
| 2 | People: 9 items fit at 1080 tall; "Where they work" two lines, not cut; tooltip | **Pass (harness)** | Window 1440 × 1080 (viewport 878 tall): last item bottom 573 px, rail does not scroll. "WHERE THEY / WORK" = 2 lines, nothing clipped. `title="Where they work"`. |
| 3 | Pay Run: 10 items; Adjust/Settle; Runs → Payslips; remembered lens | **Partial** | Harness: 10 items fit (last bottom 618 px EN, 650 px VI), click switches the pill and `aria-current`. Inner tabs, canvas switch with real data and the `localStorage` reload check: **not run live**. Lens-memory code untouched by this diff. |
| 4 | Lifecycle, Insights, Compliance, Learn; padlock | **Pass (harness) / padlock dialog not run live** | All four 72 px, no clipping in EN. Padlock span renders top-right of the 60 px button. The click sentence (dialog) is unchanged code; not exercised live. |
| 5 | Hover: width stays 72, no shadow, canvas still | **Pass (harness)** | Real mouse hover: rail w = 72, `box-shadow: none`, canvas x = 72 before and during hover. |
| 6 | Keyboard: Tab, ArrowDown, ring, Enter, `aria-current` | **Pass (harness + real template)** | Tab from the search button lands on the first rail button; ArrowDown ×2 → "Payslips", `:focus-visible` true, outline `2px solid rgb(90,75,176)`; Enter opens it, `aria-current` moves; ArrowUp ×3 wraps to "Awards". With the real `pb_hub.HubShell` template mounted in OWL: ArrowDown moved focus Run → Runs, click mounted the "runs" lens, `aria-current` moved, icon width 18. |
| 7 | Deep link with `pb_lens` lights the right item | **Not run live** | Arrival code untouched (`_arrival`, `_restoreLens`). |
| 8 | Workforce: 72 px, 10 items, labels, keyboard, no badge | **Pass (harness)** | 72 px, 10 items (Today … Holidays, Field, Approvals, Close), last bottom 618 px; same helper wired; no badge markup in the rail template. Live: not run. |
| 9 | 1024 × 768: labels visible both rails, brand text hidden, no overflow | **Pass (harness, exact iframe viewport)** | Both rails 72 px with labels (button height > 40 px), brand text `display:none`, rail scrollWidth 71 ≤ 72, no horizontal page scroll, canvas 952 px. |
| 10 | 390 × 844: strip under the header on a shared hub AND Workforce; sideways scroll; full-width canvas | **Pass (harness, exact iframe viewport)** | Rail top = header bottom (50 px), rail 390 × 84 px, scrolls sideways (scrollWidth 652), canvas 390 px, no horizontal page scroll; same for Workforce and People. |
| 11 | Vietnamese labels fit two lines | **Pass with one clip (harness)** | See §3. Not checked live with a vi_VN user. |
| 12 | Console: zero errors | **Pass (harness) / not run live** | Harness console: no errors. Server log since the deploy: 0 ERROR/CRITICAL lines; bundles regenerated on all four DBs without a compile error. |
| 13 | Access › Screens unchanged | **Not run live** | Static check only: the diff touches no lens registry, label, gate or sidebar file, and `pb_hub_lens_gates` is untouched, so the Screens lens has nothing new to read. No before/after screenshot. |
| 14 | Settings hub unchanged | **Pass (static)** | `pb_settings` not touched; no `.pbst-*` selector changed; the new rules are all scoped under `.pbim.pbhub` / `.pbim.pbms`. Not looked at live. |

Screenshots (harness, kept out of the repo):
- `/var/folders/tl/jk1lq25507v_yj3394mz25x00000gp/T/claude-chrome-screenshots-uw29cD/screenshot-1792497375931-0.png` (Pay Run, EN, ten items)
- `/var/folders/tl/jk1lq25507v_yj3394mz25x00000gp/T/claude-chrome-screenshots-uw29cD/screenshot-1792497375931-1.png` (Insights, VI)

## 3. Vietnamese clipping list for P2

Only one label goes past two lines at the 64 px label box:

| Hub | Lens | Vietnamese | Lines needed |
|---|---|---|---|
| Compliance | Young workers | Lao động chưa thành niên | 3 (shows "LAO ĐỘNG / CHƯA…") |

Two-line VI labels (they fit, but are the long ones to shorten in P2): Bảng vinh danh (Wall), Nơi họ làm việc
(Where they work), Chạy lương (Run), Các đợt lương (Runs), Phiếu lương (Payslips), Tuyển dụng (Hiring), Nhân viên mới
(New joiners), Kế hoạch phát triển (Growth plans), Khám phá dữ liệu (Explorer), Lực lượng lao động (Workforce), Báo
cáo lương (Payroll Report), Nhật ký kiểm toán (Audit), Hiện trường (Field). Where a label has more than one msgstr in
the `.po` files (Run, Records, Time, Audit, Explorer and others), the harness used one of them; the live user may see
the other.

## 4. Learn impact (R7) and Access (R8)

**No Learn impact.** Grep evidence (2026-10-20):
- `pbhub-rail`, `pbms-rail`, `rail__b` in `pb_learn`, `pb_coach`, `docs/tutorial_poc`: zero hits.
- "lens rail": one hit, `pb_learn/static/src/anchors.json:1503` `"desc": "Workforce's lens rail."` (an engineer-facing
  anchor description; the anchor is `data-coach="wf-tabs"`, which P1 keeps).
- "hover" in `learn_content.json`: two hits (lines 9177, 33248), both about hovering a tick/warning on a row, not the rail.
- No lesson, tour or coach text says the sub-menu opens on hover. `pb_learn` not touched or bumped.

**Access:** regression check by code only (see test 13). No live screenshot.

## 5. Deploy log

- Pre-check: server trees of `pb_hub`, `pb_mission`, `pb_comp_ben` were byte-identical to git HEAD before the deploy
  (no other session's work overwritten).
- Clean staging `/tmp/deployNAVP1`, rsync, per-module `sudo rsync -a --delete /tmp/deployNAVP1/<m>/ /odoo/odoo-server/addons/<m>/`.
- Hashes after deploy (sha1 of the sorted per-file sha1 list, skipping `__pycache__`, `*.pyc`, `.DS_Store`), local = server:
  - `pb_hub` 6719f1cec064dd2c909529e0885286bfaf87d002
  - `pb_mission` b9e2fe3480a3b10397e027313eb7339e8045d506
  - `pb_comp_ben` e2fe9704a00825192c3bd825fa04de43a8fea56c
- Per DB (`payobook`, `payobook_template`, `p0clone`, `rize`): `INSERT INTO orm_signaling_assets DEFAULT VALUES`,
  `DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'`, `web.assets.version` set to `17924972508081`. No restart.
- Served bundle check per DB (`/web/assets/_/web.assets_web.min.css` and `.min.js`, fetched on the server by host name):

| DB | 72 px hub rail | 60 px button | 72 px Workforce rail | old 224 px hover | `is-calm` | `railKeydown` in JS | `railCalm` in JS |
|---|---|---|---|---|---|---|---|
| payobook | 1 | 1 | 1 | 0 | 0 | 5 | 0 |
| payobook_template | 1 | 1 | 1 | 0 | 0 | 5 | 0 |
| p0clone | 1 | 1 | 1 | 0 | 0 | 5 | 0 |
| rize | 1 | 1 | 1 | 0 | 0 | 5 | 0 |

- `abm` not touched.

## 6. Self-score against R11

1. **Hero moment:** every hub now reads at a glance: short words down the left, the one you are on lit, no mouse needed. Delivered.
2. **Zero dead-ends:** nothing removed; padlock lenses still answer with their sentence; on phones the rail no longer disappears into icons but scrolls sideways.
3. **Plain language:** no words changed (P2's job); the full name stays in the tooltip.
4. **Motion with purpose:** only the 120 ms pill fade; the 160 ms width/shadow animation is gone.
5. **Keyboard:** Up/Down/Home/End walk both rails with a visible ring and wrap-around; Enter/Space open.

## 7. Deviations from the spec

1. **Label box 64 px, not `max-width: 58px` + `overflow-wrap: anywhere`.** The spec's CSS split words mid-way
   (EMPLOYEE/S, ANNOUNC/E) because the button's content box is 54 px, and "Where they work" needed three lines (fails
   test 2). Measured widths and fix are in the ledger. R1's numbers (72/60/18/9/.04em) are unchanged.
2. **`.pbhub-rail` keeps `position: relative`** (z-index 1 needs it) and the nav is `display:flex; min-height:0` so the
   inner column's `height:100%` resolves; same visual result as the spec.
3. **Keyboard helper in `hub_nav.js`** (shared with `pb_mission`), called from `onRailKeydown` next to `setLens` in both
   components. ArrowLeft/Right also handled for the phone strip.
4. **`pb_comp_ben` deployed** (comment-only change) so the server copy stays byte-identical to the repo.
5. **Browser walk not done on payobook.com** (see §2); harness verification instead. Tests 3 (partial), 7, 13 and the
   live halves of 1, 2, 4, 8, 11, 12 still need an owner walk with the QA login.
6. Design doc §12.3 says 20 px icon / 10 px label; I followed the handover and R1 (18 / 9).
