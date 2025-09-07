#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhance India Multi-Tab Spreadsheet with Additional Payroll Components
=====================================================================

This script enhances the existing India payroll spreadsheet with
additional India-specific components and proper calculation formulas.

Author: Claude Code Assistant  
Date: 2025-09-07
"""

import json
import uuid
import copy

def enhance_india_spreadsheet():
    """Enhance India payroll spreadsheet with additional components and formulas"""
    
    # Load current India spreadsheet
    try:
        with open('/Users/adity/Documents/GitHub/gitlocal/pb_hr_payroll_india/data/india_payroll_data.json', 'r') as f:
            india_data = json.load(f)
    except FileNotFoundError:
        print("❌ India spreadsheet not found. Please generate it first.")
        return None
    
    # Define additional India-specific components
    additional_components = {
        # Additional Allowances
        "BOOKS_PERIODICALS": "Books and Periodicals",
        "TELEPHONE_INTERNET": "Telephone and Internet", 
        "LEAVE_TRAVEL_ALLOWANCE": "Leave Travel Allowance",
        "MEDICAL_ALLOWANCE": "Medical Allowance",
        "TRANSPORT_ALLOWANCE": "Transport Allowance",
        "MEAL_ALLOWANCE": "Meal Allowance",
        "PERFORMANCE_BONUS": "Performance Bonus",
        
        # Tax and Compliance Components
        "ESI_EMPLOYEE": "ESI - Employee",
        "ESI_EMPLOYER": "ESI - Employer", 
        "PF_EMPLOYEE": "PF - Employee",
        "PF_EMPLOYER": "PF - Employer",
        "PROF_TAX": "Professional Tax",
        "INCOME_TAX": "Income Tax (TDS)",
        "IND_GROSS": "Gross Pay",
        
        # Deductions
        "LOAN_DEDUCTION": "Loan Deduction",
        "ADVANCE_DEDUCTION": "Advance Deduction",
        "OTHER_DEDUCTIONS": "Other Deductions",
        
        # Total calculations
        "TOTAL_ALLOWANCES": "Total Allowances",
        "TOTAL_DEDUCTIONS": "Total Deductions",
        "TOTAL_EMPLOYER_CONTRIB": "Total Employer Contributions",
        "NETPAY": "Net Pay"
    }
    
    # Sample calculation data for India employees
    india_calc_data = [
        {"basic": 50000, "hra": 25000, "special": 10000, "books": 1200, "phone": 2000, "lta": 8000, 
         "medical": 3000, "transport": 4000, "meal": 2000, "bonus": 5000},
        {"basic": 45000, "hra": 22500, "special": 8000, "books": 1200, "phone": 2000, "lta": 7200, 
         "medical": 3000, "transport": 4000, "meal": 2000, "bonus": 4500},
        {"basic": 60000, "hra": 30000, "special": 12000, "books": 1200, "phone": 2000, "lta": 9600, 
         "medical": 3000, "transport": 4000, "meal": 2000, "bonus": 6000},
        {"basic": 40000, "hra": 20000, "special": 7000, "books": 1200, "phone": 2000, "lta": 6400, 
         "medical": 3000, "transport": 4000, "meal": 2000, "bonus": 4000},
        {"basic": 55000, "hra": 27500, "special": 9000, "books": 1200, "phone": 2000, "lta": 8800, 
         "medical": 3000, "transport": 4000, "meal": 2000, "bonus": 5500},
    ]
    
    # Process each sheet to add components
    for sheet_idx, sheet in enumerate(india_data["sheets"]):
        sheet_name = sheet.get("name", "")
        
        # Enhance the main "India Allowance Details" sheet
        if sheet_name == "India Allowance Details":
            print(f"🔧 Enhancing sheet: {sheet_name}")
            
            # Current basic structure already exists (A-D columns)
            # Add new components starting from column E onwards
            new_columns = [
                ("E", "BOOKS_PERIODICALS", "Books & Periodicals"),
                ("F", "TELEPHONE_INTERNET", "Phone & Internet"),
                ("G", "LEAVE_TRAVEL_ALLOWANCE", "LTA"),
                ("H", "MEDICAL_ALLOWANCE", "Medical Allowance"),
                ("I", "TRANSPORT_ALLOWANCE", "Transport Allowance"), 
                ("J", "MEAL_ALLOWANCE", "Meal Allowance"),
                ("K", "PERFORMANCE_BONUS", "Performance Bonus"),
                ("L", "IND_GROSS", "Gross Pay"),
                ("M", "PF_EMPLOYEE", "PF Employee"),
                ("N", "ESI_EMPLOYEE", "ESI Employee"),
                ("O", "PROF_TAX", "Professional Tax"),
                ("P", "INCOME_TAX", "Income Tax"),
                ("Q", "TOTAL_DEDUCTIONS", "Total Deductions"),
                ("R", "NETPAY", "Net Pay"),
                ("S", "PF_EMPLOYER", "PF Employer"),
                ("T", "ESI_EMPLOYER", "ESI Employer")
            ]
            
            # Add headers
            for col, code, header in new_columns:
                sheet["cells"][f"{col}1"] = {
                    "style": 1,
                    "content": header
                }
            
            # Add sample data with proper formulas
            for row in range(2, 7):  # Rows 2-6 for sample employees
                emp_idx = row - 2
                if emp_idx < len(india_calc_data):
                    calc_data = india_calc_data[emp_idx]
                    
                    # Add allowance data
                    sheet["cells"][f"E{row}"] = {"style": 2, "content": str(calc_data["books"])}
                    sheet["cells"][f"F{row}"] = {"style": 2, "content": str(calc_data["phone"])}
                    sheet["cells"][f"G{row}"] = {"style": 2, "content": str(calc_data["lta"])}
                    sheet["cells"][f"H{row}"] = {"style": 2, "content": str(calc_data["medical"])}
                    sheet["cells"][f"I{row}"] = {"style": 2, "content": str(calc_data["transport"])}
                    sheet["cells"][f"J{row}"] = {"style": 2, "content": str(calc_data["meal"])}
                    sheet["cells"][f"K{row}"] = {"style": 2, "content": str(calc_data["bonus"])}
                    
                    # Gross Pay Formula (Sum of Basic + HRA + Special + Other allowances)
                    sheet["cells"][f"L{row}"] = {
                        "style": 2, 
                        "content": f"=A{row}+B{row}+C{row}+D{row}+E{row}+F{row}+G{row}+H{row}+I{row}+J{row}+K{row}"
                    }
                    
                    # PF Employee (12% of Basic, max 1800)
                    sheet["cells"][f"M{row}"] = {
                        "style": 2, 
                        "content": f"=MIN(A{row}*0.12,1800)"
                    }
                    
                    # ESI Employee (0.75% of Gross if Gross <= 25000)
                    sheet["cells"][f"N{row}"] = {
                        "style": 2, 
                        "content": f"=IF(L{row}<=25000,L{row}*0.0075,0)"
                    }
                    
                    # Professional Tax (varies by state, using Karnataka rates)
                    sheet["cells"][f"O{row}"] = {
                        "style": 2, 
                        "content": f"=IF(L{row}<=15000,0,IF(L{row}<=20000,150,200))"
                    }
                    
                    # Income Tax (simplified TDS calculation - 10% above 50000)
                    sheet["cells"][f"P{row}"] = {
                        "style": 2, 
                        "content": f"=IF(L{row}>50000,(L{row}-50000)*0.1,0)"
                    }
                    
                    # Total Deductions
                    sheet["cells"][f"Q{row}"] = {
                        "style": 2, 
                        "content": f"=M{row}+N{row}+O{row}+P{row}"
                    }
                    
                    # Net Pay
                    sheet["cells"][f"R{row}"] = {
                        "style": 2, 
                        "content": f"=L{row}-Q{row}"
                    }
                    
                    # PF Employer (12% of Basic)
                    sheet["cells"][f"S{row}"] = {
                        "style": 2, 
                        "content": f"=A{row}*0.12"
                    }
                    
                    # ESI Employer (3.25% of Gross if applicable)
                    sheet["cells"][f"T{row}"] = {
                        "style": 2, 
                        "content": f"=IF(L{row}<=25000,L{row}*0.0325,0)"
                    }
            
            # Update column count to include new columns
            sheet["colNumber"] = 20  # A-T = 20 columns
            
        # Enhance "India Earnings Details" sheet with summary formulas
        elif sheet_name == "India Earnings Details":
            print(f"🔧 Enhancing sheet: {sheet_name}")
            
            # Add earnings summary with ODOO.LIST references
            earnings_headers = [
                ("A", "Employee ID"),
                ("B", "Basic Salary"), 
                ("C", "HRA"),
                ("D", "Special Allowance"),
                ("E", "Books & Periodicals"),
                ("F", "Phone & Internet"),
                ("G", "LTA"),
                ("H", "Medical Allowance"),
                ("I", "Transport Allowance"),
                ("J", "Meal Allowance"),
                ("K", "Performance Bonus"),
                ("L", "Gross Earnings")
            ]
            
            # Add headers with ODOO.LIST.HEADER references
            for col, header in earnings_headers:
                if col == "A":
                    sheet["cells"][f"{col}1"] = {
                        "style": 1,
                        "content": '=ODOO.LIST.HEADER(1,"employee_id")'
                    }
                elif col == "B":
                    sheet["cells"][f"{col}1"] = {
                        "style": 1,
                        "content": '=ODOO.LIST.HEADER(1,"basic_salary")'
                    }
                elif col == "C":
                    sheet["cells"][f"{col}1"] = {
                        "style": 1,
                        "content": '=ODOO.LIST.HEADER(1,"hra")'
                    }
                elif col == "D":
                    sheet["cells"][f"{col}1"] = {
                        "style": 1,
                        "content": '=ODOO.LIST.HEADER(1,"special_allowance")'
                    }
                else:
                    sheet["cells"][f"{col}1"] = {
                        "style": 1,
                        "content": header
                    }
            
            # Add ODOO.LIST data references
            for row in range(2, 12):  # 10 rows of data
                sheet["cells"][f"A{row}"] = {
                    "style": 2,
                    "content": f'=ODOO.LIST(1,{row-1},"employee_id")'
                }
                sheet["cells"][f"B{row}"] = {
                    "style": 2,
                    "content": f'=ODOO.LIST(1,{row-1},"basic_salary")'
                }
                sheet["cells"][f"C{row}"] = {
                    "style": 2,
                    "content": f'=ODOO.LIST(1,{row-1},"hra")'
                }
                sheet["cells"][f"D{row}"] = {
                    "style": 2,
                    "content": f'=ODOO.LIST(1,{row-1},"special_allowance")'
                }
                # Gross calculation
                sheet["cells"][f"L{row}"] = {
                    "style": 2,
                    "content": f"=B{row}+C{row}+D{row}+E{row}+F{row}+G{row}+H{row}+I{row}+J{row}+K{row}"
                }
    
    # Add India-specific styling
    if "styles" in india_data:
        # Enhanced India color scheme
        india_colors = {
            "1": {"fillColor": "#FF6B35", "textColor": "#FFFFFF", "fontSize": 12, "bold": True},  # Header - Saffron
            "2": {"fillColor": "#FFF8E1", "textColor": "#E65100", "fontSize": 11},  # Data - Light Orange
            "3": {"fillColor": "#138808", "textColor": "#FFFFFF", "fontSize": 11, "bold": True},  # Green - Success
            "4": {"fillColor": "#000080", "textColor": "#FFFFFF", "fontSize": 11}   # Navy Blue - Totals
        }
        
        for style_id, style_props in india_colors.items():
            india_data["styles"][style_id] = style_props
    
    return india_data

def main():
    """Main function to enhance and save the India spreadsheet"""
    print("🇮🇳 Enhancing India Payroll Spreadsheet with Additional Components...")
    print("📊 Adding India-specific payroll calculations and formulas")
    print("=" * 70)
    
    # Enhance the spreadsheet data
    try:
        enhanced_data = enhance_india_spreadsheet()
        
        if enhanced_data:
            # Save enhanced version
            output_file = "/Users/adity/Documents/GitHub/gitlocal/pb_hr_payroll_india/data/india_payroll_data.json"
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(enhanced_data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Enhanced India spreadsheet: {output_file}")
            print(f"\n📊 Enhanced Features Added:")
            print("• Additional Allowances:")
            print("  - Books & Periodicals, Phone & Internet, LTA")
            print("  - Medical, Transport, Meal Allowances")
            print("  - Performance Bonus")
            print("• Compliance Calculations:")
            print("  - PF Employee/Employer (12% of Basic)")
            print("  - ESI Employee (0.75%) / Employer (3.25%)")
            print("  - Professional Tax (State-based)")
            print("  - Income Tax/TDS (Simplified)")
            print("• Summary Formulas:")
            print("  - Gross Pay calculation")
            print("  - Total Deductions")
            print("  - Net Pay calculation")
            print("• ODOO Integration:")
            print("  - ODOO.LIST references for data binding")
            print("  - Dynamic header generation")
            print("• Professional Styling:")
            print("  - India color theme (Saffron/Orange)")
            print("  - Proper cell formatting")
            
            return output_file
            
    except Exception as e:
        print(f"❌ Error enhancing spreadsheet: {e}")
        return None

if __name__ == "__main__":
    main()