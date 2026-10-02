#!/usr/bin/env python3
"""
Convert Odoo attrs to inline invisible/required for Odoo 19 compatibility.
Usage: python3 convert_attrs.py <file.xml>
"""
import re
import sys

def convert_domain_to_expr(domain_str):
    """Convert Odoo domain list to Python-like expression"""
    # Clean up the domain string
    domain_str = domain_str.strip()
    
    if not domain_str or domain_str == '[]':
        return ''
    
    # Remove outer brackets
    if domain_str.startswith('[') and domain_str.endswith(']'):
        domain_str = domain_str[1:-1].strip()
    
    # Parse tuples and operators
    parts = []
    operators = []
    current_op = 'and'  # default
    
    # Simple regex to find tuples like ('field', 'op', 'value')
    tuple_pattern = r"\('([^']+)',\s*'([^']+)',\s*([^)]+)\)"
    
    # Check for OR operators
    if "'|'" in domain_str or '"|"' in domain_str:
        # This is an OR domain - complex, we'll simplify
        pass
    
    # Find all tuples
    matches = re.findall(tuple_pattern, domain_str)
    
    expressions = []
    for field, op, value in matches:
        value = value.strip()
        # Remove quotes from value if present
        if (value.startswith("'") and value.endswith("'")) or \
           (value.startswith('"') and value.endswith('"')):
            value = value[1:-1]
        
        # Convert operator
        if op == '=':
            expr = f"{field} == '{value}'" if not value.lstrip('-').isdigit() and value not in ['True', 'False'] else f"{field} == {value}"
        elif op == '!=':
            expr = f"{field} != '{value}'" if not value.lstrip('-').isdigit() and value not in ['True', 'False'] else f"{field} != {value}"
        elif op == 'in':
            expr = f"{field} in {value}"
        elif op == 'not in':
            expr = f"{field} not in {value}"
        elif op == '>':
            expr = f"{field} > {value}"
        elif op == '<':
            expr = f"{field} < {value}"
        elif op == '>=':
            expr = f"{field} >= {value}"
        elif op == '<=':
            expr = f"{field} <= {value}"
        else:
            expr = f"{field} {op} {value}"
        
        expressions.append(expr)
    
    # Check for OR operator at start
    if domain_str.strip().startswith("'|'") or domain_str.strip().startswith('"|"'):
        if len(expressions) >= 2:
            return f"({expressions[0]}) or ({expressions[1]})"
    
    # Default to AND
    return ' and '.join(expressions) if expressions else ''


def convert_attrs_in_file(filepath):
    """Convert attrs in a single file"""
    with open(filepath, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Pattern to match attrs with invisible
    # attrs="{'invisible': [domain]}"
    invisible_pattern = r'attrs="\{\'invisible\':\s*(\[[^\]]*\])\}"'
    
    def replace_invisible(match):
        domain = match.group(1)
        expr = convert_domain_to_expr(domain)
        if expr:
            return f'invisible="{expr}"'
        return ''
    
    content = re.sub(invisible_pattern, replace_invisible, content)
    
    # Pattern for attrs with required
    required_pattern = r'attrs="\{\'required\':\s*(\[[^\]]*\])\}"'
    
    def replace_required(match):
        domain = match.group(1)
        expr = convert_domain_to_expr(domain)
        if expr:
            return f'required="{expr}"'
        return ''
    
    content = re.sub(required_pattern, replace_required, content)
    
    # Pattern for attrs with readonly
    readonly_pattern = r'attrs="\{\'readonly\':\s*(\[[^\]]*\])\}"'
    
    def replace_readonly(match):
        domain = match.group(1)
        expr = convert_domain_to_expr(domain)
        if expr:
            return f'readonly="{expr}"'
        return ''
    
    content = re.sub(readonly_pattern, replace_readonly, content)
    
    if content != original_content:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"Updated: {filepath}")
    else:
        print(f"No changes: {filepath}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 convert_attrs.py <file.xml> [file2.xml ...]")
        sys.exit(1)
    
    for filepath in sys.argv[1:]:
        try:
            convert_attrs_in_file(filepath)
        except Exception as e:
            print(f"Error processing {filepath}: {e}")
