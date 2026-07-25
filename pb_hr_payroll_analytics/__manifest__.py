# -*- coding: utf-8 -*-
{
    'name': 'HR Analytics & Reporting',
    # 19.0.1.1.0 — Sudima Phase M: the menu forest is retired (views, actions
    # and models all stay, off-menu; the Insights cockpit's report gallery is
    # now the entry point). See views/hr_analytics_menus.xml.
    'version': '19.0.1.1.0',
    'category': 'Human Resources/Payroll',
    'summary': 'Professional HR analytics with personnel costs, statutory contributions, headcount analysis',
    'description': """
        Comprehensive HR Analytics & Reporting Module
        =============================================

        Features:
        * Personnel Costs for Management - Multi-dimensional analysis by department, job title, designation, cost center
        * Cross Country Analytics - Global cost comparison and headcount distribution
        * Statutory Contributions Report - Employee & Employer contributions with compliance tracking
        * Headcount Analysis - FTE calculations, attrition rates, and trends
        * Dependents & Benefits Report - Dependent tracking and insurance impact analysis
        * Budget Variance Report - Budgeted vs Actual cost comparison
        * Annual HR Costs Overview - Annual salary costs, total cost of employment, and projections

        Dashboard Features:
        * Unified dashboard with tabbed navigation
        * 10+ professional chart types (Doughnut, Bar, Scatter, Treemap, Waterfall, Heatmap, etc.)
        * Global country filter for cross-region analysis
        * Year-over-year and historical comparisons
        * PDF/Excel export capabilities
        * Auto-refresh with caching (30-minute TTL)
        * Multi-dimensional analysis across departments and cost centers
    """,

    'depends': [
        'base',
        'hr',
        'hr_contract',
        'om_hr_payroll',           # Core payroll
        'pb_hr_payroll_base',      # Base country framework
        'pb_hr_payroll_formula',   # Formula-based payroll configs
        'web',
    ],

    'data': [
        'security/ir.model.access.csv',
        'security/hr_analytics_security.xml',
        'data/hr_analytics_data.xml',
        'data/hr_analytics_sample_data.xml',
        # Load individual view/action files first (define their own actions)
        'views/hr_analytics_personnel_costs.xml',
        'views/hr_analytics_headcount.xml',
        'views/hr_analytics_statutory.xml',
        'views/hr_analytics_dependents.xml',
        'views/hr_analytics_budget.xml',
        'views/hr_analytics_annual.xml',
        'views/hr_analytics_search_filters.xml',
        'views/hr_payroll_employee_detail_views.xml',
        # Load export wizard before dashboard (dashboard references the action)
        'wizards/hr_analytics_export_wizard_views.xml',
        # Load dashboard after all actions are defined
        'views/hr_analytics_dashboard.xml',
        # Formula Config Analytics (Salary Structure Analytics)
        'views/hr_formula_config_analytics_views.xml',
        'views/hr_payslip_line_pivot_views.xml',
        # Load menus last (they reference all actions and dashboard)
        'views/hr_analytics_menus.xml',
        'reports/hr_analytics_reports.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'pb_hr_payroll_analytics/static/src/css/hr_analytics_dashboard.css',
            'pb_hr_payroll_analytics/static/src/css/hr_analytics_responsive.css',
            # DISABLED: Legacy odoo.define/require syntax incompatible with Odoo 19
            # 'pb_hr_payroll_analytics/static/src/js/hr_analytics_dashboard.js',
            # 'pb_hr_payroll_analytics/static/src/js/hr_analytics_charts.js',
            # 'pb_hr_payroll_analytics/static/src/js/hr_analytics_export.js',
            # 'pb_hr_payroll_analytics/static/src/js/hr_formula_config_analytics.js',
        ]
    },

    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
