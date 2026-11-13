# -*- coding: utf-8 -*-
""""Time-clock punches" — the second mode of the attendance importer
(CLOCK-1 step 4, design §3.6).

The importer is EXTENDED, never forked: `mode='punches'` on the same three
stateless RPCs (parse → validate → commit). Punch files go into the LEDGER,
not straight into attendance, so they get the same dedup and the same pairing
as a machine's own punches (ledger rule 12) — this is the permanent fallback
when a machine cannot push.

THREE SHAPES ARE RECOGNISED BEFORE THE GENERIC TABLE

  * the machine's own log, `attlog.dat`: no header, tab separated, column 2 a
    `YYYY-MM-DD HH:MM:SS` → number, time, status, verify, work code. A file
    named `<serial>_attlog.dat` names its machine;
  * the attendance program's daily sheet: a header holding the employee
    number and "Lần 1" / "Lần 2" (also their legacy-font spellings "Maõ NV",
    "Laàn 1"), a date per row, first and last punch of the day →
    `source='mitaco_export'`, direction in / out;
  * anything else: a table with a number column and either one date-time
    column or a date and a time column (auto-mapped, the officer can remap).

Up to 20 000 rows in this mode (the days mode keeps its 2 000): one ledger
row per line is cheap, and a month of a factory's punches is ~50 000 lines —
the truncation is surfaced, never silent.
"""

import base64
import binascii
import csv
import io
import re
import unicodedata
from collections import Counter
from datetime import date, datetime, time, timedelta

from odoo import _, api, models
from odoo.exceptions import UserError

from ..models.clock_punch import dedup_key

try:
    import openpyxl
except ImportError:  # pragma: no cover
    openpyxl = None

PUNCH_MAX_ROWS = 20000
_HEADER_SCAN = 15                      # rows searched for a header line
_TARGETS = ('user_code', 'punch_at', 'punch_date', 'punch_time', 'direction',
            'device')
_ALIASES = {
    'user_code': ('ma nv', 'mao nv', 'user id', 'userid', 'enroll', 'badge',
                  'pin', 'code', 'employee', 'emp no', 'staff', 'id', 'so the',
                  'ma cham cong'),
    'punch_at': ('date time', 'datetime', 'date/time', 'punch time', 'checktime',
                 'check time', 'thoi gian', 'timestamp'),
    'punch_date': ('date', 'ngay', 'day'),
    'punch_time': ('time', 'gio', 'hour'),
    'direction': ('direction', 'in/out', 'in out', 'status', 'state', 'vao ra',
                  'trang thai'),
    'device': ('device', 'machine', 'terminal', 'serial', 'sn', 'may'),
}
_ZK_DIRECTION = {'0': 'in', '4': 'in', '1': 'out', '5': 'out'}
_ZK_STAMP = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$')
_ATTLOG_NAME = re.compile(r'^(.+?)_attlog\.dat$', re.I)
_MAX_NEW_DEVICES = 20


def _canon(text):
    """Header text without accents, case or the legacy-font letters the old
    Vietnamese encodings leave behind ("Maõ NV", "Laàn 1", "Ngaøy")."""
    s = unicodedata.normalize('NFD', str(text or ''))
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = s.replace('ø', '').replace('Ø', '').replace('đ', 'd').replace('Đ', 'd')
    s = re.sub(r'\s+', ' ', s).strip().lower()
    return s


def _mitaco_role(header):
    """'code' | 'date' | ('slot', n) | None for one daily-sheet header cell."""
    c = _canon(header)
    if c in ('ma nv', 'mao nv', 'ma nhan vien', 'mao nhan vien'):
        return 'code'
    if c in ('ngay', 'ngaoy', 'ngay cham'):
        return 'date'
    m = re.match(r'^la+n (\d)$', c)
    if m:
        return ('slot', int(m.group(1)))
    return None


class PbAttendanceImportWizard(models.TransientModel):
    _inherit = 'pb.attendance.import.wizard'

    # ------------------------------------------------------------- modes
    @api.model
    def import_modes(self):
        modes = super().import_modes()
        modes.append({
            'key': 'punches',
            'label': _("Time-clock punches"),
            'sub': _("Raw taps from a machine or its program — we pair them "
                     "for you"),
            'icon': 'scan',
        })
        return modes

    @api.model
    def _check_mode(self, mode):
        if mode == 'punches':
            return
        return super()._check_mode(mode)

    @api.model
    def parse(self, file_b64, filename, mode='days'):
        if mode != 'punches':
            return super().parse(file_b64, filename, mode=mode)
        self._require_officer()
        table = self._punch_table(file_b64, filename)
        out = {
            'mode': 'punches',
            'format': table['format'],
            'columns': table['columns'],
            'mapping': table['mapping'],
            'sample': table['sample'],
            'total': table['total'],
            'truncated': table['truncated'],
            'max_rows': PUNCH_MAX_ROWS,
            'ready': self._mapping_ready(table['format'], table['mapping']),
        }
        if out['ready']:
            out['preview'] = self._punch_preview(table, table['mapping'], filename)
        return out

    @api.model
    def validate(self, file_b64, filename, mapping, mode='days'):
        if mode != 'punches':
            return super().validate(file_b64, filename, mapping, mode=mode)
        self._require_officer()
        table = self._punch_table(file_b64, filename)
        mapping = self._clean_mapping(table, mapping)
        if not self._mapping_ready(table['format'], mapping):
            raise UserError(_(
                "Choose the column with the number on the machine, and either "
                "a date-and-time column or a date column and a time column."))
        return {'mode': 'punches',
                'preview': self._punch_preview(table, mapping, filename)}

    @api.model
    def commit(self, file_b64, filename, mapping, mode='days'):
        if mode != 'punches':
            return super().commit(file_b64, filename, mapping, mode=mode)
        self._require_officer()
        table = self._punch_table(file_b64, filename)
        mapping = self._clean_mapping(table, mapping)
        if not self._mapping_ready(table['format'], mapping):
            raise UserError(_(
                "Choose the column with the number on the machine, and either "
                "a date-and-time column or a date column and a time column."))
        company = self.env.company
        punches, bad = self._punches(table, mapping)
        devices, new_devices = self._resolve_devices(company, punches, filename,
                                                     create=True)
        vals_list = []
        for p in punches:
            device = devices[p['device_token']]
            vals_list.append({
                'device_id': device.id,
                'company_id': company.id,
                'source': p['source'],
                'user_code': p['user_code'],
                'punch_local': p['punch_local'],
                'direction_raw': p.get('direction_raw') or False,
                'direction': p.get('direction') or 'unknown',
                'verify_mode': p.get('verify_mode') or False,
                'work_code': p.get('work_code') or False,
            })
        res = self.env['pb.clock.punch']._ingest(vals_list)
        codes = sorted({p['user_code'] for p in punches})
        index = self.env['pb.clock.pairing']._code_index(company, codes)
        unknown = [c for c in codes if c not in index]
        triggered = self.env['pb.clock.pairing']._trigger_soon()
        return {
            'mode': 'punches',
            'created': res['created'],
            'duplicates': res['duplicates'],
            'bad': len(bad),
            'errors': bad[:20],
            'unknown_codes': unknown[:5],
            'unknown_count': len(unknown),
            'new_devices': new_devices,
            'total': table['total'],
            'truncated': table['truncated'],
            'max_rows': PUNCH_MAX_ROWS,
            'triggered': True,
            'trigger_sent': triggered,
            'message': self._commit_sentence(res['created'], len(unknown),
                                             res['duplicates']),
        }

    # ------------------------------------------------------------- reading
    @api.model
    def _raw_bytes(self, file_b64):
        try:
            return base64.b64decode(file_b64 or b'')
        except (binascii.Error, ValueError):
            raise UserError(_("The uploaded file could not be decoded."))

    @api.model
    def _text(self, raw):
        for enc in ('utf-8-sig', 'utf-16', 'cp1258', 'latin-1'):
            try:
                text = raw.decode(enc)
            except (UnicodeDecodeError, UnicodeError):
                continue
            if enc == 'utf-16' and '\x00' in text:
                continue
            return text
        return raw.decode('latin-1', errors='replace')

    @api.model
    def _grid(self, raw, filename):
        """Every row of the file as a list of cells (no header assumption)."""
        is_xlsx = (filename or '').lower().endswith(('.xlsx', '.xlsm')) \
            or raw[:2] == b'PK'
        if is_xlsx:
            if not openpyxl:
                raise UserError(_(
                    "Excel files need a library the server does not have — "
                    "please save the file as CSV and upload that."))
            try:
                wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True,
                                            data_only=True)
            except Exception:  # noqa: BLE001
                raise UserError(_("This Excel file could not be opened."))
            rows = []
            for r in wb.active.iter_rows(values_only=True):
                rows.append(list(r or ()))
                if len(rows) > PUNCH_MAX_ROWS + _HEADER_SCAN + 5:
                    break
            wb.close()
            return rows
        text = self._text(raw)
        lines = text.splitlines()
        head = '\n'.join(lines[:20])
        delim = ','
        try:
            delim = csv.Sniffer().sniff(head, delimiters=',;\t|').delimiter
        except csv.Error:
            if '\t' in head:
                delim = '\t'
            elif ';' in head:
                delim = ';'
        return [r for r in csv.reader(io.StringIO(text), delimiter=delim)]

    @api.model
    def _is_attlog(self, rows):
        seen = 0
        for r in rows[:10]:
            cells = [str(c).strip() for c in r if c is not None and str(c).strip()]
            if not cells:
                continue
            if len(cells) < 2 or not _ZK_STAMP.match(cells[1]):
                return False
            seen += 1
        return seen > 0

    @api.model
    def _punch_table(self, file_b64, filename):
        """{format, columns, mapping, rows (dicts), sample, total, truncated}."""
        raw = self._raw_bytes(file_b64)
        if not raw.strip():
            raise UserError(_("The file is empty."))
        grid = self._grid(raw, filename)
        grid = [r for r in grid
                if any(c is not None and str(c).strip() for c in r)]
        if not grid:
            raise UserError(_("The file has no rows."))

        if self._is_attlog(grid):
            cols = ['user_code', 'punch_at', 'status', 'verify', 'workcode']
            body = grid
            fmt = 'attlog'
            mapping = {'user_code': 'user_code', 'punch_at': 'punch_at',
                       'punch_date': '', 'punch_time': '',
                       'direction': 'status', 'device': ''}
        else:
            hdr_ix = self._mitaco_header(grid)
            if hdr_ix is not None:
                fmt = 'mitaco'
                header = grid[hdr_ix]
                cols = self._unique_cols(header)
                body = grid[hdr_ix + 1:]
                mapping = {'user_code': '', 'punch_at': '', 'punch_date': '',
                           'punch_time': '', 'direction': '', 'device': ''}
                for c, h in zip(cols, header):
                    role = _mitaco_role(h)
                    if role == 'code':
                        mapping['user_code'] = c
                    elif role == 'date':
                        mapping['punch_date'] = c
            else:
                fmt = 'table'
                hdr_ix = self._table_header(grid)
                header = grid[hdr_ix]
                cols = self._unique_cols(header)
                body = grid[hdr_ix + 1:]
                mapping = self._guess_punch_mapping(cols, body)

        truncated = len(body) > PUNCH_MAX_ROWS
        body = body[:PUNCH_MAX_ROWS]
        rows = [{cols[i]: (r[i] if i < len(r) else None) for i in range(len(cols))}
                for r in body]
        sample = [{'__i': i + 1, **{c: self._cell_text(rows[i].get(c)) for c in cols}}
                  for i in range(min(6, len(rows)))]
        return {'format': fmt, 'columns': cols, 'mapping': mapping,
                'rows': rows, 'sample': sample, 'total': len(rows),
                'truncated': truncated}

    @api.model
    def _unique_cols(self, header):
        cols, seen = [], Counter()
        for i, h in enumerate(header):
            name = self._cell_text(h).strip() or _("Column %s") % (i + 1)
            seen[name] += 1
            if seen[name] > 1:
                name = '%s (%s)' % (name, seen[name])
            cols.append(name)
        return cols

    @api.model
    def _mitaco_header(self, grid):
        for i, r in enumerate(grid[:_HEADER_SCAN]):
            roles = [_mitaco_role(c) for c in r]
            if 'code' in roles and ('slot', 1) in roles:
                return i
        return None

    @api.model
    def _table_header(self, grid):
        """The first row that looks like headers (mostly text, not times)."""
        for i, r in enumerate(grid[:_HEADER_SCAN]):
            cells = [c for c in r if c is not None and str(c).strip()]
            if len(cells) >= 2 and not any(
                    isinstance(c, (datetime, date, time)) for c in cells):
                if not any(_ZK_STAMP.match(str(c).strip()) for c in cells):
                    return i
        return 0

    @api.model
    def _cell_text(self, v):
        if v is None:
            return ''
        if isinstance(v, datetime):
            return v.strftime('%Y-%m-%d %H:%M:%S')
        if isinstance(v, date):
            return v.strftime('%Y-%m-%d')
        if isinstance(v, time):
            return v.strftime('%H:%M:%S')
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        return str(v)

    # ------------------------------------------------------------- mapping
    @api.model
    def _kind_of(self, values):
        """'datetime' | 'date' | 'time' | 'text' for a column's sample."""
        kinds = Counter()
        for v in values[:25]:
            if v in (None, ''):
                continue
            if isinstance(v, datetime):
                kinds['datetime' if (v.hour or v.minute or v.second) else 'date'] += 1
            elif isinstance(v, date):
                kinds['date'] += 1
            elif isinstance(v, time):
                kinds['time'] += 1
            else:
                s = str(v).strip()
                if self._parse_dt(s):
                    kinds['datetime'] += 1
                elif self._parse_date(s):
                    kinds['date'] += 1
                elif self._parse_time(s):
                    kinds['time'] += 1
                else:
                    kinds['text'] += 1
        return kinds.most_common(1)[0][0] if kinds else 'text'

    @api.model
    def _guess_punch_mapping(self, cols, body):
        mapping = {t: '' for t in _TARGETS}
        canon = {c: _canon(c) for c in cols}
        kinds = {c: self._kind_of([r[i] if i < len(r) else None for r in body])
                 for i, c in enumerate(cols)}

        def by_alias(target, want_kinds=None):
            for tok in _ALIASES[target]:
                for c in cols:
                    if c in mapping.values():
                        continue
                    if want_kinds and kinds[c] not in want_kinds:
                        continue
                    if canon[c] == tok or tok in canon[c].split() or (
                            len(tok) > 3 and tok in canon[c]):
                        return c
            return ''

        dt_cols = [c for c in cols if kinds[c] == 'datetime']
        mapping['user_code'] = by_alias('user_code', ('text',)) or by_alias('user_code')
        mapping['punch_at'] = by_alias('punch_at', ('datetime',)) or (
            dt_cols[0] if dt_cols and dt_cols[0] not in mapping.values() else '')
        if not mapping['punch_at']:
            mapping['punch_date'] = by_alias('punch_date', ('date', 'datetime'))
            mapping['punch_time'] = by_alias('punch_time', ('time', 'datetime'))
        mapping['direction'] = by_alias('direction', ('text',))
        mapping['device'] = by_alias('device', ('text',))
        return mapping

    @api.model
    def _clean_mapping(self, table, mapping):
        if table['format'] in ('attlog', 'mitaco'):
            # the shape decides; only a re-pointed number / date column counts
            base = dict(table['mapping'])
            for k in ('user_code', 'punch_date'):
                v = (mapping or {}).get(k)
                if v and v in table['columns']:
                    base[k] = v
            return base
        cols = set(table['columns'])
        return {t: ((mapping or {}).get(t) if (mapping or {}).get(t) in cols else '')
                for t in _TARGETS}

    @api.model
    def _mapping_ready(self, fmt, mapping):
        if not mapping.get('user_code'):
            return False
        if fmt == 'mitaco':
            return bool(mapping.get('punch_date'))
        return bool(mapping.get('punch_at')
                    or (mapping.get('punch_date') and mapping.get('punch_time')))

    # ------------------------------------------------------------- coercion
    @api.model
    def _parse_dt(self, s):
        s = str(s).strip().replace('T', ' ')
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%d/%m/%Y %H:%M:%S',
                    '%d/%m/%Y %H:%M', '%Y/%m/%d %H:%M:%S', '%Y/%m/%d %H:%M',
                    '%d-%m-%Y %H:%M:%S', '%d-%m-%Y %H:%M', '%m/%d/%Y %H:%M:%S'):
            try:
                return datetime.strptime(s[:19], fmt)
            except ValueError:
                continue
        return None

    @api.model
    def _as_date(self, v):
        if v in (None, ''):
            return None
        if isinstance(v, datetime):
            return v.date()
        if isinstance(v, date):
            return v
        s = str(v).strip()
        for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%Y/%m/%d', '%d.%m.%Y'):
            try:
                return datetime.strptime(s[:10], fmt).date()
            except ValueError:
                continue
        return None

    @api.model
    def _as_time(self, v):
        if v in (None, ''):
            return None
        if isinstance(v, datetime):
            return v.time()
        if isinstance(v, time):
            return v
        if isinstance(v, (int, float)) and 0 <= float(v) < 1:   # Excel fraction
            secs = int(round(float(v) * 86400))
            return time(secs // 3600 % 24, secs // 60 % 60, secs % 60)
        s = str(v).strip()
        if s in ('-', '—', '--'):
            return None
        if len(s) > 8 and (' ' in s or 'T' in s):
            s = s.replace('T', ' ').split(' ', 1)[1]
        for fmt in ('%H:%M:%S', '%H:%M', '%H.%M', '%Hh%M'):
            try:
                return datetime.strptime(s[:8], fmt).time()
            except ValueError:
                continue
        return None

    @api.model
    def _as_datetime(self, v):
        if v in (None, ''):
            return None
        if isinstance(v, datetime):
            return v
        return self._parse_dt(v)

    @api.model
    def _direction(self, raw):
        s = _canon(raw)
        if not s:
            return 'unknown'
        if s in _ZK_DIRECTION:
            return _ZK_DIRECTION[s]
        if s in ('in', 'i', 'check in', 'checkin', 'vao', 'c/in'):
            return 'in'
        if s in ('out', 'o', 'check out', 'checkout', 'ra', 'c/out'):
            return 'out'
        return 'unknown'

    @api.model
    def _code(self, v):
        return self._cell_text(v).strip()

    @api.model
    def _punches(self, table, mapping):
        """([punch dict], [bad row dict]) — nothing written."""
        fmt = table['format']
        out, bad = [], []
        slots = []
        if fmt == 'mitaco':
            for col in table['columns']:
                role = _mitaco_role(col.split(' (')[0])
                if isinstance(role, tuple):
                    slots.append((role[1], col))
            slots.sort()
        for i, row in enumerate(table['rows']):
            n = i + 1
            code = self._code(row.get(mapping['user_code']))
            if not code:
                bad.append({'index': n, 'employee': '—',
                            'reason': _("No number on this row")})
                continue
            if fmt == 'mitaco':
                day = self._as_date(row.get(mapping['punch_date']))
                if not day:
                    bad.append({'index': n, 'employee': code,
                                'reason': _("No date on this row")})
                    continue
                for slot, col in slots:
                    t = self._as_time(row.get(col))
                    if not t:
                        continue
                    out.append({'user_code': code,
                                'punch_local': datetime.combine(day, t).replace(microsecond=0),
                                'direction': 'in' if slot % 2 else 'out',
                                'direction_raw': col, 'source': 'mitaco_export',
                                'device_token': '', 'row': n})
                continue
            if mapping.get('punch_at'):
                stamp = self._as_datetime(row.get(mapping['punch_at']))
            else:
                d = self._as_date(row.get(mapping['punch_date']))
                t = self._as_time(row.get(mapping['punch_time']))
                stamp = datetime.combine(d, t) if d and t else None
            if not stamp:
                bad.append({'index': n, 'employee': code,
                            'reason': _("The date or time could not be read")})
                continue
            raw_dir = row.get(mapping['direction']) if mapping.get('direction') else None
            rec = {'user_code': code, 'punch_local': stamp.replace(microsecond=0),
                   'direction_raw': self._cell_text(raw_dir) if raw_dir not in (None, '') else '',
                   'direction': self._direction(raw_dir),
                   'source': 'upload', 'row': n,
                   'device_token': self._code(row.get(mapping['device']))
                   if mapping.get('device') else ''}
            if fmt == 'attlog':
                rec['verify_mode'] = self._code(row.get('verify'))
                rec['work_code'] = self._code(row.get('workcode'))
            out.append(rec)
        return out, bad

    # ------------------------------------------------------------- devices
    @api.model
    def _resolve_devices(self, company, punches, filename, create=False):
        """{device_token: device}. '' = the company's upload device (or the
        machine a `<serial>_attlog.dat` file name names)."""
        Device = self.env['pb.clock.device'].sudo()
        upload = Device._get_upload_device(company) if create else \
            Device.with_context(active_test=False).search(
                [('company_id', '=', company.id), ('kind', '=', 'upload')], limit=1)
        default = upload
        m = _ATTLOG_NAME.match((filename or '').strip())
        if m:
            token = m.group(1).strip()
            found = Device._find_terminal(company, token)
            if not found and create:
                found = Device.create({'name': token, 'serial': token,
                                       'kind': 'terminal', 'company_id': company.id})
            default = found or default
        out = {'': default}
        new = []
        tokens = sorted({p['device_token'] for p in punches if p['device_token']})
        for token in tokens:
            found = Device._find_terminal(company, token)
            if not found and create and len(new) < _MAX_NEW_DEVICES:
                found = Device.create({'name': token, 'kind': 'terminal',
                                       'company_id': company.id})
                new.append(token)
            out[token] = found or default
        return out, new

    # ------------------------------------------------------------- preview
    @api.model
    def _punch_preview(self, table, mapping, filename):
        """What the file holds — counts, people, days, unknown numbers,
        repeats inside the file, already on record. Writes nothing."""
        company = self.env.company
        punches, bad = self._punches(table, mapping)
        devices, _new = self._resolve_devices(company, punches, filename,
                                              create=False)
        codes = sorted({p['user_code'] for p in punches})
        index = self.env['pb.clock.pairing']._code_index(company, codes)
        unknown = [c for c in codes if c not in index]
        unknown_rows = Counter(p['user_code'] for p in punches
                               if p['user_code'] not in index)

        keys = []
        for p in punches:
            dev = devices.get(p['device_token']) or devices.get('')
            keys.append(dedup_key(company.id, dev.serial if dev else False,
                                  p['user_code'], p['punch_local']))
        repeats = len(keys) - len(set(keys))
        on_record = 0
        uniq = list(set(keys))
        Punch = self.env['pb.clock.punch'].sudo()
        for i in range(0, len(uniq), 5000):
            on_record += Punch.search_count([('dedup_key', 'in', uniq[i:i + 5000])])

        per_day = Counter(p['punch_local'].date() for p in punches)
        days = sorted(per_day)
        spark = []
        if days:
            last = days[-1]
            for k in range(6, -1, -1):
                d = last - timedelta(days=k)
                spark.append({'date': d.isoformat(), 'label': d.strftime('%a %d'),
                              'n': per_day.get(d, 0)})
        return {
            'format': table['format'],
            'punches': len(punches),
            'people': len({index[c].id for c in codes if c in index}),
            'numbers': len(codes),
            'days': len(days),
            'date_from': days[0].isoformat() if days else '',
            'date_to': days[-1].isoformat() if days else '',
            'unknown_count': len(unknown),
            'unknown': [{'code': c, 'punches': unknown_rows[c]}
                        for c in sorted(unknown, key=lambda c: -unknown_rows[c])[:5]],
            'repeats': repeats,
            'on_record': on_record,
            'new': max(len(uniq) - on_record, 0),
            'bad': len(bad),
            'bad_rows': bad[:10],
            'spark': spark,
            'spark_max': max([s['n'] for s in spark] or [0]),
            'truncated': table['truncated'],
            'max_rows': PUNCH_MAX_ROWS,
        }

    @api.model
    def _commit_sentence(self, created, unknown, duplicates):
        parts = [(_("1 punch added") if created == 1
                  else _("%s punches added") % '{:,}'.format(created))]
        if unknown:
            parts.append(_("1 number not matched") if unknown == 1
                         else _("%s numbers not matched") % unknown)
        if duplicates and not created:
            parts.append(_("all already on record"))
        elif duplicates:
            parts.append(_("%s already on record") % '{:,}'.format(duplicates))
        if created:
            parts.append(_("pairing runs in the background"))
        return ' · '.join(parts)
