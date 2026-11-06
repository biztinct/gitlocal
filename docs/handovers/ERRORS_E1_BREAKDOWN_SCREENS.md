# ERRORS · Phase E1 — The branded breakdown screen

**Read `docs/ERRORS_CONVENTIONS.md` first.** Every entry `ER1`–`ER9` referenced below is binding and
is **not** restated here. Do not re-derive anything in it.

---

## 1. Why this exists

On 2026-09-11 the brand owner opened `/my/buddy` on `rize.payobook.com` and met a bare grey page
headed *500: Internal Server Error* with a full Python traceback printed down it, server file paths
and all. The crash itself is fixed (commit `c9f96da8`, see `ER8`). **This phase is about the page
they landed on**, which would have looked the same for any other failure.

Two separate failures of the product, both still live:

1. **The vendor's name reaches the screen.** The traceback is the only user-visible surface on the
   whole platform that no debranding seam can reach, and the reason is structural, not an oversight
   (`ER1`).
2. **An ordinary member of staff gets a dead end.** They do not see the traceback (`ER2`), so what
   they get is a white page saying *500: Internal Server Error*, a "Home" link and a "Back" link, in
   a typeface that belongs to nothing. No brand, no explanation, no idea whether their pay run just
   failed, nothing to tell anybody.

## 2. Scope

**In scope.** Every server-rendered breakdown page on the public and staff side becomes a calm,
branded, plain-English screen with a way out and a support reference:

| Template | Today | After |
|---|---|---|
| `http_routing.500` | standalone HTML, no brand, traceback for designers | branded self-contained page (`ER3`), reference, no technical detail |
| `http_routing.4xx` | *"Oops! Something went wrong."* + debug block | branded wording, no debug block |
| `http_routing.400` | *"400: Bad Request"* | *"That request didn't come through"* |
| `http_routing.403` | *"403: Forbidden"* | *"You don't have access to this page"* |
| `http_routing.415` | *"415: Unsupported Media Type"* | *"That file type isn't supported here"* |
| `http_routing.422` | *"Oops! Something went wrong."* | same family as 400 |
| `http_routing.http_error` | bare `<h1>code: message</h1>` | branded family page |
| `http_routing.http_error_debug` | error + QWeb + traceback cards | renders **nothing** |
| `http_routing.error_message` | `<pre>` of raw text | plain sentence, `UserError` text only (`ER6`) |

**Binding non-goals.** Do not touch any of these:

* `http_routing.404` / the website 404. It is already branded (`<title>Page Not Found | Rize</title>`,
  verified live) and is the one page in the family that works. Leave it alone.
* The backend OWL error dialogs. `biz_theme/static/src/js/biz_error_dialogs.js` already owns them,
  ships into `web.assets_backend` **and** `web.assets_frontend`, and is good. Do not duplicate, do
  not patch, do not "improve".
* The developer-mode rail. `biz_theme/models/ir_http.py` already holds `debug` (`ER2`). Do not
  rebuild it, do not weaken it, do not add a second one.
* Any of `biz_debrand`'s five seams. `ER1` explains why the two relevant skips are correct.
* The `/odoo` → `/bizapp` routing (`biz_deroute`) and anything in `web_debranding`.
* Technical identifiers of any kind — `from odoo import …`, module and model ids, `odoo-bin`, config
  paths, log messages, code comments, this document. The white-label rule is about **user-visible
  strings only**.
* Phase E2's list (session-expired routing, the Vietnamese pre-filter, raw-error toasts, the
  spreadsheet line, the no-database page). Named in §8 so you know they are deliberate omissions,
  not things you found and should fix.

## 3. Verified plumbing — do not re-derive

All paths are on the live server, `Payobook19v2` (`3.104.113.197`), under `/odoo/odoo-server/`. The
repo's own `website/` and `web/` directories are **older vendored snapshots** and must never be
deployed (`CLAUDE.md`). `http_routing` and `portal` are not in the repo at all.

| Fact | Location |
|---|---|
| The error templates | `addons/http_routing/views/http_routing_template.xml` — `http_error` 3, `error_message` 15, `http_error_debug` 23, `4xx` 63, `400` 80, `403` 99, `404` 119, `415` 155, `422` 176, `500` 193 |
| Values builder | `addons/http_routing/models/ir_http.py._get_exception_code_values` ~525; `error_message` set at 535 (`UserError`) and 538 (werkzeug) |
| The dispatch order | `addons/http_routing/models/ir_http.py._handle_error` ~572 — quoted in full in `ER4` |
| **Your seam** | `addons/http_routing/models/ir_http.py._get_error_html` ~565, overridden at `addons/website/models/ir_http.py:397` |
| `editable` | `addons/website/models/ir_http.py:393` — `website.group_website_designer` |
| Brand parameters | `biz_debrand.brand_name` / `biz_debrand.brand_website`, falling back to `web_debranding.new_name` / `.new_website` — resolution order is `biz_debrand/models/brand.py:91` (`brand_for_env`) |
| Precedent for reading the brand into a template | `biz_debrand/views/brand_layout.xml` (the `<meta name="biz-brand">` inherit on `web.layout`) |
| Precedent for a small portable `biz_*` module | `biz_debrand/` — manifest, `models/`, `views/`, `tests/` |
| Wording and tone to match | `biz_theme/static/src/js/biz_error_dialogs.js` `VARIANTS` — the `crash` variant already says *"Something went wrong on our side"* / *"This wasn't you. Try again — if it keeps happening, let your administrator know so support can look into it."* **Reuse these sentences verbatim** so the dialog and the page speak with one voice. |

Installed on all six databases and safe to depend on: `http_routing`, `portal`, `website`, `web`.

## 4. Architecture

### 4.1 A new module, `biz_errors`

```
biz_errors/
├── __init__.py            # from . import models
├── __manifest__.py        # version 19.0.1.0.0, depends ['http_routing', 'web']
├── README.md
├── models/
│   ├── __init__.py
│   └── ir_http.py         # _inherit = 'ir.http'  — ONE method: _get_error_html
├── views/
│   └── error_templates.xml
├── i18n/
│   └── vi_VN.po
└── tests/
    ├── __init__.py
    └── test_breakdown_screens.py
```

Why a new module and not `biz_theme`: `biz_theme` deliberately depends only on `['web', 'base']` and
is the portable base theme. A hard `http_routing` dependency there would drag the website stack onto
every future consumer. `biz_errors` stays in the same portable `biz_*` family, reads the same brand
parameters without a hard dependency on `biz_debrand`, and is installed everywhere alongside it.

### 4.2 The single server seam

`biz_errors/models/ir_http.py`, `_inherit = 'ir.http'`, overriding **only** `_get_error_html`
(`ER4` explains why this method and not the obvious one):

```python
@classmethod
def _get_error_html(cls, env, code, values):
    try:
        values = cls._biz_error_values(env, code, values)
    except Exception:                       # noqa: BLE001
        _logger.warning('biz_errors: could not decorate the breakdown page',
                        exc_info=True)
    return super()._get_error_html(env, code, values)
```

`_biz_error_values` does five things, in this order:

1. **Mint the reference.** 8 characters of Crockford base32, grouped `XXXX-XXXX` (`ER5`).
2. **Log it beside the stack**, at ERROR, before anything is removed:
   `_logger.error('biz_errors [%s] %s %s\n%s', ref, code, path, values.get('traceback'))`.
   Read the path defensively — `request` may be in an odd state.
3. **Blank the technical values**: `traceback`, `qweb_exception`, and `exception`. Set `editable`
   and `debug` to `False` as well, so a template we have not replaced still cannot open the block.
4. **Decide `error_message`** per `ER6`: keep it only when the original exception is a `UserError`,
   otherwise blank it. `values['exception']` is the exception object, so test it *before* step 3
   removes it.
5. **Add the brand**: `brand_name` (chain at `biz_debrand/models/brand.py:91`, then
   `env.company.name`, then a neutral `'this application'` — **never** a vendor fallback), plus
   `error_ref` and `brand_home = '/'`.

### 4.3 The templates

Full `position="replace"` of the template bodies listed in §2. One shared macro,
`biz_errors.breakdown`, takes `headline`, `sub`, an inline SVG icon name and the reference, so the
seven pages are one design in seven wordings.

* The **4xx family** keeps its `<t t-call="web.frontend_layout"/>` wrapper. It renders after the
  rollback, the site's own assets load, so the page arrives inside the real Rize/Payobook chrome.
* The **500** must not (`ER3`): self-contained `<html>`, one inline `<style>`, one inline `<svg>`,
  the brand as a text wordmark. No asset URL, no `<img>`, no `website.layout`, no `csrf_token`.
* `http_routing.http_error_debug` is replaced with an empty template. Belt and braces on top of
  step 3.

### 4.4 The design

The mandate is binding here and this is a hero moment, not a leftover: **extreme WOW, intuitive,
out-of-this-world, best in class.** The one screen a person sees on their worst minute with the
product has to be the calmest thing in it.

* Centred card on the page ground, max-width ~34rem, generous vertical rhythm. White + rail, flat.
  **No gradients, no emoji** (Payobook design system, memory `payobook-design-system`).
* Brand wordmark at the top, small and quiet.
* One inline SVG line-icon in the Lucide style, ~44px, in the muted ink colour — *drawn inline*,
  because the 500 page cannot load the Lucide bundle (`ER3`). Copy the path data out of Lucide so it
  is the same family as the rest of the product.
* Headline in plain English, sentence case, no status code. Supporting line underneath in muted ink.
* The reference in a small monospace chip with a one-line label above it: *"If you need help, give
  your administrator this reference"*. Chip is selectable text.
* Two buttons, primary **Go back** (`history.back()`), secondary **Home** (`/`). Zero dead-ends is
  part of the mandate — never leave the person with only a back button.
* Purposeful motion: one ~200ms fade-and-rise of the card on load. Nothing else. Respect
  `prefers-reduced-motion`.
* Must read correctly at 360px wide and in Vietnamese, where the strings run ~30% longer.

**The status code never appears on screen.** It is in the reference and the log.

## 5. Safety rails

1. **Never let this module break a page.** Every addition is inside try/except; a failure logs a
   warning and renders the stock page. A breakdown page that itself breaks is unrecoverable — the
   handler has nowhere left to go.
2. **Never read the ORM before the rollback** (`ER4`). The only seam you touch is after it.
3. **Do not weaken the debug rail** (`ER2`). If a test needs a traceback, read it from the log.
4. **Do not `--delete` into the addons root** (`CLAUDE.md`, and the 2026-08-26 incident that wiped
   the live box). Scope it to `/odoo/odoo-server/addons/biz_errors/`.
5. **The word "Odoo" must not appear in any string this module puts on a screen**, including the
   Vietnamese catalogue. It stays in code comments, the README, log messages and this document.
6. `error_message` is rendered with `t-esc`, never `t-out`/`t-raw` — the value can originate in a
   `UserError` whose text came from user input.
7. The reference is a random token, not a hash of anything. It must reveal nothing about the
   failure, the user or the database.

## 6. Test cases — numbered, all must pass

Run per `ER7` (the `--db-filter=.*` and `--logfile` rules are not optional). Add a test route that
raises on demand in `tests/` so the 500 path is reachable; register it under a `/biz_errors/test/…`
prefix and keep it inside the tests package so it never ships to a live route table — if that proves
impossible, gate it on a config parameter that is off by default and say so in your report.

1. **The 500 page carries no crash report.** As a user in `website.group_website_designer` (this is
   the owner's own case, `ER2`), fetch a route that raises. Body must not contain
   `Traceback (most recent call last)`, `odoo-server`, `odoo.exceptions`, `File "`, or `line `.
2. **The 500 page carries no vendor name.** Case-insensitive: no `odoo` anywhere in the rendered
   body outside `<script>` — remember the page legitimately has none, since it loads no assets.
3. **The 500 page is branded.** Body contains the value of `biz_debrand.brand_name`.
4. **The reference is on the page and in the log**, and they are the same 8 characters.
5. **The reference differs between two failures.**
6. **A `UserError` raised from a frontend route still shows its own sentence** (`ER6`), and still
   shows no traceback.
7. **A werkzeug 403 shows our wording**, not *"The page you were looking for could not be
   authorized"*, and no `<pre>`.
8. **`?debug=1` changes nothing** for a non-system user *and* for a designer — the technical block is
   gone for everybody now, not merely gated.
9. **404 is untouched**: `/this-page-does-not-exist` still returns the website's own branded 404, and
   the body still contains the site title. This is the non-goal regression test.
10. **Every replaced template still renders** — loop the seven ids through
    `env['ir.ui.view']._render_template(id, values)` with a realistic values dict and assert no raise.
11. **Both buttons are present** on every breakdown page: a `history.back()` control and a link to
    `/`. Zero dead-ends.
12. **Vietnamese**: render the 500 page with `lang=vi_VN` and assert the headline is the Vietnamese
    string, not the English one, and still contains no `odoo`.
13. **The existing suites still pass**: `pb_onboarding`, `pb_me_portal`, `pb_pay` — 135+ tests,
    0 failed. This phase must not disturb them.

## 7. Deploy and verify

1. `sudo rm -rf /tmp/deployE1 && mkdir -p /tmp/deployE1 && chmod 777 /tmp/deployE1`
2. `rsync -az --exclude=__pycache__ --exclude='*.pyc' --exclude='.DS_Store' biz_errors Payobook19v2:/tmp/deployE1/`
3. `sudo rsync -a --delete /tmp/deployE1/biz_errors/ /odoo/odoo-server/addons/biz_errors/`
4. Install on **all six** (`ER9`): `payobook`, `payobook_template`, `abm`, `p9clone`, `rize`,
   `rztest` — `-i biz_errors --stop-after-init --max-cron-threads=0 --no-http`, one at a time, with
   the server stopped.
5. Restart, confirm `systemctl is-active odoo-server` and `curl localhost:8069/web/health` → 200.
6. **Verify per database**: manifest version equals `ir_module_module.latest_version` (normalise the
   `19.0.` series prefix first, `CLAUDE.md`), and the module tree hashes identically on both sides
   ignoring `__pycache__`, `*.pyc`, `.DS_Store`.
7. **Verify on the real site**: browse to a URL that 500s on `rize.payobook.com` as a designer and
   screenshot it. Chrome MCP is pre-approved and must not be skipped; start the server yourself if it
   is down (memory `chrome-mcp-standing-approval`). Save shots to `docs/handovers/errors_e1_shots/`.
8. One feature-scoped commit, explicit file staging, reviewer-focused message (standing rule
   `commit-per-feature`). **Do not push.**

## 8. Deliberately left for Phase E2 — do not start these

Found in the same audit, confirmed, and out of scope here. Listing them so you do not treat them as
oversights:

1. Session expiry on the staff portal is routed to a plain notification, not `BizErrorDialog`.
   `web/static/src/public/error_notifications.js` registers `odoo.http.SessionExpiredException` and
   `werkzeug.exceptions.Forbidden` in `error_notifications`, and `biz_theme`'s own
   `hasSpecificHandling()` then stands down for them. The *text* is already debranded by the `_t()`
   seam; the presentation is not ours.
2. `biz_debrand/models/translate_patch.py:42` pre-filters on the **English source**, so a translated
   string that names the vendor where the English does not slips through. Two live cases, both in
   `calendar`'s Vietnamese catalogue.
3. Legacy `pb_hr_payroll_analytics` / `pb_hr_payroll_base` paste raw `str(e)` into on-screen toasts
   (`_('Error: %s') % str(e)`). The `_()` seam debrands the template, never the interpolated
   argument — deliberately, so a record genuinely named "Odoo Ltd" survives.
4. `spreadsheet/static/src/o_spreadsheet/o_spreadsheet.js` — *"Submit a support ticket at
   odoo.com/help"*, inside the library's own translation mechanism, outside both seams.
5. The pre-database page: an unknown hostname gets werkzeug's *"No database is selected … use the
   X-Odoo-Database header"*. It is served before any database is chosen, so no module can reach it.
   The fix is an nginx `default_server` block; there is none today (`/etc/nginx/sites-enabled/`:
   `_`, `pb-wildcard`, two tenant files, no `error_page`, no `default_server`).
6. `serialize_exception` (`odoo/http.py:469`) puts the full traceback in the `debug` key of **every**
   failed JSON response. Not rendered, but on the wire to any signed-in user.

## 9. Report back

State plainly, in this order:

1. Test cases 1–13: pass or fail, one line each, with the actual assertion output for any failure.
2. The six databases: installed version vs `latest_version`, and the content hash comparison.
3. The screenshots you took and what they show.
4. Anything in §4 you implemented differently, and why.
5. Any new gotcha you hit, written as an `ER10`+ entry ready to paste into
   `docs/ERRORS_CONVENTIONS.md`.
6. Anything you could not finish, named explicitly. Do not quietly narrow the scope.
