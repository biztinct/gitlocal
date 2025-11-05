#!/usr/bin/env python3
"""
Script to fill empty Vietnamese translations in vi_VN.po from msg.po
"""

import re
from pathlib import Path

def parse_po_file(filepath):
    """Parse a .po file and extract msgid->msgstr mappings"""
    translations = {}
    current_msgid = None
    current_msgstr = None
    msgid_lines = []
    msgstr_lines = []
    in_msgid = False
    in_msgstr = False

    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for line in lines:
        line = line.rstrip('\n')

        # Skip comments and metadata
        if line.startswith('#') or not line.strip():
            continue

        # Start of msgid
        if line.startswith('msgid '):
            if current_msgid and current_msgstr:
                # Save previous entry
                msgid_text = ''.join(msgid_lines)
                msgstr_text = ''.join(msgstr_lines)
                if msgid_text and msgid_text != '""':
                    translations[msgid_text] = msgstr_text

            # Start new entry
            msgid_lines = [line[6:].strip().strip('"')]
            msgstr_lines = []
            in_msgid = True
            in_msgstr = False
            current_msgid = True
            current_msgstr = False

        # Start of msgstr
        elif line.startswith('msgstr '):
            msgstr_lines = [line[7:].strip().strip('"')]
            in_msgid = False
            in_msgstr = True
            current_msgstr = True

        # Continuation line
        elif line.startswith('"') and line.endswith('"'):
            content = line.strip().strip('"')
            if in_msgid:
                msgid_lines.append(content)
            elif in_msgstr:
                msgstr_lines.append(content)

    # Don't forget the last entry
    if current_msgid and current_msgstr:
        msgid_text = ''.join(msgid_lines)
        msgstr_text = ''.join(msgstr_lines)
        if msgid_text and msgid_text != '""':
            translations[msgid_text] = msgstr_text

    return translations

def normalize_msgid(msgid):
    """Normalize msgid for comparison by removing extra whitespace"""
    # Replace multiple spaces/newlines with single space
    normalized = re.sub(r'\s+', ' ', msgid)
    return normalized.strip()

def fill_translations(vi_vn_path, msg_path):
    """Fill empty translations in vi_VN.po from msg.po"""

    print(f"Reading reference translations from {msg_path}...")
    ref_translations = parse_po_file(msg_path)

    # Create normalized lookup
    normalized_ref = {}
    for msgid, msgstr in ref_translations.items():
        norm_key = normalize_msgid(msgid)
        normalized_ref[norm_key] = msgstr

    print(f"Found {len(ref_translations)} reference translations")

    print(f"\nReading target file {vi_vn_path}...")
    with open(vi_vn_path, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    output_lines = []

    empty_count = 0
    filled_count = 0
    not_found_count = 0
    current_msgid = None
    in_msgid = False
    msgid_buffer = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # Detect start of msgid
        if line.startswith('msgid '):
            msgid_buffer = [line[6:].strip().strip('"')]
            in_msgid = True
            output_lines.append(line)
            i += 1

            # Collect multiline msgid
            while i < len(lines) and lines[i].startswith('"') and in_msgid:
                msgid_buffer.append(lines[i].strip().strip('"'))
                output_lines.append(lines[i])
                i += 1

            current_msgid = ''.join(msgid_buffer)
            in_msgid = False
            continue

        # Detect msgstr and check if empty
        if line.startswith('msgstr '):
            msgstr_content = line[7:].strip()

            # Check if empty (msgstr "" or msgstr "")
            if msgstr_content == '""' or msgstr_content == '"':
                empty_count += 1

                # Try to find translation
                if current_msgid:
                    norm_msgid = normalize_msgid(current_msgid)

                    # Look up translation
                    if norm_msgid in normalized_ref:
                        translation = normalized_ref[norm_msgid]
                        if translation:  # Only fill if translation is not empty
                            output_lines.append(f'msgstr "{translation}"')
                            filled_count += 1
                        else:
                            output_lines.append(line)
                    else:
                        output_lines.append(line)
                        not_found_count += 1
                        print(f"  Translation not found: {current_msgid[:60]}...")
                else:
                    output_lines.append(line)
            else:
                # msgstr already has content, keep it
                output_lines.append(line)

            current_msgid = None
            i += 1
            continue

        # All other lines
        output_lines.append(line)
        i += 1

    # Write back
    print(f"\nWriting updated translations to {vi_vn_path}...")
    with open(vi_vn_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines))

    print("\n" + "="*60)
    print("TRANSLATION SUMMARY")
    print("="*60)
    print(f"Empty translations found:       {empty_count}")
    print(f"Translations filled:            {filled_count}")
    print(f"Translations not found:         {not_found_count}")
    print(f"Success rate:                   {filled_count}/{empty_count} ({100*filled_count/empty_count if empty_count > 0 else 0:.1f}%)")
    print("="*60)

    return filled_count, empty_count, not_found_count

if __name__ == '__main__':
    base_dir = Path('/Users/adity/Documents/GitHub/gitlocal/payroll_analytics_approval/i18n')
    vi_vn_file = base_dir / 'vi_VN.po'
    msg_file = base_dir / 'msg.po'

    if not vi_vn_file.exists():
        print(f"Error: {vi_vn_file} not found!")
        exit(1)

    if not msg_file.exists():
        print(f"Error: {msg_file} not found!")
        exit(1)

    filled, total, not_found = fill_translations(vi_vn_file, msg_file)

    if filled > 0:
        print(f"\n✓ Successfully filled {filled} translations!")
    else:
        print("\n✗ No translations were filled. Please check the files.")
