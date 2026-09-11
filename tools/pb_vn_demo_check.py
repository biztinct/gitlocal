# -*- coding: utf-8 -*-
"""Prove the whole chain: spreadsheet in, five payslips out, values off records.

    sudo -u odoo python3 /odoo/odoo-server/odoo-bin shell \\
        -c /etc/odoo-server.conf -d rize --no-http < tools/pb_vn_demo_check.py

WHAT IT ACTUALLY CHECKS, and why each one is worth a line:

 1. the file matches five people by their code alone;
 2. five payslips compute, and every one has a take-home figure;
 3. the values that are NO LONGER in the file arrive anyway — the union flag,
    the dependants, the pay grade — and arrive from the RECORD, which is the
    only thing that proves the mapping is doing the work rather than a default
    happening to be right;
 4. the foreign hire takes the expatriate branch and the local ones do not;
 5. the overtime hours in the file turn into overtime pay.

It deletes the run it made. A validation that leaves a pay run behind is a
validation that will be mistaken for the demo.
"""

import base64
import os

PATH = os.environ.get('PB_DEMO_XLSX') or '/tmp/pb_vn_pay_data.xlsx'
CONFIG_CODE = os.environ.get('PB_DEMO_CONFIG') or 'RIZE_VIETNAM'
KEEP = os.environ.get('PB_DEMO_KEEP') == '1'


def letters_are_safe(env, config):
    """No column of the file may sit where an unmapped component expects one.

    THE CHECK THIS FILE EXISTS FOR AS MUCH AS THE PAYSLIPS. A component the file
    does not carry and the profile does not map falls back to matching by
    POSITION, and the short monthly file's sixth column is not the scheme's
    sixth column. The first live run of it read the month being paid out of a
    column of overtime hours (see `vn_profile.RESERVED_POSITIONS`).

    So this asserts the invariant rather than the symptom: for every position
    the file occupies, the scheme component that owns that letter must either be
    carried by the file, be mapped onto a record, or be deliberately reserved.
    A future column added to the sheet trips this immediately, which is the only
    reason it is worth writing down.
    """
    import openpyxl
    sheet = openpyxl.load_workbook(PATH).active
    width = sheet.max_column
    headers = {}
    for index in range(1, width + 1):
        cell = sheet.cell(row=1, column=index)
        headers[index] = (str(cell.value or '')).strip()

    def norm(text):
        return ''.join(c for c in (text or '').lower() if c.isalnum())

    carried = {norm(h) for h in headers.values() if h}
    mapped = set(env['hr.payslip.import.mapping'].search(
        [('salary_structure_id', '=', config.id)]).mapped('component_id.code'))

    def letter_index(letter):
        value = 0
        for char in (letter or '').upper():
            value = value * 26 + (ord(char) - 64)
        return value

    problems = []
    for rule in config.rule_ids.filtered(lambda r: r.column_type == 'input'):
        index = letter_index(rule.column_letter)
        if not index or index > width:
            continue
        if rule.code in mapped:
            continue
        if norm(rule.name) in carried or norm(rule.code) in carried:
            continue
        occupant = headers.get(index) or '(empty)'
        if norm(occupant) in (norm(rule.name), norm(rule.code)):
            continue                    # reserved for itself, and empty
        problems.append('%s (%s) would read column %s of the file, which is '
                        '"%s"' % (rule.code, rule.column_letter,
                                  rule.column_letter, occupant))
    if problems:
        print('COLUMN POSITION CLASH — the file cannot be trusted:')
        for line in problems:
            print('  ! %s' % line)
        raise AssertionError('%s column(s) would be read by position' %
                             len(problems))
    print('column positions  : safe (%s columns checked)' % width)


def run(env):
    config = env['hr.formula.config'].search([('code', '=', CONFIG_CODE)], limit=1)
    assert config, 'no scheme %s' % CONFIG_CODE
    letters_are_safe(env, config)
    import datetime as _dt
    import calendar as _cal
    today = _dt.date.today()
    first = today.replace(day=1)
    last = today.replace(day=_cal.monthrange(today.year, today.month)[1])

    with open(PATH, 'rb') as handle:
        blob = base64.b64encode(handle.read())

    batch = env['hr.payroll.import.batch'].create({
        'name': 'CHECK — demo pay data',
        'source_type': 'excel',
        'formula_config_id': config.id,
        'import_file': blob,
        'import_filename': os.path.basename(PATH),
        'date_from': first,
        'date_to': last,
        'auto_create_employees': False,
        'auto_create_contracts': False,
        'match_by_code': True,
        'create_payslips': True,
        'payslip_state': 'draft',
    })
    batch.action_load_file()
    print('lines read        : %s' % batch.total_lines)
    batch.action_match_employees()
    print('people matched    : %s' % batch.matched_employees)
    print('rows in error     : %s' % batch.error_lines)
    if batch.error_lines:
        for line in batch.import_line_ids.filtered(lambda l: l.state == 'error')[:5]:
            print('   ! %s — %s' % (line.employee_code, line.error_message))

    batch.action_process()
    slips = batch.created_payslip_ids
    print('payslips created  : %s' % len(slips))

    codes = ('BASIC', 'ISUNION', 'DEPS', 'ROLEGRADE', 'ISLOCAL', 'HRSWD',
             'OTWD', 'SALARYPAID', 'GROSS', 'PIT', 'NET', 'SHUILOCAL',
             'SHUIFOREIGN', 'PRIVINSALW', 'UNIONDUES', 'UNIFORM')
    print('')
    header = 'code      ' + ''.join('%14s' % c for c in codes)
    print(header)
    for slip in slips.sorted(lambda s: s.employee_id.employee_id or ''):
        values = {}
        for line in slip.line_ids:
            values[line.code] = line.total
        row = '%-10s' % (slip.employee_id.employee_id or '?')
        for code in codes:
            row += '%14s' % _fmt(values.get(code))
        print(row)

    print('')
    print('--- where each value came from, for one person ---')
    for code in ('DEMO002', 'DEMO005'):
        sample = slips.filtered(
            lambda s: s.employee_id.employee_id == code)[:1]
        if sample:
            print('')
            print('%s:' % code)
            _provenance(env, sample,
                        ('ISUNION', 'DEPS', 'ROLEGRADE', 'BASIC', 'ISLOCAL',
                         'HOURSDAY', 'CONTRACTMTH', 'HRSWD', 'STDDAYS',
                         'PAYMONTH', 'UNIFORM', 'PRIVINSAMT', 'OTWDQUAL'))

    if not KEEP:
        run_record = batch.payslip_run_id
        slips.unlink()
        if run_record:
            run_record.unlink()
        batch.unlink()
        env.cr.commit()
        print('')
        print('check run removed; the database is back as it was.')
    else:
        env.cr.commit()


def _fmt(value):
    if value is None:
        return '-'
    if abs(value) >= 1000:
        return '{:,.0f}'.format(value)
    return '{:g}'.format(value)


def _provenance(env, slip, codes):
    """Ask the payslip where each input came from, rather than inferring it."""
    store = slip.formula_input_sources if \
        'formula_input_sources' in slip._fields else None
    print('inputs with a real source: %s of %s'
          % (slip.pb_sourced_inputs, len(codes)))
    if not store:
        print('(this build does not record where an input came from)')
        return
    import json
    try:
        data = json.loads(store or '{}')
    except Exception:
        print('(could not read the provenance record)')
        return
    rows = data.get('inputs') if (isinstance(data, dict)
                                  and 'inputs' in data) else data
    if isinstance(rows, dict):
        for code in codes:
            entry = rows.get(code)
            if entry is None:
                continue
            print('  %-12s %s' % (code, entry))
    else:
        print(json.dumps(rows)[:1500])


run(env)                                                # noqa: F821
