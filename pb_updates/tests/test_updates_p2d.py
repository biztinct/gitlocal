# -*- coding: utf-8 -*-
"""UPDATES P2d — one-off pay items for a pay month (E2-E16 + the
"Could not be made" display). E1 (byte-identical runs with no one-off) is
proven outside the suite, before and after, on a copy of payobook
(`e1_capture.py`, report R1) — and here for the no-row path (E1b).

A company of its own, today frozen at 11 Nov 2026 in Ho Chi Minh City:

    team A → "P2D Monthly" (end of month): P2D Bonus (adds), P2D Fine (takes)
             "P2D Advance" (mid-month):    P2D Advance bonus, and a P2D Bonus
                                           of its own (E14)
    team B → "P2D Daily" (any run):        P2D Bonus only
    team N → no scheme (two schemes per kind, so no "only scheme" answer)

Every payslip here is computed through the real seams: `compute_sheet`
(no pay data file), `pb.payrun.wizard.attach_spreadsheet` (a pay data file
and a monthly template file), `action_recompute_formula_lines`.
"""
import base64
import csv
import io
from datetime import date, datetime
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

try:
    import openpyxl
except ImportError:            # pragma: no cover
    openpyxl = None

NOW = datetime(2026, 11, 11, 3, 0, 0)        # 10:00 in Ho Chi Minh City
NOV, DEC = '2026-11-01', '2026-12-01'
BON, FINE, MIDB = 'o:P2DBON', 'o:P2DFINE', 'o:P2DMIDB'


def csv_b64(rows):
    out = io.StringIO()
    writer = csv.writer(out)
    for row in rows:
        writer.writerow(row)
    return base64.b64encode(out.getvalue().encode('utf-8')).decode()


def xlsx_b64(rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return base64.b64encode(buf.getvalue()).decode()


class P2dFixture(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        vnd = cls.env.ref('base.VND')
        cls.company = cls.env['res.company'].create(
            {'name': 'P2D Updates Co', 'currency_id': vnd.id})
        cls.company.partner_id.tz = 'Asia/Ho_Chi_Minh'
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env.user.company_id = cls.company
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=[cls.company.id]))
        cls._approvals()
        cls.Upd = cls.env['pb.updates.desk']
        cls.Oneoff = cls.env['pb.updates.oneoff']
        cls.W = cls.env['pb.payrun.wizard']
        Department = cls.env['hr.department']
        cls.team_a = Department.create({'name': 'P2D Team A', 'company_id': cls.company.id})
        cls.team_b = Department.create({'name': 'P2D Team B', 'company_id': cls.company.id})
        cls.team_n = Department.create({'name': 'P2D Team N', 'company_id': cls.company.id})
        cls.category = cls.env['hr.salary.rule.category'].search([], limit=1)
        cls.monthly = cls._config('P2D Monthly', 'P2DMONTHLY', 'end_cycle')
        cls.advance = cls._config('P2D Advance', 'P2DADVANCE', 'mid_cycle')
        cls.daily = cls._config('P2D Daily', 'P2DDAILY', 'end_cycle')
        cls.spare = cls._config('P2D Spare advance', 'P2DSPARE', 'mid_cycle')
        for cfg in (cls.monthly, cls.daily, cls.advance):
            cls._rule(cfg, 'P2D Basic salary', 'P2DBASE', 'earning', 1)
        cls._rule(cls.monthly, 'P2D Bonus', 'P2DBON', 'earning', 2)
        cls._rule(cls.monthly, 'P2D Fine', 'P2DFINE', 'deduction', 3)
        cls._rule(cls.monthly, 'P2D Hours', 'P2DHRS', 'info', 4, value_kind='quantity')
        cls._rule(cls.daily, 'P2D Bonus', 'P2DBON', 'earning', 2)
        cls._rule(cls.advance, 'P2D Advance bonus', 'P2DMIDB', 'earning', 2)
        cls._rule(cls.advance, 'P2D Bonus', 'P2DBON', 'earning', 3)
        Assign = cls.env['hr.formula.scheme.assignment']
        Assign.create({'config_id': cls.monthly.id, 'department_id': cls.team_a.id,
                       'cycle_type': 'end_cycle'})
        Assign.create({'config_id': cls.advance.id, 'department_id': cls.team_a.id,
                       'cycle_type': 'mid_cycle'})
        Assign.create({'config_id': cls.daily.id, 'department_id': cls.team_b.id,
                       'cycle_type': 'any'})
        cls.calendar = cls.company.resource_calendar_id or cls.env['resource.calendar'].create(
            {'name': 'P2D Hours', 'company_id': cls.company.id})
        cls.kind = cls.env['hr.contract.type'].search([], limit=1) or cls.env[
            'hr.contract.type'].create({'name': 'P2D Kind'})
        cls.ann = cls._person('P2D Ann', 'P2D0001', cls.team_a)
        cls.amy = cls._person('P2D Amy', 'P2D0002', cls.team_a)
        cls.bob = cls._person('P2D Bob', 'P2D0003', cls.team_b)
        cls.ned = cls._person('P2D Ned', 'P2D0004', cls.team_n)
        cls.contracts = {p.id: cls._contract(p) for p in (cls.ann, cls.amy, cls.bob, cls.ned)}

    @classmethod
    def _approvals(cls):
        for process in ('records', 'schememap', 'runonly', 'loads'):
            try:
                cls.env['biz.approval.seed'].sudo().set_no_approval_needed(cls.company, process)
            except Exception:   # noqa: BLE001
                pass

    def setUp(self):
        super().setUp()
        patcher = patch.object(type(self.env['pb.records.apply']), '_records_now',
                               lambda _self: NOW)
        patcher.start()
        self.addCleanup(patcher.stop)

    # ------------------------------------------------------------ fixtures
    @classmethod
    def _config(cls, name, code, cycle):
        return cls.env['hr.formula.config'].create({
            'name': name, 'code': code, 'cycle_type': cycle, 'country_code': 'VN',
            'company_id': cls.company.id, 'state': 'active'})

    @classmethod
    def _rule(cls, cfg, name, code, role, seq, value_kind='money'):
        return cls.env['hr.formula.rule'].create({
            'config_id': cfg.id, 'name': name, 'code': code, 'column_type': 'input',
            'sequence': seq, 'default_value': 0.0, 'value_kind': value_kind,
            'net_role': role, 'appears_on_payslip': value_kind == 'money',
            'category_id': cls.category.id})

    @classmethod
    def _person(cls, name, code, team):
        employee = cls.env['hr.employee'].create({
            'name': name, 'barcode': code, 'company_id': cls.company.id,
            'work_email': '%s@p2d.example' % code.lower()})
        version = employee.current_version_id if 'current_version_id' in employee._fields else None
        if version and 'department_id' in version._fields:
            version.department_id = team.id
        else:
            employee.department_id = team.id
        return employee

    @classmethod
    def _contract(cls, employee):
        return cls.env['hr.contract'].create({
            'name': 'P2D contract %s' % employee.name, 'employee_id': employee.id,
            'company_id': cls.company.id, 'wage': 1000.0, 'state': 'open',
            'date_start': '2026-01-01', 'resource_calendar_id': cls.calendar.id,
            'type_id': cls.kind.id})

    # ------------------------------------------------------------ helpers
    def cols(self, used, code=1):
        return {'used': {str(k): v for k, v in used.items()},
                'identity': {'code': code}, 'heads': {}}

    def review(self, rows, used, month=NOV):
        answer = self.Upd.review(csv_b64(rows), 'p2d.csv', self.cols(used),
                                 kind='oneoff', month=month)
        self.assertTrue(answer['ok'], answer.get('msg'))
        return answer

    def send(self, rows, used, month=NOV, name='P2D one-offs'):
        answer = self.review(rows, used, month)
        res = self.Upd.apply(name, csv_b64(rows), 'p2d.csv', self.cols(used),
                             answer['changes'], {'rows': len(rows) - 1},
                             kind='oneoff', month=month)
        self.assertTrue(res['ok'], res.get('msg'))
        return res

    def cell(self, answer, employee, fid):
        row = next(r for r in answer['rows'] if r['emp_id'] == employee.id)
        return row['cells'][fid]

    def row(self, employee, code='P2DBON', month=NOV, states=('approved', 'reserved', 'paid')):
        return self.Oneoff.sudo().search([
            ('employee_id', '=', employee.id), ('code', '=', code),
            ('period_month', '=', month), ('state', 'in', list(states))])

    def make_run(self, cfg=None, ds='2026-11-01', de='2026-11-30', name='P2D November'):
        Run = self.env['hr.payslip.run']
        vals = {'name': name, 'date_start': ds, 'date_end': de,
                'pb_formula_config_id': (cfg or self.monthly).id}
        if 'company_id' in Run._fields:
            vals['company_id'] = self.company.id
        return Run.create(vals)

    def slip(self, employee, run, cfg=None, compute=True):
        slip = self.env['hr.payslip'].create({
            'name': 'P2D %s' % employee.name, 'employee_id': employee.id,
            'contract_id': self.contracts[employee.id].id, 'payslip_run_id': run.id,
            'date_from': run.date_start, 'date_to': run.date_end,
            'company_id': self.company.id, 'formula_config_id': (cfg or self.monthly).id,
            'calculation_method': 'formula'})
        if compute:
            slip.compute_sheet()
        return slip

    def inputs(self, slip):
        import json
        slip.invalidate_recordset()
        return json.loads(slip.formula_input_values or '{}'), json.loads(
            slip.formula_input_sources or '{}')

    def line(self, slip, code):
        return slip.line_ids.filtered(lambda l: l.code == code)

    def pay_file(self, run, rows, cfg=None):
        res = self.W.attach_spreadsheet(run.id, (cfg or self.monthly).id, xlsx_b64(rows),
                                        'p2d-pay-data.xlsx', str(run.date_start),
                                        str(run.date_end), one_time=True)
        self.assertTrue(res['ok'], res.get('msg'))
        return res

    def slip_of(self, run, employee):
        return self.env['hr.payslip'].search([('payslip_run_id', '=', run.id),
                                              ('employee_id', '=', employee.id)])


@tagged('post_install', '-at_install', 'pb_updates', 'pb_updates_p2d')
class TestUpdatesP2d(P2dFixture):

    # ================================================================ screens
    def test_S1_catalogue_and_home(self):
        cat = self.Upd._oneoff_catalogue(self.Upd._desk())
        self.assertEqual(set(cat['codes']), {'P2DBON', 'P2DFINE', 'P2DMIDB'},
                         "base pay (wage), hours (quantity) are never one-off items")
        self.assertEqual(cat['codes']['P2DFINE']['role'], 'deduction')
        self.assertEqual({s['name'] for s in cat['codes']['P2DBON']['schemes']},
                         {'P2D Monthly', 'P2D Daily', 'P2D Advance'})
        home = self.Upd.get_home()
        self.assertTrue(home['oneoff']['available'])
        months = [m['value'] for m in home['oneoff']['months']]
        self.assertEqual(months[0], '2026-09-01')
        self.assertEqual(months[-1], '2027-11-01')
        self.assertEqual(len(months), 15)
        self.assertEqual(home['oneoff']['this_month'], NOV)
        self.assertEqual(home['waiting']['months'], [])

    def test_S2_month_window(self):
        bad = self.Upd.review(csv_b64([['Code', 'P2D Bonus'], ['P2D0001', '5']]), 'x.csv',
                              self.cols({2: BON}), kind='oneoff', month='2026-08-01')
        self.assertFalse(bad['ok'])
        self.assertIn('2 months back to 12 months ahead', bad['msg'])

    def test_S3_sheet_round_trip(self):
        self.send([['Code', 'P2D Bonus'], ['P2D0001', '500']], {2: BON})
        sheet = self.Upd.download_oneoff_sheet(NOV, {})
        self.assertTrue(sheet['ok'], sheet.get('msg'))
        self.assertNotIn('Odoo', sheet['filename'])
        wb = openpyxl.load_workbook(io.BytesIO(base64.b64decode(sheet['file_b64'])))
        ws = wb['Records']
        heads = [c.value for c in ws[1]]
        self.assertIn('P2D Bonus', heads)
        self.assertIn('P2D Fine', heads)
        self.assertEqual(wb.sheetnames[-1], 'Read me')
        self.assertIn('CLEAR', ' '.join(str(c.value) for c in wb['Read me']['A']))
        col_bon, col_fine = heads.index('P2D Bonus') + 1, heads.index('P2D Fine') + 1
        by_code = {ws.cell(row=r, column=1).value: r for r in range(2, ws.max_row + 1)}
        self.assertEqual(ws.cell(row=by_code['P2D0001'], column=col_bon).value, 500)
        bob = by_code['P2D0003']
        self.assertEqual(ws.cell(row=bob, column=col_fine).fill.fgColor.rgb[-6:], 'EEEEF2',
                         "Bob's scheme has no fine: grey")
        cols = self.Upd.read_columns(sheet['file_b64'], sheet['filename'], kind='oneoff',
                                     month=NOV)
        self.assertTrue(cols['ok'] and cols['from_sheet'], cols)
        self.assertEqual(cols['sheet_month'], NOV)
        used, identity = {}, {}
        for c in cols['columns']:
            if c['target'].startswith('identity:'):
                identity[c['target'].split(':')[1]] = c['idx']
            elif c['target'] and c['target'] != 'ignore':
                used[str(c['idx'])] = c['target']
        answer = self.Upd.review(sheet['file_b64'], sheet['filename'],
                                 {'used': used, 'identity': identity, 'heads': {}},
                                 kind='oneoff', month=NOV)
        self.assertEqual(answer['changes'], [], "the sheet sent straight back changes nothing")
        self.assertEqual(self.cell(answer, self.ann, BON)['status'], 'same')

    def test_S4_layout_kept_apart(self):
        rows = [['Staff no', 'Bonus Nov'], ['P2D0001', '100']]
        self.Upd.apply('P2D layout', csv_b64(rows), 'l.csv',
                       {'used': {'2': BON}, 'identity': {'code': 1},
                        'heads': {'1': 'Staff no', '2': 'Bonus Nov'}},
                       [{'emp_id': self.ann.id, 'field_id': BON, 'value': 100}], {},
                       kind='oneoff', month=NOV)
        again = self.Upd.read_columns(csv_b64(rows), 'l.csv', kind='oneoff', month=NOV)
        target = {c['head']: c['target'] for c in again['columns']}
        self.assertEqual(target['Bonus Nov'], BON)
        self.assertTrue(again['layout_known'])
        lasting = self.Upd.read_columns(csv_b64(rows), 'l.csv')
        self.assertNotEqual({c['head']: c['target'] for c in lasting['columns']}.get('Bonus Nov'),
                            BON, "a one-off matching never leaks into a lasting sheet")

    # ================================================================ E2-E7
    def test_E2_no_file_run(self):
        res = self.send([['Code', 'P2D Bonus'], ['P2D0001', '500']], {2: BON})
        self.assertTrue(res['approved'] and not res['pending'])
        self.assertEqual(res['month_label'], 'November 2026')
        row = self.row(self.ann)
        self.assertEqual(row.state, 'approved')
        run = self.make_run()
        slip = self.slip(self.ann, run)
        values, sources = self.inputs(slip)
        self.assertEqual(values['P2DBON'], 500.0)
        self.assertEqual(sources['P2DBON']['via'], 'updates_oneoff')
        self.assertEqual(sources['P2DBON']['src'], 'employee_field')
        self.assertEqual(self.line(slip, 'P2DBON').amount, 500.0)
        self.assertEqual(len(self.line(slip, 'P2DBON')), 1, "in the slip once")
        self.assertEqual((row.state, row.reserved_slip_id), ('reserved', slip))
        slip.write({'state': 'done'})
        self.assertEqual((row.state, row.paid_slip_id), ('paid', slip))

    def test_E3_pay_file_without_the_column(self):
        self.send([['Code', 'P2D Bonus'], ['P2D0001', '500']], {2: BON})
        run = self.make_run()
        self.pay_file(run, [['Employee code', 'Name', 'P2D Basic salary'],
                            ['P2D0001', 'P2D Ann', 2000]])
        slip = self.slip_of(run, self.ann)
        self.assertEqual(len(slip), 1)
        values, sources = self.inputs(slip)
        self.assertEqual(values['P2DBASE'], 2000.0)
        self.assertEqual(values['P2DBON'], 500.0)
        self.assertEqual(sources['P2DBON']['via'], 'updates_oneoff')
        self.assertEqual((self.row(self.ann).state, self.row(self.ann).reserved_slip_id),
                         ('reserved', slip))

    def test_E4_template_month_file(self):
        self.send([['Code', 'P2D Bonus'], ['P2D0001', '500']], {2: BON})
        run = self.make_run()
        month = self.W.template_month_file(self.monthly.id, '2026-11')
        res = self.W.attach_spreadsheet(run.id, self.monthly.id, month['file_b64'],
                                        month['filename'], '2026-11-01', '2026-11-30',
                                        one_time=True)
        self.assertTrue(res['ok'], res.get('msg'))
        slip = self.slip_of(run, self.ann)
        values, sources = self.inputs(slip)
        self.assertEqual(values['P2DBON'], 500.0, "the template's filler 0 is a blank")
        self.assertEqual(sources['P2DBON']['via'], 'updates_oneoff')
        self.assertEqual(self.row(self.ann).reserved_slip_id, slip)
        amy = self.slip_of(run, self.amy)
        self.assertEqual(self.inputs(amy)[0]['P2DBON'], 0.0)

    def test_E5_recompute_everywhere(self):
        self.send([['Code', 'P2D Bonus'], ['P2D0001', '500']], {2: BON})
        run = self.make_run()
        slip = self.slip(self.ann, run)
        slip.compute_sheet()
        slip.action_recompute_formula_lines()
        run.action_recompute_formula_lines_batch()
        self.assertEqual(self.inputs(slip)[0]['P2DBON'], 500.0)
        self.assertEqual(len(self.line(slip, 'P2DBON')), 1)
        self.assertEqual(self.row(self.ann).reserved_slip_id, slip)
        # the same on a pay-file run
        run2 = self.make_run(name='P2D November file', ds='2026-11-01', de='2026-11-30')
        slip.unlink()
        self.pay_file(run2, [['Employee code', 'Name', 'P2D Basic salary'], ['P2D0001', 'Ann', 3]])
        slip2 = self.slip_of(run2, self.ann)
        slip2.action_recompute_formula_lines()
        run2.action_recompute_formula_lines_batch()
        self.assertEqual(self.inputs(slip2)[0]['P2DBON'], 500.0)
        self.assertEqual(self.row(self.ann).reserved_slip_id, slip2)

    def test_E6_two_runs_same_month(self):
        self.send([['Code', 'P2D Bonus'], ['P2D0001', '500']], {2: BON})
        regular = self.make_run(name='P2D regular')
        topup = self.make_run(name='P2D top-up')
        first = self.slip(self.ann, regular)
        second = self.slip(self.ann, topup)
        self.assertEqual(self.inputs(first)[0]['P2DBON'], 500.0)
        values, sources = self.inputs(second)
        self.assertEqual(values['P2DBON'], 0.0, "paid in the first run only")
        self.assertNotEqual(sources['P2DBON'].get('via'), 'updates_oneoff')
        second.action_recompute_formula_lines()
        self.assertEqual(self.inputs(second)[0]['P2DBON'], 0.0)
        self.assertEqual(self.row(self.ann).reserved_slip_id, first)

    def test_E7_cancel_delete_clear(self):
        self.send([['Code', 'P2D Bonus'], ['P2D0001', '500']], {2: BON})
        row = self.row(self.ann)
        run = self.make_run()
        slip = self.slip(self.ann, run)
        slip.write({'state': 'cancel'})
        self.assertEqual((row.state, row.reserved_slip_id.id), ('approved', False))
        slip2 = self.slip(self.ann, run)
        self.assertEqual(row.reserved_slip_id, slip2, "the next payslip pays it")
        slip2.unlink()
        self.assertEqual(row.state, 'approved')
        slip3 = self.slip(self.ann, run)
        self.assertEqual(row.reserved_slip_id, slip3)
        self.W.sudo()._clean_period(run)
        self.assertEqual(row.state, 'approved', "the run cleared")
        run4 = self.make_run(name='P2D again')
        slip4 = self.slip(self.ann, run4)
        self.assertEqual(row.reserved_slip_id, slip4)
        run4.slip_ids.write({'state': 'draft'})
        run4.unlink()
        self.assertEqual(row.state, 'approved', "run deleted")
        self.assertIn('Waiting for a pay run again', row.note)

    # ================================================================ E8-E9 (D11)
    def test_E8_clash_choose_updates(self):
        self.send([['Code', 'P2D Bonus'], ['P2D0001', '500']], {2: BON})
        row = self.row(self.ann)
        run = self.make_run()
        self.pay_file(run, [['Employee code', 'Name', 'P2D Bonus'], ['P2D0001', 'Ann', 700],
                            ['P2D0002', 'Amy', 50]])
        self.assertFalse(self.slip_of(run, self.ann), "the run stops for Ann")
        self.assertTrue(self.slip_of(run, self.amy), "and only for Ann")
        self.assertEqual((row.clash_run_id, row.clash_file_amount, row.clash_choice),
                         (run, 700.0, False))
        # the no-file compute the pay run does next refuses with the sentence
        stray = self.slip(self.ann, run, compute=False)
        with self.assertRaises(UserError) as caught:
            stray.compute_sheet()
        self.assertIn('500', str(caught.exception))
        self.assertIn('700', str(caught.exception))
        with self.assertRaises(UserError):
            stray.write({'state': 'done'})
        summary = self.W.get_summary(run.id)
        clashes = summary['oneoff_clashes']
        self.assertEqual(len(clashes), 1)
        self.assertEqual((clashes[0]['emp'], clashes[0]['item']), ('P2D Ann', 'P2D Bonus'))
        self.assertIn('500', clashes[0]['updates'])
        self.assertIn('700', clashes[0]['file'])
        self.assertTrue(self.Upd.get_waiting()['clashes'])
        res = self.Oneoff.resolve_clash(row.id, 'updates')
        self.assertTrue(res['ok'], res)
        slip = self.slip_of(run, self.ann)
        self.assertEqual(len(slip), 1, "the stray payslip became the file's payslip")
        values, sources = self.inputs(slip)
        self.assertEqual(values['P2DBON'], 500.0)
        self.assertEqual(sources['P2DBON']['via'], 'updates_oneoff')
        self.assertEqual(sources['P2DBON']['ignored']['value'], 700)
        self.assertEqual((row.state, row.reserved_slip_id, row.clash_choice,
                          row.clash_by, row.clash_file_amount),
                         ('reserved', slip, 'updates', self.env.user, 700.0))
        self.assertTrue(row.clash_at)
        self.assertEqual(self.W.get_summary(run.id)['oneoff_clashes'], [])
        slip.write({'state': 'done'})
        self.assertEqual(row.state, 'paid')

    def test_E8b_clash_choose_file(self):
        self.send([['Code', 'P2D Bonus'], ['P2D0001', '500']], {2: BON})
        row = self.row(self.ann)
        run = self.make_run()
        self.pay_file(run, [['Employee code', 'Name', 'P2D Bonus'], ['P2D0001', 'Ann', 700]])
        res = self.Oneoff.resolve_clash(row.id, 'file')
        self.assertTrue(res['ok'], res)
        slip = self.slip_of(run, self.ann)
        values, sources = self.inputs(slip)
        self.assertEqual(values['P2DBON'], 700.0)
        self.assertEqual(sources['P2DBON']['src'], 'excel')
        self.assertEqual(sources['P2DBON']['ignored']['value'], 500.0)
        self.assertEqual((row.state, row.paid_slip_id, row.clash_choice), ('paid', slip, 'file'))
        self.assertIn("pay data file's amount", row.note)
        later = self.slip(self.ann, self.make_run(name='P2D top-up'))
        self.assertEqual(self.inputs(later)[0]['P2DBON'], 0.0, "never paid later")

    def test_E9_equal_amounts(self):
        self.send([['Code', 'P2D Bonus'], ['P2D0001', '500']], {2: BON})
        run = self.make_run()
        self.pay_file(run, [['Employee code', 'Name', 'P2D Bonus'], ['P2D0001', 'Ann', 500]])
        slip = self.slip_of(run, self.ann)
        self.assertEqual(len(slip), 1, "no stop")
        values, sources = self.inputs(slip)
        self.assertEqual(values['P2DBON'], 500.0)
        self.assertEqual(sources['P2DBON']['src'], 'excel')
        self.assertEqual(self.row(self.ann).reserved_slip_id, slip, "paid once")
        self.assertFalse(self.row(self.ann).clash_run_id)

    # ================================================================ E10-E14
    def test_E10_pending_and_cancelled_never_read(self):
        res = self.send([['Code', 'P2D Bonus'], ['P2D0001', '500']], {2: BON})
        row = self.row(self.ann)
        row.write({'state': 'pending'})
        slip = self.slip(self.ann, self.make_run())
        self.assertEqual(self.inputs(slip)[0]['P2DBON'], 0.0)
        row.write({'state': 'cancelled'})
        slip.action_recompute_formula_lines()
        self.assertEqual(self.inputs(slip)[0]['P2DBON'], 0.0)
        self.assertFalse(row.reserved_slip_id)
        self.assertTrue(res['batch_id'])

    def test_E11_deduction_and_negative(self):
        answer = self.review([['Code', 'P2D Fine'], ['P2D0001', '-200'], ['P2D0002', '200']],
                             {2: FINE})
        neg = self.cell(answer, self.ann, FINE)
        self.assertEqual(neg['status'], 'refused')
        self.assertIn('cannot be negative', neg['why'])
        self.assertIn('takes it from pay', neg['why'])
        self.assertEqual(answer['changes'], [{'emp_id': self.amy.id, 'field_id': FINE, 'value': 200.0}])
        self.send([['Code', 'P2D Fine'], ['P2D0002', '200']], {2: FINE})
        slip = self.slip(self.amy, self.make_run())
        line = self.line(slip, 'P2DFINE')
        self.assertEqual(line.amount, 200.0)
        self.assertEqual(line.pay_role, 'deduction')
        # a minus sign sneaked past the screen is refused by the server too
        res = self.Upd.apply('P2D sneaky', csv_b64([['Code', 'P2D Fine'], ['P2D0001', '-5']]),
                             's.csv', self.cols({2: FINE}),
                             [{'emp_id': self.ann.id, 'field_id': FINE, 'value': -5}], {},
                             kind='oneoff', month=NOV)
        self.assertTrue(res.get('nothing'))
        self.assertFalse(self.row(self.ann, 'P2DFINE'))

    def test_E12_not_in_scheme_and_no_scheme(self):
        answer = self.review([['Code', 'P2D Fine', 'P2D Bonus'], ['P2D0003', '50', '60'],
                              ['P2D0004', '70', '80']], {2: FINE, 3: BON})
        off = self.cell(answer, self.bob, FINE)
        self.assertEqual(off['status'], 'off_scheme')
        self.assertIn('P2D Daily', off['why'])
        self.assertEqual(self.cell(answer, self.bob, BON)['status'], 'ok')
        nobody = self.cell(answer, self.ned, BON)
        self.assertEqual(nobody['status'], 'refused')
        self.assertIn('not in any pay scheme for November 2026', nobody['why'])
        self.assertEqual(answer['changes'], [{'emp_id': self.bob.id, 'field_id': BON, 'value': 60.0}])
        res = self.Upd.apply('P2D off', csv_b64([['x']]), 'o.csv', self.cols({2: FINE}),
                             [{'emp_id': self.bob.id, 'field_id': FINE, 'value': 50}], {},
                             kind='oneoff', month=NOV)
        self.assertTrue(res.get('nothing'))
        self.assertEqual(res['off_scheme'], 1)

    def test_E13_replace_clear_reserved(self):
        self.send([['Code', 'P2D Bonus'], ['P2D0001', '500'], ['P2D0002', '300']], {2: BON})
        old = self.row(self.ann)
        answer = self.review([['Code', 'P2D Bonus'], ['P2D0001', '800']], {2: BON})
        cell = self.cell(answer, self.ann, BON)
        self.assertEqual(cell['status'], 'ok')
        self.assertIn('500', cell['old'])
        self.send([['Code', 'P2D Bonus'], ['P2D0001', '800']], {2: BON}, name='P2D replace')
        self.assertEqual(old.state, 'replaced')
        new = self.row(self.ann)
        self.assertEqual((new.amount, new.replaces_id), (800.0, old))
        cleared = self.review([['Code', 'P2D Bonus'], ['P2D0001', 'CLEAR']], {2: BON})
        self.assertTrue(self.cell(cleared, self.ann, BON)['cleared'])
        self.send([['Code', 'P2D Bonus'], ['P2D0001', 'clear']], {2: BON}, name='P2D clear')
        self.assertEqual(new.state, 'cancelled')
        self.assertFalse(self.row(self.ann))
        # a row a pay run has taken cannot be changed from a sheet
        slip = self.slip(self.amy, self.make_run(name='P2D Nov run'))
        self.assertEqual(self.row(self.amy).reserved_slip_id, slip)
        refused = self.cell(self.review([['Code', 'P2D Bonus'], ['P2D0002', '999']], {2: BON}),
                            self.amy, BON)
        self.assertEqual(refused['status'], 'refused')
        self.assertIn('already in pay run P2D Nov run. Change it there.', refused['why'])

    def test_E14_months_and_mid_month(self):
        self.send([['Code', 'P2D Bonus'], ['P2D0001', '500']], {2: BON})
        self.send([['Code', 'P2D Bonus'], ['P2D0001', '900']], {2: BON}, month=DEC, name='Dec')
        self.send([['Code', 'P2D Advance bonus'], ['P2D0001', '40']], {2: MIDB}, name='Mid')
        mid_run = self.make_run(self.advance, '2026-11-01', '2026-11-15', 'P2D advance')
        mid = self.slip(self.ann, mid_run, self.advance)
        values = self.inputs(mid)[0]
        self.assertEqual(values['P2DMIDB'], 40.0, "its own scheme's item")
        self.assertEqual(values['P2DBON'], 0.0, "not the end-of-month bonus")
        nov = self.slip(self.ann, self.make_run())
        self.assertEqual(self.inputs(nov)[0]['P2DBON'], 500.0, "November only")
        self.assertEqual(self.row(self.ann, month=DEC).state, 'approved')

    # ================================================================ E15, E17
    def test_E15_application_data_reads_nothing(self):
        self.send([['Code', 'P2D Bonus'], ['P2D0001', '500']], {2: BON})
        slip = self.env['hr.payslip'].new({
            'employee_id': self.ann.id, 'contract_id': self.contracts[self.ann.id].id,
            'date_from': date(2026, 11, 1), 'date_to': date(2026, 11, 30),
            'formula_config_id': self.monthly.id})
        prov = {}
        values = slip.with_context(pb_application_data_mode=True)._get_formula_input_values(
            self.monthly, provenance=prov)
        self.assertEqual(values['P2DBON'], 0.0)
        self.assertNotEqual(prov['P2DBON'].get('via'), 'updates_oneoff')
        self.assertEqual(self.row(self.ann).state, 'approved')
        self.monthly.sudo().write({'application_data_enabled': True,
                                   'application_effective_from': date(2026, 1, 1)})
        line = self.W._updates_oneoff_line(self.monthly.id, '2026-11-01', '2026-11-30')
        self.assertEqual(line['kind'], 'application')
        self.assertIn('not included in a pay run from application data', line['line'])

    def test_E17_existing_stores_untouched(self):
        before = self.env['hr.payroll.period.input'].sudo().search_count([])
        months = self.env['pb.payroll.month.inputs'].sudo().search_count([])
        self.send([['Code', 'P2D Bonus'], ['P2D0001', '500']], {2: BON})
        self.slip(self.ann, self.make_run())
        self.assertEqual(self.env['hr.payroll.period.input'].sudo().search_count([]), before)
        self.assertEqual(self.env['pb.payroll.month.inputs'].sudo().search_count([]), months)

    def test_E1b_no_row_no_difference(self):
        self.send([['Code', 'P2D Bonus'], ['P2D0002', '500']], {2: BON}, month=DEC)
        run = self.make_run()
        slip = self.slip(self.ann, run)
        values, sources = self.inputs(slip)
        self.assertEqual(values['P2DBON'], 0.0)
        self.assertFalse(any((s or {}).get('via') == 'updates_oneoff' for s in sources.values()))
        line = self.W._updates_oneoff_line(self.monthly.id, '2026-11-01', '2026-11-30')
        self.assertEqual(line, {})
        nov = self.W._updates_oneoff_line(self.monthly.id, '2026-12-01', '2026-12-31')
        self.assertIn('1 one-off pay item from Updates will be included', nov['line'])

    # ================================================================ home + history
    def test_H1_waiting_card_and_history(self):
        self.send([['Code', 'P2D Bonus', 'P2D Fine'], ['P2D0001', '500', '20'],
                   ['P2D0002', '300', '']], {2: BON, 3: FINE})
        waiting = self.Upd.get_waiting()
        month = waiting['months'][0]
        self.assertEqual((month['label'], month['people'], month['items']),
                         ('November 2026', 2, 3))
        self.assertIn('800', month['earn_label'])
        self.assertIn('20', month['take_label'])
        hist = self.Upd.get_history(5)['batches'][0]
        self.assertEqual((hist['kind'], hist['state'], hist['state_label']),
                         ('oneoff', 'waiting_run', 'Waiting for a pay run'))
        self.assertTrue(hist['can_cancel'])
        self.assertFalse(hist['can_undo'])
        slip = self.slip(self.ann, self.make_run(name='P2D Nov'))
        hist = self.Upd.get_history(5)['batches'][0]
        self.assertEqual(hist['state_label'], 'In pay run P2D Nov')
        res = self.Upd.cancel(batch_id=hist['id'])
        self.assertTrue(res['ok'], res)
        self.assertEqual(res['values'], 1, "Amy's bonus; Ann's two are in a pay run")
        self.assertEqual(res['kept'], 2)
        self.assertEqual(self.row(self.amy, states=('cancelled',)).state, 'cancelled')
        self.assertEqual(self.row(self.ann).reserved_slip_id, slip)
        records = self.env['pb.records.desk'].get_history(5)['applies']
        mine = next(h for h in records if h.get('oneoff'))
        self.assertIn('One-off pay items for November 2026', mine['block_note'])


@tagged('post_install', '-at_install', 'pb_updates', 'pb_updates_p2d')
class TestUpdatesP2dRoute(P2dFixture):
    """E16 and "Could not be made", with a real approval route."""

    @classmethod
    def _approvals(cls):
        for process in ('schememap', 'runonly', 'loads'):
            try:
                cls.env['biz.approval.seed'].sudo().set_no_approval_needed(cls.company, process)
            except Exception:   # noqa: BLE001
                pass
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        groups = [cls.env.ref('base.group_user').id, cls.env.ref('hr.group_hr_user').id]
        cls.hr_lead = Users.create({'name': 'P2D HR Lead', 'login': 'p2d_hr_lead',
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
                             'user_id': cls.hr_lead.id, 'date_from': date(2020, 1, 1)})
        cls.env['pb.records.apply']._approval_seed_default(cls.company)
        cls.Engine = cls.env['biz.approval.engine']

    def decide(self, apply_rec, action):
        for _guard in range(6):
            request = apply_rec.approval_request_id
            if not request or request.state not in ('pending', 'blocked'):
                return request
            step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
            seat = step.seat_ids.filtered(lambda s: s.status == 'open')[:1]
            self.Engine.with_user(seat.acting_user_id).decide(request.id, step.key, action, 'p2d')
            apply_rec.invalidate_recordset()
            if action != 'approve':
                return request
        self.fail('never finished')

    def sent(self, value='500'):
        res = self.send([['Code', 'P2D Bonus'], ['P2D0001', value]], {2: BON})
        self.assertTrue(res['pending'], res)
        apply_rec = self.env['pb.records.apply'].browse(res['apply_id'])
        return res, apply_rec, apply_rec.oneoff_ids

    def test_E16_approve(self):
        res, apply_rec, rows = self.sent()
        self.assertEqual(rows.state, 'pending')
        self.assertEqual(self.Upd.get_history(1)['batches'][0]['state'], 'pending')
        slip = self.slip(self.ann, self.make_run())
        self.assertEqual(self.inputs(slip)[0]['P2DBON'], 0.0, "E10: pending is never read")
        detail = apply_rec._approval_detail(apply_rec.approval_request_id)
        self.assertEqual(detail['rows'][0]['sub'], 'P2D Bonus · November 2026')
        self.decide(apply_rec, 'approve')
        self.assertEqual(rows.state, 'approved')
        self.assertTrue(apply_rec.applied)
        slip.action_recompute_formula_lines()
        self.assertEqual(self.inputs(slip)[0]['P2DBON'], 500.0)

    def test_E16_send_back_and_turn_down(self):
        _res, apply_rec, rows = self.sent()
        self.decide(apply_rec, 'return')
        self.assertEqual(rows.state, 'returned')
        _res, apply_rec2, rows2 = self.sent('600')
        self.decide(apply_rec2, 'reject')
        self.assertEqual(rows2.state, 'rejected')
        self.assertFalse(self.row(self.ann))

    def test_E16_cancel_waiting(self):
        res, apply_rec, rows = self.sent()
        answer = self.Upd.cancel(batch_id=res['batch_id'])
        self.assertTrue(answer['ok'], answer)
        self.assertEqual(rows.state, 'cancelled')
        self.assertEqual(apply_rec.approval_request_id.state, 'cancelled')

    def test_X1_could_not_be_made(self):
        """An approved lasting change that could not be written says so."""
        # UPDATES P3a (D3): personal details from a sheet now apply at once
        # under the shipped route; this case needs one that waits.
        self.company.pb_records_sheet_details_now = False
        rows = [['Code', 'Job title'], ['P2D0001', 'After']]
        cols = {'used': {'2': 'f:hr.employee:job_title'}, 'identity': {'code': 1}, 'heads': {}}
        rv = self.Upd.review(csv_b64(rows), 'j.csv', cols)
        res = self.Upd.apply('P2D job', csv_b64(rows), 'j.csv', cols, rv['changes'], {})
        self.assertTrue(res['pending'], res)
        self.ann.job_title = 'Moved meanwhile'
        apply_rec = self.env['pb.records.apply'].browse(res['apply_id'])
        self.decide(apply_rec, 'approve')
        request = apply_rec.approval_request_id
        self.assertEqual(request.state, 'approved')
        self.assertTrue(request.block_reason)
        hist = self.Upd.get_history(1)['batches'][0]
        self.assertEqual((hist['state'], hist['state_label']), ('blocked', 'Could not be made'))
        self.assertIn('changed by somebody else', hist['state_reason'].replace('Somebody else', 'changed by somebody else'))
        records = self.env['pb.records.desk'].get_history(3)['applies']
        mine = next(h for h in records if h['id'] == apply_rec.id)
        self.assertEqual(mine['state_label'], 'Could not be made')
        self.assertIn('Approved, but it could not be made', mine['block_note'])
