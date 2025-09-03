# Vietnam to Indonesia Spreadsheet Transformation Guide

## Complete Script Sequence Used

This documents the exact scripts used to transform Vietnam spreadsheet to the final Indonesia form with all records, Indonesia-specific fields, and calculated columns.

### **Phase 1: Base Copy (Working Demo Data)**
**Script:** `vietnam_exact_copy_converter.py`
- **Purpose:** Create exact Vietnam copy to ensure demo data appears
- **Key Function:** `convert_vietnam_exact_copy()` → `convert_vietnam_to_indonesia_enhanced()`
- **Result:** Working spreadsheet with all 5 sheets, demo data visible, but Vietnam field names

### **Phase 2: Field Enhancement (Add Indonesia Lists)**
**Same Script Enhanced:** `vietnam_exact_copy_converter.py`
- **Purpose:** Add Indonesia-specific fields to lists configuration while preserving working Vietnam fields
- **Key Changes:**
  - Added 31 Indonesia fields to lists: BPJS, PPh21, NPWP, Tunjangan, etc.
  - Field mappings: `pit_number` → `npwp_number`, `full_name_vn` → `full_name_en`
  - Total fields: 56 (25 Vietnam + 31 Indonesia)
- **Result:** Fields available for ODOO formulas, but not visible in template sheets

### **Phase 3: Database Refresh (Fix Visibility Issues)**
**Script:** `fix_indonesia_spreadsheet.py`
- **Purpose:** Fix field name errors and database caching issues  
- **Key Changes:**
  - Fixed `noupdate="1"` → `noupdate="0"` in spreadsheet_data.xml
  - Created new external ID to force database refresh
  - Used actual model field names
- **Result:** Indonesia fields accessible in ODOO.LIST.HEADER formulas

**Script:** `force_refresh_spreadsheet.py`
- **Purpose:** Create forced refresh XML to overcome database caching
- **Result:** Created `spreadsheet_data_refresh.xml` with unique timestamp ID

### **Phase 4: Add Headers to Sheets**
**Script:** `add_indonesia_headers.py`
- **Purpose:** Add Indonesia field headers to actual template sheets
- **Key Actions:**
  - Added 15 Indonesia ODOO.LIST.HEADER formulas to TEMPLATE Employee Details
  - Added Indonesia ODOO.LIST data formulas for rows 2-6
  - Updated reference sheets (Allowance Details, Earnings Details) with Indonesia terminology
- **Result:** Indonesia headers visible but overlapping with existing layout

### **Phase 5: Clean Layout (Final Form)**
**Script:** `reorganize_indonesia_templates.py`
- **Purpose:** Create clean, organized Indonesia template layout
- **Key Actions:**
  - Completely rebuilt TEMPLATE Employee Details with 34 clean Indonesia columns (A-AH)
  - Completely rebuilt TEMPLATE Master with 41 comprehensive columns
  - Logical organization: Basic Info → Salary → Indonesia Tax/Insurance → Deductions → ID Numbers
  - Generated 1,875 total ODOO formulas (850 + 1,025)
- **Result:** Professional Indonesia spreadsheet with clean layout and all Indonesia fields

### **Phase 6: Calculated Columns (NEW - Advanced Formulas)**
**Script:** `add_indonesia_calculated_columns.py`
- **Purpose:** Add calculated columns with model headers but Excel formula values
- **Key Actions:**
  - Added 14 calculated columns to TEMPLATE Master (columns AP-BC)
  - Headers use ODOO.LIST.HEADER for model field binding
  - Values use Excel formulas for calculations (hours-based, BPJS, overtime, net pay)
  - Added 350 calculation formulas (14 columns × 25 employees)
  - Extended lists configuration to 70 total fields
- **Key Calculations Added:**
  - **Hours-based adjustments:** Actual salary based on worked hours
  - **BPJS calculations:** Employee/employer contributions (1%, 2%, 4%, 3.7%)
  - **Overtime calculations:** Indonesian rates (1.5x, 2x, 3x)
  - **Tax calculations:** PPh21 progressive tax with PTKP
  - **Net pay calculation:** Complete gross-to-net calculation
- **Result:** Complete payroll calculation system with both data binding and formula calculations

## **Final Configuration Files**

### **spreadsheet_data.xml** (Final)
```xml
<record id="payrollstaging_indonesia" model="spreadsheet.spreadsheet">
    <field name="name">Indonesia Payroll Staging Data</field>
    <field name="data" type="base64" file="pb_hr_payroll_indonesia/data/indonesia_payroll_data.json"/>
</record>
```
- **Key:** `noupdate="0"` allows updates
- **Key:** External ID matches dashboard expectations

### **indonesia_payroll_data.json** (Final Result)
- **5 sheets:** Allowance Details, Earnings Details, Master lookup, TEMPLATE Employee Details, TEMPLATE Master
- **56 fields in lists:** 25 Vietnam (preserved) + 31 Indonesia (added)
- **Clean layout:** 34 columns in Employee Details, 41 in Master
- **1,875+ formulas:** All ODOO.LIST.HEADER and ODOO.LIST formulas

## **Script Execution Order**

```bash
# 1. Base copy with enhancements
python3 vietnam_exact_copy_converter.py

# 2. Fix field names and database refresh
python3 fix_indonesia_spreadsheet.py
python3 force_refresh_spreadsheet.py

# 3. Add headers to sheets
python3 add_indonesia_headers.py  

# 4. Final clean reorganization
python3 reorganize_indonesia_templates.py

# 5. NEW: Add calculated columns with formulas
python3 add_indonesia_calculated_columns.py
```

## **Key Success Factors**

1. **Preserve Working Base:** Always start with exact Vietnam copy to ensure demo data works
2. **Add Fields Gradually:** Add Indonesia fields to lists while keeping Vietnam fields
3. **Force Database Refresh:** Use `noupdate="0"` and unique IDs to overcome caching
4. **Clean Final Layout:** Completely rebuild templates with logical field organization
5. **Comprehensive Formulas:** Generate both header and data formulas for all fields

## **Adapting for Other Countries**

### **Step-by-Step Country Adaptation Process**

#### **1. Field Mapping Dictionary Updates**
For each script, update the field mapping dictionaries:

**Example for Singapore (EPF/CPF System):**
```python
# In vietnam_exact_copy_converter.py
field_mappings = {
    'pit_number': 'cpf_number',        # Tax ID: Vietnam PIT → Singapore CPF
    'full_name_vn': 'full_name_en',    # Name format
    'social_ins1': 'cpf_employee',     # Social insurance → CPF employee
    'social_ins4': 'cpf_employer',     # Social insurance → CPF employer
    'monthly_pit': 'income_tax_sg',    # Tax: Vietnam PIT → Singapore Income Tax
}

# Country-specific fields to ADD
singapore_additional_fields = [
    'cpf_employee', 'cpf_employer', 'sdl_levy', 'foreign_worker_levy',
    'cpf_number', 'income_tax_sg', 'singapore_allowance_1', 'singapore_deduction_1'
]
```

#### **2. Template Layout Customization**
**In reorganize_[country]_templates.py:**
```python
singapore_employee_layout = [
    # Basic Info (same pattern)
    ('employee_id', 'Employee ID'),
    ('first_name', 'First Name'),
    ('last_name', 'Last Name'),
    
    # Singapore-specific fields
    ('cpf_number', 'CPF Number'),
    ('cpf_employee', 'CPF Employee'),
    ('cpf_employer', 'CPF Employer'),
    ('sdl_levy', 'SDL Levy'),
    ('income_tax_sg', 'Singapore Tax'),
    # ... add more Singapore fields
]
```

#### **3. Calculated Columns by Country**
**In add_[country]_calculated_columns.py:**

**Singapore CPF Calculations:**
```python
singapore_calculated_columns = [
    {
        'field': 'calculated_cpf_employee',
        'display': 'Calc CPF Employee',
        'formula_template': '=ROUND(I{row}*0.20,0)',  # 20% CPF employee
        'description': 'CPF Employee contribution 20% of salary'
    },
    {
        'field': 'calculated_cpf_employer', 
        'display': 'Calc CPF Employer',
        'formula_template': '=ROUND(I{row}*0.17,0)',  # 17% CPF employer
        'description': 'CPF Employer contribution 17% of salary'
    }
]
```

**Malaysia EPF Calculations:**
```python
malaysia_calculated_columns = [
    {
        'field': 'calculated_epf_employee',
        'display': 'Calc EPF Employee',
        'formula_template': '=ROUND(I{row}*0.11,0)',  # 11% EPF employee
        'description': 'EPF Employee contribution 11% of salary'
    },
    {
        'field': 'calculated_socso_employee',
        'display': 'Calc SOCSO Employee', 
        'formula_template': '=ROUND(MIN(I{row}*0.005,19.75),0)',  # SOCSO with cap
        'description': 'SOCSO Employee contribution with monthly cap'
    }
]
```

#### **4. Country-Specific Calculation Formulas**

**Tax Calculation Examples:**
```python
# Singapore Progressive Tax
'formula_template': '=IF(I{row}*12<=20000,0,IF(I{row}*12<=30000,(I{row}*12-20000)*0.02/12,...))',

# Malaysia Income Tax  
'formula_template': '=IF(I{row}*12<=5000,0,IF(I{row}*12<=20000,(I{row}*12-5000)*0.01/12,...))',

# Thailand SSF
'formula_template': '=ROUND(I{row}*0.05,0)',  # 5% SSF contribution
```

#### **5. Reference Sheet Updates**
Update terminology in Allowance/Earnings Details sheets:
```python
# Singapore reference sheets
singapore_allowance_headers = [
    "Employee ID", "CPF Housing Grant", "Transport Allowance", "Meal Allowance",
    "AWS (13th Month)", "Performance Bonus", "CPF Employee", "CPF Employer"
]

# Malaysia reference sheets  
malaysia_earnings_headers = [
    "Employee ID", "EPF Employee", "EPF Employer", "SOCSO Employee", 
    "SOCSO Employer", "EIS Employee", "Income Tax MY"
]
```

### **Country Implementation Checklist**

#### **For Each New Country:**
- [ ] **1. Copy Indonesia scripts** to `pb_hr_payroll_[country]/data/`
- [ ] **2. Update field mappings** in all 6 scripts
- [ ] **3. Customize template layouts** for country-specific fields  
- [ ] **4. Adapt calculation formulas** for local tax/insurance systems
- [ ] **5. Update reference sheet terminology**
- [ ] **6. Create country model fields** in `models/zoho_staging_data.py`
- [ ] **7. Test execution order** with Vietnam base
- [ ] **8. Verify calculated formulas** work with local rates

#### **Common Country Systems to Map:**
- **Tax Systems:** PIT → Income Tax, PPh21 → PAYE, etc.
- **Social Security:** BPJS → CPF/EPF/SSF/NSSF
- **ID Numbers:** NPWP → CPF/EPF/SSN numbers  
- **Allowances:** Tunjangan → Country-specific allowances
- **Overtime Rates:** Adapt 1.5x/2x/3x to local labor laws

### **Quick Start for New Country**
```bash
# 1. Copy Indonesia transformation scripts
cp pb_hr_payroll_indonesia/data/*.py pb_hr_payroll_[country]/data/

# 2. Global find/replace in all scripts
# Indonesia → [Country]  
# BPJS → [CountrySystem]
# PPh21 → [CountryTax]
# NPWP → [CountryID]

# 3. Update calculation rates and formulas
# Edit add_[country]_calculated_columns.py with local rates

# 4. Run transformation sequence
python3 vietnam_exact_copy_converter.py
python3 fix_[country]_spreadsheet.py  
python3 force_refresh_spreadsheet.py
python3 add_[country]_headers.py
python3 reorganize_[country]_templates.py
python3 add_[country]_calculated_columns.py
```

## **Critical Files to Preserve**
- Keep all 5 transformation scripts for reference
- Keep this transformation guide  
- Keep final `indonesia_payroll_data.json` as template
- Keep working `spreadsheet_data.xml` configuration