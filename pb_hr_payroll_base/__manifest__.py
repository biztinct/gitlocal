# -*- coding: utf-8 -*-
{
    'name': 'Multi-Country Payroll Base Framework',
    'version': '16.0.2.0.0',
    'category': 'Human Resources/Payroll',
    'summary': 'Complete Multi-Country Payroll Framework - Extends om_hr_payroll without modifications',
    'description': """
        Complete Multi-Country Payroll Framework
        ========================================
        
        This module provides a comprehensive framework for multi-country payroll management
        by extending the base om_hr_payroll module WITHOUT modifying it.
        
        🌍 CORE STRATEGY:
        - Extends om_hr_payroll via inheritance
        - No modifications to base payroll module
        - Clean, maintainable architecture
        - Easy country-specific extensions
        
        🚀 KEY FEATURES:
        ================
        
        Multi-Country Dashboard:
        - Country selector with visual dashboard
        - Real-time statistics per country
        - Professional UI with Bootstrap cards
        - Quick action buttons for each country
        
        Enhanced Payroll Structures:
        - Country-specific payroll structures
        - Contract type integration
        - Multi-currency support
        - Working time configuration
        - Tax calculation methods
        
        Advanced Salary Rules Engine:
        - Country-specific salary rules
        - Contract type conditions
        - Enhanced calculation methods
        - Statutory rule marking
        - Flexible amount constraints
        
        Zoho Integration Foundation:
        - Employee data import framework
        - Country-specific data mapping
        - Processing workflow
        - Error handling and logging
        
        🎯 SUPPORTED COUNTRIES:
        =======================
        Ready for immediate deployment:
        - Vietnam (VN) - Progressive PIT, Social Security
        - Indonesia (ID) - THR, BPJS integration ready
        - India (IN) - PF, ESI integration ready
        - Singapore (SG) - Framework ready
        - Malaysia (MY) - Framework ready
        
        Expandable to any country by adding country modules.
        
        🏗️ ARCHITECTURE:
        =================
        
        Base Layer (om_hr_payroll):
        - Untouched base payroll functionality
        - Core models and workflows
        - Standard Odoo payroll features
        
        Framework Layer (pb_hr_payroll_base):
        - Multi-country extensions
        - Dashboard and navigation
        - Enhanced models via inheritance
        - Common utilities and tools
        
        Country Layer (pb_hr_payroll_*):
        - Country-specific salary rules
        - Local tax calculations
        - Compliance requirements
        - Local reporting formats
        
        🔧 TECHNICAL EXCELLENCE:
        ========================
        - Clean inheritance patterns
        - No base module modifications
        - Proper field constraints and validations
        - Comprehensive error handling
        - Performance optimized queries
        - Multi-currency support
        - Accounting integration ready
        - Portal access for employees
        - Professional reporting
        
        📊 DASHBOARD FEATURES:
        =====================
        - Country selection interface
        - Real-time employee statistics
        - Active contracts monitoring
        - Pending payslips tracking
        - Currency display
        - Quick navigation buttons
        - Responsive design
        
        🔐 SECURITY:
        ============
        - Multi-country access groups
        - Proper record rules
        - Data isolation by country
        - Audit trails
        - Permission-based access
        
        📈 EXTENSIBILITY:
        =================
        - Easy country module creation
        - Plugin architecture
        - Hook system for customizations
        - API-ready for integrations
        - Spreadsheet integration
        - Third-party payroll imports
        
        This framework eliminates the need to modify base Odoo payroll
        while providing enterprise-grade multi-country payroll capabilities.
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': [
        'base',
        'hr',
        'hr_contract',
        'om_hr_payroll',      # Extends this module via inheritance
        'spreadsheet_oca',    # For Excel integration
        'website',           # For portal and web interfaces
        'account',           # For accounting integration
        'mail',              # For notifications and tracking
        'portal',            # For employee self-service
    ],
    'data': [
        # Security - Load First (Critical for multi-country access)
        'security/payroll_base_security.xml',
        'security/ir.model.access.csv',
        
        # Data - Enhanced structures and rules
        'data/payroll_base_data.xml',
        
        # Views - Enhanced models (extends om_hr_payroll models)
        # ✅ FIXED: Only include the main view file that contains ALL views
        'views/hr_payroll_structure_base_views.xml',  # Contains ALL views: payroll structures, salary rules, contract types
        # ❌ REMOVED: 'views/hr_salary_rule_base_views.xml',  # This was causing duplication
        # ❌ REMOVED: 'views/hr_contract_base_views.xml',     # This was also causing duplication
        
        # Views - Multi-country framework
        'views/payroll_base_dashboard.xml',
        'views/payroll_country_selector_template.xml',
        
        # Views - Zoho integration framework
        'views/zoho_base_views.xml',          # Contains basic Zoho views
        'views/zoho_staging_views.xml',       # ✅ ADDED: Extends base om_hr_payroll staging functionality
        # ❌ REMOVED: 'views/zoho_staging_views.xml',        # This was also causing duplication
        
        # Views - Additional actions and utilities
        'views/additional_actions.xml',
        
        # Menus - Load Last (Creates the main navigation)
        'views/payroll_menu_base.xml',
        
        # Zoho Menu Integration
        'views/zoho_menu_integration.xml',
    ],
    'demo': [
        'demo/payroll_structure_demo.xml',
        'demo/multi_country_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_hr_payroll_base/static/src/css/payroll_dashboard.css',
            'pb_hr_payroll_base/static/src/js/payroll_base.js',
            'pb_hr_payroll_base/static/src/js/country_selector.js',
        ],
        'web.assets_frontend': [
            'pb_hr_payroll_base/static/src/css/payroll_portal.css',
        ],
    },
    'external_dependencies': {
        'python': [],
    },
    'images': [
        'static/description/banner.png',
        'static/description/icon.png',
        'static/description/architecture.png',
        'static/description/dashboard_preview.png',
    ],
    
    # Module Configuration
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
    
    # Pricing and Support
    'price': 0.00,
    'currency': 'USD',
    'support': 'support@yourcompany.com',
    
    # Installation Hooks
    'post_init_hook': '_post_init_multi_country_setup',
    'uninstall_hook': '_cleanup_multi_country_data',
    
    # Module Dependencies and Loading
    'sequence': 10,  # Load early so country modules can depend on it
    'category': 'Human Resources/Payroll',
    
    # Version and Compatibility
    'version': '16.0.2.0.0',
    'depends_on_base': True,
    
    # Multi-Country Framework Metadata
    'supported_countries': ['VN', 'ID', 'IN', 'SG', 'MY'],
    'framework_version': '2.0',
    'architecture': 'inheritance_based',
    'base_module_modifications': False,
}