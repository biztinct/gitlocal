# -*- coding: utf-8 -*-

import json

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrFullFinalSettlement(models.Model):
    _name = 'hr.full.final.settlement'
    _description = 'Full & Final Settlement'
    _order = 'settlement_date desc, employee_id'
    _sql_constraints = [
        (
            'full_final_unique_employee_date',
            'unique(employee_id, settlement_date)',
            'A Full and Final settlement already exists for this employee and date.',
        ),
    ]

    name = fields.Char(
        string='Reference',
        required=True,
        default=lambda self: _('New'),
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        ondelete='cascade',
    )
    employee_code = fields.Char(
        related='employee_id.employee_id',
        string='Employee ID',
        store=True,
        readonly=True,
    )
    department_id = fields.Many2one(
        related='employee_id.department_id',
        string='Department',
        store=True,
        readonly=True,
    )
    job_id = fields.Many2one(
        related='employee_id.job_id',
        string='Job Position',
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    contract_id = fields.Many2one(
        'hr.contract',
        string='Contract',
    )
    formula_config_id = fields.Many2one(
        'hr.formula.config',
        string='Salary Structure',
    )
    import_batch_id = fields.Many2one(
        'hr.payroll.import.batch',
        string='Payroll Batch',
    )
    settlement_date = fields.Date(
        string='Settlement Date',
        required=True,
    )
    settlement_month = fields.Char(
        string='Settlement Month',
        compute='_compute_settlement_month',
        store=True,
    )
    date_from = fields.Date(string='Period Start')
    date_to = fields.Date(string='Period End')
    source = fields.Selection(
        [('auto', 'Auto'), ('manual', 'Manual')],
        string='Source',
        default='auto',
        required=True,
    )
    raw_data_json = fields.Text(string='Source Data (JSON)')
    input_values_json = fields.Text(string='Input Values (JSON)')
    computed_values_json = fields.Text(string='Computed Values (JSON)')
    component_summary_json = fields.Text(
        string='Component Summary (JSON)',
        compute='_compute_component_summary',
        store=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    total_earnings = fields.Monetary(
        string='Total Earnings',
        compute='_compute_component_summary',
        store=True,
        currency_field='currency_id',
    )
    total_deductions = fields.Monetary(
        string='Total Deductions',
        compute='_compute_component_summary',
        store=True,
        currency_field='currency_id',
    )
    net_payable = fields.Monetary(
        string='Net Payable',
        compute='_compute_component_summary',
        store=True,
        currency_field='currency_id',
    )

    # ---- display-only breakdown (parsed from the summary JSON) for the WOW form ----
    c_basic = fields.Monetary(string='Basic salary', compute='_compute_breakdown', currency_field='currency_id')
    c_allow = fields.Monetary(string='Allowances', compute='_compute_breakdown', currency_field='currency_id')
    c_ot = fields.Monetary(string='Overtime', compute='_compute_breakdown', currency_field='currency_id')
    c_bonus = fields.Monetary(string='Bonus', compute='_compute_breakdown', currency_field='currency_id')
    c_leave = fields.Monetary(string='Unused leave', compute='_compute_breakdown', currency_field='currency_id')
    c_other_earn = fields.Monetary(string='Other earnings', compute='_compute_breakdown', currency_field='currency_id')
    c_pit = fields.Monetary(string='Personal income tax', compute='_compute_breakdown', currency_field='currency_id')
    c_si = fields.Monetary(string='Social insurance', compute='_compute_breakdown', currency_field='currency_id')
    c_hi = fields.Monetary(string='Health insurance', compute='_compute_breakdown', currency_field='currency_id')
    c_ui = fields.Monetary(string='Unemployment insurance', compute='_compute_breakdown', currency_field='currency_id')
    c_loan = fields.Monetary(string='Loan / advance', compute='_compute_breakdown', currency_field='currency_id')
    c_other_ded = fields.Monetary(string='Other deductions', compute='_compute_breakdown', currency_field='currency_id')

    _BREAKDOWN_KEYS = {
        'c_basic': 'basic_salary', 'c_allow': 'allowances', 'c_ot': 'overtime', 'c_bonus': 'bonus',
        'c_leave': 'unused_leave', 'c_other_earn': 'other_earnings', 'c_pit': 'personal_income_tax',
        'c_si': 'social_insurance', 'c_hi': 'health_insurance', 'c_ui': 'unemployment_insurance',
        'c_loan': 'loan_advance', 'c_other_ded': 'other_deductions',
    }

    @api.depends('component_summary_json')
    def _compute_breakdown(self):
        for rec in self:
            try:
                s = json.loads(rec.component_summary_json or '{}')
            except (json.JSONDecodeError, TypeError):
                s = {}
            for fname, key in self._BREAKDOWN_KEYS.items():
                rec[fname] = s.get(key, 0.0)

    def action_download_full_and_final(self):
        self.ensure_one()
        return self.env.ref('pb_hr_fullandfinal.action_report_full_and_final').report_action(self)

    def get_component_summary(self):
        self.ensure_one()
        try:
            return json.loads(self.component_summary_json or '{}')
        except json.JSONDecodeError:
            return {}

    @api.depends('settlement_date')
    def _compute_settlement_month(self):
        for record in self:
            if record.settlement_date:
                record.settlement_month = record.settlement_date.strftime('%m/%Y')
            else:
                record.settlement_month = ''

    @api.depends('computed_values_json', 'formula_config_id')
    def _compute_component_summary(self):
        for record in self:
            components = record._build_component_summary()
            record.component_summary_json = json.dumps(components)
            record.total_earnings = components.get('total_earnings', 0.0)
            record.total_deductions = components.get('total_deductions', 0.0)
            record.net_payable = components.get('net_payable', 0.0)

    @api.model
    def _compute_from_config(self, config, employee, contract, raw_data=None):
        if not config:
            raise UserError(_("No salary structure selected for full and final computation."))
        raw_data = raw_data or {}
        batch_helper = self.env['hr.payroll.import.batch'].new({
            'formula_config_id': config.id,
            'company_id': employee.company_id.id,
        })
        input_values = batch_helper._transform_data_to_formula_inputs(raw_data, contract, employee)
        rules = config.rule_ids.sorted(key=lambda r: r.sequence)
        payslip = self.env['hr.payslip'].new({
            'employee_id': employee.id,
            'contract_id': contract.id if contract else False,
            'company_id': employee.company_id.id,
        })
        computed_values, _log = payslip._evaluate_rules_with_dependencies(rules, input_values)
        return input_values, computed_values

    def _build_component_summary(self):
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

        if not self.formula_config_id or not self.computed_values_json:
            return components

        try:
            computed_values = json.loads(self.computed_values_json or '{}')
        except json.JSONDecodeError:
            return components

        rules = self.formula_config_id.rule_ids

        class _Line:
            def __init__(self, code, total, category_id):
                self.code = code
                self.total = total
                self.category_id = category_id

        def normalize_code(code):
            if not code:
                return ''
            return ''.join(ch for ch in code if ch.isalnum()).upper()

        def coerce_amount(value):
            if value is None:
                return None
            if isinstance(value, bool):
                return float(value)
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                cleaned = value.strip().replace(' ', '')
                if not cleaned:
                    return None
                is_percent = False
                if cleaned.endswith('%'):
                    cleaned = cleaned[:-1]
                    is_percent = True
                try:
                    if ',' in cleaned and '.' in cleaned:
                        if cleaned.rfind(',') > cleaned.rfind('.'):
                            cleaned = cleaned.replace('.', '').replace(',', '.')
                        else:
                            cleaned = cleaned.replace(',', '')
                    elif ',' in cleaned:
                        parts = cleaned.split(',')
                        if all(len(p) == 3 for p in parts[1:]):
                            cleaned = ''.join(parts)
                        else:
                            cleaned = cleaned.replace(',', '.')
                    elif '.' in cleaned:
                        parts = cleaned.split('.')
                        if len(parts) > 2 and all(len(p) == 3 for p in parts[1:]):
                            cleaned = ''.join(parts)
                    number = float(cleaned)
                    if is_percent:
                        number = number / 100
                    return number
                except ValueError:
                    return None
            return None

        def is_net_line(line):
            code = normalize_code(line.code)
            category_code = normalize_code(line.category_id.code if line.category_id else '')
            return code == 'NET' or category_code == 'NET'

        def is_deduction_line(line):
            category_code = normalize_code(line.category_id.code if line.category_id else '')
            if category_code in {'DED', 'DEDUCTION', 'TAX', 'LOAN', 'ADV'}:
                return True
            return line.total < 0

        def match_line(line, codes=None, prefixes=None):
            code = normalize_code(line.code)
            if not code:
                return False
            if codes and code in codes:
                return True
            if prefixes:
                return any(code.startswith(prefix) for prefix in prefixes)
            return False

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

        matched_codes = set()
        for rule in rules:
            value = computed_values.get(rule.code)
            if value is None and rule.column_letter:
                value = computed_values.get(rule.column_letter)
            amount = coerce_amount(value)
            if amount is None:
                continue
            line = _Line(
                rule.code,
                amount,
                rule.category_id or rule.salary_rule_id.category_id,
            )
            if is_net_line(line):
                continue
            for key, codes, prefixes in match_specs:
                if match_line(line, codes, prefixes):
                    components[key] += abs(line.total)
                    matched_codes.add(rule.code)
                    break

        for rule in rules:
            value = computed_values.get(rule.code)
            if value is None and rule.column_letter:
                value = computed_values.get(rule.column_letter)
            amount = coerce_amount(value)
            if amount is None:
                continue
            line = _Line(
                rule.code,
                amount,
                rule.category_id or rule.salary_rule_id.category_id,
            )
            if is_net_line(line) or rule.code in matched_codes:
                continue
            if is_deduction_line(line):
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
