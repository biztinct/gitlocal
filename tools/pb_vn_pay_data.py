# -*- coding: utf-8 -*-
"""Build the monthly pay-data spreadsheet for the Vietnam demo.

    python3 tools/pb_vn_pay_data.py [output.xlsx]

WHAT MAKES THIS FILE SHORT IS THE MAPPING, NOT THE SCRIPT. The Vietnam scheme
asks a person for about forty-five values. Twenty-two of them now come off the
employee and contract records, four off the contract as components, and the pay
period answers the month itself — so what is left is the employee's code, the
days and hours they worked, and the handful of amounts somebody approved this
month. That is the entire file.

THE HEADERS ARE THE COMPONENT NAMES, SPELLED EXACTLY. The importer matches a
header to a column by normalising both (lower-cased, letters and digits only),
so "Weekday overtime — hours this run" finds `HRSWD` and nothing else does. They
are imported from `pb_payroll_mapping_vn.models.vn_profile` rather than retyped
here, because a header that drifts from the component it names fails silently:
the column simply reads zero and the payslip is quietly wrong.

NO ODOO, NO DATABASE. It is a build step, not a deployment, so it runs on a
laptop with openpyxl and nothing else.
"""

import calendar
import datetime
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'pb_payroll_mapping_vn', 'models'))
import vn_profile                                        # noqa: E402

try:
    import openpyxl
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
except ImportError:                                      # pragma: no cover
    print('This needs openpyxl: python3 -m pip install openpyxl')
    raise SystemExit(1)


DEFAULT_OUT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'RIZE', 'VIETNAM',
    'Rize Vietnam - demo pay data.xlsx')

#: The five demo people, and a month that looks like a real one for each.
#:
#: The overtime follows the JOB rather than being sprinkled about: the field
#: technician and the operations supervisor work weekends and nights, the sales
#: executive works the odd late evening, and the country manager does not record
#: overtime at all. A demo in which everybody has the same eight hours of
#: weekend work is a demo nobody believes.
#:
#: `money` is kept for the note it carries, and is NOT written into the sheet:
#: every amount is a contract component now (owner's ruling, 2026-09-11), and
#: the demo seeder puts these same figures onto the five contracts.
ROWS = [
    {
        'code': 'DEMO001', 'name': 'Demo Nguyen Thi Mai',
        'note': 'Joined three days ago, so only part of the month is paid.',
        'paid_days': 3,
        'HRSWD': 6, 'HRSWE': 0, 'HRSHOL': 0, 'HRSNIGHT': 0,
        'money': {},
    },
    {
        'code': 'DEMO002', 'name': 'Demo Tran Van Hung',
        'note': 'Full month. Field supervisor, so weekend and night work.',
        'paid_days': None,
        'HRSWD': 14, 'HRSWE': 8, 'HRSHOL': 0, 'HRSNIGHT': 6,
        'money': {'REFERINC': 3000000},
    },
    {
        'code': 'DEMO003', 'name': 'Demo Le Thi Hoa',
        'note': 'Three days annual leave taken, and repaying a salary advance.',
        'paid_days': None, 'paid_days_less': 3,
        'HRSWD': 4, 'HRSWE': 0, 'HRSHOL': 0, 'HRSNIGHT': 0,
        'money': {'ADVANCE': 2000000},
    },
    {
        'code': 'DEMO004', 'name': 'Demo Pham Minh Quan',
        'note': 'Harvest month. Heavy overtime and a seasonal incentive.',
        'paid_days': None,
        'HRSWD': 18, 'HRSWE': 12, 'HRSHOL': 8, 'HRSNIGHT': 10,
        'money': {'AGROINC': 1500000},
    },
    {
        'code': 'DEMO005', 'name': 'Demo Vo Thanh Son',
        'note': 'Country manager. No overtime; carries the quarterly award.',
        'paid_days': None,
        'HRSWD': 0, 'HRSWE': 0, 'HRSHOL': 0, 'HRSNIGHT': 0,
        'money': {'OTHERTAX': 5000000},
    },
]

HEADER_FILL = PatternFill('solid', fgColor='1F3A5F')
KEY_FILL = PatternFill('solid', fgColor='EEF2F7')
TIME_FILL = PatternFill('solid', fgColor='F3F8F3')
HEADER_FONT = Font(color='FFFFFF', bold=True, size=10)
THIN = Side(style='thin', color='C8D2DE')
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def standard_working_days(today):
    """Working days in the month, Monday to Saturday.

    Six days is the Vietnamese working week this scheme is written for, and the
    number is COUNTED rather than fixed at 26: a demo given in a month with 27
    of them should not show 26, because the first thing an operations manager
    does with a payroll file is check that number.
    """
    days = calendar.monthrange(today.year, today.month)[1]
    return sum(1 for day in range(1, days + 1)
               if datetime.date(today.year, today.month, day).weekday() != 6)


def build(path):
    today = datetime.date.today()
    standard = standard_working_days(today)

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = 'Pay data'

    layout = vn_profile.sheet_layout()
    time_codes = {code for code, _label in vn_profile.SHEET_TIME_COLUMNS}

    for index, (code, label, reserved) in enumerate(layout, start=1):
        letter = get_column_letter(index)
        cell = sheet.cell(row=1, column=index, value=label)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(wrap_text=True, vertical='center',
                                   horizontal='center')
        cell.border = BORDER
        if reserved:
            # HIDDEN, NOT ABSENT. The column has to exist so that the position
            # it holds cannot be taken by a column that means something else
            # (see RESERVED_POSITIONS); it has to be empty so the component
            # falls through to the contract or the pay period; and it has to be
            # out of sight, because it is addressed to the resolver and not to
            # the person filling the file in.
            sheet.column_dimensions[letter].hidden = True
            sheet.column_dimensions[letter].width = 4
        else:
            sheet.column_dimensions[letter].width = 22 if index <= 2 else 16
    sheet.row_dimensions[1].height = 46

    for row_index, row in enumerate(ROWS, start=2):
        values = {
            'EMPCODE': row['code'],
            'EMPNAME': row['name'],
            'STDDAYS': standard,
            'PAIDDAYS': (row['paid_days'] if row['paid_days']
                         else standard - row.get('paid_days_less', 0)),
        }
        for code in ('HRSWD', 'HRSWE', 'HRSHOL', 'HRSNIGHT'):
            values[code] = row.get(code, 0)

        for col_index, (code, _label, reserved) in enumerate(layout, start=1):
            if reserved:
                continue
            cell = sheet.cell(row=row_index, column=col_index,
                              value=values.get(code, 0))
            cell.border = BORDER
            if code in ('EMPCODE', 'EMPNAME'):
                cell.fill = KEY_FILL
                cell.alignment = Alignment(horizontal='left')
            elif code in time_codes:
                cell.fill = TIME_FILL
                cell.alignment = Alignment(horizontal='right')
                cell.number_format = '0.##'
            else:
                cell.alignment = Alignment(horizontal='right')
                cell.number_format = '#,##0'

    sheet.freeze_panes = 'C2'
    sheet.auto_filter.ref = 'A1:%s%s' % (
        get_column_letter(len(layout)), len(ROWS) + 1)

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    workbook.save(path)
    return path, standard, layout


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUT
    path, standard, layout = build(path)
    real = [c for c in layout if not c[2]]
    print('Wrote %s' % os.path.normpath(path))
    print('%s columns to fill in, %s reserved and hidden, %s people, '
          '%s standard working days this month.'
          % (len(real), len(layout) - len(real), len(ROWS), standard))
    print('Everything else the pay run needs is read off the employee, the '
          'contract or the pay period.')


if __name__ == '__main__':
    main()
