# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
import json


class WfpScenarioComparison(models.TransientModel):
    """Transient model for side-by-side scenario comparison."""
    _name = 'wfp.scenario.comparison'
    _description = 'WFP Scenario Comparison'

    scenario_ids = fields.Many2many(
        'wfp.planning.scenario',
        'wfp_comparison_scenario_rel',
        'comparison_id', 'scenario_id',
        string='Scenarios to Compare',
    )

    @api.model
    def get_comparison_data(self, scenario_ids):
        """Return comparison data for 2+ scenarios."""
        scenarios = self.env['wfp.planning.scenario'].browse(scenario_ids)
        result = {'scenarios': []}

        for s in scenarios:
            forecasts = s.employee_forecast_ids.filtered(
                lambda f: not f.is_excluded
            )

            # Top employer cost components
            component_totals = {}
            for f in forecasts:
                comps = f.get_current_components()
                fcomps = f.get_forecast_components()
                for c in comps:
                    if c.get('wfp_category') == 'employer_cost':
                        key = c['code']
                        if key not in component_totals:
                            component_totals[key] = {
                                'code': key,
                                'name': c.get('name', key),
                                'current': 0, 'forecast': 0,
                            }
                        component_totals[key]['current'] += c.get('amount', 0)
                for c in fcomps:
                    if c.get('wfp_category') == 'employer_cost':
                        key = c['code']
                        if key in component_totals:
                            component_totals[key]['forecast'] += c.get('amount', 0)

            result['scenarios'].append({
                'id': s.id,
                'name': s.name,
                'state': s.state,
                'headcount': s.headcount,
                'current_cost': s.total_current_cost,
                'forecast_cost': s.total_forecast_cost,
                'increase_amount': s.total_increase_amount,
                'increase_pct': s.total_increase_pct,
                'budget': s.budget_amount or 0,
                'variance': s.budget_variance,
                'top_components': sorted(
                    component_totals.values(),
                    key=lambda x: abs(x.get('forecast', 0) - x.get('current', 0)),
                    reverse=True,
                )[:10],
            })

        return result
