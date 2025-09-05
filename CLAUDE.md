# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an **Odoo 16 Community Edition** multi-country HR Payroll system with enhanced spreadsheet functionality. The codebase consists of 7 interconnected modules providing comprehensive payroll management for companies operating across multiple countries (primarily Asia-Pacific region).

## Development Memories

- **Major Refactoring Completed (2024)**: Successfully consolidated menu structure and removed redundant menus
- All country modules working: Vietnam, India, Indonesia, Singapore, Thailand, Cambodia, Malaysia
- Menu structure cleaned up and centralized under original Payroll menu
- Setup guide moved to base module for all countries
- Analytics module integration completed
- **Cambodia & Malaysia Modules Created (2024)**: Professional payroll modules for Cambodia (NSSF) and Malaysia (EPF/SOCSO/EIS) successfully implemented and completed with full integration

## Current Architecture (Post-Refactoring)

### 🏗️ **Module Structure**
```
📦 Multi-Country Payroll System
├── 🏛️ om_hr_payroll (Original base)
├── 🌏 pb_hr_payroll_base (Enhanced base framework)
├── 🇻🇳 pb_hr_payroll_vietnam
├── 🇮🇩 pb_hr_payroll_indonesia  
├── 🇮🇳 pb_hr_payroll_india
├── 🇸🇬 pb_hr_payroll_singapore
├── 🇹🇭 pb_hr_payroll_thailand
├── 🇰🇭 pb_hr_payroll_cambodia
├── 🇲🇾 pb_hr_payroll_malaysia
└── 📊 payroll_analytics_approval (Optional)
```

### 🎯 **Final Menu Structure**
```
📁 Payroll (om_hr_payroll.menu_hr_payroll_root)
├── 📋 Setup Guide (All countries)
├── 📊 Dashboard
│   ├── Vietnam Dashboard
│   ├── India Dashboard  
│   ├── Indonesia Dashboard
│   ├── Singapore Dashboard
│   ├── Thailand Dashboard
│   ├── Cambodia Dashboard
│   └── Malaysia Dashboard
├── 👥 Employees
├── 📄 Payslips
├── 🔗 Zoho Integration
├── 📋 Reports
│   └── Payroll Analysis
├── 📈 Analytics (when payroll_analytics_approval installed)
│   ├── Approval Queue
│   ├── Bank Export
│   ├── Payroll Comparisons
│   └── Analytics Reports
├── Vietnam Social Insurance
├── India Gratuity Payments
├── Indonesia THR Payments
├── Singapore CPF Submission
├── Thailand SSF Reporting
├── Cambodia NSSF Processing
├── Malaysia EPF/SOCSO Submission
└── ⚙️ Configuration (from original om_hr_payroll)
```

### 🔐 **Security Groups (Base Module)**
```python
# pb_hr_payroll_base security groups
- group_payroll_base_user
- group_payroll_base_officer  
- group_payroll_base_manager
- group_payroll_super_admin
- group_payroll_vietnam
- group_payroll_indonesia
- group_payroll_india
- group_payroll_singapore
- group_payroll_thailand
- group_payroll_cambodia
- group_payroll_malaysia
- group_payroll_analytics_user
- group_payroll_analytics_manager
- group_payroll_integration_user
```

### 🎨 **Design Principles Applied**
1. **Single Source of Truth**: One main Payroll menu from om_hr_payroll
2. **No Redundancy**: Removed duplicate "Payroll Management" and "Multi-Country Payroll" menus
3. **Logical Grouping**: Country dashboards under Dashboard section, features under main menu
4. **Professional UI**: Consistent animations and styling across all dashboards
5. **Modular Architecture**: Base module handles shared functionality, country modules add specifics

### 📂 **Key Files and Their Purposes**

#### Base Module (pb_hr_payroll_base)
```
📁 pb_hr_payroll_base/
├── 🎯 views/payroll_menu_base.xml (Main menu structure)
├── 📋 views/payroll_setup_guide.xml (Universal setup guide)
├── 🔗 views/zoho_menu_integration.xml (Zoho integration menus)
├── 🏛️ models/payroll_dashboard_base.py (Core dashboard logic)
├── 🔐 security/payroll_base_security_enhanced.xml (All security groups)
└── 🎨 static/src/ (Shared CSS/JS assets)
```

#### Country Modules Pattern
```
📁 pb_hr_payroll_[country]/
├── 🎯 views/payroll_menu_structure.xml (Country-specific menus)
├── 📊 views/payroll_dashboard.xml (Country dashboard design)
├── 💰 data/hr_salary_rule_data.xml (Country tax rules)
├── 🏗️ data/hr_payroll_structure_data.xml (Payroll structures)
└── 🧙 wizards/ (Country-specific tools like SSF, CPF, etc.)
```

### 🚀 **Installation Order**
```bash
# 1. Install base modules first
pb_hr_payroll_base

# 2. Install country modules (any order)
pb_hr_payroll_vietnam
pb_hr_payroll_india  
pb_hr_payroll_indonesia
pb_hr_payroll_singapore
pb_hr_payroll_thailand
pb_hr_payroll_cambodia
pb_hr_payroll_malaysia

# 3. Optionally install analytics
payroll_analytics_approval
```

### 🎨 **Dashboard Features by Country**

#### Vietnam Dashboard
- Social Insurance calculations
- Health Insurance (HI) 
- Unemployment Insurance (UI)
- Personal Income Tax (PIT)
- Professional design with Vietnamese flag colors

#### India Dashboard  
- Provident Fund (PF) calculations
- Employee State Insurance (ESI)
- Professional Tax
- Income Tax (TDS)
- Gratuity payment wizard
- Indian Rupee (₹) currency

#### Indonesia Dashboard
- BPJS Kesehatan (Health Insurance)
- BPJS Ketenagakerjaan (Employment Insurance) 
- PPh 21 (Income Tax)
- THR (Religious Holiday Allowance) payments
- Indonesian Rupiah (Rp) currency

#### Singapore Dashboard
- Central Provident Fund (CPF) submissions
- Skills Development Levy (SDL)
- Foreign Worker Levy (FWL)
- Singapore Dollar (S$) currency

#### Thailand Dashboard
- Social Security Fund (SSF) reporting
- Provident Fund contributions
- Workmen's Compensation Fund
- Thai Baht (฿) currency

#### Cambodia Dashboard
- National Social Security Fund (NSSF) processing
- Occupational Risk Insurance
- Health Care Fund contributions
- Cambodian Riel (៛) currency

#### Malaysia Dashboard
- Employees Provident Fund (EPF) submissions
- Social Security Organisation (SOCSO) contributions
- Employment Insurance System (EIS)
- Malaysian Ringgit (RM) currency

### 🔄 **Key Integration Points**

#### Dashboard Routing Logic
```python
# pb_hr_payroll_base/models/payroll_dashboard_base.py:383-390
view_map = {
    'VN': 'pb_hr_payroll_vietnam.view_payroll_dashboard_vietnam',
    'ID': 'pb_hr_payroll_indonesia.view_payroll_dashboard_indonesia', 
    'IN': 'pb_hr_payroll_india.view_payroll_dashboard_india',
    'SG': 'pb_hr_payroll_singapore.view_payroll_dashboard_singapore',
    'TH': 'pb_hr_payroll_thailand.view_payroll_dashboard_thailand',
    'KH': 'pb_hr_payroll_cambodia.view_payroll_dashboard_cambodia',
    'MY': 'pb_hr_payroll_malaysia.view_payroll_dashboard_malaysia',
}
```

#### Country Access Control
```python
# pb_hr_payroll_base/controllers/payroll_controller.py
def _get_user_accessible_countries(self, user):
    accessible_countries = []
    if user.has_group('pb_hr_payroll_base.group_payroll_vietnam'):
        accessible_countries.append('VN')
    # ... other countries
    if user.has_group('base.group_system'):
        accessible_countries = ['VN', 'ID', 'IN', 'SG', 'MY', 'TH', 'KH']
    return accessible_countries
```

### 📊 **Analytics Integration**
When `payroll_analytics_approval` module is installed:
- Automatically adds Analytics section to main Payroll menu
- Provides approval workflows for payroll processing
- Bank export functionality
- Payroll comparison tools
- Advanced reporting capabilities

### 🛠️ **Development Commands**

#### Module Management
```bash
# Install/update modules during development
python -m odoo -c odoo.conf -d your_database -u pb_hr_payroll_base,pb_hr_payroll_vietnam

# Install new country module
python -m odoo -c odoo.conf -d your_database -i pb_hr_payroll_singapore

# Start development server with auto-reload
python -m odoo -c odoo.conf -d your_database --dev=reload,qweb,werkzeug,xml
```

#### Testing Menu Structure
```bash
# After installation, verify menu structure in UI:
# 1. Navigate to Payroll menu
# 2. Check Dashboard section has all country dashboards
# 3. Verify Setup Guide is accessible
# 4. Test country-specific features (SSF, CPF, etc.)
```

### 🚨 **Critical Design Decisions Made**

1. **Eliminated Redundant Menus**: Removed "Payroll Management" and "Multi-Country Payroll" root menus
2. **Centralized Under Original Menu**: Everything now under `om_hr_payroll.menu_hr_payroll_root`
3. **Dashboard Section Pattern**: All country dashboards under `pb_hr_payroll_base.menu_payroll_dashboard_section`
4. **Setup Guide Centralization**: Moved from individual modules to base module
5. **Analytics Conditional Loading**: Analytics only appears when optional module is installed
6. **Security Group Centralization**: All groups defined in base module for consistency

### 🎯 **Future Development Guidelines**

#### Adding New Countries
1. Follow existing country module pattern
2. Add dashboard under `pb_hr_payroll_base.menu_payroll_dashboard_section`
3. Add country-specific features under main `om_hr_payroll.menu_hr_payroll_root`
4. Update setup guide in base module
5. Add security group in base module
6. Update dashboard routing logic in base module

#### Menu Structure Rules
- ✅ Use `om_hr_payroll.menu_hr_payroll_root` as main parent
- ✅ Use `pb_hr_payroll_base.menu_payroll_dashboard_section` for dashboards
- ✅ Use appropriate security groups: `pb_hr_payroll_base.group_payroll_[country]`
- ❌ Never create new root menus
- ❌ Never reference non-existent parent menus

#### Best Practices
- Always test menu installation order
- Verify security group permissions
- Maintain consistent naming patterns
- Update CLAUDE.md when making architectural changes
- Follow the established dashboard design patterns

### 🔍 **Troubleshooting Common Issues**

#### Menu Not Appearing
- Check if parent menu exists (`om_hr_payroll.menu_hr_payroll_root`)
- Verify security groups are correctly assigned
- Ensure proper installation order (base → countries → analytics)

#### Dashboard Routing Issues  
- Update view mapping in `payroll_dashboard_base.py`
- Check external ID references are correct
- Verify dashboard views are properly defined

#### Security Access Problems
- Ensure users have appropriate country groups
- Check if base module security groups are loaded
- Verify group inheritance is working

This architecture provides a scalable, maintainable foundation for multi-country payroll management while maintaining clean separation of concerns and professional user experience.

## ✅ **COMPLETED IMPLEMENTATION STATUS (2024)**

### All Country Modules Successfully Created and Integrated:
- ✅ **Cambodia Module (`pb_hr_payroll_cambodia`)**: Complete implementation with NSSF management, professional dashboard, and KHR currency support
- ✅ **Malaysia Module (`pb_hr_payroll_malaysia`)**: Complete implementation with EPF/SOCSO/EIS, professional dashboard, and MYR currency support
- ✅ **Base Module Updates**: Both countries fully integrated in dashboard routing, controller access, and security framework
- ✅ **Professional UI**: Consistent animated dashboards with proper currency symbols (៛ and RM)
- ✅ **Security Integration**: Cambodia and Malaysia security groups centralized in base module
- ✅ **Controller Support**: Both countries added to all controller methods for full functionality

### Technical Implementation Details:

#### Cambodia Module Features:
- **NSSF Processing**: National Social Security Fund calculations and reporting
- **Professional Dashboard**: Animated interface with Cambodian Riel (៛) currency display
- **Compliance Features**: Local labor law compliance and government reporting
- **Wizard Tools**: NSSF processing wizard for batch operations
- **Security Integration**: Proper access control through `group_payroll_cambodia`

#### Malaysia Module Features:  
- **EPF Management**: Employees Provident Fund calculations and submissions
- **SOCSO Integration**: Social Security Organisation compliance
- **EIS Support**: Employment Insurance System processing
- **Professional Dashboard**: Animated interface with Malaysian Ringgit (RM) currency display
- **Wizard Tools**: EPF processing wizard for batch operations
- **Security Integration**: Proper access control through `group_payroll_malaysia`

#### Controller Updates Made:
- Added KH and MY to `_get_user_accessible_countries()` method
- Updated `_create_default_dashboard()` to support Cambodia and Malaysia
- Extended `_get_country_currency()` to include KHR and MYR mapping
- Added Cambodia and Malaysia to spreadsheet URL mapping
- Updated access rights checking for both countries

The multi-country payroll system is now **COMPLETE** with all 7 countries fully implemented, tested, and ready for production use.

## 🚀 **COMPREHENSIVE GUIDE FOR ADDING NEW COUNTRIES**

Based on learnings from implementing Cambodia and Malaysia modules, here's the complete step-by-step guide for adding new countries to the system:

### **Phase 1: Module Structure Setup**

#### 1.1 Create Module Directory Structure
```bash
📁 pb_hr_payroll_[country_code]/
├── __init__.py
├── __manifest__.py
├── 📁 models/
│   ├── __init__.py
│   ├── hr_payslip_[country].py (Main payslip model)
│   ├── hr_payroll_structure.py (Payroll structures)
│   ├── hr_zoho.py (Zoho integration)
│   ├── zoho_employee_data.py (Employee data staging)
│   ├── zoho_staging_data.py (Payroll staging)
│   └── res_users.py (User access extensions)
├── 📁 wizards/
│   ├── __init__.py
│   ├── [compliance_system]_wizard.py (e.g., epf_wizard.py, nssf_wizard.py)
│   └── payroll_import_wizard.py (Data import tools)
├── 📁 views/
│   ├── payroll_dashboard.xml (Professional dashboard)
│   ├── payroll_menu_structure.xml (Menu integration)
│   ├── [compliance_system]_wizard_views.xml (Wizard views)
│   └── [other country-specific views].xml
├── 📁 data/
│   ├── payroll_dashboard_data.xml (Dashboard record)
│   ├── hr_payroll_structure_data.xml (Salary structures)
│   ├── hr_salary_rule_data.xml (Tax rules)
│   └── hr_salary_rule_category_data.xml (Categories)
├── 📁 security/
│   ├── ir.model.access.csv (Model permissions)
│   └── [additional security files]
└── 📁 static/src/ (Optional: country-specific assets)
```

#### 1.2 Module Manifest Template (`__manifest__.py`)
```python
{
    'name': '[Country] HR Payroll',
    'version': '16.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Professional [Country] payroll management with [compliance systems]',
    'description': """
        Complete [Country] Payroll Management System
        ==========================================
        
        Features:
        * [Country compliance system] calculations
        * Professional animated dashboard
        * [Local currency] support
        * Government reporting tools
        * Zoho People integration
        * Bank export functionality
    """,
    'depends': [
        'om_hr_payroll',
        'pb_hr_payroll_base',
        'spreadsheet_oca',
        'hr_contract',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/hr_salary_rule_category_data.xml',
        'data/hr_payroll_structure_data.xml', 
        'data/hr_salary_rule_data.xml',
        'data/payroll_dashboard_data.xml',
        'wizards/[compliance]_wizard_views.xml',
        'views/payroll_dashboard.xml',
        'views/payroll_menu_structure.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
```

### **Phase 2: Core Model Implementation**

#### 2.1 Main Payslip Model (`models/hr_payslip_[country].py`)
```python
# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class HrPayslip[Country](models.Model):
    _name = 'hr.payslip.[country]'
    _description = '[Country] Payslip Extensions'
    _inherit = 'hr.payslip'

    # Country-specific compliance fields
    [compliance_field_1] = fields.Float('[Compliance System 1]', compute='_compute_compliance_1')
    [compliance_field_2] = fields.Float('[Compliance System 2]', compute='_compute_compliance_2')
    
    # Currency and country identification
    country_code = fields.Char(default='[CC]', readonly=True)
    local_currency_id = fields.Many2one('res.currency', 
                                       default=lambda self: self._get_local_currency())

    def _get_local_currency(self):
        """Get [country] currency"""
        currency = self.env['res.currency'].search([('name', '=', '[CURRENCY_CODE]')], limit=1)
        return currency or self.env.company.currency_id

    @api.depends('line_ids')
    def _compute_compliance_1(self):
        """Compute [compliance system 1] contributions"""
        for record in self:
            # Implementation specific to country's compliance system
            record.[compliance_field_1] = 0.0

    @api.depends('line_ids')  
    def _compute_compliance_2(self):
        """Compute [compliance system 2] contributions"""
        for record in self:
            # Implementation specific to country's compliance system
            record.[compliance_field_2] = 0.0
```

#### 2.2 Compliance Wizard (`wizards/[compliance]_wizard.py`)
```python
# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class [Compliance]Wizard(models.TransientModel):
    _name = '[compliance].wizard'
    _description = '[Country] [Compliance System] Processing Wizard'

    payroll_period = fields.Selection([
        ('current_month', 'Current Month'),
        ('previous_month', 'Previous Month'),
        ('custom', 'Custom Period')
    ], default='current_month', required=True)
    
    date_from = fields.Date('Date From')
    date_to = fields.Date('Date To')
    include_benefits = fields.Boolean('Include Benefits', default=True)
    
    def action_process_[compliance](self):
        """Process [compliance system] calculations"""
        # Get payslips for the period
        domain = self._get_payslip_domain()
        payslips = self.env['hr.payslip'].search(domain)
        
        if not payslips:
            raise ValidationError(_('No payslips found for the selected period.'))
        
        # Process compliance calculations
        self._calculate_[compliance]_contributions(payslips)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('[Compliance] processing completed for %s employees') % len(payslips),
                'type': 'success',
                'sticky': False,
            }
        }

    def _get_payslip_domain(self):
        """Build domain for payslip selection"""
        if self.payroll_period == 'current_month':
            # Logic for current month
            pass
        # Additional domain logic
        return []

    def _calculate_[compliance]_contributions(self, payslips):
        """Calculate [compliance system] specific contributions"""
        for payslip in payslips:
            # Country-specific calculation logic
            pass
```

### **Phase 3: Professional Dashboard Implementation**

#### 3.1 Dashboard View Template (`views/payroll_dashboard.xml`)
```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    
    <!-- Professional [Country] Dashboard View -->
    <record id="view_payroll_dashboard_[country]" model="ir.ui.view">
        <field name="name">[Country] Payroll Dashboard Professional</field>
        <field name="model">payroll.dashboard</field>
        <field name="priority">[priority_number]</field>
        <field name="arch" type="xml">
            <form string="[Country] Payroll Dashboard" create="false" edit="false" delete="false">
                <header>
                    <field name="name" invisible="1"/>
                </header>
                <sheet>
                    <!-- Enhanced Button Box with Header Tiles -->
                    <div class="oe_button_box" name="button_box">
                        <button class="oe_stat_button" type="object" name="action_view_employees_by_country" icon="fa-users">
                            <field string="Employees" name="total_employees" widget="statinfo"/>
                        </button>
                        <button class="oe_stat_button" type="object" name="action_view_payslips_by_country" icon="fa-file-text">
                            <field string="Payslips" name="pending_payslips" widget="statinfo"/>
                        </button>
                        <button class="oe_stat_button" type="object" name="action_view_contracts_by_country" icon="fa-dollar">
                            <div class="o_field_widget o_stat_info">
                                <span class="o_stat_value">[CURRENCY_SYMBOL] <field name="total_payroll" widget="monetary" options="{'currency_field': 'currency_id', 'no_symbol': True}"/></span>
                                <span class="o_stat_text">Total Payroll</span>
                            </div>
                        </button>
                        <button class="oe_stat_button" type="object" name="action_view_analytics" icon="fa-trending-up">
                            <div class="o_field_widget o_stat_info">
                                <span class="o_stat_value">[CURRENCY_SYMBOL] <field name="average_salary" widget="monetary" options="{'currency_field': 'currency_id', 'no_symbol': True}"/></span>
                                <span class="o_stat_text">Average Salary</span>
                            </div>
                        </button>
                    </div>
                    
                    <!-- Professional CSS Styling (Copy from Cambodia/Malaysia examples) -->
                    <style>
                        /* Insert professional CSS animations and styling here */
                        .dashboard-container { background: #f8f9fa; padding: 24px; border-radius: 8px; }
                        .dashboard-title { color: #2c3e50; font-size: 28px; font-weight: 600; margin: 0; letter-spacing: -0.5px; }
                        .dashboard-card { background: white; border: 1px solid #e9ecef; border-radius: 12px; padding: 24px; box-shadow: 0 2px 4px rgba(0,0,0,0.04); }
                        .dashboard-btn { background: #21435F; color: white !important; padding: 12px 24px; border-radius: 6px; }
                        /* Add animations and responsive design */
                    </style>
                    
                    <div class="dashboard-container">
                        <div class="dashboard-header">
                            <h1 class="dashboard-title">[Country] Payroll Management</h1>
                            <p class="dashboard-subtitle">Manage payroll operations for [Country] region</p>
                        </div>
                        
                        <!-- Dashboard Cards with Actions -->
                        <div class="row">
                            <!-- Main workflow cards -->
                            <div class="col-lg-4">
                                <div class="dashboard-card">
                                    <i class="fa fa-users fa-3x card-icon"/>
                                    <h4 class="card-title">Employee Data</h4>
                                    <p class="card-description">Import employee information from Zoho People</p>
                                    <button name="action_get_employee_data" type="object" class="dashboard-btn">
                                        Import employee data
                                    </button>
                                </div>
                            </div>
                            
                            <!-- Additional cards for country-specific features -->
                            <div class="col-lg-4">
                                <div class="dashboard-card">
                                    <i class="fa fa-shield fa-3x card-icon"/>
                                    <h4 class="card-title">[Compliance System] Management</h4>
                                    <p class="card-description">Process [Country] [compliance system] calculations and compliance</p>
                                    <button name="action_process_payroll" type="object" class="dashboard-btn">
                                        Process [Compliance]
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </sheet>
            </form>
        </field>
    </record>
    
</odoo>
```

#### 3.2 Menu Integration (`views/payroll_menu_structure.xml`)
```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    
    <!-- [Country] Dashboard Actions -->
    <record id="action_[country]_dashboard_window" model="ir.actions.act_window">
        <field name="name">Open [Country] Payroll Dashboard</field>
        <field name="res_model">payroll.dashboard</field>
        <field name="view_mode">form</field>
        <field name="view_id" ref="view_payroll_dashboard_[country]"/>
        <field name="target">current</field>
        <field name="res_id" ref="[country]_payroll_dashboard"/>
        <field name="context">{'create': False, 'edit': False, 'delete': False, 'default_country': '[CC]'}</field>
        <field name="domain">[('country', '=', '[CC]')]</field>
    </record>
    
    <!-- [Compliance System] Action -->
    <record id="action_[compliance]_wizard" model="ir.actions.act_window">
        <field name="name">[Compliance System Display Name] Wizard</field>
        <field name="res_model">[compliance].wizard</field>
        <field name="view_mode">form</field>
        <field name="target">new</field>
        <field name="context">{'default_payroll_country': '[CC]'}</field>
    </record>
    
    <!-- [Country] Dashboard Menu under base dashboard section -->
    <menuitem id="menu_[country]_dashboard"
              name="[Country] Dashboard"
              parent="pb_hr_payroll_base.menu_payroll_dashboard_section"
              action="action_[country]_dashboard_window"
              sequence="[sequence_number]"
              groups="pb_hr_payroll_base.group_payroll_[country]"/>
    
    <!-- [Country] [Compliance] Menu under original Payroll menu -->
    <menuitem id="menu_[country]_[compliance]"
              name="[Country] [Compliance Display Name]"
              parent="om_hr_payroll.menu_hr_payroll_root"
              action="action_[compliance]_wizard"
              sequence="[sequence_number]"
              groups="pb_hr_payroll_base.group_payroll_[country]"/>
    
</odoo>
```

#### 3.3 Dashboard Data Record (`data/payroll_dashboard_data.xml`)
```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <data noupdate="1">
        <!-- [Country]-specific dashboard record -->
        <record id="[country]_payroll_dashboard" model="payroll.dashboard">
            <field name="name">[Country] Payroll Dashboard</field>
            <field name="country">[CC]</field>
            <field name="sequence">[sequence_number]</field>
            <field name="active">True</field>
            <field name="auto_refresh">True</field>
            <field name="refresh_interval">60</field>
            <!-- Country-specific fields can be added here -->
        </record>
    </data>
</odoo>
```

### **Phase 4: Base Module Integration**

#### 4.1 Update Dashboard Routing (`pb_hr_payroll_base/models/payroll_dashboard_base.py`)
```python
# Add to view_map in action_view_country_dashboard method:
view_map = {
    # ... existing countries ...
    '[CC]': 'pb_hr_payroll_[country].view_payroll_dashboard_[country]',
}
```

#### 4.2 Update Controller Access (`pb_hr_payroll_base/controllers/payroll_controller.py`)
```python
# Add to _get_user_accessible_countries method:
if user.has_group('pb_hr_payroll_base.group_payroll_[country]'):
    accessible_countries.append('[CC]')

# Add to _create_default_dashboard method:
country_names = {
    # ... existing countries ...
    '[CC]': '[Country] Payroll Dashboard',
}

# Add to _get_country_currency method:
currency_map = {
    # ... existing currencies ...
    '[CC]': '[CURRENCY_CODE]'
}

# Add to access_rights in country_selector method:
access_rights = {
    # ... existing countries ...
    '[CC]': user.has_group('pb_hr_payroll_base.group_payroll_[country]') or user.has_group('pb_hr_payroll_base.group_payroll_base_manager'),
}
```

#### 4.3 Update Country Selector (`pb_hr_payroll_base/views/payroll_country_selector_enhanced.xml`)
```xml
<!-- Add to country_flags t-value dictionary: -->
'[CC]': '[FLAG_EMOJI]'

<!-- Add to currency_symbols t-value dictionary: -->
'[CC]': '[CURRENCY_SYMBOL]'

<!-- Add to descriptions t-value dictionary: -->
'[CC]': '[Country] payroll system with [compliance systems] and [currency] currency support.'

<!-- Add navigation case in JavaScript: -->
case '[CC]':
    url = '/web#action=pb_hr_payroll_[country].action_[country]_dashboard_window';
    break;
```

#### 4.4 Update Enhanced Dashboard Views (`pb_hr_payroll_base/views/payroll_dashboard_enhanced_views.xml`)
```xml
<!-- Add flag to kanban template: -->
<t t-if="record.country.raw_value == '[CC]'">[FLAG_EMOJI]</t>

<!-- Add currency display: -->
<t t-if="record.country.raw_value == '[CC]'">[CURRENCY_SYMBOL] <t t-esc="record.total_payroll.raw_value"/></t>
```

#### 4.5 Add Security Group (`pb_hr_payroll_base/security/payroll_base_security_enhanced.xml`)
```xml
<record id="group_payroll_[country]" model="res.groups">
    <field name="name">[Country] Payroll Access</field>
    <field name="category_id" ref="base.module_category_human_resources"/>
    <field name="implied_ids" eval="[(4, ref('group_payroll_base_user'))]"/>
    <field name="comment">Access to [Country] payroll system</field>
</record>
```

### **Phase 5: Testing and Validation**

#### 5.1 Installation Testing Checklist
- [ ] Base module installs without errors
- [ ] Country module installs after base module
- [ ] Dashboard appears in country selector
- [ ] Country flag displays correctly
- [ ] Currency symbols show properly
- [ ] Menu structure is correct
- [ ] Security groups are applied
- [ ] Dashboard actions work

#### 5.2 Functional Testing Checklist  
- [ ] Dashboard statistics display
- [ ] Country-specific compliance calculations
- [ ] Wizard functionality works
- [ ] Data import/export functions
- [ ] Bank file generation
- [ ] Report generation
- [ ] Multi-user access control

### **Phase 6: Country-Specific Examples**

#### Common Compliance Systems by Region:

**Asia-Pacific:**
- **Philippines (PH)**: SSS, PhilHealth, Pag-IBIG, BIR taxes
- **Hong Kong (HK)**: MPF (Mandatory Provident Fund)
- **Taiwan (TW)**: Labor Insurance, National Health Insurance
- **South Korea (KR)**: National Pension Service, Health Insurance

**Europe:**
- **United Kingdom (GB)**: PAYE, National Insurance
- **Germany (DE)**: Social Security, Health Insurance, Pension Insurance
- **France (FR)**: URSSAF, ASSEDIC

**Americas:**
- **Brazil (BR)**: INSS, FGTS, IR taxes
- **Mexico (MX)**: IMSS, INFONAVIT, ISR taxes
- **Canada (CA)**: CPP, EI, Income Tax

### **Phase 7: Deployment Guidelines**

#### 7.1 Module Packaging
```bash
# Create installable module package
cd pb_hr_payroll_[country]/
zip -r pb_hr_payroll_[country].zip . -x "*.pyc" "__pycache__/*"
```

#### 7.2 Installation Commands
```bash
# Install via Odoo CLI
python -m odoo -c odoo.conf -d database -i pb_hr_payroll_[country]

# Update existing installation  
python -m odoo -c odoo.conf -d database -u pb_hr_payroll_[country]
```

This comprehensive guide ensures consistent, professional implementation of new country modules following the established architectural patterns and design principles.

# 🔧 **SALARY COMPONENT MAPPING & REFACTORING DOCUMENTATION**

## **Problem Analysis (2024) - Spreadsheet Import Mapping Issues**

### **Root Cause Identified:**
The spreadsheet import system has **critical misalignment** between salary codes, data models, and country-specific implementations. This causes salary components to show 0.00 values after import despite successful data processing.

### **Current Architecture Analysis:**

#### **Data Flow Overview:**
```
Spreadsheet Import → zoho.employee.data → update_payslip_lines_from_zoho_data() → Payslip Lines
```

#### **Key Components:**
1. **Salary Rule Definitions** (`/om_hr_payroll/data/hr_payroll_data.xml`)
2. **Field Mapping Logic** (`/om_hr_payroll/models/hr_payslip.py`)
3. **Data Storage Model** (`/om_hr_payroll/models/hr_zoho.py`)
4. **Import Process** (`/spreadsheet_oca/models/spreadsheet_spreadsheet.py`)

## **Component Misalignment Issues**

### **Vietnam Salary Structure vs. Mapping Disconnect:**

#### **Salary Rules Defined (16 components):**
- `BASIC, HRA, DA, Travel, Meal, Medical, TRANSPORT, GROSS`
- `SI_EMP, HI_EMP, UI_EMP, PIT, NET`
- `SI_COMP, HI_COMP, UI_COMP`

#### **Actual Salary Codes in System (58+ codes):**
```
SEVAPP, LAINALL, DEDUC1, DEDUC2, NET_VN, DEDUC3, CICIL, LAINDED, KOPER, PINJAM,
BASIC_VN, HOUSING_VN, Meal, Medical, Travel, TRANSPORT_VN, PIT_VN, SS_VN, 
HI_EMP, UI_EMP, TRANSPORT, PIT, HI_COMP, UI_COMP, SI_EMP, BASIC, SI_COMP,
CPF_EE, SSF_EE, CPF_ER, NET, PF, SSF_ER, FIXALL1, GROSS, TUNJSK, HRA, DA,
IDN_GROSS, PPH21, BPJS_KES_EMP, BPJS_JHT_EMP, BPJS_JP_EMP, UNION_DUES, 
LOAN_DED, BPJS_JHT_COMP, BPJS_JKM, BPJS_JKK, BPJS_JP_COMP, BPJS_KES_COMP,
FIXALL2, COMMIS, SIGBON, TUNJSR, TUNJDK
```

#### **Current Field Mapping (Only ~30 mappings):**
```python
# /om_hr_payroll/models/hr_payslip.py - update_payslip_lines_from_zoho_data()
field_mapping = {
    'ACTBASE': 'actual_basicsalary',
    'MIONEFIVE': 'med_ins15',         # Indonesia legacy
    'NETPAY': 'net_pay',              # Generic
    'MONPIT': 'monthly_pit',          # Vietnam PIT
    # MISSING: BASIC_VN, HOUSING_VN, TRANSPORT_VN, PIT_VN, SS_VN, NET_VN, etc.
}
```

### **The Gap:**
- **Missing Vietnam Mappings**: 40+ Vietnam codes not mapped
- **Country Code Inconsistency**: Mixed naming patterns (BASIC vs BASIC_VN)
- **Field Alignment**: zoho.employee.data fields don't match salary codes
- **Legacy vs New**: Old Indonesia codes mixed with new Vietnam codes

## **Country-Specific Salary Code Analysis**

### **Vietnam (VN) Pattern:**
```
Primary Codes: BASIC_VN, HOUSING_VN, TRANSPORT_VN, PIT_VN, SS_VN, NET_VN
Generic Codes: BASIC, HRA, DA, Travel, Meal, Medical, TRANSPORT, GROSS, NET
Insurance Codes: SI_EMP, HI_EMP, UI_EMP, SI_COMP, HI_COMP, UI_COMP
```

### **Indonesia (ID) Pattern:**
```
Legacy Codes: MIONEFIVE, LAINALL, BPJS_KES_EMP, BPJS_JHT_EMP, PPH21
New Structure: Should follow BASIC_ID, BPJS_KES_ID, BPJS_JHT_ID pattern
```

### **Multi-Country Codes:**
```
Generic: BASIC, GROSS, NET, PF, UNION_DUES, LOAN_DED
Singapore: CPF_EE, CPF_ER, SDL_SG
Thailand: SSF_EE, SSF_ER, PF_TH
Indonesia: BPJS_*, PPH21, IDN_GROSS
```

## **Refactoring Strategy**

### **Phase 1: Country-Specific Architecture**

#### **1.1 Standardized Code Patterns**
Implement consistent salary code structure:
```
Country Format: [COMPONENT]_[COUNTRY_CODE]
Examples:
- Vietnam: BASIC_VN, HOUSING_VN, TRANSPORT_VN, PIT_VN, SS_VN
- Indonesia: BASIC_ID, BPJS_KES_ID, BPJS_JHT_ID, PPH21_ID  
- India: BASIC_IN, PF_IN, ESI_IN, TDS_IN
- Singapore: BASIC_SG, CPF_EE_SG, SDL_SG
- Thailand: BASIC_TH, SSF_EE_TH, PF_TH
- Cambodia: BASIC_KH, NSSF_KH
- Malaysia: BASIC_MY, EPF_MY, SOCSO_MY
```

#### **1.2 Dynamic Country Detection**
Country-aware mapping implementation:
```python
def get_country_field_mapping(self, country_code):
    """Return country-specific field mappings"""
    mappings = {
        'VN': self._get_vietnam_mapping(),
        'ID': self._get_indonesia_mapping(),
        'IN': self._get_india_mapping(),
        'SG': self._get_singapore_mapping(),
        'TH': self._get_thailand_mapping(),
        'KH': self._get_cambodia_mapping(),
        'MY': self._get_malaysia_mapping(),
    }
    return mappings.get(country_code, self._get_default_mapping())
```

### **Phase 2: Data Model Alignment**

#### **2.1 ZohoEmployeeData Model Extensions**
Country-specific field additions:
```python
class ZohoEmployeeData(models.Model):
    _name = 'zoho.employee.data'
    
    # Vietnam-specific salary components
    basic_vn = fields.Float(string="Basic Salary (VN)")
    housing_vn = fields.Float(string="Housing Allowance (VN)")
    transport_vn = fields.Float(string="Transport Allowance (VN)")
    pit_vn = fields.Float(string="Personal Income Tax (VN)")
    ss_vn = fields.Float(string="Social Security (VN)")
    net_vn = fields.Float(string="Net Pay (VN)")
    
    # Indonesia-specific salary components
    basic_id = fields.Float(string="Basic Salary (ID)")
    bpjs_kes_id = fields.Float(string="BPJS Healthcare (ID)")
    bpjs_jht_id = fields.Float(string="BPJS JHT (ID)")
    pph21_id = fields.Float(string="PPh21 Tax (ID)")
    
    # Other countries...
    basic_in = fields.Float(string="Basic Salary (IN)")
    pf_in = fields.Float(string="Provident Fund (IN)")
    
    # Generic calculated fields (existing - keep for compatibility)
    actual_basicsalary = fields.Float(string="Actual basic salary")
    monthly_pit = fields.Float(string="Monthly PIT")
    net_pay = fields.Float(string="Net pay")
```

#### **2.2 Salary Rule Structure Alignment**
Ensure salary rules match actual codes:
```xml
<!-- Vietnam Country-Specific Rules -->
<record id="hr_rule_basic_vn" model="hr.salary.rule">
    <field name="code">BASIC_VN</field>
    <field name="name">Basic Salary (Vietnam)</field>
    <field name="sequence" eval="1"/>
    <field name="category_id" ref="om_hr_payroll.BASIC"/>
    <field name="amount_select">fix</field>
    <field name="amount_fix">0.00</field>
</record>

<record id="hr_rule_housing_vn" model="hr.salary.rule">
    <field name="code">HOUSING_VN</field>
    <field name="name">Housing Allowance (Vietnam)</field>
    <field name="sequence" eval="3"/>
    <field name="category_id" ref="om_hr_payroll.ALW"/>
    <field name="amount_select">fix</field>
    <field name="amount_fix">0.00</field>
</record>
```

### **Phase 3: Comprehensive Field Mapping**

#### **3.1 Complete Vietnam Mapping**
Map all Vietnam salary codes:
```python
def _get_vietnam_mapping(self):
    """Complete Vietnam salary code to field mapping"""
    return {
        # Country-specific codes
        'BASIC_VN': 'basic_vn',
        'HOUSING_VN': 'housing_vn', 
        'TRANSPORT_VN': 'transport_vn',
        'PIT_VN': 'pit_vn',
        'SS_VN': 'ss_vn',
        'NET_VN': 'net_vn',
        
        # Generic codes used in Vietnam
        'BASIC': 'actual_basicsalary',
        'HRA': 'actual_gas',           # Housing = Gas allowance
        'TRANSPORT': 'actual_taxi',    # Transport = Taxi allowance
        'PIT': 'monthly_pit',
        'NET': 'net_pay',
        
        # Insurance codes  
        'SI_EMP': 'social_ins8',
        'HI_EMP': 'med_ins15',
        'UI_EMP': 'unemp_ins1',
        'SI_COMP': 'social_ins175',
        'HI_COMP': 'med_ins3',
        'UI_COMP': 'unemp_ins1',
        
        # Deduction codes
        'DEDUC1': 'deduc1_amount',
        'DEDUC2': 'deduc2_amount', 
        'DEDUC3': 'deduc3_amount',
        
        # Other Vietnam-specific codes
        'SEVAPP': 'sevapp_amount',
        'LAINALL': 'lainall_amount',
        'CICIL': 'cicil_amount',
        'LAINDED': 'lainded_amount',
        'KOPER': 'koper_amount',
        'PINJAM': 'pinjam_amount',
    }
```

#### **3.2 Indonesia Mapping**
```python
def _get_indonesia_mapping(self):
    """Complete Indonesia salary code to field mapping"""
    return {
        # Legacy codes (maintain compatibility)
        'MIONEFIVE': 'med_ins15',
        'LAINALL': 'lainall_amount',
        
        # BPJS codes
        'BPJS_KES_EMP': 'bpjs_kes_emp',
        'BPJS_JHT_EMP': 'bpjs_jht_emp', 
        'BPJS_JP_EMP': 'bpjs_jp_emp',
        'BPJS_KES_COMP': 'bpjs_kes_comp',
        'BPJS_JHT_COMP': 'bpjs_jht_comp',
        'BPJS_JP_COMP': 'bpjs_jp_comp',
        'BPJS_JKM': 'bpjs_jkm',
        'BPJS_JKK': 'bpjs_jkk',
        
        # Tax and other codes
        'PPH21': 'pph21_amount',
        'IDN_GROSS': 'idn_gross_amount',
        'UNION_DUES': 'union_dues',
        'LOAN_DED': 'loan_deduction',
    }
```

#### **3.3 Legacy Compatibility Layer**
```python
def _get_legacy_mapping(self):
    """Maintain backward compatibility with existing codes"""
    return {
        # Keep all existing mappings
        'ACTBASE': 'actual_basicsalary',
        'NETPAY': 'net_pay',
        'MONPIT': 'monthly_pit',
        'TOTDEDU': 'total_ded',
        'SIEIGHT': 'social_ins8',
        'EMPTU': 'etu',
        # ... all current mappings preserved
    }
```

### **Phase 4: Enhanced Import Process**

#### **4.1 Country-Aware Import Logic**
```python
def import_json_data(self):
    """Enhanced import with country detection"""
    # Get country context
    payroll_country = self.env.context.get('payroll_country', 'VN')
    
    # Load country-specific mappings
    salary_field_mappings = self._get_country_salary_mappings(payroll_country)
    
    # Process spreadsheet data with country-aware field mapping
    for salary_code, amount in salary_data.items():
        field_name = salary_field_mappings.get(salary_code)
        if field_name:
            field_value_dict[field_name] = amount
        else:
            _logger.warning(f"Unmapped salary code for {payroll_country}: {salary_code}")
```

#### **4.2 Validation and Error Handling**
```python
def _validate_salary_codes(self, salary_codes, country_code):
    """Validate salary codes against country expectations"""
    expected_codes = self._get_expected_codes_for_country(country_code)
    actual_codes = set(salary_codes)
    
    missing_codes = expected_codes - actual_codes
    unmapped_codes = actual_codes - expected_codes
    
    if missing_codes:
        _logger.warning(f"Missing expected {country_code} codes: {missing_codes}")
    
    if unmapped_codes:
        _logger.warning(f"Unmapped {country_code} codes: {unmapped_codes}")
    
    return len(missing_codes) == 0
```

### **Phase 5: Analytics Integration**

#### **5.1 Country-Specific Component Recognition**
```python
def _generate_analytics_data(self, payslips, country, date_from, date_to):
    """Enhanced analytics with full country code support"""
    
    # Get comprehensive country-specific component codes
    country_components = {
        'VN': ['BASIC', 'BASIC_VN', 'HOUSING_VN', 'TRANSPORT_VN', 'PIT_VN', 
               'SS_VN', 'NET_VN', 'SI_EMP', 'HI_EMP', 'UI_EMP', 'SI_COMP', 
               'HI_COMP', 'UI_COMP', 'SEVAPP', 'LAINALL', 'DEDUC1', 'DEDUC2', 'DEDUC3'],
               
        'ID': ['BASIC', 'MIONEFIVE', 'BPJS_KES_EMP', 'BPJS_JHT_EMP', 'BPJS_JP_EMP',
               'BPJS_KES_COMP', 'BPJS_JHT_COMP', 'BPJS_JP_COMP', 'PPH21', 'IDN_GROSS',
               'UNION_DUES', 'LOAN_DED', 'LAINALL'],
               
        'IN': ['BASIC', 'HRA', 'DA', 'PF_EMP', 'ESI_EMP', 'PT', 'TDS', 'NET'],
        # ... other countries
    }
    
    # Include both country-specific and generic codes
    component_codes = country_components.get(country, [])
    
    # Always include generic codes for compatibility
    generic_codes = ['BASIC', 'GROSS', 'NET', 'NETPAY']
    all_codes = list(set(component_codes + generic_codes))
    
    return all_codes
```

## **Implementation Roadmap**

### **Pre-Refactoring Audit:**
- [ ] **Code Inventory**: Document all 58+ salary codes by country
- [ ] **Field Mapping Audit**: Map current zoho.employee.data field usage  
- [ ] **Rule Usage Analysis**: Identify actually used vs. defined salary rules
- [ ] **Data Flow Testing**: Test current import → payslip → analytics process

### **Phase 1 Implementation:**
- [ ] **Extend ZohoEmployeeData**: Add country-specific fields for all codes
- [ ] **Create Country Mappings**: Implement country-specific mapping methods
- [ ] **Update Salary Rules**: Align rule definitions with actual code usage
- [ ] **Add Country Detection**: Implement country detection in import process

### **Phase 2 Implementation:**  
- [ ] **Complete Vietnam Mapping**: All 58+ codes mapped and tested
- [ ] **Indonesia Compatibility**: Maintain legacy + new code support
- [ ] **Validation Layer**: Add salary code validation and error handling
- [ ] **Analytics Update**: Recognize all new country-specific codes

### **Phase 3 Implementation:**
- [ ] **Other Countries**: Extend to India, Singapore, Thailand, Cambodia, Malaysia
- [ ] **Migration Scripts**: Convert existing data to new field structure
- [ ] **Performance Optimization**: Optimize field mapping and import speed
- [ ] **Automated Testing**: Create comprehensive test suite for all countries

### **Post-Implementation:**
- [ ] **Data Migration**: Migrate existing zoho.employee.data records
- [ ] **Documentation**: Update user guides and technical documentation
- [ ] **Training**: Create country-specific configuration guides
- [ ] **Monitoring**: Implement logging for unmapped codes and errors

## **Benefits of This Refactoring**

### **Technical Benefits:**
- **Scalable Architecture**: Easy addition of new countries and salary codes
- **Maintainable Code**: Clear separation of country-specific logic
- **Data Integrity**: Comprehensive validation and error handling
- **Performance**: Optimized field mapping and reduced query complexity

### **Business Benefits:**
- **Accurate Payroll**: All salary components properly calculated and displayed
- **Complete Analytics**: Full visibility into salary breakdowns by country
- **Compliance Ready**: Support for country-specific tax and insurance requirements
- **Future-Proof**: Architecture supports expansion to new regions

### **Operational Benefits:**
- **Reduced Errors**: Automated validation catches mapping issues
- **Faster Implementation**: Standardized patterns for new countries  
- **Better Monitoring**: Comprehensive logging and error reporting
- **Easier Maintenance**: Clear separation of concerns and documentation

## **Critical Success Factors**

### **Data Integrity:**
- Ensure no data loss during field mapping migration
- Maintain backward compatibility with existing processes
- Validate all salary code mappings before go-live

### **Performance:**
- Optimize field mapping queries for large datasets
- Implement caching for frequently accessed country mappings
- Monitor import processing time and memory usage

### **User Experience:**
- Ensure seamless transition for existing users
- Provide clear error messages for mapping issues
- Maintain existing analytics dashboard functionality

### **Maintainability:**
- Document all country-specific mapping decisions
- Create clear guidelines for adding new salary codes
- Implement automated tests for all country mappings

This comprehensive refactoring will transform the payroll system into a robust, country-aware platform that properly handles all salary components and provides accurate analytics across all supported regions.