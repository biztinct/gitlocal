"""Explicit, versioned workbook-to-statutory mapping. No ORM dependencies.

Tax Map is metadata, never an employee worksheet. All mapped values must be
numeric literals on the payroll sheet; formulas continue using normal Excel
absolute references, which the existing importer turns into constant rules.
Rates are fractions in both Excel and the database (0.05 means 5%).
"""
import datetime
import math
import re

SHEET = 'Tax Map'
HEADERS = ('Table Code', 'Country', 'Version', 'Effective From', 'Effective To',
           'Method', 'Basis', 'Slot', 'Field', 'Payroll Sheet', 'Cell', 'Label')
COUNTRIES = {'VN', 'ID', 'IN', 'SG', 'MY', 'TH', 'KH', 'PH'}


def date_text(value, required=False):
    if value in (None, '') and not required:
        return False
    if isinstance(value, datetime.datetime):
        value = value.date()
    if isinstance(value, datetime.date):
        return value.isoformat()
    return datetime.date.fromisoformat(str(value)).isoformat()


def read_tax_map(workbook):
    if SHEET not in workbook.sheetnames:
        return []
    sheet = workbook[SHEET]
    if tuple(c.value for c in sheet[1][:len(HEADERS)]) != HEADERS:
        raise ValueError('Tax Map has an invalid header. Use the payroll template format.')
    groups, cells = {}, set()
    for rownum, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), 2):
        if not any(v is not None for v in row):
            continue
        code, country, version, start, end, method, basis, slot, field, source, cell, label = row[:12]
        code = str(code or '').strip().upper()
        country = str(country or '').strip().upper()
        cell = str(cell or '').replace('$', '').upper()
        if not re.fullmatch(r'[A-Z][A-Z0-9]*', code) or country not in COUNTRIES:
            raise ValueError('Tax Map row %s has an invalid table code or country.' % rownum)
        if method not in ('progressive', 'whole_income', 'parameters') or basis not in ('monthly', 'annual', 'daily'):
            raise ValueError('Tax Map row %s has an invalid method or basis.' % rownum)
        if source == SHEET or source not in workbook.sheetnames or not re.fullmatch(r'[A-Z]+[1-9][0-9]*', cell):
            raise ValueError('Tax Map row %s has an invalid payroll cell.' % rownum)
        source_cell = workbook[source][cell]
        value = source_cell.value
        if source_cell.data_type == 'f' or isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError('Tax Map %s!%s must contain a numeric literal.' % (source, cell))
        if (source, cell) in cells:
            raise ValueError('Tax Map maps %s!%s more than once.' % (source, cell))
        cells.add((source, cell))
        if field not in ('upper', 'rate', 'parameter') or (method == 'parameters') != (field == 'parameter'):
            raise ValueError('Tax Map row %s has an invalid field for its method.' % rownum)
        slot = str(slot).strip() if field == 'parameter' else int(slot)
        if field != 'parameter' and slot < 1:
            raise ValueError('Tax band slots must be positive integers.')
        if field == 'rate' and not 0 <= value <= 1:
            raise ValueError('Tax Map rates must be fractions between 0 and 1.')
        metadata = {'code': code, 'country_code': country, 'version': str(version or '').strip(),
                    'effective_from': date_text(start, True), 'effective_to': date_text(end),
                    'method': method, 'basis': basis}
        if not metadata['version'] or (metadata['effective_to'] and metadata['effective_to'] < metadata['effective_from']):
            raise ValueError('Tax Map row %s has an invalid version or date range.' % rownum)
        key = (code, country, metadata['version'])
        group = groups.setdefault(key, dict(metadata, values=[]))
        if any(group[k] != metadata[k] for k in metadata):
            raise ValueError('Tax Map contains conflicting metadata for %s.' % code)
        if any(v['slot'] == slot and v['field'] == field for v in group['values']):
            raise ValueError('Tax Map contains a duplicate slot for %s.' % code)
        group['values'].append({'slot': slot, 'field': field, 'sheet': source,
                                'cell': cell, 'label': str(label or code), 'value': float(value)})
    for group in groups.values():
        if group['method'] == 'parameters':
            continue
        slots = sorted({v['slot'] for v in group['values']})
        if slots != list(range(1, len(slots) + 1)):
            raise ValueError('Tax Map band slots must be consecutive, starting at 1.')
        previous = 0
        for slot in slots:
            fields = {v['field']: v['value'] for v in group['values'] if v['slot'] == slot}
            if set(fields) != {'upper', 'rate'}:
                raise ValueError('Each tax band needs an upper bound and a rate.')
            cap = fields['upper']
            if (slot == slots[-1] and cap != 0) or (slot != slots[-1] and cap <= previous):
                raise ValueError('Tax band caps must increase, ending with 0 for unlimited.')
            previous = cap
    return list(groups.values())
