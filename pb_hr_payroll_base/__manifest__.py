# -*- coding: utf-8 -*-
{
    'name': 'Payroll Base Framework - Enhanced',
    'version': '16.0.2.0.0',
    'category': 'Human Resources/Payroll',
    'summary': 'Enhanced Multi-Country Payroll Base Framework with Professional Dashboard',
    'description': """
Enhanced Multi-Country Payroll Base Framework

This enhanced module provides a comprehensive base framework for multi-country payroll operations 
with professional Indonesia-style dashboard integration:

Key Features:
============
• Enhanced animated country selector with permission management
• Professional dashboard styling based on Indonesia theme (#21435F color scheme)
• Comprehensive analytics integration
• Multi-level access control with admin request system
• Responsive design with modern animations
• Country-specific payroll routing
• Unified Zoho integration framework
• Professional chart integration with Chart.js

Enhanced Dashboard Features:
============================
• Large animated country flags with hover effects
• Permission-based access indicators (✓ or 🔒)
• Ripple click effects and smooth animations
• Professional color scheme (#21435F - Navy Blue)
• Mobile-responsive design
• Loading overlays and progress indicators
• Admin contact system for access requests

Technical Improvements:
======================
• Optimized CSS/JS asset loading
• Removed unused asset files
• Consolidated styling from Indonesia module
• Enhanced JavaScript interactions
• QWeb template integration
• Professional animations and transitions

Supported Countries:
===================
• Vietnam (🇻🇳) - Full Access
• Indonesia (🇮🇩) - Full Access  
• India (🇮🇳) - Full Access
• Singapore (🇸🇬) - Request Access
• Malaysia (🇲🇾) - Request Access

Architecture:
=============
This base framework extends om_hr_payroll and provides shared components
for all country-specific modules while maintaining clean separation of concerns.
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': [
        'base',
        'hr',
        'hr_contract',
        'om_hr_payroll',
        'web',
        'website',  # For enhanced web templates
        'mail',     # REQUIRED: For messaging and notifications (mail.thread support)
    ],
    'data': [
        # Security - Load security files first
        'security/payroll_base_security_enhanced.xml',          # Security groups
        'security/ir.model.access.csv',                         # Access rights
        
        # Data
        'data/payroll_base_data.xml',
        'data/payroll_dashboard_data.xml',
        
        # Wizards - Load before views that reference them
        'wizards/analytics_wizard_views.xml',
        'wizards/employee_import_wizard_views.xml',
        'wizards/payroll_import_wizard_views.xml',
        
        # Views
        'views/payroll_menu_base.xml',                          # Base menu structure - Load first to define parent menus
        'views/hr_payroll_structure_base_views.xml',            # HR payroll structure base views
        'views/additional_actions.xml',                         # Additional actions
        'views/payroll_base_dashboard.xml',                     # Base dashboard views
        'views/payroll_dashboard_enhanced_views.xml',           # Enhanced dashboard with animations
        'views/payroll_country_selector_enhanced.xml',          # Enhanced country selector
        'views/payroll_analytics_views.xml',                    # Analytics views
        'views/zoho_base_views.xml',                            # Zoho base views
        'views/zoho_staging_views.xml',                         # Zoho staging views
        'views/zoho_menu_integration.xml',                      # Zoho menu integration - Load after base menus
    ],
    'assets': {
        'web.assets_backend': [
            # NEW Enhanced CSS and JS - Create these 2 files
            'pb_hr_payroll_base/static/src/css/payroll_dashboard_enhanced.css',  # CREATE THIS FILE
            'pb_hr_payroll_base/static/src/js/payroll_dashboard_enhanced.js',    # CREATE THIS FILE
            
            # Chart.js for analytics
            'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js',
            
            # OLD FILES REMOVED - Delete these files if they exist:
            # ❌ 'pb_hr_payroll_base/static/src/css/payroll_dashboard.css'
            # ❌ 'pb_hr_payroll_base/static/src/css/payroll_analytics.css'
            # ❌ 'pb_hr_payroll_base/static/src/js/payroll_base.js'
            # ❌ 'pb_hr_payroll_base/static/src/js/country_selector.js'
            # ❌ 'pb_hr_payroll_base/static/src/js/payroll_analytics.js'
            # ❌ 'pb_hr_payroll_base/static/src/js/payroll_charts.js'
        ],
        'web.assets_frontend': [
            # Frontend styling
            'pb_hr_payroll_base/static/src/css/payroll_dashboard_enhanced.css',
        ],
        # Remove QWeb section for now - can add later if needed
        # 'web.assets_qweb': [
        #     'pb_hr_payroll_base/static/src/xml/payroll_dashboard_templates.xml',
        # ],
    },
    'external_dependencies': {
        'python': [
            'requests',      # For API integrations
            'dateutil',      # For date calculations  
            # 'pillow',      # Commented out - uncomment if you use image processing
        ],
    },
    
    # Module Configuration
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
    
    # Enhanced Module Metadata
    'sequence': 100,
    
    # Asset Optimization Summary
    'asset_optimization': {
        'removed_files': [
            'static/src/css/payroll_dashboard.css',       # Replaced by enhanced version
            'static/src/css/payroll_analytics.css',       # Moved to analytics module  
            'static/src/js/payroll_base.js',              # Replaced by enhanced version
            'static/src/js/country_selector.js',          # Replaced by enhanced version
            'static/src/js/payroll_analytics.js',         # Moved to analytics module
            'static/src/js/payroll_charts.js',            # Integrated into enhanced version
        ],
        'new_files': [
            'views/payroll_dashboard_enhanced_views.xml',       # Enhanced dashboard views
            'views/payroll_country_selector_enhanced.xml',      # Enhanced country selector
            'static/src/css/payroll_dashboard_enhanced.css',    # Consolidated styling
            'static/src/js/payroll_dashboard_enhanced.js',      # Consolidated functionality
        ],
    },
}