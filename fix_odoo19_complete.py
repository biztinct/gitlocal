#!/usr/bin/env python3
"""Complete Odoo 19 view compatibility fixes including attrs conversion.

Fixes:
1. <tree> -> <list>
2. </tree> -> </list>  
3. <group expand="0" string="Group By"> -> <group name="group_by">
4. attrs="{'invisible': ...}" -> invisible="..."
5. attrs="{'required': ...}" -> required="..."
6. attrs="{'readonly': ...}" -> readonly="..."
"""
import re
import os
import subprocess
import ast

def convert_condition_to_domain_string(condition):
    """Convert a Python domain condition to Odoo domain string format."""
    if isinstance(condition, str):
        return condition
    
    # Convert tuples to domain format
    if isinstance(condition, (list, tuple)):
        parts = []
        for item in condition:
            if isinstance(item, str):
                # Logical operators
                parts.append(item)
            elif isinstance(item, (list, tuple)) and len(item) >= 3:
                # Domain tuple like ('field', '=', value)
                field, op, value = item[0], item[1], item[2]
                if isinstance(value, bool):
                    value = str(value)
                elif isinstance(value, str):
                    value = f"'{value}'"
                parts.append(f"('{field}', '{op}', {value})")
        return '[' + ', '.join(parts) + ']'
    
    return str(condition)

def convert_attrs_to_inline(match):
    """Convert attrs="{'invisible': [...]}" to inline attributes."""
    full_match = match.group(0)
    attrs_value = match.group(1)
    
    try:
        # Parse the Python dict
        attrs_dict = ast.literal_eval(attrs_value)
        
        inline_attrs = []
        for key, value in attrs_dict.items():
            if key in ('invisible', 'required', 'readonly', 'column_invisible'):
                # Convert the domain to string format
                if isinstance(value, bool):
                    domain_str = str(value)
                elif isinstance(value, list):
                    # It's a domain - convert to string
                    parts = []
                    for item in value:
                        if isinstance(item, str):
                            parts.append(f"'{item}'" if item in ('|', '&', '!') else item)
                        elif isinstance(item, (list, tuple)):
                            field, op, val = item[0], item[1], item[2]
                            if isinstance(val, bool):
                                val_str = str(val)
                            elif isinstance(val, str):
                                val_str = f"'{val}'"
                            else:
                                val_str = str(val)
                            parts.append(f"('{field}', '{op}', {val_str})")
                    domain_str = '[' + ', '.join(parts) + ']'
                else:
                    domain_str = str(value)
                
                inline_attrs.append(f'{key}="{domain_str}"')
        
        if inline_attrs:
            return ' '.join(inline_attrs)
        else:
            return ''  # Remove attrs entirely if no recognized keys
            
    except (ValueError, SyntaxError) as e:
        # If we can't parse, leave as is but remove 'attrs=' prefix
        print(f"  Warning: Could not parse attrs: {attrs_value[:50]}...")
        return full_match  # Keep original if can't parse

def fix_views_in_file(filepath):
    """Apply all Odoo 19 fixes to a view file."""
    if not os.path.exists(filepath):
        return 0
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    changes = 0
    
    # 1. Convert <tree to <list (keeping attributes)
    content, n = re.subn(r'<tree(\s|>|/>)', r'<list\1', content, flags=re.IGNORECASE)
    changes += n
    
    # 2. Convert </tree> to </list>
    content, n = re.subn(r'</tree>', '</list>', content, flags=re.IGNORECASE)
    changes += n
    
    # 3. Convert search view group syntax
    content, n = re.subn(
        r'<group\s+expand="0"\s+string="Group By">',
        '<group name="group_by">',
        content, flags=re.IGNORECASE
    )
    changes += n
    
    content, n = re.subn(
        r'<group\s+string="Group By"\s+expand="0">',
        '<group name="group_by">',
        content, flags=re.IGNORECASE
    )
    changes += n
    
    # 4. Convert attrs to inline - handle multi-line attrs
    # Pattern to match attrs="..." including multi-line
    attrs_pattern = re.compile(
        r'attrs\s*=\s*"(\{[^"]*\})"',
        re.MULTILINE | re.DOTALL
    )
    
    def replace_attrs(m):
        result = convert_attrs_to_inline(m)
        return result
    
    new_content = attrs_pattern.sub(replace_attrs, content)
    if new_content != content:
        attrs_changes = len(attrs_pattern.findall(content))
        changes += attrs_changes
        content = new_content
    
    # 5. Convert states= to invisible (for buttons)
    # states="draft,confirm" -> invisible="state not in ('draft', 'confirm')"
    states_pattern = re.compile(r'states\s*=\s*"([^"]+)"')
    
    def convert_states(m):
        states = m.group(1).split(',')
        states_tuple = ', '.join(f"'{s.strip()}'" for s in states)
        return f'invisible="state not in ({states_tuple})"'
    
    content, n = states_pattern.subn(convert_states, content)
    changes += n
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  {os.path.basename(filepath)}: {changes} fixes")
        return changes
    else:
        print(f"  {os.path.basename(filepath)}: No changes")
        return 0

def main():
    base = '/Users/adity/Documents/GitHub/gitlocal'
    modules = ['pb_hr_payroll_formula', 'pb_hr_payroll_vietnam', 'payroll_analytics_approval']
    
    total_changes = 0
    for module in modules:
        print(f"\n{module}:")
        for subdir in ['views', 'wizards']:
            dir_path = os.path.join(base, module, subdir)
            if os.path.exists(dir_path):
                for filename in sorted(os.listdir(dir_path)):
                    if filename.endswith('.xml'):
                        filepath = os.path.join(dir_path, filename)
                        total_changes += fix_views_in_file(filepath)
    
    print(f"\nTotal fixes: {total_changes}")
    
    # Validate
    print("\nValidating XML...")
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
                            print(f"  ERROR: {module}/{subdir}/{filename}")
                            errors += 1
    
    print(f"  {'All valid!' if errors == 0 else f'{errors} errors'}")

if __name__ == '__main__':
    main()
