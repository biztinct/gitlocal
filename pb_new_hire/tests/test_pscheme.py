# -*- coding: utf-8 -*-
"""PSCHEME P1 E — Add employee writes the pay scheme on the PERSON.

T22 (E-T1) a hand-picked scheme that differs from the team's line is honoured
T23 (E-T2) the mid-month advance switch writes / does not write the advance
T24 (E-T3) the Vietnamese-joiner shape lands in the run, no amber line
T25 an old payload: the resolver's answer is written when of the country
T26 no retired sentence is produced by any branch, none left in the catalogue
T27 a second approver: the row is written on approval, not on send
"""
import os
import re

from odoo.tests import tagged

from odoo.addons.pb_people_advanced.models.newhire_approval import NEWHIRE_WRITE

from .test_new_hire import NewHireCommon

RETIRED = (
    'and the pay run follows the team',
    'pick one of its teams',
    'The pay run will pay them by',
    'in Mapping to make',
    'in Mapping so the pay run includes them',
    "to make it the team's own",
    'Set who pays this team in Mapping before the first pay run',
)


@tagged('post_install', '-at_install', 'newhire', 'pscheme')
class TestPschemeHire(NewHireCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Config = env['hr.formula.config']
        cls.sg_end = Config.create({'name': 'DEMO PS Singapore end of month', 'code': 'DEMOPSSGE',
                                    'country_code': 'SG', 'state': 'active', 'cycle_type': 'end_cycle',
                                    'company_id': cls.company.id})
        cls.sg_adv = Config.create({'name': 'DEMO PS Singapore advance', 'code': 'DEMOPSSGA',
                                    'country_code': 'SG', 'state': 'active', 'cycle_type': 'mid_cycle',
                                    'company_id': cls.company.id})
        Rule = env['hr.formula.rule']
        end_rule = Rule.create({'config_id': cls.sg_end.id, 'name': 'DEMO PS Advance taken',
                                'code': 'DEMOPSADVT', 'column_type': 'input', 'sequence': 1})
        mid_rule = Rule.create({'config_id': cls.sg_adv.id, 'name': 'DEMO PS Advance',
                                'code': 'DEMOPSADV', 'column_type': 'input', 'sequence': 1})
        env['hr.payroll.cycle.component.mapping'].create({
            'mid_cycle_config_id': cls.sg_adv.id, 'end_cycle_config_id': cls.sg_end.id,
            'mid_component_id': mid_rule.id, 'end_component_id': end_rule.id})
        cls.Row = env['pb.person.scheme'].sudo()

    def plain(self, **kw):
        return self.draft(**dict({'login_mode': 'none', 'open_case': False, 'letter': False}, **kw))

    def rows(self, emp):
        return self.Row.search([('employee_id', '=', emp.id)], order='cycle_type')

    def population(self, config, emp, day='2026-12-01'):
        Wizard = self.env['pb.payrun.wizard'].sudo().with_company(self.company)
        covered, _missed = Wizard._scheme_population(config.id, emp.ids, on_date=day)
        return covered

    # ----------------------------------------------------------------- T22
    def test_t22_hand_pick_differs_from_the_team_and_is_honoured(self):
        self.fast_lane()
        dec = self.studio().decides(self.finance.id, 'SG', '2026-12-07', 'permanent', self.sg_end.id)
        self.assertTrue(dec['scheme']['honoured'])
        self.assertTrue(dec['scheme']['differs'])
        self.assertFalse(dec['problem'])
        answer = self.studio().send(self.plain(scheme_id=self.sg_end.id, advance_scheme_id=False))
        self.assertTrue(answer.get('applied'), answer)
        emp = self.hires()
        row = self.rows(emp)
        self.assertEqual((row.config_id, str(row.date_from), row.source),
                         (self.sg_end, '2026-12-07', 'hire'))
        if 'pb.payrun.wizard' in self.env:
            self.assertEqual(self.population(self.sg_end, emp), emp.ids,
                             "judged on the 1st, the joiner's first scheme counts")
            self.assertFalse(self.population(self.sg_scheme, emp), "not the team's")

    # ----------------------------------------------------------------- T23
    def test_t23_the_advance_switch(self):
        self.fast_lane()
        dec = self.studio().decides(self.finance.id, 'SG', '2026-12-07', 'permanent', self.sg_end.id)
        self.assertEqual([a['id'] for a in dec['scheme']['advances']], [self.sg_adv.id])
        self.assertEqual(dec['scheme']['advance']['id'], self.sg_adv.id, 'one paired advance: on')
        off = self.studio().decides(self.finance.id, 'SG', '2026-12-07', 'permanent', self.sg_end.id,
                                    False, False)
        self.assertFalse(off['scheme']['advance'])
        self.studio().send(self.plain(scheme_id=self.sg_end.id))
        emp = self.hires()
        self.assertEqual(self.rows(emp).mapped('config_id'), self.sg_end | self.sg_adv)
        self.studio().send(self.plain(name='DEMO PS No advance', work_email='demo.ps.na@example.com',
                                      personal='demo.ps.na@example.net',
                                      scheme_id=self.sg_end.id, advance_scheme_id=False))
        other = self.hires('DEMO PS No advance')
        self.assertEqual(self.rows(other).mapped('config_id'), self.sg_end)
        if 'pb.payrun.wizard' in self.env:
            self.assertEqual(self.population(self.sg_adv, emp | other), emp.ids)

    # ----------------------------------------------------------------- T24
    def test_t24_vietnamese_joiner_lands_in_the_run(self):
        self.fast_lane()
        self.env['hr.formula.scheme.assignment'].create({
            'config_id': self.vn_scheme.id, 'cycle_type': 'any', 'company_id': self.company.id,
            'domain': "[('barcode', 'in', ['DEMOPS-NOBODY'])]"})
        dec = self.studio().decides(self.lonely.id, 'VN', '2026-12-07', 'permanent', False, False, None,
                                    'DEMO PS Lan')
        self.assertEqual(dec['scheme']['id'], self.vn_scheme.id)
        self.assertTrue(dec['scheme']['honoured'])
        self.assertFalse(dec['problem'])
        self.assertFalse(dec['fix'])
        self.assertIn('DEMO PS Lan will be paid by DEMO NH Vietnam monthly from', dec['pay_line'])
        self.studio().send(self.plain(name='DEMO PS Lan', department_id=self.lonely.id, job_id=False,
                                      job_title='DEMO PS Grower', payroll_country='VN', parent_id=False,
                                      work_location_id=False, wage=9000000))
        emp = self.hires('DEMO PS Lan')
        self.assertEqual(self.rows(emp).config_id, self.vn_scheme)
        if 'pb.payrun.wizard' in self.env:
            self.assertEqual(self.population(self.vn_scheme, emp), emp.ids)

    # ----------------------------------------------------------------- T25
    def test_t25_old_payload(self):
        Wizard = self.env['pb.people.onboard.wizard'].with_user(self.maker).with_context(
            allowed_company_ids=[self.company.id], **{NEWHIRE_WRITE: True})
        vals, _d = self.studio()._values(self.plain())
        for key in ('pb_nh_own_scheme_id', 'pb_nh_advance_scheme_id'):
            vals.pop(key)
        res = Wizard.create_employee(vals)
        emp = self.env['hr.employee'].sudo().browse(res['employee_id'])
        self.assertEqual(self.rows(emp).config_id, self.sg_scheme, "the team's line, a Singapore scheme")
        vals, _d = self.studio()._values(self.plain(name='DEMO PS Malaysia', work_email='demo.ps.my@example.com',
                                                    personal='demo.ps.my@example.net',
                                                    department_id=self.lonely.id, job_id=False,
                                                    job_title='DEMO PS Clerk', payroll_country='MY',
                                                    parent_id=False, work_location_id=False))
        for key in ('pb_nh_own_scheme_id', 'pb_nh_advance_scheme_id'):
            vals.pop(key)
        res = Wizard.create_employee(vals)
        self.assertTrue(res.get('employee_id'), res)
        emp = self.env['hr.employee'].sudo().browse(res['employee_id'])
        self.assertFalse(self.rows(emp), 'nobody pays them: nothing written, the hire still succeeds')

    # ----------------------------------------------------------------- T26
    def test_t26_no_retired_sentence_anywhere(self):
        S = self.studio()
        self.env['hr.formula.scheme.assignment'].create({
            'config_id': self.vn_scheme.id, 'cycle_type': 'any', 'company_id': self.company.id,
            'domain': "[('payroll_country', '=', 'VN')]"})
        seen = []
        for team in (self.finance, self.ops, self.lonely, self.farm, self.env['hr.department']):
            for code in ('SG', 'VN', 'MY', 'IN', False):
                for pick in (False, self.sg_end.id, self.sg_scheme.id, self.vn_scheme.id):
                    out = S.decides(team.id or False, code, '2026-12-07', 'permanent', pick)
                    for key in ('problem', 'fix', 'pay_line'):
                        if out.get(key):
                            seen.append(out[key])
                    if out.get('scheme'):
                        seen.append(out['scheme'].get('why') or '')
        for sentence in seen:
            for word in RETIRED:
                self.assertNotIn(word, sentence)
        here = os.path.dirname(os.path.dirname(__file__))
        for name in ('pb_new_hire.pot', 'vi_VN.po', 'id_ID.po'):
            with open(os.path.join(here, 'i18n', name), encoding='utf-8') as fh:
                ids = re.findall(r'^msgid "(.*)"$', fh.read(), re.M)
            for msgid in ids:
                for word in RETIRED:
                    self.assertNotIn(word, msgid, '%s: %s' % (name, msgid))

    # ----------------------------------------------------------------- T27
    def test_t27_second_approver_writes_on_approval(self):
        answer = self.studio().send(self.plain(scheme_id=self.sg_end.id, advance_scheme_id=False))
        self.assertFalse(answer.get('applied'), answer)
        self.assertFalse(self.hires())
        self.approve(answer)
        emp = self.hires()
        self.assertEqual(len(emp), 1)
        self.assertEqual(self.rows(emp).config_id, self.sg_end)
        proposal = self.env['pb.newhire.proposal'].sudo().browse(answer['proposal_id'])
        rows = dict((r[0], r[2]) for r in proposal._proposal_rows())
        self.assertEqual(rows.get('Paid by'), 'DEMO PS Singapore end of month')
