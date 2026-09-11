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

## ER18 — `AccessError` IS a `UserError`, so ER6's gate lets an ORM message through

`odoo.exceptions.AccessError` subclasses `UserError`. ER6's rule — *keep
`error_message` only when the exception is a `UserError`* — therefore keeps the
ORM's own sentence, model name included:

> You are not allowed to access 'System Parameter' (ir.config_parameter) records.

Which is precisely the string ER12's escape hatch was leaking. So when a
breakdown page is built for an exception we caught ourselves (rather than one
`_get_exception_code_values` shaped), **do not put the exception in
`values['exception']`** and do not set `error_message`. Hand
`_biz_error_values` a values dict with neither, and it has nothing to leak.

## ER19 — a translated string that names the vendor is usually a VIEW TERM, not a code string

The two Vietnamese cases named in the E2 handover —

```
Synchronize your calendar with Google Calendar
    -> Đồng bộ lịch của bạn trên Odoo với Lịch Google
```

— are **not** code translations. Their `.po` entries are marked
`#: model_terms:ir.ui.view,arch_db:calendar.res_config_settings_view_form`: they
are view-arch terms, stored in `ir_ui_view.arch_db`'s per-language JSON, and they
never pass through `tools.translate.get_translation` at all. The QWeb tree walker
(`biz_debrand/models/ir_ui_view.py`) already rewrites them — verified live on
`rize`, where the rendered `vi_VN` arch reads *"Đồng bộ lịch của bạn trên **Rize**
với Lịch Google"*.

So before attributing a translated leak to a seam, read the `#:` marker above the
msgid:

| Marker | Seam that owns it |
|---|---|
| `#. odoo-python` / `code:addons/**.py` | `translate_patch.py` |
| `#. odoo-javascript` / `code:addons/**.js` | `TranslatedString.prototype.valueOf` (JS) |
| `model_terms:ir.ui.view,arch_db:` | the QWeb tree walker |
| `model:ir.model.fields,field_description:` etc. | the data scrub |

A sweep of every installed module's `vi.po` on this build finds **zero**
`odoo-python` entries whose msgid is clean and whose msgstr names the vendor, and
one `odoo-javascript` entry (`google_calendar`) that the JS seam already covers.
E2-2's Python fix is a rail against a future catalogue, not a visible change
today — say so rather than claiming a screen changed.

**Still open (found here, not fixed):** the rendered `vi_VN` arch of the Settings
page keeps one vendor reference, `help="Cho phép người dùng đăng nhập/xuất từ
Odoo."` (hr_attendance), although `debrand_text` rewrites that exact string
correctly when called directly. The walker is not reaching that particular view.
Candidate for E3.

## ER20 — `web_debranding`'s word rule refuses a sentence that ENDS in the vendor name

Its generic rule (`web_debranding/models/ir_translation.py:56`) is

```python
re.sub(r"\b(?<!\.)odoo(?!\.\S|\s?=|\w|\[)\b", new_name, source, flags=re.IGNORECASE)
```

The `(?!\.\S)` guard was written to protect the JS namespace (`odoo.define`).
It also rejects **any sentence whose last word is the vendor name**, because the
character after the full stop then only has to be non-whitespace. Inside a view
arch that character is always `<`.

Measured on `rztest` 2026-09-11, the same function, the same brand:

| input | output |
|---|---|
| `Cho phép người dùng đăng nhập/xuất từ Odoo.` | `…từ BizApp.` ✅ |
| `Cho phép người dùng đăng nhập/xuất từ Odoo.</span>` | **unchanged** ❌ |

That one character is the whole of the E3-1 bug: the Vietnamese Settings page.
Its `(?!\w)` guard refuses `OdooBot` for the same kind of reason, which is why
`res.users.odoobot_state` was still labelled `Trạng thái OdooBot`.

**Never widen that regex.** `web_debranding` is gutted, OPL-1 and not where
coverage goes. Layer `biz_debrand`'s canonical `debrand_text` on top of it —
the pre-filter makes the second pass free for everything the first already
fixed.

## ER21 — ask ER19's marker question BEFORE picking a seam, even when a table looks guilty

E3-1 was handed three candidate seams and the row counts that seemed to point at
`ir_model_fields` (37 `help` rows, 5 `field_description`). Both readings of that
evidence were wrong:

* the 37 `help` rows are **already clean** at runtime — 0 of them reach a
  tooltip naming the vendor, in either language;
* the sentence actually observed on screen was never an `ir_model_fields` row at
  all. It is `model_terms:ir.ui.view,arch_db:hr_attendance.res_config_settings_view_form`,
  `ir_ui_view` id 2009 — a view term, reaching the screen through `base.get_view`.

The two-minute check that settles it, before any code:

```sql
SELECT count(*) FROM ir_model_fields WHERE help::text ILIKE '%<the sentence>%';
SELECT id, name FROM ir_ui_view  WHERE arch_db::text ILIKE '%<the sentence>%';
```

## ER22 — the backend arch and server-rendered QWeb are two different seams

`ir.ui.view._get_view_etrees` (ER1, `biz_debrand/models/ir_ui_view.py`) is reached
only by `ir.qweb._preload_trees`, i.e. website, portal, reports and the webclient
shell. A **form / list / settings arch** never goes near it: it travels
`base.get_view` → `ir.ui.view._get_view_cache`, and core re-parses and
re-serialises it on every call (`ir_ui_view.py:3168-3171`), so a post-processing
override there costs a parse, not a second cache.

Both are needed and neither substitutes for the other. `biz_debrand/models/base.py`
is the second one.

## ER23 — a rule that can reach STORED ROWS must be opt-in per call site

`debrand_text` is shared by the runtime seams **and** by `scrub.py`, which
rewrites rows in place. The vendor rules are safe there because no customer is
called "Odoo". The product rule is not: a company genuinely named "Payobook
Vietnam JSC" is data, and renaming it is a silent corruption far worse than the
bug the rule exists to fix.

So the product name is an explicit fourth argument, defaulting to off, and the
question each seam must answer is **"could this string already carry an
interpolated record name?"** — not "is this seam at runtime?". That is why the
JS notification seam (E2-3) sits on the DATA side despite being a runtime seam:
by the time a message reaches `notificationService.add` it is finished prose
with `str(e)` and record names already in it.

Enabled (SOURCE): `translate_patch`, `ir_ui_view`, `base.get_view`,
`ir_model_fields`, `ir_module_module`, JS seams 1 and 2.
Off (DATA): `scrub.py`, JS seam 3, and `debrand_url` — `payobook.com` resolves
and a rewritten one would not.

`biz_debrand/tests/test_rewrite.py::TestProductRuleIsOptIn` reads the source of
each seam and fails if that line ever moves.

## ER24 — a blanket rule needs an author's opt-out, or one deliberate line turns it off

E3-2's product rule cannot tell two sentences apart. On a tenant's screen
"Welcome to Payobook" is the bug; "Powered by Payobook" in that same tenant's
footer is a deliberate statement about who built the platform, and rewriting it
to "Powered by Rize" is nonsense, not a fix. Without a hatch the only remedy for
one such line is turning the rule off for the whole database.

`data-biz-brand="keep"` on an element takes that element **and its subtree** out
of the walk, in both halves. Implementation notes that are easy to get wrong:

* Python: `element.iter()` is flat and cannot skip a subtree — `debrand_tree`
  walks an explicit stack instead.
* JS: the TreeWalker filter must return `NodeFilter.FILTER_REJECT`, not
  `FILTER_SKIP`. Only REJECT excludes the descendants.
* `tail` is the text after an element's CLOSING tag and belongs to the parent,
  so it is rewritten either way. The hatch covers the subtree, not the page
  after it.

## ER25 — node IS on this server, so the two halves of the rewrite can be tested against each other

ER15 stands for hoot: there is no chrome binary, so `.test.js` files never run
here. But `/usr/bin/node` is present (v18.19.1).

`biz_debrand_runtime.js` therefore carries sentinel comments
(`biz_debrand:rules:begin` / `:end`) around a region that is **pure** — no
imports, no DOM, no module state, just the rules and the two functions that
apply them. `tests/test_rewrite.py::TestPythonAndJavascriptAgree` slices that
region out, refuses it if it has stopped being import-free, runs it under
`node -e`, and compares the output to `brand.py`'s for every case in the shared
tables. "Keep the two in step" stops being a comment.

It tests the RULES, not the seams. It is not a substitute for a hoot suite and
must not be reported as one.

## ER26 — `web_debranding` substitutes a FULL URL where a bare host belongs (pre-existing, not fixed)

Found while measuring E3-2, present on every database, unrelated to this phase.

```python
# web_debranding/models/ir_translation.py:28
def debrand_links(source, new_website):
    return re.sub(r"\bodoo.com\b", new_website, source)
```

`new_website` is `web_debranding.new_website`, which `_biz_debrand_apply_brand`
seeds with the full `https://…` URL. So a vendor link in a backend arch comes
out with two schemes:

```
https://odoo.com/pricing        ->  https://https://payobook.com/pricing
placeholder="https://www.odoo.com"  ->  https://www.https://payobook.com
href="https://apps.odoo.com/…"  ->  https://apps.https://rize.payobook.com/…
```

Verified 2026-09-11 on both `payobook` and `rize`; 12 such URLs in the English
`res.config.settings` / `ir.module.module` / `payment.provider` / `res.company`
arches. They are all links to vendor services, so nobody has complained, but
they are broken URLs on a settings screen.

`biz_debrand`'s own `debrand_url` is correct — it strips the scheme with
`website_host()` first. The fix is therefore **not** to touch the gutted module:
either seed `web_debranding.new_website` with the bare host, checking its other
readers first, or collapse the two shapes in `biz_debrand/models/base.py`, which
already post-processes the arch. Left alone here because it is outside E3 and
the brand-parameter seeding has other consumers.
