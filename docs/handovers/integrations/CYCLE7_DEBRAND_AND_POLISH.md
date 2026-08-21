# Integrations Program — Cycle 7: the product's own name, one gesture, and cards that fit

> STATUS: FINAL. Conventions binding through **W153**. Prior reports: `CYCLE5_REPORT.md`, `CYCLE6_REPORT.md`.

Four owner asks from the live abm board (2026-08-21), plus one inconsistency spotted in the same screenshots.

---

## WP-1 — "Odoo" must never appear in anything a user can see

**Owner's words:** *"I do not want Odoo mentioned anywhere to the user in any form — as you see the source says ODOO FIELD - change to PAYOBOOK FIELD. Also check if you have mentioned Odoo anywhere... in fact we did a big exercise of debranding before."*

This is now a **standing rule in the owner's global instructions**, not a one-off request. It applies to UI labels, chips, tooltips, help text, placeholders, empty states, toasts/errors, menu and action names, field `string=`/`help=`, selection labels, reports, exported files, emails, and translation `msgstr`s. The replacement is the product name **Payobook** or a neutral term ("the system", "this app", "the native form").

**It does NOT apply to technical identifiers** — `from odoo import …`, module/model/XML ids, `odoo-bin`, config paths, addon names, log lines, code comments, docs and handovers. Engineering readers need the real name; **rewriting an import or an xmlid breaks the build**. Judge each hit by "could an end user read this string?".

### Confirmed hits (verified 2026-08-21 — start here, then sweep)
| file:line | string | note |
|---|---|---|
| `pb_formula_studio/static/src/js/mapping/mapping_canvas.js:443` | `label: "Odoo field"` | **the chip in the owner's screenshot** → "Payobook field" |
| `…/mapping_canvas.js:444` | hint `"This is one of Odoo's own employee fields, not a field …"` | rewrite in product voice |
| `…/mapping/mapping_studio.js:227` | `_t("%s Odoo employee fields · this source has not told us its own", …)` | the FROM sub-line (currently rendering as "BizApp employee fields" on live — **reconcile: this product's UI says Payobook, not BizApp**) |
| `pb_settings/static/src/js/settings_hub.js:164` | `sub: _t("Odoo's own payroll configuration form — use the crumb to come back.")` | user-visible card subtitle |
| `pb_import_advanced/static/src/xml/connector_cockpit.xml` (kebab item) | the native-form item's visible label/`title` | Cycle 1 shipped "The native Odoo form for this connector" as a tooltip — check and fix |
| `hr_development_ai/views/ai_provider_config_views.xml:51` | `<page string="Odoo Native AI">` | notebook page title |
| `biz_theme/static/src/js/biz_error_dialogs.js:225` | `_t("Odoo Server Error")` / `"Odoo Client Error"` handling | verify what the user actually SEES in the dialog; the debrand seam may already replace it — if it does, say so; if not, fix |
| `pb_hr_payroll_base/i18n/msg.po:2373`, `…/vi_VN.po:3387`, `pb_hr_payroll_formula/i18n/vi_VN.po:5539`, `…/vi_VNnew2.po:5434` | Vietnamese `msgstr` containing "Odoo" | translated UI strings — fix the msgstr (keep msgid semantics), `msgfmt --check-format` after (W7) |

~290 files mention "Odoo" somewhere; the overwhelming majority are imports/comments. **Do not mass-replace.** Sweep systematically for user-visible surfaces: `_t(…)`, `string=`, `help=`, `title=`, `placeholder=`, `label:`, `confirm:`, `sub:`, text nodes in QWeb/report templates, selection labels, `name=` on menus/actions, and `.po` msgstrs. Report the full audited list with a keep/change decision for each borderline case.

### The durable half — a gate, not a one-time clean
Ship a **test that fails when a user-visible string contains "Odoo"** (precedent: the repo's existing static grep gates, e.g. `test_no_python_style_implicit_string_concatenation`). Scope it to the surfaces above with an explicit, commented allowlist for technical exceptions. Without this, the next new string re-introduces the problem — which is exactly how these hits survived the earlier debranding exercise.

---

## WP-2 — Double-clicking a wire reveals BOTH ends; the `‹ ›` arrows go away

**Owner's words:** *"when double clicked you need to bring both left and right field/component in view/in center - by scrolling up and down as needed and also animate by the current glow it shows when clicked on right/left arrow. Then you can remove the < and > arrows as they would no longer be needed."*

Cycle 5 shipped the hub as `‹ │ glyph │ ›` (and `‹ 100% ✓ ✕ ›` for suggestions). Replace that model:

1. **Double-click anywhere on the wire or its hub** → scroll **both** columns simultaneously so the source card and the target card are each centred in their own scroll viewport, then **flash both** with the existing arrival glow (the `.pulse`-style animation Cycle 5 already uses for single-end jumps — reuse it, do not invent a second one).
2. **Remove the `‹` and `›` zones** from the hub. The hub keeps its meaning-carrying content: the transform glyph for accepted wires, and `confidence ✓ ✕` for suggestions. It gets simpler and smaller — check the collision-avoidance maths still holds with the narrower pill.
3. **Discoverability** (the reason the arrows existed): the wire/hub gets a tooltip — "Double-click to bring both ends into view" — and the hint appears on hover. Keep a keyboard equivalent (Enter on a focused wire does the same thing) so the gesture isn't mouse-only.
4. **Honest edge cases**: if an end cannot be centred (near the top/bottom of a list) scroll as close as possible; if an end is **hidden by a search/filter**, say so rather than silently doing nothing — reuse Cycle 5's "hidden by filter" vocabulary and offer to clear it.
5. Cycle 5's tests that assert the arrow zones must be **rewritten deliberately** to assert the new gesture (not deleted to make the suite pass), and the Cycle 5 report/ledger reference updated so the record matches the shipped behaviour.

---

## WP-3 — The feed cards' buttons overflow

**Owner's words:** *"note how the buttons in the kanban cards are overflowing - fix them eg Fetch Fields is overflowing and also Map fields visible for rightmost card overflowing."*

In the connector cockpit's **Feeds** grid (`pb_import_advanced`, the endpoints strip Cycle 1 shipped, extended in Cycle 6 with `Fetch fields`), the action row now holds up to four buttons (`Sync · View data · Fetch fields · Map fields`) and overflows the card: "Fetch fields" is clipped at the card edge and the rightmost card's "Map fields" spills outside the grid entirely.

- Make the action row **wrap** (or otherwise reflow) so buttons always stay inside their card at every breakpoint — verify at the owner's ~1450px viewport and at 1280 / 1600 / 1920.
- The button set is currently **inconsistent between cards** (some show `Map fields`, others don't). Decide one rule, apply it to every card, and state it — a card that can't offer an action should show it disabled with a reason, or not at all, but not at random.
- Nothing may be clipped by `overflow:hidden` — if a card clips, that is a layout bug, not a styling preference.
- Same pass: confirm no other cockpit card grid has the same overflow (the Integrations board cards gained content in Cycles 1/5).

---

## WP-4 — The floating launcher overlaps the right column

The support/coach launcher ("Stuck?" pill + the lightning button, bottom-right) sits on top of the TO column's cards in the Mapping Studio and over the Feeds grid in the cockpit. **Cycle 6 attempted this and failed** — its report records "a launcher offset that changed the CSS but moved nothing", i.e. the rule it edited was not the one in effect.

Find what actually positions those launchers (which module owns them; check computed styles in the live browser rather than reasoning from source), then keep them clear of scrollable content — a real fix, verified in the browser at the owner's viewport. If they are NOT ours, report what owns them and leave them alone.

---

## WP-5 — "Last sync" and "Never synced" disagree on the same screen

In the owner's cockpit screenshot the connector header reads **`Last sync 2026-08-20 23:25`** and shows **Connected**, while **all seven feeds read `Never synced`, `0 staged · 0 pulled`**. Two truths on one screen is the exact failure class this programme has been closing.

Diagnose (a test connection or a failed pull stamping `connector.last_sync` without any feed stamp is the likely cause — see Cycle 1's `_stamp_endpoint`), then make the two agree: either the header reflects real feed activity, or it says what it actually means ("Connection tested 2026-08-20 23:25"). Report the root cause; do not paper over it in the template.

---

## Binding non-goals
No new models. No changes to Cycle 6's catalog/provenance semantics beyond the WP-1 wording. **Do not press `Fetch fields` on abm's live Zoho connector** — it calls the owner's real Zoho account and is an explicit owner decision still pending. No re-seeding or editing of abm's mappings. No mass find/replace of "Odoo" across the tree. Don't touch the ⌘K fold question or the `pbms-canvas` class collision (separate item). Never stage `.claude/settings.json`, `thaco/`, `ABM/`; never push.

## Numbered tests
1. The static gate fails on a deliberately-added user-visible "Odoo" string and passes on a technical one (prove both directions — W127's lesson: a gate that cannot fail is worse than no gate).
2. Every confirmed hit in WP-1's table is fixed; the FROM sub-line, the provenance chip and its hint read in product voice; `msgfmt --check-format` clean on every touched `.po`.
3. Double-click on a wire centres BOTH ends and flashes both; from a scroll position where neither end is visible; and where one end is near a list boundary.
4. Double-click when an end is filtered out surfaces the "hidden by filter" affordance instead of doing nothing.
5. The hub no longer renders `‹`/`›`; the transform popover, accept/reject and collision avoidance all still work; keyboard equivalent works.
6. Feed-card buttons stay inside their card at 1280 / 1450 / 1600 / 1920; no clipped label; the button-set rule is uniform across cards.
7. The launcher no longer overlaps scrollable content at the owner's viewport (or is proven not ours).
8. Header sync state and feed sync state agree — assert on a connector whose feeds have never pulled.
9. Regression: Cycles 5/6 behaviour intact (wires, dock chips, search/filters, provenance, catalog, contrast); scoped suite across the affected modules green, exit 0 modulo the known pre-existing clock-dependent failures named in Cycle 6's report.
10. Live validation (Chrome MCP; W129 temp user, W130 own Chrome) on **abm** and payobook at ~1450–1900px: before/after screenshots of the chip, the sub-line, the wire double-click (both ends centred + glowing), the feed cards, and the launcher; zero console errors, zero non-warmup ≥400s.

## Deploy + verify
Standard ritual, **W136 stall-proof units**, both databases. `.po` changes need the module `-u` to reload translations; asset changes need the bundle rebuild + a Chrome page load (SCSS compiles lazily). JS gate is `node --input-type=module --check < file` (W127). Version-diff the reverse-dep closure (W118).

## Self-review
Check twice: (1) no technical identifier was renamed in the debrand pass (grep your own diff for `from odoo`, xmlids, model names); (2) the gate's allowlist is narrow and each entry has a reason; (3) the double-click gesture is discoverable without the arrows; (4) no card clips at any tested width.

## Commits
Per feature, explicit staging: (1) fix: the product says its own name; (2) test: a gate so the name cannot come back; (3) feat(pb_formula_studio): one gesture brings both ends home; (4) fix(pb_import_advanced): feed cards keep their buttons; (5) fix: the launcher stops sitting on the content; (6) fix: one sync truth per screen; (7) docs: ledger + report. Tests with their feature (W9). Write `CYCLE7_REPORT.md` incrementally, committing at milestones.

## Report back
The full WP-1 audit table with keep/change decisions; proof the gate fails and passes; before/after screenshots for every visual change; the WP-5 root cause; what owns the launchers; commit hashes; deploy EXIT codes for both databases; deviations; new W-rules (W154+).
