# -*- coding: utf-8 -*-
{
    'name': 'Payroll Base Framework - Enhanced',
    # 19.0.1.1.0 — Sudima Phase M: removed the CDN Chart.js entry from the
    # web.assets_backend list (asset-list change: needs a full service
    # RESTART, not an in-process upgrade — C18.53).
    'version': '19.0.1.1.0',
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
        # 'views/payroll_dashboard_enhanced_views.xml',           # TEMP DISABLED - Odoo 19 migration issue
        'views/payroll_menu_base.xml',                          # Base menu structure - Load after actions are defined
        'views/payroll_setup_guide.xml',                        # Setup guide for all countries
        'views/hr_payroll_structure_base_views.xml',            # HR payroll structure base views
        'views/additional_actions.xml',                         # Additional actions
        'views/payroll_base_dashboard.xml',                     # Base dashboard views
        'views/payroll_country_selector_enhanced.xml',          # Enhanced country selector
        'views/salary_configuration_workflow.xml',              # Salary configuration workflow dashboard
        # 'views/payroll_analytics_views.xml',                    # DISABLED - Search view errors need investigation
        # ZOHO VIEWS DISABLED - Models are disabled
        # 'views/zoho_base_views.xml',                            # Zoho base views
        # 'views/zoho_staging_views.xml',                         # Zoho staging views
        # 'views/zoho_menu_integration.xml',                      # Zoho menu integration - Load after base menus
    ],
    'assets': {
        'web.assets_backend': [
            # NEW Enhanced CSS and JS - DISABLED pending Odoo 19 migration
            # 'pb_hr_payroll_base/static/src/css/payroll_dashboard_enhanced.css',  # OLD OWL syntax
            # 'pb_hr_payroll_base/static/src/js/payroll_dashboard_enhanced.js',    # OLD OWL syntax
            'pb_hr_payroll_base/static/src/js/breadcrumb_override.js',           # Breadcrumb override for country selector
            'pb_hr_payroll_base/static/src/js/control_panel_home_icon.js',       # Control panel home icon

            # Chart.js: NO CDN. This asset list used to carry
            # 'https://cdnjs.cloudflare.com/.../Chart.js/3.9.1/chart.min.js',
            # which made EVERY backend page issue a cross-origin request (and
            # broke charts entirely on an offline/air-gapped install). Odoo
            # already bundles Chart.js locally in web.assets_backend
            # (web/static/lib/Chart) — verified live: window.Chart.version is
            # 4.4.6, i.e. Odoo's copy already wins over the CDN's 3.9.1, so the
            # entry was pure waste. Removed in Sudima Phase M. Never re-add a
            # remote URL to an asset list; vendor under static/lib/ instead.
            
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
            # 'pb_hr_payroll_base/static/src/css/payroll_dashboard_enhanced.css',  # DISABLED
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
