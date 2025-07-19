# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an **Odoo 16 Community Edition** multi-country HR Payroll system with enhanced spreadsheet functionality. The codebase consists of 7 interconnected modules providing comprehensive payroll management for companies operating across multiple countries (primarily Asia-Pacific region).

## Development Memories

- **Major Refactoring Completed (2024)**: Successfully consolidated menu structure and removed redundant menus
- All country modules working: Vietnam, India, Indonesia, Singapore, Thailand
- Menu structure cleaned up and centralized under original Payroll menu
- Setup guide moved to base module for all countries
- Analytics module integration completed

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
│   └── Thailand Dashboard
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
        accessible_countries = ['VN', 'ID', 'IN', 'SG', 'MY', 'TH']
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