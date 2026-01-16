
import re

file_path = 'pb_hr_payroll_formula/i18n/vi_VN.po'
regex = re.compile(r"(?:#~ )?#. +module: (.+)")

with open(file_path, 'r') as f:
    lines = f.readlines()

failed_lines = []
for i, line in enumerate(lines):
    s = line.strip()
    if s.startswith('#.') or s.startswith('#~ #.'):
        match = regex.match(line)
        if not match:
            failed_lines.append((i+1, line.strip()))

print(f"Found {len(failed_lines)} lines starting with #. that fail the Odoo regex.")
for i, l in failed_lines[:20]:
    print(f"Line {i}: '{l}'")
