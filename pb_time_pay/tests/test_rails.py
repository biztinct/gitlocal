# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""S5-B T26–T33: the rails — holidays, the pay data file notice, rights,
silent install, white-label, the click-only rule."""

import os
import re

from odoo.exceptions import AccessError
from odoo.modules.module import get_module_path
from odoo.tests import tagged

from odoo.addons.pb_time_pay import post_init_hook

from .common import TimePayCase


def _read(*parts):
    path = os.path.join(get_module_path(parts[0]), *parts[1:])
    with open(path, encoding='utf-8') as fh:
        return fh.read()


@tagged('post_install', '-at_install', 'wdgap_s5b')
class TestRails(TimePayCase):

    def test_t26_the_grid_reads_the_real_public_holidays(self):
        """Ledger S5-3: before, always an empty set."""
        self._closure(self.mon)
        days = self.env['hr.attendance.weekentry']._holidays(
            self.week_start, self.sat)
        self.assertIn(self.mon, days)
        Grid = self.env['hr.attendance.weekentry']
        cfg = self.env['hr.overtime.config'].sudo().search(
            [('overtime_type', '=', 'holiday'),
             ('company_id', '=', self.company.id), ('active', '=', True)],
            limit=1)
        self.assertTrue(Grid._config_applies(cfg, self.mon, days))

    def test_t27_pay_data_file_schemes_are_named_with_their_figures(self):
        cfg = self.env['hr.formula.config'].sudo().create({
            'name': 'S5B File scheme', 'code': 'S5BFILE', 'country_code': 'VN',
            'company_id': self.company.id})
        rule = self.env['hr.formula.rule'].sudo().create({
            'config_id': cfg.id, 'name': 'Basic', 'code': 'BASIC',
            'column_type': 'input'})
        if 'hr.formula.rule.source' not in self.env:
            self.skipTest('no rule sources on this build')
        self.env['hr.formula.rule.source'].sudo().create({
            'rule_id': rule.id, 'kind': 'excel', 'key': 'Basic salary'})
        self._approved(self.shifty, self.mon, 2.0)
        self._approved(self.shifty, self.tue, 1.0, choice='time_off')
        payload = self._payload(self.manager_user)
        self.assertIn('S5B File scheme', payload['file_schemes'])
        rows = {r['employee_id']: r for r in payload['file_month']['rows']}
        self.assertEqual(rows[self.shifty.id]['weekday'], 2.0,
                         'hours given as time off are not for the file')

    def test_t28_an_empty_week_is_quiet(self):
        payload = self._payload(self.manager_user)
        self.assertEqual(payload['suggestions'], [])
        self.assertEqual(payload['late'], [])
        self.assertEqual(payload['late_stats']['open'], 0)
        empty = self.env['hr.employee']
        self.assertEqual(self.TP._week(empty, self.mon, self.sat), ([], []))

    def test_t29_rights(self):
        with self.assertRaises(AccessError):
            self.TP.with_user(self._mk_user('s5b_nobody', []))._close_payload(
                self.dept.id, self.week_start.isoformat(), '')
        payload = self._payload(self.officer_user)
        self.assertFalse(payload['can_decide'])
        portal = self.env['res.users'].sudo().with_context(
            no_reset_password=True).create({
                'name': 's5b portal', 'login': 's5b_portal',
                'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])]})
        row = self.Late.sudo().create({
            'employee_id': self.shifty.id, 'company_id': self.company.id,
            'date': self.mon, 'kind': 'late', 'minutes': 20,
            'state': 'confirmed'})
        with self.assertRaises(AccessError):
            row.with_user(portal).read(['minutes'])
        with self.assertRaises(AccessError):
            self.Late.with_user(self.manager_user).create({
                'employee_id': self.shifty.id, 'company_id': self.company.id,
                'date': self.tue, 'kind': 'late', 'minutes': 5,
                'state': 'excused'})

    def test_t30_install_is_silent(self):
        crons = self.env['ir.cron'].sudo().with_context(active_test=False).search(
            [('ir_actions_server_id.model_id.model', 'in',
              ('pb.time.pay', 'pb.time.late', 'pb.time.ot.dismiss'))])
        self.assertFalse(crons, 'no scheduled job')
        manifest = _read('pb_time_pay', '__manifest__.py')
        self.assertNotIn("'demo'", manifest)
        self.assertFalse(os.path.isdir(os.path.join(
            get_module_path('pb_time_pay'), 'data')), 'no data files')

    def test_t31_the_collision_scan_warns(self):
        cfg = self.env['hr.formula.config'].sudo().create({
            'name': 'S5B Shadow', 'code': 'S5BSHADOW', 'country_code': 'VN',
            'company_id': self.company.id})
        self.env['hr.formula.rule'].sudo().create({
            'config_id': cfg.id, 'name': 'Shadow', 'code': 'LATEMI',
            'column_type': 'input'})
        with self.assertLogs('odoo.addons.pb_time_pay', level='WARNING') as cm:
            post_init_hook(self.env)
        self.assertTrue(any('LATEMI' in m for m in cm.output), cm.output)

    def test_t32_no_vendor_name_on_screen(self):
        """White-label: no user-visible string of this module names the
        vendor of the framework (the word is assembled here so this file
        does not trip the same scan elsewhere)."""
        word = 'Od' + 'oo'
        root = get_module_path('pb_time_pay')
        bad = []
        for folder, _dirs, files in os.walk(root):
            if '/tests' in folder or '__pycache__' in folder:
                continue
            for name in files:
                if not name.endswith(('.xml', '.po', '.js')):
                    continue
                with open(os.path.join(folder, name), encoding='utf-8') as fh:
                    for n, line in enumerate(fh, 1):
                        if word in line and 'odoo-module' not in line \
                                and '@odoo/' not in line:
                            bad.append('%s:%s' % (name, n))
        self.assertFalse(bad, bad)

    def test_t33_the_section_writes_only_from_clicks(self):
        """The Close lens's W21.1 rule, for the section this module adds."""
        js = _read('pb_time_pay', 'static', 'src', 'js', 'time_pay_close.js')
        setup = re.search(r'\n    setup\(\)\s*\{(.*?)\n    \}\n', js, re.S)
        self.assertTrue(setup)
        for writer in ('accept_suggestions', 'decide_late',
                       'dismiss_suggestion', 'orm.call'):
            self.assertNotIn(writer, setup.group(1))
        self.assertNotIn('onWillStart', js, 'the section has no read of its own')
        lens = _read('pb_mission', 'static', 'src', 'js', 'pb_close_lens.js')
        self.assertIn('export const CLOSE_SECTIONS = "pb_close_lens_section"',
                      lens)
        self.assertIn('registry.category("pb_close_lens_section")', js)
