# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class WfpIncreaseRule(models.Model):
    """
    Configurable increase rule within a planning scenario.
    Rules are evaluated in sequence order — first matching rule wins per employee.
    """
    _name = 'wfp.increase.rule'
    _description = 'Workforce Planning Increase Rule'
    _order = 'sequence, id'

    scenario_id = fields.Many2one(
        'wfp.planning.scenario',
        string='Scenario',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        related='scenario_id.company_id',
        store=True,
    )
    currency_id = fields.Many2one(
        related='scenario_id.currency_id',
    )

    # ==========================================
    # RULE IDENTITY
    # ==========================================
    name = fields.Char(
        string='Rule Name',
        required=True,
        help="e.g. '5% for Executives', '3% for Back-Office'"
    )
    sequence = fields.Integer(
        string='Priority',
        default=10,
        help="Lower number = higher priority. First matching rule wins."
    )
    active = fields.Boolean(default=True)

    # ==========================================
    # INCREASE TYPE
    # ==========================================
    increase_type = fields.Selection([
        ('percentage', 'Percentage (%)'),
        ('fixed_amount', 'Fixed Amount'),
        ('merit_matrix', 'Merit Matrix'),
    ], string='Increase Type', default='percentage', required=True)

    increase_pct = fields.Float(
        string='Increase %',
        digits=(5, 2),
        help="Percentage increase (e.g. 5.0 for 5%)"
    )
    increase_amount = fields.Monetary(
        string='Fixed Amount',
        help="Fixed increase amount per employee."
    )
    merit_matrix_id = fields.Many2one(
        'wfp.merit.matrix',
        string='Merit Matrix',
        help="Performance × Compa-ratio matrix for increase %."
    )

    # ==========================================
    # COMPONENT TARGET
    # ==========================================
    component_target = fields.Selection([
        ('base_only', 'Base Salary Only'),
        ('base_and_allowances', 'Base + Allowances (proportional via formulas)'),
        ('total_package', 'Total Package'),
    ], string='Apply To Component',
       default='base_only',
       required=True,
       help="Which component(s) the increase applies to.\n"
            "• Base Salary Only — increase only the base wage; "
            "allowances that depend on base via formulas will "
            "auto-recalculate.\n"
            "• Base + Allowances — increase base and all allowances "
            "proportionally; formula-dependent ones recalculate.\n"
            "• Total Package — increase the total gross package.")

    # ==========================================
    # SCOPE FILTERS (who gets this rule)
    # ==========================================
    apply_to = fields.Selection([
        ('all', 'All Employees'),
        ('department', 'By Department'),
        ('job', 'By Job Position'),
        ('location', 'By Location'),
        ('country', 'By Country'),
        ('custom_filter', 'Custom Domain'),
    ], string='Apply To', default='all', required=True)

    department_ids = fields.Many2many(
        'hr.department',
        'wfp_rule_department_rel',
        'rule_id', 'department_id',
        string='Departments',
    )
    job_ids = fields.Many2many(
        'hr.job',
        'wfp_rule_job_rel',
        'rule_id', 'job_id',
        string='Job Positions',
    )
    location = fields.Char(
        string='Location',
        help="Match against contract.location (cost center)."
    )
    country_code = fields.Selection([
        ('VN', 'Vietnam'), ('ID', 'Indonesia'), ('IN', 'India'),
        ('SG', 'Singapore'), ('MY', 'Malaysia'), ('TH', 'Thailand'),
        ('KH', 'Cambodia'), ('PH', 'Philippines'),
    ], string='Country')

    custom_domain = fields.Text(
        string='Custom Domain',
        help="JSON domain filter applied to hr.employee (advanced)."
    )

    # ==========================================
    # ADDITIONAL FILTERS
    # ==========================================
    exclude_probation = fields.Boolean(
        string='Exclude Probation',
        default=False,
        help="Skip employees with hirestatus = 'new hire'."
    )
    min_tenure_months = fields.Integer(
        string='Min Tenure (months)',
        help="Only apply if employee has been employed >= this many months."
    )
    max_salary = fields.Monetary(
        string='Max Current Salary',
        help="Only apply if current base salary ≤ this amount."
    )
    min_salary = fields.Monetary(
        string='Min Current Salary',
        help="Only apply if current base salary ≥ this amount."
    )

    note = fields.Text(
        string='Justification',
        help="Document the business rationale for this rule."
    )

    # ==========================================
    # MATCHING LOGIC
    # ==========================================
    def matches_employee(self, employee, contract):
        """Check if this rule matches a given employee/contract.

        Returns: True if the rule applies, False otherwise.
        """
        self.ensure_one()

        # Scope filter
        if self.apply_to == 'department' and self.department_ids:
            if employee.department_id not in self.department_ids:
                return False
        elif self.apply_to == 'job' and self.job_ids:
            if employee.job_id not in self.job_ids:
                return False
        elif self.apply_to == 'location' and self.location:
            if (contract.location or '').strip().lower() != self.location.strip().lower():
                return False
        elif self.apply_to == 'country' and self.country_code:
            emp_country = employee.country_id.code if employee.country_id else ''
            if emp_country != self.country_code:
                return False
        elif self.apply_to == 'custom_filter' and self.custom_domain:
            import json
            try:
                domain = json.loads(self.custom_domain)
                matched = self.env['hr.employee'].search(
                    domain + [('id', '=', employee.id)]
                )
                if not matched:
                    return False
            except Exception:
                return False

        # Additional filters
        if self.exclude_probation:
            if contract.hirestatus == 'new hire':
                return False

        if self.min_tenure_months:
            from dateutil.relativedelta import relativedelta
            if employee.create_date:
                tenure = relativedelta(
                    fields.Date.today(), employee.create_date.date()
                )
                months = tenure.years * 12 + tenure.months
                if months < self.min_tenure_months:
                    return False

        if self.max_salary and contract.wage > self.max_salary:
            return False

        if self.min_salary and contract.wage < self.min_salary:
            return False

        return True

    def calculate_increase(self, employee, contract, current_costs):
        """Calculate the increase amount for an employee.

        Args:
            employee: hr.employee record
            contract: hr.contract record
            current_costs: dict with current cost breakdown

        Returns:
            dict with {
                'new_base': float,
                'increase_amount': float,
                'increase_pct': float,
            }
        """
        self.ensure_one()
        current_base = contract.wage or 0

        if self.increase_type == 'percentage':
            pct = self.increase_pct / 100.0

            if self.component_target == 'base_only':
                increase = current_base * pct
                new_base = current_base + increase
            elif self.component_target == 'base_and_allowances':
                # Increase base; allowances recalculate via formula
                increase = current_base * pct
                new_base = current_base + increase
            elif self.component_target == 'total_package':
                current_gross = current_costs.get('gross', current_base)
                target_gross = current_gross * (1 + pct)
                # Scale base proportionally
                if current_gross > 0:
                    ratio = current_base / current_gross
                    new_base = target_gross * ratio
                else:
                    new_base = current_base + (current_base * pct)
                increase = new_base - current_base
            else:
                increase = current_base * pct
                new_base = current_base + increase

        elif self.increase_type == 'fixed_amount':
            increase = self.increase_amount or 0
            new_base = current_base + increase

        elif self.increase_type == 'merit_matrix':
            if not self.merit_matrix_id:
                return {
                    'new_base': current_base,
                    'increase_amount': 0,
                    'increase_pct': 0,
                }
            pct = self.merit_matrix_id.get_increase_pct(
                contract.compa_ratio,
                employee,
            )
            increase = current_base * (pct / 100.0)
            new_base = current_base + increase
        else:
            new_base = current_base
            increase = 0

        return {
            'new_base': new_base,
            'increase_amount': increase,
            'increase_pct': (
                (increase / current_base * 100) if current_base else 0
            ),
        }
