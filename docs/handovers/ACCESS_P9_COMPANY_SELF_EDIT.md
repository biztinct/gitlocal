# ACCESS P9 — "Your company": let a tenant administrator fix their own details

Read FIRST: `ACCESS_PROGRAM.md` (owner ruling 4 + ledger A1-F6), `ACCESS_CLOSEOUT.md` (debt
about the company rename), and P5's Rail C notes (the settings hub is now server-authoritative).

Owner decision 2026-09-02: **yes — a tenant administrator may edit their own company's cosmetic
and legal details.** Everything structural stays with the platform.

Design bar (verbatim, binding): **extreme WOW, intuitive, out-of-this-world, best in class** —
hero moment, zero dead-ends, plain language, purposeful motion; Lucide not emoji; Chrome-MCP
validate. White-label rule: "Odoo" never in a user-visible string; plain English only.

## The distinction that defines this phase

| Thing | Who controls it | This phase |
|---|---|---|
| The web address (`abm.payobook.com`), DNS, the certificate | Platform only (Tenants cockpit) | **untouched — a tenant can never reach it** |
| Creating/removing companies, company hierarchy, currency | Platform only | **untouched** |
| Their own company's name, address, tax details, logo, contact details | today: platform only | **opens up to the tenant administrator** |

## Scope

1. **A "Your company" surface** in Settings, visible to whoever holds the Tenant administrator
   role (and to the platform administrator, as everything is). It edits exactly ONE record —
   the user's own company — never a list, never a company picker.
2. **The editable set (whitelist, explicit — never a blacklist):** company name, legal/trading
   name if the model distinguishes them, street/city/state/zip/country, phone, email, website,
   tax/registration identifiers (the fields a payslip or a filing prints), and the logo.
   **Everything else on the company record is refused server-side**, in particular:
   `currency_id`, `parent_id`, any company-hierarchy field, and anything the platform sets
   during provisioning. Enumerate what you whitelisted in the report.
3. **Server-authoritative guard**: a facade method (follow the existing facade gate pattern) that
   (a) resolves the caller's own company itself — it must NOT accept a company id from the
   browser, (b) accepts only whitelisted field names, (c) refuses everything else with a plain
   sentence. A forged RPC naming another company or a blocked field must fail. Test it.
4. **The "where this shows up" moment** (the wow, and the honesty): before saving, show the user
   where these details actually appear — the payslip header, filings, letters. A small live
   preview card beside the form. This is what turns a settings form into something considered.
5. **Rail C interaction**: do NOT open the platform "Companies & Tenants" category. This is a
   separate, narrow surface. The platform category stays `base.group_system` and fails closed.
6. **An audit line**: a company-details change is worth a message on the company record's log
   (who changed what, when) — reuse the standard chatter/logging already on the model rather
   than inventing a store.

## Binding NON-goals

- No multi-company anything. No company creation or archiving. No currency change.
- No changes to the tenant's hostname, DNS, certificate, or any `pb_tenants` record.
- No changes to the Access home's three lenses or the composer.
- Do NOT push.

## Where it lives

`pb_settings` is the natural home (it owns the hub, it is installed on tenants, and P5 already
gave it a server-authoritative gate). If you find a cleaner seam, say why in the report. If any
new user-visible string is product-specific, keep it neutral enough for the generic layer.

## Numbered test cases

1. A user holding **only** the Tenant administrator role sees "Your company", opens it, and can
   change the name/address/tax id/logo; the change lands and shows on a payslip header.
2. The same user, via a forged RPC, tries: another company's id → refused; `currency_id` →
   refused; `parent_id` → refused. Server-side, with plain-English errors.
3. A plain `base.group_user` does not see the surface at all and its RPCs refuse.
4. The platform administrator still has the full Companies screen; the platform-only settings
   category is unchanged and still fails closed (P5 Rail C regression).
5. The audit line records who changed what.
6. Chrome MCP at ~1440 and ~1100: the form + the "where this shows up" preview; zero console
   errors; asset ritual (purge + `web.assets.version` bump) per DB.
7. Suites green on payobook and abm (compare to your captured baselines).
8. Copy audit: plain English, no "Odoo", no technical field names shown to a user.

## Deploy + verify + report

CLAUDE.md contract authoritative; ⚠ F6 (`--http-port`/`--no-http` on every `odoo-bin` run);
ledger A8 clone hygiene. Deploy to payobook and abm (both have `pb_settings`).
Report: the exact whitelist, the guard's refusal evidence, screenshots, deploy verification per
DB, decisions beyond spec, anything left out and why. Feature-scoped commit, module files only,
Claude co-author line, **not pushed**.
