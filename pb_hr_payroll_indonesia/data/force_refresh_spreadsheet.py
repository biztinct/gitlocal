#!/usr/bin/env python3
"""
Force Refresh Indonesia Spreadsheet in Database
============================================

This creates a fresh spreadsheet record that forces the database to 
use the updated indonesia_payroll_data.json with Indonesia fields.
"""
import json
import uuid
from datetime import datetime

def create_forced_refresh_data():
    print("🔄 Creating forced refresh data for Indonesia spreadsheet...")
    
    # Create a unique timestamp-based ID to force refresh
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_external_id = f"indonesia_payroll_spreadsheet_{timestamp}"
    
    # Create XML data that will force a fresh spreadsheet record
    refresh_xml = f'''<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <data noupdate="0">
        
        <!-- FORCE REFRESH: Indonesia Payroll Spreadsheet Template -->
        <record id="{new_external_id}" model="spreadsheet.spreadsheet">
            <field name="name">Indonesia Payroll Staging Data (Refreshed {timestamp})</field>
            <field name="data" type="base64" file="pb_hr_payroll_indonesia/data/indonesia_payroll_data.json"/>
        </record>
        
        <!-- Delete old record to prevent conflicts -->
        <delete model="spreadsheet.spreadsheet" id="payrollstaging_indonesia" />
        
    </data>
</odoo>

<!-- 
INDONESIA PAYROLL FIELDS NOW AVAILABLE:

🇮🇩 INDONESIA-SPECIFIC FIELDS (positions 26-56):
- gross_pay_idn (Gross Pay Indonesia)
- pph21 (Indonesian Income Tax)
- bpjs_kesehatan_employee (BPJS Health - Employee)
- bpjs_tk_jht_employee (BPJS Employment JHT - Employee)
- bpjs_tk_jp_employee (BPJS Pension - Employee)
- npwp_number (Indonesian Tax ID)
- tunjangan_sewa_rumah (Housing Allowance)
- koperasi (Cooperative Deduction)
- pinjaman (Loan Deduction)

🇻🇳 VIETNAM BASE FIELDS PRESERVED (positions 1-25):
- employee_id, base_salary, gas_allowance, phone_allowance, etc.

USAGE EXAMPLES:
=ODOO.LIST.HEADER(1,"bpjs_kesehatan_employee")
=ODOO.LIST.HEADER(1,"pph21")
=ODOO.LIST.HEADER(1,"npwp_number")
=ODOO.LIST.HEADER(1,"tunjangan_sewa_rumah")

=ODOO.LIST(1,1,"bpjs_kesehatan_employee")
=ODOO.LIST(1,2,"pph21")

Total fields available: 56 (25 Vietnam + 31 Indonesia)
-->'''
    
    # Save the refresh XML
    with open('/Users/adity/Documents/GitHub/gitlocal/pb_hr_payroll_indonesia/data/spreadsheet_data_refresh.xml', 'w') as f:
        f.write(refresh_xml)
    
    print(f"✅ Created forced refresh XML: spreadsheet_data_refresh.xml")
    print(f"✅ New spreadsheet ID: {new_external_id}")
    print()
    print("🔧 MANUAL STEPS TO APPLY:")
    print("1. Replace the content of spreadsheet_data.xml with spreadsheet_data_refresh.xml")
    print("2. Update Indonesia module: python -m odoo -c odoo.conf -d database -u pb_hr_payroll_indonesia")
    print("3. Test ODOO.LIST.HEADER(1,\"bpjs_kesehatan_employee\") in spreadsheet")
    print()
    print("🇮🇩 This will give you access to all 56 fields including:")
    print("   • bpjs_kesehatan_employee, pph21, npwp_number")
    print("   • tunjangan_sewa_rumah, koperasi, pinjaman")
    print("   • All original Vietnam fields still working")
    
    return new_external_id

if __name__ == "__main__":
    create_forced_refresh_data()