#!/usr/bin/env python3
"""
Add Indonesia Calculated Columns to TEMPLATE Master
==================================================

This adds calculated columns where headers use ODOO.LIST.HEADER but values 
are Excel formulas based on Vietnam patterns adapted for Indonesia.
"""
import json

def add_indonesia_calculated_columns():
    # Load current Indonesia spreadsheet
    with open('/Users/adity/Documents/GitHub/gitlocal/pb_hr_payroll_indonesia/data/indonesia_payroll_data.json', 'r') as f:
        data = json.load(f)
    
    print("🧮 Adding Indonesia calculated columns to TEMPLATE Master...")
    
    # Find TEMPLATE Master sheet
    template_master = None
    for sheet in data['sheets']:
        if sheet['name'] == 'TEMPLATE Master':
            template_master = sheet
            break
    
    if not template_master:
        print("❌ TEMPLATE Master sheet not found!")
        return
    
    # Indonesia calculated columns (headers from model, values from formulas)
    # Based on Vietnam patterns but adapted for Indonesia
    indonesia_calculated_columns = [
        # Basic Salary Calculations (based on hours worked)
        {
            'field': 'actual_basic_salary',  # Model field
            'display': 'Actual Basic Salary',
            'formula_template': '=ROUND(I{row}/N{row}*O{row},0)',  # I=base_salary, N=standard_whr, O=actual_hours
            'description': 'Basic salary adjusted for actual hours worked'
        },
        {
            'field': 'actual_gas_allowance', 
            'display': 'Actual Transport Allow',
            'formula_template': '=IF(ISBLANK(E{row}),J{row},J{row}/N{row}*O{row})',  # J=gas_allowance
            'description': 'Transport allowance adjusted for actual hours'
        },
        {
            'field': 'actual_phone_allowance',
            'display': 'Actual Phone Allow', 
            'formula_template': '=IF(ISBLANK(E{row}),K{row},K{row}/N{row}*O{row})',  # K=phone_allowance
            'description': 'Phone allowance adjusted for actual hours'
        },
        {
            'field': 'actual_meal_allowance',
            'display': 'Actual Meal Allow',
            'formula_template': '=IF(ISBLANK(E{row}),L{row},L{row}/N{row}*O{row})',  # L=meal_allowance
            'description': 'Meal allowance adjusted for actual hours'
        },
        
        # Indonesia BPJS Calculations
        {
            'field': 'calculated_bpjs_health_emp',
            'display': 'Calc BPJS Health Emp',
            'formula_template': '=ROUND(I{row}*0.01,0)',  # 1% of base salary
            'description': 'BPJS Kesehatan Employee 1% of basic salary'
        },
        {
            'field': 'calculated_bpjs_jht_emp', 
            'display': 'Calc BPJS JHT Emp',
            'formula_template': '=ROUND(I{row}*0.02,0)',  # 2% of base salary
            'description': 'BPJS JHT Employee 2% of basic salary'
        },
        {
            'field': 'calculated_bpjs_jp_emp',
            'display': 'Calc BPJS JP Emp', 
            'formula_template': '=ROUND(I{row}*0.01,0)',  # 1% of base salary
            'description': 'BPJS JP Employee 1% of basic salary'
        },
        {
            'field': 'calculated_bpjs_health_empr',
            'display': 'Calc BPJS Health Empr',
            'formula_template': '=ROUND(I{row}*0.04,0)',  # 4% of base salary
            'description': 'BPJS Kesehatan Employer 4% of basic salary'
        },
        {
            'field': 'calculated_bpjs_jht_empr',
            'display': 'Calc BPJS JHT Empr',
            'formula_template': '=ROUND(I{row}*0.037,0)',  # 3.7% of base salary
            'description': 'BPJS JHT Employer 3.7% of basic salary'
        },
        
        # Overtime Calculations (Indonesia rates)
        {
            'field': 'total_overtime_amount',
            'display': 'Total OT Amount',
            'formula_template': '=IF(O{row}=0,0,ROUND(I{row}/N{row}*(P{row}*1.5+Q{row}*2+R{row}*3),0))',
            'description': 'Total overtime: Normal 1.5x, Weekend 2x, Holiday 3x'
        },
        
        # Gross Pay Calculation
        {
            'field': 'calculated_gross_pay',
            'display': 'Calculated Gross Pay',
            'formula_template': '=SUM(AI{row}:AO{row})+AP{row}',  # Sum basic+allowances+overtime
            'description': 'Total gross pay including all allowances and overtime'
        },
        
        # Total Deductions
        {
            'field': 'total_deductions',
            'display': 'Total Deductions',
            'formula_template': '=SUM(AQ{row}:AW{row})',  # Sum all BPJS + tax + other deductions
            'description': 'Total deductions: BPJS, PPh21, Union, Loans, etc.'
        },
        
        # Indonesia PPh21 Tax Calculation (progressive)
        {
            'field': 'calculated_pph21',
            'display': 'Calculated PPh21',
            'formula_template': '=ROUND(MAX(0,(AX{row}*12-72000000)*0.05/12),0)',  # Basic progressive tax
            'description': 'PPh21 income tax calculation (5% on income above PTKP)'
        },
        
        # Net Pay Calculation
        {
            'field': 'net_pay',
            'display': 'Net Pay',
            'formula_template': '=AX{row}-AY{row}',  # Gross - Total Deductions
            'description': 'Final net pay after all deductions'
        }
    ]
    
    # Get current column count and start adding from the next column
    current_cols = template_master.get('colNumber', 41)
    start_col_index = current_cols
    
    print(f"   📊 Current TEMPLATE Master columns: {current_cols}")
    print(f"   ➕ Adding calculated columns starting from column {start_col_index + 1}")
    
    # Column letter helper
    def get_col_letter(index):
        if index < 26:
            return chr(ord('A') + index)
        else:
            return chr(ord('A') + (index // 26) - 1) + chr(ord('A') + (index % 26))
    
    columns_added = 0
    
    # Add each calculated column
    for i, calc_col in enumerate(indonesia_calculated_columns):
        col_index = start_col_index + i
        col_letter = get_col_letter(col_index)
        
        # Add header with ODOO.LIST.HEADER (model field)
        header_cell = f'{col_letter}1'
        template_master['cells'][header_cell] = {
            "style": 1,
            "content": f'=ODOO.LIST.HEADER(1,"{calc_col["field"]}")'
        }
        
        # Add calculated formulas for rows 2-26 (25 employees)
        for row in range(2, 27):
            data_cell = f'{col_letter}{row}'
            formula = calc_col['formula_template'].format(row=row)
            template_master['cells'][data_cell] = {
                "style": 3,  # Formula style
                "content": formula
            }
        
        columns_added += 1
        print(f"   ✅ Added {calc_col['display']}: {calc_col['description']}")
    
    # Update sheet column count
    new_col_count = current_cols + columns_added
    template_master['colNumber'] = new_col_count
    
    print(f"   📊 Updated TEMPLATE Master to {new_col_count} columns")
    print(f"   🧮 Added {columns_added * 25} calculation formulas")
    
    # Also need to add these fields to the lists configuration
    print("   🔧 Adding calculated fields to lists configuration...")
    
    if 'lists' in data and '1' in data['lists']:
        existing_fields = data['lists']['1']['columns']
        new_fields = [calc_col['field'] for calc_col in indonesia_calculated_columns]
        
        # Add new calculated fields to lists
        updated_fields = existing_fields + new_fields
        data['lists']['1']['columns'] = updated_fields
        
        print(f"   ✅ Added {len(new_fields)} calculated fields to lists configuration")
        print(f"   ✅ Total fields in lists: {len(updated_fields)}")
    
    # Save updated spreadsheet
    with open('/Users/adity/Documents/GitHub/gitlocal/pb_hr_payroll_indonesia/data/indonesia_payroll_data.json', 'w') as f:
        json.dump(data, f, indent=2)
    
    print("✅ Indonesia calculated columns added successfully!")
    print("✅ Headers use ODOO.LIST.HEADER for model fields")
    print("✅ Values use Excel formulas for calculations")
    print()
    print("🇮🇩 New Indonesia Calculated Columns:")
    for calc_col in indonesia_calculated_columns:
        print(f"   • {calc_col['display']}: =ODOO.LIST.HEADER(1,\"{calc_col['field']}\")")
        print(f"     Formula: {calc_col['formula_template'].format(row='X')}")
        print(f"     Purpose: {calc_col['description']}")
        print()
    
    print("📊 Expected Result:")
    print("• Calculated columns appear at end of TEMPLATE Master sheet")
    print("• Headers dynamically populate from model fields")
    print("• Values calculated using Excel formulas")
    print("• BPJS, PPh21, Gross/Net Pay calculations working")
    print("• Hours-based salary adjustments applied")

if __name__ == "__main__":
    add_indonesia_calculated_columns()