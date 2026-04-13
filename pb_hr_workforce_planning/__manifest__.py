# -*- coding: utf-8 -*-
{
    'name': 'Workforce Planning & Compensation Forecasting',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'summary': 'Salary simulation, scenario modelling, merit cycles, and total employer cost forecasting',
    'description': """
        World-class Workforce Planning Module
        ======================================

        Built on top of pb_hr_payroll_formula engine. Features:

        Phase 1 - Salary Simulation & Forecasting:
        * Planning scenarios with configurable increase rules
        * Formula-based total employer cost calculation (TCOW)
        * Employee-level drilldown with component breakdown
        * Monthly time-phased cost projections
        * Side-by-side scenario comparison
        * Excel export (detail / summary / component)
        * Executive dashboard with charts and KPI cards

        Phase 2 - Merit Cycles & Advanced Analytics:
        * Pay grade / salary band / compa-ratio infrastructure
        * Merit matrix (Performance × Compa-ratio grid)
        * Compensation cycle workflow (budget → worksheets → approval)
        * Headcount change modelling (hire / attrition / promotion)
        * Advanced charts (heatmap, waterfall, treemap)
    """,

    'depends': [
        'base',
        'mail',
        'web',
        'hr',
        'hr_contract',
        'om_hr_payroll',
        'pb_hr_payroll_formula',
        'pb_hr_payroll_analytics',
    ],

    'data': [
        # Security
        'security/workforce_planning_security.xml',
        'security/ir.model.access.csv',
        # Data
        'data/workforce_planning_data.xml',
        # Views
        'views/formula_rule_wfp_views.xml',
        'views/planning_scenario_views.xml',
        'views/increase_rule_views.xml',
        'views/employee_forecast_views.xml',
        'views/monthly_projection_views.xml',
        'views/pay_grade_views.xml',
        'views/merit_matrix_views.xml',
        'views/compensation_cycle_views.xml',
        'views/headcount_change_views.xml',
        # Dashboard
        'views/workforce_planning_dashboard_views.xml',
        # Wizards
        'wizards/wfp_tagging_wizard_views.xml',
        'wizards/export_wizard_views.xml',
        # Menus last
        'views/workforce_planning_menus.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'pb_hr_workforce_planning/static/src/css/workforce_planning.css',
            'pb_hr_workforce_planning/static/src/js/workforce_planning_dashboard.js',
            'pb_hr_workforce_planning/static/src/xml/workforce_planning_templates.xml',
        ],
    },

    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
