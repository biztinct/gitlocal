# -*- coding: utf-8 -*-
"""PSCHEME P2b A — a permanent move changes the pay scheme from a date.

T1  new Country of work + scheme, effective today: Country of work written,
    the old row ended the day before, the new row from the date (source
    job change); next month's pay run = the new scheme only
T2  effective the 15th: that month's run still has the old scheme, the next
    month's the new one (owner ruling R6)
T3  scheduled: nothing written before the day; the job writes it as T1
T4  company move: the old company's rows end first; a scheme of the old
    company is refused with its sentence; no scheme at all is refused
T5  take it back: rows and Country of work exactly restored; refused with a
    plain sentence after a later hand change
T6  team only: no row touched, the "stays" sentence once
T7  the what-if reads the person's own scheme first
T14 rights: a portal user is refused; nobody gains write on the rows
"""
from datetime import date, timedelta
from unittest.mock import patch

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user


@tagged('post_install', '-at_install', 'pscheme', 'pscheme_p2b')
class TestJobChangePayScheme(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        vnd = cls.env.ref('base.VND')
        vnd.active = True
        cls.company = cls.env['res.company'].create({'name': 'DEMO PS2B Co', 'currency_id': vnd.id})
        cls.other = cls.env['res.company'].create({'name': 'DEMO PS2B Other', 'currency_id': vnd.id})
        cls.env.user.company_ids = [(4, cls.company.id), (4, cls.other.id)]
        cls.env.user.company_id = cls.company
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True, mail_notrack=True,
                                       allowed_company_ids=[cls.company.id, cls.other.id]))
        for co in (cls.company, cls.other):
            cls.env['biz.approval.seed'].sudo().set_no_approval_needed(co, 'jobchange')
            try:
                cls.env['biz.approval.seed'].sudo().set_no_approval_needed(co, 'schememap')
            except Exception:   # noqa: BLE001
                pass
        cls.JC = cls.env['pb.job.change']
        cls.Board = cls.env['pb.job.change.board']
        cls.Row = cls.env['pb.person.scheme'].sudo()
        Dept = cls.env['hr.department']
        cls.team = Dept.create({'name': 'DEMO PS2B Team', 'company_id': cls.company.id})
        cls.team2 = Dept.create({'name': 'DEMO PS2B Team two', 'company_id': cls.company.id})
        cls.far = Dept.create({'name': 'DEMO PS2B Far team', 'company_id': cls.other.id})
        cls.cal = cls.company.resource_calendar_id or cls.env['resource.calendar'].create(
            {'name': 'DEMO PS2B Hours', 'company_id': cls.company.id})
        cls.cal_other = cls.other.resource_calendar_id or cls.env['resource.calendar'].create(
            {'name': 'DEMO PS2B Other hours', 'company_id': cls.other.id})
        Config = cls.env['hr.formula.config']

        def scheme(name, code, cycle, country, company):
            return Config.create({'name': name, 'code': code, 'cycle_type': cycle,
                                  'country_code': country, 'company_id': company.id,
                                  'state': 'active'})
        cls.vn = scheme('DEMO PS2B Vietnam monthly', 'DEMOP2BVN', 'end_cycle', 'VN', cls.company)
        cls.idn = scheme('DEMO PS2B Indonesia monthly', 'DEMOP2BID', 'end_cycle', 'ID', cls.company)
        cls.id_adv = scheme('DEMO PS2B Indonesia advance', 'DEMOP2BIA', 'mid_cycle', 'ID', cls.company)
        cls.far_vn = scheme('DEMO PS2B Other Vietnam', 'DEMOP2BOV', 'end_cycle', 'VN', cls.other)
        rule_e = cls.env['hr.formula.rule'].create({'config_id': cls.idn.id, 'code': 'P2BADVT',
                                                    'name': 'DEMO Advance taken',
                                                    'column_type': 'input', 'sequence': 1})
        rule_m = cls.env['hr.formula.rule'].create({'config_id': cls.id_adv.id, 'code': 'P2BADV',
                                                    'name': 'DEMO Advance',
                                                    'column_type': 'input', 'sequence': 1})
        cls.env['hr.payroll.cycle.component.mapping'].sudo().create({
            'mid_cycle_config_id': cls.id_adv.id, 'end_cycle_config_id': cls.idn.id,
            'mid_component_id': rule_m.id, 'end_component_id': rule_e.id})
        cls.seq = 0

    # ------------------------------------------------------------ fixtures
    def person(self, country='VN', own=True, since=date(2025, 1, 1)):
        type(self).seq += 1
        emp = self.env['hr.employee'].create({
            'name': 'DEMO PS2B Person %s' % self.seq, 'company_id': self.company.id,
            'department_id': self.team.id, 'payroll_country': country,
            'resource_calendar_id': self.cal.id})
        contract = self.env['hr.contract'].create({
            'name': 'DEMO PS2B contract %s' % self.seq, 'employee_id': emp.id,
            'wage': 1000.0, 'state': 'open', 'date_start': '2024-01-01',
            'company_id': self.company.id, 'department_id': self.team.id,
            'resource_calendar_id': self.cal.id})
        if own:
            self.Row.create({'employee_id': emp.id, 'config_id': self.vn.id,
                             'date_from': since, 'source': 'hand'})
        return emp, contract

    def today(self):
        return self.JC._today_for(self.company)

    def vals(self, emp, **kw):
        out = {'employee_id': emp.id, 'reason_kind': 'transfer',
               'reason': 'Moves to the Jakarta office for good',
               'effective_date': fields.Date.to_string(self.today()),
               'new_payroll_country': 'ID', 'new_scheme_id': self.idn.id,
               'new_advance_scheme_id': 0}
        out.update(kw)
        return out

    def rows(self, emp):
        return self.Row.search([('employee_id', '=', emp.id)], order='date_from, id')

    def runs(self, emp, month_start):
        wizard = self.env['pb.payrun.wizard'].with_company(self.company)
        end = month_start + relativedelta(months=1, days=-1)
        return [c for c in (self.vn, self.idn) if emp.id in wizard._eligible_employees(
            employee_ids=emp.ids, formula_config_id=c.id,
            date_start=fields.Date.to_string(month_start), date_end=fields.Date.to_string(end))]

    # ================================================================== T1
    def test_t1_country_and_scheme_from_today(self):
        emp, _c = self.person()
        day = self.today()
        answer = self.Board.send(self.vals(emp))
        rec = self.JC.browse(answer['id'])
        self.assertEqual(rec.state, 'applied', answer)
        emp.invalidate_recordset()
        self.assertEqual(emp.payroll_country, 'ID')
        old, new = self.rows(emp)
        self.assertEqual((old.config_id, old.date_to), (self.vn, day - timedelta(days=1)))
        self.assertEqual((new.config_id, new.date_from, new.date_to, new.source),
                         (self.idn, day, False, 'job_change'))
        if 'pb.payrun.wizard' in self.env:
            nxt = day.replace(day=1) + relativedelta(months=1)
            self.assertEqual(self.runs(emp, nxt), [self.idn])
        # the change's own page names the pay scheme row
        labels = [r['label'] for r in self.Board.get_change(rec.id)['rows']]
        self.assertIn('Pay scheme', labels)
        self.assertIn('Country of work', labels)

    # ================================================================== T2
    def test_t2_the_15th_old_scheme_pays_that_month(self):
        if 'pb.payrun.wizard' not in self.env:
            self.skipTest('no pay run wizard')
        emp, _c = self.person()
        today = self.today()
        d15 = today.replace(day=15) if today.day > 15 else \
            (today.replace(day=1) - relativedelta(months=1)).replace(day=15)
        preview = self.Board.preview(self.vals(emp, effective_date=fields.Date.to_string(d15)))
        self.assertIn('still pays', preview['scheme_r6'])
        self.assertIn(self.vn.name, preview['scheme_r6'])
        self.assertIn(self.idn.name, preview['scheme_line'])
        self.Board.send(self.vals(emp, effective_date=fields.Date.to_string(d15)))
        month = d15.replace(day=1)
        self.assertEqual(self.runs(emp, month), [self.vn], "the old scheme pays that month")
        self.assertEqual(self.runs(emp, month + relativedelta(months=1)), [self.idn])
        # a change dated the 1st says nothing about who still pays
        emp2, _c = self.person()
        first = today.replace(day=1)
        self.assertFalse(self.Board.preview(self.vals(emp2, effective_date=fields.Date.to_string(
            first)))['scheme_r6'])

    # ================================================================== T3
    def test_t3_scheduled_nothing_until_the_day(self):
        emp, _c = self.person()
        start = self.today() + timedelta(days=12)
        rec = self.JC.browse(self.Board.send(self.vals(
            emp, effective_date=fields.Date.to_string(start)))['id'])
        self.assertEqual(rec.state, 'scheduled')
        self.assertEqual(len(self.rows(emp)), 1, "no row before the day")
        emp.invalidate_recordset()
        self.assertEqual(emp.payroll_country, 'VN')
        self.JC._cron_start_due()
        self.assertEqual(rec.state, 'scheduled')
        with patch.object(type(self.JC), '_today_for', lambda s, company=None: start):
            self.assertEqual(self.JC._cron_start_due().get('started'), 1)
        self.assertEqual(rec.state, 'applied')
        old, new = self.rows(emp)
        self.assertEqual(old.date_to, start - timedelta(days=1))
        self.assertEqual((new.config_id, new.date_from), (self.idn, start))
        emp.invalidate_recordset()
        self.assertEqual(emp.payroll_country, 'ID')

    # ================================================================== T4
    def test_t4_company_move_ends_the_old_company_first(self):
        emp, _c = self.person()
        day = self.today()
        base = dict(new_company_id=self.other.id, new_payroll_country=False,
                    new_department_id=self.far.id, new_resource_calendar_id=self.cal_other.id)
        # no scheme: refused, naming the new company
        problems = self.Board.preview(self.vals(emp, new_scheme_id=0, **base))['problems']
        self.assertTrue(any('A move to another company needs one of its pay schemes' in p
                            and self.other.name in p for p in problems), problems)
        # a scheme of the old company: refused with its sentence
        problems = self.Board.preview(self.vals(emp, new_scheme_id=self.vn.id, **base))['problems']
        self.assertTrue(any('%s belongs to %s, so it cannot pay' % (self.vn.name, self.company.name)
                            in p for p in problems), problems)
        options = self.Board.scheme_options(emp.id, '', self.other.id, self.far.id)
        self.assertEqual([c['id'] for c in options['cards']], [self.far_vn.id])
        self.assertEqual(options['default_id'], self.far_vn.id)
        answer = self.Board.send(self.vals(emp, new_scheme_id=self.far_vn.id, **base))
        rec = self.JC.browse(answer['id'])
        self.assertEqual(rec.state, 'applied', answer)
        emp.invalidate_recordset()
        self.assertEqual(emp.company_id, self.other)
        old, new = self.rows(emp)
        self.assertEqual((old.config_id, old.date_to), (self.vn, day - timedelta(days=1)))
        self.assertEqual((new.config_id, new.date_from, new.company_id),
                         (self.far_vn, day, self.other))

    # ================================================================== T5
    def test_t5_take_it_back_exactly(self):
        emp, contract = self.person()
        later = self.today() + timedelta(days=40)
        self.rows(emp)[0].date_to = later - timedelta(days=1)
        self.Row.create({'employee_id': emp.id, 'config_id': self.idn.id,
                         'date_from': later, 'source': 'hand'})
        before = sorted((r.config_id.id, r.date_from, r.date_to, r.source) for r in self.rows(emp))
        rec = self.JC.browse(self.Board.send(self.vals(
            emp, new_advance_scheme_id=self.id_adv.id))['id'])
        self.assertEqual(rec.state, 'applied')
        self.assertIn(self.id_adv, self.rows(emp).config_id)
        self.Board.act(rec.id, 'undo')
        self.assertEqual(rec.state, 'undone')
        emp.invalidate_recordset()
        self.assertEqual(emp.payroll_country, 'VN')
        after = sorted((r.config_id.id, r.date_from, r.date_to, r.source) for r in self.rows(emp))
        self.assertEqual(after, before, "rows exactly as they were")
        # a hand change after the job change: refused in a sentence
        emp2, _c = self.person()
        rec2 = self.JC.browse(self.Board.send(self.vals(emp2))['id'])
        self.rows(emp2)[-1].date_to = self.today() + timedelta(days=90)
        with self.assertRaises(UserError) as caught:
            rec2.action_undo()
        self.assertIn("pay scheme since", str(caught.exception))
        self.assertIn(emp2.name, str(caught.exception))
        self.assertEqual(rec2.state, 'applied')

    # ================================================================== T6
    def test_t6_team_only_touches_no_row(self):
        emp, _c = self.person()
        before = [(r.id, r.date_to) for r in self.rows(emp)]
        vals = self.vals(emp, new_payroll_country=False, new_scheme_id=0,
                         new_department_id=self.team2.id)
        preview = self.Board.preview(vals)
        self.assertEqual(preview['scheme_stays'],
                         "Their pay scheme stays %s. Change it here if this move changes "
                         "who pays them." % self.vn.name)
        self.assertFalse(preview['scheme_line'])
        rec = self.JC.browse(self.Board.send(vals)['id'])
        self.assertEqual(rec.state, 'applied')
        self.assertEqual([(r.id, r.date_to) for r in self.rows(emp)], before)
        self.assertNotIn('person_rows', rec._json('written_json', {}))

    # ================================================================== T7
    def test_t7_what_if_reads_the_person_first(self):
        emp, _c = self.person()
        # the team below is paid by another scheme on the map — the person's
        # own row still answers, so moving team "stays"
        self.env['hr.formula.scheme.assignment'].create({
            'config_id': self.idn.id, 'cycle_type': 'any', 'company_id': self.company.id,
            'department_id': self.team2.id})
        draft = self.JC.new({'employee_id': emp.id, 'company_id': self.company.id,
                             'new_department_id': self.team2.id})
        now, after = draft._scheme_now_and_after()
        self.assertEqual((now['id'], after['id']), (self.vn.id, self.vn.id))
        self.assertTrue(after['own'])
        # without a row of their own the team map decides, as before
        emp2, _c = self.person(own=False)
        draft = self.JC.new({'employee_id': emp2.id, 'company_id': self.company.id,
                             'new_department_id': self.team2.id})
        self.assertEqual(draft._scheme_now_and_after()[1]['id'], self.idn.id)

    def test_t7b_choices_follow_the_new_country(self):
        emp, _c = self.person()
        opts = self.Board.scheme_options(emp.id, 'ID')
        self.assertEqual([c['id'] for c in opts['cards']], [self.idn.id])
        self.assertEqual(opts['default_id'], self.idn.id)
        self.assertEqual(opts['advance_default'][str(self.idn.id)], self.id_adv.id)
        self.assertEqual(opts['now_id'], self.vn.id)
        none = self.Board.scheme_options(emp.id, 'MY')
        self.assertFalse(none['cards'])
        self.assertIn('No pay scheme for Malaysia', none['none_words'])
        # an advance that is not one, or a main scheme that is an advance
        problems = self.Board.preview(self.vals(emp, new_scheme_id=self.id_adv.id))['problems']
        self.assertTrue(any('cannot be somebody' in p for p in problems), problems)
        problems = self.Board.preview(self.vals(emp, new_advance_scheme_id=self.vn.id))['problems']
        self.assertTrue(any('is not a mid-month advance' in p for p in problems), problems)

    # ================================================================= T14
    def test_t14_rights(self):
        emp, _c = self.person()
        portal = new_test_user(self.env, login='ps2b_portal', groups='base.group_portal',
                               company_id=self.company.id, company_ids=[(6, 0, [self.company.id])])
        with self.assertRaises(AccessError):
            self.Board.with_user(portal).scheme_options(emp.id, 'ID')
        with self.assertRaises(AccessError):
            self.Board.with_user(portal).send(self.vals(emp))
        officer = new_test_user(self.env, login='ps2b_officer',
                                groups='base.group_user,hr.group_hr_user',
                                company_id=self.company.id, company_ids=[(6, 0, [self.company.id])])
        with self.assertRaises(AccessError):
            self.Board.with_user(officer).send(self.vals(emp))
        for user in (portal, officer):
            self.assertFalse(self.env['pb.person.scheme'].with_user(user).has_access('write'))
        self.assertEqual(len(self.rows(emp)), 1)
