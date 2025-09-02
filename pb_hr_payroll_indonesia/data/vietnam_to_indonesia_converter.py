#!/usr/bin/env python3
"""
Convert Vietnam payroll spreadsheet JSON to Indonesia with proper field mappings
"""
import json
import uuid

def convert_vietnam_to_indonesia():
    # Load Vietnam JSON
    with open('/Users/adity/Documents/GitHub/gitlocal/pb_hr_payroll_vietnam/data/vietnam_payroll_data.json', 'r') as f:
        vietnam_data = json.load(f)
    
    print("Converting Vietnam spreadsheet to Indonesia...")
    
    # Vietnam to Indonesia field mappings
    field_mappings = {
        # Basic employee info
        'full_name_vn': 'full_name_en',
        'pit_number': 'npwp_number',
        'social_insurance_number': 'bpjs_kesehatan_number',
        'unemployment_insurance_number': 'bpjs_ketenagakerjaan_number',
        
        # Allowances
        'gas_allowance': 'transportation_allowance',
        'responsibility_allowance': 'fixed_allowance_1',
        'position_allowance': 'fixed_allowance_2',
        'lunch_allowance': 'meal_allowance',
        'phone_allowance': 'communication_allowance',
        'other_allowance_1': 'tunjangan_sewa_rumah',
        'other_allowance_2': 'commission',
        'other_allowance_3': 'sign_on_bonus',
        'other_allowance_4': 'tunjangan_duka',
        'other_allowance_5': 'tunjangan_suka',
        'other_allowance_6': 'severance_appreciation',
        'other_allowance_7': 'lain_lain_allowance',
        
        # Vietnam social insurance to Indonesia BPJS
        'social_ins1': 'bpjs_kesehatan_employee',
        'social_ins2': 'bpjs_tk_jht_employee', 
        'social_ins3': 'bpjs_tk_jp_employee',
        'social_ins4': 'bpjs_kesehatan_employer',
        'social_ins5': 'bpjs_tk_jht_employer',
        'social_ins6': 'bpjs_tk_jp_employer',
        'social_ins7': 'bpjs_tk_jkk',
        'social_ins8': 'bpjs_tk_jkm',
        
        # Vietnam tax to Indonesia tax
        'monthly_pit': 'pph21',
        'yearly_pit': 'pph21_yearly',
        
        # Deductions
        'union_fee': 'union_dues',
        'advance_payment': 'loan_deductions',
        'other_deduction_1': 'deduction_1',
        'other_deduction_2': 'deduction_2', 
        'other_deduction_3': 'deduction_3',
        'other_deduction_4': 'koperasi',
        'other_deduction_5': 'pinjaman',
        'other_deduction_6': 'cicilan',
        'other_deduction_7': 'lain_lain_deduction'
    }
    
    def update_formula_fields(content):
        """Update field names in ODOO formulas"""
        if not isinstance(content, str) or not content.startswith('='):
            return content
            
        updated_content = content
        for vn_field, id_field in field_mappings.items():
            updated_content = updated_content.replace(f'"{vn_field}"', f'"{id_field}"')
        
        return updated_content
    
    def update_sheet_names(content):
        """Update sheet names in formulas"""
        if not isinstance(content, str):
            return content
        return content.replace('Vietnam', 'Indonesia').replace('vietnam', 'indonesia')
    
    # Update all sheets
    for sheet in vietnam_data['sheets']:
        # Update sheet names
        sheet['name'] = sheet['name'].replace('Vietnam', 'Indonesia')
        
        # Update all cell contents
        for cell_id, cell_data in sheet['cells'].items():
            if 'content' in cell_data:
                # Update field names in formulas
                cell_data['content'] = update_formula_fields(cell_data['content'])
                # Update sheet references
                cell_data['content'] = update_sheet_names(cell_data['content'])
    
    # Update list configuration to include Indonesia fields
    if 'lists' in vietnam_data:
        indonesia_fields = [
            'employee_id', 'first_name', 'last_name', 'full_name_en', 'email',
            'department', 'designation', 'base_salary', 'transportation_allowance',
            'communication_allowance', 'meal_allowance', 'fixed_allowance_1', 
            'fixed_allowance_2', 'tunjangan_sewa_rumah', 'commission', 'sign_on_bonus',
            'tunjangan_duka', 'tunjangan_suka', 'severance_appreciation', 'lain_lain_allowance',
            'bpjs_kesehatan_employee', 'bpjs_tk_jht_employee', 'bpjs_tk_jp_employee',
            'bpjs_kesehatan_employer', 'bpjs_tk_jht_employer', 'bpjs_tk_jp_employer',
            'bpjs_tk_jkk', 'bpjs_tk_jkm', 'pph21', 'union_dues', 'loan_deductions',
            'deduction_1', 'deduction_2', 'deduction_3', 'koperasi', 'pinjaman',
            'cicilan', 'lain_lain_deduction', 'npwp_number', 'bpjs_kesehatan_number',
            'bpjs_ketenagakerjaan_number', 'total_earnings', 'total_deductions', 'net_pay'
        ]
        
        vietnam_data['lists']['1']['columns'] = [{'name': field} for field in indonesia_fields]
    
    # Update any other Vietnam references
    vietnam_json_str = json.dumps(vietnam_data)
    indonesia_json_str = vietnam_json_str.replace('Vietnam', 'Indonesia').replace('vietnam', 'indonesia')
    indonesia_data = json.loads(indonesia_json_str)
    
    # Save Indonesia JSON
    with open('/Users/adity/Documents/GitHub/gitlocal/pb_hr_payroll_indonesia/data/indonesia_payroll_data.json', 'w') as f:
        json.dump(indonesia_data, f, indent=2)
    
    print("✅ Conversion completed!")
    print("✅ Indonesia spreadsheet now has full Vietnam structure with Indonesia-specific fields")
    print("✅ All ODOO formulas updated with Indonesia field mappings")
    print("✅ Lists configuration updated with Indonesia fields")
    
    return indonesia_data

if __name__ == "__main__":
    convert_vietnam_to_indonesia()