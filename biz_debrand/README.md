# biz_debrand — Portable Odoo 19 White-Label Layer

Replaces every user-visible **Odoo** reference with a configurable brand, across
backend, login, browser tab/favicon, OdooBot, website/portal, emails, the
"Odoo Push notifications" banner, the Settings copyright line, and the database
manager page. No project-specific dependencies.

## Requirements

This module **orchestrates** an existing debranding suite (the engine). The
target database must have these installed/available:

| Module | License | Notes |
|---|---|---|
| `web_debranding` | **OPL-1 (commercial, ~€300)** | You must legally own it |
| `mail_debranding` | AGPL-3 (OCA) | Email footer |
| `portal_debranding` | AGPL-3 (OCA) | Portal + login footer |
| `website_debranding` | AGPL-3 (OCA) | Website; pulls in core `website` |
| `disable_odoo_online` | AGPL-3 (OCA) | odoo.com online bindings |

## Install

1. Drop `biz_debrand/` into your addons path.
2. Install it (`-i biz_debrand`). On install it seeds the brand and applies it.
3. **Set your brand:** Settings → General Settings → **Branding** → *Brand Name*,
   *Brand Website*, *Brand Theme Color*, then **Save**. This is the single knob;
   it re-applies everything (companies, websites, bot, debranding suite).
4. **Replace the logo:** swap `static/src/img/brand_icon.png` with your own
   square PNG (used for favicon, bot avatar, and the DB-manager logo).

Defaults are neutral placeholders (`BizApp` / `https://example.com`) so an
unconfigured install visibly signals "set your brand".

## Design notes

- Fully **config-parameter driven** (`biz_debrand.brand_name/website/theme_color`)
  — per-database, SaaS-friendly.
- Seeding runs on **install, every upgrade, and every Save** (idempotent).
- **Zero core edits.** Uses `ir.config_parameter`, QWeb/OWL `t-inherit`, a
  `res.config.settings` knob, and one controller override for the pre-login DB
  manager page (which bypasses the normal translation pipeline).
- **LGPL compliance:** source-file copyright/license headers are retained on
  disk (required); only the *visible* UI attribution is removed.

## Not in scope

- The `/odoo/…` backend URL prefix (a core SPA route; renaming it forks
  `router.js` and is upgrade-fragile — left as a technical route).
- PWA branding — this module is PWA-agnostic. The `biz_debrand.theme_color`
  param is exposed for a PWA to consume if you wire one up.
