#!/bin/bash
# Script to fill Vietnamese translations by replacing empty msgstr with translations from msg.po

cd "/Users/adity/Documents/GitHub/gitlocal/payroll_analytics_approval/i18n"

# Create Python script inline
/usr/bin/env python3 << 'PYTHON_SCRIPT'
import re

# Read msg.po to get translations
translations = {}
with open('msg.po', 'r', encoding='utf-8') as f:
    content = f.read()

# Parse msg.po for msgid->msgstr mappings
entries = re.findall(r'msgid "(.*?)"\s*msgstr "(.*?)"', content, re.DOTALL)
for msgid, msgstr in entries:
    if msgid and msgstr:  # Only store non-empty pairs
        translations[msgid] = msgstr

print(f"Loaded {len(translations)} translations from msg.po")

# Read vi_VN.po
with open('vi_VN.po', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Process and fill empty translations
filled_count = 0
output_lines = []
i = 0

while i < len(lines):
    line = lines[i]
    output_lines.append(line)

    # Check if this is a msgid line
    if line.startswith('msgid '):
        # Extract msgid
        msgid_match = re.match(r'msgid "(.*?)"', line)
        if msgid_match:
            msgid = msgid_match.group(1)

            # Check next line for msgstr
            if i + 1 < len(lines) and lines[i + 1].startswith('msgstr '):
                msgstr_line = lines[i + 1]

                # Check if empty
                if msgstr_line.strip() == 'msgstr ""':
                    # Look up translation
                    if msgid in translations:
                        # Replace with translation
                        output_lines.append(f'msgstr "{translations[msgid]}"\n')
                        filled_count += 1
                        i += 2  # Skip the old msgstr line
                        continue

    i += 1

# Write back
with open('vi_VN.po', 'w', encoding='utf-8') as f:
    f.writelines(output_lines)

print(f"Filled {filled_count} translations")
PYTHON_SCRIPT

echo "Translation filling complete!"
