#!/usr/bin/env python3
"""Disable all search views in Odoo XML files by commenting them out properly."""
import re
import os

def disable_search_view_in_file(filepath):
    """Find and comment out search view records in an XML file."""
    if not os.path.exists(filepath):
        print(f"  File not found: {filepath}")
        return 0
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    changes = 0
    
    # Find search view records and comment them out
    # Pattern: <record id="xxx" model="ir.ui.view"> with <search> inside
    pattern = re.compile(
        r'(\s*)(<record id="[^"]*" model="ir\.ui\.view">.*?<search[^>]*>.*?</search>.*?</record>)',
        re.DOTALL
    )
    
    def replace_with_comment(match):
        indent = match.group(1)
        record = match.group(2)
        if 'DISABLED' in record:
            return match.group(0)  # Already disabled
        return f'{indent}<!-- DISABLED for Odoo 19 compatibility\n{record}\n{indent}-->'
    
    content, n = pattern.subn(replace_with_comment, content)
    changes += n
    
    # Also comment out search_view_id references
    pattern2 = re.compile(
        r'(<field name="search_view_id" ref="[^"]*"/>)'
    )
    
    def comment_search_ref(match):
        ref = match.group(1)
        if '<!--' in ref:
            return match.group(0)
        return f'<!-- {ref} -->'
    
    content, n = pattern2.subn(comment_search_ref, content)
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
            total_changes += disable_search_view_in_file(filepath)
    
    print(f"\nTotal changes: {total_changes}")

if __name__ == '__main__':
    main()
