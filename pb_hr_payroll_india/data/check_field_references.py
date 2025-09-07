#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Check Field References in View
==============================

This script verifies that all field references in the view exist in the models.

Author: Claude Code Assistant  
Date: 2025-09-07
"""

import re

def check_field_references():
    """Check that all view field references exist in models"""
    
    print("🔍 Checking India View Field References...")
    print("=" * 50)
    
    # Read the view file
    try:
        with open('/Users/adity/Documents/GitHub/gitlocal/pb_hr_payroll_india/views/zoho_staging_data_views.xml', 'r') as f:
            view_content = f.read()
    except FileNotFoundError:
        print("❌ View file not found")
        return
    
    # Extract field references from the view (only actual model fields)
    field_pattern = r'<field name="([^"]+)"'
    all_field_matches = re.findall(field_pattern, view_content)
    
    # Filter out XML view attributes that aren't model fields
    xml_attributes = {'name', 'model', 'arch', 'context', 'domain', 'help', 'res_model', 'view_mode'}
    view_fields = set([f for f in all_field_matches if f not in xml_attributes])
    
    print(f"📋 Found {len(view_fields)} field references in views:")
    for field in sorted(view_fields):
        print(f"   • {field}")
    
    # Define fields that exist in base zoho.staging.data model
    base_staging_fields = {
        'first_name', 'last_name', 'email', 'employee_id', 'department', 
        'employee_status', 'location_name', 'designation', 'pan_number', 
        'bank_name', 'pit_number', 'bank_account_number_vnd', 'uan_number', 
        'aadhaar_number', 'zoho_id', 'full_name_en', 'full_name_vn', 
        'insurance_book_number', 'gender', 'employee_type', 'date_of_birth', 
        'mobile', 'date_of_joining', 'number_of_dependents', 'base_salary',
        'gas_allowance', 'phone_allowance', 'meal_allowance', 'resp_allowance',
        'park_allowance', 'taxi_allowance', 'recog_bonus', 'other_income',
        'paidleave_unused', 'other_bonus', 'bonus_stip', 'processing_status',
        'created_employee_id'
    }
    
    # Define fields that exist in India-specific zoho.staging.data extension
    india_staging_fields = {
        'hra', 'special_allowance', 'books_allowance', 'lta', 'pf_employee',
        'esi_employee', 'professional_tax', 'income_tax', 'pf_employer',
        'esi_employer', 'gratuity_provision', 'esi_number', 'pf_number'
    }
    
    # Define fields that exist in base zoho.employee.data model
    base_employee_fields = {
        'first_name', 'last_name', 'email', 'employee_id', 'department', 
        'location_name', 'date_of_joining', 'designation', 'base_salary',
        'net_pay', 'gross_salary', 'total_deductions', 'full_name_en'
    }
    
    # Define fields that exist in India-specific zoho.employee.data extension
    india_employee_fields = {
        'hra', 'special_allowance', 'books_allowance', 'lta', 'medical_allowance',
        'pf_employee', 'esi_employee', 'professional_tax', 'income_tax',
        'pf_employer', 'esi_employer', 'gratuity', 'pan_number', 'aadhaar_number'
    }
    
    # Combine all available fields
    all_staging_fields = base_staging_fields | india_staging_fields
    all_employee_fields = base_employee_fields | india_employee_fields
    all_available_fields = all_staging_fields | all_employee_fields
    
    print(f"\n📊 Field Availability Analysis:")
    print(f"   • Base staging fields: {len(base_staging_fields)}")
    print(f"   • India staging fields: {len(india_staging_fields)}")
    print(f"   • Base employee fields: {len(base_employee_fields)}")
    print(f"   • India employee fields: {len(india_employee_fields)}")
    print(f"   • Total available fields: {len(all_available_fields)}")
    
    # Check for missing fields
    missing_fields = view_fields - all_available_fields
    
    if missing_fields:
        print(f"\n❌ Missing Fields ({len(missing_fields)}):")
        for field in sorted(missing_fields):
            print(f"   • {field}")
        return False
    else:
        print(f"\n✅ All Fields Available!")
        print("   All field references in views exist in the models.")
        return True

def main():
    """Main function"""
    success = check_field_references()
    
    if success:
        print("\n🎉 Field Reference Check: PASSED")
        print("The module should install without field reference errors.")
    else:
        print("\n❌ Field Reference Check: FAILED")
        print("Some field references need to be fixed before installation.")
    
    return success

if __name__ == "__main__":
    main()