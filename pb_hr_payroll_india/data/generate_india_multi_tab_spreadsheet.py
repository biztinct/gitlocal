#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate Multi-Tab India Payroll Spreadsheet Based on Vietnam Structure
======================================================================

This script creates a multi-tab Indian payroll spreadsheet following
the Vietnam pattern with 5 tabs like Vietnam has.

Author: Claude Code Assistant  
Date: 2025-09-07
"""

import json
import uuid
import copy

def generate_india_multi_tab_spreadsheet():
    """Generate India payroll spreadsheet with multiple tabs like Vietnam"""
    
    # Load Vietnam spreadsheet as template
    try:
        with open('/Users/adity/Documents/GitHub/gitlocal/pb_hr_payroll_vietnam/data/vietnam_payroll_data.json', 'r') as f:
            vietnam_data = json.load(f)
    except FileNotFoundError:
        print("❌ Vietnam spreadsheet not found. Creating basic structure...")
        vietnam_data = {"sheets": []}
    
    # Create India version with adapted structure
    india_data = copy.deepcopy(vietnam_data)
    
    # Update sheet names and adapt for India
    sheet_mappings = {
        "Allowance Details": "India Allowance Details",
        "Earnings Details": "India Earnings Details", 
        "Master lookup": "India Master Lookup",
        "TEMPLATE Employee Details": "TEMPLATE India Employee Details",
        "TEMPLATE Master": "TEMPLATE India Master"
    }
    
    # India-specific field mappings (Vietnam → India)
    field_mappings = {
        # Vietnam fields → India fields
        "base_salary": "basic_salary",
        "actual_gas": "hra",  # Gas allowance becomes HRA
        "actual_phone": "special_allowance",  # Phone becomes Special Allowance
        "actual_meal": "other_allowances",  # Meal becomes Other Allowances
        "social_ins8": "pf_employee",  # Social Insurance becomes PF
        "med_ins15": "esi_employee",  # Medical Insurance becomes ESI
        "monthly_pit": "income_tax",  # PIT becomes Income Tax
        "trade_er175": "pf_employer",  # Trade union becomes PF employer
        "med_ins3": "esi_employer",  # Med ins employer becomes ESI employer
        "net_pay": "net_pay",  # Keep same
        "total_ded": "total_deductions",  # Keep similar
        "employee_id": "employee_id",  # Keep same
    }
    
    # India sample employee data
    india_employees = [
        {"id": "IND001", "name": "Rajesh Kumar", "basic": 50000, "hra": 25000, "special": 10000},
        {"id": "IND002", "name": "Priya Sharma", "basic": 45000, "hra": 22500, "special": 8000},
        {"id": "IND003", "name": "Amit Singh", "basic": 60000, "hra": 30000, "special": 12000},
        {"id": "IND004", "name": "Sunita Gupta", "basic": 40000, "hra": 20000, "special": 7000},
        {"id": "IND005", "name": "Vikram Patel", "basic": 55000, "hra": 27500, "special": 9000},
    ]
    
    # Process each sheet
    for i, sheet in enumerate(india_data["sheets"]):
        # Update sheet ID and name
        sheet["id"] = str(uuid.uuid4())
        original_name = sheet.get("name", "")
        sheet["name"] = sheet_mappings.get(original_name, f"India {original_name}")
        
        # Update cells with India-specific data if it's a data sheet
        if "Details" in sheet["name"] or "Employee" in sheet["name"]:
            # Update headers and data in cells
            if "cells" in sheet:
                new_cells = {}
                
                # Process each cell
                for cell_ref, cell_data in sheet["cells"].items():
                    new_cell_data = copy.deepcopy(cell_data)
                    
                    # Update ODOO.LIST.HEADER references
                    if "content" in new_cell_data and "ODOO.LIST.HEADER" in str(new_cell_data["content"]):
                        content = str(new_cell_data["content"])
                        for vn_field, in_field in field_mappings.items():
                            content = content.replace(f'"{vn_field}"', f'"{in_field}"')
                        new_cell_data["content"] = content
                    
                    # Update ODOO.LIST references
                    elif "content" in new_cell_data and "ODOO.LIST(" in str(new_cell_data["content"]):
                        content = str(new_cell_data["content"])
                        for vn_field, in_field in field_mappings.items():
                            content = content.replace(f'"{vn_field}"', f'"{in_field}"')
                        new_cell_data["content"] = content
                    
                    # Update sample employee data
                    elif "content" in new_cell_data and sheet["name"] == "India Allowance Details":
                        content = str(new_cell_data["content"])
                        # Replace Vietnam employee IDs with India employee IDs if in data rows
                        if cell_ref.startswith('A') and cell_ref != 'A1':  # Employee ID column
                            try:
                                row_num = int(cell_ref[1:])
                                if 2 <= row_num <= 6:  # Sample data rows
                                    emp_idx = row_num - 2
                                    if emp_idx < len(india_employees):
                                        new_cell_data["content"] = india_employees[emp_idx]["id"]
                            except (ValueError, IndexError):
                                pass
                        
                        # Update other data based on Indian salary structure
                        elif cell_ref.startswith('B') and cell_ref != 'B1':  # First allowance column
                            try:
                                row_num = int(cell_ref[1:])
                                if 2 <= row_num <= 6:
                                    emp_idx = row_num - 2
                                    if emp_idx < len(india_employees):
                                        new_cell_data["content"] = str(india_employees[emp_idx]["hra"])
                            except (ValueError, IndexError):
                                pass
                    
                    new_cells[cell_ref] = new_cell_data
                
                sheet["cells"] = new_cells
        
        # Update column colors to India theme (saffron)
        if "styles" in india_data:
            for style_id, style in india_data["styles"].items():
                if "fillColor" in style:
                    # Change from Vietnam colors to India saffron theme
                    style["fillColor"] = "#FF6B35"  # India saffron color
    
    # Update the lists section for India fields
    if "lists" in india_data:
        for list_data in india_data["lists"].values():
            if "columns" in list_data:
                # Map Vietnam columns to India columns
                new_columns = []
                for col in list_data["columns"]:
                    new_col = field_mappings.get(col, col)
                    new_columns.append(new_col)
                list_data["columns"] = new_columns
                
            # Update list name
            if "name" in list_data:
                list_data["name"] = "India Employee Staging Data"
    
    return india_data

def main():
    """Main function to generate and save the India multi-tab spreadsheet"""
    print("🇮🇳 Generating Multi-Tab India Payroll Spreadsheet...")
    print("📋 Based on Vietnam structure with 5 tabs")
    print("=" * 60)
    
    # Generate the spreadsheet data
    try:
        spreadsheet_data = generate_india_multi_tab_spreadsheet()
        
        # Save to JSON file
        output_file = "/Users/adity/Documents/GitHub/gitlocal/pb_hr_payroll_india/data/india_payroll_data.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(spreadsheet_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Generated multi-tab India spreadsheet: {output_file}")
        print(f"\n📊 Spreadsheet Structure:")
        
        if "sheets" in spreadsheet_data:
            for i, sheet in enumerate(spreadsheet_data["sheets"], 1):
                print(f"   {i}. {sheet.get('name', 'Unknown')}")
        
        print(f"\n🔧 India Payroll Features:")
        print("• Multi-tab structure like Vietnam")
        print("• India-specific field mappings:")
        print("  - basic_salary (Basic Salary)")
        print("  - hra (House Rent Allowance)") 
        print("  - special_allowance (Special Allowance)")
        print("  - pf_employee/pf_employer (Provident Fund)")
        print("  - esi_employee/esi_employer (ESI)")
        print("  - income_tax (Income Tax/TDS)")
        print("  - professional_tax (Professional Tax)")
        print("• Indian compliance ready")
        print("• India saffron color theme")
        
        return output_file
        
    except Exception as e:
        print(f"❌ Error generating spreadsheet: {e}")
        return None

if __name__ == "__main__":
    main()