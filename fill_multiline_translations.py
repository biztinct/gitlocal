#!/usr/bin/env python3
"""
Improved script to handle multiline msgid/msgstr entries
"""

import re
from pathlib import Path

def parse_po_entries(filepath):
    """Parse .po file handling multiline entries properly"""
    translations = {}

    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i]

        # Found start of msgid
        if line.startswith('msgid '):
            msgid_parts = []

            # Extract first part
            match = re.match(r'msgid\s+"(.*)"', line.strip())
            if match:
                msgid_parts.append(match.group(1))

            # Check for continuation lines
            i += 1
            while i < len(lines) and lines[i].startswith('"'):
                cont_match = re.match(r'"(.*)"', lines[i].strip())
                if cont_match:
                    msgid_parts.append(cont_match.group(1))
                i += 1

            # Now we should be at msgstr
            if i < len(lines) and lines[i].startswith('msgstr '):
                msgstr_parts = []

                # Extract first part
                match = re.match(r'msgstr\s+"(.*)"', lines[i].strip())
                if match:
                    msgstr_parts.append(match.group(1))

                # Check for continuation lines
                i += 1
                while i < len(lines) and lines[i].startswith('"'):
                    cont_match = re.match(r'"(.*)"', lines[i].strip())
                    if cont_match:
                        msgstr_parts.append(cont_match.group(1))
                    i += 1

                # Store the translation
                msgid = ''.join(msgid_parts)
                msgstr = ''.join(msgstr_parts)

                if msgid and msgstr:  # Both non-empty
                    translations[msgid] = msgstr

                continue

        i += 1

    return translations

def fill_translations_multiline():
    base_dir = Path('/Users/adity/Documents/GitHub/gitlocal/payroll_analytics_approval/i18n')
    msg_file = base_dir / 'msg.po'
    vi_file = base_dir / 'vi_VN.po'

    print("=" * 70)
    print("Multiline Translation Filler (Improved)")
    print("=" * 70)

    # Parse msg.po
    print(f"\n[1/3] Parsing {msg_file.name} (with multiline support)...")
    translations = parse_po_entries(msg_file)
    print(f"   ✓ Loaded {len(translations)} translations")

    # Read vi_VN.po
    print(f"\n[2/3] Processing {vi_file.name}...")
    with open(vi_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    output_lines = []
    filled_count = 0
    empty_count = 0

    i = 0
    while i < len(lines):
        line = lines[i]

        # Found msgid
        if line.startswith('msgid '):
            msgid_parts = []
            msgid_line_start = i

            # Extract msgid (possibly multiline)
            match = re.match(r'msgid\s+"(.*)"', line.strip())
            if match:
                msgid_parts.append(match.group(1))
            output_lines.append(line)
            i += 1

            # Collect continuation lines
            while i < len(lines) and lines[i].startswith('"'):
                cont_match = re.match(r'"(.*)"', lines[i].strip())
                if cont_match:
                    msgid_parts.append(cont_match.group(1))
                output_lines.append(lines[i])
                i += 1

            # Now check msgstr
            if i < len(lines) and lines[i].startswith('msgstr '):
                msgid = ''.join(msgid_parts)
                msgstr_line = lines[i]

                # Check if empty
                msgstr_match = re.match(r'msgstr\s+"(.*)"', msgstr_line.strip())
                if msgstr_match:
                    msgstr_content = msgstr_match.group(1)

                    if not msgstr_content:  # Empty msgstr
                        empty_count += 1

                        # Look up translation
                        if msgid in translations:
                            # Replace with translation
                            output_lines.append(f'msgstr "{translations[msgid]}"\n')
                            filled_count += 1
                        else:
                            output_lines.append(msgstr_line)
                    else:
                        # Already has translation
                        output_lines.append(msgstr_line)

                i += 1
                continue

        output_lines.append(line)
        i += 1

    # Write back
    print(f"\n[3/3] Writing updated file...")
    with open(vi_file, 'w', encoding='utf-8') as f:
        f.writelines(output_lines)

    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"Empty translations found:       {empty_count}")
    print(f"Translations filled:            {filled_count}")
    print(f"Remaining empty:                {empty_count - filled_count}")
    if empty_count > 0:
        print(f"Success rate:                   {100 * filled_count / empty_count:.1f}%")
    print("=" * 70)

    return filled_count, empty_count

if __name__ == '__main__':
    try:
        filled, total = fill_translations_multiline()
        print(f"\n✓ Successfully filled {filled} more translations!")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
