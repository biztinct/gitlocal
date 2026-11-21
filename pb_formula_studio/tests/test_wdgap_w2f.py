# -*- coding: utf-8 -*-
"""WDGAP W2-F — Formula Studio: "Tax year starts in" on the Health tab (F-4)
and the older offer calculator's Earnings / Deductions boxes (F-5).
Handover `docs/handovers/wdgap/WDGAP_W2_F_HANDOVER.md` §F-4, §F-5.

  F4.1  the Health tab's payload carries the field: the scheme form's label,
        help and twelve months, the saved month, whether it may be changed;
  F4.2  no finished payslips: a change is saved at once, through the
        scheme's own write of the field the form tracks;
  F4.3  finished payslips: the first press answers with the scheme form's
        own warning and saves nothing; "Change it" saves;
  F4.4  a month that is not a month, the same month, and a login that may
        not change the scheme are answered plainly — nothing written;
  F5.1  the offer calculator shows Earnings and Deductions again (the cause:
        bare in-memory lines that belong to no payslip add up to 0 wherever
        pb_payruns is installed — ledger W2C-1); nothing is saved;
  F5.2  every box once: gross is not counted beside its own parts.
"""
from unittest.mock import patch

from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install', 'wdgap_w2f')
class TestW2fStudio(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.formula.studio']
        cls.cfg = cls.env['hr.formula.config'].create({
            'name': 'W2F Studio scheme', 'code': 'WTWOFS', 'country_code': 'VN',
            'state': 'active', 'company_id': cls.env.company.id})
        basic = cls._rule('BASICPAY', 'Basic pay', 'input', role='earning', seq=10)
        b = basic.column_letter
        cls._rule('GROSSPAY', 'Gross pay', 'formula', '=%s' % b, role='earning', seq=15)
        cls.tax = cls._rule('PITAX', 'Income tax', 'formula', '=%s*0.1' % b,
                            role='deduction', seq=20)
        cls._rule('ERSOC', 'Employer social insurance', 'formula', '=%s*0.2' % b,
                  role='employer_cost', seq=25)
        cls._rule('NETPAY', 'Take-home', 'formula', '=%s-%s' % (b, cls.tax.column_letter),
                  role='net', seq=30)

    @classmethod
    def _rule(cls, code, name, kind, formula=None, role=False, seq=10):
        vals = {'config_id': cls.cfg.id, 'code': code, 'name': name,
                'column_type': kind, 'sequence': seq, 'appears_on_payslip': True,
                'net_role': role, 'default_value': 0.0}
        if formula:
            vals['excel_formula'] = formula
        return cls.env['hr.formula.rule'].create(vals)

    # ============================================================ F-4
    def test_F4_1_the_health_tab_carries_the_field(self):
        ty = self.Studio.get_config_settings(self.cfg.id)['tax_year']
        self.assertEqual(ty['label'], 'Tax year starts in')
        self.assertEqual(ty['month'], '1')
        self.assertEqual(len(ty['options']), 12)
        self.assertEqual(ty['options'][3], ['4', 'April'])
        self.assertTrue(ty['help'])
        self.assertTrue(ty['can_edit'])
        self.assertNotIn('Odoo', str(ty))

    def test_F4_2_no_finished_payslips_saves_at_once(self):
        Config = type(self.cfg)
        calls = []
        real_write = Config.write

        def spy(recs, vals):
            calls.append(dict(vals))
            return real_write(recs, vals)
        with patch.object(Config, 'write', spy):
            r = self.Studio.save_tax_year_start(self.cfg.id, '4')
        self.assertTrue(r['ok'], r)
        self.assertEqual(self.cfg.tax_year_start_month, '4')
        self.assertEqual(r['tax_year']['month'], '4')
        # the scheme's own write, the field the form tracks — the form's path
        self.assertIn({'tax_year_start_month': '4'}, calls)
        self.assertTrue(self.cfg._fields['tax_year_start_month'].tracking)
        self.assertEqual(r['msg'], 'The tax year now starts in April.')

    def test_F4_3_finished_payslips_ask_first(self):
        emp = self.env['hr.employee'].create({'name': 'W2F Tia'})
        slip = self.env['hr.payslip'].create({
            'name': 'W2F Tia', 'employee_id': emp.id, 'formula_config_id': self.cfg.id,
            'date_from': '2026-03-01', 'date_to': '2026-03-31'})
        slip.write({'state': 'done'})
        warning = self.cfg._pb_tax_year_change_warning('4')
        self.assertTrue(warning)
        r = self.Studio.save_tax_year_start(self.cfg.id, '4')
        self.assertFalse(r['ok'])
        self.assertTrue(r['needs_confirm'])
        self.assertEqual(r['warning'], warning, "the scheme form's own words")
        self.assertEqual(self.cfg.tax_year_start_month, '1', 'nothing saved yet')
        r = self.Studio.save_tax_year_start(self.cfg.id, '4', True)
        self.assertTrue(r['ok'], r)
        self.assertEqual(self.cfg.tax_year_start_month, '4')

    def test_F4_4_plain_refusals(self):
        self.assertEqual(self.Studio.save_tax_year_start(self.cfg.id, '13')['msg'],
                         'Pick a month.')
        self.assertTrue(self.Studio.save_tax_year_start(self.cfg.id, '1')['unchanged'])
        self.assertFalse(self.Studio.save_tax_year_start(0, '4')['ok'])
        reader = new_test_user(self.env, login='w2f_reader', groups='base.group_user')
        Studio = self.Studio.with_user(reader)
        try:
            r = Studio.save_tax_year_start(self.cfg.id, '4')
        except Exception:       # noqa: BLE001 — a refusal by the rights layer is fine too
            r = {'ok': False}
        self.assertFalse(r['ok'])
        self.cfg.invalidate_recordset()
        self.assertEqual(self.cfg.tax_year_start_month, '1')

    # ============================================================ F-5
    def test_F5_1_offer_calculator_shows_earnings_and_deductions(self):
        Slip, Line = self.env['hr.payslip'], self.env['hr.payslip.line']
        counts = (Slip.search_count([]), Line.search_count([]))
        r = self.Studio.offer_calc(self.cfg.id, {'BASICPAY': 10_000_000})
        self.assertTrue(r['ok'], r)
        boxes = {s['group']: s['value'] for s in r['subtotals']}
        self.assertIn('Earnings', boxes, r['subtotals'])
        self.assertIn('Deductions', boxes, r['subtotals'])
        self.assertAlmostEqual(boxes['Earnings'], 10_000_000)
        self.assertAlmostEqual(abs(boxes['Deductions']), 1_000_000)
        self.assertAlmostEqual(r['net_value'], 9_000_000)
        self.assertEqual(counts, (Slip.search_count([]), Line.search_count([])),
                         'the calculator saved something')

    def test_F5_2_every_box_once(self):
        r = self.Studio.offer_calc(self.cfg.id, {'BASICPAY': 7_000_000})
        boxes = {s['group']: abs(s['value']) for s in r['subtotals']}
        self.assertEqual(len(r['subtotals']), 3, r['subtotals'])
        self.assertAlmostEqual(boxes['Earnings'], 7_000_000, msg='gross counted once')
        self.assertAlmostEqual(boxes['Deductions'], 700_000)
        employer = [v for k, v in boxes.items() if k not in ('Earnings', 'Deductions')]
        self.assertEqual(employer, [1_400_000])
