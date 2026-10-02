# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""pb.attendance.import.wizard — bulk CSV/XLSX punch import (Phase G §3).

Upload → auto-mapped columns → dry-run validation → commit under PER-ROW
savepoints. The three RPCs are STATELESS: the file is re-parsed on each call
(the base64 travels with the request), so nothing mutable is stashed on the
recordset (Odoo 19 recordsets are ``__slots__`` — C6). Nothing is written during
``validate``; on ``commit`` each valid row is created in its own savepoint so one
bad row never rolls back the batch (safety rail 6). Imported rows carry
``pb_entry_source='import'``; the young-worker daily-cap constraint fires
naturally on create and is surfaced per row, never as a batch-killing traceback.

Times are LOCAL to the employee's working-schedule tz and converted to UTC.
"""

import base64
import binascii
import csv
import io
from datetime import datetime, time, timedelta

from pytz import timezone, utc, UnknownTimeZoneError

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

try:
    import openpyxl
except ImportError:  # degrade: CSV still works, XLSX reports a clear error
    openpyxl = None

# canonical target columns + the header tokens we auto-map them from
_TARGETS = ('employee', 'date', 'check_in', 'check_out')
_GUESS = {
    'employee': ('employee', 'name', 'code', 'badge', 'staff', 'nhan vien', 'ma nv'),
    'date': ('date', 'day', 'ngay'),
    'check_in': ('check in', 'check-in', 'checkin', 'in', 'gio vao', 'start'),
    'check_out': ('check out', 'check-out', 'checkout', 'out', 'gio ra', 'end'),
}
_MAX_ROWS = 2000  # a bulk import is bounded; beyond this, split the file


class PbAttendanceImportWizard(models.TransientModel):
    _name = 'pb.attendance.import.wizard'
    _description = 'Attendance Bulk Import'

    import_file = fields.Binary(string='File')
    filename = fields.Char(string='Filename')

    # ------------------------------------------------------------- access
    @api.model
    def _require_officer(self):
        u = self.env.user
        if not (u.has_group('hr_attendance.group_hr_attendance_officer')
                or u.has_group('base.group_system')):
            raise AccessError(_(
                "Importing attendance is restricted to attendance officers."))

    # ------------------------------------------------------------- tz
    @api.model
    def _emp_tz(self, emp):
        cal = emp.resource_calendar_id or emp.company_id.resource_calendar_id
        name = ((cal.tz if cal else False) or emp.tz or self.env.user.tz or 'UTC')
        try:
            timezone(name)
        except UnknownTimeZoneError:
            name = 'UTC'
        return name

    def _to_utc(self, emp, d, t):
        tz = timezone(self._emp_tz(emp))
        return tz.localize(datetime.combine(d, t)).astimezone(utc).replace(tzinfo=None)

    # ------------------------------------------------------------- parsing
    @api.model
    def _decode(self, file_b64):
        try:
            return base64.b64decode(file_b64 or b'')
        except (binascii.Error, ValueError):
            raise UserError(_("The uploaded file could not be decoded."))

    @api.model
    def _read_rows(self, file_b64, filename):
        # returns (cols, rows, truncated) — truncation is SURFACED, never
        # silent (review G-L15; the old cap also kept 2001 rows, off by one)
        truncated = False
        """→ (columns:list[str], rows:list[dict]). XLSX via openpyxl, else CSV."""
        raw = self._decode(file_b64)
        is_xlsx = (filename or '').lower().endswith(('.xlsx', '.xlsm')) \
            or raw[:2] == b'PK'
        if is_xlsx:
            if not openpyxl:
                raise UserError(_(
                    "XLSX import needs the openpyxl library on the server — "
                    "please upload a CSV instead."))
            wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
            ws = wb.active
            it = ws.iter_rows(values_only=True)
            try:
                header = next(it)
            except StopIteration:
                return [], [], False
            cols = [str(c).strip() if c is not None else '' for c in header]
            rows = []
            for r in it:
                if r is None or all(c is None for c in r):
                    continue
                if len(rows) >= _MAX_ROWS:
                    truncated = True
                    break
                rows.append({cols[i]: r[i] if i < len(r) else None
                             for i in range(len(cols))})
            wb.close()
            return cols, rows, truncated
        # CSV — sniff encoding gently
        try:
            text = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            text = raw.decode('latin-1')
        reader = csv.reader(io.StringIO(text))
        all_rows = list(reader)
        if not all_rows:
            return [], [], False
        cols = [str(c).strip() for c in all_rows[0]]
        rows = []
        for r in all_rows[1:]:
            if not any((c or '').strip() for c in r):
                continue
            if len(rows) >= _MAX_ROWS:
                truncated = True
                break
            rows.append({cols[i]: (r[i] if i < len(r) else None)
                         for i in range(len(cols))})
        return cols, rows, truncated

    @api.model
    def _guess_mapping(self, cols):
        mapping = {}
        lower = {c: (c or '').strip().lower() for c in cols}
        for target, tokens in _GUESS.items():
            for c in cols:
                lc = lower[c]
                if lc and any(tok in lc for tok in tokens):
                    mapping[target] = c
                    break
            mapping.setdefault(target, '')
        return mapping

    # ------------------------------------------------------------- coercion
    @api.model
    def _parse_date(self, val):
        if val in (None, ''):
            return None
        if isinstance(val, datetime):
            return val.date()
        if hasattr(val, 'year') and hasattr(val, 'month') and not isinstance(val, str):
            return val  # a date
        s = str(val).strip()
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%Y/%m/%d'):
            try:
                return datetime.strptime(s[:10], fmt).date()
            except ValueError:
                continue
        return None

    @api.model
    def _parse_time(self, val):
        if val in (None, ''):
            return None
        if isinstance(val, datetime):
            return val.time()
        if isinstance(val, time):
            return val
        s = str(val).strip()
        # a full datetime cell → take its time part
        if len(s) > 8 and (' ' in s or 'T' in s):
            s = s.replace('T', ' ').split(' ', 1)[1]
        for fmt in ('%H:%M:%S', '%H:%M', '%H.%M'):
            try:
                return datetime.strptime(s[:8], fmt).time()
            except ValueError:
                continue
        return None

    # ------------------------------------------------------------- employees
    @api.model
    def _employee_index(self):
        """Company-scoped {barcode/name → employee} maps (barcode is HR-scoped
        so read sudo — access is already gated by _require_officer)."""
        co_ids = self.env.companies.ids or [self.env.company.id]
        emps = self.env['hr.employee'].sudo().search(
            [('active', '=', True), ('company_id', 'in', co_ids)])
        by_code, by_name = {}, {}
        for e in emps:
            if e.barcode:
                by_code[str(e.barcode).strip()] = e
            if e.name:
                by_name[e.name.strip().lower()] = e
        return by_code, by_name

    def _resolve_employee(self, token, by_code, by_name):
        if token in (None, ''):
            return None
        s = str(token).strip()
        return by_code.get(s) or by_name.get(s.lower())

    # ------------------------------------------------------------- RPCs
    @api.model
    def parse(self, file_b64, filename):
        """Preview: columns, an auto-guessed mapping and a few sample rows."""
        self._require_officer()
        cols, rows, truncated = self._read_rows(file_b64, filename)
        if not cols:
            raise UserError(_("The file has no header row."))
        sample = [{'__i': i + 1, **{c: ('' if rows[i].get(c) is None
                                        else str(rows[i].get(c))) for c in cols}}
                  for i in range(min(6, len(rows)))]
        return {
            'columns': cols,
            'mapping': self._guess_mapping(cols),
            'sample': sample,
            'total': len(rows),
            'truncated': truncated,
            'max_rows': _MAX_ROWS,
        }

    @api.model
    def _prepare(self, file_b64, filename, mapping):
        """Shared row resolution for validate + commit. Returns a list of
        per-row dicts with resolved employee / datetimes / errors (no writes)."""
        cols, rows, truncated = self._read_rows(file_b64, filename)
        mp = {k: (mapping or {}).get(k) for k in _TARGETS}
        if not mp.get('employee') or not mp.get('date') or not mp.get('check_in'):
            raise UserError(_(
                "Map at least the Employee, Date and Check-In columns."))
        by_code, by_name = self._employee_index()

        prepared = []
        for i, row in enumerate(rows):
            rec = {'index': i + 1, 'errors': [], 'employee': None,
                   'raw_employee': '', 'check_in': None, 'check_out': None,
                   'date': None}
            emp_token = row.get(mp['employee'])
            rec['raw_employee'] = '' if emp_token is None else str(emp_token).strip()
            emp = self._resolve_employee(emp_token, by_code, by_name)
            d = self._parse_date(row.get(mp['date']))
            t_in = self._parse_time(row.get(mp['check_in']))
            raw_out = row.get(mp['check_out']) if mp.get('check_out') else None
            t_out = self._parse_time(raw_out) if mp.get('check_out') else None
            if not emp:
                rec['errors'].append(_("Unknown employee"))
            if not d:
                rec['errors'].append(_("Bad or missing date"))
            if not t_in:
                rec['errors'].append(_("Bad or missing check-in time"))
            if raw_out not in (None, '') and str(raw_out).strip() and not t_out:
                # a malformed check-out must flag, not silently import an
                # open punch (review G-L10)
                rec['errors'].append(_("Bad check-out time"))
            if emp and d and t_in:
                rec['employee'] = emp
                rec['date'] = d
                rec['check_in'] = self._to_utc(emp, d, t_in)
                if t_out:
                    ci = rec['check_in']
                    co = self._to_utc(emp, d, t_out)
                    if co <= ci:  # crosses midnight → next calendar day
                        co += timedelta(days=1)
                    rec['check_out'] = co
            prepared.append(rec)
        return prepared, truncated

    @api.model
    def validate(self, file_b64, filename, mapping):
        """Dry-run verdicts — NEVER writes. Flags unknown employee, malformed
        time, overlap with an existing punch, and young-worker cap breach."""
        self._require_officer()
        prepared, truncated = self._prepare(file_b64, filename, mapping)

        # batch existing punches over the file's employee/date span (overlap)
        emp_ids = list({r['employee'].id for r in prepared if r['employee']})
        dates = [r['date'] for r in prepared if r['date']]
        existing = self.env['hr.attendance']
        if emp_ids and dates:
            existing = self.env['hr.attendance'].sudo().search([
                ('employee_id', 'in', emp_ids),
                ('check_in', '>=', datetime.combine(min(dates) - timedelta(days=1), time.min)),
                ('check_in', '<=', datetime.combine(max(dates) + timedelta(days=1), time.max)),
            ])
        by_emp = {}
        for a in existing:
            by_emp.setdefault(a.employee_id.id, []).append(a)

        YW = self.env['pb.young.worker'] if 'pb.young.worker' in self.env else None
        verdicts, valid = [], 0
        for r in prepared:
            errors = list(r['errors'])
            if r['employee'] and r['check_in']:
                if self._overlaps(r, by_emp.get(r['employee'].id, [])):
                    errors.append(_("Overlaps an existing punch"))
                if YW is not None and not errors:
                    hrs = self._row_hours(r)
                    res = YW.check_day_hours(r['employee'], r['date'], extra_hours=hrs)
                    if not res['ok']:
                        errors.append(_(
                            "Exceeds the under-18 daily cap (%(cap).0f h)",
                            cap=res['cap']))
            ok = not errors
            valid += 1 if ok else 0
            verdicts.append({
                'index': r['index'],
                'employee': r['employee'].name if r['employee'] else r['raw_employee'] or '—',
                'date': r['date'].isoformat() if r['date'] else '',
                'ok': ok,
                'errors': errors,
            })
        return {'rows': verdicts, 'summary': {
            'total': len(verdicts), 'valid': valid,
            'invalid': len(verdicts) - valid,
            'truncated': truncated, 'max_rows': _MAX_ROWS}}

    @api.model
    def commit(self, file_b64, filename, mapping):
        """Write the valid rows — each in its OWN savepoint, so a single bad row
        never poisons the batch. Overlapping / cap-breaching rows are skipped."""
        self._require_officer()
        prepared, truncated = self._prepare(file_b64, filename, mapping)
        emp_ids = list({r['employee'].id for r in prepared if r['employee']})
        dates = [r['date'] for r in prepared if r['date']]
        existing = self.env['hr.attendance']
        if emp_ids and dates:
            existing = self.env['hr.attendance'].sudo().search([
                ('employee_id', 'in', emp_ids),
                ('check_in', '>=', datetime.combine(min(dates) - timedelta(days=1), time.min)),
                ('check_in', '<=', datetime.combine(max(dates) + timedelta(days=1), time.max)),
            ])
        by_emp = {}
        for a in existing:
            by_emp.setdefault(a.employee_id.id, []).append(a)

        Att = self.env['hr.attendance'].sudo()
        created, skipped, errors = 0, 0, []
        for r in prepared:
            if r['errors'] or not r['employee'] or not r['check_in']:
                skipped += 1
                errors.append({'index': r['index'],
                               'employee': r['raw_employee'] or '—',
                               'reason': ' · '.join(r['errors']) or _("Incomplete row")})
                continue
            if self._overlaps(r, by_emp.get(r['employee'].id, [])):
                skipped += 1
                errors.append({'index': r['index'], 'employee': r['employee'].name,
                               'reason': _("Overlaps an existing punch")})
                continue
            try:
                with self.env.cr.savepoint():
                    new = Att.create({
                        'employee_id': r['employee'].id,
                        'check_in': r['check_in'],
                        'check_out': r['check_out'] or False,
                        'pb_entry_source': 'import',
                    })
                created += 1
                by_emp.setdefault(r['employee'].id, []).append(new)  # block dupes within the file
            except Exception as e:
                skipped += 1
                reason = (getattr(e, 'args', None) and e.args[0]) or str(e)
                errors.append({'index': r['index'], 'employee': r['employee'].name,
                               'reason': str(reason)})
        return {'created': created, 'skipped': skipped, 'errors': errors,
                'total': len(prepared),
                'truncated': truncated, 'max_rows': _MAX_ROWS}

    # ------------------------------------------------------------- helpers
    @api.model
    def _row_hours(self, r):
        if r['check_in'] and r['check_out']:
            return (r['check_out'] - r['check_in']).total_seconds() / 3600.0
        return 0.0

    @api.model
    def _overlaps(self, r, existing):
        ci = r['check_in']
        co = r['check_out'] or ci
        for a in existing:
            aci = a.check_in
            aco = a.check_out or a.check_in
            if aci and ci <= aco and aci <= co:
                return True
        return False
