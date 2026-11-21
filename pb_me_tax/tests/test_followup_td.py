# -*- coding: utf-8 -*-
"""WDGAP S2-D follow-up — owner rulings TD1–TD3 and the label-free
dependants lookup (numbered TD1.x, TD2.x, TD3.x, DL.x in the report)."""
import json
from datetime import date, timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import TaxCase, decide


@tagged('post_install', '-at_install', 'wdgap_s2d')
class TestS2dFollowUp(TaxCase):

    def _needs(self, emp=None, user=None):
        put = {}
        self.env['pb.me.home'].with_user(user or self.portal).sudo()._pbme_needs_extra(
            (emp or self.emp).sudo(), lambda key, n, url, **kw: put.setdefault(key, (n, url, kw)))
        return put

    # ================================================================ TD1
    def test_td1_1_reminder_when_no_tax_number(self):
        for code in ('VN', 'ID', 'IN'):
            self._pay_by(self.emp, code)
            put = self._needs()
            self.assertIn('tax_number_missing', put, code)
            n, url, kw = put['tax_number_missing']
            self.assertEqual((n, url), (1, '/my/tax'))
            self.assertEqual(kw['label'], 'Add your tax number')

    def test_td1_2_no_reminder_where_no_number_is_kept(self):
        for code in ('SG', 'MY'):
            self._pay_by(self.emp, code)
            self.assertNotIn('tax_number_missing', self._needs(), code)

    def test_td1_3_gone_once_on_file_or_waiting(self):
        self._pay_by(self.emp, 'VN')
        req = self._ask('tax_number', {'t_number': '0312345678'}, upload=self._pdf())
        self.assertNotIn('tax_number_missing', self._needs(), 'waiting for HR')
        decide(self.env, req, 'return', 'Unreadable')
        put = self._needs()
        self.assertNotIn('tax_number_missing', put, 'the sent-back row covers it')
        self.assertIn('tax_sent_back', put)
        self._ask('tax_number', {'t_number': '0312345678'}, request_id=req.id)
        decide(self.env, req)
        self.assertEqual(self.emp.sudo().vietnam_tax_code, '0312345678')
        self.assertNotIn('tax_number_missing', self._needs(), 'on file')
        # taken back before HR decided: the reminder comes back
        self._pay_by(self.emp, 'IN')
        req2 = self._ask('tax_number', {'t_number': 'ABCDE1234F'}, upload=self._pdf())
        self.assertNotIn('tax_number_missing', self._needs())
        req2.with_user(self.portal).pb_portal_withdraw()
        self.assertIn('tax_number_missing', self._needs())

    def test_td1_4_no_email_and_on_the_home_page(self):
        Mail = self.env['mail.mail'].sudo()
        before = Mail.search_count([])
        self._pay_by(self.emp, 'ID')
        data = self.env['pb.me.home'].with_user(self.portal).get_home_data(self.emp)
        keys = [row.get('key') for row in data['needs_you']]
        self.assertIn('tax_number_missing', keys)
        self.assertEqual(Mail.search_count([]), before, 'nothing is emailed')

    # ================================================================ TD2
    def test_td2_uan_and_residency_cannot_be_proposed(self):
        # no kind exists for them: a crafted kind is refused
        for kind in ('tax_uan', 'tax_residency', 'pb_in_uan_number'):
            with self.assertRaises(UserError, msg=kind):
                self._ask(kind, {'t_number': '100200300400'}, upload=self._pdf())
        # crafted extra values on an offered kind are ignored, never written
        self._pay_by(self.emp, 'IN')
        self.emp.sudo().write({'pb_in_uan_number': '100200300400'})
        req = self._ask('tax_number', {'t_number': 'ABCDE1234F',
                                       'pb_in_uan_number': '999999999999',
                                       't_uan': '999999999999'}, upload=self._pdf())
        decide(self.env, req)
        self.assertEqual(self.emp.sudo().pb_in_uan_number, '100200300400')
        self._pay_by(self.emp, 'SG')
        self.emp.sudo().write({'pb_sg_tax_residency': 'resident'})
        req = self._ask('tax_fund', {'t_fund': 'sinda',
                                     'pb_sg_tax_residency': 'non_resident',
                                     't_residency': 'non_resident'})
        decide(self.env, req)
        self.assertEqual(self.emp.sudo().pb_sg_tax_residency, 'resident')
        self.assertEqual(self.emp.sudo().pb_sg_shg_fund, 'sinda')
        # shown read-only: no change link, "Kept by HR", masked number
        for code, key in (('IN', 'uan'), ('SG', 'residency')):
            self._pay_by(self.emp, code)
            rows = {r['key']: r for r in
                    self.emp.with_user(self.portal).sudo()._pbtx_portal_data()['rows']}
            self.assertIsNone(rows[key]['kind'], key)
            self.assertEqual(rows[key]['hint'], 'Kept by HR')
        self._pay_by(self.emp, 'IN')
        rows = {r['key']: r for r in
                self.emp.with_user(self.portal).sudo()._pbtx_portal_data()['rows']}
        self.assertEqual(rows['uan']['value'], '•••• 0400')

    # ================================================================ TD3
    def _contract(self, state='open', start='2026-01-01', end=False, code=False):
        vals = {'name': 'DEMO S2D TD3 %s %s' % (state, start), 'employee_id': self.emp.id,
                'company_id': self.company.id, 'wage': 10_000_000.0,
                'state': state, 'date_start': start, 'date_end': end}
        if code is not False:
            vals['vietnam_tax_code'] = code
        return self.env['hr.contract'].sudo().create(vals)

    def test_td3_1_current_contract_copy_updated_past_untouched(self):
        past = self._contract(state='close', start='2024-01-01', end='2025-12-31',
                              code='0300000001')
        current = self._contract(code='0300000001')
        self._pay_by(self.emp, 'VN')
        n_msgs = len(current.message_ids)
        req = self._ask('tax_number', {'t_number': '0312345678'}, upload=self._pdf())
        self.assertEqual(current.vietnam_tax_code, '0300000001', 'nothing before approval')
        decide(self.env, req)
        self.assertEqual(self.emp.sudo().vietnam_tax_code, '0312345678')
        self.assertEqual(current.vietnam_tax_code, '0312345678')
        self.assertEqual(past.vietnam_tax_code, '0300000001', 'a past contract is never changed')
        new = current.message_ids[:len(current.message_ids) - n_msgs]
        bodies = ' '.join(new.mapped('body'))
        self.assertIn('•••• 5678', bodies)
        self.assertNotIn('0312345678', bodies, 'the chatter never shows the full number')
        self.assertNotIn('0312345678', ' '.join(
            current.message_ids.mapped('tracking_value_ids.new_value_char') or ['']))

    def test_td3_2_future_or_ended_contract_not_written(self):
        today = fields.Date.context_today(self.env.user)
        future = self._contract(start=str(today + timedelta(days=30)), code='')
        ended = self._contract(start='2025-01-01', end=str(today - timedelta(days=1)),
                               code='')
        self._pay_by(self.emp, 'VN')
        req = self._ask('tax_number', {'t_number': '0312345678'}, upload=self._pdf())
        decide(self.env, req)
        self.assertEqual(self.emp.sudo().vietnam_tax_code, '0312345678')
        self.assertFalse(future.vietnam_tax_code)
        self.assertFalse(ended.vietnam_tax_code)

    def test_td3_3_other_countries_never_touch_the_contract(self):
        current = self._contract(code='0300000001')
        self._pay_by(self.emp, 'ID')
        req = self._ask('tax_number', {'t_number': '092542943407000'}, upload=self._pdf())
        decide(self.env, req)
        self.assertEqual(current.vietnam_tax_code, '0300000001')

    def test_td3_4_payslip_identical_after_the_contract_copy(self):
        category = self.env['hr.salary.rule.category'].search([], limit=1)
        current = self._contract(code='0300000001')
        cfg = self.env['hr.formula.config'].sudo().create({
            'name': 'DEMO S2D TD3 scheme', 'code': 'TDTHREEVN', 'cycle_type': 'end_cycle',
            'country_code': 'VN', 'company_id': self.company.id, 'state': 'active'})
        Rule = self.env['hr.formula.rule'].sudo()
        base = {'config_id': cfg.id, 'default_value': 0.0, 'appears_on_payslip': True,
                'category_id': category.id}
        Rule.create(dict(base, name='Basic', code='BASIC', column_type='input', sequence=1,
                         value_kind='money', net_role='earning'))
        Rule.create(dict(base, name='Allowance', code='TDALLOW', column_type='input',
                         sequence=2, value_kind='money', net_role='earning',
                         default_value=300_000.0))
        Rule.create(dict(base, name='Net', code='TDNET', column_type='formula', sequence=10,
                         value_kind='money', net_role='net', excel_formula='=BASIC+TDALLOW'))
        slip = self.env['hr.payslip'].sudo().create({
            'name': 'DEMO S2D TD3', 'employee_id': self.emp.id, 'contract_id': current.id,
            'date_from': date(2026, 6, 1), 'date_to': date(2026, 6, 30),
            'company_id': self.company.id, 'formula_config_id': cfg.id,
            'calculation_method': 'formula'})

        def snap():
            slip.compute_sheet()
            slip.invalidate_recordset()
            return json.dumps({
                'inputs': json.loads(slip.formula_input_values or '{}'),
                'computed': json.loads(slip.formula_computed_values or '{}'),
                'lines': sorted((l.code, l.amount, l.total) for l in slip.line_ids),
            }, sort_keys=True, default=str)
        before = snap()
        self.assertIn('TDNET', before)
        self._pay_by(self.emp, 'VN')
        req = self._ask('tax_number', {'t_number': '0312345678'}, upload=self._pdf())
        decide(self.env, req)
        self.assertEqual(current.vietnam_tax_code, '0312345678')
        self.assertEqual(snap(), before)

    # ===================================== DL — lookup by code, not by label
    def _component(self, contract, code, amount, name):
        Template = self.env['hr.contract.advantage.template'].sudo()
        tpl = Template.search([('code', '=', code)], limit=1) or Template.create(
            {'name': name, 'code': code, 'lower_bound': 0, 'upper_bound': 20})
        contract.advantages_ids.filtered(lambda a: a.advantage_template_id == tpl).unlink()
        return self.env['hr.contract.advantage'].sudo().create(
            {'contract_id': contract.id, 'advantage_template_id': tpl.id, 'amount': amount})

    def _two_confirmed(self):
        Dep = self.env['vietnam.employee.dependent'].sudo()
        for name in ('DEMO Child C', 'DEMO Child D'):
            Dep.create({'employee_id': self.emp.id, 'name': name, 'relationship': 'child',
                        'status': 'eligible', 'effective_from': '2025-01-01'})
        self.emp.invalidate_recordset()

    def test_dl_1_any_label_and_the_starter_code(self):
        contract = self._contract()
        self._two_confirmed()
        # the starter scheme's / demo code, with a label nobody at Rize uses
        self._component(contract, 'DEPS', 3, 'Số người phụ thuộc đăng ký')
        self.emp.invalidate_recordset()
        self.assertIn('3', self.emp.with_user(self.hr).pb_vn_dependants_check or '')
        # the first code in the setting wins when a contract carries two
        self._component(contract, 'VNREGISTER', 2, 'Anything at all')
        self.emp.invalidate_recordset()
        self.assertFalse(self.emp.with_user(self.hr).pb_vn_dependants_check)

    def test_dl_2_setting_names_another_code_and_unknown_codes_show_nothing(self):
        contract = self._contract()
        self._two_confirmed()
        self._component(contract, 'SDMDEP', 1, 'Registered dependants')
        self.emp.invalidate_recordset()
        self.assertFalse(self.emp.with_user(self.hr).pb_vn_dependants_check,
                         'an unknown code is not guessed from its label')
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_me_tax.vn_registered_dependants_codes', 'SDMDEP')
        self.emp.invalidate_recordset()
        self.assertIn('1', self.emp.with_user(self.hr).pb_vn_dependants_check or '')

    def test_dl_3_a_past_contract_is_not_compared(self):
        past = self._contract(state='close', start='2024-01-01', end='2025-12-31')
        self._two_confirmed()
        self._component(past, 'VNREGISTER', 5, 'Registered tax dependents')
        self.emp.invalidate_recordset()
        self.assertFalse(self.emp.with_user(self.hr).pb_vn_dependants_check)
