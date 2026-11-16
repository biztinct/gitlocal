# -*- coding: utf-8 -*-
"""WDGAP S9-B (owner ruling P6) — People reports on real employee records.

The fixture is two DEMO companies of their own (so the template's people do
not count), last calendar year (a complete year, so the test does not depend
on today's month).
"""

import base64
import io
import json
from datetime import date

from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged, TransactionCase

HIDDEN_WORD = 'Hidden (small group)'


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
        emp(cls.co_x, cls.d_small, start_old, sex='male')
        emp(cls.co_x, cls.d_small, start_old, sex='male')
        emp(cls.co_x, cls.d_small, date(Y, 5, 4), sex='female')
        # Mid: 6 people, 2 joined in September
        for i in range(4):
            emp(cls.co_x, cls.d_mid, start_old, sex='female')
        for i in range(2):
            emp(cls.co_x, cls.d_mid, date(Y, 9, 1), sex='female')
        # Y: 8 people
        for i in range(8):
            emp(cls.co_y, cls.d_y, start_old)
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
        env.flush_all()

    # ------------------------------------------------------------ helpers
    def R(self, user=None, companies=None):
        user = user or self.u_hr
        companies = companies or (self.co_x | self.co_y)
        return self.env(user=user.id, su=False, context=dict(
            self.env.context, allowed_company_ids=companies.ids))['pb.people.reports']

    def report(self, view='headcount', user=None, companies=None, **params):
        params.setdefault('year', self.year)
        return self.R(user, companies).get_report(view, params)

    def head_at(self, company_ids, day, dept=None):
        """An independent count: employment records employed that day."""
        Emp = self.env['hr.employee'].with_context(active_test=False)
        n = 0
        for e in Emp.search([('company_id', 'in', company_ids), ('name', 'like', 'DEMO R')]):
            start = e.date_of_joining if 'date_of_joining' in e._fields else e.contract_date_start
            end = e.departure_date
            if (not start or start <= day) and (not end or end >= day):
                if not dept or e.department_id.id == dept:
                    n += 1
        return n

    def walk(self, obj):
        if isinstance(obj, dict):
            yield obj
            for v in obj.values():
                yield from self.walk(v)
        elif isinstance(obj, list):
            for v in obj:
                yield from self.walk(v)

    # ------------------------------------------------------------ 80: who
    def test_80_hr_only(self):
        self.assertTrue(self.R().can_open())
        self.assertTrue(self.R().get_options()['allowed'])
        for user in (self.u_pay, self.u_portal):
            R = self.R(user, self.co_x)
            self.assertFalse(R.can_open())
            self.assertEqual(set(R.get_options()), {'allowed', 'why'})
            with self.assertRaises(AccessError):
                R.get_report('headcount', {'year': self.year})
            with self.assertRaises(AccessError):
                R.export_xlsx('age_gender', {'year': self.year})

    def test_81_only_the_companies_they_already_see(self):
        opts = self.R(self.u_hr_x, self.co_x).get_options()
        self.assertEqual([c['id'] for c in opts['companies']], [self.co_x.id])
        # asking for company Y by id is ignored: they get X only
        data = self.report(user=self.u_hr_x, companies=self.co_x, company_id=self.co_y.id)
        expected = self.head_at([self.co_x.id], date(self.year, 12, 31))
        self.assertEqual(data['tiles']['h_end']['v'], expected)

    # ------------------------------------------------------------ 82: figures
    def test_82_headcount_reconciles_with_the_records(self):
        data = self.report(company_id=self.co_x.id)
        for i, row in enumerate(data['series']):
            day = date(self.year, i + 1, 1)
            import calendar
            day = day.replace(day=calendar.monthrange(self.year, i + 1)[1])
            if not row['h']['h']:
                self.assertEqual(row['h']['v'], self.head_at([self.co_x.id], day), day)
        self.assertEqual(len(data['series']), 12)
        # March: 6 joiners in Big
        self.assertEqual(data['series'][2]['j']['v'], 6)
        self.assertEqual(data['tiles']['l']['v'], 6)      # 5 in June + the mover in July

    def test_83_small_department_hidden_with_its_complement(self):
        data = self.report(company_id=self.co_x.id)
        rows = {r['name']: r for r in data['table']['rows']}
        small = rows['DEMO Small']
        self.assertTrue(small['h']['h'])
        self.assertIsNone(small['h']['v'])                # the value never leaves the server
        total = data['table']['total']['h']
        self.assertFalse(total['h'])
        shown = sum(r['h']['v'] for r in rows.values() if not r['h']['h'])
        hidden_rows = [r for r in rows.values() if r['h']['h']]
        # nothing can be worked out by subtraction: at least two hidden, adding to 5+
        self.assertGreaterEqual(len(hidden_rows), 2)
        self.assertGreaterEqual(total['v'] - shown, 5)

    def test_84_a_small_department_on_its_own_shows_nothing(self):
        data = self.report(company_id=self.co_x.id, department_id=self.d_small.id)
        self.assertTrue(data['too_small'])
        for cell in self.walk(data):
            if set(cell) == {'v', 'h'}:
                self.assertTrue(cell['h'] or cell['v'] in (0, None), cell)

    def test_85_department_on_its_own_follows_the_table(self):
        full = self.report(company_id=self.co_x.id)
        rows = {r['name']: r for r in full['table']['rows']}
        for dept in (self.d_big, self.d_mid):
            one = self.report(company_id=self.co_x.id, department_id=dept.id)
            row = rows[dept.name]
            for col, tile in (('h', 'h_end'), ('j', 'j'), ('l', 'l')):
                if row[col]['h']:
                    self.assertTrue(one['tiles'][tile]['h'], (dept.name, col))
                else:
                    self.assertEqual(one['tiles'][tile]['v'], row[col]['v'], (dept.name, col))

    def test_86_company_on_its_own_follows_the_group_table(self):
        group = self.report()
        rows = {r['name']: r for r in group['table']['rows']}
        for co in (self.co_x, self.co_y):
            one = self.report(company_id=co.id)
            for col, tile in (('h', 'h_end'), ('j', 'j'), ('l', 'l')):
                if rows[co.name][col]['h']:
                    self.assertTrue(one['tiles'][tile]['h'])
                else:
                    self.assertEqual(one['tiles'][tile]['v'], rows[co.name][col]['v'])

    def test_87_a_move_inside_the_group_is_not_turnover(self):
        if not self.has_person:
            self.skipTest('no person link on this database')
        R = self.R()
        P = R._params({'year': self.year})
        records, _n = R._people_records(P['visible'])
        group = R._measure(records, P['ends'])
        x = R._measure([r for r in records if r['company_id'] == self.co_x.id], P['ends'])
        y = R._measure([r for r in records if r['company_id'] == self.co_y.id], P['ends'])
        # X: 5 leavers in June + the mover; Y: the mover joins; group: neither
        self.assertEqual(sum(x['leaves']), 6)
        self.assertEqual(sum(y['joins']), 1)
        self.assertEqual(sum(group['leaves']), 5)
        self.assertEqual(sum(group['joins']), sum(x['joins']))

    def test_88_breakdowns_hide_small_groups_and_not_per_department(self):
        data = self.report('age_gender', company_id=self.co_x.id)
        self.assertFalse(data['total']['h'])
        cells = data['genders'] + data['ages']
        for row in cells:
            if row['n']['h']:
                self.assertIsNone(row['n']['v'])
                self.assertIsNone(row['pct']['v'])
            else:
                self.assertTrue(row['n']['v'] == 0 or row['n']['v'] >= 5, row)
        for block in (data['genders'], data['ages']):
            hid = [r for r in block if r['n']['h']]
            if hid:
                self.assertGreaterEqual(len(hid), 2)
                shown = sum(r['n']['v'] for r in block if not r['n']['h'])
                self.assertGreaterEqual(data['total']['v'] - shown, 5)
        per_dept = self.report('age_gender', company_id=self.co_x.id, department_id=self.d_big.id)
        self.assertTrue(per_dept['dept_not_offered'])
        self.assertEqual(per_dept['genders'], [])
        leaving = self.report('leaving', company_id=self.co_x.id)
        resigned = next(r for r in leaving['reasons'] if r['key'] == 'resigned')
        self.assertEqual(resigned['n']['v'], 6)

    def test_89_group_and_company_breakdowns_cannot_be_subtracted(self):
        group = self.report('age_gender')
        x = self.report('age_gender', company_id=self.co_x.id)
        y = self.report('age_gender', company_id=self.co_y.id)
        for key in ('female', 'male', 'other', 'none'):
            g = next(r for r in group['genders'] if r['key'] == key)['n']
            a = next(r for r in x['genders'] if r['key'] == key)['n']
            b = next(r for r in y['genders'] if r['key'] == key)['n']
            # the group and one company shown would give the other company away
            self.assertFalse(not g['h'] and not a['h'] and b['h'], key)
            self.assertFalse(not g['h'] and not b['h'] and a['h'], key)

    # ------------------------------------------------------------ 90: exports, money, silence
    def test_90_the_download_hides_the_same_figures(self):
        import openpyxl
        for view in ('headcount', 'age_gender', 'leaving', 'service'):
            data = self.report(view, company_id=self.co_x.id)
            f = self.R().export_xlsx(view, {'year': self.year, 'company_id': self.co_x.id})
            book = openpyxl.load_workbook(io.BytesIO(base64.b64decode(f['data'])))
            sheet = book.active
            cells = {}
            for row in sheet.iter_rows(values_only=True):
                if row and row[0] is not None:
                    cells.setdefault(str(row[0]), []).append(list(row[1:]))
            if view == 'headcount':
                for r in data['table']['rows']:
                    got = cells[r['name']][-1]
                    self.assertEqual(got[0], HIDDEN_WORD if r['h']['h'] else r['h']['v'])
                    self.assertEqual(got[1], HIDDEN_WORD if r['j']['h'] else r['j']['v'])
            blob = json.dumps([list(r) for r in sheet.iter_rows(values_only=True)], default=str)
            self.assertNotIn('Odoo', blob)

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
