# -*- coding: utf-8 -*-

from odoo import api, fields, models
import json


class HrFormulaConfigAnalyticsVietnam(models.Model):
    """
    Extends hr.formula.config.analytics to add Vietnam-specific
    insurance contribution analytics data.
    """
    _inherit = 'hr.formula.config.analytics'

    # ==========================================
    # INSURANCE ANALYTICS DATA (JSON)
    # ==========================================
    insurance_data_json = fields.Text(
        string='Insurance Data JSON',
        compute='_compute_insurance_data',
        help="JSON data for Vietnam insurance contribution charts"
    )

    @api.depends('company_id', 'date_from', 'date_to')
    def _compute_insurance_data(self):
        """
        Compute insurance contribution data for charts and tables.
        Aggregates contributions from employees with Vietnam insurance policies.
        """
        for record in self:
            insurance_data = {
                'si_employer': 0,
                'si_employee': 0,
                'hi_employer': 0,
                'hi_employee': 0,
                'ui_employer': 0,
                'ui_employee': 0,
                'oa_od': 0,
                'si_enrolled': 0,
                'hi_enrolled': 0,
                'ui_enrolled': 0,
                'total_employees': 0,
            }

            # Get employees with insurance policies for this company
            employees = self.env['hr.employee'].search([
                ('company_id', '=', record.company_id.id),
                ('active', '=', True),
                ('vn_insurance_policy_id', '!=', False)
            ])

            for emp in employees:
                policy = emp.vn_insurance_policy_id
                if not policy:
                    continue

                # Social Insurance
                if emp.vn_si_enrolled:
                    insurance_data['si_enrolled'] += 1
                    si_base = min(emp.vn_si_salary_base or 0, policy.si_max_salary_ceiling)
                    insurance_data['si_employer'] += si_base * policy.si_employer_rate / 100
                    insurance_data['si_employee'] += si_base * policy.si_employee_rate / 100

                # Health Insurance
                if emp.vn_hi_enrolled:
                    insurance_data['hi_enrolled'] += 1
                    hi_base = min(emp.vn_hi_salary_base or 0, policy.hi_max_salary_ceiling)
                    insurance_data['hi_employer'] += hi_base * policy.hi_employer_rate / 100
                    insurance_data['hi_employee'] += hi_base * policy.hi_employee_rate / 100

                # Unemployment Insurance
                if emp.vn_ui_enrolled:
                    insurance_data['ui_enrolled'] += 1
                    ui_base = min(emp.vn_ui_salary_base or 0, policy.ui_max_salary_ceiling)
                    insurance_data['ui_employer'] += ui_base * policy.ui_employer_rate / 100
                    insurance_data['ui_employee'] += ui_base * policy.ui_employee_rate / 100

                # Occupational Accident/Disease (employer-only)
                if hasattr(emp, 'vn_exempt_oa_od') and not emp.vn_exempt_oa_od:
                    oa_base = emp.vn_si_salary_base or 0
                    insurance_data['oa_od'] += oa_base * (policy.oa_employer_rate + policy.od_employer_rate) / 100

            insurance_data['total_employees'] = len(employees)

            # Calculate totals
            insurance_data['total_employer'] = (
                insurance_data['si_employer'] +
                insurance_data['hi_employer'] +
                insurance_data['ui_employer'] +
                insurance_data['oa_od']
            )
            insurance_data['total_employee'] = (
                insurance_data['si_employee'] +
                insurance_data['hi_employee'] +
                insurance_data['ui_employee']
            )
            insurance_data['grand_total'] = (
                insurance_data['total_employer'] +
                insurance_data['total_employee']
            )

            # Chart data for distribution pie chart
            insurance_data['distribution_chart'] = {
                'labels': ['BHXH', 'BHYT', 'BHTN', 'TNLĐ-BNN'],
                'data': [
                    insurance_data['si_employer'] + insurance_data['si_employee'],
                    insurance_data['hi_employer'] + insurance_data['hi_employee'],
                    insurance_data['ui_employer'] + insurance_data['ui_employee'],
                    insurance_data['oa_od']
                ],
                'colors': ['#3b82f6', '#f59e0b', '#ec4899', '#ef4444']
            }

            # Chart data for employer/employee split bar chart
            insurance_data['split_chart'] = {
                'labels': ['BHXH', 'BHYT', 'BHTN', 'TNLĐ-BNN'],
                'employer': [
                    insurance_data['si_employer'],
                    insurance_data['hi_employer'],
                    insurance_data['ui_employer'],
                    insurance_data['oa_od']
                ],
                'employee': [
                    insurance_data['si_employee'],
                    insurance_data['hi_employee'],
                    insurance_data['ui_employee'],
                    0  # OA/OD is employer-only
                ]
            }

            record.insurance_data_json = json.dumps(insurance_data)
