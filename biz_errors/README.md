# biz_errors — the branded breakdown screen

Engineering notes. The user-facing rule (no vendor name on a screen) does not
apply to this file: Odoo is named here because engineers read it.

## What it does

Replaces every server-rendered error page in `http_routing` with one calm,
branded, plain-English design, and replaces the Python traceback with a short
support reference that is also written to the server log.

| Template | After |
|---|---|
| `http_routing.500` | self-contained branded page, no assets |
| `http_routing.4xx` / `.400` / `.403` / `.415` / `.422` / `.http_error` | branded card inside `web.frontend_layout` |
| `http_routing.http_error_debug` | renders nothing |
| `http_routing.error_message` | plain sentence, `UserError` text only |
| `http_routing.404` | **untouched** — the website's own 404 is already branded |

## Where the work happens

`models/ir_http.py` overrides exactly one method, `ir.http._get_error_html`.

That is the only safe seam. `_get_exception_code_values` runs **before**
`request.env.cr.rollback()` in `http_routing.ir_http._handle_error`, so an
`ir.config_parameter` read there can raise `InFailedSqlTransaction` — the
exception being handled may itself have aborted the transaction.
`_get_error_html` runs after the rollback and is reached by every status code.

The override:

1. mints an 8-character Crockford base32 reference, grouped `XXXX-XXXX`;
2. logs it at ERROR beside the full traceback — `grep 'biz_errors \[H4K9-2PQR\]'`
   turns a code a customer read out into the stack that produced it;
3. blanks `traceback`, `qweb_exception` and `exception`, and forces `editable`
   and `debug` to `False` so a template we did not replace still cannot open the
   technical block;
4. keeps `error_message` only when the original exception is an
   `odoo.exceptions.UserError` — that text is a sentence somebody wrote for a
   person. A `werkzeug` `description` is generic framework prose and is dropped.
   `str(exception)` is never used;
5. adds `brand_name`, `brand_color`, `brand_home` and `error_ref`.

Everything is inside `try/except`. A breakdown page that itself breaks is
unrecoverable, so a failure here logs a warning and renders the stock page.

404 (and website's `'page_404'` / `'protected_403'` pseudo-codes) are skipped
outright: the website 404 page is already branded and is not ours to touch.

## Why a separate module

`biz_theme` deliberately depends on `['web', 'base']` only, and a hard
`http_routing` dependency there would drag the website stack onto every future
consumer of the base theme. `biz_errors` stays portable: it reads
`biz_debrand.brand_name` / `web_debranding.new_name` through
`ir.config_parameter` rather than importing `biz_debrand`, and falls back to the
company name and then to a neutral phrase — never to a vendor name.

## Templates

Every user-visible sentence lives in `biz_errors.breakdown_card` and nowhere
else, selected by a `bze_variant` string (`crash`, `access`, `filetype`,
`request`, `generic`). One view means one translation reference and one place to
change the wording.

The 500 page may not use `web.frontend_layout` and may not load an asset bundle
— see the shouted comment on `http_routing.500`: it renders while the request is
already in trouble. So the stylesheet is inline and the Lucide icons are drawn
inline as SVG path data.

## Tests

`tests/error_routes.py` registers `/biz_errors/test/…` endpoints that fail on
demand. They live inside the tests package, which only the test loader imports,
so they never reach a live route table. `setUpClass` calls
`registry.clear_cache('routing')` because another module's `HttpCase` may
already have built and cached the routing map before this package was imported.

Run them with both overrides or they will lie to you:

```
sudo -u odoo /odoo/odoo-server/odoo-bin -c /etc/odoo-server.conf -d rztest \
  -u biz_errors --test-enable --test-tags /biz_errors --stop-after-init \
  --max-cron-threads=0 --http-port=8199 --gevent-port=8198 '--db-filter=.*' \
  --logfile=/tmp/biz_errors.log
```

Without `--db-filter=.*` every `url_open` answers 404 (the dbfilter here is
hostname-based). Without `--logfile` the verdict goes to the shared server log.
