# -*- coding: utf-8 -*-
"""UPDATES P4 — leave opening balances from a sheet (L1-L12, L14) and the
Attendance and timesheets tile.

A company of its own in Ho Chi Minh City, today frozen at 12 Nov 2026,
balances as at 1 Nov 2026:

    absence policy "P4 policy" (Vietnam, from 1 Jan 2026, carry cap 8)
        DEMO P4 Pol A/B/C — on it, full time confirmed
        DEMO P4 Pol D     — on it, full time NOT confirmed
    DEMO P4 Plain A/B/C/D — not on any policy

    leave types (all keep a balance):
        P4 Annual        policy annual, whole days
        P4 Annual extra  policy annual, half days
        P4 Plain days    whole days, Time Off officer approves allocations
        P4 Plain halves  half days, no approval
        P4 Plain hours   hours, no approval
        P4 Elsewhere     another company's type
        P4 Singapore     a type for Singapore

Everything is sent by a Time Off administrator through the screens' own
server calls (`review` → `apply`), and written by the real policy layer and
the real allocation flow.
"""
import base64
import csv
import io
import os
from datetime import date, datetime
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

try:
    import openpyxl
except ImportError:            # pragma: no cover
    openpyxl = None

NOW = datetime(2026, 11, 12, 3, 0, 0)        # 10:00 in Ho Chi Minh City
CUT = '2026-11-01'


def csv_b64(rows):
    out = io.StringIO()
    writer = csv.writer(out)
    for row in rows:
        writer.writerow(row)
    return base64.b64encode(out.getvalue().encode('utf-8')).decode()


def L(type_rec, part='avail'):
    return 'l:%s:%s' % (type_rec.id, part)


class P4Fixture(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        vn = cls.env.ref('base.vn')
        cls.company = cls.env['res.company'].create({'name': 'P4 Leave Co', 'country_id': vn.id})
        cls.company.partner_id.tz = 'Asia/Ho_Chi_Minh'
        cls.other_co = cls.env['res.company'].create({'name': 'P4 Elsewhere Co', 'country_id': vn.id})
        cls.env.user.company_ids = [(4, cls.company.id), (4, cls.other_co.id)]
        cls.env.user.company_id = cls.company
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=[cls.company.id]))
        cls._approvals()
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        base = [cls.env.ref('base.group_user').id, cls.env.ref('hr.group_hr_user').id]
        cls.admin_to = Users.create({
            'name': 'DEMO P4 Time Off Admin', 'login': 'p4_timeoff_admin',
            'group_ids': [(6, 0, base + [cls.env.ref('hr_holidays.group_hr_holidays_manager').id])],
            'company_ids': [(6, 0, [cls.company.id])], 'company_id': cls.company.id})
        cls.officer = Users.create({
            'name': 'DEMO P4 HR Officer', 'login': 'p4_hr_officer',
            'group_ids': [(6, 0, base)],
            'company_ids': [(6, 0, [cls.company.id])], 'company_id': cls.company.id})
        cls.calendar = cls.company.resource_calendar_id
        # ---- the absence policy (pb_timeoff), its two annual types
        Policy = cls.env['pb.leave.policy.edition'].with_company(cls.company)
        cls.policy = Policy.create({
            'name': 'P4 policy', 'code': 'P4_POLICY', 'company_id': cls.company.id,
            'country_id': vn.id, 'effective_from': '2026-01-01', 'carry_cap': 8,
            'source_reference': 'P4 test policy', 'workflow_mode': 'portal',
            'workflow_authority_ref': 'P4 test'})
        Rule = cls.env['pb.leave.policy.rule'].with_company(cls.company)
        Rule.create({'name': 'Annual', 'edition_id': cls.policy.id, 'category': 'annual',
                     'quantity': 20, 'counting': 'working', 'limit_period': 'year',
                     'pay_treatment': 'paid', 'paid_fraction': 1, 'pay_funding': 'employer'})
        Rule.create({'name': 'Wellness', 'edition_id': cls.policy.id, 'category': 'wellness',
                     'quantity': 10, 'counting': 'working', 'limit_period': 'year',
                     'pay_treatment': 'paid', 'paid_fraction': 1, 'pay_funding': 'employer'})
        cls.policy.action_publish()
        Type = cls.env['hr.leave.type'].with_company(cls.company)
        common = {'company_id': cls.company.id, 'requires_allocation': True,
                  'leave_validation_type': 'hr'}
        cls.annual = Type.create(dict(common, name='P4 Annual', request_unit='day',
                                      allocation_validation_type='no_validation',
                                      pb_policy_category='annual', pb_pay_treatment='paid',
                                      pb_pay_funding='employer'))
        cls.annual2 = Type.create(dict(common, name='P4 Annual extra', request_unit='half_day',
                                       allocation_validation_type='no_validation',
                                       pb_policy_category='annual', pb_pay_treatment='paid',
                                       pb_pay_funding='employer'))
        cls.days = Type.create(dict(common, name='P4 Plain days', request_unit='day',
                                    allocation_validation_type='hr'))
        cls.halves = Type.create(dict(common, name='P4 Plain halves', request_unit='half_day',
                                      allocation_validation_type='no_validation'))
        cls.hours = Type.create(dict(common, name='P4 Plain hours', request_unit='hour',
                                     allocation_validation_type='no_validation'))
        cls.elsewhere = cls.env['hr.leave.type'].with_company(cls.other_co).create(dict(
            common, company_id=cls.other_co.id, name='P4 Elsewhere', request_unit='day',
            allocation_validation_type='no_validation'))
        # A type for every company, but for Singapore (the stock leave types
        # look like this: no company, one country).
        cls.singapore = Type.create(dict(common, company_id=False, name='P4 Singapore',
                                         request_unit='day',
                                         allocation_validation_type='no_validation',
                                         country_id=cls.env.ref('base.sg').id))
        # ---- people
        Emp = cls.env['hr.employee'].with_company(cls.company)

        def person(name, code, policy=False, full_time=True):
            vals = {'name': name, 'barcode': code, 'company_id': cls.company.id,
                    'resource_calendar_id': cls.calendar.id,
                    'work_email': '%s@p4.example' % code.lower()}
            if policy:
                vals.update(pb_leave_policy_id=cls.policy.id,
                            pb_policy_full_time_confirmed=full_time)
            return Emp.create(vals)

        cls.pa = person('DEMO P4 Pol A', 'P4PA', True)
        cls.pb = person('DEMO P4 Pol B', 'P4PB', True)
        cls.pc = person('DEMO P4 Pol C', 'P4PC', True)
        cls.pd = person('DEMO P4 Pol D', 'P4PD', True, full_time=False)
        cls.na = person('DEMO P4 Plain A', 'P4NA')
        cls.nb = person('DEMO P4 Plain B', 'P4NB')
        cls.nc = person('DEMO P4 Plain C', 'P4NC')
        cls.nd = person('DEMO P4 Plain D', 'P4ND')

    @classmethod
    def _approvals(cls):
        try:
            cls.env['biz.approval.seed'].sudo().set_no_approval_needed(cls.company, 'records')
        except Exception:   # noqa: BLE001
            pass

    def setUp(self):
        super().setUp()
        patcher = patch.object(type(self.env['pb.records.apply']), '_records_now',
                               lambda _self: NOW)
        patcher.start()
        self.addCleanup(patcher.stop)

    # ------------------------------------------------------------ helpers
    def U(self, user=None):
        user = user or self.admin_to
        return self.env['pb.updates.desk'].with_user(user).with_context(
            allowed_company_ids=[self.company.id])

    def cols(self, used):
        return {'used': {str(k): v for k, v in used.items()}, 'identity': {'code': 1},
                'heads': {}}

    def review(self, rows, used, cutover=CUT, user=None):
        res = self.U(user).review(csv_b64(rows), 'p4.csv', self.cols(used), kind='leave',
                                  cutover=cutover)
        self.assertTrue(res.get('ok'), res.get('msg'))
        return res

    def cell(self, res, emp, fid):
        for row in res['rows']:
            if row['emp_id'] == emp.id:
                return row['cells'].get(fid)
        return None

    def send(self, rows, used, cutover=CUT, name='DEMO P4 balances', user=None, changes=None):
        rv = self.review(rows, used, cutover, user)
        res = self.U(user).apply(name=name, file_b64=csv_b64(rows), filename='p4.csv',
                                 columns=self.cols(used),
                                 changes=rv['changes'] if changes is None else changes,
                                 stats={'rows': len(rows) - 1}, kind='leave', cutover=cutover)
        self.assertTrue(res.get('ok'), res.get('msg'))
        return rv, res

    def lines(self, res):
        return self.env['pb.updates.leave.line'].search([('batch_id', '=', res['batch_id'])])

    def balance(self, emp, leave_type):
        board = self.env['pb.timeoff'].sudo().with_context(
            allowed_company_ids=[self.company.id])._balances(0)
        for row in board['rows']:
            if row['id'] == emp.id:
                return row['cells'][leave_type.id]['balance']
        return None

    def counts(self):
        env = self.env['hr.leave'].sudo()
        out = {
            'leaves': env.search_count([]),
            'leave_states': tuple(sorted((l.id, l.state) for l in env.search([]))),
            'accrual_plans': self.env['hr.leave.accrual.plan'].sudo().search_count([]),
            'carry_annual_postings': self.env['pb.leave.policy.posting'].sudo().search_count(
                [('kind', 'in', ('annual', 'carry'))]),
            'year_openings': self.env['pb.leave.policy.year.opening'].sudo().search_count([])
            if 'pb.leave.policy.year.opening' in self.env else 0,
            'accrual_allocations': self.env['hr.leave.allocation'].sudo().search_count(
                [('allocation_type', '=', 'accrual')]),
        }
        return out


@tagged('post_install', '-at_install', 'pb_updates_p4')
class TestUpdatesP4(P4Fixture):

    # ---------------------------------------------------------------- L1
    def test_L1_policy_layer_three_people_two_types(self):
        rows = [['Code', 'Annual', 'Annual carried', 'Annual taken', 'Extra'],
                ['P4PA', '12', '3', '6', '4.5'],
                ['P4PB', '10', '', '', '2'],
                ['P4PC', '8', '8', '1', '1.5']]
        used = {2: L(self.annual), 3: L(self.annual, 'carry'), 4: L(self.annual, 'taken'),
                5: L(self.annual2)}
        rv, res = self.send(rows, used)
        self.assertEqual(len(rv['changes']), 10, rv['changes'])
        self.assertFalse(res['pending'])
        self.assertEqual(res['written'], 6)
        self.assertEqual(res['permanent'], 6)
        Posting = self.env['pb.leave.policy.posting'].sudo()
        for emp, ttype, days, carried, taken in (
                (self.pa, self.annual, 12, 3, 6), (self.pb, self.annual, 10, 0, 0),
                (self.pc, self.annual, 8, 8, 1), (self.pa, self.annual2, 4.5, 0, 0),
                (self.pb, self.annual2, 2, 0, 0), (self.pc, self.annual2, 1.5, 0, 0)):
            posting = Posting.search([('employee_id', '=', emp.id), ('leave_type_id', '=', ttype.id),
                                      ('kind', '=', 'opening')])
            self.assertEqual(len(posting), 1, (emp.name, ttype.name))
            self.assertAlmostEqual(posting.days, days)
            self.assertAlmostEqual(posting.opening_carried_days, carried)
            self.assertAlmostEqual(posting.opening_taken_days, taken)
            self.assertEqual(posting.cutover_date, date(2026, 11, 1))
            self.assertIn('DEMO P4 balances', posting.review_reference)
            alloc = posting.allocation_id
            self.assertEqual(alloc.state, 'validate')
            self.assertEqual(alloc.date_from, date(2026, 11, 1))
            self.assertEqual(alloc.date_to, date(2026, 12, 31))
            line = self.lines(res).filtered(lambda r: r.employee_id == emp and r.leave_type_id == ttype)
            self.assertEqual((line.state, line.way, line.posting_ref, line.allocation_id),
                             ('set', 'policy', posting.id, alloc))
            self.assertEqual(alloc.pb_updates_leave_line_id, line)
            # The Time Off screen shows the days.
            self.assertAlmostEqual(self.balance(emp, ttype), days)

    def test_L1b_policy_rules_on_screen(self):
        rows = [['Code', 'Annual', 'Plain', 'Annual carried', 'Annual'],
                ['P4PD', '5', '', '', ''],
                ['P4PA', '', '4', '', ''],
                ['P4PB', '5', '', '9', ''],
                ['P4NA', '', '', '2', '']]
        used = {2: L(self.annual), 3: L(self.days), 4: L(self.annual, 'carry')}
        rv = self.review(rows, used)
        self.assertEqual(self.cell(rv, self.pd, L(self.annual))['status'], 'refused')
        self.assertIn('full-time', self.cell(rv, self.pd, L(self.annual))['why'])
        why = self.cell(rv, self.pa, L(self.days))['why']
        self.assertIn('only its annual leave', why)
        self.assertIn('at most 8 days', self.cell(rv, self.pb, L(self.annual, 'carry'))['why'])
        self.assertEqual(self.cell(rv, self.na, L(self.annual, 'carry'))['status'], 'off_scheme')
        # Before the policy starts: refused with its first day.
        rv2 = self.review([['Code', 'Annual'], ['P4PA', '5']], {2: L(self.annual)},
                          cutover='2025-12-01')
        self.assertIn('does not cover', self.cell(rv2, self.pa, L(self.annual))['why'])

    # ---------------------------------------------------------------- L2
    def test_L2_no_policy_one_validated_allocation(self):
        rows = [['Code', 'Days', 'Halves'], ['P4NA', '12', '3.5'], ['P4NB', '7', '']]
        _rv, res = self.send(rows, {2: L(self.days), 3: L(self.halves)})
        self.assertEqual(res['written'], 3)
        self.assertEqual(res['undoable'], 3)
        Alloc = self.env['hr.leave.allocation'].sudo()
        for emp, ttype, days in ((self.na, self.days, 12), (self.na, self.halves, 3.5),
                                 (self.nb, self.days, 7)):
            alloc = Alloc.search([('employee_id', '=', emp.id), ('holiday_status_id', '=', ttype.id)])
            self.assertEqual(len(alloc), 1)
            self.assertEqual(alloc.state, 'validate')
            self.assertAlmostEqual(alloc.number_of_days, days)
            self.assertEqual(alloc.date_from, date(2026, 11, 1))
            self.assertFalse(alloc.date_to)
            self.assertTrue(alloc.pb_updates_leave_line_id, 'recognisable as an opening balance')
            self.assertIn('Opening balance as at', alloc.notes or '')
            self.assertEqual(alloc.pb_updates_leave_line_id.way, 'allocation')
            self.assertAlmostEqual(self.balance(emp, ttype), days)
        self.assertFalse(self.env['pb.leave.policy.posting'].sudo().search(
            [('employee_id', 'in', (self.na | self.nb).ids)]))

    # ---------------------------------------------------------------- L3 / L4
    def test_L3_never_a_second_opening_balance(self):
        self.send([['Code', 'Days'], ['P4NA', '12']], {2: L(self.days)})
        self.send([['Code', 'Annual'], ['P4PA', '12']], {2: L(self.annual)})
        Alloc = self.env['hr.leave.allocation'].sudo()
        Alloc.with_context(allowed_company_ids=[self.company.id]).create({
            'employee_id': self.nc.id, 'holiday_status_id': self.days.id,
            'allocation_type': 'regular', 'number_of_days': 5, 'date_from': '2026-01-01'
        }).action_approve()
        before = Alloc.search_count([])
        rv = self.review([['Code', 'Days', 'Annual'], ['P4NA', '10', ''], ['P4NC', '4', ''],
                          ['P4PA', '', '9']], {2: L(self.days), 3: L(self.annual)})
        self.assertIn('already has an opening balance of 12 days for P4 Plain days. Undo that '
                      'update first.', self.cell(rv, self.na, L(self.days))['why'])
        self.assertIn('already has P4 Plain days days from', self.cell(rv, self.nc, L(self.days))['why'])
        self.assertIn('an opening balance cannot be added on top', self.cell(rv, self.nc, L(self.days))['why'])
        self.assertIn('cannot be replaced', self.cell(rv, self.pa, L(self.annual))['why'])
        self.assertEqual(rv['changes'], [])
        # Sent past the screen straight to apply: refused by the server too.
        res = self.U().apply(name='DEMO P4 again', file_b64=csv_b64([['Code', 'Days'], ['P4NA', '10']]),
                             filename='p4.csv', columns=self.cols({2: L(self.days)}),
                             changes=[{'emp_id': self.na.id, 'field_id': L(self.days), 'value': 10},
                                      {'emp_id': self.nc.id, 'field_id': L(self.days), 'value': 4}],
                             kind='leave', cutover=CUT)
        self.assertTrue(res.get('nothing'))
        self.assertEqual(len(res['refused']), 2)
        self.assertEqual(Alloc.search_count([]), before, 'nothing added')

    def test_L4_same_value_is_same_not_sent(self):
        self.send([['Code', 'Days'], ['P4NA', '12']], {2: L(self.days)})
        rv = self.review([['Code', 'Days'], ['P4NA', '12']], {2: L(self.days)})
        cell = self.cell(rv, self.na, L(self.days))
        self.assertEqual(cell['status'], 'same')
        self.assertEqual(rv['changes'], [])

    # ---------------------------------------------------------------- L5
    def test_L5_units_and_limits(self):
        rows = [['Code', 'Days', 'Halves', 'Hours'],
                ['P4NA', '12.5', '12.5', '7.5'],
                ['P4NB', '-2', '12.25', '2920'],
                ['P4NC', '366', '0', '2921'],
                ['P4ND', 'abc', '365', '7.125']]
        rv = self.review(rows, {2: L(self.days), 3: L(self.halves), 4: L(self.hours)})
        st = lambda emp, t: self.cell(rv, emp, L(t))
        self.assertIn('whole number of days', st(self.na, self.days)['why'])
        self.assertEqual(st(self.na, self.halves)['status'], 'ok')
        self.assertEqual(st(self.na, self.hours)['status'], 'ok')
        self.assertIn('cannot be negative', st(self.nb, self.days)['why'])
        self.assertIn('whole or half number', st(self.nb, self.halves)['why'])
        self.assertEqual(st(self.nb, self.hours)['status'], 'ok', '365 days of 8 hours')
        self.assertIn('more than a year', st(self.nc, self.days)['why'])
        self.assertIn('0 sets nothing', st(self.nc, self.halves)['why'])
        self.assertIn('more than a year', st(self.nc, self.hours)['why'])
        self.assertIn('is not a number of days', st(self.nd, self.days)['why'])
        self.assertEqual(st(self.nd, self.halves)['status'], 'ok')
        self.assertIn('two decimals', st(self.nd, self.hours)['why'])
        _rv, res = self.send([['Code', 'Hours'], ['P4NA', '7.5']], {2: L(self.hours)})
        alloc = self.lines(res).allocation_id
        per_day = self.na._get_hours_per_day(date(2026, 11, 1))
        self.assertAlmostEqual(alloc.number_of_days, 7.5 / per_day, places=4)
        self.assertAlmostEqual(alloc.number_of_hours_display, 7.5, places=2)

    # ---------------------------------------------------------------- L6
    def test_L6_type_not_offered(self):
        rv = self.review([['Code', 'Elsewhere', 'Singapore', 'Days'], ['P4NA', '5', '5', '']],
                         {2: L(self.elsewhere), 3: L(self.singapore), 4: L(self.days)})
        # Another company's leave type, and one for a country nobody here
        # works in, are not even places a column can go.
        self.assertNotIn(L(self.elsewhere), [c['field_id'] for c in rv['columns']])
        self.assertNotIn(L(self.singapore), [c['field_id'] for c in rv['columns']])
        self.assertEqual(rv['changes'], [])
        # Sent past the screen: refused by the server, nothing written.
        res = self.U().apply(name='DEMO P4 elsewhere', file_b64=csv_b64([['Code'], ['P4NA']]),
                             filename='p4.csv', columns=self.cols({}),
                             changes=[{'emp_id': self.na.id, 'field_id': L(self.elsewhere), 'value': 5},
                                      {'emp_id': self.na.id, 'field_id': L(self.singapore), 'value': 5}],
                             kind='leave', cutover=CUT)
        self.assertTrue(res.get('nothing'))
        self.assertEqual(len(res['refused']), 2)
        whys = res['refused'][0]['why'] + res['refused'][1]['why']
        self.assertIn('not offered in P4 Leave Co', whys)
        self.assertIn('another country', whys)

    # ---------------------------------------------------------------- L9
    def test_L9_undo(self):
        _rv, res = self.send([['Code', 'Days', 'Halves'], ['P4NA', '12', '3'], ['P4NB', '7', '']],
                             {2: L(self.days), 3: L(self.halves)})
        _rv2, pol = self.send([['Code', 'Annual'], ['P4PA', '12']], {2: L(self.annual)},
                              name='DEMO P4 policy balances')
        lines = self.lines(res)
        drawn = lines.filtered(lambda r: r.employee_id == self.nb)
        # DEMO P4 Plain B asks for a day against the balance.
        leave = self.env['hr.leave'].sudo().with_context(leave_fast_create=True).create({
            'employee_id': self.nb.id, 'holiday_status_id': self.days.id,
            'request_date_from': '2026-11-16', 'request_date_to': '2026-11-16',
            'name': 'DEMO P4 day off'})
        self.assertIn(leave.state, ('confirm', 'validate1', 'validate'))
        before = self.counts()
        answer = self.U().undo(batch_id=res['batch_id'])
        self.assertTrue(answer['ok'], answer)
        self.assertEqual(answer['restored'], 2)
        self.assertEqual(answer['skipped_changed_since'], 1)
        self.assertIn('DEMO P4 Plain B has already taken or asked for 1 day', answer['msg'])
        for line in lines - drawn:
            self.assertEqual(line.state, 'undone')
            self.assertEqual(line.allocation_id.state, 'refuse')
        self.assertEqual(drawn.state, 'set')
        self.assertEqual(drawn.allocation_id.state, 'validate')
        self.assertAlmostEqual(self.balance(self.na, self.days), 0)
        self.assertEqual(self.counts(), before, 'L10: leave and policy rows untouched by undo')
        # A policy-layer balance: undo is not offered and says why.
        row = [b for b in self.U().get_history(10)['batches'] if b['id'] == pol['batch_id']][0]
        self.assertFalse(row['can_undo'])
        self.assertEqual(row['permanent'], 1)
        answer = self.U().undo(batch_id=pol['batch_id'])
        self.assertFalse(answer['ok'])
        self.assertIn('permanent', answer['msg'])
        self.assertEqual(self.lines(pol).state, 'set')
        # After an undo the same balance can be set again (a fresh one).
        rv = self.review([['Code', 'Days'], ['P4NA', '10']], {2: L(self.days)})
        self.assertEqual(self.cell(rv, self.na, L(self.days))['status'], 'ok')
        # Records screen History: its Undo takes back only what nothing drew on.
        res2 = self.env['pb.records.desk'].with_user(self.admin_to).with_context(
            allowed_company_ids=[self.company.id]).undo_apply(res['apply_id'])
        self.assertFalse(res2['ok'])

    # ---------------------------------------------------------------- L10
    def test_L10_leave_rows_untouched(self):
        unpaid = self.env['hr.leave.type'].with_company(self.company).create({
            'name': 'P4 Unpaid', 'company_id': self.company.id, 'requires_allocation': False,
            'leave_validation_type': 'hr'})
        self.env['hr.leave'].sudo().with_context(leave_fast_create=True).create({
            'employee_id': self.nd.id, 'holiday_status_id': unpaid.id,
            'request_date_from': '2026-11-17', 'request_date_to': '2026-11-17',
            'name': 'DEMO P4 requested'})
        before = self.counts()
        _rv, res = self.send([['Code', 'Days', 'Annual', 'Annual carried'],
                              ['P4NA', '12', '', ''], ['P4PB', '', '9', '2']],
                             {2: L(self.days), 3: L(self.annual), 4: L(self.annual, 'carry')})
        self.assertEqual(res['written'], 2)
        self.assertEqual(self.counts(), before)
        self.U().undo(batch_id=res['batch_id'])
        self.assertEqual(self.counts(), before)

    # ---------------------------------------------------------------- L11
    def test_L11_drafts_history_readme_layouts(self):
        U = self.U()
        b64 = csv_b64([['Code', 'Days'], ['P4NA', '12']])
        saved = U.save_draft(kind='leave', month=CUT, filename='p4.csv', file_b64=b64,
                             columns=self.cols({2: L(self.days)}), step='review')
        self.assertTrue(saved['ok'])
        drafts = U.list_drafts()['drafts']
        mine = [d for d in drafts if d['id'] == saved['draft_id']][0]
        self.assertEqual((mine['kind'], mine['cutover']), ('leave', CUT))
        opened = U.open_draft(saved['draft_id'])
        self.assertEqual((opened['kind'], opened['cutover']), ('leave', CUT))
        self.assertNotIn(saved['draft_id'], [b['id'] for b in U.get_history(50)['batches']])
        rv = self.review([['Code', 'Days'], ['P4NA', '12']], {2: L(self.days)})
        res = U.apply(name='DEMO P4 from a draft', file_b64=b64, filename='p4.csv',
                      columns={'used': {'2': L(self.days)}, 'identity': {'code': 1},
                               'heads': {'1': 'Code', '2': 'Days'}},
                      changes=rv['changes'], kind='leave', cutover=CUT,
                      draft_id=saved['draft_id'])
        self.assertEqual(res['batch_id'], saved['draft_id'], 'the draft becomes the update')
        hist = [b for b in U.get_history(50)['batches'] if b['id'] == res['batch_id']][0]
        self.assertEqual((hist['kind'], hist['state'], hist['set_values'], hist['cutover']),
                         ('leave', 'applied', 1, CUT))
        self.assertTrue(hist['can_undo'])
        # Remembered layout: its own kind, never offered to a lasting sheet.
        layout = self.env['pb.updates.layout'].search([('company_id', '=', self.company.id),
                                                       ('kind', '=', 'leave')])
        self.assertEqual(len(layout), 1)
        self.assertTrue(layout.fingerprint.startswith('leave:'))
        again = U.read_columns(b64, 'p4.csv', kind='leave', cutover=CUT)
        self.assertTrue(again['layout_known'])
        self.assertEqual(again['columns'][1]['target'], L(self.days))
        lasting = U.read_columns(b64, 'p4.csv')
        self.assertFalse(lasting.get('layout_known'))
        self.assertNotEqual(lasting['columns'][1].get('how'), 'memory')
        # Discard a draft.
        saved2 = U.save_draft(kind='leave', month=CUT, filename='p4b.csv', file_b64=b64)
        self.assertTrue(U.discard_draft(saved2['draft_id'])['ok'])

    def test_L11b_sheet_round_trip_and_read_me(self):
        self.send([['Code', 'Days'], ['P4NA', '12']], {2: L(self.days)})
        U = self.U()
        sheet = U.download_leave_sheet(CUT, [self.days.id, self.annual.id])
        self.assertTrue(sheet['ok'], sheet.get('msg'))
        self.assertNotIn('Odoo', sheet['filename'])
        wb = openpyxl.load_workbook(io.BytesIO(base64.b64decode(sheet['file_b64'])))
        heads = [c.value for c in wb['Records'][1]]
        self.assertIn('P4 Plain days · days available', heads)
        self.assertIn('P4 Annual · carried from last year', heads)
        self.assertIn('P4 Annual · already taken this year', heads)
        readme = ' '.join(str(c.value) for row in wb['Read me'].iter_rows() for c in row).lower()
        for words in ('blank cell changes nothing', 'only once per person and leave type',
                      'carried from last year', 'permanent'):
            self.assertIn(words, readme)
        col = heads.index('P4 Plain days · days available') + 1
        for r in range(2, wb['Records'].max_row + 1):
            if wb['Records'].cell(row=r, column=1).value == 'P4NA':
                self.assertEqual(wb['Records'].cell(row=r, column=col).value, 12)
        cols = U.read_columns(sheet['file_b64'], sheet['filename'], kind='leave', cutover=CUT)
        self.assertTrue(cols['from_sheet'])
        self.assertEqual(cols['sheet_date'], CUT)
        used, identity = {}, {}
        for c in cols['columns']:
            if c['target'].startswith('identity:'):
                identity[c['target'].split(':')[1]] = c['idx']
            elif c['target'] and c['target'] != 'ignore':
                used[str(c['idx'])] = c['target']
        rv = U.review(sheet['file_b64'], sheet['filename'],
                      {'used': used, 'identity': identity, 'heads': {}}, kind='leave', cutover=CUT)
        self.assertEqual(rv['changes'], [], 'a sheet sent straight back sets nothing')
        self.assertEqual(self.cell(rv, self.na, L(self.days))['status'], 'same')

    # ---------------------------------------------------------------- L12
    def test_L12_attendance_tile(self):
        officer = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'DEMO P4 Attendance Officer', 'login': 'p4_att_officer',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('hr.group_hr_user').id,
                                  self.env.ref('hr_attendance.group_hr_attendance_officer').id])],
            'company_ids': [(6, 0, [self.company.id])], 'company_id': self.company.id})
        door = self.U(officer)._attendance_door()
        self.assertTrue(door['available'])
        self.assertTrue(self.env.ref(door['action']))
        self.assertEqual(door['context'].get('pb_lens'), 'import')
        self.assertFalse(self.U(self.officer)._attendance_door()['available'], 'no right')
        with patch.object(type(self.env['pb.updates.desk']), '_attendance_installed',
                          lambda _self: False):
            self.assertFalse(self.U(officer)._attendance_door()['available'], 'absent')
        home = self.U(officer).get_home()
        self.assertTrue(home['attendance']['available'])
        self.assertTrue(home['leave']['available'])

    def test_L12b_only_time_off_admins_send(self):
        rv = self.review([['Code', 'Days'], ['P4NA', '12']], {2: L(self.days)}, user=self.officer)
        self.assertEqual(len(rv['changes']), 1, 'an officer can check a sheet')
        res = self.U(self.officer).apply(name='DEMO P4 no', file_b64=csv_b64([['Code', 'Days'], ['P4NA', '12']]),
                                         filename='p4.csv', columns=self.cols({2: L(self.days)}),
                                         changes=rv['changes'], kind='leave', cutover=CUT)
        self.assertFalse(res['ok'])
        self.assertIn('Time Off administrator', res['msg'])
        self.assertFalse(self.U(self.officer).get_home()['leave']['may_set'])

    def test_L12c_dates(self):
        U = self.U()
        for bad in ('2026-11-13', '2025-11-01', ''):
            res = U.review(csv_b64([['Code', 'Days'], ['P4NA', '12']]), 'p4.csv',
                           self.cols({2: L(self.days)}), kind='leave', cutover=bad)
            self.assertFalse(res['ok'], bad)

    # ---------------------------------------------------------------- L14
    def test_L14_no_vendor_name_in_new_strings(self):
        root = os.path.dirname(os.path.dirname(__file__))
        for rel in ('models/updates_leave.py', 'models/updates_leave_desk.py',
                    'static/src/js/updates_desk.js', 'static/src/js/updates_review.js',
                    'static/src/xml/updates_desk.xml'):
            with open(os.path.join(root, rel)) as handle:
                self.assertNotIn('Odoo', handle.read(), rel)


@tagged('post_install', '-at_install', 'pb_updates_p4')
class TestUpdatesP4Route(P4Fixture):
    """L7 and L8, with a real approval route (the records route)."""

    @classmethod
    def _approvals(cls):
        from datetime import date as d
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        groups = [cls.env.ref('base.group_user').id, cls.env.ref('hr.group_hr_user').id]
        cls.hr_lead = Users.create({'name': 'DEMO P4 HR Lead', 'login': 'p4_hr_lead',
                                    'group_ids': [(6, 0, groups)],
                                    'company_ids': [(6, 0, [cls.company.id])],
                                    'company_id': cls.company.id})
        role = cls.env['biz.approval.role'].sudo().search([('key', '=', 'hr_lead')], limit=1)
        if role:
            Resp = cls.env['biz.approval.responsibility'].sudo()
            held = Resp.search([('company_id', '=', cls.company.id), ('role_id', '=', role.id),
                                ('scope_key', '=', '')], limit=1)
            if held:
                held.write({'user_id': cls.hr_lead.id, 'active': True})
            else:
                Resp.create({'company_id': cls.company.id, 'role_id': role.id,
                             'scope_key': '', 'scope_label': cls.company.name,
                             'user_id': cls.hr_lead.id, 'date_from': d(2020, 1, 1)})
        cls.env['pb.records.apply']._approval_seed_default(cls.company)
        cls.Engine = cls.env['biz.approval.engine']

    def decide(self, apply_rec, action):
        for _guard in range(6):
            request = apply_rec.approval_request_id
            if not request or request.state not in ('pending', 'blocked'):
                return request
            step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
            seat = step.seat_ids.filtered(lambda s: s.status == 'open')[:1]
            self.Engine.with_user(seat.acting_user_id).decide(request.id, step.key, action, 'p4')
            apply_rec.invalidate_recordset()
            if action != 'approve':
                return request
        self.fail('never finished')

    def sent(self):
        alloc_before = self.env['hr.leave.allocation'].sudo().search_count([])
        _rv, res = self.send([['Code', 'Days', 'Annual'], ['P4NA', '12', ''], ['P4NB', '7', ''],
                              ['P4PA', '', '10']], {2: L(self.days), 3: L(self.annual)})
        self.assertTrue(res['pending'], res)
        self.assertIn('DEMO P4 HR Lead', res['with_whom'])
        apply_rec = self.env['pb.records.apply'].browse(res['apply_id'])
        lines = apply_rec.leave_line_ids
        self.assertEqual(set(lines.mapped('state')), {'waiting'})
        self.assertEqual(self.env['hr.leave.allocation'].sudo().search_count([]), alloc_before,
                         'nothing written before approval')
        return res, apply_rec, lines

    def test_L7_outlook_names_the_approver(self):
        out = self.U().leave_outlook([{'emp_id': self.na.id, 'field_id': L(self.days)}])
        self.assertEqual(out['outcome'], 'approval')
        self.assertIn('DEMO P4 HR Lead', out['line'])

    def test_L7_approve(self):
        res, apply_rec, lines = self.sent()
        detail = apply_rec._approval_detail(apply_rec.approval_request_id)
        self.assertEqual(detail['title'], 'Leave opening balances')
        self.assertIn('Leave opening balances as at', apply_rec._headline())
        self.decide(apply_rec, 'approve')
        self.assertTrue(apply_rec.applied)
        self.assertEqual(set(lines.mapped('state')), {'set'})
        self.assertEqual(lines.filtered(lambda r: r.employee_id == self.pa).way, 'policy')
        self.assertAlmostEqual(self.balance(self.na, self.days), 12)
        # Written as the proposer: the allocation's creator is the Time Off admin.
        alloc = lines.filtered(lambda r: r.employee_id == self.na).allocation_id
        self.assertEqual(alloc.create_uid, self.admin_to)

    def test_L7_send_back_turn_down_cancel(self):
        alloc_before = self.env['hr.leave.allocation'].sudo().search_count([])
        _res, apply_rec, lines = self.sent()
        self.decide(apply_rec, 'return')
        self.assertEqual(set(lines.mapped('state')), {'returned'})
        _res2, apply2, lines2 = self.sent()
        self.decide(apply2, 'reject')
        self.assertEqual(set(lines2.mapped('state')), {'rejected'})
        res3, apply3, lines3 = self.sent()
        hist = [b for b in self.U().get_history(10)['batches'] if b['id'] == res3['batch_id']][0]
        self.assertEqual(hist['state'], 'pending')
        self.assertTrue(hist['can_cancel'])
        answer = self.U().cancel(batch_id=res3['batch_id'])
        self.assertTrue(answer['ok'], answer)
        self.assertEqual(set(lines3.mapped('state')), {'cancelled'})
        self.assertEqual(apply3.approval_request_id.state, 'cancelled')
        self.assertEqual(self.env['hr.leave.allocation'].sudo().search_count([]), alloc_before)

    def test_L8_changed_between_review_and_approval(self):
        res, apply_rec, lines = self.sent()
        # Somebody gives DEMO P4 Plain B days on the Time Off screen meanwhile.
        self.env['hr.leave.allocation'].sudo().with_context(
            allowed_company_ids=[self.company.id]).create({
                'employee_id': self.nb.id, 'holiday_status_id': self.days.id,
                'allocation_type': 'regular', 'number_of_days': 3,
                'date_from': '2026-11-05'}).action_approve()
        self.decide(apply_rec, 'approve')
        late = lines.filtered(lambda r: r.employee_id == self.nb)
        self.assertEqual(late.state, 'refused')
        self.assertIn('cannot be added on top', late.reason)
        self.assertEqual(set((lines - late).mapped('state')), {'set'})
        hist = [b for b in self.U().get_history(10)['batches'] if b['id'] == res['batch_id']][0]
        self.assertEqual(hist['not_set'], 1)
        self.assertIn('could not be set', hist['state_label'])
        self.assertEqual(hist['not_set_lines'][0]['who'], 'DEMO P4 Plain B')
