# biz_deroute

White-labels the **backend URL prefix**: the Odoo 19 web client is served at
`/bizapp` instead of `/odoo`, and the SPA router generates `/bizapp` URLs
natively (address bar, history, bookmarks, deep links). Companion of
`biz_debrand` (cosmetic debranding); auto-installs on every database.

## How it works

| Layer | Mechanism |
|---|---|
| Routes | `Home.web_client` re-routed to `/web`, `/bizapp[/...]`, `/scoped_app/...`; `/odoo[/...]` becomes a **301** to the same path under `/bizapp` (keeps old bookmarks, mail deep links, `ir.actions.act_url`, third-party hardcoded hrefs working) |
| Redirect defaults | `/` index, post-login `_login_redirect`, `/web/session/logout` |
| Client router | `router.stateToUrl` / `router.urlToState` patched at the seam core documents as patchable; `startRouter()` re-run once at bundle eval |
| Click interception | Replica of core's module-scope internal-anchor listener (which hardcodes `/odoo`), so backend links stay SPA navigations on `/bizapp` |
| Service worker | Backend SW registration no-op'd + stale `/odoo`-scoped workers unregistered (scope-filtered: self-scoped PWAs like `/health_pwa/` are never touched) |

Untouched by design: `/web/*` (login, assets, RPC, session), `/websocket`,
`/scoped_app`, portal `/my`, website. Address-bar debranding only.

## Known, accepted gaps

- **Discuss browser push notifications are disabled** (they ride the backend
  service worker). Re-enabling requires serving a re-scoped SW +
  `Service-Worker-Allowed: /bizapp` + manifest override.
- Hovering/middle-clicking navbar app links still shows `/odoo/...` hrefs
  (`menu_helpers.js` builds them from a plain function export); normal clicks
  are intercepted, middle-clicks resolve via the 301.
- Mobile chat-window auto-fold on link click (mail `store_service` checks
  `location.pathname.startsWith("/odoo")`) doesn't trigger on `/bizapp`.
- `odoo/http.py` registry-failure rerouting allowlist doesn't know `/bizapp`
  (admin-only, database-broken scenario; degrades to stock error handling).
- `/web/manifest.webmanifest` still advertises scope `/odoo` and the
  `web.web_app_name` default — irrelevant unless the backend PWA is used;
  belongs to biz_debrand if ever needed.

## Upgrade ritual (each major version, ~1h)

1. `grep -rn '"/odoo\|'\''/odoo' addons/web addons/mail --include='*.py' --include='*.js'`
   against the new core; compare with the sites this module covers.
2. Diff `addons/web/static/src/core/browser/router.js` — especially the
   module-scope click listener replicated in `deroute_click.js` and the
   `stateToUrl`/`urlToState` signatures.
3. Re-check `Home.web_client` route list and `Session.logout` signature.
4. Run `--test-tags /biz_deroute` on a scratch DB.

## Changing the prefix

Single constant in two places: `BRAND_PREFIX` in `controllers/home.py` and
in `static/src/js/deroute_router.js`. Note: browsers cache the 301s.
