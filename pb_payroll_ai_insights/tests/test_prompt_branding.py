# -*- coding: utf-8 -*-
"""ERRORS E4-3 — what the assistant is allowed to believe about itself.

THIS IS THE ONE SURFACE NO REWRITE RULE CAN REACH. Every other leak in this
programme was a string somebody wrote, sitting in a file or a column, waiting
for a seam to rewrite it on its way to the screen. "Welcome to Payobook",
greeting a Rize employee, is in no file and no column: the assistant wrote it,
in its own words, at the moment it answered. It arrives long after the last
seam has run. So the prompt is the only place it can be fixed, and these tests
are assertions about the prompt.

TWO NAMES, TWO DIFFERENT FIXES, AND THE TESTS ARE DIFFERENT TOO:

  * OUR product name is PARAMETERISED, so the test is that the slot is there
    and that filling it leaves the customer's brand behind and nothing else.
  * The VENDOR's name is DELETED, so the test is that the word is not in the
    prompt at all — not reworded, not parameterised, gone. A prompt that never
    carried the fact cannot leak it.

WHAT THESE TESTS CANNOT DO. They prove the assistant is not TOLD the vendor's
name. They cannot prove it never says one, because a large model has its own
knowledge of the world and could guess from the shape of a screen. That is why
IDENTITY_RULES exists as well, and why the phase's acceptance test is
behavioural — the live assistant, asked outright, on rize — and not this file.
"""
import os
import re

from odoo.tests import TransactionCase, tagged

from ..models.payroll_ai_engine import (
    BRAND_SLOT,
    IDENTITY_RULES,
    INTENT_CLASSIFICATION_PROMPT,
    ONBOARDING_SYSTEM_PROMPT,
    PAYAI_SYSTEM_PROMPT,
    brand_prompt,
)

#: Written as a pattern so this file's own prose is not mistaken for a hit.
VENDOR = re.compile(r"\bodoo\w*", re.I)

#: The one literal that is allowed to survive: the NAME OF A RECORD in the
#: demo world, not a statement about what the product is called. ER23 — a
#: record's own name is data and is never rewritten, and there is no company
#: called "Rize Vietnam JSC" to rename it to.
DEMO_COMPANY = "Payobook Vietnam JSC"

PROMPTS = {
    "PAYAI_SYSTEM_PROMPT": PAYAI_SYSTEM_PROMPT,
    "ONBOARDING_SYSTEM_PROMPT": ONBOARDING_SYSTEM_PROMPT,
    "INTENT_CLASSIFICATION_PROMPT": INTENT_CLASSIFICATION_PROMPT,
    "IDENTITY_RULES": IDENTITY_RULES,
}


@tagged("post_install", "-at_install")
class TestThePromptsNameNobody(TransactionCase):

    def test_01_no_prompt_tells_the_assistant_what_the_platform_is_built_on(self):
        """The vendor clause is DELETED. This is the item's whole point."""
        for name, prompt in PROMPTS.items():
            found = VENDOR.findall(prompt)
            self.assertFalse(
                found,
                "%s still names the platform vendor (%s). It must be removed, "
                "not reworded: the assistant cannot repeat a fact it was never "
                "given." % (name, found),
            )

    def test_02_the_product_name_is_a_slot_not_a_literal(self):
        for name in ("PAYAI_SYSTEM_PROMPT", "ONBOARDING_SYSTEM_PROMPT"):
            prompt = PROMPTS[name]
            self.assertIn(
                BRAND_SLOT, prompt, "%s no longer reads the brand at all" % name
            )
            # Every remaining occurrence of the product name must be the demo
            # company's — a record name, not a product name.
            residue = prompt.replace(DEMO_COMPANY, "")
            self.assertNotIn(
                "Payobook",
                residue,
                "%s writes the master product name down instead of reading the "
                "brand — a white-labelled customer would be told they are "
                "using our product" % name,
            )

    def test_03_both_system_prompts_carry_the_identity_rules(self):
        """Deleting the fact is necessary; the instruction makes it reliable."""
        for name in ("PAYAI_SYSTEM_PROMPT", "ONBOARDING_SYSTEM_PROMPT"):
            self.assertIn(
                IDENTITY_RULES,
                PROMPTS[name],
                "%s does not tell the assistant to refuse the question "
                "'what is this built on?'" % name,
            )

    def test_04_filling_the_slot_leaves_the_customers_brand_and_no_slot(self):
        for name in ("PAYAI_SYSTEM_PROMPT", "ONBOARDING_SYSTEM_PROMPT"):
            out = brand_prompt(PROMPTS[name], "Rize")
            self.assertNotIn(BRAND_SLOT, out, "%s left an unfilled slot" % name)
            self.assertIn("Rize", out)
            self.assertNotIn(
                "Payobook",
                out.replace(DEMO_COMPANY, ""),
                "%s still says our name to a white-labelled customer" % name,
            )

    def test_05_the_substitution_cannot_raise_on_the_json_in_the_prompt(self):
        """These prompts are full of `{}` and could meet a `%`. A branding
        change must never be able to take the assistant down."""
        for prompt in PROMPTS.values():
            brand_prompt(prompt, "100% Brand {weird}")  # must not raise
        self.assertEqual(brand_prompt("x %(brand)s", ""), "x this product")
        self.assertEqual(brand_prompt("x %(brand)s", None), "x this product")

    def test_06_the_classifier_prompt_still_formats(self):
        """It is sent through `.format`, so a stray brace would break it."""
        out = INTENT_CLASSIFICATION_PROMPT.format(message="how do I run payroll")
        self.assertIn("how do I run payroll", out)


@tagged("post_install", "-at_install")
class TestTheEngineBrandsEveryPromptItSends(TransactionCase):

    def setUp(self):
        super().setUp()
        self.engine = self.env["payroll.ai.engine"]

    def test_07_the_brand_is_read_from_this_database(self):
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("biz_debrand.brand_name", "Rize")
        self.assertEqual(self.engine._brand_name(), "Rize")
        self.assertIn("Rize", self.engine._system_prompt(PAYAI_SYSTEM_PROMPT))

    def test_08_an_unbranded_database_never_invents_our_name(self):
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("biz_debrand.brand_name", "")
        icp.set_param("web_debranding.new_name", "")
        name = self.engine._brand_name()
        self.assertTrue(name, "the brand must always resolve to something")
        self.assertNotIn("odoo", name.lower())
        # It falls through to the company's own name, which is right: a
        # customer being told the product is called after their own company is
        # a far smaller error than being told it is called after us.
        self.assertEqual(name, self.env.company.name)

    def test_09_every_send_site_goes_through_the_branding_helper(self):
        """Source-level: one un-branded send is one leak.

        The four sites are the four answer paths (data, knowledge, onboarding,
        general). Asserting on the source rather than on a mock keeps this
        honest when somebody adds a fifth.
        """
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "models", "payroll_ai_engine.py",
        )
        with open(path, encoding="utf-8") as fh:
            body = fh.read()
        # Strip the declarations themselves so only the SEND sites are counted.
        sends = re.findall(
            r'"content":\s*(?:\n\s*)?([A-Za-z_.()]*(?:PAYAI_SYSTEM_PROMPT|'
            r'ONBOARDING_SYSTEM_PROMPT)\)?)',
            body,
        )
        self.assertTrue(sends, "no prompt send sites found — has the shape changed?")
        for site in sends:
            self.assertTrue(
                site.startswith("self._system_prompt("),
                "a system prompt is sent unbranded: %r" % site,
            )
