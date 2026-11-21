# -*- coding: utf-8 -*-
"""FS-16 (owner 2026-11-22) — the Form builder's "Taken off the screens" lists
only boxes that can come back; the ones that must stay off are not listed at
all (no greyed row, not counted), and the server still refuses them.
The 15 dead Vietnam boxes are gone from the product.

Test numbers match FS16_REPORT.md (test 5).
"""
import unittest

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo.addons.pb_form_studio_people.models.form_studio import HOST, MODEL

STAY_OFF = ('account_number', 'bank_name', 'contract_type_id', 'structure_type_id')
DELETED = ('vn_foreign_insurance_exempt', 'vn_si_number', 'vn_si_effective_date',
           'vn_hi_number', 'vn_hi_effective_date', 'vn_ui_number', 'vn_ui_effective_date',
           'vn_tax_table_id', 'vn_tax_effective_date', 'vn_employer_insurance_cost',
           'vn_employee_insurance_cost', 'vn_total_insurance_contribution',
           'vn_personal_tax_rate', 'vn_monthly_tax_allowance', 'vn_dependent_tax_allowance')


@tagged('post_install', '-at_install')
class TestFs16BuilderList(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.form.studio']
        cls.admin = new_test_user(
            cls.env, 'fs16_admin', name='DEMO FS16 Admin',
            groups='base.group_user,base.group_system,hr.group_hr_manager,'
                   'om_hr_payroll.group_hr_payroll_manager')

    def setUp(self):
        super().setUp()
        if not hasattr(self.env[MODEL], '_pb_tidy_rules'):
            raise unittest.SkipTest('the built-in country rules are not installed here')

    def st(self):
        return self.Studio.with_user(self.admin)

    def removed_here(self):
        from odoo.addons.pb_employee_form_tidy.models.form_rules import FORM_RULES, REMOVE
        Model = self.env[MODEL]
        return {n for n, r in FORM_RULES.items() if r == REMOVE and n in Model._fields}

    def test_05a_studio_lists_only_boxes_that_can_come_back(self):
        data = self.st().get_studio(HOST)
        flds = data['fields']
        rows = flds.values() if isinstance(flds, dict) else flds
        names = {r.get('name') for r in rows}
        for name in STAY_OFF:
            self.assertNotIn(name, names, '%s must not be listed' % name)
        off = {r.get('name') for r in rows
               if (r.get('stdbox') or {}).get('removed') and (r.get('stdbox') or {}).get('off')}
        self.assertFalse([r for r in rows if (r.get('stdbox') or {}).get('comeback')],
                         'no greyed "stays off" row')
        stay = set(self.Studio._pbfs_std_comeback(MODEL))
        self.assertEqual(off, self.removed_here() - stay)

    def test_05b_library_lists_only_boxes_that_can_come_back(self):
        lib = self.st().library()
        std = [r for r in lib['std'] if r.get('model') == MODEL]
        names = {r['name'] for r in std}
        for name in STAY_OFF:
            self.assertNotIn(name, names)
        off = {r['name'] for r in std if r['stdbox'].get('removed') and r['stdbox'].get('off')}
        stay = set(self.Studio._pbfs_std_comeback(MODEL))
        self.assertEqual(off, self.removed_here() - stay)
        # 13 on a site without the three Payroll facts boxes, 16 with them
        expected = 16 if 'pb_vn_enrol_family_health' in self.env[MODEL]._fields else 13
        if 'level_of_health_compensation' in self.env[MODEL]._fields:
            self.assertEqual(len(off), expected)

    def test_05c_direct_call_still_refused(self):
        for name in STAY_OFF:
            if name not in self.env[MODEL]._fields:
                continue
            with self.assertRaises(UserError):
                self.st().update_standard(MODEL, name, {'std_show': 'all'})

    def test_05d_not_offered_as_a_placeable_box(self):
        offered = set(self.Studio._pbfs_people_standard_fields())
        self.assertFalse(offered & set(STAY_OFF))

    def test_06_dead_vietnam_boxes_are_gone(self):
        Model = self.env[MODEL]
        for name in DELETED:
            self.assertNotIn(name, Model._fields)
        # the other model's own "Tax Table" is untouched
        if 'hr.formula.config' in self.env and 'pb_hr_payroll_vietnam' in self.env.registry._init_modules:
            self.assertIn('vn_tax_table_id', self.env['hr.formula.config']._fields)
