# -*- coding: utf-8 -*-
"""DOCSTUDIO R — numbered test cases (handover §6). Cases 1, 15, 16, 17 are
run outside this file and reported in DOCSTUDIO_R_REPORT.md; 7 (grep), 14
and 18 live in test_static.py.

Fixtures are made by the test environment itself (the superuser), never by
`sudo` (rail R1 greps the whole module, tests included).
"""
import base64
import io
from datetime import date, datetime, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo.addons.pb_report_builder.models import report_builder as rb_module
from odoo.addons.pb_report_builder.models.report_builder import SpecError

try:
    from odoo.addons.pb_timeoff.models.hr_leave_approval import ENGINE_APPLY
except Exception:  # pragma: no cover — pb_timeoff absent
    ENGINE_APPLY = 'pb_leave_engine_apply'


def _xlsx_rows(res):
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(base64.b64decode(res['file_b64'])))
    ws = wb.active
    return ws, [list(r) for r in ws.iter_rows()]


@tagged('post_install', '-at_install', 'pb_report_builder')
class TestReportBuilder(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.Builder = env['pb.report.builder']
        cls.co1 = env.company
        cur1 = cls.co1.currency_id
        other = env.ref('base.EUR') if cur1 != env.ref('base.EUR') else env.ref('base.VND')
        other.active = True
        cls.cur1, cls.cur2 = cur1, other
        cls.co2 = env['res.company'].with_context(chart_template_load=True).create({
            'name': 'DEMO RB Second', 'currency_id': other.id})
        both = [(6, 0, [cls.co1.id, cls.co2.id])]
        pay = 'om_hr_payroll.group_hr_payroll_manager'
        base = ('base.group_user,hr.group_hr_user,hr_contract.group_hr_contract_manager,'
                'hr_holidays.group_hr_holidays_user,hr_attendance.group_hr_attendance_officer')
        extra = ''
        for xmlid in ('hr_recruitment.group_hr_recruitment_user', 'pb_assets.group_assets_manager',
                      'pb_hr_payroll_formula.group_formula_user'):
            if env.ref(xmlid, raise_if_not_found=False):
                extra += ',' + xmlid
        cls.admin_u = new_test_user(env, 'pbrb_admin', name='DEMO RB Admin',
                                    groups=base + extra + ',base.group_system,' + pay +
                                    ',hr_attendance.group_hr_attendance_manager',
                                    company_id=cls.co1.id, company_ids=both)
        cls.hr_u = new_test_user(env, 'pbrb_hr', name='DEMO RB HR', groups=base,
                                 company_id=cls.co1.id, company_ids=both)
        cls.mgr_u = new_test_user(env, 'pbrb_mgr', name='DEMO RB Manager', groups=base,
                                  company_id=cls.co1.id, company_ids=both)
        cls.plain_u = new_test_user(env, 'pbrb_plain', name='DEMO RB Plain',
                                    groups='base.group_user')

        Dept = env['hr.department']
        cls.dept_a = Dept.create({'name': 'DEMO RB Sales', 'company_id': cls.co1.id})
        cls.dept_b = Dept.create({'name': 'DEMO RB Ops', 'company_id': cls.co1.id})
        cls.dept_c = Dept.create({'name': 'DEMO RB Abroad', 'company_id': cls.co2.id})
        Emp = env['hr.employee']
        names = [('DEMO RB Ana', cls.dept_a), ('DEMO RB Ben', cls.dept_a),
                 ('DEMO RB Cai', cls.dept_a), ('DEMO RB Dao', cls.dept_b),
                 ('DEMO RB Eli', cls.dept_b), ('=HYPERLINK("x")', cls.dept_b)]
        cls.emps = Emp.browse()
        for name, dept in names:
            cls.emps |= Emp.create({'name': name, 'department_id': dept.id,
                                    'company_id': cls.co1.id, 'work_email': '%s@x.test' % len(cls.emps),
                                    'identification_id': 'ID-%s' % len(cls.emps)})
        cls.fen = Emp.create({'name': 'DEMO RB Fen', 'department_id': cls.dept_c.id,
                              'company_id': cls.co2.id})
        cls.ana, cls.ben, cls.cai, cls.dao, cls.eli, cls.formula = cls.emps
        cls.mine = [cls.dept_a.id, cls.dept_b.id, cls.dept_c.id]

        # contracts: two currencies (company money)
        Contract = env['hr.contract']
        today = fields.Date.today()
        cls.contracts = Contract.browse()
        for emp, wage in ((cls.ana, 1000.0), (cls.ben, 2000.0), (cls.fen, 3000.0)):
            c = Contract.create({'name': 'DEMO RB C %s' % emp.name, 'employee_id': emp.id,
                                 'company_id': emp.company_id.id,
                                 'wage': wage, 'date_start': today - timedelta(days=30),
                                 'date_end': today + timedelta(days=20)})
            c.state = 'open'
            cls.contracts |= c

        # time off this year
        cls.lt = env['hr.leave.type'].create({'name': 'DEMO RB Leave', 'requires_allocation': False})
        start = date(today.year, 1, 1)
        while start.weekday() != 1:     # a Tuesday: two working days in a row
            start += timedelta(days=1)
        cls.leaves = env['hr.leave'].browse()
        for i, (emp, days, state) in enumerate(((cls.ana, 2, 'validate'), (cls.ben, 1, 'validate'),
                                                (cls.dao, 1, 'validate'), (cls.eli, 1, 'refuse'),
                                                (cls.ana, 1, 'validate'))):
            first = start + timedelta(days=7 * i)
            leave = env['hr.leave'].with_context(
                leave_skip_state_check=True, mail_create_nolog=True).create({
                    'employee_id': emp.id, 'holiday_status_id': cls.lt.id,
                    'request_date_from': first, 'request_date_to': first + timedelta(days=days - 1),
                    'name': 'DEMO RB'})
            if leave.state != state:
                leave.with_context(**{ENGINE_APPLY: True}).write({'state': state})
            cls.leaves |= leave

        # attendance: Ana on two days (three punches), Ben on one day
        Att = env['hr.attendance']
        day1 = datetime.combine(today - timedelta(days=2), datetime.min.time())
        for emp, offsets in ((cls.ana, (8, 13)), (cls.ben, (9,))):
            for h in offsets:
                Att.create({'employee_id': emp.id, 'check_in': day1 + timedelta(hours=h),
                            'check_out': day1 + timedelta(hours=h + 3)})
        Att.create({'employee_id': cls.ana.id, 'check_in': day1 - timedelta(days=1, hours=-8),
                    'check_out': day1 - timedelta(days=1, hours=-12)})

        # assets held
        cls.has_assets = 'pb.asset' in env
        if cls.has_assets:
            cat = env['pb.asset.category'].create({'name': 'DEMO RB Laptops', 'code': 'RBL',
                                                   'kind': 'tangible'})
            for emp in (cls.ana, cls.ana, cls.dao):
                asset = env['pb.asset'].create({'name': 'DEMO RB laptop', 'category_id': cat.id,
                                                'country_id': env.ref('base.vn').id,
                                                'company_id': cls.co1.id})
                env['pb.asset.assignment'].create({'asset_id': asset.id, 'employee_id': emp.id})
                asset.state = 'assigned'

    # ------------------------------------------------------------ helpers
    def as_(self, who):
        return self.Builder.with_user(who).with_context(
            allowed_company_ids=who.company_ids.ids or [self.co1.id])

    def people_spec(self, **kw):
        spec = {'subject': 'people', 'columns': ['name', 'department'],
                'filters': [{'key': 'department', 'op': 'in', 'value': self.mine}],
                'sort': {'key': 'name', 'dir': 'asc'}}
        spec.update(kw)
        return spec

    def scope_divisions(self):
        Division = self.env['pb.division']
        div = Division.create({'name': 'DEMO RB North'})
        self.env['pb.division.link'].create({'division_id': div.id, 'department_id': self.dept_a.id,
                                             'date_from': '2020-01-01'})
        self.env['pb.group.visibility'].set_for(self.mgr_u.id, 'division', div.id)
        self.env.registry.clear_cache()
        return div

    # =============================================================== case 1
    def test_01_install_created_nothing(self):
        data = self.env['ir.model.data'].search([('module', '=', 'pb_report_builder')])
        kinds = set(data.mapped('model'))
        self.assertLessEqual(kinds, {'ir.model', 'ir.model.fields', 'ir.model.access', 'ir.rule',
                                     'ir.model.inherit',
                                     'ir.model.constraint', 'ir.model.fields.selection',
                                     'ir.module.module'}, kinds)
        self.assertFalse(self.env['ir.cron'].search([('ir_actions_server_id.model_id.model', 'in',
                                                      ('pb.report.definition',
                                                       'pb.report.builder'))]))

    # =============================================================== case 2
    def test_02_subjects_only_when_the_model_exists_and_is_readable(self):
        schema = self.as_(self.admin_u).schema()
        self.assertTrue(schema['allowed'])
        keys = {s['key']: s for s in schema['subjects']}
        expected = {'people': 'hr.employee', 'contracts': 'hr.contract', 'time_off': 'hr.leave',
                    'attendance': 'hr.attendance', 'open_roles': 'pb.hiring.requisition',
                    'applicants': 'hr.applicant', 'assets': 'pb.asset',
                    'training': 'pb.training.assignment', 'expenses': 'pb.expense.claim',
                    'goals': 'pb.goal.set'}
        for key, model in expected.items():
            self.assertEqual(key in keys, model in self.env, key)
        # a subject whose model is not on this database is never listed
        Builder = type(self.Builder)
        orig = Builder._pbrb_subjects

        def more(this):
            out = orig(this)
            out['ghost'] = dict(out['people'], key='ghost', model='pb.no.such.model')
            return out
        with patch.object(Builder, '_pbrb_subjects', more):
            subjects = self.as_(self.admin_u).schema()['subjects']
            self.assertNotIn('ghost', [s['key'] for s in subjects])
            with self.assertRaises(UserError):
                self.as_(self.admin_u).run({'subject': 'ghost', 'columns': ['name']})
        # `add()` drops absent models: the shipped registry has none
        self.assertTrue(all(s['model'] in self.env for s in self.Builder._pbrb_subjects().values()))
        # a subject the reader may not read is LOCKED with a reason, never opened
        if 'hr.applicant' in self.env:
            hr_keys = {s['key']: s for s in self.as_(self.hr_u).schema()['subjects']}
            if not self.env['hr.applicant'].with_user(self.hr_u).has_access('read'):
                self.assertTrue(hr_keys['applicants']['locked'])
                self.assertIn('Hiring', hr_keys['applicants']['why'])
                with self.assertRaises(AccessError):
                    self.as_(self.hr_u).run({'subject': 'applicants', 'columns': ['name']})
        # somebody outside the gate gets a sentence, not a screen
        plain = self.as_(self.plain_u).schema()
        self.assertFalse(plain['allowed'])
        self.assertTrue(plain['why'])
        self.assertFalse(self.as_(self.plain_u).can_open())
        with self.assertRaises(AccessError):
            self.as_(self.plain_u).run(self.people_spec())

    # =============================================================== case 3
    def test_03_people_rows_match_a_direct_read(self):
        own = None
        if 'pb.form.studio' in self.env:
            Studio = self.env['pb.form.studio']
            hosts = Studio._pbfs_hosts()
            host = next((k for k, h in hosts.items() if h['model'] == 'hr.employee'), None)
            if host:
                with patch.object(type(Studio), '_pbfs_check_busy', lambda self: None):
                    own = Studio.with_user(self.admin_u).create_field(host, {
                        'type': 'text', 'label': 'DEMO RB Badge', 'vis': 'all', 'list_ok': True})['name']
                for i, emp in enumerate(self.emps):
                    emp[own] = 'B-%s' % i
        cols = ['name', 'department', 'job', 'manager', 'company', 'work_email', 'gender']
        if own:
            cols.append('own.' + own)
        spec = self.people_spec(columns=cols)
        res = self.as_(self.hr_u).run(spec, 0, 200)
        self.assertEqual([c['key'] for c in res['columns']], cols)
        Emp = self.env['hr.employee'].with_user(self.hr_u).with_context(
            allowed_company_ids=self.hr_u.company_ids.ids)
        direct = Emp.search([('department_id', 'in', self.mine)], order='name asc, id')
        self.assertEqual(res['ids'], direct.ids)
        self.assertEqual(res['total'], len(direct))
        fnames = ['name', 'department_id', 'job_id', 'parent_id', 'company_id', 'work_email', 'sex']
        if own:
            fnames.append(own)
        gender = dict(self.env['hr.employee']._fields['sex']._description_selection(self.env))
        for row, rec in zip(res['rows'], direct.read(fnames)):
            expect = [rec['name'], rec['department_id'] and rec['department_id'][1] or '',
                      rec['job_id'] and rec['job_id'][1] or '',
                      rec['parent_id'] and rec['parent_id'][1] or '',
                      rec['company_id'] and rec['company_id'][1] or '', rec['work_email'] or '',
                      gender.get(rec['sex'], '') if rec['sex'] else '']
            if own:
                expect.append(rec[own] or '')
            self.assertEqual(row, expect)

    # =============================================================== case 4
    def test_04_time_off_grouped_by_department_totals(self):
        spec = {'subject': 'time_off', 'columns': ['employee', 'person.department', 'days'],
                'filters': [{'key': 'status', 'op': 'is', 'value': 'validate'},
                            {'key': 'person.department', 'op': 'in', 'value': self.mine}],
                'period': {'preset': 'this_year', 'date': 'from'},
                'group_by': ['person.department'], 'totals': {'days': 'sum'}}
        res = self.as_(self.admin_u).run(spec)
        year = fields.Date.today().year
        independent = self.env['hr.leave']._read_group(
            [('state', '=', 'validate'), ('employee_id.department_id', 'in', self.mine),
             ('request_date_from', '>=', date(year, 1, 1)),
             ('request_date_from', '<=', date(year, 12, 31))],
            ['employee_id.department_id'], ['number_of_days:sum'])
        want = {d.id: total for d, total in independent}
        got = {g['key'][0]: g for g in res['groups']}
        self.assertEqual(set(got), set(want))
        for dept_id, total in want.items():
            self.assertEqual(got[dept_id]['totals']['days'], self.Builder._num(total))
        self.assertEqual(res['totals']['days'], self.Builder._num(sum(want.values())))
        # opening one group gives exactly its rows
        first = res['groups'][0]
        rows = self.as_(self.admin_u).run(spec, 0, 50, first['key'])
        self.assertEqual(rows['total'], first['count'])
        self.assertEqual(len(rows['rows']), first['count'])

    # =============================================================== case 5
    def test_05_counts_from_other_areas_per_person(self):
        cols = ['name', 'count.leave_days', 'count.days_attended']
        if self.has_assets:
            cols.append('count.assets_held')
        spec = self.people_spec(columns=cols, period={'preset': 'this_year'})
        res = self.as_(self.admin_u).run(spec, 0, 200)
        by_id = dict(zip(res['ids'], res['rows']))
        year = fields.Date.today().year
        sample = [self.ana, self.ben, self.cai, self.dao, self.eli]
        for emp in sample:
            row = by_id[emp.id]
            leaves = self.env['hr.leave'].search([
                ('employee_id', '=', emp.id), ('state', '=', 'validate'),
                ('request_date_from', '>=', date(year, 1, 1)),
                ('request_date_from', '<=', date(year, 12, 31))])
            self.assertEqual(row[1], self.Builder._num(sum(leaves.mapped('number_of_days'))),
                             emp.name)
            days = {a.check_in.date() for a in self.env['hr.attendance'].search(
                [('employee_id', '=', emp.id)])
                if a.check_in.year == year}
            self.assertEqual(row[2], self.Builder._num(float(len(days))), emp.name)
            if self.has_assets:
                held = self.env['pb.asset'].search_count([('current_employee_id', '=', emp.id),
                                                          ('state', '=', 'assigned')])
                self.assertEqual(row[3], self.Builder._num(float(held)), emp.name)
        self.assertEqual(by_id[self.ana.id][1], self.Builder._num(3.0))

    # =============================================================== case 6
    def test_06_filters_each_operator_by_type(self):
        B = self.as_(self.admin_u)
        Emp = self.env['hr.employee'].with_user(self.admin_u).with_context(
            allowed_company_ids=self.admin_u.company_ids.ids)
        scope = [('department_id', 'in', self.mine)]
        cases = [
            ('name', 'contains', 'DEMO RB A', [('name', 'ilike', 'DEMO RB A')]),
            ('name', 'is', 'DEMO RB Ben', [('name', '=', 'DEMO RB Ben')]),
            ('name', 'is_not', 'DEMO RB Ben', [('name', '!=', 'DEMO RB Ben')]),
            ('department', 'in', [self.dept_a.id], [('department_id', 'in', [self.dept_a.id])]),
            ('department', 'is', self.dept_b.id, [('department_id', '=', self.dept_b.id)]),
            ('department', 'is_not', self.dept_b.id, [('department_id', '!=', self.dept_b.id)]),
            ('department', 'contains', 'Ops', [('department_id', 'ilike', 'Ops')]),
            ('job', 'empty', None, [('job_id', '=', False)]),
            ('work_email', 'not_empty', None, [('work_email', '!=', False)]),
            ('active', 'is', True, [('active', '=', True)]),
        ]
        for key, op, value, domain in cases:
            spec = self.people_spec(filters=[
                {'key': 'department', 'op': 'in', 'value': self.mine},
                {'key': key, 'op': op, 'value': value}])
            res = B.run(spec, 0, 200)
            want = Emp.search(scope + domain + [('active', '=', True)], order='name asc, id')
            self.assertEqual(res['ids'], want.ids, (key, op, value))
            self.assertEqual(len(res['filter_words']), 2)
        # selection: is one of / is
        self.ana.sex = 'female'
        self.ben.sex = 'male'
        for op, value, dom in (('in', ['female', 'male'], [('sex', 'in', ['female', 'male'])]),
                               ('is', 'female', [('sex', '=', 'female')])):
            res = B.run(self.people_spec(filters=[
                {'key': 'department', 'op': 'in', 'value': self.mine},
                {'key': 'gender', 'op': op, 'value': value}]), 0, 200)
            self.assertEqual(res['ids'], Emp.search(scope + dom, order='name asc, id').ids, op)
        # numbers and dates: between
        spec = {'subject': 'time_off', 'columns': ['employee', 'days', 'from'],
                'filters': [{'key': 'days', 'op': 'between', 'value': {'from': 1.5, 'to': 5}},
                            {'key': 'person.department', 'op': 'in', 'value': self.mine}]}
        res = B.run(spec, 0, 200)
        want = self.env['hr.leave'].search([('number_of_days', '>=', 1.5),
                                            ('number_of_days', '<=', 5),
                                            ('employee_id.department_id', 'in', self.mine)])
        self.assertEqual(sorted(res['ids']), sorted(want.ids))
        first = min(self.leaves.mapped('request_date_from'))
        spec['filters'][0] = {'key': 'from', 'op': 'between',
                              'value': {'from': str(first), 'to': str(first)}}
        res = B.run(spec, 0, 200)
        self.assertEqual(sorted(res['ids']), sorted(self.leaves.filtered(
            lambda l: l.request_date_from == first).ids))
        spec['filters'][0] = {'key': 'from', 'op': 'is', 'value': str(first)}
        self.assertEqual(B.run(spec, 0, 200)['total'], len(self.leaves.filtered(
            lambda l: l.request_date_from == first)))
        # datetime between (attendance)
        spec = {'subject': 'attendance', 'columns': ['employee', 'check_in'],
                'filters': [{'key': 'check_in', 'op': 'between',
                             'value': {'from': str(fields.Date.today() - timedelta(days=2)),
                                       'to': str(fields.Date.today() - timedelta(days=2))}},
                            {'key': 'person.department', 'op': 'in', 'value': self.mine}]}
        self.assertEqual(B.run(spec)['total'], 3)
        # a filter value of the wrong type is refused, not coerced
        for bad in (('department', 'in', ['3']), ('days', 'between', {'from': 'x'}),
                    ('active', 'is', 'yes'), ('name', 'contains', '')):
            key, op, value = bad
            subject = 'time_off' if key == 'days' else 'people'
            with self.assertRaises(SpecError, msg=bad):
                B.run({'subject': subject, 'columns': ['employee' if subject == 'time_off'
                                                       else 'name'],
                       'filters': [{'key': key, 'op': op, 'value': value}]})

    # =============================================================== case 7
    def test_07_fuzz_unknown_and_hostile_specs_are_refused(self):
        B = self.as_(self.admin_u)
        hostile = [
            {'subject': 'payslips', 'columns': ['name']},
            {'subject': 'hr.employee', 'columns': ['name']},
            {'subject': 'people', 'columns': ['password']},
            {'subject': 'people', 'columns': ['user_id.password']},
            {'subject': 'people', 'columns': ["name') OR 1=1 --"]},
            {'subject': 'people', 'columns': ['name'], 'domain': [('id', '>', 0)]},
            {'subject': 'people', 'columns': ['name'],
             'filters': [{'key': 'name', 'op': 'ilike', 'value': 'a'}]},
            {'subject': 'people', 'columns': ['name'],
             'filters': [{'key': 'department', 'op': 'in', 'value': "[('id','>',0)]"}]},
            {'subject': 'people', 'columns': ['name'],
             'filters': [{'key': 'department', 'op': 'is', 'value': True}]},
            {'subject': 'people', 'columns': ['name'], 'totals': {'name': 'max'}},
            {'subject': 'people', 'columns': ['name'], 'period': {'preset': 'forever'}},
            {'subject': 'people', 'columns': ['name'], 'sort': 'name desc; drop'},
            {'subject': 'people', 'columns': 'name'},
            "{'subject': 'people'}",
        ]
        for spec in hostile:
            # SpecError and AccessError are both UserErrors
            with self.assertRaises(UserError, msg=spec):
                B.run(spec)
            with self.assertRaises(UserError, msg=spec):
                B.export_xlsx(spec)
        with self.assertRaises(SpecError):
            B.run(self.people_spec(), 0, 50, ['not', 'a', 'group'])
        with self.assertRaises(SpecError):
            B.values_for('people', 'name', 'x')

    # =============================================================== case 8
    def test_08_one_shared_report_three_readers(self):
        div = self.scope_divisions()
        self.assertTrue(div)
        admin = self.as_(self.admin_u)
        spec = {'subject': 'contracts', 'columns': ['employee', 'person.department', 'pay', 'status'],
                'filters': [{'key': 'person.department', 'op': 'in', 'value': self.mine},
                            {'key': 'pay', 'op': 'between', 'value': {'from': 1}}],
                'sort': {'key': 'pay', 'dir': 'desc'}, 'totals': {'pay': 'sum'}}
        card = admin.save_report('DEMO RB pay', spec, True)
        # administrator: everything, pay included
        opened = admin.open_report(card['id'])
        self.assertTrue(opened['ok'])
        self.assertEqual(opened['notes'], [])
        res = admin.run(opened['spec'])
        self.assertIn('pay', [c['key'] for c in res['columns']])
        self.assertEqual(res['total'], 3)
        # HR without pay: the column, its filter, its sort and its total are gone
        hr = self.as_(self.hr_u)
        opened = hr.open_report(card['id'])
        self.assertTrue(opened['ok'])
        self.assertNotIn('pay', opened['spec']['columns'])
        self.assertNotIn('pay', [f['key'] for f in opened['spec']['filters']])
        self.assertIsNone(opened['spec']['sort'])
        self.assertEqual(opened['spec']['totals'], {})
        self.assertEqual(len(opened['notes']), 2, opened['notes'])
        res_hr = hr.run(opened['spec'])
        self.assertNotIn('pay', [c['key'] for c in res_hr['columns']])
        self.assertFalse(any('1,000' in c or '2,000' in c for row in res_hr['rows'] for c in row))
        # the raw stored spec, sent straight back, is cleaned the same way
        raw = hr.run(dict(spec))
        self.assertNotIn('pay', [c['key'] for c in raw['columns']])
        self.assertTrue(raw['notes'])
        # scoped manager: only their division's department
        mgr = self.as_(self.mgr_u)
        opened = mgr.open_report(card['id'])
        res_mgr = mgr.run(opened['spec'])
        depts = {row[1] for row in res_mgr['rows']}
        self.assertEqual(depts, {self.dept_a.name})
        # Excel matches the screen for each reader
        for builder, screen in ((admin, res), (hr, res_hr), (mgr, res_mgr)):
            out = builder.export_xlsx(screen['spec'], 'DEMO RB pay')
            self.assertTrue(out['ok'])
            ws, rows = _xlsx_rows(out)
            heads = [c.value for c in rows[0] if c.value]
            labels = [c['label'] for c in screen['columns']]
            self.assertEqual([h for h in heads if not h.endswith(' currency')], labels)
            self.assertEqual(out['rows'], screen['total'])
            text = ' '.join(str(c.value) for r in rows for c in r if c.value is not None)
            if builder is not admin:
                self.assertNotIn('3000', text.replace(',', '').replace('.0', ''))
        # a hiring subject in a shared report: the HR user without Hiring
        # access gets a sentence, never rows and never a traceback
        if 'hr.applicant' in self.env:
            app_card = admin.save_report('DEMO RB applicants',
                                         {'subject': 'applicants', 'columns': ['name', 'stage']},
                                         True)
            answer = hr.open_report(app_card['id'])
            if not self.env['hr.applicant'].with_user(self.hr_u).has_access('read'):
                self.assertFalse(answer['ok'])
                self.assertIn('Hiring', answer['msg'])
                locked = [r for r in hr.my_reports() if r['id'] == app_card['id']]
                self.assertTrue(locked and locked[0]['locked'])

    # =============================================================== case 9
    def test_09_access_studio_masked_field_vanishes(self):
        Access = type(self.env['pb.access']) if 'pb.access' in self.env else None
        spec = self.people_spec(columns=['name', 'id_number'])
        card = self.as_(self.admin_u).save_report('DEMO RB ids', spec, True)
        hr = self.as_(self.hr_u)
        self.assertIn('id_number', hr.run(spec)['spec']['columns'])
        if Access is None or not hasattr(Access, '_studio_field_allowed'):
            self.skipTest('Access Studio is not installed here')
        orig = Access._studio_field_allowed
        hr_uid = self.hr_u.id

        def masked(this, model, name, operation, record_ids=None):
            if this.env.uid == hr_uid and model == 'hr.employee' and name == 'identification_id':
                return False
            return orig(this, model, name, operation, record_ids)
        with patch.object(Access, '_studio_field_allowed', masked):
            fields_now = [f['key'] for s in hr.schema()['subjects'] if s['key'] == 'people'
                          for sec in s['sections'] for f in sec['fields']]
            self.assertNotIn('id_number', fields_now)
            opened = hr.open_report(card['id'])
            self.assertTrue(opened['ok'])
            self.assertNotIn('id_number', opened['spec']['columns'])
            self.assertTrue(opened['notes'])
            res = hr.run(opened['spec'])
            self.assertFalse(any('ID-' in c for row in res['rows'] for c in row))
            out = hr.export_xlsx(spec, 'x')
            ws, rows = _xlsx_rows(out)
            self.assertFalse(any('ID-' in str(c.value) for r in rows for c in r if c.value))
            # other subjects lose the same field through the person
            contract_fields = [f['key'] for s in hr.schema()['subjects'] if s['key'] == 'contracts'
                               for sec in s['sections'] for f in sec['fields']]
            self.assertNotIn('person.id_number', contract_fields)

    # ============================================================== case 10
    def test_10_money_totals_per_currency(self):
        spec = {'subject': 'contracts', 'columns': ['employee', 'company', 'pay'],
                'filters': [{'key': 'person.department', 'op': 'in', 'value': self.mine}],
                'totals': {'pay': 'sum'}}
        admin = self.as_(self.admin_u)
        res = admin.run(spec)
        total = res['totals']['pay']
        self.assertIn('·', total, total)
        self.assertNotIn('6,000', total)
        self.assertNotIn('6.000', total)
        # grouped by company: one currency per group
        res = admin.run(dict(spec, group_by=['company']))
        for g in res['groups']:
            self.assertNotIn('·', g['totals']['pay'])
        # the table for exporters keeps the money beside each figure
        table = admin._pbrb_table(dict(spec), 'x')
        labels = [c['label'] for c in table['columns']]
        self.assertIn('Contract pay currency', labels)
        currencies = {r[labels.index('Contract pay currency')] for r in table['rows']}
        self.assertEqual(currencies, {self.cur1.name, self.cur2.name})
        # Excel: the grand total row never adds the two
        out = admin.export_xlsx(spec, 'x')
        ws, rows = _xlsx_rows(out)
        values = [c.value for r in rows for c in r]
        self.assertNotIn(6000, values)
        self.assertNotIn(6000.0, values)

    # ============================================================== case 11
    def test_11_save_reopen_duplicate_share_delete_and_caps(self):
        hr = self.as_(self.hr_u)
        mgr = self.as_(self.mgr_u)
        card = hr.save_report('  DEMO   RB   mine  ', self.people_spec(), False)
        self.assertEqual(card['name'], 'DEMO RB mine')
        self.assertTrue(card['mine'])
        self.assertFalse(card['shared'])
        # private: the other person cannot see or open it
        self.assertNotIn(card['id'], [r['id'] for r in mgr.my_reports()])
        self.assertFalse(mgr.open_report(card['id'])['ok'])
        # share: now they can open it, not change or delete it
        hr.update_report(card['id'], {'shared': True})
        mine = [r for r in mgr.my_reports() if r['id'] == card['id']][0]
        self.assertFalse(mine['mine'])
        self.assertEqual(mine['owner'], self.hr_u.name)
        self.assertTrue(mgr.open_report(card['id'])['ok'])
        with self.assertRaises(AccessError):
            mgr.update_report(card['id'], {'name': 'stolen'})
        with self.assertRaises(AccessError):
            mgr.remove_report(card['id'])
        # duplicate a shared one: the copy is mine and private
        copy = mgr.duplicate_report(card['id'])
        self.assertTrue(copy['mine'])
        self.assertFalse(copy['shared'])
        self.assertIn('DEMO RB mine', copy['name'])
        # reopen keeps the layout
        opened = hr.open_report(card['id'])
        self.assertEqual(opened['spec']['columns'], ['name', 'department'])
        hr.update_report(card['id'], {'spec': self.people_spec(columns=['name', 'job'])})
        self.assertEqual(hr.open_report(card['id'])['spec']['columns'], ['name', 'job'])
        # names: required, at most 80 characters
        with self.assertRaises(UserError):
            hr.save_report('   ', self.people_spec())
        long = hr.save_report('x' * 200, self.people_spec())
        self.assertEqual(len(long['name']), 80)
        # delete
        self.assertTrue(hr.remove_report(card['id']))
        self.assertFalse(hr.open_report(card['id'])['ok'])
        # cap: 50 per person, said plainly
        Report = self.env['pb.report.definition']
        have = Report.search_count([('user_id', '=', self.hr_u.id)])
        Report.create([{'name': 'DEMO RB %s' % i, 'subject': 'people', 'user_id': self.hr_u.id,
                        'spec': {}} for i in range(50 - have)])
        with self.assertRaises(UserError) as caught:
            hr.save_report('one too many', self.people_spec())
        self.assertIn('50', str(caught.exception))

    # ============================================================== case 12
    def test_12_excel_cap_and_formula_text(self):
        admin = self.as_(self.admin_u)
        spec = self.people_spec(columns=['name', 'department'])
        out = admin.export_xlsx(spec, 'DEMO RB')
        ws, rows = _xlsx_rows(out)
        cell = next(c for r in rows for c in r if c.value == '=HYPERLINK("x")')
        self.assertEqual(cell.data_type, 's')
        self.assertTrue(cell.quotePrefix)
        self.assertFalse(out['truncated'])
        with patch.object(rb_module, 'EXPORT_CAP', 3):
            out = admin.export_xlsx(spec, 'DEMO RB')
        self.assertTrue(out['truncated'])
        self.assertEqual(out['rows'], 3)
        self.assertIn('first 3', out['note'])
        ws, rows = _xlsx_rows(out)
        self.assertIn(out['note'], [c.value for r in rows for c in r])
        self.assertTrue(out['filename'].endswith('.xlsx'))

    # ============================================================== case 13
    def test_13_c1_table_shape(self):
        admin = self.as_(self.admin_u)
        spec = {'subject': 'contracts',
                'columns': ['employee', 'date_start', 'pay', 'status', 'person.department'],
                'filters': [{'key': 'person.department', 'op': 'in', 'value': self.mine}]}
        card = admin.save_report('DEMO RB C1', spec, False)
        report = self.env['pb.report.definition'].with_user(self.admin_u).with_context(
            allowed_company_ids=self.admin_u.company_ids.ids).browse(card['id'])
        table = report._pbxl_table()
        self.assertEqual(set(table), {'title', 'columns', 'rows', 'truncated', 'note'})
        self.assertEqual(table['title'], 'DEMO RB C1')
        self.assertIsInstance(table['truncated'], bool)
        self.assertIsInstance(table['note'], str)
        allowed = {'text', 'number', 'money', 'date', 'datetime', 'bool'}
        for col in table['columns']:
            self.assertEqual(set(col), {'key', 'label', 'type'})
            self.assertIn(col['type'], allowed)
        types = [c['type'] for c in table['columns']]
        self.assertEqual(types, ['text', 'date', 'money', 'text', 'text', 'text'])
        for row in table['rows']:
            self.assertEqual(len(row), len(table['columns']))
            for value, ctype in zip(row, types):
                if value is None:
                    continue
                expect = {'text': str, 'date': date, 'money': float, 'number': (int, float),
                          'bool': bool}[ctype]
                self.assertIsInstance(value, expect)
        # another reader gets their own table (no pay for HR)
        report.shared = True
        hr_table = self.env['pb.report.definition'].with_user(self.hr_u).with_context(
            allowed_company_ids=self.hr_u.company_ids.ids).browse(card['id'])._pbxl_table()
        self.assertNotIn('pay', [c['key'] for c in hr_table['columns']])
        self.assertTrue(hr_table['note'])

    # ========================================================== extras
    def test_20_examples_follow_the_reader(self):
        admin = self.as_(self.admin_u).examples()
        self.assertGreaterEqual(len(admin), 8)
        for ex in admin:
            res = self.as_(self.admin_u).run(ex['spec'])
            self.assertTrue(res['ok'], ex['key'])
        if 'hr.applicant' in self.env and \
                not self.env['hr.applicant'].with_user(self.hr_u).has_access('read'):
            self.assertNotIn('applicants', [e['key'] for e in self.as_(self.hr_u).examples()])

    def test_21_sorting_on_a_field_one_link_away_pages_exactly(self):
        B = self.as_(self.admin_u)
        spec = {'subject': 'time_off', 'columns': ['employee', 'person.department'],
                'filters': [{'key': 'person.department', 'op': 'in', 'value': self.mine}],
                'sort': {'key': 'person.department', 'dir': 'desc'}}
        whole = B.run(spec, 0, 200)
        names = [r[1] for r in whole['rows']]
        self.assertEqual(names, sorted(names, reverse=True))
        page1 = B.run(spec, 0, 2)
        page2 = B.run(spec, 2, 2)
        self.assertEqual(page1['ids'] + page2['ids'], whole['ids'][:4])
        self.assertTrue(page1['has_more'])
