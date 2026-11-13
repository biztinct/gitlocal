#!/usr/bin/env python3
"""Script to disable search views in Odoo XML files for Odoo 19 compatibility."""

import re
import os

def disable_search_views_in_file(filepath):
    """Find and comment out search view records in an XML file."""
    if not os.path.exists(filepath):
        return False, "File not found"
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Find search view record patterns
    search_view_pattern = re.compile(
        r'(\s*)(<record\s+id="[^"]*"\s+model="ir\.ui\.view">\s*'
        r'<field\s+name="name">[^<]*\.search</field>'
        r'.*?</record>)',
        re.DOTALL
    )
    
    def replace_with_comment(match):
        indent = match.group(1)
        record = match.group(2)
        return f'{indent}<!-- DISABLED - Search view validation error in Odoo 19\n{record}\n{indent}-->'
    
    content = search_view_pattern.sub(replace_with_comment, content)
    
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True, "Modified"
    return False, "No changes"

def main():
    base_dir = '/Users/adity/Documents/GitHub/gitlocal/payroll_analytics_approval/views'
    xml_files = [
        'payroll_approval_views.xml',
        'payroll_comparison_views.xml',
    ]
    
    for xml_file in xml_files:
        filepath = os.path.join(base_dir, xml_file)
        modified, status = disable_search_views_in_file(filepath)
        print(f"{xml_file}: {status}")

if __name__ == '__main__':
    main()
