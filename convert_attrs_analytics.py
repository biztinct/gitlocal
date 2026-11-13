#!/usr/bin/env python3
"""Convert attrs to inline invisible/required for Odoo 19."""
import re
import os

def convert_attrs_in_file(filepath):
    """Convert simple attrs patterns to inline format."""
    if not os.path.exists(filepath):
        return 0
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    count = 0
    
    # Pattern: attrs="{'invisible': [('field', 'op', value)]}"
    simple_invisible = re.compile(
        r'''attrs="\{'invisible': \[\('(\w+)', '([^']+)', (True|False|'[^']*'|\d+)\)\]\}"'''
    )
    
    def replace_simple_invisible(m):
        field, op, value = m.groups()
        if op == '=':
            op = '=='
        if value in ('True', 'False'):
            return f'invisible="{field} {op} {value}"'
        return f"invisible=\"{field} {op} {value}\""
    
    content = simple_invisible.sub(replace_simple_invisible, content)
    
    # Pattern: attrs="{'invisible': [('field', 'op', value)], 'required': [('field2', 'op2', value2)]}"
    combined_pattern = re.compile(
        r'''attrs="\{'invisible': \[\('(\w+)', '([^']+)', '?([^)']*)'?\)\], 'required': \[\('(\w+)', '([^']+)', '?([^)']*)'?\)\]\}"'''
    )
    
    def replace_combined(m):
        f1, op1, v1, f2, op2, v2 = m.groups()
        if op1 == '=': op1 = '=='
        if op1 == '!=': pass
        if op2 == '=': op2 = '=='
        return f'''invisible="{f1} {op1} '{v1}'" required="{f2} {op2} '{v2}'"'''
    
    content = combined_pattern.sub(replace_combined, content)
    
    # Pattern with & (AND)
    and_pattern = re.compile(
        r'''attrs="\{'invisible': \['&amp;', \('(\w+)', '([^']+)', (\d+|True|False)\), \('(\w+)', '([^']+)', (True|False)\)\]\}"'''
    )
    
    def replace_and(m):
        f1, op1, v1, f2, op2, v2 = m.groups()
        if op1 == '=': op1 = '=='
        if op2 == '=': op2 = '=='
        return f'invisible="{f1} {op1} {v1} and {f2} {op2} {v2}"'
    
    content = and_pattern.sub(replace_and, content)
    
    # Pattern with | (OR)
    or_pattern = re.compile(
        r'''attrs="\{'invisible': \['\|', \('(\w+)', '([^']+)', (\d+|True|False)\), \('(\w+)', '([^']+)', (True|False)\)\]\}"'''
    )
    
    def replace_or(m):
        f1, op1, v1, f2, op2, v2 = m.groups()
        if op1 == '=': op1 = '=='
        if op2 == '=': op2 = '=='
        return f'invisible="{f1} {op1} {v1} or {f2} {op2} {v2}"'
    
    content = or_pattern.sub(replace_or, content)
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return content.count('invisible=') - original.count('invisible=')
    return 0

def main():
    base = '/Users/adity/Documents/GitHub/gitlocal/payroll_analytics_approval'
    files = [
        'views/bank_export_views.xml',
        'views/payroll_comparison_views.xml',
        'wizards/payroll_comparison_wizard_views.xml',
        'views/payroll_analytics_dashboard.xml',
        'views/payroll_analytics_approval_views.xml',
    ]
    for f in files:
        path = os.path.join(base, f)
        if os.path.exists(path):
            convert_attrs_in_file(path)
            print(f"Processed: {f}")

if __name__ == '__main__':
    main()
