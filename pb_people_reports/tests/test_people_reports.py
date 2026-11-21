# -*- coding: utf-8 -*-
"""People reports on real employee records.

WDGAP S9-B built the screen (owner ruling P6); W3-A (owner rulings PR1 + PR2,
2026-11-17) removed the small-group hiding for HR and added the month-by-month
line. Every figure below is checked against an independent count of the
records.

The fixture is two DEMO companies of their own (so the template's people do
not count), last calendar year (a complete year, so the test does not depend
on today's month).
"""

import base64
import calendar
import io
import json
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged, TransactionCase


@tagged('post_install', '-at_install', 'pb_people_reports')
class TestPeopleReports(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.year = date.today().year - 1
        Y = cls.year
        cls.co_x = env['res.company'].create({'name': 'DEMO Reports X'})
        cls.co_y = env['res.company'].create({'name': 'DEMO Reports Y'})
        Dept = env['hr.department']
        cls.d_big = Dept.create({'name': 'DEMO Big', 'company_id': cls.co_x.id})
        cls.d_small = Dept.create({'name': 'DEMO Small', 'company_id': cls.co_x.id})
        cls.d_mid = Dept.create({'name': 'DEMO Mid', 'company_id': cls.co_x.id})
        cls.d_y = Dept.create({'name': 'DEMO Y dept', 'company_id': cls.co_y.id})
        cls.n = 0

        def emp(company, dept, start, end=None, sex='female', born=None, **kw):
            cls.n += 1
            vals = {'name': 'DEMO R%03d' % cls.n, 'company_id': company.id,
                    'department_id': dept.id, 'sex': sex,
                    'birthday': born or date(1990, 1, 1)}
            e = env['hr.employee'].with_company(company).create(vals)
            e.write({'date_of_joining': start} if 'date_of_joining' in e._fields
                    else {'contract_date_start': start})
            if end:
                e.write({'departure_date': end,
                         'departure_reason_id': env.ref('hr.departure_resigned').id})
                e.write({'active': False})
                e.write({'departure_date': end})          # QF4-W2: date after archiving
            if kw:
                e.write(kw)
            return e
        start_old = date(Y - 3, 1, 1)
        # Big: 12 long-standing people, 6 joiners in March, 5 leavers in June
        for i in range(12):
            emp(cls.co_x, cls.d_big, start_old, sex='female' if i % 2 else 'male',
                born=date(1980 + i, 5, 1))
        for i in range(6):
            emp(cls.co_x, cls.d_big, date(Y, 3, 1 + i), sex='male')
        for i in range(5):
            emp(cls.co_x, cls.d_big, start_old, end=date(Y, 6, 10 + i), sex='female')
        # Small: 3 people, one joined in May
        emp(cls.co_x, cls.d_small, start_old, sex='male', born=date(2003, 2, 1))
        emp(cls.co_x, cls.d_small, start_old, sex='male', born=date(1970, 2, 1))
        emp(cls.co_x, cls.d_small, date(Y, 5, 4), sex='female', born=date(1995, 2, 1))
        # Mid: 6 people, 2 joined in September
        for i in range(4):
            emp(cls.co_x, cls.d_mid, start_old, sex='female')
        for i in range(2):
            emp(cls.co_x, cls.d_mid, date(Y, 9, 1), sex='female')
        # Y: 8 people, and 5 joiners in April
        for i in range(8):
            emp(cls.co_y, cls.d_y, start_old)
        for i in range(5):
            emp(cls.co_y, cls.d_y, date(Y, 4, 1 + i))
        # a person who MOVES from X to Y on 1 August (one person, two records)
        cls.mover_x = emp(cls.co_x, cls.d_mid, start_old, end=date(Y, 7, 31))
        cls.mover_y = emp(cls.co_y, cls.d_y, date(Y, 8, 1))
        if 'pb_person_id' in cls.mover_x._fields and 'pb.person' in env:
            person = env['pb.person'].for_employee(cls.mover_x)
            cls.mover_y.pb_person_id = person.id
            cls.has_person = True
        else:
            cls.has_person = False

        both = cls.co_x | cls.co_y
        cls.u_hr = new_test_user(env, login='s9b_rep_hr', groups='base.group_user,hr.group_hr_user',
                                 company_id=cls.co_x.id, company_ids=[(6, 0, both.ids)])
        cls.u_hr_x = new_test_user(env, login='s9b_rep_hrx', groups='base.group_user,hr.group_hr_user',
                                   company_id=cls.co_x.id, company_ids=[(6, 0, cls.co_x.ids)])
        pay_groups = ','.join(x for x in (
            'base.group_user', 'om_hr_payroll.group_hr_payroll_user',
            'pb_hr_payroll_base.group_payroll_base_officer',
            'pb_hr_payroll_base.group_payroll_analytics_user')
            if env.ref(x, raise_if_not_found=False))
        cls.u_pay = new_test_user(env, login='s9b_rep_pay', groups=pay_groups,
                                  company_id=cls.co_x.id, company_ids=[(6, 0, both.ids)])
        cls.u_portal = new_test_user(env, login='s9b_rep_portal', groups='base.group_portal',
                                     company_id=cls.co_x.id)
        cls.u_internal = new_test_user(env, login='s9b_rep_emp', groups='base.group_user',
                                       company_id=cls.co_x.id)
        cls.u_mgr = new_test_user(env, login='s9b_rep_mgr', groups='base.group_user',
                                  company_id=cls.co_x.id)
        # a line manager: an employee of Big with a login, managing Big's people
        cls.e_mgr = emp(cls.co_x, cls.d_big, start_old, sex='male', user_id=cls.u_mgr.id)
        env['hr.employee'].search([('department_id', '=', cls.d_big.id),
                                   ('id', '!=', cls.e_mgr.id)]).write({'parent_id': cls.e_mgr.id})
        env.flush_all()

    # ------------------------------------------------------------ helpers
    def R(self, user=None, companies=None):
        user = user or self.u_hr
        companies = companies or (self.co_x | self.co_y)
        return self.env(user=user.id, su=False, context=dict(
            self.env.context, allowed_company_ids=companies.ids))['pb.people.reports']

    def report(self, view='headcount', user=None, companies=None, **params):
        params.setdefault('period', str(self.year))
        return self.R(user, companies).get_report(view, params)

    def records(self, company_ids, dept=None):
        Emp = self.env['hr.employee'].with_context(active_test=False)
        out = []
        for e in Emp.search([('company_id', 'in', company_ids), ('name', 'like', 'DEMO R')]):
            if dept and e.department_id.id != dept:
                continue
            start = e.date_of_joining if 'date_of_joining' in e._fields else e.contract_date_start
            out.append((start, e.departure_date))
        return out

    def head_at(self, company_ids, day, dept=None):
        """An independent count: employment records employed that day."""
        return sum(1 for s, e in self.records(company_ids, dept)
                   if (not s or s <= day) and (not e or e > day))

    def moves_in(self, company_ids, year, month, dept=None):
        """Independent joiners and leavers of one month (records, not people)."""
        recs = self.records(company_ids, dept)
        j = sum(1 for s, _e in recs if s and (s.year, s.month) == (year, month))
        l = sum(1 for _s, e in recs if e and (e.year, e.month) == (year, month))
        return j, l

    def month_ends(self, year):
        return [date(year, m, calendar.monthrange(year, m)[1]) for m in range(1, 13)]

    # ------------------------------------------------------------ 80: who
    def test_80_hr_only(self):
        self.assertTrue(self.R().can_open())
        self.assertTrue(self.R().get_options()['allowed'])
        # the payroll team holds the HR group only because payroll implies it:
        # refused. Somebody who is HR AND payroll passes through the HR group.
        self.assertTrue(self.u_pay.has_group('hr.group_hr_user'))
        both = new_test_user(self.env, login='s9b_rep_both',
                             groups=self.u_pay.group_ids.get_external_id() and ','.join(
                                 v for v in self.u_pay.group_ids.get_external_id().values() if v)
                             + ',hr.group_hr_user',
                             company_id=self.co_x.id, company_ids=[(6, 0, self.co_x.ids)])
        self.assertTrue(self.R(both, self.co_x).can_open())
        # W3-A: the access rule is unchanged by PR1 — payroll, line managers,
        # employees (portal or internal login) are still refused
        for user in (self.u_pay, self.u_portal, self.u_internal, self.u_mgr):
            R = self.R(user, self.co_x)
            self.assertFalse(R.can_open(), user.login)
            self.assertEqual(set(R.get_options()), {'allowed', 'why'}, user.login)
            with self.assertRaises(AccessError):
                R.get_report('headcount', {'period': str(self.year)})
            with self.assertRaises(AccessError):
                R.export_xlsx('age_gender', {'period': str(self.year)})

    def test_81_only_the_companies_they_already_see(self):
        opts = self.R(self.u_hr_x, self.co_x).get_options()
        self.assertEqual([c['id'] for c in opts['companies']], [self.co_x.id])
        # asking for company Y by id is ignored: they get X only
        data = self.report(user=self.u_hr_x, companies=self.co_x, company_id=self.co_y.id)
        expected = self.head_at([self.co_x.id], date(self.year, 12, 31))
        self.assertEqual(data['tiles']['h_end'], expected)

    # ------------------------------------------------------------ 82: figures
    def test_82_tiles_reconcile_with_the_records(self):
        data = self.report(company_id=self.co_x.id)
        start = self.head_at([self.co_x.id], date(self.year - 1, 12, 31))
        end = self.head_at([self.co_x.id], date(self.year, 12, 31))
        t = data['tiles']
        self.assertEqual(t['h0'], start)
        self.assertEqual(t['h_end'], end)
        self.assertEqual(t['l'], 6)          # X: 5 in June + the mover
        self.assertEqual(t['j'], 9)          # 6 + 1 + 2
        self.assertEqual(t['h_end'], t['h0'] + 9 - 6)
        self.assertEqual(t['rate'], round(6 * 100.0 / ((start + end) / 2.0), 1))
        group = self.report()
        self.assertEqual(group['tiles']['l'], 5)     # the mover is not a group leaver
        self.assertEqual(group['tiles']['j'], 14)

    def test_82b_month_by_month_line(self):
        """PR2: headcount at every month end, joiners and leavers per month —
        each one equal to an independent count of the records."""
        for co in (self.co_x, self.co_y):
            data = self.report(company_id=co.id)
            months = data['months']
            self.assertEqual(len(months), 12)
            for i, day in enumerate(self.month_ends(self.year)):
                mo = months[i]
                self.assertEqual(mo['key'], day.strftime('%Y-%m'))
                self.assertEqual(mo['h'], self.head_at([co.id], day), (co.name, mo['key']))
                self.assertEqual((mo['j'], mo['l']), self.moves_in([co.id], self.year, day.month),
                                 (co.name, mo['key']))
            self.assertEqual(sum(m['j'] for m in months), data['tiles']['j'])
            self.assertEqual(sum(m['l'] for m in months), data['tiles']['l'])
            self.assertEqual(months[-1]['h'], data['tiles']['h_end'])
            # one company, no department: the line is exact month to month
            prev = data['tiles']['h0']
            for mo in months:
                self.assertEqual(mo['h'], prev + mo['j'] - mo['l'], mo['key'])
                self.assertEqual(mo['net'], mo['h'] - prev)
                prev = mo['h']

    def test_82c_quarters_group_the_months(self):
        data = self.report('movement', company_id=self.co_x.id)
        months, quarters = data['months'], data['quarters']
        self.assertEqual([q['label'] for q in quarters],
                         ['Q%s %s' % (n, self.year) for n in (1, 2, 3, 4)])
        self.assertEqual(sorted(i for q in quarters for i in q['months']), list(range(12)))
        for q in quarters:
            self.assertEqual(q['j'], sum(months[i]['j'] for i in q['months']))
            self.assertEqual(q['l'], sum(months[i]['l'] for i in q['months']))
            self.assertEqual(q['h'], months[q['months'][-1]]['h'])
        # X: 6 joiners in March (Q1); 5 leavers in June (Q2); the mover in July (Q3)
        self.assertEqual(quarters[0]['j'], 6)
        self.assertEqual(quarters[1]['l'], 5)
        self.assertEqual(quarters[2]['l'], 1)

    def test_83_small_department_is_shown(self):
        """PR1: a department of 3 is shown with its real figures."""
        data = self.report(company_id=self.co_x.id)
        rows = {r['name']: r for r in data['table']['rows']}
        small = rows['DEMO Small']
        self.assertEqual(small['h'], self.head_at([self.co_x.id], date(self.year, 12, 31),
                                                  self.d_small.id))
        self.assertEqual(small['h'], 3)
        self.assertEqual(small['h0'], 2)
        self.assertEqual((small['j'], small['l']), (1, 0))
        self.assertEqual(small['rate'], 0.0)
        # the rows add up to the total, which is the tiles
        for col in ('h0', 'h', 'j', 'l'):
            self.assertEqual(sum(r[col] for r in rows.values()), data['table']['total'][col], col)
        self.assertEqual(data['table']['total']['h'], data['tiles']['h_end'])

    def test_84_a_small_department_on_its_own(self):
        data = self.report(company_id=self.co_x.id, department_id=self.d_small.id)
        self.assertNotIn('too_small', data)
        self.assertEqual(data['tiles']['h_end'], 3)
        self.assertEqual(data['tiles']['j'], 1)
        may = data['months'][4]
        self.assertEqual((may['j'], may['h']), (1, 3))
        self.assertEqual(data['months'][3]['h'], 2)

    def test_85_department_on_its_own_matches_its_row(self):
        full = self.report(company_id=self.co_x.id)
        rows = {r['name']: r for r in full['table']['rows']}
        for dept in (self.d_big, self.d_mid, self.d_small):
            one = self.report(company_id=self.co_x.id, department_id=dept.id)
            row = rows[dept.name]
            for col, tile in (('h0', 'h0'), ('h', 'h_end'), ('j', 'j'), ('l', 'l')):
                self.assertEqual(one['tiles'][tile], row[col], (dept.name, col))

    def test_86_company_on_its_own_matches_the_group_table(self):
        group = self.report()
        rows = {r['name']: r for r in group['table']['rows']}
        for co in (self.co_x, self.co_y):
            one = self.report(company_id=co.id)
            for col, tile in (('h0', 'h0'), ('h', 'h_end'), ('j', 'j'), ('l', 'l')):
                self.assertEqual(one['tiles'][tile], rows[co.name][col], (co.name, col))

    def test_87_a_move_inside_the_group_is_not_turnover(self):
        if not self.has_person:
            self.skipTest('no person link on this database')
        R = self.R()
        P = R._params({'period': str(self.year)})
        records, _n = R._people_records(P['visible'])
        group = R._measure(records, P['ends'])
        x = R._measure([r for r in records if r['company_id'] == self.co_x.id], P['ends'])
        y = R._measure([r for r in records if r['company_id'] == self.co_y.id], P['ends'])
        # X: 5 leavers in June + the mover; Y: the mover joins; group: neither
        self.assertEqual(sum(x['leaves']), 6)
        self.assertEqual(sum(y['joins']), 6)          # 5 in April + the mover
        self.assertEqual(sum(group['leaves']), 5)
        self.assertEqual(sum(group['joins']), sum(x['joins']) + 5)
        # and the group's monthly line counts the mover in every month
        g = self.report()
        aug = g['months'][7]
        self.assertEqual((aug['j'], aug['l']), (0, 0))

    def test_88_breakdowns_show_every_group_and_work_per_department(self):
        """PR1: no group hidden, and age / gender / leaving per department."""
        data = self.report('age_gender', company_id=self.co_x.id)
        self.assertEqual(data['total'], data['tiles']['h_end'])
        for block in (data['genders'], data['ages']):
            self.assertEqual(sum(r['n'] for r in block), data['total'])
            for r in block:
                self.assertIsInstance(r['n'], int)
        small = self.report('age_gender', company_id=self.co_x.id, department_id=self.d_small.id)
        self.assertEqual(small['total'], 3)
        g = {r['key']: r['n'] for r in small['genders']}
        self.assertEqual((g['male'], g['female']), (2, 1))
        ages = {r['key']: r['n'] for r in small['ages']}
        self.assertEqual(ages['u25'], 1)            # born 2003
        self.assertEqual(ages['55p'], 1)            # born 1970
        self.assertEqual(round(sum(r['pct'] for r in small['genders'])), 100)
        leaving = self.report('leaving', company_id=self.co_x.id, department_id=self.d_big.id)
        reasons = {r['key']: r['n'] for r in leaving['reasons']}
        self.assertEqual(reasons['resigned'], 5)
        self.assertEqual(leaving['total'], 5)
        service = self.report('service', company_id=self.co_x.id, department_id=self.d_mid.id)
        self.assertEqual(sum(r['n'] for r in service['service_rows']), service['total'])
        self.assertEqual({r['key']: r['n'] for r in service['service_rows']}['u1'], 2)

    def test_89_group_breakdown_adds_up_from_its_companies(self):
        group = self.report('age_gender')
        x = self.report('age_gender', company_id=self.co_x.id)
        y = self.report('age_gender', company_id=self.co_y.id)
        for key in ('female', 'male', 'other', 'none'):
            g = next(r for r in group['genders'] if r['key'] == key)['n']
            a = next(r for r in x['genders'] if r['key'] == key)['n']
            b = next(r for r in y['genders'] if r['key'] == key)['n']
            self.assertEqual(g, a + b, key)

    def test_93_last_12_months(self):
        """PR1: "Last 12 months" is offered beside the calendar years."""
        opts = self.R().get_options()
        keys = [p['key'] for p in opts['periods']]
        self.assertIn('last12', keys)
        self.assertIn(str(self.year), keys)
        self.assertEqual(len(keys), 6)
        data = self.report(company_id=self.co_x.id, period='last12')
        today = fields.Date.context_today(self.R())
        last = today.replace(day=1) - relativedelta(days=1)
        months = data['months']
        self.assertEqual(len(months), 12)
        self.assertEqual(months[-1]['key'], last.strftime('%Y-%m'))
        self.assertEqual(months[0]['key'], (last.replace(day=1) - relativedelta(months=11))
                         .strftime('%Y-%m'))
        for mo in months:
            y, m = (int(x) for x in mo['key'].split('-'))
            day = date(y, m, calendar.monthrange(y, m)[1])
            self.assertEqual(mo['h'], self.head_at([self.co_x.id], day), mo['key'])
        # quarters still group the months, even when they are cut by the window
        self.assertEqual(sorted(i for q in data['quarters'] for i in q['months']),
                         list(range(12)))
        # an unknown period falls back to the first one offered
        self.assertEqual(self.report(period='1066')['period'],
                         self.report(period=keys[0])['period'])

    def test_94_nothing_is_hidden_anywhere(self):
        for view in ('headcount', 'movement', 'leaving', 'age_gender', 'service'):
            for params in ({}, {'company_id': self.co_x.id},
                           {'company_id': self.co_x.id, 'department_id': self.d_small.id}):
                data = self.report(view, **params)
                text = json.dumps(data, default=str)
                self.assertNotIn('"h": true', text)
                self.assertNotIn('Hidden', text)
                self.assertNotIn('fewer than 5', text)
                self.assertNotIn('too_small', data)
                self.assertNotIn('dept_not_offered', data)

    # ------------------------------------------------------------ 90: exports, money, silence
    def test_90_the_download_matches_the_screen(self):
        import openpyxl
        for view in ('headcount', 'movement', 'age_gender', 'leaving', 'service'):
            params = {'period': str(self.year), 'company_id': self.co_x.id}
            data = self.report(view, company_id=self.co_x.id)
            f = self.R().export_xlsx(view, params)
            book = openpyxl.load_workbook(io.BytesIO(base64.b64decode(f['data'])))
            sheet = book.active
            cells = {}
            for row in sheet.iter_rows(values_only=True):
                if row and row[0] is not None:
                    cells.setdefault(str(row[0]), []).append(list(row[1:]))
            if view in ('headcount', 'movement'):
                for mo in data['months']:
                    got = cells[mo['label']][-1]
                    self.assertEqual(got[:4], [mo['h'], mo['j'], mo['l'], mo['net']], mo['label'])
                for q in data['quarters']:
                    got = cells[q['label']][-1]
                    self.assertEqual(got[:4], [q['h'], q['j'], q['l'], q['net']], q['label'])
            if view == 'headcount':
                for r in data['table']['rows']:
                    got = cells[r['name']][-1]
                    self.assertEqual(got[:4], [r['h0'], r['h'], r['j'], r['l']])
            if view == 'age_gender':
                for r in data['genders']:
                    self.assertEqual(cells[r['label']][-1][0], r['n'])
            blob = json.dumps([list(r) for r in sheet.iter_rows(values_only=True)], default=str)
            self.assertNotIn('Odoo', blob)
            self.assertNotIn('Hidden', blob)

    def test_91_no_money_anywhere(self):
        for view in ('headcount', 'movement', 'leaving', 'age_gender', 'service'):
            data = self.report(view)
            text = json.dumps(data, default=str).lower()
            for word in ('currency', 'wage', 'salary', 'amount'):
                self.assertNotIn(word, text, view)

    def test_92_silent_install(self):
        env = self.env
        self.assertTrue(env['pb.people.reports']._abstract)
        data = env['ir.model.data'].sudo().search([('module', '=', 'pb_people_reports'),
                                                  ('model', 'not in', ('ir.model', 'ir.model.fields',
                                                                       'ir.model.constraint',
                                                                       'ir.module.module'))])
        self.assertFalse(data.filtered(lambda d: d.model in ('ir.cron', 'mail.template',
                                                              'res.groups', 'ir.rule')))
