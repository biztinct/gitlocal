# -*- coding: utf-8 -*-
"""`pb.wfp.forecasts` — the Employee Forecast Detail table on the shared
filter panel (pb_filter_kit, FILTER wave 8).

The table used to be every forecast row of the scenario, loaded whole by
`wfp.planning.scenario.get_dashboard_data` and searched and sorted in the
browser. It is now served a page at a time for the panel's state; the
scenario rides on every call as `pbf_ctx.scenario_id`. `get_dashboard_data`
is unchanged: the charts still read it (R4).

Excluded people are part of the list (the old table hid them); the first
view shows the people counted in the forecast, which is the old table.
"""
from odoo import _, api, models

#: Rows per page of the table.
FORECAST_PAGE = 60


class PbWfpForecasts(models.AbstractModel):
    _name = 'pb.wfp.forecasts'
    _description = 'Workforce planning forecast table'
    _inherit = ['pb.filter.mixin']

    # ------------------------------------------------------------ scenario
    @api.model
    def _scenario(self):
        try:
            sid = int(self._pbf_ctx().get('scenario_id') or 0)
        except (TypeError, ValueError):
            sid = 0
        Scenario = self.env['wfp.planning.scenario']
        return Scenario.browse(sid).exists() if sid else Scenario

    def _pbf_model(self):
        return 'wfp.employee.forecast'

    def _pbf_screen(self):
        # one key for every scenario: a saved view works on the next one too
        return 'wfpforecast'

    def _pbf_base_domain(self):
        scenario = self._scenario()
        if not scenario:
            return [('id', '=', 0)]
        return [('scenario_id', '=', scenario.id)]

    def _pbf_search_fields(self):
        # what the old search box looked in: name, department, job, rule
        return ['employee_id.name', 'department_id.name', 'job_id.name',
                'applied_rule_name']

    def _pbf_layout_extra(self):
        scenario = self._scenario()
        currency = scenario.currency_id if scenario else self.env.company.currency_id
        return {'currency': (currency.symbol if currency else '') or ''}

    def _pbf_sorts(self):
        # The table's columns. The first is the old default: biggest
        # increase first (the browser sorted increase_amount descending).
        return [
            {'key': 'increase_desc', 'label': _('Biggest increase first'),
             'order': 'increase_amount desc, id'},
            {'key': 'increase_asc', 'label': _('Smallest increase first'),
             'order': 'increase_amount asc, id'},
            {'key': 'pct_desc', 'label': _('Highest increase % first'),
             'order': 'increase_pct desc, id'},
            {'key': 'pct_asc', 'label': _('Lowest increase % first'),
             'order': 'increase_pct asc, id'},
            {'key': 'name', 'label': _('Name, A to Z'), 'order': 'employee_id, id'},
            {'key': 'name_desc', 'label': _('Name, Z to A'), 'order': 'employee_id desc, id'},
            {'key': 'dept', 'label': _('Department, A to Z'), 'order': 'department_id, employee_id, id'},
            {'key': 'job', 'label': _('Job, A to Z'), 'order': 'job_id, employee_id, id'},
            {'key': 'base_desc', 'label': _('Highest current base first'),
             'order': 'current_base desc, id'},
            {'key': 'total_desc', 'label': _('Highest current cost first'),
             'order': 'current_total_cost desc, id'},
            {'key': 'fbase_desc', 'label': _('Highest forecast base first'),
             'order': 'forecast_base desc, id'},
            {'key': 'ftotal_desc', 'label': _('Highest forecast cost first'),
             'order': 'forecast_total_cost desc, id'},
            {'key': 'rule', 'label': _('Rule, A to Z'), 'order': 'applied_rule_name, employee_id, id'},
        ]

    def _pbf_spec(self):
        return [
            # ---- pinned: where, which rule, how much
            {'key': 'department', 'label': _('Department'), 'icon': 'building',
             'group': 'people', 'type': 'many2one', 'path': 'department_id', 'pinned': True,
             'none_label': _('No department')},
            {'key': 'rule', 'label': _('Increase rule'), 'icon': 'sliders',
             'group': 'pay', 'type': 'many2one', 'path': 'applied_rule_id', 'pinned': True,
             'none_label': _('No rule applied')},
            {'key': 'pct', 'label': _('Increase %'), 'icon': 'percent',
             'group': 'pay', 'type': 'number', 'path': 'increase_pct', 'pinned': True},
            # ---- more filters
            {'key': 'size', 'label': _('Size of the increase'), 'icon': 'trendingUp',
             'group': 'pay', 'type': 'choice',
             'help': _('The same bands the table colours its rows by.'),
             'options': [
                 {'value': 'over10', 'label': _('Over 10%'), 'tone': 'rose',
                  'domain': [('increase_pct', '>', 10)]},
                 {'value': 'over5', 'label': _('Over 5%, up to 10%'), 'tone': 'amber',
                  'domain': [('increase_pct', '>', 5), ('increase_pct', '<=', 10)]},
                 {'value': 'upto5', 'label': _('Up to 5%'), 'tone': 'green',
                  'domain': [('increase_pct', '>', 0), ('increase_pct', '<=', 5)]},
                 {'value': 'none', 'label': _('No increase'), 'tone': 'slate',
                  'domain': ['|', ('increase_pct', '=', False), ('increase_pct', '=', 0)]},
                 {'value': 'down', 'label': _('A decrease'), 'tone': 'blue',
                  'domain': [('increase_pct', '<', 0)]},
             ]},
            {'key': 'excluded', 'label': _('In the forecast'), 'icon': 'users',
             'group': 'people', 'type': 'choice',
             'options': [
                 {'value': 'in', 'label': _('Counted in the forecast'), 'tone': 'green',
                  'domain': [('is_excluded', '=', False)]},
                 {'value': 'out', 'label': _('Excluded'), 'tone': 'slate',
                  'domain': [('is_excluded', '=', True)]},
             ]},
            {'key': 'job', 'label': _('Job position'), 'icon': 'briefcase',
             'group': 'people', 'type': 'many2one', 'path': 'job_id',
             'none_label': _('No job position')},
            {'key': 'manager', 'label': _('Manager'), 'icon': 'userCheck',
             'group': 'people', 'type': 'many2one', 'path': 'manager_id',
             'none_label': _('No manager')},
            {'key': 'amount', 'label': _('Increase amount'), 'icon': 'banknote',
             'group': 'pay', 'type': 'number', 'path': 'increase_amount', 'unit': 'money'},
            {'key': 'country', 'label': _('Country'), 'icon': 'globe',
             'group': 'work', 'type': 'char', 'path': 'country_code',
             'none_label': _('Not recorded')},
            {'key': 'location', 'label': _('Location or cost centre'), 'icon': 'mapPin',
             'group': 'work', 'type': 'char', 'path': 'location',
             'none_label': _('Not recorded')},
            {'key': 'tenure', 'label': _('Months of service'), 'icon': 'hourglass',
             'group': 'work', 'type': 'number', 'path': 'tenure_months'},
        ]

    def _pbf_builtin_views(self):
        counted = ['in']
        return [
            {'key': 'all', 'label': _('Everyone in the forecast'), 'icon': 'users',
             'filters': {'excluded': counted}},
            {'key': 'over10', 'label': _('Increases over 10%'),
             'filters': {'excluded': counted, 'size': ['over10']}},
            {'key': 'norule', 'label': _('No rule applied'),
             'filters': {'excluded': counted, 'rule': [False]}},
            {'key': 'excluded', 'label': _('Excluded people'),
             'filters': {'excluded': ['out']}},
        ]

    # --------------------------------------------------------------- rows
    @api.model
    def _row(self, f):
        """One table row — the same keys `get_dashboard_data` gives a row."""
        contract = f.contract_id
        return {
            'id': f.id,
            'employee_id': f.employee_id.id,
            'name': f.employee_id.name,
            'department': f.department_id.name or '',
            'job': f.job_id.name or '',
            'country': f.country_code or '',
            'location': f.location or '',
            'current_base': f.current_base,
            'current_gross': f.current_gross,
            'current_employer': f.current_employer_cost,
            'current_total': f.current_total_cost,
            'forecast_base': f.forecast_base,
            'forecast_gross': f.forecast_gross,
            'forecast_employer': f.forecast_employer_cost,
            'forecast_total': f.forecast_total_cost,
            'increase_amount': f.increase_amount,
            'increase_pct': f.increase_pct,
            'rule_name': f.applied_rule_name or _('No Rule'),
            'excluded': bool(f.is_excluded),
            'exclusion_reason': f.exclusion_reason or '',
            'compa_ratio': contract.compa_ratio if contract and 'compa_ratio' in contract._fields else 0,
            'grade': contract.grade_id.name if contract and 'grade_id' in contract._fields
            and contract.grade_id else '',
        }

    @api.model
    def get_forecast_page(self, filters=None, search=None, sort=None, offset=0,
                          limit=FORECAST_PAGE):
        """One page of the scenario's forecast rows for the panel's state."""
        Forecast = self.env['wfp.employee.forecast']
        if not self._scenario():
            return {'rows': [], 'total': 0, 'offset': 0}
        try:
            offset = max(0, int(offset or 0))
            limit = max(1, min(int(limit or FORECAST_PAGE), 200))
        except (TypeError, ValueError):
            offset, limit = 0, FORECAST_PAGE
        domain = self.pbf_domain(filters or {}, search)
        recs = Forecast.search(domain, order=self.pbf_order(sort) or 'increase_amount desc, id',
                               offset=offset, limit=limit)
        return {'rows': [self._row(f) for f in recs],
                'total': Forecast.search_count(domain), 'offset': offset}
