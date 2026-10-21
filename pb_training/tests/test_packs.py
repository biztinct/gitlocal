# -*- coding: utf-8 -*-
"""LEARNING L2 — country packs and their reports. Handover tests T10–T12.

A pack is a set of TEMPLATE rows (company empty, archived) copied into a
company when it is switched on. The rails: switching on twice must not copy
twice, switching off must archive and never delete, switching on again must
bring back exactly what was on, unverified rules must stay off, and a copy
must never assign anything until HR says so.
"""

from odoo import fields
from odoo.tests import tagged

from .test_requirements import RequirementCase


class PackCase(RequirementCase):

    def _copies(self, key):
        return self.Req.with_context(active_test=False).search(
            [('company_id', '=', self.company.id), ('pack_key', '=', key)])

    def _on(self, cc):
        return self.Board.switch_pack(cc, True)


# =========================================================================
#  T10 — switching a pack on and off
# =========================================================================
@tagged('post_install', '-at_install')
class TestT10Switch(PackCase):

    def test_t10_on_copies_once_off_archives_on_restores(self):
        templates = self.Req._templates('vn_osh')
        self.assertGreaterEqual(len(templates), 11)
        self.assertFalse(any(templates.mapped('active')))
        self.assertFalse(any(templates.mapped('company_id')))
        res = self._on('vn')
        copies = self._copies('vn_osh')
        self.assertEqual(res['made'], len(templates))
        self.assertEqual(len(copies), len(templates))
        self.assertEqual(set(copies.mapped('pack_key')), {'vn_osh'})
        self.assertFalse(any(copies.mapped('auto_assign')),
                         'a pack never assigns until HR says so')
        for copy in copies:
            self.assertEqual(copy.active, not copy.unverified, copy.code)
        self.assertTrue(self.Req._pack_is_on('vn', self.company))
        # Again: nothing new.
        self.assertEqual(self._on('vn')['made'], 0)
        self.assertEqual(len(self._copies('vn_osh')), len(templates))
        # Off: archived, not deleted.
        was_on = copies.filtered('active')
        self.Board.switch_pack('vn', False)
        self.assertFalse(any(self._copies('vn_osh').mapped('active')))
        self.assertEqual(len(self._copies('vn_osh')), len(templates))
        self.assertFalse(self.Req._pack_is_on('vn', self.company))
        # On again: exactly what was on.
        again = self._on('vn')
        self.assertEqual((again['made'], again['restored']),
                         (0, len(was_on)))
        self.assertEqual(self._copies('vn_osh').filtered('active'), was_on)

    def test_t10_every_pack_has_templates_and_a_copy_keeps_its_name(self):
        for cc, key in (('vn', 'vn_osh'), ('in', 'in_posh'), ('id', 'id_k3'),
                        ('sg', 'sg_hours')):
            self.assertTrue(self.Req._templates(key), key)
            self._on(cc)
            copy = self._copies(key)[:1]
            self.assertEqual(copy.name, copy.template_id.name)
            self.assertEqual(copy.code, copy.template_id.code)

    def test_t10_settings_read_says_what_each_pack_holds(self):
        data = self.Board.required_settings()
        packs = {p['cc']: p for p in data['packs']}
        self.assertEqual(set(packs), {'vn', 'in', 'id', 'sg'})
        self.assertFalse(packs['vn']['on'])
        self.assertGreater(packs['vn']['unverified'], 0)
        self.assertTrue(packs['sg']['note'])
        self._on('vn')
        packs = {p['cc']: p for p in self.Board.required_settings()['packs']}
        self.assertTrue(packs['vn']['on'])
        self.assertGreater(packs['vn']['active'], 0)


# =========================================================================
#  T11 — Vietnam
# =========================================================================
@tagged('post_install', '-at_install')
class TestT11Vietnam(PackCase):

    def test_t11_groups_carry_their_hours_and_cadence(self):
        self._on('vn')
        by = {c.code: c for c in self._copies('vn_osh')}
        expect = {'vn_osh_g1': ('1', 16, 24, 8), 'vn_osh_g2': ('2', 48, 24, 24),
                  'vn_osh_g3': ('3', 24, 24, 12), 'vn_osh_g4': ('4', 16, 12, 8),
                  'vn_osh_g5': ('5', 16, 24, 8), 'vn_osh_g6': ('6', 4, 24, 2)}
        for code, (group, hours, months, refresher) in expect.items():
            row = by[code]
            self.assertEqual((row.safety_groups, row.hours_required,
                              row.validity_months, row.refresher_hours),
                             (group, hours, months, refresher), code)
            self.assertTrue(row.active, code)
        self.assertEqual(by['vn_osh_g3'].target, 'licence')
        self.assertEqual(by['vn_osh_g4'].target, 'course')
        for code in ('vn_osh_retrain', 'vn_fire_g1', 'vn_first_aid'):
            self.assertTrue(by[code].unverified, code)
            self.assertFalse(by[code].active, code)

    def test_t11_renewals_due_in_thirty_days_lists_the_right_people(self):
        self._on('vn')
        self.e_one.pb_safety_group = '1'
        self.e_two.pb_safety_group = '1'
        self._doc(self.e_one, 'DEMO OSH group 1 certificate', days=20,
                  reference='DEMO-VN-1', issuer='DEMO Safety Centre',
                  hours=16)
        self._doc(self.e_two, 'DEMO OSH group 1 certificate', days=100)
        cols, rows = self.env['pb.training.analytics'].country_report_rows(
            'vn')
        self.assertEqual(cols, ['Person', 'Safety group', 'Course or card',
                                'Hours done', 'Valid until', 'Card number',
                                'Trainer'])
        names = [r[0] for r in rows]
        self.assertIn(self.e_one.name, names)
        self.assertNotIn(self.e_two.name, names)
        line = rows[names.index(self.e_one.name)]
        self.assertEqual((line[3], line[5], line[6]),
                         ('16', 'DEMO-VN-1', 'DEMO Safety Centre'))
        reports = self.env['pb.training.analytics'].get_numbers()[
            'country_reports']
        self.assertEqual([r['cc'] for r in reports], ['vn'])


# =========================================================================
#  T12 — India, Indonesia, Singapore
# =========================================================================
@tagged('post_install', '-at_install')
class TestT12Reports(PackCase):

    def _done(self, user, emp):
        row = self.Assignment.create({'channel_id': self.simple.id,
                                      'employee_id': emp.id})
        self._finish(user, self.simple, [self.simple_lesson])
        row._refresh()
        return row

    def test_t12_india_register(self):
        self._on('in')
        self._copies('in_posh').filtered(
            lambda r: r.code == 'in_posh_all').channel_id = self.simple.id
        self.e_one.employee_type = 'contractor'
        self._done(self.u_one, self.e_one)
        Analytics = self.env['pb.training.analytics']
        cols, rows = Analytics.country_report_rows('in')
        self.assertEqual(cols, ['Person', 'Type', 'Session date', 'Evidence'])
        self.assertEqual([(r[0], r[1]) for r in rows],
                         [(self.e_one.name, 'Contractor')])
        res = Analytics.country_report_xlsx('in')
        self.assertEqual(res['rows'], 1)

    def test_t12_indonesia_licence_register(self):
        self._on('id')
        self._doc(self.e_two, 'DEMO Forklift SIO licence', days=900,
                  category=self.lic, reference='DEMO-ID-7',
                  issuer='DEMO Kemnaker')
        self._doc(self.e_two, 'DEMO Pension letter', days=900)
        cols, rows = self.env['pb.training.analytics'].country_report_rows(
            'id')
        self.assertEqual(cols, ['Person', 'Licence', 'Number', 'Issuer',
                                'Valid until'])
        self.assertEqual([(r[0], r[1], r[2], r[3]) for r in rows],
                         [(self.e_two.name, 'DEMO Forklift SIO licence',
                           'DEMO-ID-7', 'DEMO Kemnaker')])

    def test_t12_singapore_training_hours(self):
        self._on('sg')
        self.simple.sudo().pb_hours = 3
        self.e_one.country_id = self.env.ref('base.sg').id
        self._done(self.u_one, self.e_one)
        cols, rows = self.env['pb.training.analytics'].country_report_rows(
            'sg')
        self.assertEqual(cols, ['Person', 'Course', 'Hours', 'Finished on',
                                'Residency'])
        mine = [r for r in rows if r[0] == self.e_one.name]
        self.assertEqual((mine[0][1], mine[0][2], mine[0][4]),
                         (self.simple.name, '3', 'Singapore national'))

    def test_t12_headcount_rule_says_which_site_is_short(self):
        self._on('id')
        warden = self._copies('id_k3').filtered(
            lambda r: r.code == 'id_fire_warden')
        self.assertTrue(warden.active)
        self.assertTrue(warden._is_headcount())
        short = warden._shortfalls(fields.Date.today())
        self.assertTrue(short)
        self.assertIn('needs', short[0]['words'])
        self.assertFalse(warden._people(), 'a headcount rule is not a column')
