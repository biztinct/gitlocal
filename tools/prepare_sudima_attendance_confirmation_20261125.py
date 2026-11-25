"""Read the supplied role workbook; make a private, identity-checked plan.

Usage: python3 this.py WORKBOOK EMPLOYEE_EXPORT OUTPUT
EMPLOYEE_EXPORT is a read-only JSON export of Sudima hr.employee records.
Never overwrites the workbook; no customer rows belong in git.
"""
import collections
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

import openpyxl


def norm(value):
    value = unicodedata.normalize('NFD', str(value or '')).lower().replace('đ', 'd')
    return re.sub('[^a-z0-9]', '', value)


source, export, output = map(Path, sys.argv[1:])
employees = json.loads(export.read_text())
sheet = openpyxl.load_workbook(source, data_only=True, read_only=True).active
rows, seen, problems = [], set(), []
for number, row in enumerate(sheet.values, 1):
    if row[6] not in ('Manager', 'Worker', 'Nghỉ việc'):
        continue
    code = str(row[2]).strip()
    key = code.lstrip('0') or '0'
    matches = [e for e in employees if str(e['barcode'] or '').lstrip('0') == key]
    if key in seen or len(matches) != 1 or norm(matches[0]['name']) != norm(row[1]):
        problems.append({'row': number, 'code': code, 'reason': 'Duplicate or identity mismatch'})
        continue
    seen.add(key)
    employee = matches[0]
    rows.append({'source_row': number, 'code': code, 'source_name': row[1],
                 'role': row[6], 'employee_id': employee['id'], 'before': employee})
assert not problems, problems
counts = dict(collections.Counter(r['role'] for r in rows))
assert counts == {'Manager': 151, 'Worker': 444, 'Nghỉ việc': 11}, counts
plan = {'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'source_file': source.name, 'sheet': sheet.title, 'counts': counts, 'rows': rows}
output.write_text(json.dumps(plan, ensure_ascii=False, indent=2))
print(json.dumps({'source_sha256': plan['source_sha256'], 'counts': counts,
                  'matched': len(rows), 'unmatched': len(problems)}))
