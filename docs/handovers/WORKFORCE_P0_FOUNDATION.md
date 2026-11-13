# WORKFORCE P0 — Foundation: one system of record for pixels

Program: Workforce redesign (Option B staged through A, powered by C's engine).
Read first: `docs/WORKFORCE_REDESIGN_CONVENTIONS.md` (W-rules; W0.1 = you self-review, Fable will not).
Visual reference: `docs/WORKFORCE_REDESIGN_OPTIONS.html` — Part 1 (audit) is your before-state; the
P0 row of the roadmap is this phase.

## §1 Scope

P0 makes every *surviving* Workforce surface wear one design system and ships the shared kit that
P1/P3 build on. Ten work packages, all small; **pixels + explicitly listed data records only (W11)**.

**Binding non-goals — do NOT do these in P0:**
- No IA changes: all 14 sidebar items keep their labels/targets (resequencing + one gate fix only).
- No rebuild/retirement of the legacy screens (Workforce Dashboard, Live Attendance, Timecards,
  Shift Roster, Shift Templates, Overtime Rules, Payroll Report die in P1, not now). Do not fix their
  duplicated `goHome/goFlowDashboard` breadcrumb links — wasted work, they're deleted in P1.
- No model, facade, ACL (beyond WP-H), workflow, or `hr.attendance`-adjacent behavior changes.
- No Mission Control shell, no lenses, no engine work, no dark mode.
- No re-tint of the 5 legacy screens' own CSS (only their shared breadcrumb strip, WP-F).

## §2 Verified plumbing facts (audited 2026-08-17 — do not re-derive)

- Token source of truth: `pb_import_kit/static/src/scss/import_tokens.scss` — primary `#5A4BB0`
  (hover `#4A3D96`, light `#CBC2EE`, dark `#241F52`), ink `#1B1733`, soft `#EDEAF8`, line `#E2E8F0`,
  bg `#F5F6FA`, muted `#64748B`, green `#2E7D4F`/`#E3F2E9`, rose `#DC2668`/`#FCE7EF`, amber
  `#D97706`/`#FEF3C7`, cyan `#2563EB`/`#E5EDFD`, radii 14/10/18, shadow `0 8px 24px rgba(16,12,40,.07)`.
- Lucide helper: `ic(name, size)` + `IC` map in `pb_import_kit/static/src/js/import_icons.js`
  (exports at :6 and :62).
- Off-token accents to purge:
  - `pb_timeoff/static/src/scss/pb_timeoff.scss` ~:15-19 — `--p:#059669; --ph:#047857; --soft:#D1FAE5`.
  - `pb_business_trip/static/src/scss/pb_trips.scss` :2-10 — `--pbtr-accent:#7c3aed`,
    `--pbtr-accent-soft:#ede9fe`, `--pbtr-line:#e6e8ef`, `--pbtr-text:#1e293b`, warn ok; refuse
    buttons elsewhere in the file use `#e11d48`; radii 8/12.
  - `pb_business_trip/static/src/scss/trip_composer.scss` :17 and :64 — INVALID CSS
    (`var(--pbim-primary, #7c3aed)33` — you cannot alpha-suffix a var(); both declarations are
    silently dropped today).
  - `pb_business_trip/static/src/xml/trip_composer.xml` :25,:30,:41,:44 — FontAwesome
    (`fa-file-pdf-o`, `fa-times`, `fa-circle-o-notch fa-spin`, `fa-cloud-upload`), the only Gen-2
    surface using FA.
  - `pb_team/static/src/scss/pb_team.scss` :5-8 — source tints `--ot:#dc2626`, `--trip:#7c3aed`,
    `--correction:#2563eb`, `--leave:#16a34a` (+ their `-soft`s). The conic-gradient donut at ~:62
    is a chart fill — KEEP (W3 exception).
  - `pb_driver_checkin/static/src/scss/driver_map.scss` :4 — `$dm-navy:#0b1f3a` (SCSS var), pin
    default `--bgeo-pin-color, #0b1f3a` ~:124; third copy: `const NAVY = "#0b1f3a"` in
    `pb_driver_checkin/static/src/js/driver_map.js` :7.
  - `biz_week_grid/static/src/scss/week_grid.scss` :9 — `--bwg-primary:#4f46e5`, :16(ish)
    `--bwg-primary-soft:#eef0fe` (the hosted Weekly Entry remaps these to pbim; the DEFAULTS are what
    an un-hosted embed gets).
  - `pb_hr_workforce/static/src/css/wf_breadcrumb.css` :45 `#7c3aed`, :53 `#6d28d9`, :83 `#a78bfa`
    (violet strip rendered on top of all 5 legacy screens).
- Code-health targets: `pb_hr_workforce/static/src/xml/pb_ot_desk.xml` :29 no-op ternary
  (`{{ kpis.pending > 0 ? '' : '' }}`); four stale files
  `pb_hr_workforce/static/src/js/{attendance_live,overtime_rules,payroll_report,workforce_dashboard}.js.i18n_bak`.
- Sidebar records: `pb_sidebar/data/pb_sidebar_data.xml` is `noupdate="0"` (verified) — edits apply
  via `-u pb_sidebar`. Collisions: Leave (`pb_timeoff/data/pb_sidebar.xml` :4-13, seq 30) vs Timecards
  (`pb_sidebar_data.xml` :284-288, seq 30); Trips (`pb_business_trip/data/pb_sidebar.xml` :4-12,
  seq 37) vs Overtime Desk (`pb_hr_workforce/data/pb_sidebar.xml` :21-30, seq 37). Gate gap:
  `item_wf_payroll_report` (`pb_sidebar_data.xml` :304-308) has NO groups while its legacy menu twin
  (`pb_hr_workforce/views/menu_views.xml` :40-45) requires `om_hr_payroll.group_hr_payroll_user` —
  the sidebar item currently shows salary data to ungated users.
- Cockpit assets pattern: `web.assets_backend`, ordered scss → js → xml (see any Gen-2 manifest).
- Weekly Entry pilot seam: `pb_hr_workforce/static/src/js/attendance_weekgrid.js` (373 L) owns the
  dept `<select>` + week ◀ Today ▶ nav in its toolbar
  (`attendance_weekgrid.xml` toolbar block, above the `<WeekGrid>` child at :49-55).

## §3 Work packages (one commit each, in this order)

**WP-A `pb_timeoff` re-tint → promoted green.** Replace the three invented values with the canonical
scale (W1): `--p:#2E7D4F; --ph:#246A42; --soft:#E3F2E9`. Sweep the module for any other
`#059669/#047857/#D1FAE5` literals (templates, JS). Nothing else changes.

**WP-B `pb_business_trip` re-tint → indigo + composer fixes.**
`--pbtr-accent:var(--pbim-primary,#5A4BB0)`, `--pbtr-accent-soft:var(--pbim-soft,#EDEAF8)`,
`--pbtr-bg:var(--pbim-bg,#F5F6FA)`, `--pbtr-line:var(--pbim-line,#E2E8F0)`,
`--pbtr-text:var(--pbim-ink,#1B1733)`; refuse `#e11d48` → `var(--pbim-rose,#DC2668)`; radii 8/12 →
pbim 10/14. Fix trip_composer.scss :17/:64 with
`color-mix(in srgb, var(--pbim-primary, #5A4BB0) 20%, transparent)` (and 40% for :64). Replace the 4
FA icons with `ic()` Lucide: `file-pdf-o→file-text`, `times→x`, `circle-o-notch spin→loader` (+ a
small CSS rotate keyframe), `cloud-upload→upload` — add any missing names to the `IC` registry (W2).

**WP-C `pb_team` source tints → semantic map.** `--ot` red→amber (`#D97706`/soft `#FEF3C7` — aligns
with Overtime Desk's identity), `--trip`→primary (`#5A4BB0`/`#EDEAF8`), `--correction` stays cyan but
via token (`#2563EB`/`#E5EDFD`), `--leave`→green (`#2E7D4F`/`#E3F2E9`). Use `var(--pbim-*, fallback)`
form. Donut stays.

**WP-D `pb_driver_checkin` navy → primary.** Replace all three copies ($dm-navy usages,
`--bgeo-pin-color` default, JS `NAVY`) with the pbim primary (`var(--pbim-primary,#5A4BB0)` in
CSS-land; `"#5A4BB0"` for the JS const). Freshness-dot semantics already on-token — untouched.

**WP-E `biz_week_grid` defaults.** `--bwg-primary: #4f46e5 → #5A4BB0`;
`--bwg-primary-soft: #eef0fe → #EDEAF8`. Generic module — touch only these defaults.

**WP-F `wf_breadcrumb.css` recolor.** `#7c3aed→#5A4BB0`, `#6d28d9→#4A3D96`, `#a78bfa→#CBC2EE`.
CSS-only; do not touch the JS handlers (screens die in P1).

**WP-G Code health.** Remove the pb_ot_desk.xml :29 no-op ternary; `git rm` the four `.i18n_bak` files.

**WP-H Sidebar hygiene (data records only).** Leave seq 30→32; Overtime Desk seq 37→38 (Timecards and
Trips keep theirs). Add `groups_id` = `om_hr_payroll.group_hr_payroll_user` to
`item_wf_payroll_report` (parity with its menu twin — this is the one deliberate access change; W8).
Trips stays ungated (deliberate, demo flows depend on it — note it in your report).

**WP-I NEW module `pb_wf_kit`** (depends: `web`, `pb_theme`, `pb_import_kit`). The P1/P3 seam. Ships:
- `wf_context_service.js` — a `registry.category("services")` service named `wf_context`:
  `state = reactive({ departmentId: false, weekStart: "<ISO Monday>", personId: false, search: "" })`,
  `set(patch)` (merges, persists, notifies), `onChange(cb) → unsubscribe`. Persist to localStorage key
  `pbwf.ctx.v1`. Normalize `weekStart` to Monday using LOCAL date math — not `toISOString()` (that was
  a known Sudima nit: it slips a day across timezones).
- `WfContextBar` component — dept dropdown (`hr.department` searchRead, company-scoped, ordered by
  name), week nav (◀ · label "Aug 11 – 17" · Today · ▶), person typeahead (`hr.employee` name_search,
  limit 8, selecting sets `personId`); reads/writes the service; a `features` prop toggles the three
  segments. Styling: pbim `.ctxi`-style chips per the dossier's mockups (white chip, soft-indigo when
  pinned/active).
- `WfDrawer` component — right-side panel (320px, slide-in, ESC + ✕ close), props
  `{title, subtitle?, onClose}` + default slot. This is the person-drawer chassis from mockup A;
  P0 ships the chassis only.
- `WfRibbon` component — props `{tone: 'amber'|'rose'|'green', text, actionLabel?, onAction?}`,
  rendering the exception ribbon from mockup A.
- SCSS on pbim tokens; assets ordered scss→js→xml; icons via `ic()` (W2); `vi.po` for the (few) user
  strings with proper markers (W7). No backend models — ACLs of `hr.department`/`hr.employee` already
  cover the cockpit personas; if a persona lacks read access the bar degrades to week-only (guard it).
- Server test file `pb_wf_kit/tests/test_p0.py` (@tagged, post_install): sidebar assertions of WP-H
  (unique sequences within the workforce section; payroll-report item carries the payroll group) —
  skip-guard on `pb.sidebar.item` presence so the test never blocks a bare install.

**WP-J Pilot mount — Weekly Entry.** Replace the cockpit's private dept select + week nav with
`<WfContextBar>`; grid reloads on service change; the Ceilings-rail toggle stays. Result: set a
department + week, hard-reload the page → both restored from the service. (Cross-cockpit sync is P1;
do not wire other cockpits now.)

## §4 Safety rails

- W11 behavior freeze: if a change would touch a facade/model/ACL beyond WP-H, stop and note it in
  the report instead.
- The re-tints must not change ANY selector logic — values only — so visual diffs stay reviewable.
- `pb_business_trip` color-mix: keep the existing solid-border fallback color in place if you find a
  rendering issue on the live Chrome — do not invent a new soft hex (W1).
- Respect the biz_theme brand-lock + asset-ordering contract; do not reorder existing asset bundles.
- Sequence/gate edits land via `-u` because the data files are `noupdate="0"` (§2) — no migration, no
  direct SQL.

## §5 Tests (commit with the features, W9)

- **T1** `grep -rn "#059669\|#047857\|#D1FAE5" pb_timeoff/` → 0 hits.
- **T2** `grep -rn "#7c3aed\|#ede9fe\|#e11d48\|#e6e8ef\|#1e293b" pb_business_trip/` → 0 hits;
  `grep -rn ")33;\|)66;" pb_business_trip/` → 0 hits.
- **T3** `grep -rn "fa-" pb_business_trip/static/src/xml/` → 0 hits.
- **T4** `grep -rn "#dc2626\|#7c3aed\|#16a34a" pb_team/` → 0 hits.
- **T5** `grep -rn "0b1f3a" pb_driver_checkin/` → 0 hits.
- **T6** `grep -rn "4f46e5\|eef0fe" biz_week_grid/` → 0 hits.
- **T7** `grep -rn "7c3aed\|6d28d9\|a78bfa" pb_hr_workforce/static/src/css/wf_breadcrumb.css` → 0.
- **T8** `.i18n_bak` files gone; pb_ot_desk.xml ternary gone.
- **T9** `pb_wf_kit` server tests green (`--test-tags` WITH scoping `-u pb_wf_kit` — C18.40).
- **T10** Full registry `-u` of all touched modules EXIT 0.
- **T11–T17 Chrome-MCP on live (mandatory, W10):** for each of Leave, Trips (incl. composer dialog),
  My Team, Driver Tracking, Weekly Entry, plus one legacy screen's breadcrumb (Live Attendance):
  `getComputedStyle` spot-asserts of the new accents (Leave primary button = `rgb(46,125,79)`; Trips
  accent + My Team trip-tint + Driver KPI = `rgb(90,75,176)`; My Team OT tint = `rgb(217,119,6)`;
  breadcrumb link = `rgb(90,75,176)`), zero console errors, screenshot each. Then the pilot check:
  in Weekly Entry pick dept + next week, hard reload → both persist; WfDrawer + WfRibbon rendered once
  via a temporary harness or the pilot page and screenshotted.
- **T18** Regression sweep: open all 14 Workforce sidebar items — each loads, zero console errors.

## §6 Deploy & verify

Standard live ritual (Sudima precedent, W10): md5 parity for every touched file, kill stale odoo-bin,
scoped `-u pb_timeoff,pb_business_trip,pb_team,pb_driver_checkin,biz_week_grid,pb_hr_workforce,pb_sidebar`
+ `-i pb_wf_kit`, stale-assets purge if any OWL change doesn't appear, restart, then §5 T11–T18 on the
live site. Bump each touched module's version (patch level); `pb_wf_kit` starts at `19.0.1.0.0`.

## §7 Report back

1. Commit hashes per WP (A–J), each with tests included.
2. T1–T18 outcomes with pasted evidence (grep outputs, computed-style values, screenshot names).
3. Your self-review notes (W0.1): what you re-read, what you fixed as a result.
4. Any W-rules appended to the ledger; any deviations + why.
5. Open questions Fable should account for in the P1 design (Today board + Time hub merge).

## Kickoff (paste into the Opus 5 session)

> You are Opus 5 implementing **Phase P0 (Foundation)** of the Payobook Workforce redesign. Read
> `docs/handovers/WORKFORCE_P0_FOUNDATION.md` and `docs/WORKFORCE_REDESIGN_CONVENTIONS.md` in full,
> then implement work packages WP-A through WP-J in order — commit per feature with tests, run every
> §5 test yourself, deploy live per §6, Chrome-validate, and self-review your whole diff against the
> handover (Fable will not review this program — you own quality). Report back per §7.
