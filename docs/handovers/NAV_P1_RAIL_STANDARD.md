# NAV P1 — the rail standard everywhere (looks only)

Read first: `docs/handovers/NAV_LEDGER.md` (rules R1–R13, verified plumbing). Design of record:
`docs/design/payobook-navigation-review-20261019.html#second-review`, section 12.3 "The one submenu
standard" and the mock beside it. Owner decisions locked 2026-10-20: rail standard approved; this phase
is **looks only**. Implementer: Opus. Reviewer: Opus self-review against this file, then report back.

## 1. Goal in one sentence

Every hub on the shared shell (Home, People, Pay Run, Lifecycle, Insights, Compliance, Learn) gets the
Workforce-style rail: always visible, 72 px, icon above a short capital label, soft pill when selected, no
hover widening; Workforce's own rail is aligned to the same numbers; nothing moves between areas and no
label text changes.

## 2. Scope

In:
1. `pb_hub` shell rail: template + SCSS + the fold-back JS, to R1/R2/R5/R6.
2. `pb_mission` rail: align numbers to R1/R5 (it already has the shape).
3. Keyboard: Up/Down moves between rail buttons, Enter/Space opens (native button), focus ring visible.
4. Two-line label clamp with the full label in `title` (already there).
5. Narrow screens: labels stay at < 1099 px; horizontal strip at < 768 px, for both rails.
6. Stale comments corrected (`hub_shell.js:7`, `pb_hub/__manifest__.py` description, `comp_ben_palette.js:46`).
7. Learn check (R7) and Access regression check (R8).
8. Deploy, looks-only tier, all four databases; one browser walk on payobook.com.

**Binding non-goals** (they are P2/P3; do not touch):
- No lens moves, renames, additions or removals. No sidebar changes. No "Payroll" rename.
- No Settings hub conversion (its 14 categories regroup to 7 in P2; converting 14 to a 72 px rail now would scroll).
- No new strings, fields, models, menus or translations. No manifest `-u` needed; if you find you need one, stop and report.
- No pb_mission refactor onto the kit (later phase). Same numbers, two files, documented.
- No badges/counts on rail items.

## 3. The spec (what Opus builds)

### 3.1 Shared shell rail (`pb_hub`)

Template `pb_hub/static/src/xml/hub_shell.xml:85-108`:
- Keep `nav.pbhub-rail > div.pbhub-rail__in > button.pbhub-rail__b` so every selector and lesson anchor still resolves.
- Remove the `is-calm` class binding and the `t-on-mouseleave` handler; remove the 2026-10-02 comment and write the 2026-10-20 ruling in its place (one sentence, cite R1).
- Button content order: `span.pbhub-rail__ic` with `ic(l.icon, 18)`, then `span.pbhub-rail__l`, then the padlock span as today.
- Add `t-on-keydown` on the `nav` that handles ArrowUp/ArrowDown (wrap around) and Home/End; it moves focus only; Enter/Space on a native button already clicks. Implement in `hub_shell.js` next to `setLens`.
- Keep `t-att-title="l.label"`, `aria-current`, `is-on`, `is-locked`.

Styles `pb_hub/static/src/scss/hub_shell.scss:213-268` (replace the block; keep `.pbhub-rail__b.is-locked`, `.pbhub-rail__lock`, `.pbhub-lockpane` as they are):
```scss
.pbhub-rail { flex: 0 0 72px; z-index: 1; }
.pbhub-rail__in {
    width: 72px; height: 100%;
    display: flex; flex-direction: column; align-items: center; gap: 4px;
    padding: 14px 0;
    overflow-y: auto; overflow-x: hidden;
    background: var(--pbim-surface, #fff);
    border-right: 1px solid var(--pbim-line, #E2E8F0);
}
.pbhub-rail__b {
    width: 60px; flex: none; position: relative;
    display: flex; flex-direction: column; align-items: center; gap: 5px;
    padding: 9px 3px;
    border: 0; border-radius: var(--pbim-r-sm, 10px);
    background: transparent; color: var(--pbim-muted, #64748B);
    font: inherit; font-size: 9px; font-weight: 800; letter-spacing: .04em;
    line-height: 1.2; text-transform: uppercase; text-align: center;
    cursor: pointer; transition: background .12s, color .12s;
    svg { display: block; }
    &:hover { background: var(--pbim-line-2, #F1F5F9); color: var(--pbim-ink, #1B1733); }
    &.is-on { background: var(--pbim-soft, #EDEAF8); color: var(--pbim-primary, #5A4BB0); }
    &:focus-visible { outline: 2px solid var(--pbim-primary, #5A4BB0); outline-offset: 2px; }
}
.pbhub-rail__ic { display: inline-flex; }
.pbhub-rail__l {
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
    overflow: hidden; max-width: 58px; word-break: normal; overflow-wrap: anywhere;
}
```
Narrow screens: in the existing `@media (max-width: 1099px)` block (`:527`) do **not** hide labels. Add:
```scss
@media (max-width: 767px) {
    .pbhub-low { flex-direction: column; }          // verify the class at :202 is the rail+canvas row
    .pbhub-rail { flex: none; width: 100%; }
    .pbhub-rail__in { width: 100%; height: auto; flex-direction: row; justify-content: flex-start;
                      padding: 8px; overflow-x: auto; overflow-y: hidden;
                      border-right: 0; border-bottom: 1px solid var(--pbim-line, #E2E8F0); }
}
```
JS `pb_hub/static/src/js/hub_shell.js`: delete `railCalm` from state (`:127`) and from `setLens` (`:386`); fix the header comment (`:7`). Keep `ic(n, s = 17)`; the template passes 18.

Motion with purpose (R11): the selected pill may fade in over 120 ms (already `transition: background`); nothing else animates. The **hero moment** of this phase is that every hub now reads at a glance: ten words down the left, the one you are on lit, no mouse needed to see them.

### 3.2 Workforce rail (`pb_mission`)

`pb_mission/static/src/scss/pb_mission.scss:240-286`: `flex: 0 0 72px`; icon size 18 in `pb_mission.xml:83` (`ic(l.icon, 18)`); add the same `:focus-visible` and the two-line clamp on `.pbms-rail__l`. In the `@media (max-width: 1099px)` block (`:322-325`) stop hiding labels and stop shrinking the rail (keep the brand/search text rules). Add the same `< 768 px` horizontal strip for `.pbms-low` / `.pbms-rail`. Add ArrowUp/Down handling to the rail `nav` in `pb_mission.xml:72` the same way.

### 3.3 Nothing else changes

Lens arrays, labels, icons, order, gates, localStorage key, arrival routing: untouched.

## 4. Learn and Access (R7, R8)

- Grep `pb_learn/static/src/anchors.json`, `pb_learn/static/content/learn_content.json`, `pb_learn/static/src/engine/*.js`, `docs/tutorial_poc/author/data.js`, `pb_coach` for `pbhub-rail`, `pbms-rail`, "lens rail", "hover" near rail text. Known: zero class hits; one sentence "Workforce's lens rail". If any lesson, tour step or coach banner says the sub-menu opens on hover or shows names on hover, rewrite it (EN + VI) and bump `pb_learn` patch version; otherwise state "no Learn impact" with the grep output in the report.
- Open Settings › Access and delegation › Screens lens after deploy and confirm it still lists every hub's lenses with today's words (nothing should change in P1). Screenshot it for the report.

## 5. Test cases (run all; report pass/fail with evidence)

Local first (any dev DB or the clone), then payobook.com after deploy, signed in with the QA account (Fable supplies it in the agent prompt; never write it into the repo).

1. Home hub: rail is 72 px wide, four items (Pulse, Approvals, Wall, Announce) with labels visible without hovering; selected item has the soft pill. Measure with `getBoundingClientRect()` and screenshot.
2. People hub: nine items visible at 1080 px tall without scrolling; "Where they work" wraps to two lines and is not cut; `title` tooltip shows the full label.
3. Pay Run hub: ten items; Adjust and Settle inner tabs still render; clicking Runs then Payslips switches the canvas; the remembered lens survives a reload (`localStorage pbhub.pay.lens.v1`, check the actual key in `pay_hub.js`).
4. Lifecycle, Insights, Compliance, Learn hubs: same checks; Compliance "Bank" and "Young workers" feature-locked state (if locked on the DB) still shows the padlock and the sentence on click.
5. Hover anywhere on the rail: width stays 72 px (no widening, no shadow); the canvas does not shift.
6. Keyboard: Tab to the rail, ArrowDown moves focus and shows a visible ring, Enter opens the lens, `aria-current="page"` moves with it.
7. Deep link: open `/bizapp/action-pb_pay_hub` with `pb_lens` context (use an existing lesson deep link or the palette) and confirm the right rail item is lit.
8. Workforce hub: rail 72 px, ten items incl. Holidays and Field (if enabled), labels visible, keyboard works, Approvals badge-free.
9. 1024 × 768 viewport (resize window or emulate): labels still visible on both rails; brand text hidden; nothing overflows horizontally.
10. 390 × 844 viewport: rail becomes a horizontal strip under the header on a shared hub AND on Workforce; items scroll sideways; the canvas uses the full width; no horizontal page scroll.
11. Vietnamese: switch the QA user to vi_VN (or use the Learn live switch where it affects the hub) and confirm every rail label fits in two lines on all eight hubs; list any label that clips (expected candidates: "Nơi họ làm việc", "Kế hoạch phát triển", "Báo cáo lương"). Clipping is reported for P2, not fixed here.
12. Console: zero errors on each hub load and on each lens switch.
13. Access › Screens lens lists the same lenses as before (compare a screenshot to one taken before deploy).
14. Settings hub unchanged (still its list; explicitly confirm nothing regressed there since it shares `.pbim` tokens).

## 6. Deploy and verify (R12)

Tier: **looks-only** (SCSS, XML templates in the asset bundle, JS). Steps, per CLAUDE.md deploy contract:
1. Clean staging dir on the server, rsync `pb_hub` and `pb_mission` (and `pb_learn` only if touched) to it, then per-module scoped `sudo rsync -a --delete /tmp/deployX/<m>/ /odoo/odoo-server/addons/<m>/`. Never `--delete` into the addons root.
2. Hash each module tree on both sides (skip `__pycache__`, `*.pyc`, `.DS_Store`); must be identical.
3. Per DB (`payobook`, `payobook_template`, `p0clone`, `rize`): `INSERT INTO orm_signaling_assets DEFAULT VALUES;` then `DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%';` then bump `web.assets.version`. No `-u`, no restart. Keep manifest versions unchanged (unless `pb_learn` content changed, then bump its patch version and `-u pb_learn` in the normal tier, announced to other sessions first via the parent).
4. Confirm the served bundle on each DB contains the new rule (`curl` the bundle URL from a fresh page load and grep `pbhub-rail__b{width:60px` or the compiled equivalent).
5. Browser walk on payobook.com only (tests 1–13).
6. Commit `pb_hub`, `pb_mission` (and `pb_learn` if touched) and this handover's report with explicit paths; push `19.1`.

If any DB fails the served-bundle check, stop and report; do not retry blindly.

## 7. Report back (write `docs/handovers/NAV_P1_REPORT.md`)

- Diff summary per file with line counts.
- Test results 1–14 with the measured numbers and screenshot paths (keep screenshots out of the repo).
- The Vietnamese clipping list for P2.
- Learn impact statement with grep evidence; Access screenshot.
- Deploy log: hashes identical per module, per-DB purge done, served bundle check per DB.
- Self-score against R11 (hero moment, zero dead-ends, plain language, motion, keyboard) in five lines.
- Anything that deviated from this spec and why. New gotchas appended to `NAV_LEDGER.md`.
