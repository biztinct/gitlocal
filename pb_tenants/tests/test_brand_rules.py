# -*- coding: utf-8 -*-
"""ERRORS E4-1 — what a customer's product is called, decided before it is written.

The decision is made on the platform's database and applied to the CUSTOMER's,
and no test can follow it across that boundary. So the decision is a pure
function and this file interrogates it — the same shape as `test_feature_rules`
and `test_billing_rules`, for the same reason.

THE REFERENCE IMPLEMENTATION IS A LIVE DATABASE, NOT THIS DOCUMENT. `rize` has
been running the full white-label level by hand since 2026-09-11. Its actual
parameters, read off the live database on 2026-09-12, are written into
`RIZE_LIVE` below and the rules are asserted against them character for
character. If this phase's code and that database disagree, the code is wrong.
"""
from odoo.tests import TransactionCase, tagged

from ..models.brand_rules import (
    BRAND_KEYS, LEVELS, LEVEL_POWERED, LEVEL_PRODUCT, LEVEL_WHITE,
    brand_params, level_summary, normal_level, normal_website,
    website_name_should_change,
)

MASTER = "Payobook"
MASTER_SITE = "https://payobook.com"

#: Read off the live `rize` database, 2026-09-12. The paid upgrade, as it
#: actually runs.
RIZE_LIVE = {
    "biz_debrand.brand_name": "Rize",
    "biz_debrand.brand_website": "https://rize.payobook.com",
    "biz_debrand.product_name": "Payobook",
    "web_debranding.new_name": "Rize",
    "web_debranding.new_title": "Rize",
    "web_debranding.new_website": "https://rize.payobook.com",
    "web_debranding.new_documentation_website": "https://rize.payobook.com/documentation/",
    "web.web_app_name": "Rize",
}

#: Read off the live `payobook_template` database the same day — the golden
#: template every new customer is cloned from, i.e. the default level.
TEMPLATE_LIVE = {
    "biz_debrand.brand_name": "Payobook",
    "biz_debrand.brand_website": "https://payobook.com",
    "web_debranding.new_name": "Payobook",
    "web_debranding.new_title": "Payobook",
    "web_debranding.new_website": "https://payobook.com",
    "web_debranding.new_documentation_website": "https://payobook.com/documentation/",
    "web.web_app_name": "Payobook",
}


def _params(level, name="Rize", url="https://rize.payobook.com", **kw):
    return brand_params(level, name, url, master_brand=MASTER,
                        master_website=MASTER_SITE, **kw)


@tagged("post_install", "-at_install")
class TestTheThreeLevels(TransactionCase):

    def test_01_full_white_label_reproduces_the_live_rize_database(self):
        """The only proof that matters: the code agrees with what runs."""
        out = _params(LEVEL_WHITE)
        for key, value in RIZE_LIVE.items():
            self.assertEqual(
                out[key], value,
                "the white-label level disagrees with the live rize database "
                "on %s" % key,
            )

    def test_02_the_default_level_reproduces_the_golden_template(self):
        out = _params(LEVEL_PRODUCT)
        for key, value in TEMPLATE_LIVE.items():
            self.assertEqual(out[key], value, key)
        self.assertEqual(
            out["biz_debrand.product_name"], "",
            "the default level must not switch the product rule on — our own "
            "name is what a default customer is supposed to see",
        )

    def test_03_powered_by_is_their_name_with_our_name_still_standing(self):
        out = _params(LEVEL_POWERED)
        self.assertEqual(out["biz_debrand.brand_name"], "Rize")
        self.assertEqual(out["web.web_app_name"], "Rize")
        self.assertEqual(
            out["biz_debrand.product_name"], "",
            "the middle level leaves the product rule OFF: genuine mentions of "
            "who built the platform are meant to stand",
        )
        self.assertEqual(out["biz_debrand.powered_by"], MASTER)

    def test_04_only_the_middle_level_asks_for_a_credit_line(self):
        self.assertEqual(_params(LEVEL_PRODUCT)["biz_debrand.powered_by"], "")
        self.assertEqual(_params(LEVEL_WHITE)["biz_debrand.powered_by"], "")
        self.assertEqual(_params(LEVEL_POWERED)["biz_debrand.powered_by"], MASTER)

    def test_05_the_paid_upgrade_is_the_only_one_that_hides_our_name(self):
        """One parameter is the whole difference, and it is the priced one."""
        powered = _params(LEVEL_POWERED)
        white = _params(LEVEL_WHITE)
        differing = {k for k in BRAND_KEYS if powered.get(k) != white.get(k)}
        self.assertEqual(
            differing,
            {"biz_debrand.product_name", "biz_debrand.powered_by"},
            "powered-by and white-label must differ only in whether our name "
            "is rewritten and whether the credit shows",
        )


@tagged("post_install", "-at_install")
class TestChangingTheLevelIsCompleteAndReversible(TransactionCase):

    def test_06_every_level_writes_every_key(self):
        """Changing a level must never leave a key behind.

        A level that omitted a key would leave the customer carrying the
        PREVIOUS level's answer for it, and the screen would show a choice the
        database does not make. Every level answers for every key, using '' for
        the ones it does not want.
        """
        for level in LEVELS:
            out = _params(level)
            self.assertEqual(
                set(out), set(BRAND_KEYS),
                "level %r does not answer for every key" % level,
            )

    def test_07_going_back_restores_exactly_the_default(self):
        there = _params(LEVEL_WHITE)
        back = _params(LEVEL_PRODUCT)
        self.assertNotEqual(there, back)
        self.assertEqual(back, _params(LEVEL_PRODUCT), "not deterministic")
        for key, value in TEMPLATE_LIVE.items():
            self.assertEqual(back[key], value, "%s was not restored" % key)

    def test_08_a_colour_is_only_written_when_somebody_chose_one(self):
        self.assertEqual(_params(LEVEL_WHITE)["biz_debrand.theme_color"], "")
        self.assertEqual(
            _params(LEVEL_WHITE, theme_color=" #CC9900 ")["biz_debrand.theme_color"],
            "#CC9900",
        )


@tagged("post_install", "-at_install")
class TestTheRulesFailSafe(TransactionCase):

    def test_09_an_unknown_level_is_the_default_never_the_paid_one(self):
        for bad in ("whitelabel", "WHITE", "", None, "free"):
            self.assertEqual(normal_level(bad), LEVEL_PRODUCT, repr(bad))
        self.assertEqual(
            _params("whitelabel")["biz_debrand.brand_name"], MASTER,
            "a mistyped level handed somebody the paid upgrade",
        )

    def test_10_a_customer_with_no_name_or_no_address_gets_the_default(self):
        """Half a brand is worse than none — it names them inconsistently."""
        self.assertEqual(
            brand_params(LEVEL_WHITE, "", "https://x.example",
                         master_brand=MASTER)["biz_debrand.brand_name"],
            MASTER,
        )
        self.assertEqual(
            brand_params(LEVEL_WHITE, "Acme", "",
                         master_brand=MASTER)["biz_debrand.brand_name"],
            MASTER,
        )

    def test_11_a_website_is_normalised_once_and_for_all(self):
        for given in ("rize.payobook.com", "https://rize.payobook.com/",
                      " https://rize.payobook.com ", "https://rize.payobook.com"):
            self.assertEqual(normal_website(given), "https://rize.payobook.com",
                             repr(given))
        self.assertEqual(normal_website(""), "")
        # …which is what keeps the documentation URL from growing two slashes.
        out = brand_params(LEVEL_WHITE, "Rize", "rize.payobook.com/",
                           master_brand=MASTER)
        self.assertEqual(out["web_debranding.new_documentation_website"],
                         "https://rize.payobook.com/documentation/")

    def test_12_the_platform_never_writes_its_own_name_down_twice(self):
        """With no master brand given, the fallback is still not a vendor."""
        out = brand_params(LEVEL_PRODUCT, "Acme", "https://acme.example")
        self.assertNotIn("odoo", out["biz_debrand.brand_name"].lower())
        self.assertTrue(out["biz_debrand.brand_name"])

    def test_13_only_a_customer_with_their_own_brand_gets_their_sites_renamed(self):
        self.assertFalse(website_name_should_change(LEVEL_PRODUCT))
        self.assertTrue(website_name_should_change(LEVEL_POWERED))
        self.assertTrue(website_name_should_change(LEVEL_WHITE))

    def test_14_the_summary_is_a_sentence_about_what_they_will_see(self):
        for level in LEVELS:
            title, blurb = level_summary(level, "Acme", master_brand=MASTER)
            self.assertTrue(title and blurb)
            self.assertNotIn("%(", blurb, "an unfilled slot reached the screen")
            self.assertNotIn("odoo", blurb.lower())


@tagged("post_install", "-at_install")
class TestTheTenantRecordAndTheCockpit(TransactionCase):
    """The thin layer over the rules: records in, parameters out."""

    def setUp(self):
        super().setUp()
        self.tenant = self.env["pb.tenant"].create({
            "name": "Acme Industries",
            "slug": "e4acme",
        })

    def test_15_a_new_customer_is_on_the_default_level(self):
        """The gap this phase closed, asserted as a default.

        Before E4 nothing wrote a brand parameter at all, so a customer kept
        whatever the golden template carried. Now the level is explicit, and
        the explicit answer for somebody who has bought nothing is our product.
        """
        self.assertEqual(self.tenant.brand_level, LEVEL_PRODUCT)
        self.assertFalse(self.tenant.brand_pushed_at,
                         "a brand-new record has told nobody anything yet")

    def test_16_the_empty_fields_fall_back_to_things_that_always_exist(self):
        self.tenant.brand_level = LEVEL_WHITE
        values = self.tenant.brand_values(master_brand=MASTER,
                                          master_website=MASTER_SITE)
        self.assertEqual(values["biz_debrand.brand_name"], "Acme Industries",
                         "an empty name must fall back to the company's own")
        self.assertEqual(values["biz_debrand.brand_website"],
                         self.tenant.brand_default_url())
        self.assertIn("e4acme.", values["biz_debrand.brand_website"])

    def test_17_an_explicit_name_and_address_win(self):
        self.tenant.write({
            "brand_level": LEVEL_WHITE,
            "brand_name": "Acme",
            "brand_website": "acme.example",
        })
        values = self.tenant.brand_values(master_brand=MASTER,
                                          master_website=MASTER_SITE)
        self.assertEqual(values["biz_debrand.brand_name"], "Acme")
        self.assertEqual(values["biz_debrand.brand_website"], "https://acme.example")
        self.assertEqual(values["biz_debrand.product_name"], MASTER)

    def test_18_the_cockpit_refuses_a_colour_that_is_not_one(self):
        from odoo.exceptions import UserError
        with self.assertRaises(UserError):
            self.env["pb.tenants"].tenant_set_brand(
                self.tenant.id, {"level": LEVEL_WHITE, "brand_color": "navy"})

    def test_19_the_service_never_calls_the_method_that_wipes_a_brand(self):
        """The dangerous one, pinned in the source.

        `_biz_debrand_apply_brand` is biz_debrand's own Save handler: it
        rewrites every website record's name AND replaces its favicon with the
        module's generic icon. Calling it on a customer would erase the
        branding this feature exists to give them.
        """
        import os
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "models", "service.py",
        )
        with open(path, encoding="utf-8") as fh:
            body = fh.read()
        for line in body.splitlines():
            code = line.split("#", 1)[0]
            self.assertNotIn(
                "_biz_debrand_apply_brand(", code,
                "provisioning must set the parameters directly, never call "
                "biz_debrand's Save handler on a customer",
            )
