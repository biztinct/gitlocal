# -*- coding: utf-8 -*-
"""LEARNING L3 — growth-plan objective → learning path (handover T12).

The bridge is the only place growth plans are touched. These prove an
objective can point at a path, the plan read carries how far the person has
got, "Enrol" enrols once, and the module installs only beside both sides.
Fixtures are "DEMO", in a company of their own, English pinned (LN14/LN32).
"""

import ast

from odoo.exceptions import AccessError, UserError
from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestT12GrowthBridge(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'DEMO L3G Co'})
        cls.env = cls.env(context=dict(cls.env.context, lang='en_US',
                                       allowed_company_ids=[cls.company.id]))
        Users = cls.env['res.users'].with_context(no_reset_password=True)

        def user(login, groups):
            return Users.create({
                'name': login, 'login': login, 'email': login,
                'company_id': cls.company.id,
                'company_ids': [(6, 0, cls.company.ids)],
                'group_ids': [(6, 0, [cls.env.ref(g).id for g in groups])]})
        cls.hr = user('demo.l3g.hr@example.com',
                      ['base.group_user', 'pb_pip.group_pip_head'])
        cls.stranger = user('demo.l3g.x@example.com', ['base.group_user'])
        cls.person_user = user('demo.l3g.person@example.com',
                               ['base.group_user'])
        cls.person = cls.env['hr.employee'].create({
            'name': 'DEMO L3G Line operator', 'company_id': cls.company.id,
            'user_id': cls.person_user.id})
        channel = cls.env['slide.channel'].create({
            'name': 'DEMO L3G Leading a line', 'channel_type': 'training',
            'visibility': 'members', 'enroll': 'invite',
            'completed_template_id': False, 'is_published': True})
        cls.env['slide.slide'].create({
            'name': 'DEMO L3G lesson', 'channel_id': channel.id,
            'slide_category': 'article', 'html_content': '<p>Lead.</p>',
            'is_published': True})
        cls.path = cls.env['pb.training.path'].sudo().create({
            'name': 'DEMO L3G Operator to line leader', 'purpose': 'career',
            'company_id': cls.company.id,
            'step_ids': [(0, 0, {'channel_id': channel.id})]})
        cls.case = cls.env['pb.pip.case'].sudo().create({
            'employee_id': cls.person.id, 'company_id': cls.company.id,
            'requested_by_user_id': cls.hr.id})
        cls.objective = cls.env['pb.pip.objective'].sudo().create({
            'case_id': cls.case.id, 'name': 'DEMO L3G Run the line alone',
            'metric': 'Runs a shift with no escalation'})

    def _pip(self, user):
        return self.env['pb.pip'].with_user(user).with_context(
            allowed_company_ids=[self.company.id], lang='en_US')

    def test_t12_objective_points_at_a_path(self):
        pip = self._pip(self.hr)
        out = pip.set_objective_path(self.objective.id, self.path.id)
        self.assertEqual(self.objective.path_id, self.path)
        self.assertEqual(out['path']['id'], self.path.id)
        self.assertIn('not on it yet', self.objective.path_words)
        case = pip.get_case(self.case.id)
        line = case['objectives'][0]
        self.assertEqual(line['path']['name'], self.path.name)
        self.assertEqual(line['path']['enrolment_id'], 0)
        self.assertIn({'id': self.path.id, 'name': self.path.name},
                      case['path_options'])
        pip.set_objective_path(self.objective.id, 0)
        self.assertFalse(self.objective.path_id)
        self.assertEqual(pip.get_case(self.case.id)['objectives'][0]['path'],
                         {})

    def test_t12_enrol_once(self):
        pip = self._pip(self.hr)
        pip.set_objective_path(self.objective.id, self.path.id)
        out = pip.enrol_objective_path(self.objective.id)
        self.assertIn(self.person.name, out['message'])
        Enrol = self.env['pb.training.path.enrolment'].sudo()
        enr = Enrol.search([('employee_id', '=', self.person.id)])
        self.assertEqual(len(enr), 1)
        self.assertEqual(enr.reason, 'leadership')
        self.assertEqual(enr.objective_id, self.objective)
        again = pip.enrol_objective_path(self.objective.id)
        self.assertIn('already', again['message'])
        self.assertEqual(Enrol.search_count(
            [('employee_id', '=', self.person.id)]), 1)
        line = pip.get_case(self.case.id)['objectives'][0]
        self.assertEqual(line['path']['enrolment_id'], enr.id)
        self.assertEqual(line['path']['words'],
                         '%s · 0%%' % self.path.name)

    def test_t12_the_growth_gate_holds(self):
        with self.assertRaises(AccessError):
            self._pip(self.stranger).set_objective_path(
                self.objective.id, self.path.id)
        with self.assertRaises(UserError):
            self._pip(self.hr).enrol_objective_path(self.objective.id)

    def test_t12_installs_only_beside_both_sides(self):
        path = get_module_path('pb_training_growth')
        with open(path + '/__manifest__.py', encoding='utf-8') as fh:
            manifest = ast.literal_eval(fh.read())
        self.assertTrue(manifest['auto_install'])
        self.assertEqual(sorted(manifest['depends']),
                         ['pb_pip', 'pb_training'])
        for side in ('pb_pip', 'pb_training'):
            with open(get_module_path(side) + '/__manifest__.py',
                      encoding='utf-8') as fh:
                self.assertNotIn('pb_training_growth', fh.read(), side)

    def test_t12_no_vendor_name_in_the_bridge(self):
        root = get_module_path('pb_training_growth')
        for rel in ('models/growth.py', 'static/src/js/growth_path.js',
                    'static/src/xml/growth_path.xml', '__manifest__.py'):
            with open(root + '/' + rel, encoding='utf-8') as fh:
                self.assertNotRegex(fh.read(), r'\bOdoo\b', rel)
