# -*- coding: utf-8 -*-
"""The Vietnamese payslip document: every line present, every figure live.

The thing that can go silently wrong here is a MARKER. A label is visible the
moment anybody looks at the page; a marker that names a rule this database does
not have, or that the renderer's pattern does not recognise, prints as a dash or
as raw `{{…}}` text on an employee's payslip. So the assertions below check the
markers against the two things that actually resolve them — the configuration's
own rule IDs and `hr.formula.config._payslip_meta_token_re` — rather than
against a copy of the expected output.
"""

from markupsafe import escape

from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_payroll_mapping_vn.models.vn_payslip_layout import (
    VN_PAYSLIP_SECTIONS, VN_PAYSLIP_TOTALS,
)


@tagged('post_install', '-at_install')
class TestVnPayslipLayout(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.env['hr.formula.config'].create({
            'name': 'VN payslip probe', 'code': 'VN_PAYSLIP_PROBE',
            'country_code': 'VN', 'state': 'draft',
        })
        cls.rules = {}
        for sequence, code in enumerate(
                ['BASIC', 'DEPS', 'STDDAYS', 'PAIDDAYS', 'SALARYPAID',
                 'TRANSPORT', 'PHONEALLOW', 'OTHERTAX', 'ADJADD', 'SIDED',
                 'HIDED', 'UIDED', 'UNIONDUES', 'PIT', 'NET'], start=1):
            cls.rules[code] = cls.env['hr.formula.rule'].create({
                'config_id': cls.config.id, 'name': code, 'code': code,
                'column_type': 'input', 'sequence': sequence * 10,
            })

    # ------------------------------------------------------------- the paper
    def test_01_every_label_is_printed(self):
        html = self.config.pb_build_vn_payslip_layout()
        # Labels are escaped on the way into the document — "Employee's name"
        # is stored as "Employee&#39;s name" — so the haystack has to be asked
        # the same question the browser will.
        def printed(label):
            return str(escape(label)) in html

        for _vi, english, pairs in VN_PAYSLIP_SECTIONS:
            self.assertTrue(printed(english), "section %r is missing" % english)
            for pair in [p for row in pairs for p in row if p]:
                self.assertTrue(printed(pair[1]), "line %r is missing" % pair[1])
                self.assertTrue(printed(pair[0]),
                                "Vietnamese line %r is missing" % pair[0])
        for _vi, english, _code in VN_PAYSLIP_TOTALS:
            self.assertTrue(printed(english))

    def test_02_every_component_marker_names_a_real_rule(self):
        html = self.config.pb_build_vn_payslip_layout()
        referenced = self.config._payslip_content_rule_ids(html)
        self.assertTrue(referenced, "the document must quote live components")
        self.assertLessEqual(referenced, set(self.config.rule_ids.ids),
                             "a marker may only name a rule of THIS scheme")
        # …and the ones the paper names are the ones that resolved.
        for code in ('NET', 'PIT', 'SIDED', 'STDDAYS', 'BASIC', 'DEPS'):
            self.assertIn('{{pb_component:%s:value}}' % self.rules[code].id, html,
                          "%s must be a live figure, not typed text" % code)

    def test_03_every_meta_marker_is_one_the_payslip_can_fill(self):
        """A key the renderer does not know prints as raw text on the payslip."""
        html = self.config.pb_build_vn_payslip_layout()
        pattern = self.config._payslip_meta_token_re
        found = {match.group(1) for match in pattern.finditer(html)}
        self.assertIn('employee_name', found)
        self.assertIn('position', found)
        self.assertIn('contract_type', found)
        self.assertIn('month', found)
        # Nothing shaped like a meta marker escaped the recognised set.
        import re
        every = set(re.findall(r'\{\{pb_meta:([a-z_]+)\}\}', html))
        self.assertEqual(every, found,
                         "unrecognised markers would print as literal text")

    def test_04_a_missing_component_leaves_the_line_blank(self):
        """A scheme without a phone allowance still gets a payslip."""
        self.rules['PHONEALLOW'].unlink()
        html = self.config.pb_build_vn_payslip_layout()
        self.assertIn('Phone allowance', html, "the line stays on the paper")
        self.assertNotIn('{{pb_component:', html.split('Phone allowance')[1][:120],
                         "…with an empty box, never a marker nothing replaces")

    def test_05_the_dollar_line_is_deliberately_empty(self):
        """Owner ruling 2026-09-11 — no rate, so no invented figure."""
        html = self.config.pb_build_vn_payslip_layout()
        self.assertIn('Final Net pay (USD)', html)
        tail = html.split('Final Net pay (USD)')[1]
        self.assertNotIn('{{pb_component:', tail)

    # ------------------------------------------------------------- applying
    def test_06_apply_writes_the_document_and_reports_gaps(self):
        self.rules['ADJADD'].unlink()
        report = self.config.pb_apply_vn_payslip_layout()
        self.assertTrue(self.config.payslip_layout_html)
        self.assertEqual(report[0]['missing'], ['ADJADD'],
                         "applying must say which lines it could not fill")

    def test_07_the_letterhead_is_the_callers(self):
        html = self.config.pb_build_vn_payslip_layout(
            letterhead=['Acme Vietnam Company Ltd', 'Enterprise code: 123'],
            footer=['Registered Address: somewhere'])
        self.assertIn('Acme Vietnam Company Ltd', html)
        self.assertIn('Enterprise code: 123', html)
        self.assertIn('Registered Address: somewhere', html)
        self.assertNotIn(self.env.company.name, html.split('<h2')[0],
                         "an explicit letterhead replaces the company's name")

    def test_08_it_survives_the_html_field(self):
        """Odoo sanitises this field — the styles and colspans must survive."""
        self.config.pb_apply_vn_payslip_layout()
        stored = self.config.payslip_layout_html
        self.assertIn('table-layout:fixed', stored)
        self.assertIn('colspan="4"', stored)
        self.assertIn('{{pb_component:%s:value}}' % self.rules['NET'].id, stored)
        self.assertIn('{{pb_meta:employee_name}}', stored)
