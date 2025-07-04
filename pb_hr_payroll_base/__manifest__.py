# -*- coding: utf-8 -*-
{
    'name': 'Payroll Base Framework',
    'version': '16.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'summary': 'Multi-Country Payroll Base Framework with Contract Type Integration',
    'description': """
        Complete base framework for multi-country payroll management.
        
        Key Features:
        ============
        - Multi-country dashboard with statistics
        - Country selector for easy navigation
        - Enhanced payroll structures with contract type integration
        - Advanced salary rule engine with conditions and calculations
        - Complete Zoho employee data integration
        - Progressive tax calculation examples
        - Comprehensive reporting and analytics
        - Professional UI with status indicators
        
        Supported Countries:
        ===================
        - Vietnam (VN) - Progressive PIT, Social Security
        - Indonesia (ID) - Ready for THR, BPJS integration
        - India (IN) - Ready for PF, ESI integration
        - Singapore (SG) - Framework ready
        - Malaysia (MY) - Framework ready
        
        Technical Features:
        ==================
        - Contract type integration (no conflicts)
        - Accounting integration ready
        - Multi-currency support
        - Enhanced security with proper access controls
        - Demo data with realistic examples
        - Extensible architecture for country modules
        
        This module provides the foundation for country-specific payroll modules
        and eliminates the architectural issues in the legacy system.
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': [
        'base',
        'hr',
        'hr_contract',
        'om_hr_payroll',
        'spreadsheet_oca',
        'website',
        'account',  # For accounting integration
    ],
    'data': [
        # Security - Load First
        'security/payroll_base_security.xml',
        'security/ir.model.access.csv',
        
        # Data - Load After Security
        'data/payroll_base_data.xml',
        
        # Views - Load After Models and Data
        'views/hr_payroll_structure_base_views.xml',
        'views/zoho_base_views.xml',
        'views/payroll_base_dashboard.xml',
        'views/payroll_country_selector_template.xml',
        'views/additional_actions.xml',
        
        # Menus - Load Last
        'views/payroll_menu_base.xml',
    ],
    'demo': [
        'demo/payroll_structure_demo.xml',
    ],
    'external_dependencies': {
        'python': [],
    },
    'images': [
        'static/description/banner.png',
        'static/description/icon.png',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'price': 0.00,
    'currency': 'USD',
    'support': 'support@yourcompany.com',
}