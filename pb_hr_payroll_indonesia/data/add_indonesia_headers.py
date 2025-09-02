#!/usr/bin/env python3
"""
Add Indonesia Field Headers to Spreadsheet Template Sheets
========================================================

This adds actual Indonesia field headers (like BPJS, PPh21, NPWP) to the 
TEMPLATE sheets so they appear in the generated spreadsheet.
"""
import json

def add_indonesia_headers_to_sheets():
    # Load current Indonesia spreadsheet
    with open('/Users/adity/Documents/GitHub/gitlocal/pb_hr_payroll_indonesia/data/indonesia_payroll_data.json', 'r') as f:
        data = json.load(f)
    
    print("🇮🇩 Adding Indonesia field headers to template sheets...")
    
    # Indonesia headers to add (replace some Vietnam headers)
    indonesia_headers = [
        ('npwp_number', 'NPWP Number'),
        ('bpjs_kesehatan_employee', 'BPJS Health-Emp'),
        ('bpjs_tk_jht_employee', 'BPJS JHT-Emp'),
        ('bpjs_tk_jp_employee', 'BPJS JP-Emp'),
        ('pph21', 'PPh21 Tax'),
        ('tunjangan_sewa_rumah', 'Housing Allow'),
        ('gross_pay_idn', 'Gross Pay IDN'),
        ('koperasi', 'Cooperative'),
        ('pinjaman', 'Loans'),
        ('union_dues', 'Union Dues'),
        ('fixed_allowance_1', 'Fixed Allow 1'),
        ('fixed_allowance_2', 'Fixed Allow 2'),
        ('commission', 'Commission'),
        ('bpjs_kesehatan_employer', 'BPJS Health-Emp'),
        ('bpjs_tk_jht_employer', 'BPJS JHT-Emp'),
    ]
    
    # Column letters for easy mapping
    col_letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZAAABACADAEAFAGAHAIAJAKALAMANAOAPAQARASATAUAVAWAXAYAZ'
    
    # Process TEMPLATE sheets
    for sheet in data['sheets']:
        if 'TEMPLATE' in sheet['name']:
            print(f"   🔧 Adding Indonesia headers to: {sheet['name']}")
            
            # Get current column count
            current_cols = sheet.get('colNumber', 25)
            
            # Add Indonesia headers starting from column after existing ones
            start_col_index = current_cols
            headers_added = 0
            
            for i, (field_name, display_name) in enumerate(indonesia_headers):
                col_index = start_col_index + i
                if col_index < len(col_letters):
                    col_letter = col_letters[col_index]
                    
                    # Add header with ODOO.LIST.HEADER formula
                    sheet['cells'][f'{col_letter}1'] = {
                        "style": 1,
                        "content": f'=ODOO.LIST.HEADER(1,"{field_name}")'
                    }
                    
                    # Add data formulas for first few rows
                    for row in range(2, 7):  # Add 5 data rows
                        sheet['cells'][f'{col_letter}{row}'] = {
                            "style": 2,
                            "content": f'=ODOO.LIST(1,{row-1},"{field_name}")'
                        }
                    
                    headers_added += 1
                    
                    # Update column count if needed
                    if col_index >= current_cols:
                        sheet['colNumber'] = col_index + 1
            
            print(f"      ✅ Added {headers_added} Indonesia headers")
            print(f"      ✅ Updated column count to {sheet['colNumber']}")
    
    # Also update reference sheets (Allowance Details, Earnings Details) with Indonesia data
    print("   🔧 Updating reference sheets with Indonesia field names...")
    
    for sheet in data['sheets']:
        if sheet['name'] == 'Allowance Details':
            # Update allowance headers to Indonesia fields
            indonesia_allowance_headers = [
                "Employee ID", "Tunjangan Sewa Rumah", "Gas Allowance", "Phone Allowance",
                "Meal Allowance", "Fixed Allowance 1", "Fixed Allowance 2", "Commission",
                "Thirteenth Month", "Other Income", "Gross Pay IDN", "NPWP Number"
            ]
            
            # Update headers
            for i, header in enumerate(indonesia_allowance_headers):
                if i < len(col_letters):
                    col = col_letters[i]
                    if f'{col}1' in sheet['cells']:
                        sheet['cells'][f'{col}1']['content'] = header
            
            # Extend column count if needed
            sheet['colNumber'] = max(sheet['colNumber'], len(indonesia_allowance_headers))
            print(f"      ✅ Updated Allowance Details sheet headers")
        
        elif sheet['name'] == 'Earnings Details':
            # Update earnings headers to Indonesia fields  
            indonesia_earnings_headers = [
                "Employee ID", "BPJS Kesehatan Employee", "BPJS JHT Employee", "BPJS JP Employee",
                "BPJS Kesehatan Employer", "BPJS JHT Employer", "BPJS JP Employer", "BPJS JKK",
                "BPJS JKM", "Union Dues", "Koperasi", "Pinjaman", "Loan Deductions", "PPh21"
            ]
            
            # Update headers
            for i, header in enumerate(indonesia_earnings_headers):
                if i < len(col_letters):
                    col = col_letters[i]
                    if f'{col}1' in sheet['cells']:
                        sheet['cells'][f'{col}1']['content'] = header
            
            # Extend column count if needed
            sheet['colNumber'] = max(sheet['colNumber'], len(indonesia_earnings_headers))
            print(f"      ✅ Updated Earnings Details sheet headers")
    
    # Save updated spreadsheet
    with open('/Users/adity/Documents/GitHub/gitlocal/pb_hr_payroll_indonesia/data/indonesia_payroll_data.json', 'w') as f:
        json.dump(data, f, indent=2)
    
    print("✅ Indonesia headers added to spreadsheet template sheets!")
    print("✅ TEMPLATE sheets now include Indonesia field headers")
    print("✅ Reference sheets updated with Indonesia terminology")
    print()
    print("🇮🇩 New Indonesia Headers Available:")
    for field_name, display_name in indonesia_headers:
        print(f"   • {display_name}: =ODOO.LIST.HEADER(1,\"{field_name}\")")
    print()
    print("📊 Expected Result:")
    print("• Open spreadsheet and see Indonesia headers in template sheets")
    print("• BPJS, PPh21, NPWP, Tunjangan columns visible")
    print("• All Indonesia formulas working with demo data")

if __name__ == "__main__":
    add_indonesia_headers_to_sheets()