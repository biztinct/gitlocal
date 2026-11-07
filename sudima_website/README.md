# Sudima Panels staff portal

Install `sudima_website` only on the `sudima` tenant database. It is deliberately
not auto-installed or included in the standard tenant bundle.

The welcome page inherits `website.homepage`. The sign-in layout wraps Odoo's
native form, keeping its CSRF token, login errors, reset links, language selector,
passkeys, MFA and redirect handling. `/sudima/sign-in` uses the existing login
redirect rules for authenticated users. It does not grant any permissions.

The design uses ivory, walnut, and the olive accent from Sudima's company site.
Images are served locally; no remote image or font requests are needed.

Brand assets sourced on 7 November 2026 from the owner-specified reference:

- `https://sudimapanels.com/images/logo.png` → `sudima-logo.png`
- `https://sudimapanels.com/images/main-slider/slide1.jpg` → `cabinetry.jpg`
- `https://sudimapanels.com/images/main-slider/slide2.jpg` → `sudima-workplace.jpg`

These are product assets, not test screenshots. Preserve them during cleanup.
Platform credit follows `biz_debrand.powered_by`, including the tenant's empty
white-label setting. All CSS is scoped under `.sd-portal`.
