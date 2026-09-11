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
