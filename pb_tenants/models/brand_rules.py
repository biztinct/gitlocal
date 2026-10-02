# -*- coding: utf-8 -*-
"""ERRORS E4-1 — how much of their own brand a customer gets, as a pure function.

WHY THIS FILE EXISTS AT ALL (rail R6, the same reason as `feature_rules.py`).
The answer to "what is this customer's product called" is worked out on the
platform's database and then WRITTEN to the customer's. A test cannot follow it
across that boundary, so the decision is lifted out of the write and put here,
where a test can ask it a hundred questions in a millisecond.

THE GAP THIS CLOSES. Provisioning wrote a customer's URL, their company name,
their country and their currency — and never once wrote a brand parameter
(`grep brand_name pb_tenants/models/*.py` found nothing before this phase). So
every new customer inherited the golden template's brand and kept it. Rize sat
on a placeholder for months because of that, and the fix was applied by hand.
Nothing that is applied by hand stays applied.

THE THREE LEVELS, WHICH ARE A PRICE LIST BEFORE THEY ARE A SETTING
------------------------------------------------------------------
  full product   Our name in tabs, sign-in, menus, e-mails and screens. Their
                 own name on payslips and reports, which comes from their
                 company record and never from here. The DEFAULT, and the one
                 a customer who has bought nothing extra must land on.
  powered by     Their name on everything their employees and the public see.
                 Our name still stands where it is a genuine statement about
                 who built the platform, plus a credit line.
  full white     Their name everywhere. Ours nowhere. A PAID UPGRADE.

The difference between the last two is one parameter, `biz_debrand.product_name`
— the opt-in rule of ERRORS E3-2. Set, it rewrites our product's name to theirs
wherever a seam can reach it. Unset, our name stands and only the VENDOR's is
rewritten. That is the whole mechanism; these levels are names for two settings
of it, and `rize` is the live proof that the white-label row is correct: the
values this module computes for `white` are the values that database carries.

WHAT THIS MODULE MAY NOT DO, AND IT IS THE DANGEROUS ONE
--------------------------------------------------------
It returns PARAMETERS. It never calls `_biz_debrand_apply_brand`, which is
biz_debrand's own Save handler: that method rewrites every `website` record's
name and favicon from the module's generic icon, so calling it on a customer
would erase the branding this feature exists to give them. The parameters are
set directly — which is exactly how `rize` and the golden template were set on
2026-09-12, by hand, and what this module now does by itself.
"""

#: The three levels, in the order a price list puts them. The first is the
#: default and must stay the default: a customer who bought nothing extra gets
#: our product, plainly, and never a half-configured brand.
LEVEL_PRODUCT = "product"
LEVEL_POWERED = "powered"
LEVEL_WHITE = "white"

LEVELS = (LEVEL_PRODUCT, LEVEL_POWERED, LEVEL_WHITE)

#: What the cockpit calls them, and the one line under each that says what the
#: customer will actually SEE. Plain words: the person choosing this is selling,
#: not configuring.
LEVEL_LABELS = {
    LEVEL_PRODUCT: (
        "Our product",
        "They see %(master)s — in the browser tab, on the sign-in page, in "
        "menus and e-mails. Their own company name still appears on payslips "
        "and reports. This is what everybody gets.",
    ),
    LEVEL_POWERED: (
        "Their brand, powered by us",
        "Their people and the public see %(brand)s. %(master)s is still named "
        "where it is a statement about who built the platform, and a "
        "“Powered by %(master)s” line shows on their sign-in page.",
    ),
    LEVEL_WHITE: (
        "Their brand only",
        "They see %(brand)s everywhere and %(master)s nowhere. This is the "
        "paid upgrade.",
    ),
}

#: Fallbacks for a platform database that has somehow lost its own brand. Never
#: reached in practice — the cockpit only ever runs on the master — but a
#: fallback that names nobody is better than one that invents a customer.
DEFAULT_MASTER_BRAND = "Payobook"
DEFAULT_MASTER_WEBSITE = "https://payobook.com"

#: Every key a level writes. Listed once, here, so that "what does changing the
#: level touch" has a single answer and so REVERSING a level is exactly "write
#: the other level's values for these same keys" — no key can be left behind
#: carrying the previous level's answer.
BRAND_KEYS = (
    "biz_debrand.brand_name",
    "biz_debrand.brand_website",
    "biz_debrand.product_name",
    "biz_debrand.powered_by",
    "biz_debrand.theme_color",
    "web_debranding.new_name",
    "web_debranding.new_title",
    "web_debranding.new_website",
    "web_debranding.new_documentation_website",
    "web.web_app_name",
)


def normal_level(level):
    """A level we are prepared to act on. Anything else is the default.

    Damage fails towards the SAFE answer, and here the safe answer is the one
    the customer has certainly paid for: our own product. A hand-edited row
    reading `whitelabel` must not silently hand somebody the paid upgrade.
    """
    return level if level in LEVELS else LEVEL_PRODUCT


def normal_website(url):
    """A brand website, with a scheme, and no trailing slash.

    `web_debranding` builds a documentation URL by concatenation and biz_debrand
    strips the scheme to get a host, so a value that is sometimes bare and
    sometimes not produces two different bugs at two different call sites.
    """
    url = (url or "").strip().rstrip("/")
    if not url:
        return ""
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    return url


def brand_params(level, tenant_name, tenant_url, master_brand=None,
                 master_website=None, theme_color=None):
    """``{parameter: value}`` for one customer at one level.

    Every key in :data:`BRAND_KEYS` is present in the result, always. A level
    that does not want a key sets it to ``''`` rather than omitting it, because
    omitting it is what makes a level change one-way: the customer would keep
    whatever the previous level wrote and nobody would ever see why.

    ``theme_color`` is optional and falls through to whatever the customer's
    database already carries when it is empty — a colour is a design decision
    somebody makes deliberately, not something a level should invent.
    """
    level = normal_level(level)
    master_brand = (master_brand or "").strip() or DEFAULT_MASTER_BRAND
    master_website = normal_website(master_website) or DEFAULT_MASTER_WEBSITE
    name = (tenant_name or "").strip()
    url = normal_website(tenant_url)

    if level == LEVEL_PRODUCT or not name or not url:
        # No name or no address is not a half-applied brand — it is the
        # default. A customer must never be left on a level that names them
        # inconsistently.
        brand, website, product, powered = (
            master_brand, master_website, "", "")
    elif level == LEVEL_POWERED:
        # Their name, and OUR name still standing wherever it is a genuine
        # statement about who built this — which is what leaving
        # `product_name` empty means (ERRORS E3-2).
        brand, website, product, powered = (name, url, "", master_brand)
    else:
        # The paid upgrade, and character for character what `rize` carries.
        brand, website, product, powered = (name, url, master_brand, "")

    params = {
        "biz_debrand.brand_name": brand,
        "biz_debrand.brand_website": website,
        "biz_debrand.product_name": product,
        "biz_debrand.powered_by": powered,
        "web_debranding.new_name": brand,
        "web_debranding.new_title": brand,
        "web_debranding.new_website": website,
        "web_debranding.new_documentation_website": website + "/documentation/",
        "web.web_app_name": brand,
    }
    # An empty colour means "leave whatever they have"; the caller drops the
    # key rather than writing a blank one over a real value.
    params["biz_debrand.theme_color"] = (theme_color or "").strip()
    return params


def level_summary(level, tenant_name, master_brand=None):
    """The one sentence the cockpit shows under the chosen level."""
    level = normal_level(level)
    title, blurb = LEVEL_LABELS[level]
    return title, blurb % {
        "master": (master_brand or "").strip() or DEFAULT_MASTER_BRAND,
        "brand": (tenant_name or "").strip() or "their own name",
    }


def website_name_should_change(level):
    """Whether the customer's `website` records should be renamed too.

    They carry the name a visitor reads in a browser tab on the PUBLIC site, so
    they follow the brand at both levels that give the customer their own —
    and they are left alone at `product`, where the master brand is already
    what the template wrote.
    """
    return normal_level(level) in (LEVEL_POWERED, LEVEL_WHITE)
