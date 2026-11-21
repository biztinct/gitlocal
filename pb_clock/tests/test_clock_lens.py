# -*- coding: utf-8 -*-
"""CLOCK-1 handover §7 cases 17–18 and the Time clocks lens facade."""
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import tagged

from .common import ClockCase


@tagged('post_install', '-at_install', 'pb_clock')
class TestClockLens(ClockCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Lens = cls.env['pb.clock.lens'].with_company(cls.company)

    def _user(self, login, groups):
        gids = [self.env.ref('base.group_user').id] + \
            [self.env.ref(g).id for g in groups]
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name': login, 'login': login,
            'company_id': self.company.id, 'company_ids': [(6, 0, [self.company.id])],
            'group_ids': [(6, 0, gids)]})

    # ------------------------------------------------------------ the read
    def test_lens_empty_then_live(self):
        empty = self.Lens.get_lens('2026-10-26')
        self.assertEqual(empty['hero']['state'], 'empty')
        self.assertEqual(empty['unknown']['total'], 0)
        self.assertFalse(self.env['pb.clock.device'].search([
            ('company_id', '=', self.company.id), ('kind', '=', 'upload')]),
            "a read never creates the upload device")
        self.punch('885', '2026-10-28 07:00')
        self.punch('885', '2026-10-28 16:00')
        self.punch('TST-A', '2026-10-28 07:05')
        self.run_pairing()
        d = self.Lens.get_lens('2026-10-26')
        self.assertIn(d['hero']['state'], ('live', 'quiet'))
        self.assertEqual(d['hero']['device'], 'Factory 1')
        self.assertEqual([r['code'] for r in d['unknown']['rows']], ['TST-A'])
        self.assertEqual(d['unknown']['week'], 1)
        self.assertEqual(d['recent']['total'], 3)
        kinds = sorted(r['kind'] for r in d['recent']['rows'])
        self.assertEqual(kinds, ['in', 'out', 'unknown'])
        self.assertEqual(d['devices'][0]['name'], 'Factory 1')
        only_unknown = self.Lens.get_lens('2026-10-26', filters={'state': 'unknown'})
        self.assertEqual(only_unknown['recent']['total'], 1)

    def test_hub_badge_counts_unknown_numbers(self):
        self.punch('TST-A', '2026-10-28 07:05')
        self.punch('TST-B', '2026-10-28 07:06')
        self.run_pairing()
        summary = self.env['pb.time.hub'].with_company(self.company).get_hub_summary(
            False, '2026-10-26')
        self.assertEqual(summary['lens_counts'].get('clocks'), 2)

    # ------------------------------------------------------------ writes
    def test_auto_match_and_suggestion(self):
        self.punch('0885', '2026-10-28 07:00')       # badge is 885
        self.punch('TST-B', '2026-10-28 07:02')
        self.run_pairing()
        d = self.Lens.get_lens('2026-10-26')
        sugg = {r['code']: r['suggestion'] for r in d['unknown']['rows']}
        self.assertEqual(sugg['0885']['id'], self.e885.id,
                         "leading zeros suggest the person, never assign them")
        self.assertFalse(sugg['TST-B'])
        out = self.Lens.auto_match()
        self.assertEqual(out['assigned'], 0)
        self.assertIn('Assign them one by one', out['message'])
        # someone now carries TST-B as their ID number → auto-match finds them
        self.e227.identification_id = 'TST-B'
        out = self.Lens.auto_match()
        self.assertEqual(out['assigned'], 1)
        self.assertEqual(self.Punch.search([('user_code', '=', 'TST-B')]).employee_id,
                         self.e227)

    def test_assign_refuses_a_second_number(self):
        out = self.Lens.assign_code('555', self.e227.id)     # 227 already has 227
        self.assertIn('error', out)
        self.assertIn('227', out['error'])

    def test_repair_week_and_settings_rights(self):
        self.punch('885', '2026-10-28 07:00')
        self.punch('885', '2026-10-28 16:00')
        self.run_pairing()
        res = self.Lens.repair_week('2026-10-26')
        self.assertEqual(res['paired_days'], 0)
        self.assertIn('Nothing changed', res['message'])
        officer = self._user('clk_lens_off', ['hr_attendance.group_hr_attendance_officer'])
        out = self.Lens.with_user(officer).save_settings(20, 3, False)
        self.assertIn('error', out)
        out = self.Lens.with_user(officer).set_device(self.device.id, {'allowed': False})
        self.assertIn('error', out)
        out = self.Lens.save_settings(99, 3, False)
        self.assertIn('error', out)
        out = self.Lens.save_settings(20, 3, True)
        self.assertTrue(out.get('ok'))
        self.assertEqual(self.company.pb_clock_max_span_h, 20)
        self.assertTrue(self.company.pb_clock_trust_direction)
        self.assertTrue(self.Lens.set_device(self.device.id, {'location': 'Gate A'})['ok'])
        self.assertEqual(self.device.location, 'Gate A')

    def test_people_search_includes_leavers(self):
        leaver = self.env['hr.employee'].create({
            'name': 'CLK Leaver Lan', 'company_id': self.company.id, 'barcode': '7001'})
        leaver.action_archive() if hasattr(leaver, 'action_archive') else leaver.write({'active': False})
        names = [p['name'] for p in self.Lens.search_people('CLK')]
        self.assertIn('CLK Leaver Lan', names)
        self.assertEqual(names[-1], 'CLK Leaver Lan', "active people first")

    # ================================================================== 17
    def test_17_no_brand_name_in_any_string(self):
        root = get_module_path('pb_clock')
        bad = []
        for dirpath, dirs, files in os.walk(root):
            dirs[:] = [x for x in dirs if x not in ('__pycache__', 'tests')]
            for f in files:
                if not f.endswith(('.py', '.js', '.xml', '.po', '.pot', '.scss', '.csv')):
                    continue
                with open(os.path.join(dirpath, f), encoding='utf-8') as fh:
                    for n, line in enumerate(fh, 1):
                        if re.search(r'\bOdoo\b', line):
                            bad.append('%s:%s' % (f, n))
        self.assertFalse(bad, 'the brand name appears in: %s' % bad)

    # ================================================================== 18
    def test_18_time_hub_lenses_unchanged_and_clocks_after_import(self):
        hub_js = os.path.join(get_module_path('pb_time_hub'), 'static', 'src', 'js',
                              'time_hub.js')
        with open(hub_js, encoding='utf-8') as fh:
            body = fh.read()
        self.assertIn('const BUILTIN_LENSES = ["timeline", "grid", "exceptions", "import"];',
                      body)
        self.assertIn('registry.category("pb_time_hub.lenses")', body)
        lens_js = os.path.join(get_module_path('pb_clock'), 'static', 'src', 'js',
                               'clock_lens.js')
        with open(lens_js, encoding='utf-8') as fh:
            lens = fh.read()
        self.assertRegex(lens, r'registry\.category\("pb_time_hub\.lenses"\)\.add\("clocks"')
        self.assertIn('key: "clocks"', lens)
