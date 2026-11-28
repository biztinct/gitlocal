# -*- coding: utf-8 -*-
"""PSCHEME P2b B — the pay scheme belongs to the person, in the sheets.

On the P3b fixture (Kitchen paid under "P3B Monthly", Dining under "P3B Daily",
Garden by nothing; both schemes are Vietnamese), plus an Indonesian scheme
with its paired mid-month advance.

T8  new-employee rows: an empty cell takes the only scheme of the Country of
    work, or the usual one of several; several without a usual one asks (with
    the list); a scheme of another country is refused with the reason and the
    allowed names; the advance column on / off; apply writes the person's own
    rows from their first day (`source='sheet'`), at once or when the hire is
    approved; the joiner lands in that scheme's pay run
T10 people already here: a changed cell asks for the change from the row's
    start date (fast lane, second-approver lane, refused without carry-out);
    an unchanged cell changes nothing; a Country of work change suggests the
    new country's scheme and writes nothing by itself
T11 the readers name each person's own scheme (two people of one team)
T14 the door refuses a portal user; no write access on the rows
"""
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import tagged

from odoo.addons.pb_updates.models import updates_joiners as UJ
from odoo.addons.pb_updates.tests.test_updates_p3a import csv_b64
from odoo.addons.pb_updates.tests.test_updates_p3b import P3bCommon, START, TEAM, WAGE

COUNTRY = 'f:hr.employee:payroll_country'
WHEN = 'when:start'


@tagged('post_install', '-at_install', 'pb_updates', 'pscheme', 'pscheme_p2b')
class TestUpdatesPersonScheme(P3bCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Config = cls.env['hr.formula.config']
        cls.idn = Config.create({'name': 'DEMO P2B Indonesia monthly', 'code': 'DEMOP2BUID',
                                 'cycle_type': 'end_cycle', 'country_code': 'ID',
                                 'company_id': cls.company.id, 'state': 'active'})
        cls.id_adv = Config.create({'name': 'DEMO P2B Indonesia advance', 'code': 'DEMOP2BUIA',
                                    'cycle_type': 'mid_cycle', 'country_code': 'ID',
                                    'company_id': cls.company.id, 'state': 'active'})
        Rule = cls.env['hr.formula.rule']
        e = Rule.create({'config_id': cls.idn.id, 'code': 'P2BUADVT', 'name': 'DEMO Advance taken',
                         'column_type': 'input', 'sequence': 1})
        m = Rule.create({'config_id': cls.id_adv.id, 'code': 'P2BUADV', 'name': 'DEMO Advance',
                         'column_type': 'input', 'sequence': 1})
        cls.env['hr.payroll.cycle.component.mapping'].sudo().create({
            'mid_cycle_config_id': cls.id_adv.id, 'end_cycle_config_id': cls.idn.id,
            'mid_component_id': m.id, 'end_component_id': e.id})
        cls.Row = cls.env['pb.person.scheme'].sudo()
        cls.ann.payroll_country = 'VN'
        cls.bob.payroll_country = 'VN'
        cls.bob.department_id = cls.kitchen

    # ------------------------------------------------------------ helpers
    def jrows(self, *rows, advance=False):
        head = ['Code', 'Name', 'Team', 'Start', 'Wage', 'Country of work', 'Pay scheme']
        if advance:
            head.append('Mid-month advance')
        return [head] + [list(r) for r in rows]

    def jused(self, advance=False):
        used = {3: TEAM, 4: START, 5: WAGE, 6: COUNTRY}
        if advance:
            used[8] = UJ.ADVANCE_TARGET
        return used

    def jpayload(self, rev):
        return [{'row': u['row'], 'code': u['code'], 'name': u['name'], 'email': u['email'],
                 'values': u['values'], 'scheme': u.get('scheme') or '',
                 'advance': u.get('advance') or '', 'start': u.get('start') or {}}
                for u in rev['unmatched']]

    def jjudge(self, rows, advance=False):
        rev = self.review(rows, self.jused(advance), scheme=7)
        res = self.Upd.judge_joiners(self.jpayload(rev))
        self.assertTrue(res['ok'], res.get('msg'))
        return {j['row']: j for j in res['rows']}, rev

    def jadd(self, rows, advance=False, upd=None):
        upd = upd if upd is not None else self.Upd
        used = self.jused(advance)
        rev = self.review(rows, used, scheme=7, upd=upd)
        return upd.apply('P2B joiners', csv_b64(rows), 'p2b.csv', self.jcols(used, 7),
                         rev['changes'], {'rows': len(rows) - 1}, joiners=self.jpayload(rev))

    def own(self, person):
        return self.Row.search([('employee_id', '=', person.id)], order='date_from, id')

    # ================================================================== T8
    def test_t8_new_rows_take_their_own_pay_scheme(self):
        judged, _rev = self.jjudge(self.jrows(
            ['P2BJ01', 'DEMO P2B Ayu', 'P3B Kitchen', '2026-12-15', '100', 'Indonesia', ''],
            ['P2BJ02', 'DEMO P2B Binh', 'P3B Kitchen', '2026-12-01', '100', 'VN', ''],
            ['P2BJ03', 'DEMO P2B Chau', 'P3B Garden', '2026-12-01', '100', 'VN', ''],
            ['P2BJ04', 'DEMO P2B Dewi', 'P3B Kitchen', '2026-12-01', '100', 'ID', 'P3B Monthly'],
            ['P2BJ05', 'DEMO P2B Eka', 'P3B Garden', '2026-12-01', '100', 'ID', 'P3B Advance']))
        # empty, one scheme for the country: that one, with its one advance
        self.assertEqual(judged[2]['scheme_id'], self.idn.id)
        self.assertEqual(judged[2]['advance_id'], self.id_adv.id)
        self.assertIn('The only pay scheme for Indonesia', judged[2]['scheme_from'])
        self.assertTrue(judged[2]['addable'], judged[2])
        # empty, several with a usual one (Kitchen's line): the usual one
        self.assertEqual(judged[3]['scheme_id'], self.monthly.id)
        self.assertTrue(judged[3]['addable'])
        # empty, several and no usual one: the row asks, with the list
        self.assertFalse(judged[4]['addable'])
        self.assertTrue(judged[4]['scheme_ask'])
        self.assertIn('Vietnam has 2 pay schemes', judged[4]['scheme_why'])
        self.assertEqual(sorted(o['id'] for o in judged[4]['scheme_options']),
                         sorted([self.monthly.id, self.daily.id]))
        # another country's scheme: red, with the reason and the allowed names
        self.assertFalse(judged[5]['addable'])
        self.assertIn('P3B Monthly is a pay scheme for Vietnam, but DEMO P2B Dewi works '
                      'in Indonesia.', judged[5]['scheme_why'])
        self.assertIn('Pick one of: DEMO P2B Indonesia monthly.', judged[5]['scheme_why'])
        self.assertIn("No pay scheme is called 'P3B Advance'", judged[6]['scheme_why'])
        # the dropdown fixes the row
        res = self.Upd.judge_joiners([dict(self.jpayload(_rev)[2], scheme='P3B Daily')])
        fixed = res['rows'][0]
        self.assertEqual(fixed['scheme_id'], self.daily.id)
        self.assertTrue(fixed['addable'])

    def test_t8b_apply_writes_from_the_first_day_and_lands_in_the_run(self):
        self.no_approval('newhire')
        answer = self.jadd(self.jrows(
            ['P2BJ11', 'DEMO P2B Gita', 'P3B Kitchen', '2026-12-15', '100', 'ID', '']))
        self.assertTrue(answer['ok'], answer.get('msg'))
        person = self.people('DEMO P2B Gita')
        rows = self.own(person)
        self.assertEqual([(r.config_id, r.date_from, r.source) for r in rows],
                         [(self.idn, date(2026, 12, 15), 'sheet'),
                          (self.id_adv, date(2026, 12, 15), 'sheet')])
        joiner = self.env['pb.updates.joiner'].search([('batch_id', '=', answer['batch_id'])])
        self.assertEqual(joiner.scheme_id, self.idn)
        if 'pb.payrun.wizard' in self.env:
            wizard = self.env['pb.payrun.wizard'].with_company(self.company)
            found = [c for c in (self.idn, self.monthly) if person.id in wizard._eligible_employees(
                employee_ids=person.ids, formula_config_id=c.id,
                date_start='2026-12-01', date_end='2026-12-31')]
            self.assertEqual(found, [self.idn], "the joiner of the 15th is in December's run")
        # the team map was not touched
        self.assertFalse(self.env['hr.formula.scheme.assignment'].search_count(
            [('config_id', '=', self.idn.id)]))

    def test_t8c_advance_column_on_and_off(self):
        self.no_approval('newhire')
        rows = self.jrows(
            ['P2BJ21', 'DEMO P2B Hana', 'P3B Kitchen', '2026-12-01', '100', 'ID', '', 'No'],
            ['P2BJ22', 'DEMO P2B Ida', 'P3B Kitchen', '2026-12-01', '100', 'ID', '',
             'DEMO P2B Indonesia advance'],
            ['P2BJ23', 'DEMO P2B Jaya', 'P3B Kitchen', '2026-12-01', '100', 'ID', '', 'Lunch money'],
            advance=True)
        judged, _rev = self.jjudge(rows, advance=True)
        self.assertEqual(judged[2]['advance_id'], 0)
        self.assertEqual(judged[3]['advance_id'], self.id_adv.id)
        self.assertFalse(judged[4]['addable'])
        self.assertIn('is not a mid-month advance of DEMO P2B Indonesia monthly',
                      judged[4]['scheme_why'])
        answer = self.jadd(rows[:3], advance=True)
        self.assertTrue(answer['ok'], answer.get('msg'))
        self.assertEqual(self.own(self.people('DEMO P2B Hana')).config_id, self.idn)
        self.assertEqual(self.own(self.people('DEMO P2B Ida')).config_id, self.idn | self.id_adv)
        # the blank sheet carries the column only where the company has advances
        sheet = self.Upd.download_joiner_sheet()
        self.assertTrue(sheet['ok'])
        self.assertTrue(self.Upd._company_has_advances())
        self.id_adv.state = 'draft'
        self.assertFalse(self.Upd._company_has_advances())

    def test_t8d_waiting_hire_writes_on_approval(self):
        self.second.group_ids = [(4, self.env.ref('hr_contract.group_hr_contract_manager').id)]
        self._hold(self.company, 'hr_lead', self.second)
        answer = self.jadd(self.jrows(
            ['P2BJ31', 'DEMO P2B Kadek', 'P3B Kitchen', '2026-12-01', '100', 'ID', '']))
        self.assertTrue(answer['ok'], answer.get('msg'))
        joiner = self.env['pb.updates.joiner'].search([('batch_id', '=', answer['batch_id'])])
        self.assertEqual(joiner.state, 'waiting')
        self.assertEqual((joiner.scheme_id, joiner.advance_scheme_id), (self.idn, self.id_adv))
        request = joiner.proposal_id.approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
        self.Engine.with_user(self.second).decide(request.id, step.key, 'approve', 'ok')
        person = self.people('DEMO P2B Kadek')
        self.assertEqual(self.own(person).config_id, self.idn | self.id_adv)

    # ================================================================= T10
    def lasting(self, rows, used, upd=None):
        upd = upd if upd is not None else self.Upd
        cols = self.cols(used)
        return upd.review(csv_b64(rows), 'p2b.csv', cols), cols

    def test_t10_existing_people_change_from_the_row_date(self):
        self.env['biz.approval.seed'].sudo().set_no_approval_needed(self.company, 'schememap')
        rows = [['Code', 'Pay scheme', 'Start date for this row'],
                ['P3AU01', 'P3B Daily', '2026-12-15'],
                ['P3AU02', 'P3B Monthly', '2026-12-01']]
        used = {2: UJ.SCHEME_TARGET, 3: WHEN}
        rev, cols = self.lasting(rows, used)
        self.assertTrue(rev['ok'], rev.get('msg'))
        by = {r['emp_id']: r for r in rev['rows']}
        change = by[self.ann.id]['scheme_change']
        self.assertEqual((change['status'], change['old'], change['new']),
                         ('ok', 'P3B Monthly', 'P3B Daily'))
        self.assertEqual(by[self.bob.id]['scheme_change']['status'], 'same',
                         "unchanged cell = no change")
        self.assertEqual(rev['scheme_changes'], 1)
        schemes = [{'emp_id': self.ann.id, 'config_id': change['config_id'],
                    'advance_id': change['advance_id'], 'date': '2026-12-15'}]
        # a proposer who cannot carry it out, with nobody set up to approve:
        # refused with the plain sentence, nothing written
        refused = self.Upd.apply('P2B schemes', csv_b64(rows), 'p2b.csv', cols, [], {'rows': 2},
                                 schemes=schemes)
        self.assertFalse(refused['ok'])
        self.assertIn('A payroll manager carries out pay scheme changes here', refused['msg'])
        self.assertFalse(self.own(self.ann))
        # a payroll manager in the fast lane: saved at once, from the row date
        self.proposer.group_ids = [(4, self.env.ref('pb_hr_payroll_formula.group_formula_manager').id)]
        answer = self.Upd.apply('P2B schemes', csv_b64(rows), 'p2b.csv', cols, [], {'rows': 2},
                                schemes=schemes)
        self.assertTrue(answer['ok'], answer.get('msg'))
        self.assertTrue(answer['schemes'][0]['saved'])
        rows_ann = self.own(self.ann)
        self.assertEqual([(r.config_id, r.date_from, r.source) for r in rows_ann],
                         [(self.daily, date(2026, 12, 15), 'sheet')])
        self.assertFalse(self.own(self.bob), "an unchanged cell wrote nothing")

    def test_t10b_second_approver_lane(self):
        Prop = self.env['pb.schememap.proposal']
        Prop._approval_seed_default(self.company)
        boss = self._user('p2b.boss', ('base.group_user', 'hr.group_hr_user',
                                       'pb_hr_payroll_formula.group_formula_manager'), self.company)
        self._hold(self.company, 'payroll_mgr', boss)
        self.assertEqual(self.Upd.scheme_outlook()['outcome'], 'approval')
        rows = [['Code', 'Pay scheme'], ['P3AU01', 'P3B Daily']]
        rev, cols = self.lasting(rows, {2: UJ.SCHEME_TARGET})
        change = rev['rows'][0]['scheme_change']
        answer = self.Upd.apply('P2B route', csv_b64(rows), 'p2b.csv', cols, [], {'rows': 1},
                                schemes=[{'emp_id': self.ann.id, 'config_id': change['config_id'],
                                          'advance_id': 0, 'date': '2027-01-01'}])
        self.assertTrue(answer['ok'], answer.get('msg'))
        self.assertTrue(answer['schemes'][0]['pending'])
        self.assertFalse(self.own(self.ann), "nothing until approved")
        prop = Prop.sudo().search([('kind', '=', 'person_set')], order='id desc', limit=1)
        request = prop.approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
        self.Engine.with_user(boss).decide(request.id, step.key, 'approve', 'ok')
        self.assertEqual(self.own(self.ann).config_id, self.daily)

    def test_t10c_country_change_suggests_never_applies(self):
        self.no_approval('records')
        rows = [['Code', 'Country of work'], ['P3AU01', 'Indonesia']]
        rev, cols = self.lasting(rows, {2: COUNTRY})
        self.assertTrue(rev['ok'], rev.get('msg'))
        row = rev['rows'][0]
        self.assertEqual(row['cells'][COUNTRY]['status'], 'ok', row['cells'])
        suggest = row['scheme_suggest']
        self.assertEqual(suggest['config_id'], self.idn.id)
        self.assertIn('Their pay scheme stays P3B Monthly unless you change it', suggest['line'])
        answer = self.Upd.apply('P2B country', csv_b64(rows), 'p2b.csv', cols, rev['changes'],
                                {'rows': 1})
        self.assertTrue(answer['ok'], answer.get('msg'))
        self.ann.invalidate_recordset()
        self.assertEqual(self.ann.payroll_country, 'ID')
        self.assertFalse(self.own(self.ann), "the server never changes a scheme by itself")

    def test_t10d_wrong_country_in_a_lasting_row(self):
        rows = [['Code', 'Pay scheme'], ['P3AU01', 'DEMO P2B Indonesia monthly']]
        rev, _cols = self.lasting(rows, {2: UJ.SCHEME_TARGET})
        change = rev['rows'][0]['scheme_change']
        self.assertEqual(change['status'], 'refused')
        self.assertIn('is a pay scheme for Indonesia, but P3A Ann works in Vietnam', change['why'])
        self.assertIn('Change their Country of work in the same row', change['why'])

    # ================================================================= T11
    def test_t11_readers_name_each_persons_own_scheme(self):
        self.Row.create({'employee_id': self.ann.id, 'config_id': self.daily.id,
                         'date_from': '2026-01-01'})
        self.Row.create({'employee_id': self.bob.id, 'config_id': self.monthly.id,
                         'date_from': '2026-01-01'})
        people = self.Upd._people_schemes([self.ann.id, self.bob.id])
        self.assertEqual(people[self.ann.id]['ids'], {self.daily.id})
        self.assertEqual(people[self.bob.id]['ids'], {self.monthly.id})
        ctx = self.Upd._scheme_context(self.Upd._desk(), [self.ann.id, self.bob.id], {'P3BX'})
        self.assertTrue(self.Upd._is_off_scheme(ctx, self.ann.id, 'c:P3BX'),
                        "Ann's own scheme has no meal item")
        self.assertFalse(self.Upd._is_off_scheme(ctx, self.bob.id, 'c:P3BX'))
        # the year-to-date sheets: each person's own tax year
        if 'tax_year_start_month' in self.daily._fields:
            self.daily.tax_year_start_month = '4'
            months = self.env['pb.updates.ytd.line']._ty_months_of([self.ann.id, self.bob.id])
            self.assertEqual((months[self.ann.id], months[self.bob.id]), (4, 1))

    # ================================================================= T14
    def test_t14_rights(self):
        portal = self._user('p2b.portal', ('base.group_portal',), self.company)
        with self.assertRaises(AccessError):
            self.env['pb.scheme.board'].with_user(portal).person_set(
                self.ann.ids, self.daily.id, False, '2027-01-01')
        self.assertFalse(self.env['pb.person.scheme'].with_user(self.proposer).has_access('write'))
        self.assertFalse(self.env['pb.person.scheme'].with_user(portal).has_access('read'))
