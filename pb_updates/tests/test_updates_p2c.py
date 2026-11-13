# -*- coding: utf-8 -*-
"""UPDATES P2c — start dates through the Updates door (C13, C14, C15, C19,
plus Coming up, Start now, Cancel and the Past-updates states).

A company of its own in Ho Chi Minh City (UTC+7), with a frozen clock
(`pb.records.apply._records_now`): today is 11 Nov 2026.

    team A → "P2C Monthly"  pay item X (no contract has a line for it: only
                            the Updates catalogue offers it — proves the door)
    team B → "P2C Daily"    no X (X is greyed and skipped for Bob)
"""
import base64
import csv
import io
from datetime import date, datetime
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, tagged

try:
    import openpyxl
except ImportError:            # pragma: no cover — a declared dependency
    openpyxl = None

JOB = 'f:hr.employee:job_title'
PHONE = 'f:hr.employee:work_phone'
WAGE = 'f:hr.contract:wage'
END = 'f:hr.contract:date_end'
MANAGER = 'f:hr.employee:parent_id'
X = 'c:P2CUX'
WHEN = 'when:start'
NOW = datetime(2026, 11, 11, 3, 0)
FUTURE = '2026-12-01'


def csv_b64(rows):
    out = io.StringIO()
    writer = csv.writer(out)
    for row in rows:
        writer.writerow(row)
    return base64.b64encode(out.getvalue().encode('utf-8')).decode()


@tagged('post_install', '-at_install', 'pb_updates', 'pb_updates_p2c')
class TestUpdatesP2c(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        vnd = cls.env.ref('base.VND')
        cls.company = cls.env['res.company'].create(
            {'name': 'P2C Updates Co', 'currency_id': vnd.id})
        cls.company.partner_id.tz = 'Asia/Ho_Chi_Minh'
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env = cls.env(context=dict(cls.env.context,
                                       allowed_company_ids=[cls.company.id]))
        for process in ('records', 'schememap'):
            try:
                cls.env['biz.approval.seed'].sudo().set_no_approval_needed(
                    cls.company, process)
            except Exception:   # noqa: BLE001 — a fixture must not die here
                pass
        cls.Upd = cls.env['pb.updates.desk']
        cls.Desk = cls.env['pb.records.desk']
        cls.Apply = cls.env['pb.records.apply']
        Department = cls.env['hr.department']
        cls.team_a = Department.create({'name': 'P2C Team A', 'company_id': cls.company.id})
        cls.team_b = Department.create({'name': 'P2C Team B', 'company_id': cls.company.id})
        Config = cls.env['hr.formula.config']
        cls.monthly = Config.create({'name': 'P2C Monthly', 'code': 'P2CUMONTHLY',
                                     'cycle_type': 'end_cycle', 'country_code': 'VN',
                                     'company_id': cls.company.id, 'state': 'active'})
        cls.daily = Config.create({'name': 'P2C Daily', 'code': 'P2CUDAILY',
                                   'cycle_type': 'end_cycle', 'country_code': 'VN',
                                   'company_id': cls.company.id, 'state': 'active'})
        cls.env['hr.formula.rule'].create({
            'config_id': cls.monthly.id, 'name': 'P2C Field allowance', 'code': 'P2CUX',
            'column_type': 'input', 'sequence': 1, 'default_value': 0.0,
            'is_contract_component': True})
        Assign = cls.env['hr.formula.scheme.assignment']
        Assign.create({'config_id': cls.monthly.id, 'department_id': cls.team_a.id,
                       'cycle_type': 'any'})
        Assign.create({'config_id': cls.daily.id, 'department_id': cls.team_b.id,
                       'cycle_type': 'any'})
        cls.calendar = cls.company.resource_calendar_id or cls.env[
            'resource.calendar'].create({'name': 'P2C Hours', 'company_id': cls.company.id})
        cls.kind = cls.env['hr.contract.type'].search([], limit=1) or cls.env[
            'hr.contract.type'].create({'name': 'P2C Kind'})
        cls.ann = cls._person('P2C Ann', 'P2CU01', cls.team_a)
        cls.bob = cls._person('P2C Bob', 'P2CU02', cls.team_b)
        cls.cat = cls._person('P2C Cat', 'P2CU03', cls.team_a)
        cls.contracts = {p.id: cls.env['hr.contract'].create({
            'name': 'P2C contract %s' % p.name, 'employee_id': p.id,
            'company_id': cls.company.id, 'wage': 1000.0, 'state': 'open',
            'date_start': '2026-01-01', 'date_end': '2027-12-31',
            'resource_calendar_id': cls.calendar.id, 'type_id': cls.kind.id})
            for p in (cls.ann, cls.bob, cls.cat)}

    @classmethod
    def _person(cls, name, code, team):
        employee = cls.env['hr.employee'].create({
            'name': name, 'barcode': code, 'company_id': cls.company.id,
            'job_title': 'Operator'})
        version = employee.current_version_id if 'current_version_id' in employee._fields else None
        if version and 'department_id' in version._fields:
            version.department_id = team.id
        else:
            employee.department_id = team.id
        return employee

    def setUp(self):
        super().setUp()
        self.clock = NOW
        patcher = patch.object(type(self.env['pb.records.apply']), '_records_now',
                               lambda _self: self.clock)
        patcher.start()
        self.addCleanup(patcher.stop)

    # ------------------------------------------------------------ helpers
    def cols(self, used, code=1, start=0):
        used = {str(k): v for k, v in used.items()}
        if start:
            used[str(start)] = WHEN
        return {'used': used, 'identity': {'code': code, 'name': 0, 'email': 0},
                'heads': {}}

    def review(self, rows, used, start=0):
        answer = self.Upd.review(csv_b64(rows), 'p2c.csv', self.cols(used, start=start))
        return answer

    def apply(self, rows, used, start=0, **kw):
        rev = self.review(rows, used, start=start)
        self.assertTrue(rev['ok'], rev.get('msg'))
        return rev, self.Upd.apply(kw.pop('name', 'P2C update'), csv_b64(rows), 'p2c.csv',
                                   self.cols(used, start=start), rev['changes'],
                                   {'rows': len(rows) - 1}, **kw)

    def state(self, person):
        person.invalidate_recordset()
        contract = self.contracts[person.id]
        contract.invalidate_recordset()
        line = contract.advantages_ids.filtered(lambda l: l.advantage_template_id.code == 'P2CUX')
        return {'job': person.job_title, 'wage': contract.wage,
                'end': contract.date_end, 'x': line.amount if line else None}

    def batch_row(self, batch_id):
        return next(b for b in self.Upd.get_history(50)['batches'] if b['id'] == batch_id)

    def run_job(self):
        return self.Apply._cron_start_scheduled()

    # ================================================================ C13
    def test_C13_pay_waits_personal_details_change_today(self):
        rows = [['Code', 'Job', 'Wage', 'Field allowance'],
                ['P2CU01', 'Lead', '1500', '300'], ['P2CU03', 'Chief', '1600', '400']]
        _rev, done = self.apply(rows, {2: JOB, 3: WAGE, 4: X},
                                start_date=FUTURE, hold_scope='pay')
        self.assertTrue(done['ok'], done.get('msg'))
        parts = {(p['date'], p['scheduled']): p for p in done['parts']}
        self.assertEqual(set(parts), {('', False), (FUTURE, True)})
        self.assertEqual(parts[('', False)]['written'], 2, "job titles now")
        self.assertEqual(parts[(FUTURE, True)]['values'], 4, "wage + pay item wait")
        self.assertEqual(self.state(self.ann)['job'], 'Lead')
        self.assertEqual(self.state(self.ann)['wage'], 1000.0)
        self.assertIsNone(self.state(self.ann)['x'])
        batch = self.env['pb.updates.batch'].browse(done['batch_id'])
        self.assertEqual(len(batch.apply_ids), 2, "one batch, two applies")
        row = self.batch_row(batch.id)
        self.assertEqual(row['state'], 'mixed')
        self.assertIn('Part applied, part scheduled for', row['state_label'])
        self.assertTrue(row['can_undo'] and row['can_cancel'] and row['can_start'])
        coming = self.Upd.get_coming_up()['items']
        self.assertEqual([(c['batch_id'], c['date'], c['values']) for c in coming],
                         [(batch.id, FUTURE, 4)])
        self.clock = datetime(2026, 12, 1, 3, 0)
        self.assertEqual(self.run_job(), {'started': 1})
        self.assertEqual(self.state(self.ann), {'job': 'Lead', 'wage': 1500.0,
                                                'end': date(2027, 12, 31), 'x': 300.0})
        self.assertEqual(self.batch_row(batch.id)['state'], 'applied')

    def test_C13b_everything_waits(self):
        rows = [['Code', 'Job', 'Wage'], ['P2CU01', 'Lead', '1500']]
        _rev, done = self.apply(rows, {2: JOB, 3: WAGE}, start_date=FUTURE, hold_scope='all')
        self.assertEqual([(p['date'], p['scheduled']) for p in done['parts']], [(FUTURE, True)])
        self.assertEqual(self.state(self.ann)['job'], 'Operator', "nothing changes before the day")
        rec = self.Apply.browse(done['apply_id'])
        self.assertEqual(rec.hold_scope, 'all')
        row = self.batch_row(done['batch_id'])
        self.assertEqual(row['state'], 'scheduled')
        self.assertFalse(row['can_undo'])
        undo = self.Upd.undo(done['batch_id'])
        self.assertFalse(undo['ok'])
        self.assertIn('Cancel the scheduled part', undo['msg'])

    def test_C13c_no_date_is_the_old_call(self):
        rows = [['Code', 'Job'], ['P2CU01', 'Lead']]
        _rev, done = self.apply(rows, {2: JOB})
        self.assertNotIn('parts', done, "exactly the call Updates always made")
        self.assertEqual(done['written'], 1)
        self.assertFalse(self.Apply.browse(done['apply_id']).start_date)

    # ================================================================ C14
    def test_C14_per_row_dates(self):
        rows = [['Code', 'Starts on', 'Wage'],
                ['P2CU01', '2026-12-01', '1500'],
                ['P2CU02', '2027-01-01', '1600'],
                ['P2CU03', '2026-10-01', '1700']]
        rev, done = self.apply(rows, {3: WAGE}, start=2)
        starts = {r['emp_id']: r['start'] for r in rev['rows']}
        self.assertEqual(starts[self.ann.id], {'date': '2026-12-01', 'kind': 'future',
                                               'error': '', 'raw': '2026-12-01'})
        self.assertEqual(starts[self.cat.id]['kind'], 'past')
        self.assertTrue(rev['dated'])
        self.assertNotIn('Starts on', rev['summary']['columns_ignored'])
        self.assertEqual(sorted(c.get('start') for c in rev['changes']),
                         ['2026-10-01', '2026-12-01', '2027-01-01'])
        batch = self.env['pb.updates.batch'].browse(done['batch_id'])
        self.assertEqual(len(batch.apply_ids), 3, "three dates, three applies, one batch")
        by_date = {a.start_date: a for a in batch.apply_ids}
        self.assertEqual(by_date[date(2026, 10, 1)].state, 'applied')
        self.assertEqual(by_date[date(2026, 12, 1)].state, 'scheduled')
        self.assertEqual(by_date[date(2027, 1, 1)].state, 'scheduled')
        self.assertEqual(self.state(self.cat)['wage'], 1700.0, "the past one is written now")
        self.assertEqual(set(by_date[date(2026, 10, 1)].change_ids.mapped('effective_date')),
                         {date(2026, 10, 1)})

    def test_C14b_seven_dates_are_refused(self):
        people = [self._person('P2C Many %s' % i, 'P2CM%02d' % i, self.team_a) for i in range(7)]
        rows = [['Code', 'Starts on', 'Job']] + [
            [p.barcode, '2026-12-%02d' % (i + 1), 'Job %s' % i] for i, p in enumerate(people)]
        rev = self.review(rows, {3: JOB}, start=2)
        self.assertFalse(rev['ok'])
        self.assertEqual(rev['msg'], "This file has 7 different start dates. Split it "
                                     "into files of at most 6.")

    # ================================================================ C15
    def test_C15_unreadable_and_far_dates(self):
        rows = [['Code', 'Starts on', 'Job', 'Wage'],
                ['P2CU01', 'next week', 'Lead', '1500'],
                ['P2CU02', '2029-01-01', 'Chief', '1600'],
                ['P2CU03', '1 Dec 2026', 'Boss', '1700']]
        rev = self.review(rows, {3: JOB, 4: WAGE}, start=2)
        self.assertTrue(rev['ok'], rev.get('msg'))
        cells = {r['emp_id']: r['cells'] for r in rev['rows']}
        self.assertEqual(cells[self.ann.id][WAGE]['status'], 'refused')
        self.assertTrue(cells[self.ann.id][WAGE]['date_refused'])
        self.assertEqual(cells[self.ann.id][WAGE]['why'],
                         "'next week' is not a date. Use a date like 1 Dec 2026.")
        self.assertEqual(cells[self.ann.id][JOB]['status'], 'ok', "personal details are not dated")
        self.assertIn('up to a year back or a year ahead', cells[self.bob.id][WAGE]['why'])
        self.assertEqual(cells[self.cat.id][WAGE]['status'], 'ok', "'1 Dec 2026' reads")
        starts = {r['emp_id']: r['start'] for r in rev['rows']}
        self.assertEqual(starts[self.cat.id]['date'], '2026-12-01')
        sent = {(c['emp_id'], c['field_id']) for c in rev['changes']}
        self.assertNotIn((self.ann.id, WAGE), sent)
        self.assertNotIn((self.bob.id, WAGE), sent)
        far = self.Upd.apply('Far', '', '', self.cols({3: JOB}),
                             [{'emp_id': self.ann.id, 'field_id': JOB, 'value': 'X'}],
                             {'rows': 1}, start_date='2028-02-01')
        self.assertFalse(far['ok'])
        self.assertIn('up to a year back or a year ahead', far['msg'])
        self.assertEqual(self.state(self.ann)['job'], 'Operator')

    def test_C15b_date_shapes(self):
        parse = self.Upd._parse_start
        self.assertEqual(parse('2026-12-01')[0], date(2026, 12, 1))
        self.assertEqual(parse('2026-12-01 00:00:00')[0], date(2026, 12, 1))
        self.assertEqual(parse('1 Dec 2026')[0], date(2026, 12, 1))
        self.assertEqual(parse('')[0], None)
        self.assertEqual(parse(None), (None, ''))
        self.assertTrue(parse(45992)[1], "a bare number is not a date")
        # en_US reads month first; vi_VN reads day first.
        self.assertEqual(parse('12/01/2026')[0], date(2026, 12, 1))
        vi = self.env['res.lang']._activate_lang('vi_VN') if hasattr(
            self.env['res.lang'], '_activate_lang') else None
        if vi or self.env['res.lang']._lang_get('vi_VN'):
            self.assertEqual(self.Upd.with_context(lang='vi_VN')._parse_start('01/12/2026')[0],
                             date(2026, 12, 1))

    def test_C15c_a_real_spreadsheet_date(self):
        if openpyxl is None:
            self.skipTest('openpyxl missing')
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(['Code', 'Effective date', 'Wage'])
        ws.append(['P2CU01', datetime(2026, 12, 1), 1500])
        buf = io.BytesIO()
        wb.save(buf)
        b64 = base64.b64encode(buf.getvalue()).decode()
        cols = self.Upd.read_columns(b64, 'p2c.xlsx')
        self.assertTrue(cols['ok'], cols.get('msg'))
        guessed = {c['head']: (c['target'], c['how']) for c in cols['columns']}
        self.assertEqual(guessed['Effective date'], (WHEN, 'guess'))
        rev = self.Upd.review(b64, 'p2c.xlsx', self.cols({3: WAGE}, start=2))
        self.assertEqual(rev['rows'][0]['start']['date'], '2026-12-01')

    def test_C15d_the_start_column_is_remembered(self):
        rows = [['Code', 'Valid from', 'Job'], ['P2CU01', '2026-10-01', 'Lead']]
        self.apply(rows, {3: JOB}, start=2)
        again = self.Upd.read_columns(csv_b64(rows), 'p2c.csv')
        targets = {c['head']: (c['target'], c['how']) for c in again['columns']}
        self.assertEqual(targets['Valid from'], (WHEN, 'memory'))

    # ================================================================ C19
    def test_C19_off_scheme_and_clear_on_a_scheduled_change(self):
        rows = [['Code', 'Field allowance', 'Contract end'],
                ['P2CU01', '700', 'CLEAR'], ['P2CU02', '500', '']]
        rev, done = self.apply(rows, {2: X, 3: END}, start_date=FUTURE)
        cells = {r['emp_id']: r['cells'] for r in rev['rows']}
        self.assertEqual(cells[self.bob.id][X]['status'], 'off_scheme')
        self.assertEqual(cells[self.ann.id][END]['status'], 'ok')
        self.assertTrue(cells[self.ann.id][END]['cleared'])
        self.assertEqual([(p['date'], p['scheduled']) for p in done['parts']], [(FUTURE, True)])
        plain = {c['id'] for g in self.Desk.get_fields(0)['groups'] for c in g['fields']}
        self.assertNotIn(X, plain, "only the Updates catalogue has it: the door must reopen")
        self.clock = datetime(2026, 12, 1, 3, 0)
        self.assertEqual(self.run_job(), {'started': 1})
        self.assertEqual(self.state(self.ann)['x'], 700.0)
        self.assertFalse(self.state(self.ann)['end'], "CLEAR applied as proposed")
        self.assertIsNone(self.state(self.bob)['x'], "the off-scheme value stays dropped")
        undo = self.Desk.undo_apply(done['apply_id'])
        self.assertEqual(undo['restored'], 2)
        self.assertEqual(self.state(self.ann)['end'], date(2027, 12, 31))
        self.assertIsNone(self.state(self.ann)['x'])

    # ======================================================= home actions
    def test_start_now_and_cancel_through_updates(self):
        rows = [['Code', 'Wage'], ['P2CU01', '1500'], ['P2CU03', '1600']]
        _rev, first = self.apply(rows, {2: WAGE}, start_date=FUTURE, name='Start me')
        _rev, second = self.apply([['Code', 'Wage'], ['P2CU02', '1700']], {2: WAGE},
                                  start_date=FUTURE, name='Cancel me')
        coming = {c['name']: c for c in self.Upd.get_coming_up()['items']}
        self.assertEqual(set(coming), {'Start me', 'Cancel me'})
        started = self.Upd.start_now(coming['Start me']['apply_id'])
        self.assertTrue(started['ok'], started.get('msg'))
        self.assertEqual(started['written'], 2)
        self.assertEqual(self.state(self.ann)['wage'], 1500.0)
        cancelled = self.Upd.cancel(batch_id=second['batch_id'])
        self.assertTrue(cancelled['ok'], cancelled.get('msg'))
        self.assertEqual(cancelled['values'], 1)
        self.assertEqual(self.state(self.bob)['wage'], 1000.0)
        row = self.batch_row(second['batch_id'])
        self.assertEqual((row['state'], row['state_label']), ('cancelled', 'Cancelled'))
        self.assertFalse(row['can_cancel'] or row['can_undo'])
        self.assertEqual(self.Upd.get_coming_up()['items'], [])
        again = self.Upd.cancel(batch_id=second['batch_id'])
        self.assertFalse(again['ok'])
        self.clock = datetime(2026, 12, 1, 3, 0)
        self.assertEqual(self.run_job(), {})
        self.assertEqual(self.state(self.bob)['wage'], 1000.0, "a cancelled change never starts")
        self.assertEqual(self.batch_row(first['batch_id'])['state'], 'applied')

    def test_paid_since_counts_only_finished_payslips_after_the_date(self):
        self.assertEqual(self.Upd.paid_since({})['count'], 0)
        Payslip = self.env['hr.payslip'].sudo()
        try:
            slip = Payslip.create({'name': 'P2C slip', 'employee_id': self.ann.id,
                                   'contract_id': self.contracts[self.ann.id].id,
                                   'date_from': '2026-10-01', 'date_to': '2026-10-31',
                                   'company_id': self.company.id})
        except Exception as error:   # noqa: BLE001 — the payslip model's own rules
            self.skipTest('no payslip can be made here: %s' % error)
        self.env.cr.execute("UPDATE hr_payslip SET state = 'done' WHERE id = %s", [slip.id])
        Payslip.invalidate_model(['state'])
        people = {str(self.ann.id): '2026-10-15', str(self.bob.id): '2026-10-15'}
        self.assertEqual(self.Upd.paid_since(people)['count'], 1)
        self.assertEqual(self.Upd.paid_since({str(self.ann.id): '2026-11-05'})['count'], 0)

    def test_read_me_names_how_to_give_a_manager(self):
        if openpyxl is None:
            self.skipTest('openpyxl missing')
        sheet = self.Upd.download_sheet(['employee'])
        self.assertTrue(sheet.get('ok'), sheet.get('msg'))
        wb = openpyxl.load_workbook(io.BytesIO(base64.b64decode(sheet['file_b64'])))
        self.assertEqual(wb.sheetnames[0], 'Records')
        notes = ' '.join(str(c.value or '') for c in wb[wb.sheetnames[-1]]['A'])
        self.assertIn('employee code or work email', notes)
        self.assertNotIn('Odoo', notes)
