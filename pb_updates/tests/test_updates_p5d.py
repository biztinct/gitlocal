# -*- coding: utf-8 -*-
"""UPDATES P5d — owner decisions of 2026-11-13 (ledger D29-D32).

  Z1/Z2  the employee's own tax summary (`/my/taxsheet`) counts the year the
         way "paid in Payobook" does (D29): a mid-month advance is never added
         on top of its month-end payslip; one that cannot be matched is shown
         apart, not added; nobody without an advance sees any change.
  Z3-Z5  a person with no figure before Payobook who joined this tax year is
         paid in Payobook alone (D31) — only when the joining date is filled
         in, every month from the first payslip is covered and that payslip
         starts in or before the joining month. Anything else stays as P5c.

Every expected number is worked out BY HAND next to it. A company of its own;
today frozen at 20 Nov 2026; tax year 2026. The fixture helpers are P5c's own
(`test_updates_p5c`), borrowed, not copied.
"""
import base64
import io
import json
from datetime import date
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

from . import test_updates_p5c as p5c

try:
    import openpyxl
except ImportError:            # pragma: no cover
    openpyxl = None

MONTH_END = dict(GROSS=100000.0, PIT=-10000.0, SIEMP=-8000.0)


@tagged('post_install', '-at_install', 'pb_updates', 'pb_updates_p5d')
class TestUpdatesP5d(TransactionCase):

    # P5c's fixture helpers, bound to this class.
    _scheme = p5c.TestUpdatesP5c.__dict__['_scheme']
    _person = p5c.TestUpdatesP5c.__dict__['_person']
    _finished = p5c.TestUpdatesP5c.__dict__['_finished']
    cols = p5c.TestUpdatesP5c.__dict__['cols']
    load = p5c.TestUpdatesP5c.__dict__['load']

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        vnd = cls.env.ref('base.VND')
        cls.company = cls.env['res.company'].create(
            {'name': 'P5d Joiners Co', 'currency_id': vnd.id})
        cls.company.partner_id.tz = 'Asia/Ho_Chi_Minh'
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env.user.company_id = cls.company
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=[cls.company.id]))
        for process in ('records', 'schememap', 'runonly', 'loads'):
            try:
                cls.env['biz.approval.seed'].sudo().set_no_approval_needed(cls.company, process)
            except Exception:   # noqa: BLE001
                pass
        cls.Upd = cls.env['pb.updates.desk']
        cls.Line = cls.env['pb.updates.ytd.line']
        cls.category = cls.env['hr.salary.rule.category'].search([], limit=1)
        cls.team = cls.env['hr.department'].create({'name': 'P5d Team', 'company_id': cls.company.id})
        cls.rules = {}
        cls.monthly = cls._scheme('P5d Monthly', 'P5DMONTH', 'end_cycle', [
            ('GROSS', 'earning'), ('PIT', 'deduction'), ('SIEMP', 'deduction'),
            ('ADVIN', 'deduction'), ('GROSSYTD', 'info'), ('TAXYTD', 'info'),
            ('MONTHSYTD', 'info')])
        cls.advance = cls._scheme('P5d Advance', 'P5DADV', 'mid_cycle', [
            ('GROSS', 'info'), ('PIT', 'info'), ('SIEMP', 'info'), ('ADV', 'earning')])
        cls.loose = cls._scheme('P5d Loose advance', 'P5DLOOSE', 'mid_cycle', [
            ('GROSS', 'info'), ('ADV', 'earning')])
        cls.env['hr.payroll.cycle.component.mapping'].create({
            'mid_cycle_config_id': cls.advance.id, 'end_cycle_config_id': cls.monthly.id,
            'mid_component_id': cls.rules[(cls.advance.id, 'ADV')].id,
            'end_component_id': cls.rules[(cls.monthly.id, 'ADVIN')].id})
        cls.env['hr.formula.scheme.assignment'].create({
            'config_id': cls.monthly.id, 'department_id': cls.team.id, 'cycle_type': 'any'})
        cls.calendar = cls.company.resource_calendar_id or cls.env['resource.calendar'].create(
            {'name': 'P5d Hours', 'company_id': cls.company.id})
        cls.kind = cls.env['hr.contract.type'].search([], limit=1) or cls.env[
            'hr.contract.type'].create({'name': 'P5d Kind'})
        cls.runs = {}
        cls.people = {}
        joined = {'JOY': date(2026, 5, 1), 'KIM': date(2026, 5, 1), 'MIA': date(2025, 6, 1),
                  'NED': date(2026, 5, 1), 'OLA': date(2026, 5, 1), 'PIA': date(2026, 12, 1)}
        for code in ('ZOE', 'YAN', 'XIA', 'WES', 'JOY', 'KIM', 'LEO', 'MIA', 'NED', 'OLA', 'PIA'):
            person = cls._person('DEMO P5d %s' % code.title(), 'P5D' + code)
            if code in joined:
                person.write({'date_of_joining': joined[code]})
            cls.people[code] = person
        P, M, A, L = cls.people, cls.monthly, cls.advance, cls.loose
        # ---- Z1/Z2: the tax summary.
        # ZOE — a linked advance (GROSS 100,000 as a working figure) and the
        # month-end payslip in April, May and June.
        for m in (4, 5, 6):
            cls._finished(P['ZOE'], A, m, {'GROSS': 100000.0, 'PIT': -10000.0,
                                           'SIEMP': -8000.0, 'ADV': 60000.0})
            cls._finished(P['ZOE'], M, m, dict(MONTH_END))
        # YAN — month-end only, April to June: no advance at all.
        for m in (4, 5, 6):
            cls._finished(P['YAN'], M, m, dict(MONTH_END, GROSS=90000.0 + m))
        # XIA — like ZOE, and figures before Payobook (loaded in the test).
        for m in (4, 5, 6):
            cls._finished(P['XIA'], A, m, {'GROSS': 100000.0, 'ADV': 60000.0})
            cls._finished(P['XIA'], M, m, dict(MONTH_END))
        # WES — July: an advance of a scheme linked to nothing + the month-end.
        cls._finished(P['WES'], L, 7, {'GROSS': 70000.0, 'ADV': 40000.0})
        cls._finished(P['WES'], M, 7, dict(MONTH_END))
        # ---- Z3-Z5: joined this year.
        for m in range(5, 12):                       # JOY: May .. November
            cls._finished(P['JOY'], M, m, dict(MONTH_END))
        for m in (5, 7, 8, 9, 10, 11):               # KIM: June missing
            cls._finished(P['KIM'], M, m, dict(MONTH_END))
        for m in range(5, 12):                       # LEO: no joining date
            cls._finished(P['LEO'], M, m, dict(MONTH_END))
        for m in range(5, 12):                       # MIA: joined last year
            cls._finished(P['MIA'], M, m, dict(MONTH_END))
        for m in range(6, 12):                       # NED: first payslip a month after joining
            cls._finished(P['NED'], M, m, dict(MONTH_END))
        for m in range(5, 12):                       # OLA: joined May, has figures
            cls._finished(P['OLA'], M, m, dict(MONTH_END))
        # PIA joins on 1 December: nothing finished yet.
        cls.Upd.save_ytd_figure('gross', ['GROSS'])
        cls.Upd.save_ytd_figure('tax', ['PIT'])
        cls.Upd.save_ytd_figure('ee_social', ['SIEMP'])

    def setUp(self):
        super().setUp()
        patcher = patch.object(type(self.env['pb.records.apply']), '_records_now',
                               lambda _self: p5c.NOW)
        patcher.start()
        self.addCleanup(patcher.stop)

    # ------------------------------------------------------------ helpers
    def summary(self, person):
        """The employee tax summary's values, built exactly as
        `pb_me_portal`'s `/my/taxsheet` builds them, then passed through
        `pb_updates`' override (counted totals, then figures before Payobook)."""
        Slip = self.env['hr.payslip'].sudo()
        slips = Slip.search([('employee_id', '=', person.id), ('state', '=', 'done')],
                            order='date_to desc', limit=48)
        codes = Slip._ess_tax_codes()
        rows, ytd, current = [], {c: 0.0 for c in codes}, None
        for slip in slips:
            data = slip._ess_tax_rows(codes)
            year = slip.date_to.year if slip.date_to else None
            rows.append({'id': slip.id, 'name': slip.name, 'year': year,
                         'cells': {c: data.get(c, {}).get('amount') for c in codes}})
            if current is None and year:
                current = year
            if year == current:
                for c in codes:
                    ytd[c] += data.get(c, {}).get('amount') or 0.0
        qc = {'codes': codes, 'rows': rows, 'ytd': ytd, 'ytd_year': current}
        page = json.loads(json.dumps(qc))
        Line = self.Line.sudo()
        Line._tax_summary_counted(person, qc)
        Line._tax_summary_opening(person, qc)
        return page, qc

    def view(self):
        _figures, rows = self.Upd._ytd_rows(2026, [p.id for p in self.people.values()])
        return {r['emp_id']: r for r in rows}

    def mapping(self, code, figure, basis='before_period'):
        res = self.Upd.save_ytd_map(self.monthly.id, code, figure, basis)
        self.assertTrue(res['ok'], res.get('msg'))

    def plan(self, code, ds='2026-12-01', de='2026-12-31'):
        return self.Line.sudo()._plan_for_slip(self.people[code], self.monthly, ds, de)

    def december_slip(self, code):
        run = self.env['hr.payslip.run'].create({
            'name': 'P5d December %s' % code, 'date_start': '2026-12-01',
            'date_end': '2026-12-31', 'pb_formula_config_id': self.monthly.id})
        person = self.people[code]
        contract = self.env['hr.contract'].search([('employee_id', '=', person.id)], limit=1)
        return self.env['hr.payslip'].create({
            'name': 'P5d Dec %s' % person.name, 'employee_id': person.id,
            'contract_id': contract.id, 'payslip_run_id': run.id, 'date_from': '2026-12-01',
            'date_to': '2026-12-31', 'company_id': self.company.id,
            'formula_config_id': self.monthly.id, 'calculation_method': 'formula'})

    def three_mappings(self):
        self.mapping('GROSSYTD', 'gross')
        self.mapping('TAXYTD', 'tax')
        self.mapping('MONTHSYTD', 'months', 'with_period')

    # ================================================================ Z1
    def test_Z1_tax_summary_counts_each_month_once(self):
        page, qc = self.summary(self.people['ZOE'])
        # The page alone added both payslips of each month: 6 x 100,000.
        self.assertEqual(page['ytd']['GROSS'], 600000.0)
        self.assertEqual(page['ytd']['PIT'], -60000.0)
        # Now: the three month-end payslips only — 3 x 100,000; tax 3 x 10,000
        # and contributions 3 x 8,000, in the page's own (negative) sign.
        self.assertEqual(qc['ytd']['GROSS'], 300000.0)
        self.assertEqual(qc['ytd']['PIT'], -30000.0)
        self.assertEqual(qc['ytd']['SIEMP'], -24000.0)
        # The same numbers as the year-to-date view's "paid in Payobook".
        cells = self.view()[self.people['ZOE'].id]['cells']
        self.assertEqual(qc['ytd']['GROSS'], cells['gross']['paid'])
        self.assertEqual(-qc['ytd']['PIT'], cells['tax']['paid'])
        self.assertEqual(-qc['ytd']['SIEMP'], cells['ee_social']['paid'])
        # Every payslip is still listed; the three advances say why they are
        # not in the totals.
        self.assertEqual(len(qc['rows']), 6)
        self.assertEqual(qc['rows'], page['rows'])
        self.assertEqual(len(qc['ytd_not_added']), 3)
        self.assertTrue(all(w == 'Mid-month advance · not added'
                            for w in qc['ytd_not_added'].values()))
        self.assertFalse(qc['ytd_advance_apart'])
        self.assertIn('counted once', qc['ytd_advance_note'])

    # ================================================================ Z2
    def test_Z2a_no_advance_page_unchanged(self):
        page, qc = self.summary(self.people['YAN'])
        self.assertEqual(qc, page, 'not one value of the page changes')
        # 90,004 + 90,005 + 90,006.
        self.assertEqual(qc['ytd']['GROSS'], 270015.0)

    def test_Z2b_figures_before_payobook_row_still_shown(self):
        self.load([['Code', 'Gross pay'], ['P5DXIA', '500000']], {2: 'y:gross'},
                  covers='2026-03-31', name='P5d Xia')
        _page, qc = self.summary(self.people['XIA'])
        # 3 month-end payslips 300,000 + 500,000 before Payobook.
        self.assertEqual(qc['ytd']['GROSS'], 800000.0)
        self.assertEqual(qc['ytd_opening'], {'GROSS': 500000.0})
        self.assertIn('31 Mar 2026', qc['ytd_opening_title'])

    def test_Z2c_unmatched_advance_shown_apart_not_added(self):
        page, qc = self.summary(self.people['WES'])
        self.assertEqual(page['ytd']['GROSS'], 170000.0, 'the page added both')
        self.assertEqual(qc['ytd']['GROSS'], 100000.0, 'the month-end payslip only')
        self.assertEqual(qc['ytd_advance_apart'], {'GROSS': 70000.0})
        self.assertTrue(any('shown apart' in w for w in qc['ytd_not_added'].values()))

    def test_Z2d_template_carries_the_new_parts(self):
        arch = self.env.ref('pb_updates.portal_my_taxsheet_ytd').arch
        for name in ('ytd_not_added', 'ytd_advance_apart', 'ytd_advance_note', 'ytd_opening_title'):
            self.assertIn(name, arch)

    # ================================================================ Z3
    def test_Z3_joiner_covered_from_joining_is_complete_and_delivered(self):
        row = self.view()[self.people['JOY'].id]
        gross, months = row['cells']['gross'], row['cells']['months']
        # May .. November: 7 x 100,000, nothing before Payobook.
        self.assertEqual((gross['before'], gross['paid'], gross['total']), (0.0, 700000.0, 700000.0))
        self.assertTrue(gross['year_total'])
        self.assertEqual(gross['joined_label'], 'Joined 1 May 2026 — Payobook payslips only')
        self.assertTrue(gross['note'].startswith('Joined 1 May 2026 — Payobook payslips only'))
        self.assertEqual(row['start_missing'], 0)
        self.assertEqual((months['paid'], months['total'], months['year_total']), (7.0, 7.0, True))
        self.assertTrue(months['joined_label'])
        self.assertEqual(row['cells']['tax']['total'], 70000.0, '7 x 10,000 as an amount')
        # "How this number was worked out" says so too.
        d = self.Upd.get_ytd_cell_detail(2026, self.people['JOY'].id, 'gross')
        self.assertTrue(d['ok'], d.get('msg'))
        self.assertEqual(d['joined_label'], 'Joined 1 May 2026 — Payobook payslips only')
        self.assertEqual(len(d['counted']), 7)
        self.assertTrue(d['year_total'])
        # The mapped pay items of a December payslip receive it.
        self.three_mappings()
        plan = self.plan('JOY')
        self.assertEqual(plan['GROSSYTD']['value'], 700000.0)
        self.assertEqual(plan['TAXYTD']['value'], 70000.0)
        self.assertEqual(plan['MONTHSYTD']['value'], 8.0, 'May .. November + December itself')
        self.assertEqual(plan['GROSSYTD']['joined'], '2026-05-01')
        self.assertFalse(any(self.Line._plan_blocked(i) for i in plan.values()))
        slip = self.december_slip('JOY')
        prov = {}
        values = slip._get_formula_input_values(self.monthly, provenance=prov)
        self.assertEqual(values['GROSSYTD'], 700000.0)
        self.assertEqual(values['MONTHSYTD'], 8.0)
        self.assertEqual(prov['GROSSYTD']['key'], 'updates_ytd:joined')
        self.assertEqual(prov['GROSSYTD']['ytd']['joined'], '2026-05-01')
        self.assertEqual((prov['GROSSYTD']['ytd']['before'], prov['GROSSYTD']['ytd']['paid']),
                         (0.0, 700000.0))
        # No figure row exists to hold, so nothing is locked.
        self.env['pb.updates.ytd.use'].sudo()._sync_slips(slip)
        self.assertFalse(self.env['pb.updates.ytd.use'].sudo().search([('payslip_id', '=', slip.id)]))
        # "Download for the pay run": the value, the sentence, an adjustment row.
        dl = self.Upd.download_for_payrun(self.monthly.id, '2026-12-01')
        self.assertTrue(dl['ok'], dl.get('msg'))
        wb = openpyxl.load_workbook(io.BytesIO(base64.b64decode(dl['file_b64'])))
        ws = wb.worksheets[0]
        heads = [c.value for c in ws[1]]
        joy = next(r for r in ws.iter_rows(min_row=2, values_only=True) if r[0] == 'P5DJOY')
        col = next(i for i, h in enumerate(heads) if h and '(GROSSYTD)' in h)
        self.assertEqual(joy[col], 700000.0)
        self.assertIn('Joined 1 May 2026 — Payobook payslips only', joy[-1])
        self.assertNotIn('No figures before Payobook', joy[-1])
        adj = [r for r in wb.worksheets[1].iter_rows(min_row=2, values_only=True)
               if r[0] == self.people['JOY'].id]
        self.assertEqual(len(adj), 3)
        self.assertTrue(all('joined 1 May 2026' in r[7] for r in adj))

    def test_Z3b_joining_in_this_pay_period(self):
        # PIA joins on 1 December: before this pay period there is nothing,
        # here or elsewhere — a known 0, and December is month 1.
        self.three_mappings()
        plan = self.plan('PIA')
        self.assertEqual(plan['GROSSYTD']['value'], 0.0)
        self.assertEqual(plan['MONTHSYTD']['value'], 1.0)
        # The same person in a November pay period has not joined: nothing.
        self.assertEqual(self.plan('PIA', '2026-11-01', '2026-11-30'), {})

    # ================================================================ Z4
    def test_Z4_anything_else_stays_as_before(self):
        rows = self.view()
        self.three_mappings()
        for code, why in (('KIM', 'June has no finished payslip'),
                          ('LEO', 'no joining date'),
                          ('MIA', 'joined last year'),
                          ('NED', 'the first payslip starts a month after joining')):
            row = rows[self.people[code].id]
            gross = row['cells']['gross']
            self.assertFalse(gross['year_total'], why)
            self.assertFalse(gross['joined_label'], why)
            self.assertFalse(row['cells']['months']['joined_label'], why)
            self.assertEqual(self.plan(code), {}, '%s: nothing reaches a pay run' % why)
            slip = self.december_slip(code)
            prov = {}
            values = slip._get_formula_input_values(self.monthly, provenance=prov)
            self.assertNotIn('updates_ytd', json.dumps(prov), why)
            self.assertIn(values.get('GROSSYTD'), (None, 0, 0.0, ''), why)
        # The P5c sentences stand.
        self.assertEqual(rows[self.people['KIM'].id]['missing'], 1)
        self.assertEqual(rows[self.people['LEO'].id]['start_missing'], 4, 'January to April')
        self.assertEqual(rows[self.people['MIA'].id]['start_missing'], 4)
        self.assertEqual(rows[self.people['NED'].id]['start_missing'], 1, 'May')
        dl = self.Upd.download_for_payrun(self.monthly.id, '2026-12-01')
        wb = openpyxl.load_workbook(io.BytesIO(base64.b64decode(dl['file_b64'])))
        for code in ('KIM', 'LEO', 'MIA', 'NED'):
            line = next(r for r in wb.worksheets[0].iter_rows(min_row=2, values_only=True)
                        if r[0] == 'P5D' + code)
            self.assertIn('No figures before Payobook for 2026', line[-1], code)
        adj = [r[0] for r in wb.worksheets[1].iter_rows(min_row=2, values_only=True)]
        for code in ('KIM', 'LEO', 'MIA', 'NED'):
            self.assertNotIn(self.people[code].id, adj, code)

    # ================================================================ Z5
    def test_Z5_joiner_with_figures_before_payobook_keeps_them(self):
        self.load([['Code', 'Gross pay'], ['P5DOLA', '50000']],
                  {2: 'y:gross'}, covers='2026-04-30', name='P5d Ola')
        gross = self.view()[self.people['OLA'].id]['cells']['gross']
        self.assertEqual((gross['before'], gross['paid'], gross['total']), (50000.0, 700000.0, 750000.0))
        self.assertTrue(gross['has_before'])
        self.assertFalse(gross['joined_label'], 'the figure row wins')
        self.mapping('GROSSYTD', 'gross')
        plan = self.plan('OLA')
        self.assertEqual(plan['GROSSYTD']['value'], 750000.0, '50,000 + May .. November')
        self.assertTrue(plan['GROSSYTD']['line_id'])
        self.assertNotIn('joined', plan['GROSSYTD'])

    def test_Z7_no_vendor_name_in_new_strings(self):
        texts = []
        for row in self.view().values():
            for c in row['cells'].values():
                texts += [c.get('note') or '', c.get('joined_label') or '']
        _page, qc = self.summary(self.people['WES'])
        texts += list(qc['ytd_not_added'].values()) + [qc['ytd_advance_note'],
                                                        qc['ytd_advance_apart_title']]
        self.assertFalse([t for t in texts if 'odoo' in t.lower()])
