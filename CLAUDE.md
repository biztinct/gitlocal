# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an **Odoo 16 Community Edition** multi-country HR Payroll system with enhanced spreadsheet functionality. The codebase consists of 7 interconnected modules providing comprehensive payroll management for companies operating across multiple countries (primarily Asia-Pacific region).



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