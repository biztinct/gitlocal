# ERRORS · Phase E2 — The six remaining leaks

**Read `docs/ERRORS_CONVENTIONS.md` first** (ER1–ER13, binding, not restated here) and
`docs/handovers/ERRORS_E1_BREAKDOWN_SCREENS.md` for what already shipped (`biz_errors`
19.0.1.0.0, commit `4ed69bb1`, installed on all six databases).

E1 made the breakdown *page* ours. E2 closes the six places a failure can still reach a person
unbranded, unhelpful, or carrying technical detail. Each is independent; do them in order, commit
each one separately (standing `commit-per-feature` rule), and do not let a hard one block the rest.

**Brand note:** `rize` now carries `biz_debrand.brand_name = Rize`,
`brand_website = https://rize.payobook.com`, `theme_color = #CC9900` (set 2026-09-11). `payobook`
and `abm` say `Payobook`. `payobook_template`, `p9clone` and `rztest` are still the `BizApp`
placeholder — leave them, they are not customer-facing.

---

## E2-1 — Session expiry on the portal gets a plain pop-up, not the calm screen

**Verified mechanism.** `web/static/src/core/errors/error_handlers.js:52` checks the
`error_notifications` registry **before** `error_dialogs`:

```js
if (errorNotificationRegistry.contains(exceptionName)) {
    const notif = errorNotificationRegistry.get(exceptionName);
    env.services.notification.add(notif.message || originalError.data.message, notif);
    return true;                       // <- the dialog registry is never consulted
}
```

`web/static/src/public/error_notifications.js` puts three keys in that registry:
`odoo.http.SessionExpiredException`, `werkzeug.exceptions.Forbidden` and `504`. `biz_theme` claimed
all three in `error_dialogs` with `{force: true}`, so on the portal its work is simply skipped — and
its own `hasSpecificHandling()` (`biz_error_dialogs.js:311`) then stands down for exactly these
names, because it sees them in the notification registry.

**Fix.** In `biz_theme/static/src/js/biz_error_dialogs.js`, remove those three keys from
`error_notifications` so the dialog registry wins. `BizErrorDialog` already has the right variants
(`session` → *"Your session ended"* with a **Sign in again** button, `timeout` → *"This is taking
longer than expected"*), so there is nothing new to design. Keep `hasSpecificHandling()` working for
every OTHER notification key — narrow the removal to these three by name, never clear the registry.

**Watch for:** asset ordering. Our file must evaluate after core's. If it does not, handle it rather
than hoping — re-check membership lazily inside the handler instead of at module load.

**Tests.** Force each of the three server-side on a portal page and assert the calm dialog appears
and no notification does. Assert the other error-notification keys still notify.

## E2-2 — A Vietnamese string that names the vendor where the English does not

**Verified.** `biz_debrand/models/translate_patch.py:42`:

```python
if not source or not HAS_ODOO_RE.search(source):
    return original(module, lang, source, args)
```

The pre-filter reads the **English source**. A catalogue entry whose translation names the vendor but
whose msgid does not never reaches the rewrite. Two live cases, both `calendar`'s Vietnamese
catalogue, both settings prose:

| msgid | msgstr |
|---|---|
| `Synchronize your calendar with Google Calendar` | `Đồng bộ lịch của bạn trên Odoo với Lịch Google` |
| `Synchronize your calendar with Outlook` | `Đồng bộ lịch của bạn trên Odoo với Lịch Outlook` |

**Fix.** In the `lang != 'en_US'` branch, resolve the catalogue entry first and test the **result**,
not the source. The lookup it needs is already written two lines below:
`tr_mod.code_translations.get_python_translations(module, lang)` — a cached dict, so this is a dict
`get`, not a query. Keep the `en_US` branch exactly as it is: there is no catalogue, the msgid is the
output, and the existing pre-filter is both correct and the hot path.

**Tests.** A unit test on the patch for the msgid/msgstr pair above; a test that an en_US string is
untouched and takes the fast path; a test that a clean string in both languages is returned as the
same object (the no-op contract in `brand.py:70`).

## E2-3 — Raw failure text pasted into on-screen toasts

**Verified.** 64 call sites across 15 files in `pb_hr_payroll_analytics` and `pb_hr_payroll_base`
build `_('Error: %s') % str(e)` and hand it to `display_notification`. The `_()` seam debrands the
**template** and never the interpolated argument — deliberately, so a record genuinely named
"Odoo Ltd" survives (`translate_patch.py` docstring, `brand.py:186`).

**Do not edit the 64 sites.** Both modules are legacy (memory `payobook-current-design`) and 64
hand-edits is churn that fixes today only. Add a **third global JS seam** to
`biz_debrand/static/src/js/biz_debrand_runtime.js`, beside the two already there: wrap the
notification service so every message and title passes through `debrandText()` on the way to the
screen. One change, covers all 64, every future one, and the `error_notifications` messages too.

The file already documents its seams in the header comment — extend that comment, do not bolt the
new one on silently. Both bundles (`web.assets_backend` and `web.assets_frontend`) already carry the
file, so no manifest change.

**Watch for:** a notification message may be a `Markup`/`String` subclass carrying escaped HTML.
`debrandText` already returns non-strings untouched (`biz_debrand_runtime.js:77`) — mirror the same
guard the `valueOf` patch uses at line 111, do not flatten markup into a plain string.

**Tests.** A JS unit test that a notification whose message names the vendor is rewritten, that a
clean one is untouched, that a markup message is not flattened, and that the notification still
renders when the service is called with the `(message, options)` shape **and** the options-only
shape.

## E2-4 — The spreadsheet's own support line

`spreadsheet/static/src/o_spreadsheet/o_spreadsheet.js:17` carries *"An unexpected error occurred.
Submit a support ticket at odoo.com/help."*

**Verify before fixing — it may already be half-handled.**
`spreadsheet/static/src/o_spreadsheet/odoo_module.js:12` calls
`spreadsheet.setTranslationMethod(_t, …)`, so the library's strings DO go through Odoo's `_t`, which
our `TranslatedString.prototype.valueOf` patch covers. If so, the current output is
*"Submit a support ticket at rize.payobook.com/help"* — a URL that does not exist, which is worse
than the honest fix.

So: check what it actually renders today, then **replace the sentence**, do not rewrite its domain.
Wording to match the rest of the family: *"Something went wrong on our side. If it keeps happening,
let your administrator know."* Implement as a targeted override from our own module —
**never edit `spreadsheet/`**, it is a vendored standard addon and the deploy contract forbids
shipping our copies of those (`CLAUDE.md`).

If no clean override seam exists, say so and leave it; do not fork the library.

## E2-5 — An unknown web address shows a pre-database page naming the vendor

**Verified.** A request whose `Host` no database matches gets werkzeug's *"No database is selected
and the requested URL was not found in the server-wide controllers … Alternatively, use the
X-Odoo-Database header."* It is served before any database is chosen, so **no module can reach it**
(confirmed independently during E1's test run).

Current nginx (`/etc/nginx/sites-enabled/`): `_` (`payobook.com`), `pb-wildcard`
(`*.payobook.com`), `pb-tenant-abm.payobook.com.conf`, `pb-tenant-rize.payobook.com.conf`. **No
`default_server`, no `error_page` anywhere.** So an unmatched host falls to the first block and
reaches Odoo; a mistyped *tenant* (`riez.payobook.com`) matches the wildcard and reaches it too.

**Fix, in two parts. The second is the one that matters.**

1. A `default_server` block for a host outside `payobook.com` entirely: redirect to
   `https://payobook.com`. Cheap and safe.
2. A mistyped tenant subdomain: it matches `*.payobook.com` today. Serve a small branded static page
   — *"There's no workspace at this address"* with a link to the main site — instead of passing it to
   Odoo. Drive it from the known-tenant list rather than hard-coding: `pb_tenants/tools/pb-domain-attach`
   and `pb-domain-detach` are the existing precedent for how tenant nginx config is written on this
   box, so follow their shape and their file locations.

**Safety rails, non-negotiable.** This is live infrastructure serving real customers.
`sudo nginx -t` before every reload, never `restart`. Keep a timestamped copy of every file you
touch and state the exact rollback command in your report. After the reload, confirm
`payobook.com`, `rize.payobook.com` and `abm.payobook.com` all still answer 200 **before** you move
on. If `nginx -t` fails, roll back immediately and report — do not iterate on a live config.

## E2-6 — A permission failure while drawing a public page escapes the handler entirely

**Verified (ledger ER12, found during E1).**
`http_routing/models/ir_http.py._handle_error` guards the fallback with one clause only:

```python
if code in (404, 403):
    try:
        response = cls._serve_fallback()
        ...
    except werkzeug.exceptions.Forbidden:
        pass
```

An `odoo.exceptions.AccessError` raised inside `_serve_fallback()` is not a
`werkzeug.exceptions.Forbidden`, so it propagates out of `_handle_error` before E1's
`_get_error_html` seam is ever reached. The visitor gets werkzeug's bare 403 carrying the ORM's own
message, model name included: *"You are not allowed to access 'System Parameter'
(ir.config_parameter) records."*

**Fix.** Extend `biz_errors/models/ir_http.py` with an override of `_handle_error` that calls
`super()` inside a try/except, and on an escape renders E1's own 500/403 breakdown page — same
reference code, same logging, same wording.

**Scope it tightly.** Only when `request.is_frontend` is true, and only re-raise-free for exceptions
that reach this point — a blanket catch here would swallow backend JSON-RPC behaviour the web client
depends on. Read E1's `_biz_error_values` and reuse it rather than duplicating the reference and
brand logic.

**Tests.** A frontend route that raises `AccessError` must answer a branded breakdown page with a
reference, no model name, no `ir.config_parameter`, no vendor word. A backend JSON-RPC route that
raises `AccessError` must still return the normal JSON error the client expects — assert that
explicitly, it is the thing most likely to break.

---

## Report back

In this order, plainly:

1. Each of E2-1 … E2-6: done, partly done, or not done, one line, with the reason for anything short
   of done.
2. Test results per item, and the full-suite verdict line (`odoo.tests.result: …`) for every module
   you touched.
3. The six databases: module versions vs `latest_version`, and content hashes.
4. For E2-5 specifically: the `nginx -t` output, the exact rollback command, and the three
   post-reload status codes.
5. Screenshots, in `docs/handovers/errors_e2_shots/`. Chrome MCP is pre-approved; start the server
   yourself if it is down rather than skipping the check.
6. New gotchas, written as `ER14`+ entries ready to paste into `docs/ERRORS_CONVENTIONS.md`.
7. Anything you could not finish, named explicitly. Do not quietly narrow the scope.

One commit per item, explicit file staging, **do not push**.
