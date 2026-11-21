# JOURNEY Phase J1 — One Mapping home

> **DELIVERED 2026-08-25.** Live on abm · acme · payobook · payobook_template at
> pb_formula_studio **19.0.1.131.0**. 15/15 numbered cases pass; Python **74/74** (was 63),
> hoot **62/62** (was 60); abm diffed clean before and after. Two documented deviations,
> both recorded as ledger entries rather than silently absorbed: **MJ1** — a lane chip
> filters the LEFT column only, because that is what the shared canvas' `groupFilter` prop
> has always meant and changing it is a board redesign (binding non-goal); **test 10's
> destructive round-trip had no subject** — abm's live unresolved count is 0, so the
> reconciliation dialog was proved on its real empty state plus a client-side synthetic
> pair of rows (no RPC, no write) rather than by manufacturing an unresolved column on a
> live database. Full outcome, and seven MJ gotchas, in `JOURNEY_LEDGER.md`.

**Read first:** `docs/handovers/JOURNEY_LEDGER.md` (programme frame + owner decisions J-D1/J-D2),
then the standing rules of `MAPFIX_LEDGER.md` (deploy ritual, MF12/MF17/MF35/MF37/MF41, CR6/CR20)
and `SOURCING_LEDGER.md`. **White-label absolute: no user-visible string may say "Odoo".**
Branch 19.1. Commit at the end (explicit staging, ledger + this handover included). **Do not push.**

## Mission

Today the mapping board has two shells: a modal overlay inside Formula Studio ("Mapping canvas")
and a full-screen cockpit ("Mapping Studio"). They mount the SAME `MappingCanvas` component and
call the SAME server adapters — but each shell has features the other lacks, and users meet two
half-products. J1 makes the **full-screen shell the only shell**, renamed **"Mapping"**, carrying
everything the overlay could do, reachable pre-scoped from Formula Studio. After J1 the overlay
chrome is gone.

## Scope

1. Port the overlay-only capabilities into the full-screen host (`mapping_studio.js/.xml/.scss`).
2. Rename user-visible "Mapping Studio" → **"Mapping"** (action name, Settings card, palette entry,
   buttons). Keep technical ids (`pb_mapping_studio` tag, action XML id) unchanged — label-only.
3. Formula Studio's Mapping button / tool card / ⌘K entries open the full-screen action
   **pre-scoped** to the scheme being edited (ctx `pb_config` + `pb_mode`), replacing the overlay.
4. Retire the overlay chrome (scrim markup, its state and handlers) — but MOVE, don't lose, the
   dialogs that only exist there (reconcile, template save). One implementation, one home.
5. Final tab labels (J-D2), overlay's generic labels die: `System fields → Scheme`,
   `Spreadsheet columns → Scheme`, `Employee & contract fields`, `Mid ↔ End cycle`,
   `Scheme assignment`. (A "Journey" landing tab comes in J5 — do NOT stub it now.)

**Non-goals (binding):** no Excel on-ramp (J2); no two-way arrows or conflict dialog (J3); no
Transformations tab (J4); no behaviour change in ANY server adapter contract or in the resolver;
no redesign of the board itself — this is a port + unification, feature-parity is the bar.
`om_hr_payroll` untouched (CR1).

## Verified plumbing (do not re-derive; all paths repo-relative)

**Hosts.** Full-screen: `pb_formula_studio/static/src/js/mapping/mapping_studio.js` (822 lines),
`static/src/xml/mapping_studio.xml` (270), `static/src/scss/mapping_studio.scss` (394, `.pbim.pbms`),
action `views/pb_mapping_studio_action.xml:9-12` (`action_pb_mapping_studio`, tag registered
`mapping_studio.js:822`). Overlay: `static/src/js/formula_studio.js:4385-5040` (state `:235-254`,
tabs `mapTabs :4386-4393`), `static/src/xml/studio.xml:2026-2252` (employee-mode blocks
`:2038-2085`, source `<select>` `:2085`, template UI `:2094-2102` + dialogs `:2185-2228`,
lane chips `:2122-2143`, unresolved footer `:2236-2250`, reconcile dialog `:2254+`),
`static/src/scss/mapping.scss:1-97` (`.pbfs-map*`). Shared board: `mapping/mapping_canvas.js`
(1656) + `xml/mapping_canvas.xml` (507) + `mapping.scss:98-779`; pure kernel
`mapping/mapping_geometry.js`. Non-fork rule stated at `mapping_studio.js:24-34` — keep it true.

**Overlay-only features to port (the whole J1 payload):**
- (a) Employee/Contract lane chips + lane filter + per-lane unmapped counts — `mapEmpChips`,
  `studio.xml:2122-2143`.
- (b) "Add a field to map…" autocomplete — `studio.xml:2039-2047`, RPC `ec_search_fields`
  (`pb_formula_studio.py:6375`).
- (c) "Employee ▾ / Contract ▾" browse-all dropdowns — `studio.xml:2049-2084`, RPC
  `ec_model_fields` (`:6386`).
- (d) Remove-unwired-right-field (`onRemoveRight`) — prop not passed by the Studio host today.
- (e) Card verbs make-component / make-text / detach (`onLeftAction`) —
  `formula_studio.js:4650-4653`.
- (f) Unresolved-columns footer + "Resolve remaining N columns" reconcile dialog —
  `studio.xml:2236-2250`, `:2254+`; RPCs `employee_mapping_unresolved` (`:6777`),
  `employee_mapping_resolve_remaining` (`:6786`).
- (g) Payroll-components toggle on the employee board — `_mapExtraArgs`
  (`formula_studio.js:4869`; Studio calls `employee_mapping_data(cfg, false)` with no payroll arg,
  `mapping_studio.js:454`).
- (h) Template **save** and **delete** (Studio is apply-only, `mapping_studio.xml:230-264`) —
  overlay UI `studio.xml:2094-2102`/`2185-2228`, RPCs `mapping_template_save` (`:5244`),
  `mapping_template_delete` (`:5387`); keep the overlay's per-line apply-result breakdown, it is
  strictly better than the Studio's one-line summary.

**Doors (all must still work after J1):**
- Settings hub card — `pb_settings/static/src/js/settings_hub.js:151-153` (label → "Mapping").
- Palette — `pb_hub/static/src/js/hub_palette_entries.js:195-197` (label → "Mapping · Setup").
- Integrations cockpit "N mappings" — `pb_integrations/static/src/js/integrations.js:236-246`,
  xml `:95-101` (arrives ctx `pb_connector`, `pb_mode:"api"`).
- Connector cockpit "Open Mapping Studio" + per-feed "Map fields" —
  `pb_import_advanced/static/src/js/connector_cockpit.js:639`, xml `:97`, `:186`
  (labels → "Open Mapping" / keep "Map fields").
- Formula Studio overlay's "Open in Mapping Studio" (`formula_studio.js:4771-4785`,
  `studio.xml:2107`) — this becomes the ONLY behaviour of the Mapping button itself; the separate
  escape-hatch link dies with the overlay.
- Deep-link arrival ctx read: `mapping_studio.js:151-168` (incl. `fell_back` notice — keep).
- Auto-open flag `pbfs_open_people_mapping` (`formula_studio.js:592-601`): trace its setters and
  re-route them to open the full-screen action with `pb_mode:"employee"` + `pb_config`.

**Tests that assert doors (update, don't delete):**
`pb_settings/tests/test_settings.py:129-134` and `pb_integrations/tests/test_one_door.py:158-245`
assert `pb_mapping_studio` in the hub door list / bundled JS — the tag survives J1, so these should
stay green; fix label assertions only if they bite.

**Baselines to preserve:** hoot `/web/tests?filter=mapping_canvas` = **60/60** green on abm;
Python mapping suites on abm = **63/63** (TestMappingDefects, TestMappingSelectionValues,
TestMappingCreateGuard + earlier). These numbers may only go UP.

## Architecture

- **One host absorbs, the other dies.** Extend `MappingStudio` with the employee-mode toolbar
  (chips (a), pickers (b)(c), payroll toggle (g)) and pass the missing props ((d)(e)) so
  `MappingCanvas` — which already implements the behaviours — simply receives them. Where the
  overlay implemented UI in `studio.xml` (reconcile dialog, template save dialog), MOVE the
  markup+logic into the full-screen host (or into a small shared component under
  `static/src/js/mapping/`) — never duplicate; after J1 `grep` must find ONE implementation of each.
- **Pre-scoped launch.** Formula Studio's Mapping button/tool/⌘K → `doAction` on
  `action_pb_mapping_studio` with ctx `{pb_config: <current config id>, pb_mode: <last overlay tab
  or "employee">}`. The Studio's existing ctx reader (`:151-168`) already honours these.
  Cold-start (Settings card, palette) keeps defaulting to `api`.
- **Retire the overlay.** Remove the scrim markup (`studio.xml:2026-2252`), the mapping open/close
  state and handlers in `formula_studio.js:4385-5040` that exist only for the overlay shell — but
  KEEP any function the full-screen host or other Formula Studio features still call (e.g.
  `cfg_import_excel` is unrelated; check callers before deleting anything, MF39's lesson: deleting
  live-tested code to chase tidiness buys regressions). `.pbfs-map*` styles that become unused go
  too. `mapping.scss:98-779` (the board itself) stays.
- **Naming.** User-visible strings only: action `name=`, Settings card, palette label, connector
  cockpit buttons, any header/title in `mapping_studio.xml`. The FROM…TO sentence header stays.
  No "Studio" and no "Odoo" in anything a user reads on this surface.
- **Ports honour MAPFIX lessons:** constant-width affordances out of the text flow (MF13/MF26);
  measure-then-place for any popover (MF27); root keydown must not steal Enter from buttons
  (MF33); session extras insert at lane position via `placeInLane` (MF36b/MF40 — porting (b)(c)
  makes that latent path LIVE in the full-screen host, so it must work).

## Safety rails

- **The database is the oracle (MF37).** On abm, snapshot before/after all live validation:
  `select id, component_id, target_model_id, target_field_id from hr_payslip_import_mapping order
  by id` and `select id, code, source_binding, source_binding_key from hr_formula_rule where
  config_id = <abm config> order by id` (via `ssh Payobook19v2 "sudo -u postgres psql -d abm …"`).
  Diff must be empty; restore anything that moved. Probe write-capable gestures with nothing armed.
- CR20/MF9: park validation tabs on `about:blank` before stopping servers; confirm zero odoo-bin
  pids BY PID; read results from `/var/log/odoo/odoo-server.log`.
- Server adapters: signatures and return shapes UNCHANGED. If a port genuinely needs a server
  change, it must be additive and noted in the report.
- Screenshots to `.journey-shots/J1/` (repo root, untracked).

## Numbered test cases (run on abm unless said; all must pass before commit)

1. Settings → Integrations card reads "Mapping", opens the full-screen surface, cold-start on
   `System fields → Scheme`.
2. Formula Studio Mapping button opens full-screen Mapping **pre-scoped to the open scheme** (FROM…
   TO sentence names it; no picker needed) — and there is no overlay scrim anywhere in the DOM.
3. All five tab labels match §Scope 5 exactly; tab switching works; the FROM…TO header updates.
4. Integrations cockpit "N mappings" and Connector cockpit doors still arrive with connector (and
   feed) pre-picked; the `fell_back` notice still fires on a bad deep link.
5. Employee & contract tab in full-screen now shows lane chips with unmapped counts; clicking a
   chip filters both columns; counts match the overlay's pre-J1 values (record them first).
6. "Add a field to map…" autocomplete finds `Division`, adds it **at its lane position** (count
   lane headings before/after — no new heading at the bottom, MF32/MF40), and it can be wired.
7. Employee ▾ / Contract ▾ dropdowns list the full catalogue (236 cards on abm) and pin a field.
8. make-component / make-text / detach verbs work from the ⋮ menu in full-screen; a promotion to
   amount flips the payroll toggle on before reload (MF15).
9. Payroll-components toggle shows/hides payroll cards on the employee board.
10. Unresolved footer shows abm's current count; the reconcile dialog opens, unticking a row leaves
    it `reference`, resolving updates the footer — then RESTORE abm to its pre-test state and prove
    it with the MF37 diff.
11. Templates: save a template in full-screen, apply it, see the per-line breakdown, delete it.
    (Use a throwaway config on abm if needed — restore after.)
12. Keyboard: `/` focuses search, `w` walks wires, Escape ladder intact, Enter on a focused button
    does NOT draw a wire (MF33) — all in the full-screen host.
13. Hoot `/web/tests?filter=mapping_canvas` ≥ 60/60; Python mapping suites ≥ 63/63 on abm.
14. Layout proof: 0 bounding-box overlaps over all cards at 1440 and 1024 in employee mode with
    chips + pickers visible; 0 console errors across the whole run.
15. Grep gates: `grep -ri "mapping studio" --include="*.xml" --include="*.js" pb_*` finds no
    user-visible string (comments/ids fine); no user-visible "Odoo" introduced.

## Deploy & verify

MAPFIX ritual verbatim: rsync → `sudo chmod -R a+rX` → stop → detached `systemd-run` looping
`sudo -u odoo /odoo/odoo-server/odoo-bin -c /etc/odoo-server.conf -d <db> -u pb_formula_studio,pb_settings,pb_integrations,pb_import_advanced --stop-after-init`
over **abm acme payobook payobook_template** → start → `ir_module_module.latest_version` check in
psql on all 4 (`sudo -u postgres`). Bump `pb_formula_studio` version (+ any other touched module).
MF12: late asset edits need a re-`-u` or attachment purge — do not trust the browser.

## Report back

Versions shipped · test tally per numbered case · hoot/Python counts · the MF37 before/after diffs
(must be empty) · doors checklist (all six) · screenshots index · any deviation from this spec with
reasoning · new gotchas as MJ-entries appended to `JOURNEY_LEDGER.md` (with the phase-status line
updated) · the single commit hash. Do not push.
