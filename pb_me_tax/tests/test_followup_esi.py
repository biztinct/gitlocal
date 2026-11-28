# -*- coding: utf-8 -*-
"""WDGAP S2-D follow-up ESI — India ESI number, HR-only like the
provident-fund number (TD2). The field name `pb_in_esi_number` is the first
name the India ESI monthly file probes (S2-B2 `fund_in.py`)."""
import json

from odoo.exceptions import AccessError, UserError
from odoo.modules.module import get_module_path
from odoo.tests import tagged

from .common import TaxCase, decide


@tagged('post_install', '-at_install', 'wdgap_s2d')
class TestS2dEsi(TaxCase):

    def test_esi_1_hr_keeps_it_others_cannot_read(self):
        self.emp.with_user(self.hr).write({'pb_in_esi_number': '3100123456'})
        self.assertEqual(self.emp.with_user(self.hr).pb_in_esi_number, '3100123456')
        self.env.flush_all()
        self.env.invalidate_all()
        for user in (self.manager_user, self.pay_only):
            with self.assertRaises(AccessError, msg=user.login):
                self.env['hr.employee'].with_user(user).browse(self.emp.id).read(
                    ['pb_in_esi_number'])

    def test_esi_2_read_only_and_masked_for_the_employee(self):
        self._pay_by(self.emp, 'IN')
        self.emp.sudo().write({'pb_in_esi_number': '3100123456'})
        data = self.emp.with_user(self.portal).sudo()._pbtx_portal_data()
        rows = {r['key']: r for r in data['rows']}
        self.assertEqual(rows['esi']['value'], '•••• 3456')
        self.assertIsNone(rows['esi']['kind'], 'not proposable')
        self.assertEqual(rows['esi']['hint'], 'Kept by HR')
        self.assertNotIn('3100123456', json.dumps(data, default=str))
        # outside India it is not shown
        self._pay_by(self.emp, 'SG')
        keys = {r['key'] for r in
                self.emp.with_user(self.portal).sudo()._pbtx_portal_data()['rows']}
        self.assertNotIn('esi', keys)

    def test_esi_3_forged_requests_refused_or_ignored(self):
        self._pay_by(self.emp, 'IN')
        self.emp.sudo().write({'pb_in_esi_number': '3100123456'})
        for kind in ('tax_esi', 'pb_in_esi_number'):
            with self.assertRaises(UserError, msg=kind):
                self._ask(kind, {'t_number': '9999999999'}, upload=self._pdf())
        req = self._ask('tax_number', {'t_number': 'ABCDE1234F',
                                       'pb_in_esi_number': '9999999999',
                                       't_esi': '9999999999'}, upload=self._pdf())
        decide(self.env, req)
        self.assertEqual(self.emp.sudo().pb_in_esi_number, '3100123456')

    def test_esi_4_full_details_india_group_and_translations(self):
        self._pay_by(self.emp, 'IN')
        self.emp.sudo().write({'pb_in_esi_number': '3100123456'})
        details = self.env['pb.people'].with_user(self.hr)._e360_details(
            self.emp.with_user(self.hr), True)
        india = {g['key']: g for g in details['pay']}['in']
        self.assertIn('pb_in_esi_number', [r['key'] for r in india['rows']])
        try:
            import polib
        except ImportError:
            self.skipTest('polib is not installed')
        for module in ('pb_me_tax', 'pb_employee_vault'):
            for lang in ('vi_VN', 'id_ID'):
                po = {e.msgid: e.msgstr for e in polib.pofile(
                    get_module_path(module) + '/i18n/%s.po' % lang)}
                self.assertTrue(po.get('ESI number'), (module, lang))
