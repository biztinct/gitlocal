#!/usr/bin/env python3
"""
Complete script to fill all empty Vietnamese translations from msg.po
"""

import re
from pathlib import Path

def main():
    base_dir = Path('/Users/adity/Documents/GitHub/gitlocal/payroll_analytics_approval/i18n')
    msg_file = base_dir / 'msg.po'
    vi_file = base_dir / 'vi_VN.po'

    print("=" * 70)
    print("Vietnamese Translation Filler for payroll_analytics_approval")
    print("=" * 70)

    # Step 1: Parse msg.po for all translations
    print(f"\n[1/4] Reading reference translations from {msg_file.name}...")
    translations = {}

    with open(msg_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract all msgid/msgstr pairs with better regex
    # Handle multiline strings
    pattern = r'msgid\s+"([^"]*)"\s*msgstr\s+"([^"]*)"'
    matches = re.findall(pattern, content, re.MULTILINE)

    for msgid, msgstr in matches:
        if msgid and msgstr:  # Only non-empty pairs
            translations[msgid] = msgstr

    print(f"   ✓ Loaded {len(translations)} translations")

    # Step 2: Read vi_VN.po
    print(f"\n[2/4] Reading target file {vi_file.name}...")
    with open(vi_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    print(f"   ✓ Read {len(lines)} lines")

    # Step 3: Process and fill empty translations
    print(f"\n[3/4] Processing translations...")
    output_lines = []
    filled_count = 0
    empty_count = 0
    not_found = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # Check for msgid followed by empty msgstr
        if line.startswith('msgid '):
            output_lines.append(line)

            # Extract msgid value
            msgid_match = re.match(r'msgid\s+"([^"]*)"', line)
            if msgid_match and i + 1 < len(lines):
                msgid = msgid_match.group(1)
                next_line = lines[i + 1]

                # Check if next line is empty msgstr
                if next_line.startswith('msgstr ') and next_line.strip() == 'msgstr ""':
                    empty_count += 1

                    # Look up translation
                    if msgid in translations and translations[msgid]:
                        output_lines.append(f'msgstr "{translations[msgid]}"\n')
                        filled_count += 1
                    else:
                        output_lines.append(next_line)
                        if msgid and msgid != '':  # Skip empty msgid
                            not_found.append(msgid[:50] + '...' if len(msgid) > 50 else msgid)

                    i += 2  # Skip msgstr line we just handled
                    continue

        output_lines.append(line)
        i += 1

    print(f"   ✓ Found {empty_count} empty translations")
    print(f"   ✓ Filled {filled_count} translations")
    print(f"   ✓ Not found: {len(not_found)} translations")

    # Step 4: Write back
    print(f"\n[4/4] Writing updated translations...")
    with open(vi_file, 'w', encoding='utf-8') as f:
        f.writelines(output_lines)

    print(f"   ✓ Saved to {vi_file.name}")

    # Summary
    print("\n" + "=" * 70)
    print("TRANSLATION SUMMARY")
    print("=" * 70)
    print(f"Empty translations found:       {empty_count}")
    print(f"Translations filled:            {filled_count}")
    print(f"Translations not found:         {len(not_found)}")
    if empty_count > 0:
        print(f"Success rate:                   {100 * filled_count / empty_count:.1f}%")
    print("=" * 70)

    if not_found and len(not_found) <= 10:
        print("\nTranslations not found:")
        for item in not_found:
            print(f"  - {item}")

    return filled_count, empty_count

if __name__ == '__main__':
    try:
        filled, total = main()
        print(f"\n✓ Process completed successfully!")
        print(f"✓ Filled {filled} out of {total} empty translations")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
