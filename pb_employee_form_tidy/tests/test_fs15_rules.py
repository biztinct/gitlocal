# -*- coding: utf-8 -*-
"""FS-15 (R31) — the table the employee form applies can carry the
administrator's "Shown for" of a box: shown for everyone, hidden, one
country, several countries, and "people with no Country of Work too". With
no setting the form is exactly the built-in table's (silent upgrade).
"""
from lxml import etree

from odoo.tests import TransactionCase, tagged
from odoo.tests.common import BaseCase

from ..models import form_rules
from ..models.form_rules import REMOVE, apply_rules

ARCH = """<form><sheet><notebook>
  <page string="Insurance">
    <group string="A"><field name="vn_a"/><field name="vn_b"/></group>
    <group string="B"><field name="old_1"/><field name="old_2"/></group>
  </page>
  <page string="Mixed">
    <group><field name="id_x"/><field name="in_y"/></group>
  </page>
</notebook></sheet></form>"""


def _arch():
    return etree.fromstring(ARCH)


def _attr(arch, xpath):
    return arch.xpath(xpath)[0].get('invisible')


@tagged('post_install', '-at_install', 'tidy_e', 'fs15')
class TestFs15Rules(BaseCase):

    def test_built_in_table_unchanged(self):
        rules = {'vn_a': 'VN', 'vn_b': 'VN', 'old_1': REMOVE, 'old_2': REMOVE,
                 'id_x': 'ID', 'in_y': 'IN'}
        arch = _arch()
        apply_rules(arch, rules)
        self.assertEqual(_attr(arch, "//field[@name='vn_a']"), "payroll_country != 'VN'")
        self.assertEqual(_attr(arch, "//group[@string='B']"), '1')
        self.assertEqual(_attr(arch, "//page[@string='Insurance']"), "payroll_country != 'VN'")
        # two different countries in one group: each box decides, as before
        self.assertIsNone(arch.xpath("//page[@string='Mixed']/group")[0].get('invisible'))

    def test_widened_box_opens_its_sections_for_the_new_country(self):
        rules = {'vn_a': frozenset({'VN', 'ID'}), 'vn_b': 'VN', 'old_1': 'VN', 'old_2': REMOVE,
                 'id_x': 'ID', 'in_y': 'IN'}
        arch = _arch()
        apply_rules(arch, rules)
        self.assertEqual(_attr(arch, "//field[@name='vn_a']"), "payroll_country not in ['ID', 'VN']")
        self.assertEqual(_attr(arch, "//group[@string='A']"), "payroll_country not in ['ID', 'VN']")
        # a box shown again for Vietnam opens its old group for Vietnam
        self.assertEqual(_attr(arch, "//field[@name='old_1']"), "payroll_country != 'VN'")
        self.assertEqual(_attr(arch, "//group[@string='B']"), "payroll_country != 'VN'")
        self.assertEqual(_attr(arch, "//page[@string='Insurance']"), "payroll_country not in ['ID', 'VN']")

    def test_people_with_no_country_of_work(self):
        rules = {'vn_a': frozenset({'VN', None})}
        arch = _arch()
        apply_rules(arch, rules)
        self.assertEqual(_attr(arch, "//field[@name='vn_a']"),
                         "payroll_country and payroll_country not in ['VN']")


@tagged('post_install', '-at_install', 'tidy_e', 'fs15')
class TestFs15Table(TransactionCase):

    def test_no_setting_is_the_built_in_table(self):
        Emp = self.env['hr.employee']
        if 'pb.form.studio' in self.env and hasattr(self.env['pb.form.studio'], '_pbfs_std_tidy_overrides'):
            if self.env['pb.form.studio']._pbfs_std_tidy_overrides('hr.employee'):
                self.skipTest('a setting exists on this database')
        self.assertEqual(Emp._pb_tidy_rules(), form_rules.FORM_RULES)

    def test_form_builder_reads_the_removed_boxes_where_they_were(self):
        rules = self.env['hr.employee'].with_context(pbfs_std_raw=True)._pb_tidy_rules()
        self.assertNotIn(REMOVE, rules.values())
        self.assertEqual(rules.get('vn_payroll_tax_summary'), 'VN')
