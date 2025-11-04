# -*- coding: utf-8 -*-
{
    'name': 'Payroll Analytics & Approval',
    'version': '16.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'summary': 'Advanced Payroll Analytics, Approval Dashboard & Bank Export',
    'description': """
        This module provides comprehensive payroll analytics and approval functionality:
        
        Features:
        - Professional analytics dashboard for final approvers
        - Month-over-month payroll comparisons with charts
        - Visual analytics for all salary components
        - Anomaly detection and alerts
        - Final approval workflow
        - Bank disbursement file export
        - Multi-country support (Vietnam, Indonesia, India)
        - Professional charts using Chart.js and custom analytics
        
        Analytics Include:
        - Employee count trends
        - Salary component comparisons
        - Total payroll vs previous months
        - Average salary analysis
        - Component-wise breakdowns
        - Variance alerts and recommendations
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': [
        'base',
        'hr',
        'hr_contract', 
        'om_hr_payroll',
        'pb_hr_payroll_base',  # Required for payroll.dashboard model
        'web',
        'spreadsheet_oca',
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',
        'security/payroll_analytics_security.xml',

        # Data
        'data/payroll_analytics_data.xml',

        # Views
        'views/payroll_analytics_dashboard.xml',
        'views/payroll_approval_views.xml',
        'views/payroll_comparison_views.xml',
        'views/bank_export_views.xml',
        'views/payroll_analytics_templates.xml',

        # Wizards
        'wizards/payroll_comparison_wizard_views.xml',

        # Reports
        'reports/payroll_analytics_reports.xml',

        # Menu
        'views/payroll_analytics_menus.xml',

        # Translations
        'i18n/payroll_analytics_approval.pot',
        'i18n/vi_VN.po',
        'i18n/km_KH.po',
    ],
    'assets': {
        'web.assets_backend': [
            # CSS Files
            'payroll_analytics_approval/static/src/css/payroll_analytics.css',
            
            # JavaScript Files
            'payroll_analytics_approval/static/src/js/payroll_charts.js',
            'payroll_analytics_approval/static/src/js/payroll_dashboard.js',
        ],
        'web.assets_frontend': [
            # Frontend assets if needed
            'payroll_analytics_approval/static/src/css/payroll_analytics.css',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': True,
    'license': 'LGPL-3',
}