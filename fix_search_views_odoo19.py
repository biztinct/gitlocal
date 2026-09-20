#!/usr/bin/env python3
"""Fix search views for Odoo 19 compatibility.

Odoo 19 search views require:
1. <group> with name attribute instead of expand + string
2. Format: <group name="group_by"> instead of <group expand="0" string="Group By">
"""
import re
import os

def fix_search_views_in_file(filepath):
    """Fix search view group syntax for Odoo 19."""
    if not os.path.exists(filepath):
        print(f"  File not found: {filepath}")
        return 0
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    changes = 0
    
    # Pattern: Convert <group expand="0" string="Group By"> to <group name="group_by">
    pattern = re.compile(
        r'<group\s+expand="0"\s+string="Group By">',
        re.IGNORECASE
    )
    content, n = pattern.subn('<group name="group_by">', content)
    changes += n
    
    # Also handle the reverse order: string then expand
    pattern2 = re.compile(
        r'<group\s+string="Group By"\s+expand="0">',
        re.IGNORECASE
    )
    content, n = pattern2.subn('<group name="group_by">', content)
    changes += n
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  {os.path.basename(filepath)}: {changes} group tag(s) fixed")
        return changes
    else:
        print(f"  {os.path.basename(filepath)}: No changes needed")
        return 0

def main():
    base = '/Users/adity/Documents/GitHub/gitlocal'
    
    modules_and_files = {
        'pb_hr_payroll_formula/views': [
            'formula_config_views.xml',
            'formula_rule_views.xml',
            'payroll_cycle_carryover_views.xml',
            'payroll_cycle_component_mapping_views.xml',
            'payroll_import_views.xml',
            'payroll_proration_views.xml',
            'payroll_retro_views.xml',
            'payslip_config_views.xml',
            'payslip_import_mapping_views.xml',
            'sample_data_views.xml',
        ],
        'pb_hr_payroll_vietnam/views': [
            'vietnam_employee_dependent_views.xml',
            'vietnam_insurance_adjustment_views.xml',
            'vietnam_insurance_policy_views.xml',
            'vietnam_tax_table_views.xml',
        ],
        'payroll_analytics_approval/views': [
            'payroll_approval_views.xml',
            'payroll_comparison_views.xml',
        ],
    }
    
    total_changes = 0
    for module_path, files in modules_and_files.items():
        print(f"\n{module_path}:")
        for filename in files:
            filepath = os.path.join(base, module_path, filename)
            total_changes += fix_search_views_in_file(filepath)
    
    print(f"\nTotal group tags fixed: {total_changes}")
    
    # Validate XML
    import subprocess
    print("\nValidating XML files...")
    for module_path, files in modules_and_files.items():
        for filename in files:
            filepath = os.path.join(base, module_path, filename)
            if os.path.exists(filepath):
                result = subprocess.run(['xmllint', '--noout', filepath], 
                                       capture_output=True, text=True)
                if result.returncode != 0:
                    print(f"  ERROR in {filename}: {result.stderr[:200]}")
                else:
                    pass  # Valid

if __name__ == '__main__':
    main()
