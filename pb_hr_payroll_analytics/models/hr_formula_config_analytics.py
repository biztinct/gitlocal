# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import json
import logging

_logger = logging.getLogger(__name__)


class HrFormulaConfigAnalytics(models.Model):
    """
    Salary Structure/Formula Config Analytics Dashboard
    Provides financial analysis across Company > Salary Configs > Departments hierarchy
    """
    _name = 'hr.formula.config.analytics'
    _description = 'Salary Structure Analytics Dashboard'
    _order = 'id DESC'

    # ============================================================================
    # DASHBOARD STATE & NAVIGATION
    # ============================================================================

    name = fields.Char(
        string='Dashboard Name',
        default='Salary Structure Analytics',
        readonly=True
    )

    active_view = fields.Selection([
        ('hierarchy', 'Hierarchy Home'),
        ('consolidated', 'Consolidated View'),
        ('config_detail', 'Config Detail'),
        ('department_detail', 'Department Detail')
    ], default='hierarchy', string='Active View')

    # ============================================================================
    # FILTERS
    # ============================================================================

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    company_currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        readonly=True
    )

    selected_config_id = fields.Many2one(
        'hr.formula.config',
        string='Selected Salary Config',
        domain="[('company_id', '=', company_id), ('state', '=', 'active')]"
    )

    selected_department_id = fields.Many2one(
        'hr.department',
        string='Selected Department'
    )

    period_type = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly')
    ], default='monthly', string='Period Type')

    date_from = fields.Date(
        string='Date From',
        default=lambda self: fields.Date.today().replace(day=1)
    )

    date_to = fields.Date(
        string='Date To',
        default=fields.Date.today
    )

    # ============================================================================
    # COMPUTED SUMMARY STATS (Header KPIs)
    # ============================================================================

    total_configs = fields.Integer(
        compute='_compute_summary_stats',
        string='Total Configs'
    )

    total_departments = fields.Integer(
        compute='_compute_summary_stats',
        string='Total Departments'
    )

    total_employees = fields.Integer(
        compute='_compute_summary_stats',
        string='Total Employees'
    )

    total_gross_pay = fields.Monetary(
        compute='_compute_summary_stats',
        string='Total Gross Pay',
        currency_field='company_currency_id'
    )

    total_net_pay = fields.Monetary(
        compute='_compute_summary_stats',
        string='Total Net Pay',
        currency_field='company_currency_id'
    )

    total_deductions = fields.Monetary(
        compute='_compute_summary_stats',
        string='Total Deductions',
        currency_field='company_currency_id'
    )

    total_employer_cost = fields.Monetary(
        compute='_compute_summary_stats',
        string='Total Employer Cost',
        currency_field='company_currency_id'
    )

    # ============================================================================
    # HIERARCHY DATA (JSON for JavaScript rendering)
    # ============================================================================

    hierarchy_data_json = fields.Text(
        compute='_compute_hierarchy_data',
        string='Hierarchy Data (JSON)'
    )

    consolidated_data_json = fields.Text(
        compute='_compute_consolidated_data',
        string='Consolidated Data (JSON)'
    )

    config_detail_data_json = fields.Text(
        compute='_compute_config_detail_data',
        string='Config Detail Data (JSON)'
    )

    department_detail_data_json = fields.Text(
        compute='_compute_department_detail_data',
        string='Department Detail Data (JSON)'
    )

    # ============================================================================
    # CACHE & STATE
    # ============================================================================

    last_refresh = fields.Datetime(
        string='Last Refresh',
        readonly=True
    )

    # ============================================================================
    # HELPER METHODS
    # ============================================================================

    def _get_component_category_type(self, line):
        """Get category type for a payslip line"""
        # Primary: Use category_id.category_type if defined
        if line.category_id and line.category_id.category_type:
            return line.category_id.category_type

        # Fallback: Code pattern matching
        code_upper = (line.code or '').upper()
        if any(x in code_upper for x in ['BASIC', 'BASE', 'WAGE']):
            return 'basic'
        elif 'GROSS' in code_upper:
            return 'allowance'
        elif 'NET' in code_upper and 'GROSS' not in code_upper:
            return 'net'
        elif any(x in code_upper for x in ['TAX', 'PIT']):
            return 'tax'
        elif any(x in code_upper for x in ['DEDUCT']):
            return 'deduction'
        elif any(x in code_upper for x in ['SSF', 'SSS', 'SOCIAL', 'BPJS', 'CPF', 'EPF']):
            return 'social_security'
        elif any(x in code_upper for x in ['EMPLOYER', 'ER_', 'COMP_']):
            return 'employer_cost'
        else:
            return 'allowance'

    def _get_payslips_in_range(self, config_id=None, department_id=None):
        """Get payslips within the date range with optional filters"""
        domain = [
            ('company_id', '=', self.company_id.id),
            ('date_from', '>=', self.date_from),
            ('date_to', '<=', self.date_to),
            ('state', 'in', ['done', 'level2'])
        ]
        if config_id:
            domain.append(('formula_config_id', '=', config_id))
        if department_id:
            domain.append(('employee_id.department_id', '=', department_id))

        return self.env['hr.payslip'].search(domain)

    # ============================================================================
    # COMPUTED METHODS
    # ============================================================================

    @api.depends('company_id', 'date_from', 'date_to', 'period_type')
    def _compute_summary_stats(self):
        """Compute header KPI statistics"""
        for record in self:
            # Get configs for this company
            configs = self.env['hr.formula.config'].search([
                ('company_id', '=', record.company_id.id),
                ('state', '=', 'active')
            ])
            record.total_configs = len(configs)

            # Get payslips in date range
            payslips = record._get_payslips_in_range()

            # Unique departments and employees
            departments = payslips.mapped('employee_id.department_id')
            employees = payslips.mapped('employee_id')
            record.total_departments = len(departments)
            record.total_employees = len(employees)

            # Financial totals from payslip lines with report_visible
            gross_pay = 0.0
            net_pay = 0.0
            deductions = 0.0
            employer_cost = 0.0

            for payslip in payslips:
                lines = payslip.line_ids.filtered(lambda l: l.report_visible)
                for line in lines:
                    category_type = record._get_component_category_type(line)
                    amount = line.amount or 0.0

                    if category_type == 'basic':
                        gross_pay += amount
                    elif category_type == 'allowance':
                        gross_pay += amount
                    elif category_type == 'net':
                        net_pay += amount
                    elif category_type in ['deduction', 'tax', 'social_security']:
                        deductions += abs(amount)
                    elif category_type == 'employer_cost':
                        employer_cost += amount

            record.total_gross_pay = gross_pay
            record.total_net_pay = net_pay
            record.total_deductions = deductions
            record.total_employer_cost = employer_cost

    @api.depends('company_id', 'date_from', 'date_to')
    def _compute_hierarchy_data(self):
        """Build clickable hierarchy: Company > Configs > Departments"""
        for record in self:
            hierarchy = {
                'company': {
                    'id': record.company_id.id,
                    'name': record.company_id.name,
                    'total_cost': 0.0,
                    'employee_count': 0
                },
                'configs': []
            }

            configs = self.env['hr.formula.config'].search([
                ('company_id', '=', record.company_id.id),
                ('state', '=', 'active')
            ])

            for config in configs:
                # Get payslips using this config
                payslips = record._get_payslips_in_range(config_id=config.id)

                # Aggregate by department
                dept_data = {}
                for slip in payslips:
                    dept = slip.employee_id.department_id
                    dept_key = dept.id if dept else 0
                    dept_name = dept.name if dept else 'Unassigned'

                    if dept_key not in dept_data:
                        dept_data[dept_key] = {
                            'id': dept_key,
                            'name': dept_name,
                            'employee_count': 0,
                            'gross_pay': 0.0,
                            'net_pay': 0.0,
                            'employees': set()
                        }

                    dept_data[dept_key]['employees'].add(slip.employee_id.id)

                    # Sum report_visible lines
                    for line in slip.line_ids.filtered(lambda l: l.report_visible):
                        category_type = record._get_component_category_type(line)
                        if category_type in ['basic', 'allowance']:
                            dept_data[dept_key]['gross_pay'] += line.amount or 0
                        elif category_type == 'net':
                            dept_data[dept_key]['net_pay'] += line.amount or 0

                # Convert sets to counts
                departments = []
                config_total = 0.0
                config_employees = 0
                for dept_id, data in dept_data.items():
                    data['employee_count'] = len(data['employees'])
                    del data['employees']
                    departments.append(data)
                    config_total += data['gross_pay']
                    config_employees += data['employee_count']

                config_info = {
                    'id': config.id,
                    'name': config.name,
                    'code': config.code,
                    'country_code': config.country_code,
                    'cycle_type': config.cycle_type,
                    'total_cost': config_total,
                    'employee_count': config_employees,
                    'departments': departments
                }
                hierarchy['configs'].append(config_info)
                hierarchy['company']['total_cost'] += config_total
                hierarchy['company']['employee_count'] += config_employees

            record.hierarchy_data_json = json.dumps(hierarchy)

    @api.depends('company_id', 'date_from', 'date_to')
    def _compute_consolidated_data(self):
        """Aggregated view using report_visible components across all configs"""
        for record in self:
            # Get all active configs
            configs = self.env['hr.formula.config'].search([
                ('company_id', '=', record.company_id.id),
                ('state', '=', 'active')
            ])

            # Build component mapping for report_visible rules
            component_map = {}
            for config in configs:
                for rule in config.rule_ids.filtered(lambda r: r.report_visible):
                    if rule.code not in component_map:
                        component_map[rule.code] = {
                            'name': rule.name,
                            'category': rule.category_id.name if rule.category_id else 'Other',
                            'category_type': rule.category_id.category_type if rule.category_id else 'allowance',
                            'identifier': rule.payslip_identifier.identifier if rule.payslip_identifier else ''
                        }

            # Get payslips and aggregate
            payslips = record._get_payslips_in_range()

            # Aggregate by component
            component_totals = {}
            for code, info in component_map.items():
                component_totals[code] = {
                    'code': code,
                    'name': info['name'],
                    'category': info['category'],
                    'category_type': info['category_type'],
                    'identifier': info['identifier'],
                    'total': 0.0
                }

            for payslip in payslips:
                for line in payslip.line_ids.filtered(lambda l: l.report_visible):
                    if line.code in component_totals:
                        component_totals[line.code]['total'] += line.amount or 0

            # Group by category_type
            grouped_by_type = {}
            for code, data in component_totals.items():
                cat_type = data['category_type'] or 'allowance'
                if cat_type not in grouped_by_type:
                    grouped_by_type[cat_type] = {'components': [], 'total': 0.0}
                grouped_by_type[cat_type]['components'].append(data)
                grouped_by_type[cat_type]['total'] += data['total']

            # Group by identifier (EARNINGS, DEDUCTIONS, etc.)
            grouped_by_identifier = {}
            for code, data in component_totals.items():
                identifier = data['identifier'] or 'OTHER'
                if identifier not in grouped_by_identifier:
                    grouped_by_identifier[identifier] = {'components': [], 'total': 0.0}
                grouped_by_identifier[identifier]['components'].append(data)
                grouped_by_identifier[identifier]['total'] += data['total']

            record.consolidated_data_json = json.dumps({
                'components': list(component_totals.values()),
                'grouped_by_type': grouped_by_type,
                'grouped_by_identifier': grouped_by_identifier,
                'period': {
                    'from': str(record.date_from),
                    'to': str(record.date_to),
                    'type': record.period_type
                }
            })

    @api.depends('selected_config_id', 'date_from', 'date_to')
    def _compute_config_detail_data(self):
        """Detailed view for a specific config showing all its components"""
        for record in self:
            if not record.selected_config_id:
                record.config_detail_data_json = json.dumps({})
                continue

            config = record.selected_config_id

            # Get all rules for this config
            rules = config.rule_ids.sorted(key=lambda r: r.sequence)

            # Get report_visible rules only for chart display
            report_rules = rules.filtered(lambda r: r.report_visible)

            # Get payslips using this config
            payslips = record._get_payslips_in_range(config_id=config.id)

            # Aggregate by component
            component_data = {}
            for rule in report_rules:
                component_data[rule.code] = {
                    'code': rule.code,
                    'name': rule.name,
                    'column_letter': rule.column_letter,
                    'category': rule.category_id.name if rule.category_id else 'Other',
                    'category_type': rule.category_id.category_type if rule.category_id else 'allowance',
                    'identifier': rule.payslip_identifier.identifier if rule.payslip_identifier else '',
                    'total': 0.0,
                    'by_department': {}
                }

            for payslip in payslips:
                dept_name = payslip.employee_id.department_id.name or 'Unassigned'

                for line in payslip.line_ids.filtered(lambda l: l.report_visible):
                    if line.code in component_data:
                        component_data[line.code]['total'] += line.amount or 0

                        if dept_name not in component_data[line.code]['by_department']:
                            component_data[line.code]['by_department'][dept_name] = 0.0
                        component_data[line.code]['by_department'][dept_name] += line.amount or 0

            # Get unique departments
            departments = list(set(
                p.employee_id.department_id.name or 'Unassigned'
                for p in payslips
            ))

            record.config_detail_data_json = json.dumps({
                'config': {
                    'id': config.id,
                    'name': config.name,
                    'code': config.code,
                    'country_code': config.country_code,
                    'cycle_type': config.cycle_type,
                    'rule_count': len(rules),
                    'report_visible_count': len(report_rules)
                },
                'components': list(component_data.values()),
                'departments': departments
            })

    @api.depends('selected_config_id', 'selected_department_id', 'date_from', 'date_to')
    def _compute_department_detail_data(self):
        """Department-level drill-down within a config"""
        for record in self:
            if not record.selected_config_id or not record.selected_department_id:
                record.department_detail_data_json = json.dumps({})
                continue

            config = record.selected_config_id
            department = record.selected_department_id

            # Get payslips for this config and department
            payslips = record._get_payslips_in_range(
                config_id=config.id,
                department_id=department.id
            )

            # Employee-level breakdown
            employee_data = {}
            for payslip in payslips:
                emp = payslip.employee_id
                if emp.id not in employee_data:
                    employee_data[emp.id] = {
                        'id': emp.id,
                        'name': emp.name,
                        'job_title': emp.job_id.name if emp.job_id else '',
                        'components': {}
                    }

                for line in payslip.line_ids.filtered(lambda l: l.report_visible):
                    if line.code not in employee_data[emp.id]['components']:
                        employee_data[emp.id]['components'][line.code] = {
                            'code': line.code,
                            'name': line.name,
                            'total': 0.0
                        }
                    employee_data[emp.id]['components'][line.code]['total'] += line.amount or 0

            record.department_detail_data_json = json.dumps({
                'config': config.name,
                'department': department.name,
                'employee_count': len(employee_data),
                'employees': list(employee_data.values())
            })

    # ============================================================================
    # ACTION METHODS
    # ============================================================================

    def action_navigate_to_config(self, config_id):
        """Navigate to config detail view"""
        self.ensure_one()
        self.write({
            'selected_config_id': config_id,
            'active_view': 'config_detail'
        })
        return True

    def action_navigate_to_department(self, config_id, department_id):
        """Navigate to department detail view"""
        self.ensure_one()
        self.write({
            'selected_config_id': config_id,
            'selected_department_id': department_id,
            'active_view': 'department_detail'
        })
        return True

    def action_back_to_hierarchy(self):
        """Return to hierarchy home"""
        self.ensure_one()
        self.write({
            'selected_config_id': False,
            'selected_department_id': False,
            'active_view': 'hierarchy'
        })
        return True

    def action_back_to_config(self):
        """Return to config detail from department detail"""
        self.ensure_one()
        self.write({
            'selected_department_id': False,
            'active_view': 'config_detail'
        })
        return True

    def action_refresh_data(self):
        """Force refresh all computed data"""
        self.ensure_one()
        self.last_refresh = fields.Datetime.now()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload'
        }

    def action_open_config_pivot(self):
        """Open pivot view showing employees vs report_visible components"""
        self.ensure_one()
        if not self.selected_config_id:
            raise UserError(_("Please select a salary config first"))

        # Get payslip IDs for this config in date range
        payslips = self._get_payslips_in_range(config_id=self.selected_config_id.id)

        # Get report_visible component codes for this config
        visible_codes = self.selected_config_id.rule_ids.filtered(
            lambda r: r.report_visible
        ).mapped('code')

        return {
            'name': _('Pivot: %s') % self.selected_config_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payslip.line',
            'view_mode': 'pivot,tree',
            'views': [
                (self.env.ref('pb_hr_payroll_analytics.view_payslip_line_formula_pivot').id, 'pivot'),
                (False, 'tree')
            ],
            'domain': [
                ('slip_id', 'in', payslips.ids),
                ('code', 'in', visible_codes),
                ('report_visible', '=', True)
            ],
            'context': {
                'search_default_group_by_employee': 1,
            }
        }

    def action_open_department_pivot(self):
        """Open pivot view filtered by selected department"""
        self.ensure_one()
        if not self.selected_config_id or not self.selected_department_id:
            raise UserError(_("Please select a config and department first"))

        payslips = self._get_payslips_in_range(
            config_id=self.selected_config_id.id,
            department_id=self.selected_department_id.id
        )

        visible_codes = self.selected_config_id.rule_ids.filtered(
            lambda r: r.report_visible
        ).mapped('code')

        return {
            'name': _('Pivot: %s - %s') % (self.selected_config_id.name, self.selected_department_id.name),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payslip.line',
            'view_mode': 'pivot,tree',
            'views': [
                (self.env.ref('pb_hr_payroll_analytics.view_payslip_line_formula_pivot').id, 'pivot'),
                (False, 'tree')
            ],
            'domain': [
                ('slip_id', 'in', payslips.ids),
                ('code', 'in', visible_codes),
                ('report_visible', '=', True)
            ],
        }

    def action_open_consolidated_pivot(self):
        """Open pivot view for all configs (consolidated)"""
        self.ensure_one()

        # Get all payslips in date range
        payslips = self._get_payslips_in_range()

        # Get all report_visible codes from all active configs
        configs = self.env['hr.formula.config'].search([
            ('company_id', '=', self.company_id.id),
            ('state', '=', 'active')
        ])
        visible_codes = []
        for config in configs:
            visible_codes.extend(
                config.rule_ids.filtered(lambda r: r.report_visible).mapped('code')
            )
        visible_codes = list(set(visible_codes))

        return {
            'name': _('Consolidated Pivot: All Salary Structures'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payslip.line',
            'view_mode': 'pivot,tree',
            'views': [
                (self.env.ref('pb_hr_payroll_analytics.view_payslip_line_formula_pivot').id, 'pivot'),
                (False, 'tree')
            ],
            'domain': [
                ('slip_id', 'in', payslips.ids),
                ('code', 'in', visible_codes),
                ('report_visible', '=', True)
            ],
        }

    @api.model
    def get_or_create_dashboard(self):
        """Get or create the singleton dashboard record for current company"""
        dashboard = self.search([
            ('company_id', '=', self.env.company.id)
        ], limit=1)

        if not dashboard:
            dashboard = self.create({
                'name': 'Salary Structure Analytics',
                'company_id': self.env.company.id
            })

        return dashboard

    # ============================================================================
    # RPC METHODS (for JavaScript)
    # ============================================================================

    def rpc_navigate_to_config(self, config_id):
        """RPC method for JS navigation to config"""
        return self.action_navigate_to_config(config_id)

    def rpc_navigate_to_department(self, config_id, department_id):
        """RPC method for JS navigation to department"""
        return self.action_navigate_to_department(config_id, department_id)
