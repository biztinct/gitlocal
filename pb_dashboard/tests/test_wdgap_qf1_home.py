# -*- coding: utf-8 -*-
"""WDGAP QF1 — "PayAI noticed" on Home (case 14, and the source checks the
card needs: word table parity, doors, no new dependency, no icon in a loop).
"""
import ast
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.pb_dashboard.models import home_data as home_module
from odoo.addons.pb_dashboard.models.home_data import _guards

from .test_home_front import _table_keys


def _read(module, rel):
    with open(os.path.join(get_module_path(module), rel), encoding='utf-8') as fh:
        return fh.read()


@tagged('post_install', '-at_install', 'wdgap_qf1')
class TestWdgapQf1Home(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.D = cls.env['pb.dashboard']
        cls.has_pulse = 'payroll.ai.pulse' in cls.env
        cls.js = _read('pb_dashboard', 'static/src/js/pb_dashboard.js')
        cls.tpl = _read('pb_dashboard', 'static/src/xml/pb_dashboard.xml')

    def _quiet(self):
        """Nothing open for this company: put every open alert away."""
        if self.has_pulse:
            self.env['payroll.ai.pulse'].sudo().search([
                ('state', 'in', ('new', 'acknowledged'))]).write(
                    {'state': 'resolved'})

    def _alert(self, **kw):
        vals = {'name': 'QF1 probe', 'severity': 'warning', 'category': 'cost',
                'state': 'new', 'company_id': self.env.company.id,
                'dedupe_key': '%s:cost:none' % self.env.company.id,
                'direction': 'up', 'deviation_pct': 14.2,
                'metric_value': 1140.0, 'baseline_value': 1000.0}
        vals.update(kw)
        return self.env['payroll.ai.pulse'].sudo().create(vals)

    # ------------------------------------------------------------ case 14
    def test_14a_an_open_alert_puts_the_card_on_home(self):
        if not self.has_pulse:
            self.skipTest('PayAI is not installed here')
        self._quiet()
        alert = self._alert()
        data = self.D.get_home_data()
        self.assertIn('payai_noticed', data)
        card = data['payai_noticed']
        self.assertTrue(card, 'no card with an open alert')
        row = card['alerts'][0]
        self.assertEqual(row['id'], alert.id)
        self.assertEqual(row['category'], 'cost')
        self.assertEqual(row['pct'], 14.2)
        self.assertIn('door', row)
        expected = 'explorer' if all(
            self.env.ref(x, raise_if_not_found=False)
            for x in home_module.PAYAI_DOORS['cost'][1]) else None
        self.assertEqual(row['door'], expected)
        self.assertNotIn('name', row)
        self.assertNotIn('details', row)
        self.assertIsInstance(data['timing_ms']['payai'], int)

    def test_14b_no_card_when_nothing_is_open(self):
        self._quiet()
        self.assertIsNone(self.D.get_home_data()['payai_noticed'])

    def test_14c_no_card_for_somebody_who_cannot_open_payslips(self):
        if not self.has_pulse:
            self.skipTest('PayAI is not installed here')
        self._quiet()
        self._alert()
        plain = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'QF1 home plain', 'login': 'qf1.home.plain@test.invalid',
            'company_id': self.env.company.id,
            'company_ids': [(6, 0, [self.env.company.id])],
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        if self.env['hr.payslip'].with_user(plain).has_access('read'):
            self.skipTest('every internal user reads payslips on this database')
        self.assertIsNone(self.D.with_user(plain).get_home_data()['payai_noticed'])

    def test_14d_no_card_and_no_error_without_payai(self):
        safe, optional = _guards(self.env)

        def absent(model, fn, default=None):
            if model == 'payroll.ai.pulse':
                return default
            return optional(model, fn, default)

        st = {'today': None, 'cos': self.env.companies.ids}
        self.assertIsNone(self.D._home_payai(st, safe, absent))

    def test_14e_a_broken_payai_never_blanks_home(self):
        if not self.has_pulse:
            self.skipTest('PayAI is not installed here')
        self._alert()
        Pulse = type(self.env['payroll.ai.pulse'])

        def boom(self, limit=3):
            raise RuntimeError('broken on purpose')

        from unittest.mock import patch
        with patch.object(Pulse, 'home_alerts', boom):
            data = self.D.get_home_data()
        self.assertIsNone(data['payai_noticed'])
        self.assertTrue(data['period'])

    # ------------------------------------------------------ source checks
    def test_14f_the_words_and_the_server_agree(self):
        kinds = _table_keys(self.js, 'PAYAI')
        self.assertEqual(kinds, set(home_module.PAYAI_KINDS))
        doors = _table_keys(self.js, 'PAYAI_DOORS')
        self.assertEqual(doors, {d for d, _x in home_module.PAYAI_DOORS.values()})
        # the client opens exactly the xmlids the server checked
        for door, xmlids in home_module.PAYAI_DOORS.values():
            hit = re.search(r'\n    %s: \{ xmlid: "([\w.]+)"' % door, self.js)
            self.assertTrue(hit, door)
            self.assertIn(hit.group(1), xmlids)

    def test_14g_no_new_dependency_and_no_icon_made_in_the_loop(self):
        for module in ('pb_dashboard', 'pb_home_hub'):
            manifest = ast.literal_eval(_read(module, '__manifest__.py'))
            self.assertNotIn('pb_payroll_ai_insights', manifest['depends'])
            self.assertNotIn('pb_learn', manifest['depends'])
        block = self.tpl[self.tpl.index('class="pbd-ai"'):]
        block = block[:block.index('</ul>')]
        self.assertNotIn('ic(', block, 'a new markup() per redraw in the loop')
        self.assertIn('payaiArrow', block)
        self.assertNotIn('Od' + 'oo', self.tpl)
