# ERRORS · Phase E4 — Branding becomes a setting, and the last leaks close

**Read `docs/ERRORS_CONVENTIONS.md` first** (ER1–ER26, binding, not restated), then the E1–E3
handovers for what shipped.

E1–E3 built the machinery and fixed Rize by hand. E4 makes it a **product decision the business
can sell**, and closes the four leaks no text rule can reach.

---

## The owner's ruling, 2026-09-12 — this governs every item below

Branding is **per customer, and three levels**, not one global rule:

| Level | Who sees what | Sold as |
|---|---|---|
| **Full product** (the DEFAULT) | Payobook in tabs, sign-in, menus, emails, screens. Customer's own name on payslips and reports. | Standard |
| **Powered by** | Customer's brand on what their employees and public see. Payobook in the admin console plus a credit line. | Standard or mid tier |
| **Full white-label** | Customer's brand everywhere. No Payobook. | **Paid upgrade** — this is Rize today |

Two absolutes:

* **"Odoo" must never appear to a user** (standing white-label rule), *including in text an AI
  writes*. Where the vendor name is currently shown, it becomes the brand — `Payobook` on a default
  tenant, the customer's own name on a white-labelled one.
* **"BizApp" must never appear as a LABEL, HEADING or product name** — nothing that would make a
  user think the product is called BizApp. It was removed from all six databases' data on
  2026-09-12, which is what that required.

### BizApp stays in the code. Do not touch it. (Owner's ruling, 2026-09-12)

**The owner has ruled that "BizApp" is NOT to be removed from the code at all**, and is right: it is
the deliberate technical stand-in for the vendor across this platform's plumbing — the `/bizapp`
backend URL prefix (`biz_deroute`, live), `biz_debrand.web_app_scope`, module names, config keys.
Ripping it out would break routing and the installed-app scope. The owner is content for it to
appear in a URL or any other technical element.

So, revising what an earlier draft of this document said:

* `biz_debrand/models/brand.py:47` `DEFAULT_BRAND = "BizApp"` — **LEAVE IT.**
* `biz_debrand/static/src/js/biz_debrand_runtime.js:40` — **LEAVE IT.**
* The `/bizapp` prefix and every technical identifier — **LEAVE THEM.**

These fallbacks are unreachable in practice anyway: all six databases now carry a real brand, and
the template does too, so a new tenant inherits `Payobook`. The placeholder can only surface on a
database with no brand parameter at all, which no longer exists.

**The one fallback that still must change is the vendor one** — see P4-2.

---

## P4-1 — Branding as a per-customer setting, applied when the tenant is made

**The gap, verified 2026-09-12.** `pb_tenants/models/service.py._step_clone` (:825) clones
`payobook_template` (:277); `_step_configure` (:837) sets `web.base.url`, the uuid, the secret, the
slug, the company name, country and currency — and **never touches a brand parameter**
(`grep brand_name pb_tenants/models/*.py` → nothing). Rize sat on the placeholder for months
because of this.

**Build.** A branding level on the tenant record (`pb.tenant`), defaulting to **full product**,
applied during provisioning:

* *full product* — leave `biz_debrand.brand_name` as the template's `Payobook`; `product_name` unset.
* *powered by* — brand becomes the tenant's own name; `product_name` unset so genuine Payobook
  mentions stand; the credit line shows.
* *full white-label* — brand becomes the tenant's own name; `biz_debrand.product_name = Payobook`
  so our product name is swapped out. **This is exactly Rize's current configuration** — treat
  Rize as the reference implementation and make the code reproduce it, then verify by comparing
  against the live rize parameters rather than by reading this document.

Changing the level on an existing tenant must re-apply cleanly and be reversible.

**Do not call `_biz_debrand_apply_brand` on a tenant.** It rewrites every website record's name and
favicon from the module's own generic icon, which would wipe a tenant's branding. Set the
parameters directly — the method used for rize and for the template on 2026-09-12. Set:
`biz_debrand.brand_name`, `.brand_website`, `.theme_color`, `web_debranding.new_name`, `.new_title`,
`.new_website`, `.new_documentation_website`, `web.web_app_name`, and `website.name` where it still
reads the old brand.

**Test** by provisioning a throwaway tenant at each of the three levels and reading back what a
browser would get. Remove it afterwards.

## P4-2 — One fallback, and one only: the vendor's

**Scope is exactly one line.** `biz_theme/models/ir_http.py:246` ends the browser-tab name chain
with `or "Odoo"`. If every earlier step were empty, the product would put the **vendor's name** in
the browser tab. That is the standing rule broken by a default value, and it goes.

Replace it with the brand — and `biz_theme` is a **reusable, product-neutral** module
(`biz_debrand/README.md` states the design), so do not hard-code `Payobook` into it. The chain
already reads `biz_theme.app_name`, then the debrand suite's keys, then the company name. Let it end
there, or on the reusable core's own neutral constant. The Payobook-specific default, if one is
wanted, belongs in `pb_theme`, which already exists for this and already depends on `biz_theme`.

**Do not touch the two `BizApp` constants** (`brand.py:47`, `biz_debrand_runtime.js:40`) or anything
else carrying that word — see the owner's ruling above. This item is the vendor fallback alone.

**Test** that no code path can return the vendor's name as a brand or a tab title, on a database
with the brand parameters present and on one with them absent.

## P4-3 — The AI assistant says both wrong names

**This is the item that fixes the owner's original complaint.** "Welcome to Payobook" in the Rize
backend exists in no source file and no rize database column — it is written by the assistant.

`pb_payroll_ai_insights/models/payroll_ai_engine.py`:

* **7 mentions of our product name** — `:16` *"an intelligent payroll analytics assistant for
  Payobook"*, `:81`, `:89`, `:91`, `:93`, `:99`, `:637`.
* **4 mentions of the vendor**, including `:91` *"the in-app onboarding copilot for Payobook, an
  **Odoo-based** multi-country…"*. The assistant is being told what it is built on, so it can tell a
  customer. **That is a direct breach of the standing rule and the sharpest item in this phase.**

Make the prompts read the brand at runtime, so the assistant introduces itself as `Payobook` on a
default tenant and as the customer's own name on a white-labelled one.

**The vendor mentions do not get rewritten to the brand — they get deleted.** "a Payobook-based
multi-country platform" is nonsense; the assistant never needs to know what the platform is built on
to answer a payroll question, and a sentence describing its own foundations is one it should not be
able to write at all. Owner's instruction is that the user must never see the vendor name; removing
the fact from the prompt is how that is guaranteed rather than hoped for.

Generated prose cannot be caught by any rule afterwards, so the prompt is the only place this can be
fixed.

**Test** by asking the live assistant on rize, in its own words, who it is, what product this is, and
what it is built on. Quote all three answers in your report. An assistant that still names the
vendor when asked directly is a failed item, however clean the prompt looks.

## P4-4 — 21 texts that skip the translation step

Counted 2026-09-12: 21 JavaScript string literals in `pb_*` naming the product are not wrapped in
`_t()`, so no seam sees them — e.g.
`pb_payroll_ai_insights/static/src/components/ai_insight_chat/ai_insight_chat.js:75`
`"Show me around Payobook"`. Wrap them. They are then covered automatically, in every language,
by machinery that already exists.

## P4-5 — A default written inside a QWeb expression

`pb_me_portal/views/portal_templates.xml:90` — `t-esc="hero_eyebrow or 'My Payobook'"`. The walker
must never enter a `t-` expression (ER1), so this literal is unreachable. One line: read the brand
instead. Sweep for siblings; `pb_ess_workforce/views/portal_templates.xml:449` and
`pb_me_portal:24` are plain text and already covered — confirm rather than assume.

Leave the two `data-biz-brand="keep"` credits in `rize_website` alone. They are deliberate (E3).

## P4-6 — Roughly a dozen broken links (ER26, not a naming bug)

`web_debranding.debrand_links` (`models/ir_translation.py:27`) does
`re.sub(r"\bodoo.com\b", new_website, source)` where `new_website` is a **full URL**
(`https://payobook.com`), so `https://www.odoo.com/pricing` becomes
`https://www.https://payobook.com/pricing`. Clicking one gets nothing.

Verified 2026-09-12: stored arches are clean, so the damage happens **at render**. 30 views on
`payobook` and 31 on `rize` contain a vendor URL that goes through this. The reported count of
malformed results was 12; the two numbers measure different things — establish the real one and say
which you measured.

Fix in `biz_debrand` (never edit `web_debranding`, it is gutted on Odoo 19): `debrand_url`
(`brand.py:55`) already does this correctly with `website_host()`. Route the arch path through it.

---

## Deploy, verify, report

Deploy per `CLAUDE.md`; upgrade all six databases (ER9). Chrome MCP is pre-approved. Prove P4-3 by
asking the live assistant on rize and quoting its reply. Shots to `docs/handovers/errors_e4_shots/`.

Report: each item done/partly/not with reasons; test results plus the full-suite verdict line per
module; the six databases' versions, brand parameters and content hashes; the three tenant levels
demonstrated; new gotchas as `ER27`+; anything unfinished, named. One commit per item, explicit
staging, **do not push**.
