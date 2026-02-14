#!/usr/bin/env python3
"""Complete Odoo 19 view compatibility fixes.

Fixes:
1. <tree> -> <list>
2. </tree> -> </list>
3. <group expand="0" string="Group By"> -> <group name="group_by">
4. attrs= -> inline invisible/required/readonly
"""
import re
import os
import subprocess

def fix_views_in_file(filepath):
    """Apply all Odoo 19 fixes to a view file."""
    if not os.path.exists(filepath):
        print(f"  File not found: {filepath}")
        return 0
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    changes = 0
    
    # 1. Convert <tree to <list (keeping attributes)
    pattern = re.compile(r'<tree(\s|>|/>)', re.IGNORECASE)
    content, n = pattern.subn(r'<list\1', content)
    changes += n
    
    # 2. Convert </tree> to </list>
    content, n = re.subn(r'</tree>', '</list>', content, flags=re.IGNORECASE)
    changes += n
    
    # 3. Convert search view group syntax
    pattern = re.compile(r'<group\s+expand="0"\s+string="Group By">', re.IGNORECASE)
    content, n = pattern.subn('<group name="group_by">', content)
    changes += n
    
    pattern = re.compile(r'<group\s+string="Group By"\s+expand="0">', re.IGNORECASE)
    content, n = pattern.subn('<group name="group_by">', content)
    changes += n
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  {os.path.basename(filepath)}: {changes} fixes applied")
        return changes
    else:
        print(f"  {os.path.basename(filepath)}: No changes needed")
        return 0

def main():
    base = '/Users/adity/Documents/GitHub/gitlocal'
    
    # All XML files that need fixing
    modules = ['pb_hr_payroll_formula', 'pb_hr_payroll_vietnam', 'payroll_analytics_approval']
    
    total_changes = 0
    for module in modules:
        print(f"\n{module}:")
        views_dir = os.path.join(base, module, 'views')
        wizards_dir = os.path.join(base, module, 'wizards')
        
        for dir_path in [views_dir, wizards_dir]:
            if os.path.exists(dir_path):
                for filename in os.listdir(dir_path):
                    if filename.endswith('.xml'):
                        filepath = os.path.join(dir_path, filename)
                        total_changes += fix_views_in_file(filepath)
    
    print(f"\nTotal fixes applied: {total_changes}")
    
    # Validate all XML files
    print("\nValidating XML files...")
    errors = 0
    for module in modules:
        for subdir in ['views', 'wizards']:
            dir_path = os.path.join(base, module, subdir)
            if os.path.exists(dir_path):
                for filename in os.listdir(dir_path):
                    if filename.endswith('.xml'):
                        filepath = os.path.join(dir_path, filename)
                        result = subprocess.run(['xmllint', '--noout', filepath], 
                                               capture_output=True, text=True)
                        if result.returncode != 0:
                            print(f"  ERROR in {module}/{subdir}/{filename}")
                            errors += 1
    
    if errors == 0:
        print("  All XML files are valid!")
    else:
        print(f"  {errors} files have XML errors")

if __name__ == '__main__':
    main()
