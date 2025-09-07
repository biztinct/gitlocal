#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate India Payroll Spreadsheet JSON
========================================

This script creates a properly structured Indian payroll spreadsheet following
the same pattern as Vietnam and Indonesia modules.

Author: Claude Code Assistant  
Date: 2025-09-07
"""

import json
import uuid

def generate_india_payroll_spreadsheet():
    """Generate India payroll spreadsheet JSON structure"""
    
    # India-specific columns following payroll flow
    columns = [
        # Employee Information
        {"col": "A", "field": "employee_id", "header": "Employee ID", "type": "data"},
        {"col": "B", "field": "employee_name", "header": "Employee Name", "type": "data"},
        {"col": "C", "field": "department", "header": "Department", "type": "data"},
        
        # Base Compensation
        {"col": "D", "field": "basic_salary", "header": "Basic Salary", "type": "data"},
        {"col": "E", "field": "hra", "header": "HRA", "type": "data"},
        {"col": "F", "field": "special_allowance", "header": "Special Allowance", "type": "data"},
        {"col": "G", "field": "other_allowances", "header": "Other Allowances", "type": "data"},
        
        # Calculated Gross
        {"col": "H", "field": "gross_salary", "header": "Gross Salary", "type": "formula", "formula": "=D{row}+E{row}+F{row}+G{row}"},
        
        # Employee Deductions
        {"col": "I", "field": "pf_employee", "header": "PF (Employee)", "type": "formula", "formula": "=ROUND(D{row}*0.12,0)"},
        {"col": "J", "field": "esi_employee", "header": "ESI (Employee)", "type": "formula", "formula": "=IF(H{row}<=21000,ROUND(H{row}*0.0075,0),0)"},
        {"col": "K", "field": "professional_tax", "header": "Professional Tax", "type": "data"},
        {"col": "L", "field": "income_tax", "header": "Income Tax (TDS)", "type": "data"},
        {"col": "M", "field": "other_deductions", "header": "Other Deductions", "type": "data"},
        
        # Total Deductions
        {"col": "N", "field": "total_deductions", "header": "Total Deductions", "type": "formula", "formula": "=SUM(I{row}:M{row})"},
        
        # Net Pay
        {"col": "O", "field": "net_pay", "header": "Net Pay", "type": "formula", "formula": "=H{row}-N{row}"},
        
        # Employer Contributions (For Information)
        {"col": "P", "field": "pf_employer", "header": "PF (Employer)", "type": "formula", "formula": "=ROUND(D{row}*0.12,0)"},
        {"col": "Q", "field": "esi_employer", "header": "ESI (Employer)", "type": "formula", "formula": "=IF(H{row}<=21000,ROUND(H{row}*0.0325,0),0)"},
        {"col": "R", "field": "gratuity", "header": "Gratuity", "type": "formula", "formula": "=ROUND(D{row}/26*15,0)"},
        
        # ID Numbers (For Reference)
        {"col": "S", "field": "pan_number", "header": "PAN Number", "type": "data"},
        {"col": "T", "field": "aadhaar_number", "header": "Aadhaar Number", "type": "data"},
        {"col": "U", "field": "pf_number", "header": "PF Number", "type": "data"},
        {"col": "V", "field": "esi_number", "header": "ESI Number", "type": "data"},
    ]
    
    # Generate spreadsheet JSON structure
    spreadsheet_data = {
        "version": 12.5,
        "sheets": [{
            "id": str(uuid.uuid4()),
            "name": "India Payroll Data",
            "colNumber": len(columns) + 5,
            "rowNumber": 72,
            "rows": {},
            "cols": {
                "1": {"size": 150},  # Employee ID column width
                "2": {"size": 200},  # Employee name column width
            },
            "merges": [],
            "cells": {},
        }],
        "entities": {},
        "styles": {
            "1": {  # Header style
                "bold": True,
                "fillColor": "#FF6B35",  # India saffron color
                "textColor": "#FFFFFF"
            },
            "2": {  # Data style
                "textColor": "#000000"
            },
            "3": {  # Formula style
                "textColor": "#0066CC"
            }
        },
        "formats": {},
        "borders": {},
        "lists": {
            "1": {
                "columns": [col["field"] for col in columns],
                "domain": [],
                "model": "zoho.staging.data",
                "context": {},
                "orderBy": [],
                "id": "1",
                "name": "India Employee Staging Data",
                "fieldMatching": {}
            }
        },
        "listNextId": 2,
        "chartOdooMenusReferences": {}
    }
    
    # Generate cells for headers and sample data
    cells = {}
    
    # Generate header row (row 1)
    for i, col_info in enumerate(columns):
        col = col_info["col"]
        field = col_info["field"]
        
        # Header cell
        cells[f"{col}1"] = {
            "style": 1,
            "content": f'=ODOO.LIST.HEADER(1,"{field}")'
        }
    
    # Generate sample data rows (rows 2-6)
    sample_employees = [
        {"id": "IND001", "name": "Rajesh Kumar", "basic": 50000, "hra": 25000, "special": 10000},
        {"id": "IND002", "name": "Priya Sharma", "basic": 45000, "hra": 22500, "special": 8000},
        {"id": "IND003", "name": "Amit Singh", "basic": 60000, "hra": 30000, "special": 12000},
        {"id": "IND004", "name": "Sunita Gupta", "basic": 40000, "hra": 20000, "special": 7000},
        {"id": "IND005", "name": "Vikram Patel", "basic": 55000, "hra": 27500, "special": 9000},
    ]
    
    for row_idx, emp in enumerate(sample_employees, start=2):
        for col_info in columns:
            col = col_info["col"]
            field = col_info["field"]
            cell_type = col_info["type"]
            
            cell_ref = f"{col}{row_idx}"
            
            if cell_type == "formula":
                # Generate formula for this row
                formula = col_info["formula"].format(row=row_idx)
                cells[cell_ref] = {
                    "style": 3,
                    "content": formula
                }
            elif cell_type == "data":
                # Generate sample data based on field type
                if field == "employee_id":
                    cells[cell_ref] = {"style": 2, "content": emp["id"]}
                elif field == "employee_name":
                    cells[cell_ref] = {"style": 2, "content": emp["name"]}
                elif field == "basic_salary":
                    cells[cell_ref] = {"style": 2, "content": str(emp["basic"])}
                elif field == "hra":
                    cells[cell_ref] = {"style": 2, "content": str(emp["hra"])}
                elif field == "special_allowance":
                    cells[cell_ref] = {"style": 2, "content": str(emp["special"])}
                elif field == "professional_tax":
                    cells[cell_ref] = {"style": 2, "content": "200"}
                elif field == "department":
                    cells[cell_ref] = {"style": 2, "content": "IT Department"}
                else:
                    cells[cell_ref] = {"style": 2, "content": "0"}
    
    # Add cells to spreadsheet
    spreadsheet_data["sheets"][0]["cells"] = cells
    
    return spreadsheet_data

def main():
    """Main function to generate and save the India spreadsheet"""
    print("🇮🇳 Generating India Payroll Spreadsheet...")
    print("=" * 50)
    
    # Generate the spreadsheet data
    spreadsheet_data = generate_india_payroll_spreadsheet()
    
    # Save to JSON file
    output_file = "/Users/adity/Documents/GitHub/gitlocal/pb_hr_payroll_india/data/india_payroll_data.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(spreadsheet_data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Generated India spreadsheet: {output_file}")
    print("\n🔧 India Payroll Features:")
    print("• Basic Salary, HRA, Special Allowance structure")
    print("• PF calculations: 12% employee + 12% employer")
    print("• ESI calculations: 0.75% employee + 3.25% employer (if gross <= ₹21,000)")
    print("• Professional Tax and Income Tax (TDS)")
    print("• Gratuity calculations")
    print("• Indian compliance with PAN, Aadhaar, PF, ESI numbers")
    
    return output_file

if __name__ == "__main__":
    main()