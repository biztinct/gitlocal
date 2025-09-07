#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fix Template Sheets for India - Colors and India-Specific Columns
================================================================

This script fixes colors and adds India-specific columns to:
- TEMPLATE India Employee Details
- TEMPLATE India Master

Author: Claude Code Assistant  
Date: 2025-09-07
"""

import json
import copy

def fix_template_sheets():
    """Fix template sheets with colors and India-specific columns"""
    
    # Load current India spreadsheet
    try:
        with open('/Users/adity/Documents/GitHub/gitlocal/pb_hr_payroll_india/data/india_payroll_data.json', 'r') as f:
            india_data = json.load(f)
    except FileNotFoundError:
        print("❌ India spreadsheet not found.")
        return None
    
    # Light, professional color scheme
    light_styles = {
        "1": {  # Headers
            "fillColor": "#F5F5F5",  # Very light gray
            "textColor": "#2E7D32",  # Dark green
            "fontSize": 12,
            "bold": True,
            "border": "1px solid #CCCCCC"
        },
        "2": {  # Data cells
            "fillColor": "#FFFFFF",  # Pure white
            "textColor": "#333333",  # Dark gray text
            "fontSize": 11,
            "border": "1px solid #E0E0E0"
        },
        "3": {  # Calculation cells
            "fillColor": "#F8F9FA",  # Very light blue-gray
            "textColor": "#1976D2",  # Blue
            "fontSize": 11,
            "bold": False
        },
        "4": {  # Total/Summary cells
            "fillColor": "#E8F5E8",  # Very light green
            "textColor": "#2E7D32",  # Dark green
            "fontSize": 11,
            "bold": True
        },
        "5": {  # Alternative row color
            "fillColor": "#FAFAFA",  # Very light gray
            "textColor": "#333333",
            "fontSize": 11
        }
    }
    
    # Update global styles
    if "styles" in india_data:
        india_data["styles"].update(light_styles)
    
    # India-specific template columns structure
    india_template_columns = [
        ("A", "employee_id", "Employee ID"),
        ("B", "basic_salary", "Basic Salary"),
        ("C", "hra", "HRA"),
        ("D", "special_allowance", "Special Allowance"),
        ("E", "books_periodicals", "Books & Periodicals"),
        ("F", "telephone_internet", "Phone & Internet"),
        ("G", "leave_travel_allowance", "LTA"),
        ("H", "medical_allowance", "Medical Allowance"),
        ("I", "transport_allowance", "Transport Allowance"),
        ("J", "meal_allowance", "Meal Allowance"),
        ("K", "performance_bonus", "Performance Bonus"),
        ("L", "gross_salary", "Gross Pay"),
        ("M", "pf_employee", "PF Employee"),
        ("N", "esi_employee", "ESI Employee"),
        ("O", "professional_tax", "Professional Tax"),
        ("P", "income_tax", "Income Tax"),
        ("Q", "total_deductions", "Total Deductions"),
        ("R", "net_pay", "Net Pay"),
        ("S", "pf_employer", "PF Employer"),
        ("T", "esi_employer", "ESI Employer")
    ]
    
    # Process each sheet
    for sheet_idx, sheet in enumerate(india_data["sheets"]):
        sheet_name = sheet.get("name", "")
        print(f"🔧 Processing sheet: {sheet_name}")
        
        # Fix TEMPLATE India Employee Details
        if sheet_name == "TEMPLATE India Employee Details":
            print(f"   📋 Adding India-specific columns and formulas...")
            
            # Clear existing cells and rebuild with India structure
            sheet["cells"] = {}
            sheet["colNumber"] = 20  # A-T = 20 columns
            
            # Add headers with ODOO.LIST.HEADER references
            for col, field, header in india_template_columns:
                sheet["cells"][f"{col}1"] = {
                    "style": 1,
                    "content": f'=ODOO.LIST.HEADER(1,"{field}")'
                }
            
            # Add template data rows (rows 2-6)
            for row in range(2, 7):
                for col, field, header in india_template_columns:
                    if col in ['A', 'B', 'C', 'D']:  # Basic fields with ODOO.LIST
                        sheet["cells"][f"{col}{row}"] = {
                            "style": 2,
                            "content": f'=ODOO.LIST(1,{row-1},"{field}")'
                        }
                    elif col in ['E', 'F', 'G', 'H', 'I', 'J', 'K']:  # Additional allowances
                        sheet["cells"][f"{col}{row}"] = {
                            "style": 2,
                            "content": f'=ODOO.LIST(1,{row-1},"{field}")'
                        }
                    elif col == 'L':  # Gross Pay Formula
                        sheet["cells"][f"{col}{row}"] = {
                            "style": 3,
                            "content": f"=B{row}+C{row}+D{row}+E{row}+F{row}+G{row}+H{row}+I{row}+J{row}+K{row}"
                        }
                    elif col == 'M':  # PF Employee
                        sheet["cells"][f"{col}{row}"] = {
                            "style": 3,
                            "content": f"=MIN(B{row}*0.12,1800)"
                        }
                    elif col == 'N':  # ESI Employee
                        sheet["cells"][f"{col}{row}"] = {
                            "style": 3,
                            "content": f"=IF(L{row}<=25000,L{row}*0.0075,0)"
                        }
                    elif col == 'O':  # Professional Tax
                        sheet["cells"][f"{col}{row}"] = {
                            "style": 3,
                            "content": f"=IF(L{row}<=15000,0,IF(L{row}<=20000,150,200))"
                        }
                    elif col == 'P':  # Income Tax
                        sheet["cells"][f"{col}{row}"] = {
                            "style": 3,
                            "content": f"=IF(L{row}>50000,(L{row}-50000)*0.1,0)"
                        }
                    elif col == 'Q':  # Total Deductions
                        sheet["cells"][f"{col}{row}"] = {
                            "style": 4,
                            "content": f"=M{row}+N{row}+O{row}+P{row}"
                        }
                    elif col == 'R':  # Net Pay
                        sheet["cells"][f"{col}{row}"] = {
                            "style": 4,
                            "content": f"=L{row}-Q{row}"
                        }
                    elif col == 'S':  # PF Employer
                        sheet["cells"][f"{col}{row}"] = {
                            "style": 3,
                            "content": f"=B{row}*0.12"
                        }
                    elif col == 'T':  # ESI Employer
                        sheet["cells"][f"{col}{row}"] = {
                            "style": 3,
                            "content": f"=IF(L{row}<=25000,L{row}*0.0325,0)"
                        }
            
            print(f"   ✅ Added 20 columns (A-T) with India-specific formulas")
            
        # Fix TEMPLATE India Master
        elif sheet_name == "TEMPLATE India Master":
            print(f"   📋 Adding India master data structure...")
            
            # Clear existing cells and rebuild
            sheet["cells"] = {}
            sheet["colNumber"] = 20
            
            # Master data headers
            master_headers = [
                ("A", "Employee ID"),
                ("B", "Full Name"),
                ("C", "Department"),
                ("D", "Designation"),
                ("E", "Date of Joining"),
                ("F", "PAN Number"),
                ("G", "Aadhaar Number"),
                ("H", "PF Number"),
                ("I", "ESI Number"),
                ("J", "Bank Account"),
                ("K", "IFSC Code"),
                ("L", "Location"),
                ("M", "State"),
                ("N", "Professional Tax State"),
                ("O", "Employee Type"),
                ("P", "Contract Type"),
                ("Q", "Basic Salary"),
                ("R", "HRA Rate"),
                ("S", "PF Applicable"),
                ("T", "ESI Applicable")
            ]
            
            # Add master headers
            for col, header in master_headers:
                sheet["cells"][f"{col}1"] = {
                    "style": 1,
                    "content": header
                }
            
            # Add sample master data (rows 2-6)
            sample_master_data = [
                ["IND001", "Rajesh Kumar", "IT", "Software Engineer", "01-Apr-2020", "ABCDE1234F", "1234-5678-9012", "DL/12345/67890", "1234567890", "12345678901234", "SBIN0001234", "Delhi", "Delhi", "Delhi", "Permanent", "Full Time", "50000", "0.5", "Yes", "Yes"],
                ["IND002", "Priya Sharma", "HR", "HR Manager", "15-Mar-2019", "FGHIJ5678K", "2345-6789-0123", "MH/23456/78901", "2345678901", "23456789012345", "HDFC0002345", "Mumbai", "Maharashtra", "Maharashtra", "Permanent", "Full Time", "45000", "0.5", "Yes", "Yes"],
                ["IND003", "Amit Singh", "Finance", "Accountant", "10-Jan-2021", "KLMNO9012P", "3456-7890-1234", "KA/34567/89012", "3456789012", "34567890123456", "ICIC0003456", "Bangalore", "Karnataka", "Karnataka", "Permanent", "Full Time", "60000", "0.5", "Yes", "No"],
                ["IND004", "Sunita Gupta", "Sales", "Sales Executive", "05-May-2022", "PQRST2345U", "4567-8901-2345", "TN/45678/90123", "4567890123", "45678901234567", "AXIS0004567", "Chennai", "Tamil Nadu", "Tamil Nadu", "Permanent", "Full Time", "40000", "0.5", "Yes", "Yes"],
                ["IND005", "Vikram Patel", "IT", "Team Lead", "20-Feb-2020", "UVWXY6789Z", "5678-9012-3456", "GJ/56789/01234", "5678901234", "56789012345678", "SBI0005678", "Ahmedabad", "Gujarat", "Gujarat", "Permanent", "Full Time", "55000", "0.5", "Yes", "No"]
            ]
            
            for row_idx, row_data in enumerate(sample_master_data, start=2):
                for col_idx, value in enumerate(row_data):
                    col = chr(65 + col_idx)  # A=65, B=66, etc.
                    sheet["cells"][f"{col}{row_idx}"] = {
                        "style": 2,
                        "content": str(value)
                    }
            
            print(f"   ✅ Added 20 columns of master data with Indian employee information")
        
        # Fix colors in other sheets
        elif "cells" in sheet:
            print(f"   🎨 Fixing colors...")
            colors_fixed = 0
            for cell_key, cell_data in sheet["cells"].items():
                if "style" in cell_data:
                    # Ensure we're using light styles
                    if cell_data["style"] not in [1, 2, 3, 4, 5]:
                        cell_data["style"] = 2  # Default to light data style
                        colors_fixed += 1
            print(f"   ✅ Fixed colors in {colors_fixed} cells")
    
    return india_data

def main():
    """Main function to fix template sheets"""
    print("🇮🇳 Fixing India Template Sheets - Colors & India-Specific Columns")
    print("=" * 70)
    
    # Fix the template sheets
    try:
        fixed_data = fix_template_sheets()
        
        if fixed_data:
            # Save fixed version
            output_file = "/Users/adity/Documents/GitHub/gitlocal/pb_hr_payroll_india/data/india_payroll_data.json"
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(fixed_data, f, indent=2, ensure_ascii=False)
            
            print(f"\n✅ Fixed India template sheets: {output_file}")
            print(f"\n📊 Template Sheet Updates:")
            print("• TEMPLATE India Employee Details:")
            print("  - Added 20 columns (A-T) with India payroll components")
            print("  - Added ODOO.LIST.HEADER references for dynamic headers")
            print("  - Added proper Indian payroll calculation formulas")
            print("  - Applied light color scheme (white/light gray backgrounds)")
            print("• TEMPLATE India Master:")
            print("  - Added 20 columns of Indian employee master data")
            print("  - Included PAN, Aadhaar, PF, ESI numbers")
            print("  - Added state-wise professional tax information")
            print("  - Applied light color scheme for readability")
            print("• Color Scheme:")
            print("  - Headers: Light gray (#F5F5F5) with dark green text")
            print("  - Data: Pure white (#FFFFFF) with dark gray text")
            print("  - Calculations: Light blue-gray (#F8F9FA)")
            print("  - Totals: Light green (#E8F5E8)")
            
            return output_file
            
    except Exception as e:
        print(f"❌ Error fixing template sheets: {e}")
        return None

if __name__ == "__main__":
    main()