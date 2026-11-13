# MAPFIX Phase C — Errors that say nothing technical, and a Primary Key you cannot miss

Read `docs/handovers/MAPFIX_LEDGER.md` FIRST (owner decisions MF-C1/C2, the verified error-dialog
facts, gotchas MF1-MF…) and `docs/handovers/COLROLES_LEDGER.md` (CR1-CR33 bind; CR6 chmod + psql
`latest_version` verification, CR20 park browser tabs on `about:blank` before stopping the service,
CR33 apex RPC password dead — use the browser session).

Phases A and B are live. This phase is smaller and touches a DIFFERENT module (`biz_theme`, plus a
one-line view fix in `pb_hr_payroll_formula`) — mind the manifest bumps and the asset cache.

## Scope

1. **MF-C1** — technical error detail is hidden from users everywhere a user can see a dialog,
   while remaining available in developer mode.
2. **MF-C2** — the multisheet import's Primary Key is guarded at the field, so the user never
   reaches the server-side raise that produced the owner's error screenshot.

**Binding non-goals**: do NOT redesign the error dialogs' look; do NOT touch `om_hr_payroll`
(CR1); do NOT change any server-side exception text or exception classes; do NOT remove the
existing server-side `UserError` raises (they are the backstop — only make them unreachable by
normal use).

## Part 1 — Error dialogs (MF-C1)

### The situation (verified; do not re-derive)

- The owner's dialog is `BizErrorDialog` — `biz_theme/static/src/js/biz_error_dialogs.js:108`,
  template `biz_theme/static/src/xml/biz_error_dialogs.xml:4`. The "attention" variant string is at
  `:44`; the exception→variant map at `:69-79`; the registry force-override at `:196-200`.
- The Technical-details block is `xml/biz_error_dialogs.xml:45-54`; its content comes from the
  `technicalDetails` getter (`js:141-149` — joins `props.name`, `message`, `props.exceptionName`,
  `props.traceback`); it is **already** gated on developer mode by `showTechnicalDetails`
  (`js:151-160`, `Boolean(window.odoo && window.odoo.debug)`). **The owner saw it because that
  session had developer mode on — which MF-C1 says is acceptable.** So the dialog they screenshotted
  is, strictly, behaving as designed.
- **The real, unfixed problems are the coverage gaps**, and those are what this phase must close:
  1. `biz_theme` registers its error assets into **`web.assets_backend` only**
     (`biz_theme/__manifest__.py:73-75`). On portal / website / login bundles users get the **stock**
     dialog: title `_t("Odoo Error")` and a "See technical details" `<pre>` traceback
     (`web/static/src/core/errors/error_dialogs.js:47-84`, template
     `web/static/src/core/errors/error_dialogs.xml:53-77`) — with no debug gate at all.
  2. `RedirectWarningDialog` (`web/.../error_dialogs.js:172-198`, title `_t("Odoo Warning")` at
     `:181`) is **not** in biz_theme's `EXCEPTION_VARIANT`, so `odoo.exceptions.RedirectWarning`
     still renders stock.
  3. `WarningDialog` is instantiated **directly** (bypassing the registry) at
     `web/static/src/model/relational_model/relational_model.js:719` — titles "Odoo Warning" when no
     title is supplied.
  4. `error_service.js:117` contains a hardcoded, untranslated
     "An error whose details cannot be accessed by the Odoo framework has occurred." — **no existing
     seam reaches it** (not `_t()`, so `biz_debrand`'s translate patch cannot see it).
  5. `stripOdoo` (`biz_error_dialogs.js:212`) is applied only in `bizRpcFallbackHandler` (`:278-279`)
     and `bizDefaultHandler` (`:302-303`) — **not** on the registry-routed `UserError` path, which is
     exactly the path in the owner's screenshot. So even the *message* is unsanitised there.
  6. "Copy details" (`xml:56-59`) is gated on `hasDetails`, **not** `showTechnicalDetails` — it stays
     clickable for non-developers and copies `odoo.exceptions.UserError` to the clipboard.

### Build spec

**C1.1 — sanitise on every path.** Apply `stripOdoo` to the message (and to `exceptionName`/
`traceback` when they are shown at all) inside `BizErrorDialog` itself — in the `message` getter and
`technicalDetails` getter — so it no longer depends on which handler routed the error. That single
change fixes gap 5 for every registry-mapped exception.

**C1.2 — the non-developer view shows nothing technical.** Keep the developer-mode gate for the
expander (MF-C1 says developer mode may still see it) but ALSO gate **"Copy details"** on
`showTechnicalDetails`, not `hasDetails` (gap 6). A normal user must have no route — visible or
clipboard — to the raw payload.

**C1.3 — cover the frontend bundles (gap 1).** Add the error-dialog JS/XML/SCSS to
`web.assets_frontend` in `biz_theme/__manifest__.py` (mirror how `biz_debrand/__manifest__.py:34-41`
ships into both bundles). VERIFY the module's frontend assets do not drag in backend-only imports —
if `biz_error_dialogs.js` imports something backend-only, split the file rather than bloating the
frontend bundle. If splitting proves messy, the acceptable alternative is a small frontend-only
patch module of the stock `ErrorDialog` that (a) strips the vendor word from the title and (b)
suppresses the technical block unless `odoo.debug`. Choose one, justify it in the report.

**C1.4 — close gaps 2 and 3.** Register `odoo.exceptions.RedirectWarning` in biz_theme's
`EXCEPTION_VARIANT` (variant `attention`), ensuring the redirect button/action still works —
`RedirectWarningDialog` carries an extra action button, so either extend `BizErrorDialog` to render
it or leave that class registered but patch its title + suppress technicals. Whichever you choose,
the redirect action must still function; test it. For gap 3, patch `WarningDialog.prototype`
(title-only, same idiom as the existing `CoreErrorDialog` patch at `biz_error_dialogs.js:217-222`)
so a title-less direct instantiation never reads "Odoo Warning".

**C1.5 — gap 4.** Patch the `error_service` message or the string at the point it is displayed so the
hardcoded framework sentence is debranded. If patching the service is invasive, the pragmatic route
is to sanitise in `BizErrorDialog`/the handlers (C1.1 already strips it if that text arrives as the
dialog message). Verify by triggering a third-party-script error in developer mode, or state plainly
in the report that it is unreachable in practice and why.

**C1.6 — regression guard.** Add a small JS test (hoot, if the suite exists in biz_theme) or a
scripted Chrome-MCP assertion that with `odoo.debug` falsy: the technical block is absent, "Copy
details" is absent, and no rendered text matches `/odoo/i`.

## Part 2 — Primary Key guard (MF-C2)

- Field rendered at `pb_hr_payroll_formula/wizards/multisheet_wizard_views.xml:71-74`, inside
  `<div invisible="state != 'select_sheets'">`; field def at
  `wizards/multisheet_import_wizard.py:128-131`; the raise at `:544-545` inside
  `action_process_sheets` (`:524`), fired by the "Select Columns" button
  (`multisheet_wizard_views.xml:391-394`).
- **Fix**: add `required="1"` to the view field (not to the Python field — the wizard's other steps
  must not demand it). Because the surrounding div is `invisible` on other steps, the web client
  skips required-validation there, and `type="object"` buttons save first — so the guard bites
  exactly on the Select Worksheets step and nowhere else. Use the state-conditional form
  `required="state == 'select_sheets'"` if the plain form misbehaves on the later steps; test both
  ways round-trip (Back from Review must not be blocked — note COLROLES CR28 added `perm_unlink`
  for exactly that Back path).
- **Keep the server raise** as the backstop for RPC callers.
- Improve the placeholder/help so the requirement is legible before it bites: the field's `help`
  (`:130`) is decent; make sure the "Important" callout at `multisheet_wizard_views.xml:157-164`
  still reads true.

## Numbered test cases

1. Developer mode OFF, backend: trigger a `UserError` (e.g. the Primary Key raise via RPC) — dialog
   shows the plain sentence; NO technical block; NO "Copy details"; no occurrence of the vendor word
   anywhere in the dialog DOM.
2. Developer mode ON, backend: technical block IS available (MF-C1), and its content is stripped of
   the vendor word by C1.1.
3. Frontend/portal (logged-out or portal user): trigger an error on a `web.assets_frontend` page —
   assert the same as test 1 (this is the gap-1 fix; state clearly in the report how you triggered it).
4. `RedirectWarning`: raise one; the dialog is debranded AND the redirect button still performs its
   action.
5. `WarningDialog` direct path: force a relational-model warning without a title; the title is not
   "Odoo Warning".
6. Grep the built assets or the source for user-visible occurrences: no new string contains "Odoo".
7. Primary Key: on Select Worksheets with the field empty, clicking "Select Columns" is blocked
   client-side with the standard required-field indication and **no error dialog appears**.
8. With the field filled, the wizard proceeds exactly as before (full import still works end-to-end).
9. Back-navigation from later steps still works (CR28 regression).
10. Server-side raise still fires when `action_process_sheets` is called over RPC with an empty
    primary key (backstop intact).

## Deploy + live verification

1. Local: JS parse (.mjs copy + `node --check`), XML parse, SCSS compile (`npx sass`), python compile.
2. Manifest bumps: `biz_theme` (currently 19.0.1.3.0 — verify) and `pb_hr_payroll_formula` (verify
   current after Phase A/B). Asset-bundle changes REQUIRE the `-u`.
3. Deploy per ledger ritual to abm acme payobook payobook_template — chmod, sentinel, **psql
   `latest_version` on all four**, restart, port bound.
4. Chrome-MCP (park other tabs on `about:blank` first — CR20):
   - abm: reproduce the owner's exact scenario — open the multisheet import, reach Select Worksheets,
     leave Primary Key empty, press "Select Columns" → screenshot showing the field-level block and
     NO dialog.
   - Toggle developer mode off, trigger a UserError, screenshot the clean dialog.
   - Load a frontend/portal page and trigger an error there; screenshot.
5. Self-review diff vs spec; ONE feature-scoped commit (include ledger + this handover), no push.
6. Update `MAPFIX_LEDGER.md` with a programme-complete status line.

## Report back

Per-test results with screenshots; which approach you took for C1.3 (frontend bundle vs patch
module) and why; whether gap 4 (`error_service` hardcoded string) was fixed or judged unreachable;
deviations; MF-numbered gotchas appended; files touched; manifest versions; commit hash. Finish with
a 5-line programme wrap for MAPFIX (codes, mapping, errors) written for the owner.
