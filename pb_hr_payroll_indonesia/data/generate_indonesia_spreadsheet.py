#!/usr/bin/env python3
"""
Indonesia Payroll Spreadsheet Generator
=======================================

This program generates a comprehensive Indonesia payroll spreadsheet with:
- ODOO.LIST formulas for data retrieval from zoho.staging.data
- Proper calculation formulas for Indonesian payroll compliance (BPJS, PPh21)
- Multiple rows for all employee records (25+ demo data)
- Indonesia-specific fields and tax calculations
- Cross-sheet references for lookup data

Based on Vietnam spreadsheet analysis and Indonesian labor law requirements.
"""

import json
import uuid
from datetime import datetime

class IndonesiaSpreadsheetGenerator:
    """Generate Indonesia payroll spreadsheet with proper formulas"""
    
    def __init__(self):
        self.indonesia_fields = self._get_indonesia_fields()
        self.sheet_styles = self._get_sheet_styles()
        
    def _get_indonesia_fields(self):
        """Indonesia-specific payroll fields from zoho.staging.data model"""
        return {
            # Core employee data
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
            
            # BPJS employee contributions
            'bpjs_employee_fields': [
                'bpjs_kesehatan_employee', 'bpjs_tk_jht_employee', 'bpjs_tk_jp_employee',
                'bpjs_total_employee'
            ],
            
            # BPJS employer contributions  
            'bpjs_employer_fields': [
                'bpjs_kesehatan_employer', 'bpjs_tk_jht_employer', 'bpjs_tk_jp_employer',
                'bpjs_tk_jkk_employer', 'bpjs_tk_jkm_employer', 'bpjs_total_employer'
            ],
            
            # PPh21 tax fields
            'tax_fields': [
                'number_of_dependents', 'ptkp_amount', 'taxable_income',
                'taxable_income_after_ptkp', 'monthly_pph21'
            ],
            
            # Indonesia deductions
            'deduction_fields': [
                'union_dues', 'koperasi_deduction', 'pinjaman_deduction',
                'cicilan_deduction', 'other_deductions'
            ],
            
            # Overtime (Indonesia labor law)
            'overtime_fields': [
                'overtime_normal_hours', 'overtime_weekend_hours', 'overtime_holiday_hours',
                'overtime_normal_amount', 'overtime_weekend_amount', 'overtime_holiday_amount'
            ],
            
            # Final calculations
            'calculated_fields': [
                'gross_pay_idr', 'total_deductions', 'net_pay_idr', 'total_cost_to_employer'
            ]
        }
    
    def _get_sheet_styles(self):
        """Spreadsheet styling configuration"""
        return {
            1: {"bold": True, "fillColor": "#E8F4FD", "textColor": "#2C5282"},  # Headers
            2: {"fillColor": "#F7FAFC", "textColor": "#2D3748"},                # Data rows
            3: {"fillColor": "#FED7D7", "textColor": "#C53030"}                 # Error/special
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
            "lists": {
                "1": {
                    "name": "zoho.staging.data",
                    "model": "zoho.staging.data",
                    "domain": [],
                    "fields": ["employee_id", "first_name", "last_name", "full_name_en", "email", "mobile", "department", "designation", "date_of_joining", "location_name", "ktp_number", "npwp_number", "bpjs_kesehatan_number", "bpjs_ketenagakerjaan_number", "bank_account_number_idr", "bank_name", "bank_branch", "bank_code", "base_salary_idr", "tunjangan_sewa_rumah", "transportation_allowance", "meal_allowance", "communication_allowance", "number_of_dependents"]
                }
            },
            "namedRanges": []
        }
        
        return spreadsheet
    
    def _create_allowance_details_sheet(self):
        """Create Indonesia allowance lookup sheet"""
        cells = {}
        
        # Headers
        headers = [
            "Employee ID", "Tunjangan Sewa Rumah", "Transportation Allowance", 
            "Meal Allowance", "Communication Allowance", "Fixed Allowance 1",
            "Fixed Allowance 2", "Commission", "THR Payment", "Other Allowances"
        ]
        
        # Add headers
        for i, header in enumerate(headers):
            cells[f"{chr(65+i)}1"] = {"style": 1, "content": header}
        
        # Add sample data for 25 rows (demo employees)
        for row in range(2, 27):  # Rows 2-26 for 25 employees
            employee_id = f"2{row-1:03d}"  # Indonesia employee IDs start with 2
            cells[f"A{row}"] = {"style": 2, "content": employee_id}
            cells[f"B{row}"] = {"style": 2, "content": "2000000"}  # Tunjangan sewa rumah
            cells[f"C{row}"] = {"style": 2, "content": "500000"}   # Transportation
            cells[f"D{row}"] = {"style": 2, "content": "300000"}   # Meal
            cells[f"E{row}"] = {"style": 2, "content": "200000"}   # Communication
            cells[f"F{row}"] = {"style": 2, "content": "1000000"}  # Fixed allowance 1
            cells[f"G{row}"] = {"style": 2, "content": "500000"}   # Fixed allowance 2
            cells[f"H{row}"] = {"style": 2, "content": "750000"}   # Commission
            cells[f"I{row}"] = {"style": 2, "content": "1200000"}  # THR payment
            cells[f"J{row}"] = {"style": 2, "content": "250000"}   # Other allowances
        
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
        """Create Indonesia earnings/deductions lookup sheet"""
        cells = {}
        
        # Headers
        headers = [
            "Employee ID", "BPJS Kesehatan Employee", "BPJS TK JHT Employee",
            "BPJS TK JP Employee", "BPJS Kesehatan Employer", "BPJS TK JHT Employer",
            "BPJS TK JP Employer", "BPJS TK JKK Employer", "BPJS TK JKM Employer",
            "Union Dues", "Koperasi", "Pinjaman", "Cicilan", "PPh21"
        ]
        
        # Add headers
        for i, header in enumerate(headers):
            cells[f"{chr(65+i)}1"] = {"style": 1, "content": header}
        
        # Add sample data for 25 rows
        for row in range(2, 27):
            employee_id = f"2{row-1:03d}"
            base_salary = 8000000  # Base salary for calculations
            
            cells[f"A{row}"] = {"style": 2, "content": employee_id}
            # BPJS Employee contributions
            cells[f"B{row}"] = {"style": 2, "content": str(min(int(base_salary * 0.01), 80000))}  # 1% max 80k
            cells[f"C{row}"] = {"style": 2, "content": str(int(base_salary * 0.02))}              # 2%
            cells[f"D{row}"] = {"style": 2, "content": str(int(base_salary * 0.01))}              # 1%
            # BPJS Employer contributions
            cells[f"E{row}"] = {"style": 2, "content": str(int(base_salary * 0.04))}              # 4%
            cells[f"F{row}"] = {"style": 2, "content": str(int(base_salary * 0.037))}             # 3.7%
            cells[f"G{row}"] = {"style": 2, "content": str(int(base_salary * 0.02))}              # 2%
            cells[f"H{row}"] = {"style": 2, "content": str(int(base_salary * 0.0024))}            # 0.24%
            cells[f"I{row}"] = {"style": 2, "content": str(int(base_salary * 0.003))}             # 0.30%
            # Deductions
            cells[f"J{row}"] = {"style": 2, "content": "50000"}   # Union dues
            cells[f"K{row}"] = {"style": 2, "content": "100000"}  # Koperasi
            cells[f"L{row}"] = {"style": 2, "content": "200000"}  # Pinjaman
            cells[f"M{row}"] = {"style": 2, "content": "150000"}  # Cicilan
            cells[f"N{row}"] = {"style": 2, "content": "400000"}  # PPh21 estimate
        
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
        """Create Indonesia tax lookup table"""
        cells = {}
        
        # Indonesian PPh21 tax brackets (2024)
        tax_brackets = [
            ["0", "0%", "0"],
            ["60000000", "5%", "0"], 
            ["250000000", "15%", "3000000"],
            ["500000000", "25%", "40500000"],
            ["999999999999", "30%", "115500000"]
        ]
        
        # Headers
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
        """Create Indonesia employee details template with ODOO formulas"""
        cells = {}
        
        # Indonesia employee detail fields
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
        
        # Add headers
        for i, (header, _) in enumerate(detail_fields):
            cells[f"{chr(65+i)}1"] = {"style": 1, "content": header}
        
        # Add ODOO.LIST formulas for 25 rows
        for row in range(2, 27):  # 25 employee records
            position = row - 1
            for i, (_, field) in enumerate(detail_fields):
                col = chr(65 + i)
                if field == "employee_id":
                    # Concatenate "E" prefix for employee display
                    cells[f"{col}{row}"] = {"content": f'=CONCAT("E", ODOO.LIST(1,{position},"{field}"))'}
                else:
                    cells[f"{col}{row}"] = {"content": f'=ODOO.LIST(1,{position},"{field}")'}
        
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
        """Create Indonesia payroll master template with calculation formulas"""
        cells = {}
        
        # Column definitions for Indonesia payroll
        columns = [
            # A-E: Basic employee info
            ("Employee ID", "employee_id", "concat"),
            ("First Name", "first_name", "odoo"),
            ("Last Name", "last_name", "odoo"),
            ("Department", "department", "odoo"),
            ("Designation", "designation", "odoo"),
            
            # F-J: Salary components  
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
        
        # Add headers
        for i, (header, _, _) in enumerate(columns):
            col = self._num_to_col(i + 1)
            cells[f"{col}1"] = {"style": 1, "content": header}
        
        # Add formulas for 25 rows
        for row in range(2, 27):
            position = row - 1
            for i, (_, field, formula_type) in enumerate(columns):
                col = self._num_to_col(i + 1)
                cells[f"{col}{row}"] = {"content": self._generate_formula(formula_type, field, row, col, position)}
        
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
            # Overtime normal: (Base Salary / 173) * Hours * 1.5
            return f'=IF(P{row}=0,0,(F{row}/173*P{row}*1.5))'
        
        elif formula_type == "calc_overtime_weekend":
            # Overtime weekend: (Base Salary / 173) * Hours * 2.0
            return f'=IF(Q{row}=0,0,(F{row}/173*Q{row}*2.0))'
        
        elif formula_type == "calc_overtime_holiday":
            # Overtime holiday: (Base Salary / 173) * Hours * 3.0
            return f'=IF(R{row}=0,0,(F{row}/173*R{row}*3.0))'
        
        elif formula_type == "sum_overtime":
            # Total overtime S:U
            return f'=SUM(S{row}:U{row})'
        
        elif formula_type == "calc_gross_pay":
            # Gross Pay = Base Salary + Total Allowances + Total Overtime
            return f'=F{row}+O{row}+V{row}'
        
        elif formula_type == "calc_bpjs_base":
            # BPJS base salary (for calculations)
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
            # PTKP: 54M + 4.5M per dependent
            return f'=54000000+(Y{row}*4500000)'
        
        elif formula_type == "calc_taxable_income":
            # Taxable Income = Gross Pay - BPJS Employee
            return f'=W{row}-AC{row}'
        
        elif formula_type == "calc_taxable_after_ptkp":
            # Taxable after PTKP deduction
            return f'=MAX(AE{row}-AD{row},0)'
        
        elif formula_type == "calc_pph21":
            # PPh21 using progressive tax rates
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
        
        print(f"✅ Indonesia payroll spreadsheet generated successfully!")
        print(f"📁 File saved: {output_file}")
        print(f"📊 Contains {len(spreadsheet['sheets'])} sheets:")
        for sheet in spreadsheet['sheets']:
            print(f"   • {sheet['name']} ({sheet['colNumber']} cols × {sheet['rowNumber']} rows)")


if __name__ == "__main__":
    # Generate Indonesia payroll spreadsheet
    generator = IndonesiaSpreadsheetGenerator()
    output_file = "/Users/adity/Documents/GitHub/gitlocal/pb_hr_payroll_indonesia/data/indonesia_payroll_data.json"
    generator.save_to_file(output_file)
    
    print("\n🇮🇩 Indonesia Payroll Spreadsheet Features:")
    print("• ODOO.LIST formulas for data retrieval from zoho.staging.data")
    print("• Proper calculation formulas for Indonesian payroll compliance")
    print("• BPJS Kesehatan (Health Insurance) calculations (Employee 1%, Employer 4%)")
    print("• BPJS Ketenagakerjaan (Employment Insurance) - JHT, JP, JKK, JKM")
    print("• PPh21 progressive tax calculation with PTKP deductions")
    print("• Tunjangan Sewa Rumah (Housing Allowance) per Indonesian law")
    print("• Overtime calculations following Indonesian labor law (1.5x, 2x, 3x rates)")
    print("• Cross-sheet VLOOKUP formulas for allowance and deduction lookups")
    print("• Multiple employee rows (25 records) with proper formula generation")
    print("• Indonesian currency (IDR) formatting and field naming")
    print("• Complete employer cost calculations including BPJS contributions")