# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta
import json
import logging

_logger = logging.getLogger(__name__)


class WfpSimulationEngine(models.AbstractModel):
    """
    Core simulation engine for workforce planning scenarios.
    Re-evaluates formula rules with modified salary inputs to produce
    accurate forecasts of total employer cost.
    """
    _name = 'wfp.simulation.engine'
    _description = 'WFP Simulation Engine'

    @api.model
    def run_scenario(self, scenario):
        """Run the full simulation for a planning scenario.

        Steps:
        1. Get matching employees
        2. For each employee: calculate current, apply rule, re-calculate forecast
        3. Generate monthly projections
        """
        _logger.info(
            "WFP: Running scenario '%s' (config: %s)",
            scenario.name, scenario.formula_config_id.display_name
        )

        # Clear previous results
        scenario.employee_forecast_ids.unlink()
        scenario.monthly_projection_ids.unlink()

        config = scenario.formula_config_id
        calculator = self.env['wfp.employer.cost.calculator']

        # Get employees with active contracts in scope
        employees = self._get_employees_in_scope(scenario)

        if not employees:
            raise UserError(_(
                "No employees found matching the scenario filters. "
                "Check that employees have active contracts with the "
                "correct salary structure."
            ))

        _logger.info("WFP: Processing %d employees", len(employees))

        # Get increase rules in priority order
        rules = scenario.rule_ids.filtered('active').sorted(
            key=lambda r: r.sequence
        )

        forecast_vals_list = []

        for employee in employees:
            contract = self._get_active_contract(employee, config)
            if not contract:
                continue

            try:
                forecast_data = self._process_employee(
                    employee, contract, config, rules, calculator, scenario
                )
                forecast_vals_list.append(forecast_data)
            except Exception as e:
                _logger.warning(
                    "WFP: Error processing employee %s: %s",
                    employee.name, e
                )
                # Create excluded forecast with error reason
                forecast_vals_list.append({
                    'scenario_id': scenario.id,
                    'employee_id': employee.id,
                    'contract_id': contract.id,
                    'country_code': config.country_code,
                    'location': contract.location or contract.costcenter or '',
                    'is_excluded': True,
                    'exclusion_reason': str(e)[:200],
                })

        # Bulk create forecasts
        if forecast_vals_list:
            self.env['wfp.employee.forecast'].create(forecast_vals_list)

        # Generate monthly projections
        self._generate_monthly_projections(scenario)

        _logger.info(
            "WFP: Scenario '%s' complete. %d employees, %d forecasts.",
            scenario.name, len(employees), len(forecast_vals_list)
        )

    @api.model
    def _get_employees_in_scope(self, scenario):
        """Get employees matching scenario filters who have active contracts."""
        domain = [
            ('company_id', '=', scenario.company_id.id),
        ]

        # Apply scope filters
        if scenario.filter_department_ids:
            domain.append(
                ('department_id', 'in', scenario.filter_department_ids.ids)
            )
        if scenario.filter_job_ids:
            domain.append(
                ('job_id', 'in', scenario.filter_job_ids.ids)
            )

        employees = self.env['hr.employee'].search(domain)

        # Further filter: must have active contract with matching structure
        config = scenario.formula_config_id
        structure = config.structure_id

        filtered = self.env['hr.employee']
        for emp in employees:
            contract = self._get_active_contract(emp, config)
            if contract:
                # Location filter
                if scenario.filter_location:
                    loc = (
                        contract.location or contract.costcenter or ''
                    ).strip().lower()
                    if scenario.filter_location.strip().lower() not in loc:
                        continue
                filtered |= emp

        return filtered

    @api.model
    def _get_active_contract(self, employee, formula_config):
        """Get the active contract for an employee that matches the formula config."""
        contracts = self.env['hr.contract'].search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'open'),
            ('company_id', '=', formula_config.company_id.id),
        ], order='date_start desc', limit=1)

        # If config has a linked structure, check match
        if formula_config.structure_id and contracts:
            if contracts.struct_id != formula_config.structure_id:
                # Try to find contract with matching structure
                struct_contracts = self.env['hr.contract'].search([
                    ('employee_id', '=', employee.id),
                    ('state', '=', 'open'),
                    ('struct_id', '=', formula_config.structure_id.id),
                ], limit=1)
                if struct_contracts:
                    return struct_contracts

        return contracts

    @api.model
    def _process_employee(self, employee, contract, config, rules,
                          calculator, scenario):
        """Process a single employee and return forecast vals dict."""

        # Step 1: Build current input values from contract
        current_inputs = calculator.build_input_values(contract, config)

        # Step 2: Evaluate current costs using formula engine
        current_costs = calculator.evaluate_costs(config, current_inputs)

        # Step 3: Find first matching increase rule
        applied_rule = None
        for rule in rules:
            if rule.matches_employee(employee, contract):
                applied_rule = rule
                break

        # Step 4: Calculate increase
        if applied_rule:
            increase_result = applied_rule.calculate_increase(
                employee, contract, current_costs
            )
            new_base = increase_result['new_base']
        else:
            new_base = contract.wage or 0

        # Step 5: Build modified inputs and re-evaluate forecast costs
        modified_inputs = calculator.build_modified_inputs(
            current_inputs, config, new_base, applied_rule
        )
        forecast_costs = calculator.evaluate_costs(config, modified_inputs)

        # Step 6: Calculate tenure
        tenure_months = 0
        if employee.create_date:
            delta = relativedelta(
                fields.Date.today(), employee.create_date.date()
            )
            tenure_months = delta.years * 12 + delta.months

        return {
            'scenario_id': scenario.id,
            'employee_id': employee.id,
            'contract_id': contract.id,
            'country_code': config.country_code,
            'location': contract.location or contract.costcenter or '',
            # Current
            'current_base': current_costs['base'],
            'current_allowances': current_costs['allowances'],
            'current_gross': current_costs['gross'],
            'current_deductions': current_costs['deductions'],
            'current_net': current_costs['net'],
            'current_employer_cost': current_costs['employer_cost'],
            'current_total_cost': current_costs['total_cost'],
            'current_components_json': json.dumps(
                current_costs['components']
            ),
            # Forecast
            'forecast_base': forecast_costs['base'],
            'forecast_allowances': forecast_costs['allowances'],
            'forecast_gross': forecast_costs['gross'],
            'forecast_deductions': forecast_costs['deductions'],
            'forecast_net': forecast_costs['net'],
            'forecast_employer_cost': forecast_costs['employer_cost'],
            'forecast_total_cost': forecast_costs['total_cost'],
            'forecast_components_json': json.dumps(
                forecast_costs['components']
            ),
            # Metadata
            'applied_rule_id': applied_rule.id if applied_rule else False,
            'tenure_months': tenure_months,
            'is_excluded': False,
        }

    @api.model
    def _generate_monthly_projections(self, scenario):
        """Generate 12-month projections for the scenario."""
        forecasts = scenario.employee_forecast_ids.filtered(
            lambda f: not f.is_excluded
        )
        if not forecasts:
            return

        effective = scenario.effective_date
        fy = scenario.fiscal_year

        # Generate for 12 months of the fiscal year
        projection_vals = []
        for m in range(1, 13):
            month_str = str(m).zfill(2)
            from datetime import date
            month_date = date(fy, m, 1)
            is_pre = month_date < effective if effective else False

            if is_pre:
                total_base = sum(forecasts.mapped('current_base'))
                total_alw = sum(forecasts.mapped('current_allowances'))
                total_gross = sum(forecasts.mapped('current_gross'))
                total_ded = sum(forecasts.mapped('current_deductions'))
                total_emp = sum(forecasts.mapped('current_employer_cost'))
                total_cost = sum(forecasts.mapped('current_total_cost'))
            else:
                total_base = sum(forecasts.mapped('forecast_base'))
                total_alw = sum(forecasts.mapped('forecast_allowances'))
                total_gross = sum(forecasts.mapped('forecast_gross'))
                total_ded = sum(forecasts.mapped('forecast_deductions'))
                total_emp = sum(forecasts.mapped('forecast_employer_cost'))
                total_cost = sum(forecasts.mapped('forecast_total_cost'))

            current_monthly = sum(forecasts.mapped('current_total_cost'))
            delta = total_cost - current_monthly

            # Build department breakdown
            dept_data = {}
            for f in forecasts:
                dept_name = f.department_id.name or _('No Department')
                if dept_name not in dept_data:
                    dept_data[dept_name] = {
                        'gross': 0, 'employer': 0, 'total': 0, 'headcount': 0,
                    }
                dept_data[dept_name]['headcount'] += 1
                if is_pre:
                    dept_data[dept_name]['gross'] += f.current_gross
                    dept_data[dept_name]['employer'] += f.current_employer_cost
                    dept_data[dept_name]['total'] += f.current_total_cost
                else:
                    dept_data[dept_name]['gross'] += f.forecast_gross
                    dept_data[dept_name]['employer'] += f.forecast_employer_cost
                    dept_data[dept_name]['total'] += f.forecast_total_cost

            projection_vals.append({
                'scenario_id': scenario.id,
                'month': month_str,
                'year': fy,
                'headcount': len(forecasts),
                'total_base': total_base,
                'total_allowances': total_alw,
                'total_gross': total_gross,
                'total_deductions': total_ded,
                'total_employer_cost': total_emp,
                'total_cost_to_company': total_cost,
                'delta_vs_current': delta,
                'is_pre_effective': is_pre,
                'department_breakdown_json': json.dumps(dept_data),
            })

        if projection_vals:
            self.env['wfp.monthly.projection'].create(projection_vals)
