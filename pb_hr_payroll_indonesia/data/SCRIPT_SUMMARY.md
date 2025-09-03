# Vietnam to Country Spreadsheet Transformation Scripts

## Complete Script List (6 Scripts Total)

### **Core Transformation Scripts (6 Required)**

| **Phase** | **Script Name** | **Purpose** | **Key Output** |
|-----------|----------------|-------------|----------------|
| **1** | `vietnam_exact_copy_converter.py` | Base copy + field enhancement | Working demo data + country fields in lists |
| **2** | `fix_[country]_spreadsheet.py` | Fix field names & caching | Corrected model field references |
| **3** | `force_refresh_spreadsheet.py` | Database refresh | XML with unique timestamp ID |
| **4** | `add_[country]_headers.py` | Add headers to sheets | Country headers visible in templates |
| **5** | `reorganize_[country]_templates.py` | Clean layout | Professional organized columns |
| **6** | `add_[country]_calculated_columns.py` | **NEW** - Calculated columns | Excel formulas for payroll calculations |

### **Execution Order (Must Follow Sequence)**
```bash
python3 vietnam_exact_copy_converter.py           # Phase 1
python3 fix_[country]_spreadsheet.py             # Phase 2  
python3 force_refresh_spreadsheet.py             # Phase 3
python3 add_[country]_headers.py                 # Phase 4
python3 reorganize_[country]_templates.py        # Phase 5
python3 add_[country]_calculated_columns.py      # Phase 6 (NEW)
```

## **Key Script Functions by Phase**

### **Phase 1: Base Copy (`vietnam_exact_copy_converter.py`)**
- **Function:** `convert_vietnam_to_indonesia_enhanced()`
- **Input:** Vietnam JSON spreadsheet
- **Actions:**
  - Copy Vietnam structure (preserves working demo data)
  - Add country fields to lists configuration  
  - Apply basic field mappings (pit_number → country_tax_id)
- **Output:** 56+ fields total (Vietnam + Country fields)

### **Phase 2: Field Fix (`fix_[country]_spreadsheet.py`)**
- **Function:** `fix_[country]_spreadsheet()`
- **Actions:**
  - Fix incorrect field name references
  - Verify all fields exist in actual model
  - Apply field corrections (transportation_allowance → gas_allowance)
- **Critical:** Ensures no "unknown object" errors

### **Phase 3: Database Refresh (`force_refresh_spreadsheet.py`)**
- **Function:** `create_forced_refresh_data()`
- **Actions:**
  - Generate unique timestamp ID
  - Create refresh XML with noupdate="0"
  - Override database caching
- **Critical:** Forces Odoo to load new field configuration

### **Phase 4: Add Headers (`add_[country]_headers.py`)**
- **Function:** `add_[country]_headers_to_sheets()`
- **Actions:**
  - Add ODOO.LIST.HEADER formulas to template sheets
  - Add ODOO.LIST data formulas for sample rows
  - Update reference sheets with country terminology
- **Output:** Country headers visible but may be messy layout

### **Phase 5: Clean Layout (`reorganize_[country]_templates.py`)**
- **Function:** `reorganize_[country]_templates()`
- **Actions:**
  - **Completely rebuild** TEMPLATE Employee Details & Master
  - Clean, logical column organization
  - Generate comprehensive ODOO formulas
- **Output:** Professional layout with all country fields organized

### **Phase 6: Calculated Columns (`add_[country]_calculated_columns.py`) - NEW**
- **Function:** `add_[country]_calculated_columns()`
- **Actions:**
  - Add calculated columns to TEMPLATE Master
  - Headers use ODOO.LIST.HEADER (model binding)
  - Values use Excel formulas (calculations)
  - Add hours-based, tax, social security, net pay calculations
- **Output:** Complete payroll calculation system

## **Key Configuration Areas per Script**

### **Field Mappings (Update for Each Country)**
```python
# Vietnam → Country mappings
field_mappings = {
    'pit_number': 'country_tax_id',           # Tax ID
    'full_name_vn': 'full_name_en',           # Name format  
    'social_ins1': 'country_social_emp',      # Employee social insurance
    'monthly_pit': 'country_income_tax',      # Income tax
}

# Country-specific fields to add
country_additional_fields = [
    'country_tax_id', 'country_social_emp', 'country_social_empr',
    'country_allowance_1', 'country_deduction_1'
]
```

### **Template Layouts (Customize Column Organization)**
```python
country_employee_layout = [
    # Basic Info (standard)
    ('employee_id', 'Employee ID'),
    ('first_name', 'First Name'),
    
    # Country-specific (customize)
    ('country_tax_id', 'Tax ID'),
    ('country_social_emp', 'Social Insurance'),
    ('country_income_tax', 'Income Tax'),
]
```

### **Calculated Formulas (Country-Specific Rates)**
```python
country_calculated_columns = [
    {
        'field': 'calculated_social_emp',
        'display': 'Calc Social Employee',
        'formula_template': '=ROUND(I{row}*0.XX,0)',  # Country rate
        'description': 'Employee social insurance contribution'
    }
]
```

## **Country-Specific Customization Points**

### **1. Social Security Systems**
- **Indonesia:** BPJS (1%, 2%, 4%, 3.7% rates)
- **Singapore:** CPF (20% employee, 17% employer)  
- **Malaysia:** EPF (11% employee, 12% employer) + SOCSO
- **Thailand:** SSF (5% contribution)
- **Cambodia:** NSSF (rates vary)

### **2. Tax Calculations**
- **Progressive tax brackets:** Adapt IF formulas for country rates
- **Tax-free thresholds:** Adjust PTKP/exemption amounts
- **Monthly vs Annual:** Adapt calculation periods

### **3. Overtime Rates**
- **Indonesia:** 1.5x, 2x, 3x
- **Singapore:** 1.5x normal, 2x holiday
- **Malaysia:** 1.5x normal, 2x weekend/holiday
- **Adapt formula:** `I{row}/N{row}*(P{row}*1.5+Q{row}*2+R{row}*3)`

### **4. Currency & Formatting**
- Update reference sheets with local currency symbols
- Adjust ROUND() precision based on currency (0 for IDR, 2 for SGD)

## **Success Validation Checklist**

After running all 6 scripts:
- [ ] **Demo data appears** in spreadsheet
- [ ] **Country fields visible** in TEMPLATE sheets  
- [ ] **ODOO.LIST.HEADER formulas work** for country fields
- [ ] **Calculated columns present** in TEMPLATE Master
- [ ] **Excel formulas calculate** correctly with demo data
- [ ] **No #Error messages** in spreadsheet cells
- [ ] **Lists configuration** contains all country fields
- [ ] **Database refresh successful** (noupdate="0" works)

Total transformation creates **complete country payroll system** with:
- All country fields accessible via ODOO formulas
- Professional organized layout
- Complete payroll calculations (gross to net)
- Hours-based adjustments  
- Country-specific tax and social security calculations