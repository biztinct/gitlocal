# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an **Odoo 16 Community Edition** multi-country HR Payroll system with enhanced spreadsheet functionality. The codebase consists of 7 interconnected modules providing comprehensive payroll management for companies operating across multiple countries (primarily Asia-Pacific region).

## Development Commands

### Module Management
```bash
# Install/update modules during development
python -m odoo -c odoo.conf -d your_database -u om_hr_payroll,pb_hr_payroll_base,pb_hr_payroll_indonesia,pb_hr_payroll_india

# Install new modules
python -m odoo -c odoo.conf -d your_database -i module_name

# Start development server with auto-reload
python -m odoo -c odoo.conf -d your_database --dev=reload,qweb,werkzeug,xml
```

### Testing
```bash
# Run all tests for payroll modules
python -m odoo -c odoo.conf -d your_database --test-enable -u om_hr_payroll,pb_hr_payroll_base --stop-after-init

# Run specific test file
python -m odoo -c odoo.conf -d your_database --test-enable --test-file=om_hr_payroll/tests/test_payslip_flow.py --stop-after-init

# Run tests for spreadsheet modules
python -m odoo -c odoo.conf -d your_database --test-enable -u spreadsheet,spreadsheet_oca --stop-after-init
```

## Architecture Overview

### Multi-Country Payroll Architecture Strategy
The system follows a **non-invasive extension pattern** that preserves the base `om_hr_payroll` module while adding multi-country capabilities:

```
┌─────────────────────────────────────────────────────────────┐
│                    om_hr_payroll                            │
│                   (UNTOUCHED BASE)                          │
│  • Core payroll models                                     │
│  • Basic salary rules                                      │
│  • Standard payslip processing                             │
│  • Original functionality preserved                        │
└─────────────────────────────────────────────────────────────┘
                              ↑ extends via _inherit
┌─────────────────────────────────────────────────────────────┐
│                pb_hr_payroll_base                           │
│               (FRAMEWORK LAYER)                             │
│  • Multi-country dashboard                                 │
│  • Enhanced models via inheritance                         │
│  • Country selector                                        │
│  • Contract type integration                               │
│  • Zoho integration framework                              │
│  • Utilities for country modules                           │
└─────────────────────────────────────────────────────────────┘
                              ↑ depends on
┌─────────────────────────────────────────────────────────────┐
│            Country-Specific Modules                         │
│  ┌─────────────────┐ ┌─────────────────┐ ┌──────────────┐   │
│  │ pb_hr_payroll_  │ │ pb_hr_payroll_  │ │ pb_hr_payroll│   │
│  │    vietnam      │ │   indonesia     │ │    india     │   │
│  │ • VN tax rules  │ │ • ID tax rules  │ │ • IN tax     │   │
│  │ • VN compliance │ │ • BPJS rules    │ │   rules      │   │
│  │ • VN reports    │ │ • THR payments  │ │ • PF/ESI     │   │
│  └─────────────────┘ └─────────────────┘ └──────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Core Modules Structure
- **`om_hr_payroll/`** - Foundation payroll module (Odoo 16 Community) - **NEVER MODIFIED**
- **`pb_hr_payroll_base/`** - Enhanced multi-country framework with professional dashboard
- **`pb_hr_payroll_indonesia/`** - Indonesia-specific payroll implementation
- **`pb_hr_payroll_india/`** - India-specific payroll implementation  
- **`payroll_analytics_approval/`** - Analytics and approval workflows
- **`spreadsheet/`** - Core spreadsheet functionality (alternative to Enterprise)
- **`spreadsheet_oca/`** - OCA community spreadsheet extensions
- **`spreadsheet_dashboard_oca/`** - Dashboard integration for spreadsheets

### Enhanced Models via Inheritance
The `pb_hr_payroll_base` module extends core models using `_inherit`:
- **`hr.payroll.structure`** - Added multi-country fields
- **`hr.salary.rule`** - Added country-specific options
- **`hr.contract`** - Enhanced with payroll integration
- **`hr.contract.type`** - Added payroll scheduling
- **`hr.employee`** - Added payroll country tracking

### Benefits of This Architecture
- **Zero Base Modifications**: `om_hr_payroll` remains completely untouched for safe upgrades
- **Clean Inheritance**: Uses proper Odoo `_inherit` patterns
- **Independent Deployment**: Each country module can be installed separately
- **Extensible Framework**: Easy to add new countries following established patterns

### Key Models and Entry Points
- **`hr.payslip`** (`om_hr_payroll/models/hr_payslip.py`) - Core payslip functionality
- **`payroll.dashboard`** (`pb_hr_payroll_base/models/payroll_dashboard.py`) - Multi-country dashboard
- **`hr.salary.rule`** (`om_hr_payroll/models/hr_salary_rule.py`) - Salary calculation engine
- **`spreadsheet.spreadsheet`** (`spreadsheet/models/spreadsheet.py`) - Spreadsheet management

## Development Guidelines

### Critical Development Principles
⚠️ **NEVER MODIFY `om_hr_payroll`**: The base payroll module must remain completely untouched to ensure safe upgrades and maintain compatibility. All enhancements must be implemented via inheritance in `pb_hr_payroll_base` or country-specific modules.

### Module Dependencies
- Core: `base`, `hr`, `hr_contract`, `hr_holidays`, `mail`
- External Python: `requests` (Zoho API), `dateutil` (date calculations)
- Frontend: Chart.js (CDN), enhanced CSS/JS assets

### Testing Framework
Uses Odoo's built-in testing with `TransactionCase`. Test files located in `tests/` directories follow `test_00_*` naming convention.

### Asset Management
- **Enhanced Assets**: `pb_hr_payroll_base/static/src/css/payroll_dashboard_enhanced.css`
- **Professional Styling**: Navy blue theme (#21435F) with animations
- **Chart Integration**: Chart.js for analytics and visualizations
- **Responsive Design**: Mobile-first approach with ripple effects

### Country-Specific Development
When adding new countries, follow this established pattern:

#### New Country Module Structure
```python
# Example: pb_hr_payroll_vietnam
{
    'name': 'Vietnam Payroll',
    'depends': ['pb_hr_payroll_base'],
    # Vietnam-specific implementation
}
```

#### Country Module Implementation Pattern
```python
# Vietnam-specific actions following the established pattern
def action_get_employee_data_vn(self):
    return vietnam_zoho_import_action()

def action_edit_spreadsheet_vn(self):
    return vietnam_spreadsheet_action()
```

#### Development Steps for New Countries:
1. Create new module extending `pb_hr_payroll_base`
2. Implement country-specific salary rules and tax calculations
3. Add country entry to dashboard with appropriate permissions
4. Follow existing Indonesia/India module patterns
5. Use framework utilities from `pb_hr_payroll_base` for common functionality

### Spreadsheet Development
- Reference Odoo 16.0 spreadsheet functions for custom business functions
- Use OCA modules for enhanced functionality
- Integration with accounting via custom ODOO.CREDIT/ODOO.DEBIT functions

## Key Integration Points

### Zoho CRM Integration
- Employee data synchronization via REST API
- Connection testing: `action_test_zoho_connection` method
- Staging tables for data validation before import

### Bank Export System
- Multi-format export support for payroll bank transfers
- Country-specific banking integrations

### Analytics Framework
- Bokeh integration for advanced charting
- Chart.js for web-based visualizations
- Real-time payroll analytics and comparisons