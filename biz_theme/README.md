# biz_theme — reusable Odoo 19 CE backend theme base

Brand-agnostic superset of the health19 + Payobook theme stacks. Any future
Odoo 19 CE app installs `biz_theme` and gets the full design system; a thin
brand overlay module (see `pb_theme`) supplies the palette.

## What's inside

| Layer | Files | What it gives you |
|---|---|---|
| Design tokens | `scss/biz_variables.scss` | `$vu-*` SCSS palette (all `!default`) + `:root { --vu-* }` custom properties + `[data-theme='dark']` block + `vu-card` mixins |
| Breakpoints | `scss/biz_breakpoints.scss` | `$biz-bp-xl/lg/md/sm` (1440/1280/1100/768) + `biz-down()/biz-up()` mixins + `biz-rail-mode` sidebar mixin — visible to SCSS in **every** bundle |
| Utilities | `scss/biz_utilities.scss` | `.biz-truncate`, `.biz-scroll-x`, `.biz-hide-{xl,lg,md,sm}`, `.biz-only-{lg,md}`, `.biz-icon-only-lg` (+`.biz-keep`), `.biz-cockpit-head`, `.biz-more-menu`, `.biz-skeleton--{text,title,row,card}`, `.biz-empty` |
| Sidebar behavior | `scss/biz_sidebar.scss`, `js/biz_sidebar_state.js` | manual pin/collapse + auto icon-rail (<1440px, i.e. everything below wide desktop) with hover-expand overlay; per-user persistence (`biz.sidebar.mode.<uid>`) |
| Menu-driven sidebar | `js/biz_sidebar_menu.js` | zero-config left sidebar built from `ir.ui.menu` (group-filtered by Odoo) — enable per app via `biz_theme.menu_sidebar_apps` |
| Runtime theming | `models/biz_theme.py`, `controllers/theme_tokens.py`, `studio/` | `biz.theme` + presets, `/biz_theme/tokens.css` endpoint, Theme Studio (Settings → Theme Engine): live preview, WCAG checks, publish without redeploy |
| VU Form Engine | `js/vu_form_*.js`, `scss/vu_form_engine.scss` | hero/card re-skin of native form views (kill-switch `biz_theme.vu_form_engine = off`) |
| Loading UX | `scss/biz_loading.scss` | non-blocking top progress bar + quiet loading pill; branded blocking card only for `.o_blockUI` |
| Error dialogs | `js/biz_error_dialogs.js` | calm replacements for access / validation / missing / timeout / session / crash pop-ups (registry override, no core patch) |
| Apps menu | `webclient/apps_menu*` | searchable grid app launcher |

## Building a brand overlay (the pb_theme pattern)

1. Create `<brand>_theme` depending on `biz_theme`.
2. Palette file assigning `$vu-*` scalars **without** `!default`, wired with the
   deterministic asset directive:
   ```python
   'web._assets_primary_variables': [
       ('before', 'biz_theme/static/src/scss/biz_variables.scss',
                  '<brand>_theme/static/src/scss/primary_variables.scss'),
   ],
   ```
   Compile order becomes: brand palette → biz `!default` defaults → Odoo core.
   **Never rely on prepend-vs-prepend module order, and never rename
   `biz_variables.scss` — it is a public anchor.**
3. Optional runtime overrides (`--biz-chrome-*`, `--vuf-*`) in a small SCSS
   file in `web.assets_backend` (loads after biz files by dependency order).
4. To freeze branding (no runtime re-theming), ship
   `ir.config_parameter biz_theme.runtime_tokens = off`.

## Sidebar contract

Map these classes onto your sidebar markup (additively) and the rail/toggle
behavior comes free: `.biz-layout-wrapper` (wrapper), `.biz-sidebar` (aside),
`.biz-sidebar-brand`, `.biz-sidebar-label` (any text hidden in rail mode),
`.biz-sidebar-item`, `.biz-sidebar-sub`, `.biz-sidebar-footer`,
`.biz-sidebar-toggle`. Call `applySidebarMode(getSidebarMode(uid))` on mount
and `toggleSidebarMode(uid)` from the pin button
(`@biz_theme/js/biz_sidebar_state`). Rail rules are scoped with
`:has(> .biz-sidebar)` so wrappers without a rendered sidebar never get rail
padding (requires a modern Chromium/Safari/Firefox — fine for backend apps).

For the zero-config variant, set
`biz_theme.menu_sidebar_apps = <root_menu_xmlid>[,<xmlid>…]` and skip all of
the above — level-2 menus become collapsible sections, group access follows
`ir.ui.menu.groups_id`.

## Config parameters

| Key | Default | Meaning |
|---|---|---|
| `biz_theme.runtime_tokens` | `on` | `off` = tokens endpoint serves empty CSS (brand lock) |
| `biz_theme.vu_form_engine` | `on` | `off` = native Odoo form rendering (legacy `pb_theme.vu_form_engine` still honoured) |
| `biz_theme.menu_sidebar_apps` | *(empty)* | root-menu xml_ids that get the menu-driven sidebar |
| `biz_theme.theme_version` | `0` | bumped on publish (cache invalidation) |

## Token whitelist (runtime theming)

32 colors (brand, surfaces, text, borders, status, workflow states,
navbar/sidebar chrome, buttons, statusbar/tabs, focus ring, `biz-chrome-*`) ·
7 dimensions (radius sm/md/lg, navbar height, sidebar width + rail width,
table row padding, base font size) · 4 numbers (density, radius-scale,
shadow-depth, motion-scale) · 2 fonts (body, headings). Values are
regex-validated server-side; unknown keys are dropped at CSS generation.
