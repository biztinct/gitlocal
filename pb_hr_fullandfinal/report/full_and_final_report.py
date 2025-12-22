# -*- coding: utf-8 -*-

from odoo import api, models


class ReportFullAndFinal(models.AbstractModel):
    _name = 'report.pb_hr_fullandfinal.report_full_and_final_document'
    _description = 'Full and Final Report'

    def _normalize_code(self, code):
        if not code:
            return ''
        return ''.join(ch for ch in code if ch.isalnum()).upper()

    def _is_net_line(self, line):
        code = self._normalize_code(line.code)
        category_code = self._normalize_code(line.category_id.code if line.category_id else '')
        return code == 'NET' or category_code == 'NET'

    def _is_deduction_line(self, line):
        category_code = self._normalize_code(line.category_id.code if line.category_id else '')
        if category_code in {'DED', 'DEDUCTION', 'TAX', 'LOAN', 'ADV'}:
            return True
        return line.total < 0

    def _match_line(self, line, codes=None, prefixes=None):
        code = self._normalize_code(line.code)
        if not code:
            return False
        if codes and code in codes:
            return True
        if prefixes:
            return any(code.startswith(prefix) for prefix in prefixes)
        return False

    def _compute_components(self, payslip):
        components = {
            'basic_salary': 0.0,
            'allowances': 0.0,
            'overtime': 0.0,
            'bonus': 0.0,
            'unused_leave': 0.0,
            'other_earnings': 0.0,
            'total_earnings': 0.0,
            'personal_income_tax': 0.0,
            'social_insurance': 0.0,
            'health_insurance': 0.0,
            'unemployment_insurance': 0.0,
            'loan_advance': 0.0,
            'other_deductions': 0.0,
            'total_deductions': 0.0,
            'net_payable': 0.0,
        }
        if not payslip:
            return components

        match_specs = [
            ('basic_salary',
             {'BASIC', 'BASICSALARY', 'SALARY', 'WAGE', 'ACTBASE', 'ACTBASIC', 'BASICPAY', 'BASICSAL'},
             {'BASIC', 'SALARY', 'WAGE', 'ACTBASE'}),
            ('allowances',
             {'ALW', 'ALLOW', 'ALLOWANCE', 'ALLOWANCES', 'ACTGAZ', 'ACTPHONE', 'ACTMEAL', 'ACTRESP',
              'ACTPARK', 'ACTTAXI', 'GAS', 'PHONE', 'MEAL', 'RESP', 'PARK', 'TAXI', 'TRANSPORT', 'COMM', 'HRA'},
             {'ALW', 'ALLOW'}),
            ('overtime',
             {'OT', 'OT15', 'OT2', 'OT3', 'OTNW', 'OTNO', 'OTNH', 'OVERTIME', 'OTNS', 'OTNSWEEK',
              'OTNSOFF', 'OTNSHOL', 'OVT'},
             {'OT'}),
            ('bonus',
             {'BONUS', 'BON', 'BNS', 'THIRTEENTH', '13TH', 'TET', 'ANNUALBONUS'},
             {'BONUS'}),
            ('unused_leave',
             {'LEAVE', 'LEAVEENCASH', 'LEAVEENCASHMENT', 'LEAVEENC', 'LEAVEPAY', 'UNUSEDLEAVE', 'UNUSED_LEAVE'},
             {'LEAVE'}),
            ('personal_income_tax',
             {'PIT', 'TAX', 'TAXIN', 'TAXINAD', 'MONPIT', 'PITAX', 'MONTHLYPIT', 'PERSONALTAX'},
             {'PIT', 'TAX'}),
            ('social_insurance',
             {'SI', 'SOC', 'SOCIAL', 'SOCIALINS', 'SOCSEVEN', 'SIEIGHT', 'SIHIUIT', 'SIHIUITEN'},
             {'SI', 'SOC'}),
            ('health_insurance',
             {'HI', 'HEALTH', 'MED', 'MEDTHREE', 'MIONEFIVE', 'BHYT'},
             {'HI', 'MED', 'BHYT'}),
            ('unemployment_insurance',
             {'UI', 'UNEMP', 'UNONE', 'UIONE', 'BHTN'},
             {'UI', 'UNEMP', 'BHTN'}),
            ('loan_advance',
             {'LOAN', 'ADV', 'ADVANCE', 'TAMUNG', 'TAM_UNG'},
             {'LOAN', 'ADV', 'TAM'}),
        ]

        matched_ids = set()
        for line in payslip.line_ids:
            if self._is_net_line(line):
                continue
            for key, codes, prefixes in match_specs:
                if self._match_line(line, codes, prefixes):
                    components[key] += abs(line.total)
                    matched_ids.add(line.id)
                    break

        for line in payslip.line_ids:
            if self._is_net_line(line) or line.id in matched_ids:
                continue
            if self._is_deduction_line(line):
                components['other_deductions'] += abs(line.total)
            else:
                components['other_earnings'] += abs(line.total)

        components['total_earnings'] = (
            components['basic_salary']
            + components['allowances']
            + components['overtime']
            + components['bonus']
            + components['unused_leave']
            + components['other_earnings']
        )
        components['total_deductions'] = (
            components['personal_income_tax']
            + components['social_insurance']
            + components['health_insurance']
            + components['unemployment_insurance']
            + components['loan_advance']
            + components['other_deductions']
        )
        components['net_payable'] = components['total_earnings'] - components['total_deductions']
        return components

    @api.model
    def _get_report_values(self, docids, data=None):
        employees = self.env['hr.employee'].browse(docids)
        vnd_currency = self.env['res.currency'].search([('name', '=', 'VND')], limit=1)
        payslip_data = {}
        for employee in employees:
            payslip = self.env['hr.payslip'].search(
                [('employee_id', '=', employee.id)],
                order='date_to desc',
                limit=1,
            )
            components = self._compute_components(payslip)
            settlement_date = employee.departure_date or (payslip.date_to if payslip else False)
            settlement_month = ''
            if settlement_date:
                settlement_month = settlement_date.strftime('%m/%Y')
            payslip_data[employee.id] = {
                'payslip': payslip,
                'components': components,
                'currency': vnd_currency or employee.company_id.currency_id,
                'settlement_month': settlement_month,
            }
        return {
            'doc_ids': employees.ids,
            'doc_model': 'hr.employee',
            'docs': employees,
            'payslip_data': payslip_data,
        }
