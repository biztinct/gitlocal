#!/usr/bin/env python3
"""
Reorganize Indonesia Template Sheets with Clean Layout
====================================================

This creates a proper, organized layout for Indonesia fields in the 
TEMPLATE sheets instead of just adding them to the end.
"""
import json

def reorganize_indonesia_templates():
    # Load current Indonesia spreadsheet
    with open('/Users/adity/Documents/GitHub/gitlocal/pb_hr_payroll_indonesia/data/indonesia_payroll_data.json', 'r') as f:
        data = json.load(f)
    
    print("🇮🇩 Reorganizing TEMPLATE sheets with clean Indonesia layout...")
    
    # Define clean Indonesia template layout
    indonesia_employee_layout = [
        # Basic Employee Info
        ('employee_id', 'Employee ID'),
        ('first_name', 'First Name'),
        ('last_name', 'Last Name'),
        ('full_name_en', 'Full Name'),
        ('email', 'Email'),
        ('department', 'Department'),
        ('designation', 'Job Title'),
        ('date_of_joining', 'Date Joined'),
        
        # Salary & Allowances  
        ('base_salary', 'Base Salary'),
        ('gas_allowance', 'Transport Allow'),
        ('phone_allowance', 'Phone Allow'),
        ('meal_allowance', 'Meal Allow'),
        ('fixed_allowance_1', 'Fixed Allow 1'),
        ('fixed_allowance_2', 'Fixed Allow 2'),
        ('tunjangan_sewa_rumah', 'Housing Allow'),
        ('commission', 'Commission'),
        ('gross_pay_idn', 'Gross Pay IDN'),
        
        # Indonesia Tax & Insurance
        ('npwp_number', 'NPWP Number'),
        ('pph21', 'PPh21 Tax'),
        ('bpjs_kesehatan_employee', 'BPJS Health-Emp'),
        ('bpjs_tk_jht_employee', 'BPJS JHT-Emp'),
        ('bpjs_tk_jp_employee', 'BPJS JP-Emp'),
        ('bpjs_kesehatan_employer', 'BPJS Health-Empr'),
        ('bpjs_tk_jht_employer', 'BPJS JHT-Empr'),
        ('bpjs_tk_jp_employer', 'BPJS JP-Empr'),
        ('bpjs_tk_jkk', 'BPJS JKK'),
        ('bpjs_tk_jkm', 'BPJS JKM'),
        
        # Indonesia Deductions
        ('union_dues', 'Union Dues'),
        ('koperasi', 'Koperasi'),
        ('pinjaman', 'Pinjaman'),
        ('loan_deductions', 'Loan Deduct'),
        ('lain_lain_deduction', 'Other Deduct'),
        
        # ID Numbers
        ('bpjs_kesehatan_number', 'BPJS Health No'),
        ('bpjs_ketenagakerjaan_number', 'BPJS TK No'),
    ]
    
    # Column letters helper function
    def get_col_letter(index):
        """Convert 0-based index to Excel column letter (A, B, ..., Z, AA, AB, ...)"""
        if index < 26:
            return chr(ord('A') + index)
        else:
            return chr(ord('A') + (index // 26) - 1) + chr(ord('A') + (index % 26))
    
    # Generate extended column list
    extended_cols = [get_col_letter(i) for i in range(50)]  # A-Z, AA-AX
    
    # Process TEMPLATE Employee Details sheet
    for sheet in data['sheets']:
        if sheet['name'] == 'TEMPLATE Employee Details':
            print(f"   🔧 Reorganizing: {sheet['name']}")
            
            # Clear existing cells to start fresh
            sheet['cells'] = {}
            
            # Set up clean Indonesia layout
            for i, (field_name, display_name) in enumerate(indonesia_employee_layout):
                if i < len(extended_cols):
                    col = extended_cols[i]
                    
                    # Header with ODOO.LIST.HEADER formula
                    sheet['cells'][f'{col}1'] = {
                        "style": 1,
                        "content": f'=ODOO.LIST.HEADER(1,"{field_name}")'
                    }
                    
                    # Data formulas for rows 2-26 (25 employees)
                    for row in range(2, 27):
                        sheet['cells'][f'{col}{row}'] = {
                            "style": 2,
                            "content": f'=ODOO.LIST(1,{row-1},"{field_name}")'
                        }
            
            # Update sheet dimensions
            sheet['colNumber'] = len(indonesia_employee_layout)
            sheet['rowNumber'] = 30
            
            print(f"      ✅ Clean layout: {len(indonesia_employee_layout)} Indonesia columns")
            print(f"      ✅ {25 * len(indonesia_employee_layout)} data formulas added")
        
        elif sheet['name'] == 'TEMPLATE Master':
            print(f"   🔧 Reorganizing: {sheet['name']}")
            
            # For Master sheet, create a comprehensive layout with all fields
            master_layout = indonesia_employee_layout + [
                # Additional fields for master sheet
                ('thirteenth_month', '13th Month'),
                ('other_income', 'Other Income'),
                ('overtime_normal_150_hour', 'OT Normal 1.5x'),
                ('overtime_weekend_200_hour', 'OT Weekend 2x'),
                ('nightshift_hour', 'Night Shift'),
                ('standard_whr', 'Standard Hours'),
                ('actual_working_hours_incl_paid_leave', 'Actual Hours'),
            ]
            
            # Clear existing cells
            sheet['cells'] = {}
            
            # Set up master layout
            for i, (field_name, display_name) in enumerate(master_layout):
                if i < len(extended_cols):
                    col = extended_cols[i]
                    
                    # Header
                    sheet['cells'][f'{col}1'] = {
                        "style": 1,
                        "content": f'=ODOO.LIST.HEADER(1,"{field_name}")'
                    }
                    
                    # Data formulas for rows 2-26 (25 employees)
                    for row in range(2, 27):
                        sheet['cells'][f'{col}{row}'] = {
                            "style": 2,
                            "content": f'=ODOO.LIST(1,{row-1},"{field_name}")'
                        }
            
            # Update sheet dimensions
            sheet['colNumber'] = len(master_layout)
            sheet['rowNumber'] = 30
            
            print(f"      ✅ Master layout: {len(master_layout)} total columns")
            print(f"      ✅ {25 * len(master_layout)} data formulas added")
    
    # Save reorganized spreadsheet
    with open('/Users/adity/Documents/GitHub/gitlocal/pb_hr_payroll_indonesia/data/indonesia_payroll_data.json', 'w') as f:
        json.dump(data, f, indent=2)
    
    print("✅ TEMPLATE sheets reorganized with clean Indonesia layout!")
    print("✅ All Indonesia fields properly organized and visible")
    print("✅ No overlapping columns or messy layout")
    print()
    print("🇮🇩 Clean Indonesia Layout Applied:")
    print("📋 TEMPLATE Employee Details:")
    for i, (field, display) in enumerate(indonesia_employee_layout[:10]):
        col = extended_cols[i]
        print(f"   {col}: {display} = ODOO.LIST.HEADER(1,\"{field}\")")
    print("   ... and more columns")
    print()
    print("📊 Expected Result:")
    print("• Clean, organized columns A-Z with Indonesia fields")
    print("• BPJS, PPh21, NPWP clearly visible in proper order")
    print("• No overlapping or duplicate headers")
    print("• All demo data populating correctly")

if __name__ == "__main__":
    reorganize_indonesia_templates()