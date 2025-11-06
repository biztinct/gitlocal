# -*- coding: utf-8 -*-
{
    'name': 'Workforce Demand Planning',
    'version': '16.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'summary': 'Capability mapping, role analysis, and workforce demand planning with interactive dashboards',
    'description': """
        Workforce Demand Planning & Analytics
        =====================================

        This module delivers a modern workforce planning workspace covering:
        * Capability & skill catalogs for strategic workforce design
        * Role analysis with demand segmentation and KPI tracking
        * Shift & project based demand planning with monthly breakdowns
        * Interactive dashboard with heatmaps, cards, and drilldowns
        * Budget variance tracking and automation helpers

        Inspired by the Workforce Planning Toolkit while adapted for Odoo 16 CE.
    """,
    'depends': [
        'base',
        'mail',
        'web',
        'hr',
        'hr_contract',
        'om_hr_payroll',
        'pb_hr_payroll_base',
    ],
    'data': [
        'security/pb_hr_payroll_demand_security.xml',
        'security/ir.model.access.csv',
        'data/pb_hr_payroll_demand_sequences.xml',
        'data/pb_workforce_demo.xml',
        'views/pb_workforce_menus.xml',
        'views/pb_workforce_capability_views.xml',
        'views/pb_workforce_role_views.xml',
        'views/pb_workforce_skill_views.xml',
        'views/pb_workforce_demand_plan_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js',
            'pb_hr_payroll_demand/static/src/css/workforce_dashboard.css',
            'pb_hr_payroll_demand/static/src/js/workforce_dashboard_action.js',
            'pb_hr_payroll_demand/static/src/js/workforce_dashboard.js',
            'pb_hr_payroll_demand/static/src/xml/workforce_dashboard_templates.xml',
        ],
    },
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
    'auto_install': False,
}
