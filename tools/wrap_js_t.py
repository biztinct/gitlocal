#!/usr/bin/env python3
"""
Odoo JS i18n Wrapper — Adds _t() to hardcoded English strings in JS files.

This script:
1. Scans JS files for hardcoded English strings
2. Adds `import { _t } from "@web/core/l10n/translation"` if missing
3. Wraps user-facing strings in _t()
4. Outputs the strings for adding to .po files

Usage:
    python3 wrap_js_t.py                  # Wrap all target JS files
    python3 wrap_js_t.py --dry-run        # Preview without modifying
"""
import argparse
import os
import re
import shutil

BASE_DIR = '/Users/adity/Documents/GitHub/gitlocal'

# Map of JS file paths (relative) to strings that should be wrapped in _t()
# Only includes user-visible UI strings, not debug/console/internal strings
JS_TRANSLATIONS = {
    'pb_hr_workforce/static/src/js/overtime_rules.js': {
        '"Weekday"': '_t("Weekday")',
        '"Extra hours on regular work days"': '_t("Extra hours on regular work days")',
        '"Weekend"': '_t("Weekend")',
        '"Holiday"': '_t("Holiday")',
        '"All hours on public holidays"': '_t("All hours on public holidays")',
        '"Night Shift"': '_t("Night Shift")',
        '"Hours within night time window"': '_t("Hours within night time window")',
        '"Extended"': '_t("Extended")',
        '"OT exceeding daily max cap"': '_t("OT exceeding daily max cap")',
        '"Every day"': '_t("Every day")',
        '"No days selected"': '_t("No days selected")',
        '"Please enter a rule name"': '_t("Please enter a rule name")',
        '"Rule updated"': '_t("Rule updated")',
        '"Rule created"': '_t("Rule created")',
        '"Rule deleted"': '_t("Rule deleted")',
    },
    'pb_hr_workforce/static/src/js/shift_planning_grid.js': {
        '"Copy shifts to next week"': '_t("Copy shifts to next week")',
        '"Shift conflict detected"': '_t("Shift conflict detected")',
        '"Failed to load shift grid"': '_t("Failed to load shift grid")',
        '"Employee is on leave this day"': '_t("Employee is on leave this day")',
        '"Shift created"': '_t("Shift created")',
        '"Failed to create shift"': '_t("Failed to create shift")',
        '"Shift deleted"': '_t("Shift deleted")',
        '"Cannot delete this shift"': '_t("Cannot delete this shift")',
        '"Publish failed"': '_t("Publish failed")',
        '"Copy failed"': '_t("Copy failed")',
    },
    'pb_hr_workforce/static/src/js/attendance_live.js': {
        '"Attendance data refreshed"': '_t("Attendance data refreshed")',
    },
    'pb_hr_workforce/static/src/js/attendance_timecard.js': {
        '"With hours only"': '_t("With hours only")',
    },
    'pb_hr_workforce/static/src/js/workforce_dashboard.js': {
        '"Total Hours"': '_t("Total Hours")',
        '"OT Hours"': '_t("OT Hours")',
    },
    'pb_hr_workforce/static/src/js/payroll_report.js': {
        '"Failed to load payroll report"': '_t("Failed to load payroll report")',
    },
    'payroll_analytics_approval/static/src/js/payroll_charts_v19.js': {
        '"Current"': '_t("Current")',
        '"Previous"': '_t("Previous")',
        '"Alert"': '_t("Alert")',
        '"Warning"': '_t("Warning")',
        '"Normal"': '_t("Normal")',
        '"Review all components carefully before approval"': '_t("Review all components carefully before approval")',
        '"No critical issues detected"': '_t("No critical issues detected")',
    },
    'pb_hr_payroll_base/static/src/js/payroll_dashboard_enhanced.js': {
        '"Access Dashboard"': '_t("Access Dashboard")',
        '"Request Access"': '_t("Request Access")',
        '"Total Payroll"': '_t("Total Payroll")',
    },
    'pb_hr_payroll_base/static/src/js/control_panel_home_icon.js': {
        '"Open HR Flow Dashboard"': '_t("Open HR Flow Dashboard")',
    },
    'pb_hr_payroll_formula/static/src/js/cell_editor.js': {
        '"Invalid number"': '_t("Invalid number")',
        '"Unbalanced parentheses"': '_t("Unbalanced parentheses")',
    },
}

# Vietnamese translations for the JS strings (for .po file generation)
VI_TRANSLATIONS = {
    # pb_hr_workforce - Overtime Rules
    "Weekday": "Ngày thường",
    "Extra hours on regular work days": "Giờ làm thêm vào ngày thường",
    "Weekend": "Cuối tuần",
    "Holiday": "Ngày lễ",
    "All hours on public holidays": "Tất cả giờ vào ngày lễ",
    "Night Shift": "Ca đêm",
    "Hours within night time window": "Giờ trong khung thời gian đêm",
    "Extended": "Kéo dài",
    "OT exceeding daily max cap": "Tăng ca vượt mức tối đa trong ngày",
    "Every day": "Mỗi ngày",
    "No days selected": "Chưa chọn ngày",
    "Please enter a rule name": "Vui lòng nhập tên quy tắc",
    "Rule updated": "Đã cập nhật quy tắc",
    "Rule created": "Đã tạo quy tắc",
    "Rule deleted": "Đã xóa quy tắc",
    # pb_hr_workforce - Shift Planning
    "Copy shifts to next week": "Sao chép ca sang tuần sau",
    "Shift conflict detected": "Phát hiện trùng ca",
    "Failed to load shift grid": "Không thể tải lưới ca",
    "Employee is on leave this day": "Nhân viên nghỉ phép ngày này",
    "Shift created": "Đã tạo ca",
    "Failed to create shift": "Không thể tạo ca",
    "Shift deleted": "Đã xóa ca",
    "Cannot delete this shift": "Không thể xóa ca này",
    "Publish failed": "Xuất bản thất bại",
    "Copy failed": "Sao chép thất bại",
    # pb_hr_workforce - Attendance & Dashboard
    "Attendance data refreshed": "Đã làm mới dữ liệu chấm công",
    "With hours only": "Chỉ hiển thị giờ",
    "Total Hours": "Tổng giờ",
    "OT Hours": "Giờ tăng ca",
    "Failed to load payroll report": "Không thể tải báo cáo lương",
    # payroll_analytics_approval - Charts
    "Current": "Hiện tại",
    "Previous": "Kỳ trước",
    "Alert": "Cảnh báo",
    "Warning": "Cảnh báo",
    "Normal": "Bình thường",
    "Review all components carefully before approval": "Xem xét kỹ tất cả thành phần trước khi phê duyệt",
    "No critical issues detected": "Không phát hiện vấn đề nghiêm trọng",
    # pb_hr_payroll_base - Dashboard
    "Access Dashboard": "Truy cập bảng điều khiển",
    "Request Access": "Yêu cầu quyền truy cập",
    "Total Payroll": "Tổng bảng lương",
    "Open HR Flow Dashboard": "Mở bảng điều khiển HR Flow",
    # pb_hr_payroll_formula - Cell Editor
    "Invalid number": "Số không hợp lệ",
    "Unbalanced parentheses": "Dấu ngoặc không cân bằng",
}

T_IMPORT_LINE = 'import { _t } from "@web/core/l10n/translation";'


def process_js_file(filepath, replacements, dry_run=False):
    """Process a single JS file: add _t import and wrap strings."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content
    modified_count = 0

    # Apply string replacements
    for old, new in replacements.items():
        if old in content:
            # Be careful not to replace already-wrapped strings
            # Check if the string is already inside _t()
            pattern = re.escape(old)
            # Only replace if NOT preceded by _t(
            occurrences = [(m.start(), m.end()) for m in re.finditer(pattern, content)]
            for start, end in reversed(occurrences):
                before = content[max(0, start-3):start]
                if '_t(' not in before:
                    content = content[:start] + new + content[end:]
                    modified_count += 1

    # Add _t import if we modified anything and it's not already imported
    if modified_count > 0 and '_t' not in original:
        if '/** @odoo-module **/' in content:
            content = content.replace(
                '/** @odoo-module **/',
                f'/** @odoo-module **/\n{T_IMPORT_LINE}',
                1
            )
        else:
            content = T_IMPORT_LINE + '\n' + content

    if content != original and not dry_run:
        backup = filepath + '.bak'
        shutil.copy2(filepath, backup)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

    return modified_count


def generate_po_entries(translations):
    """Generate PO-format entries for new JS strings."""
    lines = []
    lines.append("")
    lines.append("# === JavaScript UI Strings ===")
    for en, vi in sorted(translations.items()):
        lines.append(f'')
        lines.append(f'#. JS Dashboard/UI String')
        lines.append(f'msgid "{en}"')
        lines.append(f'msgstr "{vi}"')
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='Wrap JS strings in _t()')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--generate-po', action='store_true',
                        help='Generate PO entries for new strings')
    args = parser.parse_args()

    print("=" * 60)
    print("  Odoo JS i18n Wrapper")
    print("=" * 60)

    total = 0
    for rel_path, replacements in JS_TRANSLATIONS.items():
        filepath = os.path.join(BASE_DIR, rel_path)
        if not os.path.exists(filepath):
            print(f"  ⚠️  Not found: {rel_path}")
            continue

        count = process_js_file(filepath, replacements, dry_run=args.dry_run)
        if count > 0:
            print(f"  ✅ {rel_path}: {count} strings wrapped")
        else:
            print(f"  ⏭️  {rel_path}: no changes needed")
        total += count

    print()
    print(f"  Total: {total} strings wrapped in _t()")
    if args.dry_run:
        print("  (DRY RUN — no files modified)")
    print("=" * 60)

    if args.generate_po:
        print()
        print("PO entries to add to vi_VN.po files:")
        print(generate_po_entries(VI_TRANSLATIONS))


if __name__ == '__main__':
    main()
