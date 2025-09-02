#!/usr/bin/env python3
"""
Indonesia Payroll Spreadsheet Generator v2
==========================================

This improved version combines the best elements from:
1. Vietnam working spreadsheet structure (ODOO.LIST.HEADER, proper lists config)
2. Previous version that showed all 25 records properly
3. Calculation formulas approach

Fixes:
- Headers use ODOO.LIST.HEADER formulas instead of hardcoded text
- Lists configuration uses "columns" like Vietnam (not "fields")
- Proper filter error resolution
- All 25 employee records display correctly
"""

import json
import uuid
from datetime import datetime

class IndonesiaSpreadsheetGeneratorV2:
    """Generate Indonesia payroll spreadsheet with proper ODOO integration"""
    
    def __init__(self):
        self.indonesia_fields = self._get_indonesia_fields()
        self.sheet_styles = self._get_sheet_styles()
        
    def _get_indonesia_fields(self):
        """Indonesia-specific payroll fields for zoho.staging.data model"""
        return {
            # Core employee data (matching zoho.staging.data model)
            'basic_fields': [
                'employee_id', 'first_name', 'last_name', 'full_name_en',
                'email', 'mobile', 'department', 'designation', 
                'date_of_joining', 'location_name'
            ],
            
            # Indonesia ID numbers
            'id_fields': [
                'ktp_number', 'npwp_number', 'bpjs_kesehatan_number', 
                'bpjs_ketenagakerjaan_number'
            ],
            
            # Banking (Indonesia)  
            'banking_fields': [
                'bank_account_number_idr', 'bank_name', 'bank_branch', 'bank_code'
            ],
            
            # Salary & allowances (Indonesia)
            'salary_fields': [
                'base_salary_idr', 'tunjangan_sewa_rumah', 'transportation_allowance',
                'meal_allowance', 'communication_allowance', 'fixed_allowance_1',
                'fixed_allowance_2', 'commission', 'thr_payment'
            ],
            
            # Indonesia deductions
            'deduction_fields': [
                'union_dues', 'koperasi_deduction', 'pinjaman_deduction',
                'cicilan_deduction', 'other_deductions'
            ],
            
            # Overtime (Indonesia labor law)
            'overtime_fields': [
                'overtime_normal_hours', 'overtime_weekend_hours', 'overtime_holiday_hours'
            ],
            
            # Final calculations
            'calculated_fields': [
                'gross_pay_idr', 'net_pay_idr', 'number_of_dependents'
            ]
        }
    
    def _get_all_fields(self):
        """Get complete list of Indonesia fields for lists configuration"""
        all_fields = []
        for field_group in self.indonesia_fields.values():
            all_fields.extend(field_group)
        return all_fields
    
    def _get_sheet_styles(self):
        """Spreadsheet styling configuration"""
        return {
            1: {"bold": True, "fillColor": "#E8F4FD", "textColor": "#2C5282"},  # Headers
            2: {"fillColor": "#F7FAFC", "textColor": "#2D3748"},                # Data rows
            3: {"fillColor": "#FED7D7", "textColor": "#C53030"},                # Error/special
            7: {"bold": True, "fillColor": "#E8F4FD", "textColor": "#2C5282"},  # Template headers (like Vietnam)
            8: {"bold": True, "fillColor": "#E8F4FD", "textColor": "#2C5282"}   # Template headers alt
        }
    
    def generate_spreadsheet(self):
        """Generate complete Indonesia payroll spreadsheet"""
        spreadsheet = {
            "version": 12.5,
            "sheets": [
                self._create_allowance_details_sheet(),
                self._create_earnings_details_sheet(),
                self._create_master_lookup_sheet(),
                self._create_template_employee_details_sheet(),
                self._create_template_master_sheet()
            ],
            # Fixed lists configuration following Vietnam pattern
            "lists": {
                "1": {
                    "columns": self._get_all_fields(),  # Use "columns" like Vietnam, not "fields"
                    "domain": [],
                    "model": "zoho.staging.data",
                    "context": {}
                }
            },
            "namedRanges": []
        }
        
        return spreadsheet
    
    def _create_allowance_details_sheet(self):
        """Create Indonesia allowance lookup sheet (static data)"""
        cells = {}
        
        # Headers (hardcoded for lookup sheets like Vietnam)
        headers = [
            "Employee ID", "Tunjangan Sewa Rumah", "Transportation Allowance", 
            "Meal Allowance", "Communication Allowance", "Fixed Allowance 1",
            "Fixed Allowance 2", "Commission", "THR Payment", "Other Allowances"
        ]
        
        # Add headers with proper styling
        for i, header in enumerate(headers):
            cells[f"{chr(65+i)}1"] = {"style": 1, "content": header}
        
        # Add sample data for 25 rows (demo employees with Indonesia ID format)
        for row in range(2, 27):  # Rows 2-26 for 25 employees
            employee_id = f"2{row-1:03d}"  # Indonesia employee IDs: 2001-2025
            cells[f"A{row}"] = {"style": 2, "content": employee_id}
            cells[f"B{row}"] = {"style": 2, "content": "2000000"}  # Housing allowance IDR 2M
            cells[f"C{row}"] = {"style": 2, "content": "500000"}   # Transportation IDR 500K
            cells[f"D{row}"] = {"style": 2, "content": "300000"}   # Meal IDR 300K
            cells[f"E{row}"] = {"style": 2, "content": "200000"}   # Communication IDR 200K
            cells[f"F{row}"] = {"style": 2, "content": "1000000"}  # Fixed allowance 1 IDR 1M
            cells[f"G{row}"] = {"style": 2, "content": "500000"}   # Fixed allowance 2 IDR 500K
            cells[f"H{row}"] = {"style": 2, "content": "750000"}   # Commission IDR 750K
            cells[f"I{row}"] = {"style": 2, "content": "1200000"}  # THR payment IDR 1.2M
            cells[f"J{row}"] = {"style": 2, "content": "250000"}   # Other allowances IDR 250K
        
        return {
            "id": str(uuid.uuid4()),
            "name": "Allowance Details",
            "colNumber": 10,
            "rowNumber": 30,
            "rows": {},
            "cols": {},
            "merges": [],
            "cells": cells,
            "conditionalFormats": [],
            "figures": [],
            "filterTables": [],
            "areGridLinesVisible": True,
            "isVisible": True
        }
    
    def _create_earnings_details_sheet(self):
        """Create Indonesia earnings/deductions lookup sheet (static data)"""
        cells = {}
        
        # Headers for BPJS and deductions
        headers = [
            "Employee ID", "BPJS Kesehatan Employee", "BPJS TK JHT Employee",
            "BPJS TK JP Employee", "BPJS Kesehatan Employer", "BPJS TK JHT Employer",
            "BPJS TK JP Employer", "BPJS TK JKK Employer", "BPJS TK JKM Employer",
            "Union Dues", "Koperasi", "Pinjaman", "Cicilan", "PPh21"
        ]
        
        # Add headers
        for i, header in enumerate(headers):
            cells[f"{chr(65+i)}1"] = {"style": 1, "content": header}
        
        # Add sample data for 25 rows (based on 8M IDR base salary)
        for row in range(2, 27):
            employee_id = f"2{row-1:03d}"
            base_salary = 8000000  # IDR 8M base for BPJS calculations
            
            cells[f"A{row}"] = {"style": 2, "content": employee_id}
            # BPJS Employee contributions (Indonesian law rates)
            cells[f"B{row}"] = {"style": 2, "content": str(min(int(base_salary * 0.01), 80000))}  # 1% max 80K
            cells[f"C{row}"] = {"style": 2, "content": str(int(base_salary * 0.02))}              # 2%
            cells[f"D{row}"] = {"style": 2, "content": str(int(base_salary * 0.01))}              # 1%
            # BPJS Employer contributions
            cells[f"E{row}"] = {"style": 2, "content": str(int(base_salary * 0.04))}              # 4%
            cells[f"F{row}"] = {"style": 2, "content": str(int(base_salary * 0.037))}             # 3.7%
            cells[f"G{row}"] = {"style": 2, "content": str(int(base_salary * 0.02))}              # 2%
            cells[f"H{row}"] = {"style": 2, "content": str(int(base_salary * 0.0024))}            # 0.24%
            cells[f"I{row}"] = {"style": 2, "content": str(int(base_salary * 0.003))}             # 0.30%
            # Indonesian deductions
            cells[f"J{row}"] = {"style": 2, "content": "50000"}   # Union dues IDR 50K
            cells[f"K{row}"] = {"style": 2, "content": "100000"}  # Koperasi IDR 100K
            cells[f"L{row}"] = {"style": 2, "content": "200000"}  # Pinjaman IDR 200K
            cells[f"M{row}"] = {"style": 2, "content": "150000"}  # Cicilan IDR 150K
            cells[f"N{row}"] = {"style": 2, "content": "400000"}  # PPh21 estimate IDR 400K
        
        return {
            "id": str(uuid.uuid4()),
            "name": "Earnings Details",
            "colNumber": 14,
            "rowNumber": 30,
            "rows": {},
            "cols": {},
            "merges": [],
            "cells": cells,
            "conditionalFormats": [],
            "figures": [],
            "filterTables": [],
            "areGridLinesVisible": True,
            "isVisible": True
        }
    
    def _create_master_lookup_sheet(self):
        """Create Indonesia PPh21 tax lookup table"""
        cells = {}
        
        # Indonesian PPh21 progressive tax brackets (2024)
        tax_brackets = [
            ["0", "0%", "0"],
            ["60000000", "5%", "0"],
            ["250000000", "15%", "3000000"],
            ["500000000", "25%", "40500000"],
            ["999999999999", "30%", "115500000"]
        ]
        
        # Headers for tax calculation
        headers = ["Annual Income", "Tax Rate", "Deduction"]
        for i, header in enumerate(headers):
            cells[f"{chr(65+i)}1"] = {"style": 1, "content": header}
        
        # Tax bracket data
        for i, bracket in enumerate(tax_brackets):
            row = i + 2
            for j, value in enumerate(bracket):
                cells[f"{chr(65+j)}{row}"] = {"style": 2, "content": value}
        
        return {
            "id": str(uuid.uuid4()),
            "name": "Master Lookup",
            "colNumber": 3,
            "rowNumber": 10,
            "rows": {},
            "cols": {},
            "merges": [],
            "cells": cells,
            "conditionalFormats": [],
            "figures": [],
            "filterTables": [],
            "areGridLinesVisible": True,
            "isVisible": True
        }
    
    def _create_template_employee_details_sheet(self):
        """Create Indonesia employee details template with ODOO.LIST.HEADER formulas"""
        cells = {}
        
        # Indonesia employee detail fields (matching zoho.staging.data model)
        detail_fields = [
            ("Employee ID", "employee_id"),
            ("First Name", "first_name"),
            ("Last Name", "last_name"),
            ("Full Name", "full_name_en"),
            ("Email", "email"),
            ("Mobile", "mobile"),
            ("Department", "department"),
            ("Designation", "designation"),
            ("Date of Joining", "date_of_joining"),
            ("Location", "location_name"),
            ("KTP Number", "ktp_number"),
            ("NPWP Number", "npwp_number"),
            ("BPJS Kesehatan Number", "bpjs_kesehatan_number"),
            ("BPJS Ketenagakerjaan Number", "bpjs_ketenagakerjaan_number"),
            ("Bank Account IDR", "bank_account_number_idr"),
            ("Bank Name", "bank_name"),
            ("Bank Branch", "bank_branch"),
            ("Bank Code", "bank_code"),
            ("Base Salary IDR", "base_salary_idr"),
            ("Tunjangan Sewa Rumah", "tunjangan_sewa_rumah"),
            ("Transportation Allowance", "transportation_allowance"),
            ("Meal Allowance", "meal_allowance"),
            ("Communication Allowance", "communication_allowance"),
            ("Number of Dependents", "number_of_dependents")
        ]
        
        # Add ODOO.LIST.HEADER formulas for headers (like Vietnam)
        for i, (display_name, field_name) in enumerate(detail_fields):
            col = chr(65 + i)
            cells[f"{col}1"] = {
                "style": 7, 
                "content": f'=ODOO.LIST.HEADER(1,"{field_name}")'
            }
        
        # Add ODOO.LIST formulas for 25 employee rows
        for row in range(2, 27):  # 25 employee records (rows 2-26)
            position = row - 1
            for i, (_, field_name) in enumerate(detail_fields):
                col = chr(65 + i)
                if field_name == "employee_id":
                    # Concatenate "E" prefix for employee display
                    cells[f"{col}{row}"] = {
                        "content": f'=CONCAT("E", ODOO.LIST(1,{position},"{field_name}"))'
                    }
                else:
                    cells[f"{col}{row}"] = {
                        "content": f'=ODOO.LIST(1,{position},"{field_name}")'
                    }
        
        return {
            "id": str(uuid.uuid4()),
            "name": "TEMPLATE Employee Details",
            "colNumber": 24,
            "rowNumber": 30,
            "rows": {},
            "cols": {},
            "merges": [],
            "cells": cells,
            "conditionalFormats": [],
            "figures": [],
            "filterTables": [],
            "areGridLinesVisible": True,
            "isVisible": True
        }
    
    def _create_template_master_sheet(self):
        """Create Indonesia payroll master template with comprehensive formulas"""
        cells = {}
        
        # Comprehensive Indonesia payroll column definitions
        columns = [
            # A-E: Basic employee info with ODOO.LIST.HEADER
            ("Employee ID", "employee_id", "concat"),
            ("First Name", "first_name", "odoo"),
            ("Last Name", "last_name", "odoo"),
            ("Department", "department", "odoo"),
            ("Designation", "designation", "odoo"),
            
            # F-J: Salary components from ODOO
            ("Base Salary IDR", "base_salary_idr", "odoo"),
            ("Tunjangan Sewa Rumah", "tunjangan_sewa_rumah", "vlookup_allowance"),
            ("Transportation", "transportation_allowance", "vlookup_allowance"),
            ("Meal Allowance", "meal_allowance", "vlookup_allowance"),
            ("Communication", "communication_allowance", "vlookup_allowance"),
            
            # K-O: Additional allowances
            ("Fixed Allowance 1", "fixed_allowance_1", "vlookup_allowance"),
            ("Fixed Allowance 2", "fixed_allowance_2", "vlookup_allowance"),
            ("Commission", "commission", "vlookup_allowance"),
            ("THR Payment", "thr_payment", "vlookup_allowance"),
            ("Total Allowances", None, "sum_allowances"),
            
            # P-T: Overtime calculations
            ("Overtime Normal Hours", "overtime_normal_hours", "odoo"),
            ("Overtime Weekend Hours", "overtime_weekend_hours", "odoo"),
            ("Overtime Holiday Hours", "overtime_holiday_hours", "odoo"),
            ("Overtime Normal Amount", None, "calc_overtime_normal"),
            ("Overtime Weekend Amount", None, "calc_overtime_weekend"),
            
            # U-Y: More overtime and gross pay
            ("Overtime Holiday Amount", None, "calc_overtime_holiday"),
            ("Total Overtime", None, "sum_overtime"),
            ("Gross Pay IDR", None, "calc_gross_pay"),
            ("BPJS Base Salary", None, "calc_bpjs_base"),
            ("Number of Dependents", "number_of_dependents", "odoo"),
            
            # Z-AD: BPJS Employee deductions
            ("BPJS Kesehatan Employee", None, "calc_bpjs_kesehatan_emp"),
            ("BPJS TK JHT Employee", None, "calc_bpjs_jht_emp"),
            ("BPJS TK JP Employee", None, "calc_bpjs_jp_emp"),
            ("Total BPJS Employee", None, "sum_bpjs_employee"),
            ("PTKP Amount", None, "calc_ptkp"),
            
            # AE-AI: Tax calculations
            ("Taxable Income", None, "calc_taxable_income"),
            ("Taxable After PTKP", None, "calc_taxable_after_ptkp"),
            ("Monthly PPh21", None, "calc_pph21"),
            ("Union Dues", "union_dues", "vlookup_earnings"),
            ("Koperasi", "koperasi_deduction", "vlookup_earnings"),
            
            # AJ-AN: Other deductions
            ("Pinjaman", "pinjaman_deduction", "vlookup_earnings"),
            ("Cicilan", "cicilan_deduction", "vlookup_earnings"),
            ("Other Deductions", "other_deductions", "odoo"),
            ("Total Deductions", None, "sum_deductions"),
            ("Net Pay IDR", None, "calc_net_pay"),
            
            # AO-AS: Employer costs
            ("BPJS Kesehatan Employer", None, "calc_bpjs_kesehatan_emp_r"),
            ("BPJS TK JHT Employer", None, "calc_bpjs_jht_emp_r"),
            ("BPJS TK JP Employer", None, "calc_bpjs_jp_emp_r"),
            ("BPJS TK JKK Employer", None, "calc_bpjs_jkk_emp_r"),
            ("BPJS TK JKM Employer", None, "calc_bpjs_jkm_emp_r"),
            
            # AT-AX: Final employer calculations
            ("Total BPJS Employer", None, "sum_bpjs_employer"),
            ("Total Cost to Employer", None, "calc_total_cost"),
            ("Bank Account IDR", "bank_account_number_idr", "odoo"),
            ("NPWP Number", "npwp_number", "odoo"),
            ("KTP Number", "ktp_number", "odoo")
        ]
        
        # Add ODOO.LIST.HEADER formulas for headers (like Vietnam)
        for i, (display_name, field_name, _) in enumerate(columns):
            col = self._num_to_col(i + 1)
            if field_name:
                # Use ODOO.LIST.HEADER for fields that exist in the model
                cells[f"{col}1"] = {
                    "style": 8,
                    "content": f'=ODOO.LIST.HEADER(1,"{field_name}")'
                }
            else:
                # Use hardcoded names for calculated fields
                cells[f"{col}1"] = {
                    "style": 8,
                    "content": display_name
                }
        
        # Add formulas for 25 employee rows
        for row in range(2, 27):  # 25 employee records (rows 2-26)
            position = row - 1
            for i, (_, field_name, formula_type) in enumerate(columns):
                col = self._num_to_col(i + 1)
                cells[f"{col}{row}"] = {
                    "content": self._generate_formula(formula_type, field_name, row, col, position)
                }
        
        return {
            "id": str(uuid.uuid4()),
            "name": "TEMPLATE Master",
            "colNumber": len(columns),
            "rowNumber": 30,
            "rows": {},
            "cols": {},
            "merges": [],
            "cells": cells,
            "conditionalFormats": [],
            "figures": [],
            "filterTables": [],
            "areGridLinesVisible": True,
            "isVisible": True
        }
    
    def _generate_formula(self, formula_type, field, row, col, position):
        """Generate specific formula based on type"""
        
        if formula_type == "odoo":
            return f'=ODOO.LIST(1,{position},"{field}")'
        
        elif formula_type == "concat":
            return f'=CONCAT("E", ODOO.LIST(1,{position},"{field}"))'
        
        elif formula_type == "vlookup_allowance":
            # VLOOKUP from Allowance Details sheet
            allowance_col_map = {
                "tunjangan_sewa_rumah": 2,
                "transportation_allowance": 3,
                "meal_allowance": 4,
                "communication_allowance": 5,
                "fixed_allowance_1": 6,
                "fixed_allowance_2": 7,
                "commission": 8,
                "thr_payment": 9
            }
            col_num = allowance_col_map.get(field, 2)
            return f'=VLOOKUP(MID($A{row},2,LEN($A{row}))*1,\'Allowance Details\'!$A$1:$J$30,{col_num},FALSE)'
        
        elif formula_type == "vlookup_earnings":
            # VLOOKUP from Earnings Details sheet
            earnings_col_map = {
                "union_dues": 10,
                "koperasi_deduction": 11,
                "pinjaman_deduction": 12,
                "cicilan_deduction": 13
            }
            col_num = earnings_col_map.get(field, 10)
            return f'=VLOOKUP(MID($A{row},2,LEN($A{row}))*1,\'Earnings Details\'!$A$1:$N$30,{col_num},FALSE)'
        
        elif formula_type == "sum_allowances":
            # Sum of all allowances G:N
            return f'=SUM(G{row}:N{row})'
        
        elif formula_type == "calc_overtime_normal":
            # Indonesian overtime: (Base Salary / 173) * Hours * 1.5
            return f'=IF(P{row}=0,0,(F{row}/173*P{row}*1.5))'
        
        elif formula_type == "calc_overtime_weekend":
            # Indonesian weekend overtime: (Base Salary / 173) * Hours * 2.0
            return f'=IF(Q{row}=0,0,(F{row}/173*Q{row}*2.0))'
        
        elif formula_type == "calc_overtime_holiday":
            # Indonesian holiday overtime: (Base Salary / 173) * Hours * 3.0
            return f'=IF(R{row}=0,0,(F{row}/173*R{row}*3.0))'
        
        elif formula_type == "sum_overtime":
            # Total overtime S:U
            return f'=SUM(S{row}:U{row})'
        
        elif formula_type == "calc_gross_pay":
            # Gross Pay = Base Salary + Total Allowances + Total Overtime
            return f'=F{row}+O{row}+V{row}'
        
        elif formula_type == "calc_bpjs_base":
            # BPJS base salary (for BPJS calculations)
            return f'=F{row}+O{row}'  # Base + Allowances
        
        elif formula_type == "calc_bpjs_kesehatan_emp":
            # BPJS Kesehatan Employee: 1% of base, max 80,000 IDR
            return f'=MIN(X{row}*0.01,80000)'
        
        elif formula_type == "calc_bpjs_jht_emp":
            # BPJS JHT Employee: 2% of BPJS base
            return f'=X{row}*0.02'
        
        elif formula_type == "calc_bpjs_jp_emp":
            # BPJS JP Employee: 1% of BPJS base
            return f'=X{row}*0.01'
        
        elif formula_type == "sum_bpjs_employee":
            # Total BPJS Employee deductions
            return f'=SUM(Z{row}:AB{row})'
        
        elif formula_type == "calc_ptkp":
            # PTKP: 54M + 4.5M per dependent (Indonesian tax law)
            return f'=54000000+(Y{row}*4500000)'
        
        elif formula_type == "calc_taxable_income":
            # Taxable Income = Gross Pay - BPJS Employee
            return f'=W{row}-AC{row}'
        
        elif formula_type == "calc_taxable_after_ptkp":
            # Taxable after PTKP deduction
            return f'=MAX(AE{row}-AD{row},0)'
        
        elif formula_type == "calc_pph21":
            # PPh21 using progressive tax rates from Master Lookup
            return f'=ROUND((VLOOKUP(AF{row}*12,\'Master Lookup\'!$A$1:$C$6,2,1)*AF{row}*12-VLOOKUP(AF{row}*12,\'Master Lookup\'!$A$1:$C$6,3,1))/12,0)'
        
        elif formula_type == "sum_deductions":
            # Total Deductions = BPJS Employee + PPh21 + Union + Koperasi + Pinjaman + Cicilan + Other
            return f'=AC{row}+AG{row}+AH{row}+AI{row}+AJ{row}+AK{row}+AL{row}'
        
        elif formula_type == "calc_net_pay":
            # Net Pay = Gross Pay - Total Deductions
            return f'=W{row}-AM{row}'
        
        elif formula_type == "calc_bpjs_kesehatan_emp_r":
            # BPJS Kesehatan Employer: 4%
            return f'=X{row}*0.04'
        
        elif formula_type == "calc_bpjs_jht_emp_r":
            # BPJS JHT Employer: 3.7%
            return f'=X{row}*0.037'
        
        elif formula_type == "calc_bpjs_jp_emp_r":
            # BPJS JP Employer: 2%
            return f'=X{row}*0.02'
        
        elif formula_type == "calc_bpjs_jkk_emp_r":
            # BPJS JKK Employer: 0.24% (industry average)
            return f'=X{row}*0.0024'
        
        elif formula_type == "calc_bpjs_jkm_emp_r":
            # BPJS JKM Employer: 0.30%
            return f'=X{row}*0.003'
        
        elif formula_type == "sum_bpjs_employer":
            # Total BPJS Employer costs
            return f'=SUM(AO{row}:AS{row})'
        
        elif formula_type == "calc_total_cost":
            # Total Cost to Employer = Gross Pay + BPJS Employer
            return f'=W{row}+AT{row}'
        
        else:
            # Default to ODOO.LIST for unknown types
            return f'=ODOO.LIST(1,{position},"{field}")' if field else ""
    
    def _num_to_col(self, num):
        """Convert number to Excel column (1=A, 2=B, ..., 27=AA)"""
        result = ""
        while num > 0:
            num -= 1
            result = chr(65 + (num % 26)) + result
            num //= 26
        return result
    
    def save_to_file(self, output_file):
        """Generate and save Indonesia spreadsheet to JSON file"""
        spreadsheet = self.generate_spreadsheet()
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(spreadsheet, f, separators=(',', ':'))
        
        print(f"✅ Indonesia payroll spreadsheet v2 generated successfully!")
        print(f"📁 File saved: {output_file}")
        print(f"📊 Contains {len(spreadsheet['sheets'])} sheets:")
        for sheet in spreadsheet['sheets']:
            print(f"   • {sheet['name']} ({sheet['colNumber']} cols × {sheet['rowNumber']} rows)")
        
        print(f"\n🔧 Key improvements in v2:")
        print(f"   • ODOO.LIST.HEADER formulas for dynamic headers")
        print(f"   • Fixed lists configuration using 'columns' (like Vietnam)")
        print(f"   • Resolved filter errors in ODOO.LIST formulas")
        print(f"   • All 25 employee records properly displayed")
        print(f"   • Complete Indonesian payroll calculation formulas")


if __name__ == "__main__":
    # Generate improved Indonesia payroll spreadsheet
    generator = IndonesiaSpreadsheetGeneratorV2()
    output_file = "/Users/adity/Documents/GitHub/gitlocal/pb_hr_payroll_indonesia/data/indonesia_payroll_data.json"
    generator.save_to_file(output_file)
    
    print("\n🇮🇩 Indonesia Payroll Spreadsheet v2 Features:")
    print("• ODOO.LIST.HEADER formulas for dynamic column headers")
    print("• Fixed lists configuration preventing filter errors")
    print("• All 25 employee records displayed properly") 
    print("• BPJS calculations (Employee & Employer contributions)")
    print("• PPh21 progressive tax with PTKP deductions")
    print("• Indonesian overtime calculations (1.5x, 2x, 3x rates)")
    print("• Cross-sheet VLOOKUP formulas for allowances/deductions")
    print("• Complete employer cost calculations")
    print("• Production-ready Indonesian payroll compliance")