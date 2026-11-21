# -*- coding: utf-8 -*-
"""UPDATES P5 (D20) — year-to-date figures before Payobook (Y1-Y12, and the
"Nobody else … add one in Access" way out on the Updates screens).

A company of its own in Ho Chi Minh City, today frozen at 12 Nov 2026. One
scheme "P5 Monthly" (end of month) with inputs GROSS and PIT (each with a
default, so every computed payslip carries a GROSS and a PIT line), P5TAXYTD
and P5MONTHS (inputs that receive figures only when mapped) and P5BONUS.

Three people: Ann and Bob have a FINISHED October payslip (gross 1,000, tax
100); Cal has none (her months are missing). Their figures before Payobook
cover up to 30 Sep 2026.

Y9 (byte-identical runs with no mapping, or a mapping and no figures) is
proven outside the suite on a copy of payobook, before and after (report);
here for the in-suite paths (`test_Y9_*`).
"""
import base64
import csv
import io
import json
from datetime import datetime
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

try:
    import openpyxl
except ImportError:            # pragma: no cover
    openpyxl = None

NOW = datetime(2026, 11, 12, 3, 0, 0)        # 10:00 in Ho Chi Minh City
COVERS = '2026-09-30'
G, T, TX, M = 'y:gross', 'y:tax', 'y:taxable', 'y:months'


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


class P5Fixture(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        vnd = cls.env.ref('base.VND')
        cls.company = cls.env['res.company'].create(
            {'name': 'P5 Updates Co', 'currency_id': vnd.id})
        cls.company.partner_id.tz = 'Asia/Ho_Chi_Minh'
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env.user.company_id = cls.company
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=[cls.company.id]))
        cls._approvals()
        cls.Upd = cls.env['pb.updates.desk']
        cls.Line = cls.env['pb.updates.ytd.line']
        cls.W = cls.env['pb.payrun.wizard']
        cls.team = cls.env['hr.department'].create({'name': 'P5 Team', 'company_id': cls.company.id})
        cls.category = cls.env['hr.salary.rule.category'].search([], limit=1)
        cls.monthly = cls.env['hr.formula.config'].create({
            'name': 'P5 Monthly', 'code': 'P5MONTHLY', 'cycle_type': 'end_cycle',
            'country_code': 'VN', 'company_id': cls.company.id, 'state': 'active'})
        cls._rule('P5 Basic', 'P5BASE', 'earning', 1)
        cls._rule('Gross pay', 'GROSS', 'earning', 2, default=1000.0)
        cls._rule('Income tax', 'PIT', 'deduction', 3, default=100.0)
        cls._rule('Tax so far', 'P5TAXYTD', 'info', 4)
        cls._rule('Months so far', 'P5MONTHS', 'info', 5, kind='integer')
        cls._rule('Gross so far', 'P5GROSSYTD', 'info', 6)
        cls._rule('P5 Bonus', 'P5BONUS', 'earning', 7)
        cls.env['hr.formula.scheme.assignment'].create({
            'config_id': cls.monthly.id, 'department_id': cls.team.id, 'cycle_type': 'any'})
        cls.calendar = cls.company.resource_calendar_id or cls.env['resource.calendar'].create(
            {'name': 'P5 Hours', 'company_id': cls.company.id})
        cls.kind = cls.env['hr.contract.type'].search([], limit=1) or cls.env[
            'hr.contract.type'].create({'name': 'P5 Kind'})
        cls.ann = cls._person('DEMO P5 Ann', 'P5A')
        cls.bob = cls._person('DEMO P5 Bob', 'P5B')
        cls.cal = cls._person('DEMO P5 Cal', 'P5C')
        cls.contracts = {p.id: cls._contract(p) for p in (cls.ann, cls.bob, cls.cal)}
        # Ann and Bob were paid in Payobook in October; Cal was not.
        run = cls.env['hr.payslip.run'].create({
            'name': 'P5 October', 'date_start': '2026-10-01', 'date_end': '2026-10-31',
            'pb_formula_config_id': cls.monthly.id})
        for person in (cls.ann, cls.bob):
            slip = cls.env['hr.payslip'].create({
                'name': 'P5 Oct %s' % person.name, 'employee_id': person.id,
                'contract_id': cls.contracts[person.id].id, 'payslip_run_id': run.id,
                'date_from': '2026-10-01', 'date_to': '2026-10-31', 'company_id': cls.company.id,
                'formula_config_id': cls.monthly.id, 'calculation_method': 'formula'})
            slip.compute_sheet()
            slip.write({'state': 'done'})
        cls.october = run

    @classmethod
    def _approvals(cls):
        for process in ('records', 'schememap', 'runonly', 'loads'):
            try:
                cls.env['biz.approval.seed'].sudo().set_no_approval_needed(cls.company, process)
            except Exception:   # noqa: BLE001
                pass

    @classmethod
    def _rule(cls, name, code, role, seq, default=0.0, kind='money'):
        return cls.env['hr.formula.rule'].create({
            'config_id': cls.monthly.id, 'name': name, 'code': code, 'column_type': 'input',
            'sequence': seq, 'default_value': default, 'value_kind': kind,
            'net_role': role, 'appears_on_payslip': kind == 'money' and role != 'info',
            'category_id': cls.category.id})

    @classmethod
    def _person(cls, name, code):
        employee = cls.env['hr.employee'].create({
            'name': name, 'barcode': code, 'company_id': cls.company.id,
            'work_email': '%s@p5.example' % code.lower()})
        version = employee.current_version_id if 'current_version_id' in employee._fields else None
        if version and 'department_id' in version._fields:
            version.department_id = cls.team.id
        else:
            employee.department_id = cls.team.id
        return employee

    @classmethod
    def _contract(cls, employee):
        return cls.env['hr.contract'].create({
            'name': 'P5 contract %s' % employee.name, 'employee_id': employee.id,
            'company_id': cls.company.id, 'wage': 1000.0, 'state': 'open',
            'date_start': '2026-01-01', 'resource_calendar_id': cls.calendar.id,
            'type_id': cls.kind.id})

    def setUp(self):
        super().setUp()
        patcher = patch.object(type(self.env['pb.records.apply']), '_records_now',
                               lambda _self: NOW)
        patcher.start()
        self.addCleanup(patcher.stop)

    # ------------------------------------------------------------ helpers
    def cols(self, used, code=1):
        return {'used': {str(k): v for k, v in used.items()},
                'identity': {'code': code}, 'heads': {}}

    def review(self, rows, used, covers=COVERS):
        answer = self.Upd.review(csv_b64(rows), 'p5.csv', self.cols(used), kind='ytd',
                                 cutover=covers)
        self.assertTrue(answer['ok'], answer.get('msg'))
        return answer

    def send(self, rows, used, covers=COVERS, name='P5 figures'):
        answer = self.review(rows, used, covers)
        res = self.Upd.apply(name, csv_b64(rows), 'p5.csv', self.cols(used), answer['changes'],
                             {'rows': len(rows) - 1}, kind='ytd', cutover=covers)
        self.assertTrue(res['ok'], res.get('msg'))
        return answer, res

    def cell(self, answer, employee, fid):
        row = next(r for r in answer['rows'] if r['emp_id'] == employee.id)
        return row['cells'][fid]

    def figure(self, employee, key='gross', year=2026):
        return self.Line.sudo().search([('employee_id', '=', employee.id), ('figure', '=', key),
                                        ('tax_year', '=', year), ('state', '=', 'set')])

    def mapping(self, code='P5GROSSYTD', figure='gross', basis='before_period'):
        res = self.Upd.save_ytd_map(self.monthly.id, code, figure, basis)
        self.assertTrue(res['ok'], res.get('msg'))
        return res

    def make_run(self, ds='2026-11-01', de='2026-11-30', name='P5 November'):
        return self.env['hr.payslip.run'].create({
            'name': name, 'date_start': ds, 'date_end': de,
            'pb_formula_config_id': self.monthly.id})

    def slip(self, employee, run, compute=True):
        slip = self.env['hr.payslip'].create({
            'name': 'P5 %s' % employee.name, 'employee_id': employee.id,
            'contract_id': self.contracts[employee.id].id, 'payslip_run_id': run.id,
            'date_from': run.date_start, 'date_to': run.date_end,
            'company_id': self.company.id, 'formula_config_id': self.monthly.id,
            'calculation_method': 'formula'})
        if compute:
            slip.compute_sheet()
        return slip

    def inputs(self, slip):
        slip.invalidate_recordset()
        return json.loads(slip.formula_input_values or '{}'), json.loads(
            slip.formula_input_sources or '{}')

    def slip_of(self, run, employee):
        return self.env['hr.payslip'].search([('payslip_run_id', '=', run.id),
                                              ('employee_id', '=', employee.id)])

    def pay_file(self, run, rows):
        res = self.W.attach_spreadsheet(run.id, self.monthly.id, xlsx_b64(rows),
                                        'p5-pay-data.xlsx', str(run.date_start),
                                        str(run.date_end), one_time=True)
        self.assertTrue(res['ok'], res.get('msg'))
        return res

    def standard(self):
        """Ann 125,000 gross / 12,000 tax / 9 months; Bob 80,000 gross; Cal 50,000."""
        return self.send([['Code', 'Gross pay', 'Income tax withheld', 'Months counted', 'Source'],
                          ['P5A', '125,000', '12000', '9', 'Old payroll report'],
                          ['P5B', '80000', '', '', ''],
                          ['P5C', '50000', '', '9', '']],
                         {2: G, 3: T, 4: M, 5: 'y:_source'})


@tagged('post_install', '-at_install', 'pb_updates', 'pb_updates_p5')
class TestUpdatesP5(P5Fixture):

    # ================================================================ Y1
    def test_Y1_sheet_review_approve_replace_clear_undo(self):
        home = self.Upd.get_home()['ytd']
        self.assertTrue(home['available'])
        self.assertTrue(home['may_send'])
        self.assertEqual([f['key'] for f in home['figures']][:6],
                         ['gross', 'taxable', 'tax', 'ee_social', 'er_social', 'months'])
        rv, res = self.standard()
        self.assertEqual(self.cell(rv, self.ann, G)['status'], 'ok')
        self.assertEqual(rv['tax_year'], 2026)
        self.assertFalse(res['pending'], 'no approval needed in this company')
        self.assertEqual(res['written'], 6)
        ann = self.figure(self.ann)
        self.assertEqual(ann.amount, 125000.0)
        self.assertEqual(str(ann.covers_to), COVERS)
        self.assertEqual(ann.source_note, 'Old payroll report')
        self.assertEqual(self.figure(self.ann, 'months').amount, 9.0)
        # Sent straight back: the same.
        rv2 = self.review([['Code', 'Gross pay'], ['P5A', '125000']], {2: G})
        self.assertEqual(self.cell(rv2, self.ann, G)['status'], 'same')
        self.assertEqual(rv2['changes'], [])
        # Replace: old → new shown, old row kept as replaced.
        rv3, res3 = self.send([['Code', 'Gross pay'], ['P5A', '130000']], {2: G}, name='P5 fix')
        cell = self.cell(rv3, self.ann, G)
        self.assertIn('125', cell['old'])
        self.assertIn('130', cell['new'])
        self.assertEqual(ann.state, 'replaced')
        self.assertEqual(self.figure(self.ann).amount, 130000.0)
        # CLEAR removes it.
        _rv4, res4 = self.send([['Code', 'Gross pay'], ['P5B', 'CLEAR']], {2: G}, name='P5 clear')
        self.assertFalse(self.figure(self.bob))
        # Undo the clear: Bob's figure is back; undo the replace: Ann's 125,000 is back.
        undo = self.Upd.undo(batch_id=res4['batch_id'])
        self.assertTrue(undo['ok'], undo)
        self.assertEqual(self.figure(self.bob).amount, 80000.0)
        undo = self.Upd.undo(batch_id=res3['batch_id'])
        self.assertTrue(undo['ok'], undo)
        self.assertEqual(self.figure(self.ann).amount, 125000.0)
        history = self.Upd.get_history(20)['batches']
        row = next(h for h in history if h['id'] == res['batch_id'])
        self.assertEqual(row['kind'], 'ytd')
        self.assertEqual(row['state'], 'applied')
        undone = next(h for h in history if h['id'] == res3['batch_id'])
        self.assertEqual(undone['state'], 'undone')

    def test_Y1b_sheet_download_round_trip_and_draft(self):
        self.standard()
        sheet = self.Upd.download_ytd_sheet(COVERS, {})
        self.assertTrue(sheet['ok'], sheet.get('msg'))
        self.assertNotIn('Odoo', sheet['filename'])
        wb = openpyxl.load_workbook(io.BytesIO(base64.b64decode(sheet['file_b64'])))
        ws = wb['Records']
        heads = [c.value for c in ws[1]]
        for label in ('Gross pay', 'Taxable pay', 'Income tax withheld', 'Months counted', 'Source'):
            self.assertIn(label, heads)
        readme = ' '.join(str(c.value) for c in wb['Read me']['A'])
        self.assertIn('Nothing here changes how tax is calculated', readme)
        self.assertNotIn('Odoo', readme)
        cols = self.Upd.read_columns(sheet['file_b64'], sheet['filename'], kind='ytd',
                                     cutover=COVERS)
        self.assertTrue(cols['from_sheet'])
        self.assertEqual(cols['sheet_date'], COVERS)
        used = {c['idx']: c['target'] for c in cols['columns'] if c['target'].startswith('y:')}
        rv = self.Upd.review(sheet['file_b64'], sheet['filename'],
                             {'used': {str(k): v for k, v in used.items()},
                              'identity': {'code': 1}, 'heads': {}}, kind='ytd', cutover=COVERS)
        self.assertTrue(rv['ok'], rv.get('msg'))
        self.assertEqual(rv['changes'], [], 'a downloaded sheet sent straight back changes nothing')
        # A draft of this kind.
        draft = self.Upd.save_draft(0, 'ytd', COVERS, 'ytd.xlsx', sheet['file_b64'], None,
                                    {'name': 'x'}, 'match')
        self.assertTrue(draft['ok'])
        row = next(d for d in self.Upd.list_drafts()['drafts'] if d['id'] == draft['draft_id'])
        self.assertEqual(row['kind'], 'ytd')
        self.assertEqual(row['covers_to'], COVERS)
        self.assertTrue(self.Upd.discard_draft(draft['draft_id'])['ok'])

    # ================================================================ Y2
    def test_Y2_bad_cells_and_dates(self):
        rv = self.review([['Code', 'Gross pay', 'Months counted', 'Income tax withheld'],
                          ['P5A', 'abc', '13', '-5'],
                          ['P5B', '1000', '2.5', '10.123']], {2: G, 3: M, 4: T})
        self.assertIn('is not a number', self.cell(rv, self.ann, G)['why'])
        self.assertIn('whole number from 0 to 12', self.cell(rv, self.ann, M)['why'])
        self.assertIn('cannot be negative', self.cell(rv, self.ann, T)['why'])
        self.assertIn('whole number from 0 to 12', self.cell(rv, self.bob, M)['why'])
        self.assertIn('two decimals', self.cell(rv, self.bob, T)['why'])
        self.assertEqual(self.cell(rv, self.bob, G)['status'], 'ok')
        for bad, words in (('2024-12-31', 'outside both'), ('2027-03-31', 'outside both'),
                           ('', 'Pick the date')):
            res = self.Upd.review(csv_b64([['Code', 'Gross pay'], ['P5A', '1']]), 'x.csv',
                                  self.cols({2: G}), kind='ytd', cutover=bad)
            self.assertFalse(res['ok'])
            self.assertIn(words, res['msg'])
        # Joined after the date: an amber note, allowed.
        self.cal.date_of_joining = '2026-10-15'
        rv = self.review([['Code', 'Gross pay'], ['P5C', '1000']], {2: G})
        row = next(r for r in rv['rows'] if r['emp_id'] == self.cal.id)
        self.assertTrue(row['late'])
        self.assertIn('Are you sure', row['late_note'])
        self.assertEqual(row['cells'][G]['status'], 'ok')
        # Sent past the screen: refused by the server too.
        res = self.Upd.apply('bad', csv_b64([['Code']]), 'x.csv', self.cols({}),
                             [{'emp_id': self.ann.id, 'field_id': G, 'value': '-3'}],
                             {}, kind='ytd', cutover=COVERS)
        self.assertTrue(res.get('nothing'))
        self.assertIn('cannot be negative', res['refused'][0]['why'])

    # ================================================================ Y4
    def test_Y4_view_before_paid_total_and_missing_months(self):
        self.standard()
        view = self.Upd.get_ytd_view(2026)
        rows = {r['emp_id']: r for r in view['rows']}
        ann = rows[self.ann.id]
        self.assertEqual(ann['covers_to'], COVERS)
        self.assertEqual(ann['cells']['gross']['before'], 125000.0)
        self.assertEqual(ann['cells']['gross']['paid'], 1000.0, 'October GROSS line')
        self.assertEqual(ann['cells']['gross']['total'], 126000.0)
        self.assertEqual(ann['cells']['tax']['total'], 12100.0)
        self.assertEqual(ann['cells']['months']['total'], 10.0)
        self.assertEqual(ann['missing'], 0)
        self.assertEqual(rows[self.cal.id]['missing'], 0, 'no payslip yet: nothing to call missing')
        # A pay item named as a figure: its own code is summed.
        res = self.Upd.save_ytd_figure(add_item='P5BONUS')
        self.assertTrue(res['ok'], res.get('msg'))
        self.send([['Code', 'P5 Bonus'], ['P5A', '700']], {2: 'y:P5BONUS'}, name='P5 bonus')
        view = self.Upd.get_ytd_view(2026)
        ann = next(r for r in view['rows'] if r['emp_id'] == self.ann.id)
        self.assertEqual(ann['cells']['P5BONUS']['before'], 700.0)
        self.assertEqual(ann['cells']['P5BONUS']['total'], 700.0)
        # December paid while November is not: one month missing.
        run = self.make_run('2026-12-01', '2026-12-31', 'P5 December')
        slip = self.slip(self.ann, run)
        slip.write({'state': 'done'})
        view = self.Upd.get_ytd_view(2026)
        ann = next(r for r in view['rows'] if r['emp_id'] == self.ann.id)
        self.assertEqual(ann['missing'], 1)
        self.assertEqual(ann['cells']['gross']['paid'], 2000.0)
        dl = self.Upd.download_ytd_view(2026)
        self.assertTrue(dl['ok'])
        wb = openpyxl.load_workbook(io.BytesIO(base64.b64decode(dl['file_b64'])))
        heads = [c.value for c in wb.active[1]]
        self.assertIn('Gross pay · before Payobook', heads)
        self.assertIn('Gross pay · total', heads)

    # ================================================================ Y5
    def test_Y5_employee_tax_summary(self):
        self.standard()
        qc = {'codes': ['GROSS', 'SIEMP', 'PIT'], 'ytd': {'GROSS': 1000.0, 'SIEMP': 0.0, 'PIT': 100.0},
              'ytd_year': 2026, 'rows': [1]}
        self.Line._tax_summary_opening(self.ann, qc)
        self.assertEqual(qc['ytd']['GROSS'], 126000.0)
        self.assertEqual(qc['ytd']['PIT'], 12100.0)
        self.assertEqual(qc['ytd_opening'], {'GROSS': 125000.0, 'PIT': 12000.0})
        self.assertIn('30 Sep 2026', qc['ytd_opening_label'])
        self.assertEqual(qc['ytd_opening_title'], 'Before Payobook (up to 30 Sep 2026)')
        # A figure of several codes is listed apart, never split.
        self.send([['Code', 'Employee social contributions'], ['P5A', '9000']], {2: 'y:ee_social'},
                  name='P5 social')
        self.Upd.save_ytd_figure('ee_social', ['SIEMP', 'HIEMP'])
        qc = {'codes': ['GROSS', 'SIEMP', 'PIT'], 'ytd': {'GROSS': 0.0}, 'ytd_year': 2026}
        self.Line._tax_summary_opening(self.ann, qc)
        self.assertEqual(qc['ytd_opening_apart'][0]['amount'], 9000.0)
        self.assertNotIn('SIEMP', qc['ytd_opening'])
        # Nobody else changes.
        other = self.env['hr.employee'].create({'name': 'DEMO P5 Dan', 'company_id': self.company.id})
        qc = {'codes': ['GROSS'], 'ytd': {'GROSS': 5.0}, 'ytd_year': 2026}
        before = dict(qc)
        self.Line._tax_summary_opening(other, qc)
        self.assertEqual(qc, before)
        # The page template carries the row.
        arch = self.env.ref('pb_updates.portal_my_taxsheet_ytd').arch
        self.assertIn('ytd_opening_title', arch)

    # ================================================================ Y6
    def test_Y6_no_file_run_receives_once_with_both_parts(self):
        self.standard()
        self.mapping()
        self.mapping('P5MONTHS', 'months', 'with_period')
        self.mapping('P5TAXYTD', 'tax', 'opening')
        run = self.make_run()
        slip = self.slip(self.ann, run)
        values, sources = self.inputs(slip)
        self.assertEqual(values['P5GROSSYTD'], 126000.0, '125,000 before + 1,000 October')
        self.assertEqual(values['P5MONTHS'], 11.0, '9 before + October + this period')
        self.assertEqual(values['P5TAXYTD'], 12000.0, 'before Payobook only')
        parts = sources['P5GROSSYTD']['ytd']
        self.assertEqual((parts['before'], parts['paid']), (125000.0, 1000.0))
        self.assertEqual(sources['P5GROSSYTD']['via'], 'updates_ytd')
        uses = self.env['pb.updates.ytd.use'].sudo().search([('payslip_id', '=', slip.id)])
        self.assertEqual(set(uses.mapped('state')), {'in_run'})
        self.assertEqual(len(uses), 3)
        slip.action_recompute_formula_lines()
        values, _s = self.inputs(slip)
        self.assertEqual(values['P5GROSSYTD'], 126000.0, 'recalculated: still once')
        self.assertEqual(len(self.env['pb.updates.ytd.use'].sudo().search(
            [('payslip_id', '=', slip.id)])), 3)

    def test_Y6b_months_missing_stop_the_payslip(self):
        self.standard()
        self.mapping()
        run = self.make_run('2026-12-01', '2026-12-31', 'P5 December')
        slip = self.slip(self.ann, run, compute=False)
        with self.assertRaises(UserError) as caught:
            slip.compute_sheet()
        self.assertIn('no finished payslip for November 2026', str(caught.exception))

    def test_Y6d_paid_in_payobook_not_known_stops(self):
        self.standard()
        self.send([['Code', 'Taxable pay'], ['P5A', '90000']], {2: TX}, name='P5 taxable')
        self.mapping('P5GROSSYTD', 'taxable', 'before_period')
        run = self.make_run()
        slip = self.slip(self.ann, run, compute=False)
        with self.assertRaises(UserError) as caught:
            slip.compute_sheet()
        self.assertIn('has the pay items that make up Taxable pay', str(caught.exception))
        self.mapping('P5GROSSYTD', 'taxable', 'opening')
        slip.compute_sheet()
        self.assertEqual(self.inputs(slip)[0]['P5GROSSYTD'], 90000.0, 'before Payobook only: fine')

    def test_Y6c_pay_file_and_template_runs(self):
        self.standard()
        self.mapping()
        run = self.make_run()
        self.pay_file(run, [['Employee code', 'Name', 'P5 Bonus'], ['P5A', 'Ann', 50]])
        slip = self.slip_of(run, self.ann)
        values, sources = self.inputs(slip)
        self.assertEqual(values['P5GROSSYTD'], 126000.0, 'the file has no column for it')
        self.assertEqual(sources['P5GROSSYTD']['ytd']['before'], 125000.0)
        self.assertEqual(values['P5BONUS'], 50.0)
        run2 = self.make_run(name='P5 November template')
        month = self.W.template_month_file(self.monthly.id, '2026-11')
        res = self.W.attach_spreadsheet(run2.id, self.monthly.id, month['file_b64'],
                                        month['filename'], '2026-11-01', '2026-11-30',
                                        one_time=True)
        self.assertTrue(res['ok'], res.get('msg'))
        values, _s = self.inputs(self.slip_of(run2, self.ann))
        self.assertEqual(values['P5GROSSYTD'], 126000.0, "the template's filler 0 is a blank")

    # ================================================================ Y7
    def test_Y7_file_with_a_different_number_stops_and_asks(self):
        self.standard()
        self.mapping()
        run = self.make_run()
        self.pay_file(run, [['Employee code', 'Name', 'Gross so far'],
                            ['P5A', 'Ann', 999], ['P5B', 'Bob', 81000]])
        self.assertFalse(self.slip_of(run, self.ann).filtered(
            lambda s: s.state != 'cancel' and s.formula_input_values), 'no payslip from the file')
        ask = self.env['pb.updates.ytd.ask'].sudo().search([('employee_id', '=', self.ann.id)])
        self.assertEqual((ask.updates_amount, ask.clash_file_amount), (126000.0, 999.0))
        summary = self.W.get_summary(run.id)
        clash = next(c for c in summary['oneoff_clashes'] if c['emp_id'] == self.ann.id)
        self.assertTrue(clash['id'].startswith('y:'))
        self.assertIn('999', clash['file'])
        waiting = self.Upd.get_waiting()
        self.assertTrue(any(c['id'] == clash['id'] for c in waiting['clashes']))
        # Equal amounts: once, no question (Bob 80,000 + 1,000 = 81,000).
        bob = self.slip_of(run, self.bob)
        values, sources = self.inputs(bob)
        self.assertEqual(values['P5GROSSYTD'], 81000.0)
        self.assertTrue(sources['P5GROSSYTD'].get('agreed'))
        self.assertFalse(self.env['pb.updates.ytd.ask'].sudo().search(
            [('employee_id', '=', self.bob.id)]))
        # Choose the Updates amount.
        res = self.env['pb.updates.oneoff'].resolve_clash(clash['id'], 'updates')
        self.assertTrue(res['ok'], res)
        slip = self.slip_of(run, self.ann).filtered(lambda s: s.state != 'cancel')[:1]
        values, sources = self.inputs(slip)
        self.assertEqual(values['P5GROSSYTD'], 126000.0)
        self.assertEqual(sources['P5GROSSYTD']['ignored']['value'], 999)

    def test_Y7b_choose_the_file(self):
        self.standard()
        self.mapping()
        run = self.make_run()
        self.pay_file(run, [['Employee code', 'Name', 'Gross so far'], ['P5A', 'Ann', 999]])
        ask = self.env['pb.updates.ytd.ask'].sudo().search([('employee_id', '=', self.ann.id)])
        res = self.env['pb.updates.oneoff'].resolve_clash('y:%s' % ask.id, 'file')
        self.assertTrue(res['ok'], res)
        slip = self.slip_of(run, self.ann).filtered(lambda s: s.state != 'cancel')[:1]
        values, sources = self.inputs(slip)
        self.assertEqual(values['P5GROSSYTD'], 999.0)
        self.assertFalse(self.env['pb.updates.ytd.use'].sudo().search(
            [('payslip_id', '=', slip.id)]), 'the file was used, not the figure')

    def test_Y7c_an_open_question_blocks_finishing(self):
        self.standard()
        self.mapping()
        run = self.make_run()
        self.pay_file(run, [['Employee code', 'Name', 'Gross so far'], ['P5A', 'Ann', 999]])
        slip = self.slip(self.ann, run, compute=False)
        with self.assertRaises(UserError):
            slip.write({'state': 'done'})

    # ================================================================ Y8
    def test_Y8_used_by_a_finished_slip_is_locked_then_released(self):
        self.standard()
        self.mapping()
        run = self.make_run()
        slip = self.slip(self.ann, run)
        slip.write({'state': 'done'})
        use = self.env['pb.updates.ytd.use'].sudo().search([('payslip_id', '=', slip.id)])
        self.assertEqual(use.state, 'used')
        rv = self.review([['Code', 'Gross pay'], ['P5A', '1']], {2: G})
        self.assertIn('was used in pay run P5 November', self.cell(rv, self.ann, G)['why'])
        rv = self.review([['Code', 'Gross pay'], ['P5A', 'CLEAR']], {2: G})
        self.assertEqual(self.cell(rv, self.ann, G)['status'], 'refused')
        first = self.Upd.get_history(20)['batches'][-1]
        undo = self.Upd.undo(batch_id=first['id'])
        self.assertIn('so it stays', ' '.join(undo.get('kept') or []))
        self.assertEqual(self.figure(self.ann).amount, 125000.0)
        slip.write({'state': 'cancel'})
        self.assertFalse(use.exists(), 'released when the payslip is cancelled')
        rv = self.review([['Code', 'Gross pay'], ['P5A', '1']], {2: G})
        self.assertEqual(self.cell(rv, self.ann, G)['status'], 'ok')

    # ================================================================ Y9
    def test_Y9_no_mapping_or_no_figures_change_nothing(self):
        run = self.make_run()
        plain = self.slip(self.ann, run)
        base = self.inputs(plain)
        self.mapping()
        again = self.slip(self.ann, self.make_run(name='P5 again'))
        self.assertEqual(self.inputs(again), base, 'a mapping and no figures: identical')
        self.standard()
        other = self.Line.sudo()._plan_for_slip(self.ann, self.monthly, '2026-11-01', '2026-11-30')
        self.assertTrue(other)
        self.env['pb.updates.ytd.map'].sudo().search([]).unlink()
        third = self.slip(self.ann, self.make_run(name='P5 third'))
        self.assertEqual(self.inputs(third), base, 'figures and no mapping: identical')
        self.assertEqual(self.Line.sudo()._plan_for_slip(self.ann, self.monthly, '2026-11-01',
                                                         '2026-11-30'), {})

    # ================================================================ Y10
    def test_Y10_application_data_and_download_for_the_pay_run(self):
        self.standard()
        self.mapping()
        self.mapping('P5MONTHS', 'months', 'with_period')
        run = self.make_run()
        slip = self.slip(self.ann, run, compute=False)
        values = slip.with_context(pb_application_data_mode=True)._get_formula_input_values(
            self.monthly, provenance={})
        self.assertEqual(values.get('P5GROSSYTD', 0.0), 0.0, 'application data: nothing delivered')
        dl = self.Upd.download_for_payrun(self.monthly.id, '2026-11-01')
        self.assertTrue(dl['ok'], dl.get('msg'))
        wb = openpyxl.load_workbook(io.BytesIO(base64.b64decode(dl['file_b64'])))
        ws = wb.worksheets[0]
        heads = [c.value for c in ws[1]]
        self.assertIn('Gross so far (P5GROSSYTD)', heads)
        rows = {r[0]: r for r in ws.iter_rows(min_row=2, values_only=True)}
        col = heads.index('Gross so far (P5GROSSYTD)')
        self.assertEqual(rows['P5A'][col], 126000.0)
        self.assertEqual(rows['P5A'][heads.index('Months so far (P5MONTHS)')], 11.0)
        self.assertIn('months with no finished payslip', rows['P5C'][-1])
        adj = wb.worksheets[1]
        aheads = [c.value for c in adj[1]]
        self.assertEqual(aheads[:9], ['employee_id/.id', 'config_id/.id', 'component_id/.id',
                                      'date_from', 'date_to', 'value_decimal', 'unit', 'reason',
                                      'evidence_reference'])
        arows = [r for r in adj.iter_rows(min_row=2, values_only=True) if r[0] == self.ann.id]
        self.assertEqual(len(arows), 2)

    # ================================================================ set-up gates
    def test_setup_needs_a_payroll_manager(self):
        Users = self.env['res.users'].with_context(no_reset_password=True)
        officer = Users.create({
            'name': 'DEMO P5 Officer', 'login': 'p5_officer',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('hr.group_hr_user').id,
                                  self.env.ref('pb_hr_payroll_base.group_payroll_base_officer').id])],
            'company_ids': [(6, 0, [self.company.id])], 'company_id': self.company.id})
        desk = self.Upd.with_user(officer)
        self.assertTrue(desk.get_ytd_view(2026)['ok'])
        with self.assertRaises(AccessError):
            desk.save_ytd_map(self.monthly.id, 'P5GROSSYTD', 'gross', 'before_period')
        hr_only = Users.create({
            'name': 'DEMO P5 HR', 'login': 'p5_hr',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('hr.group_hr_user').id])],
            'company_ids': [(6, 0, [self.company.id])], 'company_id': self.company.id})
        self.assertFalse(self.Upd.with_user(hr_only).get_home()['ytd']['available'])
        with self.assertRaises(AccessError):
            self.Upd.with_user(hr_only).get_ytd_view(2026)

    # ================================================================ Y12
    def test_Y12_no_vendor_name_in_new_strings(self):
        import os
        import re
        here = os.path.dirname(os.path.dirname(__file__))
        for rel in ('models/updates_ytd.py', 'models/updates_ytd_desk.py',
                    'models/updates_ytd_payrun.py', 'controllers/ytd_portal.py',
                    'views/ytd_portal.xml', 'static/src/js/updates_ytd.js',
                    'static/src/xml/updates_ytd.xml'):
            with open(os.path.join(here, rel), encoding='utf-8') as fh:
                text = fh.read()
            for literal in re.findall(r'_t?\(\s*"((?:[^"\\]|\\.)*)"|_t?\(\s*\'((?:[^\'\\]|\\.)*)\'',
                                      text):
                self.assertNotIn('Odoo', ''.join(literal), rel)
            if rel.endswith('.xml'):
                visible = re.sub(r'<[^>]+>', ' ', text)
                self.assertNotIn('Odoo', visible, rel)


@tagged('post_install', '-at_install', 'pb_updates', 'pb_updates_p5')
class TestUpdatesP5Route(P5Fixture):
    """Y3 — the records (pay) route, with an HR lead step."""

    @classmethod
    def _approvals(cls):
        from datetime import date as d
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        groups = [cls.env.ref('base.group_user').id, cls.env.ref('hr.group_hr_user').id]
        cls.hr_lead = Users.create({'name': 'DEMO P5 HR Lead', 'login': 'p5_hr_lead',
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
            self.Engine.with_user(seat.acting_user_id).decide(request.id, step.key, action, 'p5')
            apply_rec.invalidate_recordset()
            if action != 'approve':
                return request
        self.fail('never finished')

    def sent(self):
        _rv, res = self.send([['Code', 'Gross pay'], ['P5A', '125000'], ['P5B', '80000']], {2: G})
        self.assertTrue(res['pending'], res)
        self.assertIn('DEMO P5 HR Lead', res['with_whom'])
        apply_rec = self.env['pb.records.apply'].browse(res['apply_id'])
        lines = apply_rec.ytd_line_ids
        self.assertEqual(set(lines.mapped('state')), {'waiting'})
        self.assertFalse(self.figure(self.ann), 'nothing set before approval')
        return res, apply_rec, lines

    def test_Y3_outlook_names_the_approver(self):
        out = self.Upd.ytd_outlook([{'emp_id': self.ann.id, 'field_id': G}])
        self.assertEqual(out['outcome'], 'approval')
        self.assertIn('DEMO P5 HR Lead', out['line'])

    def test_Y3_approve(self):
        _res, apply_rec, lines = self.sent()
        detail = apply_rec._approval_detail(apply_rec.approval_request_id)
        self.assertEqual(detail['title'], 'Year-to-date figures before Payobook')
        self.assertIn('Year-to-date figures for 2026', apply_rec._headline())
        self.decide(apply_rec, 'approve')
        self.assertEqual(set(lines.mapped('state')), {'set'})
        self.assertEqual(self.figure(self.ann).amount, 125000.0)

    def test_Y3_send_back_turn_down_cancel(self):
        _res, apply_rec, lines = self.sent()
        self.decide(apply_rec, 'return')
        self.assertEqual(set(lines.mapped('state')), {'returned'})
        res, apply_rec, lines = self.sent()
        self.decide(apply_rec, 'reject')
        self.assertEqual(set(lines.mapped('state')), {'rejected'})
        res, apply_rec, lines = self.sent()
        out = self.Upd.cancel(batch_id=res['batch_id'])
        self.assertTrue(out['ok'], out)
        self.assertEqual(set(lines.mapped('state')), {'cancelled'})
        self.assertFalse(self.figure(self.ann))


@tagged('post_install', '-at_install', 'pb_updates', 'pb_updates_p5')
class TestUpdatesP5WayOut(TransactionCase):
    """P6 deviation 1 on the Updates screens: under "Nobody else in <company>
    can approve bank details yet — add one in Access", the inbox's links for
    whoever can use them, else the plain sentence."""

    def test_way_out_links_or_ask(self):
        if 'pb.approval.inbox' not in self.env:
            self.skipTest('approvals set-up not installed')
        Desk = self.env['pb.updates.desk']
        admin = Desk._way_out(kind='access')
        self.assertTrue(admin['links'], 'a system administrator gets the links')
        self.assertEqual(admin['ask'], '')
        keys = {l['key'] for l in admin['links']}
        self.assertIn('people', keys)
        Users = self.env['res.users'].with_context(no_reset_password=True)
        plain = Users.create({'name': 'DEMO P5 Plain', 'login': 'p5_plain',
                              'group_ids': [(6, 0, [self.env.ref('base.group_user').id,
                                                    self.env.ref('hr.group_hr_user').id])]})
        out = Desk.with_user(plain)._way_out(kind='access')
        self.assertEqual(out['links'], [])
        self.assertIn('Only your administrator can add someone', out['ask'])
        route = Desk._way_out(kind='route')
        self.assertEqual([l['key'] for l in route['links']], ['route'])
