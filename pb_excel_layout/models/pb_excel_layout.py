# -*- coding: utf-8 -*-
"""Fill my own Excel layout (DOCSTUDIO X, study line 920).

A finance team uploads its own workbook ONCE — a board pack with headings,
formulas, charts, maybe macros — picks the sheet and the cell where the
figures start, and from then on gets that same file back with fresh figures.

Doctrine
--------
* **The source decides who sees what (rail R2).** A layout is attached to a
  record of any model that implements contract C1 (`_pbxl_table`, ledger).
  Every call checks, as the CALLING user, that the source may be read and
  passes the source's own gate (`_pbxl_require` when it has one); the table
  is then built by the source as that same user. A layout never widens what
  anybody may see; scheduled sends rebuild it per recipient.
* **Layouts are private unless shared.** The record rule lets owners reach
  only their own layouts through the ORM. A layout someone shared is reached
  only through this facade, after the source check, so its file (which may
  hold last month's figures) never leaks to someone who cannot open the
  report.
* **The customer's file is never rewritten by a library** (ledger DS-2):
  `xlsx_fill` edits one sheet's XML inside the zip. No macro or formula is
  ever run here (rail R4).
* **A layout never breaks a download.** When filling fails the reader gets
  the standard Excel with the reason (step 9, rail R5).
"""
import base64
import logging
from datetime import date, datetime

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from . import xlsx_fill
from .words import (coach_words, error_words, macro_words, note_words,
                    product_label)
from .xlsx_fill import LayoutError

_logger = logging.getLogger(__name__)

NAME_MAX = 80
LAYOUT_CAP = 20            # layouts per owner; said in the refusal
ROW_CAP = 50000            # rows one fill writes; the cut is said, not silent
B64_MAX = 14 * 1024 * 1024  # a 10 MB file is ~13.4 MB in base64
TYPES = ('text', 'number', 'money', 'date', 'datetime', 'bool')


class PbExcelLayout(models.Model):
    _name = 'pb.excel.layout'
    _description = 'Excel layout'
    _order = 'name, id'

    name = fields.Char(required=True)
    user_id = fields.Many2one('res.users', string='Set up by', required=True,
                              index=True, ondelete='cascade',
                              default=lambda self: self.env.user)
    shared = fields.Boolean(string='Everyone who can open the report')
    source_model = fields.Char(string='Report kind', required=True,
                               index=True)
    source_id = fields.Integer(string='Report', required=True, index=True)
    file = fields.Binary(string='Excel file', attachment=True, required=True)
    file_name = fields.Char(string='File name')
    sheet_name = fields.Char(string='Sheet')
    start_cell = fields.Char(string='Start cell', default='A1')
    write_headers = fields.Boolean(string='Write the column headings',
                                   default=True)
    has_macros = fields.Boolean(string='Contains macros')
    sheet_ok = fields.Boolean(string='Sheet found in the file', default=True)
    last_used = fields.Datetime(string='Last used')
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company)

    # ------------------------------------------------------------ helpers
    @api.model
    def _pbxl_clean_name(self, name):
        name = ' '.join(str(name or '').split())[:NAME_MAX]
        if not name:
            raise UserError(_("Give the layout a name."))
        return name

    def _pbxl_raw(self):
        self.ensure_one()
        value = self.sudo().with_context(bin_size=False).file
        return base64.b64decode(value) if value else b''

    def _pbxl_ext(self):
        self.ensure_one()
        name = (self.file_name or '').lower()
        return '.xlsm' if name.endswith('.xlsm') or self.has_macros else '.xlsx'

    def _pbxl_filename(self):
        """`payobook_board_pack_2026-11-22.xlsm` — the tenant's own product
        name, never a hard-coded brand (R7)."""
        self.ensure_one()
        word = ''.join(c if c.isalnum() else '_' for c in (self.name or '').lower())
        word = '_'.join(p for p in word.split('_') if p)[:40] or 'layout'
        return '%s_%s_%s%s' % (product_label(self.env).lower(), word,
                               fields.Date.context_today(self).isoformat(),
                               self._pbxl_ext())

    def _pbxl_mimetype(self):
        return xlsx_fill.mimetype(self._pbxl_ext())

    def _pbxl_fill_with(self, table):
        """(bytes, notes) — this layout's file filled with `table`."""
        self.ensure_one()
        if not self.sheet_ok:
            raise LayoutError('sheet_missing', sheet=self.sheet_name or '')
        return xlsx_fill.fill(self._pbxl_raw(), self.sheet_name or '',
                              self.start_cell or 'A1', bool(self.write_headers),
                              table, file_name=self.file_name or '')

    def _pbxl_problem(self):
        self.ensure_one()
        if not self.sheet_ok:
            return error_words(self.env, 'sheet_missing',
                               {'sheet': self.sheet_name or ''})
        return ''

    def _pbxl_payload(self):
        self.ensure_one()
        uid = self.env.uid
        mine = self.user_id.id == uid
        used = ''
        if self.last_used:
            used = fields.Datetime.context_timestamp(
                self, self.last_used).strftime('%Y-%m-%d %H:%M')
        return {
            'id': self.id,
            'name': self.name,
            'file_name': self.file_name or '',
            'sheet': self.sheet_name or '',
            'start': self.start_cell or 'A1',
            'headers': bool(self.write_headers),
            'shared': bool(self.shared),
            'mine': mine,
            'owner': '' if mine else (self.user_id.sudo().name or ''),
            'macros': bool(self.has_macros),
            'ext': self._pbxl_ext(),
            'sheet_ok': bool(self.sheet_ok),
            'problem': self._pbxl_problem(),
            'used': used,
        }


class PbExcelLayoutBoard(models.AbstractModel):
    """The one door of the set-up dialog and the button (contract C2)."""
    _name = 'pb.excel.layout.board'
    _description = 'Excel layouts — set-up and download'

    # ------------------------------------------------------------- gates
    @api.model
    def _pbxl_source(self, source_model, source_id):
        """The source record, after the caller is proven to be allowed to
        open it. Refuses any model that does not implement contract C1."""
        if not self.env.user._is_internal():
            raise AccessError(_("Only staff logins can use Excel layouts."))
        name = str(source_model or '')
        if not name or name not in self.env:
            raise UserError(error_words(self.env, 'no_source'))
        Model = self.env[name]
        if Model._abstract or Model._transient or \
                not callable(getattr(Model, '_pbxl_table', None)):
            raise UserError(error_words(self.env, 'no_source'))
        try:
            rec = Model.browse(int(source_id or 0)).exists()
        except (TypeError, ValueError):
            rec = Model
        if not rec:
            raise UserError(error_words(self.env, 'no_source'))
        gate = getattr(rec, '_pbxl_require', None)
        if callable(gate):
            gate()
        rec.check_access('read')
        return rec

    @api.model
    def _pbxl_layout(self, layout_id, write=False):
        """(layout as sudo, source) — readable when it is yours or shared,
        changeable only when it is yours (settings admins may tidy any)."""
        try:
            layout = self.env['pb.excel.layout'].sudo().browse(
                int(layout_id or 0)).exists()
        except (TypeError, ValueError):
            layout = self.env['pb.excel.layout']
        if not layout:
            raise UserError(error_words(self.env, 'no_layout'))
        admin = self.env.user.has_group('base.group_system')
        mine = layout.user_id.id == self.env.uid
        if write and not (mine or admin):
            raise AccessError(_("Only the person who set up this layout can "
                                "change it."))
        if not (mine or layout.shared or admin):
            raise AccessError(error_words(self.env, 'no_layout'))
        source = self._pbxl_source(layout.source_model, layout.source_id)
        return layout, source

    # ------------------------------------------------------------ tables
    @api.model
    def _pbxl_clean_table(self, table):
        """Contract C1, checked: the shape a source hands over, made safe."""
        table = table if isinstance(table, dict) else {}
        columns = []
        for j, col in enumerate(table.get('columns') or [], start=1):
            col = col if isinstance(col, dict) else {}
            kind = col.get('type') if col.get('type') in TYPES else 'text'
            columns.append({'key': str(col.get('key') or 'c%d' % j),
                            'label': str(col.get('label') or ''),
                            'type': kind})
        rows = [list(r) if isinstance(r, (list, tuple)) else [r]
                for r in (table.get('rows') or [])]
        truncated = bool(table.get('truncated'))
        note = str(table.get('note') or '')
        if len(rows) > ROW_CAP:
            rows = rows[:ROW_CAP]
            truncated = True
            note = (note + ' ' if note else '') + _(
                "Only the first %s rows are in the file.", ROW_CAP)
        return {'title': str(table.get('title') or ''), 'columns': columns,
                'rows': rows, 'truncated': truncated, 'note': note}

    @api.model
    def _pbxl_table(self, source):
        return self._pbxl_clean_table(source._pbxl_table())

    @api.model
    def _pbxl_shape(self, table):
        """What the live outline on the grid needs: the size and headings."""
        return {
            'cols': len(table['columns']),
            'rows': len(table['rows']),
            'labels': xlsx_fill.headings(table),
            'title': table['title'],
            'truncated': table['truncated'],
            'note': table['note'],
        }

    @api.model
    def _pbxl_decode(self, file_b64):
        if not file_b64 or not isinstance(file_b64, str):
            raise LayoutError('not_excel')
        if len(file_b64) > B64_MAX:
            raise LayoutError('too_big')
        if ',' in file_b64[:100] and file_b64.startswith('data:'):
            file_b64 = file_b64.split(',', 1)[1]
        try:
            return base64.b64decode(file_b64, validate=True)
        except (ValueError, TypeError) as err:
            raise LayoutError('not_excel') from err

    @api.model
    def _pbxl_fail(self, err):
        """A refusal as the screen shows it: never a traceback."""
        if isinstance(err, LayoutError):
            return {'ok': False, 'code': err.code,
                    'msg': error_words(self.env, err.code, err.params)}
        _logger.exception('pb_excel_layout: unexpected failure')
        return {'ok': False, 'code': 'unreadable',
                'msg': error_words(self.env, 'unreadable')}

    @api.model
    def _pbxl_file_answer(self, raw, file_name, only=None):
        desc = xlsx_fill.describe(raw, file_name, only=only)
        desc.update({
            'ok': True,
            'file_name': file_name or '',
            'size': len(raw),
            'macro_note': macro_words(self.env) if desc['has_macros'] else '',
            'coach': coach_words(self.env),
        })
        return desc

    @api.model
    def _pbxl_check_place(self, raw, file_name, sheet, start, headers, table):
        """Refuse a sheet / start cell that cannot take this result: a chart
        sheet, a cell that is not one, merged cells in the way (§5 states)."""
        pkg = xlsx_fill.Package(raw, file_name)
        entry = pkg.sheet(sheet)
        c0, r0 = xlsx_fill.split_cell(start)
        ncols = max(1, len(table['columns']))
        if c0 + ncols - 1 > xlsx_fill.MAX_COL:
            raise LayoutError('too_wide', cell=start)
        xlsx_fill.area_problems(pkg, entry['part'], c0, r0, c0 + ncols - 1)
        return pkg

    @api.model
    def _pbxl_plain_xlsx(self, table):
        """The standard Excel for any source: a title, the headings and the
        rows. Text is always text, never a formula (R4)."""
        import io
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
        wb = Workbook()
        ws = wb.active
        ws.title = (''.join(c for c in (table['title'] or 'Report')
                            if c not in '[]:*?/\\')[:31].strip() or 'Sheet1')

        def put(r, c, value):
            if isinstance(value, str):
                value = xlsx_fill._ILLEGAL_XML.sub('', value)[:xlsx_fill.TEXT_MAX]
            cell = ws.cell(r, c, value)
            if isinstance(value, str) and value[:1] in ('=', '+', '-', '@'):
                cell.data_type = 's'
            return cell

        put(1, 1, table['title']).font = Font(bold=True, size=14,
                                              color='241F52')
        for j, label in enumerate(xlsx_fill.headings(table), start=1):
            cell = put(3, j, label)
            cell.font = Font(bold=True, color='241F52')
            cell.fill = PatternFill('solid', fgColor='EDEAF8')
        for i, row in enumerate(table['rows'], start=4):
            for j, value in enumerate(row, start=1):
                if isinstance(value, datetime) and value.tzinfo:
                    value = value.replace(tzinfo=None)
                cell = put(i, j, value)
                if isinstance(value, (date, datetime)):
                    cell.number_format = 'yyyy-mm-dd'
        if table['note']:
            put(len(table['rows']) + 5, 1, table['note'])
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    @api.model
    def _pbxl_standard(self, source, table):
        """(filename, bytes, mimetype) — the source's own Excel when it has
        one (`_pbxl_standard`), else the plain one above."""
        own = getattr(source, '_pbxl_standard', None)
        if callable(own):
            try:
                name, data = own()
                return name, data, xlsx_fill.mimetype('.xlsx')
            except Exception:                              # noqa: BLE001
                _logger.exception('pb_excel_layout: the standard Excel of '
                                  '%s,%s failed', source._name, source.id)
        word = ''.join(c if c.isalnum() else '_' for c in
                       (table['title'] or 'report').lower())
        word = '_'.join(p for p in word.split('_') if p)[:40] or 'report'
        name = '%s_%s_%s.xlsx' % (product_label(self.env).lower(), word,
                                  fields.Date.context_today(self).isoformat())
        return name, self._pbxl_plain_xlsx(table), xlsx_fill.mimetype('.xlsx')

    # ------------------------------------------------------------ the API
    @api.model
    def list_for(self, source_model, source_id):
        """Your layouts and the shared ones for this report."""
        source = self._pbxl_source(source_model, source_id)
        Layout = self.env['pb.excel.layout'].sudo()
        uid = self.env.uid
        found = Layout.search([('source_model', '=', source._name),
                               ('source_id', '=', source.id),
                               '|', ('user_id', '=', uid),
                               ('shared', '=', True)])
        mine = found.filtered(lambda l: l.user_id.id == uid)
        others = found - mine
        own_count = Layout.search_count([('user_id', '=', uid)])
        return {
            'layouts': [l._pbxl_payload() for l in mine + others],
            'cap': LAYOUT_CAP,
            'can_add': own_count < LAYOUT_CAP,
            'coach': coach_words(self.env),
        }

    @api.model
    def inspect(self, file_b64, file_name='', source_model=False,
                source_id=False):
        """The uploaded file: its sheets, a 20 x 12 grid of each, merged
        ranges, Excel tables, a suggested start cell; with a source, the size
        and headings of the current result for the live outline."""
        table = None
        if source_model:
            table = self._pbxl_table(self._pbxl_source(source_model, source_id))
        elif not self.env.user._is_internal():
            raise AccessError(_("Only staff logins can use Excel layouts."))
        try:
            raw = self._pbxl_decode(file_b64)
            out = self._pbxl_file_answer(raw, file_name)
        except Exception as err:                           # noqa: BLE001
            return self._pbxl_fail(err)
        if table is not None:
            out['table'] = self._pbxl_shape(table)
        return out

    @api.model
    def peek(self, file_b64, sheet, file_name=''):
        """One sheet of the uploaded file, as `inspect` describes it."""
        if not self.env.user._is_internal():
            raise AccessError(_("Only staff logins can use Excel layouts."))
        try:
            raw = self._pbxl_decode(file_b64)
            out = self._pbxl_file_answer(raw, file_name, only=sheet)
        except Exception as err:                           # noqa: BLE001
            return self._pbxl_fail(err)
        out['sheet'] = next((s for s in out['sheets'] if s['name'] == sheet),
                            None)
        if out['sheet'] is None:
            return self._pbxl_fail(LayoutError('sheet_missing', sheet=sheet))
        return out

    @api.model
    def try_it(self, file_b64, sheet, start_cell, write_headers, source_model,
               source_id, file_name='', layout_id=False):
        """The customer's own file, filled with the current result, NOT
        saved. With `layout_id` and no file, the saved layout's file."""
        source = self._pbxl_source(source_model, source_id)
        table = self._pbxl_table(source)
        try:
            if file_b64:
                raw = self._pbxl_decode(file_b64)
            elif layout_id:
                layout, _src = self._pbxl_layout(layout_id)
                if (layout.source_model, layout.source_id) != (
                        source._name, source.id):
                    raise LayoutError('wrong_source')
                raw, file_name = layout._pbxl_raw(), layout.file_name
            else:
                raise LayoutError('not_excel')
            data, notes = xlsx_fill.fill(raw, sheet or '', start_cell or 'A1',
                                         bool(write_headers), table,
                                         file_name=file_name or '')
        except Exception as err:                           # noqa: BLE001
            return self._pbxl_fail(err)
        ext = '.xlsm' if (file_name or '').lower().endswith('.xlsm') else '.xlsx'
        stem = ''.join(c if c.isalnum() else '_' for c in
                       (table['title'] or 'layout').lower())
        stem = '_'.join(p for p in stem.split('_') if p)[:40] or 'layout'
        return {
            'ok': True,
            'file_b64': base64.b64encode(data).decode('ascii'),
            'filename': '%s_%s_%s%s' % (
                product_label(self.env).lower(), stem,
                fields.Date.context_today(self).isoformat(), ext),
            'mimetype': xlsx_fill.mimetype(ext),
            'notes': note_words(self.env, notes)
            + ([table['note']] if table['note'] else []),
            'rows': len(table['rows']),
            'cols': len(table['columns']),
        }

    @api.model
    def save(self, vals):
        """A new layout owned by the caller; returns its payload."""
        vals = vals if isinstance(vals, dict) else {}
        source = self._pbxl_source(vals.get('source_model'),
                                   vals.get('source_id'))
        Layout = self.env['pb.excel.layout']
        if Layout.sudo().search_count([('user_id', '=', self.env.uid)]) \
                >= LAYOUT_CAP:
            raise UserError(_("You already have %s Excel layouts. Delete one "
                              "you no longer use first.", LAYOUT_CAP))
        name = Layout._pbxl_clean_name(vals.get('name'))
        file_name = str(vals.get('file_name') or '')[:200]
        sheet = str(vals.get('sheet') or '')
        start = str(vals.get('start') or 'A1').strip().upper()
        headers = bool(vals.get('headers', True))
        table = self._pbxl_table(source)
        try:
            raw = self._pbxl_decode(vals.get('file_b64'))
            pkg = self._pbxl_check_place(raw, file_name, sheet, start,
                                         headers, table)
        except LayoutError as err:
            raise UserError(error_words(self.env, err.code, err.params)) \
                from err
        layout = Layout.create({
            'name': name,
            'user_id': self.env.uid,
            'shared': bool(vals.get('shared')),
            'source_model': source._name,
            'source_id': source.id,
            'file': base64.b64encode(raw),
            'file_name': file_name or 'layout' + pkg.ext,
            'sheet_name': sheet,
            'start_cell': xlsx_fill.cell_name(*xlsx_fill.split_cell(start)),
            'write_headers': headers,
            'has_macros': pkg.has_macros,
            'sheet_ok': True,
        })
        return layout._pbxl_payload()

    @api.model
    def detail(self, layout_id):
        """A saved layout with its file described, to change where the
        figures go."""
        layout, source = self._pbxl_layout(layout_id)
        out = {'layout': layout._pbxl_payload(),
               'table': self._pbxl_shape(self._pbxl_table(source))}
        try:
            out['file'] = self._pbxl_file_answer(layout._pbxl_raw(),
                                                 layout.file_name)
        except Exception as err:                           # noqa: BLE001
            out['file'] = self._pbxl_fail(err)
        return out

    @api.model
    def update(self, layout_id, vals):
        """Change the name, sheet, start cell, headings or sharing of one of
        your layouts."""
        layout, source = self._pbxl_layout(layout_id, write=True)
        vals = vals if isinstance(vals, dict) else {}
        write = {}
        if 'name' in vals:
            write['name'] = layout._pbxl_clean_name(vals['name'])
        if 'shared' in vals:
            write['shared'] = bool(vals['shared'])
        if 'headers' in vals:
            write['write_headers'] = bool(vals['headers'])
        if {'sheet', 'start', 'headers'} & set(vals):
            sheet = str(vals.get('sheet', layout.sheet_name) or '')
            start = str(vals.get('start', layout.start_cell) or 'A1').strip().upper()
            headers = bool(vals.get('headers', layout.write_headers))
            try:
                self._pbxl_check_place(layout._pbxl_raw(), layout.file_name,
                                       sheet, start, headers,
                                       self._pbxl_table(source))
            except LayoutError as err:
                raise UserError(error_words(self.env, err.code, err.params)) \
                    from err
            write.update({'sheet_name': sheet, 'sheet_ok': True,
                          'start_cell': xlsx_fill.cell_name(
                              *xlsx_fill.split_cell(start))})
        if write:
            layout.write(write)
        return layout._pbxl_payload()

    @api.model
    def rename(self, layout_id, name):
        return self.update(layout_id, {'name': name})

    @api.model
    def share(self, layout_id, shared):
        return self.update(layout_id, {'shared': bool(shared)})

    @api.model
    def remove(self, layout_id):
        layout, _source = self._pbxl_layout(layout_id, write=True)
        layout.unlink()
        return True

    @api.model
    def replace_file(self, layout_id, file_b64, file_name=''):
        """A new version of the file. The sheet and start cell are kept when
        the sheet is still there; otherwise the layout says so plainly and
        scheduled sends use the standard Excel until a sheet is picked."""
        layout, source = self._pbxl_layout(layout_id, write=True)
        try:
            raw = self._pbxl_decode(file_b64)
            pkg = xlsx_fill.Package(raw, file_name)
            answer = self._pbxl_file_answer(raw, file_name)
        except Exception as err:                           # noqa: BLE001
            return self._pbxl_fail(err)
        sheet_ok = True
        try:
            pkg.sheet(layout.sheet_name or '')
        except LayoutError:
            sheet_ok = False
        layout.write({
            'file': base64.b64encode(raw),
            'file_name': str(file_name or layout.file_name or '')[:200],
            'has_macros': pkg.has_macros,
            'sheet_ok': sheet_ok,
        })
        return {'ok': True,
                'layout': layout._pbxl_payload(),
                'file': answer,
                'table': self._pbxl_shape(self._pbxl_table(source))}

    @api.model
    def download(self, layout_id):
        """Download in my layout: fresh figures, as the caller, in the
        customer's own file. Never a broken file: when the layout cannot be
        used the standard Excel comes back with the reason."""
        layout, source = self._pbxl_layout(layout_id)
        table = self._pbxl_table(source)
        notes = []
        try:
            data, raw_notes = layout._pbxl_fill_with(table)
            name, mime = layout._pbxl_filename(), layout._pbxl_mimetype()
            notes = note_words(self.env, raw_notes)
            fallback, msg = False, ''
        except Exception as err:                           # noqa: BLE001
            code = err.code if isinstance(err, LayoutError) else 'unreadable'
            params = err.params if isinstance(err, LayoutError) else {}
            _logger.warning('pb_excel_layout: layout %s fell back to the '
                            'standard Excel: %s', layout.id, code)
            msg = error_words(self.env, code, params)
            name, data, mime = self._pbxl_standard(source, table)
            fallback = True
        layout.last_used = fields.Datetime.now()
        if table['note']:
            notes.append(table['note'])
        return {
            'ok': True,
            'file_b64': base64.b64encode(data).decode('ascii'),
            'filename': name,
            'mimetype': mime,
            'fallback': fallback,
            'msg': msg,
            'notes': notes,
            'rows': len(table['rows']),
        }
