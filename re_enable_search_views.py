#!/usr/bin/env python3
"""Re-enable disabled search views and search_view_id references for Odoo 19."""
import re
import os

def re_enable_search_views(filepath):
    """Re-enable search views in an XML file."""
    if not os.path.exists(filepath):
        print(f"  File not found: {filepath}")
        return 0
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    changes = 0
    
    # Pattern 1: Remove "<!-- DISABLED - Search view validation error in Odoo 19\n" before <record
    pattern1 = re.compile(
        r'<!-- DISABLED - Search view validation error in Odoo 19\s*\n(\s*<record id="[^"]*" model="ir\.ui\.view">)',
        re.MULTILINE
    )
    content, n = pattern1.subn(r'\1', content)
    changes += n
    
    # Pattern 2: Remove closing "-->" after </record> for search views
    pattern2 = re.compile(
        r'(</record>)\s*\n\s*-->', 
        re.MULTILINE
    )
    # Only remove the first occurrence per file (the one after search view)
    if '<!-- DISABLED' not in content:  # Already removed opening
        content, n = pattern2.subn(r'\1', content, count=1)
        changes += n
    
    # Pattern 3: Re-enable search_view_id references
    # <!-- <field name="search_view_id" ref="view_xxx"/> DISABLED -->
    pattern3 = re.compile(
        r'<!-- (<field name="search_view_id" ref="[^"]*"/>) DISABLED -->'
    )
    content, n = pattern3.subn(r'\1', content)
    changes += n
    
    # Pattern 4: Handle <!-- 0 DISABLED --> pattern (search_view_id numbered refs)
    pattern4 = re.compile(
        r'<!-- 0 DISABLED -->'
    )
    content, n = pattern4.subn('', content)
    changes += n
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  {os.path.basename(filepath)}: {changes} changes")
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
            total_changes += re_enable_search_views(filepath)
    
    print(f"\nTotal changes: {total_changes}")

if __name__ == '__main__':
    main()
