# Breakdown screens — Conventions & Gotcha Ledger

The shared ledger every ERRORS-phase handover references. Rules here are **binding** for any
implementation session. When a new gotcha is hit during a build, add it here — do not restate
ledger content inside individual phase docs, link to the entry.

Sibling docs: `handovers/ERRORS_E1_BREAKDOWN_SCREENS.md` (E1) · `handovers/ERRORS_E2_REMAINING_LEAKS.md` (E2).

Standing rules that also bind this programme: **no vendor name in any user-visible string**
(`CLAUDE.md`, white-label rule) and the **design mandate** — extreme WOW, intuitive,
out-of-this-world, best in class; hero moment, zero dead-ends, plain language, purposeful motion,
Lucide not emoji.

---

## ER1 — The frontend breakdown pages are the ONE surface no debranding seam reaches

`biz_debrand` has five seams and none of them touch a crash report:

| Seam | File | Why it misses |
|---|---|---|
| Python `_()` patch | `biz_debrand/models/translate_patch.py` | A traceback is not a translated string |
| QWeb tree walker | `biz_debrand/models/ir_ui_view.py` → `_get_view_etrees` | Rewrites **static template text only**. The crash arrives through `t-esc="traceback"`, a `t-` attribute the walker skips by design (`brand.py:204`), inside `<pre>`, which is in `OPAQUE_TAGS` (`brand.py:176`) |
| JS `_t()` patch | `biz_debrand/static/src/js/biz_debrand_runtime.js` | Server-rendered page, no JS involved |
| Data scrub | `biz_debrand/models/scrub.py` | Scrubs stored rows; a traceback is minted at the moment of the failure |
| Apps-list `read()` | `biz_debrand/models/ir_module_module.py` | Unrelated surface |

Both skips are **correct** and must not be relaxed: the walker must never rewrite `t-` expressions
(it would break the render) and must never rewrite `<pre>`/`<code>` (help panels quote real Python,
`from odoo import models`, which the generic word rule would turn into code that does not run).

**So the fix is never "extend a seam". It is to stop putting the crash on the page.**

## ER2 — `editable or debug` is the gate, and only half of it is already railed

`http_routing/views/http_routing_template.xml` wraps every technical block in
`<t t-if="editable or debug">`.

* `debug` — already held. `biz_theme/models/ir_http.py` clears `request.session.debug` for anybody
  who is not a system administrator (`_handle_debug`, line 156) and clears it again at render time
  (`ir.qweb._prepare_environment`, line 291). Confirmed on this build. Do not rebuild it.
* `editable` — **not railed**. `website/models/ir_http.py:393` sets it from
  `website.group_website_designer`. The brand owner is in that group, which is why the owner met a
  raw traceback on `/my/buddy` on 2026-09-11 and an ordinary member of staff did not.

## ER3 — The 500 template may not load assets, and the reason is not style

The core template carries a shouted comment (`http_routing_template.xml:194-198`):

> This template should not use any variable except those provided by
> `http_routing.ir_http._handle_exception` — no `request.crsf_token`, no theme style, no assets,
> **cursor can be broken during rendering**.

It is a standalone `<html>` document, not a `web.frontend_layout` call, for exactly that reason. So
a branded 500 page is **inline `<style>` and inline `<svg>` only**. No `/web/assets/…`, no Lucide
bundle, no `<img src="/web/image/…">` (that is a DB read), no `website.layout`.

The **4xx** family is different — `400`, `403`, `415`, `422`, `4xx`, `404` and `http_error` all call
`web.frontend_layout`, so they already carry the site's own header, footer and assets. Only their
wording and their debug block need work.

## ER4 — Inject values in `_get_error_html`, never in `_get_exception_code_values`

`http_routing/models/ir_http.py._handle_error` (line ~572) runs in this order:

```
code, values = cls._get_exception_code_values(exception)   # <- transaction may still be ABORTED
request.env.cr.rollback()                                  # <- the cursor becomes usable here
if code in (404, 403):  ... _serve_fallback()
elif code == 500:       values = cls._get_values_500_error(...)
code, html = cls._get_error_html(request.env, code, values)
```

An `ir.config_parameter` read inside `_get_exception_code_values` can raise
`InFailedSqlTransaction`, because the exception being handled may have aborted the transaction and
the rollback has not happened yet. `_get_error_html` runs **after** the rollback and is reached by
**every** status code, so it is the single correct seam for injecting the brand, minting a support
reference and blanking the technical values.

Wrap it all in try/except regardless. A branding failure must never turn a handled 400 into an
unhandled crash.

## ER5 — A support reference replaces the traceback, it does not hide it

The owner's ruling (2026-09-11): **nobody sees technical detail on screen, including the owner.**
That only works if support can still get at it, so every breakdown page mints a short reference,
prints it on screen, and logs it beside the full traceback at ERROR level. One grep in the server
log turns the code the customer read out into the stack.

Reference format: 8 characters, Crockford base32 (no `I`, `L`, `O`, `U`), grouped `XXXX-XXXX`.
Unambiguous when read aloud over a phone.

## ER6 — `UserError` text is for humans, everything else is not

`_get_exception_code_values` fills `error_message` from two very different places
(`http_routing/models/ir_http.py:535,538`):

* `exceptions.UserError` → `exception.args[0]`, a sentence somebody wrote for a person. **Keep it.**
* `werkzeug.exceptions.HTTPException` → `exception.description`, generic English framework prose.
  Replace it with our own wording.

Anything else leaves `error_message` unset. Never fall back to `str(exception)` — that is how a
Python repr reaches a payroll officer.

## ER7 — HttpCase on this platform needs `--db-filter=.*`

The dbfilter here is hostname-based (DB-per-tenant SaaS). Without the override every `url_open` in
an `HttpCase` answers 404 with *"No database is selected and the requested URL was not found in the
server-wide controllers"* and the log says `dbfilter rejects it; logging session out`. Cost one
wasted run on 2026-09-11.

```
sudo -u odoo /odoo/odoo-server/odoo-bin -c /etc/odoo-server.conf -d rztest \
  -u <module> --test-enable --test-tags /<module> --stop-after-init \
  --max-cron-threads=0 --http-port=8199 --gevent-port=8198 '--db-filter=.*' \
  --logfile=/tmp/<name>.log
```

`--logfile` is required to read the result: `logfile` is set in `/etc/odoo-server.conf`, so without
it the test output goes to `/var/log/odoo/odoo-server.log` and **nothing useful reaches stdout**.
Read the verdict from the `odoo.tests.result: N failed, N error(s)` line — a stale earlier run in
the same log file will otherwise be mistaken for this one.

## ER8 — All portal controllers share ONE namespace

`odoo/http.py` merges every `CustomerPortal` leaf subclass into a single class,
`type(name, tuple(reversed(leaf_controllers)), {})`. A helper on a portal controller is therefore
**not private to its module**: the module registered last wins and silently replaces every
same-named helper before it — no error, no log line.

Prefix every portal helper with its module (`_ob_card`, `_rnr_card`, `_pay_ess_employee`). The rule
is enforced by `pb_me_portal/tests/test_portal_helper_names.py`, which reads the live class tree and
the live module graph and exempts only a name where one module actually depends on the other.

This is what took `/my/journey`, `/my/buddy` and `/my/orgchart` down on all six databases on
2026-09-11 (commit `c9f96da8`) and is how the owner met the raw traceback in the first place.

## ER9 — Databases and deploy

Six databases, all carrying the same module set: `payobook`, `payobook_template`, `abm`, `p9clone`,
`rize`, `rztest`. A new module must be installed on **every** one (standing tenant rule: tenants get
every module the master gets, except `pb_tenants`/`pb_demo`/`pb_demo_portal`/`pb_website`).

Deploy contract is in `CLAUDE.md`: one addons directory, `/odoo/odoo-server/addons`; clean the
staging dir first; `--delete` is scoped to a single module directory and **never** to the addons
root. Verify both file content **and** `ir_module_module.latest_version` per database.

## ER10 — Blank `debug` to `''`, never to `False`

`debug` is a **string** of comma-separated flags everywhere in the platform
(`'1'`, `'assets'`, `'tests,assets'`, `''`). Templates ask membership questions
of it: `web.conditional_assets_tests` is literally
`<t t-if="'tests' in debug or test_mode_enabled"/>`.

Setting `values['debug'] = False` to shut the technical block therefore raises
`TypeError: argument of type 'bool' is not iterable` inside
`web.frontend_layout`, which takes down the whole 4xx family — and the failure
surfaces as *"Couldn't render a template for http status 422"* followed by the
418 fallback, which looks nothing like the real cause. Cost one test run on
2026-09-11 (E1). Use `''`. `editable = False` is fine; only `debug` is a string.

## ER11 — An undefined name in a QWeb expression is falsy, not an error

Verified on this build: `<t t-esc="nosuchvar"/>` renders nothing and
`<t t-if="nosuchvar">` is false. No `NameError`, no `QWebException`.

This is what makes it safe for a replaced core template to reference values that
only one of its callers injects. `http_routing.http_error` is rendered directly
by `account/controllers/terms.py` and `website_forum` with nothing but
`status_code`/`status_message`, and by `_handle_error`'s 418 fallback with the
full error values; one template body can serve both, and `brand_home or '/'`
quietly becomes `/` when nobody set it.

## ER12 — An `AccessError` raised while rendering a website page escapes the handler

`http_routing.ir_http._handle_error` wraps its `_serve_fallback()` call in
`except werkzeug.exceptions.Forbidden`. When the original failure was an
`odoo.exceptions.AccessError` raised *during the page render*, the fallback
re-renders the same page, raises `AccessError` again — which that clause does
**not** catch — and the exception leaves `_handle_error` entirely. The visitor
gets werkzeug's bare `403 Forbidden` document carrying the ORM's own message,
including the technical model name: *"You are not allowed to access 'System
Parameter' (ir.config_parameter) records."*

No module-level seam can reach this: our `_get_error_html` is never called. It is
stock behaviour, unchanged by E1, and it is the remaining hole in the breakdown
programme. Reproduced on 2026-09-11 with a website page whose arch reads a
restricted model. Candidate for E2.

## ER13 — A shell write is not visible to the running server until it is

`odoo-bin shell` in a second process commits fine, but the running server keeps
serving the old compiled QWeb template: a `website.page` whose view arch and
`visibility` had both been rewritten still answered with the previous render,
and busting the URL with a query string changed nothing. `systemctl restart
odoo-server` made it correct immediately. When a shell edit "did not take",
restart before you go looking for a bug.

## ER14 — `error_notifications` holds far more than the three obvious keys

`web/static/src/public/error_notifications.js` looks like three registrations
(`odoo.http.SessionExpiredException`, `werkzeug.exceptions.Forbidden`, `504`),
but its first statement is:

```js
odooExceptionTitleMap.forEach((title, exceptionName) => {
    registry.category("error_notifications").add(exceptionName, {...});
});
```

`odooExceptionTitleMap` (`web/static/src/core/errors/error_dialogs.js:30`) holds
nine more — `AccessError`, `AccessDenied`, `UserError`, `ValidationError`,
`MissingError`, `MissingActionError`, `ServerActionWithWarningsError`,
`MailDeliveryException`, `Warning`. Since core's `rpcErrorHandler` consults
`error_notifications` **before** `error_dialogs` and returns on a hit, **every**
`BizErrorDialog` variant was shadowed on the portal and the website, not just
the session one.

Two consequences, both binding:

* the removal must cover every name `biz_error_dialogs.js` claims, not three;
* it must be **by name**. `MailDeliveryException` is in that map but is not one
  of ours; clearing the registry would steal a presentation we never designed.

The file is bundled into `web.assets_frontend` only — `web/__manifest__.py:238`
adds `web/static/src/public/**/*.js`, and `web.assets_unit_tests:462` removes
this one file explicitly. So the backend never had the bug, and a hoot test
cannot assert on the registry's real frontend contents: it must assert on the
*behaviour* (does our fallback handler take this error, or stand down).

## ER15 — hoot JS unit tests cannot run on this server

There is no `chromium` / `google-chrome` binary on `Payobook19v2`, so
`HttpCase.browser_js`, `/web/tests` and therefore the whole `web.assets_unit_tests`
suite have nothing to run in. A `.test.js` file added to `web.assets_unit_tests`
is written, deployed and never executed here.

So a JS behaviour needs **two** proofs on this platform:

1. a Python test for the plumbing the JS depends on — is the file in the bundle,
   is it in the right order, is the seam still in the source (`ir.asset._get_asset_paths`
   answers the first two); and
2. a Chrome MCP pass against the live site for the behaviour itself.

Neither substitutes for the other. Do not report a hoot suite as "passing".

## ER16 — `--db-filter=.*` fails four unrelated tests, and they are not yours

ER7's override is required, and it has a side effect: with more than one
database visible, `/web/login` and `/web/database/manager` answer the **database
selector**, not the page the test expects. On this build that reliably fails:

| Test | Why |
|---|---|
| `biz_theme … TestTheBlockRuns.test_the_rail_is_armed_by_default` | selector page has no `debug: "…"` marker |
| `biz_theme … TestTheBlockRuns.test_the_switch_stands_the_rail_down` | same |
| `biz_theme … TestTheBlockRuns.test_asking_for_developer_mode_without_being_anybody_gets_nothing` | same |
| `biz_debrand … TestBizDebrandHttp.test_database_manager_debranded` | fails **with or without** the flag — see below |

Re-run the first three **without** `--db-filter=.*` before blaming a change.

`test_database_manager_debranded` is a genuine, pre-existing leak: the database
manager page is rendered before a database is chosen, so none of `biz_debrand`'s
five seams can reach it and its `<title>odoo</title>` stands. It is unreachable
in production — `location ^~ /web/database/ { return 404; }` is in every server
block — so it is logged here rather than fixed.

## ER17 — nginx ignores a server-level `error_page` for a server-level `if … return`

Verified on nginx 1.24.0 (Ubuntu), on this box, at the cost of two reload cycles.

```nginx
server {
    if ($pb_workspace = 0) { return 418; }
    error_page 418 =404 /_pb_no_workspace;   # NEVER CONSULTED
    location = /_pb_no_workspace { internal; alias /var/www/...; }
}
```

The visitor gets a bare `418` — and with `return 404` + `error_page 404` at the
same level, nginx's own grey *"404 Not Found"*. The `if` at server level runs in
the rewrite phase, before location selection, and the config it finalises the
request against does not carry the server block's `error_page`.

**The guard and its `error_page` must sit in the SAME `location` block:**

```nginx
location / {
    error_page 404 /_pb_no_workspace;
    if ($pb_workspace = 0) { return 404; }
    proxy_pass http://127.0.0.1:8069;
}
```

Which also means the guard has to be repeated in every location that proxies —
here `location /` and the `*/static/` regex. `proxy_intercept_errors` is off by
default, so the `error_page` only ever sees the `return 404` on the line below
it and never a 404 the application itself produced.
