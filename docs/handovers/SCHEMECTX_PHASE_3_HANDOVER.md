# SCHEMECTX Phase 3 — the studio's Settings opens the guided journey, in edit mode

Read `SCHEMECTX_LEDGER.md`, then `BLUEPRINT_LEDGER.md` (rules :78-110, rulings
:113-140, studio plumbing :143-175, gotchas — BP13, BP14/BP38, BP53, BP-R8,
BP-R11 above all), then `BLUEPRINT_CLOSEOUT.md` :190-212, then the Phase 1 and 2
reports.

## 1. What the owner asked for

In the studio (scheme header, tabs Cards / Grid / Test / Compare / Settings),
**Settings** should open the full-screen guided journey ("New configuration",
six steps) — "cleaner and premium" — with every field already filled in when an
existing payroll scheme is being edited.

Owner rulings (ledger rule 10): every Settings field moves into the journey and
the old panel is retired; the journey opens for **Active** schemes too, with
safety locks.

## 2. Scope

1. An explicit **edit mode** of the `pb_blueprint` journey for any scheme —
   draft or Active, made by the journey or not.
2. A home in the journey for every field the Settings panel edits.
3. The studio's Settings tab routes to it; the old panel is removed at the end.

### Binding non-goals

* Do NOT edit `pb_formula_studio/models/pb_formula_studio.py` (rule 7). Its
  `formula_studio.js` and `studio.xml` may be edited.
* Do NOT duplicate the settings whitelist. Edit mode reads and writes settings
  through the studio's existing `get_config_settings` / `save_config_settings`
  (`pb_formula_studio.py:12641 / :12679`, fields `_CFG_FIELDS :12540-12551`,
  option lists `_config_meta :12580`). One contract, two screens → one screen.
* Do NOT let edit mode regenerate, restart, discard or wipe anything.
* Do NOT move Activate / Validate / Set to draft out of the studio header.
* Do NOT loosen the pay-logic gate: rule, tax-band, calendar and component
  writes on a scheme that is not draft, or that has payslips, still refuse.

## 3. Ledger rule 8, reconciled → record as rule **8a** in BLUEPRINT_LEDGER.md

Rule 8: "the draft is the working copy and an active configuration is never
edited as one." It protects **pay logic**. Settings — identity, accounting,
connections, export options, part-month pay, back-pay, source lanes — are not
pay logic in that sense and ALREADY write straight to a live scheme through
`save_config_settings`. Edit mode keeps exactly that contract and adds nothing
to it. 8a: *"Edit mode writes settings to the live configuration, as the studio
always has; it never writes pay logic to a configuration that is not a draft or
that has paid anyone."*

## 4. Verified plumbing — do not re-derive

| Fact | Where |
|---|---|
| Settings tab button → `openSettings`; view switcher `state.view` | `pb_formula_studio/static/src/xml/studio.xml:98`; `static/src/js/formula_studio.js:3341-3355`; save/revert `:4086-4103`; state `:442-448`; arrival param `open_settings` `:630`; ⌘K entry `:1196` |
| Old panel markup, 5 sub-tabs (Setup, Sources, Approvals, Automation, Intelligence) | `studio.xml:210-495`, sub-tabs `:264`, footer `:490-493` |
| Journey tag + action | `pb_blueprint/static/src/js/blueprint.js:1097`; `views/pb_blueprint_action.xml:5-9`; steps `static/src/js/blueprint_steps.js:22` |
| Arrival params (params OR context) `config_id`, `step`, `task`; URL persistence `_rememberInUrl :239-246`; `onMounted` re-assert `:189-193` | `blueprint.js:209-222` |
| `resume()` → `bp_load` | `blueprint.js:248-277`; `models/blueprint_studio.py:467` |
| `_guard(config_id, require_blueprint=True)` refuses a scheme with no `pb.formula.blueprint` row; two-layer company check; `_has_payslips :197-203` | `blueprint_studio.py:153-188` |
| `pb.formula.blueprint`: `unique(config_id)`, `state draft|finished|abandoned`, `step`, `template_key`, `effective_from :97`, `revision` optimistic lock | `models/blueprint.py:51-160` |
| `bp_save` writes only name, cycle_type, effective_from, situations, step | `blueprint_studio.py:574` |
| `bp_restart` wipes rules/rate tables/samples; refuses non-draft or payslips | `blueprint_studio.py:836-888`; `bp_discard :902` |
| `bp_finish :664`, `bp_reopen :699-718` (draft + no payslips only) | `models/blueprint_finish.py` |
| Start step: starter cards `steps.xml:104-136`, picking `blueprint.js:479-503`; country select locked once created `steps.xml:61-67`, `onUnlock blueprint.js:516-526` | — |
| Per-step endpoints: rules `blueprint_components.py:56,532,753,849,1075,1151`; tax `blueprint_tax.py:94,326,416,530`; calendar `blueprint_calendar.py:66,300`; connect `blueprint_connect.py:72,452,471,532`; outputs `blueprint_outputs.py:68,231,432`; test `blueprint_tests.py:145,466,526,863`; finish `blueprint_finish.py:93,664,699,721` | — |
| Studio → journey door that exists: `bpResume` (`params:{config_id}`, `clearBreadcrumbs:false`); board override shows drafts only | `formula_studio.js:4235-4240`; `pb_blueprint/models/formula_studio_ext.py:24-46` |
| Journey → studio: `bp_studio_action :926-947`, called `blueprint.js:880-887`; back chip `blueprint.js:460-463` | — |
| Hand-off law: `doAction` + `pb_back`, never import across modules (BP-R8); Connect doors precedent `step_connect.js:246-294` | — |
| Approvals panel is ALREADY shared by both screens (`ApprovalSchemePanel`) | `studio.xml:351`; `step_connect.js:10` |
| Lifecycle + delete blockers | `pb_hr_payroll_formula/models/formula_config.py:1084-1150` |
| Tests: python `pb_blueprint/tests/*` (`post_install`), JS hoot `pb_blueprint/static/tests/*.test.js` + `blueprint_fixture.js`; no tours | — |

## 5. Architecture

### 5.1 Server (`pb_blueprint`)

* `blueprint.py`: add state `('editing', 'Being edited')`. Audit every
  `state ==`/`in (` on this model in the module (board override, reopen, finish,
  discard-check) so `editing` never shows as a "Resume setup" draft card.
* `bp_adopt(config_id)` — the ONE write that enters edit mode. `_guard(…,
  require_blueprint=False)`; no row → create one (`state='editing'`,
  `template_key=False`, `step='start'`, `effective_from` = earliest payslip
  period start if any, else today's month start); `finished` → `editing`;
  `draft` → untouched (a draft opens as the normal journey, not edit mode);
  idempotent. Returns `{ok, mode}`.
* `bp_load`: for `editing` rows returns `mode:'edit'` plus
  `locks: {country: bool, pay_logic: bool}` (`country` = `_has_payslips`;
  `pay_logic` = state ≠ draft OR `_has_payslips`), `built_from` (starter name
  or "Built in the components grid" / "Imported from a workbook"), and
  `scheme_state`. It must not write (BP53) — a scheme with no row returns
  `{ok: False, needs_adopt: True}` and the client calls `bp_adopt`.
* `bp_settings(config_id)` / `bp_save_settings(config_id, values, revision)`:
  thin, `_guard`ed pass-throughs to `pb.formula.studio`
  `get_config_settings` / `save_config_settings`. `country_code` refused with a
  plain sentence when `locks.country`; `company_id` never accepted (BP-R11).
  Bump the blueprint `revision` and honour the optimistic lock.
* `bp_finish` in edit mode = **"Save changes"**: state → `finished`, no
  generation, no activation; returns the studio action.
* `bp_restart`, `bp_discard`, regenerate-type endpoints: refuse in edit mode
  with a sentence. Every pay-logic write endpoint (§4 list): when
  `locks.pay_logic`, refuse with "This scheme has already paid people / is
  Active. Change its pay rules in the components grid, where every change is
  versioned." + the studio door. When the scheme is a draft with no payslips,
  they work as today.

### 5.2 Journey UI — edit mode

* Title **"Edit configuration"**; rail header "EDITING" + the scheme's state
  chip (Draft / Active); footer "Saved to <company>" unchanged. Final button
  "Save changes".
* **Start**: Identity card pre-filled (name, country — locked with a Lucide
  `lock` + reason when `locks.country` — pay cycle, effective from, Phase 1's
  "Pays in" chip). The starter cards are replaced by a calm read-only **"Built
  from"** card. An **Advanced** fold: code, structure, colour-coded workbook
  import, identity columns on export.
* **Pay rules**: the existing components/tax/calendar panels. When
  `locks.pay_logic` they render read-only with one banner + "Open the components
  grid" door; for a scheme with no recipe (adopted) show the component summary
  only. NEW cards here: **Part-month pay** (`use_proration`, basis, components,
  rounding) and **Back-pay** (`use_auto_retro`, `retro_component_id`) — always
  editable. Port the markup/behaviour from `studio.xml` Automation sub-tab;
  restyle to the journey's card language.
* **Connect**: NEW cards **Connected system** (`connector_id`), **Where values
  come from** (the three source lanes + priority order with the consequence
  chips from `source_lane_counts` — port from the Sources sub-tab; drag to
  reorder, keyboard-operable), **Accounting** (journal, debit, credit).
  Approvals is already here.
* **Outputs / Test**: unchanged; read-only where they would regenerate.
* **Finish**: review of what changed in this sitting (field, before → after),
  then "Save changes". Settings save as each card is committed (same as the
  journey's existing autosave pattern — follow whichever pattern the step it
  lives in uses); Finish only closes the sitting.
* These new cards are ALSO shown in create mode (a new scheme deserves them
  too), collapsed by default so the six-step flow stays light.
* `mode` joins the arrival params and the URL state (BP14/BP38): a refresh
  stays in edit mode on the same step. Back chip in edit mode returns to the
  studio on that scheme (`pb_back`), not to "Payroll configurations".
* Design bar binding: hero moment = arriving from the studio, the rail already
  ticked through with real values in every card, nothing blank. No dead ends.
  1440 + 390. EN + VI. Never "Odoo".

### 5.3 Studio

* `openSettings` → `orm.call('pb.blueprint.studio','bp_adopt',[config_id])` →
  `doAction({tag:'pb_blueprint', params:{config_id, mode:'edit'}, context:{…,
  pb_back:{tag:'pb_formula_studio', context:{config_id}}}})`. `pb_blueprint`
  depends on the studio, not the reverse — the studio must probe: if the
  `pb.blueprint.studio` model/action is absent or `bp_adopt` fails, fall back to
  the old panel (during the phase) / a plain message (after removal). The
  `open_settings` arrival param and the ⌘K entry route the same way.
* **Intelligence** sub-tab (exec order, unused components, cycles) has no
  journey home: promote it to its own studio tab, same content.
* When everything above is validated in the browser, delete the old panel's
  markup/JS/SCSS and its hoot tests; keep `get/save_config_settings` (now the
  journey's backend). That is the LAST commit of the phase.

## 6. Test cases (report each by number, PASS/FAIL + evidence)

1. `bp_adopt` on a scheme with no row → row `editing`; rules, rate tables, samples byte-identical (hash before/after).
2. `bp_adopt` twice → one row, no error; on a `draft` row → state unchanged.
3. `bp_load` on an un-adopted scheme → `needs_adopt`, and nothing written (row count, `write_date`s).
4. Edit mode on an **Active** scheme: `bp_save_settings` writes journal/accounts/part-month/back-pay/source order; reload returns them.
5. Every `_CFG_FIELDS` member except `company_id` round-trips through the journey endpoints (loop the tuple).
6. `country_code` change refused once payslips exist; accepted on a draft without.
7. Each pay-logic write endpoint refuses under `locks.pay_logic` and leaves the rules byte-identical.
8. `bp_restart` / `bp_discard` refuse in edit mode.
9. Edit-mode `bp_finish` → `finished`, no rule created/changed, scheme state unchanged (Active stays Active).
10. An `editing` row never appears as a "Resume setup" card on the board.
11. Wrong-company and unreachable-company reasons still come back as sentences (BP-R11, BP13).
12. Stale `revision` → the existing conflict answer, not a silent overwrite.
13. JS hoot: arrival with `mode=edit` renders the edit title, Built-from card, no starter cards; refresh keeps mode + step.
14. JS hoot: studio `openSettings` calls `bp_adopt` then `doAction` with `pb_back`; adopt failure → fallback.
15. VI strings load for every new string (PO gate + one rendered check).
16. Suites green: `/pb_blueprint`, `/pb_formula_studio` (pre-existing reds listed separately).

## 7. Deploy + verify

Ledger rule 13. Chrome MCP, `rize.payobook.com`, 1440 + 390, console read:

* a. Studio → **Rize Vietnam Payroll** (Active, has an August run) → Settings: journey opens titled "Edit configuration", every card filled, country locked with its reason, pay rules read-only with the door to the grid.
* b. Change the accounting journal (or, if rize has no journal, the export option), Save changes → back in the studio; Settings again → the value held. Put it back.
* c. **Rize India Payroll** (no runs): same route; country unlocked; "Pays in ₹ INR".
* d. Refresh mid-journey → same step, still edit mode. Back chip → the studio, same scheme.
* e. Payroll configurations → New configuration still behaves as before (create mode regression), starter cards present.
* f. After the old panel is removed: ⌘K "Settings" and the Intelligence tab both work; console clean.

## 8. Commits

(1) edit-mode server, (2) journey UI edit mode + new cards, (3) studio routing +
Intelligence tab, (4) old panel removal. Explicit staging, no push,
`Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.

## 9. Report back

`docs/handovers/SCHEMECTX_PHASE_3_REPORT.md`: tests by number; rule 8a added to
the BLUEPRINT ledger; any Settings field that could not be given a home and why;
handover facts that were wrong; new SC gotchas; commit hashes; anything not
browser-validated and why. Return a ≤250-word summary.
