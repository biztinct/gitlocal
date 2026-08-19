# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""W87 — every ESS portal icon must be passed as a t-value, never a t-set body.

A `t-set` BODY is rendered QWeb. On a `website=True` page the editor's
`inherit_branding` wraps rendered text in `data-oe-*` markup, so
`<t t-set="icon">download</t>` reaches `ess_icon` as Markup carrying branding
attributes, every `icon == '...'` comparison is False, and the call site falls
through to the else-branch. This module shipped that way from the start; it was
invisible because the else-branch is a plausible document sheet, so the
download / alert / calculator / verified icons all rendered as the same glyph.
"""

import os
import re

from odoo.tests import TransactionCase, tagged

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TEMPLATES = os.path.join(_HERE, 'views', 'portal_templates.xml')

# a path that appears in the 'download' branch and nowhere else in ess_icon
_DOWNLOAD_ONLY_PATH = 'M12 15V3'


def _read_templates():
    with open(_TEMPLATES, encoding='utf-8') as fh:
        return fh.read()


def _strip_comments(source):
    """The header comment quotes the forbidden pattern in order to explain it
    (W48's corollary: a word-shaped gate fails on its own documentation)."""
    return re.sub(r'<!--.*?-->', '', source, flags=re.S)


@tagged('post_install', '-at_install')
class TestPortalIcons(TransactionCase):

    # ----------------------------------------------------------- static gates
    def test_no_icon_is_passed_as_a_t_set_body(self):
        arch = _strip_comments(_read_templates())
        offenders = re.findall(r'<t t-set="icon"\s*>[^<]*</t>', arch)
        self.assertEqual(
            offenders, [],
            "W87: pass the icon name with t-value=\"'name'\". A t-set body is "
            "rendered markup and website branding turns it into a value no "
            "comparison in ess_icon can ever match.")

    def test_every_call_site_uses_a_plain_string_literal(self):
        arch = _strip_comments(_read_templates())
        call_sites = re.findall(r'<t t-set="icon"[^>]*/>', arch)
        self.assertTrue(call_sites, "the portal must still draw icons")
        for site in call_sites:
            self.assertRegex(
                site, r"""t-value="'[a-z-]+'\"""",
                "an icon name must be a plain string literal: %s" % site)

    def test_every_name_used_is_one_the_template_can_draw(self):
        """A door that can only ever produce the fallback is W29's shape — the
        icon still renders, so a typo is indistinguishable from a design
        choice. 'file' is the one deliberate exception: the else-branch IS the
        document sheet it asks for, and the header comment says so."""
        arch = _strip_comments(_read_templates())
        drawn = set(re.findall(r"""icon == '([a-z-]+)'""", arch))
        used = set(re.findall(r"""t-set="icon"[^>]*t-value="'([a-z-]+)'\"""", arch))
        self.assertTrue(drawn, "ess_icon must still have branches")
        self.assertEqual(
            used - drawn - {'file'}, set(),
            "these names fall through to the generic sheet: %s" % (used - drawn))

    def test_the_icon_template_still_draws_distinct_glyphs(self):
        """The complement of the gates above (W64): a template that drew
        nothing, or drew one glyph for every name, would pass all of them."""
        icon_tpl = re.search(
            r'<template id="ess_icon".*?</template>', _read_templates(), re.S)
        self.assertTrue(icon_tpl, "ess_icon must exist")
        branches = re.findall(r'<t t-(?:if|elif)="icon == [^>]*>(.*?)</t>',
                              icon_tpl.group(0))
        self.assertGreaterEqual(len(branches), 5)
        self.assertEqual(len(set(branches)), len(branches),
                         "two icon names drawing the identical glyph is the "
                         "bug this suite exists for, one layer down")

    # ------------------------------------------------------ the mechanism
    def _probe(self, call):
        view = self.env['ir.ui.view'].create({
            'name': 'w87 probe', 'type': 'qweb',
            'arch': '<div>%s</div>' % call,
        })
        # inherit_branding is what a website=True page renders with; it is the
        # whole difference between the two call forms.
        return self.env['ir.qweb']._render(view.id, {}, inherit_branding=True)

    def test_a_t_set_body_cannot_reach_the_right_branch(self):
        """Assert the MECHANISM, not just the source (W78): if a future Odoo
        stopped branding t-set bodies this would fail, and the rule could be
        retired on evidence rather than on memory."""
        body_form = self._probe(
            '<t t-call="pb_me_portal.ess_icon">'
            '<t t-set="icon">download</t></t>')
        self.assertNotIn(
            _DOWNLOAD_ONLY_PATH, body_form,
            "a branded t-set body matching 'download' would mean W87 no longer "
            "applies — re-check the rule before relaxing the gates above")

    def test_a_t_value_reaches_the_right_branch_under_branding(self):
        value_form = self._probe(
            '<t t-call="pb_me_portal.ess_icon">'
            "<t t-set=\"icon\" t-value=\"'download'\"/></t>")
        self.assertIn(_DOWNLOAD_ONLY_PATH, value_form,
                      "the pattern this module now ships must survive branding")
