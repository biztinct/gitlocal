# The loading language (three moments, one language)

Owner decision 2026-10-11: Payobook adopts the same loading strategy as the
health19 build (its conventions §5.262), with Payobook's own "Rise" mark. It
replaces the dim-and-spinner and the bottom-right "Loading" pill.

| Moment | When | What the person sees | Where it lives |
|---|---|---|---|
| **Quick** | every screen change, every request (< ~1 s) | a 3 px **accent** line races along the top edge to 72 %, creeps, then runs to the edge and fades; the brand mark in the sidebar corner beats once. Nothing is dimmed, blurred or blocked. | `biz_theme/static/src/scss/biz_loading.scss` §1, `pb_sidebar/static/src/scss/pb_sidebar.scss` (beat), `biz_theme/static/src/js/biz_loading_hold.js` (350 ms hold + `body.biz-load-done`) |
| **Quick, long wait** | a request still in flight after **2.5 s** | the brand mark rises to the centre of the screen ("Rise": light sweeps through the letters, the arrow pulses, a slim line runs underneath) over a soft white halo. Click-through, never a blur. | `biz_loading.scss` §1b on the stock `.o_loading_indicator` |
| **Filling** | a cockpit that knows its shape but not its data yet (1–3 s) | soft grey blocks shaped like the page, breathing. Flat colour, no shimmer. | `.biz-skel` (inline) / `.biz-skel-block` (block) in `biz_loading.scss` §2; first use: Formula Studio's Cards view (`pb_formula_studio/static/src/xml/studio.xml` `.pbfs-skel`) |
| **First open** | the web client boots (fresh tab, sign-in) | full-screen splash: the mark rises, the light sweeps through it, a status line ("Opening your workspace" / "Đang mở không gian làm việc của bạn"), then it fades to the first screen. Min 1.9 s on the first open of a tab, 250 ms on reloads (`.is-still`), 8 s hard cap. | `biz_theme/views/webclient_templates.xml` (`#biz-splash`, inline CSS), `biz_theme/static/src/js/biz_splash.js` |

## Which mark (white label)

Every moment animates **this database's** brand, decided once per page:

1. `biz_debrand.loader_logo_url` set (Settings › General › Branding › *Loading
   screen logo*: upload, or an address the server serves) → that picture, as
   picture AND mask so the sweep stays inside the letters.
2. No picture and the database is white-labelled (`biz_debrand.brand_name`
   differs from `biz_debrand.product_name`) → the **brand name as text** in the
   brand colour (`biz_debrand.theme_color`, which is also the accent line).
3. Otherwise → the product default. `pb_theme` seeds the Payobook logo address
   on install/upgrade only where the brand *is* Payobook
   (`pb_theme/models/loader_logo.py`); the SCSS keeps the same picture as a
   compiled fallback.

Server side: `biz_debrand/views/brand_layout.xml` publishes `biz-loader-logo`,
`biz-brand`, `biz-brand-product`, `biz-brand-color` as `<meta>`; the splash is
rendered with the same parameters directly. Client side:
`biz_theme/static/src/js/biz_loader_brand.js` sets `--biz-loader-logo`,
`--biz-loader-text`, `--biz-loader-accent` and `data-biz-loader` inline on
`<html>`, which beats every stylesheet rule — one compiled bundle serves every
database. Tenant provisioning (`pb_tenants/models/brand_rules.py`) writes the
master's picture only at the default level and clears it on the two levels
that carry the customer's name. The sidebar badge is the brand's first letter
(`session_info.biz_app_name`), never a hard-coded "P".

## Rules

- **Never dim, blur or block on a screen change.** `.o_blockUI` keeps its
  branded card only for operations the framework itself blocks (exports).
- **No spinners on new cockpits.** A screen that knows its shape shows
  `.biz-skel-block`s in that shape; a value that is coming shows `.biz-skel`.
- **Mono-colour blocks, no shimmer gradient.** The sweep belongs to the mark
  only.
- **The line is the accent, never the primary**: the navbar is dark, a primary
  line disappears on it.
- **Nothing in the bootstrap body is translated through `arch_db`**: the render
  lang lags one request behind a language switch; switch on
  `session_info.user_context.lang` with a `t-out` expression instead.
- **The vendor's name appears nowhere in the loading language**, and the master
  product's mark appears on no white-labelled database.

## Traps (met, do not re-learn)

- The backend bundle is a parser-blocking `<script>` in `<head>`: module
  top-level code runs **before `<body>` exists**. Anything that looks for the
  splash must wait for `DOMContentLoaded` (`biz_splash.js` does).
- A CSS `mask` needs a picture with real transparency (PNG/SVG); a JPEG on
  white masks nothing.
- The stock pill's rules carry `!important`; the centre mark overrides with
  `!important` and later order.
- `web.assets.version` on rize is a 14-digit timestamp: bump with `::bigint`.

## Still on spinners (follow-ups, convert when each screen is next touched)

25 cockpit modules still carry their own "Loading…" state: pb_timeoff,
pb_structures, pb_statutory, pb_people, pb_mission, pb_integrations,
pb_hr_workforce, pb_hiring, pb_govt_reports, pb_contracts, pb_young_worker,
pb_wf_kit, pb_today, pb_time_hub, pb_tenants, pb_source_atlas, pb_settings,
pb_schedule, pb_probation, pb_pip, pb_people_hub, pb_payslip_review,
pb_payruns, pb_payrun_ledgers (+ a few single-screen ones). Replace each with
a `.biz-skel-block` layout of that screen's shape, as the Formula Studio does.
